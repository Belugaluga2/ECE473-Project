"""Row-crop exploration: hedging Kane County, IL corn and soybean rain risk with Kalshi KXRAINCHIM.

Run from the repo root:
    python scripts/run_rowcrop_exploration.py                 # uses cached downloads + committed book
    python scripts/run_rowcrop_exploration.py --refresh-book  # also snapshots the live KXRAINCHIM book

What it does (doc: docs/analysis/14_rowcrop_exploration.md)
1. Exposure. Two representative Kane County farms (corn, soybeans; 288 acres each = the 2022 Census
   average Kane farm size). Rain-driven revenue loss per acre in each year is measured two ways:
   (a) modeled: the verified Illinois state yield models of doc 03a (our 1980-2025 re-estimate of
       Tannura, Irwin & Good) applied to O'Hare (ORD) station rain by anomaly, clipped to the
       statewide-rain range the published model was fit on; corn uses July, soybeans August;
   (b) observed: Kane County NASS yields minus a 1980-2025 linear trend, floored at zero.
   Both are valued at the WASDE-676 2026/27 prices used in doc 03a ($4.70 corn, $12.00 soybeans).
2. Hedges. Long-only Kalshi "Above X in" contracts on KXRAINCHIM (NO = drought, YES = excess rain)
   at the strikes Kalshi has listed for that month, sized by NNLS (agri_hedge.replicate.fit_ladder),
   scored by hedge effectiveness in sample and leave-one-year-out over 1980-2025.
3. Cost per $1 of expected payout under the doc-09 pricing assumptions, plus the Chicago Jul/Aug
   (and May/Jun) 2026 listing quotes.
4. Order-book capacity: the committed 2026-10-29 KXRAINCHIM book and (optionally) a live snapshot.
5. Coverage: share of US corn + soybean acres within 25/50/100 miles of an active Kalshi rain station.

Downloads (cached under $AGRI_HEDGE_RAW_DIR/rowcrop/): NASS Quick Stats county yields and acres
(keyless CSV export, as in scripts/r1_rain_yield_calcs.py) and the Census 2024 county Gazetteer.
Outputs: data/processed/rowcrop_*.csv, docs/figures/rc_*.png, Markdown tables on stdout.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import time
import urllib.parse
import zipfile
from datetime import datetime, timezone

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import requests  # noqa: E402

from agri_hedge import pricing as pr  # noqa: E402
from agri_hedge import rowcrop as rc  # noqa: E402
from agri_hedge.config import FIGURES, PROCESSED, RAW  # noqa: E402
from agri_hedge.replicate import kalshi_strike_sets  # noqa: E402

RAW_RC = RAW / "rowcrop"
RAW_RC.mkdir(parents=True, exist_ok=True)
HEADERS = {"User-Agent": "Mozilla/5.0 (ECE473 agri-hedge research)"}
QS_URL = "https://quickstats.nass.usda.gov"
GAZ_URL = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_counties_national.zip"
CAG_DIV_URL = "https://www.ncei.noaa.gov/access/monitoring/climate-at-a-glance/divisional/time-series"
DIVISION = "1102"                                 # Illinois climate division 2 (Northeast; contains Kane Co.)

STATION, SERIES = "ORD", "KXRAINCHIM"
STATE = "IL"
PRICE = {"corn": 4.70, "soybeans": 12.00}        # WASDE-676 2026/27 projections, as in doc 03a
FARM_ACRES = 288                                  # 2022 Census average Kane farm size (doc 04 Table A1)
EVAL = (1980, 2025)                               # evaluation and detrending window (= 03a update window)
LONG = (1948, 2025)                               # ORD monthly record (modeled loss only)
FAIR_WINDOW = (1991, 2025)                        # climatology for fair prices (doc 09)
NORMAL = (1991, 2020)                             # station normal, matches 03a's state normals
SPEC_MAIN, SPEC_SENS = "update 1980-2025", "rain-only 1980-2025"
CAL_MAIN = (21, "last_price")                     # calibration fit used in doc 09
SENSIBLE_TOL = 0.10                               # doc 09: at most 10c above fair value
BOOK_CAP_USEFUL = 0.95
RADII = (25.0, 50.0, 100.0)
MONTH_ABBR = {5: "May", 6: "Jun", 7: "Jul", 8: "Aug", 11: "Nov"}

SCENARIOS = {  # name -> (mid model, half spread, taker fee)
    "a0_fair_maker": ("fair", 0.0, False),
    "a1_fair_taker_4.5c": ("fair", pr.SPREAD_LOW / 2, True),
    "a2_fair_taker_13.1c": ("fair", pr.SPREAD_HIGH / 2, True),
    "b1_calibrated_taker_4.5c": ("calib", pr.SPREAD_LOW / 2, True),
    "c1_chicago_2026_listing_ask": ("obs", 0.0, True),
}
CENTRAL = "a1_fair_taker_4.5c"

# Hedge cases: (case id, crop, months, sides, label)
CASES = [
    ("corn_jul_no", "corn", (7,), ("no",), "Corn: July NO (drought)"),
    ("corn_jul_yes", "corn", (7,), ("yes",), "Corn: July YES (excess)"),
    ("corn_jul_both", "corn", (7,), ("no", "yes"), "Corn: July NO + YES"),
    ("corn_mayjun_yes", "corn", (5, 6), ("yes",), "Corn: May+Jun YES (wet spring)"),
    ("corn_jul_no_mayjun_yes", "corn", (5, 6, 7), None, "Corn: July NO + May/Jun YES"),
    ("soy_aug_no", "soybeans", (8,), ("no",), "Soy: August NO (drought)"),
    ("soy_aug_yes", "soybeans", (8,), ("yes",), "Soy: August YES (excess)"),
    ("soy_aug_both", "soybeans", (8,), ("no", "yes"), "Soy: August NO + YES"),
    ("soy_julaug_no", "soybeans", (7, 8), ("no",), "Soy: July+Aug NO (drought)"),
]


# ---------------------------------------------------------------------------------------------
# Downloads (cached)
# ---------------------------------------------------------------------------------------------

def _get(url: str, tries: int = 5) -> requests.Response:
    last = None
    for i in range(tries):
        last = requests.get(url, headers=HEADERS, timeout=180)
        if last.status_code == 200:
            return last
        if last.status_code in (429, 500, 502, 503, 504):
            time.sleep(2 ** i)
            continue
        last.raise_for_status()
    last.raise_for_status()
    return last


def nass(params: dict, name: str) -> pd.DataFrame:
    """NASS Quick Stats query via the keyless CSV export (cached as raw/rowcrop/nass_<name>.csv)."""
    path = RAW_RC / f"nass_{name}.csv"
    if not path.exists():
        q = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
        uuid = _get(f"{QS_URL}/uuid/encode?{q}").text.strip().strip('"')
        path.write_text(_get(f"{QS_URL}/data/spreadsheet/{uuid}.csv").text, encoding="utf-8")
        time.sleep(0.3)
    df = pd.read_csv(path, dtype=str)
    df["value"] = pd.to_numeric(df["Value"].str.replace(",", "").str.strip(), errors="coerce")
    df["year"] = pd.to_numeric(df["Year"], errors="coerce").astype("Int64")
    return df


YIELD_ITEM = {"corn": "CORN, GRAIN - YIELD, MEASURED IN BU / ACRE",
              "soybeans": "SOYBEANS - YIELD, MEASURED IN BU / ACRE"}
ACRE_ITEM = {"corn": "CORN, GRAIN - ACRES HARVESTED", "soybeans": "SOYBEANS - ACRES HARVESTED"}


def kane_yields() -> pd.DataFrame:
    out = {}
    for crop in ("corn", "soybeans"):
        for what, item in (("yield", YIELD_ITEM), ("acres", ACRE_ITEM)):
            d = nass({"source_desc": "SURVEY", "agg_level_desc": "COUNTY", "state_alpha": STATE,
                      "county_name": "KANE", "short_desc": item[crop], "reference_period_desc": "YEAR"},
                     f"kane_{crop}_{what}")
            d = d[d["Period"] == "YEAR"]
            out[f"{crop}_{what}"] = d.groupby("year")["value"].first()
    df = pd.DataFrame(out)
    df.index = df.index.astype(int)
    df.index.name = "year"
    return df.sort_index()


def county_acres(year: int, source: str = "CENSUS") -> pd.DataFrame:
    """US county corn-grain + soybean harvested acres for one year (Census of Agriculture by default:
    every county, some withheld as (D); the annual SURVEY publishes fewer counties)."""
    frames = []
    for crop in ("corn", "soybeans"):
        params = {"source_desc": source, "agg_level_desc": "COUNTY", "short_desc": ACRE_ITEM[crop],
                  "year": str(year), "domain_desc": "TOTAL"}
        if source == "SURVEY":
            params["reference_period_desc"] = "YEAR"
        d = nass(params, f"us_county_{crop}_acres_{source.lower()}_{year}")
        d = d[d["Period"] == "YEAR"].copy()
        d["crop"] = crop
        frames.append(d)
    d = pd.concat(frames)
    d["county_ansi"] = d["County ANSI"].fillna("").str.strip()
    d["located"] = d["county_ansi"] != ""
    d["withheld"] = d["Value"].str.strip().eq("(D)")
    d["geoid"] = np.where(d["located"], d["State ANSI"].str.zfill(2) + d["county_ansi"].str.zfill(3), "")
    return d[["year", "State", "County", "geoid", "located", "withheld", "crop", "value"]]


def noaa_division_monthly(code: str) -> pd.DataFrame:
    """NOAA NCEI Climate at a Glance climate-division monthly precipitation (nClimDiv), year x month."""
    path = RAW_RC / f"noaa_cag_div_{code}_pcp.csv"
    if not path.exists():
        url = f"{CAG_DIV_URL}/{code}/pcp/1/0/1895-2025/data.csv"
        path.write_text(_get(url).text, encoding="utf-8")
    df = pd.read_csv(path, comment="#")
    df = df[df["Value"] > -90]
    df["year"], df["month"] = df["Date"] // 100, df["Date"] % 100
    return df.pivot(index="year", columns="month", values="Value").reindex(columns=range(1, 13))


def gazetteer() -> pd.DataFrame:
    path = RAW_RC / "2024_Gaz_counties_national.zip"
    if not path.exists():
        path.write_bytes(_get(GAZ_URL).content)
    with zipfile.ZipFile(path) as z:
        name = [n for n in z.namelist() if n.endswith(".txt")][0]
        txt = z.read(name).decode("latin-1")
    g = pd.read_csv(io.StringIO(txt), sep="\t", dtype={"GEOID": str})
    g.columns = [c.strip() for c in g.columns]
    return g[["GEOID", "USPS", "NAME", "INTPTLAT", "INTPTLONG"]].rename(
        columns={"GEOID": "geoid", "INTPTLAT": "lat", "INTPTLONG": "lon"})


def live_book_snapshot() -> pd.DataFrame:
    """Snapshot every open KXRAINCHIM market's order book (public API, no key)."""
    from agri_hedge import kalshi as k
    c = k.default_client()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rows = []
    for m in c.list_markets(series_ticker=SERIES, status="open"):
        book = k.parse_orderbook(c.get_orderbook(m["ticker"]))
        strike = m.get("floor_strike")
        rows.append({"snapshot_utc": stamp, "ticker": m["ticker"], "event_ticker": m["event_ticker"],
                     "contract_month": "20" + m["event_ticker"].split("-")[1][:2] + "-"
                     + f"{list(MONTHS_UP).index(m['event_ticker'].split('-')[1][2:5]) + 1:02d}",
                     "strike": float(strike) if strike is not None else np.nan,
                     "rules_primary": m.get("rules_primary", "")[:200],
                     "yes_bids": json.dumps(book["yes_bids"]), "no_bids": json.dumps(book["no_bids"])})
        time.sleep(0.2)
    return pd.DataFrame(rows)


