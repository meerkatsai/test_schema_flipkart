# Layer: Actions
The mutation surface. Nothing executes without a registry binding resolved at
config/plan time (fail closed) + human approval (structural in the contracts).
- `contract_capability-registry-v1` — (platform, entity, operation) → tool chains; mutating tools must declare rollback + verify
- `tools-registry.yaml` — the registry instance (real pinned APIs; flipkart campaign.* deliberately UNBOUND → alert-only)
- `contract_workflows_and_automations-v1` — standing alert (read-only) + workflow (the only autonomous mutator; approval_ref + tool_binding required structurally)
Note: the action_task / resolved_selection / execution_plan definitions live in
layer 1's contract_query_and_act-v1 (shared vocabulary); this layer holds the
binding + standing-process machinery. Not exercised by the reporting harness (read-only).
