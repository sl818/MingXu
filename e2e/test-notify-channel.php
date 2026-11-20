<?php
/**
 * 多通道调度（v121）：邮件接入后，两个通道各自记账、互不顶掉。
 *
 * 这一层最容易错的是「去重键没有通道维度」——邮件发成功记了一笔，
 * 企业微信就被判「已发」跳过。所以用真实 SQLite 穷举这几种组合。
 *
 * 运行：
 *   php -d extension_dir=<php>/ext -d extension=pdo_sqlite e2e/test-notify-channel.php
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

const D = '2026-11-19';
const HM = '20:30';
const HOOK = 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test';

/**
 * @param bool $withChannel  push_sent 是否有 channel 列（false = 老库未迁移）
 * @param bool $withMailTbl  user_mail_config 表是否存在
 */
function db(bool $withChannel = true, bool $withMailTbl = true): PDO
{
    $pdo = new PDO('sqlite::memory:');
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
    $pdo->setAttribute(PDO::ATTR_DEFAULT_FETCH_MODE, PDO::FETCH_ASSOC);
    $pdo->exec('CREATE TABLE users (
        id INTEGER PRIMARY KEY, email TEXT, status TEXT DEFAULT "active",
        push_webhook TEXT, push_enabled INTEGER DEFAULT 0)');
    $pdo->exec('CREATE TABLE boards (user_id INTEGER PRIMARY KEY, data TEXT, rev INTEGER, updated_at INTEGER)');
    $pdo->exec($withChannel
        ? 'CREATE TABLE push_sent (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, slot_key TEXT,
            kind TEXT, sent_at TEXT, content TEXT, channel TEXT DEFAULT "wecom")'
        : 'CREATE TABLE push_sent (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, slot_key TEXT,
            kind TEXT, sent_at TEXT, content TEXT)');
    $pdo->exec($withChannel
        ? 'CREATE UNIQUE INDEX uq ON push_sent (user_id, slot_key, channel)'
        : 'CREATE UNIQUE INDEX uq ON push_sent (user_id, slot_key)');
    if ($withMailTbl) {
        $pdo->exec('CREATE TABLE user_mail_config (user_id INTEGER PRIMARY KEY, enabled INTEGER DEFAULT 0)');
    }
    return $pdo;
}

function notice_state(): array
{
    return ['notices' => [[
        'id' => 'nt1', 'text' => '记得吃维生素', 'time' => HM,
        'mode' => 'daily', 'on' => true,
    ]]];
}

function add_user(PDO $pdo, int $id, bool $wecom, bool $mail): void
{
    $pdo->prepare('INSERT INTO users (id, email, status, push_webhook, push_enabled) VALUES (?, ?, "active", ?, ?)')
        ->execute([$id, 'u' . $id . '@example.com', $wecom ? HOOK : null, $wecom ? 1 : 0]);
    $pdo->prepare('INSERT INTO boards (user_id, data) VALUES (?, ?)')
        ->execute([$id, json_encode(notice_state(), JSON_UNESCAPED_UNICODE)]);
    try {
        $pdo->prepare('INSERT INTO user_mail_config (user_id, enabled) VALUES (?, ?)')
            ->execute([$id, $mail ? 1 : 0]);
    } catch (PDOException $e) {
        /* 有的场景故意不建这张表 */
    }
}

/** 记录调用的假通道 */
function channels(array &$log, bool $mailOk = true): array
{
    return [
        ['channel' => 'wecom', 'fn' => function ($row, $text, &$why) use (&$log) {
            $log[] = 'wecom:' . $row['id'];
            return true;
        }],
        ['channel' => 'mail', 'fn' => function ($row, $text, &$why) use (&$log, $mailOk) {
            $log[] = 'mail:' . $row['id'];
            if (!$mailOk) {
                $why = 'SMTP 认证失败';
                return false;
            }
            return true;
        }],
    ];
}

echo '[1] 两个通道各发一次，互不顶掉' . PHP_EOL;
$pdo = db();
add_user($pdo, 1, true, true);
$log = [];
$r = lb_push_tick_run($pdo, D, HM, channels($log));
chk('两个通道都调用了', count($log) === 2, implode(',', $log));
chk('计数按投递算（2 次）', $r['sent'] === 2, (string)$r['sent']);
chk('items 里带 channel 字段', count(array_filter($r['items'], fn($i) => isset($i['channel']))) === 2);
chk('有一个 wecom 一个 mail', count(array_filter($r['items'], fn($i) => $i['channel'] === 'mail')) === 1);

echo '[2] 同一分钟再跑一次：两个都跳过' . PHP_EOL;
$log2 = [];
$r2 = lb_push_tick_run($pdo, D, HM, channels($log2));
chk('不再调用任何通道', count($log2) === 0, implode(',', $log2));
chk('跳过计数是 2', $r2['skipped'] === 2, (string)$r2['skipped']);

echo '[3] 只开邮件的用户（没有 webhook）也能被捞出来' . PHP_EOL;
$pdo3 = db();
add_user($pdo3, 2, false, true);
$log3 = [];
$r3 = lb_push_tick_run($pdo3, D, HM, channels($log3));
chk('只发了邮件', $log3 === ['mail:2'], implode(',', $log3));
chk('发出 1 次', $r3['sent'] === 1, (string)$r3['sent']);

echo '[4] 只开企业微信的用户不会碰邮件' . PHP_EOL;
$pdo4 = db();
add_user($pdo4, 3, true, false);
$log4 = [];
$r4 = lb_push_tick_run($pdo4, D, HM, channels($log4));
chk('只发了企业微信', $log4 === ['wecom:3'], implode(',', $log4));

