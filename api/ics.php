<?php
/* 明序 · 日历订阅（iCalendar 生成）
 *
 * 与前端 index.html 里的 buildICS() 输出等价，但只管「给日历 App 订阅」这条路：
 * 系统日历按 URL 定期来拉，所以内容必须由服务端生成。
 * 时间一律按 Asia/Shanghai 计算，不依赖任何客户端的时区设置。
 *
 * 三个必须守住的点（踩过）：
 *   1. DTSTART 用 TZID + 本地时刻，不要换算成 UTC。
 *      07:30 换 UTC 是前一天 23:30，带 BYDAY 的每周重复会被算到前一天。
 *   2. RRULE 的 UNTIL 必须是 UTC。
 *   3. 推进日期要保留时分（modify('+1 day')），别用日期重置的写法。
 */
if (!defined('LIFEBOARD_API')) {
    http_response_code(404);
    exit;
}

const LB_ICS_TZ = 'Asia/Shanghai';
const LB_ICS_DOMAIN = 'wanfeng-todo';
const LB_ICS_WEEK = ['SU', 'MO', 'TU', 'WE', 'TH', 'FR', 'SA'];

function lb_ics_tz(): DateTimeZone
{
    static $tz = null;
    if ($tz === null) {
        $tz = new DateTimeZone(LB_ICS_TZ);
    }
    return $tz;
}

function lb_ics_escape(string $v): string
{
    $v = str_replace('\\', '\\\\', $v);
    $v = str_replace([';', ','], ['\\;', '\\,'], $v);
    return str_replace(["\r\n", "\r", "\n"], '\\n', $v);
}

/* 按字节截取，但绝不切断 UTF-8 多字节字符。
   刻意不用 mb_strcut：有些精简环境没装 mbstring，一调就 fatal，
   而这里处理的几乎全是中文，切坏了会在日历里显示成乱码。 */
function lb_ics_cut(string $s, int $start, int $len): string
{
    $piece = substr($s, $start, $len);
    $n = strlen($piece);
    if ($n === 0) {
        return '';
    }
    $i = $n - 1;
    $trail = 0;
    while ($i >= 0 && (ord($piece[$i]) & 0xC0) === 0x80) {
        $i--;
        $trail++;
    }
    if ($i < 0) {
        return '';
    }
    $lead = ord($piece[$i]);
    if ($lead < 0x80) {
        $need = 1;
    } elseif (($lead & 0xE0) === 0xC0) {
        $need = 2;
    } elseif (($lead & 0xF0) === 0xE0) {
        $need = 3;
    } elseif (($lead & 0xF8) === 0xF0) {
        $need = 4;
    } else {
        $need = 1;
    }
    if ($trail + 1 < $need) {
        return substr($piece, 0, $i);   // 末尾这个字符还差几个字节，整块砍掉
    }
    return $piece;
}

/* RFC 5545 折行：每行不超过 75 字节，续行以单个空格开头 */
function lb_ics_fold(string $line): string
{
    if (strlen($line) <= 75) {
        return $line;
    }
    $out = [];
    $head = lb_ics_cut($line, 0, 74);
    if ($head === '') {
        return $line;
    }
    $out[] = $head;
    $pos = strlen($head);
    $total = strlen($line);
    while ($pos < $total) {
        $piece = lb_ics_cut($line, $pos, 73);
        if ($piece === '') {
            break;
        }
        $out[] = ' ' . $piece;
        $pos += strlen($piece);
    }
    return implode("\r\n", $out);
}

/* 本地时刻，配合 DTSTART;TZID 使用 */
function lb_ics_local(DateTimeImmutable $d): string
{
    return $d->format('Ymd\THis');
}

/* UTC 时刻，带 Z；RRULE 的 UNTIL 与 DTSTAMP 用它 */
function lb_ics_utc(DateTimeImmutable $d): string
{
    return $d->setTimezone(new DateTimeZone('UTC'))->format('Ymd\THis\Z');
}

