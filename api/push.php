<?php
/**
 * 推送层：企业微信群机器人。
 *
 * 为什么不用 Bark / ntfy / Web Push：
 * - Bark 只有 iOS 客户端，安卓用不了。
 * - 国行安卓没有 Google 服务框架，也就没有 FCM 这条系统级推送通道。
 *   ntfy 在安卓上只能靠 App 自己开 WebSocket 常驻，MIUI / HyperOS 会杀后台，
 *   必须手动配「自启动 + 无限制 + 锁屏显示」，系统升级还可能失效。
 * - Web Push 同理，且在 iOS 上必须先加主屏。
 * 微信 / 企业微信的进程在各大厂商的白名单里，是国行安卓上唯一稳定的送达通道。
 *
 * 这个文件只负责「把一段文字发出去」，不判断该不该发。判断逻辑在调用方。
 */

const LB_PUSH_HOST = 'qyapi.weixin.qq.com';
const LB_PUSH_TIMEOUT = 6;
/* 企业微信文本消息上限 2048 字节，留点余量给装不下的情况 */
const LB_PUSH_MAX_BYTES = 2000;

/**
 * 只允许发到企业微信的域名。
 *
 * 这条不是多余的：webhook 地址由用户在设置页填写，后端拿到什么就往哪里 POST，
 * 不限制域名等于给站点开了一个 SSRF 口子（虽然目前只有站长自己用）。
 * 校验成本几乎为零，就别省。
 */
function lb_push_url_ok(string $url): bool
{
    if ($url === '') {
        return false;
    }
    $p = parse_url($url);
    if (!is_array($p)) {
        return false;
    }
    if (($p['scheme'] ?? '') !== 'https') {
        return false;
    }
    if (($p['host'] ?? '') !== LB_PUSH_HOST) {
        return false;
    }
    return ($p['path'] ?? '') === '/cgi-bin/webhook/send';
}

/** 按字节截断但绝不切断 UTF-8 字符。不用 mb_*，精简环境可能没装。 */
function lb_push_clip(string $s, int $limit = LB_PUSH_MAX_BYTES): string
{
    if (strlen($s) <= $limit) {
        return $s;
    }
    $piece = substr($s, 0, $limit - 3);
    $n = strlen($piece);
    $i = $n - 1;
    $trail = 0;
    while ($i >= 0 && (ord($piece[$i]) & 0xC0) === 0x80) {
        $i--;
        $trail++;
    }
    if ($i < 0) {
        return '…';
    }
    $lead = ord($piece[$i]);
    if ($lead < 0x80) {
        $need = 1;
    } elseif (($lead & 0xE0) === 0xC0) {
        $need = 2;
    } elseif (($lead & 0xF0) === 0xE0) {
        $need = 3;
    } elseif (($lead & 0xF8) === 0xF0) {
        $need = 4;
    } else {
        $need = 1;
    }
    if ($trail + 1 < $need) {
        $piece = substr($piece, 0, $i);
    }
    return $piece . '…';
}

/**
 * 把企业微信的响应翻译成人话。纯函数，方便单测。
 *
 * @return array{ok:bool, msg:string}
 */
function lb_push_interpret(int $http, ?string $body): array
{
    if ($http !== 200) {
        return ['ok' => false, 'msg' => 'HTTP ' . $http . '（网络或服务端问题）'];
    }
    if ($body === null || $body === '') {
        return ['ok' => false, 'msg' => '响应为空'];
    }
    $j = json_decode($body, true);
    if (!is_array($j)) {
        return ['ok' => false, 'msg' => '响应不是 JSON：' . substr($body, 0, 80)];
    }
    $code = isset($j['errcode']) ? (int)$j['errcode'] : -1;
    if ($code === 0) {
        return ['ok' => true, 'msg' => 'ok'];
    }
    $map = [
        93000 => 'webhook 地址无效（key 错了，或机器人已被删除）',
        45009 => '发送太频繁（每个机器人每分钟上限 20 条）',
        40008 => '消息类型不合法',
        40058 => '参数不合法（内容为空或超长）',
        60020 => '服务器 IP 不在白名单（当前不应触发，是自建应用的限制）',
    ];
    $why = $map[$code] ?? ('errcode ' . $code . ' ' . (string)($j['errmsg'] ?? ''));
    return ['ok' => false, 'msg' => trim($why)];
}

