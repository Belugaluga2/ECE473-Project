"""Milestone II refinements from the submitted Milestone I (doc 20): complement PRF instead of replacing it.

Run from the repo root:   python scripts/run_prf_gaps.py

The Milestone I submission ("Refinements to our plan") said Milestone II would (1) target the gaps PRF
leaves (cover above its 90% coverage cap, uncovered months, too much rain), (2) look at payouts more
advanced than binaries, and (3) backtest on the index USDA actually paid (CPC) while forward results use
NCEI. This script measures, for the 11 farms, with the doc 15 optimizer and leave-one-year-out (LOYO)
scoring:

A. CPC as-paid robustness: the doc 15 hedges refit against PRF as actually paid, 1969-2025.
B. Top-up layer: what a 100%-coverage policy would pay on top of the farm's 90% PRF policy
   (PRF's cap), hedged with today's Kalshi NO ladder.
C. Uncovered months: each calendar month outside the farm's PRF intervals, as a single-month
   PRF-style cover at 90%, hedged with today's ladder.
D. Excess rain: a payout that starts when the window's grid rain passes 130% of normal and is full
   at 230%, hedged with Kalshi YES contracts (monthly) and with proposed two-month-total YES contracts.

Outputs: data/processed/m2_prf_gaps.csv, docs/figures/m2_prf_gaps.png, AUTO tables in
docs/analysis/20_complementing_prf.md. No network. Runs in a few minutes.
"""
from __future__ import annotations

import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from agri_hedge import error_budget as eb  # noqa: E402
from agri_hedge import hedge_builder as hb  # noqa: E402
from agri_hedge import optimizer as op  # noqa: E402
from agri_hedge.config import DOCS, FIGURES, PROCESSED  # noqa: E402
from agri_hedge.docs_util import write_auto_block  # noqa: E402
from agri_hedge.hedge_builder import CoverageRequest, Window  # noqa: E402
from agri_hedge.pricing import no_pays  # noqa: E402

DOC = DOCS / "analysis" / "20_complementing_prf.md"
EXCESS_START, EXCESS_SPAN = 130.0, 100.0
KNEE = 0.9


def fit(X, y, q, prot, budget=None) -> dict:
    ok = ~np.isnan(y) & ~np.isnan(X).any(axis=1)
    X, y = X[ok], y[ok]
    tr = op.model_tranches(q)
    if np.var(y) == 0 or len(y) < 20:
        return {"n_years": int(len(y)), "pay_years": int((y > 0).sum())}
    if budget == "knee":
        fr = op.efficient_frontier(X, y, tr, n_points=13, scale=prot, q=q)
        budget = op.knee_budget(fr, KNEE)
    sol = op.solve_penalized(X, y, tr, 0.0, prot) if budget is None else op.solve_budget(X, y, tr, budget, prot)
    loyo = op.loyo_payout(X, y, tr, budget, prot)
    ev = float(np.asarray(q) @ sol.leg_contracts)
    return {"n_years": int(len(y)), "pay_years": int((y > 0).sum()), "target_mean_usd": float(y.mean()),
            "he_in": op.hedge_effectiveness(y, sol.payout), "he_loyo": op.hedge_effectiveness(y, loyo),
            "cost_usd": sol.cost, "expected_payout_usd": ev,
            "cost_per_dollar": sol.cost / ev if ev > 0 else np.nan,
            "cost_per_target_dollar": sol.cost / y.mean() if y.mean() > 0 else np.nan}


def req_for(F, windows, index="ncei", coverage=None, prot=None) -> CoverageRequest:
    r = F["request"]
    return CoverageRequest(r.lat, r.lon, windows, coverage or r.coverage, prot or r.protection,
                           station_key=r.station_key, strikes="kalshi", grid_id=r.grid_id, index=index)


