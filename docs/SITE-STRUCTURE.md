# 晚风Todo · 网站结构（索引）

> 这份文件原来是"网站结构说明"，内容已并入更详细的分册。
> 现在只留两件事：**文档地图** 和 **主题相关的准确信息**。

最后更新：v82（2026-11-10）

---

## 1. 文档地图

| 想知道 | 读这份 |
|---|---|
| 整体怎么跑、文件职责、不能破的规矩 | [ARCHITECTURE.md](ARCHITECTURE.md) |
| `index.html` 内部结构、视图、交互分发、渲染、主题、移动端 | [FRONTEND.md](FRONTEND.md) |
| 23 个接口、鉴权、三套提醒、推送、备份 | [BACKEND.md](BACKEND.md) |
| 数据字段、迁移、多端合并规则 | [DATA-MODEL.md](DATA-MODEL.md) |
| 部署到宝塔、Nginx、HTTPS、备份、cron | [DEPLOY.md](DEPLOY.md) |
| 功能怎么用（给用户看） | [README.md](../README.md) |
| 版本流水、当前线上状态、技术债 | [HANDOFF.md](HANDOFF.md) |
| 写新皮肤 | [THEME-SPEC.md](THEME-SPEC.md) / [AI-THEME-GUIDE.md](AI-THEME-GUIDE.md) |

---

## 2. 三层职责

```text
核心层（改它要跑回归）
  index.html              页面 + 全部样式 + 全部前端逻辑
  api.php / api/*.php     接口、鉴权、日历、推送、备份
  install/  db/  tools/   安装器、建表、命令行工具
  service-worker.js       PWA 缓存策略

主题层（只写变量，最安全）
  themes/custom.css       AI 主题沙盒，最后加载，优先级最高
  themes/skin-*.css       5 套补充皮肤
  themes/_template.css    新皮肤模板

文档层
  ARCHITECTURE / FRONTEND / BACKEND / DATA-MODEL / DEPLOY / README / HANDOFF / 本文件
```

原则：**主题只负责颜色、背景、阴影、圆角、字体、组件外观。
不允许改变布局、尺寸、显示隐藏、数据逻辑。**

---

## 3. 主题系统

`<html>` 上挂三个属性：

```html
<html data-skin="paper" data-theme="light" data-layout="top">
```

| 属性 | 取值 | 谁设的 |
|---|---|---|
| `data-skin` | 9 套皮肤 key | `render()`，初始值由首屏内联脚本设置 |
| `data-theme` | `light` / `dark` | 同上。`auto` 模式下按 7:00–19:00 自动切 |
| `data-layout` | `top` / `side` / `wide` | PC 端布局 |

CSS 通过属性选择器覆盖变量：

```css
:root[data-skin="paper"] { --bg: ...; --accent: ...; }
:root[data-skin="paper"][data-theme="dark"] { --bg: ...; }
```

### 3.1 九套皮肤

**以 `index.html` 里的 `SKINS` 常量为准**，下表是 v46 时的状态：

| key | 名称 | 定义在哪 |
|---|---|---|
| `paper` | 暖绒 · 鼠尾草 | `index.html` 的 `#skins` 块 |
| `slate` | 冷雾 · 矩阵 | 同上 |
| `mono` | 石墨 · 朱砂 | 同上 |
| `clay` | 柔光 · 拟态 | 同上 |
| `mist` | 雾蓝 · 云水 | `themes/skin-mist.css` |
| `forest` | 苔绿 · 森野 | `themes/skin-forest.css` |
| `neu` | 拟态 · 素白 | `themes/skin-neu.css` |
| `cyber` | 赛博 · 霓虹 | `themes/skin-cyber.css` |
| `retro` | 复古 · 街机 | `themes/skin-retro.css` |

> `THEME-SPEC.md` 和 `AI-THEME-GUIDE.md` 里如果列的还是"四套主题"（晴空 · 白蓝等旧名），
> 那是 v32 之前的版本，**以 `SKINS` 常量和上表为准**。变量契约本身没变，仍然有效。

### 3.2 变量契约

```css
--bg  --surface  --surface-2  --text  --muted  --line
--accent  --accent-soft  --on-accent  --bad  --good
--sidebar-bg  --sidebar-text  --radius  --shadow
```

组件规则一律写 `var(--accent)` 这种形式。新皮肤只需提供一套变量值。

---

## 4. 加一套新皮肤

1. 写 CSS：`themes/skin-<key>.css`，用 `:root[data-skin="<key>"]` 和
   `:root[data-skin="<key>"][data-theme="dark"]` 两组。
2. 在 `index.html` 的 `<head>` 加 `<link rel="stylesheet" href="themes/skin-<key>.css">`。
3. 在 `SKINS` 常量加一项（key / name / desc / 四个预览色）。
4. **在首屏内联脚本的白名单数组里加 key**，否则刷新后皮肤不生效：
   ```js
   ['paper','slate','mono','clay','mist','forest','neu','cyber','retro'].indexOf(s) >= 0
   ```
5. **把文件加进 `service-worker.js` 的 `ASSETS`**，否则离线时皮肤丢失。
6. 推进 `CACHE` 版本号。
7. 跑对比度审计：`python e2e/audit-contrast-v33.py`（9 皮肤 × 明暗，会报不达标和跳过数）。

第 2–4 步属于核心注册，**建议由维护者做**；AI 先把 CSS 写到 `themes/custom.css` 更安全。

---

## 5. PWA 缓存

`service-worker.js` 的外壳缓存清单（`ASSETS`）包含 index.html、manifest、5 个 skin CSS、
themes.css、custom.css 和 3 个图标。

策略：

| 请求类型 | 策略 |
|---|---|
| `api.php` / `api/` / `install/` / `install.lock` | **永不缓存** |
| 页面导航 | 网络优先，断网回退到缓存的 `index.html` |
| 图标 / manifest | 缓存优先 |

**改任何前端资源都要推进 `CACHE` 常量**，否则老客户端拿到的是旧缓存。
