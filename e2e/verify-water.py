"""喝水卡 v18.1 验证：近 7 天迷你柱 / 24 小时分布条 / 节奏建议 / 时间戳合并 / 刚刚"""
import http.server, threading, json, socketserver, secrets, sys
from datetime import datetime
from playwright.sync_api import sync_playwright

DOC = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo'
USER = {'id': 1, 'email': 'test@example.com', 'display_name': '测试', 'is_admin': False}
sessions = {}
PORT = 38550
D = '2026-10-24'
NOW = datetime(2026, 10, 24, 13, 0, 0)

def water_habit(**kw):
    h = {'id': 'h_water', 'name': '喝水', 'icon': '💧', 'type': 'build', 'target': 9, 'unit': '杯',
         'color': '#4c7f96', 'note': '每天 9 杯 · 共 2300 ml', 'perMl': 250, 'goalMl': 2300,
         'createdAt': '2026-10-23T00:00:00Z', 'pinned': True, 'archivedAt': ''}
    h.update(kw)
    return h

OTHER = [
    {'id': 'h_med', 'name': '用药', 'icon': '💊', 'type': 'build', 'target': 1, 'unit': '次',
     'color': '#2f6f5e', 'note': '', 'createdAt': '2026-10-23T00:00:00Z', 'pinned': True, 'med': True, 'archivedAt': ''},
    {'id': 'h_move', 'name': '运动', 'icon': '🏃', 'type': 'build', 'target': 1, 'unit': '次',
     'color': '#b5733f', 'note': '', 'createdAt': '2026-10-23T00:00:00Z', 'pinned': True, 'archivedAt': ''},
    {'id': 'h_breathe', 'name': '478呼吸法', 'icon': '🌬️', 'type': 'build', 'target': 1, 'unit': '次',
     'color': '#5b8f8a', 'note': '', 'createdAt': '2026-10-23T00:00:00Z', 'pinned': True, 'optional': True, 'archivedAt': ''},
]

def ev(times):
    return [{'id': 'h_water', 'd': D, 'delta': 1, 'at': D + 'T' + t + ':00'} for t in times]

