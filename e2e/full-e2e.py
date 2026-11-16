# -*- coding: utf-8 -*-
"""晚风Todo 线上端到端实测（真实写入测试数据，不删除）。

覆盖：
1. 登录（断言进入今日页）
2. 8 个页面遍历（断言导航激活 + 关键文本 + 截图）
3. 新建 3 个待办任务（单次/每日重复，真实写入）
4. 新建 2 个习惯（养成型 + 戒除型，真实写入）
5. 今日页打卡（喝水 +1）+ 心情记录
6. 明暗主题切换
全程挂 pageerror / console.error / requestfailed / 4xx-5xx 四类钩子，输出 JSON 报告。
"""
import json, time, datetime
from playwright.sync_api import sync_playwright

URL = "https://your-domain.example"
EMAIL = "test@example.com"
PWD = "test@example.com"

report = {
    "url": URL,
    "account": EMAIL,
    "started_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "steps": [],
    "errors": {"pageerror": [], "console_error": [], "failed": [], "http4xx5xx": []},
    "api_requests": [],
    "screenshots": [],
}

STAMP = datetime.datetime.now().strftime("%H%M")


def add_step(name, status, detail=""):
    report["steps"].append({"name": name, "status": status, "detail": detail})
    icon = "PASS" if status == "pass" else ("FAIL" if status == "fail" else "SKIP")
    print(f"[{icon}] {name}" + (f"  — {detail}" if detail else ""))


def check(cond, name, detail=""):
    add_step(name, "pass" if cond else "fail", detail)
    return cond


