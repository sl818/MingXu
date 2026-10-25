"""手机端全页面拥挤/溢出扫描：8 个视图逐页检测"""
import http.server, threading, json, socketserver, secrets
from playwright.sync_api import sync_playwright

DOC = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo'
USER = {'id': 1, 'email': 't@t.top', 'display_name': 'T', 'is_admin': False}
sessions = {}

HABITS = [
    {'id': 'h_med', 'name': '用药', 'icon': '💊', 'type': 'build', 'target': 1, 'unit': '次', 'color': '#2f6f5e', 'note': '', 'createdAt': '2026-10-23T00:00:00Z', 'pinned': True, 'med': True, 'archivedAt': ''},
    {'id': 'h_water', 'name': '喝水', 'icon': '💧', 'type': 'build', 'target': 8, 'unit': '杯', 'color': '#4c7f96', 'note': '', 'createdAt': '2026-10-23T00:00:00Z', 'pinned': True, 'archivedAt': ''},
    {'id': 'h_move', 'name': '运动', 'icon': '🏃', 'type': 'build', 'target': 1, 'unit': '次', 'color': '#b5733f', 'note': '', 'createdAt': '2026-10-23T00:00:00Z', 'pinned': True, 'archivedAt': ''},
    {'id': 'h_stand', 'name': '站立', 'icon': '🧍', 'type': 'build', 'target': 8, 'unit': '次', 'color': '#7a6a9c', 'note': '', 'createdAt': '2026-10-23T00:00:00Z', 'pinned': True, 'archivedAt': ''},
    {'id': 'h_quit', 'name': '戒烟', 'icon': '🚭', 'type': 'quit', 'target': 1, 'unit': '次', 'color': '#9c5a5a', 'note': '', 'createdAt': '2026-10-23T00:00:00Z', 'pinned': True, 'archivedAt': ''},
    {'id': 'h_read', 'name': '阅读', 'icon': '📖', 'type': 'build', 'target': 1, 'unit': '次', 'color': '#5b8f8a', 'note': '', 'createdAt': '2026-10-23T00:00:00Z', 'pinned': True, 'archivedAt': ''},
    {'id': 'h_vit', 'name': '维生素', 'icon': '🌿', 'type': 'build', 'target': 2, 'unit': '次', 'color': '#8a7a3c', 'note': '', 'createdAt': '2026-10-23T00:00:00Z', 'pinned': True, 'archivedAt': ''},
    {'id': 'h_breath', 'name': '478呼吸法', 'icon': '🌬️', 'type': 'build', 'target': 1, 'unit': '次', 'color': '#5b8f8a', 'note': '', 'createdAt': '2026-10-23T00:00:00Z', 'pinned': True, 'optional': True, 'archivedAt': ''},
]

tasks = [
    {'id': 't1', 'title': '收被单被子', 'note': '记得翻面晒一下，下午三点前收回来比较好', 'tag': '生活', 'priority': '中', 'status': 'todo', 'due': '2026-10-24', 'createdAt': '2026-10-23T08:00:00Z'},
    {'id': 't2', 'title': '做 20 个俯卧撑', 'note': '', 'tag': '健康', 'priority': '高', 'status': 'todo', 'due': '2026-10-24', 'createdAt': '2026-10-23T08:00:00Z'},
    {'id': 't3', 'title': '阅读 30 分钟', 'note': '', 'tag': '学习', 'priority': '中', 'status': 'doing', 'due': '2026-10-24', 'createdAt': '2026-10-23T08:00:00Z'},
    {'id': 't4', 'title': '给妈妈打电话', 'note': '', 'tag': '生活', 'priority': '高', 'status': 'done', 'due': '2026-10-23', 'createdAt': '2026-10-22T08:00:00Z'},
]

board = {'data': {
    'version': 2, 'view': 'today', 'habits': HABITS,
    'checks': {'2026-10-22': {'h_water': 8, 'h_move': 1}, '2026-10-23': {'h_water': 6, 'h_breath': 1}, '2026-10-24': {'h_water': 12, 'h_move': 1}},
    'notes': {}, 'moods': {'2026-10-24': 'happy', '2026-10-23': 'ok'},
    'events': [], 'meds': [
        {'id': 'm1', 'name': '维生素D', 'dose': '1 粒', 'times': ['08:00'], 'startDate': '2026-10-01', 'endDate': '2026-12-31', 'note': '饭后服用'},
    ], 'doses': {},
    'bodyProfile': {'age': 30, 'height': 170},
    'weights': [{'id': 'w1', 'date': '2026-10-24', 'kg': 68.4}, {'id': 'w2', 'date': '2026-10-23', 'kg': 68.8}],
    'essays': [{'id': 'e1', 'title': '今天的天气', 'body': '早上下了点雨，下午放晴了。', 'date': '2026-10-24', 'mood': 'happy', 'tags': ['生活'], 'createdAt': '2026-10-24T09:00:00Z'}],
    'tasks': tasks}, 'rev': 5}


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
            n = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(n) or b'{}')
            if a == 'login':
                sid = secrets.token_hex(8); sessions[sid] = USER
                self._j({'ok': True, 'user': USER, 'csrf': 'x'}, eh={'Set-Cookie': 'sid=' + sid + '; Path=/'})
            elif a in ('save', 'force'):
                board['data'] = body['data']; board['rev'] += 1
                self._j({'ok': True, 'rev': board['rev']})
            else: self._j({'ok': False, 'error': '?'}, 404)
        else:
            self.send_response(405); self.end_headers()


