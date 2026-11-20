# -*- coding: utf-8 -*-
"""v122 通知通道矩阵：7 种提醒 × 2 条通道，勾选状态、保存请求、人话摘要。"""
import http.server, threading, json, socketserver, secrets
from playwright.sync_api import sync_playwright

DOC = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo'
USER = {'id': 6, 'email': 'sl@sl00.top', 'display_name': '晚风', 'is_admin': True,
        'status': 'active', 'created_at': '2026-10-01 00:00:00', 'last_login_at': None}
sessions = {}

KINDS = {'med': '用药提醒', 'task': '待办到点', 'habit': '习惯提醒', 'countdown': '倒数日',
         'notice': '自定义提醒', 'debt': '还款提醒', 'report': '每日小结'}
CHANNELS = {'wecom': '企业微信', 'mail': '邮件'}
PREFS = {
    'med': {'wecom': True, 'mail': True},
    'task': {'wecom': True, 'mail': True},
    'habit': {'wecom': True, 'mail': False},
    'countdown': {'wecom': True, 'mail': True},
    'notice': {'wecom': True, 'mail': True},
    'debt': {'wecom': True, 'mail': True},
    'report': {'wecom': True, 'mail': False},
}
SAVED = []
BOARD = {'data': {'version': 2, 'habits': [], 'tasks': [], 'checks': {}, 'essays': [], 'weights': [],
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
        if self.path.startswith('/index.html') or self.path == '/':
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
                         'registration_open': False, 'site_name': '明序'})
            elif a == 'status':
                self._j({'ok': True, 'installed': True})
            elif a == 'load':
                self._j({'ok': True, 'data': BOARD['data'], 'rev': 1, 'updated_at': 1792813000000, 'history': []})
            elif a == 'notify_prefs':
                self._j({'ok': True, 'kinds': KINDS, 'channels': CHANNELS, 'prefs': PREFS,
                         'quiet': False,
                         'report': {'morning': '08:20', 'noon': '12:30', 'evening': '20:00'}})
            elif a in ('push_status', 'ics_status', 'mail_status'):
                if a == 'mail_status':
                    self._j({'ok': True, 'config': {'host': 'smtp.qq.com', 'port': 465, 'secure': 'ssl',
                                                    'user': 'a@b.com', 'from': 'a@b.com', 'name': '',
                                                    'hasSecret': True, 'enabled': True, 'lastError': '',
                                                    'lastTestAt': ''}, 'crypto_ready': True, 'recipient': 'a@b.com'})
                else:
                    self._j({'ok': True, 'enabled': False, 'webhook_set': False, 'token': 'x', 'url': 'https://x/x.ics'})
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
        elif a == 'notify_prefs_save':
            SAVED.append(body)
            for k, row in (body.get('prefs') or {}).items():
                PREFS.setdefault(k, {}).update(row)
            self._j({'ok': True, 'prefs': PREFS, 'quiet': bool(body.get('quiet')),
                     'report': body.get('report') or {}})
        elif a in ('save', 'force'):
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
        print('PASS ', name, ' |', note)
    else:
        ok[1] += 1
        print('FAIL ', name, ' |', note)


