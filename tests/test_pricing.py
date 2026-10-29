"""Tests for agri_hedge.pricing (Kalshi hedge payouts and costs vs PRF). Synthetic data only, no network."""
import math

import numpy as np
import pandas as pd
import pytest

from agri_hedge import pricing as pr


# ---------------------------------------------------------------------------------------------
# Building hedges and payouts
# ---------------------------------------------------------------------------------------------

def _weights():
    return pd.DataFrame({
        "interval_name": ["Apr-May", "Apr-May", "Apr-May", "Jul-Aug", "Jan-Feb"],
        "contract_month": [4, 4, 5, 7, 1],
        "strike_in": [1.0, 2.0, 1.0, 3.0, 1.0],
        "weight_per_dollar_protection": [0.10, 0.05, 0.20, 0.30, 9.99],
        "leg_prob_pays_fit_window": [0.1, 0.3, 0.1, 0.5, 0.2],
    })


def test_farm_hedge_legs_scales_by_share_and_protection_and_drops_uninsured_intervals():
    legs = pr.farm_hedge_legs(_weights(), {"Apr-May": 0.6, "Jul-Aug": 0.4}, 10_000)
    assert len(legs) == 4                                  # Jan-Feb not insured
    got = legs.set_index(["contract_month", "strike_in"])["contracts"]
    assert got[(4, 1.0)] == pytest.approx(0.10 * 0.6 * 10_000)
    assert got[(5, 1.0)] == pytest.approx(0.20 * 0.6 * 10_000)
    assert got[(7, 3.0)] == pytest.approx(0.30 * 0.4 * 10_000)
    assert "leg_prob_pays_fit_window" in legs.columns


def test_farm_hedge_legs_empty_when_no_interval_matches():
    legs = pr.farm_hedge_legs(_weights(), {"Oct-Nov": 1.0}, 1000)
    assert legs.empty and "contracts" in legs.columns


def _station():
    rows = []
    for y, (apr, may, jul) in {2000: (0.5, 3.0, 2.0), 2001: (1.5, 0.9, 4.0), 2002: (1.0, 2.0, 3.0)}.items():
        for m, v in ((4, apr), (5, may), (7, jul)):
            rows.append({"station_key": "XXX", "year": y, "month": m, "precip_in": v, "n_missing": 0})
    rows.append({"station_key": "XXX", "year": 2003, "month": 4, "precip_in": 0.2, "n_missing": 1})
    rows.append({"station_key": "XXX", "year": 2003, "month": 5, "precip_in": 0.2, "n_missing": 0})
    rows.append({"station_key": "XXX", "year": 2003, "month": 7, "precip_in": 0.2, "n_missing": 0})
    rows.append({"station_key": "YYY", "year": 2000, "month": 4, "precip_in": 9.0, "n_missing": 0})
    return pd.DataFrame(rows)


def test_rain_wide_blanks_incomplete_months_and_filters_station():
    w = pr.rain_wide(_station(), "XXX")
    assert list(w.columns) == list(range(1, 13))
    assert np.isnan(w.loc[2003, 4])                       # one missing day -> unknown total
    assert w.loc[2003, 5] == pytest.approx(0.2)
    assert w.loc[2000, 4] == pytest.approx(0.5)


def test_no_pays_at_strike_and_nan():
    out = pr.no_pays([0.5, 1.0, 1.01, np.nan], 1.0)
    assert out[0] == 1.0 and out[1] == 1.0                 # exactly at the strike pays NO
    assert out[2] == 0.0 and np.isnan(out[3])


def test_hedge_payout_by_year_sums_legs_and_marks_missing_years():
    rain = pr.rain_wide(_station(), "XXX")
    legs = pd.DataFrame({"contract_month": [4, 5, 7], "strike_in": [1.0, 1.0, 3.0], "contracts": [100.0, 50.0, 10.0]})
    pay = pr.hedge_payout_by_year(legs, rain, [2000, 2001, 2002, 2003])
    assert pay[2000] == pytest.approx(100 + 0 + 10)        # Apr 0.5<=1, May 3.0>1, Jul 2.0<=3
    assert pay[2001] == pytest.approx(0 + 50 + 0)
    assert pay[2002] == pytest.approx(100 + 0 + 10)        # Apr exactly 1.0 pays
    assert np.isnan(pay[2003])                             # April incomplete


