---
name: 明序 MingXu
description: 可自托管的个人生活仪表盘；暖纸、白卡、一支红笔
colors:
  # 浅色（默认）
  paper: "#fbf3e7"
  card: "#ffffff"
  card-sunk: "#fffaf3"
  hairline: "#f0e4d1"
  hairline-inner: "#f4eadb"
  ink: "#2b2013"
  ink-soft: "#75644e"
  ink-faint: "#7d6d56"
  red-pen: "#dc2626"
  red-ink: "#c62828"
  red-wash: "#fde8e8"
  track: "#f6e7d4"
  # 深色（暖调，默认）
  coal: "#1a1512"
  coal-card: "#231c17"
  coal-sunk: "#2a221c"
  coal-line: "#3a2f26"
  coal-ink: "#f2e9dc"
  coal-ink-soft: "#a89684"
  coal-ink-faint: "#9a8a76"
  coal-red-ink: "#f87171"
  coal-red-wash: "#3d2a26"
  coal-track: "#3a2f26"
typography:
  display:
    fontFamily: "Inter, PingFang SC, Microsoft YaHei, sans-serif"
    fontSize: "22px"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "-0.01em"
  numeral:
    fontFamily: "Inter, PingFang SC, sans-serif"
    fontSize: "32px"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: "-0.03em"
  title:
    fontFamily: "Inter, PingFang SC, Microsoft YaHei, sans-serif"
    fontSize: "15px"
    fontWeight: 600
    lineHeight: 1.35
    letterSpacing: "0em"
  body:
    fontFamily: "Inter, PingFang SC, Microsoft YaHei, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.6
    letterSpacing: "0em"
  nav:
    fontFamily: "Inter, PingFang SC, Microsoft YaHei, sans-serif"
    fontSize: "13.5px"
    fontWeight: 400
    lineHeight: 1.4
    letterSpacing: "0em"
  meta:
    fontFamily: "Inter, PingFang SC, Microsoft YaHei, sans-serif"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.6
    letterSpacing: "0em"
  label:
    fontFamily: "Inter, PingFang SC, sans-serif"
    fontSize: "10.5px"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "0.12em"
  button:
    fontFamily: "Inter, PingFang SC, sans-serif"
    fontSize: "13px"
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: "0em"
rounded:
  tag: "5px"
  kbd: "4px"
  control: "8px"
  row: "10px"
  card: "12px"
  pill: "99px"
spacing:
  hair: "4px"
  tight: "6px"
  control: "8px"
  base: "12px"
  pane: "20px"
  page: "24px"
components:
  button-primary:
    backgroundColor: "{colors.red-pen}"
    textColor: "{colors.card}"
    rounded: "{rounded.control}"
    padding: "0 14px"
    height: "30px"
    typography: "{typography.button}"
  button-secondary:
    backgroundColor: "{colors.card-sunk}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "0 14px"
    height: "32px"
    typography: "{typography.button}"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.ink-soft}"
    rounded: "{rounded.control}"
    padding: "0 10px"
    height: "30px"
  nav-item:
    backgroundColor: "transparent"
    textColor: "{colors.ink-soft}"
    rounded: "{rounded.control}"
    padding: "0 9px"
    height: "29px"
    typography: "{typography.nav}"
  nav-item-active:
    backgroundColor: "{colors.red-wash}"
    textColor: "{colors.red-ink}"
    rounded: "{rounded.control}"
    padding: "0 9px"
    height: "29px"
  field:
    backgroundColor: "{colors.card-sunk}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "0 12px"
    height: "34px"
    typography: "{typography.body}"
  card:
    backgroundColor: "{colors.card}"
    textColor: "{colors.ink}"
    rounded: "{rounded.card}"
    padding: "14px 15px 13px"
  list-row:
    backgroundColor: "{colors.card}"
    textColor: "{colors.ink}"
    rounded: "{rounded.row}"
    padding: "9px 14px"
    height: "50px"
  chip:
    backgroundColor: "{colors.card-sunk}"
    textColor: "{colors.ink-soft}"
    rounded: "{rounded.pill}"
    padding: "0 9px"
    height: "23px"
  tag:
    backgroundColor: "{colors.red-wash}"
    textColor: "{colors.red-ink}"
    rounded: "{rounded.tag}"
    padding: "3px 6px"
