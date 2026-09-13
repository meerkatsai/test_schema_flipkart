"""Card payloads -> a standalone HTML report in the meerkats dashboard design system
(tokens vendored from ad-dashboards-prebuilt design/tokens). One visualization per
full-width card; provenance line on every card; the query-formation log renders as
its own mono panel at the bottom — the 'how this number happened' surface."""
import html
from .presenter import fmt_by

SERIES = ["#4285F4", "#EA4335", "#FBBC04", "#34A853", "#7E57C2", "#00ACC1", "#E91E63", "#8D6E63"]
HEAT = ["#FFFFFF", "#E8F0FE", "#AECBFA", "#669DF6", "#1A73E8", "#174EA6"]

CSS = """
:root{--surface-page:#FAFAF9;--surface-card:#FFF;--surface-sunken:#F4F4F2;--ink-900:#0B0B0C;
--ink-700:#2A2A2E;--ink-500:#5C5C63;--ink-400:#8A8A92;--rule:#E4E4E7;--rule-strong:#111113;
--rule-grid:#EFEFEC;--good:#15803D;--bad:#B91C1C;--accent:#EA580C;}
*{box-sizing:border-box}body{margin:0;background:var(--surface-page);color:var(--ink-700);
font:13px/1.45 -apple-system,'Segoe UI',Roboto,sans-serif;padding:24px}
.wrap{max-width:1440px;margin:0 auto;display:flex;flex-direction:column;gap:16px}
h1{font-size:26px;font-weight:600;color:var(--ink-900);margin:0 0 2px}
.sub{color:var(--ink-400);font-family:ui-monospace,Menlo,monospace;font-size:11px;text-transform:lowercase}
.card{background:var(--surface-card);border:1px solid var(--rule);border-radius:6px;padding:20px 16px}
.card-head{padding-bottom:10px;border-bottom:1.5px solid var(--rule-strong);margin-bottom:14px}
.card-title{font-size:15px;font-weight:600;color:var(--ink-900)}
.card-q{font-size:12px;color:var(--ink-500);margin-top:2px}
.prov{font-family:ui-monospace,Menlo,monospace;font-size:11px;color:var(--ink-400);margin-top:6px}
.prov b{color:var(--ink-500);font-weight:500}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:16px}
.kpi .lab{font-size:12px;color:var(--ink-500)}
.kpi .val{font-size:28px;font-weight:600;color:var(--ink-900);font-variant-numeric:tabular-nums}
.delta{font-size:12px;font-variant-numeric:tabular-nums}.delta.good{color:var(--good)}.delta.bad{color:var(--bad)}.delta.na{color:var(--ink-400)}
table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}
th{font-size:12px;color:var(--ink-500);font-weight:500;text-align:right;padding:6px 10px;background:var(--surface-sunken)}
th.l,td.l{text-align:left}td{font-size:13px;padding:6px 10px;border-bottom:1px solid var(--rule);text-align:right}
.hbar-row{display:grid;grid-template-columns:220px 1fr 110px;gap:10px;align-items:center;padding:5px 0}
.hbar-label{font-size:13px;color:var(--ink-700);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.hbar-track{background:var(--surface-sunken);border-radius:1px;height:18px}
.hbar-fill{height:18px;border-radius:1px}
.hbar-val{font-size:13px;color:var(--ink-900);text-align:right}.hbar-sub{font-family:ui-monospace,Menlo,monospace;font-size:10px;color:var(--ink-400)}
.legend{display:flex;gap:14px;font-size:12px;color:var(--ink-500);margin:8px 0 4px}
.legend span{display:inline-flex;align-items:center;gap:5px}
.sw{width:10px;height:10px;border-radius:2px;display:inline-block}
.axis{font-family:ui-monospace,Menlo,monospace;font-size:11px;fill:var(--ink-400)}
.caveat{font-size:12px;color:var(--ink-500);background:var(--surface-sunken);border-left:2px solid var(--ink-400);padding:6px 10px;margin-top:10px}
.logpanel{background:#111113;color:#D4D4D7;border-radius:6px;padding:18px 16px;font-family:ui-monospace,Menlo,monospace;font-size:11.5px;white-space:pre-wrap;overflow-x:auto}
.logpanel h2{color:#FAFAF9;font:600 13px -apple-system,sans-serif;margin:0 0 10px}
.logpanel .sql{color:#AECBFA}
.heat-cell{font-size:12px;text-align:right;padding:6px 10px}
"""


