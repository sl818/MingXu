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
const mergeMoveSrc = extractFunction(html, 'mergeMoveModule');

const isPlainObject = new Function('return ' + isPlainObjectSrc)();
const mergeMoveModule = new Function('isPlainObject', 'return ' + mergeMoveSrc)(isPlainObject);
/* mergeStates 里用到全局的 MODULE_KEYS —— 从 index.html 里原样抠出来，别写死 */
const mkMatch = html.match(/const\s+MODULE_KEYS\s*=\s*\[([^\]]*)\]/);
if (!mkMatch) throw new Error('MODULE_KEYS not found');
const MODULE_KEYS = eval('[' + mkMatch[1] + ']');
const mergeStates = new Function('isPlainObject', 'mergeMoveModule', 'MODULE_KEYS',
  'return ' + mergeStatesSrc)(isPlainObject, mergeMoveModule, MODULE_KEYS);

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

console.log('场景 J：运动模块按 id 逐条合并（v198）—— 不再整块取新');
{
  const T1 = '2026-10-24T09:00:00.000Z', T2 = '2026-10-24T18:00:00.000Z';
  const sport = (id) => ({ id, key: 'run', name: '跑步', tVal: 5, updatedAt: T1 });
  const rec = (id, extra) => Object.assign({ id, sportId: 'sp1', key: 'run', d: '2026-10-24', at: T1, dur: 30, updatedAt: T1 }, extra || {});
  const mod = (sports, records, updatedAt) => ({
    on: true, name: '运动', updatedAt: updatedAt || T2, sports: sports, records: records
  });
  // 云端：A 端（远端）删了 r2、带墓碑；本地：B 端改了配置、还有 r2 的旧数据
  const remote = {
    modules: { move: mod([sport('sp1')], [rec('r1'), rec('r2', { deletedAt: T2, updatedAt: T2 })], T2) },
    checks: {}, moods: {}, doses: {}, notes: {}, events: [], bodyProfile: {}, habits: [], tasks: []
  };
  // 本地：B 端新增了 r3，r2 还是没删的旧版本，配置改过（updatedAt 更新）
  const local = {
    modules: { move: mod([sport('sp1')], [rec('r1'), rec('r2'), rec('r3')], T2) },
    checks: {}, moods: {}, doses: {}, notes: {}, events: [], bodyProfile: {}, habits: [], tasks: []
  };
  const m = mergeStates(remote, local);
  const ids = m.modules.move.records.map(r => r.id).sort();
  eq(ids, ['r1', 'r2', 'r3'], '记录一条没丢（新增的 r3 保住了）');
  const r2 = m.modules.move.records.find(r => r.id === 'r2');
  eq(!!r2.deletedAt, true, '云端删掉的 r2 没被本地旧数据复活（墓碑优先）');
  // 配置以较新的一侧为准，集合另行合并
  eq(m.modules.move.sports.length, 1, '运动实例没有重复');
}

console.log('场景 K：同一条记录两边都改 → updatedAt 新的胜出');
{
  const T1 = '2026-10-24T09:00:00.000Z', T2 = '2026-10-24T20:00:00.000Z';
  const base = { id: 'r1', sportId: 'sp1', key: 'run', d: '2026-10-24', at: T1 };
  const remote = { modules: { move: { on: true, updatedAt: T2, sports: [], records: [Object.assign({}, base, { dur: 30, updatedAt: T1 })] } },
    checks: {}, moods: {}, doses: {}, notes: {}, events: [], bodyProfile: {}, habits: [], tasks: [] };
  const local = { modules: { move: { on: true, updatedAt: T2, sports: [], records: [Object.assign({}, base, { dur: 45, updatedAt: T2 })] } },
    checks: {}, moods: {}, doses: {}, notes: {}, events: [], bodyProfile: {}, habits: [], tasks: [] };
  const m = mergeStates(remote, local);
  eq(m.modules.move.records.length, 1, '只有一条记录（没有变两条）');
  eq(m.modules.move.records[0].dur, 45, '本地改的 45 分钟胜出（updatedAt 更新）');
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
