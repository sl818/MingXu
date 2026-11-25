# 前端结构 · index.html

> 单文件，17,772 行 / 约 880 KB。这份文档是它的**内部地图**。
>
> 配套阅读：`ARCHITECTURE.md`（整体）、`DATA-MODEL.md`（字段含义）。

最后更新：v119（2026-11-19）

---

## 1. 文件内部地图

`index.html` 由 **3 个 `<script>` + 一个外置 `assets/app.css` + 一段固定的骨架 HTML** 组成。
（v116 之前是 6 个内联 `<style>`，已原样外移，见 1.2。）

### 1.1 三个 script

| 位置 | 内容 | 说明 |
|---|---|---|
| `<head>` 里第一个 | 主题预置 | 同步执行，读 `localStorage` 设 `data-skin` / `data-layout` / `data-theme`，**防首屏闪白** |
| `<head>` 里第二个 | 安装检测 | `fetch('api.php?action=status')`，未安装就跳 `install/` |
| 文件末尾 | **主脚本（全部业务逻辑）** | 一个巨大的 IIFE；用 `const ACTIONS = {` 定位 |

具体行号会随改动漂移，**不要写死，用上面的特征串搜**。

**为什么主题要在最前面同步执行**：如果等主脚本加载完再设主题，用户会先看到一帧浅色再跳深色。
这段代码不能改成 `defer` 或 `async`。

### 1.2 CSS：`assets/app.css`（v116 起外置）

原来是 6 个内联 `<style>` 块，v116 原样搬到 `assets/app.css`（逐字节一致），
**顺序不变、越靠后越优先**：

| 顺序 | 层 | 约行数 | 管什么 |
|---|---|---|---|
| 1 | 基础层 | 786 | 设计变量、布局骨架、通用组件、各页面雏形、弹窗、提示、响应式 |
| 2 | `visual-v2` | 1,599 | 视觉重构：侧栏、主区、按钮、今日 Hero、习惯卡、待办、看板、日历、统计、设置、深色 |
| 3 | `skins` | 403 | 内置皮肤变量（paper / slate）+ 组件改用主题变量 + 主题选择 UI |
| 4 | `new-pages` | 438 | 统计卡、本月回顾、体重折线、更多抽屉、移动新建面板、悬浮 ＋、呼吸卡 |
| 5 | `layout-v3` | 342 | 三布局、Hero 战报、导航分组、按钮三档、柱状三态、同步指示器 |
| 6 | `notify-v33` | 492 | 提醒面板、安装提示、推送中心 |

`<link rel="stylesheet" href="assets/app.css">` 放在 `themes/*.css` **之前**，
所以主题仍能覆盖它（顺序反了会让内联样式压死主题）。

**同名规则被定义多次是正常的**（`.main` 9 处、`.sidebar` 9 处），最后一条生效。
同上下文内共 166 组重复，但**不要手动合并**——它们是跨层覆盖，合并会移动规则位置、
改变与中间几百条规则的层叠关系。`e2e/css_dedupe.py` 只删「可证明被完全覆盖」的声明，
自动空间已经耗尽（跑一次只删掉几条）。详见 `assets/app.css` 顶部注释。

---

## 2. 启动流程

```
1. HTML 解析 → script#1 设主题（同步，防闪烁）
2. script#2 检查安装状态
3. script#3 执行：
   ├─ 常量定义（TAGS / PRIO / SKINS / NAV / VIEWS / ACTIONS ...）
   ├─ let state = seedState()
   ├─ cloudInit()            ← 异步：探测云端、拉数据
   │    ├─ cloudProbing = true  → render() 画骨架屏
   │    ├─ cloudFetchMe()       → 有会话？拉 load
   │    ├─ 有数据 → cloudApplyRemote() → 覆盖 state
   │    └─ 无数据 → normalizeState(种子) → cloudPush(true) 首次上传
   ├─ render()               ← 首次真实渲染
   └─ setInterval(remindSync, 60000)  ← 每分钟检查页内提醒
```

**骨架屏的关键条件**（`render()` 开头）：

```js
if (!cloud.error && !cloud.ready && (cloudProbing || cloud.user)) { 画骨架; return; }
```

三个条件缺一不可：
- 必须在 `mode === 'landing'` 判断**之前**，否则启动时永远走落地页
- `!cloud.error` —— 请求失败必须放行，绝不能把用户锁死在骨架上
- `cloud.user` —— 已登录才等云端；未登录直接用种子数据

---

## 3. 状态与持久化

### 3.1 唯一真相是 `state`

```js
let state = seedState();   // 模块级变量，不是 window.state
```

**所有 UI 都是 `state` 的投影。** 改数据只改 `state`，然后 `render()`。

`state` 的完整字段见 `DATA-MODEL.md`。这里只说三个容易搞错的：

- `state.view` 会被写进 state（用于恢复上次页面），但**视图筛选条件不写**（如 `boardTag`、`selectedDate`）
- 纯视图状态（当前看板筛选、双击展开的任务 id、用药卡轮播索引）是**独立的模块级变量**，
  刻意不放进 `state`，否则翻个卡都会触发云同步
- `cloud.*` 是另一个对象，管同步状态，与 `state` 无关

### 3.2 加载时的清洗链

```
localStorage / 云端 JSON
      ▼
normalizeState(data)        ← 类型校验 + 补默认值（每个字段都有）
      ▼
migrateState(data)          ← 按 schemaVersion 顺序迁移（v1→v6）
      ▼
Object.assign(seedState(), data)   ← 用种子兜住缺失的顶层字段
```

**`normalizeState` 里有一段容易忽略的逻辑**：如果 `bodyProfile` 没有 age/height，
会从最新一条体重记录里反填。因为旧版本体重记录自带这两个字段。

### 3.3 保存

```js
save()  →  300ms 防抖  →  cloudOnLocalChange()  →  cloudPush()
```

`cloudPush()` 的要点：
- 并发保护：`cloud.pushing` 为真时只记 `pushAgain`，不重入
- 用 `cloud.dirtySeq` 判断"发出去的这版是不是最新的"
- 传 `base_rev`，云端 rev 不一致会返回 409 + 远端数据
- 收到 409 → `mergeStates(remote, local)` → 重新 save 一次（只重试一次，不循环）

---

## 4. 渲染管线

```js
render()
 ├─ 同步 dataset.theme / dataset.skin / body.dataset.view
 ├─ 骨架屏分支（见上）
 ├─ 落地页分支（mode === 'landing'）
 ├─ 画侧栏 #nav（wide 布局带分组标题）
 ├─ 画移动端 #mobile-nav（4 tab + 悬浮 ＋）
 └─ $('#main').innerHTML = remindBannerHtml() + installTipHtml()
                          + VIEWS[view]() + siteFooter()
    └─ bindView()               ← 挂非委托类的交互（拖拽等）
    └─ updateSyncIndicator()
    └─ remindSync()
```

**`render()` 是全量重绘**：整个 `#main` 的 `innerHTML` 被替换。
这意味着：

- 局部的 DOM 引用会失效，不要在闭包里缓存 DOM 节点
- 滚动位置靠 `window` 滚动（不是容器滚动），所以重绘不影响滚动位置
- 输入框里的内容会丢——所以表单都在弹窗里，弹窗自己管理，不随页面重绘

**什么时候必须手动调 `render()`**：改了 `state` 且想让界面立刻变。
大部分 `ACTIONS` 的处理函数末尾都有 `render()`。

---

## 5. 十二个视图

`VIEWS` 常量把 key 映射到函数。`data-nav` 的值就是这里的 key。

| key | 函数 | 页面 | 主要容器类名 |
|---|---|---|---|
| `today` | `viewToday()` | 今日 | `.hero` `.vital-grid` `.board` `.rail` |
| `meds` | `viewMeds()` | 用药 | `.med-board` `.med-group` `.med-row` `.med-stats` |
| `quit` | `viewQuit()` | 戒烟（**独立事件流，不走 `checks`**） | `.quit-page` `.quit-top` `.quit-hero` |
| `board` | `viewBoard()` | 待办（看板） | `.board-shell` `.board-col-wrap` `.board-rail` `.task` |
| `money` | `viewMoney()` | 清债 | `.money-kpi` `.money-curve` |
| `habits` | `viewHabits()` | 习惯管理 | `.habits-wrap` `.habit-row` `.habit-today` `.habit-sort` |
| `weight` | `viewWeight()` | 体重 | `.weight-row` `.chart` |
| `essays` | `viewEssays()` | 随笔 | `.essay-card` |
| `calendar` | `viewCalendar()` | 日历（月 / 周两种）+ 倒数日 | `.cal-layout` `.cal-grid` `.cal-cell` · 周视图 `.wk-*` · `.cd-*` |
| `stats` | `viewStats()` | 统计 | `.panel` `.chart` `.adh-*` `.sum-table` `.ts-*` |
| `config` | `viewConfig()` | 配置（v71） | `.notice-row` `.notice-warn` `.ntf-box` |
| `settings` | `viewSettings()` | 设置 | `.layout-grid` `.theme-grid` |
| `more` | `viewMore()` | 「更多」页 | `.more-grid` `.more-card` |