class TS(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


srv = TS(('127.0.0.1', 0), H)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()

SCAN = """() => {
  const over = [];
  document.querySelectorAll('.main *, .mobile-tabbar *, .toast, .sync-indicator').forEach(e => {
    const r = e.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) return;
    if (r.right > innerWidth + 1 || r.left < -1) {
      over.push({cls: (e.className && e.className.baseVal !== undefined ? e.className.baseVal : e.className || e.tagName).toString().slice(0, 40),
                 l: Math.round(r.left), r: Math.round(r.right), w: Math.round(r.width)});
    }
  });
  // 文字被裁切（容器内文本溢出但未换行）
  const clipped = [];
  document.querySelectorAll('.main *').forEach(e => {
    if (e.children.length) return;
    if (!(e.innerText || '').trim()) return;
    if (e.scrollWidth > e.clientWidth + 2 && getComputedStyle(e).overflow !== 'visible') {
      clipped.push({cls: (e.className || e.tagName).toString().slice(0, 34), t: e.innerText.trim().slice(0, 22),
                    sw: e.scrollWidth, cw: e.clientWidth});
    }
  });
  return {vw: innerWidth, hOverflow: document.documentElement.scrollWidth - innerWidth,
          over: over.slice(0, 6), overCount: over.length,
          clipped: clipped.slice(0, 6), clippedCount: clipped.length};
}"""

with sync_playwright() as p:
    b = p.chromium.launch(channel='chrome', headless=True)
    for w in (390, 360):
        ctx = b.new_context(viewport={'width': w, 'height': 844}, device_scale_factor=2,
                            is_mobile=True, has_touch=True,
                            user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1')
        pg = ctx.new_page()
        errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.goto(f'http://127.0.0.1:{port}/index.html', wait_until='networkidle')
        pg.wait_for_timeout(700)
        pg.click('[data-act="cloud-login"]', timeout=5000); pg.wait_for_timeout(500)
        pg.fill('input[name="email"]', 't@t.top'); pg.fill('input[name="password"]', '12345678')
        pg.click('form.modal-card button[type="submit"]'); pg.wait_for_timeout(2800)

        views = [('today', '.mobile-tab:has-text("今日")'),
                 ('board', '.mobile-tab:has-text("待办")'),
                 ('habits', '.mobile-tab:has-text("习惯")'),
                 ('stats', '.mobile-tab:has-text("统计")'),
                 ('more', '.mobile-tab:has-text("更多")')]
        print(f"\n########## 视口 {w}px ##########")
        for name, sel in views:
            try:
                pg.click(sel, timeout=5000); pg.wait_for_timeout(1100)
            except Exception as e:
                print(name, 'nav err', e); continue
            r = pg.evaluate(SCAN)
            flag = 'OK' if (r['overCount'] == 0 and r['hOverflow'] <= 0 and r['clippedCount'] == 0) else '⚠'
            print(f"[{flag}] {name}: 溢出元素 {r['overCount']} · 页面横溢 {r['hOverflow']} · 文字裁切 {r['clippedCount']}")
            if r['over']: print('     over:', json.dumps(r['over'], ensure_ascii=False))
            if r['clipped']: print('     clipped:', json.dumps(r['clipped'], ensure_ascii=False))
            pg.screenshot(path=f'design/shots/scan-{w}-{name}.png')

        # 更多页里的子页面
        if w == 390:
            for sub, label in [('calendar', '日历'), ('weight', '体重'), ('essays', '随笔'), ('settings', '设置')]:
                try:
                    pg.click('.mobile-tab:has-text("更多")'); pg.wait_for_timeout(700)
                    pg.click(f'.more-card[data-nav="{sub}"]', timeout=5000); pg.wait_for_timeout(1100)
                    r = pg.evaluate(SCAN)
                    flag = 'OK' if (r['overCount'] == 0 and r['hOverflow'] <= 0 and r['clippedCount'] == 0) else '⚠'
                    print(f"[{flag}] {label}: 溢出元素 {r['overCount']} · 页面横溢 {r['hOverflow']} · 文字裁切 {r['clippedCount']}")
                    if r['over']: print('     over:', json.dumps(r['over'], ensure_ascii=False))
                    if r['clipped']: print('     clipped:', json.dumps(r['clipped'], ensure_ascii=False))
                    pg.screenshot(path=f'design/shots/scan-{w}-{sub}.png')
                except Exception as e:
                    print(label, 'err', e)
        print('pageerrors:', errs)
        ctx.close()
    b.close()

srv.shutdown()
