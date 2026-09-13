#!/usr/bin/env python3
"""Prebuilt card library generator — catalog in, cards out. DETERMINISTIC: no model anywhere.

Reads catalog/catalog.json (canonical metric keys, entities, gold/bronze source) and expands
every report into its concrete cards — one card per representation, per the design rule "one
dataset x one representation, never mixed". Each card carries its BAKED query_task (the DSL
instance the backend executes on the platform's sync cadence); users only pin/unpin in the
cockpit. Regenerate after any catalog change; never hand-edit cards/.

  python3 generator/build.py            # regenerate cards/ + cockpit/ + card-definition schema
  python3 generator/build.py --check    # exit 1 if outputs are stale (CI)

Also emits schema/card-definition.schema.json: a prebuilt card = card.schema.json MINUS the
runtime `data` payload (data is produced at serve time by executing `query`).
"""
import copy, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PERIOD_DIM = {"D": "date", "W": "week", "M": "month"}
SUFFIX = {"kpiStrip": ("kpi", "KPIs"), "trendLine": ("trend", "Trend"),
          "barsHorizontal": ("rank", "Ranking"), "barsVertical": ("bars", "Comparison"),
          "dataTable": ("table", "Table"), "heatmap": ("grid", "Grid")}
TIME_BASED = {"kpiStrip", "trendLine", "barsVertical"}
DEFAULT_PERIOD = {"daily": "D", "weekly": "W", "monthly": "M"}


def representations(report):
    """Parse the catalog's prose representation into the concrete card list."""
    text = report["representation"].lower()
    reps = []
    if "kpi strip" in text:
        reps.append("kpiStrip")
    if "table" in text:
        reps.append("dataTable")
    if "horizontal bar" in text or "horizontal ranking" in text:
        reps.append("barsHorizontal")
    if "vertical bar" in text or "side-by-side" in text:
        reps.append("barsVertical")
    if "trend" in text:
        reps.append("trendLine")
    if report.get("grid"):
        reps.append("heatmap")
    return reps


def selector(report, prefer_invert=False):
    opts = [{"value": m["key"], "label": m["label"],
             **({"unit": m["unit"]} if m.get("unit") else {}),
             **({"invert": True} if m.get("invert") else {})} for m in report["metrics"]]
    value = opts[0]["value"]
    if prefer_invert:
        inv = next((o for o in opts if o.get("invert")), None)
        if inv:
            value = inv["value"]
    return {"value": value, "options": opts}


def build_query(report, rep, period, primary):
    task = {"entity": report["entity"],
            "metrics": [m["key"] for m in report["metrics"]],
            "time_range": {"type": "relative", "value": 30, "unit": "day"}}
    dims = []
    if rep in TIME_BASED:
        dims.append(PERIOD_DIM[period])
    if rep in ("dataTable", "heatmap"):
        dims += [d["key"] for d in report.get("dimensions", [])]
    if dims:
        task["dimensions"] = dims
    if rep in ("kpiStrip", "trendLine"):
        task["comparison"] = {"metric": primary, "baseline": "previous_period"}
    if rep in ("barsHorizontal", "dataTable"):
        invert = any(m["key"] == primary and m.get("invert") for m in report["metrics"])
        task["sort"] = {"metric": primary, "direction": "asc" if invert else "desc"}
        task["limit"] = 10
    return {"version": "1.0", "task_type": "query", "task": task}


