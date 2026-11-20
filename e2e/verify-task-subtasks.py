# -*- coding: utf-8 -*-
"""v127 任务弹窗重排 + 子任务：单击开弹窗、子任务增删勾、卡片进度、折叠默认值。"""
import http.server, threading, json, socketserver, secrets
from playwright.sync_api import sync_playwright

DOC = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo'
USER = {'id': 1, 'email': 'u@example.com', 'display_name': '测试', 'is_admin': False,
        'status': 'active', 'created_at': '2026-10-01 00:00:00', 'last_login_at': None}
sessions = {}
SAVED = []

TODAY = '2026-11-20'
TASKS = [
    {'id': 't1', 'title': '站点转型个人工作台', 'note': '', 'tag': '工作', 'priority': '中',
     'status': 'todo', 'due': TODAY, 'repeat': 'none', 'notify': True, 'notifyTime': '09:00',
     'subtasks': [{'id': 's1', 'title': '梳理现有信息架构', 'done': True},
                  {'id': 's2', 'title': '确定导航层级', 'done': False}]},
    {'id': 't2', 'title': '每天吃药', 'note': '', 'tag': '健康', 'priority': '中',
     'status': 'todo', 'due': TODAY, 'repeat': 'daily', 'notify': True, 'notifyTime': '09:00',
     'subtasks': []},
    {'id': 't3', 'title': '没有子任务的任务', 'note': '一条备注', 'tag': '生活', 'priority': '低',
     'status': 'doing', 'due': TODAY, 'repeat': 'none', 'notify': False, 'notifyTime': '09:00',
     'subtasks': []},
]
BOARD = {'data': {'version': 2, 'habits': [], 'tasks': TASKS, 'checks': {}, 'essays': [], 'weights': [],
                  'meds': [], 'medLogs': {}, 'money': {}, 'settings': {}, 'essayTags': [], 'quit': {}}, 'rev': 1}


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _j(self, obj, code=200, eh=None):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(b)))
        for k, v in (eh or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(b)

    def _auth(self):
        for part in (self.headers.get('Cookie') or '').split(';'):
            if part.strip().startswith('sid='):
                return sessions.get(part.strip()[4:])
        return None

    def do_GET(self):
        if self.path.startswith('/index.html') or self.path.split('?')[0] == '/':
            body = open(DOC + '/index.html', 'rb').read()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path.startswith('/assets/'):
            p = DOC + self.path.split('?')[0]
            try:
                body = open(p, 'rb').read()
                self.send_response(200)
                self.send_header('Content-Type', 'text/css' if p.endswith('.css') else 'application/javascript')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except Exception:
                self.send_response(404)
                self.end_headers()
            return
        if self.path.startswith('/api.php'):
            a = self.path.split('action=')[-1].split('&')[0]
            u = self._auth()
            if a == 'me':
                self._j({'ok': True, 'user': USER if u else None, 'csrf': 'x',
                         'registration_open': False, 'registration_mode': 'invite',
                         'site_name': '明序'})
            elif a == 'status':
                self._j({'ok': True, 'installed': True})
            elif a == 'load':
                self._j({'ok': True, 'data': BOARD['data'], 'rev': 1, 'updated_at': 1792813000000, 'history': []})
            elif a in ('push_status', 'ics_status'):
                self._j({'ok': True, 'enabled': False, 'webhook_set': False, 'token': 'x', 'url': 'x'})
            elif a == 'mail_status':
                self._j({'ok': True, 'config': {'hasSecret': False, 'enabled': False}, 'crypto_ready': True, 'recipient': 'a@b.com'})
            else:
                self._j({'ok': False, 'error': 'unknown'}, 404)
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        if not self.path.startswith('/api.php'):
            self.send_response(405)
            self.end_headers()
            return
        a = self.path.split('action=')[-1].split('&')[0]
        n = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(n) or b'{}')
        if a == 'login':
            sid = secrets.token_hex(8)
            sessions[sid] = USER
            self._j({'ok': True, 'user': USER, 'csrf': 'x'}, eh={'Set-Cookie': 'sid=' + sid + '; Path=/'})
        elif a in ('save', 'force'):
            SAVED.append(body.get('data') or {})
            BOARD['data'] = body['data']
            self._j({'ok': True, 'rev': 2, 'updated_at': 1792813000000})
        else:
            self._j({'ok': False, 'error': '?'}, 404)


