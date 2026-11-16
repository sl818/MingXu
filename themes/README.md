# 主题作者入口

## 只改一个文件

```text
themes/custom.css
```

它在 `themes/themes.css` 之后加载，可以用来覆盖现有主题或做实验。

## 不要改

```text
index.html
themes/themes.css
api.php
api/bootstrap.php
service-worker.js
install/
db/
tools/
```

## 现有主题键

```text
paper   暖绒 · 鼠尾草   (index.html 内联 + custom.css 覆盖)
slate   冷雾 · 矩阵     (index.html 内联)
neu     拟态 · 素白     (skin-neu.css)
retro   复古 · 街机     (skin-retro.css)
cloud-float  浮纸 · 抬升    (同上)
cloud-focus  聚光 · 晕影    (同上)
```

**v87 删除了 mono（石墨 · 朱砂）、clay（柔光 · 拟态）、forest（苔绿 · 森野）、
cyber（赛博 · 霓虹）四套皮肤**，连同 `skin-forest.css` / `skin-cyber.css` 两个文件和
`service-worker.js` 的预缓存清单一起移除。旧用户保存在 `lifeboard.skin` 里的这四个键
会自动回落到 `paper`。

**v99 又删了 `mist`（雾蓝 · 云水）和 `cloud-haze`（云晕 · 柔光）**：`skin-mist.css` 文件、`<link>`、SW 预缓存、白名单两键一起移除，旧用户存的这两个键同样回落 `paper`。

云系两套（cloud-float / cloud-focus）**共用一个文件** `skin-cloud.css`：
选择器统一用 `[data-skin^="cloud-"]`，二者只在文件末尾的变体段
区分两侧留白处理（卡片浮起 / 四周晕影），都不带重复纹理。该文件 v98 由 `skin-mist.css` 派生，v99 起**没有上游、独立维护**。改基座组件规则要同时考虑两套。

另外两套（neu / retro）
都是自包含的独立文件 `themes/skin-*.css`，加载在 `custom.css` 之后，已注册进 `index.html` 的 SKINS 数组与首屏白名单。
柔和疗愈系列用 `node design/gen-skins.mjs` 生成，风格化主题用 `node design/gen-styles.mjs` 生成，
`node design/verify-skins.mjs` 统一校验。

## 最小工作流

1. 选一个现有主题键，比如 `paper`。
2. 把 `custom.css` 里注释掉的示例复制出来，改 `data-skin="paper"`。
3. 同时写浅色和深色变量。
4. 保存，刷新页面，在设置里切换主题查看。
5. 如果主题要新增一个键，先让维护者注册；不要让 AI 自行改 `index.html`。

## 规范

完整约束和 AI 提示词在：

- [../THEME-SPEC.md](../THEME-SPEC.md)
- [../AI-THEME-GUIDE.md](../AI-THEME-GUIDE.md)（可直接复制给 AI）
- [../SITE-STRUCTURE.md](../SITE-STRUCTURE.md)

## 新主题模板

复制 [\_template.css](_template.css) 到 `custom.css` 起步。
