<?php
/**
 * 某一天的提醒时间表（实例，不是规则）。
 *
 * 和 api/ics.php 的区别要说清楚，否则以后一定会有人问「为什么有两套」：
 * - ics.php 输出的是 **规则**（FREQ=DAILY），因为它要交给日历客户端长期自己算。
 * - 这里输出的是 **某一天的实例**（今天 08:00 吃这个药），因为推送必须在正确的那一分钟
 *   主动发出去，需要的是「现在这一分钟该不该发」，而不是一条规则。
 *
 * 两者的“什么算有效”必须一致：同样的字段、同样的过滤条件。
 * 用药这里比 ics.php 更严格一点——补上了备用药（courseType=prn）和短期疗程
 * 这两个判断，因为那条路径原本漏了它们（备用药被当成每日服药导出）。
 *
 * 过滤条件对齐前端 index.html：
 *   medActiveOn()  备用药跳过、非 active 跳过、startDate 之前跳过、
 *                  只有 courseType=short 才看 endDate
 *   pendingTasks() 已归档 / done / cancelled 跳过；只有 due 正好是今天才提醒
 *   activeHabits() optional / 已归档 / 用药类习惯 跳过
 */

require_once __DIR__ . '/ics.php';

/**
 * @return array<int, array{time:string, kind:string, id:string, title:string, body:string}>
 *         time 为 HH:MM，按时间升序
 */
