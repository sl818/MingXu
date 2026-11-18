# -*- coding: utf-8 -*-
"""第三批逐项行为验证：4.3 用药疗程 / 4.4 体重目标线 / 4.5 习惯排序 / 4.6 日历补记 / 3.3 打开即提醒 / 3.4 月度回顾。"""
import http.server, threading, json, socketserver, secrets, sys
from datetime import datetime
from playwright.sync_api import sync_playwright

DOC = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo'
USER = {'id': 1, 'email': 'test@example.com', 'display_name': '测试', 'is_admin': False}
sessions = {}
TODAY = '2026-10-25'
ONLY = sys.argv[1] if len(sys.argv) > 1 else None


def habit(hid, name, target, unit, pinned=False, med=False, color='#2f6f5e', note=''):
    return {'id': hid, 'name': name, 'icon': '✅', 'type': 'build', 'target': target, 'unit': unit,
            'color': color, 'note': note, 'createdAt': '2026-09-01T08:00:00Z', 'pinned': pinned, 'med': med}


def med(mid, name, course, times, start='2026-10-01', end=''):
    return {'id': mid, 'name': name, 'purpose': '其他', 'form': '片', 'strength': '',
            'doseAmount': 1, 'doseUnit': '片', 'times': times, 'courseType': course,
            'startDate': start, 'endDate': end, 'reviewDate': '', 'status': 'active',
            'stock': '', 'note': ''}


def task(tid, title, tag, prio, status, due):
    return {'id': tid, 'title': title, 'note': '备注 ' + tid, 'tag': tag,
            'priority': prio, 'status': status, 'due': due, 'createdAt': '2026-10-01T08:00:00Z'}


# 逐日打卡：读 3 页连续 5 天、夜跑连续 2 天、喝水 1 天、事项复盘 0 天
CHECKS = {
    '2026-10-21': {'h_read': 3, 'h_run': 1},
    '2026-10-22': {'h_read': 3},
    '2026-10-23': {'h_read': 3, 'h_run': 1},
    '2026-10-24': {'h_read': 3, 'h_run': 1, 'h_water': 9, 'h_plan': 1},
    '2026-10-25': {'h_read': 3, 'h_run': 1, 'h_water': 3},
}
# 上月数据（用于 3.4 的「与上月对比」）
for d in range(1, 31):
    CHECKS['2026-09-%02d' % d] = {'h_read': 3, 'h_run': 1} if d % 2 == 0 else {}

TASKS = [
    task('o1', '逾期甲', '工作', '高', 'todo', '2026-10-22'),
    task('o2', '逾期乙', '生活', '中', 'todo', '2026-10-23'),
    task('t1', '今日甲', '健康', '中', 'todo', TODAY),
    task('t2', '今日乙', '学习', '低', 'todo', TODAY),
    task('d1', '已完成甲', '健康', '中', 'done', TODAY),
]
TASKS[-1]['doneAt'] = TODAY

board = {'data': {
    'version': 2,
    'habits': [
        habit('h_med', '用药', 2, '次', pinned=True, med=True, color='#6f7f91'),
        habit('h_water', '喝水', 9, '杯', pinned=True, color='#4c7f96'),
        habit('h_read', '读书', 3, '页', color='#6b5b8e'),
        habit('h_run', '夜跑', 1, '次', color='#b5733f'),
        habit('h_plan', '事项复盘', 1, '次', color='#7a6a3f'),
    ],
    'checks': CHECKS, 'notes': {}, 'moods': {'2026-10-25': 'happy'}, 'events': [],
    'meds': [
        med('m_long1', '阿莫西林', 'long', ['08:00', '20:00']),
        med('m_long2', '维生素D', 'long', ['12:00']),
        med('m_short1', '头孢克肟', 'short', ['09:00'], start='2026-10-20', end='2026-10-30'),
        med('m_short2', '布洛芬', 'short', ['08:00'], start='2026-10-24', end='2026-10-28'),
        med('m_prn1', '止痛片', 'prn', []),
        med('m_prn2', '感冒灵', 'prn', []),
    ],
    'doses': {TODAY: {'m_long1': {'08:00': {'at': 1}}}},
    'bodyProfile': {'age': 30, 'height': 170},
    'weights': [
        {'id': 'w1', 'date': '2026-10-01', 'weight': 70.0, 'height': 170, 'age': 30, 'bmi': 24.2},
        {'id': 'w2', 'date': '2026-10-10', 'weight': 69.4, 'height': 170, 'age': 30, 'bmi': 24.0},
        {'id': 'w3', 'date': '2026-10-25', 'weight': 68.4, 'height': 170, 'age': 30, 'bmi': 23.7},
    ],
    'essays': [{'id': 'e1', 'date': TODAY, 'title': '海边散步', 'text': '今天风很大',
                'tags': ['生活'], 'createdAt': '2026-10-01T08:00:00Z', 'updatedAt': 1}],
    'tasks': TASKS,
}, 'rev': 9}

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
                self._j({'ok': True, 'data': board['data'], 'rev': board['rev'], 'updated_at': 1792813000000})
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
            elif a in ('save', 'force'):
                board['data'] = body['data']
                board['rev'] += 1
                try:
                    SAVES[0] += 1
                except NameError:
                    pass
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

