"""用药页统计卡验证：总数 / 进行中 / 暂停 / 停用 / 今日进度 / 库存告急"""
import http.server, threading, json, socketserver, secrets, sys
from datetime import datetime
from playwright.sync_api import sync_playwright

DOC = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo'
USER = {'id': 1, 'email': 'test@sl00.top', 'display_name': '测试', 'is_admin': False}
sessions = {}
PORT = 38560
D = '2026-10-24'

def med(i, name, **kw):
    base = {'id': 'm%d' % i, 'name': name, 'purpose': '抗生素', 'form': '胶囊', 'strength': '0.25g',
            'doseAmount': 1, 'doseUnit': '粒', 'times': ['08:00', '20:00'],
            'mealTiming': 'after', 'mealOffset': 30, 'courseType': 'short',
            'startDate': '2026-10-20', 'endDate': '2026-11-04', 'reviewDate': '',
            'status': 'active', 'stock': '100', 'note': '', 'manufacturer': '青帝', 'medInfo': ''}
    base.update(kw)
    return base

MEDS = [
    med(1, '阿莫西林胶囊', stock='10'),                 # 1 粒 × 2 次 → 5 天 → 告急
    med(2, '克拉霉素片', stock='100'),                  # 50 天 → 不告急
    med(3, '雷贝拉唑钠', status='paused'),
    med(4, '枸橼酸铋钾', status='stopped'),
    med(5, '奥美拉唑', startDate='2026-10-28'),          # 未开始
]
HABITS = [{'id': 'h_med', 'name': '用药', 'icon': '💊', 'type': 'build', 'target': 1, 'unit': '次',
           'color': '#2f6f5e', 'note': '', 'createdAt': '2026-10-01T00:00:00Z', 'pinned': True, 'med': True, 'archivedAt': ''}]

