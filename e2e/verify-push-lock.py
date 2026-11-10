# -*- coding: utf-8 -*-
"""配置页 · 手机推送的 webhook 持久化（v77）。

两件事：
1. 地址存在服务器（users.push_webhook），切设备/换浏览器照样在，
   推送也不会失效 —— 之前输入框空着是 `pushLoad` 的重绘条件还写着 settings。
2. 平时只读，点「修改链接」才放开；清空才删地址，不清空就一直保留。
"""
import os, sys, json
from datetime import datetime

ROOT = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo'
head = open(os.path.join(ROOT, 'e2e', 'verify-batch4.py'), encoding='utf-8').read().split('with sync_playwright() as p:')[0]
sys.argv = [sys.argv[0]]
exec(head)

from playwright.sync_api import sync_playwright

URL = 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=abc123def456'
URL2 = 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=zzz999'

PUSH = {'webhook': URL, 'enabled': True}

_og_get = H.do_GET


def _get(self):
    if 'action=push_status' in self.path:
        self._j({'ok': True, 'enabled': PUSH['enabled'], 'webhook': PUSH['webhook'],
                 'sent_today': 0, 'last_sent': '', 'recent': []})
        return
    if 'action=push_preview' in self.path:
        self._j({'ok': True, 'date': '2026-11-10', 'items': []})
        return
    _og_get(self)


H.do_GET = _get

_og_post = H.do_POST


def _post(self):
    if 'action=push_save' in self.path:
        n = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(n) or b'{}')
        PUSH['webhook'] = str(body.get('webhook') or '')
        PUSH['enabled'] = bool(body.get('enabled')) and PUSH['webhook'] != ''
        self._j({'ok': True, 'enabled': PUSH['enabled']})
        return
    if 'action=push_test' in self.path:
        self._j({'ok': True})
        return
    _og_post(self)


H.do_POST = _post

PASS = FAIL = 0
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


def open_cfg(pg):
    pg.evaluate("() => { const b=document.querySelector('[data-nav=\"config\"]'); if(b) b.click(); }")
    pg.wait_for_timeout(1600)   # 等 push_status 回来并重绘


def hook(pg):
    return pg.evaluate("""() => {
        const el = document.getElementById('push-hook');
        if (!el) return null;
        return {val: el.value, ro: el.readOnly, cls: el.className};
    }""")


def btns(pg):
    return pg.evaluate("""() => [...document.querySelectorAll('.push-center .btn-row .btn')]
        .map(b => (b.textContent || '').trim())""")


def login(pg):
    pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
    pg.wait_for_timeout(500)
    if pg.locator('[data-act="cloud-login"]').count():
        pg.click('[data-act="cloud-login"]')
        pg.wait_for_timeout(400)
        pg.fill('input[name="email"]', 'test@sl00.top')
        pg.fill('input[name="password"]', 'test@sl00.top')
        pg.click('form.modal-card button[type="submit"]')
        pg.wait_for_timeout(2600)


