# -*- coding: utf-8 -*-
"""配置页 · 自定义通知：新建 / 校验 / 每周多选 / 开关 / 删除。"""
import os, sys
from datetime import datetime

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


def open_cfg(pg):
    pg.evaluate("() => { const b=document.querySelector('[data-nav=\"config\"]'); if(b) b.click(); }")
    pg.wait_for_timeout(600)


def rows(pg):
    return pg.evaluate("""() => [...document.querySelectorAll('.notice-row')].map(el => ({
        when: (el.querySelector('.notice-when') || {}).textContent || '',
        text: (el.querySelector('.notice-text') || {}).textContent || '',
        off: el.classList.contains('off'),
        past: el.classList.contains('past'),
        strike: getComputedStyle(el.querySelector('.notice-text')).textDecorationLine,
        resend: !!el.querySelector('[data-act="notice-send"]')
    }))""")


with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)
    ctx = br.new_context(viewport={'width': 1512, 'height': 950})
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)[:180]))
    pg.on('dialog', lambda d: d.accept())
    pg.clock.install(time=datetime(2026, 11, 8, 10, 0, 0))

    print('[1] 入口与空状态')
    board['data']['notices'] = []
    pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
    pg.wait_for_timeout(500)
    if pg.locator('[data-act="cloud-login"]').count():
        pg.click('[data-act="cloud-login"]')
        pg.wait_for_timeout(400)
        pg.fill('input[name="email"]', 'test@sl00.top')
        pg.fill('input[name="password"]', 'test@sl00.top')
        pg.click('form.modal-card button[type="submit"]')
        pg.wait_for_timeout(2600)
    open_cfg(pg)
    chk('配置页能打开', pg.locator('.page-head h2').inner_text().strip() == '配置')
    chk('标题是「配置」', '通知、订阅与数据' in pg.locator('.page-head p').inner_text())
    chk('空列表有提示', '还没有自定义通知' in (pg.locator('.notice-list').text_content() or ''))
    warn = pg.locator('.notice-warn').first.text_content() or ''
    chk('页面里有企业微信限流提示', '静默丢弃' in warn and '5 分钟' in warn, warn[:120])
    lay = pg.evaluate("""() => {
        const w = document.querySelector('.config-wrap');
        const cs = getComputedStyle(w);
        const ws = [...w.children].map(e => Math.round(e.getBoundingClientRect().width));
        return {col: cs.columnCount, n: ws.length, same: ws.every(x => x === ws[0]), w: ws[0]};
    }""")
    chk('配置页是单栏（不是 columns 瀑布流）', lay['col'] == 'auto', str(lay))
    chk('三块面板同宽、纵向堆叠', lay['n'] == 3 and lay['same'], str(lay))

    chk('设置页已经不再有「提醒」面板',
        pg.evaluate("() => { const b=document.querySelector('[data-nav=\"settings\"]'); b.click(); "
                    "return new Promise(r => setTimeout(() => r(document.body.innerText.includes('日历订阅')), 500)); }") is False)

    print('[2] 新建：每天 20:00')
    open_cfg(pg)
    pg.click('[data-act="notice-new"]')
    pg.wait_for_timeout(400)
    chk('弹窗里有内容输入框', pg.locator('#notice-form textarea[name=\"text\"]').count() == 1)
    chk('弹窗里也有错开时间的提醒', '5 分钟' in (pg.locator('#notice-form .notice-warn').text_content() or ''))
    pg.fill('#notice-form textarea[name="text"]', '该吃维生素了')
    pg.fill('#notice-form input[name="time"]', '20:00')
    pg.select_option('#notice-mode', 'daily')
    pg.wait_for_timeout(200)
    chk('每天模式不显示日期框', pg.locator('#nf-date').is_hidden())
    chk('每天模式不显示星期框', pg.locator('#nf-weeks').is_hidden())
    pg.click('#notice-form button[type="submit"]')
    pg.wait_for_timeout(700)
    r = rows(pg)
    chk('列表多了一条', len(r) == 1, str(len(r)))
    chk('时间行写「每天 20:00」', '每天 20:00' in r[0]['when'], r[0]['when'])
    chk('内容正确', '该吃维生素了' in r[0]['text'], r[0]['text'])

    print('[3] 校验：空内容 / 超长 / 每周没选')
    pg.click('[data-act="notice-new"]')
    pg.wait_for_timeout(400)
    pg.fill('#notice-form textarea[name="text"]', '   ')
    pg.click('#notice-form button[type="submit"]')
    pg.wait_for_timeout(500)
    chk('空内容不保存', len(rows(pg)) == 1)
    chk('还在弹窗里', pg.locator('#notice-form').count() == 1)

    pg.fill('#notice-form textarea[name="text"]', '字' * 501)
    pg.click('#notice-form button[type="submit"]')
    pg.wait_for_timeout(500)
    chk('超过 500 字不保存', len(rows(pg)) == 1)
    cnt = pg.locator('#nt-count').text_content() or ''
    chk('字数计数会跟着变', '501 / 500' in cnt, cnt)

    pg.fill('#notice-form textarea[name="text"]', '周复盘')
    pg.select_option('#notice-mode', 'weekly')
    pg.wait_for_timeout(250)
    chk('每周模式显示星期框', pg.locator('#nf-weeks').is_visible())
    chk('七个星期按钮', pg.locator('#wk-pick button').count() == 7)
    pg.click('#notice-form button[type="submit"]')
    pg.wait_for_timeout(500)
    chk('没选星期不保存', len(rows(pg)) == 1)

    print('[4] 每周多选：周一 + 周四')
    pg.locator('#wk-pick button').nth(0).click()   # 周一
    pg.locator('#wk-pick button').nth(3).click()   # 周四
    pg.wait_for_timeout(200)
    chk('两个按钮进入选中态', pg.locator('#wk-pick button.on').count() == 2)
    pg.fill('#notice-form input[name="time"]', '21:30')
    pg.click('#notice-form button[type="submit"]')
    pg.wait_for_timeout(700)
    r = rows(pg)
    chk('列表变成两条', len(r) == 2, str(len(r)))
    wk_row = [x for x in r if '每周' in x['when']]
    chk('每周行写着周一、四', bool(wk_row) and '每周一、四 21:30' in wk_row[0]['when'],
        wk_row[0]['when'] if wk_row else str(r))

    print('[5] 单次：只显示日期，过期标已发/过期')
    pg.click('[data-act="notice-new"]')
    pg.wait_for_timeout(400)
    pg.fill('#notice-form textarea[name="text"]', '11 月 5 号复查')
    pg.select_option('#notice-mode', 'once')
    pg.wait_for_timeout(250)
    chk('单次模式显示日期框', pg.locator('#nf-date').is_visible())
    chk('单次模式隐藏星期框', pg.locator('#nf-weeks').is_hidden())
    pg.fill('#notice-form input[name="date"]', '2026-11-05')
    pg.fill('#notice-form input[name="time"]', '08:30')
    pg.click('#notice-form button[type="submit"]')
    pg.wait_for_timeout(700)
    r = rows(pg)
    once = [x for x in r if '单次' in x['when']]
    chk('单次行有「已过期」', bool(once) and '已过期' in once[0]['when'],
        once[0]['when'] if once else str(r))
    chk('过期的单次给了「重发」按钮', bool(once) and once[0]['resend'])
    chk('过期行整行压灰（.past）', bool(once) and once[0]['past'], str(once))
    chk('过期行正文有删除线', bool(once) and 'line-through' in once[0]['strike'],
        once[0]['strike'] if once else '')

    print('[5b] 今天的单次：时刻过了才算过期')
    # 现在 10:00。09:00 已经发完（过期），20:00 还没到（不算过期）
    pg.click('[data-act="notice-new"]')
    pg.wait_for_timeout(400)
    pg.fill('#notice-form textarea[name="text"]', '今天九点这条')
    pg.select_option('#notice-mode', 'once')
    pg.wait_for_timeout(250)
    pg.fill('#notice-form input[name="date"]', '2026-11-08')
    pg.fill('#notice-form input[name="time"]', '09:00')
    pg.click('#notice-form button[type="submit"]')
    pg.wait_for_timeout(700)
    pg.click('[data-act="notice-new"]')
    pg.wait_for_timeout(400)
    pg.fill('#notice-form textarea[name="text"]', '今天晚上这条')
    pg.select_option('#notice-mode', 'once')
    pg.wait_for_timeout(250)
    pg.fill('#notice-form input[name="date"]', '2026-11-08')
    pg.fill('#notice-form input[name="time"]', '20:00')
    pg.click('#notice-form button[type="submit"]')
    pg.wait_for_timeout(700)
    r = rows(pg)
    nine = [x for x in r if '今天九点' in x['text']]
    nine_pm = [x for x in r if '今天晚上' in x['text']]
    chk('今天 09:00 的已过期（时刻过了）',
        bool(nine) and nine[0]['past'] and '已过期' in nine[0]['when'],
        nine[0]['when'] if nine else str(r))
    chk('今天 20:00 的没过期（时刻还没到）',
        bool(nine_pm) and not nine_pm[0]['past'] and '已过期' not in nine_pm[0]['when'],
        nine_pm[0]['when'] if nine_pm else str(r))
    chk('未过期的那行没有删除线',
        bool(nine_pm) and 'line-through' not in nine_pm[0]['strike'],
        nine_pm[0]['strike'] if nine_pm else '')
    # 删掉刚加的两条，把基数还给后面的用例
    before = len(rows(pg))
    for _ in range(2):
        pg.locator('[data-act="notice-del"]').first.click()
        pg.wait_for_timeout(500)
    chk('清理后少了两条', len(rows(pg)) == before - 2, '%d -> %d' % (before, len(rows(pg))))


    print('[6] 暂停与删除')
    pg.locator('[data-act="notice-toggle"]').first.click()
    pg.wait_for_timeout(600)
    r = rows(pg)
    chk('暂停后行变灰并写已暂停', r[0]['off'] and '已暂停' in r[0]['when'], r[0]['when'])
    pg.locator('[data-act="notice-del"]').first.click()
    pg.wait_for_timeout(700)
    chk('删除后少一条', len(rows(pg)) == 2, str(len(rows(pg))))

    print('[7] 刷新后仍在（写进了 state）')
    pg.reload(wait_until='networkidle')
    pg.wait_for_timeout(2200)
    open_cfg(pg)
    chk('两条通知还在', len(rows(pg)) == 2, str(len(rows(pg))))

    chk('无 JS 异常', not errs, str(errs))
    ctx.close()
    br.close()

print()
print('===== 配置页通知：%d 通过 / %d 失败 =====' % (PASS, FAIL))
if FAILS:
    print('失败项：', FAILS)
