# 邮件提醒（QQ 邮箱 SMTP）

> 最后更新：v119（2026-11-19）
>
> 本文只讲发信。QQ 邮箱官方文档见文末「参考链接」，参数是照文档抄的，不是凭印象写的。

## 0. 先说两个与需求描述不一致的事实

动手前核对了当前仓库（含全部 Git 历史），有两处必须先讲清楚，避免交付物被误读：

1. **项目里原本没有 `secret_box.php`，也没有任何加密类。** 需求写的是「复用项目自带的加密类」，实际不存在。本次按调用方约定的文件名**新建** `api/secret_box.php`，使用 PHP 原生 `openssl` 的 AES-256-GCM，不引入 composer 依赖。行为与「复用」一致，但它是新增文件，不是修改既有文件。
2. **项目里原本没有 IMAP 收信代码。** 仓库中不存在 `imap_*` 调用、邮件收取模块或相关配置。因此「保留原本 IMAP 收信逻辑不改动」在当前代码库里没有可改动的对象；本次新增的 `api/mailer.php` 只做 SMTP 发信，不触碰既有的企业微信推送（`api/push.php`）与任何数据同步逻辑。

如果这两项其实指的是另一个仓库或尚未合入的分支，请把对应文件提供出来，我再按真实代码对齐。

## 1. 官方文档梳理（先确认参数，再写代码）

### 1.1 开启服务与授权码（文档 1087）

| 项 | 官方说明 |
| --- | --- |
| 默认状态 | QQ 邮箱**默认关闭** POP3/SMTP/IMAP 等第三方客户端服务 |
| 开启路径 | 网页版 → 设置 → 账号与安全 → 「POP3/IMAP/SMTP/Exchange/CardDAV服务」→ 开启 |
| 验证方式 | 按提示用绑定手机号发送指定短信内容 → 点「我已发送」 |
| 凭证 | 验证通过后弹出 **16 位授权码**，作为第三方客户端的专属密码 |
| 用户名 | 填**完整邮箱地址**，例如 `123456789@qq.com` |
| 密码栏 | 填 **16 位授权码**，**不是** QQ 邮箱网页登录密码 |
| 失效规则 | 修改 QQ 主密码后，**所有已生成授权码立即全部失效**；可在「设备管理 → 授权码管理」停用或重置 |

### 1.2 SMTP 参数（文档 1088）

| 项 | 值 |
| --- | --- |
| SMTP 服务器 | `smtp.qq.com` |
| SSL 端口 | `465`（隐式 SSL/TLS，连上即加密） |
| 备用端口 | `587`（实际协议是 STARTTLS：先明文连接再升级；官方表格统称 SSL/TLS） |
| 认证 | 用户名 = 完整邮箱；密码 = 16 位授权码 |
| 收信（本次不用） | IMAP `imap.qq.com:993` / POP3 `pop.qq.com:995`，均为 SSL/TLS |

官方另外建议：如果用 IMAP/POP3 收信，把收取范围限制为「最近 30 天」，降低授权码泄露后的损失。本次未实现收信，这条仅作记录。

### 1.3 报错规则（文档 1083 / 1071）

| 官方退信提示 | 含义 | 触发条件 |
| --- | --- | --- |
| `550 Invalid "From" found in header` | 邮件头 `From` 含 `@qq.com` / `@foxmail.com` / `@tencent.com` 等腾讯系域名，但**未通过 DKIM 签名验证** | 发信程序冒充腾讯系地址；QQ 的反钓鱼机制严禁未授权伪造，仅配 SPF 不够 |
| `550 Sender frequency limited` | 发件人账号触发**账号级**频率限制，被临时拒绝投递 | 分钟 / 小时 / 日三级阶梯封禁；数值保密；**换 IP、换域名都无效**，只针对该发件邮箱账号 |

注意口径：上面两条是 **QQ 邮箱作为收件方时给出的退信**，不是「用 QQ 的 SMTP 发信时服务器回的话」。本项目的处理方式是**提前拦住触发条件**：

- `550 Invalid "From"` → 后端强制 `发件人 === 登录账号`，表单里两个框填不一样直接拒绝保存，不会让这封信发出去。正常用自己 QQ 账号发信时，DKIM 由 QQ 服务器签，不会触发这条。
- `550 Sender frequency limited` → 代码里做了错误翻译与文案提示，并限制测试接口**只能发到当前登录邮箱**，避免被当成群发跳板。QQ 对自家 SMTP 的发信频率阈值官方未公开，因此只能靠「错开提醒时间、别短时间连发」来规避。

### 1.4 认证失败的常见原因（文档 1087 推导）

SMTP 会话里的 `535 Authentication failed` 不在上述两篇退信文档里，但按 1087 的授权码规则，实际原因基本是这三类：服务没开、填了 QQ 登录密码而不是授权码、改过主密码导致旧授权码失效。代码把这三条直接写进了 `535` 的中文提示。

