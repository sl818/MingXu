# -*- coding: utf-8 -*-
"""清债 v95：可读性四项

  · 还款顺序里的债务名加粗（原来和金额同重、同色，一眼分不清哪个是名字）
  · 预算页收入/分类名称加粗
  · 「这个月怎么分」四段从 accent 深浅改成语义分色（蓝/绿/红/金）
  · 雾蓝云水主题宽屏两侧留白加层次（雾底 + 竖纹 + 版心分界线）
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


MONEY = {
    'v': 1,
    'debts': [
        {'id': 'd1', 'name': '测试平台', 'type': 'card', 'balance': 3220, 'start': 3220,
         'apr': 18, 'min': 322, 'due': 5, 'note': '', 'clearedAt': '', 'u': 1},
        {'id': 'd2', 'name': '测试个人', 'type': 'friend', 'balance': 1000, 'start': 1000,
         'apr': 0, 'min': 100, 'due': 8, 'note': '', 'clearedAt': '', 'u': 1},
    ],
    'extra': 1000, 'strategy': 'snowball', 'customOrder': [], 'snowflakes': [],
    'startYM': '', 'log': [],
    'incomes': [{'id': 'i1', 'name': '工资', 'amount': 6500, 'u': 1},
                {'id': 'i2', 'name': '分红', 'amount': 1500, 'u': 1}],
    'cats': [{'id': 'c1', 'name': '吃饭', 'kind': 'daily', 'budget': 1500, 'u': 1},
             {'id': 'c2', 'name': '房租', 'kind': 'fixed', 'budget': 750, 'u': 1}],
    'spends': [{'id': 's1', 'date': '2026-11-03', 'catId': 'c1', 'catName': '吃饭',
                'amount': 38.5, 'note': '', 'u': 1}],
    'notify': {'on': False, 'before': [3, 1, 0], 'time': '09:00'},
}
board['data']['money'] = MONEY
board['data']['moneyAt'] = 1


def login(pg, skin='paper', w=1440, h=950):
    pg.set_viewport_size({'width': w, 'height': h})
    pg.add_init_script(
        "try{localStorage.setItem('lifeboard.skin','%s');"
        "localStorage.setItem('lifeboard.layout','top');"
        "localStorage.setItem('lifeboard.theme.mode','light');}catch(e){}" % skin)
    pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
    pg.wait_for_timeout(800)
    if pg.locator('[data-act="cloud-login"]').count():
        pg.locator('[data-act="cloud-login"]').first.click()
        pg.wait_for_timeout(600)
        pg.fill('input[name="email"]', 'test@sl00.top')
        pg.fill('input[name="password"]', 'test@sl00.top')
        pg.click('form.modal-card button[type="submit"]')
        pg.wait_for_timeout(2800)


def go_money(pg):
    pg.evaluate("() => document.querySelector('[data-nav=\"money\"]').click()")
    pg.wait_for_timeout(800)


def tab(pg, name):
    pg.click('[data-act="subtab"][data-page="money"][data-tab="%s"]' % name)
    pg.wait_for_timeout(700)


def weight(pg, sel):
    return pg.evaluate("(s) => { const e=document.querySelector(s); "
                       "return e ? getComputedStyle(e).fontWeight : ''; }", sel)


def colors(pg, sel):
    return pg.evaluate("(s) => [...document.querySelectorAll(s)].map(e => "
                       "getComputedStyle(e).backgroundColor.toLowerCase())", sel)


with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome')
    ctx = br.new_context(viewport={'width': 1440, 'height': 950})
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)[:160]))

    print('\n[1] 还款顺序：债务名加粗')
    login(pg)
    go_money(pg)
    names = pg.evaluate("""() => [...document.querySelectorAll('.mrow-name')].map(e => ({
        t: e.textContent.trim(), w: getComputedStyle(e).fontWeight,
        numW: '' }))""")
    chk('有还款顺序行', len(names) == 2, str(names))
    # 600 在中文系统字体上常被渲染成常规体，用户实测「等于没加粗」，所以锁 700
    chk('每行名称都是 700', all(n['w'] == '700' for n in names), str(names))
    chk('名称字号比金额大半级（13.5 / 13）',
        pg.evaluate("() => { const a=document.querySelector('.mrow-name');"
                    " const b=document.querySelector('.mrow-num');"
                    " return parseFloat(getComputedStyle(a).fontSize) - "
                    "parseFloat(getComputedStyle(b).fontSize); }") == 0.5, '')
    nums = pg.evaluate("() => [...document.querySelectorAll('.mrow-num')].map(e => e.textContent.trim())")
    chk('金额还在（名称没被替换）', len(nums) == 2 and nums[0].startswith('¥'), str(nums))
    chk('名称文字就是债务名', [n['t'] for n in names] == ['测试个人', '测试平台'],
        str([n['t'] for n in names]))

    print('\n[2] 预算页：收入 / 分类名称加粗')
    tab(pg, 'budget')
    chk('收入名称 700', weight(pg, '.minc-name') == '700', weight(pg, '.minc-name'))
    chk('分类名称 700', weight(pg, '.mcat-name') == '700', weight(pg, '.mcat-name'))
    chk('流水分类名 700', weight(pg, '.mspend-cat') == '700', weight(pg, '.mspend-cat'))
    chk('金额没跟着变粗', weight(pg, '.minc-amt') == '600', '金额本来就 600，保持不变即可')

    print('\n[3] 这个月怎么分：四段语义分色')
    got = pg.evaluate("""() => {
        const probe = (v) => {
            const e = document.createElement('i');
            e.style.background = v;
            document.body.appendChild(e);
            const c = getComputedStyle(e).backgroundColor;
            e.remove();
            return c;
        };
        return {
            bars: [...document.querySelectorAll('.mbud-bar i')].map(e => getComputedStyle(e).backgroundColor),
            dots: [...document.querySelectorAll('.mbud-dot')].map(e => getComputedStyle(e).backgroundColor),
            want: ['--chart-1', '--chart-2', '--chart-3', '--chart-4'].map(k => probe('var(' + k + ')'))
        };
    }""")
    bar, dots, want = got['bars'], got['dots'], got['want']
    chk('四段都在', len(bar) == 4, str(bar))
    chk('四段颜色互不相同', len(set(bar)) == 4, str(bar))
    # 关键：就是四个语义变量，不再是 accent 的深浅混合
    names = ['固定=蓝', '日常=绿', '月供=红', '剩余=黄']
    for i in range(4):
        chk('第%d段是%s' % (i + 1, names[i]), bar[i] == want[i], '%s vs %s' % (bar[i], want[i]))
    # 关键回归：不能再出现「同一色系的深浅」。算 HSL 色相，两两至少差 35°。
    # 以前 b2/b3 是 accent 混白，色相完全相同、只差明度，实机上就是一片蓝。
    import colorsys

    def hue_of(rgb_s):
        n = [int(x) for x in rgb_s[rgb_s.index('(') + 1:rgb_s.index(')')].split(',')[:3]]
        return colorsys.rgb_to_hls(n[0] / 255, n[1] / 255, n[2] / 255)[0] * 360

    hs = [hue_of(c) for c in bar]
    worst = None
    for i in range(len(hs)):
        for j in range(i + 1, len(hs)):
            d = abs(hs[i] - hs[j])
            d = min(d, 360 - d)
            if worst is None or d < worst[0]:
                worst = (d, i + 1, j + 1)
    chk('四段两两色相至少差 35°', worst[0] >= 35,
        '第%d段与第%d段只差 %.0f°' % (worst[1], worst[2], worst[0]))
    chk('图例圆点与条形同色', dots == bar, '%s vs %s' % (dots, bar))
    chk('条形加粗到 12px',
        pg.evaluate("() => getComputedStyle(document.querySelector('.mbud-bar')).height") == '12px',
        pg.evaluate("() => getComputedStyle(document.querySelector('.mbud-bar')).height"))

    print('\n[4] 深色下四段仍然可分')
    pg.evaluate("() => { document.documentElement.dataset.theme='dark'; }")
    pg.wait_for_timeout(600)
    got2 = pg.evaluate("""() => {
        const probe = (v) => {
            const e = document.createElement('i');
            e.style.background = v;
            document.body.appendChild(e);
            const c = getComputedStyle(e).backgroundColor;
            e.remove();
            return c;
        };
        return {
            bars: [...document.querySelectorAll('.mbud-bar i')].map(e => getComputedStyle(e).backgroundColor),
            want: ['--chart-1', '--chart-2', '--chart-3', '--chart-4'].map(k => probe('var(' + k + ')'))
        };
    }""")
    chk('深色四段互不相同', len(set(got2['bars'])) == 4, str(got2['bars']))
    chk('深色也按同一套语义变量', got2['bars'] == got2['want'],
        '%s vs %s' % (got2['bars'], got2['want']))
    # 图表色是固定的，深色下不该变 —— 变了反而说明又挂到主题色上了
    chk('深色沿用同一组图表色', got2['bars'] == bar, '%s vs %s' % (got2['bars'], bar))
    pg.evaluate("() => { document.documentElement.dataset.theme='light'; }")
    pg.wait_for_timeout(400)

    print('\n[5] 雾蓝云水：宽屏两侧留白分层')
    pg2 = ctx.new_page()
    login(pg2, skin='mist', w=1920, h=1080)
    chk('皮肤切到 mist', pg2.evaluate("() => document.documentElement.dataset.skin") == 'mist', '')
    go_money(pg2)
    rail = pg2.evaluate("() => getComputedStyle(document.body,'::before').backgroundSize")
    chk('留白宽度算出来了（1920 → 每侧 120px）', rail.startswith('120px 100%'), rail)
    before = pg2.evaluate("""() => { const c=getComputedStyle(document.body,'::before');
        return {sz: c.backgroundSize, mask: c.maskImage || c.webkitMaskImage,
                pos: c.position, pe: c.pointerEvents}; }""")
    chk('竖纹层铺在左右各 120px', before['sz'].startswith('120px 100%'), str(before['sz']))
    chk('竖纹上下渐隐（有 mask）', 'gradient' in before['mask'], str(before['mask'])[:60])
    chk('不挡点击', before['pe'] == 'none', before['pe'])
    after = pg2.evaluate("""() => { const c=getComputedStyle(document.body,'::after');
        return {bg: c.backgroundImage, pe: c.pointerEvents}; }""")
    chk('雾底层是左右两侧的渐变', 'gradient' in after['bg'], str(after['bg'])[:60])
    chk('雾底层也不挡点击', after['pe'] == 'none', after['pe'])
    line = pg2.evaluate("""() => { const c=getComputedStyle(document.querySelector('#main'),'::before');
        return {w: c.width, bg: c.backgroundImage.slice(0,20)}; }""")
    chk('版心左侧有 1px 分界线', line['w'] == '1px', str(line))

    print('\n[6] 窄屏不留痕')
    pg3 = ctx.new_page()
    login(pg3, skin='mist', w=1180, h=900)
    go_money(pg3)
    sz3 = pg3.evaluate("() => getComputedStyle(document.body,'::before').backgroundSize")
    chk('1180 屏不铺留白纹理（媒体查询挡住）', sz3 in ('auto', 'auto auto'), sz3)
    chk('窄屏没有横向溢出',
        pg3.evaluate("() => document.documentElement.scrollWidth - "
                     "document.documentElement.clientWidth") == 0, '')
    # 1520–1699 这段版心=视口，--rail 会算成 0，靠 max(0px,…) 兜住
    pg4 = ctx.new_page()
    login(pg4, skin='mist', w=1600, h=900)
    go_money(pg4)
    rail4 = pg4.evaluate("() => getComputedStyle(document.body,'::before').backgroundSize")
    chk('1600 屏每侧 180px（版心 1240）', rail4.startswith('180px 100%'), rail4)
    chk('1600 屏也无横向溢出',
        pg4.evaluate("() => document.documentElement.scrollWidth - "
                     "document.documentElement.clientWidth") == 0, '')

    print('\n[7] 其他皮肤不受影响')
    pg5 = ctx.new_page()
    login(pg5, skin='retro', w=1920, h=1080)
    go_money(pg5)
    sz5 = pg5.evaluate("() => getComputedStyle(document.body,'::before').backgroundSize")
    chk('retro 下没有留白纹理', sz5 in ('auto', 'auto auto'), sz5)
    tab(pg5, 'budget')
    bar5 = pg5.evaluate("() => [...document.querySelectorAll('.mbud-bar i')].map(e => "
                        "getComputedStyle(e).backgroundColor.toLowerCase())")
    chk('retro 下分账条同样是四色', len(set(bar5)) == 4, str(bar5))

    print('\n[8] 无 JS 报错')
    chk('没有 pageerror', not errs, str(errs[:2]))
    br.close()

print('\n%d / %d 通过' % (PASS, PASS + FAIL))
if FAILS:
    print('失败：' + ' / '.join(FAILS))
    sys.exit(1)