def make_board(count=0, times=(), habit=None, checks_extra=None):
    checks = {}
    if count:
        checks[D] = {'h_water': count}
    if checks_extra:
        for k, v in checks_extra.items():
            checks.setdefault(k, {})['h_water'] = v
    data = {'version': 2, 'view': 'today',
            'habits': [habit or water_habit()] + OTHER,
            'checks': checks, 'notes': {}, 'moods': {}, 'events': ev(times), 'meds': [], 'doses': {},
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
        else:
            self.send_response(405); self.end_headers()

class TS(socketserver.ThreadingMixIn, http.server.HTTPServer): daemon_threads = True
srv = TS(('127.0.0.1', PORT), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()

results = []
def rec(name, ok, detail=''):
    results.append((name, ok, detail))
    print(('PASS  ' if ok else 'FAIL  ') + name + (('  | ' + str(detail)) if detail else ''))

WATER = """() => {
  const card = [...document.querySelectorAll('.vital-card')].find(c => c.querySelector('[data-id="h_water"]'));
  if (!card) return null;
  const q = s => card.querySelector(s);
  const st = [...card.querySelectorAll('.water-steps i')];
  const ww = [...card.querySelectorAll('.ww-bars i')];
  const dots = [...card.querySelectorAll('.wd-track i')];
  return {
    num: (q('.vnum') || {}).textContent || '',
    unit: (q('.vunit') || {}).textContent || '',
    small: (q('.vital-title small') || {}).textContent || '',
    sub: (q('.vital-sub') || {}).textContent || '',
    steps: st.length,
    on: st.filter(i => i.classList.contains('on')).length,
    cur: st.filter(i => i.classList.contains('cur')).length,
    gap: (q('.water-gap') || {}).textContent || '',
    need: !!q('.water-gap.need'),
    weekBars: ww.length,
    weekHas: ww.filter(i => i.classList.contains('has')).length,
    weekToday: ww.filter(i => i.classList.contains('is-today')).length,
    weekAvg: (q('.ww-avg') || {}).textContent.replace(/\\s+/g, ' ').trim(),
    weekHidden: !q('.water-week') || q('.water-week').getClientRects().length === 0,
    dots: dots.length,
    dotTitles: dots.map(i => i.getAttribute('title')),
    dotLefts: dots.map(i => Math.round(parseFloat(i.style.left))),
    ticks: [...card.querySelectorAll('.wd-axis span')].map(e => e.textContent),
    tickLefts: [...card.querySelectorAll('.wd-axis span')].map(e => Math.round(parseFloat(e.style.left))),
    pace: (q('.water-pace') || {}).textContent || '',
    acts: [...card.querySelectorAll('.vital-actions button')].map(b => b.textContent.trim()),
    done: card.classList.contains('is-done'),
    h: Math.round(card.getBoundingClientRect().height),
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

    # ---------- 3 杯 + 3 天历史 ----------
    board.update(make_board(3, ['08:12', '09:40', '11:06'],
                            checks_extra={'2026-10-22': 6, '2026-10-23': 9}))
    ctx, pg, errs = open_page(br)
    w = pg.evaluate(WATER)
    rec('主数字 750 / 2300 ml', w['num'] == '750' and w['unit'].strip() == '/ 2300 ml', w['num'] + w['unit'])
    rec('九格：3 实心 + 1 当前', w['steps'] == 9 and w['on'] == 3 and w['cur'] == 1, '%d/%d/%d' % (w['steps'], w['on'], w['cur']))
    rec('超 90 分钟 → 该喝水了', w['need'] and '该喝水了' in w['gap'], w['gap'])

    # A 近 7 天迷你柱
    rec('右上 7 根柱', w['weekBars'] == 7, '%d 根' % w['weekBars'])
    rec('有数据的柱 3 根（2 天历史 + 今天）', w['weekHas'] == 3, '%d 根' % w['weekHas'])
    rec('今天那根高亮', w['weekToday'] == 1, '%d 根' % w['weekToday'])
    rec('均量只算前 6 天（1500+2300）/6=633', '633' in w['weekAvg'], w['weekAvg'])

    # B 分布条
    rec('分布条 3 个点', w['dots'] == 3, '%d 个' % w['dots'])
    rec('点的时刻正确', w['dotTitles'] == ['08:12', '09:40', '11:06'], str(w['dotTitles']))
    rec('刻度 6 个且位置递增', w['ticks'] == ['06', '09', '12', '15', '18', '21'] and w['tickLefts'] == sorted(w['tickLefts']), str(w['ticks']) + str(w['tickLefts']))
    rec('08:12 落在 13% 附近', 10 <= w['dotLefts'][0] <= 16, '%d%%' % w['dotLefts'][0])

    # C 节奏建议
    rec('节奏建议：离 22:00 还有 9 小时 · 还差 6 杯 · 每 90 分钟', w['pace'].startswith('离 22:00 还有 9 小时') and '还差 6 杯' in w['pace'] and '90 分钟一杯' in w['pace'], w['pace'])
    rec('按钮写明一杯 250 ml', w['acts'][0] == '＋ 一杯 250 ml', str(w['acts']))
    rec('卡片高度未失控', w['h'] < 420, '%dpx' % w['h'])
    pg.screenshot(path='design/shots/water-3.png')

    # 点一杯 → 1000
    base = save_count['n']
    pg.click('[data-act="habit-inc"][data-id="h_water"]'); pg.wait_for_timeout(1100)
    w2 = pg.evaluate(WATER)
    rec('点一杯 → 1000 ml', w2['num'] == '1000', w2['num'])
    rec('打卡写入云端 1 次', save_count['n'] == base + 1, '%d → %d' % (base, save_count['n']))
    pg.click('[data-act="habit-dec"][data-id="h_water"]'); pg.wait_for_timeout(1100)
    rec('撤销 → 回到 750 ml', pg.evaluate(WATER)['num'] == '750', '')
    rec('无 JS 异常', not errs, str(errs[:2]))
    ctx.close()

    # ---------- 连点合并：8 次都在 14:45 ----------
    board.update(make_board(8, ['14:45'] * 8))
    ctx, pg, errs = open_page(br)
    w = pg.evaluate(WATER)
    rec('[合并] 8 次同分钟 → 分布条 1 个点', w['dots'] == 1, '%d 个' % w['dots'])
    rec('[合并] 标为 14:45 ×8', w['dotTitles'] == ['14:45 ×8'], str(w['dotTitles']))
    rec('[合并] 主数字仍为 2000', w['num'] == '2000', w['num'])
    rec('[合并] 第 9 格待喝 + 最后一杯按钮', w['on'] == 8 and w['cur'] == 1 and w['acts'][0] == '＋ 最后一杯 300 ml', str(w['acts']))
    pg.screenshot(path='design/shots/water-8.png')
    ctx.close()

    # ---------- 刚刚 ----------
    board.update(make_board(3, ['08:12', '09:40', '13:00']))
    ctx, pg, errs = open_page(br)
    w = pg.evaluate(WATER)
    rec('[刚刚] 0 分钟不显示 0 分钟', w['gap'] == '上次 13:00 · 已隔 刚刚', w['gap'])
    ctx.close()

    # ---------- 45 分钟 ----------
    board.update(make_board(3, ['08:12', '09:40', '12:15']))
    ctx, pg, errs = open_page(br)
    w = pg.evaluate(WATER)
    rec('[45分钟] 不提示该喝水', not w['need'], w['gap'])
    rec('[45分钟] 上次 12:15 · 已隔 45 分钟', w['gap'] == '上次 12:15 · 已隔 45 分钟', w['gap'])
    ctx.close()

    # ---------- 完成态 ----------
    board.update(make_board(9, ['07:30', '08:40', '09:50', '11:00', '12:10', '12:20', '12:30', '12:40', '12:50']))
    ctx, pg, errs = open_page(br)
    w = pg.evaluate(WATER)
    rec('[完成] 2300 ml / 九格全满 / 完成态', w['num'] == '2300' and w['on'] == 9 and w['done'], w['num'])
    rec('[完成] 不再显示节奏建议', w['pace'] == '', w['pace'])
    pg.screenshot(path='design/shots/water-done.png')
    ctx.close()

    # ---------- 过 22:00 ----------
    board.update(make_board(3, ['08:12', '09:40', '21:30']))
    ctx, pg, errs = open_page(br)
    pg.clock.install(time=datetime(2026, 10, 24, 22, 40, 0))
    pg.reload(wait_until='networkidle'); pg.wait_for_timeout(1800)
    w = pg.evaluate(WATER)
    rec('[22:40] 提示已过 22:00', '已经过了 22:00' in w['pace'], w['pace'])
    ctx.close()

    # ---------- 旧数据迁移 ----------
    board.update(make_board(4, ['09:00', '10:30', '12:00', '12:40'], habit=water_habit(target=8, note='一天 8 杯')))
    for h in board['data']['habits']:
        if h['id'] == 'h_water':
            h.pop('perMl', None); h.pop('goalMl', None)
    ctx, pg, errs = open_page(br)
    w = pg.evaluate(WATER)
    rec('[迁移] 9 杯 / 2300 / 9 格', '每天 9 杯 · 共 2300 ml' == w['small'].strip() and w['steps'] == 9, w['small'])
    rec('[迁移] 历史 4 次 = 1000 ml', w['num'] == '1000', w['num'])
    ctx.close()

    # ---------- 手机 ----------
    board.update(make_board(5, ['08:12', '09:40', '10:50', '11:30', '12:55']))
    for wd in (390, 360):
        ctx, pg, errs = open_page(br, w=wd, h=844, mobile=True)
        w = pg.evaluate(WATER)
        rec('[手机 %d] 无横向溢出' % wd, w['ovf'] <= 1, 'ovf=%d' % w['ovf'])
        rec('[手机 %d] 九格完整 + 分布条可见' % wd, w['steps'] == 9 and w['dots'] == 5, '%d / %d' % (w['steps'], w['dots']))
        rec('[手机 %d] 7 天柱收起不挤' % wd, w['weekHidden'], 'hidden=%s' % w['weekHidden'])
        rec('[手机 %d] 无 JS 异常' % wd, not errs, str(errs[:1]))
        if wd == 390:
            pg.screenshot(path='design/shots/water-mobile.png')
        ctx.close()

    br.close()

srv.shutdown()
ok = sum(1 for r in results if r[1])
print('\n喝水卡 v18.1 验证：%d/%d 通过' % (ok, len(results)))
if ok != len(results):
    print('失败项：')
    for n, o, d in results:
        if not o: print('  -', n, '|', d)
    sys.exit(1)
