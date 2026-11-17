"""How viable are exotic rain payouts as farm insurance on Kalshi? (doc 28)

Run from the repo root (no network):

    python scripts/run_exotic_payouts.py            # full study (about 3-5 minutes)
    python scripts/run_exotic_payouts.py --quick    # two sites, no farm block

Every candidate contract is settled on the same NWS daily climate report Kalshi uses for its
monthly rain markets (daily and monthly station totals in data/processed). "Enough volume" is
assumed throughout: no order-book limits, every leg filled at fair value plus half a 4.5-cent
spread plus the taker fee.

Targets
    PRF payout per $1 of protection at 90% coverage on the NCEI grid index (the data PRF settles
    on from 2026-08-31), for 7 PRF sites x 2 grids (station, farm) x 11 two-month intervals.
    A mirror-image "excess rain" payout, max(0, (index - 120) / 100), for the wet side.
    The 11 representative farms' PRF payouts and forage-loss proxy (prf_scenario_results.csv).
    An Illinois corn revenue-loss curve (doc 03a rain-only regression) on Chicago rain.

Contract families (built in agri_hedge.exotics; fit by NNLS with doc 08's ridge penalties)
    drought side: today's whole-inch monthly NO ladder; third-inch monthly ladder; two-month-total
    ladders (whole and third inch); worst-month lookback; AND/OR joint digitals; dry-spell
    barriers; wet-day counts; combinations.
    wet side: monthly YES ladders; two-month-total YES ladder; one-day maximum digitals.
    farm level: season totals, worst interval, count of dry months, per-interval dry spells.

Outputs
    data/processed/exotic_interval_results.csv   one row per case x family x eval set
    data/processed/exotic_family_summary.csv     pooled by family
    data/processed/exotic_farm_results.csv       farm-level block
    data/processed/exotic_corn_results.csv, exotic_basket_results.csv, exotic_event_prices.csv
    docs/figures/x2_*.png
    tables between the AUTO markers of docs/analysis/28_exotic_payouts_viability.md
"""
from __future__ import annotations

import argparse
import re
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import yaml  # noqa: E402

from agri_hedge import exotics as ex  # noqa: E402
from agri_hedge.config import DOCS, FIGURES, PROCESSED, SCENARIOS  # noqa: E402
from agri_hedge.locations import ALL_SITES  # noqa: E402
from agri_hedge.prf_intervals import INTERVAL_MONTHS, INTERVAL_NAMES  # noqa: E402
from agri_hedge.replicate import (fit_ladder, loyo_predictions, pooled_he, prf_payout,  # noqa: E402
                                  replication_metrics)

DOC = DOCS / "analysis" / "28_exotic_payouts_viability.md"
FIRST_YEAR, LAST_YEAR = 1951, 2025
YEARS = np.arange(FIRST_YEAR, LAST_YEAR + 1)
COVERAGE = 0.90
WET_TRIGGER = 120.0
PRF_SITES = ["DFW", "SAT", "OKC", "SGF", "DEN", "ABQ", "TPA"]
ALL_STUDY = PRF_SITES + ["ORD"]
RIDGE_FINE, RIDGE_COARSE = 0.1, 0.03
LADDER_TOP = 7.0
HALF_SPREAD = 0.0225
CORN_PRICE = 4.70
C_BLUE, C_ORANGE, C_AQUA, C_YELLOW, C_MAGENTA = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"
C_TEXT, C_TEXT2, C_GRID = "#0b0b0b", "#52514e", "#e6e5e2"
SEQ_BLUES = ["#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7", "#3987e5", "#2a78d6",
             "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b"]

#: (family key, label, side, ridge). Order is the order in tables and figures.
DROUGHT_FAMILIES = [
    ("D0_ideal", "Ideal: PRF formula on the station's two-month index (scaled)", "reference", 0.0),
    ("D1_today", "Today: monthly NO ladder, whole-inch strikes", "buildable today", RIDGE_COARSE),
    ("D2_third", "Monthly NO ladder, third-inch strikes", "new strikes", RIDGE_FINE),
    ("D3_sum_whole", "Two-month total, whole-inch strikes", "new contract", RIDGE_COARSE),
    ("D4_sum_third", "Two-month total, third-inch strikes", "new contract", RIDGE_FINE),
    ("D5_worst_third", "Worst month of the two (lookback), third-inch strikes", "new contract", RIDGE_FINE),
    ("D6_andor", "Both-months-dry AND / either-month-dry OR digitals", "new contract", RIDGE_COARSE),
    ("D7_dryspell", "Longest dry spell >= D days (barrier)", "new contract", RIDGE_COARSE),
    ("D8_wetdays", "Wet days (>= 0.10 in) <= N", "new contract", RIDGE_COARSE),
    ("D9_today_path", "Today's ladder + dry spell + wet days", "new contract", RIDGE_COARSE),
    ("D10_exotic_mix", "Two-month total + worst month + AND/OR (third-inch)", "new contract", RIDGE_FINE),
]
WET_FAMILIES = [
    ("W1_today", "Today: monthly YES ladder, whole-inch strikes", "buildable today", RIDGE_COARSE),
    ("W2_third", "Monthly YES ladder, third-inch strikes", "new strikes", RIDGE_FINE),
    ("W3_sum_whole", "Two-month total YES, whole-inch strikes", "new contract", RIDGE_COARSE),
    ("W4_maxday", "One-day maximum >= X in (flood digital)", "new contract", RIDGE_COARSE),
    ("W5_today_maxday", "Today's YES ladder + one-day maximum", "new contract", RIDGE_COARSE),
    ("W6_sum_maxday", "Two-month total YES + one-day maximum", "new contract", RIDGE_COARSE),
]
FAMILY_LABEL = {k: lab for k, lab, _, _ in DROUGHT_FAMILIES + WET_FAMILIES}
FAMILY_SIDE = {k: side for k, _, side, _ in DROUGHT_FAMILIES + WET_FAMILIES}


def log(*a):
    print(*a, flush=True)


# ---------------------------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------------------------

def load_monthly(keys) -> dict[str, pd.DataFrame]:
    st = pd.read_csv(PROCESSED / "station_monthly_precip.csv")
    st = st[st["station_key"].isin(keys)].copy()
    st.loc[st["n_missing"].fillna(1) != 0, "precip_in"] = np.nan
    out = {}
    for key, g in st.groupby("station_key"):
        w = g.pivot_table(index="year", columns="month", values="precip_in", aggfunc="first")
        out[key] = w.reindex(index=YEARS, columns=range(1, 13))
    return out