def build_card(platform, report, rep):
    sfx, sfx_label = SUFFIX[rep]
    period = DEFAULT_PERIOD.get(report["id"], "D")
    sel = selector(report, prefer_invert=(rep == "heatmap"))
    primary = sel["value"] if rep in ("trendLine", "barsHorizontal", "barsVertical", "heatmap") \
        else report["metrics"][0]["key"]
    controls = {"dateRange": {"preset": "30d"}}
    if rep in TIME_BASED:
        controls["period"] = period
        controls["compare"] = rep != "barsVertical"
    if rep in ("trendLine", "barsHorizontal", "barsVertical", "heatmap"):
        controls["metricSelector"] = sel
    card = {"id": f"{report['id']}-{sfx}",
            "platform": platform,
            "catalogRef": {"platform": platform, "reportId": report["id"]},
            "title": f"{report['title']} — {sfx_label}",
            "question": report["question"],
            "representation": rep,
            "query": build_query(report, rep, period, primary),
            "controls": controls,
            "pinned": False,
            "csvDownload": True}
    if report.get("note"):
        card["note"] = report["note"]
    return card


def all_platform_cards():
    """Blended cross-platform cards. Additive metrics only side-by-side; measurement.yaml
    comparability rules forbid charting self-reported ROAS across platforms without the
    regime split — so no blended ROAS card exists here on purpose."""
    tr = {"type": "relative", "value": 30, "unit": "day"}
    note = ("cross-platform card — contracts/config/measurement.yaml comparability rules apply; "
            "spend is additive and safe, revenue bases differ, never blend self-reported ROAS")
    return [
        {"id": "all-kpi", "platform": "all", "title": "Blended Performance — KPIs",
         "question": "What did we spend across every platform and what did it return blended?",
         "representation": "kpiStrip",
         "query": {"version": "1.0", "task_type": "query",
                   "task": {"entity": "account", "metrics": ["spend", "mer"],
                            "dimensions": ["date"], "time_range": tr,
                            "comparison": {"metric": "spend", "baseline": "previous_period"}}},
         "controls": {"dateRange": {"preset": "30d"}, "period": "D", "compare": True},
         "pinned": False, "csvDownload": True, "note": note + "; MER always printed with its formula"},
        {"id": "all-spend-split", "platform": "all", "title": "Spend by Platform — Comparison",
         "question": "How is ad spend distributed across platforms?",
         "representation": "barsVertical",
         "query": {"version": "1.0", "task_type": "query",
                   "task": {"entity": "account", "metrics": ["spend", "spend_share"],
                            "dimensions": ["platform"], "time_range": tr}},
         "controls": {"dateRange": {"preset": "30d"},
                      "metricSelector": {"value": "spend",
                                         "options": [{"value": "spend", "label": "Spend", "unit": "inr"},
                                                     {"value": "spend_share", "label": "Spend share", "unit": "pct"}]}},
         "pinned": False, "csvDownload": True, "note": note},
        {"id": "all-spend-trend", "platform": "all", "title": "Blended Spend — Trend",
         "question": "How is total ad spend moving day by day, split by platform?",
         "representation": "trendLine",
         "query": {"version": "1.0", "task_type": "query",
                   "task": {"entity": "account", "metrics": ["spend"],
                            "dimensions": ["date", "platform"], "time_range": tr,
                            "comparison": {"metric": "spend", "baseline": "previous_period"}}},
         "controls": {"dateRange": {"preset": "30d"}, "period": "D", "compare": True,
                      "metricSelector": {"value": "spend",
                                         "options": [{"value": "spend", "label": "Spend", "unit": "inr"}]}},
         "pinned": False, "csvDownload": True, "note": note},
    ]


def card_definition_schema():
    """card.schema.json minus the runtime data payload (+ optional note)."""
    s = json.loads((ROOT / "schema/card.schema.json").read_text())
    d = copy.deepcopy(s)
    d["$id"] = "https://meerkats.ai/schemas/ad-dashboards/card-definition.schema.json"
    d["title"] = "Prebuilt report card (definition)"
    d["description"] = ("A PREBUILT card: everything a card is, MINUS the runtime `data` payload. "
                        "The backend produces data by executing `query` on the platform's sync cadence; "
                        "definition + data = a full card per card.schema.json. Users pin/unpin these in "
                        "the cockpit; the library itself is generated from the catalog and never hand-edited.")
    d["required"] = [r for r in d["required"] if r != "data"]
    d["properties"]["data"]["description"] = "ABSENT on prebuilt definitions — produced at serve time by executing `query`."
    d["properties"]["note"] = {"type": "string", "description": "measurement/availability caveat rendered as a footnote chip"}
    return d


