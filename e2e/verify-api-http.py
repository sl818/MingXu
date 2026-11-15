# -*- coding: utf-8 -*-
"""后端 HTTP 层验证：真起一个 PHP 站点，用 SQLite 顶替 MySQL，看真实响应。

为什么需要它：`php -l` 只查语法，单测只查纯函数，
而「响应头对不对」「HEAD 能不能用」「订阅请求会不会留下垃圾 session 文件」
这些问题只有真发一次请求才看得见。小米日历加不上订阅就是死在这一层。

依赖：tempfile/php82（或 php81）/php.exe（pdo_sqlite 扩展）。没有就跳过并说明。

用法：python e2e/verify-api-http.py
"""
import io
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 本机 PHP 版本随环境变，先找 php82 再退回 php81
PHP = os.path.join(tempfile.gettempdir(), 'php82', 'php.exe')
if not os.path.exists(PHP):
    PHP = os.path.join(tempfile.gettempdir(), 'php81', 'php.exe')
SITE = os.path.join(tempfile.gettempdir(), 'lb-http-test')
TOKEN = 'a' * 64
PORT = 8917
# 单独的 session 目录：既方便统计，也不会去动系统的临时目录。
# 注意 PHP 的 session 文件名是 sess_<id>，不含 session_name，所以只能按目录统计。
SESS_DIR = os.path.join(SITE, 'sess')

PASS = 0
FAILS = []


def chk(name, ok, detail=''):
    global PASS
    if ok:
        PASS += 1
        print('  \u2713 %s' % name)
    else:
        FAILS.append((name, detail))
        print('  \u2717 %s  << %s' % (name, detail))


if not os.path.isfile(PHP):
    print('跳过：找不到 %s' % PHP)
    print('（这是后端 HTTP 验证，需要本机 PHP；语法和纯函数测试不受影响）')
    sys.exit(0)

# ---------- 准备站点 ----------
if os.path.isdir(SITE):
    shutil.rmtree(SITE)
os.makedirs(os.path.join(SITE, 'api'))
shutil.copy(os.path.join(ROOT, 'api.php'), SITE)
# 把 api/ 下所有后端文件都带上（不含 config.php，测试用自己伪造的那份）。
# 以前是写死文件名，加了 push.php / schedule.php 之后站点起不来，全部 500——
# 那种失败看起来像「接口坏了」，其实是测试环境缺文件，很容易误判。
for f in sorted(os.listdir(os.path.join(ROOT, 'api'))):
    if f.endswith('.php') and f != 'config.php':
        shutil.copy(os.path.join(ROOT, 'api', f), os.path.join(SITE, 'api', f))

# 把「临时副本」的 DSN 换成 SQLite，真文件不动
bp = os.path.join(SITE, 'api', 'bootstrap.php')
s = io.open(bp, encoding='utf-8', newline='').read()
old_dsn = """    $dsn = 'mysql:host=' . $db['host'] . ';port=' . (int)$db['port']
        . ';dbname=' . $db['name'] . ';charset=' . $db['charset'];
    $pdo = new PDO($dsn, (string)$db['user'], (string)$db['pass'], ["""
if s.count(old_dsn) != 1:
    print('失败：bootstrap.php 的 DSN 结构和脚本预期不一致，请同步更新本脚本')
    sys.exit(1)
s = s.replace(old_dsn, "    $dsn = 'sqlite:' . $db['path'];\n    $pdo = new PDO($dsn, null, null, [")
io.open(bp, 'w', encoding='utf-8', newline='').write(s)

io.open(os.path.join(SITE, 'api', 'config.php'), 'w', encoding='utf-8').write(
    "<?php\nreturn ['db'=>['path'=>%r],'session_name'=>'lbhttptest',"
    "'max_bytes'=>2097152,'cookie_secure'=>'auto'];\n" % os.path.join(SITE, 't.db'))
io.open(os.path.join(SITE, 'install.lock'), 'w').write('')

