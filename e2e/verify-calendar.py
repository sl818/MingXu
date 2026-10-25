# -*- coding: utf-8 -*-
"""验证日历卡片放大填满、与右侧本月用药底部对齐。"""
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
    {'id': 'h_stand', 'name': '站立', 'icon': '🧍', 'type': 'build', 'target': 8, 'unit': '次', 'color': '#6e6f2f', 'note': '', 'createdAt': '2026-10-23T00:00:00Z', 'pinned': False, 'archivedAt': ''},
    {'id': 'h_read', 'name': '阅读', 'icon': '📖', 'type': 'build', 'target': 1, 'unit': '次', 'color': '#4a6b8a', 'note': '', 'createdAt': '2026-10-23T00:00:00Z', 'pinned': False, 'archivedAt': ''},
    {'id': 'h_late', 'name': '不熬夜', 'icon': '🌙', 'type': 'quit', 'target': 1, 'unit': '次', 'color': '#7a5a9a', 'note': '', 'createdAt': '2026-10-23T00:00:00Z', 'pinned': False, 'archivedAt': ''},
    {'id': 'h_meditate', 'name': '冥想', 'icon': '🧘', 'type': 'build', 'target': 10, 'unit': '分钟', 'color': '#8a6a2f', 'note': '', 'createdAt': '2026-10-23T00:00:00Z', 'pinned': False, 'archivedAt': ''},
]
board = {'data': {'version': 2, 'view': 'today', 'habits': HABITS,
    'checks': {'2026-10-22': {'h_water': 8, 'h_move': 1}, '2026-10-23': {'h_water': 6, 'h_breathe': 1}},
    'notes': {}, 'moods': {'2026-10-23': 'happy'}, 'events': [], 'meds': [], 'doses': {},
    'bodyProfile': {'age': 30, 'height': 170}, 'weights': [], 'essays': [], 'tasks': []}, 'rev': 5}


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
    pg = b.new_page(viewport={'width': 1440, 'height': 1050})
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto(f'http://127.0.0.1:{port}/index.html', wait_until='networkidle')
    pg.wait_for_timeout(800)
    pg.click('[data-act="cloud-login"]'); pg.wait_for_timeout(500)
    pg.fill('input[name="email"]', 't@t.top'); pg.fill('input[name="password"]', '12345678')
    pg.click('form.modal-card button[type="submit"]'); pg.wait_for_timeout(3000)
    pg.click('.nav-item[data-nav="calendar"]'); pg.wait_for_timeout(1500)

    m = pg.evaluate("""() => {
        const wrap = document.querySelector('.cal-wrap');
        const med = document.querySelectorAll('.cal-side > .cal-side-panel')[1];
        const cells = document.querySelectorAll('.cal-grid .cal-cell');
        const cell = cells[0];
        return {
            wrapBottom: Math.round(wrap.getBoundingClientRect().bottom),
            medBottom: Math.round(med.getBoundingClientRect().bottom),
            cellH: cell ? Math.round(cell.getBoundingClientRect().height) : 0,
            cellCount: cells.length,
            wdRow: document.querySelector('.cal-wd-row') ? 'yes' : 'no'
        };
    }""")
    print('日历卡片底部:', m['wrapBottom'], '| 本月用药底部:', m['medBottom'], '| 差:', abs(m['wrapBottom'] - m['medBottom']))
    print('格子高度:', m['cellH'], '| 格子数:', m['cellCount'], '| 星期行独立容器:', m['wdRow'])
    pg.screenshot(path='design/shots/fix-calendar-bigger.png', full_page=False)
    print('JS 异常:', errs)
    b.close()

srv.shutdown()
