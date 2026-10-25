-- 晚风Todo · 增量迁移：云端历史版本
-- 适用：已经安装过、数据库里还没有 board_revisions 的站点
-- 在宝塔 phpMyAdmin 或命令行执行一次即可；重复执行会报“表已存在”，可忽略。
-- 不会修改现有 boards / users / app_settings 数据。

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
