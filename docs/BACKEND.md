# 后端结构 · api.php 与 api/

> 裸 PHP 8.2，无框架、无 Composer、无自动加载。所有文件靠显式 `require` 串起来。
>
> 配套阅读：`ARCHITECTURE.md`（整体）、`DATA-MODEL.md`（字段含义）。

最后更新：v78（2026-11-10）

---

## 1. 入口与引导顺序

`api.php` 是唯一入口，824 行，顺序很关键：

```php
1.  define('LIFEBOARD_API', true)          ← api/ 下所有文件都检查这个常量
2.  取 $action = $_GET['action']
3.  兼容 ?ics=<token>     → 等价于 action=ics
4.  action=status          → 直接返回 {installed:bool}，不加载任何模块
5.  没有 install.lock      → 503 not_installed
6.  require api/bootstrap.php
7.  require api/backup.php
8.  require api/ics.php
9.  require_once api/push.php              ← 它内部 require_once schedule.php
10. action !== 'ics' 才 lb_session_start() ← 日历订阅不开会话，省 IO
11. 三行安全头
12. lb_daily_backup()                       ← 每天一份快照，内部 try/catch
13. switch ($action) → 23 个 case
```

### 1.1 `LIFEBOARD_API` 保护

`api/bootstrap.php`、`api/ics.php` 等文件开头有：

```php
if (!defined('LIFEBOARD_API')) { http_response_code(404); exit; }
```

**作用**：即使 Nginx 配错、让 `api/` 目录可被公网直接访问，也不会执行任何逻辑。

**副作用（写测试时必须知道）**：CLI 里 `require` 这些文件前必须先
`define('LIFEBOARD_API', 1)`，否则脚本静默退出、一行输出都没有——看起来像"测试没跑"。

### 1.2 `require` vs `require_once`

**`api/` 下的文件一律 `require_once`。**

踩过的坑：`schedule.php` 被 `api.php` 和 `push.php` 各 `require` 一次，
产生 `Cannot redeclare lb_schedule_day()` → **所有接口 500，连 `action=me` 都挂**。

诊断方法：CLI 一次性加载全部后端文件看 fatal，比逐个接口试快得多。

```bash
php -r "define('LIFEBOARD_API',1); require 'api/bootstrap.php'; require 'api/backup.php';
        require 'api/ics.php'; require_once 'api/push.php'; echo 'OK';"
```

---

## 2. 23 个 action 路由表

`鉴权` 列：`—` 无需登录 / `auth` 需登录 / `admin` 需管理员。
`方法` 列：写接口先校验方法再校验身份，所以未登录的 POST 返回 401，未登录的 GET 写接口返回 405。

| action | 方法 | 鉴权 | CSRF | 作用 | 主要参数 |
|---|---|---|---|---|---|
| `status` | GET | — | — | 是否已安装 | — |
| `me` | GET | — | — | 当前会话 + CSRF token | — |
| `login` | POST | — | ✓ | 登录 | `email` `password` |
| `register` | POST | — | ✓ | 注册（需邀请码） | `email` `password` `invite` |
| `logout` | POST | auth | ✓ | 退出 | — |
| `change_password` | POST | auth | ✓ | 改密码 | `old` `new` |
| `load` | GET | auth | — | 拉整份 state | — |
| `save` | POST | auth | ✓ | 保存（乐观锁） | `base_rev` `data` |
| `force` | POST | auth | ✓ | 强制覆盖（忽略 rev） | `data` |
| `history` | GET | auth | — | 历史版本列表 / 单个详情 | `id`（可选） |
| `restore` | POST | auth | ✓ | 恢复到某历史版本 | `id` |
| `ics_status` | GET | auth | — | 订阅地址 + token | — |
| `ics_reset` | POST | auth | ✓ | 重置 token | — |
| `ics` | GET/HEAD | **token** | — | 输出 iCalendar | `ics=<token>` 或 `token` |
| `push_status` | GET | auth | — | 推送配置 + 最近发送记录 | — |
| `push_save` | POST | auth | ✓ | 保存 webhook / 开关 | `webhook` `enabled` |
| `push_test` | POST | auth | ✓ | 立刻发一条测试消息 | — |
| `push_off` | POST | auth | ✓ | 暂停推送 | — |
| `push_preview` | GET | auth | — | 今日推送计划（只读） | — |
| `admin_users` | GET | admin | — | 用户列表 | — |
| `admin_user_update` | POST | admin | ✓ | 改状态 / 重置密码 | `id` `action` `value` |
| `admin_settings` | GET | admin | — | 站点设置 | — |
| `admin_settings_save` | POST | admin | ✓ | 保存站点设置 | `registration_open` `invite_code` |

