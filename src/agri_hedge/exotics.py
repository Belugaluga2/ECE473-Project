"""Fair pricing of fine-strike rain ladders and payoffs of exotic rain contracts (docs 27 and 28).

Two questions share this module:

1. *What is a "more than K inches" contract worth at strikes Kalshi does not list?* Kalshi lists
   whole-inch strikes (1-7 in). We price a ladder in third-inch steps (0.33, 0.67, 1.00, ...)
   from station history: the share of past months whose total exceeded K (`empirical_yes_prob`),
   a Wilson interval for that share, and a smoothed estimate from a zero-inflated gamma fit to
   the same months (`zi_gamma_fit`, `zi_gamma_yes_prob`). Ladder "resolution" metrics say how
   much of the rain distribution each ladder can see (`ladder_resolution`).

2. *Which exotic payoffs would serve farm insurance?* Builders for payoff columns that do not
   exist on Kalshi today, all settled on the same NWS daily climate report Kalshi already uses:
   two-month totals, worst-month lookbacks, AND/OR joint digitals, dry-spell barriers, wet-day
   counts and one-day maxima (`interval_daily_stats`, `digital_ge`, `digital_le`, ...). Hedges
   are fit with the NNLS machinery of `agri_hedge.replicate`.

Conventions. Rain is in inches; strikes are rounded to 0.01 in because the NWS reports to
hundredths, so "more than 0.33 in" is settled YES at 0.34 in and NO at 0.33 in (Kalshi: YES iff
strictly greater). A $1 YES pays 1 if rain > K; a $1 NO pays 1 if rain <= K. Probabilities are
dollars per $1 contract. Trace counts as 0 (upstream in the station totals). Months or
intervals with a missing day are NaN (the true value is unknown).
"""
from __future__ import annotations

import math
from typing import Iterable, Mapping, Sequence

import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import nnls

#: strike step for a "third-inch" ladder, and the two comparison ladders
THIRD_IN = 1.0 / 3.0
STEPS = {"whole": 1.0, "half": 0.5, "third": THIRD_IN, "quarter": 0.25}
#: a strike is "informative" when its fair YES price sits inside this band (dollars)
INFORMATIVE_LO, INFORMATIVE_HI = 0.05, 0.95
#: "wet day" threshold used for rain-day counts and dry spells (inches). The NWS counts a day
#: with 0.01 in or more as a day with measurable precipitation; 0.10 in is the agronomic
#: convention for a day that wets the root zone.
WET_DAY_IN = 0.10
MEASURABLE_IN = 0.01


# ---------------------------------------------------------------------------------------------
# Strike grids
# ---------------------------------------------------------------------------------------------

def strike_grid(step: float, max_strike: float, min_strike: float | None = None) -> np.ndarray:
    """Strikes `step`, 2 step, ... up to the first multiple at or above `max_strike`, rounded to 0.01 in.

    A third-inch grid is 0.33, 0.67, 1.00, 1.33, ... (n/3 rounded to hundredths), so every
    whole-inch strike is also in the third-inch ladder. `min_strike` drops strikes below it.
    """
    if step <= 0:
        raise ValueError("step must be positive")
    n_max = max(1, int(math.ceil(float(max_strike) / step - 1e-9)))
    ks = np.round(np.arange(1, n_max + 1) * step, 2)
    if min_strike is not None:
        ks = ks[ks >= float(min_strike) - 1e-9]
    return ks


def third_inch_strikes(max_strike: float) -> np.ndarray:
    return strike_grid(THIRD_IN, max_strike)


def whole_inch_strikes(max_strike: float) -> np.ndarray:
    return strike_grid(1.0, max_strike)


# ---------------------------------------------------------------------------------------------
# Fair probabilities
# ---------------------------------------------------------------------------------------------

def yes_payoff(rain, strike: float) -> np.ndarray:
    """1 where rain > strike (YES pays), 0 where rain <= strike, NaN where rain is unknown."""
    r = np.asarray(rain, dtype=float)
    out = (r > float(strike) + 1e-9).astype(float)
    out[np.isnan(r)] = np.nan
    return out


