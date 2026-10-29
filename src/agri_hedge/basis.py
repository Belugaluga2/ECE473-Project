"""Geographic basis risk between Kalshi settlement stations and PRF grids (workstream A1).

A Kalshi monthly-rain contract settles on ONE airport rain gauge. A PRF policy pays on the
0.25-degree grid index of the farm's grid. "Basis risk" is everything that makes the two
disagree. This module holds the small, pure (no I/O, no network) building blocks used by
scripts/run_basis_risk.py and by later milestones:

* agreement metrics for two aligned series: Pearson / Spearman correlation, RMSE, bias,
  anomalies against a series' own climatology;
* the "station index": a station's interval total divided by its own mean for that interval
  over a base period, times 100 (the PRF index formula applied to the gauge);
* trigger agreement: the 2 x 2 table of (grid index < trigger) vs (station index < trigger),
  hit rate P(station triggers | grid triggers), miss rate, false-alarm share and phi;
* PRF-style payment factors and two-station hedge portfolios;
* the exponential distance-decay model corr(d) = c0 * exp(-d / L) and its fit.

Conventions
-----------
* Index values are on the PRF scale (100 = normal). A coverage level c pays when the grid index
  is strictly below the trigger 100 * c (e.g. index < 90 at 90% coverage).
* "Grid" is always the exposure (what PRF pays on) and "station" the hedge instrument (what
  Kalshi settles on). So a *miss* is a grid trigger without a station trigger (the PRF-style
  loss is not covered by the Kalshi hedge) and a *false alarm* is a station trigger without a
  grid trigger (the hedge pays when PRF would not).
* All functions drop pairs where either value is NaN.
"""
from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd
from scipy import optimize, stats

from agri_hedge.prf_intervals import INTERVAL_NAMES

# Season split used for the distance-decay comparison. Warm = convective season (both months in
# May-Sep); cool = frontal / winter season (both months in Oct-Mar). The three transition
# intervals (Mar-Apr, Apr-May, Sep-Oct) are only in "all".
WARM_INTERVALS = ("May-Jun", "Jun-Jul", "Jul-Aug", "Aug-Sep")
COOL_INTERVALS = ("Oct-Nov", "Nov-Dec", "Jan-Feb", "Feb-Mar")
SEASONS = {"all": tuple(INTERVAL_NAMES), "warm": WARM_INTERVALS, "cool": COOL_INTERVALS}
TRIGGERS = (90.0, 70.0)
WEIGHT_GRID = tuple(float(w) for w in np.round(np.linspace(0.0, 1.0, 21), 2))


# =================================================================================================
# Basic agreement metrics
# =================================================================================================
def finite_pair(x, y) -> tuple[np.ndarray, np.ndarray]:
    """Return float arrays of x and y restricted to positions where both are finite."""
    a = np.asarray(x, dtype=float).ravel()
    b = np.asarray(y, dtype=float).ravel()
    if a.shape != b.shape:
        raise ValueError(f"shape mismatch {a.shape} vs {b.shape}")
    ok = np.isfinite(a) & np.isfinite(b)
    return a[ok], b[ok]


def pearson(x, y, min_n: int = 3) -> float:
    """Pearson correlation over pairwise-finite values; NaN if fewer than min_n pairs or no variance."""
    a, b = finite_pair(x, y)
    if a.size < min_n:
        return float("nan")
    a = a - a.mean()
    b = b - b.mean()
    den = np.sqrt((a * a).sum() * (b * b).sum())
    return float((a * b).sum() / den) if den > 0 else float("nan")


def spearman(x, y, min_n: int = 3) -> float:
    """Spearman rank correlation (Pearson on average ranks, so ties are handled)."""
    a, b = finite_pair(x, y)
    if a.size < min_n:
        return float("nan")
    return pearson(stats.rankdata(a), stats.rankdata(b), min_n=min_n)


def rmse(x, y) -> float:
    """Root-mean-square difference sqrt(mean((x - y)^2)) over pairwise-finite values."""
    a, b = finite_pair(x, y)
    return float(np.sqrt(np.mean((a - b) ** 2))) if a.size else float("nan")


def bias(x, y) -> float:
    """Mean difference mean(x - y) over pairwise-finite values."""
    a, b = finite_pair(x, y)
    return float(np.mean(a - b)) if a.size else float("nan")


def sd_ratio(x, y) -> float:
    """Standard deviation of x divided by that of y (pairwise-finite values, ddof=1)."""
    a, b = finite_pair(x, y)
    if a.size < 2 or np.std(b, ddof=1) == 0:
        return float("nan")
    return float(np.std(a, ddof=1) / np.std(b, ddof=1))