### 2.1 统一的响应格式

```php
lb_json(['ok' => true, ...]);                        // 200
lb_fail('人能看懂的中文', 400, 'machine_code');       // 4xx/5xx
// → {"ok":false,"error":"...","code":"..."}
```

**`code` 是给代码判断用的，`error` 是给人看的。** 前端只看 `code`。

### 2.2 `ics` 为什么不需要登录

系统日历（iOS / 安卓）发请求时不带 Cookie。所以订阅靠 URL 里的 **token** 鉴权。

- token 存在 `users.ics_token`，`ics_reset` 可以换新的
- 地址形如 `https://host/api.php?ics=<token>.ics`
- **末尾的 `.ics` 是必须的**：小米等安卓日历按后缀判断这是不是日历源
- 只认 `GET`/`HEAD`；订阅地址无效时**输出空日历而不是 404**，
  否则日历客户端会把"404"记成永久失败，不再重试

---

## 3. 鉴权与会话

### 3.1 单设备登录（`session_epoch`）

```php
users.session_epoch  ← 每登录一次 +1
$_SESSION['epoch']   ← 登录时写入当时的 epoch
lb_user() 每次请求比对：不一致 → 清会话 + 标记 kicked → 401 session_replaced
```

**效果**：同一账号只允许一台设备在线。新设备登录，旧设备下次请求就被踢。
前端 `handleCloudError` 会区分「被顶替」和「会话过期」两种提示。

### 3.2 登录限流

| 常量 | 值 | 含义 |
|---|---|---|
| `LB_LOGIN_WINDOW` | 900 秒 | 15 分钟窗口 |
| `LB_MAX_LOGIN_FAILS` | 8 | 同 IP + 邮箱最多失败 8 次 |
| `LB_REGISTER_WINDOW` | 3600 秒 | 1 小时 |
| `LB_MAX_REGISTERS` | 10 | 同 IP 每小时最多 10 次注册尝试 |

数据落在 `login_attempts` / `register_attempts` 两张表。

**`LB_DUMMY_HASH` 的用途**：邮箱不存在时也跑一次 `password_verify`，
让响应时间和"密码错"一致，避免通过时间差探测账号是否存在。

### 3.3 CSRF

```php
lb_csrf()          // 生成/取回当前会话的 token
lb_require_csrf()  // 校验请求头 X-CSRF-Token 或 body.csrf
```

`me` 接口会把 token 返给前端，前端存内存，之后每个写请求带上。

**所有 POST 都要 CSRF。** 例外只有 `login` / `register`（还没有会话）。

---

## 4. 数据存储

### 4.1 七张表

| 表 | 用途 |
|---|---|
| `users` | 账号、权限、`ics_token`、`push_webhook`、`push_enabled`、`session_epoch` |
| `boards` | **业务数据主体**：`user_id` + `data`(LONGTEXT) + `rev` + `updated_at` |
| `board_revisions` | 历史快照，每用户保留最近 20 版 / 30 天 |
| `push_sent` | 推送去重记录，唯一索引 `(user_id, slot_key)` |
| `app_settings` | 站点级设置（注册开关、邀请码） |
| `login_attempts` | 登录限流 |
| `register_attempts` | 注册限流 |

### 4.2 整份快照模型

`boards.data` 存的是**整个 `state` 的 JSON**，不是增量。每次保存覆盖。

**为什么可以这样**：实测单用户 state 约 24 KB（tasks 7.2K / events 6.8K / meds 5.9K / habits 2.4K），
上限由 `config.php` 的 `max_bytes` 控制（默认 2 MB）。这个体量下全量快照完全够用，
换来的是"永远不会出现增量合并漏字段"。

**代价**：任何字段的丢失都是整份丢。所以 `mergeStates` 的正确性至关重要。

### 4.3 乐观锁

```php
$baseRev = (int)$body['base_rev'];
SELECT ... FROM boards WHERE user_id = ? FOR UPDATE;   ← 行锁
if ($baseRev !== $row['rev']) → 409 + { remote: {data, rev, updated_at} }
UPDATE boards SET data=?, rev=rev+1 WHERE user_id=?
```

- `force` 走 `base_rev = -1`，跳过 rev 检查，直接覆盖
- 保存前会 `lb_snapshot_board()` 把**旧数据**存进 `board_revisions`
- 表结构还没迁移时快照失败，**不阻塞保存**（`error_log` 后继续）

### 4.4 每日快照（`api/backup.php`）

| 常量 | 值 |
|---|---|
| `LB_BACKUP_KEEP_DAYS` | 30 天 |
| `LB_BACKUP_MIN_GAP` | 1800 秒（当天已备份则半小时内不重复） |

