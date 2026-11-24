# -*- coding: utf-8 -*-
"""移动端底部导航「更多」抽屉验证：直达全部页面、位置、热区、高亮。"""
import json, os, sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
head = open(os.path.join(ROOT, 'e2e', 'verify-batch4.py'), encoding='utf-8').read().split('with sync_playwright() as p:')[0]
sys.argv = [sys.argv[0]]
exec(head)

PASS = FAIL = 0
FAILS = []


def chk(name, ok, detail=''):
    global PASS, FAIL
    if ok:
        PASS += 1
        print('  ✓ %s' % name)
    else:
        FAIL += 1
        FAILS.append((name, detail))
        print('  ✗ %s  << %s' % (name, detail))


def login(pg):
    pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
    pg.wait_for_timeout(500)
    if pg.locator('[data-act="cloud-login"]').count() == 0:
        pg.wait_for_timeout(2400)
        return
    pg.click('[data-act="cloud-login"]')
    pg.wait_for_timeout(400)
    pg.fill('input[name="email"]', 'test@example.com')
    pg.fill('input[name="password"]', 'test@example.com')
    pg.click('form.modal-card button[type="submit"]')
    pg.wait_for_timeout(2600)


with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)
    ctx = br.new_context(viewport={'width': 390, 'height': 844}, has_touch=True, is_mobile=True, device_scale_factor=2)
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)[:180]))
    pg.clock.install(time=datetime(2026, 10, 25, 10, 0, 0))
    login(pg)

    print('[1] 底部导航结构')
    bar = pg.evaluate("""() => {
        const tabs = [...document.querySelectorAll('#mobile-nav .mobile-tab')];
        const add = document.querySelector('#mobile-nav .mobile-add');
        const r = document.querySelector('#mobile-nav').getBoundingClientRect();
        return {
            count: tabs.length,
            labels: tabs.map(t => (t.textContent || '').trim()),
            acts: tabs.map(t => t.dataset.act || ('nav:' + t.dataset.nav)),
            hasAdd: !!add,
            height: Math.round(r.height),
            bottom: Math.round(r.bottom), vh: innerHeight
        };
    }""")
    chk('底部 4 个 tab（%s）' % '/'.join(bar['labels']), bar['count'] == 4, json.dumps(bar['labels'], ensure_ascii=False))
    chk('最后一个是「更多」而不是「设置」', bar['labels'][-1] == '更多', bar['labels'][-1])
    chk('「更多」是按钮动作而非直接跳转', bar['acts'][-1] == 'more-open', bar['acts'][-1])
    chk('中间「+」仍在', bar['hasAdd'], '')
    chk('导航条贴底未被推出视口', bar['bottom'] <= bar['vh'] + 1 and bar['bottom'] > bar['vh'] - 80,
        'bottom=%d vh=%d' % (bar['bottom'], bar['vh']))

    print('\n[2] 抽屉能一次列出全部页面')
    pg.click('[data-act="more-open"]')
    pg.wait_for_timeout(700)
    sheet = pg.evaluate("""() => {
        const s = document.querySelector('#more-sheet');
        if (!s) return null;
        const r = s.getBoundingClientRect();
        const cells = [...s.querySelectorAll('.ps-cell')].map(c => ({
            label: (c.querySelector('.ps-label') || {}).textContent || '',
            view: c.dataset.view,
            w: Math.round(c.getBoundingClientRect().width),
            h: Math.round(c.getBoundingClientRect().height)
        }));
        return {
            labels: cells.map(c => c.label),
            views: cells.map(c => c.view),
            minW: Math.min(...cells.map(c => c.w)),
            minH: Math.min(...cells.map(c => c.h)),
            top: Math.round(r.top), bottom: Math.round(r.bottom),
            width: Math.round(r.width), vh: innerHeight,
            barH: Math.round(document.getElementById('mobile-nav').getBoundingClientRect().height),
            cols: getComputedStyle(s.querySelector('.ps-grid')).gridTemplateColumns.split(' ').length
        };
    }""")
    chk('抽屉打开', bool(sheet), '')
    # v61 加「戒烟」→ 7 项；v71 加「配置」→ 8 项；v170 拆分健康模块 +3 → 12 项
    chk('十二个入口齐全（%s）' % '/'.join(sheet['labels']),
    # v86 起抽屉顺序跟随 orderedNav()，体重排在随笔前 —— 按集合比，顺序归 verify-nav-order 管
        sorted(sheet['labels']) == sorted(['清债', '戒烟', '喝水', '运动', '478呼吸法', '习惯', '体重', '随笔', '日历', '统计', '配置', '设置']),
        json.dumps(sheet['labels'], ensure_ascii=False))
    chk('抽屉停在底部导航之上（bottom=%d / vh=%d / 栏高=%d）' % (sheet['bottom'], sheet['vh'], sheet['barH']),
        abs(sheet['bottom'] - (sheet['vh'] - sheet['barH'])) <= 2,
        'top=%d' % sheet['top'])
    chk('抽屉不超出屏宽（%d ≤ 390）' % sheet['width'], sheet['width'] <= 390, '')
    chk('三列排布', sheet['cols'] == 3, 'cols=%d' % sheet['cols'])
    chk('格子热区均 ≥40px（最小 %dx%d）' % (sheet['minW'], sheet['minH']),
        sheet['minW'] >= 40 and sheet['minH'] >= 40, '')
    pg.screenshot(path=os.path.join(ROOT, 'design', 'mobile-nav', '1-sheet.png'))

    print('\n[3] 六个页面都能一步直达')
    for view in ('habits', 'essays', 'weight', 'calendar', 'stats', 'settings'):
        pg.click('[data-act="more-open"]')
        pg.wait_for_timeout(500)
        pg.evaluate("""v => {
            const b = document.querySelector('[data-act="more-go"][data-view="' + v + '"]');
            if (b) b.click();
        }""", view)
        pg.wait_for_timeout(900)
        st = pg.evaluate("""() => ({
            view: document.body.dataset.view,
            sheetOpen: !!document.querySelector('#more-sheet'),
            activeTab: (document.querySelector('#mobile-nav .mobile-tab.active') || {}).textContent || '',
            scrollY: Math.round(window.scrollY),
            ovf: document.documentElement.scrollWidth - window.innerWidth
        })""")
        chk('「%s」直达成功' % view, st['view'] == view, json.dumps(st, ensure_ascii=False))
        chk('  切过去后抽屉自动关闭', not st['sheetOpen'], '')
        chk('  底部高亮落在「更多」上', st['activeTab'].strip() == '更多', st['activeTab'].strip())
        chk('  页面回到顶部且无横向溢出', st['scrollY'] == 0 and st['ovf'] <= 0,
            'scrollY=%d ovf=%d' % (st['scrollY'], st['ovf']))

    print('\n[3b] 抽屉开着时底部导航仍可点')
    pg.click('[data-act="more-open"]')
    pg.wait_for_timeout(600)
    open_now = pg.evaluate("() => !!document.querySelector('#more-sheet')")
    pg.evaluate("""() => { const l=[...document.querySelectorAll('[data-nav=\"today\"]')]; const e=l.find(x=>x.offsetParent!==null); if(e) e.click(); }""")
    pg.wait_for_timeout(900)
    after = pg.evaluate("""() => ({ view: document.body.dataset.view, sheet: !!document.querySelector('#more-sheet') })""")
    chk('抽屉打开时点「今日」能直接切页', open_now and after['view'] == 'today', json.dumps(after, ensure_ascii=False))
    chk('切页后抽屉自动关闭', not after['sheet'], json.dumps(after, ensure_ascii=False))

    print('\n[4] 当前页在抽屉里高亮（知道自己在哪）')
    # 移动端侧栏是隐藏的，必须走抽屉进入设置
    pg.click('[data-act="more-open"]')
    pg.wait_for_timeout(600)
    pg.evaluate("""() => { const b=document.querySelector('[data-act="more-go"][data-view="settings"]'); if(b) b.click(); }""")
    pg.wait_for_timeout(1000)
    pg.click('[data-act="more-open"]')
    pg.wait_for_timeout(600)
    act = pg.evaluate("""() => [...document.querySelectorAll('.ps-cell.active')].map(c => c.dataset.view)""")
    chk('停在设置页时，抽屉里「设置」高亮', act == ['settings'], json.dumps(act))
    pg.keyboard.press('Escape')
    pg.wait_for_timeout(500)

    print('\n[5] 主 tab 仍然正常')
    for view in ('today', 'meds', 'board'):
        pg.evaluate("""v => { const l=[...document.querySelectorAll('[data-nav="' + v + '"]')]; const e=l.find(x=>x.offsetParent!==null); if(e) e.click(); }""", view)
        pg.wait_for_timeout(800)
        st = pg.evaluate("""() => ({
            view: document.body.dataset.view,
            active: (document.querySelector('#mobile-nav .mobile-tab.active') || {}).textContent || ''
        })""")
        chk('底部 tab「%s」正常切换' % view, st['view'] == view, json.dumps(st, ensure_ascii=False))

    print('\n[6] 桌面端不受影响')
    dctx = br.new_context(viewport={'width': 1440, 'height': 900})
    dp = dctx.new_page()
    dp.clock.install(time=datetime(2026, 10, 25, 10, 0, 0))
    login(dp)
    dt = dp.evaluate("""() => ({
        barShown: (() => { const n = document.getElementById('mobile-nav'); return n ? getComputedStyle(n).display !== 'none' : false; })(),
        sideItems: document.querySelectorAll('.sidebar .nav-item').length
    })""")
    chk('桌面端不显示底部导航', not dt['barShown'], json.dumps(dt))
    # v61 起导航 9 项变 10 项（加「戒烟」）
    chk('桌面侧栏有 15 个页面入口', dt['sideItems'] == 15, 'sideItems=%d' % dt['sideItems'])
    dctx.close()

    print('\n[7] 错误汇总')
    chk('无 JS 运行时异常', len(errs) == 0, json.dumps(errs[:3], ensure_ascii=False))

    print('\n===== 移动端导航：%d 通过 / %d 失败 =====' % (PASS, FAIL))
    for n, d in FAILS:
        print('  - %s | %s' % (n, d))
    ctx.close()
    br.close()