**习惯页布局（v66）**：`.habits-wrap` 有归档时是两栏 `minmax(0,1fr) 340px`
（左 `.habits-main` 我的习惯、右 `.habits-arch` 已归档），没归档时**退回单栏占满**——
不留一块常年空着的板。`<900px` 自动变单列。容器**不设 `max-width`**，宽度交给 `.main`（见下节）。

### 配置页（v71 / v73 改单栏）

容器是 `.config-wrap`，**不要复用 `.settings-wrap`**——后者在 `≥1180px` 且 top 布局下是
`columns:2` 瀑布流。配置页每块都要横向读（通知列表、推送配置、安装说明），分两栏会把
阅读顺序打乱（按列读），v71 直接套 `.settings-wrap` 就是这个后果。
宽度依旧交给 `.main`，`.config-wrap` 只写 `max-width:none`。

第 11 个页面，`viewConfig()`。三块：

1. **自定义通知**（`noticePanelHtml` / `noticeModal` / `saveNoticeForm`）
2. **提醒** —— 从设置页整块搬来的 `remindPanelHtml()`：系统通知 + 日历订阅 + 企业微信推送 + 安装提示
3. **数据管理**（`dataPanelHtml()`，从设置页抽出成函数）

`noticePanelHtml` 顶部有一条 `.notice-warn`，写企业微信的硬限制：**同一分钟 20 条以上会静默丢弃**，
多条通知要错开 5 分钟；cron 只往前补 3 分钟，卡住更久就漏。表单里也放了同一句。

单次通知「日期 + 时刻」过了就显示「已过期」并给「重发」。判定是 `noticePast(n)`，
**判到分钟、不只比日期**：今天 11:40 那条，到 12:13 就已经发完，只比日期会让它整天
都显示成还有效（v73 修）。重复通知永远不会过期。
过期行加 `.past`：底色退到 `--surface`、边框改虚线、正文 `line-height` 划掉且用 `--muted`。
**不给整行加 `opacity`**——会把底色一起压淡，深色皮肤下更糊，对比度也测不准。
`<560px` 时 `.notice-acts` 整体落到下一行右对齐，否则「重发」+ 三个图标会把正文压成三行。
走 `push_test` 带 `text` 参数直接把原文再发一次。

`weeks` 用七个方块多选（`.wk-pick` + `data-act="notice-wk"` 切 `.on`），周一到周日排，
但存的是 0-6（周日=0），跟全站一致。

表单按 `mode` 显隐字段：`#nf-date` / `#nf-weeks` / `#nf-md` 三个块，`hidden` 切换，
必须在 `openModal` 之后手动绑 `change` 才生效（没有全局联动机制）。

### 页面宽度约定（v67）

内容宽度只由 `.main` 决定：默认 `max-width:1240px`；`data-layout="top"` 且视口 ≥1520 时放宽到 1680。
页面级的包裹容器（`.habits-wrap` / `.settings-wrap` …）**不要再写 `max-width`**。

原因：`.main` 是 `flex-direction:column`，子项带 `max-width` 又没 `margin:auto` 时会被顶到左边，
右边留一条空白，跟今日 / 用药 / 待办（都铺满）对不齐。这个坑踩过两次：
`.settings-wrap` 曾是 860px、`.habits-wrap` 曾是 1140px，大屏上都表现为「内容左靠」。

真要限宽只有两种写法：

1. **居中**：`max-width:1040px;margin-left:auto;margin-right:auto`（`.cal-wrap` 就是这么写的）；
2. **铺满 + 内部改多列**：`.settings-wrap` 在 ≥1180px 且 top 布局时走 `columns:2` 瀑布流。
   单列铺满会把说明文字拉成一行上百字、排版预览卡拉成横条。

`columns` 不用 `grid` 的原因：grid 行优先，「排版」会被旁边的「主题」拉高，下面留一大块空洞；
瀑布流按高度堆，卡片之间不留空。代价是 DOM 顺序按列读，Tab 焦点跟视觉不完全一致，设置页可接受。

管理行右侧的 `.habit-today` 是「今日状态灯」：保持类看 `countOf >= target`，
戒除类看 `met()`（不点就是守住）。实心 `✓` = 今天达标，空心 `—` = 未达标。
**未达标态不能用 `opacity` 压淡**——会把边框一起压没，深色主题下整圈看不见；
边框走 `--line-strong`、文字走 `--muted`。

> 表格里的类名都取自代码实际值。这类名字记错不会报错，只会让你 grep 不到东西，
> 所以新增文档时请照着代码写，不要按印象写。

**导航相关常量**（都在主脚本顶部附近）：

```js
NAV         // PC 侧栏（15 项）：仪表盘 · 用药 · 戒烟 · 喝水 · 运动 · 478呼吸法 · 待办 · 清债 · 习惯 · 体重 · 随笔 · 日历 · 统计 · 配置 · 设置
MOBILE_NAV  // 手机底部：[今日, 用药, ＋(__add), 待办, 更多(__more)]
MORE_KEYS   // 手机「更多」抽屉里的 key 列表
MORE_PAGES  // 「更多」抽屉的内容（含 label / desc）
```

v119 配置页（`viewConfig()`）在「自定义通知 / 提醒」之间多一块「邮件提醒」，
由 `mailPanelHtml()` 渲染，四个动作 `mail-test` / `mail-save` / `mail-off` / `mail-cancel`。
授权码输入框 `id="mail-secret"` 永远留空：后端不回显明文，留空即保留已存值；
改样式要同时看 `.mail-grid` 与 `.mail-result`（`assets/app.css` 末尾）。

`NAV` 只是**字典 + 默认顺序**，实际渲染顺序统一由 `orderedNav()` 算（v86）：
先按 `group`（记录 / 回顾）分段，段内按 `state.navOrder` 排，没排到的按默认补后面。
改默认顺序改 `NAV`；用户自己调的顺序存在 `state.navOrder`，设置页「导航顺序」只给组内 ↑↓。
手机底部 `MOBILE_NAV` 是固定 4 格 + 「+」+「更多」，**不跟随排序**；
「更多」抽屉（`morePagesSheet`）跟随 `orderedNav()`。
`verify-v15.py` 里有硬编码的期望顺序（`EXPECT_NAV`），改默认顺序要同步；
用户排序的行为由 `verify-nav-order.py` 锁。

---

## 6. ACTIONS 调度（读这一节理解"点一个按钮发生什么"）

### 6.1 唯一的点击入口

```js
document.addEventListener('click', e => {
  const navEl = e.target.closest('[data-nav]');
  if (navEl) { goView(navEl.dataset.nav); return; }          // 切页

  const el = e.target.closest('[data-act]');
  if (!el) return;
  const fn = ACTIONS[el.dataset.act];
  if (fn) { e.preventDefault(); fn(el, e); }                 // 干活
});
```

**全部 106 个交互都走这一个监听器**，没有一处是 `addEventListener('click')` 到具体按钮上。

### 6.2 加一个新按钮要改哪里

以"删除某条随笔"为例（`essay-del`）：

1. **渲染时输出属性**：`'<button data-act="essay-del" data-id="' + esc(e.id) + '">删除</button>'`
2. **在 `ACTIONS` 里加键**：
   ```js
   'essay-del': el => { ...; save(); render(); },
   ```
3. 处理函数里用 `el.dataset.id` 拿参数

**没有第 4 步。** 不需要注册事件、不需要手动绑定。

### 6.3 硬规则

- **`ACTIONS` 的键必须和 `data-act` 的字面值完全一致**。`_check_script.mjs` 会扫全文对比，
  发现"有 act 没有 handler"就报警。
- **handler 的 act 如果由表达式拼出**（如 `el.dataset.act = cond ? 'med-take' : 'med-undo'`），
  自检脚本会报 `handlers without literal use`。这是既有现象，不是回归。
- **`data-act` 和 `data-nav` 不要混用**。`data-nav` 只用于切页。

### 6.4 106 个 act 按功能分组

| 组 | act |
|---|---|
| 日期与视图切换 | `date-shift` `date-today` `pick-week-day` `cal-today` `pick-day` `month-shift` `set-stats-range` `set-weight-range` `stats-log-toggle` `today-expand` `today-collapse` |
| 习惯打卡 | `habit-inc` `habit-dec` `habit-set` |
| 待办 | `task-toggle` `task-move` `task-restore` `task-new` `task-edit` `task-del` `board-quick` `board-tag` `board-filter-day` `board-filter-clear` `board-focus` `clear-done` |
| 归档 | `archive-open` `task-archive` `task-unarchive` `task-archive-del` `archive-clear` |
| 用药 | `med-new` `med-edit` `med-toggle` `med-del` `med-open` `med-next` `med-take` `med-undo` `med-prn` `med-prn-undo` `med-card-prev` `med-card-next` `med-card-pick` |
| 库存 | `stock-check` `stock-check-save` |
| 统计与小结 | `month-summary` `print-summary` |
| 体重 | `weight-new` `weight-edit` `weight-del` `profile-edit` |
| 随笔 | `essay-new` `essay-edit` `essay-del` `essay-tag-filter` |
| 习惯管理 | `habit-new` `habit-edit` `habit-archive` `habit-restore` `habit-del` `habit-sort` `breathing-start` |
| 搜索与命令 | `search-open` `cmd-run` `search-pick` |
| 提醒 | `remind-dismiss` `remind-go` `notify-on` `notify-off` |
| 日历订阅 | `ics-copy` `ics-reset` `ics-export` |
| 手机推送 | `push-edit` `push-cancel` `push-save` `push-test` `push-off` `push-refresh` |
| 云账号 | `cloud-login` `cloud-register` `forgot-password` `cloud-account` `cloud-logout` `cloud-sync` `cloud-retry` `sync-dismiss` |
| 管理员 | `admin-panel` `admin-reset` `admin-toggle` |
| 数据导出 | `export-json` `export-csv` `import-json` `reset` |
| 版本历史 | `history-open` `history-preview` `history-restore` |
| 外观 | `theme` `set-mode` `set-layout`（`set-skin` 已删除） |
| PWA | `app-install` `install-skip` |
| 移动端 | `more-open` `more-go` `quick-add` |
| 其他 | `set-mood` `help` `close-modal` |

