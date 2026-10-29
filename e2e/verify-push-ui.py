# -*- coding: utf-8 -*-
"""手机推送面板的界面验证：填地址 / 保存 / 测试 / 暂停。

mock 服务原脚本没有 push_* 路由，这里在 exec 之后补上。
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

# ---------- 给 mock 补推送接口 ----------
MOCK = {
    'enabled': False,
    'webhook': '',
    'saves': [],        # 每次 push_save 收到的 body
    'tests': 0,         # push_test 被调用次数
    'fail_test': False,  # 模拟发送失败
    'bad_save': '',      # 模拟保存被拒（回 400）
}

_orig_get = H.do_GET
_orig_post = H.do_POST


def _get(self):
    if self.path.startswith('/api.php') and 'action=push_status' in self.path:
        self._j({
            'ok': True,
            'enabled': MOCK['enabled'],
            'webhook': MOCK['webhook'],
            'sent_today': 3 if MOCK['enabled'] else 0,
            'last_sent': '2026-10-25 08:00:00' if MOCK['enabled'] else '',
        })
        return
    _orig_get(self)


def _post(self):
    if self.path.startswith('/api.php') and 'action=push_save' in self.path:
        n = int(self.headers.get('Content-Length', 0))
        raw = self.rfile.read(n) if n else b'{}'
        try:
            body = json.loads(raw.decode('utf-8'))
        except Exception:
            body = {}
        MOCK['saves'].append(body)
        if MOCK['bad_save']:
            self.send_response(400)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps(
                {'ok': False, 'error': MOCK['bad_save']}, ensure_ascii=False).encode('utf-8'))
            return
        MOCK['webhook'] = body.get('webhook', '')
        MOCK['enabled'] = bool(body.get('enabled')) and MOCK['webhook'] != ''
        self._j({'ok': True, 'enabled': MOCK['enabled']})
        return
    if self.path.startswith('/api.php') and 'action=push_test' in self.path:
        n = int(self.headers.get('Content-Length', 0))
        if n:
            self.rfile.read(n)
        MOCK['tests'] += 1
        if MOCK['fail_test']:
            self.send_response(502)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps(
                {'ok': False, 'error': '没发出去：webhook 地址无效（key 错了）'},
                ensure_ascii=False).encode('utf-8'))
            return
        self._j({'ok': True})
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


HOOK = 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=11111111-2222-3333-4444-555555555555'


def box_state(pg):
    return pg.evaluate("""() => {
        const b = [...document.querySelectorAll('.ntf-box')]
          .find(x => /手机推送/.test(x.textContent));
        if (!b) return null;
        const st = b.querySelector('.ntf-state');
        const dot = b.querySelector('.ntf-dot');
        return {state: st ? st.textContent.trim() : '',
                on: !!dot && dot.className.indexOf('on') >= 0};
    }""")


def toast_text(pg):
    el = pg.locator('#toast.show')
    return el.inner_text() if el.count() else ''


with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)
    ctx = br.new_context(viewport={'width': 1440, 'height': 950})
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)[:180]))
    pg.clock.install(time=datetime(2026, 10, 25, 10, 0, 0))
    pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
    pg.wait_for_timeout(600)
    pg.click('[data-act="cloud-login"]')
    pg.wait_for_timeout(400)
    pg.fill('input[name="email"]', 'test@sl00.top')
    pg.fill('input[name="password"]', 'test@sl00.top')
    pg.click('form.modal-card button[type="submit"]')
    pg.wait_for_timeout(2600)

    print('\n[1] 还没配置时')
    nav(pg, 'settings')
    pg.wait_for_timeout(900)
    chk('设置页有「手机推送」区块',
        pg.locator('.ntf-head', has_text='手机推送').count() == 1)
    st = box_state(pg)
    chk('状态是「还没设置」', st and '还没设置' in st['state'], st)
    chk('状态点是灭的', st and not st['on'])
    chk('有地址输入框', pg.locator('#push-hook').count() == 1)
    chk('输入框初始为空',
        (pg.locator('#push-hook').input_value() or '') == '')
    chk('输入框可编辑（不是只读）',
        pg.locator('#push-hook').get_attribute('readonly') is None)
    chk('有测试按钮', pg.locator('[data-act="push-test"]').count() == 1)
    chk('未开启时没有「暂停推送」', pg.locator('[data-act="push-off"]').count() == 0)
    chk('提示里写了要建「内部群」',
        '内部群' in pg.locator('.ics-hint').last.inner_text())
    chk('提示里提醒地址不要外传',
        '别贴到公开的地方' in pg.locator('.ics-warn').last.inner_text())

    print('\n[2] 地址为空时点测试')
    before = len(MOCK['saves'])
    pg.locator('[data-act="push-test"]').click()
    pg.wait_for_timeout(600)
    chk('不发保存请求', len(MOCK['saves']) == before, 'saves=%d' % len(MOCK['saves']))
    chk('也不发测试请求', MOCK['tests'] == 0, 'tests=%d' % MOCK['tests'])
    chk('提示先填地址', '先把 webhook' in toast_text(pg), toast_text(pg))

    print('\n[3] 填地址并发测试')
    pg.fill('#push-hook', HOOK)
    pg.locator('[data-act="push-test"]').click()
    pg.wait_for_timeout(900)
    chk('先保存了一次', len(MOCK['saves']) == before + 1, 'saves=%d' % len(MOCK['saves']))
    last = MOCK['saves'][-1] if MOCK['saves'] else {}
    chk('保存时带上完整地址', last.get('webhook') == HOOK, str(last)[:80])
    chk('保存时请求开启', last.get('enabled') is True, str(last.get('enabled')))
    chk('随后调用了发送测试', MOCK['tests'] == 1, 'tests=%d' % MOCK['tests'])
    chk('提示发出去了', '发出去了' in toast_text(pg), toast_text(pg))
    st = box_state(pg)
    chk('状态变成已开启', st and ('已开启' in st['state']), st)
    chk('状态点点亮', st and st['on'])
    chk('出现「暂停推送」按钮', pg.locator('[data-act="push-off"]').count() == 1)
    # 刚配置完还没真发过，这里不该出现「最近一次发送」——它只在有记录时显示
    chk('还没有发送记录时不显示时间',
        '最近一次发送' not in pg.evaluate(
            """() => { const b=[...document.querySelectorAll('.ntf-box')]
                 .find(x=>/手机推送/.test(x.textContent)); return b ? b.textContent : ''; }"""))

    print('\n[4] 暂停')
    pg.locator('[data-act="push-off"]').click()
    pg.wait_for_timeout(800)
    last = MOCK['saves'][-1] if MOCK['saves'] else {}
    chk('暂停时请求关闭', last.get('enabled') is False, str(last.get('enabled')))
    chk('暂停时保留地址', last.get('webhook') == HOOK, str(last.get('webhook'))[:40])
    st = box_state(pg)
    chk('状态变成已填地址未开启', st and '未开启' in st['state'], st)
    chk('暂停按钮消失', pg.locator('[data-act="push-off"]').count() == 0)
    chk('输入框里地址还在',
        pg.locator('#push-hook').input_value() == HOOK)

    print('\n[5] 地址非法时后端拒绝')
    MOCK['bad_save'] = '这条地址不像是企业微信机器人。正确形式是 https://qyapi.weixin.qq.com/...'
    pg.fill('#push-hook', 'https://example.com/hook')
    pg.locator('[data-act="push-test"]').click()
    pg.wait_for_timeout(800)
    chk('把后端的错误显示出来',
        '不像是企业微信机器人' in toast_text(pg), toast_text(pg))

    print('\n[6] 发送失败时的提示')
    MOCK['bad_save'] = ''
    pg.fill('#push-hook', HOOK)
    MOCK['fail_test'] = True
    pg.locator('[data-act="push-test"]').click()
    pg.wait_for_timeout(900)
    chk('失败原因透传到界面',
        'webhook 地址无效' in toast_text(pg), toast_text(pg))

    print('\n[7] 刷新后状态还在')
    MOCK['fail_test'] = False
    MOCK['enabled'] = True
    pg.reload(wait_until='networkidle')
    pg.wait_for_timeout(2400)
    nav(pg, 'settings')
    pg.wait_for_timeout(900)
    st = box_state(pg)
    chk('重新打开仍是已开启', st and '已开启' in st['state'], st)
    chk('地址被回填', pg.locator('#push-hook').input_value() == HOOK,
        (pg.locator('#push-hook').input_value() or '')[:50])
    txt = pg.evaluate(
        """() => { const b=[...document.querySelectorAll('.ntf-box')]
             .find(x=>/手机推送/.test(x.textContent)); return b ? b.textContent : ''; }""")
    chk('有记录时显示最近一次发送时间', '最近一次发送' in txt, txt[-60:])
    chk('显示今天已发条数', '今天已发 3 条' in txt, txt[-60:])

    print('\n[8] 手机端的排版')
    pg.set_viewport_size({'width': 390, 'height': 844})
    pg.wait_for_timeout(600)
    m = pg.evaluate("""() => {
        const b = [...document.querySelectorAll('.ntf-box')]
          .find(x => /手机推送/.test(x.textContent));
        const i = document.getElementById('push-hook');
        const r = i ? i.getBoundingClientRect() : null;
        return {
          ovf: document.documentElement.scrollWidth > document.documentElement.clientWidth,
          boxW: b ? Math.round(b.getBoundingClientRect().width) : 0,
          inputW: r ? Math.round(r.width) : 0,
          inputIn: r ? (r.left >= 0 && r.right <= window.innerWidth) : false
        };
    }""")
    chk('页面没有横向溢出', not m['ovf'], str(m))
    chk('输入框没有超出边界', m['inputIn'], str(m))
    chk('输入框撑满容器宽度',
        m['boxW'] > 0 and m['inputW'] >= m['boxW'] - 40,
        'box=%d input=%d' % (m['boxW'], m['inputW']))
    pg.screenshot(path=os.path.join(ROOT, 'e2e', 'shots', 'v39-push-mobile.png'))

    print('\n[9] 控制台')
    chk('没有 JS 异常', not errs, '; '.join(errs[:2]))

    br.close()

print('\n----------------------------')
print('通过 %d 项，失败 %d 项' % (PASS, len(FAILS)))
for name, detail in FAILS:
    print('  失败：%s  << %s' % (name, detail))
sys.exit(0 if not FAILS else 1)
