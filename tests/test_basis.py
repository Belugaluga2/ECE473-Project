"""Tests for agri_hedge.basis (geographic basis-risk metrics) on small synthetic arrays; no network."""
import numpy as np
import pytest

from agri_hedge.basis import (COOL_INTERVALS, SEASONS, WARM_INTERVALS, anomalies, best_weight, bias,
                              bootstrap_decay_length, exp_decay, finite_pair, fit_exp_decay,
                              index_from_totals, index_metrics, loyo_station_selection,
                              payment_factor, pearson, portfolio_payout, rmse, rowwise_pearson,
                              sd_ratio, spearman, totals_metrics, trigger_table)
from agri_hedge.prf_intervals import INTERVAL_NAMES


# ---------------------------------------------------------------- basic metrics
def test_finite_pair_drops_nan_in_either():
    a, b = finite_pair([1, np.nan, 3, 4], [1, 2, np.inf, 5])
    assert a.tolist() == [1, 4] and b.tolist() == [1, 5]
    with pytest.raises(ValueError):
        finite_pair([1, 2], [1, 2, 3])


def test_pearson_and_spearman():
    x = np.arange(10.0)
    assert pearson(x, 3 * x + 2) == pytest.approx(1.0)
    assert pearson(x, -x) == pytest.approx(-1.0)
    assert np.isnan(pearson(x, np.ones(10)))          # no variance
    assert np.isnan(pearson([1, 2], [1, 2]))           # too few pairs
    y = np.exp(x)                                      # monotone but not linear
    assert pearson(x, y) < 0.9
    assert spearman(x, y) == pytest.approx(1.0)
    # NaNs are dropped pairwise
    assert pearson([1, 2, np.nan, 4, 5], [2, 4, 100, 8, 10]) == pytest.approx(1.0)
    # ties use average ranks: ranks of [1,1,2] are [1.5,1.5,3]
    assert spearman([1, 1, 2], [1, 2, 3]) == pytest.approx(pearson([1.5, 1.5, 3], [1, 2, 3]))


def test_rmse_bias_sd_ratio():
    assert rmse([1, 2, 3], [1, 2, 7]) == pytest.approx(np.sqrt(16 / 3))
    assert bias([3, 5], [1, 1]) == pytest.approx(3.0)
    assert sd_ratio([0, 2, 4], [0, 1, 2]) == pytest.approx(2.0)


def test_anomalies_remove_group_means():
    v = np.array([1.0, 3.0, 10.0, 14.0, np.nan])
    g = np.array(["a", "a", "b", "b", "b"])
    out = anomalies(v, g)
    assert out[:4].tolist() == [-1.0, 1.0, -2.0, 2.0]
    assert np.isnan(out[4])


def test_index_from_totals_uses_base_rows_only():
    tot = [2.0, 4.0, 6.0, 10.0, 20.0]
    grp = ["Jan-Feb", "Jan-Feb", "Jan-Feb", "Feb-Mar", "Feb-Mar"]
    base = [True, True, False, True, False]
    idx = index_from_totals(tot, grp, base)
    # Jan-Feb expected = mean(2, 4) = 3 ; Feb-Mar expected = 10
    assert idx.tolist() == pytest.approx([200 / 3, 400 / 3, 200.0, 100.0, 200.0])
    assert np.isnan(index_from_totals([1.0], ["x"], [False])[0])   # no base data


# ---------------------------------------------------------------- triggers and payouts
def test_trigger_table_counts_and_rates():
    grid = np.array([50, 80, 89.9, 95, 120, 60, 100, 90])
    stat = np.array([40, 95, 85, 85, 130, 70, 110, 50])
    t = trigger_table(grid, stat, 90.0)
    # grid triggers (< 90): 50, 80, 89.9, 60 (90 itself is NOT below the trigger)
    # station triggers: 40, 85, 85, 70, 50
    assert (t["both"], t["grid_only"], t["station_only"], t["neither"]) == (3, 1, 2, 2)
    assert t["n"] == 8
    assert t["hit_rate"] == pytest.approx(3 / 4)
    assert t["miss_rate"] == pytest.approx(1 / 4)
    assert t["false_alarm"] == pytest.approx(2 / 5)
    assert t["agreement"] == pytest.approx(5 / 8)
    assert t["p_grid"] == pytest.approx(4 / 8) and t["p_station"] == pytest.approx(5 / 8)
    assert t["miss_if_independent"] == pytest.approx(3 / 8)
    phi = (3 * 2 - 1 * 2) / np.sqrt(4 * 4 * 5 * 3)
    assert t["phi"] == pytest.approx(phi)
    # phi equals the Pearson correlation of the 0/1 indicators
    assert t["phi"] == pytest.approx(pearson(grid < 90, stat < 90))


def test_trigger_table_edge_cases():
    t = trigger_table([100, 120], [50, 60], 90.0)    # grid never triggers
    assert np.isnan(t["hit_rate"]) and np.isnan(t["miss_rate"]) and np.isnan(t["phi"])
    t = trigger_table([50, np.nan], [40, 30], 70.0)  # NaN pair dropped
    assert t["n"] == 1 and t["both"] == 1


