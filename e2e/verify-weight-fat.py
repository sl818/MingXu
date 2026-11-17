# -*- coding: utf-8 -*-
"""体重 v114：体脂率字段（记录 / 明细 / 右栏趋势卡）与「留空不影响 BMI」。

体脂是**可选**字段：留空存 0，不做任何派生，也不给参考范围。
"""
import os, sys
from datetime import date, timedelta

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


def go_weight(pg):
    pg.evaluate("() => { const b=document.querySelector('[data-nav=\"weight\"]'); if(b) b.click(); }")
    pg.wait_for_timeout(800)


def ensure_profile(pg):
    """没有档案时先建一个：30 岁 / 175 cm。"""
    if pg.locator('#profile-form').count():
        pg.fill('#profile-form input[name="age"]', '30')
        pg.fill('#profile-form input[name="height"]', '175')
        pg.click('#profile-form button[type="submit"]')
        pg.wait_for_timeout(800)


def add_weight(pg, d, weight, fat=None):
    pg.click('[data-act="weight-new"]')
    pg.wait_for_timeout(400)
    f = '#weight-form'
    pg.fill(f + ' input[name="date"]', d)
    pg.fill(f + ' input[name="weight"]', str(weight))
    if fat is None:
        pg.fill(f + ' input[name="fat"]', '')
    else:
        pg.fill(f + ' input[name="fat"]', str(fat))
    pg.click(f + ' button[type="submit"]')
    pg.wait_for_timeout(900)


def fat_panel(pg):
    return pg.evaluate("""() => {
        const p = document.querySelector('.weight-fat');
        if (!p) return null;
        return {
            big: (p.querySelector('.wfat-main b') || {}).textContent || '',
            sub: (p.querySelector('.wfat-main span') || {}).textContent || '',
            grid: [...p.querySelectorAll('.wfat-grid > div')].map(d =>
                (d.querySelector('small') || {}).textContent + '=' + (d.querySelector('b') || {}).textContent),
            dots: p.querySelectorAll('.wfat-dot').length,
            empty: (p.querySelector('.ww-empty') || {}).textContent || '',
            hint: (p.querySelector('.hint') || {}).textContent || ''
        };
    }""")


