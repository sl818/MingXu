<?php
/**
 * SMTP 发信层（QQ 邮箱适配，原生 PHP，零 composer 依赖）。
 *
 * 只负责「把一封文本邮件发出去」和「按 uid 读写发信配置」，
 * 不判断该不该发、不碰 boards / notices / push_sent。
 * 既有的企业微信推送（push.php）与任何收信逻辑都不在本文件职责内。
 *
 * ── QQ 邮箱官方参数（help.mail.qq.com/detail/0/1088）────────────────
 *   SMTP 服务器 smtp.qq.com；SSL/TLS 端口 465（隐式 TLS），
 *   也可用 587（STARTTLS）；登录用户名是完整邮箱地址；
 *   密码栏必须填 16 位授权码，不能填 QQ 登录密码。
 *
 * ── 三个最容易踩的坑（官方 1087 / 1083 / 1071）─────────────────────
 *   1) 授权码 ≠ QQ 密码。第三方客户端必须用授权码；改过 QQ 主密码后，
 *      所有旧授权码立即失效，要重新生成。
 *   2) From 必须和登录账号一致。用 @qq.com / @foxmail.com / @tencent.com
 *      冒充发件人会触发 550 Invalid "From" found in header（无 DKIM 签名）。
 *      本层直接强制 from === user，不给用户填错的机会。
 *   3) 频率限制是账号级的：550 Sender frequency limited。
 *      分钟 / 小时 / 日三级阶梯封禁，换 IP、换域名都没用，只能降低频率。
 *
 * 依赖：bootstrap.php（lb_db / lb_fail…）与 secret_box.php 必须先加载。
 */
if (!defined('LIFEBOARD_API')) {
    http_response_code(404);
    exit;
}

const LB_MAIL_TIMEOUT = 15;          // 单条 SMTP 命令的读写超时（秒）
const LB_MAIL_CONNECT_TIMEOUT = 10;  // TCP / TLS 握手超时
const LB_MAIL_MAX_LINE = 8192;
const LB_MAIL_PORTS = [25, 465, 587, 2525];
const LB_MAIL_SECURES = ['ssl', 'tls', 'none'];

/** 只放行公网域名，禁止 IP 与本地后缀：配置由用户填写，不能变成内网探测口子。 */
function lb_mail_host_ok(string $host): bool
{
    $host = strtolower(trim($host));
    if ($host === '' || strlen($host) > 190) {
        return false;
    }
    if (filter_var($host, FILTER_VALIDATE_IP) !== false) {
        return false;
    }
    if (in_array($host, ['localhost', 'localhost.localdomain'], true)) {
        return false;
    }
    if (preg_match('/^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$/', $host) !== 1) {
        return false;
    }
    foreach (['.local', '.internal', '.lan', '.home.arpa'] as $suffix) {
        if (substr($host, -strlen($suffix)) === $suffix) {
            return false;
        }
    }
    return true;
}

function lb_mail_port_ok(int $port): bool
{
    return in_array($port, LB_MAIL_PORTS, true);
}

function lb_mail_secure_ok(string $secure): bool
{
    return in_array($secure, LB_MAIL_SECURES, true);
}

/** 官方明确要求 From 与登录账号一致；顺带挡掉邮件头注入。 */
function lb_mail_from_ok(string $from, string $user): bool
{
    return $from !== '' && $user !== ''
        && strtolower($from) === strtolower($user)
        && filter_var($from, FILTER_VALIDATE_EMAIL) !== false;
}

/**
 * 把 SMTP 的响应翻译成人话。纯函数，便于单测。
 * $stage 只用来给认证失败补一句上下文，不影响错误码本身。
 *
 * @return array{ok:bool, msg:string}
 */
