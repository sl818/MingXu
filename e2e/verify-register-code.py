# -*- coding: utf-8 -*-
"""v126 注册邮箱验证：三种注册方式、注册弹窗分支、验证码发送、入口文案。"""
import http.server, threading, json, socketserver, secrets, sys
from playwright.sync_api import sync_playwright

DOC = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo'
USER = {'id': 1, 'email': 'admin@sl00.top', 'display_name': '管理员', 'is_admin': True,
        'status': 'active', 'created_at': '2026-10-01 00:00:00', 'last_login_at': None}
sessions = {}
CALLS = []
MODE = {'v': 'email'}          # 当前注册方式，可在用例里改
MAIL_READY = {'v': True}
SETTINGS = {'registration_open': True, 'registration_mode': 'email',
            'site_mail_ready': True, 'invite_code': 'ABCD', 'site_name': '明序'}
BOARD = {'data': {'version': 2, 'habits': [], 'tasks': [], 'checks': {}, 'essays': [], 'weights': [],
                  'meds': [], 'medLogs': {}, 'money': {}, 'settings': {}, 'essayTags': [], 'quit': {}}, 'rev': 1}


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _j(self, obj, code=200, eh=None):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(b)))
        for k, v in (eh or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(b)

    def _auth(self):
        for part in (self.headers.get('Cookie') or '').split(';'):
            if part.strip().startswith('sid='):
                return sessions.get(part.strip()[4:])
        return None

    def _reg(self):
        m = MODE['v']
        return {'registration_open': m != 'closed', 'registration_mode': m,
                'need_invite': m == 'invite', 'need_code': m == 'email',
                'code_ready': MAIL_READY['v'] if m == 'email' else False}

    def do_GET(self):
        if self.path.startswith('/index.html') or self.path.split('?')[0] == '/':
            body = open(DOC + '/index.html', 'rb').read()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path.startswith('/assets/'):
            p = DOC + self.path.split('?')[0]
            try:
                body = open(p, 'rb').read()
                self.send_response(200)
                self.send_header('Content-Type', 'text/css' if p.endswith('.css') else 'application/javascript')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except Exception:
                self.send_response(404)
                self.end_headers()
            return
        if self.path.startswith('/api.php'):
            a = self.path.split('action=')[-1].split('&')[0]
            u = self._auth()
            if a == 'me':
                self._j(dict({'ok': True, 'user': USER if u else None, 'csrf': 'x',
                              'site_name': '明序'}, **self._reg()))
            elif a == 'status':
                self._j({'ok': True, 'installed': True})
            elif a == 'load':
                self._j({'ok': True, 'data': BOARD['data'], 'rev': 1, 'updated_at': 1792813000000, 'history': []})
            elif a == 'admin_users':
                self._j({'ok': True, 'users': [USER]})
            elif a == 'admin_settings':
                self._j({'ok': True, 'settings': SETTINGS})
            elif a in ('push_status', 'ics_status'):
                self._j({'ok': True, 'enabled': False, 'webhook_set': False, 'token': 'x', 'url': 'x'})
            elif a == 'mail_status':
                self._j({'ok': True, 'config': {'hasSecret': False, 'enabled': False}, 'crypto_ready': True, 'recipient': 'a@b.com'})
            elif a == 'site_mail_status':
                self._j({'ok': True, 'config': {'host': 'smtp.qq.com', 'port': 465, 'secure': 'ssl',
                                                'user': 'a@b.com', 'from': 'a@b.com', 'name': '明序',
                                                'hasSecret': True}, 'ready': True, 'admin_email': 'a@b.com'})
            elif a == 'notify_prefs':
                self._j({'ok': True, 'kinds': {}, 'channels': {}, 'prefs': {}, 'quiet': False, 'report': {}})
            else:
                self._j({'ok': False, 'error': 'unknown'}, 404)
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        if not self.path.startswith('/api.php'):
            self.send_response(405)
            self.end_headers()
            return
        a = self.path.split('action=')[-1].split('&')[0]
        n = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(n) or b'{}')
        CALLS.append((a, body))
        if a == 'login':
            sid = secrets.token_hex(8)
            sessions[sid] = USER
            self._j({'ok': True, 'user': USER, 'csrf': 'x'}, eh={'Set-Cookie': 'sid=' + sid + '; Path=/'})
        elif a == 'register_code':
            if MODE['v'] != 'email':
                self._j({'ok': False, 'error': '当前不是邮箱验证注册'}, 400)
                return
            if body.get('email') == 'taken@example.com':
                self._j({'ok': False, 'error': '这个邮箱已经注册过了，直接登录即可'}, 409)
                return
            self._j({'ok': True, 'sent': True, 'email': body.get('email')})
        elif a == 'register':
            if MODE['v'] == 'email' and body.get('code') != '555666':
                self._j({'ok': False, 'error': '验证码不正确或已过期，请重新获取'}, 400)
                return
            self._j(dict({'ok': True, 'user': USER, 'csrf': 'x', 'site_name': '明序'}, **self._reg()))
        elif a in ('save', 'force'):
            self._j({'ok': True, 'rev': 2, 'updated_at': 1792813000000})
        else:
            self._j({'ok': False, 'error': '?'}, 404)


