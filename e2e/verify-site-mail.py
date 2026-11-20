# -*- coding: utf-8 -*-
"""v125 站点邮件与找回密码：登录页申请重置、邮件链接落地改密、管理员面板。"""
import http.server, threading, json, socketserver, secrets
from playwright.sync_api import sync_playwright

DOC = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo'
USER = {'id': 6, 'email': 'sl@sl00.top', 'display_name': '晚风', 'is_admin': True,
        'status': 'active', 'created_at': '2026-10-01 00:00:00', 'last_login_at': None}
sessions = {}
CALLS = []
TOKEN = 'a' * 64
SITE_MAIL = {'host': 'smtp.qq.com', 'port': 465, 'secure': 'ssl',
             'user': 'mingxu-todo@foxmail.com', 'from': 'mingxu-todo@foxmail.com',
             'name': '明序', 'hasSecret': True}
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
                self._j({'ok': True, 'user': USER if u else None, 'csrf': 'x',
                         'registration_open': False, 'site_name': '明序'})
            elif a == 'status':
                self._j({'ok': True, 'installed': True})
            elif a == 'load':
                self._j({'ok': True, 'data': BOARD['data'], 'rev': 1, 'updated_at': 1792813000000, 'history': []})
            elif a == 'site_mail_status':
                self._j({'ok': True, 'config': SITE_MAIL, 'ready': True, 'admin_email': USER['email']})
            elif a == 'notify_prefs':
                self._j({'ok': True, 'kinds': {}, 'channels': {}, 'prefs': {}, 'quiet': False, 'report': {}})
            elif a in ('push_status', 'ics_status'):
                self._j({'ok': True, 'enabled': False, 'webhook_set': False, 'token': 'x', 'url': 'x'})
            elif a == 'mail_status':
                self._j({'ok': True, 'config': {'hasSecret': False, 'enabled': False}, 'crypto_ready': True, 'recipient': 'a@b.com'})
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
        elif a == 'password_forgot':
            self._j({'ok': True, 'sent': True})
        elif a == 'password_reset':
            if body.get('token') != TOKEN:
                self._j({'ok': False, 'error': '这个链接已失效或已用过，请重新申请'}, 400)
                return
            self._j({'ok': True})
        elif a == 'site_mail_save':
            self._j({'ok': True, 'config': SITE_MAIL, 'ready': True})
        elif a == 'site_mail_test':
            self._j({'ok': True, 'to': USER['email']})
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
        print('PASS ', name, ' |', note)
    else:
        ok[1] += 1
        print('FAIL ', name, ' |', note)


