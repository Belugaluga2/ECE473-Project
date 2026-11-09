"""Exotic insurance payoffs built from Kalshi rain ladders (doc 23).

Run from the repo root:   python scripts/run_exotic_payouts.py  [--quick] [--only=months,execution] [--tables-only]

A. Insured windows: the 36 two-month PRF intervals of the 11 farms, nine payoff shapes (`exotic.SHAPES`),
   each hedged with the lowest-error fit after every real-world restriction in turn:
   S0 perfect -> S1 geography -> S2 settlement source -> S3 monthly 0.25-inch ladders -> S4 Kalshi's
   whole-inch strikes -> S5 order-book depth (2026-11-02), plus P6 = S4 with proposed "both months dry"
   combo contracts. Scored in sample and leave-one-year-out (LOYO); at S4 also the tail capture, the
   capital a farm-settled issuer needs and the cost per $1 of expected payout.
B. Open months: the 60 single farm-months PRF leaves uncovered, as single-month exotic cover. On the
   station's own rain every single-month shape is spanned exactly up to the strike grid, so this part
   measures the binning loss at Kalshi, half-inch and quarter-inch strikes, the farmer's basis risk if
   the product settles on the station, and the issuer's hedge error if it settles on the farm.
C. Executable products: exchange-settled November 2026 contracts at the seven study stations, built in
   closed form from the whole-inch ladder and filled against the 2026-11-02 order books: fair premium,
   spread, fee, capital, fill share, and the largest size the book fills.
D. The data-optimal payout: the lowest-error ladder fit to the farm's doc-13 loss curve, compared with
   the fit to PRF's linear payout: is the payout the data ask for convex?

Outputs: data/processed/m2_exotic_windows.csv, m2_exotic_months.csv, m2_exotic_execution.csv,
m2_exotic_execution_legs.csv, m2_exotic_optimal_shape.csv; docs/figures/m2_exotic_shapes.png,
m2_exotic_waterfall.png, m2_exotic_execution.png; AUTO tables in docs/analysis/23_exotic_payouts.md.
No network. The full run takes several minutes.
"""
from __future__ import annotations

import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from agri_hedge import exotic as ex  # noqa: E402
from agri_hedge import hedge_builder as hb  # noqa: E402
from agri_hedge import optimizer as op  # noqa: E402
from agri_hedge.config import DOCS, FIGURES, PROCESSED  # noqa: E402
from agri_hedge.docs_util import write_auto_block  # noqa: E402
from agri_hedge.hedge_builder import FAIR_WINDOW, NORMAL_YEARS, CoverageRequest, Window  # noqa: E402
from agri_hedge.loss_model import build_farm_model  # noqa: E402
from agri_hedge.pricing import leg_probability  # noqa: E402

DOC = DOCS / "analysis" / "23_exotic_payouts.md"
BOOK = PROCESSED / "kalshi_rain_orderbook_summary_20261102.csv"
STEPS = [("S0", "Perfect: the shape on the farm's own grid"),
         ("S1", "Geography: the shape on the station's grid"),
         ("S2", "Settlement source: the shape on the station gauge"),
         ("S3", "Monthly contracts (0.25-inch strikes)"),
         ("S4", "Kalshi's listed strikes (whole inches)"),
         ("S5", "Order-book depth (Nov 2026, post-rewards)")]
P6 = ("P6", "S4 + proposed 'both months dry' combos")
SHAPES = list(ex.SHAPES)
MONTH_SHAPES = [s for s in SHAPES if s != "persistence"]
FINE = tuple(np.round(np.arange(0.25, 15.01, 0.25), 2))
HALF = tuple(np.round(np.arange(0.5, 15.01, 0.5), 2))
MAX_PAYOUT = 6_000.0          # about one month of the Dallas hay farm's gap cover (doc 22)
EXEC_STATIONS = ["DFW", "OKC", "SGF", "SAT", "DEN", "ABQ", "TPA"]
EXEC_MONTH = "2026-11"
COLORS = {"linear": "#444444", "layered": "#2a6f97", "convex2": "#c1121f", "exponential": "#7b2cbf",
          "tiers": "#f4a261", "capped": "#2b9348", "both_tails": "#00b4d8", "loss": "#e36414", "persistence": "#9c6644"}
SHORT = {"linear": "Linear", "layered": "Layered", "convex2": "Quadratic", "exponential": "Exponential",
         "tiers": "Tiers", "capped": "Capped", "both_tails": "Both tails", "loss": "Loss curve", "persistence": "Persistence"}


def station_grid(site: str) -> int:
    sg = pd.read_csv(PROCESSED / "study_grids.csv")
    return int(sg[(sg["site"] == site) & (sg["role"] == "station")]["grid_id"].iloc[0])


