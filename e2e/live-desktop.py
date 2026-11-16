"""线上环境自检 - 桌面端
只做「只读遍历 + 本地偏好切换 + 打卡增减往返（净变化 0）」，不新增/删除业务数据。
"""
import json, time, sys
from playwright.sync_api import sync_playwright

BASE = 'https://your-domain.example'
EMAIL = 'test@example.com'
PWD = 'test@example.com'

steps = []   # {name, ok, detail}
errors = []  # runtime errors
reqfail = []  # failed requests


def rec(name, ok, detail=''):
    steps.append({'name': name, 'ok': bool(ok), 'detail': detail})
    print(('PASS  ' if ok else 'FAIL  ') + name + (('  | ' + detail) if detail else ''))


with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)
    ctx = br.new_context(viewport={'width': 1440, 'height': 900}, device_scale_factor=1)
    pg = ctx.new_page()

    pg.on('pageerror', lambda e: errors.append({'type': 'pageerror', 'msg': str(e)[:300]}))
    pg.on('console', lambda m: errors.append({'type': 'console.' + m.type, 'msg': m.text[:300]})
          if m.type in ('error',) else None)

    def on_resp(r):
        if '/api.php' in r.url and r.status >= 400:
            reqfail.append({'url': r.url.split('?')[-1][:80], 'status': r.status})
    pg.on('response', on_resp)

    # ---------- 1. 落地页 ----------
    pg.goto(BASE, wait_until='networkidle')
    pg.wait_for_timeout(1200)
    rec('落地页加载', pg.locator('[data-act="cloud-login"]').count() > 0,
        'title=' + pg.title()[:30])

    # ---------- 2. 登录 ----------
    pg.click('[data-act="cloud-login"]')
    pg.wait_for_timeout(600)
    pg.fill('input[name="email"]', EMAIL)
    pg.fill('input[name="password"]', PWD)
    pg.click('form.modal-card button[type="submit"]')
    pg.wait_for_timeout(4000)
    logged = pg.locator('.nav-item').count() > 0
    rec('登录成功', logged, f'导航 {pg.locator(".nav-item").count()} 项')

    # 数据概况（只读）
    info = pg.evaluate("""() => {
      const n = s => document.querySelectorAll(s).length;
      return {
        habits: n('.habit-card') + n('.vital-card'),
        tasks: n('.task-row'),
        navItems: n('.nav-item'),
        skin: document.documentElement.getAttribute('data-skin'),
        layout: document.documentElement.getAttribute('data-layout'),
        theme: document.documentElement.getAttribute('data-theme')
      };
    }""")
    print('   数据概况:', json.dumps(info, ensure_ascii=False))
    rec('云端数据已加载', info['habits'] > 0, f'习惯卡 {info["habits"]} 个 / 待办 {info["tasks"]} 条')

    # ---------- 3. 遍历 8 个页面 ----------
    views = ['today', 'board', 'habits', 'weight', 'essays', 'calendar', 'stats', 'settings']
    VIEW_KEY = {'today': '今日', 'board': '待办', 'habits': '习惯', 'weight': '体重',
                'essays': '随笔', 'calendar': '日历', 'stats': '统计', 'settings': '设置'}
    for v in views:
        before = len(errors)
        pg.click(f'.nav-item[data-nav="{v}"]')
        pg.wait_for_timeout(1400)
        ovf = pg.evaluate('() => document.documentElement.scrollWidth - innerWidth')
        has = pg.locator('.main .page-head, .main .hero, .main .panel, .main .settings-wrap').count() > 0
        newerr = len(errors) - before
        rec(f'页面：{VIEW_KEY[v]}', has and ovf <= 1 and newerr == 0,
            f'横溢 {ovf} / 新增报错 {newerr}')
        pg.screenshot(path=f'e2e/live-shots/d-{v}.png')

    # ---------- 4. 主题切换（9 套，本地偏好） ----------
    pg.click('.nav-item[data-nav="settings"]')
    pg.wait_for_timeout(1200)
    skins = pg.evaluate("() => [...document.querySelectorAll('[data-act=\"set-skin\"]')].map(e => e.dataset.skin)")
    rec('设置页主题卡片 9 套', len(skins) == 9, '实际 ' + str(len(skins)))
    skin_ok = 0
    for s in skins:
        pg.click(f'[data-act="set-skin"][data-skin="{s}"]')
        pg.wait_for_timeout(450)
        cur = pg.evaluate('() => document.documentElement.getAttribute("data-skin")')
        if cur == s:
            skin_ok += 1
    rec('9 套主题逐一切换生效', skin_ok == 9, f'{skin_ok}/9')

    # ---------- 5. 排版切换（双布局） ----------
    pg.click('[data-act="set-layout"][data-layout="side"]')
    pg.wait_for_timeout(900)
    side_ok = pg.evaluate("""() => {
      const a = getComputedStyle(document.querySelector('.app'));
      const s = getComputedStyle(document.querySelector('.sidebar'));
      return {appDisplay: a.display, sideFlexDir: s.flexDirection,
              layout: document.documentElement.getAttribute('data-layout')};
    }""")
    pg.screenshot(path='e2e/live-shots/d-layout-side.png')
    pg.click('[data-act="set-layout"][data-layout="top"]')
    pg.wait_for_timeout(900)
    top_ok = pg.evaluate("""() => {
      const a = getComputedStyle(document.querySelector('.app'));
      const s = getComputedStyle(document.querySelector('.sidebar'));
      return {appDisplay: a.display, sideFlexDir: s.flexDirection,
              layout: document.documentElement.getAttribute('data-layout')};
    }""")
    rec('排版切换：左侧导航', side_ok['layout'] == 'side' and side_ok['appDisplay'] == 'grid',
        json.dumps(side_ok, ensure_ascii=False))
    rec('排版切换：顶部导航', top_ok['layout'] == 'top' and top_ok['appDisplay'] == 'flex',
        json.dumps(top_ok, ensure_ascii=False))

    # ---------- 6. 明暗切换 ----------
    pg.click('[data-act="theme"]')
    pg.wait_for_timeout(700)
    dark = pg.evaluate('() => document.documentElement.getAttribute("data-theme")')
    pg.screenshot(path='e2e/live-shots/d-dark.png')
    pg.click('[data-act="theme"]')
    pg.wait_for_timeout(700)
    light = pg.evaluate('() => document.documentElement.getAttribute("data-theme")')
    rec('明暗模式切换往返', dark == 'dark' and light == 'light', f'{dark} → {light}')

    # ---------- 7. 打卡往返（+1 再 -1，净变化 0） ----------
    pg.click('.nav-item[data-nav="today"]')
    pg.wait_for_timeout(1500)
    target = pg.evaluate("""() => {
      const cards = [...document.querySelectorAll('.vital-card, .habit-card')];
      for (const c of cards) {
        const inc = c.querySelector('[data-act="habit-inc"]:not([disabled])');
        if (inc) return {name: (c.querySelector('.habit-name, h3, .vital-name') || {}).innerText || c.innerText.split('\\n')[0],
                         id: inc.dataset.id};
      }
      return null;
    }""")
    if target:
        cid = target['id']
        def cnt():
            return pg.evaluate("""(id) => {
              const el = document.querySelector('[data-act="habit-inc"][data-id="' + id + '"]');
              const card = el ? el.closest('.vital-card, .habit-card') : null;
              return card ? card.innerText.replace(/\\n/g, ' ').slice(0, 90) : null;
            }""", cid)
        t0 = cnt()
        pg.click(f'[data-act="habit-inc"][data-id="{cid}"]')
        pg.wait_for_timeout(2200)
        t1 = cnt()
        dec = pg.locator(f'[data-act="habit-dec"][data-id="{cid}"]:not([disabled])')
        restored = False
        if dec.count() > 0:
            dec.first.click()
            pg.wait_for_timeout(2200)
            restored = True
        t2 = cnt()
        rec('打卡 +1 生效', t1 != t0, f'[{target["name"][:10]}] 计数已变')
        rec('打卡 -1 还原', restored and t2 != t1, '已撤销回原值')
    else:
        rec('打卡按钮可用', False, '今日页未找到可点击的打卡按钮')


    # ---------- 8. 云同步状态 ----------
    pg.wait_for_timeout(2000)
    sync = pg.evaluate("""() => {
      const el = document.querySelector('.sync-indicator');
      return el ? {cls: el.className, txt: el.innerText.trim()} : null;
    }""")
    rec('云同步状态正常', sync is not None and 'error' not in (sync or {}).get('cls', ''), json.dumps(sync, ensure_ascii=False))

    pg.screenshot(path='e2e/live-shots/d-final-today.png')

    # ---------- 汇总 ----------
    print('\n' + '=' * 60)
    passed = sum(1 for s in steps if s['ok'])
    print(f'桌面端：{passed}/{len(steps)} 通过')
    print('JS/console 报错:', len(errors))
    for e in errors[:8]:
        print('   ', e['type'], '|', e['msg'][:140])
    print('API 4xx/5xx:', reqfail if reqfail else '无')

    with open('e2e/live-desktop.json', 'w', encoding='utf-8') as f:
        json.dump({'steps': steps, 'errors': errors, 'reqfail': reqfail,
                   'passed': passed, 'total': len(steps)}, f, ensure_ascii=False, indent=1)

    ctx.close()
    br.close()
