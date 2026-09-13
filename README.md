# test_schema_flipkart

Production test of the Meerkats layered architecture, scoped to **Flipkart Ads**:
schema → synthetic warehouse → query pipeline → charts, with contract validation
and a task-trace + data-lineage log at every stage.

## Layout — schemas separated by layer

```
layers/
  1-task-router/          contract_task-router-v1 · contract_query_and_act-v1 · contract_diagnose_and_recommend-v1
  2-semantic-layer/       contract_catalog-resolved-plan-v1 · catalog/ (resolve.mjs + catalog.json)
                          metricflow/ (registry + test-DB compile shim) · warehouse/ (gold+bronze DDL & generators)
  3-company-operations/   contract_company-operations-v1 (per-workspace knowledge)
  4-platform-heuristics/  contract_platform-{dictionary,structure,capabilities,diagnostics}-v1
                          meerkats_flipkart_schema-v1 (the consolidated Flipkart contract)
  5-presentation-layer/   card.schema.json (the data→UI contract) · cards/ (28 prebuilt) · cockpit-demo/
  6-guardrails/           contract_task-trace-v1 (observability) · contract_audit-log-v1 (hash-chained record)
                          + README: the preventive guardrails are structural, distributed across layers
  7-actions/              contract_capability-registry-v1 · tools-registry.yaml · contract_workflows_and_automations-v1
engine/                   resolver · contract gates (15 schemas registered by $id) · presenter · renderer · trace
ask.py                    NL flow: utterance → router → contracts → catalog → MetricFlow → SQL → card (+ lineage)
run_report.py             card flow: prebuilt card id → same pipeline, no router
```

Each layer folder carries its own README. Cross-layer rules: the semantic layer is
the single name authority; action defs (selection/operation/execution_plan) live in
layer 1's query_and_act as shared vocabulary and are executed through layer 7.

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
