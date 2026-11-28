# 文档目录

这个目录放所有说明文档；项目根目录只留 [README.md](../README.md)（入口）和代码。

**当前版本 v224（2026-11-28，待上传；v223 已上线）**：`index.html` 21,783 行 + `assets/app.css` 4,366 行 · 17 个页面 · 360+ 个 action · 1 套主题 × 明暗两态 · 后端 `api.php` 36 个动作 + `api/` 下 7 个接口文件（详见 [BACKEND.md](BACKEND.md) / [SMTP.md](SMTP.md)）。

---

## 技术文档（改代码前读）

| 文档                                     | 回答什么问题                                      | 什么时候读           |
| -------------------------------------- | ------------------------------------------- | --------------- |
| [ARCHITECTURE.md](ARCHITECTURE.md)     | 整体怎么跑、文件职责、**四条不能破的规矩**                     | 第一次接触项目         |
| [FRONTEND.md](FRONTEND.md)             | `index.html` 内部结构、17 个页面 / 18 个 view 函数、360+ 个 action 怎么分发、主题、移动端 | 改前端             |
| [BACKEND.md](BACKEND.md)               | 23 个接口的鉴权、**三套提醒的过滤条件对照**、推送、备份、部署运维        | 改后端             |
| [DATA-MODEL.md](DATA-MODEL.md)         | `state` 全部字段、迁移链、多端合并规则                     | 加字段 / 改合并 / 查数据 |
| [REFACTOR-PLAN.md](REFACTOR-PLAN.md)   | **拆分评估**：实测规模、三阶段、成本与限制；第 8 节是按「AI 增删改效率」的重评 | 想动结构时 |
| [CHANGE-MAP.md](CHANGE-MAP.md)         | **改动地图**：改某个功能要动哪几处、跑哪个测试                | 每次改动前          |
| [DEPLOY.md](DEPLOY.md)                 | 宝塔部署、Nginx、HTTPS、备份、定时任务、排错                 | 上线 / 运维         |
| [HANDOFF.md](HANDOFF.md)               | 当前线上状态、版本流水、已知问题、技术债                        | 接手 / 想知道改过什么    |
| [MOVE-OPTIMIZATION.md](MOVE-OPTIMIZATION.md) | **运动模块 v185 优化（已实施）**：五条反馈怎么改、「真人走一遍」回归矩阵、文末实施记录与差异 | 改运动模块前        |

## 产品与方案文档（习惯 2.0）

| 文档 | 回答什么问题 | 什么时候读 |
|---|---|---|
| [PRD-HABITS-V2.md](PRD-HABITS-V2.md) | **需求**：周期模型、双层判定、七种节奏、配额与时段、24 条异常、风险登记册（v1.0，写于 v174 之前） | 想确认「当初为什么这么设计」 |
| [HABITS-UPGRADE-GUIDE.md](HABITS-UPGRADE-GUIDE.md) | **在 v205 代码上哪些还成立**：与 PRD 的逐条裁决、现状事实、明确不做清单 | 动手前先读这份，与 PRD 冲突以它为准 |
| [HABITS-V2-CHANGE-ORDER.md](HABITS-V2-CHANGE-ORDER.md) | **可执行改动单**：B0–B8 分批、每批改哪几处、验收矩阵、架构建议（含「不建 SQL 表」「不推倒重写」的结论） | 真正开始改的时候 |
| [habits-v2-preview.html](habits-v2-preview.html) | **可交互预览**：直接引用 `assets/app.css` + `theme-v2.css` 与真实卡片 class，明暗双态、可点打卡、可切节奏 | 决定「要不要这么改」时先看它 |
| [prototype-habits-v2.html](prototype-habits-v2.html) | 单文件可交互原型：5 种打卡形态、三步表单、详情周期视图 | 想直观看看交互长什么样 |

> 这三份是递进关系：PRD 说「要什么」→ 升级指南说「哪些还成立」→ 改动单说「按什么顺序改」。
> 三者都**未落地实施**（v216 线上仍只有「每天」一种节奏），实施与否见改动单 §9 的分期建议。

## 设计文档（2026-11-23 起集中在 `design/`）