function lb_mail_explain(int $code, string $text, string $stage = ''): array
{
    $low = strtolower($text);
    if ($code >= 200 && $code < 300) {
        return ['ok' => true, 'msg' => 'ok'];
    }

    /* 认证阶段：官方 1087 —— 第三方客户端必须用 16 位授权码 */
    if ($code === 535 || ($code === 530 && $stage === 'auth')) {
        return ['ok' => false, 'msg' =>
            '认证失败：这里要填 16 位授权码，不是 QQ 登录密码。'
            . '先到 QQ 邮箱 → 设置 → 账号与安全 → 开启 SMTP 服务并生成授权码；'
            . '如果之前改过 QQ 主密码，旧授权码会全部失效，需要重新生成。'
            . ($text !== '' ? '（服务端：' . $text . '）' : '')];
    }
    /* 官方 1083：From 含腾讯系域名但无 DKIM 签名 */
    if ($code === 550 && (strpos($low, 'invalid "from"') !== false || strpos($low, 'from') !== false && strpos($low, 'invalid') !== false)) {
        return ['ok' => false, 'msg' =>
            '发件人被拒：邮件 From 必须和登录账号完全一致，不能用别的 QQ / foxmail 地址发信。'
            . '（服务端：' . $text . '）'];
    }
    /* 官方 1071：账号级频率限制，换 IP 无效 */
    if ($code === 550 && (strpos($low, 'frequency limited') !== false || strpos($low, 'frequency') !== false)) {
        return ['ok' => false, 'msg' =>
            '发信太频繁被临时限制：这是发件账号级的分钟 / 小时 / 日三级限流，换 IP 或换域名都没用。'
            . '请暂停发信一段时间，并把通知时间错开。'];
    }
    if ($code === 550 || $code === 553 || $code === 554) {
        return ['ok' => false, 'msg' =>
            '服务器拒收：检查收件人地址是否有效。'
            . ($text !== '' ? '（服务端：' . $text . '）' : '')];
    }
    if ($code === 421) {
        return ['ok' => false, 'msg' =>
            '服务器暂时不可用或连接数超限，稍后再试。'
            . ($text !== '' ? '（服务端：' . $text . '）' : '')];
    }
    if ($code === 450 || $code === 451 || $code === 452) {
        return ['ok' => false, 'msg' =>
            '服务器临时故障，稍后再试。' . ($text !== '' ? '（服务端：' . $text . '）' : '')];
    }
    if ($code === 530) {
        return ['ok' => false, 'msg' =>
            '未通过认证：确认 SMTP 服务已开启、端口与加密方式匹配。'
            . ($text !== '' ? '（服务端：' . $text . '）' : '')];
    }
    if ($code === 0) {
        return ['ok' => false, 'msg' => '连接或读取超时，检查端口（SSL 用 465）、服务器出站防火墙是否放行。'];
    }
    return ['ok' => false, 'msg' => 'SMTP 返回 ' . $code . ($text !== '' ? '：' . $text : '')];
}

/** RFC 2047：非 ASCII 主题 / 称呼必须编码，顺带去掉换行防头注入。 */
function lb_mail_header_text(string $s): string
{
    $s = str_replace(["\r", "\n"], '', $s);
    if ($s === '' || preg_match('/^[\x20-\x7E]+$/', $s) === 1) {
        return $s;
    }
    return '=?UTF-8?B?' . base64_encode($s) . '?=';
}

/** base64 正文按 76 列折行，符合 RFC 2045。 */
function lb_mail_body_b64(string $text): string
{
    return rtrim(chunk_split(base64_encode($text), 76, "\r\n"), "\r\n");
}

/**
 * 读一条 SMTP 响应（可能多行）。
 * text 是末行文本；raw 是全部行 —— EHLO 的 STARTTLS / AUTH 能力在中间行，
 * 只看 text 会把 QQ 的 587 端口误判成「不支持 STARTTLS」。
 */
