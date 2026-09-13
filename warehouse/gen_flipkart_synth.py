"""Synthetic Flipkart Ads data per meerkats_flipkart_schema-v1 warehouse.gold:
- facts ADDITIVE ONLY (no ratio columns) — roi/ctr/cpc/cvr/aov derived at read
- every table carries as_of + is_settled (T+28 backfill window => provisional)
- display names live in gold_flipkart_entities_current, not the fact tables
"""
import random, datetime, json

random.seed(42)

WORKSPACE = "ws_flipkart_demo"
AS_OF = "2026-09-13T06:30:00+05:30"          # sync timestamp (IST)
TODAY = datetime.date(2026, 9, 12)            # data through yesterday
START = TODAY - datetime.timedelta(days=89)   # 90 days
SETTLED_CUTOFF = TODAY - datetime.timedelta(days=28)  # T+28 backfill window

# campaign_id, name, type, bidding, targeting, status, budget_type, daily_budget,
# base_spend, cpc, ctr, cvr, direct_share, aov, start_offset, pause_day(None)
CAMPAIGNS = [
    ("FK-CMP-1001", "PLA_Auto_Bestsellers_AlwaysOn",   "PLA", "CPC",      "Auto",   "LIVE",             "Daily budget", 5000,  4200, 14, 0.0075, 0.055, 0.74, 1150, 0,  None),
    ("FK-CMP-1002", "PLA_Manual_Lipstick_Exact",       "PLA", "CPC",      "Manual", "LIVE",             "Daily budget", 3000,  2600, 18, 0.0062, 0.048, 0.79, 780,  0,  None),
    ("FK-CMP-1003", "PLA_SmartROI_Kajal_Core",         "PLA", "SmartROI", "Auto",   "LIVE",             "Daily budget", 4000,  3500, 11, 0.0088, 0.061, 0.71, 640,  0,  None),
    ("FK-CMP-1004", "PLA_Auto_NewLaunch_Serum",        "PLA", "CPC",      "Auto",   "LIVE",             "Daily budget", 2000,  1500, 22, 0.0045, 0.028, 0.68, 1450, 25, None),
    ("FK-CMP-1005", "PCA_Brand_Diwali_Teaser",         "PCA", "CPC",      "Manual", "LIVE",             "Total budget", None,  2800, 9,  0.0110, 0.021, 0.42, 980,  40, None),
    ("FK-CMP-1006", "PLA_Manual_Nailpolish_Broad",     "PLA", "CPC",      "Manual", "PAUSED",           "Daily budget", 1500,  1200, 16, 0.0051, 0.036, 0.76, 520,  0,  62),
    ("FK-CMP-1007", "PLA_Auto_Combo_Packs",            "PLA", "CPC",      "Auto",   "DAILY_BUDGET_MET", "Daily budget", 2500,  2480, 12, 0.0080, 0.052, 0.72, 1320, 0,  None),
    ("FK-CMP-1008", "PLA_SmartROI_Foundation_Range",   "PLA", "SmartROI", "Auto",   "LIVE",             "Daily budget", 3500,  3000, 15, 0.0070, 0.050, 0.70, 1050, 10, None),
    ("FK-CMP-1009", "PCA_Category_Makeup_Conquest",    "PCA", "CPC",      "Manual", "LIVE",             "Daily budget", 2200,  1900, 10, 0.0095, 0.018, 0.38, 890,  55, None),
    ("FK-CMP-1010", "PLA_Manual_Eyeliner_Phrase",      "PLA", "CPC",      "Manual", "LIVE",             "Daily budget", 1800,  1550, 17, 0.0058, 0.042, 0.77, 610,  0,  None),
]

SALE_START = datetime.date(2026, 8, 15)   # platform sale event: CPC and CVR move together
SALE_END   = datetime.date(2026, 8, 20)

def day_factor(d: datetime.date) -> float:
    f = 1.0 + (0.18 if d.weekday() >= 5 else 0.0)          # weekend lift
    if SALE_START <= d <= SALE_END:
        f *= 1.9                                            # sale traffic surge
    return f

rows_campaign, rows_account = [], {}

