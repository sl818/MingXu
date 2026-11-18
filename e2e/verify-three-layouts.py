"""三布局本地验证：wide 三区 / 三卡 / 完成态 / 右栏"""
import http.server, threading, json, socketserver, secrets, sys
from datetime import datetime
from playwright.sync_api import sync_playwright

DOC = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo'
USER = {'id': 1, 'email': 'test@example.com', 'display_name': '测试', 'is_admin': False}
sessions = {}
D = '2026-10-24'

HABITS = [
    {'id': 'h_med', 'name': '用药', 'icon': '💊', 'type': 'build', 'target': 2, 'unit': '次', 'color': '#2f6f5e', 'note': '', 'createdAt': '2026-10-23T00:00:00Z', 'pinned': True, 'med': True, 'archivedAt': ''},
    {'id': 'h_water', 'name': '喝水', 'icon': '💧', 'type': 'build', 'target': 8, 'unit': '杯', 'color': '#4c7f96', 'note': '', 'createdAt': '2026-10-23T00:00:00Z', 'pinned': True, 'archivedAt': ''},
    {'id': 'h_move', 'name': '运动', 'icon': '🏃', 'type': 'build', 'target': 1, 'unit': '次', 'color': '#b5733f', 'note': '', 'createdAt': '2026-10-23T00:00:00Z', 'pinned': True, 'archivedAt': ''},
    {'id': 'h_breathe', 'name': '478呼吸法', 'icon': '🌬️', 'type': 'build', 'target': 1, 'unit': '次', 'color': '#5b8f8a', 'note': '', 'createdAt': '2026-10-23T00:00:00Z', 'pinned': True, 'optional': True, 'archivedAt': ''},
    {'id': 'h_quit', 'name': '戒烟', 'icon': '🚭', 'type': 'quit', 'target': 1, 'unit': '次', 'color': '#9c5a5a', 'note': '', 'createdAt': '2026-10-23T00:00:00Z', 'pinned': False, 'archivedAt': ''},
]

checks = {}
for i, day in enumerate(['2026-10-19', '2026-10-20', '2026-10-21', '2026-10-22', '2026-10-23', '2026-10-24']):
    if i < 3:
        continue
    checks[day] = {'h_water': 8, 'h_move': 1, 'h_med': 2}
checks['2026-10-24'] = {'h_water': 12, 'h_move': 1, 'h_med': 2, 'h_breathe': 1}

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
        {'id': 't3', 'title': '晚上陪妈妈', 'note': '', 'tag': '生活', 'priority': '中', 'status': 'done', 'due': '2026-10-24', 'doneAt': D, 'createdAt': '2026-10-23T08:00:00Z'}
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

MEASURE = """() => {
  const q = s => document.querySelector(s);
  const qa = s => [...document.querySelectorAll(s)];
  const box = e => { if (!e) return null; const r = e.getBoundingClientRect();
    return {w: Math.round(r.width), h: Math.round(r.height), x: Math.round(r.x), right: Math.round(r.right)}; };
  const over = [];
  document.querySelectorAll('.main *, .sidebar *, .rail *').forEach(e => {
    const r = e.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) return;
    if (r.right > innerWidth + 1 || r.left < -1)
      over.push({cls: (e.className && e.className.baseVal !== undefined ? e.className.baseVal : e.className || e.tagName).toString().slice(0, 32)});
  });
  return {
    layout: document.documentElement.dataset.layout,
    app: box(q('.app')), sidebar: box(q('.sidebar')), main: box(q('.main')),
    rail: box(q('.rail')), todayGrid: getComputedStyle(q('.today-grid')).display,
    statCards: qa('.sh-card').length,
    navItems: qa('.nav-item').length,
    navGroups: qa('.nav-group').map(e => e.textContent.trim()),
    sideUser: q('.side-user') ? getComputedStyle(q('.side-user')).display : null,
    railCards: qa('.rail-card').length,
    heroLeft: qa('.hero').length,
    heroWeek: !!q('.hero-week'),
    heroRing: !!q('.hero-ring'),
    heroH: q('.hero') ? Math.round(q('.hero').getBoundingClientRect().height) : 0,
    heroWeekW: q('.hero-week') ? Math.round(q('.hero-week').getBoundingClientRect().width) : 0,
    hwDays: qa('.hw-day').length,
    doneBtns: qa('.vital-btn.done').map(e => e.textContent.trim()),
    disabledBtns: qa('.vital-btn[disabled]').length,
    shrRing: !!q('.sh-ring .ring'),
    vitalCards: qa('.vital-card').map(e => { const r = e.getBoundingClientRect(); const a = e.querySelector('.vital-actions'); return {h: Math.round(r.height), btnY: a ? Math.round(a.getBoundingClientRect().y) : null}; }),
    ovf: document.documentElement.scrollWidth - innerWidth,
    overCount: over.length, over: over.slice(0, 4)
  };
}"""

