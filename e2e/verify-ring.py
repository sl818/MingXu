"""遍历 9 套皮肤 × 明暗，检查手机端圆环内 '100%' 与标签是否落在内径内"""
import http.server, threading, json, socketserver, secrets
from playwright.sync_api import sync_playwright

DOC = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo'
USER = {'id': 1, 'email': 't@t.top', 'display_name': 'T', 'is_admin': False}
sessions = {}

HABITS = [
    {'id': 'h_med', 'name': '用药', 'icon': '💊', 'type': 'build', 'target': 1, 'unit': '次', 'color': '#2f6f5e', 'note': '', 'createdAt': '2026-10-23T00:00:00Z', 'pinned': True, 'med': True, 'archivedAt': ''},
    {'id': 'h_water', 'name': '喝水', 'icon': '💧', 'type': 'build', 'target': 8, 'unit': '杯', 'color': '#4c7f96', 'note': '', 'createdAt': '2026-10-23T00:00:00Z', 'pinned': True, 'archivedAt': ''},
    {'id': 'h_move', 'name': '运动', 'icon': '🏃', 'type': 'build', 'target': 1, 'unit': '次', 'color': '#b5733f', 'note': '', 'createdAt': '2026-10-23T00:00:00Z', 'pinned': True, 'archivedAt': ''},
    {'id': 'h_stand', 'name': '站立', 'icon': '🧍', 'type': 'build', 'target': 8, 'unit': '次', 'color': '#7a6a9c', 'note': '', 'createdAt': '2026-10-23T00:00:00Z', 'pinned': True, 'archivedAt': ''},
    {'id': 'h_quit', 'name': '戒烟', 'icon': '🚭', 'type': 'quit', 'target': 1, 'unit': '次', 'color': '#9c5a5a', 'note': '', 'createdAt': '2026-10-23T00:00:00Z', 'pinned': True, 'archivedAt': ''},
    {'id': 'h_read', 'name': '阅读', 'icon': '📖', 'type': 'build', 'target': 1, 'unit': '次', 'color': '#5b8f8a', 'note': '', 'createdAt': '2026-10-23T00:00:00Z', 'pinned': True, 'archivedAt': ''},
    {'id': 'h_vit', 'name': '维生素', 'icon': '🌿', 'type': 'build', 'target': 2, 'unit': '次', 'color': '#8a7a3c', 'note': '', 'createdAt': '2026-10-23T00:00:00Z', 'pinned': True, 'archivedAt': ''},
    {'id': 'h_str', 'name': '拉伸', 'icon': '🧘', 'type': 'build', 'target': 1, 'unit': '次', 'color': '#8a7a3c', 'note': '', 'createdAt': '2026-10-23T00:00:00Z', 'pinned': True, 'archivedAt': ''},
]
D = '2026-10-24'
checks = {D: {'h_med': 1, 'h_water': 12, 'h_move': 1, 'h_stand': 8, 'h_read': 1, 'h_vit': 2, 'h_str': 1}}
board = {'data': {'version': 2, 'view': 'today', 'habits': HABITS, 'checks': checks,
                  'notes': {}, 'moods': {D: 'happy'}, 'events': [], 'meds': [], 'doses': {},
                  'bodyProfile': {'age': 30, 'height': 170}, 'weights': [], 'essays': [], 'tasks': []},
         'rev': 5}


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
            elif a == 'load': self._j({'ok': True, 'data': board['data'], 'rev': board['rev'], 'updated_at': 0})
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
                self._j({'ok': True, 'rev': board['rev']})
            else: self._j({'ok': False, 'error': '?'}, 404)
        else:
            self.send_response(405); self.end_headers()


class TS(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


srv = TS(('127.0.0.1', 0), H)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()

M = """() => {
  const g = s => document.querySelector(s);
  const ring = g('.hero-ring'); const rb = ring.getBoundingClientRect();
  const b = g('.hero-pct b'), sm = g('.hero-pct small');
  const bb = b.getBoundingClientRect(), sb = sm.getBoundingClientRect();
  const cs = getComputedStyle(b);
  const inner = rb.width * (1 - 2 * 8 / 116);
  return {ringW: Math.round(rb.width), inner: Math.round(inner),
          fs: cs.fontSize, ff: cs.fontFamily.split(',')[0],
          pctW: Math.round(bb.width), labelW: Math.round(sb.width),
          label: sm.innerText,
          fits: bb.width <= inner - 2 && sb.width <= inner - 2,
          hOverflow: document.documentElement.scrollWidth - innerWidth};
}"""

SKINS = ['paper', 'slate', 'mono', 'clay', 'mist', 'forest', 'neu', 'cyber', 'retro']
bad = []

with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)
    ctx = br.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True, device_scale_factor=2)
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto(f'http://127.0.0.1:{port}/index.html', wait_until='networkidle'); pg.wait_for_timeout(600)
    pg.click('[data-act="cloud-login"]'); pg.wait_for_timeout(400)
    pg.fill('input[name="email"]', 't@t.top'); pg.fill('input[name="password"]', '12345678')
    pg.click('form.modal-card button[type="submit"]'); pg.wait_for_timeout(2600)

    for skin in SKINS:
        for theme in ('light', 'dark'):
            pg.evaluate(f"() => {{ localStorage.setItem('lifeboard.skin','{skin}'); localStorage.setItem('lifeboard.theme.mode','{theme}'); }}")
            pg.reload(wait_until='networkidle'); pg.wait_for_timeout(1500)
            r = pg.evaluate(M)
            ok = r['fits'] and r['hOverflow'] <= 0
            mark = 'OK ' if ok else '⚠ '
            if not ok: bad.append((skin, theme, r))
            print(f"[{mark}] {skin:7s}/{theme:5s} 环{r['ringW']} 内径{r['inner']:3d} | 字号{r['fs']:>6s} {r['ff'][:14]:14s} | 100%={r['pctW']:3d} | {r['label']}={r['labelW']:3d} | 横溢{r['hOverflow']}")
            pg.screenshot(path=f'design/shots/ring-{skin}-{theme}.png')
    print('\npageerrors:', errs)
    print('不达标:', bad if bad else '无')
    ctx.close()
    br.close()

srv.shutdown()
