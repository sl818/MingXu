"""用药卡轮播（≥2 种）验证：药名条 / 箭头切换 / 循环 / 胶囊不可点 / 不触发云保存"""
import http.server, threading, json, socketserver, secrets, sys
from datetime import datetime
from playwright.sync_api import sync_playwright

DOC = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo'
USER = {'id': 1, 'email': 'test@sl00.top', 'display_name': '测试', 'is_admin': False}
sessions = {}
D = '2026-10-24'
PORT = 38540

def med(i, name, dose, unit, times, meal, off=30, **kw):
    base = {'id': 'm%d' % i, 'name': name, 'purpose': '抗生素', 'form': '胶囊', 'strength': '',
            'doseAmount': dose, 'doseUnit': unit, 'times': times,
            'mealTiming': meal, 'mealOffset': off, 'courseType': 'short',
            'startDate': '2026-10-20', 'endDate': '2026-11-04', 'reviewDate': '',
            'status': 'active', 'stock': '60', 'note': '', 'manufacturer': '青帝', 'medInfo': ''}
    base.update(kw)
    return base

# 排序预期：餐前(08:00) → 餐前(12:00) → 餐前(20:00) → 餐后
FOUR = [
    med(1, '阿莫西林胶囊', 4, '胶囊', ['08:00', '19:00'], 'after'),
    med(2, '克拉霉素片', 2, '片', ['08:00'], 'before', 15),
    med(3, '艾司奥美拉唑镁肠溶胶囊', 1, '片', ['12:00'], 'before', 30),
    med(4, '枸橼酸铋钾胶囊', 2, '粒', ['20:00'], 'before', 30),
]
ONE = [med(1, '阿莫西林胶囊', 4, '胶囊', ['08:00', '19:00'], 'after')]
TWO = [FOUR[1], FOUR[0]]

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
    return {'data': {'version': 2, 'view': 'today', 'habits': HABITS,
                     'checks': {D: {'h_water': 3}}, 'notes': {}, 'moods': {}, 'events': [],
                     'meds': meds, 'doses': {D: {'m1': {'08:00': 1}}},
                     'bodyProfile': {'age': 30, 'height': 170}, 'weights': [], 'essays': [], 'tasks': []}, 'rev': 5}

board = make_board(FOUR)
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
            elif a == 'load': self._j({'ok': True, 'data': board['data'], 'rev': board['rev'], 'updated_at': 1792813000000})
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

def login(pg, layout='top'):
    pg.clock.install(time=datetime(2026, 10, 24, 10, 0, 0))
    pg.add_init_script("try{localStorage.setItem('lifeboard.layout','%s');localStorage.setItem('lifeboard.skin','paper');localStorage.setItem('lifeboard.theme.mode','light')}catch(e){}" % layout)
    pg.goto('http://127.0.0.1:%d/index.html' % PORT, wait_until='networkidle')
    pg.wait_for_timeout(700)
    pg.click('[data-act="cloud-login"]'); pg.wait_for_timeout(500)
    pg.fill('input[name="email"]', USER['email']); pg.fill('input[name="password"]', '12345678')
    pg.click('form.modal-card button[type="submit"]')
    pg.wait_for_timeout(2600)

CAR = """() => {
  const q = s => document.querySelector(s), qa = s => [...document.querySelectorAll(s)];
  const car = q('.med-carousel');
  return {
    hasCarousel: !!car,
    tabs: qa('.med-tab').map(t => ({ t: t.textContent.trim(), active: t.classList.contains('active') })),
    navs: qa('.med-nav').length,
    pos: (q('.med-pane-pos') || {}).textContent || '',
    name: (q('.med-pane-top b') || {}).textContent || '',
    meta: (q('.med-pane-meta') || {}).textContent || '',
    chips: qa('.med-pane-body .med-mini').map(c => ({ t: c.textContent.trim(), stat: c.classList.contains('is-static') })),
    headSmall: (q('.vital-card.med-card .vital-title small') || {}).textContent || '',
    lines: qa('.vital-card.med-card .med-line').length,
    cardH: q('.vital-card.med-card') ? Math.round(q('.vital-card.med-card').getBoundingClientRect().height) : 0,
    heights: qa('.vital-card').map(c => Math.round(c.getBoundingClientRect().height)),
    ovf: document.documentElement.scrollWidth - innerWidth,
    tabsOverflow: (() => { const t = q('.med-tabs'); return t ? t.scrollWidth > t.clientWidth + 1 : false; })()
  };
}"""

