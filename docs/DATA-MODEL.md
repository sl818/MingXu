# 数据模型 · state

> 云端 `boards.data` 里存的、前端内存里 `state` 里跑的，都是这一份结构。
>
> 配套阅读：`FRONTEND.md` 第 3、10 节，`BACKEND.md` 第 4 节。

最后更新：v46（2026-10-30）

---

## 1. 顶层结构

```js
{
  version: 2,              // 早期字段，保留兼容
  schemaVersion: 6,        // 迁移版本号，见第 9 节
  view: 'today',           // 上次停留的页面

  habits: [],              // 习惯（含 4 个内置常驻卡）
  tasks: [],               // 待办
  meds: [],                // 药品

  checks: {},              // 习惯打卡：{日期: {习惯id: 次数}}
  doses: {},               // 服药记录：{日期: {药品id: {时段: 记录}}}
  events: [],              // 操作日志（习惯 + 服药），上限 1000 条
  cravings: [],            // 戒烟事件流（点一根 / 忍一次），见第 5.4 节
  packs: [],               // 买烟记录：一包一条，见第 5.5 节

  weights: [],             // 体重记录
  bodyProfile: {},         // 身体档案（年龄 / 身高 / 目标体重）
  essays: [],              // 随笔

  moods: {},               // 心情：{日期: 心情key}
  notes: {}                // 旧版随记，保留但界面已无入口
}
```

**六个内置 id 要记住**：

| id | 说明 |
|---|---|
| `h_med` | 用药卡的占位习惯。`met()` 看药品记录，不看 `checks`。习惯管理页会跳过它 |
| `h_water` | 喝水。`target` 是杯数（默认 9），实际毫升靠 `waterMlOf()` 换算 |
| `h_move` | 运动。有独立的周视图和七段环 |
| `h_breathe` | 478 呼吸法。**会自动补进 habits**，即使被删也会被 `ensureBreathingHabit()` 加回来 |
| `h_drink` | 戒烟，`type: 'quit'` |
| `med_default` | 默认药品 |

---

## 2. `habits[]`

| 字段 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `id` | string | `h_xxx` | 内置的用固定 id，自建的随机 |
| `name` | string | — | 习惯名 |
| `icon` | string | `✅` | emoji |
| `type` | `'build'` \| `'quit'` | `'build'` | quit 走事件流，见第 5.4 节；`build` 看次数 |
| `target` | number | 1 | 每日目标次数 |
| `unit` | string | `'次'` | 单位 |
| `color` | string | — | 卡片强调色 |
| `note` | string | `''` | 备注。`quit` 类型为空时卡片显示一句引导语 |
| `quitStart` | `'YYYY-MM-DD'` | 无 | 只 `quit` 用：戒烟起点。没有就退回 `createdAt` 的日期 |
| `quitPerDay` | number | 0 | 只 `quit` 用：原来每天几支。0 = 不折算省钱 |
| `quitPackPrice` | number | 0 | 只 `quit` 用：一包多少钱（元）。0 = 不折算省钱 |
| `quitPackSize` | number | 20 | 只 `quit` 用：一包几支，用来把包价换算成单价 |
| `createdAt` | ISO string | — | |
| `archivedAt` | ISO string \| `''` | `''` | 非空 = 已归档 |
| `optional` | boolean | 无（falsy） | **可选项**：不催、不计入完成率分母以外的统计 |
| `med` | boolean | 无 | 标记这是用药卡占位（只有 `h_med`） |
| `suggestTime` | `'HH:MM'` | 无 | **通知时间**。没有就不推送 |
| `breatheCycles` | number | 4 | 只 `h_breathe` 用 |
| `notify` | boolean | `true` | 通知开关 |
| `notifyFreq` | `'daily'` / `'weekly'` / `'monthly'` | `'daily'` | 通知频率（**不影响打卡频率**） |
| `notifyWeekday` | 0–6 | 1 | 每周几提醒，**0 = 周日** |
| `notifyMonthday` | 1–31 | 1 | 每月几号提醒 |
| `notifyNote` | string | `''` | 通知备注，随推送一起发 |

**`optional` vs `notify` 的区别（重要）**：

