# 项目交接 · 晚风Todo（HANDOFF）

> 最后更新：2026-10-23 下午
> 用途：跨会话继续开发时，先读这份文件，不用重新翻聊天记录。

## 一句话状态

站点已经部署成功（宝塔 + PHP + MySQL + 域名 + HTTPS）。介绍页/登录门禁、找回密码、8 位密码、按时间主题、PWA 均已上线；PWA 的 manifest MIME 和 Service Worker 缓存头已通过 `curl` 验证。最新一轮“待办改名、习惯页、体重页、随笔页、页脚版权、文案整理”已在本地完成并打包，**尚未确认上传服务器**。

## 2026-10-23 已验证

- `manifest.json` 返回 `200`，`Content-Type: application/manifest+json`。
- `service-worker.js` 返回 `200`，`Content-Type: application/javascript`。
- Service Worker 响应已带 `Cache-Control: no-cache, no-store, must-revalidate` 和 HSTS。
- Nginx 配置里的临时 `X-PWA-Test` 测试头已移除（最终配置只保留 Cache-Control + HSTS）。
- 站点根目录、`api/config.php`、`install.lock` 保持不动。

## 2026-10-23 第三轮改动（待上传）

- 左侧「看板」改名为「待办」，页面标题、帮助和介绍页同步改名。
- 新增「习惯」页：原设置里的「我的习惯」「用药管理」整体移入；设置页保留入口。
- 新增「体重」页：日期、年龄、身高、体重，自动计算 BMI；体重趋势、记录明细、编辑删除。
- 日历增加体重圆点、当天体重/BMI tooltip 和「本月体重」侧栏；统计增加「体重与 BMI」面板。
- 新增「随笔」页：日期、可选标题、正文（最多 5000 字），可编辑删除。
- 待办支持「单次任务 / 每天重复」：可设每天时间（如 20:00）；完成后自动在待办列生成下一件，撤销完成会移除尚未完成的下一件；拖拽/按钮完成同样生效。
- 站点更名为「晚风Todo」：页面标题、品牌、manifest、安装器默认站点名、备份/CSV 文件名同步替换；设置里的「导出打卡 CSV」改为「导出 CSV」。
- 重写未登录介绍页：以健康与效率为主线，突出用药（短期/周期、类型/时间）、喝水 8 杯、478 呼吸、运动，补充自定义习惯/待办/体重和统计示例。

## 2026-10-23 存储方案 A（待上传）

