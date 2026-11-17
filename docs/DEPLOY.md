# 部署到阿里云轻量服务器（宝塔 + PHP + MySQL）

最后更新：v110（2026-11-17）

把项目上传到宝塔站点，访问域名后按向导安装：填数据库、创建管理员、生成邀请码。之后用户凭邀请码注册，管理员只管理账号和密码，不能查看或导出其他用户的数据。

> 示例路径：站点根目录 `/www/wwwroot/todo`，PHP 8.2，数据库名 `lifeboard`。

## 0. 最终结构

```
/www/wwwroot/todo/
├── index.html              # 前端（介绍页 + 看板）
├── api.php                 # 云同步 / 账号接口
├── api/
│   ├── bootstrap.php
│   ├── backup.php          # 每日快照（写入 ../backups/）
│   ├── ics.php             # 日历订阅的 iCalendar 生成
│   ├── schedule.php        # 「某一天几点该提醒什么」（推送用）
│   ├── push.php            # 企业微信机器人发送 + 一轮推送的调度
│   └── config.php          # 安装向导生成（不要公开）
├── install/
│   └── index.php           # 安装向导（装完删除）
├── db/
│   ├── schema.sql          # 安装器读取，用于建表
│   └── migrations/         # 已有站点的增量迁移 SQL
├── tools/
│   ├── create_user.php     # 命令行救援账号（可选）
│   ├── restore_backup.php  # 从每日快照恢复看板
│   ├── push_tick.php       # 定时任务：每分钟把该提醒的推到手机
│   └── push_test.php       # 命令行发一条测试消息
├── backups/                # 每日快照，自动生成；含隐私，勿公开勿入库
├── manifest.json           # PWA 清单
├── service-worker.js       # PWA 外壳缓存
├── icons/                  # 192 / 512 / maskable 图标
├── install.lock            # 安装完成后生成
└── DEPLOY.md
```

> `db/` 只在安装时用得到。装完可以把整个目录删掉，省得被人下载到表结构。

数据流：

```
浏览器
  │ HTTPS
  ▼
Nginx + PHP-FPM
  ├─ /                介绍页；未安装时跳 /install/；登录后进入看板
  ├─ /install/        安装向导（装完锁定/删除）
  └─ /api.php         登录、注册、读写、管理员接口
        │
        ▼
     MySQL（users / boards / app_settings / 登录限流）
```

## 1. 宝塔准备

1. 软件商店安装 **PHP 8.2**（8.1 / 8.3 也可以）和 **MySQL 8.0**（5.7 也可以）。
2. 网站 → 添加站点：
   - 域名：`todo.example.com`
   - 根目录：`/www/wwwroot/todo`
   - PHP 版本：8.2
3. 确认 PHP 已装 `pdo_mysql`：

```bash
/www/server/php/82/bin/php -m | grep -i pdo_mysql
```

没有输出就在宝塔 PHP 设置里安装扩展并重启 PHP。

## 2. 上传并解压

把 [todo-deploy.zip](todo-deploy.zip) 上传到站点根目录并解压，确保 **`index.html`、`api.php`、`install/` 直接位于 `/www/wwwroot/todo`**，而不是多套一层 `todo-deploy/`。

设置权限：

```bash
cd /www/wwwroot/todo
chown -R www:www .
find . -type d -exec chmod 755 {} \;
find . -type f -exec chmod 644 {} \;
```

安装阶段 PHP 需要能写 `api/config.php` 和 `install.lock`，所以 `api/` 和站点根目录要对 `www` 可写（上面的 `chown` 已满足）。安装完成后 `api/config.php` 会被写成 640。

## 3. 建一个空数据库

宝塔 → 数据库 → 添加数据库：

- 数据库名：`lifeboard`
- 用户名：`lifeboard`
- 密码：强密码，保存好
- 字符集：`utf8mb4`

**不要手动导入 `db/schema.sql`**，安装向导会自动建表。数据库必须是空的；如果里面有表，安装器会拒绝，避免误覆盖。

> 安装器只建表，不创建数据库。宝塔创建的数据库用户通常没有 `CREATE DATABASE` 权限，这样最安全。

## 4. 访问域名安装

浏览器打开：

```
https://todo.example.com/
```

如果还没安装，页面会检测到 `install.lock` 不存在，自动跳到：

