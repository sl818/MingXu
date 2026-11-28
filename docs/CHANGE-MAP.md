# 改动地图

> 改某个功能之前先查这张表：**要动哪几处、跑哪个测试**。
> 目的不是给人看的说明书，是省掉每次从头 grep 的探索。
> 加功能时顺手补一行；表里的函数名都能在代码里搜到，对不上就说明表过期了。

**给智能体的两步约定**（`.workbuddy/memory/MEMORY.md` 同步写了）：
1. **开工先读**：任何改动前读本表建立结构认知，再读文末「修改日志」最后 3 条，
   看有没有并行会话刚改过同一节——撞上就先停下来问，别两个人改同一块。
   本表是导航不是圣旨，函数名与口径仍要在代码里核实。
2. **改完登记**：改动触及本表任何条目（函数名改名/删除、新增模块或顶层字段、合并口径变化、
   新增测试脚本、主题/导航口径变化），当场更新对应行 + 在文末日志追加一条，不许攒着。

**最后更新**：2026-11-27 · 对应代码版本 **v205**（`service-worker.js` 的 `CACHE`）。
下文出现的 `v31` / `v88` / `v127` 等是历史版本锚点，不是当前版本。
测试项数会随版本变化，**以脚本实测输出为准**，括号里的数字仅作量级参考。

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

**跑表格对齐 / 批量格式化类脚本后，必须核对章节序列。**（2026-11-27 实测教训）
`docs/PRD-HABITS-V2.md` 做过一次纯排版重排（表格补对齐空格）：体积 25KB → 59KB，
行数 730 → 724 几乎没变，文件照常能解析，**却静默吞掉了整章「十三、上线计划、依赖与上线后验证」**，
事后没人发现。原因是这类脚本按"块"重写，段落边界判断错就整段消失，而体积与行数都不会报警。
验收两条，缺一不可：

1. `grep -nE "^#{1,2} " <file>` 对比处理前后的章节标题序列，**一条不能少**；
2. 交叉引用要能落地——文档里写「依赖三档 ✅（13.2）」，就得确认 `13.2` 真的存在。

同类风险：`sed -i` 批量替换、正则清理注释块、自动去重/合并表格、IDE 的"格式化整个文件"。

---

## 1. 习惯

| 位置 | 说明 |
| --- | --- |
| `viewToday` / `habitCard(h,d,compact)` | 今日页卡片；`compact` 分支是常驻区窄卡，改卡片结构要保住它 |
| `viewHabits` / `habitManageRows` | 习惯管理页 |
| `habitMonthOverview` / `habitDueOn` / `habitMonthRow` | 本月概览；统计页「本月」分段也调同一个函数 |
| `met(h,d)` / `dayStats` / `rateOver` / `habitDayAcc` | 达标与完成率口径 |
| `QUIT_CHECKIN_FROM` / `quitNeedsCheckin(h,d)` | v204 起戒除类（quit）必须主动打卡：生效日 2026-11-27 起写 `checks` 才算守住；戒烟（smoke）与生效日前历史走老口径。改动要同步 `habitDayMark` / `streakOn` / `quitStreak` / `habitBest` / 三个按钮 handler。**v214 起**：当天有失守时 `habit-ok` / `quit-mark` 先逐次撤销失守（一次一条），撤完再点才写 `checks`——因为 `met()` 对 quit 先判失守短路，不撤失守就永远不达标（v204 漏了这条，多次模式会卡死） |
| `normalizeState` | 习惯清洗**就在它内部**（约 1384 行起）：频率、截止时刻、目标数；没有单独的 `normalizeHabits` |

**改判定必须同步** `algoModal`（考核算法弹窗是代码镜像，不同步就等于文档在撒谎）。