- 云端是唯一数据源：不再把完整 JSON 写入 `localStorage`。
- 每次修改调用 `force` 保存接口，最后写入覆盖；取消冲突弹窗和自动拉取。
- 旧 `lifeboard.v1` 在云端为空时首次登录自动上传一次，成功后删除；云端已有数据以云端为准。
- 保留 JSON 导出和 CSV 导出；移除 JSON 导入入口。
- 保存失败会在账号面板提示，并阻止带未保存修改离开；断网刷新会停在介绍页。
- 新增 `cloud.ready`，云端加载完成前禁止保存，避免用示例数据覆盖云端。
- 新增 `board_revisions` 历史版本表：保存 / 清空 / 恢复前快照，保留 20 版 / 30 天，设置里可预览和整份恢复；已有站点需要执行 `db/migrations/2026-10-23_board_revisions.sql`。
- 保存失败兜底只做方案 A：`pagehide`/`visibilitychange` + `fetch keepalive`，不做 IndexedDB 或本地队列。
- CSV 导出增加公式注入防护。
- 手机端底部 5 Tab：今日、待办、习惯、统计、更多；更多页含体重、随笔、日历、设置。
- 体重改为身体档案：年龄 / 身高维护一次，记录只填日期和体重；旧记录自动迁移档案。
- 重复任务扩展为每天 / 每周 / 每月；每月小月取最后一天。
- 统计增加近 7 / 30 / 90 天范围，默认 30 天。
- 修复云端 `checks` / `moods` 被旧数据存成数组导致打卡和心情刷新丢失：加载时转成普通对象，`checks` 会按 `events` 重建；修复后自动回写云端。
- 日历新增「本月用药」，并把用药从本月习惯筛选中放回；统计习惯明细包含用药和自定义习惯，用药记录显示活跃 / 暂停 / 按需 / 暂无排期。
- 右下角新增全局保存状态：待保存 / 保存中 / 已保存时间 / 保存失败，点击立即保存。
- CSV 改为「日期、类型、名称、数值、单位、详情」，包含习惯、用药、体重、心情、随笔。
- 习惯弹窗图标字段增加「更多图标」外链。
- 日历宽屏改为 6 列网格：日历 + 右侧习惯/用药，底部三卡本月小结 / 心情 / 体重；1180px 以下自动变为日历整行 + 两列卡片，700px 以下单列。
- 随笔增加最多 5 个标签，卡片可点标签筛选；不做搜索；CSV 增加标签列。
- 习惯支持归档 / 恢复：归档后不进今日、日历和统计，历史打卡保留；常驻习惯不可归档。
- 主题重新设计：晴空 · 白蓝（白蓝渐变/轻盈）、冷雾 · 矩阵（雾蓝网格/科技 HUD）、石墨 · 朱砂（石白墨黑/编辑感）、柔光 · 拟态（同色浮雕/内阴影）。旧 paper/slate/mono/clay 键名保留，样式整体重写；石墨·朱砂和冷雾·矩阵保留。
- 今日页恢复原来的单列布局，不再使用双列或右侧速览栏。
- 主题层已与核心分离：现有主题 CSS 移到 `themes/themes.css`；`themes/custom.css` 作为 AI 主题沙盒，后加载可覆盖；新增 `SITE-STRUCTURE.md`、`THEME-SPEC.md`、`themes/README.md`、`themes/_template.css`。Service Worker 缓存已加入主题 CSS，缓存版本升到 `lifeboard-shell-v2`。
- 今日新增第 4 张常驻卡「478 呼吸法」：4-7-8 引导动画，完整一轮计一次；不设目标、不计入完成率，次数走现有 checks 云同步。点开始后按钮变为「进行中」并禁用，完成后恢复为「再来一次」。动画改为小球 4 秒放大、7 秒屏息外围缓慢脉动、8 秒缩回，倒计时缩小到球体下方。
- 体重和随笔写入现有 `boards.data` JSON，自动跟随云同步，无需改数据库。
- 手机端体重/随笔横向溢出修复：限制 main/body 宽度、重排体重记录行、裁切趋势图标签、随笔长文本断行。
- 手机端顶部深色区域被撑高修复：移动端 grid 改为 `auto 1fr`，侧栏 `align-self:start`，不再被 `min-height:100vh` 拉伸。
- 页脚版权和作者链接保留；文案继续整理。
- 最新更新包：`todo-update.zip`。

## 剩余待办

- [ ] 上传最新 `todo-update.zip`，确认不要覆盖 `api/config.php` / `install.lock`。
- [ ] 上线后检查待办/习惯/体重/随笔四个入口、BMI 计算和云端同步。
- [ ] 在手机/电脑上实际点一次「安装应用 / 添加到主屏幕」。
- [ ] DevTools → Application → Service Workers，确认没有旧 worker 占着；必要时 Update/Unregister。
- [ ] 备份 Nginx 配置：`/www/server/panel/vhost/nginx/todo.csl88.top.conf`。
- [ ] 确认登录/注册/找回密码/主题自动切换在线上都正常。


## 线上环境

- 域名：`https://todo.csl88.top`
- 站点根目录：`/www/wwwroot/todo.csl88.top`
- 环境：阿里云轻量服务器 + 宝塔 + PHP 8.2 + MySQL
- 数据：MySQL，`users / boards / app_settings / login_attempts / register_attempts`
- 安装器已运行过，`install/` 应已删除，`install.lock` 必须保留
- `api/config.php` 是线上数据库配置，**任何更新都不要覆盖**
- 本地文件：`index.html`、`api.php`、`api/bootstrap.php`、`install/index.php`、`db/schema.sql`、`tools/create_user.php`
- PWA：`manifest.json`、`service-worker.js`、`icons/*.png`
- 文档：`README.md`、`DEPLOY.md`

## 已完成的功能

