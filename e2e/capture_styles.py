# -*- coding: utf-8 -*-
"""抓取整站每个元素的「计算样式指纹」，用于 CSS 重构前后的等价性验证。

只依赖 DOM 顺序 + 计算样式，不截图，比像素比对更严格（能发现 1px 的差异）。
用法：python capture_styles.py before.json
"""
import sys, json, hashlib, os
OUT = sys.argv[1] if len(sys.argv) > 1 else 'styles.json'
# 复用第四批验证脚本的 mock 服务（它会在导入时启动本地服务器）
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_b4 = open(os.path.join(_root, 'e2e', 'verify-batch4.py'), encoding='utf-8').read()
_code = _b4.split('with sync_playwright() as p:')[0]
sys.argv = ['x', 'none']
exec(_code)
VIEWS = ['today', 'board', 'habits', 'meds', 'weight', 'stats']
SKINS = ['paper', 'mono']
THEMES = ['light', 'dark']

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
  const out = [];
  document.querySelectorAll('*').forEach((el, i) => {
    const cs = getComputedStyle(el);
    const parts = [];
    for (const p of props) parts.push(p + '=' + cs.getPropertyValue(p));
    // 伪元素也算上，避免漏掉 ::before / ::after 的样式变化
    ['::before', '::after'].forEach(pe => {
      const ps = getComputedStyle(el, pe);
      parts.push(pe + ':' + ps.getPropertyValue('content') + '|' + ps.getPropertyValue('color') +
                 '|' + ps.getPropertyValue('background-color') + '|' + ps.getPropertyValue('border-top-width') +
                 '|' + ps.getPropertyValue('width') + '|' + ps.getPropertyValue('height'));
    });
    out.push(i + ':' + el.tagName + '.' + String(el.className).slice(0, 40) + '|' + parts.join(';'));
  });
  return out;
}
"""

result = {}
with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)
    for skin in SKINS:
        for theme in THEMES:
            state = ctx_state = None
            # 每个组合用一个干净 context，避免残留缓存影响
            for view in VIEWS:
                c = br.new_context(viewport={'width': 1440, 'height': 900},
                                   reduced_motion='no-preference')
                pg = c.new_page()
                pg.add_init_script(
                    "try{localStorage.setItem('lifeboard.skin','%s');"
                    "localStorage.setItem('lifeboard.theme.mode','%s');"
                    "localStorage.setItem('lifeboard.layout','top');}catch(e){}" % (skin, theme))
                pg.clock.install(time=datetime(2026, 10, 25, 10, 0, 0))
                pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
                pg.wait_for_timeout(400)
                pg.click('[data-act="cloud-login"]')
                pg.wait_for_timeout(300)
                pg.fill('input[name="email"]', 'test@sl00.top')
                pg.fill('input[name="password"]', 'test@sl00.top')
                pg.click('form.modal-card button[type="submit"]')
                pg.wait_for_timeout(2400)
                pg.evaluate("v => { const b=document.querySelector('[data-nav=\"'+v+'\"]'); if(b) b.click(); }", view)
                pg.wait_for_timeout(600)
                # 关闭可能弹出的提醒横幅，避免它的出现/消失造成差异
                pg.evaluate("() => { const b=document.querySelector('[data-act=\"remind-dismiss\"]'); if(b) b.click(); }")
                pg.wait_for_timeout(400)
                dump = pg.evaluate(JS, PROPS)
                h = hashlib.sha256('\n'.join(dump).encode('utf-8')).hexdigest()[:16]
                result['%s|%s|%s' % (skin, theme, view)] = {'count': len(dump), 'hash': h, 'dump': dump}
                c.close()
    br.close()

with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False)
print('已写入 %s，组合 %d 组' % (OUT, len(result)))
for k, v in result.items():
    print('  %-22s 元素 %4d  hash %s' % (k, v['count'], v['hash']))