MONTHS_UP = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")


# ---------------------------------------------------------------------------------------------
# Exposure
# ---------------------------------------------------------------------------------------------

def state_models() -> dict:
    """IL coefficients, statewide normals and fit ranges from the committed doc-03a tables."""
    coef = pd.read_csv(PROCESSED / "crop_yield_aux" / "r1_reestimate_coefficients.csv")
    sens = pd.read_csv(PROCESSED / "crop_rain_sensitivity_corn_soy.csv")
    out = {}
    names = {5: "May", 6: "June", 7: "July", 8: "August"}
    terms = {5: ("may", None), 6: ("jun", "jun2"), 7: ("jul", "jul2"), 8: ("aug", "aug2")}
    for crop in ("corn", "soybeans"):
        for spec in (SPEC_MAIN, SPEC_SENS):
            c = coef[(coef["crop"] == crop) & (coef["state"] == STATE) & (coef["spec"] == spec)].set_index("term")["coef"]
            for mon, (t1, t2) in terms.items():
                b1 = float(c[t1])
                b2 = float(c[t2]) if t2 else 0.0
                src = f"Own re-estimate ({spec})"
                row = sens[(sens["crop"] == crop) & (sens["region"] == STATE) & (sens["month_or_window"] == names[mon])
                           & (sens["source_short"].str.startswith(src))].iloc[0]
                p0 = float(row["baseline_precip_in"])
                slope = b1 + 2 * b2 * p0
                assert abs(slope - float(row["delta_yield_per_inch"])) < 0.01, (crop, spec, mon, slope)
                tan = sens[(sens["crop"] == crop) & (sens["region"] == STATE) & (sens["month_or_window"] == names[mon])
                           & sens["source_short"].str.startswith("Tannura")].iloc[0]
                rng = re.search(r"observed range ([\d.]+)-([\d.]+) in", tan["valid_range_note"])
                out[(crop, spec, mon)] = {"b1": b1, "b2": b2, "p0": p0, "slope": slope,
                                          "clip": (float(rng.group(1)), float(rng.group(2)))}
    return out


