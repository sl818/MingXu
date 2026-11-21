# -*- coding: utf-8 -*-
"""CSS 分层合并的等价性验证（落盘前的安全网）。

思路：不改磁盘。同一个浏览器开两个页面，用 route 把 /assets/app.css
分别喂「原始内容」和「合并后内容」，然后逐 (视图 × 皮肤 × 明暗) 组合
对比全元素 getComputedStyle（含 --自定义属性）。任何一处不一致都说明
合并改变了层叠结果，必须停下来查。

为什么必须做：合并会把同一选择器的声明挪到「最后一次出现的位置」，
若两次出现之间夹着其他选择器，跨选择器的层叠顺序理论上可能变化。
纯文本解析证明不了这一点，浏览器计算值可以。

用法：
    python e2e/css_equiv_check.py
退出码 0 = 完全等价；1 = 发现差异（明细打印到 stdout）。
"""
import io
import os
import re
import sys
import json
import http.server
import threading
import socketserver
import secrets
from functools import partial
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from css_merge_layers import build_merged  # noqa: E402

DOC = ROOT
CSS_PATH = os.path.join(ROOT, 'assets', 'app.css')
SKINS = ['paper', 'slate', 'cloud-float', 'cloud-focus', 'neu', 'retro']
THEMES = ['light', 'dark']
VIEWS = ['today', 'meds', 'quit', 'board', 'money', 'habits',
         'weight', 'essays', 'calendar', 'stats', 'config', 'settings']
MAX_ELEMENTS = 300

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
            body = open(os.path.join(DOC, 'index.html'), 'rb').read()
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


# 只固定光标；刻意不冻结 animation/transition——它们的声明值本身就是
# 本次验证对象之一（合并若改变了运动声明的层叠结果，必须被抓到）
FREEZE_CSS = '*{caret-color:transparent!important}'

SNAPSHOT_JS = """(cfg) => {
  // 先把 CSS 动画/过渡/WAAPI 动画全部推到终态，避免两页动画进度不同造成假差异
  try { for (const a of document.getAnimations()) { try { a.finish(); } catch (e) {} } } catch (e) {}
  const props = cfg.props, limit = cfg.limit;
  // .toast 是带入场动画的瞬态提示，随时间出现/消失，不参与静态层叠等价验证
  const els = Array.from(document.querySelectorAll('body *'))
                   .filter(el => !el.closest('.toast'));
  const rows = [];
  for (let i = 0; i < els.length && i < limit; i++) {
    const el = els[i];
    const cs = getComputedStyle(el);
    const row = [el.tagName, (typeof el.className === 'string' ? el.className : '')];
    for (const p of props) row.push(cs.getPropertyValue(p));
    rows.push(row);
  }
  return rows;
}"""


def _fulfill_css(css_text, route, request):
    route.fulfill(status=200, content_type='text/css; charset=utf-8', body=css_text)


def prepare_page(ctx, css_text, port):
    pg = ctx.new_page()
    pg.route(re.compile(r'/assets/app\.css'), partial(_fulfill_css, css_text))
    pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle', timeout=60000)
    pg.wait_for_timeout(500)
    if pg.locator('[data-act="cloud-login"]').count():
        pg.click('[data-act="cloud-login"]')
        pg.wait_for_timeout(350)
        pg.fill('input[name="email"]', 'u@example.com')
        pg.fill('input[name="password"]', 'x')
        pg.click('form.modal-card button[type="submit"]')
        pg.wait_for_timeout(1500)
    pg.add_style_tag(content=FREEZE_CSS)
    return pg


def set_probe(pg, view, skin, theme):
    ok = pg.evaluate("""(v) => {
      const b = document.querySelector('[data-nav="' + v + '"]');
      if (b) { b.click(); return true; }
      return false;
    }""", view)
    pg.wait_for_timeout(260)
    pg.evaluate("""(c) => {
      document.documentElement.setAttribute('data-skin', c.s);
      document.documentElement.setAttribute('data-theme', c.t);
    }""", {'s': skin, 't': theme})
    pg.wait_for_timeout(140)
    return ok


