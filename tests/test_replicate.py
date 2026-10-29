"""Tests for agri_hedge.replicate (PRF replication with monthly NO-contract ladders).

All synthetic data; no network and no files from data/processed are needed.
"""
import numpy as np
import pandas as pd
import pytest

from agri_hedge.replicate import (
    DEFAULT_KALSHI_STRIKES,
    fair_cost,
    fine_strikes,
    fit_ladder,
    kalshi_strike_sets,
    ladder_design,
    loyo_predictions,
    no_payoff,
    prf_payout,
    replicate_interval,
    replication_metrics,
    station_index,
    evaluate,
)


# ---------------------------------------------------------------------------------------------
# Payoffs
# ---------------------------------------------------------------------------------------------

def test_prf_payout_formula_and_scales():
    idx = np.array([100.0, 90.0, 89.9, 45.0, 0.0, np.nan])
    out = prf_payout(idx, 0.90)
    assert out[0] == 0.0 and out[1] == 0.0           # at the trigger pays nothing
    assert out[2] == pytest.approx(0.1 / 90)
    assert out[3] == pytest.approx(0.5)
    assert out[4] == pytest.approx(1.0)
    assert np.isnan(out[5])
    np.testing.assert_allclose(prf_payout(idx[:5], 90), out[:5])  # percent input accepted
    assert prf_payout(np.array([35.0]), 0.70)[0] == pytest.approx(0.5)


def test_no_payoff_is_rain_at_or_below_strike():
    rain = np.array([0.0, 0.99, 1.0, 1.01, np.nan])
    out = no_payoff(rain, 1.0)
    # Kalshi "Above 1 inch" resolves YES only if total > 1, so exactly 1.00 pays the NO side.
    np.testing.assert_array_equal(out[:4], [1.0, 1.0, 1.0, 0.0])
    assert np.isnan(out[4])


def test_station_index():
    np.testing.assert_allclose(station_index([2.0, 4.0], 4.0), [50.0, 100.0])


# ---------------------------------------------------------------------------------------------
# Strike sets and design
# ---------------------------------------------------------------------------------------------

def test_fine_strikes_cover_the_maximum():
    s = fine_strikes(3.1)
    assert s[0] == 0.25 and s[-1] == 3.25
    assert np.allclose(np.diff(s), 0.25)
    assert fine_strikes(3.0)[-1] == 3.0            # a total equal to the top strike still pays NO
    assert fine_strikes(0.0)[-1] == 0.25


def _markets():
    rows = []
    for mon, strikes in (("2025-11", range(1, 9)), ("2026-11", range(1, 8)), ("2026-10", range(1, 11)),
                         ("2026-01", range(1, 8)), ("2026-02", range(1, 8))):
        for k in strikes:
            rows.append({"series_ticker": "KXTEST", "event_ticker": f"KXTEST-{mon}", "contract_month": mon,
                         "floor_strike": float(k), "strike_type": "greater", "is_single_month": True})
    rows.append({"series_ticker": "KXTEST", "event_ticker": "KXTEST-X", "contract_month": "2026-03",
                 "floor_strike": 9.0, "strike_type": "greater", "is_single_month": False})
    rows.append({"series_ticker": "KXOTHER", "event_ticker": "KXOTHER-1", "contract_month": "2026-05",
                 "floor_strike": 0.5, "strike_type": "greater", "is_single_month": True})
    return pd.DataFrame(rows)


def test_kalshi_strike_sets_union_and_fallback():
    sets = kalshi_strike_sets(_markets(), "KXTEST")
    assert sets[11] == tuple(float(k) for k in range(1, 9))     # union of Nov 2025 and Nov 2026
    assert sets[10] == tuple(float(k) for k in range(1, 11))
    assert sets[1] == DEFAULT_KALSHI_STRIKES
    assert sets[3] == DEFAULT_KALSHI_STRIKES                      # multi-month market ignored -> fallback
    assert sets[5] == DEFAULT_KALSHI_STRIKES                      # other series ignored
    empty = kalshi_strike_sets(_markets(), "KXNONE")
    assert all(v == DEFAULT_KALSHI_STRIKES for v in empty.values())


def test_ladder_design_columns():
    X, legs = ladder_design({4: np.array([0.5, 2.0]), 5: np.array([3.0, 1.0])}, {4: [1.0, 2.0], 5: [1.0]})
    assert legs == [(4, 1.0), (4, 2.0), (5, 1.0)]
    np.testing.assert_array_equal(X, [[1, 1, 0], [0, 1, 1]])


# ---------------------------------------------------------------------------------------------
# Fitting
# ---------------------------------------------------------------------------------------------

def _synthetic_design(n=200, seed=0):
    rng = np.random.default_rng(seed)
    r1, r2 = rng.gamma(2.0, 1.0, n), rng.gamma(2.0, 1.0, n)
    X, legs = ladder_design({1: r1, 2: r2}, {1: [0.5, 1.0, 2.0, 4.0], 2: [0.5, 1.0, 2.0, 4.0]})
    return X, legs, r1, r2


