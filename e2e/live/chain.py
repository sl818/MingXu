# -*- coding: utf-8 -*-
"""功能衔接链路测试（只读为主，不新增/删除数据）。"""
import json, os
from playwright.sync_api import sync_playwright
from mkdata import login

SHOTS = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo/design/live-test'
PASS = FAIL = 0
FAILS = []


def rec(n, ok, d=''):
    global PASS, FAIL
    if ok:
        PASS += 1
        print('  ✓ %s' % n)
    else:
        FAIL += 1
        FAILS.append((n, d))
        print('  ✗ %s  << %s' % (n, d))


with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)
    ctx = br.new_context(viewport={'width': 1440, 'height': 950})
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)[:160]))
    login(pg)

    print('[A] 日历 → 今日页 补记链路')
    pg.evaluate("""() => { const b=document.querySelector('[data-nav="calendar"]'); if(b) b.click(); }""")
    pg.wait_for_timeout(900)
    pg.evaluate("""() => { const b=document.querySelector('[data-act="pick-day"][data-date="2026-10-22"]'); if(b) b.click(); }""")
    pg.wait_for_timeout(1000)
    bf = pg.evaluate("""() => ({
        bar: (document.querySelector('.backfill-bar')||{}).textContent||'',
        has: !!document.querySelector('.backfill-bar'),
        hero: (document.querySelector('.hero-date')||{}).textContent||'',
        today: !!document.querySelector('[data-act="date-today"]') })""")
    rec('点日历 10-22 跳到今日页并出现补记提示条', bf['has'] and '10 月 22 日' in bf['bar'], bf['bar'].strip()[:36])
    rec('补记模式 hero 日期切到 10 月 22 日', '10 月 22 日' in bf['hero'], bf['hero'].strip()[:30])
    pg.screenshot(path=SHOTS + '/pc-12-backfill.png')
    pg.evaluate("""() => { const b=document.querySelector('[data-act="date-today"]'); if(b) b.click(); }""")
    pg.wait_for_timeout(900)
    rec('点「回今天」恢复正常',
        not pg.evaluate("() => !!document.querySelector('.backfill-bar')") and
        '10 月 26 日' in pg.evaluate("() => (document.querySelector('.hero-date')||{}).textContent||''"), '')

    print('\n[B] 搜索 → 跳转 → 高亮 链路')
    pg.keyboard.press('Control+k')
    pg.wait_for_timeout(600)
    pg.fill('#search-input', '晨间拉伸')
    pg.wait_for_timeout(800)
    pg.keyboard.press('Enter')
    pg.wait_for_timeout(700)   # 高亮只维持 1.8s，必须尽快取样
    jump = pg.evaluate("""() => ({
        modal: !!document.querySelector('#search-input'),
        focus: document.querySelectorAll('.is-focus').length,
        view: document.body.dataset.view,
        text: (document.querySelector('.is-focus')||{}).textContent || '' })""")
    rec('回车跳转到习惯页', jump['view'] == 'habits', 'view=%s' % jump['view'])
    rec('目标习惯卡被高亮', jump['focus'] >= 1 and '晨间拉伸' in jump['text'], json.dumps(jump, ensure_ascii=False)[:100])
    rec('搜索浮层已关闭', not jump['modal'], '')

    print('\n[C] 统计页区间切换')
    pg.evaluate("""() => { const b=document.querySelector('[data-nav="stats"]'); if(b) b.click(); }""")
    pg.wait_for_timeout(1100)
    for rng in ('7', '30', '90'):
        pg.evaluate("""r => { const b=document.querySelector('[data-act="set-stats-range"][data-range="'+r+'"]'); if(b) b.click(); }""", rng)
        pg.wait_for_timeout(800)
        info = pg.evaluate("""() => ({
            bars: document.querySelectorAll('.chart > div').length,
            ovf: document.documentElement.scrollWidth - window.innerWidth,
            rev: document.querySelectorAll('.rv-cell').length })""")
        rec('统计区间 %s 天：柱数 %d、本月回顾仍在、无横溢' % (rng, info['bars']),
            info['bars'] >= 6 and info['rev'] == 6 and info['ovf'] <= 0, json.dumps(info))

    print('\n[D] 9 套皮肤 × 三种布局（桌面）')
    pg.evaluate("""() => { const b=document.querySelector('[data-nav="settings"]'); if(b) b.click(); }""")
    pg.wait_for_timeout(1100)
    rec('设置页可见 9 套皮肤卡片', pg.evaluate("() => document.querySelectorAll('[data-act=\"set-skin\"]').length") == 9, '')
    skins = ['paper', 'slate', 'mono', 'clay', 'mist', 'forest', 'neu', 'cyber', 'retro']
    bad = []
    for s in skins:
        pg.evaluate("""s => { const b=document.querySelector('[data-act="set-skin"][data-skin="'+s+'"]'); if(b) b.click(); }""", s)
        pg.wait_for_timeout(450)
        i = pg.evaluate("""() => ({ ovf: document.documentElement.scrollWidth - window.innerWidth,
            skin: document.documentElement.dataset.skin,
            visible: (document.getElementById('main').innerText||'').length })""")
        if i['ovf'] > 0 or i['skin'] != s or i['visible'] < 100:
            bad.append((s, i))
    rec('9 套皮肤切换均正常（无横溢/无空白）', not bad, json.dumps(bad[:3], ensure_ascii=False))
    for lay in ('wide', 'side', 'top'):
        pg.evaluate("""l => { const b=document.querySelector('[data-act="set-layout"][data-layout="'+l+'"]'); if(b) b.click(); }""", lay)
        pg.wait_for_timeout(550)
        i = pg.evaluate("""() => ({ ovf: document.documentElement.scrollWidth - window.innerWidth,
            layout: document.documentElement.getAttribute('data-layout'),
            nav: document.querySelectorAll('.sidebar .nav-item, #mobile-nav [data-nav]').length })""")
        rec('布局「%s」生效且无横溢' % lay, i['layout'] == lay and i['ovf'] <= 0, json.dumps(i))
    pg.evaluate("""() => { const b=document.querySelector('[data-act="set-skin"][data-skin="paper"]'); if(b) b.click(); }""")
    pg.wait_for_timeout(400)
    pg.evaluate("""() => { const b=document.querySelector('[data-act="set-layout"][data-layout="wide"]'); if(b) b.click(); }""")
    pg.wait_for_timeout(400)

    print('\n[E] 编辑类弹窗（只开不存）')
    for view, act, form, label in (('board', 'task-edit', '#task-form', '待办编辑'),
                                   ('essays', 'essay-edit', '#essay-form', '随笔编辑'),
                                   ('meds', 'med-edit', '#med-form', '用药编辑'),
                                   ('weight', 'weight-edit', '#weight-form', '体重编辑')):
        pg.evaluate("""v => { const b=document.querySelector('[data-nav="'+v+'"]'); if(b) b.click(); }""", view)
        pg.wait_for_timeout(900)
        ok = pg.evaluate("""a => { const b=document.querySelector('[data-act="'+a+'"]'); if(!b) return false; b.click(); return true; }""", act)
        pg.wait_for_timeout(900)
        opened = pg.locator(form).count() == 1
        filled = pg.evaluate("""f => {
            const el=document.querySelector(f);
            if(!el) return 0;
            return [...el.querySelectorAll('input,select,textarea')].filter(x=>x.value!=='').length; }""", form)
        rec('%s 弹窗可打开且带原值（%d 个字段有值）' % (label, filled), ok and opened and filled >= 2, '')
        pg.keyboard.press('Escape')
        pg.wait_for_timeout(500)

    print('\n[F] 习惯编辑 / 排序 / 归档视图')
    pg.evaluate("""() => { const b=document.querySelector('[data-nav="habits"]'); if(b) b.click(); }""")
    pg.wait_for_timeout(900)
    pg.evaluate("""() => { const b=document.querySelector('[data-act="habit-edit"]'); if(b) b.click(); }""")
    pg.wait_for_timeout(800)
    rec('习惯编辑弹窗可打开', pg.locator('#habit-form').count() == 1, '')
    pg.keyboard.press('Escape')
    pg.wait_for_timeout(500)
    for s in ('progress', 'streak', 'created'):
        pg.evaluate("""s => { const b=document.querySelector('[data-act="habit-sort"][data-sort="'+s+'"]'); if(b) b.click(); }""", s)
        pg.wait_for_timeout(600)
        n = pg.evaluate("() => document.querySelectorAll('.habit-row:not(.archived)').length")
        rec('习惯排序「%s」后列表完整（%d 行）' % (s, n), n >= 16, 'n=%d' % n)
    pg.evaluate("""() => { const b=document.querySelector('[data-nav="board"]'); if(b) b.click(); }""")
    pg.wait_for_timeout(1000)
    pg.evaluate("""() => { const b=document.querySelector('[data-act="archive-open"]'); if(b) b.click(); }""")
    pg.wait_for_timeout(900)
    rec('归档视图可打开', pg.evaluate("() => !!document.querySelector('#modal-root .modal-card')"), '')
    pg.keyboard.press('Escape')
    pg.wait_for_timeout(400)

    print('\n[G] 错误汇总')
    rec('链路测试全程无 JS 异常', len(errs) == 0, json.dumps(errs[:3], ensure_ascii=False))

    print('\n===== 链路：%d 通过 / %d 失败 =====' % (PASS, FAIL))
    for n, d in FAILS:
        print('  - %s | %s' % (n, d))
    ctx.close()
    br.close()
