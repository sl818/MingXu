# -*- coding: utf-8 -*-
"""v80：月度小结的「完成度」口径 + 任务完成度面板

两件事：
1. 月度小结里习惯那一列以前是「达标天数 ÷ 天数」的二元口径，喝水目标 9 杯、
   实际每天 3 杯 → 0%，跟一口没喝同分。改成按实际完成量折算（3/9 = 33%）。
   戒除类和目标 1 次的结果必须和以前完全一样。
2. 待办页底部 / 统计页各一块「任务完成度」：新增 / 待办 / 进行中 / 已完成 / 已取消
   + 达成率，支持近 7 天 / 近 1 月 / 近 3 月 / 全部。
   达成率 = 完成 ÷ 新增（取消也算在分母里）。
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


NOW = datetime(2026, 11, 10, 15, 0, 0)


def task(tid, status, created):
    return {'id': tid, 'title': tid, 'note': '', 'tag': '工作', 'priority': '中',
            'status': status, 'due': '', 'createdAt': created,
            'doneAt': ('2026-11-08T10:00:00Z' if status == 'done' else None),
            'archivedAt': ''}


# 近 7 天（11-04 起）12 条：7 完成 / 2 取消 / 2 进行中 / 1 待办
TASKS = []
for i in range(7):
    TASKS.append(task('n_d%d' % i, 'done', '2026-11-0%dT09:00:00Z' % (4 + (i % 6))))
for i in range(2):
    TASKS.append(task('n_c%d' % i, 'cancelled', '2026-11-05T09:00:00Z'))
for i in range(2):
    TASKS.append(task('n_g%d' % i, 'doing', '2026-11-06T09:00:00Z'))
TASKS.append(task('n_t0', 'todo', '2026-11-09T09:00:00Z'))
# 10 月的 6 条：只在「近 1 月 / 3 月 / 全部」里
for i in range(3):
    TASKS.append(task('o_d%d' % i, 'done', '2026-10-2%dT09:00:00Z' % i))
for i in range(2):
    TASKS.append(task('o_c%d' % i, 'cancelled', '2026-10-18T09:00:00Z'))
TASKS.append(task('o_t0', 'todo', '2026-10-15T09:00:00Z'))
# 9 月的一条：只有「全部」看得到（近 1 月 / 近 3 月都够不到它）
TASKS.append(task('e_d0', 'done', '2026-09-01T09:00:00Z'))
# 2 条归档（均为近 7 天内创建）
TASKS[0]['archivedAt'] = '2026-11-09T09:00:00Z'
TASKS[10]['archivedAt'] = '2026-11-09T09:00:00Z'

HABITS = [
    {'id': 'h_water', 'name': '喝水', 'icon': '💧', 'type': 'build', 'target': 9, 'unit': '杯',
     'color': '#4c7f96', 'note': '', 'createdAt': '2026-10-01T08:00:00Z', 'pinned': True, 'med': False},
    {'id': 'h_run', 'name': '运动', 'icon': '🏃', 'type': 'build', 'target': 1, 'unit': '次',
     'color': '#b5733f', 'note': '', 'createdAt': '2026-10-01T08:00:00Z', 'pinned': True, 'med': False},
    {'id': 'h_q1', 'name': '不喝碳酸饮料', 'icon': '🚫', 'type': 'quit', 'target': 1, 'unit': '次',
     'color': '#8a6fa8', 'note': '', 'createdAt': '2026-10-01T08:00:00Z', 'pinned': False,
     'med': False, 'quitStart': '2026-10-01'},
    {'id': 'h_q2', 'name': '移动签到', 'icon': '📱', 'type': 'build', 'target': 1, 'unit': '次',
     'color': '#2f7d5c', 'note': '', 'createdAt': '2026-10-01T08:00:00Z', 'pinned': False, 'med': False},
]
# 喝水每天 3 杯（目标 9）；签到每天做到；戒烟 11-03 破了一次
CHECKS = {}
for d in range(1, 11):
    CHECKS['2026-11-%02d' % d] = {'h_water': 3, 'h_q2': 1}
CRAV = [{'id': 'q1', 't': int(datetime(2026, 11, 3, 20, 0).timestamp()),
         'k': 's', 'h': 'h_q1', 'g': '', 's': 0}]


def seed():
    board['data']['tasks'] = [dict(x) for x in TASKS]
    board['data']['habits'] = [dict(x) for x in HABITS]
    board['data']['checks'] = dict(CHECKS)
    board['data']['cravings'] = [dict(x) for x in CRAV]
    board['data']['meds'] = []


def go(pg, key):
    pg.evaluate("(k) => { const b=document.querySelector('[data-nav=\"'+k+'\"]'); if(b) b.click(); }", key)
    pg.wait_for_timeout(900)


def stats(pg):
    """读任务面板上的五格数字、达成率、小字。"""
    return pg.evaluate("""() => {
        const el = document.querySelector('.task-stat');
        if (!el) return null;
        const cells = [...el.querySelectorAll('.ts-cell')].map(c => ({
            label: (c.querySelector('span') || {}).textContent || '',
            n: Number(((c.querySelector('b') || {}).textContent || '0').trim())
        }));
        const on = el.querySelector('.ts-chip.on');
        return {
            cells: cells,
            range: on ? on.textContent.trim() : '',
            rate: (el.querySelector('.ts-rate span') || {}).textContent || '',
            note: (el.querySelector('.ts-note') || {}).textContent || '',
            chips: [...el.querySelectorAll('.ts-chip')].map(c => c.textContent.trim())
        };
    }""")


def by_label(st, name):
    for c in st['cells']:
        if c['label'] == name:
            return c['n']
    return None


def main():
    with sync_playwright() as p:
        br = p.chromium.launch(channel='chrome', headless=True)
        ctx = br.new_context(viewport={'width': 1512, 'height': 1200})
        pg = ctx.new_page()
        errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)[:160]))
        pg.clock.install(time=NOW)
        seed()

        pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
        pg.wait_for_timeout(500)
        if pg.locator('[data-act="cloud-login"]').count():
            pg.click('[data-act="cloud-login"]')
            pg.wait_for_timeout(400)
            pg.fill('input[name="email"]', 'test@example.com')
            pg.fill('input[name="password"]', 'test@example.com')
            pg.click('form.modal-card button[type="submit"]')
            pg.wait_for_timeout(2600)

        # ---------------- 任务面板：待办页 ----------------
        print('[1] 待办页底部的任务完成度')
        go(pg, 'board')
        st = stats(pg)
        chk('面板存在', bool(st), str(st))
        chk('默认范围是近 1 月', st['range'] == '近 1 月', st['range'])
        chk('四个范围按钮齐全', st['chips'] == ['近 7 天', '近 1 月', '近 3 月', '全部'], str(st['chips']))
        chk('五格标签齐全',
            [c['label'] for c in st['cells']] == ['新增', '待办', '进行中', '已完成', '已取消'],
            str([c['label'] for c in st['cells']]))

        n = by_label(st, '新增')
        chk('近 1 月新增 18 条（12 条 11 月 + 6 条 10 月）', n == 18, str(n))
        chk('已完成 10 条', by_label(st, '已完成') == 10, str(by_label(st, '已完成')))
        chk('已取消 4 条', by_label(st, '已取消') == 4, str(by_label(st, '已取消')))
        chk('进行中 2 条', by_label(st, '进行中') == 2, str(by_label(st, '进行中')))
        chk('待办 2 条', by_label(st, '待办') == 2, str(by_label(st, '待办')))
        chk('四格加起来等于新增',
            by_label(st, '待办') + by_label(st, '进行中') + by_label(st, '已完成')
            + by_label(st, '已取消') == n, str(st['cells']))
        chk('达成率 = 完成 ÷ 新增 = 56%', '56%' in st['rate'], st['rate'])
        chk('小字写明 10 / 18 条已完成', '10 / 18' in st['note'], st['note'])
        chk('小字写明其中 2 条已归档', '2 条已归档' in st['note'], st['note'])

        print('[2] 切到近 7 天：10 月的 6 条被排除')
        pg.click('.ts-chip[data-v="7"]')
        pg.wait_for_timeout(700)
        st = stats(pg)
        chk('范围按钮切到近 7 天', st['range'] == '近 7 天', st['range'])
        chk('新增变成 12 条', by_label(st, '新增') == 12, str(by_label(st, '新增')))
        chk('已完成变成 7 条', by_label(st, '已完成') == 7, str(by_label(st, '已完成')))
        chk('达成率 7/12 = 58%', '58%' in st['rate'], st['rate'])

        print('[3] 切到全部：9 月那条也进来了')
        pg.click('.ts-chip[data-v="0"]')
        pg.wait_for_timeout(700)
        st = stats(pg)
        chk('范围切到全部', st['range'] == '全部', st['range'])
        chk('新增 19 条（比近 1 月多那条 9 月的）', by_label(st, '新增') == 19, str(by_label(st, '新增')))
        chk('已完成 11 条', by_label(st, '已完成') == 11, str(by_label(st, '已完成')))

        print('[4] 统计页不再重复整块面板，改成总览里的一行摘要（v85）')
        go(pg, 'stats')
        st2 = stats(pg)
        chk('统计页没有重复的任务完成度面板', st2 is None, str(st2))
        chk('统计页也没有「任务概览」残留',
            pg.locator('.cal-summary').count() == 0,
            'cal-summary=%d' % pg.locator('.cal-summary').count())

        tk = pg.evaluate("""() => {
            const cells = [...document.querySelectorAll('.tk-grid .rv-cell')].map(c => ({
                label: (c.querySelector('small') || {}).textContent || '',
                big: (c.querySelector('b') || {}).textContent || ''
            }));
            const bar = document.querySelector('.tk-bar');
            const fill = bar && bar.querySelector('i');
            const btn = document.querySelector('[data-act="more-go"][data-view="board"]');
            return {
                cells: cells,
                ratio: bar && fill ? Math.round(fill.getBoundingClientRect().width /
                    bar.getBoundingClientRect().width * 100) : -1,
                btn: btn ? btn.textContent.trim() : ''
            };
        }""")
        chk('总览里有任务摘要三格',
            [c['label'] for c in tk['cells']] == ['新增', '已完成', '达成率'], str(tk['cells']))
        num = lambda c: int(''.join(ch for ch in c['big'] if ch.isdigit()) or 0)
        chk('摘要的「新增」与待办页一致', num(tk['cells'][0]) == by_label(st, '新增'),
            '%s vs %s' % (tk['cells'][0]['big'], by_label(st, '新增')))
        chk('摘要的「已完成」与待办页一致', num(tk['cells'][1]) == by_label(st, '已完成'),
            '%s vs %s' % (tk['cells'][1]['big'], by_label(st, '已完成')))
        chk('摘要的达成率与待办页一致', tk['cells'][2]['big'].strip() == st['rate'].split(' ')[-1].strip()
            or tk['cells'][2]['big'].strip() in st['rate'],
            '%s vs %s' % (tk['cells'][2]['big'], st['rate']))
        chk('细进度条宽度 = 达成率 ±2', abs(tk['ratio'] - int(tk['cells'][2]['big'].replace('%', ''))) <= 2,
            '条 %d%% vs 数字 %s' % (tk['ratio'], tk['cells'][2]['big']))
        chk('有「看待办」跳转按钮', tk['btn'] == '看待办', tk['btn'])

        # ---------------- 月度小结 ----------------
        print('[5] 月度小结：计数类按完成量折算')
        pg.click('[data-act="month-summary"]')
        pg.wait_for_timeout(800)
        rows = pg.evaluate("""() => {
            const tables = [...document.querySelectorAll('.modal-card .sum-table')];
            const t = tables[tables.length - 1];
            if (!t) return null;
            const head = [...t.querySelectorAll('th')].map(x => (x.textContent || '').trim());
            const body = [...t.querySelectorAll('tr')].slice(1).map(tr =>
                [...tr.querySelectorAll('td')].map(td => (td.textContent || '').trim()));
            return { head: head, body: body };
        }""")
        chk('表头是「达标天数 / 完成度」',
            rows and rows['head'] == ['习惯', '达标天数', '完成度'], str(rows['head'] if rows else None))
        m = {r[0]: r for r in rows['body']} if rows else {}
        chk('喝水：达标 0 天，完成度 33%（不是 0）',
            '喝水' in m and m['喝水'][1] == '0 / 10' and m['喝水'][2] == '33%',
            str(m.get('喝水')))
        chk('运动：真的没做，仍是 0%',
            '运动' in m and m['运动'][2] == '0%', str(m.get('运动')))
        chk('戒除类不变：9 / 10 天、90%',
            '不喝碳酸饮料' in m and m['不喝碳酸饮料'][1] == '9 / 10'
            and m['不喝碳酸饮料'][2] == '90%', str(m.get('不喝碳酸饮料')))
        chk('目标 1 次的保持类不变：100%',
            '移动签到' in m and m['移动签到'][2] == '100%', str(m.get('移动签到')))

        txt = pg.locator('.modal-card').text_content() or ''
        chk('表格下方有口径说明', '按实际完成量折算' in txt, txt[-400:])
        chk('记录情况用「完成度」而不是「完成率」',
            '平均完成度' in txt and '平均完成率' not in txt, txt[-300:])

        pg.click('[data-act="close-modal"]')
        pg.wait_for_timeout(400)

        chk('无 JS 异常', not errs, str(errs))
        ctx.close()
        br.close()


main()
print('----------------------------')
print('v80 统计口径：%d 通过 / %d 失败' % (PASS, FAIL))
if FAILS:
    print('失败项：' + ' / '.join(FAILS))
if FAIL:
    sys.exit(1)
