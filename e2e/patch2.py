# -*- coding: utf-8 -*-
"""补测 2：今日页打卡、心情记录、明暗切换、最终云同步（full-e2e 中断后遗漏的步骤）。"""
import json, datetime
from playwright.sync_api import sync_playwright

URL = "https://todo.csl88.top"
EMAIL = "test@sl00.top"
PWD = "test@sl00.top"

report = {"steps": [], "errors": {"pageerror": [], "console_error": [], "failed": [], "http4xx5xx": []}}


def check(cond, name, detail=""):
    report["steps"].append({"name": name, "status": "pass" if cond else "fail", "detail": detail})
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  — {detail}" if detail else ""))


with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome", headless=True)
    pg = b.new_page(viewport={"width": 1366, "height": 900})
    pg.on("pageerror", lambda e: report["errors"]["pageerror"].append(str(e)))
    pg.on("console", lambda m: report["errors"]["console_error"].append(m.text) if m.type == "error" else None)
    pg.on("requestfailed", lambda r: report["errors"]["failed"].append(f"{r.method} {r.url} -> {r.failure}"))
    pg.on("response", lambda r: report["errors"]["http4xx5xx"].append(f"{r.status} {r.request.method} {r.url}") if r.status >= 400 else None)

    try:
        pg.goto(URL, wait_until="networkidle")
        pg.wait_for_timeout(1000)
        pg.click('[data-act="cloud-login"]')
        pg.wait_for_timeout(600)
        pg.fill('input[name="email"]', EMAIL)
        pg.fill('input[name="password"]', PWD)
        pg.click('form.modal-card button[type="submit"]')
        pg.wait_for_timeout(3200)

        # 1. 今日页打卡：喝水 +1
        pg.click('.nav-item:has-text("今日")')
        pg.wait_for_timeout(1200)
        water = pg.locator(".vital-card:has-text('喝水')")
        before = water.inner_text() if water.count() else ""
        pg.click('button[data-act="habit-inc"]:has-text("喝一杯")')
        pg.wait_for_timeout(2000)
        after = water.inner_text() if water.count() else ""
        check(before != after, "今日页打卡：喝水 +1", f"before『{before.strip()[:24]}』→ after『{after.strip()[:24]}』")

        # 2. 心情记录（开心）
        pg.click('button[data-act="set-mood"]:has-text("开心")')
        pg.wait_for_timeout(1200)
        mood_cls = pg.locator('button[data-act="set-mood"]:has-text("开心")').get_attribute("class") or ""
        check("on" in mood_cls or "active" in mood_cls or "is-sel" in mood_cls,
              "今日页记录心情（开心）", f"class={mood_cls}")
        pg.screenshot(path="e2e/shots/06-today-after-checkin.png", full_page=True)

        # 3. 明暗主题切换
        t0 = pg.evaluate("() => document.documentElement.getAttribute('data-theme')")
        pg.click("#theme-btn")
        pg.wait_for_timeout(1000)
        t1 = pg.evaluate("() => document.documentElement.getAttribute('data-theme')")
        check(t0 != t1, "明暗主题切换", f"{t0} → {t1}")
        pg.screenshot(path="e2e/shots/07-dark-mode.png", full_page=True)
        pg.click("#theme-btn")
        pg.wait_for_timeout(800)

        # 4. 最终云同步状态
        pg.wait_for_timeout(1500)
        sync_text = pg.locator("#sync-indicator").inner_text()
        sync_cls = pg.locator("#sync-indicator").get_attribute("class") or ""
        check("已保存" in sync_text or "saved" in sync_cls, "全部写操作已同步到云端", sync_text)

    except Exception as e:
        check(False, "补测脚本异常", str(e))
    finally:
        b.close()

print("\n===== 补测结果 =====")
print(json.dumps(report, ensure_ascii=False, indent=2))
