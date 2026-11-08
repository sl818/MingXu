<?php
/**
 * 推送调度（去重 / 失败回滚 / 清理）的真实数据库验证。
 *
 * 用 SQLite 顶替 MySQL，发送器换成假的——这样最容易写错的三件事能穷举：
 *   1. 同一条会不会发两遍
 *   2. 发失败之后还能不能重试（占位有没有回滚）
 *   3. 时间窗边界
 *
 * 运行：
 *   php -d extension_dir=<php>/ext -d extension=pdo_sqlite e2e/test-push-tick.php
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
        echo "  ✓ " . $name . PHP_EOL;
    } else {
        $fail++;
        echo "  ✗ " . $name . ($note !== '' ? '  [' . $note . ']' : '') . PHP_EOL;
    }
}

const D = '2026-10-29';
const HOOK = 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test';

function db(): PDO
{
    $pdo = new PDO('sqlite::memory:');
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
    $pdo->setAttribute(PDO::ATTR_DEFAULT_FETCH_MODE, PDO::FETCH_ASSOC);
    $pdo->exec('CREATE TABLE users (
        id INTEGER PRIMARY KEY, email TEXT, status TEXT DEFAULT "active",
        push_webhook TEXT, push_enabled INTEGER DEFAULT 0)');
    $pdo->exec('CREATE TABLE boards (user_id INTEGER PRIMARY KEY, data TEXT, rev INTEGER, updated_at INTEGER)');
    $pdo->exec('CREATE TABLE push_sent (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, slot_key TEXT,
        kind TEXT, sent_at TEXT)');
    $pdo->exec('CREATE UNIQUE INDEX uq_push_sent ON push_sent (user_id, slot_key)');
    return $pdo;
}

/** 一个只在 08:00 和 20:00 有药的用户 */
function state_notice(): array
{
    return [
        'notices' => [[
            'id' => 'nt1', 'text' => '记得吃维生素', 'time' => '20:30',
            'mode' => 'daily', 'on' => true,
        ]],
    ];
}
function state_one_med(): array
{
    return [
        'meds' => [[
            'id' => 'm1', 'name' => '阿莫西林', 'status' => 'active', 'courseType' => 'long',
            'times' => ['08:00', '20:00'], 'doseAmount' => 1, 'doseUnit' => '片',
            'startDate' => '2026-10-01', 'endDate' => '',
        ]],
        'tasks' => [], 'habits' => [],
    ];
}

function add_user(PDO $pdo, int $id, string $hook, array $state, int $enabled = 1): void
{
    $pdo->prepare('INSERT INTO users (id, email, status, push_webhook, push_enabled) VALUES (?,?,?,?,?)')
        ->execute([$id, 'u' . $id . '@x.y', 'active', $hook, $enabled]);
    $pdo->prepare('INSERT INTO boards (user_id, data, rev, updated_at) VALUES (?,?,?,?)')
        ->execute([$id, json_encode($state, JSON_UNESCAPED_UNICODE), 1, 0]);
}

function count_sent(PDO $pdo): int
{
    return (int)$pdo->query('SELECT COUNT(*) FROM push_sent')->fetchColumn();
}

/* 假发送器：$ok 控制成功与否，$got 记录实际发出的内容 */
$ok = true;
$got = [];
$sender = function (string $hook, string $content, ?string &$err) use (&$ok, &$got): bool {
    $got[] = $content;
    if (!$ok) {
        $err = '假失败';
        return false;
    }
    return true;
};

/* ------------------------------------------------------------------ */
echo "[1] 没有开启推送的用户" . PHP_EOL;
$pdo = db();
add_user($pdo, 1, HOOK, state_one_med(), 0);
$r = lb_push_tick_run($pdo, D, '08:00', $sender);
chk('什么都不发', $r['sent'] === 0 && $r['failed'] === 0);
chk('也不留记录', count_sent($pdo) === 0);

$pdo2 = db();
add_user($pdo2, 1, '', state_one_med(), 1);
$r = lb_push_tick_run($pdo2, D, '08:00', $sender);
chk('地址为空时跳过（SQL 层已过滤）', $r['sent'] === 0);

/* ------------------------------------------------------------------ */
echo PHP_EOL . "[2] 正常发一条" . PHP_EOL;
$pdo = db();
add_user($pdo, 1, HOOK, state_one_med());
$got = [];
$ok = true;
$r = lb_push_tick_run($pdo, D, '08:00', $sender);
chk('08:00 发出 1 条', $r['sent'] === 1, 'sent=' . $r['sent']);
chk('没有失败', $r['failed'] === 0);
chk('内容是「该吃药了」', strpos($got[0] ?? '', '该吃药了') !== false, $got[0] ?? '');
chk('内容带药名', strpos($got[0] ?? '', '阿莫西林') !== false);
chk('数据库留下 1 条发送记录', count_sent($pdo) === 1);

