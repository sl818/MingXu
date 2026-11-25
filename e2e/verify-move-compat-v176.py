# -*- coding: utf-8 -*-
"""v176 运动兼容验证：v175 的旧运动数据必须能被正确迁移。

覆盖的旧形态：
  * sports 用 goal / freq / n / fields(字符串数组) / recMode = once|multi
  * freq = weekly_times、free（v176 已删除这两档）
  * records 没有 recMode / hour / count
  * 更老的记录没有 sportId（只能靠 key 关联）
断言：加载不报错、卡片与统计按旧数据正确显示、编辑保存后回写成新结构。
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
D = '2026-10-25'

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

# —— v175 形态的 modules.move ——
OLD_MOVE = {
    'on': True, 'name': '运动', 'icon': '🏃', 'color': '#b5733f', 'note': '',
    'unit': '次', 'times': 1,
    'sports': [
        # 步数：旧 goal 8000，recMode=once（v176 已废弃）
        {'id': 'sp1', 'key': 'steps', 'name': '每日步数', 'icon': '👟', 'unit': '步', 'goal': 8000,
         'freq': 'daily', 'n': 1, 'fields': [], 'recMode': 'once', 'stroke': '',
         'createdAt': '2026-10-01T08:00:00Z', 'updatedAt': '2026-10-01T08:00:00Z'},
        # 跑步：旧 freq=weekly_times（v176 已删除）
        {'id': 'sp2', 'key': 'run', 'name': '跑步', 'icon': '🏃', 'unit': '公里', 'goal': 5,
         'freq': 'weekly_times', 'n': 3, 'fields': ['pace', 'heart'], 'recMode': 'manual', 'stroke': '',
         'createdAt': '2026-10-01T08:00:00Z', 'updatedAt': '2026-10-01T08:00:00Z'},
        # 游泳：旧 freq=free，有泳姿
        {'id': 'sp3', 'key': 'swim', 'name': '游泳', 'icon': '🏊', 'unit': '米', 'goal': 800,
         'freq': 'free', 'n': 1, 'fields': ['stroke', 'pace'], 'recMode': 'manual', 'stroke': '蛙泳',
         'createdAt': '2026-10-01T08:00:00Z', 'updatedAt': '2026-10-01T08:00:00Z'},
    ],
    'records': [
        # 旧记录：无 recMode / hour / count
        {'id': 'r1', 'sportId': 'sp1', 'key': 'steps', 'd': D, 'at': D + 'T19:10:00.000Z', 'steps': 8500},
        {'id': 'r2', 'sportId': 'sp2', 'key': 'run', 'd': D, 'at': D + 'T18:20:00.000Z',
         'dist': 5.2, 'dur': 32, 'pace': '6:10', 'heart': 145},
        # 更老的记录连 sportId 都没有
        {'id': 'r3', 'sportId': '', 'key': 'swim', 'd': D, 'at': D + 'T12:30:00.000Z',
         'dist': 900, 'stroke': '蛙泳'},
    ],
    'notifyChannels': ['browser'], 'notify': True,
    'suggestTime': '', 'notifyFreq': 'daily', 'notifyWeekday': 1, 'notifyMonthday': 1,
    'notifyNote': '', 'createdAt': '2026-09-01T08:00:00Z', 'updatedAt': '2026-10-01T08:00:00Z',
}

board = {'data': {
    'version': 2, 'schemaVersion': 2, 'view': 'today',
    'habits': HABITS,
    'modules': {'move': OLD_MOVE},
    'modulesAt': 0,
    'checks': {}, 'skips': {}, 'notes': {}, 'moods': {}, 'events': [],
    'meds': [], 'doses': {}, 'bodyProfile': {'age': 30, 'height': 170},
    'weights': [], 'essays': [], 'tasks': [], 'money': {}, 'quit': {},
}, 'rev': 5}


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
    pg.wait_for_timeout(500)


with sync_playwright() as pw:
    br = pw.chromium.launch(channel='chrome')
    ctx = br.new_context(viewport={'width': 1440, 'height': 1000})
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))

    pg.clock.install(time=datetime(2026, 10, 25, 20, 0, 0))
    pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
    pg.wait_for_timeout(600)
    pg.click('[data-act="cloud-login"]')
    pg.wait_for_timeout(400)
    pg.fill('input[name="email"]', 'test@example.com')
    pg.fill('input[name="password"]', 'test@example.com')
    pg.click('form.modal-card button[type="submit"]')
    pg.wait_for_timeout(2800)

    nav(pg, 'move')
    txt = pg.inner_text('.move-page')

    print('\n===== 1. 旧数据加载 =====')
    chk('三张运动卡都渲染出来', pg.locator('.mv-card').count() == 3,
        'cards=%d' % pg.locator('.mv-card').count())
    chk('没有未捕获 JS 异常', not errs, str(errs[:2]))

    print('\n===== 2. 旧 goal 迁到目标值 =====')
    chk('步数目标仍是 8000 步', '8000 步' in txt)
    chk('跑步目标仍是 5 公里', '5 公里' in txt)
    chk('游泳目标仍是 800 米', '800 米' in txt)

    print('\n===== 3. 旧记录仍算达标（含 sportId 为空的更老记录）=====')
    cards = pg.evaluate("""() => Array.from(document.querySelectorAll('.mv-card')).map(c => ({
        name: c.querySelector('.mv-title b').textContent.trim(),
        st: (c.querySelector('.mv-st') || {}).textContent || ''
    }))""")
    st = {c['name']: c['st'].strip() for c in cards}
    chk('步数 8500 ≥ 8000 → 今天已完成', st.get('每日步数', '') == '今天已完成', json.dumps(st, ensure_ascii=False))
    chk('跑步有记录 → 今天已完成', st.get('跑步', '') == '今天已完成', json.dumps(st, ensure_ascii=False))
    chk('游泳无 sportId 的旧记录也认 → 今天已完成', st.get('游泳', '') == '今天已完成', json.dumps(st, ensure_ascii=False))

    print('\n===== 4. 旧频率迁移（weekly_times / free → 每周 N 天）=====')
    chk('界面不再出现「每周 3 次」这种旧口径', '每周 3 次' not in txt)
    chk('跑步显示「每周 7 天」', '每周 7 天' in txt, [l for l in txt.split('\n') if '每周' in l][:3])

    print('\n===== 5. 编辑弹窗回填 + 保存回写新结构 =====')
    pg.locator('.mv-card', has_text='跑步').locator('[data-act="move-edit"]').first.click()
    pg.wait_for_timeout(500)
    chk('编辑弹窗打开且为「编辑运动」', '编辑运动' in pg.inner_text('#move-sport-form'))
    chk('跑步回填 5 公里目标', pg.input_value('#sp-tval') == '5', pg.input_value('#sp-tval'))
    chk('频率回填到「每周 N 天」', pg.locator('#move-sport-body .sp-freq-opt[data-fk2="weekly"].on').count() == 1)
    chk('7 个星期按钮全部选中', pg.locator('#sp-week button.on').count() == 7,
        'on=%d' % pg.locator('#sp-week button.on').count())
    pg.click('#move-sport-form button[type="submit"]')
    pg.wait_for_timeout(1500)

    saved = board['data']['modules']['move']['sports']
    sp_run = [s for s in saved if s.get('key') == 'run'][0]
    chk('回写后 freqKind = weekly', sp_run.get('freqKind') == 'weekly', json.dumps(sp_run, ensure_ascii=False)[:160])
    chk('回写后 weekSel 是 7 天', len(sp_run.get('weekSel') or []) == 7)
    chk('回写后 tVal = 5', sp_run.get('tVal') == 5)
    chk('回写后保留 pace/heart 字段', set(sp_run.get('fields') or []) == {'pace', 'heart'},
        json.dumps(sp_run.get('fields'), ensure_ascii=False))

    print('\n===== 6. recMode=once 等旧值被收敛 =====')
    sp_steps = [s for s in saved if s.get('key') == 'steps'][0]
    chk('步数 recMode 收敛为 manual / fixed', sp_steps.get('recMode') in ('manual', 'fixed'),
        str(sp_steps.get('recMode')))
    sp_swim = [s for s in saved if s.get('key') == 'swim'][0]
    chk('游泳 strokePick 继承旧 stroke（蛙泳）', sp_swim.get('strokePick') == '蛙泳',
        str(sp_swim.get('strokePick')))

    print('\n===== 7. 统计与明细 =====')
    pg.reload(wait_until='networkidle')
    pg.wait_for_timeout(2600)
    nav(pg, 'move')
    t2 = pg.inner_text('.move-page')
    chk('数据统计仍在', '数据统计' in t2)
    # v184：底部明细总表撤了，明细改到卡片里的「今日任务记录」
    chk('底部不再有明细总表', pg.locator('.dv-list').count() == 0)
    pg.locator('.mv-card [data-act="move-log"]').first.click()
    pg.wait_for_timeout(800)
    chk('任务记录里能查到记录', pg.locator('#modal-root .sp-recrow').count() >= 1,
        'rows=%d' % pg.locator('#modal-root .sp-recrow').count())
    pg.click('#modal-root [data-act="close-modal"]')
    pg.wait_for_timeout(400)
    chk('重置后三张卡仍在', pg.locator('.mv-card').count() == 3)
    chk('全流程无 JS 异常', not errs, str(errs[:2]))

    br.close()

srv.shutdown()
print('\n============================================================')
print('v176 运动兼容：%d 通过 / %d 失败' % (PASS, FAIL))
if FAILS:
    for n, d in FAILS:
        print('  - %s | %s' % (n, d))
sys.exit(1 if FAIL else 0)
