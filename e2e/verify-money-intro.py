# -*- coding: utf-8 -*-
"""清债介绍弹窗（v93）：入口位置、九个小节、来源里的两条外链、手机宽度。

来源链接是用户给的原始出处，改动要么是笔误要么是地址失效——
所以这里把两条 URL 写死，不是「能点就行」。
"""
import os, sys

ROOT = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo'
head = open(os.path.join(ROOT, 'e2e', 'verify-batch4.py'), encoding='utf-8').read().split('with sync_playwright() as p:')[0]
sys.argv = [sys.argv[0]]
exec(head)

from playwright.sync_api import sync_playwright

PASS = FAIL = 0
FAILS = []

# 别叫 DOC —— head 里 DOC 是 mock server 的静态目录，覆盖了整页都 404
DOC_URL = 'https://acnik117j8hl.feishu.cn/wiki/XFEFw7o8siqHbnkIBJicNq08nQd'
CODE_URL = 'https://github.com/cyberdaddyleo/huanqingri'

HEADS = ['一、六个子页各干什么', '二、还清日是怎么算出来的', '三、三种策略的差别只在「顺序」',
         '四、月供为什么一开始就固定', '五、「今天还能花」怎么来的', '六、真实年化（工具页）',
         '七、提醒和日历', '八、不参与考核', '九、建议这么用']


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
    """轮询等首屏：落地页有两个「登录」按钮，登录后才有 [data-nav]。
    固定 sleep 在这台机器上不稳——同样 900ms，有时还没画完。"""
    pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
    for _ in range(40):
        if pg.locator('[data-nav="money"]').count():
            return
        if pg.locator('[data-act="cloud-login"]').count():
            break
        pg.wait_for_timeout(250)
    if not pg.locator('[data-act="cloud-login"]').count():
        info = pg.evaluate("() => ({url: location.href, html: document.body.innerHTML.length, txt: document.body.innerText.slice(0,200)})")
        raise RuntimeError('落地页既没有导航也没有登录按钮 | %s' % info)
    pg.locator('[data-act="cloud-login"]').first.click()
    pg.wait_for_timeout(600)
    pg.wait_for_selector('input[name="email"]', timeout=10000)
    pg.fill('input[name="email"]', 'test@sl00.top')
    pg.fill('input[name="password"]', 'test@sl00.top')
    pg.click('form.modal-card button[type="submit"]')
    for _ in range(40):
        pg.wait_for_timeout(250)
        if pg.locator('[data-nav="money"]').count():
            return
    raise RuntimeError('登录后没等到导航')


board['data']['money'] = {
    'v': 1, 'debts': [], 'extra': 0, 'strategy': 'snowball', 'customOrder': [],
    'snowflakes': [], 'startYM': '', 'log': [], 'incomes': [], 'cats': [], 'spends': [],
    'notify': {'on': False, 'before': [3, 1, 0], 'time': '09:00'},
}
board['data']['moneyAt'] = 1