---

## 7. 组件函数索引（305 个顶层函数，按用途分组）

不用全记，知道**去哪找**就行。

### 7.1 数据层

| 函数 | 作用 |
|---|---|
| `seedState()` | 全新用户的数据模板 |
| `normalizeState(data)` | 加载时清洗 + 补默认值 |
| `migrateState(data)` | 按版本号迁移 |
| `save()` | 防抖保存 |
| `emptyState` 不存在 | 用 `seedState()` |

### 7.2 习惯与打卡

`countOf(d,id)` `setCount(d,id,v)` `logHabit(id,delta)` `met(h,d)` `activeHabits(d)`
`dayStats(d)` `rateOver(days)` `dayQualified(d)` `overallStreak()` `habitStreak(h)`
`habitDueOn(h,d)` `habitMonthRow(h,y,m,upto)` `habitMonthOverview()`（习惯页本月概览，v109）
统计页「习惯」面板的「本月」分段也渲染同一个 `habitMonthOverview()`（v115）——
两页数字逐字一致；切到「近 N 天 / 时间线」时**不显示**，口径不同别混在一起。

**习惯页「本月概览」（v109）**：

- 位置：`viewHabits()` 在 `page-head` 之后、`habits-wrap` 之前插入 `habitMonthOverview()`；
  没有可统计的习惯时返回空串，不留空板。
- **达标** = `met(h,d)`，和今日 / 日历 / 统计同一个判定，不另立口径。
- **应打卡** = `habitDueOn(h,d)` 按 `notifyFreq` 逐日判断：`daily` 每天、
  `weekly` 每周 `notifyWeekday` 那一天、`monthly` 每月 `notifyMonthday` 那一天。
  **不能写成「本月过了 N 天就除 N」**——每周一次的习惯会被算成 4% 达标率。
  `createdAt` 之前的日子不算，新建的习惯不该为上月全勤背锅。
- **周日的 `notifyWeekday` 是 0**，`Number(x) || 1` 会把它当成周一（0 是 falsy）。
  必须用 `isFinite()` 判断。日历「建议时间」那块（`suggestTime` 分支）有同样的历史写法，
  改到这里时没动它，因为不在本需求范围。
- **用药（`h.med`）当天没有排期（`medScheduledCount(d) === 0`）就不计入应打卡**，
  「没有用药需求就不参与」。有排期时参与排名，标题旁会标「（含用药）」——
  管理列表里 med 卡不显示，不标的话数字对不上会被当成 bug。
- **排名**：只让「本月应打卡 ≥5 次」的习惯参与，按达标率降序、同率看天数。
  低频习惯（每周一次最多 4 次）不进排名：比天数它永远垫底，比比率它又能拿 100%。
- **两栏不重复**：「从未完成」= 本月 0 天；「达标最低」只在「至少达标过一天」里挑。
- **环比**用「上月同期」（上月 1 号到上月的今天号），月中就跟整月比会永远显示下降。
- 手机（≤860px）三个数字卡仍排三行一列的三列，副文案切短版（`.hs-short`），
  否则 360px 下「应打卡 101 天」会把「天」挤到第二行。

**戒烟（`type === 'quit'`）走事件流，不走 `checks`**，函数是一套独立的：

`craveList()` `cravingsOf(hid)` `dayCravings(hid,ds)` `lastSmokeTs(hid)` `quitStartDay(h)`
`quitStreak(h)` `quitTotal(h)` `quitBest(h)` `quitRange(h,days)` `craveHours(hid)`
`craveTriggers(hid)` `quitSaved(h)` `quitNextMile(streak)`
`packSpans(h)` `spanOf(h,pack)` `currentSpan(h)` `currentPack(h)` `packUsed(h,pack)`
`packOrphans(h)` `packStock(h)` `packSpanTextOf(span)` `packSpanText(sec)`
`packSpan(h,pack)` `packGridHtml(h)` `packCompareLine(h)` `dtLocalVal(ts)`
`addCraving(hid,kind)` `undoCraving(hid)` `craveTagModal(eid)` `tsDay(ts)` `tsHHMM(ts)`
`habitById(hid)` `isSmoke(h)` `isQuitLike(h)` `quitWord(h)` `craveCn(k,h)` `quitSlips(h,d)`

**习惯三种 `type`，靠类型本身区分，不用子字段**：

| type | 名称 | 点一下的含义 | 卡片形态 |
|---|---|---|---|
| `build` | 保持（早睡） | 今天达标 | 目标 1：「今天完成」通栏按钮；2-6：`pips` 格子；>6：`stepper` |
| `quit` | 戒除（不熬夜） | **今天没守住**，不点就是守着 | 横条空心 = 失守；v103 起**不再显示失败次数** |
| `smoke` | 戒烟（`h_drink` 唯一一条） | 双按钮「点一根 / 忍一次」 | 烟盒宽卡 `quitCard` |

- **`quit` 和 `build` 的卡片是同一副骨架**：`habit-head`（图标 + 标题 + 右上角状态）+ 打卡控件 + 证据层（v100）+ 备注。
- **v100 证据层 `habit-proof`（小习惯卡，不含常驻）**：连续天数从标题小字提成卡片主数字
  （`.hp-num b` 24px），右侧七个 `.hd-dot` 是最近 7 天（含当天）点阵——亮 = 达标、
  半亮 = 多目标的部分完成、红 = 戒断失守、虚线 = 那天没记录。
  数据全部现算（`checks` / `cravings`），**不存任何字段**；`streakOn(h,d)` 按当前选中日期算
  （切历史日期不撒谎），`habitWeek(h,d)` 出格子。单次卡不再显示 `0 / 1 次`，
  也不再画 `.habit-bar`；多目标的 n/m 计数与 pips 保留。
- **打卡回馈（v102）**：`habitPulse(id, 'on'|'slip')` 在 `render()` **之后**用
  `element.animate()` 放大「刚点的那颗控件 + `.hd-dot.today`」，同时 `navigator.vibrate`。
  必须排在重绘之后——CSS 动画会随每次 render 重放，翻页都在闪。
  撤销与 `prefers-reduced-motion` 下只震动不放动效。定位靠卡片根的 `data-hid`。
- **最长纪录（v102）**：`habitBest(h, d)` 取历史最长连续，只在 `best > streak` 时以
  `.hp-cap` 小字追加「· 最长 N 天」；两者相等不显示，否则一句话两个数字容易看混。
- **截止型习惯（v101）：`h.deadline` 是 `'HH:MM'`，**只对 `build` 且 `target<=1` 生效**
  （多次目标谈截止没意义，戒除/戒烟不需要）。打卡时刻不存字段：`checkTimeOf(h,d)` 从
  `state.events` 取当天最后一条 `delta>0` 的 `at`；`deadlineDiff(h,d)` 返回相对截止的分钟数
  （>0 超时），跨零点按「前一晚 → 次日凌晨」归一。卡片标题下写「01:00 前」，状态位打卡后
  直接写完成时刻、超时加 `.bad`。**不改 `met`**：超时照样算完成，只在卡片标记。
- **多目标卡布局（v102）**：圆点与「n / m」同一行 `.habit-pips-row`，
  `min-height:36px` 与 `.habit-done` 对齐。**圆点不能删**——它是一次点选的控件
  （点第 3 格就记 3 次），换成步进器会把「8 杯水」变成点 8 下。
- **`habitCard(h, d, compact)`**：`compact=true` 是常驻区窄卡（`vitalCard` 里的戒除卡），
  继续用旧骨架（圆圈状态灯 + 标题小字 streak + 进度条），v100 不波及常驻习惯。
  戒除的打卡控件分两档（`slipMode`，缺省 `once`）：
  - **单次**：中间那条 **`.pip`**（`flex:1` 撑满，一个点就是整条），「守住就填满，点一下取消」
    ——点了就是记一次未达标，再点撤销。`quit-mark` 是 toggle 语义。
  - **多次**（v79）：一颗 `.quit-add` 通栏按钮，未破「今天守住了」、已破「又失守一次」，
    点一次加一条；撤销是旁边那颗 `.quit-undo`，**只退最后一条，不清整天**。
    action 拆成 `quit-add` / `quit-dec`，**不要在 `quit-mark` 里 if 分支**——
    一个 toggle 语义、一个累加语义，混在一起最容易写成「点第二下就清零」。
    `.quit-add` 跟 `.habit-done` 一样自己定义背景，不继承 `.pip` 的皮肤渐变。
    `addCraving` 的 1 秒去重对 `multi` 必须跳过（否则一秒内连点只能记一次）。
