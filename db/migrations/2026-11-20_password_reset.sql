-- 站点邮件：找回密码的重置令牌
-- 在宝塔的 phpMyAdmin 里选中数据库 → SQL → 整段粘贴执行一次。
--
-- 为什么需要：
--   以前「找回密码」是让用户联系管理员人工重置。接上站点邮件后，
--   改成发一封带一次性链接的邮件，用户自己点开改密码。
--
-- 安全约定：
--   1. 只存 token 的 sha256，不存明文——数据库泄露也拿不到可用链接。
--   2. 30 分钟过期，用一次即作废（used_at）。
--   3. 同一邮箱 5 分钟内只能申请一次（在代码里限流，不靠这张表）。

CREATE TABLE IF NOT EXISTS password_resets (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id INT UNSIGNED NOT NULL,
  token_hash CHAR(64) NOT NULL,
  expires_at DATETIME NOT NULL,
  used_at DATETIME NULL DEFAULT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_reset_token (token_hash),
  KEY idx_reset_user (user_id),
  CONSTRAINT fk_reset_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
