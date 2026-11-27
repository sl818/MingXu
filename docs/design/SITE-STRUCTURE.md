# 明序 · 站点结构与页面地图

> **本文 2026-11-27 重写（v203）。** 上一版停在 v169，缺少 v170 拆出的
> 喝水 / 运动 / 478呼吸法 三个独立页，且把布局写成「顶部 / 侧栏 / 宽屏」三个值
> —— 实际只有两个（`top` / `wide`），`side` 在代码里已不存在。
> 更早的「六套皮肤 + `themes/*.css` + `SKINS`」口径已在 v135 随主题 v2 全部删除。
>
> 现状口径以本文件 + `DESIGN.md` 为准；视觉值以 `DESIGN.md` 为唯一出处。

最后更新：2026-11-27（v203）· 适用范围：`index.html` / `assets/*.css` / `service-worker.js`

---

## 1. 文档地图

| 想知道 | 读这份 |
|---|---|
| 整体怎么跑、文件职责、不能破的规矩 | [../ARCHITECTURE.md](../ARCHITECTURE.md) |
| `index.html` 内部结构、视图、交互分发、渲染、移动端 | [../FRONTEND.md](../FRONTEND.md) |
| 接口、鉴权、三套提醒、推送、备份 | [../BACKEND.md](../BACKEND.md) |
| 数据字段、迁移、多端合并规则 | [../DATA-MODEL.md](../DATA-MODEL.md) |
| 改某个功能要动哪些函数、跑哪些测试 | [../CHANGE-MAP.md](../CHANGE-MAP.md) |
| 部署到宝塔、Nginx、HTTPS、备份、cron | [../DEPLOY.md](../DEPLOY.md) |
| 版本流水、当前线上状态、技术债 | [../HANDOFF.md](../HANDOFF.md) |
| 功能怎么用（给用户看） | [../../README.md](../../README.md) |
| 单文件要不要拆、每阶段验收 | [../REFACTOR-PLAN.md](../REFACTOR-PLAN.md) |
| 设计类文档总索引与时效 | [README.md](README.md) |
| 视觉规范（令牌、字阶、组件态、禁止项） | [../../DESIGN.md](../../DESIGN.md) |
| 主题 v2 的需求与执行记录 | [THEME-V2-PLAN.md](THEME-V2-PLAN.md) |
| 最近的评审结论与待办 | [REVIEW-2026-11-23.md](REVIEW-2026-11-23.md) |

**本文与 CHANGE-MAP 的分工**：本文答「站点有哪些页、每页干什么」；CHANGE-MAP 答
「改这个功能要动哪些函数」。查位置看本文，查改法看 CHANGE-MAP。

---

## 2. 三层职责（现状）

```text
核心层（改它要跑回归）
  index.html              页面骨架 + 全部前端逻辑（20,542 行，样式已外移）
  assets/app.css          骨架与组件（4,267 行）
  assets/theme-v2.css     令牌覆盖 + 组件笔触，全站最后加载（1,537 行）
  api.php / api/*.php     接口、鉴权、日历、推送、备份
  install/  db/  tools/   安装器、建表、命令行工具
  service-worker.js       PWA 缓存策略

已废弃层
  themes/                 六皮肤时代遗留目录，文件已删，只留 README 说明原因

文档层
  ARCHITECTURE / FRONTEND / BACKEND / DATA-MODEL / DEPLOY / HANDOFF / CHANGE-MAP
  docs/design/            设计类文档（本目录）
```

**分层契约（仍然有效）**：`theme-v2.css` 只做两件事——覆盖令牌、覆盖组件笔触；
不写页面结构与数据逻辑，**也不应声明 `width` / `height` / `font-size` 这类尺寸**。
2026-11-23 的评审发现手机端提醒条正是被该层改了字号而坏掉（详见 `REVIEW-2026-11-23.md` 第 3 条）。

---

## 3. 页面地图

### 3.1 未登录态

不是独立页面，是同一份 `index.html` 的落地视图（`.lp-*` 系列样式 + 登录 / 注册弹窗）。
点击登录 / 注册 / 找回密码走弹窗或落地区块，不切换 `state.view`。

### 3.2 登录后：17 个页面

`VIEWS` 常量把 key 映射到视图函数，`NAV` 常量决定有哪些页与默认顺序，分四组。

