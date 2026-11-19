"""核对文档里的锚点是否真实存在，防止文档撒谎。

抽四类锚点逐个验证：
  1. 反引号里的 函数名(  → index.html 或 api/*.php 里要有 function 函数名
  2. data-act="x" / 'x': 形式的 ACTIONS 键 → ACTIONS 里要有这个键
  3. 文件路径（api/xxx.php、themes/xxx.css 等）→ 磁盘上要存在
  4. CSS 类名 .xxx → index.html 或 themes/*.css 里要出现

只报"文档提到但代码里没有"的，这是真正会误导下一个人的。

例外：写在「已删除 / 废弃 / 移除」这类说明行里的符号是历史记录，不是撒谎，直接跳过。
否则每删一个功能，那段「vNN 删掉了 xxx」的说明都会变成假报错。
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 文档都在 docs/ 下（根目录只留 README.md 作入口）
DOCS = ['docs/ARCHITECTURE.md', 'docs/FRONTEND.md', 'docs/BACKEND.md',
        'docs/DATA-MODEL.md', 'docs/README.md', 'docs/HANDOFF.md',
        'docs/SITE-STRUCTURE.md', 'docs/DEPLOY.md',
        'docs/THEME-SPEC.md', 'docs/AI-THEME-GUIDE.md',
        'docs/REFACTOR-PLAN.md', 'docs/CHANGE-MAP.md',
        'docs/BRAND.md', 'docs/RENAME-PLAN.md', 'docs/DESIGN-LIB.md',
        'README.md']

# 已知的"不是代码符号"的白名单，避免误报
NOT_CODE = {
    'json()', 'array()', 'string()', 'int()', 'bool()', 'number()', 'object()',
    'continue()', 'return()', 'if()', 'for()', 'function()', 'isset()', 'empty()',
    'Number()', 'String()', 'Array()', 'Math.max()', 'Math.round()',
    'Date.now()', 'JSON.parse()', 'JSON.stringify()', 'Object.assign()',
    'parseInt()', 'isFinite()', 'getComputedStyle()', 'querySelector()',
    'addEventListener()', 'setTimeout()', 'setInterval()', 'require()',
    'require_once()', 'define()', 'date()', 'strtotime()', 'count()',
    'trim()', 'is_array()', 'json_decode()', 'json_encode()', 'error_log()',
    'password_verify()', 'microtime()', 'round()', 'strlen()', 'substr()',
    'slice()', 'split()', 'join()', 'replace()', 'filter()', 'map()',
    'forEach()', 'sort()', 'push()', 'concat()', 'indexOf()', 'includes()',
}


def load(p):
    return io.open(p, encoding='utf-8', newline='').read().replace('\r\n', '\n')


def main():
    index = load(os.path.join(ROOT, 'index.html'))
    backend_src = ''
    for f in sorted(os.listdir(os.path.join(ROOT, 'api'))):
        if f.endswith('.php'):
            backend_src += load(os.path.join(ROOT, 'api', f))
    root_php = ''
    for f in ('api.php',):
        root_php += load(os.path.join(ROOT, f))
    tools_src = ''
    for f in sorted(os.listdir(os.path.join(ROOT, 'tools'))):
        if f.endswith('.php'):
            tools_src += load(os.path.join(ROOT, 'tools', f))
    # v116：CSS 已外移到 assets/app.css，符号不再全在 index.html 里。
    # 不把这份算进去，所有 .class 和 CSS 关键字都会变成「不存在」的假报错。
    app_css = ''
    app_css_path = os.path.join(ROOT, 'assets', 'app.css')
    if os.path.exists(app_css_path):
        app_css = load(app_css_path)
    all_code = index + app_css + backend_src + root_php + tools_src

    themes_css = ''
    for f in sorted(os.listdir(os.path.join(ROOT, 'themes'))):
        if f.endswith('.css'):
            themes_css += load(os.path.join(ROOT, 'themes', f))
    all_css = index + app_css + themes_css

    # ACTIONS 键集合
    m = re.search(r'const ACTIONS = \{(.*?)\n  \};', index, re.S)
    act_block = m.group(1) if m else ''
    action_keys = set(re.findall(r"^    '?([a-zA-Z0-9_-]+)'?:", act_block, re.M))

    # VIEWS 键
    m = re.search(r'const VIEWS = \{(.*?)\};', index, re.S)
    view_keys = set(k.strip() for k in m.group(1).split(',')) if m else set()
    view_keys = set(k.split(':')[0].strip().strip("'\"") for k in view_keys if ':' in k)

    # 后端 action
    api_actions = set(re.findall(r"case '([a-z_]+)':", root_php))

    problems = []
    del_by_doc = {}

    def deletion_spans(text):
        """收集出现在「已删除 / 废弃 / 移除」说明行里的反引号符号，后面按行豁免。"""
        out = set()
        for line in text.split('\n'):
            if re.search(r'删|移除|废弃|去掉', line):
                out.update(x.strip() for x in re.findall(r'`([^`\n]+)`', line))
        return out

    for doc in DOCS:
        path = os.path.join(ROOT, doc)
        if not os.path.isfile(path):
            problems.append((doc, '整个文件缺失', ''))
            continue
        text = load(path)
        del_by_doc[doc] = deletion_spans(text)
        code_spans = re.findall(r'`([^`\n]+)`', text)

        # 1. 函数名（只认干净标识符，跳过伪代码和内置方法）
        for span in code_spans:
            body = span.strip()
            if ' ' in body or '$' in body or "'" in body or '"' in body:
                continue
            fm = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)\s*\(', body)
            if not fm:
                continue
            fn = fm.group(1)
            if fn + '()' in NOT_CODE or fn in NOT_CODE:
                continue
            if len(fn) < 4:
                continue
            if not re.search(r'function\s+' + re.escape(fn) + r'\b', all_code) \
                    and not re.search(r'\b' + re.escape(fn) + r'\s*[:=]', all_code):
                problems.append((doc, '函数不存在', body[:60]))

        # 2. data-act 值
        for act in re.findall(r'data-act="([a-z-]+)"', text):
            if act not in action_keys:
                problems.append((doc, 'ACTIONS 缺这个键', 'data-act="%s"' % act))

        # 3. 显式写的 ACTIONS 键 `'x':`
        for act in re.findall(r"ACTIONS\['([a-z-]+)'\]", text):
            if act not in action_keys:
                problems.append((doc, 'ACTIONS 缺这个键', act))

        # 3b. 文档表格里写成 `xxx` 且形如 act 的（形如 动词-名词）
        for span in code_spans:
            s = span.strip()
            if re.match(r'^[a-z]+(-[a-z]+)+$', s) and len(s) > 5:
                if s in action_keys or s in all_code:
                    continue
                if os.path.exists(os.path.join(ROOT, 'e2e', s + '.py')):
                    continue
                problems.append((doc, '疑似 act/标识不存在', s))

        # 4. 文件路径：写了目录就按路径找；只写文件名就按文件名在整个项目里找
        all_files = set()
        for dirpath, _dirs, files in os.walk(ROOT):
            if any(x in dirpath for x in ('.git', 'design', 'beifen-dsh', 'node_modules')):
                continue
            for f in files:
                all_files.add(f)
        for p in re.findall(r'`([A-Za-z0-9_./-]+\.(?:php|css|js|json|mjs|sql|md))`', text):
            if p.startswith('/') or '*' in p:
                continue
            # 占位符（YYYY / xx / ...）是说明用的，不是真文件
            if 'YYYY' in p or 'XX' in p or '...' in p:
                continue
            # 以 ../ 开头的按「文档所在目录」解析（文档在 docs/ 下时指向仓库根）
            if p.startswith('../'):
                if os.path.exists(os.path.normpath(os.path.join(ROOT, os.path.dirname(doc), p))):
                    continue
                problems.append((doc, '文件不存在', p))
                continue
            # 示例文件名：形如 2026-10-29.php 的备份快照举例
            base = os.path.basename(p)
            if re.match(r'^\d{4}-\d{2}-\d{2}\.', base):
                continue
            if os.path.exists(os.path.join(ROOT, p.replace('/', os.sep))):
                continue
            # 只写了文件名（没有目录）且项目里存在同名文件 → 算通过
            if '/' not in p and p in all_files:
                continue
            problems.append((doc, '文件不存在', p))


        # 5. CSS 类
        for cls in re.findall(r'`\.([a-zA-Z][a-zA-Z0-9_-]{2,})`', text):
            # .gitignore / .env / .htaccess 这类是文件名，不是 CSS 类
            if cls.lower() in ('gitignore', 'gitattributes', 'env', 'htaccess', 'user', 'project',
                               'svn', 'ds', 'lock', 'ini', 'json', 'php', 'md', 'py'):
                continue
            if ('.' + cls) not in all_css:
                problems.append((doc, 'CSS 类不存在', '.' + cls))

    # 去重
    seen = set()
    out = []
    for doc, kind, detail in problems:
        spans = del_by_doc.get(doc, set())
        if any(x and (x in detail or detail in x) for x in spans):
            continue
        k = (doc, kind, detail)
        if k in seen:
            continue
        seen.add(k)
        out.append(k)

    if not out:
        print('全部锚点核对通过：没有发现"文档提到、代码里没有"的符号。')
        return 0

    print('发现 %d 处不一致：' % len(out))
    cur = None
    for doc, kind, detail in sorted(out):
        if doc != cur:
            print('\n──── %s' % doc)
            cur = doc
        print('  [%s] %s' % (kind, detail))
    return 1


if __name__ == '__main__':
    sys.exit(main())
