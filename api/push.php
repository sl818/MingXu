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

/* 依赖 schedule.php 计算「这一分钟该发什么」。
   schedule.php 依赖 ics.php 的日期工具，而 ics.php 有 LIFEBOARD_API 保护，
   所以调用方（api.php / tools / e2e）必须已经定义了这个常量。 */
require_once __DIR__ . '/schedule.php';

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
function lb_push_send(string $webhook, string $content, ?string &$err = null, string $type = 'text'): bool
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

/**
 * 检测 push_sent 有没有 content 列。
 * 旧库没跑迁移时不写正文就好，绝不能因为一个可选列让整轮推送崩掉——
 * 那意味着所有提醒都发不出去。
 *
 * 刻意不用 static 缓存：一轮只查一次，开销可忽略，但缓存会在「同一进程里
 * 先查了没列的表、再查有列的表」时给出错误答案（测试里的多实例就会踩）。
 */
function lb_push_sent_has_content(PDO $pdo): bool
{
    try {
        if ($pdo->getAttribute(PDO::ATTR_DRIVER_NAME) === 'sqlite') {
            foreach ($pdo->query("PRAGMA table_info(push_sent)")->fetchAll() as $c) {
                if (($c['name'] ?? '') === 'content') {
                    return true;
                }
            }
            return false;
        }
        return $pdo->query("SHOW COLUMNS FROM push_sent LIKE 'content'")->fetchAll() !== [];
    } catch (PDOException $e) {
        return false;
    }
}

/**
 * 跑一轮推送：算出现在该发什么，逐条发出去。
 *
 * 逻辑和 IO 分开是有意的——发送器由调用方传入，测试时可以塞一个假的，
 * 于是「去重是否正确」「发失败会不会回滚」这些最容易写错的地方能被穷举验证，
 * 而不是靠人肉盯线上。
 *
 * @param callable $sender function(string $webhook, string $content, ?string &$err): bool
 * @return array{sent:int, skipped:int, failed:int, items:array<int,array>}
 */
/** 表存在性：老库没跑迁移时不能直接查，否则整轮推送挂掉 */
function lb_table_exists(PDO $pdo, string $table): bool
{
    if (preg_match('/^[A-Za-z_][A-Za-z0-9_]*$/', $table) !== 1) {
        return false;
    }
    try {
        if ($pdo->getAttribute(PDO::ATTR_DRIVER_NAME) === 'sqlite') {
            $st = $pdo->prepare("SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?");
            $st->execute([$table]);
            return (bool)$st->fetchColumn();
        }
        /* MySQL 的 SHOW 语句不支持参数绑定（prepare 会失败 → 这里被 catch 成 false，
           结果邮件用户永远捞不出来）。表名已过白名单，直接拼接才是正确写法。 */
        return (bool)$pdo->query("SHOW TABLES LIKE '" . $table . "'")->fetchColumn();
    } catch (PDOException $e) {
        return false;
    }
}

/* ===== 历史推送记录（v216）=====
   push_log 是给人看的观测日志：ok / fail / skip 三态，不参与去重。
   表不存在时静默降级（不写、接口返回空），与 content 列的兼容思路一致。 */

function lb_push_log_ready(PDO $pdo): bool
{
    /* 不能用 static 缓存：同一进程会先后打开多个连接（测试/多租户），表有无是 per-连接的事 */
    try {
        if ($pdo->getAttribute(PDO::ATTR_DRIVER_NAME) === 'sqlite') {
            $row = $pdo->query("SELECT name FROM sqlite_master WHERE type='table' AND name='push_log'")->fetch();
        } else {
            $row = $pdo->query("SHOW TABLES LIKE 'push_log'")->fetch();
        }
        $cache = (bool)$row;
    } catch (PDOException $e) {
        $cache = false;
    }
    return $cache;
}

function lb_push_log_has_board(PDO $pdo): bool
{
    try {
        if ($pdo->getAttribute(PDO::ATTR_DRIVER_NAME) === 'sqlite') {
            foreach ($pdo->query('PRAGMA table_info(push_log)')->fetchAll() as $c) {
                if (($c['name'] ?? '') === 'board') {
                    return true;
                }
            }
            return false;
        }
        return $pdo->query("SHOW COLUMNS FROM push_log LIKE 'board'")->fetchAll() !== [];
    } catch (PDOException $e) {
        return false;
    }
}

function lb_push_log_add(PDO $pdo, int $uid, string $at, string $channel, string $kind,
                         string $key, string $content, string $status, string $error = '',
                         string $board = ''): void
{
    if (!lb_push_log_ready($pdo) || !in_array($status, ['ok', 'fail', 'skip'], true)) {
        return;
    }
    try {
        if (lb_push_log_has_board($pdo)) {
            $pdo->prepare('INSERT INTO push_log (user_id, at, channel, board, kind, slot_key, content, status, error) '
                . 'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)')
                ->execute([$uid, $at, $channel, $board, $kind, $key, $content, $status,
                           $error !== '' ? lb_notify_clip($error, 500) : null]);
        } else {
            /* 老表没有 board 列：照常落日志，只是历史面板标不了浏览器渠道 */
            $pdo->prepare('INSERT INTO push_log (user_id, at, channel, kind, slot_key, content, status, error) '
                . 'VALUES (?, ?, ?, ?, ?, ?, ?, ?)')
                ->execute([$uid, $at, $channel, $kind, $key, $content, $status,
                           $error !== '' ? lb_notify_clip($error, 500) : null]);
        }
    } catch (PDOException $e) {
        /* 日志写不进去不影响发送主链路 */
    }
}

