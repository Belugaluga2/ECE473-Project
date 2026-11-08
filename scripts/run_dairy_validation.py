"""Reproduce Maya's observed-production dairy pilot, offline from committed inputs.

Writes only maya_dairy_* outputs, doc 25's AUTO block and its figure. Does not trade.
Run after pull_dairy_validation.py once; fresh clones use the committed processed CSV.
"""
from __future__ import annotations

import json
import platform
from datetime import datetime
from importlib.metadata import version
from zoneinfo import ZoneInfo

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from agri_hedge import dairy as dy
from agri_hedge import dairy_validation as dv
from agri_hedge.config import DOCS, PROCESSED
from agri_hedge.docs_util import write_auto_block

LABELS = {"no_hedge": "No cover", "airport_dd80": "Airport temperature",
          "regional_thi69_days": "Regional THI >=69.4", "regional_thi79_days": "Regional THI >=79.3"}


def experiment(baseline_method):
    monthly = pd.read_csv(PROCESSED / "maya_dairy_state_month.csv")
    annual = dv.annual_panel(monthly, dy.load_daily(), baseline_method=baseline_method)
    annual["baseline"] = baseline_method
    availability, summaries, year_rows = [], [], []
    for state, group in annual.groupby("state"):
        group = group.sort_values("year")
        earlier = group.year <= dv.TRAIN_END
        valid = group.loss_fraction.notna()
        train = earlier & valid
        test = group.year.between(dv.TEST_START, dv.TEST_END) & valid
        available = {"state": state, "baseline": baseline_method, "complete_seasons": len(group),
                     "n_train": int(train.sum()), "n_test": int(test.sum()),
                     "test_years": ", ".join(str(int(y)) for y in group.loc[test, "year"]),
                     "status": "usable" if train.sum() >= 8 else "insufficient training data"}
        availability.append(available)
        print(available, flush=True)
        if available["status"] != "usable":
            continue
        loss = group.loc[test, "loss_fraction"].to_numpy()
        for name in ("no_hedge", *dv.INDICES):
            if name == "no_hedge":
                payout = np.zeros(len(group))
                premium = payout.copy()
                trigger, slope = np.nan, 0.0
                cover = None
            else:
                cover = dv.fit_cover(group.year, group[name], group.loss_fraction)
                payout = cover.payout(group[name])
                premium = dv.earlier_premiums(group.year, group[name], cover)
                trigger, slope = cover.trigger, cover.slope
            h, price = payout[test], premium[test]
            result = {"state": state, "baseline": baseline_method, "index": name, "n_train": int(train.sum()),
                      "trigger": trigger, "slope": slope, **dv.protection_metrics(loss, h, price)}
            low, high = dv.he_interval(loss, h)
            result.update(he_ci_low=low, he_ci_high=high)
            notionals = group.loc[test, "baseline_kg_cow"].to_numpy() * dv.HERD * dv.USD_PER_KG
            result["mean_loss_usd_scenario"] = float(np.mean(notionals * loss))
            result["mean_premium_usd_scenario"] = float(np.mean(notionals * price))
            for load in (0.0, .25):
                p = dv.earlier_premiums(group.year, group[name], cover, load)[test] if cover else price
                result[f"net_he_load_{int(load * 100)}"] = dv.protection_metrics(loss, h, p)["he_net"]
            summaries.append(result)
            for (_, r), hh, pp in zip(group.loc[test].iterrows(), h, price):
                year_rows.append({"state": state, "baseline": baseline_method, "year": int(r.year), "index": name,
                    "observed_kg_cow": r.milk_kg_cow, "baseline_kg_cow": r.baseline_kg_cow,
                    "loss_fraction": r.loss_fraction, "payout_fraction": hh, "premium_fraction": pp,
                    "net_residual_fraction": r.loss_fraction - hh + pp})
            print(state, name, f"HE {result['he_gross']:.3f}, net {result['he_net']:.3f}, "
                  f"recovery {result['payout_recovery']:.1%}", flush=True)
    return annual, summaries, availability, year_rows


