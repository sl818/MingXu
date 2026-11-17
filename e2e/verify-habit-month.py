# -*- coding: utf-8 -*-
"""习惯页「本月概览」（v109，需求四）

口径（写死在 habitDueOn / habitMonthOverview 里，这里逐条锁）：
  · 达标 = met(h,d)，和今日/日历/统计同一个判定
  · 应打卡 = 按 notifyFreq 逐日判断（daily 每天 / weekly 每周那一天 / monthly 每月那一天）
  · 排名只让「本月应打卡 ≥5 次」的参与，按达标率排，同率看天数
  · 「从未完成」= 本月 0 天达标；「最低」只从「至少达标过一天」里挑，两栏不重复
  · 周日的 notifyWeekday 是 0，不能被 `|| 1` 当成周一（v109 修的老坑）
  · 用药当天没有排期就不计入应打卡
"""
import os
import sys
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


TODAY = datetime(2026, 10, 25)


def dstr(d):
    return d.strftime('%Y-%m-%d')


BASE = {'type': 'build', 'target': 1, 'unit': '次', 'note': '', 'notifyFreq': 'daily',
        'createdAt': '2026-07-01T08:00:00Z'}


def habit(hid, name, **kw):
    h = dict(BASE)
    h.update({'id': hid, 'name': name, 'icon': '📌', 'color': '#6b5b8e'})
    h.update(kw)
    return h


def build(with_med=False):
    """A 全勤 25/25 · B 隔天 13/25 · C 每周日 4/4 · D 从未完成 0/25
       E 上月有、本月无 —— 用来测环比。"""
    habits = [
        habit('h_a', '全勤习惯'),
        habit('h_b', '隔天习惯'),
        habit('h_c', '每周日', notifyFreq='weekly', notifyWeekday=0),
        habit('h_d', '从没做'),
        habit('h_e', '月度一次', notifyFreq='monthly', notifyMonthday=28),
        # ensureBreathingHabit 会保证这条一定存在（常驻呼吸卡）；
        # 这里显式给出来，数值才可控——否则它会是「本月 0 天」的意外成员。
        habit('h_breathe', '478呼吸法', unit='组', breatheCycles=4, pinned=True),
    ]
    checks = {}
    # 本月：A 每天达标；B 每隔一天；C 只在周日；D 一次不做；E 本月没到日子
    for i in range(0, 26):
        d = TODAY - timedelta(days=i)
        day = {}
        if i <= 24:
            day['h_a'] = 1
            if i % 2 == 0:
                day['h_b'] = 1
            if d.weekday() == 6:
                day['h_c'] = 1
            if i % 5 == 0:
                day['h_breathe'] = 1
        checks[dstr(d)] = day
    # 上月同期（9/1–9/25）：A 全勤、B 全勤，凑出「上月 50 天」
    for i in range(26, 60):
        d = TODAY - timedelta(days=i)
        if 9 <= d.day <= 25:
            checks[dstr(d)] = {'h_a': 1, 'h_b': 1}
        else:
            checks[dstr(d)] = {}
    board['data']['habits'] = habits
    board['data']['checks'] = checks
    board['data']['doses'] = {}
    board['data']['meds'] = []
    if with_med:
        board['data']['habits'].append(
            habit('h_med', '用药', med=True, target=2))
        board['data']['meds'] = [{
            'id': 'm1', 'name': '阿莫西林', 'purpose': '消炎', 'form': '粒', 'strength': '0.25g',
            'doseAmount': 1, 'doseUnit': '粒', 'times': ['08:00'], 'courseType': 'long',
            'startDate': '2026-07-01', 'endDate': '', 'reviewDate': '', 'status': 'active',
            'stock': '60', 'note': '',
        }]


