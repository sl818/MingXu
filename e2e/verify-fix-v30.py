# -*- coding: utf-8 -*-
"""修复验证（v30）：D1 按需用药行内记录 / D2 提醒条与补记条热区 / D3 疗程过期提示。

复用 e2e/verify-batch4.py 的 mock 服务，不碰线上数据。
用法: python e2e/verify-fix-v30.py
"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
head = open(os.path.join(ROOT, 'e2e', 'verify-batch4.py'), encoding='utf-8').read()
head = head.split('with sync_playwright() as p:')[0]
sys.argv = [sys.argv[0]]          # 清掉外部参数，避免 ONLY 生效
exec(head)

# 追加一条「疗程已过期」的短期药 + 一条暂停的按需药，用于 D1 / D3 边界
board['data']['meds'] += [
    med('m_short_exp', '过期头孢', 'short', ['09:00'], start='2026-10-10', end='2026-10-20'),
    {**med('m_prn_paused', '暂停止痛片', 'prn', []), 'status': 'paused'},
]

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


def doses(pg):
    return pg.evaluate("""async () => (await (await fetch('/api.php?action=load',{cache:'no-store'})).json()).data""")


with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)
    ctx = br.new_context(viewport={'width': 1440, 'height': 950})
    pg = ctx.new_page()
    errs, cerrs = [], []
    pg.on('pageerror', lambda e: errs.append(str(e)[:180]))
    pg.on('console', lambda m: cerrs.append(m.text[:150]) if m.type == 'error' else None)
    pg.clock.install(time=datetime(2026, 10, 25, 10, 0, 0))
    pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
    pg.wait_for_timeout(500)
    pg.click('[data-act="cloud-login"]')
    pg.wait_for_timeout(400)
    pg.fill('input[name="email"]', 'test@sl00.top')
    pg.fill('input[name="password"]', 'test@sl00.top')
    pg.click('form.modal-card button[type="submit"]')
    pg.wait_for_timeout(2600)

    print('[D1] 按需用药行内记录')
    nav(pg, 'meds')
    info = pg.evaluate("""() => {
        const rows=[...document.querySelectorAll('.med-row')];
        const prn=rows.filter(r=>/按需服用/.test(r.textContent));
        return {
            rows: rows.length,
            prnRows: prn.length,
            addBtns: document.querySelectorAll('[data-act="med-prn"]').length,
            undoBtns: document.querySelectorAll('[data-act="med-prn-undo"]').length,
            dates: [...new Set([...document.querySelectorAll('[data-act="med-prn"]')].map(b=>b.dataset.date))],
            labels: [...document.querySelectorAll('.med-prn-add')].map(b=>b.textContent.trim())
        };
    }""")
    chk('用药页按需行出现「＋ 记一次」按钮（%d 个）' % info['addBtns'],
        info['addBtns'] == 2 and info['labels'] == ['＋ 记一次', '＋ 记一次'], json.dumps(info, ensure_ascii=False))
    chk('按钮绑定的是页面展示的那一天', info['dates'] == ['2026-10-25'], json.dumps(info['dates']))
    chk('点之前没有撤销按钮', info['undoBtns'] == 0, '')

    # 指定药，避免按 DOM 顺序点到另一条按需药
    pg.evaluate("""() => { const b=document.querySelector('[data-act="med-prn"][data-id="m_prn1"]'); if(b) b.click(); }""")
    pg.wait_for_timeout(1500)
    d1 = doses(pg)
    keys = [k for k in (d1['doses'].get('2026-10-25', {}).get('m_prn1') or {}) if k.startswith('prn_')]
    after = pg.evaluate("""() => ({
        undo: document.querySelectorAll('[data-act="med-prn-undo"]').length,
        cnt: [...document.querySelectorAll('.med-row-prn-cnt')].map(e=>e.textContent.replace(/\\s+/g,' ').trim())
    })""")
    chk('点击后写入一条按需剂量（prn_ 键 %d 个）' % len(keys), len(keys) == 1, json.dumps(d1['doses'].get('2026-10-25', {}), ensure_ascii=False)[:120])
    chk('行内计数变为「今日已记 1 次」', any('1 次' in c for c in after['cnt']), json.dumps(after['cnt'], ensure_ascii=False))
    chk('出现「撤销」按钮', after['undo'] == 1, '')

    pg.evaluate("""() => { const b=document.querySelector('[data-act="med-prn-undo"][data-id="m_prn1"]'); if(b) b.click(); }""")
    pg.wait_for_timeout(1500)
    d2 = doses(pg)
    left = [k for k in (d2['doses'].get('2026-10-25', {}).get('m_prn1') or {}) if k.startswith('prn_')]
    chk('撤销后剂量被移除（剩 %d 个）' % len(left), len(left) == 0, '')

    chk('暂停中的按需药不显示记录按钮',
        pg.evaluate("""() => {
            const rows=[...document.querySelectorAll('.med-row')];
            const r=rows.find(x=>/暂停止痛片/.test(x.textContent));
            return !r || r.querySelectorAll('[data-act="med-prn"]').length === 0;
        }"""), '')

    print('\n[D1-b] 排期药 ≥2 种时仍然可达（原先的断点）')
    reach = pg.evaluate("""() => ({
        scheduled: document.querySelectorAll('.med-slot').length,
        addBtns: document.querySelectorAll('[data-act="med-prn"]').length
    })""")
    chk('当前排期药远多于 2 种，按需按钮仍存在', reach['scheduled'] > 2 and reach['addBtns'] == 2, json.dumps(reach))

    print('\n[D1-c] 槽位写入的是页面显示的那一天，不是 selectedDate')
    nav(pg, 'today')
    pg.evaluate("""() => { const b=document.querySelector('[data-act="date-shift"][data-delta="-1"]'); if(b) b.click(); }""")
    pg.wait_for_timeout(900)
    nav(pg, 'meds')
    pg.evaluate("""() => { const b=document.querySelector('[data-act="med-take"][data-slot="09:00"]'); if(b) b.click(); }""")
    pg.wait_for_timeout(1600)
    d3 = doses(pg)
    today09 = (d3['doses'].get('2026-10-25', {}) or {}).get('m_short1', {})
    prev09 = (d3['doses'].get('2026-10-24', {}) or {}).get('m_short1', {})
    chk('回退到 10-24 后点用药页槽位，仍写入 2026-10-25',
        bool(today09.get('09:00')) and not bool(prev09.get('09:00')),
        'today=%s prev=%s' % (json.dumps(today09), json.dumps(prev09)))
    nav(pg, 'today')
    pg.evaluate("""() => { const b=document.querySelector('[data-act="date-today"]'); if(b) b.click(); }""")
    pg.wait_for_timeout(700)

    print('\n[D3] 疗程过期提示')
    nav(pg, 'meds')
    pg.evaluate("""() => {
        const rows=[...document.querySelectorAll('.med-row')];
        const r=rows.find(x=>/过期头孢/.test(x.textContent));
        if(r) r.querySelector('[data-act="med-edit"]').click();
    }""")
    pg.wait_for_timeout(900)
    warn = pg.evaluate("""() => {
        const w=document.querySelector('#med-form .hint-warn');
        return { has: !!w, text: w ? w.textContent.replace(/\\s+/g,' ').trim() : '',
                 status: (document.querySelector('#med-form [name="status"]')||{}).value };
    }""")
    chk('过期短期疗程的编辑弹窗给出提示', warn['has'] and '2026-10-20' in warn['text'], warn['text'][:70])
    chk('提示里说明了「已停用」的原因并给出两条出路',
        '已停用' in warn['text'] and '结束日期' in warn['text'], '')
    chk('状态字段仍如实显示 active（不改数据）', warn['status'] == 'active', warn['status'])
    pg.keyboard.press('Escape')
    pg.wait_for_timeout(400)

    pg.evaluate("""() => {
        const rows=[...document.querySelectorAll('.med-row')];
        const r=rows.find(x=>/头孢克肟/.test(x.textContent));
        if(r) r.querySelector('[data-act="med-edit"]').click();
    }""")
    pg.wait_for_timeout(900)
    chk('未过期的短期疗程不显示该提示',
        pg.evaluate("() => document.querySelectorAll('#med-form .hint-warn').length") == 0, '')
    pg.keyboard.press('Escape')
    pg.wait_for_timeout(400)

    print('\n[D2] 触摸端热区')
    pg.close()
    mctx = br.new_context(viewport={'width': 390, 'height': 844}, has_touch=True, is_mobile=True)
    mp = mctx.new_page()
    mctx.add_init_script("try{localStorage.setItem('lifeboard.email','x')}catch(e){}")
    mp.on('pageerror', lambda e: errs.append(str(e)[:180]))
    mp.clock.install(time=datetime(2026, 10, 25, 10, 0, 0))
    mp.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
    mp.wait_for_timeout(500)
    mp.click('[data-act="cloud-login"]')
    mp.wait_for_timeout(400)
    mp.fill('input[name="email"]', 'test@sl00.top')
    mp.fill('input[name="password"]', 'test@sl00.top')
    mp.click('form.modal-card button[type="submit"]')
    mp.wait_for_timeout(3000)

    size = """s => { const e=document.querySelector(s); if(!e) return null;
        const r=e.getBoundingClientRect(); const cs=getComputedStyle(e,'::after');
        return {w: Math.round(Math.max(r.width, parseFloat(cs.width)||0)),
                h: Math.round(Math.max(r.height, parseFloat(cs.height)||0))}; }"""
    for sel, label in (('.remind-go', '「去看看」'), ('.remind-x', '「今天不再提醒」')):
        r = mp.evaluate(size, sel)
        chk('%s 有效热区 ≥40px（%s）' % (label, ('%dx%d' % (r['w'], r['h'])) if r else '元素不存在'),
            bool(r) and r['w'] >= 40 and r['h'] >= 40, json.dumps(r))

    mp.evaluate("""() => { const b=document.querySelector('[data-act="date-shift"][data-delta="-1"]'); if(b) b.click(); }""")
    mp.wait_for_timeout(900)
    bf = mp.evaluate(size, '.backfill-today')
    chk('补记条「回今天」有效热区 ≥40px（%s）' % ((' %dx%d' % (bf['w'], bf['h'])) if bf else '元素不存在'),
        bool(bf) and bf['w'] >= 40 and bf['h'] >= 40, json.dumps(bf))

    pg2 = mctx.new_page()
    pg2.clock.install(time=datetime(2026, 10, 25, 10, 0, 0))
    pg2.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
    pg2.wait_for_timeout(2800)
    pg2.evaluate("""() => { const l=[...document.querySelectorAll('[data-nav="meds"]')]; const e=l.find(x=>x.offsetParent!==null)||l[0]; if(e) e.click(); }""")
    pg2.wait_for_timeout(1000)
    pr = pg2.evaluate(size, '.med-prn-add')
    chk('按需「＋ 记一次」在移动端热区 ≥40px（%s）' % ((' %dx%d' % (pr['w'], pr['h'])) if pr else '元素不存在'),
        bool(pr) and pr['w'] >= 40 and pr['h'] >= 40, json.dumps(pr))

    print('\n[桌面端不受影响]')
    # pg 已经关掉，另开一个桌面 context 复核
    dctx = br.new_context(viewport={'width': 1440, 'height': 950})
    dp = dctx.new_page()
    dp.clock.install(time=datetime(2026, 10, 25, 10, 0, 0))
    dp.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
    dp.wait_for_timeout(500)
    dp.click('[data-act="cloud-login"]')
    dp.wait_for_timeout(400)
    dp.fill('input[name="email"]', 'test@sl00.top')
    dp.fill('input[name="password"]', 'test@sl00.top')
    dp.click('form.modal-card button[type="submit"]')
    dp.wait_for_timeout(2800)
    desk = dp.evaluate("""() => {
        const e=document.querySelector('.remind-go'); if(!e) return 'none';
        const cs=getComputedStyle(e,'::after');
        return {w: parseFloat(cs.width)||0, h: parseFloat(cs.height)||0, body: Math.round(e.getBoundingClientRect().height)};
    }""")
    dctx.close()
    chk('桌面端 ::after 覆盖层为 0（不改变视觉）', desk != 'none' and desk['w'] == 0 and desk['h'] == 0, json.dumps(desk))

    print('\n[错误汇总]')
    chk('全程无 JS 异常', len(errs) == 0, json.dumps(errs[:3], ensure_ascii=False))
    chk('全程无 console error', len(cerrs) == 0, json.dumps(cerrs[:3], ensure_ascii=False))

    print('\n===== 修复验证：%d 通过 / %d 失败 =====' % (PASS, FAIL))
    for n, d in FAILS:
        print('  - %s | %s' % (n, d))
    mctx.close()
    ctx.close()
    br.close()
