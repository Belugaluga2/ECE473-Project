"""Milestone 2, W4 (Jack): lowest-error / lowest-cost Kalshi portfolios for the 11 farms (doc 15).

Run from the repo root:   python scripts/run_optimizer.py

For each representative farm the target is its PRF indemnity by year on the NCEI index (what PRF
pays on from crop year 2027), 1951-2025, rebuilt from the farm's grid. The instruments are NO
contracts at the strikes Kalshi lists for the farm's station, priced at fair value (1991-2025
climatology) plus half a 4.5-cent spread, with taker fees and 31 days of prepaid cash at 4.05%.

The script traces each farm's efficient frontier (lowest error at each cost), then reports four
points on it: the lowest-error hedge (= doc 08/09 NNLS), the "knee" (cheapest hedge with 90% of
the best variance reduction), and hedges whose cost equals the farm's PRF producer premium and its
full (unsubsidized) PRF premium. Each point is scored in-sample (1951-2025) and out of sample
(leave one year out, refitting at the same budget).

Outputs: data/processed/m2_optimizer_frontier.csv, m2_optimizer_summary.csv,
docs/figures/m2_frontiers.png, m2_he_by_budget.png, and the tables between the AUTO markers in
docs/analysis/15_hedge_optimizer.md. No network. Runs in about two minutes.
"""
from __future__ import annotations

import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from agri_hedge import hedge_builder as hb  # noqa: E402
from agri_hedge import optimizer as op  # noqa: E402
from agri_hedge.config import DOCS, FIGURES, PROCESSED  # noqa: E402
from agri_hedge.docs_util import write_auto_block  # noqa: E402

DOC = DOCS / "analysis" / "15_hedge_optimizer.md"
TAG = "optimizer tables (scripts/run_optimizer.py)"
KNEE_SHARE = 0.9


def score(p: hb.HedgeProblem, tr, budget, prot) -> dict:
    """In-sample and leave-one-year-out scores of the lowest-error hedge costing <= budget."""
    ok = p.ok
    X, y = p.X[ok], p.target[ok]
    sol = op.solve_penalized(X, y, tr, 0.0, prot) if budget is None else op.solve_budget(X, y, tr, budget, prot)
    loyo = op.loyo_payout(X, y, tr, budget, prot)
    ev = float(p.q @ sol.leg_contracts)
    return {"cost": sol.cost, "expected_payout_fair": ev, "cost_per_dollar_expected": sol.cost / ev if ev else np.nan,
            "he_in": op.hedge_effectiveness(y, sol.payout), "he_loyo": op.hedge_effectiveness(y, loyo),
            "rmse_in": sol.rmse, "rmse_loyo": float(np.sqrt(np.nanmean((y - loyo) ** 2))),
            "n_legs_used": int((sol.leg_contracts > 1e-6).sum()), "contracts": float(sol.leg_contracts.sum()),
            "max_contracts_one_leg": float(sol.leg_contracts.max()) if len(sol.leg_contracts) else 0.0,
            "corr_in": float(np.corrcoef(y, sol.payout)[0, 1]) if np.std(sol.payout) > 0 else np.nan,
            "sol": sol}


def main() -> int:
    farms = hb.load_farm_requests()
    frontier_rows, rows, sols = [], [], {}
    for F in farms:
        p = hb.build_problem(F["request"])
        prot = F["protection"]
        ok = p.ok
        X, y = p.X[ok], p.target[ok]
        tr = op.model_tranches(p.q)
        fr = op.efficient_frontier(X, y, tr, n_points=21, scale=prot, q=p.q)
        fr.insert(0, "farm_id", F["farm_id"])
        frontier_rows.append(fr)
        knee = op.knee_budget(fr, KNEE_SHARE)
        base = {"farm_id": F["farm_id"], "site": F["site"], "station": p.station["station_key"],
                "distance_mi": round(p.distance_mi, 1), "protection_usd": prot,
                "prf_producer_premium_usd": F["producer_premium"], "prf_total_premium_usd": F["total_premium"],
                "prf_mean_payout_1951_2025_usd": float(np.mean(y)), "n_years": int(ok.sum()),
                "n_legs_available": X.shape[1],
                "target_check_max_abs_diff_usd": float(np.nanmax(np.abs(
                    p.target - F["prf_ncei_usd"].reindex(p.years).to_numpy(float))))}
        for point, b in (("lowest_error", None), ("knee_90pct", knee),
                         ("budget_prf_producer_premium", F["producer_premium"]),
                         ("budget_prf_total_premium", F["total_premium"])):
            s = score(p, tr, b, prot)
            sols[(F["farm_id"], point)] = s.pop("sol")
            rows.append({**base, "point": point, "budget_usd": b, **s})
        print(f"{F['farm_id']}: done", flush=True)
    fr_all = pd.concat(frontier_rows, ignore_index=True)
    summ = pd.DataFrame(rows)
    fr_all.to_csv(PROCESSED / "m2_optimizer_frontier.csv", index=False)
    summ.to_csv(PROCESSED / "m2_optimizer_summary.csv", index=False)
    figures(fr_all, summ)
    write_auto_block(DOC, TAG, tables(summ))
    print(tables(summ))
    return 0


