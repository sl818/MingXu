# -*- coding: utf-8 -*-
"""看板任务卡新布局：深色桌面 + 移动端浅色 截图（复用 mock 服务器）。"""
import http.server, threading, json, socketserver, secrets
from datetime import datetime
from playwright.sync_api import sync_playwright

DOC = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo'
USER = {'id': 1, 'email': 'test@example.com', 'display_name': '测试', 'is_admin': False}
sessions = {}
D = '2026-10-24'
tasks = [
  {'id': 't1', 'title': '今天要做的事', 'note': '', 'tag': '工作', 'priority': '高', 'status': 'todo', 'due': '2026-10-24', 'createdAt': '2026-10-23T08:00:00Z'},
  {'id': 't2', 'title': '已逾期的事', 'note': '', 'tag': '生活', 'priority': '低', 'status': 'todo', 'due': '2026-10-20', 'createdAt': '2026-10-19T08:00:00Z'},
  {'id': 't3', 'title': '进行中的事', 'note': '推进中', 'tag': '健康', 'priority': '中', 'status': 'doing', 'due': '2026-10-25', 'createdAt': '2026-10-23T08:00:00Z'},
  {'id': 't4', 'title': '已完成的事', 'note': '', 'tag': '学习', 'priority': '中', 'status': 'done', 'due': '2026-10-23', 'doneAt': '2026-10-23', 'createdAt': '2026-10-22T08:00:00Z'},
  {'id': 't5', 'title': '已取消的事', 'note': '', 'tag': '其他', 'priority': '低', 'status': 'cancelled', 'due': '2026-10-20', 'createdAt': '2026-10-19T08:00:00Z'},
]
board = {'data': {'version': 2, 'view': 'today', 'habits': [], 'checks': {}, 'notes': {}, 'moods': {},
    'events': [], 'meds': [], 'doses': {}, 'bodyProfile': {}, 'weights': [], 'essays': [], 'tasks': tasks}, 'rev': 1}

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
            elif a == 'push_preview': self._j({'ok': True, 'date': '2026-10-25', 'items': []})
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

def login(pg, mobile=False):
    pg.goto(f'http://127.0.0.1:{port}/index.html', wait_until='networkidle'); pg.wait_for_timeout(500)
    pg.click('[data-act="cloud-login"]'); pg.wait_for_timeout(350)
    pg.fill('input[name="email"]', 'test@example.com'); pg.fill('input[name="password"]', 'test@example.com')
    pg.click('form.modal-card button[type="submit"]'); pg.wait_for_timeout(2200)
    sel = '.mobile-tab[data-nav="board"]' if mobile else '.nav-item[data-nav="board"]'
    pg.click(sel); pg.wait_for_timeout(1000)

with sync_playwright() as pw:
    br = pw.chromium.launch(channel='chrome', headless=True)

    # 深色桌面
    c1 = br.new_context(viewport={'width': 1440, 'height': 900})
    pg1 = c1.new_page()
    pg1.clock.install(time=datetime(2026, 10, 24, 10, 0, 0))
    pg1.add_init_script("try{localStorage.setItem('lifeboard.layout','wide');localStorage.setItem('lifeboard.skin','paper');localStorage.setItem('lifeboard.theme.mode','dark');}catch(e){}")
    login(pg1)
    pg1.screenshot(path='design/shots/task-board-v2-dark.png', full_page=False)
    c1.close()

    # 移动端浅色
    c2 = br.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True, device_scale_factor=2)
    pg2 = c2.new_page()
    pg2.clock.install(time=datetime(2026, 10, 24, 10, 0, 0))
    pg2.add_init_script("try{localStorage.setItem('lifeboard.layout','top');localStorage.setItem('lifeboard.skin','paper');localStorage.setItem('lifeboard.theme.mode','light');}catch(e){}")
    login(pg2, mobile=True)
    pg2.screenshot(path='design/shots/task-board-v2-mobile.png', full_page=False)
    c2.close()

    br.close()
print('截图完成：task-board-v2-dark.png / task-board-v2-mobile.png')
