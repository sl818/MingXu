# -*- coding: utf-8 -*-
"""v185 随笔页「查看全文 + Markdown 渲染」验证：

一、Markdown 渲染
  1. 卡片摘要按 Markdown 渲染（粗体/斜体/代码都成了标签，不再是 ** 字面）
  2. 全文弹窗里：标题、列表、引用、代码、链接都渲染出来
  3. 链接地址只放行 http/https，javascript: 被丢掉

二、安全
  4. 正文里的 <script> 不变成真标签
  5. <img onerror=...> 不带 onerror 属性
  6. javascript: 链接不成 <a>

三、交互
  7. 点卡片打开全文弹窗
  8. 弹窗里有「编辑」入口，点它进编辑弹窗
  9. 编辑弹窗有「预览」，点了出渲染结果，再点能回到编辑
 10. 弹窗里能删这篇随笔
 11. 新建的随笔带 Markdown，卡片摘要照样渲染
"""
import http.server
import json
import secrets
import socketserver
import sys
import threading
from datetime import datetime

from playwright.sync_api import sync_playwright

DOC = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo'
USER = {'id': 1, 'email': 'test@example.com', 'display_name': '测试', 'is_admin': False}
sessions = {}
D = '2026-10-24'          # 周六
PASS = 0
FAIL = 0
FAILS = []

MD_TEXT = (
    "# 今天的标题\n"
    "这是一段 **粗体** 和 *斜体* 的文字，还带 `code` 代码。\n"
    "\n"
    "> 引用一句话。\n"
    "\n"
    "- 列表第一项\n"
    "- 列表第二项\n"
    "\n"
    "外链：[明序](https://todo.csl88.top/)"
)

XSS_TEXT = (
    "正常一句。\n"
    "<script>alert('xss')</script>\n"
    "<img src=x onerror=alert(1)>\n"
    "[危险链接](javascript:alert(1))\n"
    "[正常链接](https://example.com/a)"
)

PLAIN_TEXT = "就一句话，没有 Markdown。"


def chk(name, ok, detail=''):
    global PASS, FAIL
    if ok:
        PASS += 1
        print('  [OK] %s' % name)
    else:
        FAIL += 1
        FAILS.append((name, detail))
        print('  [FAIL] %s  << %s' % (name, detail))


board = {'data': {
    'version': 2, 'schemaVersion': 2, 'view': 'today',
    'habits': [], 'modules': {}, 'modulesAt': 0,
    'checks': {}, 'skips': {}, 'notes': {}, 'moods': {}, 'events': [],
    'meds': [], 'doses': {}, 'bodyProfile': {'age': 30, 'height': 170},
    'weights': [],
    'essays': [
        {'id': 'e_md', 'date': '2026-10-20', 'title': '今天的标题', 'text': MD_TEXT,
         'tags': ['生活'], 'createdAt': '2026-10-20T08:00:00Z', 'updatedAt': 1790000000000},
        {'id': 'e_xss', 'date': '2026-10-21', 'title': '危险测试', 'text': XSS_TEXT,
         'tags': [], 'createdAt': '2026-10-21T08:00:00Z', 'updatedAt': 1790000000000},
        {'id': 'e_plain', 'date': '2026-10-22', 'title': '', 'text': PLAIN_TEXT,
         'tags': [], 'createdAt': '2026-10-22T08:00:00Z', 'updatedAt': 1790000000000},
    ],
    'tasks': [], 'money': {}, 'quit': {},
}, 'rev': 3}