def load_daily() -> dict[str, pd.DataFrame]:
    d = pd.read_parquet(PROCESSED / "station_daily_precip_study.parquet", columns=["station_key", "date", "precip_in"])
    d["date"] = pd.to_datetime(d["date"])
    d = d[d["date"].dt.year.between(FIRST_YEAR, LAST_YEAR)]
    return {k: g.sort_values("date").reset_index(drop=True) for k, g in d.groupby("station_key")}


def load_index(grids) -> pd.DataFrame:
    off = pd.read_csv(PROCESSED / "prf_official_index.csv")
    off = off[off["grid_id"].isin(grids) & off["year"].between(FIRST_YEAR, LAST_YEAR)]
    return off.pivot_table(index=["grid_id", "interval_name"], columns="year", values="index_value").reindex(columns=YEARS)


def load_grids() -> pd.DataFrame:
    return pd.read_csv(PROCESSED / "study_grids.csv")


def load_farms() -> list[dict]:
    with open(SCENARIOS / "farms.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)["farms"]


def daily_stats_cache(daily: dict[str, pd.DataFrame]) -> dict[tuple[str, tuple[int, ...]], pd.DataFrame]:
    """Path statistics for every site and every two-month interval (and single months)."""
    cache = {}
    for site, d in daily.items():
        for name in INTERVAL_NAMES:
            months = INTERVAL_MONTHS[name]
            cache[(site, months)] = ex.interval_daily_stats(d, months).reindex(YEARS)
        for m in range(1, 13):
            cache[(site, (m,))] = ex.interval_daily_stats(d, (m,)).reindex(YEARS)
    return cache


# ---------------------------------------------------------------------------------------------
# Fitting one case
# ---------------------------------------------------------------------------------------------

def fit_family(X: np.ndarray, y: np.ndarray, ridge: float, index: np.ndarray | None, label: str) -> list[dict]:
    """In-sample (full fit) and LOYO metrics plus pricing for one design matrix."""
    ok = ~np.isnan(y) & ~np.isnan(X).any(axis=1) if X.shape[1] else ~np.isnan(y)
    rows = []
    if ok.sum() < 20 or X.shape[1] == 0:
        return rows
    f = fit_ladder(X[ok], y[ok], ridge=ridge)
    pred_in = f.predict(X[ok])
    m_in = replication_metrics(y[ok], pred_in, None if index is None else index[ok])
    price = ex.hedge_pricing(f.weights, X[ok], half_spread=HALF_SPREAD)
    pred_lo = loyo_predictions(X, y, ridge=ridge)
    m_lo = replication_metrics(y[ok], pred_lo[ok], None if index is None else index[ok])
    for eval_set, m in (("in_sample", m_in), ("loyo", m_lo)):
        rows.append({"family": label, "eval_set": eval_set, **m, **{k: v for k, v in price.items()}})
    return rows


def drought_designs(r1, r2, listed: tuple[float, ...], stats: pd.DataFrame | None) -> dict[str, tuple[np.ndarray, float]]:
    """{family: (X, ridge)} for the drought side of one interval."""
    rain = {1: r1, 2: r2}
    top = max(listed)
    today = {}
    for mon, r in rain.items():
        for k in listed:
            today[f"NO m{mon} <= {k:.2f}"] = ex.no_payoff(r, k)
    third = ex.monthly_no_ladder(rain, ex.THIRD_IN, max_strike=top)
    total = ex.two_month_total(r1, r2)
    sum_whole = ex.sum_no_ladder(total, 1.0)
    sum_third = ex.sum_no_ladder(total, ex.THIRD_IN)
    worst = ex.worst_month_ladder(r1, r2, ex.THIRD_IN)
    andor = ex.and_or_ladder(r1, r2)
    out = {
        "D1_today": today, "D2_third": third, "D3_sum_whole": sum_whole, "D4_sum_third": sum_third,
        "D5_worst_third": worst, "D6_andor": andor,
        "D10_exotic_mix": {**sum_third, **worst, **andor},
    }
    if stats is not None:
        dry = ex.dry_spell_ladder(stats["dry_spell_days"].to_numpy())
        wet = ex.wet_day_ladder(stats["wet_days"].to_numpy())
        out["D7_dryspell"] = dry
        out["D8_wetdays"] = wet
        out["D9_today_path"] = {**today, **dry, **wet}
    designs = {}
    ridge = {k: r for k, _, _, r in DROUGHT_FAMILIES}
    for fam, cols in out.items():
        X, _ = ex.design_from_columns(cols)
        designs[fam] = (X, ridge[fam])
    return designs


def wet_designs(r1, r2, listed: tuple[float, ...], stats: pd.DataFrame | None) -> dict[str, tuple[np.ndarray, float]]:
    rain = {1: r1, 2: r2}
    top = max(listed)
    today = {}
    for mon, r in rain.items():
        for k in listed:
            today[f"YES m{mon} > {k:.2f}"] = ex.yes_payoff(r, k)
    third = ex.monthly_yes_ladder(rain, ex.THIRD_IN, max_strike=top)
    total = ex.two_month_total(r1, r2)
    sum_whole = ex.sum_yes_ladder(total, 1.0)
    out = {"W1_today": today, "W2_third": third, "W3_sum_whole": sum_whole}
    if stats is not None:
        mx = ex.max_day_ladder(stats["max_1day_in"].to_numpy())
        out["W4_maxday"] = mx
        out["W5_today_maxday"] = {**today, **mx}
        out["W6_sum_maxday"] = {**sum_whole, **mx}
    ridge = {k: r for k, _, _, r in WET_FAMILIES}
    designs = {}
    for fam, cols in out.items():
        X, _ = ex.design_from_columns(cols)
        designs[fam] = (X, ridge[fam])
    return designs


def wet_payout(index) -> np.ndarray:
    i = np.asarray(index, dtype=float)
    return np.where(np.isnan(i), np.nan, np.clip((i - WET_TRIGGER) / 100.0, 0.0, None))


def listed_strikes_for(series: str, markets: pd.DataFrame) -> tuple[float, ...]:
    m = markets[(markets["series_ticker"] == series)]
    ks = sorted({float(k) for k in m["floor_strike"].dropna() if float(k) == int(float(k))})
    ks = [k for k in ks if k <= LADDER_TOP] or [float(k) for k in range(1, 8)]
    return tuple(ks)


# ---------------------------------------------------------------------------------------------
# Interval study
# ---------------------------------------------------------------------------------------------

def interval_study(sites, monthly, dstats, idx, grids, markets) -> pd.DataFrame:
    rows = []
    t0 = time.time()
    for site in sites:
        series = ALL_SITES[site]["kalshi_series"]
        listed = listed_strikes_for(series, markets)
        rain = monthly[site]
        for name in INTERVAL_NAMES:
            m1, m2 = INTERVAL_MONTHS[name]
            r1 = rain[m1].to_numpy(float)
            r2 = rain[m2].to_numpy(float)
            stats = dstats.get((site, (m1, m2)))
            normal = np.nanmean(r1 + r2)
            st_idx = 100.0 * (r1 + r2) / normal
            d_des = drought_designs(r1, r2, listed, stats)
            w_des = wet_designs(r1, r2, listed, stats)
            d_des["D0_ideal"] = (prf_payout(st_idx, COVERAGE).reshape(-1, 1), 0.0)
            for _, g in grids[grids["site"] == site].iterrows():
                gi = idx.loc[(g["grid_id"], name)].to_numpy(float)
                y_d = prf_payout(gi, COVERAGE)
                y_w = wet_payout(gi)
                for fam, (X, ridge) in d_des.items():
                    for r in fit_family(X, y_d, ridge, gi, fam):
                        rows.append({"side": "drought", "site": site, "role": g["role"], "grid_id": g["grid_id"],
                                     "interval_name": name, "distance_mi": g["distance_to_station_mi"], **r})
                for fam, (X, ridge) in w_des.items():
                    for r in fit_family(X, y_w, ridge, None, fam):
                        rows.append({"side": "wet", "site": site, "role": g["role"], "grid_id": g["grid_id"],
                                     "interval_name": name, "distance_mi": g["distance_to_station_mi"], **r})
        log(f"  {site}: done ({time.time() - t0:.0f}s)")
    return pd.DataFrame(rows)


def summarize_families(res: pd.DataFrame) -> pd.DataFrame:
    rows = []
    prf = res[res["site"].isin(PRF_SITES)]
    for (side, fam, role, ev), g in prf.groupby(["side", "family", "role", "eval_set"]):
        rows.append({"side": side, "family": fam, "label": FAMILY_LABEL[fam], "status": FAMILY_SIDE[fam],
                     "role": role, "eval_set": ev, "n_cases": len(g), "he_pooled": pooled_he(g),
                     "he_median": g["he"].median(), "corr": g["corr"].mean(), "rmse": g["rmse"].mean(),
                     "tail_capture": g["tail_capture"].mean(), "miss_rate": g["miss_rate"].mean(),
                     "false_alarm_rate": g["false_alarm_rate"].mean(), "bias": g["bias"].mean(),
                     "fair_cost": g["fair_cost"].mean(), "contracts": g["contracts"].mean(),
                     "load": g["load"].mean(), "thin_share": g["thin_share"].mean(), "n_legs": g["n_legs"].mean(),
                     "mean_target": g["mean_prf"].mean()})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------------------------
# Farm block
# ---------------------------------------------------------------------------------------------

def farm_study(farms, monthly, dstats, idx, grids, markets, scen: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for farm in farms:
        fid, site = farm["farm_id"], farm["site"]
        cov = float(farm["coverage_level"])
        alloc = {k: float(v) for k, v in farm["interval_allocation"].items()}
        grid = int(grids[(grids["site"] == site) & (grids["role"] == "farm")]["grid_id"].iloc[0])
        y_prf = np.zeros(len(YEARS))
        for name, share in alloc.items():
            y_prf += share * prf_payout(idx.loc[(grid, name)].to_numpy(float), cov)
        s = scen[scen["farm_id"] == fid].set_index("year").reindex(YEARS)
        protection = float(s["policy_protection_usd"].dropna().iloc[0])
        y_loss = (s["forage_loss_usd"] / protection).to_numpy(float)
        # consistency check with the scenario file's own indemnity
        chk = (s["indemnity_usd"] / protection).to_numpy(float)
        okc = ~np.isnan(chk) & ~np.isnan(y_prf)
        if okc.any() and np.nanmax(np.abs(chk[okc] - y_prf[okc])) > 0.01:
            log(f"  warning: {fid} payout differs from prf_scenario_results by up to {np.nanmax(np.abs(chk[okc] - y_prf[okc])):.3f}")
        listed = listed_strikes_for(ALL_SITES[site]["kalshi_series"], markets)
        rain = monthly[site]
        months = sorted({m for name in alloc for m in INTERVAL_MONTHS[name]})
        rain_m = {m: rain[m].to_numpy(float) for m in months}
        today, third, sums, dry = {}, {}, {}, {}
        for m, r in rain_m.items():
            for k in listed:
                today[f"NO m{m} <= {k:.2f}"] = ex.no_payoff(r, k)
        third = ex.monthly_no_ladder(rain_m, ex.THIRD_IN, max_strike=LADDER_TOP)
        interval_totals = {}
        for name in alloc:
            m1, m2 = INTERVAL_MONTHS[name]
            tot = ex.two_month_total(rain_m[m1], rain_m[m2])
            interval_totals[name] = tot
            sums.update(ex.sum_no_ladder(tot, ex.THIRD_IN, label=name))
            st = dstats.get((site, (m1, m2)))
            if st is not None:
                for lab, col in ex.dry_spell_ladder(st["dry_spell_days"].to_numpy()).items():
                    dry[f"{name} {lab}"] = col
        season = np.sum([rain_m[m] for m in months], axis=0)
        season_ladder = ex.sum_no_ladder(season, ex.THIRD_IN, label="season")
        worst = np.min(np.column_stack([interval_totals[n] / np.nanmean(interval_totals[n]) for n in alloc]), axis=1)
        worst_ladder = {f"NO worst-interval index <= {q:.2f}": ex.digital_le(worst, q) for q in (0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)}
        dry_count = np.zeros(len(YEARS))
        for m, r in rain_m.items():
            k = ex.quantile_strikes(r, [0.4])[0]
            dry_count += ex.no_payoff(r, k)
        count_ladder = {f"COUNT dry months >= {j}": ex.digital_ge(dry_count, j) for j in range(1, len(months) + 1)}
        fams = {
            "F1_today": (today, RIDGE_COARSE),
            "F2_third": (third, RIDGE_FINE),
            "F3_interval_sums_third": (sums, RIDGE_FINE),
            "F4_season_total_third": (season_ladder, RIDGE_FINE),
            "F5_worst_interval": (worst_ladder, RIDGE_COARSE),
            "F6_dry_month_count": (count_ladder, RIDGE_COARSE),
            "F7_dry_spells": (dry, RIDGE_COARSE),
            "F8_exotic_mix": ({**sums, **worst_ladder, **count_ladder, **dry}, RIDGE_FINE),
            "F9_today_plus_exotics": ({**today, **sums, **worst_ladder, **count_ladder, **dry}, RIDGE_FINE),
        }
        for fam, (cols, ridge) in fams.items():
            X, _ = ex.design_from_columns(cols)
            for tname, y in (("prf_payout", y_prf), ("forage_loss", y_loss)):
                for r in fit_family(X, y, ridge, None, fam):
                    rows.append({"farm_id": fid, "site": site, "target": tname, "protection_usd": protection,
                                 "coverage": cov, **r})
        log(f"  farm {fid} done")
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------------------------
# Corn collar at Chicago
# ---------------------------------------------------------------------------------------------

def corn_study(monthly, dstats, listed) -> pd.DataFrame:
    coef = pd.read_csv(PROCESSED / "crop_yield_aux" / "r1_reestimate_coefficients.csv")
    c = coef[(coef["crop"] == "corn") & (coef["state"] == "IL") & (coef["spec"] == "rain-only 1980-2025")]
    b = dict(zip(c["term"], c["coef"]))
    rain = monthly["ORD"]
    r = {m: rain[m].to_numpy(float) for m in (5, 6, 7, 8)}
    n = {m: np.nanmean(v) for m, v in r.items()}
    d_yield = (b["may"] * (r[5] - n[5]) + b["jun"] * (r[6] - n[6]) + b["jun2"] * (r[6] ** 2 - n[6] ** 2)
               + b["jul"] * (r[7] - n[7]) + b["jul2"] * (r[7] ** 2 - n[7] ** 2)
               + b["aug"] * (r[8] - n[8]) + b["aug2"] * (r[8] ** 2 - n[8] ** 2))
    loss = np.clip(-d_yield * CORN_PRICE, 0, None)          # $ per acre below a normal year
    loss_per_dollar = loss / 100.0                          # per $100 of protection per acre
    rows = []
    rm = {m: r[m] for m in (6, 7, 8)}
    no_whole = {f"NO m{m} <= {k:.2f}": ex.no_payoff(v, k) for m, v in rm.items() for k in listed}
    yes_whole = {f"YES m{m} > {k:.2f}": ex.yes_payoff(v, k) for m, v in rm.items() for k in listed}
    no_third = ex.monthly_no_ladder(rm, ex.THIRD_IN, max_strike=LADDER_TOP)
    yes_third = ex.monthly_yes_ladder(rm, ex.THIRD_IN, max_strike=LADDER_TOP)
    path = {}
    for m in (6, 7, 8):
        st = dstats.get(("ORD", (m,)))
        if st is not None:
            path.update({f"m{m} {k}": v for k, v in ex.dry_spell_ladder(st["dry_spell_days"].to_numpy(), (7, 10, 14, 21)).items()})
            path.update({f"m{m} {k}": v for k, v in ex.max_day_ladder(st["max_1day_in"].to_numpy(), (1.5, 2.0, 3.0)).items()})
    fams = {
        "C1_drought_only_whole": (no_whole, RIDGE_COARSE),
        "C2_two_sided_whole": ({**no_whole, **yes_whole}, RIDGE_COARSE),
        "C3_two_sided_third": ({**no_third, **yes_third}, RIDGE_FINE),
        "C4_two_sided_whole_plus_path": ({**no_whole, **yes_whole, **path}, RIDGE_COARSE),
        "C5_two_sided_third_plus_path": ({**no_third, **yes_third, **path}, RIDGE_FINE),
    }
    for fam, (cols, ridge) in fams.items():
        X, _ = ex.design_from_columns(cols)
        for rr in fit_family(X, loss_per_dollar, ridge, None, fam):
            rows.append({"crop": "IL corn on ORD rain", **rr})
    out = pd.DataFrame(rows)
    out["mean_loss_usd_per_acre"] = float(np.nanmean(loss))
    out["share_years_loss_gt_20"] = float(np.nanmean(loss > 20))
    peak_jul = -b["jul"] / (2 * b["jul2"])
    out["july_peak_in"] = peak_jul
    out["july_normal_in"] = n[7]
    out["share_wet_side_loss"] = float(np.nansum(loss[(r[7] > peak_jul)]) / np.nansum(loss))
    return out


# ---------------------------------------------------------------------------------------------
# Two-station basket
# ---------------------------------------------------------------------------------------------

def basket_study(monthly, idx, grids) -> pd.DataFrame:
    pairs = {"SAT": ("SAT", "AUS"), "ORD": ("ORD", "MDW")}
    rows = []
    for site, (a, b) in pairs.items():
        grid = int(grids[(grids["site"] == site) & (grids["role"] == "farm")]["grid_id"].iloc[0])
        for name in INTERVAL_NAMES:
            m1, m2 = INTERVAL_MONTHS[name]
            ta = monthly[a][m1].to_numpy(float) + monthly[a][m2].to_numpy(float)
            tb = monthly[b][m1].to_numpy(float) + monthly[b][m2].to_numpy(float)
            y = prf_payout(idx.loc[(grid, name)].to_numpy(float), COVERAGE)
            variants = {f"{a} alone": ta / np.nanmean(ta), f"{b} alone": tb / np.nanmean(tb),
                        f"average of {a} and {b}": 0.5 * (ta / np.nanmean(ta) + tb / np.nanmean(tb)),
                        f"drier of {a} and {b}": np.minimum(ta / np.nanmean(ta), tb / np.nanmean(tb))}
            for lab, rel in variants.items():
                X = prf_payout(100 * rel, COVERAGE).reshape(-1, 1)
                for r in fit_family(X, y, 0.0, None, lab):
                    rows.append({"site": site, "farm_grid": grid, "interval_name": name, **r})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------------------------
# Event prices for the doc
# ---------------------------------------------------------------------------------------------

def event_prices(sites, dstats) -> pd.DataFrame:
    rows = []
    for site in sites:
        for name in INTERVAL_NAMES:
            st = dstats.get((site, INTERVAL_MONTHS[name]))
            if st is None:
                continue
            ok = st["complete"].fillna(False).astype(bool)
            s = st[ok]
            rows.append({"site": site, "interval_name": name, "n_years": int(len(s)),
                         "p_dryspell_ge_14": float((s["dry_spell_days"] >= 14).mean()),
                         "p_dryspell_ge_21": float((s["dry_spell_days"] >= 21).mean()),
                         "p_dryspell_ge_28": float((s["dry_spell_days"] >= 28).mean()),
                         "p_wetdays_le_6": float((s["wet_days"] <= 6).mean()),
                         "p_wetdays_le_10": float((s["wet_days"] <= 10).mean()),
                         "p_maxday_ge_2": float((s["max_1day_in"] >= 2.0).mean()),
                         "p_maxday_ge_3": float((s["max_1day_in"] >= 3.0).mean()),
                         "median_dry_spell": float(s["dry_spell_days"].median()),
                         "median_wet_days": float(s["wet_days"].median())})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------------------------
# Tables and figures
# ---------------------------------------------------------------------------------------------

def md_table(df: pd.DataFrame, cols, headers=None, fmt=None) -> str:
    headers = headers or cols
    fmt = fmt or {}
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            f = fmt.get(c)
            if f is not None:
                cells.append(f(v))
            elif isinstance(v, (float, np.floating)):
                cells.append("" if np.isnan(v) else f"{v:.2f}")
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def replace_between_markers(path: Path, begin: str, end: str, text: str, fallback: Path) -> None:
    block = f"{begin}\n{text}\n{end}"
    if path.exists():
        doc = path.read_text(encoding="utf-8")
        pat = re.compile(re.escape(begin) + r".*?" + re.escape(end), re.S)
        if pat.search(doc):
            path.write_text(pat.sub(lambda _m: block, doc), encoding="utf-8")
            log(f"updated tables in {path}")
            return
    fallback.write_text(block, encoding="utf-8")
    log(f"wrote tables to {fallback}")


def build_tables(summ, res, farm, corn, basket, events) -> str:
    f2 = lambda v: "" if pd.isna(v) else f"{v:.2f}"  # noqa: E731
    f3 = lambda v: "" if pd.isna(v) else f"{v:.3f}"  # noqa: E731
    pct = lambda v: "" if pd.isna(v) else f"{100 * v:.0f}%"  # noqa: E731
    parts = ["Generated by `scripts/run_exotic_payouts.py`. HE = hedge effectiveness, the share of the target's "
             "year-to-year payout variance the hedge removes; pooled over cases. LOYO = leave-one-year-out "
             "(out of sample), 1951-2025. Fair cost = expected payout per $1 of protection. Load = all-in cost "
             "(fair + half a 4.5c spread + taker fee) per $1 of expected payout. Thin = share of the fair cost on "
             "legs that paid in fewer than 5 of 75 years (their price rests on almost no history).\n"]

    # Table A: drought families, farm grid and station grid, LOYO
    for role in ("farm", "station"):
        s = summ[(summ["side"] == "drought") & (summ["role"] == role)]
        lo = s[s["eval_set"] == "loyo"].set_index("family")
        ins = s[s["eval_set"] == "in_sample"].set_index("family")
        t = lo.copy()
        t["he_in"] = ins["he_pooled"]
        t = t.reindex([k for k, *_ in DROUGHT_FAMILIES if k in t.index]).reset_index()
        parts.append(f"**Table A-{role}. Drought-side families against PRF payouts at the {role} grid "
                     f"(7 PRF sites x 11 intervals = 77 cases, 90% coverage, NCEI index).**")
        parts.append(md_table(t, ["label", "status", "he_pooled", "he_in", "he_median", "tail_capture", "false_alarm_rate",
                                  "fair_cost", "contracts", "load", "thin_share", "n_legs"],
                              ["Family", "Status", "HE LOYO", "HE in-sample", "Median HE", "Tail capture", "False alarms",
                               "Fair cost ($/$)", "Contracts per $", "Load", "Thin", "Legs"],
                              {"he_pooled": f2, "he_in": f2, "he_median": f2, "tail_capture": f2, "false_alarm_rate": f2,
                               "fair_cost": f3, "contracts": f2, "load": f2, "thin_share": pct, "n_legs": lambda v: f"{v:.1f}"}))
        parts.append("")

    # Table B: by site at the farm grid, LOYO HE pooled over intervals
    d = res[(res["side"] == "drought") & (res["role"] == "farm") & (res["eval_set"] == "loyo")]
    fam_order = [k for k, *_ in DROUGHT_FAMILIES]
    rows = []
    for site in ALL_STUDY:
        g = d[d["site"] == site]
        if g.empty:
            continue
        row = {"site": site if site != "ORD" else "ORD (row crop, contrast)"}
        for fam in fam_order:
            row[fam] = pooled_he(g[g["family"] == fam])
        rows.append(row)
    tb = pd.DataFrame(rows)
    short = {"D0_ideal": "Ideal", "D1_today": "Today", "D2_third": "Third-inch", "D3_sum_whole": "2-mo whole",
             "D4_sum_third": "2-mo third", "D5_worst_third": "Worst month", "D6_andor": "AND/OR", "D7_dryspell": "Dry spell",
             "D8_wetdays": "Wet days", "D9_today_path": "Today+path", "D10_exotic_mix": "Exotic mix"}
    parts.append("**Table B. Pooled LOYO HE by site at the farm grid (11 intervals each).**")
    parts.append(md_table(tb, ["site"] + fam_order, ["Site"] + [short[f] for f in fam_order], {f: f2 for f in fam_order}))
    parts.append("")

    # Table C: by interval, farm grid, selected families
    rows = []
    for name in INTERVAL_NAMES:
        g = d[(d["interval_name"] == name) & d["site"].isin(PRF_SITES)]
        row = {"interval": name}
        for fam in ("D1_today", "D2_third", "D4_sum_third", "D5_worst_third", "D7_dryspell", "D9_today_path", "D10_exotic_mix"):
            row[fam] = pooled_he(g[g["family"] == fam])
        rows.append(row)
    tc = pd.DataFrame(rows)
    cols = ["D1_today", "D2_third", "D4_sum_third", "D5_worst_third", "D7_dryspell", "D9_today_path", "D10_exotic_mix"]
    parts.append("**Table C. Pooled LOYO HE by interval at the farm grid (7 PRF sites).**")
    parts.append(md_table(tc, ["interval"] + cols, ["Interval"] + [short[f] for f in cols], {f: f2 for f in cols}))
    parts.append("")

    # Table D: wet side
    for role in ("farm", "station"):
        s = summ[(summ["side"] == "wet") & (summ["role"] == role)]
        lo = s[s["eval_set"] == "loyo"].set_index("family")
        ins = s[s["eval_set"] == "in_sample"].set_index("family")
        t = lo.copy()
        t["he_in"] = ins["he_pooled"]
        t = t.reindex([k for k, *_ in WET_FAMILIES if k in t.index]).reset_index()
        parts.append(f"**Table D-{role}. Excess-rain families against a wet payout max(0, (index - 120) / 100) at the {role} grid.**")
        parts.append(md_table(t, ["label", "status", "he_pooled", "he_in", "he_median", "fair_cost", "load", "thin_share", "n_legs"],
                              ["Family", "Status", "HE LOYO", "HE in-sample", "Median HE", "Fair cost ($/$)", "Load", "Thin", "Legs"],
                              {"he_pooled": f2, "he_in": f2, "he_median": f2, "fair_cost": f3, "load": f2, "thin_share": pct,
                               "n_legs": lambda v: f"{v:.1f}"}))
        parts.append("")

    # Table E: farm block
    if farm is not None and not farm.empty:
        flabel = {"F1_today": "Today: monthly whole-inch NO on insured months", "F2_third": "Monthly third-inch NO",
                  "F3_interval_sums_third": "Two-month totals of insured intervals (third-inch)",
                  "F4_season_total_third": "Whole-season total (third-inch)",
                  "F5_worst_interval": "Worst insured interval (lookback on interval index)",
                  "F6_dry_month_count": "Count of dry insured months", "F7_dry_spells": "Dry spells in each insured interval",
                  "F8_exotic_mix": "All exotics together", "F9_today_plus_exotics": "Today's ladder + all exotics"}
        for tname, tdesc in (("prf_payout", "the farm's PRF payout"), ("forage_loss", "the farm's forage-loss proxy (doc 04b)")):
            g = farm[(farm["target"] == tname) & (farm["eval_set"] == "loyo")]
            rows = []
            for fam, lab in flabel.items():
                h = g[g["family"] == fam]
                if h.empty:
                    continue
                gi = farm[(farm["target"] == tname) & (farm["eval_set"] == "in_sample") & (farm["family"] == fam)]
                rows.append({"label": lab, "he_pooled": pooled_he(h), "he_in": pooled_he(gi), "he_median": h["he"].median(),
                             "he_min": h["he"].min(), "he_max": h["he"].max(), "n_ge_05": int((h["he"] >= 0.5).sum()),
                             "fair_cost": h["fair_cost"].mean(), "load": h["load"].mean(), "thin": h["thin_share"].mean(),
                             "legs": h["n_legs"].mean()})
            parts.append(f"**Table E-{tname}. Farm-level families against {tdesc}, 11 farms, LOYO 1951-2025.** "
                         "Fair cost per $1 of policy protection.")
            parts.append(md_table(pd.DataFrame(rows), ["label", "he_pooled", "he_in", "he_median", "he_min", "he_max", "n_ge_05",
                                                        "fair_cost", "load", "thin", "legs"],
                                  ["Family", "HE LOYO (pooled)", "HE in-sample", "Median farm HE", "Worst farm", "Best farm",
                                   "Farms >= 0.5", "Fair cost ($/$)", "Load", "Thin", "Legs"],
                                  {"he_pooled": f2, "he_in": f2, "he_median": f2, "he_min": f2, "he_max": f2,
                                   "fair_cost": f3, "load": f2, "thin": pct, "legs": lambda v: f"{v:.1f}", "n_ge_05": lambda v: f"{int(v)} of 11"}))
            parts.append("")
        # per farm, PRF target
        g = farm[(farm["target"] == "prf_payout") & (farm["eval_set"] == "loyo")]
        piv = g.pivot_table(index="farm_id", columns="family", values="he").reset_index()
        fcols = [c for c in flabel if c in piv.columns]
        fshort = {"F1_today": "Today", "F2_third": "Third-inch", "F3_interval_sums_third": "Interval totals",
                  "F4_season_total_third": "Season total", "F5_worst_interval": "Worst interval", "F6_dry_month_count": "Dry-month count",
                  "F7_dry_spells": "Dry spells", "F8_exotic_mix": "Exotic mix", "F9_today_plus_exotics": "Today+exotics"}
        parts.append("**Table F. Each farm: LOYO HE against its PRF payout by family.**")
        parts.append(md_table(piv, ["farm_id"] + fcols, ["Farm"] + [fshort[c] for c in fcols], {c: f2 for c in fcols}))
        parts.append("")

    # Table G: corn
    if corn is not None and not corn.empty:
        clabel = {"C1_drought_only_whole": "Drought side only: monthly NO, whole-inch (Jun-Aug)",
                  "C2_two_sided_whole": "Collar: monthly NO + YES, whole-inch",
                  "C3_two_sided_third": "Collar: monthly NO + YES, third-inch",
                  "C4_two_sided_whole_plus_path": "Collar whole-inch + dry spells + one-day maxima",
                  "C5_two_sided_third_plus_path": "Collar third-inch + dry spells + one-day maxima"}
        lo = corn[corn["eval_set"] == "loyo"].set_index("family")
        ins = corn[corn["eval_set"] == "in_sample"].set_index("family")
        t = lo.copy()
        t["he_in"] = ins["he_pooled"] if "he_pooled" in ins.columns else ins["he"]
        t["label"] = [clabel[k] for k in t.index]
        parts.append("**Table G. Illinois corn revenue loss (doc 03a rain-only regression applied to Chicago O'Hare rain, "
                     "Jun-Aug quadratic), hedged with contracts on the same station's rain.** Because target and hedge use "
                     "the same gauge, HE here measures payoff-shape fit only, with no geography. Loss per $100 of value per acre; "
                     f"mean loss ${corn['mean_loss_usd_per_acre'].iloc[0]:.0f}/acre, "
                     f"{100 * corn['share_wet_side_loss'].iloc[0]:.0f}% of loss dollars come from Julys wetter than the yield peak "
                     f"({corn['july_peak_in'].iloc[0]:.1f} in; normal {corn['july_normal_in'].iloc[0]:.1f} in).")
        parts.append(md_table(t.reset_index(), ["label", "he", "he_in", "corr", "fair_cost", "load", "thin_share", "n_legs"],
                              ["Family", "HE LOYO", "HE in-sample", "Corr", "Fair cost ($/$)", "Load", "Thin", "Legs"],
                              {"he": f2, "he_in": f2, "corr": f2, "fair_cost": f3, "load": f2, "thin_share": pct, "n_legs": lambda v: f"{v:.1f}"}))
        parts.append("")

    # Table H: basket
    if basket is not None and not basket.empty:
        g = basket[basket["eval_set"] == "loyo"]
        rows = []
        for (site, fam), h in g.groupby(["site", "family"], sort=False):
            rows.append({"site": site, "family": fam, "he_pooled": pooled_he(h), "he_median": h["he"].median(),
                         "corr": h["corr"].mean()})
        parts.append("**Table H. Two-station baskets: ideal two-month index put on one station, the other, their average, "
                     "or the drier of the two, against the farm grid's PRF payout (11 intervals, LOYO scale fit).**")
        parts.append(md_table(pd.DataFrame(rows), ["site", "family", "he_pooled", "he_median", "corr"],
                              ["Farm", "Settles on", "HE LOYO", "Median HE", "Corr"], {"he_pooled": f2, "he_median": f2, "corr": f2}))
        parts.append("")

    # Table I: event prices
    if events is not None and not events.empty:
        e = events[events["interval_name"].isin(["Apr-May", "Jun-Jul", "Aug-Sep"])]
        parts.append("**Table I. Fair prices of path-dependent events, 1951-2025 (share of years).** Dry spell = longest run of "
                     "days under 0.10 in within the two months; wet days = days with at least 0.10 in.")
        parts.append(md_table(e, ["site", "interval_name", "median_dry_spell", "p_dryspell_ge_14", "p_dryspell_ge_21", "p_dryspell_ge_28",
                                  "median_wet_days", "p_wetdays_le_6", "p_wetdays_le_10", "p_maxday_ge_2", "p_maxday_ge_3"],
                              ["Site", "Interval", "Median dry spell (days)", "P(spell >= 14 d)", ">= 21 d", ">= 28 d",
                               "Median wet days", "P(wet days <= 6)", "<= 10", "P(1-day max >= 2 in)", ">= 3 in"],
                              {"median_dry_spell": lambda v: f"{v:.0f}", "median_wet_days": lambda v: f"{v:.0f}",
                               **{c: pct for c in ["p_dryspell_ge_14", "p_dryspell_ge_21", "p_dryspell_ge_28", "p_wetdays_le_6",
                                                   "p_wetdays_le_10", "p_maxday_ge_2", "p_maxday_ge_3"]}}))
    return "\n".join(parts)


def _style(ax):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(C_GRID)
    ax.tick_params(colors=C_TEXT2, labelsize=8, length=0)
    ax.xaxis.grid(True, color=C_GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def fig_families(summ: pd.DataFrame, path: Path):
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.4), facecolor="#fcfcfb", sharey=True)
    order = [k for k, *_ in DROUGHT_FAMILIES]
    short = {"D0_ideal": "Ideal 2-month station index", "D1_today": "Today: whole-inch monthly", "D2_third": "Third-inch monthly",
             "D3_sum_whole": "Two-month total, whole-inch", "D4_sum_third": "Two-month total, third-inch",
             "D5_worst_third": "Worst month (lookback)", "D6_andor": "AND / OR digitals", "D7_dryspell": "Dry-spell barrier",
             "D8_wetdays": "Wet-day count", "D9_today_path": "Today + dry spell + wet days", "D10_exotic_mix": "Exotic mix"}
    for ax, role in zip(axes, ("station", "farm")):
        s = summ[(summ["side"] == "drought") & (summ["role"] == role)]
        lo = s[s["eval_set"] == "loyo"].set_index("family").reindex(order)
        ins = s[s["eval_set"] == "in_sample"].set_index("family").reindex(order)
        y = np.arange(len(order))[::-1]
        ax.barh(y, ins["he_pooled"], color=C_GRID, height=0.62, label="in sample")
        ax.barh(y, lo["he_pooled"], color=[C_BLUE if k == "D1_today" else C_ORANGE if k == "D0_ideal" else C_AQUA for k in order],
                height=0.62, label="out of sample (LOYO)")
        for yi, v in zip(y, lo["he_pooled"]):
            ax.text(v + 0.01, yi, f"{v:.2f}", va="center", fontsize=8, color=C_TEXT)
        ax.set_yticks(y)
        ax.set_yticklabels([short[k] for k in order], fontsize=8.5, color=C_TEXT)
        ax.set_xlim(0, 1)
        ax.set_title(f"{role} grid" + (" (2-9 miles from the gauge)" if role == "station" else " (24-58 miles)"), fontsize=10,
                     color=C_TEXT, loc="left")
        ax.set_xlabel("pooled hedge effectiveness vs PRF payout", fontsize=8.5, color=C_TEXT2)
        _style(ax)
    axes[0].legend(frameon=False, fontsize=8, loc="lower right")
    fig.suptitle("Drought-side contract families: grey = in-sample fit, colour = out of sample", fontsize=11, color=C_TEXT,
                 x=0.01, ha="left")
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def fig_site_heatmap(res: pd.DataFrame, path: Path):
    d = res[(res["side"] == "drought") & (res["role"] == "farm") & (res["eval_set"] == "loyo")]
    order = [k for k, *_ in DROUGHT_FAMILIES]
    short = {"D0_ideal": "Ideal", "D1_today": "Today", "D2_third": "Third-inch", "D3_sum_whole": "2-mo whole",
             "D4_sum_third": "2-mo third", "D5_worst_third": "Worst month", "D6_andor": "AND/OR", "D7_dryspell": "Dry spell",
             "D8_wetdays": "Wet days", "D9_today_path": "Today+path", "D10_exotic_mix": "Exotic mix"}
    M = np.full((len(ALL_STUDY), len(order)), np.nan)
    for i, site in enumerate(ALL_STUDY):
        for j, fam in enumerate(order):
            g = d[(d["site"] == site) & (d["family"] == fam)]
            M[i, j] = pooled_he(g) if len(g) else np.nan
    cmap = matplotlib.colors.LinearSegmentedColormap.from_list("blues", SEQ_BLUES)
    fig, ax = plt.subplots(figsize=(11, 4.6), facecolor="#fcfcfb")
    im = ax.imshow(M, cmap=cmap, vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(order)))
    ax.set_xticklabels([short[k] for k in order], rotation=30, ha="right", fontsize=8.5, color=C_TEXT2)
    ax.set_yticks(range(len(ALL_STUDY)))
    ax.set_yticklabels([s if s != "ORD" else "ORD (row crop)" for s in ALL_STUDY], fontsize=9, color=C_TEXT2)
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            if not np.isnan(M[i, j]):
                ax.text(j, i, f"{M[i, j]:.2f}", ha="center", va="center", fontsize=8,
                        color="#f0efec" if M[i, j] > 0.55 else C_TEXT)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0)
    cb = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    cb.set_label("pooled LOYO HE vs PRF payout, farm grid", fontsize=8, color=C_TEXT2)
    cb.ax.tick_params(labelsize=7, colors=C_TEXT2)
    ax.set_title("Out-of-sample hedge effectiveness by site and contract family (farm grid, 11 intervals)", fontsize=11,
                 color=C_TEXT, loc="left")
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def fig_dry_spell(dstats, path: Path):
    sites = ["DFW", "OKC", "SGF", "SAT", "TPA", "DEN", "ABQ", "ORD"]
    fig, axes = plt.subplots(2, 4, figsize=(14, 6), facecolor="#fcfcfb", sharey=True)
    D = np.arange(5, 61)
    for ax, site in zip(axes.ravel(), sites):
        for name, col in (("Apr-May", C_BLUE), ("Jul-Aug", C_ORANGE), ("Oct-Nov", C_AQUA)):
            st = dstats.get((site, INTERVAL_MONTHS[name]))
            if st is None:
                continue
            s = st[st["complete"].fillna(False).astype(bool)]["dry_spell_days"]
            p = [(s >= d).mean() for d in D]
            ax.plot(D, np.array(p) * 100, color=col, linewidth=2, label=name)
        ax.set_title(site, fontsize=10, color=C_TEXT, loc="left")
        ax.set_xlabel("D (days)", fontsize=8.5, color=C_TEXT2)
        ax.yaxis.grid(True, color=C_GRID, linewidth=0.8)
        ax.xaxis.grid(False)
        _style(ax)
        ax.xaxis.grid(False)
        ax.yaxis.grid(True, color=C_GRID, linewidth=0.8)
    axes[0, 0].set_ylabel("fair YES price, cents", fontsize=8.5, color=C_TEXT2)
    axes[1, 0].set_ylabel("fair YES price, cents", fontsize=8.5, color=C_TEXT2)
    axes[0, 0].legend(frameon=False, fontsize=8, loc="upper right")
    fig.suptitle("Fair price of a dry-spell barrier: \"longest run of days under 0.10 in within the interval is at least D\" (1951-2025)",
                 fontsize=11, color=C_TEXT, x=0.01, ha="left")
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def fig_farms(farm: pd.DataFrame, path: Path):
    fams = ["F1_today", "F2_third", "F3_interval_sums_third", "F4_season_total_third", "F5_worst_interval",
            "F6_dry_month_count", "F7_dry_spells", "F8_exotic_mix", "F9_today_plus_exotics"]
    short = {"F1_today": "Today", "F2_third": "Third-inch", "F3_interval_sums_third": "Interval totals",
             "F4_season_total_third": "Season total", "F5_worst_interval": "Worst interval", "F6_dry_month_count": "Dry-month count",
             "F7_dry_spells": "Dry spells", "F8_exotic_mix": "Exotic mix", "F9_today_plus_exotics": "Today+exotics"}
    fig, ax = plt.subplots(figsize=(11, 4.8), facecolor="#fcfcfb")
    x = np.arange(len(fams))
    w = 0.38
    for off, (tname, col, lab) in enumerate((("prf_payout", C_BLUE, "vs the farm's PRF payout"),
                                             ("forage_loss", C_ORANGE, "vs the farm's forage-loss proxy"))):
        g = farm[(farm["target"] == tname) & (farm["eval_set"] == "loyo")]
        vals = [pooled_he(g[g["family"] == f]) for f in fams]
        ax.bar(x + (off - 0.5) * w, vals, width=w - 0.04, color=col, label=lab)
        for xi, v in zip(x + (off - 0.5) * w, vals):
            ax.text(xi, max(v, 0) + 0.01, f"{v:.2f}", ha="center", fontsize=7.5, color=C_TEXT)
    ax.set_xticks(x)
    ax.set_xticklabels([short[f] for f in fams], fontsize=8.5, color=C_TEXT2)
    ax.set_ylabel("pooled LOYO HE, 11 farms", fontsize=8.5, color=C_TEXT2)
    ax.set_ylim(min(0, ax.get_ylim()[0]), 1)
    ax.legend(frameon=False, fontsize=8.5, loc="upper left")
    ax.set_title("Farm-level contract families, out of sample", fontsize=11, color=C_TEXT, loc="left")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.yaxis.grid(True, color=C_GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()
    sites = ["DFW", "ABQ"] if args.quick else ALL_STUDY

    monthly = load_monthly(ALL_STUDY + ["AUS", "MDW"])
    daily = load_daily()
    grids = load_grids()
    idx = load_index(grids["grid_id"].tolist())
    markets = pd.read_parquet(PROCESSED / "kalshi_rain_markets.parquet",
                              columns=["series_ticker", "floor_strike", "is_single_month", "strike_type"])
    markets = markets[markets["is_single_month"].astype(bool) & (markets["strike_type"] == "greater")]
    log("computing daily path statistics ...")
    dstats = daily_stats_cache({k: v for k, v in daily.items() if k in sites or k == "ORD"})
    log(f"  {len(dstats)} site-window tables")

    log("interval study ...")
    res = interval_study(sites, monthly, dstats, idx, grids, markets)
    res.to_csv(PROCESSED / "exotic_interval_results.csv", index=False)
    summ = summarize_families(res)
    summ.to_csv(PROCESSED / "exotic_family_summary.csv", index=False)
    log(summ[(summ["role"] == "farm") & (summ["eval_set"] == "loyo")][["side", "family", "he_pooled", "fair_cost", "load", "thin_share"]].to_string())

    farm = corn = basket = None
    events = event_prices(sites, dstats)
    events.to_csv(PROCESSED / "exotic_event_prices.csv", index=False)
    if not args.quick:
        log("farm block ...")
        scen = pd.read_csv(PROCESSED / "prf_scenario_results.csv")
        farm = farm_study(load_farms(), monthly, dstats, idx, grids, markets, scen)
        farm.to_csv(PROCESSED / "exotic_farm_results.csv", index=False)
        log("corn collar ...")
        corn = corn_study(monthly, dstats, listed_strikes_for("KXRAINCHIM", markets))
        corn.to_csv(PROCESSED / "exotic_corn_results.csv", index=False)
        log(corn[["family", "eval_set", "he", "fair_cost", "load"]].to_string())
        log("baskets ...")
        basket = basket_study(monthly, idx, grids)
        basket.to_csv(PROCESSED / "exotic_basket_results.csv", index=False)

    fig_families(summ, FIGURES / "x2_drought_families_he.png")
    fig_site_heatmap(res, FIGURES / "x2_he_by_site_family.png")
    fig_dry_spell(dstats, FIGURES / "x2_dry_spell_fair_price.png")
    if farm is not None:
        fig_farms(farm, FIGURES / "x2_farm_families_he.png")

    text = build_tables(summ, res, farm, corn, basket, events)
    replace_between_markers(DOC, "<!-- BEGIN AUTO: exotic payout tables (scripts/run_exotic_payouts.py) -->",
                            "<!-- END AUTO: exotic payout tables (scripts/run_exotic_payouts.py) -->",
                            text, PROCESSED / "exotic_tables.md")


if __name__ == "__main__":
    main()
