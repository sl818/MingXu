# -*- coding: utf-8 -*-
"""通知路由改版前后对比截图（v210 配置页 → v211 通知路由页）。

前置：`.tmp-v210/` 下有 v210 的 index.html + assets + icons（由 git show 生成）。
产出：docs/images/notify-route-before.png / -after.png / -config-after.png
运行：python e2e/shot-notify-route.py
"""
import json
import secrets
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OLD = ROOT / '.tmp-v210'
OUT = ROOT / 'docs' / 'images'
USER = {'id': 1, 'email': 'test@example.com', 'name': '测试'}
sessions = {}
board = {'data': {'habits': [], 'tasks': [], 'meds': [], 'checks': {}, 'doses': {},
                  'modules': {'water': {'on': True}, 'move': {'on': True},
                              'breathe': {'on': True}, 'quit': {'on': False}},
                  'modulePrefs': {'meds': {'on': True}}}, 'rev': 1}
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
SCENES = {k: {'title': '{标题}', 'body': '{正文}', 'browser': '{浏览器文案}'}
          for k in ('med', 'task', 'habit', 'water', 'move', 'breathe',
                    'report', 'notice', 'countdown', 'debt', 'test')}


def make_handler(root):
    class H(SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(root), **kw)

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
                self._j({'ok': True, 'enabled': True,
                         'webhook': 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=x',
                         'sent_today': 3, 'recent': [
                             {'at': '2026-11-27 08:20:11', 'text': '今日待办早报\n未完成 2 项'},
                             {'at': '2026-11-27 08:00:04', 'text': '该吃药了\n维生素D 1粒'}], 'plan': []})
            elif a == 'mail_status':
                self._j({'ok': True, 'config': {'enabled': False, 'hasSecret': False}})
            elif a == 'push_preview':
                self._j({'ok': True, 'date': '2026-11-27', 'items': [
                    {'id': 'm1', 'time': '08:00', 'kind': 'med', 'source': 'med', 'priority': '紧急',
                     'title': '该吃药了', 'body': '维生素D 1粒（每天 08:00）'},
                    {'id': 'h_water', 'time': '10:30', 'kind': 'habit', 'source': 'water', 'priority': '日常',
                     'title': '喝水', 'body': '该喝水了 · 今天还差 4 杯'},
                    {'id': 't1', 'time': '14:00', 'kind': 'task', 'source': 'task', 'priority': '当日',
                     'title': '该做这件事了', 'body': '交周报 · 14:00–15:00'},
                ]})
            elif a == 'notify_prefs':
                self._j({'ok': True,
                         'kinds': {'med': '用药提醒', 'task': '待办到点', 'habit': '习惯提醒',
                                   'countdown': '倒数日', 'notice': '自定义提醒',
                                   'debt': '还款提醒', 'report': '每日小结'},
                         'channels': {'wecom': '企业微信', 'mail': '邮件'},
                         'prefs': {k: {'wecom': True, 'mail': k not in ('habit', 'report')}
                                   for k in ('med', 'task', 'habit', 'countdown', 'notice', 'debt', 'report')},
                         'quiet': False, 'quietCfg': {'on': False, 'start': '23:00', 'end': '07:00'},
                         'report': {'morning': '08:20', 'noon': '12:30', 'evening': '20:00'},
                         'boards': BOARDS,
                         'templates': {'scenes': SCENES,
                                       'mail': {'color': 'blue', 'footer': '明序 · 个人生活提醒'}}})
            elif a == 'load':
                self._j({'ok': True, 'data': board['data'], 'rev': board['rev'],
                         'updated_at': 1792813000000})
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
                b = json.dumps({'ok': True, 'user': USER, 'csrf': 'x'}).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(b)))
                self.send_header('Set-Cookie', 'sid=' + sid + '; Path=/')
                self.end_headers()
                self.wfile.write(b)
            elif a in ('save', 'force'):
                board['data'] = body['data']
                board['rev'] += 1
                self._j({'ok': True, 'rev': board['rev'], 'updated_at': 1792813000000})
            elif a == 'notify_prefs_save':
                self._j({'ok': True, 'prefs': {}, 'boards': BOARDS, 'quiet': False,
                         'quietCfg': {'on': False}, 'report': {}})
            elif a == 'notify_templates_save':
                self._j({'ok': True, 'templates': body.get('templates') or {}})
            else:
                self._j({'ok': False, 'error': '?'}, 404)

    return H


def serve(root):
    srv = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(root))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def login(pg, port):
    pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
    pg.wait_for_timeout(500)
    if pg.locator('[data-act="cloud-login"]').count():
        pg.click('[data-act="cloud-login"]')
        pg.wait_for_timeout(400)
        pg.fill('input[name="email"]', 'test@example.com')
        pg.fill('input[name="password"]', 'test@example.com')
        pg.click('form.modal-card button[type="submit"]')
        pg.wait_for_timeout(2600)


with sync_playwright() as pw:
    br = pw.chromium.launch(channel='chrome')

    # 改前：v210 配置页（通知通道矩阵 + 今日推送计划）
    old_srv = serve(OLD)
    pg = br.new_page(viewport={'width': 1280, 'height': 1100})
    login(pg, old_srv.server_address[1])
    pg.click('.nav-item[data-nav="config"]')
    pg.wait_for_timeout(1200)
    pg.screenshot(path=str(OUT / 'notify-route-before.png'), full_page=True)
    old_srv.shutdown()
    pg.close()

    # 改后：v211 通知路由页 + 配置页瘦身
    new_srv = serve(ROOT)
    pg = br.new_page(viewport={'width': 1280, 'height': 1100})
    login(pg, new_srv.server_address[1])
    pg.click('.nav-item[data-nav="notifyroute"]')
    pg.wait_for_timeout(1600)
    # 布局自检：数据列表网格是否铺满容器（v214 卡片上线后加的，回归时能看到数值）
    print('[布局]', pg.evaluate('''() => {
      const g = document.getElementById('nr-grid');
      const p = g ? g.closest('.panel') : null;
      if (!g || !p) return 'no grid';
      return {
        panel: Math.round(p.getBoundingClientRect().width),
        grid: Math.round(g.getBoundingClientRect().width),
        cols: getComputedStyle(g).gridTemplateColumns,
        scrollW: g.scrollWidth, clientW: g.clientWidth,
        cards: g.querySelectorAll('.nr-card').length,
        widths: [...g.querySelectorAll('.nr-card')].map(c => Math.round(c.getBoundingClientRect().width)),
        rights: [...g.querySelectorAll('.nr-card')].map(c => Math.round(c.getBoundingClientRect().right)),
        gridRight: Math.round(g.getBoundingClientRect().right)
      };
    }'''))
    pg.screenshot(path=str(OUT / 'notify-route-after.png'), full_page=True)
    pg.click('.nav-item[data-nav="config"]')
    pg.wait_for_timeout(1000)
    pg.screenshot(path=str(OUT / 'notify-route-config-after.png'), full_page=True)
    new_srv.shutdown()
    br.close()

print('截图完成：')
for n in ('notify-route-before.png', 'notify-route-after.png', 'notify-route-config-after.png'):
    p = OUT / n
    print(' ', n, p.stat().st_size // 1024, 'KB' if p.exists() else 'MISSING')
