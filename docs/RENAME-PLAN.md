# 改名清单 · 晚风 Todo → 明序 Mingxu

> 品牌定义见 [BRAND.md](BRAND.md)。本清单只回答「改哪里、按什么顺序、哪里容易漏」。
> 状态标记：`[x]` 已做 · `[~]` 待用户确认后决定
>
> **2026-11-18 更新**：代码与文档部分已全部落地（v117），相关章节改为已做；品牌名、logo 已定稿。

---

## 1. 先定三件事（不定就不动手）

- [x] **作者署名「晚风」保不保留**。`index.html` 的页脚与备份注释里有
  「作者：晚风」+ 个人站链接，这是身份不是品牌。建议保留（那是你的网名），
  但品牌位（标题、页头、推送标题）一律换成明序。
- [x] **GitHub 仓库名** 已改为 `MingXu`（2026-11-18）。旧链接 301 可用；README 徽章与 `git remote` 已同步。
- [x] **logo 定稿**：见 BRAND.md 4.2 三个方向。定了我才出 SVG + 三张 PNG。

---

## 2. 代码（6 个文件 / 28 处）

### 2.1 `index.html` — 17 处 + favicon

| 位置 | 现在 | 改成 | 影响 |
| --- | --- | --- | --- |
| L10 | `apple-mobile-web-app-title` = 晚风Todo | 明序 | iOS 添加到桌面显示名 |
| L11 | `<title>晚风Todo · 习惯与任务</title>` | `明序 · 习惯与任务` | 浏览器标签、分享卡片 |
| L12 | favicon 是内联 SVG 的 🌿 | 新 logo 的矢量 SVG | 见第 3 节 |
| L63 | 页头 `<b>晚风Todo</b>` | `明序` | 每页左上角 |
| L917 | `siteName: '晚风Todo'` 默认值 | `'明序'` | 未登录时的兜底 |
| L1897 | 设置页「站点名称」默认值 | `明序` | 与线上已存值配套改，见第 6 节 |
| L3815 | 通知标题 `showNotification('晚风Todo')` | `明序` | 浏览器通知 |
| L6843 | 月报页脚「晚风 Todo · 生成于」 | `明序 · 生成于` | 打印/导出 |
| L10906 | 落地页页脚 `© 年份 晚风Todo` | `© 年份 明序` | 未登录页 |
| L10907 | `作者：晚风` + 个人站链接 | **待定**（建议保留） | — |
| L10962 | 落地页页头 `晚风Todo<small>个人生活工作台</small>` | `明序<small>个人生活工作台</small>` | 未登录页首屏 |
| L11044 | 页脚 `© 年份 晚风Todo · 作者：` | `© 年份 明序 · 作者：` | 登录后 |
| L11045 | `作者：晚风` + 个人站链接 | **待定**（建议保留） | — |
| L12768 | ICS `DESCRIPTION` 默认「来自 晚风Todo」 | `来自 明序` | 日历订阅显示 |
| L12794 | ICS `X-WR-CALNAME: 晚风Todo 提醒` | `明序 提醒` | 日历订阅名 |
| L13767 | 备份文件名 `晚风Todo备份-日期.json` | `明序备份-日期.json` | 导出文件名 |
| L13839 | `晚风Todo提醒-日期.ics` | `明序提醒-日期.ics` | 导出文件名 |
| L13884 | `晚风Todo-CSV-日期.csv` | `明序-CSV-日期.csv` | 导出文件名 |

> 导出文件名一改，老用户会找不到以前的文件命名习惯。建议在设置页的导出按钮
> `title` 里写一句「文件名以『明序』开头」，或者干脆不改文件名（保留旧前缀）——
> 这点需要你定。

### 2.2 `manifest.json` — 2 处

- `name`: `晚风Todo · 习惯与任务` → `明序 · 习惯与任务`
- `short_name`: `晚风Todo` → `明序`

### 2.3 `api.php` — 6 处

| 行 | 内容 | 说明 |
| --- | --- | --- |
| 119 / 173 / 240 / 775 | `site_name` 默认值 `晚风Todo` | **四处默认值，必须全改**，漏一处未登录/未配置的站点还是旧名 |
| 423 | 测试消息「晚风 Todo 测试消息」 | 推送测试 |
| 788 | 保存时的兜底默认值 | 与 794 的校验配套 |

### 2.4 `service-worker.js` — 1 处

文件头注释。改完记得 `CACHE` 版本递增（改名属于改 HTML）。

### 2.5 `install/index.php` — 2 处

L187 `<title>… · 晚风Todo安装`、L204 品牌块 `晚风Todo <small>INSTALL</small>`。

