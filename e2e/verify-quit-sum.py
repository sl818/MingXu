# -*- coding: utf-8 -*-
"""戒烟「数据汇总」验证（v82/v83）：
戒烟页 8 张卡 + 一根 24 小时时段条；统计页同一组卡，但不再重复画第二根时段条。"""
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
         'unit': '根', 'color': '#7a8471', 'note': '', 'createdAt': '2026-10-01T08:00:00Z',
         'pinned': True, 'med': False, 'quitStart': '2026-10-01',
         'quitPerDay': 20, 'quitPackPrice': 15, 'quitPackSize': 20}

TODAY = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)


def ts(d, h, m):
    return int((d + timedelta(hours=h, minutes=m)).timestamp())


def build():
    """近 9 天：8 包烟、每天若干支、每天 3 次「忍一次」，中间空两天。"""
    packs = []
    for i in range(8):
        d = TODAY - timedelta(days=9 - i)
        packs.append({'id': 'p%d' % i, 'at': ts(d, 8, 30), 'name': '普皖', 'price': 15, 'size': 20})
    crav, n = [], 0
    for i in range(9):
        d = TODAY - timedelta(days=8 - i)
        if i in (2, 5):
            continue
        for j in range(6 + (i % 4)):
            crav.append({'id': 'c%d' % n, 't': ts(d, 8 + (j * 2) % 13, (j * 17) % 60),
                         'k': 's', 'h': 'h_smoke', 'g': '', 's': 0})
            n += 1
        for j in range(3):
            crav.append({'id': 'r%d' % n, 't': ts(d, 15, j * 20),
                         'k': 'r', 'h': 'h_smoke', 'g': '', 's': 0})
            n += 1
    crav.sort(key=lambda e: e['t'])
    return packs, crav


packs, crav = build()


def open_page(pg, nav):
    pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
    pg.wait_for_timeout(500)
    if pg.locator('[data-act="cloud-login"]').count():
        pg.click('[data-act="cloud-login"]')
        pg.wait_for_timeout(400)
        pg.fill('input[name="email"]', 'test@example.com')
        pg.fill('input[name="password"]', 'test@example.com')
        pg.click('form.modal-card button[type="submit"]')
        pg.wait_for_timeout(2600)
    pg.evaluate("(n) => { const b=document.querySelector('[data-nav=\"'+n+'\"]'); if(b) b.click(); }", nav)
    pg.wait_for_timeout(700)


def sum_panel(pg, kw):
    return pg.evaluate("""(kw) => {
        const p = [...document.querySelectorAll('.panel')].find(x => {
            const h = x.querySelector('h3');
            return h && (h.textContent || '').indexOf(kw) === 0;
        });
        if (!p) return null;
        return {
            cards: [...p.querySelectorAll('.qsum')].map(c => ({
                label: (c.querySelector('small') || {}).textContent || '',
                big: (c.querySelector('b') || {}).textContent || '',
                sub: (c.querySelector('span') || {}).textContent || ''
            })),
            hourBars: p.querySelectorAll('.qs-bar').length,
            hourTitle: (p.querySelector('.qs-head small') || {}).textContent || ''
        };
    }""", kw)


def card(sp, label):
    for c in (sp or {}).get('cards', []):
        if c['label'] == label:
            return c
    return None


