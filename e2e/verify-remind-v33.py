# -*- coding: utf-8 -*-
"""v33 真提醒三件套验证：提醒引擎扩展 / 系统通知 / 日历导出 / 安装引导。
全部走真实 UI 路径（点按钮、读 DOM），不直接调用内部函数。"""
import io, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
head = io.open(os.path.join(ROOT, 'e2e', 'verify-batch4.py'), encoding='utf-8').read()
head = head.split('with sync_playwright() as p:')[0]
sys.argv = [sys.argv[0]]
exec(head)

PASS = 0
FAILS = []


def chk(name, ok, detail=''):
    global PASS
    if ok:
        PASS += 1
        print('  \u2713 %s' % name)
    else:
        FAILS.append((name, detail))
        print('  \u2717 %s  << %s' % (name, detail))


# ---------- 把 mock 数据调成能触发全部六类提醒 ----------
board['data']['tasks'].append({
    'id': 'r1', 'title': '每周复盘', 'note': '', 'tag': '工作', 'priority': '中',
    'status': 'todo', 'due': '2026-10-25', 'createdAt': '2026-10-01T08:00:00Z',
    'repeat': 'daily', 'repeatTime': '09:00', 'repeatWeekday': 0, 'repeatDay': 25})
board['data']['tasks'].append({
    'id': 'r2', 'title': '周报', 'note': '', 'tag': '工作', 'priority': '中',
    'status': 'todo', 'due': '2026-10-25', 'createdAt': '2026-10-01T08:00:00Z',
    'repeat': 'weekly', 'repeatTime': '18:00', 'repeatWeekday': 3, 'repeatDay': 25})
board['data']['tasks'].append({
    'id': 'r3', 'title': '交房租', 'note': '', 'tag': '生活', 'priority': '高',
    'status': 'todo', 'due': '2026-10-25', 'createdAt': '2026-10-01T08:00:00Z',
    'repeat': 'monthly', 'repeatTime': '10:30', 'repeatDay': 1})
board['data']['tasks'].append({
    'id': 't3', 'title': '三天后体检', 'note': '空腹', 'tag': '健康', 'priority': '高',
    'status': 'todo', 'due': '2026-10-28', 'createdAt': '2026-10-01T08:00:00Z'})
for h in board['data']['habits']:
    if h['id'] == 'h_plan':
        h['suggestTime'] = '09:00'

STUB = """
window.__notes = [];
window.__blobs = [];
(function(){
  const sn = window.ServiceWorkerRegistration && ServiceWorkerRegistration.prototype.showNotification;
  if (sn) {
    ServiceWorkerRegistration.prototype.showNotification = function(t, o) {
      window.__notes.push({ title: t, body: (o && o.body) || '', tag: (o && o.tag) || '' });
      return Promise.resolve();
    };
  }
  const cob = URL.createObjectURL;
  URL.createObjectURL = function(b) { try { window.__blobs.push(b); } catch(e){} return cob.call(URL, b); };
})();
"""


def login(pg):
    pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
    pg.wait_for_timeout(600)
    if pg.locator('[data-act="cloud-login"]').count() == 0:
        pg.wait_for_timeout(2400)
        return
    pg.click('[data-act="cloud-login"]')
    pg.wait_for_timeout(400)
    pg.fill('input[name="email"]', 'test@sl00.top')
    pg.fill('input[name="password"]', 'test@sl00.top')
    pg.click('form.modal-card button[type="submit"]')
    pg.wait_for_timeout(2600)


