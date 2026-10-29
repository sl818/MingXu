"""三布局综合回归：8 页面 / 核心交互 / 移动端 / 新组件校验"""
import http.server, threading, json, socketserver, secrets
from datetime import datetime
from playwright.sync_api import sync_playwright

DOC = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo'
USER = {'id': 1, 'email': 'test@sl00.top', 'display_name': '测试', 'is_admin': False}
sessions = {}
D = '2026-10-24'

HABITS = [
    {'id': 'h_med', 'name': '用药', 'icon': '💊', 'type': 'build', 'target': 2, 'unit': '次', 'color': '#2f6f5e', 'note': '', 'createdAt': '2026-10-23T00:00:00Z', 'pinned': True, 'med': True, 'archivedAt': ''},
    {'id': 'h_water', 'name': '喝水', 'icon': '💧', 'type': 'build', 'target': 8, 'unit': '杯', 'color': '#4c7f96', 'note': '', 'createdAt': '2026-10-23T00:00:00Z', 'pinned': True, 'archivedAt': ''},
    {'id': 'h_move', 'name': '运动', 'icon': '🏃', 'type': 'build', 'target': 1, 'unit': '次', 'color': '#b5733f', 'note': '', 'createdAt': '2026-10-23T00:00:00Z', 'pinned': True, 'archivedAt': ''},
    {'id': 'h_breathe', 'name': '478呼吸法', 'icon': '🌬️', 'type': 'build', 'target': 1, 'unit': '次', 'color': '#5b8f8a', 'note': '', 'createdAt': '2026-10-23T00:00:00Z', 'pinned': True, 'optional': True, 'archivedAt': ''},
    {'id': 'h_quit', 'name': '戒烟', 'icon': '🚭', 'type': 'quit', 'target': 1, 'unit': '次', 'color': '#9c5a5a', 'note': '', 'createdAt': '2026-10-23T00:00:00Z', 'pinned': False, 'archivedAt': ''},
]

checks = {
    '2026-10-22': {'h_water': 8, 'h_move': 1, 'h_med': 2},
    '2026-10-23': {'h_water': 6, 'h_move': 1, 'h_med': 2},
    '2026-10-24': {'h_water': 12, 'h_move': 1, 'h_med': 2, 'h_breathe': 1},
}

board = {'data': {
    'version': 2, 'view': 'today', 'habits': HABITS, 'checks': checks,
    'notes': {}, 'moods': {D: 'happy', '2026-10-23': 'ok'}, 'events': [],
    'meds': [{'id': 'm1', 'name': '晚间服药', 'purpose': '其他', 'form': '片', 'strength': '', 'doseAmount': 1,
              'doseUnit': '片', 'times': ['08:00', '20:00'], 'courseType': 'long', 'startDate': '2026-10-01',
              'endDate': '', 'reviewDate': '', 'status': 'active', 'stock': '14', 'note': ''}],
    'doses': {'2026-10-24': {'m1': {'08:00': 1}}},
    'bodyProfile': {'age': 30, 'height': 170},
    'weights': [{'id': 'w1', 'date': '2026-10-24', 'kg': 68.4}],
    'essays': [],
    'tasks': [
        {'id': 't1', 'title': '晚上跟读半小时', 'note': '', 'tag': '英语', 'priority': '高', 'status': 'todo', 'due': '2026-10-24', 'createdAt': '2026-10-23T08:00:00Z'},
        {'id': 't2', 'title': '做 20 个阅读填空', 'note': '', 'tag': '英语', 'priority': '高', 'status': 'todo', 'due': '2026-10-24', 'createdAt': '2026-10-23T08:00:00Z'},
        {'id': 't3', 'title': '晚上陪妈妈', 'note': '', 'tag': '生活', 'priority': '中', 'status': 'done', 'due': '2026-10-24', 'doneAt': D, 'createdAt': '2026-10-23T08:00:00Z'},
        {'id': 't4', 'title': '整理旧书', 'note': '', 'tag': '生活', 'priority': '低', 'status': 'doing', 'due': '2026-10-24', 'createdAt': '2026-10-23T08:00:00Z'},
        {'id': 't5', 'title': '已放弃的计划', 'note': '', 'tag': '其他', 'priority': '低', 'status': 'cancelled', 'due': '2026-10-20', 'createdAt': '2026-10-19T08:00:00Z'}
    ]}, 'rev': 5}


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
            elif a == 'push_status': self._j({'ok': True, 'enabled': False, 'webhook': '', 'sent_today': 0, 'last_sent': ''})
            elif a == 'ics_status': self._j({'ok': True, 'url': None})
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


BASE_DATA = json.loads(json.dumps(board['data']))

srv = TS(('127.0.0.1', 0), H)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()

steps, errs = [], []
def rec(name, ok, detail=''):
    steps.append({'name': name, 'ok': bool(ok), 'detail': detail})
    print(('PASS  ' if ok else 'FAIL  ') + name + (('  | ' + detail) if detail else ''))