/** 读最近 N 组历史记录（按 slot_key 聚合：一张卡 = 一次提醒，组内逐渠道状态） */
function lb_push_log_list(PDO $pdo, int $uid, int $limit = 50): array
{
    if (!lb_push_log_ready($pdo)) {
        return [];
    }
    try {
        $hasBoard = lb_push_log_has_board($pdo);
        $cols = 'at, channel, kind, slot_key, content, status, error' . ($hasBoard ? ', board' : '');
        $st = $pdo->prepare('SELECT ' . $cols . ' FROM push_log WHERE user_id = ? '
            . 'ORDER BY at DESC, id DESC LIMIT ' . max(1, min(500, $limit * 4)));
        $st->execute([$uid]);
        $groups = [];
        foreach ($st->fetchAll() as $r) {
            $key = (string)$r['slot_key'];
            if (!isset($groups[$key])) {
                $groups[$key] = [
                    'key' => $key,
                    'at' => (string)$r['at'],
                    'kind' => (string)$r['kind'],
                    'board' => $hasBoard ? (string)($r['board'] ?? '') : '',
                    'content' => (string)($r['content'] ?? ''),
                    'rows' => [],
                ];
            }
            $groups[$key]['rows'][] = [
                'channel' => (string)$r['channel'],
                'status' => (string)$r['status'],
                'error' => (string)($r['error'] ?? ''),
            ];
        }
        /* 聚合状态：有 ok 无 fail=ok；混合=part；全 fail=fail；只有 skip=skip */
        $out = [];
        foreach ($groups as $g) {
            $nOk = 0;
            $nFail = 0;
            $nSkip = 0;
            foreach ($g['rows'] as $row) {
                if ($row['status'] === 'ok') {
                    $nOk++;
                } elseif ($row['status'] === 'fail') {
                    $nFail++;
                } else {
                    $nSkip++;
                }
            }
            $g['status'] = ($nOk > 0 && $nFail === 0) ? 'ok'
                : ($nOk > 0 ? 'part' : ($nFail > 0 ? 'fail' : 'skip'));
            $out[] = $g;
            if (count($out) >= max(1, min(200, $limit))) {
                break;
            }
        }
        return $out;
    } catch (PDOException $e) {
        return [];
    }
}

/** 列存在性：push_sent.channel 是 v121 才加的，老库要能降级运行 */
function lb_column_exists(PDO $pdo, string $table, string $col): bool
{
    if (preg_match('/^[A-Za-z_][A-Za-z0-9_]*$/', $table) !== 1) {
        return false;
    }
    try {
        if ($pdo->getAttribute(PDO::ATTR_DRIVER_NAME) === 'sqlite') {
            foreach ($pdo->query('PRAGMA table_info(' . $table . ')')->fetchAll() as $c) {
                if (($c['name'] ?? '') === $col) {
                    return true;
                }
            }
            return false;
        }
        /* 同上：SHOW 不能用参数绑定 */
        $safeCol = preg_replace('/[^A-Za-z0-9_]/', '', $col);
        return $pdo->query("SHOW COLUMNS FROM " . $table . " LIKE '" . $safeCol . "'")->fetchAll() !== [];
    } catch (PDOException $e) {
        return false;
    }
}

/* ===== 通知通道矩阵（v122）=====
   哪些事件类型走哪些通道。存在 app_settings 的 notify_prefs_<uid> 里——
   键值表本来就有，用户级偏好先放这儿，**不用再加迁移**。
   量大了（比如以后要按用户查、要审计）再拆独立表。 */

function lb_notify_kinds(): array
{
    return [
        'med' => '用药提醒',
        'task' => '待办到点',
        'habit' => '习惯提醒',
        'countdown' => '倒数日',
        'notice' => '自定义提醒',
        'debt' => '还款提醒',
        'report' => '每日小结',
    ];
}

function lb_notify_channels(): array
{
    return ['wecom' => '企业微信', 'mail' => '邮件'];
}

/** 默认：习惯与每日小结只走企业微信——它们每天好几条，发邮件太吵 */
function lb_notify_defaults(): array
{
    $out = [];
    foreach (array_keys(lb_notify_kinds()) as $kind) {
        $out[$kind] = ['wecom' => true, 'mail' => true];
    }
    $out['habit'] = ['wecom' => true, 'mail' => false];
    $out['report'] = ['wecom' => true, 'mail' => false];
    return $out;
}

/* ===== 通知板块矩阵（v211，方案 B）=====
   11 个板块 × 3 个渠道。浏览器只是数据列（服务端不发送），不进 lb_notify_channels()。
   模块类五板块（med/water/move/breathe/quit）**不存 on**：启用真源是
   state.modules.<key>.on / state.modulePrefs.meds.on（前端 isModuleOn、服务端 $modOn）。
   老数据是 7 类扁平结构（med/task/habit/…）：读取时原地迁移，habit 的渠道继承给
   water/move/breathe，保证升级后「该发的照发」。 */

function lb_notify_boards(): array
{
    return [
        'med' => ['channels' => ['wecom' => true, 'mail' => true, 'browser' => true]],
        'water' => ['channels' => ['wecom' => true, 'mail' => false, 'browser' => false]],
        /* v216：instances = 每个运动实例自己的通知设置（运动弹窗写入）。
           结构：{<sportId>: {on: bool, channels: {wecom,mail,browser}}}；没有实例配置时回落板块。 */
        'move' => ['channels' => ['wecom' => true, 'mail' => false, 'browser' => false], 'instances' => []],
        'breathe' => ['channels' => ['wecom' => true, 'mail' => false, 'browser' => false]],
        'quit' => ['channels' => ['wecom' => false, 'mail' => false, 'browser' => false]],
        'task' => ['on' => true, 'channels' => ['wecom' => true, 'mail' => true, 'browser' => true]],
        'habit' => ['on' => true, 'channels' => ['wecom' => true, 'mail' => false, 'browser' => true]],
        'notice' => ['on' => true, 'channels' => ['wecom' => true, 'mail' => true, 'browser' => true]],
        'countdown' => ['on' => true, 'channels' => ['wecom' => true, 'mail' => true, 'browser' => true]],
        /* debt 的「默认关」由 money.notify.on 控制；板块 on 保持 true，避免升级后
           用户已经打开还款提醒却因为板块默认关而收不到。 */
        'debt' => ['on' => true, 'channels' => ['wecom' => true, 'mail' => true, 'browser' => false]],
        'report' => ['on' => true, 'channels' => ['wecom' => true, 'mail' => false, 'browser' => true]],
    ];
}

/** 模块类板块：不存 on、也不接受 on 入参 */
function lb_notify_board_is_module(string $bid): bool
{
    return in_array($bid, ['med', 'water', 'move', 'breathe', 'quit'], true);
}