for (cid, name, ctype, bidding, targeting, status, btype, dbudget,
     base_spend, cpc, ctr, cvr, dshare, aov, start_off, pause_day) in CAMPAIGNS:
    c_start = START + datetime.timedelta(days=start_off)
    for i in range(90):
        d = START + datetime.timedelta(days=i)
        if d < c_start:
            continue
        if pause_day is not None and i >= pause_day:
            continue
        f = day_factor(d)
        noise = random.uniform(0.85, 1.15)
        eff_cpc = cpc * (1.35 if SALE_START <= d <= SALE_END else 1.0) * random.uniform(0.92, 1.08)
        spend = base_spend * f * noise
        # DAILY_BUDGET_MET campaign: spend clamps at its daily budget (capped early, goes dark)
        if status == "DAILY_BUDGET_MET" and dbudget:
            spend = min(spend, dbudget * random.uniform(0.97, 1.0))
        clicks = max(1, int(spend / eff_cpc))
        views = int(clicks / (ctr * random.uniform(0.9, 1.1)))
        eff_cvr = cvr * (1.25 if SALE_START <= d <= SALE_END else 1.0) * random.uniform(0.85, 1.15)
        orders = max(0, int(clicks * eff_cvr))
        units = int(orders * random.uniform(1.05, 1.35))
        direct_units = int(units * dshare * random.uniform(0.94, 1.06))
        direct_units = min(direct_units, units)
        indirect_units = units - direct_units
        direct_rev = round(direct_units * aov * random.uniform(0.92, 1.08), 2)
        indirect_rev = round(indirect_units * aov * random.uniform(0.75, 0.95), 2)
        ppv = int(clicks * random.uniform(0.55, 0.8))
        atc = int(ppv * random.uniform(0.18, 0.32))
        settled = d <= SETTLED_CUTOFF
        # provisional rows: trailing attribution not fully backfilled yet
        if not settled:
            lag = max(0.55, 1 - (TODAY - d).days / 28 * 0.45)
            for_var = random.uniform(0.9, 1.0)
            orders = int(orders * lag * for_var)
            direct_units = int(direct_units * lag * for_var)
            indirect_units = int(indirect_units * lag * for_var)
            direct_rev = round(direct_rev * lag * for_var, 2)
            indirect_rev = round(indirect_rev * lag * for_var, 2)
        rows_campaign.append((WORKSPACE, cid, d.isoformat(), name, ctype, bidding, status,
                              round(spend, 2), views, clicks, ppv, atc, orders,
                              direct_units, indirect_units, direct_rev, indirect_rev,
                              settled))
        acc = rows_account.setdefault(d.isoformat(), [0.0, 0, 0, 0, 0, 0, 0, 0, 0.0, 0.0, settled])
        acc[0] += spend; acc[1] += views; acc[2] += clicks; acc[3] += ppv; acc[4] += atc
        acc[5] += orders; acc[6] += direct_units; acc[7] += indirect_units
        acc[8] += direct_rev; acc[9] += indirect_rev

ddl = """
DROP TABLE IF EXISTS gold_flipkart_campaign_daily;
DROP TABLE IF EXISTS gold_flipkart_account_daily;
DROP TABLE IF EXISTS gold_flipkart_entities_current;

-- grain: day. Facts ADDITIVE ONLY — roi/ctr/cpc/cvr/aov derived at read.
CREATE TABLE gold_flipkart_account_daily (
  workspace_id      text        NOT NULL,
  day               date        NOT NULL,
  spend             numeric(14,2) NOT NULL,
  views             bigint      NOT NULL,
  clicks            bigint      NOT NULL,
  product_page_views bigint     NOT NULL,
  add_to_cart       bigint      NOT NULL,
  orders            bigint      NOT NULL,
  direct_units      bigint      NOT NULL,
  indirect_units    bigint      NOT NULL,
  direct_revenue    numeric(14,2) NOT NULL,
  indirect_revenue  numeric(14,2) NOT NULL,
  as_of             timestamptz NOT NULL,
  is_settled        boolean     NOT NULL,
  PRIMARY KEY (workspace_id, day)
);

-- grain: campaign_id x day. dims denormalized per DM gold contract.
CREATE TABLE gold_flipkart_campaign_daily (
  workspace_id      text        NOT NULL,
  campaign_id       text        NOT NULL,
  day               date        NOT NULL,
  campaign_name     text        NOT NULL,
  campaign_type     text        NOT NULL CHECK (campaign_type IN ('PLA','PCA','Display')),
  bidding_type      text        NOT NULL CHECK (bidding_type IN ('CPC','SmartROI')),
  status            text        NOT NULL,
  spend             numeric(14,2) NOT NULL,
  views             bigint      NOT NULL,
  clicks            bigint      NOT NULL,
  product_page_views bigint     NOT NULL,
  add_to_cart       bigint      NOT NULL,
  orders            bigint      NOT NULL,
  direct_units      bigint      NOT NULL,
  indirect_units    bigint      NOT NULL,
  direct_revenue    numeric(14,2) NOT NULL,
  indirect_revenue  numeric(14,2) NOT NULL,
  as_of             timestamptz NOT NULL,
  is_settled        boolean     NOT NULL,
  PRIMARY KEY (workspace_id, campaign_id, day)
);

-- latest snapshot per entity for display joins
CREATE TABLE gold_flipkart_entities_current (
  workspace_id    text NOT NULL,
  campaign_id     text NOT NULL,
  campaign_name   text NOT NULL,
  campaign_type   text NOT NULL CHECK (campaign_type IN ('PLA','PCA','Display')),
  bidding_type    text NOT NULL CHECK (bidding_type IN ('CPC','SmartROI')),
  targeting_type  text NOT NULL CHECK (targeting_type IN ('Auto','Manual')),
  status          text NOT NULL,
  budget_type     text NOT NULL,
  daily_budget    numeric(14,2),
  total_budget    numeric(14,2),
  start_date      date NOT NULL,
  end_date        date,
  as_of           timestamptz NOT NULL,
  PRIMARY KEY (workspace_id, campaign_id)
);
CREATE INDEX ix_fk_campaign_daily_day ON gold_flipkart_campaign_daily (workspace_id, day);
"""

