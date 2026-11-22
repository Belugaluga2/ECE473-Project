"""Budget and evaluation helpers for the frozen matched-premium paper experiment.

These routines evaluate rain-index and modeled forage-loss proxies. They do not
assert observed farm-income protection or submit orders.
"""
from __future__ import annotations

import json
import numpy as np


def drought_payoff(index, shape="linear", coverage=0.9):
    i = np.asarray(index, dtype=float)
    s = np.clip(1-i/100, 0, 1)
    if shape == "linear":
        return np.clip((100*coverage-i)/(100*coverage), 0, 1)
    if shape == "exp5":
        return np.expm1(5*s)/np.expm1(5)
    if shape == "digital30":
        return np.where(np.isnan(i),np.nan,(i <= 30).astype(float))
    if shape == "deep50":
        return np.clip((50-i)/50,0,1)
    raise ValueError(shape)


def all_in_cost(counts, asks, annual_rate=0.0405, days=31):
    """Model purchase + rounded retail taker fee + opportunity cost, once each."""
    n, a = np.asarray(counts, float), np.asarray(asks, float)
    fees = np.ceil(100*0.07*n*a*(1-a)-1e-10)/100
    return float((n*a+fees).sum()*(1+annual_rate*days/365))


def budget_ticket(weights, asks, budget):
    """Largest proportional whole-contract ticket below a fixed farmer budget.

    Contract rounding can leave cash unspent. No extra contracts are selected
    after looking at evaluation outcomes.
    """
    w, a = np.asarray(weights, float), np.asarray(asks, float)
    if budget < 0 or np.any(w < 0) or np.any((a <= 0) | (a >= 1)):
        raise ValueError("Invalid weight, price, or budget")
    if not w.any() or budget == 0:
        return np.zeros_like(w, dtype=int), 0.0
    high = 2*budget/float(w@a)+2
    low = 0.0
    for _ in range(60):
        mid = (low+high)/2
        n = np.floor(mid*w+1e-10).astype(int)
        if all_in_cost(n, a) <= budget+1e-9:
            low = mid
        else:
            high = mid
    return np.floor(low*w+1e-10).astype(int), low


def saved_depth_cap(counts, legs, books, fair, tolerance=0.10):
    """Capacity stress only: reuse one saved station ladder at each calendar month.

    The saved books cover November 2026, not a full future/historical season.
    This deliberately named proxy cannot establish historical executable fills.
    Pricing remains the experiment's frozen modeled prices, not a walked quote.
    """
    capped = []
    for want, leg, q in zip(counts, legs, fair):
        strike = float(leg[1])
        if strike not in books:
            capped.append(0)
            continue
        levels = json.loads(books[strike])
        available = sum(float(size) for bid, size in levels if 1-float(bid) <= q+tolerance+1e-10)
        capped.append(min(int(want), int(np.floor(available+1e-10))))
    return np.asarray(capped, dtype=int)


def effectiveness(target, payout):
    y, h = np.asarray(target, float), np.asarray(payout, float)
    v = float(np.var(y))
    return 1-float(np.var(y-h))/v if v > 1e-12 else np.nan


def paired_year_blocks(n, draws=2000, block=2, seed=473):
    """Resample calendar-year blocks; retain paired policy outcomes in each draw."""
    rng = np.random.default_rng(seed)
    starts = rng.integers(n, size=(draws, int(np.ceil(n/block))))
    return ((starts[..., None]+np.arange(block)) % n).reshape(draws, -1)[:, :n]


def summarize(loss, payout, premium, prf_reference, severe):
    y, h = np.asarray(loss, float), np.asarray(payout, float)
    reference = np.asarray(prf_reference, float)
    worst = np.argsort(y)[-min(5, len(y)):]
    residual = np.maximum(y+premium-h, 0)
    return dict(n_years=len(y), premium_spent=float(premium),
                mean_payout=float(h.mean()), payout_per_premium=float(h.mean()/premium) if premium else 0.0,
                loss_proxy_he=effectiveness(y, h), prf_tracking_he=effectiveness(reference,h),
                prf_rmse=float(np.sqrt(np.mean((reference-h)**2))),
                mean_net_loss_proxy=float((y+premium-h).mean()),
                worst5_net_shortfall=float(residual[worst].mean()),
                severe_years=int(np.sum(severe)),
                severe_mean_payout=float(h[severe].mean()) if np.any(severe) else np.nan,
                severe_miss_rate=float(np.mean(h[severe] < 0.1*y[severe])) if np.any(severe) else np.nan)
