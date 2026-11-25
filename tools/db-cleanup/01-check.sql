-- ============================================================
-- 明序 · 数据库清洗【第 1 步：只读校验】
-- 库：todo_csl88_top     生成：2026-11-25
--
-- 这个文件里只有 SELECT，不修改任何东西，可以放心先执行。
-- 执行完把 ① ② ③ 三个数字贴给我，对得上再跑第 2 步。
-- ============================================================

-- ① 待删：idcsmart_ 前缀的表，应为 182
SELECT COUNT(*) AS `待删表数_应为182`
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = DATABASE() AND LEFT(TABLE_NAME, 9) = 'idcsmart_';

-- ② 必须保留：明序自己的 10 张，应为 10
SELECT COUNT(*) AS `明序表数_应为10`
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME IN ('users',
                     'boards',
                     'board_revisions',
                     'app_settings',
                     'push_sent',
                     'user_mail_config',
                     'email_codes',
                     'password_resets',
                     'login_attempts',
                     'register_attempts');

-- ③ 双保险：既不是 idcsmart_ 也不在明序白名单里的表，应为 0 行
--    如果查出东西，先别删，把表名发我
SELECT TABLE_NAME AS `未知归属的表_应为空`
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = DATABASE()
  AND LEFT(TABLE_NAME, 9) <> 'idcsmart_'
  AND TABLE_NAME NOT IN ('users',
                     'boards',
                     'board_revisions',
                     'app_settings',
                     'push_sent',
                     'user_mail_config',
                     'email_codes',
                     'password_resets',
                     'login_attempts',
                     'register_attempts');

-- ④ 待删清单（182 行，核对一下有没有眼熟的业务表）
SELECT TABLE_NAME AS `待删表`, TABLE_ROWS AS `约行数`,
       ROUND((DATA_LENGTH + INDEX_LENGTH) / 1024 / 1024, 2) AS `MB`
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = DATABASE() AND LEFT(TABLE_NAME, 9) = 'idcsmart_'
ORDER BY TABLE_NAME;

-- ⑤ 保留清单（应正好 10 行，全是明序的表）
SELECT TABLE_NAME AS `保留表`, TABLE_ROWS AS `约行数`
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME IN ('users',
                     'boards',
                     'board_revisions',
                     'app_settings',
                     'push_sent',
                     'user_mail_config',
                     'email_codes',
                     'password_resets',
                     'login_attempts',
                     'register_attempts')
ORDER BY TABLE_NAME;