- `optional` = 这个习惯是**可选项**，影响 `activeHabits()` 的构成和统计口径
- `notify` = 这个习惯**要不要提醒**，只影响推送

两者正交。**不要为了省字段把"是否通知"塞进 `optional`。**

---

## 3. `tasks[]`

| 字段 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `id` | string | `t_xxx` / `uid()` | |
| `title` | string | — | 标题 |
| `note` | string | `''` | 备注 |
| `tag` | string | `'其他'` | 必须在 `TAGS` 枚举内：健康 / 生活 / 工作 / 学习 / 其他 |
| `priority` | string | `'中'` | 必须在 `PRIO` 枚举内：高 / 中 / 低 |
| `status` | `'todo'` / `'doing'` / `'done'` / `'cancelled'` | `'todo'` | |
| `due` | `'YYYY-MM-DD'` | — | **截止日，注意字段名是 `due` 不是 `date`** |
| `createdAt` | ISO string | — | |
| `doneAt` | `'YYYY-MM-DD'` \| `null` | `null` | 完成日期（用于"今日完成 N 项"） |
| `repeat` | `'none'` / `'daily'` / `'weekly'` / `'monthly'` | `'none'` | |
| `repeatTime` | `'HH:MM'` | `'20:00'` | **只用于重复滚动和显示，不再用于通知** |
| `repeatWeekday` | 0–6 | 由 due 推 | 每周几，0 = 周日 |
| `repeatDay` | 1–31 | 由 due 推 | 每月几号 |
| `repeatNextId` | string | `''` | 完成后生成的下一条待办的 id |
| `repeatFrom` | string | `''` | 由哪条重复任务生成 |
| `archivedAt` | ISO string \| `''` | `''` | 非空 = 已归档 |
| `notify` | boolean | `true` | 通知开关 |
| `notifyTime` | `'HH:MM'` | `'09:00'` | **通知时间**（什么时候提醒） |
| `notifyNote` | string | `''` | 通知备注 |
| `startTime` | `'HH:MM'` \| `''` | `''` | **时间块的开始时刻**，周视图据此画色块；空 = 落在「全天」行 |
| `duration` | number | `0` | **时间块时长（分钟）**，按 15 对齐，范围 15–720；`0` 表示没设 |

> `notifyTime` 和 `startTime` 是两件事：前者决定「什么时候响」，后者决定
> 「这件事几点到几点」。表单里填了开始时间、又没手动改过通知时间时，
> 通知时间会自动跟随（见 `bindTaskForm`），避免下午的事早上 9 点响。

### 3.1 重复任务的语义

完成一条重复任务时，`completeRecurringTask(t, date)`：

1. 用 `nextRepeatDate()` 算出下一次日期
2. **新建一条**新任务（新 id），`due` 是下一次，`repeatFrom` 指向原任务
3. 原任务的 `repeatNextId` 指向新任务
4. 撤销完成时 `uncompleteRecurringTask()` 把新任务删掉

所以**重复任务在数据里是很多条独立的任务**，不是一条带规则的记录。
看板/今日页通过 `liveTasks()` 过滤。

---

## 4. `meds[]`

| 字段 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `id` | string | `med_xxx` | |
| `name` | string | — | 药名 |
| `purpose` | string | `'其他'` | 用途分类 |
| `form` | string | `'片'` | 剂型 |
| `strength` | string | `''` | 规格（如 "0.25g"），纯展示 |
| `doseAmount` | number | 1 | 每次剂量 |
| `doseUnit` | string | `'片'` | 剂量单位 |
| `times` | `string[]` | `[]` | 每日服用时刻，**必须 `HH:MM` 两位** |
| `mealTiming` | `''` / `'before'` / `'after'` / `'with'` / `'empty'` | `''` | 餐前/餐后/随餐/空腹 |
| `mealOffset` | number \| `''` | `''` | 距用餐多少分钟（0–720） |
| `courseType` | `'long'` / `'short'` / `'prn'` | `'long'` | 长期 / 短期疗程 / 按需 |
| `startDate` | `'YYYY-MM-DD'` | 今天 | |
| `endDate` | `'YYYY-MM-DD'` \| `''` | `''` | **只有 `short` 才生效** |
| `reviewDate` | `'YYYY-MM-DD'` \| `''` | `''` | 复查日，只 `long` 有 |
| `status` | `'active'` / `'paused'` / `'stopped'` | `'active'` | |
| `stockBase` | number \| `''` | `''` | **库存基线**，不是余量 |
| `stockBaseAt` | ISO string | `''` | 基线登记时间 |
| `stockReview` | boolean | `false` | 「待核对」标记 |
| `updatedAt` | number (ms) | — | **合并时用来判断谁新，必须有** |
| `manufacturer` | string | `''` | 厂商 |
| `medInfo` | string | `''` | 药品说明 |
| `note` | string | `''` | 备注 |
| `createdAt` | ISO string | — | |

