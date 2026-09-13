#!/usr/bin/env python3
"""The ARCHITECTURE pipeline, end to end, on the real artifacts:

  utterance ─(LLM router: task-router-v1)→ envelope
           ─(contracts/*.schema.json: REAL jsonschema validation)→ validated task
           ─(catalog/resolve.mjs + catalog.json: THE layer-2 resolver, verbatim)→ catalog_resolved_plan
           ─(validated against contract_catalog-resolved-plan-v1)→
           ─(MetricFlow compile: metricflow/bindings_testdb.yaml — same metric names,
             measures, aggs as inputs/_metrics.yml, compiled onto the test warehouse)→ SQL
           ─(Neon)→ rows ─(card.schema.json payload)→ HTML card + DATA LINEAGE + trace

The LLM (the router) supplies: the classification, the DSL envelope, and the
representation choice — passed in via --envelope/--rep/--routing-note, because in this
harness the calling LLM IS the router. Everything after that point is deterministic.

  python3 ask.py --utterance "show me the spend report Day on Day for the last 7 days" \\
      --envelope '<router-emitted JSON>' --rep periodTable --routing-note "..." \\
      [--out out/x.html]

Env: NEON_DSN.
"""
import os, re, ssl, sys, json, argparse, datetime, subprocess
import yaml
import pg8000.native

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from engine.trace import Trace, task_digest
from engine import contracts
from engine.presenter import build_payload, period_table
from engine.render_html import render_report

CATALOG = json.load(open(os.path.join(HERE, "catalog", "generated", "catalog.json")))
MF = yaml.safe_load(open(os.path.join(HERE, "metricflow", "bindings_testdb.yaml")))
WORKSPACE = "ws_flipkart_demo"
WORKSPACE_PLATFORMS = ["flipkart"]  # company_operations: platforms.ads — unlisted platforms are refused


def connect():
    dsn = os.environ.get("NEON_DSN") or sys.exit("NEON_DSN required")
    u, p, h, db = re.match(r"postgresql://([^:]+):([^@]+)@([^/]+)/([^?]+)", dsn).groups()
    return pg8000.native.Connection(user=u, password=p, host=h, database=db,
                                    ssl_context=ssl.create_default_context())


def run_rows(con, sql):
    rows = con.run(sql)
    cols = [c["name"] for c in con.columns]
    return [dict(zip(cols, r)) for r in rows]


