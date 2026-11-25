# -*- coding: utf-8 -*-
"""v178 运动频率与通知开关验证：

1. 频率按钮文案是「每天运动 / 每周选日运动」（不再是一天一次 / 一周一次的歧义写法）
2. 「每周选日运动」也能设「每个执行日几次」，并且达标按次数算
   （设 2 次：打 1 次不算完成，打 2 次才算）
3. 弹窗里有「接收这个运动的提醒」总开关：
   * 关掉 → 渠道区消失、保存后 channels 为空
   * 三个渠道可以全部取消，且重新打开不会被自动塞回一个
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
    {'id': 'h_med', 'name': '用药', 'icon': '💊', 'type': 'build', 'target': 1, 'unit': '次',
     'color': '#2f6f5e', 'note': '', 'createdAt': '2026-09-01T08:00:00Z', 'pinned': True, 'med': True},
    {'id': 'h_water', 'name': '喝水', 'icon': '💧', 'type': 'build', 'target': 9, 'unit': '杯',
     'color': '#4c7f96', 'note': '', 'createdAt': '2026-09-01T08:00:00Z', 'pinned': True},
    {'id': 'h_move', 'name': '运动', 'icon': '🏃', 'type': 'build', 'target': 1, 'unit': '次',
     'color': '#b5733f', 'note': '', 'createdAt': '2026-09-01T08:00:00Z', 'pinned': True},
    {'id': 'h_breathe', 'name': '478呼吸法', 'icon': '🌬️', 'type': 'build', 'target': 1, 'unit': '组',
     'color': '#5b8f8a', 'note': '', 'createdAt': '2026-09-01T08:00:00Z', 'pinned': True, 'optional': True},
    {'id': 'h_drink', 'name': '戒烟', 'icon': '🚭', 'type': 'smoke', 'target': 1, 'unit': '次',
     'color': '#7a8471', 'note': '', 'createdAt': '2026-09-01T08:00:00Z', 'pinned': True},
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


def sports_now():
    return board['data']['modules']['move'].get('sports') or []


with sync_playwright() as pw:
    br = pw.chromium.launch(channel='chrome')
    ctx = br.new_context(viewport={'width': 1440, 'height': 1000})
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

    print('\n===== 1. 频率按钮文案 =====')
    pg.click('[data-act="move-new"]')
    pg.wait_for_timeout(400)
    labels = pg.eval_on_selector_all('#move-sport-body .sp-freq-opt', 'els=>els.map(e=>e.textContent.trim())')
    chk('两个按钮文案是「每天运动 / 每周选日运动」', labels == ['每天运动', '每周选日运动'], json.dumps(labels, ensure_ascii=False))
    chk('不再出现「每天 1 次」这种歧义写法', '每天 1 次' not in json.dumps(labels, ensure_ascii=False))

    print('\n===== 2. 每周选日运动也能设「每个执行日几次」=====')
    pg.click('.sp-grid .sp-opt[data-k="run"]')
    pg.wait_for_timeout(250)
    pg.click('#move-sport-body .sp-freq-opt[data-fk2="weekly"]')
    pg.wait_for_timeout(300)
    chk('每周模式出现「每个执行日几次」输入框', pg.locator('#move-sport-body #sp-perday').count() == 1)
    chk('默认是 1 次', pg.input_value('#sp-perday') == '1', pg.input_value('#sp-perday'))
    # 只选周六（今天），每天 2 次
    on_days = pg.eval_on_selector_all('#sp-week button.on', 'els=>els.map(e=>e.dataset.d)')
    for d in on_days:
        if d != '6':
            pg.click('#sp-week button[data-d="%s"]' % d)
            pg.wait_for_timeout(90)
    if '6' not in on_days:
        pg.click('#sp-week button[data-d="6"]')
        pg.wait_for_timeout(90)
    chk('只选周六一天', pg.locator('#sp-week button.on').count() == 1)
    pg.fill('#sp-perday', '2')
    pg.wait_for_timeout(150)
    # 关掉通知
    chk('弹窗里有「接收这个运动的提醒」开关', pg.locator('#sp-notify').count() == 1)
    pg.click('#move-sport-body .mv-toggle-row .w-switch')
    pg.wait_for_timeout(300)
    chk('关掉通知后渠道区隐藏', pg.locator('#move-sport-body .sp-chan').count() == 0)
    pg.click('#move-sport-form button[type="submit"]')
    pg.wait_for_timeout(1600)

    sp = sports_now()
    chk('保存了 1 个运动', len(sp) == 1, str(len(sp)))
    s0 = sp[0]
    chk('perDay 存成 2', s0.get('perDay') == 2, json.dumps(s0, ensure_ascii=False)[:200])
    chk('notifyOn 存成 false', s0.get('notifyOn') is False, str(s0.get('notifyOn')))
    chk('channels 存成空数组', s0.get('channels') == [], str(s0.get('channels')))
    card_txt = pg.inner_text('.mv-card')
    chk('卡片频率写「每天 2 次」', '每天 2 次' in card_txt, card_txt[:120])

    print('\n===== 3. 打卡后先记录数据，才能开始下一次（v181）=====')
    pg.click('.mv-card [data-act="move-do"]')
    pg.wait_for_timeout(800)
    chk('打卡后自动弹出记录表单', pg.locator('#move-record-form').count() == 1)
    chk('标题写明第 1 次', '第 1 次' in pg.inner_text('#move-record-form'))
    chk('表单里有「跳过不记录」', pg.locator('#move-record-form [data-act="move-skip"]').count() == 1)
    # 先关掉弹窗：这一次没处理完，主按钮应变成「记录数据」，且不能再打一次
    pg.click('#move-record-form [data-act="close-modal"]')
    pg.wait_for_timeout(400)
    c1 = pg.inner_text('.mv-card')
    chk('主按钮变成「记录数据」', pg.locator('.mv-card [data-act="move-fill"]').count() == 1)
    chk('此时不能再点「去运动」', pg.locator('.mv-card [data-act="move-do"]').count() == 0)
    chk('状态行提示等记录数据', '等记录这一次的数据' in c1, c1[:140])
    # 填完这一次的数据
    pg.click('.mv-card [data-act="move-fill"]')
    pg.wait_for_timeout(700)
    pg.fill('#move-record-body [name="dur"]', '32')
    pg.click('#move-record-form button[type="submit"]')
    pg.wait_for_timeout(1300)
    c2 = pg.inner_text('.mv-card')
    chk('填完后仍未达标（1 / 2）', '今天已完成' not in c2 and '1 / 2' in c2, c2[:140])
    chk('主按钮回到「去运动」', pg.locator('.mv-card [data-act="move-do"]').count() == 1)

    print('\n===== 4. 第二次打卡 → 跳过记录 → 仍算完成 =====')
    pg.click('.mv-card [data-act="move-do"]')
    pg.wait_for_timeout(800)
    pg.click('#move-record-form [data-act="move-skip"]')
    pg.wait_for_timeout(500)
    root = pg.inner_text('#modal-root')
    chk('跳过前先弹二次确认', '跳过不记录这次的数据' in root, root[:120])
    chk('确认框讲清统计里看不到详细数据', '不会显示它的详细数据' in root, root[:160])
    pg.click('[data-act="move-skip-ok"]')
    pg.wait_for_timeout(1200)
    c3 = pg.inner_text('.mv-card')
    chk('跳过也算完成（2 / 2）', '今天已完成' in c3, c3[:140])
    # v184：页面底部的明细总表已撤，改到卡片里的「今日任务记录」看
    pg.click('.mv-card [data-act="move-log"]')
    pg.wait_for_timeout(800)
    dv = pg.inner_text('#modal-root')
    chk('任务记录里这条标「未记录详细数据」', '未记录详细数据' in dv, dv[:200])
    pg.click('#modal-root [data-act="close-modal"]')
    pg.wait_for_timeout(400)

    print('\n===== 5. 三个渠道可以全部取消，且不会被塞回一个 =====')
    pg.click('.mv-card [data-act="move-edit"]')
    pg.wait_for_timeout(500)
    chk('重新打开时通知开关是关的', pg.locator('#sp-notify').is_checked() is False)
    pg.click('#move-sport-body .mv-toggle-row .w-switch')   # 打开
    pg.wait_for_timeout(350)
    chk('打开后渠道区出现', pg.locator('#move-sport-body .sp-chan').count() == 1)
    chk('打开后三个渠道都没选（保存的是空数组）',
        pg.locator('#move-sport-body .sp-chan-opt input:checked').count() == 0,
        'checked=%d' % pg.locator('#move-sport-body .sp-chan-opt input:checked').count())
    # 勾一个再取消，验证能取消干净
    mail_card = pg.locator('#move-sport-body .sp-chan-opt', has_text='邮件通知').first
    mail_card.scroll_into_view_if_needed()
    pg.wait_for_timeout(250)
    mail_card.click()
    pg.wait_for_timeout(450)
    chk('勾上邮件后是选中态', pg.locator('#move-sport-body .sp-chan-opt input[value="mail"]').is_checked())
    mail_card.click()
    pg.wait_for_timeout(450)
    chk('再点一下能取消（不再强制保留）',
        pg.locator('#move-sport-body .sp-chan-opt input:checked').count() == 0,
        'checked=%d' % pg.locator('#move-sport-body .sp-chan-opt input:checked').count())
    tip = pg.inner_text('#sp-chan-tip').strip()
    chk('全取消后有明确提示', '还没选任何渠道' in tip, tip)
    pg.click('#move-sport-form button[type="submit"]')
    pg.wait_for_timeout(1500)
    s1 = sports_now()[0]
    chk('保存后 channels 仍是空', s1.get('channels') == [], str(s1.get('channels')))
    chk('保存后 notifyOn 仍为 true（开关是开的）', s1.get('notifyOn') is True, str(s1.get('notifyOn')))
    # 刷一次页面确认不会自己冒出 browser
    pg.reload(wait_until='networkidle')
    pg.wait_for_timeout(2600)
    nav(pg, 'move')
    pg.click('.mv-card [data-act="move-edit"]')
    pg.wait_for_timeout(500)
    chk('刷新后重开，三个渠道仍是全不选',
        pg.locator('#move-sport-body .sp-chan-opt input:checked').count() == 0,
        'checked=%d' % pg.locator('#move-sport-body .sp-chan-opt input:checked').count())

    chk('全流程无 JS 异常', not errs, str(errs[:2]))
    br.close()

srv.shutdown()
print('\n============================================================')
print('v178 频率与通知开关：%d 通过 / %d 失败' % (PASS, FAIL))
if FAILS:
    for n, d in FAILS:
        print('  - %s | %s' % (n, d))
sys.exit(1 if FAIL else 0)
