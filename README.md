# test_schema_flipkart

Production test of the Meerkats layered architecture, scoped to **Flipkart Ads**:
schema → synthetic warehouse → query pipeline → charts, with contract validation
and a task-trace + data-lineage log at every stage.

## Layout

| Path | Layer | What it is |
|---|---|---|
| `meerkats_flipkart_schema-v1.schema.json` | 3 | The consolidated Flipkart platform contract (dictionary + structure + capabilities + diagnostics + DM warehouse, invariants enforced structurally) |
| `contracts/` | 1 | The DSL contracts, vendored verbatim: task-router, query_and_act, diagnose_and_recommend, workflows_and_automations, task-trace, catalog-resolved-plan |
| `catalog/` | 2 | The semantic catalog: `resolve.mjs` + `generated/catalog.json` (verbatim; word → concept → MetricFlow metric binding) |
| `metricflow/` | 2 | `flipkart.yaml` (metric registry) + `bindings_testdb.yaml` (MetricFlow compile shim: same metric names/measures as `_metrics.yml`, compiled onto the test warehouse) |
| `warehouse/` | DM | DDL + synthetic-data generators: gold (account/campaign daily + entities) and bronze (adgroup/keyword/search-term/placement/FSN/wallet), T+28 `is_settled`, bronze reconciles to gold exactly |
| `engine/` | — | resolver, contract validation (jsonschema 2020-12, schemas registered by `$id`), presenter (card payload shapes), HTML renderer, trace |
| `schema/card.schema.json` | 8 | The data→UI contract (vendored from ad-dashboards-prebuilt); payloads are gated against `#/$defs/<representation>Data` before render |
| `cards/flipkart.cards.json` | 8 | The 28 prebuilt Flipkart cards — each card's `query` is a baked DSL query_task |
| `vendor-cockpit/` | 8 | The cockpit demo UI (vanilla, seeded data) |
| `ask.py` | — | NL flow: utterance → router envelope → contracts → catalog → MetricFlow → SQL → card, with data lineage |
| `run_report.py` | — | Card flow: prebuilt card id → same pipeline, no router |
| `ENGINE.md` | — | Engine details + run instructions |

## Run

```bash
export NEON_DSN='postgresql://<user>:<password>@<host>/Flipkart_ads_test?sslmode=require'
pip install pyyaml pg8000 jsonschema referencing

python3 run_report.py --card exec-kpi --card campaign-rank      # prebuilt cards
python3 ask.py --utterance "..." --envelope '<router JSON>' --rep periodTable
```

Outputs land in `out/` (gitignored): the HTML report with the query-formation log,
data-lineage panel and executed SQL, plus the task-trace JSON (validates against
`contract_task-trace-v1`) and the catalog-resolved-plan JSON.