### 2.6 `themes/*.css` — 6 处

6 个主题文件的第 2 行头注释（`custom.css` / `skin-cloud.css` / `skin-neu.css` /
`skin-retro.css` / `themes.css` / `_template.css`）。只改注释，不影响样式。

---

## 3. 资产（4 + 2）

- [x] `icons/icon-192.png`（192×192）
- [x] `icons/icon-512.png`（512×512）
- [x] `icons/icon-maskable-512.png`（512×512，图形内缩到 62%）
- [x] `index.html` 内联 favicon（换成新 logo 的无勾简版）
- [ ] `images/landing/today.jpg`（1818×1050）——**图里的页头写着「晚风Todo」，要重新截**
- [ ] `images/landing/stats.jpg`（同尺寸）——同上

> 这两张截图是登录后界面，重截需要你提供账号，或者我改完代码后你在浏览器里截了给我。

---

## 4. 测试（7 个文件 / 9 处）

改名后这些断言会**立刻变红**，必须同步：

| 文件 | 断言内容 |
| --- | --- |
| `e2e/full-e2e.py` | L65 断言页面标题等于 `晚风Todo · 习惯与任务` |
| `e2e/verify-batch3.py` | L445 断言关闭主题面板后标题恢复 |
| `e2e/verify-money-v91.py` | L158 断言导出文件名前缀 `晚风Todo备份-` |
| `e2e/gen-live-report.py` | 报告 HTML 的 `<title>` 与 `<h1>` |
| `e2e/mobile-e2e.py` | 文档字符串（不影响断言） |
| `e2e/verify-quit-page.py` | 文档字符串（引用需求原文，建议保留） |
| `e2e/test-conflict.py` | 一处 mock 字符串 |

---

## 5. 文档（8 个文件）

- `README.md`：标题、开头简介、功能介绍、截图说明、仓库描述、所有自引用
- `docs/README.md`：版本行与索引
- `docs/ARCHITECTURE.md` / `docs/SITE-STRUCTURE.md` / `docs/DEPLOY.md` /
  `docs/THEME-SPEC.md` / `docs/AI-THEME-GUIDE.md`：项目名出现在标题与正文
- `docs/BRAND.md`：**新建，已完成**（本文档即品牌定义）

**不改**：`docs/HANDOFF.md` 的历史流水（那是当时的记录，改名不该篡改历史），
只在最新一行加一句「v117 起改名为明序」。`docs/REFACTOR-PLAN.md` / `CHANGE-MAP.md`
里的「晚风」属于项目自指，按第 5 节统一替换即可。

---

## 6. 线上数据（最容易漏的一项）

`site_name` 不是纯前端常量，它存在数据库的 settings 表里：

- 前端从 `api.php` 的 `me` / 配置接口读 `site_name`，页头和推送标题都用它
- 线上库里**已经存了 `晚风Todo`**，只改代码里的默认值不会生效

两条路，二选一：

1. **手动**：登录 → 设置 → 站点名称改成「明序」（最省事，推荐）
2. **SQL**：`UPDATE` settings 表里 `site_name` 那一行（需要先确认表名与字段）

改完在手机上收一条测试推送确认标题变了 —— 这是唯一能验证「数据层也改了」的方式。

---

## 7. GitHub 仓库

- [ ] About 描述（中英，见 BRAND.md 第 3 节）
- [ ] Topics 标签：todo、self-hosted、pwa、php、habits、dashboard
- [ ] README 顶部标题与简介
- [ ] 仓库名与 `git remote`（待你确认是否改）
- [ ] 旧名相关的外部链接（如果 README 里引用过自己的 URL）

---

## 8. 执行顺序

1. **定第 1 节三件事**（logo 方向、作者署名、仓库名）
2. 出 logo → 生成 3 张 PNG + favicon SVG
3. 代码替换（2.1–2.6），`CACHE` 递增
4. 改测试断言（第 4 节），跑全量回归
5. 改文档与 README
6. 发布 → 登录 → 设置页改 `site_name` → 收一条测试推送
7. 重截两张落地截图，替换 `images/landing/`
8. GitHub About / README

---

## 9. 明确不改的地方

- **域名** `todo.csl88.top`：换域名会让日历订阅地址全部失效（老用户要重新订阅），
  与改名不是一件事。
- **`localStorage` 键名**（`lifeboard.*`）：改了老用户主题/布局偏好全丢，得不偿失。
- **数据库表名 / 字段名**：纯内部实现，与品牌无关。
- **`HANDOFF.md` 历史版本行**：历史记录保持原样。
