# -*- coding: utf-8 -*-
"""点击登录按钮，dump 登录模态框内的输入框与提交按钮结构。"""
from playwright.sync_api import sync_playwright
import json

URL = "https://your-domain.example"
errors = {"pageerror": [], "console_error": [], "failed": [], "http4xx5xx": []}


def hook(pg):
    pg.on("pageerror", lambda e: errors["pageerror"].append(str(e)))
    pg.on("console", lambda m: errors["console_error"].append(m.text) if m.type == "error" else None)
    pg.on("requestfailed", lambda r: errors["failed"].append(f"{r.method} {r.url} -> {r.failure}"))
    pg.on("response", lambda r: errors["http4xx5xx"].append(f"{r.status} {r.request.method} {r.url}") if r.status >= 400 else None)


with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome", headless=True)
    pg = b.new_page(viewport={"width": 1366, "height": 900})
    hook(pg)
    pg.goto(URL, wait_until="networkidle")
    pg.wait_for_timeout(1000)

    # 点击登录按钮
    pg.click('[data-act="cloud-login"]')
    pg.wait_for_timeout(1200)

    # dump 模态框
    modal = pg.eval_on_selector_all(".modal, [class*=modal], form", """
        els => els.map(e => ({tag: e.tagName, cls: e.className.slice(0,60), display: getComputedStyle(e).display}))
    """)
    print("MODALS:", json.dumps(modal, ensure_ascii=False))

    els = pg.eval_on_selector_all("input, textarea, select, button", """
        els => els.map(e => ({
            tag: e.tagName, type: e.getAttribute('type'), id: e.id, name: e.getAttribute('name'),
            placeholder: e.getAttribute('placeholder'), text: (e.innerText||'').trim().slice(0,30),
            dataAct: e.getAttribute('data-act'), cls: e.className.slice(0,60)
        }))
    """)
    print("\nALL INPUTS AFTER CLICK:")
    for e in els:
        print(json.dumps(e, ensure_ascii=False))

    pg.screenshot(path="e2e/01-login-modal.png")

    b.close()

print("\nERRORS:", json.dumps(errors, ensure_ascii=False, indent=2))