def modeled_change(rain: pd.DataFrame, models: dict, crop: str, spec: str, months, normals: dict) -> pd.Series:
    """Summed yield change (bu/ac) over `months` from ORD rain, by year."""
    tot = pd.Series(0.0, index=rain.index)
    for m in months:
        mm = models[(crop, spec, m)]
        p = rc.state_equivalent_rain(rain[m].to_numpy(), normals[m], mm["p0"], clip=mm["clip"])
        tot = tot + rc.quadratic_yield_change(p, mm["b1"], mm["b2"], mm["p0"])
    return tot


# ---------------------------------------------------------------------------------------------
# Pricing helpers
# ---------------------------------------------------------------------------------------------

def chicago_listing_quotes(mk: pd.DataFrame, cd: pd.DataFrame, rain_mdw: pd.DataFrame) -> pd.DataFrame:
    """First two-sided quote (spread <= 25c) of each May-Aug 2026 KXRAINCHIM market, with MDW climatology.

    These months settled on Midway (CLIMDW), so fair value is Midway's 1991-2025 frequency.
    """
    m = mk[(mk["series_ticker"] == SERIES) & mk["contract_month"].astype(str).isin(
        ["2026-05", "2026-06", "2026-07", "2026-08"]) & (mk["strike_type"] == "greater")].copy()
    m["close"] = pd.to_datetime(m["close_time"], utc=True)
    c = cd[cd["ticker"].isin(m["ticker"])].copy()
    c["end"] = pd.to_datetime(c["end_period_ts"], unit="s", utc=True)
    rows = []
    for _, r in m.iterrows():
        cc = c[(c["ticker"] == r["ticker"]) & (c["end"] <= r["close"])].sort_values("end")
        cc = cc[(cc["yes_bid_close"] > 0) & (cc["yes_ask_close"] < 1)
                & ((cc["yes_ask_close"] - cc["yes_bid_close"]) <= 0.25)]
        mon = int(str(r["contract_month"])[5:7])
        k = float(r["floor_strike"])
        q_no = rc.leg_win_probability(rain_mdw, mon, k, "no", FAIR_WINDOW)
        base = {"ticker": r["ticker"], "month": mon, "strike_in": k, "q_no_mdw": q_no,
                "settled_in": r["expiration_value"], "result": r["result"], "volume": r["volume"]}
        if cc.empty:
            rows.append({**base, "quoted": False})
            continue
        x = cc.iloc[0]
        rows.append({**base, "quoted": True, "days_before_close": (r["close"] - x["end"]).total_seconds() / 86400,
                     "yes_bid": x["yes_bid_close"], "yes_ask": x["yes_ask_close"],
                     "no_ask": 1 - x["yes_bid_close"],
                     "markup_no_ask": (1 - x["yes_bid_close"]) - q_no,
                     "markup_yes_ask": x["yes_ask_close"] - (1 - q_no)})
    return pd.DataFrame(rows)


