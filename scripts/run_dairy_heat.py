"""Reproduce doc 24: dairy heat-stress cover from Kalshi daily-high contracts.

Reads data/processed/dairy_daily_tmax.parquet (scripts/pull_dairy_temps.py). Writes
data/processed/dairy_heat_summary.csv, the doc 24 AUTO tables and docs/figures/dairy_heat_he.png.
Under 10 seconds.
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from agri_hedge import dairy as dy
from agri_hedge.config import DOCS, PROCESSED
from agri_hedge.docs_util import write_auto_block

DOC = DOCS / "analysis" / "24_dairy_heat_stress.md"
VIEWS = [("he_index_option", "Seasonal heat-degree-day option on the airport", "#2a78d6"),
         ("he_ladder_seasonal", "Daily-high ladder, bought before summer", "#eb6834"),
         ("he_day_ahead", "Same ladder, bought one day ahead (how Kalshi lists)", "#1baf7a")]


def _usd(x: float) -> str:
    return f"-${-x:,.0f}" if x < 0 else f"${x:,.0f}"


def main() -> int:
    daily = dy.load_daily()
    rows = []
    for s in dy.SITES:
        r = dy.evaluate(s, daily)
        p, n = r.pop("_problem"), r.pop("_ladder")
        r["filled_from_thread_share"] = float(daily[daily.site == s.site_id].airport_filled_from_thread.mean())
        sens = {f"he_day_ahead_sigma{str(sig).replace('.', '_')}": dy.day_ahead_he(p, n, p.target_usd, sig, 10) for sig in (2.5, 5.0)}
        r.update(sens)
        rows.append(r)
        print(f"{s.site_id}: basis {r['he_linear_basis']:.2f}, index {r['he_index_option']:.2f}, "
              f"ladder {r['he_ladder_seasonal']:.2f}, day-ahead {r['he_day_ahead']:.2f}", flush=True)
    d = pd.DataFrame(rows)
    d.to_csv(PROCESSED / "dairy_heat_summary.csv", index=False)

    ok = d[d.years_paid_test >= 5]          # sites where the insured excess actually paid
    lines = ["### Dairy heat stress: can Kalshi daily highs cover a summer? (2001-2025 holdout)", "",
             f"Herd of {dy.HERD:,} cows; loss = milk lost to degree-days above {dy.THRESHOLD_F:.0f} F, June-September; "
             "the insured amount is the loss above its 1951-2000 average. HE = 1 - Var(loss - hedge) / Var(loss).", "",
             "| Dairy region | Kalshi airport (miles) | Basis: farm vs airport heat load (R²) | Seasonal option HE | Ladder bought before summer HE | Bought day ahead HE | Mean insured loss / yr | Ladder cost before summer (cost / fair) | Day-ahead spread + fees / yr |",
             "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for _, r in d.iterrows():
        lines.append(f"| {r.county} | {r.airport} ({r.distance_mi:.0f}) | {r.he_linear_basis:.2f} | {r.he_index_option:.2f} | "
                     f"{r.he_ladder_seasonal:.2f} | {r.he_day_ahead:.2f} | {_usd(r.mean_target_usd)} "
                     f"({r.years_paid_test} of {r.n_test} yrs) | {_usd(r.seasonal_cost_usd)} ({r.seasonal_loading:.2f}x) | "
                     f"{_usd(r.day_ahead_friction_usd)} |")
    lines += ["", "### Numbers and sources", "", "| Claim | Value | Source |", "|---|---:|---|",
              f"| Sites where the insured excess paid in at least 5 holdout years | {len(ok)} / {len(d)} | `dairy_heat_summary.csv` (Maricopa paid in {int(d.set_index('site_id').years_paid_test['AZ_maricopa'])}) |",
              f"| Median basis R², farm vs airport seasonal heat load | {d.he_linear_basis.median():.2f} | Same CSV, holdout years |",
              f"| Median HE, seasonal option on airport heat load (those sites) | {ok.he_index_option.median():.2f} | Same CSV |",
              f"| Median HE, daily ladder bought before summer (those sites) | {ok.he_ladder_seasonal.median():.2f} | Same CSV |",
              f"| Median HE, same ladder bought day ahead (those sites) | {ok.he_day_ahead.median():.2f} | Same CSV; forecast error 3.5 F, 5-day heat waves forecast |",
              f"| Same, forecast error 2.5 F / 5.0 F | {ok.he_day_ahead_sigma2_5.median():.2f} / {ok.he_day_ahead_sigma5_0.median():.2f} | Same CSV |",
              f"| Same, upper bound (no heat wave is foreseen) | {ok.he_day_ahead_upper.median():.2f} | Same CSV, `persistence_days=1` |",
              f"| Median cost / fair value, ladder bought before summer | {d.seasonal_loading.median():.2f}x | Same CSV; 2.25-cent half spread, fees per daily order, capital from May 1 |",
              f"| Largest contracts per day on one strike | {int(d.contracts_per_day_max.max()):,} | Same CSV |",
              f"| Milk loss slope | {dy.MILK_KG_PER_THI} kg / cow / day per THI unit above 72 | Ravagnolo et al. (2000), via secondary sources (see text) |",
              f"| THI per F / milk price / herd | {dy.THI_PER_F} / ${dy.MILK_PRICE_PER_CWT:.0f} per cwt / {dy.HERD:,} cows | Assumptions; HE does not depend on them |",
              f"| Dollars lost per cow per degree-day | ${dy.USD_PER_COW_DEGDAY:.3f} | Product of the three rows above |",
              "| Kalshi daily-high listing | opens about 1.5 days before the date; 2 F brackets around the forecast | Live `KXHIGHTPHX` markets, 2026-11-06 |",
              f"| Airport days filled from the NWS threaded city record | DFW {d.set_index('site_id').filled_from_thread_share['TX_erath']:.0%}, DEN {d.set_index('site_id').filled_from_thread_share['CO_weld']:.0%} | `dairy_daily_tmax.parquet`; DFW opened 1974, DEN 1994 |",
              "| Fit / holdout / fair-price years | 1951-2000 / 2001-2025 / 1991-2025 | `dairy.TRAIN`, `TEST`, `FAIR_WINDOW` |"]
    write_auto_block(DOC, "dairy heat (scripts/run_dairy_heat.py)", "\n".join(lines))

    fig, ax = plt.subplots(figsize=(9, 4.8), layout="constrained")
    order = d.sort_values("he_index_option")
    yy = np.arange(len(order))
    ax.axvline(0, color="#8a8a85", linewidth=1)
    for i, (col, label, color) in enumerate(VIEWS):
        ax.scatter(order[col].clip(lower=-0.6), yy + (1 - i) * 0.18, s=46, color=color, label=label,
                   edgecolor="white", linewidth=1.2, zorder=3)
    ax.set(yticks=yy, yticklabels=[f"{c} ({a})" for c, a in zip(order.county, order.airport)],
           xlim=(-0.65, 1), xlabel="Hedge effectiveness on 2001-2025 (values below -0.6 drawn at -0.6)")
    ax.grid(axis="x", color="#e4e3dd", linewidth=0.8)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.legend(loc="lower right", fontsize=8, frameon=False)
    ax.set_title("Dairy heat cover from Kalshi daily highs: the strip works only if bought before summer",
                 fontsize=11, loc="left")
    fig.savefig(DOCS / "figures" / "dairy_heat_he.png", dpi=160)
    plt.close(fig)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
