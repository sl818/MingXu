# -*- coding: utf-8 -*-
"""v185 运动优化：五条实测反馈 + 「真人走一遍」回归。

覆盖 docs/MOVE-OPTIMIZATION.md 4.2 的 A~G 矩阵（只列与五条需求相关的项）：

一、需求 3 · 勾选回显（往返）
  1. 新建时默认全勾（行为不变）
  2. 全部取消 → 保存 → 重开编辑 → 仍然全部未勾
  3. 只勾 3 项 → 保存 → 重开编辑 → 仍然只有那 3 项

二、需求 5 · 记录方式锁定
  4. 编辑时当前那种高亮、另一种置灰；误点只提示不切换
  5. 固定步数的数值仍可改

三、需求 1 · 「补数据」按钮改名 + 填红
  6. 跳过一次后出现「补充运动后详细数据」，底色 #DC2626
  7. 补填完按钮消失

四、需求 2 · 今日任务记录逐字段展开
  8. 每天 2 次：出现「第一次运动：」「第二次运动：」，每字段一行
  9. 每天 1 次：没有组标题，直接列字段行
 10. 填了 7 项就列 7 行，不截断

五、需求 4 · 每日步数的「距离」归位
 11. 打卡弹窗没有距离
 12. 达标后补充弹窗只有距离，且写进同一条记录（次数不翻倍）

六、D 一致性 / E 跨天
 13. 取消勾选后旧记录里的旧值不丢（只是不再显示）
 14. 昨天补录的记录不出现在「今日任务记录」里

七、G 边界
 15. 一个字段都没勾的运动：打卡后只能「跳过不记录」
 16. 全程无 JS 报错
"""
import http.server
import json
import secrets
import socketserver
import threading
from datetime import datetime

from playwright.sync_api import sync_playwright

DOC = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo'
USER = {'id': 1, 'email': 'test@example.com', 'display_name': '测试', 'is_admin': False}
sessions = {}
D = '2026-10-24'          # 周六
YDAY = '2026-10-23'
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


def move_mod():
    return board['data']['modules']['move']


def sports():
    return move_mod().get('sports') or []


def recs():
    return move_mod().get('records') or []


def sport_by_key(k):
    for s in sports():
        if s.get('key') == k:
            return s
    return None


def card_of(pg, sid):
    return pg.locator('.mv-card[data-id="%s"]' % sid)


def open_new(pg, key):
    pg.click('[data-act="move-new"]')
    pg.wait_for_timeout(400)
    pg.click('#move-sport-form .sp-grid .sp-opt[data-k="%s"]' % key)
    pg.wait_for_timeout(250)


def submit_sport(pg):
    pg.click('#move-sport-form button[type="submit"]')
    pg.wait_for_timeout(1200)


def checked_fields(pg):
    return pg.eval_on_selector_all(
        '#move-sport-body .sp-field-chk input[data-fld]',
        'e => e.filter(x => x.checked).map(x => x.dataset.fld)')


def set_field(pg, k, on):
    """点一下某个字段的开关；每次重新取 locator —— onchange 会整块重渲染。"""
    cb = pg.locator('#move-sport-body .sp-field-chk input[data-fld="%s"]' % k)
    if cb.is_checked() != on:
        cb.click(force=True)
        pg.wait_for_timeout(150)


def open_edit(pg, sid):
    card_of(pg, sid).locator('[data-act="move-edit"]').click()
    pg.wait_for_timeout(600)


def close_modal(pg):
    pg.click('#modal-root [data-act="close-modal"]')
    pg.wait_for_timeout(400)


def do_sport(pg, sid):
    card_of(pg, sid).locator('[data-act="move-do"]').click()
    pg.wait_for_timeout(700)


def fill_rec(pg, vals):
    for k, v in vals.items():
        el = pg.locator('#move-record-form [name="%s"]' % k)
        if el.count():
            el.fill(str(v))
    pg.click('#move-record-form button[type="submit"]')
    pg.wait_for_timeout(900)


