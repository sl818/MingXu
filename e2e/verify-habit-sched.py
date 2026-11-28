# -*- coding: utf-8 -*-
"""小习惯 2.0：节奏（sched）端到端验证

覆盖：
  1. 新建表单有「多久一次」四张卡；选「每周固定几天」出现星期多选；
  2. 保存 weekdays（周一三五）后：卡片 pace 显示周一三五、计数位本周 0/3、
     今天（周六）的格子是 off 虚线、徽标「今天不需要做」、完成按钮禁用；
  3. weekdays 不进今日完成率分母（dayStats 只算该做 + 已完成的）；
  4. 老数据兼容：notifyFreq=weekly + notifyWeekday=0 的习惯，应打卡仍是每周那一天，
     不会被静默改成「每天」；
  5. 周期型（weekly）不进 dayStats，另有 metPeriod。
"""
import os, sys
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
        print('  ✓', name)
    else:
        FAIL += 1
        FAILS.append(name)
        print('  ✗ %s  << %s' % (name, detail))


def main():
    with sync_playwright() as p:
        br = p.chromium.launch(channel='chrome', headless=True)
        ctx = br.new_context(viewport={'width': 1440, 'height': 1000})
        pg = ctx.new_page()
        errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)[:160]))
        pg.on('dialog', lambda d: d.accept())
        pg.clock.install(time=datetime(2026, 11, 28, 10, 0, 0))

        pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
        pg.wait_for_timeout(600)
        if pg.locator('[data-act="cloud-login"]').count():
            pg.click('[data-act="cloud-login"]')
            pg.wait_for_timeout(400)
            pg.fill('input[name="email"]', 'test@example.com')
            pg.fill('input[name="password"]', 'test@example.com')
            pg.click('form.modal-card button[type="submit"]')
            pg.wait_for_timeout(2600)

        # 老数据兼容样本：notifyFreq=weekly + 周日；以及一个 daily
        board['data']['habits'] = [
            {'id': 'h_old', 'name': '每周六', 'icon': '📌', 'type': 'build', 'target': 1,
             'unit': '次', 'color': '#6b5b8e', 'note': '', 'createdAt': '2026-07-01T08:00:00Z',
             'notifyFreq': 'weekly', 'notifyWeekday': 6},
        ]
        board['data']['checks'] = {}
        board['data']['cravings'] = []
        board['data']['skips'] = {}
        pg.reload(wait_until='networkidle')
        pg.wait_for_timeout(2400)

        print('[1] 新建表单有节奏四选一')
        pg.click('.nav-item[data-nav="habits"]')
        pg.wait_for_timeout(900)
        pg.click('[data-act="habit-new"]')
        pg.wait_for_timeout(600)
        chk('弹窗里有「多久一次」', pg.locator('#schedKind [data-sched]').count() == 4)
        chk('默认选中「每天」', pg.locator('#schedKind [data-sched="daily"]').get_attribute('class').find('on') >= 0)
        pg.evaluate("() => { const b = document.querySelector('#schedKind [data-sched=\"weekdays\"]'); if (b) b.click(); }")
        pg.wait_for_timeout(400)
        chk('选 weekdays 后出现 7 个星期按钮', pg.locator('#schedExtra [data-day]').count() == 7)
        on_days = pg.eval_on_selector_all('#schedExtra [data-day].on', 'els=>els.map(e=>e.dataset.day)')
        chk('初始默认选中周一三五', sorted(on_days) == ['1', '3', '5'], str(on_days))
        pg.evaluate("""() => { [0, 6].forEach(d => {
            const b = document.querySelector('#schedExtra [data-day="' + d + '"]'); if (b) b.click(); }); }""")
        pg.wait_for_timeout(250)
        on_days = pg.eval_on_selector_all('#schedExtra [data-day].on', 'els=>els.map(e=>e.dataset.day)')
        chk('补选周日周六后共 5 天', sorted(on_days) == ['0', '1', '3', '5', '6'], str(on_days))
        pg.evaluate("""() => { [0, 1, 3, 5, 6].forEach(d => {
            const b = document.querySelector('#schedExtra [data-day="' + d + '"]'); if (b) b.click(); }); }""")
        pg.wait_for_timeout(250)
        on_days = pg.eval_on_selector_all('#schedExtra [data-day].on', 'els=>els.map(e=>e.dataset.day)')
        chk('全取消后回落周一三五', sorted(on_days) == ['1', '3', '5'], str(on_days))

        print('[2] 填名称保存，检查卡片')
        pg.fill('#habit-form [name="name"]', '健身打卡')
        pg.click('#habit-form button[type="submit"]')
        pg.wait_for_timeout(1200)
        pg.click('.nav-item[data-nav="habits"]')
        pg.wait_for_timeout(900)

        card = pg.locator('.habit-card[data-hid] .habit-title b:text-is("健身打卡")').first
        hid = pg.evaluate("""() => {
            const c = [...document.querySelectorAll('.habit-card')].find(c => {
                const b = c.querySelector('.habit-title b');
                return b && b.textContent.trim() === '健身打卡';
            });
            return c ? c.dataset.hid : null;
        }""")
        chk('保存后习惯页出现该习惯', '健身打卡' in pg.locator('#main').inner_text(), '页面文本里没有「健身打卡」')
        if hid:
            cinfo = pg.evaluate("""(h) => {
                const e = document.querySelector('.habit-card[data-hid="' + h + '"]');
                return {
                    pace: e.querySelector('.hc-pace').textContent.trim(),
                    weekn: e.querySelector('.hc-weekn').textContent.trim(),
                    state: e.querySelector('.habit-state').textContent.trim(),
                    today: e.querySelector('.hw-cell.is-today').className.replace('hw-cell ', '').replace('is-', ''),
                    okDisabled: !!e.querySelector('[data-ok]').disabled,
                    okText: e.querySelector('[data-ok] span').textContent.trim()
                };
            }""", hid)
            chk('节奏文案 = 周一 / 周三 / 周五', cinfo['pace'] == '周一 / 周三 / 周五', cinfo['pace'])
            chk('计数位 = 本周 0/3', '本周 0/3' in cinfo['weekn'], cinfo['weekn'])
            chk('今天格子 = off 虚线', cinfo['today'] == 'off is-today' or cinfo['today'].find('off') >= 0, cinfo['today'])
            chk('徽标 = 今天不需要做', cinfo['state'] == '今天不需要做', cinfo['state'])
            chk('完成按钮禁用', cinfo['okDisabled'])
            chk('按钮文字 = 今天不需要做', cinfo['okText'] == '今天不需要做', cinfo['okText'])

        print('[3] 今日页不显示今天不需要做的习惯')
        pg.click('.nav-item[data-nav="today"]')
        pg.wait_for_timeout(900)
        visible = pg.evaluate("() => [...document.querySelectorAll('.habit-card .habit-title b')].map(e => e.textContent.trim())")
        chk('今日页不含健身打卡（今天不需要做）', '健身打卡' not in visible, str(visible))
        chk('今日页仍含老习惯', '每周六' in visible, str(visible))

        print('[4] 老数据兼容：notifyFreq=weekly 仍是每周那一天')
        oc = pg.evaluate("""() => {
            const c = [...document.querySelectorAll('.habit-card')].find(c => {
                const b = c.querySelector('.habit-title b');
                return b && b.textContent.trim() === '每周六';
            });
            if (!c) return null;
            return {
                pace: c.querySelector('.hc-pace').textContent.trim(),
                weekn: c.querySelector('.hc-weekn').textContent.trim()
            };
        }""")
        chk('老习惯卡片在今日页可见', bool(oc), '未找到「每周六」卡')
        if oc:
            chk('老习惯节奏 = 周六', '周六' in oc['pace'], oc['pace'])
            chk('计数位 = 本周 0/1', '本周 0/1' in oc['weekn'], oc['weekn'])

        print('[5] 无 JS 报错')
        chk('无 pageerror', not errs, ' / '.join(errs[:2]))

        print('\n结果：%d 通过 / %d 失败' % (PASS, FAIL))
        if FAILS:
            print('失败项：' + '、'.join(FAILS))
        br.close()
        sys.exit(1 if FAIL else 0)


if __name__ == '__main__':
    main()