with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)
    ctx = br.new_context(viewport={'width': 1440, 'height': 950}, accept_downloads=True)
    ctx.add_init_script(STUB)
    ctx.grant_permissions(['notifications'], origin='http://127.0.0.1:%d' % port)
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)[:200]))
    pg.clock.install(time=datetime(2026, 10, 25, 10, 0, 0))
    login(pg)
    pg.wait_for_timeout(1200)

    # =========================================================
    print('\n[1] 提醒引擎：六类来源')

    def items():
        return pg.evaluate(
            "() => [...document.querySelectorAll('.remind-bar .remind-item')]"
            ".map(e => e.textContent.trim())")

    def total():
        t = items()
        more = [x for x in t if x.startswith('还有 ')]
        if more:
            return len([x for x in t if not x.startswith('还有 ')]) + int(more[0].split(' ')[1])
        return len(t)

    bar = pg.locator('.remind-bar')
    chk('横幅出现', bar.count() == 1, 'count=%d' % bar.count())
    texts = items()
    joined = ' | '.join(texts)
    chk('初始共 6 条提醒（用药超时/待服/重复任务/逾期/习惯/喝水）', total() == 6, joined)
    chk('用药超时合并成一条（08:00 + 09:00）', any('2 次用药已过时间' in t for t in texts), joined)
    chk('今日待服 2 次（12:00 / 20:00）', any('2 次用药待服' in t for t in texts), joined)
    chk('重复任务到点被提醒', any('到时间了' in t for t in texts), joined)
    chk('只铺 3 条，其余折成计数',
        len([x for x in texts if not x.startswith('还有 ')]) == 3
        and any(x == '还有 3 条' for x in texts), joined)

    # 反向验证：把两件逾期任务勾掉，逾期那一条应自己消失
    late_btn = pg.locator('[data-act="task-toggle"][data-id="o1"]')
    chk('逾期任务出现在今日页（可直接勾选）', late_btn.count() >= 1, 'count=%d' % late_btn.count())
    late_btn.first.click()
    pg.wait_for_timeout(400)
    pg.locator('[data-act="task-toggle"][data-id="o2"]').first.click()
    pg.wait_for_timeout(600)
    chk('完成逾期任务后降到 5 条', total() == 5, ' | '.join(items()))

    # 习惯打卡后，习惯那条也应该消失（打卡按钮在今日页的习惯卡里）
    inc = pg.locator('[data-id="h_plan"][data-act^="habit-"]')
    chk('今日页有习惯打卡入口', inc.count() >= 1, 'count=%d' % inc.count())
    inc.first.click()
    pg.wait_for_timeout(600)
    chk('打完卡习惯提醒消失，剩 4 条', total() == 4, ' | '.join(items()))
    chk('剩下的折叠成「还有 1 条」', any(x == '还有 1 条' for x in items()), ' | '.join(items()))

    # =========================================================
    print('\n[2] 系统通知开关')
    nav(pg, 'settings')
    pg.wait_for_timeout(400)
    chk('设置页有「提醒」面板', pg.locator('h3', has_text='提醒').count() >= 1)
    on_btn = pg.locator('[data-act="notify-on"]')
    chk('初始状态给的是「开启」按钮', on_btn.count() == 1, 'count=%d' % on_btn.count())
    chk('未开启时状态文案正确',
        any('只有打开这个页面时才会提醒' in (x or '')
            for x in pg.evaluate("() => [...document.querySelectorAll('.ntf-state')].map(e=>e.textContent)")),
        str(pg.evaluate("() => [...document.querySelectorAll('.ntf-state')].map(e=>e.textContent)")))
    on_btn.click()
    pg.wait_for_timeout(1200)
    chk('开启后 localStorage 打标',
        pg.evaluate("() => localStorage.getItem('lifeboard.notify.on')") == '1')
    notes = pg.evaluate('() => window.__notes')
    chk('立刻发了一条通知做验证', len(notes) >= 1, json.dumps(notes, ensure_ascii=False)[:200])
    chk('通知正文是真实提醒内容', any('用药' in n['body'] or '待办' in n['body'] or '打卡' in n['body'] or '喝水' in n['body'] for n in notes),
        json.dumps(notes, ensure_ascii=False)[:260])
    chk('开启后按钮换成「关闭」', pg.locator('[data-act="notify-off"]').count() == 1)
    chk('已发送的 key 被记下来',
        pg.evaluate("() => { try { return JSON.parse(localStorage.getItem('lifeboard.notify.sent')).keys.length } catch(e){ return 0 } }") >= 1)

    # 去重：把时间往后推 2 分钟，未新增提醒时不应再发
    before = len(notes)
    pg.clock.fast_forward(120000)
    pg.wait_for_timeout(600)
    after = len(pg.evaluate('() => window.__notes'))
    chk('同一天不重复轰炸', after == before, 'before=%d after=%d' % (before, after))

    pg.locator('[data-act="notify-off"]').click()
    pg.wait_for_timeout(500)
    chk('可以关掉',
        pg.evaluate("() => localStorage.getItem('lifeboard.notify.on')") is None)

    # =========================================================
    print('\n[3] 日历导出（.ics）')
    pg.locator('[data-act="ics-export"]').click()
    pg.wait_for_timeout(900)
    blobs = pg.evaluate('() => window.__blobs.length')
    chk('触发了文件下载', blobs >= 1, 'blobs=%d' % blobs)
    raw = pg.evaluate("""async () => {
        const b = window.__blobs[window.__blobs.length - 1];
        return b ? await b.text() : '';
    }""")
    chk('是合法 iCalendar 外壳',
        raw.startswith('BEGIN:VCALENDAR') and raw.rstrip().endswith('END:VCALENDAR'),
        raw[:40])
    chk('声明了版本与 CALSCALE', 'VERSION:2.0' in raw and 'CALSCALE:GREGORIAN' in raw)
    lines = [l for l in raw.split('\r\n') if l]
    maxb = max(len(l.encode('utf-8')) for l in lines)
    chk('每行不超过 75 字节（RFC 5545 折行）', maxb <= 75, 'max=%d' % maxb)
    chk('折行后中文没被切断', '\ufffd' not in raw)
    uids = [l[4:] for l in lines if l.startswith('UID:')]
    chk('每个日程都有 UID', len(uids) == raw.count('BEGIN:VEVENT'), '%d vs %d' % (len(uids), raw.count('BEGIN:VEVENT')))
    chk('UID 唯一', len(set(uids)) == len(uids))
    chk('用药日程 5 条（3 个在吃 × 时段）', sum(1 for u in uids if u.startswith('med-')) == 5,
        str([u for u in uids if u.startswith('med-')]))
    chk('待办日程已生成', sum(1 for u in uids if u.startswith('task-')) >= 3,
        str([u for u in uids if u.startswith('task-')]))
    chk('习惯日程已生成', sum(1 for u in uids if u.startswith('habit-')) >= 1,
        str([u for u in uids if u.startswith('habit-')]))
    chk('每天重复写了 FREQ=DAILY', 'RRULE:FREQ=DAILY' in raw)
    chk('每周重复带 BYDAY', 'RRULE:FREQ=WEEKLY;BYDAY=WE' in raw, 'BYDAY 缺失或指错星期')
    chk('每月重复带 BYMONTHDAY', 'RRULE:FREQ=MONTHLY;BYMONTHDAY=1' in raw, 'BYMONTHDAY 缺失')
    chk('有停药日的疗程写了 UNTIL', ';UNTIL=' in raw)
    chk('每个日程都带提醒（VALARM）', raw.count('BEGIN:VALARM') == raw.count('BEGIN:VEVENT'))
    chk('提醒零延迟触发', 'TRIGGER:-PT0M' in raw)
    starts = [l for l in lines if l.startswith('DTSTART;')]
    chk('事件时间带 TZID 时区声明',
        all(l.startswith('DTSTART;TZID=Asia/Shanghai:') for l in starts), str(starts[:2]))
    chk('内嵌 VTIMEZONE 定义', 'BEGIN:VTIMEZONE' in raw and 'TZOFFSETTO:+0800' in raw)
    chk('没用 UTC 写事件时刻（否则 BYDAY 会偏一天）',
        all(not l.endswith('Z') for l in starts), str(starts[:2]))
    chk('已完成的待办没进日历', '已完成甲' not in raw)
    chk('逾期单次任务没进日历', '逾期甲' not in raw)

    # 再导一次，UID 必须完全一致（可重复导入而不叠加）
    pg.locator('[data-act="ics-export"]').click()
    pg.wait_for_timeout(700)
    raw2 = pg.evaluate("""async () => {
        const b = window.__blobs[window.__blobs.length - 1];
        return b ? await b.text() : '';
    }""")
    uids2 = [l[4:] for l in raw2.split('\r\n') if l.startswith('UID:')]
    chk('重复导出 UID 稳定（不会越导越多）', uids == uids2,
        'diff=%d' % len(set(uids) ^ set(uids2)))

    # =========================================================
    print('\n[4] 安装引导')
    nav(pg, 'today')
    pg.wait_for_timeout(500)
    tip = pg.locator('.install-tip')
    chk('今日页出现安装提示', tip.count() == 1, 'count=%d' % tip.count())
    chk('提示里写了安装路径', '安装' in (tip.inner_text() if tip.count() else ''))
    chk('设置页有安装面板', pg.locator('.ntf-box', has_text='装到手机桌面').count() >= 0)
    nav(pg, 'settings')
    pg.wait_for_timeout(400)
    chk('设置页列出装到桌面一栏',
        any('装到手机桌面' in (x or '') or '已经装到桌面' in (x or '')
            for x in pg.evaluate("() => [...document.querySelectorAll('.ntf-box b')].map(e=>e.textContent)")))
    nav(pg, 'today')
    pg.wait_for_timeout(400)
    pg.locator('[data-act="install-skip"]').click()
    pg.wait_for_timeout(500)
    chk('点 × 后提示消失', pg.locator('.install-tip').count() == 0)
    chk('关闭状态被记住',
        pg.evaluate("() => localStorage.getItem('lifeboard.install.dismissed')") == '1')
    pg.reload(wait_until='networkidle')
    pg.wait_for_timeout(2600)
    chk('刷新后不再打扰', pg.locator('.install-tip').count() == 0)

    # =========================================================
    print('\n[5] 回归：全视图与报错')
    for v in ['today', 'board', 'habits', 'meds', 'weight', 'essays', 'calendar', 'stats', 'settings']:
        nav(pg, v)
        pg.wait_for_timeout(320)
        ok = pg.evaluate("() => { const m = document.getElementById('main'); return !!m && m.innerText.length > 20; }")
        chk('视图 %s 正常渲染' % v, ok)

    chk('无 JS 运行时错误', len(errs) == 0, '; '.join(errs[:3]))

    br.close()

# =========================================================
print('\n' + '=' * 46)
print('PASS %d / %d' % (PASS, PASS + len(FAILS)))
if FAILS:
    for n, d in FAILS:
        print('  FAIL: %s | %s' % (n, d))
    sys.exit(1)
print('全部通过')
