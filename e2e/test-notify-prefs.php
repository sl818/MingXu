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

echo '[14] 11 板块默认结构（v211）' . PHP_EOL;
$bd = lb_notify_boards();
chk('11 个板块齐全', count($bd) === 11, (string)count($bd));
chk('模块五板块不存 on',
    !isset($bd['med']['on']) && !isset($bd['water']['on']) && !isset($bd['quit']['on']));
chk('基础板块有 on 且默认开', $bd['task']['on'] === true && $bd['notice']['on'] === true);
chk('三个渠道列齐全（含浏览器）', array_keys($bd['notice']['channels']) === ['wecom', 'mail', 'browser']);
chk('还款板块渠道默认开（是否发送由 money.notify 管）', $bd['debt']['channels']['wecom'] === true);

echo '[15] 旧扁平结构原地迁移' . PHP_EOL;
$pdo15 = db();
$pdo15->prepare('INSERT INTO app_settings (k, v) VALUES (?, ?)')->execute(['notify_prefs_15', json_encode([
    'med' => ['wecom' => true, 'mail' => false],
    'habit' => ['wecom' => false, 'mail' => false],
    'report' => ['wecom' => true, 'mail' => false],
], JSON_UNESCAPED_UNICODE)]);
$b15 = lb_notify_boards_load($pdo15, 15);
chk('med 渠道保留', $b15['med']['channels']['wecom'] === true && $b15['med']['channels']['mail'] === false);
chk('habit 渠道继承给 water/move/breathe',
    $b15['water']['channels']['wecom'] === false && $b15['move']['channels']['mail'] === false
    && $b15['breathe']['channels']['wecom'] === false);
chk('没出现的类型保持默认', $b15['notice']['channels']['wecom'] === true);
chk('旧结构投影回 7 类仍正确', lb_notify_prefs_flat($b15)['habit'] === ['wecom' => false, 'mail' => false]);

echo '[16] 新结构保存与模块 on 丢弃' . PHP_EOL;
$pdo16 = db();
$res16 = lb_notify_boards_save($pdo16, 16, ['boards' => [
    'med' => ['on' => false, 'channels' => ['wecom' => false, 'mail' => true, 'browser' => true]],
    'task' => ['on' => false, 'channels' => ['wecom' => true, 'mail' => false]],
    'water' => ['on' => false],
]]);
$b16 = lb_notify_boards_load($pdo16, 16);
chk('新结构保存成功', $res16['ok'] === true, (string)($res16['error'] ?? ''));
chk('模块板块的 on 入参被丢弃', !isset($b16['med']['on']));
chk('模块渠道照常保存',
    $b16['med']['channels']['wecom'] === false && $b16['med']['channels']['mail'] === true);
chk('基础板块 on 可单独关', $b16['task']['on'] === false);
chk('未提交的渠道保持默认', $b16['task']['channels']['browser'] === true);

echo '[17] 免打扰时段可配（跨夜）' . PHP_EOL;
$pdo17 = db();
chk('默认关 + 23:00–07:00',
    lb_notify_quiet_cfg($pdo17, 17) === ['on' => false, 'start' => '23:00', 'end' => '07:00']);
lb_notify_quiet_save($pdo17, 17, ['on' => true, 'start' => '22:30', 'end' => '06:30']);
$q2 = lb_notify_quiet_cfg($pdo17, 17);
chk('对象保存后读回', $q2['on'] === true && $q2['start'] === '22:30' && $q2['end'] === '06:30',
    json_encode($q2));
chk('22:30 命中', lb_notify_in_quiet('22:30', '22:30', '06:30') === true);
chk('06:29 命中', lb_notify_in_quiet('06:29', '22:30', '06:30') === true);
chk('06:30 不命中', lb_notify_in_quiet('06:30', '22:30', '06:30') === false);
chk('12:00 不命中', lb_notify_in_quiet('12:00', '22:30', '06:30') === false);
chk('起止相同视为不生效', lb_notify_in_quiet('23:00', '23:00', '23:00') === false);
$pdo17->prepare('INSERT INTO app_settings (k, v) VALUES (?, ?)')->execute(['notify_quiet_18', '1']);
chk('旧布尔存储仍可读', lb_notify_quiet_cfg($pdo17, 18)['on'] === true);

