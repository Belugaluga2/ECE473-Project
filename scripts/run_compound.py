"""Reproduce doc 26 offline from committed inputs; tuning never uses final-test outcomes."""
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

from agri_hedge.compound import (FAMILIES, PAIRS, TRAIN_END, build_panel, earlier_premiums,
                                net_he_interval, select_family)
from agri_hedge.config import PROCESSED, ROOT
from agri_hedge.dairy_validation import protection_metrics

DOC = ROOT / "docs/analysis/26_compound_heat_drought.md"


def table(rows, headers):
    return "\n".join(["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"]*len(headers)) + " |"]
                     + ["| " + " | ".join(map(str, row)) + " |" for row in rows])


def main():
    inputs = ["rowcrop_kane_yields.csv", "rowcrop_farm_year.csv", "compound_daily_temperature.csv"]
    panel, audit = build_panel(*(pd.read_csv(PROCESSED / name) for name in inputs))
    panel.to_csv(PROCESSED / "compound_panel.csv", index=False)
    audit.to_csv(PROCESSED / "compound_cohort_audit.csv", index=False)
    test = panel[panel.year > TRAIN_END].copy()
    if test.empty:
        raise ValueError("No complete final-test years")
    fitted, grid, predictions, summaries, selected = {}, [], [], [], {}
    for pair in PAIRS:
        family_scores = []
        for family in FAMILIES:
            model, scores, best = select_family(panel, pair, family)
            print(pair, family, "CV net HE", round(best["cv_he_net"], 3), flush=True)
            fitted[pair, family] = model
            grid.append(scores)
            family_scores.append((best["cv_he_net"], family))
            all_payouts = model.payout(panel)
            all_premiums = earlier_premiums(panel, model)
            held = panel.year.to_numpy() > TRAIN_END
            p, c = all_payouts[held], all_premiums[held]
            d, h = model.severities(test)
            for i, (_, row) in enumerate(test.iterrows()):
                predictions.append({"pair": pair, "family": family, "year": int(row.year),
                    "loss_fraction": row.loss_fraction, "payout_fraction": p[i], "premium_fraction": c[i],
                    "drought_severity": d[i], "heat_severity": h[i],
                    "baseline_bu_ac": row.baseline_bu_ac,
                    "loss_usd_ac": row.loss_fraction*row.baseline_bu_ac*4.70,
                    "payout_usd_ac": p[i]*row.baseline_bu_ac*4.70,
                    "premium_usd_ac": c[i]*row.baseline_bu_ac*4.70})
            for loading in (0., .10, .25):
                loaded = earlier_premiums(panel, model, loading)[held]
                for sensitivity in ("all", "without_2012"):
                    mask = np.ones(len(test), dtype=bool) if sensitivity == "all" else test.year.to_numpy() != 2012
                    metrics = protection_metrics(test.loss_fraction.to_numpy()[mask], p[mask], loaded[mask])
                    ci = net_he_interval(test.loss_fraction.to_numpy()[mask], p[mask], loaded[mask])
                    summaries.append({"pair": pair, "family": family, "loading": loading,
                        "sensitivity": sensitivity, "cv_he_net": best["cv_he_net"],
                        **metrics, "he_net_ci_low": ci[0], "he_net_ci_high": ci[1]})
            selected[f"{pair}_{family}"] = {"model": model.record(), "validation": best}
        # Stable family order resolves exact ties; no final-test metrics enter this decision.
        cv_score, winner = max(family_scores, key=lambda x: x[0])
        selected[f"{pair}_recommendation"] = winner if cv_score > 0 else "no_hedge"
    pd.concat(grid, ignore_index=True).to_csv(PROCESSED / "compound_cv.csv", index=False)
    pred, summary = pd.DataFrame(predictions), pd.DataFrame(summaries)
    pred.to_csv(PROCESSED / "compound_test_payouts.csv", index=False)
    summary.to_csv(PROCESSED / "compound_summary.csv", index=False)
    differences = []
    for pair in PAIRS:
        base = pred[(pred.pair == pair) & (pred.family == "additive")].sort_values("year")
        base_he = protection_metrics(base.loss_fraction, base.payout_fraction, base.premium_fraction)["he_net"]
        for family in ("product", "weakest_link", "mixed", "worst_peril"):
            other = pred[(pred.pair == pair) & (pred.family == family)].sort_values("year")
            ci = net_he_interval(other.loss_fraction, other.payout_fraction, other.premium_fraction,
                                 (base.payout_fraction, base.premium_fraction))
            he = protection_metrics(other.loss_fraction, other.payout_fraction, other.premium_fraction)["he_net"]
            differences.append({"pair": pair, "family": family, "reference": "additive",
                                "delta_net_he": he-base_he, "ci_low": ci[0], "ci_high": ci[1]})
    delta = pd.DataFrame(differences)
    delta.to_csv(PROCESSED / "compound_incremental.csv", index=False)
    env = {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__,
           "scipy": scipy.__version__, "matplotlib": matplotlib.__version__,
           "inputs_sha256": {name: hashlib.sha256((PROCESSED/name).read_bytes()).hexdigest() for name in inputs},
           "train_end": TRAIN_END, "test_years": test.year.astype(int).tolist(),
           "outputs": selected}
    (PROCESSED / "compound_models.json").write_text(json.dumps(env, indent=2), encoding="utf-8")

    headline = summary[(summary.loading == .10) & (summary.sensitivity == "all")]
    figure(headline, pred, selected)
    rows = []
    for _, r in headline.iterrows():
        rows.append([r.pair, r.family, f"{r.cv_he_net:.3f}", f"{r.he_gross:.3f}", f"{r.he_net:.3f}",
            f"[{r.he_net_ci_low:.2f}, {r.he_net_ci_high:.2f}]", f"{r.nrmse:.2f}",
            f"{100*r.payout_recovery:.1f}%", f"{100*r.mean_premium_fraction:.2f}%"])
    text = ["## Generated results and numbers tables", "",
        "Reproduce offline: `.venv/Scripts/python.exe scripts/run_compound.py` (Windows). "
        "Pull new source weather only when needed: `scripts/pull_compound_weather.py`.", "",
        "### Cohort and fixed assumptions", "",
        table([["Fit years", ", ".join(map(str, panel.loc[panel.year <= TRAIN_END, 'year'])), "compound_panel.csv"],
               ["Final-test years", ", ".join(map(str, test.year)), "compound_panel.csv"],
               ["Excluded years/reasons", "; ".join(f"{r.year}: {r.reason}" for r in audit[~audit.included].itertuples()), "compound_cohort_audit.csv"],
               ["Folds (fit end / validation)", "1994 / 1995-99; 1999 / 2000-04; 2004 / 2005-09", "compound.FOLDS"],
               ["Yield forecast", "previous 20 observations, minimum 15", "compound.preseason_yields"],
               ["Heat / price / maximum payout", "29 C; $4.70/bu; 30% expected yield", "protocol / run_compound.py"],
               ["Threshold quantiles / ridge", "0.25, 0.50, 0.75 / 0, 0.01, 0.10", "compound.candidates"],
               ["Candidate configurations", f"{len(pd.concat(grid)) // len(PAIRS)} per signal pair; {len(pd.concat(grid))} total", "compound_cv.csv"],
               ["Windows", "July; June-July; June-August", "compound.WINDOWS"],
               ["Loads / bootstrap replicates", "0%, 10%, 25% / 4,000 paired years, seed 473", "compound_summary.csv / compound.net_he_interval"]],
              ["Item", "Value", "Source"]), ""]
    daily = pd.read_csv(PROCESSED / inputs[2], parse_dates=["date"])
    sub_rows = []
    for label, years in (("fit", panel.loc[panel.year <= TRAIN_END, 'year']), ("test", test.year)):
        ds = daily[daily.date.dt.year.isin(years)]
        sub_rows.append([label, len(ds), int(ds.mdw_tmax_from_3sw.sum()), int(ds.mdw_tmin_from_3sw.sum()),
                         f"{100*ds[['mdw_tmax_from_3sw', 'mdw_tmin_from_3sw']].to_numpy().mean():.2f}%"])
    text += ["Nearby-station substitutions (share of Tmin/Tmax elements, not yield observations):", "",
             table(sub_rows, ["Period", "Days", "Tmax filled", "Tmin filled", "Element share"]), "",
             "### Same-target comparison", "",
             "HE is variance reduction: 0.30 means a 30% reduction in residual variance; negative "
             "values mean more variable residuals. It is neither profit nor the share of losses paid. "
             "nRMSE is gross payout error divided by the target standard deviation. Recovery counts "
             "only payouts up to the observed shortfall. Premiums are model scenarios, not quotes.", "",
             table(rows, ["Signal", "Family", "CV net HE", "Test gross HE", "Test net HE",
                          "Net HE conditional 95% interval", "nRMSE", "Loss recovered", "Mean premium / expected yield"]), "",
             f"**Validation-selected recommendations, before inspecting final scores:** station = "
             f"`{selected['station_recommendation']}`; area diagnostic = `{selected['area_recommendation']}`.", "",
             "The area diagnostic is hypothetical and is not a location selected for its test performance.", "",
             "### Cost and tail outcomes (10% load)", "",
             "HE largely ignores a constant premium: larger loads can leave HE similar while making "
             "the policy more expensive. All costs below are fractions of expected production. "
             "Average payout minus premium is not a proof of insurance value or profit; insurance "
             "can have a negative average return and still reduce risk. These families share a "
             "maximum payout budget, **not an equal premium or equal expected-payout budget**.", "",
             table([[r.pair, r.family, f"{100*r.mean_loss_fraction:.2f}%", f"{100*r.mean_payout_fraction:.2f}%",
                     f"{100*r.mean_premium_fraction:.2f}%", f"{100*r.mean_net_benefit_fraction:.2f}%",
                     f"{100*r.unhedged_p95_fraction:.2f}%", f"{100*r.p95_net_shortfall_fraction:.2f}%"]
                    for r in headline.itertuples()],
                   ["Signal", "Family", "Mean loss", "Mean payout", "Mean premium", "Payout less premium",
                    "Unhedged 95th shortfall", "Net 95th shortfall"]), "",
             "### Interaction improvement over additive cover", "",
             table([[r.pair, r.family, f"{r.delta_net_he:.3f}", f"[{r.ci_low:.3f}, {r.ci_high:.3f}]"]
                    for r in delta.itertuples()], ["Signal", "Family vs additive", "Change in net HE", "Conditional paired 95% interval"]), "",
             "### Exact frozen configurations", "",
             table([[pair, fam, (m := fitted[pair, fam]).config.window, m.config.rain_q, m.config.heat_q,
                     m.config.ridge, f"{m.rain_trigger:.4f}", f"{m.heat_trigger:.4f}",
                     ", ".join(f"{v:.6f}" for v in m.weights)] for pair in PAIRS for fam in FAMILIES],
                   ["Signal", "Family", "Window", "Rain q", "Heat q", "Ridge", "Rain trigger (in)", "Heat trigger (C-days)", "Weights"]), "",
             "Exact scales and input hashes are in `compound_models.json`; every candidate validation "
             "score is retained in `compound_cv.csv`.", "",
             "### Sensitivity: remove the already-known 2012 event, without refitting", "",
             table([[r.pair, r.family, int(r.n_test), f"{r.he_net:.3f}", f"{r.payout_recovery:.3f}"]
                    for r in summary[(summary.loading == .10) & (summary.sensitivity == 'without_2012')].itertuples()],
                   ["Signal", "Family", "Years", "Net HE without 2012", "Recovery"]), "",
             "### Price loading sensitivity (all final-test years)", "",
             table([[pair, family] + [f"{float(summary[(summary.pair == pair) & (summary.family == family) & (summary.loading == load) & (summary.sensitivity == 'all')].he_net.iloc[0]):.3f}"
                                     for load in (0., .10, .25)] for pair in PAIRS for family in FAMILIES],
                   ["Signal", "Family", "Net HE: 0% load", "10% load", "25% load"]), "",
             "Full bias, tail-shortfall, recovery, mean payout, mean loss and premium metrics are in "
             "`compound_summary.csv`. Year-level fractional and fixed-price dollar illustrations are "
             "in `compound_test_payouts.csv`.", "",
             "![Common-target comparison and selected station payout](../figures/compound_cover.png)"]
    generated = "\n".join(text)
    start, end = "<!-- AUTO: compound start -->", "<!-- AUTO: compound end -->"
    existing = DOC.read_text(encoding="utf-8")
    if start in existing:
        before, rest = existing.split(start, 1)
        _, after = rest.split(end, 1)
        existing = before + start + "\n" + generated + "\n" + end + after
    else:
        existing += "\n" + start + "\n" + generated + "\n" + end + "\n"
    DOC.write_text(existing, encoding="utf-8")
    print(headline[["pair", "family", "he_gross", "he_net", "payout_recovery"]].to_string(index=False))


