# -*- coding: utf-8 -*-
"""补测：戒除型习惯创建（quit 类型下 target 字段被禁用，需跳过）。"""
import json, datetime
from playwright.sync_api import sync_playwright

URL = "https://todo.csl88.top"
EMAIL = "test@sl00.top"
PWD = "test@sl00.top"
STAMP = datetime.datetime.now().strftime("%H%M%S")

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

        pg.click('.nav-item:has-text("习惯")')
        pg.wait_for_timeout(1200)
        pg.click('[data-act="habit-new"]')
        pg.wait_for_timeout(800)

        # 选择戒除型，验证 target 是否被禁用（产品语义：保持 0 次）
        pg.select_option('select[name="type"]', "quit")
        pg.wait_for_timeout(500)
        target_disabled = pg.locator('input[name="target"]').is_disabled()
        target_val = pg.locator('input[name="target"]').input_value()
        check(target_disabled, "戒除型习惯 target 字段被自动禁用", f"disabled={target_disabled}, value={target_val}")

        name = f"不熬夜 #{STAMP}"
        pg.fill('input[name="icon"]', "🚫")
        pg.fill('input[name="name"]', name)
        pg.fill('input[name="note"]', "端到端测试：戒除型")
        pg.click('.modal-card button[type="submit"]')
        pg.wait_for_timeout(2000)

        appeared = pg.locator(f"text={name}").count() > 0
        check(appeared, f"新建戒除型习惯『{name}』", "已出现在习惯页" if appeared else "未找到")

        # 验证戒除型习惯的显示语义（保持 0 次）
        pg.screenshot(path="e2e/shots/08-quit-habit.png", full_page=True)

    except Exception as e:
        check(False, "补测脚本异常", str(e))
    finally:
        b.close()

print("\n===== 补测结果 =====")
print(json.dumps(report, ensure_ascii=False, indent=2))
