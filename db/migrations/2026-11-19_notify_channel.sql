-- 通知通道：给发送记录加 channel 维度
-- 在宝塔的 phpMyAdmin 里选中数据库 → SQL → 逐条粘贴执行。
--
-- 为什么需要（v121）：
--   push_sent 的唯一键原本是 (user_id, slot_key)，没有通道。
--   邮件接进调度后，如果邮件先发成功并记了一笔，企业微信就会被判「已发」跳过，
--   两个通道互相顶掉。加 channel 后各自记账，互不影响。
--
-- ⚠️ 顺序不能反（v121.1 修正）：
--   外键 fk_push_sent_user 依赖 user_id 上的索引，uq_push_sent 是它唯一能用的最左前缀
--   索引。所以「先删旧索引」会报 #1553 Cannot drop index 'uq_push_sent': needed in a
--   foreign key constraint。必须先建带 channel 的新唯一键（user_id 仍是它的最左列，
--   能接手外键），再删旧的。
--
-- 逐条执行，已经做过的跳过（报 Duplicate column / Duplicate key 就是做过了）。

-- 1) 加通道列，老数据默认 wecom（与升级前行为一致，不会重复发送）
ALTER TABLE push_sent
  ADD COLUMN channel VARCHAR(16) NOT NULL DEFAULT 'wecom';

-- 2) 先建带通道的唯一键（user_id 在最左，外键能落在这上面）
ALTER TABLE push_sent
  ADD UNIQUE KEY uq_push_sent_channel (user_id, slot_key, channel);

-- 3) 旧唯一键不再需要，此时才能安全删除
ALTER TABLE push_sent
  DROP INDEX uq_push_sent;

-- 完成后自检：应能看到 uq_push_sent_channel，且 channel 列存在
--   SHOW INDEX FROM push_sent;
--   SHOW COLUMNS FROM push_sent LIKE 'channel';