- **保持类目标 1 次走 `.habit-done`（v74）**：以前这里也是 `pips`，但只有一格时 `flex:1` 会把它
  拉成整条，看不出是按钮。现在是一颗通栏按钮：未打卡写「今天完成」，打卡后变
  「✓ 已完成 · 点一下撤销」，`data-val` 给 1 / 0 复用 `habit-set`，不新增 action。
  **不做「已完成 / 未完成」两个并列按钮**：没打卡时「未完成」没有语义（本来就是未完成），
  只会常年白占一半宽度。滴答清单的「完成全部」、Loop / Streaks 的 toggle 都是单一主动作 + 二次撤销。
  目标 ≥2 仍是格子、>6 仍是 stepper，都没动。
  `.habit-done` **背景自己定义、不继承 `.pip` 的皮肤渐变**：渐变上白字的对比度算不出来
  （`bgOf` 遇到渐变整组跳过），这颗按钮上有真文字必须能真测。所以六套皮肤下它的观感
  来自 `--surface-2` / `--hc`，不是皮肤那套 `.pip` 覆盖。
- 右上角（v100）小习惯卡改成 `.habit-state` 文字（「已完成 / 待打卡 / 今天守住了 / 今天失守了」），
  不再用没有图例的圆圈；`compact` 常驻窄卡仍用 `.quit-dot` 状态灯。
  `.quit-dot`（`span`）**只是状态灯，不可点**：守住跟保持卡的 `✓` 一样是实心，
  破了是红边 + `!`（`broken`）。**别把它做成按钮**——两张卡的点按位置必须一致。
- `control` 的数字（v103 口径）：
  - 单次戒除卡**整行去掉**——横条空心就是失守，一周点阵和「连续守住」已经说清历史，
    再写「0 次未达标」是负向重复；
  - 多次戒除卡**只在真失守那天**才出现「今天 N 次 + 撤销」，写的是事实不是评判；
    没失守时整行不渲染，卡片高度也只在出事那天变高；
  - 多目标保持卡是「今天完成几次 / 目标」；
  单次保持卡 v100 起**不再显示**（点阵已表达，避免和按钮状态打架）。
- **备注只显示用户自己填的 `h.note`**，没填就不渲染整块（虚线也不出现）。
  不要给默认文案——那是替用户说话，还占掉他写自己规则的位置。
- `quit` 只记 `k === 's'` 事件（未达标），**没有 `r`**——不点就是守住，不需要第二条按钮。
  `smoke` 才两边都记（`crave` 两个按钮）。
- **所有文案走 `quitWord(h)` 词表**（`QUIT_WORD`），别在渲染里写死「点一根」。
- `isSmoke(h)` 是戒烟专属 UI 的唯一开关：`quitCard` / `quitHabit()` / `quitPanelBody()` / `pack-open` /
  `migrateQuitPack` 都靠它。**`isQuitLike(h)`** 是「两类都算戒除语义」，统计 / 连续天数 / 月历用它，
  写 `type === 'quit'` 会把戒烟漏掉。
- `smoke` 不出现在「添加习惯」的类型下拉里（它是内置常驻卡），编辑时给一个固定的展示项。
- 表单里烟专属字段用 `data-smoke-only` 控制，只有 `smoke` 显示；`quit` 只剩「开始日期」。
- **`.quit-dot.broken` 的选择器必须写成 `.habit-card .habit-check.quit-dot.broken`**：
  `themes/skin-*.css` 里是 `:root[data-skin="xxx"] .habit-check`（0,3,1），
  裸类名（0,2,0）会被皮肤样式压掉，破了看不出红边。

**常驻卡 `quitCard(h,d)`**（v50 起戒烟是第 5 张常驻卡，`PINNED_IDS` 把它排在最后）：

- **主视觉是「一包 20 支」的横向扁条烟格（`packGridHtml`），不是进度环。**
  环是「完成度」语义（运动卡那样），戒烟是「消耗」语义，硬套会拧。
  每格一支烟：上 34% 滤嘴（深色）、下面浅色烟身，10 支一排两行
### 常驻卡的顺序（v75）

`PINNED_IDS` **只负责「哪些 id 是常驻」这个集合**，顺序由 `orderedPinnedIds()` 决定：
先按 `state.cardOrder` 里排过的来，没排到的按 `PINNED_IDS` 原顺序补在后面。
所以数组里丢了某个 id，只会让那张卡回到默认位置，**不会让卡片消失**——这一点别改反。

交互是「排序模式 + ↑↓」，不是拖拽：卡片里全是「点一根 / 完成 / 撤销」这类密集按钮，
拖拽时手指一偏就会误触发；5 张卡用 ↑↓ 最多点 4 次，够用。

### 导入备份：不认识的字段必须原样带过（v78）

`handleImport` 走 `repairBackup(data)` 清洗，早期它是一张**白名单**：只有写进 return 的
14 个字段能活下来，其余一概丢弃。

导出是 `JSON.stringify(state)`（全量 20 个字段），导入是白名单（14 个）——**两边从来不对称**。
v68 之后陆续加的 `cravings` / `packs`（v68）、`notices`（v71）、`cardOrder` + `cardOrderAt`（v75）、
`countdowns`（v76）全都没同步进这张表。于是导入一次就等于把抽烟记录、买烟记录、自定义通知、
倒数日全部清空，紧接着 `save()` 又把这份残缺的 state 推上云端——**不可逆**。

现在：

1. 已知的新字段显式 normalize（`normalizeCravings` / `normalizePacks` / `normalizeNotices` /
   `normalizeCountdowns` / `normalizeCardOrder`）；
2. **其余不认识的顶层键原样带过**，兜底永远成立。

**铁律：以后新增任何顶层字段，`repairBackup` 的 return 必须同步。**
只维护白名单就是在赌「每次加功能都记得改这里」，赌输一次就是用户的全部数据。

`e2e/verify-import-keep.py` 锁这条：真实走一遍导入，断言六类数据条数一致、
陌生字段（`futureField`）也保留、刷新后仍在、配置页与日历页能正常渲染。

### 手机推送的 webhook（v77）

地址存在 **服务器**（`users.push_webhook`），不在浏览器里。
`tools/push_tick.php` 从库里读，所以**换手机、换浏览器、清缓存都不影响推送**。

界面上是两态（`pushEditing`，模块级 `let`）：

- **只读**：input 带 `readonly` + `.is-locked`（虚线边、浅底），按钮是
  「修改链接 / 发一条测试 / 暂停推送 / 刷新」
- **编辑**：点「修改链接」后清空、聚焦，按钮是「保存 / 取消」

两条铁律：

1. **`pushSave(enable, useInput)` 的第二个参数决定读哪儿的地址。**
   只读态的「暂停推送」必须传 `false`——用 `pushCfg.webhook`，不能用输入框。
   输入框在还没加载完时是空的，拿它保存会把服务器上的地址清空。
2. **`pushLoad()` 的重绘条件要包含 `config`**。v71 把面板搬到配置页时只写了
   `view === 'settings'`，于是异步加载完成后不重绘，输入框永远停在渲染那一刻的空值——
   这就是「切设备后要重新填」的真正原因（地址其实一直在库里）。

只有编辑态清空并保存才会删地址（带 `confirm`）。「暂停推送」只改 `push_enabled`。

- 入口在「今日打卡」标题栏右侧（`.sec-acts`），排序态换成「恢复默认 / 完成」
- `cardSortMode` 是模块级 `let`，纯视图状态，不进 state，刷新即退出
- 排序条 `.card-sortbar` 由渲染层**插在卡片 `</article>` 之前**，不去动
  `medCard` / `vitalCard` / `quitCard` 三个函数（它们结构各不相同，改三处风险更大）
- 排序态隐藏 `.pin-tag`（让位给 ↑↓），并给卡片内所有 `button/input/select` 关掉
  `pointer-events`，只放行排序条自己
- 标题栏的按钮**不能塞进 `.muted-sm`**：会继承那层灰字，浅色皮肤下只有 2.4–3.8 的对比度
  （审计抓的），而且透明底的 ghost 按钮背景判定会落到页面渐变上，永远算不过。
  所以按钮单独放 `.sec-acts`、用实底 `.btn`

- 尺寸跟其他常驻卡一致，**不跨列**。常驻卡为奇数张时最后一张落在下一行左列，
  贴左、单列等宽，右列空一格（5 张卡 2 列布局的必然结果，以后加第 6 个常驻会自动填满）
- 抽掉的烟加 `.out` = 变灰熄灭（`opacity:.22 + grayscale`）。**熄灭不要做粒子特效**——
  抽一根如果看着爽，就成了游戏
- 戒烟页上半是 `.quit-top` **左卡右日历并排**：`.quit-hero`（戒烟卡 `flex:1` 约 750px）
  + 日历 `.panel`（固定 360px），`align-items:stretch` 等高、月历格子 `grid-auto-rows:1fr` 拉伸填满。
  今日页窄卡仍是纵向堆叠（`quit-body` 默认 `flex-direction:column`）
- 没有买烟记录时格子里放「记一笔买烟」按钮（`pack-open`，直接开 `packModal`，
  不再 push 一条空白记录）
