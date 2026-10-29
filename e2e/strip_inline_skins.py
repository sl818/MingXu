# -*- coding: utf-8 -*-
"""分析 index.html 里的 <style id="skins"> 有多少规则被后面的外部样式表覆盖。

加载顺序（同特异性时后者胜）：
  <style id="skins"> 在 <head> 里
  → themes/themes.css → custom.css → skin-mist → skin-forest → skin-neu → skin-cyber → skin-retro

所以只要外部文件里定义了同名选择器的同属性，inline 那条就永远不会生效。

用法：
  python e2e/strip_inline_skins.py --dry
  python e2e/strip_inline_skins.py --write
"""
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analyze_themes import parse_rules, dead_rule_indices   # noqa: E402

HTML = 'index.html'
EXTERNAL = ['themes/themes.css', 'themes/custom.css', 'themes/skin-mist.css',
            'themes/skin-forest.css', 'themes/skin-neu.css', 'themes/skin-cyber.css',
            'themes/skin-retro.css']
WRITE = '--write' in sys.argv


def main():
    html = io.open(HTML, encoding='utf-8', newline='').read()
    m = re.search(r'<style id="skins">', html)
    if not m:
        print('找不到 <style id="skins">')
        return
    start_tag = m.start()
    body_start = m.end()
    end = html.find('</style>', body_start)
    if end < 0:
        print('找不到对应的 </style>')
        return
    inline_text = html[body_start:end]

    inline_rules = parse_rules(inline_text)
    ext_text = ''
    for p in EXTERNAL:
        if os.path.isfile(p):
            ext_text += io.open(p, encoding='utf-8', newline='').read() + '\n'
    ext_rules = parse_rules(ext_text)
    for r in ext_rules:
        r['external'] = True

    rules = inline_rules + ext_rules
    dead = dead_rule_indices(rules)
    dead_inline = sorted(i for i in dead if i < len(inline_rules))

    total_chars = len(inline_text)
    dead_chars = sum(inline_rules[i]['cend'] - inline_rules[i]['sel_start'] for i in dead_inline)
    print('inner 规则 %d 条，外部规则 %d 条' % (len(inline_rules), len(ext_rules)))
    print('inline 里被判死 %d 条，占 %.0f%%（%d / %d 字符）'
          % (len(dead_inline), 100.0 * len(dead_inline) / max(1, len(inline_rules)),
             dead_chars, total_chars))

    alive = [i for i in range(len(inline_rules)) if i not in set(dead_inline)]
    if not alive:
        print('全部规则都能删 —— 可以整块移除')
    else:
        print('仍生效的规则 %d 条：' % len(alive))
        seen = 0
        for i in alive:
            sel = ', '.join(inline_rules[i]['selectors'])
            if seen < 25:
                print('    L%-5d %s' % (inline_rules[i]['start'], sel[:90]))
            seen += 1
        if seen > 25:
            print('    ... 共 %d 条' % seen)

    if not WRITE:
        print('（预演，没有写文件）')
        return
    if alive:
        print('还有规则在生效，不能整块删。请先处理上面这些。')
        sys.exit(1)

    # 整块移除，连同标签和它前面的空行
    html2 = html[:start_tag] + html[end + len('</style>'):]
    html2 = re.sub(r'(\r?\n){3,}', lambda mm: mm.group(1) * 2, html2)
    io.open(HTML, 'w', encoding='utf-8', newline='').write(html2)
    print('已移除 <style id="skins"> 整块')


if __name__ == '__main__':
    main()
