# -*- coding: utf-8 -*-
"""清债 v94：金额精度（到分）+ 总览动线 + 逐月表折叠 + 备份合并。

重点在「填得进去」和「显示不丢分」两件事：
  · 以前 step=100/50，780 都填不进去
  · 以前一律 toFixed(0)，780.5 会显示成 781
"""
import os, sys, json

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
    pg.wait_for_timeout(800)
    if pg.locator('[data-act="cloud-login"]').count():
        pg.locator('[data-act="cloud-login"]').first.click()
        pg.wait_for_timeout(600)
        pg.fill('input[name="email"]', 'test@sl00.top')
        pg.fill('input[name="password"]', 'test@sl00.top')
        pg.click('form.modal-card button[type="submit"]')
        pg.wait_for_timeout(2600)


def tab(pg, k):
    pg.click('[data-act="subtab"][data-page="money"][data-tab="%s"]' % k)
    pg.wait_for_timeout(700)


def txt(pg, sel):
    return pg.evaluate("(s) => { const e=document.querySelector(s); return e?e.innerText:''; }", sel)


board['data']['money'] = {
    'v': 1,

    'debts': [], 'extra': 0, 'strategy': 'snowball', 'customOrder': [], 'snowflakes': [],
    'startYM': '', 'log': [], 'incomes': [], 'cats': [], 'spends': [],
    'notify': {'on': False, 'before': [3, 1, 0], 'time': '09:00'},
}
board['data']['moneyAt'] = 1

