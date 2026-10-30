<?php
/* 服务端日历订阅的单元验证：不连数据库，只测「把 state 转成 iCalendar」这段。
 * 运行：php e2e/test-ics.php
 */
declare(strict_types=1);

define('LIFEBOARD_API', true);
require __DIR__ . '/../api/ics.php';

$pass = 0;
$fails = [];

function chk(string $name, bool $ok, string $detail = ''): void
{
    global $pass, $fails;
    if ($ok) {
        $pass++;
        echo "  \u{2713} {$name}\n";
    } else {
        $fails[] = $name . ($detail !== '' ? ' << ' . $detail : '');
        echo "  \u{2717} {$name}" . ($detail !== '' ? "  << {$detail}" : '') . "\n";
    }
}

$tz = new DateTimeZone('Asia/Shanghai');
$now = new DateTimeImmutable('2026-10-25 10:00:00', $tz);

$state = [
    'meds' => [
        ['id' => 'm1', 'name' => '阿莫西林', 'status' => 'active', 'courseType' => 'long', 'times' => ['08:00', '20:00'],
         'startDate' => '2026-10-01', 'endDate' => '', 'doseAmount' => 1, 'doseUnit' => '片', 'note' => ''],
        ['id' => 'm2', 'name' => '维生素D', 'status' => 'active', 'courseType' => 'long', 'times' => ['12:00'],
         'startDate' => '2026-10-01', 'endDate' => '', 'doseAmount' => 2, 'doseUnit' => '粒', 'note' => '随餐'],
        ['id' => 'm3', 'name' => '头孢克肟', 'status' => 'active', 'courseType' => 'short', 'times' => ['09:00'],
         'startDate' => '2026-10-20', 'endDate' => '2026-10-30', 'doseAmount' => 1, 'doseUnit' => '片', 'note' => ''],
        // 疗程已经结束，不该进日历
        ['id' => 'm4', 'name' => '过期疗程', 'status' => 'active', 'courseType' => 'short', 'times' => ['09:00'],
         'startDate' => '2026-10-01', 'endDate' => '2026-10-10', 'doseAmount' => 1, 'doseUnit' => '片', 'note' => ''],
        // 已经停药
        ['id' => 'm5', 'name' => '已停药', 'status' => 'stopped', 'courseType' => 'long', 'times' => ['08:00'],
         'startDate' => '2026-10-01', 'endDate' => '', 'doseAmount' => 1, 'doseUnit' => '片', 'note' => ''],
        ['id' => 'm6', 'name' => '没有时间', 'status' => 'active', 'courseType' => 'long', 'times' => [],
         'startDate' => '2026-10-01', 'endDate' => '', 'doseAmount' => 1, 'doseUnit' => '片', 'note' => ''],
        // 备用药（按需服用）：没有固定时刻，不该进日历
        ['id' => 'm7', 'name' => '布洛芬', 'status' => 'active', 'courseType' => 'prn', 'times' => ['08:00'],
         'startDate' => '2026-10-01', 'endDate' => '', 'doseAmount' => 1, 'doseUnit' => '片', 'note' => '疼的时候吃'],
        // 长期药却填了结束日：不该因此停（只有 short 才看 endDate）
        ['id' => 'm8', 'name' => '长期药带结束日', 'status' => 'active', 'courseType' => 'long', 'times' => ['21:00'],
         'startDate' => '2026-10-01', 'endDate' => '2026-10-10', 'doseAmount' => 1, 'doseUnit' => '片', 'note' => ''],
    ],
    'tasks' => [
        ['id' => 't1', 'title' => '每日复盘', 'status' => 'todo', 'due' => '2026-10-25',
         'repeat' => 'daily', 'notifyTime' => '07:30'],
        ['id' => 't2', 'title' => '周报', 'status' => 'todo', 'due' => '2026-10-25',
         'repeat' => 'weekly', 'notifyTime' => '18:00', 'repeatWeekday' => 3],
        ['id' => 't3', 'title' => '交房租', 'status' => 'todo', 'due' => '2026-10-25',
         'repeat' => 'monthly', 'notifyTime' => '10:30', 'repeatDay' => 1],
        ['id' => 't4', 'title' => '三天后体检', 'status' => 'todo', 'due' => '2026-10-28', 'note' => '空腹'],
        // 填了时间块的：日历按开始时间画、按时长定长度（不是通知时间）
        ['id' => 't8', 'title' => '项目评审会', 'status' => 'todo', 'due' => '2026-10-28',
         'notifyTime' => '09:00', 'startTime' => '14:30', 'duration' => 90],
        // 今天 9 点已过，单次任务不再进日历
        ['id' => 't5', 'title' => '今天已过点', 'status' => 'todo', 'due' => '2026-10-25'],
        ['id' => 't6', 'title' => '已完成', 'status' => 'done', 'due' => '2026-10-28'],
        ['id' => 't7', 'title' => '逾期任务', 'status' => 'todo', 'due' => '2026-10-20'],
        // 已取消：日历必须和推送同口径排除，否则「日历还有、手机不响」
        ['id' => 't9', 'title' => '已取消任务', 'status' => 'cancelled', 'due' => '2026-10-28'],
    ],
    'habits' => [
        ['id' => 'h1', 'name' => '478呼吸法', 'icon' => '🌬️', 'suggestTime' => '15:00', 'note' => ''],
        ['id' => 'h2', 'name' => '看书', 'icon' => '📖', 'note' => ''],
        ['id' => 'h3', 'name' => '已归档', 'icon' => 'x', 'suggestTime' => '09:00',
         'archivedAt' => '2026-10-01T00:00:00Z'],
        ['id' => 'h4', 'name' => '戒烟', 'icon' => '🚭', 'type' => 'quit', 'suggestTime' => '09:00'],
    ],
];

