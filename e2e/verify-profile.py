# -*- coding: utf-8 -*-
"""v118 账号资料：三区左下角入口 + 设置页「资料」入口 + 名称/邮箱可改 + 改密校验。"""
import http.server, threading, json, socketserver, secrets, sys
from playwright.sync_api import sync_playwright

DOC = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo'
USER = {'id': 1, 'email': 'test@example.com', 'display_name': '测试用户', 'is_admin': True,
        'status': 'active', 'created_at': '2026-09-01 08:00:00', 'last_login_at': '2026-10-25 10:00:00'}
sessions = {}
CALLS = []          # 记录 profile_save / change_password 的入参
STATE = {'user': dict(USER)}

BOARD = {'data': {'version': 2, 'habits': [], 'tasks': [], 'checks': {}, 'essays': [], 'weights': [],
                  'meds': [], 'medLogs': {}, 'money': {}, 'settings': {}, 'essayTags': [], 'quit': {}},
         'rev': 1}


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
        c = self.headers.get('Cookie') or ''
        for part in c.split(';'):
            if part.strip().startswith('sid='):
                return sessions.get(part.strip()[4:])
        return None

    def do_GET(self):
        if self.path.startswith('/index.html') or self.path == '/':
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
                ctype = 'text/css' if p.endswith('.css') else 'application/javascript'
                self.send_response(200)
                self.send_header('Content-Type', ctype)
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
                self._j({'ok': True, 'user': STATE['user'] if u else None, 'csrf': 'x',
                         'registration_open': False, 'site_name': '明序'})
            elif a == 'status':
                self._j({'ok': True, 'installed': True})
            elif a == 'load':
                self._j({'ok': True, 'data': BOARD['data'], 'rev': BOARD['rev'], 'updated_at': 1792813000000, 'history': []})
            elif a == 'push_status':
                self._j({'ok': True, 'enabled': False, 'webhook_set': False})
            elif a == 'ics_status':
                self._j({'ok': True, 'token': 'x', 'url': 'https://x/x.ics'})
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
            sessions[sid] = STATE['user']
            self._j({'ok': True, 'user': STATE['user'], 'csrf': 'x'},
                    eh={'Set-Cookie': 'sid=' + sid + '; Path=/'})
        elif a == 'profile_save':
            em = (body.get('email') or '').strip().lower()
            if em == 'taken@example.com':
                self._j({'ok': False, 'error': '这个邮箱已被其他账号使用'}, 409)
                return
            STATE['user'] = dict(STATE['user'], email=em, display_name=(body.get('display_name') or '').strip())
            self._j({'ok': True, 'user': STATE['user']})
        elif a == 'change_password':
            if body.get('current_password') != 'right-pass':
                self._j({'ok': False, 'error': '当前密码不正确'}, 400)
                return
            self._j({'ok': True})
        elif a in ('save', 'force'):
            BOARD['data'] = body['data']
            BOARD['rev'] += 1
            self._j({'ok': True, 'rev': BOARD['rev'], 'updated_at': 1792813000000})
        else:
            self._j({'ok': False, 'error': '?'}, 404)


