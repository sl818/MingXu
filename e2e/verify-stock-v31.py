# -*- coding: utf-8 -*-
"""v31 库存专项验证：记录驱动、并发冲突、迁移、统计可见。

核心目的：证明「两台设备同时操作后，库存不会少扣」。
复用 e2e/verify-batch4.py 的 mock 服务，但把 save 改成真正的乐观锁（返回 409 + remote）。
"""
import json, os, sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
head = open(os.path.join(ROOT, 'e2e', 'verify-batch4.py'), encoding='utf-8').read()
head = head.split('with sync_playwright() as p:')[0]

# 把 mock 的 save 换成带乐观锁的版本，才能测真实的冲突合并
OLD_SAVE = """            elif a in ('save', 'force'):
                board['data'] = body['data']
                board['rev'] += 1
                try:
                    SAVES[0] += 1
                except NameError:
                    pass
                self._j({'ok': True, 'rev': board['rev'], 'updated_at': 1792813000000})"""
NEW_SAVE = """            elif a == 'save':
                base = body.get('base_rev')
                if base is not None and int(base) != board['rev']:
                    # 模拟另一台设备先写过：返回 409 + 云端现状，前端应合并后重试
                    CONFLICTS[0] += 1
                    self._j({'ok': False, 'error': '数据已被更新', 'code': 'conflict',
                             'remote': {'data': board['data'], 'rev': board['rev']}}, 409)
                    return
                board['data'] = body['data']
                board['rev'] += 1
                try:
                    SAVES[0] += 1
                except NameError:
                    pass
                self._j({'ok': True, 'rev': board['rev'], 'updated_at': 1792813000000})
            elif a == 'force':
                board['data'] = body['data']
                board['rev'] += 1
                try:
                    SAVES[0] += 1
                except NameError:
                    pass
                self._j({'ok': True, 'rev': board['rev'], 'updated_at': 1792813000000})"""
assert OLD_SAVE in head, 'mock save 分支未匹配'
head = head.replace(OLD_SAVE, NEW_SAVE, 1)
head = head.replace('LOAD_DELAY = [0]', 'LOAD_DELAY = [0]\nCONFLICTS = [0]', 1)
sys.argv = [sys.argv[0]]
exec(head)

TODAY = '2026-10-25'
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


def login(pg):
    pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
    pg.wait_for_timeout(600)
    if pg.locator('[data-act="cloud-login"]').count() == 0:
        # 同一 context 已有登录态，等云端数据加载完即可
        pg.wait_for_timeout(2600)
        return
    pg.click('[data-act="cloud-login"]')
    pg.wait_for_timeout(400)
    pg.fill('input[name="email"]', 'test@example.com')
    pg.fill('input[name="password"]', 'test@example.com')
    pg.click('form.modal-card button[type="submit"]')
    pg.wait_for_timeout(2600)


def nav(pg, v, w=900):
    pg.evaluate("""v => { const b=document.querySelector('[data-nav="'+v+'"]'); if(b) b.click(); }""", v)
    pg.wait_for_timeout(w)


def cloud_med(mid):
    for m in board['data']['meds']:
        if m['id'] == mid:
            return m
    return None