PINS_DEFAULT = {  # first-run cockpit: exec KPIs + exec trend pinned per platform, rest unpinned in the library
    "all": ["all-kpi", "all-spend-split"],
    "amazon": ["exec-kpi", "exec-trend"],
    "flipkart": ["exec-kpi", "exec-trend"],
    "google": ["exec-kpi", "exec-trend"],
    "meta": ["daily-kpi", "daily-trend"],
    "shopify": ["exec-kpi", "exec-trend"],
}


def build_all():
    catalog = json.loads((ROOT / "catalog/catalog.json").read_text())
    out = {}
    for platform in ["amazon", "flipkart", "google", "meta", "shopify"]:
        cards = []
        for report in catalog[platform]["reports"]:
            for rep in representations(report):
                cards.append(build_card(platform, report, rep))
        out[platform] = cards
    out["all"] = all_platform_cards()
    # apply default pins
    for platform, ids in PINS_DEFAULT.items():
        for c in out[platform]:
            if c["id"] in ids:
                c["pinned"] = True
    files = {}
    total = 0
    for platform, cards in out.items():
        files[ROOT / f"cards/{platform}.cards.json"] = json.dumps(cards, indent=1, ensure_ascii=False) + "\n"
        total += len(cards)
    files[ROOT / "cards/index.json"] = json.dumps(
        {p: {"cards": len(cs), "pinned_by_default": PINS_DEFAULT[p]} for p, cs in out.items()},
        indent=1, ensure_ascii=False) + "\n"
    files[ROOT / "cockpit/pins.default.json"] = json.dumps(PINS_DEFAULT, indent=1, ensure_ascii=False) + "\n"
    files[ROOT / "schema/card-definition.schema.json"] = json.dumps(card_definition_schema(), indent=1, ensure_ascii=False) + "\n"
    return files, total


def validate(files):
    try:
        import jsonschema
        from referencing import Registry, Resource
    except ImportError:
        print("jsonschema not installed — skipping validation (CI must not skip)")
        return
    defn = json.loads(files[ROOT / "schema/card-definition.schema.json"])
    qa = json.loads((ROOT / "schema/dsl/query_and_act-v1.schema.json").read_text())
    card_s = json.loads((ROOT / "schema/card.schema.json").read_text())
    reg = Registry().with_resources([(s["$id"], Resource.from_contents(s)) for s in (defn, qa, card_s)])
    v = jsonschema.Draft202012Validator(defn, registry=reg)
    qv = jsonschema.Draft202012Validator({"$ref": "https://meerkats.ai/schemas/query_and_act/v1.json#/$defs/query_task"}, registry=reg)
    n = bad = 0
    for path, content in files.items():
        if not path.name.endswith(".cards.json"):
            continue
        for c in json.loads(content):
            n += 1
            for err in list(v.iter_errors(c))[:1]:
                bad += 1
                print(f"INVALID {path.name}/{c['id']}: {err.message[:120]}")
            for err in list(qv.iter_errors(c["query"]))[:1]:
                bad += 1
                print(f"INVALID QUERY {path.name}/{c['id']}: {err.message[:120]}")
    if bad:
        sys.exit(f"{bad} invalid card(s)")
    print(f"validated {n} cards: all pass card-definition + query_task schemas")


def main():
    check = "--check" in sys.argv
    files, total = build_all()
    stale = 0
    for path, content in files.items():
        current = path.read_text() if path.exists() else None
        if current != content:
            stale += 1
            if not check:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
    validate(files)
    if check and stale:
        sys.exit(f"{stale} output(s) stale — run generator/build.py")
    print(f"{total} prebuilt cards across {len(files) - 3} platform files; {stale} file(s) {'stale' if check else 'written'}")


if __name__ == "__main__":
    main()