steps = []
def rec(name, ok, detail=''):
    steps.append({'name': name, 'ok': bool(ok), 'detail': detail})
    print(('PASS  ' if ok else 'FAIL  ') + name + (('  | ' + detail) if detail else ''))

with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)
    errs = []
    for layout in ('wide', 'top', 'side'):
        ctx = br.new_context(viewport={'width': 1440, 'height': 900}, device_scale_factor=2)
        pg = ctx.new_page()
        pg.on('pageerror', lambda e: errs.append(f'[{layout}] {e}'[:200]))
        pg.on('console', lambda m: errs.append(f'[{layout}] console: {m.text[:150]}') if m.type == 'error' else None)
        pg.clock.install(time=datetime(2026, 10, 24, 10, 0, 0))
        pg.add_init_script(f"try{{localStorage.setItem('lifeboard.layout','{layout}');localStorage.setItem('lifeboard.skin','paper');localStorage.setItem('lifeboard.theme.mode','light');}}catch(e){{}}")
        pg.goto(f'http://127.0.0.1:{port}/index.html', wait_until='networkidle'); pg.wait_for_timeout(700)
        pg.click('[data-act="cloud-login"]'); pg.wait_for_timeout(500)
        pg.fill('input[name="email"]', 'test@example.com'); pg.fill('input[name="password"]', 'test@example.com')
        pg.click('form.modal-card button[type="submit"]'); pg.wait_for_timeout(3000)

        m = pg.evaluate(MEASURE)
        print(f'\n========== {layout} ==========')
        print(json.dumps({k: v for k, v in m.items() if k not in ('over',)}, ensure_ascii=False))
        if m['over']: print('  over:', json.dumps(m['over'], ensure_ascii=False))

        rec(f'[{layout}] 深色 Hero 已恢复', m['heroLeft'] == 1 and m['heroWeek'] and m['heroRing'],
            f'Hero {m["heroH"]}px')
        rec(f'[{layout}] 本周战报 7 天柱', m['hwDays'] == 7 and m['heroWeekW'] > 120,
            f'{m["hwDays"]} 柱 / 宽 {m["heroWeekW"]}px')
        rec(f'[{layout}] 无溢出且无越界', m['ovf'] <= 1 and m['overCount'] == 0,
            f'横溢{m["ovf"]} 越界{m["overCount"]}')
        rec(f'[{layout}] 无横向溢出', m['ovf'] <= 1 and m['overCount'] == 0, f'横溢{m["ovf"]} 越界{m["overCount"]}')
        rec(f'[{layout}] 完成态按钮为可撤销', len(m['doneBtns']) > 0 and m['disabledBtns'] == 0,
            f'{len(m["doneBtns"])} 个已完成按钮 / {m["disabledBtns"]} 个禁用')
        if layout == 'wide':
            rec('[wide] 三区分栏生效', m['todayGrid'] == 'grid' and m['rail'] is not None, f'grid={m["todayGrid"]}')
            rec('[wide] 右栏 280', m['rail'] and 270 <= m['rail']['w'] <= 300, f'{m["rail"]["w"] if m["rail"] else "无"}px')
            rec('[wide] 左栏 228', m['sidebar'] and 220 <= m['sidebar']['w'] <= 240, f'{m["sidebar"]["w"] if m["sidebar"] else "无"}px')
            rec('[wide] 导航分组', m['navGroups'] == ['记录', '回顾'], str(m['navGroups']))
            rec('[wide] 账户卡片显示', m['sideUser'] == 'block', str(m['sideUser']))
            rec('[wide] 右栏卡片存在', m['railCards'] >= 1, f'{m["railCards"]} 张（概览已并入 Hero）')
        else:
            rec(f'[{layout}] 无右栏', m['rail'] is None or getattr(m['rail'], 'w', 0) == 0, '')
        pg.screenshot(path=f'design/shots/v3-{layout}.png', full_page=False)
        pg.wait_for_timeout(400)
        # 滚到中部再截一张
        pg.evaluate("window.scrollTo(0, 420)"); pg.wait_for_timeout(400)
        pg.screenshot(path=f'design/shots/v3-{layout}-b.png')
        ctx.close()
    br.close()

srv.shutdown()
print('\n' + '=' * 56)
passed = sum(1 for s in steps if s['ok'])
print(f'三布局：{passed}/{len(steps)} 通过')
print('JS/console 报错:', len(errs))
for e in errs[:8]: print('   ', e)