class TS(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


srv = TS(('127.0.0.1', 0), H)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()

ok = [0, 0]


def rec(name, cond, note=''):
    if cond:
        ok[0] += 1
        print('PASS ', name, ' |', str(note)[:80])
    else:
        ok[1] += 1
        print('FAIL ', name, ' |', str(note)[:80])


def boot(pg, mode, mail_ready=True):
    MODE['v'] = mode
    MAIL_READY['v'] = mail_ready
    pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
    pg.wait_for_timeout(900)


with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)
    ctx = br.new_context(viewport={'width': 1360, 'height': 900})
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)[:120]))
    pg.add_init_script("try{localStorage.setItem('lifeboard.theme.mode','light');"
                       "localStorage.setItem('lifeboard.skin','paper')}catch(e){}")

    print('=== email 模式：注册弹窗 ===')
    boot(pg, 'email')
    if pg.locator('[data-act="cloud-login"]').count():
        pg.click('[data-act="cloud-login"]')
        pg.wait_for_timeout(500)
    login_txt = pg.locator('.modal-card').inner_text()
    rec('登录框写「用邮箱注册」', '用邮箱注册' in login_txt, login_txt[:60])
    rec('登录框写明需收验证码', '需收验证码' in login_txt, '')

    pg.click('#cloud-login-form [data-act="cloud-register"]')
    pg.wait_for_timeout(500)
    form = pg.locator('#cloud-register-form')
    rec('注册弹窗带 data-mode=email', form.get_attribute('data-mode') == 'email')
    rec('有验证码输入框', pg.locator('#cloud-register-form input[name="code"]').count() == 1)
    rec('有发送验证码按钮', pg.locator('[data-act="reg-send-code"]').count() == 1)
    rec('没有邀请码输入框', pg.locator('#cloud-register-form input[name="invite"]').count() == 0)
    rec('说明写了 10 分钟有效', '10 分钟' in form.inner_text(), form.inner_text()[:60])

    print('\n=== 发送验证码 ===')
    pg.fill('#cloud-register-form input[name="email"]', 'new@example.com')
    pg.click('[data-act="reg-send-code"]')
    pg.wait_for_timeout(900)
    sent = [b for a, b in CALLS if a == 'register_code']
    rec('调了 register_code', len(sent) == 1, str(sent))
    rec('提交的邮箱正确', sent and sent[0].get('email') == 'new@example.com', str(sent))
    btn_txt = pg.locator('[data-act="reg-send-code"]').inner_text()
    rec('按钮进入倒计时', '秒后重发' in btn_txt, btn_txt)
    rec('倒计时期间按钮禁用', pg.locator('[data-act="reg-send-code"]').is_disabled())

    print('\n=== 验证码错误与正确 ===')
    pg.fill('#cloud-register-form input[name="password"]', 'newpass123')
    pg.fill('#cloud-register-form input[name="password_confirm"]', 'newpass123')
    pg.fill('#cloud-register-form input[name="code"]', '111111')
    pg.click('#cloud-register-form button[type="submit"]')
    pg.wait_for_timeout(800)
    rec('错误验证码显示服务端提示', '验证码不正确' in pg.locator('#cloud-register-form .cloud-error').inner_text(),
        pg.locator('#cloud-register-form .cloud-error').inner_text())

    pg.fill('#cloud-register-form input[name="code"]', '555666')
    pg.click('#cloud-register-form button[type="submit"]')
    pg.wait_for_timeout(1200)
    reg_calls = [b for a, b in CALLS if a == 'register']
    rec('注册请求带上验证码', reg_calls and reg_calls[-1].get('code') == '555666', str(reg_calls[-1]) if reg_calls else '')

    print('\n=== invite 模式 ===')
    boot(pg, 'invite')
    if pg.locator('[data-act="cloud-login"]').count():
        pg.click('[data-act="cloud-login"]')
        pg.wait_for_timeout(500)
    rec('登录框回到「用邀请码注册」', '用邀请码注册' in pg.locator('.modal-card').inner_text())
    pg.click('#cloud-login-form [data-act="cloud-register"]')
    pg.wait_for_timeout(500)
    rec('有邀请码输入框', pg.locator('#cloud-register-form input[name="invite"]').count() == 1)
    rec('没有验证码输入框', pg.locator('#cloud-register-form input[name="code"]').count() == 0)

    print('\n=== email 模式但站点邮件没配好 ===')
    boot(pg, 'email', mail_ready=False)
    if pg.locator('[data-act="cloud-login"]').count():
        pg.click('[data-act="cloud-login"]')
        pg.wait_for_timeout(500)
    pg.click('#cloud-login-form [data-act="cloud-register"]')
    pg.wait_for_timeout(600)
    rec('不发码就不让进注册弹窗', pg.locator('#cloud-register-form').count() == 0)

    print('\n=== closed 模式 ===')
    boot(pg, 'closed')
    if pg.locator('[data-act="cloud-login"]').count():
        pg.click('[data-act="cloud-login"]')
        pg.wait_for_timeout(500)
    rec('登录框显示注册已关闭', '注册已关闭' in pg.locator('.modal-card').inner_text())
    rec('没有注册按钮', pg.locator('[data-act="cloud-register"]').count() == 0)

    print('\n=== 管理员：三选项 ===')
    boot(pg, 'email')
    if pg.locator('[data-act="cloud-login"]').count():
        pg.click('[data-act="cloud-login"]')
        pg.wait_for_timeout(400)
        pg.fill('input[name="email"]', 'admin@sl00.top')
        pg.fill('input[name="password"]', 'x')
        pg.click('form.modal-card button[type="submit"]')
        pg.wait_for_timeout(1600)
    pg.evaluate("() => { const s=document.querySelector('[data-nav=\"settings\"]'); if(s) s.click(); }")
    pg.wait_for_timeout(900)
    pg.evaluate("() => { const b=document.querySelector('[data-act=\"admin-panel\"]'); if(b) b.click(); }")
    pg.wait_for_timeout(900)
    sel = pg.locator('select[name="registration_mode"]')
    if sel.count() == 0:
        rec('用户管理里有「注册方式」下拉', False, '未找到（可能入口不同）')
    else:
        opts = sel.locator('option').all_inner_texts()
        rec('三个选项齐全', len(opts) == 3, str(opts))
        rec('含「开放（邮箱验证）」', any('邮箱验证' in o for o in opts), str(opts))

    rec('无 JS / console 报错', not errs, str(errs[:2]))
    br.close()

srv.shutdown()
print('\n' + '=' * 46)
print('注册邮箱验证：%d 通过 / %d 失败' % (ok[0], ok[1]))
