"""478 呼吸卡验证：波形 / 建议时间文案 / 四轮弹窗 / 中途关闭不记 / 转正计入达标率"""
import http.server, threading, json, socketserver, secrets, sys
from datetime import datetime
from playwright.sync_api import sync_playwright

DOC = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo'
USER = {'id': 1, 'email': 'test@example.com', 'display_name': '测试', 'is_admin': False}
sessions = {}
PORT = 38554
D = '2026-10-24'

OTHER = [
    {'id': 'h_med', 'name': '用药', 'icon': '💊', 'type': 'build', 'target': 1, 'unit': '次',
     'color': '#2f6f5e', 'note': '', 'createdAt': '2026-10-01T00:00:00Z', 'pinned': True, 'med': True, 'archivedAt': ''},
    {'id': 'h_water', 'name': '喝水', 'icon': '💧', 'type': 'build', 'target': 9, 'unit': '杯',
     'color': '#4c7f96', 'note': '', 'perMl': 250, 'goalMl': 2300, 'createdAt': '2026-10-01T00:00:00Z', 'pinned': True, 'archivedAt': ''},
]

def breathe(**kw):
    h = {'id': 'h_breathe', 'name': '478呼吸法', 'icon': '🌬️', 'type': 'build', 'target': 1, 'unit': '组',
         'color': '#5b8f8a', 'note': '4-7-8 呼吸', 'breatheCycles': 4, 'suggestTime': '15:00',
         'createdAt': '2026-10-01T00:00:00Z', 'pinned': True, 'archivedAt': ''}
    h.update(kw)
    return h

def make_board(breathe_done=False, legacy=False):
    bh = breathe()
    if legacy:
        bh['optional'] = True
        bh.pop('suggestTime', None)
        bh.pop('breatheCycles', None)
    checks = {'2026-10-22': {'h_breathe': 1}, '2026-10-23': {'h_breathe': 1}}
    if breathe_done:
        checks[D] = {'h_breathe': 1}
    data = {'version': 2, 'view': 'today', 'habits': [bh] + OTHER,
            'checks': checks, 'notes': {}, 'moods': {}, 'events': [], 'meds': [], 'doses': {},
            'bodyProfile': {'age': 30, 'height': 170}, 'weights': [], 'essays': [], 'tasks': []}
    return {'data': data, 'rev': 5}

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

CARD = """() => {
  const card = document.querySelector('.vital-card.breathing-card');
  if (!card) return null;
  const q = s => card.querySelector(s);
  const path = q('.breath-wave path');
  return {
    small: (q('.vital-title small') || {}).textContent || '',
    status: (q('.breath-status') || {}).textContent || '',
    sub: (q('.vital-sub') || {}).textContent || '',
    cap: (q('.breath-wave-cap') || {}).textContent.replace(/\\s+/g, ' ').trim(),
    foot: (q('.breath-foot') || {}).textContent.replace(/\\s+/g, ' ').trim(),
    dLen: path ? (path.getAttribute('d') || '').split('C').length - 1 : 0,
    stroke: path ? getComputedStyle(path).stroke : '',
    done: card.classList.contains('is-done'),
    warm: card.classList.contains('is-warm'),
    acts: [...card.querySelectorAll('.vital-actions button')].map(b => b.textContent.trim()),
    h: Math.round(card.getBoundingClientRect().height),
    ovf: document.documentElement.scrollWidth - innerWidth
  };
}"""

