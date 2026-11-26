"""478 呼吸法页改版前后对比截图：v193 旧版 vs v195 新版，各出一张整页图"""
import http.server, threading, json, socketserver, secrets, sys, os
from datetime import datetime
from playwright.sync_api import sync_playwright

OLD = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo-before-v193'
NEW = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo'
USER = {'id': 1, 'email': 'test@example.com', 'display_name': '测试', 'is_admin': False}
OUT = NEW + '/design/shots'


def habit(hid, name, icon, **kw):
    h = {'id': hid, 'name': name, 'icon': icon, 'type': 'build', 'target': 1, 'unit': '次',
         'color': '#2f6f5e', 'note': '', 'createdAt': '2026-10-01T00:00:00Z', 'pinned': True, 'archivedAt': ''}
    h.update(kw)
    return h


HABITS = [
    habit('h_med', '用药', '💊', med=True),
    habit('h_water', '喝水', '💧', target=9, unit='杯', perMl=250, goalMl=2300, color='#4c7f96'),
    habit('h_move', '运动', '🏃', color='#b5733f'),
    habit('h_breathe', '478呼吸法', '🌬️', target=3, unit='组', color='#5b8f8a', note='4-7-8 呼吸',
          breatheCycles=4, suggestTime='07:00'),
    habit('h_drink', '戒烟', '🚭', type='smoke', color='#7a8471'),
]

CHECKS = {
    '2026-10-20': {'h_breathe': 2}, '2026-10-21': {'h_breathe': 1}, '2026-10-22': {'h_breathe': 3},
    '2026-10-23': {'h_breathe': 1}, '2026-10-24': {'h_breathe': 2},
}
MODULES = {
    'breathe': {'on': True, 'name': '478呼吸法', 'icon': '🌬️', 'color': '#5b8f8a', 'note': '4-7-8 呼吸',
                'unit': '组', 'groups': 3, 'cycles': 4, 'notify': True, 'suggestTime': '07:00',
                'notifyFreq': 'daily', 'notifyWeekday': 1, 'notifyMonthday': 1, 'notifyNote': '',
                'notifyChannels': ['browser'], 'notifyTimes': ['07:00', '14:00', '21:00'],
                'createdAt': '2026-10-01T00:00:00Z', 'updatedAt': '2026-10-01T00:00:00Z'},
    'water': {'on': True, 'name': '喝水', 'icon': '💧', 'color': '#4c7f96', 'note': '', 'unit': '杯',
              'cups': 9, 'perMl': 250, 'goalMl': 2300, 'notify': True, 'suggestTime': '',
              'notifyFreq': 'daily', 'notifyChannels': ['browser'], 'notifyMode': 'each',
              'notifyDailyCount': 2, 'notifyDailyTimes': {'morning': '08:00', 'noon': '12:30', 'afternoon': '15:00'},
              'notifyStart': '08:00', 'notifyEnd': '21:00',
              'createdAt': '2026-10-01T00:00:00Z', 'updatedAt': '2026-10-01T00:00:00Z'},
    'move': {'on': True, 'name': '运动', 'icon': '🏃', 'color': '#b5733f', 'note': '', 'unit': '次',
             'times': 1, 'notify': True, 'suggestTime': '', 'notifyFreq': 'daily',
             'notifyChannels': ['browser'], 'notifyScenes': {'steps': True, 'plan': True, 'week': True},
             'sports': [], 'records': [],
             'createdAt': '2026-10-01T00:00:00Z', 'updatedAt': '2026-10-01T00:00:00Z'},
    'quit': {'on': True, 'name': '戒烟', 'icon': '🚭', 'color': '#7a8471', 'note': '',
             'startDate': '', 'perDay': 0, 'packPrice': 0, 'packSize': 20,
             'createdAt': '2026-10-01T00:00:00Z', 'updatedAt': '2026-10-01T00:00:00Z'},
}


def make_data():
    return {'version': 2, 'view': 'today', 'habits': HABITS, 'checks': CHECKS, 'notes': {}, 'moods': {},
            'events': [], 'meds': [], 'doses': {}, 'modules': MODULES, 'modulesAt': 0,
            'bodyProfile': {'age': 30, 'height': 170}, 'weights': [], 'essays': [], 'tasks': []}


class H(http.server.SimpleHTTPRequestHandler):
    root = NEW
    sessions = {}

    def __init__(self, *a, **kw): super().__init__(*a, directory=self.root, **kw)

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
            elif a == 'me': self._j({'ok': True, 'user': self.sessions.get(self._sid()), 'csrf': 'x', 'registration_open': False})
            elif a == 'load': self._j({'ok': True, 'data': make_data(), 'rev': 5, 'updated_at': 0})
            else: self._j({'ok': False, 'error': '?'}, 404)
        else: super().do_GET()

    def do_POST(self):
        if self.path.startswith('/api.php'):
            a = self.path.split('action=')[-1].split('&')[0]
            n = int(self.headers.get('Content-Length', 0)); body = json.loads(self.rfile.read(n) or b'{}')
            if a == 'login':
                sid = secrets.token_hex(8); self.sessions[sid] = USER
                self._j({'ok': True, 'user': USER, 'csrf': 'x'}, eh={'Set-Cookie': 'sid=' + sid + '; Path=/'})
            elif a == 'save':
                self._j({'ok': True, 'rev': 6})
            elif a == 'force':
                self._j({'ok': True, 'rev': 6})
            else: self._j({'ok': False, 'error': '?'}, 404)
        else: self.send_response(405); self.end_headers()


class TS(socketserver.ThreadingMixIn, http.server.HTTPServer): daemon_threads = True


def serve(root, port):
    # 每个 server 必须用自己的 handler 子类：root / sessions 是类属性，
    # 共用一个类的话后起的 serve 会把前一个的目录顶掉，两张图会截成同一份。
    base = H

    class HH(base):
        pass

    HH.root = root
    HH.sessions = {}
    srv = TS(('127.0.0.1', port), HH)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def shoot(br, port, path, label):
    ctx = br.new_context(viewport={'width': 1440, 'height': 980}, device_scale_factor=1)
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.clock.install(time=datetime(2026, 10, 24, 14, 0, 0))
    pg.add_init_script("try{localStorage.setItem('lifeboard.layout','top');localStorage.setItem('lifeboard.skin','paper');"
                       "localStorage.setItem('lifeboard.theme.mode','light')}catch(e){}")
    pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
    pg.wait_for_timeout(700)
    pg.click('[data-act="cloud-login"]'); pg.wait_for_timeout(500)
    pg.fill('input[name="email"]', USER['email']); pg.fill('input[name="password"]', '12345678')
    pg.click('form.modal-card button[type="submit"]')
    pg.wait_for_timeout(2600)
    pg.evaluate("() => { document.querySelector('[data-nav=\"breathe\"]').click(); }")
    pg.wait_for_timeout(1200)
    os.makedirs(OUT, exist_ok=True)
    pg.screenshot(path=path, full_page=True)
    h = pg.evaluate("() => document.querySelector('#main').scrollHeight")
    print('%s → %s（页面高 %dpx，JS 错误 %d）' % (label, path, h, len(errs)))
    if errs: print('   ', errs[:2])
    ctx.close()


with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)
    s1 = serve(OLD, 38611)
    s2 = serve(NEW, 38612)
    shoot(br, 38611, OUT + '/breathe-before-v193.png', '改前 v193')
    shoot(br, 38612, OUT + '/breathe-after-v195.png', '改后 v195')
    br.close()
s1.shutdown(); s2.shutdown()
print('done')
