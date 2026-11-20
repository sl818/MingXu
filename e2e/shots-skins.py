# -*- coding: utf-8 -*-
"""六套皮肤 × 关键界面截图，一眼看出哪套破版。

为什么要有这个：
    皮肤文件会「重绘组件」（不只是换颜色），所以每加一个新组件，
    都可能在某几套皮肤下出问题——v127 的任务弹窗就是这样，只有冷雾矩阵正常。
    改完 UI 跑一遍，12 张图摊在一起看，几秒就能发现异常。

用法：
    python e2e/shots-skins.py
输出：
    design/skins/<皮肤>__board.png
    design/skins/<皮肤>__sheet.png
    design/skins/_grid.png          ← 全部拼一起，总览用
"""
import http.server, threading, json, socketserver, secrets, os, sys
from playwright.sync_api import sync_playwright

DOC = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo'
OUT = DOC + '/design/skins'
SKINS = ['paper', 'slate', 'cloud-float', 'cloud-focus', 'neu', 'retro']

USER = {'id': 1, 'email': 'u@example.com', 'display_name': '测试', 'is_admin': False,
        'status': 'active', 'created_at': '2026-10-01 00:00:00', 'last_login_at': None}
sessions = {}
TODAY = '2026-11-20'
TASKS = [
    {'id': 't1', 'title': '站点转型个人工作台', 'note': '先看埋点数据', 'tag': '工作', 'priority': '中',
     'status': 'todo', 'due': TODAY, 'repeat': 'none', 'notify': True, 'notifyTime': '09:00',
     'subtasks': [{'id': 's1', 'title': '梳理现有信息架构', 'done': True},
                  {'id': 's2', 'title': '确定导航层级', 'done': False}]},
    {'id': 't2', 'title': '优化 eLab', 'note': '', 'tag': '工作', 'priority': '高',
     'status': 'doing', 'due': TODAY, 'repeat': 'none', 'notify': True, 'notifyTime': '09:00', 'subtasks': []},
    {'id': 't3', 'title': '牙线头', 'note': '', 'tag': '生活', 'priority': '低',
     'status': 'done', 'due': TODAY, 'repeat': 'none', 'notify': False, 'notifyTime': '09:00', 'subtasks': []},
]
BOARD = {'data': {'version': 2, 'habits': [], 'tasks': TASKS, 'checks': {}, 'essays': [], 'weights': [],
                  'meds': [], 'medLogs': {}, 'money': {}, 'settings': {}, 'essayTags': [], 'quit': {}}, 'rev': 1}


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _j(self, obj, code=200, eh=None):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(b)))
        for k, v in (eh or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(b)

    def _auth(self):
        for part in (self.headers.get('Cookie') or '').split(';'):
            if part.strip().startswith('sid='):
                return sessions.get(part.strip()[4:])
        return None

    def do_GET(self):
        path = self.path.split('?')[0]
        if path in ('/', '/index.html'):
            body = open(DOC + '/index.html', 'rb').read()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path.startswith(('/assets/', '/themes/', '/icons/')) or path.endswith('/manifest.json'):
            fp = DOC + path
            try:
                body = open(fp, 'rb').read()
                ct = 'text/css' if fp.endswith('.css') else (
                    'application/javascript' if fp.endswith('.js') else 'application/octet-stream')
                self.send_response(200)
                self.send_header('Content-Type', ct)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except Exception:
                self.send_response(404)
                self.end_headers()
            return
        if self.path.startswith('/api.php'):
            a = self.path.split('action=')[-1].split('&')[0]
            u = self._auth()
            if a == 'me':
                self._j({'ok': True, 'user': USER if u else None, 'csrf': 'x',
                         'registration_open': False, 'registration_mode': 'invite', 'site_name': '明序'})
            elif a == 'status':
                self._j({'ok': True, 'installed': True})
            elif a == 'load':
                self._j({'ok': True, 'data': BOARD['data'], 'rev': 1,
                         'updated_at': 1792813000000, 'history': []})
            elif a in ('push_status', 'ics_status'):
                self._j({'ok': True, 'enabled': False, 'webhook_set': False, 'token': 'x', 'url': 'x'})
            elif a == 'mail_status':
                self._j({'ok': True, 'config': {'hasSecret': False, 'enabled': False},
                         'crypto_ready': True, 'recipient': 'a@b.com'})
            else:
                self._j({'ok': False, 'error': 'unknown'}, 404)
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        if not self.path.startswith('/api.php'):
            self.send_response(405)
            self.end_headers()
            return
        a = self.path.split('action=')[-1].split('&')[0]
        n = int(self.headers.get('Content-Length', 0))
        self.rfile.read(n or 0)
        if a == 'login':
            sid = secrets.token_hex(8)
            sessions[sid] = USER
            self._j({'ok': True, 'user': USER, 'csrf': 'x'}, eh={'Set-Cookie': 'sid=' + sid + '; Path=/'})
        else:
            self._j({'ok': True, 'rev': 2, 'updated_at': 1792813000000})


class TS(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


def main():
    os.makedirs(OUT, exist_ok=True)
    srv = TS(('127.0.0.1', 0), H)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    shots = []
    with sync_playwright() as p:
        br = p.chromium.launch(channel='chrome', headless=True)
        for skin in SKINS:
            ctx = br.new_context(viewport={'width': 1100, 'height': 760})
            pg = ctx.new_page()
            errs = []
            pg.on('pageerror', lambda e: errs.append(str(e)[:100]))
            pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
            pg.wait_for_timeout(600)
            if pg.locator('[data-act="cloud-login"]').count():
                pg.click('[data-act="cloud-login"]')
                pg.wait_for_timeout(350)
                pg.fill('input[name="email"]', 'u@example.com')
                pg.fill('input[name="password"]', 'x')
                pg.click('form.modal-card button[type="submit"]')
                pg.wait_for_timeout(1500)
            pg.evaluate("() => { const b=document.querySelector('[data-nav=\"board\"]'); if(b) b.click(); }")
            pg.wait_for_timeout(600)
            # 弹窗已经开着的情况下切皮肤最稳（render 不会把 data-skin 重置）
            pg.evaluate("(s) => document.documentElement.setAttribute('data-skin', s)", skin)
            pg.wait_for_timeout(250)

            b1 = OUT + '/%s__board.png' % skin
            pg.screenshot(path=b1)
            shots.append((skin, 'board', b1))

            pg.locator('.task[data-id="t1"]').click()
            pg.wait_for_timeout(600)
            pg.locator('.tk-title').click()
            pg.wait_for_timeout(250)
            b2 = OUT + '/%s__sheet.png' % skin
            pg.locator('#task-form').screenshot(path=b2)
            shots.append((skin, 'sheet', b2))

            if errs:
                print('  %-12s JS 报错: %s' % (skin, errs[:1]))
            else:
                print('  %-12s ok' % skin)
            ctx.close()
        br.close()
    srv.shutdown()

    # 拼总览图
    try:
        from PIL import Image
        sheets = [(s, f) for s, k, f in shots if k == 'sheet']
        imgs = [(s, Image.open(f).convert('RGB')) for s, f in sheets]
        cols = 3
        w = max(i.width for _, i in imgs)
        h = max(i.height for _, i in imgs)
        rows = (len(imgs) + cols - 1) // cols
        pad = 16
        canvas = Image.new('RGB', (cols * (w + pad) + pad, rows * (h + pad + 22) + pad), (244, 243, 239))
        from PIL import ImageDraw
        d = ImageDraw.Draw(canvas)
        for idx, (name, im) in enumerate(imgs):
            cx = pad + (idx % cols) * (w + pad)
            cy = pad + (idx // cols) * (h + pad + 22)
            d.text((cx + 2, cy + 4), name, fill=(90, 90, 90))
            canvas.paste(im, (cx, cy + 22))
        canvas.save(OUT + '/_grid.png')
        print('\n总览图: design/skins/_grid.png')
    except Exception as e:
        print('拼图跳过:', e)

    print('截图 %d 张，目录 design/skins/' % len(shots))


if __name__ == '__main__':
    main()
