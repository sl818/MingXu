<?php
/**
 * 「当天提醒时间表」单测。
 *
 * 这套判断必须和前端 index.html 一致：前端的 medActiveOn / pendingTasks /
 * activeHabits 是用户在页面上看到的事实，推送不能多一条也不能少一条。
 * 所以每个用例都写成「页面上是什么样 → 推送就该是什么样」。
 *
 * 运行：php e2e/test-schedule.php
 */

/* api/ics.php 开头有一道保护：没有这个常量就直接 exit（防止被当静态文件访问）。
   schedule.php 依赖 ics.php 里的日期工具，所以必须先在前面定义。 */
define('LIFEBOARD_API', 1);

require __DIR__ . '/../api/schedule.php';

$pass = 0;
$fail = 0;

function chk(string $name, $cond, string $note = ''): void
{
    global $pass, $fail;
    if ($cond) {
        $pass++;
        echo "  ✓ " . $name . PHP_EOL;
    } else {
        $fail++;
        echo "  ✗ " . $name . ($note !== '' ? '  [' . $note . ']' : '') . PHP_EOL;
    }
}

const D = '2026-10-29';

function times(array $plan): array
{
    return array_map(static function ($x) {
        return $x['time'] . ' ' . $x['kind'] . ':' . $x['id'];
    }, $plan);
}

function has(array $plan, string $needle): bool
{
    foreach ($plan as $p) {
        if ($p['time'] . ' ' . $p['kind'] . ':' . $p['id'] === $needle) {
            return true;
        }
    }
    return false;
}

/* ------------------------------------------------------------------ 用药 */
echo "[1] 用药" . PHP_EOL;
$med = [
    'id' => 'm1', 'name' => '阿莫西林', 'status' => 'active', 'courseType' => 'long',
    'times' => ['08:00', '20:00'], 'doseAmount' => 1, 'doseUnit' => '片',
    'startDate' => '2026-10-01', 'endDate' => '',
];
$plan = lb_schedule_day(['meds' => [$med]], D);
chk('每天两次的药出现两个时刻', count($plan) === 2, implode(' | ', times($plan)));
chk('08:00 命中', has($plan, '08:00 med:m1'));
chk('20:00 命中', has($plan, '20:00 med:m1'));
chk('标题是「该吃药了」', $plan[0]['title'] === '该吃药了', $plan[0]['title']);
chk('正文带药名与剂量', strpos($plan[0]['body'], '阿莫西林 1片') !== false, $plan[0]['body']);

$prn = $med;
$prn['id'] = 'm2';
$prn['courseType'] = 'prn';
chk('备用药（按需服用）不进日程',
    count(lb_schedule_day(['meds' => [$prn]], D)) === 0);

$off = $med;
$off['status'] = 'paused';
chk('非 active 的药不进日程',
    count(lb_schedule_day(['meds' => [$off]], D)) === 0);

$future = $med;
$future['startDate'] = '2026-11-05';
chk('还没到开始日不进日程',
    count(lb_schedule_day(['meds' => [$future]], D)) === 0);

$short = $med;
$short['courseType'] = 'short';
$short['endDate'] = '2026-10-20';
chk('短期疗程已过结束日就停', count(lb_schedule_day(['meds' => [$short]], D)) === 0);

$long = $med;
$long['courseType'] = 'long';
$long['endDate'] = '2026-10-20';
chk('长期服药即使填了结束日也不停（与前端一致）',
    count(lb_schedule_day(['meds' => [$long]], D)) === 2);

$half = $med;
$half['doseAmount'] = 0.5;
$hplan = lb_schedule_day(['meds' => [$half]], D);
chk('半片剂量显示为 0.5 片', strpos($hplan[0]['body'], '0.5片') !== false, $hplan[0]['body']);

$taken = lb_schedule_day([
    'meds' => [$med],
    'doses' => [D => ['m1' => ['08:00' => 1]]],
], D);
chk('早上已吃：08:00 不再提醒', !has($taken, '08:00 med:m1'));
chk('晚上未吃：20:00 仍然提醒', has($taken, '20:00 med:m1'));