def no_payoff(rain, strike: float) -> np.ndarray:
    """1 where rain <= strike (NO pays), 0 otherwise, NaN where unknown."""
    y = yes_payoff(rain, strike)
    return np.where(np.isnan(y), np.nan, 1.0 - y)


def empirical_yes_prob(rain, strike: float) -> tuple[float, int, int]:
    """(share of known values above `strike`, count above, count known)."""
    y = yes_payoff(rain, strike)
    y = y[~np.isnan(y)]
    n = int(len(y))
    k = int(y.sum())
    return (k / n if n else float("nan")), k, n


def wilson_interval(k: int, n: int, z: float = 1.6448536269514722) -> tuple[float, float]:
    """Wilson score interval for a binomial share (default z gives a 90% interval)."""
    if n <= 0:
        return float("nan"), float("nan")
    p = k / n
    denom = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def zi_gamma_fit(values, zero_at: float = 0.005) -> dict:
    """Fit a zero-inflated gamma to monthly totals: P(dry month) and a gamma for wet months.

    `zero_at` is the largest total treated as "zero" (0.00 in, i.e. only trace, in NWS data).
    Returns {p0, shape, scale, n, n_pos}. With fewer than 5 positive values the gamma is not
    fit (shape and scale NaN). Maximum likelihood with the location fixed at 0.
    """
    v = np.asarray(values, dtype=float)
    v = v[~np.isnan(v)]
    n = int(len(v))
    pos = v[v > zero_at]
    p0 = float((n - len(pos)) / n) if n else float("nan")
    if len(pos) < 5:
        return {"p0": p0, "shape": float("nan"), "scale": float("nan"), "n": n, "n_pos": int(len(pos))}
    shape, _, scale = stats.gamma.fit(pos, floc=0)
    return {"p0": p0, "shape": float(shape), "scale": float(scale), "n": n, "n_pos": int(len(pos))}


def zi_gamma_yes_prob(fit: Mapping[str, float], strike) -> np.ndarray:
    """P(rain > strike) under a zero-inflated gamma fit (vectorized over strikes)."""
    k = np.asarray(strike, dtype=float)
    if not np.isfinite(fit.get("shape", float("nan"))):
        return np.full(k.shape, np.nan, dtype=float)
    tail = stats.gamma.sf(k, fit["shape"], loc=0, scale=fit["scale"])
    return (1.0 - fit["p0"]) * tail


def fair_price_table(rain_by_year: pd.Series | np.ndarray, strikes: Sequence[float],
                     windows: Mapping[str, tuple[int, int]], years: np.ndarray | None = None,
                     ci_window: str | None = None, gamma_window: str | None = None) -> pd.DataFrame:
    """One row per strike with fair YES probabilities over several year windows.

    rain_by_year: values indexed by year (a Series) or an array aligned with `years`.
    windows: {name: (first_year, last_year)}; adds columns p_yes_<name>, n_<name>.
    ci_window: window whose empirical share gets a 90% Wilson interval (ci_lo, ci_hi).
    gamma_window: window used for the zero-inflated gamma fit (p_yes_gamma).
    """
    if isinstance(rain_by_year, pd.Series):
        yrs = rain_by_year.index.to_numpy(dtype=int)
        vals = rain_by_year.to_numpy(dtype=float)
    else:
        yrs = np.asarray(years, dtype=int)
        vals = np.asarray(rain_by_year, dtype=float)
    out = pd.DataFrame({"strike_in": np.round(np.asarray(strikes, dtype=float), 2)})
    for name, (y0, y1) in windows.items():
        sel = vals[(yrs >= y0) & (yrs <= y1)]
        probs, ks, ns = [], [], []
        for k in out["strike_in"]:
            p, kk, nn = empirical_yes_prob(sel, k)
            probs.append(p); ks.append(kk); ns.append(nn)
        out[f"p_yes_{name}"] = probs
        out[f"n_{name}"] = ns
        if ci_window == name:
            ci = [wilson_interval(kk, nn) for kk, nn in zip(ks, ns)]
            out["ci90_lo"] = [c[0] for c in ci]
            out["ci90_hi"] = [c[1] for c in ci]
    if gamma_window is not None:
        y0, y1 = windows[gamma_window]
        fit = zi_gamma_fit(vals[(yrs >= y0) & (yrs <= y1)])
        out["p_yes_gamma"] = zi_gamma_yes_prob(fit, out["strike_in"].to_numpy())
        out["gamma_shape"] = fit["shape"]
        out["gamma_scale"] = fit["scale"]
        out["gamma_p0"] = fit["p0"]
    return out


