// resolve.mjs — the runtime resolver. Zero dependencies.
//
// Takes what the task router emitted and returns the JSON stream the agent
// acts on. Pure lookup over generated/catalog.json — no LLM call, no tokens.
//
//   import { resolve } from './resolve.mjs'
//   resolve({ entity:'campaign', metrics:['roas'], dimensions:['platform'] })

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const CAT = JSON.parse(readFileSync(
  fileURLToPath(new URL('./generated/catalog.json', import.meta.url)), 'utf8'));

const norm = s => String(s ?? '').toLowerCase().trim();

/** plain word -> concept name (handles "return on ad spend" -> roas) */
function toConcept(word) {
  const w = norm(word);
  if (CAT.concepts[w]) return w;
  for (const [name, c] of Object.entries(CAT.concepts))
    if ((c.says || []).some(s => norm(s) === w)) return name;
  return null;
}

/** platform named in a where-clause, if any */
function platformOf(task) {
  for (const p of task.where || []) {
    if (p.dimension === 'platform') {
      const v = p.value;
      if (Array.isArray(v)) return v.length === 1 ? norm(v[0]) : '__multi__';
      return norm(v);
    }
  }
  return null;
}

/** lowest-priority binding whose every `when` key is satisfied */
function bind(concept, ctx) {
  const ok = b => Object.entries(b.when || {}).every(([k, v]) => {
    if (k === 'platform')   return ctx.platform === norm(v);
    if (k === 'grain')      return ctx.grain === v;
    if (k === 'grouped_by') return ctx.groupedBy.includes(v);
    return false;
  });
  return CAT.bindings.filter(b => b.concept === concept && ok(b))[0] || null;
}

function resolveFor(task, platform) {
  const unresolved = [], caveats = new Set(), notes = [];
  const grain = task.entity || null;

  if (grain && !CAT.grains[grain])
    unresolved.push({ kind:'bug', what: 'entity', name: grain, why: `no grain mapping for "${grain}"` });

  // group-by: the entity's own grain column, then the asked dimensions
  const groupBy = [];
  const g = CAT.grains[grain];
  if (g) {
    let col = g.group_by;
    if (platform && g.by_platform && g.by_platform[platform]) col = g.by_platform[platform];
    if (col) groupBy.push(col);
  }
  let timeAsked = false;
  for (const d of task.dimensions || []) {
    const spec = CAT.dimensions[norm(d)];
    if (!spec) { unresolved.push({ kind:'bug', what: 'dimension', name: d, why: `not in the catalog` }); continue; }
    let col = spec.resolves_to;
    if (platform && spec.by_platform && spec.by_platform[platform]) col = spec.by_platform[platform];
    if (col === '__time__') { timeAsked = true; continue; }
    groupBy.push(col);
  }

  const ctx = { platform, grain, groupedBy: groupBy.concat(task.dimensions || []).map(norm) };

  // metrics
  const chosen = [];
  for (const raw of task.metrics || []) {
    const concept = toConcept(raw);
    if (!concept) { unresolved.push({ kind:'bug', what: 'metric', name: raw, why: 'no such concept' }); continue; }
    const c = CAT.concepts[concept];
    if (c.status === 'no_data') {
      unresolved.push({ kind:'parked', what: 'metric', name: raw, why: 'recognised, but this data is not in the warehouse yet' });
      continue;
    }
    const b = bind(concept, ctx);
    if (!b) { unresolved.push({ kind:'bug', what: 'metric', name: raw, why: `no binding for "${concept}" in this context` }); continue; }
    if (b.unavailable) {
      unresolved.push({ kind:'refusal', what:'metric', name: raw, why: b.unavailable });
      continue;
    }
    const m = CAT.metrics[b.use];
    if (!m) { unresolved.push({ kind:'bug', what: 'metric', name: raw, why: `binding points at unknown metric ${b.use}` }); continue; }
    if (m.status === 'broken')
      unresolved.push({ kind:'broken', what: 'metric', name: raw, why: `${b.use} is broken — its semantic model references a missing column` });
    if (m.status === 'deprecated')
      unresolved.push({ kind:'refusal', what: 'metric', name: raw, why: `${b.use} is deprecated (retired attribution)` });
    if (b.caveat) caveats.add(b.caveat);
    (m.caveats || []).forEach(x => caveats.add(x));
    if (b.note) notes.push({ metric: raw, note: b.note });
    if (!chosen.some(c => c.use === b.use)) chosen.push({ asked: raw, use: b.use, why: b.note || null, metric: m });
  }

  // all chosen metrics must live in one model, unless we only group by time
  const usable = chosen.filter(c => c.metric.status === 'ok');
  const modelSets = usable.map(c => new Set(c.metric.served_by));
  let model = null;
  if (modelSets.length) {
    const shared = [...modelSets[0]].filter(m => modelSets.every(s => s.has(m)));
    if (shared.length) model = shared[0];
    else if (groupBy.length)
      unresolved.push({ kind:'refusal', what: 'combination',
        name: usable.map(c => c.use).join(' + '),
        why: 'these metrics come from different semantic models, so they can only be grouped by time' });
  }
  if (usable.some(c => c.metric.cross_model) && groupBy.length)
    unresolved.push({ kind:'refusal', what: 'combination', name: usable.filter(c => c.metric.cross_model).map(c => c.use).join(', '),
      why: 'cross-model metric — can only be grouped by time' });

  // every group-by column must exist on the chosen model
  const mm = model ? CAT.models[model] : null;
  if (mm) {
    for (const col of groupBy) {
      if (!mm.dimensions.includes(col)) {
        const elsewhere = Object.values(CAT.models)
          .filter(x => x.dimensions.includes(col)).map(x => x.name);
        unresolved.push({ kind:'refusal', what: 'group_by', name: col,
          why: elsewhere.length
            ? `${model} has no "${col}" dimension. It exists on: ${elsewhere.slice(0,4).join(', ')} — name a platform so one can be chosen.`
            : `no semantic model has a "${col}" dimension` });
      }
    }
  }

  // grain
  if (mm && mm.finest_grain === 'month' && (task.time_range?.unit === 'day' || task.time_range?.unit === 'week'))
    caveats.add('month_grain_only');

  // cross-platform totalling
  if (!platform || platform === '__multi__') {
    for (const c of usable) {
      const ca = CAT.caveats.cross_platform_totals;
      if ((ca.applies_to_concepts || []).includes(toConcept(c.asked))) caveats.add('cross_platform_totals');
    }
  }

  return {
    ok: unresolved.length === 0,
    plan: unresolved.length ? null : {
      platform: platform && platform !== '__multi__' ? platform : null,
      layer: 'semantic',
      semantic_model: model,
      table: mm ? mm.table : null,
      metrics: chosen.map(c => ({ asked: c.asked, use: c.use, why: c.why })),
      group_by: groupBy,
      time_dimension: mm ? mm.time_dimension : null,
      grain: mm ? mm.finest_grain : null,
      time_asked: timeAsked,
    },
    caveats, notes, unresolved,
  };
}