function lb_mail_cmd($fp, string $cmd, string &$err): array
{
    if ($cmd !== '' && fwrite($fp, $cmd . "\r\n") === false) {
        $err = '写入 SMTP 连接失败';
        return ['code' => 0, 'text' => '', 'raw' => []];
    }
    $code = 0;
    $text = '';
    $raw = [];
    while (count($raw) < 100) {
        $line = fgets($fp, LB_MAIL_MAX_LINE);
        if ($line === false) {
            $err = '读取 SMTP 响应超时';
            return ['code' => 0, 'text' => $text, 'raw' => $raw];
        }
        $clean = rtrim($line, "\r\n");
        $raw[] = $clean;
        if (preg_match('/^(\d{3})([ -])(.*)$/', $clean, $m) === 1) {
            $code = (int)$m[1];
            $text = $m[3];
            if ($m[2] === ' ') {
                return ['code' => $code, 'text' => $text, 'raw' => $raw];
            }
        }
    }
    $err = 'SMTP 响应行数异常';
    return ['code' => 0, 'text' => $text, 'raw' => $raw];
}

/** 按字符安全截断，给精简环境兜底（可能没装 mbstring）。 */
function lb_mail_clip(string $s, int $limit): string
{
    if (function_exists('mb_substr')) {
        return mb_substr($s, 0, $limit, 'UTF-8');
    }
    if (strlen($s) <= $limit) {
        return $s;
    }
    $piece = substr($s, 0, $limit);
    while (strlen($piece) > 0 && (ord($piece[strlen($piece) - 1]) & 0xC0) === 0x80) {
        $piece = substr($piece, 0, -1);
    }
    return $piece;
}

/**
 * 发一封纯文本邮件。$cfg 为已校验的地址数组：
 * host / port / secure / user / from / name / secret。
 *
 * 刻意不抛异常：调用方可能是每分钟一次的定时任务，一封坏信不该中断整轮。
 */