with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)
    ctx = br.new_context(viewport={'width': 1280, 'height': 950})
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))

    login(pg)
    go_weight(pg)
    ensure_profile(pg)

    print('\n[1] 表单里有体脂字段')
    pg.click('[data-act="weight-new"]')
    pg.wait_for_timeout(400)
    spans = pg.evaluate("() => [...document.querySelectorAll('#weight-form .field > span')].map(s => s.textContent)")
    chk('有「体脂率（%，可选）」', any('体脂率' in s and '可选' in s for s in spans), str(spans))
    fatval = pg.input_value('#weight-form input[name="fat"]')
    chk('新记录体脂默认留空', fatval == '', fatval)
    pg.click('#weight-form button[data-act="close-modal"]')
    pg.wait_for_timeout(300)

    print('\n[2] 空态：体脂卡给出引导')
    fp = fat_panel(pg)
    chk('右栏有体脂卡', fp is not None)
    chk('无数据时写「还没有体脂数据」', fp and '还没有体脂数据' in fp['empty'], fp and fp['empty'])
    chk('说明里明确不给参考范围', fp and '不给参考范围' in fp['hint'], fp and fp['hint'])

    print('\n[3] 记两条带体脂的数据')
    d1 = (date.today() - timedelta(days=7)).isoformat()
    d2 = (date.today() - timedelta(days=1)).isoformat()
    add_weight(pg, d1, 68.5, 18.5)
    add_weight(pg, d2, 67.8, 17.2)
    fp = fat_panel(pg)
    chk('大数字是最新体脂 17.2%', fp and fp['big'].strip() == '17.2%', fp and fp['big'])
    chk('较上次 ↓ 1.3%', fp and '↓ 1.3%' in fp['sub'], fp and fp['sub'])
    chk('区间变化也是 ↓ 1.3%',
        fp and '区间变化=↓ 1.3%' in fp['grid'], fp and fp['grid'])
    chk('最低 / 最高 17.2 / 18.5%',
        fp and '最低 / 最高=17.2 / 18.5%' in fp['grid'], fp and fp['grid'])
    chk('趋势图有 2 个点', fp and fp['dots'] == 2, fp and fp['dots'])

    print('\n[4] 明细行的体脂小字')
    rows = pg.evaluate("""() => [...document.querySelectorAll('.weight-row')].map(r =>
        (r.querySelector('small') || {}).textContent || '')""")
    chk('两条记录都写了体脂',
        len(rows) >= 2 and all('体脂' in r for r in rows[:2]), str(rows[:2]))

    print('\n[5] 不填体脂照常保存')
    d3 = (date.today() - timedelta(days=3)).isoformat()
    add_weight(pg, d3, 68.0, None)
    fp = fat_panel(pg)
    chk('体脂卡仍只统计有值的两条', fp and fp['dots'] == 2, fp and fp['dots'])
    rows = pg.evaluate("""() => [...document.querySelectorAll('.weight-row')].map(r =>
        (r.querySelector('small') || {}).textContent || '')""")
    chk('只有填过体脂的两条带体脂字样',
        sum(1 for r in rows if '体脂' in r) == 2, str(rows))

    print('\n[6] 体脂范围校验（min/max 交给原生校验，提交被拦）')
    n_before = pg.locator('.weight-row').count()
    pg.click('[data-act="weight-new"]')
    pg.wait_for_timeout(400)
    pg.fill('#weight-form input[name="weight"]', '68')
    pg.fill('#weight-form input[name="fat"]', '90')
    pg.click('#weight-form button[type="submit"]')
    pg.wait_for_timeout(600)
    bad = pg.evaluate("""() => {
        const el = document.querySelector('#weight-form input[name="fat"]');
        return el ? el.validity.rangeOverflow : null;
    }""")
    chk('超出 70 被原生校验标记', bad is True, str(bad))
    chk('弹窗没关', pg.locator('#weight-form').count() == 1)
    chk('没有多出一条记录', pg.locator('.weight-row').count() == n_before,
        '%d -> %d' % (n_before, pg.locator('.weight-row').count()))
    pg.click('#weight-form button[data-act="close-modal"]')
    pg.wait_for_timeout(300)

    print('\n[7] 编辑已有记录能改回留空')
    pg.evaluate("""() => {
        const r = [...document.querySelectorAll('.weight-row')].filter(x => x.textContent.indexOf('体脂') >= 0)[0];
        r.querySelector('[data-act="weight-edit"]').click();
    }""")
    pg.wait_for_timeout(500)
    nowv = pg.input_value('#weight-form input[name="fat"]')
    chk('编辑时体脂回填', nowv not in ('', '0'), nowv)
    pg.fill('#weight-form input[name="fat"]', '')
    pg.click('#weight-form button[type="submit"]')
    pg.wait_for_timeout(900)
    fp = fat_panel(pg)
    chk('清空后少一个点', fp and fp['dots'] == 1, fp and fp['dots'])

    print('\n[8] 手机 390：右栏两卡纵向排列、无溢出')
    pg.set_viewport_size({'width': 390, 'height': 900})
    pg.wait_for_timeout(600)
    ovf = pg.evaluate("() => document.documentElement.scrollWidth - innerWidth")
    chk('无横向溢出', ovf <= 0, str(ovf))
    chk('体脂卡仍在', pg.locator('.weight-fat').count() == 1)

    print('\n[9] 没有 JS 异常')
    chk('无 pageerror', not errs, ' | '.join(errs[:3]))

    print('\n===== 体重 v114：%d 通过 / %d 失败 =====' % (PASS, FAIL))
    br.close()
    sys.exit(1 if FAIL else 0)