- 落盘到 `../backups/YYYY-MM-DD.php`
- **文件写成 `.php` + 首行 `<?php exit; ?>`**：放在站点目录里即使被公网访问也不吐数据。
  取回时删掉第一行就是纯 JSON
- `lb_backup_is_mine()` 只处理自己写出来的文件名，别的文件一概不碰
- 整个入口 `lb_daily_backup()` 在 `api.php` 里被调用，**内部整段 try/catch**，
  DB 挂掉时只记 `error_log`，不影响正常请求

恢复用 `tools/restore_backup.php`，默认预演，`--yes` 才写库。

---

## 5. 三套「什么时候该提醒」实现

这是本项目最容易出漂移的地方。**改一套就要看另两套。**

### 5.1 分工

| 实现 | 位置 | 输出 | 谁消费 |
|---|---|---|---|
| 页内横幅 | `index.html` → `remindItems()` | 打开网页时显示什么 | 浏览器 |
| 日历订阅 | `api/ics.php` + 前端 `buildICS()` | `.ics` 规则（`FREQ=DAILY`） | 系统日历 |
| 手机推送 | `api/schedule.php` | 某一天的**实例** | cron + 微信 |

**为什么 ics 和 schedule 不能合并**：

- ics 要交给日历客户端**长期自己算**，所以输出规则
- 推送必须在**正确的那一分钟**主动发，所以需要实例

`ics.php` 把所有事件 `while ($start <= $now) $start = +1 day` 推到未来，
它根本没有"今天此刻"的概念。所以两者可以共用字段定义，但不能共用函数。

### 5.2 过滤条件对照表

**用药**

| 条件 | `schedule.php` | `ics.php` | 前端 `buildICS()` | 前端 `remindItems()` |
|---|---|---|---|---|
| `courseType === 'prn'` 跳过 | ✓ | ✓ | ✓ | ✓ |
| `status !== 'active'` 跳过 | ✓ | ✓ | ✓ | ✓ |
| `date < startDate` 跳过 | ✓ | ✓ | ✓ | — |
| `endDate` 只看 `short` | ✓ | ✓ | ✓ | — |
| `times` 为空跳过 | ✓ | ✓ | ✓ | ✓ |
| **当天该时段已服药则跳过** | ✓ | ✗ | ✗ | ✓ |

> 最后一行是有意为之：日历里保留事件（用户可能还想看"今天该吃什么"），
> 但推送和横幅不该催已经吃过的人。允许提前吃：7:50 记了，8:00 不再响。

**待办**

| 条件 | `schedule.php` | `ics.php` | 前端 `buildICS()` |
|---|---|---|---|
| 已归档跳过 | ✓ | ✓ | ✓ |
| `status === 'done'` 跳过 | ✓ | ✓ | ✓ |
| **`status === 'cancelled'` 跳过** | ✓ | ✓ | ✓ |
| `due` 不是合法日期跳过 | ✓ | ✓ | ✓ |
| **只有 `due === 今天` 才提醒** | ✓ | — | — |
| 逾期不进日历 | — | ✓ | ✓ |
| `notify === false` 跳过 | ✓ | ✓ | ✓ |
| 通知时间 | `notifyTime`（默认 09:00） | 同 | 同 |

> `cancelled` 曾经只有 `schedule.php` 排除，日历里还留着（v48 已统一）。
> 保留它会制造「日历还有、手机不响」的假故障现象——看起来像推送漏了。

**习惯**

| 条件 | `schedule.php` | `ics.php` | 前端 `buildICS()` |
|---|---|---|---|
| 已归档跳过 | ✓ | ✓ | ✓ |
| `optional` 或 `med` 跳过 | ✓ | ✓ | ✓ |
| `type === 'quit'` 跳过 | ✓ | ✓ | ✓ |
| `notify === false` 跳过 | ✓ | ✓ | ✓ |
| 没有 `suggestTime` 跳过 | ✓ | ✓ | ✓ |
| **当天已打卡则跳过** | ✓ | ✗ | ✗ |
| 频率 daily/weekly/monthly | ✓（按 `date('w')` / `date('j')` 判断） | ✓（用 RRULE） | ✓（用 RRULE） |

### 5.3 星期约定

**统一 0-6，0 = 周日。**

| 位置 | 用的是 |
|---|---|
| `WEEK_CN = ['日','一',...]` | 索引 0 = 日 |
| `ICS_WEEK = ['SU','MO',...]` | 索引 0 = 日 |
| `task.repeatWeekday` | 0 = 日 |
| `habit.notifyWeekday` | 0 = 日 |
| PHP `date('w')` | 0 = 日 ✓ |
| PHP `date('N')` | **1 = 周一，别用** |

