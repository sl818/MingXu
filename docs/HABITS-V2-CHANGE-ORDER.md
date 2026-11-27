# 习惯 2.0 · 可执行改动单

> 基线：**v205**（2026-11-27）。本文是 `HABITS-UPGRADE-GUIDE.md` 的执行细化版，两者冲突以本文为准。
> 拍板前提见 §0。读完 §1 再决定要不要照 §3 动手。

---

## 0. 本次拍板结论

| # | 决策 | 落地影响 |
|---|---|---|
| Q1 | 固定选日（周一三五）**和**弹性配额（每周完成 3 天）**都要** | P0 必须同时做 `weekdays` 与 `weekly` 两种节奏 |
| Q2 | 周期型不计入今日完成率，单列「本周节奏」 | `dayStats` 分母不变；新增独立指标 |
| Q3 | 周一为一周起点 | 统一用现有 `weekMonday` |
| Q4 | 改节奏不回算历史 | 保存时提示一次；历史按旧规则保留展示 |

---

## 1. 先回答两个架构问题

### 1.1 要不要给习惯单独建 SQL 表：**不建**

**结论：不建，且不建议在任何阶段建。**

| 理由 | 说明 |
|---|---|
| 与存储架构根本冲突 | 全站是**全量快照**：`boards.data` 一列存整份 `state` JSON，靠 `base_rev` 乐观锁 + `mergeStates` 内存合并。习惯是 JSON 里的一个数组。拆表等于把「原子提交 + 整份合并」换成「多表事务 + 字段级合并」 |
| 会连带重写后端全部 | 拆表要同时处理：打卡与待办同事务、多端并发合并、备份恢复、导出导入、历史版本回滚（现在是一键 JSON 快照） |
| 数据量根本不需要 | 单人使用，习惯记录实际量级在千条以下，SQLite/MySQL 表级索引带来的收益接近 0 |
| **解决不了你说的痛点** | 你的痛点是「改一个函数牵扯全站」，那是**前端判定散落**的问题，不是存储问题。建表之后 `met()` 仍然被 31 处调用，问题原样存在 |

**唯一值得建表的情形**（现在都不成立）：

1. 出现多用户共享同一习惯（如家庭共用）；
2. 单份 `state` 超过 2MB，快照读写成为瓶颈；
3. 需要按习惯维度做跨用户统计。

真到那天再做「读时投影」：从快照里抽出习惯写入只读表，写仍走快照——**不要做双向同步**。

### 1.2 要不要推倒重写：**不推倒，用绞杀者模式**

先看现在的耦合度（v205 实测）：

| 符号 | 引用次数 | 谁在用 |
|---|---|---|
| `met` | 31 | 日历、统计、月报、连续、横幅、卡片 |
| `dayStats` | 11 | 今日页、日历、统计 |
| `streakOn` | 9 | 卡片、连续、月报 |
| `assessmentHabits` | 7 | 今日页、日历、统计、横幅 |
| `habitDueOn` | 2 | 月报、应打卡 |

「旧调用全部重新写」意味着一次改 31 个调用点 + 6 套回归脚本一起动。**一旦有偏差，回滚成本极高**，而且这类偏差是静默错数，不一定被测试抓到。

**替代方案：三层接缝 + 适配器过渡。** 这是把「重写」拆成「可回滚的替换」：

```
第 1 层 数据接缝   新增 h.sched，缺省等价 daily → 老数据零迁移
第 2 层 判定接缝   HabitEngine 命名空间，内部实现、对外只出 10 个函数
第 3 层 展示接缝   卡片/周条/徽标只读引擎输出，不再自己算
```

关键在于过渡手法：

> 先让 `met()` / `habitDueOn()` / `habitDayMark()` **转调引擎**，行为与现在**逐字节等价**（全量回归必须全绿，UI 零改动）；
> 确认等价后再逐个把调用点迁到引擎 API；
> 最后删掉转调壳。

这样任何一步出问题都能单独回滚，且每一步都有测试兜底。

### 1.3 顺手修一处「后端早就写对了」

