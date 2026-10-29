# -*- coding: utf-8 -*-
"""主题样式快照：给 9 皮肤 × 明暗 × 6 视图各存一个计算样式指纹。

用来证明「删掉重复的 CSS 规则」没有产生任何视觉变化。
指纹包含：根元素上所有 CSS 自定义属性 + 每个元素的 70 个计算属性 + 伪元素。

用法：
  python e2e/snapshot-theme.py before.json
  python e2e/snapshot-theme.py after.json
  python e2e/snapshot-theme.py --diff before.json after.json
"""
import hashlib
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

SKINS = ['paper', 'slate', 'mono', 'clay', 'mist', 'forest', 'neu', 'cyber', 'retro']
MODES = ['light', 'dark']
VIEWS = ['today', 'board', 'habits', 'meds', 'weight', 'stats']

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
      if (k.indexOf('--') === 0) vars.push(k + '=' + String(v));
    }
    vars.sort();
  } catch (e) { vars.push('VARDUMP_FAILED'); }
  const out = [vars.join(';')];
  document.querySelectorAll('*').forEach(el => {
    const cs = getComputedStyle(el);
    const seg = [];
    for (let i = 0; i < props.length; i++) seg.push(cs.getPropertyValue(props[i]));
    for (const pe of ['::before', '::after']) {
      const ps = getComputedStyle(el, pe);
      seg.push(ps.getPropertyValue('content') + '|' + ps.getPropertyValue('color') + '|' +
               ps.getPropertyValue('background-color') + '|' + ps.getPropertyValue('border-top-width') + '|' +
               ps.getPropertyValue('width') + '|' + ps.getPropertyValue('height'));
    }
    out.push(seg.join(','));
  });
  return out.join('\\n');
}
"""


def diff(before_path, after_path):
    b = json.load(io.open(before_path, encoding='utf-8'))
    a = json.load(io.open(after_path, encoding='utf-8'))
    keys = sorted(set(b) | set(a))
    same = diff_keys = 0
    bad = []
    for k in keys:
        if b.get(k) == a.get(k):
            same += 1
        else:
            diff_keys += 1
            bad.append(k)
    print('对比 %d 组快照：一致 %d，不一致 %d' % (len(keys), same, diff_keys))
    for k in bad[:30]:
        print('  差异: %s' % k)
    if diff_keys == 0:
        print('视觉指纹完全一致')
        return 0
    print('存在差异，不能删')
    return 1


if _ARGS[:1] == ['--diff']:
    sys.exit(diff(_ARGS[1], _ARGS[2]))

OUT = _ARGS[0] if _ARGS else 'theme-snapshot.json'
result = {}

with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)
    ctx = br.new_context(viewport={'width': 1440, 'height': 950})
    pg = ctx.new_page()
    pg.clock.install(time=datetime(2026, 10, 25, 10, 0, 0))
    pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
    pg.wait_for_timeout(500)
    pg.click('[data-act="cloud-login"]')
    pg.wait_for_timeout(350)
    pg.fill('input[name="email"]', 'test@sl00.top')
    pg.fill('input[name="password"]', 'test@sl00.top')
    pg.click('form.modal-card button[type="submit"]')
    pg.wait_for_timeout(2400)

    total = len(SKINS) * len(MODES) * len(VIEWS)
    done = 0
    for skin in SKINS:
        for mode in MODES:
            pg.evaluate(
                "([s, m]) => { localStorage.setItem('lifeboard.skin', s);"
                " localStorage.setItem('lifeboard.theme.mode', m); }", [skin, mode])
            pg.reload(wait_until='networkidle')
            # 云端数据加载 + 首屏渲染需要时间；1200ms 时 occasionally 还停在
            # 骨架屏上，导致同一版本两次快照不一致（today 是 reload 后第一个抓的，最容易踩）
            pg.wait_for_timeout(2200)
            for view in VIEWS:
                nav(pg, view)
                pg.wait_for_timeout(320)
                raw = pg.evaluate(JS, PROPS)
                result['%s|%s|%s' % (skin, mode, view)] = hashlib.sha256(
                    raw.encode('utf-8')).hexdigest()[:32]
                done += 1
                if done % 18 == 0:
                    print('  ... %d/%d' % (done, total))
    br.close()

io.open(OUT, 'w', encoding='utf-8').write(json.dumps(result, ensure_ascii=False, indent=1))
print('已写入 %s（%d 组）' % (OUT, len(result)))