```
https://todo.example.com/install/
```

没有自动跳转就直接访问 `/install/`。

### 4.1 环境检查

向导会检查 PHP 版本、`pdo_mysql`、Session、JSON，以及 `api/`、站点根目录、`db/schema.sql` 的读写权限。全绿后点「下一步：连接数据库」。

如果提示 `api/config.php 已有真实数据库配置`，说明之前装过或文件不是模板；要重装请先删除 `api/config.php` 并清空数据库。

### 4.2 填数据库

填写第 3 步创建的：

- 地址：`127.0.0.1`（如果连不上可改 `localhost`）
- 端口：`3306`
- 数据库名：`lifeboard`
- 用户名：`lifeboard`
- 密码：数据库密码

点「测试连接并建表」。安装器会：

1. 测试 PDO 连接；
2. 确认数据库是空的；
3. 执行 `db/schema.sql` 创建 `users`、`boards`、`app_settings`、`login_attempts`、`register_attempts`。

如果提示「数据库里已经有表」，先在宝塔里换一个空库，或删除旧表后重试。

### 4.3 创建管理员

填写：

- 管理员邮箱（登录名，不会发邮件）
- 显示名称
- 密码（至少 8 位）+ 确认

点「完成安装」。安装器会：

- 写入 `api/config.php`（数据库账号 + 随机 app_key）；
- 创建第一个管理员（`is_admin=1`）；
- 生成 **邀请码**，打开「注册」开关；
- 写入 `install.lock`，锁定安装向导。

### 4.4 记下邀请码

完成页会显示管理员邮箱和邀请码，例如：

```
管理员邮箱：you@example.com
邀请码：A1B2C3D4
```

把邀请码发给需要注册的人。然后：

```bash
cd /www/wwwroot/todo
rm -rf install
```

**务必删除 `install/`**。即使不删，`install.lock` 也会让向导返回 403，但删掉更干净。

## 5. 登录、注册和管理员

### 5.1 登录

打开域名，首页是功能介绍页；点「登录」，输入管理员邮箱和密码。管理员登录后，左侧会进入看板，设置 → 云同步里会多一个「用户管理」按钮。

### 5.2 注册（邀请码）

- 首页 →「注册（需要邀请码）」；
- 或登录弹窗 →「用邀请码注册」。
- 填写显示名称（可选）、邮箱、密码、邀请码。
- 密码至少 **8 位**。
- 注册成功后自动登录，并从云端加载初始数据（新用户会得到一份示例习惯/任务，可自行修改）。
- 注册限流：同一 IP 每小时最多 10 次注册尝试。

管理员可以在「用户管理」里关闭注册。关闭后，首页和登录弹窗不再显示注册入口，接口也会拒绝注册。

### 5.3 管理员面板

设置 → 云同步 →「用户管理」：

- 查看用户列表：邮箱、显示名称、角色、状态、注册时间、最后登录。
- **重置密码**：给指定用户设置新密码；对方所有已登录设备会立即退出。
- **停用 / 启用账号**：停用后无法登录，已登录会话失效；不能停用自己。
- **注册设置**：开放/关闭注册、修改邀请码、修改站点名称。

权限边界：

- 管理员接口只返回 `id / email / display_name / is_admin / status / created_at / last_login_at`。
- 没有任何管理员读取 `boards` 的接口；管理员不能查看或导出别人的习惯、任务、用药数据。
- 但管理员可以重置密码，理论上可以设置新密码后以该用户身份登录。这是“管理员可重置密码”的固有边界；如果要求绝对隔离，需要取消管理员重置密码，或改为用户自己持有密钥的端到端加密。

### 5.4 忘记密码

登录弹窗右下角有「找回密码」；点击后提示：

```
找回密码：sl@example.com
```

用户用注册邮箱联系这个地址；管理员在「用户管理」里为他重置密码（至少 8 位）。重置后该用户所有已登录设备都会退出。

## 6. Nginx 与 PHP 配置

### 6.1 Nginx

网站 → 设置 → 配置文件，在 `server { ... }` 中加：

