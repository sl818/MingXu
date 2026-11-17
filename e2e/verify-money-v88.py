# -*- coding: utf-8 -*-
"""清债 v88：数据层、子页面、总览、债务、以及「不进考核」的隔离。

用两笔 0% 利息的债做确定性断言：
  A 1200 / 最低 100        → 单独时 12 个月还清
  B 600  / 最低 100        → 雪球先清 B（6 个月），月供滚给 A，合计 9 个月
两边都不产生利息，所以月数可以硬编码，不受取整影响。
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


def add_debt(pg, name, balance, apr, minp):
    pg.click('[data-act="money-debt-new"]')
    pg.wait_for_timeout(400)
    f = '#money-form'
    pg.fill(f + ' input[name="name"]', name)
    pg.fill(f + ' input[name="balance"]', str(balance))
    pg.fill(f + ' input[name="apr"]', str(apr))
    pg.fill(f + ' input[name="min"]', str(minp))
    pg.click(f + ' button[type="submit"]')
    pg.wait_for_timeout(900)


def hero(pg):
    return pg.evaluate("""() => {
        const h = document.querySelector('.money-hero');
        if (!h) return null;
        return {
            big: (h.querySelector('.mh-big') || {}).textContent || '',
            sub: (h.querySelector('.mh-sub') || {}).textContent || '',
            kpi: [...h.querySelectorAll('.money-kpi span')].map(s => s.textContent)
        };
    }""")


def stat_cards(pg):
    return pg.evaluate("() => [...document.querySelectorAll('.stat-card')].map(c => c.textContent.trim())")


with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome')
    pg = br.new_page(viewport={'width': 1440, 'height': 950})
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.on('dialog', lambda d: d.accept())
    login(pg)

    print('\n[1] 导航位置')
    nav = pg.evaluate("() => [...document.querySelectorAll('#nav .nav-item')].map(b => b.dataset.nav)")
    chk('清债在待办之后、习惯之前',
        nav[nav.index('board') + 1:nav.index('board') + 3] == ['money', 'habits'], str(nav))

    print('\n[2] 空状态')
    go(pg, 'money')
    chk('没有债时给出引导按钮', pg.locator('[data-act="money-debt-new"]').count() >= 1)
    chk('空状态有说明文案', '还没有债务' in pg.evaluate("() => document.body.textContent"))
    # 子页是「做完一版放出一版」，所以这里只断言「还没做的没放出来」
    tabs0 = pg.evaluate("() => [...document.querySelectorAll('.subtab button')].map(b=>b.textContent)")
    # 六版全做完后，子页一个不落
    chk('六个子页都在',
        tabs0 == ['总览', '债务', '预算', '计划', '记录', '工具'], str(tabs0))

    print('\n[3] 记一笔债 → 总览数字')
    add_debt(pg, '测试债A', 1200, 0, 100)
    h = hero(pg)
    chk('打开弹窗能保存并回到总览', bool(h), str(h))
    chk('总欠款 = 1200', any('1200' in x for x in h['kpi']), str(h['kpi']))
    chk('每月还款 = 100', any('100' in x for x in h['kpi']), str(h['kpi']))
    chk('1200 / 每月 100 → 还要 12 个月', '还要 12 个月' in h['sub'], h['sub'])
    chk('利息为 0', '利息合计 ¥0' in h['sub'], h['sub'])
    chk('还清日显示成「YYYY 年 M 月」', '年' in h['big'] and '月' in h['big'], h['big'])

    print('\n[4] 第二笔债 → 雪球顺序')
    add_debt(pg, '测试债B', 600, 0, 100)
    h2 = hero(pg)
    chk('两笔合计每月 200', any('200' in x for x in h2['kpi']), str(h2['kpi']))
    chk('1800 / 每月 200 → 9 个月', '还要 9 个月' in h2['sub'], h2['sub'])
    order = pg.evaluate("() => [...document.querySelectorAll('.mrow-name')].map(e => e.textContent)")
    chk('雪球先列小额那笔', order[:2] == ['测试债B', '测试债A'], str(order))

    print('\n[5] 债务 子页')
    pg.click('[data-act="subtab"][data-page="money"][data-tab="debts"]')
    pg.wait_for_timeout(600)
    chk('两张债务卡', pg.locator('.mdebt').count() == 2, str(pg.locator('.mdebt').count()))
    chk('卡片里有年化和还款日', '年化' in pg.evaluate("() => document.querySelector('.mdebt').textContent"))
    pg.click('[data-act="subtab"][data-page="money"][data-tab="overview"]')
    pg.wait_for_timeout(500)

    print('\n[6] 不进考核：建债前后统计页不变')
    go(pg, 'stats')
    before = stat_cards(pg)
    go(pg, 'money')
    add_debt(pg, '测试债C', 3000, 12, 300)
    go(pg, 'stats')
    after = stat_cards(pg)
    chk('统计页四张卡的数字没变', before == after, '%s vs %s' % (before, after))

    print('\n[7] 刷新后还在（云同步）')
    pg.wait_for_timeout(1200)
    login(pg)
    go(pg, 'money')
    chk('导航清债页仍有 3 笔', pg.evaluate("() => document.querySelectorAll('.mrow').length") == 3,
        str(pg.evaluate("() => document.querySelectorAll('.mrow').length")))

    print('\n[8] 编辑与删除')
    pg.click('[data-act="subtab"][data-page="money"][data-tab="debts"]')
    pg.wait_for_timeout(600)
    pg.click('.mdebt [data-act="money-debt-edit"]')
    pg.wait_for_timeout(400)
    pg.fill('#money-form input[name="balance"]', '0')
    pg.click('#money-form button[type="submit"]')
    pg.wait_for_timeout(900)
    chk('余额改 0 后归到「已还清」', '已还清' in pg.evaluate("() => document.body.textContent"))
    n0 = pg.locator('.mdebt').count()
    pg.click('.mdebt [data-act="money-debt-del"]')
    pg.wait_for_timeout(800)
    chk('删除后少一张卡', pg.locator('.mdebt').count() == n0 - 1,
        '%d -> %d' % (n0, pg.locator('.mdebt').count()))

    print('\n[9] 没有 JS 异常')
    chk('无 pageerror', not errs, str(errs[:2]))
    br.close()

print('\n===== 清债 v88：%d 通过 / %d 失败 =====' % (PASS, FAIL))
if FAILS:
    print('失败：' + ' / '.join(FAILS))
sys.exit(1 if FAIL else 0)