def leg_prices(legs: pd.DataFrame, rain: pd.DataFrame, cal_ab: tuple, quotes: pd.DataFrame) -> pd.DataFrame:
    """Add q (fair win probability at ORD, 1991-2025) and mid prices for each pricing model."""
    out = legs.copy()
    out["q"] = [rc.leg_win_probability(rain, int(m), float(k), s, FAIR_WINDOW)
                for m, k, s in zip(out["contract_month"], out["strike_in"], out["side"])]
    a, b = cal_ab
    out["mid_fair"] = out["q"]
    out["mid_calib"] = [float(pr.calibrated_no_price(q, a, b)) if s == "no" else float(pr.calibrated_yes_price(q, a, b))
                        for q, s in zip(out["q"], out["side"])]
    qk = quotes[quotes["quoted"]].set_index(["month", "strike_in"]) if not quotes.empty else pd.DataFrame()
    obs = []
    for m, k, s, q in zip(out["contract_month"], out["strike_in"], out["side"], out["q"]):
        key = (int(m), float(k))
        if len(qk) and key in qk.index:
            mk = qk.loc[key, "markup_no_ask" if s == "no" else "markup_yes_ask"]
            obs.append(float(pr.clip_price(q + float(mk))))
        else:
            obs.append(np.nan)
    out["mid_obs"] = obs
    return out


def cost_table(legs: pd.DataFrame) -> dict:
    """Cost of the farm-scale legs under every scenario; returns {scenario: cost_totals + expected}."""
    res = {}
    for name, (mid, hs, taker) in SCENARIOS.items():
        priced = pr.price_legs(legs, legs[f"mid_{mid}"].to_numpy(), half_spread=hs, taker=taker)
        t = pr.cost_totals(priced)
        ok = priced["price"].notna()
        t["expected_priced_usd"] = float((legs["contracts"] * legs["q"])[ok].sum())
        t["load"] = pr.load_factor(t["cost_usd"], t["expected_priced_usd"])
        t["share_contracts_priced"] = float(t["contracts_priced"] / legs["contracts"].sum()) if len(legs) else np.nan
        res[name] = t
    return res


# ---------------------------------------------------------------------------------------------
# Order books
# ---------------------------------------------------------------------------------------------

def books_from_frame(df: pd.DataFrame, month: str) -> dict:
    d = df[(df["contract_month"].astype(str) == month)]
    return {float(r["strike"]): {"yes_bids": [tuple(x) for x in json.loads(r["yes_bids"])],
                                 "no_bids": [tuple(x) for x in json.loads(r["no_bids"])]}
            for _, r in d.iterrows() if pd.notna(r["strike"])}


def book_depth(books: dict, rain: pd.DataFrame, month: int, label: str) -> pd.DataFrame:
    rows = []
    for k, b in sorted(books.items()):
        q_no = rc.leg_win_probability(rain, month, k, "no", FAIR_WINDOW)
        r = {"book": label, "strike_in": k, "q_no": q_no}
        for side, q in (("no", q_no), ("yes", 1 - q_no)):
            anyp = rc.walk_book(b, side, None, pr.PRICE_MAX)
            useful = rc.walk_book(b, side, None, BOOK_CAP_USEFUL)
            sens = rc.walk_book(b, side, None, min(pr.PRICE_MAX, q + SENSIBLE_TOL))
            r.update({f"{side}_contracts_any": anyp["filled"], f"{side}_contracts_le95c": useful["filled"],
                      f"{side}_contracts_sensible": sens["filled"],
                      f"{side}_premium_sensible_usd": sens["cost_usd"] + sens["fee_usd"],
                      f"{side}_fair_sensible_usd": sens["filled"] * q})
        rows.append(r)
    return pd.DataFrame(rows)


def farm_fill(legs: pd.DataFrame, books: dict, rain: pd.DataFrame, book_month: int) -> dict:
    """Doc-09 'sensible price' fill: map each leg to the book strike with the closest win probability
    (same side), buy at most fair + 10c, legs that share a strike share its depth."""
    if legs.empty or not books:
        return {"fill_share_contracts": np.nan, "fill_share_expected": np.nan}
    ks = np.array(sorted(books))
    qn = {k: rc.leg_win_probability(rain, book_month, k, "no", FAIR_WINDOW) for k in ks}
    L = legs.copy().reset_index(drop=True)
    L["match"] = [float(ks[np.argmin([abs((qn[k] if s == "no" else 1 - qn[k]) - q) for k in ks])])
                  for q, s in zip(L["q"], L["side"])]
    L["fill"] = 0.0
    for (s, km), g in L.groupby(["side", "match"]):
        need = float(g["contracts"].sum())
        fair = qn[km] if s == "no" else 1 - qn[km]
        w = rc.walk_book(books[km], s, need, min(pr.PRICE_MAX, fair + SENSIBLE_TOL))
        L.loc[g.index, "fill"] = g["contracts"] * (w["filled"] / need if need else 0.0)
    return {"fill_share_contracts": float(L["fill"].sum() / L["contracts"].sum()),
            "fill_share_expected": float((L["fill"] * L["q"]).sum() / (L["contracts"] * L["q"]).sum()),
            "contracts_needed": float(L["contracts"].sum()), "contracts_filled": float(L["fill"].sum())}


# ---------------------------------------------------------------------------------------------
# Main study
# ---------------------------------------------------------------------------------------------

