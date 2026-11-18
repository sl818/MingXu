<?php
declare(strict_types=1);

if (PHP_SAPI !== 'cli') {
    http_response_code(404);
    exit;
}

define('LIFEBOARD_API', true);
require __DIR__ . '/../api/bootstrap.php';

$args = array_slice($argv, 1);
$update = false;
$admin = false;
while (isset($args[0]) && str_starts_with((string)$args[0], '--')) {
    if ($args[0] === '--update') {
        $update = true;
    } elseif ($args[0] === '--admin') {
        $admin = true;
    } else {
        fwrite(STDERR, "未知参数：{$args[0]}\n");
        exit(1);
    }
    array_shift($args);
}

$email = strtolower(trim((string)($args[0] ?? '')));
$password = (string)($args[1] ?? '');
if ($password === '') {
    $password = (string)(getenv('LB_PASSWORD') ?: '');
}

if ($password === '') {
    fwrite(STDERR, "密码: ");
    $line = fgets(STDIN);
    $password = $line === false ? '' : trim($line);
    fwrite(STDERR, "\n");
}

if (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
    fwrite(STDERR, "用法: php tools/create_user.php [--admin] [--update] 邮箱 密码\n");
    exit(1);
}
if (lb_strlen($password) < 8 || strlen($password) > 200) {
    fwrite(STDERR, "密码需为 8–200 位。\n");
    exit(1);
}

try {
    $pdo = lb_db();
    $st = $pdo->prepare('SELECT id FROM users WHERE email = ? LIMIT 1');
    $st->execute([$email]);
    $id = $st->fetchColumn();

    if ($id && !$update) {
        fwrite(STDERR, "用户已存在。如需重置密码，加 --update 再执行。\n");
        exit(1);
    }

    $hash = password_hash($password, PASSWORD_DEFAULT);
    if (!is_string($hash) || $hash === '') {
        throw new RuntimeException('密码哈希失败');
    }
    if ($id) {
        $sql = 'UPDATE users SET password_hash = ?, session_epoch = session_epoch + 1'
            . ($admin ? ', is_admin = 1' : '') . ' WHERE id = ?';
        $up = $pdo->prepare($sql);
        $up->execute([$hash, $id]);
        echo "已更新密码" . ($admin ? "，并设为管理员" : '') . "：{$email}\n";
    } else {
        $ins = $pdo->prepare(
            'INSERT INTO users (email, password_hash, display_name, is_admin, status, session_epoch) '
            . 'VALUES (?, ?, ?, ?, \'active\', 0)'
        );
        $ins->execute([$email, $hash, $admin ? '管理员' : '', $admin ? 1 : 0]);
        echo "已创建" . ($admin ? '管理员' : '用户') . "：{$email}\n";
    }
} catch (Throwable $e) {
    fwrite(STDERR, "失败：" . $e->getMessage() . "\n");
    exit(1);
}
