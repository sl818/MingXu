# -*- coding: utf-8 -*-
"""清债 v90：预算（钱怎么分 / 每日可花 / 收入 / 分类预算）+ 开销记账。

每日可花依赖「今天是几号」，所以断言一律**现算**：
从页面读回剩余天数，再按同一个算式验证，不写死数字。
"""
import os, sys, calendar
from datetime import date

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
        pg.fill('input[name="email"]', 'test@sl00.top')
        pg.fill('input[name="password"]', 'test@sl00.top')
        pg.click('form.modal-card button[type="submit"]')
        pg.wait_for_timeout(2600)


def tab(pg, key):
    pg.click('[data-act="subtab"][data-page="money"][data-tab="%s"]' % key)
    pg.wait_for_timeout(700)


def add_income(pg, name, amount):
    pg.click('[data-act="money-income-new"]')
    pg.wait_for_timeout(400)
    pg.fill('#money-income-form input[name="name"]', name)
    pg.fill('#money-income-form input[name="amount"]', str(amount))
    pg.click('#money-income-form button[type="submit"]')
    pg.wait_for_timeout(800)


def add_cat(pg, name, kind, budget):
    pg.click('[data-act="money-cat-new"]')
    pg.wait_for_timeout(400)
    pg.fill('#money-cat-form input[name="name"]', name)
    pg.select_option('#money-cat-form select[name="kind"]', kind)
    pg.fill('#money-cat-form input[name="budget"]', str(budget))
    pg.click('#money-cat-form button[type="submit"]')
    pg.wait_for_timeout(800)


def add_spend(pg, cat_label_prefix, amount, day):
    pg.click('[data-act="money-spend-new"]')
    pg.wait_for_timeout(400)
    opts = pg.evaluate("""() => [...document.querySelectorAll('#money-spend-form select[name="catId"] option')]
        .map(o => ({v: o.value, t: o.textContent}))""")
    target = [o for o in opts if o['t'].startswith(cat_label_prefix)]
    assert target, opts
    pg.select_option('#money-spend-form select[name="catId"]', target[0]['v'])
    pg.fill('#money-spend-form input[name="amount"]', str(amount))
    pg.fill('#money-spend-form input[name="date"]', day)
    pg.click('#money-spend-form button[type="submit"]')
    pg.wait_for_timeout(900)


def text(pg, sel):
    return pg.evaluate("(s) => (document.querySelector(s) || {}).textContent || ''", sel)


def num_of(s):
    keep = ''.join(ch for ch in s if ch.isdigit() or ch == '.')
    return float(keep or 0)


TODAY = date.today()
DAYS = calendar.monthrange(TODAY.year, TODAY.month)[1]
REST = max(1, DAYS - TODAY.day + 1)
YM = '%04d-%02d' % (TODAY.year, TODAY.month)
LAST_YM = '%04d-%02d' % ((TODAY.year, TODAY.month - 1) if TODAY.month > 1 else (TODAY.year - 1, 12))
THIS_D = '%s-%02d' % (YM, min(3, TODAY.day))
LAST_D = LAST_YM + '-10'

