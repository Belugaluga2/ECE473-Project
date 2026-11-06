"""Row-crop (corn/soybean) rain exposure and simple Kalshi monthly-rain hedges (Milestone 2 exploration).

PRF does not insure row crops, so this module does not copy an insurance payout. It hedges a
farm's *rain-driven revenue loss* instead, measured two ways:

1. **Modeled loss.** The verified state yield models of doc 03a give yield as a quadratic in a
   month's statewide rain, Y = b1 P + b2 P^2 (temperature held fixed). The yield change in a year
   relative to a normal month is b1 (P - P0) + b2 (P^2 - P0^2). Station rain is mapped onto the
   state scale by its anomaly (P = P0_state + R_station - normal_station), so a normal station month
   means zero change, and is clipped to the range of statewide rain the model was fit on, so the
   quadratic is not extrapolated. Loss = max(0, -change) x price.
2. **Observed loss.** The county's NASS yield minus a linear trend, x price, floored at zero. This
   includes every peril (heat, wind, disease, wet springs), not only rain at one gauge.

Hedges are long-only portfolios of Kalshi "Above X inches" contracts on one station-month. A NO pays
$1 iff the monthly total is <= X (drought side); a YES pays $1 iff the total is > X (excess-rain
side). Weights come from the same non-negative least squares used for PRF replication
(`agri_hedge.replicate.fit_ladder`), with a free cash term so that no contract is bought only to
stand in for cash. Hedge effectiveness (HE) = 1 - Var(loss - payout) / Var(loss): the share of the
variance of rain-driven revenue that the hedge removes.

Everything here is pure arithmetic on numpy/pandas objects; data loading and the study loop live in
`scripts/run_rowcrop_exploration.py`. Units: rain in inches, yields in bu/acre, money in US dollars,
contracts are $1-notional.
"""
from __future__ import annotations

from typing import Mapping, Sequence

import numpy as np
import pandas as pd

from agri_hedge.locations import haversine_miles
from agri_hedge.pricing import walk_no_book
from agri_hedge.replicate import fit_ladder, no_payoff

SIDES = ("no", "yes")


# ---------------------------------------------------------------------------------------------
# Yield response
# ---------------------------------------------------------------------------------------------

def state_equivalent_rain(station_rain, station_normal: float, state_normal: float,
                          clip: tuple[float, float] | None = None) -> np.ndarray:
    """Map station monthly rain onto a statewide-rain scale by its anomaly from the station normal.

    P = state_normal + (station_rain - station_normal), optionally clipped to `clip` = (lo, hi).
    NaN stays NaN.
    """
    p = float(state_normal) + (np.asarray(station_rain, dtype=float) - float(station_normal))
    if clip is not None:
        p = np.where(np.isnan(p), np.nan, np.clip(p, clip[0], clip[1]))
    return p


def quadratic_yield_change(rain, b1: float, b2: float, p0: float) -> np.ndarray:
    """Yield change from moving a month's rain from `p0` to `rain` under Y = b1 P + b2 P^2.

    b2 = 0 gives a linear term. Units follow the coefficients (bu/acre per inch).
    """
    r = np.asarray(rain, dtype=float)
    return float(b1) * (r - p0) + float(b2) * (r ** 2 - float(p0) ** 2)


def revenue_loss(yield_change, price: float) -> np.ndarray:
    """Revenue loss per acre: max(0, -yield change) x price. NaN stays NaN."""
    dy = np.asarray(yield_change, dtype=float)
    return np.where(np.isnan(dy), np.nan, np.maximum(0.0, -dy) * float(price))


def linear_trend(years, values, fit_window: tuple[int, int] | None = None) -> np.ndarray:
    """Fitted values of an OLS linear time trend, fit on `fit_window` (inclusive) and evaluated at every year.

    NaN values are ignored in the fit. Raises ValueError with fewer than 3 usable points.
    """
    y = np.asarray(years, dtype=float)
    v = np.asarray(values, dtype=float)
    ok = ~np.isnan(v)
    if fit_window is not None:
        ok &= (y >= fit_window[0]) & (y <= fit_window[1])
    if ok.sum() < 3:
        raise ValueError("need at least 3 non-missing points to fit a trend")
    slope, icpt = np.polyfit(y[ok], v[ok], 1)
    return icpt + slope * y