| 分组 | 页面（key） | 职责 | 主要数据 |
|---|---|---|---|
| **顶** | `today` 仪表盘 | 当日总览：常驻模块卡、小习惯、待办、提醒 | 汇总读取（不独占） |
| **记录** | `meds` 用药 | 药箱、每日排期、依从率、余量 | `state.meds` / `state.doses` |
| | `quit` 戒烟 | 点一根 / 忍一次、烟盒、省钱、复吸趋势 | `state.modules.quit` / `cravings` / `packs` |
| | `water` 喝水 | 页内设置、科普、数据统计、提醒双模式 | `state.modules.water` / `checks.h_water` |
| | `move` 运动 | 多运动实例、打卡状态机、按模式统计 | `state.modules.move`（`sports` / `records`） |
| | `breathe` 478呼吸法 | 页内设置、科普、统计、多时间点提醒 | `state.modules.breathe` / `checks.h_breathe` |
| | `board` 待办 | 看板、筛选、拖拽排序、归档 | `state.tasks` / `state.cardOrder` |
| | `money` 清债 | 债务清单、还款顺序、还清日 | `state.money` / `state.moneyAt` |
| | `habits` 习惯 | 小习惯列表、本月概览、排序、归档 | `state.habits` / `checks` / `skips` |
| | `weight` 体重 | 身体档案、BMI、趋势 | `state.weights` / `state.bodyProfile` |
| | `essays` 随笔 | 随手记录与标签 | `state.essays` |
| **回顾** | `calendar` 日历 | 月 / 周视图，按天回看完成度 | 汇总读取 |
| | `stats` 统计 | 总览、习惯、用药、478、戒烟、体重、运动 | 汇总读取 |
| **设置** | `modules` 功能模块 | 五个模块启停；停用后导航隐藏、数据保留 | `state.modules` / `state.modulePrefs` |
| | `notifyroute` 通知路由 | 板块矩阵、免打扰、文案模板、真实通知列表 | `app_settings`（boards / quiet / templates）+ `push_preview` |
| | `config` 配置 | 企微 / 邮件配置、自定义通知、ICS 订阅、数据导出 | 服务端 `app_settings` + 本地 |
| | `modules` 功能模块 | 五个模块的启停，停用后导航隐藏、数据保留 | `state.modules` / `state.modulePrefs` |
| | `notifyroute` 通知路由 | 板块矩阵、免打扰、文案模板、真实通知列表 | `app_settings`（boards / quiet / templates）+ `push_preview` |
| | `settings` 设置 | 排版、主题、导航顺序、账号 | `state.navOrder` + 本地偏好 |

> 四个常驻模块（`water` / `move` / `breathe` / `quit`）由 `MODULE_KEYS` 定义，
> `state.modules` 存配置，记录仍写原主键 `h_water` / `h_move` / `h_breathe` / `h_drink`。
> `state.habits` 里同名的四条是 v170 留下的**回滚锚点**，不参与任何计算，
> 一律被 `isModuleAnchor()` 过滤。

### 3.3 导航与排序

- `state.view` 存当前页，**没有 URL 路由**（不写 hash）；刷新会回到上次停留的页，因为
  `view` 是 `state` 的顶层键，随之保存与同步。
- `NAV` 只管「有哪些页 + 默认顺序」；实际顺序由 `orderedNav()` 按 `state.navOrder` 计算，
  未排到的按 `NAV` 原顺序补在后面。与 `PINNED_IDS` / `orderedPinnedIds` 是同一分工。
- `NAV_GROUPS = ['记录', '回顾', '设置']`；仪表盘的 group 是 `'顶'`，不在分组里，
  排序时自然置顶，也不参与设置页的拖拽。
- 桌面两种布局都读同一个顺序；手机「更多」抽屉也读它。

### 3.4 移动端（≤960px）

`assets/app.css` 在 `@media (max-width:960px)` 内启用 `.mobile-tabbar`，5 个槽位：

| 槽位 | key | 说明 |
|---|---|---|
| 1 | `today` | 今日 |
| 2 | `meds` | 用药 |
| 3 | `__add` | 中间悬浮「＋」，`data-act="quick-add"` |
| 4 | `board` | 待办 |
| 5 | `__more` | 「更多」，弹出 `MORE_PAGES` 全部 13 页 |

`MORE_PAGES` = 清债、戒烟、喝水、运动、478呼吸法、习惯、随笔、体重、日历、统计、配置、功能模块、通知路由。
加上仪表盘、用药、待办、设置，正好 17 页，任意页面两步可达。

### 3.5 页面关系

```text
未登录落地页 ──登录──▶ 仪表盘(today)
                          │
        ┌─────────────────┼──────────────────┐
     记录 10 页          回顾 2 页          设置 4 页
   用药 / 戒烟 / 喝水   日历 / 统计        配置 / 设置
   运动 / 478 / 待办
   清债 / 习惯 / 体重 / 随笔
                          │
        仪表盘 ←──────────┴──── 各页均可在页内跳回
```

跨页跳转只有两种形态：`data-nav` 属性直接切页；`move-goto` / `more-go` / `med-card-pick`
这类跳转型 action 先切页再定位到具体区块。

---

## 4. 主题与布局

`<html>` 上挂两个属性，**没有 `data-skin`**：

