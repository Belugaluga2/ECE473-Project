"""A3: what PRF pays a farmer vs what a Kalshi monthly-rain hedge would pay, and what that hedge costs.

Run from the repo root:   python scripts/run_payout_comparison.py

For each of the 11 representative farms in data/scenarios/farms.yaml this script

1. builds the farm's Kalshi hedge from the doc-08 replication weights (H3 = real Kalshi strikes;
   H2 = 0.25-inch strikes and H1 = ideal station index for reference): contracts per leg =
   weight per $ of protection x the interval's share x the policy's total protection;
2. computes the hedge's dollar payout in every year from settlement-station rain
   (station_monthly_precip.csv, complete months only) and compares it with the PRF indemnity
   under two index regimes: CPC "as paid" (what RMA actually paid on, 1969-2025) and NCEI (what
   PRF pays on from 2026-08-31, 1951-2025);
3. prices the hedge under fair value, a calibrated market price, and observed Kalshi prices
   (DFW/DEN candles at listing, and the 2026-10-29 order books for every site), with taker
   fees and the cost of prepaying contracts;
4. compares the farmer's cost per $1 of expected payout for PRF and for the hedge.

Outputs: data/processed/payout_comparison_farm_year.csv, payout_comparison_summary.csv,
docs/figures/a3_*.png, and the tables between the AUTO markers in
docs/analysis/09_payout_comparison.md. Pure functions live in src/agri_hedge/pricing.py.
Runs in about a minute; no network.
"""
from __future__ import annotations

import json
import sys
import time

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker  # noqa: E402,F401
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import yaml  # noqa: E402

from agri_hedge import pricing as pr  # noqa: E402
from agri_hedge.config import DOCS, FIGURES, PROCESSED, SCENARIOS  # noqa: E402
from agri_hedge.prf import (PRFElection, dollar_amount_of_protection_per_acre,  # noqa: E402
                            payment_calculation_factor, simulate_years, summarize_years)
from agri_hedge.prf_intervals import INTERVAL_MONTHS, INTERVAL_NAMES  # noqa: E402

RATE_YEAR = 2026
HEADLINE = (2015, 2025)
LONG = {"cpc_as_paid": (1969, 2025), "ncei": (1951, 2025)}
TRAIN = (1951, 2009)
FAIR_WINDOW = (1991, 2025)
FAIR_SENS = ((1951, 2025), (1951, 2009), (1996, 2025), (2006, 2025))
CAL_MAIN = (21, "last_price")
CAL_SENS = ((7, "last_price"), (14, "last_price"), (14, "mid"), (21, "mid"))
MAX_LISTING_SPREAD = 0.25       # ignore placeholder quotes (e.g. 1c bid / 99c ask) at listing
BOOK_CAP_USEFUL = 0.95          # doc 05b convention: NO above 95c is not insurance
SENSIBLE_TOL = 0.10             # "sensible price": at most 10c above the contract's fair value
REGIME_LABEL = {"cpc_as_paid": "CPC as paid", "ncei": "NCEI (from 2026)"}
REGIME_TARGET = {"cpc_as_paid": "cpc", "ncei": "ncei"}
LIVE_FARMS = ("DFW_hay", "DEN_graze")   # farms whose whole 2026 season had listed Kalshi markets
EXAMPLE_FARMS = ("DFW_hay", "OKC_graze", "ABQ_graze")
DOC = DOCS / "analysis" / "09_payout_comparison.md"
AUTO_BEGIN = "<!-- BEGIN AUTO: payout comparison tables (scripts/run_payout_comparison.py) -->"
AUTO_END = "<!-- END AUTO: payout comparison tables -->"
OUT_FARM_YEAR = PROCESSED / "payout_comparison_farm_year.csv"
OUT_SUMMARY = PROCESSED / "payout_comparison_summary.csv"

#: Pricing scenarios: name -> (mid-price model, half spread paid, taker fee?)
SCENARIOS_DEF = {
    "a0_fair_maker": ("fair", 0.0, False),
    "a1_fair_taker_spread4.5c": ("fair", pr.SPREAD_LOW / 2, True),
    "a2_fair_taker_spread13.1c": ("fair", pr.SPREAD_HIGH / 2, True),
    "b1_calibrated_taker_spread4.5c": ("calib", pr.SPREAD_LOW / 2, True),
    "b2_calibrated_taker_spread13.1c": ("calib", pr.SPREAD_HIGH / 2, True),
    "c1_dfw_den_listing_ask_curve": ("curve", 0.0, True),
}
SCEN_LABEL = {
    "a0_fair_maker": "(a0) fair value, resting limit order (no fee, no spread)",
    "a1_fair_taker_spread4.5c": "(a1) fair value + half of a 4.5c spread + taker fee",
    "a2_fair_taker_spread13.1c": "(a2) fair value + half of a 13.1c spread + taker fee",
    "b1_calibrated_taker_spread4.5c": "(b1) calibrated market mid + half of 4.5c + fee",
    "b2_calibrated_taker_spread13.1c": "(b2) calibrated market mid + half of 13.1c + fee",
    "c1_dfw_den_listing_ask_curve": "(c1) DFW/DEN ask-at-listing markup curve + fee",
}
CENTRAL = "a1_fair_taker_spread4.5c"


# ---------------------------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------------------------

def load_inputs() -> dict:
    farms = yaml.safe_load((SCENARIOS / "farms.yaml").read_text(encoding="utf-8"))["farms"]
    W = pd.read_csv(PROCESSED / "replication_weights.csv")
    W = W[W["role"] == "farm"]
    st = pd.read_csv(PROCESSED / "station_monthly_precip.csv")
    scen = pd.read_csv(PROCESSED / "prf_scenario_results.csv", dtype={"grid_id": str, "county_fips": str})
    act = pd.read_csv(PROCESSED / "prf_actuarial_study_grids.csv", dtype={"grid_id": str, "county_fips": str})
    grids = sorted({int(g) for g in scen["grid_id"].unique()})
    cpc = pd.read_parquet(PROCESSED / "cpc_interval_index.parquet",
                          columns=["grid_id", "year", "interval_name", "index_value_ours"])
    cpc = cpc[cpc["grid_id"].isin(grids)].copy()
    cpc["interval_name"] = cpc["interval_name"].astype(str)
    ncei_dst = pd.read_csv(PROCESSED / "prf_official_index.csv")
    ncei_dst = ncei_dst[ncei_dst["grid_id"].isin(grids)].copy()
    ncei_reb = pd.read_parquet(PROCESSED / "ncei_interval_index.parquet",
                               columns=["grid_id", "year", "interval_name", "index_value_ours"])
    ncei_reb = ncei_reb[ncei_reb["grid_id"].isin(grids)].copy()
    ncei_reb["interval_name"] = ncei_reb["interval_name"].astype(str)
    bt = pd.read_csv(PROCESSED / "replication_backtest.csv", dtype={"farm_id": str}, low_memory=False)
    bt = bt[bt["role"] == "farm_policy"].copy()
    cal = pd.read_csv(PROCESSED / "kalshi_rain_calibration.csv")
    mk = pd.read_parquet(PROCESSED / "kalshi_rain_markets.parquet")
    cd = pd.read_parquet(PROCESSED / "kalshi_rain_daily_candles.parquet")
    ob = pd.read_csv(PROCESSED / "kalshi_rain_orderbook_summary.csv")
    return dict(farms=farms, W=W, st=st, scen=scen, act=act, cpc=cpc, ncei_dst=ncei_dst,
                ncei_reb=ncei_reb, bt=bt, cal=cal, mk=mk, cd=cd, ob=ob)


def index_wide(tbl: pd.DataFrame, grid_id: int, col: str) -> pd.DataFrame:
    """Year x interval table of one grid's index (100 = normal)."""
    g = tbl[tbl["grid_id"] == int(grid_id)]
    w = g.pivot_table(index="year", columns="interval_name", values=col, aggfunc="first")
    return w.reindex(columns=INTERVAL_NAMES)


# ---------------------------------------------------------------------------------------------
# PRF side
# ---------------------------------------------------------------------------------------------

def farm_election(farm: dict, act: pd.DataFrame, grid_id: str) -> tuple[PRFElection, dict]:
    """The farm's 2026 PRF election and per-interval premium rates (mirrors run_scenarios.py)."""
    use = str(farm.get("intended_use", "grazing")).lower()
    irr = "not specified" if use == "grazing" else (farm.get("irrigation_practice") or "non-irrigated")

    def make(cbv):
        return PRFElection(grid_id=grid_id, county_base_value=float(cbv),
                           coverage_level=farm["coverage_level"], productivity_factor=farm["productivity_factor"],
                           insured_acres=float(farm["insured_acres"]), allocation=farm["interval_allocation"],
                           intended_use=use, irrigation_practice=irr,
                           organic_practice=farm.get("organic", "not organic"),
                           share=farm.get("share", 1.0) or 1.0, county_fips=str(farm.get("fips", "")),
                           label=farm["farm_id"])
    e0 = make(farm["county_base_value_usd_per_acre"])
    sel = act[(act["crop_year"] == RATE_YEAR) & (act["grid_id"] == str(grid_id))
              & (act["intended_use"] == e0.intended_use) & (act["irrigation_practice"] == e0.irrigation_practice)
              & (act["organic_practice"] == e0.organic_practice)
              & np.isclose(act["coverage_level"], e0.coverage_level)]
    fips = str(farm.get("fips", "")).zfill(5)
    sel = sel[sel["county_fips"] == (fips if fips in set(sel["county_fips"]) else sel["county_fips"].iloc[0])]
    sel = sel.drop_duplicates("interval_name").set_index("interval_name")
    return make(float(sel["county_base_value_usd_per_acre"].iloc[0])), sel["premium_rate"].to_dict()


