# -*- coding: utf-8 -*-
"""库存盘点入口的界面验证：打开 / 填写 / 保存 / 基线更新 / 边界。

mock 里的药没有 stockBase（真实数据由 migrateStock 补），这里先补上，
否则盘点入口会正确地提示「没有可盘点的药」，测不到东西。
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
head = io.open(os.path.join(ROOT, 'e2e', 'verify-batch4.py'), encoding='utf-8').read()
head = head.split('with sync_playwright() as p:')[0]
sys.argv = [sys.argv[0]]
exec(head)

# 给三个药补库存基线：阿莫西林 30、维生素D 30（标为待核对）、头孢 18
for m in board['data']['meds']:
    if m['id'] in ('m_long1', 'm_long2', 'm_short1'):
        m['stockBase'] = 30 if m['id'] != 'm_short1' else 18
        m['stockBaseAt'] = '2026-10-24T09:00:00'
    if m['id'] == 'm_long2':
        m['stockReview'] = True

PASS = 0
FAILS = []


def chk(name, ok, detail=''):
    global PASS
    if ok:
        PASS += 1
        print('  \u2713 %s' % name)
    else:
        FAILS.append((name, detail))
        print('  \u2717 %s  << %s' % (name, detail))


def modal_text(pg):
    el = pg.locator('.modal-card')
    return el.inner_text() if el.count() else ''


def rows(pg):
    return pg.evaluate("""() => [...document.querySelectorAll('.stock-row')].map(r => {
        const name = r.querySelector('.stock-name');
        const now = r.querySelector('.stock-now');
        const inp = r.querySelector('[data-stock-for]');
        return {id: inp ? inp.dataset.stockFor : '',
                name: name ? name.textContent.trim() : '',
                now: now ? now.textContent.trim() : '',
                ph: inp ? inp.getAttribute('placeholder') : ''};
    })""")


def toast_text(pg):
    el = pg.locator('#toast.show')
    return el.inner_text() if el.count() else ''


with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)
    ctx = br.new_context(viewport={'width': 1440, 'height': 950})
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)[:180]))
    pg.clock.install(time=datetime(2026, 10, 25, 10, 0, 0))
    pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
    pg.wait_for_timeout(600)
    pg.click('[data-act="cloud-login"]')
    pg.wait_for_timeout(400)
    pg.fill('input[name="email"]', 'test@example.com')
    pg.fill('input[name="password"]', 'test@example.com')
    pg.click('form.modal-card button[type="submit"]')
    pg.wait_for_timeout(2600)

    print('\n[1] 入口')
    nav(pg, 'meds')
    pg.wait_for_timeout(700)
    btn = pg.locator('[data-act="stock-check"]')
    chk('用药页有「盘点库存」按钮', btn.count() == 1)
    chk('按钮文字正确', btn.count() == 1 and '盘点库存' in btn.inner_text(),
        btn.inner_text() if btn.count() else '')
    chk('「添加用药」仍在', pg.locator('[data-act="med-new"]').count() == 1)
    chk('保存前页面显示阿莫西林剩 30 片', '剩 30 片' in pg.locator('#main').inner_text())

    print('\n[2] 打开盘点框')
    btn.click()
    pg.wait_for_timeout(600)
    chk('弹出模态框', pg.locator('.modal-card').count() == 1)
    chk('标题是「盘点库存」', '盘点库存' in modal_text(pg))
    rs = rows(pg)
    chk('列出 3 个有基线的药', len(rs) == 3, str([r['name'] for r in rs]))
    chk('阿莫西林在内', any(r['name'] == '阿莫西林' for r in rs))
    chk('头孢克肟在内', any(r['name'] == '头孢克肟' for r in rs))
    chk('备用药（无基线）不出现',
        not any(r['name'] in ('止痛片', '感冒灵') for r in rs))
    amox = next((r for r in rs if r['name'] == '阿莫西林'), None)
    chk('显示当前推算余量', amox and '剩 30 片' in amox['now'], str(amox))
    chk('输入框占位符是当前余量', amox and amox['ph'] == '30', str(amox))
    cef = next((r for r in rs if r['name'] == '头孢克肟'), None)
    chk('不同药显示各自的余量', cef and '剩 18 片' in cef['now'], str(cef))
    vit = next((r for r in rs if r['name'] == '维生素D'), None)
    chk('待核对的药有标记', vit and '待核对' in vit['now'], str(vit))

    print('\n[3] 全部留空时不生效')
    pg.locator('[data-act="stock-check-save"]').click()
    pg.wait_for_timeout(500)
    chk('提示没填数字', '没有填任何数字' in toast_text(pg), toast_text(pg))
    chk('模态框没有关闭', pg.locator('.modal-card').count() == 1)

    print('\n[4] 填一个药并保存')
    pg.fill('[data-stock-for="m_long1"]', '12')
    pg.locator('[data-act="stock-check-save"]').click()
    pg.wait_for_timeout(900)
    chk('模态框关闭', pg.locator('.modal-card').count() == 0)
    chk('提示更新了 1 种药', '已更新 1 种药' in toast_text(pg), toast_text(pg))
    page_txt = pg.locator('#main').inner_text()
    chk('页面上的余量变成 12', '剩 12 片' in page_txt,
        [l for l in page_txt.split('\n') if '剩' in l][:3])
    chk('没填的药保持 30', '剩 30 片' in page_txt)

    print('\n[5] 再开一次：基线已更新')
    pg.locator('[data-act="stock-check"]').click()
    pg.wait_for_timeout(600)
    rs = rows(pg)
    amox = next((r for r in rs if r['name'] == '阿莫西林'), None)
    chk('阿莫西林现在显示剩 12', amox and '剩 12 片' in amox['now'], str(amox))
    chk('显示今天的登记日期', amox and '10-25 登记' in amox['now'], str(amox))
    vit = next((r for r in rs if r['name'] == '维生素D'), None)
    chk('待核对标记还在（这个药没盘）', vit and '待核对' in vit['now'], str(vit))

    print('\n[6] 一次盘两个 + 清掉待核对')
    pg.fill('[data-stock-for="m_long2"]', '100')
    pg.fill('[data-stock-for="m_short1"]', '0')
    pg.locator('[data-act="stock-check-save"]').click()
    pg.wait_for_timeout(900)
    chk('提示更新了 2 种药', '已更新 2 种药' in toast_text(pg), toast_text(pg))
    page_txt = pg.locator('#main').inner_text()
    chk('维生素D 变成 100', '剩 100 片' in page_txt,
        [l for l in page_txt.split('\n') if '剩' in l][:4])
    chk('填 0 也能保存', '剩 0 片' in page_txt,
        [l for l in page_txt.split('\n') if '剩' in l][:4])
    pg.locator('[data-act="stock-check"]').click()
    pg.wait_for_timeout(600)
    rs = rows(pg)
    vit = next((r for r in rs if r['name'] == '维生素D'), None)
    chk('盘过之后「待核对」消失', vit and '待核对' not in vit['now'], str(vit))

    print('\n[7] 负数被忽略')
    pg.fill('[data-stock-for="m_long1"]', '-5')
    pg.locator('[data-act="stock-check-save"]').click()
    pg.wait_for_timeout(700)
    chk('负数不算改动', '没有填任何数字' in toast_text(pg), toast_text(pg))
    chk('模态框仍开着', pg.locator('.modal-card').count() == 1)
    pg.locator('[data-act="close-modal"]').click()
    pg.wait_for_timeout(400)
    chk('取消后关闭', pg.locator('.modal-card').count() == 0)
    pg.locator('[data-act="stock-check"]').click()
    pg.wait_for_timeout(500)
    rs = rows(pg)
    amox = next((r for r in rs if r['name'] == '阿莫西林'), None)
    chk('负数没有写进去（仍是 12）', amox and '剩 12 片' in amox['now'], str(amox))

    print('\n[8] 手机端排版')
    pg.set_viewport_size({'width': 390, 'height': 844})
    pg.wait_for_timeout(700)
    m = pg.evaluate("""() => {
        const card = document.querySelector('.modal-card');
        const inp = document.querySelector('[data-stock-for]');
        const r = inp ? inp.getBoundingClientRect() : null;
        return {
          ovf: document.documentElement.scrollWidth > document.documentElement.clientWidth,
          cardW: card ? Math.round(card.getBoundingClientRect().width) : 0,
          inR: r ? Math.round(r.right) : -1,
          inW: r ? Math.round(r.width) : 0,
          winW: window.innerWidth
        };
    }""")
    chk('没有横向溢出', not m['ovf'], str(m))
    chk('输入框在可视区域内', 0 < m['inR'] <= m['winW'], str(m))
    chk('输入框宽度合理（60–120px）', 60 <= m['inW'] <= 120, str(m))
    chk('药名没有被挤成竖排',
        pg.evaluate("""() => {
            const n = document.querySelector('.stock-name');
            return n ? n.getBoundingClientRect().height < 30 : true;
        }"""))
    pg.screenshot(path=os.path.join(ROOT, 'e2e', 'shots', 'v40-stock-mobile.png'))

    print('\n[9] 控制台')
    chk('没有 JS 异常', not errs, '; '.join(errs[:2]))

    br.close()

print('\n----------------------------')
print('通过 %d 项，失败 %d 项' % (PASS, len(FAILS)))
for name, detail in FAILS:
    print('  失败：%s  << %s' % (name, detail))
sys.exit(0 if not FAILS else 1)