board = {'data': {'version': 2, 'view': 'meds', 'habits': HABITS, 'checks': {},
                  'notes': {}, 'moods': {}, 'events': [], 'meds': MEDS,
                  'doses': {D: {'m1': {'08:00': 1}}},
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
            elif a in ('save', 'force'):
                board['data'] = body['data']; board['rev'] += 1; self._j({'ok': True, 'rev': board['rev']})
            else: self._j({'ok': False, 'error': '?'}, 404)
        else: self.send_response(405); self.end_headers()

class TS(socketserver.ThreadingMixIn, http.server.HTTPServer): daemon_threads = True
srv = TS(('127.0.0.1', PORT), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()

results = []
def rec(name, ok, detail=''):
    results.append((name, ok, detail))
    print(('PASS  ' if ok else 'FAIL  ') + name + (('  | ' + str(detail)) if detail else ''))

STATS = """() => {
  const cards = [...document.querySelectorAll('.med-stats .ms-card')];
  return {
    n: cards.length,
    items: cards.map(c => ({
      label: (c.querySelector('small') || {}).textContent || '',
      value: (c.querySelector('b') || {}).textContent || '',
      sub: (c.querySelector('.ms-sub') || {}).textContent || '',
      warn: c.classList.contains('warn'),
      bar: c.querySelector('.ms-bar i') ? c.querySelector('.ms-bar i').style.width : ''
    })),
    groups: document.querySelectorAll('.med-group').length,
    ovf: document.documentElement.scrollWidth - innerWidth
  };
}"""

def open_page(br, w=1440, h=980, mobile=False):
    kw = {'viewport': {'width': w, 'height': h}}
    if mobile: kw.update({'is_mobile': True, 'has_touch': True, 'device_scale_factor': 2})
    ctx = br.new_context(**kw)
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.clock.install(time=datetime(2026, 10, 24, 13, 0, 0))
    pg.add_init_script("try{localStorage.setItem('lifeboard.layout','top');localStorage.setItem('lifeboard.skin','paper');localStorage.setItem('lifeboard.theme.mode','light')}catch(e){}")
    pg.goto('http://127.0.0.1:%d/index.html' % PORT, wait_until='networkidle')
    pg.wait_for_timeout(700)
    pg.click('[data-act="cloud-login"]'); pg.wait_for_timeout(500)
    pg.fill('input[name="email"]', USER['email']); pg.fill('input[name="password"]', '12345678')
    pg.click('form.modal-card button[type="submit"]')
    pg.wait_for_timeout(2500)
    pg.evaluate("""() => { const b = document.querySelector('.nav-item[data-nav="meds"]'); if (b) b.click(); }""")
    pg.wait_for_timeout(900)
    return ctx, pg, errs

with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)

    ctx, pg, errs = open_page(br)
    s = pg.evaluate(STATS)
    rec('统计卡 6 张', s['n'] == 6, '%d 张' % s['n'])
    rec('药品总数 5 种', s['items'][0]['value'] == '5种', s['items'][0]['value'])
    rec('进行中 2 种 + 未开始提示', s['items'][1]['value'] == '2种' and '另有 1 种未开始' in s['items'][1]['sub'], s['items'][1]['value'] + ' | ' + s['items'][1]['sub'])
    rec('已暂停 1 种', s['items'][2]['value'] == '1种', s['items'][2]['value'])
    rec('已停用 1 种', s['items'][3]['value'] == '1种', s['items'][3]['value'])
    rec('今日服药 1 / 4', s['items'][4]['value'] == '1 / 4', s['items'][4]['value'])
    rec('今日进度条约 25%', s['items'][4]['bar'] == '25%', s['items'][4]['bar'])
    rec('库存告急 1 种并标暖色', s['items'][5]['value'] == '1种' and s['items'][5]['warn'], s['items'][5]['value'] + ' warn=' + str(s['items'][5]['warn']))
    rec('告急卡副文案', s['items'][5]['sub'] == '7 天内会吃完', s['items'][5]['sub'])
    rec('原有四个分组仍在', s['groups'] == 4, '%d 组' % s['groups'])
    rec('无 JS 异常', not errs, str(errs[:2]))
    pg.screenshot(path='design/shots/med-stats.png')
    ctx.close()

    # ---------- 无告急 ----------
    board['data']['meds'] = [MEDS[1], MEDS[2], MEDS[3], MEDS[4]]
    ctx, pg, errs = open_page(br)
    s = pg.evaluate(STATS)
    rec('[无告急] 库存卡显示 0 且不标暖色', s['items'][5]['value'] == '0种' and not s['items'][5]['warn'], s['items'][5]['value'])
    rec('[无告急] 副文案改为都在 7 天以上', s['items'][5]['sub'] == '都在 7 天以上', s['items'][5]['sub'])
    ctx.close()

    # ---------- 空态 ----------
    board['data']['meds'] = []
    ctx, pg, errs = open_page(br)
    s = pg.evaluate(STATS)
    rec('[空态] 不渲染统计卡', s['n'] == 0, '%d 张' % s['n'])
    ctx.close()

    # ---------- 手机 ----------
    board['data']['meds'] = MEDS
    for wd in (390, 360):
        ctx, pg, errs = open_page(br, w=wd, h=844, mobile=True)
        s = pg.evaluate(STATS)
        rec('[手机 %d] 无横向溢出' % wd, s['ovf'] <= 1, 'ovf=%d' % s['ovf'])
        rec('[手机 %d] 6 张卡仍在' % wd, s['n'] == 6, '%d 张' % s['n'])
        rec('[手机 %d] 无 JS 异常' % wd, not errs, str(errs[:1]))
        if wd == 390:
            pg.screenshot(path='design/shots/med-stats-mobile.png')
        ctx.close()

    br.close()

srv.shutdown()
ok = sum(1 for r in results if r[1])
print('\n用药统计卡验证：%d/%d 通过' % (ok, len(results)))
if ok != len(results):
    print('失败项：')
    for n, o, d in results:
        if not o: print('  -', n, '|', d)
    sys.exit(1)
