# -*- coding: utf-8 -*-
"""日历订阅面板的界面验证：生成链接 / 复制 / 重新生成 / 状态展示。

mock 服务原脚本没有 ics_status / ics_reset，这里在 exec 之后补上路由。
"""
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
head = io.open(os.path.join(ROOT, 'e2e', 'verify-batch4.py'), encoding='utf-8').read()
head = head.split('with sync_playwright() as p:')[0]
sys.argv = [sys.argv[0]]
exec(head)

# ---------- 给 mock 补两个订阅接口 ----------
MOCK = {'url': None, 'status': 0, 'reset': 0}

_orig_get = H.do_GET
_orig_post = H.do_POST


def _get(self):
    if self.path.startswith('/api.php') and 'action=ics_status' in self.path:
        MOCK['status'] += 1
        self._j({'ok': True, 'url': MOCK['url']})
        return
    _orig_get(self)


def _post(self):
    if self.path.startswith('/api.php') and 'action=ics_reset' in self.path:
        MOCK['reset'] += 1
        n = int(self.headers.get('Content-Length', 0))
        if n:
            self.rfile.read(n)
        MOCK['url'] = ('https://your-domain.example/api.php?ics=%064x.ics' % MOCK['reset'])
        self._j({'ok': True, 'url': MOCK['url']})
        return
    _orig_post(self)


H.do_GET = _get
H.do_POST = _post

PASS = 0
FAILS = []


def chk(name, ok, detail=''):
    global PASS
    if ok:
        PASS += 1
        print('  \u2713 %s' % name)
    else:
        FAILS.append((name, detail))
        print('  \u2717 %s  << %s' % (name, detail))


DIALOG = {'accept': True}

