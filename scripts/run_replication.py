"""A2 baseline: how well do Kalshi-style monthly-rain ladders replicate PRF payouts, by location?

Run from the repo root (no network needed; all inputs are in data/processed):
    python scripts/run_replication.py              # full run (about 5-10 minutes)
    python scripts/run_replication.py --quick      # smoke test: no LOYO CV, no ridge search, no
                                                   # figures; writes to data/raw/replication_quick/

Inputs
  data/processed/study_grids.csv            site, role (station|farm), grid_id, distance_to_station_mi
  data/processed/prf_official_index.csv     NCEI-based DST index, 1951-2025 base (primary target)
  data/processed/ncei_interval_index.parquet   our NCEI rebuild (fallback for missing rows)
  data/processed/cpc_interval_index.parquet    CPC rebuild: index_value_fixed_base (robustness
                                            target, base 1948-2025) and index_value_ours
                                            (as settled, used only to evaluate 2010-2025)
  data/processed/station_monthly_precip.csv settlement-station monthly totals (n_missing == 0)
  data/processed/kalshi_rain_markets.parquet   strikes Kalshi lists per series and month
  data/processed/prf_actuarial_study_grids.csv 2026 premium rates (reference column only)
  data/scenarios/farms.yaml                 the 11 representative farms

Method (see docs/analysis/08_replication_quality.md)
  For every site x role x interval x coverage (70, 85, 90%) and target (NCEI, CPC):
    H1 ideal station-index contract, H2 0.25-inch NO ladder, H3 Kalshi-listed NO ladder,
    NNLS weights, no intercept. Time split: fit 1951-2009, test 2010-2025. Leave-one-year-out
    (LOYO) CV over 1951-2025. A ridge penalty (per family) is chosen by pooled LOYO CV inside the
    training window only. Sensitivity: free-sign intercept (NCEI target).
  Farm policies: allocation-weighted sums of the per-interval hedges at the farm's coverage.

Outputs
  data/processed/replication_weights.csv   NO-contract weights per $ of protection (H2, H3)
  data/processed/replication_backtest.csv  yearly PRF vs hedge payouts
  data/processed/replication_summary.csv   metrics
  docs/figures/a2_*.png                    figures
  docs/analysis/08_replication_quality.md  tables between the AUTO markers are regenerated
"""
from __future__ import annotations

import argparse
import calendar
import time

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import yaml  # noqa: E402

from agri_hedge.config import DOCS, FIGURES, PROCESSED, RAW, SCENARIOS  # noqa: E402
from agri_hedge.locations import ALL_SITES, STUDY_SITES  # noqa: E402
from agri_hedge.prf import dollar_amount_of_protection_per_acre  # noqa: E402
from agri_hedge.prf_grid import latlon_to_grid_id  # noqa: E402
from agri_hedge.prf_intervals import INTERVAL_CODES, INTERVAL_MONTHS, INTERVAL_NAMES  # noqa: E402
from agri_hedge.replicate import (  # noqa: E402
    evaluate,
    fine_strikes,
    kalshi_strike_sets,
    ladder_design,
    loyo_predictions,
    prf_payout,
    pooled_he,
    replicate_interval,
    replication_metrics,
)

FIRST_YEAR, LAST_YEAR = 1951, 2025
TRAIN = (1951, 2009)
TEST = (2010, 2025)
FULL = (1951, 2025)
COVERAGES = (0.70, 0.85, 0.90)
TARGETS = ("ncei", "cpc")
TARGET_LABEL = {
    "ncei": "NCEI nClimGrid-based PRF index as shown by RMA's DST (fixed 1951-2025 base)",
    "cpc": "CPC-based PRF index rebuild, fixed 1948-2025 base (index_value_fixed_base)",
    "cpc_as_settled": "CPC-based index as settled (base 1948 to Y-2), evaluation of CPC-fit hedges",
}
STATION_NORMAL_BASE = {"ncei": (1951, 2025), "cpc": (1948, 2025)}
RIDGE_GRID = (0.0, 1e-3, 3e-3, 1e-2, 3e-2, 0.1, 0.3, 1.0)
#: Penalties the full run selected on 2026-10-29 (used by --quick, which skips the search).
DEFAULT_RIDGE = {"H2": 0.1, "H3": 0.03}
QUICK_DIR = RAW / "replication_quick"
SITES = list(ALL_SITES)      # 7 PRF sites + ORD (row-crop contrast, flagged)
DOC = DOCS / "analysis" / "08_replication_quality.md"
AUTO_BEGIN = "<!-- BEGIN AUTO: replication tables (scripts/run_replication.py) -->"
AUTO_END = "<!-- END AUTO: replication tables -->"

# Reference palette (same as other workstreams' figures).
C_BLUE, C_ORANGE, C_AQUA, C_GRAY = "#2a78d6", "#eb6834", "#1baf7a", "#8a8984"
INK, INK2, GRID = "#0b0b0b", "#52514e", "#d9d8d4"
FAM_STYLE = {"H1": dict(color=C_BLUE, marker="o", ls="-", hatch=""),
             "H2": dict(color=C_AQUA, marker="s", ls="--", hatch="//"),
             "H3": dict(color=C_ORANGE, marker="^", ls=":", hatch="..")}
FAM_SHORT = {"H1": "H1 ideal station index", "H2": "H2 fine 0.25-in ladder", "H3": "H3 Kalshi ladder"}


# ---------------------------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------------------------

def load_station_monthly() -> dict[str, pd.DataFrame]:
    """{site: year x month (1-12) table of complete-month totals in inches; NaN if incomplete}."""
    st = pd.read_csv(PROCESSED / "station_monthly_precip.csv")
    st = st[st["station_key"].isin(SITES)]
    out = {}
    for site, g in st.groupby("station_key"):
        g = g.copy()
        g.loc[g["n_missing"] != 0, "precip_in"] = np.nan
        w = g.pivot_table(index="year", columns="month", values="precip_in", aggfunc="first")
        out[site] = w.reindex(columns=range(1, 13))
    return out


def load_station_sources() -> pd.DataFrame:
    st = pd.read_csv(PROCESSED / "station_monthly_precip.csv", usecols=["station_key", "year", "month", "source"])
    return st[st["station_key"].isin(SITES)]


