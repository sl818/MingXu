# -*- coding: utf-8 -*-
"""v99：云系两主题（浮纸 / 聚光）+ 已删主题的回落

v99 删掉「雾蓝 · 云水」mist 与「云晕 · 柔光」cloud-haze。
锁五件事：
  1. 留下的两套都能从首屏白名单生效
  2. 基座选择器 `[data-skin^="cloud-"]` 真的生效（--bg / 干净渐变 / .app 层）
  3. 两套差异成立：留白空着 + 卡片浮起 / 四周晕影；**都没有 v95 的竖向细纹**
  4. 设置页 6 张主题卡、点击切换 + 记住偏好、深色与窄屏表现
  5. 旧键 mist / cloud-haze 一律回落 paper，皮肤 CSS 不再被引用

用法：python e2e/verify-cloud-skins.py
"""
import os
import sys

ROOT = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo'
head = open(os.path.join(ROOT, 'e2e', 'verify-batch4.py'), encoding='utf-8').read().split('with sync_playwright() as p:')[0]
sys.argv = [sys.argv[0]]
exec(head)

from playwright.sync_api import sync_playwright

PASS = FAIL = 0
FAILS = []


def chk(name, ok, detail=''):
    global PASS, FAIL
    if ok:
        PASS += 1
        print('  \u2713 %s' % name)
    else:
        FAIL += 1
        FAILS.append(name)
        print('  \u2717 %s  << %s' % (name, detail))


SKINS = {
    'cloud-float': {'bg': '#dfe6ee', 'before': '',                'after': ''},
    'cloud-focus': {'bg': '#e3eaf2', 'before': 'radial-gradient', 'after': 'linear-gradient'},
}
DECOR = {}

PROBE = """() => {
  const r = getComputedStyle(document.documentElement);
  const b = getComputedStyle(document.body);
  return {
    skin: document.documentElement.dataset.skin,
    theme: document.documentElement.dataset.theme,
    bg: r.getPropertyValue('--bg').trim(),
    text: r.getPropertyValue('--text').trim(),
    bodyBg: b.backgroundImage,
    before: getComputedStyle(document.body, '::before').backgroundImage,
    after: getComputedStyle(document.body, '::after').backgroundImage,
    appZ: getComputedStyle(document.querySelector('.app') || document.body).zIndex,
    cards: [...document.querySelectorAll('[data-act="set-skin"]')].map(e => e.dataset.skin)
  };
}"""


def open_page(pg, skin, theme='light', w=1600):
    pg.set_viewport_size({'width': w, 'height': 950})
    pg.add_init_script(
        "try{localStorage.setItem('lifeboard.skin','%s');"
        "localStorage.setItem('lifeboard.layout','top');"
        "localStorage.setItem('lifeboard.theme.mode','%s');}catch(e){}" % (skin, theme))
    pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
    pg.wait_for_timeout(700)
    if pg.locator('[data-act="cloud-login"]').count():
        pg.locator('[data-act="cloud-login"]').first.click()
        pg.wait_for_timeout(600)
        pg.fill('input[name="email"]', 'test@sl00.top')
        pg.fill('input[name="password"]', 'test@sl00.top')
        pg.click('form.modal-card button[type="submit"]')
        pg.wait_for_timeout(2600)


def goto_settings(pg):
    pg.evaluate("() => { const b=document.querySelector('[data-nav=\"settings\"]'); if(b) b.click(); }")
    pg.wait_for_timeout(700)


