# 晚风 Todo · 架构总纲

> 这份文档回答一个问题：**这个网站是由哪些部分组成的，它们怎么连起来跑。**
>
> 面向读者：接手的开发者、AI 编码助手。
> 详细内容在四份分册里，本文件只给骨架和不能破的规矩。

最后更新：v108（2026-11-17）

---

## 1. 一句话概括

一个**单用户的个人生活面板**：记录待办、用药、习惯、体重、随笔，数据存在自己的服务器上，
能装成手机 App（PWA），到点通过企业微信机器人把提醒推到手机。

它**没有**：构建工具、包管理器、前端框架、CDN、TypeScript、单元测试框架。
所有代码都是手写的原生 HTML/CSS/JS + PHP。

---

## 2. 技术栈（先接受这个事实，再读代码）

| 层 | 用什么 | 说明 |
|---|---|---|
| 前端 | 原生 JS（ES2018，无编译） | 全部在 `index.html` 一个文件里，约 17,800 行 |
| 样式 | 原生 CSS + CSS 变量 | 6 个 `<style>` 块，增量叠加式演进 |
| 图标 | 内联 SVG，无图标库 | `ICONS` 常量 + `icon(name)` 函数 |
| 后端 | 裸 PHP 8.2，无框架、无 Composer | `api.php` 单入口 + `api/` 下的功能模块 |
| 数据库 | MySQL / MariaDB（PDO） | 7 张表，业务数据主要是 `boards.data` 的一个 LONGTEXT |
| 时区 | 固定 `Asia/Shanghai` | 不依赖 `php.ini`，代码里显式构造 DateTimeZone |
| 离线 | Service Worker | 只缓存外壳，接口永不缓存 |
| 推送 | 企业微信「群机器人」webhook | 不用 APNs / FCM（国行安卓没有 GMS） |
| 测试 | Python + Playwright（真 Chrome）+ PHP 单测脚本 | `e2e/` 目录，125 个文件 |

**关键推论**：因为没有构建步骤，`index.html` 就是最终产物。
改完直接传服务器就生效——这是它简单的地方，也是它臃肿的原因。

---

## 3. 数据流全景

```
                    ┌─────────────────────────────────────────┐
                    │            index.html（单文件）          │
                    │                                         │
  用户点击 ────────► │  document.addEventListener('click')      │
                    │        │                                │
                    │        ├─[data-nav]──► goView(key)       │
                    │        └─[data-act]──► ACTIONS[act](el)  │
                    │                    │                    │
                    │                    ▼                    │
                    │        改内存里的 state（唯一真相）        │
                    │                    │                    │
                    │                    ├──► render()  ← 重绘整个 #main
                    │                    │      └─► VIEWS[view]()
                    │                    │      └─► bindView()  挂交互
                    │                    │
                    │                    └──► save()
                    │                          └─► 300ms 防抖
                    │                              └─► cloudPush()
                    └────────────────────┬────────────────────┘
                                         │ POST api.php?action=save
                                         │ { base_rev, data }
                                         ▼
                    ┌─────────────────────────────────────────┐
                    │   api.php（23 个 action 的分发器）        │
                    │   鉴权 lb_auth() → CSRF → 业务逻辑       │
                    └────────────────────┬────────────────────┘
                                         │
                    ┌────────────────────┼────────────────────┐
                    ▼                    ▼                    ▼
              boards.data          board_revisions       push_sent
           （整份 state JSON）     （最近 20 版快照）    （推送去重记录）

     另一条独立链路（不经过浏览器）：
     宝塔 cron 每分钟 → tools/push_tick.php → api/schedule.php 算「这一分钟该发什么」
                     → api/push.php 发到企业微信 → 写 push_sent 去重
```

**三条要记住的**：

1. **`state` 是唯一真相**。所有 UI 都是它的投影，改数据只改 `state` 然后 `render()`。
2. **云端存的是整份快照**，不是增量。每次保存都覆盖 `boards.data` 整个字段。
3. **推送链路完全不经过前端**。前端改了字段，后端 `schedule.php` 能不能读到，取决于两边字段名是否一致。

---

## 4. 文件职责表

### 4.1 必须传上线的（核心层）

| 文件 | 行数 | 职责 | 改动风险 |
|---|---|---|---|
| `index.html` | 11,729 | 整个前端 | 高。改任何地方都要跑回归 |
| `api.php` | 824 | 唯一入口 + 23 个 action | 中。改完必须跑 `verify-api-http.py` |
| `api/bootstrap.php` | 336 | 配置、DB、会话、鉴权、限流、JSON 输出 | **高**。所有接口都过它 |
| `api/ics.php` | 406 | 生成 iCalendar（日历订阅） | 中。与前端 `buildICS()` 必须等价 |
| `api/schedule.php` | 331 | 算「某一天几点该提醒什么」（推送用） | 中。三套过滤条件之一 |
| `api/push.php` | 370 | 企业微信发送 + 一轮推送的调度 | 中。有健忘点，见分册 |
| `api/backup.php` | 168 | 每日快照写入 `../backups/` | 低。整段 try/catch 包住 |
| `service-worker.js` | 99 | PWA 缓存策略 | **低行数，高影响**。改前端必须动它 |
| `manifest.json` | — | PWA 清单 | 低 |
| `themes/*.css` | — | 6 个补充皮肤 + custom | 低。只写变量 |
| `icons/*.png` | — | 3 个尺寸图标 | 低 |

