# 晚风Todo · 给 AI 的主题编写指南

最后更新：v109（2026-11-17）· 当前 6 套主题

> 这个文件可以直接发给 AI。  
> AI 只负责写 `themes/custom.css`，不要碰核心代码。

## 0. 一句话要求

```text
你只写 themes/custom.css。
不要改 HTML、JS、API、Service Worker、布局和主题注册。
```

## 1. 项目结构

```text
核心层（禁止修改）
  index.html
  api.php
  api/bootstrap.php
  service-worker.js
  install/
  db/
  tools/
  themes/themes.css   ← 现有主题变量层，禁止改

主题层（只能写这里）
  themes/custom.css   ← AI 唯一输出文件
```

`themes/custom.css` 会在 `themes/themes.css` 之后加载，所以可以用来覆盖现有主题。

## 2. 可选主题键

```text
paper  暖绒 · 鼠尾草
slate  冷雾 · 矩阵
neu    拟态 · 素白
retro  复古 · 街机
cloud-float  浮纸 · 抬升
cloud-focus  聚光 · 晕影
```

AI 应选择一个现有键写覆盖，默认建议用 `paper`。

**不要自行新增主题键。** 新键需要维护者在 `index.html` 里注册：

1. `SKINS` 数组增加一项
2. 首屏脚本白名单加入新 key

AI 只输出 CSS；注册由维护者做。

## 3. 选择器规则

所有规则必须以 `data-skin` 开头：

```css
:root[data-skin="paper"] { ... }
:root[data-skin="paper"][data-theme="dark"] { ... }
[data-skin="paper"] .panel { ... }
[data-skin="paper"] .hero { ... }
```

禁止裸选择器：

```css
body { ... }
.panel { ... }
* { ... }
```

否则会污染其他主题。

## 4. 必须同时写浅色和深色

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

只做浅色不算完成。

## 5. 优先改变量

```text
--bg
--surface
--surface-2
--surface-3
--text
--muted
--line
--line-strong
--accent
--accent-2
--accent-strong
--accent-soft
--on-accent
--good
--warn
--bad
--gold
--gold-soft
--shadow
--shadow-lg
--font-serif
--font-sans
--font-mono
```

侧栏 / Hero 变量：

```text
--side-bg, --side-bg-2, --side-text, --side-nav
--side-border, --side-line, --side-hover
--side-active-bg, --side-active-text
--hero-bg, --hero-bg-2, --hero-bg-3
--hero-text, --hero-muted, --hero-date, --hero-ring
--hero-glow, --hero-border, --hero-shadow
--card-top
```

## 6. 可以改

```text
颜色、背景、渐变
border-color、border-radius
box-shadow、text-shadow
font-family、font-weight、letter-spacing
text-transform
小幅字号
透明度（仅装饰）
hover / focus / active 状态
```

## 7. 禁止改

```text
display
position
grid-template-*
flex-*
width / height / min-* / max-*
margin / padding
overflow
z-index
float
top / left / right / bottom
transform 造成的结构位移
```

也不要：

```text
改 HTML 结构
新增 class
@import 外部字体/图片
用 !important 覆盖布局
只改颜色、不改状态
```

## 8. 必须检查的组件

```text
.sidebar / .nav-item.active
.hero
.panel
.habit-card / .vital-card / .is-done
.stat-card / .stat-card:first-child
.cal-cell / .is-today / .is-sel
.task / .task.done / .task.cancelled
.btn.primary / .btn.ghost / .danger
.field input:focus
.modal-card
.toast
.sync-indicator.saved / .pending / .saving / .error
```

主题至少要保证这些区域在浅色和深色下都能看。

## 9. 可访问性

- 正文对比度 ≥ 4.5:1
- 不能只靠颜色区分成功与失败
- hover / focus 必须可见
- 不动效；如使用动画，尊重 `prefers-reduced-motion`
- 560px 以下不能横向溢出

