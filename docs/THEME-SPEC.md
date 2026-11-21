# 明序 · 主题规范

最后更新：v133（2026-11-21，补 §9.1 暗色契约 / §9.2 运动规范）· 当前 6 套主题

这份文件是给主题作者 / AI 的约束。目标是：**只换外观，不碰核心功能。**

## 1. 唯一允许改的文件

```text
themes/custom.css
```

不要修改：

```text
index.html
themes/themes.css
api.php
api/bootstrap.php
service-worker.js
install/
db/
tools/
```

`themes/custom.css` 在现有主题 CSS 之后加载，所以可以在里面覆盖现有主题，或者试验新主题。

## 2. 选择器必须作用域化

所有规则必须以 `data-skin` 开头：

```css
:root[data-skin="paper"] { ... }
:root[data-skin="paper"][data-theme="dark"] { ... }
[data-skin="paper"] .panel { ... }
[data-skin="paper"] .hero { ... }
```

不允许：

```css
body { ... }
.panel { ... }
* { ... }
```

否则会污染其他主题。

## 3. 主题键

现有键：

| key | 当前主题 |
|---|---|
| `paper` | 暖绒 · 鼠尾草 |
| `slate` | 冷雾 · 矩阵 |
| `neu` | 拟态 · 素白 |
| `retro` | 复古 · 街机 |
| `cloud-float` | 浮纸 · 抬升 |
| `cloud-focus` | 聚光 · 晕影 |

> v87 删除了 `mono`（石墨 · 朱砂）、`clay`（柔光 · 拟态）、`forest`（苔绿 · 森野）、
> `cyber`（赛博 · 霓虹）四套皮肤，连同各自的 CSS 一并移除。
> v99 又删了 `mist` 与 `cloud-haze`（含 `skin-mist.css` 文件与 SW 预缓存）。

> 云系两键共用 `themes/skin-cloud.css` 的 `[data-skin^="cloud-"]` 选择器，差异只在文件末尾变体段；改基座组件规则时会同时影响两套。

AI 可以覆盖已有键，但**不要自行新增键**。新增键需要维护者在 `index.html` 的 `SKINS` 和首屏白名单里注册，见 [SITE-STRUCTURE.md](SITE-STRUCTURE.md)。

## 4. 颜色变量

优先只改这些变量，组件会自动跟着变：

| 变量 | 用途 |
|---|---|
| `--bg` | 页面画布 |
| `--surface` | 卡片/面板主表面 |
| `--surface-2` | 次级表面、hover |
| `--surface-3` | 更深一层的表面、列背景 |
| `--text` | 主文字 |
| `--muted` | 次要文字 |
| `--line` | 普通边框 |
| `--line-strong` | 强边框、分隔线 |
| `--accent` | 主色 |
| `--accent-2` | 主色亮部/渐变 |
| `--accent-strong` | 主色深部/悬停 |
| `--accent-soft` | 主色浅背景 |
| `--on-accent` | 主色上的文字 |
| `--good` | 成功/完成 |
| `--warn` | 提醒 |
| `--bad` | 错误/删除 |
| `--gold` | 强调/高亮 |
| `--gold-soft` | 强调浅背景 |
| `--chart-1..4` | 图表固定色（蓝/绿/红/黄）。多段对比图形专用，**不随皮肤换**，避免主色与语义色撞色 |
| `--shadow` | 普通阴影 |
| `--shadow-lg` | 浮起阴影 |
| `--font-serif` | 衬线标题（如果主题使用） |
| `--font-sans` | 正文字体（可选） |
| `--font-mono` | 数字/标签等宽字体（可选） |

侧栏和 Hero 的扩展变量：

```text
--side-bg, --side-bg-2, --side-text, --side-nav
--side-border, --side-line, --side-hover
--side-active-bg, --side-active-text
--side-muted, --side-link, --side-foot, --side-glow
--hero-bg, --hero-bg-2, --hero-bg-3
--hero-text, --hero-muted, --hero-date, --hero-ring
--hero-glow, --hero-border, --hero-shadow
--hero-control-bg, --hero-control-border, --hero-control-text
--hero-chip-bg, --hero-chip-border, --hero-chip-text
--card-top
```

## 5. 允许改的属性