SUM = """() => {
  const s = document.querySelector('.hsum');
  if (!s) return {on: false};
  const kpi = [...s.querySelectorAll('.hs-k')].map(function (e) {
    return {
      label: (e.querySelector('small') || {}).textContent || '',
      big: (e.querySelector('b') || {}).textContent.replace(/\\s+/g, ' ').trim(),
      sub: (e.querySelector('.hs-long') || e.querySelector('span') || {}).textContent || ''
    };
  });
  const list = [...s.querySelectorAll('.hs-l')].map(function (e) {
    return {
      label: (e.querySelector('small') || {}).textContent || '',
      name: (e.querySelector('b') || {}).textContent || '',
      sub: (e.querySelector('span') || {}).textContent || ''
    };
  });
  return {
    on: true,
    range: (s.querySelector('.hsum-range') || {}).textContent || '',
    kpi: kpi, list: list,
    cols: getComputedStyle(s.querySelector('.hsum-kpi')).gridTemplateColumns,
    ovf: document.documentElement.scrollWidth - document.documentElement.clientWidth
  };
}"""


def open_habits(br, w=1440, h=1000):
    ctx = br.new_context(viewport={'width': w, 'height': h})
    pg = ctx.new_page()
    pg.clock.install(time=datetime(2026, 10, 25, 10, 0, 0))
    pg.add_init_script("try{localStorage.setItem('lifeboard.theme.mode','light');}catch(e){}")
    pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
    pg.wait_for_timeout(500)
    if pg.locator('[data-act="cloud-login"]').count():
        pg.click('[data-act="cloud-login"]')
        pg.wait_for_timeout(500)
        pg.fill('input[name="email"]', 'test@example.com')
        pg.fill('input[name="password"]', 'test@example.com')
        pg.click('form.modal-card button[type="submit"]')
        pg.wait_for_timeout(2600)
    pg.evaluate("() => { const b = document.querySelector('[data-nav=\"habits\"]'); if (b) b.click(); }")
    pg.wait_for_timeout(900)
    return ctx, pg