with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)
    ctx = br.new_context(viewport={'width': 1360, 'height': 900})
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)[:120]))
    pg.add_init_script("try{localStorage.setItem('lifeboard.theme.mode','light');"
                       "localStorage.setItem('lifeboard.skin','paper')}catch(e){}")
    pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
    pg.wait_for_timeout(600)
    if pg.locator('[data-act="cloud-login"]').count():
        pg.click('[data-act="cloud-login"]')
        pg.wait_for_timeout(400)
        pg.fill('input[name="email"]', 'sl@sl00.top')
        pg.fill('input[name="password"]', 'x')
        pg.click('form.modal-card button[type="submit"]')
        pg.wait_for_timeout(1800)

    pg.evaluate("() => { const b=document.querySelector('[data-nav=\"config\"]'); if(b) b.click(); }")
    pg.wait_for_timeout(900)

    rows = pg.locator('.mx-table tbody tr')
    rec('矩阵渲染出 7 行', rows.count() == 7, str(rows.count()))
    heads = pg.locator('.mx-table thead th').all_inner_texts()
    rec('表头是「提醒类型 + 企业微信 + 邮件」', heads == ['提醒类型', '企业微信', '邮件'], str(heads))

    def cell(kind, chan):
        return pg.locator('.mx-table input[data-kind="%s"][data-chan="%s"]' % (kind, chan)).is_checked()

    rec('用药两个通道都勾上', cell('med', 'wecom') and cell('med', 'mail'))
    rec('习惯的邮件没勾（默认只走企微）', cell('habit', 'wecom') and not cell('habit', 'mail'))
    rec('每日小结的邮件没勾', not cell('report', 'mail'))
    rec('还款提醒有独立一行', cell('debt', 'wecom'))

    summary = pg.locator('.mx-summary').inner_text()
    rec('摘要写清谁走两条通道', '发到企业微信和邮箱' in summary, summary[:60])
    rec('摘要写清谁只走企微', '只发企业微信' in summary, summary[:60])

    print('\n--- 取消「待办」的邮件，看请求体 ---')
    pg.locator('.mx-table input[data-kind="task"][data-chan="mail"]').click()
    pg.wait_for_timeout(200)
    rec('点击后复选框变成未选', not cell('task', 'mail'))
    pg.click('[data-act="notify-save"]')
    pg.wait_for_timeout(900)
    rec('发出了保存请求', len(SAVED) == 1, str(len(SAVED)))
    if SAVED:
        sent = SAVED[0]['prefs']
        rec('提交的 task.mail 是 false', sent['task']['mail'] is False, str(sent.get('task')))
        rec('提交的 med.mail 仍是 true', sent['med']['mail'] is True, str(sent.get('med')))
        rec('七种类型都提交了', len(sent) == 7, str(len(sent)))
    summary2 = pg.locator('.mx-summary').inner_text()
    rec('保存后摘要跟着变', '待办到点' in summary2 and '只发企业微信' in summary2, summary2[:80])

    print('\n--- 全部关掉 ---')
    for kind in KINDS.keys():
        for chan in CHANNELS.keys():
            el = pg.locator('.mx-table input[data-kind="%s"][data-chan="%s"]' % (kind, chan))
            if el.is_checked():
                el.click()
    pg.wait_for_timeout(300)
    rec('全关时摘要说不会收到提醒', '不会收到任何提醒' in pg.locator('.mx-summary').inner_text(),
        pg.locator('.mx-summary').inner_text())
    pg.locator('.panel').filter(has_text='通知通道矩阵').screenshot(path=DOC + '/design/matrix.png')

    print('\n--- 夜间静默与小结时刻 ---')
    pg.reload(wait_until='networkidle')
    pg.wait_for_timeout(1200)
    pg.evaluate("() => { const b=document.querySelector('[data-nav=\"config\"]'); if(b) b.click(); }")
    pg.wait_for_timeout(900)
    quiet = pg.locator('#mx-quiet')
    rec('静默开关存在', quiet.count() == 1, str(quiet.count()))
    rec('默认不勾（系统不替用户决定）', not quiet.is_checked())
    rec('说明里写明不会补发', '不会补发' in pg.locator('.mx-extra').inner_text())
    rep = {k: pg.input_value('#mx-rep-' + k) for k in ('morning', 'noon', 'evening')}
    rec('三个小结时刻有默认值', rep == {'morning': '08:20', 'noon': '12:30', 'evening': '20:00'}, json.dumps(rep))

    quiet.click()
    pg.fill('#mx-rep-morning', '10:00')
    pg.fill('#mx-rep-evening', '')
    pg.wait_for_timeout(200)
    before = len(SAVED)
    pg.click('[data-act="notify-save"]')
    pg.wait_for_timeout(900)
    rec('保存后请求体带 quiet=true', len(SAVED) > before and SAVED[-1].get('quiet') is True,
        str(SAVED[-1].get('quiet')) if SAVED else '')
    sent_rep = (SAVED[-1].get('report') or {}) if SAVED else {}
    rec('提交的早报是 10:00', sent_rep.get('morning') == '10:00', str(sent_rep))
    rec('提交的小结留空', sent_rep.get('evening') == '', str(sent_rep))

    rec('无 JS / console 报错', not errs, str(errs[:2]))
    br.close()

srv.shutdown()
print('\n' + '=' * 46)
print('通道矩阵：%d 通过 / %d 失败' % (ok[0], ok[1]))