def main() -> int:
    rows = []
    farms = hb.load_farm_requests()
    fy = pd.read_csv(PROCESSED / "payout_comparison_farm_year.csv")
    for F in farms:
        fid, prot = F["farm_id"], F["protection"]
        base = {"farm_id": fid, "site": F["site"]}
        # A. CPC as paid vs NCEI
        for idx, yrs in (("ncei", hb.CPC_YEARS), ("cpc", hb.CPC_YEARS)):
            p = hb.build_problem(req_for(F, F["request"].windows, idx), years=yrs)
            chk = np.nan
            if idx == "cpc":
                a = fy[fy["farm_id"] == fid].set_index("year")["prf_cpc_as_paid_usd"].reindex(p.years).to_numpy(float)
                m = ~np.isnan(a) & ~np.isnan(p.target)
                chk = float(np.max(np.abs(a[m] - p.target[m]))) if m.any() else np.nan
            for pt, b in (("lowest_error", None), ("knee", "knee")):
                rows.append({**base, "part": "A_index", "case": f"{idx} 1969-2025", "point": pt,
                             "target_check_max_diff_usd": chk, **fit(p.X, p.target, p.q, prot, b)})
        # B. top-up above the 90% cap: 100%-coverage payout minus 90%-coverage payout, same protection
        p100 = hb.build_problem(req_for(F, F["request"].windows, coverage=1.0))
        p90 = hb.build_problem(req_for(F, F["request"].windows, coverage=0.9))
        y = p100.target - p90.target
        rows.append({**base, "part": "B_topup", "case": "100% layer above 90%", "point": "lowest_error",
                     **fit(p90.X, y, p90.q, prot)})
        # C. uncovered months
        covered = {m for w in F["request"].windows for m in w.months}
        for m in sorted(set(range(1, 13)) - covered):
            pm = hb.build_problem(req_for(F, [Window((m,), 1.0)], coverage=0.9, prot=prot / 6))
            rows.append({**base, "part": "C_uncovered", "case": hb.MONTH_ABBR[m - 1], "point": "lowest_error",
                         **fit(pm.X, pm.target, pm.q, prot / 6)})
        # D. excess rain on each insured window
        for w in F["request"].windows:
            pw = hb.build_problem(req_for(F, [Window(w.months, 1.0)], prot=prot * w.share))
            idx = hb.window_index(pw.grid_id, w, pw.years)
            y = prot * w.share * np.clip((idx - EXCESS_START) / EXCESS_SPAN, 0, 1)
            y = np.where(np.isnan(idx), np.nan, y)
            Xy, qy = 1.0 - pw.X, 1.0 - pw.q            # YES on "above K inches" = 1 - NO
            rows.append({**base, "part": "D_excess", "case": f"{w.label}: monthly YES (today)", "window": w.label,
                         "point": "lowest_error", **fit(Xy, y, qy, prot * w.share)})
            X2, _, q2 = eb.window_total_ladder_cols(pw, 1.0)
            rows.append({**base, "part": "D_excess", "case": f"{w.label}: two-month YES (proposed)", "window": w.label,
                         "point": "lowest_error", **fit(1.0 - X2, y, 1.0 - np.asarray(q2), prot * w.share)})
        print(fid, "done", flush=True)
    d = pd.DataFrame(rows)
    d.to_csv(PROCESSED / "m2_prf_gaps.csv", index=False)
    figure(d)
    t = tables(d)
    write_auto_block(DOC, "PRF gap tables (scripts/run_prf_gaps.py)", t)
    print(t)
    return 0


def figure(d: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.2))
    c = d[d["part"] == "C_uncovered"].dropna(subset=["he_loyo"])
    ax = axes[0]
    piv = c.pivot_table(index="farm_id", columns="case", values="he_loyo", sort=False)
    piv = piv.reindex(columns=[m for m in hb.MONTH_ABBR if m in piv.columns])
    im = ax.imshow(piv.clip(lower=-0.2).to_numpy(float), cmap="viridis", vmin=-0.2, vmax=1, aspect="auto")
    ax.set_xticks(range(piv.shape[1]), piv.columns, fontsize=8)
    ax.set_yticks(range(piv.shape[0]), piv.index, fontsize=8)
    ax.set_title("C. Months PRF leaves uncovered (HE out of sample)", fontsize=10)
    fig.colorbar(im, ax=ax, fraction=0.046)
    b = d[d["part"] == "B_topup"].set_index("farm_id")
    ax = axes[1]
    ax.bar(range(len(b)), b["he_loyo"], color="#2a6f97")
    ax.set_xticks(range(len(b)), b.index, rotation=40, ha="right", fontsize=8)
    ax.set_ylim(min(0, b["he_loyo"].min() - 0.05), 1)
    ax.set_title("B. Top-up layer above PRF's 90% cap", fontsize=10)
    ax.set_ylabel("HE out of sample")
    ax.grid(axis="y", alpha=0.3)
    e = d[d["part"] == "D_excess"].copy()
    e["kind"] = np.where(e["case"].str.contains("two-month"), "two-month YES (proposed)", "monthly YES (today)")
    ax = axes[2]
    for i, (k, col) in enumerate((("monthly YES (today)", "#f4a261"), ("two-month YES (proposed)", "#2a6f97"))):
        v = e[e["kind"] == k]["he_loyo"].dropna()
        ax.boxplot(v.clip(lower=-0.5), positions=[i], widths=0.5, patch_artist=True,
                   boxprops={"facecolor": col, "alpha": 0.7})
    ax.set_xticks([0, 1], ["monthly YES\n(today)", "two-month YES\n(proposed)"], fontsize=8)
    ax.set_title("D. Excess-rain cover, 36 windows", fontsize=10)
    ax.set_ylabel("HE out of sample")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIGURES / "m2_prf_gaps.png", dpi=150)
    plt.close(fig)


def _f(v, nd=2):
    return "" if pd.isna(v) else f"{v:,.{nd}f}"


