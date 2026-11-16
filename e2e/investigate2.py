# -*- coding: utf-8 -*-
"""查 history 版本历史 + 完整 dump load 数据，定位数据回滚原因。"""
import json
from playwright.sync_api import sync_playwright

URL = "https://your-domain.example"
EMAIL = "test@example.com"
PWD = "test@example.com"

with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome", headless=True)
    pg = b.new_page()

    load_raw = {}

    def on_response(resp):
        if "action=load" in resp.url:
            try:
                load_raw["data"] = resp.json()
            except Exception as e:
                load_raw["err"] = str(e)

    pg.on("response", on_response)

    pg.goto(URL, wait_until="networkidle")
    pg.wait_for_timeout(1000)
    pg.click('[data-act="cloud-login"]')
    pg.wait_for_timeout(600)
    pg.fill('input[name="email"]', EMAIL)
    pg.fill('input[name="password"]', PWD)
    pg.click('form.modal-card button[type="submit"]')
    pg.wait_for_timeout(4000)

    # 完整 load 数据
    d = load_raw.get("data", {})
    data = d.get("data") if isinstance(d, dict) else d
    print("=== LOAD data 顶层键 ===")
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, list):
                print(f"  {k}: list[{len(v)}]")
                for i, item in enumerate(v[:6]):
                    name = item.get("name") if isinstance(item, dict) else item
                    cid = item.get("id", "?") if isinstance(item, dict) else ""
                    cat = item.get("createdAt", "") if isinstance(item, dict) else ""
                    print(f"      [{i}] {name}  (id={cid}, createdAt={cat})")
            elif isinstance(v, dict):
                print(f"  {k}: dict, keys={list(v.keys())[:10]}")
            else:
                print(f"  {k}: {str(v)[:80]}")
    print("\n=== LOAD 完整 JSON (前 2500 字) ===")
    print(json.dumps(data, ensure_ascii=False)[:2500])

    # 查 history 版本历史
    print("\n\n=== history 接口 ===")
    try:
        hist = pg.evaluate("""async () => {
            const r = await fetch('/api.php?action=history', {credentials:'include'});
            return await r.json();
        }""")
        print(json.dumps(hist, ensure_ascii=False)[:2500])
    except Exception as e:
        print("history 调用失败:", e)

    b.close()
