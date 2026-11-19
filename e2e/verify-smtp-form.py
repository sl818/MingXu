# -*- coding: utf-8 -*-
"""v119 邮件配置表单验证：字段齐全、QQ 默认值、授权码不回显、客户端拦截与错误提示。"""
import http.server, threading, json, socketserver, secrets, sys
from playwright.sync_api import sync_playwright

DOC = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo'
USER = {'id': 1, 'email': 'test@example.com', 'display_name': '测试', 'is_admin': False,
        'status': 'active', 'created_at': '2026-10-01 00:00:00', 'last_login_at': None}
sessions = {}

MAIL_CFG = {
    'host': 'smtp.qq.com', 'port': 465, 'secure': 'ssl',
    'user': '123456789@qq.com', 'from': '123456789@qq.com', 'name': '明序',
    'hasSecret': True, 'enabled': True, 'lastError': '', 'lastTestAt': '',
}


class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=DOC, **kw)

    def log_message(self, *a):
        pass

    def _j(self, o, s=200, eh=None):
        b = json.dumps(o, ensure_ascii=False).encode()
        self.send_response(s)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(b)))
        for k, v in (eh or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(b)

    def _sid(self):
        for p in (self.headers.get('Cookie', '') or '').split(';'):
            p = p.strip()
            if p.startswith('sid='):
                return p[4:]

    def do_GET(self):
        if self.path.startswith('/api.php'):
            a = self.path.split('action=')[-1].split('&')[0]
            if a == 'status':
                self._j({'ok': True, 'installed': True, 'registration_open': False})
            elif a == 'me':
                self._j({'ok': True, 'user': sessions.get(self._sid()), 'csrf': 'x', 'registration_open': False})
            elif a == 'load':
                self._j({'ok': True, 'data': {'version': 2, 'habits': [], 'tasks': [], 'meds': []},
                         'rev': 1, 'updated_at': 1792813000000})
            elif a == 'ics_status':
                self._j({'ok': True, 'url': None})
            elif a == 'push_status':
                self._j({'ok': True, 'enabled': False, 'webhook': '', 'sent_today': 0,
                         'last_sent': '', 'recent': []})
            elif a == 'push_preview':
                self._j({'ok': True, 'date': '2026-10-25', 'items': []})
            elif a == 'mail_status':
                self._j({'ok': True, 'config': MAIL_CFG, 'crypto_ready': True,
                         'recipient': USER['email']})
            else:
                self._j({'ok': False, 'error': '?'}, 404)
        else:
            super().do_GET()

    def do_POST(self):
        if self.path.startswith('/api.php'):
            a = self.path.split('action=')[-1].split('&')[0]
            n = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(n) or b'{}')
            if a == 'login':
                sid = secrets.token_hex(8)
                sessions[sid] = USER
                self._j({'ok': True, 'user': USER, 'csrf': 'x'}, eh={'Set-Cookie': 'sid=' + sid + '; Path=/'})
            elif a == 'save' or a == 'force':
                self._j({'ok': True, 'rev': 2, 'updated_at': 1792813000000})
            elif a == 'mail_test':
                self._j({'ok': False, 'error': '没发出去：认证失败：这里要填 16 位授权码',
                         'code': 'mail_failed'}, 502)
            else:
                self._j({'ok': False, 'error': '?'}, 404)
        else:
            self.send_response(405)
            self.end_headers()