- **买烟记录折叠（v107）**：超过 5 条才渲染 `.qpack-fold`，收起只看最近 5 条，
  展开每次 +20 条（`.qpack-more`，按钮写「再显示 N 条（还剩 M 条）」）。
  状态是模块级 `quitPackOpen` / `quitPackShown`，**不进 state**——纯视图开关，
  换设备不该同步。收起时把 `quitPackShown` 复位，下次展开还是从 20 条起。
  条数以「包」为单位，一包一行。
- **一包烟的区间全是派生（v68）**：`packSpans(h)` 把「点一根」事件按包切成左闭右开区间，
  `openAt(k) = max(这包的 at, closeAt(k-1) + 1)`。`max()` 那一下就是「自动绑定下一包」，
  不用字段、不用用户点「开新包」。算法和三个派生量见 DATA-MODEL 5.5。
  卡面永远画 `currentSpan(h)`（第一个没抽满的包），熄灭格数 `Math.min(used, size)` ——
  以前 `packUsed` 是「开包之后的全部」，同一天买的两包会一起涨到 `22/20`
- **末支软确认（`cfBar`）**：最近一包抽完、48 小时内、还没确认过时，卡面挂一条 `.pack-cf`。
  不是弹窗、可以不理。「对」= 落 `pack.cf = closeAt`；「改时间」= `packCfModal` → `packCfForm`。
  只在这一个时刻问，因为时长只需要两个锚点（首支靠 `at`，末支靠这一下）
- 库存空还继续点「点一根」：**照记，不拦**。给一句 toast，卡面加「另有 N 支没归包」。
  记录是事实、归包只是口径 —— 置灰会制造数据黑洞，把「今天 X 支」也一起弄假
- 按钮行三格：`点一根 / 忍一次 / 撤销`，**撤销窄一格**（`grid-template-columns:1fr 1fr auto` +
  `padding:0 14px`）、底色更淡，无记录时 `disabled`。**不要加二次确认**——撤错再点一次就补回来了
- `addCraving` 的去重窗口只有 **1 秒**：再宽会挡住「补记今天抽了几支」那种连点
- **库存为 0 时「点一根」置灰**（`packBlocked(h)`）：当前这包抽满且没有下一包时，
  戒烟页按钮文案变「这包抽完了」，今日页窄卡同步置灰，`addCraving` 里还有第三道闸。
  一包 `size` 支，抽满就到底 —— 不放这道闸，「今天抽了几支」能涨到 21，
  而烟盒还是 `20/20`，两个数字打架就是用户眼里的「算错了」。
  卡面同时给一行「这包已经抽完 · 记一笔买烟后才能继续记」，按钮的出路写明白
- **按天清空记录（v70）**：页头「清空记录」（`.btn.danger-red`，在「记一笔买烟」左边）
  → `craveClearModal`，列出有记录的日期，每天一行一个「清空」。删的是当天全部 `cravings`
  （**含「忍一次」**，用户定的），点删除会 `confirm` 并报条数。只动 `cravings`，
  包靠区间重算自动变少，不用同步任何字段
- `.btn.danger-red` 必须带 `:root[data-skin]` 前缀。皮肤 CSS 的 `:root[data-skin="paper"] .btn`
  是 (0,3,0) 且加载在 index.html 之后，裸类名 (0,2,0) 会被压掉——颜色写上去了但不生效。
  跟 `.habit-check` 那次是同一个坑
- **补记昨天（v72）**：戒烟页今天会挂一条 `.pack-cf`「昨天这包还剩 N 支 · 补记」，
  点开 `backfillModal` 填数量（支数 + 忍的次数），一次生成多条记录。
  上限 = `backfillLeft(h, 昨天)`，即那包在昨天 23:59 的剩余，补不出第 21 支。
  **只允许昨天**（`saveBackfillForm` 里硬校验 `ds === fmt(addDays(now,-1))`），
  更早的日子用户自己也记不清。
  时间戳由 `backfillSlots` 按当天 06:00 起每 30 分钟一个槽生成，**起点不早于那包的 `openAt`**——
  早于开包的记录归不进任何包，会变成「未归包」，补了等于白补（这个坑第一版就踩了）。
- `packGridHtml(h, d)` 的 `d` 是新增参数：传历史日期就画「那天结束时的样子」
  （`spanOnDay` + `usedUntil`）。戒烟页永远传 `todayStr()`，这个分支只在今日页切历史日期时用。
- 涨落：`QUIT_MILESTONES` = 1/3/7/14/30/60/90/180/365，文案在 `QUIT_MILE_CN`

要点：

- `met()` 对 quit 的判断是「当天没有 `s` 事件」，不是「次数 = 0」——两类通用
- `habitStreak()` 开头就 `if (h.type === 'quit') return quitStreak(h)`，别往下走通用循环
- `addCraving` 有 **3 秒同类型去重**：手抖双击不该记成两次犯瘾
- 卡片按钮是 `crave-smoke` / `crave-resist`（`data-id` = 习惯 id），
  撤销是 `crave-undo`，补诱因是 `crave-tag`（`data-eid` = 事件 id）
- `craveHours` / `craveTriggers` **只统计 `s`**，口径要和「抵御率」区分开

### 7.3 用药与库存

`medById(id)` `isPrn(med)` `medActiveOn(med,d)` `medDoseSlots(med)` `medScheduledFor(d)`
`medScheduledCount(d)` `doseAt(d,mid,slot)` `medTakenFor(d)` `medTakenCount(d)` `medAllTaken(d)`
`medNextDose(d)` `takeDose(d,mid,slot)` `undoDose(d,mid,slot)` `logMed(...)`
`medStockBase(med)` `medStockUsed(med)` `medStockRemain(med)` `medStockDays(med)`
`medCourseLabel(med)` `medShortName(name)` `mealTimingText(med)` `defaultSlots(n)`

### 7.4 任务

`liveTasks()` `archivedTasks()` `pendingTasks(d)` `taskRepeatLabel(t)` `dueText(t)`
`nextRepeatDate(date,r,w,d)` `completeRecurringTask(t,d)` `uncompleteRecurringTask(t)`

### 7.5.2 考核算法说明弹窗（v81）

统计页头部 `考核算法`（`data-act="algo-open"` → `algoModal()`），把上面那套口径写成用户能读的说明，
九个部分：单个习惯怎么算做到 / 当天完成率 / 75% 门槛 / 日历颜色 / 连续达标 /
为什么只统计有记录的日子 / 月度小结的两个数字 / 用药任务戒烟的特殊口径 / 不参与考核的。

**这个弹窗是代码的镜像，不是文案。** 里面的阈值和判定必须和
`met()` / `dayStats()` / `dayQualified()` / `rateOver()` / `habitDayAcc()` / `taskStats()` 一一对应。
改了那几个函数的阈值或口径，**必须同步改这个弹窗** —— 说明跟数字对不上，比没有说明更糟。

`e2e/verify-algo-modal.py`（29 项）锁住结构：九个 `.algo-h`、四张 `.algo-table`、
关键阈值 75%、以及「达标天数 / 完成度」「创建时间」这些词还在。

样式：`.algo-card` 比默认 `.modal-card` 宽一档（`min(660px,100%)`），因为有两列表格。
`<560px` 时表格**整体改成块级**（`display:block` + 隐藏表头），每行变成「类型在上、判定在下」——
两列硬挤会把第一列压成竖排的「计/数/类」。

### 7.5.1 统计口径（v80）

**月度小结的「完成度」不是「达标率」。** 两个都留着，别合并：

| 列 | 算法 | 说明 |
|---|---|---|
| 达标天数 | `met(h,d)` 为真的天数 / 总天数 | 二元事实：那天完全做到了没有 |
| 完成度 | `Σ habitDayAcc(h,d) / 天数` | 按实际完成量折算 |

`habitDayAcc()`：戒除/戒烟 → 守住 1、破了 0；用药习惯 → 已服÷应服；计数类 → 实际÷目标（封顶 1）。

以前最后一列直接就是 `达标天数 / 天数`，喝水目标 9 杯、实际每天 3 杯 → **0%**，
跟一口没喝同分。而这份小结是要打印出来给医生的，那个 0 会被读成「完全没做」。

**`dayStats()` / `rateOver()` 不能跟着改**：它们的二元口径是「达标」的定义，
日历热力、连续达标天数、统计页柱状图、`dayQualified` 全挂在上面。改了会连带一片。
所以月度小结单独走一套 `habitDayAcc()`，弹窗底部那句「有记录的日子平均完成度」也用这套，
保证弹窗内部两个数字不打架。

**归档投放条（v108）**：`.arch-zone` 是看板下方**一条通栏**（76px 高、和 `.board-shell` 等宽），
不再是右栏里那个 300px 的小方块——原来拖拽时靶子太小，还容易甩进下方的倒数日里。

- 结构：`↓ 图标 + .az-txt`，`.az-txt` 里同时放 `.az-idle`（「拖到这里归档」）和
  `.az-hot`（「松手归档」），靠 `.is-over` 切换显隐，**不做位移/缩放**（会让整条在拖拽时跳一下）。
