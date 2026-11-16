"""用药卡改版 + 间隔时长 验证"""
import http.server, threading, json, socketserver, secrets
from datetime import datetime
from playwright.sync_api import sync_playwright

DOC = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo'
USER = {'id': 1, 'email': 'test@example.com', 'display_name': '测试', 'is_admin': False}
sessions = {}
D = '2026-10-24'

MEDS = [
    {'id': 'm1', 'name': '阿莫西林', 'purpose': '抗生素', 'form': '胶囊', 'strength': '0.5g',
     'doseAmount': 1, 'doseUnit': '胶囊', 'times': ['08:00', '13:00', '20:00'],
     'mealTiming': 'after', 'mealOffset': 30, 'courseType': 'short',
     'startDate': '2026-10-20', 'endDate': '2026-10-26', 'reviewDate': '',
     'status': 'active', 'stock': '12', 'note': '', 'manufacturer': '辉瑞制药', 'medInfo': '缓释胶囊'},
    {'id': 'm2', 'name': '维生素D', 'purpose': '维生素', 'form': '粒', 'strength': '',
     'doseAmount': 1, 'doseUnit': '粒', 'times': ['08:00'],
     'mealTiming': 'before', 'mealOffset': 15, 'courseType': 'long',
     'startDate': '2026-10-13', 'endDate': '', 'reviewDate': '',
     'status': 'active', 'stock': '', 'note': '', 'manufacturer': '', 'medInfo': ''},
    {'id': 'm3', 'name': '布洛芬', 'purpose': '消炎药', 'form': '片', 'strength': '',
     'doseAmount': 1, 'doseUnit': '片', 'times': [],
     'mealTiming': 'after', 'mealOffset': 0, 'courseType': 'prn',
     'startDate': '2026-10-01', 'endDate': '', 'reviewDate': '',
     'status': 'active', 'stock': '', 'note': '', 'manufacturer': '', 'medInfo': ''},
]

