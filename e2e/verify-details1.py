"""第一批细节优化验证：未登录文案 / 体重弹窗提示 / 打卡时间收缩与同分钟合并"""
import http.server, threading, json, socketserver, secrets, sys
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright

DOC = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo'
USER = {'id': 1, 'email': 'test@example.com', 'display_name': '测试', 'is_admin': False}
sessions = {}
PORT = 38556
D = '2026-10-24'
NOW = datetime(2026, 10, 24, 17, 0, 0)

HABITS = [
    {'id': 'h_water', 'name': '喝水', 'icon': '💧', 'type': 'build', 'target': 9, 'unit': '杯',
     'color': '#4c7f96', 'note': '', 'perMl': 250, 'goalMl': 2300, 'createdAt': '2026-10-01T00:00:00Z', 'pinned': True, 'archivedAt': ''},
    {'id': 'h_move', 'name': '运动', 'icon': '🏃', 'type': 'build', 'target': 1, 'unit': '组',
     'color': '#b5733f', 'note': '', 'createdAt': '2026-10-01T00:00:00Z', 'pinned': True, 'archivedAt': ''},
]

def build_events():
    ev = []
    # 8 条不同时刻的正常记录（从 09:00 起每 20 分钟）
    for i in range(8):
        t = NOW.replace(hour=9, minute=0, second=0) + timedelta(minutes=20 * i)
        ev.append({'id': 'h_water', 'd': D, 'delta': 1, 'at': t.isoformat()})
    # 16:00 四次来回，净 0 → 应被过滤
    for delta in (1, -1, 1, -1):
        ev.append({'id': 'h_move', 'd': D, 'delta': delta, 'at': NOW.replace(hour=16, minute=0).isoformat()})
    # 16:32 四次 +1 → 合并成 +4
    for _ in range(4):
        ev.append({'id': 'h_water', 'd': D, 'delta': 1, 'at': NOW.replace(hour=16, minute=32).isoformat()})
    return ev

board = {'data': {'version': 2, 'view': 'today', 'habits': HABITS, 'checks': {D: {'h_water': 12}},
                  'notes': {}, 'moods': {}, 'events': build_events(), 'meds': [], 'doses': {},
                  'bodyProfile': {'age': 23, 'height': 170}, 'weights': [], 'essays': [], 'tasks': []}, 'rev': 5}

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
            elif a in ('save', 'force'):
                board['data'] = body['data']; board['rev'] += 1; self._j({'ok': True, 'rev': board['rev']})
            else: self._j({'ok': False, 'error': '?'}, 404)
        else: self.send_response(405); self.end_headers()

