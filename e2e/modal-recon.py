# -*- coding: utf-8 -*-
"""点击『新建任务』『添加习惯』，dump 各自模态框的表单字段。"""
from playwright.sync_api import sync_playwright
import json

URL = "https://your-domain.example"
EMAIL = "test@example.com"
PWD = "test@example.com"
errors = {"pageerror": [], "console_error": [], "failed": [], "http4xx5xx": []}


def hook(pg):
    pg.on("pageerror", lambda e: errors["pageerror"].append(str(e)))
    pg.on("console", lambda m: errors["console_error"].append(m.text) if m.type == "error" else None)
    pg.on("requestfailed", lambda r: errors["failed"].append(f"{r.method} {r.url} -> {r.failure}"))
    pg.on("response", lambda r: errors["http4xx5xx"].append(f"{r.status} {r.request.method} {r.url}") if r.status >= 400 else None)


def dump_form(pg, label):
    print(f"\n===== {label} 表单字段 =====")
    els = pg.eval_on_selector_all(".modal-card input, .modal-card textarea, .modal-card select, .modal-card button", """
        els => els.map(e => ({tag: e.tagName, type: e.getAttribute('type'), name: e.getAttribute('name'),
            id: e.id, placeholder: e.getAttribute('placeholder'), value: (e.value||'').slice(0,20),
            text: (e.innerText||'').trim().replace(/\\n/g,'/').slice(0,24), dataAct: e.getAttribute('data-act'),
            cls: e.className.slice(0,44)}))
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

    # 新建任务
    pg.click('.nav-item:has-text("待办")')
    pg.wait_for_timeout(1200)
    pg.click('button[data-act="task-new"]:has-text("新建任务")')
    pg.wait_for_timeout(1000)
    pg.screenshot(path="e2e/05-task-modal.png")
    dump_form(pg, "新建任务")

    # 关闭
    pg.click('[data-act="close-modal"]')
    pg.wait_for_timeout(600)

    # 添加习惯
    pg.click('.nav-item:has-text("习惯")')
    pg.wait_for_timeout(1200)
    pg.click('[data-act="habit-new"]')
    pg.wait_for_timeout(1000)
    pg.screenshot(path="e2e/06-habit-modal.png")
    dump_form(pg, "添加习惯")

    b.close()

print("\n===== ERRORS =====")
print(json.dumps(errors, ensure_ascii=False, indent=2))
