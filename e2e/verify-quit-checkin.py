# -*- coding: utf-8 -*-
"""戒除类主动打卡（v204）

以前戒除类「不点算一直守着」，每天凌晨自动变完成。v204 起：
  · quit 从 2026-11-27 起必须点「完成」打卡才算守住；
  · smoke（戒烟）保持「没抽就算守住」不变；
  · 生效日之前的历史仍按老口径，已有统计不翻旧账。

这组用例锁：
  1. 生效日后，戒除类不打卡 = 今日待打卡、周条空圈、连续 0 天；
  2. 点「完成」打卡后 = 今日已完成、周条勾、连续 1 天；再点撤销回到待打卡；
  3. 点「未完成」记失守后 = 今日未完成，打卡被清掉；
  4. 戒烟卡不受影响：不点仍是守住；
  5. 切到生效日前一天，同一戒除类没打卡也算守住（历史口径）。
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


def habit(hid, name, typ, slip='once'):
    return {
        'id': hid, 'name': name, 'icon': '🚫', 'type': typ, 'target': 1, 'unit': '次',
        'color': '#c2705f', 'note': '', 'createdAt': '2026-10-01T08:00:00Z',
        'pinned': False, 'med': False, 'quitStart': '2026-10-01',
        'quitPerDay': 0, 'quitPackPrice': 0, 'quitPackSize': 0, 'slipMode': slip
    }


def card(pg, name):
    return pg.evaluate("""(nm) => {
        const el = [...document.querySelectorAll('.habit-card')].find(c => {
            const b = c.querySelector('.habit-title b');
            return b && (b.textContent || '').trim() === nm;
        });
        if (!el) return null;
        const st = el.querySelector('.habit-state');
        const today = el.querySelector('.hw-cell.is-today');
        const streak = el.querySelector('.hc-streak b');
        const pace = el.querySelector('.hc-pace');
        const tally = el.querySelector('.hc-tally');
        return {
            state: st ? (st.textContent || '').trim() : '',
            mark: today ? (today.querySelector('i').textContent || '').trim() : '',
            weekCls: today ? today.className : '',
            streak: streak ? (streak.textContent || '').trim() : '',
            pace: pace ? (pace.textContent || '').trim() : '',
            tally: tally ? (tally.textContent || '').replace(/\\s+/g, ' ').trim() : '',
            done: el.classList.contains('is-done')
        };
    }""", name)


def click(pg, name, act):
    pg.evaluate("""(args) => {
        const el = [...document.querySelectorAll('.habit-card')].find(c => {
            const b = c.querySelector('.habit-title b');
            return b && (b.textContent || '').trim() === args[0];
        });
        if (!el) return;
        const btn = el.querySelector('[data-act="' + args[1] + '"]');
        if (btn) btn.click();
    }""", [name, act])
    pg.wait_for_timeout(900)


def main():
    with sync_playwright() as p:
        br = p.chromium.launch(channel='chrome', headless=True)
        ctx = br.new_context(viewport={'width': 1512, 'height': 1000})
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

        board['data']['habits'] = [habit('h_q_new', '不喝含糖饮料', 'quit'), habit('h_smoke', '戒烟测试', 'smoke')]
        board['data']['checks'] = {}
        board['data']['cravings'] = []
        board['data']['skips'] = {}
        pg.reload(wait_until='networkidle')
        pg.wait_for_timeout(2400)

        print('[1] 生效日后：戒除类不打卡 = 待打卡')
        c = card(pg, '不喝含糖饮料')
        chk('状态是「今日待打卡」', c and c['state'] == '今日待打卡', c['state'] if c else '')
        chk('周条今天没有勾', c and 'is-done' not in c['weekCls'], c['weekCls'] if c else '')
        chk('连续 0 天', c and c['streak'] == '0', c['streak'] if c else '')
        chk('节奏文案是「每天打卡守住」', c and '打卡守住' in c['pace'], c['pace'] if c else '')

        print('[2] 点「完成」打卡后变完成，再点撤销')
        click(pg, '不喝含糖饮料', 'habit-ok')
        c = card(pg, '不喝含糖饮料')
        chk('状态是「今日已完成」', c and c['state'] == '今日已完成', c['state'] if c else '')
        chk('周条今天有勾', c and 'is-done' in c['weekCls'], c['weekCls'] if c else '')
        chk('连续 1 天', c and c['streak'] == '1', c['streak'] if c else '')
        chk('打卡后卡片是完成态', c and c['done'], str(c))
        click(pg, '不喝含糖饮料', 'habit-ok')
        c = card(pg, '不喝含糖饮料')
        chk('撤销后回到待打卡', c and c['state'] == '今日待打卡', c['state'] if c else '')

        print('[3] 点「未完成」记失守')
        click(pg, '不喝含糖饮料', 'habit-no')
        c = card(pg, '不喝含糖饮料')
        chk('状态是「今日未完成」', c and c['state'] == '今日未完成', c['state'] if c else '')
        chk('周条今天画了叉', c and 'is-fail' in c['weekCls'], c['weekCls'] if c else '')

        print('[4] 戒烟卡不受影响')
        c = card(pg, '戒烟测试')
        # 戒烟走独立的 quitCard 结构，没有 .habit-state；is-done 为守住态
        chk('戒烟仍是守住态', c and c['done'], str(c))

        print('[5] 生效日前一天（11-26）：同一戒除类没打卡也算守住')
        pg2 = ctx.new_page()
        pg2.on('pageerror', lambda e: errs.append(str(e)[:160]))
        pg2.clock.install(time=datetime(2026, 11, 26, 10, 0, 0))
        pg2.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
        pg2.wait_for_timeout(2400)
        c = card(pg2, '不喝含糖饮料')
        chk('历史日没打卡也守住', c and c['state'] == '今日已完成', c['state'] if c else '')
        chk('历史日节奏文案沿用老口径', c and c['pace'] == '每天保持 0 次', c['pace'] if c else '')

        print('[6] 多次失守模式：点「完成」逐次撤销，撤完再点才打卡')
        pg2.close()          # 先关掉历史日期那个页面，避免它异步回写覆盖 mock 数据
        SLIP_TS = int(datetime(2026, 11, 28, 8, 0, 0).timestamp())
        board['data']['habits'] = [habit('h_q_multi', '不吃含糖饮料', 'quit', 'multi')]
        board['data']['checks'] = {}
        board['data']['cravings'] = [
            {'id': 'cm%02d' % i, 'h': 'h_q_multi', 'k': 's', 't': SLIP_TS} for i in range(1, 4)
        ]
        board['data']['skips'] = {}

        pg3 = ctx.new_page()
        pg3.on('pageerror', lambda e: errs.append(str(e)[:160]))
        pg3.on('dialog', lambda d: d.accept())
        pg3.clock.install(time=datetime(2026, 11, 28, 10, 0, 0))
        pg3.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
        pg3.wait_for_timeout(2600)

        c = card(pg3, '不吃含糖饮料')
        chk('多次模式初始为未完成 + 失守 3 次',
            c and c['state'] == '今日未完成' and '失守3次' in c['tally'].replace(' ', ''), str(c))

        click(pg3, '不吃含糖饮料', 'habit-ok')
        c = card(pg3, '不吃含糖饮料')
        chk('点 1 次「完成」→ 只撤销 1 条失守，仍未完成',
            c and c['state'] == '今日未完成' and '失守2次' in c['tally'].replace(' ', ''), str(c))

        click(pg3, '不吃含糖饮料', 'habit-ok')
        click(pg3, '不吃含糖饮料', 'habit-ok')
        c = card(pg3, '不吃含糖饮料')
        chk('撤完 3 条 → 回到待打卡', c and c['state'] == '今日待打卡', str(c))
        chk('失守已清零', c and '失守' not in c['tally'], str(c))

        click(pg3, '不吃含糖饮料', 'habit-ok')
        c = card(pg3, '不吃含糖饮料')
        chk('第 4 次点「完成」→ 今日已完成', c and c['state'] == '今日已完成', str(c))
        chk('卡片进入完成态', c and c['done'], str(c))

        chk('无 JS 报错', not errs, ' / '.join(errs[:2]))

        print('\n结果：%d 通过 / %d 失败' % (PASS, FAIL))
        if FAILS:
            print('失败项：' + '、'.join(FAILS))
        br.close()
        sys.exit(1 if FAIL else 0)


if __name__ == '__main__':
    main()