def loss_params_for(F) -> tuple[float, float]:
    lm = build_farm_model(F["farm"])
    return float(lm.elasticity), float(lm.curvature)


def fit_scores(X, y, mask, q, prot, caps=None) -> dict:
    Xm, ym = X[mask], y[mask]
    tr = op.model_tranches(q)
    if caps is not None:
        for t, c in zip(tr, caps):
            t.capacity = float(c)
    sol = op.solve_penalized(Xm, ym, tr, 0.0, prot)
    loyo = op.loyo_payout(Xm, ym, tr, None, prot)
    ev = float(np.asarray(q) @ sol.leg_contracts)
    return {"he_in": op.hedge_effectiveness(ym, sol.payout), "he_loyo": op.hedge_effectiveness(ym, loyo),
            "var_y": float(np.var(ym / prot)), "var_resid_in": float(np.var((ym - sol.payout) / prot)),
            "var_resid_loyo": float(np.var((ym - loyo) / prot)), "n": int(mask.sum()),
            "cost": sol.cost, "expected_payout": ev,
            "cost_per_dollar": sol.cost / ev if ev > 0 else np.nan,
            "tail_capture_loyo": ex.tail_capture(ym, loyo), "tail_capture_in": ex.tail_capture(ym, sol.payout),
            "capital95_loyo": ex.shortfall_capital(ym, loyo, prot, 0.95),
            "n_instruments": int(X.shape[1]), "contracts": float(sol.leg_contracts.sum()),
            "leg_contracts": sol.leg_contracts}


# ---------------------------------------------------------------------------------------------
# A. insured windows
# ---------------------------------------------------------------------------------------------

def analyse_window(F, w: Window, lp, depth_no, depth_yes) -> list[dict]:
    r = F["request"]
    prot = F["protection"] * w.share
    p = hb.build_problem(CoverageRequest(r.lat, r.lon, [Window(w.months, 1.0)], r.coverage, prot,
                                         station_key=r.station_key, strikes="kalshi", grid_id=r.grid_id))
    sg = station_grid(F["site"])
    kal = ex.kalshi_strikes_for(p)
    ladders = {"NO": {"S3": ex.ladder_cols(p, FINE, ("NO",)), "S4": ex.ladder_cols(p, kal, ("NO",))},
               "BOTH": {"S3": ex.ladder_cols(p, FINE, ("NO", "YES")), "S4": ex.ladder_cols(p, kal, ("NO", "YES"))}}
    combos = ex.combo_cols(p, kal)
    rows = []
    for shape in SHAPES:
        y = ex.shape_target(p, shape, lp)
        inst = dict(ladders["BOTH" if shape == "both_tails" else "NO"])
        inst["S1"] = ex.ideal_index_cols(p, shape, "station_grid", sg, lp)
        inst["S2"] = ex.ideal_index_cols(p, shape, "station_gauge", None, lp)
        X4, lab4, q4 = inst["S4"]
        if combos[0].shape[1]:
            inst["P6"] = (np.column_stack([X4, combos[0]]), list(lab4) + list(combos[1]),
                          np.concatenate([q4, combos[2]]))
        else:
            inst["P6"] = inst["S4"]
        mask = ~np.isnan(y)
        for X, _, _ in inst.values():
            mask &= ~np.isnan(X).any(axis=1)
        base = {"farm_id": F["farm_id"], "site": F["site"], "window": w.label, "share": w.share, "shape": shape,
                "max_payout": prot, "n": int(mask.sum()), "pay_years": int((y[mask] > 0).sum()),
                "fair_premium_per_dollar": float(np.mean(y[mask]) / prot) if mask.any() else np.nan,
                "tail_concentration": ex.tail_concentration(y[mask]),
                "payoff_at_half_shortfall": np.nan}
        if shape != "persistence":
            base["payoff_at_half_shortfall"] = float(ex.payoff(shape, np.array([45.0]), 0.9, lp)[0])
        if mask.sum() < 30 or np.var(y[mask]) == 0:
            rows.append({**base, "step": "S0", "he_in": np.nan, "he_loyo": np.nan})
            continue
        vy = float(np.var(y[mask] / prot))
        rows.append({**base, "step": "S0", "he_in": 1.0, "he_loyo": 1.0, "var_y": vy, "var_resid_in": 0.0,
                     "var_resid_loyo": 0.0, "tail_capture_loyo": 1.0, "capital95_loyo": 0.0})
        for s in ("S1", "S2", "S3", "S4", "P6"):
            X, _, q = inst[s]
            rr = fit_scores(X, y, mask, q, prot)
            rr.pop("leg_contracts")
            rows.append({**base, "step": s, **rr})
        caps = ex.caps_for(lab4, depth_no, depth_yes)
        rr = fit_scores(X4, y, mask, q4, prot, caps=caps)
        rr.pop("leg_contracts")
        rows.append({**base, "step": "S5", **rr})
    return rows


