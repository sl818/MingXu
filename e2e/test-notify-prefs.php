<?php
/**
 * 通知通道矩阵（v122）：默认值、存取、以及调度是否真的按矩阵过滤。
 *
 * 这层的风险是「老用户升级后一条都收不到」——所以默认值必须是
 * 「该发的照发」，不能是全关。测试把这条锁住。
 *
 * 运行：
 *   php -d extension_dir=<php>/ext -d extension=pdo_sqlite e2e/test-notify-prefs.php
 */

define('LIFEBOARD_API', 1);

require __DIR__ . '/../api/push.php';

$pass = 0;
$fail = 0;

function chk(string $name, $cond, string $note = ''): void
{
    global $pass, $fail;
    if ($cond) {
        $pass++;
        echo '  ✓ ' . $name . PHP_EOL;
    } else {
        $fail++;
        echo '  ✗ ' . $name . ($note !== '' ? '  [' . $note . ']' : '') . PHP_EOL;
    }
}

const D = '2026-11-20';
const HM = '20:30';
const HOOK = 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test';

function db(): PDO
{
    $pdo = new PDO('sqlite::memory:');
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
    $pdo->setAttribute(PDO::ATTR_DEFAULT_FETCH_MODE, PDO::FETCH_ASSOC);
    $pdo->exec('CREATE TABLE app_settings (k TEXT PRIMARY KEY, v TEXT)');
    $pdo->exec('CREATE TABLE users (
        id INTEGER PRIMARY KEY, email TEXT, status TEXT DEFAULT "active",
        push_webhook TEXT, push_enabled INTEGER DEFAULT 0)');
    $pdo->exec('CREATE TABLE boards (user_id INTEGER PRIMARY KEY, data TEXT, rev INTEGER, updated_at INTEGER)');
    $pdo->exec('CREATE TABLE push_sent (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, slot_key TEXT,
        kind TEXT, sent_at TEXT, content TEXT, channel TEXT DEFAULT "wecom")');
    $pdo->exec('CREATE UNIQUE INDEX uq ON push_sent (user_id, slot_key, channel)');
    $pdo->exec('CREATE TABLE user_mail_config (user_id INTEGER PRIMARY KEY, enabled INTEGER DEFAULT 0)');
    return $pdo;
}

function notice_state(string $time = HM): array
{
    return ['notices' => [[
        'id' => 'nt1', 'text' => '记得吃维生素', 'time' => $time,
        'mode' => 'daily', 'on' => true,
    ]]];
}

function add_user(PDO $pdo, int $id, string $time = HM): void
{
    $pdo->prepare('INSERT INTO users (id, email, status, push_webhook, push_enabled) VALUES (?, ?, "active", ?, 1)')
        ->execute([$id, 'u' . $id . '@example.com', HOOK]);
    $pdo->prepare('INSERT INTO boards (user_id, data) VALUES (?, ?)')
        ->execute([$id, json_encode(notice_state($time), JSON_UNESCAPED_UNICODE)]);
    $pdo->prepare('INSERT INTO user_mail_config (user_id, enabled) VALUES (?, 1)')->execute([$id]);
}

function channels(array &$log): array
{
    return [
        ['channel' => 'wecom', 'fn' => function ($row, $text, &$why) use (&$log) {
            $log[] = 'wecom';
            return true;
        }],
        ['channel' => 'mail', 'fn' => function ($row, $text, &$why) use (&$log) {
            $log[] = 'mail';
            return true;
        }],
    ];
}

echo '[1] 默认矩阵：该发的照发（升级后不能一条都收不到）' . PHP_EOL;
$def = lb_notify_defaults();
chk('用药两条通道都开', $def['med']['wecom'] && $def['med']['mail']);
chk('待办两条通道都开', $def['task']['wecom'] && $def['task']['mail']);
chk('习惯只走企业微信', $def['habit']['wecom'] && !$def['habit']['mail']);
chk('每日小结只走企业微信', $def['report']['wecom'] && !$def['report']['mail']);
chk('七种类型齐全（含还款提醒）', count($def) === 7, (string)count($def));

echo '[2] 空库读取：返回默认值而不是全关' . PHP_EOL;
$pdo = db();
$got = lb_notify_prefs_load($pdo, 1);
chk('与默认值一致', $got === $def);

echo '[3] 保存后能读回' . PHP_EOL;
$r = lb_notify_prefs_save($pdo, 1, [
    'med' => ['wecom' => true, 'mail' => false],
    'notice' => ['wecom' => false, 'mail' => true],
]);
chk('保存成功', $r['ok'] === true, (string)($r['error'] ?? ''));
$back = lb_notify_prefs_load($pdo, 1);
chk('用药的邮件被关掉', $back['med']['mail'] === false);
chk('用药的企业微信仍开', $back['med']['wecom'] === true);
chk('自定义提醒改成只发邮件', $back['notice']['wecom'] === false && $back['notice']['mail'] === true);
chk('没提交的类型保持默认', $back['task']['mail'] === true);

echo '[4] 调度按矩阵过滤' . PHP_EOL;
$pdo4 = db();
add_user($pdo4, 2);
lb_notify_prefs_save($pdo4, 2, ['notice' => ['wecom' => true, 'mail' => false]]);
$log = [];
lb_push_tick_run($pdo4, D, HM, channels($log));
chk('自定义提醒只走企业微信', $log === ['wecom'], implode(',', $log));

