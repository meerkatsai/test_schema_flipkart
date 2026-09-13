# Layer: Task Router
The top of the DSL — every request becomes exactly one of 7 task types (MECE oneOf).
- `contract_task-router-v1` — the 7-intent taxonomy (query | action | diagnosis | simulation | recommendation | alert | workflow)
- `contract_query_and_act-v1` — the query vocabulary (entity/metrics/where/having/time_range) AND the shared action defs (selection, operation, execution_plan) that layer 7 executes
- `contract_diagnose_and_recommend-v1` — diagnosis / simulation / recommendation request+result shapes (evidence-cited, data-quality-gated)