/** 读 11 板块矩阵；旧扁平结构在这里原地迁移（不写库，保存时自然升级） */
function lb_notify_boards_load(PDO $pdo, int $uid): array
{
    $out = lb_notify_boards();
    $raw = '';
    try {
        $st = $pdo->prepare('SELECT v FROM app_settings WHERE k = ? LIMIT 1');
        $st->execute(['notify_prefs_' . $uid]);
        $raw = (string)$st->fetchColumn();
    } catch (PDOException $e) {
        return $out;
    }
    if ($raw === '') {
        return $out;
    }
    $j = json_decode($raw, true);
    if (!is_array($j)) {
        return $out;
    }

    if (isset($j['boards']) && is_array($j['boards'])) {
        foreach ($out as $bid => $row) {
            $src = isset($j['boards'][$bid]) && is_array($j['boards'][$bid]) ? $j['boards'][$bid] : null;
            if (!is_array($src)) {
                continue;
            }
            $chIn = isset($src['channels']) && is_array($src['channels']) ? $src['channels'] : [];
            foreach ($row['channels'] as $ch => $def) {
                if (array_key_exists($ch, $chIn)) {
                    $out[$bid]['channels'][$ch] = (bool)$chIn[$ch];
                }
            }
            if (!lb_notify_board_is_module($bid) && array_key_exists('on', $src)) {
                $out[$bid]['on'] = (bool)$src['on'];
            }
            if ($bid === 'move') {
                $out['move']['instances'] = lb_notify_instances_norm(isset($src['instances']) && is_array($src['instances']) ? $src['instances'] : []);
            }
        }
        return $out;
    }

    /* 旧扁平结构：键就是板块 id。旧矩阵里 habit 同时管着喝水/运动/478，
       迁移时把它的两个服务端渠道继承过去，否则升级后这三类的邮件行为会变。 */
    foreach (['med', 'task', 'habit', 'notice', 'countdown', 'debt', 'report'] as $bid) {
        if (!isset($j[$bid]) || !is_array($j[$bid])) {
            continue;
        }
        foreach (['wecom', 'mail'] as $ch) {
            if (array_key_exists($ch, $j[$bid])) {
                $out[$bid]['channels'][$ch] = (bool)$j[$bid][$ch];
            }
        }
    }
    foreach (['water', 'move', 'breathe'] as $bid) {
        $out[$bid]['channels']['wecom'] = $out['habit']['channels']['wecom'];
        $out[$bid]['channels']['mail'] = $out['habit']['channels']['mail'];
    }
    return $out;
}

/** 把 11 板块投影回旧 7 类扁平结构（旧前端 / 旧调用方继续可用） */
function lb_notify_prefs_flat(array $boards): array
{
    $out = [];
    /* 顺序与 lb_notify_kinds() 对齐：旧调用方可能用 === 比较整个矩阵 */
    foreach (['med', 'task', 'habit', 'countdown', 'notice', 'debt', 'report'] as $bid) {
        $row = isset($boards[$bid]) && is_array($boards[$bid]) ? $boards[$bid] : [];
        $ch = isset($row['channels']) && is_array($row['channels']) ? $row['channels'] : [];
        $out[$bid] = ['wecom' => !empty($ch['wecom']), 'mail' => !empty($ch['mail'])];
    }
    return $out;
}

/** 存 11 板块矩阵（入库格式 {"boards":{...}}，方便以后加字段） */
function lb_notify_boards_save(PDO $pdo, int $uid, array $in): array
{
    /* v216 起基于已存值合并：入参里没出现的板块/字段一律保持不变。
       模块页（喝水/478/运动）只提交自己那一个板块，绝不能把路由页其他板块冲回默认。 */
    $boards = lb_notify_boards_load($pdo, $uid);
    $srcBoards = isset($in['boards']) && is_array($in['boards']) ? $in['boards'] : $in;

    if (isset($in['boards']) && is_array($in['boards'])) {
        foreach ($boards as $bid => $row) {
            $src = isset($srcBoards[$bid]) && is_array($srcBoards[$bid]) ? $srcBoards[$bid] : null;
            if (!is_array($src)) {
                continue;
            }
            $chIn = isset($src['channels']) && is_array($src['channels']) ? $src['channels'] : [];
            foreach ($row['channels'] as $ch => $def) {
                if (array_key_exists($ch, $chIn)) {
                    $boards[$bid]['channels'][$ch] = !empty($chIn[$ch]);
                }
            }
            if (!lb_notify_board_is_module($bid) && array_key_exists('on', $src)) {
                $boards[$bid]['on'] = !empty($src['on']);
            }
            if ($bid === 'move' && isset($src['instances']) && is_array($src['instances'])) {
                foreach (lb_notify_instances_norm($src['instances']) as $sid => $irow) {
                    $boards['move']['instances'][$sid] = $irow;
                }
            }
        }
    } else {
        /* 旧扁平入参：只认 7 类；habit 同步到 water/move/breathe */
        foreach (['med', 'task', 'habit', 'notice', 'countdown', 'debt', 'report'] as $bid) {
            if (!isset($in[$bid]) || !is_array($in[$bid])) {
                continue;
            }
            foreach (['wecom', 'mail'] as $ch) {
                if (array_key_exists($ch, $in[$bid])) {
                    $boards[$bid]['channels'][$ch] = !empty($in[$bid][$ch]);
                }
            }
        }
        foreach (['water', 'move', 'breathe'] as $bid) {
            $boards[$bid]['channels']['wecom'] = $boards['habit']['channels']['wecom'];
            $boards[$bid]['channels']['mail'] = $boards['habit']['channels']['mail'];
        }
    }

    $sql = $pdo->getAttribute(PDO::ATTR_DRIVER_NAME) === 'sqlite'
        ? 'INSERT INTO app_settings (k, v) VALUES (?, ?) ON CONFLICT(k) DO UPDATE SET v = excluded.v'
        : 'INSERT INTO app_settings (k, v) VALUES (?, ?) ON DUPLICATE KEY UPDATE v = VALUES(v)';
    try {
        $pdo->prepare($sql)->execute([
            'notify_prefs_' . $uid,
            json_encode(['boards' => $boards], JSON_UNESCAPED_UNICODE),
        ]);
    } catch (PDOException $e) {
        return ['ok' => false, 'error' => '保存失败：' . $e->getMessage()];
    }
    return ['ok' => true, 'boards' => $boards];
}

/** 读矩阵。没配过就返回默认值（不能返回全关，否则老用户升级后一条都不发） */
function lb_notify_prefs_load(PDO $pdo, int $uid): array
{
    /* 兼容层：返回旧 7 类扁平结构，内部读 11 板块。
       旧前端（v210 配置页矩阵）和旧调用方不用改一行。 */
    return lb_notify_prefs_flat(lb_notify_boards_load($pdo, $uid));
}

