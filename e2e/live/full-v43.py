# -*- coding: utf-8 -*-
"""线上真实环境 · 全功能 E2E（v43，修正版）

走真实 UI + 真实后端。写操作都是「新建 → 云端重读验证 → 恢复/清理」。
"""
import json, os, sys, datetime
from playwright.sync_api import sync_playwright

BASE = 'https://your-domain.example/'
EMAIL = 'test@example.com'
PWD = 'test@example.com'
TODAY = datetime.date.today().isoformat()
SHOTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'shots', 'live')
os.makedirs(SHOTS, exist_ok=True)

PASS = FAIL = 0
FAILS = []


def rec(name, ok, detail=''):
    global PASS, FAIL
    if ok:
        PASS += 1
        print('  \u2713 %s' % name)
    else:
        FAIL += 1
        FAILS.append((name, detail))
        print('  \u2717 %s  << %s' % (name, detail))


def login(pg):
    pg.goto(BASE, wait_until='networkidle', timeout=60000)
    pg.wait_for_timeout(1500)
    if pg.locator('[data-act="cloud-login"]').count():
        pg.click('[data-act="cloud-login"]')
        pg.wait_for_timeout(700)
        pg.fill('input[name="email"]', EMAIL)
        pg.fill('input[name="password"]', PWD)
        pg.click('form.modal-card button[type="submit"]')
        pg.wait_for_timeout(5000)
    pg.wait_for_selector('[data-nav="today"]', state='attached', timeout=20000)


def nav(pg, v, wait=800):
    pg.evaluate("v => { const b=document.querySelector('[data-nav=\"'+v+'\"]'); if(b) b.click(); }", v)
    pg.wait_for_timeout(wait)


def ovf(pg):
    return pg.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")


def state(pg):
    return pg.evaluate(
        "async () => (await (await fetch('/api.php?action=load',{cache:'no-store'})).json()).data")


def dose_taken(data, d, mid, slot):
    day = (data.get('doses') or {}).get(d)
    if not isinstance(day, dict):
        return False
    m = day.get(mid)
    if not isinstance(m, dict):
        return False
    return bool(m.get(slot))


def check_cnt(data, d, hid):
    day = (data.get('checks') or {}).get(d)
    return int((day or {}).get(hid) or 0) if isinstance(day, dict) else 0