def main():
    runs = [experiment(method) for method in ("growth", "trend")]
    pd.concat([run[0] for run in runs], ignore_index=True).to_csv(PROCESSED / "maya_dairy_annual.csv", index=False)
    summary = pd.DataFrame([row for run in runs for row in run[1]])
    availability = [row for run in runs for row in run[2]]
    year_rows = [row for run in runs for row in run[3]]
    summary.to_csv(PROCESSED / "maya_dairy_validation_summary.csv", index=False)
    pd.DataFrame(year_rows).to_csv(PROCESSED / "maya_dairy_validation_years.csv", index=False)
    pd.DataFrame(availability).to_csv(PROCESSED / "maya_dairy_availability.csv", index=False)
    environment = {"python": platform.python_version(),
        "packages": {name: version(name) for name in ("numpy", "pandas", "scipy", "matplotlib")},
        "bootstrap_seed": 473, "bootstrap_repetitions": 2000}
    (PROCESSED / "maya_dairy_environment.json").write_text(json.dumps(environment, indent=2), encoding="utf-8")
    source = json.loads((PROCESSED / "maya_dairy_source.json").read_text())
    write_auto_block(DOCS / "analysis" / "25_maya_dairy_validation.md", "Maya dairy validation", tables(summary, availability, source))
    figure(summary)
    print("Wrote Maya pilot outputs and doc 25")


