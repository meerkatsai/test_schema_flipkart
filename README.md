# test_schema_flipkart

`meerkats_flipkart_schema-v1.schema.json` — the Flipkart Ads platform contract
(JSON Schema draft 2020-12): one Flipkart-scoped document consolidating the four
platform_heuristics pack contracts (dictionary, structure, capabilities,
diagnostics) and the DM warehouse contract (bronze/gold), with Flipkart's
invariants enforced structurally:

- platform const `flipkart`; headline efficiency = catalog concept `roas`, DISPLAYED as **ROI** (never ROAS/ACOS)
- `operations.campaign` is const `[]` — no public ads API → every campaign.* fails closed, ads automations are **alert-only**
- the one mutable surface: `listing.set_price` (Marketplace Seller API v3, batch ≤ 10)
- every ads simulation lever is `availability: unavailable` → ads recommendations are advisory by construction
- attribution: last-touch, 28-day click / 7-day view; T+28 settlement (`is_settled`), ROI verdicts at T+14+
- gold facts are ADDITIVE ONLY (ratio columns are a schema violation); direct/indirect revenue split never pre-collapsed

Validated against the real flipkart pack files; six fail-closed negative tests
(campaign gaining an operation, ROI relabeled ROAS, a bindable ads lever, a ratio
stored in gold, platform change, absent-block removal) all reject.
