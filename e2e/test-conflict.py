# -*- coding: utf-8 -*-
"""端到端验证冲突合并：本地静态服务器 + mock api（cookie session 隔离），
两个并发会话实测「旧数据不再覆盖新数据」。"""
import http.server, threading, json, socketserver, secrets
from playwright.sync_api import sync_playwright

DOCROOT = "C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo"

board = {
    "data": {
        "version": 2, "view": "today",
        "habits": [{"id": "h_water", "name": "喝水", "icon": "💧", "type": "build", "target": 8, "unit": "杯",
                    "color": "#4c7f96", "note": "", "createdAt": "2026-10-23T00:00:00Z", "pinned": True, "archivedAt": ""}],
        "checks": {}, "notes": {}, "moods": {}, "events": [], "meds": [], "doses": {},
        "bodyProfile": {"age": 30, "height": 170}, "weights": [], "essays": [], "tasks": [],
    },
    "rev": 5,
}
USER = {"id": 1, "email": "t@t.top", "display_name": "T", "is_admin": False}
CSRF = "mock-csrf"
sessions = {}  # sid -> user


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=DOCROOT, **kw)

    def log_message(self, *a):
        pass

    def _json(self, obj, status=200, extra_headers=None):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra_headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _sid(self):
        cookie = self.headers.get("Cookie", "")
        for part in cookie.split(";"):
            part = part.strip()
            if part.startswith("sid="):
                return part[4:]
        return None

    def _user(self):
        return sessions.get(self._sid())

    def do_GET(self):
        if self.path.startswith("/api.php"):
            action = self.path.split("action=")[-1].split("&")[0]
            if action == "status":
                self._json({"ok": True, "installed": True, "registration_open": False})
            elif action == "me":
                u = self._user()
                self._json({"ok": True, "user": u, "csrf": CSRF, "registration_open": False, "site_name": "明序"})
            elif action == "load":
                if not self._user():
                    self._json({"ok": False, "error": "未登录"}, 401)
                    return
                self._json({"ok": True, "data": board["data"], "rev": board["rev"], "updated_at": 0})
            else:
                self._json({"ok": False, "error": "unknown " + action}, 404)
        else:
            super().do_GET()

    def do_POST(self):
        if self.path.startswith("/api.php"):
            action = self.path.split("action=")[-1].split("&")[0]
            length = int(self.headers.get("Content-Length", 0))
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
            except Exception:
                body = {}
            if action == "login":
                sid = secrets.token_hex(8)
                sessions[sid] = USER
                self._json({"ok": True, "user": USER, "csrf": CSRF, "registration_open": False},
                           extra_headers={"Set-Cookie": "sid=" + sid + "; Path=/"})
            elif action == "save":
                if not self._user():
                    self._json({"ok": False, "error": "未登录"}, 401)
                    return
                base = int(body.get("base_rev", 0))
                if base != board["rev"]:
                    self._json({"ok": False, "error": "云端有更新", "code": "conflict",
                                "remote": {"data": board["data"], "rev": board["rev"], "updated_at": 0}}, 409)
                else:
                    board["data"] = body["data"]
                    board["rev"] += 1
                    self._json({"ok": True, "rev": board["rev"], "updated_at": 0})
            elif action == "force":
                if not self._user():
                    self._json({"ok": False, "error": "未登录"}, 401)
                    return
                board["data"] = body["data"]
                board["rev"] += 1
                self._json({"ok": True, "rev": board["rev"], "updated_at": 0})
            elif action == "logout":
                self._json({"ok": True})
            else:
                self._json({"ok": False, "error": "unknown " + action}, 404)
        else:
            self.send_response(405)
            self.end_headers()


class TS(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


srv = TS(("127.0.0.1", 0), Handler)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{port}/index.html"
print("mock server on port", port)


def login(pg, email):
    pg.goto(BASE, wait_until="networkidle")
    pg.wait_for_timeout(800)
    assert pg.locator('[data-act="cloud-login"]').count() > 0, "登录按钮未出现"
    pg.click('[data-act="cloud-login"]')
    pg.wait_for_timeout(500)
    pg.fill('input[name="email"]', email)
    pg.fill('input[name="password"]', "12345678")
    pg.click('form.modal-card button[type="submit"]')
    pg.wait_for_timeout(2500)


def add_task(pg, title):
    pg.click('.nav-item:has-text("待办")')
    pg.wait_for_timeout(800)
    pg.click('button[data-act="task-new"]:has-text("新建任务")')
    pg.wait_for_timeout(500)
    pg.fill('input[name="title"]', title)
    pg.click('.modal-card button[type="submit"]')
    pg.wait_for_timeout(2500)


with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome", headless=True)
    ctxA = b.new_context()
    ctxB = b.new_context()
    pgA = ctxA.new_page()
    pgB = ctxB.new_page()

    login(pgA, "a@a.top")
    print("会话 A 登录完成，云端 rev =", board["rev"])

    login(pgB, "b@b.top")
    print("会话 B 登录完成，云端 rev =", board["rev"])

    # 会话 A 新建待办 → save(base_rev=5) 成功 rev=6
    add_task(pgA, "A的任务-来自会话A")
    print("A 新建待办后 rev =", board["rev"], "| tasks =", [t["title"] for t in board["data"]["tasks"]])
    assert board["rev"] == 6, "A 保存后 rev 应为 6"

    # 会话 B（持有旧 rev=5）新建待办 → 409 后应合并重存
    add_task(pgB, "B的任务-来自会话B")
    print("B 新建待办后 rev =", board["rev"], "| tasks =", [t["title"] for t in board["data"]["tasks"]])

    titles = [t["title"] for t in board["data"]["tasks"]]
    hasA = any("A的任务" in t for t in titles)
    hasB = any("B的任务" in t for t in titles)

    print("\n================ 结果 ================")
    print("最终云端 rev =", board["rev"], "（期望 7）")
    print("云端含「A的任务」:", hasA, "（期望 True）")
    print("云端含「B的任务」:", hasB, "（期望 True）")

    ok = hasA and hasB and board["rev"] == 7
    print("结论:", "PASS 冲突合并生效，旧数据不再覆盖新数据" if ok else "FAIL 仍存在问题")

    b.close()
    srv.shutdown()
    raise SystemExit(0 if ok else 1)
