# -*- coding: utf-8 -*-
"""今日页常驻卡自定义排序（v75）。

顺序存 state.cardOrder（id 数组）+ cardOrderAt（毫秒），跨设备靠 cardOrderAt
整份覆盖合并。交互是「排序模式 + ↑↓」，不做拖拽。
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
NAMES = ['用药', '喝水', '运动', '478呼吸法', '戒烟']


def chk(name, ok, detail=''):
    global PASS, FAIL
    if ok:
        PASS += 1
        print('  ✓ %s' % name)
    else:
        FAIL += 1
        FAILS.append(name)
        print('  ✗ %s  << %s' % (name, detail))


def order(pg):
    # 只看标题 .vital-title b：正文里会出现「完成运动」「戒烟」这类词，按全文匹配会认错卡。
    return pg.evaluate("""() => [...document.querySelectorAll('.vital-grid > *')].map(el => {
        const b = el.querySelector('.vital-title b');
        return b ? (b.textContent || '').trim() : '?';
    })""")


def move(pg, name, direction):
    """点某张卡的 ↑ / ↓。"""
    pg.evaluate("""([name, dir]) => {
        const card = [...document.querySelectorAll('.vital-grid > *')].find(el => {
            const b = el.querySelector('.vital-title b');
            return b && (b.textContent || '').trim() === name;
        });
        if (!card) return;
        const btn = card.querySelector('.card-sortbar [data-dir="' + dir + '"]');
        if (btn) btn.click();
    }""", [name, direction])
    pg.wait_for_timeout(500)


with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)
    ctx = br.new_context(viewport={'width': 1512, 'height': 950})
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)[:180]))
    pg.on('dialog', lambda d: d.accept())
    pg.clock.install(time=datetime(2026, 11, 9, 10, 0, 0))

    board['data'].pop('cardOrder', None)
    board['data'].pop('cardOrderAt', None)
    # 共享 mock 只给了 h_med / h_water 两个常驻 id，补齐另外三个，
    # 否则「5 张卡换位」这个核心场景根本测不到。
    have = set(h['id'] for h in board['data']['habits'])
    for hid, nm, col in (('h_move', '运动', '#b5733f'),
                         ('h_breathe', '478呼吸法', '#5b8f8a'),
                         ('h_drink', '戒烟', '#7a8471')):
        if hid not in have:
            board['data']['habits'].append(habit(hid, nm, 1, '次', pinned=True, color=col))

    pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
    pg.wait_for_timeout(500)
    if pg.locator('[data-act="cloud-login"]').count():
        pg.click('[data-act="cloud-login"]')
        pg.wait_for_timeout(400)
        pg.fill('input[name="email"]', 'test@sl00.top')
        pg.fill('input[name="password"]', 'test@sl00.top')
        pg.click('form.modal-card button[type="submit"]')
        pg.wait_for_timeout(2600)

    print('[1] 默认顺序')
    chk('五张常驻卡按默认顺序排', order(pg) == NAMES, str(order(pg)))
    chk('默认没有排序按钮', pg.locator('[data-act="card-move"]').count() == 0)
    chk('标题栏有「排序」入口', pg.locator('[data-act="card-sort"]').count() == 1)

    print('[2] 进入排序模式')
    pg.click('[data-act="card-sort"]')
    pg.wait_for_timeout(500)
    chk('每张卡都出现 ↑↓', pg.locator('.card-sortbar').count() == 5,
        str(pg.locator('.card-sortbar').count()))
    chk('第一张的 ↑ 是禁用的',
        pg.locator('.vital-grid > *').first.locator('[data-dir="-1"]').is_disabled())
    chk('最后一张的 ↓ 是禁用的',
        pg.locator('.vital-grid > *').last.locator('[data-dir="1"]').is_disabled())
    chk('「常驻」标签让位给排序条',
        pg.evaluate("() => { const t=document.querySelector('.vital-grid .pin-tag'); "
                    "return !t || getComputedStyle(t).display === 'none'; }"))
    chk('提示语换成「用 ↑↓ 调整顺序」',
        '↑↓' in (pg.locator('.sec-meta').text_content() or ''),
        pg.locator('.sec-meta').text_content() or '')

    print('[3] 排序时卡片内的按钮不响应')
    before = pg.evaluate("""() => {
        const el = [...document.querySelectorAll('.vital-grid > *')]
            .find(x => (x.textContent || '').indexOf('喝水') >= 0);
        const btn = el && el.querySelector('.vital-btn, .vital-actions button');
        return btn ? getComputedStyle(btn).pointerEvents : 'none-found';
    }""")
    chk('卡片内按钮 pointer-events 被关掉', before == 'none', before)

    print('[4] 把戒烟往上挪')
    move(pg, '戒烟', -1)
    o = order(pg)
    chk('戒烟从第 5 挪到第 4', o.index('戒烟') == 3, str(o))
    move(pg, '戒烟', -1)
    move(pg, '戒烟', -1)
    o = order(pg)
    chk('戒烟连点 3 次到第 2', o.index('戒烟') == 1, str(o))
    move(pg, '戒烟', -1)
    o = order(pg)
    chk('戒烟到第 1 位', o[0] == '戒烟', str(o))
    chk('其余四张相对顺序没变', o[1:] == ['用药', '喝水', '运动', '478呼吸法'], str(o))
    chk('第 1 张的 ↑ 现在禁用',
        pg.locator('.vital-grid > *').first.locator('[data-dir="-1"]').is_disabled())

    print('[5] 写进了 state，刷新后保持')
    # 云端推送有 600ms 防抖，等它真的写完再断言，否则读到的是推送前的服务端数据
    pg.wait_for_timeout(1200)
    saved = board['data']
    chk('服务端 state 里存了顺序', saved.get('cardOrder', [])[:1] == ['h_drink'],
        str(saved.get('cardOrder')))
    chk('state 里存了修改时刻', bool(saved.get('cardOrderAt')), str(saved.get('cardOrderAt')))
    chk('存的是完整五张的顺序', len(saved.get('cardOrder') or []) == 5,
        str(saved.get('cardOrder')))
    pg.reload(wait_until='networkidle')
    pg.wait_for_timeout(2400)
    chk('刷新后顺序不变', order(pg)[0] == '戒烟', str(order(pg)))
    chk('刷新后退出排序模式', pg.locator('.card-sortbar').count() == 0)

    print('[6] 恢复默认')
    pg.click('[data-act="card-sort"]')
    pg.wait_for_timeout(400)
    chk('排序态有「恢复默认」', pg.locator('[data-act="card-sort-reset"]').count() == 1)
    pg.click('[data-act="card-sort-reset"]')
    pg.wait_for_timeout(600)
    chk('顺序回到默认', order(pg) == NAMES, str(order(pg)))
    pg.wait_for_timeout(1200)   # 等这次重置推送完成，别和下一步改 board 抢

    print('[7] 脏数据容错：未知 id + 缺 id')
    board['data']['cardOrder'] = ['h_unknown', 'h_drink', 'h_drink']
    board['data']['cardOrderAt'] = 1
    pg.reload(wait_until='networkidle')
    pg.wait_for_timeout(2400)
    o = order(pg)
    chk('五张卡一张不少', len(o) == 5 and '?' not in o, str(o))
    chk('已知 id 按存的顺序提前', o[0] == '戒烟', str(o))
    # 之后动一下才会写回（回写的是 normalize 过的 state）
    pg.click('[data-act="card-sort"]')
    pg.wait_for_timeout(400)
    move(pg, '戒烟', 1)
    pg.wait_for_timeout(1000)
    chk('未知 id 在写回时被剔掉', 'h_unknown' not in (board['data'].get('cardOrder') or []),
        str(board['data'].get('cardOrder')))
    chk('重复 id 去重', len(board['data'].get('cardOrder') or []) == len(
        set(board['data'].get('cardOrder') or [])), str(board['data'].get('cardOrder')))

    print('[8] 换设备：远端更新则覆盖本地')
    # 本地存了一份把「用药」放到最后的顺序，但远端 cardOrderAt 更大
    board['data']['cardOrder'] = ['h_drink', 'h_med']
    board['data']['cardOrderAt'] = 9999999999999
    pg.evaluate("""() => {
        const s = JSON.parse(localStorage.getItem('lifeboard.v1') || '{}');
        s.cardOrder = ['h_water', 'h_move'];
        s.cardOrderAt = 1;
        localStorage.setItem('lifeboard.v1', JSON.stringify(s));
    }""")
    pg.reload(wait_until='networkidle')
    pg.wait_for_timeout(2600)
    o = order(pg)
    chk('远端较新的顺序胜出', o[0] == '戒烟' and o[1] == '用药', str(o))

    chk('无 JS 异常', not errs, str(errs))
    ctx.close()
    br.close()

print()
print('===== 常驻卡排序：%d 通过 / %d 失败 =====' % (PASS, FAIL))
if FAILS:
    print('失败项：', FAILS)
