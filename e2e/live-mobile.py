"""线上环境自检 - 手机端（390 / 360 两档）
只读遍历 + 局部布局测量，不做业务数据写入。
"""
import json
from playwright.sync_api import sync_playwright

BASE = 'https://todo.csl88.top'
EMAIL = 'test@sl00.top'
PWD = 'test@sl00.top'

steps, errors, reqfail = [], [], []


def rec(name, ok, detail=''):
    steps.append({'name': name, 'ok': bool(ok), 'detail': detail})
    print(('PASS  ' if ok else 'FAIL  ') + name + (('  | ' + detail) if detail else ''))


MEASURE_HERO = """() => {
  const g = s => document.querySelector(s);
  const ring = g('.hero-ring'), b = g('.hero-pct b'), sm = g('.hero-pct small');
  if (!ring) return null;
  const rb = ring.getBoundingClientRect(), bb = b.getBoundingClientRect(), sb = sm.getBoundingClientRect();
  const inner = rb.width * (1 - 2 * 8 / 116);
  const dateEl = g('.hero-date'), h1 = g('.hero h1'), chips = g('.hero-chips');
  const fs = parseFloat(getComputedStyle(dateEl).fontSize);
  const h1fs = parseFloat(getComputedStyle(h1).fontSize);
  return {
    ringW: Math.round(rb.width), inner: Math.round(inner),
    pctText: b.innerText, pctW: Math.round(bb.width),
    labelText: sm.innerText, labelW: Math.round(sb.width),
    pctFits: bb.width <= inner - 2, labelFits: sb.width <= inner - 2,
    dateRows: Math.round(dateEl.getBoundingClientRect().height / (fs * 1.7)),
    titleRows: Math.round(h1.getBoundingClientRect().height / (h1fs * 1.26)),
    chipsRows: Math.round(chips.getBoundingClientRect().height / 27),
    heroH: Math.round(g('.hero').getBoundingClientRect().height)
  };
}"""

SCAN = """() => {
  const over = [];
  document.querySelectorAll('.main *, .mobile-tabbar *').forEach(e => {
    const r = e.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) return;
    if (r.right > innerWidth + 1 || r.left < -1) {
      over.push({cls: (e.className && e.className.baseVal !== undefined ? e.className.baseVal : e.className || e.tagName).toString().slice(0, 36),
                 l: Math.round(r.left), r: Math.round(r.right)});
    }
  });
  const clipped = [];
  document.querySelectorAll('.main *').forEach(e => {
    if (e.children.length || !(e.innerText || '').trim()) return;
    if (e.scrollWidth > e.clientWidth + 2 && getComputedStyle(e).overflow !== 'visible')
      clipped.push({cls: (e.className || e.tagName).toString().slice(0, 30), t: e.innerText.trim().slice(0, 18)});
  });
  return {ovf: document.documentElement.scrollWidth - innerWidth,
          overCount: over.length, over: over.slice(0, 4),
          clippedCount: clipped.length, clipped: clipped.slice(0, 4)};
}"""

