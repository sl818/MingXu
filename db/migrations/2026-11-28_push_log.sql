-- 历史推送记录（v216）：每一条「实际尝试发送」的推送留痕，成功/失败/跳过三态。
--
-- 目的：
--   之前只有 push_sent（成功才落库、失败删占位），发送失败不留任何痕迹——
--   用户问「这条提醒为什么没收到」时无从查起。push_log 补上这块：
--   status = ok（发出去了）/ fail（尝试了但失败，error 存返回提示）/ skip（板块或实例停用，整条没发）。
--
-- 与 push_sent 的分工：
--   push_sent = 去重账本（同一条同一通道只发一次），只记成功；
--   push_log = 观测日志（给人看的），成功失败都记，不参与去重判定。
--
-- 兼容性：
--   代码对这张表做「存在才写、不存在就跳过」的检测（lb_push_log_ready），
--   不跑这个迁移也不会崩，只是历史记录面板显示「暂无数据」。
--
-- 在宝塔的 phpMyAdmin 里选中数据库 → SQL → 整段粘贴执行一次。

CREATE TABLE IF NOT EXISTS push_log (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id INT UNSIGNED NOT NULL,
  at DATETIME NOT NULL,
  channel VARCHAR(16) NOT NULL DEFAULT '',
  board VARCHAR(16) NOT NULL DEFAULT '',
  kind VARCHAR(12) NOT NULL DEFAULT '',
  slot_key VARCHAR(120) NOT NULL DEFAULT '',
  content TEXT NULL DEFAULT NULL,
  status VARCHAR(8) NOT NULL DEFAULT 'ok',
  error VARCHAR(500) NULL DEFAULT NULL,
  PRIMARY KEY (id),
  KEY idx_push_log_user_time (user_id, at),
  CONSTRAINT fk_push_log_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 如果你在 v222/v223 阶段已经建过这张表（没有 board 列），再补一条：
--   ALTER TABLE push_log ADD COLUMN board VARCHAR(16) NOT NULL DEFAULT '';
-- （报 Duplicate column 就是已经加过了，跳过即可）

-- 完成后自检：应能看到 push_log 表与 board 列
--   SHOW TABLES LIKE 'push_log';
--   SHOW COLUMNS FROM push_log LIKE 'board';