# ---------------------------------------------------------------------------------------------
# B. open single months
# ---------------------------------------------------------------------------------------------

def analyse_month(F, m: int, lp, depth_no, depth_yes) -> list[dict]:
    r = F["request"]
    gap = F["protection"] / 6
    p = hb.build_problem(CoverageRequest(r.lat, r.lon, [Window((m,), 1.0)], r.coverage, gap,
                                         station_key=r.station_key, strikes="kalshi", grid_id=r.grid_id))
    key = r.station_key
    rain_m = hb.station_rain(key).reindex(p.years)[m].to_numpy(float)
    gidx = ex.gauge_month_index(key, m, p.years)
    normal_m = float(np.nanmean(rain_m) / np.nanmean(gidx) * 100.0) if np.isfinite(np.nanmean(gidx)) else np.nan
    kal = ex.kalshi_strikes_for(p)(m)
    rows = []
    for shape in MONTH_SHAPES:
        y = ex.shape_target(p, shape, lp)
        f_g = ex.payoff(shape, gidx, r.coverage, lp)
        shape_fn = (lambda rr, s=shape: float(ex.payoff(s, np.array([100.0 * rr / normal_m]), r.coverage, lp)[0]))
        sides = ("NO", "YES") if shape == "both_tails" else ("NO",)
        X4, lab4, q4 = ex.ladder_cols(p, kal, sides)
        X2, _, q2 = ex.ideal_index_cols(p, shape, "station_gauge", None, lp)
        mask = ~np.isnan(y) & ~np.isnan(X4).any(axis=1) & ~np.isnan(X2).any(axis=1) & ~np.isnan(f_g)
        row = {"farm_id": F["farm_id"], "site": F["site"], "month": hb.MONTH_ABBR[m - 1], "shape": shape,
               "n": int(mask.sum()), "pay_years": int((y[mask] > 0).sum()),
               "fair_premium_per_dollar": float(np.mean(y[mask]) / gap) if mask.any() else np.nan}
        # exact spanning on the gauge: binning loss at three strike grids
        for name, ks in (("kalshi", kal), ("half", HALF), ("fine", FINE)):
            vals = ex.binned_values(f_g[mask], rain_m[mask], ks, shape_fn)
            h = ex.span_step(vals, ks).payout(rain_m[mask])
            vf = np.var(f_g[mask])
            row[f"binning_r2_{name}"] = float(1 - np.var(f_g[mask] - h) / vf) if vf > 0 else np.nan
        vals = ex.binned_values(f_g[mask], rain_m[mask], kal, shape_fn)
        port = ex.span_step(vals, kal)
        row["contracts_per_dollar"] = port.contracts_per_dollar
        row["cash"] = port.cash
        row["quasi_convex"] = ex.is_quasi_convex(vals)
        h_ex = gap * port.payout(rain_m)
        row["he_exchange_settled"] = op.hedge_effectiveness(y[mask], h_ex[mask]) if np.var(y[mask]) > 0 else np.nan
        if mask.sum() < 30 or np.var(y[mask]) == 0:
            rows.append(row)
            continue
        for s, (X, q, caps) in {"S2": (X2, q2, None), "S4": (X4, q4, None),
                                "S5": (X4, q4, ex.caps_for(lab4, depth_no, depth_yes))}.items():
            rr = fit_scores(X, y, mask, q, gap, caps=caps)
            rr.pop("leg_contracts")
            for k in ("he_in", "he_loyo", "cost_per_dollar", "tail_capture_loyo", "capital95_loyo", "contracts"):
                row[f"{s}_{k}"] = rr[k]
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------------------------
# C. executable exchange-settled products on the saved book
# ---------------------------------------------------------------------------------------------

