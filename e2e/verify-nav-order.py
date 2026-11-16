# -*- coding: utf-8 -*-
"""导航顺序（v86）：组内 ↑↓，一个顺序喂三种排版 + 手机「更多」抽屉。

默认顺序是 today, meds, quit, board, habits, weight, essays, calendar, stats, config, settings。
「记录」组 7 项（前 7 个）、「回顾」组 4 项（后 4 个），两组之间不允许互换。
"""
import os, sys

ROOT = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo'
head = open(os.path.join(ROOT, 'e2e', 'verify-batch4.py'), encoding='utf-8').read().split('with sync_playwright() as p:')[0]
sys.argv = [sys.argv[0]]
exec(head)

from playwright.sync_api import sync_playwright

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


DEFAULT = ['today', 'meds', 'quit', 'board', 'money', 'habits', 'weight', 'essays',
           'calendar', 'stats', 'config', 'settings']
NAV_ORDER_JS = "() => [...document.querySelectorAll('#nav .nav-item')].map(b => b.dataset.nav)"


def login(pg):
    pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
    pg.wait_for_timeout(500)
    if pg.locator('[data-act="cloud-login"]').count():
        pg.click('[data-act="cloud-login"]')
        pg.wait_for_timeout(400)
        pg.fill('input[name="email"]', 'test@example.com')
        pg.fill('input[name="password"]', 'test@example.com')
        pg.click('form.modal-card button[type="submit"]')
        pg.wait_for_timeout(2600)


def go(pg, key):
    pg.evaluate("(k) => { const b=document.querySelector('[data-nav=\"'+k+'\"]'); if(b) b.click(); }", key)
    pg.wait_for_timeout(800)


def rows(pg):
    return pg.evaluate("""() => [...document.querySelectorAll('.no-row')].map(r => ({
        n: (r.querySelector('b') || {}).textContent || '',
        dis: [...r.querySelectorAll('.no-move .icon-btn')].map(b => b.disabled)
    }))""")


def move(pg, key, direction):
    pg.click('[data-act="nav-move"][data-key="%s"][data-dir="%d"]' % (key, direction))
    pg.wait_for_timeout(500)


with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome')
    pg = br.new_page(viewport={'width': 1440, 'height': 950})
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    login(pg)

    print('\n[1] 默认顺序没有被改动')
    chk('导航顺序 = 默认 11 项', pg.evaluate(NAV_ORDER_JS) == DEFAULT,
        str(pg.evaluate(NAV_ORDER_JS)))

    print('\n[2] 设置页的排序面板')
    go(pg, 'settings')
    r = rows(pg)
    chk('共 12 行', len(r) == 12, str(len(r)))
    chk('记录 8 项 + 回顾 4 项',
        [x['n'] for x in r] == ['今日', '用药', '戒烟', '待办', '清债', '习惯', '体重', '随笔',
                                '日历', '统计', '配置', '设置'], str([x['n'] for x in r]))
    chk('组首「今日」不能再上移', r[0]['dis'] == [True, False], str(r[0]))
    chk('记录组尾「随笔」不能再下移', r[7]['dis'] == [False, True], str(r[7]))
    chk('回顾组首「日历」不能再上移', r[8]['dis'] == [True, False], str(r[8]))
    chk('组尾「设置」不能再下移', r[11]['dis'] == [False, True], str(r[11]))

    print('\n[3] 把「统计」在回顾组内上移一格')
    move(pg, 'stats', -1)
    r2 = rows(pg)
    names2 = [x['n'] for x in r2]
    # 用「名字找下标」而不是硬编码位置：导航项以后再加，下标就会漂
    i_st = names2.index('统计')
    chk('面板里变成 统计 在 日历 前面', i_st + 1 == names2.index('日历'), str(names2[i_st - 1:]))
    chk('「统计」已经到组首，上移被禁用', r2[i_st]['dis'] == [True, False], str(r2[i_st]))
    keys2 = pg.evaluate(NAV_ORDER_JS)
    chk('导航条跟着变',
        keys2.index('stats') + 1 == keys2.index('calendar'), str(keys2))

    print('\n[4] 两种排版都用同一个顺序')
    for lay in ('wide', 'top'):
        pg.evaluate("(l) => document.querySelector('[data-act=\"set-layout\"][data-layout=\"'+l+'\"]').click()", lay)
        pg.wait_for_timeout(600)
        got = pg.evaluate(NAV_ORDER_JS)
        chk('排版 %s 的顺序一致' % lay,
            got.index('stats') + 1 == got.index('calendar'), str(got))

    print('\n[5] 刷新之后还在（存进了 state）')
    pg.wait_for_timeout(1200)
    login(pg)
    keys3 = pg.evaluate(NAV_ORDER_JS)
    chk('重新加载后顺序保持', keys3.index('stats') + 1 == keys3.index('calendar'), str(keys3))

    print('\n[6] 手机「更多」抽屉跟随同一个顺序')
    pg2 = br.new_page(viewport={'width': 390, 'height': 844})
    errs2 = []
    pg2.on('pageerror', lambda e: errs2.append(str(e)))
    login(pg2)
    pg2.click('[data-act="more-open"]')
    pg2.wait_for_timeout(600)
    sheet = pg2.evaluate("() => [...document.querySelectorAll('.ps-cell .ps-label')].map(e => e.textContent)")
    chk('抽屉里 统计 在 日历 之前',
        sheet.index('统计') < sheet.index('日历'), str(sheet))
    chk('抽屉里没有 tabbar 已有的今日/用药/待办',
        not any(k in sheet for k in ['今日', '用药', '待办']), str(sheet))
    chk('抽屉含设置', '设置' in sheet, str(sheet))
    chk('手机无 JS 异常', not errs2, str(errs2[:2]))
    pg2.close()

    print('\n[7] 恢复默认')
    go(pg, 'settings')
    pg.click('[data-act="nav-reset"]')
    pg.wait_for_timeout(600)
    chk('导航回到默认顺序', pg.evaluate(NAV_ORDER_JS) == DEFAULT, str(pg.evaluate(NAV_ORDER_JS)))
    chk('恢复按钮重新变禁用',
        pg.evaluate("() => document.querySelector('[data-act=\"nav-reset\"]').disabled") is True)

    print('\n[8] 没有桌面端 JS 异常')
    chk('桌面无 JS 异常', not errs, str(errs[:2]))
    br.close()

print('\n===== 导航顺序：%d 通过 / %d 失败 =====' % (PASS, FAIL))
if FAILS:
    print('失败：' + ' / '.join(FAILS))
sys.exit(1 if FAIL else 0)
