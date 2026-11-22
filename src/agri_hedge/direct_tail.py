"""Exploratory, budget-constrained CVaR portfolios; no live prices or orders.

Fit, validation selection and replay are separate operations so evaluation data
cannot choose quantities or hyperparameters. See doc 34 and its frozen protocol.
"""
from __future__ import annotations
import json
import numpy as np
from scipy.optimize import linprog
from agri_hedge.replicate import fit_ladder


def cvar(values, alpha=0.8):
    """Empirical upper-tail mean, including fractional boundary observations."""
    x = np.asarray(values, float)
    if not 0 <= alpha < 1 or x.shape[-1] == 0 or not np.isfinite(x).all():
        raise ValueError('CVaR needs finite observations and 0 <= alpha < 1')
    ordered = np.sort(x, axis=-1)[..., ::-1]
    mass = x.shape[-1] * (1-alpha)
    whole = min(int(np.floor(mass+1e-10)), x.shape[-1])
    fraction = max(0.0, mass-whole)
    total = ordered[..., :whole].sum(axis=-1)
    if whole < x.shape[-1]:
        total = total + fraction*ordered[..., whole]
    return total/mass


def cost(counts, asks, cfg, days=None):
    n, q = np.asarray(counts, float), np.asarray(asks, float)
    if np.any(n < 0) or np.any((q <= 0) | (q >= 1)):
        raise ValueError('Invalid contract count or ask')
    fees = np.ceil(100*cfg['taker_fee_rate']*n*q*(1-q)-1e-10)/100
    carry = 1+cfg['annual_carry_rate']*(days or cfg['central_carry_days'])/365
    return float(np.sum(n*q+fees)*carry)


def linear_cost(asks, cfg):
    q = np.asarray(asks, float)
    return (q+cfg['taker_fee_rate']*q*(1-q))*(
        1+cfg['annual_carry_rate']*cfg['central_carry_days']/365)


def resize(counts, asks, budget, cfg, days=None, expand=False):
    """Proportional integer scaling; stress runs may reduce but never add positions."""
    n = np.asarray(counts, float)
    if not n.any() or budget <= 0:
        return np.zeros(len(n), dtype=int), 0.0
    if not expand and cost(n, asks, cfg, days) <= budget+1e-8:
        return n.astype(int), 1.0
    hi = 2*budget/max(float(n@linear_cost(asks, cfg)), 1e-12)+2 if expand else 1.0
    lo = 0.0
    for _ in range(60):
        mid = (hi+lo)/2
        proposed = np.floor(mid*n+1e-10).astype(int)
        if cost(proposed, asks, cfg, days) <= budget+1e-8:
            lo = mid
        else:
            hi = mid
    return np.floor(lo*n+1e-10).astype(int), lo


def capacities(legs, books, fair, tolerance=0.1):
    """Saved November capacity repeated at each month, at a modeled-price cutoff."""
    result = []
    for (_, strike), q in zip(legs, fair):
        levels = json.loads(books.get(float(strike), '[]'))
        available = sum(float(size) for bid, size in levels
                        if 1-float(bid) <= float(q)+tolerance+1e-10)
        result.append(max(0, int(np.floor(available+1e-10))))
    return np.asarray(result, dtype=int)


def direct_counts(X, loss, base_payout, base_premium, asks, budget, limits, cfg):
    """Continuous CVaR LP, a secondary cost minimization, then integer flooring."""
    X, y, p = np.asarray(X, float), np.asarray(loss, float), np.asarray(base_payout, float)
    q = np.asarray(asks, float)
    N, J = X.shape
    if not (np.isfinite(X).all() and np.isfinite(y).all() and np.isfinite(p).all()):
        raise ValueError('Non-finite fitting data')
    carry = 1+cfg['annual_carry_rate']*cfg['central_carry_days']/365
    rounding_reserve = J*0.01*carry
    if budget <= rounding_reserve:
        return np.zeros(J, dtype=int), float(cvar(np.maximum(y+base_premium-p, 0), cfg['cvar_alpha']))
    unit = linear_cost(q, cfg)
    # Variables: J contract quantities, VaR threshold z >= 0, N tail excesses u >= 0.
    objective = np.r_[np.zeros(J), 1., np.full(N, 1/((1-cfg['cvar_alpha'])*N))]
    A = np.zeros((N+1, J+1+N))
    A[0, :J] = unit
    A[1:, :J] = unit[None, :]-X
    A[1:, J] = -1
    A[1:, J+1:] = -np.eye(N)
    b = np.r_[budget-rounding_reserve, -(y+base_premium-p)]
    bounds = [(0., min(float(cap), budget/float(c))) for cap, c in zip(limits, unit)]
    bounds += [(0., None)]*(N+1)
    first = linprog(objective, A_ub=A, b_ub=b, bounds=bounds, method='highs')
    if not first.success:
        raise RuntimeError(f'CVaR optimization failed: {first.message}')
    second = linprog(np.r_[unit, np.zeros(N+1)],
                     A_ub=np.vstack([A, objective]),
                     b_ub=np.r_[b, first.fun+cfg['selection_tolerance_usd']],
                     bounds=bounds, method='highs')
    if not second.success:
        raise RuntimeError(f'CVaR cost minimization failed: {second.message}')
    counts = np.floor(np.maximum(second.x[:J], 0)+1e-8).astype(int)
    counts = np.minimum(counts, np.floor(limits)).astype(int)
    assert cost(counts, q, cfg) <= budget+1e-6
    return counts, float(first.fun)


