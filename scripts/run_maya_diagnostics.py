"""Reproduce doc 28, frozen settlement specifications and offline demo data. No downloads."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict

import numpy as np
import pandas as pd

from agri_hedge import compound_panel as cp
from agri_hedge import maya_diagnostics as md
from agri_hedge.compound import sinusoidal_excess
from agri_hedge.config import PROCESSED, ROOT
from agri_hedge.maya_contract import make_spec, settle

DOC = ROOT / "docs/analysis/28_maya_diagnosis_and_demo.md"
DEMO = ROOT / "experiments/maya"


def table(rows, headers):
    return "\n".join(["| "+" | ".join(headers)+" |", "| "+" | ".join(["---"]*len(headers))+" |"]
        + ["| "+" | ".join(map(str, row))+" |" for row in rows])


def load_model(record):
    return cp.Model(cp.Config(**record["config"]), record["fit_end"], record["normalizers"],
                    tuple(record["weights"]), record["premium"], record["training_rows"], tuple(record["training_years"]))


def chicago_inputs():
    rain = pd.read_csv(PROCESSED / "rowcrop_farm_year.csv")[["year", "ord_jun_in", "ord_jul_in"]]
    daily = pd.read_csv(PROCESSED / "compound_daily_temperature.csv", parse_dates=["date"])
    daily = daily[daily.date.dt.month.isin((6, 7))]
    rows = []
    for year, group in daily.groupby(daily.date.dt.year):
        if len(group) != 61 or not np.isfinite(group.mdw_tmax_f.to_numpy()).all():
            continue
        rows.append({"year": year, "mdw_tmax_substituted_days": int(group.mdw_tmax_from_3sw.sum()),
                     **{f"mdw_days_gt_{strike}": int((group.mdw_tmax_f > strike).sum()) for strike in md.HEAT_STRIKES_F}})
    return rain.merge(pd.DataFrame(rows), on="year", validate="one_to_one").dropna()


def main():
    counties = pd.read_csv(PROCESSED / "panel_counties.csv", dtype={"fips": str})
    annual = pd.read_csv(PROCESSED / "panel_annual.csv", dtype={"fips": str})
    yields = pd.read_csv(PROCESSED / "panel_yields.csv", dtype={"fips": str})
    daily = pd.read_csv(PROCESSED / "panel_daily_weather.csv", dtype={"fips": str}, parse_dates=["date"])
    saved = json.loads((PROCESSED / "panel_models.json").read_text())
    if saved["selected"]["equal_premium"] != "weakest_link":
        raise ValueError("The diagnostic plan specifies the saved weakest-link rule; inspect changed inputs")
    record = saved["models"]["equal_premium_weakest_link"]
    model = load_model(record)
    training = annual[(annual.role == "development") & annual.year.isin(model.training_years)]
    mean_z = float(np.minimum(*model.severities(training)[:2]).mean())
    budget_weight = .01/(1.10*mean_z)
    if not np.isclose(budget_weight, model.weights[0], atol=1e-10):
        raise ValueError("Saved coefficient no longer matches its budget explanation")
    coefficient = {"premium_fraction": .01, "load": .10, "mean_training_min_D_H": mean_z,
                   "coefficient_from_budget": budget_weight, "saved_coefficient": model.weights[0],
                   "training_rows": len(training), "training_years": list(model.training_years)}
    (PROCESSED / "maya_coefficient_audit.json").write_text(json.dumps(coefficient, indent=2), encoding="utf-8")
    held = annual[(annual.role == "held_out") & annual.year.isin(saved["final_test_years"])].copy()
    held["payout_fraction"] = model.payout(held)
    held["premium_fraction"] = model.premium
    held["drought"], held["heat"], held["wet_spring"] = model.severities(held)
    held["net_shortfall_fraction"] = np.maximum(held.loss_fraction-held.payout_fraction+model.premium, 0)
    held["overpayment_fraction"] = np.maximum(held.payout_fraction-held.loss_fraction, 0)
    held["mechanical_reason"] = [md.payment_reason(r.drought, r.heat, r.loss_fraction, r.payout_fraction) for r in held.itertuples()]
    held["deductible_10pp_loss_fraction"] = np.maximum(held.loss_fraction-.10, 0)
    forecasts = []
    for fips in held.fips.unique():
        yy = yields[yields.fips == fips].set_index("year").yield_bu_ac
        sensitivity = md.earlier_baselines(yy, range(1980, 2025))
        sensitivity.insert(0, "fips", fips)
        forecasts.append(sensitivity)
    forecasts = pd.concat(forecasts, ignore_index=True)
    forecasts.to_csv(PROCESSED / "maya_baseline_sensitivity.csv", index=False)
    original = forecasts[forecasts.method == "original_20_linear"]
    check = held.merge(original[["fips", "year", "loss_fraction"]], on=["fips", "year"], suffixes=("", "_check"))
    if not np.allclose(check.loss_fraction, check.loss_fraction_check):
        raise ValueError("Sensitivity implementation disagrees with original baseline")
    ranges = forecasts.groupby(["fips", "year"]).loss_fraction.agg(baseline_low="min", baseline_high="max").reset_index()
    held = held.merge(ranges, on=["fips", "year"], validate="one_to_one")
    august = pd.read_csv(PROCESSED / "maya_august_context.csv", dtype={"fips": str})
    thresholds = []
    for fips, group in august[august.year <= 2009].groupby("fips"):
        summer = annual[(annual.fips == fips) & (annual.year <= 2009)]
        thresholds.append({"fips": fips, "august_rain_p10": group.rain_in.quantile(.10),
            "august_heat_p90": group.heat_dd29.quantile(.90), "summer_rain_p90": summer.rain_jun_jul.quantile(.90)})
    thresholds = pd.DataFrame(thresholds)
    thresholds.to_csv(PROCESSED / "maya_context_thresholds.csv", index=False)
    held = held.merge(august[["fips", "year", "rain_in", "heat_dd29"]].rename(columns={"rain_in": "august_rain_in", "heat_dd29": "august_heat_dd29"}), on=["fips", "year"], validate="one_to_one")
    held = held.merge(thresholds, on="fips", validate="many_to_one")
    held["august_dry_clue"] = held.august_rain_in < held.august_rain_p10
    held["august_hot_clue"] = held.august_heat_dd29 > held.august_heat_p90
    held["wet_summer_clue"] = held.rain_jun_jul > held.summer_rain_p90
    held.to_csv(PROCESSED / "maya_case_diagnosis.csv", index=False)
    misses = held.sort_values("net_shortfall_fraction", ascending=False).head(9)
    over = held[held.overpayment_fraction > 0].sort_values("overpayment_fraction", ascending=False).head(5)
    misses.to_csv(PROCESSED / "maya_top_misses.csv", index=False)
    over.to_csv(PROCESSED / "maya_top_overpayments.csv", index=False)
    specs, replays = {}, []
    for county in counties[counties.role == "held_out"].to_dict("records"):
        specs[county["fips"]] = make_spec(record, county)
    for case in held.itertuples():
        season = daily[(daily.fips == case.fips) & (daily.date.dt.year == case.year) & daily.date.dt.month.isin((6, 7))]
        replay = settle(specs[case.fips], season, int(case.year), 100_000)
        if not np.isclose(replay["payout_fraction"], case.payout_fraction, atol=1e-12):
            raise ValueError("Daily settlement replay does not match the annual frozen model")
        replays.append(replay)
    (PROCESSED / "maya_contract_specs.json").write_text(json.dumps(specs, indent=2), encoding="utf-8")
    (PROCESSED / "maya_settlement_replays.json").write_text(json.dumps(replays, indent=2), encoding="utf-8")

    market = json.loads((PROCESSED / "maya_market_snapshot.json").read_text())
    rain_strikes = sorted({int(m["floor_strike"]) for m in market["series"]["KXRAINCHIM"]["markets"] if m["strike_type"] == "greater"})
    if rain_strikes != list(range(1, 8)):
        raise ValueError("Observed rain structure differs from the frozen scenario; revise the audit explicitly")
    chicago = chicago_inputs()
    replica_rows, replica_models, replica_cv, prediction_rows = [], {}, [], []
    for fips in held.fips.unique():
        local = annual[annual.fips == fips].copy()
        local["drought"], local["heat"], _ = model.severities(local)
        local["payout_fraction"] = model.payout(local)
        frame = local.merge(chicago, on="year", validate="one_to_one")
        final = frame[frame.year.isin(saved["final_test_years"])]
        for basis in md.REPLICA_BASES:
            replica, scores = md.select_replica(frame, basis, model.weights[0])
            scores.insert(0, "fips", fips)
            replica_cv.append(scores)
            estimated = replica.payout(final)
            metrics = md.payoff_metrics(final.payout_fraction, estimated)
            crop = cp.metrics(final.loss_fraction, estimated, replica.modeled_premium_fraction)
            replica_rows.append({"fips": fips, "county": local.county.iloc[0], "basis": basis,
                "test_years": len(final), "train_years": int((frame.year <= 2009).sum()),
                "ridge": replica.ridge, **metrics, "modeled_premium_fraction": replica.modeled_premium_fraction,
                "secondary_crop_he": crop["he_gross"], "secondary_crop_net_error_skill": crop["net_error_skill"],
                "train_tmax_substitution_share": float(frame.loc[frame.year <= 2009, "mdw_tmax_substituted_days"].sum()/((frame.year <= 2009).sum()*61)),
                "test_tmax_substitution_share": float(final.mdw_tmax_substituted_days.sum()/(len(final)*61))})
            replica_models[f"{fips}_{basis}"] = asdict(replica)
            for i, case in enumerate(final.itertuples()):
                prediction_rows.append({"fips": fips, "year": case.year, "basis": basis,
                    "target_fraction": case.payout_fraction, "replica_fraction": float(estimated[i]),
                    "modeled_premium_fraction": replica.modeled_premium_fraction})
    replicas = pd.DataFrame(replica_rows)
    replicas.to_csv(PROCESSED / "maya_replication_summary.csv", index=False)
    pd.concat(replica_cv, ignore_index=True).to_csv(PROCESSED / "maya_replica_cv.csv", index=False)
    predictions = pd.DataFrame(prediction_rows)
    predictions.to_csv(PROCESSED / "maya_replica_predictions.csv", index=False)
    (PROCESSED / "maya_replica_models.json").write_text(json.dumps(replica_models, indent=2), encoding="utf-8")
    bound = {"coefficient": model.weights[0], "rectangular_cross_difference": model.weights[0],
        "additive_global_worst_case_error_lower_bound_fraction": model.weights[0]/4,
        "same_tmax_35c_daily_heat_if_tmin_15c": float(sinusoidal_excess(15, 35)),
        "same_tmax_35c_daily_heat_if_tmin_25c": float(sinusoidal_excess(25, 35))}
    (PROCESSED / "maya_spanning_bound.json").write_text(json.dumps(bound, indent=2), encoding="utf-8")
    cv = pd.read_csv(PROCESSED / "panel_cv.csv")
    summary = pd.read_csv(PROCESSED / "panel_summary.csv")
    main_summary = summary[(summary.regime == "equal_premium") & (summary.role == "held_out") & (summary.loading == .10)]
    demo = {"title": "Maya's weather-cover experiments", "coefficientAudit": coefficient, "specs": specs,
        "cases": held.to_dict("records"), "topMisses": misses.to_dict("records"),
        "replicaPredictions": predictions.to_dict("records"), "replicaSummary": replicas.to_dict("records"),
        "summary": main_summary.to_dict("records"), "bound": bound,
        "market": {"checked_utc": market["checked_utc"], "currently_constructible": False,
                   "events": {k: v["open_events"] for k, v in market["series"].items()},
                   "explanation": "No pre-season summer portfolio is demonstrated. November quotes cannot price it."}}
    DEMO.mkdir(parents=True, exist_ok=True)
    (DEMO / "demo_data.js").write_text("window.MAYA_DATA = "+json.dumps(demo, allow_nan=False, separators=(",", ":"))+";\n", encoding="utf-8")
    report(coefficient, misses, over, replicas, thresholds, bound, cv, market, main_summary)
    source_names = ("panel_models.json", "panel_annual.csv", "panel_yields.csv", "panel_daily_weather.csv",
        "maya_august_context.csv", "maya_market_snapshot.json", "compound_daily_temperature.csv", "rowcrop_farm_year.csv")
    (PROCESSED / "maya_diagnostic_provenance.json").write_text(json.dumps({
        "input_sha256": {name: hashlib.sha256((PROCESSED/name).read_bytes()).hexdigest() for name in source_names},
        "diagnostic_status": "already-inspected test outcomes; no crop refitting or new validation claims"}, indent=2), encoding="utf-8")
    print("Coefficient from budget:", budget_weight, "mean min(D,H):", mean_z)
    print("Case/replay counts", len(held), len(replays))
    print(replicas[["county", "basis", "target_rmse_fraction", "payoff_replication_he"]].to_string(index=False))


def report(coefficient, misses, over, replicas, thresholds, bound, cv, market, summary):
    fmt = lambda v: f"{100*v:.2f}%"
    lines = ["## Generated diagnosis and numbers tables", "",
        "Reproduce offline: `.venv/Scripts/python.exe scripts/run_maya_diagnostics.py`.", "",
        "### Why this coefficient?", "",
        table([[key, value, "maya_coefficient_audit.json / saved panel model"] for key, value in coefficient.items()],
              ["Quantity", "Value", "Source"]), "",
        "With one feature, the equal-price constraint fixes its coefficient. Different ridge penalties "
        "cannot materially change that single coefficient under the same equality. Multi-feature fits "
        "choose how to allocate that budget by centered error plus ridge. These are contract weights, "
        "not causal crop-response coefficients.", "",
        "### Earlier validation scores, primary models", "",
        table([[r.family, r.ridge, f"{r.cv_net_error_skill:.6f}", r.validation_years, r.validation_rows]
               for r in cv[cv.regime == 'equal_premium'].itertuples()],
              ["Family", "Ridge", "CV net error skill", "Years", "County-year rows"]), "",
        "### Largest nine net shortfalls: mechanical explanations", "",
        table([[r.county, r.year, fmt(r.loss_fraction), fmt(r.payout_fraction), f"{r.drought:.3f}",
                f"{r.heat:.3f}", r.mechanical_reason] for r in misses.itertuples()],
              ["County", "Year", "Forecast shortfall", "Payment", "D", "H", "Why payment is small/zero"]), "",
        "### Baseline and missing-peril context for the same cases", "",
        table([[r.county, r.year, f"{fmt(r.baseline_low)}–{fmt(r.baseline_high)}", fmt(r.deductible_10pp_loss_fraction),
                f"{r.rain_jun_jul:.2f}", bool(r.wet_summer_clue), f"{r.august_rain_in:.2f}",
                bool(r.august_dry_clue), bool(r.august_hot_clue)] for r in misses.itertuples()],
              ["County", "Year", "Loss range across fixed forecasts", "Loss after hypothetical 10pp deductible",
               "Jun-Jul rain in", "Wet-summer clue", "August rain in", "August dry clue", "August hot clue"]), "",
        "These are diagnostics of a frozen policy, not refitted results or causal attribution. "
        "Range endpoints include all four predeclared production forecasts; none is chosen as correct. "
        "The deductible is an illustration, not a verified crop-insurance calculation.", "",
        table([[r.fips, f"{r.august_rain_p10:.4f}", f"{r.august_heat_p90:.4f}", f"{r.summer_rain_p90:.4f}"]
               for r in thresholds.itertuples()], ["County FIPS", "August rain p10 (in)", "August heat p90 (C-days)", "Jun-Jul rain p90 (in)"]), "",
        "### Up to five largest positive overpayments", "",
        table([[r.county, r.year, fmt(r.loss_fraction), fmt(r.payout_fraction), fmt(r.overpayment_fraction)]
               for r in over.itertuples()], ["County", "Year", "Forecast shortfall", "Payment", "Overpayment"]), "",
        "### Existing market availability", "",
        table([["Public snapshot UTC", market['checked_utc'], "maya_market_snapshot.json"],
               *[[ticker, ", ".join(series['open_events']), "public open-market list in snapshot"] for ticker, series in market['series'].items()],
               ["Rain thresholds checked", "1–7 inches, strictly greater YES / complementary NO", "snapshot strike metadata"],
               ["Summer-heat scenario thresholds", "80, 85, 90, 95, 100 F", "protocol; invented seasonal scenario"],
               ["Replica ridge grid", "0.01, 0.10, 1.0", "maya_replica_cv.csv"],
               ["Current summer portfolio", "not demonstrated / not currently constructible from checked listings", "snapshot; no future summer events listed"]],
              ["Item", "Value", "Source"]), "",
        "### Counterfactual long-only replication of the proposed payment", "",
        table([[r.county, r.basis, r.train_years, r.test_years, r.ridge, fmt(r.target_rmse_fraction),
                f"{r.payoff_replication_he:.3f}", fmt(r.modeled_premium_fraction)] for r in replicas.itertuples()],
              ["County", "Basis", "Earlier years", "Final years", "Ridge", "Target RMSE / expected crop value",
               "Payoff replication HE", "Modeled cost incl. 10% load"]), "",
        "All positions are nonnegative, no free intercept/cash; their conservative total face bound "
        "does not exceed the proposed contract's maximum payment. This constrained, restricted family "
        "is not a proof of the best achievable portfolio. Prices are inferred from earlier historical "
        "payouts, not quotes; fractional positions, fees, financing and fills are not verified. "
        "June-July rain structures and summer heat listings are counterfactual. Local synthetic ladders "
        "are not exchange products. Chicago also changes geography and data source. Do not attribute "
        "the score difference to geography alone.", "",
        table([[r.county, f"{100*r.train_tmax_substitution_share:.2f}%", f"{100*r.test_tmax_substitution_share:.2f}%"]
               for r in replicas[replicas.basis == 'chicago_rain'].itertuples()],
              ["County", "Earlier MDW Tmax elements from 3SW", "Final MDW Tmax elements from 3SW"]), "",
        "### Exact spanning facts", "",
        table([[key, value, "maya_spanning_bound.json; analytic formula"] for key, value in bound.items()],
              ["Quantity", "Value", "Source"]), "",
        "For any separate additive payoff f(D)+g(H), the four endpoint payments have zero "
        "rectangular cross-difference. Our min rule has a nonzero difference equal to its coefficient. "
        "If all four errors were smaller than coefficient/4, their signed sum could not equal that "
        "difference. Thus an exact static additive replication is impossible over the whole severity "
        "domain. Realized sample error can be much smaller; this does not assume equally likely states. "
        "Equal Tmax with different Tmin also gives different duration-based heat readings, another "
        "information gap relative to daily-high-only markets.", "",
        "### Frozen policy evidence retained from doc 27", "",
        table([[r.family, r.sensitivity, f"{r.he_gross:.3f}", f"{r.net_error_skill:.3f}"]
               for r in summary[summary.family == 'weakest_link'].itertuples()],
              ["Family", "Cohort", "HE", "Net squared-error reduction"]), "",
        "Settlement specifications and all historical replay receipts are in `maya_contract_specs.json` "
        "and `maya_settlement_replays.json`. No money or collateral is actually held. "
        "Exact replica positions, scores and predictions are retained in `maya_replica_*` files. "
        "Source hashes are in `maya_diagnostic_provenance.json`."]
    start, end = "<!-- AUTO: maya diagnosis start -->", "<!-- AUTO: maya diagnosis end -->"
    existing = DOC.read_text(encoding="utf-8")
    generated = "\n".join(lines)
    if start in existing:
        before, rest = existing.split(start, 1)
        _, after = rest.split(end, 1)
        existing = before+start+"\n"+generated+"\n"+end+after
    else:
        existing += "\n"+start+"\n"+generated+"\n"+end+"\n"
    DOC.write_text(existing, encoding="utf-8")


if __name__ == "__main__":
    main()
