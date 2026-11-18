<?php
/* 每日快照的单元验证：不连数据库，只测「整理 — 落盘 — 读回 — 清理」这条链。
 * 运行：php e2e/test-backup.php
 */
declare(strict_types=1);

define('LIFEBOARD_API', true);
require __DIR__ . '/../api/backup.php';

$pass = 0;
$fails = [];

function chk(string $name, bool $ok, string $detail = ''): void
{
    global $pass, $fails;
    if ($ok) {
        $pass++;
        echo "  \u{2713} {$name}\n";
    } else {
        $fails[] = $name . ($detail !== '' ? ' << ' . $detail : '');
        echo "  \u{2717} {$name}" . ($detail !== '' ? "  << {$detail}" : '') . "\n";
    }
}

$dir = sys_get_temp_dir() . '/lb-backup-test-' . bin2hex(random_bytes(4));
$now = strtotime('2026-10-29 12:00:00');

/* ---------------- 1. 备份内容整理 ---------------- */
echo "\n[1] 内容整理\n";
$rows = [
    ['user_id' => '1', 'data' => '{"habits":[],"tasks":[]}', 'rev' => '7'],
    ['user_id' => '2', 'data' => '{"habits":[{"id":"h1"}],"tasks":[]}', 'rev' => '3'],
    ['user_id' => '3', 'data' => '{坏掉的 JSON', 'rev' => '1'],
    ['user_id' => '4', 'rev' => '1'],
    'not-an-array',
];
$payload = lb_backup_payload($rows, '2026-10-29', $now);
chk('坏数据和残缺行被跳过', count($payload['boards']) === 2, (string)count($payload['boards']));
chk('保留了合法用户', isset($payload['boards']['1'], $payload['boards']['2']));
chk('rev 转成整数', $payload['boards']['1']['rev'] === 7);
chk('数据被解析成数组', is_array($payload['boards']['2']['data']));
chk('记下了日期', $payload['date'] === '2026-10-29');
chk('空输入得到空 boards', lb_backup_payload([], '2026-10-29', $now)['boards'] === []);

/* ---------------- 2. 落盘 ---------------- */
echo "\n[2] 写文件\n";
$ok = lb_backup_write($dir, '2026-10-29', $payload);
$file = $dir . '/2026-10-29.php';
chk('写入成功', $ok && is_file($file));
$raw = (string)file_get_contents($file);
chk('首行是 exit 守卫（公网访问也不会吐数据）', strpos($raw, '<?php exit; ?>') === 0, substr($raw, 0, 20));
chk('正文是合法 JSON', is_array(json_decode(substr($raw, strpos($raw, "\n") + 1), true)));
chk('没有留下临时文件', count((array)glob($dir . '/tmp-*.php')) === 0);
chk('拒绝非法日期', lb_backup_write($dir, '../../etc/passwd', $payload) === false);
chk('目录不存在时能自建', (function () use ($payload) {
    $d = sys_get_temp_dir() . '/lb-backup-mk-' . bin2hex(random_bytes(4)) . '/deep';
    $ok = lb_backup_write($d, '2026-10-29', $payload) && is_file($d . '/2026-10-29.php');
    array_map('unlink', (array)glob($d . '/*'));
    @rmdir($d);
    @rmdir(dirname($d));
    return $ok;
})());

/* ---------------- 3. 读回 ---------------- */
echo "\n[3] 读回\n";
$back = lb_backup_read($file);
chk('能读回', is_array($back));
chk('用户数一致', is_array($back) && count($back['boards']) === 2);
chk('内容一致', is_array($back) && $back['boards']['2']['data']['habits'][0]['id'] === 'h1');
chk('文件不存在返回 null', lb_backup_read($dir . '/1999-01-01.php') === null);
$badFile = $dir . '/broken.php';
file_put_contents($badFile, "<?php exit; ?>\n{不是 JSON");
chk('内容损坏返回 null', lb_backup_read($badFile) === null);
unlink($badFile);

/* ---------------- 4. 清理 ---------------- */
echo "\n[4] 清理\n";
$old = $dir . '/2026-09-01.php';
$fresh = $dir . '/2026-10-28.php';
file_put_contents($old, "<?php exit; ?>\n{}");
file_put_contents($fresh, "<?php exit; ?>\n{}");
$stale = $dir . '/tmp-deadbeef.php';
file_put_contents($stale, "<?php exit; ?>\n{}");
touch($stale, $now - 3 * 86400);
$keep = $dir . '/notes.php';
file_put_contents($keep, "<?php // 别删我");
file_put_contents($dir . '/readme.txt', 'x');

