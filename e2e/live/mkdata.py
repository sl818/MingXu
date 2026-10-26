# -*- coding: utf-8 -*-
"""线上真实环境：通过 UI 创建测试数据（用药 / 待办 / 随笔 / 体重 / 习惯）。
用法: python mkdata.py meds|tasks|extras
"""
import json, os, sys, time
from playwright.sync_api import sync_playwright

BASE = os.environ.get('LIVE_BASE', 'https://todo.csl88.top/')
# 账号密码不入库：运行前设置 LIVE_EMAIL / LIVE_PWD 两个环境变量
EMAIL = os.environ.get('LIVE_EMAIL', '')
PWD = os.environ.get('LIVE_PWD', '')
if not EMAIL or not PWD:
    sys.exit('请先设置环境变量 LIVE_EMAIL 与 LIVE_PWD')
TODAY = '2026-10-26'

LONG = [('缬沙坦胶囊', '西药', '胶囊', 2), ('瑞舒伐他汀钙片', '西药', '片', 1),
        ('甲钴胺片', '西药', '片', 3), ('复方丹参滴丸', '中药', '其他', 3),
        ('维生素B12片', '维生素', '片', 1)]
SHORT = [('阿奇霉素片', '抗生素', '片', 1), ('连花清瘟胶囊', '中药', '胶囊', 3),
         ('盐酸氨溴索口服液', '西药', '口服液', 2), ('铝镁加混悬液', '西药', '袋', 3),
         ('头孢地尼胶囊', '抗生素', '胶囊', 2)]
PRN = [('对乙酰氨基酚片', '西药', '片'), ('藿香正气水', '中药', '口服液'),
       ('西替利嗪片', '西药', '片'), ('云南白药气雾剂', '中药', '其他'),
       ('布洛芬混悬液', '西药', '口服液')]

TASKS = [
    ('健康', 'todo', '晨跑 3 公里', '高', TODAY),
    ('健康', 'todo', '补充维生素', '低', '2026-10-27'),
    ('健康', 'doing', '记录一周饮水', '中', TODAY),
    ('健康', 'done', '完成 20 个深蹲', '中', TODAY),
    ('生活', 'todo', '整理衣柜换季', '低', '2026-10-28'),
    ('生活', 'todo', '清洗空调滤网', '中', TODAY),
    ('生活', 'doing', '每日记账', '中', TODAY),
    ('生活', 'done', '给绿植浇水', '低', TODAY),
    ('工作', 'todo', '整理季度报表', '高', TODAY),
    ('工作', 'todo', '回复客户邮件', '高', '2026-10-27'),
    ('工作', 'doing', '修订项目排期', '中', TODAY),
    ('工作', 'done', '提交周报', '中', TODAY),
    ('学习', 'todo', '读完《深度工作》第 3 章', '中', '2026-10-29'),
    ('学习', 'todo', '背 50 个单词', '低', TODAY),
    ('学习', 'doing', '写读书笔记', '中', TODAY),
    ('学习', 'done', '完成 PHP 练习题', '低', TODAY),
    ('其他', 'todo', '预约洗车', '低', '2026-10-30'),
    ('其他', 'todo', '整理照片备份', '中', TODAY),
    ('其他', 'doing', '规划周末行程', '低', TODAY),
    ('其他', 'done', '缴纳水电费', '高', TODAY),
]
CANCELLED = [('健康', '取消体检预约'), ('工作', '取消旧方案评审'), ('学习', '取消网课报名')]


def login(pg):
    pg.goto(BASE, wait_until='networkidle', timeout=60000)
    pg.wait_for_timeout(1500)
    if pg.locator('[data-act="cloud-login"]').count():
        pg.click('[data-act="cloud-login"]')
        pg.wait_for_timeout(700)
        pg.fill('input[name="email"]', EMAIL)
        pg.fill('input[name="password"]', PWD)
        pg.click('form.modal-card button[type="submit"]')
        pg.wait_for_timeout(5000)
    pg.wait_for_selector('[data-nav="today"]', state='attached', timeout=20000)


def nav(pg, v):
    pg.evaluate("""v => { const b=document.querySelector('[data-nav="'+v+'"]'); if(b) b.click(); }""", v)
    pg.wait_for_timeout(600)


def mk_med(pg, name, purpose, form, course, times=None):
    nav(pg, 'meds')
    pg.click('[data-act="med-new"]')
    pg.wait_for_selector('#med-form', timeout=8000)
    pg.fill('#med-form [name="name"]', name)
    pg.select_option('#med-form [name="purpose"]', purpose)
    pg.select_option('#med-form [name="form"]', form)
    pg.select_option('#med-form [name="courseType"]', course)
    pg.wait_for_timeout(200)
    if course != 'prn':
        pg.select_option('#med-form [name="doseTimes"]', str(times))
        pg.wait_for_timeout(250)
    if course == 'short':
        pg.fill('#med-form [name="endDate"]', '2026-11-02')
    pg.fill('#med-form [name="startDate"]', '2026-10-20')
    pg.fill('#med-form [name="manufacturer"]', '终测制药')
    pg.click('#med-form button[type="submit"]')
    pg.wait_for_timeout(1100)
    return pg.locator('#med-form').count() == 0


def mk_task(pg, tag, status, title, prio, due):
    nav(pg, 'board')
    pg.click('[data-act="task-new"][data-status="%s"]' % status)
    pg.wait_for_selector('#task-form', timeout=8000)
    pg.fill('#task-form [name="title"]', '【终测】' + title)
    pg.fill('#task-form [name="note"]', '线上真实环境测试数据')
    pg.select_option('#task-form [name="tag"]', tag)
    pg.select_option('#task-form [name="priority"]', prio)
    pg.fill('#task-form [name="due"]', due)
    pg.select_option('#task-form [name="status"]', status)
    pg.click('#task-form button[type="submit"]')
    pg.wait_for_timeout(1000)
    return pg.locator('#task-form').count() == 0