function lb_notify_prefs_save(PDO $pdo, int $uid, array $in): array
{
    /* 同时接受旧扁平（prefs）与新结构（boards）；保存后两种视图都返回。
       落库永远是 {"boards":{...}}，下次读取走新结构。 */
    $res = lb_notify_boards_save($pdo, $uid, $in);
    if (empty($res['ok'])) {
        return ['ok' => false, 'error' => (string)($res['error'] ?? '保存失败')];
    }
    $boards = $res['boards'];
    return ['ok' => true, 'prefs' => lb_notify_prefs_flat($boards), 'boards' => $boards];
}

/* ===== 免打扰时间段（v124 起为布尔，v211 扩成 {on,start,end}）=====
   静默**默认关**：绝大多数提醒的时间是用户自己设的，系统替他屏蔽就是违背意图。
   只有用户主动打开，才在这段时间停止推送（跳过，不补发——补发会让
   早上的第一条推送挤满昨晚的内容）。开始晚于结束即跨夜。 */

function lb_notify_quiet_defaults(): array
{
    return ['on' => false, 'start' => '23:00', 'end' => '07:00'];
}

/** 读完整配置；旧的 '1' / '0' 照样能读 */
function lb_notify_quiet_cfg(PDO $pdo, int $uid): array
{
    $out = lb_notify_quiet_defaults();
    try {
        $st = $pdo->prepare('SELECT v FROM app_settings WHERE k = ? LIMIT 1');
        $st->execute(['notify_quiet_' . $uid]);
        $raw = (string)$st->fetchColumn();
    } catch (PDOException $e) {
        return $out;
    }
    if ($raw === '') {
        return $out;
    }
    if ($raw === '1') {
        $out['on'] = true;
        return $out;
    }
    if ($raw === '0') {
        return $out;
    }
    $j = json_decode($raw, true);
    if (!is_array($j)) {
        return $out;
    }
    $out['on'] = !empty($j['on']);
    foreach (['start', 'end'] as $k) {
        $v = (string)($j[$k] ?? '');
        /* 非法值不覆盖默认，脏数据不能让调度挂掉 */
        if (preg_match('/^([01]\d|2[0-3]):[0-5]\d$/', $v) === 1) {
            $out[$k] = $v;
        }
    }
    return $out;
}

/** 旧调用方继续可用（只关心开关） */
function lb_notify_quiet_load(PDO $pdo, int $uid): bool
{
    return lb_notify_quiet_cfg($pdo, $uid)['on'];
}

/** 跨夜判定：start > end 时 23:00–23:59 与 00:00–06:59 都算夜里；起止相同视为不生效 */
function lb_notify_in_quiet(string $hm, string $start = '23:00', string $end = '07:00'): bool
{
    if ($start === '' || $end === '' || $start === $end) {
        return false;
    }
    if ($start < $end) {
        return $hm >= $start && $hm < $end;
    }
    return $hm >= $start || $hm < $end;
}

/** 接受布尔（旧）或 {on,start,end}（新） */
function lb_notify_quiet_save(PDO $pdo, int $uid, $in): void
{
    $cfg = lb_notify_quiet_defaults();
    if (is_array($in)) {
        $cfg['on'] = !empty($in['on']);
        foreach (['start', 'end'] as $k) {
            $v = (string)($in[$k] ?? '');
            if (preg_match('/^([01]\d|2[0-3]):[0-5]\d$/', $v) === 1) {
                $cfg[$k] = $v;
            }
        }
    } else {
        $cfg['on'] = (bool)$in;
    }
    $sql = $pdo->getAttribute(PDO::ATTR_DRIVER_NAME) === 'sqlite'
        ? 'INSERT INTO app_settings (k, v) VALUES (?, ?) ON CONFLICT(k) DO UPDATE SET v = excluded.v'
        : 'INSERT INTO app_settings (k, v) VALUES (?, ?) ON DUPLICATE KEY UPDATE v = VALUES(v)';
    $pdo->prepare($sql)->execute(['notify_quiet_' . $uid, json_encode($cfg, JSON_UNESCAPED_UNICODE)]);
}

/* ===== 全局通知总闸（v212）=====
   用户级一键暂停：关掉后所有板块、所有渠道都不发送；不改动板块配置本身。
   默认开——没配过不能变成「一条都不发」。 */
function lb_notify_global_load(PDO $pdo, int $uid): bool
{
    try {
        $st = $pdo->prepare('SELECT v FROM app_settings WHERE k = ? LIMIT 1');
        $st->execute(['notify_global_' . $uid]);
        $raw = (string)$st->fetchColumn();
    } catch (PDOException $e) {
        return true;
    }
    return $raw !== '0';
}

function lb_notify_global_save(PDO $pdo, int $uid, $on): void
{
    $sql = $pdo->getAttribute(PDO::ATTR_DRIVER_NAME) === 'sqlite'
        ? 'INSERT INTO app_settings (k, v) VALUES (?, ?) ON CONFLICT(k) DO UPDATE SET v = excluded.v'
        : 'INSERT INTO app_settings (k, v) VALUES (?, ?) ON DUPLICATE KEY UPDATE v = VALUES(v)';
    $pdo->prepare($sql)->execute(['notify_global_' . $uid, $on ? '1' : '0']);
}

/** 每日小结三个时刻。空串 = 不发那一条；默认 08:20 / 12:30 / 20:00 */
function lb_notify_report_load(PDO $pdo, int $uid): array
{
    $out = ['morning' => '08:20', 'noon' => '12:30', 'evening' => '20:00'];
    try {
        $st = $pdo->prepare('SELECT v FROM app_settings WHERE k = ? LIMIT 1');
        $st->execute(['notify_report_' . $uid]);
        $raw = (string)$st->fetchColumn();
    } catch (PDOException $e) {
        return $out;
    }
    if ($raw === '') {
        return $out;
    }
    $j = json_decode($raw, true);
    if (!is_array($j)) {
        return $out;
    }
    foreach ($out as $k => $def) {
        if (!array_key_exists($k, $j)) {
            continue;
        }
        $v = (string)$j[$k];
        /* 只接受 HH:MM 或空串，别的值一律回退默认——脏数据不能让调度挂掉 */
        if ($v === '' || preg_match('/^([01]\d|2[0-3]):[0-5]\d$/', $v) === 1) {
            $out[$k] = $v;
        }
    }
    return $out;
}

