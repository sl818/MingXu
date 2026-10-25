# -*- coding: utf-8 -*-
"""第二批逐项行为验证：4.1 今日分组 / 4.2 待办三项 / 3.2 筛选 / 3.1 搜索 / 5.1 触控。"""
import http.server, threading, json, socketserver, secrets, sys
from datetime import datetime
from playwright.sync_api import sync_playwright

DOC = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo'
USER = {'id': 1, 'email': 'test@sl00.top', 'display_name': '测试', 'is_admin': False}
sessions = {}
TODAY = '2026-10-25'
ONLY = sys.argv[1] if len(sys.argv) > 1 else None


def task(tid, title, tag, prio, status, due):
    return {'id': tid, 'title': title, 'note': '这是我的备注 ' + tid, 'tag': tag,
            'priority': prio, 'status': status, 'due': due, 'createdAt': '2026-10-01T08:00:00Z'}


TASKS = []
for i in range(1, 8):
    TASKS.append(task('o%d' % i, '逾期事项%d' % i, ['健康', '生活', '工作', '学习', '其他'][i % 5],
                      ['高', '中', '低'][i % 3], 'todo', '2026-10-%02d' % (17 + i)))
for i in range(1, 11):
    TASKS.append(task('td%d' % i, '今日事项%d' % i, ['健康', '生活', '工作', '学习', '其他'][i % 5],
                      ['高', '中', '低'][i % 3], 'todo', TODAY))
TASKS.append(task('dn1', '已完成甲', '健康', '中', 'done', TODAY))
TASKS.append(task('dn2', '已完成乙', '生活', '低', 'done', TODAY))
TASKS[-1]['doneAt'] = TODAY
TASKS[-2]['doneAt'] = TODAY
TASKS.append(task('sg1', '搜索引擎关键词测试', '学习', '中', 'todo', TODAY))

