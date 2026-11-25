# -*- coding: utf-8 -*-
"""v185 前后对比截图：v184（改前）vs v185（改后）。

对比三处：
1. 随笔列表页：卡片摘要按 Markdown 渲染（改前是 **粗体** 这样的字面）＋ 多一个「全文」按钮
2. 点卡片：改前点了没反应，改后弹「全文」弹窗（Markdown 渲染）
3. 编辑弹窗：改后多了「预览」按钮与 Markdown 语法提示

用法：python e2e/shot-compare-v185.py
产物：~/.workbuddy/previews/essay-v185-*.png
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
OLD = os.path.join(tempfile.gettempdir(), 'index-v184.html')
with open(OLD, 'wb') as f:
    f.write(subprocess.check_output(['git', '-C', DOC, 'show', 'HEAD:index.html']))
NEW = DOC + '/index.html'
USER = {'id': 1, 'email': 'test@example.com', 'display_name': '测试', 'is_admin': False}
D = '2026-10-24'

MD_TEXT = (
    "# 散步的早晨\n"
    "出门走了一圈，**风很凉**，树上的叶子黄了一半。\n"
    "\n"
    "> 忽然觉得，慢一点也不是坏事。\n"
    "\n"
    "- 走了 3200 步\n"
    "- 在河边坐了十分钟\n"
    "\n"
    "路线记在[地图](https://todo.csl88.top/)里。"
)

XSS_TEXT = "随手记一句。<script>alert(1)</script>"

ESSAYS = [
    {'id': 'e_md', 'date': '2026-10-24', 'title': '散步的早晨', 'text': MD_TEXT,
     'tags': ['日常', '记录'], 'createdAt': '2026-10-24T08:00:00Z', 'updatedAt': 1790000000000},
    {'id': 'e_xss', 'date': '2026-10-23', 'title': '随手一句', 'text': XSS_TEXT,
     'tags': [], 'createdAt': '2026-10-23T08:00:00Z', 'updatedAt': 1790000000000},
    {'id': 'e_plain', 'date': '2026-10-22', 'title': '', 'text': '今天没什么特别的事，随便写一句。',
     'tags': [], 'createdAt': '2026-10-22T08:00:00Z', 'updatedAt': 1790000000000},
]


def new_board():
    return {'data': {
        'version': 2, 'schemaVersion': 2, 'view': 'today',
        'habits': [], 'modules': {}, 'modulesAt': 0,
        'checks': {}, 'skips': {}, 'notes': {}, 'moods': {}, 'events': [],
        'meds': [], 'doses': {}, 'bodyProfile': {'age': 30, 'height': 170},
        'weights': [], 'essays': [dict(e) for e in ESSAYS], 'tasks': [], 'money': {}, 'quit': {},
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
                fn = OLD if 'ver=184' in self.path else NEW
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
    ctx = br.new_context(viewport={'width': 1180, 'height': 1000})
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
    pg.evaluate("() => { const b=document.querySelector('[data-nav=\"essays\"]'); if(b) b.click(); }")
    pg.wait_for_timeout(800)

    # ① 列表页
    pg.screenshot(path=OUT + 'essay-v185-%s-list.png' % tag)
    prev = pg.locator('.essay-card').first.locator('.essay-text').inner_html()
    print('%s 卡片摘要 HTML: %s' % (tag, prev[:180]))
    print('%s 卡片按钮: %s' % (tag, pg.eval_on_selector_all('.essay-card .essay-actions button', 'e=>e.map(x=>x.textContent.trim())')))

    # ② 点卡片 → 改前没反应，改后弹全文
    pg.locator('.essay-card').first.click()
    pg.wait_for_timeout(900)
    has_modal = pg.locator('.essay-view').count()
    print('%s 点卡片后有全文弹窗: %s' % (tag, has_modal))
    pg.screenshot(path=OUT + 'essay-v185-%s-view.png' % tag)
    if has_modal:
        print('%s 正文 HTML: %s' % (tag, pg.locator('.essay-body').inner_html()[:200]))
        pg.click('.essay-view [data-act="close-modal"]')
        pg.wait_for_timeout(500)

    # ③ 编辑弹窗
    pg.locator('.essay-card').first.locator('[data-act="essay-edit"]').click()
    pg.wait_for_timeout(700)
    print('%s 编辑弹窗有预览按钮: %s' % (tag, pg.locator('#essay-form [data-act="essay-md-toggle"]').count()))
    print('%s 有 Markdown 提示: %s' % (tag, 'Markdown' in pg.inner_text('#essay-form')))
    pg.screenshot(path=OUT + 'essay-v185-%s-edit.png' % tag)
    print('%s JS 错误: %s' % (tag, errs[:2]))
    ctx.close()
    srv.shutdown()


with sync_playwright() as pw:
    br = pw.chromium.launch(channel='chrome')
    run(br, '184', 'old')
    run(br, '185', 'new')
    br.close()
print('ok')
