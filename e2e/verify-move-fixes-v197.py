# -*- coding: utf-8 -*-
"""v197 运动模块修复回归：口径统一 / 范围起点 / 时间一致 / 距离日锁 / 添加记录归属 / 卡片目标

覆盖 docs/MOVE-FIX-PLAN-v196.md 里定的 7 条改动。
运行：python e2e/verify-move-fixes-v197.py
"""
import http.server
import json
import secrets
import socketserver
import threading
from datetime import datetime, timedelta, timezone

from playwright.sync_api import sync_playwright

DOC = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo'
USER = {'id': 1, 'email': 'test@example.com', 'display_name': '测试', 'is_admin': False}
sessions = {}
TODAY = datetime(2026, 10, 24)
D = TODAY.strftime('%Y-%m-%d')
YDAY = (TODAY - timedelta(days=1)).strftime('%Y-%m-%d')

def local_iso(dstr, hm):
    """真实数据里 at 是「本地时间转 UTC」的 ISO 串（saveMoveRecordForm 用 toISOString）"""
    dt = datetime.strptime(dstr + ' ' + hm, '%Y-%m-%d %H:%M')
    return dt.astimezone().astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


PASS = 0
FAIL = 0
FAILS = []


def chk(name, ok, detail=''):
    global PASS, FAIL
    if ok:
        PASS += 1
        print('  PASS  ' + name)
    else:
        FAIL += 1
        FAILS.append('%s << %s' % (name, detail))
        print('  FAIL  %s  << %s' % (name, detail))


def clear_modal(pg):
    """强制清掉弹窗容器 —— 测试里不想被上一个弹窗挡住下一步"""
    pg.evaluate("""() => {
      const r = document.querySelector('#modal-root');
      if (r) r.innerHTML = '';
      document.body.classList.remove('modal-open');
    }""")
    pg.wait_for_timeout(300)


def sports_of(key, name, tval, freq_n=1, per_day=1, fields=None, t_idx=0):
    return {'id': 'sp-' + key, 'key': key, 'name': name, 'icon': '🏃', 'color': '#b5733f',
            'tIdx': t_idx, 'tVal': tval, 'freqKind': 'daily', 'freqN': freq_n, 'perDay': per_day,
            'weekSel': [0, 1, 2, 3, 4, 5, 6], 'recMode': 'manual', 'fixedSteps': 1000,
            'startTime': '', 'fields': fields if fields is not None else [], 'strokePick': '',
            'notifyOn': True, 'channels': ['browser'],
            'createdAt': '2026-09-01T08:00:00Z', 'updatedAt': '2026-10-01T08:00:00Z'}


SPORTS = [
    sports_of('steps', '每日步数', 10000, 1, 1, ['distM']),
    sports_of('run', '跑步', 5, 2, 2, ['dur', 'dist', 'pace', 'heart'], 0),
    sports_of('rope', '跳绳', 15, 1, 1, ['dur', 'count'], 0),
]

SPORTS[0]['distLocked'] = {D: True}   # 今天已经补过距离（v197 的日锁）
# 第二个步数实例：同样锁着今天，但一条记录都没有 → reload 后可以重新打卡验锁
_sp2 = sports_of('steps', '午后步数', 10000, 1, 1, ['distM'])
_sp2['id'] = 'sp-steps2'
_sp2['distLocked'] = {D: True}
SPORTS.append(_sp2)
# 第三个步数实例：今天没锁 —— 作对照，用来证明「弹不弹」确实由 distLocked 决定
_sp3 = sports_of('steps', '晚间步数', 10000, 1, 1, ['distM'])
_sp3['id'] = 'sp-steps3'
_sp3['distLocked'] = {}
SPORTS.append(_sp3)

