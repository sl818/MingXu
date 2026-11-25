# -*- coding: utf-8 -*-
"""v181 运动打卡流程验证（打卡 → 记数据 → 才能下一次）：

1. 打卡后立刻弹「记录第 N 次运动数据」，而不是直接算完成
2. 关掉弹窗（取消）→ 卡片变成「等记录这一次的数据」，主按钮换成「记录数据」，
   「补数据」入口消失，期间不能再打一次卡（不能把任务刷完成）
3. 进度环显示真实次数（1/2），不再写死 0/1
4. 「跳过不记录」→ 二次确认弹窗说清后果 → 确定后这次仍算完成，
   明细显示「未记录详细数据」，统计页出现「跳 N」标记
5. 第 2 次打卡 → 标题是「第 2 次」；填完数据保存 → 卡片显示「今天已完成」
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

board = {'data': {
    'version': 2, 'schemaVersion': 2, 'view': 'today',
    'habits': HABITS,
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


def recs():
    return board['data']['modules']['move'].get('records') or []


def card(pg, name='跑步'):
    return pg.locator('.mv-card', has_text=name).first


with sync_playwright() as pw:
    br = pw.chromium.launch(channel='chrome')
    ctx = br.new_context(viewport={'width': 1440, 'height': 1100})
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))

    pg.clock.install(time=datetime(2026, 10, 24, 20, 0, 0))   # 周六
    pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
    pg.wait_for_timeout(600)
    pg.click('[data-act="cloud-login"]')
    pg.wait_for_timeout(400)
    pg.fill('input[name="email"]', 'test@example.com')
    pg.fill('input[name="password"]', 'test@example.com')
    pg.click('form.modal-card button[type="submit"]')
    pg.wait_for_timeout(2800)
    nav(pg, 'move')

    print('\n===== 0. 建一个「每周选周六、每天 2 次」的跑步 =====')
    pg.click('[data-act="move-new"]')
    pg.wait_for_timeout(400)
    pg.click('.sp-grid .sp-opt[data-k="run"]')
    pg.wait_for_timeout(250)
    pg.click('#move-sport-body .sp-freq-opt[data-fk2="weekly"]')
    pg.wait_for_timeout(300)
    on_days = pg.eval_on_selector_all('#sp-week button.on', 'els=>els.map(e=>e.dataset.d)')
    for d in on_days:
        if d != '6':
            pg.click('#sp-week button[data-d="%s"]' % d)
            pg.wait_for_timeout(90)
    if '6' not in on_days:
        pg.click('#sp-week button[data-d="6"]')
        pg.wait_for_timeout(90)
    pg.fill('#sp-perday', '2')
    pg.wait_for_timeout(150)
    pg.click('#move-sport-form button[type="submit"]')
    pg.wait_for_timeout(1600)
    chk('建好了跑步', len(board['data']['modules']['move']['sports']) == 1)

    print('\n===== 1. 打卡后立刻弹数据表单 =====')
    card(pg).locator('[data-act="move-do"]').click()
    pg.wait_for_timeout(900)
    chk('弹出记录表单', pg.locator('#move-record-form').count() == 1)
    t = pg.inner_text('#move-record-form h3')
    chk('标题写明是第几次', '记录第 1 次运动数据' in t, t)
    body = pg.inner_text('#move-record-form')
    chk('说清「填完或跳过才能下一次」', '才能开始今天的下一次' in body, body[:120])
    chk('有「跳过不记录」出口', pg.locator('#move-record-form [data-act="move-skip"]').count() == 1)
    chk('记录已落库（待填状态）', len(recs()) == 1 and recs()[0].get('pending') is True,
        json.dumps(recs(), ensure_ascii=False)[:200])

    print('\n===== 2. 中途关掉弹窗 → 卡片锁住，等着记数据 =====')
    pg.click('#move-record-form [data-act="close-modal"]')
    pg.wait_for_timeout(600)
    c = card(pg)
    st = c.locator('.mv-st').inner_text()
    chk('状态行提示等记录数据', '等记录' in st, st)
    chk('主按钮变成「记录数据」',
        c.locator('[data-act="move-fill"]').count() == 1 and '记录数据' in c.locator('[data-act="move-fill"]').inner_text(),
        c.locator('.mv-btn').all_inner_texts())
    chk('「补数据」入口已撤掉', c.locator('[data-act="move-rec"]').count() == 0,
        c.locator('.mv-btn').all_inner_texts())
    chk('不能再点「去运动」', c.locator('[data-act="move-do"]').count() == 0)
    ring = c.locator('.mv-rc b').inner_text()
    chk('进度环显示真实次数 1/2', ring.strip() == '1/2', ring)
    chk('记录数没有增加（没刷完成）', len(recs()) == 1, str(len(recs())))

    print('\n===== 3. 跳过不记录：先讲清后果 =====')
    c.locator('[data-act="move-fill"]').click()
    pg.wait_for_timeout(700)
    pg.click('#move-record-form [data-act="move-skip"]')
    pg.wait_for_timeout(500)
    conf = pg.inner_text('#modal-root')
    chk('弹了二次确认', '跳过不记录' in conf, conf[:100])
    chk('说清统计页不显示详细数据', '不会显示' in conf and '详细数据' in conf, conf[:200])
    pg.click('[data-act="move-skip-ok"]')
    pg.wait_for_timeout(1000)
    c = card(pg)
    chk('跳过后仍算完成（次数 +1）', len(recs()) == 1 and recs()[0].get('skipped') is True,
        json.dumps(recs(), ensure_ascii=False)[:200])
    chk('主按钮回到「去运动」', c.locator('[data-act="move-do"]').count() == 1,
        c.locator('.mv-btn').all_inner_texts())
    chk('跳过后冒出「补数据」按钮', c.locator('[data-act="move-rec"]').count() == 1,
        c.locator('.mv-btn').all_inner_texts())
    # v184：明细改到卡片里的「今日任务记录」入口，页面底部的总表已撤
    # v186：记录拆成「运动日志 / 运动后数据」两个折叠区，默认收起 —— 先展开再断言
    c.locator('[data-act="move-log"]').click()
    pg.wait_for_timeout(800)
    for i in range(pg.locator('#modal-root .sp-fold').count()):
        box = pg.locator('#modal-root .sp-fold').nth(i)
        if not box.evaluate('e => e.open'):
            box.locator('summary').click()
            pg.wait_for_timeout(250)
    chk('任务记录里显示未记录详细数据',
        '未记录详细数据' in pg.inner_text('#modal-root'), pg.inner_text('#modal-root')[:160])
    pg.click('#modal-root [data-act="close-modal"]')
    pg.wait_for_timeout(400)

    print('\n===== 4. 统计页把跳过的次数标出来 =====')
    stats = pg.inner_text('.move-page')
    chk('统计区出现「跳 1」标记', '跳 1' in stats, stats[:200])
    chk('统计区说明只计次数不计详细数据', '不计入时长' in stats, stats[:300])

    print('\n===== 5. 第二次打卡 → 第 2 次 =====')
    card(pg).locator('[data-act="move-do"]').click()
    pg.wait_for_timeout(900)
    t2 = pg.inner_text('#move-record-form h3')
    chk('标题是第 2 次', '记录第 2 次运动数据' in t2, t2)
    pg.fill('#move-record-form input[name="dur"]', '32')
    pg.fill('#move-record-form input[name="dist"]', '5.2')
    pg.fill('#move-record-form input[name="heart"]', '145')
    pg.wait_for_timeout(200)
    pg.click('#move-record-form button[type="submit"]')
    pg.wait_for_timeout(1400)
    c = card(pg)
    chk('填完显示今天已完成', '今天已完成' in c.locator('.mv-st').inner_text(),
        c.locator('.mv-st').inner_text())
    chk('待填标记已清', recs()[-1].get('pending') is False and recs()[-1].get('skipped') is False,
        json.dumps(recs()[-1], ensure_ascii=False)[:160])
    chk('共 2 条记录', len(recs()) == 2, str(len(recs())))

    print('\n===== 6. 无 JS 报错 =====')
    chk('没有 JS 错误', not errs, str(errs[:3]))

    br.close()

print('\n===== 结果：%d 通过 / %d 失败 =====' % (PASS, FAIL))
if FAILS:
    for n, d in FAILS:
        print('  FAIL: %s  << %s' % (n, d))
    sys.exit(1)
print('全部通过')
