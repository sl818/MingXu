"""日历重构（v47）的端到端验证。

覆盖三件事：
  1. 月视图格子里显示当天待办（桌面标题 / 手机数量 / 超过 2 条折叠）
  2. 周视图时间线（0:00-24:00、合并块、时间块、全天行、点击清单、导航）
  3. 布局重排（三卡横排、本月习惯/用药挪到统计页）

时间是固定的 2026-10-25 10:30（周日），所以那一周是 10-19（周一）~ 10-25（周日）。
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
head = io.open(os.path.join(ROOT, 'e2e', 'verify-batch4.py'),
               encoding='utf-8').read().split('with sync_playwright() as p:')[0]
sys.argv = [sys.argv[0]]
exec(head)

pass_n = 0
fail_n = 0


def chk(name, ok, detail=''):
    global pass_n, fail_n
    if ok:
        pass_n += 1
        print('  OK  %s' % name)
    else:
        fail_n += 1
        print('  XX  %s   << %s' % (name, detail))


def clean_tasks():
    """替换成一组可控的待办，避免 mock 自带的干扰断言。"""
    board['data']['tasks'] = [
        # 有时间块：14:00 起 90 分钟
        {'id': 'c1', 'title': '项目评审会', 'note': '', 'tag': '工作', 'priority': '高',
         'status': 'todo', 'due': '2026-10-25', 'createdAt': '2026-10-20T00:00:00',
         'repeat': 'none', 'repeatTime': '20:00', 'notify': True, 'notifyTime': '14:00',
         'notifyNote': '', 'startTime': '14:00', 'duration': 90},
        # 没时间：进「全天」行
        {'id': 'c2', 'title': '买菜', 'note': '', 'tag': '生活', 'priority': '中',
         'status': 'todo', 'due': '2026-10-25', 'createdAt': '2026-10-20T00:00:00',
         'repeat': 'none', 'repeatTime': '20:00', 'notify': True, 'notifyTime': '09:00',
         'notifyNote': '', 'startTime': '', 'duration': 0},
        # 同一天再来两条，测「只显示 2 条 + N」
        {'id': 'c3', 'title': '预约体检', 'note': '', 'tag': '健康', 'priority': '中',
         'status': 'todo', 'due': '2026-10-25', 'createdAt': '2026-10-20T00:00:00',
         'repeat': 'none', 'repeatTime': '20:00', 'notify': True, 'notifyTime': '09:00',
         'notifyNote': '', 'startTime': '', 'duration': 0},
        {'id': 'c4', 'title': '补充常备药', 'note': '', 'tag': '健康', 'priority': '低',
         'status': 'todo', 'due': '2026-10-25', 'createdAt': '2026-10-20T00:00:00',
         'repeat': 'none', 'repeatTime': '20:00', 'notify': True, 'notifyTime': '09:00',
         'notifyNote': '', 'startTime': '', 'duration': 0},
        # 已完成的不该出现
        {'id': 'c5', 'title': '已经做完了', 'note': '', 'tag': '生活', 'priority': '中',
         'status': 'done', 'due': '2026-10-25', 'doneAt': '2026-10-25',
         'createdAt': '2026-10-20T00:00:00', 'repeat': 'none', 'repeatTime': '20:00',
         'notify': True, 'notifyTime': '09:00', 'notifyNote': '', 'startTime': '', 'duration': 0},
    ]


def clean_meds():
    """三个同在 08:00 的药，用来验证合并成一块。"""
    board['data']['meds'] = []
    for i, name in enumerate(['缬沙坦', '甲钴胺', '二甲双胍']):
        board['data']['meds'].append({
            'id': 'cm%d' % i, 'name': name, 'purpose': '其他', 'form': '片', 'strength': '',
            'doseAmount': 1, 'doseUnit': '片', 'times': ['08:00'], 'courseType': 'long',
            'status': 'active', 'startDate': '2026-09-01', 'endDate': '',
            'mealTiming': '', 'mealOffset': '', 'note': '',
            'stockBase': '', 'stockBaseAt': '', 'updatedAt': 1, 'createdAt': '2026-09-01T00:00:00',
        })


def clean_habits():
    """只留一个 15:00 的习惯，其余去掉避免时间线太杂。"""
    board['data']['habits'] = [{
        'id': 'ch1', 'name': '读书', 'icon': '📖', 'type': 'build', 'target': 1, 'unit': '次',
        'color': '#2f6f5e', 'note': '', 'createdAt': '2026-09-01T00:00:00',
        # 16:00 而不是 15:00：15:00 是 478 呼吸法的默认时刻，
        # 两个习惯会合并成「习惯 ×2」，就看不出单独一条的定位了
        'suggestTime': '16:00', 'notify': True, 'notifyFreq': 'daily',
    }]


clean_tasks()
clean_meds()
clean_habits()


with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)

    # ════════════════ 桌面 1440 ════════════════
    ctx = br.new_context(viewport={'width': 1440, 'height': 1000})
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)[:160]))
    pg.on('console', lambda m: errs.append('console:' + m.text[:120]) if m.type == 'error' else None)
    pg.clock.install(time=datetime(2026, 10, 25, 10, 30, 0))
    pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
    pg.wait_for_timeout(600)
    pg.click('[data-act="cloud-login"]'); pg.wait_for_timeout(400)
    pg.fill('input[name="email"]', 'test@sl00.top'); pg.fill('input[name="password"]', 'test@sl00.top')
    pg.click('form.modal-card button[type="submit"]'); pg.wait_for_timeout(2800)

    print('\n[1] 月视图：格子里的待办')
    nav(pg, 'calendar'); pg.wait_for_timeout(1000)
    mon = pg.evaluate("""() => {
        const cells=[...document.querySelectorAll('.cal-cell:not(.blank)')];
        const c=[...cells].find(x=>x.dataset.date==='2026-10-25');
        if(!c) return {miss:true};
        return {
            hasTab: !!document.querySelector('[data-act="cal-mode"][data-mode="week"]'),
            monthActive: (()=>{const t=document.querySelector('.cal-tab.active');return t?t.textContent.trim():''})(),
            tasks: [...c.querySelectorAll('.cal-task')].map(x=>x.textContent.trim()),
            more: (()=>{const m=c.querySelector('.cal-task-more');return m?m.textContent.trim():''})(),
            numShown: (()=>{const n=c.querySelector('.cal-tasks-num');
                return n ? getComputedStyle(n).display !== 'none' : false})(),
            done: c.textContent.indexOf('已经做完了') >= 0,
            pct: !!c.querySelector('.cal-pct'),
            mood: !!c.querySelector('.cal-mood'),
            level: c.dataset.level
        };
    }""")
    chk('月视图存在月/周切换', mon.get('hasTab'))
    chk('默认停在月视图', mon.get('monthActive') == '月', mon.get('monthActive'))
    chk('25 号格子里有 2 条待办标题', len(mon.get('tasks', [])) == 2, str(mon.get('tasks')))
    chk('超过 2 条显示 +N', mon.get('more') == '+2', mon.get('more'))
    chk('桌面显示标题、不显示「N 项」', mon.get('numShown') is False)
    chk('已完成的待办不进格子', mon.get('done') is False)
    chk('完成度百分比还在', mon.get('pct'))
    chk('心情 emoji 还在', mon.get('mood'))
    chk('完成度染色等级有效', str(mon.get('level')) in ('0', '1', '2', '3', '4'), str(mon.get('level')))

    print('\n[2] 周视图：结构')
    pg.click('[data-act="cal-mode"][data-mode="week"]'); pg.wait_for_timeout(900)
    wk = pg.evaluate("""() => {
        const tab=document.querySelector('.cal-tab.active');
        const cols=[...document.querySelectorAll('.wk-col')];
        const hours=[...document.querySelectorAll('.wk-hour')];
        const days=[...document.querySelectorAll('.wk-day')];
        return {
            activeTab: tab?tab.textContent.trim():'',
            colCount: cols.length,
            hourCount: hours.length,
            dayCount: days.length,
            firstHour: hours[0]?hours[0].textContent.trim():'',
            lastHour: hours[hours.length-1]?hours[hours.length-1].textContent.trim():'',
            range: (()=>{const b=document.querySelector('.month-nav b');return b?b.textContent.trim():''})(),
            todayMark: days.filter(d=>d.classList.contains('is-today')).length,
            nowLine: !!document.querySelector('.wk-now')
        };
    }""")
    chk('tab 切到「周」', wk.get('activeTab') == '周', wk.get('activeTab'))
    chk('7 天列', wk.get('colCount') == 7, str(wk.get('colCount')))
    chk('24 个小时刻度', wk.get('hourCount') == 24, str(wk.get('hourCount')))
    chk('时间从 00:00 到 23:00', wk.get('firstHour') == '00:00' and wk.get('lastHour') == '23:00',
        wk.get('firstHour') + '-' + wk.get('lastHour'))
    chk('日期范围同月不重复月份', wk.get('range') == '10月19–25日', wk.get('range'))
    chk('今天的列有标记', wk.get('todayMark') == 1, str(wk.get('todayMark')))
    chk('有当前时刻红线', wk.get('nowLine'))

    print('\n[3] 周视图：事件块')
    ev = pg.evaluate("""() => {
        const evs=[...document.querySelectorAll('.wk-ev')].map(e=>({
            k: e.className.replace('wk-ev','').trim(),
            t: e.textContent.trim(),
            top: Number(String(e.style.top).replace('px','')),
            h: Number(String(e.style.height).replace('px','')),
            date: e.dataset.date
        }));
        const med=evs.find(x=>/用药 ×3/.test(x.t));
        const task=evs.find(x=>x.t==='项目评审会');
        const habit=evs.find(x=>x.t==='读书');
        return {total:evs.length, med:med||null, task:task||null, habit:habit||null,
                allKinds: evs.map(x=>x.t),
                allday: [...document.querySelectorAll('.wk-ad-item')].map(x=>x.textContent.trim())};
    }""")
    chk('三个同时间的药合并成「用药 ×3」', ev.get('med') is not None, str(ev.get('total')))
    if ev.get('med'):
        chk('合并块定位在 08:00（8×44=352）', abs(ev['med']['top'] - 352) < 2, str(ev['med']['top']))
    chk('14:00 的待办画成时间块', ev.get('task') is not None)
    if ev.get('task'):
        chk('时间块起点 14:00（14×44=616）', abs(ev['task']['top'] - 616) < 2, str(ev['task']['top']))
        chk('90 分钟高度 66px（1.5×44）', abs(ev['task']['h'] - 66) < 3, str(ev['task']['h']))
    chk('习惯出现在时间线上', ev.get('habit') is not None)
    if ev.get('habit'):
        chk('习惯定位在 16:00（16×44=704）', abs(ev['habit']['top'] - 704) < 3, str(ev['habit']['top']))
    chk('不同时刻的习惯各自成块',
        all(x in ev.get('allKinds', []) for x in ('478呼吸法', '读书')), str(ev.get('allKinds'))[:120])
    chk('没填时间的待办进「全天」行', '买菜' in ev.get('allday', []), str(ev.get('allday')))

    print('\n[4] 周视图：点开清单与导航')
    pg.locator('.wk-ev', has_text='用药 ×3').first.click(); pg.wait_for_timeout(500)
    det = pg.evaluate("""() => {
        const m=document.querySelector('.modal-card');
        if(!m) return {open:false};
        const li=[...m.querySelectorAll('.wk-detail-list li')].map(x=>x.textContent.trim());
        return {open:true, title:m.querySelector('h3').textContent.trim(), items:li};
    }""")
    chk('点合并块弹出清单', det.get('open'))
    chk('清单列出 3 个药', len(det.get('items', [])) == 3, str(det.get('items')))
    chk('弹窗标题含日期与时间',
        bool(__import__('re').search(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}', str(det.get('title')))),
        str(det.get('title')))
    pg.click('[data-act="close-modal"]'); pg.wait_for_timeout(300)

    pg.click('[data-act="week-shift"][data-delta="-1"]'); pg.wait_for_timeout(700)
    prev = pg.evaluate("() => document.querySelector('.month-nav b').textContent.trim()")
    chk('上一周切到 10月12–18日', prev == '10月12–18日', prev)
    pg.click('[data-act="week-today"]'); pg.wait_for_timeout(700)
    back = pg.evaluate("() => document.querySelector('.month-nav b').textContent.trim()")
    chk('「本周」回到 10月19–25日', back == '10月19–25日', back)

    print('\n[5] 布局重排')
    lay = pg.evaluate("""() => {
        const cards=[...document.querySelectorAll('.cal-cards > .cal-side-panel')];
        return {
            cardCount: cards.length,
            titles: cards.map(c=>c.querySelector('h3').textContent.trim()),
            sameRow: cards.length ? new Set(cards.map(c=>Math.round(c.getBoundingClientRect().top))).size === 1 : false,
            oldSideGone: !document.querySelector('.cal-side'),
            noHabitPanelOnCal: [...document.querySelectorAll('.panel h3')].every(h=>!/本月习惯|本月用药/.test(h.textContent))
        };
    }""")
    chk('日历页底部 3 张卡', lay.get('cardCount') == 3, str(lay.get('cardCount')))
    chk('三卡是「小结 / 心情 / 体重」',
        lay.get('titles') == ['本月小结', '本月心情', '本月体重'], str(lay.get('titles')))
    chk('三卡在同一行', lay.get('sameRow'))
    chk('旧的右侧栏已移除', lay.get('oldSideGone'))
    chk('日历页不再有本月习惯/本月用药', lay.get('noHabitPanelOnCal'))

    nav(pg, 'stats'); pg.wait_for_timeout(1000)
    st = pg.evaluate("""() => {
        const t=[...document.querySelectorAll('.panel h3')].map(h=>h.textContent.replace(/\\s+/g,' ').trim());
        return {titles:t, hasMed:t.some(x=>x.indexOf('用药')===0),
                hasHabit:t.some(x=>x.indexOf('习惯')===0),
                order: t.map(x=>x.slice(0,2))};
    }""")
    chk('统计页出现用药块', st.get('hasMed'), str(st.get('titles'))[:160])
    chk('统计页出现习惯块', st.get('hasHabit'))
    chk('面板顺序：总览 → 习惯 → 用药',
        st.get('order', [])[:3] == ['总览', '习惯', '用药'], str(st.get('order')))
    chk('桌面端无 JS 报错', not errs, str(errs[:2]))
    ctx.close()

    # ════════════════ 手机 390 ════════════════
    ctx2 = br.new_context(viewport={'width': 390, 'height': 844}, has_touch=True, is_mobile=True)
    pg2 = ctx2.new_page()
    errs2 = []
    pg2.on('pageerror', lambda e: errs2.append(str(e)[:160]))
    pg2.clock.install(time=datetime(2026, 10, 25, 10, 30, 0))
    pg2.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
    pg2.wait_for_timeout(600)
    pg2.click('[data-act="cloud-login"]'); pg2.wait_for_timeout(400)
    pg2.fill('input[name="email"]', 'test@sl00.top'); pg2.fill('input[name="password"]', 'test@sl00.top')
    pg2.click('form.modal-card button[type="submit"]'); pg2.wait_for_timeout(2800)

    print('\n[6] 手机：月视图只显示数量')
    nav(pg2, 'calendar'); pg2.wait_for_timeout(1000)
    mm = pg2.evaluate("""() => {
        const c=[...document.querySelectorAll('.cal-cell:not(.blank)')].find(x=>x.dataset.date==='2026-10-25');
        if(!c) return {miss:true};
        const num=c.querySelector('.cal-tasks-num');
        const t=c.querySelector('.cal-task');
        return {numText:num?num.textContent.trim():'',
                numShown:num?getComputedStyle(num).display!=='none':false,
                taskHidden:t?getComputedStyle(t).display==='none':null};
    }""")
    chk('手机上显示「4 项」', mm.get('numText') == '4 项', mm.get('numText'))
    chk('数量在手机上是可见的', mm.get('numShown') is True)
    chk('卡片标题在手机上隐藏', mm.get('taskHidden') is True, str(mm.get('taskHidden')))

    print('\n[7] 手机：周视图横向滚动与自动定位')
    pg2.click('[data-act="cal-mode"][data-mode="week"]'); pg2.wait_for_timeout(1000)
    mw = pg2.evaluate("""() => {
        const sc=document.getElementById('wk-scroll');
        const panel=document.querySelector('.cal-wrap');
        const hint=document.querySelector('.wk-swipe-hint');
        return {scrollW:sc?sc.scrollWidth:0, clientW:sc?sc.clientWidth:0,
                canScrollX: sc ? sc.scrollWidth > sc.clientWidth + 5 : false,
                scrollTop: sc?Math.round(sc.scrollTop):0,
                panelW: panel?Math.round(panel.getBoundingClientRect().width):0,
                hintShown: hint?getComputedStyle(hint).display!=='none':false,
                pageOvf: document.documentElement.scrollWidth>document.documentElement.clientWidth};
    }""")
    chk('时间线可以横向滚动', mw.get('canScrollX'),
        'scrollW=%s clientW=%s' % (mw.get('scrollW'), mw.get('clientW')))
    chk('面板没被撑出屏幕', mw.get('panelW', 0) < 390, str(mw.get('panelW')))
    chk('打开时自动滚到当前时刻附近', 200 < mw.get('scrollTop', 0) < 700, str(mw.get('scrollTop')))
    chk('手机上出现滑动提示', mw.get('hintShown') is True)
    chk('页面本身没有横向溢出', mw.get('pageOvf') is False)
    chk('手机端无 JS 报错', not errs2, str(errs2[:2]))
    ctx2.close()
    br.close()

print('\n' + '=' * 46)
print('通过 %d / %d' % (pass_n, pass_n + fail_n))
if fail_n:
    print('失败 %d 项' % fail_n)
sys.exit(0 if fail_n == 0 else 1)
