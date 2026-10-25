import sys, json, os
sys.argv=['x','none']
exec(open('.tmp-b4-head.py', encoding='utf-8').read())

JS = """
(sels) => {
  const lum = c => { const [r,g,b] = c.map(v => { v/=255; return v <= 0.03928 ? v/12.92 : Math.pow((v+0.055)/1.055, 2.4); });
    return 0.2126*r + 0.7152*g + 0.0722*b; };
  const parse = s => { const t=String(s); const m=t.match(/[\\d.]+/g); if(!m) return null;
    const n=m.slice(0,3).map(Number); return /^color\\(/.test(t) ? n.map(v=>v*255) : n; };
  const bgOf = el => { let n=el;
    while(n && n!==document.documentElement){ const cs=getComputedStyle(n);
      if(cs.backgroundImage && cs.backgroundImage!=='none') return null;
      const s=cs.backgroundColor, c=parse(s), a=String(s).match(/[\\d.]+/g);
      if(c && (!a[3] || Number(a[3])>0.6)) return c; n=n.parentElement; }
    return null; };
  const out=[];
  sels.forEach(sel=>{ const el=document.querySelector(sel); if(!el) return;
    const cs=getComputedStyle(el), fg=parse(cs.color), bg=bgOf(el);
    if(!fg||!bg){ out.push({sel,skip:true}); return; }
    const l1=lum(fg), l2=lum(bg);
    out.push({sel, ratio: Math.round(((Math.max(l1,l2)+0.05)/(Math.min(l1,l2)+0.05))*100)/100,
               size: parseFloat(cs.fontSize), weight: cs.fontWeight}); });
  return out;
}
"""
SELS=['.privacy-note','.privacy-note b','.backfill-bar','.remind-item']
skins=['paper','slate','mono','clay','mist','forest','neu','cyber','retro']
bad=[]; skipped=0
with sync_playwright() as p:
    br=p.chromium.launch(channel='chrome',headless=True)
    for mode in ('light','dark'):
        for skin in skins:
            c=br.new_context(viewport={'width':1440,'height':900})
            pg=c.new_page()
            pg.add_init_script("try{localStorage.setItem('lifeboard.skin','%s');localStorage.setItem('lifeboard.theme.mode','%s')}catch(e){}"%(skin,mode))
            pg.clock.install(time=datetime(2026,10,25,10,0,0))
            pg.goto('http://127.0.0.1:%d/index.html'%port, wait_until='networkidle'); pg.wait_for_timeout(400)
            pg.click('[data-act="cloud-login"]'); pg.wait_for_timeout(300)
            pg.fill('input[name="email"]','test@sl00.top'); pg.fill('input[name="password"]','test@sl00.top')
            pg.click('form.modal-card button[type="submit"]'); pg.wait_for_timeout(2300)
            pg.evaluate("() => { const b=document.querySelector('[data-nav=\"settings\"]'); if(b) b.click(); }"); pg.wait_for_timeout(500)
            res=pg.evaluate(JS, SELS)
            for r in res:
                if r.get('skip'): skipped+=1; continue
                need = 3.0 if (r['size']>=18 or (r['size']>=14 and int(r['weight'])>=700)) else 4.5
                if r['ratio'] < need: bad.append({**r,'mode':mode,'skin':skin,'need':need})
            c.close()
    br.close()
print('跳过(渐变背景):', skipped, ' 低于 AA:', len(bad))
for b in bad[:10]:
    print('  %-5s %-7s %-16s %.2f (需 %.1f)' % (b['mode'],b['skin'],b['sel'],b['ratio'],b['need']))
