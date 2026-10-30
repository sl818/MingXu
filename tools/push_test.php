<?php
/**
 * 命令行发送测试：验证企业微信机器人的 webhook 是否真的能到手机。
 *
 * 用法：
 *   php tools/push_test.php "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxxx"
 *   php tools/push_test.php "https://..." "自定义内容"
 *   LB_PUSH_WEBHOOK="https://..." php tools/push_test.php
 *
 * 只允许命令行运行。这个脚本会把 key 当参数收下，
 * 如果开放在公网上，访问日志里就会留下完整的 webhook 地址——
 * 拿到地址的人可以往你的群里发任何消息。所以浏览器访问一律拒绝。
 *
 * 这个文件不写任何配置、不留任何痕迹；key 属于敏感信息，输出时一律脱敏。
 */

if (PHP_SAPI !== 'cli') {
    http_response_code(403);
    header('Content-Type: text/plain; charset=utf-8');
    echo "这个脚本只能在命令行运行。\n";
    exit(1);
}

require __DIR__ . '/../api/push.php';

$webhook = getenv('LB_PUSH_WEBHOOK') ?: ($argv[1] ?? '');
$msg = $argv[2] ?? '';

/* 脱敏：只留前 8 位和后 4 位，方便确认填的是哪一条，又不至于泄露 */
function lb_mask(string $url): string
{
    if (!preg_match('/key=([^&]+)/', $url, $m)) {
        return $url === '' ? '(空)' : substr($url, 0, 40) . '…';
    }
    $k = $m[1];
    $n = strlen($k);
    if ($n <= 12) {
        return 'key=' . substr($k, 0, 4) . '****';
    }
    return 'key=' . substr($k, 0, 8) . '****' . substr($k, -4);
}

if ($msg === '') {
    $msg = "晚风 Todo 测试消息\n"
        . '时间是 ' . date('Y-m-d H:i:s') . "\n"
        . '如果你在手机上看到这条，说明推送通道已经通了。';
}

$start = microtime(true);
$ok = lb_push_send($webhook, $msg, $err);
$cost = (int)round((microtime(true) - $start) * 1000);

$lines = [
    'webhook：' . lb_mask($webhook),
    '结果：' . ($ok ? '成功' : '失败'),
    '耗时：' . $cost . ' ms',
];
if (!$ok) {
    $lines[] = '原因：' . $err;
}

echo implode(PHP_EOL, $lines), PHP_EOL;
exit($ok ? 0 : 1);