/* ------------------------------------------------------------------ */
echo PHP_EOL . "[3] 去重" . PHP_EOL;
$got = [];
$r = lb_push_tick_run($pdo, D, '08:00', $sender);
chk('同一分钟再跑一次不重发', $r['sent'] === 0 && $r['skipped'] === 1,
    'sent=' . $r['sent'] . ' skip=' . $r['skipped']);
chk('发送器一次都没被调用', count($got) === 0);
chk('记录数没变', count_sent($pdo) === 1);

$got = [];
$r = lb_push_tick_run($pdo, D, '08:02', $sender);
chk('08:02 在窗口内也只算「已发过」', $r['sent'] === 0 && $r['skipped'] === 1);
chk('不会重复发', count($got) === 0);

/* ------------------------------------------------------------------ */
echo PHP_EOL . "[4] 时间窗" . PHP_EOL;
$got = [];
$r = lb_push_tick_run($pdo, D, '08:05', $sender);
chk('08:05 超出 3 分钟窗口，不补发', $r['sent'] === 0 && $r['skipped'] === 0,
    'sent=' . $r['sent'] . ' skip=' . $r['skipped']);
chk('发送器没被调用', count($got) === 0);

$pdo3 = db();
add_user($pdo3, 1, HOOK, state_one_med());
$got = [];
$r = lb_push_tick_run($pdo3, D, '07:59', $sender);
chk('07:59 不发未来时间的', $r['sent'] === 0 && count($got) === 0);

$got = [];
$r = lb_push_tick_run($pdo3, D, '20:00', $sender);
chk('20:00 发药 + 晚报（共 2 条）', $r['sent'] === 2, 'sent=' . $r['sent']);
chk('发的是晚上的内容', strpos($got[0] ?? '', '20:00') !== false, $got[0] ?? '');
chk('晚报附在第二条', strpos($got[1] ?? '', '今日小结') !== false, $got[1] ?? '');

/* ------------------------------------------------------------------ */
echo PHP_EOL . "[5] 发送失败要能重试" . PHP_EOL;
$pdo4 = db();
add_user($pdo4, 1, HOOK, state_one_med());
$got = [];
$ok = false;
$r = lb_push_tick_run($pdo4, D, '08:00', $sender);
chk('计入失败', $r['failed'] === 1, 'failed=' . $r['failed']);
chk('失败原因带回来', strpos($r['items'][0]['why'] ?? '', '假失败') !== false);
chk('占位被回滚（记录数为 0）', count_sent($pdo4) === 0, 'rows=' . count_sent($pdo4));

$ok = true;
$got = [];
$r = lb_push_tick_run($pdo4, D, '08:00', $sender);
chk('下一分钟能重试成功', $r['sent'] === 1, 'sent=' . $r['sent']);
chk('这次真的发出去了', count($got) === 1);
chk('成功后留下记录', count_sent($pdo4) === 1);

/* ------------------------------------------------------------------ */
echo PHP_EOL . "[6] 预演模式" . PHP_EOL;
$pdo5 = db();
add_user($pdo5, 1, HOOK, state_one_med());
$got = [];
$r = lb_push_tick_run($pdo5, D, '08:00', $sender, true);
chk('预演也报告 1 条', $r['sent'] === 1);
chk('预演不真发', count($got) === 0);
chk('预演不写记录', count_sent($pdo5) === 0);
chk('预演能拿到内容', strpos($r['items'][0]['text'] ?? '', '阿莫西林') !== false);

/* ------------------------------------------------------------------ */
echo PHP_EOL . "[7] 多用户互不影响" . PHP_EOL;
$pdo6 = db();
add_user($pdo6, 1, HOOK, state_one_med());
$other = state_one_med();
$other['meds'][0]['id'] = 'm9';
$other['meds'][0]['name'] = '维生素';
add_user($pdo6, 2, HOOK, $other);
$got = [];
$r = lb_push_tick_run($pdo6, D, '08:00', $sender);
chk('两个用户各发一条', $r['sent'] === 2, 'sent=' . $r['sent']);
chk('两条内容不同', count(array_unique($got)) === 2, implode(' | ', array_map(
    static function ($x) { return str_replace("\n", ' ', $x); }, $got)));
chk('记录按用户分开', count_sent($pdo6) === 2);

