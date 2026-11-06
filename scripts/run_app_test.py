"""Milestone 2, W5 (Evan): test the app against the USDA PRF benchmark (doc 19).

Run from the repo root:   python scripts/run_app_test.py [--live] [--n-grids 150]

Everything goes through `agri_hedge.platform.quote`, the same function the web app calls.

1. Farm scenarios. Each of the 11 representative farms types its own location, PRF intervals,
   coverage and protection into the app (station chosen automatically, estimated prices so the
   run is reproducible). Two budgets: the app's recommendation and the farm's real PRF producer
   premium. Compared with PRF: what the farmer pays, cost per $1 of expected payout, hedge
   effectiveness out of sample, and the remaining basis risk (worst year, years the hedge paid
   less than half of what PRF paid). Also checks the app's PRF premium estimate against the real
   2026 premium, and that the app reproduces doc 15's lowest-error hedge.
2. Coverage sweep. The same "hay season" request (Apr-May 40%, Jun-Jul 35%, Aug-Sep 25%, 90%
   coverage, $100,000 protection) at a random sample of the grids the app can serve, to map hedge
   quality against distance to the station.
3. Live smoke test (--live). One quote with live Kalshi prices; records how many orders were
   priced from a book.

Outputs: data/processed/m2_app_test_farms.csv, m2_app_test_sweep.csv, m2_app_live_smoke.json,
docs/figures/m2_app_vs_prf.png, m2_app_sweep.png, AUTO tables in docs/analysis/19_app_test.md.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

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

DOC = DOCS / "analysis" / "19_app_test.md"
HAY = [{"label": "Apr-May", "share": 0.40}, {"label": "Jun-Jul", "share": 0.35}, {"label": "Aug-Sep", "share": 0.25}]


def farm_params(F: dict, budget) -> dict:
    f = F["farm"]
    return {"lat": f["lat"], "lon": f["lon"], "coverage": f["coverage_level"], "protection": F["protection"],
            "windows": [{"label": k, "share": v} for k, v in f["interval_allocation"].items()],
            "price_source": "model", "budget": budget}


def farm_tests() -> pd.DataFrame:
    rows = []
    s15 = pd.read_csv(PROCESSED / "m2_optimizer_summary.csv")
    for F in hb.load_farm_requests():
        prf = F["prf_ncei_usd"].loc[1951:2025]
        prf_mean = float(prf.mean())
        for bname, budget in (("app recommendation", "recommended"), ("PRF producer premium", F["producer_premium"]),
                              ("lowest error", "lowest_error")):
            q = pf.quote(farm_params(F, budget))
            h, b = q["hedge"], q["backtest"]
            yrs = np.array(b["years"])
            hedge = pd.Series(b["hedge_usd"], index=yrs)
            target = pd.Series(b["target_usd"], index=yrs)
            paid = prf.reindex(yrs)
            big = paid > 0.02 * F["protection"]
            rows.append({
                "farm_id": F["farm_id"], "budget_rule": bname, "station_chosen": q["station"]["key"],
                "study_station": F["request"].station_key, "app_grid": q["grid"]["grid_id"],
                "farm_grid": F["request"].grid_id, "distance_mi": q["station"]["distance_mi"],
                "protection_usd": F["protection"],
                "app_cost_usd": h["cost_usd"], "app_expected_payout_usd": h["expected_payout_usd"],
                "app_cost_per_dollar": h["cost_per_dollar_expected"], "app_he_in": h["he_in_sample"],
                "app_he_oos": h["he_out_of_sample"],
                "prf_producer_premium_usd": F["producer_premium"], "prf_total_premium_usd": F["total_premium"],
                "prf_mean_payout_usd": prf_mean,
                "prf_producer_per_dollar": F["producer_premium"] / prf_mean,
                "prf_full_per_dollar": F["total_premium"] / prf_mean,
                "app_est_producer_premium_usd": q["prf_benchmark"]["est_producer_premium_usd"],
                "worst_year": b["worst_year"], "worst_shortfall_usd": b["worst_shortfall_usd"],
                "prf_pay_years": int(big.sum()),
                "hedge_under_half_years": int(((hedge < 0.5 * paid) & big).sum()),
                "hedge_paid_no_prf_years": int(((hedge > 0.02 * F["protection"]) & (paid <= 0)).sum()),
                "target_vs_prf_max_diff_usd": float((target - paid).abs().max()),
                "doc15_lowest_error_cost_usd": float(s15[(s15["farm_id"] == F["farm_id"]) &
                                                         (s15["point"] == "lowest_error")]["cost"].iloc[0]),
            })
        print(F["farm_id"], "done", flush=True)
    return pd.DataFrame(rows)


def sweep(n: int, seed: int = 473) -> pd.DataFrame:
    grids = sorted(hb.covered_grids())
    rng = np.random.default_rng(seed)
    pick = rng.choice(grids, size=min(n, len(grids)), replace=False)
    rows = []
    for i, g in enumerate(pick):
        lat, lon = grid_id_to_center(int(g))
        try:
            q = pf.quote({"lat": lat, "lon": lon, "coverage": 0.9, "protection": 100_000, "windows": HAY,
                          "price_source": "model", "budget": "recommended"})
        except ValueError as exc:
            rows.append({"grid_id": int(g), "lat": lat, "lon": lon, "error": str(exc)})
            continue
        h = q["hedge"]
        rows.append({"grid_id": int(g), "lat": lat, "lon": lon, "station": q["station"]["key"],
                     "distance_mi": q["station"]["distance_mi"], "he_oos": h["he_out_of_sample"],
                     "he_in": h["he_in_sample"], "cost_usd": h["cost_usd"],
                     "cost_per_dollar": h["cost_per_dollar_expected"],
                     "expected_payout_usd": h["expected_payout_usd"],
                     "target_mean_usd": q["prf_benchmark"]["expected_payout_usd"]})
        if (i + 1) % 25 == 0:
            print(f"sweep {i + 1}/{len(pick)}", flush=True)
    return pd.DataFrame(rows)


def live_smoke() -> dict:
    F = hb.load_farm_requests()[0]
    p = farm_params(F, "recommended")
    p["price_source"] = "auto"
    p["windows"] = [{"label": "Dec", "share": 0.5}, {"label": "Jan", "share": 0.5}]
    q = pf.quote(p, loyo=False)
    return {"run_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "request": p,
            "legs_priced_from_book": q["hedge"]["legs_priced_from_order_book"], "legs": q["hedge"]["legs"],
            "live_reference": q["live_reference"], "ticket": q["ticket"], "elapsed_s": q["elapsed_s"]}


def figures(ft: pd.DataFrame, sw: pd.DataFrame) -> None:
    rec = ft[ft["budget_rule"] == "app recommendation"].set_index("farm_id")
    pp = ft[ft["budget_rule"] == "PRF producer premium"].set_index("farm_id")
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.3))
    x = np.arange(len(rec))
    ax = axes[0]
    ax.bar(x - 0.2, rec["prf_producer_per_dollar"], 0.4, color="#8d99ae", label="PRF, producer pays (after subsidy)")
    ax.bar(x + 0.2, rec["app_cost_per_dollar"], 0.4, color="#2a6f97", label="App hedge (recommended)")
    ax.axhline(1, color="k", lw=0.8, ls="--")
    ax.set_xticks(x, rec.index, rotation=35, ha="right", fontsize=8)
    ax.set_ylabel("Cost per $1 of expected payout")
    ax.legend(fontsize=8)
    ax.set_title("Price")
    ax = axes[1]
    ax.bar(x - 0.2, pp["app_he_oos"], 0.4, color="#c1121f", label="Budget = PRF producer premium")
    ax.bar(x + 0.2, rec["app_he_oos"], 0.4, color="#2a6f97", label="App recommendation")
    ax.axhline(1, color="#8d99ae", lw=2, label="PRF itself (pays on the farm's grid)")
    ax.set_xticks(x, rec.index, rotation=35, ha="right", fontsize=8)
    ax.set_ylabel("Hedge effectiveness vs PRF payout, out of sample")
    ax.set_ylim(min(0, pp["app_he_oos"].min() - 0.05), 1.05)
    ax.legend(fontsize=8, loc="upper right")
    ax.set_title("Fit")
    fig.tight_layout()
    fig.savefig(FIGURES / "m2_app_vs_prf.png", dpi=150)
    plt.close(fig)

    s = sw.dropna(subset=["he_oos"])
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    ax = axes[0]
    for st, d in s.groupby("station"):
        ax.scatter(d["distance_mi"], d["he_oos"], s=14, label=st, alpha=0.8)
    ax.set_xlabel("Distance from grid to settlement station (miles)")
    ax.set_ylabel("Hedge effectiveness, out of sample")
    ax.axhline(0.6, color="#2b9348", lw=0.8, ls="--")
    ax.axhline(0.3, color="#b5651d", lw=0.8, ls="--")
    ax.legend(fontsize=7, ncol=2)
    ax.grid(alpha=0.3)
    ax.set_title("Hay-season hedge quality across the app's area")
    ax = axes[1]
    sc = ax.scatter(s["lon"], s["lat"], c=s["he_oos"].clip(-0.2, 1), cmap="viridis", vmin=-0.2, vmax=1, s=18)
    st = hb.station_table()
    ax.scatter(st["lon"], st["lat"], marker="*", color="#c1121f", s=60)
    ax.set_xlim(s["lon"].min() - 1, s["lon"].max() + 1)
    ax.set_ylim(s["lat"].min() - 1, s["lat"].max() + 1)
    fig.colorbar(sc, ax=ax, label="HE out of sample")
    ax.set_title("Map (stars = Kalshi stations)")
    fig.tight_layout()
    fig.savefig(FIGURES / "m2_app_sweep.png", dpi=150)
    plt.close(fig)


def _f(v, nd=2):
    return "" if pd.isna(v) else f"{v:,.{nd}f}"


def tables(ft: pd.DataFrame, sw: pd.DataFrame, smoke: dict | None) -> str:
    out = ["### Farm scenarios typed into the app", "",
           "| Farm | Station picked (mi) | PRF: producer pays | PRF $/$1 expected | App recommended: cost | App $/$1 | App HE out of sample "
           "| Budget = PRF premium: HE out of sample | Worst year (shortfall) | Years hedge < half of PRF / PRF paid |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for fid, d in ft.groupby("farm_id", sort=False):
        r = d[d["budget_rule"] == "app recommendation"].iloc[0]
        p = d[d["budget_rule"] == "PRF producer premium"].iloc[0]
        out.append(f"| {fid} | {r['station_chosen']} ({r['distance_mi']:.0f}) | ${r['prf_producer_premium_usd']:,.0f} "
                   f"| {_f(r['prf_producer_per_dollar'])} | ${r['app_cost_usd']:,.0f} | {_f(r['app_cost_per_dollar'])} "
                   f"| {_f(r['app_he_oos'])} | {_f(p['app_he_oos'])} | {r['worst_year']} (${r['worst_shortfall_usd']:,.0f}) "
                   f"| {r['hedge_under_half_years']} / {r['prf_pay_years']} |")
    rec = ft[ft["budget_rule"] == "app recommendation"]
    pp = ft[ft["budget_rule"] == "PRF producer premium"]
    le = ft[ft["budget_rule"] == "lowest error"]
    est_err = (rec["app_est_producer_premium_usd"] / rec["prf_producer_premium_usd"] - 1)
    out += ["", "### Totals and checks", "",
            "| Measure | Value |", "|---|---|",
            f"| PRF producer premiums, 11 farms | ${rec['prf_producer_premium_usd'].sum():,.0f} / yr |",
            f"| PRF full premiums, 11 farms | ${rec['prf_total_premium_usd'].sum():,.0f} / yr |",
            f"| App recommended hedges, 11 farms | ${rec['app_cost_usd'].sum():,.0f} / yr |",
            f"| App lowest-error hedges, 11 farms | ${le['app_cost_usd'].sum():,.0f} / yr |",
            f"| Median HE out of sample: recommended / PRF-premium budget / lowest error | "
            f"{_f(rec['app_he_oos'].median())} / {_f(pp['app_he_oos'].median())} / {_f(le['app_he_oos'].median())} |",
            f"| Farms where the app picked the study station | {(rec['station_chosen'] == rec['study_station']).sum()} of {len(rec)} |",
            f"| Farms where the app's grid = the farm's PRF grid | {(rec['app_grid'] == rec['farm_grid']).sum()} of {len(rec)} |",
            f"| App target vs PRF indemnity, largest gap in any farm-year | ${ft['target_vs_prf_max_diff_usd'].max():,.0f} |",
            f"| App lowest-error cost vs doc 15, largest gap | ${(le['app_cost_usd'] - le['doc15_lowest_error_cost_usd']).abs().max():,.2f} |",
            f"| App's PRF premium estimate vs real 2026 producer premium | median {est_err.median():+.0%}, range {est_err.min():+.0%} to {est_err.max():+.0%} |",
            f"| Farm-years the hedge paid > 2% of protection while PRF paid nothing (recommended) | {rec['hedge_paid_no_prf_years'].sum()} |"]
    s = sw.dropna(subset=["he_oos"])
    if len(s):
        bins = pd.cut(s["distance_mi"], [0, 25, 50, 75, 100, 150, 400])
        g = s.groupby(bins, observed=True)
        out += ["", f"### Coverage sweep: hay-season request at {len(s)} random grids", "",
                "| Distance to station | Grids | Median HE out of sample | Share with HE >= 0.6 | Share with HE < 0.3 | Median cost per $1 |",
                "|---|---|---|---|---|---|"]
        for k, d in g:
            out.append(f"| {k} mi | {len(d)} | {_f(d['he_oos'].median())} | {(d['he_oos'] >= 0.6).mean():.0%} "
                       f"| {(d['he_oos'] < 0.3).mean():.0%} | {_f(d['cost_per_dollar'].median())} |")
        out.append(f"| all | {len(s)} | {_f(s['he_oos'].median())} | {(s['he_oos'] >= 0.6).mean():.0%} "
                   f"| {(s['he_oos'] < 0.3).mean():.0%} | {_f(s['cost_per_dollar'].median())} |")
    if smoke:
        out += ["", "### Live smoke test", "",
                f"Run {smoke['run_utc']}: DFW_hay location covering Dec and Jan. {smoke['legs_priced_from_book']} of "
                f"{smoke['legs']} orders priced from a live book; {len(smoke['live_reference'])} open markets seen for "
                f"the series; quote took {smoke['elapsed_s']}s (without the out-of-sample refits)."]
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="also run one quote with live Kalshi prices")
    ap.add_argument("--n-grids", type=int, default=150)
    a = ap.parse_args(argv)
    ft = farm_tests()
    ft.to_csv(PROCESSED / "m2_app_test_farms.csv", index=False)
    sw = sweep(a.n_grids)
    sw.to_csv(PROCESSED / "m2_app_test_sweep.csv", index=False)
    smoke = None
    if a.live:
        smoke = live_smoke()
        (PROCESSED / "m2_app_live_smoke.json").write_text(json.dumps(smoke, indent=1, default=pf.json_default))
    elif (PROCESSED / "m2_app_live_smoke.json").exists():
        smoke = json.loads((PROCESSED / "m2_app_live_smoke.json").read_text())
    figures(ft, sw)
    t = tables(ft, sw, smoke)
    write_auto_block(DOC, "app test tables (scripts/run_app_test.py)", t)
    print(t)
    return 0


if __name__ == "__main__":
    sys.exit(main())
