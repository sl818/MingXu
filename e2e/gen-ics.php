<?php
/* 按给定 state JSON 和固定时刻生成 iCalendar，供等价性比对使用。
 * 用法：php e2e/gen-ics.php <state.json> <Y-m-d H:i:s> <out.ics>
 */
declare(strict_types=1);

define('LIFEBOARD_API', true);
require __DIR__ . '/../api/ics.php';

if ($argc < 4) {
    fwrite(STDERR, "用法: php gen-ics.php <state.json> <Y-m-d H:i:s> <out.ics>\n");
    exit(2);
}

$state = json_decode((string)file_get_contents($argv[1]), true);
if (!is_array($state)) {
    fwrite(STDERR, "state.json 解析失败\n");
    exit(2);
}

$now = new DateTimeImmutable($argv[2], new DateTimeZone('Asia/Shanghai'));
$built = lb_ics_build($state, $now);
file_put_contents($argv[3], $built['text']);
echo $built['count'], PHP_EOL;
