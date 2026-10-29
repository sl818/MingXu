"""v15：设置页按钮移除 / 用药卡单条 / 移动端 4tab+悬浮+ / 更多页面入口"""
import http.server, threading, json, socketserver, secrets, sys
from datetime import datetime
from playwright.sync_api import sync_playwright

DOC = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo'
USER = {'id': 1, 'email': 'test@sl00.top', 'display_name': '测试', 'is_admin': False}
sessions = {}
D = '2026-10-25'
PORT = 38530

def med(i, name, **kw):
    base = {'id': 'm%d' % i, 'name': name, 'purpose': '抗生素', 'form': '胶囊', 'strength': '',
            'doseAmount': 4, 'doseUnit': '胶囊', 'times': ['08:00', '19:00'],
            'mealTiming': 'after', 'mealOffset': 30, 'courseType': 'short',
            'startDate': '2026-10-20', 'endDate': '2026-11-04', 'reviewDate': '',
            'status': 'active', 'stock': '120', 'note': '', 'manufacturer': '青帝', 'medInfo': ''}
    base.update(kw)
    return base

FOUR = [med(1, '阿莫西林'),
        med(2, '克拉霉素片', doseAmount=2, doseUnit='片', mealTiming='before', mealOffset=15),
        med(3, '雷贝拉唑钠', doseAmount=1, doseUnit='片', times=['08:00'], mealTiming='before', mealOffset=30),
        med(4, '枸橼酸铋钾', doseAmount=2, doseUnit='粒')]
