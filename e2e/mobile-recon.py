# -*- coding: utf-8 -*-
"""移动端侦察：iPhone 视口下登录 + dump 底部 tabbar 与布局。"""
import json
from playwright.sync_api import sync_playwright

URL = "https://todo.csl88.top"
EMAIL = "test@sl00.top"
PWD = "test@sl00.top"

with sync_playwright() as p:
    device = p.devices["iPhone 13"]
    b = p.chromium.launch(channel="chrome", headless=True)
    ctx = b.new_context(**device)
    pg = ctx.new_page()

    pg.goto(URL, wait_until="networkidle")
    pg.wait_for_timeout(1200)
    print("视口:", pg.evaluate("() => [innerWidth, innerHeight]"))
    print("横向溢出(落地页):", pg.evaluate("() => document.documentElement.scrollWidth > innerWidth + 1"))
    pg.screenshot(path="e2e/shots/m-01-landing.png", full_page=True)

    # 登录
    pg.click('[data-act="cloud-login"]')
    pg.wait_for_timeout(600)
    pg.fill('input[name="email"]', EMAIL)
    pg.fill('input[name="password"]', PWD)
    pg.click('form.modal-card button[type="submit"]')
    pg.wait_for_timeout(3500)
    pg.screenshot(path="e2e/shots/m-02-after-login.png", full_page=True)

    # dump 移动端导航
    print("\n===== mobile-tab 结构 =====")
    tabs = pg.eval_on_selector_all(".mobile-tab", """
        els => els.map(e => ({text: (e.innerText||'').trim(), cls: e.className}))
    """)
    for t in tabs:
        print(json.dumps(t, ensure_ascii=False))

    print("\n===== nav-item 是否可见 =====")
    print(pg.eval_on_selector_all(".nav-item", "els => els.map(e => getComputedStyle(e).display)"))
    print("===== mobile-tabbar 是否可见 =====")
    print(pg.eval_on_selector_all(".mobile-tabbar, [class*=tabbar]", "els => els.map(e => [e.className, getComputedStyle(e).display])"))

    # 点击「更多」看 viewMore 结构
    pg.click('.mobile-tab:has-text("更多")')
    pg.wait_for_timeout(1200)
    pg.screenshot(path="e2e/shots/m-03-more.png", full_page=True)
    print("\n===== 更多页内容(前600字) =====")
    print(pg.evaluate("() => document.body.innerText").replace("\n", " | ")[:600])

    b.close()
