"""Row-crop rain hedges: county yield losses against station and local rain contracts (doc 29).

PRF insures forage, so it is not the benchmark for commercial crops. The benchmark there is a
private parametric rainfall policy, which settles on rain at the farm's own location (no
geographic basis) but carries an insurer's loading. This module holds the pieces of that
comparison that are pure arithmetic:

* `yield_loss_fraction`: shortfall of a county yield below its own trend, per $1 of expected revenue.
* `season_rain`: per-harvest-year rain for a crop's season months, including months of the
  previous calendar year (winter wheat's fall).
* `relative_basis`: puts and calls on rain as a share of normal. A crop's "template" payoff is a
  non-negative mix of these, fitted once on a whole state's county panel, so every county shares
  one payoff shape and no county-level curve fitting is needed.
* `digital_approximation`: the best long-only ladder of NO or YES binaries at a given strike set
  for one put or call. This is how a template is carried onto whole-inch or third-inch strikes.
* `collar_columns`: NO (drought) and YES (excess rain) ladders on each season month, used for the
  per-county fitting check.
* `breakeven_load`: the loading at which a better-fitting but dearer contract costs the same
  per unit of risk removed as a cheaper one.

Fitting and pricing reuse `agri_hedge.replicate` and `agri_hedge.exotics`.
"""
from __future__ import annotations

from typing import Mapping, Sequence

import numpy as np
import pandas as pd

from scipy.optimize import nnls

from agri_hedge import exotics as ex

#: season months per crop as (year offset, calendar month); offset -1 is the year before harvest.
SEASONS: dict[str, tuple[tuple[int, int], ...]] = {
    "corn": ((0, 5), (0, 6), (0, 7), (0, 8)),
    "soybeans": ((0, 6), (0, 7), (0, 8), (0, 9)),
    "sorghum": ((0, 5), (0, 6), (0, 7), (0, 8)),
    "cotton": ((0, 6), (0, 7), (0, 8), (0, 9)),
    "winter_wheat": ((-1, 10), (-1, 11), (0, 3), (0, 4), (0, 5)),
}
#: 2026/27 projected season-average farm prices, USDA WASDE-676 (Oct 9 2026), as in docs 03a/03b.
PRICES = {"corn": 4.70, "soybeans": 12.00, "sorghum": 4.50, "winter_wheat": 6.30, "cotton": 0.77}
CROP_LABEL = {"corn": "Corn", "soybeans": "Soybeans", "sorghum": "Grain sorghum", "cotton": "Upland cotton",
              "winter_wheat": "Winter wheat"}


#: template strikes as a share of the month's (or season's) normal rain
MONTH_PUT_K, MONTH_CALL_K = (0.3, 0.5, 0.7, 0.9, 1.1), (1.3, 1.6, 2.0, 2.5)
SEASON_PUT_K, SEASON_CALL_K = (0.4, 0.55, 0.7, 0.85, 1.0), (1.15, 1.3, 1.5, 1.8)


def haversine_mi(lat1, lon1, lat2, lon2):
    """Great-circle distance in statute miles (vectorized)."""
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = p2 - p1
    dlmb = np.radians(np.asarray(lon2) - np.asarray(lon1))
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlmb / 2) ** 2
    return 3958.7613 * 2 * np.arcsin(np.sqrt(a))


def quadratic_trend(years: np.ndarray, values: np.ndarray) -> np.ndarray:
    """Least-squares quadratic time trend evaluated at every year (NaN values are skipped in the fit)."""
    t = np.asarray(years, dtype=float)
    v = np.asarray(values, dtype=float)
    ok = ~np.isnan(v)
    if ok.sum() < 4:
        return np.full(len(t), np.nan)
    tc = t - t[ok].mean()
    coef = np.polyfit(tc[ok], v[ok], 2)
    return np.polyval(coef, tc)