- 底色 `color-mix(in srgb,var(--text) 7%,var(--bg))`：`--surface-2` 在 paper 下和页面几乎同亮度，
  整条会看不出来；掺一档正文色才有一条「带子」的形。深色下会反过来自动变亮，方向同样对。
- 三种态：平时虚线 + hover 边框转 accent；`body.is-dragging` 时整条提亮成 accent-soft；
  `.is-over` 时实线 2px + 外圈 3px 光晕。
- 点击整条打开归档弹窗（`archiveModal`），拖放之外的入口。
- 手机端（≤760px）改纵向排列、高 88px，因为横排在 390 宽会把两行文字挤成一团。

**归档任务的只读详情（v108）**：归档弹窗每行按钮是 **查看 / 恢复 / 删除**（查看在最左）。
`taskArchViewModal(id)` 打开 `.task-view`：标题 + 备注全文（`white-space:pre-wrap` 保留换行，
空备注写「没有备注」）+ 字段列表。**只读**，没有输入框，底部只有「关闭」。
归档行那一排小字放不下备注，所以才需要这个弹窗。

**任务完成度面板**（`taskStatsPanel()`，待办页底部 + 统计页各一份）：

- 时间窗口按 **`createdAt`** 圈定，再看这批任务现在的状态。
  按完成时间圈会出现「本月新增 5、完成 20」（完成的是上月建的），数字对不上。
- 达成率 = `已完成 ÷ 新增`，**取消也算在分母里**（取消了也是没做成）。
- 「已归档」不是状态，是「从看板收起来」——一条任务可以既已完成又已归档，
  所以只做一句小字标注，不占那五格。
- `createdAt` 缺失的老任务退回 `due`，再没有就只进「全部」。
- 范围存模块级 `taskRange`（0 = 全部），和 `statsRange` 分开——两个面板在不同页面。
- **`cnDate` 只认 `YYYY-MM-DD` 之外的格式会自动走 `Date` 解析**：`createdAt` / `archivedAt`
  都是 ISO 串，直接喂给 `parseD` 会得到 `NaN月NaN日`（v108 踩过）。
  纯日期仍走 `parseD`，避免时区把日期推一天。

### 7.5 渲染组件（返回 HTML 字符串）

`habitCard(h,d)` `vitalCard(h,d)` `medCard(h,d)` `breathingCard(h,d)` `moveCardHtml(h,d)`
`taskRow(t,d)` `taskCard(t)` `taskDetailHtml(t)` `medRowHtml(med)` `medSheetHtml(d)`
`monthReviewBody()` `medTrendBody(range,days)` `monthSummaryData()` `openMonthSummary()`
`habitDayAcc(h,d)`（单日单习惯的完成度 0~1，只给月度小结用）
`taskPool(range)` `taskStats(range)` `taskStatsPanel()`（任务完成度，待办页与统计页共用）
`algoModal()`（考核算法说明弹窗，统计页头部按钮 `algo-open`）
`quitPanelBody(range)`（戒烟分析面板内容，没有 quit 习惯时整块不渲染）
`viewQuit()` `quitPageHead(h)` `quitCalPanel(h)` `quitSumPanel(h)` `quitHoursStrip(h)`
`viewMoney()` `moneyOverviewView()` `moneyDebtsView()` `moneyDebtsSummaryHtml(live,done)`
`moneySimulate(strat)` `moneyOrder(list,strat)`
`moneyPlanView()` `moneyCompareHtml()` `moneyTableHtml()` `moneyCustomOrderHtml()`
`moneyBudgetView()` `moneyBudgetSplit()` `moneyDailyLeft()` `moneySpendMonth()`
`moneyIncomeModal()` `saveMoneyIncome(form)` `moneyCatModal()` `saveMoneyCat(form)`
`moneySpendModal()` `saveMoneySpend(form)`
`moneyIntroModal()`（清债介绍：九节 + 来源外链）
`dayDebts(ds)`（还款日，月/周视图共用；只认 `due` 1–31，`0` / 空 = 没有具体还款日，v110 起这类债不上日历也不进提醒）
`moneyToolsView()` `moneyAprOf(cash,pay,n)` `moneyRateWords(apr)` `moneyRiskRows()`
`moneyFmt(n)`（金额显示：整数不补零、有角分补两位；**全页金额都走它，别再写 toFixed(0)**）
`moneyLogView()` `moneySnowModal()` `saveMoneySnow(form)` `moneyLogModal()` `saveMoneyLog(form)`
清债页头按钮**按子页切换**（v113 定稿）：预算 / 计划 / 记录 / 工具四页常驻同一组四个（清债介绍＝次级；添加收入 / 添加分类预算 / 记一笔开销＝三个 `primary`，同色），总览与债务两页是（清债介绍 / 记一笔债）——那两页要留住加债入口，对应 `nav` key 是 `budget` / `plan` / `log` / `tools`。预算页的三个动作**不要**再往板块里塞按钮——
需求要的就是「全部收到右上角」，空态只留文案指向右上角，否则 `data-act` 重复匹配。
分类预算对话框的举例是 `.mcat-tip`（两段：固定 / 日常），底 `--surface-2`、字 `--text`。

债务卡结构（v110 / v111）：名称 → 备注（`.mdebt-note`，带「备注」小标签）→ 金额 + 年化/月还/还款日（没有还款日就不写这一段）→ 进度条 + 「已完成 N%」→ 「当前已还 / 还剩」→ 编辑/删除。
**已还清的卡片**百分比写「已还清」、不渲染「还剩 ¥0」，且不再有「每月 N 日」。
页底汇总卡（`.mdebt-sum`，六格）分母是**初始总额**，与总览 hero 同一口径；
平均年化按**余额加权**，别改成简单平均。
清债列表行的可读性约定（v96）：`.mrow-name`（还款顺序里的债务名）`font-weight:700 / 13.5px`，
`.minc-name` / `.mcat-name` / `.mspend-cat`（收入 / 分类 / 流水里的名称）`700 / 13px`——
**不要用 600**：中文系统字体（微软雅黑 / 苹方）经常把 600 渲染成常规体，等于没加粗。
「这个月怎么分」的 `.mbud-bar` 四段用**固定图表色** `--chart-1..4`（蓝/绿/红/黄），
**不要挂 `--accent` / `--good` 这类语义色**——paper 皮肤里 accent 是鼠尾草绿、跟 good 撞色；
也不要退回 accent 的深浅 mix（62% 和 30% 实机不可辨）。任何「需要同时对比多段」的图形都用 `--chart-*`。
`moneyDebtModal(d)` `saveMoneyDebt(form)` `subTabOf(pageKey,tabs)` `subTabsHtml(pageKey,tabs,cur)`
`quitPacksPanel(h)`
`quitTrendPanel(h)` `quitTrendSvg(days,avg,range)`（抽烟趋势折线图，周/月/季切换）
`packModal(pack)` `savePackForm(form)` `quitHabit()`（戒烟页）
统计页（`viewStats`）v84 起是 6 块：总览 / 习惯 / 用药 / 戒烟 / 体重与 BMI。同主题用分段控件切（`.stab` + `statsSegHtml(act,cur,pairs)` 构造，`data-act="stats-habit-tab"` / `stats-med-tab`），
切换状态是模块级 `statsHabitTab` / `statsMedTab` / `statsQuitOpen`，**不进 state**——
进了 state 就要改 `normalizeState` / `mergeStates` / `repairBackup` 三处，且两端切换格不同会互相覆盖。
分区小标题用 `.sblock-head`（**不是 h3**），`.sblock` 带一条上分隔线。
- `monthReviewBody()` / `medTrendBody(range,rangeDays)` / `quitPanelBody(range)` 只返回内容，不带 `.panel` 外壳
- `quitSumCardsHtml(h,withHours)` 返回 12 张卡；`quitSumPanel(h)` 才是戒烟页用的整块外壳
- `taskStatsPanel()` 整块只在待办页底部；统计页把它压成总览末尾的一行——`taskStats(taskRange)` 取数，`.tk-grid`（三格固定三列）+ `.tk-bar` 细进度条，右上 `data-act="more-go" data-view="board"` 跳过去看五格明细
- 考核算法弹窗（v81 `algoModal`）**还没跟着 v84 的分区改口径**，待完善
数据汇总（`quitSumPanel`）**12 张卡** + 一根 24 小时时段条：今天 / 本周买烟 / 本月消费 /
平均每天 / 连续无烟 / 抵御率 / 每支成本 / 上次抽 / 减量进度 / 无烟天数 / 本周守住 / 近 4 周。
口径都写在小字上——本月消费按`买烟日期`算（看支出不看消耗），平均每天的分母是`戒烟天数`
（上限 30）而不是固定 30 天。时段条只数「抽了」，统计页那 24 根柱是同一份 `craveHours`
数据的另一套渲染，两者不要合并。

**v107 新增的四格**（`quitStartAvg` / `quitNowAvg` / `quitWeekAvgs`，全部现算、零新增字段）：

- **减量进度**：起始 7 天日均 → 近 7 天日均，给出降幅。起始日均 < 0.3 时显示 `—`，
  不硬算一个 0%（一开始就没抽的人没有「降」可言）。
- **无烟天数**：从 `quitStartDay` 到今天，一支没记的天数 / 总天数。戒除型不点就是没抽，
  所以「没记录」在这里按守住算——和月历里灰 `·` 表达的是同一件事。