def main():
    build(False)
    with sync_playwright() as p:
        br = p.chromium.launch(channel='chrome', headless=True)

        # ---------- 1. 结构与数值 ----------
        print('\n[1] 本月概览的结构与数值')
        ctx, pg = open_habits(br)
        d = pg.evaluate(SUM)
        chk('习惯页顶部有「本月概览」', d.get('on'), '')
        chk('三张 KPI 卡', len(d['kpi']) == 3, str(len(d['kpi'])))
        chk('KPI 标题正确',
            [k['label'] for k in d['kpi']] == ['达标总天数', '平均达标率', '比上月同期'],
            str([k['label'] for k in d['kpi']]))
        k0, k1, k2 = d['kpi']
        # A 25 + B 13 + C 4 + D 0 + 呼吸 5 = 47（「月度一次」本月 28 号还没到，due=0 不参与）
        chk('达标总天数 = 47', k0['big'].startswith('47'), k0['big'])
        chk('应打卡写明 104 天（25+25+4+25+25）', '104' in k0['sub'], k0['sub'])
        # 47 / 104 = 45%
        chk('平均达标率 = 45%', k1['big'].startswith('45'), k1['big'])
        # 上月 mock 只在 9/9–9/25 给了记录：A、B 各 17 天 = 34；本月 47 → ↑13
        chk('比上月同期是上升（47 vs 34）', '↑' in k2['big'] and '13' in k2['big'], k2['big'])
        chk('环比小字写明上月同期 34', '34' in k2['sub'], k2['sub'])

        chk('三个点名项', len(d['list']) == 3, str(len(d['list'])))
        by = {x['label']: x for x in d['list']}
        chk('最高是「全勤习惯」', by['达标最高']['name'] == '全勤习惯', by['达标最高']['name'])
        chk('最高给出天数与达标率',
            '25 天' in by['达标最高']['sub'] and '100%' in by['达标最高']['sub'],
            by['达标最高']['sub'])
        chk('最低是「478呼吸法」（5 天 / 20%）', by['达标最低']['name'] == '478呼吸法',
            by['达标最低']['name'])
        chk('最低的小字给出天数与率',
            '5 天' in by['达标最低']['sub'] and '20%' in by['达标最低']['sub'], by['达标最低']['sub'])
        chk('最低不含 0 天的（0 天归「从未完成」）',
            '从没做' not in by['达标最低']['name'], by['达标最低']['name'])
        chk('从未完成是「从没做」', by['从未完成']['name'] == '从没做', by['从未完成']['name'])
        chk('从未完成写明本月 0 天', '本月 0 天' in by['从未完成']['sub'], by['从未完成']['sub'])
        chk('「每周日」4 次不在排名里（应打卡 <5）',
            '每周日' not in (by['达标最高']['name'] + by['达标最低']['name']), '')

        # ---------- 2. 周日不能被当成周一 ----------
        print('\n[2] 周日（notifyWeekday = 0）')
        # 若 0 被 `|| 1` 吞掉，C 会按周一算：10 月有 4 个周一（5/12/19/26，25 号前 3 个）
        # 但 mock 只在周日给了记录 → 达标会变成 0 次，掉进「从未完成」
        never = by['从未完成']['name']
        chk('周日习惯没有掉进「从未完成」', '每周日' not in never, never)
        chk('周日习惯计入应打卡（总数 104 含它的 4 天）', '104' in k0['sub'], k0['sub'])
        ctx.close()

        # ---------- 3. 用药：有排期才参与 ----------
        print('\n[3] 用药习惯')
        build(True)
        ctx, pg = open_habits(br)
        d2 = pg.evaluate(SUM)
        chk('有排期时参与统计（5 项 → 6 项）', '6 项' in d2['range'], d2['range'])
        chk('标注「含用药」', '含用药' in d2['range'], d2['range'])
        ctx.close()

        # 用药没排期（清空 meds）：应打卡为 0 → 不参与
        board['data']['meds'] = []
        ctx, pg = open_habits(br)
        d3 = pg.evaluate(SUM)
        chk('没有排期时不参与（回到 5 项且不标含用药）',
            '5 项' in d3['range'] and '含用药' not in d3['range'], d3['range'])
        ctx.close()

        # ---------- 4. 归档习惯不计入 ----------
        print('\n[4] 归档习惯')
        build(False)
        board['data']['habits'][0]['archivedAt'] = '2026-10-01T00:00:00Z'
        ctx, pg = open_habits(br)
        d4 = pg.evaluate(SUM)
        chk('归档的不参与（5 项 → 4 项）', '4 项' in d4['range'], d4['range'])
        chk('归档的不出现在排名里',
            '全勤习惯' not in (d4['list'][0]['name'] + d4['list'][1]['name']), str(d4['list']))
        ctx.close()

        # ---------- 5. 只剩常驻呼吸卡 ----------
        print('\n[5] 清空习惯之后')
        board['data']['habits'] = []
        board['data']['checks'] = {}   # 打卡记录也要清，否则呼吸法仍有本月数据
        ctx, pg = open_habits(br)
        d5 = pg.evaluate(SUM)
        # ensureBreathingHabit 会把「478呼吸法」补回来（常驻卡，删不掉），
        # 所以这里不是空态：概览只剩它一项，而且本月一次没做 → 归到「从未完成」。
        chk('只剩呼吸法时概览只算 1 项', '1 项' in d5.get('range', ''), d5.get('range', ''))
        chk('呼吸法落进「从未完成」',
            d5.get('on') and '478' in d5['list'][2]['name'], str(d5.get('list')))
        chk('习惯页本身还在', '我的习惯' in pg.evaluate("() => document.querySelector('#main').textContent"))
        ctx.close()

        # ---------- 6. 手机端 ----------
        print('\n[6] 手机端')
        build(False)
        for w in (390, 360):
            ctx, pg = open_habits(br, w=w, h=844)
            d6 = pg.evaluate(SUM)
            chk('[%d] 三个数字卡仍是三列' % w,
                len(d6['cols'].split()) == 3, d6['cols'])
            chk('[%d] 无横向溢出' % w, d6['ovf'] <= 0, '%dpx' % d6['ovf'])
            subs = pg.evaluate(
                "() => [...document.querySelectorAll('.hs-k .hs-short')]"
                ".filter(e => getComputedStyle(e).display !== 'none')"
                ".map(e => Math.round(e.getBoundingClientRect().height))")
            chk('[%d] 窄屏用短文案且都在一行内' % w, subs and all(h <= 15 for h in subs), str(subs))
            ctx.close()

        br.close()

    print('\n' + '=' * 56)
    print('习惯页本月概览 v109：%d 通过 / %d 失败' % (PASS, FAIL))
    if FAILS:
        print('失败项：')
        for f in FAILS:
            print('  -', f)
    return 0 if FAIL == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
