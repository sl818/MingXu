# -*- coding: utf-8 -*-
"""日历页 · 倒数日（v76）。

只存一个日期，未来/过去由「今天」决定。右栏 340px，日历贴左。
"""
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


def open_cal(pg):
    pg.evaluate("() => { const b=document.querySelector('[data-nav=\"calendar\"]'); if(b) b.click(); }")
    pg.wait_for_timeout(700)


def rows(pg):
    return pg.evaluate("""() => [...document.querySelectorAll('.cd-item')].map(el => ({
        num: (el.querySelector('.cd-num b') || {}).textContent || '',
        unit: (el.querySelector('.cd-num i') || {}).textContent || '',
        title: (el.querySelector('.cd-main b') || {}).textContent || '',
        sub: (el.querySelector('.cd-main small') || {}).textContent || '',
        note: (el.querySelector('.cd-main em') || {}).textContent || '',
        past: el.classList.contains('past'),
        off: el.classList.contains('off')
    }))""")


def by_title(pg, t):
    for r in rows(pg):
        if r['title'] == t:
            return r
    return None


def add(pg, title, date, note='', remind=None, time='09:00'):
    pg.click('[data-act="cd-new"]')
    pg.wait_for_timeout(400)
    pg.fill('#cd-form input[name="title"]', title)
    pg.fill('#cd-form input[name="date"]', date)
    if note:
        pg.fill('#cd-form textarea[name="note"]', note)
    pg.fill('#cd-form input[name="time"]', time)
    if remind is not None:
        # 先全关再按传入的档位开
        pg.evaluate("""() => document.querySelectorAll('#cd-form .cd-rd').forEach(b => b.classList.remove('on'))""")
        for d in remind:
            pg.click('#cd-form .cd-rd[data-d="%d"]' % d)
    pg.click('#cd-form button[type="submit"]')
    pg.wait_for_timeout(800)