def load_targets(grids: list[int]) -> dict[str, pd.DataFrame]:
    """{target: long table grid_id, year, interval_name, index_value} for 1951-2025 (+as-settled)."""
    off = pd.read_csv(PROCESSED / "prf_official_index.csv")
    off = off[off["grid_id"].isin(grids) & off["year"].between(FIRST_YEAR, LAST_YEAR)]
    ncei = off[["grid_id", "year", "interval_name", "index_value"]].copy()
    reb = pd.read_parquet(PROCESSED / "ncei_interval_index.parquet",
                          columns=["grid_id", "year", "interval_name", "index_value_ours"])
    reb = reb[reb["grid_id"].isin(grids) & reb["year"].between(FIRST_YEAR, LAST_YEAR)].copy()
    reb["interval_name"] = reb["interval_name"].astype(str)
    reb = reb.rename(columns={"index_value_ours": "index_value"})
    key = ["grid_id", "year", "interval_name"]
    ncei = pd.concat([ncei, reb[~reb.set_index(key).index.isin(ncei.set_index(key).index)]], ignore_index=True)
    cpc = pd.read_parquet(PROCESSED / "cpc_interval_index.parquet",
                          columns=["grid_id", "year", "interval_name", "index_value_fixed_base", "index_value_ours"])
    cpc = cpc[cpc["grid_id"].isin(grids) & cpc["year"].between(FIRST_YEAR, LAST_YEAR)].copy()
    cpc["interval_name"] = cpc["interval_name"].astype(str)
    out = {"ncei": ncei,
           "cpc": cpc.rename(columns={"index_value_fixed_base": "index_value"})[key + ["index_value"]],
           "cpc_as_settled": cpc.rename(columns={"index_value_ours": "index_value"})[key + ["index_value"]]}
    for k in out:
        out[k]["index_value"] = out[k]["index_value"].astype(float)
    return out


def index_series(tbl: pd.DataFrame, grid_id: int, interval: str, years: np.ndarray) -> np.ndarray:
    g = tbl[(tbl["grid_id"] == grid_id) & (tbl["interval_name"] == interval)].set_index("year")["index_value"]
    return g.reindex(years).to_numpy(dtype=float)