function lb_notify_report_save(PDO $pdo, int $uid, array $in): array
{
    $cur = lb_notify_report_load($pdo, $uid);
    $out = [];
    foreach ($cur as $k => $def) {
        $v = isset($in[$k]) ? trim((string)$in[$k]) : $cur[$k];
        if ($v !== '' && preg_match('/^([01]\d|2[0-3]):[0-5]\d$/', $v) !== 1) {
            return ['ok' => false, 'error' => '时间格式应该是 HH:MM，或者留空表示不发'];
        }
        $out[$k] = $v;
    }
    $sql = $pdo->getAttribute(PDO::ATTR_DRIVER_NAME) === 'sqlite'
        ? 'INSERT INTO app_settings (k, v) VALUES (?, ?) ON CONFLICT(k) DO UPDATE SET v = excluded.v'
        : 'INSERT INTO app_settings (k, v) VALUES (?, ?) ON DUPLICATE KEY UPDATE v = VALUES(v)';
    try {
        $pdo->prepare($sql)->execute(['notify_report_' . $uid, json_encode($out, JSON_UNESCAPED_UNICODE)]);
    } catch (PDOException $e) {
        return ['ok' => false, 'error' => '保存失败：' . $e->getMessage()];
    }
    return ['ok' => true, 'report' => $out];
}

/* ===== 文案模板（v211）=====
   存 app_settings 的 notify_tpl_<uid>，结构：
     { "scenes": { "med": {"title":"…","body":"…","browser":"…"}, … },
       "mail": {"color":"blue","footer":"明序 · 个人生活提醒"} }
   场景键 = source（med/task/habit/water/move/breathe/report/notice/countdown/debt/test），
   渲染时 source 找不到再回退 kind。企微/纯文本不转义，转义只在邮件 HTML 分支做。 */

function lb_notify_tpl_scenes(): array
{
    return ['med', 'task', 'habit', 'water', 'move', 'breathe', 'report', 'notice', 'countdown', 'debt', 'test'];
}

/** 限长截断：优先按字符，没 mbstring 时按字节兜底（不依赖 mbstring 是项目约定） */
function lb_notify_clip(string $s, int $limit): string
{
    if (function_exists('mb_substr')) {
        return mb_substr($s, 0, $limit, 'UTF-8');
    }
    return lb_push_clip($s, $limit * 4);
}

function lb_notify_tpl_defaults(): array
{
    $scenes = [];
    foreach (lb_notify_tpl_scenes() as $id) {
        $title = '{标题}';
        if ($id === 'med') {
            $title = '该吃药了';
        } elseif ($id === 'task') {
            $title = '该做这件事了';
        }
        $scenes[$id] = ['title' => $title, 'body' => '{正文}', 'browser' => '{浏览器文案}'];
    }
    return [
        'scenes' => $scenes,
        'mail' => ['color' => 'blue', 'footer' => '明序 · 个人生活提醒', 'mode' => 'html'],
    ];
}

/** 只接受白名单场景与限长字符串；脏值回退默认，不让渲染层拿到奇怪结构 */
function lb_notify_tpl_load(PDO $pdo, int $uid): array
{
    $out = lb_notify_tpl_defaults();
    try {
        $st = $pdo->prepare('SELECT v FROM app_settings WHERE k = ? LIMIT 1');
        $st->execute(['notify_tpl_' . $uid]);
        $raw = (string)$st->fetchColumn();
    } catch (PDOException $e) {
        return $out;
    }
    if ($raw === '') {
        return $out;
    }
    $j = json_decode($raw, true);
    if (!is_array($j)) {
        return $out;
    }
    $sc = isset($j['scenes']) && is_array($j['scenes']) ? $j['scenes'] : [];
    foreach ($out['scenes'] as $id => $row) {
        if (!isset($sc[$id]) || !is_array($sc[$id])) {
            continue;
        }
        foreach (['title', 'body', 'browser'] as $k) {
            if (array_key_exists($k, $sc[$id])) {
                $v = (string)$sc[$id][$k];
                $out['scenes'][$id][$k] = lb_notify_clip($v, 200);
            }
        }
    }
    $mail = isset($j['mail']) && is_array($j['mail']) ? $j['mail'] : [];
    if (isset($mail['color']) && preg_match('/^[a-z]{1,16}$/', (string)$mail['color']) === 1) {
        $out['mail']['color'] = (string)$mail['color'];
    }
    if (isset($mail['footer'])) {
        $out['mail']['footer'] = lb_notify_clip((string)$mail['footer'], 60);
    }
    if (isset($mail['mode']) && in_array((string)$mail['mode'], ['plain', 'html'], true)) {
        $out['mail']['mode'] = (string)$mail['mode'];
    }
    return $out;
}

function lb_notify_tpl_save(PDO $pdo, int $uid, array $in): array
{
    /* 基于已存值：只传部分字段时不会把其他场景/邮件设置重置成默认 */
    $cur = lb_notify_tpl_load($pdo, $uid);
    $sc = isset($in['scenes']) && is_array($in['scenes']) ? $in['scenes'] : [];
    foreach ($cur['scenes'] as $id => $row) {
        if (!isset($sc[$id]) || !is_array($sc[$id])) {
            continue;
        }
        foreach (['title', 'body', 'browser'] as $k) {
            if (array_key_exists($k, $sc[$id])) {
                $cur['scenes'][$id][$k] = lb_notify_clip((string)$sc[$id][$k], 200);
            }
        }
    }
    $mail = isset($in['mail']) && is_array($in['mail']) ? $in['mail'] : [];
    if (isset($mail['color']) && preg_match('/^[a-z]{1,16}$/', (string)$mail['color']) === 1) {
        $cur['mail']['color'] = (string)$mail['color'];
    }
    if (isset($mail['footer'])) {
        $cur['mail']['footer'] = lb_notify_clip((string)$mail['footer'], 60);
    }
    if (isset($mail['mode']) && in_array((string)$mail['mode'], ['plain', 'html'], true)) {
        $cur['mail']['mode'] = (string)$mail['mode'];
    }
    $sql = $pdo->getAttribute(PDO::ATTR_DRIVER_NAME) === 'sqlite'
        ? 'INSERT INTO app_settings (k, v) VALUES (?, ?) ON CONFLICT(k) DO UPDATE SET v = excluded.v'
        : 'INSERT INTO app_settings (k, v) VALUES (?, ?) ON DUPLICATE KEY UPDATE v = VALUES(v)';
    try {
        $pdo->prepare($sql)->execute([
            'notify_tpl_' . $uid,
            json_encode($cur, JSON_UNESCAPED_UNICODE),
        ]);
    } catch (PDOException $e) {
        return ['ok' => false, 'error' => '保存失败：' . $e->getMessage()];
    }
    return ['ok' => true, 'templates' => $cur];
}

