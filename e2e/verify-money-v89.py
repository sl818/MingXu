# -*- coding: utf-8 -*-
"""清债 v89：计划（策略/对比/逐月表/一次性多还）+ 记录（记还款/撤销）。

用 0% 利息的两笔债做确定性断言：
  A 1200 / 最低 100、B 600 / 最低 100 → base=200，9 个月还清
  加速钱改 100 → base=300，6 个月
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


def tab(pg, key):
    pg.click('[data-act="subtab"][data-page="money"][data-tab="%s"]' % key)
    pg.wait_for_timeout(700)


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


def sub(pg):
    return pg.evaluate("() => (document.querySelector('.mh-sub') || {}).textContent || ''")


def kpi(pg):
    return pg.evaluate("() => (document.querySelector('.money-kpi') || {}).textContent || ''")


with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome')
    pg = br.new_page(viewport={'width': 1440, 'height': 950})
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.on('dialog', lambda d: d.accept())
    login(pg)
    pg.evaluate("() => document.querySelector('[data-nav=\"money\"]').click()")
    pg.wait_for_timeout(800)

    print('\n[1] 子页都放出来了')
    chk('六子页', pg.evaluate("() => [...document.querySelectorAll('.subtab button')].map(b=>b.textContent)")
        == ['总览', '债务', '预算', '计划', '记录', '工具'],
        str(pg.evaluate("() => [...document.querySelectorAll('.subtab button')].map(b=>b.textContent)")))

    add_debt(pg, '测试债A', 1200, 0, 100)
    add_debt(pg, '测试债B', 600, 0, 100)
    chk('两笔债 → 9 个月', '还要 9 个月' in sub(pg), sub(pg))

    print('\n[2] 计划页：每月额度')
    tab(pg, 'plan')
    chk('加速钱初始 0', pg.evaluate("() => document.querySelector('#money-extra').value") == '0',
        pg.evaluate("() => document.querySelector('#money-extra').value"))
    chk('每月额度显示 200', '¥200' in pg.evaluate("() => document.body.textContent"),
        pg.evaluate("() => document.body.textContent")[-200:])
    pg.fill('#money-extra', '100')
    pg.click('[data-act="money-extra-save"]')
    pg.wait_for_timeout(900)
    tab(pg, 'overview')
    chk('加速钱 100 → 每月 300 → 6 个月', '还要 6 个月' in sub(pg), sub(pg))

    print('\n[3] 策略切换与对比')
    tab(pg, 'plan')
    rows = pg.evaluate("""() => [...document.querySelectorAll('.mcmp-row')].map(r =>
        [...r.querySelectorAll('span')].map(s => s.textContent.trim()))""")
    chk('对比表 = 表头 + 三种办法', len(rows) == 4, str(len(rows)))
    chk('表头四列', rows[0] == ['办法', '还清日', '总利息', '第一笔清掉'], str(rows[0]))
    pg.click('[data-act="money-strategy"][data-key="avalanche"]')
    pg.wait_for_timeout(800)
    on = pg.evaluate("() => document.querySelector('.mstart.on b').textContent")
    chk('切到雪崩法', on == '雪崩法', on)
    chk('对比表标出当前策略',
        '当前' in pg.evaluate("() => document.querySelector('.mcmp-row.on .mcmp-name').textContent"),
        pg.evaluate("() => document.querySelector('.mcmp-row.on .mcmp-name').textContent"))
    pg.click('[data-act="money-strategy"][data-key="snowball"]')
    pg.wait_for_timeout(700)

    print('\n[4] 逐月还款表')
    n = pg.evaluate("() => document.querySelectorAll('.mtr').length")
    chk('行数 = 6 个月', n == 6, str(n))
    last = pg.evaluate("() => { const r=[...document.querySelectorAll('.mtr')].pop(); return r.textContent; }")
    chk('最后一月剩余归零', '剩 ¥0' in last, last)
    chk('表里能看到每笔的名字', pg.evaluate("() => document.body.textContent").count('测试债B') >= 1)

    print('\n[5] 一次性多还')
    pg.click('[data-act="money-snow-new"]')
    pg.wait_for_timeout(400)
    pg.fill('#money-snow-form input[name="amount"]', '600')
    pg.click('#money-snow-form button[type="submit"]')
    pg.wait_for_timeout(900)
    tab(pg, 'overview')
    chk('多还 600 后提前到 4 个月', '还要 4 个月' in sub(pg), sub(pg))
    tab(pg, 'plan')
    chk('计划页列出这笔多还', pg.evaluate("() => document.querySelectorAll('.msnow').length") >= 1)

    print('\n[6] 自定义顺序')
    pg.click('[data-act="money-strategy"][data-key="custom"]')
    pg.wait_for_timeout(700)
    first = pg.evaluate("() => { const el=document.querySelector('.msnow-list b'); return el ? el.textContent : ''; }")
    chk('出现自定义排序列表', '1.' in first, first)
    pg.click('[data-act="money-order-move"][data-dir="1"]')
    pg.wait_for_timeout(600)
    first2 = pg.evaluate("() => { const el=document.querySelector('.msnow-list b'); return el ? el.textContent : ''; }")
    chk('下移第一项后顺序变了', first2 != first, '%s -> %s' % (first, first2))
    pg.click('[data-act="money-strategy"][data-key="snowball"]')
    pg.wait_for_timeout(600)

    print('\n[7] 记录页')
    tab(pg, 'log')
    chk('记录页空状态', '还没有还款记录' in pg.evaluate("() => document.body.textContent"))
    pg.click('[data-act="money-log-new"]')
    pg.wait_for_timeout(400)
    chk('弹窗列出债务下拉', pg.evaluate("() => document.querySelectorAll('#money-log-form option').length") == 2,
        str(pg.evaluate("() => document.querySelectorAll('#money-log-form option').length")))
    pg.fill('#money-log-form input[name="amount"]', '300')
    pg.click('#money-log-form button[type="submit"]')
    pg.wait_for_timeout(900)
    chk('记一笔后有一条记录', pg.evaluate("() => document.querySelectorAll('.mlog').length") == 1)
    tab(pg, 'overview')
    chk('总欠款从 1800 变 1500', '1500' in kpi(pg), kpi(pg))

    print('\n[8] 撤销')
    tab(pg, 'log')
    pg.click('[data-act="money-log-undo"]')
    pg.wait_for_timeout(900)
    chk('撤销后记录清空', pg.evaluate("() => document.querySelectorAll('.mlog').length") == 0,
        str(pg.evaluate("() => document.querySelectorAll('.mlog').length")))
    tab(pg, 'overview')
    chk('欠款加回 1800', '1800' in kpi(pg), kpi(pg))

    print('\n[9] 超额还款按余额算')
    tab(pg, 'log')
    pg.click('[data-act="money-log-new"]')
    pg.wait_for_timeout(400)
    pg.select_option('#money-log-form select[name="debtId"]', index=1)   # 第二笔（600）
    pg.fill('#money-log-form input[name="amount"]', '2000')
    pg.click('#money-log-form button[type="submit"]')
    pg.wait_for_timeout(900)
    tab(pg, 'overview')
    chk('只扣到 0，总额变 1200', '1200' in kpi(pg), kpi(pg))

    print('\n[10] 没有 JS 异常')
    chk('无 pageerror', not errs, str(errs[:2]))
    br.close()

print('\n===== 清债 v89：%d 通过 / %d 失败 =====' % (PASS, FAIL))
if FAILS:
    print('失败：' + ' / '.join(FAILS))
sys.exit(1 if FAIL else 0)
