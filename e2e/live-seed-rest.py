"""线上测试 · 阶段 3：随笔 2 篇 + 体重档案与 3 条记录 + 习惯 2 保持 2 戒除"""
import json
from datetime import date, timedelta
from playwright.sync_api import sync_playwright

BASE = 'https://your-domain.example/'
EMAIL = 'test@example.com'
PWD = 'test@example.com'
TODAY = date(2026, 10, 25)

ESSAYS = [
    dict(title='十月的最后一周', tags='生活，复盘', date=str(TODAY - timedelta(days=1)),
         text='这几天把阳台收拾了一遍，旧花盆搬下去的时候才发现土已经板结得像石头。\n\n'
              '换土这件事拖了快两个月。真正动手只花了四十分钟，但之前每次看见那盆龟背竹，'
              '心里都会积一点「还没做」的重量。做完之后那点重量忽然就没了，甚至有点奇怪——'
              '为什么这么小的事要拖这么久。\n\n'
              '大概是因为它不会催你。账单会催，邮件会催，体检报告会催，但一盆植物只会安静地长，'
              '叶子黄了一点也不吭声。等到它真的蔫了，你才开始愧疚。\n\n'
              '所以这周的准备是：把「不会催我的事」单独列一栏，每周固定看一眼。'),
    dict(title='关于早睡这件事，我试过的四种办法', tags='健康，睡眠', date=str(TODAY - timedelta(days=3)),
         text='从去年冬天开始认真对付「十二点还不想睡」这个问题，前后试了四种办法，记录一下效果。\n\n'
              '一、定闹钟提醒睡觉。响了三次之后我就学会无视它了。失败。\n\n'
              '二、把手机放在客厅充电。有效，但代价是早上闹钟听不见，改成用旧手表之后勉强能接受。'
              '坚持了两周，出差一次就断了。\n\n'
              '三、睡前读纸质书。这个效果最好。不是因为读书让人困，而是因为它占住了原本刷手机的那段时间，'
              '而且屏幕不在眼前。唯一的问题是书要好读，太硬的会越读越清醒。\n\n'
              '四、把卧室灯换成暖光小灯。有点用，主要是心理暗示：灯一暗，身体就知道该收了。\n\n'
              '现在的组合是「三 + 四」，手机放在床头但开飞行模式。入睡时间从 1:20 提前到 23:50 左右，'
              '早上起来没那么像被人打过一顿了。'),
]

WEIGHTS = [
    dict(date=str(date(2026, 5, 20)), weight='78.6'),
    dict(date=str(date(2026, 8, 8)), weight='75.2'),
    dict(date=str(date(2026, 10, 24)), weight='72.4'),
]

HABITS = [
    dict(name='早起喝温水', icon='🥛', type='build', target='1', unit='杯', color='#4c7f96',
         note='起床后先喝 300ml'),
    dict(name='睡前拉伸 10 分钟', icon='🧘', type='build', target='1', unit='次', color='#7fa79c',
         note='重点放松肩颈和腿后侧'),
    dict(name='不喝含糖饮料', icon='🚫', type='quit', target='1', unit='次', color='#9c5a5a',
         note='想喝就换成气泡水'),
    dict(name='睡前不刷短视频', icon='🌙', type='quit', target='1', unit='次', color='#6b6f9c',
         note='手机放客厅充电'),
]

PROFILE = dict(age='34', height='175')


def fill(form, name, value):
    if value is None or value == '':
        return None
    sel = form.locator('[name="%s"]' % name)
    if sel.count() == 0:
        return 'no-el'
    el = sel.first
    if not el.is_visible():
        return 'hidden'
    if el.evaluate('e => !!e.disabled'):
        return 'disabled'
    tag = el.evaluate('e => e.tagName.toLowerCase()')
    if tag == 'select':
        opts = el.evaluate('e => [...e.options].map(o => o.value)')
        if str(value) not in opts:
            return 'no-opt'
        el.select_option(str(value))
    else:
        el.fill(str(value))
    return 'ok'


def nav(pg, key):
    pg.evaluate("""(k) => {
      const b = document.querySelector('.nav-item[data-nav="' + k + '"]') ||
                document.querySelector('.mobile-tab[data-nav="' + k + '"]');
      if (b) b.click();
    }""", key)
    pg.wait_for_timeout(850)


