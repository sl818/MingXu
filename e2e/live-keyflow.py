"""线上自检 - 关键链路（修正版）
修正点：① 接管原生 confirm 弹窗；② 导出/登出前先回到设置页；③ 先清理上一轮残留的测试待办。
"""
import json
from playwright.sync_api import sync_playwright

BASE = 'https://todo.csl88.top'
EMAIL = 'test@sl00.top'
PWD = 'test@sl00.top'
MARK = '【自检临时】'

steps, errors = [], []


def rec(name, ok, detail=''):
    steps.append({'name': name, 'ok': bool(ok), 'detail': detail})
    print(('PASS  ' if ok else 'FAIL  ') + name + (('  | ' + detail) if detail else ''))


def purge(pg, tag):
    """删除所有标题含 tag 的待办：卡片 → 编辑(✎) → 弹窗内「删除」→ confirm
    返回剩余数量"""
    n0 = pg.locator(f'.task:has-text("{tag}")').count()
    for _ in range(n0 + 2):
        cards = pg.locator(f'.task:has-text("{tag}")')
        if cards.count() == 0:
            break
        card = cards.first
        card.hover(); pg.wait_for_timeout(300)
        ed = card.locator('[data-act="task-edit"]')
        if ed.count() == 0:
            break
        ed.first.click(); pg.wait_for_timeout(900)
        dele = pg.locator('.modal-card [data-act="task-del"]')
        if dele.count() == 0:
            break
        dele.first.click(); pg.wait_for_timeout(1800)
        pg.wait_for_timeout(600)
    return pg.locator(f'.task:has-text("{tag}")').count()


def close_all_modals(pg):
    """彻底关闭弹窗：先点 close-modal，再 Escape 兜底"""
    for _ in range(3):
        if pg.locator('.modal-card').count() == 0:
            return True
        btn = pg.locator('[data-act="close-modal"]')
        if btn.count() > 0:
            try:
                btn.first.click(timeout=3000); pg.wait_for_timeout(600); continue
            except Exception:
                pass
        try:
            pg.keyboard.press('Escape'); pg.wait_for_timeout(600)
        except Exception:
            pass
    return pg.locator('.modal-card').count() == 0