function lb_mail_smtp_send(array $cfg, string $to, string $subject, string $body, ?string &$err): bool
{
    $err = '';
    $host = (string)$cfg['host'];
    $port = (int)$cfg['port'];
    $secure = (string)$cfg['secure'];
    $user = (string)$cfg['user'];
    $from = (string)$cfg['from'];
    $name = (string)$cfg['name'];
    $secret = (string)$cfg['secret'];

    if (!lb_mail_host_ok($host) || !lb_mail_port_ok($port) || !lb_mail_secure_ok($secure)) {
        $err = 'SMTP 服务器 / 端口 / 加密方式不合法';
        return false;
    }
    if (!lb_mail_from_ok($from, $user) || filter_var($to, FILTER_VALIDATE_EMAIL) === false) {
        $err = '发件人必须与登录账号一致，且收件人邮箱要合法';
        return false;
    }
    if ($secret === '') {
        $err = '还没填授权码';
        return false;
    }
    $subject = str_replace(["\r", "\n"], '', $subject);
    if ($subject === '' || $body === '') {
        $err = '主题或正文为空';
        return false;
    }

    $remote = ($secure === 'ssl' ? 'ssl://' : 'tcp://') . $host . ':' . $port;
    $ctx = stream_context_create([
        'ssl' => [
            'verify_peer' => true,
            'verify_peer_name' => true,
            'peer_name' => $host,
            'SNI_enabled' => true,
            'crypto_method' => STREAM_CRYPTO_METHOD_TLS_CLIENT,
        ],
    ]);
    $fp = @stream_socket_client(
        $remote,
        $errno,
        $errstr,
        LB_MAIL_CONNECT_TIMEOUT,
        STREAM_CLIENT_CONNECT,
        $ctx
    );
    if (!$fp) {
        $hint = ($secure === 'ssl' && $port === 465)
            ? '服务器出站 465 端口可能被防火墙拦了。'
            : '检查端口与加密方式是否匹配（QQ：465+SSL/TLS 或 587+STARTTLS）。';
        $err = '连不上 ' . $host . ':' . $port . '：' . ($errstr !== '' ? $errstr : '网络不通') . ' ' . $hint;
        return false;
    }
    stream_set_timeout($fp, LB_MAIL_TIMEOUT);

    $r = lb_mail_cmd($fp, '', $err);                    // 220 greeting
    if ($err !== '' || $r['code'] !== 220) {
        fclose($fp);
        $err = $err !== '' ? $err : ('服务器没有回应 220：' . $r['text']);
        return false;
    }

    $hello = substr((string)strrchr($from, '@'), 1);
    if ($hello === '' || !lb_mail_host_ok($hello)) {
        $hello = $host;
    }
    $r = lb_mail_cmd($fp, 'EHLO ' . $hello, $err);
    if ($err !== '' || $r['code'] !== 250) {
        fclose($fp);
        $err = $err !== '' ? $err : ('EHLO 被拒：' . lb_mail_explain($r['code'], $r['text'])['msg']);
        return false;
    }
    $ehlo = implode("\n", $r['raw']);

    /* 587 端口：文档把它也写成「SSL/TLS」，实际协议是 STARTTLS——
       先明文连上再升级。升级后能力列表作废，必须重新 EHLO。 */
    if ($secure === 'tls') {
        if (stripos($ehlo, 'STARTTLS') === false) {
            fclose($fp);
            $err = '服务器不支持 STARTTLS，请改用 SSL/TLS + 465 端口';
            return false;
        }
        $r = lb_mail_cmd($fp, 'STARTTLS', $err);
        if ($err !== '' || $r['code'] !== 220) {
            fclose($fp);
            $err = $err !== '' ? $err : ('STARTTLS 失败：' . $r['text']);
            return false;
        }
        if (!@stream_socket_enable_crypto($fp, true, STREAM_CRYPTO_METHOD_TLS_CLIENT)) {
            fclose($fp);
            $err = 'TLS 升级失败：检查服务器 CA 证书（php.ini 的 openssl.cafile）';
            return false;
        }
        $r = lb_mail_cmd($fp, 'EHLO ' . $hello, $err);
        if ($err !== '' || $r['code'] !== 250) {
            fclose($fp);
            $err = $err !== '' ? $err : ('升级后 EHLO 被拒：' . $r['text']);
            return false;
        }
        $ehlo = implode("\n", $r['raw']);
    }

    /* 统一走 AUTH LOGIN：QQ / Foxmail / 大多数国内邮箱都支持，
       且比 PLAIN 少一个「服务器是否声明 PLAIN」的解析分支。
       能力里没写 AUTH 也照试一次，服务器会在 5xx 里明确回绝。 */
    $r = lb_mail_cmd($fp, 'AUTH LOGIN', $err);
    if ($err !== '' || $r['code'] !== 334) {
        fclose($fp);
        if ($err === '' && stripos($ehlo, 'AUTH') === false) {
            $err = '服务器没有声明 AUTH 能力：确认连的是 SMTP 端口（465 / 587），不是 POP3 / IMAP';
        } else {
            $err = $err !== '' ? $err : lb_mail_explain($r['code'], $r['text'], 'auth')['msg'];
        }
        return false;
    }
    $r = lb_mail_cmd($fp, base64_encode($user), $err);
    if ($err !== '' || $r['code'] !== 334) {
        fclose($fp);
        $err = $err !== '' ? $err : lb_mail_explain($r['code'], $r['text'], 'auth')['msg'];
        return false;
    }
    $r = lb_mail_cmd($fp, base64_encode($secret), $err);
    if ($err !== '' || $r['code'] !== 235) {
        fclose($fp);
        $err = $err !== '' ? $err : lb_mail_explain($r['code'], $r['text'], 'auth')['msg'];
        return false;
    }

    $r = lb_mail_cmd($fp, 'MAIL FROM:<' . $from . '>', $err);
    if ($err !== '' || $r['code'] !== 250) {
        fclose($fp);
        $err = $err !== '' ? $err : lb_mail_explain($r['code'], $r['text'], 'mailfrom')['msg'];
        return false;
    }
    $r = lb_mail_cmd($fp, 'RCPT TO:<' . $to . '>', $err);
    if ($err !== '' || ($r['code'] !== 250 && $r['code'] !== 251)) {
        fclose($fp);
        $err = $err !== '' ? $err : lb_mail_explain($r['code'], $r['text'], 'rcpt')['msg'];
        return false;
    }
    $r = lb_mail_cmd($fp, 'DATA', $err);
    if ($err !== '' || $r['code'] !== 354) {
        fclose($fp);
        $err = $err !== '' ? $err : ('DATA 被拒：' . lb_mail_explain($r['code'], $r['text'])['msg']);
        return false;
    }

    $domain = substr((string)strrchr($from, '@'), 1);
    $headers = [
        'Date: ' . date('r'),
        'From: ' . (($name !== '' ? lb_mail_header_text($name) . ' ' : '') . '<' . $from . '>'),
        'To: <' . $to . '>',
        'Subject: ' . lb_mail_header_text($subject),
        'Message-ID: <' . bin2hex(random_bytes(12)) . '@' . $domain . '>',
        'MIME-Version: 1.0',
        'Content-Type: text/plain; charset=UTF-8',
        'Content-Transfer-Encoding: base64',
    ];
    $message = implode("\r\n", $headers) . "\r\n\r\n" . lb_mail_body_b64($body) . "\r\n.\r\n";
    if (fwrite($fp, $message) === false) {
        fclose($fp);
        $err = '发送正文失败';
        return false;
    }
    $r = lb_mail_cmd($fp, '', $err);
    fclose($fp);
    if ($err !== '' || $r['code'] !== 250) {
        $err = $err !== '' ? $err : lb_mail_explain($r['code'], $r['text'], 'data')['msg'];
        return false;
    }
    return true;
}

