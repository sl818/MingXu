-- 推送发送记录留痕：加 content 列存消息正文
--
-- 目的：设置页的「推送中心」要能显示「最近发了什么」，只存 slot_key 和 kind
-- 看不出具体内容。加上正文后，排查「为什么没收到」时能直接对照。
--
-- 兼容性：代码里对这张表做了「有 content 就写、没有就退回老写法」的判断，
-- 所以不跑这个迁移也不会崩，只是发送记录里看不到正文。
--
-- 在宝塔的 phpMyAdmin 里选中数据库 → SQL → 整段粘贴执行一次。

ALTER TABLE push_sent
  ADD COLUMN content TEXT NULL DEFAULT NULL;