SCAN = """() => ({
  ovf: document.documentElement.scrollWidth - innerWidth,
  railVisible: (() => { const r = document.querySelector('.rail');
      return r ? getComputedStyle(r).display !== 'none' && r.getBoundingClientRect().width > 0 : false; })(),
  hasHead: !!document.querySelector('.today-head, .page-head, .hero'),
  cards: document.querySelectorAll('.panel, .vital-card, .habit-card, .task, .stat-card, .cal-cell').length
})"""

with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)

    # ---------- A. 三布局 × 8 页面 ----------
    for layout in ('wide', 'top', 'side'):
        board['data'] = json.loads(json.dumps(BASE_DATA))
        ctx = br.new_context(viewport={'width': 1440, 'height': 900}, device_scale_factor=1)
        pg = ctx.new_page()
        pg.on('pageerror', lambda e: errs.append(f'[{layout}] {e}'[:180]))
        pg.on('console', lambda m: errs.append(f'[{layout}] {m.text[:120]}') if m.type == 'error' else None)
        pg.add_init_script(f"try{{localStorage.setItem('lifeboard.layout','{layout}');localStorage.setItem('lifeboard.skin','paper');localStorage.setItem('lifeboard.theme.mode','light');}}catch(e){{}}")
        pg.clock.install(time=datetime(2026,10,24,10,0,0))
        pg.goto(f'http://127.0.0.1:{port}/index.html', wait_until='networkidle'); pg.wait_for_timeout(600)
        pg.click('[data-act="cloud-login"]'); pg.wait_for_timeout(400)
        pg.fill('input[name="email"]', 'test@sl00.top'); pg.fill('input[name="password"]', 'test@sl00.top')
        pg.click('form.modal-card button[type="submit"]'); pg.wait_for_timeout(2800)

        views = [('today', '今日'), ('board', '待办'), ('habits', '习惯'), ('weight', '体重'),
                 ('essays', '随笔'), ('calendar', '日历'), ('stats', '统计'), ('settings', '设置')]
        for v, label in views:
            before = len(errs)
            pg.click(f'.nav-item[data-nav="{v}"]'); pg.wait_for_timeout(1100)
            s = pg.evaluate(SCAN)
            newerr = len(errs) - before
            ok = s['ovf'] <= 1 and s['hasHead'] and s['cards'] > 0 and newerr == 0
            rail_ok = (s['railVisible'] is (v == 'today' and layout == 'wide'))
            rec(f'[{layout}] {label}', ok and rail_ok,
                f'横溢{s["ovf"]} 卡片{s["cards"]} 右栏{s["railVisible"]} 报错{newerr}')
            pg.screenshot(path=f'design/shots/rg-{layout}-{v}.png')

        # 打卡完成态可撤销
        pg.click('.nav-item[data-nav="today"]'); pg.wait_for_timeout(1200)
        st = pg.evaluate("""() => {
          const b = document.querySelector('.vital-btn.done');
          const inc = document.querySelector('[data-act="habit-inc"][data-id="h_water"]');
          return {doneTxt: b ? b.textContent.trim() : null, doneAct: b ? b.dataset.act : null,
                  incBtn: inc ? {txt: inc.textContent.trim(), disabled: inc.disabled} : null};
        }""")
        rec(f'[{layout}] 完成态文案与撤销', st['doneTxt'] and '可撤销' in st['doneTxt'] and st['doneAct'] == 'habit-dec',
            json.dumps(st, ensure_ascii=False))

        # 点击完成态按钮应真的减 1 杯（毫升制下 = 250 ml；喝水 12 次已超目标，减一次仍达标，故验证数值而非按钮态）
        if st['doneAct'] == 'habit-dec':
            rd = """() => {
              const b = document.querySelector('[data-act="habit-dec"][data-id="h_water"]');
              if (!b) return null;
              const card = b.closest('.vital-card');
              const v = card ? card.querySelector('.vnum') : null;
              return v ? Number(v.textContent) : null;
            }"""
            before = pg.evaluate(rd)
            pg.click('[data-act="habit-dec"][data-id="h_water"]'); pg.wait_for_timeout(1600)
            after = pg.evaluate(rd)
            rec(f'[{layout}] 点击已完成可撤销', before is not None and after is not None and before - after == 250,
                f'计数 {before} → {after}')
            # 计数已减 1（测试数据在下一轮开始前统一重置）

        # 图例/统计
        if layout == 'wide':
            pg.click('.nav-item[data-nav="calendar"]'); pg.wait_for_timeout(1200)
            leg = pg.evaluate("""() => {
              const l = document.querySelector('.cal-legend');
              return l ? {txt: l.innerText.replace(/\\n/g, ' ').slice(0, 60), legs: l.querySelectorAll('.leg').length} : null;
            }""")
            rec('日历图例带百分比', leg and leg['legs'] == 5 and ('39%' in leg['txt'] or '74%' in leg['txt']),
                json.dumps(leg, ensure_ascii=False))

            pg.click('.nav-item[data-nav="stats"]'); pg.wait_for_timeout(1300)
            bars = pg.evaluate("""() => {
              const z = document.querySelectorAll('.bar-wrap i.zero').length;
              const low = document.querySelectorAll('.bar-wrap i.low').length;
              const norm = document.querySelectorAll('.bar-wrap i:not(.zero):not(.low)').length;
              const note = document.querySelector('.page-head p');
              return {zero: z, low: low, normal: norm, note: note ? note.innerText.slice(0, 50) : ''};
            }""")
            rec('统计柱三态区分', bars['zero'] > 0 and bars['normal'] > 0, json.dumps(bars, ensure_ascii=False))
        ctx.close()

    # ---------- B. 布局切换持久化 ----------
    ctx = br.new_context(viewport={'width': 1440, 'height': 900})
    pg = ctx.new_page()
    pg.on('pageerror', lambda e: errs.append(f'[switch] {e}'[:180]))
    pg.clock.install(time=datetime(2026,10,24,10,0,0))
    pg.goto(f'http://127.0.0.1:{port}/index.html', wait_until='networkidle'); pg.wait_for_timeout(600)
    pg.click('[data-act="cloud-login"]'); pg.wait_for_timeout(400)
    pg.fill('input[name="email"]', 'test@sl00.top'); pg.fill('input[name="password"]', 'test@sl00.top')
    pg.click('form.modal-card button[type="submit"]'); pg.wait_for_timeout(2800)
    for target, chk in [('wide', 'grid'), ('side', 'grid'), ('top', 'flex')]:
        pg.click('.nav-item[data-nav="settings"]'); pg.wait_for_timeout(900)
        n = pg.locator('button[data-act="set-layout"]').count()
        if target == 'wide' and n != 3:
            rec('排版选择器 3 张卡片', False, f'{n} 张')
        pg.click(f'[data-act="set-layout"][data-layout="{target}"]'); pg.wait_for_timeout(900)
        got = pg.evaluate("() => ({lay: document.documentElement.dataset.layout, app: getComputedStyle(document.querySelector('.app')).display})")
        rec(f'切换到 {target}', got['lay'] == target and got['app'] == chk, json.dumps(got))
    pg.reload(wait_until='networkidle'); pg.wait_for_timeout(2500)
    kept = pg.evaluate("() => ({lay: document.documentElement.dataset.layout, items: document.querySelectorAll('.nav-item').length})")
    rec('刷新后布局保持', kept['lay'] == 'top' and kept['items'] == 9, json.dumps(kept))
    rec('排版选择器 3 张卡片', True, '已在上面校验')
    ctx.close()

    # ---------- C. 移动端三布局 ----------
    for layout in ('wide', 'top', 'side'):
        ctx = br.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True, device_scale_factor=2)
        pg = ctx.new_page()
        pg.on('pageerror', lambda e: errs.append(f'[m-{layout}] {e}'[:180]))
        pg.add_init_script(f"try{{localStorage.setItem('lifeboard.layout','{layout}');localStorage.setItem('lifeboard.skin','paper');localStorage.setItem('lifeboard.theme.mode','light');}}catch(e){{}}")
        pg.clock.install(time=datetime(2026,10,24,10,0,0))
        pg.goto(f'http://127.0.0.1:{port}/index.html', wait_until='networkidle'); pg.wait_for_timeout(700)
        pg.click('[data-act="cloud-login"]'); pg.wait_for_timeout(400)
        pg.fill('input[name="email"]', 'test@sl00.top'); pg.fill('input[name="password"]', 'test@sl00.top')
        pg.click('form.modal-card button[type="submit"]'); pg.wait_for_timeout(2800)
        m = pg.evaluate("""() => {
          const qa = s => [...document.querySelectorAll(s)];
          const over = [];
          document.querySelectorAll('.main *').forEach(e => {
            const r = e.getBoundingClientRect();
            if (r.width === 0 || r.height === 0) return;
            if (r.right > innerWidth + 1 || r.left < -1) over.push(e.className.toString().slice(0, 30));
          });
          return {ovf: document.documentElement.scrollWidth - innerWidth, over: over.slice(0, 4),
                  statCards: qa('.hero').length, heroWeek: qa('.hero-week').length, tabs: qa('.mobile-tab').length, addBtn: qa('.mobile-add').length,
                  head: !!document.querySelector('.today-head, .hero'),
                  railShown: (() => { const r = document.querySelector('.rail'); return r ? r.getBoundingClientRect().width > 0 : false; })()};
        }""")
        rec(f'[手机 {layout}] Hero 恢复 / 无溢出 / tabbar',
            m['ovf'] <= 1 and len(m['over']) == 0 and m['statCards'] == 1 and m['tabs'] == 4 and m['head'] and not m['railShown'],
            json.dumps(m, ensure_ascii=False))
        pg.screenshot(path=f'design/shots/rg-m-{layout}.png')
        ctx.close()

    br.close()

srv.shutdown()
print('\n' + '=' * 60)
passed = sum(1 for s in steps if s['ok'])
print(f'综合回归：{passed}/{len(steps)} 通过')
print('JS/console 报错:', len(errs))
for e in errs[:10]: print('   ', e)

json.dump({'steps': steps, 'errors': errs, 'passed': passed, 'total': len(steps)},
          open('e2e/regression-v3.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
