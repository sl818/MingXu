<?php
/* ============================================================
   云同步配置示例
   ------------------------------------------------------------
   用法：复制本文件为 api/config.php，按自己的环境改数据库信息。

       cp api/config.example.php api/config.php

   api/config.php 已在 .gitignore 里，**不要把它提交到仓库**。
   也可以不建这个文件，直接访问 install/ 走安装向导，它会自动生成。
   这个文件只被 PHP include，不直接对外输出；仍建议把权限设为 640。
   ============================================================ */
if (!defined('LIFEBOARD_API')) {
    http_response_code(404);
    exit;
}

return [
    'db' => [
        'host' => '127.0.0.1',
        'port' => 3306,
        'name' => 'lifeboard',
        'user' => 'lifeboard',
        'pass' => 'CHANGE_ME',
        'charset' => 'utf8mb4',
    ],

    // 会话 Cookie 名称，可保持默认
    'session_name' => 'LIFEBOARD_SID',

    // 单次保存的 JSON 上限（字节）。默认 4MB，足够整份看板数据。
    'max_bytes' => 4 * 1024 * 1024,

    // Cookie 是否只在 HTTPS 下发送：'auto' 自动判断，也可写 true / false。
    // 正式站点建议保持 'auto'；纯 HTTP 测试时它会自动关闭 Secure。
    'cookie_secure' => 'auto',

    // 邮件提醒：加密授权码用的密钥。强烈建议配置成 64 位十六进制随机串，
    // 生成方法：php -r "echo bin2hex(random_bytes(32));"
    // 留空也能跑：程序会自动在 app_settings 里生成一把并长期保存。
    // 千万别填占位字符串——公开可推算的密钥等于没加密。
    // 注意：换掉这把密钥后，所有用户已存的授权码都解不开，需要重新填写。
    'mail_secret' => '',
];
