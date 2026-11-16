"""用药面板改造验证：次数 / 每次时间 / 饭前饭后"""
import http.server, threading, json, socketserver, secrets
from datetime import datetime
from playwright.sync_api import sync_playwright

DOC = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo'
USER = {'id': 1, 'email': 'test@example.com', 'display_name': '测试', 'is_admin': False}
sessions = {}
D = '2026-10-24'

board = {'data': {
    'version': 2, 'view': 'today',
    'habits': [{'id': 'h_med', 'name': '用药', 'icon': '💊', 'type': 'build', 'target': 1, 'unit': '次',
                'color': '#2f6f5e', 'note': '', 'createdAt': '2026-10-23T00:00:00Z', 'pinned': True, 'med': True, 'archivedAt': ''}],
    'checks': {}, 'notes': {}, 'moods': {}, 'events': [],
    'meds': [{'id': 'm1', 'name': '阿莫西林', 'purpose': '抗生素', 'form': '胶囊', 'strength': '0.5g',
              'doseAmount': 1, 'doseUnit': '胶囊', 'times': ['08:00', '20:00'], 'mealTiming': 'after',
              'courseType': 'short', 'startDate': '2026-10-20', 'endDate': '2026-10-26', 'reviewDate': '',
              'status': 'active', 'stock': '12', 'note': '饭后半小时'}],
    'doses': {}, 'bodyProfile': {'age': 30, 'height': 170}, 'weights': [], 'essays': [], 'tasks': []}, 'rev': 5}


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


srv = TS(('127.0.0.1', 0), H)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()

steps, errs = [], []
def rec(name, ok, detail=''):
    steps.append({'name': name, 'ok': bool(ok), 'detail': detail})
    print(('PASS  ' if ok else 'FAIL  ') + name + (('  | ' + detail) if detail else ''))

