# -*- coding: utf-8 -*-
"""v33 新增元素对比度审计：提醒面板 / 安装提示 / 折叠计数，9 皮肤 × 明暗。"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
head = open(os.path.join(ROOT, 'e2e', 'verify-batch4.py'), encoding='utf-8').read().split('with sync_playwright() as p:')[0]
sys.argv = [sys.argv[0]]
exec(head)

# 让推送面板处于「已配置 + 有记录」状态，否则 pc-* 元素不会渲染，会被记成缺失
_og_get = H.do_GET


def _get_push(self):
    if 'action=push_status' in self.path:
        self._j({'ok': True, 'enabled': True,
                 'webhook': 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test',
                 'sent_today': 3, 'last_sent': '2026-10-25 08:00:00',
                 'recent': [
                     {'key': 'k1', 'kind': 'med', 'at': '2026-10-25 08:00:00',
                      'text': '该吃药了\n阿莫西林 1片（每天 08:00）'},
                     {'key': 'k2', 'kind': 'report', 'at': '2026-10-25 08:20:00',
                      'text': '今日待办早报\n未完成 2 项'},
                 ]})
        return
    if 'action=push_preview' in self.path:
        self._j({'ok': True, 'date': '2026-10-25', 'items': [
            {'time': '08:00', 'kind': 'med', 'title': '该吃药了', 'body': '阿莫西林 1片（每天 08:00）'},
            {'time': '08:20', 'kind': 'report', 'title': '今日待办早报', 'body': '未完成 2 项\n· 工作 1 项'},
            {'time': '20:00', 'kind': 'report', 'title': '今日小结', 'body': '今日完成 1 项待办\n明日待办 2 条'},
        ]})
        return
    _og_get(self)


# 戒烟卡片与「戒烟分析」面板只有在存在 quit 习惯时才渲染。
# mock 数据里补一条 + 今天两条事件，否则新增的 7 个选择器全是「元素缺失」，审计等于没做。
import time as _time
# 页面里装了 pg.clock，今天被冻结在 2026-10-25；mock 事件也必须用这一天，
# 否则 dayCravings 匹配不到「今天」，卡片上一条记录都不会有
_t8 = int(_time.mktime((2026, 10, 25, 8, 0, 0, 0, 0, -1)))
board['data']['habits'].append({
    # v64 起戒烟是独立类型 'smoke'，写 'quit' 会走普通戒除卡，烟盒上的元素全都取不到
    'id': 'h_drink', 'name': '戒烟', 'icon': '🚭', 'type': 'smoke',
    'target': 1, 'unit': '次', 'color': '#9c5a5a', 'note': '',
    'createdAt': '2026-09-01T00:00:00Z', 'notify': True,
})
# 三种包状态要同时出现，否则 .pack-cf / .qpack-st.done / .qpack-st.stock 取不到样本：
#   pk1 昨天抽完（触发末支软确认条）、pk2 今天在抽、pk3 还没轮到（库存）
_p1 = _t8 - 86400
board['data']['packs'] = [
    {'id': 'pk1', 'at': _p1, 'name': '普皖', 'price': 15, 'size': 20},
    {'id': 'pk2', 'at': _t8 + 3600, 'name': '普皖', 'price': 15, 'size': 20},
    {'id': 'pk3', 'at': _t8 + 7200, 'name': '利群', 'price': 18, 'size': 20},
]
_cr = [
    {'id': 'cq1', 't': _t8, 'k': 'r', 'h': 'h_drink', 'g': 'meal', 's': 0},
    {'id': 'cq2', 't': _t8 + 1800, 'k': 'r', 'h': 'h_drink', 'g': 'bored', 's': 0},
]
for _i in range(20):
    _cr.append({'id': 's1_%d' % _i, 't': _p1 + _i * 1800, 'k': 's', 'h': 'h_drink', 'g': '', 's': 0})
for _i in range(3):
    _cr.append({'id': 's2_%d' % _i, 't': _t8 + 3600 + 1800 * (_i + 1), 'k': 's', 'h': 'h_drink', 'g': '', 's': 0})
board['data']['cravings'] = _cr

# 配置页要有通知才取得到样本
# 倒数日：未来 / 过去 / 暂停 三种状态都要有样本
board['data']['countdowns'] = [
    {'id': 'cd1', 'title': '考研', 'date': '2026-11-20', 'note': '记得打印准考证',
     'time': '09:00', 'remindDays': [3, 1, 0], 'on': True},
    {'id': 'cd2', 'title': '入职', 'date': '2026-10-01', 'note': '',
     'time': '09:00', 'remindDays': [1, 0], 'on': True},
    {'id': 'cd3', 'title': '旧事', 'date': '2026-09-01', 'note': '',
     'time': '09:00', 'remindDays': [0], 'on': False},
]

# 清债（v88）：审计要取到总览和债务卡，没有债就只剩空状态
board['data']['money'] = {
    'v': 1,
    'debts': [
        {'id': 'md1', 'name': '信用卡A', 'type': 'card', 'balance': 38000, 'start': 45000,
         'apr': 18, 'min': 1900, 'due': 5, 'note': '', 'clearedAt': '', 'u': 1},
        # due=25 对齐审计时钟的「今天」，否则日历里取不到 .cal-debt / .wk-ad-debt
        {'id': 'md2', 'name': '亲友', 'type': 'friend', 'balance': 20000, 'start': 20000,
         'apr': 0, 'min': 500, 'due': 25, 'note': '', 'clearedAt': '', 'u': 1},
    ],
    'extra': 1000, 'strategy': 'snowball', 'customOrder': [],
    'snowflakes': [{'id': 'sf1', 'ym': '2026-12', 'amount': 5000, 'note': '年终奖', 'u': 1}],
    'startYM': '2026-11',
    'log': [{'id': 'lg1', 'date': '2026-10-20', 'debtId': 'md1', 'debtName': '信用卡A',
             'amount': 1900, 'note': '这个月多还了一点', 'u': 1}],
    # v90 预算页：没有收入/分类/流水的话整页只剩空态，选择器全都「元素缺失」。
    # 日期跟着 pg.clock（2026-10-25）走，流水才落在这个月里。
    'incomes': [{'id': 'mi1', 'name': '工资', 'amount': 12000, 'u': 1}],
    'cats': [{'id': 'mc1', 'name': '房租', 'kind': 'fixed', 'budget': 3500, 'u': 1},
             {'id': 'mc2', 'name': '吃饭', 'kind': 'daily', 'budget': 2000, 'u': 1}],
    'spends': [{'id': 'ms1', 'date': '2026-10-20', 'catId': 'mc2', 'catName': '吃饭',
                'amount': 58, 'note': '午饭', 'u': 1},
               {'id': 'ms2', 'date': '2026-10-22', 'catId': 'mc2', 'catName': '吃饭',
                'amount': 42, 'note': '', 'u': 1}],
    'notify': {'on': False, 'before': [3, 1, 0], 'time': '09:00'},
}
board['data']['moneyAt'] = 1

# 戒除多次模式（v79）：一个已破（.quit-add.broken + .quit-undo）、一个未破
_qm = int(datetime(2026, 10, 25, 9, 0).timestamp())
_qbase = {'type': 'quit', 'target': 1, 'unit': '次', 'note': '',
          'createdAt': '2026-10-01T08:00:00Z', 'pinned': False, 'med': False,
          'quitStart': '2026-10-01', 'slipMode': 'multi'}
board['data']['habits'] += [
    dict(_qbase, id='h_qm_brk', name='不喝可乐', icon='🥤', color='#c2705f'),
    dict(_qbase, id='h_qm_ok', name='不喝奶茶', icon='🧋', color='#8a6fa8'),
]
board['data']['cravings'].append(
    {'id': 'cqm1', 't': _qm, 'k': 's', 'h': 'h_qm_brk', 'g': '', 's': 0})

board['data']['notices'] = [
    {'id': 'n1', 'text': '该吃维生素了', 'time': '20:00', 'mode': 'daily', 'on': True},
    {'id': 'n2', 'text': '周复盘', 'time': '21:30', 'mode': 'weekly', 'weeks': [1, 4], 'on': True},
    {'id': 'n3', 'text': '交房租', 'time': '09:00', 'mode': 'monthly', 'monthday': 1, 'on': False},
    # 已过期的单次：不给一条，.notice-row.past 那套灰字取不到样本
    {'id': 'n4', 'text': '昨天这条已经发过了', 'time': '09:00', 'mode': 'once',
     'date': '2026-10-24', 'weeks': [], 'monthday': 1, 'on': True},
]

H.do_GET = _get_push

JS = """
(sels) => {
  const lum = c => { const [r,g,b] = c.map(v => { v/=255; return v <= 0.03928 ? v/12.92 : Math.pow((v+0.055)/1.055, 2.4); });
    return 0.2126*r + 0.7152*g + 0.0722*b; };
  const parse = s => { const t=String(s); const m=t.match(/[\\d.]+/g); if(!m) return null;
    const n=m.slice(0,3).map(Number); return /^color\\(/.test(t) ? n.map(v=>v*255) : n; };
  const bgOf = el => { let n=el;
    while(n && n!==document.documentElement){ const cs=getComputedStyle(n);
      const s=cs.backgroundColor, c=parse(s), a=String(s).match(/[\\d.]+/g);
      if(c && (!a[3] || Number(a[3])>0.6)) return c;
      /* 渐变背景取端点平均色。原来遇到渐变就放弃，导致 paper 等皮肤整体被跳过 */
      const bi=cs.backgroundImage;
      if(bi && bi!=='none'){
        const cols=bi.match(/rgba?\\([^)]+\\)/g);
        if(cols && cols.length){
          const arrs=cols.map(x=>parse(x)).filter(Boolean);
          if(arrs.length) return [0,1,2].map(i=>arrs.reduce((t,x)=>t+x[i],0)/arrs.length);
        }
      }
      n=n.parentElement; }
    return null; };
  const out=[];
  sels.forEach(sel=>{ const el=document.querySelector(sel); if(!el) { out.push({sel, missing:true}); return; }
    const cs=getComputedStyle(el), fg=parse(cs.color), bg=bgOf(el);
    if(!fg||!bg){ out.push({sel, skip:true}); return; }
    const l1=lum(fg), l2=lum(bg);
    out.push({sel, ratio: Math.round(((Math.max(l1,l2)+0.05)/(Math.min(l1,l2)+0.05))*100)/100,
               size: parseFloat(cs.fontSize), weight: cs.fontWeight}); });
  return out;
}
"""

# v71 起「提醒 / 日历订阅 / 手机推送 / 安装」整块搬到了配置页，设置页只剩排版和主题。
# 取样点跟着搬，否则会在设置页报一堆「元素缺失」，把真正的回归淹掉。
SELS_SETTINGS = ['.layout-name', '.layout-desc', '.theme-name', '.theme-desc',
                  # v86 设置页「导航顺序」：组标题 + 行名
                  '.no-head', '.no-head span', '.no-row b']
SELS_TODAY = ['.install-tip .it-body b', '.install-tip .it-body small', '.remind-more', '.it-go',
              # 「其他习惯」目标 1 次的打卡按钮（v74）。mock 里 h_run 已打卡、h_plan 没打，
              # 两种状态各取一次；用 :not(.on) 区分，否则第一个匹配到的永远是 on 态。
              '.habit-done:not(.on)', '.habit-done:not(.on) span', '.habit-done.on',
              '.habit-done.on span', '.sec-acts .sort-btn',
              # 戒除多次模式的按钮（v79）：未破 / 已破两种状态 + 撤销
              '.quit-add:not(.broken)', '.quit-add:not(.broken) span',
              '.quit-add.broken', '.quit-add.broken span',
              '.quit-undo', '.quit-count span',
              # v100 证据层与文字状态
              '.habit-state', '.hp-num b', '.hp-cap']
# .adh-delta 与 .adh-note 是互斥的两个分支（有上月数据 / 没有），
# 同一时刻只会出现一个，所以只取有数据时的那种。--muted 那套已被 .ics-hint 等覆盖。
SELS_STATS = ['.adh-big', '.adh-delta', '.adh-head + .chart .bar-col span',
              '.stats-acts .btn', '.stats-acts .range-switch button',
              # v84 分区后新增：分段控件（当前格是 accent 字压 surface 底）、分区小标题
              '.sblock-head b', '.sblock-head span', '.shead h3',
              '.stab button', '.stab button.on',
              # v85 总览里的任务摘要三格（.rv-cell 的另一处用法）
              '.tk-grid .rv-cell small', '.tk-grid .rv-cell b', '.tk-grid .rv-cell span']
# 待办页底部的任务完成度面板（v80）。五格里只有「已完成」换了底色，
# 所以单独取一次 .ts-cell.ok b —— 它在 accent 淡底上，最容易踩线。
SELS_BOARD = ['.ts-chip', '.ts-chip.on', '.ts-cell b', '.ts-cell span',
              '.ts-cell.ok b', '.ts-cell.ok span', '.ts-rate span',
              '.ts-rate span b', '.ts-note']
# 日历：月视图格子里的待办、底部三卡
SELS_CAL_MONTH = ['.cal-task', '.cal-tasks-num', '.cal-pct', '.cal-tab', '.cal-side-panel h3',
                  '.cal-debt',
                  # 倒数日右栏（v76）：大数字、单位、标题、日期、备注、分组标题
                  '.cd-num b', '.cd-num i', '.cd-main b', '.cd-main small', '.cd-main em',
                  '.cd-group', '.cd-item.past .cd-main b']
# 日历：周视图时间线
SELS_CAL_WEEK = ['.wk-wd', '.wk-num', '.wk-hour', '.wk-ev b', '.wk-ad-item', '.wk-legend',
                 '.wk-ad-debt']
# 戒烟常驻卡（v50）：两个按钮、状态字、数据行、里程碑、今日记录
# .cl-item 的底色是 rgba 浅红/浅绿，文字一律 --text，不单独取样
# 时间轴和里程碑进度条都换成了 20 支格子，格子是纯色块没有文字，
# 取样的选择器只留真正有字的（按钮、状态、数据行、里程碑脚注）
SELS_QUIT_TODAY = ['.quit-btn', '.quit-btn.undo', '.quit-card .mv-status',
                   '.quit-card .move-lines > span', '.quit-card .move-foot']
# 统计页：勋章墙 + 时段图坐标轴
# v83 起「戒烟汇总」8 张卡也出现在统计页，同一套样式换个页面底，要单独取样
SELS_QUIT_STATS = ['.qmile-i', '.qmile-i b', '.qh-axis', '.cal-summary b',
                   '.qsum small', '.qsum b', '.qsum span']
# 戒烟页（导航在用药后）：汇总卡、买烟记录、月历
# 清债页（v88）。**总览和「我的债」是两个子页，选择器必须分开取**——
# 混成一份的话，总览里永远找不到债务卡、债务页里永远找不到还清日，两边都记「元素缺失」。
SELS_MONEY = ['.money-hero small', '.mh-big', '.mh-sub', '.money-kpi b', '.money-kpi span',
              '.mrow-name', '.mrow-num', '.mrow-at', '.subtab button', '.subtab button.on']
SELS_MONEY_DEBTS = ['.mdebt-tag', '.mdebt-num b', '.mdebt-num span',
                    '.subtab button', '.subtab button.on']
# 计划 / 记录是另外两个子页，选择器同样分开取
SELS_MONEY_PLAN = ['.mstart b', '.mstart span', '.mfield > span', '.mcmp-name',
                   '.mcmp-name i', '.mcmp-cell', '.mtag', '.mtr-ym', '.mtr-left',
                   '.msnow b', '.msnow span']
SELS_MONEY_LOG = ['.mlog-date', '.mlog-name', '.mlog-amt', '.mlog-note']
# 预算子页（v90）：分账图例、每日可花、收入/分类/流水三种行
SELS_MONEY_BUDGET = ['.mbud-li span', '.mbud-li b', '.mbud-net span', '.mbud-net b',
                     '.mbud-net small', '.mdaily b', '.mdaily span', '.msum span', '.msum b',
                     '.minc-name', '.minc-amt', '.mcat-name', '.mcat-bud',
                     '.mspend-date', '.mspend-cat', '.mspend-amt', '.mym b']
# 工具子页（v91）：换算四格、对照表、真实年化、风险体检
SELS_MONEY_TOOLS = ['.mrate-cell small', '.mrate-cell b', '.mtbl-row', '.mtbl-row.head',
                    '.mapr b', '.mapr span', '.mrisk-body b', '.mrisk-body span']
SELS_QUIT_PAGE = ['.qsum small', '.qsum b', '.qsum span',
                  '.qs-head small', '.qs-head span', '.qs-axis span', '.qpack-main b',
                  '.qpack-main small', '.qpack-st', '.pack-cf', '.pack-cf span',
                  '.pack-cf button', '.btn.danger-red', '.qc-day span', '.qc-day b']
# 习惯页：管理行的今日状态灯（v66）
SELS_HABITS_PAGE = ['.habit-today', '.habit-today.ok', '.habit-row-info b', '.habit-row-info small']
# 配置页：自定义通知（v71）。提示框是 --warn 浅底，最容易踩线
# .pc-* 是推送预览里的条目，mock 的 push_preview 返回空数组，这四项永远取不到；
# 留着会让「元素缺失」一直不为 0，把真正的回归信号淹掉。
SELS_CONFIG_PAGE = ['.notice-when', '.notice-text', '.notice-warn',
                    '.notice-row.past .notice-text', '.notice-row.past .notice-when',
                    '.ntf-head b', '.ntf-state', '.ntf-box .muted-sm', '.ics-hint', '.ics-warn',
                    '.pc-sec-head', '.pc-count']
# v87 删掉 mono / clay / forest / cyber 四套皮肤，审计只跑剩下的
skins = ['paper', 'slate', 'neu', 'retro', 'cloud-float', 'cloud-focus']

# 安装提示要出现：未装、未关闭
board['data']['habits'][2]['suggestTime'] = '09:00'

# 让统计页的「环比」那一条出现（.adh-delta）。默认数据里没有上月记录，
# 走的是「上月同期没有用药排期」那个分支，取样会一直报元素缺失。
for m in board['data']['meds']:
    if m['id'] in ('m_long1', 'm_long2'):
        m['startDate'] = '2026-09-01'
for day in range(1, 31):
    ds = '2026-09-%02d' % day
    board['data']['doses'][ds] = {
        'm_long1': {'08:00': {'at': ds + 'T08:00:00+08:00'}},
        'm_long2': {'12:00': {'at': ds + 'T12:00:00+08:00'}},
    }

bad, skipped, missing, checked = [], 0, [], 0
with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)
    for mode in ('light', 'dark'):
        for skin in skins:
            ctx = br.new_context(viewport={'width': 1440, 'height': 950})
            pg = ctx.new_page()
            pg.add_init_script(
                "try{localStorage.setItem('lifeboard.skin','%s');"
                "localStorage.setItem('lifeboard.theme.mode','%s')}catch(e){}" % (skin, mode))
            pg.clock.install(time=datetime(2026, 10, 25, 10, 0, 0))
            pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
            pg.wait_for_timeout(400)
            pg.click('[data-act="cloud-login"]')
            pg.wait_for_timeout(350)
            pg.fill('input[name="email"]', 'test@example.com')
            pg.fill('input[name="password"]', 'test@example.com')
            pg.click('form.modal-card button[type="submit"]')
            pg.wait_for_timeout(2400)

            res = pg.evaluate(JS, SELS_TODAY)
            res += pg.evaluate(JS, SELS_QUIT_TODAY)

            # 常驻卡排序态（v75）：↑↓ 和标题栏那两颗按钮只在排序时出现
            pg.evaluate("() => { const b=document.querySelector('[data-act=\"card-sort\"]'); if(b) b.click(); }")
            pg.wait_for_timeout(600)
            res += pg.evaluate(JS, ['.card-sortbar .csb', '.sec-acts .btn'])
            pg.evaluate("() => { const b=document.querySelector('[data-act=\"card-sort\"]'); if(b) b.click(); }")
            pg.wait_for_timeout(400)
            nav(pg, 'settings')
            pg.wait_for_timeout(500)
            res += pg.evaluate(JS, SELS_SETTINGS)
            nav(pg, 'config')
            pg.wait_for_timeout(900)
            res += pg.evaluate(JS, SELS_CONFIG_PAGE)
            nav(pg, 'habits')
            pg.wait_for_timeout(800)
            res += pg.evaluate(JS, SELS_HABITS_PAGE)
            nav(pg, 'quit')
            pg.wait_for_timeout(800)
            res += pg.evaluate(JS, SELS_QUIT_PAGE)
            nav(pg, 'board')
            pg.wait_for_timeout(900)
            res += pg.evaluate(JS, SELS_BOARD)
            nav(pg, 'money')
            pg.wait_for_timeout(900)
            res += pg.evaluate(JS, SELS_MONEY)
            pg.click('[data-act="subtab"][data-page="money"][data-tab="debts"]')
            pg.wait_for_timeout(500)
            res += pg.evaluate(JS, SELS_MONEY_DEBTS)
            pg.click('[data-act="subtab"][data-page="money"][data-tab="budget"]')
            pg.wait_for_timeout(700)
            res += pg.evaluate(JS, SELS_MONEY_BUDGET)
            pg.click('[data-act="subtab"][data-page="money"][data-tab="plan"]')
            pg.wait_for_timeout(700)
            res += pg.evaluate(JS, SELS_MONEY_PLAN)
            pg.click('[data-act="subtab"][data-page="money"][data-tab="log"]')
            pg.wait_for_timeout(600)
            res += pg.evaluate(JS, SELS_MONEY_LOG)
            pg.click('[data-act="subtab"][data-page="money"][data-tab="tools"]')
            pg.wait_for_timeout(800)
            res += pg.evaluate(JS, SELS_MONEY_TOOLS)
            nav(pg, 'stats')
            pg.wait_for_timeout(800)
            # v84：用药趋势和戒烟分析都藏在分段控件 / 折叠后面，取样前先点开，
            # 否则这两组永远「元素缺失」，真正的回归信号会被淹没。
            if pg.locator('[data-act="stats-med-tab"][data-tab="trend"]').count():
                pg.click('[data-act="stats-med-tab"][data-tab="trend"]')
                pg.wait_for_timeout(400)
            if pg.locator('[data-act="stats-quit-fold"]').count():
                pg.click('[data-act="stats-quit-fold"]')
                pg.wait_for_timeout(500)
            res += pg.evaluate(JS, SELS_STATS)
            res += pg.evaluate(JS, SELS_QUIT_STATS)
            nav(pg, 'calendar')
            pg.wait_for_timeout(900)
            res += pg.evaluate(JS, SELS_CAL_MONTH)
            # 周视图：切过去再取一遍，时间线上的小字最容易踩对比度
            if pg.locator('[data-act="cal-mode"][data-mode="week"]').count():
                pg.click('[data-act="cal-mode"][data-mode="week"]')
                pg.wait_for_timeout(900)
                res += pg.evaluate(JS, SELS_CAL_WEEK)

            for r in res:
                checked += 1
                if r.get('skip'):
                    skipped += 1
                    continue
                if r.get('missing'):
                    missing.append('%s/%s/%s' % (mode, skin, r['sel']))
                    continue
                need = 3.0 if (r['size'] >= 18 or (r['size'] >= 14 and int(r['weight']) >= 700)) else 4.5
                if r['ratio'] < need:
                    bad.append({'mode': mode, 'skin': skin, 'sel': r['sel'],
                                'ratio': r['ratio'], 'need': need, 'size': r['size']})
            ctx.close()
    br.close()

print('检查：%d 皮肤 × 明暗 = %d 组 × %d 个元素（共 %d 次取样）'
      % (len(skins), len(skins) * 2,
         len(SELS_SETTINGS) + len(SELS_TODAY) + len(SELS_STATS)
         + len(SELS_CAL_MONTH) + len(SELS_CAL_WEEK) + len(SELS_MONEY) + len(SELS_MONEY_DEBTS)
         + len(SELS_MONEY_PLAN) + len(SELS_MONEY_LOG)
         + len(SELS_MONEY_BUDGET) + len(SELS_MONEY_TOOLS), checked))
print('跳过（渐变/透明背景）：%d' % skipped)
print('元素缺失：%d %s' % (len(missing), missing[:4]))
print('低于 WCAG AA：%d' % len(bad))
for b in bad[:14]:
    print('   %-5s %-7s %-24s %.2f (需 %.1f) %gpx' % (b['mode'], b['skin'], b['sel'], b['ratio'], b['need'], b['size']))
