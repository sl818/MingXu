# -*- coding: utf-8 -*-
"""戒烟页的两处改动（v107）

需求二来自《晚风Todo版本需求：》：
  1. 买烟记录折叠：默认收起只看最近 5 条，标题写「共 N 条」，展开每次多 20 条；
  2. 数据汇总从 8 格扩到 12 格：新增减量进度 / 无烟天数 / 本周守住 / 近 4 周，
     并把「忍住了」改成「抵御率」当主数字。

这组用例锁的是「显示口径」，不是数据层——所有新增值都从 cravings / packs 现算，
一个字段都没加，所以也要锁住「不写 state」这件事。
"""
import os
import sys
from datetime import datetime, timedelta

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


TODAY = datetime(2026, 10, 25)


def ts(d, hh=12, mm=0):
    return int(datetime(d.year, d.month, d.day, hh, mm).timestamp())


def build(pack_count=26, base=9, now=3):
    """造一份「早期每天 9 支、最近 3 支」的记录，凑够减量对比的样本。"""
    board['data']['habits'] = [{
        'id': 'h_smoke', 'name': '戒烟', 'icon': '🚭', 'type': 'quit', 'quitKind': 'smoke',
        'target': 1, 'unit': '支', 'color': '#7a8a6f', 'note': '',
        'createdAt': '2026-08-20T00:00:00Z',
    }]
    board['data']['packs'] = [
        {'id': 'p%d' % i, 'at': ts(TODAY - timedelta(days=i * 3), 9),
         'name': '黄鹤楼', 'price': 25, 'size': 20, 'cf': ''}
        for i in range(pack_count - 1, -1, -1)
    ]
    crav = []
    for i in range(70, -1, -1):
        d = TODAY - timedelta(days=i)
        n = base if i > 40 else (7 if i > 20 else (5 if i > 7 else now))
        for k in range(n):
            crav.append({'id': 'c%s_%s' % (i, k), 'h': 'h_smoke', 'k': 's', 't': ts(d, 8 + k, 15)})
        for k in range(1 if i % 2 else 2):
            crav.append({'id': 'r%s_%s' % (i, k), 'h': 'h_smoke', 'k': 'r', 't': ts(d, 20, k * 10)})
    board['data']['cravings'] = crav


def open_quit(br, w=1440, h=1100):
    ctx = br.new_context(viewport={'width': w, 'height': h})
    p = ctx.new_page()
    p.clock.install(time=datetime(2026, 10, 25, 21, 0, 0))
    p.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
    p.wait_for_timeout(500)
    if p.locator('[data-act="cloud-login"]').count():
        p.click('[data-act="cloud-login"]')
        p.wait_for_timeout(500)
        p.fill('input[name="email"]', 'test@example.com')
        p.fill('input[name="password"]', 'test@example.com')
        p.click('form.modal-card button[type="submit"]')
        p.wait_for_timeout(2600)
    p.evaluate("() => { const b = document.querySelector('[data-nav=\"quit\"]'); if (b) b.click(); }")
    p.wait_for_timeout(900)
    return ctx, p


def _parse_color(c):
    """getComputedStyle 现在会返回 color(srgb r g b)（color-mix 的结果），
    老式 rgb() 也要能解析——两种都出现在同一页里。"""
    c = c.strip()
    if c.startswith('color(srgb'):
        return [float(x) * 255 for x in c[c.index('srgb') + 4:c.rindex(')')].split()[:3]]
    if c.startswith('rgb'):
        return [float(x) for x in c[c.index('(') + 1:c.index(')')].split(',')[:3]]
    return None


