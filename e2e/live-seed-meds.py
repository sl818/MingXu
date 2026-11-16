"""线上测试 · 阶段 1：创建 15 条用药（长期 5 / 短期 5 / 按需 5）"""
import sys, json
from playwright.sync_api import sync_playwright

BASE = 'https://your-domain.example/'
EMAIL = 'test@example.com'
PWD = 'test@example.com'

# course: long / short / prn
MEDS = [
    # ---- 长期 5 条 ----
    dict(course='long', name='左甲状腺素钠片', purpose='西药', form='片', strength='50μg',
         amount='1', unit='片', times=['06:30'], meal='empty', mealOff='30',
         start='2026-09-01', review='2026-11-20', stock='30', maker='默克', info='晨起空腹，服后 30 分钟再进食'),
    dict(course='long', name='二甲双胍缓释片', purpose='西药', form='片', strength='0.5g',
         amount='1', unit='片', times=['08:00', '20:00'], meal='with', mealOff='',
         start='2026-08-15', review='2026-11-15', stock='60', maker='中美上海施贵宝', info='缓释片需整片吞服，不可掰开'),
    dict(course='long', name='苯磺酸氨氯地平片', purpose='西药', form='片', strength='5mg',
         amount='1', unit='片', times=['08:30'], meal='after', mealOff='30',
         start='2026-07-10', review='2026-11-10', stock='28', maker='辉瑞', info='降压药，需固定时间服用'),
    dict(course='long', name='维生素D3滴剂', purpose='维生素', form='口服液', strength='400IU/滴',
         amount='2', unit='滴', times=['12:30'], meal='after', mealOff='0',
         start='2026-09-20', review='', stock='20', maker='星鲨', info='随餐服用吸收更好'),
    dict(course='long', name='阿托伐他汀钙片', purpose='西药', form='片', strength='20mg',
         amount='1', unit='片', times=['22:00'], meal='', mealOff='',
         start='2026-06-01', review='2026-12-01', stock='28', maker='辉瑞', info='睡前服用，避免与西柚同服'),

    # ---- 短期疗程 5 条 ----
    dict(course='short', name='阿莫西林胶囊', purpose='抗生素', form='胶囊', strength='0.25g',
         amount='2', unit='粒', times=['08:00', '14:00', '20:00'], meal='after', mealOff='30',
         start='2026-10-20', end='2026-10-26', stock='42', maker='华北制药', info='必须吃完整个疗程'),
    dict(course='short', name='布洛芬缓释胶囊', purpose='消炎药', form='胶囊', strength='0.3g',
         amount='1', unit='粒', times=['09:00', '21:00'], meal='after', mealOff='15',
         start='2026-10-22', end='2026-10-26', stock='10', maker='芬必得', info='止痛，连续服用不超过 5 天'),
    dict(course='short', name='蒙脱石散', purpose='西药', form='袋', strength='3g',
         amount='1', unit='袋', times=['07:30', '13:00', '19:00'], meal='empty', mealOff='60',
         start='2026-10-23', end='2026-10-25', stock='9', maker='博福-益普生', info='与其他药间隔 1 小时以上'),
    dict(course='short', name='头孢克肟片', purpose='抗生素', form='片', strength='0.1g',
         amount='1', unit='片', times=['08:00', '20:00'], meal='after', mealOff='30',
         start='2026-10-21', end='2026-10-27', stock='14', maker='广州白云山', info='服药期间禁止饮酒'),
    dict(course='short', name='奥美拉唑肠溶胶囊', purpose='西药', form='胶囊', strength='20mg',
         amount='1', unit='粒', times=['07:30'], meal='before', mealOff='30',
         start='2026-10-18', end='2026-10-31', stock='14', maker='阿斯利康', info='晨起空腹，餐前 30 分钟'),

    # ---- 按需 5 条 ----
    dict(course='prn', name='布洛芬片', purpose='消炎药', form='片', strength='0.2g',
         amount='1', unit='片', start='2026-09-01', stock='12', maker='中美史克', info='头痛或发热时服用，24 小时不超过 4 次'),
    dict(course='prn', name='氯雷他定片', purpose='西药', form='片', strength='10mg',
         amount='1', unit='片', start='2026-08-01', stock='6', maker='拜耳', info='过敏发作时服用，每日最多 1 次'),
    dict(course='prn', name='铝碳酸镁咀嚼片', purpose='西药', form='片', strength='0.5g',
         amount='2', unit='片', start='2026-07-15', stock='20', maker='拜耳', info='胃部不适时嚼服'),
    dict(course='prn', name='沙丁胺醇气雾剂', purpose='西药', form='其他', strength='100μg/揿',
         amount='2', unit='揿', start='2026-05-01', stock='200', maker='葛兰素史克', info='喘息发作时使用，随身携带'),
    dict(course='prn', name='口服补液盐Ⅲ', purpose='西药', form='袋', strength='5.125g',
         amount='1', unit='袋', start='2026-10-01', stock='8', maker='西安安健', info='腹泻脱水时冲服，每袋兑 250ml 温水'),
]