$removed = lb_backup_prune($dir, 30, $now);
chk('超过 30 天被删掉', !is_file($old) && $removed === 1, 'removed=' . $removed);
chk('未过期的保留', is_file($fresh));
chk('过期的临时文件被清掉', !is_file($stale));
chk('不属于自己命名的文件不碰', is_file($keep));
chk('非 php 文件不碰', is_file($dir . '/readme.txt'));
chk('今天的备份还在', is_file($file));

/* 30 天边界：正好 30 天内的保留 */
file_put_contents($dir . '/2026-09-30.php', "<?php exit; ?>\n{}");
lb_backup_prune($dir, 30, $now);
chk('第 29 天（09-30）仍在保留期内', is_file($dir . '/2026-09-30.php'));

/* ---------------- 5. 完整链路（用 SQLite 顶替 MySQL 的 boards 表） ---------------- */
echo "\n[5] 完整链路\n";
if (!extension_loaded('pdo_sqlite')) {
    echo "  - 跳过（当前 PHP 没开 pdo_sqlite）\n";
} else {
    $db = new PDO('sqlite::memory:');
    $db->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
    $db->setAttribute(PDO::ATTR_DEFAULT_FETCH_MODE, PDO::FETCH_ASSOC);
    $db->exec('CREATE TABLE boards (user_id INTEGER PRIMARY KEY, data TEXT, rev INTEGER, updated_at INTEGER)');
    $ins = $db->prepare('INSERT INTO boards (user_id, data, rev, updated_at) VALUES (?, ?, ?, ?)');

    $bdir = sys_get_temp_dir() . '/lb-backup-e2e-' . bin2hex(random_bytes(4));

    lb_daily_backup($db, $bdir);
    chk('空库不生成备份', !is_dir($bdir) || count((array)glob($bdir . '/*.php')) === 0);

    $ins->execute([1, '{"habits":[],"tasks":[]}', 5, 1]);
    $ins->execute([2, '{"habits":[{"id":"h1"}],"tasks":[]}', 9, 2]);
    lb_daily_backup($db, $bdir);

    $bfile = $bdir . '/' . date('Y-m-d') . '.php';
    chk('有数据后生成当天文件', is_file($bfile));
    $got = lb_backup_read($bfile);
    chk('两个用户都在里面', is_array($got) && count($got['boards']) === 2);
    chk('rev 与库里一致', is_array($got) && $got['boards']['2']['rev'] === 9,
        is_array($got) ? (string)$got['boards']['2']['rev'] : '');

    clearstatcache();
    $m1 = (int)filemtime($bfile);
    lb_daily_backup($db, $bdir);
    clearstatcache();
    chk('半小时内不重复写盘', (int)filemtime($bfile) === $m1);

    touch($bfile, time() - 3600);
    clearstatcache();
    $db->exec('UPDATE boards SET rev = 10 WHERE user_id = 2');
    lb_daily_backup($db, $bdir);
    clearstatcache();
    $got2 = lb_backup_read($bfile);
    chk('过了间隔会刷新成最新数据', is_array($got2) && $got2['boards']['2']['rev'] === 10,
        is_array($got2) ? (string)$got2['boards']['2']['rev'] : '');

    $db2 = new PDO('sqlite::memory:');
    $db2->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
    $threw = false;
    try {
        lb_daily_backup($db2, $bdir);   // 这张库没有 boards 表
    } catch (Throwable $e) {
        $threw = true;
    }
    chk('查库出错不会把异常抛给调用方', !$threw);

    array_map('unlink', (array)glob($bdir . '/*.php'));
    @rmdir($bdir);
    $db = null;
    $db2 = null;
}

/* ---------------- 收尾 ---------------- */
array_map('unlink', (array)glob($dir . '/*'));
@rmdir($dir);

echo "\n" . str_repeat('=', 46) . "\n";
echo 'PASS ' . $pass . ' / ' . ($pass + count($fails)) . "\n";
if ($fails) {
    foreach ($fails as $f) {
        echo '  FAIL: ' . $f . "\n";
    }
    exit(1);
}
echo "快照逻辑全部通过\n";
