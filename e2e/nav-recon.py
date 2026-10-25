# -*- coding: utf-8 -*-
"""登录后探索『待办』『习惯』页的新增入口。"""
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


def dump(pg, sel, label):
    print(f"\n===== {label} =====")
    els = pg.eval_on_selector_all(sel, """
        els => els.map(e => ({tag: e.tagName, text: (e.innerText||'').trim().replace(/\\n/g,'/').slice(0,32),
            dataAct: e.getAttribute('data-act'), type: e.getAttribute('type'),
            placeholder: e.getAttribute('placeholder'), id: e.id, cls: e.className.slice(0,50)}))
    """)
    for e in els:
        print(json.dumps(e, ensure_ascii=False))


def login(pg):
    pg.goto(URL, wait_until="networkidle")
    pg.wait_for_timeout(800)
    pg.click('[data-act="cloud-login"]')
    pg.wait_for_timeout(600)
    pg.fill('input[name="email"]', EMAIL)
    pg.fill('input[name="password"]', PWD)
    pg.click('form.modal-card button[type="submit"]')
    pg.wait_for_timeout(3000)


with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome", headless=True)
    pg = b.new_page(viewport={"width": 1366, "height": 900})
    hook(pg)
    login(pg)

    # 待办页
    pg.click('.nav-item:has-text("待办")')
    pg.wait_for_timeout(1500)
    pg.screenshot(path="e2e/03-board.png", full_page=True)
    dump(pg, "button, input, [data-act]", "待办页 buttons/inputs")

    # 习惯页
    pg.click('.nav-item:has-text("习惯")')
    pg.wait_for_timeout(1500)
    pg.screenshot(path="e2e/04-habits.png", full_page=True)
    dump(pg, "button, input, [data-act]", "习惯页 buttons/inputs")

    b.close()

print("\n===== ERRORS =====")
print(json.dumps(errors, ensure_ascii=False, indent=2))
