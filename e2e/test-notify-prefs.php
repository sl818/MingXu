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

function notice_state(): array
{
    return ['notices' => [[
        'id' => 'nt1', 'text' => '记得吃维生素', 'time' => HM,
        'mode' => 'daily', 'on' => true,
    ]]];
}

function add_user(PDO $pdo, int $id): void
{
    $pdo->prepare('INSERT INTO users (id, email, status, push_webhook, push_enabled) VALUES (?, ?, "active", ?, 1)')
        ->execute([$id, 'u' . $id . '@example.com', HOOK]);
    $pdo->prepare('INSERT INTO boards (user_id, data) VALUES (?, ?)')
        ->execute([$id, json_encode(notice_state(), JSON_UNESCAPED_UNICODE)]);
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

echo PHP_EOL . str_repeat('-', 46) . PHP_EOL;
echo '通知通道矩阵：通过 ' . $pass . ' 项，失败 ' . $fail . ' 项' . PHP_EOL;
exit($fail > 0 ? 1 : 0);
