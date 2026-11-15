# -*- coding: utf-8 -*-
"""清债 v92：还款日进日历（月/周）+ 提醒开关（默认关）+ 前端 ics。

关键约定：还款日只做展示，**不写成 task 或 check**，所以不参与完成率。
"""
import os, sys, re
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
        pg.fill('input[name="email"]', 'test@sl00.top')
        pg.fill('input[name="password"]', 'test@sl00.top')
        pg.click('form.modal-card button[type="submit"]')
        pg.wait_for_timeout(2600)


def go(pg, nav):
    pg.evaluate("(n) => document.querySelector('[data-nav=\"' + n + '\"]').click()", nav)
    pg.wait_for_timeout(800)


TODAY = datetime.now()
DUE = TODAY.day

board['data']['money'] = {
    'v': 1,
    'debts': [
        {'id': 'd1', 'name': '信用卡A', 'type': 'card', 'balance': 38000, 'start': 45000,
         'apr': 18, 'min': 1900, 'due': DUE, 'note': '', 'clearedAt': '', 'u': 1},
        {'id': 'd2', 'name': '已还清的债', 'type': 'loan', 'balance': 0, 'start': 5000,
         'apr': 10, 'min': 500, 'due': DUE, 'note': '', 'clearedAt': '', 'u': 1},
    ],
    'extra': 1000, 'strategy': 'snowball', 'customOrder': [], 'snowflakes': [],
    'startYM': '', 'log': [],
    'incomes': [{'id': 'i1', 'name': '工资', 'amount': 9000, 'u': 1}],
    'cats': [], 'spends': [],
    'notify': {'on': False, 'before': [3, 1, 0], 'time': '09:00'},
}
board['data']['moneyAt'] = 1

