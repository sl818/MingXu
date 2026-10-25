# -*- coding: utf-8 -*-
"""排版重构后的功能回归测试（mock API + Playwright）。"""
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


with sync_playwright() as p:
    b = p.chromium.launch(channel='chrome', headless=True)
    pg = b.new_page(viewport={'width': 1360, 'height': 1000})
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto(f'http://127.0.0.1:{port}/index.html', wait_until='networkidle')
    pg.wait_for_timeout(800)

    # 登录
    pg.click('[data-act="cloud-login"]'); pg.wait_for_timeout(500)
    pg.fill('input[name="email"]', 't@t.top'); pg.fill('input[name="password"]', '12345678')
    pg.click('form.modal-card button[type="submit"]'); pg.wait_for_timeout(3000)
    check(pg.locator('.hero').count() > 0, '登录进入今日页')

    # 1. 顶部导航 8 项 + 切换
    check(pg.locator('.nav-item').count() == 8, '顶部导航 8 项')
    pg.click('.nav-item[data-nav="board"]'); pg.wait_for_timeout(1200)
    check(pg.locator('.col').count() == 4, '待办看板 4 列')

    # 2. 新建待办
    pg.click('button[data-act="task-new"]:has-text("新建任务")'); pg.wait_for_timeout(600)
    pg.fill('input[name="title"]', '回归测试-新待办')
    pg.click('.modal-card button[type="submit"]'); pg.wait_for_timeout(2200)
    check(pg.locator('text=回归测试-新待办').count() > 0, '新建待办并出现在看板')

    # 3. 今日页打卡（喝水 +1）
    pg.click('.nav-item[data-nav="today"]'); pg.wait_for_timeout(1200)
    water = pg.locator(".vital-card:has-text('喝水')")
    before = water.inner_text() if water.count() else ''
    pg.click('button[data-act="habit-inc"]:has-text("喝一杯")'); pg.wait_for_timeout(2200)
    after = water.inner_text() if water.count() else ''
    check(before != after, '打卡喝水 +1')

    # 4. 心情
    pg.click('button[data-mood="happy"]'); pg.wait_for_timeout(1200)
    mc = pg.locator('button[data-mood="happy"]').get_attribute('class') or ''
    check('active' in mc, '记录心情')

    # 5. 明暗切换
    t0 = pg.evaluate("() => document.documentElement.getAttribute('data-theme')")
    pg.click('#theme-btn'); pg.wait_for_timeout(800)
    t1 = pg.evaluate("() => document.documentElement.getAttribute('data-theme')")
    check(t0 != t1, f'明暗切换 {t0}→{t1}')
    pg.click('#theme-btn'); pg.wait_for_timeout(500)

    # 6. 主题切换（set-skin：切换到赛博再切回）
    pg.click('.nav-item[data-nav="settings"]'); pg.wait_for_timeout(1000)
    skins = pg.locator('.theme-card').count()
    check(skins == 9, f'主题卡片共 9 套（实际 {skins}）')
    pg.click('[data-act="set-skin"]:has-text("赛博")'); pg.wait_for_timeout(800)
    sk = pg.evaluate("() => document.documentElement.getAttribute('data-skin')")
    check(sk == 'cyber', '切换主题到赛博')
    pg.screenshot(path='design/shots/rebuild-theme-cyber.png')
    pg.click('[data-act="set-skin"]:has-text("暖绒")'); pg.wait_for_timeout(800)
    sk2 = pg.evaluate("() => document.documentElement.getAttribute('data-skin')")
    check(sk2 == 'paper', '切回暖绒')

    # 7. 拖拽契约仍在（.task draggable）
    pg.click('.nav-item[data-nav="board"]'); pg.wait_for_timeout(1000)
    drag_ok = pg.evaluate("""() => { const t = document.querySelector('.task'); return t ? t.draggable : 'no-task'; }""")
    check(drag_ok is True or drag_ok == 'true', '拖拽契约 draggable 保留')

    # 8. 快速添加待办（quick-form）
    pg.click('.nav-item[data-nav="today"]'); pg.wait_for_timeout(1000)
    if pg.locator('#quick-form [name="title"]').count():
        pg.fill('#quick-form [name="title"]', '快速添加-回归')
        pg.press('#quick-form [name="title"]', 'Enter'); pg.wait_for_timeout(2000)
        check(pg.locator('text=快速添加-回归').count() > 0, '快速添加待办')

    print('\\nJS 异常:', len(errs))
    for e in errs:
        print('  ', e)
    b.close()

srv.shutdown()
passed = sum(1 for _, ok in results if ok)
print(f'\\n===== 回归结果：{passed}/{len(results)} 通过 =====')
sys.exit(0 if passed == len(results) and not errs else 1)
