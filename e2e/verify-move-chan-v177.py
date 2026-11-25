# -*- coding: utf-8 -*-
"""v177 运动提醒渠道验证：

1. 运动页的「运动提醒」板块**不再**出现渠道多选（渠道只在新建/编辑运动弹窗里选）
2. 弹窗里勾选渠道时，当场检测能力并给出准确提示：
   * 浏览器通知：看 Notification.permission（granted / denied / default）
   * 企业微信：看 push_status 的 enabled + webhook
   * 邮件：看 mail_status 的 enabled + host + user + hasSecret
3. 在页面保存提醒设置，**不会**把弹窗里选好的 notifyChannels 冲掉
"""
import http.server
import json
import secrets
import socketserver
import sys
import threading
from datetime import datetime

from playwright.sync_api import sync_playwright

DOC = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo'
USER = {'id': 1, 'email': 'test@example.com', 'display_name': '测试', 'is_admin': False}
sessions = {}
D = '2026-10-24'

PASS = 0
FAIL = 0
FAILS = []


def chk(name, ok, detail=''):
    global PASS, FAIL
    if ok:
        PASS += 1
        print('  [OK] %s' % name)
    else:
        FAIL += 1
        FAILS.append((name, detail))
        print('  [FAIL] %s  << %s' % (name, detail))


# 由测试用例切换的「渠道配置状态」
CFG = {'push_enabled': False, 'webhook': '', 'mail_enabled': False,
       'mail_host': '', 'mail_user': '', 'mail_secret': False}

HABITS = [
    {'id': 'h_med', 'name': '用药', 'icon': '💊', 'type': 'build', 'target': 1, 'unit': '次',
     'color': '#2f6f5e', 'note': '', 'createdAt': '2026-09-01T08:00:00Z', 'pinned': True, 'med': True},
    {'id': 'h_water', 'name': '喝水', 'icon': '💧', 'type': 'build', 'target': 9, 'unit': '杯',
     'color': '#4c7f96', 'note': '', 'createdAt': '2026-09-01T08:00:00Z', 'pinned': True},
    {'id': 'h_move', 'name': '运动', 'icon': '🏃', 'type': 'build', 'target': 1, 'unit': '次',
     'color': '#b5733f', 'note': '', 'createdAt': '2026-09-01T08:00:00Z', 'pinned': True},
    {'id': 'h_breathe', 'name': '478呼吸法', 'icon': '🌬️', 'type': 'build', 'target': 1, 'unit': '组',
     'color': '#5b8f8a', 'note': '', 'createdAt': '2026-09-01T08:00:00Z', 'pinned': True, 'optional': True},
    {'id': 'h_drink', 'name': '戒烟', 'icon': '🚭', 'type': 'smoke', 'target': 1, 'unit': '次',
     'color': '#7a8471', 'note': '', 'createdAt': '2026-09-01T08:00:00Z', 'pinned': True},
]

board = {'data': {
    'version': 2, 'schemaVersion': 2, 'view': 'today',
    'habits': HABITS,
    'modules': {'move': {
        'on': True, 'name': '运动', 'icon': '🏃', 'color': '#b5733f', 'note': '',
        'unit': '次', 'times': 1,
        'sports': [{'key': 'steps', 'tIdx': 0, 'tVal': 10000, 'freqKind': 'daily', 'freqN': 1,
                    'weekSel': [0, 1, 2, 3, 4, 5, 6], 'recMode': 'manual', 'fixedSteps': 1000,
                    'fields': [], 'strokePick': ''}],
        'records': [],
        'notifyChannels': ['browser'], 'notify': True,
        'notifyScenes': {'steps': True, 'plan': True, 'week': True},
        'suggestTime': '', 'notifyFreq': 'daily', 'notifyWeekday': 1, 'notifyMonthday': 1,
        'notifyNote': '', 'createdAt': '2026-09-01T08:00:00Z', 'updatedAt': '2026-10-01T08:00:00Z',
    }},
    'modulesAt': 0,
    'checks': {}, 'skips': {}, 'notes': {}, 'moods': {}, 'events': [],
    'meds': [], 'doses': {}, 'bodyProfile': {'age': 30, 'height': 170},
    'weights': [], 'essays': [], 'tasks': [], 'money': {}, 'quit': {},
}, 'rev': 3}