with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)
    ctx = br.new_context(viewport={'width': 1440, 'height': 950}, device_scale_factor=2)
    pg = ctx.new_page()
    pg.on('pageerror', lambda e: errs.append(str(e)[:200]))
    pg.on('console', lambda m: errs.append('console:' + m.text[:150]) if m.type == 'error' else None)
    pg.on('dialog', lambda d: d.accept())

    pg.clock.install(time=datetime(2026,10,24,10,0,0))

    pg.goto(f'http://127.0.0.1:{port}/index.html', wait_until='networkidle'); pg.wait_for_timeout(600)
    pg.click('[data-act="cloud-login"]'); pg.wait_for_timeout(400)
    pg.fill('input[name="email"]', 'test@example.com'); pg.fill('input[name="password"]', 'test@example.com')
    pg.click('form.modal-card button[type="submit"]'); pg.wait_for_timeout(2800)

    # ---------- 1. 编辑已有用药：字段回填 ----------
    pg.click('.nav-item[data-nav="meds"]'); pg.wait_for_timeout(1300)
    pg.click('[data-act="med-edit"]'); pg.wait_for_timeout(900)

    f = pg.evaluate("""() => {
      const q = s => document.querySelector(s);
      const qa = s => [...document.querySelectorAll(s)];
      const g = n => { const el = q('[name="' + n + '"]'); return el ? el.value : null; };
      return {
        hasOldTimes: !!q('[name="times"]'),
        count: g('doseTimes'), meal: g('mealTiming'),
        slots: qa('#time-slots input').map(i => i.value),
        labels: qa('#med-form .field > span').map(s => s.textContent.trim())
      };
    }""")
    rec('旧「服药时间」单行输入已移除', not f['hasOldTimes'], '已删除' if not f['hasOldTimes'] else '仍存在')
    rec('每日次数回填', f['count'] == '2', f'次数={f["count"]}')
    rec('饭前/饭后回填', f['meal'] == 'after', f'值={f["meal"]}')
    rec('每次时间回填 2 个', f['slots'] == ['08:00', '20:00'], str(f['slots']))
    rec('新增字段标签齐全', ('每日用药次数' in f['labels']) and ('饭前 / 饭后' in f['labels']) and ('每次时间' in f['labels']),
        str([x for x in f['labels'] if '次' in x or '饭' in x or '时间' in x]))
    rec('新增厂商 / 药品信息备注字段', ('药品厂商' in f['labels']) and ('药品信息备注' in f['labels']),
        str([x for x in f['labels'] if '厂商' in x or '备注' in x]))
    rec('原「备注」已删除', '备注' not in f['labels'],
        str([x for x in f['labels'] if '备注' in x]))
    pg.screenshot(path='design/shots/med-form-edit.png')

    # ---------- 2. 次数 3 → 时间槽变 3 个 ----------
    pg.select_option('[name="doseTimes"]', '3'); pg.wait_for_timeout(600)
    s3 = pg.evaluate("""() => {
      const q = s => document.querySelector(s);
      return {n: q('#time-slots').querySelectorAll('input').length,
              vals: [...q('#time-slots').querySelectorAll('input')].map(i => i.value)};
    }""")
    rec('次数改 3 → 3 个时间输入', s3['n'] == 3, str(s3['vals']))
    rec('保留已填时间并补默认值', s3['vals'][0] == '08:00' and s3['vals'][1] == '20:00', str(s3['vals']))

    # 改第二个时间 + 饭前 + 填厂商与药品信息备注
    pg.fill('#time-slots input[name="slot1"]', '13:30')
    pg.select_option('[name="mealTiming"]', 'before')
    pg.fill('[name="manufacturer"]', '辉瑞制药')
    pg.fill('[name="medInfo"]', '缓释胶囊 · 需避光')
    pg.screenshot(path='design/shots/med-form-3times.png')

    # ---------- 3. 保存并检查数据 ----------
    pg.click('#med-form button[type="submit"]'); pg.wait_for_timeout(2000)
    saved = pg.evaluate("""() => {
      const m = (window.__state || {}).meds ? null : null;
      return null;
    }""")
    # 从列表文本验证
    rowTxt = pg.evaluate("""() => {
      const row = document.querySelector('.med-row');
      return row ? row.innerText.replace(/\\n/g, ' / ') : null;
    }""")
    rec('列表显示次数+时间+餐前', rowTxt and '每天三次' in rowTxt and '13:30' in rowTxt and '餐前' in rowTxt, rowTxt or '')
    rec('列表显示厂商与药品信息', rowTxt and '辉瑞制药' in rowTxt and '缓释胶囊' in rowTxt, rowTxt or '')
    pg.screenshot(path='design/shots/med-list.png')

    # 重新打开确认持久化
    pg.click('[data-act="med-edit"]'); pg.wait_for_timeout(900)
    f2 = pg.evaluate("""() => {
      const q = s => document.querySelector(s);
      const g = n => { const el = q('[name="' + n + '"]'); return el ? el.value : null; };
      return {count: g('doseTimes'), meal: g('mealTiming'), mfr: g('manufacturer'), info: g('medInfo'),
              slots: [...q('#time-slots').querySelectorAll('input')].map(i => i.value)};
    }""")
    rec('保存后回填一致（时间按先后排序）', f2['count'] == '3' and f2['meal'] == 'before' and f2['slots'] == ['08:00', '12:00', '13:30'],
        json.dumps(f2, ensure_ascii=False))
    rec('保存后厂商/信息回填', f2['mfr'] == '辉瑞制药' and f2['info'] == '缓释胶囊 · 需避光',
        f'{f2["mfr"]} / {f2["info"]}')
    pg.screenshot(path='design/shots/med-form-saved.png')

    # ---------- 4. 按需疗程：隐藏次数/时间 ----------
    pg.select_option('[name="courseType"]', 'prn'); pg.wait_for_timeout(600)
    prn = pg.evaluate("""() => {
      const els = [...document.querySelectorAll('[data-timing]')];
      return els.map(e => getComputedStyle(e).display);
    }""")
    rec('按需疗程隐藏次数/时间', prn and all(d == 'none' for d in prn), str(prn))
    pg.screenshot(path='design/shots/med-form-prn.png')
    pg.select_option('[name="courseType"]', 'short'); pg.wait_for_timeout(500)

    # ---------- 5. 新增用药默认值 ----------
    pg.click('[data-act="close-modal"]'); pg.wait_for_timeout(500)
    pg.click('[data-act="med-new"]'); pg.wait_for_timeout(900)
    nf = pg.evaluate("""() => {
      const q = s => document.querySelector(s);
      return {count: q('[name="doseTimes"]').value, meal: q('[name="mealTiming"]').value,
              slots: [...q('#time-slots').querySelectorAll('input')].map(i => i.value)};
    }""")
    rec('新增默认 1 次 + 08:00 + 不限', nf['count'] == '1' and nf['slots'] == ['08:00'] and nf['meal'] == '',
        json.dumps(nf, ensure_ascii=False))
    pg.screenshot(path='design/shots/med-form-new.png')

    # 手机端看一眼
    ctx.close()
    mctx = br.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True, device_scale_factor=2)
    mp = mctx.new_page()
    mp.on('pageerror', lambda e: errs.append('[m]' + str(e)[:150]))
    mp.clock.install(time=datetime(2026,10,24,10,0,0))
    mp.goto(f'http://127.0.0.1:{port}/index.html', wait_until='networkidle'); mp.wait_for_timeout(600)
    mp.click('[data-act="cloud-login"]'); mp.wait_for_timeout(400)
    mp.fill('input[name="email"]', 'test@example.com'); mp.fill('input[name="password"]', 'test@example.com')
    mp.click('form.modal-card button[type="submit"]'); mp.wait_for_timeout(2600)
    mp.click('.mobile-tab:has-text("用药")'); mp.wait_for_timeout(1200)
    mp.click('[data-act="med-new"]'); mp.wait_for_timeout(800)
    m = mp.evaluate("""() => {
      const q = s => document.querySelector(s);
      const fs = q('#med-form');
      const r = fs.getBoundingClientRect();
      return {w: Math.round(r.width), ovf: document.documentElement.scrollWidth - innerWidth,
              slots: q('#time-slots').querySelectorAll('input').length};
    }""")
    rec('手机端面板无横向溢出', m['ovf'] <= 1 and m['slots'] == 1, json.dumps(m, ensure_ascii=False))
    mp.screenshot(path='design/shots/med-form-mobile.png')
    mctx.close()
    br.close()

srv.shutdown()
print('\n' + '=' * 56)
passed = sum(1 for s in steps if s['ok'])
print(f'用药面板：{passed}/{len(steps)} 通过')
print('JS/console 报错:', len(errs))
for e in errs[:6]: print('   ', e)
