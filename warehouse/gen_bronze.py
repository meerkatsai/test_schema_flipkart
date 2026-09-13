"""Bronze layer for Flipkart_ads_test: disaggregate gold_flipkart_campaign_daily into
child grains so SUM(children) == parent (production reconciliation test), plus the
wallet/budget series. Grains per DM/bronze/flipkart.yaml: ad group, keyword (manual
PLA only), search term (PLA), placement, FSN/product (PLA), wallet (account).
"""
import os, re, ssl, random, datetime, itertools
import pg8000.native

random.seed(7)
DSN = os.environ["NEON_DSN"]
u, p, h, db = re.match(r"postgresql://([^:]+):([^@]+)@([^/]+)/([^?]+)", DSN).groups()
con = pg8000.native.Connection(user=u, password=p, host=h, database=db,
                               ssl_context=ssl.create_default_context())

AS_OF = "2026-09-13T06:30:00+05:30"
WORKSPACE = "ws_flipkart_demo"

TARGETING = {  # from entities_current design
  "FK-CMP-1001": ("PLA", "Auto"),  "FK-CMP-1002": ("PLA", "Manual"),
  "FK-CMP-1003": ("PLA", "Auto"),  "FK-CMP-1004": ("PLA", "Auto"),
  "FK-CMP-1005": ("PCA", "Manual"),"FK-CMP-1006": ("PLA", "Manual"),
  "FK-CMP-1007": ("PLA", "Auto"),  "FK-CMP-1008": ("PLA", "Auto"),
  "FK-CMP-1009": ("PCA", "Manual"),"FK-CMP-1010": ("PLA", "Manual"),
}
CATEGORY = {
  "FK-CMP-1001": "bestsellers", "FK-CMP-1002": "lipstick", "FK-CMP-1003": "kajal",
  "FK-CMP-1004": "serum", "FK-CMP-1005": "brand", "FK-CMP-1006": "nailpolish",
  "FK-CMP-1007": "combo", "FK-CMP-1008": "foundation", "FK-CMP-1009": "makeup",
  "FK-CMP-1010": "eyeliner",
}
PLACEMENTS = ["Top of Search", "Rest of Search", "Top of Browse", "Rest of Browse", "Product Page"]
PLACEMENT_W = [0.34, 0.22, 0.16, 0.12, 0.16]  # ToS earns its share
KW_BANK = {
  "lipstick":  ["matte lipstick", "lipstick combo", "red lipstick", "liquid lipstick", "nude lipstick", "lipstick long lasting"],
  "nailpolish":["nail polish", "nail polish combo", "gel nail polish", "matte nail polish", "nail paint"],
  "eyeliner":  ["eyeliner", "waterproof eyeliner", "gel eyeliner", "sketch eyeliner", "kajal eyeliner"],
}
ST_EXTRA = ["best {c} under 200", "{c} for women", "{c} offer", "{c} branded", "{c} waterproof", "top {c}"]
FSN_BANK = {c: [(f"FSN{abs(hash(c+str(i)))%10**10:010d}", f"{c.title()} SKU {i+1}") for i in range(3)] for c in CATEGORY.values()}

FACT_COLS = ["spend","views","clicks","product_page_views","add_to_cart","orders",
             "direct_units","indirect_units","direct_revenue","indirect_revenue"]
INT_COLS = {"views","clicks","product_page_views","add_to_cart","orders","direct_units","indirect_units"}

def split(total, weights, is_int):
    """largest-remainder split so children sum exactly to parent"""
    raw = [total * w for w in weights]
    if not is_int:
        vals = [round(x, 2) for x in raw]
        vals[-1] = round(vals[-1] + (round(total, 2) - sum(vals)), 2)
        return vals
    base = [int(x) for x in raw]
    rem = int(total) - sum(base)
    order = sorted(range(len(raw)), key=lambda i: raw[i] - base[i], reverse=True)
    for i in order[:rem]:
        base[i] += 1
    return base

def child_weights(n, seed_key, jitter=0.25):
    rnd = random.Random(seed_key)
    w = [max(0.05, rnd.gauss(1, jitter)) for _ in range(n)]
    s = sum(w)
    return [x / s for x in w]

rows = con.run("SELECT campaign_id, day, campaign_name, " + ",".join(FACT_COLS) +
               ", is_settled FROM gold_flipkart_campaign_daily ORDER BY campaign_id, day")
print(f"gold campaign-day rows: {len(rows)}")

adgroup_rows, keyword_rows, st_rows, plc_rows, fsn_rows = [], [], [], [], []