/* ------------------------------------------------------------------ 待办 */
echo PHP_EOL . "[2] 待办" . PHP_EOL;
$once = ['id' => 't1', 'title' => '交报告', 'status' => 'todo', 'due' => D,
    'repeat' => 'none', 'repeatTime' => '20:00', 'note' => ''];
$plan = lb_schedule_day(['tasks' => [$once]], D);
chk('单次任务在 09:00 提醒', has($plan, '09:00 task:t1'), implode(' | ', times($plan)));

$daily = ['id' => 't2', 'title' => '吃药打卡', 'status' => 'todo', 'due' => D,
    'repeat' => 'daily', 'repeatTime' => '20:00', 'notifyTime' => '20:00', 'note' => '别忘了'];
$plan = lb_schedule_day(['tasks' => [$daily]], D);
chk('任务用通知时间（notifyTime）', has($plan, '20:00 task:t2'), implode(' | ', times($plan)));
chk('正文包含待办标题', strpos($plan[0]['body'], '吃药打卡') !== false, $plan[0]['body']);
chk('正文带上备注', strpos($plan[0]['body'], '别忘了') !== false);

$overdue = $once;
$overdue['due'] = '2026-10-27';
chk('逾期任务不按点提醒（否则会天天响）',
    count(lb_schedule_day(['tasks' => [$overdue]], D)) === 0);

$tomorrow = $once;
$tomorrow['due'] = '2026-10-30';
chk('明天到期的今天不提醒',
    count(lb_schedule_day(['tasks' => [$tomorrow]], D)) === 0);

$done = $once;
$done['status'] = 'done';
chk('已完成的不提醒', count(lb_schedule_day(['tasks' => [$done]], D)) === 0);

$cancelled = $once;
$cancelled['status'] = 'cancelled';
chk('已取消的不提醒', count(lb_schedule_day(['tasks' => [$cancelled]], D)) === 0);

$archived = $once;
$archived['archivedAt'] = '2026-10-28T10:00:00';
chk('已归档的不提醒', count(lb_schedule_day(['tasks' => [$archived]], D)) === 0);

$noNotify = $once;
$noNotify['notify'] = false;
chk('关闭通知的待办不提醒', count(lb_schedule_day(['tasks' => [$noNotify]], D)) === 0);

$custom = $once;
$custom['notifyTime'] = '11:30';
$custom['notifyNote'] = '记得带材料';
$plan = lb_schedule_day(['tasks' => [$custom]], D);
chk('自定义通知时间生效', has($plan, '11:30 task:t1'), implode(' | ', times($plan)));
chk('通知备注附加到正文', strpos($plan[0]['body'], '记得带材料') !== false, $plan[0]['body']);

/* ------------------------------------------------------------------ 习惯 */
echo PHP_EOL . "[3] 习惯" . PHP_EOL;
$h = ['id' => 'h1', 'name' => '读书', 'suggestTime' => '15:00', 'target' => 1, 'unit' => '次'];
$plan = lb_schedule_day(['habits' => [$h]], D);
chk('带建议时间的习惯会提醒', has($plan, '15:00 habit:h1'), implode(' | ', times($plan)));

$noTime = ['id' => 'h2', 'name' => '冥想'];
chk('没填时间的习惯不提醒',
    count(lb_schedule_day(['habits' => [$noTime]], D)) === 0);

$opt = $h;
$opt['optional'] = true;
chk('可选项不催', count(lb_schedule_day(['habits' => [$opt]], D)) === 0);

$medHabit = $h;
$medHabit['med'] = true;
chk('用药类习惯由药品自己提醒，不重复推',
    count(lb_schedule_day(['habits' => [$medHabit]], D)) === 0);

$quit = $h;
$quit['type'] = 'quit';
chk('戒除类习惯不排提醒（与 ics 一致）',
    count(lb_schedule_day(['habits' => [$quit]], D)) === 0);