测试：`verify-habit-btn`(31)、`verify-quit-multi`(32)、`verify-habit-month`(38)、
`verify-habit-deadline`(16)、`verify-habit-feedback`(16)、`verify-quit-checkin`(21，v204 主动打卡 + v214 多次模式逐次撤销)、
`verify-habit-sched`(13，v219 节奏 sched：四选一表单/weekdays off/老数据 notifyFreq 兼容)。
注：前四个脚本里找 `.pips .pip` / `.habit-done` 的断言在 v2 卡片改版后已腐化，改前版本同样失败，不算回归信号；
`verify-habit-month` 的 14 项失败同为模块化改版后的既有腐化（基线对照已确认），不计入回归信号。

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
| `viewMeds` / `medById` / `medScheduledCount` / `medScheduledFor` | 用药；用药清洗走 `migrateMeds`，没有单独的 `normalizeMeds` / `doseCount` |
| `normalizeState`（`doses` 原样带过）/ `mergeStates`（`doses` 三层并集） | 用药合并单独写，不能和 `checks` 混在一起 |

测试：`verify-med-page` / `verify-med-form` / `verify-med-card` / `verify-med-collapse`、
`verify-stock-v31`、`verify-stockcheck-v40`。

---

## 6.1 运动（v179 起，当前最复杂的模块）

数据在 `state.modules.move`，含 `sports[]` 与 `records[]` 两个数组。**改动前先看 `docs/MOVE-FIX-PLAN-v197.md`**。

### 清洗与白名单

| 位置 | 说明 |
| --- | --- |
| `normalizeMoveSport` | 实例字段白名单：`tIdx`/`tVal`（目标档与值）、`freqKind`/`freqN`/`perDay`/`weekSel`、`recMode`/`fixedSteps`、`fields[]`、`distLocked`、`notifyOn`/`channels` |
| `normalizeMoveRecord` | 记录字段白名单 + **真实日期校验**；带 `updatedAt`（合并比新）、`deletedAt`（软删除墓碑，30 天后清理）、`pending`/`skipped` |
| `normalizeModule` / `normalizeModules` | 模块层清洗；外键原样带过，别被洗掉 |
| `MOVE_TYPES` / `MOVE_PICKABLE` | 模式库；`retired:true` 仍保留渲染（游泳/瑜伽），新建列表用 `MOVE_PICKABLE` 过滤 |

加模式 / 加字段要同步四处：`MOVE_TYPES`、记录白名单、补数据 `fieldsHtml`（已动态化）、统计 `moveStatsHtml`。

### 合并（并发口径，v198）

`mergeMoveModule(remote, local)` 单独写，**不能整块取新**：

- `sports` / `records` 都按 `id` 并集合并；只有一端有的直接保留。
- `records` 墓碑优先：任一端有 `deletedAt`，合并后就是删掉的，不会被旧数据复活。
- 两端都有时比 `updatedAt`，新的一侧胜出。
- 模块级配置字段整体取较新的一侧。

### 打卡状态机（v181）

非步数打卡先落一条 `pending` 记录并弹数据表单；`movePendingRec()` 找到待填记录时主按钮锁成「记录数据」，「补数据」入口换成「撤销这一次」。填完或点「跳过不记录」（二次确认后置 `skipped`）才放行下一次。记录字段的 `pending` / `skipped` 老数据默认 false。

- `moveRecords()` 过滤墓碑；页面一律用它，不直接读 `m.records`。
- `moveStalePendings` / `moveUnfinishedRecs`：跨天 pending 与「跳过 + 待填」近 30 天列表。
- `closeModal()` 对 `data-must-settle="1"` 的待填弹窗禁止 ESC / 遮罩关闭。

### 统计口径（v197，改前必读）