---

# Design System: 明序 MingXu

## Overview

**Creative North Star: "暖纸、白卡、一支红笔"**

整套界面是一叠放在暖色纸上的白色卡片：纸底 `#fbf3e7`、卡面纯白、1px 沙色描边，没有阴影、没有渐变块面。颜色只有一个来源——一支红笔，只在两件事上落笔：**需要你现在处理的事**（逾期、失守）和**主操作按钮**。其余所有层级靠三件事分开：描边、底色的明暗差、字重。

这不是一套靠装饰取胜的皮肤，而是一套**秩序**：左边是分组导航，中间是一列定宽内容，每一页都从一句问候开始、以一条待办列表结束。任何页面都不允许长出第二列、不允许长出侧边抽屉、不允许在卡片里再套卡片。

对标来源是 Trackie（`trackie.free.nf`），只取它的版式语法（通栏顶栏 46px、可折叠侧栏 272↔62、1120px 定宽列、行式列表、Hero 唯一光）与配色逻辑（暖纸 + 白卡 + 单支红 + 双模式）。它的具体色值没有照抄——实测它的红字对比度只有 3.42、白字压红钮只有 3.76，都不到 AA；本规范用「两支红」修正，见 Colors。

**Key Characteristics:**
- 一套主题，明暗两态；浅色默认，深色为暖调炭褐（不是冷蓝黑）
- 唯一强调色是红，分填充红与文字红两支，各自达标
- 零阴影：分层靠 1px 描边 + 三级底色（paper / card / card-sunk）
- 两种排版同一套骨架：顶部导航条 / 左侧菜单栏，只换导航位置
- 主列填满可用宽度，纵向堆叠；只有常驻卡网格是多列
- 动效只做三件事：侧栏折叠、导航选中、主题切换

## Colors

暖纸底 + 纯白卡 + 沙色发丝线，全部层级由亮度差建立；红色是唯一的色相。

### Primary
- **行动蓝 Action Blue**（`#2C68FF`）：**创建类主操作**的底——新增、添加、新建、写一篇。白字在其上对比度 **4.71**，达标（hover `#1E55E6`）。它是全站唯一可以「填满一整颗按钮」的颜色，因为它只表示「开始创建一条新东西」，不表示任何状态。
- **红笔 Red Pen**（`#dc2626`）：留给**需要特别注意**的事——删除、重置、退出、逾期、失守，以及「今天还没做完」的提示。不再承担「新建」这件事。白字在其上对比度 **4.83**，达标。
- **红字 Red Ink**（浅色 `#c62828` / 深色 `#f87171`）：用于逾期、失守、**今天未完成的数值**与激活项文字。浅色底上 5.11，深色底上 5.29。
- **红晕 Red Wash**（浅色 `#fde8e8` / 深色 `#3d2a26`）：激活项与「今天」标签的底，永远不独立承担信息。

> 为什么是两支红：`#ef4444`（对标站原色）做白字按钮只有 3.76，做小字只有 3.42–4.46，全部不达标。一支红无法同时满足「深底上要够亮」和「白字压上去要够暗」，所以拆成填充与文字两支。

### Neutral（浅色）
- **纸底 Paper**（`#fbf3e7`）：页面画布。这是全站面积最大的颜色。
- **卡面 Card**（`#ffffff`）：卡片、列表、弹窗。
- **凹陷 Sunk**（`#fffaf3`）：输入框、用户卡、次级按钮——比卡面更接近纸色的那一档。
- **发丝线 Hairline**（`#f0e4d1`）：卡片与区块的 1px 描边；**内线**（`#f4eadb`）只用于列表行之间的分隔。
- **墨 Ink**（`#2b2013`）：标题与正文，14.47。
- **次级 Ink Soft**（`#75644e`）：说明文字，5.17。
- **弱化 Ink Faint**（`#7d6d56`）：最小号的元信息，4.55——**这已经是可用下限，不许再淡**。
- **轨道 Track**（`#f6e7d4`）：进度条底、环形进度未完成段、点阵未点亮格。

### Neutral（深色 · 暖调）
- **炭褐 Coal**（`#1a1512`）画布 / **炭卡**（`#231c17`）/ **炭凹**（`#2a221c`）/ **炭线**（`#3a2f26`）
- 文字 `#f2e9dc`（13.97）/ `#a89684`（5.89）/ `#9a8a76`（5.02）
- 红笔不变 `#dc2626`，红字降到 `#f87171`