RECORDS = [
    # 今天的步数：一条正常 6000，一条「跳过未记录」但仍带 5200 步与 12061 米距离
    {'id': 'p1', 'sportId': 'sp-steps', 'key': 'steps', 'd': D, 'at': local_iso(D, '09:00'), 'hour': 9,
     'steps': 6000, 'distM': 0, 'recMode': 'manual', 'pending': False, 'skipped': False},
    {'id': 'p2', 'sportId': 'sp-steps', 'key': 'steps', 'd': D, 'at': local_iso(D, '20:24'), 'hour': 20,
     'steps': 5200, 'distM': 12061, 'recMode': 'manual', 'pending': False, 'skipped': True},
    # 今天的跑步：50 分钟 5 公里
    {'id': 'r1', 'sportId': 'sp-run', 'key': 'run', 'd': D, 'at': local_iso(D, '19:56'), 'hour': 19,
     'steps': 0, 'dur': 50, 'dist': 5, 'pace': '10:00', 'heart': 140,
     'pending': False, 'skipped': False},
    # 昨天有一条「还没填数据」的跑步记录（pending，跨天）
    {'id': 'yp', 'sportId': 'sp-run', 'key': 'run', 'd': YDAY, 'at': local_iso(YDAY, '19:00'), 'hour': 19,
     'steps': 0, 'dur': 0, 'dist': 0, 'pending': True, 'skipped': False},
]
# 跑步的历史记录：40 天前开始（步数没有历史 → 用来验「全部」范围按模式起点）
for i in range(40, 0, -1):
    ds = (TODAY - timedelta(days=i)).strftime('%Y-%m-%d')
    RECORDS.append({'id': 'h%d' % i, 'sportId': 'sp-run', 'key': 'run', 'd': ds,
                    'at': local_iso(ds, '19:00'), 'hour': 19, 'steps': 0, 'dur': 40, 'dist': 5,
                    'pace': '8:00', 'heart': 140, 'pending': False, 'skipped': False})

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


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=DOC, **kw)

    def log_message(self, *a):
        pass

    def _j(self, obj, status=200, extra=None):
        body = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        for k, v in (extra or {}).items():
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
        a = self.path.split('action=')[-1].split('&')[0]
        if a == 'status':
            return self._j({'ok': True, 'installed': True})
        if a == 'me':
            return self._j({'ok': True, 'user': sessions.get(self._sid()), 'csrf': 'x',
                            'registration_open': False, 'registration_mode': 'closed',
                            'need_invite': False, 'need_code': False, 'code_ready': False})
        if a == 'push_status':
            return self._j({'ok': True, 'enabled': False, 'webhook': '', 'sent_today': 0,
                            'last_sent': '', 'recent': []})
        if a == 'push_preview':
            return self._j({'ok': True, 'date': D, 'items': []})
        if a == 'mail_status':
            return self._j({'ok': True, 'crypto_ready': True, 'recipient': 'test@example.com',
                            'config': {'host': '', 'port': 465, 'secure': 'ssl', 'user': '', 'from': '',
                                       'name': '', 'hasSecret': False, 'enabled': False,
                                       'lastError': '', 'lastTestAt': ''}})
        if a == 'ics_status':
            return self._j({'ok': True, 'url': None})
        if a == 'load':
            return self._j({'ok': True, 'data': BOARD['data'], 'rev': BOARD['rev'],
                            'updated_at': 1792813000000})
        return self._j({'ok': False, 'error': '?'}, 404)

    def do_POST(self):
        if not self.path.startswith('/api.php'):
            self.send_response(405)
            self.end_headers()
            return
        a = self.path.split('action=')[-1].split('&')[0]
        n = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(n) or b'{}')
        if a == 'login':
            sid = secrets.token_hex(8)
            sessions[sid] = USER
            return self._j({'ok': True, 'user': USER, 'csrf': 'x', 'registration_open': False},
                           extra={'Set-Cookie': 'sid=' + sid + '; Path=/'})
        if a in ('save', 'force'):
            BOARD['data'] = body.get('data', BOARD['data'])
            BOARD['rev'] += 1
            return self._j({'ok': True, 'rev': BOARD['rev'], 'updated_at': 1792813000000})
        return self._j({'ok': False, 'error': '?'}, 404)


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


