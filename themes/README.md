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
paper   暖绒 · 鼠尾草   (由 custom.css 覆盖)
slate   冷雾 · 矩阵
mono    石墨 · 朱砂
clay    柔光 · 拟态
mist    雾蓝 · 云水     (skin-mist.css)
ember   暖橙 · 琥珀     (skin-ember.css)
rose    藕粉 · 樱云     (skin-rose.css)
forest  苔绿 · 森野     (skin-forest.css)
tech    科技 · 星舰     (skin-tech.css)
neu     拟态 · 素白     (skin-neu.css)
anime   动漫 · 樱糖     (skin-anime.css)
cyber   赛博 · 霓虹     (skin-cyber.css)
glass   液态 · 玻璃     (skin-glass.css)
lux     黑金 · 奢华     (skin-lux.css)
print   杂志 · 编辑     (skin-print.css)
retro   复古 · 街机     (skin-retro.css)
ocean   海岛 · 假日     (skin-ocean.css)
```

柔和疗愈系列（mist / ember / rose / forest）与风格化主题（tech / neu / anime / cyber / glass）
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