with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)
    ctx = br.new_context(viewport={'width': 1440, 'height': 900}, accept_downloads=True)
    pg = ctx.new_page()
    pg.on('pageerror', lambda e: errors.append(str(e)[:200]))
    pg.on('console', lambda m: errors.append(m.text[:200]) if m.type == 'error' else None)
    # 关键：自动接受原生 confirm
    pg.on('dialog', lambda d: d.accept())

    pg.goto(BASE, wait_until='networkidle'); pg.wait_for_timeout(1000)
    pg.click('[data-act="cloud-login"]'); pg.wait_for_timeout(600)
    pg.fill('input[name="email"]', EMAIL); pg.fill('input[name="password"]', PWD)
    pg.click('form.modal-card button[type="submit"]'); pg.wait_for_timeout(4000)

    # ---------- 0. 清理残留 ----------
    pg.click('.nav-item[data-nav="board"]'); pg.wait_for_timeout(1400)
    left = purge(pg, MARK)
    rec('清理历史测试数据', left == 0, f'残留 {left} 条' if left else '无残留')

    # ---------- 1. 待办增删 ----------
    try:
        before = pg.locator('.task').count()
        pg.click('[data-act="task-new"]'); pg.wait_for_timeout(700)
        pg.fill('form.modal-card input[name="title"]', MARK + '功能自检')
        pg.click('form.modal-card button[type="submit"]'); pg.wait_for_timeout(2200)
        created = pg.locator(f'.task:has-text("{MARK}")').count() > 0
        rec('新建待办并出现在看板', created, f'待办数 {before} → {pg.locator(".task").count()}')
        pg.screenshot(path='e2e/live-shots/k2-task-created.png')

        left2 = purge(pg, MARK)
        rec('删除待办 + confirm 确认', left2 == 0, '已删除，无残留' if left2 == 0 else f'仍剩 {left2} 条')
        pg.screenshot(path='e2e/live-shots/k2-task-deleted.png')
    except Exception as e:
        rec('待办增删链路', False, str(e)[:120])

    # ---------- 2. 设置页：历史版本 / 导出 / 登出 ----------
    pg.click('.nav-item[data-nav="settings"]'); pg.wait_for_timeout(1500)

    # 历史版本
    try:
        hist = pg.evaluate("() => [...document.querySelectorAll('[data-act]')].map(e => e.dataset.act).filter(a => /history|revision/i.test(a))")
        if hist:
            pg.click(f'[data-act="{hist[0]}"]'); pg.wait_for_timeout(2600)
            rows = pg.locator('.history-row, .revision-row, .modal-card li, .modal-card tr').count()
            rec('历史版本列表可用', rows > 0, f'{rows} 条备份')
            pg.screenshot(path='e2e/live-shots/k2-history.png')
            rec('历史版本弹窗可关闭', close_all_modals(pg), '已关闭')
            pg.wait_for_timeout(700)
        else:
            rec('历史版本入口', False, '未找到')
    except Exception as e:
        rec('历史版本', False, str(e)[:120])

    # 导出 JSON
    try:
        close_all_modals(pg)
        pg.click('.nav-item[data-nav="settings"]'); pg.wait_for_timeout(1300)
        with pg.expect_download(timeout=25000) as dl:
            pg.click('[data-act="export-json"]')
        d = dl.value
        raw = open(d.path(), 'rb').read()
        json.loads(raw.decode('utf-8'))
        rec('JSON 备份导出', len(raw) > 100, f'{len(raw)} 字节，JSON 合法')
    except Exception as e:
        rec('JSON 备份导出', False, str(e)[:140])

    # 导出 CSV
    try:
        close_all_modals(pg)
        pg.click('.nav-item[data-nav="settings"]'); pg.wait_for_timeout(1300)
        with pg.expect_download(timeout=25000) as dl:
            pg.click('[data-act="export-csv"]')
        d = dl.value
        raw = open(d.path(), 'rb').read()
        rec('CSV 导出', len(raw) > 20, f'{len(raw)} 字节')
    except Exception as e:
        rec('CSV 导出', False, str(e)[:120])

    # ---------- 3. 登出 ----------
    try:
        close_all_modals(pg)
        pg.click('.nav-item[data-nav="settings"]'); pg.wait_for_timeout(1300)
        n = pg.locator('[data-act="cloud-logout"]').count()
        if n > 0:
            pg.locator('[data-act="cloud-logout"]').first.click(); pg.wait_for_timeout(3000)
            close_all_modals(pg)
            pg.wait_for_timeout(1500)
            back = pg.locator('[data-act="cloud-login"]').count() > 0
            rec('退出登录', back, '已回到落地页')
            pg.screenshot(path='e2e/live-shots/k2-logout.png')
        else:
            rec('登出入口存在', False, '设置页未找到 cloud-logout')
    except Exception as e:
        rec('退出登录', False, str(e)[:120])

    # ---------- 4. 错误密码必须被拒绝 ----------
    try:
        if pg.locator('[data-act="cloud-login"]').count() > 0:
            pg.click('[data-act="cloud-login"]'); pg.wait_for_timeout(700)
            pg.fill('input[name="email"]', EMAIL); pg.fill('input[name="password"]', 'wrong-password-xyz')
            pg.click('form.modal-card button[type="submit"]'); pg.wait_for_timeout(3000)
            still_out = pg.locator('[data-act="cloud-login"]').count() > 0 and pg.locator('.nav-item').count() == 0
            rec('错误密码被拒绝', still_out, '未进入应用')
            close_all_modals(pg)
            pg.wait_for_timeout(800)
        else:
            rec('错误密码被拒绝', False, '当前仍处登录态，无法测试')
    except Exception as e:
        rec('错误密码校验', False, str(e)[:120])

    # ---------- 5. 正确密码重新登录 + 最终无残留 ----------
    try:
        pg.goto(BASE, wait_until='networkidle'); pg.wait_for_timeout(1800)
        pg.click('[data-act="cloud-login"]'); pg.wait_for_timeout(700)
        pg.fill('input[name="email"]', EMAIL); pg.fill('input[name="password"]', PWD)
        pg.click('form.modal-card button[type="submit"]'); pg.wait_for_timeout(4000)
        ok = pg.locator('.nav-item').count() >= 8
        rec('正确密码可再次登录', ok, f'导航 {pg.locator(".nav-item").count()} 项')
        pg.click('.nav-item[data-nav="board"]'); pg.wait_for_timeout(1600)
        final_left = pg.locator(f'.task:has-text("{MARK}")').count()
        rec('最终确认无测试数据残留', final_left == 0, f'{final_left} 条')
        pg.screenshot(path='e2e/live-shots/k2-final.png')
    except Exception as e:
        rec('重新登录', False, str(e)[:120])

    ctx.close(); br.close()

print('\n' + '=' * 60)
passed = sum(1 for s in steps if s['ok'])
print(f'关键链路：{passed}/{len(steps)} 通过')
print('JS/console 报错:', len(errors))
for e in errors[:6]:
    print('   ', e)

with open('e2e/live-keyflow.json', 'w', encoding='utf-8') as f:
    json.dump({'steps': steps, 'errors': errors, 'passed': passed, 'total': len(steps)}, f, ensure_ascii=False, indent=1)