class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=DOC, **kw)

    def log_message(self, *a):
        pass

    def _j(self, obj, status=200, eh=None):
        b = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(b)))
        self.send_header('Cache-Control', 'no-store')
        for k, v in (eh or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(b)

    def _sid(self):
        for p in (self.headers.get('Cookie', '') or '').split(';'):
            p = p.strip()
            if p.startswith('sid='):
                return p[4:]
        return ''

    def do_GET(self):
        if self.path.startswith('/api.php'):
            a = self.path.split('action=')[-1].split('&')[0]
            if a == 'status':
                self._j({'ok': True, 'installed': True})
            elif a == 'me':
                self._j({'ok': True, 'user': sessions.get(self._sid()), 'csrf': 'x',
                         'registration_open': False, 'registration_mode': 'closed',
                         'need_invite': False, 'need_code': False, 'code_ready': False})
            elif a == 'push_status':
                self._j({'ok': True, 'enabled': CFG['push_enabled'], 'webhook': CFG['webhook'],
                         'sent_today': 0, 'last_sent': '', 'recent': []})
            elif a == 'push_preview':
                self._j({'ok': True, 'date': D, 'items': []})
            elif a == 'mail_status':
                self._j({'ok': True, 'crypto_ready': True, 'recipient': 'test@example.com',
                         'config': {'host': CFG['mail_host'], 'port': 465, 'secure': 'ssl',
                                    'user': CFG['mail_user'], 'from': CFG['mail_from'] if 'mail_from' in CFG else CFG['mail_user'],
                                    'name': '测试', 'hasSecret': CFG['mail_secret'],
                                    'enabled': CFG['mail_enabled'], 'lastError': '', 'lastTestAt': ''}})
            elif a == 'ics_status':
                self._j({'ok': True, 'url': None})
            elif a == 'load':
                self._j({'ok': True, 'data': board['data'], 'rev': board['rev'],
                         'updated_at': 1792813000000})
            else:
                self._j({'ok': False, 'error': '?'}, 404)
        else:
            super().do_GET()

    def do_POST(self):
        if self.path.startswith('/api.php'):
            a = self.path.split('action=')[-1].split('&')[0]
            n = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(n) or b'{}')
            if a == 'login':
                sid = secrets.token_hex(8)
                sessions[sid] = USER
                self._j({'ok': True, 'user': USER, 'csrf': 'x', 'registration_open': False},
                        eh={'Set-Cookie': 'sid=' + sid + '; Path=/'})
            elif a in ('save', 'force'):
                board['data'] = body['data']
                board['rev'] += 1
                self._j({'ok': True, 'rev': board['rev'], 'updated_at': 1792813000000})
            else:
                self._j({'ok': False, 'error': '?'}, 404)
        else:
            self.send_response(405)
            self.end_headers()


