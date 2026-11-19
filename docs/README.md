# 文档目录

这个目录放所有说明文档；项目根目录只留 [README.md](../README.md)（入口）和代码。

**当前版本 v119（2026-11-19）**：`index.html` 14,669 行 + `assets/app.css` 4,078 行 · 12 个页面 · 187 个 action · 6 套主题 × 明暗 · 27 个后端接口（含 4 个邮件接口，详见 [SMTP.md](SMTP.md)）。

---

## 技术文档（改代码前读）

| 文档                                     | 回答什么问题                                      | 什么时候读           |
| -------------------------------------- | ------------------------------------------- | --------------- |
| [ARCHITECTURE.md](ARCHITECTURE.md)     | 整体怎么跑、文件职责、**四条不能破的规矩**                     | 第一次接触项目         |
| [FRONTEND.md](FRONTEND.md)             | `index.html` 内部结构、12 个页面 / 15 个 view 函数、182 个 action 怎么分发、主题、移动端 | 改前端             |
| [BACKEND.md](BACKEND.md)               | 23 个接口的鉴权、**三套提醒的过滤条件对照**、推送、备份、部署运维        | 改后端             |
| [DATA-MODEL.md](DATA-MODEL.md)         | `state` 全部字段、迁移链、多端合并规则                     | 加字段 / 改合并 / 查数据 |
| [SITE-STRUCTURE.md](SITE-STRUCTURE.md) | 文档索引 + 主题系统的准确信息                            | 写皮肤             |
| [REFACTOR-PLAN.md](REFACTOR-PLAN.md)   | **拆分评估**：实测规模、三阶段、成本与限制；第 8 节是按「AI 增删改效率」的重评 | 想动结构时 |
| [CHANGE-MAP.md](CHANGE-MAP.md)         | **改动地图**：改某个功能要动哪几处、跑哪个测试                | 每次改动前          |
| [DESIGN-LIB.md](DESIGN-LIB.md)         | **设计参考库**：Trackie / Yuvomi 的交互素材、成本与优先级      | 做大改版前          |
| [DEPLOY.md](DEPLOY.md)                 | 宝塔部署、Nginx、HTTPS、备份、定时任务、排错                 | 上线 / 运维         |
| [HANDOFF.md](HANDOFF.md)               | 当前线上状态、版本流水、已知问题、技术债                        | 接手 / 想知道改过什么    |
| [THEME-SPEC.md](THEME-SPEC.md)         | 主题变量、组件类名、允许 / 禁止清单                         | 写皮肤             |
| [AI-THEME-GUIDE.md](AI-THEME-GUIDE.md) | 可直接复制给 AI 的主题编写提示词                          | 让 AI 写皮肤        |

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
| [明序-UI评审报告.md](reports/明序-UI评审报告.md)         | UI 评审结论                                |
| [整站优化清单.md](reports/整站优化清单.md)                       | 整站优化项清单（多数已执行）                         |
| `明序 UI优化方案.pdf`                                  | UI 方案设计稿                               |

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
