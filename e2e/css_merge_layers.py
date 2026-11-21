# -*- coding: utf-8 -*-
"""CSS 版本分层合并（按 REFACTOR-PLAN 阶段 0 第二步）。

目标：同一选择器在同一上下文（@media 链）里被多次定义时，
合成一条规则，放到**最后一次出现的位置**，删掉前面的。

生效语义：「保留最后生效的那份值」——
  * 同属性后者覆盖前者（!important 优先于普通，同级后者胜）；
  * 简写覆盖它包含的长写（如 margin 覆盖 margin-top），
    但长写不覆盖简写（margin-top 不删 margin）；
  * 其余声明按原先后顺序全部保留。

有意不做：跨选择器的静态证明（做不到）。合并只保证「同选择器自身」的
层叠结果不变；跨选择器的影响靠六皮肤截图比对 + 三套对比度审计 + 全量 e2e 验证。

用法：
  python css_merge_layers.py --dry     只报告
  python css_merge_layers.py --write   写回 assets/app.css
"""
import re
import sys

PATH = 'assets/app.css'

# 简写 -> 它覆盖的长写（写错了会真删错声明，宁可少列不可错列）
LONGHANDS = {
    'margin': ['margin-top', 'margin-right', 'margin-bottom', 'margin-left'],
    'padding': ['padding-top', 'padding-right', 'padding-bottom', 'padding-left'],
    'border': [p for side in ('', 'top-', 'right-', 'bottom-', 'left-')
               for p in ('border-%swidth' % side, 'border-%sstyle' % side, 'border-%scolor' % side)]
              + ['border-top', 'border-right', 'border-bottom', 'border-left'],
    'border-width': ['border-top-width', 'border-right-width', 'border-bottom-width', 'border-left-width'],
    'border-style': ['border-top-style', 'border-right-style', 'border-bottom-style', 'border-left-style'],
    'border-color': ['border-top-color', 'border-right-color', 'border-bottom-color', 'border-left-color'],
    'border-top': ['border-top-width', 'border-top-style', 'border-top-color'],
    'border-right': ['border-right-width', 'border-right-style', 'border-right-color'],
    'border-bottom': ['border-bottom-width', 'border-bottom-style', 'border-bottom-color'],
    'border-left': ['border-left-width', 'border-left-style', 'border-left-color'],
    'border-radius': ['border-top-left-radius', 'border-top-right-radius',
                      'border-bottom-right-radius', 'border-bottom-left-radius'],
    'background': ['background-image', 'background-position', 'background-size', 'background-repeat',
                   'background-origin', 'background-clip', 'background-attachment', 'background-color',
                   'background-blend-mode', 'background-position-x', 'background-position-y'],
    'font': ['font-style', 'font-variant', 'font-weight', 'font-stretch', 'font-size',
             'line-height', 'font-family'],
    'flex': ['flex-grow', 'flex-shrink', 'flex-basis'],
    'gap': ['row-gap', 'column-gap'],
    'overflow': ['overflow-x', 'overflow-y'],
    'transition': ['transition-property', 'transition-duration', 'transition-timing-function',
                   'transition-delay', 'transition-behavior'],
    'animation': ['animation-name', 'animation-duration', 'animation-timing-function',
                  'animation-delay', 'animation-iteration-count', 'animation-direction',
                  'animation-fill-mode', 'animation-play-state'],
    'outline': ['outline-width', 'outline-style', 'outline-color'],
    'text-decoration': ['text-decoration-line', 'text-decoration-style', 'text-decoration-color',
                        'text-decoration-thickness'],
    'list-style': ['list-style-type', 'list-style-position', 'list-style-image'],
    'inset': ['top', 'right', 'bottom', 'left'],
    'columns': ['column-count', 'column-width'],
    'place-items': ['align-items', 'justify-items'],
    'place-content': ['align-content', 'justify-content'],
    'place-self': ['align-self', 'justify-self'],
}


def norm_sel(sel):
    return ','.join(x.strip() for x in re.split(r'\s*,\s*', sel.strip()))


def find_blocks(css, start=0, end=None, ctx=()):
    end = len(css) if end is None else end
    out = []
    i = start
    while i < end:
        # 跳过空白与注释（注释里可能带示例用的 {}，不剥会错配）
        while i < end:
            if css.startswith('/*', i):
                e = css.find('*/', i + 2)
                i = (e + 2) if e != -1 else end
            elif css[i] in ' \t\r\n':
                i += 1
            else:
                break
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
            out.extend(find_blocks(css, brace + 1, k - 1, ctx + (stripped,)))
        else:
            out.append((stripped, body, i, k, ctx, brace + 1, k - 1))
        i = k
    return out