### 备选：冷调深色
若最终选择对标站那种冷调深色，只替换这六个值，其余规范全部不变：
`#0f172a` 画布 / `#1e293b` 卡面 / `#2e3a4d` 描边 / `#f1f5f9` 正文 / `#93a2b7` 次级 / `#8b9bb0` 弱化 / `#3e2d3c` 红晕。

### Named Rules
**The Blue-for-Creation Rule.** 创建类主操作（新增 / 添加 / 新建 / 写一篇 / 记录第一次）用行动蓝 `#2C68FF`；**保存、确认仍然用红**，那是落定一件事的动作，不是开启一件事。红在别的场合（逾期、失守、删除）出现次数要克制，一页红太多就不灵了。

**The One-Pen Rule.** 红 = 还没做完。今天未完成、逾期、失守都可以红——但只落在**数值、主按钮、未完成的进度段**上，卡片描边与容器保持中性。已完成、达标一律中性色。一页出现四个红框就是失败：红是点，不是面。

> **例外（v146 · 日历周视图）**：周视图的事件块按内容分三类着色——用药绿 `#16a34a`、待办蓝 `#2563eb`、
> 习惯琥珀 `#d97706`（深色 `#4ade80` / `#60a5fa` / `#fbbf24`）。这是全站唯一允许出现红以外色相的地方：
> 「这一格是用药还是待办」必须在扫一眼时就能分开。三色只作用于 `.wk-ev-*` 与 `.wk-legend`，
> 不进按钮、状态徽标、文字与统计图表。

**The Two-Red Rule.** 填充用 `#dc2626`，文字用 `#c62828`（深色 `#f87171`）。永远不要拿填充红去写小字，也不要拿文字红去铺按钮底。

**The Faint-Is-Not-Text Rule.** `ink-faint` 是全站最淡的文字色，已到 4.55 的下限。需要更淡时只能降字重或缩短文案，不许再调浅——装饰性元素（图标、分隔、轨道）才允许低于 4.5。

## Typography

**Display / Body Font:** Inter，中文回落到 PingFang SC / Microsoft YaHei。系统栈优先，不加载 Web 字体。

**Character:** 一处很轻的克制：标题只比正文重一档（600 vs 400），层级靠字重与颜色而非字号拉开。这让人在一天里看十几次也不累，代价是弱化了「大字冲击」——需要冲击的地方交给数字（32px/700 + tabular-nums）。

### Hierarchy
- **Display**（700, 22px / 1.2, `-0.01em`）：Hero 问候语。全站唯一大于 22px 的非数字。
- **Numeral**（700, 32px / 1, `-0.03em`, 等宽数位）：常驻卡的主数值。单位另起 12px 次级色。
- **Title**（600, 15px / 1.35）：卡片标题、列表行标题。
- **Body**（400, **15px** / 1.6）：正文与说明。
- **Nav**（400/600, 13.5px）：侧栏项；激活项 600。
- **Meta**（400, 12px / 1.6）：行内元信息、卡片副标题。
- **Label**（700, 10.5px / `0.12em`）：区块标签（如「今日到期」「回顾」）。中文不用全大写，用字距模拟标签感。
- **Button**（600, 13px）：按钮文字。

### Named Rules
**The Fifteen Rule.** 正文定为 15px（对标站实测 13.5，按可读性要求上调一档）。15px 生效时行高 1.6、列表行高 50→52、卡片内距 +2px，密度不得靠压文字换回来。

**The Tabular Rule.** 所有会纵向对齐或被扫读的数字（毫升、次数、金额、天数）必须 `font-variant-numeric: tabular-nums`；单位、斜杠、副标一律切回正文体与次级色。

## Layout

**骨架**：`grid-template-rows: 46px 1fr`，第一行通栏顶栏，第二行侧栏 + 主区。