class TS(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


srv = TS(('127.0.0.1', 0), H)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()


def nav(pg, v):
    pg.evaluate("v => { const b=document.querySelector('[data-nav=\"'+v+'\"]'); if(b) b.click(); }", v)
    pg.wait_for_timeout(450)


def open_modal(pg):
    pg.click('[data-act="move-new"]')
    pg.wait_for_timeout(400)


def click_chan(pg, val):
    """点渠道卡片本身（input 被样式隐藏，且弹窗变长后要先滚到可视区）。"""
    card = pg.locator('#move-sport-body .sp-chan-opt',
                      has=pg.locator('input[value="%s"]' % val)).first
    card.scroll_into_view_if_needed()
    pg.wait_for_timeout(200)
    card.click()
    pg.wait_for_timeout(500)
    return pg.inner_text('#move-sport-body #sp-chan-tip').strip()


def close_modal(pg):
    pg.click('[data-act="close-modal"]')
    pg.wait_for_timeout(250)


with sync_playwright() as pw:
    br = pw.chromium.launch(channel='chrome')
    ctx = br.new_context(viewport={'width': 1440, 'height': 1000})
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))

    pg.clock.install(time=datetime(2026, 10, 24, 20, 0, 0))
    pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
    pg.wait_for_timeout(600)
    pg.click('[data-act="cloud-login"]')
    pg.wait_for_timeout(400)
    pg.fill('input[name="email"]', 'test@example.com')
    pg.fill('input[name="password"]', 'test@example.com')
    pg.click('form.modal-card button[type="submit"]')
    pg.wait_for_timeout(2800)

    nav(pg, 'move')

    print('\n===== 1. 页面上的重复渠道区已删除 =====')
    page_txt = pg.inner_text('.move-page')
    chk('页面仍有「运动提醒」板块', '运动提醒' in page_txt)
    chk('页面不再有渠道勾选框', pg.locator('#move-notify-form [name="channels"]').count() == 0,
        'count=%d' % pg.locator('#move-notify-form [name="channels"]').count())
    chk('页面不再出现「提醒渠道（可多选）」标题', '提醒渠道（可多选）' not in page_txt)
    chk('页面仍有「提醒场景」三个开关', pg.locator('#move-notify-form [name="sceneSteps"]').count() == 1
        and pg.locator('#move-notify-form [name="sceneWeek"]').count() == 1)

    print('\n===== 2. 未配置时勾选 → 提示去配置 =====')
    CFG.update({'push_enabled': False, 'webhook': '', 'mail_enabled': False,
                'mail_host': '', 'mail_user': '', 'mail_secret': False})
    open_modal(pg)
    t_pre = pg.inner_text('#move-sport-body #sp-chan-tip').strip()
    chk('一打开就预检浏览器渠道状态',
        ('浏览器通知' in t_pre) and ('还没开启' in t_pre or '拦截' in t_pre or '不支持' in t_pre), t_pre)
    t_wecom = click_chan(pg, 'wecom')
    chk('企微未配置 → 逐条提示里出现企微', ('企业微信群' in t_wecom and '还没配置' in t_wecom and '配置' in t_wecom), t_wecom)
    t_mail = click_chan(pg, 'mail')
    chk('邮箱未配置 → 逐条提示里出现邮件', ('邮件通知' in t_mail and '还没配置' in t_mail), t_mail)
    # v180 核心：三个都勾、都未配置时，必须三条都列出来，不能只报一条
    all_tip = pg.inner_text('#move-sport-body #sp-chan-tip')
    chk('三条渠道状态逐个列出', ('浏览器通知' in all_tip and '企业微信群' in all_tip and '邮件通知' in all_tip), all_tip)
    chk('正好 3 行状态', len([l for l in all_tip.split('\n') if l.strip()]) == 3, all_tip)
    close_modal(pg)

    print('\n===== 3. 已配置时勾选 → 提示服务正常 =====')
    CFG.update({'push_enabled': True,
                'webhook': 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test',
                'mail_enabled': True, 'mail_host': 'smtp.qq.com',
                'mail_user': 'test@example.com', 'mail_secret': True})
    open_modal(pg)
    t_wecom2 = click_chan(pg, 'wecom')
    chk('企微已配置 → 服务正常', '服务正常' in t_wecom2, t_wecom2)
    t_mail2 = click_chan(pg, 'mail')
    chk('邮箱已配置 → 服务正常', '服务正常' in t_mail2, t_mail2)
    close_modal(pg)

    print('\n===== 4. 浏览器通知已授权 → 服务正常 =====')
    ctx.grant_permissions(['notifications'])
    open_modal(pg)
    t_pre2 = pg.inner_text('#move-sport-body #sp-chan-tip').strip()
    chk('已授权 → 预检显示服务正常', '服务正常' in t_pre2, t_pre2)
    close_modal(pg)

    print('\n===== 5. 只差授权码也算未配置完整 =====')
    CFG.update({'mail_secret': False})
    open_modal(pg)
    t_mail3 = click_chan(pg, 'mail')
    chk('邮箱缺授权码 → 未配置', '还没配置邮箱与授权码' in t_mail3, t_mail3)
    close_modal(pg)

    print('\n===== 6. 弹窗选的渠道不会被页面保存冲掉 =====')
    CFG.update({'mail_secret': True})
    open_modal(pg)
    click_chan(pg, 'mail')                       # 勾上邮件
    pg.click('#move-sport-form button[type="submit"]')
    pg.wait_for_timeout(1500)
    # v178 起渠道按「每个运动」自己存（sports[].channels），不再只存模块级
    sps = board['data']['modules']['move'].get('sports') or []
    got = sps[-1].get('channels') if sps else None
    chk('保存运动后该运动的 channels 含 mail', isinstance(got, list) and 'mail' in got, str(got))
    # 页面上改提醒场景并保存
    pg.click('#move-notify-form [name="sceneWeek"]')
    pg.click('#move-notify-form button[type="submit"]')
    pg.wait_for_timeout(1400)
    sps2 = board['data']['modules']['move'].get('sports') or []
    got2 = sps2[-1].get('channels') if sps2 else None
    chk('页面保存提醒设置后该运动的 channels 仍含 mail',
        isinstance(got2, list) and 'mail' in got2, str(got2))

    chk('全流程无 JS 异常', not errs, str(errs[:2]))
    br.close()

srv.shutdown()
print('\n============================================================')
print('v177 渠道检测：%d 通过 / %d 失败' % (PASS, FAIL))
if FAILS:
    for n, d in FAILS:
        print('  - %s | %s' % (n, d))
sys.exit(1 if FAIL else 0)
