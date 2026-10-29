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
    'repeat' => 'daily', 'repeatTime' => '20:00', 'note' => '别忘了'];
$plan = lb_schedule_day(['tasks' => [$daily]], D);
chk('重复任务用自己的时间', has($plan, '20:00 task:t2'), implode(' | ', times($plan)));
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

echo PHP_EOL . '----------------------------' . PHP_EOL;
echo '通过 ' . $pass . ' 项，失败 ' . $fail . ' 项' . PHP_EOL;
exit($fail === 0 ? 0 : 1);
