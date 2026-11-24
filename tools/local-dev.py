#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""明序 · 本地测试服务器（Local Dev Server）

用途：把**真实的 index.html**（正式代码，不是另写的预览）在本机跑起来，
      并内置一个 mock 的 api.php，让云同步、登录、推送、ICS、邮件、管理后台
      等所有需要后端的功能都能在本地点一遍。

特点：
  * 静态文件直接读项目目录，改代码刷新即生效
  * mock 接口的返回字段严格照 api.php 的真实实现写
  * 数据落盘到 tools/.local-dev-state.json，刷新/重启都不丢
  * service-worker.js 被替换成「自注销 + 清缓存」版本，本地绝不会被旧缓存骗
  * 不发送任何真实邮件 / 企业微信推送（如实返回失败，不假装成功）

用法：
    python tools/local-dev.py                # 启动，默认 8899 端口
    python tools/local-dev.py --port 9000    # 指定端口
    python tools/local-dev.py --reset        # 清空本地数据后启动
"""
import argparse
import json
import os
import re
import secrets
import sys
import threading
import time
from datetime import datetime, timedelta
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_FILE = os.path.join(ROOT, 'tools', '.local-dev-state.json')

SETTINGS_DEFAULT = {
    'registration_open': True,
    'registration_mode': 'invite',      # closed / invite / email
    'invite_code': 'LOCAL-TEST',
    'site_name': '明序（本地测试）',
}

NOTIFY_KINDS = ['med', 'task', 'habit', 'countdown', 'notice', 'debt', 'report']
NOTIFY_KIND_LABEL = {
    'med': '用药提醒', 'task': '待办到点', 'habit': '习惯提醒',
    'countdown': '倒数日', 'notice': '自定义提醒', 'debt': '还款提醒',
    'report': '每日小结',
}
NOTIFY_CHANNELS = {'wecom': '企业微信', 'mail': '邮件'}


def notify_defaults():
    out = {k: {'wecom': True, 'mail': True} for k in NOTIFY_KINDS}
    out['habit'] = {'wecom': True, 'mail': False}
    out['report'] = {'wecom': True, 'mail': False}
    return out


def now_ms():
    return int(time.time() * 1000)


def now_str():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


# ---------------------------------------------------------------- 数据层

class Store:
    """极简 JSON 状态库，带锁。结构对应 MySQL 里的那几张表。"""

    def __init__(self, path):
        self.path = path
        self.lock = threading.RLock()
        self.data = self._load()

    def _blank(self):
        return {
            'users': [
                {
                    'id': 1, 'email': 'test@sl00.top', 'password': 'test@sl00.top',
                    'display_name': '本地测试', 'is_admin': False, 'status': 'active',
                    'created_at': '2026-11-01 10:00:00', 'last_login_at': None,
                    'push_webhook': '', 'push_enabled': 0, 'ics_token': '',
                    'session_epoch': 1,
                    'mail_cfg': {'host': '', 'port': 465, 'secure': 'ssl', 'user': '',
                                 'from': '', 'name': '', 'hasSecret': False,
                                 'enabled': False, 'lastError': '', 'lastTestAt': ''},
                },
                {
                    'id': 2, 'email': 'admin@sl00.top', 'password': 'admin@sl00.top',
                    'display_name': '管理员', 'is_admin': True, 'status': 'active',
                    'created_at': '2026-11-01 10:00:00', 'last_login_at': None,
                    'push_webhook': '', 'push_enabled': 0, 'ics_token': '',
                    'session_epoch': 1,
                    'mail_cfg': {'host': '', 'port': 465, 'secure': 'ssl', 'user': '',
                                 'from': '', 'name': '', 'hasSecret': False,
                                 'enabled': False, 'lastError': '', 'lastTestAt': ''},
                },
            ],
            'boards': {},        # uid -> {data, rev, updated_at}
            'revisions': {},     # uid -> [{id, rev, data, reason, created_at}]
            'push_sent': {},     # uid -> [{key, kind, at, text}]
            'notify': {},        # uid -> {prefs, quiet, report}
            'settings': dict(SETTINGS_DEFAULT),
            'site_mail': {'host': '', 'port': 465, 'secure': 'ssl', 'user': '',
                          'from': '', 'name': '', 'hasSecret': False},
            'sessions': {},      # sid -> uid
        }

    def _load(self):
        try:
            with open(self.path, 'r', encoding='utf-8') as f:
                d = json.load(f)
            base = self._blank()
            base.update(d or {})
            return base
        except Exception:
            return self._blank()

    def flush(self):
        with self.lock:
            tmp = self.path + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=1)
            os.replace(tmp, self.path)

    def reset(self):
        with self.lock:
            self.data = self._blank()
            self.flush()


STORE = Store(STATE_FILE)


def user_by_id(uid):
    for u in STORE.data['users']:
        if int(u['id']) == int(uid):
            return u
    return None


def user_by_email(email):
    e = (email or '').strip().lower()
    for u in STORE.data['users']:
        if u['email'].lower() == e:
            return u
    return None


def public_user(u):
    if not u:
        return None
    return {
        'id': int(u['id']),
        'email': u['email'],
        'display_name': u.get('display_name') or '',
        'is_admin': bool(u.get('is_admin')),
        'status': u.get('status') or 'active',
        'created_at': u.get('created_at') or now_str(),
        'last_login_at': u.get('last_login_at'),
    }


def reg_public():
    mode = STORE.data['settings'].get('registration_mode') or 'closed'
    return {
        'registration_open': mode != 'closed',
        'registration_mode': mode,
        'need_invite': mode == 'invite',
        'need_code': mode == 'email',
        'code_ready': False,     # 本地不发邮件
    }


def notify_state(uid):
    d = STORE.data['notify']
    key = str(uid)
    if key not in d:
        d[key] = {
            'prefs': notify_defaults(),
            'quiet': False,
            'report': {'morning': '08:20', 'noon': '12:30', 'evening': '20:00'},
        }
    return d[key]


def public_mail_cfg(cfg):
    return {
        'host': cfg.get('host', ''), 'port': int(cfg.get('port') or 465),
        'secure': cfg.get('secure', 'ssl'), 'user': cfg.get('user', ''),
        'from': cfg.get('from', ''), 'name': cfg.get('name', ''),
        'hasSecret': bool(cfg.get('hasSecret')), 'enabled': bool(cfg.get('enabled')),
        'lastError': cfg.get('lastError', ''), 'lastTestAt': cfg.get('lastTestAt', ''),
    }


def public_site_mail(cfg):
    return {
        'host': cfg.get('host', ''), 'port': int(cfg.get('port') or 465),
        'secure': cfg.get('secure', 'ssl'), 'user': cfg.get('user', ''),
        'from': cfg.get('from', ''), 'name': cfg.get('name', ''),
        'hasSecret': bool(cfg.get('hasSecret')),
    }


def site_mail_ready():
    c = STORE.data.get('site_mail') or {}
    return bool(c.get('host') and c.get('user') and c.get('from') and c.get('hasSecret'))


# ---------------------------------------------------------------- HTTP

class ApiError(Exception):
    def __init__(self, msg, status=400, code='bad_request'):
        super().__init__(msg)
        self.msg = msg
        self.status = status
        self.code = code


class Handler(SimpleHTTPRequestHandler):
    server_version = 'MingXuLocalDev/1.0'
    protocol_version = 'HTTP/1.1'

    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    # ---- 基础工具 ----
    def log_message(self, fmt, *args):
        # 只记录 api 请求，静态资源不刷屏
        if '/api.php' in (self.path or ''):
            sys.stderr.write('[api] %s %s\n' % (self.command, self.path))

    def _json(self, obj, status=200, headers=None):
        body = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def _text(self, text, ctype='text/plain; charset=utf-8', status=200, headers=None):
        body = text.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def _cookies(self):
        out = {}
        raw = self.headers.get('Cookie') or ''
        for part in raw.split(';'):
            part = part.strip()
            if '=' in part:
                k, v = part.split('=', 1)
                out[k.strip()] = v.strip()
        return out

    def _sid(self):
        return self._cookies().get('sid') or ''

    def _current_user(self):
        sid = self._sid()
        if not sid:
            return None
        uid = STORE.data['sessions'].get(sid)
        if not uid:
            return None
        u = user_by_id(uid)
        if not u or u.get('status') != 'active':
            return None
        return u

    def _body(self):
        try:
            n = int(self.headers.get('Content-Length') or 0)
        except Exception:
            n = 0
        if n <= 0:
            return {}
        raw = self.rfile.read(n)
        try:
            return json.loads(raw.decode('utf-8') or '{}')
        except Exception:
            return {}

    def _require_user(self):
        u = self._current_user()
        if not u:
            raise ApiError('请先登录', 401, 'unauthenticated')
        return u

    def _require_admin(self):
        u = self._require_user()
        if not u.get('is_admin'):
            raise ApiError('需要管理员权限', 403, 'forbidden')
        return u

    # ---- 路由 ----
    def do_GET(self):
        self._dispatch()

    def do_HEAD(self):
        self._dispatch()

    def do_POST(self):
        self._dispatch()

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Content-Length', '0')
        self.end_headers()

    def _dispatch(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path.startswith('/api.php'):
            q = parse_qs(parsed.query)
            action = (q.get('action') or [''])[0]
            if not action and 'ics' in q:
                action = 'ics'
            try:
                self._api(action, q)
            except ApiError as e:
                self._json({'ok': False, 'error': e.msg, 'code': e.code}, e.status)
            except Exception as e:                      # noqa: BLE001
                self._json({'ok': False, 'error': '本地服务器异常：%s' % e,
                            'code': 'local_dev_error'}, 500)
            return

        if path in ('/', '/index.html') and 'autologin=1' in parsed.query:
            # 便于本地测试：带 autologin=1 打开就自动登录为测试账号
            u = user_by_email('test@sl00.top')
            sid = secrets.token_hex(12)
            STORE.data['sessions'][sid] = u['id']
            STORE.flush()
            self.send_response(302)
            self.send_header('Location', '/index.html')
            self.send_header('Set-Cookie', 'sid=%s; Path=/; SameSite=Lax' % sid)
            self.send_header('Content-Length', '0')
            self.end_headers()
            return

        if path == '/service-worker.js':
            # 本地测试一定要避开 SW 缓存：这里返回「清空缓存并注销自己」的 SW
            self._text(
                "/* local dev: 永不缓存，并自动注销 */\n"
                "self.addEventListener('install',e=>self.skipWaiting());\n"
                "self.addEventListener('activate',e=>e.waitUntil((async()=>{\n"
                "  const ks=await caches.keys();\n"
                "  await Promise.all(ks.map(k=>caches.delete(k)));\n"
                "  await self.registration.unregister();\n"
                "})()));\n",
                'application/javascript; charset=utf-8')
            return

        if path == '/__reset':
            STORE.reset()
            self._json({'ok': True, 'msg': '本地数据已清空'})
            return

        # 其余交给静态文件；一律 no-store，避免改了代码看不到
        self._serve_static(path, parsed.query)

    def _serve_static(self, path, query):
        fs_path = self.translate_path(path)
        if os.path.isdir(fs_path):
            idx = os.path.join(fs_path, 'index.html')
            if os.path.isfile(idx):
                fs_path = idx
            else:
                self.send_error(404)
                return
        if not os.path.isfile(fs_path):
            self.send_error(404, 'Not Found')
            return

        ctype = self.guess_type(fs_path)
        try:
            with open(fs_path, 'rb') as f:
                body = f.read()
        except Exception:
            self.send_error(500)
            return
        self.send_response(200)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store, must-revalidate')
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    # ---- mock api ----
    def _api(self, action, q):
        st = STORE.data

        if action == 'status':
            self._json({'ok': True, 'installed': True})
            return

        if action == 'me':
            u = self._current_user()
            self._json(dict({
                'ok': True,
                'user': public_user(u),
                'csrf': secrets.token_hex(16),
                'site_name': st['settings'].get('site_name', '明序'),
            }, **reg_public()))
            return

        if action == 'login':
            body = self._body()
            email = (body.get('email') or '').strip().lower()
            pwd = body.get('password') or ''
            u = user_by_email(email)
            if not u or u.get('password') != pwd:
                time.sleep(0.2)
                raise ApiError('邮箱或密码不正确', 401, 'bad_credentials')
            if u.get('status') != 'active':
                raise ApiError('这个账号已被管理员停用', 403, 'account_disabled')
            u['session_epoch'] = int(u.get('session_epoch') or 1) + 1
            u['last_login_at'] = now_str()
            sid = secrets.token_hex(12)
            st['sessions'][sid] = u['id']
            STORE.flush()
            payload = dict({
                'ok': True,
                'user': public_user(u),
                'csrf': secrets.token_hex(16),
                'site_name': st['settings'].get('site_name', '明序'),
            }, **reg_public())
            self._json(payload, headers={
                'Set-Cookie': 'sid=%s; Path=/; SameSite=Lax' % sid})
            return

        if action == 'logout':
            sid = self._sid()
            if sid in st['sessions']:
                del st['sessions'][sid]
                STORE.flush()
            self._json({'ok': True}, headers={
                'Set-Cookie': 'sid=; Path=/; Max-Age=0'})
            return

        if action == 'register_code':
            raise ApiError('本地测试服务器不发邮件，无法走邮箱验证注册；'
                           '请改用邀请码注册（邀请码 LOCAL-TEST）', 400, 'not_email_mode')

        if action == 'register':
            body = self._body()
            email = (body.get('email') or '').strip().lower()
            pwd = body.get('password') or ''
            name = (body.get('display_name') or '').strip()
            invite = (body.get('invite_code') or '').strip()
            mode = st['settings'].get('registration_mode') or 'closed'
            if mode == 'closed':
                raise ApiError('注册已关闭', 403, 'registration_closed')
            if mode == 'invite' and invite != st['settings'].get('invite_code'):
                raise ApiError('邀请码不正确', 400, 'bad_invite')
            if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email or ''):
                raise ApiError('请输入有效的邮箱地址', 400, 'bad_email')
            if len(pwd) < 8:
                raise ApiError('密码至少 8 位', 400, 'bad_password')
            if user_by_email(email):
                raise ApiError('这个邮箱已经注册过了，直接登录即可', 409, 'email_exists')
            new_id = max([int(x['id']) for x in st['users']] + [0]) + 1
            u = {
                'id': new_id, 'email': email, 'password': pwd,
                'display_name': name or email.split('@')[0],
                'is_admin': False, 'status': 'active', 'created_at': now_str(),
                'last_login_at': now_str(), 'push_webhook': '', 'push_enabled': 0,
                'ics_token': '', 'session_epoch': 1,
                'mail_cfg': {'host': '', 'port': 465, 'secure': 'ssl', 'user': '',
                             'from': '', 'name': '', 'hasSecret': False,
                             'enabled': False, 'lastError': '', 'lastTestAt': ''},
            }
            st['users'].append(u)
            sid = secrets.token_hex(12)
            st['sessions'][sid] = new_id
            STORE.flush()
            self._json(dict({
                'ok': True, 'user': public_user(u),
                'csrf': secrets.token_hex(16),
                'site_name': st['settings'].get('site_name', '明序'),
            }, **reg_public()), headers={
                'Set-Cookie': 'sid=%s; Path=/; SameSite=Lax' % sid})
            return

        if action == 'password_forgot':
            self._json({'ok': True})
            return

        if action == 'password_reset':
            body = self._body()
            u = user_by_email(body.get('email') or '')
            pwd = body.get('password') or ''
            if not u:
                raise ApiError('重置链接无效或已过期', 400, 'bad_token')
            if len(pwd) < 8:
                raise ApiError('密码至少 8 位', 400, 'bad_password')
            u['password'] = pwd
            u['session_epoch'] = int(u.get('session_epoch') or 1) + 1
            STORE.flush()
            self._json({'ok': True})
            return

        if action == 'change_password':
            u = self._require_user()
            body = self._body()
            if (body.get('current_password') or '') != u.get('password'):
                raise ApiError('当前密码不正确', 400, 'bad_current_password')
            new = body.get('new_password') or ''
            if len(new) < 8:
                raise ApiError('新密码至少 8 位', 400, 'bad_password')
            u['password'] = new
            u['session_epoch'] = int(u.get('session_epoch') or 1) + 1
            STORE.flush()
            self._json({'ok': True})
            return

        if action == 'profile_save':
            u = self._require_user()
            body = self._body()
            name = (body.get('display_name') or '').strip()
            email = (body.get('email') or '').strip().lower()
            if len(name) > 40:
                raise ApiError('名称最多 40 个字符', 400, 'bad_display_name')
            if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email or ''):
                raise ApiError('邮箱格式不正确', 400, 'bad_email')
            other = user_by_email(email)
            if other and int(other['id']) != int(u['id']):
                raise ApiError('这个邮箱已被其他账号使用', 409, 'email_taken')
            u['display_name'] = name
            u['email'] = email
            STORE.flush()
            self._json({'ok': True, 'user': public_user(u)})
            return

        if action == 'load':
            u = self._require_user()
            b = st['boards'].get(str(u['id']))
            if not b:
                self._json({'ok': True, 'data': None, 'rev': 0, 'updated_at': 0})
                return
            self._json({'ok': True, 'data': b['data'], 'rev': b['rev'],
                        'updated_at': b['updated_at']})
            return

        if action in ('save', 'force'):
            u = self._require_user()
            body = self._body()
            data = body.get('data')
            if not isinstance(data, dict) or 'habits' not in data or 'tasks' not in data:
                raise ApiError('数据格式不正确', 400, 'bad_data')
            key = str(u['id'])
            cur = st['boards'].get(key)
            base_rev = -1 if action == 'force' else int(body.get('base_rev') or 0)
            if cur and action != 'force' and base_rev != int(cur['rev']):
                self._json({
                    'ok': False, 'error': '云端有更新', 'code': 'conflict',
                    'remote': {'data': cur['data'], 'rev': cur['rev'],
                               'updated_at': cur['updated_at']},
                }, 409)
                return
            new_rev = (int(cur['rev']) + 1) if cur else 1
            if cur:
                revs = st['revisions'].setdefault(key, [])
                revs.insert(0, {
                    'id': int(time.time() * 1000) % 10 ** 9,
                    'rev': int(cur['rev']), 'data': cur['data'],
                    'reason': 'save', 'created_at': now_ms(),
                })
                del revs[20:]
            st['boards'][key] = {'data': data, 'rev': new_rev, 'updated_at': now_ms()}
            STORE.flush()
            self._json({'ok': True, 'rev': new_rev,
                        'updated_at': st['boards'][key]['updated_at']})
            return

        if action == 'history':
            u = self._require_user()
            revs = st['revisions'].get(str(u['id']), [])
            rid = int((q.get('id') or ['0'])[0] or 0)
            if rid:
                for r in revs:
                    if int(r['id']) == rid:
                        self._json({'ok': True, 'item': r})
                        return
                raise ApiError('历史版本不存在', 404, 'revision_not_found')
            items = [{'id': r['id'], 'rev': r['rev'], 'reason': r['reason'],
                      'created_at': r['created_at'],
                      'bytes': len(json.dumps(r['data'], ensure_ascii=False))}
                     for r in revs]
            self._json({'ok': True, 'items': items})
            return

        if action == 'restore':
            u = self._require_user()
            body = self._body()
            rid = int(body.get('id') or 0)
            revs = st['revisions'].get(str(u['id']), [])
            target = next((r for r in revs if int(r['id']) == rid), None)
            if not target:
                raise ApiError('历史版本不存在', 404, 'revision_not_found')
            key = str(u['id'])
            cur = st['boards'].get(key) or {'data': {}, 'rev': 0, 'updated_at': 0}
            new_rev = int(cur['rev']) + 1
            st['boards'][key] = {'data': target['data'], 'rev': new_rev,
                                 'updated_at': now_ms()}
            STORE.flush()
            self._json({'ok': True, 'data': target['data'], 'rev': new_rev,
                        'updated_at': st['boards'][key]['updated_at']})
            return

        if action == 'push_status':
            u = self._require_user()
            sent = st['push_sent'].get(str(u['id']), [])
            today = datetime.now().strftime('%Y-%m-%d')
            sent_today = len([x for x in sent if str(x.get('at', '')).startswith(today)])
            self._json({
                'ok': True,
                'enabled': int(u.get('push_enabled') or 0) == 1,
                'webhook': u.get('push_webhook') or '',
                'sent_today': sent_today,
                'last_sent': sent[0]['at'] if sent else '',
                'recent': sent[:10],
            })
            return

        if action == 'push_save':
            u = self._require_user()
            body = self._body()
            url = (body.get('webhook') or '').strip()
            if url and 'qyapi.weixin.qq.com' not in url:
                raise ApiError('这条地址不像是企业微信机器人。正确形式是 '
                               'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=...',
                               400, 'bad_webhook')
            u['push_webhook'] = url
            u['push_enabled'] = 1 if (body.get('enabled') and url) else 0
            STORE.flush()
            self._json({'ok': True, 'enabled': bool(u['push_enabled'])})
            return

        if action == 'push_off':
            u = self._require_user()
            u['push_enabled'] = 0
            STORE.flush()
            self._json({'ok': True})
            return

        if action == 'push_test':
            u = self._require_user()
            if not (u.get('push_webhook') or ''):
                raise ApiError('还没填推送地址', 400, 'no_webhook')
            raise ApiError('本地测试服务器不会真的发企业微信消息（避免误发到你的群）',
                           502, 'push_failed')

        if action == 'push_preview':
            self._require_user()
            self._json({'ok': True,
                        'date': datetime.now().strftime('%Y-%m-%d'),
                        'items': []})
            return

        if action == 'ics_status':
            u = self._require_user()
            tok = u.get('ics_token') or ''
            self._json({'ok': True, 'url': ('/api.php?ics=%s.ics' % tok) if tok else None})
            return

        if action == 'ics_reset':
            u = self._require_user()
            u['ics_token'] = secrets.token_hex(32)
            STORE.flush()
            self._json({'ok': True, 'url': '/api.php?ics=%s.ics' % u['ics_token']})
            return

        if action == 'ics':
            tok = (q.get('token') or q.get('ics') or [''])[0]
            if tok.endswith('.ics'):
                tok = tok[:-4]
            u = next((x for x in st['users'] if x.get('ics_token') == tok and tok), None)
            if not u:
                raise ApiError('订阅地址无效', 404, 'bad_token')
            ics = ("BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//MingXu Local Dev//CN\r\n"
                   "CALSCALE:GREGORIAN\r\nX-WR-CALNAME:明序（本地测试）\r\n"
                   "BEGIN:VEVENT\r\n"
                   "UID:localdev-%s@mingxu\r\n"
                   "DTSTAMP:%s\r\n"
                   "DTSTART:%sT090000\r\n"
                   "DTEND:%sT091000\r\n"
                   "SUMMARY:本地测试日历源（占位）\r\n"
                   "DESCRIPTION:本地开发服务器不生成真实提醒，仅验证订阅地址可用。\r\n"
                   "END:VEVENT\r\nEND:VCALENDAR\r\n") % (
                int(u['id']), datetime.utcnow().strftime('%Y%m%dT%H%M%SZ'),
                datetime.now().strftime('%Y%m%d'), datetime.now().strftime('%Y%m%d'))
            self._text(ics, 'text/calendar; charset=utf-8')
            return

        if action == 'mail_status':
            u = self._require_user()
            self._json({'ok': True, 'config': public_mail_cfg(u.get('mail_cfg') or {}),
                        'crypto_ready': True, 'recipient': u['email']})
            return

        if action == 'mail_save':
            u = self._require_user()
            body = self._body()
            cfg = u.setdefault('mail_cfg', {})
            for k in ('host', 'secure', 'user', 'from', 'name'):
                if k in body:
                    cfg[k] = body.get(k) or ''
            if 'port' in body:
                try:
                    cfg['port'] = int(body.get('port') or 465)
                except Exception:
                    cfg['port'] = 465
            if body.get('secret'):
                cfg['hasSecret'] = True
            cfg['enabled'] = bool(body.get('enabled'))
            STORE.flush()
            self._json({'ok': True, 'config': public_mail_cfg(cfg)})
            return

        if action == 'mail_off':
            u = self._require_user()
            cfg = u.setdefault('mail_cfg', {})
            cfg['enabled'] = False
            STORE.flush()
            self._json({'ok': True})
            return

        if action == 'mail_test':
            self._require_user()
            raise ApiError('本地测试服务器不会真的发邮件（避免用你的授权码发信）',
                           400, 'mail_send_failed')

        if action == 'site_mail_status':
            u = self._require_admin()
            self._json({'ok': True, 'config': public_site_mail(st['site_mail']),
                        'ready': site_mail_ready(), 'admin_email': u['email']})
            return

        if action == 'site_mail_save':
            self._require_admin()
            body = self._body()
            cfg = st['site_mail']
            for k in ('host', 'secure', 'user', 'from', 'name'):
                if k in body:
                    cfg[k] = body.get(k) or ''
            if 'port' in body:
                try:
                    cfg['port'] = int(body.get('port') or 465)
                except Exception:
                    cfg['port'] = 465
            if body.get('secret'):
                cfg['hasSecret'] = True
            STORE.flush()
            self._json({'ok': True, 'config': public_site_mail(cfg),
                        'ready': site_mail_ready()})
            return

        if action == 'site_mail_test':
            self._require_admin()
            raise ApiError('本地测试服务器不会真的发邮件', 400, 'site_mail_test_failed')

        if action == 'notify_prefs':
            u = self._require_user()
            ns = notify_state(u['id'])
            self._json({'ok': True, 'kinds': NOTIFY_KIND_LABEL,
                        'channels': NOTIFY_CHANNELS,
                        'prefs': ns['prefs'], 'quiet': ns['quiet'],
                        'report': ns['report']})
            return

        if action == 'notify_prefs_save':
            u = self._require_user()
            body = self._body()
            ns = notify_state(u['id'])
            prefs = notify_defaults()
            inp = body.get('prefs') or {}
            for kind, row in prefs.items():
                for ch in row:
                    if isinstance(inp.get(kind), dict) and ch in inp[kind]:
                        prefs[kind][ch] = bool(inp[kind][ch])
            ns['prefs'] = prefs
            ns['quiet'] = bool(body.get('quiet'))
            rep = body.get('report') or {}
            for k in ('morning', 'noon', 'evening'):
                if k in rep:
                    v = str(rep.get(k) or '')
                    if v == '' or re.match(r'^([01]\d|2[0-3]):[0-5]\d$', v):
                        ns['report'][k] = v
            STORE.flush()
            self._json({'ok': True, 'prefs': ns['prefs'], 'quiet': ns['quiet'],
                        'report': ns['report']})
            return

        if action == 'admin_users':
            self._require_admin()
            self._json({'ok': True,
                        'users': [public_user(x) for x in st['users']]})
            return

        if action == 'admin_user_update':
            admin = self._require_admin()
            body = self._body()
            tid = int(body.get('id') or 0)
            act = body.get('action') or ''
            val = str(body.get('value') or '')
            t = user_by_id(tid)
            if not t:
                raise ApiError('用户不存在', 404, 'not_found')
            if act == 'reset_password':
                if len(val) < 8:
                    raise ApiError('新密码至少 8 位', 400, 'bad_password')
                t['password'] = val
                t['session_epoch'] = int(t.get('session_epoch') or 1) + 1
                STORE.flush()
                self._json({'ok': True, 'user': public_user(t)})
                return
            if act == 'set_status':
                status = 'disabled' if val == 'disabled' else 'active'
                if int(t['id']) == int(admin['id']) and status == 'disabled':
                    raise ApiError('不能停用自己的管理员账号', 400, 'cannot_disable_self')
                t['status'] = status
                t['session_epoch'] = int(t.get('session_epoch') or 1) + 1
                STORE.flush()
                self._json({'ok': True, 'user': public_user(t)})
                return
            raise ApiError('未知的用户操作', 400, 'bad_action')

        if action == 'admin_settings':
            self._require_admin()
            s = st['settings']
            self._json({'ok': True, 'settings': {
                'registration_open': s.get('registration_mode') != 'closed',
                'registration_mode': s.get('registration_mode'),
                'site_mail_ready': site_mail_ready(),
                'invite_code': s.get('invite_code', ''),
                'site_name': s.get('site_name', '明序'),
            }})
            return

        if action == 'admin_settings_save':
            self._require_admin()
            body = self._body()
            s = st['settings']
            mode = body.get('registration_mode') or ''
            if not mode:
                mode = 'invite' if body.get('registration_open') else 'closed'
            if mode not in ('closed', 'invite', 'email'):
                raise ApiError('注册方式不合法', 400, 'bad_mode')
            if mode == 'email' and not site_mail_ready():
                raise ApiError('邮箱注册需要先配好站点邮件', 400, 'site_mail_not_ready')
            s['registration_mode'] = mode
            if 'invite_code' in body:
                s['invite_code'] = str(body.get('invite_code') or '')
            if 'site_name' in body:
                s['site_name'] = str(body.get('site_name') or '明序')[:40]
            s['registration_open'] = mode != 'closed'
            STORE.flush()
            self._json({'ok': True, 'settings': {
                'registration_open': s['registration_open'],
                'registration_mode': s['registration_mode'],
                'site_mail_ready': site_mail_ready(),
                'invite_code': s['invite_code'],
                'site_name': s['site_name'],
            }})
            return

        # 未实现的 action：明确告知，而不是假装成功
        raise ApiError('本地测试服务器还没实现这个接口：%s' % (action or '(空)'),
                       501, 'not_implemented')


def pick_port(start):
    import socket
    for p in range(start, start + 30):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(('127.0.0.1', p))
                return p
            except OSError:
                continue
    raise SystemExit('找不到空闲端口')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=8899)
    ap.add_argument('--reset', action='store_true', help='清空本地数据后启动')
    args = ap.parse_args()

    if args.reset and os.path.isfile(STATE_FILE):
        os.remove(STATE_FILE)
        STORE.__init__(STATE_FILE)

    port = pick_port(args.port)
    srv = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    srv.daemon_threads = True
    print('=' * 56)
    print('  明序 · 本地测试服务器')
    print('  打开： http://127.0.0.1:%d/' % port)
    print('  自动登录： http://127.0.0.1:%d/index.html?autologin=1' % port)
    print('  测试账号： test@sl00.top / test@sl00.top')
    print('  管理员：   admin@sl00.top / admin@sl00.top')
    print('  邀请码：   LOCAL-TEST')
    print('  数据文件： %s' % STATE_FILE)
    print('  清空数据： 访问 /__reset')
    print('=' * 56)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print('\n已停止')


if __name__ == '__main__':
    main()
