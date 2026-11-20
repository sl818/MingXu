# 改动地图

> 改某个功能之前先查这张表：**要动哪几处、跑哪个测试**。
> 目的不是给人看的说明书，是省掉每次从头 grep 的探索。
> 加功能时顺手补一行；表里的函数名都能在代码里搜到，对不上就说明表过期了。

---

## 0. 通用铁律

| 改了什么 | 必须同时改 | 验证 |
| --- | --- | --- |
| 新增**顶层字段**（`state.xxx`） | `normalizeState` / `mergeStates` / `repairBackup` 三处 | `verify-import-keep`(13) |
| 新增**可编辑实体** | 合并按 id 并集、带 `updatedAt`；单值比较时间戳 | 同上 |
| 新增前端会调的**接口** | 所有 e2e mock 都要加路由 | `verify-api-http`(33) |
| 改 CSS / JS / HTML | `service-worker.js` 的 `CACHE` 递增 | — |
| 删 UI | 先 grep `e2e/` 里的选择器与文案 | 相关 verify |
| 改列 / 加列（数据库） | 先跑 SQL 再传代码，检测函数要容错 | `verify-api-http` |

**行尾**：全仓库 LF（`.gitattributes` 锁定）。写文件一率用 `\n`，不要掺 `\r`。

---

## 1. 习惯

| 位置 | 说明 |
| --- | --- |
| `viewToday` / `habitCard(h,d,compact)` | 今日页卡片；`compact` 分支是常驻区窄卡，改卡片结构要保住它 |
| `viewHabits` / `habitManageRows` | 习惯管理页 |
| `habitMonthOverview` / `habitDueOn` / `habitMonthRow` | 本月概览；统计页「本月」分段也调同一个函数 |
| `met(h,d)` / `dayStats` / `rateOver` / `habitDayAcc` | 达标与完成率口径 |
| `normalizeHabits` / `normalizeState` | 频率、截止时刻、目标数的清洗 |

**改判定必须同步** `algoModal`（考核算法弹窗是代码镜像，不同步就等于文档在撒谎）。

测试：`verify-habit-btn`(31)、`verify-quit-multi`(32)、`verify-habit-month`(38)、
`verify-habit-deadline`(16)、`verify-habit-feedback`(16)。

---

## 2. 戒烟

| 位置 | 说明 |
| --- | --- |
| `viewQuit` / `quitCard` | 页面与卡片；汇总 12 格的数据全现算 |
| `normalizePacks` | `packs` 只有 `{id,at,name,price,size,cf}`，**加字段必须同步这个白名单** |
| `packSpans` / `openAt` | 库存与当前包，全是派生量，一个字段都不存 |
| `quitStartAvg` / `quitNowAvg` / `quitWeekAvgs` | 减量进度与近 4 周 |

测试：`verify-quit-page`(32)、`verify-quit-pack`、`verify-quit-multi`(32)。

---

## 3. 待办

| 位置 | 说明 |
| --- | --- |
| `viewBoard` / `taskCard` | 看板与卡片 |
| `taskStats` | 任务统计；改它要同步 `algoModal` |
| `taskArchViewModal` | 已归档任务的只读弹窗（备注全文） |
| `liveTasks` / `orderedNav` | 取数范围与导航顺序 |

测试：`verify-archive`(52)、`verify-batch3`(60)、`verify-task-detail`。

---

## 4. 清债

| 位置 | 说明 |
| --- | --- |
| `viewMoney` + `moneyOverviewView` / `moneyDebtsView` / `moneyBudgetView` / `moneyPlanView` / `moneyLogView` / `moneyToolsView` | 六个子页 |
| `subTab` 字典 | 子页状态**不进 state**，进了就要改三处清洗，且两端会互相覆盖 |
| `normalizeMoney` | `state.money` 的清洗；`due = 0` 表示没有具体还款日 |
| `moneyDebtsSummaryHtml` | 债务页底部汇总；分母是初始总额，平均年化按余额加权 |

**还款日四处口径必须一致**：`dayDebts`（页面日历）、`buildICS`（导出）、
`api/ics.php`（订阅）、`lb_schedule_debts`（企微提醒）。`due = 0` 四处都跳过。

测试：`verify-money-v88`(20) / `v89`(24) / `v90`(29) / `v91`(34) / `v92`(23) / `v94`(32) / `v95`(24)、
`verify-debt-card`(22)、`verify-budget-actions`(25)、`verify-money-intro`(24)。

---

## 5. 体重

| 位置 | 说明 |
| --- | --- |
| `viewWeight` | 页面：档案卡 → hero → 两栏（折线图 + 统计/体脂） |
| `weightLineChart` / `weightSummaryHtml` / `weightFatPanel` / `weightFatSpark` | 图表与右栏两块 |
| `normalizeWeightRecord` | 记录清洗；`fat` 可选、0 表示没量 |