/** source 的中文名（模板变量 {场景}/{来源}/{功能} 共用） */
function lb_notify_source_cn(): array
{
    return [
        'med' => '用药', 'task' => '待办', 'habit' => '习惯', 'water' => '喝水',
        'move' => '运动', 'breathe' => '478呼吸', 'report' => '每日小结',
        'notice' => '自定义提醒', 'countdown' => '倒数日', 'debt' => '还款',
        'test' => '测试消息',
    ];
}

/** 事件 → 板块 id。habit 三兄弟靠 source 区分，其余按 kind。 */
function lb_notify_board_of(array $ev): string
{
    $src = (string)($ev['source'] ?? '');
    if (in_array($src, ['water', 'move', 'breathe', 'quit'], true)) {
        return $src;
    }
    $kind = (string)($ev['kind'] ?? '');
    $map = [
        'med' => 'med', 'task' => 'task', 'habit' => 'habit', 'notice' => 'notice',
        'countdown' => 'countdown', 'debt' => 'debt', 'report' => 'report',
    ];
    return $map[$kind] ?? 'habit';
}

/** 清洗 move 板块的实例设置：id 键任意（sportId），值只认 on + 三渠道布尔 */
function lb_notify_instances_norm(array $in): array
{
    $out = [];
    foreach ($in as $sid => $row) {
        $sid = (string)$sid;
        if ($sid === '' || !is_array($row)) {
            continue;
        }
        $item = ['on' => !isset($row['on']) || !empty($row['on'])];
        $ch = [];
        foreach (['wecom', 'mail', 'browser'] as $chName) {
            $ch[$chName] = !isset($row['channels'][$chName]) || !empty($row['channels'][$chName]);
        }
        $item['channels'] = $ch;
        $out[$sid] = $item;
    }
    return $out;
}

/** 这条事件的生效配置：move 板块且事件带 sport 且该运动存过实例设置 → 用实例；否则回落板块。
    返回 {on, channels, level}；on=false 表示这条不推（也不补）。 */
function lb_notify_effective_row(array $boards, array $item): array
{
    $bid = lb_notify_board_of($item);
    $row = isset($boards[$bid]) && is_array($boards[$bid]) ? $boards[$bid] : [];
    $ch = is_array($row['channels'] ?? null) ? $row['channels'] : [];
    $on = !isset($row['on']) || !empty($row['on']);
    $level = 'board';
    if ($bid === 'move' && !empty($item['sport'])
        && isset($row['instances'][$item['sport']])
        && is_array($row['instances'][$item['sport']])) {
        $inst = $row['instances'][$item['sport']];
        $on = !isset($inst['on']) || !empty($inst['on']);
        $ch = is_array($inst['channels'] ?? null) ? $inst['channels'] : $ch;
        $level = 'instance';
    }
    /* 小习惯 2.0：事件自带习惯级渠道（notifyPlan.channels）→ 与板块渠道取交集，
       交集空则全关。板块是账号级总闸，习惯级是单习惯微调，两者都开才发。 */
    if ($bid === 'habit' && isset($item['channels']) && is_array($item['channels']) && $item['channels']) {
        foreach (['wecom', 'mail', 'browser'] as $chName) {
            if (!empty($ch[$chName]) && in_array($chName, array_map('strval', $item['channels']), true)) {
                continue;
            }
            $ch[$chName] = false;
        }
        $level = 'habit';
    }
    return ['on' => $on, 'channels' => $ch, 'level' => $level, 'board' => $bid];
}

/** 渲染成最终发送文本（标题 + 换行 + 正文），未知占位符原样保留 */
function lb_notify_text_render(array $tpl, array $ev): string
{
    $src = (string)($ev['source'] ?? '');
    $kind = (string)($ev['kind'] ?? '');
    $key = $src !== '' ? $src : $kind;
    $scene = isset($tpl['scenes'][$key]) && is_array($tpl['scenes'][$key]) ? $tpl['scenes'][$key] : null;
    if (!is_array($scene) && $kind !== '' && isset($tpl['scenes'][$kind]) && is_array($tpl['scenes'][$kind])) {
        $scene = $tpl['scenes'][$kind];
    }
    if (!is_array($scene)) {
        $scene = ['title' => '{标题}', 'body' => '{正文}'];
    }
    $cn = lb_notify_source_cn();
    $label = $cn[$src] ?? (lb_notify_kinds()[$kind] ?? $kind);
    $vars = [
        '{标题}' => (string)($ev['title'] ?? ''),
        '{正文}' => (string)($ev['body'] ?? ''),
        '{时间}' => (string)($ev['time'] ?? ''),
        '{类目}' => (string)(lb_notify_kinds()[$kind] ?? $kind),
        '{场景}' => $label,
        '{来源}' => $label,
        '{功能}' => $label,
        '{优先级}' => (string)($ev['priority'] ?? ''),
        '{浏览器文案}' => (string)($ev['browser'] ?? ''),
    ];
    $title = trim(strtr((string)($scene['title'] ?? '{标题}'), $vars));
    $body = trim(strtr((string)($scene['body'] ?? '{正文}'), $vars));
    if ($body === '') {
        return $title;
    }
    return $title === '' ? $body : $title . "\n" . $body;
}

/** 把旧的企业微信发送函数包成统一签名 ($row, $text, &$why) */
function lb_push_wecom_adapter(callable $fn): callable
{
    return function (array $row, string $text, ?string &$why) use ($fn) {
        $why = '';
        return (bool)$fn((string)($row['push_webhook'] ?? ''), $text, $why);
    };
}

/** 邮件通道：把「标题 + 正文」拆成主题与正文，收件人固定为账号邮箱。
    v211 起附带 HTML 卡片（纯文本 part 仍在，客户端自己挑）；模板取不到时退回纯文本。 */