with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)

    # ---------- 4 种药：轮播 ----------
    board.update(make_board(FOUR))
    ctx = br.new_context(viewport={'width': 1440, 'height': 950})
    pg = ctx.new_page()
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    login(pg, 'top')
    c = pg.evaluate(CAR)
    rec('4 种药 → 出现轮播', c['hasCarousel'], '')
    rec('药名条 4 个且用简称',
        [t['t'] for t in c['tabs']] == ['克拉霉素', '艾司奥美拉唑镁', '枸橼酸铋钾', '阿莫西林'],
        str([t['t'] for t in c['tabs']]))
    rec('默认选中第 1 个', [t['active'] for t in c['tabs']] == [True, False, False, False], str(c['tabs']))
    rec('左右箭头各一个', c['navs'] == 2, '%d 个' % c['navs'])
    rec('显示 1 / 4', c['pos'].strip() == '1 / 4', c['pos'])
    rec('卡体显示全名', c['name'] == '克拉霉素片', c['name'])
    rec('卡体显示剂量+服法+天数', '2 片' in c['meta'] and '餐前 15 分钟' in c['meta'] and '第 5/16 天' in c['meta'], c['meta'])
    rec('轮播内胶囊不可点', bool(c['chips']) and all(x['stat'] for x in c['chips']), str(c['chips']))
    rec('头部只显示种数（不重复次数）', c['headSmall'].strip() == '4 种药', c['headSmall'])
    rec('四张卡等高', max(c['heights']) - min(c['heights']) <= 1, str(c['heights']))
    pg.screenshot(path='design/shots/carousel-4.png')

    # 翻卡不触发云保存
    base_save = save_count['n']
    pg.click('.med-nav[data-act="med-card-next"]'); pg.wait_for_timeout(900)
    c2 = pg.evaluate(CAR)
    rec('点右箭头切到第 2 个', c2['pos'].strip() == '2 / 4' and c2['name'] == '艾司奥美拉唑镁肠溶胶囊', c2['pos'] + ' ' + c2['name'])
    rec('翻卡不改变卡片高度', abs(c2['cardH'] - c['cardH']) <= 2, '%d → %d' % (c['cardH'], c2['cardH']))
    rec('翻卡不触发云保存', save_count['n'] == base_save, 'save 次数 %d → %d' % (base_save, save_count['n']))
    pg.screenshot(path='design/shots/carousel-4b.png')

    pg.click('.med-nav[data-act="med-card-prev"]'); pg.wait_for_timeout(800)
    c3 = pg.evaluate(CAR)
    rec('点左箭头回到第 1 个', c3['pos'].strip() == '1 / 4', c3['pos'])

    pg.click('.med-nav[data-act="med-card-prev"]'); pg.wait_for_timeout(800)
    c4 = pg.evaluate(CAR)
    rec('第 1 个再往前 → 循环到最后', c4['pos'].strip() == '4 / 4' and c4['name'] == '阿莫西林胶囊', c4['pos'] + ' ' + c4['name'])

    pg.locator('.med-tab:has-text("枸橼酸铋钾")').click(); pg.wait_for_timeout(800)
    c5 = pg.evaluate(CAR)
    rec('点药名条直达', c5['pos'].strip() == '3 / 4' and '枸橼酸铋钾' in c5['name'], c5['pos'] + ' ' + c5['name'])
    rec('药名条选中态同步', [t['active'] for t in c5['tabs']] == [False, False, True, False], str([t['active'] for t in c5['tabs']]))

    # 主按钮仍为查看详细 + 记录
    btns = pg.evaluate("() => [...document.querySelectorAll('.vital-card.med-card .vital-actions button')].map(b => ({t:b.textContent.trim(),nav:b.dataset.nav||'',act:b.dataset.act||''}))")
    rec('按钮=查看详细 + 记录', btns[0]['nav'] == 'meds' and btns[1]['act'] == 'med-next', str(btns))
    rec('无 JS 异常', not errs, str(errs[:2]))
    ctx.close()

    # ---------- 1 种药：无轮播、胶囊可点 ----------
    board.update(make_board(ONE))
    ctx = br.new_context(viewport={'width': 1440, 'height': 950})
    pg = ctx.new_page()
    login(pg, 'top')
    c = pg.evaluate(CAR)
    rec('[1种] 不出现轮播', not c['hasCarousel'], '')
    rec('[1种] 显示单条明细', c['lines'] == 1, '%d 条' % c['lines'])
    btn_chips = pg.evaluate("() => [...document.querySelectorAll('.med-line .med-mini')].map(e => ({tag: e.tagName, stat: e.classList.contains('is-static')}))")
    rec('[1种] 胶囊是可点按钮', bool(btn_chips) and all(x['tag'] == 'BUTTON' and not x['stat'] for x in btn_chips), str(btn_chips))
    rec('[1种] 按钮=记录 + 全部', pg.evaluate("() => [...document.querySelectorAll('.vital-card.med-card .vital-actions button')].map(b=>b.dataset.act||'')") == ['med-next', 'med-open'], '')
    pg.screenshot(path='design/shots/carousel-1.png')
    ctx.close()

    # ---------- 2 种药：轮播 + 两格 ----------
    board.update(make_board(TWO))
    ctx = br.new_context(viewport={'width': 1440, 'height': 950})
    pg = ctx.new_page()
    login(pg, 'top')
    c = pg.evaluate(CAR)
    rec('[2种] 出现轮播且 2 个药名', c['hasCarousel'] and len(c['tabs']) == 2, str(c['tabs']))
    rec('[2种] 显示 1 / 2', c['pos'].strip() == '1 / 2', c['pos'])
    ctx.close()

    # ---------- 手机：药名条可横向滚动、无溢出 ----------
    for w in (390, 360):
        board.update(make_board(FOUR))
        ctx = br.new_context(viewport={'width': w, 'height': 844}, is_mobile=True, has_touch=True, device_scale_factor=2)
        pg = ctx.new_page()
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        login(pg, 'top')
        c = pg.evaluate(CAR)
        tag = '[手机 %d]' % w
        rec(tag + ' 轮播渲染', c['hasCarousel'] and len(c['tabs']) == 4, '%d 个药名' % len(c['tabs']))
        rec(tag + ' 无横向溢出', c['ovf'] <= 1, 'ovf=%d' % c['ovf'])
        rec(tag + ' 药名条可滚动不撑破', c['ovf'] <= 1, 'scrollable=%s' % c['tabsOverflow'])
        rec(tag + ' 无 JS 异常', not errs, str(errs[:1]))
        if w == 390:
            pg.screenshot(path='design/shots/carousel-mobile.png')
            pg.click('.med-nav[data-act="med-card-next"]'); pg.wait_for_timeout(800)
            rec(tag + ' 手机上可翻卡', pg.evaluate(CAR)['pos'].strip() == '2 / 4', '')
        ctx.close()

    br.close()

srv.shutdown()
ok = sum(1 for r in results if r[1])
print('\n用药卡轮播验证：%d/%d 通过' % (ok, len(results)))
if ok != len(results):
    print('失败项：')
    for n, o, d in results:
        if not o: print('  -', n, '|', d)
    sys.exit(1)
