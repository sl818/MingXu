# -*- coding: utf-8 -*-
"""通知路由页（v211）：页面入口、板块矩阵、模块派生、模板编辑、真实数据列表、旧入口移除。

运行：
  python e2e/verify-notify-route.py
"""
import json
import secrets
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PASS = 0
FAIL = 0
FAILS = []


def chk(name, ok, detail=''):
    global PASS, FAIL
    if ok:
        PASS += 1
        print('  ✓ %s' % name)
    else:
        FAIL += 1
        FAILS.append(name)
        print('  ✗ %s  << %s' % (name, detail))


USER = {'id': 1, 'email': 'test@example.com', 'name': '测试'}
sessions = {}
board = {
    'data': {
        'habits': [], 'tasks': [], 'meds': [], 'checks': {}, 'doses': {},
        'modules': {'water': {'on': True}, 'move': {'on': True}, 'breathe': {'on': True}, 'quit': {'on': False}},
        'modulePrefs': {'meds': {'on': True}},
    },
    'rev': 1,
}
SAVED = {'prefs': None, 'templates': None}

BOARDS = {
    'med': {'channels': {'wecom': True, 'mail': True, 'browser': True}},
    'water': {'channels': {'wecom': True, 'mail': False, 'browser': False}},
    'move': {'channels': {'wecom': True, 'mail': False, 'browser': False}},
    'breathe': {'channels': {'wecom': True, 'mail': False, 'browser': False}},
    'quit': {'channels': {'wecom': False, 'mail': False, 'browser': False}},
    'task': {'on': True, 'channels': {'wecom': True, 'mail': True, 'browser': True}},
    'habit': {'on': True, 'channels': {'wecom': True, 'mail': False, 'browser': True}},
    'notice': {'on': True, 'channels': {'wecom': True, 'mail': True, 'browser': True}},
    'countdown': {'on': True, 'channels': {'wecom': True, 'mail': True, 'browser': True}},
    'debt': {'on': True, 'channels': {'wecom': True, 'mail': True, 'browser': False}},
    'report': {'on': True, 'channels': {'wecom': True, 'mail': False, 'browser': True}},
}
SCENES = {k: {'title': '{标题}' if k not in ('med', 'task') else ('该吃药了' if k == 'med' else '该做这件事了'),
              'body': '{正文}', 'browser': '{浏览器文案}'}
          for k in ('med', 'task', 'habit', 'water', 'move', 'breathe', 'report', 'notice', 'countdown', 'debt', 'test')}


