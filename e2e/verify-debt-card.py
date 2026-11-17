# -*- coding: utf-8 -*-
"""清债 v111：债务卡的完成百分比 / 已还还剩 / 页底汇总卡。

用可硬编码的三笔债（A 已还一部分、B 已还清、C 还没开始）：
  A 38000 → 12000   apr 18  min 1900    68% / 已还 26000
  B  5000 → 0       apr 0   min 500     已还清
  C  8000 → 8000    apr 24  min 800     0%
汇总：总待还 20000 / 总已还 31000 / 一共欠过 51000 / 最低合计 2700 /
      加权平均年化 (18×12000 + 24×8000) ÷ 20000 = 20.4% / 在还 2 已清 1 / 总进度 61%
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


def debts_tab(pg):
    pg.evaluate("() => { const b=document.querySelector('[data-nav=\"money\"]'); if(b) b.click(); }")
    pg.wait_for_timeout(800)
    pg.evaluate("""() => {
        const b = document.querySelector('[data-act="subtab"][data-page="money"][data-tab="debts"]');
        if (b) b.click();
    }""")
    pg.wait_for_timeout(600)


def add_debt(pg, name, balance, apr, minp, due=''):
    pg.click('[data-act="money-debt-new"]')
    pg.wait_for_timeout(400)
    f = '#money-form'
    pg.fill(f + ' input[name="name"]', name)
    pg.fill(f + ' input[name="balance"]', str(balance))
    pg.fill(f + ' input[name="apr"]', str(apr))
    pg.fill(f + ' input[name="min"]', str(minp))
    if due != '':
        pg.fill(f + ' input[name="due"]', str(due))
    pg.click(f + ' button[type="submit"]')
    pg.wait_for_timeout(900)


def edit_balance(pg, name, balance):
    pg.evaluate("""(n) => {
        const c = [...document.querySelectorAll('.mdebt')].filter(x => x.textContent.indexOf(n) >= 0)[0];
        c.querySelector('[data-act="money-debt-edit"]').click();
    }""", name)
    pg.wait_for_timeout(500)
    pg.fill('#money-form input[name="balance"]', str(balance))
    pg.click('#money-form button[type="submit"]')
    pg.wait_for_timeout(1000)


def card_of(pg, name):
    return pg.evaluate("""(n) => {
        const c = [...document.querySelectorAll('.mdebt')].filter(x => x.textContent.indexOf(n) >= 0)[0];
        if (!c) return null;
        return {
            txt: c.textContent,
            pct: (c.querySelector('.mdebt-pct') || {}).textContent || '',
            paid: [...c.querySelectorAll('.mdebt-paid span')].map(s => s.textContent),
            barW: (c.querySelector('.mdebt-bar i') || {}).style ? c.querySelector('.mdebt-bar i').style.width : '',
            hasBar: !!c.querySelector('.mdebt-bar')
        };
    }""", name)


def summary(pg):
    return pg.evaluate("""() => {
        const cells = [...document.querySelectorAll('.mdebt-sum > div')];
        if (!cells.length) return null;
        const p = [...document.querySelectorAll('.panel')].filter(x => x.querySelector('.mdebt-sum'))[0];
        return {
            cells: cells.map(c => (c.querySelector('span') || {}).textContent + '=' + (c.querySelector('b') || {}).textContent),
            head: (p.querySelector('.mhead-row .muted-sm') || {}).textContent || '',
            barW: (p.querySelector('.mdebt-bar i') || {}).style.width || ''
        };
    }""")


with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)
    ctx = br.new_context(viewport={'width': 1280, 'height': 950})
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))

    login(pg)
    debts_tab(pg)

    print('\n[1] 造三笔债（A 已还一部分 / B 已还清 / C 未开始）')
    add_debt(pg, '信用卡A', 38000, 18, 1900, due=5)
    add_debt(pg, '亲友B', 5000, 0, 500)
    add_debt(pg, '网贷C', 8000, 24, 800, due=15)
    edit_balance(pg, '信用卡A', 12000)
    edit_balance(pg, '亲友B', 0)
    chk('三张卡都在', pg.locator('.mdebt').count() == 3, '%d' % pg.locator('.mdebt').count())

    print('\n[2] 每笔债的完成百分比')
    a = card_of(pg, '信用卡A')
    chk('A 百分比 68%', a and '68%' in a['pct'], a and a['pct'])
    chk('A 进度条宽度 68%', a and a['barW'] == '68%', a and a['barW'])
    c = card_of(pg, '网贷C')
    chk('C 百分比 0%', c and '已完成 0%' in c['pct'], c and c['pct'])
    chk('C 进度条宽度 0%', c and c['barW'] == '0%', c and c['barW'])
    b = card_of(pg, '亲友B')
    chk('B 写「已还清」不是百分比', b and b['pct'].strip() == '已还清', b and b['pct'])
    chk('B 进度条满格', b and b['barW'] == '100%', b and b['barW'])

    print('\n[3] 当前已还 / 还剩')
    chk('A 已还 26000、还剩 12000',
        a and a['paid'] == ['当前已还 ¥26000', '还剩 ¥12000'], a and a['paid'])
    chk('C 已还 0、还剩 8000',
        c and c['paid'] == ['当前已还 ¥0', '还剩 ¥8000'], c and c['paid'])
    chk('已还清的卡片不再写「还剩 ¥0」',
        b and all('还剩' not in x for x in b['paid']), b and b['paid'])

    print('\n[4] 页底汇总卡')
    s = summary(pg)
    chk('汇总卡存在且有 6 格', s and len(s['cells']) == 6, s and s['cells'])
    cells = s['cells'] if s else []
    chk('当前总待还 ¥20000', '当前总待还=¥20000' in cells, str(cells))
    chk('当前总已还 ¥31000', '当前总已还=¥31000' in cells, str(cells))
    chk('一共欠过 ¥51000', '一共欠过=¥51000' in cells, str(cells))
    chk('每月最低合计 ¥2700', '每月最低合计=¥2700' in cells, str(cells))
    chk('平均年化按余额加权 20.4%', '平均年化=20.4%' in cells, str(cells))
    chk('在还 / 已还清 2 / 1 笔', '在还 / 已还清=2 / 1 笔' in cells, str(cells))
    chk('总进度 61%', s and '61%' in s['head'], s and s['head'])
    chk('汇总进度条 61%', s and s['barW'] == '61%', s and s['barW'])

    print('\n[5] 手机 390：汇总卡两列')
    pg.set_viewport_size({'width': 390, 'height': 900})
    pg.wait_for_timeout(600)
    cols = pg.evaluate("""() => {
        const g = document.querySelector('.mdebt-sum');
        return g ? getComputedStyle(g).gridTemplateColumns.split(' ').length : 0;
    }""")
    chk('窄屏两列', cols == 2, str(cols))
    ovf = pg.evaluate("""() => {
        const bad = [];
        document.querySelectorAll('.mdebt, .mdebt-sum > div').forEach(el => {
            if (el.scrollWidth > el.clientWidth + 1) bad.push(el.className);
        });
        return bad;
    }""")
    chk('卡片没有横向溢出', not ovf, str(ovf))

    print('\n[6] 没有 JS 异常')
    chk('无 pageerror', not errs, ' | '.join(errs[:3]))

    print('\n===== 清债 v111：%d 通过 / %d 失败 =====' % (PASS, FAIL))
    br.close()
    sys.exit(1 if FAIL else 0)
