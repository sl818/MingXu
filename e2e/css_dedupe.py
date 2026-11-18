# -*- coding: utf-8 -*-
"""CSS 重复选择器合并（保守版）。

只做可证明安全的删除：
  同一选择器在**同一个上下文**（同一 @media 等嵌套链）里出现多次时，
  后面的同名属性声明一定会覆盖前面的。所以前面那条同名声明是死的，可以删。
  若一条规则的声明被删光，整条规则删掉。

刻意跳过的情况（保守，宁可不合并也不改语义）：
  * 简写 / 长写互相影响（margin 与 margin-top、border 与 border-color 等）
  * !important 不一致（前面的带 !important 时它反而会赢）
  * 同一属性组里出现了不同的属性名

用法：
  python css_dedupe.py --dry        只报告，不写文件
  python css_dedupe.py --write      写回 index.html
"""
import re
import sys

# 属性组：同组内出现不同属性名（简写/长写）就跳过，避免误删
GROUPS = ('margin', 'padding', 'border', 'background', 'font', 'flex', 'grid',
          'gap', 'inset', 'overflow', 'transition', 'animation', 'outline',
          'text-decoration', 'list-style', 'place', 'align', 'justify', 'columns')
SHORTHANDS = {
    'margin', 'padding', 'border', 'background', 'font', 'flex', 'grid', 'gap',
    'inset', 'overflow', 'transition', 'animation', 'outline', 'text-decoration',
    'list-style', 'place', 'place-items', 'place-content', 'place-self',
    'columns', 'border-radius', 'border-width', 'border-style', 'border-color',
}


def group_of(prop):
    p = prop.lower()
    for g in GROUPS:
        if p == g or p.startswith(g + '-'):
            return g
    return p


def norm_sel(sel):
    return ','.join(x.strip() for x in re.split(r'\s*,\s*', sel.strip()))


def split_top(s, sep=','):
    parts, depth, cur = [], 0, ''
    for ch in s:
        if ch in '([':
            depth += 1
        elif ch in ')]':
            depth -= 1
        if ch == sep and depth == 0:
            parts.append(cur)
            cur = ''
        else:
            cur += ch
    parts.append(cur)
    return parts


def find_blocks(css, start=0, end=None, ctx=()):
    """扫出所有 rule 块，返回 [(prelude, body, abs_start, abs_end, ctx, body_start, body_end)]。"""
    end = len(css) if end is None else end
    out = []
    i = start
    while i < end:
        # 跳过注释
        if css.startswith('/*', i):
            e = css.find('*/', i + 2)
            i = (e + 2) if e != -1 else end
            continue
        brace = css.find('{', i)
        if brace == -1 or brace >= end:
            break
        prelude = css[i:brace]
        depth = 1
        k = brace + 1
        while k < end and depth > 0:
            if css.startswith('/*', k):
                e = css.find('*/', k + 2)
                k = (e + 2) if e != -1 else end
                continue
            if css[k] == '{':
                depth += 1
            elif css[k] == '}':
                depth -= 1
            k += 1
        body = css[brace + 1:k - 1]
        stripped = prelude.strip()
        if stripped.startswith('@') and '{' in body:
            # 嵌套 at-rule：递归进去，上下文加这一层
            out.extend(find_blocks(css, brace + 1, k - 1, ctx + (stripped,)))
        else:
            out.append((stripped, body, i, k, ctx, brace + 1, k - 1))
        i = k
    return out


def parse_decls(body):
    """把声明体拆成 [(prop, value, important, raw)]；无法解析时返回 None。"""
    out = []
    depth = 0
    cur = ''
    for ch in body:
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        if ch == ';' and depth == 0:
            out.append(cur)
            cur = ''
        else:
            cur += ch
    out.append(cur)
    decls = []
    for raw in out:
        t = raw.strip()
        if not t:
            continue
        if ':' not in t:
            return None
        prop, value = t.split(':', 1)
        prop = prop.strip()
        if not re.fullmatch(r'-{0,2}[a-zA-Z][\w-]*', prop):
            return None
        imp = '!important' in value.lower()
        decls.append((prop.lower(), value.strip(), imp, raw))
    return decls