class TS(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


srv = TS(('127.0.0.1', 0), H)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()

ok = [0, 0]


def chk(name, cond, extra=''):
    if cond:
        ok[0] += 1
        print('  ✓', name)
    else:
        ok[1] += 1
        print('  ✗', name, extra)


with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)
    ctx = br.new_context(viewport={'width': 1440, 'height': 900})
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)[:100]))
    pg.add_init_script("try{localStorage.setItem('lifeboard.layout','wide');"
                       "localStorage.setItem('lifeboard.theme.mode','light');"
                       "localStorage.setItem('lifeboard.skin','paper')}catch(e){}")
    pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
    pg.wait_for_timeout(600)
    if pg.locator('[data-act="cloud-login"]').count():
        pg.click('[data-act="cloud-login"]')
        pg.wait_for_timeout(400)
        pg.fill('input[name="email"]', 'test@example.com')
        pg.fill('input[name="password"]', 'test@example.com')
        pg.click('form.modal-card button[type="submit"]')
        pg.wait_for_timeout(1600)

    print('\n=== 入口 ===')
    chk('三区左下角卡片存在', pg.locator('.su-card').count() == 1)
    chk('卡片绑定了资料入口', pg.locator('.su-card[data-act="cloud-account"]').count() == 1)

    pg.click('[data-nav="settings"]')
    pg.wait_for_timeout(700)
    btns = pg.locator('.btn-row button').all_inner_texts()
    chk('设置页出现「资料」按钮', '资料' in btns, str(btns))
    chk('「资料」在「退出登录」之后', btns.index('资料') > btns.index('退出登录'), str(btns))

    print('\n=== 弹窗预填 ===')
    pg.click('.su-card[data-act="cloud-account"]')
    pg.wait_for_timeout(500)
    chk('弹窗标题是「账号资料」', '账号资料' in pg.locator('#cloud-account-form h3').inner_text())
    chk('名称预填', pg.input_value('#cloud-account-form [name="display_name"]') == '测试用户')
    chk('邮箱预填', pg.input_value('#cloud-account-form [name="email"]') == 'test@example.com')
    chk('有「保存资料」按钮', pg.locator('[data-act="profile-save"]').count() == 1)
    chk('有「保存新密码」按钮', pg.locator('[data-act="cloud-change-password"]').count() == 1)
    pg.screenshot(path=DOC + '/design/profile-modal.png', clip={'x': 380, 'y': 20, 'width': 700, 'height': 820})

    print('\n=== 保存资料 ===')
    pg.fill('#cloud-account-form [name="display_name"]', '晚风')
    pg.fill('#cloud-account-form [name="email"]', 'new@example.com')
    pg.click('[data-act="profile-save"]')
    pg.wait_for_timeout(800)
    sent = [b for a, b in CALLS if a == 'profile_save']
    chk('确实调了 profile_save', len(sent) == 1, str(sent))
    chk('提交的名称正确', sent and sent[0].get('display_name') == '晚风', str(sent))
    chk('提交的邮箱正确', sent and sent[0].get('email') == 'new@example.com', str(sent))
    chk('保存后弹窗关闭', pg.locator('#cloud-account-form').count() == 0)
    user = pg.evaluate('() => window.__cloudUser || null') if False else None
    chk('左下角邮箱已更新', 'new@example.com' in pg.locator('.su-card').inner_text(), pg.locator('.su-card').inner_text())

    print('\n=== 校验 ===')
    pg.click('.su-card[data-act="cloud-account"]')
    pg.wait_for_timeout(400)
    pg.fill('#cloud-account-form [name="email"]', 'bad-email')
    pg.click('[data-act="profile-save"]')
    pg.wait_for_timeout(400)
    chk('邮箱格式错误被前端拦下', '格式' in pg.locator('.profile-error').inner_text())
    chk('格式错误不发请求', len([1 for a, _ in CALLS if a == 'profile_save']) == 1)

    pg.fill('#cloud-account-form [name="email"]', 'taken@example.com')
    pg.click('[data-act="profile-save"]')
    pg.wait_for_timeout(600)
    chk('邮箱重复显示后端错误', '已被其他账号' in pg.locator('.profile-error').inner_text(),
        pg.locator('.profile-error').inner_text())

    print('\n=== 改密 ===')
    pg.fill('#cloud-account-form [name="current_password"]', 'wrong')
    pg.fill('#cloud-account-form [name="new_password"]', 'abcdefgh')
    pg.fill('#cloud-account-form [name="new_password_confirm"]', 'abcdefgh')
    pg.click('[data-act="cloud-change-password"]')
    pg.wait_for_timeout(600)
    chk('旧密码错显示提示', '不正确' in pg.locator('.cloud-error').inner_text(),
        pg.locator('.cloud-error').inner_text())

    pg.fill('#cloud-account-form [name="current_password"]', 'right-pass')
    pg.fill('#cloud-account-form [name="new_password"]', 'abcdefgh')
    pg.fill('#cloud-account-form [name="new_password_confirm"]', 'zzzzzzzz')
    pg.click('[data-act="cloud-change-password"]')
    pg.wait_for_timeout(500)
    chk('两次新密码不一致被拦下', '不一致' in pg.locator('.cloud-error').inner_text(),
        pg.locator('.cloud-error').inner_text())

    chk('全程无 JS 异常', not errs, str(errs[:2]))
    br.close()

srv.shutdown()
print('\n' + '=' * 46)
print('账号资料 v118：%d 通过 / %d 失败' % (ok[0], ok[1]))
