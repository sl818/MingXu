# -*- coding: utf-8 -*-
"""v184 运动规则改造验证：

一、每日步数（独立规则）
  1. 新建/编辑弹窗里没有「每天做几次」「每个选中的日子做几次」
  2. 卡片频率显示「每天」，不出现次数
  3. 完成度按累计步数 ÷ 目标步数，点一次不等于完成
  4. 达标后弹「补充运动数据」，里面只有勾选的字段（距离）
  5. 填了 → 不再出现补数据按钮；跳过 → 出现补数据按钮

二、其余 6 种
  6. 新建/编辑弹窗有【运动开始时间】，默认留空；每日步数没有这一项

三、补数据 / 记录
  7. 补数据只列勾选的字段，不把全部字段搬上来
  8. 卡片有【今日任务记录】入口；页面底部不再有明细总表

四、弹窗
  9. 空数据不允许提交（至少一项有效数据）
 10. 文案：时间选择器是「任务完成时间」，时长是「运动时长（分钟）」
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

    print('\n===== 1. 每日步数：没有次数设置 =====')
    pg.click('[data-act="move-new"]')
    pg.wait_for_timeout(500)
    chk('默认选中每日步数', pg.eval_on_selector_all('#move-sport-form .sp-opt.on', 'e=>e.map(x=>x.dataset.k)') == ['steps'])
    chk('没有「每天 N 次」输入框', pg.locator('#move-sport-body #sp-freqn').count() == 0)
    chk('没有「每个选中的日子做 N 次」输入框', pg.locator('#move-sport-body #sp-perday').count() == 0)
    chk('每日步数没有「运动开始时间」', pg.locator('#move-sport-body #sp-starttime').count() == 0)
    chk('有「记录方式」两选项', pg.locator('#move-sport-body .sp-rec-opt').count() == 2)
    pg.fill('#move-sport-body #sp-tval', '3000')
    pg.wait_for_timeout(200)
    pg.click('#move-sport-form button[type="submit"]')
    pg.wait_for_timeout(1600)
    sp = sports()[0]
    chk('建好了每日步数', sp.get('key') == 'steps', json.dumps(sp, ensure_ascii=False)[:160])
    chk('次数被强制成 1', sp.get('perDay') == 1 and sp.get('freqN') == 1,
        'perDay=%s freqN=%s' % (sp.get('perDay'), sp.get('freqN')))
    card = pg.locator('.mv-card').first
    freq = card.locator('.mv-title small').inner_text()
    chk('卡片频率显示「每天」不带次数', '每天' in freq and '次' not in freq, freq)

    print('\n===== 2. 完成度按总量，点一次不算完成 =====')
    card.locator('[data-act="move-do"]').click()
    pg.wait_for_timeout(800)
    chk('弹的是「记录步数」', '记录步数' in pg.inner_text('#move-record-form h3'),
        pg.inner_text('#move-record-form h3'))
    pg.fill('#move-record-form input[name="steps"]', '1000')
    pg.click('#move-record-form button[type="submit"]')
    pg.wait_for_timeout(1400)
    card = pg.locator('.mv-card').first
    txt = card.inner_text()
    chk('1000/3000 还没达标', '还没达标' in txt, txt[:140])
    chk('环显示完成率 33%', '33%' in txt, txt[:140])
    chk('没弹运动后数据（还没达标）', pg.locator('#move-record-form').count() == 0)

    print('\n===== 3. 达标后弹「补充运动数据」=====')
    card.locator('[data-act="move-do"]').click()
    pg.wait_for_timeout(800)
    pg.fill('#move-record-form input[name="steps"]', '2000')
    pg.click('#move-record-form button[type="submit"]')
    pg.wait_for_timeout(1400)
    chk('弹了补充运动数据', pg.locator('#move-record-form').count() == 1)
    chk('标题是「补充运动数据 · 每日步数」',
        '补充运动数据' in pg.inner_text('#move-record-form h3'), pg.inner_text('#move-record-form h3'))
    fields = pg.eval_on_selector_all('#move-record-body .field > span', 'e=>e.map(x=>x.textContent.trim())')
    chk('只有距离一个字段', len(fields) == 1 and '距离' in fields[0], json.dumps(fields, ensure_ascii=False))
    chk('没有步数输入框（步数已经记好了）', pg.locator('#move-record-body input[name="steps"]').count() == 0)
    pg.fill('#move-record-body input[name="distM"]', '2400')
    pg.click('#move-record-form button[type="submit"]')
    pg.wait_for_timeout(1400)
    card = pg.locator('.mv-card').first
    chk('今天已完成', '今天已完成' in card.locator('.mv-st').inner_text(), card.locator('.mv-st').inner_text())
    chk('填了数据 → 不出现补数据按钮', card.locator('[data-act="move-rec"]').count() == 0,
        card.locator('.mv-btn').all_inner_texts())
    chk('距离写进了同一条记录', len(recs()) == 2 and float(recs()[1].get('distM') or 0) == 2400,
        json.dumps(recs(), ensure_ascii=False)[:200])

    print('\n===== 4. 空数据不许提交 =====')
    card.locator('[data-act="move-edit"]').click()
    pg.wait_for_timeout(800)
    chk('编辑弹窗也没有次数输入框', pg.locator('#move-sport-body #sp-freqn').count() == 0
        and pg.locator('#move-sport-body #sp-perday').count() == 0)
    pg.click('#move-sport-form button[type="submit"]')
    pg.wait_for_timeout(1200)

    print('\n===== 5. 其余 6 种：有运动开始时间 =====')
    pg.click('[data-act="move-new"]')
    pg.wait_for_timeout(500)
    pg.click('.sp-grid .sp-opt[data-k="run"]')
    pg.wait_for_timeout(400)
    chk('跑步有「运动开始时间」输入框', pg.locator('#move-sport-body #sp-starttime').count() == 1)
    chk('默认留空', pg.input_value('#sp-starttime') == '', pg.input_value('#sp-starttime'))
    chk('跑步仍有次数设置', pg.locator('#move-sport-body #sp-freqn').count() == 1)
    pg.fill('#sp-starttime', '07:30')
    pg.wait_for_timeout(200)
    pg.click('#move-sport-form button[type="submit"]')
    pg.wait_for_timeout(1600)
    run = [s for s in sports() if s.get('key') == 'run'][0]
    chk('开始时间存下来了', run.get('startTime') == '07:30', json.dumps(run, ensure_ascii=False)[:200])
    card2 = pg.locator('.mv-card', has_text='跑步').first
    chk('卡片上能看到开始时间', '07:30' in card2.inner_text(), card2.inner_text()[:200])

    print('\n===== 6. 补数据只列勾选的字段 =====')
    card2.locator('[data-act="move-do"]').click()
    pg.wait_for_timeout(900)
    chk('打卡后弹运动后数据', pg.locator('#move-record-form').count() == 1)
    lbl = pg.eval_on_selector_all('#move-record-body .field > span', 'e=>e.map(x=>x.textContent.trim())')
    chk('字段名是「运动时长（分钟）」等', any('运动时长' in x for x in lbl), json.dumps(lbl, ensure_ascii=False))
    chk('有时间字段「任务完成时间」', '任务完成时间' in pg.inner_text('#move-record-form'),
        pg.inner_text('#move-record-form')[:200])
    # 什么都不填直接提交 → 应被拦
    n_before = len(recs())
    pg.click('#move-record-form button[type="submit"]')
    pg.wait_for_timeout(900)
    chk('空数据被拦下，没生成记录', len(recs()) == n_before, str(len(recs())))
    chk('有提示', '至少填写一项有效数据' in pg.inner_text('body'),
        pg.inner_text('body')[-160:])
    # 跳过
    pg.click('#move-record-form [data-act="move-skip"]')
    pg.wait_for_timeout(600)
    pg.click('[data-act="move-skip-ok"]')
    pg.wait_for_timeout(1200)
    card2 = pg.locator('.mv-card', has_text='跑步').first
    chk('跳过 → 出现补数据按钮', card2.locator('[data-act="move-rec"]').count() == 1,
        card2.locator('.mv-btn').all_inner_texts())
    card2.locator('[data-act="move-rec"]').click()
    pg.wait_for_timeout(800)
    chk('补数据弹窗标题', '补数据' in pg.inner_text('#modal-root h3'), pg.inner_text('#modal-root h3'))
    chk('列表里有那一次', '补填' in pg.inner_text('#modal-root'), pg.inner_text('#modal-root')[:200])
    pg.click('#modal-root [data-act="move-fill"]')
    pg.wait_for_timeout(900)
    lbl2 = pg.eval_on_selector_all('#move-record-body .field > span', 'e=>e.map(x=>x.textContent.trim())')
    chk('补填弹窗只出勾选的字段（跑步默认 7 项）', len(lbl2) == 7, json.dumps(lbl2, ensure_ascii=False))
    pg.click('#move-record-form [data-act="close-modal"]')
    pg.wait_for_timeout(400)

    print('\n===== 7. 卡片有「今日任务记录」，底部总表撤了 =====')
    chk('底部没有明细总表了', pg.locator('.dv-list').count() == 0)
    chk('页头有「＋ 添加记录」', pg.locator('[data-act="move-add-rec"]').count() == 1)
    card2.locator('[data-act="move-log"]').click()
    pg.wait_for_timeout(800)
    chk('任务记录弹窗打开', '今日任务记录' in pg.inner_text('#modal-root h3'), pg.inner_text('#modal-root h3'))
    chk('里面有今天的记录', pg.locator('#modal-root .sp-recrow').count() >= 1,
        str(pg.locator('#modal-root .sp-recrow').count()))
    pg.click('#modal-root [data-act="close-modal"]')
    pg.wait_for_timeout(400)

    print('\n===== 8. 无 JS 报错 =====')
    chk('没有 JS 错误', not errs, str(errs[:3]))

    br.close()

print('\n===== 结果：%d 通过 / %d 失败 =====' % (PASS, FAIL))
if FAILS:
    for n, d in FAILS:
        print('  FAIL: %s  << %s' % (n, d))
    sys.exit(1)
print('全部通过')