/** 对外的底层发送入口：先按官方限制校验，再真正连接 SMTP。 */
function lb_mail_send(array $cfg, string $to, string $subject, string $body, ?string &$err): bool
{
    $err = '';
    $host = trim((string)($cfg['host'] ?? ''));
    $port = (int)($cfg['port'] ?? 465);
    $secure = (string)($cfg['secure'] ?? 'ssl');
    $user = trim((string)($cfg['user'] ?? ''));
    $from = trim((string)($cfg['from'] ?? ''));
    $name = trim((string)($cfg['name'] ?? ''));
    $secret = (string)($cfg['secret'] ?? '');

    if (!lb_mail_host_ok($host)) {
        $err = 'SMTP 服务器地址不合法（只接受公网域名，例如 smtp.qq.com）';
        return false;
    }
    if (!lb_mail_port_ok($port)) {
        $err = '端口只能用 25 / 465 / 587 / 2525；QQ 邮箱推荐 465';
        return false;
    }
    if (!lb_mail_secure_ok($secure)) {
        $err = '安全协议只能是 SSL/TLS、STARTTLS 或不加密';
        return false;
    }
    if (filter_var($user, FILTER_VALIDATE_EMAIL) === false) {
        $err = '用户名要填完整邮箱地址，例如 123456789@qq.com';
        return false;
    }
    if (!lb_mail_from_ok($from, $user)) {
        $err = '发件人必须和用户名（登录账号）完全一致，否则会被判为伪造发件人（550 Invalid "From"）';
        return false;
    }
    if (lb_strlen($name) > 60) {
        $err = '称呼最多 60 个字';
        return false;
    }
    return lb_mail_smtp_send([
        'host' => $host, 'port' => $port, 'secure' => $secure,
        'user' => $user, 'from' => $from, 'name' => $name, 'secret' => $secret,
    ], $to, $subject, $body, $err);
}

/* ───────────────── 配置读写（每用户一份，授权码只存密文） ───────────────── */

