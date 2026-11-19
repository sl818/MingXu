<?php
/**
 * 推送诊断：只读，不写库、不发消息。
 *
 * 一次性 dump 出「某天某时刻该不该提醒、为什么没提醒」的全部依据：
 *   1. 每个用户的推送开关、webhook（脱敏）
 *   2. 每个药的完整字段（times / courseType / status / startDate / endDate）
 *   3. 当天已记录服药的时段（已吃的不再提醒）
 *   4. 当天完整时间表（lb_schedule_day）
 *   5. 指定时刻这一分钟该发什么（lb_schedule_due）
 *   6. 今天已经发过什么（push_sent，去重依据）
 *
 * 用法（在服务器上跑）：
 *   php tools/push_diag.php                 # 默认诊断今天 08:40
 *   php tools/push_diag.php --at 08:40      # 指定时刻
 *   php tools/push_diag.php --date 2026-10-30 --at 08:40
 */

define('LIFEBOARD_API', 1);

if (PHP_SAPI !== 'cli') {
    http_response_code(404);
    exit;
}

require __DIR__ . '/../api/bootstrap.php';
require __DIR__ . '/../api/push.php';

$argvList = array_slice($argv, 1);
$date = null;
$at = '08:40';

$i = array_search('--date', $argvList, true);
if ($i !== false && isset($argvList[$i + 1])) {
    $date = (string)$argvList[$i + 1];
}
$j = array_search('--at', $argvList, true);
if ($j !== false && isset($argvList[$j + 1])) {
    $at = (string)$argvList[$j + 1];
}

if (!preg_match('/^([01]\d|2[0-3]):[0-5]\d$/', $at)) {
    fwrite(STDERR, '--at 的格式应该是 HH:MM，例如 08:40' . PHP_EOL);
    exit(2);
}

$tz = lb_ics_tz();
$now = new DateTimeImmutable('now', $tz);
if ($date === null) {
    $date = $now->format('Y-m-d');
}

echo '服务器当前（上海时间）：' . $now->format('Y-m-d H:i:s') . PHP_EOL;
echo '诊断日期：' . $date . '   诊断时刻：' . $at . PHP_EOL . PHP_EOL;

try {
    $pdo = lb_db();
} catch (PDOException $e) {
    fwrite(STDERR, '数据库连接失败：' . $e->getMessage() . PHP_EOL);
    exit(1);
}

$rows = $pdo->query(
    "SELECT u.id, u.email, u.push_webhook, u.push_enabled, b.data
       FROM users u
       INNER JOIN boards b ON b.user_id = u.id
      WHERE u.status = 'active'"
)->fetchAll();

if (!$rows) {
    echo '没有找到任何有看板的用户。' . PHP_EOL;
    exit(0);
}