with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)

    print('[1] 切设备：新浏览器打开配置页，地址应该在')
    ctx = br.new_context(viewport={'width': 1512, 'height': 1000})
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)[:180]))
    pg.on('dialog', lambda d: d.accept())
    pg.clock.install(time=datetime(2026, 11, 10, 10, 0, 0))
    login(pg)
    open_cfg(pg)
    h = hook(pg)
    chk('输入框里有地址', bool(h) and h['val'] == URL, str(h))
    chk('是只读的', bool(h) and h['ro'], str(h))
    chk('带 is-locked 样式', bool(h) and 'is-locked' in h['cls'], str(h))
    b = btns(pg)
    chk('按钮是「修改链接」', '修改链接' in b, str(b))
    chk('没有「保存」按钮', '保存' not in b, str(b))
    chk('提示写「换手机也会保留」',
        '换手机' in (pg.locator('.push-center .ics-hint').first.text_content() or ''),
        pg.locator('.push-center .ics-hint').first.text_content() or '')

    print('[2] 只读态点「暂停推送」不能清掉地址')
    pg.click('[data-act="push-off"]')
    pg.wait_for_timeout(900)
    chk('服务端地址还在', PUSH['webhook'] == URL, PUSH['webhook'])
    chk('推送已停用', PUSH['enabled'] is False, str(PUSH['enabled']))
    h = hook(pg)
    chk('页面上的地址还在', bool(h) and h['val'] == URL, str(h))

    print('[3] 点「修改链接」才放开')
    pg.click('[data-act="push-edit"]')
    pg.wait_for_timeout(500)
    h = hook(pg)
    chk('变成可编辑', bool(h) and not h['ro'], str(h))
    chk('框被清空（等新地址）', bool(h) and h['val'] == '', str(h))
    chk('去掉了 is-locked', bool(h) and 'is-locked' not in h['cls'], str(h))
    b = btns(pg)
    chk('出现「保存」和「取消」', '保存' in b and '取消' in b, str(b))
    chk('没有「修改链接」了', '修改链接' not in b, str(b))

    print('[4] 取消：原样还原')
    pg.click('[data-act="push-cancel"]')
    pg.wait_for_timeout(500)
    h = hook(pg)
    chk('回到只读且值不变', bool(h) and h['ro'] and h['val'] == URL, str(h))
    chk('服务端没被改', PUSH['webhook'] == URL, PUSH['webhook'])

    print('[5] 改成一个新地址')
    pg.click('[data-act="push-edit"]')
    pg.wait_for_timeout(400)
    pg.fill('#push-hook', URL2)
    pg.click('[data-act="push-save"]')
    pg.wait_for_timeout(900)
    chk('服务端换成了新地址', PUSH['webhook'] == URL2, PUSH['webhook'])
    chk('保存后重新启用', PUSH['enabled'] is True, str(PUSH['enabled']))
    h = hook(pg)
    chk('页面回到只读、显示新地址', bool(h) and h['ro'] and h['val'] == URL2, str(h))

    print('[6] 编辑态清空 = 真的删掉')
    pg.click('[data-act="push-edit"]')
    pg.wait_for_timeout(400)
    pg.click('[data-act="push-save"]')   # dialog 自动确认
    pg.wait_for_timeout(900)
    chk('服务端地址被清空', PUSH['webhook'] == '', repr(PUSH['webhook']))
    chk('推送停用', PUSH['enabled'] is False, str(PUSH['enabled']))
    h = hook(pg)
    chk('清空后框保持可编辑（没有地址可锁）', bool(h) and not h['ro'], str(h))

    print('[7] 再填一个新地址后刷新，仍然保留')
    pg.fill('#push-hook', URL)
    pg.click('[data-act="push-save"]')
    pg.wait_for_timeout(900)
    pg.reload(wait_until='networkidle')
    pg.wait_for_timeout(2600)
    open_cfg(pg)
    h = hook(pg)
    chk('刷新后地址还在且只读', bool(h) and h['val'] == URL and h['ro'], str(h))
    chk('刷新后没有 JS 异常', not errs, str(errs))
    ctx.close()

    print('[8] 换一台设备（全新 context）')
    ctx2 = br.new_context(viewport={'width': 1512, 'height': 1000})
    pg2 = ctx2.new_page()
    errs2 = []
    pg2.on('pageerror', lambda e: errs2.append(str(e)[:180]))
    pg2.on('dialog', lambda d: d.accept())
    pg2.clock.install(time=datetime(2026, 11, 10, 10, 0, 0))
    login(pg2)
    open_cfg(pg2)
    h = hook(pg2)
    chk('新设备上也有地址', bool(h) and h['val'] == URL, str(h))
    chk('新设备上是只读的', bool(h) and h['ro'], str(h))
    chk('新设备无 JS 异常', not errs2, str(errs2))
    ctx2.close()
    br.close()

print()
print('===== webhook 持久化：%d 通过 / %d 失败 =====' % (PASS, FAIL))
if FAILS:
    print('失败项：', FAILS)