## 10. 输出格式

AI 只输出 `themes/custom.css` 的完整内容：

- 不要输出 `<style>` 标签
- 不要输出 HTML
- 不要解释设计思路
- 不要输出多个文件
- 不要写布局

## 11. 复制给 AI 的完整提示词

```text
你是一名 CSS 主题设计师，正在为「晚风Todo」写主题。

只允许修改 themes/custom.css。
不要修改 index.html、themes/themes.css、api.php、api/bootstrap.php、service-worker.js。
不要新增主题键。

规则：
1. 所有选择器必须以 [data-skin="..."] 或 :root[data-skin="..."] 开头。
2. 不写 HTML、JS、API、布局、display/grid/flex/宽高/内外边距。
3. 必须同时提供浅色和深色（[data-theme="dark"]）。
4. 不要 @import 外部字体或图片。
5. 只覆盖现有 paper / slate / neu / retro / cloud-float / cloud-focus 之一。
6. 只输出完整的 themes/custom.css 内容，不要 <style> 标签。

主题键：paper
主题名：{主题名}
关键词：{关键词}
主色：{主色}
氛围：{氛围}
参考：暖白、留白、轻层次、可读性优先

请先阅读 THEME-SPEC.md，然后只输出 CSS。
```

## 12. 起步模板

```css
:root[data-skin="paper"]{
  --bg:#f4f7fb;
  --surface:#ffffff;
  --surface-2:#f5f8fc;
  --surface-3:#e8eef6;
  --text:#1b2a3d;
  --muted:#6d7c8f;
  --line:#dce5ef;
  --line-strong:#c2cfdd;
  --accent:#3f6f9e;
  --accent-2:#6d99c4;
  --accent-strong:#2b537b;
  --accent-soft:#e7f0f8;
  --on-accent:#f9fcff;
  --good:#3d7f64;
  --warn:#b07a3e;
  --bad:#b04a50;
  --gold:#a8874f;
  --gold-soft:#f2e8d2;
  --shadow:0 1px 2px rgba(30,50,80,.04),0 16px 36px -30px rgba(30,50,80,.28);
  --shadow-lg:0 28px 56px -36px rgba(30,50,80,.4);
}

:root[data-skin="paper"][data-theme="dark"]{
  --bg:#0b1420;
  --surface:#13202e;
  --surface-2:#182738;
  --surface-3:#1f3044;
  --text:#e8f0fa;
  --muted:#9aacbf;
  --line:#24384c;
  --line-strong:#3a556e;
  --accent:#8ab6e6;
  --accent-2:#b0d0f0;
  --accent-strong:#c6e0f8;
  --accent-soft:#1a3047;
  --on-accent:#0a1521;
  --shadow:0 1px 2px rgba(0,0,0,.4),0 20px 42px -32px rgba(0,0,0,.8);
  --shadow-lg:0 30px 60px -32px rgba(0,0,0,.95);
}

[data-skin="paper"] body{
  background:
    radial-gradient(900px 600px at 88% -10%,rgba(120,170,240,.16),transparent 62%),
    linear-gradient(180deg,#f7faff 0%,#eef3fa 100%);
}

[data-skin="paper"][data-theme="dark"] body{
  background:
    radial-gradient(900px 600px at 88% -10%,rgba(100,150,220,.12),transparent 62%),
    linear-gradient(180deg,#0e1824 0%,#0a121c 100%);
}

[data-skin="paper"] .panel{
  background:var(--surface);
  border-color:var(--line);
  box-shadow:var(--shadow);
}
```

## 13. 验收

- [ ] 只改了 `themes/custom.css`
- [ ] 没有裸选择器
- [ ] 浅色正常
- [ ] 深色正常
- [ ] 四个主题互不污染
- [ ] 没有改布局
- [ ] 560px 没有横向溢出
- [ ] 刷新后主题仍生效
