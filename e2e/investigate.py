# -*- coding: utf-8 -*-
"""调查：登录后 force 请求的 body 是什么？load 返回的云端数据是什么？"""
import json
from playwright.sync_api import sync_playwright

URL = "https://your-domain.example"
EMAIL = "test@example.com"
PWD = "test@example.com"

with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome", headless=True)
    ctx = b.new_context()
    pg = ctx.new_page()

    def on_request(req):
        if "api.php" in req.url and req.method == "POST":
            body = req.post_data or ""
            print(f"\n>>> POST {req.url.split('action=')[-1]}")
            print("    body:", body[:600])

    def on_response(resp):
        if "action=load" in resp.url:
            try:
                data = resp.json()
                print(f"\n>>> LOAD 响应 (action=load)")
                d = data.get("data") if isinstance(data, dict) else data
                s = json.dumps(d, ensure_ascii=False) if not isinstance(d, str) else d
                print("    data 长度:", len(s))
                print("    data 前 500 字:", s[:500])
            except Exception as e:
                print("    load 解析失败:", e)

    pg.on("request", on_request)
    pg.on("response", on_response)

    pg.goto(URL, wait_until="networkidle")
    pg.wait_for_timeout(1000)
    pg.click('[data-act="cloud-login"]')
    pg.wait_for_timeout(600)
    pg.fill('input[name="email"]', EMAIL)
    pg.fill('input[name="password"]', PWD)
    pg.click('form.modal-card button[type="submit"]')
    pg.wait_for_timeout(4000)

    print("\n\n=== 登录后今日页完整文本 ===")
    print(pg.evaluate("() => document.body.innerText")[:1500])

    b.close()