### 4.1 三种 `courseType` 的行为差异

| | `long` | `short` | `prn` |
|---|---|---|---|
| 需要 `times` | ✓ | ✓ | ✗（空数组） |
| 需要 `endDate` | ✗ | ✓（必填） | ✗ |
| 进日历 | ✓ | ✓（到 endDate） | ✗ |
| 推送提醒 | ✓ | ✓ | ✗ |
| 计入依从率 | ✓ | ✓ | ✗（只报"吃了 N 次"） |
| 库存扣减 | ✓ | ✓ | ✓（按需记录也扣） |

**`prn` 是最容易漏的**：它没有固定时刻，不进日历、不推送，但**会扣库存**。

### 4.2 库存：基线 + 推算，不存余量

```js
medStockRemain(med) = medStockBase(med) - medStockUsed(med)
```

- `medStockBase(med)` = `stockBase`（基线，用户某天登记的"手里有多少"）
- `medStockUsed(med)` = 基线之后所有服药记录的剂量之和（含 `prn`）

**为什么不存"剩余数量"**：记录合并是并集，各端从同一条基线推算出来的结果天然一致、可自愈。
存绝对数一旦某次扣减丢了，就永久错且无法自查。**这是踩过事故后改的。**

### 4.3 登记库存时的三种情况（`saveMedForm` / `saveStockCheck`）

| 用户输入 | 行为 |
|---|---|
| 留空 | 不跟踪库存 |
| 与当前推算余量相同 | **保留原基线**（否则历史扣减会被"洗掉"） |
| 与当前余量不同 | 视为一次重新登记，把此刻设为新基线 |

---

## 5. `checks` 与 `doses`（最容易合并错的两个）

### 5.1 `checks` —— 两层

```js
checks = {
  '2026-10-30': { 'h_water': 6, 'h_move': 1 }
}
```

- 第一层：日期
- 第二层：习惯 id → **次数**（number）
- 合并规则：**取较大值，只增不减**

### 5.2 `doses` —— 三层

```js
doses = {
  '2026-10-30': {
    'med_abc': {
      '08:00': { at: '2026-10-30T08:05:00+08:00' }
    }
  }
}
```

- 第一层：日期
- 第二层：药品 id
- 第三层：**时段 `HH:MM`** → 记录对象
- 合并规则：**时段级并集**，两边都有的时段取本地那份

### 5.3 为什么必须分开合并

曾经用同一段代码处理两者：

```js
m[k] = Math.max(Number(rv) || 0, Number(lv) || 0);   // 对 doses 来说 lv 是对象
```

`Number({})` = `NaN`，`NaN || 0` = `0` → **整瓶药当天的记录被压成 0**。
这是"用药数据突然消失"的历史元凶。

现在是 `mergeByDay()` 里按 `isPlainObject` 分流：

```js
if (isPlainObject(lv)) { 时段级并集 }
else { Math.max(次数) }
```

**加新的按天数据时，先想清楚它是两层还是三层。**

### 5.4 `cravings[]` —— 戒烟事件流

```js
cravings: [
  { id: 'k3x9a', t: 1761824520, k: 's', h: 'h_drink', g: 'stress', s: 0 }
]
```

| 字段 | 说明 |
|---|---|
| `id` | 合并去重用的键 |
| `t` | **秒级**时间戳。不用 ISO 字符串——一天几十条、一年上万条，而同步是全量快照 |
| `k` | `'s'` 抽了 / `'r'` 忍住了 |
| `h` | 习惯 id。只有 `type === 'quit'` 的习惯会产生事件 |
| `g` | 诱因 key（`CRAVE_TRIGGERS`：meal / stress / social / bored / drive / drink / other），空串 = 没标 |
| `s` | 强度 0–5，**预留字段，当前未使用** |