def prf_indemnity_by_year(e: PRFElection, rates: dict, wide: pd.DataFrame) -> pd.Series:
    """Total indemnity per year ('official' rounding); NaN if any insured interval is missing."""
    yr = summarize_years(simulate_years(e, rates, wide.copy(), rounding="official", validate=False))
    return yr["indemnity"].where(yr["n_intervals_missing"] == 0)


# ---------------------------------------------------------------------------------------------
# Kalshi prices observed in the data
# ---------------------------------------------------------------------------------------------

def listing_prices(mk: pd.DataFrame, cd: pd.DataFrame, rain: dict) -> pd.DataFrame:
    """Prices of DFW and DEN monthly-rain markets at listing (about 28-30 days before close).

    For each single-month 'greater' market in the Nov 2025 - Oct 2026 events, take the earliest
    daily candle (before the market closed) with a two-sided quote and a spread of at most
    MAX_LISTING_SPREAD. NO ask = 1 - YES bid, NO bid = 1 - YES ask. q = the station's
    climatological NO probability for that calendar month and strike over FAIR_WINDOW.
    """
    m = mk[mk["series_ticker"].isin(["KXRAINDALM", "KXRAINDENM"]) & mk["is_single_month"].astype(bool)
           & (mk["strike_type"] == "greater")].copy()
    m = m[m["contract_month"].astype(str) <= "2026-10"]
    m["close"] = pd.to_datetime(m["close_time"], utc=True)
    m["ev_close"] = m.groupby("event_ticker")["close"].transform("max")
    c = cd[cd["ticker"].isin(m["ticker"])].copy()
    c["end"] = pd.to_datetime(c["end_period_ts"], unit="s", utc=True)
    rows = []
    for _, r in m.iterrows():
        cc = c[(c["ticker"] == r["ticker"]) & (c["end"] <= r["close"])].sort_values("end")
        ok = (cc["yes_bid_close"] > 0) & (cc["yes_ask_close"] < 1) & \
             ((cc["yes_ask_close"] - cc["yes_bid_close"]) <= MAX_LISTING_SPREAD)
        cc = cc[ok]
        site = r["study_site"]
        month = int(str(r["contract_month"])[5:7])
        k = float(r["floor_strike"])
        q = pr.leg_probability(rain[site], month, k, FAIR_WINDOW)
        base = dict(ticker=r["ticker"], site=site, contract_month=str(r["contract_month"]), month=month,
                    strike_in=k, q=q, result=r["result"], volume=r["volume"])
        if cc.empty:
            rows.append({**base, "quoted": False})
            continue
        x = cc.iloc[0]
        rows.append({**base, "quoted": True,
                     "days_before_close": (r["ev_close"] - x["end"]).total_seconds() / 86400,
                     "yes_bid": x["yes_bid_close"], "yes_ask": x["yes_ask_close"],
                     "no_ask": 1 - x["yes_bid_close"], "no_bid": 1 - x["yes_ask_close"],
                     "no_mid": 1 - (x["yes_bid_close"] + x["yes_ask_close"]) / 2})
    out = pd.DataFrame(rows)
    out["no_paid"] = out["result"].map({"no": 1.0, "yes": 0.0})
    out["markup_ask"] = out["no_ask"] - out["q"]
    out["markup_mid"] = out["no_mid"] - out["q"]
    return out


Q_BINS = [0.0, 0.05, 0.2, 0.4, 0.6, 0.8, 0.95, 1.0001]


def markup_curve(obs: pd.DataFrame) -> pd.DataFrame:
    """Mean NO ask and mid markup over climatology by bins of the climatological probability q."""
    d = obs[obs["quoted"]].copy()
    d["bin"] = pd.cut(d["q"], Q_BINS, right=False)
    g = d.groupby("bin", observed=True)
    t = pd.DataFrame({"n": g.size(), "q_mean": g["q"].mean(), "no_ask_mean": g["no_ask"].mean(),
                      "no_mid_mean": g["no_mid"].mean(), "markup_ask": g["markup_ask"].mean(),
                      "markup_mid": g["markup_mid"].mean(),
                      "markup_ask_median": g["markup_ask"].median(),
                      "n_settled": g["no_paid"].count(), "no_paid_share": g["no_paid"].mean()}).reset_index()
    t["bin"] = t["bin"].astype(str)
    return t


def curve_price(q, curve: pd.DataFrame) -> np.ndarray:
    """NO ask implied by the markup curve: q + interpolated mean markup (flat beyond the end bins)."""
    return pr.clip_price(np.asarray(q, float) + np.interp(np.asarray(q, float), curve["q_mean"], curve["markup_ask"]))


def nov_books(ob: pd.DataFrame) -> dict:
    """{(site, strike): list of YES bids [(price, size)]} for the Nov 2026 ladders of the study sites."""
    d = ob[(ob["contract_month"] == "2026-11") & ob["study_site"].notna()]
    return {(r["study_site"], float(r["strike"])): json.loads(r["yes_bids"]) for _, r in d.iterrows()}


# ---------------------------------------------------------------------------------------------
# Per-farm analysis
# ---------------------------------------------------------------------------------------------

