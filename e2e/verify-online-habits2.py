# -*- coding: utf-8 -*-
"""小习惯 2.0 线上实测（todo.csl88.top，test@sl00.top）
跨天用 clock mock；虚拟数据留在测试账号，结束后 logout。"""
import sys
from datetime import datetime

sys.argv = [sys.argv[0]]
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
        print('  ✗ %s  << %s' % (name, str(detail)[:120]))


def card_state(pg, name):
    return pg.evaluate("""(n) => {
        const c = [...document.querySelectorAll('.habit-card')].find(c => {
            const b = c.querySelector('.habit-title b');
            return b && b.textContent.trim() === n;
        });
        if (!c) return null;
        const ok = c.querySelector('[data-ok]');
        return {
            state: c.querySelector('.habit-state').textContent.trim(),
            today: c.querySelector('.hw-cell.is-today') ? c.querySelector('.hw-cell.is-today').className.replace('hw-cell ', '').replace('is-', '') : '',
            disabled: ok ? !!ok.disabled : false,
            weekn: c.querySelector('.hc-weekn') ? c.querySelector('.hc-weekn').textContent.trim() : '',
            pace: c.querySelector('.hc-pace') ? c.querySelector('.hc-pace').textContent.trim() : ''
        };
    }""", name)


def new_habit(pg, name, kind, days=None, per_week=None, interval=None):
    pg.click('[data-act="habit-new"]')
    pg.wait_for_timeout(600)
    pg.fill('#habit-form [name="name"]', name)
    if kind != 'daily':
        pg.evaluate("(k) => document.querySelector('#schedKind [data-sched=\"' + k + '\"]').click()", kind)
        pg.wait_for_timeout(350)
        if kind == 'weekdays' and days is not None:
            on_now = pg.eval_on_selector_all('#schedExtra [data-day].on', 'els=>els.map(e=>e.dataset.day)')
            for d in on_now:
                pg.evaluate("(d) => document.querySelector('#schedExtra [data-day=\"' + d + '\"]').click()", d)
            for d in days:
                pg.evaluate("(d) => document.querySelector('#schedExtra [data-day=\"' + d + '\"]').click()", d)
        elif kind == 'weekly' and per_week:
            pg.fill('#schedExtra [data-sw="perWeek"]', str(per_week))
        elif kind == 'interval' and interval:
            pg.fill('#schedExtra [data-sw="intervalDays"]', str(interval))
    pg.click('#habit-form button[type="submit"]')
    pg.wait_for_timeout(1000)


