<?php
/* 晚风Todo · 日历订阅（iCalendar 生成）
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
        'DESCRIPTION:' . lb_ics_escape($desc !== '' ? $desc : '来自 晚风Todo'),
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
        'X-WR-CALNAME:' . lb_ics_escape('晚风Todo（' . $why . '）'),
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
        'X-WR-CALNAME:' . lb_ics_escape('晚风Todo 提醒'),
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
        $times = isset($m['times']) && is_array($m['times']) ? $m['times'] : [];
        $times = array_values(array_filter($times, static function ($t) {
            return is_string($t) && preg_match('/^([01]\d|2[0-3]):[0-5]\d$/', $t);
        }));
        if (!$times) {
            continue;
        }
        $startDay = lb_ics_is_date($m['startDate'] ?? '') ? (string)$m['startDate'] : $today;
        $endDay = lb_ics_is_date($m['endDate'] ?? '') ? (string)$m['endDate'] : '';
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
        if (!is_array($t) || !empty($t['archivedAt']) || ($t['status'] ?? '') === 'done') {
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

        if ($repeat === 'none') {
            if ($due < $today) {
                continue;   // 逾期的交给页内提醒，别塞满日历
            }
            $start = $dueDate->setTime(9, 0);
            if ($start <= $now) {
                continue;
            }
            $rrule = '';
        } else {
            [$hh, $mm] = lb_ics_clock($t['repeatTime'] ?? '', '20:00');
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
            $start, $start->modify('+15 minutes'),
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
        if (!empty($h['med']) || !empty($h['optional']) || ($h['type'] ?? '') === 'quit') {
            continue;
        }
        $st = is_string($h['suggestTime'] ?? '') ? (string)$h['suggestTime'] : '';
        if (!preg_match('/^([01]\d|2[0-3]):([0-5]\d)$/', $st, $mm)) {
            continue;
        }
        $start = $todayDate->setTime((int)$mm[1], (int)$mm[2]);
        while ($start <= $now) {
            $start = $start->modify('+1 day');
        }
        $icon = (string)($h['icon'] ?? '🔔');
        $name = (string)($h['name'] ?? '习惯');
        $out[] = lb_ics_event(
            'habit-' . (string)($h['id'] ?? ''),
            $start, $start->modify('+15 minutes'),
            $icon . ' ' . $name, (string)($h['note'] ?? ''), 'FREQ=DAILY'
        );
        $count++;
    }

    $out[] = 'END:VCALENDAR';
    return ['text' => implode("\r\n", $out) . "\r\n", 'count' => $count];
}