| 文档                                     | 回答什么问题                                      | 什么时候读           |
| -------------------------------------- | ------------------------------------------- | --------------- |
| [design/README.md](design/README.md)   | **设计文档索引 + 每份的时效与适用范围**（读设计文档先看这份）        | 动视觉层之前          |
| [design/REVIEW-2026-11-23.md](design/REVIEW-2026-11-23.md) | 最近一次设计评审：23/40、13 条待办、复核记录、复评方法 | 做视觉层 / 想知道欠什么 |
| [design/SITE-STRUCTURE.md](design/SITE-STRUCTURE.md) | 17 页页面地图、导航与移动端槽位、主题与断点、PWA 缓存（2026-11-27 重写，v203）  | 查页面在哪 / 视觉文件怎么分工     |
| [design/THEME-V2-PLAN.md](design/THEME-V2-PLAN.md)   | 主题 v2 的需求与逐版执行记录                        | 改主题           |
| [design/BRAND.md](design/BRAND.md)     | logo、命名、slogan、语气、字体                        | 动品牌资产时          |
| [design/DESIGN-LIB.md](design/DESIGN-LIB.md) | 设计参考库：Trackie / Yuvomi 的交互素材、成本与优先级      | 做大改版前          |
| [design/THEME-SPEC.md](design/THEME-SPEC.md) | ⚠️ **已失效**：六皮肤时代的变量契约（机制已删）              | 只作历史参考          |
| [design/AI-THEME-GUIDE.md](design/AI-THEME-GUIDE.md) | ⚠️ **已失效**：给 AI 写 `themes/custom.css` 的提示词      | 只作历史参考          |

> 视觉规范的**唯一出处**是根目录 [DESIGN.md](../DESIGN.md)，不在本目录。

**建议阅读顺序**：ARCHITECTURE 第 3 节（数据流图）→ DATA-MODEL 第 1 节（`state` 长什么样）  
→ FRONTEND 第 6 节（点一个按钮发生什么）→ 只读你关心的那个视图。

**别一上来啃 17,772 行**。找代码用 grep：

```bash
grep -n "function viewMeds" index.html          # 定位视图
grep -n "data-act=\"med-take\"" index.html       # 定位按钮
grep -n "'med-take':" index.html                # 定位 handler
```

---

## 历史报告（`reports/`）

| 文档                                                   | 内容                                     |
| ---------------------------------------------------- | -------------------------------------- |
| [线上测试报告-2026-10-29.md](reports/线上测试报告-2026-10-29.md) | v43 线上全功能测试：环境体检、后端、前端、桌面 32 项、移动 12 项 |
| [线上测试报告-2026-10-26.md](reports/线上测试报告-2026-10-26.md) | v30 时代的线上测试报告                          |
| [库存事故复盘-2026-10-27.md](reports/库存事故复盘-2026-10-27.md) | v31 库存错乱与用药记录丢失的完整复盘                   |
| [网站改动报告.md](reports/网站改动报告.md)                       | 早期改动的汇总                                |
| [整站优化清单.md](reports/整站优化清单.md)                       | 整站优化项清单（多数已执行）                         |

> UI 评审报告与 UI 方案设计稿已于 2026-11-23 移入 [`design/reviews/`](design/reviews/)。

---

## 维护约定

**改完代码如果动了结构，顺手更新对应分册。** 文档过期比没有文档更糟——  
它会让人按错误的前提动手。

**写文档只写锚点，不写行号。** 行号一改就废；函数名、常量名、类名相对稳定，而且能 grep 到。

**写完跑一次核对**：

```bash
python e2e/check-doc-anchors.py
```

它会抽取文档里提到的函数名、`data-act`、`ACTIONS` 键、文件路径、CSS 类，  
逐个去代码里验证，报"文档提到但代码里没有"的符号。

> 这个工具不是摆设：第一次跑就抓出两处我按印象写的类名——用药页写成 med-page  
> （实际是 med-board）、待办卡片写成 task-card（实际是 task）。这个项目所有 class  
> 都由 JS 字符串拼出，名字写错不会报错，只会 grep 不到——所以必须机器核对。