/**
 * 真的发一次 HTTP POST。
 * 优先用 curl（线上必然有）；万一没装则退回 stream context。
 *
 * @return array{http:int, body:?string, error:string}
 */
function lb_push_http(string $url, string $payload): array
{
    $headers = ['Content-Type: application/json; charset=utf-8'];

    if (function_exists('curl_init')) {
        $ch = curl_init($url);
        curl_setopt_array($ch, [
            CURLOPT_POST => true,
            CURLOPT_POSTFIELDS => $payload,
            CURLOPT_HTTPHEADER => $headers,
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_CONNECTTIMEOUT => 4,
            CURLOPT_TIMEOUT => LB_PUSH_TIMEOUT,
            CURLOPT_SSL_VERIFYPEER => true,
            CURLOPT_SSL_VERIFYHOST => 2,
            CURLOPT_FOLLOWLOCATION => false,
        ]);
        $body = curl_exec($ch);
        $http = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE);
        $err = (string)curl_error($ch);
        unset($ch);
        if ($body === false) {
            return ['http' => $http, 'body' => null, 'error' => $err !== '' ? $err : '请求失败'];
        }
        return ['http' => $http, 'body' => (string)$body, 'error' => ''];
    }

    $ctx = stream_context_create([
        'http' => [
            'method' => 'POST',
            'header' => implode("\r\n", $headers),
            'content' => $payload,
            'timeout' => LB_PUSH_TIMEOUT,
            'ignore_errors' => true,
        ],
        'ssl' => ['verify_peer' => true, 'verify_peer_name' => true],
    ]);
    $body = @file_get_contents($url, false, $ctx);
    $http = 0;
    foreach ($http_response_header ?? [] as $line) {
        if (preg_match('#^HTTP/\S+\s+(\d{3})#', $line, $m)) {
            $http = (int)$m[1];
        }
    }
    if ($body === false) {
        return ['http' => $http, 'body' => null, 'error' => '请求失败（stream）'];
    }
    return ['http' => $http, 'body' => $body, 'error' => ''];
}

/**
 * 发一条消息。$type 为 text 或 markdown。
 *
 * 刻意不抛异常：调用方是每分钟跑的定时任务，一次失败只该记日志，
 * 不该让整轮中断（否则一条烂消息会让后面所有提醒都不发）。
 */
function lb_push_send(string $webhook, string $content, string $type = 'text', ?string &$err = null): bool
{
    $err = '';
    if (!lb_push_url_ok($webhook)) {
        $err = 'webhook 地址不合法（必须是 https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=...）';
        return false;
    }
    $content = trim($content);
    if ($content === '') {
        $err = '内容为空';
        return false;
    }
    $content = lb_push_clip($content);

    $payload = json_encode(
        ['msgtype' => $type, $type => ['content' => $content]],
        JSON_UNESCAPED_UNICODE
    );
    if (!is_string($payload)) {
        $err = '内容无法序列化';
        return false;
    }

    $r = lb_push_http($webhook, $payload);
    if ($r['error'] !== '') {
        $e = $r['error'];
        /* 这个错误信息本身不提「怎么办」，运维看到只会以为是网络问题。
           实际原因几乎都是 PHP 没配 CA 证书包，而它会让「所有」推送静默失败。 */
        if (stripos($e, 'certificate') !== false || stripos($e, 'SSL') !== false) {
            $e .= '（服务器 PHP 缺少根证书包：检查 php.ini 的 curl.cainfo 与 openssl.cafile）';
        }
        $err = '网络不通：' . $e;
        return false;
    }
    $v = lb_push_interpret($r['http'], $r['body']);
    if (!$v['ok']) {
        $err = $v['msg'];
        return false;
    }
    return true;
}
