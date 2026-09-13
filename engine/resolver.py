"""query_task -> resolved plan -> SQL. Every decision is logged to the Trace.

Pipeline (mirrors the production layer order):
  validate_structural : envelope shape (query_and_act-v1 subset)
  validate_semantic   : every metric/dimension must resolve in the registry — no hit = STOP
  resolve             : entity -> semantic model (gold, or bronze fallback SAID OUT LOUD),
                        metric word -> expression, dimension word -> column
  plan                : time bounds, comparison window, settlement policy, sort/limit
"""
import os, re, datetime, yaml

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REG = yaml.safe_load(open(os.path.join(HERE, "metricflow", "flipkart.yaml")))

WORKSPACE = "ws_flipkart_demo"
OPS = {"eq": "=", "neq": "<>", "lt": "<", "lte": "<=", "gt": ">", "gte": ">=",
       "contains": "ILIKE", "in": "IN", "not_in": "NOT IN", "between": "BETWEEN"}


class ResolveError(Exception):
    pass


def _data_bounds(con):
    r = con.run("SELECT min(day), max(day), max(as_of), min(day) FILTER (WHERE NOT is_settled) "
                "FROM gold_flipkart_campaign_daily")[0]
    return {"min_day": r[0], "max_day": r[1], "as_of": r[2], "provisional_from": r[3]}


def validate_structural(task_env, trace):
    ok = (task_env.get("version") == "1.0" and task_env.get("task_type") == "query"
          and isinstance(task_env.get("task"), dict)
          and task_env["task"].get("entity") and task_env["task"].get("metrics"))
    if not ok:
        trace.span("validate_structural", "error", " envelope does not match query_task")
        raise ResolveError("structural: not a valid {version, task_type: query, task{entity, metrics[]}} envelope")
    trace.span("validate_structural", detail=" query_and_act-v1 query_task shape: PASS",
               entity=task_env["task"]["entity"], metrics=task_env["task"]["metrics"])


def validate_semantic(task, trace):
    unresolved = []
    entity = task["entity"]
    if entity not in REG["semantic_models"]:
        unresolved.append({"kind": "bug", "what": "entity", "name": entity,
                           "why": f"no semantic model for '{entity}'; known: {sorted(REG['semantic_models'])}"} )
    model = REG["semantic_models"].get(entity, {})
    for m in task["metrics"]:
        spec = REG["metrics"].get(m)
        if spec is None:
            unresolved.append({"kind": "refusal", "what": "metric", "name": m,
                               "why": "not modeled in the registry — the engine never improvises a formula"})
        elif entity in REG["semantic_models"] and entity not in spec["models"]:
            unresolved.append({"kind": "refusal", "what": "combination", "name": f"{m} @ {entity}",
                               "why": f"'{m}' is not carried by the {entity} model ({model.get('table')})"})
    for d in task.get("dimensions", []):
        if d != "date" and d not in REG["dimensions"]:
            unresolved.append({"kind": "bug", "what": "dimension", "name": d, "why": "unknown dimension word"})
    if unresolved:
        trace.span("validate_semantic", "error", f" {len(unresolved)} unresolved — task fails BEFORE any SQL",
                   unresolved=unresolved)
        raise ResolveError("semantic: " + "; ".join(f"{u['what']} '{u['name']}': {u['why']}" for u in unresolved))
    trace.span("validate_semantic", detail=" every metric/dimension resolves in metricflow/flipkart.yaml")


def resolve(task, trace):
    entity = task["entity"]
    model = REG["semantic_models"][entity]
    trace.span("resolve", detail=f" entity '{entity}' -> {model['layer']}.{model['table']}",
               layer=model["layer"], table=model["table"])
    if model["layer"] == "bronze":
        trace.note(f"BRONZE FALLBACK: '{entity}' has no basic gold table — {REG['caveats']['bronze_fallback']}")

    bindings, caveats, companions = [], set(), []
    for m in task["metrics"]:
        spec = REG["metrics"][m]
        bindings.append({"asked": m, "expr": spec["expr"], "unit": spec["unit"],
                         "label": spec["label"], "invert": spec.get("invert", False)})
        trace.note(f"metric '{m}' -> {spec['expr']}  [{spec['unit']}, native label '{spec['label']}']"
                   + (f" — {spec['note']}" if spec.get("note") else ""))
        if m == "roi":
            caveats.add("roi_includes_indirect")
            comp = spec.get("companion")
            if comp and comp not in task["metrics"]:
                cs = REG["metrics"][comp]
                companions.append({"asked": comp, "expr": cs["expr"], "unit": cs["unit"],
                                   "label": cs["label"], "invert": False})
                trace.note(f"COMPANION RULE: roi never renders alone — adding '{comp}' ({cs['label']}) beside it")
        if m == "cvr":
            caveats.add("cvr_fcc_basis")
        if spec.get("agg") == "level":
            caveats.add("wallet_levels")
    bindings += companions

    dims = []
    for d in task.get("dimensions", []):
        col = REG["time_dimension"] if d == "date" else REG["dimensions"][d]["column"]
        dims.append({"asked": d, "column": col})
        trace.note(f"dimension '{d}' -> column '{col}'")
    return {"entity": entity, "model": model, "metrics": bindings, "dims": dims,
            "caveats": sorted(caveats)}


