import fs from 'node:fs';
import vm from 'node:vm';

// 用法：node _check_script.mjs [index.html]
// 1) 校验每一段内联 <script> 的语法（跳过带 src 的外链脚本）
// 2) 对照最后一段脚本里的 ACTIONS 键与整份 HTML 中的字面量 data-act，报告缺漏
//    注意：动态拼接的 data-act（如用药清单里的 med-take）不会出现在字面量统计中。

const file = process.argv[2] || 'index.html';
const html = fs.readFileSync(file, 'utf8');

const blocks = [];
const re = /<script\b([^>]*)>([\s\S]*?)<\/script>/gi;
let m;
while ((m = re.exec(html)) !== null) {
  if (/\bsrc\s*=/i.test(m[1] || '')) continue;
  blocks.push({
    attrs: (m[1] || '').trim(),
    code: m[2],
    line: html.slice(0, m.index).split('\n').length
  });
}

if (!blocks.length) {
  console.log('NO INLINE SCRIPT');
  process.exit(1);
}

let ok = true;
blocks.forEach((b, i) => {
  const label = 'block #' + (i + 1) + ' @ line ' + b.line + ' (' + b.code.length + ' chars' +
    (b.attrs ? ', ' + b.attrs : '') + ')';
  try {
    new vm.Script(b.code, { filename: 'inline-' + (i + 1) + '.js' });
    console.log('SYNTAX: OK   ' + label);
  } catch (e) {
    ok = false;
    console.log('SYNTAX: FAIL ' + label);
    const stack = String((e && e.stack) || e).split('\n');
    console.log('  ' + stack.slice(0, 3).join('\n  '));
    if (e && e.lineNumber) console.log('  file line ~ ' + (b.line + e.lineNumber - 1));
  }
});
if (!ok) process.exitCode = 1;

// 以最后一段内联脚本（应用主体）为准做覆盖率检查；
// data-act 同时也会出现在静态 HTML 里，所以从整份文件收集。
const main = blocks[blocks.length - 1].code;
const used = [...new Set(
  [...html.matchAll(/\bdata-act="([a-z][a-z-]*)"/g)].map(x => x[1])
)].sort();
const defined = [...new Set(
  [...main.matchAll(/^\s*'([a-z][a-z-]*)'\s*:\s*(?:el\b|\(\)|function\b)/gm)].map(x => x[1])
)].sort();

console.log('\nacts used (literal): ' + used.length);
console.log('  ' + JSON.stringify(used));
console.log('actions defined: ' + defined.length);
console.log('  ' + JSON.stringify(defined));

const missing = used.filter(k => !defined.includes(k));
const extra = defined.filter(k => !used.includes(k));
console.log('\nmissing handlers: ' + (missing.length ? JSON.stringify(missing) : 'none'));
console.log('handlers without literal use (may be dynamic): ' + (extra.length ? JSON.stringify(extra) : 'none'));
if (missing.length) process.exitCode = 1;

// PHP 文件开头的 UTF-8 BOM 会让 declare(strict_types=1) 不再是第一条语句
const phpFiles = ['api.php', 'api/bootstrap.php', 'api/config.php', 'install/index.php', 'tools/create_user.php'];
const bomHits = [];
for (const f of phpFiles) {
  if (!fs.existsSync(f)) continue;
  const buf = fs.readFileSync(f);
  if (buf.length >= 3 && buf[0] === 0xEF && buf[1] === 0xBB && buf[2] === 0xBF) bomHits.push(f);
}
console.log('\nPHP BOM: ' + (bomHits.length ? JSON.stringify(bomHits) : 'none'));
if (bomHits.length) {
  console.log('  Remove the BOM before the opening <?php, or PHP will fail on declare(strict_types=1).');
  process.exitCode = 1;
}