- **本周守住**：本周已过天数里 0 支的天数。
- **近 4 周**：`.qs-spark` 四根柱（末根 `.last` 用 accent），末根是本周、可能不满 7 天。
  小字给首尾对比，柱高按最大值归一、最低 6px，保证「降到 0」也看得见。
- **「忍住了」改「抵御率」**：主数字换成百分比，小字给「想抽 N 次 · 忍住 M 次」。
  累计次数是过去式，抵御率回答的是「现在有多大把握」。
- `.qsum span b` **必须还原成 `display:inline;font-size:inherit`**：`.qsum b` 是给主数字的
  20px 块级，不覆盖会把「从 7.0 降到 3.0」拆成两行大字。
统计页复用同一套卡片：`quitSumCardsHtml(qh, false)`（`withHours=false` 跳过时段条，避免和戒烟分析的 24 根柱重复），分析内容 `quitPanelBody(range)` 默认折叠。
没有戒烟习惯时两块都不渲染。
戒烟月历可翻月：action `quit-month-shift` / `quit-month-today`，锚点是模块级 `quitCalMonth`
（纯视图状态，不进 state）。翻月只改月历标题和格子，不影响下方汇总和买烟记录。
「上一包对比」只在戒烟页宽卡显示（`quitCard` 第三个参数 `compare=true` 才渲染），今日页窄卡不塞。
`weightLineChart(list,profile)` `weightSummaryHtml(list)` `weightFatPanel(list)` `weightFatSpark(pts)`
体重页右栏（v114）`.weight-side` 里是「统计」+「体脂率」两张卡：grid 默认 stretch，
体脂卡 `flex:1` 吃掉剩余高度、`.hint` 用 `margin-top:auto` 沉底，右栏下方才不会留一块空白。
折线图 viewBox 是 **600×340**（v114 从 200 加高）——改高度会让 `verify-batch3` 里
「目标线在绘图区内」那类断言失效，所以测试改成从 viewBox 推上下边界，别再写死 174。
`waterWeekHtml(h)` `waterDistHtml(h,d)` `moveRingHtml(h,d)` `breathWavePath(cycles)`
`ring(ratio,size,stroke,color,track)` `icon(name)` `esc(s)`

**所有返回 HTML 的函数都必须对用户输入用 `esc()`**。全站有 216 处 `esc()` 调用。

### 7.6 弹窗

`openModal(html)` `closeModal()` `taskModal(t,status)` `habitModal(h)` `medFormModal(med)`
`weightModal(rec)` `essayModal(essay)` `profileModal(after)` `helpModal()`
`historyModal()` `archiveModal()` `quickAddModal()` `openStockCheck()` `openBreathingModal()`

配合 `bind*Form()` 系列挂表单提交。

**弹窗机制**：内容渲染到 `#modal-root`（`body` 的直接子元素），
所以打印样式可以只保留它、其余全部隐藏。焦点在打开前记录、关闭时归还。

### 7.6b 日历（月 / 周）

| 函数 | 作用 |
|---|---|
| `viewCalendar()` | 入口，按 `calMode` 分派到月或周；`cal-layout` 三块：日历 / `countdownPanelHtml()` / 三卡 |
| `viewMonth()` | 月视图：格子 = 完成度染色 + 待办 + 百分比 + 心情 |
| `viewWeek()` | 周视图：0:00–24:00 时间线 |
| `dayTasks(ds)` | 某天到期的未完成待办，按「优先级 → 开始时间」排 |
| `weekDayBlocks(ds)` | 某天的全部安排：`blocks`（有时间）+ `allday`（没时间） |
| `taskHitsDay(t, ds)` | 重复任务在某天是否命中（周视图靠它展开未来几周） |
| `monthHabitsInfo(y,m)` | 本月习惯统计，日历三卡和统计页共用 |
| `monthOverview(y,m)` | 日历页底部三卡（小结 / 心情 / 体重） |

### 日历页布局与倒数日（v76）

`.cal-layout` 是网格，宽屏（`≥1400px`）两列 `minmax(0,1fr) 340px`：左边日历、右边倒数日，
三张统计卡 `grid-column:1/-1` 跨两栏留在最下面。窄屏掉回单列，顺序是 日历 → 倒数日 → 三卡。

**日历卡片（`.panel.cal-wrap`）绝不能写 `max-width` + `margin:auto`。**
之前同时存在两处限宽（700px 和 1040px），后者覆盖前者；删掉 1040 之后 700 又浮上来，
日历又开始居中——表现为「标题左对齐、日历居中，右边空一条」。
现在两处都删了，宽度完全由网格列决定。`width:100%` 必须留着：`.main` 是 flex，
不给宽度会退化成 `max-content`，周视图 620px 的时间线会把面板撑出屏幕。

**倒数日（`countdownPanelHtml`）**

- 数据只有 `date` 一个日期，**不存「未来还是过去」**——`cdDiff(date)` 每次现算，
  存成状态明天就不同步了。
- 渲染分两组：未来（`n >= 0`）按天数升序、过去（`n < 0`）按距今升序（最近的在前）。
- 过去超过 3 个默认只露 3 个，`cd-more` 展开；`cdPastOpen` 是模块级 `let`，纯视图状态。
- 大数字区：`n > 0` 显示 `N 天`，`n === 0` 显示「今天」（`.today` 降到 15px），
  `n < 0` 显示 `N 天前`。**副标题只写日期**，天数不重复写第二遍——
  390px 下重复写会换行。
- `cd-toggle` 只开关通知，**不影响倒数天数**：还剩几天是事实，不该被提醒开关影响。

**表单（`countdownModal`）**

提醒档位 `CD_REMIND = [0,1,3,7,30]`，0 是当天，用 `.cd-rd` chips 多选（`cd-rd` 切 `.on`）。
默认「当天 + 提前 1 天 + 提前 3 天」。日期默认今天 + 30 天，免得每次都要点日历。


**周视图的两个关键设计**：

1. **同一时刻 + 同一类型合并成一块**。08:00 有十一个药时，并排分列每列不到 5px
   什么都看不见，所以合并成「用药 ×11」，点开看清单。
2. **块是绝对定位的**（`top = 开始分钟 / 60 × 44`），同列碰撞时往下挪，
   避免两个块互相遮住。

`calMode` / `calWeek` 是模块级变量，**不进 state**（切视图不该触发云同步）。

### 7.7 搜索与命令

`openSearch()` `closeSearch()` `searchResults(term)` `searchBodyHtml()` `searchLocate(it)` `searchGo(it)`
`parseCommand(raw)` `runCommand(cmd)` `findHabitByName(q)`

**关键设计**：`parseCommand` 是纯函数，不碰 `state`；`runCommand` 才改数据。
所以解析逻辑可以单独测。

### 7.8 提醒与通知

`remindItems()` `remindBannerHtml()` `remindSync()` `remindStop()` `remindDismissedOn()`
`notifyEnable()` `notifyDisable()` `notifyPing(force)` `notifyState()` `notifyMarkSent(keys)`

两者的区别：
- `remind*` = **页内横幅**，打开网页才看得到，每分钟自查一次
- `notify*` = **浏览器 Web 通知**，需要用户授权，安卓上常被杀后台
- 真正可靠的是**企业微信推送**（后端 cron），不在这两个体系里

### 7.9 日历（ICS）

`buildICS()` `icsEvent(...)` `icsFold(line)` `icsEsc(v)` `icsUtc(d)` `icsLocal(d)`
`icsAddDays(d,n)` `icsUtcCst(...)` `ICS_VTIMEZONE`

**`icsAddDays` 不是 `addDays`**：全局 `addDays()` 只保留年月日，会把时分清零。
日历推进必须用 `icsAddDays`。

### 7.10 工具

`todayStr()` `fmt(d)` `parseD(ds)` `addDays(d,n)` `clamp(n,min,max)` `uid()`
`esc(s)` `isPlainObject(v)` `download(fn,content,mime)` `csvCell(v)` `toast(msg)`

---

## 7.5 未登录页（v106 浅色暖调）

未登录时 `render()` 走 `mode === 'landing'` 分支：清空侧栏与移动 tabbar，把 `landingHtml()` 塞进 `#main`。
整页是**独立的一页**，配色**跟随当前主题**（默认 paper = 米色暖调），不另立一套固定色板。

- **色板**：`--lp-*` 这一层只是别名，值全部取自主题令牌 ——
  `--bg` / `--surface` / `--surface-2` / `--text` / `--muted` / `--line` / `--accent` / `--gold-soft`。
  所以换皮肤、切深色都会自动跟着变，**不要写死十六进制**。
- **底色是混出来的**：`color-mix(in srgb, var(--bg) 65%, var(--gold-soft))`。
  直接用 `--bg` 会偏冷白偏绿（paper 的 `--bg` 是 `#f2f5f1`），只有右上角一团金色光斑压不住整页；
  混 35% 暖色之后才是米色。深色模式下 `--gold-soft` 是暖深棕，同样成立。
- **次要文字不能直接用 `--muted`**：`#727a90` 在浅底上只有 3.9:1，11.5px 小字不达标。
  用 `color-mix(in srgb, var(--muted) 78%, var(--text))`（5.2:1）与 85%（4.8:1），
  深色下混入的 `--text` 变浅，方向同样正确。