```html
<html lang="zh-CN" data-theme="light" data-layout="wide">
```

| 属性 | 取值 | 谁设的 |
|---|---|---|
| `data-theme` | `light` / `dark`（另有 `auto`：按 7:00–19:00 切换） | 首屏引导脚本 + `render()` |
| `data-layout` | **`top` / `wide`（只有两个）** | 设置页「排版」，存本地偏好 |

- `top`：顶部导航条，内容全宽。
- `wide`：左侧菜单栏，内容定宽 1210。
- **不存在 `side`**，也没有「三种布局」；设置页只渲染两张排版卡。

样式来源只有两处，加载顺序固定：

1. `assets/app.css` —— 骨架、组件、栅格、断点
2. `assets/theme-v2.css` —— 令牌（`--bg` / `--surface` / `--accent` / `--action` …）与组件笔触

**不要新建 `themes/*.css`，不要新增 `data-skin`。** 六皮肤机制已删除，首屏白名单与 `SKINS` 常量都不存在了。

### 4.1 令牌要点

```css
--bg  --surface  --surface-2  --surface-3  --text  --muted  --line  --line-strong
--accent(#dc2626)  --accent-2  --accent-strong  --accent-soft  --on-accent
--action(#2C68FF)  --action-strong  --on-action     /* 创建类主操作，红不再承担 */
--good  --warn  --bad  --gold  --gold-soft
```

完整值见 `assets/theme-v2.css` 顶部两个 `:root` 块（浅色 / 深色），语义规则见 `DESIGN.md`。

### 4.2 断点族

`app.css` 实际在用的宽度断点：`560 / 600 / 640 / 700 / 760 / 900 / 960 / 1080 / 1180`。
其中三条是结构性断点，改布局前先确认：

| 断点 | 作用 |
|---|---|
| **960px** | 桌面侧栏 → 手机底部 tabbar 的切换点 |
| **1180px** | 配置页 / 设置页由单列转双列瀑布 |
| **560px** | 卡片内边距与字号收紧的最后一级 |

---

## 5. PWA 缓存

`service-worker.js` 的 `ASSETS` 只含 8 项：`./`、`./index.html`、`./manifest.json`、
`./assets/app.css?v=VER`、`./assets/theme-v2.css?v=VER`、3 个图标。

| 请求类型 | 策略 |
|---|---|
| `api.php` / `api/` / `install/` | **永不缓存** |
| 页面导航 | 网络优先，断网回退缓存的 `index.html` |
| 图标 / manifest / 两份 CSS | 缓存优先 |

改任何前端资源都要**四处同步版本号**（v169 起）：

1. `service-worker.js` 的 `CACHE`（`lifeboard-shell-vNN`）
2. `service-worker.js` 的 `VER`
3. `index.html` 里全部 `?v=NNN` 查询串
4. `index.html` 的 `const APP_VERSION = 'vNNN'`（设置页「系统版本」显示它）

漏第 4 处不会导致缓存问题，但页面会显示落后一个版本号。

---

## 6. 新增一个页面要改哪几处

按 v170 拆三个页的实际改动整理，顺序即依赖顺序：

| # | 位置 | 改什么 | 漏了会怎样 |
|---|---|---|---|
| 1 | `VIEWS` | 加 `key: viewXxx` 映射 | 切页白屏 |
| 2 | `NAV` | 加 `{key, label, icon, group, wideLabel}` | 桌面导航里没有入口 |
| 3 | `MORE_PAGES` | 加 `{key, label, icon, desc}` | 手机「更多」抽屉里没有 |
| 4 | `ICONS` | 加同 key 的 SVG path | 导航图标空白 |
| 5 | `service-worker.js` | 推进 `CACHE` / `VER` + `index.html` 四处版本号 | 老客户端拿旧代码 |
| 6 | `docs/CHANGE-MAP.md` | 加一节「改这个模块要动哪些函数」 | 下次改动只能从 grep 开始 |
| 7 | **本文 §3.2** | 加一行页面与数据归属 | 站点地图缺页 |

**不要**为了新页面往 `state` 加顶层键：多端同步与备份修复都要跟着改三处。
只有「需要跨端同步的用户资产」才进 `state`；子页签、展开态、临时筛选一律用模块级变量，
参考清债的 `subTab` 字典与统计页的 `statsHabitTab`。

---

## 7. 维护约定

1. 页面增删、分组调整、移动端槽位变化，**必须同步 §3.2 / §3.4 与本行版本号**。
2. 布局取值、断点、PWA 资源清单变化，同步 §4 / §5。
3. 本文只写锚点（常量名、类名、文件名），**不写行号**——行号会随每次提交失效。
4. 改完跑一次 `python e2e/check-doc-anchors.py`，确认锚点没有被重命名打断。