def _delta_html(d, invert=False):
    if d is None:
        return '<span class="delta na">—</span>'
    good = (d >= 0) != bool(invert)
    sign = "+" if d >= 0 else "−"
    return f'<span class="delta {"good" if good else "bad"}">{sign}{abs(d):.1f}%</span>'


def _spark(vals, w=120, h=28, color="#4285F4"):
    vs = [v for v in vals if v is not None]
    if len(vs) < 2:
        return ""
    lo, hi = min(vs), max(vs)
    rng = (hi - lo) or 1
    pts = " ".join(f"{i*w/(len(vals)-1):.1f},{h-2-(v-lo)/rng*(h-4) if v is not None else h-2:.1f}"
                   for i, v in enumerate(vals))
    return f'<svg width="{w}" height="{h}"><polyline fill="none" stroke="{color}" stroke-width="1.5" points="{pts}"/></svg>'


def render_kpi(p):
    cells = []
    for it in p["items"]:
        cells.append(f"""<div class="kpi"><div class="lab">{html.escape(it['label'])}</div>
<div class="val">{html.escape(it['value'])}</div>
<div>{_delta_html(it['delta'], it.get('invert'))}</div>
{_spark(it.get('spark', []))}</div>""")
    return f'<div class="kpis">{"".join(cells)}</div>'


