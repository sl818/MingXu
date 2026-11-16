# 数据模型 · state

> 云端 `boards.data` 里存的、前端内存里 `state` 里跑的，都是这一份结构。
>
> 配套阅读：`FRONTEND.md` 第 3、10 节，`BACKEND.md` 第 4 节。

最后更新：v99（2026-11-16）

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
  packs: [],               // 买烟记录：一包一条（不含库存/在抽状态），见第 5.5 节

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
| `type` | `'build'` \| `'quit'` \| `'smoke'` | `'build'` | **三种类型，靠 type 分**（`quit` 内部还有一个 `slipMode` 决定打卡方式，但它是「同一类习惯的计量口径」，不是新类型——类型判定永远只看 `type`）：`build` 保持（点一下算达标，看 `checks` 次数）；`quit` 戒除（**点一下算今天没守住**，不点就是守着，走事件流）；`smoke` 戒烟（站点自带的常驻卡，双按钮 + 烟盒 + 买烟 + 趋势）。见 3.1 与 5.4 |
| `target` | number | 1 | 每日目标次数 |
| `unit` | string | `'次'` | 单位 |
| `color` | string | — | 卡片强调色 |
| `note` | string | `''` | 备注。`quit` 类型为空时卡片显示一句引导语 |
| `quitStart` | `'YYYY-MM-DD'` | 无 | 只 `quit` 用：起点日期（戒烟叫「戒烟起点」，其他叫「开始日期」）。没有就退回 `createdAt` 的日期 |
| `slipMode` | `'once'` \| `'multi'` | `'once'` | 只 `quit` 用：打卡方式。`once` = 每日单次（点了就是破了，再点撤销）；`multi` = 每日多次（一天能记好几次）。**缺省就是 once，老数据不用迁移**。见 3.1 |
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
packs: [{ id: 'pk1', at: 1761824520, name: '黄鹤楼', price: 25, size: 20, cf: 0 }]
```

| 字段 | 说明 |
|---|---|
| `at` | 买烟时刻（秒，**精确到分**）。表单填「日期 + 时间」，同一天买两包才分得清先后 |
| `name` / `price` | 烟名、一包多少钱。可以不填（迁移补的包 `price: 0`） |
| `size` | 一包几支，默认 20 |
| `cf` | 末支确认时刻（秒）。`0` = 没确认过；非 0 = 用户确认过「这包是几点抽完的」 |

**绝不存「哪包在抽」「还剩几支」「库存几包」**，全是派生量。

一包 = 一个左闭右开区间，由 `packSpans(h)` 推出来：

```
openAt(第1包)  = 这包的 at
closeAt(第k包) = 这包第 size 支的时刻（不足 size 支 = 0，表示还在抽）
openAt(第k包)  = max(这包的 at, closeAt(第k-1包) + 1)

消耗(第k包) = 落在 [openAt, closeAt) 内的 k === 's' 事件条数，封顶 size
```

`max()` 那一下就是「自动绑定下一包」：一包抽满，下一包的起点自动推到那一刻，
不用字段、不用用户点「开新包」。一次买三条只抽第一条时，后两包的起点还在未来，
天然就是库存。同一天买两包（`at` 相同）也不会再共用同一个计数窗口——
v67 之前两包都显示 `22/20` 就是这个 bug。

派生出三个量：

| 量 | 算法 | 用在哪 |
|---|---|---|
| 当前这包 | 第一个 `used < size` 的包 | 卡面烟盒画谁 |
| 库存 | `openAt > now` 的包数 | 买烟记录上的「库存」标 |
| 未归包 | 总 `k==='s'` 条数 − 所有包 `used` 之和 | 库存空时抽的那些散烟 |

**库存为 0 时不再收新记录**（`packBlocked(h)`）：当前这包已经抽满、又没有下一包时，
「点一根」在戒烟页和今日页都置灰，`addCraving` 里还有一道同样的闸——按钮的 `disabled`
能被回车提交绕过，只挡 UI 不够。

这是库存模型的原意：一包 `size` 支，抽满就到底，没有下一包就没有下一支。
不放这道闸，「超出」会被记成未归包，「今天抽了几支」就会涨到 21，而烟盒和买烟记录
仍然是 `20/20`——两个数字打架，看起来就是算错了。

因此「未归包」只在两种情况下非 0：v68 之前留下的老数据，或者从备份导入的数据。
正常操作路径上已经产生不出来。

**为什么所有量都派生**：存了就要维护——撤销一支、补记、改买烟日期、两台设备同时点，
每条路径都会让存的字段对不上。派生则会自动重算（跟 4.2 药品库存同一条铁律）。

`packSpanTextOf(span)` 算「这包抽了多久」：抽完了算 `首支 → 末支`，没抽完算 `开包 → 现在`。
末支优先用 `cf`（用户确认值），没确认就用最后一条记录的时刻。

时长口径：满 24 小时显示「X 天 Y 小时」，不满显示「X 小时 Y 分」，超过 7 天只显示「X 天」。

### 5.6 `notices[]` —— 自定义通知（v71）

```js
notices: [{ id: 'n1', text: '该吃维生素了', time: '20:00', mode: 'daily',
            date: '', weeks: [], monthday: 1, on: true }]