## 2. 新增 / 修改的文件

| 文件 | 动作 | 作用 |
| --- | --- | --- |
| `api/secret_box.php` | **新增** | 授权码加密盒。AES-256-GCM，密钥来自 `config.php` 的 `mail_secret` 或 `app_settings` 自动生成 |
| `api/mailer.php` | **新增** | SMTP 客户端、错误码翻译、每用户配置读写、`lb_mail_send_to_user()` 通知入口 |
| `db/migrations/2026-11-19_smtp.sql` | **新增** | 建 `user_mail_config` 表 |
| `e2e/test-mailer.php` | **新增** | 44 项单测：主机校验、报错翻译、MIME 编码、加解密往返 |
| `api.php` | 修改 | 加载两个新文件；新增 `mail_status` / `mail_save` / `mail_test` / `mail_off` 四个接口 |
| `index.html` | 修改 | 配置页新增「邮件提醒」表单与四个动作 |
| `assets/app.css` | 修改 | `.mail-grid` / `.mail-result` 等样式 |
| `api/config.example.php` | 修改 | 增加 `mail_secret` 示例（默认留空，让程序自动生成） |
| `db/schema.sql` | 修改 | 全新安装也建 `user_mail_config` |
| `service-worker.js` | 修改 | 缓存版本推进到 `lifeboard-shell-v119` |

## 3. 数据库字段变更说明

新增一张表，**不改动** `users` / `boards` / `push_sent` 的任何列。旧数据完全不受影响。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `user_id` | `INT UNSIGNED` PK | 与 `users.id` 一对一，外键 `ON DELETE CASCADE` |
| `smtp_host` | `VARCHAR(190)` | 默认 `smtp.qq.com`，只接受公网域名 |
| `smtp_port` | `SMALLINT UNSIGNED` | 默认 `465`；白名单 25 / 465 / 587 / 2525 |
| `smtp_secure` | `ENUM('ssl','tls','none')` | 默认 `ssl`；`tls` = STARTTLS |
| `smtp_user` | `VARCHAR(190)` | 登录用户名 = 完整邮箱地址 |
| `from_email` | `VARCHAR(190)` | 发件人，后端强制等于 `smtp_user` |
| `from_name` | `VARCHAR(80)` | 称呼，用于 From 显示名，UTF-8 走 RFC 2047 编码 |
| `secret_enc` | `TEXT NULL` | **授权码密文**，AES-256-GCM，base64 封装；任何接口都不回显 |
| `enabled` | `TINYINT(1)` | 是否允许 `lb_mail_send_to_user()` 发信 |
| `last_error` | `VARCHAR(500)` | 最近一次测试失败原因（不含授权码） |
| `last_test_at` | `DATETIME NULL` | 最近一次测试时间 |
| `created_at` / `updated_at` | `DATETIME` | 标准时间戳 |

另外 `app_settings` 会多出一行 key = `mail_secret_key`（仅当 `config.php` 没配 `mail_secret` 时自动生成），存 64 位十六进制的加密主密钥。这是**数据行不是表结构变更**，不需要你手工插入。

## 4. 部署配置步骤

1. **先跑 SQL**（顺序不能反）：宝塔 → 数据库 → phpMyAdmin → 选中站点数据库 → SQL → 粘贴 `db/migrations/2026-11-19_smtp.sql` → 执行。
   命令行等价：`mysql -u 用户 -p 数据库名 < db/migrations/2026-11-19_smtp.sql`。
2. **配置加密密钥**（推荐但非必须）：在 `api/config.php` 的返回数组里加一项：
   ```php
   'mail_secret' => '这里填 64 位十六进制随机串',
   ```
   生成命令：`php -r "echo bin2hex(random_bytes(32));"`。
   留空也能跑：程序会在 `app_settings` 自动生成一把并长期保存。
   **警告**：不要把示例里的占位字符串原样填进去——公开可推算的密钥等于没加密。换密钥会让所有用户已存的授权码解不开，需要重新填一次。
3. **确认 PHP 扩展**：`openssl` 必须开启（`php -m | grep openssl`）。不需要 composer，不需要安装 PHPMailer。
4. **传代码**：覆盖 `index.html`、`api.php`、`api/secret_box.php`、`api/mailer.php`、`api/config.example.php`、`assets/app.css`、`service-worker.js`、`db/schema.sql`。**不要覆盖** `api/config.php` 和 `install.lock`。
5. **QQ 邮箱侧准备**：网页版 → 设置 → 账号与安全 → 开启 SMTP 服务 → 短信验证 → 复制 16 位授权码。
6. **页面配置**：登录 → 配置 → 「邮件提醒」。服务器 `smtp.qq.com`、端口 `465`、协议 `SSL/TLS`、用户名与发件人填**同一个完整邮箱**、称呼随意、密码栏填 16 位授权码 → 点「发信测试」→ 收到测试信后再点「保存」。
7. **验证版本**：线上比对 md5，并确认 SW 的 `CACHE` 已是 `lifeboard-shell-v119`：
   ```bash
   curl -sS "https://你的域名/index.html?_$(date +%s)" | md5sum
   curl -sS "https://你的域名/service-worker.js?_$(date +%s)" | grep CACHE
   ```

