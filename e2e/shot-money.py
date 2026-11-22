# -*- coding: utf-8 -*-
"""清债三页 v2 改版截图：总览 / 债务 / 计划 × 明暗（mock 数据）。"""
import http.server, threading, json, socketserver, secrets
from datetime import datetime
from playwright.sync_api import sync_playwright

DOC = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo'
USER = {'id': 1, 'email': 'test@example.com', 'display_name': '测试', 'is_admin': False}
sessions = {}

money = {
    'v': 1,
    'debts': [
        {'id': 'd1', 'name': '招商信用卡', 'type': 'card', 'balance': 32000, 'start': 48000,
         'apr': 18.25, 'min': 3200, 'due': 8, 'note': '分期还剩 6 期'},
        {'id': 'd2', 'name': '某网贷', 'type': 'loan', 'balance': 15000, 'start': 20000,
         'apr': 23.9, 'min': 1500, 'due': 15, 'note': ''},
        {'id': 'd3', 'name': '小姨借款', 'type': 'friend', 'balance': 8000, 'start': 10000,
         'apr': 0, 'min': 500, 'due': 0, 'note': '不着急，慢慢还'},
        {'id': 'd4', 'name': '已还清的旧账', 'type': 'other', 'balance': 0, 'start': 5000,
         'apr': 0, 'min': 0, 'due': 0, 'note': ''},
    ],
    'extra': 500, 'strategy': 'snowball', 'customOrder': [],
    'snowflakes': [{'id': 's1', 'ym': '2026-12', 'amount': 5000, 'note': '年终奖'}],
    'startYM': '', 'log': [], 'incomes': [], 'cats': [], 'spends': [],
    'notify': {'on': False, 'before': [3, 1, 0], 'time': '09:00'},
}
board = {'data': {'version': 2, 'view': 'today', 'habits': [], 'checks': {}, 'notes': {}, 'moods': {},
    'events': [], 'meds': [], 'doses': {}, 'bodyProfile': {}, 'weights': [], 'essays': [],
    'tasks': [], 'money': money}, 'rev': 1}

class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw): super().__init__(*a, directory=DOC, **kw)
    def log_message(self, *a): pass
    def _j(self, o, s=200, eh=None):
        b = json.dumps(o, ensure_ascii=False).encode()
        self.send_response(s); self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(b)))
        for k, v in (eh or {}).items(): self.send_header(k, v)
        self.end_headers(); self.wfile.write(b)
    def _sid(self):
        for p in (self.headers.get('Cookie', '') or '').split(';'):
            p = p.strip()
            if p.startswith('sid='): return p[4:]
    def do_GET(self):
        if self.path.startswith('/api.php'):
            a = self.path.split('action=')[-1].split('&')[0]
            if a == 'status': self._j({'ok': True, 'installed': True, 'registration_open': False})
            elif a == 'me': self._j({'ok': True, 'user': sessions.get(self._sid()), 'csrf': 'x', 'registration_open': False})
            elif a == 'push_status': self._j({'ok': True, 'enabled': False, 'webhook': '', 'sent_today': 0, 'last_sent': '', 'recent': []})
            elif a == 'push_preview': self._j({'ok': True, 'date': '2026-11-23', 'items': []})
            elif a == 'ics_status': self._j({'ok': True, 'url': None})
            elif a == 'load': self._j({'ok': True, 'data': board['data'], 'rev': board['rev'], 'updated_at': 1792813000000})
            else: self._j({'ok': False, 'error': '?'}, 404)
        else: super().do_GET()
    def do_POST(self):
        if self.path.startswith('/api.php'):
            a = self.path.split('action=')[-1].split('&')[0]
            n = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(n) or b'{}')
            if a == 'login':
                sid = secrets.token_hex(8); sessions[sid] = USER
                self._j({'ok': True, 'user': USER, 'csrf': 'x'}, eh={'Set-Cookie': 'sid=' + sid + '; Path=/'})
            elif a in ('save', 'force'):
                board['data'] = body['data']; board['rev'] += 1
                self._j({'ok': True, 'rev': board['rev'], 'updated_at': 1792813000000})
            else: self._j({'ok': False, 'error': '?'}, 404)
        else:
            self.send_response(405); self.end_headers()

class TS(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True

srv = TS(('127.0.0.1', 0), H)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()

def dump(pg, mode):
    for tab in ('overview', 'debts', 'plan'):
        pg.click(f'button[data-act="subtab"][data-page="money"][data-tab="{tab}"]'); pg.wait_for_timeout(700)
        pg.screenshot(path=f'design/shots/money-{tab}-{mode}.png', full_page=False)

with sync_playwright() as pw:
    br = pw.chromium.launch(channel='chrome', headless=True)
    for mode in ('light', 'dark'):
        ctx = br.new_context(viewport={'width': 1440, 'height': 980})
        pg = ctx.new_page()
        pg.clock.install(time=datetime(2026, 11, 22, 10, 0, 0))
        pg.add_init_script(f"try{{localStorage.setItem('lifeboard.layout','wide');localStorage.setItem('lifeboard.skin','paper');localStorage.setItem('lifeboard.theme.mode','{mode}');}}catch(e){{}}")
        pg.goto(f'http://127.0.0.1:{port}/index.html', wait_until='networkidle'); pg.wait_for_timeout(500)
        pg.click('[data-act="cloud-login"]'); pg.wait_for_timeout(350)
        pg.fill('input[name="email"]', 'test@example.com'); pg.fill('input[name="password"]', 'test@example.com')
        pg.click('form.modal-card button[type="submit"]'); pg.wait_for_timeout(2200)
        pg.click('.nav-item[data-nav="money"]'); pg.wait_for_timeout(1000)
        dump(pg, mode)
        ctx.close()
    br.close()
srv.shutdown()
print('清债截图完成：总览/债务/计划 × 明暗')
