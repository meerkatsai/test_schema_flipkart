#!/usr/bin/env python3
"""Report harness CLI — prompt-side query_task in, rendered card + trace out.

  python run_report.py --card exec-kpi [--card campaign-rank ...] [--out out/report.html]
  python run_report.py --query '{"version":"1.0","task_type":"query","task":{...}}' \\
                       --rep dataTable --title "My report"

Cards come from cards/flipkart.cards.json (vendored from meerkatsai/ad-dashboards-prebuilt);
the query on each card IS the DSL query_task — this harness runs the same pipeline the
service would: validate -> resolve (metricflow/flipkart.yaml) -> plan -> SQL -> rows ->
representation payload (card.schema.json shapes) -> HTML. Every stage logs to the trace.
Env: NEON_DSN=postgresql://...
"""
import os, re, ssl, sys, json, copy, argparse, datetime
import pg8000.native

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine.trace import Trace
from engine import resolver, contracts
from engine.presenter import build_payload
from engine.render_html import render_report

HERE = os.path.dirname(os.path.abspath(__file__))


def connect():
    dsn = os.environ.get("NEON_DSN")
    if not dsn:
        sys.exit("NEON_DSN env var required (postgresql://user:pass@host/db)")
    u, p, h, db = re.match(r"postgresql://([^:]+):([^@]+)@([^/]+)/([^?]+)", dsn).groups()
    return pg8000.native.Connection(user=u, password=p, host=h, database=db,
                                    ssl_context=ssl.create_default_context())


def run_rows(con, sql):
    rows = con.run(sql)
    cols = [c["name"] for c in con.columns]
    return [dict(zip(cols, r)) for r in rows]