class H(SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _j(self, o, s=200):
        b = json.dumps(o, ensure_ascii=False).encode()
        self.send_response(s)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _sid(self):
        for p in (self.headers.get('Cookie', '') or '').split(';'):
            p = p.strip()
            if p.startswith('sid='):
                return p[4:]

    def do_GET(self):
        if not self.path.startswith('/api.php'):
            return super().do_GET()
        a = self.path.split('action=')[-1].split('&')[0]
        if a == 'status':
            self._j({'ok': True, 'installed': True})
        elif a == 'me':
            self._j({'ok': True, 'user': sessions.get(self._sid()), 'csrf': 'x'})
        elif a == 'push_status':
            self._j({'ok': True, 'enabled': False, 'webhook': '', 'sent_today': 0, 'recent': []})
        elif a == 'mail_status':
            self._j({'ok': True, 'config': {'enabled': False, 'hasSecret': False}})
        elif a == 'push_preview':
            self._j({'ok': True, 'date': '2026-11-27', 'items': [
                {'id': 'm1', 'time': '08:00', 'kind': 'med', 'source': 'med', 'priority': '紧急',
                 'title': '该吃药了', 'body': '阿莫西林 1片'},
                {'id': 't1', 'time': '09:00', 'kind': 'task', 'source': 'task', 'priority': '当日',
                 'title': '该做这件事了', 'body': '交周报'},
                {'id': 'h_water', 'time': '10:30', 'kind': 'habit', 'source': 'water', 'priority': '日常',
                 'title': '喝水', 'body': '今天还差 4 杯'},
                {'id': 'c1', 'time': '12:00', 'kind': 'countdown', 'source': 'countdown', 'priority': '当日',
                 'title': '生日', 'body': '还有 3 天'},
                {'id': 'n1', 'time': '15:00', 'kind': 'notice', 'source': 'notice', 'priority': '当日',
                 'title': '自定义提醒', 'body': '去取快递'},
                {'id': 'r1', 'time': '20:00', 'kind': 'report', 'source': 'report', 'priority': '日常',
                 'title': '今日小结', 'body': '今日完成 2 项'},
            ]})
        elif a == 'notify_prefs':
            self._j({'ok': True, 'kinds': {'med': '用药提醒', 'task': '待办到点', 'habit': '习惯提醒',
                                          'countdown': '倒数日', 'notice': '自定义提醒',
                                          'debt': '还款提醒', 'report': '每日小结'},
                     'channels': {'wecom': '企业微信', 'mail': '邮件'},
                     'prefs': {k: {'wecom': True, 'mail': k not in ('habit', 'report')}
                               for k in ('med', 'task', 'habit', 'countdown', 'notice', 'debt', 'report')},
                     'quiet': False, 'quietCfg': {'on': False, 'start': '23:00', 'end': '07:00'},
                     'report': {'morning': '08:20', 'noon': '12:30', 'evening': '20:00'},
                     'boards': BOARDS, 'templates': {'scenes': SCENES,
                                                     'mail': {'color': 'blue', 'footer': '明序 · 个人生活提醒'}},
                     'global': True})
        elif a == 'load':
            self._j({'ok': True, 'data': board['data'], 'rev': board['rev'], 'updated_at': 1792813000000})
        elif a == 'ics_status':
            self._j({'ok': True, 'url': None})
        else:
            self._j({'ok': False, 'error': '?'}, 404)

    def do_POST(self):
        if not self.path.startswith('/api.php'):
            return super().do_POST()
        a = self.path.split('action=')[-1].split('&')[0]
        n = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(n) or b'{}')
        if a == 'login':
            sid = secrets.token_hex(8)
            sessions[sid] = USER
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            b = json.dumps({'ok': True, 'user': USER, 'csrf': 'x'}).encode()
            self.send_header('Content-Length', str(len(b)))
            self.send_header('Set-Cookie', 'sid=' + sid + '; Path=/')
            self.end_headers()
            self.wfile.write(b)
            return
        if a in ('save', 'force'):
            board['data'] = body['data']
            board['rev'] += 1
            self._j({'ok': True, 'rev': board['rev'], 'updated_at': 1792813000000})
        elif a == 'notify_prefs_save':
            SAVED['prefs'] = body
            self._j({'ok': True, 'prefs': {}, 'boards': BOARDS,
                     'quiet': False, 'quietCfg': body.get('quiet') or {'on': False},
                     'report': body.get('report') or {}})
        elif a == 'notify_templates_save':
            SAVED['templates'] = body
            self._j({'ok': True, 'templates': body.get('templates') or {}})
        else:
            self._j({'ok': False, 'error': '?'}, 404)


srv = ThreadingHTTPServer(('127.0.0.1', 0), lambda *a, **kw: H(*a, directory=str(ROOT), **kw))
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()

