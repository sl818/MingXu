# -*- coding: utf-8 -*-
"""v181 前后对比截图：v180（改前）vs v181（改后）。

自带 mock server，/index.html?ver=180 返回旧版页面，?ver=181 返回当前页面。
"""
import http.server
import json
import os
import secrets
import socketserver
import subprocess
import tempfile
import threading
from datetime import datetime

from playwright.sync_api import sync_playwright

DOC = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo'
OUT = 'C:/Users/slgzs/.workbuddy/previews/'
# 改前的版本：用 git 取 v180 的 index.html（Windows 下 Python 读不了 Git Bash 的 /tmp）
OLD = os.path.join(tempfile.gettempdir(), 'index-v180.html')
with open(OLD, 'wb') as f:
    f.write(subprocess.check_output(['git', '-C', DOC, 'show', 'c0cac26:index.html']))
NEW = DOC + '/index.html'
D = '2026-10-24'
USER = {'id': 1, 'email': 'test@example.com', 'display_name': '测试', 'is_admin': False}

HABITS = [
    {'id': 'h_move', 'name': '运动', 'icon': '🏃', 'type': 'build', 'target': 1, 'unit': '次',
     'color': '#b5733f', 'note': '', 'createdAt': '2026-09-01T08:00:00Z', 'pinned': True},
]


def new_board():
    return {'data': {
        'version': 2, 'schemaVersion': 2, 'view': 'today',
        'habits': HABITS,
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


def make_server(board, sessions):
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
            path = self.path.split('?')[0]
            if path == '/index.html':
                ver = '181'
                if 'ver=180' in self.path:
                    ver = '180'
                fn = OLD if ver == '180' else NEW
                body = open(fn, 'rb').read()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                self.wfile.write(body)
                return
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
                return
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
                return
            self.send_response(405)
            self.end_headers()

    class TS(socketserver.ThreadingMixIn, http.server.HTTPServer):
        daemon_threads = True

    srv = TS(('127.0.0.1', 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]


def build_sport(pg):
    """建一个「每周选周六、每天 2 次」的跑步"""
    pg.click('[data-act="move-new"]')
    pg.wait_for_timeout(450)
    pg.click('.sp-grid .sp-opt[data-k="run"]')
    pg.wait_for_timeout(250)
    pg.click('#move-sport-body .sp-freq-opt[data-fk2="weekly"]')
    pg.wait_for_timeout(300)
    for d in pg.eval_on_selector_all('#sp-week button.on', 'els=>els.map(e=>e.dataset.d)'):
        if d != '6':
            pg.click('#sp-week button[data-d="%s"]' % d)
            pg.wait_for_timeout(90)
    pg.click('#sp-week button[data-d="6"]')
    pg.wait_for_timeout(120)
    pg.fill('#sp-perday', '2')
    pg.wait_for_timeout(150)
    pg.click('#move-sport-form button[type="submit"]')
    pg.wait_for_timeout(1600)


def login(pg, port, ver='181'):
    pg.clock.install(time=datetime(2026, 10, 24, 20, 0, 0))
    pg.goto('http://127.0.0.1:%d/index.html?ver=%s' % (port, ver), wait_until='networkidle')
    pg.wait_for_timeout(600)
    pg.click('[data-act="cloud-login"]')
    pg.wait_for_timeout(400)
    pg.fill('input[name="email"]', 'test@example.com')
    pg.fill('input[name="password"]', 'test@example.com')
    pg.click('form.modal-card button[type="submit"]')
    pg.wait_for_timeout(2800)
    pg.evaluate("() => { const b=document.querySelector('[data-nav=\"move\"]'); if(b) b.click(); }")
    pg.wait_for_timeout(600)


with sync_playwright() as pw:
    br = pw.chromium.launch(channel='chrome')

    # ---------- 改前 v180 ----------
    board = new_board()
    sessions = {}
    srv, port = make_server(board, sessions)
    ctx = br.new_context(viewport={'width': 1280, 'height': 1000})
    pg = ctx.new_page()
    login(pg, port, '180')
    build_sport(pg)
    card = pg.locator('.mv-card', has_text='跑步').first
    card.locator('[data-act="move-do"]').click()
    pg.wait_for_timeout(900)
    print('v180 打卡后按钮:', card.locator('.mv-btn').all_inner_texts())
    card.scroll_into_view_if_needed()
    pg.wait_for_timeout(200)
    pg.screenshot(path=OUT + 'cmp-old-card.png')
    # 旧的补数据入口
    if card.locator('[data-act="move-rec"]').count():
        card.locator('[data-act="move-rec"]').click()
        pg.wait_for_timeout(800)
        print('v180 补数据弹窗标题:', pg.inner_text('#move-record-form h3'))
        pg.screenshot(path=OUT + 'cmp-old-modal.png')
    ctx.close()
    srv.shutdown()

    # ---------- 改后 v181 ----------
    board = new_board()
    sessions = {}
    srv, port = make_server(board, sessions)
    ctx = br.new_context(viewport={'width': 1280, 'height': 1000})
    pg = ctx.new_page()
    login(pg, port)
    build_sport(pg)
    card = pg.locator('.mv-card', has_text='跑步').first
    card.locator('[data-act="move-do"]').click()
    pg.wait_for_timeout(900)
    print('v181 打卡后弹窗:', pg.inner_text('#move-record-form h3'))
    pg.screenshot(path=OUT + 'cmp-new-modal.png')
    pg.click('#move-record-form [data-act="close-modal"]')
    pg.wait_for_timeout(700)
    card = pg.locator('.mv-card', has_text='跑步').first
    print('v181 卡片按钮:', card.locator('.mv-btn').all_inner_texts())
    print('v181 状态行:', card.locator('.mv-st').inner_text())
    card.scroll_into_view_if_needed()
    pg.wait_for_timeout(200)
    pg.screenshot(path=OUT + 'cmp-new-card.png')
    # 跳过 → 统计标记
    card.locator('[data-act="move-fill"]').click()
    pg.wait_for_timeout(700)
    pg.click('#move-record-form [data-act="move-skip"]')
    pg.wait_for_timeout(600)
    pg.screenshot(path=OUT + 'cmp-new-skip.png')
    pg.click('[data-act="move-skip-ok"]')
    pg.wait_for_timeout(1200)
    st = pg.locator('.move-page')
    st.scroll_into_view_if_needed()
    pg.wait_for_timeout(300)
    print('v181 统计含「跳 1」:', '跳 1' in pg.inner_text('.move-page'))
    pg.screenshot(path=OUT + 'cmp-new-stats.png')
    ctx.close()
    srv.shutdown()
    br.close()

print('ok')