class TS(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


srv = TS(('127.0.0.1', 0), H)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()

passed = failed = 0
errs = []


def rec(name, ok, detail=''):
    global passed, failed
    if ok:
        passed += 1
    else:
        failed += 1
    print(('PASS  ' if ok else 'FAIL  ') + name + (('  | ' + detail) if detail else ''))


with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)
    ctx = br.new_context(viewport={'width': 1440, 'height': 900})
    pg = ctx.new_page()
    pg.on('pageerror', lambda e: errs.append(str(e)[:140]))
    # mock 故意返回 502 来测错误提示，浏览器会记一条资源加载日志；那不是 JS 错误
    pg.on('console', lambda m: errs.append(m.text[:120])
          if m.type == 'error' and 'Failed to load resource' not in m.text else None)
    pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
    pg.wait_for_timeout(400)
    pg.click('[data-act="cloud-login"]')
    pg.wait_for_timeout(300)
    pg.fill('input[name="email"]', 'test@example.com')
    pg.fill('input[name="password"]', 'test@example.com')
    pg.click('form.modal-card button[type="submit"]')
    pg.wait_for_timeout(2000)

    pg.evaluate("() => { const b=document.querySelector('[data-nav=\"config\"]'); if(b) b.click(); }")
    pg.wait_for_timeout(700)

    fields = ['mail-host', 'mail-port', 'mail-secure', 'mail-user', 'mail-from', 'mail-name', 'mail-secret']
    got = pg.evaluate("""ids => ids.map(id => {
        const e = document.getElementById(id);
        return e ? {id: id, value: e.value, type: e.type, placeholder: e.placeholder || ''} : null;
    })""", fields)
    rec('七个字段全部渲染', all(got), str([g['id'] for g in got if not g]))

    d = {g['id']: g for g in got if g}
    rec('服务器默认 smtp.qq.com', d['mail-host']['value'] == 'smtp.qq.com', d['mail-host']['value'])
    rec('端口默认 465', d['mail-port']['value'] == '465', d['mail-port']['value'])
    rec('协议默认 ssl', d['mail-secure']['value'] == 'ssl', d['mail-secure']['value'])
    rec('授权码不回显（框永远为空）', d['mail-secret']['value'] == '', repr(d['mail-secret']['value']))
    rec('授权码是 password 输入框', d['mail-secret']['type'] == 'password', d['mail-secret']['type'])
    # 已保存时必须看得出来（否则空框 + 「16 位授权码」占位会让人以为没填过）
    rec('已保存时 placeholder 写明已保存', '已保存' in d['mail-secret']['placeholder'], d['mail-secret']['placeholder'])
    pg.locator('.mail-center').screenshot(path=DOC + '/design/mail-saved.png')
    hint = pg.locator('.mail-saved-hint')
    rec('已保存时有绿色提示行', hint.count() == 1 and '已保存' in hint.inner_text(),
        hint.inner_text() if hint.count() else '缺失')

    btns = pg.evaluate("""() => ['mail-test','mail-save','mail-cancel','mail-off']
        .map(a => !!document.querySelector('[data-act="'+a+'"]'))""")
    rec('发信测试 / 保存 / 取消 / 暂停四个按钮齐全', all(btns), str(btns))

    pg.evaluate("""() => {
        const labels = Array.from(document.querySelectorAll('.mail-center')).map(x => x.textContent).join(' ');
        return labels;
    }""")
    hint = pg.evaluate("() => (document.querySelector('.mail-center') || {}).textContent || ''")
    rec('表单内写明授权码不是密码', '16 位授权码' in hint)
    rec('表单内写明发件人须一致', '必须和用户名' in hint)
    rec('表单内写明两个 550 坑',
        '550 Invalid "From"' in hint and '550 Sender frequency limited' in hint)

    # 发件人填错：客户端应拦下并提示，不发请求
    pg.fill('#mail-from', 'other@qq.com')
    pg.click('[data-act="mail-save"]')
    pg.wait_for_timeout(400)
    toast = pg.evaluate("() => (document.querySelector('#toast') || {}).textContent || ''")
    rec('发件人不一致被前端拦下', '发件人必须和用户名' in toast, toast.strip()[:60])

    # 恢复一致后点测试：mock 返回 502，错误信息应显示在表单里
    pg.fill('#mail-from', '123456789@qq.com')
    pg.fill('#mail-secret', 'abcdefghijklmnop')
    pg.click('[data-act="mail-test"]')
    pg.wait_for_timeout(1200)
    result = pg.evaluate("""() => {
        const e = document.getElementById('mail-result');
        return e ? {hidden: e.hidden, cls: e.className, txt: e.textContent} : null;
    }""")
    rec('测试失败显示错误条', result and not result['hidden'] and 'bad' in result['cls'], str(result))
    rec('错误条带服务端的人话提示', result and '16 位授权码' in result['txt'], (result or {}).get('txt', '')[:80])

    rec('无 JS / console 报错', not errs, '; '.join(errs[:3]))
    br.close()

print('\n邮件表单验证：%d/%d 通过' % (passed, passed + failed))
sys.exit(1 if failed else 0)
