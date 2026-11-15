# -*- coding: utf-8 -*-
"""弹窗内容的对比度审计：库存盘点 + 月度小结，9 皮肤 × 明暗。

新加的 .stock-flag 一开始用 var(--bad)，而 clay 皮肤的 --bad 是 #e08a7d，
11.5px 小字在浅底上只有 2.2:1。这类问题肉眼看不出、功能测试也测不到，
只能靠逐皮肤取色。之前 .ics-warn 踩过同一个坑。
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
head = open(os.path.join(ROOT, 'e2e', 'verify-batch4.py'), encoding='utf-8').read()
head = head.split('with sync_playwright() as p:')[0]
sys.argv = [sys.argv[0]]
exec(head)

# 盘点框只列出有库存基线的药，mock 里没有，补上
for m in board['data']['meds']:
    if m['id'] in ('m_long1', 'm_long2', 'm_short1'):
        m['stockBase'] = 30
        m['stockBaseAt'] = '2026-10-24T09:00:00'
    if m['id'] == 'm_long2':
        m['stockReview'] = True      # 让「待核对」那一段出现

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
      /* 纯色取不到时，若是渐变就把各端点颜色平均。
         paper / mist / forest / cyber 这几个皮肤的卡片背景是渐变，
         原来直接放弃，结果这四个皮肤（含默认的 paper）整体被跳过。 */
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

SELS_STOCK = ['.stock-name', '.stock-now', '.stock-flag', '.stock-hint']
# 清债介绍（v93）：导语 / 分级标题 / 正文 / 公式 / 来源块 / 行内 code
SELS_MONEY_INTRO = ['.algo-lead', '.algo-h', '.algo-p', '.algo-formula',
                    '.algo-src > b', '.algo-src p', '.algo-src a',
                    '.algo-card code', '.algo-foot']
SELS_SUMMARY = ['.sum-head span', '.sum-big', '.sum-lead', '.sum-table th',
                '.sum-table td', '.sum-foot']
# v87 删除 mono / clay / forest / cyber，只跑剩下的 5 套
skins = ['paper', 'slate', 'mist', 'neu', 'retro']

bad, skipped, missing, checked = [], 0, [], 0
skip_detail = {}
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

            nav(pg, 'meds')
            pg.wait_for_timeout(600)
            pg.click('[data-act="stock-check"]')
            pg.wait_for_timeout(500)
            res = pg.evaluate(JS, SELS_STOCK)
            pg.click('[data-act="close-modal"]')
            pg.wait_for_timeout(300)

            nav(pg, 'stats')
            pg.wait_for_timeout(700)
            pg.click('[data-act="month-summary"]')
            pg.wait_for_timeout(500)
            res += pg.evaluate(JS, SELS_SUMMARY)
            pg.click('[data-act="close-modal"]')
            pg.wait_for_timeout(300)

            nav(pg, 'money')
            pg.wait_for_timeout(700)
            pg.click('[data-act="money-intro"]')
            pg.wait_for_timeout(600)
            res += pg.evaluate(JS, SELS_MONEY_INTRO)

            for r in res:
                checked += 1
                if r.get('skip'):
                    skipped += 1
                    skip_detail['%s/%s' % (mode, skin)] = skip_detail.get('%s/%s' % (mode, skin), 0) + 1
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
      % (len(skins), len(skins) * 2,
         len(SELS_STOCK) + len(SELS_SUMMARY) + len(SELS_MONEY_INTRO), checked))
print('跳过（渐变/透明背景）：%d  %s' % (skipped, skip_detail))
print('元素缺失：%d %s' % (len(missing), missing[:4]))
print('低于 WCAG AA：%d' % len(bad))
for b in bad[:14]:
    print('   %-5s %-7s %-16s %.2f (需 %.1f) %gpx' % (b['mode'], b['skin'], b['sel'], b['ratio'], b['need'], b['size']))
sys.exit(1 if (bad or missing) else 0)
