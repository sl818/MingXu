# -*- coding: utf-8 -*-
"""抓 computed style 快照，用于 CSS 去重前后的逐属性比对。

用法：python snap_styles.py <输出文件>
  6 皮肤 × 明暗 × 6 页面，每个元素取 30 个关键属性。
  key = 标签.类名#同键序号 —— 不依赖 nth-child，页面结构不变就稳。
"""
import os, sys, json
from datetime import datetime

ROOT = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo'
OUT = sys.argv[1] if len(sys.argv) > 1 else '/tmp/styles_snap.json'

head = open(os.path.join(ROOT, 'e2e', 'verify-batch4.py'), encoding='utf-8').read().split('with sync_playwright() as p:')[0]
sys.argv = [sys.argv[0]]
exec(head)

from playwright.sync_api import sync_playwright
SKINS = ['paper', 'slate', 'cloud-float', 'cloud-focus', 'neu', 'retro']
PAGES = [('today', None), ('habits', None), ('board', None),
         ('money', 'debts'), ('weight', None), ('stats', None)]

JS = """() => {
  const PROPS = ['display','position','float','width','height','min-width','min-height',
    'max-width','max-height','margin-top','margin-right','margin-bottom','margin-left',
    'padding-top','padding-right','padding-bottom','padding-left',
    'color','background-color','background-image','background-position','background-size',
    'border-top-width','border-top-style','border-top-color','border-radius',
    'box-shadow','opacity','z-index','font-size','font-weight','line-height',
    'letter-spacing','text-align','white-space','overflow','flex-direction',
    'justify-content','align-items','gap','grid-template-columns'];
  const seen = {};
  const out = [];
  document.querySelectorAll('body *').forEach(function (el) {
    if (el.tagName === 'SCRIPT' || el.tagName === 'STYLE') return;
    const cls = [...el.classList].sort().join('.');
    const base = el.tagName.toLowerCase() + (cls ? '.' + cls : '');
    const n = (seen[base] = (seen[base] || 0) + 1);
    const cs = getComputedStyle(el);
    const vals = PROPS.map(function (p) { return cs.getPropertyValue(p); }).join('|');
    out.push(base + '#' + n + '=' + vals);
  });
  return out;
}"""

def main():
    data = {}
    with sync_playwright() as p:
        br = p.chromium.launch(channel='chrome', headless=True)
        for mode in ('light', 'dark'):
            for skin in SKINS:
                ctx = br.new_context(viewport={'width': 1440, 'height': 950})
                pg = ctx.new_page()
                pg.clock.install(time=datetime(2026, 10, 25, 10, 0, 0))
                pg.add_init_script("try{localStorage.setItem('lifeboard.skin','%s');"
                                   "localStorage.setItem('lifeboard.theme.mode','%s')}catch(e){}" % (skin, mode))
                pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
                pg.wait_for_timeout(400)
                if pg.locator('[data-act="cloud-login"]').count():
                    pg.click('[data-act="cloud-login"]')
                    pg.wait_for_timeout(350)
                    pg.fill('input[name="email"]', 'test@example.com')
                    pg.fill('input[name="password"]', 'test@example.com')
                    pg.click('form.modal-card button[type="submit"]')
                    pg.wait_for_timeout(2400)
                for page, tab in PAGES:
                    pg.evaluate("(k) => { const b = document.querySelector('[data-nav=\"' + k + '\"]'); if (b) b.click(); }", page)
                    pg.wait_for_timeout(700)
                    if tab:
                        pg.evaluate("(t) => { const b = document.querySelector('[data-act=\"subtab\"][data-page=\"money\"][data-tab=\"' + t + '\"]'); if (b) b.click(); }", tab)
                        pg.wait_for_timeout(600)
                    data['%s/%s/%s' % (skin, mode, page)] = pg.evaluate(JS)
                ctx.close()
        br.close()
    json.dump(data, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False)
    total = sum(len(v) for v in data.values())
    print('快照写入', OUT, '组数', len(data), '元素总数', total)

main()
