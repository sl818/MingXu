<?php
if (!defined('LIFEBOARD_API')) {
    http_response_code(404);
    exit;
}

const LB_LOGIN_WINDOW = 900;      // 15 分钟内
const LB_MAX_LOGIN_FAILS = 8;     // 同一 IP + 邮箱最多失败次数
const LB_REGISTER_WINDOW = 3600;  // 1 小时
const LB_MAX_REGISTERS = 10;      // 同一 IP 每小时最多注册尝试
const LB_DUMMY_HASH = '$2y$10$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi';

function lb_config(): array
{
    static $cfg = null;
    if ($cfg === null) {
        $cfg = require __DIR__ . '/config.php';
    }
    return $cfg;
}

function lb_is_https(): bool
{
    if (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off') {
        return true;
    }
    $proto = $_SERVER['HTTP_X_FORWARDED_PROTO'] ?? '';
    if (is_string($proto) && $proto !== '') {
        $first = strtolower(trim(explode(',', $proto)[0]));
        if ($first === 'https') {
            return true;
        }
    }
    return false;
}

function lb_session_start(): void
{
    if (session_status() === PHP_SESSION_ACTIVE) {
        return;
    }
    $cfg = lb_config();
    $secure = $cfg['cookie_secure'] === 'auto' ? lb_is_https() : (bool)$cfg['cookie_secure'];

    ini_set('session.use_strict_mode', '1');
    ini_set('session.use_only_cookies', '1');
    session_name((string)$cfg['session_name']);
    session_set_cookie_params([
        'lifetime' => 0,
        'path' => '/',
        'domain' => '',
        'secure' => $secure,
        'httponly' => true,
        'samesite' => 'Lax',
    ]);
    session_start();
}

function lb_db(): PDO
{
    static $pdo = null;
    if ($pdo instanceof PDO) {
        return $pdo;
    }
    $db = lb_config()['db'];
    $dsn = 'mysql:host=' . $db['host'] . ';port=' . (int)$db['port']
        . ';dbname=' . $db['name'] . ';charset=' . $db['charset'];
    $pdo = new PDO($dsn, (string)$db['user'], (string)$db['pass'], [
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        PDO::ATTR_EMULATE_PREPARES => false,
    ]);
    return $pdo;
}

function lb_strlen(string $value): int
{
    return function_exists('mb_strlen') ? (int)mb_strlen($value, 'UTF-8') : strlen($value);
}

function lb_json(array $payload, int $status = 200): void
{
    http_response_code($status);
    header('Content-Type: application/json; charset=utf-8');
    header('Cache-Control: no-store');
    header('X-Content-Type-Options: nosniff');
    $json = json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    if ($json === false) {
        http_response_code(500);
        echo '{"ok":false,"error":"响应序列化失败","code":"encode_error"}';
        exit;
    }
    echo $json;
    exit;
}

function lb_fail(string $message, int $status = 400, string $code = 'bad_request', array $extra = []): void
{
    lb_json(array_merge([
        'ok' => false,
        'error' => $message,
        'code' => $code,
    ], $extra), $status);
}

function lb_body(): array
{
    $raw = file_get_contents('php://input');
    if ($raw === false || $raw === '') {
        return [];
    }
    if (strlen($raw) > (int)lb_config()['max_bytes']) {
        lb_fail('数据太大', 413, 'too_large');
    }
    $data = json_decode($raw, true, 64);
    if (!is_array($data)) {
        lb_fail('请求格式不正确', 400, 'bad_json');
    }
    return $data;
}

function lb_require_post(): void
{
    if (($_SERVER['REQUEST_METHOD'] ?? 'GET') !== 'POST') {
        lb_fail('请使用 POST', 405, 'method_not_allowed');
    }
}

function lb_csrf(): string
{
    if (empty($_SESSION['csrf']) || !is_string($_SESSION['csrf'])) {
        $_SESSION['csrf'] = bin2hex(random_bytes(32));
    }
    return $_SESSION['csrf'];
}

function lb_require_csrf(): void
{
    $sent = $_SERVER['HTTP_X_CSRF_TOKEN'] ?? '';
    $known = $_SESSION['csrf'] ?? '';
    if (!is_string($sent) || !is_string($known) || $known === '' || !hash_equals($known, $sent)) {
        lb_fail('会话校验失败，请刷新页面后重试', 403, 'csrf');
    }
}

function lb_uid(): int
{
    return (int)($_SESSION['uid'] ?? 0);
}

function lb_user(): ?array
{
    $uid = lb_uid();
    if ($uid <= 0) {
        return null;
    }
    $st = lb_db()->prepare(
        'SELECT id, email, display_name, is_admin, status, session_epoch, created_at, last_login_at '
        . 'FROM users WHERE id = ? LIMIT 1'
    );
    $st->execute([$uid]);
    $user = $st->fetch();
    if (!$user || $user['status'] !== 'active') {
        unset($_SESSION['uid'], $_SESSION['epoch']);
        return null;
    }
    if (!isset($_SESSION['epoch']) || (int)$_SESSION['epoch'] !== (int)$user['session_epoch']) {
        // 之前登录过、但现在 epoch 对不上：说明这个账号在别处重新登录了，本设备被顶替
        $wasLoggedIn = isset($_SESSION['uid']);
        unset($_SESSION['uid'], $_SESSION['epoch']);
        if ($wasLoggedIn) {
            $_SESSION['kicked'] = 1;
        }
        return null;
    }
    return $user;
}

