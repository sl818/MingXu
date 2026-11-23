# -*- coding: utf-8 -*-
"""设置页截图（明暗），支持 --tag before|after --w 宽度。"""
import http.server, threading, json, socketserver, secrets, sys, os, datetime
from playwright.sync_api import sync_playwright

TAG = 'after'; W = 1440
for i, a in enumerate(sys.argv):
    if a == '--tag' and i + 1 < len(sys.argv): TAG = sys.argv[i + 1]
    if a == '--w' and i + 1 < len(sys.argv): W = int(sys.argv[i + 1])

DOC = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo'
OUT = os.path.join(DOC, 'design', 'shots')
USER = {'id': 1, 'email': 'test@example.com', 'display_name': '测试', 'is_admin': False}
sessions = {}

board = {'data': {'version': 2, 'view': 'settings', 'habits': [], 'checks': {}, 'notes': {}, 'moods': {},
    'events': [], 'meds': [], 'doses': {}, 'bodyProfile': {}, 'weights': [], 'essays': [], 'tasks': [],
    'notices': [], 'countdowns': [], 'cravings': [], 'packs': []}, 'rev': 1}

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
            else: self._j({'ok': False}, 200)
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
            else: self._j({'ok': False}, 200)
        else:
            self.send_response(405); self.end_headers()

class TS(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True

srv = TS(('127.0.0.1', 0), H)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()

with sync_playwright() as pw:
    br = pw.chromium.launch(channel='chrome', headless=True)
    for mode in ('light', 'dark'):
        ctx = br.new_context(viewport={'width': W, 'height': 1000})
        pg = ctx.new_page()
        pg.clock.install(time=datetime.datetime(2026, 11, 23, 10, 0, 0))
        pg.add_init_script(f"try{{localStorage.setItem('lifeboard.layout','wide');localStorage.setItem('lifeboard.skin','paper');localStorage.setItem('lifeboard.theme.mode','{mode}');}}catch(e){{}}")
        pg.goto(f'http://127.0.0.1:{port}/index.html', wait_until='networkidle'); pg.wait_for_timeout(500)
        pg.click('[data-act="cloud-login"]'); pg.wait_for_timeout(350)
        pg.fill('input[name="email"]', 'test@example.com'); pg.fill('input[name="password"]', 'test@example.com')
        pg.click('form.modal-card button[type="submit"]'); pg.wait_for_timeout(2200)
        pg.click('.nav-item[data-nav="settings"]'); pg.wait_for_timeout(1000)
        pg.screenshot(path=os.path.join(OUT, f'settings-{TAG}-{mode}.png'), full_page=True)
        ctx.close()
    br.close()
srv.shutdown()
print(f'设置页截图完成：{TAG}（{W} 宽，明暗）')
