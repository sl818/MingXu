# -*- coding: utf-8 -*-
"""v183 编辑运动时锁定运动类型：

陛下定的规矩 —— 类型建好后不能改，要别的运动就新建一个。

1. 新建弹窗里类型照常可选
2. 编辑弹窗里有「类型不能修改」的提示文案
3. 编辑弹窗里只有当前类型可选，其余灰掉
4. 点别的类型：不会切换，只给一句提示
5. 保存后类型不变、历史记录不受影响
"""
import http.server
import json
import secrets
import socketserver
import sys
import threading
from datetime import datetime

from playwright.sync_api import sync_playwright

DOC = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo'
USER = {'id': 1, 'email': 'test@example.com', 'display_name': '测试', 'is_admin': False}
sessions = {}
D = '2026-10-24'
PASS = 0
FAIL = 0
FAILS = []


def chk(name, ok, detail=''):
    global PASS, FAIL
    if ok:
        PASS += 1
        print('  [OK] %s' % name)
    else:
        FAIL += 1
        FAILS.append((name, detail))
        print('  [FAIL] %s  << %s' % (name, detail))


board = {'data': {
    'version': 2, 'schemaVersion': 2, 'view': 'today',
    'habits': [],
    'modules': {'move': {
        'on': True, 'name': '运动', 'icon': '🏃', 'color': '#b5733f', 'note': '',
        'unit': '次', 'times': 1, 'sports': [], 'records': [],
        'notifyChannels': ['browser'], 'notify': True,
        'notifyScenes': {'steps': True, 'plan': True, 'week': True},
        'suggestTime': '', 'notifyFreq': 'daily', 'notifyWeekday': 1, 'notifyMonthday': 1,
        'notifyNote': '', 'createdAt': '2026-09-01T08:00:00Z', 'updatedAt': '2026-10-01T08:00:00Z',
    }},
    'modulesAt': 0,
    'checks': {}, 'skips': {}, 'notes': {}, 'moods': {}, 'events': [],
    'meds': [], 'doses': {}, 'bodyProfile': {'age': 30, 'height': 170},
    'weights': [], 'essays': [], 'tasks': [], 'money': {}, 'quit': {},
}, 'rev': 3}


