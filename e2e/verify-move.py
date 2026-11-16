"""运动卡（周视图 + 七段环）验证：3/7 填充色 / 连续 / 本月 / 上次 / 习惯时刻 / 完成态"""
import http.server, threading, json, socketserver, secrets, sys
from datetime import datetime
from playwright.sync_api import sync_playwright

DOC = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo'
USER = {'id': 1, 'email': 'test@example.com', 'display_name': '测试', 'is_admin': False}
sessions = {}
PORT = 38551
D = '2026-10-24'
NOW = datetime(2026, 10, 24, 13, 0, 0)

OTHER = [
    {'id': 'h_med', 'name': '用药', 'icon': '💊', 'type': 'build', 'target': 1, 'unit': '次',
     'color': '#2f6f5e', 'note': '', 'createdAt': '2026-10-01T00:00:00Z', 'pinned': True, 'med': True, 'archivedAt': ''},
    {'id': 'h_water', 'name': '喝水', 'icon': '💧', 'type': 'build', 'target': 9, 'unit': '杯',
     'color': '#4c7f96', 'note': '', 'perMl': 250, 'goalMl': 2300, 'createdAt': '2026-10-01T00:00:00Z', 'pinned': True, 'archivedAt': ''},
    {'id': 'h_breathe', 'name': '478呼吸法', 'icon': '🌬️', 'type': 'build', 'target': 1, 'unit': '次',
     'color': '#5b8f8a', 'note': '', 'createdAt': '2026-10-01T00:00:00Z', 'pinned': True, 'optional': True, 'archivedAt': ''},
]
MOVE = {'id': 'h_move', 'name': '运动', 'icon': '🏃', 'type': 'build', 'target': 1, 'unit': '次',
        'color': '#b5733f', 'note': '', 'createdAt': '2026-10-01T00:00:00Z', 'pinned': True, 'archivedAt': ''}

# 本月 12 天；本周（10-19 ~ 10-25）完成 10-20 / 10-22 / 10-23 = 3 天；上周 4 天
MOVE_DAYS = ['2026-10-02', '2026-10-05', '2026-10-07', '2026-10-08', '2026-10-11', '2026-10-13',
             '2026-10-15', '2026-10-17', '2026-10-18', '2026-10-20', '2026-10-22', '2026-10-23']
EV_TIMES = ['19:00', '19:40', '19:20']

def make_board(extra_today=False, ev=True):
    checks = {}
    for ds in MOVE_DAYS:
        checks[ds] = {'h_move': 1}
    if extra_today:
        checks[D] = {'h_move': 1}
    events = []
    if ev:
        events = [{'id': 'h_move', 'd': ds, 'delta': 1, 'at': ds + 'T' + EV_TIMES[i % 3] + ':00'}
                  for i, ds in enumerate(MOVE_DAYS[-3:])]
    data = {'version': 2, 'view': 'today',
            'habits': [MOVE] + OTHER,
            'checks': checks, 'notes': {}, 'moods': {}, 'events': events, 'meds': [], 'doses': {},
            'bodyProfile': {'age': 30, 'height': 170}, 'weights': [], 'essays': [], 'tasks': []}
    return {'data': data, 'rev': 5}

board = make_board()
save_count = {'n': 0}

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
            elif a == 'save':
                save_count['n'] += 1
                if int(body.get('base_rev', 0)) == board['rev']:
                    board['data'] = body['data']; board['rev'] += 1
                    self._j({'ok': True, 'rev': board['rev']})
                else:
                    self._j({'ok': False, 'code': 'conflict', 'remote': {'data': board['data'], 'rev': board['rev']}}, 409)
            elif a == 'force':
                save_count['n'] += 1
                board['data'] = body['data']; board['rev'] += 1
                self._j({'ok': True, 'rev': board['rev']})
            else: self._j({'ok': False, 'error': '?'}, 404)
        else: self.send_response(405); self.end_headers()