/** 读取内部配置（含解密后的授权码）。绝不能直接回给前端。 */
function lb_mail_cfg_load(PDO $pdo, int $uid): array
{
    $default = [
        'host' => 'smtp.qq.com', 'port' => 465, 'secure' => 'ssl',
        'user' => '', 'from' => '', 'name' => '', 'secret' => '',
        'enabled' => false, 'hasSecret' => false, 'lastError' => '', 'lastTestAt' => '',
    ];
    try {
        $st = $pdo->prepare('SELECT * FROM user_mail_config WHERE user_id = ? LIMIT 1');
        $st->execute([$uid]);
        $row = $st->fetch();
    } catch (PDOException $e) {
        return $default; // 迁移还没跑时，页面仍能正常打开
    }
    if (!$row) {
        return $default;
    }
    $enc = (string)($row['secret_enc'] ?? '');
    return [
        'host' => (string)($row['smtp_host'] ?? 'smtp.qq.com'),
        'port' => (int)($row['smtp_port'] ?? 465),
        'secure' => (string)($row['smtp_secure'] ?? 'ssl'),
        'user' => (string)($row['smtp_user'] ?? ''),
        'from' => (string)($row['from_email'] ?? ''),
        'name' => (string)($row['from_name'] ?? ''),
        'secret' => $enc !== '' ? lb_secret_decrypt($enc) : '',
        'enabled' => (int)($row['enabled'] ?? 0) === 1,
        'hasSecret' => $enc !== '',
        'lastError' => (string)($row['last_error'] ?? ''),
        'lastTestAt' => (string)($row['last_test_at'] ?? ''),
    ];
}

/** 给前端的配置：授权码只给一个「有没有」的布尔，任何片段都不回显。 */
function lb_mail_cfg_public(array $cfg): array
{
    return [
        'host' => (string)$cfg['host'],
        'port' => (int)$cfg['port'],
        'secure' => (string)$cfg['secure'],
        'user' => (string)$cfg['user'],
        'from' => (string)$cfg['from'],
        'name' => (string)$cfg['name'],
        'hasSecret' => !empty($cfg['hasSecret']),
        'enabled' => !empty($cfg['enabled']),
        'lastError' => (string)$cfg['lastError'],
        'lastTestAt' => (string)$cfg['lastTestAt'],
    ];
}

/**
 * 保存配置。$in['secret'] 留空 = 保留原授权码（前端不回显，留空是常态）。
 * @return array{ok:bool,error:string,cfg:array}
 */