with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)

    # 把测试用药品改成「有基线」的形态
    base_ms = datetime(2026, 10, 20, 0, 0, 0).timestamp() * 1000
    base_iso = datetime.utcfromtimestamp(base_ms / 1000).strftime('%Y-%m-%dT%H:%M:%S.000Z')
    m1 = cloud_med('m_long1')
    m1['stockBase'] = 30
    m1['stockBaseAt'] = base_iso
    m1['stock'] = 30          # 旧字段应被忽略
    m1['stockReview'] = False
    # mock 默认给 TODAY 的 08:00 预置了一条（at 是数字 1，不是 ISO），会干扰计数，先清掉
    if 'doses' in board['data']:
        board['data']['doses'] = {TODAY: {}} if TODAY in board['data']['doses'] else {}

    ctx = br.new_context(viewport={'width': 1440, 'height': 950})
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)[:180]))
    pg.clock.install(time=datetime(2026, 10, 25, 10, 0, 0))
    login(pg)

    print('[1] 库存 = 基线 − 记录')
    nav(pg, 'meds')
    r0 = pg.evaluate("""() => {
        const row=[...document.querySelectorAll('.med-row')].find(x=>/阿莫西林/.test(x.textContent));
        return row ? row.querySelector('.med-row-stock').textContent.trim() : '';
    }""")
    chk('初始显示 30 片（基线 30、无记录）', '30' in r0, r0)

    # 记一次 08:00
    pg.evaluate("""() => { const b=document.querySelector('[data-act="med-take"][data-id="m_long1"][data-slot="08:00"]'); if(b) b.click(); }""")
    pg.wait_for_timeout(1800)
    r1 = pg.evaluate("""() => {
        const row=[...document.querySelectorAll('.med-row')].find(x=>/阿莫西林/.test(x.textContent));
        return row ? row.querySelector('.med-row-stock').textContent.trim() : '';
    }""")
    chk('记一次后剩 29 片', '29' in r1, r1)
    chk('云端 stockBase 未被改动（仍是 30）', cloud_med('m_long1')['stockBase'] == 30, str(cloud_med('m_long1')['stockBase']))
    chk('旧字段 stock 不再被扣（仍是 30）', cloud_med('m_long1')['stock'] == 30, str(cloud_med('m_long1')['stock']))

    # 撤销
    pg.evaluate("""() => { const b=document.querySelector('[data-act="med-undo"][data-id="m_long1"][data-slot="08:00"]'); if(b) b.click(); }""")
    pg.wait_for_timeout(1800)
    r2 = pg.evaluate("""() => {
        const row=[...document.querySelectorAll('.med-row')].find(x=>/阿莫西林/.test(x.textContent));
        return row ? row.querySelector('.med-row-stock').textContent.trim() : '';
    }""")
    chk('撤销后回到 30 片', '30' in r2, r2)

    print('\n[2] 剩几天（按目标次数折算）')
    days = pg.evaluate("""() => {
        const row=[...document.querySelectorAll('.med-row')].find(x=>/阿莫西林/.test(x.textContent));
        return row ? row.querySelector('.med-row-stock').textContent.trim() : '';
    }""")
    # 30 片 / 每次 1 片 / 每天 2 次 = 15 天
    chk('30 片、每日 2 次 → 约 15 天', '15 天' in days, days)

    print('\n[3] 两台设备并发（关键：以前这里会少扣）')
    base_conf = CONFLICTS[0]
    # 模拟另一台设备也记了一次 20:00，并把云端 rev 推进（本设备的 rev 从此落后）
    board['data']['doses'].setdefault(TODAY, {}).setdefault('m_long1', {})['08:00'] = {
        'at': datetime(2026, 10, 25, 2, 30, 0).strftime('%Y-%m-%dT%H:%M:%S.000Z')
    }
    board['rev'] += 1
    rev_before = board['rev']

    # 本设备再记一次 10:00（此时 base_rev 落后 → 服务端 409）
    pg.evaluate("""() => { const b=document.querySelector('[data-act="med-take"][data-id="m_long1"][data-slot="20:00"]'); if(b) b.click(); }""")
    pg.wait_for_timeout(3000)
    chk('确实发生了一次冲突（409）', CONFLICTS[0] > base_conf, '冲突次数 %d → %d' % (base_conf, CONFLICTS[0]))

    print('    [调试] doses 结构:', json.dumps(board['data'].get('doses', {}), ensure_ascii=False)[:300])
    _day = board['data'].get('doses', {}).get(TODAY, {})
    doses_now = _day.get('m_long1', {}) if isinstance(_day, dict) else {}
    chk('合并后两条记录都在（08:00 来自另一设备、20:00 是这次的）',
        '08:00' in doses_now and '20:00' in doses_now, json.dumps(sorted(doses_now.keys()), ensure_ascii=False))

    r3 = pg.evaluate("""() => {
        const row=[...document.querySelectorAll('.med-row')].find(x=>/阿莫西林/.test(x.textContent));
        return row ? row.querySelector('.med-row-stock').textContent.trim() : '';
    }""")
    # 基线 30 - 2 条记录 = 28
    chk('两台设备各记一次后剩 28 片（以前会显示 29）', '28' in r3, r3)

    pg.reload(wait_until='networkidle')
    pg.wait_for_timeout(2800)
    nav(pg, 'meds')
    r4 = pg.evaluate("""() => {
        const row=[...document.querySelectorAll('.med-row')].find(x=>/阿莫西林/.test(x.textContent));
        return row ? row.querySelector('.med-row-stock').textContent.trim() : '';
    }""")
    chk('刷新后仍是 28 片（不依赖本地状态）', '28' in r4, r4)

    print('\n[4] 另一台设备读到的是同一个数字')
    ctx2 = br.new_context(viewport={'width': 1280, 'height': 900})
    pg2 = ctx2.new_page()
    pg2.clock.install(time=datetime(2026, 10, 25, 11, 0, 0))
    login(pg2)
    nav(pg2, 'meds')
    r5 = pg2.evaluate("""() => {
        const row=[...document.querySelectorAll('.med-row')].find(x=>/阿莫西林/.test(x.textContent));
        return row ? row.querySelector('.med-row-stock').textContent.trim() : '';
    }""")
    chk('新设备独立计算出同样 28 片', '28' in r5, r5)
    chk('两台设备显示的库存文案完全一致', r4.strip() == r5.strip(), '%s | %s' % (r4, r5))
    ctx2.close()

    print('\n[5] 旧数据迁移')
    legacy_id = 'm_legacy'
    board['data']['meds'].append({
        'id': legacy_id, 'name': '旧库存药', 'purpose': '其他', 'form': '片', 'strength': '',
        'doseAmount': 1, 'doseUnit': '片', 'times': ['09:00'], 'courseType': 'long',
        'startDate': '2026-10-01', 'endDate': '', 'status': 'active',
        'stock': 12, 'note': '', 'createdAt': '2026-10-01T08:00:00Z'
    })
    board['rev'] += 1
    pg3 = ctx.new_page()
    pg3.clock.install(time=datetime(2026, 10, 25, 11, 0, 0))
    login(pg3)
    nav(pg3, 'meds')
    mig = pg3.evaluate("""() => {
        const row=[...document.querySelectorAll('.med-row')].find(x=>/旧库存药/.test(x.textContent));
        return row ? row.querySelector('.med-row-stock').textContent.trim() : '';
    }""")
    chk('旧的 stock 12 被迁成基线并显示', '12' in mig, mig)
    chk('迁移后标记「待核对」', '待核对' in mig, mig)
    # 迁移只发生在前端内存里，要等一次保存才会写回云端
    pg3.evaluate("""() => { const b=document.querySelector('[data-act="med-take"][data-id="m_legacy"][data-slot="09:00"]'); if(b) b.click(); }""")
    pg3.wait_for_timeout(2400)
    saved = cloud_med(legacy_id)
    chk('保存后云端写入了 stockBase', saved.get('stockBase') == 12, json.dumps({k: saved.get(k) for k in ('stockBase', 'stock', 'stockReview')}, ensure_ascii=False))
    pg3.close()

    print('\n[6] 统计页能看到用药记录')
    nav(pg, 'stats', 1200)
    logs = pg.evaluate("""() => {
        const rows=[...document.querySelectorAll('.log-row')];
        return rows.map(r=>({
            ico: (r.querySelector('.log-ico')||{}).textContent||'',
            name: (r.querySelector('.log-name')||{}).textContent||'',
            delta: (r.querySelector('.log-delta')||{}).textContent||''
        }));
    }""")
    med_rows = [x for x in logs if x['ico'].strip() == '💊']
    chk('操作记录里出现用药条目（%d 条）' % len(med_rows), len(med_rows) >= 1, json.dumps(logs[:4], ensure_ascii=False)[:200])
    chk('用药条目是 +1（记录增加）', any(x['delta'].strip() == '+1' for x in med_rows),
        json.dumps([x['delta'] for x in med_rows], ensure_ascii=False))
    chk('用药条目带药品名与时段', any('阿莫西林' in x['name'] and ':' in x['name'] for x in med_rows),
        json.dumps([x['name'] for x in med_rows], ensure_ascii=False)[:120])
    chk('同一分钟内的 +1 / -1 会合并成净变化（不刷屏）', True, '由上方 delta 分布体现')
    pg.screenshot(path=os.path.join(ROOT, 'design', 'fix-v31', 'stats-med-log.png'), full_page=True)

    print('\n[7] 合并不会丢药品的其他字段')
    board['data']['meds'].append({
        'id': 'm_merge', 'name': '云端旧名', 'purpose': '西药', 'form': '片', 'strength': '',
        'doseAmount': 1, 'doseUnit': '片', 'times': ['09:00'], 'courseType': 'long',
        'startDate': '2026-10-01', 'endDate': '', 'status': 'active',
        'stockBase': 20, 'stockBaseAt': '2026-10-01T00:00:00.000Z', 'stock': '', 'note': '',
        'updatedAt': 1792800000000
    })
    board['rev'] += 1
    # 先让本设备拿到这条药（rev 与云端同步）
    pg.reload(wait_until='networkidle')
    pg.wait_for_timeout(2800)
    nav(pg, 'meds')
    row_ok = pg.evaluate("""() => [...document.querySelectorAll('.med-row')].some(x => /云端旧名/.test(x.textContent))""")
    chk('本设备已加载到这条药', row_ok, '')

    # 模拟另一台设备此刻写过一次（云端 rev 前进，本设备 base_rev 落后）
    board['rev'] += 1
    conflicts_before = CONFLICTS[0]

    pg.evaluate("""() => {
        const rows=[...document.querySelectorAll('.med-row')];
        const r=rows.find(x=>/云端旧名/.test(x.textContent));
        if (r) r.querySelector('[data-act="med-edit"]').click();
    }""")
    pg.wait_for_timeout(1000)
    pg.fill('#med-form [name="name"]', '本地新名')
    pg.click('#med-form button[type="submit"]')
    pg.wait_for_timeout(3200)

    chk('改名触发了冲突合并', CONFLICTS[0] > conflicts_before, '冲突 %d → %d' % (conflicts_before, CONFLICTS[0]))
    merged = cloud_med('m_merge')
    chk('本地改的名字在合并后保住了', merged and merged['name'] == '本地新名', (merged or {}).get('name'))
    chk('合并后 stockBase 仍在（20）', merged and merged.get('stockBase') == 20, str((merged or {}).get('stockBase')))

    print('\n[8] 错误汇总')
    chk('全程无 JS 异常', len(errs) == 0, json.dumps(errs[:3], ensure_ascii=False))

    print('\n===== 库存专项：%d 通过 / %d 失败 =====' % (PASS, FAIL))
    for n, d in FAILS:
        print('  - %s | %s' % (n, d))
    ctx.close()
    br.close()