def tables(d: pd.DataFrame) -> str:
    out = ["### A. Backtest on the index USDA actually paid (CPC) vs NCEI, same years 1969-2025", "",
           "| Farm | NCEI: HE in / LOYO (lowest error) | CPC as paid: HE in / LOYO (lowest error) | NCEI knee LOYO | CPC knee LOYO | CPC target vs doc 09 as-paid PRF, max gap |",
           "|---|---|---|---|---|---|"]
    a = d[d["part"] == "A_index"]
    for fid, x in a.groupby("farm_id", sort=False):
        g = x.set_index(["case", "point"])
        n, c = g.loc[("ncei 1969-2025", "lowest_error")], g.loc[("cpc 1969-2025", "lowest_error")]
        out.append(f"| {fid} | {_f(n['he_in'])} / {_f(n['he_loyo'])} | {_f(c['he_in'])} / {_f(c['he_loyo'])} "
                   f"| {_f(g.loc[('ncei 1969-2025', 'knee'), 'he_loyo'])} | {_f(g.loc[('cpc 1969-2025', 'knee'), 'he_loyo'])} "
                   f"| ${c['target_check_max_diff_usd']:,.0f} |")
    for case in ("ncei 1969-2025", "cpc 1969-2025"):
        x = a[(a["case"] == case)]
        out.append(f"| **median, {case}** | lowest error LOYO {_f(x[x['point'] == 'lowest_error']['he_loyo'].median())} "
                   f"| | knee LOYO {_f(x[x['point'] == 'knee']['he_loyo'].median())} | | |")
    b = d[d["part"] == "B_topup"]
    out += ["", "### B. Top-up layer above PRF's 90% coverage cap", "",
            "Target: what a 100%-coverage policy would pay minus what the farm's 90% policy pays, same protection "
            "and intervals (NCEI, 1951-2025). Hedge: today's Kalshi NO ladder, lowest error.", "",
            "| Farm | Years the layer pays | Mean layer payout / yr | HE in | HE LOYO | Hedge cost / yr | Cost per $1 of layer payout |",
            "|---|---|---|---|---|---|---|"]
    for _, r in b.iterrows():
        out.append(f"| {r['farm_id']} | {r['pay_years']} of {r['n_years']} | ${r['target_mean_usd']:,.0f} | {_f(r['he_in'])} "
                   f"| {_f(r['he_loyo'])} | ${r['cost_usd']:,.0f} | {_f(r['cost_per_target_dollar'])} |")
    out.append(f"| **median** | | | {_f(b['he_in'].median())} | {_f(b['he_loyo'].median())} | | "
               f"{_f(b['cost_per_target_dollar'].median())} |")
    c = d[d["part"] == "C_uncovered"].dropna(subset=["he_loyo"])
    out += ["", "### C. Months PRF leaves uncovered (single-month cover at 90%, today's ladder)", "",
            f"{len(c)} farm-months outside the farms' PRF intervals. Median HE LOYO {_f(c['he_loyo'].median())}; "
            f"{(c['he_loyo'] >= 0.6).sum()} reach 0.6, {(c['he_loyo'] < 0.3).sum()} are below 0.3.", "",
            "| Month | Farm-months | Median HE LOYO | Best farm (HE LOYO) |", "|---|---|---|---|"]
    for m in hb.MONTH_ABBR:
        x = c[c["case"] == m]
        if len(x):
            bst = x.loc[x["he_loyo"].idxmax()]
            out.append(f"| {m} | {len(x)} | {_f(x['he_loyo'].median())} | {bst['farm_id']} ({_f(bst['he_loyo'])}) |")
    e = d[d["part"] == "D_excess"].dropna(subset=["he_loyo"])
    out += ["", "### D. Excess-rain cover on each insured window", "",
            f"Target: pays from {EXCESS_START:.0f}% of normal grid rain in the window, in full at "
            f"{EXCESS_START + EXCESS_SPAN:.0f}% (share of protection x min(1, (index - {EXCESS_START:.0f}) / {EXCESS_SPAN:.0f})). "
            "Hedge: YES contracts (pay when station rain is above K).", "",
            "| Contracts | Windows | Median years paying | Median HE in | Median HE LOYO | Windows with HE LOYO >= 0.6 | Median cost per $1 expected |",
            "|---|---|---|---|---|---|---|"]
    for kind in ("monthly YES (today)", "two-month YES (proposed)"):
        x = e[e["case"].str.contains(kind.split(" (")[0])]
        out.append(f"| {kind} | {len(x)} | {x['pay_years'].median():.0f} of 75 | {_f(x['he_in'].median())} | {_f(x['he_loyo'].median())} "
                   f"| {(x['he_loyo'] >= 0.6).sum()} | {_f(x['cost_per_dollar'].median())} |")
    best = e[e["case"].str.contains("two-month")].sort_values("he_loyo", ascending=False).head(5)
    out += ["", "Best excess-rain windows with two-month YES contracts: " +
            "; ".join(f"{r['farm_id']} {r['window']} ({_f(r['he_loyo'])})" for _, r in best.iterrows()) + "."]
    return "\n".join(out)


if __name__ == "__main__":
    sys.exit(main())