for r in rows:
    cid, day, cname = r[0], r[1], r[2]
    facts = dict(zip(FACT_COLS, r[3:13]))
    settled = r[13]
    ctype, targeting = TARGETING[cid]
    cat = CATEGORY[cid]

    # ── ad groups: 2 per campaign ──
    ag_names = [f"{cat}_core", f"{cat}_extended"]
    agw = child_weights(2, cid + "ag")
    ag_facts = {c: split(float(facts[c]), agw, c in INT_COLS) for c in FACT_COLS}
    for i, ag in enumerate(ag_names):
        adgroup_rows.append((WORKSPACE, cid, f"{cid}-AG{i+1}", day.isoformat(), cname, ag, ctype,
                             *[ag_facts[c][i] for c in FACT_COLS], settled))
        # ── keywords: manual PLA only, on core ad group ──
        if i == 0 and ctype == "PLA" and targeting == "Manual":
            kws = KW_BANK[cat]
            kw_w = child_weights(len(kws), cid + "kw")
            kf = {c: split(float(ag_facts[c][0]), kw_w, c in INT_COLS) for c in FACT_COLS}
            for j, kw in enumerate(kws):
                mt = ["Exact", "Phrase", "Broad"][j % 3]
                bid = round(random.Random(cid + kw).uniform(8, 30), 1)
                keyword_rows.append((WORKSPACE, cid, f"{cid}-AG1", day.isoformat(), kw, mt, bid,
                                     *[kf[c][j] for c in FACT_COLS], settled))

    # ── search terms: PLA campaigns (auto discovers terms too) ──
    if ctype == "PLA":
        base_terms = KW_BANK.get(cat, [f"{cat}", f"{cat} combo", f"best {cat}"])[:3]
        terms = base_terms + [t.format(c=cat) for t in ST_EXTRA[:3]]
        stw = child_weights(len(terms), cid + "st", 0.5)
        stf = {c: split(float(facts[c]), stw, c in INT_COLS) for c in FACT_COLS}
        for j, t in enumerate(terms):
            matched = base_terms[j % len(base_terms)] if targeting == "Manual" else "(auto)"
            st_rows.append((WORKSPACE, cid, day.isoformat(), t, matched,
                            *[stf[c][j] for c in FACT_COLS], settled))

    # ── placements: all campaigns, 5 surfaces ──
    pw = [w * random.Random(cid + pl + str(day)).uniform(0.85, 1.15) for w, pl in zip(PLACEMENT_W, PLACEMENTS)]
    s = sum(pw); pw = [x / s for x in pw]
    pf = {c: split(float(facts[c]), pw, c in INT_COLS) for c in FACT_COLS}
    for j, pl in enumerate(PLACEMENTS):
        plc_rows.append((WORKSPACE, cid, day.isoformat(), pl, ctype,
                         *[pf[c][j] for c in FACT_COLS], settled))

    # ── FSN/products: PLA only, 3 per campaign ──
    if ctype == "PLA":
        fsns = FSN_BANK[cat]
        fw = child_weights(3, cid + "fsn")
        ff = {c: split(float(facts[c]), fw, c in INT_COLS) for c in FACT_COLS}
        for j, (fsn, pname) in enumerate(fsns):
            status = "INACTIVE" if (cid == "FK-CMP-1004" and j == 2) else "LIVE"
            units_sold = ff["direct_units"][j] + ff["indirect_units"][j]
            fsn_rows.append((WORKSPACE, cid, day.isoformat(), fsn, pname, status,
                             *[ff[c][j] for c in FACT_COLS], units_sold, settled))

# ── wallet/budget series (account grain) ──
acct = con.run("SELECT day, spend FROM gold_flipkart_account_daily ORDER BY day")
budgets = con.run("SELECT coalesce(sum(daily_budget),0) FROM gold_flipkart_entities_current WHERE status <> 'PAUSED'")[0][0]
wallet_rows, bal = [], 900000.0
for day, spend in acct:
    spend = float(spend)
    topup = 0.0
    if bal < 250000:  # finance tops up when runway shrinks
        topup = 500000.0
        bal += topup
    blocked = round(spend * random.uniform(0.4, 0.7), 2)     # holds against live campaigns
    released = round(blocked * random.uniform(0.85, 1.0), 2)
    bal = round(bal - spend, 2)
    wallet_rows.append((WORKSPACE, day.isoformat(), float(budgets), spend, bal,
                        blocked, released, spend, 0.0, day >= datetime.date(2026, 8, 16)))
