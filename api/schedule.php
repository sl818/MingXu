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

    /* v209：模块启停 —— 与前端 isModuleOn 同语义（四模块 modules[key].on；用药 modulePrefs.meds.on） */
    $modOn = function (array $state, string $key): bool {
        if ($key === 'meds') {
            $mp = isset($state['modulePrefs']['meds']) && is_array($state['modulePrefs']['meds']) ? $state['modulePrefs']['meds'] : [];
            return ($mp['on'] ?? true) !== false;
        }
        $m = isset($state['modules'][$key]) && is_array($state['modules'][$key]) ? $state['modules'][$key] : [];
        return ($m['on'] ?? true) !== false;
    };
    /* ---------------------------------------------------------------- 用药 */
    foreach ((array)($state['meds'] ?? []) as $m) {
        if (!$modOn($state, 'meds')) {
            continue;   // v209：用药停用后不排提醒
        }
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

        /* v235：通知总开关（弹窗「开启提醒」）——关掉不排；按需用药天然无时刻（上面已 continue） */
        if (($m['notify'] ?? true) === false) {
            continue;
        }
        /* 服药方式文案进正文：饭前/饭后 + 间隔（饭后30分钟）；mealOffset 0=立即 */
        $mealText = '';
        $mealTiming = (string)($m['mealTiming'] ?? '');
        if ($mealTiming === 'before' || $mealTiming === 'after') {
            $off = $m['mealOffset'] ?? null;
            $offText = '';
            if ($off === 0 || $off === '0') {
                $offText = '立即';
            } elseif (is_numeric($off) && (int)$off > 0) {
                $offText = (int)$off . '分钟';
            }
            $mealText = ($mealTiming === 'before' ? '饭前' : '饭后') . $offText;
        }
        $notifyNote = trim((string)($m['notifyNote'] ?? ''));
        $npCh = (isset($m['notifyPlan']['channels']) && is_array($m['notifyPlan']['channels']) && $m['notifyPlan']['channels'])
            ? array_values($m['notifyPlan']['channels']) : null;
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
                'body' => $name . ' ' . $amt . $unit . '（每天 ' . $slot . ($mealText !== '' ? ' · ' . $mealText : '') . '）'
                    . ($notifyNote !== '' ? "\n" . $notifyNote : ''),
                /* v211：模板变量用的来源/优先级。只增不改，去重键仍是 日期|kind|id|时间 */
                'source' => 'med',
                'priority' => '紧急',
                /* v235：{服药方式} 模板变量 + 任务级同款渠道交集 */
                'mealText' => $mealText,
                'channels' => $npCh,
            ];
        }
        /* v235：长期疗程复诊日提醒——一次性，当天 09:00，走同一渠道交集 */
        if (($m['courseType'] ?? '') === 'long') {
            $rd = lb_ics_is_date($m['reviewDate'] ?? '') ? (string)$m['reviewDate'] : '';
            if ($rd !== '' && $rd === $date) {
                $out[] = [
                    'time' => '09:00',
                    'kind' => 'med',
                    'id' => $mid . '-review',
                    'title' => '今天复诊',
                    'body' => $name . ' 今天复诊' . ($notifyNote !== '' ? "\n" . $notifyNote : ''),
                    'source' => 'med',
                    'priority' => '紧急',
                    'mealText' => $mealText,
                    'channels' => $npCh,
                ];
            }
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
            /* v211：tag/priority 是任务自身字段；priority 与通知级 priority 不同义 */
            'source' => 'task',
            'priority' => '当日',
            'tag' => (string)($t['tag'] ?? ''),
            'taskPriority' => (string)($t['priority'] ?? ''),
            /* v230：任务级渠道随事件下发（push.php effective_row 与 task 板块取交集） */
            'channels' => (isset($t['notifyPlan']['channels']) && is_array($t['notifyPlan']['channels']) && $t['notifyPlan']['channels'])
                ? array_values($t['notifyPlan']['channels']) : null,
        ];
    }

    /* ---------------------------------------------------------------- 习惯
       v221 批 3：分两条路径。
       · 无 notifyPlan（老数据 + 戒烟旧路径）：原样走 suggestTime + notifyFreq，
         quit 仍不排提醒——行为零变化，老断言不受影响。
       · 有 notifyPlan（2.0 矩阵）：按 h.sched 判定当日是否要求，再按
         notifyPlan 的时间数组逐时间生成排程项；多次型按已完成次数覆盖时间点。 */
    foreach ((array)($state['habits'] ?? []) as $h) {
        if (!is_array($h) || !empty($h['archivedAt'])) {
            continue;
        }
        if (!empty($h['optional']) || !empty($h['med'])
            || in_array((string)($h['id'] ?? ''), ['h_water', 'h_move', 'h_breathe', 'h_drink'], true)) {
            continue;   // 可选项不催；用药类习惯由药品自己提醒；四个健康模块由模块配置接管
        }
        /* 通知开关：默认开，显式关掉才不提醒 */
        if (($h['notify'] ?? true) === false) {
            continue;
        }
        $hid = (string)($h['id'] ?? '');
        if ($hid === '') {
            continue;
        }
        $np = isset($h['notifyPlan']) && is_array($h['notifyPlan']) ? $h['notifyPlan'] : null;
        if ($np === null) {
            /* ============ 旧路径（老数据 + 戒烟，行为零变化） ============ */
            /* 与 ics.php 保持一致：旧戒除类不排提醒，它靠当天“没破戒”来算 */
            if (($h['type'] ?? '') === 'quit') {
                continue;
            }
            $slot = (string)($h['suggestTime'] ?? '');
            if (!preg_match('/^([01]\d|2[0-3]):[0-5]\d$/', $slot)) {
                continue;
            }
            /* 通知频率：daily 每天；weekly 只在 notifyWeekday；monthly 只在 notifyMonthday。 */
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
                'source' => 'habit',
                'priority' => '日常',
                'habitType' => (string)($h['type'] ?? 'build'),
            ];
            continue;
        }

        /* ============ 2.0 矩阵路径（有 notifyPlan） ============ */
        $sched = isset($h['sched']) && is_array($h['sched']) ? $h['sched'] : null;
        $kind = $sched ? (string)($sched['kind'] ?? 'daily') : 'daily';
        $dow = (int)date('w', strtotime($date));   // 0=周日，与前端一致
        $due = true;
        if ($kind === 'weekdays') {
            $days = isset($sched['days']) && is_array($sched['days'])
                ? array_map('intval', $sched['days']) : [];
            $due = in_array($dow, $days, true);
        } elseif ($kind === 'weekly') {
            $due = false;   // 弹性配额不单独排程，未完成项走每日日报
        } elseif ($kind === 'interval') {
            /* 以 anchor 分轮：轮内任一天打卡即本轮完成，剩余日不排（绝不拿上次完成日推算） */
            $iv = max(2, min(60, (int)($sched['intervalDays'] ?? 3)));
            $anchor = preg_match('/^\d{4}-\d{2}-\d{2}$/', (string)($sched['anchor'] ?? ''))
                ? (string)$sched['anchor']
                : substr((string)($h['createdAt'] ?? ''), 0, 10);
            $due = false;
            $doneAny = false;
            if ($anchor !== '' && strtotime($date) >= strtotime($anchor)) {
                $diff = (int)floor((strtotime($date) - strtotime($anchor)) / 86400);
                $roundStart = date('Y-m-d', strtotime($anchor) + ($diff - ($diff % $iv)) * 86400);
                for ($i = 0; $i < $iv; $i++) {
                    $ds = date('Y-m-d', strtotime($roundStart) + $i * 86400);
                    if ($ds > $date) {
                        break;
                    }
                    if (isset($state['checks'][$ds][$hid]) && (float)$state['checks'][$ds][$hid] > 0) {
                        $doneAny = true;
                        break;
                    }
                }
                $due = empty($doneAny);
            }
            unset($doneAny);
        }
        if (!$due) {
            continue;
        }
        /* 当日时间数组：weekdays → notifyPlan.wd[dow]；interval → intervalTime；daily → notifyPlan.daily */
        $times = [];
        if ($kind === 'weekdays') {
            $k = (string)$dow;
            if (isset($np['wd'][$k]) && is_array($np['wd'][$k])) {
                $times = $np['wd'][$k];
            }
        } elseif ($kind === 'interval') {
            $times = [ (string)($np['intervalTime'] ?? '09:00') ];
        } else {
            if (isset($np['daily']) && is_array($np['daily'])) {
                $times = $np['daily'];
            }
        }
        $times = array_values(array_filter($times, function ($t) {
            return preg_match('/^([01]\d|2[0-3]):[0-5]\d$/', (string)$t);
        }));
        sort($times);
        if (!$times) {
            continue;
        }
        $name = trim((string)($h['name'] ?? '习惯'));
        if ($name === '') {
            $name = '习惯';
        }
        $target = max(1, (int)round((float)($h['target'] ?? 1)));
        $unit = (string)($h['unit'] ?? '');
        $count = isset($checks[$hid]) ? (float)$checks[$hid] : 0;
        $notifyNote = trim((string)($h['notifyNote'] ?? ''));
        $icon = (string)($h['icon'] ?? '');
        /* 多次型催促：第 i 个时间点前若已完成次数 ≥ i，该条不发（次数覆盖时间点） */
        $slotIdx = 0;
        foreach ($times as $slot) {
            $slotIdx++;
            if ($count >= $slotIdx) {
                continue;
            }
            $left = max(0, $target - (int)round($count));
            $body = $target > 1
                ? '今天已完成 ' . (string)(int)round($count) . '/' . (string)$target . ' · 还差 ' . (string)$left . ($unit !== '' ? $unit : '次')
                : '今天的习惯还没打卡';
            if ((bool)($h['type'] === 'quit')) {
                $body = $target > 1
                    ? '今天已失守 ' . (string)(int)round($count) . '/' . (string)$target . ' 次'
                    : '今天还没打卡 · 守住它';
            }
            if ($notifyNote !== '') {
                $body .= "\n" . $notifyNote;
            }
            $out[] = [
                'time' => (string)$slot,
                'kind' => 'habit',
                'id' => $hid,
                'title' => ($icon !== '' ? $icon . ' ' : '') . $name,
                'body' => $body,
                'source' => 'habit',
                'priority' => '日常',
                'habitType' => (string)($h['type'] ?? 'build'),
                /* 批 4：习惯级渠道随事件下发，push.php 的 effective_row 与板块矩阵取交集；
                   无配置时不带该字段（回落板块默认） */
                'channels' => (isset($np['channels']) && is_array($np['channels']) && $np['channels'])
                    ? array_values($np['channels']) : null,
            ];
        }
    }

    /* ---------------------------------------------------------------- 健康模块
       水/运动/478 的配置在 state.modules；戒烟不提醒。口径与上面的习惯一致。 */
    $modules = isset($state['modules']) && is_array($state['modules']) ? $state['modules'] : [];
    $modRec = ['water' => 'h_water', 'move' => 'h_move', 'breathe' => 'h_breathe'];
    foreach ($modRec as $mkey => $hid) {
        $m = $modules[$mkey] ?? null;
        if (!$modOn($state, $mkey)) {
            continue;   // v209：停用的模块不排提醒
        }
        if (!is_array($m)) {
            continue;
        }
        if (($m['on'] ?? true) === false) {
            continue;
        }
        if (($m['notify'] ?? true) === false) {
            continue;
        }
        $name = trim((string)($m['name'] ?? ''));
        if ($name === '') {
            $name = '健康习惯';
        }
        $icon = (string)($m['icon'] ?? '');

        /* 喝水：按 notifyMode 生成多个时间点（v173） */
        if ($mkey === 'water') {
            $cups = max(1, (int)($m['cups'] ?? 9));
            $done = isset($checks[$hid]) ? (int)$checks[$hid] : 0;
            foreach (lb_water_slots($m, $cups) as $i => $t) {
                if ($done >= $i + 1) {
                    continue;   // 已喝到第 i+1 杯，就不再催这一杯
                }
                $left = max(0, $cups - $done);
                $body = $left > 1
                    ? '该喝水了 · 今天还差 ' . (string)$left . ' 杯'
                    : '该喝水了 · 今天还差最后一杯';
                $out[] = [
                    'time' => $t,
                    'kind' => 'habit',
                    'id' => $hid,
                    'title' => ($icon !== '' ? $icon . ' ' : '') . $name,
                    'body' => $body,
                    /* v211：喝水不再与普通习惯共用 source */
                    'source' => 'water',
                    'priority' => '日常',
                ];
            }
            continue;
        }

        /* v184：运动实例级提醒 —— 每个运动有自己的「运动开始时间」，
           按它自己的频率排（每周选日运动的只在选中的星期提醒）；
           今天已经记录过的运动不再催。
           只要有实例设了开始时间，就不再用模块级那条，免得提醒两遍。 */
        if ($mkey === 'move') {
            $sports = isset($m['sports']) && is_array($m['sports']) ? $m['sports'] : [];
            $records = isset($m['records']) && is_array($m['records']) ? $m['records'] : [];
            $instSlots = [];
            foreach ($sports as $sp) {
                if (!is_array($sp)) {
                    continue;
                }
                $st = (string)($sp['startTime'] ?? '');
                if (!preg_match('/^([01]\d|2[0-3]):[0-5]\d$/', $st)) {
                    continue;
                }
                $spid = (string)($sp['id'] ?? '');
                $spkey = (string)($sp['key'] ?? 'steps');
                if ((string)($sp['freqKind'] ?? 'daily') === 'weekly') {
                    $sel = [];
                    foreach ((array)($sp['weekSel'] ?? []) as $w) {
                        $sel[] = (int)$w;
                    }
                    if (!in_array((int)date('w', strtotime($date)), $sel, true)) {
                        continue;
                    }
                }
                $done = false;
                foreach ($records as $r) {
                    if (!is_array($r) || (string)($r['d'] ?? '') !== $date) {
                        continue;
                    }
                    $rid = (string)($r['sportId'] ?? '');
                    $mine = $rid !== '' ? ($rid === $spid) : ((string)($r['key'] ?? '') === $spkey);
                    if ($mine) {
                        $done = true;
                        break;
                    }
                }
                if ($done) {
                    continue;
                }
                $instSlots[] = [
                    'time' => $st,
                    'name' => trim((string)($sp['name'] ?? '')) ?: '运动',
                    'icon' => (string)($sp['icon'] ?? ''),
                    'id' => $spid !== '' ? ('sport-' . $spid) : $hid,
                    /* v216：sport 带实例 id（instances 的键）；mode 保留模式 key 供展示 */
                    'sport' => $spid !== '' ? $spid : $spkey,
                    'mode' => $spkey,
                ];
            }
            if ($instSlots) {
                foreach ($instSlots as $is) {
                    $out[] = [
                        'time' => $is['time'],
                        'kind' => 'habit',
                        'id' => $is['id'],
                        'title' => ($is['icon'] !== '' ? $is['icon'] . ' ' : '') . $is['name'],
                        'body' => '该开始运动了',
                        /* v211：运动实例带自己的模式 key，模板/板块映射要用 */
                        'source' => 'move',
                        'priority' => '日常',
                        'sport' => $is['sport'],
                        'mode' => $is['mode'] ?? $is['sport'],
                    ];
                }
                continue;
            }
        }

        /* v194：478 呼吸 —— 每天固定时间推送，做几组就有几个时间点。
           第 N 个提醒对应第 N 组：当天已经做完 N 组就不再催第 N 个。
           v200：组数上限收到 5；同一时刻只出一条（推送去重键含时刻，重复会让后一条被吃掉）。 */
        if ($mkey === 'breathe') {
            $times = isset($m['notifyTimes']) && is_array($m['notifyTimes']) ? $m['notifyTimes'] : [];
            $groups = max(1, min(LB_BREATHE_MAX_GROUPS, (int)($m['groups'] ?? 1)));
            /* v202：先洗一遍 —— 时间点可能「非空但全是脏值」（手改坏了 / 老数据）。
               一个合法值都没有就按「每天几组」兜底，别掉进下面那条通用 suggestTime 单条逻辑：
               那样前端与 api/ics.php 出 N 条、这里只出 1 条，两边口径就不一致了。 */
            $clean = [];
            foreach ($times as $t) {
                $t = (string)$t;
                if (preg_match('/^([01]\d|2[0-3]):[0-5]\d$/', $t)) {
                    $clean[] = $t;
                }
            }
            $times = count($clean) ? $clean : lb_breathe_default_times($groups);
            $doneN = isset($checks[$hid]) ? (int)(float)$checks[$hid] : 0;
            $any = false;
            $seen = [];
            $slotNo = 0;
            foreach ($times as $t) {
                if ($slotNo >= $groups) {
                    break;   // 最多到「每天几组」那么多条，脏数据里多出来的时间点不推
                }
                $slot = (string)$t;
                if (!preg_match('/^([01]\d|2[0-3]):[0-5]\d$/', $slot)) {
                    continue;
                }
                if (isset($seen[$slot])) {
                    continue;
                }
                $seen[$slot] = true;
                $slotNo++;
                $any = true;
                if ($doneN >= $slotNo) {
                    continue;   // 第 $slotNo 组已经做完了，就不再催这一组
                }
                $left = max(0, $groups - $doneN);
                $body = $left > 1
                    ? '该做 478 呼吸了 · 今天还差 ' . (string)$left . ' 组'
                    : '该做 478 呼吸了 · 今天还差最后一组';
                $out[] = [
                    'time' => $slot,
                    'kind' => 'habit',
                    'id' => $hid,
                    'title' => ($icon !== '' ? $icon . ' ' : '') . $name . ' · 第 ' . (string)$slotNo . ' 组',
                    'body' => $body,
                    /* v211：478 独立来源 */
                    'source' => 'breathe',
                    'priority' => '日常',
                ];
            }
            if ($any) {
                continue;
            }
        }

        /* 运动 / 478：沿用原 suggestTime 单条逻辑 */
        $slot = (string)($m['suggestTime'] ?? '');
        if (!preg_match('/^([01]\d|2[0-3]):[0-5]\d$/', $slot)) {
            continue;
        }
        $freq = (string)($m['notifyFreq'] ?? 'daily');
        if ($freq === 'weekly') {
            $wd = max(0, min(6, (int)($m['notifyWeekday'] ?? 1)));
            if ((int)date('w', strtotime($date)) !== $wd) {
                continue;
            }
        } elseif ($freq === 'monthly') {
            $md = max(1, min(31, (int)($m['notifyMonthday'] ?? 1)));
            if ((int)date('j', strtotime($date)) !== $md) {
                continue;
            }
        }
        /* 今天已经打过卡就不再催 */
        if (isset($checks[$hid]) && (float)$checks[$hid] > 0) {
            continue;
        }
        $target = $mkey === 'move' ? max(1, (int)($m['times'] ?? 1)) : max(1, (int)($m['groups'] ?? 1));
        $unit = $mkey === 'move' ? '次' : '组';
        $body = $target > 1
            ? '今天还差 ' . (string)$target . $unit
            : '今天的习惯还没打卡';
        $out[] = [
            'time' => $slot,
            'kind' => 'habit',
            'id' => $hid,
            'title' => ($icon !== '' ? $icon . ' ' : '') . $name,
            'body' => $body,
            /* v211：模块兜底路径按 $mkey 给来源，别退回 habit */
            'source' => $mkey,
            'priority' => '日常',
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
                  'title' => '今日待办早报', 'body' => $summary,
                  'source' => 'report', 'priority' => '日常'];
    }
    if ($tNoon !== '') {
        $out[] = ['time' => $tNoon, 'kind' => 'report', 'id' => 'noon',
                  'title' => '待办进度午报', 'body' => $summary,
                  'source' => 'report', 'priority' => '日常'];
    }
    if ($tEvening !== '') {
        $out[] = ['time' => $tEvening, 'kind' => 'report', 'id' => 'evening',
                  'title' => '今日小结',
                  'body' => '今日完成 ' . $doneToday . ' 项待办' . "\n"
                      . '明日待办 ' . $tomorrow . ' 条',
                  'source' => 'report', 'priority' => '日常'];
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
            'source' => 'notice',
            'priority' => '当日',
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
            'source' => 'countdown',
            'priority' => '当日',
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
    /* v211：清债模块停用则整段不产生提醒（与前端 isModuleOn 同语义） */
    if (($state['money']['on'] ?? true) === false) {
        return [];
    }
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
        /* v237：债务级开关（无还款日时 normalize 已强制关；这里再兜底） */
        if (($d['notify'] ?? true) === false) {
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
            'source' => 'debt',
            'priority' => '紧急',
            /* v237：债务级渠道随事件下发（push.php 与 debt 板块取交集） */
            'channels' => (isset($d['notifyPlan']['channels']) && is_array($d['notifyPlan']['channels']) && $d['notifyPlan']['channels'])
                ? array_values($d['notifyPlan']['channels']) : null,
            /* 本次提醒对应的还款日（不是每月的号数） */
            'due' => $dueDay,
        ];
    }
    return $out;
}
