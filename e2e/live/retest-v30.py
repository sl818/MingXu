# -*- coding: utf-8 -*-
"""v30 线上专项复测：D1 按需用药记录 / D2 触摸热区 / D3 疗程过期提示。
断言全部基于线上真实数据重算或直接测量，不写死数字。
运行前设置 LIVE_EMAIL / LIVE_PWD。
"""
import json, os, sys
from playwright.sync_api import sync_playwright

BASE = os.environ.get('LIVE_BASE', 'https://your-domain.example/')
EMAIL = os.environ.get('LIVE_EMAIL', '')
PWD = os.environ.get('LIVE_PWD', '')
if not EMAIL or not PWD:
    sys.exit('请先设置 LIVE_EMAIL / LIVE_PWD')

PASS = FAIL = 0
FAILS = []


def rec(name, ok, detail=''):
    global PASS, FAIL
    if ok:
        PASS += 1
        print('  ✓ %s' % name)
    else:
        FAIL += 1
        FAILS.append((name, detail))
        print('  ✗ %s  << %s' % (name, detail))


def login(pg):
    pg.goto(BASE, wait_until='networkidle', timeout=90000)
    pg.wait_for_timeout(1500)
    if pg.locator('[data-act="cloud-login"]').count():
        pg.click('[data-act="cloud-login"]')
        pg.wait_for_timeout(800)
        pg.fill('input[name="email"]', EMAIL)
        pg.fill('input[name="password"]', PWD)
        pg.click('form.modal-card button[type="submit"]')
        pg.wait_for_timeout(6000)
    pg.wait_for_selector('[data-nav="today"]', state='attached', timeout=30000)


def nav(pg, v, wait=900):
    pg.evaluate("""v => {
        const l=[...document.querySelectorAll('[data-nav="'+v+'"]')];
        const e=l.find(x=>x.offsetParent!==null)||l[0];
        if(e) e.click();
    }""", v)
    pg.wait_for_timeout(wait)


def state(pg):
    return pg.evaluate("""async () => (await (await fetch('/api.php?action=load',{cache:'no-store'})).json()).data""")


