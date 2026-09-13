# Prebuilt Report Cards — meerkats.ai cockpit

The **prebuilt card library**: every catalog report, already materialized as concrete,
schema-valid report cards with their **queries baked in** — so the cockpit user just browses
the library and **pins** what they want to track. No prompts, no generation, no model anywhere
in this path. (The on-demand prompt→card path is a separate task and lives with the
prompt-to-task router; this repo is the standing library.)

Companion repos: [ad-platform-dashboards-aligned](https://github.com/meerkatsai/ad-platform-dashboards-aligned)
(the UI + DSL-aligned schemas these cards render in) · original design reference:
[ad-platform-dashboards](https://github.com/meerkatsai/ad-platform-dashboards).

## Cockpit demo + design system

`index.html` + `cockpit.js` at the root are a faithful vanilla port of the design
handoff's own dashboard (`ui_kits/dashboard/`): **top bar = wordmark + platform dropdown
only**; below it the design file's exact card sets — 10 separate full-width cards per
platform (KPIs with sparklines + vs-prev/vs-target deltas, trend, ranked campaigns,
campaign trend, performance table, DoD/WoW/MoM period tables, campaign×dimension grid,
placement bars; Meta swaps in Android vs iOS) and 5 blended cards on All platforms.
Per-card controls (metric / campaign / D-W-M / compare) work; unpin hides a card into a
dashed restore row. Tokens vendored at `design/tokens/`. Seeded demo data, no LLM, no
build step, Vercel-deployable as-is.

## What's here

| Path | Contents |
| --- | --- |
| `cards/<platform>.cards.json` | The library: **125 prebuilt cards** — amazon 32 · google 34 · flipkart 28 · meta 23 · shopify 5 · all (blended) 3. Every card validates against `card-definition.schema.json` and its `query` against the DSL `query_task` |
| `cards/index.json` | Per-platform counts + default pin sets |
| `cockpit/pins.default.json` | First-run cockpit seed: exec KPIs + exec trend pinned per platform; everything else unpinned in the library |
| `schema/card-definition.schema.json` | A prebuilt card = `card.schema.json` **minus** the runtime `data` payload (data is produced at serve time by executing `query`); adds optional `note` for measurement caveats |
| `schema/` | Vendored: card / catalog / dashboard schemas + `dsl/query_and_act-v1.schema.json` — the repo self-validates |
| `catalog/catalog.json` | The generation source (canonical metric keys, native labels, entities, gold/bronze source) |
| `generator/build.py` | Deterministic generator: catalog in → cards out. `--check` fails CI on drift. **Never hand-edit `cards/`** |

## How a card becomes pixels

1. Cockpit loads `cards/<platform>.cards.json` + the user's pin state (`dashboard.schema.json`
   shape; `cockpit/pins.default.json` seeds first run). Pinned cards render on the dashboard,
   newest pin last; the rest live on the Reports page. Pin/unpin is the **only** user mutation.
2. For each rendered card the backend executes `card.query` — a validated DSL `query_task` —
   against the semantic layer (gold; bronze for keyword/search-term/placement/product grains,
   already declared per report as `source`). Pinned cards are standing views: refresh on the
   platform's sync cadence, stamp `provenance.data_as_of`, label the settled window.
3. Result rows → component props via the aligned repo's `src/lib/queryBinding.js` shapers.
   Definition + data = a full `card.schema.json` card.

## Generation rules (all deterministic, in `build.py`)

- One card per representation per report ("one dataset × one representation"): KPI strip,
  trend, ranked bars, comparison bars, table, and a heatmap where the catalog row says `grid`.
- Defaults: 30d range; D period (Meta weekly/monthly reports default W/M); Compare on for
  KPI/trend; rankings sort by the primary metric (ascending when lower-is-better) with
  `limit: 10`.
- Metric selectors carry the report's full canonical metric set (`{key, label, unit, invert}`),
  native labels verbatim.
- Blended "all" cards are **additive-metrics only** (spend, spend share, MER-with-formula) —
  `measurement.yaml` comparability rules; deliberately no blended-ROAS card.

## Regenerating

```bash
python3 generator/build.py          # rebuild cards/ + cockpit/ + card-definition schema
python3 generator/build.py --check  # CI: fail on drift or invalid cards
```

Catalog changes (new report, metric rename) go into `catalog/catalog.json` — in step with the
basic repo's `contracts/config/primitives.yaml` metric_sources — then regenerate.