```nginx
client_max_body_size 8m;

# 这些目录只给 PHP include / 安装器读取，禁止浏览器直接访问
location ^~ /api/ {
    deny all;
}
location ^~ /db/ {
    deny all;
}
location ^~ /tools/ {
    deny all;
}

# PWA 清单和 Service Worker
location = /manifest.json {
    types { application/manifest+json json; }
    default_type application/manifest+json;
}
location = /service-worker.js {
    add_header Cache-Control "no-cache, no-store, must-revalidate";
}
```

不要拦 `/api.php`（它在站点根目录）。`install/` 在安装阶段必须可访问，装完删除即可；`install.lock` 存在时向导自己会返回 403。

验证：

- `https://todo.example.com/api/config.php` → 403
- `https://todo.example.com/db/schema.sql` → 403
- `https://todo.example.com/api.php?action=status` → `{"ok":true,"installed":true}`

### 6.2 PHP

宝塔 → 软件商店 → PHP 8.2 → 设置 → 配置修改：

```ini
post_max_size = 8M
upload_max_filesize = 8M
max_execution_time = 60
max_input_time = 60
display_errors = Off
log_errors = On
session.cookie_httponly = 1
session.cookie_samesite = Lax
```

保存后重启 PHP-FPM。`post_max_size` 要大于单次保存的数据量（接口默认上限 4MB）。

## 7. HTTPS

网站 → 设置 → SSL → Let's Encrypt → 申请（域名解析到这台服务器）→ 开启「强制 HTTPS」。

没有证书前先用 HTTP 跑通也可以，但登录密码会明文传输，页面的云同步面板会显示红色提醒。

### 7.1 安装到桌面（PWA）

项目自带：

- `manifest.json`：应用名称、图标、`start_url`、`display: standalone`；
- `service-worker.js`：缓存页面外壳、manifest 和图标，**不缓存 `api.php`**；
- `icons/icon-192.png`、`icon-512.png`、`icon-maskable-512.png`。

要求：

1. HTTPS（PWA 安装必须）；
2. `/manifest.json` 和 `/service-worker.js` 能正常访问（上面的 Nginx 配置已处理 MIME 和缓存）；
3. 浏览器打开一次首页，Service Worker 注册成功后，Chrome/Edge 地址栏会出现安装图标；手机 Safari 用「分享 → 添加到主屏幕」。

限制：PWA 只缓存页面外壳。登录、注册和读写数据仍要联网访问 `api.php`；离线打开会看到介绍页/连接失败提示，不会把账号数据缓存到本地。

更新前端后，如果希望强制刷新外壳缓存，把 `service-worker.js` 里的 `CACHE` 版本号改一下（如 `lifeboard-shell-v2`）。

## 8. 备份

备份分两层，互相独立，任何一层都能单独把数据救回来。

### 8.1 应用自带的每日快照（已内置，不用配）

`api/backup.php` 会在**任意一次 API 请求**时顺手检查：今天备过没有，没有就往站点根目录的 `backups/` 写一份。

- 文件名形如 `2026-10-29.php`，保留 30 天，过期的自动删掉
- 一天最多写一份；当天已有且不到 30 分钟会跳过，不会每次保存都落盘
- 内容是**所有用户的看板数据**，不含账号和密码哈希
- **不依赖 cron**，不用在宝塔里配计划任务

备份文件故意写成 `.php`，第一行是 `<?php exit; ?>`：即使 `backups/` 被公网访问到，PHP 也只会执行 exit，不会把数据吐出去。取回时删掉第一行，剩下的就是纯 JSON。

**部署后确认一次**：打开站点随便点几下，然后到宝塔文件管理器看 `/www/wwwroot/todo/backups/` 有没有今天的文件。没有的话通常是目录不可写：

```bash
cd /www/wwwroot/todo
mkdir -p backups && chown -R www:www backups && chmod 750 backups
```

**恢复**（只覆盖该用户的看板，不动账号和登录态）：

```bash
cd /www/wwwroot/todo
php tools/restore_backup.php backups/2026-10-29.php          # 预演，只列不写
php tools/restore_backup.php backups/2026-10-29.php --yes    # 确认后真写
```

恢复会把该用户的 `rev` 加 1，已经打开的页面刷新后拿到的就是恢复后的数据。

### 8.1b 日历订阅（可选，手机上到点响的最省事办法）

设置 → 提醒 → 日历订阅，点「生成订阅链接」，把地址粘进手机日历：

