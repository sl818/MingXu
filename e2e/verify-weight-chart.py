"""体重折线图 + 统计面板验证：健康区间 / 范围切换 / 空态 / 单条 / 手机"""
import http.server, threading, json, socketserver, secrets, sys
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright

DOC = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo'
USER = {'id': 1, 'email': 'test@sl00.top', 'display_name': '测试', 'is_admin': False}
sessions = {}
PORT = 38558
D = '2026-10-24'
NOW = datetime(2026, 10, 24, 17, 0, 0)
H = 170

def bmi_of(w):
    return round(w / ((H / 100) ** 2), 1)

def recs(pairs):
    out = []
    for i, (date, w) in enumerate(pairs):
        out.append({'id': 'w%d' % i, 'date': date, 'weight': w, 'height': H, 'age': 23,
                    'bmi': bmi_of(w), 'createdAt': date + 'T08:00:00Z'})
    return out

# 10 条：90 天内逐步从 72.5 降到 68.3
TEN = recs([
    ('2026-07-28', 72.5), ('2026-08-06', 72.1), ('2026-08-15', 71.4), ('2026-08-24', 70.8),
    ('2026-09-02', 70.5), ('2026-09-14', 69.9), ('2026-09-26', 69.4), ('2026-10-08', 68.9),
    ('2026-10-16', 68.6), ('2026-10-23', 68.3),
])

def make_board(weights):
    return {'data': {'version': 2, 'view': 'weight',
                     'habits': [{'id': 'h_med', 'name': '用药', 'icon': '💊', 'type': 'build', 'target': 1, 'unit': '次',
                                 'color': '#2f6f5e', 'note': '', 'createdAt': '2026-10-01T00:00:00Z', 'pinned': True, 'med': True, 'archivedAt': ''}],
                     'checks': {}, 'notes': {}, 'moods': {}, 'events': [], 'meds': [], 'doses': {},
                     'bodyProfile': {'age': 23, 'height': H}, 'weights': weights, 'essays': [], 'tasks': []}, 'rev': 5}

board = make_board(TEN)

class Hd(http.server.SimpleHTTPRequestHandler):
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
srv = TS(('127.0.0.1', PORT), Hd)
threading.Thread(target=srv.serve_forever, daemon=True).start()

results = []
def rec(name, ok, detail=''):
    results.append((name, ok, detail))
    print(('PASS  ' if ok else 'FAIL  ') + name + (('  | ' + str(detail)) if detail else ''))

