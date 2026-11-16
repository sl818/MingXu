# -*- coding: utf-8 -*-
"""线上移动端（390×844 触摸）全页面渲染 + 溢出 + 关键交互。"""
import os, sys, datetime
from playwright.sync_api import sync_playwright

BASE = 'https://your-domain.example/'
EMAIL = 'test@example.com'
PWD = 'test@example.com'
SHOTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'shots', 'live')
os.makedirs(SHOTS, exist_ok=True)

PASS = FAIL = 0
FAILS = []


def rec(name, ok, detail=''):
    global PASS, FAIL
    if ok:
        PASS += 1
        print('  \u2713 %s' % name)
    else:
        FAIL += 1
        FAILS.append((name, detail))
        print('  \u2717 %s  << %s' % (name, detail))


def nav(pg, v, wait=800):
    # 移动端侧栏隐藏，data-nav 会命中多个节点，只点可见的那个
    pg.evaluate("v => { const b=[...document.querySelectorAll('[data-nav=\"'+v+'\"]')].find(x=>x.offsetParent!==null); if(b) b.click(); }", v)
    pg.wait_for_timeout(wait)


def ovf(pg):
    return pg.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")


with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)
    ctx = br.new_context(viewport={'width': 390, 'height': 844},
                         has_touch=True, is_mobile=True, device_scale_factor=2)
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)[:180]))
    pg.on('console', lambda m: errs.append('console:%s' % m.text[:120])
          if m.type == 'error' else None)
    pg.on('dialog', lambda d: d.accept())

    pg.goto(BASE, wait_until='networkidle', timeout=60000)
    pg.wait_for_timeout(1500)
    if pg.locator('[data-act="cloud-login"]').count():
        pg.click('[data-act="cloud-login"]')
        pg.wait_for_timeout(700)
        pg.fill('input[name="email"]', EMAIL)
        pg.fill('input[name="password"]', PWD)
        pg.click('form.modal-card button[type="submit"]')
        pg.wait_for_timeout(5000)
    rec('登录成功', pg.locator('#mobile-nav').count() == 1)

    print('\n[1] 底部 4 tab 逐个切')
    for v in ('today', 'meds', 'board'):
        try:
            nav(pg, v, wait=900)
            o = ovf(pg)
            rec('tab %-6s 渲染无溢出' % v, o <= 0, 'ovf=%d' % o)
            pg.screenshot(path=os.path.join(SHOTS, 'm-%s.png' % v))
        except Exception as e:
            rec('tab %-6s 渲染无溢出' % v, False, str(e)[:80])

    print('\n[2] 「更多」抽屉里的其余页面')
    try:
        pg.click('[data-act="more-open"]')
        pg.wait_for_timeout(700)
        rec('更多抽屉打开', pg.locator('.page-sheet').count() >= 1)
        for v in ('weight', 'essays', 'calendar', 'stats', 'settings'):
            try:
                nav(pg, v, wait=900)
                o = ovf(pg)
                rec('页面 %-8s 无溢出' % v, o <= 0, 'ovf=%d' % o)
                pg.screenshot(path=os.path.join(SHOTS, 'm-%s.png' % v))
            except Exception as e:
                rec('页面 %-8s 无溢出' % v, False, str(e)[:80])
    except Exception as e:
        rec('更多抽屉打开', False, str(e)[:80])

    print('\n[3] 命令面板（悬浮按钮）')
    try:
        pg.keyboard.press('Escape')   # 先关掉可能还开着的「更多」抽屉
        pg.wait_for_timeout(400)
        pg.evaluate("() => { const b=document.querySelector('.search-fab'); if(b) b.click(); }")
        pg.wait_for_timeout(600)
        pg.fill('#search-input', '+1 喝水')
        pg.wait_for_timeout(400)
        rec('命令卡在手机端显示', pg.evaluate("() => !!document.querySelector('.se-cmd')"))
        pg.keyboard.press('Escape')
        pg.wait_for_timeout(400)
    except Exception as e:
        rec('命令卡在手机端显示', False, str(e)[:80])

    print('\n[4] 全程 JS 报错')
    rec('无 JS/console 错误', not errs, '; '.join(errs[:5]))

    br.close()

print('\n==============================================')
print('移动端 E2E：%d 通过 / %d 失败' % (PASS, FAIL))
for name, detail in FAILS:
    print('  失败：%s  << %s' % (name, detail))
sys.exit(0 if FAIL == 0 else 1)