def main():
    srv = Server(('127.0.0.1', 0), Handler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    with sync_playwright() as pw:
        br = pw.chromium.launch(channel='chrome')
        ctx = br.new_context(viewport={'width': 1280, 'height': 1100})
        pg = ctx.new_page()
        errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.clock.install(time=datetime(2026, 10, 24, 22, 30, 0))
        pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
        pg.wait_for_timeout(400)
        pg.click('[data-act="cloud-login"]')
        pg.wait_for_timeout(400)
        pg.fill('input[name="email"]', 'test@example.com')
        pg.fill('input[name="password"]', 'test@example.com')
        pg.click('form.modal-card button[type="submit"]')
        pg.wait_for_timeout(2600)
        pg.evaluate("() => document.querySelector('[data-nav=\"move\"]').click()")
        pg.wait_for_timeout(1200)

        print('\n===== 1. 口径统一：跳过的步数照计，运动后数据不计 =====')
        pg.click('[data-act="move-stat-mode"][data-v="steps"]')
        pg.wait_for_timeout(400)
        pg.click('[data-act="move-stat-range"][data-v="today"]')
        pg.wait_for_timeout(700)
        stats_txt = pg.inner_text('.move-page')
        chk('KPI 累计步数含跳过的 5200 步（6000+5200=11200）',
            '11,200' in stats_txt, stats_txt[:400])
        chk('统计区仍写明「不计入时长」', '不计入时长' in stats_txt, stats_txt[:400])
        chk('记录质量里有「跳过未记录」且不为 0',
            '跳过未记录' in stats_txt and '0 次' not in
            stats_txt[stats_txt.find('跳过未记录'):stats_txt.find('跳过未记录') + 20],
            stats_txt[stats_txt.find('跳过未记录'):stats_txt.find('跳过未记录') + 30])
        chk('记录质量里有「还没填数据」', '还没填数据' in stats_txt, stats_txt[:400])

        print('\n===== 2. 「全部」范围按当前模式起点 =====')
        pg.click('[data-act="move-stat-mode"][data-v="run"]')
        pg.wait_for_timeout(400)
        pg.click('[data-act="move-stat-range"][data-v="all"]')
        pg.wait_for_timeout(800)
        lead = pg.inner_text('.move-page')
        chk('跑步 + 全部 = 按周分 5 个点（40 天 ≈ 6 周，取整后不为空）',
            '跑步 · 距离趋势' in lead, lead[:200])

        print('\n===== 3. 最近记录的时间与卡片日志一致 =====')
        rec_time = pg.evaluate("""() => {
          const rows = [...document.querySelectorAll('.stt-recs .rr')];
          const r = rows.find(x => x.innerText.includes('跑步'));
          return r ? r.querySelector('.dd').innerText.trim() : '';
        }""")
        # 原来这里用 hour 拼成 ":00"（19:00），现在跟卡片日志一样精确到分钟
        chk('最近记录精确到分钟（不是拼出来的整点）',
            ':' in rec_time and not rec_time.endswith(':00'), rec_time)

        print('\n===== 4. 卡片目标显示实际判定依据 =====')
        card_txt = pg.inner_text('.mv-card[data-id="sp-run"]')
        chk('跑步卡片目标写「每天 2 次」', '每天 2 次' in card_txt, card_txt[:200])
        chk('跑步卡片不再把距离目标当达标依据', '目标5 公里' not in card_txt.replace(' ', ''),
            card_txt[:200])

        print('\n===== 5. 补录距离后删记录 → 当天不能再补（距离日锁）=====')
        pg.click('[data-act="move-stat-mode"][data-v="steps"]')
        pg.wait_for_timeout(400)
        pg.click('[data-act="move-stat-range"][data-v="today"]')
        pg.wait_for_timeout(600)
        # 打开步数卡片的「今日任务记录」，删掉带距离的那条（p2）
        pg.locator('.mv-card[data-id="sp-steps"] [data-act="move-log"]').click()
        pg.wait_for_timeout(700)
        pg.on('dialog', lambda d: d.accept())
        # 「今日任务记录」的两个折叠区默认收起，删除按钮在里面 → 先展开
        for i in range(pg.locator('#modal-root .sp-fold').count()):
            box = pg.locator('#modal-root .sp-fold').nth(i)
            if not box.evaluate('e => e.open'):
                box.locator('summary').click()
                pg.wait_for_timeout(250)
        pg.locator('#modal-root [data-rec-del]').last.click()
        pg.wait_for_timeout(1500)
        if pg.locator('#modal-root [data-act="close-modal"]').count():
            pg.click('#modal-root [data-act="close-modal"]')
            pg.wait_for_timeout(500)
        clear_modal(pg)
        sp = [x for x in BOARD['data']['modules']['move']['sports'] if x.get('id') == 'sp-steps'][0]
        chk('距离日锁记在运动实例上（删记录也不清）',
            (sp.get('distLocked') or {}).get(D) is True, str(sp.get('distLocked')))
        # 再打一次卡、达标 → 自动弹补数据；当天已锁 → 不给距离输入框
        pg.locator('.mv-card[data-id="sp-steps"] [data-act="move-do"]').click()
        pg.wait_for_timeout(700)
        pg.locator('#move-record-form [name="steps"]').fill('12000')
        pg.click('#move-record-form button[type="submit"]')
        pg.wait_for_timeout(1300)
        if pg.locator('#move-record-form').count():
            chk('当天已锁：补数据弹窗不再给距离输入框',
                pg.locator('#move-record-form input[name="distM"]').count() == 0,
                str(pg.locator('#move-record-form input[name="distM"]').count()))
            chk('弹窗说明这一天已经补过',
                '补过' in pg.inner_text('#move-record-form'),
                pg.inner_text('#move-record-form')[:160])
            pg.keyboard.press('Escape')
            pg.wait_for_timeout(500)
        else:
            chk('达标后弹出补数据弹窗', False, '弹窗没打开')

        print('\n===== 6. 「＋添加记录」写所属运动 =====')
        clear_modal(pg)
        pg.click('[data-act="move-add-rec"]')
        pg.wait_for_timeout(600)
        chk('表单里有「属于哪个运动」下拉',
            pg.locator('#move-record-form select[name="sportId"]').count() == 1)
        pg.select_option('#move-record-form select[name="key"]', 'rope')
        pg.wait_for_timeout(400)
        pg.select_option('#move-record-form select[name="sportId"]', 'sp-rope')
        pg.wait_for_timeout(300)
        pg.fill('#move-record-form [name="d"]', YDAY)
        pg.locator('#move-record-form [name="dur"]').fill('20')
        pg.click('#move-record-form button[type="submit"]')
        pg.wait_for_timeout(1200)
        new_rec = [r for r in BOARD['data']['modules']['move']['records']
                   if r.get('d') == YDAY and r.get('key') == 'rope']
        chk('补录的记录存进去了（昨天 / 跳绳 / 20 分钟）',
            len(new_rec) == 1 and new_rec[0].get('dur') == 20, str(new_rec))
        chk('记录带着所属运动实例 id（sp-rope）',
            len(new_rec) == 1 and new_rec[0].get('sportId') == 'sp-rope',
            str(new_rec[0].get('sportId')) if new_rec else 'none')

        print('\n===== 7. 历史 pending 出现在待处理列表 =====')
        clear_modal(pg)
        chk('跑步卡片出现「待补」胶囊（跨天待填也有入口）',
            pg.locator('.mv-card[data-id="sp-run"] [data-act="move-rec"]').count() == 1,
            str(pg.locator('.mv-card[data-id="sp-run"] [data-act="move-rec"]').count()))
        pg.locator('.mv-card[data-id="sp-run"] [data-act="move-rec"]').click()
        pg.wait_for_timeout(800)
        if pg.locator('#modal-root').count():
            txt = pg.inner_text('#modal-root')
            chk('待处理列表标题是「待处理」', '待处理' in txt, txt[:120])
            chk('昨天那条 pending 出现在列表里', '昨天' in txt or '10-23' in txt, txt[:400])
        else:
            chk('待处理弹窗能打开', False, '没打开')

        print('\n===== 8. distLocked 存得住（编辑运动重写实例 → 上传 → 拉回 → 归一化后还在）=====')
        clear_modal(pg)
        # 编辑运动（保存会重写整个实例）→ 锁不能被冲掉
        pg.locator('.mv-card[data-id="sp-steps"] [data-act="move-edit"]').click()
        pg.wait_for_timeout(800)
        if pg.locator('#move-sport-form').count():
            pg.click('#move-sport-form button[type="submit"]')
            pg.wait_for_timeout(1200)
        else:
            pg.keyboard.press('Escape')
            pg.wait_for_timeout(400)
        sp2 = [x for x in BOARD['data']['modules']['move']['sports'] if x.get('id') == 'sp-steps'][0]
        chk('编辑运动后距离日锁仍在（实例被重写也不丢）',
            (sp2.get('distLocked') or {}).get(D) is True, str(sp2.get('distLocked')))
        # 刷新页面 → 云端拉回 → 归一化 → 仍应锁着（补数据弹窗不给距离输入框）
        pg.reload(wait_until='networkidle')
        pg.wait_for_timeout(1500)
        pg.evaluate("() => document.querySelector('[data-nav=\"move\"]').click()")
        pg.wait_for_timeout(1200)
        # 用「午后步数」这个实例（未达标、有打卡按钮），它的今天也已锁
        pg.locator('.mv-card[data-id="sp-steps2"] [data-act="move-do"]').click()
        pg.wait_for_timeout(700)
        pg.locator('#move-record-form [name="steps"]').fill('500')
        pg.click('#move-record-form button[type="submit"]')
        pg.wait_for_timeout(1300)
        chk('刷新后仍锁着：当天已补过 → 不再弹补数据弹窗（没有可补项）',
            pg.locator('#move-record-form').count() == 0,
            str(pg.locator('#move-record-form').count()))
        # 对照：另一个今天没锁的实例 → 照常弹补数据弹窗，且有距离输入框
        pg.locator('.mv-card[data-id="sp-steps3"] [data-act="move-do"]').click()
        pg.wait_for_timeout(700)
        pg.locator('#move-record-form [name="steps"]').fill('12000')
        pg.click('#move-record-form button[type="submit"]')
        pg.wait_for_timeout(1300)
        chk('对照实例（今天没锁）照常弹补数据弹窗',
            pg.locator('#move-record-form').count() == 1,
            str(pg.locator('#move-record-form').count()))
        if pg.locator('#move-record-form').count():
            chk('对照实例有距离输入框（说明弹不弹确实由 distLocked 决定）',
                pg.locator('#move-record-form input[name="distM"]').count() == 1,
                str(pg.locator('#move-record-form input[name="distM"]').count()))

        print('\n===== 9. 无 JS 报错 =====')
        chk('无未捕获异常', not errs, str(errs[:3]))
        br.close()

    print('\n' + '=' * 60)
    print('v197 运动修复回归：%d 通过 / %d 失败' % (PASS, FAIL))
    for f in FAILS:
        print('  FAIL: ' + f)
    return 1 if FAIL else 0


if __name__ == '__main__':
    raise SystemExit(main())
