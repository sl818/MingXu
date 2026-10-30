<?php
declare(strict_types=1);

define('LIFEBOARD_API', true);

$lockFile = __DIR__ . '/install.lock';
$action = isset($_GET['action']) ? (string)$_GET['action'] : '';

/* 订阅地址做成单参数 ?ics=<token>：有些安卓日历把 URL 里的 & 当截断点，
   ?action=ics&token=... 会被切成 action=ics，token 直接丢掉，于是报「导入失败」。
   老的 ?action=ics&token= 仍然支持，已经加进日历的地址继续能用。 */
if ($action === '' && isset($_GET['ics'])) {
    $action = 'ics';
}

/* 安装状态：不依赖数据库和配置，未安装时前端据此处跳转安装向导 */
if ($action === 'status') {
    header('Content-Type: application/json; charset=utf-8');
    header('Cache-Control: no-store');
    header('X-Content-Type-Options: nosniff');
    echo json_encode(['ok' => true, 'installed' => is_file($lockFile)]);
    exit;
}

if (!is_file($lockFile)) {
    http_response_code(503);
    header('Content-Type: application/json; charset=utf-8');
    header('Cache-Control: no-store');
    echo json_encode(['ok' => false, 'error' => '系统尚未安装', 'code' => 'not_installed']);
    exit;
}

ini_set('display_errors', '0');
require __DIR__ . '/api/bootstrap.php';
require __DIR__ . '/api/backup.php';
require __DIR__ . '/api/ics.php';
/* push.php 内部已经 require_once 了 schedule.php；
   这里必须用 once，否则 schedule.php 被加载两次会「函数重复声明」直接 fatal */
require_once __DIR__ . '/api/push.php';

/* 订阅请求用不上会话：系统日历不带 Cookie，不需要登录态。
   而 session_start() 每次都会新建/锁定一个文件 —— 实测每个订阅请求都会在
   session 目录留下一个 0 字节的空文件，纯属白费 IO。 */
if ($action !== 'ics') {
    lb_session_start();
}

header('X-Frame-Options: DENY');
header('Referrer-Policy: same-origin');
header('X-Content-Type-Options: nosniff');

$method = isset($_SERVER['REQUEST_METHOD']) ? (string)$_SERVER['REQUEST_METHOD'] : 'GET';

/* 每天一份整站快照落到 backups/：数据库和文件分开存，一边出事另一边还能捞。
   内部自带 try/catch，任何异常都不会影响正常的读写请求。 */
lb_daily_backup();

/* 订阅地址。Host 只用来拼给自己看的链接，仍然过滤一遍字符，
   免得被伪造的 Host 头把奇怪内容带进页面 */
function lb_ics_url(string $token): string
{
    $host = isset($_SERVER['HTTP_HOST']) ? (string)$_SERVER['HTTP_HOST'] : '';
    if (!preg_match('/^[A-Za-z0-9.\-]+(:\d+)?$/', $host)) {
        $host = '';
    }
    $scheme = lb_is_https() ? 'https' : 'http';
    /* 末尾带 .ics：不少安卓日历（含小米）会按后缀判断这是不是一个日历源，
       没有后缀就直接报「无法添加」。这个后缀纯属给客户端看的，服务端会剥掉。 */
    return $scheme . '://' . $host . '/api.php?ics=' . $token . '.ics';
}

function lb_prune_revisions(PDO $pdo, int $uid, int $now): void
{
    try {
        $keep = $pdo->prepare(
            'DELETE FROM board_revisions
             WHERE user_id = ?
               AND id NOT IN (
                 SELECT id FROM (
                   SELECT id FROM board_revisions WHERE user_id = ? ORDER BY id DESC LIMIT 20
                 ) keep_rows
               )'
        );
        $keep->execute([$uid, $uid]);
        $old = $pdo->prepare('DELETE FROM board_revisions WHERE user_id = ? AND created_at < ?');
        $old->execute([$uid, $now - 30 * 86400000]);
    } catch (Throwable $e) {
        error_log('lifeboard revision prune: ' . $e->getMessage());
    }
}