echo '[5] 邮件失败：撤掉自己的占位，不影响企业微信' . PHP_EOL;
$pdo5 = db();
add_user($pdo5, 4, true, true);
$log5 = [];
$r5 = lb_push_tick_run($pdo5, D, HM, channels($log5, false));
chk('企业微信成功、邮件失败', $r5['sent'] === 1 && $r5['failed'] === 1,
    'sent=' . $r5['sent'] . ' failed=' . $r5['failed']);
$rows = $pdo5->query('SELECT channel FROM push_sent ORDER BY channel')->fetchAll();
chk('只剩 wecom 的占位', count($rows) === 1 && $rows[0]['channel'] === 'wecom',
    json_encode($rows));

echo '[6] 下一分钟重试：邮件补发成功，企业微信不重复' . PHP_EOL;
$log6 = [];
$r6 = lb_push_tick_run($pdo5, D, HM, channels($log6, true));
chk('只重试邮件', $log6 === ['mail:4'], implode(',', $log6));
chk('企业微信被判已发跳过', $r6['skipped'] === 1, 'skipped=' . $r6['skipped']);

echo '[7] 老库（push_sent 没有 channel 列）不报错' . PHP_EOL;
$pdo7 = db(false);
add_user($pdo7, 5, true, true);
$log7 = [];
$r7 = lb_push_tick_run($pdo7, D, HM, channels($log7));
chk('仍然能跑完，没有异常', $r7['sent'] + $r7['skipped'] + $r7['failed'] > 0);
chk('降级为单键去重（第二个通道被顶掉）', $r7['skipped'] >= 1,
    'sent=' . $r7['sent'] . ' skipped=' . $r7['skipped']);

echo '[8] user_mail_config 表不存在时不报错' . PHP_EOL;
$pdo8 = db(true, false);
add_user($pdo8, 6, true, true);
$log8 = [];
$r8 = lb_push_tick_run($pdo8, D, HM, channels($log8));
chk('只走了企业微信', $log8 === ['wecom:6'], implode(',', $log8));

echo '[9] 单通道旧调用方式不受影响' . PHP_EOL;
$pdo9 = db();
add_user($pdo9, 7, true, false);
$log9 = [];
$old = function ($hook, $text, &$why) use (&$log9) {
    $log9[] = 'legacy:' . (strlen($hook) > 10 ? 'hook' : 'empty');
    return true;
};
$r9 = lb_push_tick_run($pdo9, D, HM, $old);
chk('旧签名仍然只发一次', $log9 === ['legacy:hook'], implode(',', $log9));
chk('channels 计为 1', ($r9['channels'] ?? 0) === 1, (string)($r9['channels'] ?? -1));

echo '[10] 同一时刻的药合并成一条' . PHP_EOL;
$merged = lb_notify_merge_med([
    ['kind' => 'med', 'id' => 'm1', 'time' => '08:00', 'title' => '该吃药了', 'body' => '缬沙坦胶囊 1胶囊'],
    ['kind' => 'med', 'id' => 'm2', 'time' => '08:00', 'title' => '该吃药了', 'body' => '甲钴胺片 1片'],
    ['kind' => 'med', 'id' => 'm3', 'time' => '08:00', 'title' => '该吃药了', 'body' => '复方丹参滴丸 1其他'],
]);
chk('三条合成一条', count($merged) === 1, (string)count($merged));
chk('标题带数量', ($merged[0]['title'] ?? '') === '该吃药了（3 种）', $merged[0]['title'] ?? '');
chk('正文逐条列出', substr_count($merged[0]['body'] ?? '', '· ') === 3, $merged[0]['body'] ?? '');
chk('合并后 id 是 batch_08:00', ($merged[0]['id'] ?? '') === 'batch_08:00', $merged[0]['id'] ?? '');

echo '[11] 不同时刻的药不合并，单条保持原样' . PHP_EOL;
$m2 = lb_notify_merge_med([
    ['kind' => 'med', 'id' => 'm1', 'time' => '08:00', 'title' => '该吃药了', 'body' => 'A'],
    ['kind' => 'med', 'id' => 'm2', 'time' => '20:00', 'title' => '该吃药了', 'body' => 'B'],
]);
chk('两条不同时刻仍是两条', count($m2) === 2, (string)count($m2));
chk('单条不改标题', ($m2[0]['title'] ?? '') === '该吃药了', $m2[0]['title'] ?? '');

echo '[12] 非用药类型不参与合并' . PHP_EOL;
$m3 = lb_notify_merge_med([
    ['kind' => 'task', 'id' => 't1', 'time' => '08:00', 'title' => '交报告', 'body' => '今天到期'],
    ['kind' => 'task', 'id' => 't2', 'time' => '08:00', 'title' => '打电话', 'body' => '今天到期'],
]);
chk('两个任务不合并', count($m3) === 2, (string)count($m3));

echo '[13] 合并后的条目仍然标成 med（矩阵才管得到它）' . PHP_EOL;
$m4 = lb_notify_merge_med([
    ['kind' => 'med', 'id' => 'a', 'time' => '08:00', 'title' => '该吃药了', 'body' => 'A'],
    ['kind' => 'med', 'id' => 'b', 'time' => '08:00', 'title' => '该吃药了', 'body' => 'B'],
]);
chk('kind 还是 med', ($m4[0]['kind'] ?? '') === 'med', $m4[0]['kind'] ?? '');
chk('带 merged 计数', ($m4[0]['merged'] ?? 0) === 2, (string)($m4[0]['merged'] ?? 0));

echo PHP_EOL . str_repeat('-', 46) . PHP_EOL;
echo '多通道调度：通过 ' . $pass . ' 项，失败 ' . $fail . ' 项' . PHP_EOL;
exit($fail > 0 ? 1 : 0);
