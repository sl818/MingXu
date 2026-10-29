<?php
/* 晚风Todo · 每日快照
 *
 * 为什么要有这个：历史版本表 board_revisions 和主数据在同一个库，
 * 库挂了、被误删、或者机房出事，主数据和「后悔药」会一起没。
 * 所以每天再往文件系统落一份，跟数据库彻底分开。
 *
 * 为什么不用 cron：任意一次 API 请求都会顺手补上当天的备份，
 * 宝塔里不用配定时任务，也不怕任务没启动。
 *
 * 为什么写成 .php 而不是 .json：备份在站点目录下，万一被公网访问到，
 * PHP 会执行首行的 exit 直接退出，不会把整份隐私数据吐出去。
 * 取回时用编辑器删掉第一行，剩下的就是纯 JSON。
 */
if (!defined('LIFEBOARD_API')) {
    http_response_code(404);
    exit;
}

const LB_BACKUP_KEEP_DAYS = 30;   // 保留天数
const LB_BACKUP_MIN_GAP = 1800;   // 当天已有备份时，半小时内不重复写

function lb_backup_dir(): string
{
    return __DIR__ . '/../backups';
}

/* 只认自己写出来的文件名，别的文件一概不碰 */
function lb_backup_is_mine(string $path): bool
{
    return (bool)preg_match('/^\d{4}-\d{2}-\d{2}\.php$/', basename($path));
}

/* 把查出来的 boards 行整理成备份结构。纯函数，方便单独验证。 */
function lb_backup_payload(array $rows, string $date, int $now): array
{
    $boards = [];
    foreach ($rows as $row) {
        if (!is_array($row) || !array_key_exists('user_id', $row) || !array_key_exists('data', $row)) {
            continue;
        }
        $data = json_decode((string)$row['data'], true);
        if (!is_array($data)) {
            continue;   // 坏数据跳过，别让一条坏记录毁掉整份备份
        }
        $boards[(string)$row['user_id']] = [
            'rev' => (int)($row['rev'] ?? 0),
            'data' => $data,
        ];
    }
    return ['at' => date('c', $now), 'date' => $date, 'boards' => $boards];
}

function lb_backup_write(string $dir, string $date, array $payload): bool
{
    if (!preg_match('/^\d{4}-\d{2}-\d{2}$/', $date)) {
        return false;
    }
    if (!is_dir($dir) && !@mkdir($dir, 0750, true) && !is_dir($dir)) {
        return false;
    }
    $json = json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    if ($json === false) {
        return false;
    }
    $final = $dir . '/' . $date . '.php';
    /* 临时文件也用 .php 结尾：万一写一半被访问，只会执行 exit，不会泄露半个文件 */
    $tmp = $dir . '/tmp-' . bin2hex(random_bytes(6)) . '.php';
    if (@file_put_contents($tmp, "<?php exit; ?>\n" . $json) === false) {
        return false;
    }
    @chmod($tmp, 0640);
    if (!@rename($tmp, $final)) {
        @unlink($tmp);
        return false;
    }
    @chmod($final, 0640);
    return true;
}

/* 读回备份：跳过首行的 exit 守卫，剩下就是 JSON */
function lb_backup_read(string $file): ?array
{
    if (!is_file($file)) {
        return null;
    }
    $raw = @file_get_contents($file);
    if ($raw === false) {
        return null;
    }
    $pos = strpos($raw, "\n");
    if ($pos === false) {
        return null;
    }
    $data = json_decode(substr($raw, $pos + 1), true);
    return is_array($data) ? $data : null;
}

/* 清掉过期备份和写失败留下的临时文件，返回删了几个正式备份 */
function lb_backup_prune(string $dir, int $keepDays, int $now): int
{
    $removed = 0;
    $limit = $now - $keepDays * 86400;
    $files = glob($dir . '/*.php');
    if (!is_array($files)) {
        return 0;
    }
    foreach ($files as $file) {
        $base = basename($file);
        $mtime = @filemtime($file);
        if ($mtime === false) {
            continue;
        }
        if (strpos($base, 'tmp-') === 0) {
            if ($mtime < $now - 86400) {
                @unlink($file);   // 写一半留下的垃圾，超过一天就清
            }
            continue;
        }
        if (!lb_backup_is_mine($file)) {
            continue;
        }
        $ts = strtotime(substr($base, 0, 10) . ' 00:00:00');
        if ($ts !== false && $ts < $limit) {
            if (@unlink($file)) {
                $removed++;
            }
        }
    }
    return $removed;
}

/* 入口。一天最多备一份，当天已有且不超过半小时就跳过，
   所以正常使用下每天写盘十几次，不会每保存一次就落一遍。
   $pdo / $dir 只在测试时注入（用 SQLite 和临时目录），线上不传。 */
function lb_daily_backup(?PDO $pdo = null, ?string $dir = null): void
{
    try {
        $dir = $dir !== null ? $dir : lb_backup_dir();
        $now = time();
        $date = date('Y-m-d', $now);
        $file = $dir . '/' . $date . '.php';

        if (is_file($file)) {
            $mtime = @filemtime($file);
            if ($mtime !== false && $mtime > $now - LB_BACKUP_MIN_GAP) {
                return;
            }
        }

        $rows = ($pdo !== null ? $pdo : lb_db())->query('SELECT user_id, data, rev FROM boards')->fetchAll();
        if (!$rows) {
            return;   // 还没有任何数据，没必要备
        }

        $payload = lb_backup_payload($rows, $date, $now);
        if (!$payload['boards']) {
            return;
        }

        if (lb_backup_write($dir, $date, $payload)) {
            lb_backup_prune($dir, LB_BACKUP_KEEP_DAYS, $now);
        }
    } catch (Throwable $e) {
        // 备份失败绝不能影响正常读写
        error_log('lifeboard backup: ' . $e->getMessage());
    }
}
