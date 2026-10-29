# -*- coding: utf-8 -*-
"""删掉 themes/themes.css 里被完全覆盖的规则（重复定义的旧版本皮肤）。

判定逻辑来自 analyze_themes.dead_rule_indices：同一上下文里同名选择器出现多次时，
前面的声明若全被后面的同属性覆盖（且自己不带 !important），那它永远不会生效。

删除后一定要跑 e2e/snapshot-theme.py 对比指纹，视觉零变化才算安全。

用法：
  python e2e/strip_themes.py --dry
  python e2e/strip_themes.py --write
"""
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analyze_themes import parse_rules, dead_rule_indices   # noqa: E402

CSS = 'themes/themes.css'
WRITE = '--write' in sys.argv


def main():
    text = io.open(CSS, encoding='utf-8', newline='').read()
    rules = parse_rules(text)
    dead = dead_rule_indices(rules)

    spans = sorted((rules[i]['sel_start'], rules[i]['cend']) for i in dead)

    # 合并重叠区间
    merged = []
    for a, b in spans:
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])

    removed_chars = sum(b - a for a, b in merged)
    print('规则 %d 条，判死 %d 条，合并成 %d 段，删除 %d 字符'
          % (len(rules), len(dead), len(merged), removed_chars))

    out = text
    for a, b in reversed(merged):
        out = out[:a] + out[b:]

    # 收拾留下的空行：三个以上连续换行压成两个；行尾空白去掉
    eol = '\r\n' if '\r\n' in out else '\n'
    out = re.sub(r'[ \t]+\r?\n', eol, out)
    out = re.sub(r'(\r?\n){3,}', eol + eol, out)
    out = out.lstrip('\r\n') if not text.startswith('\n') else out

    before_lines = text.count('\n') + 1
    after_lines = out.count('\n') + 1
    print('行数 %d -> %d（减少 %d，%.0f%%）'
          % (before_lines, after_lines, before_lines - after_lines,
             100.0 * (before_lines - after_lines) / before_lines))

    if not WRITE:
        print('（预演，没有写文件。确认后加 --write）')
        return

    io.open(CSS, 'w', encoding='utf-8', newline='').write(out)
    print('已写入 %s' % CSS)


if __name__ == '__main__':
    main()
