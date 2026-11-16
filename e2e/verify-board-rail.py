"""待办页右侧信息栏（迷你月历 + 接下来 7 天）验证：显示条件 / 日期筛选 / 定位卡片 / 不触发云保存"""
import http.server, threading, json, socketserver, secrets, sys
from datetime import datetime
from playwright.sync_api import sync_playwright

DOC = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo'
USER = {'id': 1, 'email': 'test@example.com', 'display_name': '测试', 'is_admin': False}
sessions = {}
PORT = 38546
D = '2026-10-24'

TASKS = [
    {'id': 't1', 'title': '今天要做的事', 'note': '', 'tag': '生活', 'priority': '中', 'status': 'todo', 'due': D, 'createdAt': D + 'T08:00:00Z'},
    {'id': 't2', 'title': '今天第二条', 'note': '备注', 'tag': '健康', 'priority': '高', 'status': 'todo', 'due': D, 'createdAt': D + 'T09:00:00Z'},
    {'id': 't3', 'title': '逾期那条', 'note': '', 'tag': '工作', 'priority': '中', 'status': 'doing', 'due': '2026-10-23', 'createdAt': D + 'T07:00:00Z'},
    {'id': 't4', 'title': '后天到期', 'note': '', 'tag': '学习', 'priority': '低', 'status': 'todo', 'due': '2026-10-26', 'createdAt': D + 'T07:00:00Z'},
    {'id': 't5', 'title': '大后天到期', 'note': '', 'tag': '健康', 'priority': '中', 'status': 'todo', 'due': '2026-10-28', 'createdAt': D + 'T07:00:00Z'},
    {'id': 't6', 'title': '没有截止日', 'note': '', 'tag': '其他', 'priority': '低', 'status': 'todo', 'due': '', 'createdAt': D + 'T07:00:00Z'},
    {'id': 't7', 'title': '已经做完的', 'note': '', 'tag': '生活', 'priority': '中', 'status': 'done', 'due': '2026-10-22', 'createdAt': D + 'T07:00:00Z', 'doneAt': D},
    {'id': 't8', 'title': '取消掉的', 'note': '', 'tag': '生活', 'priority': '低', 'status': 'cancelled', 'due': '2026-10-24', 'createdAt': D + 'T07:00:00Z'},
]

HABITS = [
    {'id': 'h_med', 'name': '用药', 'icon': '💊', 'type': 'build', 'target': 1, 'unit': '次',
     'color': '#2f6f5e', 'note': '', 'createdAt': '2026-10-23T00:00:00Z', 'pinned': True, 'med': True, 'archivedAt': ''},
]

def make_board():
    return {'data': {'version': 2, 'view': 'board', 'habits': HABITS, 'checks': {D: {}},
                     'notes': {}, 'moods': {}, 'events': [], 'meds': [], 'doses': {},
                     'bodyProfile': {'age': 30, 'height': 170}, 'weights': [], 'essays': [],
                     'tasks': [dict(t) for t in TASKS]}, 'rev': 5}

board = make_board()
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
    goto_board(pg)

def goto_board(pg):
    pg.evaluate("""() => {
      const b = document.querySelector('.nav-item[data-nav="board"]') ||
                document.querySelector('.mobile-tab[data-nav="board"]');
      if (b) b.click();
    }""")
    pg.wait_for_timeout(800)

RAIL = """() => {
  const q = s => document.querySelector(s), qa = s => [...document.querySelectorAll(s)];
  const rail = q('.board-rail');
  return {
    railShown: rail ? getComputedStyle(rail).display !== 'none' : false,
    railW: rail ? Math.round(rail.getBoundingClientRect().width) : 0,
    mainW: Math.round(q('#main').getBoundingClientRect().width),
    cards: qa('.board-rail .rail-card').length,
    calDays: qa('.bcal-d:not(.is-blank)').length,
    calMarked: qa('.bcal-d.has').map(e => e.textContent.trim()),
    calToday: qa('.bcal-d.is-today').map(e => e.textContent.trim()),
    calOn: qa('.bcal-d.on').map(e => e.textContent.trim()),
    upItems: qa('.bup-i').map(e => e.textContent.trim()),
    upGroups: qa('.bup-g').map(e => e.textContent.replace(/\\s+/g, ' ').trim()),
    overItems: qa('.bup-i.is-over').map(e => e.textContent.trim()),
    filter: (q('.board-filter') || {}).textContent || '',
    counts: qa('.col').map(c => c.querySelector('.col-count').textContent),
    todoTasks: qa('.col-body[data-status="todo"] .task').length,
    ovf: document.documentElement.scrollWidth - innerWidth
  };
}"""