def _group_means(values: np.ndarray, groups, mask: np.ndarray) -> np.ndarray:
    """Mean of values[mask] within each group, broadcast back to every row (NaN if a group has none)."""
    _, inv = np.unique(np.asarray(groups), return_inverse=True)
    inv = inv.ravel()
    k = int(inv.max()) + 1 if inv.size else 0
    ok = mask & np.isfinite(values)
    sums = np.bincount(inv[ok], weights=values[ok], minlength=k)
    cnt = np.bincount(inv[ok], minlength=k)
    with np.errstate(invalid="ignore", divide="ignore"):
        means = np.where(cnt > 0, sums / np.maximum(cnt, 1), np.nan)
    return means[inv]


def anomalies(values, groups) -> np.ndarray:
    """values minus the mean of their group (e.g. calendar month or PRF interval).

    This removes a series' own seasonal cycle ("climatology") so that a correlation measures
    whether wet and dry spells line up, not merely that both series are wet in May.
    NaN values are ignored when computing the group means and stay NaN.
    """
    v = np.asarray(values, dtype=float).ravel()
    return v - _group_means(v, groups, np.ones(v.shape, dtype=bool))


def index_from_totals(totals, groups, base_mask) -> np.ndarray:
    """PRF-style index: 100 x total / (mean total of the same group over the base rows).

    totals: interval totals (any unit); groups: interval name (or any key) per row;
    base_mask: boolean per row, True for rows inside the base period. Groups with no base data
    get NaN. This is the formula RMA applies to grids (FCIC-18150 sec. 33D) applied to any series.
    """
    t = np.asarray(totals, dtype=float).ravel()
    expected = _group_means(t, groups, np.asarray(base_mask, dtype=bool).ravel())
    with np.errstate(invalid="ignore", divide="ignore"):
        return 100.0 * t / expected


# =================================================================================================
# Trigger agreement and payouts
# =================================================================================================
def trigger_table(grid_index, station_index, trigger: float = 90.0) -> dict:
    """2 x 2 trigger confusion table of grid (exposure) vs station (hedge) at one trigger.

    Returns counts n, both, grid_only (misses), station_only (false alarms), neither, and the
    rates:
      p_grid      = P(grid index < trigger)
      p_station   = P(station index < trigger)
      hit_rate    = P(station triggers | grid triggers)
      miss_rate   = P(station does not trigger | grid triggers) = 1 - hit_rate
      false_alarm = P(grid does not trigger | station triggers)
      agreement   = share of cases where both agree (both or neither)
      phi         = Pearson correlation of the two 0/1 trigger indicators
      miss_if_independent = 1 - p_station, the miss rate of a hedge unrelated to the grid
    """
    g, s = finite_pair(grid_index, station_index)
    gt = g < trigger
    st = s < trigger
    both = int(np.sum(gt & st))
    grid_only = int(np.sum(gt & ~st))
    station_only = int(np.sum(~gt & st))
    neither = int(np.sum(~gt & ~st))
    n = both + grid_only + station_only + neither
    nan = float("nan")
    n_g = both + grid_only
    n_s = both + station_only
    out = {"n": n, "both": both, "grid_only": grid_only, "station_only": station_only,
           "neither": neither,
           "p_grid": n_g / n if n else nan, "p_station": n_s / n if n else nan,
           "hit_rate": both / n_g if n_g else nan,
           "miss_rate": grid_only / n_g if n_g else nan,
           "false_alarm": station_only / n_s if n_s else nan,
           "agreement": (both + neither) / n if n else nan}
    den = np.sqrt(float(n_g) * (n - n_g) * n_s * (n - n_s))
    out["phi"] = float((both * neither - grid_only * station_only) / den) if den > 0 else nan
    out["miss_if_independent"] = 1.0 - out["p_station"] if n else nan
    return out


def payment_factor(index, trigger: float = 90.0) -> np.ndarray:
    """PRF payment calculation factor max(0, (trigger - index) / trigger), unrounded."""
    x = np.asarray(index, dtype=float)
    with np.errstate(invalid="ignore"):
        return np.where(np.isfinite(x), np.clip((trigger - x) / trigger, 0.0, None), np.nan)


def portfolio_payout(pf_a, pf_b, weight_a: float) -> np.ndarray:
    """Payout of a two-station hedge: weight_a x payout(A) + (1 - weight_a) x payout(B).

    Kalshi lists each city separately, so a two-station hedge can only mix the two cities'
    payouts; it cannot pay on the average of their rainfall.
    """
    return weight_a * np.asarray(pf_a, dtype=float) + (1.0 - weight_a) * np.asarray(pf_b, dtype=float)


