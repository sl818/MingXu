## 改了什么

<!-- 一两句话说清：改了哪个页面 / 哪个函数 / 修了什么现象 -->

## 为什么

<!-- 解决什么问题；如果是 bug，说明复现方式 -->

## 检查清单

- [ ] `node _check_script.mjs` 通过（JS 语法 + 事件 action 自检）
- [ ] 改了 `index.html` / `themes/` / `service-worker.js` 后，**递增了 `CACHE` 版本号**
- [ ] 动了 `state` 的顶层字段时，同步了 `normalizeState` / `mergeStates` / `repairBackup`
- [ ] 新增主题键时，四处都注册了：`SKINS` / 首屏白名单 / `<link>` / SW 的 `ASSETS`
- [ ] 没有把 `api/config.php`、`install.lock`、`backups/` 提交进来
- [ ] 没有统一文件行尾（仓库里有 CRLF 与 LF 混用）
- [ ] 如果改了界面，贴一张改前 / 改后的截图