折线图 viewBox 是 600×340。**改高度会让写死坐标的断言失效**，测试里从 viewBox 推边界。

测试：`verify-weight-chart`(27)、`verify-weight-fat`(21)、`audit-weight`(18)。

---

## 6. 随笔 / 用药

| 位置 | 说明 |
| --- | --- |
| `viewEssays` / `essayModal` / `saveEssayForm` | 随笔；正文是 `text` 字段 |
| `viewMeds` / `medById` / `doseCount` / `medScheduledCount` | 用药 |
| `normalizeMeds` / `mergeStates`（`doses` 三层并集） | 用药合并单独写，不能和 `checks` 混在一起 |

测试：`verify-med-page` / `verify-med-form` / `verify-med-card` / `verify-med-collapse`、
`verify-stock-v31`、`verify-stockcheck-v40`。

---

## 7. 日历与提醒（三处口径）

同一条规则要在**三个地方**成立，改一处必须改另两处：

1. 前端 `buildICS`（下载 .ics）与页面日历 `dayDebts` / `dayHabits`
2. `api/ics.php`（订阅地址）
3. `api/schedule.php` 的 `lb_schedule_notices` / `lb_schedule_debts`（企微推送）

`lb_schedule_day` 被前两处复用，**不要把提醒塞进去**，否则订阅里会多条目。

测试：`e2e/test-ics.php`(64)、`e2e/test-schedule.php`(130)、`verify-ics-subscribe`(9)、`verify-ics-ui`。

---

## 8. 统计

| 位置 | 说明 |
| --- | --- |
| `viewStats` | 6 块：总览 / 习惯 / 用药 / 戒烟 / 体重 / 任务完成度 |
| `statsSegHtml` | 分段控件；`stats-habit-tab` 与 `stats-med-tab` 的选项在 `viewStats` 里 |
| `monthReviewBody` | 本月回顾 |

**改 `met` / `dayStats` / `rateOver` / `habitDayAcc` / `taskStats` 必须同步 `algoModal`**。

测试：`verify-stats-v80`、`verify-batch3`(60)、`verify-algo-modal`、`audit-contrast-v33`。

---

## 9. 导航 / 布局 / 主题

| 位置 | 说明 |
| --- | --- |
| `NAV` / `MORE_PAGES` / `orderedNav` | 12 个页面；手机上部分进「更多」抽屉 |
| `SKINS` | 6 套皮肤 |
| 主题注册**四处** | `SKINS`、首屏白名单（`<head>` 里那个内联脚本）、`<link>`、SW `ASSETS` |

**CSS 顺序**：`assets/app.css` → `themes/*.css`。主题在后加载，所以
`themes` 里 `:root[data-skin] .btn` 这类规则会压掉 `app.css` 里的裸类名。
自己写按钮样式要带 `:root[data-skin]` 前缀，否则在部分皮肤下不生效。

对比度：`audit-contrast-v33`（页面）、`audit-stock-contrast`（弹窗）、`audit-cmd-contrast`（命令卡）。

---

## 9.2 注册

| 位置 | 说明 |
| --- | --- |
| `lb_reg_mode()` / `lb_reg_public()`（`api/bootstrap.php`） | 三种注册方式；兼容旧 `registration_open` |
| `api.php` 的 `register_code` | 发注册验证码；限流 60 秒 / 每天 10 条 / IP 20 条 |
| `api.php` 的 `register` | 按模式校验邀请码或验证码；验证码校验在 INSERT 之前 |
| `email_codes` 表 | 迁移 `2026-11-20_email_codes.sql`；只存 sha256、10 分钟、一次性 |
| 前端 | `cloudRegisterModal`（按 `data-mode` 渲两套字段）、`registerSendCode`、`regLabel()` |

测试：`verify-register-code.py`(22)。

## 9.3 站点邮件与找回密码

| 位置 | 说明 |
| --- | --- |
| `lb_site_mail_cfg_load` / `_save`（`api/mailer.php`） | 站点级发信配置，存 `app_settings` 的 `site_mail_*` |
| `lb_site_mail_send()` | **只给注册确认和找回密码用**，别接到提醒调度里 |
| `api.php` 的 `password_forgot` / `password_reset` | token 存 sha256、30 分钟、一次性；防枚举 |
| `password_resets` 表 | 迁移 `2026-11-20_password_reset.sql` |
| 前端 | `forgotPasswordModal` / `passwordResetModal` / `checkResetToken` / `siteMailPanelHtml` |

测试：`verify-site-mail.py`(25)。

## 9.4 通知与提醒