def best_weight(target, pf_a, pf_b, weights: Sequence[float] = WEIGHT_GRID) -> tuple[float, float]:
    """Weight on A (from a grid of weights) that maximises corr(target, portfolio payout).

    Returns (weight_a, correlation). Ties go to the first weight in the grid.
    """
    best_w, best_r = float("nan"), -np.inf
    for w in weights:
        r = pearson(target, portfolio_payout(pf_a, pf_b, w))
        if np.isfinite(r) and r > best_r:
            best_w, best_r = float(w), r
    return best_w, (float(best_r) if np.isfinite(best_r) else float("nan"))


# =================================================================================================
# All metrics for one station-grid pair
# =================================================================================================
TRIGGER_FIELDS = ("p_grid", "p_station", "both", "grid_only", "station_only", "neither",
                  "hit_rate", "miss_rate", "false_alarm", "agreement", "phi", "miss_if_independent")


def index_metrics(station_index, grid_index, interval_of=None,
                  triggers: Sequence[float] = TRIGGERS) -> dict:
    """Index-level agreement: correlations, RMSE, bias, SD ratio, payout correlation at 90%,
    seasonal correlations (if interval_of is given) and the trigger table at each trigger.

    Trigger-table keys are the TRIGGER_FIELDS names with the trigger appended, e.g. miss_rate90.
    """
    sx, gx = np.asarray(station_index, float), np.asarray(grid_index, float)
    out = {"n_index": int((np.isfinite(sx) & np.isfinite(gx)).sum()),
           "r_index": pearson(sx, gx), "rho_index": spearman(sx, gx),
           "rmse_index": rmse(sx, gx), "bias_index": bias(sx, gx),
           "sd_ratio_index": sd_ratio(sx, gx),
           "r_payout90": pearson(payment_factor(sx, 90.0), payment_factor(gx, 90.0))}
    if interval_of is not None:
        iv = np.asarray(interval_of)
        for season in ("warm", "cool"):
            sel = np.isin(iv, SEASONS[season])
            out[f"r_index_{season}"] = pearson(sx[sel], gx[sel])
            out[f"miss_rate90_{season}"] = trigger_table(gx[sel], sx[sel], 90.0)["miss_rate"]
    for trig in triggers:
        t = trigger_table(gx, sx, trig)
        for name in TRIGGER_FIELDS:
            out[f"{name}{int(trig)}"] = t[name]
    return out


def totals_metrics(station_vals, grid_vals, groups, prefix: str) -> dict:
    """Pearson and Spearman correlation of raw totals and of anomalies vs each series' own
    climatology (group means, e.g. per calendar month or per interval). Keys: n_<prefix>,
    r_<prefix>, rho_<prefix>, r_<prefix>_anom, rho_<prefix>_anom."""
    s, g = np.asarray(station_vals, float), np.asarray(grid_vals, float)
    ok = np.isfinite(s) & np.isfinite(g)
    grp = np.asarray(groups)
    sa = anomalies(np.where(ok, s, np.nan), grp)
    ga = anomalies(np.where(ok, g, np.nan), grp)
    return {f"n_{prefix}": int(ok.sum()), f"r_{prefix}": pearson(s, g),
            f"rho_{prefix}": spearman(s, g), f"r_{prefix}_anom": pearson(sa, ga),
            f"rho_{prefix}_anom": spearman(sa, ga)}


# =================================================================================================
# Distance decay
# =================================================================================================
def exp_decay(d, c0: float, L: float):
    """corr(d) = c0 * exp(-d / L). c0 is the zero-distance correlation (below 1 when the point
    gauge and the areal grid value differ even at the same place); L is the e-folding distance,
    the distance over which correlation falls by a factor e = 2.718."""
    return c0 * np.exp(-np.asarray(d, dtype=float) / L)


