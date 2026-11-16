"""用药页面 + 今日卡片跳页 验证"""
import http.server, threading, json, socketserver, secrets, sys
from datetime import datetime
from playwright.sync_api import sync_playwright

DOC = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo'
USER = {'id': 1, 'email': 'test@example.com', 'display_name': '测试', 'is_admin': False}
sessions = {}
D = '2026-10-24'
PORT = 38522

def med(i, name, **kw):
    base = {'id': 'm%d' % i, 'name': name, 'purpose': '抗生素', 'form': '胶囊', 'strength': '',
            'doseAmount': 4, 'doseUnit': '胶囊', 'times': ['08:00', '19:00'],
            'mealTiming': 'after', 'mealOffset': 30, 'courseType': 'short',
            'startDate': '2026-10-20', 'endDate': '2026-11-04', 'reviewDate': '',
            'status': 'active', 'stock': '120', 'note': '', 'manufacturer': '青帝', 'medInfo': ''}
    base.update(kw)
    return base

MEDS = [
    med(1, '阿莫西林'),
    med(2, '克拉霉素片', doseAmount=2, doseUnit='片', times=['08:00', '12:00', '19:00'],
        mealTiming='before', mealOffset=15, stock='60'),
    med(6, '雷贝拉唑钠', doseAmount=1, doseUnit='片', times=['08:00'], mealTiming='before', mealOffset=30, stock='30'),
    med(3, '女奥美拉唑', startDate='2026-10-28', endDate='2026-11-10'),
    med(4, '枸橼酸铋钾', status='paused'),
    med(5, '头孢克洛', status='stopped'),
]

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
        'doses': {D: {'m1': {'08:00': 1}}},
        'bodyProfile': {'age': 30, 'height': 170}, 'weights': [], 'essays': [], 'tasks': []}, 'rev': 5}

board = make_board(MEDS)

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

PAGE_JS = """() => {
  const q = s => document.querySelector(s), qa = s => [...document.querySelectorAll(s)];
  const groups = qa('.med-group').map(g => ({
    label: (g.querySelector('.med-group-head h3') || {}).textContent || '',
    count: (g.querySelector('.med-group-head i') || {}).textContent || '',
    rows: g.querySelectorAll('.med-row').length,
    names: [...g.querySelectorAll('.med-row-title b')].map(e => e.textContent.trim())
  }));
  const rows = qa('.med-row').map(r => ({
    name: (r.querySelector('.med-row-title b') || {}).textContent || '',
    main: (r.querySelector('.med-row-dose > b') || {}).textContent || '',
    sec: (r.querySelector('.med-row-dose > span') || {}).textContent || '',
    slots: [...r.querySelectorAll('.med-slot')].map(s => ({ t: s.textContent.trim(), static: s.classList.contains('is-static'), done: s.classList.contains('done') })),
    stock: (r.querySelector('.med-row-stock') || {}).textContent || ''
  }));
  const mainB = rows.length ? q('.med-row-dose > b') : null;
  const secS = rows.length ? q('.med-row-dose > span') : null;
  const fs = el => el ? { size: parseFloat(getComputedStyle(el).fontSize), color: getComputedStyle(el).color, weight: getComputedStyle(el).fontWeight } : null;
  return {
    groups, rows,
    title: (q('.page-head h2') || {}).textContent || '',
    sub: (q('.page-head p') || {}).textContent || '',
    mainStyle: fs(mainB), secStyle: fs(secS),
    navActive: (q('.nav-item.active') || {}).textContent || '',
    ovf: document.documentElement.scrollWidth - innerWidth
  };
}"""

CARD_JS = """() => {
  const q = s => document.querySelector(s), qa = s => [...document.querySelectorAll(s)];
  const card = q('.vital-card.med-card');
  if (!card) return null;
  return {
    btns: qa('.vital-card.med-card .vital-actions button').map(b => ({ t: b.textContent.trim(), nav: b.dataset.nav || '', act: b.dataset.act || '', dis: b.disabled })),
    more: q('.vital-card.med-card .med-more') ? { t: q('.vital-card.med-card .med-more').textContent.trim(), nav: q('.vital-card.med-card .med-more').dataset.nav || '', act: q('.vital-card.med-card .med-more').dataset.act || '' } : null,
    lines: qa('.vital-card.med-card .med-line').length,
    carousel: qa('.vital-card.med-card .med-carousel').length,
    tabs: qa('.vital-card.med-card .med-tab').map(e => e.textContent.trim()),
    pane: (q('.vital-card.med-card .med-pane-top b') || {}).textContent || '',
    heights: qa('.vital-card').map(c => Math.round(c.getBoundingClientRect().height))
  };
}"""

