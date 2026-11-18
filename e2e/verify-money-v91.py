# -*- coding: utf-8 -*-
"""清债 v91：工具页（利率换算 / 真实年化 / 风险体检）+ 清债 JSON 导出导入。

真实年化用二分法解 IRR，所以断言给 ±0.3 的容差（10000/1000/12 期 ≈ 35.1%）。
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
    pg.wait_for_timeout(800)


def text(pg, sel):
    return pg.evaluate("(s) => (document.querySelector(s) || {}).textContent || ''", sel)


def panels(pg):
    return pg.evaluate("() => [...document.querySelectorAll('.panel')].map(x => x.textContent).join('')")


def num_of(s):
    keep = ''.join(ch for ch in s if ch.isdigit() or ch == '.')
    return float(keep or 0)


# 风险体检要靠收入/预算才出得来，所以这里给一份带收入的清债数据
board['data']['money'] = {
    'v': 1,
    'debts': [
        {'id': 'd1', 'name': '信用卡A', 'type': 'card', 'balance': 38000, 'start': 45000,
         'apr': 18, 'min': 1900, 'due': 5, 'note': '', 'clearedAt': '', 'u': 1},
        {'id': 'd2', 'name': '网贷X', 'type': 'loan', 'balance': 25000, 'start': 25000,
         'apr': 24, 'min': 1350, 'due': 15, 'note': '', 'clearedAt': '', 'u': 1},
    ],
    'extra': 1000, 'strategy': 'snowball', 'customOrder': [], 'snowflakes': [],
    'startYM': '', 'log': [],
    'incomes': [{'id': 'i1', 'name': '工资', 'amount': 9000, 'u': 1}],
    'cats': [{'id': 'c1', 'name': '房租', 'kind': 'fixed', 'budget': 3500, 'u': 1}],
    'spends': [],
    'notify': {'on': False, 'before': [3, 1, 0], 'time': '09:00'},
}
board['data']['moneyAt'] = 1

with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome')
    pg = br.new_page(viewport={'width': 1440, 'height': 950})
    errs, dialogs = [], []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.on('dialog', lambda d: (dialogs.append(d.message), d.accept()))
    login(pg)
    pg.evaluate("() => document.querySelector('[data-nav=\"money\"]').click()")
    pg.wait_for_timeout(800)

    print('\n[1] 六个子页都放出来了')
    tabs = pg.evaluate("() => [...document.querySelectorAll('.subtab button')].map(b=>b.textContent)")
    chk('六个子页', tabs == ['总览', '债务', '预算', '计划', '记录', '工具'], str(tabs))
    tab(pg, 'tools')

    print('\n[2] 利率换算')
    cells = pg.evaluate("() => [...document.querySelectorAll('.mrate-cell')].map(x=>x.textContent)")
    chk('四格齐全', len(cells) == 4, str(cells))
    chk('默认 18% → 月息 1.5%', '1.5%' in cells[0], cells[0])
    chk('18% → 月息 1.5 分', '1.5 分' in cells[1], cells[1])
    d = num_of(cells[2].replace('万', ''))
    chk('18% → 日息约万 4.9', abs(d - 4.9) <= 0.15, cells[2])
    chk('18% → 借 1 万每月 ¥150', '150' in cells[3], cells[3])

    pg.fill('#money-apr', '24')
    pg.click('[data-act="money-rate-calc"]')
    pg.wait_for_timeout(700)
    cells2 = pg.evaluate("() => [...document.querySelectorAll('.mrate-cell')].map(x=>x.textContent)")
    chk('改 24% → 月息 2%', '2%' in cells2[0], cells2[0])
    chk('改 24% → 月息 2 分（不是「2 分」写成「20 厘」）', '2 分' in cells2[1], cells2[1])
    d2 = num_of(cells2[2].replace('万', ''))
    chk('24% → 日息约万 6.6', abs(d2 - 6.58) <= 0.2, cells2[2])
    chk('24% → 借 1 万每月 ¥200', '200' in cells2[3], cells2[3])

    print('\n[3] 常用对照表')
    rows = pg.evaluate("() => [...document.querySelectorAll('.mtbl-row')].map(x=>x.textContent)")
    chk('表头 + 5 行', len(rows) == 6, str(len(rows)))
    chk('「日息万 5」= 年化 18.25%', any('日息万 5' in r and '18.25' in r for r in rows), str(rows[-1]))

    print('\n[4] 真实年化')
    apr = num_of(text(pg, '.mapr b'))
    chk('10000 到手 / 每月 1000 / 12 期 ≈ 35%', abs(apr - 35.1) <= 0.5, '%.1f' % apr)
    chk('总还款 12000', '12000' in text(pg, '.msum'), text(pg, '.msum'))
    chk('总利息 2000', '2000' in text(pg, '.msum'), text(pg, '.msum'))

    pg.fill('#money-loan-pay', '1000')
    pg.fill('#money-loan-n', '10')
    pg.click('[data-act="money-loan-calc"]')
    pg.wait_for_timeout(700)
    apr0 = num_of(text(pg, '.mapr b'))
    chk('10 期共还 10000 = 本金 → 年化 0', apr0 == 0, '%.1f' % apr0)
    chk('提示利息为 0', '利息为 0' in panels(pg), panels(pg)[-90:])

    print('\n[5] 风险体检')
    risks = pg.evaluate("() => [...document.querySelectorAll('.mrisk-body b')].map(x=>x.textContent)")
    chk('至少 3 条', len(risks) >= 3, str(risks))
    chk('指出高息债', any('年化超过 15%' in r for r in risks), str(risks))
    chk('指出月供占收入', any('占收入' in r for r in risks), str(risks))
    chk('警告圆点有 2 个以上', pg.locator('.mrisk-dot.warn').count() >= 2,
        '%d' % pg.locator('.mrisk-dot.warn').count())
    chk('免责声明在', '不构成任何借贷或投资建议' in panels(pg), panels(pg)[-60:])

    print('\n[6] 清债专属备份已合并进全站备份')
    chk('工具页没有「清债备份」面板',
        '清债备份' not in pg.evaluate("() => document.querySelector('#main').textContent"), '')
    chk('没有 money-export 按钮', pg.locator('[data-act="money-export"]').count() == 0,
        '%d' % pg.locator('[data-act="money-export"]').count())
    chk('没有 money-import 按钮', pg.locator('[data-act="money-import"]').count() == 0,
        '%d' % pg.locator('[data-act="money-import"]').count())
    chk('没有 money-import-file 输入框',
        pg.locator('#money-import-file').count() == 0,
        '%d' % pg.locator('#money-import-file').count())

    print('\n[7] 全站备份带着清债数据')
    pg.evaluate("() => document.querySelector('[data-nav=\"config\"]').click()")
    pg.wait_for_timeout(900)
    with pg.expect_download() as dl_info:
        pg.click('[data-act="export-json"]')
    dl = dl_info.value
    body = json.load(open(dl.path(), encoding='utf-8'))
    chk('文件名是「明序备份-日期」', dl.suggested_filename.startswith('明序备份-'),
        dl.suggested_filename)
    chk('整份 state 里有 habits', isinstance(body.get('habits'), list), str(type(body.get('habits'))))
    chk('整份 state 里有 money',
        isinstance(body.get('money'), dict), str(type(body.get('money'))))
    chk('债务跟着备份走了', len(body.get('money', {}).get('debts', [])) >= 1,
        str(len(body.get('money', {}).get('debts', []))))
    chk('收入 / 分类 / 流水也都在',
        all(k in body.get('money', {}) for k in ('incomes', 'cats', 'spends', 'log')),
        str(list(body.get('money', {}).keys()))[:80])

    print('\n[9] 文案')
    pg.evaluate("() => document.querySelector('[data-nav=\"config\"]').click()")
    pg.wait_for_timeout(900)
    cfg = pg.evaluate("() => document.querySelector('#main').textContent")
    chk('全站备份提示里提到债务金额', '债务金额' in cfg, cfg[:0])
    chk('没有「不上传服务器」这种旧口径', '不上传' not in cfg and '只存在你自己的设备' not in cfg, '')

    print('\n[10] 无 JS 报错')
    chk('没有 pageerror', not errs, '; '.join(errs[:2]))

    br.close()

print('\n%d / %d 通过' % (PASS, PASS + FAIL))
if FAILS:
    print('失败：' + '、'.join(FAILS))
sys.exit(1 if FAIL else 0)
