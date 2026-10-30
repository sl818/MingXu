<?php
/**
 * 修复推送去重：补建 push_sent 表的唯一索引。
 *
 * 推送的「每条只发一次」靠这张表的唯一索引 (user_id, slot_key) + INSERT IGNORE 实现。
 * 线上曾出现唯一索引没建上的情况，导致定时任务每分钟都重复发同一条提醒。
 * 这个脚本做三件事，全部幂等，可重复执行：
 *   1. 检测唯一索引 uq_push_sent 是否存在
 *   2. 若不存在：先清掉已有的重复记录，再补建唯一索引
 *   3. 清理 7 天前的旧记录
 *
 * 用法（在服务器上跑）：
 *   php tools/push_fix.php
 */

define('LIFEBOARD_API', 1);

if (PHP_SAPI !== 'cli') {
    http_response_code(404);
    exit;
}

require __DIR__ . '/../api/bootstrap.php';

try {
    $pdo = lb_db();
} catch (PDOException $e) {
    fwrite(STDERR, '数据库连接失败：' . $e->getMessage() . PHP_EOL);
    exit(1);
}

$driver = $pdo->getAttribute(PDO::ATTR_DRIVER_NAME);

/* 1. 检测唯一索引是否存在 */
$hasUnique = false;
if ($driver === 'mysql') {
    foreach ($pdo->query("SHOW INDEX FROM push_sent")->fetchAll() as $row) {
        if (($row['Key_name'] ?? '') === 'uq_push_sent') {
            $hasUnique = true;
            break;
        }
    }
} else {
    foreach ($pdo->query("PRAGMA index_list('push_sent')")->fetchAll() as $row) {
        if (($row['name'] ?? '') === 'uq_push_sent') {
            $hasUnique = true;
            break;
        }
    }
}

if ($hasUnique) {
    echo '唯一索引 uq_push_sent 已存在，无需修复。' . PHP_EOL;
} else {
    echo '未找到唯一索引 uq_push_sent，开始修复…' . PHP_EOL;

    /* 2. 清理重复：每个 (user_id, slot_key) 只保留 id 最小的一条。
       派生表写法和 MySQL / SQLite 都兼容。 */
    $dupes = $pdo->exec(
        "DELETE FROM push_sent WHERE id NOT IN ("
        . "SELECT keep_id FROM ("
        . "SELECT MIN(id) AS keep_id FROM push_sent GROUP BY user_id, slot_key"
        . ") AS keep)"
    );
    echo '清理重复记录：' . (int)$dupes . ' 条' . PHP_EOL;

    /* 3. 补建唯一索引。CREATE UNIQUE INDEX 语法 MySQL / SQLite 通用。 */
    $pdo->exec('CREATE UNIQUE INDEX uq_push_sent ON push_sent (user_id, slot_key)');
    echo '已补建唯一索引 uq_push_sent。' . PHP_EOL;
}

/* 4. 清理 7 天前的旧记录（发送记录只留 7 天） */
if ($driver === 'mysql') {
    $old = $pdo->exec("DELETE FROM push_sent WHERE sent_at < (NOW() - INTERVAL 7 DAY)");
} else {
    $old = $pdo->exec("DELETE FROM push_sent WHERE sent_at < datetime('now', '-7 days')");
}
echo '清理 7 天前旧记录：' . (int)$old . ' 条' . PHP_EOL;

/* 5. 复核：再跑一次检测，确认索引已就位 */
$ok = false;
if ($driver === 'mysql') {
    foreach ($pdo->query("SHOW INDEX FROM push_sent")->fetchAll() as $row) {
        if (($row['Key_name'] ?? '') === 'uq_push_sent') {
            $ok = true;
            break;
        }
    }
} else {
    foreach ($pdo->query("PRAGMA index_list('push_sent')")->fetchAll() as $row) {
        if (($row['name'] ?? '') === 'uq_push_sent') {
            $ok = true;
            break;
        }
    }
}

echo $ok ? '修复完成，唯一索引已就位。' : '仍有问题：唯一索引未建成功。' . PHP_EOL;
exit($ok ? 0 : 1);