def _md(df: pd.DataFrame, floatfmt: str = "{:,.2f}") -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            cells.append(floatfmt.format(v) if isinstance(v, (float, np.floating)) and np.isfinite(v)
                         else ("" if isinstance(v, float) and np.isnan(v) else str(v)))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--refresh-book", action="store_true", help="snapshot the live KXRAINCHIM order book")
    ap.add_argument("--acres-year", type=int, default=None, help="Census of Agriculture year for county acres (default 2022)")
    args = ap.parse_args(argv)

    st = pd.read_csv(PROCESSED / "station_monthly_precip.csv")
    rain = pr.rain_wide(st, STATION)
    rain_mdw = pr.rain_wide(st, "MDW")
    normals = {m: float(rain.loc[NORMAL[0]:NORMAL[1], m].mean()) for m in range(1, 13)}
    models = state_models()
    mk = pd.read_parquet(PROCESSED / "kalshi_rain_markets.parquet")
    cd = pd.read_parquet(PROCESSED / "kalshi_rain_daily_candles.parquet")
    cal = pd.read_csv(PROCESSED / "kalshi_rain_calibration.csv")
    cal_ab = pr.logistic_calibration_fit(cal[(cal["horizon_days"] == CAL_MAIN[0]) & (cal["price_kind"] == CAL_MAIN[1])])
    strikes = kalshi_strike_sets(mk, SERIES)
    sstr = rc.side_strikes(strikes, normals)
    print("ORD 1991-2020 normals (in): " + ", ".join(f"{MONTH_ABBR[m]} {normals[m]:.2f}" for m in (5, 6, 7, 8)))
    print("strike sets: " + "; ".join(f"{MONTH_ABBR[m]} NO {sstr['no'][m]} YES {sstr['yes'][m]}" for m in (5, 6, 7, 8)))

    # ---- 1. exposure ---------------------------------------------------------------------
    ky = kane_yields()
    ky.to_csv(PROCESSED / "rowcrop_kane_yields.csv")
    years = np.arange(LONG[0], LONG[1] + 1)
    R = rain.reindex(years)
    fy = pd.DataFrame({"year": years})
    for m in (5, 6, 7, 8):
        fy[f"ord_{MONTH_ABBR[m].lower()}_in"] = R[m].to_numpy()
    div = noaa_division_monthly(DIVISION)
    div_normals = {m: float(div.loc[NORMAL[0]:NORMAL[1], m].mean()) for m in range(1, 13)}
    D = div.reindex(years)
    for m in (5, 6, 7, 8):
        fy[f"div_{MONTH_ABBR[m].lower()}_in"] = D[m].to_numpy()
    for crop, mon in (("corn", 7), ("soybeans", 8)):
        tag = "corn" if crop == "corn" else "soy"
        dyd = modeled_change(D, models, crop, SPEC_MAIN, (mon,), div_normals).to_numpy()
        fy[f"{tag}_div_dy_bu"] = dyd
        fy[f"{tag}_div_loss_usd_ac"] = rc.revenue_loss(dyd, PRICE[crop])
        for spec, sfx in ((SPEC_MAIN, ""), (SPEC_SENS, "_rainonly")):
            dy = modeled_change(R, models, crop, spec, (mon,), normals).to_numpy()
            fy[f"{tag}_model_dy_bu{sfx}"] = dy
            fy[f"{tag}_model_loss_usd_ac{sfx}"] = rc.revenue_loss(dy, PRICE[crop])
        dys = modeled_change(R, models, crop, SPEC_MAIN, (5, 6, 7, 8), normals).to_numpy()
        fy[f"{tag}_model_season_dy_bu"] = dys
        fy[f"{tag}_model_season_loss_usd_ac"] = rc.revenue_loss(dys, PRICE[crop])
        y = ky[f"{crop}_yield"].reindex(years).to_numpy()
        ts = rc.trend_shortfall(years, y, EVAL)
        fy[f"kane_{tag}_yield"] = y
        fy[f"kane_{tag}_trend"] = ts["trend"].to_numpy()
        fy[f"kane_{tag}_dev_bu"] = ts["deviation"].to_numpy()
        fy[f"{tag}_obs_loss_usd_ac"] = ts["shortfall"].to_numpy() * PRICE[crop]

    ev = fy[(fy["year"] >= EVAL[0]) & (fy["year"] <= EVAL[1])].copy()
    print("\n## Exposure (per acre, 1980-2025 unless noted)\n")
    exp_rows = []
    for tag, crop in (("corn", "corn"), ("soy", "soybeans")):
        for col, lab in ((f"{tag}_model_loss_usd_ac", "modeled, key month, temp fixed"),
                         (f"{tag}_model_loss_usd_ac_rainonly", "modeled, key month, rain-only"),
                         (f"{tag}_model_season_loss_usd_ac", "modeled, May-Aug sum"),
                         (f"{tag}_div_loss_usd_ac", "modeled, key month, NE Illinois division rain"),
                         (f"{tag}_obs_loss_usd_ac", "observed Kane shortfall vs trend")):
            for wnd, d in (("1980-2025", ev), ("1948-2025", fy)):
                if "obs" in col and wnd != "1980-2025":
                    continue
                v = d[col].dropna()
                worst = d.loc[d[col].idxmax()] if len(v) else None
                exp_rows.append({"crop": crop, "measure": lab, "window": wnd, "n_years": len(v),
                                 "mean_usd_ac": v.mean(), "sd_usd_ac": v.std(ddof=0),
                                 "years_loss>0": int((v > 0).sum()),
                                 "worst_year": int(worst["year"]) if worst is not None else np.nan,
                                 "worst_usd_ac": v.max(), "mean_farm_usd": v.mean() * FARM_ACRES})
    exp_df = pd.DataFrame(exp_rows)
    print(_md(exp_df))
    # agreement between modeled and observed
    def pc(a, b):
        x, y = ev[a].to_numpy(float), ev[b].to_numpy(float)
        ok = ~(np.isnan(x) | np.isnan(y))
        return float(np.corrcoef(x[ok], y[ok])[0, 1]), int(ok.sum())

    agree = []
    for tag, mon in (("corn", "jul"), ("soy", "aug")):
        pairs = {"model loss (ORD) vs obs loss": (f"{tag}_model_loss_usd_ac", f"{tag}_obs_loss_usd_ac"),
                 "rain-only model (ORD) vs obs loss": (f"{tag}_model_loss_usd_ac_rainonly", f"{tag}_obs_loss_usd_ac"),
                 "May-Aug model (ORD) vs obs loss": (f"{tag}_model_season_loss_usd_ac", f"{tag}_obs_loss_usd_ac"),
                 "model loss (division) vs obs loss": (f"{tag}_div_loss_usd_ac", f"{tag}_obs_loss_usd_ac"),
                 "model loss ORD vs division": (f"{tag}_model_loss_usd_ac", f"{tag}_div_loss_usd_ac"),
                 f"ORD vs division {mon} rain": (f"ord_{mon}_in", f"div_{mon}_in"),
                 f"ORD {mon} rain vs Kane yield dev": (f"ord_{mon}_in", f"kane_{tag}_dev_bu"),
                 f"division {mon} rain vs Kane yield dev": (f"div_{mon}_in", f"kane_{tag}_dev_bu")}
        for lab, (a, b) in pairs.items():
            r, n = pc(a, b)
            agree.append({"crop": tag, "pair": lab, "n": n, "corr": r})
    agree = pd.DataFrame(agree)
    agree.to_csv(PROCESSED / "rowcrop_exposure_correlations.csv", index=False)
    print("\n" + _md(agree, "{:.2f}"))
    worst_obs = ev.nlargest(6, "corn_obs_loss_usd_ac")[["year", "ord_may_in", "ord_jun_in", "ord_jul_in", "kane_corn_dev_bu",
                                                       "corn_obs_loss_usd_ac", "corn_model_loss_usd_ac"]]
    print("\nWorst observed Kane corn years:\n" + _md(worst_obs))
    worst_soy = ev.nlargest(6, "soy_obs_loss_usd_ac")[["year", "ord_jul_in", "ord_aug_in", "kane_soy_dev_bu",
                                                      "soy_obs_loss_usd_ac", "soy_model_loss_usd_ac"]]
    print("\nWorst observed Kane soybean years:\n" + _md(worst_soy))

    # ---- 2+3. hedges and costs -----------------------------------------------------------
    quotes = chicago_listing_quotes(mk, cd, rain_mdw)
    quotes.to_csv(PROCESSED / "rowcrop_chicago_2026_listing_quotes.csv", index=False)
    summary, leg_rows = [], []
    for target, wnd in (("model", EVAL), ("div", EVAL), ("obs", EVAL), ("model", LONG)):
        d = fy[(fy["year"] >= wnd[0]) & (fy["year"] <= wnd[1])]
        for cid, crop, months, sides, label in CASES:
            tag = "corn" if crop == "corn" else "soy"
            loss = d[f"{tag}_{target}_loss_usd_ac"].to_numpy()
            rbm = {m: d[f"ord_{MONTH_ABBR[m].lower()}_in"].to_numpy() for m in months}
            if sides is None:   # corn July NO + May/Jun YES
                X1, l1 = rc.binary_design({7: rbm[7]}, sstr, ("no",))
                X2, l2 = rc.binary_design({5: rbm[5], 6: rbm[6]}, sstr, ("yes",))
                X, legs = np.column_stack([X1, X2]), l1 + l2
            else:
                X, legs = rc.binary_design(rbm, sstr, sides)
            fit = rc.fit_loss_hedge(X, loss, legs)
            one = rc.best_single_strike(X, loss, legs)
            lf = rc.legs_frame(legs, fit["weights"], FARM_ACRES)
            row = {"target": target, "window": f"{wnd[0]}-{wnd[1]}", "case": cid, "label": label,
                   "n_years": fit["n_years"], "mean_loss_usd_ac": float(np.nanmean(loss[~np.isnan(X).any(axis=1)])),
                   "he_in": fit["he_in"], "he_loyo": fit["he_loyo"], "corr_in": fit["corr_in"],
                   "tail5_in": fit["tail_in"], "tail5_loyo": fit["tail_loyo"],
                   "one_strike_leg": (f"{MONTH_ABBR[one['leg'][0]]} {one['leg'][2].upper()} >{one['leg'][1]:g}"
                                      if one.get("leg") else ""),
                   "one_strike_he_loyo": one["he_loyo"],
                   "n_legs": len(lf), "contracts_per_ac": float(lf["contracts"].sum() / FARM_ACRES) if len(lf) else 0.0,
                   "legs": "; ".join(f"{MONTH_ABBR[int(r.contract_month)]} {r.side.upper()} >{r.strike_in:g}: {r.contracts / FARM_ACRES:.1f}/ac"
                                     for r in lf.itertuples())}
            if len(lf):
                lp = leg_prices(lf, rain, cal_ab, quotes)
                ct = cost_table(lp)
                exp_pay = float((lp["contracts"] * lp["q"]).sum())
                row["expected_payout_usd_ac"] = exp_pay / FARM_ACRES
                for name, t in ct.items():
                    row[f"cost_usd_ac_{name}"] = t["cost_usd"] / FARM_ACRES
                    row[f"load_{name}"] = t["load"]
                row["share_contracts_priced_obs"] = ct["c1_chicago_2026_listing_ask"]["share_contracts_priced"]
                row["net_cost_central_usd_farm"] = ct[CENTRAL]["cost_usd"] - exp_pay
                if wnd == EVAL:
                    for r_ in lp.itertuples():
                        leg_rows.append({"target": target, "case": cid, "contract_month": r_.contract_month,
                                         "strike_in": r_.strike_in, "side": r_.side, "contracts_farm": r_.contracts,
                                         "q": r_.q, "mid_calib": r_.mid_calib, "mid_obs": r_.mid_obs})
            summary.append(row)
            if wnd == EVAL:
                fy.loc[d.index, f"hedge_{target}_{cid}_loyo_usd_ac"] = fit["loyo_payout"]
    summ = pd.DataFrame(summary)
    summ.to_csv(PROCESSED / "rowcrop_hedge_summary.csv", index=False)
    pd.DataFrame(leg_rows).to_csv(PROCESSED / "rowcrop_hedge_legs.csv", index=False)
    fy.to_csv(PROCESSED / "rowcrop_farm_year.csv", index=False)
    print("\n## Hedge effectiveness\n")
    print(_md(summ[["target", "window", "label", "n_years", "mean_loss_usd_ac", "he_in", "he_loyo", "tail5_in",
                    "tail5_loyo", "one_strike_leg", "one_strike_he_loyo", "contracts_per_ac"]]))
    print("\n## Cost per $1 of expected payout\n")
    print(_md(summ[["target", "window", "label", "expected_payout_usd_ac"]
                   + [f"load_{n}" for n in SCENARIOS] + ["share_contracts_priced_obs"]]))
    print("\nLegs:\n" + _md(summ[summ["window"] == "1980-2025"][["target", "label", "legs"]]))
    q = quotes[quotes["quoted"]]
    print("\n## Chicago 2026 listing quotes (May-Aug, Midway)\n")
    print(_md(q[["ticker", "days_before_close", "q_no_mdw", "yes_bid", "yes_ask", "markup_no_ask", "markup_yes_ask",
                 "result", "volume"]]))
    print(f"\nmean markup NO ask {q['markup_no_ask'].mean():+.3f}; YES ask {q['markup_yes_ask'].mean():+.3f}; "
          f"n quoted {len(q)} of {len(quotes)}; calibration a={cal_ab[0]:.3f} b={cal_ab[1]:.3f}")
    vol = mk[mk["series_ticker"] == SERIES].groupby("contract_month")["volume"].sum()
    print("\nKXRAINCHIM volume by event:\n" + vol.to_string())

    # ---- 4. capacity ---------------------------------------------------------------------
    ob = pd.read_csv(PROCESSED / "kalshi_rain_orderbook_summary.csv")
    ob = ob[ob["series_ticker"] == SERIES]
    snaps = {f"2026-10-29 (Nov 2026 ladder)": books_from_frame(ob, "2026-11")}
    live_path = sorted(PROCESSED.glob("rowcrop_kxrainchim_orderbook_*.csv"))
    if args.refresh_book:
        live = live_book_snapshot()
        p = PROCESSED / f"rowcrop_kxrainchim_orderbook_{live['snapshot_utc'].iloc[0]}.csv"
        live.to_csv(p, index=False)
        live_path = [p]
    if live_path:
        live = pd.read_csv(live_path[-1])
        for mon in sorted(live["contract_month"].astype(str).unique()):
            snaps[f"{live['snapshot_utc'].iloc[0]} ({mon} ladder)"] = books_from_frame(live, mon)
    cap_rows, fill_rows = [], []
    farm_legs = {}
    for r_ in leg_rows:
        if r_["target"] == "model":
            farm_legs.setdefault(r_["case"], []).append(r_)
    for lab, books in snaps.items():
        bm = int(lab.split("(")[1][5:7])
        dep = book_depth(books, rain, bm, lab)
        cap_rows.append(dep)
        for cid in ("corn_jul_no", "corn_jul_both", "soy_aug_no", "soy_aug_both", "corn_mayjun_yes"):
            if cid not in farm_legs:
                continue
            L = pd.DataFrame(farm_legs[cid]).rename(columns={"contracts_farm": "contracts"})
            f = farm_fill(L, books, rain, bm)
            fill_rows.append({"book": lab, "case": cid, **f,
                              "acres_fillable": FARM_ACRES * f["fill_share_contracts"]})
    cap = pd.concat(cap_rows)
    cap.to_csv(PROCESSED / "rowcrop_kxrainchim_book_depth.csv", index=False)
    print("\n## Order-book depth (contracts = $ of payout)\n")
    print(_md(cap[["book", "strike_in", "q_no", "no_contracts_any", "no_contracts_le95c", "no_contracts_sensible",
                   "yes_contracts_any", "yes_contracts_sensible"]], "{:,.1f}"))
    tot = cap.groupby("book")[["no_contracts_any", "no_contracts_le95c", "no_contracts_sensible",
                               "yes_contracts_any", "yes_contracts_sensible"]].sum()
    print("\n" + tot.to_string())
    print("\n## Farm fill (sensible price, moneyness-matched)\n")
    print(_md(pd.DataFrame(fill_rows)))

    # ---- 5. coverage ---------------------------------------------------------------------
    yr = args.acres_year or 2022
    acres = county_acres(yr, "CENSUS")
    print(f"\ncounty rows withheld (D): {int(acres['withheld'].sum())} of {len(acres)}")
    gz = gazetteer()
    smap = pd.read_csv(PROCESSED / "station_map.csv")
    act = smap[(smap["events_to"].astype(str) >= "2026-11") & smap["series_ticker"].str.startswith("KX")]
    act = act.drop_duplicates("series_ticker", keep="last")[["series_ticker", "station_key", "state", "lat", "lon"]]
    a = acres.groupby(["geoid", "located", "State", "County", "crop"])["value"].sum().unstack("crop").fillna(0).reset_index()
    a["corn_soy_acres"] = a.get("corn", 0) + a.get("soybeans", 0)
    loc = a[a["located"]].merge(gz, on="geoid", how="left")
    unl = a.loc[~a["located"], "corn_soy_acres"].sum()
    n_miss = int(loc["lat"].isna().sum())
    loc = loc.dropna(subset=["lat"])
    ns = rc.nearest_station(loc["lat"], loc["lon"], act)
    loc = pd.concat([loc.reset_index(drop=True), ns], axis=1)
    loc.to_csv(PROCESSED / "rowcrop_county_station_distance.csv", index=False,
               columns=["geoid", "State", "County", "USPS", "corn", "soybeans", "corn_soy_acres", "lat", "lon",
                        "nearest_station", "distance_mi"])
    tot_all = loc["corn_soy_acres"].sum() + unl
    sh = rc.share_within(loc["distance_mi"], loc["corn_soy_acres"], RADII)
    print(f"\n## Coverage ({yr} NASS county acres; {len(act)} active stations)\n")
    print(f"located county acres {loc['corn_soy_acres'].sum():,.0f}; unlocated (combined counties) {unl:,.0f}; "
          f"counties without gazetteer match {n_miss}")
    for r, s in sh.items():
        print(f"within {r:.0f} mi: {s:.1%} of located acres; {s * loc['corn_soy_acres'].sum() / tot_all:.1%} of all")
    print(f"median acre-weighted distance: {np.interp(0.5, np.cumsum(loc.sort_values('distance_mi')['corn_soy_acres']) / loc['corn_soy_acres'].sum(), np.sort(loc['distance_mi'])):.0f} mi")
    near = loc[loc["distance_mi"] <= 50].groupby("nearest_station")["corn_soy_acres"].sum().sort_values(ascending=False)
    print("\nacres within 50 mi by station:\n" + (near / 1e6).round(2).to_string())
    near100 = loc[loc["distance_mi"] <= 100].groupby("nearest_station")["corn_soy_acres"].sum().sort_values(ascending=False)
    print("\nacres within 100 mi by station:\n" + (near100 / 1e6).round(2).to_string())
    stt = loc.groupby("USPS").apply(lambda g: pd.Series({
        "acres_m": g["corn_soy_acres"].sum() / 1e6,
        "share_le50": g.loc[g["distance_mi"] <= 50, "corn_soy_acres"].sum() / g["corn_soy_acres"].sum(),
        "share_le100": g.loc[g["distance_mi"] <= 100, "corn_soy_acres"].sum() / g["corn_soy_acres"].sum()}),
        include_groups=False).sort_values("acres_m", ascending=False).head(12)
    print("\nby state (top 12 by acres):\n" + stt.round(3).to_string())
    top = loc.nlargest(25, "corn_soy_acres")[["State", "County", "corn_soy_acres", "nearest_station", "distance_mi"]]
    print("\ntop 25 counties:\n" + _md(top, "{:,.0f}"))
    print(f"top-25 counties within 50 mi: {(top['distance_mi'] <= 50).sum()}; within 100 mi: {(top['distance_mi'] <= 100).sum()}")
    kane = loc[loc["geoid"] == "17089"]
    print("\nKane:", kane[["corn", "soybeans", "nearest_station", "distance_mi"]].to_dict("records"))

    # ---- figure --------------------------------------------------------------------------
    fig_rain_vs_yield(ev, models, normals)
    return 0


