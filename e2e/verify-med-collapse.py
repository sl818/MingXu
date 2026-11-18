"""用药卡折叠 + 四卡等高 + A2 按钮 + 弹窗刷新 验证"""
import http.server, threading, json, socketserver, secrets, sys
from datetime import datetime
from playwright.sync_api import sync_playwright

DOC = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo'
USER = {'id': 1, 'email': 'test@example.com', 'display_name': '测试', 'is_admin': False}
sessions = {}
D = '2026-10-24'

def mk_med(i, name, dose, unit):
    return {'id': 'm%d' % i, 'name': name, 'purpose': '西药', 'form': '片', 'strength': '',
            'doseAmount': dose, 'doseUnit': unit, 'times': ['08:00', '19:00'],
            'mealTiming': 'after', 'mealOffset': 30, 'courseType': 'short',
            'startDate': '2026-10-20', 'endDate': '2026-11-04', 'reviewDate': '',
            'status': 'active', 'stock': '20', 'note': '', 'manufacturer': '某制药', 'medInfo': ''}

FOUR = [mk_med(1, '阿莫西林', 4, '胶囊'), mk_med(2, '克拉霉素片', 2, '片'),
        mk_med(3, '女奥美拉唑', 1, '片'), mk_med(4, '枸橼酸铋钾', 2, '粒')]
ONE = [mk_med(1, '阿莫西林', 4, '胶囊')]

HABITS = [
    {'id': 'h_med', 'name': '用药', 'icon': '💊', 'type': 'build', 'target': 1, 'unit': '次',
     'color': '#2f6f5e', 'note': '', 'createdAt': '2026-10-23T00:00:00Z', 'pinned': True, 'med': True, 'archivedAt': ''},
    {'id': 'h_water', 'name': '喝水', 'icon': '💧', 'type': 'build', 'target': 8, 'unit': '杯',
     'color': '#4c7f96', 'note': '', 'createdAt': '2026-10-23T00:00:00Z', 'pinned': True, 'archivedAt': ''},
    {'id': 'h_move', 'name': '运动', 'icon': '🏃', 'type': 'build', 'target': 1, 'unit': '次',
     'color': '#b5733f', 'note': '', 'createdAt': '2026-10-23T00:00:00Z', 'pinned': True, 'archivedAt': ''},
    {'id': 'h_breathe', 'name': '478呼吸法', 'icon': '🌬️', 'type': 'build', 'target': 1, 'unit': '次',
     'color': '#5b8f8a', 'note': '', 'createdAt': '2026-10-23T00:00:00Z', 'pinned': True, 'optional': True, 'archivedAt': ''},
]

def make_board(meds):
    return {'data': {
        'version': 2, 'view': 'today', 'habits': HABITS,
        'checks': {D: {'h_water': 5}}, 'notes': {}, 'moods': {}, 'events': [],
        'meds': meds,
        'doses': {D: {m['id']: {'08:00': 1} for m in meds}},
        'bodyProfile': {'age': 30, 'height': 170}, 'weights': [], 'essays': [], 'tasks': []}, 'rev': 5}

board = make_board(FOUR)

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
            elif a == 'save':
                if int(body.get('base_rev', 0)) == board['rev']:
                    board['data'] = body['data']; board['rev'] += 1
                    self._j({'ok': True, 'rev': board['rev']})
                else:
                    self._j({'ok': False, 'code': 'conflict', 'remote': {'data': board['data'], 'rev': board['rev']}}, 409)
            elif a == 'force':
                board['data'] = body['data']; board['rev'] += 1
                self._j({'ok': True, 'rev': board['rev']})
            else: self._j({'ok': False, 'error': '?'}, 404)
        else:
            self.send_response(405); self.end_headers()

class TS(socketserver.ThreadingMixIn, http.server.HTTPServer): daemon_threads = True

srv = TS(('127.0.0.1', 0), H)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()

results = []
def rec(name, ok, detail=''):
    results.append((name, ok, detail))
    print(('PASS  ' if ok else 'FAIL  ') + name + (('  | ' + str(detail)) if detail else ''))

def login(pg):
    pg.clock.install(time=datetime(2026,10,24,10,0,0))
    pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
    pg.wait_for_timeout(700)
    pg.click('[data-act="cloud-login"]'); pg.wait_for_timeout(500)
    pg.fill('input[name="email"]', USER['email']); pg.fill('input[name="password"]', '12345678')
    pg.click('form.modal-card button[type="submit"]')
    pg.wait_for_timeout(2600)

