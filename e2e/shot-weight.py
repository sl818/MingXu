# -*- coding: utf-8 -*-
"""体重页截图（明暗），支持 --tag before|after，用于前后对比。"""
import http.server, threading, json, socketserver, secrets, sys, os
from datetime import datetime
from playwright.sync_api import sync_playwright

TAG = 'after'; W = 1440; OLD = False
for i, a in enumerate(sys.argv):
    if a == '--tag' and i + 1 < len(sys.argv): TAG = sys.argv[i + 1]
    if a == '--w' and i + 1 < len(sys.argv): W = int(sys.argv[i + 1])
    if a == '--old': OLD = True

DOC = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo'
OUT = os.path.join(DOC, 'design', 'shots')
USER = {'id': 1, 'email': 'test@example.com', 'display_name': '测试', 'is_admin': False}
sessions = {}

weights = [
    {'id': 'w01', 'date': '2026-10-10', 'weight': 72.4, 'bmi': 23.6, 'age': 30, 'height': 175, 'fat': 19.6},
    {'id': 'w02', 'date': '2026-10-14', 'weight': 72.1, 'bmi': 23.5, 'age': 30, 'height': 175, 'fat': 19.4},
    {'id': 'w03', 'date': '2026-10-18', 'weight': 72.0, 'bmi': 23.5, 'age': 30, 'height': 175, 'fat': 0},
    {'id': 'w04', 'date': '2026-10-22', 'weight': 71.6, 'bmi': 23.4, 'age': 30, 'height': 175, 'fat': 19.1},
    {'id': 'w05', 'date': '2026-10-26', 'weight': 71.2, 'bmi': 23.2, 'age': 30, 'height': 175, 'fat': 0},
    {'id': 'w06', 'date': '2026-10-30', 'weight': 70.8, 'bmi': 23.1, 'age': 30, 'height': 175, 'fat': 18.9},
    {'id': 'w07', 'date': '2026-11-03', 'weight': 70.5, 'bmi': 23.0, 'age': 30, 'height': 175, 'fat': 18.7},
    {'id': 'w08', 'date': '2026-11-07', 'weight': 70.1, 'bmi': 22.9, 'age': 30, 'height': 175, 'fat': 0},
    {'id': 'w09', 'date': '2026-11-11', 'weight': 69.8, 'bmi': 22.8, 'age': 30, 'height': 175, 'fat': 18.6},
    {'id': 'w10', 'date': '2026-11-15', 'weight': 69.4, 'bmi': 22.7, 'age': 30, 'height': 175, 'fat': 0},
    {'id': 'w11', 'date': '2026-11-19', 'weight': 69.1, 'bmi': 22.6, 'age': 30, 'height': 175, 'fat': 18.5},
    {'id': 'w12', 'date': '2026-11-22', 'weight': 68.9, 'bmi': 22.5, 'age': 30, 'height': 175, 'fat': 18.4},
]
board = {'data': {'version': 2, 'view': 'today', 'habits': [], 'checks': {}, 'notes': {}, 'moods': {},
    'events': [], 'meds': [], 'doses': {}, 'bodyProfile': {'age': 30, 'height': 175, 'goalWeight': 68},
    'weights': weights, 'essays': [], 'tasks': []}, 'rev': 1}

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

with sync_playwright() as pw:
    br = pw.chromium.launch(channel='chrome', headless=True)
    for mode in ('light', 'dark'):
        ctx = br.new_context(viewport={'width': W, 'height': 1000})
        pg = ctx.new_page()
        pg.clock.install(time=datetime(2026, 11, 22, 10, 0, 0))
        pg.add_init_script(f"try{{localStorage.setItem('lifeboard.layout','wide');localStorage.setItem('lifeboard.skin','paper');localStorage.setItem('lifeboard.theme.mode','{mode}');}}catch(e){{}}")
        pg.goto(f'http://127.0.0.1:{port}/index.html', wait_until='networkidle'); pg.wait_for_timeout(500)
        pg.click('[data-act="cloud-login"]'); pg.wait_for_timeout(350)
        pg.fill('input[name="email"]', 'test@example.com'); pg.fill('input[name="password"]', 'test@example.com')
        pg.click('form.modal-card button[type="submit"]'); pg.wait_for_timeout(2200)
        pg.click('.nav-item[data-nav="weight"]'); pg.wait_for_timeout(1000)
        if OLD:
            # 模拟 v158 旧布局：右栏固定 262px + 图 max-height 400（宽屏会两侧留白）
            pg.add_style_tag(content=".ww-svg{max-height:400px !important;width:100% !important;height:auto !important;}"
                                     ".weight-charts{grid-template-columns:minmax(0,1fr) 262px !important;}")
            pg.wait_for_timeout(250)
        pg.screenshot(path=os.path.join(OUT, f'weight-{TAG}-{mode}.png'), full_page=True)
        ctx.close()
    br.close()
srv.shutdown()
print(f'体重页截图完成：{TAG}（light/dark）')
