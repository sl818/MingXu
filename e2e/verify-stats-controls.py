# -*- coding: utf-8 -*-
"""统计页交互控件回归：区间切换 / 时间线展开 / 戒烟分析折叠。

背景（v134 修复）：这三个按钮的处理器键被误写成 statk-*，与渲染的 stats-* 不匹配，
事件分发 if (fn) 静默跳过——点了没反应，statsRange 恒为 30 天。
本脚本用真浏览器点击验证，防止同类"死键"回归。

用法：python e2e/verify-stats-controls.py
"""
import http.server
import threading
import json
import socketserver
import secrets
import os
import sys
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = ROOT
USER = {'id': 1, 'email': 'u@example.com', 'display_name': '测试', 'is_admin': False}
sessions = {}
TODAY = '2026-11-21'

checks = {}
for i in range(60):
    d = '2026-11-%02d' % (1 + i % 20)
    checks.setdefault('h_read', {})[d] = 3

# 时间线读的是 state.events（不是 checks），必须造 >5 条才会出现「查看更多」
EVENTS = []
for i in range(8):
    day = 21 - i
    EVENTS.append({'id': 'h_read', 'at': '2026-11-%02dT%02d:30:00' % (day, 8 + i),
                   'delta': 1, 'd': '2026-11-%02d' % day, 'kind': ''})