- **顶栏 46px**：折叠键 → logo 方块 24px → 产品名 → 1px 竖分隔 → 当前页名；右侧依次是搜索（含 `Ctrl K`）、新建、通知（带角标）、明暗切换、头像胶囊。
- **侧栏 272px**，折叠后 **62px**（只留图标，标签淡出，不滑出）。顶部是用户卡（头像 + 昵称 + 连续天数），下面是分组：**记录**（今日/用药/戒烟/待办/清债/习惯/体重/随笔）与**回顾**（日历/统计/设置），分组标题可折叠。底部固定两块：快速添加、**退出登录（红字）**。
- **主区**：`padding: 20px 28px 32px`，主列**填满可用宽度**（不居中留白）。任何页面都只有这一列。
- **页面纵向顺序**：Hero（问候 + 日期 + 摘要 + 环形进度）→ 常驻卡片网格 → 待办列表。其它页依次替换「常驻卡片网格」这一段，骨架不动。

**两种排版**：`data-layout="top"` 时侧栏收起、同一批导航项平铺进顶栏第二行；`data-layout="side"`（原 `wide`）时用侧栏。**两版内容宽度完全一致**（都填满可用宽度），不允许顶栏版更宽。

**断点**：1440 / 1180 / 960 / 720 / 560。常驻卡列数：<720 一列、720–1199 两列、1200–1699 三列、≥1700 四列；960–1180 两列；<960 单列；<720 侧栏强制折叠为 62px；<560 顶栏搜索收成图标、环形进度缩到 56px。

**触控**：`(pointer: coarse)` 下所有可点项命中区 ≥ 44px，折叠键与图标按钮扩到 40px。列表行高提到 56px。

## Elevation & Depth

**全站零阴影。** 层次只由三样东西建立：1px 描边（`hairline`）、三级底色（`paper` → `card` → `card-sunk`）、以及字重差。

唯一的「光」在 Hero：右上角一枚径向渐变（浅色 `#fde8e8` / 深色 `rgba(239,68,68,.16)`），半径约 560×240，62% 处收干净。它不承担功能，只标出「这是本页的头部」。

浮起只发生在两种时刻：模态（`box-shadow: 0 24px 60px -30px rgba(0,0,0,.55)`）与拖拽中的卡片。其它任何状态都不许加阴影。

### Named Rules
**The No-Shadow Rule.** 卡片静止态、hover 态都不许有阴影。想要「浮起来」的错觉，用底色提亮一档，不用投影。

**The Single-Light Rule.** 一屏只有 Hero 带径向光。第二个光斑出现，页面的头部就不存在了。

## Shapes

圆角是一套紧阶梯：`4px`（kbd）→ `5px`（标签）→ `8px`（按钮、输入框、导航项）→ `10px`（列表容器）→ `12px`（卡片、Hero）→ `99px`（胶囊、圆形勾选、头像）。

形态语言有三处固定件：
- **圆环**：环形进度用 `conic-gradient` + 内嵌同底色的遮罩盘，盘内写 `完成/总数` 与 7.5px 的 `DONE` 标签。描边厚度 = 尺寸的 7%。
- **点阵**：`12px` 方块、`3px` 圆角、间距 4px。点亮用红笔，未点亮用轨道色。**点阵是点选控件，不是装饰**，命中区在触控下扩到 20px。
- **勾选圆**：`18px` 圆、1.5px 描边（轨道色）；完成后填充红笔并出现 ✓。

## Components

### Buttons
- **Primary（新建）**：行动蓝 `#2C68FF` 实心 + 白字，类名 `.btn.new`。用于「＋ 新建任务」「＋ 添加习惯」这类创建入口。
- **Primary（红）**：红笔实心 + 白字，类名 `.btn.primary`。给**保存 / 确认 / 删除 / 重置 / 退出**这类「落定一件事」的按钮。一屏只能有一个。
- **Secondary**：凹陷底 + 1px 描边 + 墨色字，高 32px。常驻卡底部的动作按钮用它（「开始运动」「管理用药」）。
- **Ghost**：透明底 + 次级色字，只用于标题栏与行内轻操作。
- **States**：hover 只提亮底色一档（不位移）；`:active` 下移 1px；`:focus-visible` 用 2px 红笔描边外扩 2px。

### Navigation
- **项**：高 29px、内距 9px、圆角 8px，图标 15px 描边（1.7 线宽）。默认次级色。
- **Active**：红晕底 + 红字 + 600 字重，**不加左侧色条、不位移**。
- **分组标题**：10.5px/700 + 0.12em 字距 + 次级色，右侧一个 12px 折叠箭头。
- **折叠态**：62px 宽，只剩图标居中；标签 `opacity` 淡出 120ms，宽度同时过渡，不做横向滑出。