---

## 6. 推送（`api/push.php`）

### 6.1 两层职责

```
lb_push_send($webhook, $content, &$err, $type)   ← 只负责「把一段文字发出去」
lb_push_tick_run($pdo, $date, $hm, $sender)      ← 负责「这一分钟该发什么、发完记账」
```

**逻辑与 IO 分开是有意的**：`$sender` 由调用方传入，测试时可以塞一个假的，
于是「去重是否正确」「发失败会不会回滚」这些最容易写错的地方能被穷举验证。

### 6.2 `lb_push_send` 的签名契约（重要）

```php
function lb_push_send(string $webhook, string $content, ?string &$err = null, string $type = 'text'): bool
```

第 3 参必须是 `&$err`（引用），第 4 参才是 `$type`。

**为什么强调**：`lb_push_tick_run` 里是三参调用 `$sender($hook, $text, $why)`。
曾经签名是 `(webhook, content, $type, &$err)`，结果 `$why` 被塞进 `$type`，
`msgtype` 变成空字符串，**企业微信返回 errcode 0 但一条都不显示**。

`e2e/test-push.php` 里有反射测试锁死参数顺序，别删。

### 6.3 安全限制

- 只允许发到 `qyapi.weixin.qq.com` 的 https 地址（`lb_push_url_ok`）
  —— 地址由用户填写，不限制域名等于开一个 SSRF 口子
- 优先 curl，没装则退回 stream context
- 文本上限 2000 字节，按 UTF-8 安全截断（不依赖 `mbstring`）
- 全程不抛异常：调用方是每分钟跑的定时任务，一条失败不该让整轮中断

### 6.4 去重（最容易错的地方）

```php
INSERT IGNORE INTO push_sent (user_id, slot_key, kind, sent_at) VALUES (?,?,?,?)   -- MySQL
INSERT OR IGNORE INTO ...                                                          -- SQLite
```

- 唯一索引 `(user_id, slot_key)` 是去重的**唯一**依靠，**不用"先查再插"**
- **先占位再发送**：发失败必须 `DELETE` 占位，否则那条提醒永久丢失（不会再被尝试）
- `slot_key = 日期|kind|id|时间`，例：`2026-10-30|med|med_abc|09:40`
- 时间窗只往前宽容 **3 分钟**（`lb_schedule_due`），更早的时段不补发

**上线前必须验证唯一索引真的建上了**：

```bash
php tools/push_fix.php     # 检测 + 清理重复 + 补建索引，全幂等
```

线上踩过：索引存在但**不是唯一的**（同名普通索引），`INSERT IGNORE` 每轮都成功，
表现为"每分钟重复发"。

### 6.5 定时任务

```bash
# 宝塔 → 计划任务 → Shell 脚本 → 每 1 分钟
/www/server/php/82/bin/php /www/wwwroot/todo.csl88.top/tools/push_tick.php
```

**绝对不能带 `--dry`。** `--dry` 是预演模式：只打印、不真发、不写库。
曾经因为 cron 里带了 `--dry`，推送"一直收不到"排查了两小时——
症状是日志每条带 `[预演]` 前缀、每轮"发出"而非"跳过"。

---

## 7. 工具脚本（`tools/`）

| 脚本 | 用途 | 安全措施 |
|---|---|---|
| `push_tick.php` | 推送主循环，cron 每分钟跑 | `--dry` 预演、`--at HH:MM` 指定时刻、`-v` 详细 |
| `push_diag.php` | **只读**诊断"某时刻该不该发、为什么没发" | 不写库不发消息；非 CLI 访问返回 404 |
| `push_fix.php` | 检测并补建 `push_sent` 唯一索引 | 幂等，可重复跑 |
| `push_test.php` | 发一条测试消息 | **只允许 CLI**（它把 webhook 当参数收，开放公网会让 access log 留下完整地址） |
| `restore_backup.php` | 从每日快照恢复 | 默认预演，`--yes` 才写库 |
| `create_user.php` | 命令行建号（救援） | 只允许 CLI |

**排查"为什么这条没发"的标准动作**：

```bash
# 1. 看 cron 到底跑没跑、有没有 [预演] 前缀
grep -h "发出" /www/server/cron/*.log | tail -5

# 2. 预演指定时刻，看它算出什么
php tools/push_tick.php --dry --at 08:40 -v

# 3. 还是不对，dump 全部依据
php tools/push_diag.php --at 08:40
```

---

## 8. 部署与运维

