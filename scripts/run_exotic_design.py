"""Doc 24: contract design beyond the fixed shapes of doc 23.

Parts (each saves a CSV in data/processed; parts not named in --only= are loaded from their CSV):
  equal      A. equal-premium comparison, farm-settled, 36 insured windows: S4, S5 at equal maximum payout
                and S5 at the linear shape's premium (the depth cap binds harder on a bigger contract)
  holdout    B. holdout term sheet, 60 open months x 8 shapes: bin payouts fitted on 1951-2000, scored on 2001-2025
  optimal    C. the utility-optimal step payout for 132 farm-months (all 12 months of the 11 farms), over a grid of
                risk aversion x load x wealth; the certainty-equivalent share each fixed shape captures (base case);
                a 2001-2025 holdout of the base case
  execution  D. the seven study stations, Nov 2026, every shape at the same maximum payout and at the linear
                product's premium on the 2026-11-02 book (platform.exotic_compare)

Usage: python scripts/run_exotic_design.py [--quick] [--tables-only] [--only=equal,holdout,optimal,execution]
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_exotic_payouts import (BOOK, COLORS, MAX_PAYOUT, MONTH_SHAPES, SHAPES, SHORT, fit_scores,  # noqa: E402
                                loss_params_for)

from agri_hedge import design as dg  # noqa: E402
from agri_hedge import exotic as ex  # noqa: E402
from agri_hedge import hedge_builder as hb  # noqa: E402
from agri_hedge import optimizer as op  # noqa: E402
from agri_hedge import platform as pf  # noqa: E402
from agri_hedge.config import DOCS, FIGURES, PROCESSED  # noqa: E402
from agri_hedge.docs_util import write_auto_block  # noqa: E402
from agri_hedge.hedge_builder import CoverageRequest, Window  # noqa: E402

DOC = DOCS / "analysis" / "24_contract_design.md"
TAG = "contract design tables (scripts/run_exotic_design.py)"
EXEC_STATIONS = ["DFW", "OKC", "SGF", "SAT", "DEN", "ABQ", "TPA"]
EXEC_TODAY = date(2026, 10, 20)          # so November 2026 is the listed month on the saved book
GAMMAS = (1.0, 2.0, 4.0)
LOADS = (0.0, 0.1, 0.2, 0.3)
WEALTHS = (1.25, 2.0, 4.0)
BASE = (dg.DEFAULT_GAMMA, dg.DEFAULT_LOAD, dg.DEFAULT_WEALTH)
FIXED = ("linear", "layered", "convex2", "exponential", "tiers", "capped", "loss")
HOLDOUT_CUT = 2000
SAVED = {"equal": "m2_design_equal_premium.csv", "holdout": "m2_design_holdout.csv",
         "optimal": "m2_design_optimal.csv", "ce": "m2_design_shape_ce.csv", "execution": "m2_design_execution.csv"}


def _shape_fn(shape, normal_m, cov, lp):
    return lambda rr, s=shape: float(ex.payoff(s, np.array([100.0 * rr / normal_m]), cov, lp)[0])


# ---------------------------------------------------------------------------------------------
# A. equal premium (farm-settled, insured windows)
# ---------------------------------------------------------------------------------------------

def equal_premium_study(farms) -> pd.DataFrame:
    rows = []
    st = hb.station_table().set_index("station_key")
    for F in farms:
        r = F["request"]
        series = st.loc[r.station_key, "series_ticker"]
        depth_no, _ = ex.book_depth_by_side(series, r.station_key, "NO", BOOK)
        depth_yes, _ = ex.book_depth_by_side(series, r.station_key, "YES", BOOK)
        lp = loss_params_for(F)
        for w in r.windows:
            prot = F["protection"] * w.share
            p = hb.build_problem(CoverageRequest(r.lat, r.lon, [Window(w.months, 1.0)], r.coverage, prot,
                                                 station_key=r.station_key, strikes="kalshi", grid_id=r.grid_id))
            kal = ex.kalshi_strikes_for(p)
            lad = {"NO": ex.ladder_cols(p, kal, ("NO",)), "BOTH": ex.ladder_cols(p, kal, ("NO", "YES"))}
            y_lin = ex.shape_target(p, "linear", lp)
            for shape in SHAPES:
                X, lab, q = lad["BOTH" if shape == "both_tails" else "NO"]
                y = ex.shape_target(p, shape, lp)
                mask = ~np.isnan(y) & ~np.isnan(y_lin) & ~np.isnan(X).any(axis=1)
                if mask.sum() < 30 or np.var(y[mask]) == 0 or np.mean(y[mask]) <= 0:
                    continue
                prem = float(np.mean(y[mask]))
                k = float(np.mean(y_lin[mask]) / prem)
                caps = ex.caps_for(lab, depth_no, depth_yes)
                r4 = fit_scores(X, y, mask, q, prot)
                r5 = fit_scores(X, y, mask, q, prot, caps=caps)
                r5e = fit_scores(X, k * y, mask, q, prot * k, caps=caps)
                rows.append({"farm_id": F["farm_id"], "site": F["site"], "window": w.label, "shape": shape,
                             "max_payout": prot, "fair_premium_usd": prem, "premium_scale": k,
                             "max_payout_equal_premium": prot * k, "n": int(mask.sum()),
                             "he_loyo_S4": r4["he_loyo"], "he_loyo_S5": r5["he_loyo"], "he_loyo_S5_equal_premium": r5e["he_loyo"],
                             "var_y_prem": float(np.var(y[mask] / prem)),
                             "var_resid_S5_prem": r5["var_resid_loyo"] * (prot / prem) ** 2,
                             "var_resid_S5eq_prem": r5e["var_resid_loyo"] * (prot / prem) ** 2,
                             "contracts_per_premium_dollar": r4["contracts"] / prem,
                             "contracts_per_max_payout_dollar": r4["contracts"] / prot,
                             "capital95_per_premium_dollar": r4["capital95_loyo"] * prot / prem,
                             "capital95_share_of_max_payout": r4["capital95_loyo"],
                             "tail_capture_loyo": r4["tail_capture_loyo"]})
        print(F["farm_id"], "equal-premium done", flush=True)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------------------------
# B. holdout term sheet (exchange-settled, open months)
# ---------------------------------------------------------------------------------------------

def holdout_study(farms) -> pd.DataFrame:
    rows = []
    for F in farms:
        r = F["request"]
        lp = loss_params_for(F)
        gap = F["protection"] / 6
        covered = {m for w in r.windows for m in w.months}
        for m in sorted(set(range(1, 13)) - covered):
            p = hb.build_problem(CoverageRequest(r.lat, r.lon, [Window((m,), 1.0)], r.coverage, gap,
                                                 station_key=r.station_key, strikes="kalshi", grid_id=r.grid_id))
            key = r.station_key
            rain_m = hb.station_rain(key).reindex(p.years)[m].to_numpy(float)
            gidx = ex.gauge_month_index(key, m, p.years)
            normal_m = float(np.nanmean(rain_m) / np.nanmean(gidx) * 100.0)
            kal = ex.kalshi_strikes_for(p)(m)
            tr, te = dg.split_years(p.years, HOLDOUT_CUT)
            for shape in MONTH_SHAPES:
                y = ex.shape_target(p, shape, lp)
                f_g = ex.payoff(shape, gidx, r.coverage, lp)
                sfn = _shape_fn(shape, normal_m, r.coverage, lp)
                mask = ~np.isnan(y) & ~np.isnan(f_g) & ~np.isnan(rain_m)
                if (mask & tr).sum() < 20 or (mask & te).sum() < 10 or np.var(y[mask & te]) == 0:
                    continue
                v_all = ex.binned_values(f_g[mask], rain_m[mask], kal, sfn)
                v_tr = ex.binned_values(f_g[mask & tr], rain_m[mask & tr], kal, sfn)

                def r2(v, sel):
                    h = ex.span_step(v, kal).payout(rain_m[sel])
                    vf = np.var(f_g[sel])
                    return float(1 - np.var(f_g[sel] - h) / vf) if vf > 0 else np.nan

                def he(v, sel):
                    h = gap * ex.span_step(v, kal).payout(rain_m[sel])
                    return op.hedge_effectiveness(y[sel], h) if np.var(y[sel]) > 0 else np.nan

                rows.append({"farm_id": F["farm_id"], "site": F["site"], "month": hb.MONTH_ABBR[m - 1], "shape": shape,
                             "n_train": int((mask & tr).sum()), "n_test": int((mask & te).sum()),
                             "binning_r2_all": r2(v_all, mask), "binning_r2_test_trainbins": r2(v_tr, mask & te),
                             "binning_r2_test_allbins": r2(v_all, mask & te),
                             "he_exchange_all": he(v_all, mask), "he_exchange_test_trainbins": he(v_tr, mask & te),
                             "he_exchange_test_allbins": he(v_all, mask & te),
                             "max_abs_bin_change": float(np.max(np.abs(v_all - v_tr))),
                             "fair_premium_all": float(np.mean(ex.span_step(v_all, kal).payout(rain_m[mask]))),
                             "fair_premium_trainbins_on_test": float(np.mean(ex.span_step(v_tr, kal).payout(rain_m[mask & te])))})
        print(F["farm_id"], "holdout done", flush=True)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------------------------
# C. the utility-optimal payout
# ---------------------------------------------------------------------------------------------

def optimal_study(farms) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows, ce_rows = [], []
    for F in farms:
        r = F["request"]
        lp = loss_params_for(F)
        covered = {m for w in r.windows for m in w.months}
        key = r.station_key
        for m in range(1, 13):
            kind = "insured" if m in covered else "open"
            p = hb.build_problem(CoverageRequest(r.lat, r.lon, [Window((m,), 1.0)], r.coverage, 1.0,
                                                 station_key=key, strikes="kalshi", grid_id=r.grid_id))
            rain_m = hb.station_rain(key).reindex(p.years)[m].to_numpy(float)
            gidx = ex.gauge_month_index(key, m, p.years)
            normal_m = float(np.nanmean(rain_m) / np.nanmean(gidx) * 100.0)
            kal = ex.kalshi_strikes_for(p)(m)
            nb = len(kal) + 1
            for target in ("linear", "loss"):
                loss = ex.shape_target(p, target, lp)
                mask = ~np.isnan(loss) & ~np.isnan(rain_m)
                if mask.sum() < 30 or np.var(loss[mask]) == 0:
                    continue
                L, Rm, G = loss[mask], rain_m[mask], gidx[mask]
                bins = ex.rain_bins(Rm, kal)
                fixed = {s: ex.binned_values(ex.payoff(s, G, r.coverage, lp), Rm, kal, _shape_fn(s, normal_m, r.coverage, lp))
                         for s in FIXED}
                base_row = {"farm_id": F["farm_id"], "site": F["site"], "month": hb.MONTH_ABBR[m - 1], "month_number": m,
                            "kind": kind, "target": target, "n": int(mask.sum()),
                            "strikes": ",".join(f"{k:g}" for k in kal)}
                for g in GAMMAS:
                    for ld in LOADS:
                        for W in WEALTHS:
                            o = dg.optimal_step_payout(L, bins, nb, g, ld, W)
                            v = o.values
                            rows.append({**base_row, "gamma": g, "load": ld, "wealth": W,
                                         "bins_paying": int((v > 1e-6).sum()), "max_payout_per_dollar": o.max_payout,
                                         "fair_premium_per_dollar": o.fair_premium, "premium_per_dollar": o.premium,
                                         "ce_gain_pct": 100 * o.ce_gain, "convexity_ratio": ex.convexity_ratio(v),
                                         "v0": v[0], "v1": v[1] if nb > 1 else np.nan, "v2": v[2] if nb > 2 else np.nan,
                                         "step_values": ",".join(f"{x:.4f}" for x in v),
                                         "he_vs_farm": op.hedge_effectiveness(L, v[bins]) if o.max_payout > 0 else np.nan,
                                         "converged": o.converged})
                g, ld, W = BASE
                tab = dg.ce_shares(L, bins, nb, fixed, g, ld, W)
                tr, te = dg.split_years(p.years[mask], HOLDOUT_CUT)
                test = {}
                if tr.sum() >= 20 and te.sum() >= 10:
                    f_tr = dg.bin_frequencies(bins[tr], nb)
                    o_tr = dg.optimal_step_payout(L[tr], bins[tr], nb, g, ld, W)
                    test["optimal"] = dg.evaluate_payout(o_tr.values, L[te], bins[te], g, ld, W, freq=f_tr)["ce_gain"]
                    fixed_tr = {s: ex.binned_values(ex.payoff(s, G[tr], r.coverage, lp), Rm[tr], kal,
                                                    _shape_fn(s, normal_m, r.coverage, lp)) for s in FIXED}
                    for s in FIXED:
                        sc = dg.scale_for_utility(fixed_tr[s], L[tr], bins[tr], g, ld, W)
                        test[s] = dg.evaluate_payout(sc.values, L[te], bins[te], g, ld, W, freq=f_tr)["ce_gain"]
                for s, d in tab.items():
                    ce_rows.append({**base_row, "shape": s, "ce_gain_pct": 100 * d["ce_gain"], "share": d["share"],
                                    "max_payout_per_dollar": d["max_payout"], "premium_per_dollar": d["premium"],
                                    "ce_gain_test_pct": 100 * test[s] if s in test else np.nan})
        print(F["farm_id"], "optimal done", flush=True)
    return pd.DataFrame(rows), pd.DataFrame(ce_rows)


# ---------------------------------------------------------------------------------------------
# D. execution at equal premium (exchange-settled, saved book)
# ---------------------------------------------------------------------------------------------

def execution_study(farms) -> pd.DataFrame:
    live = pf.LiveQuotes(offline=True)
    rows = []
    for key in EXEC_STATIONS:
        F = next(F for F in farms if F["site"] == key)
        r = F["request"]
        c = pf.exotic_compare({"lat": r.lat, "lon": r.lon, "station_key": key, "month": 11, "max_payout": MAX_PAYOUT,
                               "price_source": "auto"}, live, EXEC_TODAY)
        for row in c["rows"]:
            rows.append({"station": key, "contract_month": c["product"]["contract_month"],
                         **{k: row[k] for k in ("shape", "fair_premium_usd", "contracts", "fill_share",
                                                "largest_fillable_max_payout_usd", "max_payout_equal_premium_usd",
                                                "fill_share_equal_premium", "farm_he", "tail_capture",
                                                "ce_gain_pct_of_value", "ce_share_of_optimal", "utility_best_max_payout_usd")},
                         "recommended": c["recommendation"]["shape"], "best_fixed": c["recommendation"]["best_fixed_shape"]})
        print(key, "execution done", flush=True)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------------------------
# main, figures, tables
# ---------------------------------------------------------------------------------------------

def main(argv=None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    quick = "--quick" in args
    parts = {"equal", "holdout", "optimal", "execution"}
    for a in args:
        if a.startswith("--only="):
            parts = set(a.split("=", 1)[1].split(","))
    if "--tables-only" in args:
        parts = set()
    farms = hb.load_farm_requests()
    if quick:
        farms = farms[:2]
    out = {}
    if "equal" in parts:
        out["equal"] = equal_premium_study(farms)
        out["equal"].to_csv(PROCESSED / SAVED["equal"], index=False)
    if "holdout" in parts:
        out["holdout"] = holdout_study(farms)
        out["holdout"].to_csv(PROCESSED / SAVED["holdout"], index=False)
    if "optimal" in parts:
        out["optimal"], out["ce"] = optimal_study(farms)
        out["optimal"].to_csv(PROCESSED / SAVED["optimal"], index=False)
        out["ce"].to_csv(PROCESSED / SAVED["ce"], index=False)
    if "execution" in parts:
        out["execution"] = execution_study(hb.load_farm_requests())
        out["execution"].to_csv(PROCESSED / SAVED["execution"], index=False)
    for k, f in SAVED.items():
        if k not in out:
            out[k] = pd.read_csv(PROCESSED / f)
    figures(out)
    t = tables(out)
    if not quick:
        write_auto_block(DOC, TAG, t)
    print(t)
    return 0


def pooled_he(d: pd.DataFrame, resid_col: str) -> float:
    return float(1 - d[resid_col].sum() / d["var_y_prem"].sum()) if len(d) and d["var_y_prem"].sum() > 0 else np.nan


def figures(out: dict) -> None:
    O, CE, EQ = out["optimal"], out["ce"], out["equal"]
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.6))
    ax = axes[0]
    d = O[(O["farm_id"] == "DFW_hay") & (O["target"] == "linear") & (O["gamma"] == BASE[0]) & (O["wealth"] == BASE[2])]
    for mon, c in (("Nov", "#2a6f97"), ("Jun", "#c1121f")):
        for ld, ls in ((0.0, "-"), (0.1, "--"), (0.2, ":")):
            g = d[(d["month"] == mon) & (d["load"] == ld)]
            if g.empty:
                continue
            vals = np.array([float(v) for v in g["step_values"].iloc[0].split(",")])
            ks = [float(k) for k in g["strikes"].iloc[0].split(",")]
            edges = [0.0] + ks + [ks[-1] + 1]
            ax.step(edges, np.concatenate([vals[:1], vals]), where="pre", color=c, ls=ls, lw=1.6,
                    label=f"{mon}, load {ld:.0%}")
    ax.set_xlabel("Station monthly rain (inches)")
    ax.set_ylabel("Optimal payout per USD 1 of the month's value")
    ax.set_title("A. DFW_hay: the utility-optimal payout shrinks to the\ndeepest bins as the load rises (gamma 2)", fontsize=10)
    ax.legend(fontsize=7)
    ax.grid(alpha=0.3)
    ax = axes[1]
    base = CE[(CE["target"] == "linear")]
    med = base.groupby("shape")["share"].median().reindex(list(FIXED))
    ax.bar(np.arange(len(med)), med.to_numpy(), color=[COLORS[s] for s in med.index])
    ax.set_xticks(np.arange(len(med)), [SHORT[s] for s in med.index], fontsize=7, rotation=15)
    ax.set_ylabel("Share of the optimum's certainty-equivalent gain (median)")
    ax.set_ylim(0, 1.05)
    ax.set_title(f"B. How much of the best contract each fixed shape captures\n(132 farm-months, gamma {BASE[0]:g}, load {BASE[1]:.0%})", fontsize=10)
    ax.grid(axis="y", alpha=0.3)
    ax = axes[2]
    labels = [s for s in SHAPES if s in set(EQ["shape"])]
    he_mp = [pooled_he(EQ[EQ["shape"] == s], "var_resid_S5_prem") for s in labels]
    he_eq = [pooled_he(EQ[EQ["shape"] == s], "var_resid_S5eq_prem") for s in labels]
    xs = np.arange(len(labels))
    ax.bar(xs - 0.2, he_mp, 0.4, color="#8d99ae", label="same maximum payout")
    ax.bar(xs + 0.2, he_eq, 0.4, color="#2a6f97", label="same premium as linear")
    ax.set_xticks(xs, [SHORT[s] for s in labels], fontsize=7, rotation=20)
    ax.set_ylabel("Pooled HE at today's depth (LOYO)")
    ax.set_title("C. Farm-settled, at today's order-book depth:\nthe convex advantage is a same-payout artefact", fontsize=10)
    ax.legend(fontsize=7)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIGURES / "m2_design_optimal.png", dpi=150)
    plt.close(fig)


def _f(v, nd=2):
    return "" if v is None or pd.isna(v) else f"{v:,.{nd}f}"


def _pct(v):
    return "" if v is None or pd.isna(v) else f"{v:.0%}"


def tables(out: dict) -> str:
    EQ, HO, O, CE, EX = out["equal"], out["holdout"], out["optimal"], out["ce"], out["execution"]
    lin = EQ[EQ["shape"] == "linear"].set_index(["farm_id", "window"])
    res = ["### A. Equal premium: farm-settled hedges at today's depth, 36 insured windows", "",
           "Each shape is first sized at the same maximum payout as doc 23 (S5), then scaled so its fair premium equals the "
           "linear shape's (S5 at equal premium). Pooled HE weights windows by payout variance per $1 of premium. "
           "Contracts and capital are per $1 of premium.", "",
           "| Shape | Premium scale (median) | Contracts per $1 premium | Pooled S5 HE, same max payout | Pooled S5 HE, same premium "
           "| Windows beating linear at same premium | Issuer capital per $1 premium (95th pct) |", "|---|---|---|---|---|---|---|"]
    for s in SHAPES:
        d = EQ[EQ["shape"] == s]
        if d.empty:
            continue
        j = d.set_index(["farm_id", "window"]).join(lin[["he_loyo_S5_equal_premium"]].rename(
            columns={"he_loyo_S5_equal_premium": "he_loyo_S5_equal_premium_lin"}))
        beats = int((j["he_loyo_S5_equal_premium"] > j["he_loyo_S5_equal_premium_lin"] + 1e-9).sum())
        res.append(f"| {ex.SHAPES[s]} | {_f(d['premium_scale'].median())} | {_f(d['contracts_per_premium_dollar'].median(), 1)} "
                   f"| {_f(pooled_he(d, 'var_resid_S5_prem'))} | {_f(pooled_he(d, 'var_resid_S5eq_prem'))} | {beats} of {len(j)} "
                   f"| {_f(d['capital95_per_premium_dollar'].median(), 1)} |")
    res += ["", "### B. Holdout term sheet: bins fitted on 1951-2000, scored on 2001-2025 (60 open months)", "",
            "Binning R2 = share of the smooth shape's variance the step function reproduces on the gauge. Exchange-settled HE = "
            "how well the product tracks the farm-grid payoff. 'All years' is doc 23's in-sample number; 'test' scores 2001-2025 "
            "with bins fitted on 1951-2000.", "",
            "| Shape | Binning R2, all years | Binning R2, test | Exchange HE, all years | Exchange HE, test | "
            "Largest bin payout change per $1 (median) | Premium change, test vs all (median) |", "|---|---|---|---|---|---|---|"]
    for s in MONTH_SHAPES:
        d = HO[HO["shape"] == s]
        if d.empty:
            continue
        dp = (d["fair_premium_trainbins_on_test"] - d["fair_premium_all"]) / d["fair_premium_all"]
        res.append(f"| {ex.SHAPES[s]} | {_f(d['binning_r2_all'].median())} | {_f(d['binning_r2_test_trainbins'].median())} "
                   f"| {_f(d['he_exchange_all'].median())} | {_f(d['he_exchange_test_trainbins'].median())} "
                   f"| {_f(d['max_abs_bin_change'].median(), 3)} | {_pct(dp.median())} |")
    res += ["", "### C. The utility-optimal payout: what a CRRA farmer buys on the station's ladder (132 farm-months, PRF-linear farm loss)", "",
            "Wealth = 2 x the month's insured value. Bins paying = rain bins with a positive payout (the ladder has 7-9). "
            "Premium and CE gain are per $1 of the month's insured value; the CE gain is what the farmer would pay for the cover "
            "beyond its premium.", "",
            "| Risk aversion | Load | Bins paying (median) | Months with 3+ bins paying | Premium per $1 of value (median) "
            "| CE gain, % of value (median) | Months buying nothing | Convexity ratio (median) | HE vs farm (median) |",
            "|---|---|---|---|---|---|---|---|---|"]
    ol = O[(O["target"] == "linear") & (O["wealth"] == BASE[2])]
    for g in GAMMAS:
        for ld in LOADS:
            d = ol[(ol["gamma"] == g) & (ol["load"] == ld)]
            if d.empty:
                continue
            cr = d["convexity_ratio"].replace([np.inf, -np.inf], np.nan)
            res.append(f"| {g:g} | {ld:.0%} | {d['bins_paying'].median():.0f} | {int((d['bins_paying'] >= 3).sum())} of {len(d)} "
                       f"| {_pct(d['premium_per_dollar'].median())} | {_f(d['ce_gain_pct'].median())} "
                       f"| {int((d['max_payout_per_dollar'] <= 1e-6).sum())} | {_f(cr.median())} | {_f(d['he_vs_farm'].median())} |")
    ow = O[(O["target"] == "linear") & (O["gamma"] == BASE[0]) & (O["load"] == BASE[1])]
    res += ["", "Wealth sensitivity at risk aversion 2 and a 20% load: bins paying (median) and premium per $1 of value for wealth "
            + "; ".join(f"{W:g}x: {ow[ow['wealth'] == W]['bins_paying'].median():.0f} bins, {_pct(ow[ow['wealth'] == W]['premium_per_dollar'].median())}"
                        for W in WEALTHS if not ow[ow["wealth"] == W].empty) + "."]
    res += ["", f"### D. Fixed shapes against the optimum (risk aversion {BASE[0]:g}, load {BASE[1]:.0%}, wealth {BASE[2]:g}x): "
            "certainty-equivalent gain at each shape's best size", "",
            "Share = the shape's CE gain / the optimum's. 'Best fixed shape' counts the farm-months where the shape has the "
            "highest share among the seven. Test = CE gain on 2001-2025 with sizes and bins chosen on 1951-2000 (25 test years "
            "make it noisy: the mean is shown, with the share of farm-months where the gain stayed positive and where the shape "
            "beat the optimum out of sample).", "",
            "| Shape | Share of optimum (median) | Best fixed shape in | Best size, max payout per $1 of value (median) "
            "| Premium per $1 of value (median) | CE gain, % of value (median) | Test CE gain, % of value (mean) "
            "| Test gain positive | Beats the optimum on test |",
            "|---|---|---|---|---|---|---|---|---|"]
    for target in ("linear", "loss"):
        cl = CE[CE["target"] == target]
        fixed_only = cl[(cl["shape"] != "optimal") & cl["share"].notna()]     # NaN share = the farmer buys nothing there
        best = fixed_only.loc[fixed_only.groupby(["farm_id", "month"])["share"].idxmax()]["shape"].value_counts()
        n_fm = fixed_only.groupby(["farm_id", "month"]).ngroups
        res.append(f"| **Farm loss: {'PRF linear payoff' if target == 'linear' else 'doc-13 loss curve'}** | | | | | | | | |")
        opt_test = cl[cl["shape"] == "optimal"].set_index(["farm_id", "month"])["ce_gain_test_pct"]
        for s in ("optimal",) + FIXED:
            d = cl[cl["shape"] == s]
            if d.empty:
                continue
            lab = "Utility optimum" if s == "optimal" else ex.SHAPES[s]
            t = d.set_index(["farm_id", "month"])["ce_gain_test_pct"].dropna()
            beats = int((t > opt_test.reindex(t.index) + 1e-9).sum())
            res.append(f"| {lab} | {_f(d['share'].median())} | {'' if s == 'optimal' else f'{int(best.get(s, 0))} of {n_fm}'} "
                       f"| {_f(d['max_payout_per_dollar'].median())} | {_pct(d['premium_per_dollar'].median())} "
                       f"| {_f(d['ce_gain_pct'].median())} | {_f(t.mean())} | {int((t > 0).sum())} of {len(t)} "
                       f"| {'' if s == 'optimal' else f'{beats} of {len(t)}'} |")
    res += ["", f"### E. Exchange-settled, Nov 2026, ${MAX_PAYOUT:,.0f} maximum payout on the 2026-11-02 book: fill at equal payout and at equal premium", "",
            "Equal premium = each shape scaled to the linear product's fair premium at the same station. Utility share as in D "
            "(risk aversion 2, load 20%) for the study farm at each site.", "",
            "| Station | Shape | Fair premium | Filled, same max payout | Max payout at linear's premium | Filled, same premium "
            "| Largest fillable max payout | Farm HE | Utility share | Best size (utility) |", "|---|---|---|---|---|---|---|---|---|---|"]
    for key, g in EX.groupby("station", sort=False):
        for _, r in g.iterrows():
            lab = "Utility optimum" if r["shape"] == "optimal" else ex.SHAPES.get(r["shape"], r["shape"])
            res.append(f"| {key} | {lab} | ${_f(r['fair_premium_usd'], 0)} | {_pct(r['fill_share'])} | ${_f(r['max_payout_equal_premium_usd'], 0)} "
                       f"| {_pct(r['fill_share_equal_premium'])} | ${_f(r['largest_fillable_max_payout_usd'], 0)} | {_f(r['farm_he'])} "
                       f"| {_f(r['ce_share_of_optimal'])} | ${_f(r['utility_best_max_payout_usd'], 0)} |")
    return "\n".join(res)


if __name__ == "__main__":
    sys.exit(main())
