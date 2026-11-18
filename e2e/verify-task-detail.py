"""待办卡双击展开详情：展开/收起 / 内容 / 单击不触发 / 重建后保持"""
import http.server, threading, json, socketserver, secrets, sys
from datetime import datetime
from playwright.sync_api import sync_playwright

DOC = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo'
USER = {'id': 1, 'email': 'test@example.com', 'display_name': '测试', 'is_admin': False}
sessions = {}
PORT = 38552
D = '2026-10-24'

NOTE = '这是完整备注：包括起床入睡时间、三餐时间、散步时间、吃饭时间等，长度足够触发两行截断以便验证展开后不再截断。'
TASKS = [
    {'id': 't1', 'title': '后疫情的生活时间规划', 'note': NOTE, 'tag': '健康', 'priority': '高',
     'status': 'todo', 'due': '2026-10-22', 'createdAt': '2026-10-20T09:00:00Z'},
    {'id': 't2', 'title': '没有备注的任务', 'note': '', 'tag': '生活', 'priority': '中',
     'status': 'doing', 'due': '', 'createdAt': '2026-10-23T09:00:00Z'},
]
HABITS = [{'id': 'h_med', 'name': '用药', 'icon': '💊', 'type': 'build', 'target': 1, 'unit': '次',
           'color': '#2f6f5e', 'note': '', 'createdAt': '2026-10-01T00:00:00Z', 'pinned': True, 'med': True, 'archivedAt': ''}]
board = {'data': {'version': 2, 'view': 'board', 'habits': HABITS, 'checks': {}, 'notes': {}, 'moods': {},
                  'events': [], 'meds': [], 'doses': {}, 'bodyProfile': {'age': 30, 'height': 170},
                  'weights': [], 'essays': [], 'tasks': [dict(t) for t in TASKS]}, 'rev': 5}

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

CARD = """(id) => {
  const c = document.querySelector('.task[data-id="' + id + '"]');
  if (!c) return null;
  const d = c.querySelector('.task-detail');
  const note = c.querySelector('.td-note');
  const meta = [...c.querySelectorAll('.td-meta span')].map(e => e.textContent);
  const noteCs = note ? getComputedStyle(note) : null;
  const para = c.querySelector('p');
  return {
    open: c.classList.contains('is-open'),
    detailShown: d ? getComputedStyle(d).display !== 'none' : false,
    h: Math.round(c.getBoundingClientRect().height),
    note: note ? note.textContent : '',
    meta: meta,
    noteVisible: note ? note.getBoundingClientRect().height > 0 : false,
    paraClamp: para ? getComputedStyle(para).webkitLineClamp : ''
  };
}"""

def open_page(br, w=1600, h=1000):
    ctx = br.new_context(viewport={'width': w, 'height': h})
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.clock.install(time=datetime(2026, 10, 24, 13, 0, 0))
    pg.add_init_script("try{localStorage.setItem('lifeboard.layout','top');localStorage.setItem('lifeboard.skin','paper');localStorage.setItem('lifeboard.theme.mode','light')}catch(e){}")
    pg.goto('http://127.0.0.1:%d/index.html' % PORT, wait_until='networkidle')
    pg.wait_for_timeout(700)
    pg.click('[data-act="cloud-login"]'); pg.wait_for_timeout(500)
    pg.fill('input[name="email"]', USER['email']); pg.fill('input[name="password"]', '12345678')
    pg.click('form.modal-card button[type="submit"]')
    pg.wait_for_timeout(2600)
    pg.evaluate("""() => {
      const b = document.querySelector('.nav-item[data-nav=\"board\"]');
      if (b) b.click();
    }""")
    pg.wait_for_timeout(900)
    return ctx, pg, errs

with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)
    ctx, pg, errs = open_page(br)

    a0 = pg.evaluate(CARD, 't1')
    rec('初始为收起', not a0['open'] and not a0['detailShown'], 'open=%s' % a0['open'])
    rec('收起时备注被两行截断', a0['paraClamp'] in ('2', 2), 'clamp=%s' % a0['paraClamp'])

    pg.click('.task[data-id="t1"]'); pg.wait_for_timeout(350)
    a1 = pg.evaluate(CARD, 't1')
    rec('单击不展开', not a1['open'], 'open=%s' % a1['open'])

    pg.dblclick('.task[data-id="t1"]'); pg.wait_for_timeout(500)
    a2 = pg.evaluate(CARD, 't1')
    rec('双击展开', a2['open'] and a2['detailShown'], 'open=%s shown=%s' % (a2['open'], a2['detailShown']))
    rec('展开后卡片变高', a2['h'] > a0['h'] + 20, '%d → %d' % (a0['h'], a2['h']))
    rec('备注全文出现', a2['note'] == NOTE, a2['note'][:20] + '…')
    rec('展开后不再截断', a2['paraClamp'] in ('none', ''), 'clamp=%s' % a2['paraClamp'])
    rec('元信息含截止 / 优先级 / 创建', any('截止' in m for m in a2['meta']) and any('优先级' in m for m in a2['meta']) and any('创建' in m for m in a2['meta']), str(a2['meta']))
    rec('逾期在详情里写明', any('逾期' in m for m in a2['meta']), str([m for m in a2['meta'] if '逾期' in m]))
    pg.screenshot(path='design/shots/task-detail-open.png')

    pg.dblclick('.task[data-id="t1"]'); pg.wait_for_timeout(500)
    a3 = pg.evaluate(CARD, 't1')
    rec('再双击收起', not a3['open'] and a3['h'] == a0['h'], 'h=%d' % a3['h'])

    # 重建后保持：展开后触发一次渲染（点右栏某条定位会 render）
    pg.dblclick('.task[data-id="t1"]'); pg.wait_for_timeout(500)
    pg.evaluate("""() => {
      const b = document.querySelector('.nav-item[data-nav="today"]');
      if (b) b.click();
    }""")
    pg.wait_for_timeout(700)
    pg.evaluate("""() => {
      const b = document.querySelector('.nav-item[data-nav="board"]');
      if (b) b.click();
    }""")
    pg.wait_for_timeout(800)
    a4 = pg.evaluate(CARD, 't1')
    rec('切换页面后仍保持展开', a4['open'], 'open=%s' % a4['open'])

    # 无备注的任务
    pg.dblclick('.task[data-id="t2"]'); pg.wait_for_timeout(500)
    b1 = pg.evaluate(CARD, 't2')
    rec('无备注任务也能展开', b1['open'] and b1['detailShown'], 'open=%s' % b1['open'])
    rec('无备注时不渲染空备注块', b1['note'] == '', b1['note'])
    rec('无期限显示无期限', any('无期限' in m for m in b1['meta']), str(b1['meta']))

    rec('无 JS 异常', not errs, str(errs[:2]))
    ctx.close()
    br.close()

srv.shutdown()
ok = sum(1 for r in results if r[1])
print('\n双击展开详情验证：%d/%d 通过' % (ok, len(results)))
if ok != len(results):
    print('失败项：')
    for n, o, d in results:
        if not o: print('  -', n, '|', d)
    sys.exit(1)