with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)
    ctx = br.new_context(viewport={'width': 1512, 'height': 1000})
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)[:180]))
    pg.on('dialog', lambda d: d.accept())
    pg.clock.install(time=datetime(2026, 11, 10, 10, 0, 0))

    board['data']['countdowns'] = []

    pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
    pg.wait_for_timeout(500)
    if pg.locator('[data-act="cloud-login"]').count():
        pg.click('[data-act="cloud-login"]')
        pg.wait_for_timeout(400)
        pg.fill('input[name="email"]', 'test@example.com')
        pg.fill('input[name="password"]', 'test@example.com')
        pg.click('form.modal-card button[type="submit"]')
        pg.wait_for_timeout(2600)
    open_cal(pg)

    print('[1] 右栏与布局')
    chk('日历页有倒数日面板', pg.locator('.cd-panel').count() == 1)
    chk('空状态有提示', '还没有倒数日' in (pg.locator('.cd-empty').text_content() or ''))
    lay = pg.evaluate("""() => {
        const g = document.querySelector('.cal-layout');
        const cs = getComputedStyle(g);
        const cal = document.querySelector('.cal-wrap').getBoundingClientRect();
        const head = document.querySelector('.page-head').getBoundingClientRect();
        const cd = document.querySelector('.cd-panel').getBoundingClientRect();
        const cards = document.querySelector('.cal-cards').getBoundingClientRect();
        return {cols: cs.gridTemplateColumns, calLeft: Math.round(cal.left), headLeft: Math.round(head.left),
                calW: Math.round(cal.width), cdW: Math.round(cd.width),
                cdLeft: Math.round(cd.left), calRight: Math.round(cal.right),
                cardsW: Math.round(cards.width), cardsLeft: Math.round(cards.left)};
    }""")
    chk('宽屏是两栏', len(lay['cols'].split()) == 2, str(lay))
    chk('日历跟标题左对齐（不再居中）', abs(lay['calLeft'] - lay['headLeft']) <= 2, str(lay))
    chk('倒数日在日历右侧', lay['cdLeft'] > lay['calRight'], str(lay))
    chk('右栏约 340px', 320 <= lay['cdW'] <= 360, str(lay['cdW']))
    chk('三张统计卡跨两栏', lay['cardsW'] > lay['calW'] + 100, str(lay))

    print('[2] 未来目标：还剩 N 天')
    add(pg, '考研', '2026-11-20', '记得打印准考证', remind=[3, 1, 0])
    r = by_title(pg, '考研')
    chk('新增后出现在列表里', bool(r), str(rows(pg)))
    chk('数字是 10', bool(r) and r['num'] == '10', r['num'] if r else '')
    chk('单位是「天」', bool(r) and r['unit'] == '天', r['unit'] if r else '')
    chk('副标题写日期（不重复天数）', bool(r) and '11 月 20 日' in r['sub'] and '还剩' not in r['sub'],
        r['sub'] if r else '')
    chk('备注显示在卡片上', bool(r) and '准考证' in r['note'], r['note'] if r else '')
    chk('不是「已过去」样式', bool(r) and not r['past'])

    print('[3] 今天')
    add(pg, '今天的事', '2026-11-10')
    r = by_title(pg, '今天的事')
    chk('数字位置写「今天」', bool(r) and r['num'] == '今天', r['num'] if r else '')
    chk('今天的卡副标题写日期', bool(r) and '11 月 10 日' in r['sub'], r['sub'] if r else '')

    print('[4] 过去的目标：已过去 N 天')
    add(pg, '入职', '2026-10-01')
    r = by_title(pg, '入职')
    chk('数字是 40', bool(r) and r['num'] == '40', r['num'] if r else '')
    chk('单位是「天前」', bool(r) and r['unit'] == '天前', r['unit'] if r else '')
    chk('过去的卡副标题写日期', bool(r) and '10 月 1 日' in r['sub'], r['sub'] if r else '')
    chk('过去的行有 past 样式', bool(r) and r['past'])
    chk('有「已过去」分组标题', '已过去' in (pg.locator('.cd-group').text_content() or ''),
        pg.locator('.cd-group').text_content() or '')

    print('[5] 排序：未来的按远近升序')
    add(pg, '旅行', '2026-11-15')
    order = [x['title'] for x in rows(pg) if not x['past']]
    chk('未来组按天数升序', order == ['今天的事', '旅行', '考研'], str(order))

    print('[6] 暂停提醒')
    pg.evaluate("""() => {
        const el = [...document.querySelectorAll('.cd-item')]
            .find(x => (x.querySelector('.cd-main b') || {}).textContent === '考研');
        el.querySelector('[data-act="cd-toggle"]').click();
    }""")
    pg.wait_for_timeout(700)
    r = by_title(pg, '考研')
    chk('暂停后行变灰划线', bool(r) and r['off'], str(r))
    chk('暂停不影响倒数天数', bool(r) and r['num'] == '10', r['num'] if r else '')

    print('[7] 编辑')
    pg.evaluate("""() => {
        const el = [...document.querySelectorAll('.cd-item')]
            .find(x => (x.querySelector('.cd-main b') || {}).textContent === '旅行');
        el.querySelector('[data-act="cd-edit"]').click();
    }""")
    pg.wait_for_timeout(500)
    chk('编辑弹窗带出了原值',
        pg.input_value('#cd-form input[name="title"]') == '旅行',
        pg.input_value('#cd-form input[name="title"]'))
    pg.fill('#cd-form input[name="date"]', '2026-11-30')
    pg.click('#cd-form button[type="submit"]')
    pg.wait_for_timeout(700)
    r = by_title(pg, '旅行')
    chk('改日期后天数跟着变', bool(r) and r['num'] == '20', r['num'] if r else '')

    print('[8] 已过去超过 3 个时折叠')
    for i, d in enumerate(['2026-09-01', '2026-08-01', '2026-07-01']):
        add(pg, '旧事%d' % i, d)
    chk('只露 3 个已过去', len([x for x in rows(pg) if x['past']]) == 3, str(len(rows(pg))))
    more = pg.locator('[data-act="cd-past-more"]')
    chk('有展开按钮', more.count() == 1)
    chk('展开按钮写着总数', '展开全部 4 个' in (more.text_content() or ''), more.text_content() or '')
    more.click()
    pg.wait_for_timeout(600)
    chk('展开后 4 个都在', len([x for x in rows(pg) if x['past']]) == 4, str(len(rows(pg))))
    chk('按钮变成收起', '收起' in (pg.locator('[data-act="cd-past-more"]').text_content() or ''))

    print('[9] 写进 state，刷新后保持')
    pg.wait_for_timeout(1200)
    chk('服务端存了 7 个', len(board['data'].get('countdowns') or []) == 7,
        str(len(board['data'].get('countdowns') or [])))
    saved = [c for c in (board['data'].get('countdowns') or []) if c['title'] == '考研']
    chk('提醒档位存进去了', bool(saved) and sorted(saved[0]['remindDays']) == [0, 1, 3],
        str(saved[0]['remindDays']) if saved else '')
    pg.reload(wait_until='networkidle')
    pg.wait_for_timeout(2400)
    open_cal(pg)
    chk('刷新后还在', by_title(pg, '考研') is not None, str(rows(pg)))

    print('[10] 删除')
    pg.evaluate("""() => {
        const el = [...document.querySelectorAll('.cd-item')]
            .find(x => (x.querySelector('.cd-main b') || {}).textContent === '今天的事');
        el.querySelector('[data-act="cd-del"]').click();
    }""")
    pg.wait_for_timeout(900)
    chk('删掉后不见了', by_title(pg, '今天的事') is None, str(rows(pg)))

    print('[11] 校验')
    pg.click('[data-act="cd-new"]')
    pg.wait_for_timeout(400)
    pg.click('#cd-form button[type="submit"]')
    pg.wait_for_timeout(500)
    chk('没填名字存不进去', pg.locator('#cd-form').count() == 1)
    pg.fill('#cd-form input[name="title"]', '占位')
    pg.fill('#cd-form input[name="date"]', '')
    pg.click('#cd-form button[type="submit"]')
    pg.wait_for_timeout(500)
    chk('日期清空后存不进去', pg.locator('#cd-form').count() == 1)
    pg.click('#cd-form [data-act="close-modal"]')
    pg.wait_for_timeout(400)
    chk('取消后弹窗关掉', pg.locator('#cd-form').count() == 0)

    chk('无 JS 异常', not errs, str(errs))
    ctx.close()
    br.close()

print()
print('===== 倒数日：%d 通过 / %d 失败 =====' % (PASS, FAIL))
if FAILS:
    print('失败项：', FAILS)
