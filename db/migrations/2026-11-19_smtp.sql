-- 邮件提醒（QQ 邮箱 SMTP 发信）
-- 在宝塔的 phpMyAdmin 里选中数据库 → SQL → 整段粘贴执行一次。只需执行一次。
--
-- 安全约定：授权码只存 secret_enc 密文（AES-256-GCM），任何接口都不回显。
-- 密钥来源：api/config.php 的 mail_secret，或本库 app_settings 自动生成的
-- mail_secret_key。换密钥 = 旧密文作废，用户重新填一次授权码即可。

CREATE TABLE IF NOT EXISTS user_mail_config (
  user_id INT UNSIGNED NOT NULL,
  smtp_host VARCHAR(190) NOT NULL DEFAULT 'smtp.qq.com',
  smtp_port SMALLINT UNSIGNED NOT NULL DEFAULT 465,
  smtp_secure ENUM('ssl', 'tls', 'none') NOT NULL DEFAULT 'ssl',
  smtp_user VARCHAR(190) NOT NULL DEFAULT '',
  from_email VARCHAR(190) NOT NULL DEFAULT '',
  from_name VARCHAR(80) NOT NULL DEFAULT '',
  secret_enc TEXT NULL DEFAULT NULL,
  enabled TINYINT(1) NOT NULL DEFAULT 0,
  last_error VARCHAR(500) NOT NULL DEFAULT '',
  last_test_at DATETIME NULL DEFAULT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id),
  CONSTRAINT fk_mail_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
