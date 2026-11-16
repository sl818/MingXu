# -*- coding: utf-8 -*-
"""命令卡（.se-cmd）的对比度审计：按 skins 清单逐套 × 明暗。

这张卡底下是 --accent-soft，是带强调色的浅底而不是中性色，
深色皮肤下最容易和 --text 撞色，所以单独量一次。
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
head = open(os.path.join(ROOT, 'e2e', 'verify-batch4.py'), encoding='utf-8').read()
head = head.split('with sync_playwright() as p:')[0]
sys.argv = [sys.argv[0]]
exec(head)

JS = """
(sels) => {
  const lum = c => { const [r,g,b] = c.map(v => { v/=255; return v <= 0.03928 ? v/12.92 : Math.pow((v+0.055)/1.055, 2.4); });
    return 0.2126*r + 0.7152*g + 0.0722*b; };
  const parse = s => { const t=String(s); const m=t.match(/[\\d.]+/g); if(!m) return null;
    const n=m.slice(0,3).map(Number); return /^color\\(/.test(t) ? n.map(v=>v*255) : n; };
  const bgOf = el => { let n=el;
    while(n && n!==document.documentElement){ const cs=getComputedStyle(n);
      const s=cs.backgroundColor, c=parse(s), a=String(s).match(/[\\d.]+/g);
      if(c && (!a[3] || Number(a[3])>0.6)) return c;
      const bi=cs.backgroundImage;
      if(bi && bi!=='none'){
        const cols=bi.match(/rgba?\\([^)]+\\)/g);
        if(cols && cols.length){
          const arrs=cols.map(x=>parse(x)).filter(Boolean);
          if(arrs.length) return [0,1,2].map(i=>arrs.reduce((t,x)=>t+x[i],0)/arrs.length);
        }
      }
      n=n.parentElement; }
    return null; };
  const out=[];
  sels.forEach(sel=>{ const el=document.querySelector(sel); if(!el) { out.push({sel, missing:true}); return; }
    const cs=getComputedStyle(el), fg=parse(cs.color), bg=bgOf(el);
    if(!fg||!bg){ out.push({sel, skip:true}); return; }
    const l1=lum(fg), l2=lum(bg);
    out.push({sel, ratio: Math.round(((Math.max(l1,l2)+0.05)/(Math.min(l1,l2)+0.05))*100)/100,
               size: parseFloat(cs.fontSize), weight: cs.fontWeight}); });
  return out;
}
"""

# 命令模式下 .se-hint / .se-group 不显示，所以要分两次取样
SELS_CMD = ['.se-cmd .se-title', '.se-cmd .se-meta']
SELS_IDLE = ['.se-hint', '.se-group']
skins = ['paper', 'slate', 'neu', 'retro', 'cloud-float', 'cloud-focus']

bad, skipped, missing, checked = [], [], [], 0
with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)
    for mode in ('light', 'dark'):
        for skin in skins:
            ctx = br.new_context(viewport={'width': 1440, 'height': 950})
            pg = ctx.new_page()
            pg.add_init_script(
                "try{localStorage.setItem('lifeboard.skin','%s');"
                "localStorage.setItem('lifeboard.theme.mode','%s')}catch(e){}" % (skin, mode))
            pg.clock.install(time=datetime(2026, 10, 25, 10, 0, 0))
            pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
            pg.wait_for_timeout(400)
            pg.click('[data-act="cloud-login"]')
            pg.wait_for_timeout(350)
            pg.fill('input[name="email"]', 'test@sl00.top')
            pg.fill('input[name="password"]', 'test@sl00.top')
            pg.click('form.modal-card button[type="submit"]')
            pg.wait_for_timeout(2400)

            pg.keyboard.press('Control+k')
            pg.wait_for_timeout(400)
            pg.fill('#search-input', '+1 喝水')
            pg.wait_for_timeout(350)
            res = pg.evaluate(JS, SELS_CMD)
            pg.fill('#search-input', '')
            pg.wait_for_timeout(350)
            res += pg.evaluate(JS, SELS_IDLE)

            for r in res:
                checked += 1
                if r.get('skip'):
                    skipped.append('%s/%s/%s' % (mode, skin, r['sel']))
                    continue
                if r.get('missing'):
                    missing.append('%s/%s/%s' % (mode, skin, r['sel']))
                    continue
                need = 3.0 if (r['size'] >= 18 or (r['size'] >= 14 and int(r['weight']) >= 700)) else 4.5
                if r['ratio'] < need:
                    bad.append({'mode': mode, 'skin': skin, 'sel': r['sel'],
                                'ratio': r['ratio'], 'need': need, 'size': r['size']})
            ctx.close()
    br.close()

print('检查：%d 皮肤 × 明暗 = %d 组 × %d 个元素（共 %d 次取样）'
      % (len(skins), len(skins) * 2, len(SELS_CMD) + len(SELS_IDLE), checked))
print('跳过：%d %s' % (len(skipped), skipped[:3]))
print('元素缺失：%d %s' % (len(missing), missing[:3]))
print('低于 WCAG AA：%d' % len(bad))
for b in bad[:14]:
    print('   %-5s %-7s %-20s %.2f (需 %.1f) %gpx' % (b['mode'], b['skin'], b['sel'], b['ratio'], b['need'], b['size']))
sys.exit(1 if (bad or missing) else 0)