class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=DOC, **kw)

    def log_message(self, *a):
        pass

    def _j(self, obj, status=200, eh=None):
        b = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(b)))
        self.send_header('Cache-Control', 'no-store')
        for k, v in (eh or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(b)

    def _sid(self):
        for p in (self.headers.get('Cookie', '') or '').split(';'):
            p = p.strip()
            if p.startswith('sid='):
                return p[4:]
            return ''

    def do_GET(self):
        if self.path.startswith('/api.php'):
            a = self.path.split('action=')[-1].split('&')[0]
            if a == 'status':
                self._j({'ok': True, 'installed': True})
            elif a == 'me':
                self._j({'ok': True, 'user': sessions.get(self._sid()), 'csrf': 'x',
                         'registration_open': False, 'registration_mode': 'closed',
                         'need_invite': False, 'need_code': False, 'code_ready': False})
            elif a == 'push_status':
                self._j({'ok': True, 'enabled': False, 'webhook': '', 'sent_today': 0,
                         'last_sent': '', 'recent': []})
            elif a == 'push_preview':
                self._j({'ok': True, 'date': D, 'items': []})
            elif a == 'mail_status':
                self._j({'ok': True, 'crypto_ready': True, 'recipient': 'test@example.com',
                         'config': {'host': '', 'port': 465, 'secure': 'ssl', 'user': '', 'from': '',
                                    'name': '', 'hasSecret': False, 'enabled': False,
                                    'lastError': '', 'lastTestAt': ''}})
            elif a == 'ics_status':
                self._j({'ok': True, 'url': None})
            elif a == 'load':
                self._j({'ok': True, 'data': board['data'], 'rev': board['rev'],
                         'updated_at': 1792813000000})
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
                self._j({'ok': True, 'user': USER, 'csrf': 'x', 'registration_open': False},
                        eh={'Set-Cookie': 'sid=' + sid + '; Path=/'})
            elif a in ('save', 'force'):
                board['data'] = body['data']
                board['rev'] += 1
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


def nav(pg, v):
    pg.evaluate("v => { const b=document.querySelector('[data-nav=\"'+v+'\"]'); if(b) b.click(); }", v)
    pg.wait_for_timeout(450)


def essays():
    return board['data'].get('essays') or []


with sync_playwright() as pw:
    br = pw.chromium.launch(channel='chrome')
    ctx = br.new_context(viewport={'width': 1440, 'height': 1000})
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.on('dialog', lambda d: d.accept())

    pg.clock.install(time=datetime(2026, 10, 24, 20, 0, 0))
    pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
    pg.wait_for_timeout(600)
    pg.click('[data-act="cloud-login"]')
    pg.wait_for_timeout(400)
    pg.fill('input[name="email"]', 'test@example.com')
    pg.fill('input[name="password"]', 'test@example.com')
    pg.click('form.modal-card button[type="submit"]')
    pg.wait_for_timeout(2800)
    nav(pg, 'essays')

    print('\n===== 1. 卡片摘要按 Markdown 渲染 =====')
    cards = pg.locator('.essay-card')
    chk('三张随笔卡', cards.count() == 3, str(cards.count()))
    card_md = cards.filter(has_text='今天的标题').first
    prev_html = card_md.locator('.essay-text').inner_html()
    chk('粗体成了 <strong>', '<strong>粗体</strong>' in prev_html, prev_html[:240])
    chk('斜体成了 <em>', '<em>斜体</em>' in prev_html, prev_html[:240])
    chk('代码成了 <code>', '<code>code</code>' in prev_html, prev_html[:240])
    chk('摘要里不再有 ** 字面', '**' not in prev_html, prev_html[:240])
    chk('列表项前面带 ·', 'md-li' in prev_html, prev_html[:240])

    print('\n===== 2. 点卡片打开全文弹窗 =====')
    card_md.click()
    pg.wait_for_timeout(700)
    chk('弹窗打开了', pg.locator('.essay-view').count() == 1)
    chk('标题对', pg.inner_text('.essay-view h3').strip() == '今天的标题', pg.inner_text('.essay-view h3'))
    chk('有日期与字数', '2026-10-20' in pg.inner_text('.essay-view') and '字' in pg.inner_text('.essay-view'),
        pg.inner_text('.essay-view')[:120])
    body_html = pg.locator('.essay-body').inner_html()
    chk('标题渲染成 h1', '<h1>今天的标题</h1>' in body_html, body_html[:240])
    chk('列表渲染成 ul/li', '<ul>' in body_html and '<li>列表第一项</li>' in body_html, body_html[:300])
    chk('引用渲染成 blockquote', '<blockquote>引用一句话。</blockquote>' in body_html, body_html[:300])
    chk('代码渲染成 code', '<code>code</code>' in body_html, body_html[:300])
    href = pg.eval_on_selector_all('.essay-body a', 'e=>e.map(x=>x.getAttribute("href"))')
    chk('外链保留且指向原地址', href == ['https://todo.csl88.top/'], json.dumps(href, ensure_ascii=False))
    chk('链接是新窗口打开', pg.eval_on_selector_all('.essay-body a', 'e=>e.map(x=>x.getAttribute("rel"))') == ['noopener noreferrer'],
        pg.eval_on_selector_all('.essay-body a', 'e=>e.map(x=>x.getAttribute("rel"))'))

    print('\n===== 3. XSS 与危险链接 =====')
    pg.click('.essay-view [data-act="close-modal"]')
    pg.wait_for_timeout(400)
    cards.filter(has_text='危险测试').first.click()
    pg.wait_for_timeout(700)
    xss_html = pg.locator('.essay-body').inner_html()
    chk('没有真 script 标签', pg.locator('.essay-body script').count() == 0, xss_html[:200])
    chk('script 字面被转义', '&lt;script&gt;' in xss_html, xss_html[:240])
    chk('img 没有 onerror', pg.locator('.essay-body img[onerror]').count() == 0, xss_html[:240])
    hrefs = pg.eval_on_selector_all('.essay-body a', 'e=>e.map(x=>x.getAttribute("href"))')
    chk('javascript: 链接被丢掉', all(not (h or '').lower().startswith('javascript:') for h in hrefs),
        json.dumps(hrefs, ensure_ascii=False))
    chk('https 链接照常保留', 'https://example.com/a' in (hrefs or []), json.dumps(hrefs, ensure_ascii=False))

    print('\n===== 4. 弹窗里点「编辑」 =====')
    pg.click('.essay-view [data-act="close-modal"]')
    pg.wait_for_timeout(400)
    cards.filter(has_text='今天的标题').first.click()
    pg.wait_for_timeout(700)
    pg.click('.essay-view [data-act="essay-edit"]')
    pg.wait_for_timeout(700)
    chk('进了编辑弹窗', pg.locator('#essay-form').count() == 1)
    chk('正文带回来了', MD_TEXT.strip()[:12] in pg.input_value('#essay-form [name="text"]'),
        pg.input_value('#essay-form [name="text"]')[:60])

    print('\n===== 5. 编辑器里的「预览」 =====')
    chk('有预览按钮', pg.locator('#essay-form [data-act="essay-md-toggle"]').count() == 1)
    pg.click('#essay-form [data-act="essay-md-toggle"]')
    pg.wait_for_timeout(500)
    chk('预览区出现了', pg.locator('#essay-md-preview').is_visible())
    pv_html = pg.locator('#essay-md-preview').inner_html()
    chk('预览里是渲染后的粗体', '<strong>粗体</strong>' in pv_html, pv_html[:240])
    chk('预览里没有 ** 字面', '**' not in pv_html, pv_html[:240])
    chk('文本框藏起来了', not pg.locator('#essay-form [name="text"]').is_visible())
    chk('按钮变成「继续编辑」', pg.inner_text('#essay-form [data-act="essay-md-toggle"]').strip() == '继续编辑',
        pg.inner_text('#essay-form [data-act="essay-md-toggle"]'))
    pg.click('#essay-form [data-act="essay-md-toggle"]')
    pg.wait_for_timeout(500)
    chk('再点回到编辑', pg.locator('#essay-form [name="text"]').is_visible())
    chk('按钮变回「预览」', pg.inner_text('#essay-form [data-act="essay-md-toggle"]').strip() == '预览',
        pg.inner_text('#essay-form [data-act="essay-md-toggle"]'))

    print('\n===== 6. 弹窗里能删 =====')
    pg.click('#essay-form [data-act="close-modal"]')
    pg.wait_for_timeout(400)
    n_before = len(essays())
    cards.filter(has_text='危险测试').first.click()
    pg.wait_for_timeout(700)
    pg.click('.essay-view [data-act="essay-del"]')
    pg.wait_for_timeout(1400)
    chk('这篇被删掉了', len(essays()) == n_before - 1, str(len(essays())))
    chk('列表里也没了', pg.locator('.essay-card', has_text='危险测试').count() == 0)

    print('\n===== 7. 全文按钮也能开 =====')
    card_md = pg.locator('.essay-card').filter(has_text='今天的标题').first
    card_md.locator('[data-act="essay-view"]').first.click()
    pg.wait_for_timeout(700)
    chk('弹窗打开了', pg.locator('.essay-view').count() == 1)
    pg.click('.essay-view [data-act="close-modal"]')
    pg.wait_for_timeout(400)

    print('\n===== 8. 新建的随笔带 Markdown =====')
    pg.click('[data-act="essay-new"]')
    pg.wait_for_timeout(600)
    pg.fill('#essay-form [name="title"]', '新写的')
    pg.fill('#essay-form [name="text"]', '这里是 **重点** 内容。')
    pg.click('#essay-form button[type="submit"]')
    pg.wait_for_timeout(1600)
    new_card = pg.locator('.essay-card', has_text='新写的').first
    chk('新卡片出来了', new_card.count() == 1)
    chk('摘要按 Markdown 渲染', '<strong>重点</strong>' in new_card.locator('.essay-text').inner_html(),
        new_card.locator('.essay-text').inner_html()[:160])
    chk('数据存下来了', any(e.get('title') == '新写的' for e in essays()),
        json.dumps(essays(), ensure_ascii=False)[:200])

    print('\n===== 9. 无 JS 报错 =====')
    chk('没有 JS 错误', not errs, str(errs[:3]))

    br.close()

print('\n===== 结果：%d 通过 / %d 失败 =====' % (PASS, FAIL))
if FAILS:
    for n, d in FAILS:
        print('  FAIL: %s  << %s' % (n, d))
    sys.exit(1)
print('全部通过')