1. 单文件习惯/用药/任务看板，本地 localStorage 可用。
2. 云同步：PHP + MySQL，登录、拉取、防抖上传、冲突选择。
3. 多用户：邀请码注册、管理员/普通用户、每个账号一份 boards。
4. 管理员面板：用户列表、重置密码、停用/启用、注册开关、邀请码、站点名；不读取用户数据。
5. 安装向导：空库建表、创建首个管理员、生成邀请码、写 config + install.lock。
6. 域名首页介绍页：未登录只能看介绍，登录/注册后进看板；本地 `file://` 仍直接进看板。
7. 登录框右下角「找回密码」，弹窗内容：`找回密码：sl@sl00.top`。
8. 密码最低长度统一为 8 位（注册、改密、管理员重置、安装器、CLI）。
9. 主题默认按时间自动：7:00–19:00 浅色，其余深色；设置里可手动固定/恢复自动。
10. PWA：manifest、Service Worker、192/512/maskable 图标；缓存外壳，不缓存 `api.php`。

## 最近生成的文件

- `todo-update.zip`：**更新用**。只含前端/接口/PWA/文档，不含 `api/config.php`、`install.lock`、`install/`、`db/schema.sql`。
- `todo-deploy.zip`：全新安装用。含 `api/config.php` 占位符，**不要拿它覆盖现有站点**。
- 旧的 `todo.zip` 是很早的版本，忽略。

## 更新步骤（已完成，留档）

1. 备份数据库和 `api/config.php`。
2. 上传 `todo-update.zip` 到 `/www/wwwroot/todo.csl88.top/`，解压覆盖。
3. 确认没有覆盖 `api/config.php`、`install.lock`；`install/` 保持删除。
4. Nginx 站点配置增加：

```nginx
location = /manifest.json {
    types { application/manifest+json json; }
    default_type application/manifest+json;
}
location = /service-worker.js {
    add_header Cache-Control "no-cache, no-store, must-revalidate";
}
```

5. 重载 Nginx；浏览器 Ctrl+F5。
6. 无痕窗口打开域名，确认看到介绍页；登录/注册/找回密码/管理员面板各测一次。
7. 访问 `https://todo.csl88.top/manifest.json` 和 `/service-worker.js`，确认 200；浏览器菜单试安装 PWA。

## 重点验证

- [ ] 更新后未登录只看到介绍页，看不到看板。
- [ ] 登录后进入看板；退出后回到介绍页。
- [ ] 登录框右下角「找回密码」显示 `sl@sl00.top`。
- [ ] 8 位密码可以注册；旧密码仍能登录。
- [ ] 自动主题在当前时间正确（7–19 浅色，其余深色）。
- [ ] 管理员能看到用户管理；普通用户看不到。
- [ ] PWA 可安装；`manifest.json` MIME 正确；Service Worker 已注册。
- [ ] 两台设备同步正常；冲突弹窗正常。
- [ ] 宝塔 PHP 错误日志无 `lifeboard api:` 异常。

## 已知限制/注意

- 本机没有 PHP/MySQL，安装器和接口只做了结构与 BOM 检查，未真实连库跑；线上如报错看 PHP 日志。
- 管理员能重置密码，因此理论上可设置新密码后以该用户身份登录；这是“管理员可重置密码”的固有边界。
- PWA 只缓存外壳，离线不能登录/同步；离线重新打开会回介绍页或提示连接失败。
- 同一浏览器切换账号会清空本地缓存并从新账号云端拉取，避免串号。
- 服务端 `register_attempts` 同 IP 每小时最多 10 次注册尝试。
- 备份文件含所有用户用药数据，权限要收紧，不要放网站根目录。

## 明天怎么继续聊

新开会话，第一句发：

```text
读 HANDOFF.md、DEPLOY.md 和 README.md，先告诉我当前状态和待办，然后从“验证更新”开始。
不要覆盖 api/config.php 和 install.lock。
```

之后每完成一件事，让我更新 `HANDOFF.md` 的「已完成 / 待办 / 已知问题」三节。这样即使上下文变长、换会话，也不会丢关键信息。

## 可选后续方向

- PWA 安装到手机桌面后的图标/启动页细节。
- 用户自助导出自己的数据。
- 注册邮件验证 / 更严格的邀请码（一次性）。
- 主题跟随日出日落而不是固定 7–19。
- 管理员操作审计日志（重置密码/停用记录）。
