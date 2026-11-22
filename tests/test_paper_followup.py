"""Check incremental-cover accounting and finite versus absent market capacity."""
import numpy as np
import pytest

from agri_hedge.paper_followup import (
    addon_statistics, keep_prf, required_depth_multiplier,
)


def test_restore_full_prf_without_changing_market_component_or_double_counting_cash():
    prf = np.array([0., 100., 200.])
    market = np.array([20., 0., 70.])
    restored = keep_prf(prf, .8 * prf + market, 95., 100.)
    assert np.allclose(restored['component'], market)
    assert np.allclose(restored['total_payout'], prf + market)
    assert restored['component_cost'] == 15.
    assert restored['total_premium'] == 115.
    assert np.isclose(restored['cash_retained'], 5.)
    assert np.isclose(restored['total_premium'] + restored['cash_retained'], 120.)


def test_restore_rejects_spending_outside_frozen_extra_budget():
    with pytest.raises(ValueError):
        keep_prf([0], [0], 101., 100.)
    with pytest.raises(ValueError):
        keep_prf([0], [0], 79., 100.)


def test_cash_and_constant_cover_include_cost_once_and_do_not_claim_variance_reduction():
    loss = np.arange(10.) * 10
    prf = loss * .5
    cash = addon_statistics(loss, prf, np.zeros(10), 10., 0., draws=20)
    assert cash['mean_net_gain_vs_cash'] == 0
    assert cash['residual_variance_reduction'] == 0
    assert cash['worst5_shortfall_reduction'] == 0
    # A constant $5 payout bought for $7 costs $2 relative to retained cash.
    constant = addon_statistics(loss, prf, np.full(10, 5.), 10., 7., draws=20)
    assert constant['mean_net_gain_vs_cash'] == -2
    assert constant['residual_variance_reduction'] == 0
    assert constant['worst5_shortfall_reduction'] == -2


def test_uncertainty_is_reproducible_and_addon_can_reduce_residual_risk():
    loss = np.arange(12.) * 10
    prf = loss * .4
    market = loss * .2
    a = addon_statistics(loss, prf, market, 10., 3., draws=50)
    b = addon_statistics(loss, prf, market, 10., 3., draws=50)
    assert a == b
    assert np.isclose(a['residual_variance_reduction'], 1 - (.4 / .6) ** 2)
    assert a['worst5_shortfall_reduction'] > 0


def test_zero_offer_requires_a_new_quote_rather_than_more_of_zero():
    assert required_depth_multiplier([10, 0], [5, 0]) == (2., 0)
    assert required_depth_multiplier([10, 8], [20, 16]) == (1., 0)
    assert required_depth_multiplier([0, 0], [0, 0]) == (1., 0)
    multiplier, missing = required_depth_multiplier([10, 8], [5, 0])
    assert np.isinf(multiplier) and missing == 1
