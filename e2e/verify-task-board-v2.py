# -*- coding: utf-8 -*-
"""看板任务卡 v154 新布局专项验证：左栏竖排 + 复选框 + 票根 + 快捷移动(去编辑笔) + 拖拽契约。"""
import http.server, threading, json, socketserver, secrets
from datetime import datetime
from playwright.sync_api import sync_playwright

DOC = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo'
USER = {'id': 1, 'email': 'test@example.com', 'display_name': '测试', 'is_admin': False}
sessions = {}
D = '2026-10-24'

tasks = [
  {'id': 't1', 'title': '今天要做的事', 'note': '', 'tag': '工作', 'priority': '高', 'status': 'todo', 'due': '2026-10-24', 'createdAt': '2026-10-23T08:00:00Z'},
  {'id': 't2', 'title': '已逾期的事', 'note': '', 'tag': '生活', 'priority': '低', 'status': 'todo', 'due': '2026-10-20', 'createdAt': '2026-10-19T08:00:00Z'},
  {'id': 't3', 'title': '进行中的事', 'note': '', 'tag': '健康', 'priority': '中', 'status': 'doing', 'due': '2026-10-25', 'createdAt': '2026-10-23T08:00:00Z'},
  {'id': 't4', 'title': '已完成的事', 'note': '', 'tag': '学习', 'priority': '中', 'status': 'done', 'due': '2026-10-23', 'doneAt': '2026-10-23', 'createdAt': '2026-10-22T08:00:00Z'},
  {'id': 't5', 'title': '已取消的事', 'note': '', 'tag': '其他', 'priority': '低', 'status': 'cancelled', 'due': '2026-10-20', 'createdAt': '2026-10-19T08:00:00Z'},
]
board = {'data': {
    'version': 2, 'view': 'today', 'habits': [], 'checks': {}, 'notes': {}, 'moods': {},
    'events': [], 'meds': [], 'doses': {}, 'bodyProfile': {}, 'weights': [],
    'essays': [], 'tasks': tasks}, 'rev': 1}

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
            elif a == 'push_status': self._j({'ok': True, 'enabled': False, 'webhook': '', 'sent_today': 0, 'last_sent': '', 'recent': []})
            elif a == 'push_preview': self._j({'ok': True, 'date': '2026-10-25', 'items': []})
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

srv = TS(('127.0.0.1', 0), H)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()

results = []
def rec(name, ok, detail=''):
    results.append((name, bool(ok), detail))
    print(('PASS  ' if ok else 'FAIL  ') + name + (('  | ' + detail) if detail else ''))

def card_by_title(pg, txt):
    return pg.locator('.board .task').filter(has_text=txt).first

with sync_playwright() as pw:
    br = pw.chromium.launch(channel='chrome', headless=True)
    ctx = br.new_context(viewport={'width': 1440, 'height': 900}, device_scale_factor=1)
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.clock.install(time=datetime(2026, 10, 24, 10, 0, 0))
    pg.add_init_script("try{localStorage.setItem('lifeboard.layout','wide');localStorage.setItem('lifeboard.skin','paper');localStorage.setItem('lifeboard.theme.mode','light');}catch(e){}")
    pg.goto(f'http://127.0.0.1:{port}/index.html', wait_until='networkidle'); pg.wait_for_timeout(600)
    pg.click('[data-act="cloud-login"]'); pg.wait_for_timeout(400)
    pg.fill('input[name="email"]', 'test@example.com'); pg.fill('input[name="password"]', 'test@example.com')
    pg.click('form.modal-card button[type="submit"]'); pg.wait_for_timeout(2400)
    pg.click('.nav-item[data-nav="board"]'); pg.wait_for_timeout(1200)

    # 1. 结构与拖拽契约
    n = pg.locator('.board .task').count()
    rec('卡片 5 张', n == 5, f'实际 {n}')
    rec('左栏 rail 齐全', pg.locator('.board .task .task-rail').count() == 5)
    rec('复选框齐全', pg.locator('.board .task .task-check').count() == 5)
    rec('票根齐全', pg.locator('.board .task .task-stub').count() == 5)
    rec('主体齐全', pg.locator('.board .task .task-main').count() == 5)
    rec('优先级 pill 齐全', pg.locator('.board .task .prio').count() == 5)
    rec('拖拽契约 draggable', pg.locator('.board .task[draggable="true"]').count() == 5)
    rec('无编辑笔 task-edit', pg.locator('.board .task [data-act="task-edit"]').count() == 0)

    # 2. 票根状态：逾期红 / 今天
    rec('逾期票根标红', card_by_title(pg, '已逾期的事').locator('.task-stub.over').count() == 1)
    rec('今天票根', card_by_title(pg, '今天要做的事').locator('.task-stub.today').count() == 1)

    # 3. 快捷移动按钮数量（按状态）
    rec('待办卡只有 →', card_by_title(pg, '今天要做的事').locator('.task-btns button').count() == 1)
    rec('进行中卡有 ← →', card_by_title(pg, '进行中的事').locator('.task-btns button').count() == 2)
    rec('已完成卡只有 ←', card_by_title(pg, '已完成的事').locator('.task-btns button').count() == 1)
    rec('已取消卡只有 ↩', card_by_title(pg, '已取消的事').locator('.task-btns button').count() == 1)

    # 4. 勾选完成：t1 → done 列
    card_by_title(pg, '今天要做的事').locator('.task-check').click(); pg.wait_for_timeout(900)
    rec('勾选后进入已完成列', pg.locator('.col[data-status="done"] .task').filter(has_text='今天要做的事').count() == 1)
    rec('勾选后复选框置勾', card_by_title(pg, '今天要做的事').locator('.task-check.on').count() == 1)

    # 5. 移动按钮：t3(doing) → done
    card_by_title(pg, '进行中的事').locator('.task-btns [data-dir="1"]').click(); pg.wait_for_timeout(900)
    rec('→ 移到下一列', pg.locator('.col[data-status="done"] .task').filter(has_text='进行中的事').count() == 1)

    # 6. 单击标题打开编辑弹窗（编辑入口仍在）
    card_by_title(pg, '今天要做的事').locator('h4').click(); pg.wait_for_timeout(600)
    sheet = pg.locator('.task-sheet, #task-form').count()
    rec('单击卡片打开编辑弹窗', sheet > 0, f'编辑弹窗 {sheet}')
    close = pg.locator('[data-act="close-modal"]').first
    if close.count() > 0:
        try: close.click(timeout=3000)
        except Exception: pass
        pg.wait_for_timeout(400)

    pg.screenshot(path='design/shots/task-board-v2.png', full_page=False)
    rec('无 JS 报错', len(errs) == 0, '；'.join(errs) if errs else '')
    br.close()

ok = all(r[1] for r in results)
print(f'\n看板任务卡专项：{sum(1 for r in results if r[1])}/{len(results)} 通过')
print('结论:', '通过' if ok else '未通过')