## 5. 常见报错坑点（按出现频率排序）

| 现象 | 真实原因 | 处理 |
| --- | --- | --- |
| `535 Authentication failed` | 填了 QQ 登录密码，或 SMTP 服务没开，或改过主密码导致授权码失效 | 填 16 位授权码；到「设置 → 账号与安全」重新开启并生成新授权码 |
| `550 Invalid "From" found in header` | 发件人不是登录账号，冒充了别的腾讯系地址且没有 DKIM 签名 | 发件人与用户名必须是同一个邮箱；本项目在保存时就会拦住 |
| `550 Sender frequency limited` | 发件账号被账号级限流（分钟 / 小时 / 日三级） | 暂停发信、错开提醒时间；换 IP / 域名无效；清理无效收件人 |
| 连不上 465 | 服务器出站防火墙拦截，或端口与协议不匹配 | 确认 465 配 SSL/TLS、587 配 STARTTLS；检查主机商是否封 465 |
| `TLS 升级失败` | 服务器 PHP 缺 CA 根证书包 | 检查 `php.ini` 的 `openssl.cafile` / `curl.cainfo` |
| 授权码保存后再次打开变空 | **设计如此**：后端不回显任何片段，密码框永远留空 | 留空 = 保留已存授权码；只有要换码时才填新的 |
| 换密钥后所有发信都认证失败 | `mail_secret` 变了，旧密文解不开 | 去配置页重新填一次授权码 |
| 测试邮件没收到 | 被判垃圾邮件 / 收件地址不是账号邮箱 | 看垃圾箱；测试接口固定发到当前登录邮箱，不能改收件人 |

## 6. 接口与调用方式

四个接口都要求登录；写操作额外要求 CSRF token（`X-CSRF-Token`）。

| action | 方法 | 说明 |
| --- | --- | --- |
| `mail_status` | GET | 返回脱敏配置（无授权码）、`crypto_ready`、测试收件人 |
| `mail_save` | POST | 保存配置。`secret` 留空 = 保留原授权码 |
| `mail_test` | POST | 可带表单当前值试发（不落库）；不带则用已保存配置。收件人固定为登录邮箱 |
| `mail_off` | POST | 只关 `enabled`，保留配置 |

业务代码发通知（真正给提醒用的入口）：

```php
$why = '';
$ok = lb_mail_send_to_user(lb_db(), $uid, '该吃药了', '阿莫西林，1 片', $why);
if (!$ok) {
    // $why 是人话，可直接写日志；里面绝不会包含授权码
}
```

`lb_mail_send_to_user()` 不会替你判断「该不该发」，也不会写 `push_sent`。去重、定时、判断逻辑仍归调用方——这与 `api/push.php` 的分层约定一致。

## 7. 安全设计

- 授权码用 **AES-256-GCM** 加密存储，带完整性校验；密文被改动会解密失败，不会吐出错码。
- 接口**只回 `hasSecret` 布尔**，不回显授权码的任何片段。
- 主机只接受公网域名，拒绝 IP / `localhost` / `.local` 等，防止配置接口变成内网探测口子。
- 测试接口收件人**硬编码为当前登录邮箱**，不能指定任意地址，避免被用作中继。
- 主题、称呼里的换行会被剥掉，防邮件头注入。
- 「不加密（none）」只是给本地调试留的口子，界面明确标了「不推荐」；QQ 生产环境应使用 465 + SSL/TLS。

## 8. 验证与回滚

```bash
# 前端脚本语法 + 动作注册
node _check_script.mjs
# 邮件层单测（44 项）
php -d extension_dir=<php>/ext -d extension=openssl e2e/test-mailer.php
# 既有回归（分开跑，串一起会超时）
php e2e/test-push.php
python e2e/verify-ics-subscribe.py
```

回滚：恢复 `index.html` / `api.php` / `service-worker.js` 等文件后，`DROP TABLE user_mail_config;`（或保留表，只是不再使用；表本身不会写任何数据）。

## 9. 参考链接

- [开启 POP3/SMTP/IMAP 服务并获取授权码](https://help.mail.qq.com/detail/0/1087)
- [QQ 邮箱客户端安全登录指南（含服务器参数）](https://help.mail.qq.com/detail/0/1088)
- [退信提示：550 Invalid "From" found in header](https://help.mail.qq.com/detail/0/1083)
- [退信提示：550 Sender frequency limited](https://help.mail.qq.com/detail/0/1071)
