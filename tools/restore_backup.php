<?php
/* 从每日快照恢复 boards。只能在命令行运行。
 *
 * 用法（在站点根目录下）：
 *   php tools/restore_backup.php backup/2026-10-29.php          预演，只看不写
 *   php tools/restore_backup.php ../backups/2026-10-29.php --yes 真的写回数据库
 *
 * 恢复会覆盖该用户当前的 boards 数据，但不会动 users / board_revisions。
 * 写回时 rev 会 +1，所以已经打开的页面刷新后拿到的是恢复后的数据。
 */
declare(strict_types=1);

define('LIFEBOARD_API', true);

if (PHP_SAPI !== 'cli') {
    http_response_code(404);
    exit;
}

$root = dirname(__DIR__);
require $root . '/api/bootstrap.php';
require $root . '/api/backup.php';

function lb_say(string $line): void
{
    fwrite(STDOUT, $line . "\n");
}

$args = array_slice($argv, 1);
$force = in_array('--yes', $args, true);
$rest = array_values(array_filter($args, static function ($a) {
    return $a !== '--yes';
}));

if (!$rest) {
    fwrite(STDERR, "用法: php tools/restore_backup.php <备份文件> [--yes]\n");
    exit(2);
}

$file = (string)$rest[0];
if (!is_file($file)) {
    $alt = $root . '/' . ltrim($file, '/');
    if (is_file($alt)) {
        $file = $alt;
    }
}
if (!is_file($file)) {
    fwrite(STDERR, "找不到备份文件: " . $file . "\n");
    exit(2);
}

$payload = lb_backup_read($file);
if (!is_array($payload) || !isset($payload['boards']) || !is_array($payload['boards'])) {
    fwrite(STDERR, "这个文件读不出看板数据，可能不是备份文件、或者被截断了。\n");
    exit(2);
}

lb_say('备份时间：' . (string)($payload['at'] ?? '（未记录）'));
lb_say('包含用户：' . count($payload['boards']) . ' 个');

$pdo = lb_db();
$check = $pdo->prepare('SELECT id FROM users WHERE id = ? LIMIT 1');
$now = (int)round(microtime(true) * 1000);
$ready = 0;

foreach ($payload['boards'] as $uid => $item) {
    $uid = (int)$uid;
    if ($uid <= 0 || !isset($item['data']) || !is_array($item['data'])) {
        lb_say(sprintf('  用户 %s：数据不完整，跳过', (string)$uid));
        continue;
    }
    $check->execute([$uid]);
    $exists = (bool)$check->fetchColumn();
    if ($exists) {
        $ready++;
    }
    lb_say(sprintf(
        '  用户 %d：rev %d，%s',
        $uid,
        (int)($item['rev'] ?? 0),
        $exists ? '将覆盖写入' : '账号已不存在，跳过'
    ));
}

if ($ready === 0) {
    lb_say('没有可恢复的记录。');
    exit(1);
}

if (!$force) {
    lb_say('');
    lb_say('以上是预演，数据库没动。确认无误后加 --yes 重跑一次。');
    exit(0);
}

$pdo->beginTransaction();
try {
    $up = $pdo->prepare('UPDATE boards SET data = ?, rev = rev + 1, updated_at = ? WHERE user_id = ?');
    $ins = $pdo->prepare('INSERT INTO boards (user_id, data, rev, updated_at) VALUES (?, ?, 1, ?)');
    $done = 0;
    foreach ($payload['boards'] as $uid => $item) {
        $uid = (int)$uid;
        if ($uid <= 0 || !isset($item['data']) || !is_array($item['data'])) {
            continue;
        }
        $check->execute([$uid]);
        if (!$check->fetchColumn()) {
            continue;
        }
        $json = json_encode($item['data'], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
        if ($json === false) {
            continue;
        }
        $up->execute([$json, $now, $uid]);
        if ($up->rowCount() === 0) {
            $ins->execute([$json, $now, $uid]);
        }
        $done++;
    }
    $pdo->commit();
    lb_say('');
    lb_say('已写回 ' . $done . ' 个用户的看板。刷新页面就能看到。');
} catch (Throwable $e) {
    if ($pdo->inTransaction()) {
        $pdo->rollBack();
    }
    fwrite(STDERR, '恢复失败：' . $e->getMessage() . "\n");
    exit(1);
}
