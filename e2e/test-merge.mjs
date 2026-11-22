// 从 index.html 提取真实的 mergeStates 与 isPlainObject，做单元测试
import fs from 'node:fs';

const html = fs.readFileSync('index.html', 'utf8');

function extractFunction(src, name) {
  const idx = src.indexOf('function ' + name);
  if (idx < 0) throw new Error('function not found: ' + name);
  const start = src.indexOf('{', idx);
  let depth = 0;
  for (let i = start; i < src.length; i++) {
    if (src[i] === '{') depth++;
    else if (src[i] === '}') { depth--; if (depth === 0) return src.slice(idx, i + 1); }
  }
  throw new Error('unbalanced: ' + name);
}

const isPlainObjectSrc = extractFunction(html, 'isPlainObject');
const mergeStatesSrc = extractFunction(html, 'mergeStates');

const isPlainObject = new Function('return ' + isPlainObjectSrc)();
const mergeStates = new Function('isPlainObject', 'return ' + mergeStatesSrc)(isPlainObject);

let pass = 0, fail = 0;
function eq(actual, expected, name) {
  const a = JSON.stringify(actual), b = JSON.stringify(expected);
  if (a === b) { pass++; console.log('  PASS ' + name); }
  else { fail++; console.log('  FAIL ' + name + '\n    expect ' + b + '\n    actual ' + a); }
}

console.log('场景 A：本地新增待办（旧云端无此任务）→ 补入');
{
  const remote = { habits: [], tasks: [{ id: 't1', title: '收被单被子' }], checks: {}, moods: {}, doses: {}, notes: {}, events: [], bodyProfile: {} };
  const local = { habits: [], tasks: [{ id: 't1', title: '收被单被子' }, { id: 't2', title: '【测试】阅读' }], checks: {}, moods: {}, doses: {}, notes: {}, events: [], bodyProfile: {} };
  const m = mergeStates(remote, local);
  eq(m.tasks.map(t => t.id).sort(), ['t1', 't2'], '本地新增 t2 被保留');
}

console.log('场景 B：云端新增（本地无）→ 保留');
{
  const remote = { habits: [], tasks: [{ id: 't1' }, { id: 't3', title: '云端新' }], checks: {}, moods: {}, doses: {}, notes: {}, events: [], bodyProfile: {} };
  const local = { habits: [], tasks: [{ id: 't1' }, { id: 't2' }], checks: {}, moods: {}, doses: {}, notes: {}, events: [], bodyProfile: {} };
  const m = mergeStates(remote, local);
  eq(m.tasks.map(t => t.id).sort(), ['t1', 't2', 't3'], '云端 t3 + 本地 t2 都保留');
}

console.log('场景 C：两边同 id → 云端为主');
{
  const remote = { habits: [{ id: 'h1', name: '喝水', target: 8, archivedAt: '' }], tasks: [], checks: {}, moods: {}, doses: {}, notes: {}, events: [], bodyProfile: {} };
  const local = { habits: [{ id: 'h1', name: '喝水', target: 5, archivedAt: '' }], tasks: [], checks: {}, moods: {}, doses: {}, notes: {}, events: [], bodyProfile: {} };
  const m = mergeStates(remote, local);
  eq(m.habits[0].target, 8, 'target 以云端 8 为准');
}

console.log('场景 D：打卡计数 → 取较大值');
{
  const remote = { habits: [], tasks: [], checks: { '2026-10-24': { h_water: 3 } }, moods: {}, doses: {}, notes: {}, events: [], bodyProfile: {} };
  const local = { habits: [], tasks: [], checks: { '2026-10-24': { h_water: 5 } }, moods: {}, doses: {}, notes: {}, events: [], bodyProfile: {} };
  const m = mergeStates(remote, local);
  eq(m.checks['2026-10-24'].h_water, 5, '喝水计数取 5');
}

console.log('场景 E：软删除 archivedAt → 非空优先');
{
  const remote = { habits: [{ id: 'h1', archivedAt: '' }], tasks: [], checks: {}, moods: {}, doses: {}, notes: {}, events: [], bodyProfile: {} };
  const local = { habits: [{ id: 'h1', archivedAt: '2026-10-24T00:00:00Z' }], tasks: [], checks: {}, moods: {}, doses: {}, notes: {}, events: [], bodyProfile: {} };
  const m = mergeStates(remote, local);
  eq(m.habits[0].archivedAt, '2026-10-24T00:00:00Z', '本地归档被保留（删除不复活）');
}

console.log('场景 F：心情按日期合并，本地优先');
{
  const remote = { habits: [], tasks: [], checks: {}, moods: { '2026-10-23': 'happy' }, doses: {}, notes: {}, events: [], bodyProfile: {} };
  const local = { habits: [], tasks: [], checks: {}, moods: { '2026-10-24': 'ok' }, doses: {}, notes: {}, events: [], bodyProfile: {} };
  const m = mergeStates(remote, local);
  eq(Object.keys(m.moods).sort(), ['2026-10-23', '2026-10-24'], '两天心情都在');
}

console.log('场景 G：events 去重并集');
{
  const remote = { habits: [], tasks: [], checks: {}, moods: {}, doses: {}, notes: {}, events: [{ at: 'a', id: 'h1', delta: 1 }], bodyProfile: {} };
  const local = { habits: [], tasks: [], checks: {}, moods: {}, doses: {}, notes: {}, events: [{ at: 'a', id: 'h1', delta: 1 }, { at: 'b', id: 'h2', delta: 1 }], bodyProfile: {} };
  const m = mergeStates(remote, local);
  eq(m.events.length, 2, '去重后 2 条（a重复去掉，b保留）');
}

console.log('场景 H：未完成标记 skips → 按天逐键并集');
{
  const remote = { habits: [], tasks: [], checks: {}, skips: { '2026-11-18': { a: 1 } }, moods: {}, doses: {}, notes: {}, events: [] };
  const local = { habits: [], tasks: [], checks: {}, skips: { '2026-11-18': { b: 1 }, '2026-11-20': { a: 1 } }, moods: {}, doses: {}, notes: {}, events: [] };
  const m = mergeStates(remote, local);
  eq(m.skips['2026-11-18'], { a: 1, b: 1 }, '同一天两边各标一个，都保留');
  eq(m.skips['2026-11-20'], { a: 1 }, '本地新增的那天被保留');
}

console.log('场景 I：一侧没有 skips 字段 → 不报错');
{
  const remote = { habits: [], tasks: [], checks: {}, moods: {}, doses: {}, notes: {}, events: [] };
  const local = { habits: [], tasks: [], checks: {}, skips: { '2026-11-18': { a: 1 } }, moods: {}, doses: {}, notes: {}, events: [] };
  const m = mergeStates(remote, local);
  eq(m.skips['2026-11-18'], { a: 1 }, '旧客户端没有这个字段也能合并');
}

console.log('\n结果：' + pass + ' 通过 / ' + fail + ' 失败');
process.exit(fail ? 1 : 0);
