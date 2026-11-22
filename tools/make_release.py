# -*- coding: utf-8 -*-
"""生成 Todo-update.zip。

为什么要有这个脚本（v118 的教训）：
    当时是手写文件清单打包，清单里没有 api/mailer.php 和 api/secret_box.php，
    但 api.php 第 42–43 行 require_once 了这两个文件。结果线上除了 status
    （它在 require 之前就返回）以外，**所有接口 500**。
    所以这里改成：固定清单 + 自动收集 + 依赖核对，缺文件直接拒绝打包。

用法：python tools/make_release.py [输出路径]
"""
import glob
import io
import os
import re
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 前端与静态资源：必须逐项列出（打包安全，避免把备份/隐私文件带出去）
FIXED = [
    'index.html',
    'service-worker.js',
    'assets/app.css',
    'assets/theme-v2.css',
    'manifest.json',
    'themes/README.md',
    'icons/icon-192.png',
    'icons/icon-512.png',
    'icons/icon-maskable-512.png',
    'images/landing/today.jpg',
    'images/landing/stats.jpg',
]

# 后端：自动收集，不手写（这次就是手写漏了两个文件）
AUTO = ['api.php', 'api/*.php', 'tools/*.php']
# 这些是环境相关或非运行时代码，不能进包
AUTO_EXCLUDE = {'api/config.php', 'api/config.example.php'}


def rel(p):
    return os.path.relpath(p, ROOT).replace('\\', '/')


def main():
    files = list(FIXED)

    for pat in AUTO:
        for p in glob.glob(os.path.join(ROOT, pat)):
            if os.path.isfile(p):
                r = rel(p)
                if r not in AUTO_EXCLUDE and r not in files:
                    files.append(r)

    # 依赖核对：api.php 里 require 的每个文件都必须在包里
    api_src = io.open(os.path.join(ROOT, 'api.php'), encoding='utf-8', newline='').read()
    required = set(re.findall(r"require(?:_once)?\s+__DIR__\s*\.\s*'/([^']+)'", api_src))
    missing = [r for r in required if r not in files]

    # 版本一致性：index.html 的 ?v= 必须与 service-worker.js 的 VER / CACHE 对齐。
    # 这三处不同步的话，样式会在某些浏览器上「发版了但没生效」——v127 踩过一次。
    html = io.open(os.path.join(ROOT, 'index.html'), encoding='utf-8').read()
    sw = io.open(os.path.join(ROOT, 'service-worker.js'), encoding='utf-8').read()
    m_cache = re.search(r"CACHE = 'lifeboard-shell-(v\d+)'", sw)
    m_ver = re.search(r"VER = '(v\d+)'", sw)
    html_vers = set(re.findall(r'\?v=(\d+)', html))
    if not m_cache or not m_ver:
        print('service-worker.js 里找不到 CACHE / VER，拒绝打包')
        return 1
    if m_cache.group(1) != m_ver.group(1):
        print('版本不一致：CACHE = %s，VER = %s' % (m_cache.group(1), m_ver.group(1)))
        return 1
    want = m_cache.group(1).lstrip('v')
    if html_vers != {want}:
        print('index.html 的样式版本串与 SW 不一致：HTML 是 %s，SW 是 v%s'
              % (sorted(html_vers) or '（没有）', want))
        print('  把 index.html 里所有 ?v=NNN 改成 ?v=%s' % want)
        return 1

    absent = [f for f in files if not os.path.exists(os.path.join(ROOT, f))]
    if absent:
        print('缺文件，拒绝打包：')
        for f in absent:
            print('  -', f)
        return 1
    if missing:
        print('api.php 要求加载但清单里没有（会被线上 500）：')
        for f in missing:
            print('  -', f)
        return 1

    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'Todo-update.zip')
    tmp = out + '.tmp'
    zo = zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED)
    for f in sorted(files):
        zo.write(os.path.join(ROOT, f), f)
    zo.close()
    os.replace(tmp, out)

    php = [f for f in files if f.endswith('.php')]
    print('打包完成：%s' % out)
    print('  共 %d 个文件，其中 PHP %d 个' % (len(files), len(php)))
    print('  依赖核对：api.php 要求 %d 个文件，全部在包内' % len(required))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
