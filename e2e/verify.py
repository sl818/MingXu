# -*- coding: utf-8 -*-
"""核实：登录 test@sl00.top，检查之前写入的测试数据是否还在云端。"""
from playwright.sync_api import sync_playwright

URL = "https://todo.csl88.top"
EMAIL = "test@sl00.top"
PWD = "test@sl00.top"

with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome", headless=True)
    pg = b.new_page(viewport={"width": 1366, "height": 900})
    pg.on("response", lambda r: print(f"  [api] {r.status} {r.request.method} {r.url}") if "api.php" in r.url else None)

    pg.goto(URL, wait_until="networkidle")
    pg.wait_for_timeout(1000)
    pg.click('[data-act="cloud-login"]')
    pg.wait_for_timeout(600)
    pg.fill('input[name="email"]', EMAIL)
    pg.fill('input[name="password"]', PWD)
    pg.click('form.modal-card button[type="submit"]')
    pg.wait_for_timeout(3500)

    print("登录后 sync-indicator:", pg.locator("#sync-indicator").inner_text())

    # 待办页
    pg.click('.nav-item:has-text("待办")')
    pg.wait_for_timeout(1500)
    tasks = pg.eval_on_selector_all(".task .task-title, .task [class*=title], .task-row", """
        els => els.map(e => (e.innerText||'').trim().replace(/\\n/g,' ').slice(0,40))
    """)
    print("\n=== 待办看板内容 ===")
    for t in tasks:
        print("  -", t)

    # 直接找 #1126 关键字
    has_1126 = pg.locator("text=#1126").count()
    print("\n含 '#1126' 的元素数量:", has_1126)

    # 习惯页
    pg.click('.nav-item:has-text("习惯")')
    pg.wait_for_timeout(1500)
    habits = pg.eval_on_selector_all(".habit-card, .habit-card [class*=name]", """
        els => els.map(e => (e.innerText||'').trim().replace(/\\n/g,' ').slice(0,40))
    """)
    print("\n=== 习惯页内容 ===")
    for h in habits:
        print("  -", h)

    b.close()