`api/schedule.php` 的注释原文：

> 通知频率：daily 每天；weekly 只在 notifyWeekday；monthly 只在 notifyMonthday。
> **打卡仍是每天，这里只决定「今天要不要提醒」。**

也就是说：**后端一直把 `notifyFreq` 当提醒频率，语义是对的；是前端 `habitDueOn` 把它借来当应打卡频率。**

所以这次拆开**不需要改后端任何一行**（`schedule.php` / `ics.php` 零改动），风险面比预想小。

---

## 2. 目标模型（定稿）

### 2.1 新增字段

```js
h.sched = {
  kind: 'daily' | 'weekdays' | 'weekly',
  days: [1, 3, 5],     // weekdays 用；0=周日 … 6=周六
  perWeek: 3,          // weekly 用；1..7
  startDate: ''        // 可选：从哪天起生效，空=创建日
}
h.updatedAt = 0        // 毫秒时间戳，供 mergeStates 判断谁更新
```

规则：

- `kind` 缺失/非法 → `'daily'`，行为与现在完全一致；
- `weekdays` 的 `days` 去重升序，空数组回落 `[1,3,5]` 并在表单拦截空选；
- `weekly` 的 `perWeek` 限 1..7；
- `interval`（每 N 天）不在本次范围，字段留白即可（`kind` 白名单先不含它）。

### 2.2 判定分层

| 函数 | 回答什么 | 改动 |
|---|---|---|
| `HabitEngine.schedOf(h)` | 归一化节奏 | 新增 |
| `HabitEngine.isPeriodic(h)` | 是否周期型（weekly） | 新增 |
| `HabitEngine.dueOn(h, d)` | 今天该不该做 | 新增，替代 `habitDueOn` 的日常分支 |
| `HabitEngine.stateOf(h, d)` | `todo / done / off / none` 四态 | 新增，解决「已达成但未消失」 |
| `HabitEngine.met(h, d)` | 日粒度是否达标 | 新增，内部保留 `met` 前四分支 |
| `HabitEngine.periodOf(h, d)` | 本周期 `{key, start, end, daysLeft}` | 新增 |
| `HabitEngine.periodStats(h, d)` | `{done, target, met, ratio}` | 新增 |
| `HabitEngine.mark(h, ds, today)` | 周条单格状态 | 扩展 `habitDayMark` 的 `off` 态 |
| `HabitEngine.streak(h, d)` | `{n, unit}`，单位随节奏 | 新增 |
| `HabitEngine.label(h)` | `{pace, counter, badge}` 展示文案 | 新增 |

**四态的意义**：`dueOn` 只能回答「要不要做」，回答不了「做完了但还该不该占位」。`weekly` 达成后必须显示「已完成」而不是从待办消失——否则用户会以为记录丢了。

### 2.3 判定伪代码

```
schedOf(h):  h.sched?.kind 合法 ? h.sched : {kind:'daily'}

weekKey(d):  周一为界的 YYYY-Www（复用 weekMonday）

dueOn(h, d):
  if (!活跃(h, d)) return false              // 归档 / 未创建 / 暂停
  s = schedOf(h)
  if (s.kind === 'weekdays') return s.days.includes(dow(d))
  if (s.kind === 'weekly')   return periodStats(h, d).done < s.perWeek
  return true                                // daily

periodStats(h, d):                            // 仅 weekly 有意义
  days = 本自然周 7 天
  done = days.filter(ds => mark(h, ds, d) === 'done').length
  return { done, target: s.perWeek, met: done >= s.perWeek, daysLeft: 7 - 已过天数 }

mark(h, ds, today):
  if (ds > today) return 'future'
  ...现有 habitDayMark 的前四分支（med/smoke/quit）...
  if (!dueOnLike(h, ds)) return 'off'         // 不需要做（weekdays 非命中日）
  done ? 'done' : (有记录 ? 'part' : 'none')
```

注意 `if (!dueOnLike(...))` 必须用**「该日是否被要求」**的纯函数版本，**不能**调 `dueOn`（后者对 `weekly` 含「是否已达成」的动态判断，判定历史日会失真）。

