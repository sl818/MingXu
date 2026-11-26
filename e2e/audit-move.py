# -*- coding: utf-8 -*-
"""运动页对比度复核（WCAG AA）· 单主题 · 浅色 / 深色

为什么重写（v190）：
    旧版是「6 皮肤 × 明暗」时代写的，脚本里还列着 paper / slate / mono / clay /
    mist / forest / neu / cyber / retro 九套皮肤 —— 这些皮肤早已删除，只剩
    「暖纸 / 白卡 / 一支红」一套主题 + 深色。数据也停在 habits + checks + events，
    而运动早已搬到 state.modules.move.sports / records，跑起来运动卡根本不出现。

现在覆盖：
    · 运动卡片四种状态（未开始 / 等记录数据 / 已完成 / 跳过后的「待补 N」胶囊）
    · 今日任务记录弹窗（运动日志 + 运动后数据两个折叠区展开后）
    · 数据统计区（模式/范围 chips、KPI、趋势、热力图、周内分布、时段、专项、记录质量）

用法：python e2e/audit-move.py
退出码：0 = 全部达标；1 = 有元素低于 AA
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
D = '2026-10-24'
sessions = {}

SPORTS = [
    {'id': 's-step', 'key': 'steps', 'name': '每日步数', 'icon': '👟', 'color': '#4c7f96', 'tIdx': 0,
     'tVal': 10000, 'freqKind': 'daily', 'freqN': 1, 'perDay': 1, 'weekSel': [0, 1, 2, 3, 4, 5, 6],
     'recMode': 'manual', 'fixedSteps': 1000, 'startTime': '', 'fields': ['distM'], 'strokePick': '',
     'notifyOn': True, 'channels': ['browser'],
     'createdAt': '2026-09-01T08:00:00Z', 'updatedAt': '2026-10-01T08:00:00Z'},
    {'id': 's-run', 'key': 'run', 'name': '跑步', 'icon': '🏃', 'color': '#b5733f', 'tIdx': 0,
     'tVal': 3, 'freqKind': 'daily', 'freqN': 2, 'perDay': 2, 'weekSel': [0, 1, 2, 3, 4, 5, 6],
     'recMode': 'manual', 'fixedSteps': 1000, 'startTime': '', 'fields': ['dur', 'dist', 'pace', 'heart'],
     'strokePick': '', 'notifyOn': True, 'channels': ['browser'],
     'createdAt': '2026-09-01T08:00:00Z', 'updatedAt': '2026-10-01T08:00:00Z'},
    {'id': 's-walk', 'key': 'walk', 'name': '健走', 'icon': '🚶', 'color': '#7a9d6b', 'tIdx': 0,
     'tVal': 3, 'freqKind': 'daily', 'freqN': 1, 'perDay': 1, 'weekSel': [0, 1, 2, 3, 4, 5, 6],
     'recMode': 'manual', 'fixedSteps': 1000, 'startTime': '', 'fields': ['dur', 'dist', 'pace'],
     'strokePick': '', 'notifyOn': True, 'channels': ['browser'],
     'createdAt': '2026-09-01T08:00:00Z', 'updatedAt': '2026-10-01T08:00:00Z'},
]

RECORDS = [
    # 步数：今天 2 条，累计达标（6000 + 5200 > 10000），带补录距离
    {'id': 'p1', 'sportId': 's-step', 'key': 'steps', 'd': D, 'at': D + 'T09:20:00Z', 'hour': 9,
     'steps': 6000, 'distM': 0, 'recMode': 'manual', 'pending': False, 'skipped': False},
    {'id': 'p2', 'sportId': 's-step', 'key': 'steps', 'd': D, 'at': D + 'T21:40:00Z', 'hour': 21,
     'steps': 5200, 'distM': 12061, 'recMode': 'manual', 'pending': False, 'skipped': False},
    # 跑步：第 1 次已记录，第 2 次跳过（卡片出现「待补 1」胶囊）
    {'id': 'r1', 'sportId': 's-run', 'key': 'run', 'd': D, 'at': D + 'T19:56:00Z', 'hour': 19,
     'steps': 0, 'dur': 50, 'dist': 3, 'pace': '5:20', 'heart': 126,
     'pending': False, 'skipped': False},
    {'id': 'r2', 'sportId': 's-run', 'key': 'run', 'd': D, 'at': D + 'T21:30:00Z', 'hour': 21,
     'steps': 0, 'dur': 0, 'dist': 0, 'pending': False, 'skipped': True},
    # 健走：打卡后还没填数据（卡片进入「等记录这一次的数据」）
    {'id': 'w1', 'sportId': 's-walk', 'key': 'walk', 'd': D, 'at': D + 'T07:10:00Z', 'hour': 7,
     'steps': 0, 'dur': 0, 'dist': 0, 'pending': True, 'skipped': False},
]
# 历史记录：让统计区的趋势 / 热力图 / 周内分布有东西可画
for i in range(1, 40):
    day = '2026-%02d-%02d' % (9 + (i // 28), (i % 28) + 1)
    RECORDS.append({'id': 'h%d' % i, 'sportId': 's-run', 'key': 'run', 'd': day,
                    'at': day + 'T19:00:00Z', 'hour': 19, 'steps': 0,
                    'dur': 30 + (i % 25), 'dist': 4 + (i % 4), 'pace': '5:%02d' % (10 + i % 40),
                    'heart': 130 + (i % 20), 'pending': False, 'skipped': i % 11 == 0})

BOARD = {'data': {
    'version': 2, 'schemaVersion': 2, 'view': 'today', 'habits': [],
    'modules': {'move': {
        'on': True, 'name': '运动', 'icon': '🏃', 'color': '#b5733f', 'note': '',
        'unit': '次', 'times': 1, 'sports': SPORTS, 'records': RECORDS,
        'notifyChannels': ['browser'], 'notify': True,
        'notifyScenes': {'steps': True, 'plan': True, 'week': True},
        'suggestTime': '', 'notifyFreq': 'daily', 'notifyWeekday': 1, 'notifyMonthday': 1,
        'notifyNote': '', 'createdAt': '2026-09-01T08:00:00Z', 'updatedAt': '2026-10-01T08:00:00Z'}},
    'modulesAt': 0, 'checks': {}, 'skips': {}, 'notes': {}, 'moods': {}, 'events': [],
    'meds': [], 'doses': {}, 'bodyProfile': {'age': 30, 'height': 170},
    'weights': [], 'essays': [], 'tasks': [], 'money': {}, 'quit': {}}, 'rev': 3}

# 需要复核的元素（选择器 → 说明）
SELS = [
    '.mv-card .mv-title b', '.mv-card .mv-title small', '.mv-card .mv-tag',
    '.mv-card .mv-pill', '.mv-card .mv-pill b',
    '.mv-st', '.mv-st.ok', '.mv-st.pend', '.mv-st.rest', '.mv-note',
    '.mv-ft', '.mv-ft b', '.mv-rc b', '.mv-rc span',
    '.mv-btn', '.mv-btn.done', '.mv-btn.ghost', '.mv-btn.ghost.danger',
    '.sp-hint', '.sp-desc',
    '#modal-root .sp-fold-t', '#modal-root .sp-fold-n',
    '#modal-root .sp-logrow .idx', '#modal-root .sp-logrow .st', '#modal-root .sp-logrow .st.bad',
    '#modal-root .sp-logrow .oktag', '#modal-root .sp-logrow .tm',
    '#modal-root .sp-recfield .k', '#modal-root .sp-recfield .v', '#modal-root .sp-recfield.is-empty',
    '#modal-root .sp-dataitem-h b', '#modal-root .sp-datafoot',
    '.stt-chip', '.stt-chip.on', '.stt-chip.sm',
    '.stt-range', '.stt-kpi b', '.stt-kpi b small', '.stt-kpi span', '.stt-delta.up', '.stt-delta.down',
    '.stt-ax', '.stt-legend', '.stt-wl span', '.stt-cell',
    '.stt-bar b', '.stt-bar span', '.stt-rank .nm', '.stt-rank .vl', '.stt-tag',
    '.stt-dist .nm', '.stt-dist .vl', '.stt-spec h4', '.stt-spec .kv', '.stt-spec .kv b',
    '.stt-q .q', '.stt-q .q b', '.stt-recs .dd', '.stt-recs .vv', '.stt-recs .nm',
    '.stt-ring .rc b', '.stt-ring .rc span', '.stt-none',
]

JS_CONTRAST = r"""
(sels) => {
  const lum = (c) => {
    const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]);
  };
  const ratio = (a, b) => {
    const l1 = lum(a), l2 = lum(b);
    return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
  };
  const parse = (s) => {
    const m = String(s || '').match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const p = m[1].split(',').map((x) => parseFloat(x));
    return { c: [p[0], p[1], p[2]], a: p.length > 3 ? p[3] : 1 };
  };
  const bgOf = (el) => {
    let n = el;
    while (n && n !== document.documentElement) {
      const p = parse(getComputedStyle(n).backgroundColor);
      if (p && p.a > 0.5) return p.c;
      n = n.parentElement;
    }
    const b = parse(getComputedStyle(document.body).backgroundColor);
    return b ? b.c : [255, 255, 255];
  };
  const out = [];
  let skipped = 0;
  sels.forEach((sel) => {
    document.querySelectorAll(sel).forEach((el) => {
      const r = el.getBoundingClientRect();
      if (!r.width || !r.height) { skipped++; return; }
      /* 纯色块（热力图格子）没有文字，量它的前景色没有意义 */
      if (!(el.textContent || '').trim()) { skipped++; return; }
      const cs = getComputedStyle(el);
      if (cs.visibility === 'hidden' || cs.display === 'none') { skipped++; return; }
      if (parseFloat(cs.opacity) < 0.2) { skipped++; return; }
      const fg = parse(cs.color);
      if (!fg) { skipped++; return; }
      const size = parseFloat(cs.fontSize) || 14;
      const bold = (parseInt(cs.fontWeight, 10) || 400) >= 600;
      const big = size >= 24 || (bold && size >= 18.66);
      const cr = ratio(fg.c, bgOf(el));
      const need = big ? 3.0 : 4.5;
      out.push({
        sel: sel,
        txt: (el.textContent || '').trim().slice(0, 18),
        ratio: Math.round(cr * 100) / 100,
        need: need,
        size: Math.round(size * 10) / 10,
        ok: cr >= need - 0.005
      });
    });
  });
  return { items: out, skipped: skipped };
}
"""


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=DOC, **kw)

    def log_message(self, *a):
        pass

    def _j(self, obj, status=200, extra_headers=None):
        body = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        for k, v in (extra_headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _sid(self):
        for part in (self.headers.get('Cookie', '') or '').split(';'):
            part = part.strip()
            if part.startswith('sid='):
                return part[4:]
        return ''

    def do_GET(self):
        if not self.path.startswith('/api.php'):
            return super().do_GET()
        action = self.path.split('action=')[-1].split('&')[0]
        if action == 'status':
            return self._j({'ok': True, 'installed': True})
        if action == 'me':
            return self._j({'ok': True, 'user': sessions.get(self._sid()), 'csrf': 'x',
                            'registration_open': False, 'registration_mode': 'closed',
                            'need_invite': False, 'need_code': False, 'code_ready': False})
        if action == 'push_status':
            return self._j({'ok': True, 'enabled': False, 'webhook': '', 'sent_today': 0,
                            'last_sent': '', 'recent': []})
        if action == 'push_preview':
            return self._j({'ok': True, 'date': D, 'items': []})
        if action == 'mail_status':
            return self._j({'ok': True, 'crypto_ready': True, 'recipient': 'test@example.com',
                            'config': {'host': '', 'port': 465, 'secure': 'ssl', 'user': '', 'from': '',
                                       'name': '', 'hasSecret': False, 'enabled': False,
                                       'lastError': '', 'lastTestAt': ''}})
        if action == 'ics_status':
            return self._j({'ok': True, 'url': None})
        if action == 'load':
            return self._j({'ok': True, 'data': BOARD['data'], 'rev': BOARD['rev'],
                            'updated_at': 1792813000000})
        return self._j({'ok': False, 'error': 'unknown action'}, 404)

    def do_POST(self):
        if not self.path.startswith('/api.php'):
            self.send_response(405)
            self.end_headers()
            return
        action = self.path.split('action=')[-1].split('&')[0]
        length = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(length) or b'{}')
        if action == 'login':
            sid = secrets.token_hex(8)
            sessions[sid] = USER
            return self._j({'ok': True, 'user': USER, 'csrf': 'x', 'registration_open': False},
                           extra_headers={'Set-Cookie': 'sid=' + sid + '; Path=/'})
        if action in ('save', 'force'):
            BOARD['data'] = body.get('data', BOARD['data'])
            BOARD['rev'] += 1
            return self._j({'ok': True, 'rev': BOARD['rev'], 'updated_at': 1792813000000})
        return self._j({'ok': False, 'error': 'unknown action'}, 404)


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


def run_theme(browser, port, theme):
    ctx = browser.new_context(viewport={'width': 1280, 'height': 1000})
    pg = ctx.new_page()
    errors = []
    pg.on('pageerror', lambda e: errors.append(str(e)))
    pg.clock.install(time=datetime(2026, 10, 24, 22, 30, 0))
    pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
    pg.wait_for_timeout(400)
    pg.click('[data-act="cloud-login"]')
    pg.wait_for_timeout(400)
    pg.fill('input[name="email"]', 'test@example.com')
    pg.fill('input[name="password"]', 'test@example.com')
    pg.click('form.modal-card button[type="submit"]')
    pg.wait_for_timeout(2600)
    pg.evaluate("() => { document.documentElement.dataset.theme = '%s'; }" % theme)
    pg.evaluate("() => document.querySelector('[data-nav=\"move\"]').click()")
    pg.wait_for_timeout(900)

    results = []

    def audit(tag):
        r = pg.evaluate(JS_CONTRAST, SELS)
        for item in r['items']:
            item['tag'] = tag
        results.extend(r['items'])
        return r

    audit('运动卡片')

    # 今日任务记录：两个折叠区都展开，才能量到日志行与数据行的颜色
    pg.locator('.mv-card[data-id="s-run"] [data-act="move-log"]').click()
    pg.wait_for_timeout(600)
    for i in range(pg.locator('#modal-root .sp-fold').count()):
        box = pg.locator('#modal-root .sp-fold').nth(i)
        if not box.evaluate('e => e.open'):
            box.locator('summary').click()
            pg.wait_for_timeout(220)
    audit('任务记录弹窗')
    pg.click('#modal-root [data-act="close-modal"]')
    pg.wait_for_timeout(400)

    # 统计区：切到「全部」+ 近 30 天，确保 KPI / 专项都在
    pg.click('[data-act="move-stat-mode"][data-v=""]')
    pg.wait_for_timeout(400)
    pg.click('[data-act="move-stat-range"][data-v="30d"]')
    pg.wait_for_timeout(500)
    audit('数据统计')

    # 窄屏也要量一次（KPI 与按钮会换行，字号不变但底色可能变）
    pg.set_viewport_size({'width': 390, 'height': 900})
    pg.wait_for_timeout(500)
    audit('数据统计（手机）')

    skipped = 0
    ctx.close()
    return results, skipped, errors


def main():
    srv = Server(('127.0.0.1', 0), Handler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    all_rows = []
    all_errs = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel='chrome')
        for theme in ('light', 'dark'):
            rows, _sk, errs = run_theme(browser, port, theme)
            for r in rows:
                r['theme'] = theme
            all_rows.extend(rows)
            all_errs.extend(errs)
        browser.close()

    bad = [r for r in all_rows if not r['ok']]
    uniq_sels = sorted({r['sel'] + '|' + r['theme'] for r in all_rows})
    print('=' * 64)
    print('运动页对比度复核（WCAG AA）· 浅色 + 深色 · 共 %d 处元素 / %d 个组合' % (len(all_rows), len(uniq_sels)))
    print('=' * 64)
    if all_errs:
        print('JS 报错 %d 条：' % len(all_errs))
        for e in all_errs[:5]:
            print('  ! ' + e)
    if not bad:
        print('全部达标：没有元素低于 AA。')
        print('（大字按 3.0、正文按 4.5 判定；隐藏/零尺寸元素已跳过）')
        return 0

    print('低于 AA 的元素 %d 处：' % len(bad))
    for r in sorted(bad, key=lambda x: x['ratio']):
        print('  [%s/%s] %-34s %5.2f < %.1f  %s · %spx · %s'
              % (r['theme'], r['tag'], r['sel'], r['ratio'], r['need'], r['txt'], r['size'], '粗' if r['size'] >= 18.66 else ''))
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
