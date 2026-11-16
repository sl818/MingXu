"""线上测试 · 阶段 1b：幂等补齐用药（跳过已存在），修掉单位/空腹两处字段陷阱"""
import sys, json, re
from playwright.sync_api import sync_playwright

BASE = 'https://your-domain.example/'
EMAIL = 'test@example.com'
PWD = 'test@example.com'

MEDS = [
    dict(course='long', name='左甲状腺素钠片', purpose='西药', form='片', strength='50μg',
         amount='1', unit='片', times=['06:30'], meal='empty',
         start='2026-09-01', review='2026-11-20', stock='30', maker='默克', info='晨起空腹，服后 30 分钟再进食'),
    dict(course='long', name='维生素D3软胶囊', purpose='维生素', form='胶囊', strength='400IU',
         amount='1', unit='粒', times=['12:30'], meal='after', mealOff='0',
         start='2026-09-20', review='', stock='40', maker='星鲨', info='随餐服用吸收更好'),
    dict(course='short', name='蒙脱石散', purpose='西药', form='袋', strength='3g',
         amount='1', unit='袋', times=['07:30', '13:00', '19:00'], meal='empty',
         start='2026-10-23', end='2026-10-25', stock='9', maker='博福-益普生', info='与其他药间隔 1 小时以上'),
    dict(course='prn', name='沙丁胺醇片', purpose='西药', form='片', strength='2mg',
         amount='1', unit='片', start='2026-05-01', stock='20', maker='葛兰素史克', info='喘息发作时使用，随身携带'),
]


def fill(form, name, value, log=None):
    if value is None or value == '':
        return
    sel = form.locator('[name="%s"]' % name)
    if sel.count() == 0:
        return
    el = sel.first
    if not el.is_visible():
        if log is not None:
            log.append('skip-hidden:' + name)
        return
    tag = el.evaluate('e => e.tagName.toLowerCase()')
    if tag == 'select':
        opts = el.evaluate('e => [...e.options].map(o => o.value)')
        if str(value) not in opts:
            if log is not None:
                log.append('skip-noopt:%s=%s' % (name, value))
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
    pg.on('dialog', lambda d: (print('DIALOG:', d.message[:120]), d.accept()))

    pg.goto(BASE, wait_until='networkidle', timeout=60000)
    pg.wait_for_timeout(1200)
    pg.click('[data-act="cloud-login"]'); pg.wait_for_timeout(700)
    pg.fill('input[name="email"]', EMAIL)
    pg.fill('input[name="password"]', PWD)
    pg.click('form.modal-card button[type="submit"]')
    pg.wait_for_timeout(3800)
    pg.evaluate("""() => { const b=document.querySelector('.nav-item[data-nav="meds"]'); if(b) b.click(); }""")
    pg.wait_for_timeout(1000)

    existing = pg.evaluate("""() => [...document.querySelectorAll('.med-row .med-name, .med-row b')].map(e=>e.textContent.trim())""")
    body = pg.evaluate("() => document.querySelector('#main').textContent")
    print('existing rows =', len(existing))

    ok = 0
    for i, m in enumerate(MEDS, 1):
        if m['name'] in body:
            print('[%02d] skip (exists) %s' % (i, m['name']))
            ok += 1
            continue
        logs = []
        try:
            pg.click('[data-act="med-new"]')
            pg.wait_for_timeout(500)
            form = pg.locator('#med-form')
            if form.count() == 0:
                print('[%02d] FAIL no form' % i); continue
            fill(form, 'name', m['name'], logs)
            fill(form, 'purpose', m.get('purpose'), logs)
            fill(form, 'form', m.get('form'), logs)
            fill(form, 'strength', m.get('strength'), logs)
            fill(form, 'doseAmount', m.get('amount'), logs)
            fill(form, 'doseUnit', m.get('unit'), logs)
            fill(form, 'courseType', m['course'], logs)
            pg.wait_for_timeout(250)
            if m['course'] != 'prn':
                fill(form, 'doseTimes', str(len(m['times'])), logs)   # option 的 value 是数字，label 才带「次」
                pg.wait_for_timeout(300)
                for k, tm in enumerate(m['times'], 1):
                    pg.locator('#time-slots input').nth(k - 1).fill(tm)
                if m.get('meal'):
                    fill(form, 'mealTiming', m['meal'], logs)
                    pg.wait_for_timeout(220)
                    if m.get('mealOff'):
                        fill(form, 'mealOffset', m['mealOff'], logs)
            fill(form, 'status', 'active', logs)
            fill(form, 'startDate', m.get('start'), logs)
            if m['course'] == 'short':
                fill(form, 'endDate', m.get('end'), logs)
            else:
                fill(form, 'reviewDate', m.get('review'), logs)
            fill(form, 'stock', m.get('stock'), logs)
            fill(form, 'manufacturer', m.get('maker'), logs)
            fill(form, 'medInfo', m.get('info'), logs)
            pg.wait_for_timeout(150)
            pg.click('#med-form button[type="submit"]')
            pg.wait_for_timeout(1200)
            shown = pg.evaluate("(n) => document.querySelector('#main').textContent.includes(n)", m['name'])
            print('[%02d] %s %s %s' % (i, 'OK  ' if shown else 'FAIL', m['name'], ('| ' + ','.join(logs)) if logs else ''))
            if shown:
                ok += 1
            else:
                pg.screenshot(path='design/shots/live-med-fail-%02d.png' % i)
                pg.evaluate("() => { const b=document.querySelector('[data-act=\"close-modal\"]'); if(b) b.click(); }")
                pg.wait_for_timeout(400)
        except Exception as e:
            print('[%02d] ERR %s -> %s' % (i, m['name'], str(e)[:140]))
            pg.evaluate("() => { const b=document.querySelector('[data-act=\"close-modal\"]'); if(b) b.click(); }")
            pg.wait_for_timeout(400)

    print('\n补齐结果 %d / %d' % (ok, len(MEDS)))
    print(json.dumps(pg.evaluate("""() => ({
      cards: [...document.querySelectorAll('.med-stats .ms-card')].map(c=>c.textContent.replace(/\\s+/g,' ').trim()),
      rows: document.querySelectorAll('.med-row').length
    })"""), ensure_ascii=False, indent=1))
    print('errs=', errs[:3])
    pg.screenshot(path='design/shots/live-02-meds.png', full_page=True)
    br.close()
