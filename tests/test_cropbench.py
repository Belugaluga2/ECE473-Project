"""Tests for agri_hedge.cropbench (row-crop rain benchmark, doc 29)."""
import numpy as np
import pandas as pd
import pytest

from agri_hedge import cropbench as cb
from agri_hedge import exotics as ex


def test_haversine_known_distance():
    # O'Hare to Midway is about 15.5 statute miles
    d = cb.haversine_mi(41.96017, -87.93164, 41.78412, -87.75514)
    assert d == pytest.approx(15.2, abs=0.7)
    assert cb.haversine_mi(40.0, -90.0, 40.0, -90.0) == pytest.approx(0.0)


def test_quadratic_trend_recovers_a_quadratic_and_skips_nan():
    years = np.arange(1960, 2026)
    y = 50 + 1.5 * (years - 1960) + 0.01 * (years - 1960) ** 2
    y_missing = y.copy()
    y_missing[[3, 20, 41]] = np.nan
    assert np.allclose(cb.quadratic_trend(years, y_missing), y, atol=1e-6)
    assert np.isnan(cb.quadratic_trend(years[:3], np.array([1.0, np.nan, 2.0]))).all()


def test_yield_loss_fraction_is_shortfall_below_trend():
    years = np.arange(1980, 2026)
    trend = 100 + 2.0 * (years - 1980)
    y = trend.copy()
    y[10] *= 0.7           # a 30% shortfall
    y[20] *= 1.2           # a good year is not a loss
    y[30] = np.nan
    loss, fitted = cb.yield_loss_fraction(years, y)
    assert np.isnan(loss[30])
    assert loss[20] == 0.0
    # the fitted trend is pulled slightly by the two outliers, so allow a few points
    assert loss[10] == pytest.approx(0.30, abs=0.03)
    assert np.nanmax(np.abs(fitted - trend) / trend) < 0.03
    assert np.nanmin(loss) >= 0.0


def test_season_rain_uses_prior_year_months_for_winter_wheat():
    idx = np.arange(1999, 2003)
    monthly = pd.DataFrame({m: 100 * idx + m for m in range(1, 13)}, index=idx, dtype=float)
    out = cb.season_rain(monthly, cb.SEASONS["winter_wheat"], np.array([2000, 2001]))
    assert list(out) == ["m10p", "m11p", "m3", "m4", "m5"]
    assert out["m10p"].tolist() == [199910.0, 200010.0]
    assert out["m3"].tolist() == [200003.0, 200103.0]
    # a harvest year whose prior year is outside the table is unknown
    assert np.isnan(cb.season_rain(monthly, cb.SEASONS["winter_wheat"], np.array([1999]))["m10p"][0])
    assert np.isnan(cb.season_total(out)).sum() == 0


def test_relative_basis_values_and_strikes():
    B, legs = cb.relative_basis(np.array([0.0, 2.0, 4.0, 8.0, np.nan]), 4.0, put_k=(0.5, 1.0), call_k=(1.5,))
    assert legs == [("put", 2.0), ("put", 4.0), ("call", 6.0)]
    assert B[0].tolist() == [0.5, 1.0, 0.0]
    assert B[1].tolist() == [0.0, 0.5, 0.0]
    assert B[3].tolist() == [0.0, 0.0, 0.5]
    assert np.isnan(B[4]).all()


def test_digital_approximation_is_long_only_and_improves_with_finer_strikes():
    rng = np.random.default_rng(1)
    rain = rng.gamma(2.0, 1.6, size=400).round(2)
    put = np.clip(2.5 - rain, 0, None) / 3.0
    call = np.clip(rain - 5.0, 0, None) / 3.0
    errs = {}
    for name, ks in (("whole", ex.strike_grid(1.0, 7.0)), ("third", ex.strike_grid(ex.THIRD_IN, 7.0))):
        wp = cb.digital_approximation(rain, put, "put", ks)
        wc = cb.digital_approximation(rain, call, "call", ks)
        assert (wp >= 0).all() and (wc >= 0).all()
        X = cb.digital_matrix(rain, ks)
        assert X.shape == (400, 2 * len(ks))
        approx = X @ np.concatenate([wp, wc])
        errs[name] = float(np.sqrt(np.mean((approx - put - call) ** 2)))
    assert errs["third"] < errs["whole"]
    # a put only needs strikes below its own strike: no weight on NO binaries above 3 in for a 2.5-in put
    wp = cb.digital_approximation(rain, put, "put", ex.strike_grid(1.0, 7.0))
    assert wp[3:].sum() == pytest.approx(0.0, abs=1e-9)


def test_digital_approximation_handles_empty_inputs():
    assert cb.digital_approximation(np.array([np.nan]), np.array([np.nan]), "put", [1.0, 2.0]).tolist() == [0.0, 0.0]
    assert len(cb.digital_approximation(np.array([1.0]), np.array([0.2]), "put", [])) == 0


def test_pooled_hedge_ratio_recovers_slope_and_floors_at_zero():
    rng = np.random.default_rng(2)
    h = rng.gamma(1.0, 1.0, size=(6, 60))
    y = 0.4 * h + 5.0 + rng.normal(0, 0.01, size=h.shape) + np.arange(6)[:, None]   # county-specific levels
    y[0, 5] = np.nan
    assert cb.pooled_hedge_ratio(y, h) == pytest.approx(0.4, abs=0.01)
    assert cb.pooled_hedge_ratio(y, h, leave_out=3) == pytest.approx(0.4, abs=0.01)
    assert cb.pooled_hedge_ratio(-y, h) == 0.0
    assert cb.pooled_hedge_ratio(y, np.zeros_like(h)) == 0.0


def test_breakeven_load():
    # same payout and risk removed: break-even equals the cheap load
    assert cb.breakeven_load(1.2, 5.0, 1.0, 5.0, 1.0) == pytest.approx(1.2)
    # the dearer contract removes three times the risk for the same payout: it can carry three times the loading margin
    assert cb.breakeven_load(1.2, 5.0, 1.0, 5.0, 3.0) == pytest.approx(1.6)
    # larger payout for the same risk removed lowers the break-even margin proportionally
    assert cb.breakeven_load(1.2, 5.0, 1.0, 10.0, 1.0) == pytest.approx(1.1)
    assert np.isnan(cb.breakeven_load(1.2, 5.0, 0.0, 5.0, 1.0))


def test_collar_columns_shapes():
    rain = {"m6": np.array([0.5, 2.5, 6.0]), "m7": np.array([1.0, np.nan, 3.0])}
    cols = cb.collar_columns(rain, 1.0, strikes=(1.0, 2.0))
    assert len(cols) == 8
    assert cols["NO m6 <= 1.00"].tolist() == [1.0, 0.0, 0.0]
    assert cols["YES m6 > 2.00"].tolist() == [0.0, 1.0, 1.0]
    assert np.isnan(cols["NO m7 <= 1.00"][1])
    assert len(cb.collar_columns(rain, 1.0, strikes=(1.0, 2.0), drought_only=True)) == 4
    assert len(cb.collar_columns(rain, ex.THIRD_IN, max_strike=1.0)) == 12
