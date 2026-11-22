"""Budget, risk-objective, zero-purchase and temporal-boundary checks."""
import json
import importlib.util
from pathlib import Path
import numpy as np
import pytest
from agri_hedge.direct_tail import (cvar, cost, resize, capacities, direct_counts,
                                    fit_candidates, select_candidates, linear_cost)


@pytest.fixture
def cfg():
    return json.loads((Path(__file__).resolve().parents[1]/
                       'data/scenarios/maya_direct_protocol.json').read_text())


def test_cvar_handles_fractional_tail_mass_and_vectorized_pairs():
    assert np.isclose(cvar([0, 1, 2, 3, 4], .5), 3.2)
    assert np.isclose(cvar([0, 1, 2, 3, 4], .8), 4)
    assert np.isclose(cvar([0, 1, 2, 3, 4], 0), 2)
    assert np.allclose(cvar([[0, 1], [0, 3]], .8), [1, 3])
    with pytest.raises(ValueError):
        cvar([1, np.nan])


def test_direct_portfolio_reduces_training_tail_loss_and_obeys_cost_and_depth(cfg):
    X = np.array([[0], [1], [0], [1]], float)
    loss = np.array([0, 100, 0, 100], float)
    n, continuous = direct_counts(X, loss, np.zeros(4), 0, [.2], 30, [100], cfg)
    paid = cost(n, [.2], cfg)
    assert 98 <= n[0] <= 100 and paid <= 30
    assert cvar(np.maximum(loss+paid-X@n, 0)) < cvar(loss)
    assert continuous < cvar(loss)
    small, _ = direct_counts(X, loss, np.zeros(4), 0, [.2], 30, [5], cfg)
    assert small[0] <= 5


def test_direct_optimizer_can_buy_nothing_when_cover_worsens_bad_states(cfg):
    X = np.array([[1], [0], [1], [0]], float)
    loss = np.array([0, 100, 0, 100], float)
    n, _ = direct_counts(X, loss, np.zeros(4), 0, [.2], 30, [100], cfg)
    assert n.tolist() == [0]
    n, _ = direct_counts(X, loss, np.zeros(4), 0, [.2], 30, [0], cfg)
    assert n.tolist() == [0]


def test_fee_rounding_and_price_stress_keep_budget_without_adding_positions(cfg):
    local = dict(cfg, annual_carry_rate=0)
    assert np.isclose(cost([10], [.5], local), 5.18)
    original = np.array([100, 200])
    scaled, factor = resize(original, [.8, .9], 100, cfg, days=180)
    assert 0 <= factor <= 1 and (scaled <= original).all()
    assert np.equal(scaled, np.floor(scaled)).all()
    assert cost(scaled, [.8, .9], cfg, days=180) <= 100+1e-8


def test_saved_depth_rejects_missing_or_overpriced_orders():
    caps = capacities([(1, 1), (2, 2)], {1: '[[0.8, 3], [0.1, 100]]'}, [.1, .1])
    assert caps.tolist() == [3, 0]


def test_changing_nonfitting_years_cannot_change_prices_or_contract_counts(cfg):
    cfg = dict(cfg, minimum_fit_years=5)
    rng = np.random.default_rng(473)
    X = (rng.random((15, 3)) < .4).astype(float)
    I = np.linspace(30, 140, 15)
    y = np.maximum(100-I, 0)
    prf = np.maximum(90-I, 0)
    fit = np.arange(15) < 10
    legs = [(1, 1.), (2, 2.), (3, 3.)]
    a = fit_candidates(X, y, I, prf, 10, fit, 20, legs, {}, 'unlimited', cfg)
    XX, yy, II, PP = X.copy(), y.copy(), I.copy(), prf.copy()
    XX[~fit] = 1-XX[~fit]
    yy[~fit] += 10000
    II[~fit] -= 1000
    PP[~fit] += 3000
    b = fit_candidates(XX, yy, II, PP, 10, fit, 20, legs, {}, 'unlimited', cfg)
    assert list(a) == list(b)
    for name in a:
        assert np.array_equal(a[name]['counts'], b[name]['counts'])
        assert np.array_equal(a[name]['asks'], b[name]['asks'])


def test_validation_selection_cannot_see_evaluation_outcomes(cfg):
    tickets = {'cash': dict(counts=np.array([0]), cost=0),
               'direct_cvar': dict(counts=np.array([20]), cost=5)}
    X = np.array([[0], [1], [0], [1]], float)
    y = np.array([0, 100, 0, 100], float)
    valid = np.array([True, True, False, False])
    chosen, scores = select_candidates(tickets, X, y, np.zeros(4), 0, valid, cfg)
    X[~valid] = 0
    y[~valid] = 10000
    changed, other = select_candidates(tickets, X, y, np.zeros(4), 0, valid, cfg)
    assert chosen == changed == 'direct_cvar' and scores == other


def test_continuous_cvar_reference_matches_analytical_two_state_solution(cfg):
    # At 50% tail mass the objective is max(normal outlay, drought outlay).
    # Equalizing the two gives 100 contracts and CVaR = 100*unit cost.
    local = dict(cfg, cvar_alpha=.5)
    _, optimum = direct_counts([[0], [1]], [0, 100], [0, 0], 0, [.25], 30, [200], local)
    assert np.isclose(optimum, 100*linear_cost([.25], local)[0])


def test_no_extra_purchase_is_needed_when_original_cover_already_eliminates_outlay(cfg):
    n, optimum = direct_counts([[0], [1]], [0, 100], [20, 120], 10, [.25], 30, [200], cfg)
    assert optimum == 0 and n.tolist() == [0]


def test_replay_statistics_charge_extra_premium_once_and_preserve_cash_reference(cfg):
    script = Path(__file__).resolve().parents[1]/'scripts/run_direct_tail.py'
    spec = importlib.util.spec_from_file_location('direct_replay', script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    y = np.arange(10.)*10
    prf = .5*y
    years = np.arange(2001, 2011)
    args = dict(reference_cost=10, years=years, severe=np.zeros(10, bool), cfg=cfg)
    cash = module.summarize(y, prf, prf, total_cost=10, **args)
    assert cash['cvar_improvement'] == cash['mean_net_gain_vs_prf'] == 0
    added = module.summarize(y, prf, prf+.2*y, total_cost=17, **args)
    assert np.isclose(added['mean_net_gain_vs_prf'], .2*y.mean()-7)
    assert np.isclose(added['residual_variance_reduction'], 1-(.3/.5)**2)