CARD_JS = """() => {
  const q = s => document.querySelector(s), qa = s => [...document.querySelectorAll(s)];
  const card = q('.vital-card.med-card');
  if (!card) return null;
  const btn = qa('.vital-card.med-card .vital-actions button').map(b => ({
    t: b.textContent.trim(), act: b.dataset.act || '', nav: b.dataset.nav || '', dis: b.disabled,
    cls: b.className.replace('vital-btn ', '').trim()
  }));
  const heights = qa('.vital-card').map(c => Math.round(c.getBoundingClientRect().height));
  return {
    lines: qa('.vital-card.med-card .med-line').length,
    carousel: qa('.vital-card.med-card .med-carousel').length,
    pane: (q('.vital-card.med-card .med-pane-top b') || {}).textContent || '',
    more: q('.vital-card.med-card .med-more') ? q('.vital-card.med-card .med-more').textContent.trim() : '',
    names: qa('.vital-card.med-card .med-line-top b').map(e => e.textContent.trim()),
    btns: btn,
    heights: heights,
    sameH: heights.length >= 4 && Math.max(...heights) - Math.min(...heights) <= 1,
    hasList: !!q('.vital-card.med-card .med-today'),
    ovf: document.documentElement.scrollWidth - innerWidth
  };
}"""

SHEET_JS = """() => {
  const s = document.querySelector('#med-sheet');
  if (!s) return null;
  return {items: s.querySelectorAll('.med-item').length,
          doses: s.querySelectorAll('.med-dose').length,
          scrollTop: Math.round(s.scrollTop),
          scrollable: s.scrollHeight > s.clientHeight};
}"""

