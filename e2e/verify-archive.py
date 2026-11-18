"""待办归档验证：拖拽归档 / 归档弹层 / 恢复 / 永久删除 / 全站过滤 / 历史仍计入统计"""
import http.server, threading, json, socketserver, secrets, sys
from datetime import datetime
from playwright.sync_api import sync_playwright

DOC = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo'
USER = {'id': 1, 'email': 'test@example.com', 'display_name': '测试', 'is_admin': False}
sessions = {}
PORT = 38563
D = '2026-10-24'

TASKS = [
    {'id': 't1', 'title': '要归档的第一条', 'note': '备注内容', 'tag': '生活', 'priority': '中', 'status': 'done',
     'due': '2026-10-22', 'createdAt': D + 'T08:00:00Z', 'doneAt': '2026-10-22'},
    {'id': 't2', 'title': '今天要做的事', 'note': '', 'tag': '健康', 'priority': '高', 'status': 'todo',
     'due': D, 'createdAt': D + 'T09:00:00Z'},
    {'id': 't3', 'title': '进行中的事', 'note': '', 'tag': '工作', 'priority': '中', 'status': 'doing',
     'due': '2026-10-23', 'createdAt': D + 'T07:00:00Z'},
    {'id': 't4', 'title': '已完成的一条', 'note': '', 'tag': '学习', 'priority': '低', 'status': 'done',
     'due': '2026-10-23', 'createdAt': D + 'T07:00:00Z', 'doneAt': D},
    {'id': 't5', 'title': '早先归档的', 'note': '', 'tag': '生活', 'priority': '中', 'status': 'done',
     'due': '2026-10-20', 'createdAt': '2026-10-20T07:00:00Z', 'doneAt': '2026-10-20',
     'archivedAt': '2026-10-21T10:00:00Z'},
    {'id': 't6', 'title': '没有截止日', 'note': '', 'tag': '其他', 'priority': '低', 'status': 'todo',
     'due': '', 'createdAt': D + 'T07:00:00Z'},
]

HABITS = [
    {'id': 'h_med', 'name': '用药', 'icon': '💊', 'type': 'build', 'target': 1, 'unit': '次',
     'color': '#2f6f5e', 'note': '', 'createdAt': '2026-10-23T00:00:00Z', 'pinned': True, 'med': True, 'archivedAt': ''},
]


def make_board():
    return {'data': {'version': 2, 'view': 'board', 'habits': HABITS, 'checks': {D: {}},
                     'notes': {}, 'moods': {}, 'events': [], 'meds': [], 'doses': {},
                     'bodyProfile': {'age': 30, 'height': 170}, 'weights': [], 'essays': [],
                     'tasks': [dict(t) for t in TASKS]}, 'rev': 5}


board = make_board()
save_count = {'n': 0}


class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw): super().__init__(*a, directory=DOC, **kw)
    def log_message(self, *a): pass
    def _j(self, o, s=200, eh=None):
        b = json.dumps(o, ensure_ascii=False).encode()
        self.send_response(s); self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(b)))
        for k, v in (eh or {}).items(): self.send_header(k, v)
        self.end_headers(); self.wfile.write(b)
    def _sid(self):
        for p in (self.headers.get('Cookie', '') or '').split(';'):
            p = p.strip()
            if p.startswith('sid='): return p[4:]
    def do_GET(self):
        if self.path.startswith('/api.php'):
            a = self.path.split('action=')[-1].split('&')[0]
            if a == 'status': self._j({'ok': True, 'installed': True, 'registration_open': False})
            elif a == 'me': self._j({'ok': True, 'user': sessions.get(self._sid()), 'csrf': 'x', 'registration_open': False})
            elif a == 'load': self._j({'ok': True, 'data': board['data'], 'rev': board['rev'], 'updated_at': 1792813000000})
            else: self._j({'ok': False, 'error': '?'}, 404)
        else: super().do_GET()
    def do_POST(self):
        if self.path.startswith('/api.php'):
            a = self.path.split('action=')[-1].split('&')[0]
            n = int(self.headers.get('Content-Length', 0)); body = json.loads(self.rfile.read(n) or b'{}')
            if a == 'login':
                sid = secrets.token_hex(8); sessions[sid] = USER
                self._j({'ok': True, 'user': USER, 'csrf': 'x'}, eh={'Set-Cookie': 'sid=' + sid + '; Path=/'})
            elif a == 'save':
                save_count['n'] += 1
                if int(body.get('base_rev', 0)) == board['rev']:
                    board['data'] = body['data']; board['rev'] += 1
                    self._j({'ok': True, 'rev': board['rev']})
                else:
                    self._j({'ok': False, 'code': 'conflict', 'remote': {'data': board['data'], 'rev': board['rev']}}, 409)
            elif a == 'force':
                save_count['n'] += 1
                board['data'] = body['data']; board['rev'] += 1
                self._j({'ok': True, 'rev': board['rev']})
            else: self._j({'ok': False, 'error': '?'}, 404)
        else:
            self.send_response(405); self.end_headers()