with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)

    for key, spec in SKINS.items():
        ctx = br.new_context(viewport={'width': 1600, 'height': 950})
        pg = ctx.new_page()
        errs = []
        pg.on('pageerror', lambda e: errs.append('pageerror: ' + str(e)))
        pg.on('console', lambda m: errs.append('console: ' + m.text) if m.type == 'error' else None)
        open_page(pg, key)
        d = pg.evaluate(PROBE)
        chk('%s 首屏白名单生效' % key, d['skin'] == key, 'data-skin=' + str(d['skin']))
        chk('%s 变量层生效（--bg）' % key, d['bg'] == spec['bg'], d['bg'])
        chk('%s 文字色沿用基座' % key, d['text'] == '#1d2a36', d['text'])
        chk('%s 底色是干净渐变' % key, 'linear-gradient' in d['bodyBg'] and 'repeating-linear-gradient' not in d['bodyBg'], d['bodyBg'][:80])
        chk('%s 内容层在背景之上' % key, d['appZ'] == '1', 'z-index=' + d['appZ'])
        if spec['before']:
            chk('%s 背景装饰符合方案' % key, spec['before'] in d['before'], d['before'][:90])
        else:
            chk('%s 留白区不加东西' % key, d['before'] == 'none', d['before'][:90])
        if spec['after']:
            chk('%s 两侧横向过渡' % key, spec['after'] in d['after'], d['after'][:90])
        chk('%s 无竖向细纹（v95 那套）' % key,
            'repeating-linear-gradient' not in (d['before'] + d['after']), d['before'][:90])
        chk('%s 无 JS 报错 / 404' % key, not errs, ' / '.join(errs[:2]))
        DECOR[key] = (d['before'], d['after'], d['bg'], d['bodyBg'])
        ctx.close()

    chk('两套背景装饰互不相同', len(set(DECOR.values())) == 2, str(sorted(DECOR.keys())))

    # 设置页：8 张卡 + 点击切换 + 刷新记忆
    ctx = br.new_context(viewport={'width': 1600, 'height': 950})
    pg = ctx.new_page()
    open_page(pg, 'paper')
    goto_settings(pg)
    d = pg.evaluate(PROBE)
    chk('设置页共 6 张主题卡', len(d['cards']) == 6, str(d['cards']))
    for key in SKINS:
        chk('设置页有 %s' % key, key in d['cards'], str(d['cards']))
    pg.click('[data-act="set-skin"][data-skin="cloud-focus"]')
    pg.wait_for_timeout(700)
    d2 = pg.evaluate(PROBE)
    chk('点击切换到聚光生效', d2['skin'] == 'cloud-focus' and d2['bg'] == '#e3eaf2', str(d2['skin']) + '/' + d2['bg'])
    chk('切换后记住主题偏好', pg.evaluate("() => localStorage.getItem('lifeboard.skin')") == 'cloud-focus',
        str(pg.evaluate("() => localStorage.getItem('lifeboard.skin')")))
    ctx.close()

    # 深色模式：聚光换成暗部晕影；浮纸仍「留白空着」
    for key in ('cloud-float', 'cloud-focus'):
        ctx = br.new_context(viewport={'width': 1600, 'height': 950})
        pg = ctx.new_page()
        open_page(pg, key, theme='dark')
        d = pg.evaluate(PROBE)
        chk('%s 深色模式生效' % key, d['theme'] == 'dark', str(d['theme']))
        if key == 'cloud-focus':
            chk('聚光深色背景装饰不为空', d['before'] != 'none', d['before'][:80])
        else:
            chk('浮纸深色仍不加背景装饰', d['before'] == 'none', d['before'][:80])
        ctx.close()

    # 窄屏：背景装饰不出现，避免手机被光斑/晕影干扰
    for key in SKINS:
        ctx = br.new_context(viewport={'width': 390, 'height': 844})
        pg = ctx.new_page()
        open_page(pg, key, w=390)
        d = pg.evaluate(PROBE)
        chk('%s 手机窄屏不叠背景装饰' % key, d['before'] == 'none' and d['after'] == 'none',
            d['before'][:60] + ' / ' + d['after'][:60])
        ctx.close()

    # v99：删掉的两个旧键必须回落 paper，且页面不再引用 skin-mist.css
    for old in ('mist', 'cloud-haze'):
        ctx = br.new_context(viewport={'width': 1440, 'height': 900})
        pg = ctx.new_page()
        open_page(pg, old)
        goto_settings(pg)
        d = pg.evaluate(PROBE)
        chk('旧键 %s 回落 paper' % old, d['skin'] == 'paper', str(d['skin']))
        chk('旧键 %s 不在主题卡里' % old, old not in d['cards'], str(d['cards']))
        chk('不再引用 skin-mist.css',
            not pg.evaluate("() => [...document.querySelectorAll('link[rel=stylesheet]')]"
                            ".some(l => l.href.indexOf('skin-mist') >= 0)"), '')
        ctx.close()

    br.close()

print('\nv99 云系两主题验证：%d/%d 通过' % (PASS, PASS + FAIL))
if FAIL:
    print('失败项：' + ', '.join(FAILS))
    sys.exit(1)