# ---------------------------------------------------------------------------------------------
# Ladder resolution: how much of the distribution a strike set can see
# ---------------------------------------------------------------------------------------------

def informative_count(p_yes: Sequence[float], lo: float = INFORMATIVE_LO, hi: float = INFORMATIVE_HI) -> int:
    """Number of strikes whose fair YES price lies in [lo, hi]."""
    p = np.asarray(p_yes, dtype=float)
    return int(np.sum((p >= lo) & (p <= hi)))


def bin_masses(p_yes: Sequence[float]) -> np.ndarray:
    """Probability mass between consecutive strikes, including both tails.

    For strikes K1 < K2 < ... with YES probabilities p1 >= p2 >= ..., the masses are
    [1 - p1, p1 - p2, ..., p_last]. Their maximum is the coarsest bin: the largest share of
    outcomes the ladder lumps together.
    """
    p = np.asarray(p_yes, dtype=float)
    if len(p) == 0:
        return np.array([1.0])
    return np.concatenate([[1.0 - p[0]], p[:-1] - p[1:], [p[-1]]])


def linear_put_payoff(rain, trigger: float) -> np.ndarray:
    """PRF-style payout per $1 on one rain total: max(0, (trigger - rain) / trigger)."""
    r = np.asarray(rain, dtype=float)
    return np.where(np.isnan(r), np.nan, np.clip((float(trigger) - r) / float(trigger), 0.0, None))


def ladder_approximation(target, rain, strikes: Sequence[float]) -> dict:
    """Best long-only NO ladder (NNLS, in sample) for a payoff that is a known function of rain.

    This is a discretization measure, not a forecast: the target is a deterministic function
    of the same rain the ladder settles on, so in-sample fit is the right yardstick. Returns
    rmse, r2 (share of target variance explained), n_legs used, and the ladder's fair cost
    (mean payout) against the target's mean.
    """
    y = np.asarray(target, dtype=float)
    r = np.asarray(rain, dtype=float)
    ok = ~np.isnan(y) & ~np.isnan(r)
    y, r = y[ok], r[ok]
    if len(y) == 0:
        return {"rmse": np.nan, "r2": np.nan, "n_legs": 0, "fair_cost": np.nan, "target_mean": np.nan}
    X = np.column_stack([no_payoff(r, k) for k in strikes]) if len(strikes) else np.zeros((len(y), 0))
    if X.shape[1] == 0:
        w = np.zeros(0)
        pred = np.zeros_like(y)
    else:
        w, _ = nnls(X, y, maxiter=50 * max(X.shape[1], 10))
        pred = X @ w
    e = y - pred
    vy = np.var(y)
    return {"rmse": float(np.sqrt(np.mean(e ** 2))),
            "r2": float(1 - np.var(e) / vy) if vy > 0 else np.nan,
            "n_legs": int(np.sum(w > 1e-10)),
            "fair_cost": float(np.mean(pred)), "target_mean": float(np.mean(y)),
            "weights": w}