```

| 字段 | 说明 |
|---|---|
| `text` | 通知正文，用户自己写。上限 1000 字符（前端卡 500 字，`lb_push_clip` 再兜 2048 字节） |
| `time` | `HH:MM`，必须合法，否则这条不参与推送 |
| `mode` | `once` / `daily` / `weekly` / `monthly` |
| `date` | 仅 `once` 用 |
| `weeks` | 仅 `weekly` 用，0-6（0=周日），可多选 |
| `monthday` | 仅 `monthly` 用，1-31。**超过当月天数时按月末那天发**（31 号在 2 月就是 28/29） |
| `on` | `false` = 暂停 |

**不存「发过没有」**。去重靠后端 `push_sent` 的 `slot_key`（`日期|notice|id|时间`）：
单次通知只有指定那天会进计划，发过一次就再也不出现；重复的每天键不同，各发一次。

合并策略：按 `id` 去重并集（和 `packs` 一样）。代价是「只在一端删掉」会被另一端合回来。

### 5.7 `cardOrder` / `cardOrderAt` —— 常驻卡顺序（v75）

```js
cardOrder: ['h_drink', 'h_med', 'h_water', 'h_move', 'h_breathe'],
cardOrderAt: 1762660800000
```

| 字段 | 说明 |
|---|---|
| `cardOrder` | 常驻卡的 id 顺序。只存顺序，**不存集合**——哪些卡存在永远由 `PINNED_IDS` 决定 |
| `cardOrderAt` | 最后修改时刻（毫秒）。合并时只认它 |

`normalizeCardOrder()` 只做去重和剔空值，**不剔未知 id**：将来 `PINNED_IDS` 加卡片时，
用户之前存过的顺序还能用上；真正排序时 `orderedPinnedIds()` 会按已知集合再过滤一遍。

**合并规则：整份覆盖，绝不能按 id 并集。**
两端各排一次，并集会拼出一个「两边交错」的顺序，谁看都不对。所以：

```js
if (本地 cardOrderAt > 远端 cardOrderAt) 用本地整份;  // 否则保持远端
```

两边都是 0（从没排过）时保持远端，也就是默认顺序。

### 5.7b `navOrder` / `navOrderAt` —— 导航顺序（v86）

```js
navOrder: ['today', 'meds', 'quit', ...],   // 只存 key 顺序，不存分组
navOrderAt: 1763000000000
```

| 字段 | 说明 |
|---|---|
| `navOrder` | 导航项的 key 顺序。只存顺序，**不存集合**——有哪些页永远由 `NAV` 决定 |
| `navOrderAt` | 最后修改时刻（毫秒）。合并时只认它 |

`normalizeNavOrder()` 只去重和剔空值，**不剔未知 key**：`NAV` 是后面才声明的 `const`，
状态初始化时它还在 TDZ 里，引用会直接抛错。未知 key 交给 `orderedNav()` 在渲染时忽略。

**组间固定**：`orderedNav()` 先按 `group`（记录 / 回顾）排，再按 `navOrder` 排名。
UI 只给组内 ↑↓，但导入的备份不一定规整，所以这层兜底写在排序函数里而不是 UI 里。

**合并规则：整份覆盖**（同 `cardOrder`），绝不能按 key 并集。

### 5.7c `money` / `moneyAt` —— 清债（v88）

```js
money: {
  v: 1,
  debts:      [{ id, name, type, balance, start, apr, min, due, note, clearedAt, u }],
  extra:      1000,          // 每月在最低还款之外多还的「加速钱」
  strategy:   'snowball',    // snowball | avalanche | custom
  customOrder: [],
  snowflakes: [{ id, ym, amount, note, u }],   // 一次性多还
  startYM:    '',            // 空 = 下个月
  log:        [{ id, date, debtId, debtName, amount, note, u }],
  incomes:    [{ id, name, amount, u }],
  cats:       [{ id, name, kind:'fixed'|'daily', budget, u }],
  spends:     [{ id, date, catId, catName, amount, note, u }],
  notify:     { on:false, before:[3,1,0], time:'09:00' }   // v92 起生效，默认关
}
moneyAt: 1763000000000
```

**为什么是一个子对象而不是十个顶层字段**：顶层字段每加一个，`normalizeState` /
`mergeStates` / `repairBackup` 三处都要跟着改，v78 那次导入清空数据就是漏了第三处。
收成一个对象，三处各加两行就够。

**合并**：六个集合走 `mergeById()` 按 id 并集，**同 id 取 `u` 更大的那份**
（债是可编辑实体，跟 `packs` 那种只增不改的不一样，直接远端优先会把本地刚改的余额吃掉）；
`extra` / `strategy` / `customOrder` / `startYM` / `notify` 这些单值字段没有各自的修改时间，
只能整组比 `moneyAt` —— 新的那端覆盖旧的。

**不参与考核**：清债数据不写 `habits` / `checks` / `tasks`，
所以 `rateOver` / `dayStats` / `taskStats` / `habitDayAcc` 全都看不见它。
（用户说过「以后可能要做」，到时候得另开一套口径，别往 `dayStats` 里塞。）

**备份（v94 起只有一份）**：清债数据就在 `state.money` 里，**设置页导出的整站 JSON 已经完整包含它**，
`repairBackup()` 里也有 `money: normalizeMoney(data.money)`。所以不再单独提供「清债备份」——
两套导出只会让人以为要分别备份两次。旧版导出的 `清债备份-*.json` 已无法导入（缺 `habits`/`tasks`）。

**预算口径（v90）**：`incomes` / `cats` 都是**每月额度**，不是本月实际；
`cats.kind` 只有 `daily`（按天摊）和 `fixed`（房租水电，不按天摊）两种。

- 钱怎么分：`收入 − 固定 − 日常 − 债务月供 = 剩余可支配`，可以是负数
- 每日可花：`(日常预算 − 本月已花) ÷ 本月剩余天数`，**只摊 daily**，否则房租会把「今天能花」压成负数
- 删分类不删流水：`spends.catName` 是写入时的快照，分类被删后按 daily 计——
  钱已经花出去了，不能因为挂的分类不存在就从账上消失

**还款日不进日历事件流**（v92 要做时注意）：只做展示和提醒，
**不要写成 task 或 check**，否则会混进完成率。

### 5.8 `countdowns[]` —— 倒数日（v76）

```js
countdowns: [{ id: 'cd1', title: '考研初试', date: '2026-11-20',
               note: '记得打印准考证', time: '09:00', remindDays: [3, 1, 0], on: true }]