def plan(task, resolved, con, trace):
    b = _data_bounds(con)
    tr = task.get("time_range") or {"type": "relative", "value": 30, "unit": "day"}
    if not task.get("time_range"):
        trace.note("no time_range on the task — WIDEST-DEFAULT rule: assuming last 30 days, declared on the card")
    end = b["max_day"]
    if tr["type"] == "relative":
        days = tr["value"] * {"day": 1, "week": 7, "month": 30, "quarter": 90, "year": 365}[tr["unit"]]
        start = end - datetime.timedelta(days=days - 1)
    elif tr["type"] == "custom":
        start, end = datetime.date.fromisoformat(tr["start"]), datetime.date.fromisoformat(tr["end"])
    else:  # named — anchor on data max_day
        named_days = {"today": 1, "yesterday": 1, "this_week": 7, "last_week": 7,
                      "this_month": 30, "last_month": 30, "this_quarter": 90, "last_quarter": 90}
        start = end - datetime.timedelta(days=named_days.get(tr["type"], 30) - 1)

    p = {"start": start, "end": end, "comparison": None,
         "sort": task.get("sort"), "limit": task.get("limit"),
         "where": task.get("where", []), "having": task.get("having", []),
         "provenance": {"data_as_of": str(b["as_of"]), "provisional_from": str(b["provisional_from"])}}

    if task.get("comparison"):
        span_days = (end - start).days + 1
        p["comparison"] = {"metric": task["comparison"]["metric"],
                           "start": start - datetime.timedelta(days=span_days),
                           "end": start - datetime.timedelta(days=1)}
        trace.note(f"comparison baseline=previous_period -> shifted window {p['comparison']['start']} .. {p['comparison']['end']}")

    # settlement policy (contract: provisional rows excluded from verdicts/rankings, labeled on trends)
    ranked = bool(task.get("sort") and task.get("limit"))
    p["settled_only"] = ranked
    trace.span("plan", detail=f" window {start} .. {end}"
               + (f"; RANKED query -> is_settled=true only (T+28 rule)" if ranked
                  else f"; trend/table query -> provisional rows kept, labeled from {b['provisional_from']}"),
               window=[str(start), str(end)], settled_only=ranked,
               provisional_from=str(b["provisional_from"]))
    return p


def to_sql(resolved, p, trace, group_by_entity):
    t = resolved["model"]["table"]
    time_col = REG["time_dimension"]
    sel, grp = [], []
    for d in resolved["dims"]:
        sel.append(f"{d['column']} AS {d['asked'] if d['asked'] != 'date' else 'day'}")
        grp.append(d["column"])
    if group_by_entity and resolved["model"]["name_dim"] and not any(
            d["column"] == resolved["model"]["name_dim"] for d in resolved["dims"]):
        nd = resolved["model"]["name_dim"]
        sel.insert(0, f"{nd} AS name")
        grp.insert(0, nd)
        trace.note(f"entity grain, no explicit name dim on the task -> grouping by model name_dim '{nd}'")
    for m in resolved["metrics"]:
        sel.append(f"{m['expr']} AS {m['asked']}")

    where = [f"{REG['tenant_key']} = '{WORKSPACE}'",
             f"{time_col} BETWEEN '{p['start']}' AND '{p['end']}'"]
    if p["settled_only"]:
        where.append(f"{REG['settled_flag']} = true")
    for w in p["where"]:
        col = REG["dimensions"].get(w["dimension"], {}).get("column", w["dimension"])
        op = OPS[w["operator"]]
        v = w["value"]
        if w["operator"] in ("in", "not_in"):
            vs = ",".join(f"'{x}'" for x in v)
            where.append(f"{col} {op} ({vs})")
        elif w["operator"] == "between":
            where.append(f"{col} BETWEEN '{v[0]}' AND '{v[1]}'")
        elif w["operator"] == "contains":
            where.append(f"{col} ILIKE '%{v}%'")
        else:
            vv = f"'{v}'" if isinstance(v, str) else v
            where.append(f"{col} {op} {vv}")

    sql = f"SELECT {', '.join(sel)}\nFROM {t}\nWHERE " + "\n  AND ".join(where)
    if grp:
        sql += f"\nGROUP BY {', '.join(grp)}"
    hav = []
    for hq in p["having"]:
        spec = REG["metrics"].get(hq["metric"])
        if spec:
            hav.append(f"{spec['expr']} {OPS[hq['operator']]} {hq['value']}")
    if hav:
        sql += "\nHAVING " + " AND ".join(hav)
    if p["sort"]:
        srt = p["sort"]["metric"]
        spec = REG["metrics"].get(srt, {})
        direction = p["sort"]["direction"]
        sql += f"\nORDER BY {srt} {direction.upper()} NULLS LAST"
        if spec.get("invert"):
            trace.note(f"'{srt}' is lower-is-better — caller asked {direction}; rendered rank respects invert flag")
    elif grp and grp[0] == REG["time_dimension"] or any(d["asked"] == "date" for d in resolved["dims"]):
        sql += f"\nORDER BY {REG['time_dimension']}"
    if p["limit"]:
        sql += f"\nLIMIT {p['limit']}"
    return sql