/** Platforms this request could plausibly be split across, given the grain
 *  and dimensions asked for. Derived from by_platform in the catalog — the
 *  RDF already knows product means advertised_asin on Amazon and fsn_id on
 *  Flipkart, so a platform-less request fans out rather than being refused. */
function fanoutCandidates(task) {
  const set = new Set();
  const g = CAT.grains[task.entity];
  if (g && g.by_platform) Object.keys(g.by_platform).forEach(p => set.add(p));
  for (const d of task.dimensions || []) {
    const spec = CAT.dimensions[norm(d)];
    if (spec && spec.by_platform) Object.keys(spec.by_platform).forEach(p => set.add(p));
  }
  return [...set];
}

export function resolve(task) {
  const asked = platformOf(task);

  // explicit single platform, or nothing platform-specific in the request
  const direct = resolveFor(task, asked);
  const needsFanout = !asked && !direct.ok &&
        direct.unresolved.some(u => u.what === 'group_by' || u.what === 'combination') &&
        fanoutCandidates(task).length > 0;

  if (!needsFanout) {
    return {
      version: CAT.version, build_id: CAT.build_id,
      resolved: direct.ok,
      fanout: false,
      plans: direct.plan ? [direct.plan] : [],
      not_available_on: [],
      caveats: [...direct.caveats].map(id => ({ id, severity: CAT.caveats[id].severity, text: CAT.caveats[id].text })),
      notes: direct.notes,
      unresolved: direct.unresolved,
    };
  }

  // fan out: try each candidate platform independently
  const plans = [], missing = [], caveats = new Set(), notes = [];
  for (const p of fanoutCandidates(task)) {
    const r = resolveFor(task, p);
    if (r.ok) {
      plans.push(r.plan);
      r.caveats.forEach(c => caveats.add(c));
      r.notes.forEach(n => notes.push(n));
    } else {
      missing.push({ platform: p, why: r.unresolved.map(u => u.why).join('; ') });
    }
  }
  // platforms with ad data that simply cannot break down this way
  for (const p of ['meta', 'google']) {
    if (!plans.some(x => x.platform === p) && !missing.some(x => x.platform === p))
      missing.push({ platform: p, why: 'fct_ad_spend has no dimension at this grain — Meta and Google cannot be broken down this way' });
  }
  if (plans.length > 1) caveats.add('fanout_not_totalled');

  return {
    version: CAT.version, build_id: CAT.build_id,
    resolved: plans.length > 0,
    fanout: true,
    plans,
    not_available_on: missing,
    caveats: [...caveats].map(id => ({ id, severity: CAT.caveats[id].severity, text: CAT.caveats[id].text })),
    notes,
    unresolved: plans.length ? [] : direct.unresolved,
  };
}

// CLI:  node resolve.mjs '{"entity":"campaign","metrics":["roas"]}'
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const task = JSON.parse(process.argv[2] || '{"entity":"campaign","metrics":["roas"],"dimensions":["platform"]}');
  console.log(JSON.stringify(resolve(task), null, 2));
}