$built = lb_ics_build($state, $now);
$text = $built['text'];
$lines = array_values(array_filter(explode("\r\n", $text)));

/* ---------------- 1. 外壳 ---------------- */
echo "\n[1] 外壳\n";
chk('以 BEGIN:VCALENDAR 开头', strpos($text, 'BEGIN:VCALENDAR') === 0);
chk('以 END:VCALENDAR 结尾', str_ends_with(rtrim($text), 'END:VCALENDAR'));
chk('声明了版本', strpos($text, 'VERSION:2.0') !== false);
chk('带 VTIMEZONE', substr_count($text, 'BEGIN:VTIMEZONE') === 1);
chk('时区偏移 +0800', strpos($text, 'TZOFFSETTO:+0800') !== false);
chk('日历名已转义写入', strpos($text, 'X-WR-CALNAME:') !== false);
chk('第一行就是 BEGIN:VCALENDAR（前面没有 BOM 或空行）', strpos($text, 'BEGIN:VCALENDAR') === 0);
chk('全程 CRLF，没有裸 LF', preg_match("/(?<!\r)\n/", $text) === 0);
/* 下面两条是小米日历不认订阅的直接原因，别再改回去 */
chk('不带 METHOD（订阅源不需要，带上会被当成会议邀请）',
    strpos($text, 'METHOD:') === false);
chk('声明了刷新间隔（客户端据此决定多久来拉一次）',
    strpos($text, 'REFRESH-INTERVAL;VALUE=DURATION:PT6H') !== false
    && strpos($text, 'X-PUBLISHED-TTL:PT6H') !== false);

/* ---------------- 2. 事件数量 ---------------- */
echo "\n[2] 事件筛选\n";
$vevents = substr_count($text, 'BEGIN:VEVENT');
chk('总事件数 11', $built['count'] === 11 && $vevents === 11, 'count=' . $built['count'] . ' vevent=' . $vevents);
chk('在吃的药仍是 5 条（新增的时间块用例是待办，不影响药）',
    substr_count($text, 'UID:med-') === 5, (string)substr_count($text, 'UID:med-'));