def parse_decls(body):
    # 声明体里的行内注释先剥掉（合并后的规则不保留行内注释，属可接受损耗）
    body = re.sub(r'/\*.*?\*/', '', body, flags=re.S)
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
        decls.append((prop.lower(), value.strip(), imp, t))
    return decls


def overrides(later, earlier):
    """later 是否完全覆盖 earlier（同组规则链内）。"""
    lp, _lv, li, _lr = later
    ep, _ev, ei, _er = earlier
    if li < ei:                       # 普通不能压 important
        return False
    if lp == ep:
        return True
    return ep in LONGHANDS.get(lp, [])


def merge_group(occs):
    """occs: 同组规则（按出现顺序）。返回 (merged_body, n_removed_decls) 或 None。"""
    decls = []
    for oi, occ in enumerate(occs):
        d = parse_decls(occ[1])
        if d is None:
            return None
        for di, one in enumerate(d):
            decls.append((oi, di, one))
    drop = set()
    for i in range(len(decls)):
        for j in range(i + 1, len(decls)):
            if overrides(decls[j][2], decls[i][2]):
                drop.add(i)
                break
    keep = [decls[i][2][3] for i in range(len(decls)) if i not in drop]
    if not keep:
        return ('', len(decls))
    return (';'.join(keep) + ';', len(drop))


def build_merged(src):
    """返回 (合并后文本, 统计字典)；任何规则体无法解析则返回 (None, 原因)。

    抽成函数供 e2e/css_equiv_check.py 复用，保证「验证用的合并产物」与
    「实际落盘的合并产物」是同一套逻辑，不会漂移。
    """
    blocks = find_blocks(src)
    groups = {}
    for idx, b in enumerate(blocks):
        groups.setdefault((b[4], norm_sel(b[0])), []).append(idx)

    multi = {k: v for k, v in groups.items() if len(v) > 1}
    edits = []            # (abs_start, abs_end, replacement)
    merged = removed = skipped = 0
    drop_total = 0
    for key, idxs in multi.items():
        occs = [blocks[i] for i in idxs]
        r = merge_group(occs)
        if r is None:
            skipped += 1
            continue
        body, dropped = r
        drop_total += dropped
        # 最后一次出现的位置：换上合并后的声明体
        last = occs[-1]
        edits.append((last[5], last[6], body))
        # 前面的整条删除（连同前导空白与尾巴换行）
        for occ in occs[:-1]:
            s, e = occ[2], occ[3]
            while s > 0 and src[s - 1] in ' \t':
                s -= 1
            if e < len(src) and src[e] == '\n':
                e += 1
            edits.append((s, e, ''))
        merged += 1
        removed += len(occs) - 1

    edits.sort(key=lambda x: -x[0])
    out = src
    for s, e, t in edits:
        out = out[:s] + t + out[e:]

    # 全量解析保护：任何一条规则体解析失败都不返回成果
    for b in find_blocks(out):
        if parse_decls(b[1]) is None:
            return None, '合并后存在无法解析的规则体: %s' % b[0][:60]
    return out, {
        'groups': len(multi),
        'rules': sum(len(v) for v in multi.values()),
        'merged': merged,
        'removed_rules': removed,
        'removed_decls': drop_total,
        'skipped': skipped,
    }


def main():
    write = '--write' in sys.argv
    with open(PATH, encoding='utf-8', newline='') as f:
        src = f.read()

    out, info = build_merged(src)
    if out is None:
        print('!! %s —— 已放弃写入' % info)
        return
    print('重复选择器组: %d（共 %d 条规则）' % (info['groups'], info['rules']))
    print('合并组: %d｜删除整条规则: %d｜删除被覆盖声明: %d｜跳过（含注释/无法解析）: %d'
          % (info['merged'], info['removed_rules'], info['removed_decls'], info['skipped']))

    if not write:
        print('（dry-run，加 --write 写回）')
        return

    with open(PATH, 'w', encoding='utf-8', newline='') as f:
        f.write(out)
    raw = open(PATH, 'rb').read()
    print('已写入 %s：%d → %d 字节，裸 CR %d' % (PATH, len(src.encode("utf-8")), len(raw), raw.count(b'\r')))


if __name__ == '__main__':
    main()