def open_log(pg, sid):
    card_of(pg, sid).locator('[data-act="move-log"]').click()
    pg.wait_for_timeout(700)


def fold_open(pg):
    """两个折叠区当前是否展开（v186 起默认都收起）"""
    return pg.eval_on_selector_all('#modal-root .sp-fold', 'e => e.map(x => x.open)')


def expand_folds(pg):
    """把「运动日志」「运动后数据」都展开（已展开的不动，避免点成收起）"""
    for i in range(pg.locator('#modal-root .sp-fold').count()):
        box = pg.locator('#modal-root .sp-fold').nth(i)
        if not box.evaluate('e => e.open'):
            box.locator('summary').click()
            pg.wait_for_timeout(280)


def rec_text(pg, sid):
    open_log(pg, sid)
    expand_folds(pg)
    return pg.inner_text('#modal-root')


with sync_playwright() as pw:
    br = pw.chromium.launch(channel='chrome')
    ctx = br.new_context(viewport={'width': 1440, 'height': 1000})
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    dlg = {'n': 0, 'msg': ''}

    def on_dlg(d):
        dlg['n'] += 1
        dlg['msg'] = d.message
        d.accept()

    pg.on('dialog', on_dlg)

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

    # ============================================================
    print('\n===== 1. 需求3：勾选默认值 + 往返（新建全勾）=====')
    open_new(pg, 'rope')
    got = checked_fields(pg)
    chk('新建跳绳默认全勾 5 项', got == ['dur', 'count', 'ropeRate', 'heart', 'kcal'], str(got))
    for k in ['dur', 'count', 'ropeRate', 'heart', 'kcal']:
        set_field(pg, k, False)
    chk('界面上已全部取消', checked_fields(pg) == [], str(checked_fields(pg)))
    submit_sport(pg)
    rope = sport_by_key('rope')
    chk('存档 fields 是空数组', rope is not None and rope.get('fields') == [],
        str(rope and rope.get('fields')))

    print('\n===== 2. 需求3：全部取消 → 重开编辑 → 仍然全不勾（往返）=====')
    open_edit(pg, rope['id'])
    got = checked_fields(pg)
    chk('重开编辑后仍全部未勾', got == [], str(got))
    chk('没有 checkbox 被默认勾上',
        pg.eval_on_selector_all('#move-sport-body .sp-field-chk input[data-fld]',
                                'e => e.every(x => !x.checked)'))
    close_modal(pg)

    print('\n===== 3. 需求3：只勾 3 项 → 重开仍是那 3 项 =====')
    open_edit(pg, rope['id'])
    for k in ['count', 'heart', 'kcal']:
        set_field(pg, k, True)
    submit_sport(pg)
    rope = sport_by_key('rope')
    chk('存档 fields 只有 count/heart/kcal',
        sorted(rope.get('fields') or []) == ['count', 'heart', 'kcal'], str(rope.get('fields')))
    open_edit(pg, rope['id'])
    got = checked_fields(pg)
    chk('重开编辑后只有那 3 项勾着', sorted(got) == ['count', 'heart', 'kcal'], str(got))
    close_modal(pg)

    # ============================================================
    print('\n===== 4. 需求5：记录方式编辑态锁定 =====')
    open_new(pg, 'steps')
    pg.fill('#sp-tval', '1000')
    submit_sport(pg)
    step1 = sport_by_key('steps')
    chk('新建的是手动记录方式', step1.get('recMode') == 'manual', str(step1.get('recMode')))
    open_edit(pg, step1['id'])
    on_cls = pg.eval_on_selector_all('#move-sport-body .sp-rec-opt',
                                     'e => e.map(x => [x.dataset.rm, x.className])')
    manual_cls = [c for k, c in on_cls if k == 'manual'][0]
    fixed_cls = [c for k, c in on_cls if k == 'fixed'][0]
    chk('当前那种（手动）保持高亮', 'on' in manual_cls and 'locked' not in manual_cls, manual_cls)
    chk('另一种（固定步数）置灰', 'locked' in fixed_cls, fixed_cls)
    chk('锁定提示在弹窗里', '记录方式建好后不能修改' in pg.inner_text('#move-sport-body'),
        pg.inner_text('#move-sport-body')[:80])
    pg.click('#move-sport-body .sp-rec-opt[data-rm="fixed"]')
    pg.wait_for_timeout(350)
    chk('误点灰掉的那项只给提示不切换',
        'on' in pg.eval_on_selector('#move-sport-body .sp-rec-opt[data-rm="manual"]', 'e => e.className'),
        pg.eval_on_selector('#move-sport-body .sp-rec-opt[data-rm="manual"]', 'e => e.className'))
    chk('提示文案出现', '记录方式建好后不能修改' in pg.inner_text('#toast'),
        pg.inner_text('#toast'))
    chk('固定步数输入框没出来（没切换）', pg.locator('#sp-fixed').count() == 0)
    submit_sport(pg)
    step1 = sport_by_key('steps')
    chk('存档里记录方式仍是 manual', step1.get('recMode') == 'manual', str(step1.get('recMode')))

    print('\n===== 5. 需求5：固定步数的数值仍可改 =====')
    open_new(pg, 'steps')
    pg.fill('#sp-tval', '5000')
    pg.click('#move-sport-body .sp-rec-opt[data-rm="fixed"]')
    pg.wait_for_timeout(250)
    pg.fill('#sp-fixed', '800')
    submit_sport(pg)
    step2 = [s for s in sports() if s.get('key') == 'steps' and s.get('recMode') == 'fixed'][0]
    chk('固定步数存成 800', step2.get('fixedSteps') == 800, str(step2.get('fixedSteps')))
    open_edit(pg, step2['id'])
    chk('编辑时固定步数那种高亮', 'on' in pg.eval_on_selector(
        '#move-sport-body .sp-rec-opt[data-rm="fixed"]', 'e => e.className'))
    chk('手动那种置灰', 'locked' in pg.eval_on_selector(
        '#move-sport-body .sp-rec-opt[data-rm="manual"]', 'e => e.className'))
    pg.fill('#sp-fixed', '900')
    submit_sport(pg)
    step2 = [s for s in sports() if s.get('key') == 'steps' and s.get('recMode') == 'fixed'][0]
    chk('固定步数的数值可以改（900）', step2.get('fixedSteps') == 900, str(step2.get('fixedSteps')))

    # ============================================================
    print('\n===== 6. 需求4：打卡弹窗没有距离 / 达标后只补距离 =====')
    do_sport(pg, step1['id'])
    chk('打卡弹窗打开', pg.locator('#move-record-form').count() == 1)
    labels = pg.eval_on_selector_all('#move-record-body .field > span', 'e => e.map(x => x.textContent)')
    chk('打卡弹窗有「步数（步）」', any('步数' in x for x in labels), str(labels))
    chk('打卡弹窗有「记录方式」', any('记录方式' in x for x in labels), str(labels))
    chk('打卡弹窗没有「距离」', not any('距离' in x for x in labels), str(labels))
    chk('打卡弹窗没有距离输入框', pg.locator('#move-record-form input[name="distM"]').count() == 0)
    # v187：打卡时记录方式只读 —— 不能再从下拉切手动/固定
    chk('打卡弹窗没有记录方式下拉', pg.locator('#move-record-form select[name="recMode"]').count() == 0,
        str(pg.locator('#move-record-form select[name="recMode"]').count()))
    ro = pg.locator('#move-record-form .f-ro')
    chk('记录方式只读展示且与运动设置一致',
        ro.count() == 1 and '手动输入今日步数' in ro.inner_text(),
        ro.inner_text() if ro.count() else 'none')
    fill_rec(pg, {'steps': 600})
    chk('600/1000 还没达标', '还没达标' in card_of(pg, step1['id']).inner_text())
    chk('打卡不会改写记录的记录方式', all((r.get('recMode') or 'manual') == 'manual'
                                   for r in recs() if r.get('sportId') == step1['id']),
        str([r.get('recMode') for r in recs() if r.get('sportId') == step1['id']]))
    do_sport(pg, step1['id'])
    fill_rec(pg, {'steps': 600})
    chk('达标后弹补充运动数据', '补充运动数据' in pg.inner_text('#move-record-form h3'),
        pg.inner_text('#move-record-form h3') if pg.locator('#move-record-form h3').count() else 'no modal')
    labels2 = pg.eval_on_selector_all('#move-record-body .field > span', 'e => e.map(x => x.textContent)')
    chk('补充弹窗只有距离', len(labels2) == 1 and '距离' in labels2[0], str(labels2))
    chk('补充弹窗没有步数输入框', pg.locator('#move-record-form input[name="steps"]').count() == 0)
    fill_rec(pg, {'distM': 1500})
    srecs = [r for r in recs() if r.get('sportId') == step1['id']]
    chk('距离写进同一条记录（仍是 2 条）', len(srecs) == 2, 'n=%d' % len(srecs))
    chk('原步数没被冲掉', sum(int(r.get('steps') or 0) for r in srecs) == 1200,
        str([r.get('steps') for r in srecs]))
    chk('距离存下来了', any(int(r.get('distM') or 0) == 1500 for r in srecs),
        str([r.get('distM') for r in srecs]))

    # ============================================================
    print('\n===== 6b. v187：步数的运动后数据「一天一份」+ 达标标记 + 补过即锁 =====')
    open_log(pg, step1['id'])
    expand_folds(pg)
    t = pg.inner_text('#modal-root')
    fold_n = pg.eval_on_selector_all('#modal-root .sp-fold-n', 'e => e.map(x => x.textContent.trim())')
    chk('数据框标题写「今天」', len(fold_n) == 2 and fold_n[1] == '今天', str(fold_n))
    chk('数据框只有一条（不是 4 条空的）', pg.locator('#modal-root .sp-dataitem').count() == 1,
        str(pg.locator('#modal-root .sp-dataitem').count()))
    chk('不再出现「未记录运动后数据」', '未记录运动后数据' not in t, t[:200])
    chk('数据框显示距离 1500 米', '1500 米' in t, t[:200])
    chk('日志里达标那次带「达标」标记', pg.locator('#modal-root .oktag').count() == 1,
        str(pg.locator('#modal-root .oktag').count()))
    # 距离补过就锁定：修改那条记录时距离只读
    pg.locator('#modal-root [data-rec-edit]').last.click()
    pg.wait_for_timeout(700)
    chk('修改达标记录时距离没有输入框', pg.locator('#move-record-form input[name="distM"]').count() == 0,
        str(pg.locator('#move-record-form input[name="distM"]').count()))
    ro2 = pg.eval_on_selector_all('#move-record-form .f-ro', 'e => e.map(x => x.textContent.trim())')
    chk('编辑时距离不可改（没有输入框、也不在表单里）',
        not any('1500' in x for x in ro2)
        and pg.locator('#move-record-form input[name="distM"]').count() == 0, str(ro2))
    chk('但明确告诉用户已记录距离', '1500' in pg.inner_text('#move-record-form'), 
        pg.inner_text('#move-record-form')[:200])
    pg.click('#move-record-form button[type="submit"]')
    pg.wait_for_timeout(1500)
    chk('保存后距离没被冲掉', any(int(r.get('distM') or 0) == 1500
                            for r in recs() if r.get('sportId') == step1['id']),
        str([r.get('distM') for r in recs() if r.get('sportId') == step1['id']]))
    # 删除带距离的记录要有提示
    open_log(pg, step1['id'])
    expand_folds(pg)
    pg.locator('#modal-root [data-rec-del]').last.click()
    pg.wait_for_timeout(900)
    chk('删除带距离的记录有提示', '距离也一起消失' in dlg['msg'], dlg['msg'][:140])
    pg.wait_for_timeout(600)
    close_modal(pg)

    # ============================================================
    print('\n===== 7. 需求2：两个折叠区（运动日志 / 运动后数据，默认收起）=====')
    open_new(pg, 'run')
    pg.fill('#sp-tval', '3')
    pg.fill('#sp-freqn', '2')
    submit_sport(pg)
    run = sport_by_key('run')
    chk('跑步设成每天 2 次', run.get('freqN') == 2, str(run.get('freqN')))
    do_sport(pg, run['id'])
    fill_rec(pg, {'dur': 50, 'dist': 3, 'pace': '5:20', 'cadence': 180, 'heart': 126,
                  'kcal': 765, 'stride': 120})
    do_sport(pg, run['id'])
    fill_rec(pg, {'dur': 36, 'dist': 5.2, 'pace': '6:25'})
    open_log(pg, run['id'])
    chk('默认两个折叠区都收起', fold_open(pg) == [False, False], str(fold_open(pg)))
    titles = pg.eval_on_selector_all('#modal-root .sp-fold-t', 'e => e.map(x => x.textContent)')
    chk('分「运动日志」「运动后数据」两块', titles == ['运动日志', '运动后数据'], str(titles))
    expand_folds(pg)
    t = pg.inner_text('#modal-root')
    chk('日志里出现「第 1 次」「第 2 次」', '第 1 次' in t and '第 2 次' in t, t[:160])
    chk('日志区只放日志（不塞运动后数据）',
        not any('运动时长（分钟）' in x for x in
                pg.eval_on_selector_all('#modal-root .sp-logitem', 'e => e.map(x => x.innerText)')),
        pg.eval_on_selector_all('#modal-root .sp-logitem', 'e => e.map(x => x.innerText)'))
    chk('数据区字段行带字段名与单位', '· 运动时长（分钟）' in t and '· 距离（公里）' in t, t[:200])
    chk('值原样显示（50 分钟 / 3 公里）', '50 分钟' in t and '3 公里' in t, t[:200])
    chk('配速整串显示（5:20）', '5:20' in t, t[:200])
    lines = pg.eval_on_selector_all('#modal-root .sp-dataitem .sp-recfield', 'e => e.map(x => x.innerText)')
    chk('数据区字段行总数 = 7 + 3', len(lines) == 10, 'lines=%d' % len(lines))
    clip = pg.eval_on_selector_all('#modal-root .sp-recfield .v', 'e => e.map(x => x.scrollWidth <= x.clientWidth + 1)')
    chk('字段值没有被截断', all(clip), str(clip))
    chk('数据区每条带序号与时间', pg.locator('#modal-root .sp-dataitem-h').count() == 2,
        str(pg.locator('#modal-root .sp-dataitem-h').count()))
    close_modal(pg)

    print('\n===== 8. 需求2：只有一条记录时不编号 =====')
    do_sport(pg, rope['id'])
    fill_rec(pg, {'count': 300, 'heart': 130, 'kcal': 200})
    t = rec_text(pg, rope['id'])
    chk('单条记录不编号', '第 1 次' not in t, t[:120])
    chk('数据区列出字段行', '· 总次数（次）' in t and '· 心率（bpm）' in t, t[:200])
    chk('没勾的字段不显示', '· 运动时长（分钟）' not in t, t[:200])
    close_modal(pg)

    # ============================================================
    print('\n===== 9. 需求1：跳过 → 红色「补充运动后详细数据」=====')
    open_new(pg, 'walk')
    pg.fill('#sp-tval', '3')
    submit_sport(pg)
    walk = sport_by_key('walk')
    do_sport(pg, walk['id'])
    pg.click('#move-record-form [data-act="move-skip"]')
    pg.wait_for_timeout(400)
    chk('跳过要二次确认', pg.locator('[data-act="move-skip-ok"]').count() == 1)
    pg.click('[data-act="move-skip-ok"]')
    pg.wait_for_timeout(900)
    notice = card_of(pg, walk['id']).locator('[data-act="move-rec"]')
    chk('卡片出现补数据入口', notice.count() == 1, str(notice.count()))
    chk('按钮文案是「补充运动后详细数据」', notice.inner_text().strip() == '补充运动后详细数据',
        notice.inner_text().strip() if notice.count() else '')
    bg = notice.evaluate('e => getComputedStyle(e).backgroundColor')
    chk('底色是 #DC2626', bg.replace(' ', '') == 'rgb(220,38,38)', bg)
    chk('卡片说明指向新名字', '补充运动后详细数据' in card_of(pg, walk['id']).inner_text(),
        card_of(pg, walk['id']).inner_text())
    chk('卡片说明不再写「点『补数据』补上」', '点「补数据」补上' not in card_of(pg, walk['id']).inner_text())

    print('\n===== 10. 需求1：补填完按钮消失 =====')
    notice.click()
    pg.wait_for_timeout(600)
    pg.click('#modal-root [data-act="move-fill"]')
    pg.wait_for_timeout(600)
    fill_rec(pg, {'dur': 30, 'dist': 3})
    chk('补填后按钮消失', card_of(pg, walk['id']).locator('[data-act="move-rec"]').count() == 0)

    # ============================================================
    print('\n===== 11. D 一致性：取消勾选后旧值不丢 =====')
    open_edit(pg, run['id'])
    set_field(pg, 'stride', False)
    submit_sport(pg)
    run = sport_by_key('run')
    chk('存档 fields 不再含 stride', 'stride' not in (run.get('fields') or []), str(run.get('fields')))
    keep = [r for r in recs() if r.get('sportId') == run['id'] and int(r.get('stride') or 0) == 120]
    chk('旧记录里的步幅值仍在', len(keep) == 1, str([r.get('stride') for r in recs()]))
    t = rec_text(pg, run['id'])
    chk('只是不再显示步幅', '步幅' not in t, t[:200])
    close_modal(pg)

    print('\n===== 12. G 边界：一个字段都没勾的运动 =====')
    open_new(pg, 'ball')
    pg.fill('#sp-tval', '60')
    for k in ['dur', 'hrZone', 'heartAvg', 'kcal']:
        set_field(pg, k, False)
    submit_sport(pg)
    ball = sport_by_key('ball')
    chk('球类 fields 是空数组', ball.get('fields') == [], str(ball.get('fields')))
    do_sport(pg, ball['id'])
    hint = pg.inner_text('#move-record-form')
    chk('弹窗说明没勾数据', '没有勾选要记录的数据' in hint, hint[:120])
    chk('只有「跳过不记录」可选', pg.locator('#move-record-form [data-act="move-skip"]').count() == 1
        and pg.locator('#move-record-form input[type="number"]').count() == 0,
        str(pg.locator('#move-record-form input[type="number"]').count()))
    pg.click('#move-record-form [data-act="move-skip"]')
    pg.wait_for_timeout(400)
    pg.click('[data-act="move-skip-ok"]')
    pg.wait_for_timeout(800)

    print('\n===== 13. C 记录改 / 删（列表 DOM 重构后仍可点）=====')
    t = rec_text(pg, run['id'])
    chk('日志里两条记录', pg.locator('#modal-root .sp-logitem').count() == 2,
        str(pg.locator('#modal-root .sp-logitem').count()))
    pg.locator('#modal-root [data-rec-edit]').first.click()
    pg.wait_for_timeout(700)
    chk('点「修改」打开这条记录', pg.locator('#move-record-form').count() == 1)
    pg.locator('#move-record-form [name="dur"]').fill('45')
    pg.click('#move-record-form button[type="submit"]')
    pg.wait_for_timeout(1000)
    t = rec_text(pg, run['id'])
    chk('改完值同步到数据区（45 分钟）', '45 分钟' in t, t[:160])
    chk('改完日志仍是两条', pg.locator('#modal-root .sp-logitem').count() == 2,
        str(pg.locator('#modal-root .sp-logitem').count()))
    n_before = len(recs())
    pg.locator('#modal-root [data-rec-del]').first.click()
    # save() 有 600ms 防抖，等 1500ms 再读存档，否则可能读到删除前的快照
    pg.wait_for_timeout(1500)
    chk('删除要二次确认', dlg['n'] >= 1, 'dialogs=%d' % dlg['n'])
    chk('删完少了一条', len(recs()) == n_before - 1, '%d -> %d' % (n_before, len(recs())))
    # 删完会重开这个列表（v185 修的行为），直接数当前弹窗里的日志条
    pg.wait_for_timeout(700)
    chk('删完日志只剩一条', pg.locator('#modal-root .sp-logitem').count() == 1,
        str(pg.locator('#modal-root .sp-logitem').count()))
    close_modal(pg)

    print('\n===== 14. E 跨天：昨天的记录不进今日任务记录 =====')
    pg.click('[data-act="move-add-rec"]')
    pg.wait_for_timeout(500)
    pg.select_option('#move-record-form select[name="key"]', 'ball')
    pg.wait_for_timeout(200)
    pg.fill('#move-record-form [name="d"]', YDAY)
    pg.locator('#move-record-form [name="dur"]').fill('40')
    pg.click('#move-record-form button[type="submit"]')
    pg.wait_for_timeout(900)
    old = [r for r in recs() if r.get('d') == YDAY]
    chk('昨天那条已进存档', len(old) == 1, str([r.get('d') for r in recs()]))
    t = rec_text(pg, ball['id'])
    groups = pg.locator('#modal-root .sp-logitem').count()
    chk('今日任务记录只算今天（1 条）', groups == 1, 'groups=%d' % groups)
    chk('没有出现昨天的日期', '10-23' not in t, t[:160])
    close_modal(pg)

    print('\n===== 15. v187：未达标提示 + 补数据列表带「第 N 次」=====')
    open_new(pg, 'steps')
    pg.fill('#sp-tval', '10000')
    submit_sport(pg)
    st3 = [s for s in sports() if s.get('key') == 'steps'][-1]
    do_sport(pg, st3['id'])
    fill_rec(pg, {'steps': 1000})
    open_log(pg, st3['id'])
    expand_folds(pg)
    t = pg.inner_text('#modal-root')
    chk('未达标：数据框只给一句说明',
        pg.locator('#modal-root .sp-dataitem').count() == 0 and '还没达标' in t, t[:200])
    chk('未达标时不写「未记录运动后数据」', '未记录运动后数据' not in t, t[:200])
    close_modal(pg)

    open_new(pg, 'ride')
    pg.fill('#sp-tval', '10')
    pg.fill('#sp-freqn', '2')
    submit_sport(pg)
    ride = sport_by_key('ride')
    for _ in range(2):
        do_sport(pg, ride['id'])
        pg.click('#move-record-form [data-act="move-skip"]')
        pg.wait_for_timeout(350)
        pg.click('[data-act="move-skip-ok"]')
        pg.wait_for_timeout(800)
    card_of(pg, ride['id']).locator('[data-act="move-rec"]').click()
    pg.wait_for_timeout(700)
    rows = pg.eval_on_selector_all('#modal-root .sp-reclist .rt', 'e => e.map(x => x.textContent)')
    chk('补数据列表带「第 1 次」「第 2 次」',
        any('第 1 次' in x for x in rows) and any('第 2 次' in x for x in rows), str(rows))
    close_modal(pg)

    print('\n===== 16. 无 JS 报错 =====')
    chk('没有 JS 错误', not errs, '; '.join(errs[:3]))

    br.close()


print('\n' + '=' * 60)
print('v185 运动优化：%d 通过 / %d 失败' % (PASS, FAIL))
if FAILS:
    for n, d in FAILS:
        print('  FAIL: %s  << %s' % (n, d))
else:
    print('全部通过')