with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome')
    pg = br.new_page(viewport={'width': 1440, 'height': 950})
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    login(pg)
    # 直接点一个 data-nav：页面上不止一处（顶栏 + 手机 tabbar），class 也不总是同一个
    pg.evaluate("() => document.querySelector('[data-nav=\"money\"]').click()")
    pg.wait_for_timeout(800)

    print('\n[1] 入口在「记一笔债」左边')
    btns = pg.evaluate("() => [...document.querySelectorAll('.head-actions .btn')].map(b=>b.textContent.trim())")
    chk('两个按钮，介绍在前', btns == ['清债介绍', '记一笔债'], str(btns))

    print('\n[2] 打开弹窗')
    pg.click('[data-act="money-intro"]')
    pg.wait_for_timeout(700)
    chk('弹窗出现了', pg.locator('.modal-card').count() == 1, '%d' % pg.locator('.modal-card').count())
    title = pg.evaluate("() => (document.querySelector('.modal-card h3')||{}).textContent || ''")
    chk('标题是「清债是怎么算的」', title == '清债是怎么算的', title)

    print('\n[3] 九个小节都在')
    heads = pg.evaluate("() => [...document.querySelectorAll('.modal-card .algo-h')].map(x=>x.textContent)")
    chk('九节齐全', heads == HEADS, str(heads))
    chk('至少两张表', pg.locator('.modal-card .sum-table').count() >= 2,
        '%d' % pg.locator('.modal-card .sum-table').count())
    body = pg.evaluate("() => document.querySelector('.modal-card').textContent")
    chk('讲了三个策略', '雪球法' in body and '雪崩法' in body and '自定义' in body, '')
    chk('讲了月供固定', '一开始就固定' in body, '')
    chk('讲了每日可花公式', '本月剩余天数' in body, '')
    chk('讲了不参与考核', '全都看不见它' in body, '')
    # v94 起清债专属备份已合并进全站备份，介绍里不该再提
    chk('不再提「清债备份」', '清债备份' not in body, '')

    print('\n[4] 来源块')
    src = pg.evaluate("""() => {
        const box = document.querySelector('.algo-src');
        if (!box) return null;
        return {
            label: (box.querySelector('b') || {}).textContent || '',
            links: [...box.querySelectorAll('a')].map(a => ({href: a.href, t: a.target, r: a.rel})),
            text: box.textContent
        };
    }""")
    chk('有「来源」块', src is not None, '')
    chk('标题写的是来源', src and src['label'] == '来源', str(src and src['label']))
    chk('两条链接', src and len(src['links']) == 2, str(src and len(src['links'])))
    chk('文档地址正确', src and any(l['href'] == DOC_URL for l in src['links']),
        str([l['href'] for l in src['links']]) if src else '')
    chk('GitHub 地址正确', src and any(l['href'] == CODE_URL for l in src['links']),
        str([l['href'] for l in src['links']]) if src else '')
    chk('新标签打开且带 noopener',
        src and all(l['t'] == '_blank' and 'noopener' in (l['r'] or '') for l in src['links']),
        str(src['links']) if src else '')
    chk('说明了原版是 MIT', 'MIT' in (src['text'] if src else ''), '')
    chk('说明了口径一致', '计算口径保持一致' in (src['text'] if src else ''), '')

    print('\n[5] 关掉')
    pg.click('.modal-card [data-act="close-modal"]')
    pg.wait_for_timeout(500)
    chk('弹窗关掉了', pg.locator('.modal-card').count() == 0, '%d' % pg.locator('.modal-card').count())

    print('\n[6] 手机上不溢出')
    pg2 = br.new_page(viewport={'width': 390, 'height': 844}, device_scale_factor=2,
                      is_mobile=True, has_touch=True)
    errs2 = []
    pg2.on('pageerror', lambda e: errs2.append(str(e)))
    login(pg2)
    pg2.click('[data-act="more-open"]')
    pg2.wait_for_timeout(400)
    pg2.click('[data-act="more-go"][data-view="money"]')
    pg2.wait_for_timeout(800)
    pg2.click('[data-act="money-intro"]')
    pg2.wait_for_timeout(600)
    chk('手机上也打开了', pg2.locator('.modal-card').count() == 1, '')
    chk('没有横向溢出',
        pg2.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth") == 0, '')
    chk('弹窗本身可滚动',
        pg2.evaluate("""() => { const m = document.querySelector('.modal-card');
            return m.scrollHeight > m.clientHeight; }"""), '')

    print('\n[7] 无 JS 报错')
    chk('桌面没有 pageerror', not errs, '; '.join(errs[:2]))
    chk('手机没有 pageerror', not errs2, '; '.join(errs2[:2]))

    br.close()

print('\n%d / %d 通过' % (PASS, PASS + FAIL))
if FAILS:
    print('失败：' + '、'.join(FAILS))
sys.exit(1 if FAIL else 0)
