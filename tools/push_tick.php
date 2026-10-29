<?php
/**
 * 定时任务：每分钟跑一次，把「这一分钟该提醒的」推到企业微信。
 *
 * 宝塔「计划任务」里添加（任务类型选 Shell 脚本，周期 1 分钟）：
 *   cd /www/wwwroot/todo && /www/server/php/81/bin/php tools/push_tick.php
 *
 * 常用参数：
 *   --dry          只打印要发什么，不写库也不真发
 *   --at 08:00     假装现在是 08:00（排查「为什么这条没发」时用）
 *   -v             把跳过的也打出来
 *
 * 真正的逻辑在 api/push.php 的 lb_push_tick_run() 里，这里只负责连库、解析参数、打印。
 * 分开是为了那部分能用假发送器做穷举测试。
 */

define('LIFEBOARD_API', 1);

if (PHP_SAPI !== 'cli') {
    http_response_code(404);
    exit;
}

require __DIR__ . '/../api/bootstrap.php';
require __DIR__ . '/../api/push.php';

$argvList = array_slice($argv, 1);
$dry = in_array('--dry', $argvList, true);
$verbose = $dry || in_array('-v', $argvList, true);

/* --at HH:MM 覆盖当前时刻，日期仍取今天。测试和排查用 */
$at = null;
$i = array_search('--at', $argvList, true);
if ($i !== false && isset($argvList[$i + 1])) {
    $at = (string)$argvList[$i + 1];
}

$tz = lb_ics_tz();
$now = new DateTimeImmutable('now', $tz);
$date = $now->format('Y-m-d');
$hm = $now->format('H:i');
if ($at !== null) {
    if (!preg_match('/^([01]\d|2[0-3]):[0-5]\d$/', $at)) {
        fwrite(STDERR, '--at 的格式应该是 HH:MM，例如 --at 08:00' . PHP_EOL);
        exit(2);
    }
    $hm = $at;
}

try {
    $pdo = lb_db();
    $r = lb_push_tick_run($pdo, $date, $hm, 'lb_push_send', $dry, 3);
} catch (PDOException $e) {
    fwrite(STDERR, '数据库出错：' . $e->getMessage() . PHP_EOL);
    fwrite(STDERR, '如果提示 push_sent 表不存在，先执行 db/migrations/2026-10-29_push.sql' . PHP_EOL);
    exit(1);
}

if ($verbose) {
    foreach ($r['items'] as $it) {
        $body = str_replace("\n", ' / ', $it['text']);
        if ($it['ok']) {
            echo '  ' . ($dry ? '[预演] ' : '✓ ') . $it['time'] . ' ' . $it['kind']
                . ' → ' . $body . PHP_EOL;
        } else {
            fwrite(STDERR, '  ✗ ' . $it['time'] . ' ' . $it['kind'] . ' → ' . $body
                . '（' . ($it['why'] ?? '') . '）' . PHP_EOL);
        }
    }
}

/* 没开 -v 时，失败也必须让人看见——否则 cron 日志里会一片安静 */
if (!$verbose && $r['failed'] > 0) {
    foreach ($r['items'] as $it) {
        if (!$it['ok']) {
            fwrite(STDERR, '推送失败 ' . $it['time'] . ' ' . $it['kind']
                . '：' . ($it['why'] ?? '') . PHP_EOL);
        }
    }
}

echo sprintf(
    '[%s] 发出 %d 条，已发过跳过 %d 条，失败 %d 条' . PHP_EOL,
    $hm,
    $r['sent'],
    $r['skipped'],
    $r['failed']
);

exit($r['failed'] > 0 ? 1 : 0);