- `moveStatAgg`：步数是**打卡数据**，跳过也计；时长 / 距离 / 心率等是**运动后数据**，跳过不计。`pending` 单列，不算「有详细数据」。
- `moveStatBounds`：all 范围的起点按**当前模式**最早记录，不用全局最早。
- `moveStatDayScore`：有详细时长按时长；纯步数按 100 步 ≈ 1 分钟折算（否则步数和时长画进同一张热力图会整片全红）。
- 非步数达标 = 当天记录数 ≥ `weekly ? perDay : freqN`；步数按累计步数 ≥ `tVal`。
- 休息日不纳入考核（`moveMet`）：所有实例当天都按计划休息时返回 true。

改 `met` / `dayStats` / `rateOver` / `habitDayAcc` 相关口径时，**同步 `algoModal`**，运动统计也一样。

测试：`verify-move`(基础) / `verify-move-compat-v176` / `verify-move-chan-v177` /
`verify-move-freq-notify-v178` / `verify-move-modes-v179` / `verify-move-flow-v181` /
`verify-move-lock-v183` / `verify-move-rules-v184` / `verify-move-full-v185` /
`verify-move-fixes-v197`；合并逻辑另有 `e2e/test-merge.mjs`。

---

## 7. 日历与提醒（三处口径）

同一条规则要在**三个地方**成立，改一处必须改另两处：

1. 前端 `buildICS`（下载 .ics）与页面日历 `dayDebts`（还款日）；**没有 `dayHabits`**，习惯提醒不进页面日历
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
| `NAV` / `MORE_PAGES` / `orderedNav` | 15 个页面；手机上部分进「更多」抽屉 |
| 主题 | **只有 1 套**（暖纸 / 白卡 / 一支红笔），分浅色与深色两态；v135 起六套皮肤机制已全部删除 |
| 明暗切换 | `<html data-theme="light\|dark">`，首屏内联脚本按 localStorage 设置（v2 起**取消按时间自动判断**），防闪白 |
| 主题样式位置 | `assets/theme-v2.css`（唯一主题，加载在 `app.css` 之后） |

**CSS 顺序**：`assets/app.css` → `assets/theme-v2.css`。主题层在后加载，会压掉 `app.css` 的裸类名，
自定义按钮样式要考虑这层覆盖（旧皮肤时代要带 `:root[data-skin]` 前缀，该机制已删除）。

对比度：`audit-contrast-v33`（页面）、`audit-stock-contrast`（弹窗）、`audit-cmd-contrast`（命令卡）。

---

## 8.9 主题层的约定

| 规则 | 说明 |
| --- | --- |
| 主题**只改令牌与笔触** | 在 `assets/theme-v2.css` 覆盖变量与必要组件，不写页面结构和数据逻辑 |
| 规范出处 | 根目录 `DESIGN.md`（v2）；`docs/design/THEME-V2-PLAN.md` 是需求与执行记录 |
| 焦点轮廓 | **只在 `app.css` 定义一次**，不要在主题层复制 |
| 新增组件 | 样式只写 `app.css`；改完跑三套对比度审计 + 明暗两态截图比对 |
| 历史教训 | 旧皮肤层曾有 76 条重绘组件的规则，所以现在禁止在主题层重绘组件 |

## 9.0 静态资源缓存（v128）

| 位置 | 说明 |
| --- | --- |
| `index.html` 的 `<link>` | 全部带 `?v=NNN`，与 SW 版本一致。**改版本时必须同步改这里** |
| `service-worker.js` 的 `VER` | ASSETS 里统一拼 `?v=' + VER` |
| SW `install` | 逐个 `fetch(..., {cache:'reload'})` + `cache.put`，**不能用 `cache.addAll`**（会吃 HTTP 缓存） |
| `tools/make_release.py` | 打包前校验 HTML 的 `?v=` 与 SW 的 `CACHE`/`VER` 一致，不一致直接拒绝 |
| `index.html` 的 SW 注册 | **必须带 `?v=NNN` 和 `updateViaCache:'none'`**，裸地址会因 HTTP 缓存永不更新（v131 踩过） |

踩坑：v127 发版后，同一账号在两个浏览器上一个样式正常、一个全丢——因为旧 CSS 被重新缓存进了新 SW。

