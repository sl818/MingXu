# -*- coding: utf-8 -*-
"""导入备份不能丢字段（v78 事故回归）

背景：导入走 repairBackup()，它以前是「白名单」，只返回 14 个字段。
v68 之后陆续加的 cravings / packs / notices / cardOrder / countdowns 没同步进去，
导入时被静默丢弃，紧接着 save() 把残缺的 state 推上云端，用户的抽烟、买烟、
自定义通知、倒数日全部消失。

这组用例锁三件事：
  1. 已知的新字段导入后还在，条数一致；
  2. 白名单里从没出现过的字段（模拟将来新增）也原样带过；
  3. 导入结果真的写回服务端，不只是内存里看着对。
"""
import io
import json
import os
import sys
import tempfile
from datetime import datetime

ROOT = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo'
head = io.open(os.path.join(ROOT, 'e2e', 'verify-batch4.py'), encoding='utf-8').read()
head = head.split('with sync_playwright() as p:')[0]
sys.argv = [sys.argv[0]]
exec(head)

from playwright.sync_api import sync_playwright

PASS = 0
FAIL = 0


def chk(name, cond, extra=''):
    global PASS, FAIL
    if cond:
        PASS += 1
        print('  OK   ' + name)
    else:
        FAIL += 1
        print('  FAIL ' + name + ('   [' + str(extra) + ']' if extra else ''))


NOW = datetime(2026, 11, 10, 14, 0, 0)

# 待导入的备份：每类都给几条，条数写死，好断言
BACKUP = {
    'version': 2,
    'schemaVersion': 6,
    'view': 'settings',
    'habits': [],
    'checks': {},
    'notes': {},
    'moods': {},
    'events': [],
    'meds': [],
    'doses': {},
    'tasks': [],
    'bodyProfile': {'age': 30, 'height': 175},
    'weights': [],
    'essays': [],
    # ↓ 这六项是 v78 之前会被吃掉的
    'cravings': [
        {'id': 'cq%d' % i, 't': 1762000000 + i * 600, 'k': 's', 'h': 'h_drink', 'g': '', 's': 0}
        for i in range(12)
    ],
    'packs': [
        {'id': 'pk1', 'at': 1762000000, 'name': '普皖', 'price': 15, 'size': 20, 'cf': 0},
        {'id': 'pk2', 'at': 1762100000, 'name': '利群', 'price': 18, 'size': 20, 'cf': 0},
    ],
    'notices': [
        {'id': 'n1', 'text': '该吃维生素了', 'time': '20:00', 'mode': 'daily',
         'date': '', 'weeks': [], 'monthday': 1, 'on': True},
        {'id': 'n2', 'text': '周复盘', 'time': '21:30', 'mode': 'weekly',
         'date': '', 'weeks': [1, 4], 'monthday': 1, 'on': True},
    ],
    'countdowns': [
        {'id': 'cd1', 'title': '考研初试', 'date': '2026-12-20', 'note': '打印准考证',
         'time': '09:00', 'remindDays': [3, 1, 0], 'on': True},
    ],
    'cardOrder': ['h_drink', 'h_med'],
    'cardOrderAt': 1794225546519,
    'navOrder': ['settings', 'today'],          # v86 导航顺序也要能过导入
    'navOrderAt': 1794225546519,
    'money': {'debts': [{'id': 'md1', 'name': '房贷', 'balance': 5000, 'start': 5000,
                         'apr': 4, 'min': 200, 'due': 8, 'type': 'other', 'u': 1}],
              'extra': 300, 'strategy': 'avalanche'},
    'moneyAt': 1794225546519,
    # 模拟「将来又加了一个顶层字段」——白名单不认识，也必须原样带过
    'futureField': {'hello': 'world'},
}


