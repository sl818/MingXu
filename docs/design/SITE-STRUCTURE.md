# 明序 · 站点结构与主题现状（索引）

> **本文 2026-11-23 重写。** 旧版描述的是「六套皮肤 + `themes/*.css` + `SKINS` 常量」的时代，
> 那套机制已在 v135 随主题 v2 全部删除（`themes/` 现存只有一个 README）。旧版内容整体失效，
> 不再保留，避免后来者按已删除的文件动手。
>
> 现状口径以本文件 + `DESIGN.md` 为准；视觉值以 `DESIGN.md` 为唯一出处。

最后更新：2026-11-23（v169）· 适用范围：`index.html` / `assets/*.css` / `service-worker.js`

---

## 1. 文档地图

| 想知道 | 读这份 |
|---|---|
| 整体怎么跑、文件职责、不能破的规矩 | [../ARCHITECTURE.md](../ARCHITECTURE.md) |
| `index.html` 内部结构、视图、交互分发、渲染、移动端 | [../FRONTEND.md](../FRONTEND.md) |
| 接口、鉴权、三套提醒、推送、备份 | [../BACKEND.md](../BACKEND.md) |
| 数据字段、迁移、多端合并规则 | [../DATA-MODEL.md](../DATA-MODEL.md) |
| 部署到宝塔、Nginx、HTTPS、备份、cron | [../DEPLOY.md](../DEPLOY.md) |
| 版本流水、当前线上状态、技术债 | [../HANDOFF.md](../HANDOFF.md) |
| 功能怎么用（给用户看） | [../../README.md](../../README.md) |
| 单文件要不要拆、每阶段验收 | [../REFACTOR-PLAN.md](../REFACTOR-PLAN.md) |
| 设计类文档总索引与时效 | [README.md](README.md) |
| 视觉规范（令牌、字阶、组件态、禁止项） | [../../DESIGN.md](../../DESIGN.md) |
| 主题 v2 的需求与执行记录 | [THEME-V2-PLAN.md](THEME-V2-PLAN.md) |
| 最近的评审结论与待办 | [docs/design/REVIEW-2026-11-23.md](REVIEW-2026-11-23.md) |

---

## 2. 三层职责（现状）

```text
核心层（改它要跑回归）
  index.html              页面骨架 + 全部前端逻辑（样式已外移）
  assets/app.css          骨架与组件（约 3,700 行）
  assets/theme-v2.css     令牌覆盖 + 组件笔触，全站最后加载（约 1,500 行）
  api.php / api/*.php     接口、鉴权、日历、推送、备份
  install/  db/  tools/   安装器、建表、命令行工具
  service-worker.js       PWA 缓存策略

已废弃层
  themes/                 六皮肤时代遗留目录，文件已删，只留 README 说明原因

文档层
  ARCHITECTURE / FRONTEND / BACKEND / DATA-MODEL / DEPLOY / HANDOFF
  docs/design/            设计类文档（本目录）
```

**分层契约（仍然有效）**：`theme-v2.css` 只做两件事——覆盖令牌、覆盖组件笔触；
不写页面结构与数据逻辑，**也不应声明 `width` / `height` / `font-size` 这类尺寸**。
2026-11-23 的评审发现手机端提醒条正是被该层改了字号而坏掉（详见 `REVIEW-2026-11-23.md` 第 3 条）。

---

## 3. 主题现状

`<html>` 上挂两个属性，**没有 `data-skin`**：

```html
<html lang="zh-CN" data-theme="light">
```

| 属性 | 取值 | 谁设的 |
|---|---|---|
| `data-theme` | `light` / `dark`（另有 `auto`：按 7:00–19:00 切换） | 首次进站的引导脚本 + `render()` |
| `data-layout` | `top` / `side` / `wide` | 设置页「布局」，存本地偏好 |

样式来源只有两处，加载顺序固定：

1. `assets/app.css` —— 骨架、组件、栅格、断点
2. `assets/theme-v2.css` —— 令牌（`--bg` / `--surface` / `--accent` / `--action` …）与组件笔触

**不要新建 `themes/*.css`，不要新增 `data-skin`。** 六皮肤机制已删除，首屏白名单与 `SKINS` 常量都不存在了。

### 3.1 令牌要点

```css
--bg  --surface  --surface-2  --surface-3  --text  --muted  --line  --line-strong
--accent(#dc2626)  --accent-2  --accent-strong  --accent-soft  --on-accent
--action(#2C68FF)  --action-strong  --on-action     /* 创建类主操作，红不再承担 */
--good  --warn  --bad  --gold  --gold-soft
```

完整值见 `assets/theme-v2.css` 顶部两个 `:root` 块（浅色 / 深色），语义规则见 `DESIGN.md`。

---

## 4. PWA 缓存

`service-worker.js` 的 `ASSETS` 只含：`./`、`./index.html`、`./manifest.json`、
`./assets/app.css?v=VER`、`./assets/theme-v2.css?v=VER`、3 个图标。

| 请求类型 | 策略 |
|---|---|
| `api.php` / `api/` / `install/` | **永不缓存** |
| 页面导航 | 网络优先，断网回退缓存的 `index.html` |
| 图标 / manifest / 两份 CSS | 缓存优先 |

改任何前端资源都要同时推进 `CACHE`（`lifeboard-shell-vNN`）与 `VER`，否则老客户端拿旧缓存。
版本号另外还有两处：`index.html` 里 `?v=` 查询串与 `const APP_VERSION`。