class TS(socketserver.ThreadingMixIn, http.server.HTTPServer): daemon_threads = True
srv = TS(('127.0.0.1', PORT), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()

results = []
def rec(name, ok, detail=''):
    results.append((name, ok, detail))
    print(('PASS  ' if ok else 'FAIL  ') + name + (('  | ' + str(detail)) if detail else ''))

MOVE_JS = """() => {
  const card = document.querySelector('.vital-card.move-card');
  if (!card) return null;
  const q = s => card.querySelector(s);
  const circles = [...card.querySelectorAll('.move-ring circle')];
  const stroke = c => getComputedStyle(c).stroke;
  return {
    hasCard: true,
    circles: circles.length,
    doneN: circles.filter(c => c.classList.contains('done')).length,
    futureN: circles.filter(c => c.classList.contains('future')).length,
    doneStroke: circles.filter(c => c.classList.contains('done')).map(stroke)[0] || '',
    idleStroke: circles.filter(c => !c.classList.contains('done') && !c.classList.contains('future')).map(stroke)[0] || '',
    ratio: (q('.move-ring-txt b') || {}).textContent || '',
    status: (q('.mv-status') || {}).textContent || '',
    sub: (q('.vital-sub') || {}).textContent || '',
    lines: [...card.querySelectorAll('.move-lines span')].map(e => e.textContent.trim()),
    foot: (q('.move-foot') || {}).textContent || '',
    small: (q('.vital-title small') || {}).textContent || '',
    acts: [...card.querySelectorAll('.vital-actions button')].map(b => b.textContent.trim()),
    done: card.classList.contains('is-done'),
    ringW: Math.round(q('.move-ring').getBoundingClientRect().width),
    ovf: document.documentElement.scrollWidth - innerWidth
  };
}"""

def open_page(br, w=1440, h=950, mobile=False):
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
    pg.wait_for_timeout(2600)
    return ctx, pg, errs

with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)

    # ---------- 3/7 未完成 ----------
    board.update(make_board())
    ctx, pg, errs = open_page(br)
    m = pg.evaluate(MOVE_JS)
    rec('运动卡渲染', m and m['hasCard'], '')
    rec('环共 7 段', m['circles'] == 7, '%d 段' % m['circles'])
    rec('已完成 3 段有色', m['doneN'] == 3, '%d 段' % m['doneN'])
    rec('完成段用的是主题陶土色', m['doneStroke'] not in ('', 'none') and m['doneStroke'] != m['idleStroke'],
        'done=%s idle=%s' % (m['doneStroke'], m['idleStroke']))
    rec('未来 1 段（周日）', m['futureN'] == 1, '%d 段' % m['futureN'])
    rec('中间显示 3/7', m['ratio'] == '3/7', m['ratio'])
    rec('状态「还没开始」', m['status'] == '还没开始', m['status'])
    rec('习惯时刻来自 events（19:20）', '19:20 左右' in m['sub'], m['sub'])
    rec('连续 2 天 · 本月 12 天', '连续 2 天' in m['lines'][0] and '本月 12 天' in m['lines'][0], str(m['lines']))
    rec('上次 昨天', len(m['lines']) > 1 and m['lines'][1] == '上次 昨天', str(m['lines']))
    rec('底部追平提示', '距本周结束还有 1 天' in m['foot'] and '再动 1 次就追平上周' in m['foot'], m['foot'])
    rec('副标题写明目标步数', '10,000 步' in m['small'], m['small'])
    rec('按钮为完成运动 + 撤销', m['acts'] == ['完成运动', '撤销'], str(m['acts']))
    rec('环宽 132', m['ringW'] == 132, '%dpx' % m['ringW'])
    pg.screenshot(path='design/shots/move-3.png')

    # 点完成运动
    base = save_count['n']
    pg.click('[data-act="habit-inc"][data-id="h_move"]'); pg.wait_for_timeout(1200)
    m2 = pg.evaluate(MOVE_JS)
    rec('点完成后变 4/7', m2['ratio'] == '4/7' and m2['doneN'] == 4, m2['ratio'] + ' / %d 段' % m2['doneN'])
    rec('完成态文案与按钮', m2['done'] and m2['acts'] == ['已完成 · 点击可撤销'], str(m2['acts']))
    rec('打卡写入云端 1 次', save_count['n'] == base + 1, '%d → %d' % (base, save_count['n']))
    pg.click('[data-act="habit-dec"][data-id="h_move"]'); pg.wait_for_timeout(1200)
    rec('撤销回到 3/7', pg.evaluate(MOVE_JS)['ratio'] == '3/7', '')
    rec('无 JS 异常', not errs, str(errs[:2]))
    ctx.close()

    # ---------- 无 events：不猜测时刻 ----------
    board.update(make_board(ev=False))
    ctx, pg, errs = open_page(br)
    m = pg.evaluate(MOVE_JS)
    rec('样本不足时不说「你通常…」', '你通常' not in m['sub'], m['sub'])
    ctx.close()

    # ---------- 本月只有少量记录 ----------
    board.update(make_board())
    board['data']['checks'] = {'2026-10-23': {'h_move': 1}}
    ctx, pg, errs = open_page(br)
    m = pg.evaluate(MOVE_JS)
    rec('[仅1天] 1/7 且连续 1 天', m['ratio'] == '1/7' and '连续 1 天' in m['lines'][0], m['ratio'] + ' ' + str(m['lines']))
    ctx.close()

    # ---------- 手机 ----------
    board.update(make_board())
    for wd in (390, 360):
        ctx, pg, errs = open_page(br, w=wd, h=844, mobile=True)
        m = pg.evaluate(MOVE_JS)
        rec('[手机 %d] 无横向溢出' % wd, m['ovf'] <= 1, 'ovf=%d' % m['ovf'])
        rec('[手机 %d] 环缩小到 104' % wd, m['ringW'] == 104, '%dpx' % m['ringW'])
        rec('[手机 %d] 7 段仍在' % wd, m['circles'] == 7, '%d 段' % m['circles'])
        rec('[手机 %d] 无 JS 异常' % wd, not errs, str(errs[:1]))
        if wd == 390:
            pg.screenshot(path='design/shots/move-mobile.png')
        ctx.close()

    br.close()

srv.shutdown()
ok = sum(1 for r in results if r[1])
print('\n运动卡验证：%d/%d 通过' % (ok, len(results)))
if ok != len(results):
    print('失败项：')
    for n, o, d in results:
        if not o: print('  -', n, '|', d)
    sys.exit(1)