def fit_exp_decay(distance, corr, min_points: int = 5, l_max: float = 1e5) -> dict:
    """Least-squares fit of exp_decay to (distance, correlation) points.

    Bounds: 0 < c0 <= 1 and 1 <= L <= l_max (miles). Returns {"c0", "L", "n", "rmse"}
    (NaN when there are too few points or the fit fails). An L that hits l_max means the
    correlation shows no measurable decay over the distances supplied.
    """
    d, r = finite_pair(distance, corr)
    nan = {"c0": float("nan"), "L": float("nan"), "n": int(d.size), "rmse": float("nan")}
    if d.size < min_points:
        return nan
    c0_guess = float(np.clip(r[np.argsort(d)][: max(3, d.size // 10)].mean(), 0.05, 1.0))
    try:
        popt, _ = optimize.curve_fit(exp_decay, d, r, p0=(c0_guess, 200.0),
                                     bounds=([1e-6, 1.0], [1.0, l_max]), maxfev=20000)
    except (RuntimeError, ValueError):
        return nan
    resid = r - exp_decay(d, *popt)
    return {"c0": float(popt[0]), "L": float(popt[1]), "n": int(d.size),
            "rmse": float(np.sqrt(np.mean(resid ** 2)))}


def rowwise_pearson(matrix, vector) -> np.ndarray:
    """Pearson correlation of every row of `matrix` with `vector` (no NaNs allowed); vectorised."""
    m = np.asarray(matrix, dtype=float)
    v = np.asarray(vector, dtype=float)
    mc = m - m.mean(axis=1, keepdims=True)
    vc = v - v.mean()
    den = np.sqrt((mc * mc).sum(axis=1) * (vc * vc).sum())
    with np.errstate(invalid="ignore", divide="ignore"):
        return (mc @ vc) / den


def bootstrap_decay_length(matrix, vector, distance, years, n_boot: int = 200, seed: int = 0,
                           l_max: float = 1e5) -> np.ndarray:
    """Year-block bootstrap of the e-folding distance L.

    matrix: grids x observations (index values), vector: station index per observation,
    distance: miles per grid, years: year label per observation. Whole years are resampled with
    replacement (keeping each year's overlapping intervals together), correlations recomputed,
    and the decay refitted. Returns the array of bootstrap L values (NaN for failed fits).
    """
    rng = np.random.default_rng(seed)
    years = np.asarray(years)
    mat = np.asarray(matrix, dtype=float)
    vec = np.asarray(vector, dtype=float)
    uniq = np.unique(years)
    cols_by_year = {y: np.flatnonzero(years == y) for y in uniq}
    out = np.full(n_boot, np.nan)
    for b in range(n_boot):
        pick = rng.choice(uniq, size=uniq.size, replace=True)
        cols = np.concatenate([cols_by_year[y] for y in pick])
        r = rowwise_pearson(mat[:, cols], vec[cols])
        out[b] = fit_exp_decay(distance, r, l_max=l_max)["L"]
    return out


# =================================================================================================
# Station selection with leave-one-year-out cross-validation
# =================================================================================================
def _mode(xs: list) -> str:
    return max(sorted(set(xs)), key=xs.count) if xs else ""


def loyo_station_selection(target, payouts: dict, years, paired: str,
                           weights: Sequence[float] = WEIGHT_GRID) -> dict:
    """Compare a fixed paired station, the best single station and the best two-station mix
    out of sample, leaving one year out at a time.

    target: the grid's PRF payment factor per observation; payouts: {station: payment factor
    per observation} (same rows, no NaN); years: year label per observation; paired: key of the
    station paired with the farm by design. For each held-out year the best single station and
    the best (pair, weight) are chosen on the other years by correlation with the target, then
    used to predict the held-out year. Pooled held-out predictions give the out-of-sample (oos)
    correlations. Also returns the most frequent choices and how often they were chosen.
    """
    years = np.asarray(years)
    target = np.asarray(target, dtype=float)
    keys = list(payouts)
    pairs = [(a, b) for i, a in enumerate(keys) for b in keys[i + 1:]]
    pred_single = np.full(target.shape, np.nan)
    pred_pair = np.full(target.shape, np.nan)
    chosen_single, chosen_pair = [], []
    for y in np.unique(years):
        tr, te = years != y, years == y
        rs = {k: pearson(target[tr], payouts[k][tr]) for k in keys}
        k_best = max(keys, key=lambda k: rs[k] if np.isfinite(rs[k]) else -np.inf)
        pred_single[te] = payouts[k_best][te]
        chosen_single.append(k_best)
        if pairs:
            best = (pairs[0], float("nan"), -np.inf)
            for a, b in pairs:
                w, r = best_weight(target[tr], payouts[a][tr], payouts[b][tr], weights)
                if np.isfinite(r) and r > best[2]:
                    best = ((a, b), w, r)
            (a, b), w = best[0], best[1]
            pred_pair[te] = portfolio_payout(payouts[a][te], payouts[b][te], w)
            chosen_pair.append(f"{a}+{b}@{w:.2f}")
    ms, mp = _mode(chosen_single), _mode(chosen_pair)
    return {"n": int(target.size), "n_years": int(np.unique(years).size),
            "oos_r_paired": pearson(target, payouts[paired]),
            "oos_r_best_single": pearson(target, pred_single),
            "oos_r_best_pair": pearson(target, pred_pair) if pairs else float("nan"),
            "chosen_single_mode": ms,
            "chosen_single_share": chosen_single.count(ms) / len(chosen_single),
            "chosen_pair_mode": mp,
            "chosen_pair_share": (chosen_pair.count(mp) / len(chosen_pair)
                                  if chosen_pair else float("nan"))}