# expiring funds spike near month end
for i, w in enumerate(wallet_rows):
    d = datetime.date.fromisoformat(w[1])
    if d.day >= 25:
        wallet_rows[i] = w[:8] + (round(random.uniform(20000, 60000), 2),) + w[9:]

DDL = """
DROP TABLE IF EXISTS bronze_flipkart_adgroup_daily;
DROP TABLE IF EXISTS bronze_flipkart_keyword_daily;
DROP TABLE IF EXISTS bronze_flipkart_search_term_daily;
DROP TABLE IF EXISTS bronze_flipkart_placement_daily;
DROP TABLE IF EXISTS bronze_flipkart_fsn_daily;
DROP TABLE IF EXISTS bronze_flipkart_wallet_daily;

CREATE TABLE bronze_flipkart_adgroup_daily (
  workspace_id text NOT NULL, campaign_id text NOT NULL, ad_group_id text NOT NULL,
  day date NOT NULL, campaign_name text NOT NULL, ad_group_name text NOT NULL,
  campaign_type text NOT NULL,
  spend numeric(14,2) NOT NULL, views bigint NOT NULL, clicks bigint NOT NULL,
  product_page_views bigint NOT NULL, add_to_cart bigint NOT NULL, orders bigint NOT NULL,
  direct_units bigint NOT NULL, indirect_units bigint NOT NULL,
  direct_revenue numeric(14,2) NOT NULL, indirect_revenue numeric(14,2) NOT NULL,
  as_of timestamptz NOT NULL DEFAULT '%(AS_OF)s', is_settled boolean NOT NULL,
  PRIMARY KEY (workspace_id, ad_group_id, day));

CREATE TABLE bronze_flipkart_keyword_daily (
  workspace_id text NOT NULL, campaign_id text NOT NULL, ad_group_id text NOT NULL,
  day date NOT NULL, keyword text NOT NULL, match_type text NOT NULL CHECK (match_type IN ('Exact','Phrase','Broad')),
  bid numeric(8,1) NOT NULL,
  spend numeric(14,2) NOT NULL, views bigint NOT NULL, clicks bigint NOT NULL,
  product_page_views bigint NOT NULL, add_to_cart bigint NOT NULL, orders bigint NOT NULL,
  direct_units bigint NOT NULL, indirect_units bigint NOT NULL,
  direct_revenue numeric(14,2) NOT NULL, indirect_revenue numeric(14,2) NOT NULL,
  as_of timestamptz NOT NULL DEFAULT '%(AS_OF)s', is_settled boolean NOT NULL,
  PRIMARY KEY (workspace_id, campaign_id, keyword, match_type, day));

CREATE TABLE bronze_flipkart_search_term_daily (
  workspace_id text NOT NULL, campaign_id text NOT NULL, day date NOT NULL,
  search_term text NOT NULL, matched_keyword text NOT NULL,
  spend numeric(14,2) NOT NULL, views bigint NOT NULL, clicks bigint NOT NULL,
  product_page_views bigint NOT NULL, add_to_cart bigint NOT NULL, orders bigint NOT NULL,
  direct_units bigint NOT NULL, indirect_units bigint NOT NULL,
  direct_revenue numeric(14,2) NOT NULL, indirect_revenue numeric(14,2) NOT NULL,
  as_of timestamptz NOT NULL DEFAULT '%(AS_OF)s', is_settled boolean NOT NULL,
  PRIMARY KEY (workspace_id, campaign_id, search_term, day));

CREATE TABLE bronze_flipkart_placement_daily (
  workspace_id text NOT NULL, campaign_id text NOT NULL, day date NOT NULL,
  placement text NOT NULL CHECK (placement IN ('Top of Search','Rest of Search','Top of Browse','Rest of Browse','Product Page')),
  campaign_type text NOT NULL,
  spend numeric(14,2) NOT NULL, views bigint NOT NULL, clicks bigint NOT NULL,
  product_page_views bigint NOT NULL, add_to_cart bigint NOT NULL, orders bigint NOT NULL,
  direct_units bigint NOT NULL, indirect_units bigint NOT NULL,
  direct_revenue numeric(14,2) NOT NULL, indirect_revenue numeric(14,2) NOT NULL,
  as_of timestamptz NOT NULL DEFAULT '%(AS_OF)s', is_settled boolean NOT NULL,
  PRIMARY KEY (workspace_id, campaign_id, placement, day));

CREATE TABLE bronze_flipkart_fsn_daily (
  workspace_id text NOT NULL, campaign_id text NOT NULL, day date NOT NULL,
  fsn text NOT NULL, product_name text NOT NULL, sku_status text NOT NULL,
  spend numeric(14,2) NOT NULL, views bigint NOT NULL, clicks bigint NOT NULL,
  product_page_views bigint NOT NULL, add_to_cart bigint NOT NULL, orders bigint NOT NULL,
  direct_units bigint NOT NULL, indirect_units bigint NOT NULL,
  direct_revenue numeric(14,2) NOT NULL, indirect_revenue numeric(14,2) NOT NULL,
  units_sold bigint NOT NULL,
  as_of timestamptz NOT NULL DEFAULT '%(AS_OF)s', is_settled boolean NOT NULL,
  PRIMARY KEY (workspace_id, campaign_id, fsn, day));

CREATE TABLE bronze_flipkart_wallet_daily (
  workspace_id text NOT NULL, day date NOT NULL,
  budget numeric(14,2) NOT NULL, spend numeric(14,2) NOT NULL,
  wallet_balance numeric(14,2) NOT NULL, blocked_funds numeric(14,2) NOT NULL,
  released_funds numeric(14,2) NOT NULL, redeemed_spend numeric(14,2) NOT NULL,
  expiring_funds numeric(14,2) NOT NULL,
  as_of timestamptz NOT NULL DEFAULT '%(AS_OF)s', is_settled boolean NOT NULL,
  PRIMARY KEY (workspace_id, day));
""" % {"AS_OF": AS_OF}

