"""Replicating PRF interval payouts with monthly station-rain contracts (Kalshi-style ladders).

This is the Milestone 1 baseline for "how well can a portfolio of Kalshi monthly-rain contracts
copy a USDA PRF Rainfall Index payout?" and the foundation the Milestone 2 optimizer builds on.
Everything here is pure arithmetic on year-indexed arrays; data loading and the study loop live
in scripts/run_replication.py.

Objects
-------
Target (what we try to copy). For one PRF grid, one two-month interval and coverage level c, the
payout per $1 of policy protection in year t is

    P_t = max(0, (T - I_t) / T),   T = 100 c,

where I_t is the final grid index (100 = normal). We use the unrounded payment calculation factor
(`agri_hedge.prf.payment_calculation_factor(..., decimals=None)`); RMA's 3-decimal rounding moves
P_t by at most 0.0005.

Contracts (what we can buy). A Kalshi market "Above X inches" for a station and month resolves
YES iff the station's monthly total is strictly greater than X. A NO position therefore pays $1
iff rain <= X. Trace counts as 0 (handled upstream in the station totals).

Hedge families (each adds one constraint, so the cost of each constraint is visible):
  H1  "ideal station index": a hypothetical contract that pays the PRF formula applied to the
      station's own two-month index 100 x (station interval total) / (station normal). No
      fitting. Its error is pure geography + station-vs-gridded measurement mismatch. Variant
      "scaled" holds the NNLS-optimal number of these contracts per $ (one weight).
  H2  "fine monthly ladder": a non-negative combination of hypothetical NO contracts on the
      station's two calendar months, at every 0.25-inch strike. Adds the restriction that the
      hedge must be a sum of a function of month-1 rain and a function of month-2 rain
      (h = g1(R1) + g2(R2), each g non-increasing), while PRF pays on the two-month sum.
  H3  "actual Kalshi ladder": as H2 but only with the strikes Kalshi lists for that series and
      calendar month (whole inches, usually 1-7). Adds strike binning.

Weights are fit by non-negative least squares (NNLS): long-only NO positions, no free cash term
("intercept-free"; a NO at a strike above every observed total plays the role of cash and is a
real contract). Optional ridge shrinkage and a free-sign intercept are available as sensitivity
variants.

Units: weights are numbers of $1-notional NO contracts per $1 of PRF policy protection for the
interval. Fair cost = expected payout of the portfolio under the training-window climatology
(sum over legs of weight x training frequency of rain <= strike), in $ per $ of protection.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping, Sequence

import numpy as np
import pandas as pd
from scipy.optimize import nnls

from agri_hedge.prf import payment_calculation_factor, trigger_grid_index

FINE_STEP_IN = 0.25
#: Kalshi's standard monthly-rain ladder (whole inches 1-7) seen at every series in 2025-2026.
DEFAULT_KALSHI_STRIKES = tuple(float(k) for k in range(1, 8))
FAMILIES = {
    "H1": "ideal station index (PRF formula on the station's own two-month index)",
    "H2": "fine monthly ladder (NO contracts every 0.25 in, both calendar months, NNLS)",
    "H3": "actual Kalshi ladder (NO contracts at listed strikes only, both months, NNLS)",
}
TAIL_INDEX = 70.0          # "tail" years: grid index below 70
MISS_PRF = 0.10            # a "miss": PRF pays more than this per $ ...
MISS_HEDGE = 0.02          # ... but the hedge pays less than this
FALSE_ALARM_PRF = 0.02     # a "false alarm": PRF pays less than this per $ ...
FALSE_ALARM_HEDGE = 0.10   # ... but the hedge pays more than this
MIN_PAY_YEARS = 3          # HE is reported only if PRF pays in at least this many evaluation years


# ---------------------------------------------------------------------------------------------
# Payoffs
# ---------------------------------------------------------------------------------------------

def prf_payout(index, coverage: float) -> np.ndarray:
    """PRF payment calculation factor (indemnity per $1 of protection), unrounded, vectorized.

    `index` is on the 100 = normal scale; `coverage` is a fraction (0.9) or percent (90).
    NaN index stays NaN.
    """
    c = coverage / 100.0 if coverage > 1.0 else coverage
    return np.asarray(payment_calculation_factor(np.asarray(index, dtype=float),
                                                 trigger_grid_index(c), decimals=None), dtype=float)


def no_payoff(rain, strike: float) -> np.ndarray:
    """Payoff of one $1 NO contract on "Above `strike` inches": 1 if rain <= strike, else 0.

    Kalshi resolves YES iff the monthly total is strictly greater than the strike, so a total
    exactly at the strike pays the NO side. NaN rain gives NaN.
    """
    r = np.asarray(rain, dtype=float)
    out = (r <= strike + 1e-9).astype(float)
    out[np.isnan(r)] = np.nan
    return out


def station_index(interval_total, normal: float) -> np.ndarray:
    """Station two-month index on the PRF scale: 100 x interval total / station normal."""
    return 100.0 * np.asarray(interval_total, dtype=float) / float(normal)


# ---------------------------------------------------------------------------------------------
# Strike sets and design matrices
# ---------------------------------------------------------------------------------------------

def fine_strikes(max_rain: float, step: float = FINE_STEP_IN) -> np.ndarray:
    """0.25-inch strike grid from `step` up to the first strike at or above `max_rain`.

    The top strike pays in every observed year, so the ladder can represent any non-increasing
    step function of monthly rain over the observed range (including a constant).
    """
    top = max(step, np.ceil(float(max_rain) / step - 1e-9) * step)
    return np.round(np.arange(step, top + step / 2, step), 4)


def kalshi_strike_sets(markets: pd.DataFrame, series_ticker: str,
                       default: Sequence[float] = DEFAULT_KALSHI_STRIKES) -> dict[int, tuple[float, ...]]:
    """Strikes Kalshi has listed for one series, by calendar month (1-12).

    Uses single-month "greater" markets only. For a calendar month the series has listed, the
    strike set is the union of every strike listed in any year for that month. For months the
    series has never listed, the fallback is the series' most common ladder (or `default` if the
    series has no markets at all). Returns {month: sorted tuple of strikes in inches}.
    """
    m = markets[(markets["series_ticker"] == series_ticker)]
    if "is_single_month" in m.columns:
        m = m[m["is_single_month"].astype(bool)]
    if "strike_type" in m.columns:
        m = m[m["strike_type"] == "greater"]
    m = m.dropna(subset=["floor_strike"])
    out: dict[int, tuple[float, ...]] = {}
    fallback = tuple(float(x) for x in default)
    if not m.empty:
        months = m["contract_month"].astype(str).str[5:7].astype(int)
        ladders = m.groupby("event_ticker")["floor_strike"].apply(lambda s: tuple(sorted(set(s.astype(float)))))
        fallback = ladders.value_counts().index[0]
        for mon, grp in m.groupby(months):
            out[int(mon)] = tuple(sorted(set(grp["floor_strike"].astype(float))))
    return {mon: out.get(mon, fallback) for mon in range(1, 13)}


def ladder_design(rain_by_month: Mapping[int, np.ndarray], strikes_by_month: Mapping[int, Sequence[float]]
                  ) -> tuple[np.ndarray, list[tuple[int, float]]]:
    """Design matrix of NO payoffs: one column per (calendar month, strike).

    rain_by_month maps calendar month -> array of station monthly totals (inches), one per year,
    aligned across months. Returns (X with shape n_years x n_legs, list of (month, strike) legs).
    """
    cols, legs = [], []
    for mon in rain_by_month:
        for k in strikes_by_month[mon]:
            cols.append(no_payoff(rain_by_month[mon], float(k)))
            legs.append((int(mon), float(k)))
    X = np.column_stack(cols) if cols else np.empty((len(next(iter(rain_by_month.values()))), 0))
    return X, legs


# ---------------------------------------------------------------------------------------------
# Fitting
# ---------------------------------------------------------------------------------------------

@dataclass
class LadderFit:
    """Result of a non-negative least-squares ladder fit."""
    weights: np.ndarray                  # contracts per $ of protection, one per leg (>= 0)
    intercept: float = 0.0               # free cash term (0 unless fit_intercept=True)
    legs: list = field(default_factory=list)

    def predict(self, X: np.ndarray) -> np.ndarray:
        return X @ self.weights + self.intercept


def fit_ladder(X: np.ndarray, y: np.ndarray, ridge: float = 0.0, fit_intercept: bool = False,
               legs: list | None = None) -> LadderFit:
    """Fit long-only NO weights w >= 0 minimizing mean((y - Xw - b)^2) + ridge * |w|^2.

    ridge is per observation (the penalty does not grow with sample size). With
    fit_intercept=True a free-sign cash term b is added (unpenalized) via two non-negative
    columns +1 and -1. Rows with NaN in X or y are dropped.
    """
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    ok = ~np.isnan(y) & ~np.isnan(X).any(axis=1)
    X, y = X[ok], y[ok]
    n, p = X.shape
    A = X
    if fit_intercept:
        A = np.column_stack([X, np.ones(n), -np.ones(n)])
    q = A.shape[1]
    b = y
    if ridge > 0:
        pen = np.zeros((p, q))
        pen[np.arange(p), np.arange(p)] = np.sqrt(ridge * n)
        A = np.vstack([A, pen])
        b = np.concatenate([y, np.zeros(p)])
    if q == 0 or n == 0:
        return LadderFit(np.zeros(p), 0.0, list(legs or []))
    sol, _ = nnls(A, b, maxiter=50 * max(q, 10))
    w = sol[:p]
    icpt = float(sol[p] - sol[p + 1]) if fit_intercept else 0.0
    w = np.where(w < 1e-10, 0.0, w)
    return LadderFit(w, icpt, list(legs or []))


def loyo_predictions(X: np.ndarray, y: np.ndarray, ridge: float = 0.0,
                     fit_intercept: bool = False) -> np.ndarray:
    """Leave-one-year-out predictions: refit without year i, predict year i (NaN rows stay NaN)."""
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    out = np.full(len(y), np.nan)
    ok = ~np.isnan(y) & ~np.isnan(X).any(axis=1)
    idx = np.flatnonzero(ok)
    for i in idx:
        keep = ok.copy()
        keep[i] = False
        f = fit_ladder(X[keep], y[keep], ridge=ridge, fit_intercept=fit_intercept)
        out[i] = f.predict(X[i:i + 1])[0]
    return out


def fair_cost(fit: LadderFit, X_train: np.ndarray) -> float:
    """Expected payout per $ of protection under training climatology (mean of in-sample payout)."""
    X_train = np.asarray(X_train, dtype=float)
    ok = ~np.isnan(X_train).any(axis=1)
    return float(np.mean(fit.predict(X_train[ok]))) if ok.any() else float("nan")


# ---------------------------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------------------------

def replication_metrics(prf, hedge, index=None) -> dict:
    """Replication-quality metrics for paired yearly payouts (both in $ per $ of protection).

    rmse           sqrt(mean((PRF - hedge)^2))
    corr           Pearson correlation of PRF and hedge payouts (NaN if either is constant)
    he             hedge effectiveness 1 - Var(PRF - hedge) / Var(PRF); NaN if PRF pays in fewer
                   than MIN_PAY_YEARS years (a 16-year window at 70% coverage often has 0-2)
    tail_capture   sum of hedge payouts / sum of PRF payouts over years with index < 70
    miss_rate      share of years with PRF > 0.10 in which the hedge pays < 0.02
    false_alarm_rate share of years with PRF < 0.02 in which the hedge pays > 0.10
    bias           mean(hedge - PRF) (positive = hedge overpays on average)
    mean_over      mean(max(0, hedge - PRF)); mean_under = mean(max(0, PRF - hedge))
    Also returns n_years, n_prf_pay (PRF > 0), n_tail, n_prf_big (PRF > 0.10), n_prf_small,
    mean_prf, mean_hedge, min_hedge, and var_prf / var_resid (population variances) so HE can be
    pooled across groups as 1 - sum(n var_resid) / sum(n var_prf) (see `pooled_he`).
    """
    p = np.asarray(prf, dtype=float)
    h = np.asarray(hedge, dtype=float)
    ok = ~np.isnan(p) & ~np.isnan(h)
    idx = None if index is None else np.asarray(index, dtype=float)
    if idx is not None:
        ok &= ~np.isnan(idx)
        idx = idx[ok]
    p, h = p[ok], h[ok]
    n = len(p)
    res = {"n_years": n}
    if n == 0:
        return {**res, **{k: np.nan for k in ("rmse", "corr", "he", "tail_capture", "miss_rate",
                                              "false_alarm_rate", "bias", "mean_over", "mean_under",
                                              "mean_prf", "mean_hedge", "min_hedge", "var_prf", "var_resid")},
                "n_prf_pay": 0, "n_tail": 0, "n_prf_big": 0, "n_prf_small": 0}
    e = p - h
    res["rmse"] = float(np.sqrt(np.mean(e ** 2)))
    res["corr"] = float(np.corrcoef(p, h)[0, 1]) if (np.std(p) > 0 and np.std(h) > 0) else np.nan
    vp = np.var(p)
    res["n_prf_pay"] = int((p > 0).sum())
    res["var_prf"] = float(vp)
    res["var_resid"] = float(np.var(e))
    res["he"] = float(1.0 - np.var(e) / vp) if (vp > 0 and res["n_prf_pay"] >= MIN_PAY_YEARS) else np.nan
    if idx is not None:
        tail = idx < TAIL_INDEX
        res["n_tail"] = int(tail.sum())
        res["tail_capture"] = float(h[tail].sum() / p[tail].sum()) if p[tail].sum() > 0 else np.nan
    else:
        res["n_tail"], res["tail_capture"] = 0, np.nan
    big = p > MISS_PRF
    small = p < FALSE_ALARM_PRF
    res["n_prf_big"] = int(big.sum())
    res["n_prf_small"] = int(small.sum())
    res["miss_rate"] = float(np.mean(h[big] < MISS_HEDGE)) if big.any() else np.nan
    res["false_alarm_rate"] = float(np.mean(h[small] > FALSE_ALARM_HEDGE)) if small.any() else np.nan
    res["bias"] = float(np.mean(h - p))
    res["mean_over"] = float(np.mean(np.maximum(0.0, h - p)))
    res["mean_under"] = float(np.mean(np.maximum(0.0, p - h)))
    res["mean_prf"] = float(np.mean(p))
    res["mean_hedge"] = float(np.mean(h))
    res["min_hedge"] = float(np.min(h))
    return res


def pooled_he(df: pd.DataFrame) -> float:
    """Variance-weighted HE over several groups: 1 - sum(n var_resid) / sum(n var_prf).

    `df` holds rows of `replication_metrics` output (columns n_years, var_prf, var_resid). This
    is the share of total PRF payout variance (summed over the groups) that the hedges remove;
    unlike a plain mean of per-group HE it is not dominated by groups where PRF barely varies.
    """
    d = df.dropna(subset=["var_prf", "var_resid"])
    den = float((d["n_years"] * d["var_prf"]).sum())
    return float(1.0 - (d["n_years"] * d["var_resid"]).sum() / den) if den > 0 else float("nan")


# ---------------------------------------------------------------------------------------------
# One interval, all families
# ---------------------------------------------------------------------------------------------

@dataclass
class IntervalReplication:
    """All hedge families for one (grid, interval, coverage) target.

    years         years used (station data complete for both months and index available)
    prf           PRF payout per $ by year
    hedges        {(family, variant, scheme): payout array}; scheme is "split" (fit on train
                  years, in-sample there, out-of-sample on test years), "loyo" (leave one year
                  out) or "full" (fit on all years, in-sample)
    fits          {(family, variant, fit_window): LadderFit}
    legs          {family: list of (month, strike)}
    leg_probs     {(family, fit_window): training frequency that each leg pays}
    """
    years: np.ndarray
    index: np.ndarray
    prf: np.ndarray
    station_index: np.ndarray
    train_mask: np.ndarray
    hedges: dict
    fits: dict
    legs: dict
    leg_probs: dict


def replicate_interval(years, grid_index, rain_m1, rain_m2, months: tuple[int, int], coverage: float,
                       train_years: tuple[int, int], fine_strikes_by_month: Mapping[int, Sequence[float]],
                       kalshi_strikes_by_month: Mapping[int, Sequence[float]], station_normal: float,
                       ridge: float | Mapping[str, float] = 0.0, variants: Iterable[str] = ("no_intercept",),
                       do_loyo: bool = True, full_window: tuple[int, int] | None = None
                       ) -> IntervalReplication:
    """Fit and backtest H1, H2, H3 for one PRF grid, interval, and coverage level.

    years, grid_index, rain_m1, rain_m2 are aligned arrays (one value per year). Years with any
    NaN among index, rain_m1, rain_m2 are dropped. months are the interval's two calendar months.
    train_years = (first, last) inclusive for the time-split fit. station_normal is the station's
    mean two-month total (inches) used by H1. ridge is one penalty for both ladders or a dict
    {"H2": lam2, "H3": lam3}. variants: "no_intercept" (primary) and/or
    "free_intercept". full_window (first, last) adds an in-sample fit on that window (used for
    forward-looking weights).
    """
    years = np.asarray(years, dtype=int)
    gi = np.asarray(grid_index, dtype=float)
    r1 = np.asarray(rain_m1, dtype=float)
    r2 = np.asarray(rain_m2, dtype=float)
    ok = ~(np.isnan(gi) | np.isnan(r1) | np.isnan(r2))
    years, gi, r1, r2 = years[ok], gi[ok], r1[ok], r2[ok]
    prf = prf_payout(gi, coverage)
    st_idx = station_index(r1 + r2, station_normal)
    train = (years >= train_years[0]) & (years <= train_years[1])
    hedges, fits, legs, leg_probs = {}, {}, {}, {}

    h1 = prf_payout(st_idx, coverage)
    for scheme in ("split", "loyo", "full"):
        hedges[("H1", "none", scheme)] = h1
    # H1 "scaled": the best non-negative number of ideal contracts per $ (one NNLS weight). It
    # makes H1 comparable with the fitted ladders, which can shrink toward zero when far away.
    X1 = h1.reshape(-1, 1)
    f1 = fit_ladder(X1[train], prf[train], legs=[("station_index_put", np.nan)])
    fits[("H1", "scaled", "train")] = f1
    hedges[("H1", "scaled", "split")] = f1.predict(X1)
    if do_loyo:
        hedges[("H1", "scaled", "loyo")] = loyo_predictions(X1, prf)

    m1, m2 = months
    windows = {"train": train}
    if full_window is not None:
        windows["full"] = (years >= full_window[0]) & (years <= full_window[1])
    for fam, sets in (("H2", fine_strikes_by_month), ("H3", kalshi_strikes_by_month)):
        lam = float(ridge.get(fam, 0.0)) if isinstance(ridge, Mapping) else float(ridge)
        X, fam_legs = ladder_design({m1: r1, m2: r2}, {m1: sets[m1], m2: sets[m2]})
        legs[fam] = fam_legs
        for wname, wmask in windows.items():
            leg_probs[(fam, wname)] = X[wmask].mean(axis=0) if wmask.any() else np.full(X.shape[1], np.nan)
        for var in variants:
            icpt = var == "free_intercept"
            f = fit_ladder(X[train], prf[train], ridge=lam, fit_intercept=icpt, legs=fam_legs)
            fits[(fam, var, "train")] = f
            hedges[(fam, var, "split")] = f.predict(X)
            if "full" in windows:
                ff = fit_ladder(X[windows["full"]], prf[windows["full"]], ridge=lam,
                                fit_intercept=icpt, legs=fam_legs)
                fits[(fam, var, "full")] = ff
                hedges[(fam, var, "full")] = ff.predict(X)
            if do_loyo:
                hedges[(fam, var, "loyo")] = loyo_predictions(X, prf, ridge=lam, fit_intercept=icpt)
    return IntervalReplication(years, gi, prf, st_idx, train, hedges, fits, legs, leg_probs)


def evaluate(rep: IntervalReplication, test_years: tuple[int, int]) -> list[dict]:
    """Metrics for every hedge in `rep` on three evaluation sets.

    eval_set "train" (in-sample, split fit), "test" (out-of-sample years of the split fit) and
    "loyo" (all years, leave-one-year-out predictions). H1 has no fitted parameters, so its
    three rows are plain evaluations on those year sets.
    """
    test = (rep.years >= test_years[0]) & (rep.years <= test_years[1])
    rows = []
    for (fam, var, scheme), h in rep.hedges.items():
        if scheme == "split":
            sets = {"train": rep.train_mask, "test": test}
        elif scheme == "loyo":
            sets = {"loyo": np.ones(len(rep.years), bool)}
        else:
            continue
        for name, mask in sets.items():
            m = replication_metrics(rep.prf[mask], h[mask], rep.index[mask])
            rows.append({"hedge_family": fam, "fit_variant": var, "eval_set": name,
                         "eval_years": f"{rep.years[mask].min()}-{rep.years[mask].max()}" if mask.any() else "",
                         **m})
    return rows