def load_orig():
    """合并前基线优先取 git HEAD 的 app.css——与磁盘当前状态解耦，
    落盘之后重跑本脚本依然有效（否则会变成"合并版 vs 合并版"的自比）。"""
    try:
        import subprocess
        r = subprocess.run(['git', '-C', ROOT, 'show', 'HEAD:assets/app.css'],
                           capture_output=True, timeout=20)
        if r.returncode == 0 and r.stdout:
            return r.stdout.decode('utf-8'), 'git HEAD'
    except Exception:
        pass
    with io.open(CSS_PATH, encoding='utf-8', newline='') as f:
        return f.read(), '磁盘当前文件'


def main():
    orig, src_of = load_orig()
    print('原始基线来源: %s（%d 字节）' % (src_of, len(orig.encode('utf-8'))))
    merged, info = build_merged(orig)
    if merged is None:
        print('!! 合并产物不可用: %s' % info)
        return 1
    print('合并统计: %s' % json.dumps(info, ensure_ascii=False))
    print('原始 %d 字节 → 合并后 %d 字节' % (len(orig.encode('utf-8')), len(merged.encode('utf-8'))))

    # 候选属性：允许前导 --，把皮肤自定义属性也纳入对比
    cand = set(re.findall(r'(-{0,2}[a-zA-Z][a-zA-Z0-9-]*)\s*:', orig))

    srv = TS(('127.0.0.1', 0), H)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    probes = []
    for v in VIEWS:
        probes.append((v, 'paper', 'light'))
    for s in SKINS:
        for t in THEMES:
            probes.append(('today', s, t))
    # 截图比对中曾出现差异的两个皮肤 × board 场景，专门重现
    probes += [('board', 'cloud-float', 'light'), ('board', 'neu', 'light')]
    seen = set()
    probes = [p for p in probes if not (p in seen or seen.add(p))]

    diffs = []
    nav_miss = []
    with sync_playwright() as p:
        br = p.chromium.launch(channel='chrome', headless=True)
        ctx = br.new_context(viewport={'width': 1100, 'height': 760}, service_workers='block')
        pgA = prepare_page(ctx, orig, port)     # 原始
        pgB = prepare_page(ctx, merged, port)   # 合并后

        valid = set(pgA.evaluate(
            "() => { const s = new Set(); for (const p of getComputedStyle(document.documentElement)) s.add(p); return Array.from(s); }"))
        props = sorted((cand & valid) | {x for x in cand if x.startswith('--')})
        print('对比属性 %d 个（其中自定义属性 %d 个）｜探针 %d 个'
              % (len(props), len([x for x in props if x.startswith('--')]), len(probes)))

        for idx, (view, skin, theme) in enumerate(probes):
            okA = set_probe(pgA, view, skin, theme)
            okB = set_probe(pgB, view, skin, theme)
            if not (okA and okB):
                nav_miss.append('%s/%s/%s' % (view, skin, theme))
            a = pgA.evaluate(SNAPSHOT_JS, {'props': props, 'limit': MAX_ELEMENTS})
            b = pgB.evaluate(SNAPSHOT_JS, {'props': props, 'limit': MAX_ELEMENTS})
            tag = '%s | %s | %s' % (view, skin, theme)
            if len(a) != len(b):
                diffs.append('%s: 元素数 %d vs %d' % (tag, len(a), len(b)))
                continue
            n = 0
            for i, (ra, rb) in enumerate(zip(a, b)):
                if ra == rb:
                    continue
                for j in range(2, min(len(ra), len(rb))):
                    if ra[j] != rb[j]:
                        prop = props[j - 2] if j - 2 < len(props) else '?'
                        diffs.append('%s: 元素[%d] %s.%s 的 %s: %r → %r'
                                     % (tag, i, ra[0], (ra[1] or '')[:28], prop, ra[j], rb[j]))
                        n += 1
                        if n >= 4:
                            break
                if n >= 4:
                    break
            if (idx + 1) % 6 == 0:
                print('  ... %d/%d 探针完成，累计差异 %d' % (idx + 1, len(probes), len(diffs)))

        br.close()
    srv.shutdown()

    print('\n=== 结果 ===')
    print('探针: %d｜导航未命中(跳过): %d｜计算样式差异: %d' % (len(probes), len(nav_miss), len(diffs)))
    if nav_miss:
        print('导航未命中:', ', '.join(nav_miss[:8]))
    for d in diffs[:30]:
        print('  ' + d)
    if len(diffs) > 30:
        print('  ...另有 %d 条' % (len(diffs) - 30))
    if diffs:
        print('\n结论: 不等价，禁止落盘。')
        return 1
    print('\n结论: 全部探针计算样式一致，合并等价。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