echo '[18] 文案模板与渲染' . PHP_EOL;
$pdo18 = db();
$tpl = lb_notify_tpl_load($pdo18, 18);
chk('默认 11 个场景', count($tpl['scenes']) === 11, (string)count($tpl['scenes']));
chk('用药默认标题固定', $tpl['scenes']['med']['title'] === '该吃药了');
$sv18 = lb_notify_tpl_save($pdo18, 18, [
    'scenes' => ['med' => ['title' => '吃药 {时间}', 'body' => "{正文}\n{优先级}"]],
    'mail' => ['color' => 'green', 'footer' => '测试页脚'],
]);
chk('模板保存成功', $sv18['ok'] === true, (string)($sv18['error'] ?? ''));
$tpl2 = lb_notify_tpl_load($pdo18, 18);
chk('自定义标题读回', $tpl2['scenes']['med']['title'] === '吃药 {时间}');
chk('邮件配色与页脚读回', $tpl2['mail']['color'] === 'green' && $tpl2['mail']['footer'] === '测试页脚');
chk('邮件样式默认 HTML 卡片', $tpl2['mail']['mode'] === 'html', (string)($tpl2['mail']['mode'] ?? ''));
lb_notify_tpl_save($pdo18, 18, ['mail' => ['mode' => 'plain']]);
chk('可切换为纯文本', lb_notify_tpl_load($pdo18, 18)['mail']['mode'] === 'plain');
lb_notify_tpl_save($pdo18, 18, ['mail' => ['mode' => 'xxx']]);
chk('非法模式不覆盖原值', lb_notify_tpl_load($pdo18, 18)['mail']['mode'] === 'plain');

$evMed = ['kind' => 'med', 'source' => 'med', 'id' => 'm1', 'time' => '08:00',
    'title' => '该吃药了', 'body' => '阿莫西林 1片', 'priority' => '紧急'];
chk('渲染替换变量', lb_notify_text_render($tpl2, $evMed) === "吃药 08:00\n阿莫西林 1片\n紧急",
    lb_notify_text_render($tpl2, $evMed));

$evWater = ['kind' => 'habit', 'source' => 'water', 'id' => 'h_water', 'time' => '10:00',
    'title' => '喝水', 'body' => '还差 4 杯', 'priority' => '日常'];
chk('未知场景回退 kind 模板', strpos(lb_notify_text_render($tpl2, $evWater), '喝水') !== false,
    lb_notify_text_render($tpl2, $evWater));
chk('板块映射：water 归 water', lb_notify_board_of($evWater) === 'water');
chk('板块映射：测试消息归自定义提醒', lb_notify_board_of(['kind' => 'notice', 'source' => 'test']) === 'notice');
chk('板块映射：无 source 的 habit 归 habit', lb_notify_board_of(['kind' => 'habit']) === 'habit');

echo '[19] 板块停用真的拦发送（接线）' . PHP_EOL;
$pdo19 = db();
$pdo19->prepare('INSERT INTO users (id, email, status, push_webhook, push_enabled) VALUES (?, ?, ?, ?, 1)')
    ->execute([19, 'u19@example.com', 'active', HOOK]);
$pdo19->prepare('INSERT INTO user_mail_config (user_id, enabled) VALUES (?, 1)')->execute([19]);
$taskState = ['tasks' => [[
    'id' => 't1', 'title' => '交报告', 'status' => 'todo', 'due' => D,
    'repeat' => 'none', 'notifyTime' => HM,
]]];
$pdo19->prepare('INSERT INTO boards (user_id, data) VALUES (?, ?)')
    ->execute([19, json_encode($taskState, JSON_UNESCAPED_UNICODE)]);