ONE = [med(1, '阿莫西林')]

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
        'meds': meds, 'doses': {D: {'m1': {'08:00': 1}}},
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
            elif a == 'load': self._j({'ok': True, 'data': board['data'], 'rev': board['rev'], 'updated_at': 1792900000000})
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
srv = TS(('127.0.0.1', PORT), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()

results = []
def rec(name, ok, detail=''):
    results.append((name, ok, detail))
    print(('PASS  ' if ok else 'FAIL  ') + name + (('  | ' + str(detail)) if detail else ''))

def login(pg, layout='top'):
    pg.add_init_script("try{localStorage.setItem('lifeboard.layout','%s');localStorage.setItem('lifeboard.skin','paper');localStorage.setItem('lifeboard.theme.mode','light')}catch(e){}" % layout)
    pg.clock.install(time=datetime(2026,10,24,10,0,0))
    pg.goto('http://127.0.0.1:%d/index.html' % PORT, wait_until='networkidle')
    pg.wait_for_timeout(700)
    pg.click('[data-act="cloud-login"]'); pg.wait_for_timeout(500)
    pg.fill('input[name="email"]', USER['email']); pg.fill('input[name="password"]', '12345678')
    pg.click('form.modal-card button[type="submit"]')
    pg.wait_for_timeout(2600)

EXPECT_NAV = ['今日', '用药', '待办', '随笔', '体重', '习惯', '日历', '统计', '设置']

with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)

    # ---------- 桌面：三布局 ----------
    for layout in ('top', 'side', 'wide'):
        board.update(make_board(FOUR))
        ctx = br.new_context(viewport={'width': 1440, 'height': 950})
        pg = ctx.new_page()
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        login(pg, layout)
        tag = '[%s]' % layout

        nav = pg.evaluate("() => [...document.querySelectorAll('.nav-item')].map(e => e.textContent.trim())")
        expect = EXPECT_NAV if layout != 'wide' else ['今日', '用药管理', '待办看板', '随笔', '体重与 BMI', '习惯', '打卡日历', '数据统计', '设置']
        rec(tag + ' 导航顺序正确', nav == expect, str(nav))

        # 用药卡：只剩一条
        card = pg.evaluate("""() => {
          const q = s => document.querySelector(s), qa = s => [...document.querySelectorAll(s)];
          return {
            lines: qa('.vital-card.med-card .med-line').length,
            carousel: qa('.vital-card.med-card .med-carousel').length,
            tabs: qa('.vital-card.med-card .med-tab').map(e => e.textContent.trim()),
            pane: (q('.vital-card.med-card .med-pane-top b') || {}).textContent || '',
            more: qa('.vital-card.med-card .med-more').length,
            btns: qa('.vital-card.med-card .vital-actions button').map(b => ({t: b.textContent.trim(), nav: b.dataset.nav || '', act: b.dataset.act || ''})),
            head: (q('.vital-card.med-card .vital-title small') || {}).textContent || ''
          };
        }""")
        rec(tag + ' 用药卡改为轮播（一次一种）', card['carousel'] == 1 and len(card['tabs']) == 4 and card['pane'] != '',
            'carousel=%d tabs=%s pane=%s' % (card['carousel'], card['tabs'], card['pane']))
        rec(tag + ' 无「还有 N 种」提示', card['more'] == 0, 'count=%d' % card['more'])
        prim = [b for b in card['btns'] if b['t'] == '查看详细']
        rec(tag + ' 主按钮=查看详细(跳用药页)', bool(prim) and prim[0]['nav'] == 'meds', str(card['btns']))
        rec(tag + ' 次按钮=记录(med-next)', any(b['act'] == 'med-next' for b in card['btns']), str(card['btns']))
        rec(tag + ' 卡片头部仍显示总种数', '4 种药' in card['head'], card['head'])
        if layout == 'top':
            pg.screenshot(path='design/shots/v15-card-1line.png')

        # 设置页：无「习惯与用药」按钮 + 桌面不显示「更多页面」
        pg.click('.nav-item[data-nav="settings"]'); pg.wait_for_timeout(1100)
        st = pg.evaluate("""() => {
          const q = s => document.querySelector(s);
          const btn = [...document.querySelectorAll('.page-head button')].map(b => b.textContent.trim());
          const mo = q('.mobile-only');
          return {headBtns: btn, mobileOnly: mo ? getComputedStyle(mo).display : 'absent'};
        }""")
        rec(tag + ' 设置页头无多余按钮', st['headBtns'] == [], str(st['headBtns']))
        rec(tag + ' 桌面隐藏「更多页面」区块', st['mobileOnly'] in ('absent', 'none'), st['mobileOnly'])
        if layout == 'top':
            pg.screenshot(path='design/shots/v15-settings.png')
        rec(tag + ' 无 JS 异常', not errs, str(errs[:2]))
        ctx.close()

    # ---------- 只有 1 种药：卡片仍一条 + 按钮不变 ----------
    board.update(make_board(ONE))
    ctx = br.new_context(viewport={'width': 1440, 'height': 950})
    pg = ctx.new_page()
    login(pg, 'top')
    card = pg.evaluate("""() => {
      const qa = s => [...document.querySelectorAll(s)];
      return {
        lines: qa('.vital-card.med-card .med-line').length,
        btns: qa('.vital-card.med-card .vital-actions button').map(b => ({t: b.textContent.trim(), act: b.dataset.act || '', nav: b.dataset.nav || ''}))
      };
    }""")
    rec('[1种] 卡片 1 条 + 记录/全部', card['lines'] == 1 and card['btns'][0]['act'] == 'med-next'
        and card['btns'][1]['act'] == 'med-open', str(card))
    ctx.close()

    # ---------- 手机：4 tab + 悬浮加号 ----------
    board.update(make_board(FOUR))
    for w in (390, 360):
        ctx = br.new_context(viewport={'width': w, 'height': 844}, is_mobile=True, has_touch=True, device_scale_factor=2)
        pg = ctx.new_page()
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        login(pg, 'top')
        tag = '[手机 %d]' % w

        mb = pg.evaluate("""() => {
          const qa = s => [...document.querySelectorAll(s)];
          const add = document.querySelector('.mobile-add');
          const r = add ? add.getBoundingClientRect() : null;
          const bar = document.querySelector('.mobile-tabbar');
          const br = bar ? bar.getBoundingClientRect() : null;
          return {
            tabs: qa('.mobile-tab').map(e => e.textContent.trim()),
            hasAdd: !!add,
            addSize: r ? Math.round(r.width) + 'x' + Math.round(r.height) : '',
            addAboveBar: r && br ? Math.round(br.top - r.top) > 0 : false,
            ovf: document.documentElement.scrollWidth - innerWidth
          };
        }""")
        rec(tag + ' 底部 4 个 tab（末位为「更多」抽屉入口）', mb['tabs'] == ['今日', '用药', '待办', '更多'], str(mb['tabs']))
        rec(tag + ' 中间有悬浮加号且凸出', mb['hasAdd'] and mb['addAboveBar'], '%s top-out=%s' % (mb['addSize'], mb['addAboveBar']))
        rec(tag + ' 无横向溢出', mb['ovf'] <= 1, 'ovf=%d' % mb['ovf'])

        # 点加号 → 新建面板
        pg.click('.mobile-add'); pg.wait_for_timeout(700)
        qa = pg.evaluate("""() => {
          const q = s => document.querySelector(s);
          return {open: !!q('#quick-add'),
                  items: [...document.querySelectorAll('#quick-add .qa-item')].map(e => e.querySelector('b').textContent.trim())};
        }""")
        rec(tag + ' 加号打开新建面板 5 项', qa['open'] and qa['items'] == ['待办', '习惯', '用药', '随笔', '体重'], str(qa))
        if w == 390:
            pg.screenshot(path='design/shots/v15-quick-add.png')

        # 点「待办」→ 待办表单
        pg.locator('#quick-add .qa-item:has-text("待办")').click(); pg.wait_for_timeout(800)
        rec(tag + ' 新建面板可打开待办表单', pg.locator('#task-form').count() == 1, '')
        pg.click('[data-act="close-modal"]'); pg.wait_for_timeout(500)

        # 设置页「更多页面」5 项（仅手机显示）
        # 底部最后一个 tab 已改为「更多」抽屉，设置页从抽屉进入
        pg.click('[data-act="more-open"]'); pg.wait_for_timeout(600)
        pg.evaluate("""() => { const b = document.querySelector('[data-act="more-go"][data-view="settings"]'); if (b) b.click(); }""")
        pg.wait_for_timeout(1100)
        mp = pg.evaluate("""() => {
          const q = s => document.querySelector(s);
          const mo = q('.mobile-only');
          return {disp: mo ? getComputedStyle(mo).display : 'absent',
                  links: [...document.querySelectorAll('.page-link')].map(e => e.querySelector('b').textContent.trim())};
        }""")
        rec(tag + ' 手机显示「更多页面」区块', mp['disp'] == 'block', mp['disp'])
        rec(tag + ' 更多页面 5 个入口', mp['links'] == ['习惯', '随笔', '体重', '日历', '统计'], str(mp['links']))
        if w == 390:
            pg.screenshot(path='design/shots/v15-mobile-settings.png')
            # 点「日历」跳转
            pg.locator('.page-link:has-text("日历")').click(); pg.wait_for_timeout(1100)
            jumped = pg.evaluate("() => document.body.dataset.view")
            rec(tag + ' 更多页面可跳转', jumped == 'calendar', jumped)
        rec(tag + ' 无 JS 异常', not errs, str(errs[:1]))
        ctx.close()

    br.close()

srv.shutdown()
ok = sum(1 for r in results if r[1])
print('\nv15 验证：%d/%d 通过' % (ok, len(results)))
if ok != len(results):
    print('失败项：')
    for n, o, d in results:
        if not o: print('  -', n, '|', d)
    sys.exit(1)
