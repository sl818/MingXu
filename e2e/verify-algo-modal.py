# -*- coding: utf-8 -*-
"""统计页「考核算法」说明弹窗（v81）

锁三件事：
  1. 按钮在统计页头部、7/30/90 天分段控件的左边；
  2. 弹窗九个部分都在，且关键阈值与代码一致（75%、完成度、按创建时间）；
  3. 手机上不横向溢出，表格换成块状排列。
"""
import os
import sys
from datetime import datetime

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


def to_stats(pg):
    pg.evaluate("() => { const b=document.querySelector('[data-nav=\"stats\"]'); if(b) b.click(); }")
    pg.wait_for_timeout(1000)


def main():
    with sync_playwright() as p:
        br = p.chromium.launch(channel='chrome', headless=True)
        ctx = br.new_context(viewport={'width': 1512, 'height': 1000})
        pg = ctx.new_page()
        errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)[:160]))
        pg.clock.install(time=datetime(2026, 11, 10, 15, 0, 0))

        pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
        pg.wait_for_timeout(500)
        if pg.locator('[data-act="cloud-login"]').count():
            pg.click('[data-act="cloud-login"]')
            pg.wait_for_timeout(400)
            pg.fill('input[name="email"]', 'test@sl00.top')
            pg.fill('input[name="password"]', 'test@sl00.top')
            pg.click('form.modal-card button[type="submit"]')
            pg.wait_for_timeout(2600)

        to_stats(pg)

        print('[1] 按钮位置')
        btn = pg.locator('.stats-acts [data-act="algo-open"]')
        chk('统计页头部有「考核算法」按钮', btn.count() == 1)
        chk('按钮文字正确', (btn.text_content() or '').strip() == '考核算法', btn.text_content())
        pos = pg.evaluate("""() => {
            const b = document.querySelector('.stats-acts [data-act="algo-open"]');
            const r = document.querySelector('.stats-acts .range-switch');
            if (!b || !r) return null;
            const rb = b.getBoundingClientRect(), rr = r.getBoundingClientRect();
            return {
                btnRight: Math.round(rb.right), rangeLeft: Math.round(rr.left),
                sameRow: Math.abs(Math.round(rb.bottom) - Math.round(rr.bottom)) <= 4,
                btnTop: Math.round(rb.top), rangeTop: Math.round(rr.top)
            };
        }""")
        chk('按钮在分段控件左边', pos and pos['btnRight'] <= pos['rangeLeft'],
            str(pos))
        chk('两者垂直居中在同一行', pos and pos['sameRow'], str(pos))

        print('[2] 弹窗内容')
        btn.first.click()
        pg.wait_for_timeout(700)
        card = pg.locator('.algo-card')
        chk('弹窗打开', card.count() == 1)
        txt = card.text_content() or ''

        chk('标题是「考核算法」', '考核算法' in txt)

        heads = pg.evaluate("""() => [...document.querySelectorAll('.algo-card .algo-h')]
            .map(x => (x.textContent || '').trim())""")
        chk('九个部分齐全', len(heads) == 9, '%d 个：%s' % (len(heads), heads))
        for key in ['单个习惯', '完成率', '75%', '日历上的颜色', '连续达标',
                    '有记录', '月度小结', '用药', '不参与考核']:
            chk('包含「%s」一节' % key, any(key in h for h in heads), str(heads))

        # 关键阈值必须和代码一致：改 met/dayStats/dayQualified 时这里会先炸
        chk('写着达标门槛 75%', '75%' in txt)
        chk('写着「只统计有记录的日子」', '有记录' in txt)
        chk('月度小结两个口径都讲了', '达标天数' in txt and '完成度' in txt)
        chk('任务按创建时间圈定', '创建时间' in txt)
        chk('写明取消也算分母', '分母' in txt)
        chk('写明不参与考核的模块', '不打分' in txt)

        tables = card.locator('table.algo-table')
        chk('用了 4 张表（类型 / 颜色 / 两口径 / 模块口径）', tables.count() == 4,
            'tables=%d' % tables.count())

        print('[3] 关闭')
        pg.click('.algo-card [data-act="close-modal"]')
        pg.wait_for_timeout(500)
        chk('点「知道了」能关掉', pg.locator('.algo-card').count() == 0)

        print('[4] 手机端')
        ctx.close()
        ctx2 = br.new_context(viewport={'width': 390, 'height': 844},
                              has_touch=True, is_mobile=True, device_scale_factor=2)
        pg2 = ctx2.new_page()
        pg2.on('pageerror', lambda e: errs.append('mb ' + str(e)[:120]))
        pg2.clock.install(time=datetime(2026, 11, 10, 15, 0, 0))
        pg2.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
        pg2.wait_for_timeout(500)
        if pg2.locator('[data-act="cloud-login"]').count():
            pg2.click('[data-act="cloud-login"]')
            pg2.wait_for_timeout(400)
            pg2.fill('input[name="email"]', 'test@sl00.top')
            pg2.fill('input[name="password"]', 'test@sl00.top')
            pg2.click('form.modal-card button[type="submit"]')
            pg2.wait_for_timeout(2600)
        to_stats(pg2)
        pg2.click('[data-act="algo-open"]')
        pg2.wait_for_timeout(700)
        dim = pg2.evaluate("""() => {
            const c = document.querySelector('.algo-card');
            const td = c.querySelector('.algo-table td');
            const cs = getComputedStyle(td);
            return {
                docW: document.documentElement.scrollWidth,
                vw: innerWidth,
                cardW: Math.round(c.getBoundingClientRect().width),
                overflow: c.scrollWidth - c.clientWidth,
                tdDisplay: cs.display,
                firstColW: Math.round(td.getBoundingClientRect().width)
            };
        }""")
        chk('手机上没有横向溢出', dim['docW'] <= dim['vw'], str(dim))
        chk('弹窗内部也不溢出', dim['overflow'] <= 1, str(dim))
        chk('表格在窄屏变成块级（不是两列硬挤）', dim['tdDisplay'] == 'block', str(dim))
        chk('第一列占了整行宽度', dim['firstColW'] > dim['cardW'] * 0.8, str(dim))

        chk('无 JS 异常', not errs, str(errs))

        ctx2.close()
        br.close()


main()
print('----------------------------')
print('考核算法弹窗：%d 通过 / %d 失败' % (PASS, FAIL))
if FAILS:
    print('失败项：' + ' / '.join(FAILS))
if FAIL:
    sys.exit(1)