class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=DOC, **kw)

    def log_message(self, *a):
        pass

    def _j(self, obj, status=200, eh=None):
        b = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(b)))
        self.send_header('Cache-Control', 'no-store')
        for k, v in (eh or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(b)

    def _sid(self):
        for p in (self.headers.get('Cookie', '') or '').split(';'):
            p = p.strip()
            if p.startswith('sid='):
                return p[4:]
            return ''

    def do_GET(self):
        if self.path.startswith('/api.php'):
            a = self.path.split('action=')[-1].split('&')[0]
            if a == 'status':
                self._j({'ok': True, 'installed': True})
            elif a == 'me':
                self._j({'ok': True, 'user': sessions.get(self._sid()), 'csrf': 'x',
                         'registration_open': False, 'registration_mode': 'closed',
                         'need_invite': False, 'need_code': False, 'code_ready': False})
            elif a == 'push_status':
                self._j({'ok': True, 'enabled': False, 'webhook': '', 'sent_today': 0,
                         'last_sent': '', 'recent': []})
            elif a == 'push_preview':
                self._j({'ok': True, 'date': D, 'items': []})
            elif a == 'mail_status':
                self._j({'ok': True, 'crypto_ready': True, 'recipient': 'test@example.com',
                         'config': {'host': '', 'port': 465, 'secure': 'ssl', 'user': '', 'from': '',
                                    'name': '', 'hasSecret': False, 'enabled': False,
                                    'lastError': '', 'lastTestAt': ''}})
            elif a == 'ics_status':
                self._j({'ok': True, 'url': None})
            elif a == 'load':
                self._j({'ok': True, 'data': board['data'], 'rev': board['rev'],
                         'updated_at': 1792813000000})
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
                self._j({'ok': True, 'user': USER, 'csrf': 'x', 'registration_open': False},
                        eh={'Set-Cookie': 'sid=' + sid + '; Path=/'})
            elif a in ('save', 'force'):
                board['data'] = body['data']
                board['rev'] += 1
                self._j({'ok': True, 'rev': board['rev'], 'updated_at': 1792813000000})
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


def nav(pg, v):
    pg.evaluate("v => { const b=document.querySelector('[data-nav=\"'+v+'\"]'); if(b) b.click(); }", v)
    pg.wait_for_timeout(450)


def sports():
    return board['data']['modules']['move'].get('sports') or []


def recs():
    return board['data']['modules']['move'].get('records') or []


with sync_playwright() as pw:
    br = pw.chromium.launch(channel='chrome')
    ctx = br.new_context(viewport={'width': 1440, 'height': 1000})
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))

    pg.clock.install(time=datetime(2026, 10, 24, 20, 0, 0))
    pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
    pg.wait_for_timeout(600)
    pg.click('[data-act="cloud-login"]')
    pg.wait_for_timeout(400)
    pg.fill('input[name="email"]', 'test@example.com')
    pg.fill('input[name="password"]', 'test@example.com')
    pg.click('form.modal-card button[type="submit"]')
    pg.wait_for_timeout(2800)
    nav(pg, 'move')

    print('\n===== 1. 新建时类型照常可选 =====')
    pg.click('[data-act="move-new"]')
    pg.wait_for_timeout(500)
    dis_new = pg.locator('#move-sport-form .sp-opt.dis').count()
    chk('新建时没有灰掉的类型', dis_new == 0, str(dis_new))
    chk('新建时没有锁定提示', pg.locator('#move-sport-form .sp-locked').count() == 0)
    pg.click('#move-sport-form .sp-opt[data-k="strength"]')
    pg.wait_for_timeout(400)
    on = pg.eval_on_selector_all('#move-sport-form .sp-opt', 'e=>e.filter(x=>x.classList.contains("on")).map(x=>x.dataset.k)')
    chk('可以选到力量训练', on == ['strength'], json.dumps(on))
    pg.click('#move-sport-form button[type="submit"]')
    pg.wait_for_timeout(1500)
    chk('建好了力量训练', [s.get('key') for s in sports()] == ['strength'],
        json.dumps([s.get('key') for s in sports()]))

    # 打一次卡，产生一条记录
    pg.locator('.mv-card [data-act="move-do"]').first.click()
    pg.wait_for_timeout(900)
    pg.click('#move-record-form button[type="submit"]')
    pg.wait_for_timeout(1400)
    chk('有 1 条记录', len(recs()) == 1, str(len(recs())))

    print('\n===== 2. 编辑时类型锁定 =====')
    pg.locator('.mv-card [data-act="move-edit"]').first.click()
    pg.wait_for_timeout(700)
    chk('弹窗标题是「编辑运动」', pg.inner_text('#move-sport-form h3').strip() == '编辑运动')
    locked = pg.locator('#move-sport-form .sp-locked')
    chk('有锁定提示', locked.count() == 1)
    txt = locked.inner_text() if locked.count() else ''
    chk('提示说清「不能修改」', '不能修改' in txt, txt)
    chk('提示说清「请新建」', '新建' in txt, txt)
    on2 = pg.eval_on_selector_all('#move-sport-form .sp-opt', 'e=>e.filter(x=>x.classList.contains("on")).map(x=>x.dataset.k)')
    chk('当前类型仍然高亮', on2 == ['strength'], json.dumps(on2))
    dis = pg.eval_on_selector_all('#move-sport-form .sp-opt.dis', 'e=>e.map(x=>x.dataset.k)')
    chk('其余 6 种全部灰掉', sorted(dis) == ['ball', 'ride', 'rope', 'run', 'steps', 'walk'],
        json.dumps(dis))

    print('\n===== 3. 点别的类型：只提示，不切换 =====')
    pg.click('#move-sport-form .sp-opt[data-k="run"]')
    pg.wait_for_timeout(600)
    on3 = pg.eval_on_selector_all('#move-sport-form .sp-opt', 'e=>e.filter(x=>x.classList.contains("on")).map(x=>x.dataset.k)')
    chk('高亮没变（还是力量训练）', on3 == ['strength'], json.dumps(on3))
    toast = pg.inner_text('#toast, .toast, .toast-wrap') if pg.locator('#toast, .toast, .toast-wrap').count() else pg.inner_text('body')
    chk('给出「不能改、请新建」的提示', ('不能改' in toast) and ('新建' in toast), toast[-200:])

    print('\n===== 4. 保存后类型与记录都不变 =====')
    pg.click('#move-sport-form button[type="submit"]')
    pg.wait_for_timeout(1600)
    chk('类型没被改', sports()[0].get('key') == 'strength', json.dumps(sports()[0], ensure_ascii=False)[:140])
    titles = pg.eval_on_selector_all('.mv-card .mv-title b', 'e=>e.map(x=>x.textContent.trim())')
    chk('卡片标题还是力量训练', titles == ['力量训练'], json.dumps(titles, ensure_ascii=False))
    chk('记录没被动过', len(recs()) == 1 and recs()[0].get('key') == 'strength',
        json.dumps(recs(), ensure_ascii=False)[:160])

    print('\n===== 5. 目标等其它设置仍可改 =====')
    pg.locator('.mv-card [data-act="move-edit"]').first.click()
    pg.wait_for_timeout(700)
    pg.fill('#move-sport-body #sp-tval', '45')
    pg.wait_for_timeout(200)
    pg.click('#move-sport-form button[type="submit"]')
    pg.wait_for_timeout(1600)
    chk('目标值改成了 45', float(sports()[0].get('tVal') or 0) == 45, str(sports()[0].get('tVal')))
    chk('类型仍是力量训练', sports()[0].get('key') == 'strength')

    print('\n===== 6. 无 JS 报错 =====')
    chk('没有 JS 错误', not errs, str(errs[:3]))

    br.close()

print('\n===== 结果：%d 通过 / %d 失败 =====' % (PASS, FAIL))
if FAILS:
    for n, d in FAILS:
        print('  FAIL: %s  << %s' % (n, d))
    sys.exit(1)
print('全部通过')
