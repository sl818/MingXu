# 晚风Todo · 网站结构

## 1. 先分清三层

```text
核心功能层（不要给 AI 改）
  index.html 的结构和 JavaScript
  api.php / api/bootstrap.php
  install/、db/、tools/
  service-worker.js

主题层（AI 可以改）
  themes/custom.css        ← 唯一推荐给 AI 写的文件
  themes/_template.css     ← 新主题模板
  themes/themes.css        ← 现有四套主题，不建议 AI 直接改

文档层
  SITE-STRUCTURE.md        本文件：网站结构
  THEME-SPEC.md            主题规范
  themes/README.md         给 AI / 主题作者的简短说明
```

原则：

- **HTML、JS、API、数据库、Service Worker 都是核心。**
- **主题只负责颜色、背景、阴影、圆角、字体和组件外观。**
- 主题不允许改变布局、尺寸、显示隐藏、数据逻辑。

## 2. 页面与核心区域

```text
index.html
├── 首屏 / 介绍页 landingHtml()
├── 登录 / 注册 / 找回密码
├── 应用外壳
│   ├── 左侧导航 .sidebar
│   │   ├── 品牌 .brand / .logo
│   │   ├── 导航 .nav / .nav-item
│   │   └── 底部 .side-foot
│   ├── 主区域 .main
│   │   ├── 页面标题 .page-head
│   │   ├── 今日 .hero
│   │   ├── 习惯卡 .habit-card / .vital-card
│   │   ├── 待办 .task / .task-row / .col
│   │   ├── 日历 .cal-layout / .cal-cell
│   │   ├── 统计 .stat-card / .chart / .hstat
│   │   ├── 体重 / 随笔 / 设置
│   │   └── 页脚
│   └── 手机底部导航 .mobile-tabbar
├── 弹窗 .modal-backdrop / .modal-card
├── 提示 .toast
└── 云端保存状态 .sync-indicator
```

这些结构由 JS 渲染，**主题不要依赖新增 DOM**。

## 3. 主题系统怎么工作

HTML 根节点上有两个关键属性：

```html
<html data-skin="paper" data-theme="light">
```

- `data-skin`：`paper` / `slate` / `mono` / `clay`
- `data-theme`：`light` / `dark`

CSS 通过这两个属性选择主题：

```css
:root[data-skin="paper"] { --bg: ...; --accent: ...; }
:root[data-skin="paper"][data-theme="dark"] { --bg: ...; }
[data-skin="paper"] .panel { ... }
```

主题键对应的当前主题：

| key | 名称 | 风格 |
|---|---|---|
| `paper` | 晴空 · 白蓝 | 白蓝、页边渐变 |
| `slate` | 冷雾 · 矩阵 | 科技 HUD、网格、青色 |
| `mono` | 石墨 · 朱砂 | 石白墨黑、朱砂、硬边框 |
| `clay` | 柔光 · 拟态 | 同色浮雕、内阴影 |

## 4. 主题文件

- `themes/themes.css`：现有四套主题的完整实现。
- `themes/custom.css`：**AI 主题沙盒**，在主题 CSS 之后加载，用它覆盖或试验。
- `themes/_template.css`：新主题模板。

AI 只改 `themes/custom.css`，不要动 `index.html` 和 `themes/themes.css`。

## 5. 加一个新主题要改哪里

CSS 写好后，还需要在核心注册一个主题键。注册涉及两处：

1. `index.html` 里 `SKINS` 数组增加一项：

```js
{ key: 'aurora', name: '极光 · 主题', desc: '短描述', bg: '#...', card: '#...', side: '#...', accent: '#...' }
```

2. `index.html` 首屏脚本的白名单加入 `'aurora'`：

```js
['paper','slate','mono','clay','aurora'].indexOf(s) >= 0
```

这两处属于核心注册，**不要让 AI 改**。可以让 AI 先把 CSS 写到 `custom.css`，再让维护者注册键。

## 6. PWA 缓存

`service-worker.js` 已把以下文件加入外壳缓存：

```text
./themes/themes.css
./themes/custom.css
```

改主题后需要重新加载页面；Service Worker 会按缓存版本更新。

## 7. 相关文档

- [THEME-SPEC.md](THEME-SPEC.md)：颜色变量、组件类名、允许/禁止清单、AI 提示词。
- [AI-THEME-GUIDE.md](AI-THEME-GUIDE.md)：可以直接复制给 AI 的完整主题编写说明。
- [themes/README.md](themes/README.md)：主题作者的最小工作流。
