"""Frozen contract, honest data handling and replication safeguards for doc 28."""
import numpy as np
import pandas as pd
import pytest

from agri_hedge import maya_diagnostics as md
from agri_hedge.compound import sinusoidal_excess
from agri_hedge.maya_contract import make_spec, settle


def contract_and_weather():
    model = {"config": {"family": "weakest_link"}, "fit_end": 2009, "weights": [.1], "premium": .01,
             "normalizers": {"17167": [10, 0, 0, 10, 1, 1]}}
    county = {"fips": "17167", "county": "Sangamon", "state": "IL", "lat": 39.75, "lon": -89.66}
    spec = make_spec(model, county)
    weather = pd.DataFrame({"fips": "17167", "date": pd.date_range("2012-06-01", "2012-07-31"),
                            "rain_in": 0., "tmin_f": 80., "tmax_f": 95.})
    return spec, weather


def test_settlement_is_capped_funded_and_order_independent():
    spec, weather = contract_and_weather()
    receipt = settle(spec, weather, 2012, "100000.00")
    assert receipt["payout_cents"] == receipt["required_mock_collateral_cents"] == 1_000_000
    assert receipt["modeled_premium_cents"] == 100_000
    assert receipt["unused_mock_collateral_cents"] == 0
    assert not receipt["source_truth_verified"]
    assert settle(spec, weather.sample(frac=1, random_state=473), 2012, "100000.00") == receipt
    weather.rain_in = 1
    assert settle(spec, weather, 2012, 100000)["payout_cents"] == 0


@pytest.mark.parametrize("problem", ["missing", "duplicate", "wrong_county", "negative_rain", "invalid_temp", "nan", "wrong_year"])
def test_settlement_rejects_incomplete_or_invalid_observations(problem):
    spec, weather = contract_and_weather()
    if problem == "missing":
        weather = weather.iloc[1:]
    elif problem == "duplicate":
        weather.loc[1, "date"] = weather.loc[0, "date"]
    elif problem == "wrong_county":
        weather.fips = "19169"
    elif problem == "negative_rain":
        weather.loc[0, "rain_in"] = -1
    elif problem == "invalid_temp":
        weather.loc[0, "tmin_f"] = 100
    elif problem == "nan":
        weather.loc[0, "tmax_f"] = np.nan
    else:
        weather.date = weather.date+pd.DateOffset(years=1)
    with pytest.raises(ValueError):
        settle(spec, weather, 2012, 100000)


def test_settlement_detects_changed_terms_and_invalid_money():
    spec, weather = contract_and_weather()
    altered = dict(spec, coefficient=.2)
    with pytest.raises(ValueError, match="hash mismatch"):
        settle(altered, weather, 2012, 100000)
    for value in (-1, 0, "NaN", "100.001"):
        with pytest.raises(ValueError):
            settle(spec, weather, 2012, value)


def test_diagnostic_forecasts_never_use_current_or_future_production():
    yields = pd.Series(100.+np.arange(70), index=range(1950, 2020))
    before = md.earlier_baselines(yields, [2000, 2001])
    changed = yields.copy()
    changed.loc[2000:] *= 2
    after = md.earlier_baselines(changed, [2000, 2001])
    assert before.loc[before.year == 2000, "expected_bu_ac"].to_numpy() == pytest.approx(after.loc[after.year == 2000, "expected_bu_ac"].to_numpy())
    assert not np.allclose(before.loc[before.year == 2001, "expected_bu_ac"], after.loc[after.year == 2001, "expected_bu_ac"])


def replica_frame():
    rng = np.random.default_rng(473)
    d, h = rng.uniform(0, 1, (2, 45))
    return pd.DataFrame({"year": np.arange(1980, 2025), "drought": d, "heat": h,
                         "payout_fraction": .1*np.minimum(d, h), "loss_fraction": rng.uniform(0, .3, 45)})


def test_replica_selection_does_not_read_crop_losses_or_final_weather_payoffs():
    frame = replica_frame()
    model, scores = md.select_replica(frame, "local_ladders", .1)
    altered = frame.copy()
    altered.loss_fraction += 1000
    altered.loc[altered.year > 2009, ["payout_fraction", "drought", "heat"]] += 1000
    after, after_scores = md.select_replica(altered, "local_ladders", .1)
    assert model == after
    pd.testing.assert_frame_equal(scores, after_scores)


def test_long_only_replica_has_no_free_cash_and_respects_face_bound():
    frame = replica_frame()
    model = md.fit_replica(frame, "local_ladders", .01, .1)
    assert min(model.weights) >= 0 and sum(model.weights) <= .1+1e-8
    assert model.payout(frame).max() <= .1+1e-8
    frame.drought = 0
    frame.heat = 0
    frame.payout_fraction = .1
    empty = md.fit_replica(frame, "local_continuous", .01, .1)
    assert np.array_equal(empty.payout(frame), np.zeros(len(frame)))
    assert empty.modeled_premium_fraction == 0


def test_joint_rule_has_nonzero_rectangular_cross_difference():
    d, h, a = np.array([0, 0, 1, 1]), np.array([0, 1, 0, 1]), .107
    joint = a*np.minimum(d, h)
    separate = .03*d+.06*h+.01
    cross = lambda x: x[3]-x[2]-x[1]+x[0]
    assert cross(separate) == pytest.approx(0)
    assert cross(joint) == pytest.approx(a)
    # Best unrestricted additive endpoint fit reaches (but cannot beat) the a/4 bound.
    x = np.column_stack([np.ones(4), d, h])
    fit = x @ np.linalg.lstsq(x, joint, rcond=None)[0]
    assert max(abs(joint-fit)) == pytest.approx(a/4)


def test_tmax_only_primitives_cannot_identify_temperature_duration():
    assert sinusoidal_excess(15, 35) != pytest.approx(sinusoidal_excess(25, 35))


def test_mechanical_explanation_does_not_invent_a_crop_damage_cause():
    assert md.payment_reason(0, .8, .2, 0).startswith("drought trigger not met")
    assert "smaller severity is weak" in md.payment_reason(.5, .01, .3, .001)
    assert "below shortfall" in md.payment_reason(.8, .8, .3, .08)