with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome')
    board['data']['habits'] = [SMOKE]
    board['data']['packs'] = packs
    board['data']['cravings'] = crav

    print('\n[1] 戒烟页：8 张卡 + 时段条')
    pg = br.new_page(viewport={'width': 1440, 'height': 950})
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    open_page(pg, 'quit')
    sp = sum_panel(pg, '数据汇总')
    chk('有「数据汇总」面板', sp is not None)
    chk('正好 8 张卡', len((sp or {}).get('cards', [])) == 8, str(len((sp or {}).get('cards', []))))
    want = ['今天', '本周买烟', '本月消费', '平均每天', '连续无烟', '忍住了', '每支成本', '上次抽']
    got = [c['label'] for c in (sp or {}).get('cards', [])]
    chk('八张卡的标签齐全', got == want, str(got))
    chk('底部有 24 根时段柱', (sp or {}).get('hourBars') == 24, str((sp or {}).get('hourBars')))
    chk('时段条标题是「时段分布」', (sp or {}).get('hourTitle') == '时段分布', str((sp or {}).get('hourTitle')))

    print('\n[2] 口径写在小字上')
    avg = card(sp, '平均每天') or {}
    chk('平均每天标了分母天数', '近' in avg.get('sub', '') and '天' in avg.get('sub', ''), str(avg.get('sub')))
    mo = card(sp, '本月消费') or {}
    chk('本月消费标了「按买烟日期」', '按买烟日期' in mo.get('sub', ''), str(mo.get('sub')))
    unit = card(sp, '每支成本') or {}
    chk('每支成本是 ¥ 单价', unit.get('big', '').startswith('¥'), str(unit.get('big')))
    last = card(sp, '上次抽') or {}
    ok_last = ('前' in last.get('big', '')) or (last.get('big') == '还没有记录')
    chk('上次抽是紧凑时长（不折三行）', ok_last and len(last.get('big', '')) <= 8, str(last.get('big')))
    res = card(sp, '忍住了') or {}
    chk('忍住率带了分母说明', '忍住率' in res.get('sub', '') or res.get('sub') == '还没有记录', str(res.get('sub')))
    chk('戒烟页无 JS 异常', not errs, str(errs[:2]))
    pg.close()

    print('\n[3] 统计页：并进「戒烟」块，分析默认折起来')
    pg = br.new_page(viewport={'width': 1440, 'height': 950})
    errs2 = []
    pg.on('pageerror', lambda e: errs2.append(str(e)))
    open_page(pg, 'stats')
    ss = sum_panel(pg, '戒烟')
    chk('统计页有「戒烟」块', ss is not None)
    chk('统计页也是 8 张卡', len((ss or {}).get('cards', [])) == 8, str(len((ss or {}).get('cards', []))))
    chk('统计页不再画第二根时段条', (ss or {}).get('hourBars') == 0, str((ss or {}).get('hourBars')))
    chk('分析默认折叠（没有 24 根柱）',
        pg.evaluate("() => document.querySelectorAll('.qh-bar').length") == 0,
        str(pg.evaluate("() => document.querySelectorAll('.qh-bar').length")))
    chk('有「展开分析」按钮',
        pg.locator('[data-act="stats-quit-fold"]').count() == 1)
    pg.click('[data-act="stats-quit-fold"]')
    pg.wait_for_timeout(500)
    chk('展开后出现 24 根柱',
        pg.evaluate("() => document.querySelectorAll('.qh-bar').length") == 24,
        str(pg.evaluate("() => document.querySelectorAll('.qh-bar').length")))
    chk('展开后出现勋章墙', pg.evaluate("() => document.querySelectorAll('.qmile-i').length") > 0)
    pg.click('[data-act="stats-quit-fold"]')
    pg.wait_for_timeout(400)
    chk('再点一次收回去',
        pg.evaluate("() => document.querySelectorAll('.qh-bar').length") == 0)
    chk('统计页无 JS 异常', not errs2, str(errs2[:2]))
    pg.close()

    print('\n[4] 没有戒烟习惯时两块都不渲染')
    board['data']['habits'] = []
    board['data']['packs'] = []
    board['data']['cravings'] = []
    pg = br.new_page(viewport={'width': 1440, 'height': 950})
    errs3 = []
    pg.on('pageerror', lambda e: errs3.append(str(e)))
    open_page(pg, 'stats')
    chk('统计页没有「戒烟」块', sum_panel(pg, '戒烟') is None)
    chk('也没有 8 张卡', pg.evaluate("() => document.querySelectorAll('.qsum').length") == 0)
    chk('无 JS 异常', not errs3, str(errs3[:2]))
    pg.close()
    br.close()

print('\n===== 戒烟数据汇总：%d 通过 / %d 失败 =====' % (PASS, FAIL))
if FAILS:
    print('失败：' + ' / '.join(FAILS))
sys.exit(1 if FAIL else 0)
