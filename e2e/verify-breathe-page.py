"""478 呼吸法页 v194 验证：介绍 / 页内设置 / 图标名锁死 / 统计四档 / 提醒时间点联动 / 统计页块"""
import http.server, threading, json, socketserver, secrets, sys
from datetime import datetime
from playwright.sync_api import sync_playwright

DOC = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo'
USER = {'id': 1, 'email': 'test@example.com', 'display_name': '测试', 'is_admin': False}
sessions = {}
PORT = 38558
D = '2026-10-24'

OTHER = [
    {'id': 'h_med', 'name': '用药', 'icon': '💊', 'type': 'build', 'target': 1, 'unit': '次',
     'color': '#2f6f5e', 'note': '', 'createdAt': '2026-10-01T00:00:00Z', 'pinned': True, 'med': True, 'archivedAt': ''},
    {'id': 'h_water', 'name': '喝水', 'icon': '💧', 'type': 'build', 'target': 9, 'unit': '杯',
     'color': '#4c7f96', 'note': '', 'perMl': 250, 'goalMl': 2300, 'createdAt': '2026-10-01T00:00:00Z', 'pinned': True, 'archivedAt': ''},
]


def breathe_module(**kw):
    m = {'on': True, 'name': '478呼吸法', 'icon': '🌬️', 'color': '#5b8f8a', 'note': '4-7-8 呼吸',
         'unit': '组', 'groups': 3, 'cycles': 4, 'notify': True, 'suggestTime': '07:00',
         'notifyFreq': 'daily', 'notifyWeekday': 1, 'notifyMonthday': 1, 'notifyNote': '',
         'notifyChannels': ['browser'], 'notifyTimes': ['07:00', '13:00', '21:00'],
         'createdAt': '2026-10-01T00:00:00Z', 'updatedAt': '2026-10-01T00:00:00Z'}
    m.update(kw)
    return m


def make_board(modules=None, checks=None):
    checks = checks if checks is not None else {
        '2026-10-22': {'h_breathe': 2},
        '2026-10-23': {'h_breathe': 1},
        '2026-10-24': {'h_breathe': 1},
    }
    mods = {'breathe': breathe_module()}
    if modules:
        mods.update(modules)
    data = {'version': 2, 'view': 'today', 'habits': OTHER, 'checks': checks, 'notes': {}, 'moods': {},
            'events': [], 'meds': [], 'doses': {}, 'modules': mods, 'modulesAt': 0,
            'bodyProfile': {'age': 30, 'height': 170}, 'weights': [], 'essays': [], 'tasks': []}
    return {'data': data, 'rev': 5}


board = make_board()
save_count = {'n': 0}
rev_counter = {'n': 100}


def set_board(b):
    """换一组测试数据时同时把 rev 换成一个没被用过的值 ——
    否则上一个用例里迟到的 save 请求（base_rev 相同）会把新数据覆盖掉。"""
    rev_counter['n'] += 1
    b['rev'] = rev_counter['n']
    board.update(b)


class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw): super().__init__(*a, directory=DOC, **kw)

    def log_message(self, *a): pass

    def _j(self, o, s=200, eh=None):
        b = json.dumps(o, ensure_ascii=False).encode()
        self.send_response(s); self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(b)))
        for k, v in (eh or {}).items(): self.send_header(k, v)
        self.end_headers()
        self.wfile.write(b)

    def _sid(self):
        for p in (self.headers.get('Cookie', '') or '').split(';'):
            p = p.strip()
            if p.startswith('sid='): return p[4:]

    def do_GET(self):
        if self.path.startswith('/api.php'):
            a = self.path.split('action=')[-1].split('&')[0]
            if a == 'status': self._j({'ok': True, 'installed': True, 'registration_open': False})
            elif a == 'me': self._j({'ok': True, 'user': sessions.get(self._sid()), 'csrf': 'x', 'registration_open': False})
            elif a == 'load': self._j({'ok': True, 'data': board['data'], 'rev': board['rev'], 'updated_at': 0})
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
        else: self.send_response(405); self.end_headers()