def fill(pg, form, name, value):
    if value is None or value == '':
        return
    sel = form.locator('[name="%s"]' % name)
    if sel.count() == 0:
        return
    tag = sel.first.evaluate('e => e.tagName.toLowerCase()')
    if tag == 'select':
        sel.first.select_option(str(value))
    else:
        sel.first.fill(str(value))


with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)
    ctx = br.new_context(viewport={'width': 1680, 'height': 1000})
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)[:200]))
    pg.on('console', lambda m: errs.append('console: ' + m.text[:150]) if m.type == 'error' else None)
    pg.on('dialog', lambda d: (print('DIALOG:', d.message[:120]), d.accept()))

    pg.goto(BASE, wait_until='networkidle', timeout=60000)
    pg.wait_for_timeout(1200)
    pg.click('[data-act="cloud-login"]'); pg.wait_for_timeout(700)
    pg.fill('input[name="email"]', EMAIL)
    pg.fill('input[name="password"]', PWD)
    pg.click('form.modal-card button[type="submit"]')
    pg.wait_for_timeout(3500)
    print('logged in, view =', pg.evaluate("() => document.body.dataset.view"))

    pg.evaluate("""() => { const b = document.querySelector('.nav-item[data-nav="meds"]'); if (b) b.click(); }""")
    pg.wait_for_timeout(1000)
    print('meds view =', pg.evaluate("() => document.body.dataset.view"))

    ok = 0
    for i, m in enumerate(MEDS, 1):
        try:
            pg.click('[data-act="med-new"]')
            pg.wait_for_timeout(500)
            form = pg.locator('#med-form')
            if form.count() == 0:
                print('[%02d] FAIL no form' % i); continue
            fill(pg, form, 'name', m['name'])
            fill(pg, form, 'purpose', m.get('purpose'))
            fill(pg, form, 'form', m.get('form'))
            fill(pg, form, 'strength', m.get('strength'))
            fill(pg, form, 'doseAmount', m.get('amount'))
            fill(pg, form, 'doseUnit', m.get('unit'))
            fill(pg, form, 'courseType', m['course'])
            pg.wait_for_timeout(220)
            if m['course'] != 'prn':
                fill(pg, form, 'doseTimes', '%d 次' % len(m['times']))
                pg.wait_for_timeout(260)
                for k, tm in enumerate(m['times'], 1):
                    el = pg.locator('#time-slots input').nth(k - 1)
                    el.fill(tm)
                if m.get('meal'):
                    fill(pg, form, 'mealTiming', m['meal'])
                    pg.wait_for_timeout(200)
                    if m.get('mealOff') != '':
                        fill(pg, form, 'mealOffset', m['mealOff'])
            fill(pg, form, 'status', 'active')
            fill(pg, form, 'startDate', m.get('start'))
            if m['course'] == 'short':
                fill(pg, form, 'endDate', m.get('end'))
            else:
                fill(pg, form, 'reviewDate', m.get('review'))
            fill(pg, form, 'stock', m.get('stock'))
            fill(pg, form, 'manufacturer', m.get('maker'))
            fill(pg, form, 'medInfo', m.get('info'))
            pg.wait_for_timeout(120)
            pg.click('#med-form button[type="submit"]')
            pg.wait_for_timeout(1100)
            shown = pg.evaluate("(n) => document.querySelector('#main').textContent.includes(n)", m['name'])
            if shown:
                ok += 1
                print('[%02d] OK  %s (%s)' % (i, m['name'], m['course']))
            else:
                print('[%02d] FAIL not shown: %s' % (i, m['name']))
                pg.screenshot(path='design/shots/live-med-fail-%02d.png' % i)
                pg.evaluate("() => { const b=document.querySelector('[data-act=\"close-modal\"]'); if(b) b.click(); }")
                pg.wait_for_timeout(300)
        except Exception as e:
            print('[%02d] ERR  %s -> %s' % (i, m['name'], str(e)[:160]))
            pg.evaluate("() => { const b=document.querySelector('[data-act=\"close-modal\"]'); if(b) b.click(); }")
            pg.wait_for_timeout(300)

    print('\ncreated %d / %d' % (ok, len(MEDS)))
    stats = pg.evaluate("""() => {
      const q = s => document.querySelector(s);
      return {
        cards: [...document.querySelectorAll('.med-stats .ms-card')].map(c => c.textContent.replace(/\\s+/g,' ').trim()),
        rows: document.querySelectorAll('.med-row').length,
        groups: [...document.querySelectorAll('.med-group h3, .med-group-head')].map(e=>e.textContent.trim())
      };
    }""")
    print(json.dumps(stats, ensure_ascii=False, indent=1))
    print('errs=', errs[:3])
    pg.screenshot(path='design/shots/live-02-meds.png', full_page=True)
    br.close()