- iPhone：设置 → 日历 → 账户 → 添加账户 → 其他 → 添加已订阅的日历
- 小米 / Redmi（MIUI、HyperOS）：日历 → 右上角设置 → 日程导入 → URL 导入
- 华为 / 荣耀：日历 → 订阅管理 → 添加订阅
- 原生安卓 / Google 日历：添加其他日历 → 通过网址添加

各家自带日历对 ICS 源的挑剔程度差别很大，下面几条是按「小米日历打不开」的反馈补的，
改动都在服务端，不用配置：

- 响应带 `Content-Length`（避免 chunked，部分国产 ROM 不认分块响应）
- 允许 `HEAD` 请求（客户端添加订阅前常先发一个 HEAD 探测，只让 GET 会被判成地址无效）
- `Content-Disposition` 里不带反斜杠转义（严格的解析器会判格式错误）
- 不输出 `METHOD:PUBLISH`（METHOD 是会议邀请用的，订阅源带上会被当成一次性邀请）
- 声明 `REFRESH-INTERVAL` 与 `X-PUBLISHED-TTL`，告诉客户端多久来拉一次
- 订阅地址改成单参数 `?ics=<token>`，避免某些客户端把 `&` 当截断点

如果某台机器还是不行，可以再给一个以 `.ics` 结尾的地址（有客户端按后缀判断格式）。
在宝塔「网站 → 设置 → 配置文件」里，`server { }` 内、`location ~ \.php` 之前加：

```nginx
location ~ ^/ics/([a-f0-9]{64})\.ics$ {
    rewrite ^/ics/([a-f0-9]{64})\.ics$ /api.php?ics=$1 last;
}
```

然后把订阅地址里的 `/api.php?ics=` 换成 `/ics/`、末尾补 `.ics`。

之后用药时段、重复任务、带建议时间的习惯都由系统日历负责提醒，
计划改了系统自己来拉，不用再重新导出。刷新频率由系统决定（一般几小时一次），
但事件时间本身是准的，只有「临时新加的日程」可能赶不上。

地址里那串 token 等于你日程的钥匙，别发给别人；泄露了点「重新生成」，旧地址立刻失效。
这个功能需要先执行 `db/migrations/2026-10-29_ics_token.sql`（给 users 表加一列）。

### 8.1c 手机推送（企业微信群机器人）

日历订阅靠手机自己算，好处是零维护；缺点是改计划后要等系统来拉，而且部分国产日历
（小米、华为）解析不了订阅源。想要「服务器在那一分钟主动发到手机」，就用这条路。

为什么是微信而不是别的：国行安卓没有 Google 服务框架，也就没有 FCM 这条系统级推送通道。
Bark 只有 iOS 客户端；ntfy 这类要 App 自己开长连接保活，会被 MIUI / HyperOS 杀掉。
微信和企业微信在厂商白名单里，是国行安卓上唯一稳定的送达通道。

**配置步骤**

1. 执行 `db/migrations/2026-10-29_push.sql`（给 users 加两列 + 建 push_sent 表）
2. 传代码
3. 进 **配置** → 手机推送，粘贴 webhook，点「保存」
   （地址存在服务器，换设备会保留；要改点「修改链接」，清空才会停用）

webhook 在哪拿：企业微信 → 建一个**只有自己的内部群**（外部群加不了机器人）→
群设置 → 群机器人 → 添加 → 复制地址。个人注册免费，不需要营业执照。

**必须配的计划任务**

宝塔 → 计划任务 → 添加：

- 任务类型：Shell 脚本
- 任务名称：晚风推送
- 执行周期：**N 分钟 → 1 分钟**（不能更稀，代码只往前宽容 3 分钟）
- 脚本内容：

```bash
cd /www/wwwroot/todo && /www/server/php/81/bin/php tools/push_tick.php
```

PHP 路径按实际版本改（`ls /www/server/php/` 能看到）。

**怎么确认它在工作**

```bash
# 预演：只打印这一分钟要发什么，不写库也不真发
cd /www/wwwroot/todo && php tools/push_tick.php --dry

# 假装现在是 08:00，排查「为什么这条没发」
php tools/push_tick.php --dry --at 08:00
```

**几个要知道的行为**