class TS(socketserver.ThreadingMixIn, http.server.HTTPServer): daemon_threads = True
srv = TS(('127.0.0.1', PORT), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()

results = []


def rec(name, ok, detail=''):
    results.append((name, ok, detail))
    print(('PASS  ' if ok else 'FAIL  ') + name + (('  | ' + str(detail)) if detail else ''))


PAGE = """() => {
  const q = s => document.querySelector(s);
  const qa = s => Array.from(document.querySelectorAll(s));
  const page = q('.breathe-page');
  if (!page) return null;
  const secTitle = n => { const el = qa('.w-sec-title').find(x => x.textContent.indexOf(n) >= 0); return el ? el.textContent.trim() : ''; };
  const setForm = q('#breathe-settings-form');
  const notifyForm = q('#breathe-notify-form');
  return {
    title: (q('.page-head h2') || {}).textContent || '',
    sub: (q('.page-head .sub') || {}).textContent.replace(/\\s+/g, ' ').trim(),
    hasSetBtn: !!q('[data-act="module-edit"]'),
    secTitles: qa('.w-sec-title').map(x => x.textContent.trim()),
    benefitCount: qa('.w-benefit').length,
    sciText: (q('.w-sci') || {}).textContent.replace(/\\s+/g, ' ').trim() || '',
    lockText: (q('.w-locked .lock') || {}).textContent.trim() || '',
    lockName: (q('.w-locked b') || {}).textContent.trim() || '',
    setFields: setForm ? Array.from(setForm.querySelectorAll('input,select')).map(x => x.name) : [],
    setHint: (q('#breathe-link-hint') || {}).textContent.replace(/\\s+/g, ' ').trim() || '',
    rangeBtns: qa('.br-range button').map(x => x.textContent.trim()),
    rangeActive: (q('.br-range button.active') || {}).textContent.trim() || '',
    kpiCount: qa('.w-kpi').length,
    miniLabels: qa('.w-mini span').map(x => x.textContent.trim()),
    miniVals: qa('.w-mini b').map(x => x.textContent.trim()),
    trendSvg: qa('.br-trend svg').length,
    algoText: (q('.w-algo') || {}).textContent.replace(/\\s+/g, ' ').trim() || '',
    notifySwitch: !!notifyForm && !!notifyForm.querySelector('[name="notify"]'),
    chanCount: notifyForm ? notifyForm.querySelectorAll('[name="channels"]').length : 0,
    timeCount: notifyForm ? notifyForm.querySelectorAll('#breathe-times input[type="time"]').length : 0,
    timeVals: notifyForm ? Array.from(notifyForm.querySelectorAll('#breathe-times input[type="time"]')).map(x => x.value) : [],
    freqNote: (q('.w-freq-note') || {}).textContent.replace(/\\s+/g, ' ').trim() || '',
    ovf: document.documentElement.scrollWidth - innerWidth
  };
}"""


def open_page(br, w=1440, h=950, mobile=False):
    kw = {'viewport': {'width': w, 'height': h}}
    if mobile: kw.update({'is_mobile': True, 'has_touch': True, 'device_scale_factor': 2})
    ctx = br.new_context(**kw)
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.clock.install(time=datetime(2026, 10, 24, 14, 0, 0))
    pg.add_init_script("try{localStorage.setItem('lifeboard.layout','top');localStorage.setItem('lifeboard.skin','paper');localStorage.setItem('lifeboard.theme.mode','light')}catch(e){}")
    pg.goto('http://127.0.0.1:%d/index.html' % PORT, wait_until='networkidle')
    pg.wait_for_timeout(700)
    pg.click('[data-act="cloud-login"]'); pg.wait_for_timeout(500)
    pg.fill('input[name="email"]', USER['email']); pg.fill('input[name="password"]', '12345678')
    pg.click('form.modal-card button[type="submit"]')
    pg.wait_for_timeout(2600)
    return ctx, pg, errs


with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)

    # ---------- 页面结构 ----------
    set_board(make_board())
    ctx, pg, errs = open_page(br)
    pg.evaluate("() => { document.querySelector('[data-nav=\"breathe\"]').click(); }")
    pg.wait_for_timeout(700)
    c = pg.evaluate(PAGE)
    rec('478 页渲染', c is not None, '')
    rec('页头标题 478呼吸法', c['title'].strip() == '478呼吸法', c['title'])
    rec('页头副标题带组数与循环数',
        '每天 3 组' in c['sub'] and '每组 4 次循环' in c['sub'] and '1 分 16 秒' in c['sub'], c['sub'])
    rec('右上角「设置」按钮已撤掉', not c['hasSetBtn'], '')
    rec('四个区块齐全（介绍/设置/统计/提醒）',
        c['secTitles'] == ['478呼吸法的介绍', '478呼吸法设置', '数据统计', '478呼吸法提醒'], str(c['secTitles']))
    rec('介绍 6 张卡', c['benefitCount'] == 6, '%d 张' % c['benefitCount'])
    rec('介绍底部有做法说明', '吸气 4 秒' in c['sciText'] and '屏息 7 秒' in c['sciText'], c['sciText'][:40])
    rec('锁定行写明不可修改', '图标' in c['lockText'] and '名称' in c['lockText'] and '固定' in c['lockText'], c['lockText'])
    rec('锁定行名称 478呼吸法', c['lockName'] == '478呼吸法', c['lockName'])
    rec('设置区只有「每天几组」「每组循环次数」',
        sorted(c['setFields']) == ['cycles', 'groups'], str(c['setFields']))
    rec('设置区没有图标/名称/颜色/备注输入框',
        not any(k in c['setFields'] for k in ('icon', 'name', 'color', 'note')), str(c['setFields']))
    rec('设置联动提示：组数 × 循环 = 次数',
        '每天 3 组' in c['setHint'] and '4 次循环' in c['setHint'] and '12 次呼吸' in c['setHint'], c['setHint'])
    rec('统计区四档切换', c['rangeBtns'] == ['近 7 天', '近 1 月', '近 3 月', '全部'], str(c['rangeBtns']))
    rec('默认档位 近 7 天', c['rangeActive'] == '近 7 天', c['rangeActive'])
    rec('KPI 三个环', c['kpiCount'] == 3, '%d 个' % c['kpiCount'])
    rec('统计小卡 6 个（含组数/次数/累计）',
        len(c['miniLabels']) == 6 and any('完成组数' in x for x in c['miniLabels'])
        and any('呼吸次数' in x for x in c['miniLabels']), str(c['miniLabels']))
    rec('近 7 天组数 = 4（2+1+1）', c['miniVals'][0] == '4', str(c['miniVals'][:2]))
    rec('近 7 天呼吸次数 = 16（4 组 × 4 次）', c['miniVals'][1] == '16', str(c['miniVals'][:2]))
    rec('累计组数 = 4', c['miniVals'][4] == '4', str(c['miniVals']))
    rec('累计呼吸次数 = 16', c['miniVals'][5] == '16', str(c['miniVals']))
    rec('趋势图有 1 张', c['trendSvg'] == 1, '%d 张' % c['trendSvg'])
    rec('算法说明写清达标与次数口径',
        '每天几组' in c['algoText'] and '循环次数' in c['algoText'], c['algoText'][:50])
    rec('提醒区有开关', c['notifySwitch'], '')
    rec('提醒渠道 3 个', c['chanCount'] == 3, '%d 个' % c['chanCount'])
    rec('时间点数量 = 每天几组（3）', c['timeCount'] == 3, '%d 个' % c['timeCount'])
    rec('时间点回显已存的值', c['timeVals'] == ['07:00', '13:00', '21:00'], str(c['timeVals']))
    rec('提醒说明写明按组数生成', '每天 3 组' in c['freqNote'] and '3 个提醒时间' in c['freqNote'], c['freqNote'])
    rec('无 JS 异常', not errs, str(errs[:2]))
    pg.screenshot(path='design/shots/breathe-page.png')
    ctx.close()

    # ---------- 改组数 → 提醒时间点联动 ----------
    set_board(make_board())
    ctx, pg, errs = open_page(br)
    pg.evaluate("() => { document.querySelector('[data-nav=\"breathe\"]').click(); }")
    pg.wait_for_timeout(700)
    pg.fill('#breathe-settings-form input[name="groups"]', '5')
    pg.wait_for_timeout(400)
    c = pg.evaluate(PAGE)
    rec('改组数 → 提醒时间点变 5 个', c['timeCount'] == 5, '%d 个' % c['timeCount'])
    rec('联动后提示变成 5 组 × 4 次 = 20 次',
        '每天 5 组' in c['setHint'] and '20 次呼吸' in c['setHint'], c['setHint'])
    # 保存设置
    pg.click('#breathe-settings-form button[type="submit"]')
    pg.wait_for_timeout(1400)
    m = board['data']['modules']['breathe']
    rec('保存设置 → groups=5', int(m.get('groups') or 0) == 5, str(m.get('groups')))
    rec('保存设置 → notifyTimes 变成 5 个', len(m.get('notifyTimes') or []) == 5, str(m.get('notifyTimes')))
    rec('保存设置 → 新增的两个时间点合法且在 07:00–21:00 之间',
        all(t in ('07:00', '10:30', '14:00', '17:30', '21:00') for t in m.get('notifyTimes', [])[3:]),
        str(m.get('notifyTimes')))
    rec('保存设置 → 保留原有时间值',
        m.get('notifyTimes', [])[:3] == ['07:00', '13:00', '21:00'], str(m.get('notifyTimes')))
    rec('保存设置 → suggestTime 同步第一个', m.get('suggestTime') == '07:00', str(m.get('suggestTime')))
    ctx.close()

    # ---------- 提醒保存 ----------
    set_board(make_board())
    ctx, pg, errs = open_page(br)
    pg.evaluate("() => { document.querySelector('[data-nav=\"breathe\"]').click(); }")
    pg.wait_for_timeout(700)
    pg.fill('#breathe-times input[name="bt1"]', '11:30')
    pg.wait_for_timeout(200)
    pg.click('#breathe-notify-form button[type="submit"]')
    pg.wait_for_timeout(1400)
    m = board['data']['modules']['breathe']
    rec('保存提醒 → 写回 notifyTimes', m.get('notifyTimes') == ['07:00', '11:30', '21:00'], str(m.get('notifyTimes')))
    rec('保存提醒 → 渠道仍是浏览器', m.get('notifyChannels') == ['browser'], str(m.get('notifyChannels')))
    ctx.close()

    # ---------- 统计档位切换 ----------
    set_board(make_board())
    ctx, pg, errs = open_page(br)
    pg.evaluate("() => { document.querySelector('[data-nav=\"breathe\"]').click(); }")
    pg.wait_for_timeout(700)
    pg.click('.br-range button[data-range="30"]')
    pg.wait_for_timeout(500)
    c = pg.evaluate(PAGE)
    rec('切到近 1 月', c['rangeActive'] == '近 1 月', c['rangeActive'])
    pg.click('.br-range button[data-range="0"]')
    pg.wait_for_timeout(500)
    c = pg.evaluate(PAGE)
    rec('切到全部', c['rangeActive'] == '全部', c['rangeActive'])
    rec('全部档改画按月柱状（无折线）', c['trendSvg'] == 0, '%d 张 svg' % c['trendSvg'])
    ctx.close()

    # ---------- 统计页的 478 块 ----------
    set_board(make_board())
    ctx, pg, errs = open_page(br)
    pg.evaluate("() => { document.querySelector('[data-nav=\"stats\"]').click(); }")
    pg.wait_for_timeout(900)
    st = pg.evaluate("""() => {
      const heads = Array.from(document.querySelectorAll('.panel .shead h3')).map(x => x.textContent.trim());
      const panel = Array.from(document.querySelectorAll('.panel')).find(p => (p.querySelector('.shead h3') || {}).textContent && p.querySelector('.shead h3').textContent.indexOf('478呼吸法') >= 0);
      if (!panel) return { heads: heads, kpis: 0, goto: false, today: '' };
      return {
        heads: heads,
        kpis: panel.querySelectorAll('.stt-kpi').length,
        goto: !!panel.querySelector('[data-act="breathe-goto"]'),
        today: (panel.querySelector('.ms-val') || {}).textContent || ''
      };
    }""")
    rec('统计页有 478 块', any('478呼吸法' in h for h in st['heads']), str(st['heads'][:6]))
    rec('统计页 478 块 KPI 6 张', st['kpis'] == 6, '%d 张' % st['kpis'])
    rec('统计页有「完整统计 →」', st['goto'], '')
    rec('统计页今日行写组数', '/ 3 组' in st['today'], st['today'])
    # 点「完整统计 →」跳回 478 页
    pg.click('[data-act="breathe-goto"]')
    pg.wait_for_timeout(800)
    ok = pg.evaluate("() => !!document.querySelector('.breathe-page')")
    rec('「完整统计 →」跳回 478 页', ok, '')
    ctx.close()

    # ---------- 旧数据迁移 ----------
    old = make_board()
    old['data'].pop('modules')
    set_board(old)
    ctx, pg, errs = open_page(br)
    pg.evaluate("() => { document.querySelector('[data-nav=\"breathe\"]').click(); }")
    pg.wait_for_timeout(700)
    c = pg.evaluate(PAGE)
    rec('[迁移] 老数据没有 modules 也能出页面', c is not None, '')
    rec('[迁移] 迁移后默认 1 组 / 1 个提醒时间点',
        c and c['timeCount'] == 1 and '每天 1 组' in c['sub'], (c or {}).get('timeVals'))
    rec('[迁移] 无 JS 异常', not errs, str(errs[:2]))
    ctx.close()

    # ---------- 手机 ----------
    set_board(make_board())
    for wd in (390, 360):
        ctx, pg, errs = open_page(br, w=wd, h=844, mobile=True)
        pg.evaluate("() => { document.querySelector('[data-nav=\"breathe\"]').click(); }")
        pg.wait_for_timeout(700)
        c = pg.evaluate(PAGE)
        rec('[手机 %d] 无横向溢出' % wd, c['ovf'] <= 1, 'ovf=%d' % c['ovf'])
        rec('[手机 %d] 四块都在' % wd,
            len(c['secTitles']) == 4 and c['benefitCount'] == 6 and c['timeCount'] == 3, str(c['secTitles']))
        rec('[手机 %d] 无 JS 异常' % wd, not errs, str(errs[:1]))
        if wd == 390:
            pg.screenshot(path='design/shots/breathe-mobile.png', full_page=True)
        ctx.close()

    br.close()

srv.shutdown()
ok = sum(1 for r in results if r[1])
print('\n478 页面验证：%d/%d 通过' % (ok, len(results)))
if ok != len(results):
    print('失败项：')
    for n, o, d in results:
        if not o: print('  -', n, '| ', d)
    sys.exit(1)
