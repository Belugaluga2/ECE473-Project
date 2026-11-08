"""Scientific safeguards for temporal compound-cover selection, not snapshot score tests."""
import numpy as np
import pandas as pd
import pytest

from agri_hedge import compound as c
from agri_hedge.config import PROCESSED


def synthetic_panel():
    rng = np.random.default_rng(473)
    n = 45
    out = pd.DataFrame({"year": np.arange(1980, 1980+n)})
    for pair in c.PAIRS:
        for window in c.WINDOWS:
            out[f"{pair}_{window}_rain"] = rng.uniform(1, 15, n)
            out[f"{pair}_{window}_heat"] = rng.uniform(0, 60, n)
    out["loss_fraction"] = np.clip(.15-.01*out.station_jul_rain+.002*out.station_jul_heat, 0, .30)
    return out


def test_daily_heat_integral_matches_numerical_temperature_duration():
    low, high = np.array([20, 30, 20, 29, 29]), np.array([36, 40, 25, 29, 35])
    theta = np.linspace(0, 2*np.pi, 100_000, endpoint=False)
    temp = (low[:, None]+high[:, None])/2 + (high[:, None]-low[:, None])/2*np.sin(theta)
    numerical = np.maximum(temp-29, 0).mean(axis=1)
    assert c.sinusoidal_excess(low, high) == pytest.approx(numerical, abs=1e-7)
    assert c.sinusoidal_excess(30, 30) == pytest.approx(1)
    with pytest.raises(ValueError):
        c.sinusoidal_excess(35, 20)


def test_production_forecast_excludes_current_and_future_outcomes():
    yields = pd.Series(80+2*np.arange(60), index=np.arange(1960, 2020), dtype=float)
    before = c.preseason_yields(yields)
    changed = yields.copy()
    changed.loc[2000:] *= 2
    after = c.preseason_yields(changed)
    assert before.loc[2000] == pytest.approx(yields.loc[2000])
    assert after.loc[2000] == pytest.approx(before.loc[2000])
    assert after.loc[2001] != pytest.approx(before.loc[2001])
    assert before.iloc[:15].isna().all()


def test_temporal_selection_is_invariant_to_all_final_test_information():
    panel = synthetic_panel()
    before_model, before_scores, before_best = c.select_family(panel, "station", "mixed")
    altered = panel.copy()
    hold = altered.year > c.TRAIN_END
    altered.loc[hold, "loss_fraction"] = 100
    for col in altered.columns:
        if col.endswith(("_rain", "_heat")):
            altered.loc[hold, col] += 10_000
    after_model, after_scores, after_best = c.select_family(altered, "station", "mixed")
    assert before_model == after_model
    pd.testing.assert_frame_equal(before_scores, after_scores)
    assert before_best == after_best


def test_fold_dates_are_strictly_temporal_and_pretest():
    assert max(end for _, _, end in c.FOLDS) == c.TRAIN_END
    assert all(train_end < start <= end <= c.TRAIN_END for train_end, start, end in c.FOLDS)


@pytest.mark.parametrize("family", c.FAMILIES)
def test_fitted_payoff_is_nonnegative_and_respects_shared_payout_budget(family):
    panel = synthetic_panel()
    panel.loss_fraction *= 100  # force binding capacity constraints for this test
    model = c.fit_model(panel[panel.year <= c.TRAIN_END], "station", c.Config(family, "jul", .5, .5, 0.))
    payout = model.payout(panel)
    assert min(model.weights) >= 0
    assert sum(model.weights) <= c.LIMIT+1e-12
    assert np.min(payout) >= 0 and np.max(payout) <= c.LIMIT+1e-12


def test_compound_payoffs_have_genuinely_joint_state_dependence():
    d, h = np.array([0, 0, 1, 1]), np.array([0, 1, 0, 1])
    def cross_difference(p):
        return p[3]-p[2]-p[1]+p[0]
    additive = c.features(d, h, "additive") @ np.array([.1, .2])
    joint = c.features(d, h, "product").ravel()
    assert cross_difference(additive) == pytest.approx(0)
    assert cross_difference(joint) == pytest.approx(1)
    assert np.array_equal(joint, [0, 0, 0, 1])
    assert np.array_equal(c.features(d, h, "mixed") @ [.1, .2, 0], additive)


def test_premium_does_not_use_current_or_future_weather():
    panel = synthetic_panel()
    model = c.fit_model(panel[panel.year <= c.TRAIN_END], "station", c.Config("heat", "jul", .5, .5, .01))
    before = c.earlier_premiums(panel, model)
    altered = panel.copy()
    altered.loc[altered.year >= 2015, "station_jul_heat"] = 100_000
    after = c.earlier_premiums(altered, model)
    assert before[panel.year == 2015] == pytest.approx(after[panel.year == 2015])
    assert before[panel.year == 2016] < after[panel.year == 2016]


def test_actual_data_cohort_drops_missing_yields_and_uses_same_complete_weather():
    yields = pd.read_csv(PROCESSED / "rowcrop_kane_yields.csv")
    rain = pd.read_csv(PROCESSED / "rowcrop_farm_year.csv")
    daily = pd.read_csv(PROCESSED / "compound_daily_temperature.csv")
    before, audit = c.build_panel(yields, rain, daily)
    assert 2025 not in set(before.year)
    assert "missing observed corn yield" in audit.set_index("year").loc[2025, "reason"]
    # A missing June temperature removes the year even from the July-only family.
    daily.loc[daily.date == "2011-06-01", "mdw_tmin_f"] = np.nan
    after, _ = c.build_panel(yields, rain, daily)
    assert set(before.year)-set(after.year) == {2011}


def test_bootstrap_delta_uses_the_same_year_draw_for_both_hedges():
    y = np.array([0, .01, .03, 0, .07, .02])
    p, cost = .8*y, np.full(len(y), .01)
    interval = c.net_he_interval(y, p, cost, (p, cost), repetitions=100)
    assert interval == pytest.approx([0, 0])
