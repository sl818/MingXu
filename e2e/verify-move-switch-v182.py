# -*- coding: utf-8 -*-
"""v182 编辑运动时切换模式验证：

1. 已有运动在编辑弹窗里能切换到别的模式（高亮、目标、记录项都跟着换）
2. 编辑弹窗会先告诉用户「有 N 条记录，换模式会一起归档」
3. 保存后卡片标题变成新模式
4. **历史记录的 key 跟着迁移** —— 否则卡片写跑步、统计里那条还挂着力量训练，等于切了也用不了
5. 老数据里没有 sportId 的记录，在旧模式唯一时也会被迁移
6. 另一个同模式实例的记录不受牵连
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
D = '2026-10-24'          # 周六
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


HABITS = [
    {'id': 'h_move', 'name': '运动', 'icon': '🏃', 'type': 'build', 'target': 1, 'unit': '次',
     'color': '#b5733f', 'note': '', 'createdAt': '2026-09-01T08:00:00Z', 'pinned': True},
]

# 老数据：v176 之前的记录没有 sportId，只有 key
OLD_REC = {'id': 'oldrec01', 'key': 'strength', 'd': '2026-10-20',
           'at': '2026-10-20T12:00:00.000Z', 'hour': 20, 'dur': 30, 'dist': 0, 'kcal': 0,
           'steps': 0, 'count': 0, 'heart': 0, 'pace': ''}

board = {'data': {
    'version': 2, 'schemaVersion': 2, 'view': 'today',
    'habits': HABITS,
    'modules': {'move': {
        'on': True, 'name': '运动', 'icon': '🏃', 'color': '#b5733f', 'note': '',
        'unit': '次', 'times': 1, 'sports': [], 'records': [OLD_REC],
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


def recs():
    return board['data']['modules']['move'].get('records') or []


def sports():
    return board['data']['modules']['move'].get('sports') or []


def new_sport(pg, key):
    pg.click('[data-act="move-new"]')
    pg.wait_for_timeout(450)
    pg.click('.sp-grid .sp-opt[data-k="%s"]' % key)
    pg.wait_for_timeout(250)
    pg.click('#move-sport-form button[type="submit"]')
    pg.wait_for_timeout(1500)


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

    print('\n===== 1. 准备：力量训练 ×1（并带一条老记录）=====')
    new_sport(pg, 'strength')
    chk('建好了力量训练', [s.get('key') for s in sports()] == ['strength'],
        json.dumps([s.get('key') for s in sports()]))
    chk('老记录还在（没有 sportId）', any(r.get('id') == 'oldrec01' for r in recs()))

    # 打一次卡，产生带 sportId 的记录
    pg.locator('.mv-card [data-act="move-do"]').first.click()
    pg.wait_for_timeout(900)
    pg.click('#move-record-form button[type="submit"]')
    pg.wait_for_timeout(1400)
    chk('共有 2 条记录', len(recs()) == 2, str(len(recs())))

    print('\n===== 2. 编辑弹窗里切到别的模式 =====')
    pg.locator('.mv-card [data-act="move-edit"]').first.click()
    pg.wait_for_timeout(700)
    chk('弹窗标题是「编辑运动」', pg.inner_text('#move-sport-form h3').strip() == '编辑运动',
        pg.inner_text('#move-sport-form h3'))
    on = pg.eval_on_selector_all('#move-sport-form .sp-opt', 'e=>e.filter(x=>x.classList.contains("on")).map(x=>x.dataset.k)')
    chk('当前选中的是力量训练', on == ['strength'], json.dumps(on))
    hint = pg.inner_text('#move-sport-body')
    chk('先告诉用户有记录会一起归档', '条记录' in hint and '归档' in hint, hint[:160])

    pg.click('#move-sport-form .sp-opt[data-k="run"]')
    pg.wait_for_timeout(600)
    on2 = pg.eval_on_selector_all('#move-sport-form .sp-opt', 'e=>e.filter(x=>x.classList.contains("on")).map(x=>x.dataset.k)')
    chk('点了之后高亮切到跑步', on2 == ['run'], json.dumps(on2))
    body = pg.inner_text('#move-sport-body')
    chk('运动说明换成跑步的', '跑步' in body, body[:120])
    chk('记录项换成跑步的', '距离（公里）' in body and '组数（组）' not in body, body[:200])
    chk('提示「已切换、保存后生效」', '切换到' in body and '保存后生效' in body, body[:240])

    print('\n===== 3. 保存：卡片与历史记录一起换模式 =====')
    pg.click('#move-sport-form button[type="submit"]')
    pg.wait_for_timeout(1600)
    chk('运动模式已改成跑步', sports()[0].get('key') == 'run', json.dumps(sports()[0], ensure_ascii=False)[:160])
    titles = pg.eval_on_selector_all('.mv-card .mv-title b', 'e=>e.map(x=>x.textContent.trim())')
    chk('卡片标题变成跑步', titles == ['跑步'], json.dumps(titles, ensure_ascii=False))
    keys = [r.get('key') for r in recs()]
    chk('两条历史记录都改成跑步', keys == ['run', 'run'], json.dumps(keys))
    chk('记录内容没丢', any(float(r.get('dur') or 0) == 30 for r in recs()),
        json.dumps(recs(), ensure_ascii=False)[:200])
    stats = pg.eval_on_selector_all('.st-barrow .nm', 'e=>e.map(x=>x.textContent.trim())')
    chk('统计页只剩跑步，不再分裂', all('力量训练' not in s for s in stats), json.dumps(stats, ensure_ascii=False))
    chk('统计页里有跑步', any('跑步' in s for s in stats), json.dumps(stats, ensure_ascii=False))

    print('\n===== 4. 别的实例不受牵连 =====')
    new_sport(pg, 'strength')
    chk('又建了一个力量训练', [s.get('key') for s in sports()] == ['run', 'strength'],
        json.dumps([s.get('key') for s in sports()]))
    n_before = len(recs())
    # 编辑第一个（跑步）切回力量训练：这时「力量训练」有另一个实例，老记录不该被它牵走
    pg.locator('.mv-card [data-act="move-edit"]').first.click()
    pg.wait_for_timeout(700)
    pg.click('#move-sport-form .sp-opt[data-k="strength"]')
    pg.wait_for_timeout(500)
    pg.click('#move-sport-form button[type="submit"]')
    pg.wait_for_timeout(1600)
    chk('记录数没变', len(recs()) == n_before, str(len(recs())))
    chk('第二个力量训练实例没被改', sports()[1].get('key') == 'strength',
        json.dumps([s.get('key') for s in sports()]))
    chk('所有记录都归到力量训练名下', all(r.get('key') == 'strength' for r in recs()),
        json.dumps([r.get('key') for r in recs()]))

    print('\n===== 5. 无 JS 报错 =====')
    chk('没有 JS 错误', not errs, str(errs[:3]))

    br.close()

print('\n===== 结果：%d 通过 / %d 失败 =====' % (PASS, FAIL))
if FAILS:
    for n, d in FAILS:
        print('  FAIL: %s  << %s' % (n, d))
    sys.exit(1)
print('全部通过')