def execution_study(farms) -> tuple[pd.DataFrame, pd.DataFrame]:
    st = hb.station_table().set_index("station_key")
    rows, legs = [], []
    for key in EXEC_STATIONS:
        series = st.loc[key, "series_ticker"]
        ob = ex.load_book(series, BOOK, EXEC_MONTH)
        if ob.empty:
            continue
        books = ex.books_by_strike(ob)
        strikes = sorted(books)
        rain_all = hb.station_rain(key)
        R = rain_all[11]
        normal = R[(R.index >= NORMAL_YEARS[0]) & (R.index <= NORMAL_YEARS[1])].mean()
        gidx = (100.0 * R / normal).to_numpy(float)
        Rv = R.to_numpy(float)
        fair_no = {k: leg_probability(rain_all, 11, k, FAIR_WINDOW) for k in strikes}
        fw = np.asarray((R.index >= FAIR_WINDOW[0]) & (R.index <= FAIR_WINDOW[1]))
        F = next(f for f in farms if f["site"] == key)
        lp = loss_params_for(F)
        for shape in MONTH_SHAPES:
            f = ex.payoff(shape, gidx, 0.9, lp)
            ok = ~np.isnan(f) & ~np.isnan(Rv)
            shape_fn = (lambda rr, s=shape: float(ex.payoff(s, np.array([100.0 * rr / normal]), 0.9, lp)[0]))
            vals = ex.binned_values(f[ok], Rv[ok], strikes, shape_fn)
            port = ex.span_step(vals, strikes)
            hp = port.payout(Rv)
            exp_rate = float(np.nanmean(hp[fw & ok]))
            exd = ex.execute_portfolio(port, MAX_PAYOUT, books, fair_no)
            summ = ex.execution_summary(exd, MAX_PAYOUT, exp_rate)
            wts = exd["contracts_wanted"] / MAX_PAYOUT
            fill_lim = (exd["depth_sensible"] / wts).min() if len(exd) else np.nan
            rows.append({"station": key, "series": series, "contract_month": EXEC_MONTH, "shape": shape,
                         "contracts_per_dollar": port.contracts_per_dollar, "cash": port.cash,
                         "fair_rate": exp_rate, "legs": int(len(exd)), **summ,
                         "max_fully_fillable_usd": float(fill_lim)})
            for _, lr in exd.iterrows():
                legs.append({"station": key, "shape": shape, **lr.to_dict()})
        print("execution", key, "done", flush=True)
    return pd.DataFrame(rows), pd.DataFrame(legs)


# ---------------------------------------------------------------------------------------------
# D. the data-optimal payout: ladder fit to the loss curve vs to PRF
# ---------------------------------------------------------------------------------------------

def optimal_shape_study(farms) -> pd.DataFrame:
    rows = []
    for F in farms:
        r = F["request"]
        lp = loss_params_for(F)
        for w in r.windows:
            prot = F["protection"] * w.share
            p = hb.build_problem(CoverageRequest(r.lat, r.lon, [Window(w.months, 1.0)], r.coverage, prot,
                                                 station_key=r.station_key, strikes="kalshi", grid_id=r.grid_id))
            for target in ("linear", "loss"):
                y = ex.shape_target(p, target, lp)
                ok = p.ok & ~np.isnan(y)
                if ok.sum() < 30 or np.var(y[ok]) == 0:
                    continue
                sol = op.solve_penalized(p.X[ok], y[ok], op.model_tranches(p.q), 0.0, prot)
                legs = pd.DataFrame(p.legs, columns=["month", "strike"])
                legs["w"] = sol.leg_contracts / prot
                for m, g in legs.groupby("month"):
                    g = g.sort_values("strike")
                    wv = g["w"].to_numpy(float)
                    vals = np.concatenate([np.cumsum(wv[::-1])[::-1], [0.0]])     # payout per $1 in each rain bin
                    rows.append({"farm_id": F["farm_id"], "window": w.label, "month": hb.MONTH_ABBR[int(m) - 1],
                                 "target": target, "strikes": ",".join(f"{k:g}" for k in g["strike"]),
                                 "step_values": ",".join(f"{v:.4f}" for v in vals),
                                 "payout_at_or_below_1in": float(vals[0]),
                                 "payout_1_to_2in": float(vals[1]) if len(vals) > 1 else np.nan,
                                 "payout_2_to_3in": float(vals[2]) if len(vals) > 2 else np.nan,
                                 "convexity_ratio": ex.convexity_ratio(vals),
                                 "he_in": op.hedge_effectiveness(y[ok], sol.payout)})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------------------------

def pooled(d: pd.DataFrame, col: str) -> float:
    d = d.dropna(subset=[col, "var_y"])
    den = (d["n"] * d["var_y"]).sum()
    return float(1 - (d["n"] * d[col]).sum() / den) if den > 0 else np.nan


