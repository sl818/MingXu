-- 晚风Todo · 数据库结构（全新安装）
-- 先在宝塔创建空数据库，再导入本文件；安装器也会自动执行它。
-- MySQL 5.7+ / 8.0，字符集 utf8mb4

CREATE TABLE IF NOT EXISTS users (
  id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  email VARCHAR(190) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  display_name VARCHAR(40) NOT NULL DEFAULT '',
  is_admin TINYINT(1) NOT NULL DEFAULT 0,
  status ENUM('active', 'disabled') NOT NULL DEFAULT 'active',
  session_epoch INT UNSIGNED NOT NULL DEFAULT 0,
  ics_token VARCHAR(64) NULL DEFAULT NULL,
  push_webhook VARCHAR(255) NULL DEFAULT NULL,
  push_enabled TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_login_at DATETIME NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_users_email (email),
  UNIQUE KEY uq_users_ics_token (ics_token)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS boards (
  user_id INT UNSIGNED NOT NULL,
  data LONGTEXT NOT NULL,
  rev INT UNSIGNED NOT NULL DEFAULT 1,
  updated_at BIGINT UNSIGNED NOT NULL,
  PRIMARY KEY (user_id),
  CONSTRAINT fk_boards_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS board_revisions (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id INT UNSIGNED NOT NULL,
  rev INT UNSIGNED NOT NULL,
  data LONGTEXT NOT NULL,
  reason VARCHAR(16) NOT NULL DEFAULT 'save',
  created_at BIGINT UNSIGNED NOT NULL,
  PRIMARY KEY (id),
  KEY idx_revisions_user_time (user_id, created_at),
  KEY idx_revisions_user_id (user_id, id),
  CONSTRAINT fk_revisions_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS push_sent (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id INT UNSIGNED NOT NULL,
  slot_key VARCHAR(120) NOT NULL,
  kind VARCHAR(12) NOT NULL DEFAULT '',
  sent_at DATETIME NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_push_sent (user_id, slot_key),
  KEY idx_push_sent_time (sent_at),
  CONSTRAINT fk_push_sent_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS app_settings (
  k VARCHAR(64) NOT NULL,
  v TEXT NOT NULL,
  PRIMARY KEY (k)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS login_attempts (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  ip VARCHAR(45) NOT NULL,
  email VARCHAR(190) NOT NULL,
  at DATETIME NOT NULL,
  PRIMARY KEY (id),
  KEY idx_attempts (ip, at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS register_attempts (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  ip VARCHAR(45) NOT NULL,
  at DATETIME NOT NULL,
  PRIMARY KEY (id),
  KEY idx_register_attempts (ip, at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
