-- ============================================================
-- 明序 · 数据库清洗【第 2 步：删除外来表】
-- 删除 182 张 idcsmart_ 表（另一个 IDC 系统残留），明序 10 张不动
-- 生成：2026-11-25
--
-- ⚠ 执行前必须确认这三件事，缺一件都别跑：
--   1) 已经备份整个库（宝塔 → 数据库 → 备份按钮，或下面的命令）
--   2) 第 1 步校验结果：待删 182 / 明序 10 / 未知归属 空
--   3) 另一个项目已彻底下线，没有定时任务会重建这些表
--
-- 备份命令（在宝塔终端执行，把 <用户>/<密码> 换成数据库账号）：
--   mysqldump -u<用户> -p<密码> todo_csl88_top > /www/backup/todo_20261125.sql
--
-- 回滚：把备份文件导回同一个库即可
--
-- 说明：idcsmart_ 表之间没有任何外键，也没有被明序的表引用，
--       所以不需要关闭外键检查，逐条 DROP 是安全的。
-- ============================================================

SET NAMES utf8mb4;

-- ===== 开始删除（共 182 张）=====
DROP TABLE IF EXISTS `idcsmart_addon_idcsmart_announcement`;
DROP TABLE IF EXISTS `idcsmart_addon_idcsmart_announcement_type`;
DROP TABLE IF EXISTS `idcsmart_addon_idcsmart_certification_company`;
DROP TABLE IF EXISTS `idcsmart_addon_idcsmart_certification_log`;
DROP TABLE IF EXISTS `idcsmart_addon_idcsmart_certification_person`;
DROP TABLE IF EXISTS `idcsmart_addon_idcsmart_file`;
DROP TABLE IF EXISTS `idcsmart_addon_idcsmart_file_folder`;
DROP TABLE IF EXISTS `idcsmart_addon_idcsmart_file_link`;
DROP TABLE IF EXISTS `idcsmart_addon_idcsmart_help`;
DROP TABLE IF EXISTS `idcsmart_addon_idcsmart_help_type`;
DROP TABLE IF EXISTS `idcsmart_addon_idcsmart_news`;
DROP TABLE IF EXISTS `idcsmart_addon_idcsmart_news_type`;
DROP TABLE IF EXISTS `idcsmart_addon_idcsmart_refund`;
DROP TABLE IF EXISTS `idcsmart_addon_idcsmart_refund_product`;
DROP TABLE IF EXISTS `idcsmart_addon_idcsmart_refund_reason`;
DROP TABLE IF EXISTS `idcsmart_addon_idcsmart_renew`;
DROP TABLE IF EXISTS `idcsmart_addon_idcsmart_renew_auto`;
DROP TABLE IF EXISTS `idcsmart_addon_idcsmart_security_group`;
DROP TABLE IF EXISTS `idcsmart_addon_idcsmart_security_group_host_link`;
DROP TABLE IF EXISTS `idcsmart_addon_idcsmart_security_group_link`;
DROP TABLE IF EXISTS `idcsmart_addon_idcsmart_security_group_rule`;
DROP TABLE IF EXISTS `idcsmart_addon_idcsmart_security_group_rule_link`;
DROP TABLE IF EXISTS `idcsmart_addon_idcsmart_ssh_key`;
DROP TABLE IF EXISTS `idcsmart_addon_idcsmart_sub_account`;
DROP TABLE IF EXISTS `idcsmart_addon_idcsmart_sub_account_host`;
DROP TABLE IF EXISTS `idcsmart_addon_idcsmart_sub_account_project`;
DROP TABLE IF EXISTS `idcsmart_addon_idcsmart_ticket`;
DROP TABLE IF EXISTS `idcsmart_addon_idcsmart_ticket_host_link`;
DROP TABLE IF EXISTS `idcsmart_addon_idcsmart_ticket_notes`;
DROP TABLE IF EXISTS `idcsmart_addon_idcsmart_ticket_prereply`;
DROP TABLE IF EXISTS `idcsmart_addon_idcsmart_ticket_reply`;
DROP TABLE IF EXISTS `idcsmart_addon_idcsmart_ticket_status`;
DROP TABLE IF EXISTS `idcsmart_addon_idcsmart_ticket_type`;
DROP TABLE IF EXISTS `idcsmart_addon_idcsmart_ticket_type_admin_link`;
DROP TABLE IF EXISTS `idcsmart_addon_idcsmart_vpc`;
DROP TABLE IF EXISTS `idcsmart_addon_idcsmart_vpc_host_link`;
DROP TABLE IF EXISTS `idcsmart_addon_idcsmart_vpc_link`;
DROP TABLE IF EXISTS `idcsmart_addon_idcsmart_withdraw`;
DROP TABLE IF EXISTS `idcsmart_addon_idcsmart_withdraw_method`;
DROP TABLE IF EXISTS `idcsmart_addon_idcsmart_withdraw_reject_reason`;
DROP TABLE IF EXISTS `idcsmart_addon_idcsmart_withdraw_rule`;
DROP TABLE IF EXISTS `idcsmart_addon_promo_code`;
DROP TABLE IF EXISTS `idcsmart_addon_promo_code_log`;
DROP TABLE IF EXISTS `idcsmart_addon_promo_code_product`;
DROP TABLE IF EXISTS `idcsmart_addon_promo_code_product_need`;
DROP TABLE IF EXISTS `idcsmart_admin`;
DROP TABLE IF EXISTS `idcsmart_admin_field`;
DROP TABLE IF EXISTS `idcsmart_admin_login`;
DROP TABLE IF EXISTS `idcsmart_admin_role`;
DROP TABLE IF EXISTS `idcsmart_admin_role_link`;
DROP TABLE IF EXISTS `idcsmart_admin_role_widget`;
DROP TABLE IF EXISTS `idcsmart_admin_widget`;
DROP TABLE IF EXISTS `idcsmart_api`;
DROP TABLE IF EXISTS `idcsmart_auth`;
DROP TABLE IF EXISTS `idcsmart_auth_link`;
DROP TABLE IF EXISTS `idcsmart_auth_rule`;
DROP TABLE IF EXISTS `idcsmart_auth_rule_link`;
DROP TABLE IF EXISTS `idcsmart_bottom_bar_group`;
DROP TABLE IF EXISTS `idcsmart_bottom_bar_nav`;
DROP TABLE IF EXISTS `idcsmart_cabinet_rental_product`;
DROP TABLE IF EXISTS `idcsmart_cart`;
DROP TABLE IF EXISTS `idcsmart_client`;
DROP TABLE IF EXISTS `idcsmart_client_credit`;
DROP TABLE IF EXISTS `idcsmart_client_custom_field`;
DROP TABLE IF EXISTS `idcsmart_client_login`;
DROP TABLE IF EXISTS `idcsmart_client_record`;
DROP TABLE IF EXISTS `idcsmart_clientarea_auth`;
DROP TABLE IF EXISTS `idcsmart_clientarea_auth_rule`;
DROP TABLE IF EXISTS `idcsmart_clientarea_auth_rule_link`;
DROP TABLE IF EXISTS `idcsmart_cloud_server_area`;
DROP TABLE IF EXISTS `idcsmart_cloud_server_banner`;
DROP TABLE IF EXISTS `idcsmart_cloud_server_discount`;
DROP TABLE IF EXISTS `idcsmart_cloud_server_product`;
DROP TABLE IF EXISTS `idcsmart_config_option`;
DROP TABLE IF EXISTS `idcsmart_config_option_sub`;
DROP TABLE IF EXISTS `idcsmart_configuration`;
DROP TABLE IF EXISTS `idcsmart_consult`;
DROP TABLE IF EXISTS `idcsmart_country`;
DROP TABLE IF EXISTS `idcsmart_email_log`;
DROP TABLE IF EXISTS `idcsmart_email_template`;
DROP TABLE IF EXISTS `idcsmart_feedback`;
DROP TABLE IF EXISTS `idcsmart_feedback_type`;
DROP TABLE IF EXISTS `idcsmart_file_log`;
DROP TABLE IF EXISTS `idcsmart_friendly_link`;
DROP TABLE IF EXISTS `idcsmart_honor`;
DROP TABLE IF EXISTS `idcsmart_host`;
DROP TABLE IF EXISTS `idcsmart_host_config_option`;
DROP TABLE IF EXISTS `idcsmart_host_ip`;
DROP TABLE IF EXISTS `idcsmart_icp_service_product`;
DROP TABLE IF EXISTS `idcsmart_index_banner`;
DROP TABLE IF EXISTS `idcsmart_menu`;
DROP TABLE IF EXISTS `idcsmart_module_idcsmart_common_custom_cycle`;
DROP TABLE IF EXISTS `idcsmart_module_idcsmart_common_custom_cycle_pricing`;
DROP TABLE IF EXISTS `idcsmart_module_idcsmart_common_host_configoption`;
DROP TABLE IF EXISTS `idcsmart_module_idcsmart_common_pricing`;
DROP TABLE IF EXISTS `idcsmart_module_idcsmart_common_product`;
DROP TABLE IF EXISTS `idcsmart_module_idcsmart_common_product_configoption`;
DROP TABLE IF EXISTS `idcsmart_module_idcsmart_common_product_configoption_sub`;
DROP TABLE IF EXISTS `idcsmart_module_idcsmart_common_product_custom_field`;
DROP TABLE IF EXISTS `idcsmart_module_idcsmart_common_product_custom_field_value`;
DROP TABLE IF EXISTS `idcsmart_module_idcsmart_common_server`;
DROP TABLE IF EXISTS `idcsmart_module_idcsmart_common_server_group`;
DROP TABLE IF EXISTS `idcsmart_module_idcsmart_common_server_host_link`;
DROP TABLE IF EXISTS `idcsmart_module_mf_cloud_backup_config`;
DROP TABLE IF EXISTS `idcsmart_module_mf_cloud_config`;
DROP TABLE IF EXISTS `idcsmart_module_mf_cloud_config_limit`;
DROP TABLE IF EXISTS `idcsmart_module_mf_cloud_data_center`;
DROP TABLE IF EXISTS `idcsmart_module_mf_cloud_disk`;
DROP TABLE IF EXISTS `idcsmart_module_mf_cloud_disk_limit`;
DROP TABLE IF EXISTS `idcsmart_module_mf_cloud_duration`;
DROP TABLE IF EXISTS `idcsmart_module_mf_cloud_host_image_link`;
DROP TABLE IF EXISTS `idcsmart_module_mf_cloud_host_link`;
DROP TABLE IF EXISTS `idcsmart_module_mf_cloud_image`;
DROP TABLE IF EXISTS `idcsmart_module_mf_cloud_image_group`;
DROP TABLE IF EXISTS `idcsmart_module_mf_cloud_limit_rule`;
DROP TABLE IF EXISTS `idcsmart_module_mf_cloud_line`;
DROP TABLE IF EXISTS `idcsmart_module_mf_cloud_option`;
DROP TABLE IF EXISTS `idcsmart_module_mf_cloud_price`;
DROP TABLE IF EXISTS `idcsmart_module_mf_cloud_recommend_config`;
DROP TABLE IF EXISTS `idcsmart_module_mf_cloud_recommend_config_upgrade_range`;
DROP TABLE IF EXISTS `idcsmart_module_mf_cloud_resource_package`;
DROP TABLE IF EXISTS `idcsmart_module_mf_cloud_vpc_network`;
DROP TABLE IF EXISTS `idcsmart_module_mf_dcim_config`;
DROP TABLE IF EXISTS `idcsmart_module_mf_dcim_config_limit`;
DROP TABLE IF EXISTS `idcsmart_module_mf_dcim_data_center`;
DROP TABLE IF EXISTS `idcsmart_module_mf_dcim_duration`;
DROP TABLE IF EXISTS `idcsmart_module_mf_dcim_host_image_link`;
DROP TABLE IF EXISTS `idcsmart_module_mf_dcim_host_link`;
DROP TABLE IF EXISTS `idcsmart_module_mf_dcim_host_option_link`;
DROP TABLE IF EXISTS `idcsmart_module_mf_dcim_image`;
DROP TABLE IF EXISTS `idcsmart_module_mf_dcim_image_group`;
DROP TABLE IF EXISTS `idcsmart_module_mf_dcim_limit_rule`;
DROP TABLE IF EXISTS `idcsmart_module_mf_dcim_line`;
DROP TABLE IF EXISTS `idcsmart_module_mf_dcim_model_config`;
DROP TABLE IF EXISTS `idcsmart_module_mf_dcim_model_config_option_link`;
DROP TABLE IF EXISTS `idcsmart_module_mf_dcim_option`;
DROP TABLE IF EXISTS `idcsmart_module_mf_dcim_package`;
DROP TABLE IF EXISTS `idcsmart_module_mf_dcim_package_option_link`;
DROP TABLE IF EXISTS `idcsmart_module_mf_dcim_price`;
DROP TABLE IF EXISTS `idcsmart_nav`;
DROP TABLE IF EXISTS `idcsmart_notice_setting`;
DROP TABLE IF EXISTS `idcsmart_oauth`;
DROP TABLE IF EXISTS `idcsmart_order`;
DROP TABLE IF EXISTS `idcsmart_order_item`;
DROP TABLE IF EXISTS `idcsmart_order_tmp`;
DROP TABLE IF EXISTS `idcsmart_partner`;
DROP TABLE IF EXISTS `idcsmart_physical_server_area`;
DROP TABLE IF EXISTS `idcsmart_physical_server_banner`;
DROP TABLE IF EXISTS `idcsmart_physical_server_discount`;
DROP TABLE IF EXISTS `idcsmart_physical_server_product`;
DROP TABLE IF EXISTS `idcsmart_plugin`;
DROP TABLE IF EXISTS `idcsmart_plugin_hook`;
DROP TABLE IF EXISTS `idcsmart_price`;
DROP TABLE IF EXISTS `idcsmart_product`;
DROP TABLE IF EXISTS `idcsmart_product_duration_ratio`;
DROP TABLE IF EXISTS `idcsmart_product_group`;
DROP TABLE IF EXISTS `idcsmart_product_upgrade_product`;
DROP TABLE IF EXISTS `idcsmart_refund_record`;
DROP TABLE IF EXISTS `idcsmart_self_defined_field`;
DROP TABLE IF EXISTS `idcsmart_self_defined_field_value`;
DROP TABLE IF EXISTS `idcsmart_seo`;
DROP TABLE IF EXISTS `idcsmart_server`;
DROP TABLE IF EXISTS `idcsmart_server_group`;
DROP TABLE IF EXISTS `idcsmart_server_hosting_area`;
DROP TABLE IF EXISTS `idcsmart_server_hosting_product`;
DROP TABLE IF EXISTS `idcsmart_side_floating_window`;
DROP TABLE IF EXISTS `idcsmart_sms_log`;
DROP TABLE IF EXISTS `idcsmart_sms_service_product`;
DROP TABLE IF EXISTS `idcsmart_sms_template`;
DROP TABLE IF EXISTS `idcsmart_ssl_certificate_product`;
DROP TABLE IF EXISTS `idcsmart_supplier`;
DROP TABLE IF EXISTS `idcsmart_system_log`;
DROP TABLE IF EXISTS `idcsmart_task`;
DROP TABLE IF EXISTS `idcsmart_task_wait`;
DROP TABLE IF EXISTS `idcsmart_trademark_register_product`;
DROP TABLE IF EXISTS `idcsmart_trademark_service_product`;
DROP TABLE IF EXISTS `idcsmart_transaction`;
DROP TABLE IF EXISTS `idcsmart_upgrade`;
DROP TABLE IF EXISTS `idcsmart_upstream_host`;
DROP TABLE IF EXISTS `idcsmart_upstream_order`;
DROP TABLE IF EXISTS `idcsmart_upstream_product`;
DROP TABLE IF EXISTS `idcsmart_web_nav`;

-- ===== 校验：应只剩 10 张，全部是明序的表 =====
SELECT TABLE_NAME AS `剩余表`, TABLE_ROWS AS `约行数`
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = DATABASE()
ORDER BY TABLE_NAME;
