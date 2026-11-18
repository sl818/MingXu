# -*- coding: utf-8 -*-
"""v33 ICS 交叉验证：把真实导出的文件交给第三方 iCalendar 解析器，
确认能被系统日历正常读入（结构、时区、重复规则、提醒）。"""
import io, json, os, sys
from icalendar import Calendar

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


board['data']['tasks'].append({
    'id': 'r1', 'title': '每周复盘', 'note': '', 'tag': '工作', 'priority': '中',
    'status': 'todo', 'due': '2026-10-25', 'createdAt': '2026-10-01T08:00:00Z',
    'repeat': 'daily', 'repeatTime': '07:30', 'repeatWeekday': 0, 'repeatDay': 25})
board['data']['tasks'].append({
    'id': 'r2', 'title': '周报', 'note': '发给组长', 'tag': '工作', 'priority': '中',
    'status': 'todo', 'due': '2026-10-25', 'createdAt': '2026-10-01T08:00:00Z',
    'repeat': 'weekly', 'repeatTime': '18:00', 'repeatWeekday': 3, 'repeatDay': 25})
for h in board['data']['habits']:
    if h['id'] == 'h_plan':
        h['suggestTime'] = '09:00'

OUT = os.path.join(ROOT, 'e2e', 'out-v33.ics')

with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)
    ctx = br.new_context(viewport={'width': 1440, 'height': 950}, accept_downloads=True)
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)[:160]))
    pg.clock.install(time=datetime(2026, 10, 25, 10, 0, 0))
    pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
    pg.wait_for_timeout(500)
    pg.click('[data-act="cloud-login"]')
    pg.wait_for_timeout(350)
    pg.fill('input[name="email"]', 'test@example.com')
    pg.fill('input[name="password"]', 'test@example.com')
    pg.click('form.modal-card button[type="submit"]')
    pg.wait_for_timeout(2500)
    nav(pg, 'settings')
    pg.wait_for_timeout(500)
    with pg.expect_download() as dl:
        pg.locator('[data-act="ics-export"]').click()
    dl.value.save_as(OUT)
    br.close()

print('\n[1] 第三方解析器')
raw = io.open(OUT, 'r', encoding='utf-8', newline='').read()
cal = Calendar.from_ical(raw)
chk('icalendar 能完整解析', cal is not None)
chk('产品标识可识别', 'wanfeng' in str(cal.get('prodid', '')).lower(),
    str(cal.get('prodid')))
chk('声明了日历名', str(cal.get('x-wr-calname')) != 'None', str(cal.get('x-wr-calname')))

events = [c for c in cal.walk('VEVENT')]
chk('事件数量与源数据匹配', len(events) >= 6, 'events=%d' % len(events))

print('\n[2] 时区与时间')
tzs = [c for c in cal.walk('VTIMEZONE')]
chk('带 VTIMEZONE', len(tzs) == 1, 'n=%d' % len(tzs))
chk('时区是 Asia/Shanghai', str(tzs[0].get('tzid')) == 'Asia/Shanghai' if tzs else False,
    str(tzs[0].get('tzid')) if tzs else '')
dt = events[0].decoded('dtstart')
chk('dtstart 能解码成本地时间', dt is not None and dt.tzinfo is not None, str(dt))

# 07:30 那条必须落回 07:30，不能被 UTC 换算挪走
early = [e for e in events if '每周复盘' in str(e.get('summary'))]
chk('早于 8 点的重复任务仍保持在 07:30',
    bool(early) and early[0].decoded('dtstart').hour == 7 and early[0].decoded('dtstart').minute == 30,
    str(early[0].decoded('dtstart')) if early else '未找到')

print('\n[3] 重复规则')
r1 = early[0].get('rrule') if early else None
chk('每日重复被正确解析', r1 is not None and [str(x) for x in r1.get('FREQ', [])] == ['DAILY'], str(r1))
weekly = [e for e in events if '周报' in str(e.get('summary'))]
r2 = weekly[0].get('rrule') if weekly else None
chk('每周重复被正确解析', r2 is not None and [str(x) for x in r2.get('FREQ', [])] == ['WEEKLY'], str(r2))
chk('每周的星期与设定一致（repeatWeekday=3 → 周三）',
    r2 is not None and [str(x) for x in r2.get('BYDAY', [])] == ['WE'],
    str(r2.get('BYDAY')) if r2 else '')

print('\n[4] 提醒与字段')
alarms = [c for c in cal.walk('VALARM')]
chk('每个事件都带提醒', len(alarms) == len(events), '%d vs %d' % (len(alarms), len(events)))
trig = alarms[0].decoded('trigger') if alarms else None
chk('提醒在事件开始时触发', str(trig) in ('0:00:00', '0 seconds', 'PT0S'), str(trig))
med_events = [e for e in events if '\U0001F48A' in str(e.get('summary'))]
med_times = sorted(e.decoded('dtstart').strftime('%H:%M') for e in med_events)
chk('用药时刻没被挪走（08:00 / 12:00 / 20:00）',
    '08:00' in med_times and '12:00' in med_times and '20:00' in med_times, str(med_times))
chk('用药事件标题带药名与剂量',
    any('💊' in str(e.get('summary')) for e in events),
    '; '.join(str(e.get('summary')) for e in events)[:120])
chk('有备注的事件保留了描述',
    any('发给组长' in str(e.get('description', '')) for e in events), '')
chk('全程无 JS 报错', len(errs) == 0, '; '.join(errs[:2]))

print('\n' + '=' * 46)
print('PASS %d / %d' % (PASS, PASS + len(FAILS)))
if FAILS:
    for n, d in FAILS:
        print('  FAIL: %s | %s' % (n, d))
    sys.exit(1)
print('日历文件可被第三方解析器正确读入')