with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)
    ctx = br.new_context(viewport={'width': 1680, 'height': 1000})
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)[:200]))
    pg.on('dialog', lambda d: (print('DIALOG:', d.message[:120]), d.accept()))

    pg.goto(BASE, wait_until='networkidle', timeout=60000)
    pg.wait_for_timeout(1200)
    pg.click('[data-act="cloud-login"]'); pg.wait_for_timeout(700)
    pg.fill('input[name="email"]', EMAIL)
    pg.fill('input[name="password"]', PWD)
    pg.click('form.modal-card button[type="submit"]')
    pg.wait_for_timeout(3800)

    # ---------------- 随笔 ----------------
    nav(pg, 'essays')
    body = pg.evaluate("() => document.querySelector('#main').textContent")
    e_ok = 0
    for i, e in enumerate(ESSAYS, 1):
        if e['title'] in body:
            print('[随笔 %d] skip (exists) %s' % (i, e['title'])); e_ok += 1; continue
        pg.evaluate("""() => { const b=document.querySelector('[data-act="essay-new"]'); if(b) b.click(); }""")
        pg.wait_for_timeout(550)
        form = pg.locator('#essay-form')
        if form.count() == 0:
            print('[随笔 %d] FAIL no form' % i); continue
        fill(form, 'date', e['date'])
        fill(form, 'title', e['title'])
        fill(form, 'tags', e['tags'])
        fill(form, 'text', e['text'])
        pg.wait_for_timeout(120)
        pg.click('#essay-form button[type="submit"]')
        pg.wait_for_timeout(1200)
        shown = pg.evaluate("(n) => document.querySelector('#main').textContent.includes(n)", e['title'])
        print('[随笔 %d] %s %s' % (i, 'OK  ' if shown else 'FAIL', e['title']))
        if shown: e_ok += 1
        else: pg.screenshot(path='design/shots/live-essay-fail-%d.png' % i)
    print('随笔 %d / %d\n' % (e_ok, len(ESSAYS)))

    # ---------------- 体重 ----------------
    nav(pg, 'weight')
    pbody = pg.evaluate("() => document.querySelector('#main').textContent")
    has_profile = pg.evaluate("""() => {
      const t = document.querySelector('#main').textContent || '';
      const m = t.match(/当前档案：(\\d+) 岁 · ([\\d.]+) cm/);
      return m ? {age: m[1], h: m[2]} : null;
    }""")
    print('existing profile =', has_profile)
    if not has_profile:
        pg.evaluate("""() => { const b=document.querySelector('[data-act="profile-edit"]'); if(b) b.click(); }""")
        pg.wait_for_timeout(600)
        form = pg.locator('#body-profile-form')
        if form.count():
            fill(form, 'age', PROFILE['age'])
            fill(form, 'height', PROFILE['height'])
            pg.click('#body-profile-form button[type="submit"]')
            pg.wait_for_timeout(1200)
            print('profile created:', pg.evaluate("""() => {
              const t = document.querySelector('#main').textContent || '';
              const m = t.match(/当前档案：(\\d+) 岁 · ([\\d.]+) cm/); return m ? m[0] : 'not shown';
            }"""))
    else:
        print('profile kept as-is (不覆盖已有档案)')

    w_ok = 0
    for i, w in enumerate(WEIGHTS, 1):
        pg.evaluate("""() => { const b=document.querySelector('[data-act="weight-new"]'); if(b) b.click(); }""")
        pg.wait_for_timeout(600)
        form = pg.locator('#weight-form')
        if form.count() == 0:
            print('[体重 %d] FAIL no form' % i); continue
        fill(form, 'date', w['date'])
        fill(form, 'weight', w['weight'])
        pg.wait_for_timeout(120)
        pg.click('#weight-form button[type="submit"]')
        pg.wait_for_timeout(1200)
        shown = pg.evaluate("(n) => document.querySelector('#main').textContent.includes(n)", w['weight'])
        print('[体重 %d] %s %s kg @ %s' % (i, 'OK  ' if shown else 'FAIL', w['weight'], w['date']))
        if shown: w_ok += 1
        else: pg.screenshot(path='design/shots/live-weight-fail-%d.png' % i)
    print('体重 %d / %d' % (w_ok, len(WEIGHTS)))
    print('chart =', pg.evaluate("""() => ({
      dots: document.querySelectorAll('.ww-dot').length,
      labels: [...document.querySelectorAll('.ww-lbl')].map(e=>e.textContent),
      rows: [...document.querySelectorAll('.wsum-row')].map(e=>e.textContent.replace(/\\s+/g,' ').trim()),
      band: (document.querySelector('.cal-hint')||{}).textContent||''
    })"""))

    # ---------------- 习惯 ----------------
    nav(pg, 'habits')
    hbody = pg.evaluate("() => document.querySelector('#main').textContent")
    h_ok = 0
    for i, h in enumerate(HABITS, 1):
        if h['name'] in hbody:
            print('[习惯 %d] skip (exists) %s' % (i, h['name'])); h_ok += 1; continue
        pg.evaluate("""() => { const b=document.querySelector('[data-act="habit-new"]'); if(b) b.click(); }""")
        pg.wait_for_timeout(550)
        form = pg.locator('#habit-form')
        if form.count() == 0:
            print('[习惯 %d] FAIL no form' % i); continue
        fill(form, 'icon', h['icon'])
        fill(form, 'name', h['name'])
        r = fill(form, 'type', h['type'])
        pg.wait_for_timeout(250)
        if h['type'] == 'build':
            fill(form, 'target', h['target'])
        fill(form, 'unit', h['unit'])
        fill(form, 'note', h['note'])
        pg.wait_for_timeout(120)
        pg.click('#habit-form button[type="submit"]')
        pg.wait_for_timeout(1200)
        shown = pg.evaluate("(n) => document.querySelector('#main').textContent.includes(n)", h['name'])
        print('[习惯 %d] %s %s (%s) type=%s' % (i, 'OK  ' if shown else 'FAIL', h['name'], h['type'], r))
        if shown: h_ok += 1
        else: pg.screenshot(path='design/shots/live-habit-fail-%d.png' % i)
    print('习惯 %d / %d' % (h_ok, len(HABITS)))

    print('\nfinal habits =', json.dumps(pg.evaluate("""() => [...document.querySelectorAll('.habit-row')].map(e=>e.textContent.replace(/\\s+/g,' ').trim().slice(0,56))"""), ensure_ascii=False, indent=1))
    print('errs=', errs[:3])
    pg.screenshot(path='design/shots/live-04-habits.png', full_page=True)
    br.close()