def main():
    with sync_playwright() as p:
        br = p.chromium.launch(channel='chrome', headless=True)
        ctx = br.new_context(viewport={'width': 1440, 'height': 1000})
        pg = ctx.new_page()
        errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)[:160]))
        pg.on('dialog', lambda d: d.accept())
        pg.clock.install(time=datetime(2026, 11, 28, 10, 0, 0))  # 周六

        pg.goto('https://todo.csl88.top/index.html', wait_until='domcontentloaded')
        pg.wait_for_timeout(3500)
        if pg.locator('[data-act="cloud-login"]').count():
            pg.click('[data-act="cloud-login"]')
            pg.wait_for_timeout(500)
            pg.fill('input[name="email"]', 'test@sl00.top')
            pg.fill('input[name="password"]', 'test@sl00.top')
            pg.click('form.modal-card button[type="submit"]')
            pg.wait_for_timeout(3200)

        print('[0] 版本与登录')
        ver = pg.evaluate("() => (window.APP_VERSION || '')")
        chk('线上版本 v221', 'v221' in ver or pg.locator('body').inner_text().find('v221') >= 0, ver)

        pg.click('.nav-item[data-nav="habits"]')
        pg.wait_for_timeout(800)
        print('[1] UI 创建四个不同节奏的习惯')
        new_habit(pg, '健身2.0', 'weekdays', days=[1, 3, 5])
        new_habit(pg, '冥想2.0', 'weekly', per_week=3)
        new_habit(pg, '浇花2.0', 'interval', interval=3)
        new_habit(pg, '读书2.0', 'daily')
        for n in ['健身2.0', '冥想2.0', '浇花2.0', '读书2.0']:
            found = pg.evaluate("(n) => !![...document.querySelectorAll('.habit-card')].find(c => { const b = c.querySelector('.habit-title b'); return b && b.textContent.trim() === n; })", n)
            chk('已创建 ' + n, found)

        print('[2] 周六（今天）：weekdays 不在待办、其余可打卡')
        pg.click('.nav-item[data-nav="today"]')
        pg.wait_for_timeout(900)
        s = card_state(pg, '健身2.0')
        chk('健身不在今日页（周六不需要做）', s is None, s)
        for n in ['冥想2.0', '浇花2.0', '读书2.0']:
            s = card_state(pg, n)
            chk(n + ' 在今日页且待打卡', s and s['state'] == '今日待打卡', s)

        print('[3] 读书打卡 / 撤销')
        hid = pg.evaluate("""() => { const c = [...document.querySelectorAll('.habit-card')].find(c => { const b = c.querySelector('.habit-title b'); return b && b.textContent.trim() === '读书2.0'; }); return c ? c.dataset.hid : null; }""")
        pg.click('[data-hid="' + hid + '"] [data-ok]')
        pg.wait_for_timeout(400)
        s = card_state(pg, '读书2.0')
        chk('打卡后已完成', s and s['state'] == '今日已完成', s)
        pg.click('[data-hid="' + hid + '"] [data-ok]')
        pg.wait_for_timeout(400)
        s = card_state(pg, '读书2.0')
        chk('撤销后回待打卡', s and s['state'] == '今日待打卡', s)
        pg.click('[data-hid="' + hid + '"] [data-ok]')
        pg.wait_for_timeout(400)

        print('[4] 冥想（每周3次）跨三天打卡 → 达成')
        for i in range(3):
            if i:
                pg.clock.fast_forward('1d')
                pg.wait_for_timeout(900)
                pg.reload(wait_until='domcontentloaded')
                pg.wait_for_timeout(3000)
            hid = pg.evaluate("""() => { const c = [...document.querySelectorAll('.habit-card')].find(c => { const b = c.querySelector('.habit-title b'); return b && b.textContent.trim() === '冥想2.0'; }); return c ? c.dataset.hid : null; }""")
            if hid:
                pg.click('[data-hid="' + hid + '"] [data-ok]')
                pg.wait_for_timeout(500)
        pg.wait_for_timeout(600)
        pg.reload(wait_until='domcontentloaded')
        pg.wait_for_timeout(3000)
        s = card_state(pg, '冥想2.0')
        chk('三次打卡后已达成', s and s['state'] == '今日已完成', s)
        chk('计数位显示 3/3', s and '3/3' in s['weekn'], s and s['weekn'])
        hero = pg.locator('#main').inner_text()
        chk('hero 出现「本周节奏：冥想2.0 3/3」', '本周节奏' in hero and '冥想2.0 3/3' in hero, hero[:80])
        chk('冥想仍在今日页（折叠显示不消失）', s is not None)

        print('[5] 浇花（每3天）：day0 打卡 → day1 off → day3 新一轮')
        pg.clock.fast_forward('1d')
        pg.wait_for_timeout(900)
        pg.reload(wait_until='domcontentloaded')
        pg.wait_for_timeout(3000)
        s = card_state(pg, '浇花2.0')
        chk('day1 本轮已做 → off 折叠', s and s['today'].find('off') >= 0, s)
        pg.clock.fast_forward('2d')
        pg.wait_for_timeout(900)
        pg.reload(wait_until='domcontentloaded')
        pg.wait_for_timeout(3000)
        s = card_state(pg, '浇花2.0')
        chk('day3 新一轮回到待打卡', s and s['state'] == '今日待打卡', s)

        print('[6] 周一：健身卡出现且待打卡')
        # 当前是 12-01 周二（11-28+3）……先回周六再跳周一
        pg.clock.fast_forward('6d')
        pg.wait_for_timeout(900)
        pg.reload(wait_until='domcontentloaded')
        pg.wait_for_timeout(3000)
        s = card_state(pg, '健身2.0')
        chk('周一健身卡出现', s is not None, s)
        if s:
            chk('周一健身待打卡（不禁用）', s['state'] == '今日待打卡' and not s['disabled'], s)

        print('[7] 代码逻辑自检')
        chk('无 pageerror', not errs, ' / '.join(errs[:2]))

        print('[8] 退出登录（释放会话）')
        try:
            pg.evaluate("() => { const b = [...document.querySelectorAll('[data-act]')].find(b => b.dataset.act.indexOf('logout') >= 0); if (b) b.click(); }")
            pg.wait_for_timeout(800)
            print('  已触发 logout')
        except Exception as e:
            print('  logout 手动跳过:', str(e)[:60])

        print('\n结果：%d 通过 / %d 失败' % (PASS, FAIL))
        if FAILS:
            print('失败项：' + '、'.join(FAILS))
        br.close()
        sys.exit(1 if FAIL else 0)


if __name__ == '__main__':
    main()