for stmt in [s for s in DDL.split(";\n") if s.strip()]:
    con.run(stmt)
print("bronze DDL applied")

def sqlv(v):
    if isinstance(v, bool): return "true" if v else "false"
    if isinstance(v, (int, float)): return str(v)
    return "'" + str(v).replace("'", "''") + "'"

def bulk_insert(table, cols, rows, batch=400):
    for i in range(0, len(rows), batch):
        vals = ",".join("(" + ",".join(sqlv(x) for x in r) + ")" for r in rows[i:i + batch])
        con.run(f"INSERT INTO {table} ({cols}) VALUES {vals}")
    print(f"{table}: {len(rows)} rows")

F = "spend,views,clicks,product_page_views,add_to_cart,orders,direct_units,indirect_units,direct_revenue,indirect_revenue"
bulk_insert("bronze_flipkart_adgroup_daily", f"workspace_id,campaign_id,ad_group_id,day,campaign_name,ad_group_name,campaign_type,{F},is_settled", adgroup_rows)
bulk_insert("bronze_flipkart_keyword_daily", f"workspace_id,campaign_id,ad_group_id,day,keyword,match_type,bid,{F},is_settled", keyword_rows)
bulk_insert("bronze_flipkart_search_term_daily", f"workspace_id,campaign_id,day,search_term,matched_keyword,{F},is_settled", st_rows)
bulk_insert("bronze_flipkart_placement_daily", f"workspace_id,campaign_id,day,placement,campaign_type,{F},is_settled", plc_rows)
bulk_insert("bronze_flipkart_fsn_daily", f"workspace_id,campaign_id,day,fsn,product_name,sku_status,{F},units_sold,is_settled", fsn_rows)
bulk_insert("bronze_flipkart_wallet_daily", "workspace_id,day,budget,spend,wallet_balance,blocked_funds,released_funds,redeemed_spend,expiring_funds,is_settled", wallet_rows)

# ── reconciliation gate: bronze must sum back to gold ──
print("\n-- reconciliation: SUM(bronze) vs SUM(gold campaign) --")
for t, flt in [("bronze_flipkart_adgroup_daily", ""), ("bronze_flipkart_placement_daily", "")]:
    r = con.run(f"""SELECT (SELECT round(sum(spend)) FROM {t}) - (SELECT round(sum(spend)) FROM gold_flipkart_campaign_daily) AS spend_diff,
                           (SELECT sum(clicks) FROM {t}) - (SELECT sum(clicks) FROM gold_flipkart_campaign_daily) AS clicks_diff""")[0]
    print(f"{t}: spend_diff={r[0]} clicks_diff={r[1]}")
r = con.run("""SELECT (SELECT sum(clicks) FROM bronze_flipkart_fsn_daily)
                    - (SELECT sum(clicks) FROM gold_flipkart_campaign_daily WHERE campaign_type='PLA')""")[0]
print(f"fsn vs PLA-gold clicks_diff={r[0]}")
con.close()
