# 参与贡献

这个项目是单人维护的个人工具，会把「自己用得上」放在第一位。提 PR 之前先开个 issue 聊两句，比直接写一大坨代码更容易合进去。

## 先决条件

| 工具 | 用途 | 必需 |
|---|---|---|
| Node.js 18+ | 跑 `_check_script.mjs`（JS 语法 + 事件自检） | 是 |
| PHP 8.0+ | 后端与单元测试 | 改后端时 |
| Python 3 + Playwright | 浏览器回归与对比度审计 | 改界面时 |

前端没有构建步骤：没有 npm install、没有打包、没有 CDN。改完 `index.html` 刷新就能看。

## 本地环境

完整部署（数据库、安装向导、推送）见 [docs/DEPLOY.md](docs/DEPLOY.md)。

只想改界面：任意静态服务器都行，但页面会停在登录页，因为 `api.php?action=status` 探不到后端。要看完整界面就跑一遍安装向导，本地 PHP + MySQL 十分钟能起来。

## 改完至少跑这些

```bash
node _check_script.mjs              # JS 语法 + data-act 是否都有 handler
php e2e/test-ics.php                # 日程生成（改日历/提醒必跑）
php e2e/test-schedule.php           # 推送排期（改提醒必跑）
python e2e/regression-v3.py         # 综合回归，需要 Playwright
python e2e/audit-contrast-v33.py    # 对比度审计，改任何颜色后必跑
```

审审计脚本会同时报「跳过数」。**只看「0 不达标」不看跳过数等于自欺**——跳过集中在哪些皮肤要一起看。

## 代码约定

- **前端不拆文件**：HTML / CSS / JS 都在 `index.html` 里，这是刻意的（见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)），不要为了「整洁」拆成多个 JS。
- **可点控件用 `data-act`**：新增 action 必须同时在 `ACTIONS` 里实现，否则 `node _check_script.mjs` 会报 missing handler。
- **主题只写变量**：皮肤放 `themes/*.css`，规范见 [docs/THEME-SPEC.md](docs/THEME-SPEC.md)；新增主题键要四处注册（`SKINS` / 首屏白名单 / `<link>` / SW `ASSETS`）。
- **后端一律 `require_once`**：`require` 被包含两次会导致重复声明，所有接口 500。
- **新增 state 顶层字段要三处同步**：`normalizeState` / `mergeStates` / `repairBackup`。漏第三处会在导入备份时**直接删用户数据**。
- **行尾不要统一**：`index.html`、`api.php`、`api/*.php` 是 CRLF，`docs/`、`e2e/`、`themes/*.css` 是 LF。统一了会产生整文件级假 diff。
- **改 CSS / HTML / JS 必须递增** `service-worker.js` 的 `CACHE`，否则用户拿到的是旧缓存。
- **不存派生数量**：库存、当前烟包这类能从记录推算的值，一律现算。

## 提交 PR

1. 一个 PR 只做一件事，别把重构和功能混在一起。
2. 说明改了什么、为什么、跑了哪些测试。
3. 界面改动附改前 / 改后截图。
4. 确认没有把 `api/config.php`、`install.lock`、`backups/` 加进提交。

## 报告问题

- 功能异常 → 用 Issue 模板里的「Bug 反馈」
- 安全漏洞 → **不要公开开 issue**，按 [SECURITY.md](SECURITY.md) 私下报告