def analyse_farm(farm: dict, D: dict, rain: dict, cal_ab: tuple, curve: pd.DataFrame, obs: pd.DataFrame,
                 books: dict) -> dict:
    fid, site = farm["farm_id"], farm["site"]
    cov = round(float(farm["coverage_level"]), 2)
    sc = D["scen"][D["scen"]["farm_id"] == fid].set_index("year").sort_index()
    gid = str(sc["grid_id"].iloc[0])
    e, rates = farm_election(farm, D["act"], gid)
    prot = float(dollar_amount_of_protection_per_acre(e.county_base_value, e.coverage_level,
                                                      e.productivity_factor)) * e.insured_acres * e.share
    years = np.arange(1951, 2026)
    # ---- PRF under both regimes
    prf_ncei = sc["indemnity_usd"].reindex(years)
    prf_ncei_check = prf_indemnity_by_year(e, rates, index_wide(D["ncei_dst"], gid, "index_value")).reindex(years)
    ncei_check_maxdiff = float((prf_ncei - prf_ncei_check).abs().max())
    prf_cpc = prf_indemnity_by_year(e, rates, index_wide(D["cpc"], gid, "index_value_ours")).reindex(years)
    # ---- hedges from weights
    W = D["W"]
    legs, pay = {}, {}
    for tgt in ("ncei", "cpc"):
        for fam in ("H3", "H2"):
            for fit in ("full", "train"):
                w = W[(W["target_index"] == tgt) & (W["hedge_family"] == fam) & (W["fit_window"] == fit)
                      & (W["site"] == site) & np.isclose(W["coverage"], cov)]
                lg = pr.farm_hedge_legs(w, e.allocation, prot)
                legs[(tgt, fam, fit)] = lg
                pay[(tgt, fam, fit)] = pr.hedge_payout_by_year(lg, rain[site], years)
    # ---- reference hedges from the doc-08 backtest (per $ of protection)
    b = D["bt"][D["bt"]["farm_id"] == fid]
    ref = {}
    for tgt in ("ncei", "cpc"):
        bb = b[b["target_index"] == tgt].set_index("year")
        for col in ("h3_loyo", "h2_loyo", "h1", "h1_scaled_split", "h3_split"):
            ref[(tgt, col)] = (bb[col] * bb["policy_protection_usd"]).reindex(years)
    split_check = float((ref[("ncei", "h3_split")] - pay[("ncei", "H3", "train")]).abs().max())
    fy = pd.DataFrame({
        "farm_id": fid, "site": site, "year": years, "grid_id": gid, "coverage_level": cov,
        "policy_protection_usd": float(sc["policy_protection_usd"].iloc[0]),
        "total_premium_usd": float(sc["total_premium_usd"].iloc[0]),
        "producer_premium_usd": float(sc["producer_premium_usd"].iloc[0]),
        "prf_cpc_as_paid_usd": prf_cpc.to_numpy(), "prf_ncei_usd": prf_ncei.to_numpy(),
        "h3_cpc_train_usd": pay[("cpc", "H3", "train")].to_numpy(),
        "h3_cpc_loyo_usd": ref[("cpc", "h3_loyo")].to_numpy(),
        "h3_cpc_full_usd": pay[("cpc", "H3", "full")].to_numpy(),
        "h3_ncei_train_usd": pay[("ncei", "H3", "train")].to_numpy(),
        "h3_ncei_loyo_usd": ref[("ncei", "h3_loyo")].to_numpy(),
        "h3_ncei_full_usd": pay[("ncei", "H3", "full")].to_numpy(),
        "h2_ncei_train_usd": pay[("ncei", "H2", "train")].to_numpy(),
        "h2_ncei_loyo_usd": ref[("ncei", "h2_loyo")].to_numpy(),
        "h2_cpc_train_usd": pay[("cpc", "H2", "train")].to_numpy(),
        "h2_cpc_loyo_usd": ref[("cpc", "h2_loyo")].to_numpy(),
        "h1_ncei_usd": ref[("ncei", "h1")].to_numpy(), "h1_cpc_usd": ref[("cpc", "h1")].to_numpy(),
        "h1s_ncei_split_usd": ref[("ncei", "h1_scaled_split")].to_numpy(),
    })
    # ---- payout comparisons
    comp = []
    for regime in ("cpc_as_paid", "ncei"):
        tgt = REGIME_TARGET[regime]
        prf_col = "prf_cpc_as_paid_usd" if regime == "cpc_as_paid" else "prf_ncei_usd"
        for wname, (y0, y1) in (("2015-2025", HEADLINE), ("long run", LONG[regime])):
            sub = fy[(fy["year"] >= y0) & (fy["year"] <= y1)]
            oos = "train" if wname == "2015-2025" else "loyo"
            variants = {"H3 out-of-sample": f"h3_{tgt}_{oos}_usd", "H3 in-sample": f"h3_{tgt}_full_usd",
                        "H2 out-of-sample": f"h2_{tgt}_{oos}_usd", "H1 ideal station index": f"h1_{tgt}_usd"}
            for hname, hcol in variants.items():
                m = pr.payout_comparison(sub[prf_col], sub[hcol], prot, years=sub["year"])
                comp.append({"farm_id": fid, "site": site, "regime": regime, "window": wname,
                             "years": f"{y0}-{y1}", "hedge": hname, **m})
    comp = pd.DataFrame(comp)
    # ---- pricing the forward hedge (H3, NCEI target, full-window weights)
    lg = legs[("ncei", "H3", "full")].copy()
    lg = pr.add_leg_probabilities(lg, rain[site], FAIR_WINDOW, "q")
    for wnd in FAIR_SENS:
        lg = pr.add_leg_probabilities(lg, rain[site], wnd, f"q_{wnd[0]}_{wnd[1]}")
    a, bcal = cal_ab
    mids = {"fair": lg["q"].to_numpy(), "calib": pr.calibrated_no_price(lg["q"], a, bcal),
            "curve": curve_price(lg["q"], curve)}
    fair_value = pr.expected_payout(lg, "q")
    costs = {}
    for name, (mid, hs, taker) in SCENARIOS_DEF.items():
        costs[name] = pr.cost_totals(pr.price_legs(lg, mids[mid], half_spread=hs, taker=taker))
    # sensitivities on the central scenario
    mid, hs, taker = SCENARIOS_DEF[CENTRAL]
    sens = {
        "central_with_kalshi_apy": pr.cost_totals(pr.price_legs(lg, mids[mid], hs, taker,
                                                                credited_rate=pr.KALSHI_APY))["cost_usd"],
        "central_direct_member_fee_tick": pr.cost_totals(pr.price_legs(lg, mids[mid], hs, taker,
                                                                       fee_tick=pr.FEE_TICK_DIRECT))["cost_usd"],
        "central_lockup_92_days": pr.cost_totals(pr.price_legs(lg, mids[mid], hs, taker, days=92))["cost_usd"],
    }
    for wnd in FAIR_SENS:
        sens[f"fair_value_{wnd[0]}_{wnd[1]}"] = pr.expected_payout(lg, f"q_{wnd[0]}_{wnd[1]}")
    # ---- (c) actual 2025-26 asks at listing (DFW, DEN only)
    actual = {}
    o = obs[(obs["site"] == site) & obs["quoted"]]
    if not o.empty:
        key = o.groupby(["month", "strike_in"])["no_ask"].first()
        ask = np.array([key.get((int(mm), float(kk)), np.nan) for mm, kk in zip(lg["contract_month"], lg["strike_in"])])
        priced = pr.price_legs(lg, ask, 0.0, True)
        t = pr.cost_totals(priced)
        okm = ~np.isnan(ask)
        fair_priced = float((lg["contracts"] * lg["q"])[okm].sum())
        actual = {"actual_cost_priced_usd": t["cost_usd"], "actual_fair_priced_usd": fair_priced,
                  "actual_load_priced": t["cost_usd"] / fair_priced if fair_priced else np.nan,
                  "actual_share_contracts_priced": t["contracts_priced"] / lg["contracts"].sum()}
    # ---- capacity in the Nov 2026 books
    # (1) "at all": each leg walks the same site's Nov 2026 book at the same strike, any price.
    # (2) "at a sensible price": each leg is matched to the Nov 2026 strike whose November chance of
    #     paying is closest to the leg's own chance (same moneyness), and only offers priced at most
    #     SENSIBLE_TOL above that strike's fair value count. Legs of one month that map to the same
    #     strike share that strike's depth. Both assume every month's book looks like November's.
    nov_q = {k: pr.leg_probability(rain[site], 11, k, FAIR_WINDOW)
             for (s_, k), bids in books.items() if s_ == site and bids}
    cap = lg[["contract_month", "strike_in", "contracts", "q"]].copy().reset_index(drop=True)
    f_any, f_95 = [], []
    for _, leg in cap.iterrows():
        bids = books.get((site, float(leg["strike_in"])), [])
        f_any.append(pr.walk_no_book(bids, leg["contracts"], max_price=pr.PRICE_MAX)["filled"])
        f_95.append(pr.walk_no_book(bids, leg["contracts"], max_price=BOOK_CAP_USEFUL)["filled"])
    cap["fill_any"], cap["fill_95"] = f_any, f_95
    cap["in_book"] = [bool(books.get((site, float(k)))) for k in cap["strike_in"]]
    ks = np.array(sorted(nov_q))
    cap["match_strike"] = [float(ks[np.argmin(np.abs(np.array([nov_q[k] for k in ks]) - q))]) if len(ks) else np.nan
                           for q in cap["q"]]
    cap["fill_sensible"] = 0.0
    for (mm, km), grp in cap.groupby(["contract_month", "match_strike"]):
        need = float(grp["contracts"].sum())
        w = pr.walk_no_book(books.get((site, float(km)), []), need,
                            max_price=min(pr.PRICE_MAX, nov_q[float(km)] + SENSIBLE_TOL))
        cap.loc[grp.index, "fill_sensible"] = grp["contracts"] * (w["filled"] / need if need else 0.0)
    by_m = cap.groupby("contract_month")[["contracts", "fill_any", "fill_95", "fill_sensible"]].sum()
    busiest = by_m["contracts"].idxmax()
    nov = cap[cap["contract_month"] == 11]
    nov_cost = nov_fair = 0.0
    for _, leg in nov.iterrows():
        w = pr.walk_no_book(books.get((site, float(leg["strike_in"])), []), leg["contracts"], max_price=pr.PRICE_MAX)
        nov_cost += w["cost_usd"] + w["fee_usd"]
        nov_fair += w["filled"] * float(leg["q"])
    tot_c, tot_p = cap["contracts"].sum(), (cap["contracts"] * cap["q"]).sum()
    capacity = {
        "contracts_per_year": float(tot_c),
        "busiest_month": int(busiest), "busiest_month_contracts": float(by_m.loc[busiest, "contracts"]),
        "busiest_month_fill_any": float(by_m.loc[busiest, "fill_any"]),
        "busiest_month_fill_95": float(by_m.loc[busiest, "fill_95"]),
        "busiest_month_fill_sensible": float(by_m.loc[busiest, "fill_sensible"]),
        "fill_share_any": float(cap["fill_any"].sum() / tot_c),
        "fill_share_95": float(cap["fill_95"].sum() / tot_c),
        "fill_share_sensible": float(cap["fill_sensible"].sum() / tot_c),
        "fill_share_payout_any": float((cap["fill_any"] * cap["q"]).sum() / tot_p),
        "fill_share_payout_sensible": float((cap["fill_sensible"] * cap["q"]).sum() / tot_p),
        "share_contracts_strike_not_listed_nov": float(cap.loc[~cap["in_book"], "contracts"].sum() / tot_c),
        "nov_contracts": float(nov["contracts"].sum()), "nov_fill_any": float(nov["fill_any"].sum()),
        "nov_fill_sensible": float(nov["fill_sensible"].sum()),
        "nov_cost_filled_usd": float(nov_cost), "nov_fair_filled_usd": float(nov_fair),
    }
    return dict(farm=farm, fid=fid, site=site, cov=cov, prot=prot, e=e, rates=rates, grid=gid, fy=fy, comp=comp,
                legs=legs, priced_legs=lg, fair_value=fair_value, costs=costs, sens=sens, actual=actual,
                capacity=capacity, cap=cap, checks={"ncei_recompute_maxdiff_usd": ncei_check_maxdiff,
                                                     "h3_train_vs_backtest_maxdiff_usd": split_check},
                prf={"producer_premium": float(sc["producer_premium_usd"].iloc[0]),
                     "total_premium": float(sc["total_premium_usd"].iloc[0]),
                     "protection_policy": float(sc["policy_protection_usd"].iloc[0])})


