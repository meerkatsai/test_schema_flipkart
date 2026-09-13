# Layer: Company Operations
Per-workspace (client) knowledge: which platforms they run, account ids, targets
(target ROI/ACOS), roles + approval routing, PII policy, brand guidelines.
- `contract_company-operations-v1` — the per-workspace document contract
The test harness uses this informally today (ws_flipkart_demo is flipkart-only,
which is why the router injects platform=flipkart); a filled instance document
for the demo workspace is the known gap.