$checked = lb_schedule_day(['habits' => [$h], 'checks' => [D => ['h1' => 1]]], D);
chk('今天已打卡就不再催', count($checked) === 0);

$multi = $h;
$multi['target'] = 8;
$multi['unit'] = '杯';
$mplan = lb_schedule_day(['habits' => [$multi]], D);
chk('多目标习惯说明还差几次', strpos($mplan[0]['body'], '还差 8杯') !== false, $mplan[0]['body']);

/* -------------------------------------------------------------- 排序与窗口 */
echo PHP_EOL . "[4] 排序与时间窗" . PHP_EOL;
$mixed = lb_schedule_day([
    'meds' => [$med],
    'tasks' => [$daily],
    'habits' => [$h],
], D);
chk('按时间升序排列',
    times($mixed) === ['08:00 med:m1', '15:00 habit:h1', '20:00 med:m1', '20:00 task:t2'],
    implode(' | ', times($mixed)));

$p = [['time' => '08:00'], ['time' => '08:05'], ['time' => '20:00']];
chk('08:00 整点命中', count(lb_schedule_due($p, '08:00', 3)) === 1);
chk('08:02 仍在窗口内（cron 抖动）', count(lb_schedule_due($p, '08:02', 3)) === 1);
chk('08:03 恰好在窗口边界', count(lb_schedule_due($p, '08:03', 3)) === 1);
chk('08:04 超出窗口不补发', count(lb_schedule_due($p, '08:04', 3)) === 0);
chk('07:59 不发未来时间的', count(lb_schedule_due($p, '07:59', 3)) === 0);
chk('非法时刻返回空', lb_schedule_due($p, '8:00', 3) === []);

echo PHP_EOL . "[5] 边界" . PHP_EOL;
chk('日期格式非法时返回空', lb_schedule_day(['meds' => [$med]], '2026-13-01') === []);
chk('空 state 不崩', lb_schedule_day([], D) === []);
chk('times 里有垃圾值被忽略', count(lb_schedule_day([
    'meds' => [array_merge($med, ['times' => ['08:00', 'bad', '', '25:00', '7:00']])],
], D)) === 1);

echo PHP_EOL . "[6] 待办汇报" . PHP_EOL;
$rtasks = [
    ['id' => 'r1', 'title' => '写周报', 'status' => 'todo', 'due' => D, 'tag' => '工作'],
    ['id' => 'r2', 'title' => '买菜', 'status' => 'todo', 'due' => '2026-10-30', 'tag' => '生活'],
    ['id' => 'r3', 'title' => '交房租', 'status' => 'todo', 'due' => '2026-10-20', 'tag' => '生活'],
    ['id' => 'r4', 'title' => '已完成', 'status' => 'done', 'due' => D, 'doneAt' => D, 'tag' => '工作'],
    ['id' => 'r5', 'title' => '取消', 'status' => 'cancelled', 'due' => D, 'tag' => '工作'],
    ['id' => 'r6', 'title' => '归档', 'status' => 'todo', 'due' => D, 'tag' => '工作', 'archivedAt' => '2026-10-01'],
];
$reports = lb_schedule_reports(['tasks' => $rtasks], D);
$find = static function (array $list, string $id) {
    foreach ($list as $x) {
        if ($x['id'] === $id) return $x;
    }
    return null;
};

$morning = $find($reports, 'morning');
chk('早报在 08:20', $morning !== null && $morning['time'] === '08:20',
    $morning ? $morning['time'] : '无');
chk('早报统计未完成 3 项', $morning && strpos($morning['body'], '未完成 3 项') !== false,
    $morning['body']);
chk('早报统计逾期 1 项', $morning && strpos($morning['body'], '已逾期 1 项') !== false,
    $morning['body']);
chk('早报按 tag 分组', $morning
    && strpos($morning['body'], '工作 1 项') !== false
    && strpos($morning['body'], '生活 2 项') !== false, $morning['body']);

$noon = $find($reports, 'noon');
chk('午报在 12:30', $noon !== null && $noon['time'] === '12:30');