def trend_shortfall(years, values, fit_window: tuple[int, int] | None = None) -> pd.DataFrame:
    """Trend, deviation (actual - trend) and shortfall (max(0, trend - actual)) for a yield series."""
    tr = linear_trend(years, values, fit_window)
    v = np.asarray(values, dtype=float)
    dev = v - tr
    return pd.DataFrame({"year": np.asarray(years), "actual": v, "trend": tr, "deviation": dev,
                         "shortfall": np.where(np.isnan(dev), np.nan, np.maximum(0.0, -dev))})


# ---------------------------------------------------------------------------------------------
# Contracts and hedges
# ---------------------------------------------------------------------------------------------

def yes_payoff(rain, strike: float) -> np.ndarray:
    """Payoff of one $1 YES on "Above `strike` inches": 1 if rain > strike, else 0 (NaN stays NaN)."""
    n = no_payoff(rain, strike)
    return np.where(np.isnan(n), np.nan, 1.0 - n)


def payoff(rain, strike: float, side: str) -> np.ndarray:
    """NO or YES payoff by `side` ("no" = drought, "yes" = excess rain)."""
    if side == "no":
        return no_payoff(rain, strike)
    if side == "yes":
        return yes_payoff(rain, strike)
    raise ValueError(f"side must be 'no' or 'yes', got {side!r}")


def side_strikes(strikes_by_month: Mapping[int, Sequence[float]], normals: Mapping[int, float]
                 ) -> dict[str, dict[int, tuple[float, ...]]]:
    """Split each month's listed strikes into a drought set and an excess-rain set.

    Drought side (NO) keeps strikes at or below the month's normal rounded to the nearest inch;
    excess side (YES) keeps strikes at or above it. A NO far above normal ("not a very wet month")
    is economically a short excess-rain position, and NO and YES on the same strike add up to
    cash, so this split keeps each side's contracts doing what the side is meant to do.
    """
    out = {"no": {}, "yes": {}}
    for m, ks in strikes_by_month.items():
        if m not in normals:
            continue
        c = float(np.round(normals[m]))
        out["no"][m] = tuple(float(k) for k in ks if k <= c)
        out["yes"][m] = tuple(float(k) for k in ks if k >= c)
    return out


def binary_design(rain_by_month: Mapping[int, np.ndarray], strikes_by_month: Mapping,
                  sides: Sequence[str]) -> tuple[np.ndarray, list[tuple[int, float, str]]]:
    """Design matrix of contract payoffs: one column per (month, strike, side).

    rain_by_month maps calendar month -> station monthly totals, one per year, aligned across
    months. strikes_by_month is either {month: strikes} (same strikes for every side) or
    {side: {month: strikes}} (e.g. from `side_strikes`). Returns (X of shape n_years x n_legs,
    list of (month, strike, side)).
    """
    cols, legs = [], []
    n = len(next(iter(rain_by_month.values())))
    per_side = all(s in strikes_by_month for s in sides) and not any(isinstance(k, (int, np.integer))
                                                                     for k in strikes_by_month)
    for mon, rain in rain_by_month.items():
        for side in sides:
            ks = strikes_by_month[side][mon] if per_side else strikes_by_month[mon]
            for k in ks:
                cols.append(payoff(rain, float(k), side))
                legs.append((int(mon), float(k), side))
    X = np.column_stack(cols) if cols else np.empty((n, 0))
    return X, legs


def hedge_effectiveness(loss, payout) -> float:
    """1 - Var(loss - payout) / Var(loss) over years where both are known (population variances).

    1 = the hedge removes all variance of the loss; 0 = no better than holding nothing; negative =
    the hedge adds variance. NaN if the loss does not vary.
    """
    lo = np.asarray(loss, dtype=float)
    h = np.asarray(payout, dtype=float)
    ok = ~(np.isnan(lo) | np.isnan(h))
    lo, h = lo[ok], h[ok]
    v = np.var(lo)
    return float(1.0 - np.var(lo - h) / v) if len(lo) > 1 and v > 0 else float("nan")


