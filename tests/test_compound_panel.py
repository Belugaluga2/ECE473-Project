"""Guards for county transfer, equal-cost fitting and dependence-aware evidence in doc 27."""
import numpy as np
import pandas as pd
import pytest

from agri_hedge import compound_panel as cp


def synthetic():
    rng = np.random.default_rng(473)
    rows = []
    for fips, role in (("17001", "development"), ("19001", "development"), ("18001", "held_out")):
        for year in range(1980, 2025):
            r, h, w = rng.uniform(1, 15), rng.uniform(0, 60), rng.uniform(1, 15)
            rows.append({"fips": fips, "role": role, "year": year, "rain_jun_jul": r,
                         "heat_dd29": h, "rain_apr_may": w,
                         "loss_fraction": max(.10-.012*r+.002*h+.001*w, 0)})
    return pd.DataFrame(rows)


@pytest.mark.parametrize("family", cp.FAMILIES)
def test_equal_cost_models_really_share_the_training_budget_and_cap(family):
    panel = synthetic()
    model = cp.fit_model(panel, 2009, cp.Config(family, .01))
    train = panel[(panel.role == "development") & panel.year.isin(model.training_years)]
    assert model.premium == pytest.approx(cp.PREMIUM, abs=1e-8)
    assert model.payout(train).mean()*(1+cp.LOAD) == pytest.approx(cp.PREMIUM, abs=1e-8)
    assert sum(model.weights) <= cp.LIMIT+1e-8
    assert min(model.weights) >= 0
    assert model.payout(panel).min() >= 0
    assert model.payout(panel).max() <= cp.LIMIT+1e-8


def test_selection_cannot_read_reserved_county_losses_or_future_weather():
    panel = synthetic()
    before, scores, best = cp.select_family(panel, "mixed", "equal_premium")
    altered = panel.copy()
    altered.loc[altered.role == "held_out", "loss_fraction"] = 1000
    final = altered.year > 2009
    altered.loc[final, "loss_fraction"] += 1000
    altered.loc[final, cp.WEATHER] += 1000
    after, new_scores, new_best = cp.select_family(altered, "mixed", "equal_premium")
    assert before == after
    pd.testing.assert_frame_equal(scores, new_scores)
    assert best == new_best
    assert before.training_rows == 2*30


def test_infeasible_budget_is_reported_instead_of_silently_raising_cap():
    panel = synthetic()
    panel.heat_dd29 = 0
    with pytest.raises(ValueError, match="Infeasible equal premium"):
        cp.fit_model(panel, 2009, cp.Config("heat", 0.))


def test_missing_data_removes_the_same_year_for_all_competing_policies():
    panel = synthetic()
    panel.loc[(panel.fips == "17001") & (panel.year == 1997), "rain_apr_may"] = np.nan
    development = ["17001", "19001"]
    assert 1997 not in cp.common_years(panel, development, 1995, 1999)
    model = cp.fit_model(panel, 2009, cp.Config("drought", 0.))
    assert 1997 not in model.training_years  # also removed from dry-only fitting
    assert model.training_rows == 2*29


def test_spring_excess_is_a_shared_benchmark_and_interaction_can_be_zero():
    d, h, w = np.array([0, .5, 1]), np.array([.2, 1, 0]), np.array([1, .5, .2])
    separate = cp.feature_matrix(d, h, w, "additive") @ [.1, .05, .03]
    combined = cp.feature_matrix(d, h, w, "mixed") @ [.1, .05, .03, 0.]
    assert combined == pytest.approx(separate)
    assert cp.feature_matrix(d, h, w, "rain_two_sided")[0, 1] == 1


def bootstrap_frame():
    return pd.DataFrame({"year": np.arange(2010, 2025), "fips": "A",
        "loss_fraction": [0, .01, .2, 0, .01, .03, 0, .01, .05, .08, .02, 0, .01, 0, .02],
        "payout_fraction": [0, 0, .1, 0, .02, 0, 0, 0, .01, .02, .03, 0, 0, 0, .01],
        "premium_fraction": .01})


def test_counties_sharing_a_weather_shock_do_not_manufacture_more_independent_years():
    first = bootstrap_frame()
    second = first.copy()
    second.fips = "B"
    single = cp.paired_year_interval(first, repetitions=200)
    duplicated = cp.paired_year_interval(pd.concat([first, second]), repetitions=200)
    assert duplicated == pytest.approx(single)
    assert cp.paired_year_interval(first, first, repetitions=200) == pytest.approx([0, 0])


def test_bootstrap_requires_exactly_matched_county_years_and_targets():
    frame = bootstrap_frame()
    altered = frame.copy()
    altered.loc[0, "loss_fraction"] = .1
    with pytest.raises(ValueError, match="same losses"):
        cp.paired_year_interval(frame, altered, repetitions=50)
    with pytest.raises(ValueError, match="same county-years"):
        cp.paired_year_interval(frame, frame.iloc[1:], repetitions=50)


def test_cost_is_visible_even_when_he_does_not_change():
    y = np.array([.01, .02, .03, .04])
    free, costly = cp.metrics(y, y, 0.), cp.metrics(y, y, .02)
    assert free["he_net"] == costly["he_net"] == 1
    assert costly["net_error_skill"] < free["net_error_skill"]
    assert costly["p95_net_shortfall_fraction"] > free["p95_net_shortfall_fraction"]


def test_daily_aggregation_is_earlier_baseline_based_and_does_not_fill_weather():
    counties = pd.DataFrame([{"fips": "17001", "state": "IL", "county": "test", "role": "development"}])
    yields = pd.DataFrame({"fips": "17001", "year": np.arange(1940, 2025), "yield_bu_ac": np.arange(85)+80.})
    dates = pd.date_range("2010-04-01", "2010-07-31")
    daily = pd.DataFrame({"fips": "17001", "date": dates, "rain_in": .1, "tmax_f": 90., "tmin_f": 65.})
    panel, _ = cp.build_panel(counties, yields, daily)
    year = panel[panel.year == 2010].iloc[0]
    assert year.baseline_bu_ac == pytest.approx(150)
    assert year.rain_jun_jul == pytest.approx(6.1)
    absent_yield, absent_audit = cp.build_panel(counties, yields[yields.year != 2010], daily)
    assert absent_yield.loc[absent_yield.year == 2010, "baseline_bu_ac"].iloc[0] == pytest.approx(150)
    assert absent_audit.loc[absent_audit.year == 2010, "reason"].iloc[0] == "missing yield"
    changed = daily.copy()
    changed.loc[0, "rain_in"] = np.nan
    missing, audit = cp.build_panel(counties, yields, changed)
    assert missing.loc[missing.year == 2010, cp.WEATHER].isna().all().all()
    assert not audit.loc[audit.year == 2010, "complete"].iloc[0]


def test_synthetic_primitive_spanning_does_not_use_crop_test_outcomes():
    panel = synthetic()
    model = cp.fit_model(panel, 2009, cp.Config("mixed", .01))
    train = panel[(panel.role == "development") & (panel.year <= 2009)]
    before = cp.fit_primitive_approximation(model, train)
    changed = train.copy()
    changed.loss_fraction += 1000
    assert cp.fit_primitive_approximation(model, changed) == pytest.approx(before)