def test_leg_probability_and_expected_payout():
    rain = pr.rain_wide(_station(), "XXX")
    assert pr.leg_probability(rain, 4, 1.0, (2000, 2002)) == pytest.approx(2 / 3)
    assert pr.leg_probability(rain, 4, 1.0, (2000, 2003)) == pytest.approx(2 / 3)   # NaN month ignored
    assert pr.leg_probability(rain, 4, 1.0, (2001, 2001)) == 0.0
    assert math.isnan(pr.leg_probability(rain, 4, 1.0, (1990, 1995)))
    legs = pd.DataFrame({"contract_month": [4, 7], "strike_in": [1.0, 3.0], "contracts": [30.0, 10.0]})
    legs = pr.add_leg_probabilities(legs, rain, (2000, 2002))
    assert pr.expected_payout(legs) == pytest.approx(30 * 2 / 3 + 10 * 2 / 3)


# ---------------------------------------------------------------------------------------------
# Fees, capital, calibration
# ---------------------------------------------------------------------------------------------

def test_taker_fee_matches_fee_schedule_examples_and_rounding():
    # Kalshi fee schedule (2022-09-22) table: 1 @ $0.50 -> $0.02, 100 @ $0.50 -> $1.75, 100 @ $0.05 -> $0.34
    fees = pr.taker_fee([1, 100, 100], [0.50, 0.50, 0.05])
    np.testing.assert_allclose(fees, [0.02, 1.75, 0.34])
    # direct members round to $0.0001: 0.07 x 100 x 0.05 x 0.95 = 0.3325
    assert pr.taker_fee([100], [0.05], tick=pr.FEE_TICK_DIRECT)[0] == pytest.approx(0.3325)
    assert pr.taker_fee([0], [0.5])[0] == 0.0
    # fee is symmetric in P and 1 - P
    assert pr.taker_fee([1000], [0.2])[0] == pytest.approx(pr.taker_fee([1000], [0.8])[0])


def test_capital_cost_simple_interest_and_credit():
    assert pr.capital_cost(1000.0, rate=0.0405, days=31) == pytest.approx(1000 * 0.0405 * 31 / 365)
    assert pr.capital_cost(1000.0, rate=0.0405, days=31, credited_rate=0.035) == pytest.approx(1000 * 0.0055 * 31 / 365)
    assert pr.capital_cost(1000.0, rate=0.03, days=31, credited_rate=0.035) == 0.0


def _synthetic_calibration(a, b):
    price = np.array([0.02, 0.07, 0.15, 0.3, 0.5, 0.7, 0.85, 0.93, 0.98])
    z = a + b * np.log(price / (1 - price))
    rate = 1 / (1 + np.exp(-z))
    return pd.DataFrame({"mean_price": price, "yes_rate": rate, "n": 2000})


def test_logistic_calibration_recovers_parameters_and_inverts():
    cal = _synthetic_calibration(-0.4, 1.1)
    a, b = pr.logistic_calibration_fit(cal)
    assert a == pytest.approx(-0.4, abs=0.02) and b == pytest.approx(1.1, abs=0.02)
    # a market with this calibration quotes price p for an outcome whose true rate is cal.yes_rate
    np.testing.assert_allclose(pr.calibrated_yes_price(cal["yes_rate"], a, b), cal["mean_price"], atol=0.01)


def test_calibrated_no_price_identity_and_direction():
    q = np.array([0.1, 0.4, 0.8])
    np.testing.assert_allclose(pr.calibrated_no_price(q, 0.0, 1.0), q)         # perfectly calibrated
    # a < 0: YES is priced above its win rate, so the matching NO is priced below its win rate
    assert np.all(pr.calibrated_no_price(q, -0.4, 1.0) < q)
    assert pr.calibrated_no_price([1.0], -0.4, 1.0)[0] <= pr.PRICE_MAX


