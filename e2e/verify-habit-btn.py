# -*- coding: utf-8 -*-
"""今日页「其他习惯」：目标 1 次的打卡按钮（v74）。

以前目标 1 次时，.pips 里那个唯一的 .pip 被 flex:1 拉成整条，
看不出是按钮。现在改成通栏按钮「今天完成 / 已完成 · 点一下撤销」。
目标 >= 2 的仍然是一排格子，不能被这版改坏。
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


def cards(pg):
    """今日页「其他习惯」区：每张卡的名字、按钮文案、次数、有哪些打卡控件。"""
    return pg.evaluate("""() => [...document.querySelectorAll('.habit-grid .habit-card')].map(el => {
        const btn = el.querySelector('.habit-done');
        const cnt = el.querySelector('.habit-count');
        const st = el.querySelector('.habit-state');
        return {
            name: (el.querySelector('.habit-title b') || {}).textContent || '',
            state: st ? (st.textContent || '').trim() : '',
            btn: btn ? (btn.textContent || '').replace(/\\s+/g, '') : '',
            on: btn ? btn.classList.contains('on') : false,
            val: btn ? btn.dataset.val : '',
            count: cnt ? (cnt.textContent || '').replace(/\\s+/g, '') : '',
            pips: el.querySelectorAll('.pips .pip').length,
            isDone: el.classList.contains('is-done')
        };
    })""")


def card_by(pg, name):
    for c in cards(pg):
        if c['name'] == name:
            return c
    return None


def to_today(pg):
    pg.evaluate("() => { const b=document.querySelector('[data-nav=\"today\"]'); if(b) b.click(); }")
    pg.wait_for_timeout(600)


with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)
    ctx = br.new_context(viewport={'width': 1512, 'height': 950})
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)[:180]))
    pg.on('dialog', lambda d: d.accept())
    pg.clock.install(time=datetime(2026, 10, 25, 10, 0, 0))

    # mock 里：h_run 目标 1（今天已完成）、h_plan 目标 1（今天没打）、h_read 目标 3
    pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
    pg.wait_for_timeout(500)
    if pg.locator('[data-act="cloud-login"]').count():
        pg.click('[data-act="cloud-login"]')
        pg.wait_for_timeout(400)
        pg.fill('input[name="email"]', 'test@sl00.top')
        pg.fill('input[name="password"]', 'test@sl00.top')
        pg.click('form.modal-card button[type="submit"]')
        pg.wait_for_timeout(2600)
    to_today(pg)

    print('[1] 目标 1 次：按钮的两种状态')
    run = card_by(pg, '夜跑')
    plan = card_by(pg, '事项复盘')
    chk('已打卡的卡有按钮', bool(run) and run['btn'] != '', str(run))
    chk('已打卡文案是「已完成 · 点一下撤销」', bool(run) and '已完成' in run['btn'] and '撤销' in run['btn'],
        run['btn'] if run else '')
    chk('已打卡按钮带 on 态', bool(run) and run['on'], str(run))
    chk('已打卡按钮的 data-val 是 0（再点是撤销）', bool(run) and run['val'] == '0',
        run['val'] if run else '')
    chk('未打卡的卡有按钮', bool(plan) and plan['btn'] != '', str(plan))
    chk('未打卡文案是「今天完成」', bool(plan) and plan['btn'] == '✓今天完成', plan['btn'] if plan else '')
    chk('未打卡按钮不带 on 态', bool(plan) and not plan['on'], str(plan))
    chk('未打卡的 data-val 是 1', bool(plan) and plan['val'] == '1', plan['val'] if plan else '')
    chk('单次卡不再显示 0 / 1 次', bool(plan) and plan['count'] == '', plan['count'] if plan else '')
    chk('右上角状态写「待打卡」', bool(plan) and plan['state'] == '待打卡', plan['state'] if plan else '')

    print('[2] 点一下完成')
    pg.click('.habit-card:has(.habit-title b:text-is("事项复盘")) .habit-done')
    pg.wait_for_timeout(700)
    plan = card_by(pg, '事项复盘')
    chk('状态变成「已完成」', bool(plan) and plan['state'] == '已完成', plan['state'] if plan else '')
    chk('按钮进入 on 态', bool(plan) and plan['on'], str(plan))
    chk('文案变成「已完成」', bool(plan) and '已完成' in plan['btn'], plan['btn'] if plan else '')
    chk('卡片进入已完成', bool(plan) and plan['isDone'], str(plan))
    chk('右上角状态灯点亮',
        pg.evaluate("""() => {
            const el = [...document.querySelectorAll('.habit-card')]
                .find(x => (x.querySelector('.habit-title b')||{}).textContent === '事项复盘');
            return !!el && el.classList.contains('is-done');
        }"""))

    print('[3] 再点一下撤销')
    pg.click('.habit-card:has(.habit-title b:text-is("事项复盘")) .habit-done')
    pg.wait_for_timeout(700)
    plan = card_by(pg, '事项复盘')
    chk('状态回到「待打卡」', bool(plan) and plan['state'] == '待打卡', plan['state'] if plan else '')
    chk('按钮退出 on 态', bool(plan) and not plan['on'], str(plan))
    chk('文案回到「今天完成」', bool(plan) and plan['btn'] == '✓今天完成', plan['btn'] if plan else '')
    chk('卡片退出已完成', bool(plan) and not plan['isDone'], str(plan))

    print('[4] 目标 >= 2 的卡不能受影响')
    read = card_by(pg, '读书')
    chk('读书没有新按钮', bool(read) and read['btn'] == '', str(read))
    chk('读书仍是 3 个格子', bool(read) and read['pips'] == 3, str(read))
    pg.click('.habit-card:has(.habit-title b:text-is("读书")) .pip[data-val="1"]')
    pg.wait_for_timeout(600)
    read = card_by(pg, '读书')
    chk('点第 1 格还是记 1 页', bool(read) and read['count'].startswith('1'), read['count'] if read else '')

    print('[5] 历史日期也能补记')
    pg.evaluate("() => document.querySelector('[data-act=\"date-shift\"][data-delta=\"-1\"]').click()")
    pg.wait_for_timeout(700)
    old = card_by(pg, '事项复盘')
    chk('昨天那天的卡也有按钮', bool(old) and old['btn'] != '', str(old))
    chk('昨天状态是「已完成」（mock 里昨天打过）',
        bool(old) and old['state'] == '已完成', old['state'] if old else '')
    chk('昨天那天的按钮是「已完成」态', bool(old) and old['on'], str(old))
    chk('历史日期按钮不禁用',
        pg.evaluate("""() => {
            const el = [...document.querySelectorAll('.habit-card')]
                .find(x => (x.querySelector('.habit-title b')||{}).textContent === '事项复盘');
            const b = el && el.querySelector('.habit-done');
            return !!b && !b.disabled;
        }"""))
    pg.click('.habit-card:has(.habit-title b:text-is("事项复盘")) .habit-done')
    pg.wait_for_timeout(700)
    chk('历史日期也能改（已完成 -> 待打卡）',
        bool(card_by(pg, '事项复盘')) and card_by(pg, '事项复盘')['state'] == '待打卡',
        str(card_by(pg, '事项复盘')))

    print('[6] 按钮尺寸与文案不溢出')
    pg.evaluate("() => document.querySelector('[data-act=\"date-shift\"][data-delta=\"1\"]').click()")
    pg.wait_for_timeout(600)
    box = pg.evaluate("""() => {
        const el = document.querySelector('.habit-done');
        const b = el.getBoundingClientRect();
        const card = el.closest('.habit-card').getBoundingClientRect();
        const span = el.querySelector('span').getBoundingClientRect();
        return {h: Math.round(b.height), w: Math.round(b.width),
                cardW: Math.round(card.width),
                textW: Math.round(span.width),
                overflow: span.right > b.right + 1};
    }""")
    chk('高度 36px', box['h'] == 36, str(box))
    chk('宽度铺满卡片内宽', box['w'] > box['cardW'] - 60, str(box))
    chk('文字没有溢出按钮', not box['overflow'], str(box))

    chk('无 JS 异常', not errs, str(errs))
    ctx.close()
    br.close()

print()
print('===== 目标 1 次打卡按钮：%d 通过 / %d 失败 =====' % (PASS, FAIL))
if FAILS:
    print('失败项：', FAILS)