$evening = $find($reports, 'evening');
chk('晚报在 20:00', $evening !== null && $evening['time'] === '20:00');
chk('晚报今日完成 1 项', $evening && strpos($evening['body'], '今日完成 1 项') !== false,
    $evening['body']);
chk('晚报明日待办 1 条', $evening && strpos($evening['body'], '明日待办 1 条') !== false,
    $evening['body']);

$empty = lb_schedule_reports([], D);
$emptyMorning = $find($empty, 'morning');
chk('无待办时早报说全部完成', $emptyMorning && strpos($emptyMorning['body'], '全部完成') !== false,
    $emptyMorning['body']);

echo PHP_EOL . "[7] 习惯通知" . PHP_EOL;
$dw = (int)date('w', strtotime(D));   // D 那天的星期几（0=周日）
$dm = (int)date('j', strtotime(D));   // D 的几号

$hOff = ['id' => 'h9', 'name' => '不通知', 'suggestTime' => '15:00', 'target' => 1, 'notify' => false];
chk('关闭通知的习惯不提醒', count(lb_schedule_day(['habits' => [$hOff]], D)) === 0);

$hWeekly = ['id' => 'h10', 'name' => '称体重', 'suggestTime' => '08:25', 'target' => 1,
    'notifyFreq' => 'weekly', 'notifyWeekday' => $dw, 'notifyNote' => '空腹称'];
$plan = lb_schedule_day(['habits' => [$hWeekly]], D);
chk('weekly 今天命中会提醒', has($plan, '08:25 habit:h10'), implode(' | ', times($plan)));
chk('习惯通知备注附加正文', strpos($plan[0]['body'], '空腹称') !== false, $plan[0]['body']);

$hWeekly2 = $hWeekly;
$hWeekly2['id'] = 'h11';
$hWeekly2['notifyWeekday'] = ($dw + 1) % 7;   // 明天，不是今天
chk('weekly 非今天不提醒', count(lb_schedule_day(['habits' => [$hWeekly2]], D)) === 0);

$hMonthly = ['id' => 'h12', 'name' => '交房租', 'suggestTime' => '09:00', 'target' => 1,
    'notifyFreq' => 'monthly', 'notifyMonthday' => $dm];
chk('monthly 今天命中会提醒', has(lb_schedule_day(['habits' => [$hMonthly]], D), '09:00 habit:h12'));

$hMonthly2 = $hMonthly;
$hMonthly2['id'] = 'h13';
$hMonthly2['notifyMonthday'] = ($dm === 31 ? 1 : $dm + 1);
chk('monthly 非今天不提醒', count(lb_schedule_day(['habits' => [$hMonthly2]], D)) === 0);

/* ---------------- 待办时间块：推送正文带上「14:30–16:00」 ---------------- */
$block = ['tasks' => [[
    'id' => 'tb1', 'title' => '项目评审会', 'status' => 'todo', 'due' => D,
    'notifyTime' => '09:00', 'startTime' => '14:30', 'duration' => 90,
]]];
$planB = lb_schedule_day($block, D);
chk('有时间块的待办仍按通知时间 09:00 推送（不是开始时间）',
    has($planB, '09:00 task:tb1'), implode(' | ', times($planB)));
$bodyB = $planB[0]['body'] ?? '';
chk('正文带时间段 14:30–16:00', strpos($bodyB, '14:30–16:00') !== false, $bodyB);
chk('正文仍有标题', strpos($bodyB, '项目评审会') !== false);

$noDur = ['tasks' => [[
    'id' => 'tb2', 'title' => '只看时间', 'status' => 'todo', 'due' => D,
    'notifyTime' => '10:00', 'startTime' => '15:00', 'duration' => 0,
]]];
$bodyC = (lb_schedule_day($noDur, D)[0]['body'] ?? '');
chk('没设时长时只写开始时间', strpos($bodyC, '15:00') !== false && strpos($bodyC, '–') === false, $bodyC);

