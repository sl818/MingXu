# -*- coding: utf-8 -*-
"""戒烟包区间验证：同天两包不再共用一个计数、抽完封顶、库存、未归包、末支软确认。"""
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

DAY = datetime(2026, 11, 1, 0, 0, 0)
TS0 = int(DAY.timestamp())


def pack(pid, hour=0, minute=0, size=20, price=15, name='普皖'):
    d = DAY + timedelta(hours=hour, minutes=minute)
    return {'id': pid, 'at': int(d.timestamp()), 'name': name, 'price': price, 'size': size}


def smokes(n, start_hour=8, step_min=30):
    """从 08:00 起每 30 分钟一支，返回 n 条「点一根」事件"""
    out = []
    for i in range(n):
        d = DAY + timedelta(hours=start_hour, minutes=i * step_min)
        out.append({'id': 'c%d' % i, 't': int(d.timestamp()), 'k': 's', 'h': 'h_smoke', 'g': '', 's': 0})
    return out


def load(pg, packs, cravings):
    board['data']['habits'] = [SMOKE]
    board['data']['packs'] = packs
    board['data']['cravings'] = cravings
    pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
    pg.wait_for_timeout(500)
    if pg.locator('[data-act="cloud-login"]').count():
        pg.click('[data-act="cloud-login"]')
        pg.wait_for_timeout(400)
        pg.fill('input[name="email"]', 'test@example.com')
        pg.fill('input[name="password"]', 'test@example.com')
        pg.click('form.modal-card button[type="submit"]')
        pg.wait_for_timeout(2600)
    pg.evaluate("() => { const b=document.querySelector('[data-nav=\"quit\"]'); if(b) b.click(); }")
    pg.wait_for_timeout(600)


def rows(pg):
    return pg.evaluate("""() => [...document.querySelectorAll('.qpack')].map(el => ({
        txt: (el.querySelector('.qpack-main') || {}).textContent || '',
        st: (el.querySelector('.qpack-st') || {}).textContent || '',
        cur: el.classList.contains('cur')
    }))""")


def grid_out(pg):
    return pg.evaluate("""() => {
        const g = document.querySelector('.quit-hero .pack-grid');
        if (!g) return {cells: 0, out: 0};
        return {cells: g.querySelectorAll('.pk').length, out: g.querySelectorAll('.pk.out').length};
    }""")


def card_text(pg):
    return pg.evaluate("""() => {
        const c = document.querySelector('.quit-hero .quit-card');
        return c ? c.textContent.replace(/\\s+/g, ' ').trim() : '';
    }""")


