# -*- coding: utf-8 -*-
"""侦察脚本：打开线上站点，dump 登录页与登录后的 DOM 结构，用于定位交互元素。"""
from playwright.sync_api import sync_playwright
import json

URL = "https://todo.csl88.top"
EMAIL = "test@sl00.top"
PWD = "test@sl00.top"

errors = {"pageerror": [], "console_error": [], "failed": [], "http4xx5xx": []}


def hook(pg):
    pg.on("pageerror", lambda e: errors["pageerror"].append(str(e)))
    pg.on("console", lambda m: errors["console_error"].append(m.text) if m.type == "error" else None)
    pg.on("requestfailed", lambda r: errors["failed"].append(f"{r.method} {r.url} -> {r.failure}"))
    pg.on("response", lambda r: errors["http4xx5xx"].append(f"{r.status} {r.request.method} {r.url}") if r.status >= 400 else None)


def dump_inputs(pg, label):
    print(f"\n===== {label} =====")
    els = pg.eval_on_selector_all("input, textarea, select, button", """
        els => els.map(e => ({
            tag: e.tagName,
            type: e.getAttribute('type'),
            id: e.id,
            name: e.getAttribute('name'),
            placeholder: e.getAttribute('placeholder'),
            text: (e.innerText || '').trim().slice(0, 30),
            dataAct: e.getAttribute('data-act'),
            dataId: e.getAttribute('data-id'),
            dataKey: e.getAttribute('data-key'),
            cls: e.className.slice(0, 60)
        }))
    """)
    for e in els:
        print(json.dumps(e, ensure_ascii=False))


def dump_clickables(pg, label):
    print(f"\n===== {label} clickables =====")
    els = pg.eval_on_selector_all("[data-act], .nav-item, .btn, .icon-btn", """
        els => els.map(e => ({
            tag: e.tagName,
            text: (e.innerText || '').trim().slice(0, 24),
            dataAct: e.getAttribute('data-act'),
            cls: e.className.slice(0, 50),
            href: e.getAttribute('href')
        }))
    """)
    for e in els:
        print(json.dumps(e, ensure_ascii=False))


with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome", headless=True)
    pg = b.new_page(viewport={"width": 1366, "height": 900})
    hook(pg)

    pg.goto(URL, wait_until="networkidle")
    pg.wait_for_timeout(1500)
    print("TITLE:", pg.title())
    print("URL:", pg.url)
    pg.screenshot(path="e2e/00-landing.png", full_page=True)

    # 页面可见文本（前 1500 字符）
    txt = pg.evaluate("() => document.body.innerText")
    print("\n----- BODY TEXT (head) -----")
    print(txt[:1500])

    dump_inputs(pg, "landing inputs")
    dump_clickables(pg, "landing clickables")

    b.close()

print("\n===== ERRORS SO FAR =====")
print(json.dumps(errors, ensure_ascii=False, indent=2))