$notBlock = ['tasks' => [[
    'id' => 'tb3', 'title' => '纯提醒', 'status' => 'todo', 'due' => D, 'notifyTime' => '11:00',
]]];
$bodyD = (lb_schedule_day($notBlock, D)[0]['body'] ?? '');
chk('没有时间块时正文不带时间行', strpos($bodyD, '11:00') === false, $bodyD);

/* ---------------- 自定义通知（v71） ----------------
   这一块只在推送里用，不进日历订阅：通知不是日程。
   去重靠 push_sent 的 slot_key（日期|notice|id|时间），所以这里只管「那天该不该发」。 */
echo PHP_EOL . '自定义通知' . PHP_EOL;

$noticesOf = static function (array $list, string $date): array {
    return lb_schedule_notices(['notices' => $list], $date);
};

$everyDay = ['id' => 'n1', 'text' => '记得吃维生素', 'time' => '20:00', 'mode' => 'daily', 'on' => true];
$pDaily = $noticesOf([$everyDay], '2026-11-08');
chk('每天：任意一天都进计划', count($pDaily) === 1 && $pDaily[0]['time'] === '20:00', json_encode($pDaily));
chk('每天的 kind 是 notice', ($pDaily[0]['kind'] ?? '') === 'notice');
chk('正文就是用户写的内容', ($pDaily[0]['body'] ?? '') === '记得吃维生素');
chk('标题带「自定义提醒」', strpos($pDaily[0]['title'] ?? '', '自定义提醒') !== false);
chk('换一天还在（重复任务不是一次性的）', count($noticesOf([$everyDay], '2026-11-09')) === 1);

$once = ['id' => 'n2', 'text' => '去医院复查', 'time' => '08:30', 'mode' => 'once', 'date' => '2026-11-05'];
chk('单次：指定那天发', count($noticesOf([$once], '2026-11-05')) === 1);
chk('单次：过了那天不再出现', count($noticesOf([$once], '2026-11-06')) === 0);
chk('单次：还没到那天也不提前发', count($noticesOf([$once], '2026-11-04')) === 0);

$weekly = ['id' => 'n3', 'text' => '周复盘', 'time' => '21:30', 'mode' => 'weekly', 'weeks' => [1, 4]];
chk('每周一、四：周一发（11-09 是周一）', count($noticesOf([$weekly], '2026-11-09')) === 1);
chk('每周一、四：周四发（11-12 是周四）', count($noticesOf([$weekly], '2026-11-12')) === 1);
chk('每周一、四：周二不发', count($noticesOf([$weekly], '2026-11-10')) === 0);
chk('每周没选星期时不发', count($noticesOf([array_merge($weekly, ['weeks' => []])], '2026-11-09')) === 0);

$monthly = ['id' => 'n4', 'text' => '交房租', 'time' => '09:00', 'mode' => 'monthly', 'monthday' => 1];
chk('每月 1 号：1 号发', count($noticesOf([$monthly], '2026-12-01')) === 1);
chk('每月 1 号：2 号不发', count($noticesOf([$monthly], '2026-12-02')) === 0);

$m31 = ['id' => 'n5', 'text' => '月末对账', 'time' => '09:00', 'mode' => 'monthly', 'monthday' => 31];
chk('每月 31 号：大月 31 号发', count($noticesOf([$m31], '2026-12-31')) === 1);
chk('每月 31 号：2 月按月末 28 号发', count($noticesOf([$m31], '2026-02-28')) === 1);
chk('每月 31 号：2 月 27 号不发', count($noticesOf([$m31], '2026-02-27')) === 0);

$paused = ['id' => 'n6', 'text' => '暂停的', 'time' => '20:00', 'mode' => 'daily', 'on' => false];
chk('暂停的通知不发', count($noticesOf([$paused], '2026-11-08')) === 0);

$blank = ['id' => 'n7', 'text' => '   ', 'time' => '20:00', 'mode' => 'daily'];
chk('空内容不发', count($noticesOf([$blank], '2026-11-08')) === 0);

$badTime = ['id' => 'n8', 'text' => '时间坏了', 'time' => '25:99', 'mode' => 'daily'];
chk('时间格式非法不发', count($noticesOf([$badTime], '2026-11-08')) === 0);

