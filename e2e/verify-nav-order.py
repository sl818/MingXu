# -*- coding: utf-8 -*-
"""导航顺序：组内拖拽换位（v165 起用拖拽手柄，键盘也可：空格拿起 / 方向键移动 / 空格放下）。

默认顺序 12 项；「记录」组 8 项（今日…随笔）、「回顾」组 4 项（日历…设置），两组不互换。
一个顺序喂三种排版 + 手机「更多」抽屉。
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


DEFAULT = ['today', 'meds', 'quit', 'water', 'move', 'breathe', 'board', 'money', 'habits',
           'weight', 'essays', 'calendar', 'stats', 'modules', 'notifyroute', 'config', 'settings']
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


def names(pg):
    return pg.evaluate("() => [...document.querySelectorAll('.no-row')].map(r => (r.querySelector('b')||{}).textContent || '')")


def handle_of(pg, name):
    return pg.locator('.no-row').filter(has_text=name).first.locator('.drag-handle')


def move_key(pg, name, direction):
    """键盘拖拽：聚焦手柄 → 空格拿起 → 方向键移动一格 → 空格放下。"""
    h = handle_of(pg, name)
    h.focus()
    pg.wait_for_timeout(80)
    pg.keyboard.press('Space')
    pg.wait_for_timeout(120)
    pg.keyboard.press('ArrowUp' if direction < 0 else 'ArrowDown')
    pg.wait_for_timeout(150)
    pg.keyboard.press('Space')
    pg.wait_for_timeout(700)


with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome')
    pg = br.new_page(viewport={'width': 1440, 'height': 950})
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    login(pg)

    print('\n[1] 默认顺序没有被改动')
    chk('导航顺序 = 默认 17 项', pg.evaluate(NAV_ORDER_JS) == DEFAULT, str(pg.evaluate(NAV_ORDER_JS)))

    print('\n[2] 设置页的排序面板')
    go(pg, 'settings')
    n = names(pg)
    chk('共 17 行（今日 + 记录 10 + 回顾 2 + 设置 4）', len(n) == 17, str(len(n)))
    chk('顺序：仪表盘置顶 + 三组',
        n == ['仪表盘', '用药', '戒烟', '喝水', '运动', '478呼吸法', '待办', '清债', '习惯', '体重', '随笔',
              '日历', '统计', '模块', '通知路由', '配置', '设置'], str(n))
    chk('今日置顶行没有拖拽手柄',
        pg.locator('.no-row', has_text='仪表盘').locator('.drag-handle').count() == 0)
    before = names(pg)
    move_key(pg, '用药', -1)
    chk('记录组首「用药」上移无变化（边界夹住）', names(pg) == before, str(names(pg)))

    print('\n[3] 把「统计」在回顾组内上移一格')
    move_key(pg, '统计', -1)
    n2 = names(pg)
    # 用名字找下标，别硬编码（导航项以后再加会漂）
    i_st = n2.index('统计')
    chk('面板里变成 统计 在 日历 前面', i_st + 1 == n2.index('日历'), str(n2[i_st - 1:]))
    keys2 = pg.evaluate(NAV_ORDER_JS)
    chk('导航条跟着变', keys2.index('stats') + 1 == keys2.index('calendar'), str(keys2))

    print('\n[4] 两种排版都用同一个顺序')
    for lay in ('wide', 'top'):
        pg.evaluate("(l) => document.querySelector('[data-act=\"set-layout\"][data-layout=\"'+l+'\"]').click()", lay)
        pg.wait_for_timeout(600)
        got = pg.evaluate(NAV_ORDER_JS)
        chk('排版 %s 的顺序一致' % lay, got.index('stats') + 1 == got.index('calendar'), str(got))

    print('\n[5] 刷新之后还在（存进了 state）')
    pg.wait_for_timeout(1400)
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
    chk('抽屉里 统计 在 日历 之前', sheet.index('统计') < sheet.index('日历'), str(sheet))
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