def mk_essay(pg, date, title, text):
    nav(pg, 'essays')
    pg.click('[data-act="essay-new"]')
    pg.wait_for_selector('#essay-form', timeout=8000)
    pg.fill('#essay-form [name="date"]', date)
    pg.fill('#essay-form [name="title"]', title)
    pg.fill('#essay-form [name="text"]', text)
    pg.click('#essay-form button[type="submit"]')
    pg.wait_for_timeout(1000)
    return pg.locator('#essay-form').count() == 0


def mk_weight(pg, date, weight):
    nav(pg, 'weight')
    pg.click('[data-act="weight-new"]')
    pg.wait_for_selector('#weight-form', timeout=8000)
    pg.fill('#weight-form [name="date"]', date)
    pg.fill('#weight-form [name="weight"]', str(weight))
    pg.click('#weight-form button[type="submit"]')
    pg.wait_for_timeout(1000)
    return pg.locator('#weight-form').count() == 0


def mk_habit(pg, icon, name, htype, target, unit, note):
    nav(pg, 'habits')
    pg.click('[data-act="habit-new"]')
    pg.wait_for_selector('#habit-form', timeout=8000)
    pg.fill('#habit-form [name="icon"]', icon)
    pg.fill('#habit-form [name="name"]', name)
    pg.select_option('#habit-form [name="type"]', htype)
    pg.fill('#habit-form [name="target"]', str(target))
    pg.fill('#habit-form [name="unit"]', unit)
    pg.fill('#habit-form [name="note"]', note)
    pg.click('#habit-form button[type="submit"]')
    pg.wait_for_timeout(1000)
    return pg.locator('#habit-form').count() == 0


def main():
    stage = sys.argv[1] if len(sys.argv) > 1 else 'all'
    log = []
    with sync_playwright() as p:
        br = p.chromium.launch(channel='chrome', headless=True)
        ctx = br.new_context(viewport={'width': 1440, 'height': 950})
        pg = ctx.new_page()
        errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)[:160]))
        login(pg)
        print('已登录')

        if stage in ('meds', 'all'):
            for n, pu, f, t in LONG:
                log.append(('长期用药 ' + n, mk_med(pg, n, pu, f, 'long', t)))
            for n, pu, f, t in SHORT:
                log.append(('短期用药 ' + n, mk_med(pg, n, pu, f, 'short', t)))
            for n, pu, f in PRN:
                log.append(('按需用药 ' + n, mk_med(pg, n, pu, f, 'prn')))

        if stage in ('tasks', 'all'):
            for tag, st, title, prio, due in TASKS:
                log.append(('%s/%s %s' % (tag, st, title), mk_task(pg, tag, st, title, prio, due)))
            for tag, title in CANCELLED:
                log.append(('已取消 ' + title, mk_task(pg, tag, 'cancelled', title, '低', TODAY)))

        if stage in ('extras', 'all'):
            # 虚拟身体档案
            nav(pg, 'weight')
            pg.click('[data-act="profile-edit"]')
            pg.wait_for_selector('#body-profile-form', timeout=8000)
            pg.fill('#body-profile-form [name="age"]', '30')
            pg.fill('#body-profile-form [name="height"]', '172')
            pg.fill('#body-profile-form [name="goalWeight"]', '65')
            pg.click('#body-profile-form button[type="submit"]')
            pg.wait_for_timeout(1200)
            log.append(('虚拟身体档案 30岁/172cm/目标65', pg.locator('#body-profile-form').count() == 0))
            log.append(('体重 2026-06-18', mk_weight(pg, '2026-06-18', 79.5)))
            log.append(('体重 2026-09-05', mk_weight(pg, '2026-09-05', 74.8)))
            log.append(('体重 2026-10-26', mk_weight(pg, '2026-10-26', 71.6)))
            log.append(('随笔 第一篇', mk_essay(pg, '2026-10-26', '终测 · 清晨的十分钟',
                        '今天把闹钟往前拨了十分钟，用来坐在窗边喝一杯水。\n'
                        '没有看手机，也没有想今天要做什么，只是听了一会儿楼下的声音。\n'
                        '这十分钟说不上有什么用，但一整天都没那么赶。')))
            log.append(('随笔 第二篇', mk_essay(pg, '2026-10-25', '终测 · 药店排队的二十分钟',
                        '排在我前面的老先生拿着一张写满字的纸，反复确认每种药怎么吃。\n'
                        '药师一条一条念给他听，还写了便签贴在药盒上。\n'
                        '轮到我的时候，忽然觉得该把自己那份用药记录也再核一遍。')))
            log.append(('习惯 晨间拉伸(保持)', mk_habit(pg, '🧘', '终测·晨间拉伸', 'build', 1, '次', '起床后 5 分钟')))
            log.append(('习惯 防晒(保持)', mk_habit(pg, '🧴', '终测·涂防晒', 'build', 1, '次', '出门前')))
            log.append(('习惯 戒碳酸饮料(戒除)', mk_habit(pg, '🥤', '终测·戒碳酸饮料', 'quit', 1, '次', '改喝白水')))
            log.append(('习惯 戒睡前刷手机(戒除)', mk_habit(pg, '📵', '终测·睡前不刷手机', 'quit', 1, '次', '十点后放客厅')))

        print('=== 创建结果 ===')
        ok = 0
        for name, r in log:
            if not r:
                print('  ✗ %s' % name)
            ok += 1 if r else 0
        print('成功 %d / %d' % (ok, len(log)))
        print('页面错误:', errs[:3] or '无')
        ctx.close()
        br.close()


if __name__ == '__main__':
    main()