def main():
    tmp = os.path.join(tempfile.gettempdir(), '_lb_import_test.json')
    io.open(tmp, 'w', encoding='utf-8', newline='').write(
        json.dumps(BACKUP, ensure_ascii=False))

    with sync_playwright() as p:
        br = p.chromium.launch(channel='chrome', headless=True)
        ctx = br.new_context(viewport={'width': 1512, 'height': 950})
        pg = ctx.new_page()
        errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)[:160]))
        pg.on('dialog', lambda d: d.accept())
        pg.clock.install(time=NOW)

        pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
        pg.wait_for_timeout(600)
        if pg.locator('[data-act="cloud-login"]').count():
            pg.click('[data-act="cloud-login"]')
            pg.wait_for_timeout(400)
            pg.fill('input[name="email"]', 'test@sl00.top')
            pg.fill('input[name="password"]', 'test@sl00.top')
            pg.click('form.modal-card button[type="submit"]')
            pg.wait_for_timeout(2600)

        print('[1] 走一次导入')
        # 共享 mock 里这几个字段本来就是空的，正好能看出导入是不是真把它们带进来了
        chk('导入前这些字段是空的', not board['data'].get('cravings')
            and not board['data'].get('countdowns'),
            'cravings=%s countdowns=%s' % (len(board['data'].get('cravings') or []),
                                           len(board['data'].get('countdowns') or [])))

        pg.set_input_files('#import-file', tmp)
        pg.wait_for_timeout(2600)          # 导入 + save() 600ms 防抖 + 推送

        print('[2] 导入结果写回了服务端')
        pg.wait_for_timeout(1200)
        sv = board['data']
        chk('服务端 cravings 12 条', len(sv.get('cravings') or []) == 12,
            str(len(sv.get('cravings') or [])))
        chk('服务端 packs 2 条', len(sv.get('packs') or []) == 2,
            str(len(sv.get('packs') or [])))
        chk('服务端 notices 2 条', len(sv.get('notices') or []) == 2,
            str(len(sv.get('notices') or [])))
        chk('服务端 countdowns 1 条', len(sv.get('countdowns') or []) == 1,
            str(len(sv.get('countdowns') or [])))
        chk('服务端 cardOrder 保留', (sv.get('cardOrder') or [])[:2] == ['h_drink', 'h_med'],
            str(sv.get('cardOrder')))
        chk('服务端 navOrder 保留', (sv.get('navOrder') or [])[:2] == ['settings', 'today'],
            str(sv.get('navOrder')))
        chk('服务端 money 保留', (sv.get('money') or {}).get('extra') == 300,
            str((sv.get('money') or {}).get('extra')))
        chk('服务端陌生字段保留', (sv.get('futureField') or {}).get('hello') == 'world',
            str(sv.get('futureField')))

        print('[3] 刷新后仍然在（不是只改了内存）')
        pg.reload(wait_until='networkidle')
        pg.wait_for_timeout(2600)
        sv2 = board['data']
        chk('刷新后服务端抽烟记录仍是 12 条', len(sv2.get('cravings') or []) == 12,
            str(len(sv2.get('cravings') or [])))
        chk('刷新后服务端倒数日仍是 1 条', len(sv2.get('countdowns') or []) == 1,
            str(len(sv2.get('countdowns') or [])))
        chk('刷新后服务端通知仍是 2 条', len(sv2.get('notices') or []) == 2,
            str(len(sv2.get('notices') or [])))

        print('[4] 界面能正常渲染')
        pg.evaluate("() => { const b=document.querySelector('[data-nav=\"config\"]'); if(b) b.click(); }")
        pg.wait_for_timeout(1200)
        chk('配置页列出两条通知', pg.locator('.notice-row').count() == 2,
            str(pg.locator('.notice-row').count()))
        pg.evaluate("() => { const b=document.querySelector('[data-nav=\"calendar\"]'); if(b) b.click(); }")
        pg.wait_for_timeout(1000)
        chk('日历页倒数日渲染出来了', pg.locator('.cd-item').count() >= 1,
            str(pg.locator('.cd-item').count()))
        chk('无 JS 异常', not errs, str(errs))

        ctx.close()
        br.close()

    try:
        os.remove(tmp)
    except OSError:
        pass


main()
print('----------------------------')
print('通过 %d 项，失败 %d 项' % (PASS, FAIL))
if FAIL:
    sys.exit(1)