def test_fit_ladder_recovers_nonnegative_weights():
    X, legs, *_ = _synthetic_design()
    w_true = np.array([0.0, 0.2, 0.1, 0.0, 0.05, 0.0, 0.3, 0.0])
    y = X @ w_true
    f = fit_ladder(X, y, legs=legs)
    np.testing.assert_allclose(f.weights, w_true, atol=1e-8)
    assert f.intercept == 0.0
    assert f.legs == legs


def test_fit_ladder_is_long_only_and_intercept_variant():
    X, legs, *_ = _synthetic_design()
    y = 0.4 - X[:, 1] * 0.3           # payoff falls when the leg pays: needs a short position
    f = fit_ladder(X, y)
    assert (f.weights >= 0).all()
    fi = fit_ladder(X, y - 0.4 + 0.05, fit_intercept=True)   # y = 0.05 - 0.3 x: still no short allowed
    assert (fi.weights >= 0).all()
    g = fit_ladder(X, 0.1 + X[:, 2] * 0.2, fit_intercept=True)
    assert g.intercept == pytest.approx(0.1, abs=1e-8)
    assert g.weights[2] == pytest.approx(0.2, abs=1e-8)
    gn = fit_ladder(X, -0.1 + X[:, 2] * 0.2, fit_intercept=True)   # negative cash term allowed
    assert gn.intercept == pytest.approx(-0.1, abs=1e-8)


def test_ridge_shrinks_and_nan_rows_dropped():
    X, legs, *_ = _synthetic_design()
    y = X @ np.array([0.0, 0.2, 0.1, 0.0, 0.05, 0.0, 0.3, 0.0])
    w0 = fit_ladder(X, y).weights
    w1 = fit_ladder(X, y, ridge=0.05).weights
    assert np.sum(w1 ** 2) < np.sum(w0 ** 2)
    y_nan = y.copy()
    y_nan[:5] = np.nan
    np.testing.assert_allclose(fit_ladder(X, y_nan).weights, w0, atol=1e-8)


def test_loyo_matches_manual_refit():
    X, legs, *_ = _synthetic_design(n=40, seed=3)
    rng = np.random.default_rng(1)
    y = np.clip(X @ np.array([0.1, 0.1, 0, 0, 0.1, 0, 0, 0]) + rng.normal(0, 0.05, 40), 0, None)
    pred = loyo_predictions(X, y)
    keep = np.ones(40, bool)
    keep[7] = False
    manual = fit_ladder(X[keep], y[keep]).predict(X[7:8])[0]
    assert pred[7] == pytest.approx(manual)
    assert pred.shape == y.shape


def test_fair_cost_is_weight_times_leg_probability():
    X, legs, *_ = _synthetic_design()
    f = fit_ladder(X, X @ np.array([0.0, 0.2, 0.1, 0.0, 0.05, 0.0, 0.3, 0.0]))
    assert fair_cost(f, X) == pytest.approx(float(np.sum(f.weights * X.mean(axis=0))))


# ---------------------------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------------------------

def test_metrics_perfect_zero_and_shifted_hedges():
    idx = np.array([50.0, 65.0, 80.0, 95.0, 110.0, 130.0, 60.0, 100.0])
    prf = prf_payout(idx, 0.9)
    m = replication_metrics(prf, prf, idx)
    assert m["he"] == pytest.approx(1.0) and m["rmse"] == pytest.approx(0.0)
    assert m["tail_capture"] == pytest.approx(1.0) and m["miss_rate"] == 0.0 and m["false_alarm_rate"] == 0.0
    assert m["n_tail"] == 3
    z = replication_metrics(prf, np.zeros_like(prf), idx)
    assert z["he"] == pytest.approx(0.0) and z["tail_capture"] == 0.0 and z["miss_rate"] == 1.0
    assert z["bias"] == pytest.approx(-prf.mean()) and z["mean_under"] == pytest.approx(prf.mean())
    s = replication_metrics(prf, prf + 0.15, idx)
    assert s["he"] == pytest.approx(1.0)          # a constant shift does not change the variance
    assert s["bias"] == pytest.approx(0.15) and s["mean_over"] == pytest.approx(0.15)
    assert s["false_alarm_rate"] == 1.0           # 0.15 paid in years PRF pays nothing
    assert s["corr"] == pytest.approx(1.0)


def test_metrics_handle_nan_and_constant_prf():
    m = replication_metrics(np.zeros(5), np.array([0.0, 0.1, np.nan, 0.0, 0.0]), np.full(5, 120.0))
    assert m["n_years"] == 4 and np.isnan(m["he"]) and np.isnan(m["corr"]) and np.isnan(m["tail_capture"])


# ---------------------------------------------------------------------------------------------
# Whole-interval replication
# ---------------------------------------------------------------------------------------------

