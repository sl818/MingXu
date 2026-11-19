-- 通知通道：给发送记录加 channel 维度
-- 在宝塔的 phpMyAdmin 里选中数据库 → SQL → 整段粘贴执行一次。
--
-- 为什么需要（v121）：
--   push_sent 的唯一键原本是 (user_id, slot_key)，没有通道。
--   邮件接进调度后，如果邮件先发成功并记了一笔，企业微信就会被判「已发」跳过，
--   两个通道互相顶掉。加 channel 后各自记账，互不影响。
--
-- 老数据：channel 默认 'wecom'，与升级前的行为一致，不会重复发送。

ALTER TABLE push_sent
  ADD COLUMN channel VARCHAR(16) NOT NULL DEFAULT 'wecom';

-- 换唯一键：先删旧的，再建带通道的
ALTER TABLE push_sent
  DROP INDEX uq_push_sent;

ALTER TABLE push_sent
  ADD UNIQUE KEY uq_push_sent_channel (user_id, slot_key, channel);

-- 说明：如果执行时报 "Duplicate entry"，说明同一 slot 已有重复记录，
-- 先清掉重复行再重试：
--   DELETE p1 FROM push_sent p1
--     INNER JOIN push_sent p2
--     ON p1.user_id = p2.user_id AND p1.slot_key = p2.slot_key AND p1.id > p2.id;