CHART = """() => {
  const svg = document.querySelector('.ww-svg');
  const band = document.querySelector('.ww-lbl-band');
  const rows = [...document.querySelectorAll('.wsum-row')];
  const sw = [...document.querySelectorAll('.range-switch button')];
  return {
    hasSvg: !!svg,
    dots: svg ? svg.querySelectorAll('.ww-dot').length : 0,
    pathD: svg && svg.querySelector('.ww-line') ? svg.querySelector('.ww-line').getAttribute('d') : '',
    band: (document.querySelector('.cal-hint') || {}).textContent || '',
    bandRect: !!document.querySelector('.ww-band'),
    rows: rows.map(r => (r.querySelector('small') || {}).textContent + ' = ' + (r.querySelector('b') || {}).textContent),
    switch: sw.map(b => b.textContent + (b.classList.contains('active') ? '*' : '')),
    empty: (document.querySelector('.ww-empty') || {}).textContent || '',
    emptyCount: document.querySelectorAll('.ww-empty').length,
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
    pg.clock.install(time=NOW)
    pg.add_init_script("try{localStorage.setItem('lifeboard.layout','top');localStorage.setItem('lifeboard.skin','paper');localStorage.setItem('lifeboard.theme.mode','light')}catch(e){}")
    pg.goto('http://127.0.0.1:%d/index.html' % PORT, wait_until='networkidle')
    pg.wait_for_timeout(700)
    pg.click('[data-act="cloud-login"]'); pg.wait_for_timeout(500)
    pg.fill('input[name="email"]', USER['email']); pg.fill('input[name="password"]', '12345678')
    pg.click('form.modal-card button[type="submit"]')
    pg.wait_for_timeout(2500)
    pg.evaluate("""() => { const b = document.querySelector('.nav-item[data-nav="weight"]'); if (b) b.click(); }""")
    pg.wait_for_timeout(900)
    return ctx, pg, errs

with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)

    # ---------- 10 条记录 ----------
    board.update(make_board(TEN))
    ctx, pg, errs = open_page(br)
    c = pg.evaluate(CHART)
    rec('折线图渲染', c['hasSvg'], '')
    rec('默认全部区间 → 10 个点', c['dots'] == 10, '%d 个' % c['dots'])
    rec('折线包含 10 段坐标', c['pathD'].count('L') == 9, '%d 段 L' % c['pathD'].count('L'))
    rec('画出健康区间带', c['bandRect'], '')
    rec('健康区间说明写到 53.5–69.1', '53.5' in c['band'] and '69.1' in c['band'], c['band'])
    rec('统计 6 行', len(c['rows']) == 6, str(len(c['rows'])))
    rec('起始 → 当前 72.5 → 68.3', any('72.5 → 68.3' in r for r in c['rows']), str(c['rows'][:1]))
    rec('区间变化 ↓ 4.2 kg', any('4.2' in r and '↓' in r for r in c['rows']), str([r for r in c['rows'] if '变化' in r]))
    rec('最高 / 最低 72.5 / 68.3', any('72.5 / 68.3' in r for r in c['rows']), str([r for r in c['rows'] if '最高' in r]))
    rec('四档切换且全部高亮', c['switch'] == ['7 天', '30 天', '90 天', '全部*'], str(c['switch']))
    pg.screenshot(path='design/shots/weight-chart-all.png')

    # 切到 7 天
    pg.click('.range-switch button[data-range="7"]'); pg.wait_for_timeout(600)
    c7 = pg.evaluate(CHART)
    rec('[7天] 只剩 1 条（10-23）', c7['dots'] == 1, '%d 个' % c7['dots'])
    rec('[7天] 统计跟着变（单条持平）', any('68.3 → 68.3' in r for r in c7['rows']), str(c7['rows'][:1]))
    rec('[7天] 按钮高亮切到 7 天', '7 天*' in c7['switch'], str(c7['switch']))
    pg.screenshot(path='design/shots/weight-chart-7.png')

    # 切到 30 天
    pg.click('.range-switch button[data-range="30"]'); pg.wait_for_timeout(600)
    c30 = pg.evaluate(CHART)
    rec('[30天] 4 个点', c30['dots'] == 4, '%d 个' % c30['dots'])

    pg.click('.range-switch button[data-range="0"]'); pg.wait_for_timeout(600)
    rec('[全部] 回到 10 个点', pg.evaluate(CHART)['dots'] == 10, '')
    rec('无 JS 异常', not errs, str(errs[:2]))
    ctx.close()

    # ---------- 单条记录 ----------
    board.update(make_board(TEN[-1:]))
    ctx, pg, errs = open_page(br)
    c = pg.evaluate(CHART)
    rec('[单条] 1 个点', c['dots'] == 1, '%d 个' % c['dots'])
    rec('[单条] 不画折线（只有 M）', c['pathD'].count('L') == 0, c['pathD'][:30])
    rec('[单条] 统计仍是 6 行', len(c['rows']) == 6, str(len(c['rows'])))
    pg.screenshot(path='design/shots/weight-chart-one.png')
    ctx.close()

    # ---------- 空态 ----------
    board.update(make_board([]))
    ctx, pg, errs = open_page(br)
    c = pg.evaluate(CHART)
    rec('[空态] 无 SVG，显示引导', not c['hasSvg'] and '还没有体重记录' in c['empty'], c['empty'][:20])
    rec('[空态] 图表区与统计区都有占位', c['emptyCount'] == 2, '%d 个 ww-empty' % c['emptyCount'])
    pg.screenshot(path='design/shots/weight-chart-empty.png')
    ctx.close()

    # ---------- 手机 ----------
    board.update(make_board(TEN))
    for wd in (390, 360):
        ctx, pg, errs = open_page(br, w=wd, h=844, mobile=True)
        c = pg.evaluate(CHART)
        rec('[手机 %d] 无横向溢出' % wd, c['ovf'] <= 1, 'ovf=%d' % c['ovf'])
        rec('[手机 %d] 折线与 10 个点仍在' % wd, c['dots'] == 10, '%d 个' % c['dots'])
        rec('[手机 %d] 无 JS 异常' % wd, not errs, str(errs[:1]))
        if wd == 390:
            pg.screenshot(path='design/shots/weight-chart-mobile.png')
        ctx.close()

    br.close()

srv.shutdown()
ok = sum(1 for r in results if r[1])
print('\n体重图表验证：%d/%d 通过' % (ok, len(results)))
if ok != len(results):
    print('失败项：')
    for n, o, d in results:
        if not o: print('  -', n, '|', d)
    sys.exit(1)
