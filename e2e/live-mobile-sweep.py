"""线上测试 · 阶段 5：移动端（390 / 360）全页面巡检"""
import json
from playwright.sync_api import sync_playwright

BASE = 'https://todo.csl88.top/'
EMAIL = 'test@sl00.top'
PWD = 'test@sl00.top'

PAGES = ['today', 'meds', 'board', 'essays', 'weight', 'habits', 'calendar', 'stats', 'settings']

PROBE = """() => {
  const t = e => e ? e.textContent.replace(/\\s+/g, ' ').trim() : '';
  return {
    view: document.body.dataset.view,
    ovf: document.documentElement.scrollWidth - window.innerWidth,
    h1: t(document.querySelector('#main h2')),
    pct: t(document.querySelector('.hero-pct b')),
    habitCards: document.querySelectorAll('.habit-card, .vital-card').length,
    taskRows: document.querySelectorAll('.task, .task-row').length,
    medRows: document.querySelectorAll('.med-row').length,
    msCards: document.querySelectorAll('.ms-card').length,
    essayItems: [...document.querySelectorAll('.essay-item, .essay-card, .essay-row')].length,
    essayTitles: [...document.querySelectorAll('.essay-item h4, .essay-item b, .essay-card h4')].map(e => t(e)).slice(0, 4),
    wwDots: document.querySelectorAll('.ww-dot').length,
    wsum: document.querySelectorAll('.wsum-row').length,
    habitRows: document.querySelectorAll('.habit-row').length,
    calCells: document.querySelectorAll('.cal-cell, .cal-day, .heat-cell').length,
    hstat: document.querySelectorAll('.hstat').length,
    text: (document.querySelector('#main').textContent || '').replace(/\\s+/g, ' ').length
  };
}"""


def nav(pg, key):
    pg.evaluate("""(k) => {
      const b = document.querySelector('[data-nav="' + k + '"]');
      if (b) b.click();
    }""", key)
    pg.wait_for_timeout(900)


with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)
    results = []

    for w, h in ((390, 844), (360, 780)):
        ctx = br.new_context(viewport={'width': w, 'height': h}, is_mobile=True, has_touch=True, device_scale_factor=2)
        pg = ctx.new_page()
        errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)[:160]))
        pg.on('console', lambda m: errs.append('console: ' + m.text[:120]) if m.type == 'error' else None)
        pg.on('dialog', lambda d: d.accept())

        pg.goto(BASE, wait_until='networkidle', timeout=60000)
        pg.wait_for_timeout(1500)
        pg.click('[data-act="cloud-login"]'); pg.wait_for_timeout(700)
        pg.fill('input[name="email"]', EMAIL)
        pg.fill('input[name="password"]', PWD)
        pg.click('form.modal-card button[type="submit"]')
        pg.wait_for_timeout(4500)

        print('\n===== %dx%d =====' % (w, h))
        for key in PAGES:
            nav(pg, key)
            r = pg.evaluate(PROBE)
            ok = r['ovf'] <= 0
            results.append((w, key, ok, r['ovf']))
            print('  %-9s view=%-8s ovf=%3d  cards=%d tasks=%d meds=%d ms=%d dots=%d rows=%d hstat=%d text=%d' % (
                key, r['view'], r['ovf'], r['habitCards'], r['taskRows'], r['medRows'],
                r['msCards'], r['wwDots'], r['habitRows'], r['hstat'], r['text']))
            if key in ('today', 'meds', 'board', 'stats', 'weight'):
                pg.screenshot(path='design/shots/live-m%d-%s.png' % (w, key))

        print('  essays =', json.dumps(pg.evaluate("""() => [...document.querySelectorAll('#main')].map(e=>e.textContent).join(' ').slice(0,0)"""), ensure_ascii=False))
        # 随笔标题单独核对
        nav(pg, 'essays')
        txt = pg.evaluate("() => (document.querySelector('#main').textContent || '')")
        print('  随笔 1:', '十月的最后一周' in txt, '| 随笔 2:', '关于早睡这件事' in txt)
        nav(pg, 'weight')
        print('  体重图点数:', pg.evaluate("() => document.querySelectorAll('.ww-dot').length"))
        print('  JS errors:', errs[:3] if errs else 'none')
        ctx.close()

    br.close()

bad = [r for r in results if not r[2]]
print('\n横向溢出检查：%d/%d 通过' % (len(results) - len(bad), len(results)))
if bad:
    for b in bad:
        print('  溢出 %dpx @ %dx %s' % (b[3], b[0], b[1]))