- **主按钮前景用 `var(--on-accent)`**：深色皮肤下 `--accent` 是浅绿，写死 `#fff` 只有 1.9:1。
- **截图做 5% 暖化**（`filter:sepia(.05) saturate(1.04)`）：应用界面是冷白偏蓝，直接贴在暖底上色温打架。
- **类名统一 `lp-` 前缀**：`.lp-nav` / `.lp-hero` / `.lp-pages` / `.lp-notify` / `.lp-shot` …
  不要复用站内 `.card` / `.btn` / `.panel`，否则会被主题的 `:root[data-skin]` 规则压掉。
- **必须盖掉站内布局**：`:root[data-layout="wide"] .sidebar` 也是 (0,3,0) 且加载更晚，
  只写 `.app.landing .sidebar` 会被它按顺序反压回来。所以用
  `body[data-view="landing"] .app.landing .sidebar{display:none}`（(0,3,1)）。
  站内搜索悬浮按钮 `.search-fab` 同理要隐藏。
- **截图是真实截图**，放在 `images/landing/`：`today.jpg`（1212×700）、`stats.jpg`（1212×600），
  用演示数据截取（不含任何真实记录）。**不要改成懒加载**：懒加载在长截图/慢网下会先留一块空白。
  截图由 `#main` 的 boundingBox 裁出来，所以只有主内容区、没有侧栏。
  底部用 `mask-image` 淡出（不是盖一层渐变）——遮罩不需要知道背景色，换皮肤不会露馅。
- **登录/注册是弹窗**：页面顶部右上角两个 `data-act="cloud-login"` / `cloud-register"` 按钮，
  页面中间不再有登录卡片。
- **标题走衬线体**（`var(--font-serif)`）：这是暖调观感的一部分，换成无衬线会立刻变成"工具官网"。
- **`landing-note` 这段隐私说明被 e2e 锁着文案**（`verify-details1.py` 断言首尾字符串），改文案要同步改测试。

## 8. 主题系统

### 8.1 三层

```
dataset.theme  = light | dark      ← 明暗
dataset.skin   = paper | slate | mist | neu | retro        // v87 删掉 mono/clay/forest/cyber
                                      ← 9 套皮肤（4 套内置 + 5 套外部 CSS）
dataset.layout = top | side | wide  ← 三种 PC 布局
```

三个属性都挂在 `<html>` 上。CSS 里用 `[data-skin="paper"]` 选择器覆盖变量。

### 8.2 变量契约

皮肤只改 CSS 变量，不改组件规则：

```
--bg  --surface  --surface-2  --text  --muted  --line
--accent  --accent-soft  --on-accent  --bad  --good
--sidebar-bg  --sidebar-text  --radius  --shadow
```

组件规则一律写 `var(--accent)` 这种形式。**新皮肤只需提供一套变量值。**

### 8.3 加一套新皮肤

1. 在 `SKINS` 常量里加一项（key / name / desc / 预览色）
2. 新建 `themes/skin-<key>.css`，写 `html[data-skin="<key>"] { --bg: ...; }`
3. 在 `index.html` 的 `<head>` 加 `<link>`
4. **加进 `service-worker.js` 的 `ASSETS`**（否则离线时皮肤丢失）
5. 跑对比度审计：`e2e/audit-contrast-v33.py`

详见 `design/THEME-SPEC.md`（已失效，六皮肤已下线，见 `design/README.md` 的时效表）。

---

## 9. 移动端

### 9.1 断点

| 宽度 | 布局 |
|---|---|
| ≤ 560px | 手机：底部 4 tab + 悬浮 ＋ + 更多抽屉 |
| 561–1024px | 平板：顶部导航或侧栏 |
| > 1024px | 桌面：三种布局可切（top / side / wide） |

### 9.2 底部导航

```
[今日] [用药] [＋] [待办] [更多]
        ↑ 悬浮，凸出 tabbar，data-act="quick-add"
```

「更多」打开 `.page-sheet` 抽屉（`data-act="more-open"`），列出 `MORE_PAGES`。

**两个坑**（已踩过）：
- 抽屉遮罩带 `backdrop-filter`，会形成**包含块**，里面的 `position:fixed` 相对遮罩定位，
  不是相对视口。做底部抽屉时只抬遮罩，不要同时给抽屉设 `bottom`
- 抽屉里的类名用 `ps-` 前缀，不要用 `.more-grid`（560px 断点里有历史死规则会压成单列）

### 9.3 触摸热区

```css
@media (pointer: coarse) {
  .some-btn { position: relative; }
  .some-btn::after { content: ''; position: absolute; inset: -8px; }
}
```

**新增任何可点控件，必须同时加进这两组**，否则手指点不准。
已经漏过两批（`.remind-*`、`.backfill-today`）。

---

## 10. 云同步

### 10.1 关键对象

```js
const cloud = {
  available, user, rev, updatedAt, lastData,
  ready, probing, pulling, pushing, pending, pushAgain,
  error, conflict, dirtySeq, migrateLegacy
};
```

### 10.2 `cloudApi(action, body, query)`

所有请求的统一封装：
- 自动带 `credentials: 'same-origin'`
- 自动带 CSRF（从 `me` 接口拿到，存在内存）
- 非 2xx 抛错，错误对象带 `status` 和 `data`
- `data.code === 'session_stale'` 表示被其他设备顶替

### 10.3 冲突处理（这是最容易出错的部分）

```
本地 save(base_rev=5) ──► 云端 rev 已是 7
                            │
                    返回 409 + remote.data
                            ▼
              mergeStates(remote, local)   ← 逐字段规则见 DATA-MODEL.md
                            ▼
              normalizeState(merged)  →  set state
                            ▼
              save(base_rev=7)   ← 只重试一次
```

**`mergeStates` 的设计原则**：能并集就并集，不能并集才比时间。
- 数组类（habits/tasks/meds/weights/essays）：按 id 并集，本地新增补入
- `meds` 特殊：按 `updatedAt` 比新旧，库存基线额外比 `stockBaseAt`
- `checks`：同一天同一习惯取**较大值**（只增不减）
- `doses`：三层合并，时段级并集
- `moods` / `notes`：日期级，本地优先
- `events`：按 `at|id|delta` 去重并集

**`checks` 和 `doses` 必须分开合并**。曾经用同一段代码，`Number({})` 得到 `NaN → 0`，
把整瓶药的记录压成 0。这是"用药数据突然消失"的历史元凶。

---

## 11. 页内提醒 vs 手机推送

| | 页内提醒 | Web 通知 | 企业微信推送 |
|---|---|---|---|
| 触发 | `setInterval(remindSync, 60000)` | 同左，但需授权 | 服务器 cron 每分钟 |
| 前提 | 网页开着 | 网页开着 + 授权 | 都不需要 |
| 可靠性 | 低（关页面就没） | 低（安卓后台被杀） | 高 |
| 内容 | 横幅最多 3 条 | 系统通知 | 纯文本消息 |
| 去重 | `localStorage` 记日期 | `lifeboard.notify.sent` | 数据库 `push_sent` 表 |

**三者共用同一套"该不该提醒"的判断**（`remindItems` / `schedule.php` / `ics.php`），
但只在前者之间保持一致，见 `BACKEND.md` 第 5 节的对照表。

---

## 12. 前端陷阱清单

按被坑的次数排序。

1. **改完必须推进 `service-worker.js` 的 `CACHE`**，否则老客户端永远看旧页面。
2. **`index.html` 是 CRLF**，脚本改它必须 `newline=''`（见 ARCHITECTURE 不变量 4）。
3. **所有 class 由 JS 字符串拼出**。判断某个 CSS 类是否还在用，要搜
   `` `class="类名 `` 字面量，不能只扫 DOM——空种子数据时很多元素根本不渲染。
4. **同名 CSS 规则跨块覆盖**。`.tag-chip.active` 在 `#new-pages` 块里另有一条，
   在更早的块里加修正必须提权（`.board-tools .tag-chip.active`），单类选择器无效。
5. **`selectedDate` 是模块级 `let`**，`page.evaluate` 里读不到（ReferenceError）。
   测试要通过 DOM 或接口间接验证。
6. **纯视图状态不要放进 `state`**（筛选、展开、轮播索引），否则会触发无意义的云同步。
7. **`var(--bad)` 不能用于小字**：已删的 clay 皮肤当年 `#e08a7d` 在浅底只有 2.2:1（教训保留，新皮肤同理）。
   `var(--muted)` 不能用于彩色底（`--accent-soft`）上的小字，只有 4.2–4.49。
   两类都改用 `var(--text)`，层次靠字号和字重。**已踩三次。**
8. **`#modal-root` 是 body 直接子元素**。打印样式靠 `body > *:not(#modal-root){display:none}`
   清场，`.modal-backdrop` 必须从 `fixed` 改 `static`，否则只打一页。
9. **`h_med` 不是普通习惯**：它是用药卡的占位习惯，`met()` 看药品记录而不是 `checks`。
   遍历习惯列表且会跳转/管理的地方，都要想清楚要不要排除它。
10. **`h_breathe` 会自动补进 `habits`**（`ensureBreathingHabit`），所以
    `activeHabits(d).length` 比你以为的多 1，构造测试数据时要算上。
