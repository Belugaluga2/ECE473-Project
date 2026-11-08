"""Offline reproduction of doc 27's fixed multi-county study; never retunes on final scores."""
from __future__ import annotations

import hashlib
import json
import platform

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy

from agri_hedge import compound_panel as cp
from agri_hedge.config import PROCESSED, ROOT

DOC = ROOT / "docs/analysis/27_compound_county_panel.md"


def table(rows, headers):
    return "\n".join(["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"]*len(headers)) + " |"]
                     + ["| " + " | ".join(map(str, row)) + " |" for row in rows])


def inputs():
    counties = pd.read_csv(PROCESSED / "panel_counties.csv", dtype={"fips": str})
    yields = pd.read_csv(PROCESSED / "panel_yields.csv", dtype={"fips": str})
    daily = pd.read_csv(PROCESSED / "panel_daily_weather.csv", dtype={"fips": str})
    return counties, yields, daily


def main():
    counties, yields, daily = inputs()
    panel, audit = cp.build_panel(counties, yields, daily)
    panel.to_csv(PROCESSED / "panel_annual.csv", index=False)
    audit.to_csv(PROCESSED / "panel_cohort_audit.csv", index=False)
    test_years = cp.common_years(panel, counties.fips.tolist(), 2010, 2024)
    test = panel[panel.year.isin(test_years)].sort_values(["year", "fips"]).copy()
    if len(test_years) < 10:
        raise ValueError("Too few common final-test years for the pre-specified study")
    models, grids, pred_rows, selected, cv_bests = {}, [], [], {}, {}
    for regime in cp.REGIMES:
        choices = []
        for family in cp.FAMILIES:
            model, grid, best = cp.select_family(panel, family, regime)
            grids.append(grid)
            cv_bests[regime, family] = best
            print(regime, family, "CV net error skill", round(best["cv_net_error_skill"], 3), flush=True)
            if model is None:
                continue
            models[regime, family] = model
            choices.append((best["cv_net_error_skill"], family))
            p = model.payout(test)
            d, h, w = model.severities(test)
            for i, row in enumerate(test.itertuples(index=False)):
                pred_rows.append({"regime": regime, "family": family, "fips": row.fips, "state": row.state,
                    "county": row.county, "role": row.role, "year": row.year, "loss_fraction": row.loss_fraction,
                    "payout_fraction": p[i], "premium_fraction": model.premium,
                    "drought": d[i], "heat": h[i], "wet_spring": w[i],
                    "baseline_bu_ac": row.baseline_bu_ac})
        score, family = max(choices, key=lambda item: item[0]) if choices else (0, "no_hedge")
        selected[regime] = family if score > 0 else "no_hedge"
        for row in test.itertuples(index=False):
            pred_rows.append({"regime": regime, "family": "no_hedge", "fips": row.fips, "state": row.state,
                "county": row.county, "role": row.role, "year": row.year, "loss_fraction": row.loss_fraction,
                "payout_fraction": 0., "premium_fraction": 0., "baseline_bu_ac": row.baseline_bu_ac})
    pred = pd.DataFrame(pred_rows)
    pd.concat(grids, ignore_index=True).to_csv(PROCESSED / "panel_cv.csv", index=False)
    pred.to_csv(PROCESSED / "panel_predictions.csv", index=False)
    summaries, county_results, differences, replication = [], [], [], []
    for (regime, family, role), group in pred.groupby(["regime", "family", "role"], sort=False):
        for sensitivity in ("all", "without_2012"):
            subset = group if sensitivity == "all" else group[group.year != 2012]
            ci = cp.paired_year_interval(subset)
            for loading in (0., .10, .25):
                premium = subset.premium_fraction.to_numpy()/(1+cp.LOAD)*(1+loading)
                met = cp.metrics(subset.loss_fraction, subset.payout_fraction, premium)
                summaries.append({"regime": regime, "family": family, "role": role,
                    "sensitivity": sensitivity, "loading": loading, "years": subset.year.nunique(),
                    "counties": subset.fips.nunique(), **met,
                    "net_skill_ci_low_at_10pct_load": ci[0], "net_skill_ci_high_at_10pct_load": ci[1]})
        for fips, local in group.groupby("fips"):
            county_results.append({"regime": regime, "family": family, "role": role, "fips": fips,
                "county": local.county.iloc[0], "state": local.state.iloc[0],
                "payout_years": int((local.payout_fraction > 1e-10).sum()), "years": local.year.nunique(),
                **cp.metrics(local.loss_fraction, local.payout_fraction, local.premium_fraction)})
    summary = pd.DataFrame(summaries)
    per_county = pd.DataFrame(county_results)
    summary.to_csv(PROCESSED / "panel_summary.csv", index=False)
    per_county.to_csv(PROCESSED / "panel_county_results.csv", index=False)
    replica_models = {}
    for regime in cp.REGIMES:
        for role in ("development", "held_out"):
            for sensitivity in ("all", "without_2012"):
                filtered = pred[(pred.regime == regime) & (pred.role == role)]
                if sensitivity == "without_2012":
                    filtered = filtered[filtered.year != 2012]
                mix = filtered[filtered.family == "mixed"]
                add = filtered[filtered.family == "additive"]
                if mix.empty or add.empty:
                    continue
                mix_skill = cp.metrics(mix.loss_fraction, mix.payout_fraction, mix.premium_fraction)["net_error_skill"]
                add_skill = cp.metrics(add.loss_fraction, add.payout_fraction, add.premium_fraction)["net_error_skill"]
                ci = cp.paired_year_interval(mix, add)
                differences.append({"regime": regime, "role": role, "sensitivity": sensitivity,
                    "mixed_minus_additive_net_skill": mix_skill-add_skill, "ci_low": ci[0], "ci_high": ci[1]})
        model = models.get((regime, "mixed"))
        if model is not None:
            train = panel[(panel.role == "development") & panel.year.isin(model.training_years)]
            coefficients = cp.fit_primitive_approximation(model, train)
            replica_models[regime] = coefficients.tolist()
            for role in ("development", "held_out"):
                local = test[test.role == role]
                target = model.payout(local)
                estimate = cp.primitive_basis(*model.severities(local)) @ coefficients
                variance = np.var(target)
                replication.append({"regime": regime, "role": role, "years": local.year.nunique(),
                    "rows": len(local), "target_mean_fraction": target.mean(),
                    "approximation_rmse_fraction": float(np.sqrt(np.mean((target-estimate)**2))),
                    "payoff_replication_he": 1-float(np.var(target-estimate))/variance if variance else np.nan,
                    "minimum_replica_fraction": estimate.min(), "negative_replica_rows": int((estimate < -1e-10).sum())})
    incremental, replica = pd.DataFrame(differences), pd.DataFrame(replication)
    incremental.to_csv(PROCESSED / "panel_incremental.csv", index=False)
    replica.to_csv(PROCESSED / "panel_replication.csv", index=False)
    main = summary[(summary.regime == "equal_premium") & (summary.loading == .10) &
                   (summary.sensitivity == "all") & (summary.role == "held_out")]
    mix = per_county[(per_county.regime == "equal_premium") & (per_county.role == "held_out") & (per_county.family == "mixed")].set_index("fips")
    add = per_county[(per_county.regime == "equal_premium") & (per_county.role == "held_out") & (per_county.family == "additive")].set_index("fips")
    advantage_count = int((mix.net_error_skill > add.net_error_skill).sum())
    interval = incremental[(incremental.regime == "equal_premium") & (incremental.role == "held_out") & (incremental.sensitivity == "all")].iloc[0]
    chosen_score = float(main.loc[main.family == selected["equal_premium"], "net_error_skill"].iloc[0])
    evidence = {"primary_selected_policy": selected["equal_premium"], "selected_final_skill_positive": chosen_score > 0,
        "mixed_increment_interval_positive": bool(interval.ci_low > 0),
        "held_out_counties_mixed_beats_additive": advantage_count,
        "interaction_evidence_checks_pass": bool(chosen_score > 0 and interval.ci_low > 0 and advantage_count >= 2)}
    source_files = ["panel_counties.csv", "panel_yields.csv", "panel_daily_weather.csv"]
    output = {"protocol": "docs/analysis/27_compound_county_panel.md", "selected": selected, "evidence": evidence,
        "final_test_years": test_years,
        "models": {f"{regime}_{family}": model.record() for (regime, family), model in models.items()},
        "replica_coefficients": replica_models,
        "input_sha256": {name: hashlib.sha256((PROCESSED/name).read_bytes()).hexdigest() for name in source_files},
        "environment": {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__,
                        "scipy": scipy.__version__, "matplotlib": matplotlib.__version__}}
    (PROCESSED / "panel_models.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
    make_figure(main, pred, selected)
    report(counties, audit, test_years, summary, per_county, incremental, replica, models, selected, evidence)
    print("PRIMARY HELD-OUT COUNTY RESULTS\n", main[["family", "he_gross", "net_error_skill", "payout_recovery"]].to_string(index=False))
    print("EVIDENCE", evidence)


def report(counties, audit, years, summary, per_county, incremental, replica, models, selected, evidence):
    headline = summary[(summary.loading == .10) & (summary.sensitivity == "all")]
    main = headline[headline.regime == "equal_premium"]
    rows = [[r.role, r.family, f"{r.he_gross:.3f}", f"{r.net_error_skill:.3f}",
             f"[{r.net_skill_ci_low_at_10pct_load:.3f}, {r.net_skill_ci_high_at_10pct_load:.3f}]",
             f"{100*r.payout_recovery:.1f}%", f"{100*r.mean_premium_fraction:.2f}%",
             f"{100*r.p95_net_shortfall_fraction:.2f}%"] for r in main.itertuples()]
    text = ["## Generated results and numbers tables", "",
        "Reproduce offline: `.venv/Scripts/python.exe scripts/run_compound_panel.py`. Download inputs "
        "only when absent: `scripts/pull_compound_panel.py` (cached public requests, no key).", "",
        table([["Panel", f"{len(counties)} counties; {(counties.role == 'development').sum()} development, {(counties.role == 'held_out').sum()} held out", "panel_counties.csv"],
               ["Final common years", ", ".join(map(str, years)), "panel_annual.csv / common_years"],
               ["Final county-year rows", f"{len(years)*len(counties)} total; {len(years)*(counties.role == 'held_out').sum()} held-out-county rows", "panel_predictions.csv, per family"],
               ["Incomplete source county-years", int((~audit.complete).sum()), "panel_cohort_audit.csv (all retained, with reasons)"],
               ["Primary premium / load / maximum payout", "1% expected production / 10% / 30%", "protocol; panel_models.json"],
               ["Quantiles / windows", "D median June-July rain; H median June-July DD29; W 75th April-May rain; scales 90th-10th", "compound_panel.fit_model"],
               ["Search size", "8 families x 3 penalties = 24 per regime; 2 regimes", "panel_cv.csv"],
               ["Production baseline", "previous 20 available observations, minimum 15", "compound.preseason_yields"],
               ["Bootstrap", "4,000 whole-year draws; seed 473; conditional fixed models", "compound_panel.paired_year_interval"],
               ["Synthetic primitive basis", "cash + 12 binary indicators (3 severities x 4 strikes: 0.10, 0.25, 0.50, 0.75)", "compound_panel.primitive_basis"]],
              ["Item", "Value", "Source"]), "",
        "Source exclusions (no imputation or replacement counties):", "",
        table([[r.fips, r.county, r.year, r.reason] for r in audit[~audit.complete].itertuples()],
              ["FIPS", "County", "Year", "Reason"]), "",
        "**Metric meanings:** HE is variance reduction. Net error skill is reduction in squared "
        "signed loss-minus-payout-plus-premium error, relative to no hedge. Neither is profit, "
        "causal damage explained, or the share of losses reimbursed. Recovery measures matched "
        "payouts capped at the observed shortfall. Premium and tail numbers are percentages of "
        "expected production. Constant fractional premiums make net HE equal gross HE.", "",
        f"**Pre-test recommendations:** primary `{selected['equal_premium']}`; secondary cap-only "
        f"`{selected['cap_only']}`. Chosen using development-county temporal validation, not final scores.", "",
        "### Primary: matched modeled premium", "",
        table(rows, ["County group", "Family", "HE", "Net error skill", "Conditional 95% interval",
                     "Loss recovered", "Mean premium", "95th net shortfall"]), "",
        "### Does the interaction add protection over the full additive benchmark?", "",
        table([[r.regime, r.role, r.sensitivity, f"{r.mixed_minus_additive_net_skill:.4f}",
                f"[{r.ci_low:.4f}, {r.ci_high:.4f}]"] for r in incremental.itertuples()],
              ["Regime", "County group", "Years", "Mixed minus additive net skill", "Paired-year 95% interval"]), "",
        "### Held-out counties, primary regime", "",
        table([[r.state, r.county, r.family, f"{r.he_gross:.3f}", f"{r.net_error_skill:.3f}",
                f"{100*r.payout_recovery:.1f}%", f"{r.payout_years}/{r.years}"] for r in per_county[(per_county.regime == 'equal_premium') &
                  (per_county.role == 'held_out')].itertuples()],
              ["State", "County", "Family", "HE", "Net error skill", "Recovery", "Payout years / test years"]), "",
        "### Remove 2012 without refitting, primary held-out counties", "",
        table([[r.family, f"{r.he_gross:.3f}", f"{r.net_error_skill:.3f}", f"{100*r.payout_recovery:.1f}%"]
                for r in summary[(summary.regime == 'equal_premium') & (summary.role == 'held_out') &
                    (summary.sensitivity == 'without_2012') & (summary.loading == .10)].itertuples()],
              ["Family", "HE", "Net error skill", "Recovery"]), "",
        "### Secondary: equal cap, prices can differ", "",
        table([[r.role, r.family, f"{r.he_gross:.3f}", f"{r.net_error_skill:.3f}", f"{100*r.mean_premium_fraction:.2f}%"]
                for r in headline[headline.regime == 'cap_only'].itertuples()],
              ["County group", "Family", "HE", "Net error skill", "Modeled premium"]), "",
        "### Primary held-out price sensitivity, no refitting", "",
        table([[family] + [f"{summary[(summary.regime == 'equal_premium') & (summary.role == 'held_out') & (summary.family == family) & (summary.sensitivity == 'all') & (summary.loading == load)].net_error_skill.iloc[0]:.3f}"
                          for load in (0., .10, .25)] for family in list(cp.FAMILIES)+['no_hedge']],
              ["Family", "Net skill: 0% load", "10% load", "25% load"]), "",
        "### Synthetic static replication of the frozen mixed payout", "",
        table([[r.regime, r.role, f"{100*r.approximation_rmse_fraction:.3f}%", f"{r.payoff_replication_he:.3f}",
                r.negative_replica_rows] for r in replica.itertuples()],
              ["Regime", "County group", "Payoff approximation RMSE / expected production", "Payoff replication HE", "Negative replica rows"]), "",
        "This is an optimistic signed-position diagnostic of the **proposed payout**, not its "
        "protection against crop loss, nor executable exchange replication. Negative replica payouts "
        "would require extra collateral. Finite strikes cause errors even for separable payoffs.", "",
        "### Frozen fitted weights and prices", "",
        table([[regime, family, model.config.ridge, ", ".join(f"{v:.6f}" for v in model.weights),
                f"{model.premium:.6f}", model.training_rows, ", ".join(map(str, model.training_years))]
                for (regime, family), model in models.items()],
              ["Regime", "Family", "Ridge", "Weights in feature-table order", "Premium fraction", "Training rows", "Training years"]), "",
        "### Pre-specified evidence checks", "",
        table([[key, value, "panel_models.json; summary and paired-year comparisons"] for key, value in evidence.items()],
              ["Check", "Result", "Source"]), "",
        "All candidates, individual county results, source suppressions, audit exclusions, payouts, "
        "costs, overpayments and tail measures are retained in the `panel_*.csv` files. Exact transforms, "
        "coefficients, input hashes and environment versions are in `panel_models.json`. "
        "Download provenance is in `panel_source_manifest.json`.", "",
        "![Primary multi-county comparison](../figures/compound_panel.png)"]
    generated = "\n".join(text)
    start, end = "<!-- AUTO: panel start -->", "<!-- AUTO: panel end -->"
    previous = DOC.read_text(encoding="utf-8")
    if start in previous:
        before, remaining = previous.split(start, 1)
        _, after = remaining.split(end, 1)
        previous = before+start+"\n"+generated+"\n"+end+after
    else:
        previous += "\n"+start+"\n"+generated+"\n"+end+"\n"
    DOC.write_text(previous, encoding="utf-8")


def make_figure(main, pred, selected):
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8), constrained_layout=True)
    families = list(cp.FAMILIES)+["no_hedge"]
    bars = main.set_index("family").reindex(families)
    axes[0].bar(np.arange(len(families)), bars.net_error_skill, color="#24788a")
    axes[0].axhline(0, color="black", lw=.8)
    axes[0].set_xticks(np.arange(len(families)), [x.replace('_', '\n') for x in families], rotation=35, ha="right", fontsize=8)
    axes[0].set_ylabel("Net squared-error reduction vs no hedge")
    axes[0].set_title("Reserved counties, equal modeled premium")
    winner = selected["equal_premium"]
    local = pred[(pred.regime == "equal_premium") & (pred.role == "held_out") & (pred.family == winner)]
    annual = local.groupby("year")[["loss_fraction", "payout_fraction", "premium_fraction"]].mean()
    axes[1].plot(annual.index, 100*annual.loss_fraction, marker="o", label="County shortfall (mean)")
    axes[1].plot(annual.index, 100*annual.payout_fraction, marker="s", label=f"Selected {winner} payout")
    axes[1].plot(annual.index, 100*annual.premium_fraction, ls="--", label="Modeled premium")
    axes[1].set_ylabel("% of expected production")
    axes[1].set_title("Selection fixed using earlier development years")
    axes[1].legend(fontsize=8)
    fig.suptitle("Proposed regional corn cover; county outcomes, gridded weather, hypothetical prices", fontsize=11)
    fig.savefig(ROOT / "docs/figures/compound_panel.png", dpi=170, metadata={"Software": "agri_hedge"})
    plt.close(fig)


if __name__ == "__main__":
    main()