lb_notify_boards_save($pdo19, 19, ['boards' => ['task' => ['on' => false]]]);
$log19 = [];
lb_push_tick_run($pdo19, D, HM, channels($log19));
chk('停用待办板块后不发送', $log19 === [], implode(',', $log19));

lb_notify_boards_save($pdo19, 19, ['boards' => ['task' => ['on' => true]]]);
$log19b = [];
lb_push_tick_run($pdo19, D, HM, channels($log19b));
chk('重新启用后照常发送', $log19b === ['wecom', 'mail'], implode(',', $log19b));

echo '[20] 自定义免打扰时段真的拦发送' . PHP_EOL;
$pdo20 = db();
add_user($pdo20, 20, '21:30');
lb_notify_quiet_save($pdo20, 20, ['on' => true, 'start' => '21:00', 'end' => '22:00']);
$log20 = [];
$r20 = lb_push_tick_run($pdo20, D, '21:30', channels($log20));
chk('21:30 命中自定义时段，一条不发',
    $log20 === [] && ($r20['quiet_skipped'] ?? 0) === 1, implode(',', $log20));
lb_notify_quiet_save($pdo20, 20, ['on' => false, 'start' => '21:00', 'end' => '22:00']);
$log20b = [];
lb_push_tick_run($pdo20, D, '21:30', channels($log20b));
chk('关掉后同一时刻照发', count($log20b) > 0, implode(',', $log20b));

echo '[21] 全局通知总闸（v212）' . PHP_EOL;
$pdo21 = db();
add_user($pdo21, 21);
chk('默认开（没配过不能一条都不发）', lb_notify_global_load($pdo21, 21) === true);
lb_notify_global_save($pdo21, 21, false);
chk('关掉后读回 false', lb_notify_global_load($pdo21, 21) === false);
$log21 = [];
$r21 = lb_push_tick_run($pdo21, D, HM, channels($log21));
chk('总闸关闭时一条不发',
    $log21 === [] && ($r21['global_skipped'] ?? 0) === 1, implode(',', $log21));
lb_notify_global_save($pdo21, 21, true);
$log21b = [];
lb_push_tick_run($pdo21, D, HM, channels($log21b));
chk('重新打开后照常发送', count($log21b) > 0, implode(',', $log21b));

echo '[22] 部分更新：模块页只提交一个板块，其他板块不被重置（v216）' . PHP_EOL;
$pdo22 = db();
add_user($pdo22, 22);
/* 先存一套「非默认」配置：water 只走邮件、task 板块停用、小结只走企微 */
lb_notify_boards_save($pdo22, 22, ['boards' => [
    'water' => ['channels' => ['wecom' => false, 'mail' => true, 'browser' => true]],
    'task' => ['on' => false],
    'report' => ['channels' => ['wecom' => true, 'mail' => false, 'browser' => true]],
]]);
/* 模块页（喝水）只提交自己板块的一个字段：其余字段与其他板块必须原样保留 */
lb_notify_boards_save($pdo22, 22, ['boards' => [
    'water' => ['channels' => ['wecom' => true]],
]]);
$b22 = lb_notify_boards_load($pdo22, 22);
chk('water.wecom 按提交改为 true', $b22['water']['channels']['wecom'] === true);
chk('water.mail 保持已存值 true（不被默认 false 冲掉）', $b22['water']['channels']['mail'] === true);
chk('water.browser 保持已存值 true', $b22['water']['channels']['browser'] === true);
chk('task.on 保持已存值 false（板块没提交就不能被重置）', $b22['task']['on'] === false);
chk('report.channels 保持已存值', $b22['report']['channels']['wecom'] === true
    && $b22['report']['channels']['mail'] === false);

