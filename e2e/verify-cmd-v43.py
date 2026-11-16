# -*- coding: utf-8 -*-
"""命令面板（Ctrl+K）的验证：命令识别 / 执行效果 / 认不出时退回搜索。

打卡的验证不看内部变量，而是「执行后再问一次，看它报的次数变了没有」——
这样测的是用户真正能看到的链路。
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
head = io.open(os.path.join(ROOT, 'e2e', 'verify-batch4.py'), encoding='utf-8').read()
head = head.split('with sync_playwright() as p:')[0]
sys.argv = [sys.argv[0]]
exec(head)

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


def open_search(pg):
    pg.keyboard.press('Control+k')
    pg.wait_for_timeout(400)


def ask(pg, text):
    """输入一段内容，返回命令卡的信息（没有则为 None）"""
    pg.fill('#search-input', text)
    pg.wait_for_timeout(350)
    return pg.evaluate("""() => {
        const el = document.querySelector('.se-cmd');
        if (!el) return null;
        const t = el.querySelector('.se-title');
        const m = el.querySelector('.se-meta');
        return {title: t ? t.textContent.trim() : '',
                meta: m ? m.textContent.trim() : '',
                bad: el.className.indexOf('is-bad') >= 0};
    }""")


def body_text(pg):
    el = pg.locator('#search-body')
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

    print('\n[1] 打开与提示')
    open_search(pg)
    chk('Ctrl+K 打开面板', pg.evaluate("() => !!document.querySelector('.se-card #search-input')"))
    txt = body_text(pg)
    chk('空输入时给出命令示例', '+1 喝水' in txt and '记 体重' in txt and '新任务' in txt, txt[:80])
    chk('占位提示也提到命令',
        '+1 喝水' in pg.locator('#search-input').get_attribute('placeholder'))

    print('\n[2] 习惯打卡：识别')
    c = ask(pg, '+1 喝水')
    chk('识别为命令', c is not None)
    chk('标题是「喝水 +1」', c and c['title'] == '喝水 +1', str(c))
    chk('说明里报出今天已记录 3 次', c and '已记录 3 次' in c['meta'], str(c))
    chk('不是错误样式', c and not c['bad'])
    chk('右下角不再显示「无结果」', '无结果' not in pg.locator('.se-foot').inner_text(),
        pg.locator('.se-foot').inner_text())
    chk('底部提示改成「回车执行」', '回车执行' in pg.locator('#se-hint').inner_text(),
        pg.locator('#se-hint').inner_text())

    print('\n[3] 习惯打卡：执行')
    pg.keyboard.press('Enter')
    pg.wait_for_timeout(800)
    chk('执行后关闭面板', pg.evaluate("() => !document.querySelector('.se-card')"))
    chk('弹出提示', pg.locator('#toast.show').count() == 1,
        pg.locator('#toast.show').inner_text() if pg.locator('#toast.show').count() else '')
    open_search(pg)
    c = ask(pg, '+1 喝水')
    chk('再问一次：已记录 4 次（真的写进去了）', c and '已记录 4 次' in c['meta'], str(c))

    print('\n[4] 撤销')
    c = ask(pg, '-1 喝水')
    chk('识别为「喝水 -1」', c and c['title'] == '喝水 -1', str(c))
    pg.keyboard.press('Enter')
    pg.wait_for_timeout(800)
    open_search(pg)
    c = ask(pg, '+1 喝水')
    chk('撤销后回到 3 次', c and '已记录 3 次' in c['meta'], str(c))

    print('\n[5] 记体重')
    c = ask(pg, '记 体重 65.5')
    chk('识别为记录体重', c and '65.5' in c['title'], str(c))
    chk('说明写「写进今天」', c and '今天' in c['meta'], str(c))
    pg.keyboard.press('Enter')
    pg.wait_for_timeout(900)
    chk('执行后关闭', pg.evaluate("() => !document.querySelector('.se-card')"))
    nav(pg, 'stats')
    pg.wait_for_timeout(900)
    stats_txt = pg.locator('#main').inner_text()
    chk('统计页体重变化更新为 -4.5 kg', '-4.5' in stats_txt,
        [l for l in stats_txt.split('\n') if 'kg' in l][:2])

    print('\n[6] 新任务')
    open_search(pg)
    c = ask(pg, '新任务 交报告 明天')
    chk('识别为新建待办', c and '交报告' in c['title'], str(c))
    chk('截止日期解析成明天（2026-10-26）', c and '2026-10-26' in c['meta'], str(c))
    chk('标题里没有残留「明天」', c and '明天' not in c['title'], str(c))
    pg.keyboard.press('Enter')
    pg.wait_for_timeout(900)
    open_search(pg)
    ask(pg, '交报告')
    found = pg.locator('.se-item').count()
    chk('搜索「交报告」能搜到刚建的待办', found >= 1, 'count=%d' % found)
    chk('搜到的那条标题就是它', '交报告' in body_text(pg), body_text(pg)[:60])

    print('\n[7] 认不出来就退回搜索')
    c = ask(pg, '+1 不存在的习惯')
    chk('不认识的习惯名不当命令', c is None, str(c))
    chk('提示无匹配', '没有匹配' in body_text(pg), body_text(pg)[:50])
    c = ask(pg, '阿莫西林')
    chk('普通搜索词不当命令', c is None)
    chk('搜到了药', pg.locator('.se-item').count() >= 1)

    print('\n[8] 错误用法给出原因')
    c = ask(pg, '记 体重 999')
    chk('超范围识别为错误卡', c and c['bad'], str(c))
    chk('说明合理范围', c and '1–500' in c['title'], str(c))
    c = ask(pg, '新任务 今天')
    chk('只有日期没有标题时报错', c and c['bad'], str(c))
    chk('提示用户补上要做什么', c and '加上要做什么' in c['title'], str(c))

    print('\n[9] 手机上')
    pg.keyboard.press('Escape')
    pg.wait_for_timeout(300)
    pg.set_viewport_size({'width': 390, 'height': 844})
    pg.wait_for_timeout(500)
    # 窄屏下 brand-search 是隐藏的，悬浮按钮才是可见入口
    pg.click('.search-fab')
    pg.wait_for_timeout(500)
    pg.fill('#search-input', '+1 喝水')
    pg.wait_for_timeout(400)
    m = pg.evaluate("""() => {
        const card = document.querySelector('.se-card');
        const cmd = document.querySelector('.se-cmd');
        return {
          ovf: document.documentElement.scrollWidth > document.documentElement.clientWidth,
          hasCmd: !!cmd,
          cmdW: cmd ? Math.round(cmd.getBoundingClientRect().width) : 0,
          cardW: card ? Math.round(card.getBoundingClientRect().width) : 0
        };
    }""")
    chk('没有横向溢出', not m['ovf'], str(m))
    chk('命令卡在手机上仍然显示', m['hasCmd'], str(m))
    chk('命令卡没有超出卡片', m['cmdW'] <= m['cardW'], str(m))
    pg.screenshot(path=os.path.join(ROOT, 'e2e', 'shots', 'v43-cmd-mobile.png'))

    print('\n[10] 控制台')
    chk('没有 JS 异常', not errs, '; '.join(errs[:2]))

    br.close()

print('\n----------------------------')
print('通过 %d 项，失败 %d 项' % (PASS, len(FAILS)))
for name, detail in FAILS:
    print('  失败：%s  << %s' % (name, detail))
sys.exit(0 if not FAILS else 1)