def live_2026(res: dict, D: dict, obs: pd.DataFrame, rain: dict) -> dict | None:
    """One real season: buy the 2026 legs at their listing asks, collect what they actually paid.

    PRF 2026 is computed per insured interval from the as-settled index: ADM final grid index
    where published (through Jun-Jul), else our NCEI rebuild (Jul-Aug onward settle on NCEI;
    RMA had not published them on 2026-10-29), so the PRF figure is partly provisional.
    """
    e, gid, lg = res["e"], res["grid"], res["priced_legs"]
    o = obs[(obs["site"] == res["site"]) & (obs["contract_month"].str.startswith("2026"))]
    rows = []
    for _, leg in lg.iterrows():
        x = o[(o["month"] == int(leg["contract_month"])) & (o["strike_in"] == float(leg["strike_in"]))]
        if x.empty:
            return None
        x = x.iloc[0]
        paid = 1.0 if x["result"] == "no" else (0.0 if x["result"] == "yes" else np.nan)
        if not np.isfinite(paid):
            r = rain[res["site"]].loc[2026, int(leg["contract_month"])]
            paid = float(r <= float(leg["strike_in"]) + 1e-9)
        price = x["no_ask"] if x["quoted"] else np.nan
        rows.append({"contracts": leg["contracts"], "price": price, "paid": paid, "q": leg["q"]})
    t = pd.DataFrame(rows)
    priced = pr.price_legs(t, t["price"].to_numpy(), 0.0, True)
    cost = pr.cost_totals(priced)
    payout = float((t["contracts"] * t["paid"]).sum())
    act = D["act"]
    adm = act[(act["crop_year"] == 2026) & (act["grid_id"] == gid)].drop_duplicates("interval_name") \
        .set_index("interval_name")["final_index_adm"]
    reb = D["ncei_reb"]
    reb = reb[(reb["grid_id"] == int(gid)) & (reb["year"] == 2026)].set_index("interval_name")["index_value_ours"]
    ind, src = 0.0, []
    for iv, share in e.allocation.items():
        idx = adm.get(iv, np.nan)
        s = "ADM final (CPC)"
        if not np.isfinite(idx):
            idx, s = reb.get(iv, np.nan), "our NCEI rebuild (provisional)"
        pcf = float(payment_calculation_factor(idx, e.trigger, decimals=3))
        ind += pcf * share * res["prot"]
        src.append(f"{iv} {idx:.1f} [{s}]")
    return {"farm_id": res["fid"], "kalshi_cost_usd": cost["cost_usd"],
            "kalshi_share_priced": cost["contracts_priced"] / t["contracts"].sum(),
            "kalshi_fair_value_usd": float((t["contracts"] * t["q"]).sum()), "kalshi_payout_usd": payout,
            "prf_indemnity_usd": ind, "prf_producer_premium_usd": res["prf"]["producer_premium"],
            "prf_index_sources": "; ".join(src)}


# ---------------------------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------------------------

def farm_summary(res: dict, prf_means: dict) -> dict:
    fid, fy, comp = res["fid"], res["fy"], res["comp"]

    def cm(regime, window, hedge, key):
        r = comp[(comp["regime"] == regime) & (comp["window"] == window) & (comp["hedge"] == hedge)]
        return float(r[key].iloc[0]) if len(r) else np.nan
    pp, tp = res["prf"]["producer_premium"], res["prf"]["total_premium"]
    prf_exp = prf_means["ncei_long"]
    fv = res["fair_value"]
    c = {k: v["cost_usd"] for k, v in res["costs"].items()}
    central = c[CENTRAL]
    sub = pr.subsidy_to_match(central, fv, pp, prf_exp)
    h = fy[(fy["year"] >= HEADLINE[0]) & (fy["year"] <= HEADLINE[1])]
    out = {
        "farm_id": fid, "site": res["site"], "coverage_level": res["cov"], "grid_id": res["grid"],
        "policy_protection_usd": res["prf"]["protection_policy"],
        "prf_total_premium_usd": tp, "prf_producer_premium_usd": pp, "prf_subsidy_usd": tp - pp,
        "prf_mean_cpc_as_paid_2015_2025_usd": prf_means["cpc_head"],
        "prf_mean_cpc_as_paid_1969_2025_usd": prf_means["cpc_long"],
        "prf_mean_ncei_2015_2025_usd": prf_means["ncei_head"], "prf_mean_ncei_1951_2025_usd": prf_exp,
        "kalshi_mean_payout_oos_cpc_2015_2025_usd": float(h["h3_cpc_train_usd"].mean()),
        "kalshi_mean_payout_oos_ncei_2015_2025_usd": float(h["h3_ncei_train_usd"].mean()),
        "kalshi_mean_payout_full_ncei_1951_2025_usd": float(fy["h3_ncei_full_usd"].mean()),
        "corr_cpc_as_paid_2015_2025_oos": cm("cpc_as_paid", "2015-2025", "H3 out-of-sample", "corr"),
        "corr_cpc_as_paid_1969_2025_loyo": cm("cpc_as_paid", "long run", "H3 out-of-sample", "corr"),
        "corr_ncei_2015_2025_oos": cm("ncei", "2015-2025", "H3 out-of-sample", "corr"),
        "corr_ncei_1951_2025_loyo": cm("ncei", "long run", "H3 out-of-sample", "corr"),
        "corr_ncei_1951_2025_insample": cm("ncei", "long run", "H3 in-sample", "corr"),
        "recovery_cpc_as_paid_2015_2025_oos": cm("cpc_as_paid", "2015-2025", "H3 out-of-sample", "recovery"),
        "recovery_ncei_1951_2025_loyo": cm("ncei", "long run", "H3 out-of-sample", "recovery"),
        "n_legs_h3": int(len(res["priced_legs"])),
        "kalshi_fair_value_1991_2025_usd": fv,
        "kalshi_share_fair_value_in_legs_q_ge_0.75": float(
            (res["priced_legs"]["contracts"] * res["priced_legs"]["q"])[res["priced_legs"]["q"] >= 0.75].sum() / fv),
        "kalshi_min_payout_full_1951_2025_usd": float(fy["h3_ncei_full_usd"].min()),
        "contracts_per_dollar_fair_value": float(res["priced_legs"]["contracts"].sum() / fv),
    }
    for k, v in c.items():
        out[f"kalshi_cost_{k}_usd"] = v
    out["kalshi_fee_central_usd"] = res["costs"][CENTRAL]["fee_usd"]
    out["kalshi_capital_central_usd"] = res["costs"][CENTRAL]["capital_usd"]
    for k, v in res["sens"].items():
        out[f"sens_{k}_usd"] = v
    out.update({f"{k}" if k.startswith("actual") else k: v for k, v in res["actual"].items()})
    out.update({
        "prf_producer_load": pp / prf_exp, "prf_full_premium_load": tp / prf_exp,
        "prf_producer_load_as_paid_2015_2025": pp / prf_means["cpc_head"],
        "kalshi_load_central": central / fv,
        "kalshi_load_min": min(c.values()) / fv, "kalshi_load_max": max(c.values()) / fv,
        "prf_net_benefit_usd": prf_exp - pp, "kalshi_net_benefit_central_usd": fv - central,
        "subsidy_needed_same_net_usd": sub["dollars_same_net"], "subsidy_needed_share_same_net": sub["share_same_net"],
        "subsidy_needed_share_same_load": sub["share_same_load"],
    })
    out.update({f"cap_{k}": v for k, v in res["capacity"].items()})
    return out


# ---------------------------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------------------------

def _style(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="0.85", lw=0.6)
    ax.set_axisbelow(True)


