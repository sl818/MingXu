# themes/ —— 旧主题层（已废弃）

自 **v135（主题 v2）** 起，明序只有一套主题：暖纸 / 白卡 / 一支红笔。

- 六套皮肤（paper / slate / cloud-float / cloud-focus / neu / retro）已全部删除，相关文件在本目录下不再存在。
- 主题样式位置：**`assets/theme-v2.css`**（加载在 `assets/app.css` 之后，全站最后一份样式）。
- 设计规范位置：根目录 **`DESIGN.md`**（令牌、字阶、栅格、组件态、动效）。
- 需求与执行计划：`docs/THEME-V2-PLAN.md`。

## 为什么这个目录还在

`themes/` 曾承载皮肤层，`index.html` 的 `<link>`、`service-worker.js` 的 `ASSETS`、约 20 个 `e2e/` 脚本都曾引用它。文件删除后保留本说明，避免后来者按旧文档去 `themes/` 找样式。

## 旧文件去哪了

- git 历史：`git show theme-v2-base:themes/skin-retro.css`
- 线上备份：`beifen-dsh/live-backup-<时间戳>/themes/`

## 新增样式改哪里

不要在 `themes/` 里加任何东西。改 `assets/theme-v2.css`（令牌与组件笔触）或 `assets/app.css`（骨架）。

改完必须同时 bump `service-worker.js` 的 `lifeboard-shell-vNN` 与 `index.html` 里的 `?v=` 版本串。
