"""Tests for the Milestone 2 hedge optimizer (synthetic data, no files)."""
import numpy as np
import pytest

from agri_hedge import optimizer as op
from agri_hedge.replicate import fit_ladder


def _toy(n=60, seed=0):
    rng = np.random.default_rng(seed)
    rain1, rain2 = rng.gamma(2.0, 1.5, n), rng.gamma(2.0, 1.5, n)
    strikes = [1.0, 2.0, 3.0, 4.0]
    X = np.column_stack([(r <= k).astype(float) for r in (rain1, rain2) for k in strikes])
    idx = 100 * (rain1 + rain2) / np.mean(rain1 + rain2)
    y = 1000 * np.maximum(0, (90 - idx) / 90)
    q = X.mean(axis=0)
    return X, y, q


def test_unit_cost_adds_fee_and_capital():
    c = op.all_in_unit_cost(0.5, taker=True, rate=0.0, days=0)
    assert c == pytest.approx(0.5 + 0.07 * 0.25)
    assert op.all_in_unit_cost(0.5, taker=False, rate=0.0365, days=100) == pytest.approx(0.5 * 1.01)


def test_lowest_error_matches_nnls():
    X, y, q = _toy()
    sol = op.solve_penalized(X, y, op.model_tranches(q), 0.0, scale=1000)
    nn = fit_ladder(X, y / 1000)
    assert sol.mse == pytest.approx(np.mean((y - X @ nn.weights * 1000) ** 2), rel=1e-6)


def test_budget_is_respected_and_error_rises():
    X, y, q = _toy()
    tr = op.model_tranches(q)
    free = op.solve_penalized(X, y, tr, 0.0, scale=1000)
    half = op.solve_budget(X, y, tr, free.cost / 2, scale=1000)
    assert half.cost <= free.cost / 2 * 1.001
    assert half.mse > free.mse


def test_capacity_is_respected():
    X, y, q = _toy()
    tr = op.model_tranches(q, capacity=5.0)
    sol = op.solve_penalized(X, y, tr, 0.0, scale=1000)
    assert sol.contracts.max() <= 5.0 + 1e-6


def test_cheaper_tranche_fills_first():
    X, y, q = _toy()
    tr = [op.Tranche(j, 0.2, 3.0, "book") for j in range(X.shape[1])] + \
         [op.Tranche(j, 0.6, np.inf, "book") for j in range(X.shape[1])]
    sol = op.solve_penalized(X, y, tr, 0.0, scale=1000)
    m = X.shape[1]
    cheap, dear = sol.contracts[:m], sol.contracts[m:]
    assert np.all((dear < 1e-6) | (cheap > 3.0 - 1e-3))


def test_frontier_monotone():
    X, y, q = _toy()
    fr = op.efficient_frontier(X, y, op.model_tranches(q), n_points=6, scale=1000, q=q)
    assert fr["cost"].is_monotonic_increasing
    assert np.all(np.diff(fr["rmse"]) <= 1e-6)
    assert fr["share_of_max_he"].iloc[-1] == pytest.approx(1.0)
    assert 0 < op.knee_budget(fr, 0.9) <= fr["budget"].max()


def test_book_tranches_from_yes_bids():
    tr = op.book_tranches(2, [(0.30, 10), (0.25, 5), (0.01, 100)], max_price=0.8)
    assert [t.price for t in tr] == pytest.approx([0.70, 0.75])
    assert [t.capacity for t in tr] == [10, 5]
    assert all(t.leg == 2 for t in tr)


def test_loyo_has_no_lookahead():
    X, y, q = _toy(n=30)
    out = op.loyo_payout(X, y, op.model_tranches(q), None, scale=1000)
    assert np.isfinite(out).all()
    assert op.hedge_effectiveness(y, out) < op.hedge_effectiveness(
        y, op.solve_penalized(X, y, op.model_tranches(q), 0.0, 1000).payout)
