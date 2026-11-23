# -*- coding: utf-8 -*-
"""诊断体重页折线图：SVG 实际尺寸 vs viewBox、path 范围、两栏网格。"""
import http.server, threading, json, socketserver, secrets
from datetime import datetime
from playwright.sync_api import sync_playwright

DOC = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo'
USER = {'id': 1, 'email': 'test@example.com', 'display_name': '测试', 'is_admin': False}
sessions = {}
weights = [{'id': 'w%02d' % i, 'date': '2026-11-%02d' % (i + 1), 'weight': 113.1 - i * 0.4,
            'bmi': 39.1, 'age': 30, 'height': 170, 'fat': 34.5 + i * 0.1} for i in range(12)]
board = {'data': {'version': 2, 'view': 'today', 'habits': [], 'checks': {}, 'notes': {}, 'moods': {},
    'events': [], 'meds': [], 'doses': {}, 'bodyProfile': {'age': 30, 'height': 170, 'goalWeight': 100},
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
    ctx = br.new_context(viewport={'width': 1920, 'height': 1080})
    pg = ctx.new_page()
    pg.clock.install(time=datetime(2026, 11, 22, 10, 0, 0))
    pg.add_init_script("try{localStorage.setItem('lifeboard.layout','wide');localStorage.setItem('lifeboard.skin','paper');localStorage.setItem('lifeboard.theme.mode','light');}catch(e){}")
    pg.goto(f'http://127.0.0.1:{port}/index.html', wait_until='networkidle'); pg.wait_for_timeout(500)
    pg.click('[data-act="cloud-login"]'); pg.wait_for_timeout(350)
    pg.fill('input[name="email"]', 'test@example.com'); pg.fill('input[name="password"]', 'test@example.com')
    pg.click('form.modal-card button[type="submit"]'); pg.wait_for_timeout(2200)
    pg.click('.nav-item[data-nav="weight"]'); pg.wait_for_timeout(1000)
    r = pg.evaluate("""() => {
      const q = s => document.querySelector(s);
      const rect = e => { const b = e.getBoundingClientRect(); return {x:Math.round(b.x),y:Math.round(b.y),w:Math.round(b.width),h:Math.round(b.height)}; };
      const svg = q('.ww-svg');
      const charts = q('.weight-charts');
      const leftPanel = q('.weight-charts > .panel');
      const cs = svg ? getComputedStyle(svg) : null;
      const line = svg && svg.querySelector('.ww-line');
      const bb = line ? line.getBBox() : null;
      return {
        chartsRect: charts ? rect(charts) : null,
        chartsCols: charts ? getComputedStyle(charts).gridTemplateColumns : null,
        leftPanelRect: leftPanel ? rect(leftPanel) : null,
        svgRect: svg ? rect(svg) : null,
        svgViewBox: svg ? svg.getAttribute('viewBox') : null,
        svgPreserve: svg ? svg.getAttribute('preserveAspectRatio') : null,
        svgCssW: cs ? cs.width : null, svgCssH: cs ? cs.height : null, svgMaxH: cs ? cs.maxHeight : null,
        lineBBox: bb ? {x:Math.round(bb.x),y:Math.round(bb.y),w:Math.round(bb.width),h:Math.round(bb.height)} : null,
        dots: svg ? svg.querySelectorAll('.ww-dot').length : 0
      };
    }""")
    print(json.dumps(r, ensure_ascii=False, indent=1))
    br.close()
srv.shutdown()