class TS(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


srv = TS(('127.0.0.1', 0), H)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()

ok = [0, 0]


def rec(name, cond, note=''):
    if cond:
        ok[0] += 1
        print('PASS ', name, ' |', str(note)[:70])
    else:
        ok[1] += 1
        print('FAIL ', name, ' |', str(note)[:70])


with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)
    ctx = br.new_context(viewport={'width': 1400, 'height': 950})
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)[:120]))
    pg.add_init_script("try{localStorage.setItem('lifeboard.theme.mode','light');"
                       "localStorage.setItem('lifeboard.skin','paper');"
                       "localStorage.setItem('lifeboard.layout','wide')}catch(e){}")
    pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
    pg.wait_for_timeout(700)
    if pg.locator('[data-act="cloud-login"]').count():
        pg.click('[data-act="cloud-login"]')
        pg.wait_for_timeout(400)
        pg.fill('input[name="email"]', 'u@example.com')
        pg.fill('input[name="password"]', 'x')
        pg.click('form.modal-card button[type="submit"]')
        pg.wait_for_timeout(1800)

    pg.evaluate("() => { const b=document.querySelector('[data-nav=\"board\"]'); if(b) b.click(); }")
    pg.wait_for_timeout(900)

    print('=== 卡片 ===')
    cards = pg.locator('.task')
    rec('看板渲染出 3 张卡', cards.count() == 3, str(cards.count()))
    first = pg.locator('.task[data-id="t1"]')
    rec('有子任务的卡显示进度', first.locator('.task-subs').count() == 1)
    rec('进度写的是 1/2', '1/2' in first.locator('.task-subs').inner_text(),
        first.locator('.task-subs').inner_text())
    rec('没子任务的卡不显示进度',
        pg.locator('.task[data-id="t2"] .task-subs').count() == 0)

    print('\n=== 单击打开弹窗 ===')
    first.click()
    pg.wait_for_timeout(600)
    form = pg.locator('#task-form')
    rec('单击卡片就打开弹窗', form.count() == 1, str(form.count()))
    rec('弹窗带 task-sheet 类', 'task-sheet' in (form.get_attribute('class') or ''))

    print('\n=== 弹窗结构 ===')
    rec('标题是无边框大输入', pg.locator('.tk-title').count() == 1)
    rec('属性区有 4 个胶囊', pg.locator('.tk-props .tk-p').count() == 4,
        str(pg.locator('.tk-props .tk-p').count()))
    props = pg.locator('.tk-props').inner_text()
    rec('四个属性齐全', all(k in props for k in ['状态', '分类', '优先级', '截止']), props.replace('\n', ' '))
    rec('有子任务区', pg.locator('.tk-sec').count() == 1)
    rec('折叠区存在', pg.locator('.tk-fold').count() == 1)
    rec('无 startTime 时折叠是收起的', not pg.locator('.tk-fold').evaluate('e => e.open'))
    pg.locator('#task-form').screenshot(path=DOC + '/design/task-sheet-new.png')

    print('\n=== 子任务 ===')
    rows = pg.locator('.tk-sub')
    rec('列出 2 条子任务', rows.count() == 2, str(rows.count()))
    rec('第一条是勾上的', rows.nth(0).locator('input').is_checked())
    rec('第二条未勾', not rows.nth(1).locator('input').is_checked())
    rec('计数显示 1/2', pg.locator('[data-sub-count]').inner_text() == '1/2',
        pg.locator('[data-sub-count]').inner_text())

    pg.fill('[data-sub-input]', '新增一条子任务')
    pg.press('[data-sub-input]', 'Enter')
    pg.wait_for_timeout(300)
    rec('回车新增一条', pg.locator('.tk-sub').count() == 3, str(pg.locator('.tk-sub').count()))
    rec('计数变成 1/3', pg.locator('[data-sub-count]').inner_text() == '1/3',
        pg.locator('[data-sub-count]').inner_text())

    pg.locator('.tk-sub').nth(2).locator('input').check()
    pg.wait_for_timeout(250)
    rec('勾上后计数 2/3', pg.locator('[data-sub-count]').inner_text() == '2/3',
        pg.locator('[data-sub-count]').inner_text())

    pg.locator('.tk-sub').nth(1).hover()
    pg.locator('.tk-sub').nth(1).locator('.tk-sub-del').click()
    pg.wait_for_timeout(250)
    rec('删除一条后剩 2 条', pg.locator('.tk-sub').count() == 2, str(pg.locator('.tk-sub').count()))

    print('\n=== 保存 ===')
    pg.click('#task-form button[type="submit"]')
    pg.wait_for_timeout(1200)
    rec('弹窗关闭', pg.locator('#task-form').count() == 0)
    saved_subs = []
    if SAVED:
        # 取最后一次保存：登录后可能已经自动存过一次，那是操作前的数据
        t1 = [t for t in (SAVED[-1].get('tasks') or []) if t.get('id') == 't1']
        saved_subs = (t1[0].get('subtasks') or []) if t1 else []
    rec('提交里带 subtasks', len(saved_subs) == 2, str(saved_subs))
    rec('新增那条被保存', any(s.get('title') == '新增一条子任务' for s in saved_subs), str(saved_subs))
    rec('勾选状态被保存', sum(1 for s in saved_subs if s.get('done')) == 2,
        str([s.get('done') for s in saved_subs]))

    print('\n=== 折叠默认值 ===')
    pg.locator('.task[data-id="t2"]').click()
    pg.wait_for_timeout(600)
    rec('带每日重复的任务，折叠自动展开', pg.locator('.tk-fold').evaluate('e => e.open'))
    pg.keyboard.press('Escape')
    pg.wait_for_timeout(300)

    pg.locator('.task[data-id="t3"]').click()
    pg.wait_for_timeout(600)
    rec('通知关闭的任务，折叠也展开', pg.locator('.tk-fold').evaluate('e => e.open'))
    rec('备注带出来了', '一条备注' in pg.input_value('.tk-note'), pg.input_value('.tk-note'))

    rec('无 JS / console 报错', not errs, str(errs[:2]))
    br.close()

srv.shutdown()
print('\n' + '=' * 46)
print('任务弹窗与子任务：%d 通过 / %d 失败' % (ok[0], ok[1]))
