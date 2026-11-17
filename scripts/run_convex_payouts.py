"""Convex (tail-heavy) drought payouts: does a finer or two-month ladder serve a farmer who wants
little cover at a 10% shortfall and a lot at a 70% shortfall? (doc 28, convex section)

Run from the repo root (no network, about 3 minutes):

    python scripts/run_convex_payouts.py

Targets on the PRF grid index I (100 = normal), per $1 of maximum payout:
    prf90      max(0, (90 - I) / 90)                      PRF at 90% coverage (linear, reference)
    deep50     max(0, (50 - I) / 50)                      linear, but only from a 50% shortfall
    quad       s^2,  s = max(0, (100 - I) / 100)          quadratic in the shortfall
    exp5       (e^(5 s) - 1) / (e^5 - 1)                   exponential: 0.4% at s = 0.1, 22% at s = 0.7
    digital30  1 if I <= 30                                a 70%-shortfall binary
Families: today's whole-inch monthly ladder; third-inch monthly; "fine" monthly (0.10-inch steps
below 1 inch, third-inch above); two-month total at third-inch strikes; the ideal contract (the
same payoff on the station's own two-month index, scaled).

Outputs: data/processed/exotic_convex_results.csv, exotic_convex_strike_coverage.csv, and the
tables between the "convex payout tables" AUTO markers of doc 28.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_exotic_payouts as rx  # noqa: E402

from agri_hedge import exotics as ex  # noqa: E402
from agri_hedge.config import PROCESSED  # noqa: E402
from agri_hedge.locations import ALL_SITES  # noqa: E402
from agri_hedge.prf_intervals import INTERVAL_MONTHS, INTERVAL_NAMES  # noqa: E402
from agri_hedge.replicate import fit_ladder, loyo_predictions, pooled_he, replication_metrics  # noqa: E402

TARGETS = {
    "prf90": "PRF 90% (linear from a 10% shortfall)",
    "deep50": "Linear from a 50% shortfall",
    "quad": "Quadratic in the shortfall",
    "exp5": "Exponential in the shortfall (k = 5)",
    "digital30": "Pays 1 if the index is 30 or less (70% shortfall)",
}
FAMILIES = {
    "D0_ideal": "Ideal: same payoff on the station's two-month index",
    "D1_today": "Today: monthly whole-inch",
    "D2_third": "Monthly third-inch",
    "D2_fine": "Monthly 0.10-inch below 1 in, third-inch above",
    "D4_sum_third": "Two-month total, third-inch",
}
RIDGE = {"D0_ideal": 0.0, "D1_today": rx.RIDGE_COARSE, "D2_third": rx.RIDGE_FINE, "D2_fine": rx.RIDGE_FINE,
         "D4_sum_third": rx.RIDGE_FINE}


def payoff(kind: str, index) -> np.ndarray:
    i = np.asarray(index, dtype=float)
    s = np.clip((100.0 - i) / 100.0, 0.0, None)
    if kind == "prf90":
        out = np.clip((90.0 - i) / 90.0, 0.0, None)
    elif kind == "deep50":
        out = np.clip((50.0 - i) / 50.0, 0.0, None)
    elif kind == "quad":
        out = s ** 2
    elif kind == "exp5":
        out = np.expm1(5.0 * s) / np.expm1(5.0)
    elif kind == "digital30":
        out = (i <= 30.0 + 1e-9).astype(float)
    else:
        raise ValueError(kind)
    return np.where(np.isnan(i), np.nan, out)


def fine_strikes(top: float) -> np.ndarray:
    sub = np.round(np.arange(0.1, 1.0, 0.1), 2)
    return np.unique(np.concatenate([sub, ex.strike_grid(ex.THIRD_IN, top)]))


def tick_pricing(weights, X, half_spread=rx.HALF_SPREAD, fee_rate=0.07) -> dict:
    """Like exotics.hedge_pricing but the ask is rounded up to the next whole cent (minimum 1 cent)."""
    w = np.asarray(weights, float)
    Xm = np.asarray(X, float)
    Xm = Xm[~np.isnan(Xm).any(axis=1)]
    p = Xm.mean(axis=0)
    n_pay = Xm.sum(axis=0)
    fair = float(np.sum(w * p))
    ask = np.clip(np.ceil((p + half_spread) * 100 - 1e-9) / 100, 0.01, 0.99)
    fee = fee_rate * ask * (1 - ask)
    all_in = float(np.sum(w * (ask + fee)))
    cheap = p < 0.10
    return {"fair_cost": fair, "all_in_tick": all_in, "load_tick": all_in / fair if fair > 0 else np.nan,
            "cheap_leg_share": float(np.sum((w * p)[cheap]) / fair) if fair > 0 else np.nan,
            "thin_share": float(np.sum((w * p)[n_pay < 5]) / fair) if fair > 0 else np.nan,
            "contracts": float(np.sum(w)), "n_legs": int(np.sum(w > 1e-10))}


def run_cases(monthly, idx, grids, markets) -> pd.DataFrame:
    rows = []
    t0 = time.time()
    for site in rx.PRF_SITES + ["ORD"]:
        listed = rx.listed_strikes_for(ALL_SITES[site]["kalshi_series"], markets)
        rain = monthly[site]
        for name in INTERVAL_NAMES:
            m1, m2 = INTERVAL_MONTHS[name]
            r1, r2 = rain[m1].to_numpy(float), rain[m2].to_numpy(float)
            st_idx = 100.0 * (r1 + r2) / np.nanmean(r1 + r2)
            rainm = {1: r1, 2: r2}
            designs = {}
            today = {f"NO m{m} <= {k:.2f}": ex.no_payoff(r, k) for m, r in rainm.items() for k in listed}
            designs["D1_today"] = ex.design_from_columns(today)[0]
            designs["D2_third"] = ex.design_from_columns(ex.monthly_no_ladder(rainm, ex.THIRD_IN, max_strike=max(listed)))[0]
            fine = {f"NO m{m} <= {k:.2f}": ex.no_payoff(r, k) for m, r in rainm.items() for k in fine_strikes(max(listed))}
            designs["D2_fine"] = ex.design_from_columns(fine)[0]
            designs["D4_sum_third"] = ex.design_from_columns(ex.sum_no_ladder(r1 + r2, ex.THIRD_IN))[0]
            for _, g in grids[grids["site"] == site].iterrows():
                gi = idx.loc[(g["grid_id"], name)].to_numpy(float)
                for tk in TARGETS:
                    y = payoff(tk, gi)
                    d = dict(designs)
                    d["D0_ideal"] = payoff(tk, st_idx).reshape(-1, 1)
                    for fam, X in d.items():
                        ok = ~np.isnan(y) & ~np.isnan(X).any(axis=1)
                        if ok.sum() < 20 or X.shape[1] == 0:
                            continue
                        f = fit_ladder(X[ok], y[ok], ridge=RIDGE[fam])
                        pred_lo = loyo_predictions(X, y, ridge=RIDGE[fam])
                        m = replication_metrics(y[ok], pred_lo[ok], gi[ok])
                        m_in = replication_metrics(y[ok], f.predict(X[ok]), gi[ok])
                        pr = tick_pricing(f.weights, X[ok])
                        pr0 = ex.hedge_pricing(f.weights, X[ok], half_spread=rx.HALF_SPREAD)
                        rows.append({"site": site, "role": g["role"], "interval_name": name, "target": tk, "family": fam,
                                     "he_in": m_in["he"], "var_prf_in": m_in["var_prf"], "var_resid_in": m_in["var_resid"],
                                     "p_target_pays": float(np.mean(y[ok] > 0.01)),
                                     "p_target_big": float(np.mean(y[ok] > 0.10)),
                                     "load": pr0["load"], **m, **pr})
        rx.log(f"  {site} done ({time.time() - t0:.0f}s)")
    return pd.DataFrame(rows)


def strike_coverage(monthly) -> pd.DataFrame:
    rows = []
    for site in rx.PRF_SITES + ["ORD"]:
        rain = monthly[site]
        for m in range(1, 13):
            s = rain[m].dropna()
            normal = float(s.mean())
            rows.append({"site": site, "month": m, "normal_in": normal, "k70": 0.3 * normal, "k50": 0.5 * normal,
                         "k70_below_1in": 0.3 * normal < 1.0, "k70_below_third": 0.3 * normal < 1 / 3,
                         "k50_below_1in": 0.5 * normal < 1.0,
                         "p_month_le_30pct": float((s <= 0.3 * normal).mean()),
                         "p_month_le_50pct": float((s <= 0.5 * normal).mean())})
    return pd.DataFrame(rows)


def tables(res: pd.DataFrame, cov: pd.DataFrame, idx: pd.DataFrame, grids: pd.DataFrame) -> str:
    f2 = lambda v: "" if pd.isna(v) else f"{v:.2f}"  # noqa: E731
    f3 = lambda v: "" if pd.isna(v) else f"{v:.3f}"  # noqa: E731
    pct = lambda v: "" if pd.isna(v) else f"{100 * v:.0f}%"  # noqa: E731
    prf = res[res["site"].isin(rx.PRF_SITES)]
    parts = ["Generated by `scripts/run_convex_payouts.py`. Targets are functions of the farm or station grid's PRF "
             "index per $1 of maximum payout. Load (tick) = all-in cost per $1 of expected payout when every ask is "
             "rounded up to the next whole cent (minimum 1 cent) and the taker fee is added; cheap legs = share of fair "
             "cost on legs priced under 10 cents; thin = share on legs that paid in fewer than 5 of 75 years.\n"]
    for role in ("farm", "station"):
        rows = []
        for tk, tlab in TARGETS.items():
            for fam, flab in FAMILIES.items():
                g = prf[(prf["role"] == role) & (prf["target"] == tk) & (prf["family"] == fam)]
                if g.empty:
                    continue
                he_in = 1 - (g["n_years"] * g["var_resid_in"]).sum() / (g["n_years"] * g["var_prf_in"]).sum()
                rows.append({"target": tlab, "family": flab, "p_pays": g["p_target_pays"].mean(), "p_big": g["p_target_big"].mean(),
                             "mean_target": g["mean_prf"].mean(), "he": pooled_he(g), "he_in": he_in,
                             "tail": g["tail_capture"].mean(), "fa": g["false_alarm_rate"].mean(),
                             "fair": g["fair_cost"].mean(), "load": g["load"].mean(), "load_tick": g["load_tick"].mean(),
                             "cheap": g["cheap_leg_share"].mean(), "thin": g["thin_share"].mean(), "legs": g["n_legs"].mean()})
        t = pd.DataFrame(rows)
        parts.append(f"**Table J-{role}. Convex targets at the {role} grid (7 PRF sites x 11 intervals).** P(pays) = share of "
                     "years the target pays more than 1 cent per $; P(> 10c) = share paying more than 10 cents.")
        parts.append(rx.md_table(t, ["target", "family", "p_pays", "p_big", "mean_target", "he", "he_in", "tail", "fa", "fair",
                                     "load", "load_tick", "cheap", "thin", "legs"],
                                 ["Target", "Family", "P(pays)", "P(> 10c)", "Mean payout ($/$)", "HE LOYO", "HE in-sample",
                                  "Tail capture", "False alarms", "Fair cost ($/$)", "Load", "Load (tick)", "Cheap legs", "Thin", "Legs"],
                                 {"p_pays": pct, "p_big": pct, "mean_target": f3, "he": f2, "he_in": f2, "tail": f2, "fa": f2,
                                  "fair": f3, "load": f2, "load_tick": f2, "cheap": pct, "thin": pct, "legs": lambda v: f"{v:.1f}"}))
        parts.append("")
    # by site, exp5 target, farm grid
    rows = []
    for site in rx.PRF_SITES + ["ORD"]:
        g = res[(res["site"] == site) & (res["role"] == "farm") & (res["target"] == "exp5")]
        row = {"site": site}
        for fam in FAMILIES:
            row[fam] = pooled_he(g[g["family"] == fam])
        row["p_big"] = g[g["family"] == "D1_today"]["p_target_big"].mean()
        rows.append(row)
    parts.append("**Table K. Exponential target (k = 5) at the farm grid, pooled LOYO HE by site.** P(> 10c) = share of years "
                 "the target pays more than 10 cents per $ of maximum payout.")
    parts.append(rx.md_table(pd.DataFrame(rows), ["site"] + list(FAMILIES) + ["p_big"],
                             ["Site", "Ideal", "Today", "Third-inch", "Fine sub-inch", "Two-month third", "P(> 10c)"],
                             {**{f: f2 for f in FAMILIES}, "p_big": pct}))
    parts.append("")
    # strike coverage
    c = cov[cov["site"].isin(rx.PRF_SITES + ["ORD"])]
    g = c.groupby("site").agg(normal=("normal_in", "mean"), k70_below_1=("k70_below_1in", "sum"), k70_below_third=("k70_below_third", "sum"),
                              k50_below_1=("k50_below_1in", "sum"), p30=("p_month_le_30pct", "mean"), p50=("p_month_le_50pct", "mean")).reset_index()
    parts.append("**Table L. Where the tail strikes sit.** For each station, the number of calendar months (of 12) in which a "
                 "70% monthly shortfall (0.3 x the month's mean) falls below today's lowest strike (1 inch) and below the lowest "
                 "third-inch strike (0.33 inch), and the same for a 50% shortfall; plus the share of months on record at or below "
                 "30% and 50% of the month's mean (1951-2025).")
    parts.append(rx.md_table(g, ["site", "normal", "k70_below_1", "k70_below_third", "k50_below_1", "p30", "p50"],
                             ["Station", "Mean monthly rain (in)", "Months with 70% strike < 1 in", "< 0.33 in",
                              "Months with 50% strike < 1 in", "P(month <= 30% of mean)", "P(<= 50%)"],
                             {"normal": f2, "k70_below_1": lambda v: f"{int(v)}", "k70_below_third": lambda v: f"{int(v)}",
                              "k50_below_1": lambda v: f"{int(v)}", "p30": pct, "p50": pct}))
    parts.append("")
    # frequency of deep shortfalls on the farm grids
    rows = []
    for _, g in grids[grids["role"] == "farm"].iterrows():
        vals = idx.loc[g["grid_id"]].to_numpy(float)
        rows.append({"site": g["site"], "grid": g["grid_id"], "p_le_30": float(np.nanmean(vals <= 30)),
                     "p_le_50": float(np.nanmean(vals <= 50)), "p_le_70": float(np.nanmean(vals <= 70)),
                     "p_le_90": float(np.nanmean(vals <= 90))})
    parts.append("**Table M. How often the farm grid's two-month index falls below 30, 50, 70 and 90 (all 11 intervals, 1951-2025).**")
    parts.append(rx.md_table(pd.DataFrame(rows), ["site", "grid", "p_le_30", "p_le_50", "p_le_70", "p_le_90"],
                             ["Site", "Farm grid", "Index <= 30", "<= 50", "<= 70", "<= 90"],
                             {"p_le_30": pct, "p_le_50": pct, "p_le_70": pct, "p_le_90": pct, "grid": lambda v: f"{int(v)}"}))
    return "\n".join(parts)


def main():
    monthly = rx.load_monthly(rx.ALL_STUDY)
    grids = rx.load_grids()
    idx = rx.load_index(grids["grid_id"].tolist())
    markets = pd.read_parquet(PROCESSED / "kalshi_rain_markets.parquet",
                              columns=["series_ticker", "floor_strike", "is_single_month", "strike_type"])
    markets = markets[markets["is_single_month"].astype(bool) & (markets["strike_type"] == "greater")]
    rx.log("convex study ...")
    res = run_cases(monthly, idx, grids, markets)
    res.to_csv(PROCESSED / "exotic_convex_results.csv", index=False)
    cov = strike_coverage(monthly)
    cov.to_csv(PROCESSED / "exotic_convex_strike_coverage.csv", index=False)
    text = tables(res, cov, idx, grids)
    rx.replace_between_markers(rx.DOC, "<!-- BEGIN AUTO: convex payout tables (scripts/run_convex_payouts.py) -->",
                               "<!-- END AUTO: convex payout tables (scripts/run_convex_payouts.py) -->",
                               text, PROCESSED / "exotic_convex_tables.md")
    prf = res[res["site"].isin(rx.PRF_SITES) & (res["role"] == "farm")]
    for tk in TARGETS:
        line = []
        for fam in FAMILIES:
            g = prf[(prf["target"] == tk) & (prf["family"] == fam)]
            line.append(f"{fam} {pooled_he(g):.2f} (load {g['load'].mean():.2f}/tick {g['load_tick'].mean():.2f}, thin {g['thin_share'].mean():.0%})")
        rx.log(tk + ": " + "; ".join(line))


if __name__ == "__main__":
    main()
