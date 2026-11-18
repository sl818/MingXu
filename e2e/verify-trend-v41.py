# -*- coding: utf-8 -*-
"""用药依从趋势面板的验证：百分比 / 柱子 / 空柱 / 环比 / 区间切换。

mock 的 doses 只有今天一条，这里补一段上个月的记录，
否则「与上月同期对比」永远是「无从比较」，测不到那条路径。
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
head = io.open(os.path.join(ROOT, 'e2e', 'verify-batch4.py'), encoding='utf-8').read()
head = head.split('with sync_playwright() as p:')[0]
sys.argv = [sys.argv[0]]
exec(head)

# 两个长期药改成 9 月就开始：否则 9 月没有排期，「与上月同期对比」永远走不到比较那条路
for m in board['data']['meds']:
    if m['id'] in ('m_long1', 'm_long2'):
        m['startDate'] = '2026-09-01'

# 9 月每天按时服药，造出「上月高、本月低」的对比
doses = board['data']['doses']
for day in range(1, 31):
    ds = '2026-09-%02d' % day
    doses[ds] = {
        'm_long1': {'08:00': {'at': ds + 'T08:00:00+08:00'},
                    '20:00': {'at': ds + 'T20:00:00+08:00'}},
        'm_long2': {'12:00': {'at': ds + 'T12:00:00+08:00'}},
    }

PASS = 0
FAILS = []


def chk(name, ok, detail=''):
    global PASS
    if ok:
        PASS += 1
        print('  \u2713 %s' % name)
    else:
        FAILS.append((name, detail))
        print('  \u2717 %s  << %s' % (name, detail))


PANEL_JS = """() => {
    const p = [...document.querySelectorAll('.panel')]
      .find(x => /用药依从趋势/.test(x.querySelector('h3') ? x.querySelector('h3').textContent : ''));
    if (!p) return null;
    const bars = [...p.querySelectorAll('.bar-col')];
    const cls = bars.map(b => {
        const i = b.querySelector('.bar-wrap > i');
        return i ? i.className : '';
    });
    const big = p.querySelector('.adh-big');
    const delta = p.querySelector('.adh-delta, .adh-note');
    const today = p.querySelector('.bar-col.is-today');
    const heights = bars.map(b => {
        const i = b.querySelector('.bar-wrap > i');
        return i && i.style.height ? i.style.height : '';
    });
    return {
      title: p.querySelector('h3').textContent.trim(),
      big: big ? big.textContent.trim() : '',
      delta: delta ? delta.textContent.trim() : '',
      deltaCls: delta ? delta.className : '',
      bars: bars.length,
      zero: cls.filter(c => c === 'zero').length,
      low: cls.filter(c => c === 'low').length,
      hasToday: !!today,
      todayTitle: today ? today.getAttribute('title') : '',
      heights: heights,
      hint: (p.querySelector('.hint') || {}).textContent || ''
    };
}"""


def panel(pg):
    return pg.evaluate(PANEL_JS)


with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)
    ctx = br.new_context(viewport={'width': 1440, 'height': 950})
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)[:180]))
    pg.clock.install(time=datetime(2026, 10, 25, 10, 0, 0))
    pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
    pg.wait_for_timeout(600)
    pg.click('[data-act="cloud-login"]')
    pg.wait_for_timeout(400)
    pg.fill('input[name="email"]', 'test@example.com')
    pg.fill('input[name="password"]', 'test@example.com')
    pg.click('form.modal-card button[type="submit"]')
    pg.wait_for_timeout(2600)

    print('\n[1] 面板存在')
    nav(pg, 'stats')
    pg.wait_for_timeout(900)
    d = panel(pg)
    chk('找到「用药依从趋势」面板', d is not None)
    chk('标题标明区间', d and '近 30 天' in d['title'], d['title'] if d else '')
    chk('有百分比大数字', d and d['big'].endswith('%'), d['big'] if d else '')
    pct = int(d['big'].replace('%', '')) if d and d['big'].endswith('%') else -1
    chk('百分比在合理范围', 0 <= pct <= 100, str(pct))

    print('\n[2] 柱子')
    chk('柱子数等于区间天数（30）', d['bars'] == 30, str(d['bars']))
    chk('有今天那一根', d['hasToday'])
    chk('今天的 tooltip 带服药次数', d and '已服' in d['todayTitle'], d['todayTitle'] if d else '')
    chk('有低于 80% 的浅色柱', d['low'] > 0, 'low=%d' % d['low'])
    chk('柱子高度都是百分比', all(h.endswith('%') for h in d['heights'] if h),
        str([h for h in d['heights'] if h][:4]))

    print('\n[3] 与上月同期对比')
    chk('显示了环比文案', bool(d['delta']), d['delta'])
    chk('识别为下降（本月只服了 1 次）', '↓' in d['delta'], d['delta'])
    chk('带上了两个百分比', d['delta'].count('%') == 2, d['delta'])

    print('\n[4] 区间切换')
    pg.click('[data-act="set-stats-range"][data-range="7"]')
    pg.wait_for_timeout(800)
    d7 = panel(pg)
    chk('切到 7 天后柱子变成 7 根', d7['bars'] == 7, str(d7['bars']))
    chk('标题跟着变', '近 7 天' in d7['title'], d7['title'])
    chk('7 天里没有空柱（天天有排期）', d7['zero'] == 0, 'zero=%d' % d7['zero'])

    pg.click('[data-act="set-stats-range"][data-range="90"]')
    pg.wait_for_timeout(900)
    d90 = panel(pg)
    chk('切到 90 天后柱子变成 90 根', d90['bars'] == 90, str(d90['bars']))
    chk('90 天里有「无排期」的空柱（9-01 之前）', d90['zero'] > 0, 'zero=%d' % d90['zero'])
    chk('90 天里空柱比 7 天多', d90['zero'] > d7['zero'], 'v7=%d v90=%d' % (d7['zero'], d90['zero']))
    chk('90 天的百分比比 30 天高（含整个 9 月）', 
        int(d90['big'].replace('%', '')) > pct,
        '30天=%d 90天=%s' % (pct, d90['big']))

    print('\n[5] 手机端')
    pg.click('[data-act="set-stats-range"][data-range="30"]')
    pg.wait_for_timeout(600)
    pg.set_viewport_size({'width': 390, 'height': 844})
    pg.wait_for_timeout(700)
    m = pg.evaluate("""() => {
        const p = [...document.querySelectorAll('.panel')]
          .find(x => /用药依从趋势/.test(x.querySelector('h3').textContent));
        const r = p ? p.getBoundingClientRect() : null;
        const head = p ? p.querySelector('.adh-head') : null;
        const big = p ? p.querySelector('.adh-big') : null;
        const bars = p ? p.querySelectorAll('.bar-col') : [];
        const last = bars.length ? bars[bars.length - 1].getBoundingClientRect() : null;
        return {
          ovf: document.documentElement.scrollWidth > document.documentElement.clientWidth,
          panelW: r ? Math.round(r.width) : 0,
          inPanel: last ? (last.right <= r.right + 1) : false,
          bigSize: big ? Math.round(parseFloat(getComputedStyle(big).fontSize)) : 0,
          headH: head ? Math.round(head.getBoundingClientRect().height) : 0
        };
    }""")
    chk('页面没有横向溢出', not m['ovf'], str(m))
    chk('最后一根柱子没有超出面板', m['inPanel'], str(m))
    chk('大数字没有被缩成小字', m['bigSize'] >= 20, str(m['bigSize']))
    chk('头部没有撑成三行', m['headH'] <= 70, str(m['headH']))
    pg.screenshot(path=os.path.join(ROOT, 'e2e', 'shots', 'v41-trend-mobile.png'))

    print('\n[6] 控制台')
    chk('没有 JS 异常', not errs, '; '.join(errs[:2]))

    br.close()

print('\n----------------------------')
print('通过 %d 项，失败 %d 项' % (PASS, len(FAILS)))
for name, detail in FAILS:
    print('  失败：%s  << %s' % (name, detail))
sys.exit(0 if not FAILS else 1)
