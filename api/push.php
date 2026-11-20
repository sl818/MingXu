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

/** 把旧的企业微信发送函数包成统一签名 ($row, $text, &$why) */
function lb_push_wecom_adapter(callable $fn): callable
{
    return function (array $row, string $text, ?string &$why) use ($fn) {
        $why = '';
        return (bool)$fn((string)($row['push_webhook'] ?? ''), $text, $why);
    };
}

/** 邮件通道：把「标题 + 正文」拆成主题与正文，收件人固定为账号邮箱 */
function lb_mail_channel_sender(PDO $pdo): callable
{
    return function (array $row, string $text, ?string &$why) use ($pdo) {
        $lines = preg_split('/\r?\n/', trim($text), 2);
        $subject = trim((string)($lines[0] ?? ''));
        $body = (string)($lines[1] ?? '');
        if ($subject === '') {
            $subject = '提醒';
        }
        return lb_mail_send_to_user($pdo, (int)$row['id'], '【明序】' . $subject, $body, $why);
    };
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
        $state = json_decode((string)$r['data'], true);
        if (!is_array($state)) {
            continue;
        }
        /* 单条提醒（药/待办/习惯）+ 待办汇报（report），统一走 lb_schedule_due 判窗口 */
        $plan = array_merge(lb_schedule_day($state, $date), lb_schedule_reports($state, $date), lb_schedule_notices($state, $date), lb_schedule_countdowns($state, $date), lb_schedule_debts($state, $date));
        $due = lb_schedule_due($plan, $hm, $grace);
        if (!$due) {
            continue;
        }

        foreach ($due as $item) {
            $key = $date . '|' . $item['kind'] . '|' . $item['id'] . '|' . $item['time'];
            $text = $item['title'] . "\n" . $item['body'];

            foreach ($senders as $ch) {
                $chan = (string)($ch['channel'] ?? 'wecom');
                /* 通道没配就不发：省掉一次必然失败的调用，也免得占位后又被撤掉 */
                if ($chan === 'wecom' && $hook === '') {
                    continue;
                }
                if ($chan === 'mail' && !$mailOn) {
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
                } else {
                    $out['failed']++;
                    $entry['why'] = $why;
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
        } catch (PDOException $e) {
            /* 忽略：清理失败不该让推送停摆 */
        }
    }

    return $out;
}