def load_farms() -> list[dict]:
    with open(SCENARIOS / "farms.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)["farms"]


def load_premium_rates() -> pd.DataFrame:
    """2026 premium rate per grid x interval x coverage (rates are county- and use-invariant)."""
    a = pd.read_csv(PROCESSED / "prf_actuarial_study_grids.csv")
    a = a[a["crop_year"] == 2026]
    a["coverage_level"] = a["coverage_level"].round(2)
    return a.groupby(["grid_id", "interval_name", "coverage_level"])["premium_rate"].first()


# ---------------------------------------------------------------------------------------------
# Ridge selection (training window only)
# ---------------------------------------------------------------------------------------------

def select_ridge(station: dict, targets: dict, grids: pd.DataFrame, fine_sets: dict, kal_sets: dict,
                 coverage: float = 0.90) -> dict[str, float]:
    """Pick one ridge penalty per ladder family by pooled LOYO MSE inside the training years.

    Pools every PRF site (not ORD), both roles and all 11 intervals for the NCEI target at
    `coverage`. Test years 2010-2025 are never touched. Returns {"H2": lam, "H3": lam, "table": df}.
    """
    years = np.arange(TRAIN[0], TRAIN[1] + 1)
    sse = {(fam, lam): 0.0 for fam in ("H2", "H3") for lam in RIDGE_GRID}
    for _, g in grids[grids["site"].isin(STUDY_SITES)].iterrows():
        site, gid = g["site"], int(g["grid_id"])
        rain = station[site].reindex(years)
        for iv in INTERVAL_NAMES:
            m1, m2 = INTERVAL_MONTHS[iv]
            y = rep_target(targets["ncei"], gid, iv, years, coverage)
            r1, r2 = rain[m1].to_numpy(float), rain[m2].to_numpy(float)
            ok = ~(np.isnan(y) | np.isnan(r1) | np.isnan(r2))
            for fam, sets in (("H2", fine_sets[site]), ("H3", kal_sets[site])):
                X, _ = ladder_design({m1: r1[ok], m2: r2[ok]}, {m1: sets[m1], m2: sets[m2]})
                for lam in RIDGE_GRID:
                    pred = loyo_predictions(X, y[ok], ridge=lam)
                    sse[(fam, lam)] += float(np.sum((y[ok] - pred) ** 2))
    tab = pd.DataFrame([{"hedge_family": f, "ridge": l, "pooled_loyo_sse_train": v} for (f, l), v in sse.items()])
    best = tab.loc[tab.groupby("hedge_family")["pooled_loyo_sse_train"].idxmin()].set_index("hedge_family")["ridge"]
    return {"H2": float(best["H2"]), "H3": float(best["H3"]), "table": tab}


def rep_target(tbl: pd.DataFrame, gid: int, iv: str, years: np.ndarray, coverage: float) -> np.ndarray:
    return prf_payout(index_series(tbl, gid, iv, years), coverage)


# ---------------------------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------------------------

def run(quick: bool = False):
    t0 = time.time()
    grids = pd.read_csv(PROCESSED / "study_grids.csv")
    grids = grids[grids["site"].isin(SITES)].reset_index(drop=True)
    station = load_station_monthly()
    sources = load_station_sources()
    targets = load_targets(grids["grid_id"].astype(int).tolist())
    markets = pd.read_parquet(PROCESSED / "kalshi_rain_markets.parquet")
    rates = load_premium_rates()
    years_all = np.arange(FIRST_YEAR, LAST_YEAR + 1)

    # Strike sets per site and calendar month.
    fine_sets, kal_sets = {}, {}
    for site in SITES:
        rain = station[site].loc[FIRST_YEAR:LAST_YEAR]
        fine_sets[site] = {m: tuple(fine_strikes(np.nanmax(rain[m]))) for m in range(1, 13)}
        kal_sets[site] = kalshi_strike_sets(markets, ALL_SITES[site]["kalshi_series"])

    out_dir = PROCESSED
    if quick:
        ridge = {**DEFAULT_RIDGE, "table": pd.DataFrame()}
        out_dir = QUICK_DIR
        out_dir.mkdir(parents=True, exist_ok=True)
    else:
        ridge = select_ridge(station, targets, grids, fine_sets, kal_sets)
        print(f"ridge selected (training-window LOYO): H2={ridge['H2']}, H3={ridge['H3']}  [{time.time() - t0:.0f}s]")
        print(ridge["table"].pivot(index="ridge", columns="hedge_family", values="pooled_loyo_sse_train").round(4))

    weight_rows, back_rows, summ_rows, reps = [], [], [], {}
    for _, g in grids.iterrows():
        site, role, gid = g["site"], g["role"], int(g["grid_id"])
        meta = ALL_SITES[site]
        rain = station[site].reindex(years_all)
        for iv in INTERVAL_NAMES:
            m1, m2 = INTERVAL_MONTHS[iv]
            r1, r2 = rain[m1].to_numpy(float), rain[m2].to_numpy(float)
            desc = site_descriptors(station[site], targets, gid, iv, kal_sets[site], m1, m2)
            desc["distance_to_station_mi"] = float(g["distance_to_station_mi"])
            for tgt in TARGETS:
                gi = index_series(targets[tgt], gid, iv, years_all)
                base = STATION_NORMAL_BASE[tgt]
                tot = (station[site][m1] + station[site][m2]).loc[base[0]:base[1]]
                normal = float(tot.mean())
                normal_train = float(tot.loc[TRAIN[0]:TRAIN[1]].mean())
                desc_t = {**desc, "station_normal_in": normal,
                          "station_grid_rain_corr_train": rain_corr(station[site], targets, tgt, gid, iv, m1, m2)}
                for cov in COVERAGES:
                    variants = ("no_intercept", "free_intercept") if tgt == "ncei" else ("no_intercept",)
                    rep = replicate_interval(years_all, gi, r1, r2, (m1, m2), cov, TRAIN, fine_sets[site],
                                             kal_sets[site], normal, ridge={"H2": ridge["H2"], "H3": ridge["H3"]},
                                             variants=variants, do_loyo=not quick, full_window=FULL)
                    reps[(tgt, site, role, iv, cov)] = rep
                    key = dict(target_index=tgt, site=site, is_prf_site=site in STUDY_SITES, role=role,
                               grid_id=gid, farm_id="", interval_name=iv, coverage=cov)
                    # Sensitivity: H1 with the station normal from training years only.
                    rep.hedges[("H1", "train_normal", "split")] = prf_payout(rep.station_index * normal / normal_train, cov)
                    fair = fair_costs(rep)
                    prf_mean_train = float(np.mean(rep.prf[rep.train_mask]))
                    for r in evaluate(rep, TEST):
                        if r["hedge_family"] == "H1" and r["fit_variant"] == "train_normal" and r["eval_set"] == "train":
                            continue
                        summ_rows.append({**key, **r, "fair_cost_per_dollar": fair.get((r["hedge_family"], r["fit_variant"]), np.nan),
                                          "prf_mean_payout_train": prf_mean_train,
                                          "ridge": ridge.get(r["hedge_family"], 0.0) if r["hedge_family"] != "H1" else np.nan,
                                          "premium_rate_2026": rates.get((gid, iv, round(cov, 2)), np.nan), **desc_t})
                    if tgt == "cpc":
                        # Evaluate CPC-fit split hedges against the as-settled CPC index, 2010-2025.
                        gi_s = index_series(targets["cpc_as_settled"], gid, iv, rep.years)
                        test = (rep.years >= TEST[0]) & (rep.years <= TEST[1]) & ~np.isnan(gi_s)
                        for (fam, var, scheme), h in rep.hedges.items():
                            if scheme != "split" or var == "train_normal":
                                continue
                            m = replication_metrics(prf_payout(gi_s[test], cov), h[test], gi_s[test])
                            summ_rows.append({**key, "target_index": "cpc_as_settled", "hedge_family": fam,
                                              "fit_variant": var, "eval_set": "test",
                                              "eval_years": f"{TEST[0]}-{TEST[1]}", **m,
                                              "fair_cost_per_dollar": fair.get((fam, var), np.nan),
                                              "prf_mean_payout_train": prf_mean_train,
                                              "ridge": ridge.get(fam, 0.0) if fam != "H1" else np.nan,
                                              "premium_rate_2026": rates.get((gid, iv, round(cov, 2)), np.nan), **desc_t})
                    weight_rows += weight_records(rep, key, meta, site, iv, cov, prf_mean_train, ridge,
                                                  rates.get((gid, iv, round(cov, 2)), np.nan), kal_sets[site])
                    back_rows.append(backtest_frame(rep, key, targets, gid, iv, tgt))
        print(f"{site} {role} done [{time.time() - t0:.0f}s]")

    weights = pd.DataFrame(weight_rows)
    weights.to_csv(out_dir / "replication_weights.csv", index=False, float_format="%.6g")
    print(f"wrote replication_weights.csv ({len(weights)} rows) [{time.time() - t0:.0f}s]")

    farm_summ, farm_back = farm_policies(reps, grids, quick)
    summary = pd.concat([pd.DataFrame(summ_rows), farm_summ], ignore_index=True)
    backtest = pd.concat(back_rows + [farm_back], ignore_index=True)
    summary.to_csv(out_dir / "replication_summary.csv", index=False, float_format="%.5g")
    backtest.to_csv(out_dir / "replication_backtest.csv", index=False, float_format="%.5g")
    print(f"wrote summary ({len(summary)}) and backtest ({len(backtest)}) [{time.time() - t0:.0f}s]")

    extras = threaded_check(reps, sources)
    if not quick:
        make_figures(summary, backtest, station, kal_sets, reps)
        update_doc(summary, weights, ridge, extras)
    print(f"done [{time.time() - t0:.0f}s]")
    return summary, weights, backtest


def fair_costs(rep) -> dict:
    """{(family, variant): fair cost per $ (train-window mean payout of the train-window fit)}."""
    return {(fam, var): float(np.mean(h[rep.train_mask]))
            for (fam, var, scheme), h in rep.hedges.items() if scheme == "split"}


def site_descriptors(rain: pd.DataFrame, targets, gid, iv, kal, m1, m2) -> dict:
    """Climate descriptors for one site x interval: medians and P(rain <= lowest Kalshi strike)."""
    r = rain.loc[TRAIN[0]:TRAIN[1]]
    lo1, lo2 = min(kal[m1]), min(kal[m2])
    return {"month1": m1, "month2": m2,
            "median_rain_m1_in": float(np.nanmedian(r[m1])), "median_rain_m2_in": float(np.nanmedian(r[m2])),
            "lowest_kalshi_strike_m1_in": lo1, "lowest_kalshi_strike_m2_in": lo2,
            "p_rain_le_lowest_strike_m1": float(np.nanmean(r[m1] <= lo1 + 1e-9)),
            "p_rain_le_lowest_strike_m2": float(np.nanmean(r[m2] <= lo2 + 1e-9))}


def rain_corr(rain: pd.DataFrame, targets, tgt, gid, iv, m1, m2) -> float:
    """Correlation of station interval total with the grid index (training years)."""
    yrs = np.arange(TRAIN[0], TRAIN[1] + 1)
    s = (rain[m1] + rain[m2]).reindex(yrs).to_numpy(float)
    gi = index_series(targets[tgt], gid, iv, yrs)
    ok = ~(np.isnan(s) | np.isnan(gi))
    return float(np.corrcoef(s[ok], gi[ok])[0, 1])


def weight_records(rep, key, meta, site, iv, cov, prf_mean_train, ridge, prem, kal) -> list[dict]:
    """Non-zero NO legs of the H2/H3 no-intercept fits (train window and full window)."""
    rows = []
    for fam in ("H2", "H3"):
        for window, yrs, use in (("train", TRAIN, "backtest"), ("full", FULL, "forward")):
            f = rep.fits.get((fam, "no_intercept", window))
            if f is None:
                continue
            probs = rep.leg_probs[(fam, window)]
            fc = float(np.sum(f.weights * probs))
            n_tr = int(((rep.years >= yrs[0]) & (rep.years <= yrs[1])).sum())
            nz = np.flatnonzero(f.weights > 0)
            for j in nz:
                mon, k = f.legs[j]
                rows.append({
                    "target_index": key["target_index"], "site": site, "is_prf_site": key["is_prf_site"],
                    "role": key["role"], "grid_id": key["grid_id"], "interval_name": iv,
                    "interval_code": INTERVAL_CODES[iv], "coverage": cov, "hedge_family": fam,
                    "fit_window": window, "train_years": f"{yrs[0]}-{yrs[1]}", "n_train_years": n_tr,
                    "weights_use": use, "kalshi_series": meta["kalshi_series"], "cli_code": meta["cli_code"],
                    "station_ghcn": meta["ghcn"], "contract_month": mon,
                    "contract_month_name": calendar.month_abbr[mon], "strike_in": k, "position": "NO",
                    "payoff_rule": "NO pays $1 if station monthly total <= strike_in",
                    "weight_per_dollar_protection": float(f.weights[j]),
                    "leg_prob_pays_fit_window": float(probs[j]),
                    "leg_fair_cost_per_dollar": float(f.weights[j] * probs[j]),
                    "fair_cost_per_dollar": fc, "n_legs": len(nz),
                    "prf_mean_payout_fit_window": prf_mean_train if window == "train" else
                    float(np.mean(rep.prf[(rep.years >= yrs[0]) & (rep.years <= yrs[1])])),
                    "premium_rate_2026": prem, "ridge": ridge.get(fam, 0.0),
                    "strike_listed_on_kalshi": bool(any(abs(k - x) < 1e-9 for x in kal[mon])),
                })
    return rows


def backtest_frame(rep, key, targets, gid, iv, tgt) -> pd.DataFrame:
    df = pd.DataFrame({
        "target_index": tgt, "site": key["site"], "role": key["role"], "grid_id": gid, "farm_id": "",
        "interval_name": iv, "coverage": key["coverage"], "year": rep.years,
        "sample": np.where(rep.train_mask, "train", "test"), "grid_index": rep.index,
        "station_index": rep.station_index, "prf_payout": rep.prf,
        "h1": rep.hedges[("H1", "none", "split")],
        "h1_scaled_split": rep.hedges[("H1", "scaled", "split")],
        "h2_split": rep.hedges[("H2", "no_intercept", "split")],
        "h3_split": rep.hedges[("H3", "no_intercept", "split")],
        "h2_loyo": rep.hedges.get(("H2", "no_intercept", "loyo"), np.full(len(rep.years), np.nan)),
        "h3_loyo": rep.hedges.get(("H3", "no_intercept", "loyo"), np.full(len(rep.years), np.nan)),
        "policy_protection_usd": np.nan,
    })
    if tgt == "cpc":
        df["grid_index_cpc_as_settled"] = index_series(targets["cpc_as_settled"], gid, iv, rep.years)
    return df


# ---------------------------------------------------------------------------------------------
# Farm policies
# ---------------------------------------------------------------------------------------------

def farm_policies(reps: dict, grids: pd.DataFrame, quick: bool):
    """Allocation-weighted policy payouts (per $ of total protection and in dollars) per farm."""
    rows, backs = [], []
    for farm in load_farms():
        site, cov = farm["site"], round(float(farm["coverage_level"]), 2)
        gid = int(grids[(grids["site"] == site) & (grids["role"] == "farm")]["grid_id"].iloc[0])
        assert gid == latlon_to_grid_id(float(farm["lat"]), float(farm["lon"])), farm["farm_id"]
        alloc = {k: float(v) for k, v in farm["interval_allocation"].items() if float(v) > 0}
        protection = float(dollar_amount_of_protection_per_acre(
            float(farm["county_base_value_usd_per_acre"]), cov, float(farm["productivity_factor"]))) \
            * float(farm["insured_acres"]) * float(farm.get("share", 1.0) or 1.0)
        for tgt in TARGETS:
            parts = {iv: reps[(tgt, site, "farm", iv, cov)] for iv in alloc}
            years = sorted(set.intersection(*[set(r.years.tolist()) for r in parts.values()]))
            years = np.array(years)

            def agg(fn):
                tot = np.zeros(len(years))
                for iv, r in parts.items():
                    s = pd.Series(fn(r), index=r.years).reindex(years).to_numpy(float)
                    tot += alloc[iv] * s
                return tot
            prf = agg(lambda r: r.prf)
            widx = agg(lambda r: r.index)
            train = (years >= TRAIN[0]) & (years <= TRAIN[1])
            test = (years >= TEST[0]) & (years <= TEST[1])
            hedges = {}
            for fam, var in (("H1", "none"), ("H1", "scaled"), ("H2", "no_intercept"), ("H3", "no_intercept")):
                for scheme in ("split", "loyo"):
                    if (fam, var, scheme) in next(iter(parts.values())).hedges:
                        name = "H1s" if var == "scaled" else fam
                        hedges[(name, scheme)] = agg(lambda r, k=(fam, var, scheme): r.hedges[k])
            key = dict(target_index=tgt, site=site, is_prf_site=True, role="farm_policy", grid_id=gid,
                       farm_id=farm["farm_id"], interval_name="+".join(alloc), coverage=cov)
            for (fam, scheme), h in hedges.items():
                sets = {"train": train, "test": test} if scheme == "split" else {"loyo": np.ones(len(years), bool)}
                for name, mask in sets.items():
                    m = replication_metrics(prf[mask], h[mask], widx[mask])
                    rows.append({**key, "hedge_family": fam[:2],
                                 "fit_variant": {"H1": "none", "H1s": "scaled"}.get(fam, "no_intercept"),
                                 "eval_set": name, "eval_years": f"{years[mask].min()}-{years[mask].max()}", **m,
                                 "fair_cost_per_dollar": float(np.mean(hedges[(fam, 'split')][train])),
                                 "prf_mean_payout_train": float(np.mean(prf[train])),
                                 "policy_protection_usd": protection,
                                 "rmse_usd": m["rmse"] * protection, "mean_prf_usd": m["mean_prf"] * protection,
                                 "mean_hedge_usd": m["mean_hedge"] * protection,
                                 "fair_cost_usd": float(np.mean(hedges[(fam, 'split')][train])) * protection,
                                 "distance_to_station_mi": float(grids[(grids['site'] == site) & (grids['role'] == 'farm')]['distance_to_station_mi'].iloc[0])})
            backs.append(pd.DataFrame({
                "target_index": tgt, "site": site, "role": "farm_policy", "grid_id": gid, "farm_id": farm["farm_id"],
                "interval_name": "+".join(alloc), "coverage": cov, "year": years,
                "sample": np.where(train, "train", "test"), "grid_index": widx, "station_index": np.nan,
                "prf_payout": prf, "h1": hedges[("H1", "split")], "h1_scaled_split": hedges[("H1s", "split")],
                "h2_split": hedges[("H2", "split")],
                "h3_split": hedges[("H3", "split")],
                "h2_loyo": hedges.get(("H2", "loyo"), np.full(len(years), np.nan)),
                "h3_loyo": hedges.get(("H3", "loyo"), np.full(len(years), np.nan)),
                "policy_protection_usd": protection}))
    return pd.DataFrame(rows), pd.concat(backs, ignore_index=True)


def threaded_check(reps, sources) -> dict:
    """Share of training years that come from ThreadEx predecessor records (DFW, DEN, ORD)."""
    out = {}
    thr = sources[sources["source"].str.startswith("acis_threaded")]
    for site in ("DFW", "DEN", "ORD"):
        yrs = thr[(thr["station_key"] == site)]["year"]
        out[site] = (int(yrs.min()), int(yrs.max())) if len(yrs) else None
    return out


# ---------------------------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------------------------

def _style(ax):
    ax.grid(True, color=GRID, lw=0.6, zorder=0)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


#: (hedge_family, fit_variant) pairs used in tables and figures, with short labels.
HEDGES = [("H1", "none", "H1 ideal station index"), ("H1", "scaled", "H1s ideal index, fitted scale"),
          ("H2", "no_intercept", "H2 fine 0.25-in ladder"), ("H3", "no_intercept", "H3 Kalshi ladder")]


def _sel(summary, target="ncei", coverage=0.90, eval_set="loyo", prf_only=True, roles=("station", "farm")):
    d = summary[(summary["target_index"] == target) & (summary["coverage"] == coverage)
                & (summary["eval_set"] == eval_set) & summary["role"].isin(roles)]
    if prf_only:
        d = d[d["is_prf_site"].astype(bool)]
    return d


def _phe(d, fam, var):
    return pooled_he(d[(d["hedge_family"] == fam) & (d["fit_variant"] == var)])


def make_figures(summary, backtest, station, kal_sets, reps):
    prf_sites = list(STUDY_SITES)
    s = _sel(summary)

    # 1. Pooled HE by site, role and family (LOYO, 90%); H1 unscaled shown as a tick.
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.4), sharey=True)
    for ax, role in zip(axes, ("station", "farm")):
        x = np.arange(len(prf_sites))
        vals = {(f, v): [_phe(s[(s["site"] == si) & (s["role"] == role)], f, v) for si in prf_sites]
                for f, v, _ in HEDGES}
        for j, (fam, var) in enumerate((("H1", "scaled"), ("H2", "no_intercept"), ("H3", "no_intercept"))):
            st = FAM_STYLE[fam]
            ax.bar(x + (j - 1) * 0.27, vals[(fam, var)], 0.25, color=st["color"], hatch=st["hatch"],
                   edgecolor="white", lw=0.5, zorder=3,
                   label={"H1": "H1s ideal station index (fitted scale)", "H2": FAM_SHORT["H2"], "H3": FAM_SHORT["H3"]}[fam])
        ax.scatter(x - 0.27, np.maximum(vals[("H1", "none")], -0.2), marker="_", s=180, color=INK, lw=2, zorder=4,
                   label="H1 unscaled (clipped at -0.2)")
        ax.axhline(0, color=INK2, lw=0.8)
        ax.set_xticks(x, prf_sites)
        ax.set_ylim(-0.25, 1.0)
        ax.set_title(f"{role.capitalize()} grid", fontsize=11)
        _style(ax)
    axes[0].set_ylabel("Hedge effectiveness, pooled over 11 intervals\n(share of PRF payout variance removed)")
    axes[1].legend(frameon=False, fontsize=7.5, loc="upper right", ncol=1)
    fig.suptitle("Replication quality by site: 90% coverage, NCEI target, leave-one-year-out 1951-2025", fontsize=11)
    fig.tight_layout()
    fig.savefig(FIGURES / "a2_he_by_site_family.png", dpi=150)
    plt.close(fig)

    # 2. Heatmaps of per-interval HE by site-role x interval (H3 and H1 scaled).
    for (fam, var), fname, label in ((("H3", "no_intercept"), "a2_he_heatmap_h3.png", FAM_SHORT["H3"]),
                                     (("H1", "scaled"), "a2_he_heatmap_h1.png", "H1s ideal station index (fitted scale)")):
        d = s[(s["hedge_family"] == fam) & (s["fit_variant"] == var)].pivot_table(
            index=["site", "role"], columns="interval_name", values="he")
        d = d.reindex(columns=INTERVAL_NAMES).reindex([(si, r) for si in prf_sites for r in ("station", "farm")])
        fig, ax = plt.subplots(figsize=(10, 5.6))
        im = ax.imshow(np.clip(d.to_numpy(), 0, 1), cmap="Blues", vmin=0, vmax=1, aspect="auto")
        for i in range(d.shape[0]):
            for j in range(d.shape[1]):
                v = d.iloc[i, j]
                if np.isfinite(v):
                    ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=7,
                            color="white" if v > 0.6 else INK)
        ax.set_xticks(range(len(INTERVAL_NAMES)), INTERVAL_NAMES, rotation=45, ha="right")
        ax.set_yticks(range(d.shape[0]), [f"{a} {b}" for a, b in d.index])
        ax.set_xlabel("PRF interval")
        cb = fig.colorbar(im, ax=ax)
        cb.set_label("Hedge effectiveness (colour clipped at 0; text shows value)")
        ax.set_title(f"{label}: hedge effectiveness by site and interval\n"
                     "90% coverage, NCEI target, leave-one-year-out 1951-2025", fontsize=11)
        fig.tight_layout()
        fig.savefig(FIGURES / fname, dpi=150)
        plt.close(fig)

    # 3. HE vs distance from station.
    fig, ax = plt.subplots(figsize=(7.8, 4.8))
    dist = s.groupby(["site", "role"])["distance_to_station_mi"].first()
    for (fam, var, lab), mk, fc in ((HEDGES[0], "o", FAM_STYLE["H1"]["color"]), (HEDGES[1], "o", "white"),
                                    (HEDGES[3], "^", FAM_STYLE["H3"]["color"])):
        pts = [(dist[k], _phe(s[(s["site"] == k[0]) & (s["role"] == k[1])], fam, var)) for k in dist.index]
        xs, ys = zip(*pts)
        ax.scatter(xs, np.maximum(ys, -0.6), marker=mk, s=46, facecolor=fc,
                   edgecolor=FAM_STYLE[fam]["color"], lw=1.4, label=lab, zorder=3)
        if fam == "H3":
            for k, (xx, yy) in zip(dist.index, pts):
                ax.annotate(k[0], (xx, yy), textcoords="offset points", xytext=(4, -9), fontsize=7, color=INK2)
    ax.axhline(0, color=INK2, lw=0.8)
    ax.set_xlabel("Distance from settlement station to PRF grid centre (miles)")
    ax.set_ylabel("Hedge effectiveness, pooled over 11 intervals")
    ax.set_title("Hedge effectiveness vs distance (90% coverage, NCEI target, leave-one-year-out)\n"
                 "unscaled H1 values below -0.6 are drawn at -0.6", fontsize=10)
    ax.legend(frameon=False, fontsize=8, loc="lower left")
    _style(ax)
    fig.tight_layout()
    fig.savefig(FIGURES / "a2_he_vs_distance.png", dpi=150)
    plt.close(fig)

    # 4. Where the lowest Kalshi strike sits in the monthly distribution.
    fig, ax = plt.subplots(figsize=(10, 4.4))
    mat = np.array([[np.nanmean(station[si].loc[TRAIN[0]:TRAIN[1], m] <= min(kal_sets[si][m]) + 1e-9)
                     for m in range(1, 13)] for si in prf_sites])
    im = ax.imshow(mat, cmap="Blues", vmin=0, vmax=1, aspect="auto")
    for i in range(mat.shape[0]):
        for j in range(12):
            ax.text(j, i, f"{mat[i, j]:.2f}", ha="center", va="center", fontsize=7,
                    color="white" if mat[i, j] > 0.6 else INK)
    ax.set_xticks(range(12), [calendar.month_abbr[m] for m in range(1, 13)])
    ax.set_yticks(range(len(prf_sites)), prf_sites)
    ax.set_xlabel("Calendar month")
    cb = fig.colorbar(im, ax=ax)
    cb.set_label("Probability the 1-inch NO pays")
    ax.set_title("Share of months (1951-2009) with station rain at or below the lowest Kalshi strike (1 in)\n"
                 "above 0.5 = the lowest strike is above the median month, so the ladder cannot see a dry month",
                 fontsize=10)
    fig.tight_layout()
    fig.savefig(FIGURES / "a2_lowest_strike_probability.png", dpi=150)
    plt.close(fig)

    # 5. Example time series: good and poor cases.
    cases = [("OKC", "station", "May-Jun"), ("DFW", "farm", "Apr-May"), ("ABQ", "station", "Apr-May"),
             ("TPA", "farm", "Jul-Aug")]
    fig, axes = plt.subplots(2, 2, figsize=(11, 6.4), sharex=True)
    b = backtest[(backtest["target_index"] == "ncei") & (backtest["coverage"] == 0.90)]
    for ax, (si, ro, iv) in zip(axes.flat, cases):
        d = b[(b["site"] == si) & (b["role"] == ro) & (b["interval_name"] == iv)].sort_values("year")
        ax.bar(d["year"], d["prf_payout"], color=GRID, edgecolor=INK2, lw=0.3, label="PRF payout", zorder=2)
        for fam, col, lab in (("H1", "h1", "H1 ideal station index"), ("H3", "h3_loyo", "H3 Kalshi ladder (LOYO)")):
            st = FAM_STYLE[fam]
            ax.plot(d["year"], d[col], color=st["color"], ls=st["ls"], marker=st["marker"], ms=2.5, lw=1.1,
                    label=lab, zorder=3)
        ax.axvspan(TEST[0] - 0.5, TEST[1] + 0.5, color=C_BLUE, alpha=0.06, lw=0)
        q = s[(s["site"] == si) & (s["role"] == ro) & (s["interval_name"] == iv)]
        he3 = q[(q["hedge_family"] == "H3")]["he"].iloc[0]
        he1 = q[(q["hedge_family"] == "H1") & (q["fit_variant"] == "none")]["he"].iloc[0]
        ax.set_title(f"{si} {ro} grid, {iv}: HE H1 {he1:.2f}, H3 {he3:.2f}", fontsize=10)
        ax.set_ylabel("Payout per $ of protection")
        _style(ax)
    for ax in axes[1]:
        ax.set_xlabel("Year")
    axes[0, 0].legend(frameon=False, fontsize=7, loc="upper left")
    fig.suptitle("PRF payouts vs replicating hedges, 90% coverage, NCEI target (shaded: 2010-2025 test years)", fontsize=11)
    fig.tight_layout()
    fig.savefig(FIGURES / "a2_example_backtests.png", dpi=150)
    plt.close(fig)

    # 6. Farm policies: dollar payouts PRF vs hedges (out-of-sample 2010-2025, split fit).
    fb = backtest[(backtest["target_index"] == "ncei") & (backtest["role"] == "farm_policy")]
    farms = list(dict.fromkeys(fb["farm_id"]))
    fig, axes = plt.subplots(3, 4, figsize=(13, 8.2), sharex=True)
    for ax, fid in zip(axes.flat, farms):
        d = fb[(fb["farm_id"] == fid) & (fb["year"] >= TEST[0])].sort_values("year")
        p = d["policy_protection_usd"].iloc[0]
        ax.bar(d["year"], d["prf_payout"] * p / 1000, color=GRID, edgecolor=INK2, lw=0.3, label="PRF indemnity", zorder=2)
        for fam, col, lab in (("H1", "h1", "H1 ideal station index"), ("H3", "h3_split", "H3 Kalshi ladder")):
            st = FAM_STYLE[fam]
            ax.plot(d["year"], d[col] * p / 1000, color=st["color"], ls=st["ls"], marker=st["marker"], ms=3,
                    lw=1.1, label=lab, zorder=3)
        ax.set_title(fid, fontsize=9)
        _style(ax)
    for ax in axes.flat[len(farms):]:
        ax.axis("off")
    axes[1, 3].tick_params(labelbottom=True)
    for ax in axes[:, 0]:
        ax.set_ylabel("$ thousand per year")
    axes.flat[0].legend(frameon=False, fontsize=7, loc="upper left")
    fig.suptitle("Farm policies, 2010-2025 out of sample: PRF indemnity vs hedges fit on 1951-2009 (NCEI target)", fontsize=11)
    fig.tight_layout()
    fig.savefig(FIGURES / "a2_farm_policy_backtest.png", dpi=150)
    plt.close(fig)


