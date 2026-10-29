# -*- coding: utf-8 -*-
"""逐元素对比某个视图的计算样式，定位具体是哪一行哪个属性变了。

用法：
  python e2e/diff-theme-detail.py out.json [view] [skin] [mode]
  python e2e/diff-theme-detail.py --diff a.json b.json
"""
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
head = io.open(os.path.join(ROOT, 'e2e', 'verify-batch4.py'), encoding='utf-8').read()
head = head.split('with sync_playwright() as p:')[0]
_ARGS = sys.argv[1:]
sys.argv = [sys.argv[0]]
exec(head)

PROPS = ['color', 'background-color', 'background-image', 'background-size', 'background-position',
         'border-top-width', 'border-right-width', 'border-bottom-width', 'border-left-width',
         'border-top-color', 'border-bottom-color', 'border-top-style', 'border-radius',
         'margin-top', 'margin-right', 'margin-bottom', 'margin-left',
         'padding-top', 'padding-right', 'padding-bottom', 'padding-left',
         'font-size', 'font-weight', 'font-family', 'line-height', 'letter-spacing',
         'display', 'position', 'top', 'right', 'bottom', 'left', 'z-index',
         'width', 'height', 'min-width', 'min-height', 'max-width',
         'flex-direction', 'flex-wrap', 'flex-grow', 'flex-shrink', 'flex-basis',
         'align-items', 'align-self', 'justify-content', 'gap', 'order',
         'grid-template-columns', 'grid-template-rows', 'grid-column', 'grid-row',
         'opacity', 'transform', 'box-shadow', 'overflow-x', 'overflow-y',
         'text-align', 'text-decoration-line', 'text-transform', 'white-space',
         'animation-name', 'animation-duration', 'transition-property', 'transition-duration',
         'fill', 'stroke', 'stroke-width', 'outline-style', 'outline-width', 'cursor']

JS = """
(props) => {
  const vars = [];
  try {
    for (const [k, v] of document.documentElement.computedStyleMap()) {
      if (k.indexOf('--') === 0) vars.push([k, String(v)]);
    }
    vars.sort();
  } catch (e) {}
  const els = [];
  document.querySelectorAll('*').forEach((el, i) => {
    const cs = getComputedStyle(el);
    const d = {};
    for (const p of props) d[p] = cs.getPropertyValue(p);
    for (const pe of ['::before', '::after']) {
      const ps = getComputedStyle(el, pe);
      d['pseudo' + pe] = ps.getPropertyValue('content') + '|' + ps.getPropertyValue('color') + '|' +
        ps.getPropertyValue('background-color') + '|' + ps.getPropertyValue('border-top-width') + '|' +
        ps.getPropertyValue('width') + '|' + ps.getPropertyValue('height');
    }
    els.push([i, el.tagName, String(el.className).slice(0, 60), d]);
  });
  return { vars: vars, els: els, count: document.querySelectorAll('*').length };
}
"""


def diff(a_path, b_path):
    a = json.load(io.open(a_path, encoding='utf-8'))
    b = json.load(io.open(b_path, encoding='utf-8'))
    print('元素数 a=%d b=%d' % (a['count'], b['count']))

    va = dict(a['vars'])
    vb = dict(b['vars'])
    var_diff = 0
    for k in sorted(set(va) | set(vb)):
        if va.get(k) != vb.get(k):
            var_diff += 1
            if var_diff <= 20:
                print('  变量 %s: %r -> %r' % (k, va.get(k), vb.get(k)))
    print('变量差异 %d 个' % var_diff)

    shown = 0
    for ea, eb in zip(a['els'], b['els']):
        if ea[1] != eb[1] or ea[2] != eb[2]:
            print('  结构错位 at %d: %s.%s vs %s.%s' % (ea[0], ea[1], ea[2], eb[1], eb[2]))
            break
        da, db_ = ea[3], eb[3]
        bad = [(p, da[p], db_[p]) for p in da if da[p] != db_[p]]
        if bad:
            shown += 1
            if shown <= 12:
                print('  [%d] %s.%s' % (ea[0], ea[1], ea[2]))
                for p, x, y in bad[:6]:
                    print('      %-18s %r -> %r' % (p, x[:60], y[:60]))
    print('有差异的元素 %d 个' % shown)


if _ARGS[:1] == ['--diff']:
    diff(_ARGS[1], _ARGS[2])
    sys.exit(0)

OUT = _ARGS[0] if _ARGS else 'detail.json'
view = _ARGS[1] if len(_ARGS) > 1 else 'today'
skin = _ARGS[2] if len(_ARGS) > 2 else 'paper'
mode = _ARGS[3] if len(_ARGS) > 3 else 'light'

with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)
    ctx = br.new_context(viewport={'width': 1440, 'height': 950})
    pg = ctx.new_page()
    pg.add_init_script(
        "try{localStorage.setItem('lifeboard.skin','%s');"
        "localStorage.setItem('lifeboard.theme.mode','%s')}catch(e){}" % (skin, mode))
    pg.clock.install(time=datetime(2026, 10, 25, 10, 0, 0))
    pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
    pg.wait_for_timeout(500)
    pg.click('[data-act="cloud-login"]')
    pg.wait_for_timeout(350)
    pg.fill('input[name="email"]', 'test@sl00.top')
    pg.fill('input[name="password"]', 'test@sl00.top')
    pg.click('form.modal-card button[type="submit"]')
    pg.wait_for_timeout(2400)
    if view != 'today':
        nav(pg, view)
    pg.wait_for_timeout(500)
    data = pg.evaluate(JS, PROPS)
    br.close()

io.open(OUT, 'w', encoding='utf-8').write(json.dumps(data, ensure_ascii=False))
print('已写入 %s（%d 元素）' % (OUT, data['count']))