board = {'data': {
    'version': 2, 'view': 'today',
    'habits': [{'id': 'h_med', 'name': '用药', 'icon': '💊', 'type': 'build', 'target': 1, 'unit': '次',
                'color': '#2f6f5e', 'note': '', 'createdAt': '2026-10-23T00:00:00Z', 'pinned': True, 'med': True, 'archivedAt': ''},
               {'id': 'h_water', 'name': '喝水', 'icon': '💧', 'type': 'build', 'target': 8, 'unit': '杯',
                'color': '#4c7f96', 'note': '', 'createdAt': '2026-10-23T00:00:00Z', 'pinned': True, 'archivedAt': ''}],
    'checks': {D: {'h_water': 5}}, 'notes': {}, 'moods': {}, 'events': [],
    'meds': MEDS[1:], 'doses': {D: {}},
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


BASE = json.loads(json.dumps(board['data']))
srv = TS(('127.0.0.1', 0), H)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()

steps, errs = [], []
def rec(name, ok, detail=''):
    steps.append({'name': name, 'ok': bool(ok), 'detail': detail})
    print(('PASS  ' if ok else 'FAIL  ') + name + (('  | ' + detail) if detail else ''))

with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)
    ctx = br.new_context(viewport={'width': 1440, 'height': 1000}, device_scale_factor=2)
    pg = ctx.new_page()
    pg.on('pageerror', lambda e: errs.append(str(e)[:200]))
    pg.on('console', lambda m: errs.append('console:' + m.text[:150]) if m.type == 'error' else None)
    pg.on('dialog', lambda d: d.accept())

    board['data'] = json.loads(json.dumps(BASE))
    pg.add_init_script("try{localStorage.setItem('lifeboard.layout','top');localStorage.setItem('lifeboard.skin','paper');localStorage.setItem('lifeboard.theme.mode','light');}catch(e){}")
    pg.clock.install(time=datetime(2026,10,24,10,0,0))
    pg.goto(f'http://127.0.0.1:{port}/index.html', wait_until='networkidle'); pg.wait_for_timeout(600)
    pg.click('[data-act="cloud-login"]'); pg.wait_for_timeout(400)
    pg.fill('input[name="email"]', 'test@example.com'); pg.fill('input[name="password"]', 'test@example.com')
    pg.click('form.modal-card button[type="submit"]'); pg.wait_for_timeout(3000)

    # ---------- 1. 两列布局 ----------
    grid = pg.evaluate("""() => {
      const g = document.querySelector('.vital-grid');
      const cs = getComputedStyle(g);
      const cards = [...g.querySelectorAll('.vital-card')].map(e => Math.round(e.getBoundingClientRect().width));
      return {cols: cs.gridTemplateColumns.split(' ').length, cards: cards.slice(0, 4)};
    }""")
    rec('常驻卡改为两列', grid['cols'] == 2, f"{grid['cols']} 列 / 卡宽 {grid['cards']}")

    # ---------- 2. 用药卡内嵌今日清单 ----------
    card = pg.evaluate("""() => {
      const c = document.querySelector('.med-card');
      if (!c) return null;
      const lines = [...c.querySelectorAll('.med-line')].map(l => ({
        name: l.querySelector('.med-line-top b').textContent,
        meta: l.querySelector('.med-line-top span').textContent,
        day: (l.querySelector('.med-line-day') || {}).textContent || '',
        slots: [...l.querySelectorAll('.med-mini')].map(b => ({t: b.textContent, done: b.classList.contains('done')}))
      }));
      return {lines: lines, prn: (c.querySelector('.med-prn-row') || {}).textContent || '',
              head: (c.querySelector('.vital-title small') || {}).textContent || '',
              status: (c.querySelector('.vital-status') || {}).textContent || ''};
    }""")
    print('   卡片明细:', json.dumps(card, ensure_ascii=False)[:400])
    rec('卡片只显示 1 种药（折叠）', card and len(card['lines']) == 1, f'{len(card["lines"]) if card else 0} 种')
    rec('显示餐前 + 间隔', card and '餐前 15 分钟' in card['lines'][0]['meta'],
        card['lines'][0]['meta'] if card and card['lines'] else '')
    rec('长期显示 N 天', card and '第 12 天' in card['lines'][0]['day'],
        card['lines'][0]['day'] if card and card['lines'] else '')
    rec('按需药单独一行', card and '按需' in card['prn'] and '布洛芬' in card['prn'], card['prn'] if card else '')
    slot_cnt = sum(len(l['slots']) for l in card['lines']) if card else 0
    rec('该药时段胶囊（1 个）', slot_cnt == 1, f'{slot_cnt} 个')
    rec('卡片头部仍显示总种数', card and '2 种药' in card['head'], card['head'] if card else '')
    pg.screenshot(path='design/shots/medcard-v2.png')

    # ---------- 3. 点时段胶囊打卡 ----------
    before = pg.evaluate("() => document.querySelector('.med-card .vital-status').textContent")
    pg.click('.med-card .med-mini:not(.done)')
    pg.wait_for_timeout(1800)
    after = pg.evaluate("() => ({s: document.querySelector('.med-card .vital-status').textContent, d: document.querySelectorAll('.med-card .med-mini.done').length})")
    rec('点击时段胶囊可打卡', before != after['s'] or after['d'] == 3, f'{before.strip()} → {after["s"].strip()} / 已完成胶囊 {after["d"]}')
    pg.screenshot(path='design/shots/medcard-v2-after.png')

    # ---------- 4. 间隔时长字段 ----------
    pg.click('.nav-item[data-nav="meds"]'); pg.wait_for_timeout(1300)
    pg.click('[data-act="med-edit"][data-id="m2"]'); pg.wait_for_timeout(900)
    f = pg.evaluate("""() => {
      const q = s => document.querySelector(s);
      const vis = s => { const e = q(s); return e ? getComputedStyle(e).display !== 'none' : null; };
      return {offSel: vis('[data-off]'), offVal: q('[name="mealOffset"]').value,
              custom: vis('[data-off-custom]'), meal: q('[name="mealTiming"]').value};
    }""")
    rec('间隔时长字段显示（饭前）', f['offSel'] is True and f['offVal'] == '15', json.dumps(f, ensure_ascii=False))

    pg.select_option('[name="mealTiming"]', ''); pg.wait_for_timeout(500)
    hidden = pg.evaluate("() => { const e = document.querySelector('[data-off]'); return getComputedStyle(e).display; }")
    rec('选「不限」时间隔自动隐藏', hidden == 'none', hidden)

    pg.select_option('[name="mealTiming"]', 'after'); pg.wait_for_timeout(400)
    pg.select_option('[name="mealOffset"]', 'custom'); pg.wait_for_timeout(500)
    cust = pg.evaluate("() => { const e = document.querySelector('[data-off-custom]'); return {d: getComputedStyle(e).display, v: e.querySelector('input').value}; }")
    rec('选自定义出现输入框', cust['d'] != 'none', json.dumps(cust, ensure_ascii=False))
    pg.fill('[name="mealOffsetCustom"]', '25')
    pg.screenshot(path='design/shots/med-form-offset.png')
    pg.click('#med-form button[type="submit"]'); pg.wait_for_timeout(2000)

    chk = pg.evaluate("""() => {
      const row = [...document.querySelectorAll('.med-row')].find(r => r.textContent.includes('维生素D'));
      return row ? row.innerText.replace(/\\n/g, ' / ') : null;
    }""")
    rec('保存自定义间隔 25 分钟', chk and '餐后 25 分钟' in chk, chk or '')

    # ---------- 5. 返回首页确认卡片同步 ----------
    pg.click('.nav-item[data-nav="today"]'); pg.wait_for_timeout(1500)
    card2 = pg.evaluate("""() => {
      const l = document.querySelector('.med-card .med-line');
      return l ? {n: l.querySelector('.med-line-top b').textContent,
                  meta: l.querySelector('.med-line-top span').textContent} : null;
    }""")
    rec('改间隔后首页卡片仍正常（1 条）', card2 and card2['meta'], str(card2))
    pg.screenshot(path='design/shots/medcard-v2-saved.png')

    # ---------- 6. wide 布局 / 手机 ----------
    for layout in ('wide',):
        pg.click('.nav-item[data-nav="settings"]'); pg.wait_for_timeout(1000)
        pg.click(f'[data-act="set-layout"][data-layout="{layout}"]'); pg.wait_for_timeout(900)
        pg.click('.nav-item[data-nav="today"]'); pg.wait_for_timeout(1500)
        w = pg.evaluate("""() => {
          const g = document.querySelector('.vital-grid');
          return {cols: getComputedStyle(g).gridTemplateColumns.split(' ').length,
                  ovf: document.documentElement.scrollWidth - innerWidth,
                  cardW: Math.round(document.querySelector('.med-card').getBoundingClientRect().width)};
        }""")
        rec(f'[{layout}] 两列且无溢出', w['cols'] == 2 and w['ovf'] <= 1, json.dumps(w, ensure_ascii=False))
        pg.screenshot(path=f'design/shots/medcard-v2-{layout}.png')
        pg.click('.nav-item[data-nav="settings"]'); pg.wait_for_timeout(900)
        pg.click('[data-act="set-layout"][data-layout="top"]'); pg.wait_for_timeout(800)
    ctx.close()

    mctx = br.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True, device_scale_factor=2)
    mp = mctx.new_page()
    mp.on('pageerror', lambda e: errs.append('[m]' + str(e)[:160]))
    mp.clock.install(time=datetime(2026,10,24,10,0,0))
    mp.goto(f'http://127.0.0.1:{port}/index.html', wait_until='networkidle'); mp.wait_for_timeout(600)
    mp.click('[data-act="cloud-login"]'); mp.wait_for_timeout(400)
    mp.fill('input[name="email"]', 'test@example.com'); mp.fill('input[name="password"]', 'test@example.com')
    mp.click('form.modal-card button[type="submit"]'); mp.wait_for_timeout(2800)
    m = mp.evaluate("""() => {
      const g = document.querySelector('.vital-grid');
      const c = document.querySelector('.med-card');
      return {cols: getComputedStyle(g).gridTemplateColumns.split(' ').length,
              lines: document.querySelectorAll('.med-card .med-line').length,
              ovf: document.documentElement.scrollWidth - innerWidth,
              cardH: Math.round(c.getBoundingClientRect().height)};
    }""")
    rec('手机端 1 列 + 清单不溢出', m['cols'] == 1 and m['ovf'] <= 1 and m['lines'] == 1, json.dumps(m, ensure_ascii=False))
    mp.screenshot(path='design/shots/medcard-v2-mobile.png')
    mctx.close()
    br.close()

srv.shutdown()
print('\n' + '=' * 56)
passed = sum(1 for s in steps if s['ok'])
print(f'用药卡改版：{passed}/{len(steps)} 通过')
print('JS/console 报错:', len(errs))
for e in errs[:6]: print('   ', e)