BOARD = {'data': {
    'version': 2, 'view': 'today',
    'habits': [
        {'id': 'h_read', 'name': '读书', 'icon': '📖', 'type': 'build', 'target': 3, 'unit': '页',
         'color': '#6b5b8e', 'createdAt': '2026-10-01T08:00:00Z'},
        {'id': 'h_drink', 'name': '戒烟', 'icon': '🚭', 'type': 'smoke', 'target': 1, 'unit': '次',
         'color': '#7a8471', 'createdAt': '2026-10-01T08:00:00Z'},
    ],
    'checks': checks, 'notes': {}, 'moods': {}, 'events': EVENTS,
    'meds': [{'id': 'm1', 'name': '阿莫西林', 'purpose': '消炎', 'form': '胶囊', 'strength': '0.25g',
              'doseAmount': 1, 'doseUnit': '粒', 'times': ['08:00'], 'courseType': 'long',
              'startDate': TODAY, 'endDate': '', 'reviewDate': '', 'status': 'active', 'stock': '', 'note': ''}],
    'doses': {}, 'bodyProfile': {'age': 30, 'height': 170}, 'weights': [], 'essays': [],
    'tasks': [{'id': 't1', 'title': '测试', 'tag': '生活', 'priority': '中', 'status': 'todo', 'due': TODAY}],
}, 'rev': 3}


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _j(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        path = self.path.split('?')[0]
        if path in ('/', '/index.html'):
            body = open(os.path.join(DOC, 'index.html'), 'rb').read()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path.startswith(('/assets/', '/themes/', '/icons/')) or path.endswith('/manifest.json'):
            try:
                body = open(DOC + path, 'rb').read()
                ct = 'text/css' if path.endswith('.css') else 'application/octet-stream'
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
            if a == 'status':
                return self._j({'ok': True, 'installed': True, 'registration_open': False})
            if a == 'me':
                return self._j({'ok': True, 'user': USER, 'csrf': 'x', 'registration_open': False})
            if a == 'load':
                return self._j({'ok': True, 'data': BOARD['data'], 'rev': BOARD['rev'],
                                'updated_at': 1792813000000, 'history': []})
            if a in ('push_status', 'ics_status'):
                return self._j({'ok': True, 'enabled': False, 'webhook_set': False, 'token': 'x', 'url': 'x'})
            return self._j({'ok': False}, 404)
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        n = int(self.headers.get('Content-Length', 0))
        self.rfile.read(n or 0)
        if self.path.startswith('/api.php'):
            return self._j({'ok': True, 'rev': BOARD['rev'] + 1, 'updated_at': 1792813000000})
        self.send_response(405)
        self.end_headers()


class TS(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


SUB_JS = """() => {
  const m = document.body.innerText.match(/近 (\\d+) 天 · 只看有记录的日子/);
  return m ? m[0] : '';
}"""


def main():
    srv = TS(('127.0.0.1', 0), H)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    results = []

    def check(name, cond, detail=''):
        results.append((name, bool(cond), detail))
        print('  %s %s %s' % ('PASS' if cond else 'FAIL', name, detail))

    with sync_playwright() as p:
        br = p.chromium.launch(channel='chrome', headless=True)
        ctx = br.new_context(viewport={'width': 1280, 'height': 900}, service_workers='block')
        pg = ctx.new_page()
        errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)[:150]))
        pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle', timeout=60000)
        pg.wait_for_timeout(1200)
        pg.evaluate("() => { const b = document.querySelector('[data-nav=\"stats\"]'); if (b) b.click(); }")
        pg.wait_for_timeout(900)
        check('进入统计页', pg.evaluate("() => document.body.innerText.includes('数据统计')"))

        # ① 区间切换：30 → 7 → 90
        sub0 = pg.evaluate(SUB_JS)
        btn7 = pg.locator('[data-act="set-stats-range"][data-range="7"]')
        check('区间按钮存在', btn7.count() > 0, sub0)
        if btn7.count():
            btn7.first.click()
            pg.wait_for_timeout(600)
            sub7 = pg.evaluate(SUB_JS)
            active7 = pg.evaluate("""() => {
              const b = document.querySelector('[data-act="set-stats-range"][data-range="7"]');
              return b ? /(^|\\s)active(\\s|$)/.test(b.className) : false;
            }""")
            check('点 7 天后副标题变为近 7 天', '近 7 天' in sub7, '%s → %s' % (sub0, sub7))
            check('7 天按钮高亮', active7)
            pg.locator('[data-act="set-stats-range"][data-range="90"]').first.click()
            pg.wait_for_timeout(600)
            check('点 90 天后副标题变为近 90 天', '近 90 天' in pg.evaluate(SUB_JS))

        # ② 时间线展开/收起（先切到习惯面板的「时间线」tab，默认是「本月」不渲染时间线）
        pg.evaluate("""() => {
          const b = document.querySelector('[data-act="stats-habit-tab"][data-tab="log"]');
          if (b) b.click();
        }""")
        pg.wait_for_timeout(600)
        tg = pg.locator('[data-act="stats-log-toggle"]')
        check('时间线按钮存在', tg.count() > 0)
        if tg.count():
            before = pg.evaluate("() => document.querySelectorAll('.log-row').length")
            label0 = tg.first.inner_text()
            tg.first.click()
            pg.wait_for_timeout(600)
            after = pg.evaluate("() => document.querySelectorAll('.log-row').length")
            label1 = pg.evaluate("""() => {
              const b = document.querySelector('[data-act="stats-log-toggle"]');
              return b ? b.innerText : '';
            }""")
            check('时间线展开后行数增加', after > before, '%d → %d 行' % (before, after))
            check('按钮文案变为收起', '收起' in label1, '%s → %s' % (label0.strip(), label1.strip()))

        # ③ 戒烟分析折叠
        qf = pg.locator('[data-act="stats-quit-fold"]')
        check('戒烟折叠按钮存在', qf.count() > 0)
        if qf.count():
            l0 = qf.first.inner_text()
            qf.first.click()
            pg.wait_for_timeout(600)
            l1 = pg.evaluate("""() => {
              const b = document.querySelector('[data-act="stats-quit-fold"]');
              return b ? b.innerText : '';
            }""")
            check('点击后展开分析 → 收起分析', '展开分析' in l0 and '收起分析' in l1,
                  '%s → %s' % (l0.strip(), l1.strip()))
            pg.locator('[data-act="stats-quit-fold"]').first.click()
            pg.wait_for_timeout(600)
            l2 = pg.evaluate("""() => {
              const b = document.querySelector('[data-act="stats-quit-fold"]');
              return b ? b.innerText : '';
            }""")
            check('再点可折叠回去', '展开分析' in l2)

        check('无 JS 运行时异常', not errs, str(errs[:2]))
        br.close()
    srv.shutdown()

    passed = sum(1 for _, ok, _ in results if ok)
    print('\n统计页控件回归：%d/%d 通过' % (passed, len(results)))
    return 0 if passed == len(results) else 1


if __name__ == '__main__':
    sys.exit(main())