with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)

    for layout in ('top', 'wide', 'side'):
        board.update(make_board(FOUR))
        ctx = br.new_context(viewport={'width': 1440, 'height': 950})
        pg = ctx.new_page()
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.add_init_script("try{localStorage.setItem('lifeboard.layout','%s');localStorage.setItem('lifeboard.skin','paper');localStorage.setItem('lifeboard.theme.mode','light')}catch(e){}" % layout)
        login(pg)
        m = pg.evaluate(CARD_JS)
        tag = '[%s]' % layout
        rec(tag + ' 四张卡等高', m['sameH'], str(m['heights']))
        rec(tag + ' 卡片改为轮播', m['carousel'] == 1, 'carousel=%d' % m['carousel'])
        rec(tag + ' 不再显示「还有 N 种」提示', m['more'] == '', repr(m['more']))
        rec(tag + ' 轮播默认显示排序第一条', m['pane'] == '阿莫西林', m['pane'])
        prim = [b for b in m['btns'] if 'primary' in b['cls']]
        ghost = [b for b in m['btns'] if 'ghost' in b['cls']]
        rec(tag + ' 主按钮=查看详细(跳用药页)', bool(prim) and prim[0]['t'] == '查看详细' and prim[0]['nav'] == 'meds',
            str(prim))
        rec(tag + ' 次按钮=记录 19:00', bool(ghost) and ghost[0]['t'] == '记录 19:00' and ghost[0]['act'] == 'med-next',
            str(ghost))
        rec(tag + ' 无横向溢出', m['ovf'] <= 1, 'ovf=%d' % m['ovf'])
        if layout == 'top':
            pg.screenshot(path='design/shots/collapse-4meds-top.png')
        if layout == 'wide':
            pg.screenshot(path='design/shots/collapse-4meds-wide.png')

        # ≥2 种药改为跳转用药页（不再是弹窗）
        if layout == 'top':
            pg.click('.vital-card.med-card .vital-actions button[data-nav="meds"]')
            pg.wait_for_timeout(1200)
            jumped = pg.evaluate("() => ({ view: document.body.dataset.view, rows: document.querySelectorAll('.med-row').length })")
            rec('[跳页] 点查看详细进入用药页', jumped['view'] == 'meds', str(jumped))
            rec('[跳页] 用药页列出全部 4 种药', jumped['rows'] == 4, '%d 行' % jumped['rows'])
            pg.screenshot(path='design/shots/collapse-medpage.png', full_page=True)
            # 页内直接打卡
            n_before = pg.evaluate("() => document.querySelectorAll('.med-slot.done').length")
            pg.locator('.med-slot:not(.done):not(.is-static)').first.click(); pg.wait_for_timeout(1300)
            n_after = pg.evaluate("() => document.querySelectorAll('.med-slot.done').length")
            rec('[跳页] 用药页内点胶囊可记录', n_after == n_before + 1, '%d → %d' % (n_before, n_after))
            # 回到今日页确认卡片同步
            pg.click('.nav-item[data-nav="today"]'); pg.wait_for_timeout(1200)
            m2 = pg.evaluate(CARD_JS)
            rec('[卡片] 页内打卡后主按钮仍为查看详细', any(b['t'] == '查看详细' for b in m2['btns']), str(m2['btns']))
        rec(tag + ' 无 JS 异常', len(errs) == 0, str(errs[:2]))
        ctx.close()

    # 只有 1 种药：保持原样
    for layout in ('top', 'wide'):
        board.update(make_board(ONE))
        ctx = br.new_context(viewport={'width': 1440, 'height': 950})
        pg = ctx.new_page()
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.add_init_script("try{localStorage.setItem('lifeboard.layout','%s');localStorage.setItem('lifeboard.skin','paper');localStorage.setItem('lifeboard.theme.mode','light')}catch(e){}" % layout)
        login(pg)
        m = pg.evaluate(CARD_JS)
        tag = '[1种/%s]' % layout
        rec(tag + ' 四张卡等高', m['sameH'], str(m['heights']))
        rec(tag + ' 无折叠提示', m['more'] == '' and m['lines'] == 1, '%d 行 more=%r' % (m['lines'], m['more']))
        rec(tag + ' 主按钮=记录 19:00', m['btns'][0]['t'] == '记录 19:00' and m['btns'][0]['act'] == 'med-next', str(m['btns']))
        rec(tag + ' 次按钮=全部(med-open)', len(m['btns']) > 1 and m['btns'][1]['t'] == '全部' and m['btns'][1]['act'] == 'med-open', str(m['btns']))
        rec(tag + ' 无溢出/无异常', m['ovf'] <= 1 and not errs, 'ovf=%d %s' % (m['ovf'], errs[:1]))
        if layout == 'top':
            pg.screenshot(path='design/shots/collapse-1med.png')
        ctx.close()

    # 没有用药：保持「添加用药」
    board.update(make_board([]))
    ctx = br.new_context(viewport={'width': 1440, 'height': 950})
    pg = ctx.new_page()
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.add_init_script("try{localStorage.setItem('lifeboard.layout','top');localStorage.setItem('lifeboard.skin','paper');localStorage.setItem('lifeboard.theme.mode','light')}catch(e){}")
    login(pg)
    m = pg.evaluate(CARD_JS)
    rec('[0种] 主按钮=添加用药', m['btns'][0]['t'] == '添加用药' and m['btns'][0]['act'] == 'med-new', str(m['btns']))
    rec('[0种] 无用药清单区', not m['hasList'], '')
    rec('[0种] 四张卡等高', m['sameH'], str(m['heights']))
    rec('[0种] 无异常', not errs, str(errs[:1]))
    pg.screenshot(path='design/shots/collapse-0med.png')
    ctx.close()

    # 手机：单列自然高度，不强制等高
    for meds, label in ((FOUR, '4种'), (ONE, '1种')):
        board.update(make_board(meds))
        ctx = br.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True, device_scale_factor=2)
        pg = ctx.new_page()
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.add_init_script("try{localStorage.setItem('lifeboard.layout','top');localStorage.setItem('lifeboard.skin','paper');localStorage.setItem('lifeboard.theme.mode','light')}catch(e){}")
        login(pg)
        m = pg.evaluate(CARD_JS)
        tag = '[手机 %s]' % label
        rec(tag + ' 无横向溢出', m['ovf'] <= 1, 'ovf=%d' % m['ovf'])
        rec(tag + ' 无 JS 异常', not errs, str(errs[:1]))
        if label == '4种':
            rec(tag + ' 手机上也是轮播', m['carousel'] == 1, 'carousel=%d' % m['carousel'])
            pg.screenshot(path='design/shots/collapse-mobile.png')
        ctx.close()

    br.close()

srv.shutdown()

ok = sum(1 for r in results if r[1])
print('\n用药卡折叠验证：%d/%d 通过' % (ok, len(results)))
if ok != len(results):
    print('失败项：')
    for n, o, d in results:
        if not o: print('  -', n, '|', d)
    sys.exit(1)
