# Flipkart Report Engine — production test harness

Query-to-chart pipeline over the `Flipkart_ads_test` Neon database, exercising the
full layer stack: **DSL query_task → metricflow registry → bronze/gold SQL → rows →
card payload → HTML report**, with a task-trace log of every decision.

## The warehouse it runs on (Neon · Flipkart_ads_test)

| Layer | Table | Grain | Rows |
|---|---|---|---|
| gold | `gold_flipkart_account_daily` | day | 90 |
| gold | `gold_flipkart_campaign_daily` | campaign × day | 742 |
| gold | `gold_flipkart_entities_current` | campaign snapshot | 10 |
| bronze | `bronze_flipkart_adgroup_daily` | ad group × day | 1,484 |
| bronze | `bronze_flipkart_keyword_daily` | keyword × match_type × day (manual PLA only) | 1,300 |
| bronze | `bronze_flipkart_search_term_daily` | search term × day (PLA) | 3,942 |
| bronze | `bronze_flipkart_placement_daily` | placement × day | 3,710 |
| bronze | `bronze_flipkart_fsn_daily` | FSN × day (PLA) | 1,971 |
| bronze | `bronze_flipkart_wallet_daily` | account wallet day | 90 |

Bronze disaggregates gold with exact reconciliation (SUM(children) == parent for
every additive fact). All tables carry `workspace_id`, `as_of`, `is_settled`
(T+28 window ⇒ provisional). Additive facts only — every ratio computes at read.

## Files

| Path | What |
|---|---|
| `metricflow/flipkart.yaml` | THE metric registry: semantic models (entity → gold/bronze table), metric → SUM() expression + unit + native label + invert + caveat, dimension words → columns. A metric absent here is refused, never improvised. |
| `engine/resolver.py` | validate_structural → validate_semantic → resolve → plan → SQL. Logs every binding, the bronze fallback, the widest-default time rule, comparison-window shift, and the settlement policy (ranked queries = settled rows only). |
| `engine/presenter.py` | rows → representation payloads matching `card.schema.json` `$defs` (kpiStrip / trendLine / barsHorizontal / barsVertical / dataTable / heatmap) + `fmtBy` formatting parity (₹ K/L/Cr, ×, %). |
| `engine/render_html.py` | payloads → standalone HTML in the ad-dashboards-prebuilt design system; provenance line on every card; query-formation log + executed SQL rendered as a panel. |
| `engine/trace.py` | task-trace-v1-shaped span log (route … present), emitted as pretty text + JSON. |
| `cards/flipkart.cards.json` | The 28 prebuilt cards (vendored from meerkatsai/ad-dashboards-prebuilt) — each card's `query` is the DSL query_task the pipeline executes. |
| `run_report.py` | CLI entry point. |

## Run

```bash
export NEON_DSN='postgresql://<user>:<password>@<host>/Flipkart_ads_test?sslmode=require'

# prebuilt cards (any of the 28 ids in cards/flipkart.cards.json)
python3 run_report.py --card exec-kpi --card campaign-rank --card placement-grid

# ad-hoc DSL query
python3 run_report.py --rep dataTable --title "Top search terms" --query '{
  "version":"1.0","task_type":"query",
  "task":{"entity":"search","metrics":["clicks","ctr","spend","roi"],
          "dimensions":["search_term"],
          "sort":{"metric":"clicks","direction":"desc"},"limit":10,
          "time_range":{"type":"relative","value":30,"unit":"day"}}}'
```

Outputs land in `out/`: `<name>.html` (the report, incl. the log panel) and
`<name>.trace.json` (task-trace-v1-shaped machine log).

Python deps: `pyyaml`, `pg8000` (pure-Python Postgres driver).

## Contract behaviors under test

- **Name authority**: `acos` refuses at validate_semantic ("not modeled — the engine
  never improvises a formula") before any SQL runs.
- **Bronze fallback is said out loud**: keyword/search/placement/sku/budget grains log
  and render the fallback caveat.
- **T+28 settlement**: ranked/top-N queries filter `is_settled = true`; trends keep
  provisional rows and stamp `provisional from` on the card.
- **ROI companion rule**: `roi` never renders without `direct_roi` beside it, and the
  halo caveat prints on the card.
- **Wallet levels**: balance-style metrics aggregate as AVG, never SUM across days.
- **Provenance**: every card carries source table · window · as_of · provisional-from.