def main(argv=None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    quick = "--quick" in args
    farms = hb.load_farm_requests()
    parts = {"windows", "months", "execution", "optimal"}
    for a in args:                    # --only months,execution  recomputes those parts, loads the rest from CSV
        if a.startswith("--only="):
            parts = set(a.split("=", 1)[1].split(","))
    if "--tables-only" in args:
        parts = set()
    saved = {"windows": "m2_exotic_windows.csv", "months": "m2_exotic_months.csv",
             "execution": "m2_exotic_execution.csv", "optimal": "m2_exotic_optimal_shape.csv"}
    if quick:
        farms = farms[:2]
    win_rows, mon_rows = [], []
    st = hb.station_table().set_index("station_key")
    if parts & {"windows", "months"}:
        for F in farms:
            r = F["request"]
            series = st.loc[r.station_key, "series_ticker"]
            depth_no, _ = ex.book_depth_by_side(series, r.station_key, "NO", BOOK)
            depth_yes, _ = ex.book_depth_by_side(series, r.station_key, "YES", BOOK)
            lp = loss_params_for(F)
            if "windows" in parts:
                for w in r.windows:
                    win_rows += analyse_window(F, w, lp, depth_no, depth_yes)
            if "months" in parts:
                covered = {m for w in r.windows for m in w.months}
                for m in sorted(set(range(1, 13)) - covered):
                    mon_rows += analyse_month(F, m, lp, depth_no, depth_yes)
            print(F["farm_id"], "done", flush=True)
    W = pd.DataFrame(win_rows) if "windows" in parts else pd.read_csv(PROCESSED / saved["windows"])
    M = pd.DataFrame(mon_rows) if "months" in parts else pd.read_csv(PROCESSED / saved["months"])
    if "execution" in parts:
        E, EL = execution_study(farms if not quick else hb.load_farm_requests())
        E.to_csv(PROCESSED / "m2_exotic_execution.csv", index=False)
        EL.to_csv(PROCESSED / "m2_exotic_execution_legs.csv", index=False)
    else:
        E = pd.read_csv(PROCESSED / saved["execution"])
    O = optimal_shape_study(farms) if "optimal" in parts else pd.read_csv(PROCESSED / saved["optimal"])
    if "windows" in parts:
        W.to_csv(PROCESSED / "m2_exotic_windows.csv", index=False)
    if "months" in parts:
        M.to_csv(PROCESSED / "m2_exotic_months.csv", index=False)
    if "optimal" in parts:
        O.to_csv(PROCESSED / "m2_exotic_optimal_shape.csv", index=False)
    figures(W, M, E, O, farms)
    t = tables(W, M, E, O)
    if not quick:
        write_auto_block(DOC, "exotic payout tables (scripts/run_exotic_payouts.py)", t)
    print(t)
    return 0


# ---------------------------------------------------------------------------------------------
# figures
# ---------------------------------------------------------------------------------------------

def figures(W, M, E, O, farms) -> None:
    lp = loss_params_for(farms[0])
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4))
    ax = axes[0]
    for s in MONTH_SHAPES:
        c = ex.shape_curve(s, 0.9, lp)
        ax.plot(c["index"], c["payoff"], color=COLORS[s], lw=1.8 if s in ("linear", "convex2") else 1.2,
                label=ex.SHAPES[s] + (f" (DFW_hay: e={lp[0]:.2f}, g={lp[1]:.2f})" if s == "loss" else ""))
    ax.axvline(90, color="k", ls=":", lw=0.8)
    ax.set_xlabel("Rain index for the window (100 = normal)")
    ax.set_ylabel("Payout per $1 of maximum payout")
    ax.set_xlim(0, 250)
    ax.legend(fontsize=7)
    ax.grid(alpha=0.3)
    ax.set_title("A. The payoff shapes (trigger 90)")
    ax = axes[1]
    s4 = W[(W["step"] == "S4")]
    for s in SHAPES:
        d = s4[s4["shape"] == s]
        ax.scatter(d["fair_premium_per_dollar"].median(), d["tail_concentration"].median(), color=COLORS[s], s=60)
        ax.annotate(ex.SHAPES[s], (d["fair_premium_per_dollar"].median(), d["tail_concentration"].median()),
                    fontsize=7, xytext=(4, 3), textcoords="offset points")
    ax.set_xlabel("Fair premium per $1 of maximum payout (median of 36 windows)")
    ax.set_ylabel("Share of payout dollars in the worst 10% of years")
    ax.grid(alpha=0.3)
    ax.set_title("B. Cheaper shapes concentrate payouts in the worst years")
    fig.tight_layout()
    fig.savefig(FIGURES / "m2_exotic_shapes.png", dpi=150)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(13, 4.6))
    ax = axes[0]
    steps = [s for s, _ in STEPS]
    x = np.arange(len(steps))
    for s in SHAPES:
        d = W[W["shape"] == s]
        he = [pooled(d[d["step"] == st], "var_resid_loyo") for st in steps]
        ax.plot(x, he, "o-", color=COLORS[s], lw=1.8 if s in ("linear", "convex2") else 1.1, ms=4, label=ex.SHAPES[s])
        p6 = pooled(d[d["step"] == "P6"], "var_resid_loyo")
        ax.scatter([len(steps) - 1.65], [p6], marker="^", color=COLORS[s], s=30)
    ax.set_xticks(x, ["Perfect", "Geography", "Settlement\nsource", "Monthly\ncontracts", "Whole-inch\nstrikes",
                      "Order-book\ndepth"], fontsize=8)
    ax.text(0.05, 0.04, "triangles: whole-inch strikes\n+ both-months-dry combos", fontsize=7, ha="left")
    ax.set_ylabel("Pooled hedge effectiveness, out of sample (36 windows)")
    ax.set_ylim(0, 1.1)
    ax.legend(fontsize=7, ncol=2, loc="upper right")
    ax.grid(alpha=0.3)
    ax.set_title("A. Error waterfall by payoff shape (insured two-month windows)", fontsize=10)
    ax = axes[1]
    g = M.groupby("shape")[["binning_r2_kalshi", "binning_r2_half", "binning_r2_fine"]].median().reindex(MONTH_SHAPES)
    xs = np.arange(len(g))
    for i, (col, lab, c) in enumerate((("binning_r2_kalshi", "whole-inch (Kalshi)", "#c1121f"),
                                       ("binning_r2_half", "half-inch", "#f4a261"),
                                       ("binning_r2_fine", "quarter-inch", "#2a6f97"))):
        ax.bar(xs + (i - 1) * 0.27, g[col], 0.27, color=c, label=lab)
    ax.set_xticks(xs, [SHORT[s] for s in g.index], fontsize=8)
    ax.set_ylabel("Share of the shape's variance the ladder spans (station rain)")
    ax.set_ylim(0, 1.05)
    ax.legend(fontsize=8, loc="lower left")
    ax.grid(axis="y", alpha=0.3)
    ax.set_title("B. Binning loss on station rain, by strike grid (60 open months)", fontsize=10)
    fig.tight_layout()
    fig.savefig(FIGURES / "m2_exotic_waterfall.png", dpi=150)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(13, 4.6))
    ax = axes[0]
    d = E[E["station"] == "DFW"].set_index("shape").reindex(MONTH_SHAPES)
    comp = pd.DataFrame({"fair premium": d["premium_fair_usd"], "spread": d["spread_cost_usd"],
                         "fee": d["fee_usd"], "capital (31 d)": d["capital_usd"]}) / MAX_PAYOUT
    bottom = np.zeros(len(comp))
    for col, c in zip(comp.columns, ("#2a6f97", "#f4a261", "#c1121f", "#2b9348")):
        ax.bar(np.arange(len(comp)), comp[col].fillna(0), bottom=bottom, color=c, label=col)
        bottom += comp[col].fillna(0).to_numpy()
    ax2 = ax.twinx()
    ax2.plot(np.arange(len(comp)), d["fill_share"], "kD", ms=5, label="share filled at a sensible price")
    ax2.set_ylim(0, 1.05)
    ax2.set_ylabel("Share of the order filled")
    ax.set_xticks(np.arange(len(comp)), [SHORT[s] for s in comp.index], fontsize=8)
    ax.set_ylabel(f"Cost per USD 1 of maximum payout (USD {MAX_PAYOUT:,.0f} product)")
    ax.legend(fontsize=7, loc="upper left")
    ax2.legend(fontsize=7, loc="upper right")
    ax.grid(axis="y", alpha=0.3)
    ax.set_title("A. Dallas, Nov 2026: each exchange-settled shape on the 2026-11-02 book", fontsize=10)
    ax = axes[1]
    o = O[(O["farm_id"] == farms[0]["farm_id"])]
    from matplotlib.lines import Line2D
    for target, ls in (("linear", "--"), ("loss", "-")):
        for (win, mon), g in o[o["target"] == target].groupby(["window", "month"]):
            vals = np.array([float(v) for v in g["step_values"].iloc[0].split(",")])
            ks = [float(k) for k in g["strikes"].iloc[0].split(",")]
            edges = [0.0] + ks + [ks[-1] + 1]
            ax.step(edges, np.concatenate([vals[:1], vals]), where="pre", ls=ls,
                    color=COLORS["loss" if target == "loss" else "linear"], alpha=0.8)
            ax.text(0.05, vals[0], mon, fontsize=6, color=COLORS["loss" if target == "loss" else "linear"],
                    va="bottom")
    ax.legend(handles=[Line2D([], [], color=COLORS["linear"], ls="--", label="fit to PRF's linear payout"),
                       Line2D([], [], color=COLORS["loss"], ls="-", label="fit to the farm's loss curve (doc 13)")],
              fontsize=8, loc="upper right")
    ax.set_xlabel("Station monthly rain (inches)")
    ax.set_ylabel("Optimal payout per USD 1 of window protection")
    ax.grid(alpha=0.3)
    ax.set_title(f"B. {farms[0]['farm_id']}: the payout the data ask for, one line per insured month", fontsize=10)
    fig.tight_layout()
    fig.savefig(FIGURES / "m2_exotic_execution.png", dpi=150)
    plt.close(fig)