三条硬规则：

1. **不进 `checks`**。`checks` 是「今天做了几次」的计数语义，事件是「此刻发生了什么」。
   混进去会让 `met()`、`habitStreak()`、月历、统计页每一处都要再判一次类型——
   这正是 `type === 'quit'` 现在有十几处特判的原因，不要再加深。
2. **「抽了」和「忍住了」都记**。只让用户记失败的话，人会因为不想承认而少记，数据就废了。
3. **合并走独立的 `id` 并集**（见第 10 节）。不要套 `events` 的 `at|id|delta` 判重键，
   事件流没有 `delta`，同一秒两条会互相顶掉。

派生函数：`quitStreak` / `quitTotal` / `quitBest` / `quitRange` / `craveHours` / `craveTriggers` /
`quitSaved`（省钱）/ `quitNextMile`（下一个里程碑）/ `currentPack` / `packUsed` / `packSpan` /
`packCompareLine`（上一包 vs 这一包）。

### 5.5 `packs[]` —— 买烟记录

```js
packs: [{ id: 'pk1', at: 1761824520, name: '黄鹤楼', price: 25, size: 20 }]
```

| 字段 | 说明 |
|---|---|
| `at` | 开包时刻（秒）。“当前这包” = `at` 最大的那条 |
| `name` / `price` | 烟名、一包多少钱。可以不填（迁移补的包 `price: 0`） |
| `size` | 一包几支，默认 20 |

**绝不存「还剩几支」。** 那是派生量：

```js
剩余 = pack.size - packUsed(h, pack).length
packUsed = 开包之后所有 k === 's' 的事件
```

存了剩余量，多端一合并必然对不上（跟药品库存是同一个道理，见 4.2）。

`packSpan(h, pack)` 算「这包抽了多久」：抽完了算到最后一次，没抽完算到现在。
这是戒烟卡上信息量最大的一个数——比「连续几天没抽」更能反映还在抽的人的进度。

`packCompareLine(h)` 对比上一包：上一包「用了多久」= 这一包开包时间 − 上一包开包时间
（开新包就代表上一包结束）。这一包还没抽完时只补一句「上一包 X 就抽完了」，
不重复第一行已有的「这包开了多久 / 还剩几支」；两包都抽完才并列两个时长。

> **口径**：`craveHours`（时段图）和 `craveTriggers`（诱因）**只统计 `k === 's'`**。
> 把「忍住了」混进去会出现「压力 7 次」但其实只抽了 3 根的矛盾，
> 而且这两件事回答的是不同的问题：什么是危险场景 vs 什么场景能扛住。

---

## 6. 其他实体

### 6.1 `weights[]`

```js
{ id, date: 'YYYY-MM-DD', age, height, weight, bmi, createdAt }
```

**`age` 和 `height` 必须都有**（`normalizeWeightRecord` 会因此丢弃整条）。

### 6.2 `bodyProfile`

```js
{ age: 0, height: 0, goalWeight: 0 }   // 0 表示未设置
```

`normalizeBodyProfile` 会校验范围：age 1–120、height 50–250、goalWeight 20–300。
超出范围退回全 0。

**有一段隐式逻辑**：如果 `bodyProfile` 没有 age/height，`normalizeState` 会从最新一条
体重记录里反填（旧版本体重记录自带这两个字段）。

### 6.3 `essays[]`

```js
{ id, date, title, text, tags: [], createdAt, updatedAt }
```

**正文字段是 `text`，不是 `body`。** 上限 5000 字；`tags` 最多 5 个，每个 12 字。

### 6.4 `events[]`

```js
// 习惯打卡
{ at: 'ISO', d: 'YYYY-MM-DD', id: 'h_water', delta: +1 }

// 服药
{ at: 'ISO', d: 'YYYY-MM-DD', id: 'med_abc', delta: +1, kind: 'med', slot: '08:00' }
```

- 上限 1000 条，超出 `slice(-1000)`
- 合并时按 `at` + `id` + `delta` 去重并集
- `rebuildChecksFromEvents()` 能在 `checks` 丢失时从事件流重建

