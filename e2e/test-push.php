<?php
/**
 * 推送层单测。只测纯逻辑（URL 校验、截断、响应解析），不发真实网络请求。
 *
 * 运行：
 *   php e2e/test-push.php
 *   php -d extension_dir=<php>/ext -d extension=openssl -d extension=curl e2e/test-push.php
 */

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

$GOOD = 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee';

echo "[1] webhook 地址校验" . PHP_EOL;
chk('标准地址通过', lb_push_url_ok($GOOD));
chk('空串不通过', !lb_push_url_ok(''));
chk('http 明文不通过', !lb_push_url_ok(str_replace('https://', 'http://', $GOOD)));
chk('别的域名不通过', !lb_push_url_ok('https://evil.example.com/cgi-bin/webhook/send?key=x'));
chk('相似域名不通过', !lb_push_url_ok('https://qyapi.weixin.qq.com.evil.com/cgi-bin/webhook/send?key=x'));
chk('路径不对不通过', !lb_push_url_ok('https://qyapi.weixin.qq.com/cgi-bin/webhook/other?key=x'));
chk('完全不是 URL 不通过', !lb_push_url_ok('not a url'));

echo PHP_EOL . "[2] 超长内容截断" . PHP_EOL;
$short = '该吃阿莫西林了 · 1 片';
chk('短内容原样返回', lb_push_clip($short) === $short);

$long = str_repeat('阿莫西林缓释胶囊', 300);   // 2400 字 ≈ 7200 字节
$clipped = lb_push_clip($long, 2000);
chk('超长被截到上限以内', strlen($clipped) <= 2000, 'len=' . strlen($clipped));
chk('截断后仍是合法 UTF-8（中文没被切坏）', preg_match('//u', $clipped) === 1);
chk('末尾加了省略号', substr($clipped, -3) === '…');

/* 边界：边界正好落在一个三字节汉字的中间，必须整个字符砍掉 */
$s = str_repeat('a', 1998) . '中';
$c = lb_push_clip($s, 2000);
chk('边界卡在多字节字符中间时整字丢弃', preg_match('//u', $c) === 1 && strlen($c) <= 2000,
    'len=' . strlen($c));

/* 1994 + 「中文」6 字节 = 2000，正好等于上限，不该被动 */
$s2 = str_repeat('a', 1994) . '中文';
$c2 = lb_push_clip($s2, 2000);
chk('刚好放得下时不截断', $c2 === $s2, 'len=' . strlen($c2));

echo PHP_EOL . "[3] 响应解析" . PHP_EOL;
$v = lb_push_interpret(200, '{"errcode":0,"errmsg":"ok"}');
chk('errcode 0 判成功', $v['ok']);

$v = lb_push_interpret(200, '{"errcode":93000,"errmsg":"invalid webhook url"}');
chk('93000 判失败', !$v['ok']);
chk('93000 提示 key 错误', strpos($v['msg'], 'webhook 地址无效') !== false, $v['msg']);

$v = lb_push_interpret(200, '{"errcode":45009,"errmsg":"api freq out of limit"}');
chk('45009 提示频率超限', !$v['ok'] && strpos($v['msg'], '每分钟') !== false, $v['msg']);

$v = lb_push_interpret(500, 'oops');
chk('HTTP 500 判失败并带状态码', !$v['ok'] && strpos($v['msg'], '500') !== false, $v['msg']);

$v = lb_push_interpret(200, '<html>502 Bad Gateway</html>');
chk('返回 HTML 时不崩，报「不是 JSON」', !$v['ok'] && strpos($v['msg'], 'JSON') !== false, $v['msg']);

$v = lb_push_interpret(200, '');
chk('空响应判失败', !$v['ok']);

$v = lb_push_interpret(200, '{"errcode":12345,"errmsg":"something"}');
chk('未知错误码带上原始 errcode', !$v['ok'] && strpos($v['msg'], '12345') !== false, $v['msg']);

echo PHP_EOL . "[4] 发送前置校验（不发网络）" . PHP_EOL;
$err = null;
chk('空 webhook 直接失败，不尝试连接', lb_push_send('', 'x', 'text', $err) === false && $err !== '');
chk('非法域名直接失败', lb_push_send('https://127.0.0.1/x', 'x', 'text', $err) === false);
chk('空白内容直接失败', lb_push_send($GOOD, "  \n ", 'text', $err) === false);
chk('内容为空时给出原因', $err === '内容为空', (string)$err);

echo PHP_EOL . '----------------------------' . PHP_EOL;
echo '通过 ' . $pass . ' 项，失败 ' . $fail . ' 项' . PHP_EOL;
exit($fail === 0 ? 0 : 1);
