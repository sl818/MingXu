# -*- coding: utf-8 -*-
"""v170 拆分冒烟：健康模块独立页 / 导航 / 模块设置表单 / 迁移 / 统计单列。"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
head = open(os.path.join(ROOT, 'e2e', 'verify-batch4.py'), encoding='utf-8').read().split('with sync_playwright() as p:')[0]
sys.argv = [sys.argv[0]]
exec(head)

PASS = FAIL = 0
FAILS = []


def chk(name, ok, detail=''):
    global PASS, FAIL
    if ok:
        PASS += 1
        print('  ✓ %s' % name)
    else:
        FAIL += 1
        FAILS.append((name, detail))
        print('  ✗ %s  << %s' % (name, detail))


def login(pg):
    pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
    pg.wait_for_timeout(500)
    if pg.locator('[data-act="cloud-login"]').count() == 0:
        pg.wait_for_timeout(2400)
        return
    pg.click('[data-act="cloud-login"]')
    pg.wait_for_timeout(400)
    pg.fill('input[name="email"]', 'test@example.com')
    pg.fill('input[name="password"]', 'test@example.com')
    pg.click('form.modal-card button[type="submit"]')
    pg.wait_for_timeout(2600)


def nav(pg, v):
    pg.evaluate("v => { const b=document.querySelector('[data-nav=\"'+v+'\"]'); if(b) b.click(); }", v)
    pg.wait_for_timeout(500)


with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome')
    ctx = br.new_context(viewport={'width': 1440, 'height': 900})
    pg = ctx.new_page()
    jserrs = []
    pg.on('pageerror', lambda e: jserrs.append(str(e)))

    login(pg)

    print('\n===== 1. 导航三项 =====')
    for k, label in [('water', '喝水'), ('move', '运动'), ('breathe', '478呼吸法')]:
        n = pg.locator('[data-nav="%s"]' % k)
        chk('导航有「%s」' % label, n.count() == 1, 'count=%d' % n.count())

    print('\n===== 2. 三个健康模块页 =====')
    nav(pg, 'water')
    chk('喝水 页渲染 .water-page（v173 内联改版）', pg.locator('.water-page').count() >= 1)
    chk('喝水 页有内联设置表单', pg.locator('#water-settings-form').count() == 1)
    chk('喝水 页有「喝水的好处」', '喝水的好处' in pg.inner_text('.water-page'))
    chk('喝水 页有「数据统计」', '数据统计' in pg.inner_text('.water-page'))
    chk('喝水 页有「喝水提醒」', '喝水提醒' in pg.inner_text('.water-page'))
    nav(pg, 'move')
    chk('运动 页渲染 .move-page（v175 改版）', pg.locator('.move-page').count() >= 1)
    chk('运动 页有「新建运动」按钮', pg.locator('[data-act="move-new"]').count() >= 1)
    nav(pg, 'breathe')
    chk('478呼吸法 页渲染 .module-page', pg.locator('.module-page').count() >= 1)
    chk('478呼吸法 页有「设置」按钮', pg.locator('[data-act="module-edit"][data-key="breathe"]').count() >= 1)

    print('\n===== 3. 喝水设置三值联动 =====')
    nav(pg, 'water')
    chk('有水总量字段', pg.locator('#water-settings-form [name="goalMl"]').count() == 1)
    chk('有每次毫升字段', pg.locator('#water-settings-form [name="perMl"]').count() == 1)
    chk('有杯数字段', pg.locator('#water-settings-form [name="cups"]').count() == 1)
    pg.fill('#water-settings-form [name="perMl"]', '500')
    pg.wait_for_timeout(200)
    cups_after = pg.input_value('#water-settings-form [name="cups"]')
    chk('改每次 500 后杯数重算为 5（2300/500 上取整）', cups_after == '5', 'cups=%s' % cups_after)

    print('\n===== 4. 运动 2.1：新建运动弹窗（模式 / 说明 / 目标 / 频率 / 记录方式）=====')
    nav(pg, 'move')
    chk('运动页空状态「还没有运动」', '还没有运动' in pg.inner_text('.move-page'))
    pg.click('[data-act="move-new"]')
    pg.wait_for_timeout(300)
    chk('新建运动弹窗打开', pg.locator('#move-sport-form').count() == 1)
    form_txt = pg.inner_text('#move-sport-form')
    chk('弹窗写「选择运动模式」', '选择运动模式' in form_txt)
    chk('弹窗写「运动说明」', '运动说明' in form_txt)
    chk('弹窗不再让填「名称」', '名称' not in form_txt)
    chk('模式网格 7 格（游泳/瑜伽已下线）', pg.locator('.sp-grid .sp-opt').count() == 7,
        'count=%d' % pg.locator('.sp-grid .sp-opt').count())
    # 每日步数：两种记录方式，无配速/心率
    pg.click('.sp-grid .sp-opt[data-k="steps"]')
    pg.wait_for_timeout(200)
    body1 = pg.inner_text('#move-sport-body')
    chk('步数有「记录方式」', '记录方式' in body1)
    chk('步数有「手动输入今日步数」', '手动输入今日步数' in body1)
    chk('步数有「每次记录固定步数」', '每次记录固定步数' in body1)
    chk('步数目标写「每日步数（步）」', '每日步数（步）' in body1)
    chk('步数无「配速」开关', pg.locator('#move-sport-body [data-fld="pace"]').count() == 0)
    chk('步数无「心率」开关', pg.locator('#move-sport-body [data-fld="heart"]').count() == 0)
    # 跑步
    pg.click('.sp-grid .sp-opt[data-k="run"]')
    pg.wait_for_timeout(200)
    body2 = pg.inner_text('#move-sport-body')
    chk('跑步目标写「每次距离（公里）」', '每次距离（公里）' in body2)
    chk('跑步有配速 / 心率 / 步频', all(x in body2 for x in ['配速', '心率', '步频']))
    # 健走：目标可在距离↔时长之间下拉
    pg.click('.sp-grid .sp-opt[data-k="walk"]')
    pg.wait_for_timeout(200)
    chk('健走目标有下拉', pg.locator('#move-sport-body #sp-target').count() == 1)
    chk('健走下拉含「每次时长（分钟）」', '每次时长（分钟）' in pg.inner_text('#move-sport-body #sp-target'))
    # 频率只留两档；每周是星期多选
    chk('频率只有两档', pg.locator('#move-sport-body .sp-freq-opt').count() == 2)
    pg.click('#move-sport-body .sp-freq-opt[data-fk2="weekly"]')
    pg.wait_for_timeout(200)
    chk('每周模式有 7 个星期按钮', pg.locator('#sp-week button').count() == 7)
    chk('每周模式没有数字次数框', pg.locator('#move-sport-body #sp-freqn').count() == 0)
    pg.click('#move-sport-body .sp-freq-opt[data-fk2="daily"]')
    pg.wait_for_timeout(200)
    chk('每天模式有紧凑次数框', pg.locator('#move-sport-body #sp-freqn').count() == 1)
    # v179：游泳、瑜伽已下线，新建列表里不应再出现
    chk('新建列表不含游泳', pg.locator('.sp-grid .sp-opt[data-k="swim"]').count() == 0)
    chk('新建列表不含瑜伽', pg.locator('.sp-grid .sp-opt[data-k="yoga"]').count() == 0)
    chk('新建列表共 7 种模式', pg.locator('.sp-grid .sp-opt').count() == 7,
        'count=%d' % pg.locator('.sp-grid .sp-opt').count())
    # 力量训练的运动数据记录
    pg.click('.sp-grid .sp-opt[data-k="strength"]')
    pg.wait_for_timeout(250)
    st_txt = pg.inner_text('#move-sport-body')
    chk('力量训练写「运动数据记录」', '运动数据记录' in st_txt)
    chk('力量训练含组数 / 负重重量', '组数' in st_txt and '负重重量' in st_txt)
    pg.click('[data-act="close-modal"]')
    pg.wait_for_timeout(200)

    print('\n===== 5. 运动 2.1：添加每日步数 + 固定步数直接累加 + 明细 =====')
    nav(pg, 'move')
    pg.click('[data-act="move-new"]')
    pg.wait_for_timeout(300)
    pg.click('.sp-grid .sp-opt[data-k="steps"]')
    pg.wait_for_timeout(200)
    pg.fill('#sp-tval', '10000')
    pg.click('#move-sport-body .sp-rec-opt[data-rm="fixed"]')
    pg.wait_for_timeout(200)
    pg.fill('#sp-fixed', '2000')
    pg.click('#move-sport-form button[type="submit"]')
    pg.wait_for_timeout(1200)
    chk('添加后弹窗关闭', pg.locator('#move-sport-form').count() == 0)
    chk('运动页出现「每日步数」卡', '每日步数' in pg.inner_text('.move-page'))
    chk('卡片按钮写「记录 +2000 步」', '记录 +2000 步' in pg.inner_text('.move-page'))
    pg.click('[data-act="move-do"]')
    pg.wait_for_timeout(700)
    chk('固定步数点一下不弹输入框', pg.locator('#move-record-form').count() == 0)
    move_txt = pg.inner_text('.move-page')
    chk('卡片累计到 2000 步', '2000' in move_txt)
    chk('有「数据统计」板块', '数据统计' in move_txt)
    # v184：页面底部的「运动明细」总表撤了，记录改到卡片里的【今日任务记录】
    chk('底部不再有运动明细板块', '运动明细' not in move_txt)
    chk('卡片有「今日任务记录」入口', pg.locator('.mv-card [data-act="move-log"]').count() >= 1)
    pg.click('.mv-card [data-act="move-log"]')
    pg.wait_for_timeout(800)
    chk('任务记录里有 1 条记录', pg.locator('#modal-root .sp-recrow').count() == 1,
        'rows=%d' % pg.locator('#modal-root .sp-recrow').count())
    chk('每条带「修改 / 删除」', pg.locator('#modal-root [data-rec-edit]').count() >= 1
        and pg.locator('#modal-root [data-rec-del]').count() >= 1)
    pg.click('#modal-root [data-act="close-modal"]')
    pg.wait_for_timeout(400)

    print('\n===== 6. 习惯页不含常驻卡 =====')
    nav(pg, 'habits')
    main = pg.inner_text('.habits-main')
    for label in ['喝水', '戒烟', '运动', '478']:
        chk('习惯页不含「%s」条目' % label, label not in main)

    print('\n===== 7. 统计页：喝水 / 运动 / 478 各自成块、无合并面板 =====')
    nav(pg, 'stats')
    pg.wait_for_timeout(400)
    titles = [t.strip() for t in pg.locator('.panel h3').all_inner_texts()]
    joined = ' | '.join(titles)
    chk('统计页不再有「健康模块」合并面板', '健康模块' not in joined, joined)
    for label in ['喝水', '运动', '478呼吸法']:
        chk('统计页有独立的「%s」块' % label, any(t.startswith(label) for t in titles), joined)

    print('\n===== 8. 迁移：seed 只有 h_water 锚点，四个模块仍全部成卡 =====')
    nav(pg, 'today')
    pg.wait_for_timeout(400)
    dash = pg.inner_text('.vital-grid') if pg.locator('.vital-grid').count() else ''
    for label in ['喝水', '运动', '478呼吸法', '戒烟']:
        chk('仪表盘有「%s」卡' % label, label in dash)

    print('\n===== 9. JS 报错 =====')
    chk('无未捕获 JS 异常', len(jserrs) == 0, ' | '.join(jserrs[:3]))

    br.close()

print('\n========== 结果：通过 %d，失败 %d ==========' % (PASS, FAIL))
for name, detail in FAILS:
    print('FAIL: %s  (%s)' % (name, detail))
sys.exit(1 if FAIL else 0)