def figures(fr: pd.DataFrame, summ: pd.DataFrame) -> None:
    ids = list(dict.fromkeys(fr["farm_id"]))
    fig, axes = plt.subplots(3, 4, figsize=(13, 8.5), sharey=True)
    for ax, fid in zip(axes.flat, ids):
        d = fr[fr["farm_id"] == fid]
        s = summ[summ["farm_id"] == fid].set_index("point")
        prot = s["protection_usd"].iloc[0]
        ax.plot(100 * d["cost"] / prot, d["he"], color="#2a6f97", lw=2)
        for pt, mk, col, lab in (("budget_prf_producer_premium", "o", "#c1121f", "PRF producer premium"),
                                 ("budget_prf_total_premium", "s", "#6a4c93", "PRF full premium"),
                                 ("knee_90pct", "^", "#2b9348", "90% knee")):
            ax.scatter(100 * s.loc[pt, "cost"] / prot, s.loc[pt, "he_in"], marker=mk, color=col, zorder=3, label=lab)
        ax.set_title(fid, fontsize=10)
        ax.grid(alpha=0.3)
        ax.set_ylim(0, 1)
    for ax in axes.flat[len(ids):]:
        ax.axis("off")
    axes.flat[0].legend(fontsize=7, loc="lower right")
    fig.supxlabel("Hedge cost, % of the farm's PRF protection")
    fig.supylabel("Hedge effectiveness, in-sample 1951-2025")
    fig.suptitle("Efficient frontiers: lowest error at each price (Kalshi strikes, fair + half spread)")
    fig.tight_layout()
    fig.savefig(FIGURES / "m2_frontiers.png", dpi=150)
    plt.close(fig)

    piv = summ.pivot(index="farm_id", columns="point", values="he_loyo").reindex(ids)
    fig, ax = plt.subplots(figsize=(10, 4.2))
    cols = [("budget_prf_producer_premium", "#c1121f", "budget = PRF producer premium"),
            ("budget_prf_total_premium", "#6a4c93", "budget = PRF full premium"),
            ("lowest_error", "#2a6f97", "no budget (lowest error)")]
    w = 0.27
    x = np.arange(len(ids))
    for i, (c, col, lab) in enumerate(cols):
        ax.bar(x + (i - 1) * w, piv[c].clip(lower=-0.2), w, color=col, label=lab)
    ax.axhline(0, color="k", lw=0.8)
    ax.set_xticks(x, ids, rotation=30, ha="right")
    ax.set_ylabel("Hedge effectiveness, out of sample (LOYO)")
    ax.legend(fontsize=8)
    ax.grid(axis="y", alpha=0.3)
    ax.set_title("What each budget buys, out of sample")
    fig.tight_layout()
    fig.savefig(FIGURES / "m2_he_by_budget.png", dpi=150)
    plt.close(fig)


def _f(v, nd=2):
    return "" if pd.isna(v) else f"{v:,.{nd}f}"


def _usd(v):
    return "" if pd.isna(v) else f"${v:,.0f}"


def tables(summ: pd.DataFrame) -> str:
    out = ["### Per farm: four points on the frontier", "",
           "HE = hedge effectiveness (1 - Var(PRF - hedge) / Var(PRF)). In = fit and scored on 1951-2025. "
           "LOYO = refit without each year at the same budget, scored on that year. Cost is all-in "
           "(fair + 2.25c, taker fee, 31 days of capital). $/$ = cost per $1 of fair expected payout.", "",
           "| Farm | PRF producer premium | Lowest-error hedge: cost / HE in / HE LOYO | 90% knee: cost / HE in / HE LOYO "
           "| Budget = producer premium: HE in / HE LOYO | Budget = full premium: HE in / HE LOYO |",
           "|---|---|---|---|---|---|"]
    for fid, d in summ.groupby("farm_id", sort=False):
        s = d.set_index("point")
        le, kn, pp, tp = (s.loc[k] for k in ("lowest_error", "knee_90pct", "budget_prf_producer_premium",
                                             "budget_prf_total_premium"))
        out.append(f"| {fid} | {_usd(pp['budget_usd'])} | {_usd(le['cost'])} / {_f(le['he_in'])} / {_f(le['he_loyo'])} "
                   f"| {_usd(kn['cost'])} / {_f(kn['he_in'])} / {_f(kn['he_loyo'])} "
                   f"| {_f(pp['he_in'])} / {_f(pp['he_loyo'])} | {_f(tp['he_in'])} / {_f(tp['he_loyo'])} |")
    out += ["", "### All 11 farms together", "",
            "| Point | Total cost | Total fair expected payout | Cost per $1 expected | Median HE in | Median HE LOYO | Legs used (median) |",
            "|---|---|---|---|---|---|---|"]
    for pt, lab in (("lowest_error", "Lowest error (no budget)"), ("knee_90pct", "90% knee"),
                    ("budget_prf_producer_premium", "Budget = PRF producer premium"),
                    ("budget_prf_total_premium", "Budget = PRF full premium")):
        d = summ[summ["point"] == pt]
        out.append(f"| {lab} | {_usd(d['cost'].sum())} | {_usd(d['expected_payout_fair'].sum())} "
                   f"| {_f(d['cost'].sum() / d['expected_payout_fair'].sum())} | {_f(d['he_in'].median())} "
                   f"| {_f(d['he_loyo'].median())} | {d['n_legs_used'].median():.0f} |")
    tot_pp = summ[summ["point"] == "lowest_error"]["prf_producer_premium_usd"].sum()
    tot_tp = summ[summ["point"] == "lowest_error"]["prf_total_premium_usd"].sum()
    out += ["", f"PRF premiums for the same 11 farms: producer {_usd(tot_pp)}, full {_usd(tot_tp)} per year.",
            "", f"Target check: largest gap between the rebuilt PRF target and doc 04b's NCEI indemnity in any "
            f"farm-year: {_usd(summ['target_check_max_abs_diff_usd'].max())} (index rounding)."]
    return "\n".join(out)


if __name__ == "__main__":
    sys.exit(main())