chk('多条通知互不影响（11-05 是周四）',
    count($noticesOf([$everyDay, $once, $weekly], '2026-11-05')) === 3);
$dayPlan = lb_schedule_day(['notices' => [$everyDay]], '2026-11-08');
$noticeInDay = 0;
foreach ($dayPlan as $x) {
    if (($x['kind'] ?? '') === 'notice') {
        $noticeInDay++;
    }
}
chk('通知不进日历订阅（lb_schedule_day 不含 notice）', $noticeInDay === 0);

/* ------------------------------------------------------------------ */
echo '[5] 倒数日' . PHP_EOL;

/* 今天 2026-11-10：距 11-20 还有 10 天，距 11-13 还有 3 天 */
$cdsOf = static function (array $list, string $date): array {
    return lb_schedule_countdowns(['countdowns' => $list], $date);
};
$cd = static function (array $over) {
    return array_merge([
        'id' => 'cd1', 'title' => '考研', 'date' => '2026-11-20',
        'note' => '记得打印准考证', 'time' => '09:00', 'remindDays' => [3, 1, 0], 'on' => true,
    ], $over);
};

chk('提前 10 天不在档位里，不发', count($cdsOf([$cd([])], '2026-11-10')) === 0);
chk('提前 3 天发一条', count($cdsOf([$cd([])], '2026-11-17')) === 1);
chk('提前 1 天发一条', count($cdsOf([$cd([])], '2026-11-19')) === 1);
chk('当天发一条', count($cdsOf([$cd([])], '2026-11-20')) === 1);

$one = $cdsOf([$cd([])], '2026-11-17')[0] ?? [];
chk('kind 是 countdown', ($one['kind'] ?? '') === 'countdown', json_encode($one, JSON_UNESCAPED_UNICODE));
chk('标题带名字', strpos((string)($one['title'] ?? ''), '考研') !== false, (string)($one['title'] ?? ''));
chk('正文写还剩几天', strpos((string)($one['body'] ?? ''), '还有 3 天') !== false, (string)($one['body'] ?? ''));
chk('备注跟着发出去', strpos((string)($one['body'] ?? ''), '准考证') !== false, (string)($one['body'] ?? ''));
chk('时间是 09:00', ($one['time'] ?? '') === '09:00', (string)($one['time'] ?? ''));

$today = $cdsOf([$cd([])], '2026-11-20')[0] ?? [];
chk('当天文案是「就是今天」', strpos((string)($today['body'] ?? ''), '就是今天') !== false, (string)($today['body'] ?? ''));

chk('过去的日子不再提醒', count($cdsOf([$cd([])], '2026-11-25')) === 0);
chk('暂停的不发', count($cdsOf([$cd(['on' => false])], '2026-11-17')) === 0);
chk('档位里没有这天就不发', count($cdsOf([$cd(['remindDays' => [7]])], '2026-11-17')) === 0);
chk('档位为空不发', count($cdsOf([$cd(['remindDays' => []])], '2026-11-17')) === 0);
chk('没填名字不发', count($cdsOf([$cd(['title' => '  '])], '2026-11-17')) === 0);
chk('日期格式非法不发', count($cdsOf([$cd(['date' => '2026/11/20'])], '2026-11-17')) === 0);
chk('时刻非法不发', count($cdsOf([$cd(['time' => '9:00'])], '2026-11-17')) === 0);
chk('没备注就不多空行', strpos((string)($cdsOf([$cd(['note' => ''])], '2026-11-17')[0]['body'] ?? ''), "\n") === false);

$two = $cdsOf([
    $cd(['id' => 'a', 'title' => 'A']),
    $cd(['id' => 'b', 'title' => 'B']),
], '2026-11-17');
chk('两个倒数日同一天各发一条', count($two) === 2);

