# -*- coding: utf-8 -*-
"""v102：小习惯卡的三处收尾（文档 P1 剩下两项 + 多目标瘦身）。

锁四件事：
  1. 最长纪录：只比当前连续长时才出现在小字里，两者相等时不许冒出来
  2. 多目标卡：圆点与「n / m」在同一行（同一个 .habit-pips-row），不再上下两行
  3. 打卡回馈：点了会调 WAAPI 动效 + navigator.vibrate
  4. 撤销不给动效（否则撤销看起来也像一次奖励）

动效那条**不能装假时钟**：habitPulse 把 animate 排在 requestAnimationFrame 里，
Playwright 的 clock.install 会把 rAF 一起接管，断言会变成测时钟而不是测代码。
所以分两个 context：带时钟的测「最长 / 布局」，真时钟的测「动效 / 震动」。
"""
import os, sys

ROOT = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo'
head = open(os.path.join(ROOT, 'e2e', 'verify-batch4.py'), encoding='utf-8').read().split('with sync_playwright() as p:')[0]
sys.argv = [sys.argv[0]]
exec(head)

from datetime import datetime
from playwright.sync_api import sync_playwright

# 给 h_read 补一段 9/10–9/20 的连续记录（11 天），让「最长」与「当前 5 天」拉开差距
for _d in range(10, 21):
    CHECKS['2026-09-%02d' % _d] = {'h_read': 3}

PASS = FAIL = 0
FAILS = []


def chk(name, ok, detail=''):
    global PASS, FAIL
    if ok:
        PASS += 1
        print('  \u2713 %s' % name)
    else:
        FAIL += 1
        FAILS.append(name)
        print('  \u2717 %s  << %s' % (name, detail))


def card_info(pg, name):
    """按名字取一张卡：小字、圆点行、计数、控件。"""
    return pg.evaluate("""(name) => {
        const el = [...document.querySelectorAll('.habit-grid .habit-card')]
            .find(x => ((x.querySelector('.habit-title b') || {}).textContent || '') === name);
        if (!el) return null;
        const cap = el.querySelector('.hp-cap');
        const row = el.querySelector('.habit-pips-row');
        const pips = el.querySelectorAll('.pips .pip');
        const cnt = el.querySelector('.habit-count');
        let dy = null, sameRow = null;
        if (row && pips.length && cnt) {
            const a = pips[0].getBoundingClientRect(), b = cnt.getBoundingClientRect();
            dy = Math.abs((a.top + a.height / 2) - (b.top + b.height / 2));
            sameRow = pips[0].closest('.habit-pips-row') === cnt.closest('.habit-pips-row');
        }
        return {
            cap: cap ? (cap.textContent || '').trim() : '',
            hasRow: !!row,
            pips: pips.length,
            count: cnt ? (cnt.textContent || '').replace(/\\s+/g, '') : '',
            dy: dy, sameRow: sameRow,
            state: (el.querySelector('.habit-state') || {}).textContent || ''
        };
    }""", name)


def login_and_today(pg):
    pg.wait_for_timeout(400)
    if pg.locator('[data-act="cloud-login"]').count():
        pg.click('[data-act="cloud-login"]')
        pg.wait_for_timeout(400)
        pg.fill('input[name="email"]', 'test@example.com')
        pg.fill('input[name="password"]', 'test@example.com')
        pg.click('form.modal-card button[type="submit"]')
        pg.wait_for_timeout(2600)
    pg.evaluate("() => { const b=document.querySelector('[data-nav=\"today\"]'); if(b) b.click(); }")
    pg.wait_for_timeout(700)


with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)

    # ---------- A. 带假时钟：最长纪录 + 一行布局 ----------
    ctx = br.new_context(viewport={'width': 1512, 'height': 950})
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)[:180]))
    pg.clock.install(time=datetime(2026, 10, 25, 10, 0, 0))
    pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
    login_and_today(pg)

    print('[1] 最长纪录：只在比当前长时出现')
    read = card_info(pg, '读书')
    chk('读书卡有证据层小字', bool(read) and read['cap'] != '', str(read))
    chk('读书 当前 5 天 · 最长 11 天',
        bool(read) and '连续达标' in read['cap'] and '最长 11 天' in read['cap'],
        read['cap'] if read else '')
    run = card_info(pg, '夜跑')
    chk('夜跑 当前就是最长时不写「最长」',
        bool(run) and '最长' not in run['cap'], run['cap'] if run else '')

    print('[2] 多目标卡：圆点与计数并成一行')
    chk('读书卡有 .habit-pips-row', bool(read) and read['hasRow'], str(read))
    chk('圆点仍是 3 格（一次点选的控件没删）', bool(read) and read['pips'] == 3, str(read))
    chk('计数仍在（3 / 3 页）', bool(read) and read['count'].startswith('3'), read['count'] if read else '')
    chk('圆点与计数在同一行（中线差 < 8px）', bool(read) and read['dy'] is not None and read['dy'] < 8,
        str(read['dy'] if read else None))
    chk('两者同属一个 .habit-pips-row', bool(read) and read['sameRow'] is True, str(read))
    ctx.close()

    # ---------- B. 真时钟：打卡动效与震动 ----------
    ctx = br.new_context(viewport={'width': 1512, 'height': 950})
    pg = ctx.new_page()
    pg.on('pageerror', lambda e: errs.append(str(e)[:180]))
    pg.add_init_script("""
        window.__an = 0; window.__vib = 'none';
        const orig = Element.prototype.animate;
        Element.prototype.animate = function () { window.__an++; return orig.apply(this, arguments); };
        try {
            Object.defineProperty(navigator, 'vibrate', {
                value: function (v) { window.__vib = v; return true; }, configurable: true
            });
        } catch (e) { /* 有的浏览器不让覆盖，震动那条会自动降级 */ }
    """)
    pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
    login_and_today(pg)

    print('[3] 打卡有动效与轻震动')
    before = pg.evaluate('() => window.__an')
    chk('点之前没有动效', before == 0, str(before))
    pg.click('.habit-card:has(.habit-title b:text-is("事项复盘")) .habit-done')
    pg.wait_for_timeout(700)
    after = pg.evaluate('() => window.__an')
    vib = pg.evaluate('() => window.__vib')
    chk('打卡后调用了动效', after > before, '%s -> %s' % (before, after))
    chk('动效打在两处（控件 + 今天那一格）', after >= 2, str(after))
    chk('触发了轻震动', vib == 12, str(vib))
    chk('状态变成「已完成」', (card_info(pg, '事项复盘') or {}).get('state') == '已完成',
        str(card_info(pg, '事项复盘')))

    print('[4] 撤销不给动效')
    pg.click('.habit-card:has(.habit-title b:text-is("事项复盘")) .habit-done')
    pg.wait_for_timeout(700)
    undo = pg.evaluate('() => window.__an')
    chk('撤销没有新增动效', undo == after, '%s -> %s' % (after, undo))
    chk('撤销后回到「待打卡」', (card_info(pg, '事项复盘') or {}).get('state') == '待打卡',
        str(card_info(pg, '事项复盘')))

    print('[5] 无 JS 报错')
    chk('没有页面异常', not errs, ' / '.join(errs[:2]))

    br.close()

print('\nv102 小习惯卡收尾：%d/%d 通过' % (PASS, PASS + FAIL))
if FAILS:
    print('失败项：' + '、'.join(FAILS))
    sys.exit(1)
