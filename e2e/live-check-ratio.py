"""线上测试 · 阶段 4：今日页打卡 + 完成率核算 + 统计页达标率 + 刷新持久化"""
import json
from playwright.sync_api import sync_playwright

BASE = 'https://your-domain.example/'
EMAIL = 'test@example.com'
PWD = 'test@example.com'

HERO = """() => {
  const q = s => document.querySelector(s);
  const t = e => e ? e.textContent.replace(/\\s+/g, ' ').trim() : '';
  return {
    sub: t(q('.hero-sub')),
    chips: [...document.querySelectorAll('.hero-chips > *')].map(e => t(e)),
    pct: t(q('.hero-pct b')),
    pctLabel: t(q('.hero-pct small')),
    weekAvg: t(q('.hero-week b')),
    weekMeta: [...document.querySelectorAll('.hero-week .hw-meta, .hero-week small')].map(e => t(e)),
    todayStat: t(q('.hstat, .day-stat'))
  };
}"""

CARDS = """() => [...document.querySelectorAll('[data-act="habit-inc"], [data-act="habit-dec"]')].map(b => {
  let n = b, txt = '';
  for (let i = 0; i < 6 && n; i++) {
    n = n.parentElement;
    if (!n) break;
    const tt = n.textContent || '';
    if (tt.trim().length > 6) { txt = tt.replace(/\\s+/g, ' ').trim(); }
  }
  return { id: b.dataset.id, act: b.dataset.act, txt: txt.slice(0, 60) };
})"""

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
    pg.wait_for_timeout(4000)

    print('=== 打卡前 ===')
    h0 = pg.evaluate(HERO)
    print(json.dumps(h0, ensure_ascii=False, indent=1))

    print('\n=== 习惯卡 → id 映射 ===')
    cards = pg.evaluate(CARDS)
    for c in cards:
        print('  %-14s %-10s %s' % (c['id'], c['act'], c['txt'][:52]))

    # 找到两个新习惯的 id
    def find_id(keyword):
        for c in cards:
            if keyword in c['txt']:
                return c['id']
        return None

    h_warm = find_id('早起喝温水')
    h_stretch = find_id('睡前拉伸')
    print('\n早起喝温水 id =', h_warm, '| 睡前拉伸 id =', h_stretch)

    # ---- 打卡：两个新习惯 ----
    for label, hid in (('早起喝温水', h_warm), ('睡前拉伸', h_stretch)):
        if not hid:
            print('SKIP (未找到)', label); continue
        pg.click('[data-act="habit-inc"][data-id="%s"]' % hid)
        pg.wait_for_timeout(1200)
        print('已打卡:', label)

    # ---- 喝水 3 杯 ----
    for i in range(3):
        pg.click('[data-act="habit-inc"][data-id="h_water"]')
        pg.wait_for_timeout(1100)
    print('已喝水 3 杯')

    print('\n=== 打卡后 ===')
    h1 = pg.evaluate(HERO)
    print(json.dumps(h1, ensure_ascii=False, indent=1))

    water = pg.evaluate("""() => {
      const c = [...document.querySelectorAll('.vital-card')].find(x => (x.textContent||'').includes('喝水'));
      if (!c) return null;
      return { num: (c.querySelector('.vnum')||{}).textContent||'',
               sub: (c.querySelector('.vital-sub')||{}).textContent||'',
               steps: c.querySelectorAll('.water-steps i.on').length,
               pace: (c.querySelector('.water-pace')||{}).textContent||'' };
    }""")
    print('喝水卡 =', json.dumps(water, ensure_ascii=False))
    pg.screenshot(path='design/shots/live-05-today-after-checkin.png', full_page=True)

    # ---- 统计页 ----
    pg.evaluate("""() => { const b=document.querySelector('.nav-item[data-nav="stats"]'); if(b) b.click(); }""")
    pg.wait_for_timeout(1400)
    stats = pg.evaluate("""() => {
      const q = s => document.querySelector(s);
      const t = e => e ? e.textContent.replace(/\\s+/g, ' ').trim() : '';
      const pick = (label) => {
        const rows = [...document.querySelectorAll('.hstat, .hstat-row, .stat-row')];
        const r = rows.find(x => (x.textContent||'').includes(label));
        return r ? t(r) : '';
      };
      return {
        ranges: [...document.querySelectorAll('.range-switch button, [data-act="set-stats-range"]')].map(e=>t(e)),
        activeRange: t(q('.range-switch button.active, [data-act="set-stats-range"].active')),
        topCards: [...document.querySelectorAll('.stat-card, .scard, .stats-top > *')].map(e=>t(e)).slice(0, 8),
        summary: [...document.querySelectorAll('.cal-summary span')].map(e=>t(e)),
        hstats: [...document.querySelectorAll('.hstat')].map(e=>t(e)).slice(0, 16),
        taskPanel: t(q('#main .panel:last-child'))
      };
    }""")
    print('\n=== 统计页 ===')
    print(json.dumps(stats, ensure_ascii=False, indent=1))
    pg.screenshot(path='design/shots/live-06-stats.png', full_page=True)

    # ---- 刷新验证持久化 ----
    pg.reload(wait_until='networkidle')
    pg.wait_for_timeout(3000)
    h2 = pg.evaluate(HERO)
    print('\n=== 刷新后 ===')
    print('pct =', h2['pct'], '| chips =', h2['chips'])
    persist = pg.evaluate("""() => ({
      view: document.body.dataset.view,
      water: (() => { const c=[...document.querySelectorAll('.vital-card')].find(x=>(x.textContent||'').includes('喝水')); return c ? (c.querySelector('.vnum')||{}).textContent : null; })()
    })""")
    print('persist =', json.dumps(persist, ensure_ascii=False))
    print('errs=', errs[:3])
    br.close()