def _synthetic_site(n=75, seed=7, noise=0.0):
    rng = np.random.default_rng(seed)
    years = np.arange(1951, 1951 + n)
    r1, r2 = rng.gamma(3.0, 0.8, n), rng.gamma(3.0, 0.9, n)
    normal = float(np.mean(r1 + r2))
    grid_index = 100 * (r1 + r2) / normal * np.exp(rng.normal(0, noise, n))
    return years, r1, r2, normal, grid_index


def test_replicate_interval_identical_station_and_grid():
    years, r1, r2, normal, gi = _synthetic_site()
    fine = {m: tuple(fine_strikes(max(r1.max(), r2.max()))) for m in (4, 5)}
    kal = {m: DEFAULT_KALSHI_STRIKES for m in (4, 5)}
    rep = replicate_interval(years, gi, r1, r2, (4, 5), 0.9, (1951, 2009), fine, kal, normal,
                             full_window=(1951, 2025))
    # H1 is exact when station == grid.
    np.testing.assert_allclose(rep.hedges[("H1", "none", "split")], rep.prf)
    rows = pd.DataFrame(evaluate(rep, (2010, 2025)))
    h1 = rows[(rows.hedge_family == "H1") & (rows.eval_set == "loyo")].iloc[0]
    assert h1["he"] == pytest.approx(1.0)
    tr = rows[rows.eval_set == "train"].set_index("hedge_family")
    # Kalshi integer strikes are a subset of the 0.25-inch grid, so H2 fits at least as well in sample.
    assert tr.loc["H2", "rmse"] <= tr.loc["H3", "rmse"] + 1e-12
    assert 0.0 < tr.loc["H3", "he"] <= tr.loc["H2", "he"] + 1e-12 <= 1.0 + 1e-12
    # Weights are long-only and the fair cost equals the mean in-sample payout.
    f = rep.fits[("H3", "no_intercept", "train")]
    assert (f.weights >= 0).all()
    probs = rep.leg_probs[("H3", "train")]
    assert np.sum(f.weights * probs) == pytest.approx(np.mean(rep.hedges[("H3", "no_intercept", "split")][rep.train_mask]))
    assert ("H2", "no_intercept", "loyo") in rep.hedges and ("H3", "no_intercept", "full") in rep.hedges
    assert set(rows.eval_set) == {"train", "test", "loyo"}


def test_replicate_interval_drops_missing_years_and_noise_lowers_h1():
    years, r1, r2, normal, gi = _synthetic_site(noise=0.25)
    r1 = r1.copy()
    r1[3] = np.nan
    kal = {m: DEFAULT_KALSHI_STRIKES for m in (6, 7)}
    rep = replicate_interval(years, gi, r1, r2, (6, 7), 0.9, (1951, 2009), kal, kal, normal, do_loyo=False)
    assert len(rep.years) == len(years) - 1 and 1954 not in rep.years
    m = replication_metrics(rep.prf, rep.hedges[("H1", "none", "split")], rep.index)
    assert 0.0 < m["he"] < 1.0


def test_he_guard_and_pooled_he():
    from agri_hedge.replicate import pooled_he
    idx = np.array([120.0, 110.0, 85.0, 130.0, 100.0, 95.0])     # PRF pays in one year only
    prf = prf_payout(idx, 0.9)
    m = replication_metrics(prf, prf * 0.5, idx)
    assert m["n_prf_pay"] == 1 and np.isnan(m["he"])          # too few payout years for HE
    assert m["var_prf"] > 0 and m["var_resid"] == pytest.approx(m["var_prf"] * 0.25)
    rows = pd.DataFrame([
        {"n_years": 10, "var_prf": 0.04, "var_resid": 0.01},     # HE 0.75
        {"n_years": 10, "var_prf": 0.0001, "var_resid": 0.001},  # HE -9 (barely varies)
    ])
    assert pooled_he(rows) == pytest.approx(1 - 0.011 / 0.0401)
    assert pooled_he(rows) > 0.7                                 # not dominated by the tiny group


def test_h1_scaled_variant_shrinks_toward_zero_when_unrelated():
    rng = np.random.default_rng(11)
    years = np.arange(1951, 2026)
    r1, r2 = rng.gamma(3.0, 0.8, 75), rng.gamma(3.0, 0.9, 75)
    normal = float(np.mean(r1 + r2))
    gi = 100 * rng.gamma(6.0, 1 / 6.0, 75)                    # grid index unrelated to the station
    kal = {m: DEFAULT_KALSHI_STRIKES for m in (8, 9)}
    rep = replicate_interval(years, gi, r1, r2, (8, 9), 0.9, (1951, 2009), kal, kal, normal, do_loyo=False)
    w = rep.fits[("H1", "scaled", "train")].weights[0]
    assert 0.0 <= w < 1.0
    tr = rep.train_mask
    raw = replication_metrics(rep.prf[tr], rep.hedges[("H1", "none", "split")][tr])
    scl = replication_metrics(rep.prf[tr], rep.hedges[("H1", "scaled", "split")][tr])
    assert scl["rmse"] <= raw["rmse"] + 1e-12