def fig_year_by_year(fy_all: pd.DataFrame, summ: pd.DataFrame, path):
    fig, axes = plt.subplots(len(EXAMPLE_FARMS), 1, figsize=(9, 2.9 * len(EXAMPLE_FARMS)), sharex=True)
    yrs = np.arange(HEADLINE[0], HEADLINE[1] + 1)
    for ax, fid in zip(axes, EXAMPLE_FARMS):
        d = fy_all[fy_all["farm_id"] == fid].set_index("year").reindex(yrs)
        s = summ.set_index("farm_id").loc[fid]
        wdt = 0.27
        ax.bar(yrs - wdt, d["prf_cpc_as_paid_usd"] / 1e3, wdt, color="0.15", label="PRF paid (CPC as paid)")
        ax.bar(yrs, d["prf_ncei_usd"] / 1e3, wdt, color="0.6", label="PRF on NCEI index (2026+ data)")
        ax.bar(yrs + wdt, d["h3_cpc_train_usd"] / 1e3, wdt, color="white", edgecolor="0.1", hatch="///",
               label="Kalshi hedge (H3, out of sample)")
        ax.axhline(s["prf_producer_premium_usd"] / 1e3, color="0.1", ls="--", lw=1.2, label="PRF premium the farmer pays")
        ax.axhline(s[f"kalshi_cost_{CENTRAL}_usd"] / 1e3, color="0.1", ls=":", lw=1.6,
                   label="Kalshi hedge cost (central)")
        miss = d.index[d["h3_cpc_train_usd"].isna()]
        for y in miss:
            ax.text(y + wdt, 0.2, "n/a", ha="center", va="bottom", fontsize=7, rotation=90)
        ax.set_title(f"{fid}: protection ${s['policy_protection_usd']:,.0f}; correlation "
                     f"{s['corr_cpc_as_paid_2015_2025_oos']:.2f} (as paid, 2015-2025)", fontsize=10, loc="left")
        ax.set_ylabel("$ thousand per year")
        _style(ax)
    axes[0].legend(fontsize=7.5, ncol=2, frameon=False, loc="upper left")
    axes[-1].set_xticks(yrs)
    axes[-1].set_xlabel("Crop year")
    fig.suptitle("What PRF paid vs what a Kalshi monthly-rain hedge would have paid, 2015-2025", fontsize=11)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fig_cost_vs_payout(summ: pd.DataFrame, path):
    fig, ax = plt.subplots(figsize=(7.2, 6))
    s = summ
    x_prf = s["prf_mean_ncei_1951_2025_usd"] / 1e3
    x_k = s["kalshi_fair_value_1991_2025_usd"] / 1e3
    ax.scatter(x_prf, s["prf_producer_premium_usd"] / 1e3, marker="o", s=45, color="0.1", label="PRF: premium farmer pays")
    ax.scatter(x_prf, s["prf_total_premium_usd"] / 1e3, marker="o", s=45, facecolor="white", edgecolor="0.1",
               label="PRF: full premium (before subsidy)")
    lo = s[[f"kalshi_cost_{k}_usd" for k in SCENARIOS_DEF]].min(axis=1) / 1e3
    hi = s[[f"kalshi_cost_{k}_usd" for k in SCENARIOS_DEF]].max(axis=1) / 1e3
    mid = s[f"kalshi_cost_{CENTRAL}_usd"] / 1e3
    ax.errorbar(x_k, mid, yerr=[mid - lo, hi - mid], fmt="s", ms=6, color="0.45", ecolor="0.45", capsize=3,
                label="Kalshi hedge: central cost (bar = scenario range)")
    top = float(max(x_prf.max(), x_k.max(), hi.max())) * 1.08
    xx = np.linspace(0, top, 10)
    ax.plot(xx, xx, color="0.3", lw=1, label="cost = expected payout")
    ax.plot(xx, 0.5 * xx, color="0.3", lw=1, ls="--", label="cost = half of expected payout")
    for _, r in s.iterrows():
        ax.annotate(r["farm_id"], (r["prf_mean_ncei_1951_2025_usd"] / 1e3, r["prf_producer_premium_usd"] / 1e3),
                    fontsize=6.5, xytext=(3, -8), textcoords="offset points")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ticks = [2, 3, 5, 10, 20, 30]
    for axis in (ax.xaxis, ax.yaxis):
        axis.set_major_locator(matplotlib.ticker.FixedLocator(ticks))
        axis.set_major_formatter(matplotlib.ticker.FixedFormatter([str(t) for t in ticks]))
        axis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    ax.set_xlim(2.5, top * 1.1)
    ax.set_ylim(1.5, top * 1.2)
    ax.set_xlabel("Expected payout per year, $ thousand\n(PRF: NCEI 1951-2025 mean; Kalshi: 1991-2025 climatology)")
    ax.set_ylabel("Cost to the farmer per year ($ thousand)")
    ax.set_title("Annual cost vs expected payout, 11 farms (log scales)", fontsize=11)
    ax.legend(fontsize=7.5, frameon=False, loc="upper left")
    ax.grid(color="0.9", lw=0.5, which="both")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fig_load(summ: pd.DataFrame, path):
    s = summ.set_index("farm_id")
    cols = [("prf_producer_load", "PRF, farmer's share", dict(color="0.1")),
            ("prf_full_premium_load", "PRF, full premium", dict(color="0.55")),
            (f"kalshi_cost_a0_fair_maker_usd", "Kalshi (a0) fair, limit order", dict(color="white", edgecolor="0.1", hatch="..")),
            (f"kalshi_cost_{CENTRAL}_usd", "Kalshi (a1) fair + 4.5c spread + fee", dict(color="white", edgecolor="0.1", hatch="///")),
            (f"kalshi_cost_a2_fair_taker_spread13.1c_usd", "Kalshi (a2) fair + 13.1c spread + fee", dict(color="white", edgecolor="0.1", hatch="xx")),
            (f"kalshi_cost_c1_dfw_den_listing_ask_curve_usd", "Kalshi (c1) observed DFW/DEN asks", dict(color="0.8", edgecolor="0.1"))]
    fig, ax = plt.subplots(figsize=(10, 4.6))
    x = np.arange(len(s))
    wdt = 0.13
    for i, (c, lab, kw) in enumerate(cols):
        v = s[c] if "load" in c else s[c] / s["kalshi_fair_value_1991_2025_usd"]
        ax.bar(x + (i - 2.5) * wdt, v, wdt, label=lab, lw=0.6, **kw)
    ax.axhline(1.0, color="0.2", lw=1)
    ax.set_xticks(x)
    ax.set_xticklabels(s.index, rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("Cost per \\$1 of expected payout (\\$)")
    ax.set_title("What \\$1 of expected payout costs the farmer: PRF vs a Kalshi hedge", fontsize=11)
    ax.legend(fontsize=7.5, ncol=3, frameon=False, loc="upper left")
    ax.set_ylim(0, 1.8)
    _style(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fig_market_vs_fair(obs: pd.DataFrame, nov: pd.DataFrame, cal_ab: tuple, curve: pd.DataFrame, path):
    fig, ax = plt.subplots(figsize=(6.6, 6))
    o = obs[obs["quoted"]]
    for site, mkr in (("DFW", "o"), ("DEN", "^")):
        d = o[o["site"] == site]
        ax.scatter(d["q"], d["no_ask"], marker=mkr, s=22, facecolor="white", edgecolor="0.15",
                   label=f"{site} 2025-26, NO ask at listing (n={len(d)})")
    ax.scatter(nov["q"], nov["no_ask"], marker="x", s=22, color="0.45",
               label=f"7 PRF sites, Nov 2026 best NO ask, 2026-10-29 (n={len(nov)})")
    qq = np.linspace(0.005, 0.995, 200)
    ax.plot(qq, qq, color="0.2", lw=1, label="fair value (price = probability)")
    ax.plot(qq, pr.calibrated_no_price(qq, *cal_ab), color="0.2", ls="--", lw=1.2,
            label="calibrated mid (doc 05b pattern, 21 days)")
    ax.plot(qq, curve_price(qq, curve), color="0.5", ls="-.", lw=1.5, label="DFW/DEN mean ask by probability bin")
    ax.set_xlabel("Climatological probability the NO pays, 1991-2025 station record")
    ax.set_ylabel("Price of the NO contract ($)")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_title("Kalshi drought-contract prices vs fair value", fontsize=11)
    ax.legend(fontsize=7, frameon=False, loc="upper left")
    ax.grid(color="0.9", lw=0.5)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fig_capacity(summ: pd.DataFrame, path):
    s = summ.set_index("farm_id")
    fig, ax = plt.subplots(figsize=(9.5, 4.4))
    x = np.arange(len(s))
    wdt = 0.27
    ax.bar(x - wdt, s["cap_busiest_month_contracts"], wdt, color="0.15", label="Contracts the hedge needs (busiest month)")
    ax.bar(x, s["cap_busiest_month_fill_any"], wdt, color="0.6", label="Fillable at all (same strike, any price)")
    ax.bar(x + wdt, np.maximum(s["cap_busiest_month_fill_sensible"], 1), wdt, color="white", edgecolor="0.1",
           hatch="///", label="Fillable at a sensible price (<= fair + 10c)")
    ax.set_yscale("log")
    ax.set_xticks(x)
    new_sites = {"SAT", "OKC", "SGF", "ABQ", "TPA"}
    ax.set_xticklabels([f"{i}\n({s.loc[i, 'site']}{'*' if s.loc[i, 'site'] in new_sites else ''})" for i in s.index],
                       fontsize=7.5)
    ax.text(0.99, -0.2, "* listed 2026-10-25; depth supported by liquidity rewards ending 2026-11-01",
            transform=ax.transAxes, ha="right", fontsize=7)
    ax.set_ylabel("$1 contracts (log scale)")
    ax.set_title("Can today's order books fill a farm's hedge? Busiest month vs Nov 2026 book depth (2026-10-29)",
                 fontsize=10)
    ax.legend(fontsize=7.5, frameon=False, loc="upper left", ncol=3)
    _style(ax)
    ax.set_ylim(1, s["cap_busiest_month_contracts"].max() * 8)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


# ---------------------------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------------------------

def _m(v, nd=0):
    return "" if v is None or (isinstance(v, float) and not np.isfinite(v)) else f"{v:,.{nd}f}"


def _k(v):
    return "n/a" if not np.isfinite(v) else f"{v / 1e3:.1f}"


def doc_tables(summ, comp, fy_all, curve, obs, nov, cal_fits, live, checks) -> str:
    s = summ.set_index("farm_id")
    L = []
    L.append(f"Generated by `scripts/run_payout_comparison.py`. PRF = the farm's 2026 policy (2026 rates, "
             f"premium and subsidy) applied to each year's index. Kalshi hedge = the doc-08 H3 ladder (real "
             f"Kalshi strikes) scaled to the farm's protection. Central Kalshi cost = scenario {SCEN_LABEL[CENTRAL]}, "
             f"with T-bill capital cost {pr.DEFAULT_TBILL_RATE:.2%} for {pr.DEFAULT_LOCKUP_DAYS} days. "
             f"Fair value = expected payout under {FAIR_WINDOW[0]}-{FAIR_WINDOW[1]} station climatology.\n")
    # Table 1
    L.append("**Table 1. Plain-English summary per farm (dollars per year).** PRF payout = mean indemnity on the "
             "NCEI index 1951-2025 (the data PRF now pays on) and, in brackets, as actually paid on CPC 2015-2025. "
             "Kalshi payout = mean payout of the hedge under 1991-2025 climatology (its fair value) and, in brackets, the out-of-sample hedge's mean payout in 2015-2025 (CPC weights). Correlation = "
             "out-of-sample hedge vs PRF as paid, 2015-2025 (fit 1951-2009). Fill today = share of the hedge's "
             "contracts that November-2026-sized order books (2026-10-29) could fill at all (same strike, any price) / "
             "at a sensible price (same chance of paying, at most 10 cents above fair value); see Table 9.\n")
    L.append("| Farm | PRF premium farmer pays | PRF full premium | PRF avg payout (as paid 2015-25) | Kalshi central cost | "
             "Kalshi avg payout (2015-25 out of sample) | Correlation | Fill today: at all / sensible price |")
    L.append("|---|---|---|---|---|---|---|---|")
    for f, r in s.iterrows():
        L.append(f"| {f} | {_m(r['prf_producer_premium_usd'])} | {_m(r['prf_total_premium_usd'])} | "
                 f"{_m(r['prf_mean_ncei_1951_2025_usd'])} ({_m(r['prf_mean_cpc_as_paid_2015_2025_usd'])}) | "
                 f"{_m(r[f'kalshi_cost_{CENTRAL}_usd'])} | {_m(r['kalshi_fair_value_1991_2025_usd'])} "
                 f"({_m(r['kalshi_mean_payout_oos_cpc_2015_2025_usd'])}) | "
                 f"{_m(r['corr_cpc_as_paid_2015_2025_oos'], 2)} | {r['cap_fill_share_any']:.0%} / "
                 f"{r['cap_fill_share_sensible']:.0%} |")
    tot = s[["prf_producer_premium_usd", "prf_total_premium_usd", "prf_mean_ncei_1951_2025_usd",
             f"kalshi_cost_{CENTRAL}_usd", "kalshi_fair_value_1991_2025_usd", "prf_mean_cpc_as_paid_2015_2025_usd",
             "kalshi_mean_payout_oos_cpc_2015_2025_usd"]].sum()
    L.append(f"| **All 11** | {_m(tot.iloc[0])} | {_m(tot.iloc[1])} | {_m(tot.iloc[2])} ({_m(tot.iloc[5])}) | "
             f"{_m(tot.iloc[3])} | {_m(tot.iloc[4])} ({_m(tot.iloc[6])}) | median {s['corr_cpc_as_paid_2015_2025_oos'].median():.2f} | "
             f"{(s['cap_fill_share_any'] * s['cap_contracts_per_year']).sum() / s['cap_contracts_per_year'].sum():.0%} / "
             f"{(s['cap_fill_share_sensible'] * s['cap_contracts_per_year']).sum() / s['cap_contracts_per_year'].sum():.0%} |\n")
    # Table 2 year by year
    yrs = list(range(HEADLINE[0], HEADLINE[1] + 1))
    L.append("**Table 2. Year by year, 2015-2025: PRF as actually paid (CPC) / Kalshi hedge payout, $ thousand.** "
             "Hedge = H3 weights fit to the CPC index on 1951-2009 (out of sample), settled on station rain. "
             "n/a = a needed station month has a missing day. The NCEI version is in "
             "`payout_comparison_farm_year.csv`.\n")
    L.append("| Farm | " + " | ".join(str(y) for y in yrs) + " | Total |")
    L.append("|---|" + "---|" * (len(yrs) + 1))
    for f in s.index:
        d = fy_all[fy_all["farm_id"] == f].set_index("year").reindex(yrs)
        cells = [f"{_k(p)} / {_k(h)}" for p, h in zip(d["prf_cpc_as_paid_usd"], d["h3_cpc_train_usd"])]
        ok = d["h3_cpc_train_usd"].notna()
        L.append(f"| {f} | " + " | ".join(cells) +
                 f" | {_k(d.loc[ok, 'prf_cpc_as_paid_usd'].sum())} / {_k(d.loc[ok, 'h3_cpc_train_usd'].sum())} |")
    L.append("")
    # Table 3 comparison metrics
    L.append("**Table 3. Payout match by regime and window (H3 Kalshi ladder, out of sample).** 2015-2025 uses "
             "weights fit on 1951-2009; the long run uses leave-one-year-out predictions. Recovery = share of PRF's "
             "dollars matched by the hedge in the same year. PRF-only year = PRF paid at least 5% of protection and "
             "the hedge less than half of that; Kalshi-only year = the reverse.\n")
    L.append("| Farm | Regime | Window | Years | Corr | Recovery | Hedge / PRF total | PRF-only years | "
             "Kalshi-only years | Worst shortfall (year, $) | Worst overpayment (year, $) |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|")
    c3 = comp[comp["hedge"] == "H3 out-of-sample"]
    for _, r in c3.sort_values(["farm_id", "regime", "window"], key=lambda x: x if x.name != "window" else x.map({"2015-2025": 0, "long run": 1})).iterrows():
        L.append(f"| {r['farm_id']} | {REGIME_LABEL[r['regime']]} | {r['window']} | {r['n_years']} | {r['corr']:.2f} | "
                 f"{r['recovery']:.0%} | {r['payout_ratio']:.2f} | {r['prf_only_years']} "
                 f"{('(' + r['prf_only_list'] + ')') if r['window'] == '2015-2025' and r['prf_only_list'] else ''} | "
                 f"{r['kalshi_only_years']} {('(' + r['kalshi_only_list'] + ')') if r['window'] == '2015-2025' and r['kalshi_only_list'] else ''} | "
                 f"{r['worst_shortfall_year']}, {_m(r['worst_shortfall_usd'])} | {r['worst_overpay_year']}, {_m(r['worst_overpay_usd'])} |")
    L.append("")
    # Table 4 families
    L.append("**Table 4. Reference hedges: median over the 11 farms.** H1 = ideal contract on the station's own "
             "two-month index (not tradable); H2 = 0.25-inch monthly ladder (mostly not listed); H3 = real Kalshi "
             "strikes. In-sample = weights fit on 1951-2025, judged on the same years.\n")
    L.append("| Regime | Window | Hedge | Corr | Recovery | Hedge / PRF total | PRF-only years (sum over farms) | Kalshi-only years (sum) |")
    L.append("|---|---|---|---|---|---|---|---|")
    g = comp.groupby(["regime", "window", "hedge"])
    for (rg, wn, hd), d in g:
        L.append(f"| {REGIME_LABEL[rg]} | {wn} | {hd} | {d['corr'].median():.2f} | {d['recovery'].median():.0%} | "
                 f"{d['payout_ratio'].median():.2f} | {int(d['prf_only_years'].sum())} | {int(d['kalshi_only_years'].sum())} |")
    L.append("")
    # Table 5 costs
    L.append("**Table 5. Annual cost of each farm's Kalshi hedge under each pricing assumption ($ per year, "
             "including taker fee where stated and T-bill capital cost).** Fair value = the hedge's expected payout. "
             "(c2) = the same hedge bought at the actual 2025-26 asks at listing, for the legs that had a two-sided "
             "quote, expressed as cost per $1 of fair value of those legs.\n")
    hdr = ["Farm", "Fair value"] + [k.split("_")[0] for k in SCENARIOS_DEF] + ["(c2) actual asks, cost / fair", "Fees in a1", "Capital cost in a1"]
    L.append("| " + " | ".join(hdr) + " |")
    L.append("|" + "---|" * len(hdr))
    for f, r in s.iterrows():
        act = (f"{r['actual_load_priced']:.2f} ({r['actual_share_contracts_priced']:.0%} of contracts quoted)"
               if "actual_load_priced" in r and np.isfinite(r.get("actual_load_priced", np.nan)) else "no history")
        L.append(f"| {f} | {_m(r['kalshi_fair_value_1991_2025_usd'])} | " +
                 " | ".join(_m(r[f'kalshi_cost_{k}_usd']) for k in SCENARIOS_DEF) +
                 f" | {act} | {_m(r['kalshi_fee_central_usd'])} | {_m(r['kalshi_capital_central_usd'])} |")
    L.append("\nScenario key: " + "; ".join(f"**{k.split('_')[0]}** {v.split(') ', 1)[1]}" for k, v in SCEN_LABEL.items()) + ".\n")
    L.append("**Table 5b. Why the hedge costs more than its fair value: its shape.** Contracts per $1 of fair value "
             "drive the spread and fee bill (each contract pays half the spread). Likely legs = NO contracts that "
             "paid in at least 75% of 1991-2025 months; they behave mostly like prepaid cash. Floor = the smallest annual payout "
             "of the forward hedge in 1951-2025.\n")
    L.append("| Farm | Legs | Contracts per year | Contracts per $1 of fair value | Share of fair value in likely legs | "
             "Floor payout ($/yr) | Spread + fee + capital over fair value (a1, $/yr) |")
    L.append("|---|---|---|---|---|---|---|")
    for f, r in s.iterrows():
        L.append(f"| {f} | {int(r['n_legs_h3'])} | {_m(r['cap_contracts_per_year'])} | {r['contracts_per_dollar_fair_value']:.2f} | "
                 f"{r['kalshi_share_fair_value_in_legs_q_ge_0.75']:.0%} | {_m(r['kalshi_min_payout_full_1951_2025_usd'])} | "
                 f"{_m(r[f'kalshi_cost_{CENTRAL}_usd'] - r['kalshi_fair_value_1991_2025_usd'])} |")
    L.append("")
    # Table 6 loads and net benefit
    L.append("**Table 6. Cost per $1 of expected payout (load), net benefit, and the subsidy Kalshi would need.** "
             "PRF expected payout = NCEI 1951-2025 mean. Kalshi expected payout = fair value (1991-2025). Net "
             "benefit = expected payout - cost. Subsidy to match = dollars per year someone would have to pay "
             "toward the Kalshi hedge so the farmer's expected net gain equals PRF's; 'same load' = share of the "
             "hedge's cost that would have to be paid so that $1 of expected payout costs the farmer what it costs "
             "under PRF.\n")
    L.append("| Farm | PRF load (farmer) | PRF load (farmer, as paid 2015-25) | PRF load (full premium) | Kalshi load central | Kalshi load range | "
             "PRF net benefit | Kalshi net benefit (central) | Subsidy to match net ($) | as share of hedge cost | "
             "Subsidy share for same load |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for f, r in s.iterrows():
        L.append(f"| {f} | {r['prf_producer_load']:.2f} | {r['prf_producer_load_as_paid_2015_2025']:.2f} | "
                 f"{r['prf_full_premium_load']:.2f} | {r['kalshi_load_central']:.2f} | "
                 f"{r['kalshi_load_min']:.2f}-{r['kalshi_load_max']:.2f} | {_m(r['prf_net_benefit_usd'])} | "
                 f"{_m(r['kalshi_net_benefit_central_usd'])} | {_m(r['subsidy_needed_same_net_usd'])} | "
                 f"{r['subsidy_needed_share_same_net']:.0%} | {r['subsidy_needed_share_same_load']:.0%} |")
    tot = s[["prf_producer_premium_usd", "prf_total_premium_usd", "prf_mean_ncei_1951_2025_usd",
             f"kalshi_cost_{CENTRAL}_usd", "kalshi_fair_value_1991_2025_usd", "subsidy_needed_same_net_usd",
             "prf_mean_cpc_as_paid_2015_2025_usd"]].sum()
    L.append(f"| **All 11 (dollar-weighted)** | {tot.iloc[0] / tot.iloc[2]:.2f} | {tot.iloc[0] / tot.iloc[6]:.2f} | "
             f"{tot.iloc[1] / tot.iloc[2]:.2f} | "
             f"{tot.iloc[3] / tot.iloc[4]:.2f} | | {_m(tot.iloc[2] - tot.iloc[0])} | {_m(tot.iloc[4] - tot.iloc[3])} | "
             f"{_m(tot.iloc[5])} | {tot.iloc[5] / tot.iloc[3]:.0%} | |\n")
    # Table 7 sensitivity
    L.append("**Table 7. Sensitivity of the central cost and of fair value ($ per year, all 11 farms summed).**\n")
    L.append("| Item | Value | Change vs central |")
    L.append("|---|---|---|")
    cen = s[f"kalshi_cost_{CENTRAL}_usd"].sum()
    fvt = s["kalshi_fair_value_1991_2025_usd"].sum()
    L.append(f"| Central cost (a1) | {_m(cen)} | |")
    for k, lab in (("central_with_kalshi_apy", f"Central, Kalshi credits {pr.KALSHI_APY:.2%} APY on positions"),
                   ("central_direct_member_fee_tick", "Central, fee rounded to $0.0001 (direct member)"),
                   ("central_lockup_92_days", "Central, 92-day lock-up instead of 31")):
        v = s[f"sens_{k}_usd"].sum()
        L.append(f"| {lab} | {_m(v)} | {v / cen - 1:+.2%} |")
    L.append(f"| Fair value, {FAIR_WINDOW[0]}-{FAIR_WINDOW[1]} climatology (main) | {_m(fvt)} | |")
    for wnd in FAIR_SENS:
        v = s[f"sens_fair_value_{wnd[0]}_{wnd[1]}_usd"].sum()
        L.append(f"| Fair value, {wnd[0]}-{wnd[1]} climatology | {_m(v)} | {v / fvt - 1:+.1%} vs main |")
    for (h, kind), (a, b), tot_b in cal_fits:
        L.append(f"| Calibrated mid + 4.5c spread + fee, calibration at {h} days ({kind}); a = {a:.3f}, b = {b:.3f} | "
                 f"{_m(tot_b)} | {tot_b / cen - 1:+.1%} |")
    L.append("")
    # Table 8 markup curve
    L.append("**Table 8. Observed Kalshi NO prices at listing vs climatology, DFW and DEN, Nov 2025 - Oct 2026.** "
             f"Earliest daily candle with a two-sided quote (spread <= {MAX_LISTING_SPREAD:.2f}); median "
             f"{obs.loc[obs['quoted'], 'days_before_close'].median():.0f} days before the event closes. "
             f"{int(obs['quoted'].sum())} of {len(obs)} markets had such a quote. q = share of 1991-2025 months with "
             "rain at or below the strike.\n")
    L.append("| q bin | Markets | Mean q | Mean NO ask | Mean NO mid | Mean ask - q | Median ask - q | Mean mid - q | "
             "Settled markets | Share where NO paid |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    for _, r in curve.iterrows():
        L.append(f"| {r['bin']} | {int(r['n'])} | {r['q_mean']:.3f} | {r['no_ask_mean']:.3f} | {r['no_mid_mean']:.3f} | "
                 f"{r['markup_ask']:+.3f} | {r['markup_ask_median']:+.3f} | {r['markup_mid']:+.3f} | "
                 f"{int(r['n_settled'])} | {r['no_paid_share']:.3f} |")
    oq = obs[obs["quoted"]]
    L.append(f"| all | {len(oq)} | {oq['q'].mean():.3f} | {oq['no_ask'].mean():.3f} | {oq['no_mid'].mean():.3f} | "
             f"{oq['markup_ask'].mean():+.3f} | {oq['markup_ask'].median():+.3f} | {oq['markup_mid'].mean():+.3f} | "
             f"{int(oq['no_paid'].count())} | {oq['no_paid'].mean():.3f} |\n")
    st_ = oq.dropna(subset=["no_paid"])
    L.append(f"On the {len(st_)} settled quoted markets the mean NO ask was {st_['no_ask'].mean():.3f}, the mean "
             f"climatological probability {st_['q'].mean():.3f}, and NO actually paid in {st_['no_paid'].mean():.3f} "
             "of them.\n")
    if len(nov):
        L.append("Nov 2026 books (2026-10-29), best NO ask minus November climatology, by site (mean over the strikes "
                 "with a YES bid): " + "; ".join(f"{st} {d['markup'].mean():+.3f} ({len(d)} strikes)"
                                                 for st, d in nov.groupby("site")) + ".\n")
    # Table 9 capacity
    L.append("**Table 9. Fill capacity in the 2026-10-29 order books.** 'At all' = each leg walks the same site's "
             "November 2026 book at the same strike, any price up to 99 cents (an upper bound: much of the new-site "
             "depth is NO offered at 98-99 cents). 'Sensible price' = each leg uses the November strike with the "
             "closest chance of paying and counts only offers at most 10 cents above that strike's fair value; legs "
             "of one month that map to the same strike share its depth. Both assume every month's book looks like "
             "November's. Payout-weighted = share of the hedge's expected payout that could be filled. Nov legs = "
             "the farm's real November 2026 legs bought now at any price (cost incl. fee per $1 of their fair value).\n")
    L.append("| Farm | Contracts per year | Busiest month | Needed that month | Fillable at all | Fillable at a sensible price | "
             "Share of contracts: at all / sensible | Share of expected payout: at all / sensible | Nov legs: needed / fillable / cost per $1 fair |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for f, r in s.iterrows():
        nov_txt = "no Nov legs"
        if r["cap_nov_contracts"] > 0:
            ratio = r["cap_nov_cost_filled_usd"] / r["cap_nov_fair_filled_usd"] if r["cap_nov_fair_filled_usd"] > 0 else np.nan
            nov_txt = f"{_m(r['cap_nov_contracts'])} / {_m(r['cap_nov_fill_any'])} / {_m(ratio, 2)}"
        L.append(f"| {f} | {_m(r['cap_contracts_per_year'])} | {int(r['cap_busiest_month'])} | {_m(r['cap_busiest_month_contracts'])} | "
                 f"{_m(r['cap_busiest_month_fill_any'])} | {_m(r['cap_busiest_month_fill_sensible'])} | "
                 f"{r['cap_fill_share_any']:.0%} / {r['cap_fill_share_sensible']:.0%} | "
                 f"{r['cap_fill_share_payout_any']:.0%} / {r['cap_fill_share_payout_sensible']:.0%} | {nov_txt} |")
    L.append("")
    # Table 10 live
    if live:
        L.append("**Table 10. One real season, 2026: the hedge bought at each month's actual ask at listing and "
                 "settled by Kalshi, vs the 2026 PRF policy.** PRF index sources are listed per interval.\n")
        L.append("| Farm | Kalshi cost (actual asks + fee + capital) | Share of contracts with a quote | Fair value of the legs | "
                 "Kalshi paid | PRF premium farmer pays | PRF indemnity 2026 | PRF index used |")
        L.append("|---|---|---|---|---|---|---|---|")
        for r in live:
            L.append(f"| {r['farm_id']} | {_m(r['kalshi_cost_usd'])} | {r['kalshi_share_priced']:.0%} | "
                     f"{_m(r['kalshi_fair_value_usd'])} | {_m(r['kalshi_payout_usd'])} | {_m(r['prf_producer_premium_usd'])} | "
                     f"{_m(r['prf_indemnity_usd'])} | {r['prf_index_sources']} |")
        L.append("")
    L.append("Checks: NCEI indemnity recomputed from `prf_official_index.csv` matches `prf_scenario_results.csv` "
             f"to within ${checks['ncei']:.2f} per farm-year; hedge payouts from `replication_weights.csv` match "
             f"doc 08's `replication_backtest.csv` to within ${checks['h3']:.2f}.")
    return "\n".join(L)


def write_doc_block(block: str):
    if not DOC.exists():
        print(f"  {DOC} not found; tables printed only")
        print(block)
        return
    txt = DOC.read_text(encoding="utf-8")
    if AUTO_BEGIN not in txt or AUTO_END not in txt:
        print("  AUTO markers missing in doc; tables not written")
        return
    pre, rest = txt.split(AUTO_BEGIN, 1)
    _, post = rest.split(AUTO_END, 1)
    DOC.write_text(pre + AUTO_BEGIN + "\n" + block + "\n" + AUTO_END + post, encoding="utf-8")


# ---------------------------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------------------------

def main(argv=None) -> int:
    t0 = time.time()
    D = load_inputs()
    sites = sorted({f["site"] for f in D["farms"]})
    rain = {s: pr.rain_wide(D["st"], s) for s in sites}
    # calibration fits
    cal = D["cal"]

    def cal_fit(h, kind):
        return pr.logistic_calibration_fit(cal[(cal["horizon_days"] == h) & (cal["price_kind"] == kind)])
    cal_ab = cal_fit(*CAL_MAIN)
    obs = listing_prices(D["mk"], D["cd"], rain)
    curve = markup_curve(obs)
    books = nov_books(D["ob"])
    nov = []
    for (site, k), bids in books.items():
        if site in rain and bids:
            q = pr.leg_probability(rain[site], 11, k, FAIR_WINDOW)
            best = max(p for p, _ in bids)
            nov.append({"site": site, "strike_in": k, "q": q, "no_ask": 1 - best, "markup": 1 - best - q})
    nov = pd.DataFrame(nov)
    results = []
    for farm in D["farms"]:
        r = analyse_farm(farm, D, rain, cal_ab, curve, obs, books)
        results.append(r)
        print(f"  {r['fid']}: fair {r['fair_value']:,.0f}  central {r['costs'][CENTRAL]['cost_usd']:,.0f}  "
              f"checks {r['checks']}")
    fy_all = pd.concat([r["fy"] for r in results], ignore_index=True)
    comp = pd.concat([r["comp"] for r in results], ignore_index=True)
    rows = []
    for r in results:
        fy = r["fy"]

        def mean_between(col, y0, y1):
            return float(fy.loc[(fy["year"] >= y0) & (fy["year"] <= y1), col].mean())
        means = {"ncei_long": mean_between("prf_ncei_usd", *LONG["ncei"]),
                 "ncei_head": mean_between("prf_ncei_usd", *HEADLINE),
                 "cpc_long": mean_between("prf_cpc_as_paid_usd", *LONG["cpc_as_paid"]),
                 "cpc_head": mean_between("prf_cpc_as_paid_usd", *HEADLINE)}
        rows.append(farm_summary(r, means))
    summ = pd.DataFrame(rows)
    fy_all["kalshi_fair_value_usd"] = fy_all["farm_id"].map(summ.set_index("farm_id")["kalshi_fair_value_1991_2025_usd"])
    fy_all["kalshi_cost_central_usd"] = fy_all["farm_id"].map(summ.set_index("farm_id")[f"kalshi_cost_{CENTRAL}_usd"])
    # calibration sensitivity (central spread and fee, different calibration fits)
    cal_rows = []
    for h, kind in (CAL_MAIN,) + CAL_SENS:
        ab = cal_fit(h, kind)
        tot = 0.0
        for r in results:
            lg = r["priced_legs"]
            tot += pr.cost_totals(pr.price_legs(lg, pr.calibrated_no_price(lg["q"], *ab), pr.SPREAD_LOW / 2, True))["cost_usd"]
        cal_rows.append(((h, kind), ab, tot))
    live = [x for x in (live_2026(r, D, obs, rain) for r in results if r["fid"] in LIVE_FARMS) if x]
    # outputs
    fy_all.round(2).to_csv(OUT_FARM_YEAR, index=False)
    summ.to_csv(OUT_SUMMARY, index=False, float_format="%.4f")
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig_year_by_year(fy_all, summ, FIGURES / "a3_year_by_year_2015_2025.png")
    fig_cost_vs_payout(summ, FIGURES / "a3_cost_vs_payout.png")
    fig_load(summ, FIGURES / "a3_cost_per_dollar_of_payout.png")
    fig_market_vs_fair(obs, nov, cal_ab, curve, FIGURES / "a3_market_price_vs_fair.png")
    fig_capacity(summ, FIGURES / "a3_fill_capacity.png")
    checks = {"ncei": max(r["checks"]["ncei_recompute_maxdiff_usd"] for r in results),
              "h3": max(r["checks"]["h3_train_vs_backtest_maxdiff_usd"] for r in results)}
    block = doc_tables(summ, comp, fy_all, curve, obs, nov, cal_rows, live, checks)
    write_doc_block(block)
    # console digest
    print(f"calibration fit {CAL_MAIN}: a={cal_ab[0]:.3f} b={cal_ab[1]:.3f}")
    print(curve.to_string())
    print(comp[comp["hedge"] == "H3 out-of-sample"].groupby(["regime", "window"])[["corr", "recovery", "payout_ratio"]].median())
    cols = ["farm_id", "prf_producer_premium_usd", "prf_mean_ncei_1951_2025_usd", "kalshi_fair_value_1991_2025_usd",
            f"kalshi_cost_{CENTRAL}_usd", "prf_producer_load", "kalshi_load_central", "kalshi_load_min",
            "kalshi_load_max", "cap_fill_share_any", "cap_fill_share_95"]
    print(summ[cols].round(3).to_string())
    for x in live:
        print(x)
    print(f"wrote {OUT_FARM_YEAR.name}, {OUT_SUMMARY.name}, 5 figures in {time.time() - t0:.0f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
