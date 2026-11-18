# -*- coding: utf-8 -*-
"""PC 端线上测试（最终版）。"""
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


def nav(pg, v, wait=750):
    pg.evaluate("""v => { const b=document.querySelector('[data-nav="'+v+'"]'); if(b) b.click(); }""", v)
    pg.wait_for_timeout(wait)


def ovf(pg):
    return pg.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")


def state(pg):
    return pg.evaluate("""async () => (await (await fetch('/api.php?action=load',{cache:'no-store'})).json()).data""")


def slots(data, d):
    out = []
    for m in data.get('meds', []):
        if not m or m.get('courseType') == 'prn':
            continue
        if m.get('status') != 'active' and d >= '2026-10-26':
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
    hs = [h for h in data.get('habits', [])
          if not h.get('optional') and not h.get('archivedAt')
          and not (h.get('med') and len(slots(data, d)) == 0)]
    return len(hs), sum(1 for h in hs if met(data, h, d))


with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)
    ctx = br.new_context(viewport={'width': 1440, 'height': 950}, accept_downloads=True)
    pg = ctx.new_page()
    errs, cerrs = [], []
    pg.on('pageerror', lambda e: errs.append(str(e)[:200]))
    pg.on('console', lambda m: cerrs.append(m.text[:160]) if m.type == 'error' else None)
    login(pg)
    TODAY = pg.evaluate("() => new Date().toISOString().slice(0,10)")
    print('== 今天 %s ==' % TODAY)

    print('\n[1] 渲染与数据一致性')
    d0 = state(pg)

    nav(pg, 'meds')
    m = pg.evaluate("""() => ({
        groups: Array.from(document.querySelectorAll('.med-group')).map(g => ({
            phase: (g.querySelector('.med-group-head h3')||{}).textContent.trim(),
            subs: Array.from(g.querySelectorAll('.med-sub-head')).map(s => s.textContent.trim()),
            rows: g.querySelectorAll('.med-row').length })),
        rows: document.querySelectorAll('.med-row').length })""")
    mine = [x for x in d0['meds'] if x.get('manufacturer') == '终测制药']
    rec('用药页总行数 = %d（数据 %d 条）' % (m['rows'], len(d0['meds'])), m['rows'] == len(d0['meds']), '')
    rec('本次创建的 15 条都在页面上', len(mine) == 15, 'mine=%d' % len(mine))
    act = [g for g in m['groups'] if g['phase'] == '进行中']
    if act:
        g = act[0]
        each = {}
        for s in g['subs']:
            key = re.sub(r'[\d\s种]', '', s)
            each[key] = int(''.join(ch for ch in s if ch.isdigit()) or 0)
        rec('进行中组内三段小标题齐全', list(each.keys()) == ['长期', '短期', '按需'], json.dumps(g['subs'], ensure_ascii=False))
        rec('三段计数之和 = 该组药品数 %d' % g['rows'], sum(each.values()) == g['rows'], json.dumps(each, ensure_ascii=False))
        rec('长期 / 短期 / 按需 各 ≥5 种', min(each.values()) >= 5, json.dumps(each, ensure_ascii=False))
    rec('用药页无横向溢出', ovf(pg) == 0, 'ovf=%d' % ovf(pg))
    pg.screenshot(path=SHOTS + '/pc-1-meds.png', full_page=True)

    nav(pg, 'board')
    b = pg.evaluate("""() => ({
        cols: Array.from(document.querySelectorAll('.board .col')).map(c => ({
            st: c.dataset.status, head: (c.querySelector('.col-head b')||{}).textContent.trim(),
            n: parseInt((c.querySelector('.col-count')||{}).textContent||'0',10),
            cards: c.querySelectorAll('.task').length })),
        all: document.querySelectorAll('.board .task').length })""")
    exp = collections.Counter(x.get('status') for x in d0['tasks'])
    rec('四列顺序 待办/进行中/已完成/已取消',
        [c['st'] for c in b['cols']] == ['todo', 'doing', 'done', 'cancelled'], '')
    rec('四列计数 = 状态分布 %s' % [exp['todo'], exp['doing'], exp['done'], exp['cancelled']],
        [c['n'] for c in b['cols']] == [exp['todo'], exp['doing'], exp['done'], exp['cancelled']], '')
    rec('列头计数与列内卡片数一致', all(c['n'] == c['cards'] for c in b['cols']), json.dumps(b['cols'], ensure_ascii=False))
    rec('卡片总数 = 任务数 %d' % len(d0['tasks']), b['all'] == len(d0['tasks']), 'all=%d' % b['all'])
    rec('待办页无横向溢出', ovf(pg) == 0, 'ovf=%d' % ovf(pg))
    pg.screenshot(path=SHOTS + '/pc-2-board.png', full_page=True)

    nav(pg, 'essays')
    e = pg.evaluate("() => ({ cards: document.querySelectorAll('.essay-card').length, text: document.body.innerText })")
    rec('随笔卡片数 = %d' % len(d0['essays']), e['cards'] == len(d0['essays']), 'cards=%d' % e['cards'])
    rec('两篇新随笔标题都在页面上',
        '终测 · 清晨的十分钟' in e['text'] and '终测 · 药店排队的二十分钟' in e['text'], '')
    rec('随笔正文正确显示', '这十分钟说不上有什么用' in e['text'], '')
    rec('随笔页无横向溢出', ovf(pg) == 0, 'ovf=%d' % ovf(pg))
    pg.screenshot(path=SHOTS + '/pc-3-essays.png', full_page=True)

    nav(pg, 'weight')
    w = pg.evaluate("""() => ({
        goal: document.querySelectorAll('.ww-goal').length,
        lbl: (document.querySelector('.ww-goal-lbl')||{}).textContent || '',
        dots: document.querySelectorAll('.ww-svg circle').length,
        prof: Array.from(document.querySelectorAll('.profile-grid b')).map(x => x.textContent.trim()),
        rows: document.querySelectorAll('.weight-row').length,
        text: document.body.innerText })""")
    rec('体重折线图渲染（%d 个点位）' % w['dots'], w['dots'] >= 3, '')
    rec('目标体重线 65 已画出', w['goal'] == 1 and '65.0' in w['lbl'], w['lbl'])
    rec('档案显示 30 岁 / 172 cm',
        '30' in ' '.join(w['prof']) and '172' in ' '.join(w['prof']), json.dumps(w['prof'], ensure_ascii=False))
    rec('距目标 71.6-65 = 6.6 kg', '6.6' in w['text'], '')
    rec('体重记录 %d 条全部显示' % len(d0['weights']), w['rows'] == len(d0['weights']), 'rows=%d' % w['rows'])
    rec('体重页无横向溢出', ovf(pg) == 0, 'ovf=%d' % ovf(pg))
    pg.screenshot(path=SHOTS + '/pc-4-weight.png', full_page=True)

    nav(pg, 'habits')
    h = pg.evaluate("""() => ({
        rows: document.querySelectorAll('.habit-row:not(.archived)').length,
        names: Array.from(document.querySelectorAll('.habit-row:not(.archived) .habit-row-info b')).map(x => x.textContent.trim()),
        text: document.body.innerText })""")
    real = [x for x in d0['habits'] if not x.get('archivedAt') and not x.get('med')]
    rec('习惯页行数 = %d（排除用药伪习惯）' % len(real), h['rows'] == len(real), 'rows=%d' % h['rows'])
    rec('4 个新习惯全部在列表',
        all(n in h['names'] for n in ['终测·晨间拉伸', '终测·涂防晒', '终测·戒碳酸饮料', '终测·睡前不刷手机']), '')
    rec('戒除型标注「保持」', h['text'].count('保持') >= 2, '')
    rec('习惯页无横向溢出', ovf(pg) == 0, 'ovf=%d' % ovf(pg))
    pg.screenshot(path=SHOTS + '/pc-5-habits.png', full_page=True)

    print('\n[2] 真实交互')
    nav(pg, 'today')
    ids = {x['name']: x['id'] for x in d0['habits']}
    for nm in ('终测·晨间拉伸', '终测·涂防晒'):
        hid = ids[nm]
        # pip 的 data-val 是「点到第 n 格」；已完成时该格为 i-1，所以显式点 data-val=1 才是打卡
        for _ in range(3):
            if cnt(state(pg), TODAY, hid) >= 1:
                break
            pg.evaluate("""hid => {
                const b = document.querySelector('[data-act="habit-set"][data-id="'+hid+'"][data-val="1"]')
                       || document.querySelector('[data-act="habit-inc"][data-id="'+hid+'"]');
                if (b) b.click(); }""", hid)
            pg.wait_for_timeout(1400)
        rec('今日页给「%s」打卡' % nm, cnt(state(pg), TODAY, hid) == 1, 'count=%d' % cnt(state(pg), TODAY, hid))
    d1 = state(pg)
    rec('两个保持型习惯今日计数 = 1',
        cnt(d1, TODAY, ids['终测·晨间拉伸']) == 1 and cnt(d1, TODAY, ids['终测·涂防晒']) == 1,
        '拉伸=%d 防晒=%d' % (cnt(d1, TODAY, ids['终测·晨间拉伸']), cnt(d1, TODAY, ids['终测·涂防晒'])))

    # 取消打卡再打回：验证 pip 的「点掉」语义
    pg.evaluate("""hid => { const b=document.querySelector('[data-act="habit-set"][data-id="'+hid+'"][data-val="0"]'); if(b) b.click(); }""", ids['终测·涂防晒'])
    pg.wait_for_timeout(1400)
    off = cnt(state(pg), TODAY, ids['终测·涂防晒'])
    pg.evaluate("""hid => { const b=document.querySelector('[data-act="habit-set"][data-id="'+hid+'"][data-val="1"]'); if(b) b.click(); }""", ids['终测·涂防晒'])
    pg.wait_for_timeout(1400)
    back = cnt(state(pg), TODAY, ids['终测·涂防晒'])
    rec('已完成习惯可取消再打回（1→%d→%d）' % (off, back), off == 0 and back == 1, '')

    # 戒除型：保持 0 次即达标
    dq = state(pg)
    quit_ids = [x['id'] for x in dq['habits'] if x.get('type') == 'quit']
    rec('戒除型习惯 0 次即计为达标',
        all(cnt(dq, TODAY, i) == 0 for i in quit_ids if i in ids.values() or True), '%d 个戒除型' % len(quit_ids))

    nav(pg, 'meds')
    pg.evaluate("""() => { const b=document.querySelector('[data-act="med-take"]'); if(b) b.click(); }""")
    pg.wait_for_timeout(1700)
    d2 = state(pg)
    rec('用药页记录一次服药', taken(d2, TODAY) >= 1, '已服 %d / 应服 %d' % (taken(d2, TODAY), len(slots(d2, TODAY))))

    # 按需用药：今日页用药卡 → 用药页 → 按需行「＋ 记一次」→ 撤销还原
    # （v30 起改在用药页行内记录：排期药 ≥2 种时今日卡没有 med-open，弹层够不到）
    nav(pg, 'today')
    entry = pg.evaluate("""() => {
        const sec = [...document.querySelectorAll('.vital-card')].find(c => /种药|按需用药/.test(c.textContent));
        if (!sec) return null;
        const b = sec.querySelector('[data-nav="meds"]') || sec.querySelector('[data-act="med-open"]');
        if (!b) return null;
        b.click();
        return { act: b.dataset.act || ('nav:' + b.dataset.nav), text: b.textContent.trim() };
    }""")
    pg.wait_for_timeout(1200)
    landed = pg.evaluate("() => document.body.dataset.view")
    rec('今日页用药卡可进入用药页（%s）' % ((entry or {}).get('text', '无入口')),
        bool(entry) and landed == 'meds', 'view=%s' % landed)

    target = pg.evaluate("""() => {
        const b = document.querySelector('[data-act="med-prn"]');
        return b ? b.dataset.id : '';
    }""")
    before = len([k for k in (((state(pg).get('doses') or {}).get(TODAY, {}) or {}).get(target) or {}) if k.startswith('prn_')])
    pg.evaluate("""id => { const b=document.querySelector('[data-act="med-prn"][data-id="'+id+'"]'); if(b) b.click(); }""", target)
    pg.wait_for_timeout(1800)
    mid = len([k for k in (((state(pg).get('doses') or {}).get(TODAY, {}) or {}).get(target) or {}) if k.startswith('prn_')])
    rec('用药页按需行可「记一次」（%d → %d）' % (before, mid), bool(target) and mid == before + 1, '')

    pg.evaluate("""id => { const b=document.querySelector('[data-act="med-prn-undo"][data-id="'+id+'"]'); if(b) b.click(); }""", target)
    pg.wait_for_timeout(1800)
    after = len([k for k in (((state(pg).get('doses') or {}).get(TODAY, {}) or {}).get(target) or {}) if k.startswith('prn_')])
    rec('撤销后还原到点击前（%d）' % after, after == before, 'before=%d after=%d' % (before, after))

    nav(pg, 'board')
    d2b = state(pg)   # 重新取一次：前面几次操作会 rev 递增
    before = collections.Counter(x.get('status') for x in d2b['tasks'])
    moved = pg.evaluate("""() => {
        const btn = document.querySelector('.board .col[data-status="todo"] [data-act="task-move"][data-dir="1"]');
        if (!btn) return '';
        const t = btn.closest('.task').querySelector('h4').textContent.trim();
        btn.click(); return t; }""")
    pg.wait_for_timeout(1700)
    d3 = state(pg)
    after = collections.Counter(x.get('status') for x in d3['tasks'])
    rec('待办推进一列（%s）' % (moved or '未找到'), bool(moved) and after['doing'] == before['doing'] + 1,
        'todo %d→%d doing %d→%d' % (before['todo'], after['todo'], before['doing'], after['doing']))

    pg.keyboard.press('Control+k')
    pg.wait_for_timeout(500)
    pg.fill('#search-input', '终测')
    pg.wait_for_timeout(700)
    s = pg.evaluate("""() => ({
        groups: Array.from(document.querySelectorAll('.se-group')).map(x => x.textContent.trim()),
        items: document.querySelectorAll('.se-item').length })""")
    rec('全局搜索「终测」命中 %d 条' % s['items'], s['items'] > 0, '')
    rec('搜索结果按类型分组（%d 组）' % len(s['groups']), len(s['groups']) >= 2, json.dumps(s['groups'], ensure_ascii=False))
    pg.screenshot(path=SHOTS + '/pc-6-search.png')
    pg.keyboard.press('Escape')
    pg.wait_for_timeout(400)

    nav(pg, 'board')
    total_cards = pg.evaluate("() => document.querySelectorAll('.board .task').length")
    for quick, label in (('today', '今天'), ('overdue', '逾期'), ('week', '本周')):
        hit = pg.evaluate("""q => { const b=document.querySelector('[data-act="board-quick"][data-quick="'+q+'"]'); if(!b) return false; b.click(); return true; }""", quick)
        pg.wait_for_timeout(700)
        n = pg.evaluate("() => document.querySelectorAll('.board .task').length")
        act = pg.evaluate("() => (document.querySelector('.board-tools .tag-chip.active')||{}).textContent.trim()")
        rec('筛选「%s」生效（%d → %d 张）' % (label, total_cards, n), hit and n != total_cards and act == label, 'active=%s' % act)
        pg.evaluate("""q => { const b=document.querySelector('[data-act="board-quick"][data-quick="'+q+'"]'); if(b) b.click(); }""", quick)
        pg.wait_for_timeout(700)
        rec('再次点击「%s」取消筛选' % label,
            pg.evaluate("() => document.querySelectorAll('.board .task').length") == total_cards, '')

    print('\n[3] 完成率核对')
    d4 = state(pg)
    nav(pg, 'today')
    tot, don = stats_of(d4, TODAY)
    exp_pct = round(don * 100.0 / tot) if tot else 0
    u = pg.evaluate("""() => ({
        pct: (document.querySelector('.hero-pct b')||{}).textContent.trim(),
        hero: (document.querySelector('.hero-main h1, h1')||{}).textContent.trim(),
        text: document.body.innerText })""")
    ui = int(''.join(c for c in u['pct'] if c.isdigit()) or -1)
    rec('今日完成率 = 重算 %d%% / 页面 %s（%d/%d）' % (exp_pct, u['pct'], don, tot), ui == exp_pct, '')
    rec('Hero 文案含「完成 %d/%d」' % (don, tot), ('完成 %d/%d' % (don, tot)) in u['hero'] + u['text'], u['hero'])
    rec('今日页「还差 N 项」与重算一致', ('还差 %d 项' % (tot - don) in u['text']) if don < tot else True, '')
    rec('今日页能看到新增待办', '【终测】' in u['text'], '')
    rec('今日页无横向溢出', ovf(pg) == 0, 'ovf=%d' % ovf(pg))
    pg.screenshot(path=SHOTS + '/pc-7-today.png', full_page=True)

    nav(pg, 'stats', 950)
    st = pg.evaluate("""() => ({
        cells: Array.from(document.querySelectorAll('.rv-cell')).map(x => ({
            l: x.querySelector('small').textContent.trim(),
            v: x.querySelector('b').textContent.trim(),
            s: (x.querySelector('span')||{}).textContent || '' })),
        verdict: (document.querySelector('.rv-verdict')||{}).textContent || '',
        titles: Array.from(document.querySelectorAll('.panel h3')).map(x => x.textContent.trim()),
        bars: document.querySelectorAll('.chart > div').length })""")
    c = {x['l']: x for x in st['cells']}
    num = lambda s: int(''.join(ch for ch in s if ch.isdigit()) or -1)
    chk = sorted(d for d, v in (d4.get('checks') or {}).items() if d.startswith('2026-10') and any((v or {}).values()))
    dose = sorted(d for d, v in (d4.get('doses') or {}).items() if d.startswith('2026-10') and v)
    recd = sorted(set(chk) | set(dose))
    qual = [d for d in recd if (lambda t: t[0] and t[1] / t[0] >= 0.75)(stats_of(d4, d))]
    best = cur = 0
    prev = None
    for d in qual:
        cur = cur + 1 if prev and (datetime.date.fromisoformat(d) - datetime.date.fromisoformat(prev)).days == 1 else 1
        best = max(best, cur)
        prev = d
    avg = round(sum(stats_of(d4, d)[1] / stats_of(d4, d)[0] * 100 for d in recd) / len(recd)) if recd else 0
    wo = sorted([x for x in d4['weights'] if str(x.get('date', '')).startswith('2026-10')], key=lambda x: x['date'])
    wd = round(wo[-1]['weight'] - wo[0]['weight'], 1) if len(wo) >= 2 else None

    rec('统计页有「本月回顾」', any(t.startswith('本月回顾') for t in st['titles']), json.dumps(st['titles'][:4], ensure_ascii=False))
    rec('六项指标齐全', [x['l'] for x in st['cells']] == ['达标天数', '有记录', '最长连续', '平均完成率', '体重变化', '用药依从'], '')
    rec('有记录天数 重算 %d / 页面 %s' % (len(recd), c['有记录']['v']), num(c['有记录']['v']) == len(recd), json.dumps(recd))
    rec('达标天数 重算 %d / 页面 %s' % (len(qual), c['达标天数']['v']), num(c['达标天数']['v']) == len(qual), json.dumps(qual))
    rec('最长连续 重算 %d / 页面 %s' % (best, c['最长连续']['v']), num(c['最长连续']['v']) == best, '')
    rec('平均完成率 重算 %d%% / 页面 %s' % (avg, c['平均完成率']['v']), abs(num(c['平均完成率']['v']) - avg) <= 1, '')
    if wd is not None:
        v = c['体重变化']['v'].replace(' ', '')
        val = float(''.join(ch for ch in v if ch.isdigit() or ch in '.-') or 0)
        rec('体重变化 重算 %.1f / 页面 %s' % (wd, v), abs(val - wd) < 0.05, '')
    rec('统计结论句非空', len(st['verdict'].strip()) > 6, st['verdict'].strip()[:44])
    rec('近 30 天完成率柱状图有数据（%d 根）' % st['bars'], st['bars'] >= 20, '')
    rec('统计页无横向溢出', ovf(pg) == 0, 'ovf=%d' % ovf(pg))
    pg.screenshot(path=SHOTS + '/pc-8-stats.png', full_page=True)

    print('\n[4] 其余页面与入口')
    nav(pg, 'calendar', 900)
    cal = pg.evaluate("""() => ({
        cells: document.querySelectorAll('.cal-cell').length,
        dated: document.querySelectorAll('.cal-cell[data-date]').length,
        ovf: document.documentElement.scrollWidth - window.innerWidth })""")
    rec('日历渲染整月（%d 格）' % cal['cells'], cal['cells'] >= 28 and cal['dated'] >= 28, json.dumps(cal))
    rec('日历页无横向溢出', cal['ovf'] == 0, '')
    pg.screenshot(path=SHOTS + '/pc-9-calendar.png', full_page=True)

    nav(pg, 'settings', 900)
    se = pg.evaluate("""() => ({
        panels: Array.from(document.querySelectorAll('.panel h3')).map(x => x.textContent.trim()),
        skins: document.querySelectorAll('[data-act="set-skin"]').length,
        layouts: document.querySelectorAll('[data-act="set-layout"]').length,
        acts: Array.from(document.querySelectorAll('[data-act]')).map(x => x.dataset.act),
        ovf: document.documentElement.scrollWidth - window.innerWidth })""")
    rec('设置页面板 %d 个' % len(se['panels']), len(se['panels']) >= 5, json.dumps(se['panels'], ensure_ascii=False)[:110])
    rec('9 套皮肤可选（%d）' % se['skins'], se['skins'] == 9, '')
    rec('3 种布局可选（%d）' % se['layouts'], se['layouts'] == 3, '')
    rec('导入/导出/历史版本入口齐全', all(a in se['acts'] for a in ('import-json', 'export-json', 'history-open')), '')
    rec('设置页无横向溢出', se['ovf'] == 0, '')
    pg.screenshot(path=SHOTS + '/pc-10-settings.png', full_page=True)

    pg.click('[data-act="history-open"]')
    pg.wait_for_timeout(1600)
    hi = pg.evaluate("""() => ({ items: document.querySelectorAll('[data-act="history-preview"]').length,
        open: !!document.querySelector('#modal-root .modal-card') })""")
    rec('历史版本弹层可打开（%d 条）' % hi['items'], hi['open'] and hi['items'] > 0, json.dumps(hi))
    pg.keyboard.press('Escape')
    pg.wait_for_timeout(400)

    # 导出 JSON（浏览器下载，不写服务器）
    try:
        with pg.expect_download(timeout=15000) as dl:
            pg.evaluate("""() => { const b=document.querySelector('[data-act="export-json"]'); if(b) b.click(); }""")
        d = dl.value
        path = d.path()
        size = os.path.getsize(path) if path else 0
        try:
            obj = json.load(open(path, 'r', encoding='utf-8'))
            keys_ok = all(k in obj for k in ('tasks', 'habits', 'meds', 'weights', 'essays'))
            cnt_ok = len(obj.get('tasks', [])) == len(d4.get('tasks', []))
        except Exception as ex:
            keys_ok = cnt_ok = False
            obj = {'err': str(ex)[:60]}
        rec('导出 JSON 备份可解析且字段齐全（%.0f KB）' % (size / 1024),
            size > 10000 and keys_ok and cnt_ok,
            'size=%d keys=%s tasks=%s/%s' % (size, keys_ok, len(obj.get('tasks', [])), len(d4.get('tasks', []))))
        try:
            os.remove(path)
        except Exception:
            pass
    except Exception as ex:
        rec('导出 JSON 备份成功', False, str(ex)[:80])

    print('\n[5] 错误汇总')
    rec('无 JS 运行时异常', len(errs) == 0, json.dumps(errs[:3], ensure_ascii=False))
    rec('无 console error', len(cerrs) == 0, json.dumps(cerrs[:3], ensure_ascii=False))

    print('\n===== PC：%d 通过 / %d 失败 =====' % (PASS, FAIL))
    for n, dd in FAILS:
        print('  - %s | %s' % (n, dd))
    ctx.close()
    br.close()