with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)
    ctx = br.new_context(viewport={'width': 1440, 'height': 950})
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)[:180]))
    pg.on('console', lambda m: errs.append('console:%s' % m.text[:120])
          if m.type == 'error' else None)
    pg.on('dialog', lambda d: d.accept())   # task-del 会弹 confirm
    login(pg)
    base = state(pg)
    rec('登录并加载数据', isinstance(base, dict) and 'tasks' in base)
    rec('账号里有数据', bool(base.get('tasks')))

    # ---------------------------------------------------------------- 各页渲染
    print('\n[1] 各页面渲染')
    for v in ('today', 'board', 'habits', 'meds', 'weight', 'essays', 'stats', 'settings'):
        try:
            nav(pg, v, wait=900)
            o = ovf(pg)
            rec('页面 %-8s 无横向溢出' % v, o <= 0, 'ovf=%d' % o)
        except Exception as e:
            rec('页面 %-8s 无横向溢出' % v, False, str(e)[:80])

    # ---------------------------------------------------------------- 待办 CRUD（today 页操作）
    print('\n[2] 待办：新建 → 完成 → 删除')
    try:
        nav(pg, 'board', wait=900)
        pg.click('[data-act="task-new"]')
        pg.wait_for_selector('#task-form', timeout=8000)
        pg.fill('#task-form [name="title"]', 'E2E测试任务-v43')
        pg.select_option('#task-form [name="tag"]', '其他')
        pg.fill('#task-form [name="due"]', TODAY)
        pg.click('#task-form button[type="submit"]')
        pg.wait_for_timeout(2000)
        d = state(pg)
        t = next((x for x in d['tasks'] if x['title'] == 'E2E测试任务-v43'), None)
        rec('新建任务写进云端', t is not None)
        if t:
            tid = t['id']
            # 切 today 页，点 toggle 完成
            nav(pg, 'today', wait=1000)
            pg.evaluate("id => { const b=[...document.querySelectorAll('[data-act=\"task-toggle\"]')].find(x=>x.dataset.id===id); if(b) b.click(); }", tid)
            pg.wait_for_timeout(2500)
            d = state(pg)
            t2 = next((x for x in d['tasks'] if x['id'] == tid), None)
            rec('完成任务后 status=done', t2 is not None and t2['status'] == 'done',
                t2['status'] if t2 else 'NOT FOUND')
            # 删除
            pg.evaluate("id => { const b=[...document.querySelectorAll('[data-act=\"task-edit\"]')].find(x=>x.dataset.id===id); if(b) b.click(); }", tid)
            pg.wait_for_timeout(900)
            if pg.locator('[data-act="task-del"][data-id="%s"]' % tid).count():
                pg.click('[data-act="task-del"][data-id="%s"]' % tid)
                pg.wait_for_timeout(1500)
            d = state(pg)
            rec('删除后云端不再有这条', not any(x['id'] == tid for x in d['tasks']))
    except Exception as e:
        rec('待办 CRUD 流程', False, str(e)[:120])

    # ---------------------------------------------------------------- 习惯打卡 + 撤销（target==1）
    print('\n[3] 习惯：打卡 → 撤销')
    try:
        d = state(pg)
        hab = next((h for h in d.get('habits', []) if not h.get('med') and not h.get('optional')
                    and not h.get('archivedAt') and 1 <= (h.get('target') or 1) <= 6), None)
        rec('找到可用刻度点打卡的习惯', hab is not None)
        if hab:
            hid = hab['id']
            before = check_cnt(d, TODAY, hid)
            # 习惯打卡在今日页的 vital-card 上，不在习惯管理页
            nav(pg, 'today', wait=900)
            pg.evaluate("id => { const b=[...document.querySelectorAll('[data-act=\"habit-inc\"]')].find(x=>x.dataset.id===id); if(b) b.click(); }", hid)
            pg.wait_for_timeout(2000)
            d2 = state(pg)
            after = check_cnt(d2, TODAY, hid)
            rec('打卡后计数 +1', after == before + 1, '%d -> %d' % (before, after))
            pg.evaluate("id => { const b=[...document.querySelectorAll('[data-act=\"habit-dec\"]')].find(x=>x.dataset.id===id); if(b) b.click(); }", hid)
            pg.wait_for_timeout(2000)
            d3 = state(pg)
            back = check_cnt(d3, TODAY, hid)
            rec('撤销后恢复原值', back == before, '%d -> %d' % (after, back))
    except Exception as e:
        rec('习惯打卡流程', False, str(e)[:120])

    # ---------------------------------------------------------------- 命令面板 +1/-1
    print('\n[4] 命令面板')
    try:
        d = state(pg)
        hab = next((h for h in d.get('habits', []) if not h.get('med') and not h.get('optional')
                    and not h.get('archivedAt') and (h.get('target') or 1) == 1), None)
        if hab:
            hid = hab['id']
            before = check_cnt(d, TODAY, hid)
            pg.keyboard.press('Control+k')
            pg.wait_for_timeout(500)
            pg.fill('#search-input', '+1 %s' % hab['name'].split(' ')[0])
            pg.wait_for_timeout(400)
            rec('命令被识别', pg.evaluate("() => !!document.querySelector('.se-cmd')"))
            pg.keyboard.press('Enter')
            pg.wait_for_timeout(2000)
            d2 = state(pg)
            now = check_cnt(d2, TODAY, hid)
            rec('命令 +1 生效', now == before + 1, '%d -> %d' % (before, now))
            pg.keyboard.press('Control+k')
            pg.wait_for_timeout(500)
            pg.fill('#search-input', '-1 %s' % hab['name'].split(' ')[0])
            pg.wait_for_timeout(400)
            pg.keyboard.press('Enter')
            pg.wait_for_timeout(2000)
            d3 = state(pg)
            rec('命令 -1 撤销', check_cnt(d3, TODAY, hid) == before)
    except Exception as e:
        rec('命令面板流程', False, str(e)[:120])

    # ---------------------------------------------------------------- 用药记录 + 撤销
    print('\n[5] 用药：记录 → 撤销')
    try:
        d = state(pg)
        med = next((m for m in d.get('meds', []) if m.get('courseType') != 'prn'
                    and m.get('status') == 'active' and m.get('times')), None)
        rec('找到定时药', med is not None)
        if med:
            mid = med['id']
            slot = sorted(med['times'])[0]
            nav(pg, 'meds', wait=900)
            had = dose_taken(d, TODAY, mid, slot)
            if had:
                rec('该时段已记录，跳过写入', True)
            else:
                pg.evaluate("a => { const b=[...document.querySelectorAll('[data-act=\"med-take\"]')].find(x=>x.dataset.id===a[0] && x.dataset.slot===a[1]); if(b) b.click(); }", [mid, slot])
                pg.wait_for_timeout(2000)
                d6 = state(pg)
                rec('记录服药写进云端', dose_taken(d6, TODAY, mid, slot))
                pg.evaluate("a => { const b=[...document.querySelectorAll('[data-act=\"med-undo\"]')].find(x=>x.dataset.id===a[0] && x.dataset.slot===a[1]); if(b) b.click(); }", [mid, slot])
                pg.wait_for_timeout(2000)
                d7 = state(pg)
                rec('撤销后恢复', not dose_taken(d7, TODAY, mid, slot))
    except Exception as e:
        rec('用药记录流程', False, str(e)[:120])

    # ---------------------------------------------------------------- 随笔 增删
    print('\n[6] 随笔：新建 → 删除')
    try:
        nav(pg, 'essays', wait=900)
        pg.click('[data-act="essay-new"]')
        pg.wait_for_selector('#essay-form', timeout=8000)
        pg.fill('#essay-form [name="text"]', 'E2E测试随笔-v43 内容')
        pg.fill('#essay-form [name="title"]', 'E2E测试随笔')
        pg.click('#essay-form button[type="submit"]')
        pg.wait_for_timeout(2000)
        d = state(pg)
        e = next((x for x in d.get('essays', []) if x.get('title') == 'E2E测试随笔'), None)
        rec('随笔写进云端', e is not None)
        if e:
            eid = e['id']
            pg.evaluate("id => { const b=[...document.querySelectorAll('[data-act=\"essay-del\"]')].find(x=>x.dataset.id===id); if(b) b.click(); }", eid)
            pg.wait_for_timeout(1500)
            d2 = state(pg)
            rec('随笔删除生效', not any(x['id'] == eid for x in d2.get('essays', [])))
    except Exception as e:
        rec('随笔流程', False, str(e)[:120])

    # ---------------------------------------------------------------- 盘点 / 小结 / 面板
    print('\n[7] 盘点、小结、面板')
    try:
        nav(pg, 'meds', wait=900)
        pg.click('[data-act="stock-check"]')
        pg.wait_for_timeout(800)
        rec('盘点弹窗打开', pg.locator('.modal-card').count() == 1)
        pg.keyboard.press('Escape')
        pg.wait_for_timeout(400)
    except Exception as e:
        rec('盘点弹窗打开', False, str(e)[:100])
    try:
        nav(pg, 'stats', wait=900)
        rec('小结入口存在', pg.locator('[data-act="month-summary"]').count() >= 1)
        if pg.locator('[data-act="month-summary"]').count():
            pg.click('[data-act="month-summary"]')
            pg.wait_for_timeout(900)
            rec('月度小结打开', pg.locator('.summary-card').count() == 1)
            pg.keyboard.press('Escape')
            pg.wait_for_timeout(400)
    except Exception as e:
        rec('月度小结打开', False, str(e)[:100])
    try:
        nav(pg, 'settings', wait=900)
        rec('日历订阅面板在', pg.locator('.ntf-head', has_text='日历订阅').count() >= 1)
        rec('手机推送面板在', pg.locator('.ntf-head', has_text='手机推送').count() >= 1)
    except Exception as e:
        rec('设置面板', False, str(e)[:100])

    # ---------------------------------------------------------------- 皮肤 + 布局
    print('\n[8] 皮肤与布局切换')
    try:
        nav(pg, 'settings', wait=900)
        pg.evaluate("() => { const b=document.querySelector('[data-act=\"set-skin\"][data-skin=\"cyber\"]'); if(b) b.click(); }")
        pg.wait_for_timeout(800)
        rec('切 cyber 皮肤无报错', ovf(pg) <= 0)
        pg.evaluate("() => { const b=document.querySelector('[data-act=\"set-skin\"][data-skin=\"paper\"]'); if(b) b.click(); }")
        pg.wait_for_timeout(800)
        pg.evaluate("() => { const b=document.querySelector('[data-act=\"set-layout\"][data-layout=\"wide\"]'); if(b) b.click(); }")
        pg.wait_for_timeout(800)
        rec('切 wide 布局无报错', ovf(pg) <= 0)
        pg.evaluate("() => { const b=document.querySelector('[data-act=\"set-layout\"][data-layout=\"side\"]'); if(b) b.click(); }")
        pg.wait_for_timeout(800)
    except Exception as e:
        rec('皮肤布局切换', False, str(e)[:100])

    print('\n[9] 全程 JS 报错')
    rec('无 JS/console 错误', not errs, '; '.join(errs[:5]))

    br.close()

print('\n==============================================')
print('线上 E2E：%d 通过 / %d 失败' % (PASS, FAIL))
for name, detail in FAILS:
    print('  失败：%s  << %s' % (name, detail))
sys.exit(0 if FAIL == 0 else 1)