### 2.4 指标

| 指标 | 定义 | 位置 |
|---|---|---|
| `dayStats(d)` | **不变**：`assessmentHabits` 中**日型**习惯的达标比 | 今日页、日历、统计 |
| `weekPace(d)` | 周期型：已达成数 ÷ 周期型总数 | 今日页新增一块 |

`assessmentHabits` 保持现状（含四模块）。周期型习惯**不进入** `dayStats` 的分子分母，只是不从 `dayStats` 里取数。

### 2.5 展示映射

| 位置 | daily | weekdays | weekly |
|---|---|---|---|
| pace | `每天` | `周一/三/五` | `每周 3 次` |
| 计数位 | `本周 x/7` | `本周 x/3`（N=选中天数） | `本周 x/3 · 还差 M` |
| 周条非要求日 | 正常空圈 | `off` 淡态 + 斜纹 | 正常空圈 |
| 连续单位 | 天 | 天（只算选中日） | **周** |
| 列表徽标 | `每天` | `周一三五` | `每周 3 次` |

---

## 3. 分批改动单

每批独立可验收、可回滚（建议每批打 tag）。**不要合并批次**。

### B0 基线（动手前必做）

| 步骤 | 内容 |
|---|---|
| B0-1 | `git tag habit-v2-base`，记录当前 HEAD |
| B0-2 | 跑一遍 `regression-v3` / `verify-v15` / `verify-batch2` / `verify-batch3` / `verify-batch4` / `verify-habit-month` / `verify-quit-checkin` / `test-merge.mjs`，**把当前失败项记下来**（已有失败不能被后续误判为新增） |
| B0-3 | 截图今日页与习惯页（明暗各一张），作为视觉回归基准 |

### B1 数据层

| # | 位置 | 改动 | 验证 |
|---|---|---|---|
| B1-1 | `normalizeState` 的 habits 段 | 加 `sched` 清洗（`kind` 白名单、`days` 去重升序、`perWeek` 夹取）；缺省写 `{kind:'daily'}`；加 `updatedAt` 默认 0 | `verify-import-keep` |
| B1-2 | `repairBackup` 的 habits 段 | 加 `sched` 结构校验（非法值丢弃而非抛错，`Object.assign` 已保留字段） | 同上 |
| B1-3 | `mergeStates` 的 habits 分支 | 加 `updatedAt` 比较：本地更新则整体用本地（`archivedAt` 仍取非空）。**不加这一条，改节奏会被另一端旧快照静默覆盖** | `test-merge.mjs` |
| B1-4 | `saveHabitForm` | 写入 `sched` 与 `updatedAt: Date.now()` | 手动 |

**验收**：老数据导入后 `sched` 全部为 `daily`，今日页与截图基准**逐像素无差异**。

### B2 引擎骨架（行为等价，零 UI 改动）

| # | 内容 |
|---|---|
| B2-1 | 新增 `HabitEngine`（IIFE 命名空间，约 200 行），实现 §2.2 的 10 个函数；`met` 前四分支**原样搬进**引擎内部 |
| B2-2 | 把 `habitDueOn` 改成 `return HabitEngine.dueOn(h, d)`（此时引擎内部仍按 `notifyFreq` 判定，**故意保持旧行为**） |
| B2-3 | 把 `habitDayMark` 改成转调 `HabitEngine.mark`（不含 `off`） |
| B2-4 | 把 `met` 改成「前四分支原样 + 其余转调引擎」 |

**验收（关键）**：全量回归结果与 B0-2 基线**逐项一致**，UI 零差异。这一步不做任何行为改变，只是把逻辑搬进接缝。

### B3 判定切到 `sched`（仍只支持 daily）

| # | 内容 |
|---|---|
| B3-1 | 引擎内部 `dueOn` 改为读 `sched`（`kind==='daily'` 时返回 true，与旧行为一致） |
| B3-2 | `notifyFreq` 从此只出现在提醒链路，判定链不再引用 |