function lb_schedule_day(array $state, string $date): array
{
    if (!lb_ics_is_date($date)) {
        return [];
    }
    $out = [];

    $doses = [];
    if (isset($state['doses'][$date]) && is_array($state['doses'][$date])) {
        $doses = $state['doses'][$date];
    }
    $checks = [];
    if (isset($state['checks'][$date]) && is_array($state['checks'][$date])) {
        $checks = $state['checks'][$date];
    }

    /* ---------------------------------------------------------------- 用药 */
    foreach ((array)($state['meds'] ?? []) as $m) {
        if (!is_array($m)) {
            continue;
        }
        if (($m['courseType'] ?? '') === 'prn') {
            continue;   // 备用药按需服用，没有固定时刻
        }
        if (($m['status'] ?? '') !== 'active') {
            continue;
        }
        $mid = (string)($m['id'] ?? '');
        if ($mid === '') {
            continue;
        }
        $startDay = lb_ics_is_date($m['startDate'] ?? '') ? (string)$m['startDate'] : '';
        if ($startDay !== '' && $date < $startDay) {
            continue;
        }
        /* 只有短期疗程才有结束日；长期服药即便填了 endDate 也不该停 */
        if (($m['courseType'] ?? '') === 'short') {
            $endDay = lb_ics_is_date($m['endDate'] ?? '') ? (string)$m['endDate'] : '';
            if ($endDay !== '' && $date > $endDay) {
                continue;
            }
        }

        $times = isset($m['times']) && is_array($m['times']) ? $m['times'] : [];
        $times = array_values(array_filter($times, static function ($t) {
            return is_string($t) && preg_match('/^([01]\d|2[0-3]):[0-5]\d$/', $t);
        }));
        if (!$times) {
            continue;
        }

        $name = (string)($m['name'] ?? '药');
        $amount = (float)($m['doseAmount'] ?? 1);
        if ($amount <= 0) {
            $amount = 1;
        }
        $amt = (floor($amount) == $amount)
            ? (string)(int)$amount
            : rtrim(rtrim(number_format($amount, 2, '.', ''), '0'), '.');
        $unit = (string)($m['doseUnit'] ?? '');
        if ($unit === '') {
            $unit = (string)($m['form'] ?? '');
        }
        if ($unit === '') {
            $unit = '片';
        }

        foreach ($times as $slot) {
            /* 已经吃过了就别再提醒。允许提前吃：7:50 记了，8:00 不该再响 */
            if (isset($doses[$mid][$slot]) && $doses[$mid][$slot]) {
                continue;
            }
            $out[] = [
                'time' => $slot,
                'kind' => 'med',
                'id' => $mid,
                'title' => '该吃药了',
                'body' => $name . ' ' . $amt . $unit . '（每天 ' . $slot . '）',
            ];
        }
    }

    /* ---------------------------------------------------------------- 待办 */
    foreach ((array)($state['tasks'] ?? []) as $t) {
        if (!is_array($t) || !empty($t['archivedAt'])) {
            continue;
        }
        $st = (string)($t['status'] ?? '');
        if ($st === 'done' || $st === 'cancelled') {
            continue;
        }
        if (!lb_ics_is_date($t['due'] ?? '')) {
            continue;
        }
        /* 只提醒「今天到期」的。逾期的不按点提醒，否则过了三天还在响 */
        if ((string)$t['due'] !== $date) {
            continue;
        }
        $tid = (string)($t['id'] ?? '');
        if ($tid === '') {
            continue;
        }
        $repeat = in_array(($t['repeat'] ?? 'none'), ['daily', 'weekly', 'monthly'], true);
        /* 重复任务用自己设定的时间；单次任务沿用日历里那个 09:00 */
        $slot = $repeat ? (string)($t['repeatTime'] ?? '20:00') : '09:00';
        if (!preg_match('/^([01]\d|2[0-3]):[0-5]\d$/', $slot)) {
            $slot = $repeat ? '20:00' : '09:00';
        }
        $title = trim((string)($t['title'] ?? '待办'));
        if ($title === '') {
            $title = '待办';
        }
        $note = trim((string)($t['note'] ?? ''));
        $out[] = [
            'time' => $slot,
            'kind' => 'task',
            'id' => $tid,
            'title' => '该做这件事了',
            'body' => $title . ($note !== '' ? "\n" . $note : ''),
        ];
    }

    /* ---------------------------------------------------------------- 习惯 */
    foreach ((array)($state['habits'] ?? []) as $h) {
        if (!is_array($h) || !empty($h['archivedAt'])) {
            continue;
        }
        if (!empty($h['optional']) || !empty($h['med'])) {
            continue;   // 可选项不催；用药类习惯由药品自己提醒
        }
        /* 与 ics.php 保持一致：戒除类（quit）不排提醒，它靠当天“没破戒”来算 */
        if (($h['type'] ?? '') === 'quit') {
            continue;
        }
        $hid = (string)($h['id'] ?? '');
        if ($hid === '') {
            continue;
        }
        $slot = (string)($h['suggestTime'] ?? '');
        if (!preg_match('/^([01]\d|2[0-3]):[0-5]\d$/', $slot)) {
            continue;
        }
        /* 今天已经打过卡就不再催 */
        if (isset($checks[$hid]) && (float)$checks[$hid] > 0) {
            continue;
        }
        $name = trim((string)($h['name'] ?? '习惯'));
        if ($name === '') {
            $name = '习惯';
        }
        $target = (float)($h['target'] ?? 1);
        $unit = (string)($h['unit'] ?? '');
        $body = $target > 1
            ? '今天还差 ' . (string)(int)$target . ($unit !== '' ? $unit : '次')
            : '今天的习惯还没打卡';
        $icon = (string)($h['icon'] ?? '');
        $out[] = [
            'time' => $slot,
            'kind' => 'habit',
            'id' => $hid,
            'title' => ($icon !== '' ? $icon . ' ' : '') . $name,
            'body' => $body,
        ];
    }

    usort($out, static function ($a, $b) {
        $c = strcmp($a['time'], $b['time']);
        return $c !== 0 ? $c : strcmp($a['kind'] . $a['id'], $b['kind'] . $b['id']);
    });
    return $out;
}

/**
 * 取出「在指定时间窗内到点」的条目。
 *
 * 为什么是窗口而不是「正好这一分钟」：定时任务会延迟，服务器重启还会漏跑。
 * 留几分钟的宽容期，配合发送记录的去重，既不重复也不会漏。
 *
 * @param string $now   HH:MM
 * @param int    $grace 往前宽容多少分钟
 */
function lb_schedule_due(array $plan, string $now, int $grace = 3): array
{
    if (!preg_match('/^([01]\d|2[0-3]):([0-5]\d)$/', $now, $m)) {
        return [];
    }
    $nowMin = (int)$m[1] * 60 + (int)$m[2];
    $from = $nowMin - max(0, $grace);
    $out = [];
    foreach ($plan as $item) {
        if (!preg_match('/^([01]\d|2[0-3]):([0-5]\d)$/', (string)($item['time'] ?? ''), $mm)) {
            continue;
        }
        $t = (int)$mm[1] * 60 + (int)$mm[2];
        if ($t <= $nowMin && $t >= $from) {
            $out[] = $item;
        }
    }
    return $out;
}