def figure(summary, pred, selected):
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8), constrained_layout=True)
    x = np.arange(len(FAMILIES))
    for pair, offset, color in (("station", -.18, "#237a93"), ("area", .18, "#dd8b29")):
        sub = summary[summary.pair == pair].set_index("family").loc[list(FAMILIES)]
        axes[0].bar(x+offset, sub.he_net, width=.35, label=pair, color=color)
    axes[0].axhline(0, color="black", lw=.8)
    axes[0].set_xticks(x, [f.replace('_', '\n') for f in FAMILIES], rotation=30, ha="right")
    axes[0].set_ylabel("Net hedge effectiveness (model premium)")
    axes[0].set_title("Kane corn: common final-test target")
    axes[0].legend()
    family = selected["station_recommendation"]
    display_family = family if family != "no_hedge" else "additive"
    sub = pred[(pred.pair == "station") & (pred.family == display_family)]
    axes[1].plot(sub.year, sub.loss_fraction*100, marker="o", label="Observed county shortfall")
    axes[1].plot(sub.year, sub.payout_fraction*100, marker="s", label=f"Station {display_family} payout")
    axes[1].plot(sub.year, sub.premium_fraction*100, ls="--", label="Model premium")
    axes[1].set_ylabel("% of expected yield")
    axes[1].set_title(f"CV recommendation: {family}")
    axes[1].legend(fontsize=8)
    fig.suptitle("Exploratory early-season contract design; not tradable Kalshi portfolios", fontsize=12)
    fig.savefig(ROOT / "docs/figures/compound_cover.png", dpi=170, metadata={"Software": "agri_hedge"})
    plt.close(fig)


if __name__ == "__main__":
    main()