**验收**：回归仍全绿（因为所有数据都是 `daily`）。这一步的价值是**切断了耦合点**，为 B4/B5 铺路。

### B4 固定周几（`weekdays`）

| # | 位置 | 改动 |
|---|---|---|
| B4-1 | `HabitEngine.dueOn` | 加 `weekdays` 分支：`days.includes(dow)` |
| B4-2 | `HabitEngine.mark` | 加 `off` 态：非命中日返回 `off` |
| B4-3 | `habitWeekLabelled` | 渲染 `off`（淡态 + 斜纹），`title` 写「今天不需要做」 |
| B4-4 | `habitCardV2` 的 pace / 计数位 | 按 `sched` 生成；分母用 `days.length` |
| B4-5 | `habitManageRows` | 徽标 `周一三五` |
| B4-6 | `habitModal` | 加「多久一次」四张卡片中的前两张（每天 / 每周固定几天 + 星期多选） |

**验收**：新增 `verify-habit-sched.py` 至少 20 项，覆盖：非命中日不进待办、周条 `off` 态、分母为 N、连续只算命中日。

### B5 弹性配额（`weekly`）+ 新指标

| # | 位置 | 改动 |
|---|---|---|
| B5-1 | `HabitEngine.periodOf` / `periodStats` | 按 `weekMonday` 切周，统计 `done` |
| B5-2 | `HabitEngine.dueOn` | `weekly` 未达成 → true；已达成 → false |
| B5-3 | `HabitEngine.stateOf` | 已达成但当日无记录 → `done`（进折叠区，不从界面消失） |
| B5-4 | `habitCardV2` | 计数位 `本周 x/3 · 还差 M`；已达成显示 `本周已达成` |
| B5-5 | 今日页 | 新增「本周节奏」块：`weekPace(d)` = 周期型达成数 / 总数 |
| B5-6 | `HabitEngine.streak` | 周期型按「连续达成周数」，单位「周」 |
| B5-7 | `habitModal` | 加「每周 N 次」卡片 + N 输入 |

**验收**：`verify-habit-sched` 扩到 30 项，覆盖「1/3 → 2/3 → 3/3 进入已完成」「跨周清零」「连续周数」。

### B6 展示收尾

| # | 位置 | 改动 |
|---|---|---|
| B6-1 | `habitMonthOverview` / `habitMonthRow` | **只统计日型**（daily + weekdays 命中）；周期型另起一行「本周/本月周期达成 x/y」 |
| B6-2 | `habitCardV2` 的 sub 行 | 周期型不显示 pips 与「本周 x/7」混排 |
| B6-3 | 习惯页排序 | 达成率排序排除周期型，避免「每周 1 次」永远垫底 |

**验收**：三处数字一致（卡片 / 周条 / 月报），明暗两态截图与基准对比，只有预期差异。

### B7 表单与文案

| # | 内容 |
|---|---|
| B7-1 | 「通知频率」标签改「提醒频率」，下加一行说明：「只影响什么时候提醒，不影响怎么算达标」 |
| B7-2 | `sched` 变更时二次确认：「修改只影响本周及以后，历史按原规则保留」 |
| B7-3 | 空选星期 / `perWeek` 越界的前端拦截 |

### B8 清理与发布

| # | 内容 |
|---|---|
| B8-1 | 删除 `habitDueOn` 里的 `notifyFreq` 分支（若已被引擎取代则整个函数变薄壳） |
| B8-2 | 删除 B2 阶段的转调壳，调用点全部改调 `HabitEngine.*` |
| B8-3 | `service-worker.js` 推进 `CACHE` / `VER`；`?v=` 与 `APP_VERSION` 四处同步 |
| B8-4 | 更新 `CHANGE-MAP.md` §1 与 `design/SITE-STRUCTURE.md`（若页面结构有变）；日志补一行 |
| B8-5 | 新增 `verify-habit-sched.py` 纳入回归清单 |

---

## 4. 不变式清单（改到就停手）

