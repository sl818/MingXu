"""线上测试 · 阶段 2：待办（待办/进行中/已完成 各 1 组 4 条 + 已取消 3 条随机分组）"""
import json
from datetime import date, timedelta
from playwright.sync_api import sync_playwright

BASE = 'https://your-domain.example/'
EMAIL = 'test@example.com'
PWD = 'test@example.com'
TODAY = date(2026, 10, 25)


def d(offset):
    return str(TODAY + timedelta(days=offset))


TASKS = [
    # ---- 待办列 ----
    dict(status='todo', title='整理本月医疗账单', tag='健康', prio='高', due=d(0),
         note='把门诊、药房、检查三类发票分好，拍照存档。'),
    dict(status='todo', title='预约牙科半年复查', tag='健康', prio='中', due=d(2),
         note='上次洗牙是 4 月，顺便问一下智齿的情况。'),
    dict(status='todo', title='给阳台绿植换土', tag='生活', prio='低', due=d(5),
         note='龟背竹和琴叶榕都要换大一号的盆。'),
    dict(status='todo', title='复习《PHP 设计模式》第 3 章', tag='学习', prio='中', due=d(3),
         note='策略模式 + 观察者模式，做两个小例子。'),

    # ---- 进行中列 ----
    dict(status='doing', title='重写个人简历', tag='工作', prio='高', due=d(0),
         note='重点改项目经历部分，量化成果，删掉 2019 年以前的实习。'),
    dict(status='doing', title='整理 2026 年度体检报告', tag='健康', prio='中', due=d(1),
         note='把三年数据做成对比表，重点看血脂和尿酸。'),
    dict(status='doing', title='学完 Laravel 中间件视频课', tag='学习', prio='中', due=d(7),
         note='还剩 4 节，边看边把项目里的鉴权中间件重构一遍。'),
    dict(status='doing', title='家里路由器固件升级', tag='其他', prio='低', due='',
         note='升级前先导出配置备份。'),

    # ---- 已完成列 ----
    dict(status='done', title='缴纳本月水电费', tag='生活', prio='中', due=d(-1),
         note='已通过手机银行缴清，电子回单存在网盘。'),
    dict(status='done', title='回复客户关于交付时间的邮件', tag='工作', prio='高', due=d(-2),
         note='确认 11 月 5 日交付第一版，附上里程碑表。'),
    dict(status='done', title='采购一周食材', tag='生活', prio='低', due=d(-1),
         note='鸡胸、西兰花、燕麦、无糖酸奶、冷冻蓝莓。'),
    dict(status='done', title='完成今日 8000 步', tag='健康', prio='中', due=d(0),
         note='晚上绕小区走了两圈，配速比上周快了一点。'),

    # ---- 已取消 3 条（不同分组）----
    dict(status='cancelled', title='报名周末摄影进阶课', tag='学习', prio='低', due=d(4),
         note='时间与家庭安排冲突，等下期再报。'),
    dict(status='cancelled', title='更换客厅主灯', tag='生活', prio='中', due=d(6),
         note='量过尺寸后发现吊顶承重不够，先搁置。'),
    dict(status='cancelled', title='参加行业线下交流会', tag='工作', prio='低', due=d(8),
         note='和出差撞期，改为看回放。'),
]


def fill(form, name, value):
    if value is None or value == '':
        return
    sel = form.locator('[name="%s"]' % name)
    if sel.count() == 0:
        return
    el = sel.first
    if not el.is_visible():
        return
    tag = el.evaluate('e => e.tagName.toLowerCase()')
    if tag == 'select':
        opts = el.evaluate('e => [...e.options].map(o => o.value)')
        if str(value) not in opts:
            return
        el.select_option(str(value))
    else:
        el.fill(str(value))


with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)
    ctx = br.new_context(viewport={'width': 1680, 'height': 1000})
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)[:200]))
    pg.on('dialog', lambda dlg: (print('DIALOG:', dlg.message[:120]), dlg.accept()))

    pg.goto(BASE, wait_until='networkidle', timeout=60000)
    pg.wait_for_timeout(1200)
    pg.click('[data-act="cloud-login"]'); pg.wait_for_timeout(700)
    pg.fill('input[name="email"]', EMAIL)
    pg.fill('input[name="password"]', PWD)
    pg.click('form.modal-card button[type="submit"]')
    pg.wait_for_timeout(3800)
    pg.evaluate("""() => { const b=document.querySelector('.nav-item[data-nav="board"]'); if(b) b.click(); }""")
    pg.wait_for_timeout(1000)

    before = pg.evaluate("""() => [...document.querySelectorAll('.col')].map(c => c.querySelector('.col-count').textContent)""")
    print('before counts =', before)

    ok = 0
    for i, t in enumerate(TASKS, 1):
        try:
            pg.evaluate("""(st) => {
              const b = document.querySelector('[data-act="task-new"][data-status="' + st + '"]');
              if (b) b.click();
            }""", t['status'])
            pg.wait_for_timeout(550)
            form = pg.locator('#task-form')
            if form.count() == 0:
                print('[%02d] FAIL no form' % i); continue
            fill(form, 'title', t['title'])
            fill(form, 'note', t.get('note'))
            fill(form, 'status', t['status'])
            fill(form, 'tag', t['tag'])
            fill(form, 'priority', t['prio'])
            fill(form, 'due', t.get('due'))
            pg.wait_for_timeout(120)
            pg.click('#task-form button[type="submit"]')
            pg.wait_for_timeout(1100)
            shown = pg.evaluate("(n) => document.querySelector('#main').textContent.includes(n)", t['title'])
            print('[%02d] %s %s [%s]' % (i, 'OK  ' if shown else 'FAIL', t['title'], t['status']))
            if shown:
                ok += 1
            else:
                pg.screenshot(path='design/shots/live-task-fail-%02d.png' % i)
                pg.evaluate("() => { const b=document.querySelector('[data-act=\"close-modal\"]'); if(b) b.click(); }")
                pg.wait_for_timeout(300)
        except Exception as e:
            print('[%02d] ERR %s -> %s' % (i, t['title'], str(e)[:140]))
            pg.evaluate("() => { const b=document.querySelector('[data-act=\"close-modal\"]'); if(b) b.click(); }")
            pg.wait_for_timeout(300)

    print('\ncreated %d / %d' % (ok, len(TASKS)))
    after = pg.evaluate("""() => ({
      counts: [...document.querySelectorAll('.col')].map(c => c.querySelector('.col-count').textContent),
      titles: [...document.querySelectorAll('.col')].map(c => ({
        col: c.dataset.status,
        items: [...c.querySelectorAll('.task h4')].map(e => e.textContent.trim())
      })),
      arch: (document.querySelector('[data-act="archive-open"]') || {}).textContent || ''
    })""")
    print(json.dumps(after, ensure_ascii=False, indent=1))
    print('errs=', errs[:3])
    pg.screenshot(path='design/shots/live-03-board.png', full_page=True)
    br.close()
