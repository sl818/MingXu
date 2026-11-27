"""喝水 / 运动 的「数据不变量」测试（invariant test）

跟 verify-water / verify-move-full 的区别：
  那两份验的是「按钮能点、数字会变」；
  这一份验的是「数据该成立的性质」——即使 UI 看着正常，不变量被打破就说明数据是错的。

原则：每条断言都写「应该成立」，不写「现在是这样」。
      写反了就会保护 bug（改实现时测试全红，逼你改测试而不是改代码）。

跑法：python e2e/invariants-water-move.py
      全绿 = 这两块的数据是自洽的；红 = 下面「未通过」那几条就是待修的点。
"""
import http.server, threading, json, socketserver, secrets, sys, re, time
from datetime import datetime
from playwright.sync_api import sync_playwright

DOC = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo'
PORT = 38711
USER = {'id': 1, 'email': 't@e.com', 'display_name': 'T', 'is_admin': False}

BOARD = {'data': None, 'rev': 5}


def water_board(goal=2300, per=250, cups=9, checks=None):
    return {'version': 2, 'view': 'today', 'schemaVersion': 6,
            'habits': [{'id': 'h_med', 'name': '用药', 'icon': '💊', 'type': 'build', 'target': 1, 'unit': '次',
                        'color': '#2f6f5e', 'note': '', 'createdAt': '2026-10-01T00:00:00Z', 'pinned': True,
                        'med': True, 'archivedAt': ''},
                       {'id': 'h_water', 'name': '喝水', 'icon': '💧', 'type': 'build', 'target': cups, 'unit': '杯',
                        'color': '#4c7f96', 'note': '', 'perMl': per, 'goalMl': goal,
                        'createdAt': '2026-10-01T00:00:00Z', 'pinned': True, 'archivedAt': ''}],
            'checks': checks or {}, 'notes': {}, 'moods': {}, 'events': [], 'meds': [], 'doses': {},
            'modules': {'water': {'on': True, 'name': '喝水', 'icon': '💧', 'color': '#4c7f96', 'note': '',
                                  'unit': '杯', 'cups': cups, 'perMl': per, 'goalMl': goal,
                                  'notify': False, 'suggestTime': '', 'notifyFreq': 'daily',
                                  'notifyChannels': ['browser'], 'notifyMode': 'each', 'notifyDailyCount': 2,
                                  'notifyDailyTimes': {'morning': '08:00', 'noon': '12:30', 'afternoon': '15:00'},
                                  'notifyStart': '08:00', 'notifyEnd': '21:00',
                                  'createdAt': '2026-10-01T00:00:00Z', 'updatedAt': '2026-10-01T00:00:00Z'}},
            'modulesAt': 0, 'bodyProfile': {'age': 30, 'height': 170}, 'weights': [], 'essays': [], 'tasks': []}


def move_board_no_sport():
    """运动模块存在但一个运动实例都没有 —— 这是「孤儿记录」最容易发生的状态"""
    d = water_board()
    d['modules']['move'] = {'on': True, 'name': '运动', 'icon': '🏃', 'color': '#b5733f', 'note': '',
                            'unit': '次', 'times': 1, 'notify': False, 'suggestTime': '',
                            'notifyFreq': 'daily', 'notifyChannels': ['browser'],
                            'notifyScenes': {'steps': True, 'plan': True, 'week': True},
                            'sports': [], 'records': [],
                            'createdAt': '2026-10-01T00:00:00Z', 'updatedAt': '2026-10-01T00:00:00Z'}
    return d


