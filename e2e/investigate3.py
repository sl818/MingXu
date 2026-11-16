# -*- coding: utf-8 -*-
"""预览 rev90(6019B) 与 rev91(3947B) 的内容，比对差异，定位数据丢失。"""
import json
from playwright.sync_api import sync_playwright

URL = "https://your-domain.example"
EMAIL = "test@example.com"
PWD = "test@example.com"

with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome", headless=True)
    pg = b.new_page()
    pg.goto(URL, wait_until="networkidle")
    pg.wait_for_timeout(1000)
    pg.click('[data-act="cloud-login"]')
    pg.wait_for_timeout(600)
    pg.fill('input[name="email"]', EMAIL)
    pg.fill('input[name="password"]', PWD)
    pg.click('form.modal-card button[type="submit"]')
    pg.wait_for_timeout(3500)

    def fetch_rev(rev_id):
        return pg.evaluate("""async (id) => {
            const r = await fetch('/api.php?action=history&id=' + id, {credentials:'include'});
            return await r.json();
        }""", rev_id)

    def summarize(item):
        d = item.get("item", {}).get("data", {})
        return {
            "id": item.get("item", {}).get("id"),
            "rev": item.get("item", {}).get("rev"),
            "reason": item.get("item", {}).get("reason"),
            "habits": [h.get("name") for h in d.get("habits", [])],
            "tasks": [t.get("title") for t in d.get("tasks", [])],
            "checks_days": list(d.get("checks", {}).keys()),
            "moods": d.get("moods", {}),
            "events_n": len(d.get("events", [])),
        }

    for rev_id in [265, 264, 266, 267]:
        try:
            item = fetch_rev(rev_id)
            s = summarize(item)
            print(f"\n=== id={rev_id} (rev {s['rev']}, reason={s['reason']}) ===")
            print("  习惯:", s["habits"])
            print("  待办:", s["tasks"])
            print("  checks 天数:", s["checks_days"])
            print("  moods:", s["moods"])
            print("  events 数量:", s["events_n"])
        except Exception as e:
            print(f"id={rev_id} 预览失败:", e)

    b.close()
