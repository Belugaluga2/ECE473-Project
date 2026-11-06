"""Milestone 2, week 4 (Jack): choose the lowest-error / lowest-cost portfolio of rain contracts.

Doc 08 fit hedge weights by non-negative least squares (NNLS). That finds the lowest-error hedge
but ignores what the contracts cost and how many of them can actually be bought. This module adds
both, so the platform can show a farmer the whole trade-off between hedge quality and price.

Problem
-------
Years t = 1..n. The farmer wants a payout y_t (dollars) in year t: a PRF indemnity, a PRF-style
payout on months the farmer picks, or a modeled farm loss. The market offers "legs": a NO
contract on one station-month "Above K inches", paying $1 iff that month's station rain <= K.
X[t, l] is leg l's payoff in year t (0 or 1).

Each leg can be bought in one or more *tranches*. A tranche is a quantity available at one
all-in price: one price level of a live order book, or an unlimited quantity at a model price.
Variables x_j >= 0 are contracts bought in tranche j, with x_j <= capacity_j. The hedge pays
h = X A x, where A maps tranches to legs, and costs c . x, where c_j is the all-in unit cost
(price + taker fee + cost of prepaying the cash until settlement).

    lowest error for a budget:   minimize  mean_t (y_t - h_t)^2   s.t.  c . x <= B,  0 <= x <= cap
    penalized form:              minimize  mean_t (y_t - h_t)^2 + lam * c . x

Both are convex quadratic programs. Sweeping B from 0 to the cost of the unconstrained
lowest-error hedge traces the efficient frontier (the lowest error at each price). With no
capacity limits and lam = 0 the solution is the doc-08 NNLS fit.

The optimizer works per $1 of `scale` (normally the farmer's total protection) so that the
variables are of order one; results are returned in contracts and dollars.

Solver: L-BFGS-B on the penalized form with an analytic gradient (bounds are native to it). The
budget form is solved by bisection on lam: the cost of the penalized solution falls as lam rises.
A tiny default lam (1e-9) breaks ties between tranches of the same leg in favour of the cheaper one.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from agri_hedge.pricing import (DEFAULT_LOCKUP_DAYS, DEFAULT_TBILL_RATE, PRICE_MAX, PRICE_MIN,
                                no_asks_from_yes_bids)

KALSHI_TAKER_RATE = 0.07
TIE_LAMBDA = 1e-9


# ---------------------------------------------------------------------------------------------
# Unit costs and tranches
# ---------------------------------------------------------------------------------------------

def all_in_unit_cost(price, taker: bool = True, rate: float = DEFAULT_TBILL_RATE,
                     days: float = DEFAULT_LOCKUP_DAYS) -> np.ndarray:
    """Cost of one $1 contract bought at `price`: price + taker fee + cost of locking up the cash.

    The fee is Kalshi's 0.07 x P x (1 - P) per contract without the per-order round-up (at most
    one cent per order; `pricing.taker_fee` applies it when a final order is priced). The capital
    cost is simple interest at `rate` for `days` days on price + fee.
    """
    p = np.clip(np.asarray(price, dtype=float), PRICE_MIN, PRICE_MAX)
    fee = KALSHI_TAKER_RATE * p * (1.0 - p) if taker else 0.0
    return (p + fee) * (1.0 + rate * float(days) / 365.0)


@dataclass
class Tranche:
    """A quantity of one leg available at one price."""
    leg: int                 # column of the payoff matrix X
    price: float             # quoted price per contract (dollars, 0-1)
    capacity: float = np.inf # contracts available at this price
    source: str = "model"    # "model" | "book" | ...


def model_tranches(q, half_spread: float = 0.0225, n_legs: int | None = None,
                   capacity: float = np.inf) -> list[Tranche]:
    """One tranche per leg at fair value q (climatological NO probability) plus half the spread.

    The default half spread, 2.25 cents, is half the 4.5-cent median contested spread of doc 05
    (the "central" pricing case of doc 09).
    """
    q = np.asarray(q, dtype=float)
    return [Tranche(i, float(np.clip(qi + half_spread, PRICE_MIN, PRICE_MAX)), capacity, "model")
            for i, qi in enumerate(q[:n_legs] if n_legs else q)]


def book_tranches(leg: int, yes_bids, max_price: float | None = None) -> list[Tranche]:
    """Tranches for one leg from a live order book: every NO ask level, cheapest first.

    `yes_bids` is the order book's YES bid list [(price, size)]; a YES bid at p for s contracts is
    a NO offer at 1 - p for s contracts. Levels above `max_price` are dropped.
    """
    out = []
    for p, s in no_asks_from_yes_bids(yes_bids):
        if max_price is not None and p > max_price + 1e-12:
            continue
        out.append(Tranche(leg, float(p), float(s), "book"))
    return out


# ---------------------------------------------------------------------------------------------
# Solver
# ---------------------------------------------------------------------------------------------

@dataclass
class HedgeSolution:
    contracts: np.ndarray            # per tranche
    leg_contracts: np.ndarray        # per leg (sum over its tranches)
    cost: float                      # all-in dollars
    lam: float
    mse: float                       # in-sample mean squared error, dollars^2
    payout: np.ndarray               # in-sample hedge payout by year, dollars
    tranches: list = field(default_factory=list)

    @property
    def rmse(self) -> float:
        return float(np.sqrt(self.mse))


def _clean(X, y):
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    ok = ~np.isnan(y) & ~np.isnan(X).any(axis=1)
    return X[ok], y[ok]


def _fill_cheapest_first(u: np.ndarray, leg_of: np.ndarray, c: np.ndarray, cap: np.ndarray) -> np.ndarray:
    """Keep each leg's total but buy it from its cheapest tranches first.

    The payout depends only on leg totals, so this never changes the fit and never raises the
    cost; it removes solver slack between tranches of the same leg.
    """
    out = np.zeros_like(u)
    for leg in np.unique(leg_of):
        idx = np.flatnonzero(leg_of == leg)
        need = float(u[idx].sum())
        for j in idx[np.argsort(c[idx], kind="stable")]:
            take = min(need, cap[j])
            out[j] = take
            need -= take
            if need <= 0:
                break
    return out


def solve_penalized(X, y, tranches: list[Tranche], lam: float = 0.0, scale: float | None = None,
                    taker: bool = True, rate: float = DEFAULT_TBILL_RATE,
                    days: float = DEFAULT_LOCKUP_DAYS, x0=None) -> HedgeSolution:
    """Minimize mean((y - X A x)^2) + lam * cost(x) over 0 <= x <= capacity.

    `lam` is in units of (fraction of scale)^2 per (fraction of scale) of cost, i.e. it is applied
    after dividing money by `scale`. lam = 0 gives the lowest-error hedge (with a tie-breaking
    lam of 1e-9 so the cheapest tranche of each leg fills first).
    """
    Xc, yc = _clean(X, y)
    n, p = Xc.shape
    m = len(tranches)
    s = float(scale) if scale else max(float(np.nanmax(np.abs(yc))) if len(yc) else 1.0, 1.0)
    leg_of = np.array([t.leg for t in tranches], dtype=int)
    c = all_in_unit_cost([t.price for t in tranches], taker, rate, days)
    cap = np.array([t.capacity for t in tranches], dtype=float) / s
    M = Xc[:, leg_of] if m else np.zeros((n, 0))
    ys = yc / s
    lam_eff = max(float(lam), TIE_LAMBDA)
    MtM = M.T @ M / n
    Mty = M.T @ ys / n

    def f(u):
        r = ys - M @ u
        return float(r @ r / n + lam_eff * c @ u)

    def g(u):
        return 2.0 * (MtM @ u - Mty) + lam_eff * c

    if m == 0 or n == 0:
        u = np.zeros(m)
    else:
        start = np.zeros(m) if x0 is None else np.minimum(np.asarray(x0, float) / s, cap)
        bounds = [(0.0, None if not np.isfinite(b) else float(b)) for b in cap]
        res = minimize(f, start, jac=g, method="L-BFGS-B", bounds=bounds,
                       options={"maxiter": 5000, "ftol": 1e-15, "gtol": 1e-12})
        u = np.where(res.x < 1e-10, 0.0, res.x)
        u = _fill_cheapest_first(u, leg_of, c, cap)
    x = u * s
    leg_x = np.bincount(leg_of, weights=x, minlength=p) if m else np.zeros(p)
    pay = Xc @ leg_x
    return HedgeSolution(x, leg_x, float(c @ x), float(lam), float(np.mean((yc - pay) ** 2)), pay,
                         list(tranches))


def solve_budget(X, y, tranches: list[Tranche], budget: float, scale: float | None = None,
                 tol: float = 1e-4, **kw) -> HedgeSolution:
    """Lowest-error hedge costing at most `budget` dollars (bisection on the cost penalty)."""
    free = solve_penalized(X, y, tranches, 0.0, scale, **kw)
    if free.cost <= budget * (1 + tol) or budget < 0:
        return free
    if budget <= 0:
        return solve_penalized(X, y, tranches, 1e6, scale, **kw)
    lo, hi = 0.0, 1.0
    sol_hi = solve_penalized(X, y, tranches, hi, scale, **kw)
    while sol_hi.cost > budget and hi < 1e6:
        lo, hi = hi, hi * 4
        sol_hi = solve_penalized(X, y, tranches, hi, scale, **kw)
    best = sol_hi
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        sol = solve_penalized(X, y, tranches, mid, scale, x0=best.contracts, **kw)
        if sol.cost > budget:
            lo = mid
        else:
            hi, best = mid, sol
        if hi - lo < 1e-7 * max(hi, 1e-6) or abs(best.cost - budget) <= tol * max(budget, 1.0):
            break
    return best


def efficient_frontier(X, y, tranches: list[Tranche], n_points: int = 15, scale: float | None = None,
                       q=None, **kw) -> pd.DataFrame:
    """Lowest error at each cost, from $0 to the cost of the unconstrained lowest-error hedge.

    Returns one row per budget with cost, rmse, hedge effectiveness (1 - Var(y - h) / Var(y)),
    the share of the lowest-error hedge's variance reduction achieved, and (if leg probabilities
    `q` are given) the hedge's fair expected payout and its cost per $1 of expected payout.
    """
    Xc, yc = _clean(X, y)
    free = solve_penalized(X, y, tranches, 0.0, scale, **kw)
    rows = []
    vy = float(np.var(yc)) if len(yc) else np.nan
    for b in np.linspace(0.0, free.cost, n_points):
        sol = free if b >= free.cost else solve_budget(X, y, tranches, b, scale, **kw)
        he = 1.0 - float(np.var(yc - sol.payout)) / vy if vy > 0 else np.nan
        row = {"budget": float(b), "cost": sol.cost, "rmse": sol.rmse, "he": he,
               "mean_payout": float(np.mean(sol.payout)), "lam": sol.lam}
        if q is not None:
            ev = float(np.asarray(q, float) @ sol.leg_contracts)
            row["expected_payout_fair"] = ev
            row["cost_per_dollar_expected"] = sol.cost / ev if ev > 0 else np.nan
        rows.append(row)
    df = pd.DataFrame(rows)
    he_max = df["he"].max()
    df["share_of_max_he"] = df["he"] / he_max if he_max and he_max > 0 else np.nan
    return df


def knee_budget(frontier: pd.DataFrame, share: float = 0.9) -> float:
    """Cheapest frontier budget that reaches `share` of the best hedge effectiveness."""
    ok = frontier[frontier["share_of_max_he"] >= share]
    return float(ok["budget"].min()) if len(ok) else float(frontier["budget"].max())


def hedge_effectiveness(y, h) -> float:
    """1 - Var(y - h) / Var(y) on years where both are known."""
    y = np.asarray(y, float)
    h = np.asarray(h, float)
    ok = ~np.isnan(y) & ~np.isnan(h)
    v = np.var(y[ok]) if ok.any() else 0.0
    return float(1 - np.var(y[ok] - h[ok]) / v) if v > 0 else float("nan")


def loyo_payout(X, y, tranches: list[Tranche], budget: float | None = None, scale: float | None = None,
                **kw) -> np.ndarray:
    """Leave-one-year-out hedge payouts: refit without year i (same budget), predict year i.

    Rows with NaN target or payoffs stay NaN. With `budget=None` the lowest-error hedge is fit.
    """
    X = np.asarray(X, float)
    y = np.asarray(y, float)
    ok = ~np.isnan(y) & ~np.isnan(X).any(axis=1)
    out = np.full(len(y), np.nan)
    for i in np.flatnonzero(ok):
        keep = ok.copy()
        keep[i] = False
        if budget is None:
            sol = solve_penalized(X[keep], y[keep], tranches, 0.0, scale, **kw)
        else:
            sol = solve_budget(X[keep], y[keep], tranches, budget, scale, tol=1e-3, **kw)
        out[i] = float(X[i] @ sol.leg_contracts)
    return out
