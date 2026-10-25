"""线上对比度审计：遍历真实渲染的文本元素，算实际前景/背景对比度"""
import json
from playwright.sync_api import sync_playwright

BASE = 'https://todo.csl88.top'

AUDIT = """() => {
  const parse = c => {
    const m = c.match(/rgba?\\(([^)]+)\\)/);
    if (!m) return null;
    const p = m[1].split(',').map(x => parseFloat(x.trim()));
    return {r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1};
  };
  const lin = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
  const lum = c => 0.2126 * lin(c.r) + 0.7152 * lin(c.g) + 0.0722 * lin(c.b);
  const over = (fg, bg) => ({r: fg.r * fg.a + bg.r * (1 - fg.a),
                             g: fg.g * fg.a + bg.g * (1 - fg.a),
                             b: fg.b * fg.a + bg.b * (1 - fg.a), a: 1});
  const ratio = (a, b) => { const l1 = lum(a), l2 = lum(b);
    const [hi, lo] = l1 >= l2 ? [l1, l2] : [l2, l1];
    return (hi + 0.05) / (lo + 0.05); };

  // 向上找有实色背景的祖先
  const bgOf = el => {
    let n = el;
    while (n && n !== document.documentElement) {
      const cs = getComputedStyle(n);
      const bc = parse(cs.backgroundColor);
      if (bc && bc.a > 0.85) return bc;
      if (cs.backgroundImage && cs.backgroundImage !== 'none') return null; // 渐变/图，跳过
      n = n.parentElement;
    }
    return parse(getComputedStyle(document.body).backgroundColor) || {r: 255, g: 255, b: 255, a: 1};
  };

  const out = [];
  const seen = new Set();
  document.querySelectorAll('.main *, .sidebar *, .mobile-tabbar *').forEach(el => {
    if (el.children.length) return;
    const txt = (el.textContent || '').trim();
    if (!txt || txt.length > 40) return;
    const r = el.getBoundingClientRect();
    if (r.width < 4 || r.height < 4) return;
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.display === 'none' || parseFloat(cs.opacity) < 0.5) return;
    const fg = parse(cs.color);
    if (!fg) return;
    const bg = bgOf(el);
    if (!bg) return;
    const real = fg.a < 1 ? over(fg, bg) : fg;
    const cr = ratio(real, bg);
    const size = parseFloat(cs.fontSize);
    const bold = parseInt(cs.fontWeight, 10) >= 600;
    // AA 阈值：大字(>=18.66px 或 >=24px) 3:1，其余 4.5:1
    const large = size >= 24 || (size >= 18.66 && bold);
    const need = large ? 3 : 4.5;
    if (cr < need) {
      const key = cs.color + '|' + Math.round(size);
      if (seen.has(key)) return;
      seen.add(key);
      out.push({text: txt.slice(0, 26), color: cs.color, size: Math.round(size * 10) / 10,
                bold, ratio: Math.round(cr * 100) / 100, need});
    }
  });
  return out;
}"""

views = [('today', '今日'), ('board', '待办'), ('habits', '习惯'), ('weight', '体重'),
         ('essays', '随笔'), ('calendar', '日历'), ('stats', '统计'), ('settings', '设置')]

result = {}
with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)
    for skin, theme in [('slate', 'dark'), ('paper', 'light'), ('paper', 'dark')]:
        ctx = br.new_context(viewport={'width': 1440, 'height': 900})
        pg = ctx.new_page()
        pg.add_init_script(f"""
          try {{ localStorage.setItem('lifeboard.skin','{skin}');
                 localStorage.setItem('lifeboard.theme.mode','{theme}'); }} catch(e) {{}}
        """)
        pg.goto(BASE, wait_until='networkidle'); pg.wait_for_timeout(900)
        pg.click('[data-act="cloud-login"]'); pg.wait_for_timeout(500)
        pg.fill('input[name="email"]', 'test@sl00.top')
        pg.fill('input[name="password"]', 'test@sl00.top')
        pg.click('form.modal-card button[type="submit"]'); pg.wait_for_timeout(3800)

        key = f'{skin}/{theme}'
        result[key] = {}
        for v, label in views:
            pg.click(f'.nav-item[data-nav="{v}"]')
            pg.wait_for_timeout(1300)
            bad = pg.evaluate(AUDIT)
            result[key][label] = bad
            if bad:
                print(f'[{key}] {label}: {len(bad)} 处不达标')
                for b in bad[:4]:
                    print(f'    {b["ratio"]}:1 (需{b["need"]}) {b["size"]}px "{b["text"]}" {b["color"]}')
            else:
                print(f'[{key}] {label}: 全部达标')
        ctx.close()
    br.close()

json.dump(result, open('e2e/contrast-audit.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

print('\n' + '=' * 56)
for k, v in result.items():
    total = sum(len(x) for x in v.values())
    print(f'{k}: 共 {total} 处低于 AA 阈值')