def ladder_resolution(rain, strikes: Sequence[float], trigger: float | None = None) -> dict:
    """Resolution metrics of one strike set against one month's rain history.

    informative: strikes priced 5-95 cents; max_bin: coarsest probability bin; approx_r2 and
    approx_rmse: how well the best NO ladder copies a PRF-style linear put with `trigger`
    (default 0.9 x the mean of the known values, i.e. a 90% coverage monthly put).
    """
    r = np.asarray(rain, dtype=float)
    r = r[~np.isnan(r)]
    probs = np.array([empirical_yes_prob(r, k)[0] for k in strikes])
    trig = float(trigger) if trigger is not None else 0.9 * float(np.mean(r)) if len(r) else np.nan
    appr = ladder_approximation(linear_put_payoff(r, trig), r, strikes) if len(r) and trig > 0 else {}
    return {"n_strikes": len(strikes), "informative": informative_count(probs),
            "max_bin": float(np.max(bin_masses(probs))) if len(probs) else 1.0,
            "trigger_in": trig, "approx_r2": appr.get("r2", np.nan), "approx_rmse": appr.get("rmse", np.nan),
            "approx_legs": appr.get("n_legs", 0)}


# ---------------------------------------------------------------------------------------------
# Exotic payoffs from monthly totals
# ---------------------------------------------------------------------------------------------

def digital_le(x, k: float) -> np.ndarray:
    """1 where x <= k (NaN-aware)."""
    return no_payoff(x, k)


def digital_ge(x, k: float) -> np.ndarray:
    """1 where x >= k (NaN-aware). For counts and spell lengths, where "at least" is natural."""
    v = np.asarray(x, dtype=float)
    out = (v >= float(k) - 1e-9).astype(float)
    out[np.isnan(v)] = np.nan
    return out


def two_month_total(r1, r2) -> np.ndarray:
    return np.asarray(r1, dtype=float) + np.asarray(r2, dtype=float)


def worst_month(r1, r2) -> np.ndarray:
    """min of the two monthly totals (NaN if either is unknown)."""
    a = np.asarray(r1, dtype=float)
    b = np.asarray(r2, dtype=float)
    out = np.minimum(a, b)
    out[np.isnan(a) | np.isnan(b)] = np.nan
    return out


def and_digital(r1, r2, k1: float, k2: float) -> np.ndarray:
    """1 if both months are at or below their strikes."""
    return no_payoff(r1, k1) * no_payoff(r2, k2)


def or_digital(r1, r2, k1: float, k2: float) -> np.ndarray:
    """1 if either month is at or below its strike."""
    a = no_payoff(r1, k1)
    b = no_payoff(r2, k2)
    return np.where(np.isnan(a) | np.isnan(b), np.nan, np.maximum(a, b))


def quantile_strikes(rain, quantiles: Sequence[float], step: float = THIRD_IN) -> np.ndarray:
    """Third-inch strikes closest to the given quantiles of a rain history (unique, sorted)."""
    r = np.asarray(rain, dtype=float)
    r = r[~np.isnan(r)]
    if len(r) == 0:
        return np.array([])
    qs = np.quantile(r, quantiles)
    ks = np.round(np.maximum(1, np.round(qs / step)) * step, 2)
    return np.unique(ks)


# ---------------------------------------------------------------------------------------------
# Exotic statistics from daily data
# ---------------------------------------------------------------------------------------------

def longest_dry_spell(daily: Sequence[float], wet_threshold: float = WET_DAY_IN) -> float:
    """Longest run of consecutive days with precipitation below `wet_threshold` (NaN if any day unknown)."""
    v = np.asarray(daily, dtype=float)
    if len(v) == 0 or np.isnan(v).any():
        return float("nan")
    best = run = 0
    for x in v:
        if x < wet_threshold - 1e-9:
            run += 1
            best = max(best, run)
        else:
            run = 0
    return float(best)


def wet_day_count(daily: Sequence[float], wet_threshold: float = WET_DAY_IN) -> float:
    v = np.asarray(daily, dtype=float)
    if len(v) == 0 or np.isnan(v).any():
        return float("nan")
    return float(np.sum(v >= wet_threshold - 1e-9))


def max_daily(daily: Sequence[float]) -> float:
    v = np.asarray(daily, dtype=float)
    if len(v) == 0 or np.isnan(v).any():
        return float("nan")
    return float(np.max(v))