function lb_ics_event(string $uid, DateTimeImmutable $start, DateTimeImmutable $end,
                      string $summary, string $desc, string $rrule): string
{
    $lines = [
        'BEGIN:VEVENT',
        'UID:' . $uid . '@' . LB_ICS_DOMAIN,
        'DTSTAMP:' . lb_ics_utc(new DateTimeImmutable('now', new DateTimeZone('UTC'))),
        'DTSTART;TZID=' . LB_ICS_TZ . ':' . lb_ics_local($start),
        'DTEND;TZID=' . LB_ICS_TZ . ':' . lb_ics_local($end),
        'SUMMARY:' . lb_ics_escape($summary),
        'DESCRIPTION:' . lb_ics_escape($desc !== '' ? $desc : '来自 明序'),
        'TRANSP:TRANSPARENT',
    ];
    if ($rrule !== '') {
        $lines[] = 'RRULE:' . $rrule;
    }
    $lines[] = 'BEGIN:VALARM';
    $lines[] = 'TRIGGER:-PT0M';
    $lines[] = 'ACTION:DISPLAY';
    $lines[] = 'DESCRIPTION:' . lb_ics_escape($summary);
    $lines[] = 'END:VALARM';
    $lines[] = 'END:VEVENT';
    return implode("\r\n", array_map('lb_ics_fold', $lines));
}

function lb_ics_vtimezone(): string
{
    /* 北京时间固定 +8、没有夏令时，一个 STANDARD 块足够，
       不用跟着日历 App 的时区库走 */
    $lines = [
        'BEGIN:VTIMEZONE',
        'TZID:' . LB_ICS_TZ,
        'BEGIN:STANDARD',
        'DTSTART:19700101T000000',
        'TZOFFSETFROM:+0800',
        'TZOFFSETTO:+0800',
        'TZNAME:CST',
        'END:STANDARD',
        'END:VTIMEZONE',
    ];
    return implode("\r\n", array_map('lb_ics_fold', $lines));
}

function lb_ics_is_date($v): bool
{
    if (!is_string($v) || !preg_match('/^(\d{4})-(\d{2})-(\d{2})$/', $v, $m)) {
        return false;
    }
    return checkdate((int)$m[2], (int)$m[3], (int)$m[1]);
}

function lb_ics_day(string $date): DateTimeImmutable
{
    $d = DateTimeImmutable::createFromFormat('!Y-m-d', $date, lb_ics_tz());
    return $d instanceof DateTimeImmutable ? $d : new DateTimeImmutable('today', lb_ics_tz());
}

function lb_ics_clock($v, string $fallback): array
{
    $v = is_string($v) ? $v : '';
    if (!preg_match('/^([01]\d|2[0-3]):([0-5]\d)$/', $v, $m)) {
        $v = $fallback;
        preg_match('/^([01]\d|2[0-3]):([0-5]\d)$/', $v, $m);
    }
    return [(int)$m[1], (int)$m[2]];
}

/**
 * 喝水模块的提醒时间点（v173）。
 * - notifyMode=daily：取 notifyDailyTimes 的前 notifyDailyCount 个（早/中/晚）。
 * - notifyMode=each（默认）：在 notifyStart~notifyEnd 之间按杯数均分。
 * schedule.php 通过 require 复用本函数，与前端 buildICS 口径一致。
 *
 * @return array<int, string>  HH:MM 时间点列表（升序）
 */
function lb_water_slots(array $m, int $cups): array
{
    $mode = (string)($m['notifyMode'] ?? 'each');
    if ($mode === 'daily') {
        $n = max(1, min(3, (int)($m['notifyDailyCount'] ?? 2)));
        $dt = isset($m['notifyDailyTimes']) && is_array($m['notifyDailyTimes']) ? $m['notifyDailyTimes'] : [];
        $names = ['morning', 'noon', 'afternoon'];
        $slots = [];
        for ($i = 0; $i < $n; $i++) {
            $t = (string)($dt[$names[$i]] ?? '');
            if (preg_match('/^([01]\d|2[0-3]):[0-5]\d$/', $t)) {
                $slots[] = $t;
            }
        }
        return $slots;
    }
    $start = (string)($m['notifyStart'] ?? '08:00');
    $end = (string)($m['notifyEnd'] ?? '21:00');
    if (!preg_match('/^([01]\d|2[0-3]):[0-5]\d$/', $start, $sm)
        || !preg_match('/^([01]\d|2[0-3]):[0-5]\d$/', $end, $em)) {
        return [];
    }
    $s = (int)$sm[1] * 60 + (int)$sm[2];
    $e = (int)$em[1] * 60 + (int)$em[2];
    $total = $e > $s ? $e - $s : $e - $s + 1440;
    $step = $cups > 1 ? $total / ($cups - 1) : 0;
    $slots = [];
    for ($i = 0; $i < $cups; $i++) {
        $mm = ($s + (int)round($step * $i)) % 1440;
        $slots[] = sprintf('%02d:%02d', intdiv($mm, 60), $mm % 60);
    }
    return $slots;
}

