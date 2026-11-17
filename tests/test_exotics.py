"""Tests for agri_hedge.exotics (third-inch strike pricing and exotic rain payoffs). Synthetic data only."""
import numpy as np
import pandas as pd
import pytest

from agri_hedge import exotics as ex


# ---------------------------------------------------------------------------------------------
# Strike grids and fair probabilities
# ---------------------------------------------------------------------------------------------

def test_third_inch_grid_contains_whole_inches_and_rounds_to_hundredths():
    ks = ex.third_inch_strikes(3.0)
    assert list(ks) == [0.33, 0.67, 1.0, 1.33, 1.67, 2.0, 2.33, 2.67, 3.0]
    assert set(ex.whole_inch_strikes(3.0)) <= set(ks)


def test_strike_grid_min_and_top():
    assert list(ex.strike_grid(0.5, 1.2)) == [0.5, 1.0, 1.5]          # first multiple at or above max
    assert list(ex.strike_grid(1.0, 3.0, min_strike=2)) == [2.0, 3.0]
    with pytest.raises(ValueError):
        ex.strike_grid(0, 1)


def test_yes_and_no_payoffs_at_the_strike_and_nan():
    rain = np.array([0.33, 0.34, 1.0, np.nan])
    y = ex.yes_payoff(rain, 0.33)
    n = ex.no_payoff(rain, 0.33)
    assert list(y[:3]) == [0.0, 1.0, 1.0] and np.isnan(y[3])      # strictly greater pays YES
    assert list(n[:3]) == [1.0, 0.0, 0.0] and np.isnan(n[3])


def test_empirical_yes_prob_and_wilson():
    p, k, n = ex.empirical_yes_prob([0.5, 1.5, 2.5, np.nan], 1.0)
    assert (p, k, n) == (2 / 3, 2, 3)
    lo, hi = ex.wilson_interval(18, 35)
    assert lo < 18 / 35 < hi and 0 <= lo and hi <= 1
    assert ex.wilson_interval(0, 0) == (pytest.approx(np.nan, nan_ok=True), pytest.approx(np.nan, nan_ok=True))


def test_zero_inflated_gamma_recovers_dry_share_and_tail():
    rng = np.random.default_rng(0)
    vals = np.where(rng.random(2000) < 0.3, 0.0, rng.gamma(2.0, 1.5, 2000))
    fit = ex.zi_gamma_fit(vals)
    assert fit["p0"] == pytest.approx(0.3, abs=0.03)
    assert fit["shape"] == pytest.approx(2.0, rel=0.15)
    emp = ex.empirical_yes_prob(vals, 3.0)[0]
    assert float(ex.zi_gamma_yes_prob(fit, 3.0)) == pytest.approx(emp, abs=0.03)
    assert np.isnan(ex.zi_gamma_yes_prob(ex.zi_gamma_fit([0, 0, 0, 1.0]), 1.0))


def test_fair_price_table_windows_ci_and_gamma():
    yrs = np.arange(1951, 2026)
    rain = pd.Series(np.linspace(0.1, 7.5, len(yrs)), index=yrs)
    t = ex.fair_price_table(rain, [1.0, 4.0], {"a": (1951, 2025), "b": (1991, 2025)}, ci_window="b", gamma_window="a")
    assert list(t["strike_in"]) == [1.0, 4.0]
    assert t["n_a"].iloc[0] == 75 and t["n_b"].iloc[0] == 35
    assert t["p_yes_a"].iloc[0] > t["p_yes_a"].iloc[1]
    assert (t["ci90_lo"] <= t["p_yes_b"]).all() and (t["p_yes_b"] <= t["ci90_hi"]).all()
    assert t["p_yes_gamma"].notna().all()


# ---------------------------------------------------------------------------------------------
# Ladder resolution
# ---------------------------------------------------------------------------------------------

def test_bin_masses_sum_to_one_and_informative_count():
    p = [0.9, 0.5, 0.04]
    assert np.sum(ex.bin_masses(p)) == pytest.approx(1.0)
    assert list(ex.bin_masses(p)) == pytest.approx([0.1, 0.4, 0.46, 0.04])
    assert ex.informative_count(p) == 2


def test_finer_ladder_copies_a_linear_put_at_least_as_well():
    rng = np.random.default_rng(1)
    rain = rng.gamma(2.5, 1.2, 300)
    target = ex.linear_put_payoff(rain, 2.5)
    coarse = ex.ladder_approximation(target, rain, ex.whole_inch_strikes(7))
    fine = ex.ladder_approximation(target, rain, ex.third_inch_strikes(7))
    assert fine["r2"] >= coarse["r2"] - 1e-9
    assert fine["rmse"] <= coarse["rmse"] + 1e-9
    assert fine["fair_cost"] == pytest.approx(fine["target_mean"], abs=0.02)


