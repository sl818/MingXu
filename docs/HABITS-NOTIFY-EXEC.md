# 小习惯 2.0 新提醒 · 执行方案（工单）

> 2026-11-28 定稿 · 基线 **v221**（ca1ff1e）· 需求与口径全部经陛下确认，
> 背景与裁决见 `docs/HABITS-NOTIFY-SPEC.md`（冲突时以本文为准）。
> 铁律：**一切通知必须并入通知路由**（CHANGE-MAP 通用铁律），PHP 改动与前端同批上传。

---

## 0. 开工检查（不做完不许动代码）

1. `git log -3` 查并行提交；基线漂移则版本号顺延并以函数名为锚重新定位（本文不给行号）。
2. 解释器：Python `~/.workbuddy/binaries/python/envs/default/Scripts/python`；
   PHP `/tmp/php82/php.exe`（SQLite 加 `-d extension_dir=/tmp/php82/ext -d extension=pdo_sqlite`）；
   浏览器 `channel='chrome'`。测试账号 `test@sl00.top`（登录即踢会话，用完 logout）。
3. 测试账号里已有 4 个 2.0 虚拟习惯（健身2.0/冥想2.0/浇花2.0/读书2.0），可复用，不许删。
4. 通知相关改动**必须同批跑**：`test-ics.php` / `test-schedule.php` / `test-push.php` /
   `test-push-tick.php` / `verify-notify-route.py` + `verify-habit-sched.py`(16) + `regression-v3`。

## 1. 需求确认表（陛下原话 → 验收）

| # | 原话要点 | 验收 |
| --- | --- | --- |
| 1 | 渠道选择不支持 | 习惯表单有渠道三开关（企微/邮件/浏览器），未配置渠道红点提示并参与发送拦截 |
| 2 | 每日单次要有单次提醒时间+频率 | 每天×单次：单时间每日推送 |
| 3 | 每日多次要有 N 个提醒时间；且 5 次目标点 1 次就完成 | 每天×多次：N 个时间行（纯提醒，不做打卡截止节点）；BUG-① 修复 |
| 4 | 删「每日单次 · 点了就是破了」选项 | 戒除 slipMode 只剩每日多次（单次是唯一默认语义） |
| 5 | 每周选天的单次按所选星期推送 | weekdays：每个选中日按其时间推送；旧「每周几」单选下拉退役（只管节奏不再管提醒） |
| 6 | 每周选天的多次：每选中日各配各的时间 | weekdays：选中日 × 当日次数 → 时间矩阵（如周一 3 个时间、周三 2 个时间） |
| 7 | 每周 N 次不单独通知；weekly×当日多次不进戒除 | weekly 弹性型不产生排程项，只进每日日报与「还有任务未完成」；表单禁 weekly×quit |
| 8 | 每隔 N 天单次/多次不支持戒除 | 表单禁 interval×quit |
| 9 | 每隔 N 天点完成卡片消失；要始终显示、当天可撤销、非本轮日禁用按钮显示「未到打卡时间」；新增每轮通知一次 | BUG-② 修复 + interval 排程 |

## 2. 批次划分

### 批 1 · BUG 定位与修复（先定位后修，禁止盲改）
- **BUG-①**：写复现测试——造 target=5 的保持类与戒除类各一，点 1 次打卡，
  分别检查 `checks` 存储、`met()` 读取。定位两种假设：
  a) 戒除类：`saveHabitForm` 的 `target: type==='quit' ? 1 : ...` 强制（v204 遗留）——若复现，
     该强制改为「保持 1（戒除默认）但用户可改多目标」；
  b) 保持类：怀疑编辑弹窗保存时 target 被重置。若 b) 复现，修 `Object.assign` 覆盖前的表单初值。
- **BUG-②**：`todayVisible` 加 interval 分支——`intervalDone(h,d)` 为真时恒显示；
  `habitDueOn` 为假时卡片按钮禁用并显示「未到打卡时间」。
- 验收：两个复现测试转正为断言（并入 `verify-habit-sched.py`）。

### 批 2 · 数据结构（三处同步铁律）
习惯级新增（**不新增 state 顶层字段**，习惯对象内）：

```
h.notifyPlan = {
  channels: ['wecom','mail','browser'],  // 习惯级渠道（发送时与板块矩阵取交集）
  daily:    ['07:00','12:00'],           // daily 多次的 N 个时间（单次为 1 元素）
  wd:       { '1': ['07:00','12:00','19:00'], '3': [...] },  // weekdays：真实周序 0-6 → 当日时间数组
  intervalTime: '09:00'                  // interval 本轮要求日通知时间
}
```