with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)
    ctx = br.new_context(viewport={'width': 1440, 'height': 950})
    ctx.grant_permissions(['clipboard-read', 'clipboard-write'],
                          origin='http://127.0.0.1:%d' % port)
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)[:180]))
    pg.on('dialog', lambda d: d.accept() if DIALOG['accept'] else d.dismiss())
    pg.clock.install(time=datetime(2026, 10, 25, 10, 0, 0))
    pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
    pg.wait_for_timeout(600)
    pg.click('[data-act="cloud-login"]')
    pg.wait_for_timeout(400)
    pg.fill('input[name="email"]', 'test@example.com')
    pg.fill('input[name="password"]', 'test@example.com')
    pg.click('form.modal-card button[type="submit"]')
    pg.wait_for_timeout(2600)

    print('\n[1] 还没生成时')
    nav(pg, 'settings')
    pg.wait_for_timeout(900)
    chk('设置页有「日历订阅」区块',
        pg.locator('.ntf-head', has_text='日历订阅').count() == 1)
    chk('没有订阅输入框', pg.locator('#ics-url').count() == 0)
    gen = pg.locator('[data-act="ics-reset"]')
    chk('给出「生成订阅链接」按钮', gen.count() == 1 and '生成订阅链接' in gen.inner_text(),
        gen.inner_text() if gen.count() else '')
    chk('导出文件按钮仍在', pg.locator('[data-act="ics-export"]').count() == 1)
    chk('状态文案是「还没生成」',
        any('还没生成' in (x or '') for x in
            pg.evaluate("() => [...document.querySelectorAll('.ntf-state')].map(e=>e.textContent)")))

    print('\n[2] 生成之后')
    gen.click()
    pg.wait_for_timeout(900)
    inp = pg.locator('#ics-url')
    chk('出现订阅地址输入框', inp.count() == 1)
    val = inp.input_value() if inp.count() else ''
    chk('地址是单参数形式（不带 & ，免得被客户端截断）',
        '?ics=' in val and '&' not in val, val[:70])
    chk('地址以 .ics 结尾（安卓日历会按后缀判断）', val.endswith('.ics'), val[-16:])
    chk('token 是 64 位十六进制',
        bool(__import__('re').search(r'ics=[0-9a-f]{64}\.ics$', val)), val[-24:])
    chk('输入框只读', inp.get_attribute('readonly') is not None if inp.count() else False)
    chk('有复制按钮', pg.locator('[data-act="ics-copy"]').count() == 1)
    chk('有重新生成按钮', pg.locator('[data-act="ics-reset"]').count() == 1)
    chk('有导出文件按钮', pg.locator('[data-act="ics-export"]').count() == 1)
    chk('状态点变成已开启',
        pg.evaluate("""() => {
            const box = [...document.querySelectorAll('.ntf-box')]
              .find(b => /日历订阅/.test(b.textContent));
            const dot = box ? box.querySelector('.ntf-dot') : null;
            return !!dot && dot.className.indexOf('on') >= 0;
        }"""))
    chk('提示里写了 iPhone 的添加路径',
        'iPhone' in pg.locator('.ics-hint').first.inner_text())
    chk('提示里提醒不要外传',
        '别发给别人' in pg.locator('.ics-warn').first.inner_text())

    print('\n[3] 复制')
    pg.locator('[data-act="ics-copy"]').click()
    pg.wait_for_timeout(600)
    clip = pg.evaluate("() => navigator.clipboard.readText()")
    chk('剪贴板拿到同一条地址', clip == val, (clip or '')[:50])
    chk('弹出复制提示', pg.locator('#toast.show').count() == 1)

    print('\n[4] 重新生成')
    first = val
    DIALOG['accept'] = True
    pg.locator('[data-act="ics-reset"]').click()
    pg.wait_for_timeout(1000)
    second = pg.locator('#ics-url').input_value()
    chk('确认后地址变了', second != first, second[-16:])
    chk('新地址同样是 64 位 token 且带 .ics',
        bool(__import__('re').search(r'ics=[0-9a-f]{64}\.ics$', second)))

    DIALOG['accept'] = False
    pg.locator('[data-act="ics-reset"]').click()
    pg.wait_for_timeout(900)
    third = pg.locator('#ics-url').input_value()
    chk('取消确认时地址不变', third == second, third[-16:])
    DIALOG['accept'] = True

    print('\n[5] 状态缓存')
    before = MOCK['status']
    nav(pg, 'today')
    pg.wait_for_timeout(400)
    nav(pg, 'settings')
    pg.wait_for_timeout(700)
    chk('再进设置不会重复请求状态', MOCK['status'] == before, 'calls=%d' % MOCK['status'])
    chk('地址仍在', pg.locator('#ics-url').input_value() == second)

    print('\n[6] 手机端')
    mob = br.new_context(viewport={'width': 390, 'height': 844}, has_touch=True, is_mobile=True,
                         device_scale_factor=2)
    mpg = mob.new_page()
    merrs = []
    mpg.on('pageerror', lambda e: merrs.append(str(e)[:160]))
    mpg.on('dialog', lambda d: d.accept())
    mpg.clock.install(time=datetime(2026, 10, 25, 10, 0, 0))
    mpg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
    mpg.wait_for_timeout(500)
    mpg.click('[data-act="cloud-login"]')
    mpg.wait_for_timeout(400)
    mpg.fill('input[name="email"]', 'test@example.com')
    mpg.fill('input[name="password"]', 'test@example.com')
    mpg.click('form.modal-card button[type="submit"]')
    mpg.wait_for_timeout(2600)
    mpg.evaluate("() => { const a=document.querySelector('[data-act=\"more-open\"]'); if(a) a.click(); }")
    mpg.wait_for_timeout(500)
    mpg.evaluate("() => { const b=document.querySelector('[data-act=\"more-go\"][data-view=\"settings\"]')"
                 " || document.querySelector('[data-nav=\"settings\"]'); if(b) b.click(); }")
    mpg.wait_for_timeout(900)
    chk('手机端能进到设置并看到订阅块',
        mpg.locator('.ntf-head', has_text='日历订阅').count() == 1)
    chk('手机端无横向溢出',
        mpg.evaluate("() => document.documentElement.scrollWidth <= document.documentElement.clientWidth"))
    w = mpg.evaluate("""() => {
        const el = document.getElementById('ics-url');
        if (!el) return -1;
        const r = el.getBoundingClientRect();
        return Math.round(r.width);
    }""")
    chk('地址输入框没有撑出屏幕', w > 0 and w <= 370, 'w=%s' % w)
    chk('手机端无 JS 报错', len(merrs) == 0, '; '.join(merrs[:2]))
    mob.close()

    chk('全程无 JS 报错', len(errs) == 0, '; '.join(errs[:3]))
    br.close()

print('\n' + '=' * 46)
print('PASS %d / %d' % (PASS, PASS + len(FAILS)))
if FAILS:
    for n, d in FAILS:
        print('  FAIL: %s | %s' % (n, d))
    sys.exit(1)
print('订阅面板全部通过')