def tables(summary, availability, source):
    lines = ["## Observed-production results", "",
        "These are fixed-slope seasonal contracts evaluated against state-average production shortfalls.",
        "The airport and regional THI indices differ in location, threshold **and** measurement, so their contrast",
        "does not isolate humidity. No seasonal contract is claimed executable. No Dairy-RP policy is simulated.", "",
        "Growth is the primary forecast baseline; trend is the exploratory missing-data sensitivity.", "",
        "| State | Baseline | Complete seasons | Training shortfalls | Holdout seasons | Status |",
        "|---|---|---:|---:|---:|---|"]
    for row in availability:
        lines.append(f"| {row['state']} | {row['baseline']} | {row['complete_seasons']} | {row['n_train']} | {row['n_test']} | {row['status']} |")
    lines += ["", "HE: 1 = perfect variance reduction; 0 = none; negative = added variance. The interval is a",
        "paired-year bootstrap conditional on a fixed fitted hedge; it omits fitting/selection uncertainty.", "",
        "| State | Baseline | Cover | Gross HE [95% interval] | Net HE, 10% load | Payout recovery | 95th-percentile net shortfall / expected milk |",
        "|---|---|---|---:|---:|---:|---:|"]
    for _, r in summary.iterrows():
        lines.append(f"| {r.state} | {r.baseline} | {LABELS[r['index']]} | {r.he_gross:.2f} [{r.he_ci_low:.2f}, {r.he_ci_high:.2f}] | "
            f"{r.he_net:.2f} | {r.payout_recovery:.0%} | {r.p95_net_shortfall_fraction:.2%} |")
    lines += ["", "Actual evaluated years (source gaps and baseline requirements can reduce the nominal period):", ""]
    for row in availability:
        if row["status"] == "usable":
            lines.append(f"- {row['state']}, {row['baseline']}: {row['test_years']}.")
    lines += ["", "### How to distinguish better from rainfall", "",
        "| Evidence | What is scored | Result / source | Why not directly comparable |",
        "|---|---|---|---|"]
    rain = pd.read_csv(PROCESSED / "m2_companion_holdout.csv")
    picked = rain.dropna(subset=["companion_he_2001_2025"])
    lines += [f"| Rainfall Companion, doc 21 | PRF-style gap-month payout | Median holdout HE {picked.companion_he_2001_2025.median():.2f} | Weather-index target; 2001-2025; selected farm-months |",
        f"| Rainfall replacement, same picked cohort | PRF payout | Median HE {picked.prf_intervals_he_2001_2025.median():.2f} | Different coverage from dairy |"]
    for method in ("growth", "trend"):
        for index in dv.INDICES:
            rows = summary[(summary["index"] == index) & (summary.baseline == method)]
            lines.append(f"| Dairy {LABELS[index]}, {method} baseline | Observed state-production shortfall | Median HE {rows.he_gross.median():.2f} | State averages; missing-data-restricted {dv.TEST_START}-{dv.TEST_END}; different target |")
    if (PROCESSED / "dairy_heat_summary.csv").exists():
        old = pd.read_csv(PROCESSED / "dairy_heat_summary.csv")
        old = old[old.years_paid_test >= 5]
        lines += [f"| Old dairy ladder, doc 24 | Temperature-defined loss | Median seasonal HE {old.he_ladder_seasonal.median():.2f}, simulated day-ahead {old.he_day_ahead.median():.2f} | Modeled target, hypothetical strikes/listing and simulated prices |"]
    market_path = PROCESSED / "maya_dairy_market_check.json"
    if market_path.exists():
        market = json.loads(market_path.read_text(encoding="utf-8"))
        local_time = datetime.fromisoformat(market["observed_at_utc"]).astimezone(ZoneInfo("America/New_York"))
        lines += ["", "### Dated market availability", "",
            f"Public API observation: {market['observed_at_utc']} ({local_time:%Y-%m-%d %H:%M %Z}).",
            "Only the selected daily-high series were checked; this is not an audit of all seasonal products.", "",
            "| Series | Open daily events | Listed days for target summer | Target year |",
            "|---|---|---:|---:|"]
        for row in market["rows"]:
            lines.append(f"| {row['series']} | {', '.join(row['open_event_dates'])} | {row['listed_summer_days']} | {row['target_summer_year']} |")
        lines += ["", "Source URLs and timestamps: `maya_dairy_market_check.json`; collected by",
            "`scripts/pull_dairy_market_check.py`. A market listing does not prove sufficient depth."]
    lines += ["", "### Numbers and assumptions", "", "| Quantity | Value | Source / status |", "|---|---|---|",
        f"| Prepared observed records | {source['rows']} state-months | `maya_dairy_state_month.csv`; source DOI {source['record_doi']} |",
        f"| Raw milk conversion max absolute error | {source['source_conversion_max_abs_error']:.2g} kg/cow/day | Raw NASS workbook versus publication panel |",
        f"| Cover fit / nominal evaluation years | through {dv.TRAIN_END} / {dv.TEST_START}-{dv.TEST_END} | Cover terms fixed; production baseline and prices update from earlier observations only |",
        "| Pre-season baseline | Prior summer yield times mean log growth over five completed annual changes | Six consecutive earlier summers required; recalculated each spring |",
        "| Training target | Positive shortfall relative to that earlier-only baseline | Observed yield; all causes, not causal heat loss |",
        f"| Maximum payout | {dv.LIMIT_FRACTION:.0%} of expected summer production | Fixed scenario cap |",
        "| Trigger / slope | Earlier weather mean / one nonnegative least-squares slope on earlier shortfalls | No validation threshold search; capped after fitting |",
        "| Model premium | Earlier-weather expected payout times 1.10 | Hypothetical; 0% and 25% load sensitivity in summary CSV |",
        f"| Dollar illustration | {dv.HERD} cows, ${dv.MILK_PRICE_CWT:g}/cwt | Fixed scenario assumptions, not historical prices or profit |",
        "| Regional THI index thresholds | Approx. 69.4 and 79.3 | Publication's CreateFigure2a.R; cow-weighted daily-maximum THI bins |",
        "| Geographic weather weights | Published 2002-2012 cow inventories | Fixed study specification; future relative to earliest years |",
        "| Individual-farm validation / government-policy price comparison | Not established / not performed | No individual milk records or historical Dairy-RP quotes used |",
        "| Executable seasonal hedge / market-maker capital | Not established / not modeled | A model premium is not a live quote |", "",
        "## Reproduce", "", "```powershell",
        r".\.venv\Scripts\python.exe scripts/run_dairy_validation.py", "# Optional raw refresh; needs internet and the dairy extra:",
        r'.\.venv\Scripts\python.exe -m pip install -e ".[dairy]"',
        r".\.venv\Scripts\python.exe scripts/pull_dairy_validation.py",
        r".\.venv\Scripts\python.exe scripts/pull_dairy_market_check.py", "```", "",
        "![Observed dairy pilot](../figures/maya_dairy_validation.png)"]
    return "\n".join(lines)


def figure(summary):
    fig, axes = plt.subplots(2, 2, figsize=(11, 8), layout="constrained")
    colors = ["#3978a8", "#e19b35", "#369878"]
    for ax, ((method, state), group) in zip(axes.flat, summary.groupby(["baseline", "state"])):
        group = group[group["index"] != "no_hedge"]
        y = np.arange(len(group))
        ax.axvline(0, color="#777777", linewidth=1)
        for pos, (_, row), color in zip(y, group.iterrows(), colors):
            ax.plot([row.he_ci_low, row.he_ci_high], [pos, pos], color=color, linewidth=2)
            ax.scatter(row.he_gross, pos, color=color, s=45, zorder=3)
        n_test = int(group.n_test.iloc[0])
        ax.set(yticks=y, yticklabels=[LABELS[k] for k in group["index"]], title=f"{state.title()} — {method} baseline (n={n_test})",
               xlabel="Held-out gross HE (interval conditional on fitted cover)")
        ax.grid(axis="x", alpha=.2)
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle("Does seasonal heat cover protect observed milk-production shortfalls?\n"
                 "State averages, 2001-2018; proposed contracts, not executable trades", fontsize=12)
    fig.savefig(DOCS / "figures" / "maya_dairy_validation.png", dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    main()
