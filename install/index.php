<?php
declare(strict_types=1);

session_name('LIFEBOARD_INSTALL');
$https = (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off')
    || (($_SERVER['HTTP_X_FORWARDED_PROTO'] ?? '') === 'https');
session_set_cookie_params([
    'lifetime' => 0,
    'path' => '/',
    'domain' => '',
    'secure' => $https,
    'httponly' => true,
    'samesite' => 'Lax',
]);
session_start();

$ROOT = dirname(__DIR__);
$LOCK = $ROOT . '/install.lock';
$CONFIG = $ROOT . '/api/config.php';
$SCHEMA = $ROOT . '/db/schema.sql';

header('X-Frame-Options: DENY');
header('X-Content-Type-Options: nosniff');
header('X-Robots-Tag: noindex');
header('Cache-Control: no-store');

function h($value): string
{
    return htmlspecialchars((string)$value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}

function slen(string $value): int
{
    return function_exists('mb_strlen') ? (int)mb_strlen($value, 'UTF-8') : strlen($value);
}

function post_str(string $key, string $default = ''): string
{
    return isset($_POST[$key]) ? trim((string)$_POST[$key]) : $default;
}

function post_raw(string $key): string
{
    return isset($_POST[$key]) ? (string)$_POST[$key] : '';
}

function csrf_token(): string
{
    if (empty($_SESSION['csrf']) || !is_string($_SESSION['csrf'])) {
        $_SESSION['csrf'] = bin2hex(random_bytes(32));
    }
    return $_SESSION['csrf'];
}

function csrf_check(): void
{
    $sent = $_POST['csrf'] ?? '';
    $known = $_SESSION['csrf'] ?? '';
    if (!is_string($sent) || !is_string($known) || $known === '' || !hash_equals($known, $sent)) {
        http_response_code(400);
        exit('会话校验失败，请刷新页面后重试。');
    }
}

function redirect(string $url): void
{
    header('Location: ' . $url);
    exit;
}

function db_connect(array $db): PDO
{
    $dsn = 'mysql:host=' . $db['host'] . ';port=' . (int)$db['port']
        . ';dbname=' . $db['name'] . ';charset=utf8mb4';
    return new PDO($dsn, $db['user'], $db['pass'], [
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        PDO::ATTR_EMULATE_PREPARES => false,
    ]);
}

function db_is_empty(PDO $pdo): bool
{
    $tables = $pdo->query('SHOW TABLES')->fetchAll(PDO::FETCH_COLUMN);
    return count($tables) === 0;
}

function create_tables(PDO $pdo, string $schemaFile): void
{
    $sql = file_get_contents($schemaFile);
    if ($sql === false) {
        throw new RuntimeException('无法读取 db/schema.sql');
    }
    $sql = preg_replace('/^\s*--.*$/m', '', $sql);
    $sql = preg_replace('#/\*.*?\*/#s', '', $sql);
    $parts = array_filter(array_map('trim', explode(';', (string)$sql)));
    foreach ($parts as $statement) {
        if ($statement !== '') {
            $pdo->exec($statement);
        }
    }
}

function config_is_fresh(string $configFile): bool
{
    if (!is_file($configFile)) {
        return true;
    }
    $raw = file_get_contents($configFile);
    if ($raw === false) {
        return false;
    }
    return strpos($raw, 'CHANGE_ME') !== false;
}

function write_config(string $configFile, array $db): string
{
    $appKey = bin2hex(random_bytes(32));
    $config = [
        'db' => [
            'host' => $db['host'],
            'port' => (int)$db['port'],
            'name' => $db['name'],
            'user' => $db['user'],
            'pass' => $db['pass'],
            'charset' => 'utf8mb4',
        ],
        'session_name' => 'LIFEBOARD_SID',
        'max_bytes' => 4 * 1024 * 1024,
        'cookie_secure' => 'auto',
        'app_key' => $appKey,
    ];
    $php = "<?php\nif (!defined('LIFEBOARD_API')) { http_response_code(404); exit; }\n\nreturn "
        . var_export($config, true) . ";\n";

    $dir = dirname($configFile);
    if (!is_dir($dir) || !is_writable($dir)) {
        throw new RuntimeException('api/ 目录不可写，请先 chown -R www:www 并检查权限');
    }
    $tmp = $configFile . '.tmp-' . bin2hex(random_bytes(4));
    $bytes = file_put_contents($tmp, $php, LOCK_EX);
    if ($bytes === false || $bytes < 20) {
        @unlink($tmp);
        throw new RuntimeException('写入 api/config.php 失败');
    }
    @chmod($tmp, 0640);
    if (!@rename($tmp, $configFile)) {
        @unlink($tmp);
        throw new RuntimeException('替换 api/config.php 失败');
    }
    return $appKey;
}

function install_lock(string $lockFile): void
{
    $bytes = file_put_contents($lockFile, 'installed_at=' . date('c') . "\n", LOCK_EX);
    if ($bytes === false) {
        throw new RuntimeException('写入 install.lock 失败');
    }
    @chmod($lockFile, 0644);
}

function env_checks(string $root, string $configFile, string $schemaFile): array
{
    $configWritable = is_file($configFile)
        ? is_writable($configFile)
        : is_writable(dirname($configFile));
    return [
        ['PHP 8.1+', version_compare(PHP_VERSION, '8.1.0', '>='), PHP_VERSION],
        ['PDO MySQL', extension_loaded('pdo_mysql'), extension_loaded('pdo_mysql') ? '已安装' : '未安装'],
        ['Session', function_exists('session_start'), '可用'],
        ['JSON', function_exists('json_encode'), '可用'],
        ['db/schema.sql', is_readable($schemaFile), is_readable($schemaFile) ? '可读' : '不可读'],
        ['api/ 目录可写', is_writable(dirname($configFile)), is_writable(dirname($configFile)) ? '可写' : '不可写'],
        ['api/config.php 可写', $configWritable, $configWritable ? '可写' : '不可写'],
        ['站点根目录可写', is_writable($root), is_writable($root) ? '可写' : '不可写'],
    ];
}

function page(string $title, string $body, int $step = 0): void
{
    ?><!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title><?= h($title) ?> · 明序安装</title>
<style>
:root{--bg:#f3eee4;--surface:#fffdf8;--line:#e3dac8;--line2:#cfc2aa;--text:#1c2621;--muted:#6f7468;--accent:#1f6b57;--accent2:#154b3e;--bad:#b0473d;--good:#2f7d5c;--gold:#b8893b}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(900px 420px at 90% -10%,#fbf7ef,rgba(251,247,239,0) 60%),var(--bg);color:var(--text);font:14px/1.7 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;padding:36px 16px 70px}
.wrap{max-width:760px;margin:0 auto}.brand{display:flex;align-items:center;gap:10px;margin:0 4px 18px;font-weight:700;font-size:17px}.brand small{font-weight:400;color:var(--muted);font-size:11px;letter-spacing:.12em}
.card{background:var(--surface);border:1px solid var(--line);border-radius:18px;padding:26px 26px 24px;box-shadow:0 24px 50px -38px rgba(30,40,30,.5)}
h1{font-size:20px;margin:0 0 6px;letter-spacing:-.01em}h2{font-size:15px;margin:22px 0 10px}p{margin:8px 0;color:var(--muted);font-size:13px}
.steps{display:flex;gap:8px;margin:0 0 14px;flex-wrap:wrap}.steps span{font-size:11px;color:var(--muted);border:1px solid var(--line);padding:3px 10px;border-radius:99px;background:var(--surface)}.steps span.on{border-color:var(--accent);color:var(--accent);font-weight:600}
.checks{display:flex;flex-direction:column;gap:8px;margin:16px 0}.check{display:flex;align-items:center;justify-content:space-between;gap:12px;border-bottom:1px dashed var(--line);padding:8px 2px;font-size:13px}.check b{font-weight:600;color:var(--text)}.ok{color:var(--good);font-weight:600}.no{color:var(--bad);font-weight:600}
.field{margin:12px 0}.field label{display:block;font-size:12px;color:var(--muted);margin-bottom:5px}.field input{width:100%;border:1px solid var(--line);background:#fbf7ee;border-radius:10px;padding:10px 12px;font:inherit;color:var(--text)}.field input:focus{outline:none;border-color:var(--accent);box-shadow:0 0 0 3px #e1eee7}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:0 14px}.btn{display:inline-flex;align-items:center;justify-content:center;gap:6px;background:var(--accent);border:1px solid var(--accent);color:#fffdf6;border-radius:10px;padding:10px 18px;font-size:13px;font-weight:600;text-decoration:none;cursor:pointer}.btn:hover{background:var(--accent2)}.btn.ghost{background:transparent;color:var(--muted);border-color:var(--line)}.actions{display:flex;gap:10px;align-items:center;margin-top:22px;flex-wrap:wrap}
.err{background:#f8e9e7;border:1px solid #e9c9c4;color:var(--bad);padding:10px 13px;border-radius:10px;font-size:12.5px;margin:10px 0}.err ul{margin:4px 0 0 18px;padding:0}.hint{font-size:11.5px;color:var(--muted)}code{background:#f3ede1;border:1px solid var(--line);border-radius:6px;padding:2px 7px;font-size:12.5px;color:var(--accent2)}.done{font-size:15px;color:var(--good);font-weight:600}.footer{text-align:center;color:var(--muted);font-size:11px;margin-top:18px}
@media(max-width:620px){.grid{grid-template-columns:1fr}.card{padding:20px 17px}}
</style>
</head>
<body>
<div class="wrap">
  <div class="brand">明序 <small>INSTALL</small></div>
  <?php if ($step > 0): ?>
  <div class="steps">
    <span class="<?= $step === 1 ? 'on' : '' ?>">1 环境检查</span>
    <span class="<?= $step === 2 ? 'on' : '' ?>">2 数据库</span>
    <span class="<?= $step === 3 ? 'on' : '' ?>">3 管理员</span>
    <span class="<?= $step === 4 ? 'on' : '' ?>">4 完成</span>
  </div>
  <?php endif; ?>
  <div class="card"><?= $body ?></div>
  <div class="footer">安装完成后请删除 install/ 目录 · 数据只存放在你的服务器</div>
</div>
</body>
</html><?php
}

/* 已安装：直接拒绝 */
if (is_file($LOCK)) {
    http_response_code(403);
    page('已经安装', '<h1>已经安装过了</h1><p>检测到 <code>install.lock</code>，安装向导已锁定。</p><p>如果确实要重装，请先删除 <code>install.lock</code> 和 <code>api/config.php</code>，并清空数据库。</p><div class="actions"><a class="btn" href="/">进入应用</a></div>');
    exit;
}

$step = max(1, min(4, (int)($_GET['step'] ?? 1)));
$errors = [];
$checks = env_checks($ROOT, $CONFIG, $SCHEMA);
$envOk = true;
foreach ($checks as $check) {
    if (!$check[1]) {
        $envOk = false;
    }
}
$configFresh = config_is_fresh($CONFIG);
if (!$configFresh) {
    $errors[] = '检测到 api/config.php 已有真实数据库配置。若要重装，请先删除 api/config.php 并清空数据库。';
    $step = 1;
}

/* ---------- 第 2 步：数据库 ---------- */
if ($step === 2 && $_SERVER['REQUEST_METHOD'] === 'POST' && post_str('action') === 'db') {
    csrf_check();
    $db = [
        'host' => post_str('host', '127.0.0.1'),
        'port' => (int)post_str('port', '3306'),
        'name' => post_str('name'),
        'user' => post_str('user'),
        'pass' => post_raw('pass'),
    ];
    if (!preg_match('/^[A-Za-z0-9_.:-]+$/', $db['host'])) {
        $errors[] = '数据库地址格式不正确。';
    }
    if ($db['port'] < 1 || $db['port'] > 65535) {
        $errors[] = '端口应在 1–65535 之间。';
    }
    if (!preg_match('/^[A-Za-z0-9_]+$/', $db['name'])) {
        $errors[] = '数据库名只能包含字母、数字和下划线。';
    }
    if (!preg_match('/^[A-Za-z0-9_]+$/', $db['user'])) {
        $errors[] = '数据库用户名只能包含字母、数字和下划线。';
    }
    if ($db['pass'] === '') {
        $errors[] = '请填写数据库密码。';
    }

    if (!$errors) {
        try {
            $pdo = db_connect($db);
            if (!db_is_empty($pdo)) {
                throw new RuntimeException('这个数据库里已经有表了。请先在宝塔新建一个空数据库，再回来安装。');
            }
            create_tables($pdo, $SCHEMA);
            $_SESSION['db'] = $db;
            unset($_SESSION['db_form']);
            redirect('?step=3');
        } catch (Throwable $e) {
            $errors[] = '数据库连接或建表失败：' . $e->getMessage();
            $_SESSION['db_form'] = ['host' => $db['host'], 'port' => $db['port'], 'name' => $db['name'], 'user' => $db['user']];
        }
    }
}

/* ---------- 第 3 步：管理员 ---------- */
if ($step === 3 && $_SERVER['REQUEST_METHOD'] === 'POST' && post_str('action') === 'admin') {
    csrf_check();
    $db = $_SESSION['db'] ?? null;
    if (!is_array($db)) {
        redirect('?step=2');
    }
    $email = strtolower(post_str('email'));
    $display = post_str('display_name', '管理员');
    $password = post_raw('password');
    $confirm = post_raw('password_confirm');

    if (!filter_var($email, FILTER_VALIDATE_EMAIL) || strlen($email) > 190) {
        $errors[] = '请输入有效的邮箱地址（它只是登录名，不会发邮件）。';
    }
    if (slen($display) > 40) {
        $errors[] = '显示名称最多 40 个字符。';
    }
    if (slen($password) < 8 || strlen($password) > 200) {
        $errors[] = '管理员密码需为 8–200 位。';
    }
    if ($password !== $confirm) {
        $errors[] = '两次输入的密码不一致。';
    }

    if (!$errors) {
        try {
            $pdo = db_connect($db);
            $invite = strtoupper(substr(bin2hex(random_bytes(6)), 0, 8));

            $pdo->beginTransaction();
            $st = $pdo->prepare('SELECT id FROM users WHERE email = ? LIMIT 1');
            $st->execute([$email]);
            if ($st->fetchColumn()) {
                throw new RuntimeException('这个邮箱已经存在。');
            }
            $ins = $pdo->prepare(
                'INSERT INTO users (email, password_hash, display_name, is_admin, status, session_epoch, created_at) '
                . 'VALUES (?, ?, ?, 1, \'active\', 0, NOW())'
            );
            $hash = password_hash($password, PASSWORD_DEFAULT);
            if (!is_string($hash) || $hash === '') {
                throw new RuntimeException('管理员密码哈希失败');
            }
            $ins->execute([$email, $hash, $display === '' ? '管理员' : $display]);

            $setting = $pdo->prepare('INSERT INTO app_settings (k, v) VALUES (?, ?) ON DUPLICATE KEY UPDATE v = VALUES(v)');
            $setting->execute(['registration_open', '1']);
            $setting->execute(['invite_code', $invite]);
            $setting->execute(['site_name', '明序']);
            $pdo->commit();

            write_config($CONFIG, $db);
            install_lock($LOCK);

            $_SESSION['install_done'] = [
                'email' => $email,
                'invite' => $invite,
            ];
            unset($_SESSION['db'], $_SESSION['db_form']);
            $step = 4;
        } catch (Throwable $e) {
            if (isset($pdo) && $pdo instanceof PDO && $pdo->inTransaction()) {
                $pdo->rollBack();
            }
            $errors[] = '创建管理员或写入配置失败：' . $e->getMessage();
        }
    }
}

/* ---------- 第 4 步：完成 ---------- */
if ($step === 4) {
    $done = $_SESSION['install_done'] ?? null;
    if (!is_array($done)) {
        redirect('?step=1');
    }
    $body = '<h1>安装完成</h1>' .
        '<p class="done">数据库、管理员和邀请码都准备好了。</p>' .
        '<div class="checks">' .
        '<div class="check"><b>管理员邮箱</b><span>' . h($done['email']) . '</span></div>' .
        '<div class="check"><b>邀请码</b><span><code>' . h($done['invite']) . '</code></span></div>' .
        '</div>' .
        '<p>把邀请码发给要注册的人；他们打开首页 → 登录 → 注册，填写邀请码即可。管理员登录后，在「设置 → 云同步 → 用户管理」里可以重置密码、停用账号、修改邀请码和注册开关。</p>' .
        '<div class="err"><b>重要：</b>请立即删除服务器上的 <code>install/</code> 目录，或至少确认它已经无法再次执行。安装锁已生成，重复访问会被拒绝。</div>' .
        '<div class="actions"><a class="btn" href="/">进入应用</a></div>';
    page('安装完成', $body, 4);
    exit;
}

/* ---------- 第 3 步页面 ---------- */
if ($step === 3) {
    $db = $_SESSION['db'] ?? null;
    if (!is_array($db)) {
        redirect('?step=2');
    }
    $err = '';
    if ($errors) {
        $err = '<div class="err"><ul>' . implode('', array_map(fn($x) => '<li>' . h($x) . '</li>', $errors)) . '</ul></div>';
    }
    $email = h(post_str('email'));
    $display = h(post_str('display_name', '管理员'));
    $body = '<h1>创建管理员</h1>' .
        '<p>数据库：<code>' . h($db['name']) . '</code> · 用户：<code>' . h($db['user']) . '</code></p>' .
        $err .
        '<form method="post" action="?step=3" autocomplete="off">' .
        '<input type="hidden" name="csrf" value="' . h(csrf_token()) . '">' .
        '<input type="hidden" name="action" value="admin">' .
        '<div class="field"><label>管理员邮箱（登录名）</label><input name="email" type="email" required maxlength="190" value="' . $email . '" placeholder="you@example.com"></div>' .
        '<div class="field"><label>显示名称</label><input name="display_name" maxlength="40" value="' . $display . '" placeholder="管理员"></div>' .
        '<div class="grid">' .
        '<div class="field"><label>密码（至少 8 位）</label><input name="password" type="password" required minlength="8" maxlength="200" autocomplete="new-password"></div>' .
        '<div class="field"><label>确认密码</label><input name="password_confirm" type="password" required minlength="8" maxlength="200" autocomplete="new-password"></div>' .
        '</div>' .
        '<p class="hint">这个账号是第一个管理员；注册开关和邀请码会在完成后生成。</p>' .
        '<div class="actions"><a class="btn ghost" href="?step=2">上一步</a><button class="btn" type="submit">完成安装</button></div>' .
        '</form>';
    page('创建管理员', $body, 3);
    exit;
}

/* ---------- 第 2 步页面 ---------- */
if ($step === 2) {
    $form = $_SESSION['db_form'] ?? ['host' => '127.0.0.1', 'port' => '3306', 'name' => 'lifeboard', 'user' => 'lifeboard'];
    $err = '';
    if ($errors) {
        $err = '<div class="err"><ul>' . implode('', array_map(fn($x) => '<li>' . h($x) . '</li>', $errors)) . '</ul></div>';
    }
    $body = '<h1>连接数据库</h1>' .
        '<p>请先在宝塔创建一个<strong>空数据库</strong>（字符集 utf8mb4），这里只负责建表，不会创建数据库。</p>' .
        $err .
        '<form method="post" action="?step=2" autocomplete="off">' .
        '<input type="hidden" name="csrf" value="' . h(csrf_token()) . '">' .
        '<input type="hidden" name="action" value="db">' .
        '<div class="grid">' .
        '<div class="field"><label>数据库地址</label><input name="host" required value="' . h($form['host']) . '" placeholder="127.0.0.1"></div>' .
        '<div class="field"><label>端口</label><input name="port" type="number" min="1" max="65535" required value="' . h($form['port']) . '"></div>' .
        '<div class="field"><label>数据库名</label><input name="name" required value="' . h($form['name']) . '" placeholder="lifeboard"></div>' .
        '<div class="field"><label>数据库用户名</label><input name="user" required value="' . h($form['user']) . '" placeholder="lifeboard"></div>' .
        '</div>' .
        '<div class="field"><label>数据库密码</label><input name="pass" type="password" required autocomplete="new-password"></div>' .
        '<p class="hint">这些账号只用于连接你刚建的空库；安装器会测试连接并创建 users / boards 等表。</p>' .
        '<div class="actions"><a class="btn ghost" href="?step=1">上一步</a><button class="btn" type="submit">测试连接并建表</button></div>' .
        '</form>';
    page('连接数据库', $body, 2);
    exit;
}

/* ---------- 第 1 步页面 ---------- */
$rows = '';
foreach ($checks as $check) {
    $rows .= '<div class="check"><b>' . h($check[0]) . '</b><span class="' . ($check[1] ? 'ok' : 'no') . '">'
        . ($check[1] ? '✓ ' : '✕ ') . h($check[2]) . '</span></div>';
}
$err = '';
if ($errors) {
    $err = '<div class="err"><ul>' . implode('', array_map(fn($x) => '<li>' . h($x) . '</li>', $errors)) . '</ul></div>';
}
$body = '<h1>准备安装</h1>' .
    '<p>安装向导会检查环境、连接一个空数据库、建表，并创建第一个管理员。</p>' .
    $err .
    '<div class="checks">' . $rows . '</div>' .
    ($envOk && $configFresh
        ? '<div class="actions"><a class="btn" href="?step=2">下一步：连接数据库</a></div>'
        : '<p class="err">请先修复上面的红项，或删除旧的 api/config.php 后再继续。</p>');
page('环境检查', $body, 1);