with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)

    for layout in ('top', 'wide', 'side'):
        board.update(make_board(MEDS))
        ctx = br.new_context(viewport={'width': 1440, 'height': 950})
        pg = ctx.new_page()
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        login(pg, layout)
        tag = '[%s]' % layout

        # 导航里要有「用药」
        nav_txt = pg.evaluate("() => [...document.querySelectorAll('.nav-item')].map(e => e.textContent.trim())")
        rec(tag + ' 导航含用药入口', any('用药' in t for t in nav_txt), str(nav_txt))

        pg.click('.nav-item[data-nav="meds"]'); pg.wait_for_timeout(1100)
        m = pg.evaluate(PAGE_JS)
        labels = [g['label'] for g in m['groups']]
        rec(tag + ' 四个板块齐全且顺序正确', labels == ['进行中', '未开始', '暂停中', '已停用'], str(labels))
        rec(tag + ' 分组归属正确',
            [g['names'] for g in m['groups']] == [['克拉霉素片', '雷贝拉唑钠', '阿莫西林'], ['女奥美拉唑'], ['枸橼酸铋钾'], ['头孢克洛']],
            str([g['names'] for g in m['groups']]))
        rec(tag + ' 板块显示数量', [g['count'] for g in m['groups']] == ['3 种', '1 种', '1 种', '1 种'], str([g['count'] for g in m['groups']]))
        rec(tag + ' 导航高亮在用药', '用药' in m['navActive'], m['navActive'])
        rec(tag + ' 无横向溢出', m['ovf'] <= 1, 'ovf=%d' % m['ovf'])

        rec(tag + ' 同板块内餐前排在餐后前面',
            [x['name'] for x in m['rows'][:3]] == ['克拉霉素片', '雷贝拉唑钠', '阿莫西林'],
            str([x['name'] for x in m['rows'][:3]]))
        r0 = m['rows'][0]
        rec(tag + ' 餐前药主信息=每天三次/2片/餐前15分钟',
            r0['main'] == '每天三次，每次 2 片 餐前 15 分钟', r0['main'])
        rec(tag + ' 次要信息=用途/厂商/疗程',
            r0['sec'] == '· 抗生素 · 青帝 · 短期 · 第 5/16 天', r0['sec'])
        r_after = m['rows'][2]
        rec(tag + ' 餐后药主信息=每天两次/4胶囊/餐后半小时',
            r_after['main'] == '每天两次，每次 4 胶囊 餐后半小时', r_after['main'])
        rec(tag + ' 主信息比次要信息更显眼',
            m['mainStyle'] and m['secStyle'] and m['mainStyle']['size'] > m['secStyle']['size']
            and int(m['mainStyle']['weight']) >= 600 and m['mainStyle']['color'] != m['secStyle']['color'],
            '%s vs %s' % (m['mainStyle'], m['secStyle']))

        # 进行中可点，其余静态
        rec(tag + ' 进行中时间胶囊可点', all(not s['static'] for s in r0['slots']), str(r0['slots']))
        rec(tag + ' 已服胶囊标记 done', any(s['done'] for s in r_after['slots']), str(r_after['slots']))
        future_row = m['rows'][3]
        rec(tag + ' 未开始的时间为静态不可点', all(s['static'] for s in future_row['slots']), str(future_row['slots']))
        rec(tag + ' 未开始显示疗程未开始', '未开始' in future_row['sec'], future_row['sec'])
        rec(tag + ' 暂停/停用显示状态', '已暂停' in m['rows'][4]['sec'] and '已停用' in m['rows'][5]['sec'],
            m['rows'][4]['sec'] + ' / ' + m['rows'][5]['sec'])
        rec(tag + ' 库存显示', '剩 120 胶囊' in r_after['stock'], r_after['stock'])

        # 点时间胶囊打卡
        if layout == 'top':
            pg.screenshot(path='design/shots/medpage-top.png', full_page=True)
            before = pg.evaluate("() => document.querySelectorAll('.med-row .med-slot.done').length")
            pg.locator('.med-row .med-slot:not(.done):not(.is-static)').first.click()
            pg.wait_for_timeout(1300)
            after = pg.evaluate("() => document.querySelectorAll('.med-row .med-slot.done').length")
            rec('[top] 页面内点胶囊可记录', after == before + 1, '%d → %d' % (before, after))
        if layout == 'wide':
            pg.screenshot(path='design/shots/medpage-wide.png', full_page=True)

        # 今日卡片按钮
        pg.click('.nav-item[data-nav="today"]'); pg.wait_for_timeout(1200)
        c = pg.evaluate(CARD_JS)
        prim = [b for b in c['btns'] if b['t'] == '查看详细']
        rec(tag + ' 今日卡片主按钮=查看详细', bool(prim) and prim[0]['nav'] == 'meds', str(c['btns']))
        rec(tag + ' 卡片不显示「还有 N 种」提示', c['more'] is None, str(c['more']))
        rec(tag + ' 用药卡改为轮播（一次一种）', c['carousel'] == 1 and c['pane'] != '',
            'carousel=%d tabs=%d pane=%s' % (c['carousel'], len(c['tabs']), c['pane']))
        rec(tag + ' 四卡仍等高', max(c['heights']) - min(c['heights']) <= 1, str(c['heights']))
        # 点「查看详细」跳转
        pg.click('.vital-card.med-card .vital-actions button[data-nav="meds"]'); pg.wait_for_timeout(1200)
        jumped = pg.evaluate("() => ({ view: document.body.dataset.view, groups: document.querySelectorAll('.med-group').length })")
        rec(tag + ' 点查看详细跳转到用药页', jumped['view'] == 'meds' and jumped['groups'] == 4, str(jumped))
        rec(tag + ' 无 JS 异常', not errs, str(errs[:2]))
        ctx.close()

    # 只有 1 种药：卡片保持原样（弹窗）
    board.update(make_board([med(1, '阿莫西林')]))
    ctx = br.new_context(viewport={'width': 1440, 'height': 950})
    pg = ctx.new_page()
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    login(pg, 'top')
    c = pg.evaluate(CARD_JS)
    rec('[1种] 主按钮=记录(med-next)', c['btns'][0]['act'] == 'med-next', str(c['btns']))
    rec('[1种] 次按钮=全部(med-open 弹窗)', len(c['btns']) > 1 and c['btns'][1]['act'] == 'med-open', str(c['btns']))
    rec('[1种] 无折叠提示', c['more'] is None, str(c['more']))
    pg.click('.vital-card.med-card .vital-actions button[data-act="med-open"]'); pg.wait_for_timeout(900)
    rec('[1种] 弹窗可打开', pg.locator('#med-sheet').count() == 1, '')
    pg.screenshot(path='design/shots/medpage-1med.png')
    ctx.close()

    # 空状态
    board.update(make_board([]))
    ctx = br.new_context(viewport={'width': 1440, 'height': 950})
    pg = ctx.new_page()
    login(pg, 'top')
    pg.click('.nav-item[data-nav="meds"]'); pg.wait_for_timeout(1000)
    empty = pg.evaluate("() => ({ groups: document.querySelectorAll('.med-group').length, empty: !!document.querySelector('.empty-box'), add: !!document.querySelector('[data-act=\"med-new\"]') })")
    rec('[空] 无板块但有空态和添加按钮', empty['groups'] == 0 and empty['empty'] and empty['add'], str(empty))
    pg.screenshot(path='design/shots/medpage-empty.png')
    ctx.close()

    # 手机：更多页有入口 + 布局不溢出
    board.update(make_board(MEDS))
    for w in (390, 360):
        ctx = br.new_context(viewport={'width': w, 'height': 844}, is_mobile=True, has_touch=True, device_scale_factor=2)
        pg = ctx.new_page()
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        login(pg, 'top')
        has = pg.locator('.mobile-tab[data-nav="meds"]').count()
        pg.click('.mobile-tab[data-nav="meds"]'); pg.wait_for_timeout(1100)
        m = pg.evaluate(PAGE_JS)
        tag = '[手机 %d]' % w
        rec(tag + ' 底部 tab 有用药入口', has == 1, 'count=%d' % has)
        rec(tag + ' 四板块渲染', len(m['groups']) == 4, str([g['label'] for g in m['groups']]))
        rec(tag + ' 无横向溢出', m['ovf'] <= 1, 'ovf=%d' % m['ovf'])
        rec(tag + ' 无 JS 异常', not errs, str(errs[:1]))
        if w == 390:
            pg.screenshot(path='design/shots/medpage-mobile.png', full_page=True)
        ctx.close()

    br.close()

srv.shutdown()

ok = sum(1 for r in results if r[1])
print('\n用药页面验证：%d/%d 通过' % (ok, len(results)))
if ok != len(results):
    print('失败项：')
    for n, o, d in results:
        if not o: print('  -', n, '|', d)
    sys.exit(1)