完整步骤见 `DEPLOY.md`。这里只列**必须记住的**：

### 8.1 发布顺序

```
含 db/migrations/ 新文件  →  先跑 SQL
含 api/ 改动              →  和前端一起传（先传 PHP，传完立刻访问首页验证不 500）
只改前端                  →  传 index.html + service-worker.js
```

### 8.2 线上版本核查（不看部署记录，直接比 md5）

```bash
curl -sS "https://todo.csl88.top/index.html?_=$(date +%s)" -o online.html
md5sum online.html /path/to/local/index.html
curl -sS "https://todo.csl88.top/service-worker.js" | grep CACHE
```

### 8.3 Nginx 必须有的配置

- `location = /service-worker.js` → `Cache-Control: no-cache`
- `location = /manifest.json` → `types { application/manifest+json json; }`
- 安全头：`X-Content-Type-Options` / `X-Frame-Options` / `Referrer-Policy`，
  都要带 `always`。**注意**：`location` 里只要写了自己的 `add_header`，
  就不再继承 server 级的同指令，要单独补一遍
- `backups/`、`api/config.php`、`install.lock` 禁止公网访问

### 8.4 定时任务只有一条

每分钟一次 `push_tick.php`（不带 `--dry`）。汇报（08:20 / 12:30 / 20:00）复用它，不需要额外任务。

---

## 9. 后端陷阱清单

1. **`api/` 下文件一律 `require_once`**，否则函数重复声明 → 全站 500。
2. **CLI 里 require 后端文件前必须 `define('LIFEBOARD_API', 1)`**，否则静默退出。
3. **`lb_push_send` 的第 3 参是 `&$err`**，不是 `$type`。有反射测试锁着。
4. **cron 绝不能带 `--dry`**。
5. **`push_sent` 的唯一索引必须是真的唯一**，不是同名普通索引。
6. **备份/日志这类附属逻辑必须整段 try/catch**，失败只记 `error_log`。
7. **日历时间必须 `DTSTART;TZID=Asia/Shanghai` + 内嵌 VTIMEZONE**，
   不要用 UTC——07:30 换 UTC 是前一天，`RRULE` 的 `BYDAY` 会偏一天。
   `UNTIL` 才用 UTC，手工减 8 小时。
8. **PHP 文件行尾不统一**：`api.php` 是 CRLF，`api/bootstrap.php` 是 LF。脚本改它们要 `newline=''`。
9. **新增 `api/*.php` 时，`e2e/verify-api-http.py` 会自动复制**（已改成扫目录），
   但 `install/` 和 `config.php` 不会，测试用自己伪造的那份。
10. **`lb_settings()` 有 static 缓存**，同一请求内改了设置要传 `refresh=true` 才读得到新值。


---

## 自定义通知（v71）

`api/schedule.php` 的 `lb_schedule_notices($state, $date)`：把 `state.notices` 里当天该发的
挑出来，返回和 `lb_schedule_day` 一样的结构（`time / kind='notice' / id / title / body`）。

**为什么单独一个函数、不并进 `lb_schedule_day`**：后者会被 `api/ics.php` 和前端 `buildICS`
复用来生成日历日程。通知不是日程，混进去会让订阅的日历里多出一堆条目。
`e2e/test-schedule.php` 有一条用例专门锁这个（`lb_schedule_day` 里不许出现 `kind === 'notice'`）。

`api/push.php` 的 `lb_push_tick_run` 里三路合并：

```php
$plan = array_merge(
    lb_schedule_day($state, $date),
    lb_schedule_reports($state, $date),
    lb_schedule_notices($state, $date)
);
```

因为 `slot_key` 带日期，重复通知每天各发一次、单次只发一次，不需要额外状态。

`api.php` 的 `push_test` 增加了可选 `text` 参数，配置页的「重发」就借它把原文再推一次。

### 倒数日提醒（v76）

`api/schedule.php` 的 `lb_schedule_countdowns($state, $date)`：算 `目标日期 - $date` 的天数，
落在 `remindDays` 里才返回，结构跟 notices 一样（`time / kind='countdown' / id / title / body`）。

- **只对未来发**：`$days < 0` 直接跳过。「已经过去 100 天」不是提醒，是回顾。
- 天数用 `round` 不用 `floor`：跨夏令时的日子是 23/25 小时，`floor` 会把「还有 1 天」算成 0。
- 同样**不能并进 `lb_schedule_day`**，否则日历订阅里会冒出倒数日条目
  （`test-schedule.php` 有专门一条锁它）。
- `push.php` 的 `lb_push_tick_run` 现在是四路 merge：day / reports / notices / countdowns。
