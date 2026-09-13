# Layer: Guardrails
The record-keeping guardrails live here; the PREVENTIVE guardrails are deliberately
distributed and structural, enforced where they bite:
- additionalProperties:false everywhere (no field smuggling) — layer 1 contracts
- approval-before-action, frozen selections, drift re-approval — layer 1 (query_and_act) + layer 7
- fail-closed tool binding (no binding = refused at creation) — layer 7 registry
- data-quality-before-causes — layer 4 diagnostics check vocabulary
- T+28 settlement exclusion for rankings/verdicts — semantic + presentation layers
In this folder:
- `contract_task-trace-v1` — observability: one request end-to-end (spans, artifact refs, replayable via data_as_of)
- `contract_audit-log-v1` — the append-only, hash-chained system of record for mutations/approvals/config changes (seq gap detection; not used by read-only reporting)
