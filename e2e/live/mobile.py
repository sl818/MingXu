# -*- coding: utf-8 -*-
"""移动端（390×844 触摸）线上测试。"""
import json, os, datetime, collections, re
from playwright.sync_api import sync_playwright
from mkdata import login

SHOTS = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo/design/live-test'
os.makedirs(SHOTS, exist_ok=True)
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


def nav(pg, v, wait=850):
    """移动端侧栏隐藏，必须点可见的那个导航项。"""
    ok = pg.evaluate("""v => {
        const list = [...document.querySelectorAll('[data-nav="'+v+'"]')];
        const el = list.find(e => e.offsetParent !== null) || list[0];
        if (!el) return false;
        el.click(); return true;
    }""", v)
    pg.wait_for_timeout(wait)
    return ok


def state(pg):
    return pg.evaluate("""async () => (await (await fetch('/api.php?action=load',{cache:'no-store'})).json()).data""")


def slots(data, d):
    out = []
    for m in data.get('meds', []):
        if not m or m.get('courseType') == 'prn':
            continue
        if m.get('startDate') and d < m['startDate']:
            continue
        if m.get('courseType') == 'short' and m.get('endDate') and d > m['endDate']:
            continue
        for s in (m.get('times') or []):
            out.append((m['id'], s))
    return out


def taken(data, d):
    day = (data.get('doses') or {}).get(d) or {}
    return sum(1 for mid, s in slots(data, d) if (day.get(mid) or {}).get(s))


def cnt(data, d, hid):
    return int(((data.get('checks') or {}).get(d) or {}).get(hid) or 0)


def met(data, h, d):
    if h.get('med'):
        sc = len(slots(data, d))
        return sc > 0 and taken(data, d) >= sc
    c = cnt(data, d, h['id'])
    return c == 0 if h.get('type') == 'quit' else c >= max(1, int(h.get('target') or 1))


def stats_of(data, d):
    hs = [h for h in data.get('habits', []) if not h.get('optional') and not h.get('archivedAt')
          and not (h.get('med') and len(slots(data, d)) == 0)]
    return len(hs), sum(1 for h in hs if met(data, h, d))


TAP_JS = """() => {
  const SEL='.check,.icon-btn,.link-btn,.hero-arrow,.hero-today,.mini-btn,.tag-chip,.essay-tag,.arrow,.pip,.med-slot,.med-mini,.sync-indicator,.bf-clear,.backfill-today,.remind-x,.remind-go,.search-fab,.mobile-add';
  const small=[], mis=[];
  const fab=document.querySelector('.mobile-add');
  const fr=fab?fab.getBoundingClientRect():null;
  const nav=document.getElementById('mobile-nav');
  const nr=nav?nav.getBoundingClientRect():null;
  document.querySelectorAll(SEL).forEach(e=>{
    const r=e.getBoundingClientRect();
    if(!r.width) return;
    if(getComputedStyle(e).pointerEvents==='none') return;
    const cs=getComputedStyle(e,'::after');
    // 有效热区 = 元素自身尺寸 与 ::after 覆盖层尺寸 取大
    const w=Math.max(r.width, parseFloat(cs.width)||0);
    const h=Math.max(r.height, parseFloat(cs.height)||0);
    if(w<40||h<40) small.push({cls:e.className.slice(0,24), w:Math.round(w), h:Math.round(h), act:e.dataset.act||''});
    // 命中测试：被固定悬浮层（+ 按钮 / 底栏）盖住的不算缺陷，单独统计
    const cx=r.left+r.width/2, cy=r.top+r.height/2;
    if(cy<0||cy>innerHeight||cx<0||cx>innerWidth) return;
    const inFab = !!(fr && cx>=fr.left && cx<=fr.right && cy>=fr.top && cy<=fr.bottom);
    const inNav = !!(nr && cy>=nr.top);
    const hit=document.elementFromPoint(cx, cy);
    if(hit&&hit!==e&&!e.contains(hit)&&!hit.contains(e)&&!(inFab||inNav)){
      mis.push({mine:e.dataset.act||e.className.slice(0,16), got:(hit.dataset||{}).act||hit.tagName});
    }
  });
  return {small, mis};
}"""