### 4.2 只在服务器上跑，不经浏览器

| 文件 | 用途 | 触发方式 |
|---|---|---|
| `tools/push_tick.php` | 推送主循环 | 宝塔 cron，**每分钟** |
| `tools/push_diag.php` | 只读诊断「为什么这条没发」 | 手动 CLI |
| `tools/push_fix.php` | 检测并补建 `push_sent` 唯一索引 | 手动 CLI，幂等 |
| `tools/push_test.php` | 发一条测试消息 | 手动 CLI，仅 CLI |
| `tools/restore_backup.php` | 从快照恢复 | 手动 CLI，默认预演 |
| `tools/create_user.php` | 命令行建号（救援用） | 手动 CLI |

### 4.3 开发期只有，不上线

| 路径 | 用途 |
|---|---|
| `e2e/` | 95 个测试文件：PHP 单测、Playwright E2E、对比度审计、线上测试 |
| `install/` | 首次安装向导（装完应删或锁住） |
| `db/` | `schema.sql` + 4 个迁移文件 |
| `design/`、`beifen-dsh/`、`*.md`、`*.pdf` | 设计稿、历史快照、文档 |

---

## 5. 四条不变量

这四条任何一条破了，都会出**看起来毫不相关**的故障。改代码前先读一遍。

### 不变量 1：改前端必须推进 SW 缓存名

`service-worker.js` 第 3 行 `const CACHE = 'lifeboard-shell-vNN'`。
不推进 → 老客户端永远拿缓存的旧 `index.html`，你会以为"改了没生效"。

### 不变量 2：`state` 新增字段必须同步四处

新增一个可编辑字段，要同时改：

1. `normalizeState()` —— 补默认值和类型校验
2. `mergeStates()` —— 多端合并时别把它丢了
3. `api/ics.php` + 前端 `buildICS()` —— 日历要用就一起加
4. `api/schedule.php` —— 推送要用就一起加

漏第 1 处：老数据加载出来字段是 `undefined`。
漏第 2 处：两台设备同时用，一边的修改会被静默吞掉（**已踩两次**）。
漏第 3、4 处：页面显示了，但日历/推送算不出来。

### 不变量 3：「什么时候该提醒」有三套实现，过滤条件必须一致

| 实现 | 位置 | 输出 |
|---|---|---|
| 页内提醒横幅 | `index.html` → `remindItems()` | 打开网页时看到什么 |
| 日历订阅 | `api/ics.php` + 前端 `buildICS()` | `.ics` 规则，给日历客户端 |
| 手机推送 | `api/schedule.php` | 某一分钟的实例 |

**改任意一套的过滤条件，另外两套要跟着改。** 详细对照见 `BACKEND.md` 第 5 节。

### 不变量 4：写文件的脚本必须保持行尾

`index.html` 和 `api.php` 是 **CRLF**；`api/bootstrap.php`、`api/*.php`（多数）、`DEPLOY.md` 是 **LF**。

用 Python 改这些文件，必须：

```python
raw = io.open(p, 'r', encoding='utf-8', newline='').read()   # newline='' 原样读
nl = '\r\n' if '\r\n' in raw else '\n'
s = raw.replace('\r\n', '\n')          # 内部统一按 LF 处理
... 改 ...
io.open(p, 'w', encoding='utf-8', newline='').write(s.replace('\n', nl))
```

不做这层处理，git 上会出现整文件级假 diff（几千行），review 就废了。

---

## 6. 文档地图

**所有文档都在 `docs/` 下**，项目根目录只留 `README.md` 作入口。

| 文档 | 管什么 | 什么时候读 |
|---|---|---|
| **ARCHITECTURE.md**（本文） | 骨架、文件职责、不变量 | 第一次接触项目 |
| **FRONTEND.md** | `index.html` 内部结构、视图、ACTIONS、渲染、主题 | 改任何前端代码前 |
| **BACKEND.md** | 23 个接口、鉴权、三套提醒、推送、备份、部署 | 改任何后端代码前 |
| **DATA-MODEL.md** | `state` 全部字段、迁移、合并规则 | 加字段、改合并、查数据 |
| `DEPLOY.md` | 宝塔部署、Nginx、HTTPS、备份、cron | 上线时 |
| `THEME-SPEC.md` / `AI-THEME-GUIDE.md` | 写新皮肤 | 加主题时 |
| `docs/README.md` | 目录索引 | 不知道该看哪份 |
| `../README.md` | 功能说明（给用户看的） | 想知道"这功能是干什么的" |
| `HANDOFF.md` | 版本流水与交接 | 想知道"哪些版本改了什么" |
| `SITE-STRUCTURE.md` | 已并入本文，保留为指路牌 | — |
| `reports/` | 历史测试报告与事故复盘 | 想知道"当时为什么这么改" |