/* v194：478 提醒的默认时间点 —— 与前端 breatheDefaultTimes() 同口径：
   每天几组就在 07:00–21:00 之间铺开、落到 5 分钟整；只有 1 组时给 15:00。
   三处（前端 / api/ics.php / api/schedule.php）必须一致，否则订阅出来的
   日历和页面提醒对不上（UID 一个带序号一个不带）。 */
function lb_breathe_default_times(int $k): array
{
    $k = max(1, min(12, $k));
    $from = 7 * 60;
    $to = 21 * 60;
    $out = [];
    for ($i = 0; $i < $k; $i++) {
        /* 先落到 5 分钟刻度再转 HH:MM：除法必须在加法外面，
           写成 round($from + (...)/5)*5 会算出 35:00 / 45:30 这种非法时间。 */
        $mm = $k === 1
            ? 15 * 60
            : (int)(round(($from + ($to - $from) * ($i / ($k - 1))) / 5) * 5);
        $out[] = sprintf('%02d:%02d', intdiv($mm, 60) % 24, $mm % 60);
    }
    return $out;
}

/* 订阅地址无效时输出一个「空日历」而不是 404。
   原因：线上 Nginx 配了 error_page 404，会把 PHP 的 404 换成自己的 HTML 页面。
   日历客户端收到 HTML 只会报「格式错误 / 无法添加」，比空日历还难排查。
   返回一个合法但没事件的日历，客户端会正常添加，日历名里直接写清问题。 */
function lb_ics_emit_empty(string $why): void
{
    $lines = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//WanfengTodo//Reminder//CN',
        'CALSCALE:GREGORIAN',
        'X-WR-CALNAME:' . lb_ics_escape('明序（' . $why . '）'),
        'X-WR-TIMEZONE:' . LB_ICS_TZ,
        'REFRESH-INTERVAL;VALUE=DURATION:PT6H',
        'X-PUBLISHED-TTL:PT6H',
        'END:VCALENDAR',
    ];
    $text = implode("\r\n", array_map('lb_ics_fold', $lines)) . "\r\n";
    http_response_code(200);
    header('Content-Type: text/calendar; charset=utf-8');
    header('Content-Length: ' . strlen($text));
    header('Cache-Control: private, max-age=300');
    header('X-Content-Type-Options: nosniff');
    echo $text;
    exit;
}