$dayPlan2 = lb_schedule_day(['countdowns' => [$cd([])]], '2026-11-17');
$cdInDay = 0;
foreach ($dayPlan2 as $x) {
    if (($x['kind'] ?? '') === 'countdown') {
        $cdInDay++;
    }
}
chk('倒数日不进日历订阅（lb_schedule_day 不含 countdown）', $cdInDay === 0);

/* ------------------------------------------------------------------ */
echo '[6] 还款提醒' . PHP_EOL;

$dbtOf = static function (array $debts, string $date, array $nt = []): array {
    return lb_schedule_debts(['money' => [
        'notify' => array_merge(['on' => true, 'time' => '09:00', 'before' => [3, 1, 0]], $nt),
        'debts' => $debts,
    ]], $date);
};
$db = static function (array $over) {
    return array_merge([
        'id' => 'dd1', 'name' => '信用卡A', 'balance' => 38000, 'min' => 1900,
        'apr' => 18, 'due' => 15, 'type' => 'card',
    ], $over);
};

/* 今天锚点 2026-11-10，还款日 15 号 */
chk('距还款还有 5 天，档位 [3,1,0] 不发', count($dbtOf([$db([])], '2026-11-10')) === 0);
chk('提前 3 天发', count($dbtOf([$db([])], '2026-11-12')) === 1);
chk('提前 1 天发', count($dbtOf([$db([])], '2026-11-14')) === 1);
chk('当天发', count($dbtOf([$db([])], '2026-11-15')) === 1);

$one = $dbtOf([$db([])], '2026-11-12')[0] ?? [];
chk('kind 是 debt', ($one['kind'] ?? '') === 'debt', json_encode($one, JSON_UNESCAPED_UNICODE));
chk('标题带债名', strpos((string)($one['title'] ?? ''), '信用卡A') !== false, (string)($one['title'] ?? ''));
chk('正文写还有几天', strpos((string)($one['body'] ?? ''), '还有 3 天') !== false, (string)($one['body'] ?? ''));
chk('正文带日期', strpos((string)($one['body'] ?? ''), '2026-11-15') !== false, (string)($one['body'] ?? ''));
chk('正文带剩余与最低', strpos((string)($one['body'] ?? ''), '38000') !== false
    && strpos((string)($one['body'] ?? ''), '1900') !== false, (string)($one['body'] ?? ''));

$todayOne = $dbtOf([$db([])], '2026-11-15')[0] ?? [];
chk('当天文案是「就是今天」',
    strpos((string)($todayOne['body'] ?? ''), '就是今天') !== false,
    (string)($todayOne['body'] ?? ''));

/* 跨月：11-16 之后本月还款日已过，指向 12-15 */
chk('本月已过 → 下月还有 29 天，不发', count($dbtOf([$db([])], '2026-11-16')) === 0);
chk('跨月提前 3 天照常发', count($dbtOf([$db([])], '2026-12-12')) === 1);
$cross = $dbtOf([$db([])], '2026-12-12')[0] ?? [];
chk('跨月正文日期是下月那天',
    strpos((string)($cross['body'] ?? ''), '2026-12-15') !== false, (string)($cross['body'] ?? ''));

/* 开关默认关 */
chk('开关关着一条都不发', count($dbtOf([$db([])], '2026-11-12', ['on' => false])) === 0);
chk('开关字段缺失也当关',
    count(lb_schedule_debts(['money' => ['debts' => [$db([])]]], '2026-11-12')) === 0);
chk('没有 money 字段不报错',
    count(lb_schedule_debts(['money' => []], '2026-11-12')) === 0);

/* 边界 */
chk('已还清（余额 0）不发', count($dbtOf([$db(['balance' => 0])], '2026-11-12')) === 0);
chk('没填名字不发', count($dbtOf([$db(['name' => '  '])], '2026-11-12')) === 0);
/* v110：还款日 0 / 空 = 没有具体还款日，一条都不发 */
chk('还款日填 0 不发', count($dbtOf([$db(['due' => 0])], '2026-11-15')) === 0);
chk('还款日为空不发', count($dbtOf([$db(['due' => null])], '2026-11-15')) === 0);
chk('档位没有这天不发',
    count($dbtOf([$db([])], '2026-11-12', ['before' => [7]])) === 0);