```text
颜色 / 背景 / 渐变
border-color / border-radius
box-shadow / text-shadow
font-family / font-weight / letter-spacing
text-transform
字体大小（小幅调整，不能改变整体布局）
透明度（仅装饰层）
hover / focus / active 状态
light / dark 两套变量
```

## 6. 禁止改的属性

```text
display
position
grid-template-*
flex-*
width / height / min-* / max-*
margin / padding（会影响布局）
overflow
z-index
float
top / left / right / bottom
transform 造成的结构位移
```

也不要：

- 改 HTML 结构或新增 class
- 用 `@import` 引外部字体/图片
- 用 `!important` 覆盖布局
- 用动画影响操作
- 只做浅色、不做深色
- 只改颜色、不改交互状态

## 7. 必须覆盖的状态

主题至少要让这些状态看起来正常：

```text
.nav-item.active
.btn.primary
.btn.ghost
.btn.danger
.habit-card.is-done
.vital-card.is-done
.task.done
.task.cancelled
.stat-card:first-child
.cal-cell.is-today
.cal-cell.is-sel
.cal-cell[data-level="1..4"]
.field input:focus
.modal-card
.toast
.sync-indicator.saved / .pending / .saving / .error
```

## 8. 关键组件类名

```text
外壳：.app .sidebar .brand .logo .nav .nav-item .main
标题：.page-head .section-head
首屏：.hero .hero-main .hero-ring .hero-chips .hero-date
卡片：.panel .habit-card .vital-card .stat-card .cal-cell
      .task .task-row .col .essay-card .med-stat
控件：.btn .btn.primary .mini-btn .icon-btn .field
弹窗：.modal-backdrop .modal-card
状态：.is-done .done .active .is-today .is-sel
      .sync-indicator .toast
```

不要修改类名，也不要用不存在的类名。

## 9. 浅色和深色都要写

每个主题至少两段：

```css
:root[data-skin="paper"] {
  --bg: ...;
  --surface: ...;
  --text: ...;
  --accent: ...;
}

:root[data-skin="paper"][data-theme="dark"] {
  --bg: ...;
  --surface: ...;
  --text: ...;
  --accent: ...;
}
```

如果只覆盖局部组件，浅色和深色也都要给出。

## 9.1 暗色契约

深色不是浅色的反色。写 `[data-theme="dark"]` 段时遵守下面六条：

1. **海拔式表面分层**：暗色下表面层级靠「明度」表达——`--bg` 最深，
   `--surface` 比 `--bg` 亮、`--surface-2` 再亮、`--surface-3` 最亮。
   禁止用白色半透明叠加模拟层级（会产生雾感，且多主题下不可控）。
2. **降饱和、抬明度**：暗色下 `--accent` / `--good` / `--warn` / `--bad`
   相对浅色降饱和约 10–20%，同时抬明度保证对比度不降级；
   禁止直接把浅色色值搬进 dark 段。
3. **阴影降级为描边**：暗色下 `--shadow` 趋近透明，层级主要由
   `--line` / `--line-strong` 承担；`--shadow-lg` 仅弹窗保留。
   暗色里的大面积投影既不显形也显脏。
4. **对比度底线不变**：正文 4.5:1 在 dark 同样成立。
   沿用两条已知坑：`--muted` 不压彩色底（压了要换 `--text`）；
   `--bad` 不用于小字（小字错误态用 `--text` + 图标）。
5. **两组例外不改**：
   - `--chart-1..4` 不随皮肤、也不随明暗——统计页配色必须稳定可控；
   - 打印三件套不改：深色模式不影响打印输出（打印强制黑字白底，
     见 index.html 打印规则，任何 dark 段不得触碰）。
6. **首屏防闪烁**：新增 skin 必须进首屏白名单；主题四处注册
   （`SKINS` / 首屏白名单 / `<link>` / SW `ASSETS`）一处不能漏，
   漏了就是首屏闪默认皮肤或白屏。

## 9.2 运动规范

动画的职责是**确认动作已发生**，不是表演。先立规矩，再上动效。

**硬性约束（本项目特有，先于一切动效）**

