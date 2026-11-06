"""Reproduce doc 23: farmer-specific Kalshi replacement costs and held-out coverage.

Default is a deterministic planning scenario as of 2026-11-06, not live quotes.
--live attempts current books and writes a separate observation JSON (no trades).
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from agri_hedge.comparison import compare, farms
from agri_hedge.config import DOCS, PROCESSED
from agri_hedge.docs_util import write_auto_block
from agri_hedge.webapp.server import _clean


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="observe current books; write a separate JSON")
    args = parser.parse_args(argv)
    now = datetime.now(timezone.utc) if args.live else datetime(2026, 11, 6, tzinfo=timezone.utc)
    year = now.year + 1
    results, rows, years, legs = [], [], [], []
    for f in farms():
        result = compare({"farm_id": f["farm_id"], "contract_year": year,
                          "price_source": "auto" if args.live else "model"}, now=None if args.live else now)
        results.append(result)
        for s in result["strategies"]:
            common = {"farm_id": f["farm_id"], "strategy": s["id"]}
            rows.append({**common, "acres": f["acres"], "prf_producer_usd": result["prf"]["producer_premium_usd"],
                         "prf_full_usd": result["prf"]["total_premium_usd"],
                         "kalshi_estimated_usd": s["cost"]["cost_usd"], "price_gap_usd": s["price_gap_usd"],
                         "cost_ratio": s["cost_ratio"], **s["metrics"],
                         "same_coverage": False, "arbitrage": False,
                         "book_check_attempted": s["execution"]["checked"],
                         "fillable_fraction": s["execution"]["fill_fraction"]})
            years.extend({**common, **b} for b in s["backtest"])
            legs.extend({**common, **t} for t in s["ticket"])
        s = result["strategies"][0]
        print(f"{f['farm_id']}: PRF ${result['prf']['producer_premium_usd']:,.0f}; "
              f"Kalshi estimated ${s['cost']['cost_usd']:,.0f}; holdout HE {s['metrics']['he']:.2f}", flush=True)
        if args.live:
            print(f"  Market data: {result['market_data']}", flush=True)
    payload = {"as_of": now.isoformat(), "live_requested": args.live, "results": results}
    if args.live:
        path = PROCESSED / "farmer_comparison_live.json"
        path.write_text(json.dumps(_clean(payload), indent=2, allow_nan=False) + "\n")
        print(path)
        return 0
    frame = pd.DataFrame(rows)
    frame.to_csv(PROCESSED / "farmer_comparison_summary.csv", index=False)
    pd.DataFrame(years).to_csv(PROCESSED / "farmer_comparison_holdout.csv", index=False)
    pd.DataFrame(legs).to_csv(PROCESSED / "farmer_comparison_orders.csv", index=False)
    (PROCESSED / "farmer_comparison.json").write_text(json.dumps(_clean(payload), indent=2, allow_nan=False) + "\n")
    best = frame[frame.strategy == "best_fit"]
    equal = frame[frame.strategy == "equal_mean"]
    lines = ["### Farmer results — estimated prices, fixed holdout portfolios", "",
             "Positive price gap would mean estimated savings; these hedges have different coverage.", "",
             "| Farm | PRF producer / full premium | Kalshi estimate | Cost / producer premium | Holdout HE | Same-year PRF dollars recovered | Worst holdout shortfall | Complete holdout years |",
             "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for _, r in best.iterrows():
        lines.append(f"| {r.farm_id} | ${r.prf_producer_usd:,.0f} / ${r.prf_full_usd:,.0f} | "
                     f"${r.kalshi_estimated_usd:,.0f} | {r.cost_ratio:.2f}× | {r.he:.2f} | "
                     f"{r.payout_recovery:.1%} | ${r.worst_shortfall_usd:,.0f} | {r.n_years} |")
    lines += ["", "### Numbers and sources", "",
              "| Claim | Value | Source |", "|---|---:|---|",
              f"| Best-fit hedges cheaper than subsidized PRF | {int((best.price_gap_usd > 0).sum())} / {len(best)} | `farmer_comparison_summary.csv`, best_fit |",
              f"| Best-fit median cost / producer premium | {best.cost_ratio.median():.2f}× | Same CSV |",
              f"| Best-fit median cost / full premium | {(best.kalshi_estimated_usd / best.prf_full_usd).median():.2f}× | Same CSV |",
              f"| Best-fit median holdout HE | {best.he.median():.2f} | Same CSV, 2001–2025 complete years |",
              f"| Best-fit median same-year recovery | {best.payout_recovery.median():.1%} | Same CSV; sum min(PRF, hedge) / sum PRF |",
              f"| Best-fit annual PRF producer premium / hedge estimate, all farms | ${best.prf_producer_usd.sum():,.0f} / ${best.kalshi_estimated_usd.sum():,.0f} | Same CSV |",
              f"| Equal-training-mean median cost / producer premium | {equal.cost_ratio.median():.2f}× | Same CSV, equal_mean |",
              f"| Equal-training-mean median holdout HE | {equal.he.median():.2f} | Same CSV |",
              f"| Equal-training-mean cheaper than subsidized PRF | {int((equal.price_gap_usd > 0).sum())} / {len(equal)} | Same CSV |",
              f"| Same coverage / demonstrated PRF arbitrage | 0 / 0 | Different settlement functions; no offsetting short PRF trade identified |",
              "| Live books checked in this reproducible table | 0 | Model-only run; no inference of current market depth |",
              "| PRF scenario terms | 2026 | `prf_scenario_results.csv`, `farms.yaml` |",
              "| Fit / holdout years | 1951–2000 / 2001–2025 | `comparison.TRAIN` / `TEST`; incomplete years omitted |",
              "| Forward price probability window | 1991–2025 | `hedge_builder.FAIR_WINDOW`; not used in fitting |",
              "| Quote date / contract year | 2026-11-06 / 2027 | This script's deterministic default |",
              "| Model half spread | 2.25 cents | Doc 05 historical median spread / 2 |",
              "| Funding rate / assumed settlement delay | 4.05% annual / 2 days after month-end | Scenario assumptions; historical rate in `pricing.DEFAULT_TBILL_RATE` |",
              "| Taker rate / rounding assumption | 0.07 / up to $0.01 per price-level fill | Repository retail model; [Kalshi fee schedule](https://kalshi.com/docs/kalshi-fee-schedule.pdf) has account-specific rounding and multipliers |",
              "| Freshness threshold / material shortfall threshold | 120 seconds / $1 | `comparison.MAX_BOOK_AGE_SECONDS` / `coverage_metrics` |"]
    write_auto_block(DOCS / "analysis" / "23_farmer_price_comparison.md", "farmer comparison (scripts/run_farmer_comparison.py)", "\n".join(lines))
    fig, (a, b) = plt.subplots(1, 2, figsize=(12, 5), layout="constrained")
    yy = np.arange(len(best))
    a.barh(yy, best.cost_ratio, color="#2a6f97")
    a.axvline(1, color="#a34c1e", linestyle="--", label="Same producer cost")
    a.set(yticks=yy, yticklabels=best.farm_id, xlabel="Estimated Kalshi cost / PRF producer premium",
          title="All comparisons use each farm's premium")
    a.invert_yaxis()
    a.legend(fontsize=8)
    b.barh(yy, best.payout_recovery * 100, color="#52816b")
    b.set(yticks=yy, yticklabels=[], xlim=(0, 100), xlabel="PRF payout dollars matched in the same year (%)",
          title="Coverage on held-out years")
    b.invert_yaxis()
    fig.suptitle("Kalshi replacement screen — estimates, not equivalent coverage or arbitrage", fontsize=12)
    fig.savefig(DOCS / "figures" / "farmer_price_comparison.png", dpi=160)
    plt.close(fig)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