### 6.5 `moods` / `notes`

```js
moods = { '2026-10-30': 'calm' }     // 值必须在 MOODS 枚举内
notes = {}                            // 旧版随记，保留但无界面
```

---

## 7. 派生值（**不存储，每次算**）

这些值看起来很需要存，但都刻意每次现算。理解这点能避免"为什么没有这个字段"的困惑。

| 派生值 | 函数 | 算法 |
|---|---|---|
| 库存余量 | `medStockRemain` | 基线 − 基线之后的记录剂量和 |
| 库存可吃天数 | `medStockDays` | 余量 ÷ 每日剂量 |
| 某天的待办 | `dayTasks(ds)` | `liveTasks()` 里 due 正好是那天、且未完成/未取消的 |
| 周视图的事件块 | `weekDayBlocks(ds)` | 待办 + 用药 + 习惯，同一时刻同类合并 |
| 今日应服次数 | `medScheduledCount(d)` | 当天有排期的药的时段总数 |
| 今日已服次数 | `medTakenCount(d)` | 当天 `doses` 的记录数 |
| 今日依从率 | `medAdherenceDay(d)` | 已服 ÷ 应服 |
| 习惯今日计数 | `countOf(d, id)` | `checks[d][id]` |
| 习惯是否达标 | `met(h, d)` | 次数 ≥ target；`h_med` / `quit` 特殊（quit 看当天有无 `s` 事件）|
| 连续无烟天数 | `quitStreak(h)` | 今天 − 最后一次「抽了」那天；从没抽过则从 `quitStart` 算 |
| 累计无烟天数 | `quitTotal(h)` | 起点到今天的天数 − 有「抽了」的天数 |
| 最长无烟段 | `quitBest(h)` | 扫全部 `s` 事件求最大相邻间隔 |
| 抵御率 | `quitRange(h, N)` | 忍住 ÷ (忍住 + 抽了)，`rate` 字段 |
| 时段分布 | `craveHours(hid)` | 24 个桶，**只数 `s`** |
| 失守诱因 | `craveTriggers(hid)` | 按 `g` 计数，**只数 `s`** |
| 当日统计 | `dayStats(d)` | 见下 |
| 连续天数 | `habitStreak(h)` / `overallStreak()` | 从今天往回数 |
| 未完成任务 | `liveTasks()` / `pendingTasks(d)` | 过滤 done/cancelled/archived |

### 7.1 `dayStats(d)` 的分母陷阱

```js
dayStats(d).total = activeHabits(d).length
```

`activeHabits(d)` **包含自动补进来的 `h_breathe`**，也可能包含 `h_med`。
而 `h_med` 的 `met()` 不看 `checks`，看 `medTakenCount(d) >= medScheduledCount(d)`。

所以构造"全部达标"的测试数据时，要同时打满：所有普通习惯的 `checks` +
`h_med` 对应的 `doses` + `h_breathe`。否则你算出的 4/6 = 66.7% 会让人以为代码错了。

---

## 8. 枚举与常量

```js
TAGS   = { '健康': '#2f7d5c', '生活': '#8a6524', '工作': '#9a5a2f',
           '学习': '#6b5b8e', '其他': '#6f7468' }
PRIO   = { '高': '#b0473d', '中': '#8a6524', '低': '#6f7468' }
STATUS = { todo: '待办', doing: '进行中', done: '已完成', cancelled: '已取消' }
MOODS  = [ ... ]                                   // 心情枚举
WEEK_CN   = ['日','一','二','三','四','五','六']    // 0 = 周日
ICS_WEEK  = ['SU','MO','TU','WE','TH','FR','SA']

COURSE_TYPE   long / short / prn
MED_MEAL_CN   before→餐前 / after→餐后 / with→随餐 / empty→空腹
MED_PHASES    进行中 / 未开始 / 暂停 / 已停用   （按 status + 日期算出来的分组）
```

**`tag` 和 `priority` 的值必须在枚举内**。超出枚举的颜色查不到，会退化成继承色。

---

## 9. 迁移链

`migrateState(data)` 按 `schemaVersion` 顺序执行，每一步只跑一次。