- 每一条只发一次。靠 `push_sent` 的唯一索引去重，定时任务重叠执行也不会重复发
- 发失败会把占位删掉，下一分钟自动重试
- 只往前宽容 3 分钟。服务器重启后不会补发几小时前的提醒——那没有意义
- 只有「今天到期」的待办会按点提醒；逾期的走页内提醒，不在这里反复响
- 备用药（按需服用）、可选项习惯、已经打过卡的，都不会推
- 企业微信限每个机器人每分钟 20 条，超出直接丢弃。正常使用远远够

**时区**

代码里固定按 `Asia/Shanghai` 计算，不依赖 php.ini。但 `push_sent.sent_at` 和清理逻辑
用的是同一个时间源，所以服务器时区即使是 UTC 也不会错位。真要保险，可以在宝塔里
把 PHP 时区设成 Asia/Shanghai。

### 8.2 数据库级备份（建议配上）

应用快照挡得住误删和程序故障，挡不住整台服务器出事，所以再加一层数据库 dump：

```bash
mkdir -p /www/backup
mysqldump --single-transaction --default-character-set=utf8mb4 \
  -u lifeboard -p lifeboard | gzip > /www/backup/lifeboard-$(date +%F).sql.gz
```

恢复：

```bash
gunzip < /www/backup/lifeboard-2026-10-22.sql.gz | mysql -u lifeboard -p lifeboard
```

另外：

- 宝塔 → 数据库 → 备份 → 设置计划任务，每天一次，保留 7–14 天。
- 阿里云控制台给轻量服务器做定期快照。
- 应用内「设置 → 数据管理 → 导出备份 JSON」保留，适合导一份到自己电脑长期存。

**别把 `backups/` 提交进 git**（`.gitignore` 已排除）：里面是整站隐私数据，只留在服务器和本机。

## 9. 安全清单

- 宝塔面板：改默认端口、强密码、面板 SSL、限制访问 IP；不要公开 8888。
- 阿里云防火墙 / 宝塔防火墙：只放行 80、443、SSH；不要放行 3306。
- 数据库用户只授权 `lifeboard` 库，不用 root 跑应用。
- `api/config.php` 权限 640，不要提交到公开仓库。
- 全站 HTTPS；登录 Cookie 使用 HttpOnly、SameSite=Lax，HTTPS 下加 Secure。
- 安装完成后删除 `install/`，保留 `install.lock`。
- 注册默认需要邀请码；不需要开放时在管理员面板关闭。
- 管理员的密码重置会强制目标用户退出；建议只在用户求助时使用。
- 保持 PHP / MySQL / 宝塔更新；改完 PHP 先 `php -l`。
- 备份文件含所有用户的用药数据，权限设为 600/640，不要放网站根目录。

## 10. 更新代码

> 如果这次更新包含 `db/migrations/` 里的新文件，先执行 SQL 再传代码。
> 顺序反了不会崩（对应接口会报 500），功能用不了。
>
> - v36 日历订阅：`ALTER TABLE users ADD COLUMN ics_token ...`
> - v39 手机推送：`ALTER TABLE users ADD COLUMN push_webhook / push_enabled`
>   ＋ 建 `push_sent` 表，见 `db/migrations/2026-10-29_push.sql`
> - v45 推送中心：`ALTER TABLE push_sent ADD COLUMN content TEXT`
>   （给发送记录留正文，见 `db/migrations/2026-10-30_push_content.sql`）。
>   不跑也不会崩——代码会检测列是否存在，没有就退回不写正文的旧写法，
>   只是「推送中心」的发送记录看不到具体内容。
>
> 推送还需要在宝塔里加一个**每分钟**的计划任务，见 8.1c。

1. 备份数据库。
2. 覆盖 `index.html`、`api.php`、`api/bootstrap.php`、`install/`、`db/schema.sql`、`db/migrations/`（保留 `api/config.php` 和 `install.lock`）。
3. 如果数据库还没有 `board_revisions`，执行一次：
   - 宝塔 → 数据库 → phpMyAdmin → 选中站点数据库 → SQL，粘贴 `db/migrations/2026-10-23_board_revisions.sql`；
   - 或命令行：`mysql -u 用户名 -p 数据库名 < db/migrations/2026-10-23_board_revisions.sql`。
4. `php -l` 检查，重载 PHP/Nginx。
5. 浏览器 `Ctrl+F5` 强制刷新。

