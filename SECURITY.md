# 安全策略

## 报告漏洞

**不要公开开 issue。** 用 GitHub 的私密报告：

仓库页 → **Security** → **Report a vulnerability**

请写清：影响的版本（`service-worker.js` 里的 `CACHE` 值）、复现步骤、能造成什么后果。收到后会尽快确认并修复，修完在 Release 里说明。

## 支持范围

只维护 `main` 分支的最新版本。旧版本不回补，升级方式就是覆盖文件（数据库结构变化会在 `db/migrations/` 里给 SQL）。

## 设计边界（部署者需要知道的）

- **数据在你自己手里**：这是自托管项目，数据库、账号、看板内容都在部署者自己的服务器上，作者不接触任何实例的数据。
- **仓库不含凭据**：`api/config.php`、`install.lock`、`backups/` 都在 `.gitignore` 里，仓库只有 `api/config.example.php` 这个占位示例。
- **账号隔离**：接口按 `session` 取 `user_id` 过滤数据；管理员只能管理账号与密码，**不能读取其他用户的看板数据**。
- **单设备登录**：`users.session_epoch` 每次登录递增，旧设备的请求会被拒绝。
- **邀请码**：注册需要管理员在安装向导或后台生成的邀请码，不是开放注册。

## 部署建议

- 全程 HTTPS（`cookie_secure` 保持 `auto`，正式站点会自动加 Secure）
- 数据库账号只给当前库权限，不要用 root
- 不要把 `api/config.php` 放在可被直接下载的位置（文件开头有 `LIFEBOARD_API` 保护，但仍建议 Nginx 层再挡一次）
- `install/` 装完后建议改名或加访问限制，避免被重复触发
- 定期备份：设置页可导出全站 JSON；服务器侧建议每日快照数据库

## 已知取舍

- 企业微信 Webhook 存在数据库里（`users.push_webhook`），部署者能在库里看到，但不会下发给其他用户。
- ICS 订阅链接里的 token 是长期有效的，泄露等于泄露日程；在设置页可以重置。