| 版本 | 做什么 |
|---|---|
| v1 → v2 | `migrateColors` / `migratePinned` / `migrateMeds` / `migrateQuitHabit` |
| v2 → v3 | `migrateWater`（8 杯 → 9 杯 / 250ml）、`ensureBreathingHabit` |
| v3 → v4 | 库存从"绝对数逐次扣减"改为"基线 + 推算" |
| v4 → v5 | `migrateQuitCravings`：老 `checks` 里的戒烟次数转成 `s` 事件，清掉「保持 0 次」备注 |
| v5 → v6 | `migrateQuitPack`：给有戒烟习惯但没有买烟记录的账号补一包（开包时间 = 戒烟起点） |
| 每次加载 | `migrateStock()` —— **幂等补齐，不依赖版本号** |

### 9.1 两条规则

1. **状态迁移只加不减**。新版本号只增，老的迁移步骤保留在对应版本分支里，不要删。
   删了之后，从很老的备份恢复的数据就迁不上来。
2. **幂等补齐要每次跑**。`migrateStock()` 不挂在版本号分支上，因为
   "版本已经是 4、但后来又混进旧格式条目" 的情况会发生（比如从旧备份导入）。

---

## 10. `mergeStates(remote, local)` 逐字段规则

冲突时的合并策略。原则：**能并集就并集，不能并集才比时间。**

| 字段 | 规则 |
|---|---|
| `habits` / `tasks` / `meds` / `weights` / `essays` | 按 `id` 并集。云端为基，本地有而云端没有的补入 |
| 上述数组里的 `archivedAt` | 取非空优先（归档只增不减） |
| `meds` 单条 | 先比 `updatedAt`，**新的一侧整体胜出**；再单独比 `stockBaseAt`，更晚的库存基线覆盖 |
| `checks` | 按天，同 key 取 `Math.max`（只增不减） |
| `doses` | 按天 → 按药品 → **按时段并集**，两边都有取本地 |
| `moods` | 按日期，本地优先 |
| `notes` | 按日期，本地优先 |
| `events` | 按 `at` + `id` + `delta` 去重并集 |
| `cravings` | 按 `id` 去重并集，合并后按 `t` 排序。**单独一段，不复用 `events` 的判重键** |
| `packs` | 按 `id` 去重并集，合并后按 `at` 排序。同样单独一段 |
| `bodyProfile` | 浅合并，本地优先 |
| `view` | 以远程为准（`out = {...remote}`） |

### 10.1 为什么 `meds` 要特殊处理

早期是"整条以云端为准"，结果**本地刚改的名字、刚登记的库存全被丢弃**。
现在按 `updatedAt` 判断，所以**每个可编辑实体都要有 `updatedAt`**，否则合并时永远平手、
永远是云端赢。

### 10.2 加新字段时的检查清单

- [ ] `normalizeState` 里补默认值和类型校验
- [ ] 如果这个字段需要合并，`mergeStates` 里明确它的规则
      （**忘了这步 = 多端使用时被静默吞掉，已踩两次**）
- [ ] 如果是可编辑实体，确保有 `updatedAt`
- [ ] 如果日历要用，`api/ics.php` + 前端 `buildICS()` 一起加
- [ ] 如果推送要用，`api/schedule.php` 一起加
- [ ] 跑 `verify-ics-subscribe.py`（前后端日历等价）
- [ ] 跑 `test-schedule.php`（推送语义）

---

## 11. 数据流小结

```
用户点按钮
   │
   ▼
ACTIONS[act](el)  ──► 改 state（如 state.tasks.push(...)）
   │                      │
   │                      ├─► takeDose/logHabit 会同时写 doses/checks + events
   │                      └─► 可编辑实体更新 updatedAt
   ▼
save()  →  300ms 防抖  →  cloudPush(base_rev)
                              │
                        ┌─────┴─────┐
                       成功         409
                        │           │
                    rev+1      mergeStates(remote, local)
                                    │
                              normalizeState → save(base_rev=新rev)
```

**推送链路完全不在这张图里**。它读的是云端 `boards.data` 的一份拷贝，
所以前端改了字段，后端要能读到——这就是"新增字段必须同步 `schedule.php`"的原因。
