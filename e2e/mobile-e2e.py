# -*- coding: utf-8 -*-
"""晚风Todo 移动端（iPhone 13 视口）端到端实测。

重点：横向溢出、触控目标(≥44px)、底部 tabbar、移动端表单、明暗切换。
真实写入 1 待办 + 1 习惯（#M 前缀，保留）。
"""
import json, datetime
from playwright.sync_api import sync_playwright

URL = "https://your-domain.example"
EMAIL = "test@example.com"
PWD = "test@example.com"
STAMP = datetime.datetime.now().strftime("%H%M%S")

report = {"steps": [], "errors": {"pageerror": [], "console_error": [], "failed": [], "http4xx5xx": []}, "touch_targets": []}


def check(cond, name, detail=""):
    report["steps"].append({"name": name, "status": "pass" if cond else "fail", "detail": detail})
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  — {detail}" if detail else ""))


def no_h_overflow(pg):
    return pg.evaluate("() => document.documentElement.scrollWidth <= innerWidth + 1")


with sync_playwright() as p:
    device = p.devices["iPhone 13"]
    b = p.chromium.launch(channel="chrome", headless=True)
    ctx = b.new_context(**device)
    pg = ctx.new_page()

    pg.on("pageerror", lambda e: report["errors"]["pageerror"].append(str(e)))
    pg.on("console", lambda m: report["errors"]["console_error"].append(m.text) if m.type == "error" else None)
    pg.on("requestfailed", lambda r: report["errors"]["failed"].append(f"{r.method} {r.url} -> {r.failure}"))
    pg.on("response", lambda r: report["errors"]["http4xx5xx"].append(f"{r.status} {r.request.method} {r.url}") if r.status >= 400 else None)

    def shot(name):
        pg.screenshot(path=f"e2e/shots/{name}.png", full_page=True)

    def touch_audit(selectors):
        for sel in selectors:
            boxes = pg.eval_on_selector_all(sel, """
                els => els.map(e => {const r = e.getBoundingClientRect();
                    return {w: Math.round(r.width), h: Math.round(r.height), text: (e.innerText||'').trim().slice(0,10)}})
            """)
            for bx in boxes:
                if bx["w"] > 0 and bx["h"] > 0:
                    report["touch_targets"].append({"selector": sel, **bx})

    try:
        # 1. 落地页
        pg.goto(URL, wait_until="networkidle")
        pg.wait_for_timeout(1200)
        check(no_h_overflow(pg), "落地页无横向溢出")
        check(pg.locator('[data-act="cloud-login"]').count() > 0, "落地页登录入口可见")
        shot("m-01-landing")

        # 2. 登录
        pg.click('[data-act="cloud-login"]')
        pg.wait_for_timeout(600)
        pg.fill('input[name="email"]', EMAIL)
        pg.fill('input[name="password"]', PWD)
        pg.click('form.modal-card button[type="submit"]')
        pg.wait_for_timeout(3500)
        check(pg.locator('.mobile-tab:has-text("今日").active').count() > 0, "移动端登录成功，底部 tabbar 出现")
        check(no_h_overflow(pg), "登录后无横向溢出")
        shot("m-02-after-login")

        # 3. 底部 tabbar 遍历（今日/待办/习惯/统计）
        for tab in ["今日", "待办", "习惯", "统计"]:
            pg.click(f'.mobile-tab:has-text("{tab}")')
            pg.wait_for_timeout(1200)
            active = pg.locator(f'.mobile-tab.active:has-text("{tab}")').count() > 0
            ovf = no_h_overflow(pg)
            check(active and ovf, f"底部 tab『{tab}』切换正常且无溢出", f"active={active}, overflow={not ovf}")
            shot(f"m-03-{tab}")

        # 4. 更多页 + 收纳的 4 个入口
        pg.click('.mobile-tab:has-text("更多")')
        pg.wait_for_timeout(1200)
        more_items = ["体重", "随笔", "日历", "设置"]
        found_all = all(pg.locator(f"text={k}").count() > 0 for k in more_items)
        check(found_all and no_h_overflow(pg), "『更多』页收纳体重/随笔/日历/设置且无溢出")
        shot("m-04-more")

        # 5. 移动端新建待办
        pg.click('.mobile-tab:has-text("待办")')
        pg.wait_for_timeout(1200)
        pg.click('button[data-act="task-new"]')
        pg.wait_for_timeout(800)
        title = f"【测试M】移动端任务 #{STAMP}"
        pg.fill('input[name="title"]', title)
        pg.select_option('select[name="tag"]', "工作")
        pg.click('.modal-card button[type="submit"]')
        pg.wait_for_timeout(2000)
        check(pg.locator(f"text={title}").count() > 0, "移动端新建待办", "已出现在看板")
        shot("m-05-task")

        # 6. 移动端新建习惯
        pg.click('.mobile-tab:has-text("习惯")')
        pg.wait_for_timeout(1200)
        pg.click('[data-act="habit-new"]')
        pg.wait_for_timeout(800)
        hname = f"冥想 #{STAMP}"
        pg.fill('input[name="icon"]', "🧘")
        pg.fill('input[name="name"]', hname)
        pg.select_option('select[name="type"]', "build")
        pg.fill('input[name="target"]', "10")
        pg.fill('input[name="unit"]', "分钟")
        pg.click('.modal-card button[type="submit"]')
        pg.wait_for_timeout(2000)
        check(pg.locator(f"text={hname}").count() > 0, "移动端新建习惯", "已出现在习惯页")
        shot("m-06-habit")

        # 7. 今日页打卡 + 明暗切换（通过「更多」）
        pg.click('.mobile-tab:has-text("今日")')
        pg.wait_for_timeout(1200)
        water = pg.locator(".vital-card:has-text('喝水')")
        before = water.inner_text() if water.count() else ""
        pg.click('button[data-act="habit-inc"]:has-text("喝一杯")')
        pg.wait_for_timeout(2000)
        after = water.inner_text() if water.count() else ""
        check(before != after, "移动端打卡：喝水 +1", f"{before.strip()[:16]} → {after.strip()[:16]}")

        # 明暗切换（更多 → 切换深色/浅色）
        pg.click('.mobile-tab:has-text("更多")')
        pg.wait_for_timeout(1000)
        t0 = pg.evaluate("() => document.documentElement.getAttribute('data-theme')")
        pg.click('text=切换深色 / 浅色')
        pg.wait_for_timeout(1000)
        t1 = pg.evaluate("() => document.documentElement.getAttribute('data-theme')")
        check(t0 != t1, "移动端明暗主题切换", f"{t0} → {t1}")
        shot("m-07-dark")
        pg.click('text=切换深色 / 浅色')
        pg.wait_for_timeout(800)

        # 8. 触控目标审计（关键可点击元素尺寸）
        pg.click('.mobile-tab:has-text("今日")')
        pg.wait_for_timeout(1200)
        touch_audit([".mobile-tab", ".vital-btn", ".mini-btn", ".icon-btn", ".mood"])
        small = [t for t in report["touch_targets"] if t["h"] < 44 or t["w"] < 44]
        check(True, "触控目标审计完成", f"共测 {len(report['touch_targets'])} 个，其中 <44px 的有 {len(small)} 个（详见报告）")

    except Exception as e:
        check(False, "脚本异常", str(e))
        try:
            shot("m-99-error")
        except Exception:
            pass
    finally:
        b.close()

report["finished_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
report["passed"] = sum(1 for s in report["steps"] if s["status"] == "pass")
report["failed"] = sum(1 for s in report["steps"] if s["status"] == "fail")
report["total"] = len(report["steps"])
report["touch_small"] = [t for t in report["touch_targets"] if t["h"] < 44 or t["w"] < 44]

with open("e2e/mobile-report.json", "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

print("\n================ 移动端测试汇总 ================")
print(f"通过 {report['passed']} / 失败 {report['failed']} / 总计 {report['total']}")
print(f"JS 异常 {len(report['errors']['pageerror'])}，console.error {len(report['errors']['console_error'])}，请求失败 {len(report['errors']['failed'])}，4xx/5xx {len(report['errors']['http4xx5xx'])}")
print(f"\n--- 触控目标 <44px（移动端体验短板）---")
for t in report["touch_small"]:
    print(f"  {t['selector']} 『{t['text']}』 {t['w']}×{t['h']}px")
if not report["touch_small"]:
    print("  （无）")
