<?php
declare(strict_types=1);

define('LIFEBOARD_API', true);

$lockFile = __DIR__ . '/install.lock';
$action = isset($_GET['action']) ? (string)$_GET['action'] : '';

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

lb_session_start();

header('X-Frame-Options: DENY');
header('Referrer-Policy: same-origin');
header('X-Content-Type-Options: nosniff');

$method = isset($_SERVER['REQUEST_METHOD']) ? (string)$_SERVER['REQUEST_METHOD'] : 'GET';

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

        default:
            lb_fail('未知操作', 404, 'unknown_action');
    }
} catch (Throwable $e) {
    error_log('lifeboard api: ' . $e->getMessage());
    lb_fail('服务器内部错误', 500, 'server_error');
}