> 本文里出现的 `api/ics.php`、`index.html`、`e2e/xxx.py` 这类路径，**一律相对项目根**，
> 不是相对 `docs/`。看到它们时从仓库根目录找。

---

## 7. 阅读路线（30 分钟上手）

**别一上来啃 17,800 行。** 按这个顺序：

1. **本文第 3 节的图**（5 分钟）—— 知道数据从哪来到哪去
2. **`DATA-MODEL.md` 第 1 节**（5 分钟）—— 知道 `state` 长什么样
3. **`FRONTEND.md` 第 6 节「ACTIONS 调度」**（5 分钟）—— 知道点一个按钮会发生什么
4. **只读你关心的那个视图**（10 分钟）—— 比如改用药页，就只读 `viewMeds()` 和相关组件函数
5. **`BACKEND.md` 第 2 节路由表**（5 分钟）—— 需要接口时对号入座

**找代码的方法比读得快更重要**：

```bash
grep -n "function viewMeds" index.html          # 定位视图
grep -n "data-act=\"med-take\"" index.html       # 定位按钮
grep -n "'med-take':" index.html                # 定位 handler
grep -n "class=\"med-row" index.html            # 定位渲染出的 DOM 结构
grep -n "^\\.med-row{" index.html               # 定位样式
```

---

## 8. 改代码的标准流程

```
1. 找出要改的位置（用上面那组 grep）
2. 改代码
3. node _check_script.mjs                ← JS 语法 + data-act handler 覆盖
4. node _check_script.mjs 报的缺失必须修，不能忽略
5. 跑相关的 PHP 单测（改了后端才需要）
6. 跑相关的 e2e（见下）
7. 改了前端？推进 service-worker.js 的 CACHE 名
8. 打包 Todo-update.zip
9. 传服务器（含 api/ 改动就先传 PHP，含迁移就先跑 SQL）
10. 线上比 md5 确认版本对
```

**回归套件（分开跑，不要串在一条命令里，120 秒超时会杀掉后一个）**：

| 脚本 | 项数 | 管什么 |
|---|---|---|
| `e2e/regression-v3.py` | 40 | 综合冒烟（登录、各页面渲染、0 JS 报错） |
| `e2e/verify-v15.py` | 44 | 三种 PC 布局 + 手机布局 + 导航顺序 |
| `e2e/verify-mobile-nav.py` | 44 | 移动端 4 tab + 更多抽屉 |
| `e2e/verify-batch2.py` | 51 | 第二批功能（搜索、命令、归档等） |
| `e2e/verify-batch3.py` | 60 | 第三批功能（统计、拖拽、详情） |
| `e2e/verify-batch4.py` | 20 | 第四批功能 |
| `e2e/verify-api-http.py` | 33 | 后端 HTTP 层（鉴权、方法、404） |
| `e2e/verify-ics-subscribe.py` | 9 | 前后端日历等价性 |
| `e2e/audit-*.py` | 468 取样 | 9 皮肤 × 明暗对比度 |

---

## 9. 已知的不一致（不是 bug，但要知道）

写在文档里是为了避免下一个人重复困惑。

| 现象 | 原因 | 要不要修 |
|---|---|---|
| 「已完成 / 已取消」的过滤口径 | 曾经 `ics.php` / `buildICS()` 只排除 `done`，`schedule.php` 还排除 `cancelled`，导致「日历有、手机不响」 | **v48 已统一**：三处一律排除 `done` + `cancelled`。改任一处都要同步另两处，`e2e/test-ics.php` 有用例锁死 |
| `tools/push_tick.php` 头部注释写 PHP 8.1，线上实际用 8.2 | 注释没跟着改 | 注释而已 |
| `e2e/regression-rebuild.py` 跑不通 | 它在等一个早就移除的按钮 | 不修，已排除在回归外 |
| `handleImport()` 是死代码 | 设置页文案已声明「不再支持导入」 | 不修 |

---

## 10. 这个项目的性格

读代码时你会发现一些反复出现的选择，理解它们能少走很多弯路：

- **宁可多写判断，不要静默出错**。所以到处是 `if (!is_array($x)) continue;`。
- **派生数据不存储，每次算**。库存 = 基线 − 记录推算，不做"剩余数量"字段。
- **配置类的东西写死，不做设置页**。推送汇报的 3 个时间、断点、配色都是常量。
- **样式靠叠加修复，不重构**。6 个 `<style>` 块是 6 轮迭代的结果，后块覆盖前块。
  看到重复定义不要惊讶，先确认哪条最后生效。
- **注释写"为什么"，不写"是什么"**。注释里出现"以前""踩过""否则会"的地方，都是血泪。
