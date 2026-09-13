# Layer: Semantic Layer
Words → metrics → SQL. No LLM anywhere in this layer.
- `contract_catalog-resolved-plan-v1` — the catalog resolver's output contract
- `catalog/` — resolve.mjs + catalog.json (verbatim): word → concept → binding → MetricFlow metric name
- `metricflow/` — flipkart.yaml (metric registry) + bindings_testdb.yaml (MetricFlow compile shim for the test warehouse; same names/measures as _metrics.yml)
- `warehouse/` — DM gold/bronze DDL + synthetic-data generators (additive facts only, as_of + is_settled, bronze reconciles to gold exactly)