/* ------------------------------------------------------------------ */
echo PHP_EOL . "[8] 旧记录清理" . PHP_EOL;
$pdo7 = db();
add_user($pdo7, 1, HOOK, state_one_med());
$pdo7->prepare('INSERT INTO push_sent (user_id, slot_key, kind, sent_at) VALUES (?,?,?,?)')
    ->execute([1, '2026-10-01|med|old|08:00', 'med', '2026-10-01 08:00:00']);
chk('先塞一条 28 天前的', count_sent($pdo7) === 1);
$ok = true;
lb_push_tick_run($pdo7, D, '08:00', $sender);
$old = (int)$pdo7->query("SELECT COUNT(*) FROM push_sent WHERE sent_at < '2026-10-20'")->fetchColumn();
chk('超过 7 天的被清掉', $old === 0, 'old=' . $old);
chk('今天的记录还在', count_sent($pdo7) === 1);

/* ------------------------------------------------------------------ */
echo PHP_EOL . "[9] 数据坏了不拖垮别人" . PHP_EOL;
$pdo8 = db();
add_user($pdo8, 1, HOOK, state_one_med());
$pdo8->prepare('INSERT INTO users (id,email,status,push_webhook,push_enabled) VALUES (2,?,?,?,?)')
    ->execute(['bad@x.y', 'active', HOOK, 1]);
$pdo8->prepare('INSERT INTO boards (user_id,data,rev,updated_at) VALUES (?,?,?,?)')
    ->execute([2, '这不是 JSON', 1, 0]);
$got = [];
$ok = true;
$r = lb_push_tick_run($pdo8, D, '08:00', $sender);
chk('坏数据被跳过，好用户照常发', $r['sent'] === 1, 'sent=' . $r['sent']);
chk('没有因为坏数据抛异常', $r['failed'] === 0);

/* ------------------------------------------------------------------ */
echo PHP_EOL . "[10] 发送记录留痕（content 列）" . PHP_EOL;
/* 带 content 列的库：写入正文。db() 建的表故意没有这列，用来验证旧库兼容。 */
$pdoC = new PDO('sqlite::memory:');
$pdoC->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
$pdoC->setAttribute(PDO::ATTR_DEFAULT_FETCH_MODE, PDO::FETCH_ASSOC);
$pdoC->exec('CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT, status TEXT DEFAULT "active", push_webhook TEXT, push_enabled INTEGER DEFAULT 0)');
$pdoC->exec('CREATE TABLE boards (user_id INTEGER PRIMARY KEY, data TEXT, rev INTEGER, updated_at INTEGER)');
$pdoC->exec('CREATE TABLE push_sent (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, slot_key TEXT, kind TEXT, sent_at TEXT, content TEXT)');
$pdoC->exec('CREATE UNIQUE INDEX uq_push_sent ON push_sent (user_id, slot_key)');
add_user($pdoC, 1, HOOK, state_one_med());
$got = [];
$ok = true;
$r = lb_push_tick_run($pdoC, D, '08:00', $sender);
chk('有 content 列时正常发送', $r['sent'] === 1, 'sent=' . $r['sent']);
$row = $pdoC->query('SELECT content FROM push_sent LIMIT 1')->fetch();
chk('正文存进了 content', $row && strpos((string)$row['content'], '阿莫西林') !== false,
    $row ? (string)$row['content'] : '无');

/* 旧库（db() 建的表无 content 列）不能因此崩——上面所有用例已经跑过这情况 */

/* ------------------------------------------------------------------ */
echo "[11] 自定义通知" . PHP_EOL;
$pdoN = db();
add_user($pdoN, 1, HOOK, state_notice(), 1);
$got = [];
$r = lb_push_tick_run($pdoN, D, '20:30', $sender);
chk('到点发出去一条', $r['sent'] === 1, json_encode($r));
chk('正文就是用户写的内容', strpos((string)($got[0] ?? ''), '记得吃维生素') !== false,
    (string)($got[0] ?? ''));
chk('标题带「自定义提醒」', strpos((string)($got[0] ?? ''), '自定义提醒') !== false,
    (string)($got[0] ?? ''));
$r2 = lb_push_tick_run($pdoN, D, '20:30', $sender);
chk('同一分钟再跑一次不重复发', $r2['sent'] === 0 && $r2['skipped'] === 1, json_encode($r2));
$r3 = lb_push_tick_run($pdoN, D, '20:34', $sender);
chk('过了容差窗口也不再补发', $r3['sent'] === 0, json_encode($r3));

echo PHP_EOL . '----------------------------' . PHP_EOL;
echo '通过 ' . $pass . ' 项，失败 ' . $fail . ' 项' . PHP_EOL;
exit($fail === 0 ? 0 : 1);