def tail_recovery(loss, payout, top_k: int = 5) -> float:
    """Share of the summed loss in the `top_k` worst-loss years that the hedge paid back in those years.

    Uses min(payout, loss) per year so overpayment in one bad year does not offset a miss in another.
    """
    lo = np.asarray(loss, dtype=float)
    h = np.asarray(payout, dtype=float)
    ok = ~(np.isnan(lo) | np.isnan(h))
    lo, h = lo[ok], h[ok]
    if len(lo) == 0:
        return float("nan")
    idx = np.argsort(-lo)[:top_k]
    tot = lo[idx].sum()
    return float(np.minimum(h[idx], lo[idx]).sum() / tot) if tot > 0 else float("nan")


def fit_loss_hedge(X: np.ndarray, loss, legs: list | None = None, loyo: bool = True) -> dict:
    """Fit long-only contract counts to a yearly loss and score them in and out of sample.

    Uses `replicate.fit_ladder` with a free cash term (`fit_intercept=True`): the cash term shifts
    the payout by a constant, does not change its variance and is not bought. Rows with NaN in X or
    the loss are dropped. Returns {"weights", "intercept", "legs", "payout" (in-sample, contracts
    only, NaN where X is NaN), "loyo_payout" (leave-one-year-out, contracts only), "loyo_net_payout"
    (that payout minus the refit's mean training-year payout), "he_in",
    "he_loyo", "corr_in", "tail_in", "tail_loyo", "n_years"}.
    """
    X = np.asarray(X, dtype=float)
    lo = np.asarray(loss, dtype=float)
    legs = list(legs or [])
    ok = ~(np.isnan(lo) | np.isnan(X).any(axis=1))
    w, icpt = _fit_varying(X, lo, ok)
    w = net_complements(w, legs)
    pay = X @ w
    out = {"weights": w, "intercept": icpt, "legs": legs, "payout": pay}
    out["n_years"] = int(ok.sum())
    out["he_in"] = hedge_effectiveness(lo, pay)
    out["corr_in"] = (float(np.corrcoef(lo[ok], pay[ok])[0, 1])
                      if ok.sum() > 2 and np.std(pay[ok]) > 0 and np.std(lo[ok]) > 0 else float("nan"))
    out["tail_in"] = tail_recovery(lo, pay)
    if loyo:
        # Leave-one-year-out: refit without year i and record the contracts-only payout in year i
        # (the refit's cash term is not bought). HE out of sample is scored on the *net* payout,
        # payout minus that refit's mean payout over its training years (its fair premium), so a
        # refit that happens to hold more cash-like contracts is not scored as variance.
        loyo_pay = np.full(len(lo), np.nan)
        loyo_net = np.full(len(lo), np.nan)
        for i in np.flatnonzero(ok):
            keep = ok.copy()
            keep[i] = False
            wi, _ = _fit_varying(X, lo, keep)
            wi = net_complements(wi, legs)
            loyo_pay[i] = float(X[i] @ wi)
            loyo_net[i] = loyo_pay[i] - float(np.mean(X[keep] @ wi))
        out["loyo_payout"] = loyo_pay
        out["loyo_net_payout"] = loyo_net
        out["he_loyo"] = hedge_effectiveness(lo, loyo_net)
        out["tail_loyo"] = tail_recovery(lo, loyo_pay)
    return out


def net_complements(weights, legs: list) -> np.ndarray:
    """Cancel NO/YES pairs on the same month and strike: NO + YES on one strike always pays $1 (cash).

    For every (month, strike) held on both sides, min(w_no, w_yes) is removed from both, which
    leaves the payout unchanged up to a constant and avoids buying cash through the exchange.
    `legs` are (month, strike, side) tuples aligned with `weights`; without legs nothing changes.
    """
    w = np.asarray(weights, dtype=float).copy()
    if not legs:
        return w
    pos = {(m, k, s): j for j, (m, k, s) in enumerate(legs)}
    for (m, k, s), j in pos.items():
        if s == "no" and (m, k, "yes") in pos:
            jy = pos[(m, k, "yes")]
            c = min(w[j], w[jy])
            w[j] -= c
            w[jy] -= c
    return w


def _fit_varying(X: np.ndarray, loss: np.ndarray, rows: np.ndarray) -> tuple[np.ndarray, float]:
    """NNLS weights (with free cash term) on the `rows` subset, using only columns that vary there.

    A column that pays the same in every fitted year is indistinguishable from cash, so NNLS could
    put weight on it arbitrarily; such contracts would be bought for nothing, so they get weight 0.
    """
    w = np.zeros(X.shape[1])
    Xs, ys = X[rows], loss[rows]
    if len(ys) == 0:
        return w, 0.0
    vary = np.ptp(Xs, axis=0) > 0 if Xs.shape[1] else np.zeros(0, dtype=bool)
    fit = fit_ladder(Xs[:, vary], ys, fit_intercept=True)
    w[vary] = fit.weights
    return w, fit.intercept


