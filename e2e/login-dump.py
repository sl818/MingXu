# -*- coding: utf-8 -*-
"""登录并 dump 登录后的导航结构与今日页元素。"""
from playwright.sync_api import sync_playwright
import json

URL = "https://todo.csl88.top"
EMAIL = "test@sl00.top"
PWD = "test@sl00.top"
errors = {"pageerror": [], "console_error": [], "failed": [], "http4xx5xx": [], "http_all": []}


def hook(pg):
    pg.on("pageerror", lambda e: errors["pageerror"].append(str(e)))
    pg.on("console", lambda m: errors["console_error"].append(m.text) if m.type == "error" else None)
    pg.on("requestfailed", lambda r: errors["failed"].append(f"{r.method} {r.url} -> {r.failure}"))
    pg.on("response", lambda r: (
        errors["http_all"].append(f"{r.status} {r.request.method} {r.url}") if "api" in r.url else None,
        errors["http4xx5xx"].append(f"{r.status} {r.request.method} {r.url}") if r.status >= 400 else None,
    ))


def dump(pg, sel, label):
    print(f"\n===== {label} =====")
    els = pg.eval_on_selector_all(sel, """
        els => els.map(e => ({tag: e.tagName, text: (e.innerText||'').trim().slice(0,26),
            dataAct: e.getAttribute('data-act'), id: e.id, cls: e.className.slice(0,46), href: e.getAttribute('href')}))
    """)
    for e in els:
        print(json.dumps(e, ensure_ascii=False))


with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome", headless=True)
    pg = b.new_page(viewport={"width": 1366, "height": 900})
    hook(pg)
    pg.goto(URL, wait_until="networkidle")
    pg.wait_for_timeout(1000)

    # 登录
    pg.click('[data-act="cloud-login"]')
    pg.wait_for_timeout(800)
    pg.fill('input[name="email"]', EMAIL)
    pg.fill('input[name="password"]', PWD)
    pg.click('form.modal-card button[type="submit"]')
    pg.wait_for_timeout(3500)

    print("URL after login:", pg.url)
    print("TITLE:", pg.title())
    print("SKIN:", pg.evaluate("() => document.documentElement.getAttribute('data-skin')"))
    print("THEME:", pg.evaluate("() => document.documentElement.getAttribute('data-theme')"))
    pg.screenshot(path="e2e/02-after-login.png", full_page=True)

    txt = pg.evaluate("() => document.body.innerText")
    print("\n----- BODY TEXT (head 1200) -----")
    print(txt[:1200])

    dump(pg, ".nav-item, [class*=nav]", "NAV")
    dump(pg, "[data-act]", "ALL data-act")

    b.close()

print("\n===== HTTP (api) =====")
for x in errors["http_all"]:
    print(x)
print("\n===== ERRORS =====")
print(json.dumps({k: v for k, v in errors.items() if k != "http_all"}, ensure_ascii=False, indent=2))
