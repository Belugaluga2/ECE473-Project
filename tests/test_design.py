"""Tests for contract design (doc 24): utility-optimal step payouts, equal-premium scaling, holdout split."""
import numpy as np
import pytest

from agri_hedge import design as dg
from agri_hedge import exotic as ex
from agri_hedge import hedge_builder as hb


def test_certainty_equivalent_basics():
    assert dg.certainty_equivalent(np.full(10, 1.7), 2.0) == pytest.approx(1.7)
    assert dg.certainty_equivalent(np.full(10, 1.7), 1.0) == pytest.approx(1.7)
    risky = np.array([1.0, 3.0])
    for g in (1.0, 2.0, 4.0):
        assert dg.certainty_equivalent(risky, g) < 2.0                         # risk averse: CE below the mean
    assert dg.certainty_equivalent(risky, 4.0) < dg.certainty_equivalent(risky, 1.0)


def test_full_insurance_when_loss_is_a_function_of_the_bin_and_the_price_is_fair():
    rng = np.random.default_rng(0)
    bins = rng.integers(0, 4, size=400)
    loss_by_bin = np.array([0.8, 0.4, 0.1, 0.0])
    loss = loss_by_bin[bins]
    opt = dg.optimal_step_payout(loss, bins, 4, gamma=2.0, load=0.0)
    w = dg.DEFAULT_WEALTH - loss + opt.values[bins] - opt.premium
    assert np.std(w) < 1e-4                                                     # wealth is the same every year
    d = opt.values - loss_by_bin
    assert np.ptp(d) < 1e-3                                                     # payout = loss + a constant
    assert opt.ce_gain > 0 and opt.converged


def test_load_creates_a_deductible_and_the_optimum_beats_fixed_shapes():
    rng = np.random.default_rng(1)
    bins = rng.integers(0, 5, size=600)
    loss = np.clip(np.array([0.7, 0.35, 0.15, 0.05, 0.0])[bins] + rng.normal(0, 0.05, size=600), 0, 1)
    opt = dg.optimal_step_payout(loss, bins, 5, gamma=2.0, load=0.3)
    assert opt.values[-1] == pytest.approx(0.0, abs=1e-6)                      # the wettest bin pays nothing
    assert opt.values[0] > 0 and np.all(np.diff(opt.values) <= 1e-9)           # falls with rain
    assert 0 < opt.premium < 0.5
    cheap = dg.optimal_step_payout(loss, bins, 5, gamma=2.0, load=0.0)
    assert (cheap.values > 1e-6).sum() >= (opt.values > 1e-6).sum()            # a load widens the deductible
    shapes = {"linear": np.array([1.0, 0.5, 0.2, 0.05, 0.0]), "flat": np.array([1.0, 1.0, 1.0, 0.0, 0.0]),
              "cat": np.array([1.0, 0.1, 0.0, 0.0, 0.0])}
    tab = dg.ce_shares(loss, bins, 5, shapes, gamma=2.0, load=0.3)
    assert tab["optimal"]["share"] == pytest.approx(1.0)
    for name in shapes:
        assert tab[name]["ce_gain"] <= tab["optimal"]["ce_gain"] + 1e-9
        assert 0.0 <= tab[name]["share"] <= 1.0 + 1e-9
    assert tab["linear"]["share"] > tab["flat"]["share"]                        # the closer shape captures more


def test_fixed_premium_variant_spends_the_budget():
    rng = np.random.default_rng(2)
    bins = rng.integers(0, 4, size=300)
    loss = np.array([0.6, 0.3, 0.1, 0.0])[bins]
    opt = dg.optimal_step_payout(loss, bins, 4, gamma=2.0, load=0.2, premium=0.05)
    assert opt.premium == pytest.approx(0.05, abs=1e-4)
    assert opt.values[0] >= opt.values[-1]


def test_equal_premium_scale_and_split_years():
    freq = np.array([0.1, 0.2, 0.3, 0.4])
    lin = np.array([1.0, 0.6, 0.2, 0.0])
    quad = lin ** 2
    k = dg.equal_premium_scale(quad, freq, dg.fair_premium(lin, freq))
    assert k > 1 and dg.fair_premium(k * quad, freq) == pytest.approx(dg.fair_premium(lin, freq))
    tr, te = dg.split_years(np.arange(1951, 2026), 2000)
    assert tr.sum() == 50 and te.sum() == 25 and not (tr & te).any()


def test_optimal_payout_on_repo_data_is_convex_in_station_rain():
    key, month = "DFW", 11
    p = hb.build_problem(hb.CoverageRequest(32.7771, -97.8059, [hb.Window((month,), 1.0)], 0.9, 1000.0, station_key=key))
    loss = ex.shape_target(p, "linear") / 1000.0
    R = hb.station_rain(key)[month].reindex(p.years).to_numpy(float)
    strikes = ex.kalshi_strikes_for(p)(month)
    ok = ~np.isnan(loss) & ~np.isnan(R)
    bins = ex.rain_bins(R[ok], strikes)
    opt = dg.optimal_step_payout(loss[ok], bins, len(strikes) + 1, gamma=2.0, load=0.2)
    assert opt.converged and opt.ce_gain > 0
    assert opt.values[0] > opt.values[2] and opt.values[-1] == pytest.approx(0.0, abs=1e-6)
    assert ex.convexity_ratio(opt.values) > 1.0                                 # the first drop is the biggest
    port = ex.span_step(opt.shape, strikes)
    assert port.cash == pytest.approx(0.0) and np.all(port.yes_weights == 0)   # long-only NO contracts
    ev = dg.evaluate_payout(opt.values, loss[ok], bins, 2.0, 0.2)
    assert ev["ce_gain"] == pytest.approx(opt.ce_gain)