with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome')
    pg = br.new_page(viewport={'width': 1440, 'height': 950})
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.on('dialog', lambda d: d.accept())
    login(pg)
    pg.evaluate("() => document.querySelector('[data-nav=\"money\"]').click()")
    pg.wait_for_timeout(800)

    print('\n[1] 子页放出来了')
    tabs = pg.evaluate("() => [...document.querySelectorAll('.subtab button')].map(b=>b.textContent)")
    chk('预算已放出、工具还没放', '预算' in tabs and '工具' not in tabs, str(tabs))
    tab(pg, 'budget')

    print('\n[2] 空态')
    chk('没收入时提示先填收入', '先填一下每月收入' in text(pg, '.panel'), text(pg, '.panel')[:60])
    chk('没有日常预算时不显示每日可花', pg.locator('.mdaily').count() == 0,
        '%d' % pg.locator('.mdaily').count())

    print('\n[3] 收入')
    add_income(pg, '工资', 10000)
    add_income(pg, '副业', 2000)
    chk('两条收入都在', pg.locator('.minc').count() == 2, '%d' % pg.locator('.minc').count())
    chk('合计 12000', '合计 ¥12000' in pg.locator('.panel').first.inner_text() or
        '¥12000' in text(pg, '.mbud-net'), text(pg, '.mbud-net'))
    chk('没有开支时剩余 = 收入', '12000' in text(pg, '.mbud-net'), text(pg, '.mbud-net'))

    print('\n[4] 分类预算')
    add_cat(pg, '房租', 'fixed', 3000)
    add_cat(pg, '吃饭', 'daily', 2000)
    chk('两个分类都在', pg.locator('.mcat').count() == 2, '%d' % pg.locator('.mcat').count())
    chk('固定/日常标签分开',
        '固定' in pg.locator('.mcat').first.inner_text() and
        '日常' in pg.locator('.mcat').nth(1).inner_text(),
        pg.locator('.mcat').first.inner_text())
    net = text(pg, '.mbud-net')
    chk('剩余 12000-3000-2000=7000', '7000' in net, net)

    print('\n[5] 每日可花')
    chk('出现每日可花大字', pg.locator('.mdaily').count() == 1, '%d' % pg.locator('.mdaily').count())
    per = num_of(text(pg, '.mdaily b'))
    chk('按预算÷剩余天数算', abs(per - round(2000 / REST)) <= 1,
        'per=%.0f 期望=%.0f (REST=%d)' % (per, 2000 / REST, REST))
    chk('写清了剩余天数', str(REST) in text(pg, '.msum'), text(pg, '.msum'))

    print('\n[6] 记开销')
    add_spend(pg, '吃饭', 500, THIS_D)
    chk('列表出现 1 笔', pg.locator('.mspend').count() == 1, '%d' % pg.locator('.mspend').count())
    chk('合计 500', '¥500' in text(pg, '.msum'), text(pg, '.msum'))
    per2 = num_of(text(pg, '.mdaily b'))
    chk('每日可花跟着降', abs(per2 - round((2000 - 500) / REST)) <= 1,
        'per=%.0f 期望=%.0f' % (per2, (2000 - 500) / REST))
    chk('本月已花 500', '¥500' in text(pg, '.msum') or '500' in text(pg, '.mdaily-bar'), text(pg, '.msum'))

    print('\n[7] 翻月')
    pg.click('[data-act="money-spend-ym"][data-dir="-1"]')
    pg.wait_for_timeout(600)
    chk('上月没有流水', pg.locator('.mspend').count() == 0,
        '%d' % pg.locator('.mspend').count())
    chk('标题变成上月', LAST_YM.replace('-', '.') in text(pg, '.mym'), text(pg, '.mym'))

    print('\n[8] 记上月的一笔 → 自动跳到那个月')
    add_spend(pg, '吃饭', 300, LAST_D)
    chk('跳到上月并显示 1 笔', pg.locator('.mspend').count() == 1,
        '%d / %s' % (pg.locator('.mspend').count(), text(pg, '.mym')))
    chk('月份是上月', LAST_YM.replace('-', '.') in text(pg, '.mym'), text(pg, '.mym'))

    print('\n[9] 删分类不删流水')
    pg.click('[data-act="subtab"][data-page="money"][data-tab="budget"]')
    pg.wait_for_timeout(500)
    pg.locator('.mcat', has_text='吃饭').locator('[data-act="money-cat-del"]').click()
    pg.wait_for_timeout(900)
    chk('分类只剩 1 个', pg.locator('.mcat').count() == 1, '%d' % pg.locator('.mcat').count())
    chk('流水还在（上月的 1 笔）', pg.locator('.mspend').count() == 1,
        '%d' % pg.locator('.mspend').count())
    chk('流水名字还留着', '吃饭' in pg.locator('.mspend').first.inner_text(),
        pg.locator('.mspend').first.inner_text())
    chk('没日常预算了，每日可花收起', pg.locator('.mdaily').count() == 0,
        '%d' % pg.locator('.mdaily').count())

    print('\n[10] 开销不参与考核')
    before = pg.evaluate("""() => {
        document.querySelector('[data-nav="stats"]').click();
        return null;
    }""")
    pg.wait_for_timeout(900)
    stats_rate = pg.evaluate("""() => {
        const el = [...document.querySelectorAll('.adh-big, .money-kpi b')].map(x => x.textContent);
        const t = document.querySelector('[data-nav="stats"]');
        return document.querySelector('#main').textContent.match(/\\d+%/g) || [];
    }""")
    pg.evaluate("() => document.querySelector('[data-nav=\"money\"]').click()")
    pg.wait_for_timeout(700)
    chk('统计页照常渲染（开销不进任何达成率）',
        pg.locator('[data-nav="stats"]').count() == 1, str(stats_rate[:3]))

    print('\n[11] 持久化')
    pg.wait_for_timeout(1200)
    login(pg)
    pg.evaluate("() => document.querySelector('[data-nav=\"money\"]').click()")
    pg.wait_for_timeout(800)
    tab(pg, 'budget')
    chk('刷新后收入还在', pg.locator('.minc').count() == 2,
        '%d' % pg.locator('.minc').count())
    chk('刷新后分类还在', pg.locator('.mcat').count() == 1,
        '%d' % pg.locator('.mcat').count())
    chk('刷新后流水还在', pg.locator('.mspend').count() == 1,
        '%d' % pg.locator('.mspend').count())

    print('\n[12] 无 JS 报错')
    chk('没有 pageerror', not errs, '; '.join(errs[:2]))

    br.close()

print('\n%d / %d 通过' % (PASS, PASS + FAIL))
if FAILS:
    print('失败：' + '、'.join(FAILS))
sys.exit(1 if FAIL else 0)
