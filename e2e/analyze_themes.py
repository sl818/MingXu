# -*- coding: utf-8 -*-
"""分析 themes/themes.css 的重复规则，找出可证明安全删除的部分。

判定标准（保守）：
  同一选择器 + 同一 @media 上下文出现多次时，后面那条的同名属性会覆盖前面的。
  若前面的每条声明都能在后面的同名规则里找到同属性名的覆盖（且前面没带 !important），
  那条声明就是死的。一条规则的全部声明都死了，整条规则可删。

用法：python e2e/analyze_themes.py [--verbose]
"""
import io
import re
import sys

CSS = 'themes/themes.css'
VERBOSE = '--verbose' in sys.argv


def strip_comments(text):
    return re.sub(r'/\*.*?\*/', lambda m: ' ' * len(m.group(0)), text, flags=re.S)


def parse_rules(css):
    """返回 [{selectors:[...], body, start, end, context, decls:{prop:important}}]"""
    css = strip_comments(css)
    rules = []
    stack = []          # 当前 @media 链
    i = 0
    n = len(css)
    line_starts = [0]
    for idx, ch in enumerate(css):
        if ch == '\n':
            line_starts.append(idx + 1)

    def line_of(pos):
        lo, hi = 0, len(line_starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if line_starts[mid] <= pos:
                lo = mid
            else:
                hi = mid - 1
        return lo + 1

    buf = ''
    while i < n:
        ch = css[i]
        if ch == '@':
            j = css.find('{', i)
            if j < 0:
                break
            at = css[i:j].strip()
            if at.startswith('@media') or at.startswith('@supports'):
                stack.append(at)
                i = j + 1
                buf = ''
                continue
            # @font-face / @keyframes 等，整段跳过
            depth = 0
            k = j
            while k < n:
                if css[k] == '{':
                    depth += 1
                elif css[k] == '}':
                    depth -= 1
                    if depth == 0:
                        break
                k += 1
            i = k + 1
            buf = ''
            continue
        if ch == '}':
            if stack:
                stack.pop()
            i += 1
            buf = ''
            continue
        if ch == '{':
            j = css.find('}', i)
            if j < 0:
                break
            sel = buf.strip()
            body = css[i + 1:j]
            decls = {}
            for part in body.split(';'):
                if ':' not in part:
                    continue
                prop, val = part.split(':', 1)
                prop = prop.strip().lower()
                if not prop:
                    continue
                decls[prop] = '!important' in val.lower()
            lead = len(buf) - len(buf.lstrip())
            rules.append({
                'sel_start': i - len(buf) + lead,
                'selectors': [s.strip() for s in sel.split(',') if s.strip()],
                'body': body,
                'start': line_of(i - len(buf)),
                'end': line_of(j),
                'cstart': i - len(buf),   # 选择器起始的字符偏移
                'cend': j + 1,            # 右花括号之后
                'context': '||'.join(stack),
                'decls': decls,
            })
            buf = ''
            i = j + 1
            continue
        buf += ch
        i += 1
    return rules


def dead_rule_indices(rules):
    """返回可整条删除的规则下标集合（判定标准见文件头）。"""
    groups = {}
    for idx, r in enumerate(rules):
        for sel in r['selectors']:
            groups.setdefault((r['context'], sel), []).append(idx)

    stays = set()
    for (ctx, sel), idxs in groups.items():
        if len(idxs) < 2:
            stays.update(idxs)
            continue
        covered = {}
        for ridx in reversed(idxs):
            r = rules[ridx]
            alive = {p: imp for p, imp in r['decls'].items() if not (p in covered and not imp)}
            if alive or ridx == idxs[-1]:
                stays.add(ridx)
            covered.update(alive)
    return {i for i in range(len(rules)) if i not in stays}


def main():
    text = io.open(CSS, encoding='utf-8', newline='').read()
    rules = parse_rules(text)
    total_lines = text.count('\n') + 1
    print('规则数 %d，文件 %d 行' % (len(rules), total_lines))

    # 按 (context, selector) 分组
    groups = {}
    for idx, r in enumerate(rules):
        for sel in r['selectors']:
            groups.setdefault((r['context'], sel), []).append(idx)

    dead_rules = dead_rule_indices(rules)
    # 估算可删行数（仅整条规则可删的）
    save_lines = 0
    for ridx in dead_rules:
        r = rules[ridx]
        save_lines += r['end'] - r['start'] + 1

    print('整条可删规则：%d 条，约 %d 行' % (len(dead_rules), save_lines))

    if VERBOSE:
        for ridx in sorted(dead_rules):
            r = rules[ridx]
            print('  L%-5d %-4s %s' % (r['start'], '', ', '.join(r['selectors'])[:100]))

    # 按皮肤统计
    print('\n各皮肤根定义块分布：')
    for m in re.finditer(r':root\[data-skin="([a-z]+)"\](\[data-theme="dark"\])?\s*\{', text):
        pos = m.start()
        line = text.count('\n', 0, pos) + 1
        print('  L%-5d %s%s' % (line, m.group(1), ' (dark)' if m.group(2) else ''))


if __name__ == '__main__':
    main()