chk('疗程结束后不进日历', strpos($text, '过期疗程') === false);
chk('停药的不进日历', strpos($text, '已停药') === false);
chk('没有时间的药不进日历', strpos($text, '没有时间') === false);
/* 下面两条以前是错的：备用药被当成每日服药导出、长期药被 endDate 提前截断 */
chk('备用药（按需服用）不进日历', strpos($text, '布洛芬') === false);
chk('长期药填了结束日也不该停', strpos($text, '长期药带结束日') !== false);
chk('待办：5 条（日/周/月重复 + 未来单次 + 时间块）',
    substr_count($text, 'UID:task-') === 5, (string)substr_count($text, 'UID:task-'));
chk('已完成的不进日历', strpos($text, '已完成') === false);
chk('已取消的不进日历（与推送同口径，别只排除 done）', strpos($text, '已取消任务') === false);
chk('逾期的单次任务不进日历', strpos($text, '逾期任务') === false);
/* 时间块：日历按「开始时间」画，不是通知时间；长度按 duration，不是固定 15 分钟 */
$ev8 = '';
if (preg_match('/BEGIN:VEVENT.*?项目评审会.*?END:VEVENT/s', $text, $mm8)) {
    $ev8 = $mm8[0];
}
chk('有开始时间的任务进了日历', $ev8 !== '');
chk('DTSTART 用开始时间 14:30 而不是通知时间 09:00',
    strpos($ev8, 'T143000') !== false, $ev8 === '' ? '(没有这条事件)' : substr($ev8, 0, 200));
chk('DTEND 按 90 分钟算（16:00）', strpos($ev8, 'T160000') !== false,
    $ev8 === '' ? '' : substr($ev8, 0, 200));
chk('今天已过点的单次任务不进日历', strpos($text, '今天已过点') === false);
chk('习惯：只导出有建议时间的 1 条',
    substr_count($text, 'UID:habit-') === 1, (string)substr_count($text, 'UID:habit-'));
chk('归档习惯不进日历', strpos($text, '已归档') === false);
chk('戒除型习惯不进日历', strpos($text, '戒烟') === false);

/* ---------------- 3. 时间正确性 ---------------- */
echo "\n[3] 时间\n";
chk('DTSTART 一律带 TZID',
    substr_count($text, 'DTSTART;TZID=Asia/Shanghai:') === 11,
    (string)substr_count($text, 'DTSTART;TZID=Asia/Shanghai:'));
chk('没有把时刻写成 UTC（否则 BYDAY 会偏一天）',
    !preg_match('/DTSTART[^:]*:\d{8}T\d{6}Z/', $text));
chk('晚上 8 点那条仍是 20:00', strpos($text, 'T200000') !== false);
chk('早于 8 点的任务保持 07:30', strpos($text, 'T073000') !== false);
chk('上午 9 点的药推到明天（今天已过）', strpos($text, '20261026T090000') !== false);
chk('DTEND 都比 DTSTART 晚', (function () use ($lines) {
    $starts = [];
    $ends = [];
    foreach ($lines as $l) {
        if (strpos($l, 'DTSTART;') === 0) {
            $starts[] = substr($l, strrpos($l, ':') + 1);
        } elseif (strpos($l, 'DTEND;') === 0) {
            $ends[] = substr($l, strrpos($l, ':') + 1);
        }
    }
    if (count($starts) !== count($ends)) {
        return false;
    }
    foreach ($starts as $i => $s) {
        if ($ends[$i] <= $s) {
            return false;
        }
    }
    return true;
})());

/* ---------------- 4. 重复规则 ---------------- */
echo "\n[4] 重复规则\n";
chk('每日重复', strpos($text, 'RRULE:FREQ=DAILY') !== false);
chk('每周重复带 BYDAY=WE（repeatWeekday=3）',
    strpos($text, 'RRULE:FREQ=WEEKLY;BYDAY=WE') !== false);
