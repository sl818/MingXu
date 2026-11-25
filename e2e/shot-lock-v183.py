# -*- coding: utf-8 -*-
"""v183 截图：编辑运动时类型锁定。"""
import http.server
import json
import secrets
import socketserver
import threading
from datetime import datetime

from playwright.sync_api import sync_playwright

DOC = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo'
OUT = 'C:/Users/slgzs/.workbuddy/previews/'
USER = {'id': 1, 'email': 'test@example.com', 'display_name': '测试', 'is_admin': False}
D = '2026-10-24'

board = {'data': {
    'version': 2, 'schemaVersion': 2, 'view': 'today',
    'habits': [],
    'modules': {'move': {
        'on': True, 'name': '运动', 'icon': '🏃', 'color': '#b5733f', 'note': '',
        'unit': '次', 'times': 1, 'sports': [], 'records': [],
        'notifyChannels': ['browser'], 'notify': True,
        'notifyScenes': {'steps': True, 'plan': True, 'week': True},
        'suggestTime': '', 'notifyFreq': 'daily', 'notifyWeekday': 1, 'notifyMonthday': 1,
        'notifyNote': '', 'createdAt': '2026-09-01T08:00:00Z', 'updatedAt': '2026-10-01T08:00:00Z',
    }},
    'modulesAt': 0,
    'checks': {}, 'skips': {}, 'notes': {}, 'moods': {}, 'events': [],
    'meds': [], 'doses': {}, 'bodyProfile': {'age': 30, 'height': 170},
    'weights': [], 'essays': [], 'tasks': [], 'money': {}, 'quit': {},
}, 'rev': 3}
sessions = {}


class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=DOC, **kw)

    def log_message(self, *a):
        pass

    def _j(self, obj, status=200, eh=None):
        b = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(b)))
        self.send_header('Cache-Control', 'no-store')
        for k, v in (eh or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(b)

    def _sid(self):
        for p in (self.headers.get('Cookie', '') or '').split(';'):
            p = p.strip()
            if p.startswith('sid='):
                return p[4:]
            return ''

    def do_GET(self):
        if self.path.startswith('/api.php'):
            a = self.path.split('action=')[-1].split('&')[0]
            if a == 'status':
                self._j({'ok': True, 'installed': True})
            elif a == 'me':
                self._j({'ok': True, 'user': sessions.get(self._sid()), 'csrf': 'x',
                         'registration_open': False, 'registration_mode': 'closed',
                         'need_invite': False, 'need_code': False, 'code_ready': False})
            elif a == 'push_status':
                self._j({'ok': True, 'enabled': False, 'webhook': '', 'sent_today': 0,
                         'last_sent': '', 'recent': []})
            elif a == 'push_preview':
                self._j({'ok': True, 'date': D, 'items': []})
            elif a == 'mail_status':
                self._j({'ok': True, 'crypto_ready': True, 'recipient': 'test@example.com',
                         'config': {'host': '', 'port': 465, 'secure': 'ssl', 'user': '', 'from': '',
                                    'name': '', 'hasSecret': False, 'enabled': False,
                                    'lastError': '', 'lastTestAt': ''}})
            elif a == 'ics_status':
                self._j({'ok': True, 'url': None})
            elif a == 'load':
                self._j({'ok': True, 'data': board['data'], 'rev': board['rev'],
                         'updated_at': 1792813000000})
            else:
                self._j({'ok': False, 'error': '?'}, 404)
        else:
            super().do_GET()

    def do_POST(self):
        if self.path.startswith('/api.php'):
            a = self.path.split('action=')[-1].split('&')[0]
            n = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(n) or b'{}')
            if a == 'login':
                sid = secrets.token_hex(8)
                sessions[sid] = USER
                self._j({'ok': True, 'user': USER, 'csrf': 'x', 'registration_open': False},
                        eh={'Set-Cookie': 'sid=' + sid + '; Path=/'})
            elif a in ('save', 'force'):
                board['data'] = body['data']
                board['rev'] += 1
                self._j({'ok': True, 'rev': board['rev'], 'updated_at': 1792813000000})
            else:
                self._j({'ok': False, 'error': '?'}, 404)
        else:
            self.send_response(405)
            self.end_headers()


class TS(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


srv = TS(('127.0.0.1', 0), H)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()

with sync_playwright() as pw:
    br = pw.chromium.launch(channel='chrome')
    ctx = br.new_context(viewport={'width': 1180, 'height': 1000})
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.clock.install(time=datetime(2026, 10, 24, 20, 0, 0))
    pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
    pg.wait_for_timeout(600)
    pg.click('[data-act="cloud-login"]')
    pg.wait_for_timeout(400)
    pg.fill('input[name="email"]', 'test@example.com')
    pg.fill('input[name="password"]', 'test@example.com')
    pg.click('form.modal-card button[type="submit"]')
    pg.wait_for_timeout(2800)
    pg.evaluate("() => { const b=document.querySelector('[data-nav=\"move\"]'); if(b) b.click(); }")
    pg.wait_for_timeout(700)
    # 建一个跳绳
    pg.click('[data-act="move-new"]')
    pg.wait_for_timeout(450)
    pg.click('.sp-grid .sp-opt[data-k="rope"]')
    pg.wait_for_timeout(250)
    pg.click('#move-sport-form button[type="submit"]')
    pg.wait_for_timeout(1500)
    # 编辑
    pg.locator('.mv-card [data-act="move-edit"]').first.click()
    pg.wait_for_timeout(800)
    pg.screenshot(path=OUT + 'v183-lock-modal.png')
    print('锁定提示:', pg.inner_text('#move-sport-form .sp-locked'))
    print('灰掉的:', pg.eval_on_selector_all('#move-sport-form .sp-opt.dis', 'e=>e.map(x=>x.dataset.k)'))
    # 点一个灰掉的类型 → toast
    pg.click('#move-sport-form .sp-opt[data-k="run"]')
    pg.wait_for_timeout(500)
    pg.screenshot(path=OUT + 'v183-lock-toast.png')
    print('点跑步后高亮:', pg.eval_on_selector_all('#move-sport-form .sp-opt.on', 'e=>e.map(x=>x.dataset.k)'))
    print('JS 错误:', errs[:3])
    br.close()
print('ok')