function lb_mail_channel_sender(PDO $pdo, bool $card = true): callable
{
    return function (array $row, string $text, ?string &$why) use ($pdo, $card) {
        $lines = preg_split('/\r?\n/', trim($text), 2);
        $subject = trim((string)($lines[0] ?? ''));
        $body = (string)($lines[1] ?? '');
        if ($subject === '') {
            $subject = '提醒';
        }
        $html = '';
        if ($card && function_exists('lb_notify_tpl_load') && function_exists('lb_notify_mail_card')) {
            $tpl = lb_notify_tpl_load($pdo, (int)$row['id']);
            $mode = (string)($tpl['mail']['mode'] ?? 'html');
            $html = $mode === 'plain' ? '' : lb_notify_mail_card(
                $subject,
                $body,
                (string)($tpl['mail']['footer'] ?? ''),
                (string)($tpl['mail']['color'] ?? 'blue')
            );
        }
        return lb_mail_send_to_user($pdo, (int)$row['id'], '【明序】' . $subject, $body, $why, $html);
    };
}

/**
 * 同一时刻的多种药合并成一条（v123）。
 *
 * 8:00 吃六种药，发六条既吵又容易看漏——而且六条挤在通知栏里，
 * 用户通常只点开第一条。合并成「该吃药了（6 种）」+ 列表更好读。
 * 只合并 kind=med：任务/习惯本来就不常撞在同一分钟，合并反而会让标题变抽象。
 */
function lb_notify_merge_med(array $due): array
{
    $byTime = [];
    $out = [];
    $pos = 0;
    foreach ($due as $item) {
        /* 记原始位置：合并会打乱输出顺序，而顺序决定推送文案的先后
           （20:00 的晚报必须排在药之后），所以合并完要按原位重排 */
        $item['_pos'] = $pos++;
        $id = (string)($item['id'] ?? '');
        if (($item['kind'] ?? '') === 'med' && $id !== '' && strpos($id, 'batch_') !== 0) {
            $byTime[(string)$item['time']][] = $item;
        } else {
            $out[] = $item;
        }
    }
    foreach ($byTime as $time => $group) {
        if (count($group) === 1) {
            $out[] = $group[0];
            continue;
        }
        $lines = [];
        foreach ($group as $g) {
            $lines[] = '· ' . $g['body'];
        }
        $out[] = [
            'kind' => 'med',
            'id' => 'batch_' . $time,
            'time' => (string)$time,
            'title' => '该吃药了（' . count($group) . ' 种）',
            'body' => implode("\n", $lines),
            'merged' => count($group),
            /* v211：合并后仍要带来源/优先级，否则模板渲染成空白 */
            'source' => (string)($group[0]['source'] ?? 'med'),
            'priority' => (string)($group[0]['priority'] ?? '紧急'),
            '_pos' => $group[0]['_pos'],
        ];
    }
    usort($out, function ($a, $b) {
        return ($a['_pos'] ?? 0) <=> ($b['_pos'] ?? 0);
    });
    foreach ($out as $i => $item) {
        unset($out[$i]['_pos']);
    }
    return $out;
}

/**
 * 每分钟调度一轮提醒。
 *
 * $senders 两种形态都支持：
 *   - callable                        单通道（企业微信），旧调用方与旧测试不受影响
 *   - [['channel'=>'wecom','fn'=>fn], ['channel'=>'mail','fn'=>fn], ...]
 *     fn 统一签名 ($row, $text, &$why)，$row 带 id / push_webhook。
 *
 * 去重：push_sent 唯一键 (user_id, slot_key, channel)。channel 列没迁移时
 * 退回 (user_id, slot_key)，此时多通道会互相顶掉——push_tick 会提示跑迁移。
 */