def interval_daily_stats(daily: pd.DataFrame, months: Sequence[int], wet_threshold: float = WET_DAY_IN,
                         value_col: str = "precip_in", date_col: str = "date") -> pd.DataFrame:
    """Per-year path statistics of one station over a set of calendar months.

    `daily` has one row per day with `date` and `precip_in` (NaN = missing). Returns a frame
    indexed by year with total_in, dry_spell_days (longest run below `wet_threshold`), wet_days
    (days at or above it), measurable_days (days >= 0.01 in), max_1day_in and n_days. A year
    is NaN on every statistic if any day in the window is missing or absent from the record
    (the window is incomplete).
    """
    d = daily[[date_col, value_col]].copy()
    d[date_col] = pd.to_datetime(d[date_col])
    d = d[d[date_col].dt.month.isin(list(months))]
    rows = []
    for year, g in d.groupby(d[date_col].dt.year):
        expected = sum(pd.Period(f"{year}-{m:02d}").days_in_month for m in months)
        v = g.sort_values(date_col)[value_col].to_numpy(dtype=float)
        complete = len(v) == expected and not np.isnan(v).any()
        rows.append({
            "year": int(year), "n_days": int(len(v)), "complete": bool(complete),
            "total_in": float(np.sum(v)) if complete else np.nan,
            "dry_spell_days": longest_dry_spell(v, wet_threshold) if complete else np.nan,
            "wet_days": wet_day_count(v, wet_threshold) if complete else np.nan,
            "measurable_days": wet_day_count(v, MEASURABLE_IN) if complete else np.nan,
            "max_1day_in": max_daily(v) if complete else np.nan,
        })
    out = pd.DataFrame(rows).set_index("year").sort_index()
    return out


# ---------------------------------------------------------------------------------------------
# Instrument sets (design-matrix builders) for the exotic study
# ---------------------------------------------------------------------------------------------

def design_from_columns(cols: Mapping[str, np.ndarray]) -> tuple[np.ndarray, list[str]]:
    """Stack named payoff columns into a design matrix, dropping all-NaN or constant-zero legs."""
    names, mats = [], []
    for name, c in cols.items():
        c = np.asarray(c, dtype=float)
        if np.all(np.isnan(c)):
            continue
        if np.nanmax(c) <= 0:
            continue
        names.append(name)
        mats.append(c)
    X = np.column_stack(mats) if mats else np.empty((len(next(iter(cols.values()))), 0))
    return X, names


def monthly_no_ladder(rain_by_month: Mapping[int, np.ndarray], step: float, max_strike: float | None = None
                      ) -> dict[str, np.ndarray]:
    """NO payoffs at every strike of a `step` ladder for each calendar month in `rain_by_month`."""
    cols = {}
    for mon, r in rain_by_month.items():
        top = max_strike if max_strike is not None else np.nanmax(r)
        for k in strike_grid(step, top):
            cols[f"NO m{mon} <= {k:.2f}"] = no_payoff(r, k)
    return cols


def monthly_yes_ladder(rain_by_month: Mapping[int, np.ndarray], step: float, max_strike: float | None = None
                       ) -> dict[str, np.ndarray]:
    """YES payoffs ("more than K") at every strike of a `step` ladder for each month."""
    cols = {}
    for mon, r in rain_by_month.items():
        top = max_strike if max_strike is not None else np.nanmax(r)
        for k in strike_grid(step, top):
            cols[f"YES m{mon} > {k:.2f}"] = yes_payoff(r, k)
    return cols


def sum_no_ladder(total: np.ndarray, step: float, label: str = "sum") -> dict[str, np.ndarray]:
    return {f"NO {label} <= {k:.2f}": no_payoff(total, k) for k in strike_grid(step, np.nanmax(total))}


def sum_yes_ladder(total: np.ndarray, step: float, label: str = "sum") -> dict[str, np.ndarray]:
    return {f"YES {label} > {k:.2f}": yes_payoff(total, k) for k in strike_grid(step, np.nanmax(total))}