function lb_mail_cfg_save(PDO $pdo, int $uid, array $in): array
{
    $old = lb_mail_cfg_load($pdo, $uid);
    $host = trim((string)($in['host'] ?? $old['host']));
    $port = (int)($in['port'] ?? $old['port']);
    $secure = (string)($in['secure'] ?? $old['secure']);
    $user = trim((string)($in['user'] ?? $old['user']));
    $from = trim((string)($in['from'] ?? $old['from']));
    $name = trim((string)($in['name'] ?? $old['name']));
    $secret = (string)($in['secret'] ?? '');
    $enabled = !empty($in['enabled']);

    if (!lb_mail_host_ok($host)) {
        return ['ok' => false, 'error' => 'SMTP 服务器地址不合法（只接受公网域名，例如 smtp.qq.com）', 'cfg' => $old];
    }
    if (!lb_mail_port_ok($port)) {
        return ['ok' => false, 'error' => '端口只能用 25 / 465 / 587 / 2525；QQ 邮箱推荐 465', 'cfg' => $old];
    }
    if (!lb_mail_secure_ok($secure)) {
        return ['ok' => false, 'error' => '安全协议只能是 ssl / tls / none', 'cfg' => $old];
    }
    if ($user !== '' && filter_var($user, FILTER_VALIDATE_EMAIL) === false) {
        return ['ok' => false, 'error' => '用户名要填完整邮箱地址，例如 123456789@qq.com', 'cfg' => $old];
    }
    if ($from !== '' && !lb_mail_from_ok($from, $user)) {
        return ['ok' => false, 'error' => '发件人必须和用户名完全一致，否则会被判为伪造发件人（550 Invalid "From"）', 'cfg' => $old];
    }
    if (lb_strlen($name) > 60) {
        return ['ok' => false, 'error' => '称呼最多 60 个字', 'cfg' => $old];
    }
    if ($secret !== '' && !lb_secret_ready()) {
        return ['ok' => false, 'error' => '加密组件不可用：请执行数据库迁移，或在 api/config.php 配置 mail_secret', 'cfg' => $old];
    }
    if ($enabled && ($user === '' || $secret === '' && !$old['hasSecret'])) {
        return ['ok' => false, 'error' => '启用前先填好用户名和授权码', 'cfg' => $old];
    }

    $enc = $secret !== '' ? lb_secret_encrypt($secret) : null;
    if ($secret !== '' && $enc === '') {
        return ['ok' => false, 'error' => '授权码加密失败，配置未保存', 'cfg' => $old];
    }
    try {
        /* secret_enc 传 null = 保留原密文；ON DUPLICATE KEY 保证一个用户只有一行 */
        $st = $pdo->prepare(
            'INSERT INTO user_mail_config
                (user_id, smtp_host, smtp_port, smtp_secure, smtp_user, from_email, from_name, secret_enc, enabled, updated_at)
             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NOW())
             ON DUPLICATE KEY UPDATE
                smtp_host = VALUES(smtp_host), smtp_port = VALUES(smtp_port),
                smtp_secure = VALUES(smtp_secure), smtp_user = VALUES(smtp_user),
                from_email = VALUES(from_email), from_name = VALUES(from_name),
                secret_enc = COALESCE(VALUES(secret_enc), secret_enc),
                enabled = VALUES(enabled), updated_at = NOW()'
        );
        $st->execute([$uid, $host, $port, $secure, $user, $from, $name, $enc, $enabled ? 1 : 0]);
    } catch (PDOException $e) {
        return ['ok' => false, 'error' => '保存失败：' . $e->getMessage(), 'cfg' => $old];
    }
    $cfg = lb_mail_cfg_load($pdo, $uid);
    $cfg['enabled'] = $enabled;
    return ['ok' => true, 'error' => '', 'cfg' => $cfg];
}

/** 记录一次测试结果（成功也留时间，失败留原因给页面显示）。 */
function lb_mail_cfg_mark(PDO $pdo, int $uid, bool $ok, string $error): void
{
    try {
        $st = $pdo->prepare(
            'UPDATE user_mail_config SET last_test_at = NOW(), last_error = ? WHERE user_id = ?'
        );
        $st->execute([$ok ? '' : lb_mail_clip($error, 500), $uid]);
    } catch (PDOException $e) {
        /* 写日志失败不该让测试结果本身丢失 */
    }
}

/**
 * 通知调用入口：给业务代码发一封邮件到用户自己的邮箱。
 * 例：$ok = lb_mail_send_to_user(lb_db(), $uid, '该吃药了', '...', $why);
 *
 * 没配置、没开启、没授权码时返回 false 并写清楚原因，绝不静默吞掉。
 */
function lb_mail_send_to_user(PDO $pdo, int $uid, string $subject, string $body, ?string &$err): bool
{
    $err = '';
    $cfg = lb_mail_cfg_load($pdo, $uid);
    if (!$cfg['enabled'] || $cfg['user'] === '') {
        $err = '用户没有开启邮件提醒';
        return false;
    }
    if ($cfg['secret'] === '') {
        $err = '授权码无法解密，请在配置页重新填写';
        return false;
    }
    return lb_mail_send($cfg, $cfg['user'], $subject, $body, $err);
}