def render_trend(p, height=240, width=1120):
    labels, series = p["labels"], p["series"]
    all_vals = [v for s in series for v in s["data"] if v is not None]
    if not all_vals:
        return "<p>—</p>"
    lo, hi = min(all_vals), max(all_vals)
    if lo > 0 and lo / (hi or 1) > 0.35:
        lo = lo * 0.95
    rng = (hi - lo) or 1
    pad_l, pad_b = 56, 22
    iw, ih = width - pad_l - 8, height - pad_b - 8
    grid, out = [], []
    for g in range(5):
        y = 8 + ih * g / 4
        val = hi - rng * g / 4
        grid.append(f'<line x1="{pad_l}" y1="{y:.0f}" x2="{width}" y2="{y:.0f}" stroke="var(--rule-grid)"/>'
                    f'<text class="axis" x="{pad_l-6}" y="{y+3:.0f}" text-anchor="end">{fmt_by(p["unit"], val)}</text>')
    n = len(labels)
    step = max(1, n // 8)
    for i in range(0, n, step):
        x = pad_l + iw * i / max(1, n - 1)
        grid.append(f'<text class="axis" x="{x:.0f}" y="{height-4}" text-anchor="middle">{html.escape(labels[i][5:])}</text>')
    leg = []
    ci = 0
    for s in series:
        if s.get("dashed"):
            color, dash, swid = "#8A8A92", ' stroke-dasharray="5,4"', 1.5
        else:
            color, dash, swid = SERIES[ci % 8], "", 2
            ci += 1
        pts = " ".join(f"{pad_l + iw*i/max(1,n-1):.1f},{8 + ih*(1-((v-lo)/rng)):.1f}"
                       for i, v in enumerate(s["data"]) if v is not None)
        out.append(f'<polyline fill="none" stroke="{color}" stroke-width="{swid}"{dash} points="{pts}"/>')
        leg.append(f'<span><span class="sw" style="background:{color}"></span>{html.escape(s["label"])}</span>')
    return (f'<div class="legend">{"".join(leg)}</div>'
            f'<svg width="{width}" height="{height}" style="max-width:100%">{"".join(grid)}{"".join(out)}</svg>')


def render_hbars(p):
    mx = max((it["value"] for it in p["items"]), default=1) or 1
    rows = []
    for i, it in enumerate(p["items"]):
        w = max(1.5, it["value"] / mx * 100)
        sub = f'<div class="hbar-sub">{html.escape(it["sub"])}</div>' if it.get("sub") else ""
        rows.append(f"""<div class="hbar-row"><div class="hbar-label">{html.escape(it['label'])}</div>
<div class="hbar-track"><div class="hbar-fill" style="width:{w:.1f}%;background:{SERIES[i%8]}"></div></div>
<div class="hbar-val">{fmt_by(p['unit'], it['value'])}{sub}</div></div>""")
    return "".join(rows)


def render_vbars(p, height=240, width=1120):
    groups = p["groups"]
    nseries = len(groups[0]["values"]) if groups else 1
    mx = max((v for g in groups for v in g["values"]), default=1) or 1
    pad_b, pad_l = 40, 8
    ih = height - pad_b
    gw = width / max(1, len(groups))
    bw = min(64, (gw * 0.7) / nseries)
    parts = []
    for gi, g in enumerate(groups):
        x0 = gi * gw + (gw - bw * nseries) / 2
        for si, v in enumerate(g["values"]):
            h = v / mx * (ih - 10)
            parts.append(f'<rect x="{x0+si*bw:.1f}" y="{ih-h:.1f}" width="{bw-2:.1f}" height="{h:.1f}" rx="1" fill="{SERIES[si%8] if nseries>1 else SERIES[gi%8]}"/>')
        parts.append(f'<text class="axis" x="{gi*gw+gw/2:.0f}" y="{height-24}" text-anchor="middle">{html.escape(str(g["label"])[:16])}</text>')
        parts.append(f'<text class="axis" x="{gi*gw+gw/2:.0f}" y="{height-10}" text-anchor="middle">{fmt_by(p["unit"], g["values"][0])}</text>')
    leg = ""
    if p.get("seriesLabels"):
        leg = '<div class="legend">' + "".join(
            f'<span><span class="sw" style="background:{SERIES[i%8]}"></span>{html.escape(l)}</span>'
            for i, l in enumerate(p["seriesLabels"])) + "</div>"
    return leg + f'<svg width="{width}" height="{height}" style="max-width:100%">{"".join(parts)}</svg>'


def render_table(p):
    ths = "".join(f'<th class="{ "l" if c.get("align")=="left" else "" }">{html.escape(c["label"])}</th>' for c in p["columns"])
    trs = []
    for r in p["rows"][:p.get("pageSize", 10)]:
        tds = []
        for c in p["columns"]:
            v = r.get(c["key"])
            if c.get("unit") and v is not None:
                tds.append(f"<td>{fmt_by(c['unit'], v)}</td>")
            else:
                tds.append(f'<td class="l">{html.escape(str(v)) if v is not None else "—"}</td>')
        trs.append("<tr>" + "".join(tds) + "</tr>")
    return f'<table><thead><tr>{ths}</tr></thead><tbody>{"".join(trs)}</tbody></table>'


def render_heatmap(p):
    ncols = len(p["cols"])
    mins, maxs = [], []
    for j in range(ncols):
        col = [row[j] for row in p["values"] if row[j] is not None]
        mins.append(min(col) if col else 0)
        maxs.append(max(col) if col else 1)
    col_units = p.get("_colUnits") or [p["unit"]] * ncols
    col_invert = p.get("_colInvert") or [False] * ncols
    ths = '<th class="l"></th>' + "".join(f"<th>{html.escape(c)}</th>" for c in p["cols"])
    trs = []
    for i, rl in enumerate(p["rows"]):
        tds = [f'<td class="l">{html.escape(rl)}</td>']
        for j in range(ncols):
            v = p["values"][i][j]
            if v is None:
                tds.append('<td class="heat-cell" style="background:var(--surface-sunken)">—</td>')
                continue
            rng = (maxs[j] - mins[j]) or 1
            t = (v - mins[j]) / rng
            if col_invert[j]:
                t = 1 - t
            step = min(5, int(t * 5) + (1 if t > 0 else 0))
            fg = "#FFF" if step >= 4 else "#0B0B0C"
            tds.append(f'<td class="heat-cell" style="background:{HEAT[step]};color:{fg}">{fmt_by(col_units[j], v)}</td>')
        trs.append("<tr>" + "".join(tds) + "</tr>")
    return f'<table><thead><tr>{ths}</tr></thead><tbody>{"".join(trs)}</tbody></table>'


def render_period_table(p):
    """periodTableData: rows=entities, cols=dates; each cell value + Δ vs the previous
    column; trailing whole-period Δ column. DoD mechanics live HERE (presentation)."""
    unit, inv = p["unit"], p.get("invert", False)
    ths = '<th class="l"></th>' + "".join(
        f"<th>{html.escape(pd[5:] if len(pd) == 10 else pd)}</th>" for pd in p["periods"]) + "<th>Δ period</th>"
    trs = []
    for r in p["rows"][:p.get("pageSize", 10)]:
        tds = [f'<td class="l">{html.escape(r["label"])}</td>']
        prev = None
        for v in r["values"]:
            d = None
            if prev not in (None, 0) and v is not None:
                d = (v - prev) / prev * 100
            cell = fmt_by(unit, v)
            dh = "" if d is None else f'<div>{_delta_html(round(d,1), inv)}</div>'
            tds.append(f"<td>{cell}{dh}</td>")
            prev = v
        first, last = (r["values"][0] or None), (r["values"][-1] or None)
        whole = None if not first else round((last - first) / first * 100, 1)
        tds.append(f"<td>{_delta_html(whole, inv)}</td>")
        trs.append("<tr>" + "".join(tds) + "</tr>")
    return f'<div style="overflow-x:auto"><table><thead><tr>{ths}</tr></thead><tbody>{"".join(trs)}</tbody></table></div>'


RENDERERS = {"kpiStrip": render_kpi, "trendLine": render_trend, "barsHorizontal": render_hbars,
             "barsVertical": render_vbars, "dataTable": render_table, "heatmap": render_heatmap,
             "periodTable": render_period_table}


def render_report(title, cards, trace_text, sql_texts, as_of, lineage=None):
    body_cards = []
    for c in cards:
        caveats = "".join(f'<div class="caveat">{html.escape(t)}</div>' for t in c.get("caveats", []))
        body_cards.append(f"""<div class="card">
<div class="card-head"><div class="card-title">{html.escape(c['title'])}</div>
<div class="card-q">{html.escape(c.get('question',''))}</div>
<div class="prov"><b>source</b> {html.escape(c['source'])} · <b>window</b> {html.escape(c['window'])} · <b>as_of</b> {html.escape(str(as_of))} · <b>provisional from</b> {html.escape(c['provisional_from'])}</div></div>
{RENDERERS[c['payload']['kind']](c['payload'])}
{caveats}</div>""")
    sql_block = "\n\n".join(f"-- {t}\n{s}" for t, s in sql_texts)
    lineage_panel = ""
    if lineage:
        blocks = []
        for metric, chain in lineage:
            steps = "\n".join(f"  {i+1}. {html.escape(step)}" for i, step in enumerate(chain))
            blocks.append(f"<b>{html.escape(metric)}</b>\n{steps}")
        lineage_panel = ('<div class="logpanel"><h2>Data lineage (word → concept → catalog binding → '
                         'MetricFlow metric → semantic model → warehouse table → SQL)</h2>'
                         + "\n\n".join(blocks) + "</div>")
    return f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><style>{CSS}</style></head><body><div class="wrap">
<div><h1>{html.escape(title)}</h1><div class="sub">flipkart · ws_flipkart_demo · generated by the report engine — every number is a recorded query</div></div>
{"".join(body_cards)}
{lineage_panel}
<div class="logpanel"><h2>Query-formation log (task-trace)</h2>{html.escape(trace_text)}

<h2 style="margin-top:16px">Executed SQL</h2><span class="sql">{html.escape(sql_block)}</span></div>
</div></body></html>"""