foreach ($rows as $r) {
    $hook = (string)($r['push_webhook'] ?? '');
    $masked = $hook === ''
        ? '（未填写）'
        : substr($hook, 0, 56) . '...' . substr($hook, -4);

    echo '════════ 用户 ' . $r['email'] . ' (id=' . $r['id'] . ') ════════' . PHP_EOL;
    echo '推送开关 push_enabled = ' . ($r['push_enabled'] ?? 0) . PHP_EOL;
    echo 'webhook = ' . $masked . PHP_EOL;

    /* v121：邮件通道同样决定「这个用户会不会被调度捞出来」，所以一起显示。
       没有这张表时说明迁移没跑——调度会降级成只发企业微信。 */
    if (lb_table_exists($pdo, 'user_mail_config')) {
        $ms = $pdo->prepare('SELECT enabled, smtp_user, from_email, secret_enc, last_error FROM user_mail_config WHERE user_id = ?');
        $ms->execute([(int)$r['id']]);
        $mc = $ms->fetch();
        if (!$mc) {
            echo '邮件提醒 mail = 未配置' . PHP_EOL;
        } else {
            echo '邮件提醒 mail = enabled=' . (int)$mc['enabled']
                . ' / 账号=' . (($mc['smtp_user'] ?? '') !== '' ? $mc['smtp_user'] : '（空）')
                . ' / 授权码=' . (($mc['secret_enc'] ?? '') !== '' && $mc['secret_enc'] !== null ? '已存' : '（空）')
                . PHP_EOL;
            if ((string)($mc['last_error'] ?? '') !== '') {
                echo '  上次错误：' . $mc['last_error'] . PHP_EOL;
            }
        }
    } else {
        echo '邮件提醒 mail = （user_mail_config 表不存在，先跑迁移）' . PHP_EOL;
    }

    $state = json_decode((string)$r['data'], true);
    if (!is_array($state)) {
        echo '  （看板数据无法解析）' . PHP_EOL . PHP_EOL;
        continue;
    }

    echo PHP_EOL . '── 待办清单（未完成的都列，方便对「为什么不发」）──' . PHP_EOL;
    $anyTask = false;
    foreach ((array)($state['tasks'] ?? []) as $t) {
        if (!is_array($t)) {
            continue;
        }
        $st = (string)($t['status'] ?? 'todo');
        if ($st === 'done' || $st === 'cancelled') {
            continue;
        }
        $anyTask = true;
        $due = (string)($t['due'] ?? '');
        $nt = (string)($t['notifyTime'] ?? '09:00');
        $no = array_key_exists('notify', $t) ? (bool)$t['notify'] : true;
        echo '  [' . ($t['id'] ?? '?') . '] ' . ($t['title'] ?? '')
            . '  due=' . ($due === '' ? '（无截止日）' : $due)
            . '  通知=' . ($no ? '开 ' . $nt : '关')
            . '  ' . $st;
        if ($due !== $date) {
            echo '  ← 不是今天到期，今天不会推';
        }
        echo PHP_EOL;
    }
    if (!$anyTask) {
        echo '  （没有未完成的待办）' . PHP_EOL;
    }

    echo PHP_EOL . '── 药品清单 ──' . PHP_EOL;
    $dosesToday = (array)($state['doses'][$date] ?? []);
    $hasMed = false;
    foreach ((array)($state['meds'] ?? []) as $m) {
        if (!is_array($m)) {
            continue;
        }
        $hasMed = true;
        $times = implode(',', (array)($m['times'] ?? []));
        $taken = [];
        foreach ((array)($m['times'] ?? []) as $slot) {
            if (!empty($dosesToday[$m['id']][$slot])) {
                $taken[] = $slot;
            }
        }
        echo '  [' . ($m['id'] ?? '?') . '] ' . ($m['name'] ?? '?')
            . ' ' . ($m['doseAmount'] ?? '?') . ($m['doseUnit'] ?? '') . PHP_EOL;
        echo '        times=[' . $times . ']  courseType=' . ($m['courseType'] ?? '?')
            . '  status=' . ($m['status'] ?? '?')
            . '  start=' . ($m['startDate'] ?? '')
            . '  end=' . ($m['endDate'] ?? '') . PHP_EOL;
        if ($taken) {
            echo '        ! 今天已记录服药时段：' . implode(',', $taken)
                . '（已吃的不再提醒）' . PHP_EOL;
        }
    }
    if (!$hasMed) {
        echo '  （没有药）' . PHP_EOL;
    }

    echo PHP_EOL . '── ' . $date . ' 完整时间表（lb_schedule_day）──' . PHP_EOL;
    $plan = lb_schedule_day($state, $date);
    if (!$plan) {
        echo '  （空：今天没有任何该提醒的条目）' . PHP_EOL;
    }
    foreach ($plan as $it) {
        echo '  ' . $it['time'] . '  [' . $it['kind'] . ']  ' . $it['title']
            . ' / ' . $it['body'] . PHP_EOL;
    }

    echo PHP_EOL . '── ' . $at . ' 这一分钟该发什么（lb_schedule_due，宽容 3 分钟）──' . PHP_EOL;
    $due = lb_schedule_due($plan, $at, 3);
    if (!$due) {
        echo '  （无）' . PHP_EOL;
    }
    foreach ($due as $it) {
        echo '  ' . $it['time'] . '  [' . $it['kind'] . ']  ' . $it['title'] . PHP_EOL;
    }

    $st = $pdo->prepare(
        'SELECT slot_key, sent_at FROM push_sent WHERE user_id = ? AND slot_key LIKE ? ORDER BY sent_at DESC'
    );
    $st->execute([(int)$r['id'], $date . '%']);
    $sent = $st->fetchAll();
    echo PHP_EOL . '── 今天已发送记录（push_sent，去重依据）──' . PHP_EOL;
    if (!$sent) {
        echo '  （无）' . PHP_EOL;
    }
    foreach ($sent as $s) {
        echo '  ' . $s['sent_at'] . '  ' . $s['slot_key'] . PHP_EOL;
    }

    echo PHP_EOL;
}

echo '── 诊断结束 ──' . PHP_EOL;