echo '[23] 运动实例级通知：开关与渠道（v216）' . PHP_EOL;
$pdo23 = db();
add_user($pdo23, 23);
/* 造一个每天 HM 提醒的运动实例 */
$pdo23->prepare('UPDATE boards SET data = ? WHERE user_id = 23')->execute([json_encode([
    'modules' => ['move' => ['on' => true, 'sports' => [[
        'id' => 'sp1', 'key' => 'run', 'name' => '晨跑',
        'startTime' => HM, 'freqKind' => 'daily', 'recMode' => 'manual',
    ]]],
]], JSON_UNESCAPED_UNICODE)]);
/* 无实例配置：回落板块渠道（move 默认只走企微） */
$log23 = [];
lb_push_tick_run($pdo23, D, HM, channels($log23));
chk('无实例配置回落板块：只发企微', $log23 === ['wecom'], implode(',', $log23));

/* 实例关闭：整条不发，且计数进 instance_skipped */
lb_notify_boards_save($pdo23, 23, ['boards' => ['move' => ['instances' => [
    'sp1' => ['on' => false],
]]]]);
$log23 = [];
$r23 = lb_push_tick_run($pdo23, D, HM, channels($log23));
chk('实例关闭 → 一条不发', $log23 === [], implode(',', $log23));
chk('实例关闭计入 instance_skipped', ($r23['instance_skipped'] ?? 0) >= 1,
    json_encode($r23));

/* v216：实例关闭的 skip 进历史记录（tick 前 log 表要存在才记） */
$pdo23->exec('CREATE TABLE IF NOT EXISTS push_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, at TEXT,
    channel TEXT, kind TEXT, slot_key TEXT, content TEXT, status TEXT, error TEXT)');
$pdo23->prepare('DELETE FROM push_log WHERE user_id = 23')->execute();
$log23 = [];
lb_push_tick_run($pdo23, D, HM, channels($log23));
$rSkip = $pdo23->query("SELECT status, error FROM push_log WHERE user_id = 23")->fetchAll();
chk('实例关闭记一条 skip（原因=该运动的通知已关闭）',
    count($rSkip) === 1 && $rSkip[0]['status'] === 'skip'
    && strpos((string)$rSkip[0]['error'], '已关闭') !== false,
    json_encode($rSkip));

/* 实例渠道覆盖板块：板块 mail=false，实例只勾邮件 → 发邮件、不发企微 */
lb_notify_boards_save($pdo23, 23, ['boards' => ['move' => ['instances' => [
    'sp1' => ['on' => true, 'channels' => ['wecom' => false, 'mail' => true, 'browser' => true]],
]]]]);
$log23 = [];
lb_push_tick_run($pdo23, D, HM, channels($log23));
chk('实例渠道覆盖板块：只发邮件', $log23 === ['mail'], implode(',', $log23));

/* 白名单清洗：脏键与非法结构进不来 */
lb_notify_boards_save($pdo23, 23, ['boards' => ['move' => ['instances' => [
    'sp1' => ['on' => 1, 'channels' => ['wecom' => 1, 'foo' => 1]],
    '' => ['on' => false],
    'ok2' => 'not-array',
]]]]);
$b23 = lb_notify_boards_load($pdo23, 23);
$ins23 = $b23['move']['instances'];
chk('实例 on 归一化为布尔', isset($ins23['sp1']) && $ins23['sp1']['on'] === true);
chk('实例渠道只认三键', isset($ins23['sp1']['channels']['wecom'])
    && !isset($ins23['sp1']['channels']['foo']), json_encode($ins23['sp1'] ?? null));
chk('空 id 与非法结构的实例被丢弃', !isset($ins23['']) && !isset($ins23['ok2']),
    json_encode(array_keys($ins23)));

echo PHP_EOL . str_repeat('-', 46) . PHP_EOL;
echo '通知通道矩阵：通过 ' . $pass . ' 项，失败 ' . $fail . ' 项' . PHP_EOL;
exit($fail > 0 ? 1 : 0);
