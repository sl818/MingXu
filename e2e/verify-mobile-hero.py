"""手机端 Hero 排版验证：多宽度测量 + 溢出检测"""
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
    {'id': 'h_breath', 'name': '478呼吸法', 'icon': '🌬️', 'type': 'build', 'target': 1, 'unit': '次', 'color': '#5b8f8a', 'note': '', 'createdAt': '2026-10-23T00:00:00Z', 'pinned': True, 'optional': True, 'archivedAt': ''},
]

board = {'data': {'version': 2, 'view': 'today', 'habits': HABITS,
                  'checks': {'2026-10-22': {'h_water': 8, 'h_move': 1}, '2026-10-23': {'h_water': 6, 'h_breath': 1}},
                  'notes': {}, 'moods': {'2026-10-24': 'happy'}, 'events': [], 'meds': [], 'doses': {},
                  'bodyProfile': {'age': 30, 'height': 170}, 'weights': [], 'essays': [],
                  'tasks': [{'id': 't1', 'title': '收被单被子', 'note': '', 'tag': '生活', 'priority': '中', 'status': 'todo', 'due': '2026-10-24', 'createdAt': '2026-10-23T08:00:00Z'}]},
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

MEASURE = """() => {
  const g = s => document.querySelector(s);
  const box = e => { if (!e) return null; const r = e.getBoundingClientRect();
    return {x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height), right: Math.round(r.right), bottom: Math.round(r.bottom)}; };
  // 找出所有超出视口右边界 / 左边界 的元素
  const over = [];
  document.querySelectorAll('.main *, .mobile-tabbar *').forEach(e => {
    const r = e.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) return;
    if (r.right > innerWidth + 1 || r.left < -1) {
      over.push({cls: (e.className && e.className.baseVal !== undefined ? e.className.baseVal : e.className || e.tagName).toString().slice(0, 46),
                 left: Math.round(r.left), right: Math.round(r.right), w: Math.round(r.width)});
    }
  });
  const dateEl = g('.hero-date');
  const dateRows = dateEl ? Math.round(dateEl.getBoundingClientRect().height / (parseFloat(getComputedStyle(dateEl).fontSize) * 1.6)) : 0;
  return {
    vw: innerWidth,
    hOverflow: document.documentElement.scrollWidth - innerWidth,
    hero: box(g('.hero')),
    date: box(g('.hero-date')),
    h1: box(g('.hero h1')),
    ring: box(g('.hero-ring')),
    pctSmall: box(g('.hero-pct small')),
    chips: box(g('.hero-chips')),
    heroMainDisplay: getComputedStyle(g('.hero-main')).display,
    over: over.slice(0, 8),
    overCount: over.length
  };
}"""

with sync_playwright() as p:
    b = p.chromium.launch(channel='chrome', headless=True)
    for w, h, label in [(390, 844, 'iPhone13'), (375, 812, 'iPhoneX'), (360, 780, 'Android360')]:
        ctx = b.new_context(viewport={'width': w, 'height': h}, device_scale_factor=3,
                            is_mobile=True, has_touch=True,
                            user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1')
        pg = ctx.new_page()
        errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.goto(f'http://127.0.0.1:{port}/index.html', wait_until='networkidle')
        pg.wait_for_timeout(700)
        try:
            pg.click('[data-act="cloud-login"]', timeout=5000); pg.wait_for_timeout(500)
            pg.fill('input[name="email"]', 't@t.top'); pg.fill('input[name="password"]', '12345678')
            pg.click('form.modal-card button[type="submit"]'); pg.wait_for_timeout(2800)
        except Exception as e:
            print(label, 'login err', e)
        r = pg.evaluate(MEASURE)
        print(f"===== {label} {w}px =====")
        print(json.dumps(r, ensure_ascii=False, indent=1))
        print('pageerrors:', errs)
        pg.screenshot(path=f'design/shots/mh-{w}.png')
        ctx.close()
    b.close()

srv.shutdown()
