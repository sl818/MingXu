-- 手机推送（企业微信群机器人）
-- 在宝塔的 phpMyAdmin 里选中数据库 → SQL → 整段粘贴执行一次。
-- 只需执行一次；重复执行会因为列已存在而报错，不影响数据。

ALTER TABLE users
  ADD COLUMN push_webhook VARCHAR(255) NULL DEFAULT NULL,
  ADD COLUMN push_enabled TINYINT(1) NOT NULL DEFAULT 0;

-- 发送记录：唯一索引就是去重手段。
-- 定时任务每分钟跑一次，靠 INSERT IGNORE 判断「这条是否已经发过」，
-- 比「先查再插」可靠（并发和延迟都安全）。
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