echo '[5] 两条都关：这条不打扰' . PHP_EOL;
$pdo5 = db();
add_user($pdo5, 3);
lb_notify_prefs_save($pdo5, 3, ['notice' => ['wecom' => false, 'mail' => false]]);
$log5 = [];
$r5 = lb_push_tick_run($pdo5, D, HM, channels($log5));
chk('一条都没发', $log5 === [], implode(',', $log5));
chk('也没有写去重记录', (int)$pdo5->query('SELECT COUNT(*) FROM push_sent')->fetchColumn() === 0);

echo '[6] 关掉一条不影响另一条' . PHP_EOL;
$pdo6 = db();
add_user($pdo6, 4);
lb_notify_prefs_save($pdo6, 4, ['notice' => ['wecom' => false, 'mail' => true]]);
$log6 = [];
lb_push_tick_run($pdo6, D, HM, channels($log6));
chk('只发邮件', $log6 === ['mail'], implode(',', $log6));

echo '[7] 存储脏数据时退回默认值' . PHP_EOL;
$pdo7 = db();
$pdo7->prepare('INSERT INTO app_settings (k, v) VALUES (?, ?)')->execute(['notify_prefs_5', '{oops']);
chk('坏 JSON 不影响', lb_notify_prefs_load($pdo7, 5) === $def);

echo '[8] 夜间静默默认关闭' . PHP_EOL;
$pdo8 = db();
chk('没配过就是不静默', lb_notify_quiet_load($pdo8, 1) === false);
chk('23:00 算夜里', lb_notify_in_quiet('23:00') === true);
chk('03:30 算夜里', lb_notify_in_quiet('03:30') === true);
chk('06:59 算夜里', lb_notify_in_quiet('06:59') === true);
chk('07:00 不算', lb_notify_in_quiet('07:00') === false);
chk('22:59 不算', lb_notify_in_quiet('22:59') === false);

echo '[9] 开了静默后，夜间提醒整段跳过' . PHP_EOL;
$pdo9 = db();
add_user($pdo9, 9);
lb_notify_quiet_save($pdo9, 9, true);
chk('读回是开着的', lb_notify_quiet_load($pdo9, 9) === true);
$log9 = [];
$r9 = lb_push_tick_run($pdo9, D, '23:30', channels($log9));
chk('23:30 一条都没发', $log9 === [], implode(',', $log9));
chk('计到 quiet_skipped', ($r9['quiet_skipped'] ?? 0) === 1, (string)($r9['quiet_skipped'] ?? 0));
$log9b = [];
lb_push_tick_run($pdo9, D, HM, channels($log9b));
chk('白天照常发', count($log9b) > 0, implode(',', $log9b));

echo '[10] 关掉静默后夜间恢复推送' . PHP_EOL;
$pdo10 = db();
add_user($pdo10, 10, '23:30');
$log10 = [];
lb_push_tick_run($pdo10, D, '23:30', channels($log10));
chk('默认（关）时夜里也发', count($log10) > 0, implode(',', $log10));

echo '[11] 每日小结三个时刻可改' . PHP_EOL;
$pdo11 = db();
$rep = lb_notify_report_load($pdo11, 11);
chk('默认 08:20 / 12:30 / 20:00',
    $rep === ['morning' => '08:20', 'noon' => '12:30', 'evening' => '20:00'], json_encode($rep));
$sv = lb_notify_report_save($pdo11, 11, ['morning' => '10:00', 'noon' => '', 'evening' => '22:30']);
chk('保存成功', $sv['ok'] === true, (string)($sv['error'] ?? ''));
$rep2 = lb_notify_report_load($pdo11, 11);
chk('早报改成 10:00', $rep2['morning'] === '10:00', $rep2['morning']);
chk('午报留空表示不发', $rep2['noon'] === '', '[' . $rep2['noon'] . ']');
chk('小结改成 22:30', $rep2['evening'] === '22:30', $rep2['evening']);

echo '[12] 小结时间非法时拒绝，不写坏数据' . PHP_EOL;
$bad = lb_notify_report_save($pdo11, 11, ['morning' => '25:99']);
chk('非法时间被拒', $bad['ok'] === false, (string)($bad['error'] ?? ''));
chk('原值没被改动', lb_notify_report_load($pdo11, 11)['morning'] === '10:00');

echo '[13] 小结时刻真的作用到调度' . PHP_EOL;
$st = [];
$def = lb_schedule_reports($st, D);
chk('默认三条', count($def) === 3, (string)count($def));
$cus = lb_schedule_reports($st, D, ['morning' => '10:00', 'noon' => '', 'evening' => '22:30']);
chk('自定义后只剩两条', count($cus) === 2, (string)count($cus));
chk('第一条是 10:00', ($cus[0]['time'] ?? '') === '10:00', $cus[0]['time'] ?? '');
chk('最后一条是 22:30', ($cus[1]['time'] ?? '') === '22:30', $cus[1]['time'] ?? '');

echo PHP_EOL . str_repeat('-', 46) . PHP_EOL;
echo '通知通道矩阵：通过 ' . $pass . ' 项，失败 ' . $fail . ' 项' . PHP_EOL;
exit($fail > 0 ? 1 : 0);