| # | 不许碰 | 原因 |
|---|---|---|
| 1 | `met()` 的四个前置分支（med / h_move / smoke / quit） | 四模块与用药的达标语义，改动会污染模块 |
| 2 | `state.modules` / `moduleAsHabit` / `isModuleAnchor` | 模块化边界，动了就是两套真相 |
| 3 | `api/schedule.php` / `api/ics.php` | 后端语义本来就对，`notifyFreq` 在那只决定提醒 |
| 4 | `dayStats` 的分母定义 | 日历、横幅、统计三处共用，改了会连带 |
| 5 | `habitDayMark` 作为唯一判定出口 | v143 修过的「一张卡讲两套话」 |
| 6 | 提醒三处（`buildICS` / `ics.php` / `schedule.php`）的日期口径 | 已有测试锁定 |

---

## 5. 验收矩阵

| 层级 | 检查 | 通过标准 |
|---|---|---|
| 数据 | 老数据导入 | 全部 `daily`，行为与基准一致 |
| 数据 | 多端改节奏 | 后改的生效，不被旧快照回退 |
| 判定 | `weekdays` 非命中日 | 不进待办、周条 `off`、分母为 N |
| 判定 | `weekly` 1/3 → 3/3 | 达标后进「已完成」而非消失 |
| 判定 | 跨周 | 周一 00:00 清零，连续周数 +1 或归零 |
| 展示 | 三处一致 | 卡片 / 周条 / 月报数字相同 |
| 展示 | 单位 | 不出现「连续 N 天」配周期型 |
| 回归 | 四模块与用药 | 与 B0 基线一致 |
| 性能 | 200 习惯首屏 | ≤ 300ms（周期计算不得全量扫史） |

---

## 6. 风险与止损

| 风险 | 触发信号 | 止损动作 |
|---|---|---|
| 周期型污染 `dayStats` | 今日完成率无故变化 | 回滚 B5，检查是否漏了「不计入」 |
| 一张卡两套话 | 徽标说已完成、周条是空圈 | 全部改读 `HabitEngine.mark` |
| 四处 7 天漏改 | 「本周 3/7」出现在 weeks 型卡片 | 按 §2.5 逐格核，补断言 |
| 改节奏被覆盖 | 另一端刷新后节奏回退 | 检查 B1-3 的 `updatedAt` 比较 |
| 范围蔓延 | 有人提「加个时段」 | 明确回复：模块层已有，习惯层不做 |

---

## 7. 工作量与顺序

| 批次 | 改动点 | 相对工作量 |
|---|---|---|
| B0 | 0（只跑测试） | 半天 |
| B1 | 4 | 小 |
| B2 | 4（新建引擎） | **最大**，约占总量的 40% |
| B3 | 2 | 小 |
| B4 | 6 | 中 |
| B5 | 7 | **次大**，约 25% |
| B6 | 3 | 中 |
| B7 | 3 | 小 |
| B8 | 5 | 小 |

**建议节奏**：B0→B1→B2 一口气做完（这一步不改行为，风险最低、收益最大：接缝建好后，后面的改动都被关在引擎里）；B4 与 B5 之间可以停下来观察一周再继续。

**如果只想最小可用**：做到 B4 为止就是一个完整功能（固定周几），且完全不碰统计口径。B5 的弹性配额才是会动周条与连续口径的部分，可以单独决策。

---

## 8. 一句话回答你的原始问题

> 「能不能针对习惯单独写算法，旧调用全部重写，以后改不牵扯别处？」

**能，而且应该，但不是「重写」，是「建接缝后替换」。**

差别在于：重写是 31 个调用点一起动、出错只能整体回滚；建接缝是先把判定收进一个命名空间、用转调壳保证行为等价，再逐个迁移，任何一步都能单独回滚。

接缝建好之后，**习惯功能以后怎么改都只动 `HabitEngine` 内部**，外部 10 个 API 的签名不变——这才是你要的「不牵扯别的地方」。而单独建 SQL 表不但做不到这一点，还会把复杂度从前端搬到后端。

---

本改动单为工程实施参考，动手前请按 §4 逐条确认不变式，并在 `CHANGE-MAP.md` 登记本次改动。
