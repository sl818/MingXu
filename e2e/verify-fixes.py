# -*- coding: utf-8 -*-
"""验证三项改动：Hero 迷你周概览、日历三卡等高、页脚贴底。"""
import http.server, threading, json, socketserver, secrets
from playwright.sync_api import sync_playwright

DOC = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo'
USER = {'id': 1, 'email': 't@t.top', 'display_name': 'T', 'is_admin': False}
sessions = {}
HABITS = [
    {'id': 'h_med', 'name': '用药', 'icon': '💊', 'type': 'build', 'target': 1, 'unit': '次', 'color': '#2f6f5e', 'note': '', 'createdAt': '2026-10-23T00:00:00Z', 'pinned': True, 'med': True, 'archivedAt': ''},
    {'id': 'h_water', 'name': '喝水', 'icon': '💧', 'type': 'build', 'target': 8, 'unit': '杯', 'color': '#4c7f96', 'note': '', 'createdAt': '2026-10-23T00:00:00Z', 'pinned': True, 'archivedAt': ''},
    {'id': 'h_move', 'name': '运动', 'icon': '🏃', 'type': 'build', 'target': 1, 'unit': '次', 'color': '#b5733f', 'note': '', 'createdAt': '2026-10-23T00:00:00Z', 'pinned': True, 'archivedAt': ''},
    {'id': 'h_breathe', 'name': '478呼吸法', 'icon': '🌬️', 'type': 'build', 'target': 1, 'unit': '次', 'color': '#5b8f8a', 'note': '', 'createdAt': '2026-10-23T00:00:00Z', 'pinned': True, 'optional': True, 'archivedAt': ''},
    {'id': 'h_quit', 'name': '戒烟', 'icon': '🚭', 'type': 'quit', 'target': 1, 'unit': '次', 'color': '#9c5a5a', 'note': '', 'createdAt': '2026-10-23T00:00:00Z', 'pinned': False, 'archivedAt': ''},
]
board = {'data': {'version': 2, 'view': 'today', 'habits': HABITS,
    'checks': {'2026-10-19': {'h_water': 8, 'h_move': 1, 'h_med': 1}, '2026-10-20': {'h_water': 5, 'h_move': 1}, '2026-10-21': {'h_water': 8, 'h_move': 1, 'h_breathe': 1}, '2026-10-22': {'h_water': 8, 'h_move': 1}, '2026-10-23': {'h_water': 6, 'h_breathe': 1}, '2026-10-24': {'h_water': 3}},
    'notes': {}, 'moods': {'2026-10-23': 'happy'}, 'events': [], 'meds': [], 'doses': {},
    'bodyProfile': {'age': 30, 'height': 170}, 'weights': [], 'essays': [], 'tasks': [
    {'id': 't1', 'title': '收被单被子', 'note': '', 'tag': '生活', 'priority': '中', 'status': 'todo', 'due': '2026-10-24', 'createdAt': '2026-10-23T08:00:00Z'},
    {'id': 't2', 'title': '做20个俯卧撑', 'note': '', 'tag': '健康', 'priority': '高', 'status': 'todo', 'due': '2026-10-24', 'createdAt': '2026-10-23T08:00:00Z'},
    {'id': 't3', 'title': '阅读30分钟', 'note': '', 'tag': '学习', 'priority': '中', 'status': 'doing', 'due': '2026-10-24', 'createdAt': '2026-10-23T08:00:00Z'}]}, 'rev': 5}


class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=DOC, **kw)

    def log_message(self, *a):
        pass

    def _j(self, o, s=200, eh=None):
        b = json.dumps(o, ensure_ascii=False).encode()
        self.send_response(s)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(b)))
        for k, v in (eh or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(b)

    def _sid(self):
        for p in (self.headers.get('Cookie', '') or '').split(';'):
            p = p.strip()
            if p.startswith('sid='):
                return p[4:]

    def do_GET(self):
        if self.path.startswith('/api.php'):
            a = self.path.split('action=')[-1].split('&')[0]
            if a == 'status':
                self._j({'ok': True, 'installed': True, 'registration_open': False})
            elif a == 'me':
                self._j({'ok': True, 'user': sessions.get(self._sid()), 'csrf': 'x', 'registration_open': False})
            elif a == 'load':
                self._j({'ok': True, 'data': board['data'], 'rev': board['rev'], 'updated_at': 0})
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
                self._j({'ok': True, 'user': USER, 'csrf': 'x'}, eh={'Set-Cookie': 'sid=' + sid + '; Path=/'})
            elif a == 'save':
                if int(body.get('base_rev', 0)) == board['rev']:
                    board['data'] = body['data']; board['rev'] += 1
                    self._j({'ok': True, 'rev': board['rev']})
                else:
                    self._j({'ok': False, 'code': 'conflict', 'remote': {'data': board['data'], 'rev': board['rev']}}, 409)
            elif a == 'force':
                board['data'] = body['data']; board['rev'] += 1
                self._j({'ok': True, 'rev': board['rev']})
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

with sync_playwright() as p:
    b = p.chromium.launch(channel='chrome', headless=True)
    pg = b.new_page(viewport={'width': 1440, 'height': 1000})
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto(f'http://127.0.0.1:{port}/index.html', wait_until='networkidle')
    pg.wait_for_timeout(800)
    pg.click('[data-act="cloud-login"]'); pg.wait_for_timeout(500)
    pg.fill('input[name="email"]', 't@t.top'); pg.fill('input[name="password"]', '12345678')
    pg.click('form.modal-card button[type="submit"]'); pg.wait_for_timeout(3000)

    # 今日页：Hero 迷你周概览
    print('hero-week 数量:', pg.locator('.hero-week').count())
    print('hw-day 数量:', pg.locator('.hw-day').count())
    pg.screenshot(path='design/shots/fix-today-hero.png', full_page=False)

    # 页脚贴底：footer 底部应接近视口底部
    f = pg.evaluate("""() => { const f=document.querySelector('.site-footer'); const r=f.getBoundingClientRect();
        return {bottom: Math.round(r.bottom), vh: window.innerHeight, pageH: document.documentElement.scrollHeight}; }""")
    print('今日页 footer:', f)

    # 待办页页脚
    pg.click('.nav-item[data-nav="board"]'); pg.wait_for_timeout(1200)
    pg.screenshot(path='design/shots/fix-board-footer.png', full_page=False)
    f2 = pg.evaluate("""() => { const f=document.querySelector('.site-footer'); const r=f.getBoundingClientRect();
        return {bottom: Math.round(r.bottom), vh: window.innerHeight}; }""")
    print('待办页 footer:', f2)

    # 日历页：三卡等高
    pg.click('.nav-item[data-nav="calendar"]'); pg.wait_for_timeout(1500)
    hs = pg.evaluate("""() => {
        const ps = document.querySelectorAll('.cal-side > .cal-side-panel');
        return Array.from(ps).slice(2).map(p => Math.round(p.getBoundingClientRect().height));
    }""")
    print('日历底部三卡高度:', hs, '=> 全相等:', len(set(hs)) == 1)
    pg.screenshot(path='design/shots/fix-calendar-cards.png', full_page=False)

    print('JS 异常:', errs)
    b.close()

srv.shutdown()