def yield_loss_fraction(years: np.ndarray, yields: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(loss, trend): loss = max(0, 1 - yield / trend), the revenue shortfall per $1 of expected
    revenue at a fixed price. NaN where the yield is missing."""
    y = np.asarray(yields, dtype=float)
    trend = quadratic_trend(years, y)
    with np.errstate(invalid="ignore", divide="ignore"):
        loss = np.clip(1.0 - y / trend, 0.0, None)
    loss[np.isnan(y) | ~(trend > 0)] = np.nan
    return loss, trend


def season_rain(monthly: pd.DataFrame, season: Sequence[tuple[int, int]], years: np.ndarray) -> dict[str, np.ndarray]:
    """Rain for each season month by harvest year.

    `monthly` is indexed by calendar year with columns 1..12 (NaN = unknown). Returns
    {label: array aligned with `years`}; labels are "m10p" for a previous-year month, "m5" otherwise.
    """
    out = {}
    for off, mon in season:
        col = monthly[mon].reindex(np.asarray(years) + off).to_numpy(dtype=float)
        out[f"m{mon}{'p' if off < 0 else ''}"] = col
    return out


def collar_columns(rain: Mapping[str, np.ndarray], step: float, strikes: Sequence[float] | None = None,
                   max_strike: float = 7.0, drought_only: bool = False) -> dict[str, np.ndarray]:
    """Monthly NO (and YES unless `drought_only`) payoffs for every season month.

    `strikes` fixes the strike list (today's listed whole-inch strikes); otherwise a `step`
    ladder up to `max_strike` is used.
    """
    cols = {}
    for lab, r in rain.items():
        ks = np.asarray(strikes, dtype=float) if strikes is not None else ex.strike_grid(step, max_strike)
        for k in ks:
            cols[f"NO {lab} <= {k:.2f}"] = ex.no_payoff(r, k)
            if not drought_only:
                cols[f"YES {lab} > {k:.2f}"] = ex.yes_payoff(r, k)
    return cols


def season_total(rain: Mapping[str, np.ndarray]) -> np.ndarray:
    """Sum of the season months (NaN if any month is unknown)."""
    return np.sum(np.column_stack(list(rain.values())), axis=1)


def season_total_columns(rain: Mapping[str, np.ndarray], step: float) -> dict[str, np.ndarray]:
    """NO and YES ladders on the season total, up to the wettest season on record."""
    tot = season_total(rain)
    return {**ex.sum_no_ladder(tot, step, label="season"), **ex.sum_yes_ladder(tot, step, label="season")}


def relative_basis(rain, normal: float, put_k: Sequence[float] = MONTH_PUT_K,
                   call_k: Sequence[float] = MONTH_CALL_K) -> tuple[np.ndarray, list[tuple[str, float]]]:
    """Puts max(0, k - x) and calls max(0, x - k) on x = rain / normal.

    Returns (B, legs): B has one column per leg (NaN rows where rain is unknown); legs lists
    ("put" | "call", strike in inches) for each column.
    """
    r = np.asarray(rain, dtype=float)
    x = r / float(normal)
    cols, legs = [], []
    for k in put_k:
        cols.append(np.clip(k - x, 0.0, None))
        legs.append(("put", float(k) * float(normal)))
    for k in call_k:
        cols.append(np.clip(x - k, 0.0, None))
        legs.append(("call", float(k) * float(normal)))
    B = np.column_stack(cols)
    B[np.isnan(r)] = np.nan
    return B, legs


def digital_approximation(rain, target, kind: str, strikes: Sequence[float]) -> np.ndarray:
    """Long-only weights on binaries at `strikes` that best copy `target` (least squares on the rain history).

    kind "put" uses NO binaries (pay when rain <= K), "call" uses YES binaries (rain > K). The
    target is a known function of the same rain, so this is a discretization, not a forecast.
    """
    r = np.asarray(rain, dtype=float)
    y = np.asarray(target, dtype=float)
    ok = ~np.isnan(r) & ~np.isnan(y)
    ks = np.asarray(strikes, dtype=float)
    if len(ks) == 0 or ok.sum() == 0:
        return np.zeros(len(ks))
    pay = ex.no_payoff if kind == "put" else ex.yes_payoff
    X = np.column_stack([pay(r[ok], k) for k in ks])
    w, _ = nnls(X, y[ok], maxiter=50 * max(len(ks), 10))
    return w


def digital_matrix(rain, strikes: Sequence[float]) -> np.ndarray:
    """[NO at each strike | YES at each strike] payoffs for one rain series (NaN rows where unknown)."""
    ks = np.asarray(strikes, dtype=float)
    return np.column_stack([ex.no_payoff(rain, k) for k in ks] + [ex.yes_payoff(rain, k) for k in ks])


def pooled_hedge_ratio(y: np.ndarray, h: np.ndarray, leave_out: int | None = None) -> float:
    """Minimum-variance hedge ratio pooled over cases: sum cov(y, h) / sum var(h), floored at 0.

    y and h are (cases x years) arrays with NaN for missing years; each case is demeaned by its
    own mean. `leave_out` drops one year column from the sums.
    """
    y = np.asarray(y, dtype=float)
    h = np.asarray(h, dtype=float)
    ok = ~np.isnan(y) & ~np.isnan(h)
    yd = np.where(ok, y, np.nan)
    hd = np.where(ok, h, np.nan)
    yd = yd - np.nanmean(yd, axis=1, keepdims=True)
    hd = hd - np.nanmean(hd, axis=1, keepdims=True)
    if leave_out is not None:
        yd = np.delete(yd, leave_out, axis=1)
        hd = np.delete(hd, leave_out, axis=1)
    den = np.nansum(hd * hd)
    return float(max(0.0, np.nansum(yd * hd) / den)) if den > 0 else 0.0


def breakeven_load(load_cheap: float, payout_cheap: float, risk_removed_cheap: float,
                   payout_dear: float, risk_removed_dear: float) -> float:
    """Loading at which the better-fitting contract costs the same per unit of risk removed.

    The buyer of a hedge with expected payout E and load L pays (L - 1) E a year in expectation
    for removing R of risk (standard deviation of the net loss). Setting the cost per unit of
    risk equal, (L* - 1) E_dear / R_dear = (L_cheap - 1) E_cheap / R_cheap. Returns L*; NaN if
    either hedge removes no risk.
    """
    if not (risk_removed_cheap > 0 and risk_removed_dear > 0 and payout_dear > 0):
        return float("nan")
    unit = (load_cheap - 1.0) * payout_cheap / risk_removed_cheap
    return float(1.0 + unit * risk_removed_dear / payout_dear)