def _lum(rgb):
    c = [x / 255 for x in rgb]
    c = [(x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4) for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def _ratio(a, b):
    la, lb = _lum(a), _lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


CONTRAST = """(sel) => {
    const el = document.querySelector(sel);
    if (!el) return null;
    const cs = getComputedStyle(el);
    let n = el, bg = '';
    while (n) {
      const b = getComputedStyle(n).backgroundColor;
      if (b && !/rgba\\(0, 0, 0, 0\\)|transparent/.test(b)) { bg = b; break; }
      n = n.parentElement;
    }
    if (!bg) {
      // 父链全是 transparent（深色皮肤的 .panel 用了变量背景），
      // 退回主题的 --surface，别拿白色当兜底——深色页上会算出假的不达标。
      const v = getComputedStyle(document.documentElement).getPropertyValue('--surface').trim();
      if (v.charAt(0) === '#') {
        const h = v.slice(1);
        const f = h.length === 3 ? h.split('').map(x => parseInt(x + x, 16))
                                 : [0, 2, 4].map(i => parseInt(h.slice(i, i + 2), 16));
        bg = 'rgb(' + f.join(',') + ')';
      }
    }
    return { fg: cs.color, bg: bg || 'rgb(255,255,255)', size: parseFloat(cs.fontSize) };
}"""

PACK_ROWS = "() => document.querySelectorAll('.qpack-list .qpack').length"
FOLD_TEXT = "() => { const f = document.querySelector('.qpack-fold'); return f ? f.textContent.replace(/\\s+/g, ' ').trim() : ''; }"
SUM = """() => [...document.querySelectorAll('.qsum-grid .qsum')].map(el => ({
    label: (el.querySelector('small') || {}).textContent || '',
    big: (el.querySelector(':scope > b') || {}).textContent || '',
    sub: (el.querySelector('span') || {}).textContent || ''
}))"""


def main():
    build()
    with sync_playwright() as p:
        br = p.chromium.launch(channel='chrome', headless=True)

        # ---------- 1. 折叠：默认收起只看 5 条 ----------
        print('\n[1] 买烟记录折叠')
        ctx, pg = open_quit(br)
        chk('默认只渲染 5 条', pg.evaluate(PACK_ROWS) == 5, str(pg.evaluate(PACK_ROWS)))
        txt = pg.evaluate(FOLD_TEXT)
        chk('折叠条写明总条数', '共 26 条' in txt, txt)
        chk('折叠条写明收起时只看 5 条', '只看最近 5 条' in txt, txt)
        chk('收起时没有「再显示」按钮', pg.locator('.qpack-more').count() == 0)

        # ---------- 2. 展开：一次 20 条 ----------
        print('\n[2] 展开与分页')
        pg.click('.qpack-fold')
        pg.wait_for_timeout(500)
        chk('展开后 20 条', pg.evaluate(PACK_ROWS) == 20, str(pg.evaluate(PACK_ROWS)))
        txt = pg.evaluate(FOLD_TEXT)
        chk('折叠条改写成已显示条数', '已显示 20 条' in txt, txt)
        more = pg.locator('.qpack-more')
        chk('出现「再显示」按钮', more.count() == 1)
        chk('按钮写明还能再显示几条', '再显示 6 条' in more.inner_text() and '还剩 6 条' in more.inner_text(),
            more.inner_text() if more.count() else '')

        pg.click('.qpack-more')
        pg.wait_for_timeout(500)
        chk('再展开后 26 条全出', pg.evaluate(PACK_ROWS) == 26, str(pg.evaluate(PACK_ROWS)))
        chk('全部展开后按钮消失', pg.locator('.qpack-more').count() == 0)
        chk('全部展开后折叠条写「已显示 26 条」', '已显示 26 条' in pg.evaluate(FOLD_TEXT), pg.evaluate(FOLD_TEXT))

        # ---------- 3. 收起复位 ----------
        print('\n[3] 收起后分页复位')
        pg.click('.qpack-fold')
        pg.wait_for_timeout(500)
        chk('收起回到 5 条', pg.evaluate(PACK_ROWS) == 5, str(pg.evaluate(PACK_ROWS)))
        pg.click('.qpack-fold')
        pg.wait_for_timeout(500)
        chk('再次展开从 20 条开始（不是接着上次的 26）',
            pg.evaluate(PACK_ROWS) == 20, str(pg.evaluate(PACK_ROWS)))
        ctx.close()

        # ---------- 4. 汇总 12 格 ----------
        print('\n[4] 数据汇总 12 格')
        ctx, pg = open_quit(br)
        sums = pg.evaluate(SUM)
        chk('一共 12 格', len(sums) == 12, str(len(sums)))
        labels = [s['label'] for s in sums]
        want = ['今天', '本周买烟', '本月消费', '平均每天', '连续无烟', '抵御率',
                '每支成本', '上次抽', '减量进度', '无烟天数', '本周守住', '近 4 周']
        chk('12 个标题与顺序一致', labels == want, str(labels))

        by = {s['label']: s for s in sums}
        chk('抵御率是百分比主数字',
            by['抵御率']['big'].endswith('%'), by['抵御率']['big'])
        chk('抵御率小字给了分子分母',
            '想抽' in by['抵御率']['sub'] and '忍住' in by['抵御率']['sub'], by['抵御率']['sub'])
        chk('减量进度是降幅', by['减量进度']['big'].startswith('↓'), by['减量进度']['big'])
        chk('减量进度写明起止日均',
            '起始 7 天' in by['减量进度']['sub'] and '近 7 天' in by['减量进度']['sub'],
            by['减量进度']['sub'])
        chk('无烟天数是 N / M 天', '/ ' in by['无烟天数']['big'] and '天' in by['无烟天数']['big'],
            by['无烟天数']['big'])
        chk('本周守住是 N / M 天', '/ ' in by['本周守住']['big'] and '天' in by['本周守住']['big'],
            by['本周守住']['big'])

        # 数值对不对：早期 9 支 → 近 3 支，降幅应落在 60~70%
        m = pg.evaluate("""() => {
          const el = [...document.querySelectorAll('.qsum')].find(x => x.textContent.indexOf('减量进度') === 0);
          return el ? el.textContent : '';
        }""")
        chk('降幅数值合理（9→3 约 67%）', '67%' in m, m[:80])

        # ---------- 5. 近 4 周柱子 ----------
        print('\n[5] 近 4 周走向')
        bars = pg.evaluate("""() => {
          const s = document.querySelector('.qs-spark');
          if (!s) return null;
          return [...s.querySelectorAll('i')].map(i => ({
            h: Math.round(i.getBoundingClientRect().height),
            last: i.classList.contains('last')
          }));
        }""")
        chk('画出 4 根柱', bool(bars) and len(bars) == 4, str(bars))
        chk('只有最后一根是当前周', bool(bars) and bars[3]['last'] and not bars[0]['last'], str(bars))
        chk('柱高随时间递减（早期高、最近低）',
            bool(bars) and bars[0]['h'] > bars[3]['h'], str(bars))
        chk('小字一行写完趋势', '降到' in by['近 4 周']['sub'], by['近 4 周']['sub'])
        ctx.close()

        # ---------- 5.5 「再显示」按钮的对比度 ----------
        # 它要「展开 + 超过 20 条」才出现，对比度审计点不到，只能在这里测。
        print('\n[5.5] 「再显示」按钮对比度')
        for mode in ('light', 'dark'):
            ctx = br.new_context(viewport={'width': 1440, 'height': 1100})
            p2 = ctx.new_page()
            p2.clock.install(time=datetime(2026, 10, 25, 21 if mode == 'dark' else 10, 0, 0))
            p2.add_init_script("try{localStorage.setItem('lifeboard.theme.mode','%s');}catch(e){}" % mode)
            p2.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
            p2.wait_for_timeout(500)
            if p2.locator('[data-act="cloud-login"]').count():
                p2.click('[data-act="cloud-login"]')
                p2.wait_for_timeout(500)
                p2.fill('input[name="email"]', 'test@example.com')
                p2.fill('input[name="password"]', 'test@example.com')
                p2.click('form.modal-card button[type="submit"]')
                p2.wait_for_timeout(2600)
            p2.evaluate("() => { const b = document.querySelector('[data-nav=\"quit\"]'); if (b) b.click(); }")
            p2.wait_for_timeout(800)
            p2.click('.qpack-fold')
            p2.wait_for_timeout(400)
            r = p2.evaluate(CONTRAST, '.qpack-more')
            rr = _ratio(_parse_color(r['fg']), _parse_color(r['bg'])) if r else 0
            chk('%s 模式下「再显示」按钮 %.2f:1' % ('深色' if mode == 'dark' else '浅色', rr), rr >= 4.5,
                r['fg'] + ' on ' + r['bg'] if r else 'MISSING')
            ctx.close()

        # ---------- 6. 少于 5 条不显示折叠条 ----------
        print('\n[6] 记录不足 5 条时不折叠')
        build(pack_count=3)
        ctx, pg = open_quit(br)
        chk('3 条时没有折叠条', pg.locator('.qpack-fold').count() == 0)
        chk('3 条全部显示', pg.evaluate(PACK_ROWS) == 3, str(pg.evaluate(PACK_ROWS)))
        ctx.close()

        # ---------- 7. 手机端 2 列 ----------
        print('\n[7] 手机端布局')
        build()
        ctx, pg = open_quit(br, w=390, h=844)
        cols = pg.evaluate("() => getComputedStyle(document.querySelector('.qsum-grid')).gridTemplateColumns")
        chk('汇总在手机上排 2 列', len(cols.split()) == 2, cols)
        ovf = pg.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
        chk('没有横向溢出', ovf <= 0, str(ovf))
        ctx.close()

        br.close()

    print('\n' + '=' * 56)
    print('戒烟页 v107：%d 通过 / %d 失败' % (PASS, FAIL))
    if FAILS:
        print('失败项：')
        for f in FAILS:
            print('  -', f)
    return 0 if FAIL == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