def sqlv(v):
    if v is None: return "NULL"
    if isinstance(v, bool): return "true" if v else "false"
    if isinstance(v, (int, float)): return str(v)
    return "'" + str(v).replace("'", "''") + "'"

parts = [ddl]

vals = []
for d, a in sorted(rows_account.items()):
    vals.append(f"({sqlv(WORKSPACE)},{sqlv(d)},{round(a[0],2)},{a[1]},{a[2]},{a[3]},{a[4]},{a[5]},{a[6]},{a[7]},{round(a[8],2)},{round(a[9],2)},{sqlv(AS_OF)},{sqlv(a[10])})")
parts.append("INSERT INTO gold_flipkart_account_daily VALUES\n" + ",\n".join(vals) + ";")

vals = []
for r in rows_campaign:
    vals.append("(" + ",".join(sqlv(x) for x in r[:7]) + "," + ",".join(str(x) for x in r[7:17]) + f",{sqlv(AS_OF)},{sqlv(r[17])})")
# chunk campaign inserts
for i in range(0, len(vals), 300):
    parts.append("INSERT INTO gold_flipkart_campaign_daily VALUES\n" + ",\n".join(vals[i:i+300]) + ";")

vals = []
for (cid, name, ctype, bidding, targeting, status, btype, dbudget, *_rest) in CAMPAIGNS:
    start_off, pause_day = _rest[-2], _rest[-1]
    c_start = START + datetime.timedelta(days=start_off)
    end_date = None
    total_budget = 250000 if btype == "Total budget" else None
    vals.append(f"({sqlv(WORKSPACE)},{sqlv(cid)},{sqlv(name)},{sqlv(ctype)},{sqlv(bidding)},{sqlv(targeting)},{sqlv(status)},{sqlv(btype)},{sqlv(dbudget)},{sqlv(total_budget)},{sqlv(c_start.isoformat())},{sqlv(end_date)},{sqlv(AS_OF)})")
parts.append("INSERT INTO gold_flipkart_entities_current VALUES\n" + ",\n".join(vals) + ";")

sql = "\n\n".join(parts)
open("flipkart_synth_load.sql", "w").write(sql)
print(f"campaign rows: {len(rows_campaign)}, account rows: {len(rows_account)}, entities: {len(CAMPAIGNS)}")
print(f"SQL size: {len(sql)//1024} KB")
# sanity: derived metrics on a settled sample
s = [r for r in rows_campaign if r[17] and r[1] == 'FK-CMP-1001'][:30]
sp = sum(r[7] for r in s); cl = sum(r[9] for r in s); rev = sum(r[15]+r[16] for r in s); o = sum(r[12] for r in s)
print(f"sample FK-CMP-1001 settled 30d: roi={rev/sp:.2f}x cpc=₹{sp/cl:.1f} cvr={o/cl*100:.1f}% direct_share={sum(r[15] for r in s)/rev*100:.0f}%")
