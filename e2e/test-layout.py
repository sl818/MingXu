# -*- coding: utf-8 -*-
"""双排版切换测试：顶部导航 <-> 左侧导航，含 localStorage 持久化。"""
import http.server, threading, json, socketserver, secrets, sys
from playwright.sync_api import sync_playwright

DOC = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo'
USER = {'id': 1, 'email': 't@t.top', 'display_name': 'T', 'is_admin': False}
sessions = {}
board = {'data': {'version': 2, 'view': 'today', 'habits': [
    {'id': 'h_med', 'name': '用药', 'icon': '💊', 'type': 'build', 'target': 1, 'unit': '次', 'color': '#2f6f5e', 'note': '', 'createdAt': '2026-10-23T00:00:00Z', 'pinned': True, 'med': True, 'archivedAt': ''},
    {'id': 'h_water', 'name': '喝水', 'icon': '💧', 'type': 'build', 'target': 8, 'unit': '杯', 'color': '#4c7f96', 'note': '', 'createdAt': '2026-10-23T00:00:00Z', 'pinned': True, 'archivedAt': ''},
    {'id': 'h_move', 'name': '运动', 'icon': '🏃', 'type': 'build', 'target': 1, 'unit': '次', 'color': '#b5733f', 'note': '', 'createdAt': '2026-10-23T00:00:00Z', 'pinned': True, 'archivedAt': ''},
    {'id': 'h_breathe', 'name': '478呼吸法', 'icon': '🌬️', 'type': 'build', 'target': 1, 'unit': '次', 'color': '#5b8f8a', 'note': '', 'createdAt': '2026-10-23T00:00:00Z', 'pinned': True, 'optional': True, 'archivedAt': ''}],
    'checks': {}, 'notes': {}, 'moods': {}, 'events': [], 'meds': [], 'doses': {},
    'bodyProfile': {'age': 30, 'height': 170}, 'weights': [], 'essays': [], 'tasks': [
    {'id': 't1', 'title': '收被单被子', 'note': '', 'tag': '生活', 'priority': '中', 'status': 'todo', 'due': '2026-10-24', 'createdAt': '2026-10-23T08:00:00Z'}]}, 'rev': 5}


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

results = []


def check(cond, name):
    results.append((name, bool(cond)))
    print(('PASS  ' if cond else 'FAIL  ') + name)


def layout_state(pg):
    return pg.evaluate("""() => {
        const sb = document.querySelector('.sidebar');
        const app = document.querySelector('.app');
        return {
            attr: document.documentElement.getAttribute('data-layout'),
            sbDir: getComputedStyle(sb).flexDirection,
            sbDisp: getComputedStyle(sb).display,
            appDisp: getComputedStyle(app).display
        };
    }""")


with sync_playwright() as p:
    b = p.chromium.launch(channel='chrome', headless=True)
    pg = b.new_page(viewport={'width': 1360, 'height': 1000})
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto(f'http://127.0.0.1:{port}/index.html', wait_until='networkidle')
    pg.wait_for_timeout(800)
    pg.click('[data-act="cloud-login"]'); pg.wait_for_timeout(500)
    pg.fill('input[name="email"]', 't@t.top'); pg.fill('input[name="password"]', '12345678')
    pg.click('form.modal-card button[type="submit"]'); pg.wait_for_timeout(3000)

    st = layout_state(pg)
    print('初始:', st)
    check(st['attr'] == 'top', '默认布局 = top')
    check(st['sbDir'] == 'row' and st['appDisp'] == 'flex', '默认是顶部导航（横向顶栏 + flex 纵向）')

    # 去设置页切到左侧导航
    pg.click('.nav-item[data-nav="settings"]'); pg.wait_for_timeout(1200)
    check(pg.locator('.layout-card').count() == 2, '设置页有 2 个排版卡片')
    pg.screenshot(path='design/shots/layout-settings.png')
    pg.click('[data-act="set-layout"][data-layout="side"]'); pg.wait_for_timeout(1500)
    st2 = layout_state(pg)
    print('切到 side:', st2)
    check(st2['attr'] == 'side', '切换后 data-layout = side')
    check(st2['sbDir'] == 'column' and st2['appDisp'] == 'grid', '左侧导航：纵向侧栏 + grid 两列')
    pg.screenshot(path='design/shots/layout-side.png')

    # 切回顶部
    pg.click('.nav-item[data-nav="settings"]'); pg.wait_for_timeout(1000)
    pg.click('[data-act="set-layout"][data-layout="top"]'); pg.wait_for_timeout(1500)
    st3 = layout_state(pg)
    check(st3['attr'] == 'top' and st3['sbDir'] == 'row', '切回顶部导航')

    # 持久化：切到 side 后刷新，应保持 side
    pg.click('[data-act="set-layout"][data-layout="side"]'); pg.wait_for_timeout(1200)
    pg.reload(wait_until='networkidle'); pg.wait_for_timeout(2500)
    st4 = layout_state(pg)
    print('刷新后:', st4)
    check(st4['attr'] == 'side' and st4['sbDir'] == 'column', '刷新后保持左侧导航（持久化）')

    # 恢复默认 top，避免影响用户
    pg.evaluate("() => localStorage.setItem('lifeboard.layout','top')")
    print('\\nJS 异常:', len(errs))
    for e in errs:
        print('  ', e)
    b.close()

srv.shutdown()
passed = sum(1 for _, ok in results if ok)
print(f'\\n===== 双布局测试：{passed}/{len(results)} 通过 =====')
sys.exit(0 if passed == len(results) and not errs else 1)