chk('每月重复带 BYMONTHDAY=1', strpos($text, 'RRULE:FREQ=MONTHLY;BYMONTHDAY=1') !== false);
chk('有停药日的疗程写了 UNTIL', strpos($text, ';UNTIL=') !== false);
chk('UNTIL 是 UTC（以 Z 结尾）', (bool)preg_match('/UNTIL=\d{8}T\d{6}Z/', $text));

/* ---------------- 5. 提醒 ---------------- */
echo "\n[5] 提醒\n";
chk('每个事件都带 VALARM', substr_count($text, 'BEGIN:VALARM') === 11,
    (string)substr_count($text, 'BEGIN:VALARM'));
chk('提醒零延迟触发', substr_count($text, 'TRIGGER:-PT0M') === 11);

/* ---------------- 6. 格式合规 ---------------- */
echo "\n[6] 格式\n";
$maxBytes = 0;
$badLine = '';
foreach ($lines as $l) {
    $b = strlen($l);
    if ($b > $maxBytes) {
        $maxBytes = $b;
        $badLine = $l;
    }
}
chk('每行不超过 75 字节（RFC 5545 折行）', $maxBytes <= 75, 'max=' . $maxBytes);
/* 不依赖 mbstring：preg_match 的 /u 修饰符内部就会校验 UTF-8，
   遇到非法字节序列直接返回 false */
chk('折行后是合法 UTF-8（中文没被切坏）', preg_match('//u', $text) === 1);
chk('中文药名完整保留', strpos($text, '阿莫西林') !== false);
chk('备注进了 DESCRIPTION', strpos($text, '空腹') !== false);
chk('UID 唯一', (function () use ($lines) {
    $uids = [];
    foreach ($lines as $l) {
        if (strpos($l, 'UID:') === 0) {
            $uids[] = substr($l, 4);
        }
    }
    return count($uids) === count(array_unique($uids));
})());

/* ---------------- 7. 异常输入 ---------------- */
echo "\n[7] 异常输入\n";
$empty = lb_ics_build([], $now);
chk('空数据不报错且返回空日历', $empty['count'] === 0
    && strpos($empty['text'], 'BEGIN:VCALENDAR') === 0);
chk('空日历也有 VTIMEZONE', strpos($empty['text'], 'BEGIN:VTIMEZONE') !== false);
$weird = lb_ics_build([
    'meds' => [null, 'x', ['id' => 'a', 'status' => 'active', 'times' => ['99:99', 'garbage']]],
    'tasks' => [['id' => 'b', 'status' => 'todo', 'due' => '不是日期'], 42],
    'habits' => [['id' => 'c', 'suggestTime' => '25:00']],
], $now);
chk('字段缺失/类型不对时不崩', $weird['count'] === 0, 'count=' . $weird['count']);

/* ---------------- 8. 折行不切坏多字节 ---------------- */
echo "\n[8] 折行\n";
$long = str_repeat('很长的中文备注', 12);
$one = lb_ics_build([
    'tasks' => [['id' => 'z', 'title' => '长备注', 'status' => 'todo',
                 'due' => '2026-10-28', 'note' => $long]],
], $now);
$okUtf8 = preg_match('//u', $one['text']) === 1;
chk('长中文备注折行后仍是合法 UTF-8', $okUtf8);
$plain = strip_tags($one['text']);
chk('折行后拼回原文（去掉续行空格和转义）', (function () use ($plain, $long) {
    $joined = str_replace(["\r\n ", "\\n"], ['', ''], $plain);
    return strpos($joined, $long) !== false || strpos(str_replace('\\,', ',', $joined), $long) !== false;
})());

echo "\n" . str_repeat('=', 46) . "\n";
echo 'PASS ' . $pass . ' / ' . ($pass + count($fails)) . "\n";
if ($fails) {
    foreach ($fails as $f) {
        echo '  FAIL: ' . $f . "\n";
    }
    exit(1);
}
echo "服务端日历生成全部通过\n";