function lb_auth(): array
{
    $user = lb_user();
    if (!$user) {
        if (!empty($_SESSION['kicked'])) {
            unset($_SESSION['kicked']);
            lb_fail('这个账号已在其他设备登录，这台设备已退出。同一账号只允许一台设备在线。', 401, 'session_replaced');
        }
        lb_fail('请先登录', 401, 'unauthenticated');
    }
    return $user;
}

function lb_admin(): array
{
    $user = lb_auth();
    if ((int)$user['is_admin'] !== 1) {
        lb_fail('需要管理员权限', 403, 'forbidden');
    }
    return $user;
}

function lb_public_user(array $user): array
{
    return [
        'id' => (int)$user['id'],
        'email' => (string)$user['email'],
        'display_name' => (string)$user['display_name'],
        'is_admin' => (int)$user['is_admin'] === 1,
        'status' => (string)$user['status'],
        'created_at' => (string)$user['created_at'],
        'last_login_at' => $user['last_login_at'] !== null ? (string)$user['last_login_at'] : null,
    ];
}

function lb_user_by_id(int $id): ?array
{
    $st = lb_db()->prepare(
        'SELECT id, email, display_name, is_admin, status, session_epoch, created_at, last_login_at '
        . 'FROM users WHERE id = ? LIMIT 1'
    );
    $st->execute([$id]);
    $user = $st->fetch();
    return $user ?: null;
}

function lb_settings(bool $refresh = false): array
{
    static $cache = null;
    if ($cache !== null && !$refresh) {
        return $cache;
    }
    $cache = [
        'registration_open' => '0',
        'invite_code' => '',
        'site_name' => '晚风Todo',
    ];
    $rows = lb_db()->query('SELECT k, v FROM app_settings')->fetchAll();
    foreach ($rows as $row) {
        if (isset($row['k'])) {
            $cache[(string)$row['k']] = (string)$row['v'];
        }
    }
    return $cache;
}

function lb_setting(string $key, string $default = ''): string
{
    $settings = lb_settings();
    return array_key_exists($key, $settings) ? $settings[$key] : $default;
}

function lb_save_settings(array $values): void
{
    $st = lb_db()->prepare(
        'INSERT INTO app_settings (k, v) VALUES (?, ?) ON DUPLICATE KEY UPDATE v = VALUES(v)'
    );
    foreach ($values as $key => $value) {
        $st->execute([(string)$key, (string)$value]);
    }
    lb_settings(true);
}

function lb_session_login(array $user): void
{
    session_regenerate_id(true);
    $_SESSION['uid'] = (int)$user['id'];
    $_SESSION['epoch'] = (int)$user['session_epoch'];
    $_SESSION['csrf'] = bin2hex(random_bytes(32));
}

function lb_session_logout(): void
{
    $_SESSION = [];
    if (ini_get('session.use_cookies')) {
        $params = session_get_cookie_params();
        setcookie(session_name(), '', [
            'expires' => time() - 42000,
            'path' => $params['path'],
            'domain' => $params['domain'],
            'secure' => (bool)$params['secure'],
            'httponly' => (bool)$params['httponly'],
            'samesite' => 'Lax',
        ]);
    }
    session_destroy();
}

function lb_client_ip(): string
{
    $ip = (string)($_SERVER['REMOTE_ADDR'] ?? '');
    return filter_var($ip, FILTER_VALIDATE_IP) ? $ip : '0.0.0.0';
}

function lb_throttle_check(string $email): void
{
    $st = lb_db()->prepare(
        'SELECT COUNT(*) FROM login_attempts '
        . 'WHERE ip = ? AND email = ? AND at > (NOW() - INTERVAL ' . LB_LOGIN_WINDOW . ' SECOND)'
    );
    $st->execute([lb_client_ip(), $email]);
    if ((int)$st->fetchColumn() >= LB_MAX_LOGIN_FAILS) {
        lb_fail('尝试次数过多，请 15 分钟后再试', 429, 'rate_limited');
    }
}

function lb_throttle_add(string $email): void
{
    $st = lb_db()->prepare('INSERT INTO login_attempts (ip, email, at) VALUES (?, ?, NOW())');
    $st->execute([lb_client_ip(), $email]);
    if (random_int(1, 20) === 1) {
        lb_db()->exec('DELETE FROM login_attempts WHERE at < (NOW() - INTERVAL 1 DAY)');
    }
}

function lb_throttle_clear(string $email): void
{
    $st = lb_db()->prepare('DELETE FROM login_attempts WHERE ip = ? AND email = ?');
    $st->execute([lb_client_ip(), $email]);
}

function lb_register_limit(): void
{
    $ip = lb_client_ip();
    $st = lb_db()->prepare(
        'SELECT COUNT(*) FROM register_attempts '
        . 'WHERE ip = ? AND at > (NOW() - INTERVAL ' . LB_REGISTER_WINDOW . ' SECOND)'
    );
    $st->execute([$ip]);
    if ((int)$st->fetchColumn() >= LB_MAX_REGISTERS) {
        lb_fail('注册尝试过于频繁，请稍后再试', 429, 'rate_limited');
    }
    $ins = lb_db()->prepare('INSERT INTO register_attempts (ip, at) VALUES (?, NOW())');
    $ins->execute([$ip]);
    if (random_int(1, 10) === 1) {
        lb_db()->exec('DELETE FROM register_attempts WHERE at < (NOW() - INTERVAL 2 DAY)');
    }
}