历史版本表只新增表，不会修改 `boards` / `users` / `app_settings` 的现有数据。没有执行迁移时，正常保存仍可用，但「历史版本」页面会提示不可用。

更新时**不要覆盖** `api/config.php`（数据库密码）和 `install.lock`，否则会重新进入安装状态或连不上数据库。

## 11. 排错

| 现象 | 排查 |
|---|---|
| `Fatal error: strict_types declaration must be the very first statement` | PHP 文件开头有 UTF-8 BOM 或空白。用最新部署包覆盖 `api.php`、`install/index.php`、`tools/create_user.php`；不要用记事本「UTF-8 带 BOM」另存 |
| 访问域名显示旧静态页、不进安装 | 先 Ctrl+F5 清缓存；确认 `index.html` 里有 `api.php?action=status`；直接访问 `/api.php?action=status` 看是否返回 JSON |
| 登录后还是看到看板、看不到介绍页 | 已登录时直接进看板是正常的；要回到介绍页点「退出登录」。如果未登录也直接进看板，说明 `index.html` 还是旧版，重新上传 |
| PWA 无法安装 | 必须 HTTPS；确认 `/manifest.json`、`/service-worker.js` 返回 200；Nginx 给 manifest 配 `application/manifest+json`；手机用浏览器菜单「添加到主屏幕」 |
| 主题没有按时间切换 | 设置 → 主题 → 选「自动」；规则是 7:00–19:00 浅色，其余深色；页面每分钟检查一次 |
| 点「找回密码」没反应 | 登录弹窗右下角；点击后应显示 `找回密码：sl@example.com`；旧缓存会缺这个按钮，Ctrl+F5 |
| 访问域名没跳安装 | `api.php?action=status` 是否返回 `installed:false`；`install/` 是否上传；浏览器控制台是否有 JS 错误 |
| 安装页 403 | `install.lock` 已存在；要重装先删 `install.lock` + `api/config.php` + 清空数据库 |
| 安装页空白 / 500 | 看宝塔网站错误日志；PHP 版本、`pdo_mysql`、文件权限 |
| 提示数据库不是空库 | 换一个空数据库；或删除旧表后重试 |
| 提示 api/ 不可写 | `chown -R www:www /www/wwwroot/todo`，确认 `api/` 755、PHP 以 www 运行 |
| 数据库连接失败 | 地址/端口/库名/用户/密码；`127.0.0.1` 不行改 `localhost`；MySQL 是否启动 |
| 安装完成但登录 500 | `api/config.php` 是否存在且账号正确；看 PHP 错误日志 |
| 登录提示「会话校验失败」 | Cookie 被拦、域名/协议不一致、`session.save_path` 不可写；清 Cookie 再试 |
| 登录一直「邮箱或密码不正确」 | 邮箱/密码错误；管理员可重置；看是否被限流 |
| 注册提示邀请码错误 | 管理员面板复制最新邀请码；注意大小写（接口会自动转大写） |
| 注册提示频繁 | 同 IP 每小时最多 10 次；等一会儿或换网络 |
| 保存 409 / 冲突弹窗 | 当前版本采用最后写入覆盖，正常不会再出现；若旧缓存页面还在，Ctrl+F5 更新 |
| 保存 413 | 调大 Nginx `client_max_body_size` 和 PHP `post_max_size` |
| 管理员看不到用户管理 | 当前账号 `is_admin` 不是 1；用安装器创建的管理员登录，或 CLI `--admin` |
| 停用后还能登录 | 检查 users.status；接口登录会拒绝 disabled；清 Cookie 再试 |
| 云端数据损坏 | 从数据库备份恢复；导入 JSON 功能已取消 |

日志：

- 宝塔网站日志：`/www/wwwlogs/你的域名.log`、`.error.log`
- PHP 错误日志：宝塔 PHP 设置里的 `error_log`
- 接口异常：PHP `error_log`，前缀 `lifeboard api:`

## 12. 救援：命令行创建/重置账号

安装器之外保留了一个 CLI 脚本，适合忘记管理员密码或需要手动建号：

```bash
cd /www/wwwroot/todo
/www/server/php/82/bin/php tools/create_user.php --admin you@example.com '至少8位的密码'
```

- `--admin`：创建管理员；不加则创建普通用户。
- `--update`：重置已有账号密码（会使该账号已登录设备退出）。
- 示例：`--update --admin you@example.com '新密码'`（重置并确保是管理员）。