with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)

    # ---------------- 桌面端：D1 + D3 ----------------
    ctx = br.new_context(viewport={'width': 1440, 'height': 950})
    pg = ctx.new_page()
    errs, cerrs = [], []
    pg.on('pageerror', lambda e: errs.append(str(e)[:180]))
    pg.on('console', lambda m: cerrs.append(m.text[:150]) if m.type == 'error' else None)
    login(pg)
    TODAY = pg.evaluate("() => new Date().toISOString().slice(0,10)")
    print('== 线上今天 %s ==' % TODAY)

    print('\n[D1] 按需用药行内记录')
    nav(pg, 'meds')
    info = pg.evaluate("""() => {
        const rows = [...document.querySelectorAll('.med-row')];
        const prn = rows.filter(r => /按需服用/.test(r.textContent));
        const add = [...document.querySelectorAll('[data-act="med-prn"]')];
        return {
            rows: rows.length,
            prnRows: prn.length,
            addBtns: add.length,
            ids: add.map(b => b.dataset.id),
            dates: [...new Set(add.map(b => b.dataset.date))],
            labels: [...document.querySelectorAll('.med-prn-add')].map(b => b.textContent.trim()),
            sample: prn.slice(0, 1).map(r => r.textContent.replace(/\\s+/g, ' ').trim().slice(0, 60))
        };
    }""")
    rec('用药页按需行出现「＋ 记一次」（%d 条按需药 / %d 个按钮）' % (info['prnRows'], info['addBtns']),
        info['addBtns'] == info['prnRows'] and info['addBtns'] >= 2, json.dumps(info['labels'], ensure_ascii=False))
    rec('按钮绑定日期 = 今天', info['dates'] == [TODAY], json.dumps(info['dates']))

    d0 = state(pg)
    target = info['ids'][0] if info['ids'] else ''
    before_n = len([k for k in ((d0.get('doses') or {}).get(TODAY, {}).get(target) or {}) if k.startswith('prn_')])

    pg.evaluate("""id => { const b=document.querySelector('[data-act="med-prn"][data-id="'+id+'"]'); if(b) b.click(); }""", target)
    pg.wait_for_timeout(2200)
    d1 = state(pg)
    after_n = len([k for k in ((d1.get('doses') or {}).get(TODAY, {}).get(target) or {}) if k.startswith('prn_')])
    rec('点击后云端多出一条按需剂量（%d → %d）' % (before_n, after_n), after_n == before_n + 1,
        json.dumps(((d1.get('doses') or {}).get(TODAY, {}).get(target) or {}), ensure_ascii=False)[:100])

    ui = pg.evaluate("""id => {
        const bp = document.querySelector('[data-act="med-prn-undo"][data-id="'+id+'"]');
        const row = bp ? bp.closest('.med-row') : document.querySelector('[data-act="med-prn"][data-id="'+id+'"]').closest('.med-row');
        const cnt = row.querySelector('.med-row-prn-cnt');
        return {undo: !!bp, cnt: cnt ? cnt.textContent.replace(/\\s+/g, ' ').trim() : ''};
    }""", target)
    rec('行内计数同步刷新', ('已记 %d 次' % after_n) in ui['cnt'], ui['cnt'])
    rec('出现「撤销」按钮', ui['undo'], '')

    pg.evaluate("""id => { const b=document.querySelector('[data-act="med-prn-undo"][data-id="'+id+'"]'); if(b) b.click(); }""", target)
    pg.wait_for_timeout(2200)
    d2 = state(pg)
    final_n = len([k for k in ((d2.get('doses') or {}).get(TODAY, {}).get(target) or {}) if k.startswith('prn_')])
    rec('撤销后恢复到点击前（%d）' % final_n, final_n == before_n, '')
    rec('刷新后页面仍可记录（按钮未被重建丢失）',
        pg.evaluate("""id => !!document.querySelector('[data-act="med-prn"][data-id="'+id+'"]')""", target), '')

    print('\n[D3] 疗程过期提示')
    exp = pg.evaluate("""() => {
        const rows=[...document.querySelectorAll('.med-row')];
        const groups=[...document.querySelectorAll('.med-group')];
        const g=groups.find(x=>/已停用/.test((x.querySelector('.med-group-head h3')||{}).textContent||''));
        const r=g ? g.querySelector('.med-row') : null;
        if(!r) return null;
        const name=(r.querySelector('.med-row-title b')||{}).textContent;
        r.querySelector('[data-act="med-edit"]').click();
        return {name};
    }""")
    pg.wait_for_timeout(1200)
    warn = pg.evaluate("""() => {
        const w=document.querySelector('#med-form .hint-warn');
        const f=document.querySelector('#med-form');
        return {has: !!w, text: w ? w.textContent.replace(/\\s+/g,' ').trim() : '',
                first: f ? (f.children[1]||{}).className : '',
                end: f ? (f.querySelector('[name="endDate"]')||{}).value : ''};
    }""")
    rec('已停用组第一条药（%s）编辑弹窗出现提示' % (exp['name'] if exp else '无'), warn['has'], warn['text'][:60])
    rec('提示里写明结束日期', bool(warn['end']) and warn['end'] in warn['text'], warn['end'])
    rec('提示位于标题下方（第一个内容块）', warn['first'] == 'hint hint-warn', warn['first'])
    pg.keyboard.press('Escape')
    pg.wait_for_timeout(600)

    pg.evaluate("""() => {
        const rows=[...document.querySelectorAll('.med-row')];
        const r=rows.find(x=>/阿奇霉素|连花清瘟|头孢地尼|盐酸氨溴索|铝镁加/.test(x.textContent));
        if(r) r.querySelector('[data-act="med-edit"]').click();
    }""")
    pg.wait_for_timeout(1200)
    rec('未过期的短期疗程不显示该提示',
        pg.evaluate("() => document.querySelectorAll('#med-form .hint-warn').length") == 0, '')
    pg.keyboard.press('Escape')
    pg.wait_for_timeout(600)

    print('\n[桌面端不受热区规则影响]')
    desk = pg.evaluate("""() => {
        const e=document.querySelector('.remind-go'); if(!e) return 'none';
        const cs=getComputedStyle(e,'::after');
        return {w: parseFloat(cs.width)||0, h: parseFloat(cs.height)||0,
                box: Math.round(e.getBoundingClientRect().height)};
    }""")
    rec('桌面端 ::after 覆盖层为 0（视觉未变）', desk != 'none' and desk['w'] == 0 and desk['h'] == 0, json.dumps(desk))
    ctx.close()

    # ---------------- 移动端：D2 ----------------
    print('\n[D2] 触摸端热区')
    mctx = br.new_context(viewport={'width': 390, 'height': 844}, has_touch=True, is_mobile=True, device_scale_factor=2)
    mp = mctx.new_page()
    mp.on('pageerror', lambda e: errs.append(str(e)[:180]))
    mp.on('console', lambda m: cerrs.append(m.text[:150]) if m.type == 'error' else None)
    login(mp)
    rec('触摸设备判定生效', mp.evaluate("() => matchMedia('(pointer: coarse)').matches"), '')

    SIZE = """s => { const e=document.querySelector(s); if(!e) return null;
        const r=e.getBoundingClientRect(); const cs=getComputedStyle(e,'::after');
        return {w: Math.round(Math.max(r.width, parseFloat(cs.width)||0)),
                h: Math.round(Math.max(r.height, parseFloat(cs.height)||0)),
                boxH: Math.round(r.height)}; }"""
    for sel, label in (('.remind-go', '「去看看」'), ('.remind-x', '「今天不再提醒」')):
        r = mp.evaluate(SIZE, sel)
        rec('%s 热区 ≥40（%s）' % (label, ('%dx%d' % (r['w'], r['h'])) if r else '元素不存在'),
            bool(r) and r['w'] >= 40 and r['h'] >= 40, json.dumps(r))

    nav(mp, 'today')
    mp.evaluate("""() => {
        const l=[...document.querySelectorAll('[data-act="date-shift"]')];
        const e=l.find(x=>x.dataset.delta==='-1');
        if(e) e.click();
    }""")
    mp.wait_for_timeout(1200)
    bf = mp.evaluate(SIZE, '.backfill-today')
    rec('补记条「回今天」热区 ≥40（%s）' % (('%dx%d' % (bf['w'], bf['h'])) if bf else '元素不存在'),
        bool(bf) and bf['w'] >= 40 and bf['h'] >= 40, json.dumps(bf))
    mp.evaluate("""() => { const b=document.querySelector('[data-act="date-today"]'); if(b) b.click(); }""")
    mp.wait_for_timeout(900)

    nav(mp, 'meds', 1200)
    pr = mp.evaluate(SIZE, '.med-prn-add')
    rec('按需「＋ 记一次」热区 ≥40（%s）' % (('%dx%d' % (pr['w'], pr['h'])) if pr else '元素不存在'),
        bool(pr) and pr['w'] >= 40 and pr['h'] >= 40, json.dumps(pr))
    rec('移动端也能看到按需记录入口（%d 个）' % mp.evaluate("() => document.querySelectorAll('[data-act=\"med-prn\"]').length"),
        mp.evaluate("() => document.querySelectorAll('[data-act=\"med-prn\"]').length") >= 2, '')

    print('\n[错误汇总]')
    rec('线上无 JS 运行时异常', len(errs) == 0, json.dumps(errs[:3], ensure_ascii=False))
    rec('线上无 console error', len(cerrs) == 0, json.dumps(cerrs[:3], ensure_ascii=False))

    print('\n===== 线上复测：%d 通过 / %d 失败 =====' % (PASS, FAIL))
    for n, d in FAILS:
        print('  - %s | %s' % (n, d))
    mctx.close()
    br.close()