def removable_indexes(decls, later_decls):
    """返回可安全删除的声明下标集合。"""
    later_by_prop = {}
    for d in later_decls:
        later_by_prop.setdefault(d[0], []).append(d)
    # 本规则与后一条规则里，每个属性组出现过的属性名集合
    groups_seen = {}
    for d in decls + later_decls:
        groups_seen.setdefault(group_of(d[0]), set()).add(d[0])
    kill = set()
    for idx, d in enumerate(decls):
        prop, value, imp, _raw = d
        if prop not in later_by_prop:
            continue
        if prop in SHORTHANDS:
            continue
        if len(groups_seen.get(group_of(prop), ())) > 1:
            continue          # 同组里有长写/简写混用，跳过
        if not imp and any(not x[2] for x in later_by_prop[prop]):
            kill.add(idx)     # 后者无 !important 也能覆盖（本处也无 !important）
        elif imp and any(x[2] for x in later_by_prop[prop]):
            kill.add(idx)     # 双方都是 !important，后者仍赢
    return kill


def main():
    write = '--write' in sys.argv
    # v116 起 CSS 已外移到 assets/app.css（原来是 6 个内联 style 块）。
    # 整个文件天然是一条时间线，不再需要按块拼。
    path = 'assets/app.css'
    with open(path, encoding='utf-8', newline='') as f:
        src = f.read()

    print('文件: %s（%.0f KB）' % (path, len(src) / 1024))

    edits = []
    removed_rules = 0
    trimmed_rules = 0
    killed_decls = 0

    # 把 5 个 style 块里的规则收进同一条时间线：跨块的「后出现者胜」和块内同理
    all_blocks = []      # (norm_sel, ctx, abs_start, abs_end, body_start, body_end, body)
    for b in find_blocks(src):
        all_blocks.append((norm_sel(b[0]), b[4], b[2], b[3], b[5], b[6], b[1]))

    order = []
    seen = {}
    for idx, b in enumerate(all_blocks):
        key = (b[0], b[1])
        order.append((key, b))
        seen.setdefault(key, []).append(idx)

    multi = {k: v for k, v in seen.items() if len(v) > 1}
    print('重复选择器组（含跨块）: %d' % len(multi))

    for key, idxs in multi.items():
        for pos in range(len(idxs) - 1):
            cur = order[idxs[pos]][1]
            nxt = order[idxs[pos + 1]][1]
            cur_decls = parse_decls(cur[6])
            nxt_decls = parse_decls(nxt[6])
            if cur_decls is None or nxt_decls is None:
                continue
            kill = removable_indexes(cur_decls, nxt_decls)
            if not kill:
                continue
            if len(kill) == len(cur_decls):
                edits.append((cur[2], cur[3], ''))
                removed_rules += 1
                killed_decls += len(kill)
            else:
                keep = [d[3] for i, d in enumerate(cur_decls) if i not in kill]
                new_body = ';'.join(x.strip() for x in keep if x.strip())
                edits.append((cur[4], cur[5], new_body))
                trimmed_rules += 1
                killed_decls += len(kill)

    print('可删除整条规则: %d' % removed_rules)
    print('可裁剪部分声明: %d' % trimmed_rules)
    print('合计删除声明: %d' % killed_decls)

    if not write:
        print('\n（dry-run，未写入。加 --write 才改文件）')
        return

    edits.sort(key=lambda x: -x[0])
    out = src
    for start, end, text in edits:
        out = out[:start] + text + out[end:]

    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(out)
    raw = open(path, 'rb').read()
    print('\n已写入。字节 %d，裸 CR %d（应为 0）' % (len(raw), raw.count(b'\r')))


if __name__ == '__main__':
    main()