class TS(socketserver.ThreadingMixIn, http.server.HTTPServer): daemon_threads = True


srv = TS(('127.0.0.1', PORT), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()

results = []


def rec(name, ok, detail=''):
    results.append((name, ok, detail))
    print(('PASS  ' if ok else 'FAIL  ') + name + (('  | ' + str(detail)) if detail else ''))


def login(pg, layout='top', width=1700):
    pg.clock.install(time=datetime(2026, 10, 24, 10, 0, 0))
    pg.add_init_script("try{localStorage.setItem('lifeboard.layout','%s');localStorage.setItem('lifeboard.skin','paper');localStorage.setItem('lifeboard.theme.mode','light')}catch(e){}" % layout)
    pg.goto('http://127.0.0.1:%d/index.html' % PORT, wait_until='networkidle')
    pg.wait_for_timeout(700)
    pg.click('[data-act="cloud-login"]'); pg.wait_for_timeout(500)
    pg.fill('input[name="email"]', USER['email']); pg.fill('input[name="password"]', '12345678')
    pg.click('form.modal-card button[type="submit"]')
    pg.wait_for_timeout(2600)


def goto(pg, key):
    pg.evaluate("""(k) => {
      const b = document.querySelector('.nav-item[data-nav="' + k + '"]') ||
                document.querySelector('.mobile-tab[data-nav="' + k + '"]');
      if (b) b.click();
    }""", key)
    pg.wait_for_timeout(800)


STATE = """() => {
  const q = s => document.querySelector(s), qa = s => [...document.querySelectorAll(s)];
  const zone = q('.arch-zone');
  return {
    archBtn: (q('[data-act="archive-open"]') || {}).textContent || '',
    zoneShown: zone ? zone.getBoundingClientRect().height > 0 : false,
    zoneText: zone ? zone.textContent.replace(/\\s+/g, ' ').trim() : '',
    zoneInRail: !!zone && !!zone.closest('.board-rail'),
    zoneW: zone ? Math.round(zone.getBoundingClientRect().width) : 0,
    zoneH: zone ? Math.round(zone.getBoundingClientRect().height) : 0,
    shellW: (q('.board-shell') || {getBoundingClientRect: () => ({width: 0})}).getBoundingClientRect().width,
    hotText: (q('.arch-zone .az-hot') || {}).textContent || '',
    counts: qa('.col').map(c => c.querySelector('.col-count').textContent),
    titles: qa('.col-body .task').map(e => e.querySelector('h4').textContent.trim()),
    doneCol: qa('.col-body[data-status="done"] .task').length,
    railItems: qa('.bup-i').map(e => e.textContent.trim()),
    bodyDragging: document.body.classList.contains('is-dragging'),
    zoneOver: zone ? zone.classList.contains('is-over') : false,
    ovf: document.documentElement.scrollWidth - innerWidth
  };
}"""

MODAL = """() => {
  const q = s => document.querySelector(s), qa = s => [...document.querySelectorAll(s)];
  const m = q('.arch-modal');
  if (!m) return {open: false};
  return {
    open: true,
    head: (m.querySelector('h3') || {}).textContent.replace(/\\s+/g, ' ').trim(),
    rows: qa('.arch-row').length,
    titles: qa('.arch-row .ar-main b').map(e => e.textContent.trim()),
    metas: qa('.arch-row .ar-main small').map(e => e.textContent.trim()),
    hasRestore: qa('.arch-row [data-act="task-unarchive"]').length === qa('.arch-row').length,
    hasDel: qa('.arch-row [data-act="task-archive-del"]').length === qa('.arch-row').length,
    hasView: qa('.arch-row [data-act="task-arch-view"]').length === qa('.arch-row').length,
    /* 顺序必须是 查看 → 恢复 → 删除（查看在恢复左边） */
    btnOrder: qa('.arch-row .ar-btns').map(g => [...g.children].map(b => b.textContent.trim())),
    clearBtn: !!q('[data-act="archive-clear"]')
  };
}"""


def drag_to_zone(pg, task_id):
    return pg.evaluate("""(id) => {
      const card = document.querySelector('.task[data-id="' + id + '"]');
      const zone = document.querySelector('.arch-zone');
      if (!card || !zone) return {ok: false, why: !card ? 'no card' : 'no zone'};
      const dt = new DataTransfer();
      card.dispatchEvent(new DragEvent('dragstart', {bubbles: true, cancelable: true, dataTransfer: dt}));
      const dragging = document.body.classList.contains('is-dragging');
      zone.dispatchEvent(new DragEvent('dragover', {bubbles: true, cancelable: true, dataTransfer: dt}));
      const over = zone.classList.contains('is-over');
      zone.dispatchEvent(new DragEvent('drop', {bubbles: true, cancelable: true, dataTransfer: dt}));
      card.dispatchEvent(new DragEvent('dragend', {bubbles: true, cancelable: true, dataTransfer: dt}));
      return {ok: true, dragging: dragging, over: over};
    }""", task_id)


with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)
    errs = []

    # ============ 桌面 / top 布局 ============
    ctx = br.new_context(viewport={'width': 1700, 'height': 1000})
    pg = ctx.new_page()
    pg.on('console', lambda m: errs.append(m.text[:160]) if m.type == 'error' else None)
    pg.on('pageerror', lambda e: errs.append(str(e)[:160]))
    login(pg)
    goto(pg, 'board')

    s0 = pg.evaluate(STATE)
    rec('页头有「归档 1」按钮（含已归档的 1 条）', s0['archBtn'].strip() == '归档 1', s0['archBtn'])
    rec('归档槽不在右栏里了', s0['zoneShown'] and not s0['zoneInRail'], 'inRail=%s' % s0['zoneInRail'])
    rec('归档槽撑满看板宽度（通栏）', s0['zoneW'] >= s0['shellW'] - 2,
        'zone=%d shell=%d' % (s0['zoneW'], s0['shellW']))
    rec('归档槽高度在 72–88px', 72 <= s0['zoneH'] <= 88, 'h=%d' % s0['zoneH'])
    rec('拖进来时文案切成「松手归档」', s0['hotText'].strip() == '松手归档', s0['hotText'])
    rec('归档槽文案', '拖到这里归档' in s0['zoneText'] and '随时可以找回' in s0['zoneText'], s0['zoneText'])
    rec('已归档任务不显示在看板', '早先归档的' not in s0['titles'], str(s0['titles']))
    rec('已归档任务不进右栏接下来 7 天', '早先归档的' not in ' '.join(s0['railItems']), str(s0['railItems'][:3]))
    rec('四列计数不含归档', s0['counts'] == ['2', '1', '2', '0'], str(s0['counts']))
    rec('拖拽前归档槽不显形（无 is-dragging）', not s0['bodyDragging'], str(s0))

    # 拖拽归档
    before_save = save_count['n']
    dr = drag_to_zone(pg, 't1')
    pg.wait_for_timeout(700)
    s1 = pg.evaluate(STATE)
    rec('拖拽过程中 body 标记 is-dragging', dr.get('dragging') is True, str(dr))
    rec('悬停在归档槽时高亮 is-over', dr.get('over') is True, str(dr))
    rec('拖入归档后卡片从看板消失', '要归档的第一条' not in s1['titles'], str(s1['titles']))
    rec('拖入归档后已完成列 -1', s1['counts'] == ['2', '1', '1', '0'], str(s1['counts']))
    rec('页头归档计数 +1', s1['archBtn'].strip() == '归档 2', s1['archBtn'])
    rec('归档会写一次云端', save_count['n'] == before_save + 1, '%d → %d' % (before_save, save_count['n']))
    rec('拖拽结束清掉 is-dragging', not s1['bodyDragging'], '')
    rec('拖拽结束清掉 is-over', not s1['zoneOver'], '')

    # 打开归档弹层
    pg.click('[data-act="archive-open"]')
    pg.wait_for_timeout(600)
    m0 = pg.evaluate(MODAL)
    rec('归档弹层打开', m0['open'], '')
    rec('标题显示条数', '归档任务' in m0.get('head', '') and '2 条' in m0.get('head', ''), m0.get('head', ''))
    rec('列出 2 条归档任务', m0['rows'] == 2, str(m0.get('titles')))
    rec('新归档的排在前面（按归档时间倒序）', m0['titles'][0] == '要归档的第一条', str(m0['titles']))
    rec('每条都能恢复', m0['hasRestore'], '')
    rec('每条都能永久删除', m0['hasDel'], '')
    rec('有清空归档按钮', m0['clearBtn'], '')
    rec('元信息含完成日期与优先级', '完成于 10月22日' in m0['metas'][0] and '优先级 中' in m0['metas'][0], str(m0['metas']))
    rec('每行都有「查看」', m0['hasView'], '')
    rec('按钮顺序是 查看 / 恢复 / 删除',
        m0['btnOrder'] and m0['btnOrder'][0] == ['查看', '恢复', '删除'], str(m0['btnOrder'][:1]))

    # 查看弹窗（只读）
    pg.click('.arch-row [data-act="task-arch-view"]')
    pg.wait_for_timeout(500)
    tv = pg.evaluate("""() => {
      const m = document.querySelector('.task-view');
      if (!m) return {open: false};
      return {
        open: true,
        head: m.querySelector('h3').textContent.replace(/\\s+/g, ' ').trim(),
        title: (m.querySelector('.tv-title') || {}).textContent || '',
        note: (m.querySelector('.tv-note') || {}).textContent || '',
        noteEmpty: !!(m.querySelector('.tv-note') || {}).classList?.contains('empty'),
        meta: m.querySelector('.tv-meta') ? m.querySelector('.tv-meta').innerText.replace(/\\s+/g, ' ').trim() : '',
        hasInput: !!m.querySelector('input,textarea'),
        btns: [...m.querySelectorAll('button')].map(b => b.textContent.trim())
      };
    }""")
    rec('点「查看」打开只读弹窗', tv.get('open'), str(tv)[:80])
    rec('弹窗显示标题', '要归档的第一条' in tv.get('title', ''), tv.get('title', ''))
    rec('弹窗显示备注全文', tv.get('note', '').strip() == '备注内容', tv.get('note', ''))
    rec('只读：没有任何输入框', not tv.get('hasInput'), '')
    rec('只读：只有「关闭」', tv.get('btns') == ['关闭'], str(tv.get('btns')))
    rec('字段里有优先级与完成时间',
        '优先级' in tv.get('meta', '') and '完成时间' in tv.get('meta', ''), tv.get('meta', '')[:90])
    # 查看弹窗和归档弹窗共用同一个 modal 容器，关掉之后要重新打开归档
    pg.click('.task-view [data-act="close-modal"]')
    pg.wait_for_timeout(400)
    pg.click('[data-act="archive-open"]')
    pg.wait_for_timeout(500)

    # 恢复
    pg.click('.arch-row [data-act="task-unarchive"]')
    pg.wait_for_timeout(800)
    s2 = pg.evaluate(STATE)
    m1 = pg.evaluate(MODAL)
    rec('恢复后回到已完成列', s2['counts'] == ['2', '1', '2', '0'], str(s2['counts']))
    rec('恢复后页头计数 -1', s2['archBtn'].strip() == '归档 1', s2['archBtn'])
    rec('恢复后弹层仍开着且只剩 1 条', m1['open'] and m1['rows'] == 1, str(m1.get('rows')))

    # 详情区「归档」按钮
    pg.click('[data-act="close-modal"]')
    pg.wait_for_timeout(400)
    pg.evaluate("""() => {
      const c = document.querySelector('.task[data-id="t4"]');
      c.dispatchEvent(new MouseEvent('dblclick', {bubbles: true}));
    }""")
    pg.wait_for_timeout(500)
    has_btn = pg.evaluate("""() => !!document.querySelector('.task[data-id="t4"].is-open [data-act="task-archive"]')""")
    rec('详情展开后有「归档」按钮', has_btn, '')
    pg.click('.task[data-id="t4"].is-open [data-act="task-archive"]')
    pg.wait_for_timeout(700)
    s3 = pg.evaluate(STATE)
    rec('详情按钮也能归档', '已完成的一条' not in s3['titles'], str(s3['titles']))
    rec('归档后页头变「归档 2」', s3['archBtn'].strip() == '归档 2', s3['archBtn'])

    # 永久删除
    pg.click('[data-act="archive-open"]')
    pg.wait_for_timeout(600)
    pg.on('dialog', lambda d: d.accept())
    pg.click('.arch-row [data-act="task-archive-del"]')
    pg.wait_for_timeout(800)
    m2 = pg.evaluate(MODAL)
    rec('永久删除后归档剩 1 条', m2['rows'] == 1, str(m2.get('titles')))
    rec('删掉的是当前第一条', m2['titles'] == ['早先归档的'], str(m2['titles']))

    # 统计页：已完成仍计入历史
    pg.click('[data-act="close-modal"]')
    pg.wait_for_timeout(400)
    goto(pg, 'stats')
    # v84 起统计页按主题并成 6 块，任务在「任务」小卡里（.tk-grid 的 .rv-cell），
    # 不再是日历页那种 .cal-summary 药丸；数字取「已完成」那格，小字写明含几条归档。
    stats_done = pg.evaluate("""() => {
      const cells = [...document.querySelectorAll('.tk-grid .rv-cell')];
      const c = cells.find(x => ((x.querySelector('small') || {}).textContent || '').trim() === '已完成');
      if (!c) return null;
      return {
        n: Number((((c.querySelector('b') || {}).textContent) || '').replace(/[^0-9]/g, '')),
        sub: (((c.querySelector('span') || {}).textContent) || '').trim()
      };
    }""")
    # 此时完成的只有 t1（在看板）+ t5（已归档），若过滤掉归档会显示 1
    rec('统计页「已完成」仍包含归档任务（历史保留）',
        bool(stats_done) and stats_done['n'] == 2 and '含归档' in stats_done['sub'],
        str(stats_done))

    # 今日页不含归档任务
    goto(pg, 'today')
    today_txt = pg.evaluate("() => document.querySelector('#main').textContent")
    rec('今日页不显示已归档任务', '早先归档的' not in today_txt, '')

    # 手机：右栏隐藏，详情按钮仍在
    ctx2 = br.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True)
    pg2 = ctx2.new_page()
    pg2.on('pageerror', lambda e: errs.append('[m] ' + str(e)[:160]))
    login(pg2)
    goto(pg2, 'board')
    ms = pg2.evaluate(STATE)
    rec('[手机 390] 归档槽仍然显示（不再藏在右栏里）', ms['zoneShown'], 'h=%s' % ms['zoneShown'])
    rec('[手机 390] 归档槽改纵向排列（更高）', ms['zoneH'] >= 80, 'h=%s' % ms['zoneH'])
    rec('[手机 390] 页头仍有归档入口', '归档' in ms['archBtn'], ms['archBtn'])
    rec('[手机 390] 无横向溢出', ms['ovf'] <= 0, '%dpx' % ms['ovf'])

    ctx3 = br.new_context(viewport={'width': 360, 'height': 780}, is_mobile=True, has_touch=True)
    pg3 = ctx3.new_page()
    pg3.on('pageerror', lambda e: errs.append('[m2] ' + str(e)[:160]))
    login(pg3)
    goto(pg3, 'board')
    m3 = pg3.evaluate(STATE)
    rec('[手机 360] 无横向溢出', m3['ovf'] <= 0, '%dpx' % m3['ovf'])

    # 侧栏布局也不显示宽屏归档槽（只有 top + >=1520 有右栏）
    ctx4 = br.new_context(viewport={'width': 1440, 'height': 900})
    pg4 = ctx4.new_page()
    pg4.on('pageerror', lambda e: errs.append('[side] ' + str(e)[:160]))
    login(pg4, layout='side')
    goto(pg4, 'board')
    s4 = pg4.evaluate(STATE)
    rec('[侧栏布局 1440] 归档槽仍在且不靠右栏', s4['zoneShown'] and not s4['zoneInRail'], '')
    rec('[侧栏布局] 页头仍有归档入口', '归档' in s4['archBtn'], s4['archBtn'])

    rec('无 JS 异常', not errs, '; '.join(errs[:3]))

    br.close()

srv.shutdown()
ok = sum(1 for _, o, _ in results if o)
print('\n归档功能：%d/%d 通过' % (ok, len(results)))
sys.exit(0 if ok == len(results) else 1)
