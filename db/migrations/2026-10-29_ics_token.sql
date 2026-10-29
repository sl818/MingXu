-- 晚风Todo · 增量迁移：日历订阅令牌
-- 适用：已经安装过、users 表还没有 ics_token 字段的站点
-- 在宝塔 phpMyAdmin「SQL」里执行一次即可；重复执行会报「字段已存在」，可忽略。
-- 不影响任何现有数据。

ALTER TABLE users
  ADD COLUMN ics_token VARCHAR(64) NULL DEFAULT NULL,
  ADD UNIQUE KEY uq_users_ics_token (ics_token);