## 13. 接口与表结构

接口都在 `api.php`，同域访问，不需要 CORS。

| action | 方法 | 登录 | 管理员 | CSRF | 说明 |
|---|---|---|---|---|---|
| `status` | GET | 否 | 否 | 否 | 是否已安装，不连数据库 |
| `me` | GET | 否 | 否 | 否 | 当前用户、CSRF、注册开关 |
| `login` | POST | 否 | 否 | 是 | 登录 |
| `register` | POST | 否 | 否 | 是 | 邀请码注册，自动登录 |
| `logout` | POST | 是 | 否 | 是 | 退出 |
| `load` | GET | 是 | 否 | 否 | 读取自己的 boards |
| `history` | GET | 是 | 否 | 否 | 自己的历史版本列表；带 `id` 时返回该版本数据 |
| `restore` | POST | 是 | 否 | 是 | 恢复自己的历史版本（恢复前自动存快照） |
| `save` | POST | 是 | 否 | 是 | 保存自己的 boards（带 base_rev） |
| `force` | POST | 是 | 否 | 是 | 用自己的数据覆盖云端 |
| `change_password` | POST | 是 | 否 | 是 | 修改自己的密码 |
| `admin_users` | GET | 是 | 是 | 否 | 用户列表（不含数据） |
| `admin_user_update` | POST | 是 | 是 | 是 | 重置密码 / 停用启用 |
| `admin_settings` | GET | 是 | 是 | 否 | 注册开关、邀请码、站点名 |
| `admin_settings_save` | POST | 是 | 是 | 是 | 保存注册设置 |

表：

- `users`：`id`、`email`、`password_hash`、`display_name`、`is_admin`、`status`、`session_epoch`、`created_at`、`last_login_at`
- `boards`：`user_id`（主键）、`data`（整份 JSON）、`rev`、`updated_at`（毫秒）
- `board_revisions`：`id`、`user_id`、`rev`、`data`、`reason`、`created_at`；每个用户保留最近 20 版 / 30 天，仅本人可读
- `app_settings`：`k` / `v`（`registration_open`、`invite_code`、`site_name`）
- `login_attempts`：登录失败限流
- `register_attempts`：注册限流

管理员接口只查询 `users` 的账号字段，不读取 `boards` 或 `board_revisions`。

---

## 回滚（每次部署前必做）

线上只有两个文件会随版本变化：`index.html` 和 `service-worker.js`。
`api.php`、`api/config.php`、`db/`、`install/` 不参与日常发布，改它们属于另一类变更。

### 1. 部署前：在服务器留一份现场

在站点根目录（如 `/www/wwwroot/todo`）下建带时间戳的备份目录：

```bash
cd /www/wwwroot/todo
STAMP=$(date +%Y%m%d-%H%M%S)
mkdir -p .bak/$STAMP
cp -p index.html service-worker.js .bak/$STAMP/
```

### 2. 上传新文件

只覆盖这两个文件，其余不动。

### 3. 部署后：核对线上与本地是否一致

```bash
# 本地
sha256sum index.html service-worker.js
# 线上
curl -s https://your-domain.example/index.html | sha256sum
curl -s https://your-domain.example/service-worker.js | sha256sum
```

两边哈希一致 = 文件已生效。`service-worker.js` 里的 `CACHE` 常量必须比上一版大，
否则老客户端不会拉新资源。

### 4. 出问题：回滚

```bash
cd /www/wwwroot/todo
cp -p .bak/20261026-014000/index.html .bak/20261026-014000/service-worker.js ./
```

回滚后 `CACHE` 常量会退回旧值，**必须再手动 +1**，否则已经缓存新版的客户端不会回退：

```bash
sed -i "s/lifeboard-shell-v[0-9]*/lifeboard-shell-v103/" service-worker.js
```

（`v103` 只要是没出现过的更大值即可。数字只能往前走，往回退会导致缓存卡住。）

### 5. 用 git 找回任意历史版本

```bash
git tag                    # 看所有发布锚点，如 v28-baseline
git show v28-baseline:index.html > /tmp/index.html
```

发布锚点约定：每个上线版本打一个 `vNN-baseline` 标签，指向与线上完全一致的那次提交。
