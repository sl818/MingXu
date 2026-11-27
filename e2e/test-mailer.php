<?php
/**
 * 邮件层单测。只测纯逻辑与本地加解密，不发真实 SMTP 请求。
 *
 * 运行：
 *   php -d extension_dir=<php>/ext -d extension=openssl e2e/test-mailer.php
 */

define('LIFEBOARD_API', 1);

/* 便携 PHP 默认不带 openssl，缺了会让「加密组件可用」等 4 项直接红。
   这里显式提示，避免把环境问题误读成代码缺陷。 */
if (!function_exists('openssl_encrypt')) {
    echo "警告：当前 PHP 未加载 openssl，加密相关用例会失败。
";
    echo "      用 -d extension_dir=<php>/ext -d extension=openssl 重跑。

";
}

/* secret_box / mailer 依赖 bootstrap 里的两个小工具，这里给最小替身，
   避免测试去连真实数据库。mail_secret 固定值只用于本测试进程。 */
function lb_config(): array
{
    return ['mail_secret' => str_repeat('a', 64)];
}
function lb_strlen(string $value): int
{
    return function_exists('mb_strlen') ? (int)mb_strlen($value, 'UTF-8') : strlen($value);
}

require __DIR__ . '/../api/secret_box.php';
require __DIR__ . '/../api/mailer.php';

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

echo "[1] SMTP 主机校验（防 SSRF）" . PHP_EOL;
chk('smtp.qq.com 通过', lb_mail_host_ok('smtp.qq.com'));
chk('smtp.exmail.qq.com 通过', lb_mail_host_ok('smtp.exmail.qq.com'));
chk('空串拒绝', !lb_mail_host_ok(''));
chk('IPv4 拒绝', !lb_mail_host_ok('127.0.0.1'));
chk('IPv6 拒绝', !lb_mail_host_ok('::1'));
chk('localhost 拒绝', !lb_mail_host_ok('localhost'));
chk('.local 内网域名拒绝', !lb_mail_host_ok('mail.local'));
chk('带端口的写法拒绝', !lb_mail_host_ok('smtp.qq.com:465'));
chk('乱字符拒绝', !lb_mail_host_ok('not a host'));

echo PHP_EOL . "[2] 端口 / 协议 / 发件人" . PHP_EOL;
chk('465 允许', lb_mail_port_ok(465));
chk('587 允许', lb_mail_port_ok(587));
chk('80 拒绝', !lb_mail_port_ok(80));
chk('ssl 允许', lb_mail_secure_ok('ssl'));
chk('tls 允许', lb_mail_secure_ok('tls'));
chk('none 允许', lb_mail_secure_ok('none'));
chk('starttls 拒绝（界面值必须统一）', !lb_mail_secure_ok('starttls'));
chk('发件人与用户名一致通过', lb_mail_from_ok('a@qq.com', 'a@qq.com'));
chk('大小写不同仍视为同一账号', lb_mail_from_ok('A@qq.com', 'a@qq.com'));
chk('冒用别的发件人被挡', !lb_mail_from_ok('b@qq.com', 'a@qq.com'));
chk('非邮箱被挡', !lb_mail_from_ok('notmail', 'notmail'));

echo PHP_EOL . "[3] QQ 官方报错翻译" . PHP_EOL;
$v = lb_mail_explain(535, 'Authentication failed', 'auth');
chk('535 指向授权码', strpos($v['msg'], '16 位授权码') !== false && strpos($v['msg'], '不是 QQ 登录密码') !== false, $v['msg']);
chk('535 提示改密码后授权码失效', strpos($v['msg'], '旧授权码会全部失效') !== false, $v['msg']);
$v = lb_mail_explain(550, 'Invalid "From" found in header');
chk('550 Invalid From 指向发件人一致', strpos($v['msg'], '必须和登录账号完全一致') !== false, $v['msg']);
$v = lb_mail_explain(550, 'Sender frequency limited');
chk('550 frequency 指向账号级限流', strpos($v['msg'], '换 IP 或换域名都没用') !== false, $v['msg']);
chk('250 判成功', lb_mail_explain(250, 'ok')['ok']);
chk('421 提示稍后再试', strpos(lb_mail_explain(421, 'service unavailable')['msg'], '稍后再试') !== false);
chk('0 = 连接超时', strpos(lb_mail_explain(0, '')['msg'], '超时') !== false);