def fig_rain_vs_yield(ev: pd.DataFrame, models: dict, normals: dict) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), constrained_layout=True)
    for ax, (tag, crop, mon, lab) in zip(axes, (("corn", "corn", 7, "July"), ("soy", "soybeans", 8, "August"))):
        col = f"ord_{lab[:3].lower()}_in"
        ax.scatter(ev[col], ev[f"kane_{tag}_dev_bu"], s=18, color="#2a6f97", zorder=3, label="Kane yield minus trend")
        xs = np.linspace(0, max(10, ev[col].max()), 200)
        mm = models[(crop, SPEC_MAIN, mon)]
        p = rc.state_equivalent_rain(xs, normals[mon], mm["p0"], clip=mm["clip"])
        ax.plot(xs, rc.quadratic_yield_change(p, mm["b1"], mm["b2"], mm["p0"]), color="#c8553d", lw=2,
                label="doc 03a IL model (by anomaly, clipped)")
        for _, r in ev.nsmallest(3, f"kane_{tag}_dev_bu").iterrows():
            ax.annotate(str(int(r["year"])), (r[col], r[f"kane_{tag}_dev_bu"]), fontsize=8, xytext=(4, -2),
                        textcoords="offset points")
        ax.axhline(0, color="0.6", lw=0.8)
        ax.set_xlabel(f"O'Hare {lab} rain (in)")
        ax.set_ylabel("bu/acre vs trend")
        ax.set_title(f"Kane Co. {crop}, 1980-2025")
        ax.spines[["top", "right"]].set_visible(False)
    h, lab = axes[0].get_legend_handles_labels()
    fig.legend(h, lab, frameon=False, fontsize=9, loc="outside lower center", ncol=2)
    fig.savefig(FIGURES / "rc_rain_vs_kane_yield.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    raise SystemExit(main())
