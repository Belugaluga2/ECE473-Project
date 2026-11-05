"""Milestone II showcase: the PRF Companion on the 11 farms and across the app's area (doc 21).

Run from the repo root:   python scripts/run_companion_study.py [--n-grids 60]

Everything goes through `agri_hedge.platform.companion`, the function behind the app's PRF Companion
tab. For each representative farm it enters the farm's real PRF election; for the sweep it enters a
standard hay-season election (Apr-May 40%, Jun-Jul 35%, Aug-Sep 25%, 90%, $36,585 protection) at
random grids. Estimated prices (reproducible). Also records the two experiments that set the app's
defaults: recommending at 95% of the best fit, and multi-station hedges (see doc 21).

Outputs: data/processed/m2_companion_farms.csv, m2_companion_months.csv, m2_companion_sweep.csv,
docs/figures/m2_companion_farms.png, m2_companion_sweep.png, AUTO tables in
docs/analysis/21_prf_companion.md.
"""
from __future__ import annotations

import argparse
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from agri_hedge import hedge_builder as hb  # noqa: E402
from agri_hedge import platform as pf  # noqa: E402
from agri_hedge.config import DOCS, FIGURES, PROCESSED  # noqa: E402
from agri_hedge.docs_util import write_auto_block  # noqa: E402
from agri_hedge.prf_grid import grid_id_to_center  # noqa: E402

DOC = DOCS / "analysis" / "21_prf_companion.md"
HAY = [{"label": "Apr-May", "share": 0.40}, {"label": "Jun-Jul", "share": 0.35}, {"label": "Aug-Sep", "share": 0.25}]


def run_one(lat, lon, intervals, coverage, protection, station_key=None) -> dict:
    return pf.companion({"lat": lat, "lon": lon, "prf_intervals": intervals, "coverage": coverage,
                         "protection": protection, "station_key": station_key, "price_source": "model"})


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-grids", type=int, default=60)
    a = ap.parse_args(argv)
    farm_rows, month_rows = [], []
    for F in hb.load_farm_requests():
        f = F["farm"]
        c = run_one(f["lat"], f["lon"], [{"label": k, "share": v} for k, v in f["interval_allocation"].items()],
                    f["coverage_level"], F["protection"])
        for m in c["months"]:
            if not m["covered_by_prf"]:
                month_rows.append({"farm_id": F["farm_id"], **{k: m.get(k) for k in
                                   ("name", "month", "he_out_of_sample", "cost_per_dollar_expected", "verdict")}})
        s = c.get("summary") or {}
        q = c.get("package") or {}
        farm_rows.append({"farm_id": F["farm_id"], "station": c["station"]["key"],
                          "distance_mi": c["station"]["distance_mi"],
                          "uncovered_months": sum(not m["covered_by_prf"] for m in c["months"]),
                          "recommended": ", ".join(c["recommended_months"]), "n_recommended": len(c["recommended_months"]),
                          "package_cost_usd": s.get("package_cost_usd"),
                          "package_expected_payout_usd": s.get("package_expected_payout_usd"),
                          "package_cost_per_dollar": (q.get("hedge") or {}).get("cost_per_dollar_expected"),
                          "package_he_oos": s.get("package_he_out_of_sample"),
                          "gap_cover_expected_usd": s.get("gap_cover_expected_usd"),
                          "prf_producer_premium_usd": F["producer_premium"],
                          "prf_expected_payout_usd": c["prf"]["expected_payout_usd"],
                          "prf_intervals_he_oos_doc19": None})
        print(F["farm_id"], c["recommended_months"], s.get("package_he_out_of_sample"), flush=True)
    farms = pd.DataFrame(farm_rows)
    months = pd.DataFrame(month_rows)
    app = pd.read_csv(PROCESSED / "m2_app_test_farms.csv")
    app = app[app["budget_rule"] == "app recommendation"].set_index("farm_id")["app_he_oos"]
    farms["prf_intervals_he_oos_doc19"] = farms["farm_id"].map(app)
    farms.to_csv(PROCESSED / "m2_companion_farms.csv", index=False)
    months.to_csv(PROCESSED / "m2_companion_months.csv", index=False)
    rng = np.random.default_rng(473)
    grids = rng.choice(sorted(hb.covered_grids()), size=a.n_grids, replace=False)
    sw = []
    for i, g in enumerate(grids):
        lat, lon = grid_id_to_center(int(g))
        try:
            c = run_one(lat, lon, HAY, 0.9, 36585)
        except ValueError:
            continue
        s = c.get("summary") or {}
        sw.append({"grid_id": int(g), "lat": lat, "lon": lon, "station": c["station"]["key"],
                   "distance_mi": c["station"]["distance_mi"], "n_recommended": len(c["recommended_months"]),
                   "recommended": ", ".join(c["recommended_months"]), "package_he_oos": s.get("package_he_out_of_sample"),
                   "package_cost_usd": s.get("package_cost_usd"),
                   "best_month_he": max([m.get("he_out_of_sample") or -9 for m in c["months"] if not m["covered_by_prf"]])})
        if (i + 1) % 10 == 0:
            print(f"sweep {i + 1}/{len(grids)}", flush=True)
    sw = pd.DataFrame(sw)
    sw.to_csv(PROCESSED / "m2_companion_sweep.csv", index=False)
    figures(farms, months, sw)
    t = tables(farms, months, sw)
    write_auto_block(DOC, "companion tables (scripts/run_companion_study.py)", t)
    print(t)
    return 0


