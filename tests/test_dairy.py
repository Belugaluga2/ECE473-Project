"""Dairy heat-stress hedge (doc 24): index arithmetic, fitting, day-ahead pricing."""
import numpy as np
import pandas as pd
import pytest

from agri_hedge import dairy as dy


def synthetic_daily(farm_offset=0.0, noise=0.0, seed=0):
    """Airport highs with a random yearly heat level; farm = airport + offset (+ noise)."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("1951-05-01", "2025-09-30", freq="D")
    dates = dates[dates.month.isin(range(5, 10))]
    years = dates.year.to_numpy()
    level = pd.Series(rng.normal(0, 3, 2026), index=range(2026))
    air = 88 + level.loc[years].to_numpy() + rng.normal(0, 5, len(dates))
    farm = air + farm_offset + rng.normal(0, noise, len(dates))
    air, farm = np.round(air), np.round(farm)  # highs settle in whole degrees
    return pd.DataFrame({"site": "TX_erath", "date": dates, "airport_tmax_f": air,
                         "farm_tmax_f": farm, "airport_filled_from_thread": False})


def test_heat_load():
    assert dy.heat_load([79, 80, 85, 92]) == pytest.approx(0 + 0 + 5 + 12)
    assert dy.heat_load([70, 75], threshold=72) == pytest.approx(3)


def test_usd_per_degree_day():
    # 0.2 kg x 0.67 THI/F x 2.20462 lb/kg x $21/cwt / 100
    assert dy.USD_PER_COW_DEGDAY == pytest.approx(0.2 * 0.67 * 2.20462 * 0.21)


def test_build_problem_counts_and_trigger():
    p = dy.build_problem("TX_erath", synthetic_daily())
    assert p.years[0] == 1951 and p.years[-1] == 2025 and len(p.years) == 75
    assert len(p.legs) == p.X.shape[1] == len(p.q)
    # X counts days with airport high above the strike in that month
    m, k = p.legs[0]
    d = p.daily
    first = ((d.year == 1951) & (d.month == m) & (d.airport_tmax_f > k)).sum()
    assert p.X[0, 0] == first
    tr = p.mask(dy.TRAIN)
    assert p.trigger_usd == pytest.approx(p.loss_usd[tr].mean())
    assert (p.target_usd >= 0).all()


def test_identical_farm_and_airport_index_option_hedges_well():
    p = dy.build_problem("TX_erath", synthetic_daily())
    tr, te = p.mask(dy.TRAIN), p.mask(dy.TEST)
    b, K = dy.fit_index_option(p.airport_hl, p.target_usd, tr)
    from agri_hedge.optimizer import hedge_effectiveness
    he = hedge_effectiveness(p.target_usd[te], b * np.maximum(p.airport_hl[te] - K, 0))
    assert he > 0.9


def test_ladder_seasonal_beats_day_ahead():
    p = dy.build_problem("TX_erath", synthetic_daily(noise=1.0))
    tr, te = p.mask(dy.TRAIN), p.mask(dy.TEST)
    n = dy.fit_ladder(p.X, p.target_usd, tr, p.q)
    assert (n >= 0).all() and n.dtype.kind == "i"
    from agri_hedge.optimizer import hedge_effectiveness
    seasonal = hedge_effectiveness(p.target_usd[te], p.X[te] @ n)
    day_ahead = dy.day_ahead_he(p, n, p.target_usd, seeds=3)
    assert seasonal > 0.5
    assert day_ahead < seasonal - 0.3


def test_forecasts_are_calibrated():
    """T = F + e with e roughly uncorrelated with F, and error sd capped at sigma."""
    p = dy.build_problem("TX_erath", synthetic_daily())
    f, sd = dy.simulate_forecasts(p, sigma=3.5, seed=1)
    t = p.daily.airport_tmax_f.to_numpy()
    e = t - f
    assert abs(np.corrcoef(e, f)[0, 1]) < 0.05
    assert abs(e.mean()) < 0.1
    assert (sd <= 3.5 + 1e-9).all()
    assert e.std() == pytest.approx(np.sqrt(np.mean(sd ** 2)), rel=0.05)


def test_day_ahead_features_have_zero_mean():
    p = dy.build_problem("TX_erath", synthetic_daily())
    F = dy.day_ahead_features(p, seed=2)
    days_per_year = p.days.astype(float)
    # Fair prices: average net payoff per contract-day is close to zero on every leg
    assert np.abs(F.mean(axis=0) / days_per_year).max() < 0.02


def test_seasonal_cost_above_fair():
    p = dy.build_problem("TX_erath", synthetic_daily())
    n = np.zeros(len(p.legs), int)
    n[0] = 10
    c = dy.seasonal_cost(p, n)
    assert c["cost_usd"] > c["fair_payout_usd"] > 0
    assert c["contract_days"] == 10 * p.days[0]
    assert c["fee_usd"] > 0 and c["capital_usd"] > 0


def test_committed_data_reproduces_doc_numbers():
    r = dy.evaluate("CO_weld", seeds=3)
    assert r["n_train"] == 50 and r["n_test"] == 25
    assert r["he_linear_basis"] == pytest.approx(0.86, abs=0.01)
    assert r["he_index_option"] == pytest.approx(0.67, abs=0.01)
    assert r["he_day_ahead"] < r["he_ladder_seasonal"]
