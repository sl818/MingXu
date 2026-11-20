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
/* 邮件提醒：secret_box 提供授权码加解密，mailer 提供 SMTP 发信。
   两者都只定义函数，不改变 push / schedule 的任何行为。 */
require_once __DIR__ . '/api/secret_box.php';
require_once __DIR__ . '/api/mailer.php';

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
            lb_json(array_merge([
                'ok' => true,
                'user' => $user ? lb_public_user($user) : null,
                'csrf' => lb_csrf(),
                'site_name' => $settings['site_name'] ?? '明序',
            ], lb_reg_public()));
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
                'site_name' => lb_setting('site_name', '明序'),
            ]);
            break;

        /* 发注册验证码（仅 email 模式）。限流：同邮箱 60 秒一条 / 每天 10 条，同 IP 每天 20 条 */
        case 'register_code':
            lb_require_post();
            lb_require_csrf();
            if (lb_reg_mode() !== 'email') {
                lb_fail('当前不是邮箱验证注册', 400, 'not_email_mode');
            }
            if (!lb_site_mail_ready()) {
                lb_fail('站点还没配好发信服务，暂时不能注册，请联系管理员', 400, 'site_mail_not_ready');
            }
            lb_register_limit();

            $inC = lb_body();
            $emailC = strtolower(trim((string)($inC['email'] ?? '')));
            if (!filter_var($emailC, FILTER_VALIDATE_EMAIL) || strlen($emailC) > 190) {
                lb_fail('请输入有效的邮箱地址', 400, 'bad_email');
            }
            $pdoC = lb_db();
            $stEx = $pdoC->prepare('SELECT id FROM users WHERE email = ? LIMIT 1');
            $stEx->execute([$emailC]);
            if ($stEx->fetchColumn()) {
                lb_fail('这个邮箱已经注册过了，直接登录即可', 409, 'email_exists');
            }

            $nowC = time();
            $stFast = $pdoC->prepare('SELECT COUNT(*) FROM email_codes WHERE email = ? AND created_at > ?');
            $stFast->execute([$emailC, date('Y-m-d H:i:s', $nowC - 60)]);
            if ((int)$stFast->fetchColumn() > 0) {
                lb_fail('验证码刚发过，60 秒后再试', 429, 'too_fast');
            }
            $stDay = $pdoC->prepare('SELECT COUNT(*) FROM email_codes WHERE email = ? AND created_at > ?');
            $stDay->execute([$emailC, date('Y-m-d 00:00:00')]);
            if ((int)$stDay->fetchColumn() >= 10) {
                lb_fail('这个邮箱今天发得太多了，明天再试或联系管理员', 429, 'email_quota');
            }
            $ipC = substr((string)($_SERVER['REMOTE_ADDR'] ?? ''), 0, 45);
            if ($ipC !== '') {
                $stIp = $pdoC->prepare('SELECT COUNT(*) FROM email_codes WHERE ip = ? AND created_at > ?');
                $stIp->execute([$ipC, date('Y-m-d 00:00:00')]);
                if ((int)$stIp->fetchColumn() >= 20) {
                    lb_fail('这台设备今天申请得太多了，明天再试', 429, 'ip_quota');
                }
            }

            $codeC = (string)random_int(100000, 999999);
            /* 重发让旧码立即失效，避免同时有两个能用的码 */
            $pdoC->prepare('UPDATE email_codes SET used_at = ? WHERE email = ? AND purpose = ? AND used_at IS NULL')
                ->execute([date('Y-m-d H:i:s'), $emailC, 'register']);
            $pdoC->prepare('INSERT INTO email_codes (email, purpose, code_hash, expires_at, ip, created_at) VALUES (?, ?, ?, ?, ?, ?)')
                ->execute([$emailC, 'register', hash('sha256', $codeC),
                           date('Y-m-d H:i:s', $nowC + 600), $ipC, date('Y-m-d H:i:s')]);

            $errC = '';
            $okC = lb_site_mail_send($emailC, '【明序】注册验证码',
                "你的注册验证码是：{$codeC}\n\n10 分钟内有效，只能用一次。\n"
                . '如果不是你本人操作，忽略这封邮件即可。', $errC);
            if (!$okC) {
                lb_fail('验证码发送失败：' . $errC, 400, 'send_failed');
            }
            lb_json(['ok' => true, 'sent' => true, 'email' => $emailC]);
            break;

        case 'register':
            lb_require_post();
            lb_require_csrf();

            $regMode = lb_reg_mode();
            if ($regMode === 'closed') {
                lb_fail('管理员关闭了注册', 403, 'registration_closed');
            }
            lb_register_limit();

            $body = lb_body();
            $email = strtolower(trim((string)($body['email'] ?? '')));
            $password = (string)($body['password'] ?? '');
            $display = trim((string)($body['display_name'] ?? ''));
            $invite = strtoupper(trim((string)($body['invite'] ?? '')));
            $regCode = trim((string)($body['code'] ?? ''));

            if ($regMode === 'invite') {
                $expected = strtoupper((string)lb_setting('invite_code', ''));
                if ($expected === '' || !hash_equals($expected, $invite)) {
                    lb_fail('邀请码不正确', 403, 'invite_invalid');
                }
            }
            if ($regMode === 'email') {
                if (!lb_site_mail_ready()) {
                    lb_fail('站点还没配好发信服务，暂时不能注册，请联系管理员', 400, 'site_mail_not_ready');
                }
                if ($regCode === '') {
                    lb_fail('请填写邮箱验证码', 400, 'code_required');
                }
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

            /* email 模式：验证码必须对上、没过期、没用过。放在插入前，避免生成废账号 */
            $codeRowId = 0;
            if ($regMode === 'email') {
                $stCode = $pdo->prepare(
                    'SELECT id FROM email_codes WHERE email = ? AND purpose = ? AND code_hash = ?'
                    . ' AND used_at IS NULL AND expires_at > ? ORDER BY id DESC LIMIT 1'
                );
                $stCode->execute([$email, 'register', hash('sha256', $regCode), date('Y-m-d H:i:s')]);
                $codeRowId = (int)$stCode->fetchColumn();
                if ($codeRowId <= 0) {
                    lb_fail('验证码不正确或已过期，请重新获取', 400, 'code_invalid');
                }
            }

            $newUid = 0;
            try {
                $ins = $pdo->prepare(
                    'INSERT INTO users (email, password_hash, display_name, is_admin, status, session_epoch, created_at) '
                    . 'VALUES (?, ?, ?, 0, \'active\', 0, NOW())'
                );
                $ins->execute([$email, password_hash($password, PASSWORD_DEFAULT), $display]);
                /* 必须紧跟 INSERT 取。v126 曾把它放在一条 UPDATE 之后，某些驱动下会返回 0，
                   结果账号已经建好却报「注册失败」，用户重试只会看到「已注册」。 */
                $newUid = (int)$pdo->lastInsertId();
            } catch (PDOException $e) {
                if ((string)$e->getCode() === '23000') {
                    lb_fail('这个邮箱已经注册过了，直接登录即可', 409, 'email_exists');
                }
                throw $e;
            }

            /* 拿不到 id 就按邮箱找回：这时候账号已经落库了，不能再说"注册失败" */
            if ($newUid <= 0) {
                $stNew = $pdo->prepare('SELECT id FROM users WHERE email = ? LIMIT 1');
                $stNew->execute([$email]);
                $newUid = (int)$stNew->fetchColumn();
            }

            if ($codeRowId > 0) {
                $pdo->prepare('UPDATE email_codes SET used_at = ? WHERE id = ?')
                    ->execute([date('Y-m-d H:i:s'), $codeRowId]);
            }

            $user = $newUid > 0 ? lb_user_by_id($newUid) : null;
            if (!$user) {
                /* 账号已存在，只是没能读回来。让用户直接登录，别让他再注册一次 */
                lb_fail('账号已创建，但初始化没完成。请直接用刚才的邮箱和密码登录', 500, 'registered_but_unreadable');
            }
            lb_session_login($user);
            $up = $pdo->prepare('UPDATE users SET last_login_at = NOW() WHERE id = ?');
            $up->execute([(int)$user['id']]);
            $user['last_login_at'] = date('Y-m-d H:i:s');

            /* v125：注册确认信。**发不出去也不影响注册**——它只是告知，不是验证门槛。
               站点邮箱只做这类事务性邮件；到点提醒走各用户自己绑的邮箱。 */
            try {
                if (lb_site_mail_ready()) {
                    $errR = '';
                    lb_site_mail_send($email, '【明序】账号已开通',
                        "你的明序账号已创建。\n\n"
                        . '登录邮箱：' . $email . "\n"
                        . '站点地址：' . lb_site_url() . "\n\n"
                        . "想让到点提醒也发到邮箱，去「设置 → 邮件提醒」绑定你自己的邮箱。\n"
                        . '站点邮箱只用于注册确认和找回密码，不会替你接收提醒。', $errR);
                }
            } catch (Throwable $e) {
                /* 忽略 */
            }

            lb_json(array_merge([
                'ok' => true,
                'user' => lb_public_user($user),
                'csrf' => $_SESSION['csrf'],
                'site_name' => lb_setting('site_name', '明序'),
            ], lb_reg_public()));
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
            /* text 可选：自定义通知的「重发」借这个口子把原文再发一次。
               不传就是原来的测试消息。长度由 lb_push_send 里的 lb_push_clip 兜底（2048 字节）。 */
            $text = trim((string)($in['text'] ?? ''));
            if ($text === '') {
                $text = '明序 测试消息' . "\n" . '时间是 ' . $now->format('Y-m-d H:i:s')
                    . "\n" . '收到这条就说明推送通道是通的。';
            }
            $ok = lb_push_send($url, $text, $why);
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

        /* ---------- 邮件提醒（QQ 邮箱 SMTP）----------
           授权码只进不出：mail_status 不回显任何片段，只给 hasSecret。
           原 IMAP / 企业微信推送逻辑一律不动。 */
        case 'mail_status':
            if ($method !== 'GET') {
                lb_fail('请使用 GET', 405, 'method_not_allowed');
            }
            $user = lb_auth();
            lb_json([
                'ok' => true,
                'config' => lb_mail_cfg_public(lb_mail_cfg_load(lb_db(), (int)$user['id'])),
                'crypto_ready' => lb_secret_ready(),
                'recipient' => (string)$user['email'],
            ]);
            break;

        case 'mail_save':
            lb_require_post();
            $user = lb_auth();
            lb_require_csrf();
            $in = lb_body();
            $res = lb_mail_cfg_save(lb_db(), (int)$user['id'], [
                'host' => $in['host'] ?? null,
                'port' => $in['port'] ?? null,
                'secure' => $in['secure'] ?? null,
                'user' => $in['user'] ?? null,
                'from' => $in['from'] ?? null,
                'name' => $in['name'] ?? null,
                'secret' => $in['secret'] ?? '',
                'enabled' => !empty($in['enabled']),
            ]);
            if (!$res['ok']) {
                lb_fail($res['error'], 400, 'mail_save_failed');
            }
            lb_json(['ok' => true, 'config' => lb_mail_cfg_public($res['cfg'])]);
            break;

        case 'mail_test':
            lb_require_post();
            $user = lb_auth();
            lb_require_csrf();
            $in = lb_body();
            $pdo = lb_db();
            $uid = (int)$user['id'];
            $saved = lb_mail_cfg_load($pdo, $uid);

            /* 带字段 = 用表单里还没保存的值试发；不带 = 用已保存的配置。
               授权码留空表示沿用已保存的那一个（前端永远拿不到明文）。 */
            $cfg = $saved;
            foreach (['host', 'secure', 'user', 'from', 'name'] as $k) {
                if (array_key_exists($k, $in)) {
                    $cfg[$k] = trim((string)$in[$k]);
                }
            }
            if (array_key_exists('port', $in)) {
                $cfg['port'] = (int)$in['port'];
            }
            if (!empty($in['secret'])) {
                $cfg['secret'] = (string)$in['secret'];
            }

            /* 收件人固定为登录邮箱：绝不让这个接口变成任意地址的发信跳板 */
            $to = (string)$user['email'];
            if (filter_var($to, FILTER_VALIDATE_EMAIL) === false) {
                lb_fail('账号邮箱不合法，无法接收测试信', 400, 'bad_recipient');
            }
            $now = (new DateTimeImmutable('now', lb_ics_tz()))->format('Y-m-d H:i:s');
            $why = '';
            $ok = lb_mail_send(
                $cfg,
                $to,
                '明序 · 邮件测试',
                '这是一封测试邮件。' . "\n" . '发送时间：' . $now . "\n"
                . 'SMTP：' . $cfg['host'] . ':' . $cfg['port']
                . "\n" . '收到就说明邮件通道已经配好了。',
                $why
            );
            lb_mail_cfg_mark($pdo, $uid, $ok, $why);
            if (!$ok) {
                lb_fail('没发出去：' . $why, 502, 'mail_failed');
            }
            lb_json(['ok' => true, 'to' => $to]);
            break;

        /* ===== 站点邮件（管理员配置，只用于注册确认与找回密码）===== */
        case 'site_mail_status':
            lb_admin();
            $cfg = lb_site_mail_cfg_load();
            lb_json(['ok' => true, 'config' => lb_site_mail_cfg_public($cfg),
                     'ready' => lb_site_mail_ready(), 'admin_email' => (string)lb_admin()['email']]);
            break;

        case 'site_mail_save':
            lb_require_post();
            lb_admin();
            lb_require_csrf();
            $res = lb_site_mail_cfg_save((array)lb_body());
            if (!$res['ok']) {
                lb_fail($res['error'], 400, 'site_mail_save_failed');
            }
            lb_json(['ok' => true, 'config' => $res['cfg'], 'ready' => lb_site_mail_ready()]);
            break;

        case 'site_mail_test':
            lb_require_post();
            $admin = lb_admin();
            lb_require_csrf();
            if (!lb_site_mail_ready()) {
                lb_fail('站点邮件还没配完整（服务器 / 账号 / 授权码 / 发件人）', 400, 'site_mail_not_ready');
            }
            $err = '';
            $okSend = lb_site_mail_send((string)$admin['email'], '【明序】站点邮件测试',
                "这是站点邮件的测试信件。\n\n"
                . "它只用于「注册确认」和「找回密码」两类邮件，提醒通知不会走这个邮箱。\n"
                . '收件人固定为管理员自己的地址。', $err);
            if (!$okSend) {
                lb_fail('没发出去：' . $err, 400, 'site_mail_test_failed');
            }
            lb_json(['ok' => true, 'to' => (string)$admin['email']]);
            break;

        /* 找回密码：第一步，申请重置链接。无论邮箱是否存在都回同样的结果，防枚举 */
        case 'password_forgot':
            lb_require_post();
            lb_require_csrf();
            $in2 = lb_body();
            $email2 = strtolower(trim((string)($in2['email'] ?? '')));
            if (!lb_site_mail_ready()) {
                lb_fail('站点还没配好发信服务，请联系管理员重置密码', 400, 'site_mail_not_ready');
            }
            if (!filter_var($email2, FILTER_VALIDATE_EMAIL)) {
                lb_json(['ok' => true, 'sent' => true]);
                break;
            }
            $stU = lb_db()->prepare("SELECT id, email, status FROM users WHERE email = ? LIMIT 1");
            $stU->execute([$email2]);
            $u2 = $stU->fetch();
            if (!$u2 || (string)$u2['status'] !== 'active') {
                lb_json(['ok' => true, 'sent' => true]);
                break;
            }
            $uid2 = (int)$u2['id'];
            /* 5 分钟内已申请过就不重发，避免被当成发信工具 */
            $stR = lb_db()->prepare('SELECT COUNT(*) FROM password_resets WHERE user_id = ? AND created_at > ?');
            $stR->execute([$uid2, date('Y-m-d H:i:s', time() - 300)]);
            if ((int)$stR->fetchColumn() > 0) {
                lb_json(['ok' => true, 'sent' => true]);
                break;
            }
            $token = bin2hex(random_bytes(32));
            $insR = lb_db()->prepare('INSERT INTO password_resets (user_id, token_hash, expires_at, created_at) VALUES (?, ?, ?, ?)');
            $insR->execute([$uid2, hash('sha256', $token), date('Y-m-d H:i:s', time() + 1800), date('Y-m-d H:i:s')]);
            $link = lb_site_url() . '/?reset=1&token=' . $token;
            $err2 = '';
            $ok2 = lb_site_mail_send($email2, '【明序】重置密码',
                "有人在明序上申请重置这个账号的密码。\n\n"
                . "点下面的链接设置新密码，链接 30 分钟内有效、只能用一次：\n" . $link . "\n\n"
                . "如果不是你本人操作，忽略这封邮件即可，密码不会被改动。", $err2);
            if (!$ok2) {
                lb_fail('邮件发送失败：' . $err2, 400, 'send_failed');
            }
            lb_json(['ok' => true, 'sent' => true]);
            break;

        /* 找回密码：第二步，用令牌设置新密码 */
        case 'password_reset':
            lb_require_post();
            lb_require_csrf();
            $in3 = lb_body();
            $tok = trim((string)($in3['token'] ?? ''));
            $pw3 = (string)($in3['password'] ?? '');
            if ($tok === '' || strlen($tok) < 32) {
                lb_fail('链接不完整，请重新申请', 400, 'bad_token');
            }
            if (lb_strlen($pw3) < 8 || strlen($pw3) > 200) {
                lb_fail('新密码至少 8 位', 400, 'bad_password');
            }
            $stT = lb_db()->prepare(
                'SELECT id, user_id FROM password_resets WHERE token_hash = ? AND used_at IS NULL AND expires_at > ? LIMIT 1'
            );
            $stT->execute([hash('sha256', $tok), date('Y-m-d H:i:s')]);
            $row3 = $stT->fetch();
            if (!$row3) {
                lb_fail('这个链接已失效或已用过，请重新申请', 400, 'token_expired');
            }
            $uid3 = (int)$row3['user_id'];
            $stE = lb_db()->prepare('SELECT session_epoch FROM users WHERE id = ? LIMIT 1');
            $stE->execute([$uid3]);
            $epoch3 = (int)$stE->fetchColumn() + 1;
            lb_db()->prepare('UPDATE users SET password_hash = ?, session_epoch = ? WHERE id = ?')
                ->execute([password_hash($pw3, PASSWORD_DEFAULT), $epoch3, $uid3]);
            lb_db()->prepare('UPDATE password_resets SET used_at = ? WHERE id = ?')
                ->execute([date('Y-m-d H:i:s'), (int)$row3['id']]);
            lb_json(['ok' => true]);
            break;

        case 'notify_prefs':
            $user = lb_auth();
            $uid = (int)$user['id'];
            lb_json([
                'ok' => true,
                'kinds' => lb_notify_kinds(),
                'channels' => lb_notify_channels(),
                'prefs' => lb_notify_prefs_load(lb_db(), $uid),
                'quiet' => lb_notify_quiet_load(lb_db(), $uid),
                'report' => lb_notify_report_load(lb_db(), $uid),
            ]);
            break;

        case 'notify_prefs_save':
            lb_require_post();
            $user = lb_auth();
            lb_require_csrf();
            $in = lb_body();
            $uid = (int)$user['id'];
            $res = lb_notify_prefs_save(lb_db(), $uid, (array)($in['prefs'] ?? []));
            if (!$res['ok']) {
                lb_fail($res['error'], 400, 'prefs_save_failed');
            }
            lb_notify_quiet_save(lb_db(), $uid, !empty($in['quiet']));
            $rep = lb_notify_report_save(lb_db(), $uid, (array)($in['report'] ?? []));
            if (!$rep['ok']) {
                lb_fail($rep['error'], 400, 'report_save_failed');
            }
            lb_json(['ok' => true, 'prefs' => $res['prefs'],
                     'quiet' => !empty($in['quiet']), 'report' => $rep['report']]);
            break;

        case 'mail_off':
            lb_require_post();
            $user = lb_auth();
            lb_require_csrf();
            lb_db()->prepare('UPDATE user_mail_config SET enabled = 0 WHERE user_id = ?')
                ->execute([(int)$user['id']]);
            lb_json(['ok' => true]);
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

        case 'profile_save':
            lb_require_post();
            $user = lb_auth();
            lb_require_csrf();

            $body = lb_body();
            $name = trim((string)($body['display_name'] ?? ''));
            $email = strtolower(trim((string)($body['email'] ?? '')));
            if (lb_strlen($name) > 40) {
                lb_fail('名称最多 40 个字符', 400, 'bad_display_name');
            }
            if ($email === '' || strlen($email) > 190 || !filter_var($email, FILTER_VALIDATE_EMAIL)) {
                lb_fail('邮箱格式不正确', 400, 'bad_email');
            }
            $st = lb_db()->prepare('SELECT id FROM users WHERE email = ? AND id <> ? LIMIT 1');
            $st->execute([$email, (int)$user['id']]);
            if ($st->fetch()) {
                lb_fail('这个邮箱已被其他账号使用', 409, 'email_taken');
            }
            $up = lb_db()->prepare('UPDATE users SET display_name = ?, email = ? WHERE id = ?');
            $up->execute([$name, $email, (int)$user['id']]);
            $fresh = lb_user_by_id((int)$user['id']);
            lb_json(['ok' => true, 'user' => $fresh ? lb_public_user($fresh) : null]);
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
                    'registration_mode' => lb_reg_mode(),
                    'site_mail_ready' => lb_site_mail_ready(),
                    'invite_code' => $settings['invite_code'] ?? '',
                    'site_name' => $settings['site_name'] ?? '明序',
                ],
            ]);
            break;

        case 'admin_settings_save':
            lb_require_post();
            lb_admin();
            lb_require_csrf();

            $body = lb_body();
            $mode = (string)($body['registration_mode'] ?? '');
            if ($mode === '') {
                /* 旧客户端只传 registration_open */
                $mode = !empty($body['registration_open']) ? 'invite' : 'closed';
            }
            if (!in_array($mode, ['closed', 'invite', 'email'], true)) {
                lb_fail('注册方式只能是 关闭 / 邀请码 / 邮箱验证', 400, 'bad_reg_mode');
            }
            if ($mode === 'email' && !lb_site_mail_ready()) {
                lb_fail('要开启邮箱验证注册，先把「站点邮件」配好并发信测试通过', 400, 'site_mail_not_ready');
            }
            $registrationOpen = $mode !== 'closed';
            $invite = strtoupper(trim((string)($body['invite_code'] ?? '')));
            $siteName = trim((string)($body['site_name'] ?? '明序'));

            if ($invite !== '' && !preg_match('/^[A-Z0-9_-]{4,32}$/', $invite)) {
                lb_fail('邀请码需为 4–32 位字母、数字、下划线或短横线', 400, 'bad_invite');
            }
            if ($mode === 'invite' && $invite === '') {
                lb_fail('选了邀请码注册，就必须填一个邀请码', 400, 'bad_invite');
            }
            if ($siteName === '' || lb_strlen($siteName) > 40) {
                lb_fail('站点名称需为 1–40 个字符', 400, 'bad_site_name');
            }

            lb_save_settings([
                'registration_open' => $registrationOpen ? '1' : '0',
                'registration_mode' => $mode,
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
