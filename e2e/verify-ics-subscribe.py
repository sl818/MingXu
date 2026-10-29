# -*- coding: utf-8 -*-
"""服务端订阅接口的等价性验证。

两份 ICS 必须描述同一批日程：
  A. PHP 生成（api/ics.php，订阅接口用的那份）
  B. 前端生成（index.html 的 buildICS()，导出文件用的那份）

两边是独立实现，所以要比对解析出来的事件本身，而不是文本。
比对项：事件数、UID、DTSTART、DTEND、RRULE、SUMMARY。
"""
import io
import json
import os
import subprocess
import sys
import tempfile

from icalendar import Calendar

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PHP = os.path.join(tempfile.gettempdir(), 'php81', 'php.exe')
NOW = '2026-10-25 10:00:00'
TMP = tempfile.gettempdir()

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


STATE = {
    'habits': [
        # 用 h_breathe 这个内置 id：前端迁移会补它，id 对不上时前端会多生成一条
        {'id': 'h_breathe', 'name': '478呼吸法', 'icon': '🌬️', 'suggestTime': '15:00',
         'type': 'build', 'target': 1, 'unit': '组', 'color': '#5b8f8a',
         'note': '4-7-8 呼吸', 'breatheCycles': 4},
        {'id': 'h_water', 'name': '喝水', 'icon': '💧', 'type': 'build', 'target': 9,
         'unit': '杯', 'color': '#4c7f96', 'note': '', 'perMl': 250, 'goalMl': 2300},
        {'id': 'h3', 'name': '已归档习惯', 'icon': 'x', 'suggestTime': '09:00',
         'type': 'build', 'target': 1, 'unit': '次', 'archivedAt': '2026-10-01T00:00:00Z'},
        {'id': 'h4', 'name': '戒烟', 'icon': '🚭', 'type': 'quit', 'target': 1,
         'unit': '次', 'suggestTime': '09:00'},
    ],
    'meds': [
        {'id': 'm1', 'name': '阿莫西林', 'status': 'active', 'times': ['08:00', '20:00'],
         'startDate': '2026-10-01', 'endDate': '', 'doseAmount': 1, 'doseUnit': '片',
         'form': '片', 'note': '', 'courseType': 'long'},
        {'id': 'm2', 'name': '维生素D', 'status': 'active', 'times': ['12:00'],
         'startDate': '2026-10-01', 'endDate': '', 'doseAmount': 2, 'doseUnit': '粒',
         'form': '粒', 'note': '随餐', 'courseType': 'long'},
        {'id': 'm3', 'name': '头孢克肟', 'status': 'active', 'times': ['09:00'],
         'startDate': '2026-10-20', 'endDate': '2026-10-30', 'doseAmount': 1,
         'doseUnit': '片', 'form': '片', 'note': '', 'courseType': 'short'},
        {'id': 'm4', 'name': '过期疗程', 'status': 'active', 'times': ['09:00'],
         'startDate': '2026-10-01', 'endDate': '2026-10-10', 'doseAmount': 1,
         'doseUnit': '片', 'form': '片', 'note': '', 'courseType': 'short'},
        {'id': 'm5', 'name': '已停药', 'status': 'stopped', 'times': ['08:00'],
         'startDate': '2026-10-01', 'endDate': '', 'doseAmount': 1, 'doseUnit': '片',
         'form': '片', 'note': '', 'courseType': 'long'},
    ],
    'tasks': [
        {'id': 't1', 'title': '每日复盘', 'status': 'todo', 'due': '2026-10-25',
         'repeat': 'daily', 'repeatTime': '07:30', 'repeatWeekday': 0, 'repeatDay': 25,
         'tag': '工作', 'priority': '中', 'note': ''},
        {'id': 't2', 'title': '周报', 'status': 'todo', 'due': '2026-10-25',
         'repeat': 'weekly', 'repeatTime': '18:00', 'repeatWeekday': 3, 'repeatDay': 25,
         'tag': '工作', 'priority': '中', 'note': ''},
        {'id': 't3', 'title': '交房租', 'status': 'todo', 'due': '2026-10-25',
         'repeat': 'monthly', 'repeatTime': '10:30', 'repeatWeekday': 0, 'repeatDay': 1,
         'tag': '生活', 'priority': '高', 'note': ''},
        {'id': 't4', 'title': '三天后体检', 'status': 'todo', 'due': '2026-10-28',
         'repeat': 'none', 'repeatTime': '20:00', 'tag': '健康', 'priority': '高', 'note': '空腹'},
        {'id': 't5', 'title': '今天已过点', 'status': 'todo', 'due': '2026-10-25',
         'repeat': 'none', 'repeatTime': '20:00', 'tag': '生活', 'priority': '低', 'note': ''},
        {'id': 't6', 'title': '已完成', 'status': 'done', 'due': '2026-10-28',
         'repeat': 'none', 'repeatTime': '20:00', 'tag': '生活', 'priority': '低', 'note': ''},
        {'id': 't7', 'title': '逾期任务', 'status': 'todo', 'due': '2026-10-20',
         'repeat': 'none', 'repeatTime': '20:00', 'tag': '生活', 'priority': '低', 'note': ''},
    ],
    'checks': {}, 'notes': {}, 'moods': {}, 'events': [], 'doses': {},
    'bodyProfile': {'age': 30, 'height': 170}, 'weights': [], 'essays': [],
}