function lb_push_tick_run(
    PDO $pdo,
    string $date,
    string $hm,
    $senders,
    bool $dry = false,
    int $grace = 3
): array {
    $out = ['sent' => 0, 'skipped' => 0, 'failed' => 0, 'items' => [], 'channels' => 0];

    if (is_callable($senders)) {
        $senders = [['channel' => 'wecom', 'fn' => lb_push_wecom_adapter($senders)]];
    }
    if (!is_array($senders) || !$senders) {
        return $out;
    }
    $out['channels'] = count($senders);

    /* 谁在等提醒：配了企业微信的，或者开了邮件提醒的（后者要表存在才查） */
    $hasMailTable = lb_table_exists($pdo, 'user_mail_config');
    $where = "(u.push_enabled = 1 AND u.push_webhook IS NOT NULL AND u.push_webhook <> '')";
    $mailCol = '0 AS mail_on';
    if ($hasMailTable) {
        $where = '(' . $where
            . ' OR EXISTS (SELECT 1 FROM user_mail_config m WHERE m.user_id = u.id AND m.enabled = 1))';
        $mailCol = '(SELECT 1 FROM user_mail_config m WHERE m.user_id = u.id AND m.enabled = 1) AS mail_on';
    }

    $rows = $pdo->query(
        "SELECT u.id, u.push_webhook, " . $mailCol . ", b.data
           FROM users u
           INNER JOIN boards b ON b.user_id = u.id
          WHERE u.status = 'active'
            AND " . $where
    )->fetchAll();

    if (!$rows) {
        return $out;
    }

    $ins = null;
    $del = null;
    $hasContent = false;
    $hasChannel = false;
    if (!$dry) {
        /* SQLite 不认 MySQL 的 INSERT IGNORE，但它是我们唯一能在本地跑起来的
           真实数据库——去重逻辑只有在真库上验过才算数，所以两种写法都留着。 */
        $verb = $pdo->getAttribute(PDO::ATTR_DRIVER_NAME) === 'sqlite'
            ? 'INSERT OR IGNORE' : 'INSERT IGNORE';
        $hasContent = lb_push_sent_has_content($pdo);
        $hasChannel = lb_column_exists($pdo, 'push_sent', 'channel');
        $cols = ['user_id', 'slot_key', 'kind', 'sent_at'];
        $ph = ['?', '?', '?', '?'];
        if ($hasContent) {
            $cols[] = 'content';
            $ph[] = '?';
        }
        if ($hasChannel) {
            $cols[] = 'channel';
            $ph[] = '?';
        }
        $ins = $pdo->prepare(
            $verb . ' INTO push_sent (' . implode(', ', $cols) . ') VALUES (' . implode(', ', $ph) . ')'
        );
        $del = $hasChannel
            ? $pdo->prepare('DELETE FROM push_sent WHERE user_id = ? AND slot_key = ? AND channel = ?')
            : $pdo->prepare('DELETE FROM push_sent WHERE user_id = ? AND slot_key = ?');
    }
    $stamp = $date . ' ' . $hm . ':00';

    foreach ($rows as $r) {
        $uid = (int)$r['id'];
        $hook = (string)($r['push_webhook'] ?? '');
        $mailOn = !empty($r['mail_on']);
        /* v212：全局总闸关掉就整段跳过（不改板块配置，重新打开立即恢复） */
        if (!lb_notify_global_load($pdo, $uid)) {
            $out['global_skipped'] = ($out['global_skipped'] ?? 0) + 1;
            continue;
        }
        /* 免打扰：v211 起时段可配（{on,start,end}），旧的布尔存储照样能读 */
        $quiet = lb_notify_quiet_cfg($pdo, $uid);
        if ($quiet['on'] && lb_notify_in_quiet($hm, $quiet['start'], $quiet['end'])) {
            $out['quiet_skipped'] = ($out['quiet_skipped'] ?? 0) + 1;
            continue;
        }
        $boards = lb_notify_boards_load($pdo, $uid);
        $tpl = lb_notify_tpl_load($pdo, $uid);
        $reportTimes = lb_notify_report_load($pdo, $uid);
        $state = json_decode((string)$r['data'], true);
        if (!is_array($state)) {
            continue;
        }
        /* 单条提醒（药/待办/习惯）+ 待办汇报（report），统一走 lb_schedule_due 判窗口 */
        $plan = array_merge(lb_schedule_day($state, $date), lb_schedule_reports($state, $date, $reportTimes), lb_schedule_notices($state, $date), lb_schedule_countdowns($state, $date), lb_schedule_debts($state, $date));
        $due = lb_schedule_due($plan, $hm, $grace);
        if (!$due) {
            continue;
        }
        $due = lb_notify_merge_med($due);

        foreach ($due as $item) {
            $key = $date . '|' . $item['kind'] . '|' . $item['id'] . '|' . $item['time'];
            /* 文案模板：source 优先、kind 兜底；模板没配过时长这样与原「标题\n正文」等价 */
            $text = lb_notify_text_render($tpl, $item);
            /* v216：生效配置 = 实例（运动弹窗存的）优先，回落板块矩阵 */
            $eff = lb_notify_effective_row($boards, $item);
            /* 板块/实例停用是 item 级判定：整条跳过，skip 日志只记一条 */
            if (!$eff['on']) {
                if ($eff['level'] === 'instance') {
                    $out['instance_skipped'] = ($out['instance_skipped'] ?? 0) + 1;
                    lb_push_log_add($pdo, $uid, $stamp, '', (string)$item['kind'], $key,
                        $text, 'skip', '该运动的通知已关闭', $eff['board']);
                } else {
                    lb_push_log_add($pdo, $uid, $stamp, '', (string)$item['kind'], $key,
                        $text, 'skip', '板块已停用', $eff['board']);
                }
                continue;
            }

            foreach ($senders as $ch) {
                $chan = (string)($ch['channel'] ?? 'wecom');
                /* 板块没勾这个渠道 = 用户不想走它，静默跳过、不记日志 */
                if (isset($eff['channels'][$chan]) && !$eff['channels'][$chan]) {
                    continue;
                }
                /* v223：渠道勾了但没配置 = 该发没发，记一条 fail（用户能在历史里看到原因）。
                   判定顺序不能反——先过滤「没勾」，再记「勾了但没配」。 */
                if ($chan === 'wecom' && $hook === '') {
                    lb_push_log_add($pdo, $uid, $stamp, $chan, (string)$item['kind'], $key,
                        $text, 'fail', '企业微信未配置：去「配置」页填机器人地址', $eff['board']);
                    continue;
                }
                if ($chan === 'mail' && !$mailOn) {
                    lb_push_log_add($pdo, $uid, $stamp, $chan, (string)$item['kind'], $key,
                        $text, 'fail', '邮件未开启：去「配置」页配置 SMTP 与授权码', $eff['board']);
                    continue;
                }

                $entry = ['user' => $uid, 'key' => $key, 'kind' => $item['kind'],
                          'time' => $item['time'], 'channel' => $chan, 'text' => $text, 'ok' => false];

                if ($dry) {
                    $entry['ok'] = true;
                    $out['items'][] = $entry;
                    $out['sent']++;
                    continue;
                }

                /* 先占位再看结果：唯一索引保证同一条（同通道）只可能插进去一次，
                   比「先查再插」在并发和延迟下都可靠 */
                try {
                    $vals = [$uid, $key, $item['kind'], $stamp];
                    if ($hasContent) {
                        $vals[] = $text;
                    }
                    if ($hasChannel) {
                        $vals[] = $chan;
                    }
                    $ins->execute($vals);
                } catch (PDOException $e) {
                    $out['failed']++;
                    $entry['why'] = '写发送记录失败：' . $e->getMessage();
                    $out['items'][] = $entry;
                    continue;
                }
                if ($ins->rowCount() < 1) {
                    $out['skipped']++;
                    continue;
                }

                $why = '';
                $ok = (bool)($ch['fn'])($r, $text, $why);
                if ($ok) {
                    $out['sent']++;
                    $entry['ok'] = true;
                    lb_push_log_add($pdo, $uid, $stamp, $chan, (string)$item['kind'], $key, $text, 'ok');
                } else {
                    $out['failed']++;
                    $entry['why'] = $why;
                    lb_push_log_add($pdo, $uid, $stamp, $chan, (string)$item['kind'], $key, $text, 'fail', $why, $eff['board']);
                    /* 发失败必须撤掉占位，否则这条永远不会再试，提醒就永久丢了 */
                    $del->execute($hasChannel ? [$uid, $key, $chan] : [$uid, $key]);
                }
                $out['items'][] = $entry;
            }
        }
    }

    /* 清理旧记录。失败也不影响本轮结果 */
    if (!$dry) {
        try {
            $pdo->prepare('DELETE FROM push_sent WHERE sent_at < ?')
                ->execute([date('Y-m-d H:i:s', strtotime($stamp . ' -7 days'))]);
            if (lb_push_log_ready($pdo)) {
                $pdo->prepare('DELETE FROM push_log WHERE at < ?')
                    ->execute([date('Y-m-d H:i:s', strtotime($stamp . ' -14 days'))]);
            }
        } catch (PDOException $e) {
            /* 忽略：清理失败不该让推送停摆 */
        }
    }

    return $out;
}
