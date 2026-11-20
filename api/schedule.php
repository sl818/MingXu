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
        /* 通知开关：默认开，显式关掉才不提醒 */
        if (($t['notify'] ?? true) === false) {
            continue;
        }
        $tid = (string)($t['id'] ?? '');
        if ($tid === '') {
            continue;
        }
        /* 通知时间统一用 notifyTime，默认 09:00 */
        $slot = (string)($t['notifyTime'] ?? '09:00');
        if (!preg_match('/^([01]\d|2[0-3]):[0-5]\d$/', $slot)) {
            $slot = '09:00';
        }
        $title = trim((string)($t['title'] ?? '待办'));
        if ($title === '') {
            $title = '待办';
        }
        $note = trim((string)($t['note'] ?? ''));
        $notifyNote = trim((string)($t['notifyNote'] ?? ''));
        /* 填了时间块的，正文里带上「14:00–15:00」，让人一眼知道这事占多久。
           推送时刻仍然用 notifyTime（那是「什么时候提醒」，和时间块是两回事）。 */
        $slotLabel = '';
        $st = (string)($t['startTime'] ?? '');
        if (preg_match('/^([01]\d|2[0-3]):([0-5]\d)$/', $st, $sm)) {
            $slotLabel = $st;
            $dur = (int)($t['duration'] ?? 0);
            if ($dur >= 15) {
                $endMin = (int)$sm[1] * 60 + (int)$sm[2] + $dur;
                $slotLabel .= '–' . sprintf('%02d:%02d', intdiv($endMin, 60) % 24, $endMin % 60);
            }
        }
        $body = $title . ($slotLabel !== '' ? "\n" . $slotLabel : '')
            . ($note !== '' ? "\n" . $note : '')
            . ($notifyNote !== '' ? "\n" . $notifyNote : '');
        $out[] = [
            'time' => $slot,
            'kind' => 'task',
            'id' => $tid,
            'title' => '该做这件事了',
            'body' => $body,
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
        /* 通知开关：默认开，显式关掉才不提醒 */
        if (($h['notify'] ?? true) === false) {
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
        /* 通知频率：daily 每天；weekly 只在 notifyWeekday；monthly 只在 notifyMonthday。
           打卡仍是每天，这里只决定「今天要不要提醒」。notifyWeekday 用 0-6（0=周日），
           和任务的 repeatWeekday、date('w') 一致。 */
        $freq = (string)($h['notifyFreq'] ?? 'daily');
        if ($freq === 'weekly') {
            $wd = max(0, min(6, (int)($h['notifyWeekday'] ?? 1)));
            if ((int)date('w', strtotime($date)) !== $wd) {
                continue;
            }
        } elseif ($freq === 'monthly') {
            $md = max(1, min(31, (int)($h['notifyMonthday'] ?? 1)));
            if ((int)date('j', strtotime($date)) !== $md) {
                continue;
            }
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
        $notifyNote = trim((string)($h['notifyNote'] ?? ''));
        if ($notifyNote !== '') {
            $body .= "\n" . $notifyNote;
        }
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

/**
 * 待办「汇报」：不挂在某个对象上，而是按固定时间推一条汇总。
 * 这是和单条提醒并列的第二类推送，kind 固定为 'report'，用 id 区分时段，
 * 去重 key 也因此独立，不会和单条提醒打架。
 *
 * 三个固定时段（写死，不进设置）：
 *   08:20 早报 —— 未完成汇总（总数 + 逾期 + 按 tag 分组）
 *   12:30 午报 —— 同上（方便午休时看一眼还剩什么）
 *   20:00 晚报 —— 今日完成数 + 明日待办数
 *
 * 口径：未完成 = 所有没做完的待办（含未来几天，不含已取消/已归档）。
 *
 * @return array<int, array{time:string, kind:string, id:string, title:string, body:string}>
 */
/**
 * 每日小结（早报 / 午报 / 小结）。
 *
 * $times 可覆盖三个时刻（v124）：['morning'=>'08:20','noon'=>'12:30','evening'=>'20:00']，
 * 传空字符串表示不发那一条；不传则用内置默认值——旧调用方和旧测试不受影响。
 */
function lb_schedule_reports(array $state, string $date, ?array $times = null): array
{
    $pending = [];   // 未完成（按 tag 分组）
    $total = 0;      // 未完成总数
    $overdue = 0;    // 已逾期
    $doneToday = 0;  // 今日完成
    $tomorrow = 0;   // 明日待办

    $tomorrowDate = date('Y-m-d', strtotime($date . ' +1 day'));

    foreach ((array)($state['tasks'] ?? []) as $t) {
        if (!is_array($t) || !empty($t['archivedAt'])) {
            continue;
        }
        $st = (string)($t['status'] ?? '');
        $due = (string)($t['due'] ?? '');
        if ($st === 'done') {
            if (($t['doneAt'] ?? '') === $date) {
                $doneToday++;
            }
            continue;
        }
        if ($st === 'cancelled') {
            continue;
        }
        /* 未完成 */
        $total++;
        if ($due !== '' && $due < $date) {
            $overdue++;
        }
        if ($due === $tomorrowDate) {
            $tomorrow++;
        }
        $tag = trim((string)($t['tag'] ?? ''));
        if ($tag === '') {
            $tag = '其他';
        }
        $pending[$tag] = ($pending[$tag] ?? 0) + 1;
    }

    $summary = '未完成 ' . $total . ' 项'
        . ($overdue > 0 ? '，已逾期 ' . $overdue . ' 项' : '');
    if ($pending) {
        foreach ($pending as $tag => $n) {
            $summary .= "\n· " . $tag . ' ' . $n . ' 项';
        }
    } else {
        $summary .= "\n· 全部完成，没有待办";
    }

    /* 三个时刻可由用户改（作息颠倒的人 08:20 正在睡觉）；空串 = 不发那一条 */
    $t = is_array($times) ? $times : [];
    $tMorning = array_key_exists('morning', $t) ? (string)$t['morning'] : '08:20';
    $tNoon = array_key_exists('noon', $t) ? (string)$t['noon'] : '12:30';
    $tEvening = array_key_exists('evening', $t) ? (string)$t['evening'] : '20:00';

    $out = [];
    if ($tMorning !== '') {
        $out[] = ['time' => $tMorning, 'kind' => 'report', 'id' => 'morning',
                  'title' => '今日待办早报', 'body' => $summary];
    }
    if ($tNoon !== '') {
        $out[] = ['time' => $tNoon, 'kind' => 'report', 'id' => 'noon',
                  'title' => '待办进度午报', 'body' => $summary];
    }
    if ($tEvening !== '') {
        $out[] = ['time' => $tEvening, 'kind' => 'report', 'id' => 'evening',
                  'title' => '今日小结',
                  'body' => '今日完成 ' . $doneToday . ' 项待办' . "\n"
                      . '明日待办 ' . $tomorrow . ' 条'];
    }
    return $out;
}

/**
 * 自定义通知：用户自己写的文案，按「单次 / 每天 / 每周几 / 每月几号」在指定时刻推。
 *
 * 为什么单独一个函数、不并进 lb_schedule_day：
 * lb_schedule_day 会被 api/ics.php 复用去生成日历日程。自定义通知是「提醒」不是「日程」，
 * 混进去会让订阅的日历里冒出一堆不该有的条目。
 *
 * 去重靠 push_sent 的 slot_key（日期|kind|id|时间）：
 *   单次 —— 只有指定那天会进计划，发过一次就再也不出现；
 *   每天 / 每周 / 每月 —— 每天的计划不同，键里的日期不同，天然各发一次。
 *
 * @return array<int, array{time:string, kind:string, id:string, title:string, body:string}>
 */
function lb_schedule_notices(array $state, string $date): array
{
    if (!lb_ics_is_date($date)) {
        return [];
    }
    $out = [];
    $ts = strtotime($date);
    foreach ((array)($state['notices'] ?? []) as $n) {
        if (!is_array($n)) {
            continue;
        }
        if (($n['on'] ?? true) === false) {
            continue;
        }
        $id = (string)($n['id'] ?? '');
        $text = trim((string)($n['text'] ?? ''));
        $time = (string)($n['time'] ?? '');
        if ($id === '' || $text === '') {
            continue;
        }
        if (!preg_match('/^([01]\d|2[0-3]):[0-5]\d$/', $time)) {
            continue;
        }

        $mode = (string)($n['mode'] ?? 'daily');
        $hit = false;
        if ($mode === 'once') {
            $hit = ((string)($n['date'] ?? '') === $date);
        } elseif ($mode === 'daily') {
            $hit = true;
        } elseif ($mode === 'weekly') {
            $weeks = is_array($n['weeks'] ?? null) ? array_map('intval', $n['weeks']) : [];
            $hit = in_array((int)date('w', $ts), $weeks, true);
        } elseif ($mode === 'monthly') {
            /* 31 号在小月按月末那天发，否则「每月 31 号」在 2/4/6/9/11 月永远不会响。
               这点和待办的重复任务（严格按号）有意不同，通知不该静默消失。 */
            $md = max(1, min(31, (int)($n['monthday'] ?? 1)));
            $hit = ((int)date('j', $ts) === min($md, (int)date('t', $ts)));
        }
        if (!$hit) {
            continue;
        }

        $out[] = [
            'time' => $time,
            'kind' => 'notice',
            'id' => $id,
            'title' => '🔔 自定义提醒',
            'body' => $text,
        ];
    }
    return $out;
}

/**
 * 倒数日提醒：距目标日期还剩 N 天时推一条（N 由 remindDays 指定，0 = 当天）。
 *
 * 只对未来发。日子过去之后「已过去 N 天」照常显示，但不再响——
 * 「已经过去 100 天」这种不是提醒，是回顾，不该占通知。
 *
 * 去重仍靠 push_sent 的 slot_key（日期|kind|id|时间）：不同档位落在不同日期，
 * 天然各发一次，不需要额外状态。
 *
 * 跟 lb_schedule_notices 一样，**不能并进 lb_schedule_day** ——
 * 后者被 api/ics.php 复用生成日历订阅，倒数日不是日程。
 *
 * @return array<int, array{time:string, kind:string, id:string, title:string, body:string}>
 */
function lb_schedule_countdowns(array $state, string $date): array
{
    if (!lb_ics_is_date($date)) {
        return [];
    }
    $out = [];
    $ts = strtotime($date);
    foreach ((array)($state['countdowns'] ?? []) as $c) {
        if (!is_array($c)) {
            continue;
        }
        if (($c['on'] ?? true) === false) {
            continue;
        }
        $id = (string)($c['id'] ?? '');
        $name = trim((string)($c['title'] ?? ''));
        $target = (string)($c['date'] ?? '');
        if ($id === '' || $name === '' || !lb_ics_is_date($target)) {
            continue;
        }
        $time = (string)($c['time'] ?? '');
        if (!preg_match('/^([01]\d|2[0-3]):[0-5]\d$/', $time)) {
            continue;
        }

        /* 目标日期 - 今天。用 round 而不是 floor：跨夏令时的日子会有 23/25 小时，
           floor 会把「还有 1 天」算成 0。 */
        $days = (int)round((strtotime($target) - $ts) / 86400);
        if ($days < 0) {
            continue;
        }
        $remind = is_array($c['remindDays'] ?? null)
            ? array_map('intval', $c['remindDays'])
            : [];
        if (!in_array($days, $remind, true)) {
            continue;
        }

        $note = trim((string)($c['note'] ?? ''));
        $body = ($days === 0 ? '就是今天' : '还有 ' . $days . ' 天')
            . ' · ' . $target
            . ($note !== '' ? "\n" . $note : '');
        $out[] = [
            'time' => $time,
            'kind' => 'countdown',
            'id' => $id,
            'title' => '📅 ' . $name,
            'body' => $body,
        ];
    }
    return $out;
}

/**
 * 还款提醒：清债里每笔债的「每月几号」到了，提前 N 天推一条。
 *
 * 跟 lb_schedule_notices / lb_schedule_countdowns 一样，**不能并进
 * lb_schedule_day**：后者会被 api/ics.php 复用来生成订阅日历，
 * 而还款提醒要跟随 money.notify.on 这个开关。混进去的话，关掉提醒的人
 * 订阅里依然会冒出一堆还款条目。
 *
 * 开关默认关（用户明确要求「提醒非强制」）：
 * money.notify.on 不为 true 就整段不产生任何提醒。
 *
 * 小月按月末：due 是「每月几号」，2 月没有 31 号就落在 28/29。
 * 这点跟前端 dayDebts()、api/ics.php 必须同一口径。
 *
 * @return array<int, array{time:string, kind:string, id:string, title:string, body:string}>
 */
function lb_schedule_debts(array $state, string $date): array
{
    if (!lb_ics_is_date($date)) {
        return [];
    }
    $money = isset($state['money']) && is_array($state['money']) ? $state['money'] : [];
    $nt = isset($money['notify']) && is_array($money['notify']) ? $money['notify'] : [];
    if (($nt['on'] ?? false) !== true) {
        return [];
    }
    $time = (string)($nt['time'] ?? '');
    if (!preg_match('/^([01]\d|2[0-3]):[0-5]\d$/', $time)) {
        $time = '09:00';
    }
    $before = isset($nt['before']) && is_array($nt['before'])
        ? array_map('intval', $nt['before'])
        : [3, 1, 0];

    $ts = strtotime($date);
    $out = [];
    foreach ((array)($money['debts'] ?? []) as $d) {
        if (!is_array($d)) {
            continue;
        }
        $id = (string)($d['id'] ?? '');
        $name = trim((string)($d['name'] ?? ''));
        $bal = (float)($d['balance'] ?? 0);
        /* 已还清的不再提醒 —— 「还剩 0 元」不是提醒，是噪音 */
        if ($id === '' || $name === '' || $bal <= 0.005) {
            continue;
        }
        /* v110：0 / 空 = 没有具体还款日，既不提醒也不排日历 */
        $due = (int)($d['due'] ?? 0);
        if ($due < 1 || $due > 31) {
            continue;
        }

        /* 本月还款日：超出当月天数时按月末 */
        $eff = min($due, (int)date('t', $ts));
        $dueDay = date('Y-m', $ts) . '-' . str_pad((string)$eff, 2, '0', STR_PAD_LEFT);
        if ($dueDay < $date) {
            /* 本月已经过了，看下个月那天 */
            $nextTs = strtotime(date('Y-m-01', $ts) . ' +1 month');
            $eff = min($due, (int)date('t', $nextTs));
            $dueDay = date('Y-m', $nextTs) . '-' . str_pad((string)$eff, 2, '0', STR_PAD_LEFT);
        }
        /* round 不用 floor：跨夏令时那天是 23/25 小时 */
        $days = (int)round((strtotime($dueDay) - $ts) / 86400);
        if ($days < 0 || !in_array($days, $before, true)) {
            continue;
        }

        $body = ($days === 0 ? '就是今天' : '还有 ' . $days . ' 天')
            . ' · ' . $dueDay
            . "\n还剩 ¥" . number_format($bal, 0, '.', '')
            . ' · 最低 ¥' . number_format((float)($d['min'] ?? 0), 0, '.', '');
        $out[] = [
            'time' => $time,
            'kind' => 'debt',
            'id' => $id,
            'title' => '💳 还款 · ' . $name,
            'body' => $body,
        ];
    }
    return $out;
}
