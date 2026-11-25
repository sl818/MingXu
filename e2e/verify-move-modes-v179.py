# -*- coding: utf-8 -*-
"""v179 运动模式与运动数据记录验证（按陛下 2026-11-25 的表）：

1. 模式只剩 7 种：每日步数 / 跑步 / 健走 / 骑行 / 跳绳 / 力量训练 / 球类运动
   —— 游泳、瑜伽下线，新建列表里不出现
2. 每种模式的「运动目标类型」与「可记录的运动数据」逐项对照表格
3. 「记录字段」已改名「运动数据记录」
4. 补数据表单只显示该运动勾选过的数据项
5. 编辑一条已下线的历史运动（游泳）时，网格里仍能看到它并标「已下线」
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

# 初始：一条已下线的历史运动（游泳），用于验证「编辑老数据仍可用」
board = {'data': {
    'version': 2, 'schemaVersion': 2, 'view': 'today',
    'habits': HABITS,
    'modules': {'move': {
        'on': True, 'name': '运动', 'icon': '🏃', 'color': '#b5733f', 'note': '',
        'unit': '次', 'times': 1,
        'sports': [{'id': 'sp_swim', 'key': 'swim', 'name': '游泳', 'unit': '米', 'goal': 800,
                    'tIdx': 0, 'tVal': 800, 'freqKind': 'daily', 'freqN': 1, 'perDay': 1,
                    'weekSel': [0, 1, 2, 3, 4, 5, 6], 'recMode': 'manual', 'fixedSteps': 1000,
                    'fields': ['dist', 'dur', 'stroke'],
                    'strokePick': '蛙泳', 'notifyOn': True, 'channels': ['browser']}],
        'records': [],
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


# 陛下表格：模式 -> (目标类型, 可记录数据)
SPEC = {
    'steps': (['每日步数（步）'], ['距离']),
    'run': (['每次距离（公里）', '每次时长（分钟）'], ['运动时长', '距离', '配速', '步频', '心率', '热量消耗', '步幅']),
    'walk': (['每次距离（公里）', '每次时长（分钟）'], ['运动时长', '距离', '配速', '步频', '心率', '热量消耗', '步幅']),
    'ride': (['每次距离（公里）', '每次时长（分钟）'], ['运动时长', '骑行里程', '踏频', '心率', '热量消耗', '平均速度']),
    'rope': (['每次时长（分钟）'], ['运动时长', '总次数', '每分钟跳频', '心率', '热量消耗']),
    'strength': (['每次时长（分钟）'], ['运动时长', '组数', '次数', '负重重量', '组间休息', '心率', '热量消耗']),
    'ball': (['每次时长（分钟）'], ['运动时长', '心率区间', '平均心率', '热量消耗']),
}
ORDER = ['steps', 'run', 'walk', 'ride', 'rope', 'strength', 'ball']


def probe(pg, key):
    pg.click('.sp-grid .sp-opt[data-k="%s"]' % key)
    pg.wait_for_timeout(260)
    tgt = pg.eval_on_selector_all('#move-sport-body #sp-target option', 'e => e.map(x => x.textContent.trim())')
    if not tgt:
        tgt = pg.eval_on_selector_all('#move-sport-body .sp-tlbl', 'e => e.map(x => x.textContent.trim())')
    fld = pg.eval_on_selector_all('#move-sport-body .sp-field-chk b', 'e => e.map(x => x.textContent.replace(/（.*$/, "").trim())')
    return tgt, fld


with sync_playwright() as pw:
    br = pw.chromium.launch(channel='chrome')
    ctx = br.new_context(viewport={'width': 1200, 'height': 1100})
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

    print('\n===== 1. 模式列表（游泳 / 瑜伽已下线）=====')
    pg.click('[data-act="move-new"]')
    pg.wait_for_timeout(450)
    keys = pg.eval_on_selector_all('.sp-grid .sp-opt', 'e => e.map(x => x.dataset.k)')
    chk('网格正好 7 种模式', len(keys) == 7, str(keys))
    chk('顺序正确', keys == ORDER, str(keys))
    chk('不含 swim', 'swim' not in keys)
    chk('不含 yoga', 'yoga' not in keys)
    names = pg.eval_on_selector_all('.sp-grid .sp-opt', 'e => e.map(x => x.textContent.trim())')
    chk('球类显示为「球类运动」', any('球类运动' in n for n in names), str(names))

    print('\n===== 2. 逐模式核对「运动目标类型 / 可记录数据」=====')
    for k in ORDER:
        want_t, want_f = SPEC[k]
        got_t, got_f = probe(pg, k)
        chk('%s 目标类型' % k, got_t == want_t, '得到 %s / 期望 %s' % (got_t, want_t))
        chk('%s 可记录数据' % k, got_f == want_f, '得到 %s / 期望 %s' % (got_f, want_f))
    txt = pg.inner_text('#move-sport-body')
    chk('文案已改为「运动数据记录」', '运动数据记录' in txt)
    chk('不再出现旧的「记录字段」标题', '记录字段' not in txt)
    pg.click('[data-act="close-modal"]')
    pg.wait_for_timeout(300)

    print('\n===== 3. 编辑已下线的历史运动（游泳）=====')
    pg.click('.mv-card [data-act="move-edit"]')
    pg.wait_for_timeout(500)
    k2 = pg.eval_on_selector_all('.sp-grid .sp-opt', 'e => e.map(x => x.dataset.k)')
    chk('网格里出现待编辑的游泳（8 格）', k2 == ORDER + ['swim'], str(k2))
    chk('游泳卡上标「已下线」', '已下线' in pg.inner_text('.sp-grid'))
    chk('游泳的泳姿仍可显示', '泳姿' in pg.inner_text('#move-sport-body'))
    pg.click('[data-act="close-modal"]')
    pg.wait_for_timeout(300)

    print('\n===== 4. 补数据只显示勾选过的数据项 =====')
    pg.click('[data-act="move-new"]')
    pg.wait_for_timeout(450)
    pg.click('.sp-grid .sp-opt[data-k="strength"]')
    pg.wait_for_timeout(300)
    # 只留「时长」「组数」，其余取消
    for fk in ['reps', 'weight', 'rest', 'heart', 'kcal']:
        sw = pg.locator('#move-sport-body .sp-field-chk', has=pg.locator('input[data-fld="%s"]' % fk)).locator('.switch').first
        sw.scroll_into_view_if_needed()
        sw.click()
        pg.wait_for_timeout(160)
    left = pg.eval_on_selector_all('#move-sport-body [data-fld]', 'e => e.filter(x => x.checked).map(x => x.dataset.fld)')
    chk('只剩 时长 + 组数 被勾选', sorted(set(left)) == ['dur', 'sets'], str(left))
    pg.click('#move-sport-form button[type="submit"]')
    pg.wait_for_timeout(1600)
    sps = board['data']['modules']['move'].get('sports') or []
    st = [s for s in sps if s.get('key') == 'strength']
    chk('力量训练保存成功', len(st) == 1, str(len(st)))
    chk('存档里的 fields 只有 dur/sets', sorted(st[0].get('fields') or []) == ['dur', 'sets'], str(st[0].get('fields')))

    # 打卡后弹「运动后数据」弹窗，检查表单字段（v184：补数据入口只在跳过后出现）
    card = pg.locator('.mv-card', has_text='力量训练').first
    card.locator('[data-act="move-do"]').click()
    pg.wait_for_timeout(900)
    names_in_form = pg.eval_on_selector_all('#move-record-body [name]', 'e => e.map(x => x.name)')
    chk('运动后数据表单只有 时长 / 组数', sorted([n for n in names_in_form if n not in ('d', 't')]) == ['dur', 'sets'],
        str(names_in_form))
    chk('表单里没有「负重重量」', pg.locator('#move-record-body [name="weight"]').count() == 0)
    pg.fill('#move-record-body [name="dur"]', '30')
    pg.fill('#move-record-body [name="sets"]', '3')
    pg.click('#move-record-form button[type="submit"]')
    pg.wait_for_timeout(1500)
    card.locator('[data-act="move-log"]').click()
    pg.wait_for_timeout(700)
    dv = pg.inner_text('#modal-root')
    chk('明细摘要含「30 分钟」', '30 分钟' in dv, dv[:160])
    chk('明细摘要含「3 组」', '3 组' in dv, dv[:160])
    pg.click('#modal-root [data-act="close-modal"]')
    pg.wait_for_timeout(400)
    chk('卡片显示记录数据 2 项', '记录数据' in pg.locator('.mv-card', has_text='力量训练').first.inner_text())

    chk('全流程无 JS 异常', not errs, str(errs[:2]))
    br.close()

srv.shutdown()
print('\n============================================================')
print('v179 模式与数据记录：%d 通过 / %d 失败' % (PASS, FAIL))
if FAILS:
    for n, d in FAILS:
        print('  - %s | %s' % (n, d))
sys.exit(1 if FAIL else 0)