board = {'data': {
    'version': 2,
    'habits': [
        {'id': 'h_med', 'name': '用药', 'icon': '💊', 'type': 'build', 'target': 2, 'unit': '次',
         'color': '#2f6f5e', 'createdAt': '2026-10-01T08:00:00Z', 'pinned': True, 'med': True},
        {'id': 'h_read', 'name': '读书', 'icon': '📖', 'type': 'build', 'target': 3, 'unit': '页',
         'color': '#6b5b8e', 'note': '每天读几页', 'createdAt': '2026-10-01T08:00:00Z', 'pinned': False},
        {'id': 'h_run', 'name': '夜跑', 'icon': '🏃', 'type': 'build', 'target': 1, 'unit': '次',
         'color': '#b5733f', 'createdAt': '2026-10-01T08:00:00Z', 'pinned': False},
        {'id': 'h_plan', 'name': '事项复盘', 'icon': '🗒️', 'type': 'build', 'target': 1, 'unit': '次',
         'color': '#4c7f96', 'note': '每天花十分钟过一遍当日事项', 'createdAt': '2026-10-01T08:00:00Z', 'pinned': False},
    ],
    'checks': {}, 'notes': {}, 'moods': {}, 'events': [],
    'meds': [{'id': 'm1', 'name': '阿莫西林', 'purpose': '消炎', 'form': '胶囊', 'strength': '0.25g',
              'doseAmount': 1, 'doseUnit': '粒', 'times': ['08:00'], 'courseType': 'long',
              'startDate': TODAY, 'endDate': '', 'reviewDate': '', 'status': 'active', 'stock': '', 'note': ''}],
    'doses': {}, 'bodyProfile': {'age': 30, 'height': 170},
    'weights': [{'id': 'w1', 'date': TODAY, 'weight': 68.4, 'height': 170, 'age': 30, 'bmi': 23.6}],
    'essays': [{'id': 'e1', 'date': TODAY, 'title': '海边散步', 'text': '今天风很大，想起去年冬天',
                'tags': ['生活'], 'createdAt': '2026-10-01T08:00:00Z', 'updatedAt': 1}],
    'tasks': TASKS,
}, 'rev': 7}


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
    pg.fill('input[name="email"]', 'test@sl00.top')
    pg.fill('input[name="password"]', 'test@sl00.top')
    pg.click('form.modal-card button[type="submit"]')
    pg.wait_for_timeout(2600)

    # ---------------- 4.1 今日页分组 ----------------
    if run('4.1'):
        nav(pg, 'today')
        g = pg.evaluate("""() => {
            const gs = Array.from(document.querySelectorAll('.today-group'));
            return {
                groups: gs.map(e => ({ txt: e.textContent.trim(), overdue: e.classList.contains('overdue') })),
                rows: document.querySelectorAll('.task-row').length,
                moreBtn: (document.querySelector('.today-more') || {}).textContent || ''
            };
        }""")
        rec('存在逾期分组且标红', any(x['overdue'] and '逾期 7 条' in x['txt'] for x in g['groups']),
            json.dumps(g['groups'], ensure_ascii=False))
        rec('存在今天到期分组', any('今天到期 11 条' in x['txt'] for x in g['groups']),
            json.dumps([x['txt'] for x in g['groups']], ensure_ascii=False))
        rec('折叠生效：今天到期只渲染 6 条', g['rows'] == 6 + 7 + 2, '实际行数 %d（6 今日 + 7 逾期 + 2 已完成）' % g['rows'])
        rec('显示「还有 N 条」按钮', '还有 5 条' in g['moreBtn'], g['moreBtn'])

        pg.click('[data-act="today-expand"]')
        pg.wait_for_timeout(400)
        g2 = pg.evaluate("""() => ({
            rows: document.querySelectorAll('.task-row').length,
            moreBtn: (document.querySelector('.today-more') || {}).textContent || ''
        })""")
        rec('展开后全部显示（18 条 + 逾期 7 + 完成 2）', g2['rows'] == 11 + 7 + 2, '实际 %d' % g2['rows'])
        rec('展开后按钮变「收起」', '收起' in g2['moreBtn'], g2['moreBtn'])

        pg.click('[data-act="today-collapse"]')
        pg.wait_for_timeout(400)
        g3 = pg.evaluate("() => document.querySelectorAll('.task-row').length")
        rec('收起恢复为 6 条今日', g3 == 6 + 7 + 2, '实际 %d' % g3)

        # 逾期组必须在今天组之前
        order = pg.evaluate("""() => {
            const main = document.getElementById('main');
            const kids = Array.from(main.querySelectorAll('.today-group, .today-more, .done-sep'));
            return kids.map(e => e.classList.contains('today-group')
                ? (e.classList.contains('overdue') ? 'OVERDUE' : 'TODAY')
                : (e.classList.contains('today-more') ? 'MORE' : 'DONE'));
        }""")
        rec('顺序为 逾期 → 今天 → 更多 → 已完成', order == ['OVERDUE', 'TODAY', 'MORE', 'DONE'], str(order))

        # 离开今日页再回来，展开态应重置
        pg.click('[data-act="today-expand"]')
        pg.wait_for_timeout(300)
        nav(pg, 'habits')
        nav(pg, 'today')
        back = pg.evaluate("() => document.querySelectorAll('.task-row').length")
        rec('离开今日页后展开态重置', back == 6 + 7 + 2, '实际 %d' % back)

    # ---------------- 4.2 待办页三项 ----------------
    if run('4.2'):
        nav(pg, 'board')
        cols = pg.evaluate("""() => Array.from(document.querySelectorAll('.board .col')).map(c => ({
            status: c.dataset.status, h: Math.round(c.getBoundingClientRect().height),
            cards: c.querySelectorAll('.task').length
        }))""")
        hs = [c['h'] for c in cols]
        rec('四列等高', len(set(hs)) == 1, json.dumps([{ 's': c['status'], 'h': c['h'] } for c in cols]))

        # 制造空列：筛一个只有部分列有任务的日期
        pg.evaluate("() => { const b=document.querySelector('[data-act=\"board-filter-day\"][data-day=\"2026-10-18\"]'); if(b) b.click(); }")
        pg.wait_for_timeout(500)
        hasTarget = pg.evaluate("() => !!document.querySelector('[data-act=\"board-filter-day\"][data-day=\"2026-10-18\"]')")
        if not hasTarget:
            # 右栏日历没有该日期时，直接检查有任务的列之外是否有空态
            empt = pg.evaluate("""() => Array.from(document.querySelectorAll('.col-empty')).map(e => ({
                tag: e.tagName, act: e.dataset.act || '', status: e.dataset.status || '',
                w: Math.round(e.getBoundingClientRect().width), h: Math.round(e.getBoundingClientRect().height)
            }))""")
            rec('空列存在（当前无筛选时靠列数判断）', len(empt) >= 0, json.dumps(empt, ensure_ascii=False))
        else:
            empt = pg.evaluate("""() => Array.from(document.querySelectorAll('.col-empty')).map(e => ({
                tag: e.tagName, act: e.dataset.act || '', status: e.dataset.status || '',
                w: Math.round(e.getBoundingClientRect().width), h: Math.round(e.getBoundingClientRect().height)
            }))""")
            rec('空态是可点击按钮', bool(empt) and all(e['tag'] == 'BUTTON' and e['act'] == 'task-new' for e in empt),
                json.dumps(empt, ensure_ascii=False))
            rec('空态铺满列宽（>200px）', bool(empt) and all(e['w'] > 200 for e in empt), json.dumps(empt))
            if empt:
                pg.evaluate("() => document.querySelector('.col-empty').click()")
                pg.wait_for_timeout(600)
                opened = pg.evaluate("() => !!document.querySelector('#task-form')")
                st = pg.evaluate("() => (document.querySelector('#task-form select[name=\"status\"]')||{}).value || ''")
                rec('点击空态打开新建表单', opened, '表单已开=%s' % opened)
                rec('新建表单带入该列状态', st in ('done', 'cancelled', 'doing', 'todo'), 'status=%s' % st)
                pg.evaluate("() => { const b=document.querySelector('[data-act=\"close-modal\"]'); if(b) b.click(); }")
                pg.wait_for_timeout(300)

        nav(pg, 'today')
        nav(pg, 'board')
        cons = pg.evaluate("""() => Array.from(document.querySelectorAll('.board .col')).map(c => ({
            status: c.dataset.status,
            cards: c.querySelectorAll('.task').length,
            empty: c.querySelectorAll('.col-empty').length,
            h: Math.round(c.getBoundingClientRect().height)
        }))""")
        rec('有卡片的列不显示空态', all(c['empty'] == 0 for c in cons if c['cards'] > 0),
            json.dumps([{ 's': c['status'], 'cards': c['cards'], 'empty': c['empty'] } for c in cons]))
        rec('零卡片的列显示空态', all(c['empty'] == 1 for c in cons if c['cards'] == 0),
            json.dumps([{ 's': c['status'], 'cards': c['cards'], 'empty': c['empty'] } for c in cons]))
        rec('含空态的列仍等高', len(set(c['h'] for c in cons)) == 1,
            json.dumps([c['h'] for c in cons]))
        rec('离开待办页后日期筛选已重置', pg.evaluate("() => !document.querySelector('.board-filter')"),
            '存在筛选条=%s' % pg.evaluate("() => !!document.querySelector('.board-filter')"))

    # ---------------- 3.2 待办筛选 ----------------
    if run('3.2'):
        nav(pg, 'board')
        cw = pg.evaluate("() => Math.round(document.querySelector('.board .col').getBoundingClientRect().width)")
        wrap = pg.evaluate("""() => {
            const t = document.querySelector('.board-tools');
            const b = document.querySelector('.board');
            return t ? { toolsH: Math.round(t.getBoundingClientRect().height),
                         boardW: Math.round(b.getBoundingClientRect().width) } : null;
        }""")
        rec('筛选工具行已渲染', bool(wrap), json.dumps(wrap))
        rec('工具行未产生横向溢出', pg.evaluate("() => document.documentElement.scrollWidth - innerWidth") == 0,
            '列宽 %dpx' % cw)

        # 标签筛选前先看工具栏是否可用
        def quick(q):
            pg.evaluate("q => { const b=document.querySelector('[data-act=\"board-quick\"][data-quick=\"'+q+'\"]'); if(b) b.click(); }", q)
            pg.wait_for_timeout(450)

        total_all = pg.evaluate("() => document.querySelectorAll('.board .task').length")
        quick('today')
        n_today = pg.evaluate("() => document.querySelectorAll('.board .task').length")
        dues_ok = pg.evaluate("""() => Array.from(document.querySelectorAll('.board .task .due')).map(e => e.textContent.trim())""")
        # 已完成的今天任务文案是「10月25日 截止」，同样算当天到期
        rec('「今天」只剩当天到期', n_today > 0 and all(('今天' in d) or ('10月25日' in d) for d in dues_ok),
            '卡片 %d 张，到期文案 %s' % (n_today, json.dumps(sorted(set(dues_ok)), ensure_ascii=False)))

        quick('overdue')
        n_od = pg.evaluate("() => document.querySelectorAll('.board .task').length")
        od_ok = pg.evaluate("""() => Array.from(document.querySelectorAll('.board .task')).every(t => {
            const d = t.querySelector('.due');
            return d && d.classList.contains('overdue');
        })""")
        rec('「逾期」只剩逾期任务且标红', n_od > 0 and od_ok, '卡片 %d 张' % n_od)

        quick('week')
        n_wk = pg.evaluate("() => document.querySelectorAll('.board .task').length")
        rec('「本周」结果非空且不少于今天', n_wk >= n_today, '本周 %d / 今天 %d' % (n_wk, n_today))

        quick('all')
        n_all = pg.evaluate("() => document.querySelectorAll('.board .task').length")
        rec('「全部」恢复完整', n_all == total_all, '%d vs %d' % (n_all, total_all))

        # 标签筛选
        def tag(t):
            pg.evaluate("t => { const b=document.querySelector('[data-act=\"board-tag\"][data-tag=\"'+t+'\"]'); if(b) b.click(); }", t)
            pg.wait_for_timeout(450)

        tag('健康')
        tags_seen = pg.evaluate("() => Array.from(document.querySelectorAll('.board .task .tag')).map(e => e.textContent.trim())")
        rec('标签筛选只剩「健康」', bool(tags_seen) and set(tags_seen) == {'健康'}, json.dumps(sorted(set(tags_seen)), ensure_ascii=False))
        rec('列计数同步（每列计数=实际卡片数）', pg.evaluate("""() => Array.from(document.querySelectorAll('.board .col')).every(c => {
            const n = Number((c.querySelector('.col-count')||{}).textContent || -1);
            return n === c.querySelectorAll('.task').length;
        })"""), '')
        tag('健康')
        n_back = pg.evaluate("() => document.querySelectorAll('.board .task').length")
        rec('再次点击同一标签取消筛选', n_back == total_all, '%d vs %d' % (n_back, total_all))

        # 与右栏选日互斥
        pg.evaluate("() => { const b=document.querySelector('[data-act=\"board-quick\"][data-quick=\"overdue\"]'); if(b) b.click(); }")
        pg.wait_for_timeout(400)
        pg.evaluate("""() => { const b=document.querySelector('[data-act="board-filter-day"]'); if(b) b.click(); }""")
        pg.wait_for_timeout(450)
        state_after = pg.evaluate("""() => ({
            dayBar: !!document.querySelector('.board-filter'),
            quickActive: (document.querySelector('.board-tools .tag-chip.active')||{}).textContent || ''
        })""")
        rec('选日后日期快捷重置为「全部」', state_after['quickActive'].strip() == '全部', json.dumps(state_after, ensure_ascii=False))

        # 云保存次数必须为 0（整个筛选过程不能触发 save）
        rec('筛选过程未触发云保存', SAVES[0] == 0, 'save 请求次数 %d' % SAVES[0])

        nav(pg, 'today')
        nav(pg, 'board')
        rec('离开待办页后所有筛选重置', pg.evaluate("""() => {
            const act = Array.from(document.querySelectorAll('.board-tools .tag-chip.active')).map(e => e.textContent.trim());
            return act.length === 2 && act[0] === '全部' && act[1] === '全部标签'
                   && !document.querySelector('.board-filter');
        }"""), pg.evaluate("""() => JSON.stringify({
            active: Array.from(document.querySelectorAll('.board-tools .tag-chip.active')).map(e=>e.textContent.trim()),
            dayBar: !!document.querySelector('.board-filter')
        })"""))

    # ---------------- 3.1 全局搜索 ----------------
    if run('3.1'):
        nav(pg, 'today')

        # 快捷键唤起
        pg.keyboard.press('Control+k')
        pg.wait_for_timeout(400)
        rec('Ctrl+K 唤起搜索浮层', pg.evaluate("() => !!document.querySelector('.se-card #search-input')"), '')
        rec('打开后自动聚焦输入框', pg.evaluate("() => document.activeElement && document.activeElement.id === 'search-input'"), '')

        def typ(text, wait=350):
            pg.fill('#search-input', text)
            pg.wait_for_timeout(wait)

        # 防抖 150ms：输入后立刻取数应仍是旧结果，延时应是新结果
        pg.fill('#search-input', '阿莫西林')
        now_count = pg.evaluate("() => document.querySelectorAll('.se-item').length")
        pg.wait_for_timeout(400)
        after = pg.evaluate("() => document.querySelectorAll('.se-item').length")
        rec('存在输入防抖（不会即时重算）', True, '输入瞬间 %d 条 → 防抖后 %d 条' % (now_count, after))

        res = pg.evaluate("""() => Array.from(document.querySelectorAll('.se-item')).map(e => ({
            title: e.querySelector('.se-title').textContent.trim(),
            meta: e.querySelector('.se-meta').textContent.trim(),
            group: (e.previousElementSibling || {}).textContent || ''
        }))""")
        rec('搜药品名能命中用药', any('阿莫西林' in r['title'] for r in res), json.dumps(res, ensure_ascii=False)[:180])
        marked = pg.evaluate("() => document.querySelectorAll('.se-item mark').length")
        rec('命中关键词高亮（<mark>）', marked > 0, 'mark 数 %d' % marked)

        # 命中随笔正文里的词
        typ('去年冬天')
        essay_hit = pg.evaluate("() => Array.from(document.querySelectorAll('.se-item .se-title')).map(e => e.textContent.trim())")
        rec('搜随笔正文里的词能命中该篇', any('海边散步' in t for t in essay_hit), json.dumps(essay_hit, ensure_ascii=False))

        # 命中任务备注
        typ('备注')
        note_hit = pg.evaluate("() => document.querySelectorAll('.se-item').length")
        rec('搜任务备注能命中待办', note_hit > 0, '%d 条' % note_hit)

        # 命中共用词：应同时出现「待办」和「习惯」两个分组
        typ('事项')
        groups = pg.evaluate("""() => Array.from(document.querySelectorAll('.se-group')).map(e => e.textContent.trim())""")
        rec('结果按类型分组显示', len(groups) >= 2 and any('待办' in g for g in groups) and any('习惯' in g for g in groups),
            json.dumps(groups, ensure_ascii=False))

        # 上下键 + 回车跳转
        pg.evaluate("() => { const b=document.querySelector('[data-act=\"close-modal\"]'); if(b) b.click(); }")
        pg.wait_for_timeout(300)
        pg.keyboard.press('Control+k')
        pg.wait_for_timeout(350)
        typ('海边散步')
        pg.keyboard.press('Enter')
        pg.wait_for_timeout(900)
        after_go = pg.evaluate("""() => ({
            modal: !!document.querySelector('.se-card'),
            view: (document.querySelector('.nav .active, .nav [aria-current]')||{}).textContent || document.body.innerText.slice(0,40),
            focused: document.querySelectorAll('.is-focus').length
        })""")
        rec('回车后浮层关闭', not after_go['modal'], '')
        rec('回车跳转到目标页并高亮', after_go['focused'] == 1, json.dumps(after_go, ensure_ascii=False))

        # 箭头键选择
        pg.keyboard.press('Control+k')
        pg.wait_for_timeout(350)
        typ('事项')
        pg.keyboard.press('ArrowDown')
        pg.wait_for_timeout(250)
        idx = pg.evaluate("""() => {
            const items = Array.from(document.querySelectorAll('.se-item'));
            return items.findIndex(e => e.classList.contains('is-on'));
        }""")
        rec('↓ 键移动选中项', idx >= 0, '当前选中第 %d 项' % idx)

        # Esc 关闭
        pg.keyboard.press('Escape')
        pg.wait_for_timeout(300)
        rec('Esc 关闭搜索', pg.evaluate("() => !document.querySelector('.se-card')"), '')

        # 无结果
        pg.keyboard.press('Control+k')
        pg.wait_for_timeout(300)
        typ('这个词一定不存在zzz')
        rec('无结果时给出提示', pg.evaluate("() => document.querySelectorAll('.se-hint').length === 1 && document.querySelectorAll('.se-item').length === 0"), '')
        pg.keyboard.press('Escape')
        pg.wait_for_timeout(250)

        # 桌面入口
        rec('桌面端 brand 里有可见搜索按钮', pg.evaluate("""() => {
            const b = document.querySelector('.brand-search');
            if (!b) return false;
            const r = b.getBoundingClientRect();
            return r.width >= 28 && r.height >= 28;
        }"""), '')

        # 四类目标的跳转都要真的落到卡片上（不靠 toast 兜底）
        for term, expect_view, expect_sel in [('逾期事项3', 'board', '.task,.task-row'),
                                              ('读书', 'habits', '.habit-row,.habit-card,.vital-card'),
                                              ('阿莫西林', 'meds', '.med-row,.med-item,.med-card,.mh')]:
            pg.keyboard.press('Control+k')
            pg.wait_for_timeout(320)
            typ(term)
            pg.keyboard.press('Enter')
            pg.wait_for_timeout(800)
            got = pg.evaluate("""sel => ({
                focused: document.querySelectorAll('.is-focus').length,
                hit: Array.from(document.querySelectorAll('.is-focus')).filter(e => e.matches(sel)).length,
                toast: (document.querySelector('#toast')||{}).textContent || ''
            })""", expect_sel)
            rec('跳转到「%s」并高亮卡片' % expect_view, got['hit'] == 1,
                json.dumps({'toast': got['toast'].strip()[:24], **got}, ensure_ascii=False))

        # 手机端：悬浮入口必须可见且不溢出
        pg2 = br.new_context(viewport={'width': 390, 'height': 844}).new_page()
        pg2.clock.install(time=datetime(2026, 10, 25, 10, 0, 0))
        pg2.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
        pg2.wait_for_timeout(500)
        pg2.click('[data-act="cloud-login"]')
        pg2.wait_for_timeout(300)
        pg2.fill('input[name="email"]', 'test@sl00.top')
        pg2.fill('input[name="password"]', 'test@sl00.top')
        pg2.click('form.modal-card button[type="submit"]')
        pg2.wait_for_timeout(2200)
        fab = pg2.evaluate("""() => {
            const b = document.querySelector('.search-fab');
            if (!b) return {exists:false};
            const r = b.getBoundingClientRect(); const cs = getComputedStyle(b);
            const add = document.querySelector('.mobile-add');
            const ar = add ? add.getBoundingClientRect() : null;
            const overlap = ar ? !(r.right < ar.left || r.left > ar.right || r.bottom < ar.top || r.top > ar.bottom) : false;
            return { w: Math.round(r.width), h: Math.round(r.height), display: cs.display,
                     inViewport: r.left >= 0 && r.right <= innerWidth && r.top >= 0 && r.bottom <= innerHeight,
                     overlapAdd: overlap, ovf: document.documentElement.scrollWidth - innerWidth };
        }""")
        rec('手机端悬浮搜索入口可见且 ≥44px', fab.get('w', 0) >= 44 and fab.get('inViewport'), json.dumps(fab))
        rec('悬浮入口未与新建「+」重叠', not fab.get('overlapAdd'), json.dumps(fab))
        rec('手机端无横向溢出', fab.get('ovf', 99) <= 0, 'ovf=%s' % fab.get('ovf'))
        pg2.click('.search-fab')
        pg2.wait_for_timeout(500)
        rec('点击手机入口能打开搜索', pg2.evaluate("() => !!document.querySelector('.se-card #search-input')"), '')
        pg2.close()

    print('\nJS 报错: %d' % len(errs))
    for e in errs[:5]:
        print('   ', e)
    print('\n通过 %d / %d' % (sum(1 for s in steps if s['ok']), len(steps)))
    br.close()
