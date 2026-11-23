# -*- coding: utf-8 -*-
"""随笔页截图（明暗），支持 --tag before|after --w 宽度。"""
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

essays = [
    {'id': 'e1', 'date': '2026-11-22', 'title': '关于「慢下来」',
     'text': '最近总在想，快本身不是目的。把一件事做透，比同时开五个头更让人踏实。今天把手头的活收了个尾，晚上的散步也走得比平时慢。', 'tags': ['想法', '生活'], 'updatedAt': 1},
    {'id': 'e2', 'date': '2026-11-20', 'title': '',
     'text': '楼下的桂花开了，路过的时候闻到一整条街的香。想起小时候外婆院子里也有一棵。', 'tags': ['片段'], 'updatedAt': 2},
    {'id': 'e3', 'date': '2026-11-18', 'title': '读书笔记：《被讨厌的勇气》',
     'text': '课题分离这四个字，说起来简单。真正难的是把「别人的评价」从自己的课题里拿出去。', 'tags': ['读书', '想法'], 'updatedAt': 3},
    {'id': 'e4', 'date': '2026-11-15', 'title': '这周复盘',
     'text': '做成了三件事：体检预约、把书桌收拾了、连续七天没有熬夜。没做成的是每天读二十页，下周从十页开始。', 'tags': ['复盘', '生活'], 'updatedAt': 4},
    {'id': 'e5', 'date': '2026-11-10', 'title': '一句备忘',
     'text': '别在最累的时候做决定。', 'tags': ['想法'], 'updatedAt': 5},
    {'id': 'e6', 'date': '2026-11-05', 'title': '',
     'text': '今天下雨，没出门。泡了杯茶把积压的邮件清了，意外地轻松。', 'tags': ['片段', '生活'], 'updatedAt': 6},
]
board = {'data': {'version': 2, 'view': 'today', 'habits': [], 'checks': {}, 'notes': {}, 'moods': {},
    'events': [], 'meds': [], 'doses': {}, 'bodyProfile': {}, 'weights': [], 'essays': essays, 'tasks': []}, 'rev': 1}

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
        pg.clock.install(time=datetime.datetime(2026, 11, 23, 10, 0, 0))
        pg.add_init_script(f"try{{localStorage.setItem('lifeboard.layout','wide');localStorage.setItem('lifeboard.skin','paper');localStorage.setItem('lifeboard.theme.mode','{mode}');}}catch(e){{}}")
        pg.goto(f'http://127.0.0.1:{port}/index.html', wait_until='networkidle'); pg.wait_for_timeout(500)
        pg.click('[data-act="cloud-login"]'); pg.wait_for_timeout(350)
        pg.fill('input[name="email"]', 'test@example.com'); pg.fill('input[name="password"]', 'test@example.com')
        pg.click('form.modal-card button[type="submit"]'); pg.wait_for_timeout(2200)
        pg.click('.nav-item[data-nav="essays"]'); pg.wait_for_timeout(1000)
        pg.screenshot(path=os.path.join(OUT, f'essay-{TAG}-{mode}.png'), full_page=True)
        ctx.close()
    br.close()
srv.shutdown()
print(f'随笔页截图完成：{TAG}（{W} 宽，明暗）')