## 9.1 任务编辑与子任务（v127）

| 位置 | 说明 |
| --- | --- |
| `taskModal()` | 三段式弹窗。类名统一 `tk-` 前缀，**别用 `ts-`**（与「任务完成度」组件冲突） |
| `taskSubs` / `taskSubsHtml` / `bindTaskSubs` | 子任务渲染与增删勾；数据在 `task.subtasks` |
| `taskSubsBar()` | 卡片上的进度条，`1/2` + 进度 |
| `taskFoldOpen()` | 折叠区默认展开的判定：有开始时间/时长/重复/通知变化就展开 |
| 卡片点击 | **单击**开弹窗；原来的双击内联展开已移除 |
| `normalizeState` | 子任务规整：非数组补空、去空标题、补 id |

测试：`verify-task-subtasks.py`(28)。

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
| 事件字段（v211） | 13 个产出点统一带 `source`（med/task/habit/water/move/breathe/report/notice/countdown/debt）+ `priority`（紧急/当日/日常）；任务另带 `tag`/`taskPriority`，习惯带 `habitType`，运动带 `sport`，还款带 `due`。**只增不改**，去重键仍是 `日期\|kind\|id\|时间`；`push_preview` 已对齐五源并透传这些字段 |
| `lb_push_tick_run()`（`api/push.php`） | 每分钟调度。发送前过板块闸门（基础板块 on=false 整条跳过、渠道按 11 板块矩阵过滤）；文案走模板渲染 |
| 通道 | `wecom`（企业微信）、`mail`（邮件）。加通道只需往 `$senders` 里加一项，不动调度核心；`browser` 只是板块数据列，服务端不发送 |
| 去重 | `push_sent` 唯一键 `(user_id, slot_key, channel)`。**channel 列必须迁移**，否则多通道互相顶掉 |
| `tools/push_tick.php` | cron 入口，传两个通道；输出带通道标记 |
| `lb_notify_boards_load` / `_save`（v211） | 11 板块 × 3 渠道，存 `{"boards":{...}}`；模块五板块不存 on；旧 7 类扁平读取时原地迁移（habit 渠道继承给 water/move/breathe）。`lb_notify_prefs_load/_save` 保留为旧 7 类兼容层 |
| `lb_notify_kinds()` | 七种事件类型，**必须与 `schedule.php` 产出的 kind 一致**（notice / debt 容易写错） |
| `lb_notify_merge_med()` | 同时刻的用药合并成一条；只动 `med`，合并后 id 为 `batch_<time>`；v211 起合并结果保留 source/priority |
| `lb_notify_quiet_cfg` / `_save`（v211） | 免打扰 `{on,start,end}`，默认关 + 23:00–07:00；旧 `'1'/'0'` 兼容；`lb_notify_in_quiet($hm,$start,$end)` 支持跨夜 |
| `lb_notify_tpl_load` / `_save`（v211） | 文案模板存 `notify_tpl_<uid>`：`{scenes:{…}, mail:{color,footer}}`，11 场景白名单，零迁移 |
| `lb_notify_text_render`（v211） | 模板渲染：9 个变量，source 优先、kind 兜底；**不做转义**（转义只在邮件 HTML 分支） |
| `lb_notify_board_of`（v211） | 事件 → 板块 id；habit 三兄弟靠 source 区分 |
| `lb_mail_smtp_send` / `lb_notify_mail_card`（v211） | 邮件支持 `multipart/alternative`：纯文本 + HTML 卡片两个 part；卡片内联样式，配色/页脚取模板；旧 5 参调用不变，第 6 参可选 HTML |
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

## 13. 升级判断与待办（2026-11-27）

| 文档 | 用途 |
| --- | --- |
| `docs/架构升级评估对照.md` | 外部《明序架构升级建议书》的逐条评估：哪些前提错了、哪些可采纳 |
| `docs/两万行单文件对策.md` | 单文件规模问题的三条路径与推荐做法 |
| `docs/组件规范与日期控件待办.md` | 组件规范 / 日期控件 / 动效规范的实施待办；落地后回头补进本表 |