with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome')
    pg = br.new_page(viewport={'width': 1440, 'height': 950})
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)[:200]))
    pg.on('dialog', lambda d: d.accept())
    login(pg)
    pg.evaluate("() => document.querySelector('[data-nav=\"money\"]').click()")
    pg.wait_for_timeout(800)

    print('\n[1] 输入框都放开到分')
    pg.click('[data-act="money-debt-new"]')
    pg.wait_for_timeout(600)
    steps = pg.evaluate("""() => { const f=document.querySelector('#money-form');
        return Object.fromEntries([...f.querySelectorAll('input[type=number]')].map(e=>[e.name, e.step])); }""")
    chk('债务余额 step=0.01', steps.get('balance') == '0.01', str(steps))
    chk('最低还款 step=0.01', steps.get('min') == '0.01', str(steps))
    chk('年化 step=0.01', steps.get('apr') == '0.01', str(steps))

    print('\n[2] 填 780.5 存得进去，显示不丢分')
    pg.fill('#money-form input[name="name"]', '零碎账')
    pg.fill('#money-form input[name="balance"]', '780.5')
    pg.fill('#money-form input[name="apr"]', '6.35')
    pg.fill('#money-form input[name="min"]', '88.8')
    pg.click('#money-form button[type="submit"]')
    pg.wait_for_timeout(900)
    chk('弹窗关掉了（没被 step 卡住）', pg.locator('#money-form').count() == 0,
        'still open')
    tab(pg, 'debts')
    card = txt(pg, '.mdebt')
    chk('卡片显示 ¥780.50', '780.50' in card, card.replace('\n', ' | '))
    chk('月还显示 ¥88.80', '88.80' in card, card.replace('\n', ' | '))
    chk('年化显示 6.35%', '6.35' in card, card.replace('\n', ' | '))

    print('\n[2b] 再建一笔大额债（逐月表要够长才看得出折叠）')
    pg.click('[data-act="subtabs"]') if False else None
    pg.click('[data-act="money-debt-new"]')
    pg.wait_for_timeout(600)
    pg.fill('#money-form input[name="name"]', '大额房贷')
    pg.fill('#money-form input[name="balance"]', '50123.45')
    pg.fill('#money-form input[name="apr"]', '4.9')
    pg.fill('#money-form input[name="min"]', '1000.5')
    pg.click('#money-form button[type="submit"]')
    pg.wait_for_timeout(900)
    tab(pg, 'debts')
    chk('两笔债都在', pg.locator('.mdebt').count() == 2, '%d' % pg.locator('.mdebt').count())

    print('\n[3] 编辑回填不丢精度')
    pg.locator('.mdebt').first.locator('[data-act="money-debt-edit"]').click()
    pg.wait_for_timeout(600)
    val = pg.evaluate("() => document.querySelector('#money-form input[name=\"balance\"]').value")
    chk('回填 780.5（不是 781）', val == '780.5', val)
    pg.locator('[data-act="close-modal"]').first.click()
    pg.wait_for_timeout(400)

    print('\n[4] 总览动线：还清日 → 还款顺序 → 曲线')
    tab(pg, 'overview')
    order = pg.evaluate("""() => [...document.querySelectorAll('#main .panel')].map(p => {
        if (p.classList.contains('money-hero')) return 'hero';
        if (p.querySelector('.mrow')) return 'order';
        if (p.querySelector('.money-curve')) return 'curve';
        return p.className;
    })""")
    chk('顺序是 hero → order → curve', order == ['hero', 'order', 'curve'], str(order))
    chk('曲线在最后一块', order[-1] == 'curve', str(order))

    print('\n[5] 副标题不再用「万」')
    sub = txt(pg, '.page-head p')
    chk('不含「万」', '万' not in sub, sub)
    chk('写了笔数', '共 2 笔' in sub, sub)

    print('\n[6] 预算：小数进得去、算得对')
    tab(pg, 'budget')
    pg.click('[data-act="money-income-new"]')
    pg.wait_for_timeout(500)
    chk('收入 step=0.01',
        pg.evaluate("() => document.querySelector('#money-income-form input[name=\"amount\"]').step") == '0.01', '')
    pg.fill('#money-income-form input[name="name"]', '工资')
    pg.fill('#money-income-form input[name="amount"]', '8123.45')
    pg.click('#money-income-form button[type="submit"]')
    pg.wait_for_timeout(900)
    chk('收入显示 ¥8123.45', '8123.45' in txt(pg, '.minc'), txt(pg, '.minc').replace('\n', '|'))

    pg.click('[data-act="money-cat-new"]')
    pg.wait_for_timeout(500)
    chk('分类 step=0.01',
        pg.evaluate("() => document.querySelector('#money-cat-form input[name=\"budget\"]').step") == '0.01', '')
    pg.fill('#money-cat-form input[name="name"]', '吃饭')
    pg.select_option('#money-cat-form select[name="kind"]', 'daily')
    pg.fill('#money-cat-form input[name="budget"]', '1521.35')
    pg.click('#money-cat-form button[type="submit"]')
    pg.wait_for_timeout(900)
    chk('分类显示 ¥1521.35', '1521.35' in txt(pg, '.mcat'), txt(pg, '.mcat').replace('\n', '|'))

    print('\n[7] 记一笔 88.88 的开销')
    pg.click('[data-act="money-spend-new"]')
    pg.wait_for_timeout(600)
    pg.fill('#money-spend-form input[name="amount"]', '88.88')
    pg.click('#money-spend-form button[type="submit"]')
    pg.wait_for_timeout(900)
    chk('流水显示 ¥88.88', '88.88' in txt(pg, '.mspend'), txt(pg, '.mspend').replace('\n', '|'))
    chk('「今天还能花」保留两位', '.' in txt(pg, '.mdaily'), txt(pg, '.mdaily').replace('\n', ' '))

    print('\n[8] 加速钱也能填小数')
    tab(pg, 'plan')
    chk('加速钱 step=0.01',
        pg.evaluate("() => document.querySelector('#money-extra').step") == '0.01', '')
    pg.fill('#money-extra', '780.5')
    pg.click('[data-act="money-extra-save"]')
    pg.wait_for_timeout(900)
    chk('额度说明里是 780.50', '780.50' in txt(pg, '.panel'), txt(pg, '.panel')[:120].replace('\n', '|'))

    print('\n[9] 逐月表默认折叠')
    chk('默认只显示 6 行', pg.locator('.mtr').count() == 6, '%d' % pg.locator('.mtr').count())
    btn = pg.evaluate("() => { const b=document.querySelector('[data-act=\"money-plan-toggle\"]'); return b?b.textContent:''; }")
    chk('有「展开 N 个月」按钮', btn.startswith('展开'), btn)
    h0 = pg.evaluate("() => Math.round(document.querySelector('#main').getBoundingClientRect().height)")
    pg.click('[data-act="money-plan-toggle"]')
    pg.wait_for_timeout(800)
    n1 = pg.locator('.mtr').count()
    h1 = pg.evaluate("() => Math.round(document.querySelector('#main').getBoundingClientRect().height)")
    chk('展开后行数变多', n1 > 6, '%d' % n1)
    chk('展开后页面变高', h1 > h0, '%d → %d' % (h0, h1))
    chk('按钮变成「收起」',
        pg.evaluate("() => document.querySelector('[data-act=\"money-plan-toggle\"]').textContent") == '收起', '')
    pg.click('[data-act="money-plan-toggle"]')
    pg.wait_for_timeout(600)
    chk('收起后回到 6 行', pg.locator('.mtr').count() == 6, '%d' % pg.locator('.mtr').count())

    print('\n[10] 工具页只剩 4 块，没有清债备份')
    tab(pg, 'tools')
    heads = pg.evaluate("() => [...document.querySelectorAll('.panel')].map(p=>(p.querySelector('h3')||{}).textContent)")
    chk('4 块', len(heads) == 4, str(heads))
    chk('没有「清债备份」', not any('清债备份' in (h or '') for h in heads), str(heads))
    chk('没有 money-export', pg.locator('[data-act="money-export"]').count() == 0, '')

    print('\n[11] 刷新后数据还在')
    pg.wait_for_timeout(1200)
    login(pg)
    pg.evaluate("() => document.querySelector('[data-nav=\"money\"]').click()")
    pg.wait_for_timeout(900)
    pg.click('[data-act="subtab"][data-page="money"][data-tab="debts"]')
    pg.wait_for_timeout(700)
    chk('金额还是 780.50', '780.50' in txt(pg, '.mdebt'), txt(pg, '.mdebt').replace('\n', '|'))

    print('\n[12] 无 JS 报错')
    chk('没有 pageerror', not errs, '; '.join(errs[:2]))

    br.close()

print('\n%d / %d 通过' % (PASS, PASS + FAIL))
if FAILS:
    print('失败：' + '、'.join(FAILS))
sys.exit(1 if FAIL else 0)