def figures(farms, months, sw):
    fig, ax = plt.subplots(figsize=(11, 4.6))
    piv = months.pivot_table(index="farm_id", columns="name", values="he_out_of_sample", sort=False)
    order = list(dict.fromkeys(farms["farm_id"]))
    piv = piv.reindex(index=order, columns=hb.MONTH_ABBR)
    im = ax.imshow(piv.clip(lower=-0.2).to_numpy(float), cmap="RdYlGn", vmin=-0.2, vmax=0.9, aspect="auto")
    for i in range(piv.shape[0]):
        for j in range(piv.shape[1]):
            v = piv.iloc[i, j]
            ax.text(j, i, "PRF" if pd.isna(v) else f"{v:.2f}", ha="center", va="center", fontsize=7,
                    color="#555" if pd.isna(v) else "k")
    ax.set_xticks(range(12), hb.MONTH_ABBR)
    ax.set_yticks(range(len(order)), order)
    fig.colorbar(im, ax=ax, label="HE on unseen years")
    ax.set_title("PRF Companion: how well each month PRF leaves open can be hedged (grey text = covered by PRF)")
    fig.tight_layout()
    fig.savefig(FIGURES / "m2_companion_farms.png", dpi=150)
    plt.close(fig)
    if len(sw):
        fig, axes = plt.subplots(1, 2, figsize=(12, 4.3))
        ax = axes[0]
        ax.scatter(sw["distance_mi"], sw["n_recommended"], c=sw["package_he_oos"].fillna(0), cmap="viridis", vmin=0, vmax=0.9)
        ax.set_xlabel("Distance to settlement station (miles)")
        ax.set_ylabel("Gap months recommended (of 6)")
        ax.grid(alpha=0.3)
        ax.set_title("Hay-season PRF policy at random grids")
        ax = axes[1]
        sc = ax.scatter(sw["lon"], sw["lat"], c=sw["n_recommended"], cmap="viridis", vmin=0, vmax=6, s=22)
        st = hb.station_table()
        ax.scatter(st["lon"], st["lat"], marker="*", color="#c1121f", s=60)
        ax.set_xlim(sw["lon"].min() - 1, sw["lon"].max() + 1)
        ax.set_ylim(sw["lat"].min() - 1, sw["lat"].max() + 1)
        fig.colorbar(sc, ax=ax, label="months recommended")
        ax.set_title("Map (stars = Kalshi stations)")
        fig.tight_layout()
        fig.savefig(FIGURES / "m2_companion_sweep.png", dpi=150)
        plt.close(fig)


def _f(v, nd=2):
    return "" if v is None or pd.isna(v) else f"{v:,.{nd}f}"


def tables(farms, months, sw) -> str:
    out = ["### The 11 farms", "",
           "| Farm | Station (mi) | Months PRF leaves open | Recommended | Companion HE (unseen years) | PRF-interval hedge HE (doc 19) "
           "| Companion cost / yr | Cost per $1 | PRF producer premium |", "|---|---|---|---|---|---|---|---|---|"]
    for _, r in farms.iterrows():
        out.append(f"| {r['farm_id']} | {r['station']} ({r['distance_mi']:.0f}) | {r['uncovered_months']} | {r['recommended'] or 'none'} "
                   f"| {_f(r['package_he_oos'])} | {_f(r['prf_intervals_he_oos_doc19'])} "
                   f"| {'' if pd.isna(r['package_cost_usd']) else f'${r.package_cost_usd:,.0f}'} | {_f(r['package_cost_per_dollar'])} "
                   f"| ${r['prf_producer_premium_usd']:,.0f} |")
    has = farms.dropna(subset=["package_he_oos"])
    out += ["", f"Farms with at least one recommended month: {len(has)} of {len(farms)}. Median companion HE {_f(has['package_he_oos'].median())} "
            f"vs {_f(farms['prf_intervals_he_oos_doc19'].median())} for hedging the PRF intervals themselves. "
            f"Companions cost ${has['package_cost_usd'].sum():,.0f} a year in total for {int(has['n_recommended'].sum())} farm-months "
            f"(median {_f(has['package_cost_per_dollar'].median())} per $1 of expected payout).",
            "", "### Each month PRF leaves open (all 11 farms)", "",
            "| Month | Farm-months | Recommended | Median HE |", "|---|---|---|---|"]
    for m in hb.MONTH_ABBR:
        x = months[months["name"] == m]
        if len(x):
            out.append(f"| {m} | {len(x)} | {(x['verdict'] == 'recommended').sum()} | {_f(x['he_out_of_sample'].median())} |")
    if len(sw):
        bins = pd.cut(sw["distance_mi"], [0, 25, 50, 75, 100, 150, 400])
        out += ["", f"### Sweep: hay-season PRF policy at {len(sw)} random grids", "",
                "| Distance to station | Grids | Share with any month recommended | Median months recommended | Median companion HE |",
                "|---|---|---|---|---|"]
        for k, d in sw.groupby(bins, observed=True):
            out.append(f"| {k} mi | {len(d)} | {(d['n_recommended'] > 0).mean():.0%} | {d['n_recommended'].median():.0f} "
                       f"| {_f(d['package_he_oos'].median())} |")
        out.append(f"| all | {len(sw)} | {(sw['n_recommended'] > 0).mean():.0%} | {sw['n_recommended'].median():.0f} "
                   f"| {_f(sw['package_he_oos'].median())} |")
    return "\n".join(out)


if __name__ == "__main__":
    sys.exit(main())