function lb_snapshot_board(PDO $pdo, int $uid, string $data, int $rev, string $reason, int $now): void
{
    try {
        $ins = $pdo->prepare(
            'INSERT INTO board_revisions (user_id, rev, data, reason, created_at) VALUES (?, ?, ?, ?, ?)'
        );
        $ins->execute([$uid, $rev, $data, $reason, $now]);
        lb_prune_revisions($pdo, $uid, $now);
    } catch (Throwable $e) {
        // 历史表还没迁移时不阻塞正常保存；迁移完成后自动恢复快照。
        error_log('lifeboard revision insert: ' . $e->getMessage());
    }
}

try {
    switch ($action) {
        case 'me':
            if ($method !== 'GET') {
                lb_fail('请使用 GET', 405, 'method_not_allowed');
            }
            $user = lb_user();
            $settings = lb_settings();
            lb_json([
                'ok' => true,
                'user' => $user ? lb_public_user($user) : null,
                'csrf' => lb_csrf(),
                'registration_open' => $settings['registration_open'] === '1',
                'site_name' => $settings['site_name'] ?? '晚风Todo',
            ]);
            break;

        case 'login':
            lb_require_post();
            lb_require_csrf();

            $body = lb_body();
            $email = strtolower(trim((string)($body['email'] ?? '')));
            $password = (string)($body['password'] ?? '');

            if (!filter_var($email, FILTER_VALIDATE_EMAIL) || strlen($email) > 190
                || $password === '' || strlen($password) > 200) {
                lb_fail('邮箱或密码不正确', 401, 'bad_credentials');
            }

            lb_throttle_check($email);

            $st = lb_db()->prepare(
                'SELECT id, email, password_hash, display_name, is_admin, status, session_epoch, created_at, last_login_at '
                . 'FROM users WHERE email = ? LIMIT 1'
            );
            $st->execute([$email]);
            $user = $st->fetch();

            $hash = $user ? (string)$user['password_hash'] : LB_DUMMY_HASH;
            $verified = password_verify($password, $hash);

            if (!$user || !$verified) {
                lb_throttle_add($email);
                usleep(250000);
                lb_fail('邮箱或密码不正确', 401, 'bad_credentials');
            }
            if ($user['status'] !== 'active') {
                lb_fail('这个账号已被管理员停用', 403, 'account_disabled');
            }

            lb_throttle_clear($email);
            // 单设备登录：每次登录都把 session_epoch 推进一步，
            // 之前那台设备的会话下一次请求就会因 epoch 不匹配而失效（被踢下线）。
            $bump = lb_db()->prepare('UPDATE users SET session_epoch = session_epoch + 1 WHERE id = ?');
            $bump->execute([(int)$user['id']]);
            $user['session_epoch'] = (int)$user['session_epoch'] + 1;
            lb_session_login($user);
            $up = lb_db()->prepare('UPDATE users SET last_login_at = NOW() WHERE id = ?');
            $up->execute([(int)$user['id']]);
            $user['last_login_at'] = date('Y-m-d H:i:s');

            lb_json([
                'ok' => true,
                'user' => lb_public_user($user),
                'csrf' => $_SESSION['csrf'],
                'registration_open' => lb_setting('registration_open') === '1',
                'site_name' => lb_setting('site_name', '晚风Todo'),
            ]);
            break;

        case 'register':
            lb_require_post();
            lb_require_csrf();

            if (lb_setting('registration_open') !== '1') {
                lb_fail('管理员关闭了注册', 403, 'registration_closed');
            }
            lb_register_limit();

            $body = lb_body();
            $email = strtolower(trim((string)($body['email'] ?? '')));
            $password = (string)($body['password'] ?? '');
            $display = trim((string)($body['display_name'] ?? ''));
            $invite = strtoupper(trim((string)($body['invite'] ?? '')));
            $expected = strtoupper((string)lb_setting('invite_code', ''));

            if ($expected === '' || !hash_equals($expected, $invite)) {
                lb_fail('邀请码不正确', 403, 'invite_invalid');
            }
            if (!filter_var($email, FILTER_VALIDATE_EMAIL) || strlen($email) > 190) {
                lb_fail('请输入有效的邮箱地址', 400, 'bad_email');
            }
            if (lb_strlen($password) < 8 || strlen($password) > 200) {
                lb_fail('密码至少 8 位', 400, 'bad_password');
            }
            if (lb_strlen($display) > 40) {
                lb_fail('显示名称最多 40 个字符', 400, 'bad_display_name');
            }

            $pdo = lb_db();
            $st = $pdo->prepare('SELECT id FROM users WHERE email = ? LIMIT 1');
            $st->execute([$email]);
            if ($st->fetchColumn()) {
                lb_fail('这个邮箱已经注册过了', 409, 'email_exists');
            }

            try {
                $ins = $pdo->prepare(
                    'INSERT INTO users (email, password_hash, display_name, is_admin, status, session_epoch, created_at) '
                    . 'VALUES (?, ?, ?, 0, \'active\', 0, NOW())'
                );
                $ins->execute([$email, password_hash($password, PASSWORD_DEFAULT), $display]);
            } catch (PDOException $e) {
                if ((string)$e->getCode() === '23000') {
                    lb_fail('这个邮箱已经注册过了', 409, 'email_exists');
                }
                throw $e;
            }

            $user = lb_user_by_id((int)$pdo->lastInsertId());
            if (!$user) {
                lb_fail('注册失败，请重试', 500, 'server_error');
            }
            lb_session_login($user);
            $up = $pdo->prepare('UPDATE users SET last_login_at = NOW() WHERE id = ?');
            $up->execute([(int)$user['id']]);
            $user['last_login_at'] = date('Y-m-d H:i:s');

            lb_json([
                'ok' => true,
                'user' => lb_public_user($user),
                'csrf' => $_SESSION['csrf'],
                'registration_open' => true,
                'site_name' => lb_setting('site_name', '晚风Todo'),
            ]);
            break;

        case 'logout':
            lb_require_post();
            if (!lb_user()) {
                lb_fail('请先登录', 401, 'unauthenticated');
            }
            lb_require_csrf();
            lb_session_logout();
            lb_json(['ok' => true]);
            break;

        /* ---------- 日历订阅 ----------
           两条路由要分清楚：
           ics_status / ics_reset 需要登录，只给自己看链接；
           ics 必须免登录 —— 系统日历不会带 Cookie，只能靠 URL 里的令牌认人。 */
        case 'ics_status':
            if ($method !== 'GET') {
                lb_fail('请使用 GET', 405, 'method_not_allowed');
            }
            $user = lb_auth();
            $st = lb_db()->prepare('SELECT ics_token FROM users WHERE id = ? LIMIT 1');
            $st->execute([(int)$user['id']]);
            $token = (string)$st->fetchColumn();
            lb_json([
                'ok' => true,
                'url' => $token !== '' ? lb_ics_url($token) : null,
            ]);
            break;

        case 'ics_reset':
            lb_require_post();
            $user = lb_auth();
            lb_require_csrf();
            $token = bin2hex(random_bytes(32));
            $up = lb_db()->prepare('UPDATE users SET ics_token = ? WHERE id = ?');
            $up->execute([$token, (int)$user['id']]);
            lb_json(['ok' => true, 'url' => lb_ics_url($token)]);
            break;

        case 'ics':
            /* HEAD 也要放行：安卓上的日历客户端添加订阅前经常先发一个 HEAD 探测，
               只认 GET 会直接被判成「地址无效」——小米、华为自带的日历都有这个行为。 */
            if ($method !== 'GET' && $method !== 'HEAD') {
                lb_fail('请使用 GET', 405, 'method_not_allowed');
            }
            $token = '';
            if (isset($_GET['token'])) {
                $token = (string)$_GET['token'];
            } elseif (isset($_GET['ics'])) {
                $token = (string)$_GET['ics'];
            }
            /* 地址末尾的 .ics 只是给客户端看的，校验前剥掉 */
            if (substr($token, -4) === '.ics') {
                $token = substr($token, 0, -4);
            }
            /* 格式不对和不存在统一回 404，别给探测者区分信号 */
            if (!preg_match('/^[a-f0-9]{64}$/', $token)) {
                lb_ics_emit_empty('订阅地址无效，请在设置页重新生成');
            }
            $st = lb_db()->prepare(
                'SELECT b.data FROM users u INNER JOIN boards b ON b.user_id = u.id '
                . 'WHERE u.ics_token = ? AND u.status = \'active\' LIMIT 1'
            );
            $st->execute([$token]);
            $raw = $st->fetchColumn();
            if (!is_string($raw) || $raw === '') {
                lb_ics_emit_empty('订阅地址已失效，请在设置页重新生成');
            }
            $state = json_decode($raw, true);
            if (!is_array($state)) {
                http_response_code(500);
                header('Content-Type: text/plain; charset=utf-8');
                echo '数据损坏';
                exit;
            }
            $built = lb_ics_build($state);
            http_response_code(200);
            header('Content-Type: text/calendar; charset=utf-8');
            /* 引号必须是普通的双引号。写成 \" 的话发出去就是字面带反斜杠的值，
               宽松的客户端（Google）会忽略，严格的（小米日历）直接判定格式错误。 */
            header('Content-Disposition: inline; filename="wanfeng-todo.ics"');
            /* 显式给出长度：不写可能变成 chunked 传输，部分国产 ROM 的日历
               对分块响应处理有问题，会直接报「导入失败」 */
            header('Content-Length: ' . strlen($built['text']));
            /* 允许短暂缓存。no-store 更安全，但有些订阅客户端会把它理解成
               「这个源不可缓存」而拒绝保存 */
            header('Cache-Control: private, max-age=300');
            header('X-Content-Type-Options: nosniff');
            if ($method === 'HEAD') {
                exit;   /* 只要响应头，正文不输出 */
            }
            echo $built['text'];
            exit;

        /* ---------- 手机推送 ----------
           地址不在这里回显成脱敏形式，而是原样返回：
           用户需要能核对、能复制，登录态下给完整地址是合理的。 */
        case 'push_status':
            if ($method !== 'GET') {
                lb_fail('请使用 GET', 405, 'method_not_allowed');
            }
            $user = lb_auth();
            $st = lb_db()->prepare(
                'SELECT push_webhook, push_enabled FROM users WHERE id = ? LIMIT 1'
            );
            $st->execute([(int)$user['id']]);
            $row = $st->fetch() ?: [];
            $cnt = lb_db()->prepare(
                'SELECT COUNT(*) FROM push_sent WHERE user_id = ? AND sent_at >= ?'
            );
            $cnt->execute([
                (int)$user['id'],
                (new DateTimeImmutable('today', lb_ics_tz()))->format('Y-m-d H:i:s'),
            ]);
            $last = lb_db()->prepare(
                'SELECT sent_at FROM push_sent WHERE user_id = ? ORDER BY sent_at DESC LIMIT 1'
            );
            $last->execute([(int)$user['id']]);
            /* 最近 10 条发送记录，给「推送中心」展示。
               SELECT * 是为了兼容还没加 content 列的旧库（那一列取不到就当空）。 */
            $recentSt = lb_db()->prepare(
                'SELECT * FROM push_sent WHERE user_id = ? ORDER BY sent_at DESC LIMIT 10'
            );
            $recentSt->execute([(int)$user['id']]);
            $recent = [];
            foreach ($recentSt->fetchAll() as $s) {
                $recent[] = [
                    'key' => (string)($s['slot_key'] ?? ''),
                    'kind' => (string)($s['kind'] ?? ''),
                    'at' => (string)($s['sent_at'] ?? ''),
                    'text' => (string)($s['content'] ?? ''),
                ];
            }
            lb_json([
                'ok' => true,
                'enabled' => (int)($row['push_enabled'] ?? 0) === 1,
                'webhook' => (string)($row['push_webhook'] ?? ''),
                'sent_today' => (int)$cnt->fetchColumn(),
                'last_sent' => (string)($last->fetchColumn() ?: ''),
                'recent' => $recent,
            ]);
            break;

        case 'push_save':
            lb_require_post();
            $user = lb_auth();
            lb_require_csrf();
            $in = lb_body();
            $url = trim((string)($in['webhook'] ?? ''));
            if ($url !== '' && !lb_push_url_ok($url)) {
                lb_fail(
                    '这条地址不像是企业微信机器人。正确形式是 '
                    . 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=...',
                    400,
                    'bad_webhook'
                );
            }
            $enabled = !empty($in['enabled']) && $url !== '';
            $up = lb_db()->prepare(
                'UPDATE users SET push_webhook = ?, push_enabled = ? WHERE id = ?'
            );
            $up->execute([$url !== '' ? $url : null, $enabled ? 1 : 0, (int)$user['id']]);
            lb_json(['ok' => true, 'enabled' => $enabled]);
            break;

        case 'push_test':
            lb_require_post();
            $user = lb_auth();
            lb_require_csrf();
            $st = lb_db()->prepare('SELECT push_webhook FROM users WHERE id = ? LIMIT 1');
            $st->execute([(int)$user['id']]);
            $url = (string)$st->fetchColumn();
            if ($url === '') {
                lb_fail('还没填推送地址', 400, 'no_webhook');
            }
            $now = new DateTimeImmutable('now', lb_ics_tz());
            $ok = lb_push_send(
                $url,
                '晚风 Todo 测试消息' . "\n" . '时间是 ' . $now->format('Y-m-d H:i:s')
                . "\n" . '收到这条就说明推送通道是通的。',
                $why
            );
            if (!$ok) {
                lb_fail('没发出去：' . $why, 502, 'push_failed');
            }
            lb_json(['ok' => true]);
            break;

        case 'push_off':
            lb_require_post();
            $user = lb_auth();
            lb_require_csrf();
            lb_db()->prepare('UPDATE users SET push_enabled = 0 WHERE id = ?')
                ->execute([(int)$user['id']]);
            lb_json(['ok' => true]);
            break;

        /* 今日推送计划：把这一天所有会推的时间点列出来，供「推送中心」预览。
           只读，不写库、不发消息、不消耗去重记录——纯粹回答「今天几点会推什么」。 */
        case 'push_preview':
            if ($method !== 'GET') {
                lb_fail('请使用 GET', 405, 'method_not_allowed');
            }
            $user = lb_auth();
            $bd = lb_db()->prepare('SELECT data FROM boards WHERE user_id = ? LIMIT 1');
            $bd->execute([(int)$user['id']]);
            $state = json_decode((string)$bd->fetchColumn(), true);
            $today = (new DateTimeImmutable('now', lb_ics_tz()))->format('Y-m-d');
            $plan = [];
            if (is_array($state)) {
                $plan = array_merge(
                    lb_schedule_day($state, $today),
                    lb_schedule_reports($state, $today)
                );
            }
            usort($plan, static function ($a, $b) {
                return strcmp((string)$a['time'], (string)$b['time']);
            });
            $items = [];
            foreach ($plan as $it) {
                $items[] = [
                    'time' => (string)($it['time'] ?? ''),
                    'kind' => (string)($it['kind'] ?? ''),
                    'title' => (string)($it['title'] ?? ''),
                    'body' => (string)($it['body'] ?? ''),
                ];
            }
            lb_json(['ok' => true, 'date' => $today, 'items' => $items]);
            break;

        case 'load':
            if ($method !== 'GET') {
                lb_fail('请使用 GET', 405, 'method_not_allowed');
            }
            $user = lb_auth();
            $st = lb_db()->prepare('SELECT data, rev, updated_at FROM boards WHERE user_id = ? LIMIT 1');
            $st->execute([(int)$user['id']]);
            $row = $st->fetch();

            if (!$row) {
                lb_json(['ok' => true, 'data' => null, 'rev' => 0, 'updated_at' => 0]);
            }

            $data = json_decode((string)$row['data'], true);
            if (!is_array($data)) {
                lb_fail('云端数据损坏，请从备份恢复', 500, 'bad_remote_data');
            }
            lb_json([
                'ok' => true,
                'data' => $data,
                'rev' => (int)$row['rev'],
                'updated_at' => (int)$row['updated_at'],
            ]);
            break;

        case 'history':
            if ($method !== 'GET') {
                lb_fail('请使用 GET', 405, 'method_not_allowed');
            }
            $user = lb_auth();
            $uid = (int)$user['id'];
            $id = isset($_GET['id']) ? (int)$_GET['id'] : 0;
            $pdo = lb_db();
            lb_prune_revisions($pdo, $uid, (int)round(microtime(true) * 1000));

            if ($id > 0) {
                $st = $pdo->prepare(
                    'SELECT id, rev, data, reason, created_at FROM board_revisions WHERE id = ? AND user_id = ? LIMIT 1'
                );
                $st->execute([$id, $uid]);
                $rev = $st->fetch();
                if (!$rev) {
                    lb_fail('历史版本不存在', 404, 'revision_not_found');
                }
                $data = json_decode((string)$rev['data'], true);
                if (!is_array($data)) {
                    lb_fail('历史数据损坏', 500, 'bad_revision_data');
                }
                lb_json([
                    'ok' => true,
                    'item' => [
                        'id' => (int)$rev['id'],
                        'rev' => (int)$rev['rev'],
                        'reason' => (string)$rev['reason'],
                        'created_at' => (int)$rev['created_at'],
                        'data' => $data,
                    ],
                ]);
            }

            $st = $pdo->prepare(
                'SELECT id, rev, reason, created_at, LENGTH(data) AS bytes
                 FROM board_revisions WHERE user_id = ? ORDER BY id DESC LIMIT 20'
            );
            $st->execute([$uid]);
            $items = [];
            foreach ($st->fetchAll() as $row) {
                $items[] = [
                    'id' => (int)$row['id'],
                    'rev' => (int)$row['rev'],
                    'reason' => (string)$row['reason'],
                    'created_at' => (int)$row['created_at'],
                    'bytes' => (int)$row['bytes'],
                ];
            }
            lb_json(['ok' => true, 'items' => $items]);
            break;

        case 'restore':
            lb_require_post();
            $user = lb_auth();
            lb_require_csrf();
            $body = lb_body();
            $id = (int)($body['id'] ?? 0);
            if ($id <= 0) {
                lb_fail('缺少历史版本 id', 400, 'bad_revision_id');
            }
            $uid = (int)$user['id'];
            $pdo = lb_db();
            $st = $pdo->prepare(
                'SELECT id, rev, data FROM board_revisions WHERE id = ? AND user_id = ? LIMIT 1'
            );
            $st->execute([$id, $uid]);
            $rev = $st->fetch();
            if (!$rev) {
                lb_fail('历史版本不存在', 404, 'revision_not_found');
            }
            $revData = json_decode((string)$rev['data'], true);
            if (!is_array($revData) || !isset($revData['habits'], $revData['tasks'])
                || !is_array($revData['habits']) || !is_array($revData['tasks'])) {
                lb_fail('历史数据损坏', 500, 'bad_revision_data');
            }
            $now = (int)round(microtime(true) * 1000);
            $pdo->beginTransaction();
            try {
                $boardSt = $pdo->prepare('SELECT data, rev, updated_at FROM boards WHERE user_id = ? FOR UPDATE');
                $boardSt->execute([$uid]);
                $board = $boardSt->fetch();
                if (!$board) {
                    $pdo->rollBack();
                    lb_fail('云端还没有数据，无法恢复', 404, 'no_board');
                }
                lb_snapshot_board($pdo, $uid, (string)$board['data'], (int)$board['rev'], 'restore', $now);
                $newRev = (int)$board['rev'] + 1;
                $up = $pdo->prepare('UPDATE boards SET data = ?, rev = ?, updated_at = ? WHERE user_id = ?');
                $up->execute([(string)$rev['data'], $newRev, $now, $uid]);
                $pdo->commit();
                lb_json([
                    'ok' => true,
                    'data' => $revData,
                    'rev' => $newRev,
                    'updated_at' => $now,
                ]);
            } catch (Throwable $e) {
                if ($pdo->inTransaction()) {
                    $pdo->rollBack();
                }
                throw $e;
            }
            break;

        case 'save':
        case 'force':
            lb_require_post();
            $user = lb_auth();
            lb_require_csrf();

            $body = lb_body();
            $data = $body['data'] ?? null;
            if (!is_array($data) || !isset($data['habits'], $data['tasks'])
                || !is_array($data['habits']) || !is_array($data['tasks'])) {
                lb_fail('数据格式不正确', 400, 'bad_data');
            }

            $json = json_encode($data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
            if ($json === false) {
                lb_fail('数据无法序列化', 400, 'bad_data');
            }
            if (strlen($json) > (int)lb_config()['max_bytes']) {
                lb_fail('数据太大', 413, 'too_large');
            }

            $force = ($action === 'force');
            $baseRev = $force ? -1 : (int)($body['base_rev'] ?? 0);
            $now = (int)round(microtime(true) * 1000);
            $uid = (int)$user['id'];
            $pdo = lb_db();
            $pdo->beginTransaction();

            try {
                $st = $pdo->prepare('SELECT data, rev, updated_at FROM boards WHERE user_id = ? FOR UPDATE');
                $st->execute([$uid]);
                $row = $st->fetch();

                if (!$row) {
                    $rev = 1;
                    $ins = $pdo->prepare(
                        'INSERT INTO boards (user_id, data, rev, updated_at) VALUES (?, ?, ?, ?)'
                    );
                    $ins->execute([$uid, $json, $rev, $now]);
                    $pdo->commit();
                    lb_json(['ok' => true, 'rev' => $rev, 'updated_at' => $now]);
                }

                if (!$force && $baseRev !== (int)$row['rev']) {
                    $remoteData = json_decode((string)$row['data'], true);
                    $pdo->rollBack();
                    lb_json([
                        'ok' => false,
                        'error' => '云端有更新',
                        'code' => 'conflict',
                        'remote' => [
                            'data' => $remoteData,
                            'rev' => (int)$row['rev'],
                            'updated_at' => (int)$row['updated_at'],
                        ],
                    ], 409);
                }

                lb_snapshot_board($pdo, $uid, (string)$row['data'], (int)$row['rev'], 'save', $now);
                $rev = (int)$row['rev'] + 1;
                $up = $pdo->prepare('UPDATE boards SET data = ?, rev = ?, updated_at = ? WHERE user_id = ?');
                $up->execute([$json, $rev, $now, $uid]);
                $pdo->commit();
                lb_json(['ok' => true, 'rev' => $rev, 'updated_at' => $now]);
            } catch (Throwable $e) {
                if ($pdo->inTransaction()) {
                    $pdo->rollBack();
                }
                throw $e;
            }
            break;

        case 'change_password':
            lb_require_post();
            $user = lb_auth();
            lb_require_csrf();

            $body = lb_body();
            $current = (string)($body['current_password'] ?? '');
            $new = (string)($body['new_password'] ?? '');
            if ($current === '' || lb_strlen($new) < 8 || strlen($new) > 200) {
                lb_fail('新密码至少 8 位', 400, 'bad_password');
            }

            $st = lb_db()->prepare('SELECT password_hash FROM users WHERE id = ? LIMIT 1');
            $st->execute([(int)$user['id']]);
            $hash = (string)$st->fetchColumn();
            if (!password_verify($current, $hash)) {
                lb_fail('当前密码不正确', 400, 'bad_current_password');
            }

            $newEpoch = (int)$user['session_epoch'] + 1;
            $up = lb_db()->prepare('UPDATE users SET password_hash = ?, session_epoch = ? WHERE id = ?');
            $up->execute([password_hash($new, PASSWORD_DEFAULT), $newEpoch, (int)$user['id']]);
            $_SESSION['epoch'] = $newEpoch;

            lb_json(['ok' => true]);
            break;

        case 'admin_users':
            if ($method !== 'GET') {
                lb_fail('请使用 GET', 405, 'method_not_allowed');
            }
            lb_admin();
            $rows = lb_db()->query(
                'SELECT id, email, display_name, is_admin, status, session_epoch, created_at, last_login_at '
                . 'FROM users ORDER BY id ASC'
            )->fetchAll();
            lb_json([
                'ok' => true,
                'users' => array_map('lb_public_user', $rows),
            ]);
            break;

        case 'admin_user_update':
            lb_require_post();
            $admin = lb_admin();
            lb_require_csrf();

            $body = lb_body();
            $targetId = (int)($body['id'] ?? 0);
            $targetAction = (string)($body['action'] ?? '');
            $value = (string)($body['value'] ?? '');
            $target = lb_user_by_id($targetId);
            if (!$target) {
                lb_fail('用户不存在', 404, 'not_found');
            }

            if ($targetAction === 'reset_password') {
                if (lb_strlen($value) < 8 || strlen($value) > 200) {
                    lb_fail('新密码至少 8 位', 400, 'bad_password');
                }
                $newEpoch = (int)$target['session_epoch'] + 1;
                $up = lb_db()->prepare('UPDATE users SET password_hash = ?, session_epoch = ? WHERE id = ?');
                $up->execute([password_hash($value, PASSWORD_DEFAULT), $newEpoch, $targetId]);
                if ($targetId === (int)$admin['id']) {
                    $_SESSION['epoch'] = $newEpoch;
                }
                $target['session_epoch'] = $newEpoch;
                lb_json(['ok' => true, 'user' => lb_public_user($target)]);
            }

            if ($targetAction === 'set_status') {
                $status = $value === 'disabled' ? 'disabled' : 'active';
                if ($targetId === (int)$admin['id'] && $status === 'disabled') {
                    lb_fail('不能停用自己的管理员账号', 400, 'cannot_disable_self');
                }
                $newEpoch = $status === 'disabled' ? (int)$target['session_epoch'] + 1 : (int)$target['session_epoch'];
                $up = lb_db()->prepare('UPDATE users SET status = ?, session_epoch = ? WHERE id = ?');
                $up->execute([$status, $newEpoch, $targetId]);
                $target['status'] = $status;
                $target['session_epoch'] = $newEpoch;
                lb_json(['ok' => true, 'user' => lb_public_user($target)]);
            }

            lb_fail('未知的用户操作', 400, 'bad_action');
            break;

        case 'admin_settings':
            if ($method !== 'GET') {
                lb_fail('请使用 GET', 405, 'method_not_allowed');
            }
            lb_admin();
            $settings = lb_settings();
            lb_json([
                'ok' => true,
                'settings' => [
                    'registration_open' => $settings['registration_open'] === '1',
                    'invite_code' => $settings['invite_code'] ?? '',
                    'site_name' => $settings['site_name'] ?? '晚风Todo',
                ],
            ]);
            break;

        case 'admin_settings_save':
            lb_require_post();
            lb_admin();
            lb_require_csrf();

            $body = lb_body();
            $registrationOpen = !empty($body['registration_open']);
            $invite = strtoupper(trim((string)($body['invite_code'] ?? '')));
            $siteName = trim((string)($body['site_name'] ?? '晚风Todo'));

            if (!preg_match('/^[A-Z0-9_-]{4,32}$/', $invite)) {
                lb_fail('邀请码需为 4–32 位字母、数字、下划线或短横线', 400, 'bad_invite');
            }
            if ($siteName === '' || lb_strlen($siteName) > 40) {
                lb_fail('站点名称需为 1–40 个字符', 400, 'bad_site_name');
            }

            lb_save_settings([
                'registration_open' => $registrationOpen ? '1' : '0',
                'invite_code' => $invite,
                'site_name' => $siteName,
            ]);
            lb_json([
                'ok' => true,
                'settings' => [
                    'registration_open' => $registrationOpen,
                    'invite_code' => $invite,
                    'site_name' => $siteName,
                ],
            ]);
            break;

        case '':
            /* 有些客户端（尤其安卓日历）在添加订阅前会先探一下服务是否活着。
               线上 Nginx 配了 error_page 404，这里返回 404 会被换成 HTML 页面，
               客户端一看到 HTML 就判定服务不可用。给个 200 把探测打发掉。 */
            lb_json(['ok' => true, 'api' => 'wanfeng-todo', 'hint' => '请使用具体接口']);
            break;

        default:
            lb_fail('未知操作', 404, 'unknown_action');
    }
} catch (Throwable $e) {
    error_log('lifeboard api: ' . $e->getMessage());
    lb_fail('服务器内部错误', 500, 'server_error');
}