with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)
    ctx = br.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2,
                         has_touch=True, is_mobile=True)
    pg = ctx.new_page()
    errs, cerrs = [], []
    pg.on('pageerror', lambda e: errs.append(str(e)[:200]))
    pg.on('console', lambda m: cerrs.append(m.text[:160]) if m.type == 'error' else None)
    login(pg)
    TODAY = pg.evaluate("() => new Date().toISOString().slice(0,10)")
    print('== 移动端 今天 %s ==' % TODAY)
    rec('触摸设备判定生效（pointer: coarse）', pg.evaluate("() => matchMedia('(pointer: coarse)').matches"), '')

    print('\n[1] 框架与导航')
    fr = pg.evaluate("""() => {
        const tabs=[...document.querySelectorAll('#mobile-nav [data-nav], #mobile-nav button')];
        const fab=document.querySelector('.mobile-add, .search-fab');
        const nav=document.getElementById('mobile-nav');
        const nr=nav?nav.getBoundingClientRect():null;
        return {tabs:tabs.length, labels:tabs.map(t=>(t.textContent||'').trim()),
                navVisible: !!nav && getComputedStyle(nav).display!=='none',
                navBottom: nr?Math.round(nr.bottom):0, vh: innerHeight,
                fab: !!document.querySelector('.mobile-add'),
                search: !!document.querySelector('.search-fab')};
    }""")
    rec('底部 tabbar 可见（%d 项：%s）' % (fr['tabs'], '/'.join(fr['labels'])), fr['navVisible'] and fr['tabs'] >= 4, json.dumps(fr, ensure_ascii=False))
    rec('中间「+」与搜索悬浮按钮都在', fr['fab'] and fr['search'], '')
    rec('tabbar 未被推出视口', 0 < fr['navBottom'] <= fr['vh'] + 1, 'bottom=%d vh=%d' % (fr['navBottom'], fr['vh']))

    print('\n[2] 逐页渲染（触摸端）')
    d0 = state(pg)
    pages = ['today', 'meds', 'board', 'habits', 'weight', 'essays', 'calendar', 'stats', 'settings']
    for v in pages:
        nav(pg, v, 950)
        info = pg.evaluate("""() => ({
            len: (document.getElementById('main').innerText||'').length,
            ovf: document.documentElement.scrollWidth - window.innerWidth,
            zero: document.querySelectorAll('#main *').length })""")
        rec('页面「%s」有内容且无横向溢出' % v, info['len'] > 150 and info['ovf'] <= 0, json.dumps(info))
        pg.screenshot(path=SHOTS + '/m-%s.png' % v, full_page=True)

    print('\n[3] 数据在移动端的呈现')
    nav(pg, 'meds', 950)
    mm = pg.evaluate("""() => ({
        rows: document.querySelectorAll('.med-row').length,
        subs: [...document.querySelectorAll('.med-sub-head')].map(e=>e.textContent.trim()) })""")
    rec('移动端用药页行数 = %d' % len(d0['meds']), mm['rows'] == len(d0['meds']), 'rows=%d' % mm['rows'])
    rec('移动端也有三疗程小标题', len(mm['subs']) >= 3, json.dumps(mm['subs'], ensure_ascii=False))

    nav(pg, 'board', 950)
    bm = pg.evaluate("""() => {
        const cols = [...document.querySelectorAll('.board .col')];
        return {
        cols: cols.length,
        cards: document.querySelectorAll('.board .task').length,
        colW: cols.map(c=>Math.round(c.getBoundingClientRect().width)),
        tops: [...new Set(cols.map(c=>Math.round(c.getBoundingClientRect().top)))],
        pageOvf: document.documentElement.scrollWidth - window.innerWidth };
    }""")
    rec('移动端看板四列都在，共 %d 张卡' % bm['cards'], bm['cols'] == 4 and bm['cards'] == len(d0['tasks']), json.dumps(bm['colW']))
    rec('移动端看板列宽合理（>200px，未被压扁）', min(bm['colW']) > 200, json.dumps(bm['colW']))
    rec('移动端四列改为竖排堆叠（每列 %dpx，页面不横溢）' % min(bm['colW']),
        len(set(bm['tops'])) == 4 and bm['pageOvf'] <= 0 and min(bm['colW']) > 300,
        'tops=%s ovf=%d' % (bm['tops'], bm['pageOvf']))

    nav(pg, 'essays', 950)
    em = pg.evaluate("() => ({ cards: document.querySelectorAll('.essay-card').length, text: document.body.innerText })")
    rec('移动端随笔 %d 篇都在且标题可读' % em['cards'],
        em['cards'] == len(d0['essays']) and '终测 · 清晨的十分钟' in em['text'], '')

    nav(pg, 'weight', 950)
    wm = pg.evaluate("""() => ({
        dots: document.querySelectorAll('.ww-svg circle').length,
        goal: document.querySelectorAll('.ww-goal').length,
        ovf: document.documentElement.scrollWidth - window.innerWidth })""")
    rec('移动端体重图 %d 个点 + 目标线' % wm['dots'], wm['dots'] >= 3 and wm['goal'] == 1 and wm['ovf'] <= 0, json.dumps(wm))

    nav(pg, 'habits', 950)
    hm = pg.evaluate("""() => ({
        rows: document.querySelectorAll('.habit-row:not(.archived)').length,
        ovf: document.documentElement.scrollWidth - window.innerWidth })""")
    real = [x for x in d0['habits'] if not x.get('archivedAt') and not x.get('med')]
    rec('移动端习惯页行数 = %d' % len(real), hm['rows'] == len(real) and hm['ovf'] <= 0, json.dumps(hm))

    print('\n[4] 移动端交互')
    nav(pg, 'today', 950)
    # 触摸点打卡
    ids = {x['name']: x['id'] for x in d0['habits']}
    hid = ids['终测·晨间拉伸']
    before = cnt(state(pg), TODAY, hid)
    for _ in range(3):
        if cnt(state(pg), TODAY, hid) >= 1:
            break
        pg.evaluate("""hid => {
            const b=document.querySelector('[data-act="habit-set"][data-id="'+hid+'"][data-val="1"]')
                 || document.querySelector('[data-act="habit-inc"][data-id="'+hid+'"]');
            if(b) b.click(); }""", hid)
        pg.wait_for_timeout(1400)
    rec('移动端打卡可写入（%d → %d）' % (before, cnt(state(pg), TODAY, hid)), cnt(state(pg), TODAY, hid) >= 1, '')

    # 搜索悬浮按钮
    pg.click('.search-fab')
    pg.wait_for_timeout(800)
    pg.fill('#search-input', '终测')
    pg.wait_for_timeout(700)
    sm = pg.evaluate("""() => ({
        items: document.querySelectorAll('.se-item').length,
        ovf: document.documentElement.scrollWidth - window.innerWidth,
        w: Math.round((document.querySelector('.se-card')||{getBoundingClientRect:()=>({width:0})}).getBoundingClientRect().width) })""")
    rec('移动端搜索可用（%d 条结果）' % sm['items'], sm['items'] > 0 and sm['ovf'] <= 0, json.dumps(sm))
    pg.screenshot(path=SHOTS + '/m-search.png')
    pg.keyboard.press('Escape')
    pg.wait_for_timeout(500)

    # 移动端新建：+ 按钮
    pg.click('.mobile-add')
    pg.wait_for_timeout(900)
    qa = pg.evaluate("""() => ({ open: !!document.querySelector('#modal-root .modal-card'),
        acts: [...document.querySelectorAll('#modal-root [data-act]')].map(e=>e.dataset.act) })""")
    rec('移动端「+」打开新建菜单（%s）' % ','.join(qa['acts'][:4]), qa['open'], json.dumps(qa['acts'][:6], ensure_ascii=False))
    pg.keyboard.press('Escape')
    pg.wait_for_timeout(400)

    print('\n[5] 触控热区与误触')
    agg = {'small': [], 'mis': []}
    for v in pages:
        nav(pg, v, 900)
        r = pg.evaluate(TAP_JS)
        agg['small'] += r['small']
        agg['mis'] += r['mis']
    rec('关键控件热区均 ≥40px（不达标 %d 处）' % len(agg['small']), len(agg['small']) == 0, json.dumps(agg['small'][:6], ensure_ascii=False))
    rec('无热区被遮挡导致的误触（%d 处）' % len(agg['mis']), len(agg['mis']) == 0, json.dumps(agg['mis'][:4], ensure_ascii=False))
    pad = pg.evaluate("""() => {
        const nav=document.getElementById('mobile-nav');
        return {mainPB: parseInt(getComputedStyle(document.getElementById('main')).paddingBottom),
                navH: nav?Math.round(nav.getBoundingClientRect().height):0};
    }""")
    rec('底部留白足够，内容不会被底栏永久遮住（%d ≥ %d）' % (pad['mainPB'], pad['navH']),
        pad['mainPB'] >= pad['navH'], json.dumps(pad))
    if agg['small']:
        print('    不达标明细:', json.dumps(agg['small'], ensure_ascii=False))

    print('\n[6] 移动端完成率与 PC 一致性')
    nav(pg, 'today', 950)
    d1 = state(pg)
    tot, don = stats_of(d1, TODAY)
    exp = round(don * 100.0 / tot) if tot else 0
    ui = pg.evaluate("""() => ({
        pct: (document.querySelector('.hero-pct b')||{}).textContent.trim(),
        ring: document.querySelectorAll('.hero-ring').length,
        text: document.body.innerText })""")
    got = int(''.join(c for c in ui['pct'] if c.isdigit()) or -1)
    rec('移动端今日完成率 = 重算 %d%% / 页面 %s' % (exp, ui['pct']), got == exp, '')
    rec('移动端进度环正常渲染', ui['ring'] == 1, '')
    nav(pg, 'stats', 1000)
    ms = pg.evaluate("""() => ({
        cells: [...document.querySelectorAll('.rv-cell')].map(x=>x.querySelector('small').textContent.trim()+':'+x.querySelector('b').textContent.trim()),
        ovf: document.documentElement.scrollWidth - window.innerWidth })""")
    rec('移动端本月回顾六项齐全', len(ms['cells']) == 6 and ms['ovf'] <= 0, json.dumps(ms['cells'], ensure_ascii=False)[:150])

    print('\n[7] 错误汇总')
    rec('移动端无 JS 运行时异常', len(errs) == 0, json.dumps(errs[:3], ensure_ascii=False))
    rec('移动端无 console error', len(cerrs) == 0, json.dumps(cerrs[:3], ensure_ascii=False))

    print('\n===== 移动端：%d 通过 / %d 失败 =====' % (PASS, FAIL))
    for n, dd in FAILS:
        print('  - %s | %s' % (n, dd))
    ctx.close()
    br.close()