with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome", headless=True)
    pg = b.new_page(viewport={"width": 1366, "height": 900})

    # ---- 四类错误钩子 ----
    pg.on("pageerror", lambda e: report["errors"]["pageerror"].append(str(e)))
    pg.on("console", lambda m: report["errors"]["console_error"].append(m.text) if m.type == "error" else None)
    pg.on("requestfailed", lambda r: report["errors"]["failed"].append(f"{r.method} {r.url} -> {r.failure}"))
    pg.on("response", lambda r: (
        report["api_requests"].append(f"{r.status} {r.request.method} {r.url}") if "api.php" in r.url else None,
        report["errors"]["http4xx5xx"].append(f"{r.status} {r.request.method} {r.url}") if r.status >= 400 else None,
    ))

    def shot(name):
        pg.screenshot(path=f"e2e/shots/{name}.png", full_page=True)
        report["screenshots"].append(f"e2e/shots/{name}.png")

    try:
        # ============ 1. 打开 & 未登录落地页 ============
        pg.goto(URL, wait_until="networkidle")
        pg.wait_for_timeout(1200)
        check(pg.title() == "晚风Todo · 习惯与任务", "打开首页", pg.title())
        check(pg.locator('[data-act="cloud-login"]').count() > 0, "未登录落地页展示登录入口")
        shot("01-landing")

        # ============ 2. 登录 ============
        pg.click('[data-act="cloud-login"]')
        pg.wait_for_timeout(600)
        pg.fill('input[name="email"]', EMAIL)
        pg.fill('input[name="password"]', PWD)
        pg.click('form.modal-card button[type="submit"]')
        pg.wait_for_timeout(3500)
        pg.wait_for_selector(".hero", timeout=8000)
        logged_in = pg.locator('.nav-item:has-text("今日")').count() > 0 and \
                    pg.locator('[data-act="cloud-login"]').count() == 0
        check(logged_in, "登录成功并进入今日页")
        sync_ok = pg.locator("#sync-indicator.saved").count() > 0
        check(sync_ok, "登录后云同步完成（sync-indicator=saved）", pg.locator("#sync-indicator").inner_text())
        shot("02-after-login")

        # ============ 3. 八个页面遍历 ============
        pages = [
            ("今日", "完成度", "今日任务"),
            ("待办", "新建任务", "待办"),
            ("习惯", "添加习惯", "习惯"),
            ("体重", "BMI", "体重"),
            ("随笔", "随笔", "随笔"),
            ("日历", "月", "日历"),
            ("统计", "完成率", "统计"),
            ("设置", "主题", "设置"),
        ]
        for name, keyword, nav in pages:
            pg.click(f'.nav-item:has-text("{name}")')
            pg.wait_for_timeout(1200)
            active = pg.locator(f'.nav-item.active:has-text("{name}")').count() > 0
            has_kw = pg.locator(f"text={keyword}").count() > 0
            check(active and has_kw, f"页面『{name}』正常渲染", f"active={active}, keyword『{keyword}』={has_kw}")
            shot(f"03-view-{name}")

        # ============ 4. 新建待办任务（真实写入，保留） ============
        tasks = [
            {"title": f"【测试】阅读 30 分钟 #{STAMP}", "tag": "学习", "priority": "中", "due": "2026-10-24", "note": "端到端测试：单次任务"},
            {"title": f"【测试】做 20 个俯卧撑 #{STAMP}", "tag": "健康", "priority": "高", "due": "2026-10-24", "note": "端到端测试：高优先级"},
            {"title": f"【测试】晚上整理书桌 #{STAMP}", "tag": "生活", "priority": "低", "due": "2026-10-24", "repeat": "daily", "repeatTime": "21:30", "note": "端到端测试：每日重复"},
        ]
        pg.click('.nav-item:has-text("待办")')
        pg.wait_for_timeout(1200)
        for t in tasks:
            pg.click('button[data-act="task-new"]:has-text("新建任务")')
            pg.wait_for_timeout(800)
            pg.fill('input[name="title"]', t["title"])
            if "note" in t:
                pg.fill('textarea[name="note"]', t["note"])
            pg.select_option('select[name="tag"]', t["tag"])
            pg.select_option('select[name="priority"]', t["priority"])
            if "repeat" in t:
                pg.select_option('select[name="repeat"]', t["repeat"])
                pg.wait_for_timeout(400)
                if "repeatTime" in t:
                    pg.fill('input[name="repeatTime"]', t["repeatTime"])
            pg.click('.modal-card button[type="submit"]')
            pg.wait_for_timeout(2000)
            # 断言：任务标题出现在看板
            appeared = pg.locator(f"text={t['title']}").count() > 0
            check(appeared, f"新建待办『{t['title']}』", "已出现在看板" if appeared else "未找到任务")
        shot("04-tasks-created")

        # ============ 5. 新建习惯（真实写入，保留） ============
        habits = [
            {"icon": "📖", "name": f"阅读 #{STAMP}", "type": "build", "target": "1", "unit": "次", "note": "端到端测试：养成型"},
            {"icon": "🚫", "name": f"不熬夜 #{STAMP}", "type": "quit", "target": "0", "unit": "次", "note": "端到端测试：戒除型"},
        ]
        pg.click('.nav-item:has-text("习惯")')
        pg.wait_for_timeout(1200)
        for h in habits:
            pg.click('[data-act="habit-new"]')
            pg.wait_for_timeout(800)
            pg.fill('input[name="icon"]', h["icon"])
            pg.fill('input[name="name"]', h["name"])
            pg.select_option('select[name="type"]', h["type"])
            # 戒除型(quit)的 target/unit 会被禁用，仅养成型(build)才填
            if h["type"] == "build":
                pg.fill('input[name="target"]', h["target"])
                pg.fill('input[name="unit"]', h["unit"])
            if "note" in h:
                pg.fill('input[name="note"]', h["note"])
            pg.click('.modal-card button[type="submit"]')
            pg.wait_for_timeout(2000)
            appeared = pg.locator(f"text={h['name']}").count() > 0
            check(appeared, f"新建习惯『{h['name']}』({h['type']})", "已出现在习惯页" if appeared else "未找到习惯")
        shot("05-habits-created")

        # ============ 6. 今日页打卡 + 心情 ============
        pg.click('.nav-item:has-text("今日")')
        pg.wait_for_timeout(1200)
        before = pg.locator(".vital-card:has-text('喝水')").inner_text() if pg.locator(".vital-card:has-text('喝水')").count() else ""
        pg.click('button[data-act="habit-inc"]:has-text("喝一杯")')
        pg.wait_for_timeout(2000)
        after = pg.locator(".vital-card:has-text('喝水')").inner_text() if pg.locator(".vital-card:has-text('喝水')").count() else ""
        check(before != after, "今日页打卡：喝水 +1", f"before『{before[:30]}』→ after『{after[:30]}』")

        pg.click('button[data-act="set-mood"]:has-text("开心")')
        pg.wait_for_timeout(1200)
        mood_on = pg.locator("button.mood.happy.on, button.mood.happy.active, button.mood.happy.is-sel").count() > 0 or \
                  pg.locator("button.mood.happy[class*=on]").count() > 0
        check(mood_on, "今日页记录心情（开心）", "已选中" if mood_on else "未确认选中态")
        shot("06-today-after-checkin")

        # ============ 7. 明暗主题切换 ============
        theme_before = pg.evaluate("() => document.documentElement.getAttribute('data-theme')")
        pg.click("#theme-btn")
        pg.wait_for_timeout(1000)
        theme_after = pg.evaluate("() => document.documentElement.getAttribute('data-theme')")
        check(theme_before != theme_after, "明暗主题切换", f"{theme_before} → {theme_after}")
        shot("07-dark-mode")
        pg.click("#theme-btn")
        pg.wait_for_timeout(800)

        # ============ 8. 云同步最终状态 ============
        pg.wait_for_timeout(1500)
        final_sync = pg.locator("#sync-indicator").inner_text()
        check("已保存" in final_sync or "saved" in (pg.locator("#sync-indicator").get_attribute("class") or ""),
              "全部写操作已同步到云端", final_sync)

    except Exception as e:
        add_step("脚本执行异常", "fail", str(e))
        try:
            shot("99-error")
        except Exception:
            pass
    finally:
        b.close()

report["finished_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
report["passed"] = sum(1 for s in report["steps"] if s["status"] == "pass")
report["failed"] = sum(1 for s in report["steps"] if s["status"] == "fail")
report["total"] = len(report["steps"])

with open("e2e/report.json", "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

print("\n================ 测试汇总 ================")
print(f"通过 {report['passed']} / 失败 {report['failed']} / 总计 {report['total']}")
print(f"JS 异常 {len(report['errors']['pageerror'])} 条")
print(f"console.error {len(report['errors']['console_error'])} 条")
print(f"请求失败 {len(report['errors']['failed'])} 条")
print(f"HTTP 4xx/5xx {len(report['errors']['http4xx5xx'])} 条")
if report["errors"]["pageerror"]:
    print("\n--- pageerror ---")
    for e in report["errors"]["pageerror"]:
        print(e)
if report["errors"]["console_error"]:
    print("\n--- console.error ---")
    for e in report["errors"]["console_error"][:20]:
        print(e)
if report["errors"]["failed"]:
    print("\n--- requestfailed ---")
    for e in report["errors"]["failed"]:
        print(e)
if report["errors"]["http4xx5xx"]:
    print("\n--- 4xx/5xx ---")
    for e in report["errors"]["http4xx5xx"]:
        print(e)