### Cards（常驻卡）
明序独有的组件，今日页五张：戒烟 / 喝水 / 运动 / 478 呼吸 / 用药。
- **结构**：标题行（图标 + 名称 + 右上角小标签）→ 主数值（32px + 单位）→ 一行副标 → 微型可视化（进度条 / 点阵 / 七日柱）→ 底部动作区（单按钮或双按钮）。
- **形状**：12px 圆角、1px 描边、`min-height: 190px`、内距 14/15/13。
- **规则**：一张卡只放一种可视化——要么进度条、要么点阵、要么七日柱，不许两种叠用。底部动作区必须贴底（`margin-top:auto`），保证五张卡在同一行时按钮水平对齐。

### List Rows
- **结构**：圆形勾选 + 两行文字（标题 15px/600 + 元信息 12px）+ 右侧数值或标签。
- **尺寸**：行高 50px（触控 56px），左右内距 14px，行间 1px 内线。
- **完成态**：勾选填红 + 标题删除线 + 标题降为次级色。

### Inputs
- **默认**：凹陷底 + 1px 描边 + 8px 圆角 + 34px 高，字号 15px。
- **聚焦**：描边换红笔 + 3px 红晕外扩；不加阴影。
- **错误**：描边换红笔并常驻，下方 12px 红字说明。

### Overlays
- **Toast**：底部居中胶囊，深色底（`coal`）+ 浅字，`11px 18px`，进 220ms、退 180ms。
- **Modal**：卡面 + 12px 圆角 + 唯一允许的投影；背景 `rgba(26,21,18,.55)` + 6px 模糊。

## Do's and Don'ts

### Do:
- **Do** 每页从 Hero 开始、以列表结束；新页面照抄这个纵向顺序，只换中间那段。
- **Do** 用描边与底色区分层级；需要更「高」时提亮底色一档。
- **Do** 数字全部等宽（`tabular-nums`），单位切回 12px 次级色。
- **Do** 图标用 1.7 线宽的描边 SVG，尺寸 15px（行内 12px）。**不要用 emoji 当图标**——它会立刻把界面拉回玩具感。
- **Do** 侧栏折叠保持 272↔62 两档，标签淡出、宽度同步过渡（200ms）。
- **Do** 主题切换只做颜色过渡（250ms），不翻转、不遮罩、不做圆形扩散。
- **Do** 改任何颜色后跑三套对比度审计（`audit-contrast-v33` / `audit-stock-contrast` / `audit-cmd-contrast`）并报告跳过数。
- **Do** 正文 15px 生效时同步把行高、行内距、卡内距各加一档，不要压缩文字换密度。
- **Do** 五张常驻卡的内部结构（字段、文案、按钮位置、标志性图形）保持冻结，只换令牌与尺寸；逐卡清单见 `docs/design/THEME-V2-PLAN.md` 第 4 节。
- **Do** 习惯卡的身份色只准出现在两处：卡片顶部 3px 色条、标题前的 7px 圆点。它是「这是哪个习惯」的标记，不是状态。
- **Do** 周条固定为自然周（周一 → 周日）七等分栅格，同一列永远是同一个星期几；圈内符号只有三种——完成 ✓、明确未完成 ✕、无记录留空。

### Don't:
- **Don't** 用 `#ef4444` 写小字或铺按钮——3.42/3.76，不达标。
- **Don't** 在已完成、达标上用红色；红只属于「还没做完」。
- **Don't** 让身份色进入按钮、状态徽标、文字或图表——多色一旦扩散，「一支红笔」的秩序就散了。
- **Don't** 给卡片加阴影，也不要一屏出现两个径向光。
- **Don't** 在 `themes/` 里写布局、栅格或断点——那是骨架层的事。
- **Don't** 让两种排版的主区宽度不同；顶栏版不许更宽。
- **Don't** 在卡片里套卡片，或在列表行里放第二个可点区域。
- **Don't** 用玻璃拟态、渐变文字、霓虹发光；这套语言里没有它们的位置。
- **Don't** 新增第四个圆角变量；圆角阶梯固定为 4/5/8/10/12/99。
