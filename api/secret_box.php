<?php
/**
 * 授权码加密盒（原生 PHP，无 composer 依赖）。
 *
 * 背景：QQ 邮箱 SMTP 的登录凭证是 16 位「授权码」，不是 QQ 密码。
 * 它等同于邮箱的收发钥匙，绝不能以明文落在数据库、日志或接口响应里。
 *
 * 本文件原为项目缺失的组件，按调用方约定的文件名 secret_box.php 新建；
 * 只做「字符串 → 密文 → 字符串」这件事，不读 POST、不碰用户态逻辑。
 *
 * 密钥来源优先级：
 *   1. api/config.php 的 mail_secret（推荐：放在 Web 目录之外更稳妥）
 *   2. app_settings 表的 mail_secret_key（首次自动生成并持久化）
 * 换密钥会让旧密文全部解不开；此时让用户重新填一次授权码即可。
 *
 * 依赖：bootstrap.php 必须先加载（lb_config / lb_db / lb_save_settings / lb_setting）。
 */
if (!defined('LIFEBOARD_API')) {
    http_response_code(404);
    exit;
}

const LB_SECRET_METHOD = 'aes-256-gcm';
const LB_SECRET_IV_BYTES = 12;
const LB_SECRET_TAG_BYTES = 16;

/** 取 32 字节二进制密钥。失败返回空串，调用方据此给出明确的安装提示。 */
function lb_secret_key(): string
{
    static $key = null;
    if ($key !== null) {
        return $key;
    }

    /* 1）管理员显式配置的密钥：64 位十六进制，或任意字符串（走 sha256） */
    $configured = '';
    try {
        $cfg = lb_config();
        if (isset($cfg['mail_secret']) && is_string($cfg['mail_secret'])) {
            $configured = trim($cfg['mail_secret']);
        }
    } catch (Throwable $e) {
        $configured = '';
    }
    if ($configured !== '') {
        if (preg_match('/^[0-9a-fA-F]{64}$/', $configured) === 1) {
            $raw = hex2bin($configured);
            $key = $raw === false ? '' : $raw;
        } else {
            $key = hash('sha256', $configured, true);
        }
        return $key;
    }

    /* 2）库里自动生成并保存。用 app_settings 是为了跟站点其它设置走同一套读写，
          不额外建表；生成一次就固定，除非管理员手工清空。 */
    try {
        $saved = lb_setting('mail_secret_key', '');
        if (preg_match('/^[0-9a-fA-F]{64}$/', $saved) === 1) {
            $raw = hex2bin($saved);
            $key = $raw === false ? '' : $raw;
            return $key;
        }
        $hex = bin2hex(random_bytes(32));
        lb_save_settings(['mail_secret_key' => $hex]);
        $key = hex2bin($hex);
        $key = $key === false ? '' : $key;
    } catch (Throwable $e) {
        /* 表还没建、或数据库只读：不要在这里 fatal，交给上层报错 */
        $key = '';
    }
    return $key;
}

/** 当前环境能否加密/解密。部署自检和测试接口都用它。 */
function lb_secret_ready(): bool
{
    return lb_secret_key() !== ''
        && function_exists('openssl_encrypt')
        && in_array(LB_SECRET_METHOD, openssl_get_cipher_methods(), true);
}

/**
 * 加密。返回 base64(iv[12] + tag[16] + ciphertext)，失败返回空串。
 * GCM 自带完整性校验：密文被改动过，解密会直接失败而不是吐出错码。
 */
function lb_secret_encrypt(string $plain): string
{
    if ($plain === '' || !lb_secret_ready()) {
        return '';
    }
    $iv = random_bytes(LB_SECRET_IV_BYTES);
    $tag = '';
    $ct = openssl_encrypt(
        $plain,
        LB_SECRET_METHOD,
        lb_secret_key(),
        OPENSSL_RAW_DATA,
        $iv,
        $tag
    );
    if ($ct === false || strlen($tag) !== LB_SECRET_TAG_BYTES) {
        return '';
    }
    return base64_encode($iv . $tag . $ct);
}

/** 解密。任何异常（含密钥被换、密文损坏）都返回空串，不向调用方抛错。 */
function lb_secret_decrypt(string $enc): string
{
    if ($enc === '' || !lb_secret_ready()) {
        return '';
    }
    $raw = base64_decode($enc, true);
    if ($raw === false || strlen($raw) <= LB_SECRET_IV_BYTES + LB_SECRET_TAG_BYTES) {
        return '';
    }
    $iv = substr($raw, 0, LB_SECRET_IV_BYTES);
    $tag = substr($raw, LB_SECRET_IV_BYTES, LB_SECRET_TAG_BYTES);
    $ct = substr($raw, LB_SECRET_IV_BYTES + LB_SECRET_TAG_BYTES);
    $plain = openssl_decrypt(
        $ct,
        LB_SECRET_METHOD,
        lb_secret_key(),
        OPENSSL_RAW_DATA,
        $iv,
        $tag
    );
    return $plain === false ? '' : $plain;
}