```

| 字段 | 说明 |
|---|---|
| `title` | 名字，必填。空的会被 `normalizeCountdowns` 直接丢掉 |
| `date` | 目标日期 `YYYY-MM-DD`，**只到天**。倒数天数是日期级的，加时刻没意义 |
| `note` | 自定义备注，会跟在推送正文后面。不填就不多发空行 |
| `time` | 提醒时刻 `HH:MM`，默认 09:00 |
| `remindDays` | 提前几天提醒，`0` = 当天，可多选。空数组 = 只显示不提醒 |
| `on` | `false` = 暂停提醒（**不影响倒数天数的显示**） |

**不存「未来还是过去」「还剩几天」**：全部由 `date` 与今天现算。
存了就要维护「今天过零点要改字段」这条路径，而它没有触发点，必然错。

合并策略：按 `id` 去重并集（和 `packs` / `notices` 一致），合并后按 `date` 升序。

### 戒除的打卡方式 `slipMode`（v79）

```js
{ id: 'h_q1', type: 'quit', slipMode: 'multi' }   // 缺省是 'once'
```

| 值 | 卡面 | 数据 |
|---|---|---|
| `once`（默认） | 一条 `.pip` 通栏横条，点了变空心，再点撤销 | 当天最多 1 条 `s` 事件 |
| `multi` | 一颗 `.quit-add` 通栏按钮（未破「今天守住了」/ 已破「又破一次」）+ 次数 + 「撤销」 | 当天可以有多条 `s` 事件 |

**这个字段不影响任何统计**：`quitSlips()` 一直是 `filter(k==='s').length`（本来就能返回 2、3），
`met()` 判的是「当天有没有任何一条 `s`」，破几次都是未达标。

**注意它和 v63 被否掉的 `quitKind` 不是一回事。** 那次是把「戒烟」当成戒除的子类，
于是所有戒除习惯都被套上了「点一根」；`slipMode` 只是同一类习惯的计量方式，
跟保持类的 `target` 同级，不改变类型的语义，也不新增 `type` 取值。

`addCraving` 里那条「1 秒内同类型去重」对 `multi` **必须失效**——
一天两杯奶茶就是两次，用户可能一秒内连点，挡掉就等于记不进去（误点靠「撤销」兜底）。

### 导入的字段范围（v78）

**导出 = 全量 `JSON.stringify(state)`；导入 = `repairBackup()` 清洗后重建。**

历史上导入是一张白名单，只保留 14 个字段，导致 v68 之后新增的
`cravings` / `packs` / `notices` / `cardOrder` / `cardOrderAt` / `navOrder` / `navOrderAt` / `countdowns`
在导入时被静默丢弃，并把残缺 state 推回云端（v78 修）。

现在的规则：白名单内的字段逐项清洗，**白名单外的顶层键原样带过**。
新增顶层字段时仍要主动加进去（走对应的 normalize），但**漏加不会再丢数据**。

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
| `packs` | 按 `id` 去重并集，合并后按 `at` 主键 + `id` 次键排序（同分钟两包顺序必须两端一致）。`cf` 只要任一端有值就保留 |
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
