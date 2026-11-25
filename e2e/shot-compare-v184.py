# -*- coding: utf-8 -*-
"""v184 前后对比截图：v183（改前）vs v184（改后）。

对比三处：
1. 新建运动弹窗的频率区（每日步数不再有次数框；其余 6 种多出运动开始时间）
2. 运动后数据弹窗的字段文案（任务完成时间 / 运动时长（分钟））
3. 卡片按钮与记录入口（补数据不再常驻；多出今日任务记录）
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
OLD = os.path.join(tempfile.gettempdir(), 'index-v183.html')
with open(OLD, 'wb') as f:
    f.write(subprocess.check_output(['git', '-C', DOC, 'show', 'f9abc37:index.html']))
NEW = DOC + '/index.html'
USER = {'id': 1, 'email': 'test@example.com', 'display_name': '测试', 'is_admin': False}
D = '2026-10-24'


def new_board():
    return {'data': {
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
                fn = OLD if 'ver=183' in self.path else NEW
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


def run(br, ver, tag):
    board = new_board()
    sessions = {}
    srv, port = make_server(board, sessions)
    ctx = br.new_context(viewport={'width': 1180, 'height': 1050})
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
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
    pg.wait_for_timeout(700)

    # ① 每日步数的新建弹窗（频率区）
    pg.click('[data-act="move-new"]')
    pg.wait_for_timeout(600)
    pg.screenshot(path=OUT + 'cmp3-%s-steps.png' % tag)
    print('%s 每日步数频率区有次数框: %s' % (tag, pg.locator('#move-sport-body #sp-freqn').count()))
    print('%s 每日步数有运动开始时间: %s' % (tag, pg.locator('#move-sport-body #sp-starttime').count()))
    # 切到跑步，看频率区与运动开始时间
    pg.click('.sp-grid .sp-opt[data-k="run"]')
    pg.wait_for_timeout(500)
    pg.screenshot(path=OUT + 'cmp3-%s-run.png' % tag)
    print('%s 跑步有运动开始时间: %s' % (tag, pg.locator('#move-sport-body #sp-starttime').count()))
    pg.click('#move-sport-form button[type="submit"]')
    pg.wait_for_timeout(1500)

    # ② 建跑步 → 打卡 → 运动后数据弹窗（字段文案）
    pg.click('[data-act="move-new"]')
    pg.wait_for_timeout(500)
    pg.click('.sp-grid .sp-opt[data-k="run"]')
    pg.wait_for_timeout(400)
    pg.fill('#move-sport-body #sp-tval', '5')
    pg.wait_for_timeout(150)
    pg.click('#move-sport-form button[type="submit"]')
    pg.wait_for_timeout(1500)
    pg.locator('.mv-card', has_text='跑步').last.locator('[data-act="move-do"]').click()
    pg.wait_for_timeout(900)
    labels = pg.eval_on_selector_all('#move-record-form .field > span', 'e=>e.map(x=>x.textContent.trim())')
    print('%s 弹窗字段标签: %s' % (tag, json.dumps(labels, ensure_ascii=False)))
    pg.screenshot(path=OUT + 'cmp3-%s-after.png' % tag)
    pg.click('#move-record-form [data-act="close-modal"]')
    pg.wait_for_timeout(600)

    # ③ 卡片区（按钮与记录入口）
    pg.evaluate("() => { const el=document.querySelector('.mv-card'); if(el) el.scrollIntoView({block:'center'}); }")
    pg.wait_for_timeout(300)
    pg.screenshot(path=OUT + 'cmp3-%s-card.png' % tag)
    print('%s 卡片按钮: %s' % (tag, pg.eval_on_selector_all('.mv-card .mv-btn', 'e=>e.map(x=>x.textContent.trim())')))
    print('%s 页面有底部明细总表: %s' % (tag, pg.locator('.dv-list').count()))
    print('%s JS 错误: %s' % (tag, errs[:2]))
    ctx.close()
    srv.shutdown()


with sync_playwright() as pw:
    br = pw.chromium.launch(channel='chrome')
    run(br, '183', 'old')
    run(br, '184', 'new')
    br.close()
print('ok')