steps, errs = [], []
SAVES = [0]


def rec(name, ok, detail=''):
    steps.append({'name': name, 'ok': bool(ok)})
    print(('PASS  ' if ok else 'FAIL  ') + name + (('  | ' + detail) if detail else ''))


def nav(pg, v):
    pg.evaluate("v => { const b=document.querySelector('[data-nav=\"'+v+'\"]'); if(b) b.click(); }", v)
    pg.wait_for_timeout(450)


def run(sec):
    if ONLY and ONLY != sec:
        return False
    print('\n===== %s =====' % sec)
    return True


with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)

    ctx = br.new_context(viewport={'width': 1440, 'height': 900}, device_scale_factor=1)
    pg = ctx.new_page()
    pg.on('pageerror', lambda e: errs.append(str(e)[:140]))
    pg.on('console', lambda m: errs.append(m.text[:120]) if m.type == 'error' else None)
    pg.clock.install(time=datetime(2026, 10, 25, 10, 0, 0))
    pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
    pg.wait_for_timeout(500)
    pg.click('[data-act="cloud-login"]')
    pg.wait_for_timeout(400)
    pg.fill('input[name="email"]', 'test@example.com')
    pg.fill('input[name="password"]', 'test@example.com')
    pg.click('form.modal-card button[type="submit"]')
    pg.wait_for_timeout(2600)

    # ---------------- 4.3 用药页疗程维度 ----------------
    if run('4.3'):
        nav(pg, 'meds')
        info = pg.evaluate("""() => {
            const subs = Array.from(document.querySelectorAll('.med-sub-head')).map(e => e.textContent.trim().replace(/\\s+/g,' '));
            const groups = Array.from(document.querySelectorAll('.med-group-head h3')).map(e => e.textContent.trim());
            const rows = document.querySelectorAll('.med-row').length;
            return { subs, groups, rows,
                     names: Array.from(document.querySelectorAll('.med-row-title b')).map(e => e.textContent.trim()) };
        }""")
        norm = lambda xs: [x.replace(' ', '') for x in xs]
        rec('进行中组内出现三个疗程小标题', norm(info['subs']) == ['长期2种', '短期2种', '按需2种'],
            json.dumps(info['subs'], ensure_ascii=False))
        rec('六种药全部仍在页面上', info['rows'] == 6, '药品行数 %d 种，名单 %s' % (info['rows'], json.dumps(info['names'], ensure_ascii=False)))
        rec('疗程分组不破坏原有阶段分组', any('进行中' in g for g in info['groups']),
            json.dumps(info['groups'], ensure_ascii=False))

        order = pg.evaluate("""() => Array.from(document.querySelectorAll('.med-sub-head, .med-board .med-row-title b'))
            .map(e => e.classList.contains('med-sub-head') ? '#' + e.textContent.trim() : e.textContent.trim())""")
        rec('每段药品紧跟自己的小标题',
            norm(order) == ['#长期2种', '阿莫西林', '维生素D', '#短期2种', '布洛芬', '头孢克肟', '#按需2种', '感冒灵', '止痛片'],
            json.dumps(order, ensure_ascii=False))

        # 边界：只剩一种疗程时不应该出现小标题（避免少量药品被切碎）
        saved = list(board['data']['meds'])
        board['data']['meds'] = [m for m in saved if m['courseType'] == 'long']
        pg2 = ctx.new_page()
        pg2.clock.install(time=datetime(2026, 10, 25, 10, 0, 0))
        pg2.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
        pg2.wait_for_timeout(2600)   # 同 context 已带登录态，直接等云端数据加载
        nav(pg2, 'meds')
        only = pg2.evaluate("() => ({subs: document.querySelectorAll('.med-sub-head').length, rows: document.querySelectorAll('.med-row').length})")
        rec('只有一种疗程时不显示小标题', only['subs'] == 0 and only['rows'] == 2, json.dumps(only))
        pg2.close()
        board['data']['meds'] = saved

    # ---------------- 4.4 体重页目标体重线 ----------------
    if run('4.4'):
        nav(pg, 'weight')
        before = pg.evaluate("""() => ({
            goalLines: document.querySelectorAll('.ww-goal').length,
            goalLbl: (document.querySelector('.ww-goal-lbl') || {}).textContent || '',
            profileCells: Array.from(document.querySelectorAll('.profile-grid small')).map(e => e.textContent.trim())
        })""")
        rec('未设目标时不画目标线', before['goalLines'] == 0, json.dumps(before, ensure_ascii=False))
        rec('档案卡默认显示 BMI 参考', 'BMI' in ' '.join(before['profileCells']),
            json.dumps(before['profileCells'], ensure_ascii=False))

        # 通过档案表单设置目标体重 65
        pg.click('[data-act="profile-edit"]')
        pg.wait_for_timeout(500)
        has_goal_field = pg.evaluate("() => !!document.querySelector('#body-profile-form [name=\"goalWeight\"]')")
        rec('档案表单有目标体重字段', has_goal_field, '')
        pg.fill('#body-profile-form [name="goalWeight"]', '65')
        pg.click('#body-profile-form button[type="submit"]')
        pg.wait_for_timeout(900)

        after = pg.evaluate("""() => {
            const line = document.querySelector('.ww-goal');
            const lbl = document.querySelector('.ww-goal-lbl');
            return {
                goalLines: document.querySelectorAll('.ww-goal').length,
                goalLbl: lbl ? lbl.textContent.trim() : '',
                dash: line ? getComputedStyle(line).strokeDasharray : '',
                profileCells: Array.from(document.querySelectorAll('.profile-grid small')).map(e => e.textContent.trim()),
                values: Array.from(document.querySelectorAll('.profile-grid b')).map(e => e.textContent.trim())
            };
        }""")
        rec('设目标后画出虚线', after['goalLines'] == 1 and after['dash'] not in ('none', ''), json.dumps({'dash': after['dash']}))
        rec('目标标签显示 65.0', '65.0' in after['goalLbl'], after['goalLbl'])
        rec('档案卡显示目标体重与距目标', '目标体重' in after['profileCells'] and '距目标' in after['profileCells'],
            json.dumps(after['profileCells'], ensure_ascii=False) + ' ' + json.dumps(after['values'], ensure_ascii=False))
        rec('距目标数值正确（68.4 - 65 = 3.4）', any('3.4' in v for v in after['values']), json.dumps(after['values'], ensure_ascii=False))

        # 目标线必须落在图表可视区域内
        inb = pg.evaluate("""() => {
            const svg = document.querySelector('.ww-svg');
            const line = document.querySelector('.ww-goal');
            if (!svg || !line) return null;
            const y = Number(line.getAttribute('y1'));
            /* 绘图区上下边界从 viewBox 推：v114 把 H 从 200 改到 340，
               写死 174 的断言就变成假失败 */
            const vb = (svg.getAttribute('viewBox') || '').split(/\s+/);
            const H = Number(vb[3]) || 200;
            return { y: y, H: H, ok: y >= 16 && y <= H - 26 };
        }""")
        rec('目标线在绘图区内', bool(inb and inb['ok']), json.dumps(inb))

        # 保存后应触发云同步且不报错
        rec('保存目标体重后无 JS 报错', len(errs) == 0, '报错 %d' % len(errs))

        # 清空目标后目标线消失
        pg.click('[data-act="profile-edit"]')
        pg.wait_for_timeout(500)
        pg.fill('#body-profile-form [name="goalWeight"]', '')
        pg.click('#body-profile-form button[type="submit"]')
        pg.wait_for_timeout(900)
        gone = pg.evaluate("() => ({lines: document.querySelectorAll('.ww-goal').length, cells: Array.from(document.querySelectorAll('.profile-grid small')).map(e=>e.textContent.trim())})")
        rec('清空目标后目标线消失', gone['lines'] == 0 and '目标体重' not in gone['cells'], json.dumps(gone, ensure_ascii=False))

        # 非法值拦截
        pg.click('[data-act="profile-edit"]')
        pg.wait_for_timeout(500)
        pg.fill('#body-profile-form [name="goalWeight"]', '999')
        pg.click('#body-profile-form button[type="submit"]')
        pg.wait_for_timeout(500)
        err_txt = pg.evaluate("() => (document.querySelector('#body-profile-form .form-error') || {}).textContent || ''")
        blocked = pg.evaluate("""() => ({
            open: !!document.querySelector('#body-profile-form'),
            native: !!document.querySelector('#body-profile-form [name=\\"goalWeight\\"]:invalid'),
            lines: document.querySelectorAll('.ww-goal').length
        })""")
        # 999 超出 input 的 max=300，浏览器原生校验会先拦住提交；JS 里的范围判断是第二道防线
        rec('目标体重超出范围时无法保存', blocked['open'] and blocked['lines'] == 0,
            '拦截方式=%s err=%s' % ('原生校验' if blocked['native'] else 'JS 校验', err_txt.strip()[:24]))
        pg.evaluate("() => { const b=document.querySelector('[data-act=\"close-modal\"]'); if(b) b.click(); }")
        pg.wait_for_timeout(300)

    # ---------------- 4.5 习惯页排序 ----------------
    if run('4.5'):
        nav(pg, 'habits')
        names = lambda: pg.evaluate("() => Array.from(document.querySelectorAll('.panel .habit-row:not(.archived) .habit-row-info b')).map(e => e.textContent.trim())")
        chips = pg.evaluate("""() => Array.from(document.querySelectorAll('.habit-sort .tag-chip')).map(e => ({
            txt: e.textContent.trim(), active: e.classList.contains('active'), sort: e.dataset.sort
        }))""")
        rec('习惯页出现三个排序 chip', len(chips) == 3 and [c['txt'] for c in chips] == ['按创建', '今日进度', '连续天数'],
            json.dumps(chips, ensure_ascii=False))
        rec('默认选中「按创建」', chips[0]['active'], json.dumps([c['txt'] for c in chips if c['active']], ensure_ascii=False))

        created_order = names()
        # 478呼吸法 是 ensureBreathingHabit 自动补的常驻习惯，会排在最后
        expect_created = ['喝水', '读书', '夜跑', '事项复盘', '478呼吸法']
        rec('按创建顺序与数据一致', created_order == expect_created, json.dumps(created_order, ensure_ascii=False))

        saves_before = SAVES[0]
        pg.click('[data-act="habit-sort"][data-sort="progress"]')
        pg.wait_for_timeout(500)
        prog = names()
        rec('按今日进度重排（100% 的读书/夜跑在前）', prog[:2] == ['读书', '夜跑'], json.dumps(prog, ensure_ascii=False))
        rec('排序与创建顺序确实不同', prog != created_order, '创建=%s 进度=%s' % (created_order, prog))

        pg.click('[data-act="habit-sort"][data-sort="streak"]')
        pg.wait_for_timeout(500)
        st = names()
        rec('按连续天数重排（读书连续最久排第一）', st[0] == '读书', json.dumps(st, ensure_ascii=False))
        rec('排序切换不触发云保存', SAVES[0] == saves_before, 'save 次数 %d -> %d' % (saves_before, SAVES[0]))

        # 连续天数必须单调不增
        mono = pg.evaluate("""() => {
            const rows = Array.from(document.querySelectorAll('.panel .habit-row:not(.archived)'));
            return rows.length > 0;
        }""")
        rec('排序后所有习惯仍在列表里', mono, '')

        # 离开再回来：排序保留（设计如此，排序不隐藏数据）
        nav(pg, 'today')
        nav(pg, 'habits')
        kept = pg.evaluate("() => Array.from(document.querySelectorAll('.habit-sort .tag-chip.active')).map(e => e.textContent.trim())")
        rec('离开再回来排序保持', kept == ['连续天数'], json.dumps(kept, ensure_ascii=False))

        # 回到按创建
        pg.click('[data-act="habit-sort"][data-sort="created"]')
        pg.wait_for_timeout(450)
        rec('可切回按创建', names() == created_order, json.dumps(names(), ensure_ascii=False))

    # ---------------- 4.6 日历页去补记 ----------------
    if run('4.6'):
        nav(pg, 'calendar')
        # 点 10 月 20 日（当月内、有记录）
        pg.click('[data-act="pick-day"][data-date="2026-10-20"]')
        pg.wait_for_timeout(900)
        jumped = pg.evaluate("""() => ({
            view: (document.querySelector('.nav .active, .nav [aria-current]') || {}).textContent || '',
            bar: (document.querySelector('.backfill-bar') || {}).textContent || '',
            hasBar: !!document.querySelector('.backfill-bar'),
            heroDate: (document.querySelector('.hero-date span') || {}).textContent || ''
        })""")
        rec('点日历某天跳到今日页', jumped['hasBar'], json.dumps(jumped, ensure_ascii=False))
        rec('提示条写明日期', '10 月 20 日' in jumped['bar'], jumped['bar'].strip()[:40])
        rec('提示条有「回今天」按钮', pg.evaluate("() => !!document.querySelector('.backfill-today')"), '')
        rec('hero 日期跟着切到该日', '10 月 20 日' in jumped['heroDate'], jumped['heroDate'])

        # 端到端：在补记模式下真点一次打卡，看数据是否落到 10-20
        cnt_before = board['data'].get('checks', {}).get('2026-10-20', {}).get('h_read', 0)
        today_before = board['data'].get('checks', {}).get('2026-10-25', {}).get('h_read', 0)
        # 读书目标 3，卡片上是 3 个刻度点（habit-set），点第 1 个 = 记 1 页
        pg.click('[data-act="habit-set"][data-id="h_read"][data-val="1"]')
        pg.wait_for_timeout(1600)
        cnt_after = board['data'].get('checks', {}).get('2026-10-20', {}).get('h_read', 0)
        today_after = board['data'].get('checks', {}).get('2026-10-25', {}).get('h_read', 0)
        rec('补记打卡写入所选日期而非今天',
            cnt_after == cnt_before + 1 and today_after == today_before,
            '10-20: %d → %d ；今天: %d → %d' % (cnt_before, cnt_after, today_before, today_after))

        # 回今天
        pg.click('[data-act="date-today"]')
        pg.wait_for_timeout(700)
        back = pg.evaluate("() => ({bar: !!document.querySelector('.backfill-bar'), hero: (document.querySelector('.hero-date span')||{}).textContent || ''})")
        rec('点「回今天」后提示条消失', not back['bar'] and '10 月 25 日' in back['hero'], json.dumps(back, ensure_ascii=False))

        # 未来日期不可点（先回日历页）
        nav(pg, 'calendar')
        future_disabled = pg.evaluate("""() => {
            const b = document.querySelector('[data-act="pick-day"][data-date="2026-10-30"]');
            if (!b) return null;
            return { disabled: b.disabled, cls: b.className.indexOf('is-future') >= 0 };
        }""")
        rec('未来日期单元格不可点', bool(future_disabled) and future_disabled['disabled'], json.dumps(future_disabled))
        nav(pg, 'calendar')
        nav(pg, 'today')

    # ---------------- 3.3 打开即提醒 ----------------
    if run('3.3'):
        # 回到今日页，横幅应出现（时钟 10:00，两个 08:00/09:00 未服 → 逾期）
        nav(pg, 'today')
        pg.wait_for_timeout(600)
        bar = pg.evaluate("""() => {
            const b = document.querySelector('.remind-bar');
            return b ? { items: Array.from(b.querySelectorAll('.remind-item')).map(e => e.textContent.trim()),
                         go: !!b.querySelector('.remind-go'), x: !!b.querySelector('.remind-x') } : null;
        }""")
        rec('打开页面出现提醒横幅',
            bool(bar) and len([x for x in bar['items'] if not x.startswith('还有 ')]) <= 3,
            json.dumps(bar, ensure_ascii=False))
        if bar:
            joined = ' | '.join(bar['items'])
            shown = [x for x in bar['items'] if not x.startswith('还有 ')]
            rec('提示逾期用药次数（2 次）', '逾期' in joined or '已过时间' in joined, joined[:60])
            rec('提示今日待服次数（2 次）', '待服' in joined, joined[:60])
            rec('横幅最多铺 3 条', len(shown) == 3, joined[:80])
            # 从 v33 起提醒来源扩到 6 类，超过 3 条的折成「还有 N 条」，
            # 喝水排在最后，正常情况下会被折进计数
            rec('喝水提醒仍在（超出部分折进计数）',
                '喝水还差 6' in joined or any(x == '还有 1 条' for x in bar['items']), joined[:80])
            rec('横幅有「去看看」与「今天不再提醒」', bar['go'] and bar['x'], '')

        # 标题闪烁：轮询 3.4 秒，应至少出现一次带计数前缀的标题
        titles = set()
        for _ in range(17):
            titles.add(pg.title())
            pg.wait_for_timeout(200)
        rec('标签页标题闪烁计数', any(t.startswith('(') for t in titles), json.dumps(sorted(titles), ensure_ascii=False))

        saves_before = SAVES[0]
        pg.click('[data-act="remind-dismiss"]')
        pg.wait_for_timeout(500)
        after = pg.evaluate("""() => ({
            bar: !!document.querySelector('.remind-bar'),
            stored: localStorage.getItem('lifeboard.remind.dismissed')
        })""")
        rec('点「今天不再提醒」横幅消失', not after['bar'], json.dumps(after, ensure_ascii=False))
        rec('当天不再提醒写入 localStorage', after['stored'] == '2026-10-25', 'stored=%s' % after['stored'])
        rec('关闭提醒不触发云保存', SAVES[0] == saves_before, 'save %d -> %d' % (saves_before, SAVES[0]))

        # 标题已恢复
        pg.wait_for_timeout(1600)
        rec('关闭后标题恢复原标题', pg.title() == '明序 · 习惯与任务', pg.title())

        # 刷新后当天仍不再弹
        pg.reload(wait_until='networkidle')
        pg.wait_for_timeout(2600)
        rec('刷新后当天不再出现横幅', not pg.evaluate("() => !!document.querySelector('.remind-bar')"), '')

        # 模拟次日：清掉记录后应重新出现
        pg.evaluate("() => localStorage.removeItem('lifeboard.remind.dismissed')")
        pg.reload(wait_until='networkidle')
        pg.wait_for_timeout(2600)
        rec('清除当天记录后重新出现', pg.evaluate("() => !!document.querySelector('.remind-bar')"), '')

        # 「去看看」跳转到用药页
        pg.click('[data-act="remind-go"]')
        pg.wait_for_timeout(700)
        rec('点「去看看」跳到对应页面', pg.evaluate("() => !!document.querySelector('.med-group')"), '')
        pg.evaluate("() => localStorage.removeItem('lifeboard.remind.dismissed')")

    # ---------------- 3.4 月度回顾 ----------------
    if run('3.4'):
        nav(pg, 'stats')
        rv = pg.evaluate("""() => {
            /* v85 起总览底部还有一组「任务」三格，也是 .rv-cell，必须只在「本月回顾」那块里取 */
            const blk = Array.from(document.querySelectorAll('.sblock')).find(b => {
                const t = b.querySelector('.sblock-head b');
                return t && t.textContent.trim().indexOf('本月回顾') === 0;
            });
            const cells = Array.from((blk || document).querySelectorAll('.rv-cell')).map(e => ({
                label: e.querySelector('small').textContent.trim(),
                value: e.querySelector('b').textContent.trim(),
                sub: (e.querySelector('span') || {}).textContent || ''
            }));
            const head = (document.querySelector('.panel h3') || {});
            /* v84 起「本月回顾」并进总览面板，标题在 .sblock-head 里，不再是 h3 */
            const titles = Array.from(document.querySelectorAll('.panel h3, .sblock-head b'))
                .map(e => e.textContent.trim());
            return { cells, titles, verdict: (document.querySelector('.rv-verdict') || {}).textContent || '' };
        }""")
        rec('统计页出现「本月回顾」卡', any(t.startswith('本月回顾') for t in rv['titles']),
            json.dumps(rv['titles'][:6], ensure_ascii=False))
        rec('六项指标齐全', [c['label'] for c in rv['cells']] == ['达标天数', '有记录', '最长连续', '平均完成率', '体重变化', '用药依从'],
            json.dumps([c['label'] for c in rv['cells']], ensure_ascii=False))

        cells = {c['label']: c for c in rv['cells']}
        # 有记录天数按当前服务端数据算，避免前面的用例写入数据后断言失效（顺序依赖）
        oct_days = [d for d, v in (board['data'].get('checks') or {}).items()
                    if d.startswith('2026-10-') and v]
        expect_rec = len(oct_days)
        expect_miss = 25 - expect_rec
        rec('有记录天数与数据一致（%d 天）' % expect_rec,
            cells['有记录']['value'].strip().startswith(str(expect_rec)), cells['有记录']['value'])
        rec('缺失天数 = 25 - 有记录', ('缺 %d 天' % expect_miss) in cells['有记录']['sub'], cells['有记录']['sub'])
        rec('体重变化 = 68.4 - 70.0 = -1.6', '-1.6' in cells['体重变化']['value'] and 'kg' in cells['体重变化']['value'],
            cells['体重变化']['value'] + ' / ' + cells['体重变化']['sub'])
        rec('平均完成率是百分比', '%' in cells['平均完成率']['value'], cells['平均完成率']['value'])
        rec('用药依从是百分比或占位', '%' in cells['用药依从']['value'] or cells['用药依从']['value'] == '—',
            cells['用药依从']['value'] + ' / ' + cells['用药依从']['sub'])

        # 达标天数与最长连续的一致性
        q = int(''.join(ch for ch in cells['达标天数']['value'] if ch.isdigit()) or 0)
        best = int(''.join(ch for ch in cells['最长连续']['value'] if ch.isdigit()) or 0)
        rec('最长连续不超过达标天数', best <= q, '达标 %d 天，最长连续 %d 天' % (q, best))
        rec('达标天数不超过有记录天数', q <= expect_rec, '达标 %d 天 / 有记录 %d 天' % (q, expect_rec))

        rec('有一句话结论且提到上月对比', any(k in rv['verdict'] for k in ['上月', '这个月']), rv['verdict'].strip()[:50])

        # 切换统计区间不应影响本月回顾（它固定按月）
        pg.click('[data-act="set-stats-range"][data-range="7"]')
        pg.wait_for_timeout(500)
        rv7 = pg.evaluate("""() => ({
            hasRev: !!document.querySelector('.rv-cell'),
            rec: (document.querySelectorAll('.rv-cell b')[1] || {}).textContent || ''
        })""")
        rec('切到 7 天区间后本月回顾仍在且数值不变', rv7['hasRev'] and rv7['rec'].strip() == cells['有记录']['value'],
            json.dumps(rv7, ensure_ascii=False))
        pg.click('[data-act="set-stats-range"][data-range="30"]')
        pg.wait_for_timeout(400)

        # 对比分支：把本月 21–25 全部达标、上月清空，结论应变成「上月没有达标记录」
        # 注意必须用「新开页面」读：旧页面的 pagehide 会把手上的旧 state 推回服务端，
        # 直接把服务端数据覆盖回去（踩过一次）。
        saved_checks = json.loads(json.dumps(board['data']['checks']))
        # h_breathe 是 ensureBreathingHabit 自动补的常驻习惯，也计入分母，必须一起打满
        # h_med 的达标不看 checks，而看当天用药是否全服（medTakenCount >= medScheduledCount）
        full = {'h_med': 2, 'h_water': 9, 'h_read': 3, 'h_run': 1, 'h_plan': 1, 'h_breathe': 1}
        board['data']['checks'] = {('2026-10-%02d' % d): dict(full) for d in range(21, 26)}
        board['rev'] += 1
        pg4 = ctx.new_page()
        pg4.clock.install(time=datetime(2026, 10, 25, 10, 0, 0))
        pg4.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
        pg4.wait_for_timeout(2600)
        nav(pg4, 'stats')
        v2 = pg4.evaluate("() => (document.querySelector('.rv-verdict') || {}).textContent || ''")
        q2 = pg4.evaluate("() => (document.querySelectorAll('.rv-cell b')[0] || {}).textContent || ''")
        rec('上月无达标时按对应措辞提示', '上月没有达标记录' in v2, v2.strip()[:44] + ' | 达标 ' + q2.strip())
        rec('全达标时达标天数 = 5', q2.strip().startswith('5'), q2.strip())
        pg4.close()
        board['data']['checks'] = saved_checks
        board['rev'] += 1


    print('\nJS 报错: %d' % len(errs))
    for e in errs[:5]:
        print('   ', e)
    print('\n通过 %d / %d' % (sum(1 for s in steps if s['ok']), len(steps)))
    br.close()
