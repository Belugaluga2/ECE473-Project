"""What limits the PRF Companion, and how to design it better (doc 22).

Run from the repo root:   python scripts/run_companion_improve.py

A. Liquidity: refit each farm's recommended companion with every leg capped at the NO contracts
   offered within 10 cents of fair value on a real order book (the same strike on the station's
   listed November ladder, taken as the depth for every month), on the 2026-10-29 snapshot (during
   liquidity rewards) and the 2026-11-02 snapshot (after). Then find the depth multiple needed to
   reach 90% of the uncapped fit, and how much cover per month today's depth supports.
B. Cover design: for every month a farm's PRF policy leaves open, compare trigger levels (70-100% of
   normal) and payout shapes (PRF-style linear vs a fixed payment when the index is below the
   trigger). Scored by hedge effectiveness on unseen years (LOYO) at the app's 95% knee.

Outputs: data/processed/m2_improve_liquidity.csv, m2_improve_design.csv, docs/figures/m2_improve.png,
AUTO tables in docs/analysis/22_making_it_better.md.
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
from agri_hedge.platform import KNEE_SHARE  # noqa: E402

DOC = DOCS / "analysis" / "22_making_it_better.md"
SNAPS = {"2026-10-29 (rewards on)": PROCESSED / "kalshi_rain_orderbook_summary_20261029.csv",
         "2026-11-02 (rewards off)": PROCESSED / "kalshi_rain_orderbook_summary_20261102.csv"}
MULTS = (1, 2, 5, 10, 25, 50, 100)


def he_loyo(X, y, tr, prot, budget=None):
    return op.hedge_effectiveness(y, op.loyo_payout(X, y, tr, budget, prot))


def liquidity(F, months) -> list[dict]:
    r, prot = F["request"], F["protection"]
    gap = prot / 6
    p = hb.build_problem(CoverageRequest(r.lat, r.lon, [Window((m,), 1.0 / len(months)) for m in months],
                                         r.coverage, gap * len(months), station_key=r.station_key, grid_id=r.grid_id))
    ok = p.ok
    X, y = p.X[ok], p.target[ok]
    free = he_loyo(X, y, op.model_tranches(p.q), gap * len(months))
    sol = op.solve_penalized(X, y, op.model_tranches(p.q), 0.0, gap * len(months))
    series = p.station["series_ticker"]
    rows = []
    for snap, path in SNAPS.items():
        depth, _ = eb.book_depth_by_strike(series, r.station_key, path=path)
        base = {"farm_id": F["farm_id"], "months": ", ".join(hb.MONTH_ABBR[m - 1] for m in months), "snapshot": snap,
                "he_uncapped": free, "contracts_needed": float(sol.leg_contracts.sum()),
                "depth_total": float(sum(depth.get(k, 0.0) for (_, k) in p.legs))}
        need = None
        for mult in MULTS:
            tr = op.model_tranches(p.q)
            for t, (_, k) in zip(tr, p.legs):
                t.capacity = mult * depth.get(k, 0.0)
            h = he_loyo(X, y, tr, gap * len(months))
            rows.append({**base, "depth_multiple": mult, "he_capped": h})
            if need is None and free > 0 and h >= 0.9 * free:
                need = mult
        for row in rows[-len(MULTS):]:
            row["multiple_for_90pct"] = need
    return rows


def design(F) -> list[dict]:
    r, prot = F["request"], F["protection"]
    gap = prot / 6
    covered = {m for w in r.windows for m in w.months}
    rows = []
    for m in sorted(set(range(1, 13)) - covered):
        for cov in (0.7, 0.8, 0.9, 1.0):
            p = hb.build_problem(CoverageRequest(r.lat, r.lon, [Window((m,), 1.0)], cov, gap,
                                                 station_key=r.station_key, grid_id=r.grid_id))
            ok = p.ok
            idx = hb.window_index(p.grid_id, Window((m,), 1.0), p.years)
            shapes = {"linear (PRF-style)": p.target,
                      "fixed payment below trigger": np.where(np.isnan(idx), np.nan, gap * 0.3 * (idx < 100 * cov))}
            for shape, y in shapes.items():
                yy, XX = y[ok], p.X[ok]
                if np.var(yy) == 0:
                    continue
                tr = op.model_tranches(p.q)
                fr = op.efficient_frontier(XX, yy, tr, n_points=13, scale=gap, q=p.q)
                b = op.knee_budget(fr, KNEE_SHARE)
                rows.append({"farm_id": F["farm_id"], "month": hb.MONTH_ABBR[m - 1], "coverage": cov, "shape": shape,
                             "pay_years": int((yy > 0).sum()), "he_loyo": he_loyo(XX, yy, tr, gap, b)})
    return rows


def main() -> int:
    comp = pd.read_csv(PROCESSED / "m2_companion_farms.csv").set_index("farm_id")
    liq, des = [], []
    for F in hb.load_farm_requests():
        rec = comp.loc[F["farm_id"], "recommended"]
        if isinstance(rec, str) and rec:
            liq += liquidity(F, [hb.MONTH_ABBR.index(x.strip()) + 1 for x in rec.split(",")])
        des += design(F)
        print(F["farm_id"], "done", flush=True)
    L, D = pd.DataFrame(liq), pd.DataFrame(des)
    L.to_csv(PROCESSED / "m2_improve_liquidity.csv", index=False)
    D.to_csv(PROCESSED / "m2_improve_design.csv", index=False)
    figure(L, D)
    t = tables(L, D)
    write_auto_block(DOC, "improvement tables (scripts/run_companion_improve.py)", t)
    print(t)
    return 0


def figure(L, D):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.3))
    ax = axes[0]
    for snap, col in zip(SNAPS, ("#2b9348", "#c1121f")):
        g = L[L["snapshot"] == snap].groupby("depth_multiple")[["he_capped", "he_uncapped"]].median()
        ax.plot(g.index, g["he_capped"], "o-", color=col, label=f"capped at book depth x k, {snap}")
    ax.axhline(L["he_uncapped"].median(), color="k", ls="--", lw=1, label="no depth limit")
    ax.set_xscale("log")
    ax.set_xlabel("Order-book depth multiple k")
    ax.set_ylabel("Median companion HE (unseen years)")
    ax.legend(fontsize=7)
    ax.grid(alpha=0.3)
    ax.set_title("A. How deep the book must be")
    ax = axes[1]
    g = D.groupby(["shape", "coverage"])["he_loyo"].median().unstack(0)
    for col, c in zip(g.columns, ("#f4a261", "#2a6f97")):
        ax.plot(g.index * 100, g[col], "o-", color=c, label=col)
    ax.set_xlabel("Trigger (% of normal rain)")
    ax.set_ylabel("Median HE (unseen years), 60 open farm-months")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    ax.set_title("B. Designing the gap cover")
    fig.tight_layout()
    fig.savefig(FIGURES / "m2_improve.png", dpi=150)
    plt.close(fig)


def _f(v, nd=2):
    return "" if v is None or pd.isna(v) else f"{v:,.{nd}f}"


def tables(L, D) -> str:
    out = ["### A. The companion under real order-book depth", "",
           "| Farm | Months | Contracts needed | Depth near fair value (2026-11-02) | HE, no limit | HE at today's depth (rewards off) "
           "| HE at depth during rewards | Depth multiple for 90% of the fit |", "|---|---|---|---|---|---|---|---|"]
    for fid, x in L.groupby("farm_id", sort=False):
        off = x[(x["snapshot"].str.contains("off")) & (x["depth_multiple"] == 1)].iloc[0]
        on = x[(x["snapshot"].str.contains("on")) & (x["depth_multiple"] == 1)].iloc[0]
        out.append(f"| {fid} | {off['months']} | {off['contracts_needed']:,.0f} | {off['depth_total']:,.0f} | {_f(off['he_uncapped'])} "
                   f"| {_f(off['he_capped'])} | {_f(on['he_capped'])} | {'' if pd.isna(off['multiple_for_90pct']) else f'{off.multiple_for_90pct:.0f}x'} |")
    for snap in SNAPS:
        g = L[L["snapshot"] == snap].groupby("depth_multiple")["he_capped"].median()
        out.append("")
        out.append(f"Median companion HE by depth multiple, {snap}: " + ", ".join(f"{k}x {_f(v)}" for k, v in g.items())
                   + f" (no limit {_f(L['he_uncapped'].median())}).")
    out += ["", "### B. Designing the gap cover (60 open farm-months)", "",
            "| Trigger | Linear (PRF-style): median HE | months >= 0.5 | Fixed payment: median HE | months >= 0.5 | Median years paying (linear) |",
            "|---|---|---|---|---|---|"]
    for cov, x in D.groupby("coverage"):
        lin, fix = x[x["shape"].str.startswith("linear")], x[x["shape"].str.startswith("fixed")]
        out.append(f"| {cov:.0%} | {_f(lin['he_loyo'].median())} | {(lin['he_loyo'] >= 0.5).sum()} | {_f(fix['he_loyo'].median())} "
                   f"| {(fix['he_loyo'] >= 0.5).sum()} | {lin['pay_years'].median():.0f} of 75 |")
    best = D.loc[D.groupby(["farm_id", "month"])["he_loyo"].idxmax()]
    base = D[(D["coverage"] == 0.9) & D["shape"].str.startswith("linear")].set_index(["farm_id", "month"])["he_loyo"]
    gain = best.set_index(["farm_id", "month"])["he_loyo"] - base
    out += ["", f"Best design per month vs the current default (linear, 90%): median gain {_f(gain.median())}, "
            f"months reaching 0.5 rise from {(base >= 0.5).sum()} to {(best['he_loyo'] >= 0.5).sum()} of {len(base)}. "
            "Best designs: " + ", ".join(f"{k} {v}" for k, v in best.groupby(['coverage', 'shape']).size().sort_values(ascending=False).head(4).items()) + "."]
    return "\n".join(out)


if __name__ == "__main__":
    sys.exit(main())