def open_page(br, w=1440, h=980, at=None, mobile=False):
    kw = {'viewport': {'width': w, 'height': h}}
    if mobile: kw.update({'is_mobile': True, 'has_touch': True, 'device_scale_factor': 2})
    ctx = br.new_context(**kw)
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.clock.install(time=at or datetime(2026, 10, 24, 14, 0, 0))
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

    # ---------- 14:00 建议之前 ----------
    board.update(make_board())
    ctx, pg, errs = open_page(br, at=datetime(2026, 10, 24, 14, 0, 0))
    c = pg.evaluate(CARD)
    rec('呼吸卡渲染', c is not None, '')
    rec('副标题 每天一组 · 4 次循环 · 约 1 分 16 秒',
        c['small'].strip() == '每天一组 · 4 次循环 · 约 1 分 16 秒', c['small'])
    rec('状态 还没开始', c['status'] == '还没开始', c['status'])
    rec('文案含 14:00 与 还有 1 小时', '14:00' in c['sub'] and '还有 1 小时' in c['sub'], c['sub'])
    rec('波形 4 个周期（8 段贝塞尔）', c['dLen'] == 8, '%d 段' % c['dLen'])
    rec('波形标注 ×4 次循环 + 比例', '×4 次循环' in c['cap'] and '吸 4 · 屏 7 · 呼 8' in c['cap'], c['cap'])
    rec('底部本周 2 / 7 天', '2 / 7' in c['foot'], c['foot'])
    rec('未完成也显示累计组数', '累计 2 组' in c['foot'], c['foot'])
    rec('按钮 开始练习 + 撤销', c['acts'] == ['开始练习', '撤销'], str(c['acts']))
    rec('未完成不是 is-warm', not c['warm'] and not c['done'], 'warm=%s' % c['warm'])
    pg.screenshot(path='design/shots/breath-before.png')
    ctx.close()

    # ---------- 15:30 建议时段内 ----------
    board.update(make_board())
    ctx, pg, errs = open_page(br, at=datetime(2026, 10, 24, 15, 30, 0))
    c = pg.evaluate(CARD)
    rec('[15:30] 状态 现在正好', c['status'] == '现在正好', c['status'])
    rec('[15:30] 卡片带 is-warm', c['warm'], '')
    rec('[15:30] 文案说到建议时段', '正是建议的 15:00 时段' in c['sub'], c['sub'])
    pg.screenshot(path='design/shots/breath-warm.png')
    ctx.close()

    # ---------- 16:30 已过建议时间 ----------
    board.update(make_board())
    ctx, pg, errs = open_page(br, at=datetime(2026, 10, 24, 16, 30, 0))
    c = pg.evaluate(CARD)
    rec('[16:30] 状态 还没开始', c['status'] == '还没开始', c['status'])
    rec('[16:30] 文案 睡前补上也有用', '睡前补上也有用' in c['sub'], c['sub'])
    rec('[16:30] 不再是 warm', not c['warm'], '')
    ctx.close()

    # ---------- 已完成 ----------
    board.update(make_board(breathe_done=True))
    ctx, pg, errs = open_page(br, at=datetime(2026, 10, 24, 16, 30, 0))
    c = pg.evaluate(CARD)
    rec('[完成] 状态 今天已完成', c['status'] == '今天已完成', c['status'])
    rec('[完成] 卡片 is-done', c['done'], '')
    rec('[完成] 波形用主题色', c['stroke'] == 'rgb(91, 143, 138)', c['stroke'])
    rec('[完成] 底部有累计组数', '累计' in c['foot'], c['foot'])
    rec('[完成] 按钮可撤销', c['acts'] == ['已完成 · 点击可撤销'], str(c['acts']))
    pg.screenshot(path='design/shots/breath-done.png')
    ctx.close()

    # ---------- 弹窗四轮 + 中途关闭 ----------
    board.update(make_board())
    ctx, pg, errs = open_page(br, at=datetime(2026, 10, 24, 14, 0, 0))
    pg.click('[data-act="breathing-start"][data-id="h_breathe"]'); pg.wait_for_timeout(500)
    note = pg.evaluate("() => (document.querySelector('.breathing-note') || {}).textContent || ''")
    rec('弹窗说明写到 4 次循环与总时长', '4 次循环' in note and '1 分 16 秒' in note, note)
    pg.click('#breathing-start-btn'); pg.wait_for_timeout(300)
    t1 = pg.evaluate("() => (document.querySelector('#breathing-timer') || {}).textContent || ''")
    rec('开始后显示 第 1 / 4 次', '第 1 / 4 次' in t1, t1)

    # 跑完第 1 轮（19 秒 + 250ms 间隔）
    pg.clock.run_for(20000); pg.wait_for_timeout(300)
    t2 = pg.evaluate("() => (document.querySelector('#breathing-timer') || {}).textContent || ''")
    rec('一轮之后进入 第 2 / 4 次', '第 2 / 4 次' in t2, t2)

    # 中途关闭：回到页面检查仍未记
    pg.click('[data-act="close-modal"]'); pg.wait_for_timeout(600)
    c = pg.evaluate(CARD)
    rec('中途关闭不记录', c['status'] == '还没开始' and not c['done'], c['status'])

    # 完整跑 4 轮
    base = save_count['n']
    pg.click('[data-act="breathing-start"][data-id="h_breathe"]'); pg.wait_for_timeout(500)
    pg.click('#breathing-start-btn'); pg.wait_for_timeout(300)
    pg.clock.run_for(80000); pg.wait_for_timeout(900)
    phase = pg.evaluate("() => (document.querySelector('#breathing-phase') || {}).textContent || ''")
    rec('跑满 4 轮后弹窗显示完成', '完成' in phase and '4 次循环' in phase, phase)
    pg.click('[data-act="close-modal"]'); pg.wait_for_timeout(700)
    c = pg.evaluate(CARD)
    rec('完整一组后卡片变已完成', c['status'] == '今天已完成' and c['done'], c['status'])
    rec('只写入云端 1 次（一组 = 1 次记录）', save_count['n'] - base == 1, '%d 次' % (save_count['n'] - base))
    rec('无 JS 异常', not errs, str(errs[:2]))
    ctx.close()

    # ---------- 旧数据迁移：optional 转正 + 补字段 ----------
    old = make_board(legacy=True)
    old['data']['habits'] = [old['data']['habits'][0]]
    old['data']['checks'] = {D: {'h_breathe': 1}}
    board.update(old)
    ctx, pg, errs = open_page(br, at=datetime(2026, 10, 24, 14, 0, 0))
    c = pg.evaluate(CARD)
    rec('[迁移] 旧 optional 卡仍按呼吸卡渲染', c['small'].startswith('每天一组 · 4 次循环'), c['small'])
    rec('[迁移] 完成态文案正常', '4 次循环跑完了' in c['sub'], c['sub'])
    pct = pg.evaluate("() => (document.querySelector('.hero-pct b') || {}).textContent || ''")
    rec('[迁移] 已计入达标率（1/1 = 100%）', pct.strip() == '100%', pct)
    ctx.close()

    # ---------- 手机 ----------
    board.update(make_board())
    for wd in (390, 360):
        ctx, pg, errs = open_page(br, w=wd, h=844, mobile=True, at=datetime(2026, 10, 24, 14, 0, 0))
        c = pg.evaluate(CARD)
        rec('[手机 %d] 无横向溢出' % wd, c['ovf'] <= 1, 'ovf=%d' % c['ovf'])
        rec('[手机 %d] 波形 4 周期仍在' % wd, c['dLen'] == 8, '%d 段' % c['dLen'])
        rec('[手机 %d] 无 JS 异常' % wd, not errs, str(errs[:1]))
        if wd == 390:
            pg.screenshot(path='design/shots/breath-mobile.png')
        ctx.close()

    br.close()

srv.shutdown()
ok = sum(1 for r in results if r[1])
print('\n呼吸卡验证：%d/%d 通过' % (ok, len(results)))
if ok != len(results):
    print('失败项：')
    for n, o, d in results:
        if not o: print('  -', n, '|', d)
    sys.exit(1)