with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome')
    pg = br.new_page(viewport={'width': 1440, 'height': 950})
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.on('dialog', lambda d: d.accept())
    login(pg)

    print('\n[1] 月视图有还款标记')
    go(pg, 'calendar')
    marks = pg.evaluate("""() => [...document.querySelectorAll('.cal-cell')]
        .filter(c => c.querySelector('.cal-debt'))
        .map(c => ({d: c.dataset.date, t: c.getAttribute('title') || ''}))""")
    chk('今天的格子有「还款」标记',
        any(m['d'] == TODAY.strftime('%Y-%m-%d') for m in marks), str(marks)[:120])
    chk('title 里写了债名和余额',
        any('还款：信用卡A' in m['t'] and '38000' in m['t'] for m in marks), str(marks)[:160])
    chk('已还清的债不标', not any('已还清的债' in m['t'] for m in marks), str(marks)[:160])

    print('\n[2] 周视图有还款条')
    pg.click('[data-act="cal-mode"][data-mode="week"]')
    pg.wait_for_timeout(900)
    wk = pg.evaluate("() => [...document.querySelectorAll('.wk-ad-debt')].map(x=>x.textContent.trim())")
    chk('本周出现还款条', len(wk) >= 1, str(wk))
    chk('条上带图标和债名', any('信用卡A' in x for x in wk), str(wk))
    pg.click('[data-act="cal-mode"][data-mode="month"]')
    pg.wait_for_timeout(600)

    print('\n[3] 还款日不算进任何统计')
    go(pg, 'today')
    pg.wait_for_timeout(400)
    pg.evaluate("() => { const m = document.querySelector('.nav-item[data-nav=\"stats\"]'); if (m) m.click(); }")
    pg.wait_for_timeout(900)
    statsPct = re.findall(r'\d+%', pg.evaluate("() => document.querySelector('#main').textContent"))
    chk('统计页照常出数字（不是被 0 塞满）', len(statsPct) > 0, str(statsPct[:4]))

    print('\n[4] 提醒默认关')
    go(pg, 'money')
    pg.click('[data-act="subtab"][data-page="money"][data-tab="tools"]')
    pg.wait_for_timeout(800)
    chk('面板标题在', '还款提醒' in pg.evaluate("() => document.querySelector('#main').textContent"), '')
    chk('默认显示已关闭',
        pg.evaluate("() => document.querySelector('[data-act=\"money-notify-toggle\"]').textContent.trim()") == '已关闭',
        pg.evaluate("() => document.querySelector('[data-act=\"money-notify-toggle\"]').textContent"))
    chk('三个档位默认都开',
        pg.evaluate("""() => [...document.querySelectorAll('[data-act="money-notify-day"]')]
            .every(b => b.classList.contains('on'))"""), '')

    print('\n[5] 关闭状态不进 ics')
    go(pg, 'config')
    with pg.expect_download() as dl0:
        pg.click('[data-act="ics-export"]')
    txt0 = open(dl0.value.path(), encoding='utf-8').read()
    chk('ics 里没有 debt 事件', 'UID:debt-d1@' not in txt0, str(txt0.count('BEGIN:VEVENT')))

    print('\n[6] 打开开关')
    go(pg, 'money')
    pg.click('[data-act="subtab"][data-page="money"][data-tab="tools"]')
    pg.wait_for_timeout(700)
    pg.click('[data-act="money-notify-toggle"]')
    pg.wait_for_timeout(900)
    chk('变成已开启',
        pg.evaluate("() => document.querySelector('[data-act=\"money-notify-toggle\"]').textContent.trim()") == '已开启',
        pg.evaluate("() => document.querySelector('[data-act=\"money-notify-toggle\"]').textContent"))
    chk('说明跟着变',
        '企业微信' in pg.evaluate("() => (document.querySelector('.mfield-sub')||{}).textContent || ''"), '')

    print('\n[7] 档位可关，但不能全关')
    pg.click('[data-act="money-notify-day"][data-day="3"]')
    pg.wait_for_timeout(700)
    ons = pg.evaluate("""() => [...document.querySelectorAll('[data-act="money-notify-day"]')]
        .filter(b => b.classList.contains('on')).map(b => b.dataset.day)""")
    chk('关掉「提前 3 天」后剩 1 和 0', sorted(ons) == ['0', '1'], str(ons))
    pg.click('[data-act="money-notify-day"][data-day="1"]')
    pg.wait_for_timeout(600)
    pg.click('[data-act="money-notify-day"][data-day="0"]')
    pg.wait_for_timeout(700)
    ons2 = pg.evaluate("""() => [...document.querySelectorAll('[data-act="money-notify-day"]')]
        .filter(b => b.classList.contains('on')).map(b => b.dataset.day)""")
    chk('最后一档关不掉', len(ons2) == 1, str(ons2))
    chk('留下的是「当天」', ons2 == ['0'], str(ons2))

    print('\n[8] 改推送时刻')
    pg.fill('#money-notify-time', '21:30')
    pg.click('[data-act="money-notify-save"]')
    pg.wait_for_timeout(800)
    chk('重绘后还是 21:30',
        pg.evaluate("() => (document.querySelector('#money-notify-time')||{}).value") == '21:30',
        pg.evaluate("() => (document.querySelector('#money-notify-time')||{}).value"))

    print('\n[9] 打开后进 ics')
    go(pg, 'config')
    with pg.expect_download() as dl1:
        pg.click('[data-act="ics-export"]')
    txt1 = open(dl1.value.path(), encoding='utf-8').read()
    chk('ics 里有 debt 事件', 'UID:debt-d1@' in txt1, str(txt1.count('BEGIN:VEVENT')))
    chk('RRULE 是每月 ' + str(DUE) + ' 号',
        ('FREQ=MONTHLY;BYMONTHDAY=%d' % DUE) in txt1, '')
    chk('用 21:30 这个时刻', 'T213000' in txt1, '')
    chk('已还清的债不进 ics', 'UID:debt-d2@' not in txt1, '')

    print('\n[10] 刷新后保持')
    pg.wait_for_timeout(1200)
    login(pg)
    go(pg, 'money')
    pg.click('[data-act="subtab"][data-page="money"][data-tab="tools"]')
    pg.wait_for_timeout(800)
    chk('开关还是开着的',
        pg.evaluate("() => document.querySelector('[data-act=\"money-notify-toggle\"]').textContent.trim()") == '已开启',
        pg.evaluate("() => document.querySelector('[data-act=\"money-notify-toggle\"]').textContent"))
    chk('时刻还是 21:30',
        pg.evaluate("() => (document.querySelector('#money-notify-time')||{}).value") == '21:30', '')

    print('\n[11] 无 JS 报错')
    chk('没有 pageerror', not errs, '; '.join(errs[:2]))

    br.close()

print('\n%d / %d 通过' % (PASS, PASS + FAIL))
if FAILS:
    print('失败：' + '、'.join(FAILS))
sys.exit(1 if FAIL else 0)