echo PHP_EOL . "[4] MIME 编码" . PHP_EOL;
chk('中文主题走 RFC2047', strpos(lb_mail_header_text('该吃药了'), '=?UTF-8?B?') === 0);
chk('纯 ASCII 主题不编码', lb_mail_header_text('Test Mail') === 'Test Mail');
chk('主题里的换行被剥掉', strpos(lb_mail_header_text("a\r\nBcc: x@y.com"), "\n") === false);
$wrapped = lb_mail_body_b64(str_repeat('用药提醒内容', 200));
$lines = explode("\r\n", $wrapped);
$max = 0;
foreach ($lines as $line) {
    $max = max($max, strlen($line));
}
chk('base64 每行不超过 76 列', $max <= 76, 'max=' . $max);
chk('base64 往返一致', base64_decode(str_replace("\r\n", '', $wrapped), true) === str_repeat('用药提醒内容', 200));

echo PHP_EOL . "[5] 授权码加解密" . PHP_EOL;
chk('加密组件可用', lb_secret_ready());
$enc = lb_secret_encrypt('abcdefghijklmnop');
chk('密文非空', $enc !== '');
chk('密文不含明文授权码', strpos($enc, 'abcdefghijklmnop') === false);
chk('解密回到原文', lb_secret_decrypt($enc) === 'abcdefghijklmnop');
chk('密文被篡改后解密失败', lb_secret_decrypt(substr($enc, 0, -4) . 'AAAA') === '');
chk('中文授权码往返一致', lb_secret_decrypt(lb_secret_encrypt('授权码中文测试')) === '授权码中文测试');
chk('空串不加密', lb_secret_encrypt('') === '');

echo PHP_EOL . "[6] 发送前的配置拦截（不发网络）" . PHP_EOL;
$base = [
    'host' => 'smtp.qq.com', 'port' => 465, 'secure' => 'ssl',
    'user' => 'a@qq.com', 'from' => 'a@qq.com', 'name' => '明序', 'secret' => 'x',
];
$why = '';
chk('合法配置的各项校验都通过',
    lb_mail_host_ok($base['host']) && lb_mail_port_ok($base['port'])
    && lb_mail_secure_ok($base['secure']) && lb_mail_from_ok($base['from'], $base['user']));
$bad = $base;
$bad['host'] = '127.0.0.1';
lb_mail_send($bad, 'a@qq.com', '主题', '正文', $why);
chk('内网地址被挡', strpos($why, '服务器地址不合法') !== false, $why);
$bad = $base;
$bad['port'] = 80;
lb_mail_send($bad, 'a@qq.com', '主题', '正文', $why);
chk('非 SMTP 端口被挡', strpos($why, '端口只能用') !== false, $why);
$bad = $base;
$bad['from'] = 'b@qq.com';
lb_mail_send($bad, 'a@qq.com', '主题', '正文', $why);
chk('发件人不一致被挡（550 Invalid From 的预防）', strpos($why, '必须和用户名') !== false, $why);
$bad = $base;
$bad['user'] = 'notmail';
lb_mail_send($bad, 'a@qq.com', '主题', '正文', $why);
chk('用户名不是完整邮箱被挡', strpos($why, '完整邮箱地址') !== false, $why);

echo PHP_EOL . '[7] 通知邮件 HTML 卡片（v211）' . PHP_EOL;
$card = lb_notify_mail_card('该吃药了 <x>', "阿莫西林 1片\n记得饭后", '明序 · 测试', 'green');
chk('卡片是 HTML', strpos($card, '<div') === 0);
chk('标题被转义', strpos($card, '&lt;x&gt;') !== false && strpos($card, '<x>') === false);
chk('换行转成 br', strpos($card, '阿莫西林 1片<br') !== false);
chk('主题色生效', strpos($card, '#0c6e42') !== false);
chk('页脚写入', strpos($card, '明序 · 测试') !== false);

echo PHP_EOL . "通过 " . $pass . " / " . ($pass + $fail) . PHP_EOL;
exit($fail > 0 ? 1 : 0);