with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)

    # ---------- 用例 1：两包同一天、共 22 支 ----------
    print('[1] 同天买两包，抽了 22 支')
    ctx = br.new_context(viewport={'width': 1512, 'height': 950})
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)[:160]))
    pg.clock.install(time=datetime(2026, 11, 1, 21, 0, 0))
    load(pg, [pack('p1'), pack('p2')], smokes(22))
    r = rows(pg)
    chk('列表两行', len(r) == 2, str(len(r)))
    chk('最新那包在上面', '普皖' in r[0]['txt'])
    # 包2 吃 2 支、在抽；包1 被吃满 20 支
    chk('第二包 2 支（没被算成 22）', '2/20' in r[0]['txt'], r[0]['txt'])
    chk('第一包 20/20 封顶', '20/20' in r[1]['txt'], r[1]['txt'])
    chk('第二包状态 = 在抽', r[0]['st'] == '在抽', r[0]['st'])
    chk('第一包状态 = 已抽完', r[1]['st'] == '已抽完', r[1]['st'])
    chk('第一包显示抽完用时', '抽了' in r[1]['txt'], r[1]['txt'])
    g = grid_out(pg)
    chk('卡面 20 格', g['cells'] == 20, str(g))
    chk('卡面只熄灭 2 格（当前这包）', g['out'] == 2, str(g))
    ct = card_text(pg)
    chk('卡面写「还剩 18 支」', '还剩 18 支' in ct, ct[:120])
    chk('没有未归包的支', '没归包' not in ct, ct[:120])

    # 末支软确认：当前这包还在抽，但上一包刚抽完 —— 提示条该说的是「上一包」
    cf = pg.locator('.pack-cf')
    chk('上一包刚抽完，出现确认条', cf.count() == 1)
    cft = cf.first.text_content() if cf.count() else ''
    chk('文案说的是「上一包」不是「这包」', '上一包' in cft, cft)
    chk('确认条时间是上一包抽完的 17:30', '17:30' in cft, cft)
    chk('无 JS 异常', not errs, str(errs))
    ctx.close()

    # ---------- 用例 2：一包抽完，20 支 ----------
    print('[2] 一包刚好抽完 20 支')
    ctx = br.new_context(viewport={'width': 1512, 'height': 950})
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)[:160]))
    pg.clock.install(time=datetime(2026, 11, 1, 21, 0, 0))
    # 08:00 买、08:00 抽第一支 —— 新表单带时分之后就是这个精度
    load(pg, [pack('p1', 8)], smokes(20))
    r = rows(pg)
    chk('显示 20/20', '20/20' in r[0]['txt'], r[0]['txt'])
    chk('状态已抽完', r[0]['st'] == '已抽完', r[0]['st'])
    # 08:00 → 17:30 是 9.5 小时
    chk('用时 9 小时 30 分', '9 小时 30 分' in r[0]['txt'], r[0]['txt'])
    g = grid_out(pg)
    chk('20 格全灭', g['out'] == 20, str(g))
    chk('出现末支确认条', pg.locator('.pack-cf').count() == 1)
    cf = pg.locator('.pack-cf').first.text_content()
    chk('确认条带日期时间', '17:30' in cf, cf)
    # 点「对」
    pg.click('[data-act="pack-cf-ok"]')
    pg.wait_for_timeout(700)
    chk('确认后提示条消失', pg.locator('.pack-cf').count() == 0)
    r2 = rows(pg)
    chk('确认后仍显示 9 小时 30 分', '9 小时 30 分' in r2[0]['txt'], r2[0]['txt'])
    chk('无 JS 异常', not errs, str(errs))
    ctx.close()

    # ---------- 用例 3：一包抽完后又抽 5 支（库存空） ----------
    print('[3] 库存空了还继续抽 5 支')
    ctx = br.new_context(viewport={'width': 1512, 'height': 950})
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)[:160]))
    pg.clock.install(time=datetime(2026, 11, 1, 23, 0, 0))
    load(pg, [pack('p1')], smokes(25))
    ct = card_text(pg)
    chk('卡面提示 5 支没归包', '另有 5 支没归包' in ct, ct[:160])
    r = rows(pg)
    chk('这一包仍是 20/20', '20/20' in r[0]['txt'], r[0]['txt'])
    g = grid_out(pg)
    chk('格子不会超过 20', g['cells'] == 20 and g['out'] == 20, str(g))
    chk('无 JS 异常', not errs, str(errs))
    ctx.close()

    # ---------- 用例 4：买三条，只抽第一条 ----------
    print('[4] 买三包只抽一包')
    ctx = br.new_context(viewport={'width': 1512, 'height': 950})
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)[:160]))
    pg.clock.install(time=datetime(2026, 11, 1, 21, 0, 0))
    load(pg, [pack('p1', 8), pack('p2', 9), pack('p3', 10)], smokes(6))
    r = rows(pg)
    st = [x['st'] for x in r]
    chk('最新在下单里排最上（p3 库存）', st[0] == '库存', str(st))
    chk('中间 p2 也是库存', st[1] == '库存', str(st))
    chk('p1 在抽 6/20', st[2] == '在抽' and '6/20' in r[2]['txt'], r[2]['txt'])
    g = grid_out(pg)
    chk('卡面熄灭 6 格', g['out'] == 6, str(g))
    chk('无 JS 异常', not errs, str(errs))
    ctx.close()

    # ---------- 用例 5：跨天抽完，时长按天 ----------
    print('[5] 跨天抽完，时长显示天 + 小时')
    ctx = br.new_context(viewport={'width': 1512, 'height': 950})
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)[:160]))
    pg.clock.install(time=datetime(2026, 11, 6, 12, 0, 0))
    evs = []
    for i in range(20):
        d = DAY + timedelta(hours=9) + timedelta(hours=6 * i)
        evs.append({'id': 'x%d' % i, 't': int(d.timestamp()), 'k': 's', 'h': 'h_smoke', 'g': '', 's': 0})
    load(pg, [pack('p1', 9)], evs)
    r = rows(pg)
    chk('20/20', '20/20' in r[0]['txt'], r[0]['txt'])
    chk('用时 4 天 18 小时', '4 天 18 小时' in r[0]['txt'], r[0]['txt'])
    chk('无 JS 异常', not errs, str(errs))
    ctx.close()

    # ---------- 用例 6：一包抽满、库存 0 → 第 21 支根本记不进去 ----------
    print('[6] 抽满后不能再记')
    ctx = br.new_context(viewport={'width': 1512, 'height': 950})
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)[:160]))
    pg.clock.install(time=datetime(2026, 11, 1, 23, 30, 0))
    load(pg, [pack('p1', 8)], smokes(20))
    btn = pg.locator('.quit-hero [data-act="crave-smoke"]')
    chk('点一根按钮置灰', btn.is_disabled())
    chk('按钮文案改成「这包抽完了」', '这包抽完了' in (btn.text_content() or ''), btn.text_content())
    # 绕过 disabled：手动放开属性再点。disabled 的 button 不派发 click，
    # 所以只能这样才测得到数据层那道闸
    pg.evaluate("() => { document.getElementById('toast').textContent = '';"
                " const b = document.querySelector('.quit-hero [data-act=\"crave-smoke\"]');"
                " b.disabled = false; b.click(); }")
    pg.wait_for_timeout(700)
    tst = (pg.locator('#toast').text_content() or '').strip()
    chk('绕过置灰也被拦', '已经抽完' in tst, tst)
    chk('仍是 20/20，没有 21', '20/20' in rows(pg)[0]['txt'], rows(pg)[0]['txt'])
    ct = card_text(pg)
    chk('没有未归包的支', '另有' not in ct, ct[:160])
    chk('卡面提示先记一笔买烟', '记一笔买烟后才能继续记' in ct, ct[:220])
    head = pg.evaluate("() => (document.querySelector('.page-head p') || {}).textContent || ''")
    chk('副标题还是 20 支', '20 支' in head, head)
    chk('无 JS 异常', not errs, str(errs))
    ctx.close()

    # ---------- 用例 7：有第二包库存时不该拦 ----------
    print('[7] 有库存照常能点')
    ctx = br.new_context(viewport={'width': 1512, 'height': 950})
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)[:160]))
    pg.clock.install(time=datetime(2026, 11, 1, 23, 30, 0))
    load(pg, [pack('p1', 8), pack('p2', 9)], smokes(20))
    btn = pg.locator('.quit-hero [data-act="crave-smoke"]')
    chk('两包时按钮可点', not btn.is_disabled())
    pg.click('.quit-hero [data-act="crave-smoke"]')
    pg.wait_for_timeout(700)
    r = rows(pg)
    chk('第一包 20/20 抽完', '20/20' in r[1]['txt'], r[1]['txt'])
    chk('第二包接上 1/20', '1/20' in r[0]['txt'], r[0]['txt'])
    chk('无 JS 异常', not errs, str(errs))
    ctx.close()

    # ---------- 用例 8：按天清空（含「忍一次」） ----------
    print('[8] 清空某天的记录')
    ctx = br.new_context(viewport={'width': 1512, 'height': 950})
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)[:160]))
    pg.on('dialog', lambda d: d.accept())
    pg.clock.install(time=datetime(2026, 11, 1, 21, 0, 0))
    evs = smokes(12) + [
        {'id': 'r%d' % i, 't': int((DAY + timedelta(hours=10, minutes=i * 40)).timestamp()),
         'k': 'r', 'h': 'h_smoke', 'g': '', 's': 0} for i in range(3)]
    load(pg, [pack('p1', 8)], evs)

    btn = pg.locator('[data-act="crave-clear"]')
    chk('页头有「清空记录」按钮', btn.count() == 1)
    chk('按钮走红色系样式', 'danger-red' in (btn.first.get_attribute('class') or ''),
        btn.first.get_attribute('class'))
    btn.first.click()
    pg.wait_for_timeout(500)
    chk('弹窗打开并列出日期', pg.locator('.cc-row').count() >= 1)
    row_txt = pg.locator('.cc-row').first.text_content() or ''
    chk('行内显示支数和忍的次数', ('12 支' in row_txt and '3 次忍' in row_txt), row_txt)

    pg.locator('[data-act="crave-clear-day"]').first.click()
    pg.wait_for_timeout(900)
    chk('清空后那天从列表消失', pg.locator('.cc-row').count() == 0)
    chk('弹窗提示还没有记录', '还没有任何记录' in (pg.locator('.modal-card').text_content() or ''))
    pg.click('[data-act="close-modal"]')
    pg.wait_for_timeout(400)
    ct = card_text(pg)
    chk('卡面不再有「今天记了」', '今天记了' not in ct, ct[:140])
    head = pg.evaluate("() => (document.querySelector('.page-head p') || {}).textContent || ''")
    chk('副标题回到「连续 N 天没抽」', '没抽' in head, head)
    chk('无 JS 异常', not errs, str(errs))
    ctx.close()
    br.close()

print()
print('===== 戒烟包区间：%d 通过 / %d 失败 =====' % (PASS, FAIL))
if FAILS:
    print('失败项：', FAILS)
