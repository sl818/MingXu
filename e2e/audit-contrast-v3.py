"""本地（wide 布局）对比度复核：页头 / 三卡 / 右栏 / 打卡卡"""
import http.server, threading, json, socketserver, secrets
from playwright.sync_api import sync_playwright

DOC = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo'
USER = {'id': 1, 'email': 'test@example.com', 'display_name': '测试', 'is_admin': False}
sessions = {}
D = '2026-10-24'
HABITS = [
    {'id': 'h_med', 'name': '用药', 'icon': '💊', 'type': 'build', 'target': 2, 'unit': '次', 'color': '#2f6f5e', 'note': '', 'createdAt': '2026-10-23T00:00:00Z', 'pinned': True, 'med': True, 'archivedAt': ''},
    {'id': 'h_water', 'name': '喝水', 'icon': '💧', 'type': 'build', 'target': 8, 'unit': '杯', 'color': '#4c7f96', 'note': '', 'createdAt': '2026-10-23T00:00:00Z', 'pinned': True, 'archivedAt': ''},
    {'id': 'h_move', 'name': '运动', 'icon': '🏃', 'type': 'build', 'target': 1, 'unit': '次', 'color': '#b5733f', 'note': '', 'createdAt': '2026-10-23T00:00:00Z', 'pinned': True, 'archivedAt': ''},
    {'id': 'h_breathe', 'name': '478呼吸法', 'icon': '🌬️', 'type': 'build', 'target': 1, 'unit': '次', 'color': '#5b8f8a', 'note': '', 'createdAt': '2026-10-23T00:00:00Z', 'pinned': True, 'optional': True, 'archivedAt': ''},
]
board = {'data': {'version': 2, 'view': 'today', 'habits': HABITS,
                  'checks': {'2026-10-22': {'h_water': 8, 'h_move': 1}, '2026-10-23': {'h_water': 6}, '2026-10-24': {'h_water': 12, 'h_move': 1, 'h_med': 2, 'h_breathe': 1}},
                  'notes': {}, 'moods': {D: 'happy'}, 'events': [],
                  'meds': [{'id': 'm1', 'name': '晚间服药', 'purpose': '其他', 'form': '片', 'strength': '', 'doseAmount': 1, 'doseUnit': '片', 'times': ['08:00', '20:00'], 'courseType': 'long', 'startDate': '2026-10-01', 'endDate': '', 'reviewDate': '', 'status': 'active', 'stock': '14', 'note': ''}],
                  'doses': {D: {'m1': {'08:00': 1}}}, 'bodyProfile': {'age': 30, 'height': 170},
                  'weights': [], 'essays': [], 'tasks': []}, 'rev': 5}


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


AUDIT = """() => {
  const parse = c => { const m = c.match(/rgba?\\(([^)]+)\\)/); if (!m) return null;
    const p = m[1].split(',').map(x => parseFloat(x.trim()));
    return {r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1}; };
  const lin = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
  const lum = c => 0.2126 * lin(c.r) + 0.7152 * lin(c.g) + 0.0722 * lin(c.b);
  const over = (fg, bg) => ({r: fg.r*fg.a + bg.r*(1-fg.a), g: fg.g*fg.a + bg.g*(1-fg.a), b: fg.b*fg.a + bg.b*(1-fg.a), a: 1});
  const ratio = (a, b) => { const l1 = lum(a), l2 = lum(b); const [hi, lo] = l1 >= l2 ? [l1, l2] : [l2, l1];
    return (hi + 0.05) / (lo + 0.05); };
  const bgOf = el => { let n = el;
    while (n && n !== document.documentElement) {
      const cs = getComputedStyle(n); const bc = parse(cs.backgroundColor);
      if (bc && bc.a > 0.85) return bc;
      if (cs.backgroundImage && cs.backgroundImage !== 'none') return null;
      n = n.parentElement; }
    return parse(getComputedStyle(document.body).backgroundColor) || {r:255,g:255,b:255,a:1}; };
  const out = []; const seen = new Set();
  document.querySelectorAll('.main *, .sidebar *, .rail *').forEach(el => {
    if (el.children.length) return;
    const txt = (el.textContent || '').trim(); if (!txt || txt.length > 40) return;
    const r = el.getBoundingClientRect(); if (r.width < 4 || r.height < 4) return;
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.display === 'none' || parseFloat(cs.opacity) < 0.5) return;
    const fg = parse(cs.color); if (!fg) return;
    const bg = bgOf(el); if (!bg) return;
    const real = fg.a < 1 ? over(fg, bg) : fg;
    const cr = ratio(real, bg);
    const size = parseFloat(cs.fontSize);
    const bold = parseInt(cs.fontWeight, 10) >= 600;
    const need = (size >= 24 || (size >= 18.66 && bold)) ? 3 : 4.5;
    if (cr < need) {
      const key = cs.color + '|' + Math.round(size) + '|' + txt.slice(0, 8);
      if (seen.has(key)) return; seen.add(key);
      out.push({text: txt.slice(0, 20), color: cs.color, size: Math.round(size*10)/10, ratio: Math.round(cr*100)/100, need});
    }
  });
  return out;
}"""

srv = TS(('127.0.0.1', 0), H)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()

total = 0
with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)
    for skin, theme in [('paper', 'light'), ('paper', 'dark'), ('slate', 'dark'), ('forest', 'light')]:
        ctx = br.new_context(viewport={'width': 1440, 'height': 900})
        pg = ctx.new_page()
        pg.add_init_script(f"try{{localStorage.setItem('lifeboard.layout','wide');localStorage.setItem('lifeboard.skin','{skin}');localStorage.setItem('lifeboard.theme.mode','{theme}');}}catch(e){{}}")
        pg.goto(f'http://127.0.0.1:{port}/index.html', wait_until='networkidle'); pg.wait_for_timeout(600)
        pg.click('[data-act="cloud-login"]'); pg.wait_for_timeout(400)
        pg.fill('input[name="email"]', 'test@example.com'); pg.fill('input[name="password"]', 'test@example.com')
        pg.click('form.modal-card button[type="submit"]'); pg.wait_for_timeout(2800)
        bad = pg.evaluate(AUDIT)
        real = [b for b in bad if 'rgba(0, 0, 0, 0)' not in b['color']]
        total += len(real)
        print(f"[{skin}/{theme}] 低于 AA：{len(real)} 处" + ('  ✓' if not real else ''))
        for b in real[:5]:
            print(f'    {b["ratio"]}:1 (需{b["need"]}) {b["size"]}px "{b["text"]}" {b["color"]}')
        pg.screenshot(path=f'design/shots/ct-{skin}-{theme}.png')
        ctx.close()
    br.close()
srv.shutdown()
print(f'\n合计低于 AA：{total} 处')
