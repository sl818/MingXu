# -*- coding: utf-8 -*-
"""戒除习惯的「每日单次 / 每日多次」（v79）

数据层本来就支持一天多条（戒除的失守记录也存在 cravings 事件流里，
quitSlips 一直是 filter(k==='s').length）。卡住的只有 UI 和 action：
  · habitCard 的戒除分支只画了一个开/关两态的 .pip
  · quit-mark 是 toggle，再点一下就把当天全删，记不到第 2 次

这组用例锁：
  1. 老习惯（没有 slipMode）行为一点不变，还是 toggle 横条；
  2. multi 走 .quit-add 按钮，点 3 次记 3 次；
  3. **同一秒内连点也记 2 次**（addCraving 的 1 秒去重必须对 multi 失效）；
  4. 撤销只退最后一条，不是整天清零；
  5. 表单里「打卡方式」只对通用戒除显示，戒烟不显示。
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


def quit_habit(hid, name, mode=None):
    h = {
        'id': hid, 'name': name, 'icon': '🚫', 'type': 'quit', 'target': 1, 'unit': '次',
        'color': '#c2705f', 'note': '', 'createdAt': '2026-10-01T08:00:00Z',
        'pinned': False, 'med': False, 'quitStart': '2026-10-01',
        'quitPerDay': 0, 'quitPackPrice': 0, 'quitPackSize': 0,
    }
    if mode:
        h['slipMode'] = mode
    return h


def load(pg, habits):
    board['data']['habits'] = habits
    board['data']['cravings'] = []
    board['data']['packs'] = []
    pg.reload(wait_until='networkidle')
    pg.wait_for_timeout(2400)


def card(pg, name):
    """今日页某张习惯卡：按钮形态、文案、次数。"""
    return pg.evaluate("""(nm) => {
        const el = [...document.querySelectorAll('.habit-card')].find(c => {
            const b = c.querySelector('.habit-title b');
            return b && (b.textContent || '').trim() === nm;
        });
        if (!el) return null;
        const add = el.querySelector('.quit-add');
        const pip = el.querySelector('.pips .pip');
        const undo = el.querySelector('.quit-undo');
        const cnt = el.querySelector('.habit-count');
        return {
            hasAdd: !!add,
            addText: add ? (add.textContent || '').replace(/\\s+/g, '') : '',
            addBroken: add ? add.classList.contains('broken') : false,
            hasPip: !!pip,
            pipMark: pip ? pip.dataset.act : '',
            pipOn: pip ? pip.classList.contains('on') : false,
            hasUndo: !!undo,
            count: cnt ? (cnt.textContent || '').replace(/\\s+/g, '') : '',
            state: (el.querySelector('.habit-state') || {}).textContent || ''
        };
    }""", name)


def main():
    with sync_playwright() as p:
        br = p.chromium.launch(channel='chrome', headless=True)
        ctx = br.new_context(viewport={'width': 1512, 'height': 1000})
        pg = ctx.new_page()
        errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)[:160]))
        # 时钟固定：连点几下都落在同一秒，正好验证 multi 的 1 秒去重被跳过
        pg.clock.install(time=datetime(2026, 11, 10, 10, 0, 0))

        pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
        pg.wait_for_timeout(600)
        if pg.locator('[data-act="cloud-login"]').count():
            pg.click('[data-act="cloud-login"]')
            pg.wait_for_timeout(400)
            pg.fill('input[name="email"]', 'test@example.com')
            pg.fill('input[name="password"]', 'test@example.com')
            pg.click('form.modal-card button[type="submit"]')
            pg.wait_for_timeout(2600)

        # 三个：老习惯（无 slipMode）、显式 once、multi
        load(pg, [
            quit_habit('h_q_old', '不熬夜'),
            quit_habit('h_q_once', '不喝奶茶', 'once'),
            quit_habit('h_q_multi', '不喝可乐', 'multi'),
        ])

        print('[1] 老习惯不受影响（无 slipMode = 单次）')
        c = card(pg, '不熬夜')
        chk('画的是 .pip 横条', c and c['hasPip'], str(c))
        chk('没有 .quit-add 按钮', c and not c['hasAdd'], str(c))
        chk('初始是「守住」态（pip 有 on）', c and c['pipOn'], str(c))
        chk('次数显示 0 次未达标', c and c['count'].startswith('0'), c['count'] if c else '')

        pg.click('.habit-card:has(.habit-title b:text-is("不熬夜")) .pips .pip')
        pg.wait_for_timeout(700)
        c = card(pg, '不熬夜')
        chk('点一下 → 1 次未达标', c and c['count'].startswith('1'), c['count'] if c else '')
        chk('横条变空心', c and not c['pipOn'], str(c))
        pg.click('.habit-card:has(.habit-title b:text-is("不熬夜")) .pips .pip')
        pg.wait_for_timeout(700)
        c = card(pg, '不熬夜')
        chk('再点一下 → 撤销回 0（老 toggle 行为）', c and c['count'].startswith('0'),
            c['count'] if c else '')

        print('[2] 显式 once 也走 toggle')
        c = card(pg, '不喝奶茶')
        chk('画的是 .pip 横条', c and c['hasPip'] and not c['hasAdd'], str(c))

        print('[3] multi：点一次记一次')
        c = card(pg, '不喝可乐')
        chk('画的是 .quit-add 按钮', c and c['hasAdd'], str(c))
        chk('没有 .pip 横条', c and not c['hasPip'], str(c))
        chk('未破时文案「今天守住了」', c and '今天守住了' in c['addText'], c['addText'] if c else '')
        chk('未破时没有撤销按钮', c and not c['hasUndo'], str(c))

        pg.click('.habit-card:has(.habit-title b:text-is("不喝可乐")) .quit-add')
        pg.wait_for_timeout(700)
        c = card(pg, '不喝可乐')
        chk('第 1 次 → 1 次未达标', c and c['count'].startswith('1'), c['count'] if c else '')
        chk('按钮变「又破一次」', c and '又破一次' in c['addText'], c['addText'] if c else '')
        chk('按钮进 broken 态', c and c['addBroken'], str(c))
        chk('右上角状态变成「今天失守」', bool(c) and c['state'] == '今天失守', str(c))
        chk('出现撤销按钮', c and c['hasUndo'], str(c))

        # 关键：同一秒内再点第二、第三次，不能被 1 秒去重挡掉
        pg.click('.habit-card:has(.habit-title b:text-is("不喝可乐")) .quit-add')
        pg.wait_for_timeout(500)
        pg.click('.habit-card:has(.habit-title b:text-is("不喝可乐")) .quit-add')
        pg.wait_for_timeout(700)
        c = card(pg, '不喝可乐')
        chk('同一秒连点两次也记上 → 3 次', c and c['count'].startswith('3'), c['count'] if c else '')

        print('[4] 撤销只退最后一条')
        pg.click('.habit-card:has(.habit-title b:text-is("不喝可乐")) .quit-undo')
        pg.wait_for_timeout(700)
        c = card(pg, '不喝可乐')
        chk('撤销 1 次 → 还剩 2 次', c and c['count'].startswith('2'), c['count'] if c else '')
        chk('仍是 broken 态', c and c['addBroken'], str(c))

        pg.click('.habit-card:has(.habit-title b:text-is("不喝可乐")) .quit-undo')
        pg.wait_for_timeout(700)
        pg.click('.habit-card:has(.habit-title b:text-is("不喝可乐")) .quit-undo')
        pg.wait_for_timeout(900)
        c = card(pg, '不喝可乐')
        chk('撤到 0 → 回到「今天守住了」', c and '今天守住了' in c['addText'], c['addText'] if c else '')
        chk('撤销按钮消失', c and not c['hasUndo'], str(c))
        chk('次数回到 0', c and c['count'].startswith('0'), c['count'] if c else '')

        print('[5] 数据确实写进了服务端')
        pg.wait_for_timeout(1200)
        cr = [x for x in (board['data'].get('cravings') or []) if x.get('h') == 'h_q_multi']
        chk('multi 那条记录被撤销干净了', len(cr) == 0, 'cravings=%d' % len(cr))

        print('[6] 表单：打卡方式只给通用戒除')
        pg.evaluate("() => { const b=document.querySelector('[data-nav=\"habits\"]'); if(b) b.click(); }")
        pg.wait_for_timeout(900)
        pg.click('[data-act="habit-edit"][data-id="h_q_multi"]')
        pg.wait_for_timeout(600)
        sel = pg.locator('#habit-form select[name="slipMode"]')
        chk('多次习惯的编辑表单有「打卡方式」', sel.count() == 1)
        chk('值回填成 multi', sel.input_value() == 'multi', sel.input_value() if sel.count() else '')
        chk('它是可见的', sel.is_visible())
        pg.click('#habit-form [data-act="close-modal"]')
        pg.wait_for_timeout(400)

        # 换成单次再保存，卡面要变回横条
        pg.click('[data-act="habit-edit"][data-id="h_q_multi"]')
        pg.wait_for_timeout(600)
        pg.select_option('#habit-form select[name="slipMode"]', 'once')
        pg.click('#habit-form button[type="submit"]')
        pg.wait_for_timeout(900)
        pg.evaluate("() => { const b=document.querySelector('[data-nav=\"today\"]'); if(b) b.click(); }")
        pg.wait_for_timeout(900)
        c = card(pg, '不喝可乐')
        chk('改成单次后卡面变回横条', c and c['hasPip'] and not c['hasAdd'], str(c))

        print('[7] 戒烟不受影响（没有「打卡方式」）')
        board['data']['habits'].append({
            'id': 'h_smk', 'name': '戒烟', 'icon': '🚭', 'type': 'smoke', 'target': 0,
            'unit': '根', 'color': '#7a8471', 'note': '', 'createdAt': '2026-10-01T08:00:00Z',
            'pinned': False, 'med': False, 'quitStart': '2026-10-01',
        })
        pg.reload(wait_until='networkidle')
        pg.wait_for_timeout(2400)
        pg.evaluate("() => { const b=document.querySelector('[data-nav=\"habits\"]'); if(b) b.click(); }")
        pg.wait_for_timeout(900)
        pg.click('[data-act="habit-edit"][data-id="h_smk"]')
        pg.wait_for_timeout(600)
        smkSel = pg.locator('#habit-form select[name="slipMode"]')
        chk('戒烟表单里「打卡方式」是隐藏的',
            smkSel.count() == 1 and not smkSel.is_visible(),
            'count=%d visible=%s' % (smkSel.count(),
                                     smkSel.is_visible() if smkSel.count() else 'n/a'))
        chk('戒烟的「开始日期」仍然可见',
            pg.locator('#habit-form [data-qf-start]').is_visible())
        pg.click('#habit-form [data-act="close-modal"]')
        pg.wait_for_timeout(400)
        pg.evaluate("() => { const b=document.querySelector('[data-nav=\"today\"]'); if(b) b.click(); }")
        pg.wait_for_timeout(900)
        chk('戒烟卡仍是双按钮（crave-smoke + crave-resist）',
            pg.locator('[data-act="crave-smoke"]').count() == 1
            and pg.locator('[data-act="crave-resist"]').count() == 1,
            'smoke=%d resist=%d' % (pg.locator('[data-act="crave-smoke"]').count(),
                                    pg.locator('[data-act="crave-resist"]').count()))

        chk('无 JS 异常', not errs, str(errs))
        ctx.close()
        br.close()


main()
print('----------------------------')
print('戒除单次/多次：%d 通过 / %d 失败' % (PASS, FAIL))
if FAILS:
    print('失败项：' + ' / '.join(FAILS))
if FAIL:
    sys.exit(1)
