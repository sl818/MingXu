# -*- coding: utf-8 -*-
"""v101：截止型习惯（早睡）

只对「保持 × 单次目标」生效：
  · 表单能填截止时刻，回填正确；目标 >1 或非保持类型时保存会清空
  · 卡片标题下显示「01:00 前」约束
  · 打卡后右上角状态位直接写完成时刻（23:10），不是笼统的「已完成」
  · 晚于截止时刻 → 状态标红 + title 说明晚多少分钟
  · 历史日期（补记）不显示时刻，避免拿「现在」冒充那天

用法：python e2e/verify-habit-deadline.py
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
        print('  \u2713 %s' % name)
    else:
        FAIL += 1
        FAILS.append(name)
        print('  \u2717 %s  << %s' % (name, detail))


# 注入一张截止型习惯（早睡：01:00 前）
board['data']['habits'].append({
    'id': 'h_early', 'name': '早睡', 'icon': '🌙', 'type': 'build',
    'target': 1, 'unit': '次', 'color': '#5b6f8a', 'note': '',
    'deadline': '01:00', 'createdAt': '2026-10-01T00:00:00Z', 'pinned': False,
})

PROBE = """() => {
  const el = [...document.querySelectorAll('.habit-card')].find(c => {
    const b = c.querySelector('.habit-title b');
    return b && (b.textContent || '').trim() === '早睡';
  });
  if (!el) return null;
  const st = el.querySelector('.habit-state');
  return {
    sub: (el.querySelector('.habit-title small') || {}).textContent || '',
    state: st ? (st.textContent || '').trim() : '',
    bad: st ? st.classList.contains('bad') : false,
    title: st ? (st.getAttribute('title') || '') : '',
    btn: (el.querySelector('.habit-done') || {}).textContent || ''
  };
}"""


def open_page(pg, when, w=1440):
    pg.set_viewport_size({'width': w, 'height': 950})
    pg.clock.install(time=when)
    pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
    pg.wait_for_timeout(500)
    pg.click('[data-act="cloud-login"]')
    pg.wait_for_timeout(400)
    pg.fill('input[name="email"]', 'test@example.com')
    pg.fill('input[name="password"]', 'test@example.com')
    pg.click('form.modal-card button[type="submit"]')
    pg.wait_for_timeout(2400)
    pg.evaluate("() => { const b=document.querySelector('[data-nav=\"today\"]'); if(b) b.click(); }")
    pg.wait_for_timeout(700)


with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)

    # ---------- 1. 未打卡：约束写在小字里，状态是待打卡 ----------
    ctx = br.new_context(viewport={'width': 1440, 'height': 950})
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)[:160]))
    open_page(pg, datetime(2026, 10, 25, 20, 0, 0))
    c = pg.evaluate(PROBE)
    chk('卡片渲染出来', bool(c), '找不到「早睡」卡')
    chk('标题下显示「01:00 前」', bool(c) and c['sub'].strip() == '01:00 前', c['sub'] if c else '')
    chk('未打卡状态是「待打卡」', bool(c) and c['state'] == '待打卡', c['state'] if c else '')
    chk('未打卡不标红', bool(c) and not c['bad'], str(c))

    # ---------- 2. 23:10 打卡：早于 01:00，状态写时刻、不超时 ----------
    pg.click('.habit-card:has(.habit-title b:text-is("早睡")) .habit-done')
    pg.wait_for_timeout(800)
    c = pg.evaluate(PROBE)
    chk('打卡后状态写完成时刻 20:00', bool(c) and c['state'] == '20:00', c['state'] if c else '')
    chk('早于截止时刻不标红', bool(c) and not c['bad'], str(c))
    chk('按钮进入已完成', bool(c) and '已完成' in c['btn'], c['btn'] if c else '')
    chk('无 JS 报错', not errs, str(errs[:2]))
    ctx.close()

    # ---------- 3. 01:40 打卡：晚 40 分钟，标红 + title ----------
    ctx = br.new_context(viewport={'width': 1440, 'height': 950})
    pg = ctx.new_page()
    # 用 10-26 的凌晨，避开上一段在 10-25 留下的打卡记录
    open_page(pg, datetime(2026, 10, 26, 1, 40, 0))
    pg.click('.habit-card:has(.habit-title b:text-is("早睡")) .habit-done')
    pg.wait_for_timeout(800)
    c = pg.evaluate(PROBE)
    chk('凌晨 01:40 打卡状态是 01:40', bool(c) and c['state'] == '01:40', c['state'] if c else '')
    chk('晚于截止时刻标红', bool(c) and c['bad'], str(c))
    chk('title 说明晚 40 分', bool(c) and '晚 40 分' in c['title'], c['title'] if c else '')

    # ---------- 4. 历史日期不显示时刻 ----------
    pg.evaluate("() => document.querySelector('[data-act=\"date-shift\"][data-delta=\"-1\"]').click()")
    pg.wait_for_timeout(700)
    c = pg.evaluate(PROBE)
    chk('历史日期不拿「现在」当时刻', bool(c) and c['state'] in ('待打卡', '已完成'), c['state'] if c else '')
    chk('历史日期不标红', bool(c) and not c['bad'], str(c))
    ctx.close()

    # ---------- 5. 表单回填 + 目标改多时清空 ----------
    ctx = br.new_context(viewport={'width': 1440, 'height': 950})
    pg = ctx.new_page()
    open_page(pg, datetime(2026, 10, 25, 20, 0, 0))
    pg.evaluate("() => { const b=document.querySelector('[data-nav=\"habits\"]'); if(b) b.click(); }")
    pg.wait_for_timeout(700)
    pg.click('[data-act="habit-edit"][data-id="h_early"]')
    pg.wait_for_timeout(600)
    val = pg.evaluate("() => { const el=document.querySelector('#habit-form input[name=\"deadline\"]'); return el ? el.value : 'MISSING'; }")
    chk('表单回填截止时刻 01:00', val == '01:00', val)
    pg.fill('#habit-form input[name="target"]', '3')
    pg.click('#habit-form button[type="submit"]')
    pg.wait_for_timeout(1600)
    saved = [h for h in board['data']['habits'] if h.get('id') == 'h_early']
    chk('目标改成 3 后 deadline 被清空', bool(saved) and not saved[0].get('deadline'), str(saved[:1]))
    chk('目标确实存成 3', bool(saved) and int(saved[0].get('target') or 0) == 3, str(saved[:1]))
    ctx.close()

    br.close()

print('\nv101 截止型习惯验证：%d/%d 通过' % (PASS, PASS + FAIL))
if FAIL:
    print('失败项：' + ', '.join(FAILS))
    sys.exit(1)
