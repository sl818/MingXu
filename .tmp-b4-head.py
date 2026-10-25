# -*- coding: utf-8 -*-
"""第四批逐项行为验证：6.2 导出提示 / 5.3 减少动画 / 5.4 首屏骨架 / 1.2 状态版本号 / 5.2 键盘可达性。"""
import http.server, threading, json, socketserver, secrets, sys, time
from datetime import datetime
from playwright.sync_api import sync_playwright

DOC = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo'
USER = {'id': 1, 'email': 'test@sl00.top', 'display_name': '测试', 'is_admin': False}
sessions = {}
TODAY = '2026-10-25'
ONLY = sys.argv[1] if len(sys.argv) > 1 else None


def habit(hid, name, target, unit, pinned=False, med=False, color='#2f6f5e', note=''):
    return {'id': hid, 'name': name, 'icon': '✅', 'type': 'build', 'target': target, 'unit': unit,
            'color': color, 'note': note, 'createdAt': '2026-09-01T08:00:00Z', 'pinned': pinned, 'med': med}


def med(mid, name, course, times, start='2026-10-01', end=''):
    return {'id': mid, 'name': name, 'purpose': '其他', 'form': '片', 'strength': '',
            'doseAmount': 1, 'doseUnit': '片', 'times': times, 'courseType': course,
            'startDate': start, 'endDate': end, 'reviewDate': '', 'status': 'active',
            'stock': '', 'note': ''}


def task(tid, title, tag, prio, status, due):
    return {'id': tid, 'title': title, 'note': '备注 ' + tid, 'tag': tag,
            'priority': prio, 'status': status, 'due': due, 'createdAt': '2026-10-01T08:00:00Z'}


# 逐日打卡：读 3 页连续 5 天、夜跑连续 2 天、喝水 1 天、事项复盘 0 天
CHECKS = {
    '2026-10-21': {'h_read': 3, 'h_run': 1},
    '2026-10-22': {'h_read': 3},
    '2026-10-23': {'h_read': 3, 'h_run': 1},
    '2026-10-24': {'h_read': 3, 'h_run': 1, 'h_water': 9, 'h_plan': 1},
    '2026-10-25': {'h_read': 3, 'h_run': 1, 'h_water': 3},
}
# 上月数据（用于 3.4 的「与上月对比」）
for d in range(1, 31):
    CHECKS['2026-09-%02d' % d] = {'h_read': 3, 'h_run': 1} if d % 2 == 0 else {}

TASKS = [
    task('o1', '逾期甲', '工作', '高', 'todo', '2026-10-22'),
    task('o2', '逾期乙', '生活', '中', 'todo', '2026-10-23'),
    task('t1', '今日甲', '健康', '中', 'todo', TODAY),
    task('t2', '今日乙', '学习', '低', 'todo', TODAY),
    task('d1', '已完成甲', '健康', '中', 'done', TODAY),
]
TASKS[-1]['doneAt'] = TODAY

board = {'data': {
    'version': 2,
    'habits': [
        habit('h_med', '用药', 2, '次', pinned=True, med=True, color='#6f7f91'),
        habit('h_water', '喝水', 9, '杯', pinned=True, color='#4c7f96'),
        habit('h_read', '读书', 3, '页', color='#6b5b8e'),
        habit('h_run', '夜跑', 1, '次', color='#b5733f'),
        habit('h_plan', '事项复盘', 1, '次', color='#7a6a3f'),
    ],
    'checks': CHECKS, 'notes': {}, 'moods': {'2026-10-25': 'happy'}, 'events': [],
    'meds': [
        med('m_long1', '阿莫西林', 'long', ['08:00', '20:00']),
        med('m_long2', '维生素D', 'long', ['12:00']),
        med('m_short1', '头孢克肟', 'short', ['09:00'], start='2026-10-20', end='2026-10-30'),
        med('m_short2', '布洛芬', 'short', ['08:00'], start='2026-10-24', end='2026-10-28'),
        med('m_prn1', '止痛片', 'prn', []),
        med('m_prn2', '感冒灵', 'prn', []),
    ],
    'doses': {TODAY: {'m_long1': {'08:00': {'at': 1}}}},
    'bodyProfile': {'age': 30, 'height': 170},
    'weights': [
        {'id': 'w1', 'date': '2026-10-01', 'weight': 70.0, 'height': 170, 'age': 30, 'bmi': 24.2},
        {'id': 'w2', 'date': '2026-10-10', 'weight': 69.4, 'height': 170, 'age': 30, 'bmi': 24.0},
        {'id': 'w3', 'date': '2026-10-25', 'weight': 68.4, 'height': 170, 'age': 30, 'bmi': 23.7},
    ],
    'essays': [{'id': 'e1', 'date': TODAY, 'title': '海边散步', 'text': '今天风很大',
                'tags': ['生活'], 'createdAt': '2026-10-01T08:00:00Z', 'updatedAt': 1}],
    'tasks': TASKS,
}, 'rev': 9}

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
                if LOAD_DELAY[0]:
                    time.sleep(LOAD_DELAY[0] / 1000.0)
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
LOAD_DELAY = [0]
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