def test_payment_factor_and_portfolio():
    pf = payment_factor([45, 90, 120, np.nan], 90.0)
    assert pf[:3].tolist() == pytest.approx([0.5, 0.0, 0.0])
    assert np.isnan(pf[3])
    assert payment_factor([35.0], 70.0)[0] == pytest.approx(0.5)
    out = portfolio_payout([1.0, 0.0], [0.0, 1.0], 0.25)
    assert out.tolist() == pytest.approx([0.25, 0.75])


def test_best_weight_finds_the_right_mix():
    rng = np.random.default_rng(1)
    a, b = rng.random(200), rng.random(200)
    w, r = best_weight(a, a, b)
    assert w == 1.0 and r == pytest.approx(1.0)
    w, r = best_weight(0.3 * a + 0.7 * b, a, b)
    assert w == pytest.approx(0.3) and r == pytest.approx(1.0)


# ---------------------------------------------------------------- composite metrics
def test_index_metrics_keys_and_seasons():
    names = np.array(INTERVAL_NAMES * 20)
    rng = np.random.default_rng(2)
    grid = rng.gamma(4, 25, names.size)
    station = grid.copy()
    warm = np.isin(names, WARM_INTERVALS)
    station[warm] = rng.gamma(4, 25, warm.sum())          # warm season unrelated
    m = index_metrics(station, grid, names)
    assert m["r_index_cool"] == pytest.approx(1.0)
    assert abs(m["r_index_warm"]) < 0.4
    assert m["miss_rate90_cool"] == 0.0
    for k in ("n_index", "r_index", "rho_index", "rmse_index", "bias_index", "sd_ratio_index",
              "r_payout90", "hit_rate90", "miss_rate90", "false_alarm90", "phi90", "both70",
              "grid_only70", "station_only70", "neither70"):
        assert k in m
    assert m["both90"] + m["grid_only90"] + m["station_only90"] + m["neither90"] == m["n_index"]
    assert set(SEASONS["cool"]) == set(COOL_INTERVALS)
    assert not set(WARM_INTERVALS) & set(COOL_INTERVALS)


def test_totals_metrics_anomaly_removes_shared_seasonal_cycle():
    months = np.tile(np.arange(1, 13), 30)
    cycle = 50 * np.sin(2 * np.pi * months / 12) + 100
    rng = np.random.default_rng(3)
    s = cycle + rng.normal(0, 5, months.size)
    g = cycle + rng.normal(0, 5, months.size)          # independent noise around the same cycle
    m = totals_metrics(s, g, months, "month")
    assert m["r_month"] > 0.9                            # inflated by the shared cycle
    assert abs(m["r_month_anom"]) < 0.2                  # anomalies are unrelated
    assert m["n_month"] == months.size


# ---------------------------------------------------------------- distance decay
def test_fit_exp_decay_recovers_parameters():
    d = np.linspace(0, 150, 60)
    r = exp_decay(d, 0.9, 150.0)
    f = fit_exp_decay(d, r)
    assert f["c0"] == pytest.approx(0.9, abs=1e-4)
    assert f["L"] == pytest.approx(150.0, rel=1e-3)
    assert f["rmse"] < 1e-6
    assert np.isnan(fit_exp_decay([1, 2], [0.9, 0.8])["L"])   # too few points


def test_rowwise_pearson_matches_scalar():
    rng = np.random.default_rng(4)
    m = rng.normal(size=(5, 40))
    v = rng.normal(size=40)
    got = rowwise_pearson(m, v)
    assert got == pytest.approx([pearson(row, v) for row in m])


def test_bootstrap_decay_length_is_reproducible():
    rng = np.random.default_rng(5)
    years = np.repeat(np.arange(30), 11)
    station = rng.normal(size=years.size)
    dist = np.linspace(5, 150, 25)
    rho = exp_decay(dist, 0.95, 120.0)
    noise = rng.normal(size=(dist.size, years.size))
    grids = rho[:, None] * station[None, :] + np.sqrt(1 - rho[:, None] ** 2) * noise
    a = bootstrap_decay_length(grids, station, dist, years, n_boot=20, seed=7)
    b = bootstrap_decay_length(grids, station, dist, years, n_boot=20, seed=7)
    assert np.allclose(a, b, equal_nan=True)
    assert np.isfinite(a).all()
    assert 60 < np.median(a) < 240


# ---------------------------------------------------------------- station selection
def test_loyo_station_selection_prefers_the_informative_station():
    rng = np.random.default_rng(6)
    years = np.repeat(np.arange(25), 11)
    target = rng.random(years.size)
    payouts = {"NEAR": target + rng.normal(0, 0.1, years.size),
               "FAR": rng.random(years.size)}
    cv = loyo_station_selection(target, payouts, years, paired="NEAR")
    assert cv["chosen_single_mode"] == "NEAR" and cv["chosen_single_share"] == 1.0
    assert cv["oos_r_best_single"] == pytest.approx(cv["oos_r_paired"])
    assert cv["oos_r_paired"] > 0.9
    assert cv["oos_r_best_pair"] > 0.85
    assert cv["chosen_pair_mode"].startswith("NEAR+FAR@") or cv["chosen_pair_mode"].startswith("FAR+NEAR@")
    one = loyo_station_selection(target, {"NEAR": payouts["NEAR"]}, years, paired="NEAR")
    assert np.isnan(one["oos_r_best_pair"])