with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)

    # ---------- 宽屏：右栏显示 ----------
    ctx = br.new_context(viewport={'width': 1800, 'height': 1000})
    pg = ctx.new_page()
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    login(pg)
    r = pg.evaluate(RAIL)
    rec('宽屏 1800 → 右栏显示', r['railShown'], 'display=%s' % r['railShown'])
    rec('右栏宽 300', r['railW'] == 300, '%dpx' % r['railW'])
    rec('主区加宽到 1680', r['mainW'] == 1680, '%dpx' % r['mainW'])
    rec('右栏两张卡', r['cards'] == 2, '%d 张' % r['cards'])
    rec('月历渲染 31 天', r['calDays'] == 31, '%d 天' % r['calDays'])
    rec('今天有今日标记', r['calToday'] == ['24'], str(r['calToday']))
    rec('有任务的日期打点', r['calMarked'] == ['23', '24', '26', '28'], str(r['calMarked']))
    rec('接下来清单跳过已完成/已取消', '已经做完的' not in ' '.join(r['upItems']) and '取消掉的' not in ' '.join(r['upItems']), str(r['upItems']))
    rec('逾期单独成组', r['upGroups'][0].startswith('已逾期') and r['overItems'] == ['10/23逾期那条'], str(r['upGroups'][:2]))
    rec('分组含今天/明天/周X', any(g.startswith('今天') for g in r['upGroups']) and any(g.startswith('周') for g in r['upGroups']), str(r['upGroups']))
    rec('无截止日不进清单', '没有截止日' not in ' '.join(r['upItems']), '')
    pg.screenshot(path='design/shots/board-rail-1800.png')

    # ---------- 点日期筛选 ----------
    base_save = save_count['n']
    pg.click('.bcal-d[data-day="2026-10-24"]'); pg.wait_for_timeout(600)
    r2 = pg.evaluate(RAIL)
    rec('点 24 号 → 出现筛选提示条', '今天' in r2['filter'], r2['filter'].strip())
    rec('筛选后待办列只剩 2 条', r2['todoTasks'] == 2, '%d 条' % r2['todoTasks'])
    rec('筛选后各列计数同步', r2['counts'][:2] == ['2', '0'], str(r2['counts']))
    rec('月历该日高亮', r2['calOn'] == ['24'], str(r2['calOn']))
    rec('筛选不触发云保存', save_count['n'] == base_save, 'save %d → %d' % (base_save, save_count['n']))
    pg.screenshot(path='design/shots/board-rail-filter.png')

    # 再点同一天 → 取消
    pg.click('.bcal-d[data-day="2026-10-24"]'); pg.wait_for_timeout(600)
    r3 = pg.evaluate(RAIL)
    rec('再点同一天 → 取消筛选', r3['filter'] == '' and r3['todoTasks'] == 5, 'todo=%d' % r3['todoTasks'])

    # ---------- 从右栏定位卡片 ----------
    pg.click('.bcal-d[data-day="2026-10-26"]'); pg.wait_for_timeout(500)
    r4 = pg.evaluate(RAIL)
    rec('点 26 号 → 只剩 1 条', r4['todoTasks'] == 1, '%d 条' % r4['todoTasks'])
    pg.click('.bup-i:has-text("今天要做的事")'); pg.wait_for_timeout(900)
    focused = pg.evaluate("""() => ({
      f: document.querySelectorAll('.task.is-focus').length > 0,
      id: (document.querySelector('.task.is-focus') || {}).dataset ? document.querySelector('.task.is-focus').dataset.id : '',
      filter: (document.querySelector('.board-filter') || {}).textContent || ''
    })""")
    rec('点右栏条目 → 自动解除筛选并高亮卡片', focused['f'] and focused['id'] == 't1' and focused['filter'] == '', str(focused))
    pg.screenshot(path='design/shots/board-rail-focus.png')

    # 筛选条 × 清除
    pg.click('.bcal-d[data-day="2026-10-24"]'); pg.wait_for_timeout(500)
    pg.click('.bf-clear'); pg.wait_for_timeout(500)
    r5 = pg.evaluate(RAIL)
    rec('提示条 ✕ 可清除筛选', r5['filter'] == '' and r5['todoTasks'] == 5, 'todo=%d' % r5['todoTasks'])

    # 离开页面后筛选自动重置
    pg.click('.bcal-d[data-day="2026-10-24"]'); pg.wait_for_timeout(500)
    pg.evaluate("""() => {
      const b = document.querySelector('.nav-item[data-nav="today"]') ||
                document.querySelector('.mobile-tab[data-nav="today"]');
      if (b) b.click();
    }""")
    pg.wait_for_timeout(800)
    goto_board(pg)
    r6 = pg.evaluate(RAIL)
    rec('离开待办页后筛选重置', r6['filter'] == '' and r6['todoTasks'] == 5, 'todo=%d' % r6['todoTasks'])
    rec('无 JS 异常', not errs, str(errs[:2]))
    ctx.close()

    # ---------- 窄屏 1440：右栏隐藏、看板满宽 ----------
    ctx = br.new_context(viewport={'width': 1440, 'height': 950})
    pg = ctx.new_page()
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    login(pg)
    r = pg.evaluate(RAIL)
    rec('1440 → 右栏隐藏', not r['railShown'], 'display=%s' % r['railShown'])
    rec('1440 → 主区不加宽（1200）', r['mainW'] == 1200, '%dpx' % r['mainW'])
    rec('1440 → 无横向溢出', r['ovf'] <= 1, 'ovf=%d' % r['ovf'])
    rec('1440 → 无 JS 异常', not errs, str(errs[:1]))
    pg.screenshot(path='design/shots/board-1440.png')
    ctx.close()

    # ---------- 手机 390：右栏隐藏 ----------
    ctx = br.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True, device_scale_factor=2)
    pg = ctx.new_page()
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    login(pg)
    goto_board(pg)
    r = pg.evaluate(RAIL)
    rec('[手机] 右栏隐藏', not r['railShown'], '')
    rec('[手机] 无横向溢出', r['ovf'] <= 1, 'ovf=%d' % r['ovf'])
    rec('[手机] 无 JS 异常', not errs, str(errs[:1]))
    ctx.close()

    br.close()

srv.shutdown()
ok = sum(1 for r in results if r[1])
print('\n待办右栏验证：%d/%d 通过' % (ok, len(results)))
if ok != len(results):
    print('失败项：')
    for n, o, d in results:
        if not o: print('  -', n, '|', d)
    sys.exit(1)