chk('时刻非法退回 09:00',
    ($dbtOf([$db([])], '2026-11-12', ['time' => '9:00'])[0]['time'] ?? '') === '09:00');

/* 小月按月末：due=31 在 2 月就是 28 号 */
$feb = $dbtOf([$db(['due' => 31])], '2026-02-28', ['before' => [0]]);
chk('31 号在 2 月落到 28 号（当天发）', count($feb) === 1, json_encode($feb, JSON_UNESCAPED_UNICODE));
chk('落在月末的日期写的是 2026-02-28',
    strpos((string)($feb[0]['body'] ?? ''), '2026-02-28') !== false, (string)($feb[0]['body'] ?? ''));

$two = $dbtOf([
    $db(['id' => 'a', 'name' => 'A']),
    $db(['id' => 'b', 'name' => 'B']),
], '2026-11-12');
chk('两笔债同日各发一条', count($two) === 2);

$dbInDay = 0;
foreach (lb_schedule_day(['money' => ['notify' => ['on' => true], 'debts' => [$db([])]]],
    '2026-11-12') as $x) {
    if (($x['kind'] ?? '') === 'debt') {
        $dbInDay++;
    }
}
chk('还款日不进日历订阅（lb_schedule_day 不含 debt）', $dbInDay === 0);

/* v194：478 呼吸 —— 每天固定时间推送，做几组就有几个时间点。
   第 i 个提醒对应第 i 组：当天做完 i 组就不再催第 i 个。 */
$breathOf = static function (array $times, array $extra = [], array $checks = []): array {
    return [
        'modules' => ['breathe' => array_merge([
            'on' => true, 'name' => '478呼吸法', 'icon' => '🌬️',
            'notify' => true, 'groups' => 3, 'cycles' => 4, 'notifyTimes' => $times,
        ], $extra)],
        'checks' => $checks ? [D => $checks] : [],
    ];
};
$bplan = lb_schedule_day($breathOf(['07:00', '13:00', '21:00']), D);
chk('478：三个时间点都进当天计划', count($bplan) === 3, implode(' | ', times($bplan)));
chk('478：时刻分别是 07:00 / 13:00 / 21:00',
    times($bplan) === ['07:00 habit:h_breathe', '13:00 habit:h_breathe', '21:00 habit:h_breathe'],
    implode(' | ', times($bplan)));
chk('478：正文写今天还差几组',
    strpos((string)($bplan[0]['body'] ?? ''), '还差 3 组') !== false, (string)($bplan[0]['body'] ?? ''));
$bplan1 = lb_schedule_day($breathOf(['07:00', '13:00', '21:00'], [], ['h_breathe' => 1]), D);
chk('478：做完 1 组就不再催第 1 组', count($bplan1) === 2, implode(' | ', times($bplan1)));
$bplan2 = lb_schedule_day($breathOf(['07:00', '13:00', '21:00'], [], ['h_breathe' => 3]), D);
chk('478：三组做完一条都不催', count($bplan2) === 0, implode(' | ', times($bplan2)));
$bplanOff = lb_schedule_day($breathOf(['07:00'], ['notify' => false]), D);
chk('478：关掉提醒不进计划', count($bplanOff) === 0, implode(' | ', times($bplanOff)));
$bplanDef = lb_schedule_day($breathOf([], ['groups' => 3]), D);
chk('478：没存时间点时按组数兜底出 3 条', count($bplanDef) === 3, implode(' | ', times($bplanDef)));
chk('478：兜底时间点是 07:00 / 14:00 / 21:00',
    times($bplanDef) === ['07:00 habit:h_breathe', '14:00 habit:h_breathe', '21:00 habit:h_breathe'],
    implode(' | ', times($bplanDef)));

echo PHP_EOL . '----------------------------' . PHP_EOL;
echo '通过 ' . $pass . ' 项，失败 ' . $fail . ' 项' . PHP_EOL;
exit($fail === 0 ? 0 : 1);