`render()` 每次用 innerHTML 整体重写 `#main`。「节点入场动画」会在每次
保存/打卡后整页重播——勾一个习惯，全屏卡片跟着闪一遍。因此只允许两类动画：

1. **状态切换动画**：class 变化驱动的 transition（如 `.is-done`、`.active`、
   hover/focus），元素不被重建，天然安全；
2. **视图入场动画**：必须绑定渲染指纹（key = 视图 + 当前日期），
   key 变化才加动画类，纯数据刷新（同视图同日期）不加。

**时长与缓动**

- 进入：180–240ms，ease-out；退出：120–160ms，ease-in；任何单条动画 ≤400ms。
- 弹窗：backdrop 淡入 + 卡片 `scale(0.98 → 1)`，200ms 以内。

**只允许动的属性**

`transform` / `opacity`（合成器线程）。禁止动画化 `width / height / top /
left / margin / padding / box-shadow`——它们触发布局，移动端会掉帧。
（进度条用 `transform: scaleX`，不用 `width`。）

**运动预算**

同屏同时运动的元素 ≤3 个；列表错落 stagger ≤40ms 且最多 3 项。

**reduced-motion**

`@media (prefers-reduced-motion: reduce)` 是全局唯一开关（`app.css` 已有一处），
任何新动效必须在该媒体查询里有「瞬时完成」的对应声明；JS 侧判断点沿用现有
matchMedia 检查，不要新增第二处开关。

**推荐落地的五个交互（全部遵守上述规范）**

1. 页面切换：内容区 8px 上浮 + 淡入（绑定视图指纹）；
2. 弹窗：backdrop 淡入 + 卡片 scale 回正；
3. 打卡成功：卡片 1.02→1 回弹 200ms + 进度条 `scaleX` 过渡；
4. 分段控件/Tab：指示条 `transform` 位移；
5. Toast 与同步指示器：统一时长与缓动。

**明确不做**

无限循环动画（同步旋转除外）、视差滚动、物理弹性 hover、超过 400ms 的动画、
任何服务「炫」而非「反馈」的动画。

## 10. 可访问性

- 正文文字对比度至少 4.5:1。
- 不能只靠颜色区分成功/失败。
- hover / focus 必须可见。
- 尊重 `prefers-reduced-motion`。
- 不要用低对比度浅灰字作为主要信息。

## 11. 响应式

已有的断点：

```text
1180px
960px
700px
560px
```

主题可以写自己的 `@media`，但只能改颜色、阴影、字体和装饰；不能改栅格、列数、显示隐藏。

## 12. 给 AI 的提示词

把下面这段和 `THEME-SPEC.md` 一起发给 AI：

```text
你是明序的 CSS 主题设计师。

只允许修改 themes/custom.css。
不要修改 index.html、themes/themes.css、api.php、service-worker.js。

规则：
1. 所有选择器必须以 [data-skin="..."] 或 :root[data-skin="..."] 开头。
2. 不写 HTML、JS、API、布局、display/grid/flex/宽高/内外边距。
3. 必须同时提供浅色和深色（[data-theme="dark"]）。
4. 不要 @import 外部字体或图片。
5. 不要新增主题键；只覆盖现有 paper / slate / neu / retro / cloud-float / cloud-focus 之一。
6. 输出完整的 themes/custom.css 内容，不要输出 <style> 标签。

设计目标：
- 主题：{替换这里}
- 关键词：{替换这里}
- 主色：{替换这里}
- 氛围：{替换这里}

请先阅读 THEME-SPEC.md，然后只输出 CSS。
```

## 13. 验收清单

- [ ] 六套主题互不污染
- [ ] 浅色模式可读
- [ ] 深色模式可读，且用海拔式表面分层（阴影已降级为描边）
- [ ] 12 组合（6 皮肤 × 2 明暗）对比度审计通过，且审计报告跳过数
- [ ] 侧栏、Hero、面板、习惯卡、统计卡、日历、弹窗都检查过
- [ ] hover / active / done / today 状态正常
- [ ] 新增动效只动 transform/opacity，reduced-motion 下可瞬时完成，无整页重播
- [ ] 没有改布局
- [ ] 没有改 HTML/JS/API
- [ ] 560px 以下没有横向溢出
- [ ] 刷新和 PWA 重开后主题仍生效