- `normalizeState`：结构校验（时间格式、周序 0-6、去重排序）；无此键不写，老数据零迁移。
- `repairBackup`：同上校验，非法归一。
- `mergeStates`：habits 已按 `updatedAt` 整体胜出，无需改。
- 缺省回落：`daily:['07:00']`、`wd` 按 sched.days 生成 `['07:00']`×N、`intervalTime:'09:00'`。

### 批 3 · 排程生成（api/schedule.php 习惯段重写，锚：`---- 习惯` 注释段）
现状（必须改掉的三点）：`suggestTime` 单时间；`notifyFreq` 过滤；**198 行 quit 直接 continue**。
新逻辑：

1. 保留归档/optional/med/模块锚/notify=false 的跳过；
2. **删除 quit 的 continue**（改为按 notifyPlan 排，quit 无 notifyPlan 才跳过）；
3. 按 `h.sched` 判定今天是否要求（前端 `schedDueRaw` 同口径，PHP 重写同逻辑）：
   daily → 是；weekdays → `days` 含 `date('w')`；weekly → **跳过（不排程）**；
   interval → 本轮未完成（按 anchor 分轮，同前端 `intervalDone`）；
4. 要求日 → 取当日时间数组：daily 取 `notifyPlan.daily`；weekdays 取 `wd[date('w')]`；
   interval 取 `intervalTime`；**每个时间一条排程项**（kind=habit, source=habit）；
5. 已完成过滤从「打过卡就跳过」改为「当日已完成次数 ≥ 当日应完成次数才跳过」（多次型做 1/3 仍要催 2、3 次）；
6. 文案：多次型 body 写「今天还差 X 次」，单次维持原文案。

### 批 4 · 三链路接线
1. **企微/邮件 cron**（`api/push.php` 发送判定处）：板块渠道（habit 行）∩ `notifyPlan.channels`
   取交集，交集空则该习惯本条不发；免打扰时段沿用；
2. **浏览器本地**（index.html `remindItems`）：按同一时间矩阵生成今日本地提醒，套 habit 模板；
3. **ICS**（`buildICS` / `api/ics.php` / `api/schedule.php` 三处一致铁律）：时间矩阵 → 多 VEVENT，
   SUMMARY 用 habit 模板标题，RRULE 跟 sched。

### 批 5 · 表单重构（habitModal + saveHabitForm）
1. 「多久一次」选中后动态渲染「提醒设置」区：
   daily 单次 1 行 / daily 多次 N 行（N=target）/ weekdays 每选中日一组（行数=当日次数）/
   weekly 显示说明文案（不做单独提醒）/ interval 1 行；
2. 渠道三开关 + 配置检测（复用通知路由页的全局检测数据）；
3. 约束矩阵：`type=quit` 时 weekly、interval 两张节奏卡置灰禁选；slipMode 删「每日单次」选项；
4. `saveHabitForm`：收集 notifyPlan + `updatedAt`；**修 BUG-① 的 target 链路**。

### 批 6 · 测试与发布
- 新脚本 `e2e/verify-habit-notify.py`：矩阵排程生成（ weekdays 不同日不同时间）、
  quit 解禁与约束、渠道交集拦截、多次型催促口径、免打扰；
- 全量：五个通知测试 + `verify-habit-sched`(16) + `regression-v3` + 戒除 21；
- 版本顺延；**PHP 与前端同批上传**；对比页（通知前后）按惯例出一份。

## 3. 函数锚清单（以函数名为准，行号会漂）

| 文件 | 函数/段 | 动作 |
| --- | --- | --- |
| index.html | `todayVisible` | interval 恒显 + 禁用态（BUG-②） |
| index.html | `saveHabitForm` | target 链路修复 + notifyPlan 收集 |
| index.html | `habitModal` | 提醒设置区动态渲染 + 渠道开关 + 约束置灰 |
| index.html | `remindItems` | 浏览器本地提醒按矩阵生成 |
| index.html | `buildICS` | 多 VEVENT |
| api/schedule.php | `---- 习惯` 段 | 重写排程生成（quit 解禁、矩阵、多次催促） |
| api/push.php | 发送判定 | 板块渠道 ∩ 习惯渠道 |
| api/ics.php | 与前端三处一致 | 同步矩阵 |

## 4. 风险与回滚

- schedule.php 改写涉及所有习惯的提醒——批 3 完成必须先跑 `test-schedule.php` 快照对比；
- quit 解禁会让戒除类突然开始收到提醒：上线说明里要写（或默认 notify=false 让用户自己开，
  **待陛下拍板**：解禁后戒除类默认提醒开还是关）；
- 回滚点：`git tag` 每批一个，PHP 回滚直接恢复旧文件即可（无 DB 迁移，notifyPlan 是习惯对象内字段）。