state = {
    'habits': [{'id': 'h_breathe', 'name': '478呼吸法', 'icon': '🌬️', 'type': 'build',
                'target': 1, 'unit': '组', 'suggestTime': '15:00', 'note': ''}],
    'meds': [{'id': 'm1', 'name': '阿莫西林', 'status': 'active', 'times': ['08:00', '20:00'],
              'startDate': '2026-10-01', 'endDate': '', 'doseAmount': 1, 'doseUnit': '片',
              'form': '片', 'note': ''}],
    'tasks': [{'id': 't1', 'title': '每日复盘', 'status': 'todo', 'due': '2026-10-25',
               'repeat': 'daily', 'repeatTime': '07:30', 'repeatWeekday': 0,
               'repeatDay': 25, 'note': ''}],
    'checks': {}, 'notes': {}, 'moods': {}, 'events': [], 'doses': {},
}

db = sqlite3.connect(os.path.join(SITE, 't.db'))
db.executescript("""
CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT, password_hash TEXT, display_name TEXT,
  is_admin INTEGER DEFAULT 0, status TEXT DEFAULT 'active', session_epoch INTEGER DEFAULT 0,
  ics_token TEXT, push_webhook TEXT, push_enabled INTEGER DEFAULT 0,
  created_at TEXT, last_login_at TEXT);
CREATE TABLE boards (user_id INTEGER PRIMARY KEY, data TEXT, rev INTEGER, updated_at INTEGER);
CREATE TABLE push_sent (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
  slot_key TEXT, kind TEXT, sent_at TEXT);
CREATE TABLE app_settings (k TEXT PRIMARY KEY, v TEXT);
""")
db.execute("INSERT INTO users (id,email,status,ics_token) VALUES (1,'x@y.z','active',?)", (TOKEN,))
db.execute("INSERT INTO boards VALUES (1,?,5,1)", (json.dumps(state, ensure_ascii=False),))
db.commit()
db.close()

BASE = 'http://127.0.0.1:%d/api.php' % PORT


def count_sessions():
    try:
        return len([f for f in os.listdir(SESS_DIR) if f.startswith('sess_')])
    except OSError:
        return 0


def req(url, method='GET'):
    r = urllib.request.Request(url, method=method)
    try:
        with urllib.request.urlopen(r) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


os.makedirs(SESS_DIR, exist_ok=True)