with sync_playwright() as pw:
    br = pw.chromium.launch(channel='chrome')
    pg = br.new_page(viewport={'width': 1440, 'height': 1000})
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
    pg.wait_for_timeout(500)
    pg.click('[data-act="cloud-login"]')
    pg.wait_for_timeout(400)
    pg.fill('input[name="email"]', 'test@example.com')
    pg.fill('input[name="password"]', 'test@example.com')
    pg.click('form.modal-card button[type="submit"]')
    pg.wait_for_timeout(2600)

    print('\n[1] 页面入口与基础结构')
    chk('导航有「通知路由」', pg.locator('[data-nav="notifyroute"]').count() == 1)
    pg.click('[data-nav="notifyroute"]')
    pg.wait_for_timeout(1200)
    chk('进入通知路由页', pg.evaluate("() => document.body.dataset.view") == 'notifyroute')
    chk('四个板块面板', pg.locator('.nr-panel').count() == 4, str(pg.locator('.nr-panel').count()))
    chk('板块表 11 行', pg.locator('.nr-table tbody tr').count() == 11, str(pg.locator('.nr-table tbody tr').count()))
    chk('模块类行标注「跟随功能模块开关」',
        pg.locator('.nr-table tbody tr', has_text='用药').first.inner_text().find('跟随功能模块') >= 0)
    chk('存在三渠道列', pg.locator('.nr-table thead th').count() == 5)

    print('\n[2] 板块开关与渠道')
    row_task = pg.locator('.nr-table tbody tr', has_text='待办').first
    chk('待办默认启用', 'off' not in (row_task.get_attribute('class') or ''))
    pg.click('[data-act="notify-board-toggle"][data-b="task"]')
    pg.wait_for_timeout(400)
    chk('点击后待办变停用',
        'off' in (pg.locator('.nr-table tbody tr', has_text='待办').first.get_attribute('class') or ''))
    pg.click('[data-act="notify-board-toggle"][data-b="task"]')
    pg.wait_for_timeout(400)
    chk('再点恢复启用',
        'off' not in (pg.locator('.nr-table tbody tr', has_text='待办').first.get_attribute('class') or ''))

    pg.click('[data-act="notify-board-ch"][data-b="task"][data-ch="mail"]')
    pg.wait_for_timeout(400)
    chk('邮件渠道取消勾选',
        'on' not in (pg.locator('[data-act="notify-board-ch"][data-b="task"][data-ch="mail"]').get_attribute('class') or ''))

    pg.click('[data-act="notify-board-toggle"][data-b="med"]')
    pg.wait_for_timeout(300)
    chk('模块类板块提示去功能模块页', '功能模块' in pg.locator('#toast').inner_text())

    print('\n[3] 免打扰与小结时刻')
    pg.click('[data-act="notify-quiet-toggle"]')
    pg.wait_for_timeout(400)
    chk('免打扰开关可切换', 'on' in (pg.locator('[data-act="notify-quiet-toggle"]').get_attribute('class') or ''))
    pg.fill('#nr-quiet-start', '22:30')
    pg.fill('#nr-quiet-end', '06:30')
    pg.click('[data-act="notify-route-save"]')
    pg.wait_for_timeout(900)
    chk('保存请求带 boards/quiet/report',
        SAVED['prefs'] is not None and 'boards' in SAVED['prefs'] and SAVED['prefs']['quiet']['start'] == '22:30',
        json.dumps(SAVED['prefs'], ensure_ascii=False)[:200])

    print('\n[3b] 全局总开关')
    chk('默认开启', 'on' in (pg.locator('[data-act="notify-global-toggle"]').get_attribute('class') or ''))
    pg.click('[data-act="notify-global-toggle"]')
    pg.wait_for_timeout(1000)
    chk('关闭后保存请求 global=False',
        SAVED['prefs'] is not None and SAVED['prefs'].get('global') is False,
        json.dumps(SAVED['prefs'], ensure_ascii=False)[:160])
    chk('数据列表标出总开关关闭', '总开关关闭' in pg.locator('#nr-grid').inner_text(),
        pg.locator('#nr-grid').inner_text()[:120])
    pg.click('[data-act="notify-global-toggle"]')
    pg.wait_for_timeout(1000)
    chk('恢复后列表回到会发送', '总开关关闭' not in pg.locator('#nr-grid').inner_text())

    print('\n[4] 文案模板编辑')
    pg.click('[data-act="notify-tpl-scene"][data-s="med"]')
    pg.wait_for_timeout(500)
    before = pg.locator('#nr-tpl-title').input_value()
    pg.fill('#nr-tpl-title', '吃药提醒 · {时间}')
    pg.wait_for_timeout(300)
    chk('输入即时反映到预览区', '吃药提醒' in pg.locator('#nr-tpl-preview').inner_text(),
        pg.locator('#nr-tpl-preview').inner_text())
    pg.click('[data-act="notify-tpl-save"]')
    pg.wait_for_timeout(900)
    chk('模板保存请求带上自定义标题',
        SAVED['templates'] is not None and
        SAVED['templates'].get('templates', {}).get('scenes', {}).get('med', {}).get('title') == '吃药提醒 · {时间}',
        json.dumps(SAVED['templates'], ensure_ascii=False)[:200])
    chk('模板默认值仍可恢复', before in ('该吃药了', '{标题}'), before)

    pg.click('[data-act="notify-tpl-mailmode"][data-m="plain"]')
    pg.wait_for_timeout(300)
    chk('切纯文本后预览同步', '邮件（纯文本）' in pg.locator('#nr-tpl-preview').inner_text())
    pg.click('[data-act="notify-tpl-mailmode"][data-m="html"]')
    pg.wait_for_timeout(300)
    chk('HTML 卡片预览存在', pg.locator('.nr-mailprev').count() == 1)
    pg.click('[data-act="notify-tpl-color"][data-c="green"]')
    pg.wait_for_timeout(300)
    chk('主题色切换生效',
        'on' in (pg.locator('[data-act="notify-tpl-color"][data-c="green"]').get_attribute('class') or ''))
    pg.fill('#nr-tpl-footer', '测试页脚')
    pg.click('[data-act="notify-tpl-save"]')
    pg.wait_for_timeout(900)
    chk('保存带上邮件模式与页脚',
        SAVED['templates']['templates']['mail']['mode'] == 'html' and
        SAVED['templates']['templates']['mail']['footer'] == '测试页脚',
        json.dumps(SAVED['templates'].get('templates', {}).get('mail', {}), ensure_ascii=False))

    print('\n[5] 用户通知数据列表（卡片网格，对齐设计稿）')
    cards = pg.locator('.nr-card')
    N_SERVER = 6
    n0 = cards.count()
    chk('服务端 %d 条都渲染成卡片（另含本地提醒）' % N_SERVER,
        all(pg.locator('[data-act="notify-plan-item"][data-id="%s"]' % i).count() == 1
            for i in ('m1', 't1', 'h_water', 'c1', 'n1', 'r1')) and n0 >= N_SERVER, str(n0))
    body = pg.locator('#nr-grid').inner_text()
    chk('显示用药与喝水', ('该吃药了' in body) and ('喝水' in body), body[:120])
    chk('默认按优先级分组', '紧急' in body and '当日' in body and '日常' in body, body[:80])
    chk('卡片带类目徽标', '用药提醒' in body and '每日小结' in body, '')
    chk('卡片带时间与状态', '08:00' in body and ('会发送' in body or '本地' in body), body[:200])
    chk('卡片带功能与来源脚注', '功能：喝水' in body and '来源：服务端排程' in body, '')
    stat_txt = pg.locator('#nr-plan-stat').inner_text()
    chk('统计行给出条数 / 类目数 / 当前显示',
        '个类目' in stat_txt and '当前显示' in stat_txt, stat_txt)

    print('\n[5b] 筛选：类目 / 优先级 / 状态')
    pg.select_option('#nr-f-cat', 'med')
    pg.wait_for_timeout(400)
    chk('按类目筛只剩用药 1 张', pg.locator('.nr-card').count() == 1, str(pg.locator('.nr-card').count()))
    pg.select_option('#nr-f-cat', '')
    pg.select_option('#nr-f-pri', '当日')
    pg.wait_for_timeout(400)
    chk('按优先级筛出 3 张', pg.locator('.nr-card').count() == 3, str(pg.locator('.nr-card').count()))
    pg.select_option('#nr-f-pri', '')
    pg.wait_for_timeout(300)
    chk('清理筛选后回到初始数量', pg.locator('.nr-card').count() == n0,
        '%d vs %d' % (pg.locator('.nr-card').count(), n0))

    print('\n[5c] 排序：按类目 / 按时间')
    pg.select_option('#nr-f-sort', 'category')
    pg.wait_for_timeout(400)
    gtext = pg.locator('#nr-grid').inner_text()
    chk('按类目排序出现类目分组条', '用药提醒' in gtext and '每日小结' in gtext, gtext[:80])
    pg.select_option('#nr-f-sort', 'time')
    pg.wait_for_timeout(400)
    chk('按时间排序不打分组条', pg.locator('.nr-group').count() == 0,
        str(pg.locator('.nr-group').count()))
    pg.select_option('#nr-f-sort', 'priority')
    pg.wait_for_timeout(300)

    print('\n[5d] 点卡片应用真实内容到模板预览')
    before_prev = pg.locator('#nr-tpl-preview').inner_text()
    pg.click('[data-act="notify-plan-item"][data-id="h_water"]')
    pg.wait_for_timeout(400)
    chk('卡片高亮', pg.locator('[data-act="notify-plan-item"][data-id="h_water"].on').count() == 1)
    after_prev = pg.locator('#nr-tpl-preview').inner_text()
    chk('模板预览换成该条内容', '今天还差 4 杯' in after_prev and '今天还差 4 杯' not in before_prev,
        after_prev[:80])
    pg.click('[data-act="notify-plan-clear"]')
    pg.wait_for_timeout(400)
    chk('清除选择后取消高亮', pg.locator('.nr-card.on').count() == 0)
    chk('预览回到按场景取样的内容', '今天还差 4 杯' not in pg.locator('#nr-tpl-preview').inner_text())
    pg.click('[data-act="notify-board-toggle"][data-b="water"]')
    pg.wait_for_timeout(300)
    chk('模块板块不能直接停用（提示去功能模块）', '功能模块' in pg.locator('#toast').inner_text())

    print('\n[6] 配置页旧入口已移除')
    pg.click('[data-nav="config"]')
    pg.wait_for_timeout(900)
    chk('配置页没有通知通道矩阵', pg.locator('.mx-table').count() == 0)
    chk('配置页没有今日推送计划', pg.locator('text=今日推送计划').count() == 0)
    chk('配置页仍有最近发送', pg.locator('text=最近发送').count() >= 1)

    chk('无 JS 运行时异常', len(errs) == 0, json.dumps(errs[:3], ensure_ascii=False))
    br.close()

srv.shutdown()
print('\n==============================================')
print('通知路由页：%d 通过 / %d 失败' % (PASS, FAIL))
if FAILS:
    print('失败：' + ' / '.join(FAILS))
raise SystemExit(0 if FAIL == 0 else 1)