def test_price_legs_fair_maker_taker_and_missing_price():
    legs = pd.DataFrame({"contracts": [100.0, 200.0, 50.0], "q": [0.30, 0.995, np.nan]})
    maker = pr.price_legs(legs, "q", half_spread=0.0, taker=False, rate=0.0)
    assert maker["price"].iloc[1] == pr.PRICE_MAX                                # clipped to 99c
    t = pr.cost_totals(maker)
    assert t["cost_usd"] == pytest.approx(100 * 0.30 + 200 * 0.99)
    assert t["contracts_unpriced"] == 50.0 and t["fee_usd"] == 0.0
    taker = pr.price_legs(legs, "q", half_spread=0.02, taker=True, rate=0.04, days=365)
    assert taker["price"].iloc[0] == pytest.approx(0.32)
    fee0 = math.ceil(0.07 * 100 * 0.32 * 0.68 * 100 - 1e-9) / 100
    assert taker["fee_usd"].iloc[0] == pytest.approx(fee0)
    assert taker["capital_usd"].iloc[0] == pytest.approx((32 + fee0) * 0.04)


# ---------------------------------------------------------------------------------------------
# Order books
# ---------------------------------------------------------------------------------------------

def test_walk_no_book_takes_cheapest_no_first_and_respects_cap():
    yes_bids = [[0.70, 10], [0.60, 20], [0.02, 1000], [0.0, 5]]          # NO asks: 0.30, 0.40, 0.98
    assert pr.no_asks_from_yes_bids(yes_bids)[0] == (0.30, 10.0)
    w = pr.walk_no_book(yes_bids, contracts=25)
    assert w["filled"] == 25 and w["cost_usd"] == pytest.approx(10 * 0.30 + 15 * 0.40)
    assert w["levels_used"] == 2
    assert w["fee_usd"] == pytest.approx(float(pr.taker_fee([10], [0.30])[0] + pr.taker_fee([15], [0.40])[0]))
    capped = pr.walk_no_book(yes_bids, contracts=None, max_price=0.95)
    assert capped["filled"] == 30 and capped["depth_available"] == 30
    allin = pr.walk_no_book(yes_bids, contracts=5000)
    assert allin["filled"] == 1030
    empty = pr.walk_no_book([], contracts=10)
    assert empty["filled"] == 0 and math.isnan(empty["vwap"])


# ---------------------------------------------------------------------------------------------
# Comparisons
# ---------------------------------------------------------------------------------------------

def test_payout_comparison_perfect_and_designed_misses():
    prf = np.array([0.0, 100.0, 500.0, 0.0, 300.0])
    perfect = pr.payout_comparison(prf, prf, protection=1000.0, years=[1, 2, 3, 4, 5])
    assert perfect["corr"] == pytest.approx(1.0) and perfect["recovery"] == pytest.approx(1.0)
    assert perfect["he"] == pytest.approx(1.0) and perfect["prf_only_years"] == 0
    hedge = np.array([200.0, 100.0, 100.0, 0.0, np.nan])
    m = pr.payout_comparison(prf, hedge, protection=1000.0, years=[1, 2, 3, 4, 5])
    assert m["n_years"] == 4                                 # year 5 dropped (NaN)
    assert m["prf_only_years"] == 1 and m["prf_only_list"] == "3"      # PRF 500 >= 50, hedge 100 < 250
    assert m["kalshi_only_years"] == 1 and m["kalshi_only_list"] == "1"  # hedge 200 >= 50, PRF 0
    assert m["recovery"] == pytest.approx((0 + 100 + 100 + 0) / 600)
    assert m["payout_ratio"] == pytest.approx(400 / 600)
    assert m["worst_shortfall_year"] == 3 and m["worst_shortfall_usd"] == pytest.approx(400)
    assert m["worst_overpay_year"] == 1 and m["worst_overpay_usd"] == pytest.approx(200)


def test_load_and_subsidy_to_match():
    assert pr.load_factor(49.0, 100.0) == pytest.approx(0.49)
    # PRF: premium 49 buys 100 expected (net +51). Kalshi: cost 110 buys 100 expected (net -10).
    s = pr.subsidy_to_match(kalshi_cost=110.0, kalshi_expected=100.0, prf_producer_premium=49.0, prf_expected=100.0)
    assert s["dollars_same_net"] == pytest.approx(61.0)
    assert s["share_same_net"] == pytest.approx(61.0 / 110.0)
    assert s["share_same_load"] == pytest.approx(1 - 0.49 * 100 / 110)
    # check: after the subsidy the farmer's net equals PRF's
    assert 100.0 - (110.0 - s["dollars_same_net"]) == pytest.approx(100.0 - 49.0)