def target_curve(index, trigger, power):
    return np.clip((float(trigger)-np.asarray(index, float))/float(trigger), 0, 1)**power


def fit_candidates(X, loss, index, base_payout, base_premium, fit, budget, legs, books, depth, cfg):
    """Use only fitting rows for prices, target weights and direct quantities."""
    X, y, I, P = map(lambda a: np.asarray(a, float), (X, loss, index, base_payout))
    train = np.asarray(fit, bool) & np.isfinite(y) & np.isfinite(I) & np.isfinite(P) & np.isfinite(X).all(axis=1)
    if train.sum() < cfg['minimum_fit_years']:
        raise ValueError('Insufficient complete fitting years')
    Xt, yt, It, Pt = X[train], y[train], I[train], P[train]
    fair = Xt.mean(axis=0)
    asks = np.clip(fair+cfg['central_half_spread'], *cfg['ask_bounds'])
    limits = (capacities(legs, books, fair, cfg['depth_price_tolerance'])
              if depth == 'saved_depth_proxy' else np.full(X.shape[1], 1e12))
    direct, optimum = direct_counts(Xt, yt, Pt, base_premium, asks, budget, limits, cfg)
    tickets = {'cash': dict(counts=np.zeros(X.shape[1], dtype=int)),
               'direct_cvar': dict(counts=direct, continuous_training_cvar=optimum)}
    curves = {f'power_T{T}_p{p}': target_curve(It, T, p)
              for T in cfg['trigger_indexes'] for p in cfg['powers']}
    curves['exp5_T100'] = np.expm1(5*np.clip(1-It/100, 0, 1))/np.expm1(5)
    for name, target in curves.items():
        weights = fit_ladder(Xt, target, ridge=cfg['ridge']).weights
        counts, _ = resize(weights, asks, budget, cfg, expand=True)
        counts = np.minimum(counts, limits).astype(int)
        tickets[name] = dict(counts=counts)
    for name, ticket in tickets.items():
        ticket.update(asks=asks, fair=fair, limits=limits, fit_n=int(train.sum()))
        ticket['cost'] = cost(ticket['counts'], asks, cfg)
        assert ticket['cost'] <= budget+1e-6
        assert (ticket['counts'] <= limits).all()
    return tickets


def select_candidates(tickets, X, loss, base_payout, base_premium, validation, cfg, shapes_only=False):
    """Choose by pre-2001 validation only; return the full validation score table."""
    valid = np.asarray(validation, bool)
    Xv, yv, pv = np.asarray(X)[valid], np.asarray(loss)[valid], np.asarray(base_payout)[valid]
    if not len(yv):
        raise ValueError('No validation observations')
    rows = []
    for order, (name, ticket) in enumerate(tickets.items()):
        if shapes_only and name == 'direct_cvar':
            continue
        residual = np.maximum(yv+base_premium+ticket['cost']-pv-Xv@ticket['counts'], 0)
        rows.append(dict(candidate=name, validation_cvar=float(cvar(residual, cfg['cvar_alpha'])),
                         validation_mean_positive_outlay=float(residual.mean()),
                         market_cost=ticket['cost'], order=order))
    best = min(r['validation_cvar'] for r in rows)
    tied = [r for r in rows if r['validation_cvar'] <= best+cfg['selection_tolerance_usd']]
    winner = min(tied, key=lambda r: (r['validation_mean_positive_outlay'], r['market_cost'], r['order']))
    return winner['candidate'], rows