proc = subprocess.Popen(
    [PHP, '-d', 'extension_dir=' + os.path.join(os.path.dirname(PHP), 'ext'),
     '-d', 'extension=pdo_sqlite', '-d', 'session.save_path=' + SESS_DIR,
     '-S', '127.0.0.1:%d' % PORT, '-t', SITE],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

try:
    for _ in range(60):
        try:
            req(BASE + '?action=status')
            break
        except Exception:
            time.sleep(0.1)

    print('\n[1] 订阅：基本响应')
    st, hd, body = req('%s?ics=%s' % (BASE, TOKEN))
    chk('GET 返回 200', st == 200, 'status=%d' % st)
    chk('Content-Type 是 text/calendar',
        'text/calendar' in hd.get('Content-Type', ''), hd.get('Content-Type', ''))
    chk('Content-Disposition 没有反斜杠转义',
        'filename="wanfeng-todo.ics"' in hd.get('Content-Disposition', '')
        and '\\' not in hd.get('Content-Disposition', ''),
        repr(hd.get('Content-Disposition')))
    chk('Content-Length 与正文长度一致',
        hd.get('Content-Length') == str(len(body)),
        '头=%s 实际=%d' % (hd.get('Content-Length'), len(body)))
    chk('Cache-Control 允许短缓存',
        'max-age=' in hd.get('Cache-Control', ''), hd.get('Cache-Control', ''))
    chk('正文以 BEGIN:VCALENDAR 开头', body.startswith(b'BEGIN:VCALENDAR'))
    chk('正文用 CRLF', b'\r\n' in body and body.count(b'\n') == body.count(b'\r\n'))
    chk('没有 METHOD（订阅源不需要）', b'METHOD:' not in body)
    chk('声明了刷新间隔', b'REFRESH-INTERVAL' in body and b'X-PUBLISHED-TTL' in body)

    print('\n[2] 订阅：方法与其他')
    st, hd, body = req('%s?ics=%s' % (BASE, TOKEN), method='HEAD')
    chk('HEAD 返回 200（客户端会先探测）', st == 200, 'status=%d' % st)
    chk('HEAD 也带 Content-Length', hd.get('Content-Length') is not None)
    st, _, _ = req('%s?ics=%s' % (BASE, TOKEN), method='POST')
    chk('POST 返回 405', st == 405, 'status=%d' % st)
    st, _, body = req('%s?ics=%s' % (BASE, 'z' * 10))
    chk('坏令牌返回 200 + 空日历（404 会被上游换成 HTML）',
        st == 200 and b'BEGIN:VCALENDAR' in body and b'VEVENT' not in body,
        'status=%d' % st)
    chk('空日历里写明地址已失效', '订阅地址无效'.encode('utf-8') in body)
    st, _, body = req('%s?ics=%s' % (BASE, ''))
    chk('空令牌也是 200 空日历', st == 200 and b'VEVENT' not in body, 'status=%d' % st)
    st, _, _ = req('%s?action=ics&token=%s' % (BASE, TOKEN))
    chk('旧的 ?action=ics&token= 仍可用', st == 200, 'status=%d' % st)
    st, hd, body = req('%s?ics=%s.ics' % (BASE, TOKEN))
    chk('地址带 .ics 后缀也能取到（安卓日历按后缀判断）',
        st == 200 and body.startswith(b'BEGIN:VCALENDAR'), 'status=%d' % st)
    st, _, body = req('%s?ics=%s.ics' % (BASE, 'z' * 10))
    chk('带后缀的坏令牌同样 200 空日历', st == 200 and b'VEVENT' not in body,
        'status=%d' % st)

    print('\n[3] 订阅不产生会话文件')
    req(BASE + '?action=me')          # 先制造一个会话文件，否则下面的计数为 0 是假通过
    before = count_sessions()
    chk('计数本身有效（已有会话文件）', before > 0, 'before=%d' % before)
    for _ in range(5):
        req('%s?ics=%s' % (BASE, TOKEN))
    after = count_sessions()
    chk('连打 5 次订阅，session 文件不增加', after == before,
        '前=%d 后=%d' % (before, after))

    print('\n[4] 其他接口仍需要会话')
    st, _, body = req(BASE + '?action=load')
    chk('未登录读数据返回 401', st == 401, 'status=%d' % st)
    st, _, body = req(BASE + '?action=me')
    chk('me 正常返回', st == 200 and b'"ok":true' in body, 'status=%d' % st)
    chk('me 会创建会话（说明会话没被整体跳过）', count_sessions() > after,
        'now=%d' % count_sessions())

    print('\n[4b] 推送接口的鉴权与降级')
    st, _, _ = req(BASE + '?action=push_status')
    chk('push_status 未登录返回 401', st == 401, 'status=%d' % st)
    st, _, _ = req(BASE + '?action=push_preview')
    chk('push_preview 未登录返回 401', st == 401, 'status=%d' % st)
    # 写接口先校验方法再校验身份，所以要用 POST 才能看到 401
    for act in ('push_save', 'push_test', 'push_off'):
        st, _, _ = req('%s?action=%s' % (BASE, act), method='POST')
        chk('%s 未登录返回 401' % act, st == 401, 'status=%d' % st)
    st, _, _ = req(BASE + '?action=push_status', method='POST')
    chk('push_status 用 POST 返回 405', st == 405, 'status=%d' % st)
    st, _, _ = req(BASE + '?action=push_preview', method='POST')
    chk('push_preview 用 POST 返回 405', st == 405, 'status=%d' % st)
    st, _, _ = req(BASE + '?action=push_save')
    chk('push_save 用 GET 返回 405', st == 405, 'status=%d' % st)

    print('\n[5] 探测与未知路径')
    st, _, body = req(BASE)
    chk('不带 action 的探测返回 200 JSON（客户端会先探活）',
        st == 200 and b'"ok":true' in body, 'status=%d' % st)
    st, _, _ = req(BASE + '?action=nosuch')
    chk('未知 action 仍是 404', st == 404, 'status=%d' % st)

finally:
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except Exception:
        proc.kill()
    shutil.rmtree(SITE, ignore_errors=True)

print('\n' + '=' * 46)
print('PASS %d / %d' % (PASS, PASS + len(FAILS)))
if FAILS:
    for n, d in FAILS:
        print('  FAIL: %s | %s' % (n, d))
    sys.exit(1)
print('后端 HTTP 层全部通过')