with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)
    ctx = br.new_context(viewport={'width': 1360, 'height': 900})
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)[:120]))
    pg.add_init_script("try{localStorage.setItem('lifeboard.theme.mode','light');"
                       "localStorage.setItem('lifeboard.skin','paper')}catch(e){}")
    pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
    pg.wait_for_timeout(900)

    print('=== 未登录：找回密码入口 ===')
    if pg.locator('[data-act="cloud-login"]').count():
        pg.click('[data-act="cloud-login"]')
        pg.wait_for_timeout(500)
    rec('登录框里有「找回密码」', pg.locator('[data-act="forgot-password"]').count() == 1)
    pg.click('[data-act="forgot-password"]')
    pg.wait_for_timeout(400)
    rec('弹出的是表单不是纯文字', pg.locator('#forgot-form').count() == 1)
    rec('有邮箱输入框', pg.locator('#forgot-form input[name="email"]').count() == 1)
    rec('说明写了 30 分钟有效', '30 分钟' in pg.locator('#forgot-form').inner_text(),
        pg.locator('#forgot-form').inner_text()[:50])

    pg.fill('#forgot-form input[name="email"]', 'someone@example.com')
    pg.click('#forgot-form button[type="submit"]')
    pg.wait_for_timeout(800)
    sent = [b for a, b in CALLS if a == 'password_forgot']
    rec('调了 password_forgot', len(sent) == 1, str(sent))
    rec('提交的邮箱正确', sent and sent[0].get('email') == 'someone@example.com', str(sent))
    rec('提示「请查收邮件」', '请查收' in pg.locator('.modal-card h3').inner_text(),
        pg.locator('.modal-card h3').inner_text())
    rec('提示不泄露账号是否存在', '如果这个邮箱注册过' in pg.locator('.modal-card').inner_text())

    print('\n=== 邮件链接落地：设置新密码 ===')
    pg.goto('http://127.0.0.1:%d/index.html?reset=1&token=%s' % (port, TOKEN), wait_until='networkidle')
    pg.wait_for_timeout(1400)
    rec('自动弹出设置新密码', pg.locator('#reset-form').count() == 1)
    rec('表单带上了 token', pg.locator('#reset-form').get_attribute('data-token') == TOKEN)

    pg.fill('#reset-form input[name="password"]', '12345678')
    pg.fill('#reset-form input[name="password_confirm"]', '87654321')
    pg.click('#reset-form button[type="submit"]')
    pg.wait_for_timeout(400)
    rec('两次不一致被拦下', '不一致' in pg.locator('#reset-form .cloud-error').inner_text(),
        pg.locator('#reset-form .cloud-error').inner_text())
    rec('不一致时不发请求', len([1 for a, _ in CALLS if a == 'password_reset']) == 0)

    pg.fill('#reset-form input[name="password"]', '123')
    pg.fill('#reset-form input[name="password_confirm"]', '123')
    before_reset = len([1 for a, _ in CALLS if a == 'password_reset'])
    pg.click('#reset-form button[type="submit"]')
    pg.wait_for_timeout(400)
    # minlength 由浏览器原生校验先拦（更早于 JS），所以看的是「有没有发请求」
    rec('少于 8 位没有发出重置请求',
        len([1 for a, _ in CALLS if a == 'password_reset']) == before_reset, '')

    pg.fill('#reset-form input[name="password"]', 'newpass123')
    pg.fill('#reset-form input[name="password_confirm"]', 'newpass123')
    pg.click('#reset-form button[type="submit"]')
    pg.wait_for_timeout(1100)
    reset_calls = [b for a, b in CALLS if a == 'password_reset']
    rec('发起了重置请求', len(reset_calls) == 1, str(len(reset_calls)))
    rec('请求带 token 与新密码',
        reset_calls and reset_calls[0].get('token') == TOKEN and reset_calls[0].get('password') == 'newpass123',
        str(reset_calls[0]) if reset_calls else '')
    rec('成功后打开登录框', pg.locator('#cloud-login-form').count() == 1)
    rec('地址栏的 token 被抹掉', 'token=' not in pg.url, pg.url)

    print('\n=== 管理员：站点邮件面板 ===')
    pg.fill('input[name="email"]', 'sl@sl00.top')
    pg.fill('input[name="password"]', 'x')
    pg.click('form.modal-card button[type="submit"]')
    pg.wait_for_timeout(1500)
    pg.evaluate("() => { const b=document.querySelector('[data-nav=\\\"config\\\"]'); if(b) b.click(); }")
    pg.wait_for_timeout(900)
    panel = pg.locator('.panel').filter(has_text='站点邮件')
    rec('管理员能看到「站点邮件」面板', panel.count() >= 1, str(panel.count()))
    txt = panel.first.inner_text()
    rec('写明只做两件事', '只用两件事' in txt, txt[:60])
    rec('写明提醒不走这个邮箱', '提醒通知不会走它' in txt, txt[:60])
    rec('状态显示已就绪', '已就绪' in txt, txt[:80])
    rec('有发件人输入框', pg.locator('#sm-from').count() == 1)
    rec('授权码框为空且提示已保存', pg.input_value('#sm-secret') == '' and
        '已保存' in pg.locator('#sm-secret').get_attribute('placeholder'), '')

    pg.click('[data-act="site-mail-test"]')
    pg.wait_for_timeout(700)
    rec('测试发送有结果提示', pg.locator('#sm-result').count() == 1 and
        not pg.locator('#sm-result').is_hidden(), '')

    rec('无 JS / console 报错', not errs, str(errs[:2]))
    br.close()

srv.shutdown()
print('\n' + '=' * 46)
print('站点邮件与找回密码：%d 通过 / %d 失败' % (ok[0], ok[1]))