with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)
    for W in (390, 360):
        ctx = br.new_context(viewport={'width': W, 'height': 844}, device_scale_factor=2,
                             is_mobile=True, has_touch=True,
                             user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1')
        pg = ctx.new_page()
        pg.on('pageerror', lambda e: errors.append({'w': W, 'msg': str(e)[:200]}))
        pg.on('console', lambda m: errors.append({'w': W, 'msg': m.text[:200]}) if m.type == 'error' else None)
        pg.on('response', lambda r: reqfail.append({'w': W, 'u': r.url.split('?')[-1][:60], 's': r.status})
              if '/api.php' in r.url and r.status >= 400 else None)

        pg.goto(BASE, wait_until='networkidle')
        pg.wait_for_timeout(1000)
        pg.click('[data-act="cloud-login"]')
        pg.wait_for_timeout(600)
        pg.fill('input[name="email"]', EMAIL)
        pg.fill('input[name="password"]', PWD)
        pg.click('form.modal-card button[type="submit"]')
        pg.wait_for_timeout(4000)

        # Hero 测量
        m = pg.evaluate(MEASURE_HERO)
        if m:
            rec(f'[{W}] Hero 圆环尺寸', m['ringW'] >= 70, f'{m["ringW"]}px（内径≈{m["inner"]}px）')
            rec(f'[{W}] 圆环数字不溢出', m['pctFits'], f'"{m["pctText"]}" {m["pctW"]}px')
            rec(f'[{W}] 圆环标签不溢出', m['labelFits'], f'"{m["labelText"]}" {m["labelW"]}px')
            rec(f'[{W}] 日期行单行', m['dateRows'] <= 1, f'{m["dateRows"]} 行')
            rec(f'[{W}] 标题行数合理', m['titleRows'] <= 2, f'{m["titleRows"]} 行')
            rec(f'[{W}] chips 单行', m['chipsRows'] <= 1, f'{m["chipsRows"]} 行')
            print(f'    Hero: ring={m["ringW"]} inner={m["inner"]} 100%={m["pctW"]} label={m["labelW"]} H={m["heroH"]}')
        else:
            rec(f'[{W}] Hero 渲染', False, '未找到 .hero-ring')

        # tabbar
        tabs = pg.locator('.mobile-tab').count()
        rec(f'[{W}] 底部 tabbar 5 项', tabs == 5, f'{tabs} 项')

        # 主页面遍历
        views = [('today', '今日'), ('board', '待办'), ('habits', '习惯'), ('stats', '统计'), ('more', '更多')]
        for v, label in views:
            try:
                pg.click(f'.mobile-tab:has-text("{label}")')
                pg.wait_for_timeout(1200)
                r = pg.evaluate(SCAN)
                ok = r['ovf'] <= 1 and r['overCount'] == 0 and r['clippedCount'] == 0
                rec(f'[{W}] 页面：{label}', ok, f'横溢{r["ovf"]} 越界{r["overCount"]} 裁切{r["clippedCount"]}')
                if not ok and r['over']:
                    print('       over:', json.dumps(r['over'], ensure_ascii=False))
                pg.screenshot(path=f'e2e/live-shots/m{W}-{v}.png')
            except Exception as e:
                rec(f'[{W}] 页面：{label}', False, str(e)[:80])

        # 更多页子页面
        for sub, label in [('calendar', '日历'), ('weight', '体重'), ('essays', '随笔'), ('settings', '设置')]:
            try:
                pg.click('.mobile-tab:has-text("更多")')
                pg.wait_for_timeout(700)
                pg.click(f'.more-card[data-nav="{sub}"]')
                pg.wait_for_timeout(1200)
                r = pg.evaluate(SCAN)
                ok = r['ovf'] <= 1 and r['overCount'] == 0 and r['clippedCount'] == 0
                rec(f'[{W}] 页面：{label}', ok, f'横溢{r["ovf"]} 越界{r["overCount"]} 裁切{r["clippedCount"]}')
                pg.screenshot(path=f'e2e/live-shots/m{W}-{sub}.png')
            except Exception as e:
                rec(f'[{W}] 页面：{label}', False, str(e)[:80])

        ctx.close()
    br.close()

print('\n' + '=' * 60)
passed = sum(1 for s in steps if s['ok'])
print(f'手机端：{passed}/{len(steps)} 通过')
print('JS/console 报错:', len(errors))
for e in errors[:8]:
    print('   ', e)
print('API 4xx/5xx:', reqfail if reqfail else '无')

with open('e2e/live-mobile.json', 'w', encoding='utf-8') as f:
    json.dump({'steps': steps, 'errors': errors, 'reqfail': reqfail,
               'passed': passed, 'total': len(steps)}, f, ensure_ascii=False, indent=1)