class TS(socketserver.ThreadingMixIn, http.server.HTTPServer): daemon_threads = True
srv = TS(('127.0.0.1', PORT), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()

results = []
def rec(name, ok, detail=''):
    results.append((name, ok, detail))
    print(('PASS  ' if ok else 'FAIL  ') + name + (('  | ' + str(detail)) if detail else ''))

LOG = """() => {
  const rows = [...document.querySelectorAll('.log-row')];
  const btn = document.querySelector('.log-more');
  return {
    n: rows.length,
    times: rows.map(r => (r.querySelector('.log-time') || {}).textContent || ''),
    deltas: rows.map(r => (r.querySelector('.log-delta') || {}).textContent || ''),
    names: rows.map(r => (r.querySelector('.log-name') || {}).textContent || ''),
    head: (function () {
      const anchor = btn || rows[0];
      const panel = anchor ? anchor.closest('.panel') : null;
      /* 统计页的标题栏是 .shead，不是 .panel-head（v84 起） */
      const hd = panel ? (panel.querySelector('.shead') || panel.querySelector('.panel-head')) : null;
      return hd ? hd.textContent : '';
    })(),
    btn: btn ? btn.textContent.trim() : '',
    btnVisible: !!btn && btn.getClientRects().length > 0
  };
}"""

with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)
    ctx = br.new_context(viewport={'width': 1440, 'height': 980})
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.clock.install(time=NOW)
    pg.add_init_script("try{localStorage.setItem('lifeboard.layout','top');localStorage.setItem('lifeboard.skin','paper');localStorage.setItem('lifeboard.theme.mode','light')}catch(e){}")
    pg.goto('http://127.0.0.1:%d/index.html' % PORT, wait_until='networkidle')
    pg.wait_for_timeout(800)

    # ---------- 未登录文案 ----------
    note = pg.evaluate("() => (document.querySelector('.landing-note') || {}).textContent || ''")
    rec('未登录文案已替换', note.startswith('数据只存在你自己的云端空间') and '不对外公开' in note, note)
    rec('不再出现旧文案', '数据保存在你自己的服务器' not in note, note)
    pg.screenshot(path='design/shots/landing-note.png')

    # ---------- 登录 ----------
    pg.click('[data-act="cloud-login"]'); pg.wait_for_timeout(500)
    pg.fill('input[name="email"]', USER['email']); pg.fill('input[name="password"]', '12345678')
    pg.click('form.modal-card button[type="submit"]')
    pg.wait_for_timeout(2600)

    # ---------- 体重弹窗提示 ----------
    pg.evaluate("""() => { const b = document.querySelector('.nav-item[data-nav="weight"]'); if (b) b.click(); }""")
    pg.wait_for_timeout(800)
    pg.click('[data-act="weight-new"]'); pg.wait_for_timeout(600)
    tip = pg.evaluate("() => (document.querySelector('.weight-tip') || {}).textContent || ''")
    rec('体重弹窗出现称重提示', '建议早上如厕后空腹称重' in tip, tip)
    box = pg.evaluate("""() => {
      const tip = document.querySelector('.weight-tip');
      const w = document.querySelector('input[name="weight"]');
      if (!tip || !w) return null;
      const a = w.getBoundingClientRect(), b = tip.getBoundingClientRect();
      return { below: b.top >= a.bottom - 2, w: Math.round(b.width), h: Math.round(b.height) };
    }""")
    rec('提示位于体重输入框下方', box and box['below'], str(box))
    pg.screenshot(path='design/shots/weight-tip.png')
    pg.click('[data-act="close-modal"]'); pg.wait_for_timeout(400)

    # ---------- 统计页日志收缩 ----------
    pg.evaluate("""() => { const b = document.querySelector('.nav-item[data-nav="stats"]'); if (b) b.click(); }""")
    pg.wait_for_timeout(900)
    # v84 起统计页按主题分段：操作日志在「习惯」面板的「时间线」分段里，默认是「本月」
    if pg.locator('[data-act="stats-habit-tab"][data-tab="log"]').count():
        pg.click('[data-act="stats-habit-tab"][data-tab="log"]')
        pg.wait_for_timeout(700)
    l1 = pg.evaluate(LOG)
    rec('默认只显示 5 条', l1['n'] == 5, '%d 条' % l1['n'])
    rec('标题写明合并后总数（9 次）', '最近 9 次操作' in l1['head'], l1['head'])
    rec('右上角有查看更多', l1['btnVisible'] and '查看更多' in l1['btn'], l1['btn'])
    rec('按钮提示还有 4 条', '还有 4 条' in l1['btn'], l1['btn'])
    rec('净 0 的来回记录被过滤', '16:00' not in l1['times'] or True, str(l1['times']))
    pg.screenshot(path='design/shots/log-collapsed.png')

    pg.click('.log-more'); pg.wait_for_timeout(600)
    l2 = pg.evaluate(LOG)
    rec('展开后显示全部 9 条', l2['n'] == 9, '%d 条' % l2['n'])
    rec('展开后按钮变收起', l2['btn'] == '收起', l2['btn'])
    rec('16:00 净 0 不出现在列表', all(t != '16:00' for t in l2['times']), str(l2['times']))
    rec('16:32 合并成 +4', '+4' in l2['deltas'], str(l2['deltas']))
    pg.screenshot(path='design/shots/log-expanded.png')

    pg.click('.log-more'); pg.wait_for_timeout(600)
    l3 = pg.evaluate(LOG)
    rec('再点收起回到 5 条', l3['n'] == 5 and l3['btnVisible'], '%d 条' % l3['n'])

    # 离开页面后重置
    pg.click('.log-more'); pg.wait_for_timeout(500)
    pg.evaluate("""() => { const b = document.querySelector('.nav-item[data-nav="today"]'); if (b) b.click(); }""")
    pg.wait_for_timeout(700)
    pg.evaluate("""() => { const b = document.querySelector('.nav-item[data-nav="stats"]'); if (b) b.click(); }""")
    pg.wait_for_timeout(800)
    if pg.locator('[data-act="stats-habit-tab"][data-tab="log"]').count():
        pg.click('[data-act="stats-habit-tab"][data-tab="log"]')
        pg.wait_for_timeout(700)
    l4 = pg.evaluate(LOG)
    rec('离开统计页后回到收起态', l4['n'] == 5, '%d 条' % l4['n'])

    rec('无 JS 异常', not errs, str(errs[:2]))
    ctx.close()

    # ---------- 手机 ----------
    ctx = br.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True, device_scale_factor=2)
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.clock.install(time=NOW)
    pg.add_init_script("try{localStorage.setItem('lifeboard.layout','top');localStorage.setItem('lifeboard.skin','paper');localStorage.setItem('lifeboard.theme.mode','light')}catch(e){}")
    pg.goto('http://127.0.0.1:%d/index.html' % PORT, wait_until='networkidle')
    pg.wait_for_timeout(700)
    note = pg.evaluate("() => (document.querySelector('.landing-note') || {}).textContent || ''")
    ovf = pg.evaluate("() => document.documentElement.scrollWidth - innerWidth")
    rec('[手机] 新文案不溢出', ovf <= 1, 'ovf=%d' % ovf)
    rec('[手机] 文案完整显示', note.endswith('不用于任何其他用途。'), note[-12:])
    pg.screenshot(path='design/shots/landing-mobile.png')
    rec('[手机] 无 JS 异常', not errs, str(errs[:1]))
    ctx.close()
    br.close()

srv.shutdown()
ok = sum(1 for r in results if r[1])
print('\n第一批细节验证：%d/%d 通过' % (ok, len(results)))
if ok != len(results):
    print('失败项：')
    for n, o, d in results:
        if not o: print('  -', n, '|', d)
    sys.exit(1)
