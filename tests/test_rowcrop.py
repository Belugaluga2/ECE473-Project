"""Tests for agri_hedge.rowcrop (row-crop rain exposure and Kalshi hedges). Synthetic data only, no network."""
import numpy as np
import pandas as pd
import pytest

from agri_hedge import rowcrop as rc


# ---------------------------------------------------------------------------------------------
# Yield response
# ---------------------------------------------------------------------------------------------

def test_state_equivalent_rain_shifts_by_anomaly_and_clips():
    p = rc.state_equivalent_rain([3.0, 5.0, 20.0, np.nan], station_normal=4.0, state_normal=4.5, clip=(1.0, 7.0))
    assert p[0] == pytest.approx(3.5)
    assert p[1] == pytest.approx(5.5)
    assert p[2] == pytest.approx(7.0)          # clipped to the model's fit range
    assert np.isnan(p[3])


def test_quadratic_yield_change_matches_03a_illinois_july_exact_values():
    # IL corn July, our 1980-2025 update (doc 03a headline table): exact +1 / -1 / -2 in = +5.0 / -9.2 / -22.6 bu/ac
    b1, b2, p0 = 24.07101795007585, -2.0905515845313123, 4.06
    got = rc.quadratic_yield_change([p0 + 1, p0 - 1, p0 - 2, p0], b1, b2, p0)
    assert got[0] == pytest.approx(5.01, abs=0.01)
    assert got[1] == pytest.approx(-9.19, abs=0.01)
    assert got[2] == pytest.approx(-22.56, abs=0.01)
    assert got[3] == pytest.approx(0.0)


def test_revenue_loss_floors_gains_and_keeps_nan():
    out = rc.revenue_loss([-10.0, 5.0, np.nan], price=4.7)
    assert out[0] == pytest.approx(47.0)
    assert out[1] == 0.0
    assert np.isnan(out[2])


def test_trend_shortfall_on_exact_line_plus_one_bad_year():
    years = np.arange(2000, 2010)
    y = 100 + 2.0 * (years - 2000)
    y = y.astype(float)
    y[5] -= 30          # one bad year
    ts = rc.trend_shortfall(years, y, fit_window=(2000, 2004))   # fit on the clean years only
    assert ts.loc[0, "trend"] == pytest.approx(100.0)
    assert ts.loc[5, "shortfall"] == pytest.approx(30.0)
    assert ts.loc[6, "shortfall"] == pytest.approx(0.0)
    assert ts.loc[5, "deviation"] == pytest.approx(-30.0)


def test_linear_trend_needs_three_points():
    with pytest.raises(ValueError):
        rc.linear_trend([1, 2, 3], [1.0, np.nan, np.nan])


# ---------------------------------------------------------------------------------------------
# Contracts and hedges
# ---------------------------------------------------------------------------------------------

def test_yes_and_no_payoffs_are_complements_and_strike_goes_to_no():
    r = np.array([1.0, 2.0, 2.5, np.nan])
    no = rc.payoff(r, 2.0, "no")
    yes = rc.payoff(r, 2.0, "yes")
    assert list(no[:3]) == [1.0, 1.0, 0.0]          # exactly at the strike pays NO (Kalshi: YES iff > strike)
    assert list(yes[:3]) == [0.0, 0.0, 1.0]
    assert np.isnan(no[3]) and np.isnan(yes[3])
    with pytest.raises(ValueError):
        rc.payoff(r, 2.0, "maybe")


def test_side_strikes_split_at_rounded_normal():
    s = rc.side_strikes({7: (1.0, 2.0, 3.0, 4.0, 5.0, 6.0)}, {7: 3.71})
    assert s["no"][7] == (1.0, 2.0, 3.0, 4.0)
    assert s["yes"][7] == (4.0, 5.0, 6.0)


def test_binary_design_columns_and_per_side_strikes():
    rain = {7: np.array([1.5, 3.5, 6.0])}
    X, legs = rc.binary_design(rain, {7: (2.0, 4.0)}, ("no", "yes"))
    assert legs == [(7, 2.0, "no"), (7, 4.0, "no"), (7, 2.0, "yes"), (7, 4.0, "yes")]
    np.testing.assert_array_equal(X[:, 0], [1, 0, 0])
    np.testing.assert_array_equal(X[:, 3], [0, 0, 1])
    X2, legs2 = rc.binary_design(rain, {"no": {7: (2.0,)}, "yes": {7: (5.0,)}}, ("no", "yes"))
    assert legs2 == [(7, 2.0, "no"), (7, 5.0, "yes")]
    np.testing.assert_array_equal(X2[:, 1], [0, 0, 1])


def test_hedge_effectiveness_perfect_none_and_constant_loss():
    loss = np.array([0.0, 10.0, 0.0, 30.0])
    assert rc.hedge_effectiveness(loss, loss) == pytest.approx(1.0)
    assert rc.hedge_effectiveness(loss, loss + 5) == pytest.approx(1.0)      # a constant does not matter
    assert rc.hedge_effectiveness(loss, np.zeros(4)) == pytest.approx(0.0)
    assert np.isnan(rc.hedge_effectiveness(np.ones(4), loss))


def test_tail_recovery_caps_overpayment_per_year():
    loss = np.array([100.0, 50.0, 0.0, 0.0])
    pay = np.array([200.0, 0.0, 10.0, 0.0])
    assert rc.tail_recovery(loss, pay, top_k=2) == pytest.approx(100.0 / 150.0)


