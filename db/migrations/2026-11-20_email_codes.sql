-- 注册邮箱验证：一次性验证码
-- 在宝塔的 phpMyAdmin 里选中数据库 → SQL → 整段粘贴执行一次。
--
-- 为什么需要：
--   注册新增第三种方式「开放（邮箱验证）」——不需要邀请码，但要能收到 6 位验证码。
--
-- 安全约定：
--   1. 只存 code 的 sha256，不存明文。
--   2. 10 分钟过期，用一次作废（used_at）。
--   3. 重发会让旧码失效（发新码时把同邮箱未用的标记 used）。
--   4. 限流在代码里做：同邮箱 60 秒一条 / 每天 10 条，同 IP 每天 20 条。

CREATE TABLE IF NOT EXISTS email_codes (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  email VARCHAR(190) NOT NULL,
  purpose VARCHAR(16) NOT NULL DEFAULT 'register',
  code_hash CHAR(64) NOT NULL,
  expires_at DATETIME NOT NULL,
  used_at DATETIME NULL DEFAULT NULL,
  ip VARCHAR(45) NOT NULL DEFAULT '',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_code_email (email, purpose),
  KEY idx_code_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
