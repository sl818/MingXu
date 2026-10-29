# -*- coding: utf-8 -*-
"""第四批逐项行为验证：6.2 导出提示 / 5.3 减少动画 / 5.4 首屏骨架 / 1.2 状态版本号 / 5.2 键盘可达性。"""
import http.server, threading, json, socketserver, secrets, sys, time
from datetime import datetime
from playwright.sync_api import sync_playwright

DOC = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo'
USER = {'id': 1, 'email': 'test@sl00.top', 'display_name': '测试', 'is_admin': False}
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
            elif a == 'ics_status':
                # 订阅地址默认没有；专门的 verify-ics-ui.py 会覆盖这个路由做交互测试
                self._j({'ok': True, 'url': None})
            elif a == 'load':
                if LOAD_DELAY[0]:
                    time.sleep(LOAD_DELAY[0] / 1000.0)
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
LOAD_DELAY = [0]
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
    pg.fill('input[name="email"]', 'test@sl00.top')
    pg.fill('input[name="password"]', 'test@sl00.top')
    pg.click('form.modal-card button[type="submit"]')
    pg.wait_for_timeout(2600)

    # ---------------- 6.2 导出隐私提示 ----------------
    if run('6.2'):
        nav(pg, 'settings')
        note = pg.evaluate("""() => {
            const n = document.querySelector('.privacy-note');
            return n ? { txt: n.textContent.replace(/\\s+/g, ' ').trim(), has: true } : { has: false };
        }""")
        rec('设置页有导出隐私提示', note['has'], '')
        rec('提示写明不要上传公开网盘/链接',
            all(k in note.get('txt', '') for k in ['明文', '网盘']), note.get('txt', '')[:60])

        with pg.expect_download() as dl:
            pg.click('[data-act="export-json"]')
        pg.wait_for_timeout(400)
        toast_txt = pg.evaluate("() => (document.querySelector('#toast') || {}).textContent || ''")
        rec('导出后 toast 带隐私提醒', '隐私' in toast_txt, toast_txt.strip()[:40])
        rec('导出的确实是 JSON 文件', dl.value.suggested_filename.endswith('.json'), dl.value.suggested_filename)

    # ---------------- 5.3 减少动画 ----------------
    if run('5.3'):
        full = ctx.storage_state()
        # 只带 cookie、不带 localStorage：模拟「首次在这台设备打开」，
        # 否则客户端会先用本地缓存直接画出内容，骨架根本没机会出现
        state = {'cookies': full['cookies'], 'origins': []}

        def motion_probe(reduce):
            c2 = br.new_context(viewport={'width': 1200, 'height': 800}, storage_state=state,
                                reduced_motion='reduce' if reduce else 'no-preference')
            p2 = c2.new_page()
            p2.clock.install(time=datetime(2026, 10, 25, 10, 0, 0))
            LOAD_DELAY[0] = 1200
            p2.goto('http://127.0.0.1:%d/index.html' % port, wait_until='domcontentloaded')
            p2.wait_for_timeout(300)
            r = p2.evaluate("""() => {
                const el = document.querySelector('.bs-block');
                if (!el) return null;
                const cs = getComputedStyle(el);
                return { dur: cs.animationDuration, name: cs.animationName,
                         media: matchMedia('(prefers-reduced-motion: reduce)').matches };
            }""")
            LOAD_DELAY[0] = 0
            c2.close()
            return r

        normal = motion_probe(False)
        reduced = motion_probe(True)
        rec('默认允许动画时骨架有动画', bool(normal) and normal['name'] != 'none' and normal['dur'] != '0.01ms',
            json.dumps(normal, ensure_ascii=False))
        # 浏览器会把 0.01ms 归一化成 1e-05s / 0.00001s，两种写法都认
        tiny = bool(reduced) and reduced['dur'] in ('1e-05s', '0.00001s', '0.01ms')
        rec('减少动画时动画被压到 0.01ms', tiny, json.dumps(reduced, ensure_ascii=False))
        rec('媒体查询确实被模拟生效', bool(reduced) and reduced['media'] is True, '')

    # ---------------- 5.4 首屏骨架 ----------------
    if run('5.4'):
        LOAD_DELAY[0] = 1500
        cookies_only = {'cookies': ctx.storage_state()['cookies'], 'origins': []}
        c3 = br.new_context(viewport={'width': 1200, 'height': 800}, storage_state=cookies_only)
        p3 = c3.new_page()
        p3.clock.install(time=datetime(2026, 10, 25, 10, 0, 0))
        p3.goto('http://127.0.0.1:%d/index.html' % port, wait_until='domcontentloaded')
        p3.wait_for_timeout(350)
        early = p3.evaluate("""() => {
            const s = document.querySelector('.boot-skel');
            return { has: !!s, blocks: document.querySelectorAll('.boot-skel .bs-block').length,
                     h: s ? Math.round(s.getBoundingClientRect().height) : 0,
                     mainEmpty: !document.querySelector('.page-head, .hero') };
        }""")
        rec('数据到达前显示骨架屏', early['has'] and early['blocks'] >= 4 and early['h'] > 100,
            json.dumps(early, ensure_ascii=False))
        rec('骨架期间还没有真实内容（说明确实是首屏占位）', early['mainEmpty'], '')
        p3.wait_for_timeout(3200)
        late = p3.evaluate("""() => ({
            skel: !!document.querySelector('.boot-skel'),
            content: !!document.querySelector('.page-head, .hero')
        })""")
        rec('数据到达后骨架被真实内容替换', (not late['skel']) and late['content'], json.dumps(late, ensure_ascii=False))
        LOAD_DELAY[0] = 0
        c3.close()

    # ---------------- 1.2 状态版本号 ----------------
    if run('1.2'):
        # 老数据（无 schemaVersion）应被迁移并打上版本号，同时补齐呼吸法习惯
        saved = json.loads(json.dumps(board['data']))
        board['data'].pop('schemaVersion', None)
        board['data']['habits'] = [h for h in board['data']['habits'] if h['id'] != 'h_breathe']
        board['rev'] += 1
        p4 = ctx.new_page()
        p4.clock.install(time=datetime(2026, 10, 25, 10, 0, 0))
        p4.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
        p4.wait_for_timeout(2600)
        nav(p4, 'habits')
        v1 = p4.evaluate("""() => ({
            breathe: Array.from(document.querySelectorAll('.habit-row-info b')).some(e => e.textContent.indexOf('478') >= 0)
        })""")
        rec('无版本号的老数据会执行 v1→v3 迁移（补回呼吸法习惯）', v1['breathe'], json.dumps(v1, ensure_ascii=False))
        # 触发一次保存，检查落库的数据带上了版本号
        # 真改一次数据触发保存：用「今日状态」的心情按钮，它一定在今日页且必定写库
        nav(p4, 'today')
        p4.evaluate("""() => { const b = document.querySelector('[data-act="set-mood"]'); if (b) b.click(); }""")
        p4.wait_for_timeout(2200)
        # 不写死具体版本号：以后再加迁移步骤不该让这条变成假红灯
        rec('保存后数据里带上当前 schemaVersion', (board['data'].get('schemaVersion') or 0) >= 3,
            'schemaVersion=%s' % board['data'].get('schemaVersion'))
        p4.close()

        # 已经是 v3 的数据不应该再被"修复"：删掉呼吸法后不应被自动加回
        board['data']['schemaVersion'] = 3
        board['data']['habits'] = [h for h in board['data']['habits'] if h['id'] != 'h_breathe']
        board['rev'] += 1
        p5 = ctx.new_page()
        p5.clock.install(time=datetime(2026, 10, 25, 10, 0, 0))
        p5.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
        p5.wait_for_timeout(2600)
        nav(p5, 'habits')
        v3 = p5.evaluate("""() => Array.from(document.querySelectorAll('.habit-row-info b')).map(e => e.textContent.trim())""")
        rec('v3 数据不再重复执行迁移（呼吸法不被自动加回）',
            not any('478' in n for n in v3), json.dumps(v3, ensure_ascii=False))
        p5.close()
        board['data'] = saved
        board['rev'] += 1

    # ---------------- 5.2 键盘可达性 ----------------
    if run('5.2'):
        # 用桌面端一定存在的「编辑档案」按钮作为触发点（quick-add 是移动端专属）
        nav(pg, 'weight')
        pg.focus('[data-act="profile-edit"]')
        pg.wait_for_timeout(200)
        pg.keyboard.press('Enter')
        pg.wait_for_timeout(600)
        opened = pg.evaluate("() => !!document.querySelector('#modal-root .modal-card')")
        rec('回车能打开弹窗（按钮可被键盘触发）', opened, '')

        inside = []
        for _ in range(12):
            pg.keyboard.press('Tab')
            pg.wait_for_timeout(60)
            inside.append(pg.evaluate("() => !!document.querySelector('#modal-root').contains(document.activeElement)"))
        rec('Tab 循环 12 次焦点始终留在弹窗内', all(inside), '跑出次数 %d' % inside.count(False))

        # Shift+Tab 反向也应留在内部
        back_in = []
        for _ in range(6):
            pg.keyboard.press('Shift+Tab')
            pg.wait_for_timeout(60)
            back_in.append(pg.evaluate("() => !!document.querySelector('#modal-root').contains(document.activeElement)"))
        rec('Shift+Tab 反向也困在弹窗内', all(back_in), '跑出次数 %d' % back_in.count(False))

        # 焦点环：输入框用 box-shadow 环，按钮用 outline，有其一即算可见
        ring = pg.evaluate("""() => {
            const el = document.activeElement;
            if (!el) return null;
            const cs = getComputedStyle(el);
            const hasOutline = cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) > 0;
            const hasShadow = cs.boxShadow && cs.boxShadow !== 'none';
            return { tag: el.tagName, outline: cs.outlineStyle, w: cs.outlineWidth,
                     shadow: !!hasShadow, visible: el.matches(':focus-visible'),
                     ok: hasOutline || hasShadow };
        }""")
        rec('弹窗内焦点有可见指示（outline 或焦点阴影）', bool(ring) and ring['visible'] and ring['ok'],
            json.dumps(ring, ensure_ascii=False))

        pg.keyboard.press('Escape')
        pg.wait_for_timeout(500)
        closed = pg.evaluate("""() => ({
            modal: !!document.querySelector('#modal-root .modal-card'),
            backTo: (document.activeElement || {}).getAttribute ? (document.activeElement.getAttribute('data-act') || '') : '',
            inMain: document.getElementById('main').contains(document.activeElement)
        })""")
        rec('Esc 关闭弹窗', not closed['modal'], '')
        rec('关闭后焦点归还到触发按钮', closed['backTo'] == 'profile-edit', json.dumps(closed, ensure_ascii=False))

        # 搜索浮层同样受焦点陷阱保护
        pg.keyboard.press('Control+k')
        pg.wait_for_timeout(400)
        loop = []
        for _ in range(8):
            pg.keyboard.press('Tab')
            pg.wait_for_timeout(50)
            loop.append(pg.evaluate("() => !!document.querySelector('#modal-root').contains(document.activeElement)"))
        rec('搜索浮层内 Tab 也不外逃', all(loop), '跑出次数 %d' % loop.count(False))
        pg.keyboard.press('Escape')
        pg.wait_for_timeout(300)

    print('\nJS 报错: %d' % len(errs))
    for e in errs[:5]:
        print('   ', e)
    print('\n通过 %d / %d' % (sum(1 for s in steps if s['ok']), len(steps)))
    br.close()