def test_ladder_resolution_keys_and_defaults():
    rain = np.array([0.2, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0])
    r = ex.ladder_resolution(rain, ex.whole_inch_strikes(7))
    assert r["trigger_in"] == pytest.approx(0.9 * rain.mean())
    assert 0 <= r["max_bin"] <= 1 and r["n_strikes"] == 7


# ---------------------------------------------------------------------------------------------
# Exotic payoffs
# ---------------------------------------------------------------------------------------------

def test_two_month_worst_and_and_or_digitals():
    r1 = np.array([0.5, 2.0, np.nan])
    r2 = np.array([1.0, 0.4, 1.0])
    assert list(ex.two_month_total(r1, r2)[:2]) == [1.5, 2.4]
    w = ex.worst_month(r1, r2)
    assert list(w[:2]) == [0.5, 0.4] and np.isnan(w[2])
    assert list(ex.and_digital(r1, r2, 1.0, 1.0)[:2]) == [1.0, 0.0]
    assert list(ex.or_digital(r1, r2, 1.0, 1.0)[:2]) == [1.0, 1.0]
    assert np.isnan(ex.or_digital(r1, r2, 1.0, 1.0)[2])


def test_quantile_strikes_snap_to_third_inch_grid():
    rain = np.linspace(0.1, 5, 50)
    ks = ex.quantile_strikes(rain, [0.2, 0.5])
    assert all(abs(k * 3 - round(k * 3)) < 0.02 for k in ks)      # multiples of 1/3 to the cent
    assert ks.min() >= 0.33


def test_dry_spell_wet_days_and_max_daily():
    d = [0.0, 0.0, 0.05, 0.0, 0.2, 0.0, 0.0, 0.0, 0.0, 1.3]
    assert ex.longest_dry_spell(d) == 4                           # four days under 0.10 after the 0.2
    assert ex.longest_dry_spell(d, wet_threshold=0.01) == 4       # 0.05 counts as wet at 0.01
    assert ex.wet_day_count(d) == 2 and ex.wet_day_count(d, 0.01) == 3
    assert ex.max_daily(d) == 1.3
    assert np.isnan(ex.longest_dry_spell([0.0, np.nan]))


def test_interval_daily_stats_marks_incomplete_windows():
    days = pd.date_range("2000-04-01", "2001-05-31", freq="D")
    v = np.zeros(len(days))
    v[(days.month == 5) & (days.year == 2000) & (days.day == 10)] = 2.0
    daily = pd.DataFrame({"date": days, "precip_in": v})
    daily = daily[~((daily["date"].dt.year == 2001) & (daily["date"].dt.month == 4) & (daily["date"].dt.day == 3))]  # drop a day
    st = ex.interval_daily_stats(daily, (4, 5))
    assert st.loc[2000, "complete"] and st.loc[2000, "total_in"] == 2.0
    assert st.loc[2000, "max_1day_in"] == 2.0 and st.loc[2000, "wet_days"] == 1
    assert st.loc[2000, "dry_spell_days"] == 39                   # Apr 1 - May 9 (39 days) beats May 11 - May 31 (21)
    assert not st.loc[2001, "complete"] and np.isnan(st.loc[2001, "total_in"])


def test_dry_spell_value_in_interval_stats():
    # 30 dry days in April, rain on May 10, then dry: longest run is April 1 .. May 9 = 39 days
    days = pd.date_range("2000-04-01", "2000-05-31", freq="D")
    v = np.zeros(len(days))
    v[days.get_loc(pd.Timestamp("2000-05-10"))] = 0.5
    st = ex.interval_daily_stats(pd.DataFrame({"date": days, "precip_in": v}), (4, 5))
    assert st.loc[2000, "dry_spell_days"] == 39


def test_design_from_columns_drops_dead_legs():
    X, names = ex.design_from_columns({"a": np.array([1.0, 0.0]), "zero": np.array([0.0, 0.0]),
                                       "nan": np.array([np.nan, np.nan])})
    assert names == ["a"] and X.shape == (2, 1)


def test_ladders_and_pricing():
    rain = {4: np.array([0.5, 1.5, 2.5, 3.5]), 5: np.array([1.0, 1.0, 4.0, 0.2])}
    cols = ex.monthly_no_ladder(rain, 1.0, max_strike=2.0)
    assert set(cols) == {"NO m4 <= 1.00", "NO m4 <= 2.00", "NO m5 <= 1.00", "NO m5 <= 2.00"}
    X, names = ex.design_from_columns(cols)
    w = np.array([1.0, 0.0, 2.0, 0.0])
    pr = ex.hedge_pricing(w, X, half_spread=0.0, fee_rate=0.0)
    assert pr["fair_cost"] == pytest.approx(1.0 * 0.25 + 2.0 * 0.75)
    assert pr["contracts"] == 3.0 and pr["load"] == pytest.approx(1.0) and pr["n_legs"] == 2
    pr2 = ex.hedge_pricing(w, X, half_spread=0.02, fee_rate=0.07)
    assert pr2["load"] > 1.0 and pr2["spread_cost"] == pytest.approx(0.02 * 3.0)