sessions = {}


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
            elif a == 'load': self._j({'ok': True, 'data': BOARD['data'], 'rev': BOARD['rev'], 'updated_at': 0})
            else: self._j({'ok': False, 'error': '?'}, 404)
        else: super().do_GET()

    def do_POST(self):
        if self.path.startswith('/api.php'):
            a = self.path.split('action=')[-1].split('&')[0]
            n = int(self.headers.get('Content-Length', 0)); body = json.loads(self.rfile.read(n) or b'{}')
            if a == 'login':
                sid = secrets.token_hex(8); sessions[sid] = USER
                self._j({'ok': True, 'user': USER, 'csrf': 'x'}, eh={'Set-Cookie': 'sid=' + sid + '; Path=/'})
            elif a in ('save', 'force'):
                BOARD['data'] = body.get('data', BOARD['data']); BOARD['rev'] += 1
                self._j({'ok': True, 'rev': BOARD['rev']})
            else: self._j({'ok': False, 'error': '?'}, 404)
        else: self.send_response(405); self.end_headers()


class TS(socketserver.ThreadingMixIn, http.server.HTTPServer): daemon_threads = True
srv = TS(('127.0.0.1', PORT), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()

results = []


def rec(name, ok, detail=''):
    results.append((name, ok, detail))
    print(('PASS  ' if ok else 'FAIL  ') + name + (('  | ' + str(detail)) if detail else ''), flush=True)


def open_page(br, nav):
    ctx = br.new_context(viewport={'width': 1440, 'height': 980})
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    cons = []
    pg.on('console', lambda m: cons.append(m.text) if m.type in ('log','info') else None)
    pg.__cons__ = cons
    pg.clock.install(time=datetime(2026, 10, 24, 14, 0, 0))
    pg.add_init_script("try{localStorage.setItem('lifeboard.layout','top');localStorage.setItem('lifeboard.skin','paper');"
                       "localStorage.setItem('lifeboard.theme.mode','light')}catch(e){}")
    pg.goto('http://127.0.0.1:%d/index.html?_t=%d' % (PORT, int(time.time()*1000)), wait_until='networkidle')
    pg.wait_for_timeout(700)
    pg.click('[data-act="cloud-login"]'); pg.wait_for_timeout(450)
    pg.fill('input[name="email"]', USER['email']); pg.fill('input[name="password"]', '12345678')
    pg.click('form.modal-card button[type="submit"]'); pg.wait_for_timeout(2600)
    pg.evaluate("() => { document.querySelector('[data-nav=\"%s\"]').click(); }" % nav)
    pg.wait_for_timeout(1100)
    return ctx, pg, errs


# 读喝水页的关键数据
WATER = """() => {
  const q = s => document.querySelector(s);
  const txt = e => e ? e.textContent.replace(/\\s+/g, ' ').trim() : '';
  const v = n => { const e = q('input[name="' + n + '"]'); return e ? e.value : ''; };
  const st = txt(q('[class*=water] [class*=status], .breath-status'));
  const m = st.match(/([\\d,]+)\\s*\\/\\s*([\\d,]+)\\s*ml/);
  const kpi = Array.from(document.querySelectorAll('.w-kpi b')).map(txt);
  return {
    goalMl: v('goalMl'), perMl: v('perMl'), cups: v('cups'),
    status: st, gotMl: m ? Number(m[1].replace(/,/g, '')) : null,
    targetMl: m ? Number(m[2].replace(/,/g, '')) : null,
    kpi: kpi,
    /* 喝水卡是普通 vital-card，状态文本是「2550 / 2300 ml」不含「已完成」字样，
       达标标志看 .is-done class（这个坑我第一次就踩了，写成了 /已完成/ 正则） */
    done: (function () {
      const btn = q('[data-act="habit-inc"][data-id="h_water"]') || q('[data-act="habit-dec"][data-id="h_water"]');
      const card = btn ? btn.closest('.vital-card') : null;
      return card ? card.classList.contains('is-done') : false;
    })(),
    toast: txt(q('#toast'))
  };
}"""

with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)

    # ========== 喝水 ==========
    BOARD['data'] = water_board(); BOARD['rev'] = 5
    ctx, pg, errs = open_page(br, 'water')
    w0 = pg.evaluate(WATER)
    print('\n初始：', json.dumps(w0, ensure_ascii=False), flush=True)

    # W1 往返一致性：改总量 → 保存 → 重新加载，值不变
    pg.fill('input[name="goalMl"]', '2600')
    pg.wait_for_timeout(500)
    pg.click('#water-settings-form button[type="submit"]')
    pg.wait_for_timeout(2200)
    saved = BOARD['data']['modules']['water'].get('goalMl')
    saved_cups = BOARD['data']['modules']['water'].get('cups')
    rec('W1 只改「每天总量」2600 → 存下来必须还是 2600', saved == 2600,
        '存了 goalMl=%r cups=%r' % (saved, saved_cups))

    # W2 改杯数不动自定义总量
    BOARD['data'] = water_board(); BOARD['rev'] += 1
    ctx.close()
    ctx, pg, errs = open_page(br, 'water')
    pg.fill('input[name="cups"]', '12')
    pg.wait_for_timeout(400)
    after12 = pg.evaluate("() => { const e=document.querySelector('input[name=\"goalMl\"]'); return e?e.value:''; }")
    pg.click('#water-settings-form button[type="submit"]')
    pg.wait_for_timeout(2200)
    rec('W2 改「每天几杯」不应改写「每天总量」',
        after12 == '2300' and BOARD['data']['modules']['water'].get('goalMl') == 2300,
        '输入框=%r 存了=%r' % (after12, BOARD['data']['modules']['water'].get('goalMl')))

    # W3 目标 ≥ 杯数 × 每杯（否则最后一杯溢出）
    BOARD['data'] = water_board(); BOARD['rev'] += 1
    ctx.close()
    ctx, pg, errs = open_page(br, 'water')
    w = pg.evaluate(WATER)
    tgt = w['targetMl'] or 0
    rec('W3 目标毫升 ≥ 杯数 × 每杯（2250）', tgt >= 9 * 250, '目标=%r' % tgt)

    # W4【尺子一致】状态说「已完成」时，完成度必须 100%
    #    现在：9 杯 = 2250 < 2300，杯数达标 → 状态已完成，但完成度 98% → 红
    BOARD['data'] = water_board(checks={'2026-10-24': {'h_water': 9}})
    BOARD['rev'] += 1
    ctx.close()
    ctx, pg, errs = open_page(br, 'water')
    w9 = pg.evaluate(WATER)
    rec('W4 状态「已完成」时完成度必须 = 100%（两把尺子打架检测）',
        (not w9['done']) or (w9['kpi'] and w9['kpi'][0] == '100%'),
        '状态=%r 今日完成度=%r' % (w9['status'], w9['kpi'][0] if w9['kpi'] else ''))

    # W5 喝到目标毫升 → 必须达标
    BOARD['data'] = water_board(checks={'2026-10-24': {'h_water': 10}})
    BOARD['rev'] += 1
    ctx.close()
    ctx, pg, errs = open_page(br, 'water')
    w10 = pg.evaluate(WATER)
    rec('W5 喝满目标毫升（10 杯 = 2500 ≥ 2300）必须判达标',
        w10['done'], '状态=%r 今日完成度=%r' % (w10['status'], w10['kpi'][0] if w10['kpi'] else ''))

    # W6 日均必须含今天（同一块的 p7 / p30 / met30 都含今天，只有 sum7 曾经从昨天算起）
    BOARD['data'] = water_board(checks={'2026-10-24': {'h_water': 4}})
    BOARD['rev'] += 1
    ctx.close()
    ctx, pg, errs = open_page(br, 'water')
    w6 = pg.evaluate("""() => {
      const txt = e => e ? e.textContent.replace(/\\s+/g, ' ').trim() : '';
      const items = Array.from(document.querySelectorAll('.w-mini'));
      const hit = items.find(x => /近 7 天日均/.test(txt(x)));
      return { avg: hit ? Number((hit.querySelector('b') || {}).textContent.replace(/,/g, '')) : null };
    }""")
    rec('W6 今天喝了 4 杯时，「近 7 天日均」必须 > 0（不能漏掉今天）',
        (w6['avg'] or 0) > 0, '日均=%r' % w6['avg'])

    # W7 每记一杯要有反馈
    pg.evaluate("() => { const b=document.querySelector('[data-act=\"habit-inc\"][data-id=\"h_water\"]'); if(b) b.click(); }")
    pg.wait_for_timeout(1600)
    w7 = pg.evaluate("""() => {
      const t = document.querySelector('#toast');
      return { text: t ? t.textContent : '', on: t ? t.classList.contains('show') : false };
    }""")
    rec('W7 记录一杯要有 toast 反馈', w7['on'] and ('已记录一杯' in w7['text']), json.dumps(w7, ensure_ascii=False))
    ctx.close()

    # ========== 运动 ==========
    BOARD['data'] = move_board_no_sport(); BOARD['rev'] += 1
    ctx, pg, errs = open_page(br, 'move')
    m0 = pg.evaluate("""() => {
      const txt = e => e ? e.textContent.replace(/\\s+/g, ' ').trim() : '';
      const b = document.querySelector('[data-act="move-add-rec"]');
      return { empty: /还没有运动/.test(document.body.innerText || ''),
               btn: !!b, disabled: b ? (b.disabled || b.getAttribute('disabled') !== null) : null,
               cls: b ? b.className : '' };
    }""")
    # M1 不要求禁用（那样太硬），要求「点了也不能产生脏数据 + 引导用户去新建」
    guided = None
    if m0['btn']:
        pg.evaluate("() => { document.querySelector('[data-act=\"move-add-rec\"]').click(); }")
        pg.wait_for_timeout(900)
        guided = pg.evaluate("""() => {
          const t = (document.querySelector('#toast') || {}).textContent || '';
          return { toast: t, newModal: /新建运动/.test((document.querySelector('.modal-card h3') || {}).textContent || '') };
        }""")
        pg.evaluate("() => { const b=document.querySelector('[data-act=\"close-modal\"]'); if(b) b.click(); }")
        pg.wait_for_timeout(400)
    rec('M1 没有运动实例时点「添加记录」应被引导去新建（不产生记录）',
        bool(guided) and (guided['newModal'] or '先新建' in guided['toast']),
        json.dumps(guided, ensure_ascii=False) if guided else 'no-btn')

    # M2 没有实例时不应能写入 record（点了也不该落数据）
    recs = (BOARD['data']['modules']['move'].get('records') or [])
    sports = (BOARD['data']['modules']['move'].get('sports') or [])
    orphans = [r for r in recs if not any(s.get('key') == r.get('key') for s in sports)]
    rec('M2 不应产生「孤儿记录」（key 找不到对应运动实例）', len(orphans) == 0,
        'records=%d sports=%d 孤儿=%d' % (len(recs), len(sports), len(orphans)))
    ctx.close()

    # M3 筛选只列「用户真有的」模式（一个都没建时，除「全部」外不该有别的入口）
    BOARD['data'] = move_board_no_sport(); BOARD['rev'] += 1
    ctx, pg, errs = open_page(br, 'move')
    chips = pg.evaluate("""() => Array.from(document.querySelectorAll('[data-act="move-stat-mode"]'))
        .map(x => x.textContent.replace(/\\s+/g, ' ').trim())""")
    rec('M3 没有运动实例时，筛选只应有「全部」（不列模式库全量）',
        chips == ['全部'], '实际=%r' % (chips,))
    ctx.close()

    # ========== v209 模块启停链路 ==========
    BOARD['data'] = water_board(checks={'2026-10-24': {'h_water': 5}})
    BOARD['rev'] += 1
    ctx, pg, errs = open_page(br, 'modules')
    # M4 停用喝水：开关落库 + 锚点归档 + 导航隐藏，但 checks 数据保留
    pg.evaluate("() => { const c=document.querySelector('[data-act=\"module-toggle\"][data-key=\"water\"]'); if(c) c.click(); }")
    pg.wait_for_timeout(1800)
    m4 = pg.evaluate("() => ({ navWater: Array.from(document.querySelectorAll('[data-nav=\"water\"]')).length, rowOff: document.querySelectorAll('.mdl-row.off').length })")
    st = BOARD['data']
    rec('M4 停用后：开关落库（on=false）',
        st['modules']['water'].get('on') is False, str(st['modules']['water'].get('on')))
    rec('M4 停用后：锚点习惯被归档（archivedAt 非空）',
        bool((st['habits'][1] or {}).get('archivedAt')),
        str((st['habits'][1] or {}).get('archivedAt'))[:30])
    rec('M4 停用后：导航里不再有「喝水」入口', m4['navWater'] == 0, '入口数=%d' % m4['navWater'])
    rec('M4 停用后：打卡数据一个字节不动',
        st['checks'].get('2026-10-24', {}).get('h_water') == 5,
        str(st['checks'].get('2026-10-24')))

    # M5 再开启：一切恢复
    saves = []
    pg.on('request', lambda req: saves.append(('water":{"on":True' in (req.post_data or '')) or ('water":{"on":true' in (req.post_data or ''))) if (req.method == 'POST' and 'save' in req.url) else None)
    pg.click('[data-act="module-toggle"][data-key="water"]')   # M5：Playwright click（带自动重试）
    print('  [M5] console:', [c for c in pg.__cons__ if any(t in c for t in ('[save]', '[cloudOLC]', '[setModuleOn]'))][-8:], flush=True)

    pg.wait_for_timeout(1800)
    m5 = pg.evaluate("() => Array.from(document.querySelectorAll('[data-nav=\"water\"]')).length")
    pg.wait_for_timeout(1500)   # save() 有 600ms 防抖，落库晚于 UI —— 给它发出去的时间
    print('  [M5] save 请求数=%d，其中含启用=%s' % (len(saves), any(saves)), flush=True)
    st = BOARD['data']   # mock 的 save 是整体替换 BOARD['data']，必须重新取引用
    rec('M5 重新开启：开关恢复（on=true）',
        st['modules']['water'].get('on') is True, str(st['modules']['water'].get('on')))
    rec('M5 重新开启：锚点归档清空', not (st['habits'][1] or {}).get('archivedAt'),
        str((st['habits'][1] or {}).get('archivedAt')))
    rec('M5 重新开启：导航恢复「喝水」入口', m5 >= 1, '入口数=%d' % m5)
    rec('M5 重新开启：数据仍在（checks 未丢）',
        st['checks'].get('2026-10-24', {}).get('h_water') == 5,
        str(st['checks'].get('2026-10-24')))

    # M6 停用状态下刷新：view 兜底回仪表盘，不进停用页
    pg.evaluate("() => { const c=document.querySelector('[data-act=\"module-toggle\"][data-key=\"water\"]'); if(c) c.click(); }")
    pg.wait_for_timeout(1200)
    pg.evaluate("() => { localStorage.setItem('lifeboard.view', 'water'); }")
    pg.reload(wait_until='networkidle'); pg.wait_for_timeout(2200)
    m6 = pg.evaluate("() => ({ hasWaterCard: /每天喝水量/.test(document.body.innerText || '') })")
    rec('M6 停用状态下刷新，view 兜底回仪表盘（不进停用页）',
        not m6['hasWaterCard'], str(m6))
    ctx.close()

    br.close()

srv.shutdown()
ok = sum(1 for r in results if r[1])
print('\n不变量体检：%d/%d 通过' % (ok, len(results)))
if ok != len(results):
    print('未通过（这些就是待修的点）：')
    for n, o, d in results:
        if not o: print('  ·', n, '|', d)
    sys.exit(1)
