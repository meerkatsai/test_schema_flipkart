"""rows -> representation payload (card.schema.json $defs shapes, verbatim keys) -> HTML.
Formatting per the design system: inr -> ₹ with K/L/Cr, x -> 4.7×, pct -> 26.2%,
one decimal max, unavailable renders as —. Brand ember never encodes data."""
import html as _html


# ── formatters (lib/format.js parity) ────────────────────────────────────────
def fmt_inr(v):
    if v is None: return "—"
    v = float(v)
    a = abs(v)
    if a >= 1e7:  return f"₹{v/1e7:.1f} Cr"
    if a >= 1e5:  return f"₹{v/1e5:.1f} L"
    if a >= 1e3:  return f"₹{v/1e3:.1f} K"
    return f"₹{v:,.0f}"

def fmt_num(v):
    if v is None: return "—"
    v = float(v)
    a = abs(v)
    if a >= 1e7:  return f"{v/1e7:.1f} Cr"
    if a >= 1e5:  return f"{v/1e5:.1f} L"
    if a >= 1e3:  return f"{v/1e3:.1f} K"
    return f"{v:,.0f}"

def fmt_by(unit, v):
    if v is None: return "—"
    return {"inr": fmt_inr, "num": fmt_num,
            "pct": lambda x: f"{float(x):.1f}%", "x": lambda x: f"{float(x):.1f}×"}[unit](v)


def _num(v):
    return None if v is None else float(v)


# ── payload builders (one per representation) ────────────────────────────────
def kpi_strip(rows, spark_rows, prev_totals, metrics):
    """rows: single aggregate row dict; spark_rows: daily rows; prev_totals: dict or {}"""
    items = []
    tot = rows[0] if rows else {}
    for m in metrics:
        cur = _num(tot.get(m["asked"]))
        prev = _num(prev_totals.get(m["asked"])) if prev_totals else None
        delta = None
        if cur is not None and prev not in (None, 0):
            delta = round((cur - prev) / prev * 100, 1)
        items.append({"key": m["asked"], "label": m["label"], "value": fmt_by(m["unit"], cur),
                      "delta": delta, "invert": m["invert"],
                      "spark": [(_num(r.get(m["asked"])) or 0) for r in spark_rows]})
    return {"kind": "kpiStrip", "items": items}


def trend_line(rows, metrics, compare_rows=None):
    labels = [str(r["day"]) for r in rows]
    series = []
    for m in metrics[:8]:
        series.append({"id": m["asked"], "label": m["label"],
                       "data": [_num(r.get(m["asked"])) for r in rows]})
    if compare_rows and len(metrics) >= 1:
        m = metrics[0]
        series.append({"id": f"{m['asked']}_prev", "label": f"{m['label']} (prev)", "dashed": True,
                       "data": [_num(r.get(m["asked"])) for r in compare_rows][:len(labels)]})
    return {"kind": "trendLine", "labels": labels, "series": series, "unit": metrics[0]["unit"]}


def bars_horizontal(rows, metrics, sort_metric):
    m = next((x for x in metrics if x["asked"] == sort_metric), metrics[0])
    sub_m = next((x for x in metrics if x["asked"] != m["asked"]), None)
    items = []
    for r in rows[:10]:
        label = str(r.get("name") or next(iter(r.values())))
        items.append({"id": label, "label": label, "value": _num(r.get(m["asked"])) or 0,
                      **({"sub": f"{sub_m['label']} {fmt_by(sub_m['unit'], r.get(sub_m['asked']))}"} if sub_m else {})})
    return {"kind": "barsHorizontal", "items": items, "unit": m["unit"]}


def bars_vertical(rows, metrics, group_key):
    groups, series_labels = [], [m["label"] for m in metrics[:4]]
    for r in rows[:8]:
        groups.append({"label": str(r.get(group_key) or r.get("name") or r.get("day")),
                       "values": [(_num(r.get(m["asked"])) or 0) for m in metrics[:4]]})
    payload = {"kind": "barsVertical", "groups": groups, "unit": metrics[0]["unit"]}
    if len(metrics) > 1:
        payload["seriesLabels"] = series_labels
    return payload


def data_table(rows, resolved, sort):
    cols = []
    first = rows[0] if rows else {}
    for k in first.keys():
        m = next((x for x in resolved["metrics"] if x["asked"] == k), None)
        if m:
            cols.append({"key": k, "label": m["label"], "unit": m["unit"], "align": "right"})
        else:
            cols.append({"key": k, "label": k.replace("_", " ").title(), "align": "left"})
    trows = []
    for i, r in enumerate(rows):
        row = {"id": str(r.get("name") or r.get("day") or i)}
        row.update({k: (_num(v) if isinstance(v, (int, float)) or (v is not None and not isinstance(v, str) and not hasattr(v, "isoformat")) else (str(v) if v is not None else None)) for k, v in r.items()})
        trows.append(row)
    return {"kind": "dataTable", "columns": cols, "rows": trows, "pageSize": 10,
            **({"sortKey": sort["metric"], "sortDir": sort["direction"]} if sort else {})}


def heatmap(rows, metrics):
    labels = [str(r.get("name") or next(iter(r.values()))) for r in rows[:12]]
    cols = [m["label"] for m in metrics]
    values = [[_num(r.get(m["asked"])) for m in metrics] for r in rows[:12]]
    return {"kind": "heatmap", "rows": labels, "cols": cols, "values": values,
            "unit": metrics[0]["unit"],
            "_colUnits": [m["unit"] for m in metrics],
            "_colInvert": [m["invert"] for m in metrics]}


def period_table(rows, unit, invert=False, name_key="name", value_key=None):
    """rows: per (name, day) records -> periodTableData: rows=entities, cols=dates.
    DoD/WoW/MoM deltas are PERIOD MECHANICS — computed by the renderer per cell
    (value + Δ vs previous column + trailing whole-period Δ)."""
    periods = sorted({str(r["day"]) for r in rows})
    by_name = {}
    for r in rows:
        label = str(r.get(name_key) or "account")
        vk = value_key or next(k for k in r if k not in (name_key, "day"))
        by_name.setdefault(label, {})[str(r["day"])] = _num(r.get(vk))
    trows = []
    for label, vals in by_name.items():
        trows.append({"id": label, "label": label,
                      "values": [vals.get(p) if vals.get(p) is not None else 0 for p in periods]})
    trows.sort(key=lambda x: -sum(x["values"]))
    return {"kind": "periodTable", "periods": periods, "rows": trows[:10],
            "invert": invert, "unit": unit, "pageSize": 10}


def build_payload(representation, rows, resolved, planp, extra):
    metrics = resolved["metrics"]
    if representation == "kpiStrip":
        return kpi_strip(extra.get("totals_rows", []), extra.get("spark_rows", rows),
                         extra.get("prev_totals", {}), metrics)
    if representation == "trendLine":
        return trend_line(rows, metrics, extra.get("compare_rows"))
    if representation == "barsHorizontal":
        return bars_horizontal(rows, metrics, (planp.get("sort") or {}).get("metric", metrics[0]["asked"]))
    if representation == "barsVertical":
        key = rows and ("day" in rows[0] and "day" or "name") or "name"
        return bars_vertical(rows, metrics, key)
    if representation == "dataTable":
        return data_table(rows, resolved, planp.get("sort"))
    if representation == "heatmap":
        return heatmap(rows, metrics)
    raise ValueError(f"unknown representation {representation}")
