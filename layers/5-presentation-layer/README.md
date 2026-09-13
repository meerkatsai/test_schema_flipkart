# Layer: Presentation
Data → charts. No LLM at render time; controls are deterministic query rewrites.
- `card.schema.json` — THE data→UI contract: 7 payload shapes ($defs.<representation>Data), unit vocabulary (inr|num|pct|x), delta semantics, provenance. Payloads are gated against it before render.
- `cards/flipkart.cards.json` — 28 prebuilt cards; each card's `query` is a baked DSL query_task
- `cockpit-demo/` — the vanilla cockpit UI (pin/unpin, per-card controls, seeded data)