def worst_month_ladder(r1, r2, step: float) -> dict[str, np.ndarray]:
    w = worst_month(r1, r2)
    return {f"NO min <= {k:.2f}": no_payoff(w, k) for k in strike_grid(step, np.nanmax(w))}


def and_or_ladder(r1, r2, quantiles: Sequence[float] = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6),
                  step: float = THIRD_IN) -> dict[str, np.ndarray]:
    """AND and OR digitals at quantile-matched third-inch strike pairs."""
    cols = {}
    k1s = quantile_strikes(r1, quantiles, step)
    k2s = quantile_strikes(r2, quantiles, step)
    for q, k1, k2 in zip(quantiles, np.resize(k1s, len(quantiles)), np.resize(k2s, len(quantiles))):
        cols[f"AND m1<={k1:.2f} & m2<={k2:.2f}"] = and_digital(r1, r2, k1, k2)
        cols[f"OR m1<={k1:.2f} | m2<={k2:.2f}"] = or_digital(r1, r2, k1, k2)
    return cols


def dry_spell_ladder(spell_days: np.ndarray, thresholds: Sequence[int] = (7, 10, 14, 21, 28, 35, 42)
                     ) -> dict[str, np.ndarray]:
    return {f"DRYSPELL >= {d}d": digital_ge(spell_days, d) for d in thresholds}


def wet_day_ladder(wet_days: np.ndarray, thresholds: Sequence[int] = (2, 4, 6, 8, 10, 12, 15)
                   ) -> dict[str, np.ndarray]:
    return {f"WETDAYS <= {n}": digital_le(wet_days, n) for n in thresholds}


def max_day_ladder(max_1day: np.ndarray, thresholds: Sequence[float] = (1.0, 1.5, 2.0, 2.5, 3.0, 4.0)
                   ) -> dict[str, np.ndarray]:
    return {f"MAXDAY >= {x:.1f}": digital_ge(max_1day, x) for x in thresholds}


# ---------------------------------------------------------------------------------------------
# Pricing a fitted hedge: fair value, spread and fee per $ of expected payout
# ---------------------------------------------------------------------------------------------

def hedge_pricing(weights: np.ndarray, X: np.ndarray, half_spread: float = 0.0225,
                  fee_rate: float = 0.07) -> dict:
    """Cost of holding `weights` contracts of each leg, per $1 of protection.

    Leg probabilities are in-sample means of the payoff columns. The taker pays the fair
    probability plus `half_spread` and Kalshi's fee `fee_rate` x p x (1 - p) per contract (no
    rounding here; see `agri_hedge.pricing.taker_fee` for per-order rounding).
    Returns fair_cost (expected payout), contracts (sum of weights), spread_cost, fee_cost,
    all_in_cost, load (= all_in / fair) and thin_share (share of fair cost on legs that paid
    in fewer than 5 of the years in X).
    """
    w = np.asarray(weights, dtype=float)
    Xm = np.asarray(X, dtype=float)
    ok = ~np.isnan(Xm).any(axis=1)
    Xm = Xm[ok]
    p = Xm.mean(axis=0) if len(Xm) else np.full(len(w), np.nan)
    n_pay = Xm.sum(axis=0) if len(Xm) else np.zeros(len(w))
    fair = float(np.sum(w * p))
    price = np.clip(p + half_spread, 0.01, 0.99)
    spread_cost = float(np.sum(w * (price - p)))
    fee = float(np.sum(w * fee_rate * price * (1 - price)))
    thin = float(np.sum((w * p)[n_pay < 5]) / fair) if fair > 0 else np.nan
    return {"fair_cost": fair, "contracts": float(np.sum(w)), "spread_cost": spread_cost,
            "fee_cost": fee, "all_in_cost": fair + spread_cost + fee,
            "load": (fair + spread_cost + fee) / fair if fair > 0 else np.nan, "thin_share": thin,
            "n_legs": int(np.sum(w > 1e-10))}