def best_single_strike(X: np.ndarray, loss, legs: list) -> dict:
    """Best one-contract-type hedge: fit each column alone and keep the highest leave-one-year-out HE."""
    best = {"he_loyo": -np.inf}
    for j, leg in enumerate(legs):
        col = X[:, [j]]
        if np.nanstd(col) == 0:
            continue
        r = fit_loss_hedge(col, loss, [leg])
        if np.isfinite(r["he_loyo"]) and r["he_loyo"] > best["he_loyo"]:
            best = {**r, "leg": leg}
    return best if "leg" in best else {"he_loyo": float("nan"), "leg": None}


def legs_frame(legs: list, weights, scale: float = 1.0) -> pd.DataFrame:
    """Non-zero legs as a DataFrame (contract_month, strike_in, side, contracts = weight x scale)."""
    w = np.asarray(weights, dtype=float) * float(scale)
    rows = [{"contract_month": m, "strike_in": k, "side": s, "contracts": c}
            for (m, k, s), c in zip(legs, w) if c > 1e-9]
    return pd.DataFrame(rows, columns=["contract_month", "strike_in", "side", "contracts"])


def leg_win_probability(rain: pd.DataFrame, month: int, strike: float, side: str,
                        window: tuple[int, int]) -> float:
    """Share of complete months in `window` where the leg pays (rain <= strike for NO, > strike for YES).

    `rain` is a year x month table (`pricing.rain_wide`).
    """
    col = rain.loc[(rain.index >= window[0]) & (rain.index <= window[1]), int(month)].to_numpy(float)
    p = payoff(col, strike, side)
    p = p[~np.isnan(p)]
    return float(p.mean()) if len(p) else float("nan")


# ---------------------------------------------------------------------------------------------
# Order books
# ---------------------------------------------------------------------------------------------

def walk_book(book: Mapping[str, Sequence], side: str, contracts: float | None = None,
              max_price: float | None = None) -> dict:
    """Buy `side` contracts against a parsed order book {"yes_bids": [...], "no_bids": [...]}.

    A resting YES bid at p is a NO offer at 1 - p, and a resting NO bid at p is a YES offer at
    1 - p, so buying NO walks the YES bids and buying YES walks the NO bids
    (`pricing.walk_no_book` does the walk and charges the taker fee per level).
    """
    if side == "no":
        return walk_no_book(book.get("yes_bids", []), contracts, max_price)
    if side == "yes":
        return walk_no_book(book.get("no_bids", []), contracts, max_price)
    raise ValueError(f"side must be 'no' or 'yes', got {side!r}")


# ---------------------------------------------------------------------------------------------
# Station coverage of crop areas
# ---------------------------------------------------------------------------------------------

def nearest_station(lat, lon, stations: pd.DataFrame) -> pd.DataFrame:
    """Nearest station (columns station_key, lat, lon) and its great-circle distance in miles for each point."""
    lat = np.asarray(lat, dtype=float)
    lon = np.asarray(lon, dtype=float)
    keys = stations["station_key"].to_numpy()
    slat = stations["lat"].to_numpy(float)
    slon = stations["lon"].to_numpy(float)
    best_d = np.full(len(lat), np.inf)
    best_k = np.empty(len(lat), dtype=object)
    for k, a, b in zip(keys, slat, slon):
        d = np.array([haversine_miles(x, y, a, b) for x, y in zip(lat, lon)])
        better = d < best_d
        best_d[better] = d[better]
        best_k[better] = k
    return pd.DataFrame({"nearest_station": best_k, "distance_mi": best_d})


def share_within(distance, weight, radii: Sequence[float]) -> dict:
    """Weighted share of points within each radius (miles): {radius: share}."""
    d = np.asarray(distance, dtype=float)
    w = np.asarray(weight, dtype=float)
    tot = np.nansum(w)
    return {float(r): float(np.nansum(w[d <= r]) / tot) if tot > 0 else float("nan") for r in radii}
