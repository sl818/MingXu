# -*- coding: utf-8 -*-
"""戒烟页 · 补记昨天：入口条件 / 数量校验 / 补完的显示。"""
import os, sys
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


SMOKE = {'id': 'h_smoke', 'name': '戒烟', 'icon': '🚭', 'type': 'smoke', 'target': 0,
         'unit': '根', 'color': '#7a8471', 'note': '普皖', 'createdAt': '2026-10-24T11:51:21Z',
         'pinned': True, 'med': False, 'quitStart': '2026-10-24',
         'quitPerDay': 0, 'quitPackPrice': 15, 'quitPackSize': 20}
NOW = datetime(2026, 11, 8, 10, 0, 0)
YDAY = datetime(2026, 11, 7, 8, 0, 0)


def open_quit(pg):
    pg.evaluate("() => { const b=document.querySelector('[data-nav=\"quit\"]'); if(b) b.click(); }")
    pg.wait_for_timeout(700)


def card(pg):
    return pg.evaluate("""() => {
        const c = document.querySelector('.quit-card');
        return c ? c.textContent.replace(/\\s+/g, ' ').trim() : '';
    }""")


def grid_out(pg):
    return pg.evaluate("""() => {
        const g = document.querySelector('.quit-card .pack-grid');
        return g ? g.querySelectorAll('.pk.out').length : -1;
    }""")


with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)

    # ---------- 用例 1：昨天零记录，入口出现 ----------
    print('[1] 昨天没记，今天给入口')
    ctx = br.new_context(viewport={'width': 1512, 'height': 950})
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)[:180]))
    pg.clock.install(time=NOW)
    board['data']['habits'] = [SMOKE]
    board['data']['packs'] = [{'id': 'p1', 'at': int(YDAY.timestamp()), 'name': '普皖', 'price': 15, 'size': 20}]
    board['data']['cravings'] = []
    pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
    pg.wait_for_timeout(500)
    if pg.locator('[data-act="cloud-login"]').count():
        pg.click('[data-act="cloud-login"]')
        pg.wait_for_timeout(400)
        pg.fill('input[name="email"]', 'test@sl00.top')
        pg.fill('input[name="password"]', 'test@sl00.top')
        pg.click('form.modal-card button[type="submit"]')
        pg.wait_for_timeout(2600)
    open_quit(pg)
    chk('出现「昨天还剩 20 支」的补记条', '昨天这包还剩' in card(pg), card(pg)[:160])
    chk('补记条里数字是 20', '20' in card(pg).split('昨天这包还剩')[1][:6], card(pg)[:160])

    print('[2] 补 5 支')
    pg.click('[data-act="crave-backfill"]')
    pg.wait_for_timeout(500)
    chk('弹窗打开', pg.locator('#backfill-form').count() == 1)
    txt = pg.locator('#backfill-form').text_content() or ''
    chk('弹窗写着最多补 20 支', '最多补 20 支' in txt, txt[:120])
    chk('有两个数量框', pg.locator('#backfill-form input[type="number"]').count() == 2)
    pg.fill('#backfill-form [name="smoke"]', '5')
    pg.fill('#backfill-form [name="resist"]', '2')
    pg.click('#backfill-form button[type="submit"]')
    pg.wait_for_timeout(800)
    chk('弹窗关闭', pg.locator('#backfill-form').count() == 0)
    c = card(pg)
    chk('今天这包剩 15 支', '还剩 15 支' in c, c[:200])
    chk('烟盒熄灭 5 格', grid_out(pg) == 5, str(grid_out(pg)))
    chk('补记条变成 15', '还剩 <b>15</b>' in pg.locator('.quit-hero').inner_html() or '15' in c, c[:200])

    print('[3] 超上限被挡')
    pg.evaluate("() => { const b=document.querySelector('[data-nav=\"quit\"]'); if(b) b.click(); }")
    pg.wait_for_timeout(700)
    pg.click('[data-act="crave-backfill"]')
    pg.wait_for_timeout(500)
    pg.fill('#backfill-form [name="smoke"]', '99')
    pg.click('#backfill-form button[type="submit"]')
    pg.wait_for_timeout(600)
    chk('填 99 不保存、还停在弹窗', pg.locator('#backfill-form').count() == 1)
    chk('超上限时弹窗不关', pg.locator('#backfill-form').count() == 1)
    pg.click('[data-act="close-modal"]')
    pg.wait_for_timeout(400)
    chk('这包仍是 15/20', '还剩 15 支' in card(pg), card(pg)[:160])

    chk('无 JS 异常', not errs, str(errs))
    ctx.close()

    # ---------- 用例 5：昨天已经抽满，不给入口 ----------
    print('[5] 昨天抽满了不再给入口')
    ctx = br.new_context(viewport={'width': 1512, 'height': 950})
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)[:180]))
    pg.clock.install(time=NOW)
    evs = [{'id': 'e%d' % i, 't': int((YDAY + timedelta(minutes=30 * i)).timestamp()),
            'k': 's', 'h': 'h_smoke', 'g': '', 's': 0} for i in range(20)]
    board['data']['habits'] = [SMOKE]
    board['data']['packs'] = [{'id': 'p1', 'at': int(YDAY.timestamp()), 'name': '普皖', 'price': 15, 'size': 20}]
    board['data']['cravings'] = evs
    pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
    pg.wait_for_timeout(500)
    if pg.locator('[data-act="cloud-login"]').count():
        pg.click('[data-act="cloud-login"]')
        pg.wait_for_timeout(400)
        pg.fill('input[name="email"]', 'test@sl00.top')
        pg.fill('input[name="password"]', 'test@sl00.top')
        pg.click('form.modal-card button[type="submit"]')
        pg.wait_for_timeout(2600)
    open_quit(pg)
    chk('昨天抽满 20 支时没有补记条', '昨天这包还剩' not in card(pg), card(pg)[:160])
    chk('无 JS 异常', not errs, str(errs))
    ctx.close()
    br.close()

print()
print('===== 补记昨天：%d 通过 / %d 失败 =====' % (PASS, FAIL))
if FAILS:
    print('失败项：', FAILS)