def run_card(con, card, trace):
    env = card["query"]
    task = env["task"]
    sql_texts = []

    trace.span("route", detail=f" utterance/card '{card['id']}' -> task_type=query (family query_and_act)",
               representation=card["representation"], entity=task["entity"])
    resolver.validate_structural(env, trace)
    resolver.validate_semantic(task, trace)
    resolved = resolver.resolve(task, trace)
    p = resolver.plan(task, resolved, con, trace)

    rep = card["representation"]
    extra = {}

    if rep == "kpiStrip":
        # 3 queries: window totals, daily spark, previous-period totals
        t_task = copy.deepcopy(task); t_task.pop("dimensions", None)
        r_tot = copy.deepcopy(resolved); r_tot = {**resolved, "dims": []}
        sql_tot = resolver.to_sql(r_tot, {**p, "sort": None, "limit": None}, trace, group_by_entity=False)
        sql_texts.append((f"{card['id']} · window totals", sql_tot))
        extra["totals_rows"] = run_rows(con, sql_tot)

        r_spark = {**resolved, "dims": [{"asked": "date", "column": "day"}]}
        sql_spark = resolver.to_sql(r_spark, {**p, "sort": None, "limit": None}, trace, group_by_entity=False)
        sql_texts.append((f"{card['id']} · daily spark", sql_spark))
        extra["spark_rows"] = run_rows(con, sql_spark)
        rows = extra["spark_rows"]

        if p["comparison"]:
            pp = {**p, "start": p["comparison"]["start"], "end": p["comparison"]["end"], "sort": None, "limit": None}
            sql_prev = resolver.to_sql(r_tot, pp, trace, group_by_entity=False)
            sql_texts.append((f"{card['id']} · previous period totals", sql_prev))
            prev = run_rows(con, sql_prev)
            extra["prev_totals"] = prev[0] if prev else {}
            trace.note(f"previous-period totals fetched for deltas ({pp['start']} .. {pp['end']})")
    elif rep == "trendLine":
        if not any(d["asked"] == "date" for d in resolved["dims"]):
            resolved["dims"].insert(0, {"asked": "date", "column": "day"})
            trace.note("trendLine without a date dimension — date added (a trend needs a time axis)")
        sql = resolver.to_sql(resolved, p, trace, group_by_entity=False)
        sql_texts.append((f"{card['id']} · trend", sql))
        rows = run_rows(con, sql)
        if p["comparison"]:
            pp = {**p, "start": p["comparison"]["start"], "end": p["comparison"]["end"]}
            sql_prev = resolver.to_sql(resolved, pp, trace, group_by_entity=False)
            sql_texts.append((f"{card['id']} · previous period trend", sql_prev))
            extra["compare_rows"] = run_rows(con, sql_prev)
    else:
        by_entity = not any(d["asked"] == "date" for d in resolved["dims"])
        # ranked/table/grid defaults: heatmap and table need a limit to stay readable
        if rep in ("heatmap", "dataTable", "barsHorizontal") and not p.get("limit"):
            p["limit"] = 10
            if not p.get("sort"):
                p["sort"] = {"metric": resolved["metrics"][0]["asked"], "direction": "desc"}
            p["settled_only"] = True
            trace.note(f"{rep} without sort/limit — defaulted to top 10 by {p['sort']['metric']} (settled rows only)")
        sql = resolver.to_sql(resolved, p, trace, group_by_entity=by_entity)
        sql_texts.append((f"{card['id']} · {rep}", sql))
        rows = run_rows(con, sql)

    trace.span("execute", detail=f" {sum(1 for _ in rows)} rows returned"
               + (f" (+{len(extra.get('compare_rows', []))} compare rows)" if extra.get("compare_rows") else ""),
               queries=len(sql_texts))

    payload = build_payload(rep, rows, resolved, p, extra)
    ok, errs, _clean = contracts.validate_ui_payload(rep, payload)
    if not ok:
        raise resolver.ResolveError(f"UI contract violation ({rep}Data): " + "; ".join(errs))
    trace.note(f"rows -> {rep} payload — UI CONTRACT GATE: card.schema.json $defs.{rep}Data PASS "
               "(a payload that fails this never reaches the renderer)")

    caveat_texts = [resolver.REG["caveats"][c] for c in resolved["caveats"] if c in resolver.REG["caveats"]]
    if resolved["model"]["layer"] == "bronze":
        caveat_texts.insert(0, resolver.REG["caveats"]["bronze_fallback"])
    return {
        "title": card.get("title", card["id"]),
        "question": card.get("question", ""),
        "source": f"{resolved['model']['layer']}.{resolved['model']['table']}",
        "window": f"{p['start']} .. {p['end']}",
        "provisional_from": p["provenance"]["provisional_from"],
        "payload": payload,
        "caveats": caveat_texts,
    }, sql_texts, p["provenance"]["data_as_of"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--card", action="append", default=[], help="card id from cards/flipkart.cards.json")
    ap.add_argument("--query", help="inline query_task envelope JSON")
    ap.add_argument("--rep", default="dataTable", help="representation for --query")
    ap.add_argument("--title", default="Ad-hoc report")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    library = {c["id"]: c for c in json.load(open(os.path.join(HERE, "cards", "flipkart.cards.json")))}
    jobs = []
    for cid in args.card:
        if cid not in library:
            sys.exit(f"unknown card '{cid}'. known: {', '.join(sorted(library))}")
        jobs.append(library[cid])
    if args.query:
        jobs.append({"id": "adhoc", "title": args.title, "question": "",
                     "representation": args.rep, "query": json.loads(args.query)})
    if not jobs:
        sys.exit("nothing to run — pass --card and/or --query")

    con = connect()
    utter = ", ".join(j["id"] for j in jobs)
    trace = Trace(utterance=f"report run: {utter}")
    cards_out, all_sql, as_of = [], [], None
    status = "ok"
    for job in jobs:
        trace.lines.append(f"\n═══ card {job['id']} ({job['representation']}) ═══")
        try:
            c, sqls, as_of = run_card(con, job, trace)
            cards_out.append(c)
            all_sql += sqls
        except resolver.ResolveError as e:
            status = "refused"
            trace.lines.append(f"      REFUSED: {e}")
    con.close()

    out = args.out or os.path.join(HERE, "out", f"report_{datetime.date.today()}.html")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    title = cards_out[0]["title"] if len(cards_out) == 1 else f"Flipkart Ads report · {len(cards_out)} cards"
    html_doc = render_report(title, cards_out, trace.pretty(), all_sql, as_of)
    open(out, "w").write(html_doc)

    tr = trace.finish(status, {"task_type": "query", "family": "query_and_act"},
                      jobs[0]["query"] if jobs else None, output_ref=out, data_as_of=str(as_of))
    tpath = out.replace(".html", ".trace.json")
    json.dump(tr, open(tpath, "w"), indent=1, default=str)

    print(trace.pretty())
    print(f"\nreport : {out}\ntrace  : {tpath}")


if __name__ == "__main__":
    main()