| 位置 | 说明 |
| --- | --- |
| `lb_schedule_day` 等（`api/schedule.php`） | 算出「某天几点该提醒什么」；只产出事件，不发 |
| `lb_push_tick_run()`（`api/push.php`） | 每分钟调度。`$senders` 可以是单个 callable 或 `[['channel','fn'], ...]` |
| 通道 | `wecom`（企业微信）、`mail`（邮件）。加通道只需往 `$senders` 里加一项，不动调度核心 |
| 去重 | `push_sent` 唯一键 `(user_id, slot_key, channel)`。**channel 列必须迁移**，否则多通道互相顶掉 |
| `tools/push_tick.php` | cron 入口，传两个通道；输出带通道标记 |
| `lb_notify_prefs_load` / `_save` | 通道矩阵，存 `app_settings` 的 `notify_prefs_<uid>`（零迁移） |
| `lb_notify_kinds()` | 七种事件类型，**必须与 `schedule.php` 产出的 kind 一致**（notice / debt 容易写错） |
| `lb_notify_merge_med()` | 同时刻的用药合并成一条；只动 `med`，合并后 id 为 `batch_<time>` |
| `lb_notify_quiet_load` / `_save` | 夜间静默开关，**默认关**；`lb_notify_in_quiet()` 判断 23:00–07:00 |
| `lb_notify_report_load` / `_save` | 每日小结三个时刻，空串 = 不发；非法值拒绝写入 |
| `lb_schedule_reports($state, $date, $times)` | 第三参数可选，不传用默认 08:20/12:30/20:00（旧调用不受影响） |

测试：`test-push-tick.php`(44) / `test-notify-channel.php`(18) / `test-mailer.php`(44)。

## 9.5 账号与资料

| 位置 | 说明 |
| --- | --- |
| `cloudAccountModal` | 账号资料弹窗：名称、邮箱、改密两段。**不是 `<form>`**，两个按钮各自 `data-act` |
| `cloudDoSaveProfile` / `cloudDoChangePassword` | 分别读卡片里的字段，各自校验 |
| `api.php` 的 `profile_save` | 名称 1–40 字、邮箱格式 + 唯一性；改邮箱不踢会话 |
| `api.php` 的 `change_password` | 旧密码校验 + 新密码 ≥8 位 + `session_epoch` 递增（其他设备失效） |
| 入口 | 三区左下角 `.su-card`（整卡可点）、设置页「资料」按钮 |

测试：`verify-profile.py`(20)。

## 10. 云同步 / 备份

| 位置 | 说明 |
| --- | --- |
| `cloudPush` / `base_rev` | 乐观锁；冲突时 `mergeStates` 自动合并，**界面无提示** |
| `mergeStates` | `habits` 以云端为主、本地只补新增 id；`checks` 按天取较大值 |
| `repairBackup` | 导入时的清洗；不认识顶层键要原样带过（别退回白名单） |
| 导出 | 全量 `JSON.stringify(state)`，设置页那个就是完整备份 |

测试：`verify-import-keep`(13)、`e2e/test-backup.php`。

---

## 11. 推送

| 位置 | 说明 |
| --- | --- |
| `api/push.php` | `lb_push_send(webhook, content, &$err, $type)`，签名被反射测试锁死 |
| `tools/push_tick.php` | 宝塔每分钟调用，**不能带 `--dry`** |
| `pushLoad` / `pushSave` | 面板在两处（设置 + 配置），搬家要同步重绘条件 |

测试：`e2e/test-push.php`、`e2e/test-push-tick.php`、`verify-push-ui`、`verify-push-lock`。

---

## 12. 发布清单

1. `service-worker.js` 的 `CACHE` 递增（改 CSS / JS / HTML 就必须）
2. 含 `db/migrations/` → **先跑 SQL 再传代码**
3. 含 `api/` → 同时传 PHP
4. `Todo-update.zip` 按 23 个文件重打（2026-11-18 起含 `assets/app.css`）
5. 线上核对 md5，不看部署记录

---

## 附：回归脚本分层

| 层 | 脚本 | 项数 |
| --- | --- | --- |
| 语法 | `node _check_script.mjs` | — |
| 后端单测 | `e2e/test-ics.php` / `test-schedule.php` / `test-push.php` / `test-push-tick.php` | 64 / 130 / — / — |
| 集成 | `verify-ics-subscribe.py` / `verify-api-http.py` | 9 / 33 |
| 主回归 | `regression-v3.py` / `verify-v15.py` / `verify-mobile-nav.py` | 28 / 35 / 44 |
| 批次 | `verify-batch2.py` / `verify-batch3.py` / `verify-batch4.py` | 51 / 60 / 20 |
| 视觉 | `audit-contrast-v33.py` / `audit-stock-contrast.py` / `audit-cmd-contrast.py` | 2532 取样 |
| 文档 | `e2e/check-doc-anchors.py` | — |

跑法见 `docs/DEPLOY.md`；本机解释器与 PHP 路径写在 `HANDOFF.md` 的验证段。