---

## 14. 地图修改日志（只追加，不改旧行）

> 每次动本表**当场追加一行**，写清改了哪几节、对应什么代码改动、由谁发起。
> 作用：① 两个智能体/会话撞同一任务时，靠最后几条发现对方已动过，避免重复改或互相覆盖；
> ② 本表哪天又对不上代码了，能顺着日志定位是哪次改动漏同步。
> 纯问答与只读分析不记；只改文档也要记。日期取本机当天。

| 日期 | 代码版本 | 改了哪几节 | 改动摘要 | 发起方 |
| --- | --- | --- | --- | --- |
| 2026-11-27 | v202 | 表头 / 6.1 / 1 / 6 / 7 / 9 / 13 | 建表后首次校准：补运动整节、修 4 个死函数名、修主题口径、加版本表头与升级文档索引 | 会话：改动地图校准 |
| 2026-11-27 | v202 | 表头 / 14 | 加「开工两步约定」与本节修改日志，并在 MEMORY.md 写入开工必读规则 | 会话：地图智能体指导 |
| 2026-11-27 | v204 | 1 / 14 | 补 v204 戒除类主动打卡的判定入口（`QUIT_CHECKIN_FROM` / `quitNeedsCheckin`）与同步点；新增 `verify-quit-checkin`(15)、前后对比页 | 会话：戒除类自动打卡修复（与 v204 提交撞车，代码已由并行会话落地，本行补记导航与新验证） |
| 2026-11-27 | v204 | 0 / 14 | 通用铁律新增：表格对齐 / 批量格式化脚本跑完必须核对章节序列（`PRD-HABITS-V2.md` 曾被静默吞掉整章十三，体积与行数均未报警） | 会话：PRD 缺章修复 |
| 2026-11-27 | v205 | 表头 | 校正对应代码版本 v202 → v205（线上与本地均已 v205，本地领先 origin 4 个提交）；同批校正根 `README.md`、`docs/README.md` 里过期的页面数与行数 | 会话：版本号校正 |
| 2026-11-27 | v214 | 1 / 14 | 修 v204 回归：戒除类当天有失守时，「完成」按钮无法撤销（`met()` 失守短路 + `habit-ok` 只写 checks）。改为逐次撤销一条；`verify-quit-checkin` 15→21 项新增多次模式用例 | 会话：戒除失守撤销修复 |
| 2026-11-27 | v207 | 14 | 新增 `docs/通知路由方案汇总.md`（三渠道现状、11 类功能推送文案、缺口与建议）与 `docs/通知路由管理预览.html`（离线交互预览）；`e2e/check-doc-anchors.py` 的文档清单同步登记。纯文档，未动代码 | 会话：通知路由方案汇总 |
| 2026-11-27 | v207 | 14 | 汇总文档补功能→类目映射与三级优先级排序；新增 `docs/通知路由示例数据.json`（32 条 / 12 功能）；预览页接入数据筛选排序、点击载入解析与戒除对照项。纯文档，未动代码 | 会话：通知分类与示例数据 |
| 2026-11-27 | v207 | 14 | 预览页新增通知渠道总控（全局总开关 + 三渠道独立开关 / 多选 + 全开全关），拦截结果接入路由解析；汇总文档补第 8.7 节说明落地缺口。纯文档，未动代码 | 会话：渠道总控预览 |
| 2026-11-27 | v207 | 14 | 汇总文档新增第 9 节「实例级 / 模块级落地审计」：逐层完成度、按功能覆盖矩阵、P0/P1 问题清单与整改顺序（原第 9 节顺延为第 10 节）。只读审计结论落文档，未动产品代码 | 会话：通知路由落地审计 |
| 2026-11-27 | v207 | 14 | 预览页渠道总控复刻运动弹窗的配置检测：三渠道状态点 + 逐条检测反馈 + 模拟配置开关 + 选中高亮/未选中灰暗，检测结果参与路由拦截；汇总文档补配置检测落地语义。纯文档，未动产品代码 | 会话：渠道配置检测预览 |
| 2026-11-27 | v208 | 14 | 预览页新增文案模板编辑器（按场景改标题 / 正文 / 浏览器文案 + 中文变量插入 + 恢复默认）与邮件 HTML 卡片预览（纯文本 / 卡片切换、主题色、页脚、内联样式源码）；汇总文档补第 10.1 节与产品落地缺口。纯文档，未动产品代码 | 会话：文案模板与邮件卡片预览 |
| 2026-11-27 | v208 | 14 | 汇总文档新增第 11 节「模块启用 / 停用与通知路由合并方案」（单一板块数据源、存储方案 A/B、免打扰时间段、小结时刻、判定顺序）；预览页接入 11 板块总控、全局免打扰时段与每日小结时刻，拦截接入路由解析。纯文档，未动产品代码 | 会话：模块与通知路由合并 |
| 2026-11-27 | v208 | 14 | 预览页文案模板编辑器新增「变量取值」列表：九个变量跟随场景 / 数据项显示真实内容、可直接改并按项或场景分别保存、未引用变量给提示；汇总文档第 10 节与 10.1 节同步说明。纯文档，未动产品代码 | 会话：变量取值随场景联动 |
| 2026-11-27 | v208 | 14 | 按陛下确认，变量取值区改为只读展示：移除九个输入框 / 文本域与变量编辑、保存、恢复逻辑，保留跟随场景与数据项切换；汇总文档第 10 节与 10.1 节同步改为“只读不可改”。纯文档，未动产品代码 | 会话：变量取值改只读 |
| 2026-11-27 | v208 | 14 | 模板编辑器布局优化：变量取值从右侧整列移到编辑框下方、压成横向紧凑卡片；右侧改为「实时通知预览」（新增预览页渲染函数，与解析结果共用同一份文案数据）；编辑框高度收紧。汇总文档第 10、10.1 节同步。纯文档，未动产品代码 | 会话：编辑器布局优化 |
| 2026-11-27 | v208 | 14 | 新增 `docs/通知字段落地改动清单.md`：把预览 9 变量逐项映射到真实落点（补 source + priority）、后端 13 个排程产出点 / 模板层 / multipart / 接口、独立导航页 8 处挂载、浏览器通知渲染、测试与发布清单、7 条风险。陛下已定：先清单确认后动代码；管理页独立导航页。登记进 `check-doc-anchors.py` 的 DOCS + PLAN_DOCS。纯文档，未动产品代码 | 会话：通知字段落地清单 |
| 2026-11-27 | v209 | 14 | 板块总控接入 v209 功能模块开关：预览页新增「功能模块开关 · 同步源」（五开关，默认对齐实测截图 1/5 仅戒烟），模块类板块（用药/喝水/运动/478/戒烟）的启用列改为派生值——读 `modOn`（对齐 `isModuleOn()`），点击走 `setModuleOn()` 同语义，停用行置灰 + 渠道锁定 + 路由判定拦截；批量启用/停用按钮限定基础板块。汇总文档补 11.8 节、改动清单 3.3 / 第 4 节同步（notifyBoards 模块板块只存渠道不存启用）。纯文档，未动产品代码 | 会话：功能模块与路由同步 |
| 2026-11-27 | v209 | 14 | 新增 `docs/通知路由落地执行方案.md`（交另一会话执行的落地工单）：需求确认表、目标页面五板块（页面 key `notifyroute` 进 NAV 设置组）、阶段 1~8 依赖链（排程补 source/priority → 偏好表扩 11 板块（方案 B，陛下拍板）→ 模板层/邮件卡片 → 发送判定接线 → 前端页与真实数据列表 → e2e → 文档对比页 → 发版）、测试清单、13 条防坑铁律。登记 `check-doc-anchors.py` DOCS+PLAN_DOCS。纯文档，未动产品代码 | 会话：通知路由落地工单 |
| 2026-11-27 | v211 | 9.4 | 批 A 落地：13 个排程产出点补 `source`/`priority` 与附加字段（任务 tag/taskPriority、习惯 habitType、运动 sport、还款 due），只增不改；`push_preview` 对齐五源并透传字段、小结时刻读用户设置；顺手修 `lb_water_slots` 正则缺捕获组导致喝水提醒分钟被截成整点（warning 同步消失）。`test-schedule.php` 143→154（新增 11 条），`test-ics.php` 76、`test-push.php` 28、`test-push-tick.php` 44、`test-notify-channel.php` 27、`regression-v3` 28 全绿 | 会话：通知路由落地批 A |
| 2026-11-27 | v211 | 9.4 | 批 B 后端：`notify_prefs` 扩成 11 板块 × 3 渠道（`{"boards":{...}}`，模块五板块不存 on，旧 7 类扁平读取时原地迁移且 habit 渠道继承给 water/move/breathe）；免打扰扩成 `{on,start,end}`（旧布尔兼容）；新增文案模板 `notify_tpl_<uid>`（11 场景 + 邮件配色页脚）与 `lb_notify_text_render`；tick 接板块闸门 + 模板渲染；`api.php` 的 `notify_prefs` 旧字段保持、新增 boards/quietCfg/templates，新增 `notify_templates_save`。`test-notify-prefs.php` 38→74（新增 11 板块/迁移/时段/模板/闸门接线）。**旧 v210 页面完全兼容（prefs 仍为 7 类、quiet 仍为布尔）**；邮件 multipart + `lb_notify_mail_card` 已落地（`test-mailer.php` 44→49，4 项失败是本地缺 openssl，基线同样失败） | 会话：通知路由落地批 B |
| 2026-11-27 | v211 | 9.4 / 5（导航） | 批 C 前端：新增「通知路由」页（`viewNotifyRoute`，NAV 设置组、移动端更多抽屉、VIEWS 三处挂载）；四块内容——全局总控 / 板块总控（模块派生 + 11 板块渠道 + 免打扰 + 小结时刻）/ 文案模板（场景切换 + 实时预览 + 保存）/ 用户通知数据列表（`push_preview` 真实排程 + `remindItems` 本地提醒合并，标「会发送 / 板块停用 / 免打扰 / 本地」）；配置页移除通知矩阵与今日推送计划（`viewConfig` 不再调 `notifyMatrixHtml`，`pushBoxHtml` 删 pc-sec）；浏览器通知 `notifyPing` 套模板。测试：新增 `verify-notify-route.py` 23 项、`regression-v3` 30 项（含新页）、`verify-v15` 35、`verify-nav-order` 17、`verify-mobile-nav` 44；`verify-notify-matrix.py` 随旧 UI 退役删除。SW → v211，包已生成 | 会话：通知路由落地批 C |
| 2026-11-27 | v212 | 9.4 | 批 C 收尾（P0+P1）：①新增全局通知总闸 `notify_global_<uid>`（默认开，tick 最前跳过）；②浏览器渠道真正被消费——`notifyPing` 按板块 `channels.browser` 过滤，通知先于页面访问时懒加载配置；③数据列表状态补「总开关关闭 / 渠道留空 / 本地渠道停用」；④全局总控加总开关与快捷动作（企微暂停、邮件去配、浏览器开启通知）；⑤模板区补齐：变量取值表（真实值）、点变量插入光标、邮件样式（纯文本/HTML + 4 主题色 + 页脚）、邮件卡片预览与 HTML 源码、恢复全部默认；⑥模板保存改为基于已存值（部分更新不再重置其他字段），后端支持 `mail.mode`；⑦开关/勾选/胶囊改用 `--good` 绿（红会被读成停用）。测试：`test-notify-prefs.php` 74→81、`verify-notify-route.py` 23→31、`regression-v3` 30、`test-mailer.php` 45/49（缺 openssl 4 项基线同样）。SW → v212，包已生成未上传 | 会话：通知路由落地 P0+P1 |
| 2026-11-27 | v213 | 9.4 / 5（导航） / 12（测试） | P2 清理：①删除旧通知矩阵全部死代码——`notifyLoad` / `notifySummary` / `notifyMatrixHtml` / `notifySyncSummary` / `notifySave` 五个函数（140 行）、`notifyPrefs` / `notifyMeta` / `notifyLoading` / `notifyQuiet` / `notifyReport` 五个模块级变量、`bindView` 的 `.mx-table` 绑定、`ACTIONS['notify-save']`、`assets/app.css` 里 24 条 `.mx-*`；②`verify-push-ui.py` 对齐当前 UI 重写流程（未配置时只有「保存」、保存后才出现「发一条测试」；空地址点保存弹「清空即停用」确认）并修正导航设置页→配置页、`.ics-hint` 取到了别的面板共 3 处历史漂移，40/40 通过；③文档清债：根 README 三处「今日推送计划」改指「通知路由」页、`BACKEND.md` 的 `push_preview` 改「五源合并」、`FRONTEND.md` 视图表补 `modules` / `notifyroute` 两行、`HANDOFF.md` 测试现状数字全部按实测更新、`通知路由方案汇总.md` 文首加「实现状态（v212）」并标注第 5 条已修。测试：`verify-push-ui` 40、`verify-notify-route` 31、`regression-v3` 30、`verify-v15` 35、`verify-nav-order` 17、`verify-mobile-nav` 44、`verify-batch2~4` 51/60/20、`verify-money-v92` 23、`verify-api-http` 33、对比度 0 项违规。SW → v213，包已重新生成未上传 | 会话：通知路由 P2 清债 |
| 2026-11-27 | v215 | 9.4 | 数据列表对齐设计稿（**版本顺延**：并行会话已占 v214 修「戒除类习惯」当天有失守时「完成」无法撤销的问题，本会话从 v214 顺延到 v215）：`notifyRoutePlanHtml` 由单行列表改为**卡片网格**——顶部四筛选（通知类目 / 优先级 / 状态 / 排序）+ 统计行 + 「清除数据项选择」；按排序方式出分组条（优先级 / 类目 / 时间不分组）；卡片为「优先级徽标 + 类目徽标 + 时间 + 状态徽标 / 标题 / 正文 / 功能·来源·id」四行，本地提醒显示「手动」，网格 4 列、max-height 452 滚动。新增 `NOTIFY_KIND_CN` / `NOTIFY_SRC_CN` / `NOTIFY_PRI_RANK`、`notifyPlanFiltered` / `notifyPriClass` / `notifyPlanCardsHtml` / `renderNotifyPlanList` / `notifyLocalKind`；筛选与选中用模块级 `nrFilter` / `nrActiveItem`（不进 state），只重绘网格不整页 render（保下拉焦点）；点卡片把该条真实内容套进模板预览，再点或「清除数据项选择」取消。本地提醒的 kind 归到 habit、细分放 source（类目显示「习惯提醒」、功能显示「喝水」）。CSS 删旧 `.nr-prow` 一套换 `.nr-toolbar` / `.nr-grid` / `.nr-card` / `.nr-badge` / `.nr-group`。测试：`verify-notify-route.py` 31→45（新增卡片字段、四筛选、三排序、选中/清除、统计行）；`regression-v3` 30、`verify-v15` 35、`verify-push-ui` 40 全绿。SW → v215，包已生成未上传 | 会话：数据列表对齐设计稿 |

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