# ---------- A. PHP 生成 ----------
state_path = os.path.join(TMP, 'eq-state.json')
server_ics = os.path.join(TMP, 'eq-server.ics')
io.open(state_path, 'w', encoding='utf-8').write(json.dumps(STATE, ensure_ascii=False))
out = subprocess.run([PHP, os.path.join(ROOT, 'e2e', 'gen-ics.php'), state_path, NOW, server_ics],
                     capture_output=True, text=True)
if out.returncode != 0:
    print('PHP 生成失败:', out.stdout, out.stderr)
    sys.exit(1)
print('PHP 生成 %s 条事件' % out.stdout.strip())

# ---------- B. 前端生成 ----------
board['data'] = json.loads(json.dumps(STATE))   # 深拷贝，避免被前端保存改写
client_ics = os.path.join(TMP, 'eq-client.ics')

with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)
    ctx = br.new_context(viewport={'width': 1440, 'height': 950},
                         accept_downloads=True, timezone_id='Asia/Shanghai')
    ctx.add_init_script("""
      window.__blobs = [];
      (function(){
        const cob = URL.createObjectURL;
        URL.createObjectURL = function(b) { window.__blobs.push(b); return cob.call(URL, b); };
      })();
    """)
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)[:160]))
    pg.clock.install(time=datetime(2026, 10, 25, 10, 0, 0))
    pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
    pg.wait_for_timeout(600)
    pg.click('[data-act="cloud-login"]')
    pg.wait_for_timeout(400)
    pg.fill('input[name="email"]', 'test@sl00.top')
    pg.fill('input[name="password"]', 'test@sl00.top')
    pg.click('form.modal-card button[type="submit"]')
    pg.wait_for_timeout(2600)
    nav(pg, 'settings')
    pg.wait_for_timeout(500)
    pg.locator('[data-act="ics-export"]').click()
    pg.wait_for_timeout(800)
    raw = pg.evaluate("""async () => {
        const b = window.__blobs[window.__blobs.length - 1];
        return b ? await b.text() : '';
    }""")
    io.open(client_ics, 'w', encoding='utf-8', newline='').write(raw)
    br.close()


def collect(path):
    cal = Calendar.from_ical(io.open(path, 'r', encoding='utf-8', newline='').read())
    out = {}
    for e in cal.walk('VEVENT'):
        uid = str(e.get('uid'))
        ds = e.decoded('dtstart')
        de = e.decoded('dtend')
        rr = e.get('rrule')
        out[uid] = {
            'start': ds.strftime('%Y-%m-%d %H:%M') if hasattr(ds, 'strftime') else str(ds),
            'end': de.strftime('%Y-%m-%d %H:%M') if hasattr(de, 'strftime') else str(de),
            'rrule': str(rr) if rr else '',
            'summary': str(e.get('summary')),
        }
    return out


print('\n[1] 两份文件都能被解析')
A = collect(server_ics)
B = collect(client_ics)
chk('服务端 ICS 可解析', len(A) > 0, 'n=%d' % len(A))
chk('前端 ICS 可解析', len(B) > 0, 'n=%d' % len(B))

print('\n[2] 事件集合一致')
chk('事件数量相同', len(A) == len(B), 'server=%d client=%d' % (len(A), len(B)))
only_a = sorted(set(A) - set(B))
only_b = sorted(set(B) - set(A))
chk('UID 集合完全相同', not only_a and not only_b,
    '仅服务端:%s 仅前端:%s' % (only_a[:3], only_b[:3]))

print('\n[3] 每条日程的内容一致')
bad = []
for uid in sorted(set(A) & set(B)):
    for field in ('start', 'end', 'rrule', 'summary'):
        if A[uid][field] != B[uid][field]:
            bad.append('%s.%s: %r != %r' % (uid, field, A[uid][field], B[uid][field]))
chk('开始/结束/重复规则/标题全部一致', not bad, '; '.join(bad[:4]))

print('\n[4] 服务端输出本身合法')
chk('无 JS 报错（前端生成时）', len(errs) == 0 if 'errs' in dir() else True)
raw_server = io.open(server_ics, 'r', encoding='utf-8', newline='').read()
lines = [l for l in raw_server.split('\r\n') if l]
chk('每行 ≤ 75 字节', max(len(l.encode()) for l in lines) <= 75,
    'max=%d' % max(len(l.encode()) for l in lines))
chk('带 VTIMEZONE', 'BEGIN:VTIMEZONE' in raw_server)
chk('DTSTART 用 TZID', all(l.startswith('DTSTART;TZID=Asia/Shanghai:')
                          for l in lines if l.startswith('DTSTART;')))

print('\n' + '=' * 46)
print('PASS %d / %d' % (PASS, PASS + len(FAILS)))
if FAILS:
    for n, d in FAILS:
        print('  FAIL: %s | %s' % (n, d))
    sys.exit(1)
print('服务端与前端生成的日程完全等价')
