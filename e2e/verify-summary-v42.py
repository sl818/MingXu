# -*- coding: utf-8 -*-
"""月度健康小结的验证：内容 / 明细 / 体重 / 打印样式。

打印部分用 emulate_media(media='print') 真的切到打印媒体再取值，
否则只能验证 HTML 里有那几条 CSS，验证不了它到底生效没有。
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
head = io.open(os.path.join(ROOT, 'e2e', 'verify-batch4.py'), encoding='utf-8').read()
head = head.split('with sync_playwright() as p:')[0]
sys.argv = [sys.argv[0]]
exec(head)

# 备用药要给一条服用记录，否则「按需服用 N 次」那行不出现
board['data']['doses'].setdefault(TODAY, {})['m_prn1'] = {
    'prn_1': {'at': TODAY + 'T14:00:00+08:00', 'amount': 1}
}

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


def card(pg):
    el = pg.locator('.summary-card')
    return el.inner_text() if el.count() else ''


def rows_of(pg, idx):
    return pg.evaluate("""(i) => {
        const ts = document.querySelectorAll('.summary-card .sum-table');
        const t = ts[i];
        if (!t) return [];
        return [...t.querySelectorAll('tr')].slice(1).map(r =>
            [...r.children].map(c => c.textContent.trim()));
    }""", idx)


with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)
    ctx = br.new_context(viewport={'width': 1440, 'height': 950})
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)[:180]))
    pg.clock.install(time=datetime(2026, 10, 25, 21, 45, 0))
    pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
    pg.wait_for_timeout(600)
    pg.click('[data-act="cloud-login"]')
    pg.wait_for_timeout(400)
    pg.fill('input[name="email"]', 'test@example.com')
    pg.fill('input[name="password"]', 'test@example.com')
    pg.click('form.modal-card button[type="submit"]')
    pg.wait_for_timeout(2600)

    print('\n[1] 入口')
    nav(pg, 'stats')
    pg.wait_for_timeout(900)
    btn = pg.locator('[data-act="month-summary"]')
    chk('本月回顾里有「生成月度小结」按钮', btn.count() == 1)
    chk('按钮文字正确', btn.count() == 1 and '月度小结' in btn.inner_text(),
        btn.inner_text() if btn.count() else '')

    print('\n[2] 打开小结')
    btn.click()
    pg.wait_for_timeout(700)
    chk('弹出小结卡片', pg.locator('.summary-card').count() == 1)
    txt = card(pg)
    chk('标题是「月度健康小结」', '月度健康小结' in txt)
    chk('标明年月', '2026 年 10 月' in txt, txt[:40])
    chk('标明时间范围与天数', '2026-10-01 至 2026-10-25' in txt and '25 天' in txt)

    print('\n[3] 用药依从')
    chk('有「用药依从」小节', '用药依从' in txt)
    chk('给出百分比', '1%' in txt or '%' in txt)
    chk('给出应服/已服次数', '应服' in txt and '已服' in txt)
    med = rows_of(pg, 0)
    chk('按药明细 5 行（4 种定时药 + 1 种备用药）', len(med) == 5, str([r[0] for r in med]))
    names = [r[0] for r in med]
    chk('阿莫西林在内', '阿莫西林' in names, str(names))
    chk('头孢克肟在内', '头孢克肟' in names)
    chk('备用药单独一行', '止痛片' in names, str(names))
    prn_row = next((r for r in med if r[0] == '止痛片'), None)
    chk('备用药标为按需', prn_row and '按需' in prn_row[2], str(prn_row))
    chk('备用药只有次数没有依从率', prn_row and prn_row[4] == '1 次', str(prn_row))
    amox = next((r for r in med if r[0] == '阿莫西林'), None)
    chk('定时药有应服次数', amox and amox[3].isdigit() and int(amox[3]) > 0, str(amox))
    chk('定时药有时间列', amox and '08:00' in amox[2], str(amox))

    print('\n[4] 体重')
    chk('有体重小节', '体重' in txt)
    chk('显示变化量 -1.6 kg', '-1.6' in txt, [l for l in txt.split('\n') if 'kg' in l][:3])
    chk('显示起止日期与数值',
        '2026-10-01' in txt and '70 kg' in txt and '68.4 kg' in txt,
        [l for l in txt.split('\n') if 'kg' in l][:3])

    print('\n[5] 习惯与记录情况')
    chk('有习惯小节', '习惯完成' in txt)
    hab = rows_of(pg, 1)
    chk('习惯明细有内容', len(hab) > 0, str(hab[:2]))
    chk('习惯行有完成率', hab and '%' in hab[0][2], str(hab[:1]))
    chk('有记录情况小节', '记录情况' in txt)
    chk('给出有记录天数与达标天数', '有记录' in txt and '达标' in txt)
    chk('有生成时间和免责说明', '生成于' in txt and '不构成医疗建议' in txt)

    print('\n[6] 打印样式（切到 print 媒体真的取一次值）')
    pg.emulate_media(media='print')
    pg.wait_for_timeout(300)
    m = pg.evaluate("""() => {
        const others = [...document.body.children].filter(e => e.id !== 'modal-root');
        const card = document.querySelector('.summary-card');
        const btn = document.querySelector('[data-act="print-summary"]');
        const btnRow = document.querySelector('.btn-row.no-print');
        const bd = document.querySelector('.modal-backdrop');
        return {
          othersHidden: others.length > 0 && others.every(e => getComputedStyle(e).display === 'none'),
          othersCount: others.length,
          cardW: card ? Math.round(card.getBoundingClientRect().width) : 0,
          cardBg: card ? getComputedStyle(card).backgroundColor : '',
          cardShadow: card ? getComputedStyle(card).boxShadow : '',
          cardColor: card ? getComputedStyle(card).color : '',
          /* no-print 挂在按钮的父容器上，按钮自身仍是 inline-flex，
             所以要看 offsetParent：祖先 display:none 时它为 null */
          btnHidden: btn ? (btn.offsetParent === null) : true,
          btnRowDisplay: btnRow ? getComputedStyle(btnRow).display : '',
          backdropPos: bd ? getComputedStyle(bd).position : ''
        };
    }""")
    chk('body 下除模态根节点外全部隐藏', m['othersHidden'], str(m))
    chk('小结卡片仍有宽度（不是被一起隐藏了）', m['cardW'] > 300, str(m['cardW']))
    chk('卡片背景是白色', m['cardBg'] in ('rgb(255, 255, 255)', 'rgba(0, 0, 0, 0)'), m['cardBg'])
    chk('卡片没有阴影', m['cardShadow'] == 'none', m['cardShadow'])
    chk('打印时文字是深色', m['cardColor'].startswith('rgb(17, 17, 17)'), m['cardColor'])
    chk('打印按钮不可见（no-print 父容器）', m['btnHidden'], str(m))
    chk('按钮容器 display 是 none', m['btnRowDisplay'] == 'none', m['btnRowDisplay'])
    chk('遮罩改成 static（否则分页会只打一页）', m['backdropPos'] == 'static', m['backdropPos'])
    pg.emulate_media(media='screen')
    pg.wait_for_timeout(300)

    print('\n[7] 手机上')
    pg.set_viewport_size({'width': 390, 'height': 844})
    pg.wait_for_timeout(600)
    mm = pg.evaluate("""() => {
        const card = document.querySelector('.summary-card');
        const t = document.querySelector('.summary-card .sum-table');
        return {
          ovf: document.documentElement.scrollWidth > document.documentElement.clientWidth,
          cardW: card ? Math.round(card.getBoundingClientRect().width) : 0,
          tableW: t ? Math.round(t.getBoundingClientRect().width) : 0,
          winW: window.innerWidth
        };
    }""")
    chk('没有横向溢出', not mm['ovf'], str(mm))
    chk('表格没有超出屏幕', mm['tableW'] <= mm['winW'], str(mm))
    pg.screenshot(path=os.path.join(ROOT, 'e2e', 'shots', 'v42-summary-mobile.png'))

    print('\n[8] 控制台')
    chk('没有 JS 异常', not errs, '; '.join(errs[:2]))

    br.close()

print('\n----------------------------')
print('通过 %d 项，失败 %d 项' % (PASS, len(FAILS)))
for name, detail in FAILS:
    print('  失败：%s  << %s' % (name, detail))
sys.exit(0 if not FAILS else 1)