def test_fit_loss_hedge_recovers_a_step_loss_exactly():
    rng = np.random.default_rng(0)
    rain = rng.uniform(0.5, 7.0, 40)
    loss = 80.0 * (rain <= 2.0) + 30.0 * (rain <= 3.0)       # a two-step drought loss
    X, legs = rc.binary_design({7: rain}, {7: (1.0, 2.0, 3.0, 4.0)}, ("no",))
    r = rc.fit_loss_hedge(X, loss, legs)
    w = dict(zip(legs, r["weights"]))
    assert w[(7, 2.0, "no")] == pytest.approx(80.0, abs=1e-6)
    assert w[(7, 3.0, "no")] == pytest.approx(30.0, abs=1e-6)
    assert r["he_in"] == pytest.approx(1.0)
    # out of sample the net payout subtracts each refit's training-mean premium, which moves a little
    assert r["he_loyo"] == pytest.approx(1.0, abs=0.01)
    assert r["tail_loyo"] == pytest.approx(1.0, abs=1e-6)


def test_fit_loss_hedge_ignores_contracts_that_never_vary():
    rain = np.array([1.5, 2.5, 3.5, 4.5, 5.5, 2.2])
    loss = 10.0 * (rain <= 2.5)
    X, legs = rc.binary_design({7: rain}, {7: (1.0, 2.5, 9.0)}, ("no",))   # NO >9 always pays, NO >1 never
    r = rc.fit_loss_hedge(X, loss, legs)
    w = dict(zip(legs, r["weights"]))
    assert w[(7, 9.0, "no")] == 0.0 and w[(7, 1.0, "no")] == 0.0
    assert w[(7, 2.5, "no")] == pytest.approx(10.0)


def test_net_complements_removes_synthetic_cash():
    legs = [(7, 4.0, "no"), (7, 4.0, "yes"), (7, 5.0, "yes")]
    w = rc.net_complements([3.0, 5.0, 1.0], legs)
    np.testing.assert_allclose(w, [0.0, 2.0, 1.0])
    np.testing.assert_allclose(rc.net_complements([3.0, 5.0, 1.0], []), [3.0, 5.0, 1.0])


def test_best_single_strike_picks_the_loss_trigger():
    rain = np.linspace(0.5, 7.0, 30)
    loss = 50.0 * (rain <= 3.0)
    X, legs = rc.binary_design({8: rain}, {8: (1.0, 2.0, 3.0, 4.0)}, ("no",))
    b = rc.best_single_strike(X, loss, legs)
    assert b["leg"] == (8, 3.0, "no")
    assert b["he_loyo"] == pytest.approx(1.0, abs=0.01)


def test_legs_frame_scales_and_drops_zero_legs():
    df = rc.legs_frame([(7, 2.0, "no"), (7, 3.0, "no")], [0.5, 0.0], scale=100)
    assert len(df) == 1 and df.loc[0, "contracts"] == pytest.approx(50.0)


def test_leg_win_probability_by_side_and_window():
    rain = pd.DataFrame({7: [1.0, 2.0, 3.0, np.nan, 5.0]}, index=[2000, 2001, 2002, 2003, 2004])
    rain = rain.reindex(columns=range(1, 13))
    assert rc.leg_win_probability(rain, 7, 2.0, "no", (2000, 2004)) == pytest.approx(2 / 4)
    assert rc.leg_win_probability(rain, 7, 2.0, "yes", (2000, 2004)) == pytest.approx(2 / 4)
    assert rc.leg_win_probability(rain, 7, 2.0, "no", (2002, 2004)) == pytest.approx(0.0)


# ---------------------------------------------------------------------------------------------
# Order books and coverage
# ---------------------------------------------------------------------------------------------

def test_walk_book_buys_no_from_yes_bids_and_yes_from_no_bids():
    book = {"yes_bids": [(0.30, 10.0), (0.20, 5.0)], "no_bids": [(0.60, 4.0)]}
    no = rc.walk_book(book, "no", contracts=12)
    assert no["filled"] == pytest.approx(12.0)
    assert no["cost_usd"] == pytest.approx(10 * 0.70 + 2 * 0.80)
    yes = rc.walk_book(book, "yes", contracts=None)
    assert yes["filled"] == pytest.approx(4.0)
    assert yes["vwap"] == pytest.approx(0.40)
    capped = rc.walk_book(book, "no", contracts=None, max_price=0.75)
    assert capped["filled"] == pytest.approx(10.0)
    with pytest.raises(ValueError):
        rc.walk_book(book, "both")


def test_nearest_station_and_share_within():
    stations = pd.DataFrame({"station_key": ["A", "B"], "lat": [40.0, 45.0], "lon": [-90.0, -90.0]})
    ns = rc.nearest_station([40.1, 44.0], [-90.0, -90.0], stations)
    assert list(ns["nearest_station"]) == ["A", "B"]
    assert ns.loc[0, "distance_mi"] == pytest.approx(6.9, abs=0.1)    # 0.1 degree of latitude
    sh = rc.share_within(ns["distance_mi"], [3.0, 1.0], radii=(10.0, 100.0))
    assert sh[10.0] == pytest.approx(0.75)
    assert sh[100.0] == pytest.approx(1.0)