# ---------------------------------------------------------------------------------------------
# Doc tables
# ---------------------------------------------------------------------------------------------

def _fmt(x, nd=2):
    return "" if (x is None or pd.isna(x)) else f"{x:.{nd}f}"


def doc_tables(summary: pd.DataFrame, weights: pd.DataFrame, ridge: dict, extras: dict) -> str:
    out = []
    out.append("HE values in Tables A-D are **pooled**: 1 - sum(n Var(PRF - hedge)) / sum(n Var(PRF)) over the "
               "site-grid-intervals in the cell, i.e. the share of total PRF payout variance the hedges remove. "
               "Other metrics are plain means over site-grid-intervals. \"loyo\" = leave-one-year-out 1951-2025; "
               "\"test\" = fit 1951-2009, evaluated 2010-2025; \"train\" = in-sample 1951-2009.\n")

    out.append("**Table A. All 7 PRF sites x 2 grids x 11 intervals (154 site-grid-intervals), 90% coverage, NCEI target.**\n")
    out.append("| Hedge | Eval set | HE (pooled) | HE (median) | Corr | RMSE ($/$) | Tail capture | Miss rate | False-alarm rate | Bias ($/$) | Fair cost ($/$) |")
    out.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for ev in ("train", "test", "loyo"):
        d0 = _sel(summary, eval_set=ev)
        for fam, var, lab in HEDGES:
            d = d0[(d0["hedge_family"] == fam) & (d0["fit_variant"] == var)]
            if d.empty:
                continue
            out.append(f"| {lab} | {ev} | {_fmt(pooled_he(d))} | {_fmt(d['he'].median())} | {_fmt(d['corr'].mean())} | "
                       f"{_fmt(d['rmse'].mean(), 3)} | {_fmt(d['tail_capture'].mean())} | {_fmt(d['miss_rate'].mean())} | "
                       f"{_fmt(d['false_alarm_rate'].mean())} | {_fmt(d['bias'].mean(), 3)} | {_fmt(d['fair_cost_per_dollar'].mean(), 3)} |")
    d = _sel(summary, eval_set="train")
    out.append(f"\nMean PRF payout over 1951-2009 (the PRF \"burn\"): {d['prf_mean_payout_train'].mean():.3f} per $ of protection; "
               f"mean 2026 full premium rate at these grids: {d.drop_duplicates(['site', 'role', 'interval_name'])['premium_rate_2026'].mean():.3f}.\n")

    out.append("**Table B. Pooled LOYO HE by site and grid (11 intervals, 90% coverage, NCEI).** The last three "
               "columns describe climate: correlation of the station's two-month total with the grid index "
               "(1951-2009, mean over intervals), the station's mean two-month normal, and the share of calendar "
               "months in which the 1-inch NO pays.\n")
    out.append("| Site | Grid | Distance (mi) | H1 | H1s | H2 | H3 | H3 tail capture | H3 false-alarm rate | Station-grid corr | Two-month normal (in) | P(month <= 1 in) |")
    out.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    lo = _sel(summary, prf_only=False)
    for site in SITES:
        for role in ("station", "farm"):
            d = lo[(lo["site"] == site) & (lo["role"] == role)]
            if d.empty:
                continue
            d3 = d[d["hedge_family"] == "H3"]
            p_lo = np.nanmean(np.r_[d3["p_rain_le_lowest_strike_m1"], d3["p_rain_le_lowest_strike_m2"]])
            name = site if site in STUDY_SITES else f"{site} (contrast, not PRF)"
            out.append(f"| {name} | {role} | {d['distance_to_station_mi'].iloc[0]:.0f} | "
                       + " | ".join(_fmt(_phe(d, f, v)) for f, v, _ in HEDGES)
                       + f" | {_fmt(d3['tail_capture'].mean())} | {_fmt(d3['false_alarm_rate'].mean())} | "
                       f"{_fmt(d3['station_grid_rain_corr_train'].mean())} | {_fmt(d3['station_normal_in'].mean(), 1)} | {_fmt(p_lo)} |")
    out.append("")

    out.append("**Table C. Pooled LOYO HE by interval (7 PRF sites x 2 grids, 90% coverage, NCEI).**\n")
    out.append("| Interval | H1 | H1s | H2 | H3 | H3 best site-grid | H3 worst site-grid |")
    out.append("|---|---|---|---|---|---|---|")
    lo = _sel(summary)
    for iv in INTERVAL_NAMES:
        d = lo[lo["interval_name"] == iv]
        d3 = d[d["hedge_family"] == "H3"].dropna(subset=["he"]).sort_values("he")
        best, worst = d3.iloc[-1], d3.iloc[0]
        out.append(f"| {iv} | " + " | ".join(_fmt(_phe(d, f, v)) for f, v, _ in HEDGES)
                   + f" | {best['site']} {best['role']} {best['he']:.2f} | {worst['site']} {worst['role']} {worst['he']:.2f} |")
    out.append("")

    out.append("**Table D. Robustness: pooled HE over the 154 PRF site-grid-intervals by target, coverage and evaluation set.** "
               "cpc_as_settled = hedges fit to the fixed-base CPC index, evaluated against the CPC index as RMA settled it.\n")
    out.append("| Target | Coverage | Eval set | H1 | H1s | H2 | H3 | PRF mean payout ($/$) |")
    out.append("|---|---|---|---|---|---|---|---|")
    for tgt in ("ncei", "cpc", "cpc_as_settled"):
        for cov in COVERAGES:
            for ev in ("test", "loyo"):
                d = _sel(summary, target=tgt, coverage=cov, eval_set=ev)
                if d.empty:
                    continue
                out.append(f"| {tgt} | {cov:.2f} | {ev} | " + " | ".join(_fmt(_phe(d, f, v)) for f, v, _ in HEDGES)
                           + f" | {_fmt(d[d['hedge_family'] == 'H3']['mean_prf'].mean(), 3)} |")
    out.append("")
    out.append("Sensitivities (NCEI, 90%, 154 PRF site-grid-intervals):")
    for fam in ("H2", "H3"):
        for ev in ("test", "loyo"):
            d = _sel(summary, eval_set=ev)
            fi = d[(d["hedge_family"] == fam) & (d["fit_variant"] == "free_intercept")]
            ni = d[(d["hedge_family"] == fam) & (d["fit_variant"] == "no_intercept")]
            out.append(f"- {fam} with a free-sign cash intercept, {ev}: pooled HE {_fmt(pooled_he(fi))} "
                       f"(vs {_fmt(pooled_he(ni))} without), mean RMSE {_fmt(fi['rmse'].mean(), 3)} "
                       f"(vs {_fmt(ni['rmse'].mean(), 3)}), mean bias {_fmt(fi['bias'].mean(), 3)} (vs {_fmt(ni['bias'].mean(), 3)}).")
    d = _sel(summary, eval_set="test")
    h1t = d[(d["hedge_family"] == "H1") & (d["fit_variant"] == "train_normal")]
    h1n = d[(d["hedge_family"] == "H1") & (d["fit_variant"] == "none")]
    out.append(f"- H1 with the station normal from 1951-2009 only, test: pooled HE {_fmt(pooled_he(h1t))} "
               f"(vs {_fmt(pooled_he(h1n))} with the 1951-2025 normal), mean bias {_fmt(h1t['bias'].mean(), 3)} (vs {_fmt(h1n['bias'].mean(), 3)}).")
    if ridge.get("table") is not None and not ridge["table"].empty:
        t = ridge["table"].pivot(index="ridge", columns="hedge_family", values="pooled_loyo_sse_train")
        out.append(f"- Ridge penalty chosen by pooled LOYO inside 1951-2009: H2 = {ridge['H2']:g}, H3 = {ridge['H3']:g}. "
                   "Pooled training-window LOYO sum of squared errors by penalty: "
                   + "; ".join(f"{lam:g}: H2 {row['H2']:.1f}, H3 {row['H3']:.1f}" for lam, row in t.iterrows()) + ".")
    out.append("")

    out.append("**Table E. Farm policies (allocation-weighted hedges on the farm grid at the farm's coverage, NCEI target).** "
               "Dollar columns use the farm's total policy protection.\n")
    out.append("| Farm | Coverage | Protection ($) | PRF mean ($/yr, 1951-2025) | HE H1 / H1s / H2 / H3 (LOYO) | HE H3 (test 2010-25) | "
               "H3 RMSE ($/yr, LOYO) | H3 fair cost ($/yr) | H3 tail capture (LOYO) | H3 false-alarm rate (LOYO) |")
    out.append("|---|---|---|---|---|---|---|---|---|---|")
    fp = summary[(summary["role"] == "farm_policy") & (summary["target_index"] == "ncei")]
    for fid in dict.fromkeys(fp["farm_id"]):
        d = fp[fp["farm_id"] == fid]
        lo_ = d[d["eval_set"] == "loyo"].set_index(["hedge_family", "fit_variant"])
        te = d[d["eval_set"] == "test"].set_index(["hedge_family", "fit_variant"])
        h3 = ("H3", "no_intercept")
        out.append(f"| {fid} | {d['coverage'].iloc[0]:.2f} | {d['policy_protection_usd'].iloc[0]:,.0f} | "
                   f"{lo_.loc[h3, 'mean_prf_usd']:,.0f} | "
                   + " / ".join(_fmt(lo_.loc[(f, v), "he"]) if (f, v) in lo_.index else "" for f, v, _ in HEDGES)
                   + f" | {_fmt(te.loc[h3, 'he'])} | {lo_.loc[h3, 'rmse_usd']:,.0f} | {te.loc[h3, 'fair_cost_usd']:,.0f} | "
                   f"{_fmt(lo_.loc[h3, 'tail_capture'])} | {_fmt(lo_.loc[h3, 'false_alarm_rate'])} |")
    out.append("")

    w = weights[(weights["target_index"] == "ncei") & (weights["fit_window"] == "train")]
    out.append("**Table F. Shape of the fitted ladders (NCEI, 90%, 1951-2009 fit, 154 PRF site-grid-intervals).**\n")
    out.append("| Family | Fits | Mean legs per fit | Median strike (in) | Mean total contracts per $ | Mean fair cost ($/$) |")
    out.append("|---|---|---|---|---|---|")
    for fam in ("H2", "H3"):
        d = w[(w["hedge_family"] == fam) & (w["coverage"] == 0.90) & w["is_prf_site"].astype(bool)]
        g = d.groupby(["site", "role", "interval_name"])
        out.append(f"| {fam} | {g.ngroups} | {g.size().mean():.1f} | {d['strike_in'].median():.2f} | "
                   f"{g['weight_per_dollar_protection'].sum().mean():.3f} | {g['fair_cost_per_dollar'].first().mean():.3f} |")
    out.append("")
    if extras:
        out.append("Threaded (ThreadEx) station years used in training: " +
                   "; ".join(f"{k} {v[0]}-{v[1]}" for k, v in extras.items() if v) + ". All test years 2010-2025 are single-station.")
    return "\n".join(out)


def update_doc(summary, weights, ridge, extras):
    tables = doc_tables(summary, weights, ridge, extras)
    (FIGURES.parent / "analysis").mkdir(exist_ok=True)
    if DOC.exists():
        txt = DOC.read_text(encoding="utf-8")
        if AUTO_BEGIN in txt and AUTO_END in txt:
            pre, rest = txt.split(AUTO_BEGIN, 1)
            _, post = rest.split(AUTO_END, 1)
            DOC.write_text(pre + AUTO_BEGIN + "\n" + tables + "\n" + AUTO_END + post, encoding="utf-8")
            print(f"updated tables in {DOC}")
            return
    out = FIGURES.parent.parent / "data" / "raw" / "replication_tables.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(tables, encoding="utf-8")
    print(f"doc has no AUTO markers; tables written to {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--quick", action="store_true",
                    help="skip LOYO CV, ridge search, figures and doc update; write to data/raw/replication_quick/")
    run(**vars(ap.parse_args()))