/* 主流程：把一份 state 转成 iCalendar 文本 */
function lb_ics_build(array $state, ?DateTimeImmutable $now = null): array
{
    $now = $now !== null ? $now : new DateTimeImmutable('now', lb_ics_tz());
    $today = $now->format('Y-m-d');
    $todayDate = lb_ics_day($today);
    $out = [];
    $count = 0;

    $head = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//WanfengTodo//Reminder//CN',
        'CALSCALE:GREGORIAN',
        /* 不写 METHOD:PUBLISH：METHOD 是 iTIP 消息（会议邀请）用的，
           订阅源带上它，部分客户端会当成一次性邀请而不是可订阅的日历 */
        'X-WR-CALNAME:' . lb_ics_escape('明序 提醒'),
        'X-WR-TIMEZONE:' . LB_ICS_TZ,
        'REFRESH-INTERVAL;VALUE=DURATION:PT6H',
        'X-PUBLISHED-TTL:PT6H',
    ];
    $out[] = implode("\r\n", array_map('lb_ics_fold', $head));
    $out[] = lb_ics_vtimezone();

    /* ---- 用药：每个服用时刻一条每日重复，有停药日就截止到那天 ---- */
    $meds = isset($state['meds']) && is_array($state['meds']) ? $state['meds'] : [];
    foreach ($meds as $m) {
        if (!is_array($m) || ($m['status'] ?? '') !== 'active') {
            continue;
        }
        /* 备用药按需服用，没有固定时刻，不该进日历 */
        if (($m['courseType'] ?? '') === 'prn') {
            continue;
        }
        $times = isset($m['times']) && is_array($m['times']) ? $m['times'] : [];
        $times = array_values(array_filter($times, static function ($t) {
            return is_string($t) && preg_match('/^([01]\d|2[0-3]):[0-5]\d$/', $t);
        }));
        if (!$times) {
            continue;
        }
        $startDay = lb_ics_is_date($m['startDate'] ?? '') ? (string)$m['startDate'] : $today;
        /* 只有短期疗程才看结束日；长期服药填了 endDate 也不该提前停 */
        $endDay = (($m['courseType'] ?? '') === 'short' && lb_ics_is_date($m['endDate'] ?? ''))
            ? (string)$m['endDate'] : '';
        $amount = (int)($m['doseAmount'] ?? 0);
        if ($amount <= 0) {
            $amount = 1;
        }
        $unit = (string)($m['doseUnit'] ?? '');
        if ($unit === '') {
            $unit = (string)($m['form'] ?? '');
        }
        if ($unit === '') {
            $unit = '片';
        }
        $name = (string)($m['name'] ?? '用药');
        $note = (string)($m['note'] ?? '');

        foreach ($times as $t) {
            [$hh, $mm] = lb_ics_clock($t, '08:00');
            $base = lb_ics_day($startDay);
            $start = $base->setTime($hh, $mm);
            while ($start <= $now) {
                $start = $start->modify('+1 day');
            }
            $rrule = 'FREQ=DAILY';
            if ($endDay !== '') {
                $untilDate = lb_ics_day($endDay)->setTime($hh, $mm)->modify('+15 minutes');
                if ($untilDate < $start) {
                    continue;   // 疗程已经结束
                }
                $rrule .= ';UNTIL=' . lb_ics_utc($untilDate);
            }
            $end = $start->modify('+15 minutes');
            $out[] = lb_ics_event(
                'med-' . (string)($m['id'] ?? '') . '-' . str_replace(':', '', $t),
                $start, $end,
                '💊 ' . $name . ' ' . $amount . $unit,
                $note !== '' ? $note : ('每天 ' . $t),
                $rrule
            );
            $count++;
        }
    }

    /* ---- 待办：单次任务只在还没过点时进日历；重复任务用 RRULE ---- */
    $tasks = isset($state['tasks']) && is_array($state['tasks']) ? $state['tasks'] : [];
    foreach ($tasks as $t) {
        if (!is_array($t) || !empty($t['archivedAt'])
            || in_array(($t['status'] ?? ''), ['done', 'cancelled'], true)) {
            continue;
        }
        /* 通知开关：默认开，显式关掉才不提醒 */
        if (($t['notify'] ?? true) === false) {
            continue;
        }
        if (!lb_ics_is_date($t['due'] ?? '')) {
            continue;
        }
        $due = (string)$t['due'];
        $dueDate = lb_ics_day($due);
        $repeat = in_array(($t['repeat'] ?? 'none'), ['daily', 'weekly', 'monthly'], true)
            ? (string)$t['repeat'] : 'none';
        $title = (string)($t['title'] ?? '待办');
        $note = (string)($t['note'] ?? '');

        /* 日历是「日程」语义：填了开始时间就按它画，否则退回通知时间（默认 09:00） */
        $timeSrc = (string)($t['startTime'] ?? '');
        if ($timeSrc === '') {
            $timeSrc = (string)($t['notifyTime'] ?? '');
        }
        [$hh, $mm] = lb_ics_clock($timeSrc, '09:00');
        /* 有真实时长就按它画，否则沿用 15 分钟的短块 */
        $durMin = (int)($t['duration'] ?? 0);
        if ($durMin < 15 || $durMin > 720) {
            $durMin = 15;
        }

        if ($repeat === 'none') {
            if ($due < $today) {
                continue;   // 逾期的交给页内提醒，别塞满日历
            }
            $start = $dueDate->setTime($hh, $mm);
            if ($start <= $now) {
                continue;
            }
            $rrule = '';
        } else {
            $start = $dueDate->setTime($hh, $mm);
            if ($repeat === 'daily') {
                $rrule = 'FREQ=DAILY';
            } elseif ($repeat === 'weekly') {
                $wd = isset($t['repeatWeekday']) && is_numeric($t['repeatWeekday'])
                    ? (int)$t['repeatWeekday'] : (int)$dueDate->format('w');
                $wd = max(0, min(6, $wd));
                $rrule = 'FREQ=WEEKLY;BYDAY=' . LB_ICS_WEEK[$wd];
            } else {
                $dom = isset($t['repeatDay']) && is_numeric($t['repeatDay'])
                    ? (int)$t['repeatDay'] : (int)$dueDate->format('j');
                $dom = max(1, min(31, $dom));
                $rrule = 'FREQ=MONTHLY;BYMONTHDAY=' . $dom;
            }
            $guard = 0;
            while ($start <= $now && $guard < 400) {
                if ($repeat === 'daily') {
                    $start = $start->modify('+1 day');
                } elseif ($repeat === 'weekly') {
                    $start = $start->modify('+7 days');
                } else {
                    $start = $start->modify('+1 month');
                }
                $guard++;
            }
        }
        $out[] = lb_ics_event(
            'task-' . (string)($t['id'] ?? ''),
            $start, $start->modify('+' . $durMin . ' minutes'),
            '📌 ' . $title, $note, $rrule
        );
        $count++;
    }

    /* ---- 习惯：只导出填了建议时间的 ---- */
    $habits = isset($state['habits']) && is_array($state['habits']) ? $state['habits'] : [];
    foreach ($habits as $h) {
        if (!is_array($h) || !empty($h['archivedAt'])) {
            continue;
        }
        if (!empty($h['med']) || !empty($h['optional']) || ($h['type'] ?? '') === 'quit'
            || in_array((string)($h['id'] ?? ''), ['h_water', 'h_move', 'h_breathe', 'h_drink'], true)) {
            continue;
        }
        /* 通知开关：默认开 */
        if (($h['notify'] ?? true) === false) {
            continue;
        }
        $st = is_string($h['suggestTime'] ?? '') ? (string)$h['suggestTime'] : '';
        if (!preg_match('/^([01]\d|2[0-3]):([0-5]\d)$/', $st, $mm)) {
            continue;
        }
        $start = $todayDate->setTime((int)$mm[1], (int)$mm[2]);
        /* 频率：weekly/monthly 用对应 RRULE 和推进步长 */
        $freq = (string)($h['notifyFreq'] ?? 'daily');
        $rrule = 'FREQ=DAILY';
        $step = '+1 day';
        if ($freq === 'weekly') {
            $wd = max(0, min(6, (int)($h['notifyWeekday'] ?? 1)));
            $rrule = 'FREQ=WEEKLY;BYDAY=' . LB_ICS_WEEK[$wd];
            $step = '+7 days';
        } elseif ($freq === 'monthly') {
            $md = max(1, min(31, (int)($h['notifyMonthday'] ?? 1)));
            $rrule = 'FREQ=MONTHLY;BYMONTHDAY=' . $md;
            $step = '+1 month';
        }
        while ($start <= $now) {
            $start = $start->modify($step);
        }
        $icon = (string)($h['icon'] ?? '🔔');
        $name = (string)($h['name'] ?? '习惯');
        $out[] = lb_ics_event(
            'habit-' . (string)($h['id'] ?? ''),
            $start, $start->modify('+15 minutes'),
            $icon . ' ' . $name, (string)($h['note'] ?? ''), $rrule
        );
        $count++;
    }

    /* ---- 健康模块（水/运动/478）：配置在 state.modules；戒烟不提醒。
       喝水按 notifyMode 拆成多个时间点（v173）；运动/478 仍是单条 suggestTime。 ---- */
    $modules = isset($state['modules']) && is_array($state['modules']) ? $state['modules'] : [];
    $modRec = ['water' => 'h_water', 'move' => 'h_move', 'breathe' => 'h_breathe'];
    foreach ($modRec as $mkey => $hid) {
        $m = $modules[$mkey] ?? null;
        if (!is_array($m)) {
            continue;
        }
        if (($m['on'] ?? true) === false) {
            continue;
        }
        if (($m['notify'] ?? true) === false) {
            continue;
        }
        $icon = (string)($m['icon'] ?? '🔔');
        $name = (string)($m['name'] ?? '健康');
        $note = (string)($m['note'] ?? '');

        /* 喝水：按 notifyMode 拆成多个时间点（v173） */
        if ($mkey === 'water') {
            $cups = max(1, (int)($m['cups'] ?? 9));
            foreach (lb_water_slots($m, $cups) as $i => $t) {
                [$hh, $mm] = array_map('intval', explode(':', $t));
                $start = $todayDate->setTime($hh, $mm);
                if ($start <= $now) {
                    $start = $start->modify('+1 day');
                }
                $out[] = lb_ics_event(
                    'habit-' . $hid . '-' . ($i + 1),
                    $start, $start->modify('+15 minutes'),
                    $icon . ' ' . $name . ' · 第 ' . ($i + 1) . ' 杯', $note, 'FREQ=DAILY'
                );
                $count++;
            }
            continue;
        }

        /* v184：运动实例级提醒 —— 每个运动有自己的「运动开始时间」，
           按它自己的频率生成日历事件；有实例时间就不再用模块级那条。 */
        if ($mkey === 'move') {
            $sports = isset($m['sports']) && is_array($m['sports']) ? $m['sports'] : [];
            $instCount = 0;
            foreach ($sports as $sp) {
                if (!is_array($sp)) {
                    continue;
                }
                $st = (string)($sp['startTime'] ?? '');
                if (!preg_match('/^([01]\d|2[0-3]):([0-5]\d)$/', $st, $mm)) {
                    continue;
                }
                $spid = (string)($sp['id'] ?? '');
                $rrule = 'FREQ=DAILY';
                $step = '+1 day';
                if ((string)($sp['freqKind'] ?? 'daily') === 'weekly') {
                    $sel = [];
                    foreach ((array)($sp['weekSel'] ?? []) as $w) {
                        $sel[] = (int)$w;
                    }
                    if (!count($sel)) {
                        continue;
                    }
                    $days = [];
                    foreach ($sel as $w) {
                        $days[] = LB_ICS_WEEK[max(0, min(6, $w))];
                    }
                    $rrule = 'FREQ=WEEKLY;BYDAY=' . implode(',', $days);
                    $step = '+7 days';
                }
                $start = (clone $todayDate)->setTime((int)$mm[1], (int)$mm[2]);
                while ($start <= $now) {
                    $start = $start->modify($step);
                }
                $spname = trim((string)($sp['name'] ?? '')) ?: '运动';
                $spicon = (string)($sp['icon'] ?? '');
                $out[] = lb_ics_event(
                    'sport-' . ($spid !== '' ? $spid : $hid),
                    $start, $start->modify('+15 minutes'),
                    ($spicon !== '' ? $spicon . ' ' : '') . $spname, $note, $rrule
                );
                $count++;
                $instCount++;
            }
            if ($instCount > 0) {
                continue;
            }
        }

        /* v194：478 呼吸 —— 每天固定时间推送，做几组就有几个时间点。
           口径与前端 buildICS 一致：habit-h_breathe-1 / -2 / ... */
        if ($mkey === 'breathe') {
            $times = isset($m['notifyTimes']) && is_array($m['notifyTimes']) ? $m['notifyTimes'] : [];
            /* v194：notifyTimes 为空时按「每天几组」算默认时间点 ——
               前端 breatheDefaultTimes() 就是这么兜底的（7:00~21:00 之间均分，取 5 分钟整），
               后端不兜底的话，同一件事会变成「前端 habit-h_breathe-1 / 后端 habit-h_breathe」，
               订阅出来的日历和页面日历对不上。 */
            if (!count($times)) {
                $times = lb_breathe_default_times(max(1, min(12, (int)($m['groups'] ?? 1))));
            }
            $bn = 0;
            foreach ($times as $i => $t) {
                $t = (string)$t;
                if (!preg_match('/^([01]\d|2[0-3]):([0-5]\d)$/', $t, $mm)) {
                    continue;
                }
                $start = $todayDate->setTime((int)$mm[1], (int)$mm[2]);
                if ($start <= $now) {
                    $start = $start->modify('+1 day');
                }
                $out[] = lb_ics_event(
                    'habit-' . $hid . '-' . ($i + 1),
                    $start, $start->modify('+15 minutes'),
                    $icon . ' ' . $name . ' · 第 ' . ($i + 1) . ' 组', $note, 'FREQ=DAILY'
                );
                $count++;
                $bn++;
            }
            if ($bn > 0) {
                continue;
            }
        }

        /* 运动 / 478：原单条 suggestTime */
        $st = (string)($m['suggestTime'] ?? '');
        if (!preg_match('/^([01]\d|2[0-3]):([0-5]\d)$/', $st, $mm)) {
            continue;
        }
        $start = $todayDate->setTime((int)$mm[1], (int)$mm[2]);
        $freq = (string)($m['notifyFreq'] ?? 'daily');
        $rrule = 'FREQ=DAILY';
        $step = '+1 day';
        if ($freq === 'weekly') {
            $wd = max(0, min(6, (int)($m['notifyWeekday'] ?? 1)));
            $rrule = 'FREQ=WEEKLY;BYDAY=' . LB_ICS_WEEK[$wd];
            $step = '+7 days';
        } elseif ($freq === 'monthly') {
            $md = max(1, min(31, (int)($m['notifyMonthday'] ?? 1)));
            $rrule = 'FREQ=MONTHLY;BYMONTHDAY=' . $md;
            $step = '+1 month';
        }
        while ($start <= $now) {
            $start = $start->modify($step);
        }
        $out[] = lb_ics_event(
            'habit-' . $hid,
            $start, $start->modify('+15 minutes'),
            $icon . ' ' . $name, $note, $rrule
        );
        $count++;
    }

    /* ---- 还款日：每月固定一天，跟着 money.notify.on 走 ----
       开关关着就不进订阅，跟企微提醒用同一个开关（用户要求「提醒非强制」）。
       前端 buildICS 里那段必须跟这里逐条对齐，否则「下载的日历有、
       订阅的没有」这种怪事就会发生。

       已知限制：RRULE 用 BYMONTHDAY=due，29/30/31 号在小月不会产生实例
       （iCalendar 规范如此）。页面日历和企微提醒走的是「小月按月末」，
       两者在 2 月会有出入。还款日设在 28 号以内就完全没这个问题。 */
    $money = isset($state['money']) && is_array($state['money']) ? $state['money'] : [];
    $mnt = isset($money['notify']) && is_array($money['notify']) ? $money['notify'] : [];
    if (($mnt['on'] ?? false) === true) {
        [$nh, $nm] = lb_ics_clock((string)($mnt['time'] ?? ''), '09:00');
        $debts = isset($money['debts']) && is_array($money['debts']) ? $money['debts'] : [];
        foreach ($debts as $d) {
            if (!is_array($d)) {
                continue;
            }
            $bal = (float)($d['balance'] ?? 0);
            if ($bal <= 0.005) {
                continue;   // 已还清的债不该还挂在日历上
            }
            /* v110：0 / 空 = 没有具体还款日。这类债不生成日历条目 ——
               跟前端 dayDebts()、lb_schedule_debts() 同一口径。 */
            $due = (int)($d['due'] ?? 0);
            if ($due < 1 || $due > 31) {
                continue;
            }
            /* **从本月 1 号起算**，不能从「今天」起算 ——
               今天是 25 号、还款日 31 号时，从今天起算会一步推到下个月，
               把本月还剩的那次还款整个跳过（前端 buildICS 是从 1 号起的，
               两边一对就露馅，verify-ics-subscribe 就是干这个的）。 */
            $start = $todayDate->setDate(
                (int)$todayDate->format('Y'), (int)$todayDate->format('n'), 1
            )->setTime($nh, $nm);
            $start = $start->setDate(
                (int)$start->format('Y'), (int)$start->format('n'),
                min($due, (int)$start->format('t'))
            )->setTime($nh, $nm);
            $guard = 0;
            while ($start <= $now && $guard < 40) {
                /* 用 first day of next month 推进：直接 +1 month 遇到 31 号
                   会溢出（10-31 +1 month = 12-01），月份就跳过去了。 */
                $start = $start->modify('first day of next month')->setTime($nh, $nm);
                $start = $start->setDate(
                    (int)$start->format('Y'), (int)$start->format('n'),
                    min($due, (int)$start->format('t'))
                )->setTime($nh, $nm);
                $guard++;
            }
            $note = '还剩 ¥' . number_format($bal, 0, '.', '')
                . ' · 最低 ¥' . number_format((float)($d['min'] ?? 0), 0, '.', '')
                . ' · 年化 ' . (int)($d['apr'] ?? 0) . '%';
            $out[] = lb_ics_event(
                'debt-' . (string)($d['id'] ?? ''),
                $start, $start->modify('+15 minutes'),
                '💳 还款 · ' . (string)($d['name'] ?? '债务'),
                $note,
                'FREQ=MONTHLY;BYMONTHDAY=' . $due
            );
            $count++;
        }
    }

    $out[] = 'END:VCALENDAR';
    return ['text' => implode("\r\n", $out) . "\r\n", 'count' => $count];
}
