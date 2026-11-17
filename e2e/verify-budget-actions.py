# -*- coding: utf-8 -*-
"""清债 v112：预算页右上角四个按钮 / 板块内按钮收走 / 分类预算对话框的举例。

需求原文：「把这三个按钮全部转到右上角……在子页面中删除记一笔债按钮，
右上角保持四个按钮，分别是清债介绍、添加收入、添加分类预算、记一笔开销」。
其余子页仍是「清债介绍 + 记一笔债」—— 债务页要留住加债入口。
"""
import os, sys

ROOT = 'C:/Users/slgzs/Desktop/ai-codex/workbuddy/Todo'
head = open(os.path.join(ROOT, 'e2e', 'verify-batch4.py'), encoding='utf-8').read().split('with sync_playwright() as p:')[0]
sys.argv = [sys.argv[0]]
exec(head)

from playwright.sync_api import sync_playwright

PASS = FAIL = 0
FAILS = []


def chk(name, ok, detail=''):
    global PASS, FAIL
    if ok:
        PASS += 1
        print('  ✓ %s' % name)
    else:
        FAIL += 1
        FAILS.append(name)
        print('  ✗ %s  << %s' % (name, detail))


def login(pg):
    pg.goto('http://127.0.0.1:%d/index.html' % port, wait_until='networkidle')
    pg.wait_for_timeout(500)
    if pg.locator('[data-act="cloud-login"]').count():
        pg.click('[data-act="cloud-login"]')
        pg.wait_for_timeout(400)
        pg.fill('input[name="email"]', 'test@example.com')
        pg.fill('input[name="password"]', 'test@example.com')
        pg.click('form.modal-card button[type="submit"]')
        pg.wait_for_timeout(2600)


def money(pg):
    pg.evaluate("() => { const b=document.querySelector('[data-nav=\"money\"]'); if(b) b.click(); }")
    pg.wait_for_timeout(800)


def tab(pg, key):
    pg.evaluate("""(k) => {
        const b = document.querySelector('[data-act="subtab"][data-page="money"][data-tab="' + k + '"]');
        if (b) b.click();
    }""", key)
    pg.wait_for_timeout(700)


def head_btns(pg):
    return pg.evaluate("""() => [...document.querySelectorAll('.head-actions .btn')].map(b => b.textContent.trim())""")


with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True)
    ctx = br.new_context(viewport={'width': 1280, 'height': 950})
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))

    login(pg)
    money(pg)

    print('\n[1] 预算页右上角四个按钮')
    tab(pg, 'budget')
    btns = head_btns(pg)
    chk('正好四个', len(btns) == 4, str(btns))
    chk('顺序是 介绍/收入/分类预算/记一笔开销',
        btns == ['清债介绍', '添加收入', '添加分类预算', '记一笔开销'], str(btns))
    chk('预算页没有「记一笔债」',
        '记一笔债' not in btns, str(btns))
    acts = pg.evaluate("""() => [...document.querySelectorAll('.head-actions .btn')].map(b => b.dataset.act)""")
    chk('四个按钮的 action 对得上',
        acts == ['money-intro', 'money-income-new', 'money-cat-new', 'money-spend-new'], str(acts))

    print('\n[2] 三个板块里不再有常驻按钮')
    inner = pg.evaluate("""() => {
        const panels = [...document.querySelectorAll('.panel')];
        const want = ['money-income-new', 'money-cat-new', 'money-spend-new'];
        const hits = [];
        panels.forEach(pn => {
            want.forEach(a => {
                if (pn.querySelector('[data-act="' + a + '"]')) hits.push(a);
            });
        });
        return hits;
    }""")
    chk('板块内没有这三个按钮', not inner, str(inner))
    chk('空态也不再放按钮', pg.locator('.empty-box [data-act="money-income-new"]').count() == 0)

    print('\n[3] 分类预算对话框的两段举例')
    pg.click('[data-act="money-cat-new"]')
    pg.wait_for_timeout(500)
    tip = pg.evaluate("""() => {
        const t = document.querySelector('#money-cat-form .mcat-tip');
        if (!t) return null;
        return { txt: t.textContent, ps: t.querySelectorAll('p').length,
                 bs: [...t.querySelectorAll('b')].map(b => b.textContent) };
    }""")
    chk('对话框里有 .mcat-tip', tip is not None)
    chk('两段（固定 / 日常）', tip and tip['ps'] == 2, tip and tip['ps'])
    chk('固定那段含「房租」「保险」',
        tip and '房租' in tip['txt'] and '保险' in tip['txt'], tip and tip['txt'][:40])
    chk('日常那段含「吃饭」「会员订阅」',
        tip and '吃饭' in tip['txt'] and '会员订阅' in tip['txt'], tip and tip['txt'][:40])
    chk('「固定」「日常」是加粗标签',
        tip and tip['bs'] == ['固定', '日常'], tip and tip['bs'])
    pg.click('#money-cat-form button[data-act="close-modal"]')
    pg.wait_for_timeout(300)

    print('\n[4] 其他子页保持「介绍 + 记一笔债」')
    for key, label in (('debts', '债务'), ('overview', '总览'), ('plan', '计划'), ('log', '记录'), ('tools', '工具')):
        tab(pg, key)
        b = head_btns(pg)
        chk('%s页两个按钮' % label, b == ['清债介绍', '记一笔债'], str(b))

    print('\n[5] 手机 390：四个按钮都在且不被截断')
    tab(pg, 'budget')
    pg.set_viewport_size({'width': 390, 'height': 900})
    pg.wait_for_timeout(600)
    vis = pg.evaluate("""() => {
        const bs = [...document.querySelectorAll('.head-actions .btn')];
        const box = document.querySelector('.head-actions').getBoundingClientRect();
        return {
            n: bs.length,
            clipped: bs.filter(b => {
                const r = b.getBoundingClientRect();
                return r.right > box.right + 1 || r.width < 8;
            }).length,
            lines: new Set(bs.map(b => Math.round(b.getBoundingClientRect().top))).size
        };
    }""")
    chk('四个按钮都在', vis['n'] == 4, str(vis))
    chk('没有被裁掉', vis['clipped'] == 0, str(vis))
    chk('最多两行', vis['lines'] <= 2, str(vis))

    print('\n[6] 没有 JS 异常')
    chk('无 pageerror', not errs, ' | '.join(errs[:3]))

    print('\n===== 清债 v112：%d 通过 / %d 失败 =====' % (PASS, FAIL))
    br.close()
    sys.exit(1 if FAIL else 0)
