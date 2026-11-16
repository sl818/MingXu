"""用药页面新增组件的对比度复核（WCAG AA，真实渲染逐元素计算）"""
import http.server, threading, json, socketserver, secrets, sys
from playwright.sync_api import sync_playwright

DOC = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo'
USER = {'id': 1, 'email': 'test@example.com', 'display_name': '测试', 'is_admin': False}
sessions = {}
D = '2026-10-24'
PORT = 38523

def med(i, name, **kw):
    base = {'id': 'm%d' % i, 'name': name, 'purpose': '抗生素', 'form': '胶囊', 'strength': '',
            'doseAmount': 4, 'doseUnit': '胶囊', 'times': ['08:00', '19:00'],
            'mealTiming': 'after', 'mealOffset': 30, 'courseType': 'short',
            'startDate': '2026-10-20', 'endDate': '2026-11-04', 'reviewDate': '',
            'status': 'active', 'stock': '120', 'note': '', 'manufacturer': '青帝', 'medInfo': '需避光'}
    base.update(kw)
    return base

MEDS = [med(1, '阿莫西林'), med(2, '克拉霉素片', status='paused'), med(3, '雷贝拉唑钠', startDate='2026-10-28')]
HABITS = [{'id': 'h_med', 'name': '用药', 'icon': '💊', 'type': 'build', 'target': 1, 'unit': '次',
           'color': '#2f6f5e', 'note': '', 'createdAt': '2026-10-23T00:00:00Z', 'pinned': True, 'med': True, 'archivedAt': ''}]
board = {'data': {'version': 2, 'view': 'meds', 'habits': HABITS, 'checks': {}, 'notes': {}, 'moods': {}, 'events': [],
                  'meds': MEDS, 'doses': {D: {'m1': {'08:00': 1}}},
                  'bodyProfile': {'age': 30, 'height': 170}, 'weights': [], 'essays': [], 'tasks': []}, 'rev': 5}

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
            n = int(self.headers.get('Content-Length', 0)); body = json.loads(self.rfile.read(n) or b'{}')
            if a == 'login':
                sid = secrets.token_hex(8); sessions[sid] = USER
                self._j({'ok': True, 'user': USER, 'csrf': 'x'}, eh={'Set-Cookie': 'sid=' + sid + '; Path=/'})
            elif a in ('save', 'force'): board['data'] = body['data']; board['rev'] += 1; self._j({'ok': True, 'rev': board['rev']})
            else: self._j({'ok': False, 'error': '?'}, 404)
        else: self.send_response(405); self.end_headers()

class TS(socketserver.ThreadingMixIn, http.server.HTTPServer): daemon_threads = True
srv = TS(('127.0.0.1', PORT), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()

AUDIT_JS = r"""() => {
  const parse = c => {
    c = (c || '').trim();
    if (c.startsWith('#')) {
      const h = c.length === 4 ? c[1] + c[1] + c[2] + c[2] + c[3] + c[3] : c.slice(1, 7);
      if (h.length !== 6) return null;
      return { r: parseInt(h.slice(0, 2), 16), g: parseInt(h.slice(2, 4), 16), b: parseInt(h.slice(4, 6), 16), a: 1 };
    }
    const m = c.match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const p = m[1].split(',').map(Number);
    return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 };
  };
  const lum = c => {
    const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b);
  };
  const blend = (fg, bg) => ({ r: fg.r * fg.a + bg.r * (1 - fg.a), g: fg.g * fg.a + bg.g * (1 - fg.a), b: fg.b * fg.a + bg.b * (1 - fg.a), a: 1 });
  const solidBg = el => {
    let n = el;
    while (n) {
      const c = parse(getComputedStyle(n).backgroundColor);
      if (c && c.a >= 0.95) return c;
      n = n.parentElement;
    }
    const v = parse(getComputedStyle(document.documentElement).getPropertyValue('--bg'));
    return v || { r: 255, g: 255, b: 255, a: 1 };
  };
  const ratio = el => {
    const fgRaw = parse(getComputedStyle(el).color);
    if (!fgRaw) return null;
    const bg = solidBg(el);
    const fg = fgRaw.a < 1 ? blend(fgRaw, bg) : fgRaw;
    const L1 = lum(fg), L2 = lum(bg);
    const hi = Math.max(L1, L2), lo = Math.min(L1, L2);
    return { ratio: Math.round(((hi + 0.05) / (lo + 0.05)) * 100) / 100,
             text: (el.textContent || '').trim().slice(0, 18), cls: el.className.toString().slice(0, 30) };
  };
  const sel = ['.page-head h2', '.page-head p', '.med-group-head h3', '.med-group-head i', '.med-group-hint',
               '.med-row-title b', '.med-row-dose > b', '.med-row-dose > span', '.med-row-note',
               '.med-row-stock', '.med-slot', '.med-slot.done', '.med-slot.is-static', '.hint'];
  const out = [];
  sel.forEach(s => {
    document.querySelectorAll(s).forEach((el, i) => {
      if (i > 0) return;
      const r = ratio(el);
      if (r) { r.sel = s; r.size = parseFloat(getComputedStyle(el).fontSize); r.weight = getComputedStyle(el).fontWeight; out.push(r); }
    });
  });
  return out;
}"""

results = []
def rec(name, ok, detail=''):
    results.append((name, ok, detail))
    print(('PASS  ' if ok else 'FAIL  ') + name + (('  | ' + str(detail)) if detail else ''))

with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)
    for skin in ('paper', 'slate', 'mono', 'forest'):
        for mode in ('light', 'dark'):
            ctx = br.new_context(viewport={'width': 1440, 'height': 950})
            pg = ctx.new_page()
            pg.add_init_script("try{localStorage.setItem('lifeboard.layout','top');localStorage.setItem('lifeboard.skin','%s');localStorage.setItem('lifeboard.theme.mode','%s')}catch(e){}" % (skin, mode))
            pg.goto('http://127.0.0.1:%d/index.html' % PORT, wait_until='networkidle'); pg.wait_for_timeout(600)
            pg.click('[data-act="cloud-login"]'); pg.wait_for_timeout(400)
            pg.fill('input[name="email"]', USER['email']); pg.fill('input[name="password"]', '12345678')
            pg.click('form.modal-card button[type="submit"]'); pg.wait_for_timeout(2400)
            pg.click('.nav-item[data-nav="meds"]'); pg.wait_for_timeout(1100)
            rows = pg.evaluate(AUDIT_JS)
            bad = [r for r in rows if r['ratio'] < 4.5]
            tag = '[%s/%s]' % (skin, mode)
            rec(tag + ' 用药页文字全部 ≥4.5:1', not bad,
                ('%d 项 · 最低 %.2f' % (len(rows), min(r['ratio'] for r in rows))) if not bad else str(bad))
            if skin == 'paper' and mode == 'light':
                pg.screenshot(path='design/shots/medpage-contrast-light.png', full_page=True)
            if skin == 'slate' and mode == 'dark':
                pg.screenshot(path='design/shots/medpage-dark.png', full_page=True)
            ctx.close()
    br.close()
srv.shutdown()

ok = sum(1 for r in results if r[1])
print('\n用药页对比度：%d/%d 通过' % (ok, len(results)))
if ok != len(results):
    sys.exit(1)