def concept_of(word):
    w = word.lower().strip()
    if w in CATALOG["concepts"]:
        return w, CATALOG["concepts"][w].get("says", [])
    for name, c in CATALOG["concepts"].items():
        if w in [s.lower() for s in c.get("says", [])]:
            return name, c.get("says", [])
    return None, []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--utterance", required=True)
    ap.add_argument("--envelope", required=True, help="router-emitted task envelope JSON")
    ap.add_argument("--rep", default="dataTable")
    ap.add_argument("--routing-note", default="")
    ap.add_argument("--title", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    envelope = json.loads(args.envelope)
    task = envelope["task"]
    trace = Trace(utterance=args.utterance)
    lineage, sql_texts = [], []

    # ── 1. route (LLM = task router) ─────────────────────────────────────────
    trace.span("route", detail=" LLM router classified the utterance (task-router-v1 intent taxonomy)",
               task_type=envelope["task_type"], family="query_and_act", confidence=0.98)
    if args.routing_note:
        for line in args.routing_note.split("|"):
            trace.note(line.strip())

    # ── 2. generate (LLM emits the DSL instance — schema-constrained) ────────
    digest = task_digest(envelope)
    trace.span("generate", detail=" router emitted the DSL envelope (fields from lookups, never free-typed)",
               envelope=envelope, representation=args.rep,
               task_ref={"conforms_to": contracts.TASK_ROUTER, "digest": digest})
    trace.note(f"task instance content-addressed: {digest} — the task_instances PK; "
               "identical tasks in any later trace dedupe to this row")
    # persist the instance the way the DB would: one file per digest
    art_dir = os.path.join(HERE, "out", "artifacts")
    os.makedirs(art_dir, exist_ok=True)
    json.dump(envelope, open(os.path.join(art_dir, digest.replace("sha256:", "sha256-") + ".json"), "w"), indent=1)

    # ── 3. validate_structural — REAL contract files, jsonschema 2020-12 ─────
    ok, errs = contracts.validate(contracts.TASK_ROUTER, envelope)
    if not ok:
        trace.span("validate_structural", "error", " contract_task-router-v1: FAIL", errors=errs)
        sys.exit(trace.pretty())
    trace.span("validate_structural",
               detail=" contract_task-router-v1.schema.json (oneOf → query_task via query_and_act-v1): PASS",
               schemas_registered=len(contracts.loaded()))

    # ── 4. resolve — the layer-2 catalog, VERBATIM (catalog/resolve.mjs) ─────
    r = subprocess.run(["node", os.path.join(HERE, "catalog", "resolve.mjs"), json.dumps(task)],
                       capture_output=True, text=True, check=True)
    plan_doc = json.loads(r.stdout)
    trace.span("resolve", detail=f" catalog/resolve.mjs (build {plan_doc['build_id']}) → "
               f"resolved={plan_doc['resolved']} fanout={plan_doc['fanout']} plans={len(plan_doc['plans'])}",
               build_id=plan_doc["build_id"])
    for m in task["metrics"]:
        cname, says = concept_of(m)
        trace.note(f"word '{m}' → concept '{cname}' (says: {', '.join(says[:4])})")
    for p_ in plan_doc["plans"]:
        for m in p_["metrics"]:
            trace.note(f"binding: '{m['asked']}' @ platform={p_['platform']} → MetricFlow metric '{m['use']}'"
                       + (f" — {m['why']}" if m.get("why") else ""))
    for c in plan_doc.get("caveats", []):
        trace.note(f"CAVEAT [{c['severity']}] {c['text'][:120]}")
    for u in plan_doc.get("unresolved", []):
        trace.note(f"UNRESOLVED [{u['kind']}] {u['what']} '{u['name']}': {u['why']}")

    # ── 5. validate_semantic — plan validates against catalog-resolved-plan-v1
    ok, errs = contracts.validate(contracts.CATALOG_PLAN, plan_doc)
    if not ok:
        trace.span("validate_semantic", "error", " contract_catalog-resolved-plan-v1: FAIL", errors=errs)
        sys.exit(trace.pretty())
    if not plan_doc["resolved"]:
        trace.span("validate_semantic", "error", " catalog refused the task (with reasons, before any SQL)")
        sys.exit(trace.pretty())
    trace.span("validate_semantic", detail=" contract_catalog-resolved-plan-v1.schema.json: PASS")

    # ── 6. plan — MetricFlow compile (bindings_testdb.yaml) + time window ────
    con = connect()
    b = con.run("SELECT max(day), max(as_of), min(day) FILTER (WHERE NOT is_settled) FROM gold_flipkart_campaign_daily")[0]
    max_day, as_of, prov_from = b
    tr = task.get("time_range", {"type": "relative", "value": 30, "unit": "day"})
    days = tr.get("value", 30) * {"day": 1, "week": 7, "month": 30, "quarter": 90, "year": 365}.get(tr.get("unit", "day"), 1) \
        if tr.get("type") == "relative" else 30
    start, end = max_day - datetime.timedelta(days=days - 1), max_day

    cplan = plan_doc["plans"][0]
    model = MF["semantic_models"][cplan["semantic_model"]]
    exprs, cols, headers = [], [], []
    group_cols = []
    for g in cplan["group_by"]:
        col = model["dimension_map"].get(g, g)
        group_cols.append(col)
        cols.append(f"{col} AS {g}")
    if cplan["time_asked"]:
        tcol = model["time_dimension"]["test"]
        group_cols.append(tcol)
        cols.append(f"{tcol} AS day")
    mf_metrics = []
    for m in cplan["metrics"]:
        spec = MF["metrics"][m["use"]]
        mf_metrics.append({"asked": m["asked"], "use": m["use"], **spec})
        exprs.append(f"{spec['compiled']} AS {m['asked']}")
        cname, _ = concept_of(m["asked"])
        chain = [
            f"user said: '{m['asked']}' (in: \"{args.utterance}\")",
            f"catalog concept: '{cname}' (catalog.yaml concepts — build {plan_doc['build_id']})",
            f"catalog binding: concept '{cname}' + platform={cplan['platform']} → '{m['use']}'"
            + (f" ({m['why']})" if m.get("why") else ""),
            f"MetricFlow metric: {m['use']} — type={spec['mf'].get('type')}"
            + (f", measure={spec['mf'].get('measure')} (agg={spec['mf'].get('agg')}, expr={spec['mf'].get('expr')})"
               if spec['mf'].get('measure') else "")
            + f" [label '{spec['mf'].get('label', m['use'])}', defined in inputs/_metrics.yml]",
            f"semantic model: {cplan['semantic_model']} → prod {model['prod_table']} (from inputs/_semantic_models.yml)",
            f"test warehouse: {model['test_table']} (Flipkart_ads_test @ Neon)"
            + (f" — {spec['compile_note']}" if spec.get("compile_note") else ""),
            f"compiled SQL: {spec['compiled']}",
            f"display: '{spec['display_label']}' [{spec['unit']}] (dictionary pack: native Flipkart term)",
        ]
        lineage.append((m["asked"], chain))
        # companion rule (dictionary: ROI never renders without Direct ROI)
        comp = spec.get("companion")
        if comp and not any(x["use"] == comp for x in mf_metrics):
            cs = MF["metrics"][comp]
            mf_metrics.append({"asked": "direct_roi", "use": comp, **cs})
            exprs.append(f"{cs['compiled']} AS direct_roi")
            trace.note(f"COMPANION RULE: '{m['use']}' never renders alone — adding '{comp}'")

    where = [f"workspace_id = '{WORKSPACE}'",
             f"{model['time_dimension']['test']} BETWEEN '{start}' AND '{end}'"]
    for w in task.get("where", []):
        if w["dimension"] == "platform":
            continue  # consumed by the catalog; test warehouse is single-platform
        col = model["dimension_map"].get(w["dimension"], w["dimension"])
        where.append(f"{col} = '{w['value']}'")

    sql = (f"SELECT {', '.join(cols + exprs)}\nFROM {model['test_table']}\nWHERE "
           + "\n  AND ".join(where)
           + (f"\nGROUP BY {', '.join(group_cols)}" if group_cols else "")
           + (f"\nORDER BY {group_cols[-1]}" if group_cols else ""))
    sql_texts.append(("compiled query", sql))
    trace.span("plan", detail=f" window {start} .. {end} (anchored on data max_day); "
               f"MetricFlow compile → {model['test_table']}",
               window=[str(start), str(end)], provisional_from=str(prov_from),
               grain=cplan["grain"], time_dimension=model["time_dimension"])
    if prov_from and prov_from <= end:
        trace.note(f"T+28 settlement: days ≥ {prov_from} are provisional (is_settled=false) — labeled, not hidden")

    # ── 7. execute ────────────────────────────────────────────────────────────
    rows = run_rows(con, sql)
    con.close()
    trace.span("execute", detail=f" {len(rows)} rows from {model['test_table']}", rows=len(rows))

    # ── 8. present (payload per card.schema.json, DoD mechanics in the renderer)
    first = mf_metrics[0]
    if args.rep == "periodTable":
        payload = period_table(rows, unit=first["unit"], name_key=cplan["group_by"][0] if cplan["group_by"] else "name")
        trace.note("representation periodTable: DoD deltas are PERIOD MECHANICS — computed per cell in the "
                   "presentation layer (value + Δ vs previous day + whole-period Δ), never stored in the warehouse")
    else:
        resolved_shim = {"metrics": [{"asked": m["asked"], "expr": m["compiled"], "unit": m["unit"],
                                      "label": m["display_label"], "invert": False} for m in mf_metrics],
                         "dims": [], "model": {"layer": "gold", "table": model["test_table"], "name_dim": None},
                         "caveats": []}
        payload = build_payload(args.rep, rows, resolved_shim, {"sort": task.get("sort")}, {})

    trace.lines.append(f"       » payload shape: card.schema.json $defs.{args.rep}Data — handed to the chart layer "
                       f"(ad-dashboards-prebuilt renderer contract)")

    # trace itself must validate against contract_task-trace-v1
    tdoc = trace.finish("ok", {"task_type": envelope["task_type"], "family": "query_and_act", "confidence": 0.98},
                        envelope, data_as_of=str(as_of))
    ok, errs = contracts.validate("https://meerkats.ai/schemas/task-trace/v1.json", tdoc)
    trace.lines.append(f"       » task-trace self-check: trace document validates against contract_task-trace-v1: "
                       + ("PASS" if ok else f"FAIL {errs}"))
    tdoc["spans"] = trace.spans  # refresh after self-check note

    card = {"title": args.title or f"Spend — Day on Day · last {days} days",
            "question": args.utterance,
            "source": f"{model['test_table']} (prod: {model['prod_table']} via MetricFlow {cplan['semantic_model']})",
            "window": f"{start} .. {end}",
            "provisional_from": str(prov_from),
            "payload": payload,
            "caveats": [c["text"] for c in plan_doc.get("caveats", [])] +
                       ([f"T+28 settlement: values on/after {prov_from} are provisional (is_settled=false)."]
                        if prov_from and prov_from <= end else [])}

    out = args.out or os.path.join(HERE, "out", "ask_report.html")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w").write(render_report(card["title"], [card], trace.pretty(), sql_texts, as_of, lineage=lineage))
    json.dump(tdoc, open(out.replace(".html", ".trace.json"), "w"), indent=1, default=str)
    json.dump(plan_doc, open(out.replace(".html", ".catalog-plan.json"), "w"), indent=1, default=str)

    print(trace.pretty())
    print("\n── DATA LINEAGE ──")
    for metric, chain in lineage:
        print(f"\n{metric}:")
        for i, step in enumerate(chain):
            print(f"  {i+1}. {step}")
    print(f"\nreport : {out}\ntrace  : {out.replace('.html', '.trace.json')}\nplan   : {out.replace('.html', '.catalog-plan.json')}")


if __name__ == "__main__":
    main()