# ---------------------------------------------------------------------------------------------
# tables
# ---------------------------------------------------------------------------------------------

def _f(v, nd=2):
    return "" if v is None or pd.isna(v) else f"{v:,.{nd}f}"


def _pct(v):
    return "" if v is None or pd.isna(v) else f"{v:.0%}"


def tables(W, M, E, O) -> str:
    s4 = W[W["step"] == "S4"]
    out = ["### A. The shapes: what each one costs and where it pays (36 insured windows, farm grid)", "",
           "Per $1 of maximum payout (what the contract pays when the window's rain index is 0). Fair premium = mean payout "
           "1951-2025. Tail share = payout dollars in the worst 10% of years (8 of 75).", "",
           "| Shape | Payout at index 45 (half the shortfall) | Fair premium per $1 max payout (median) | Tail share (median) "
           "| Years paying (median of 75) |", "|---|---|---|---|---|"]
    for s in SHAPES:
        d = s4[s4["shape"] == s]
        out.append(f"| {ex.SHAPES[s]} | {_f(d['payoff_at_half_shortfall'].median())} | {_f(d['fair_premium_per_dollar'].median(), 3)} "
                   f"| {_pct(d['tail_concentration'].median())} | {d['pay_years'].median():.0f} |")
    steps = [s for s, _ in STEPS]
    out += ["", "### B. Error waterfall by shape: pooled HE out of sample (LOYO), 36 insured two-month windows", "",
            "Each column adds one restriction (doc 16's steps). P6 = today's strikes plus proposed 'both months dry' combo "
            "contracts. Pooled HE weights windows by their payout variance per $1 of protection.", "",
            "| Shape | " + " | ".join(steps) + " | P6 | Drop: geography | settlement | monthly | binning | depth |",
            "|---|" + "---|" * (len(steps) + 6)]
    for s in SHAPES:
        d = W[W["shape"] == s]
        he = [pooled(d[d["step"] == st], "var_resid_loyo") for st in steps]
        p6 = pooled(d[d["step"] == "P6"], "var_resid_loyo")
        drops = [he[i] - he[i + 1] for i in range(len(he) - 1)]
        out.append(f"| {ex.SHAPES[s]} | " + " | ".join(_f(v) for v in he) + f" | {_f(p6)} | "
                   + " | ".join(_f(v) for v in drops) + " |")
    out += ["", "### C. At Kalshi's strikes (S4), by shape: fit, tail capture, issuer capital, cost (medians over the 36 windows)", "",
            "Tail capture = hedge payout in the worst 10% of years / target payout in those years (LOYO). Issuer capital = "
            "95th percentile of the yearly shortfall (target minus hedge) as a share of the window's protection: what a "
            "farm-settled issuer must hold. Cost per $1 = all-in hedge cost / fair expected payout.", "",
            "| Shape | HE LOYO (median) | Windows HE >= 0.6 | Windows HE < 0.3 | Tail capture | Issuer capital (95th pct) "
            "| Cost per $1 expected | Contracts per $1 of max payout |", "|---|---|---|---|---|---|---|---|"]
    for s in SHAPES:
        d = s4[s4["shape"] == s].dropna(subset=["he_loyo"])
        cpd = (d["contracts"] / d["max_payout"]).median()
        out.append(f"| {ex.SHAPES[s]} | {_f(d['he_loyo'].median())} | {(d['he_loyo'] >= 0.6).sum()} of {len(d)} "
                   f"| {(d['he_loyo'] < 0.3).sum()} | {_pct(d['tail_capture_loyo'].median())} | {_pct(d['capital95_loyo'].median())} "
                   f"| {_f(d['cost_per_dollar'].median())} | {_f(cpd)} |")
    out += ["", "### D. Single open months (60 farm-months): spanning on the station, basis risk, and binning", "",
            "On the station's own rain every single-month shape is spanned exactly by long NO and YES contracts, up to the strike "
            "grid. Binning R2 = share of the shape's variance (on the gauge's monthly index) that the step function on each strike "
            "grid reproduces. Exchange-settled HE = how well that exact product tracks the farm-grid payoff (the farmer's basis "
            "risk). Farm-settled HE = the issuer's out-of-sample hedge error (S4), and at today's depth (S5).", "",
            "| Shape | Binning R2: whole-inch | half-inch | quarter-inch | Contracts per $1 max payout | Exchange-settled HE "
            "(farmer's basis risk) | Farm-settled HE LOYO (S4) | Months >= 0.5 | S5 HE at today's depth |",
            "|---|---|---|---|---|---|---|---|---|"]
    for s in MONTH_SHAPES:
        d = M[M["shape"] == s]
        out.append(f"| {ex.SHAPES[s]} | {_f(d['binning_r2_kalshi'].median())} | {_f(d['binning_r2_half'].median())} "
                   f"| {_f(d['binning_r2_fine'].median())} | {_f(d['contracts_per_dollar'].median())} "
                   f"| {_f(d['he_exchange_settled'].median())} | {_f(d['S4_he_loyo'].median())} "
                   f"| {(d['S4_he_loyo'] >= 0.5).sum()} of {d['S4_he_loyo'].notna().sum()} | {_f(d['S5_he_loyo'].median())} |")
    qc = M["quasi_convex"].mean() if len(M) else np.nan
    cash = (M["cash"].abs() > 1e-9).mean() if len(M) else np.nan
    out += ["", f"Every binned shape was quasi-convex in {_pct(qc)} of the {len(M)} shape-months and needed a cash leg in "
            f"{_pct(cash)}, so all of them are long-only portfolios of today's contracts."]
    d = E[E["station"] == "DFW"].set_index("shape").reindex(MONTH_SHAPES)
    out += ["", f"### E. Executing exchange-settled products on the 2026-11-02 book: Dallas (KXRAINDALM), Nov 2026, "
            f"${MAX_PAYOUT:,.0f} maximum payout", "",
            "Closed-form portfolio from the whole-inch ladder, filled cheapest-first up to 10 cents above fair value. Fair premium = "
            "contracts filled x climatological probability; spread = premium paid minus fair; capital = 31 days of interest at 4.05%.", "",
            "| Shape | Contracts | Fair premium | Spread | Fee | Capital | All-in | Cost per $1 expected | Filled | "
            "Largest size the book fills |", "|---|---|---|---|---|---|---|---|---|---|"]
    for s, r in d.iterrows():
        if pd.isna(r["contracts_wanted"]):
            continue
        out.append(f"| {ex.SHAPES[s]} | {r['contracts_wanted']:,.0f} | ${_f(r['premium_fair_usd'])} | ${_f(r['spread_cost_usd'])} "
                   f"| ${_f(r['fee_usd'])} | ${_f(r['capital_usd'])} | ${_f(r['all_in_usd'])} | {_f(r['cost_per_dollar_expected'])} "
                   f"| {_pct(r['fill_share'])} | ${_f(r['max_fully_fillable_usd'], 0)} |")
    out += ["", "#### Fill share by station (same products, same book)", "",
            "| Station | " + " | ".join(ex.SHAPES[s] for s in MONTH_SHAPES) + " |", "|---|" + "---|" * len(MONTH_SHAPES)]
    for key, g in E.groupby("station", sort=False):
        gg = g.set_index("shape").reindex(MONTH_SHAPES)
        out.append(f"| {key} | " + " | ".join(_pct(v) for v in gg["fill_share"]) + " |")
    out += ["", "### F. The payout the data ask for: lowest-error ladder fit to the farm's loss curve vs to PRF's linear payout", "",
            "For each insured window and each of its two months, the fitted NO weights define a payout per $1 of protection in each "
            "rain bin. Convexity ratio = the drop from the <=1 in bin to the 1-2 in bin, over the mean of the next two drops; above 1 "
            "the payout accelerates as rain falls to zero.", "",
            "| Target | Months | Median convexity ratio | Months with ratio > 1 | Median payout per $1 at <= 1 in | at 1-2 in | at 2-3 in |",
            "|---|---|---|---|---|---|---|"]
    for t in ("linear", "loss"):
        g = O[O["target"] == t]
        gr = g["convexity_ratio"].replace([np.inf, -np.inf], np.nan).dropna()
        out.append(f"| {'PRF linear payout' if t == 'linear' else 'Farm loss curve (doc 13)'} | {len(g)} | {_f(gr.median())} "
                   f"| {(gr > 1).sum()} of {len(gr)} | {_f(g['payout_at_or_below_1in'].median(), 3)} "
                   f"| {_f(g['payout_1_to_2in'].median(), 3)} | {_f(g['payout_2_to_3in'].median(), 3)} |")
    return "\n".join(out)


if __name__ == "__main__":
    sys.exit(main())
