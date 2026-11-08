"""A frozen, small pilot against observed regional milk yield (doc 25).

Observed shortfalls include every cause. Weather-index protection against these shortfalls
does not identify causal heat damage, an individual farm's loss, or an executable trade.
The publication's cow-weighted THI bins are distinct from the airport temperature signal.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

STATES = {"COLORADO": "CO_weld", "PENNSYLVANIA": "PA_lancaster", "TEXAS": "TX_erath"}
TRAIN_END = 2000
TEST_START, TEST_END = 2001, 2018
MONTHS = (6, 7, 8, 9)
LIMIT_FRACTION = 0.10
HERD = 1000
MILK_PRICE_CWT = 21.0  # fixed scenario, not an observed historical milk-price series
USD_PER_KG = 2.20462262185 * MILK_PRICE_CWT / 100
INDICES = ("airport_dd80", "regional_thi69_days", "regional_thi79_days")


def annual_panel(monthly: pd.DataFrame, daily: pd.DataFrame, baseline_method="growth") -> pd.DataFrame:
    """Complete June-September milk totals and fixed weather indices, no gap filling.

    Milk is kg/cow/day in the prepared input. The source hot bins start approximately at
    THI 69.4 and 79.3 (publication's CreateFigure2a.R); source fractions are multiplied by
    calendar days before aggregation. Airport DD-80 uses observed/flagged threaded Tmax.
    """
    m = monthly[monthly.state.isin(STATES) & monthly.month.isin(MONTHS)].copy()
    if m.duplicated(["state", "year", "month"]).any():
        raise ValueError("Duplicate state-month observations")
    records = []
    for (state, year), group in m.groupby(["state", "year"]):
        if set(group.month) != set(MONTHS) or group["milk_kg_cow_day"].isna().any():
            continue
        expected = pd.to_datetime(dict(year=group.year, month=group.month, day=1)).dt.days_in_month
        if not np.array_equal(group.days.to_numpy(), expected.to_numpy()):
            raise ValueError("Source calendar days do not match dates")
        site = STATES[state]
        weather = daily[(daily.site == site) & (daily.date.dt.year == year)
                        & daily.date.dt.month.isin(MONTHS)]
        if (len(weather) != int(group.days.sum()) or weather.date.duplicated().any()
                or not np.isfinite(weather.airport_tmax_f).all()):
            continue
        records.append({"state": state, "year": int(year),
            "milk_kg_cow": float(group.milk_kg_cow_day @ group.days),
            "regional_thi69_days": float(group.thi69_share @ group.days),
            "regional_thi79_days": float(group.thi79_share @ group.days),
            "airport_dd80": float(np.maximum(weather.airport_tmax_f - 80, 0).sum()),
            "airport_thread_share": float(weather.airport_filled_from_thread.mean())})
    out = pd.DataFrame(records).sort_values(["state", "year"]).reset_index(drop=True)
    out["baseline_kg_cow"] = np.nan
    for state, group in out.groupby("state"):
        series = group.set_index("year").milk_kg_cow
        predicted = preseason_baseline(series, method=baseline_method)
        out.loc[group.index, "baseline_kg_cow"] = group.year.map(predicted).to_numpy()
    out["loss_fraction"] = np.maximum(1 - out.milk_kg_cow / out.baseline_kg_cow, 0)
    return out


def preseason_baseline(milk: pd.Series, growth_years: int = 5, method="growth") -> pd.Series:
    """Previous summer's milk times average log growth over five completed annual changes.

    Six consecutive earlier summers are required. Every forecast uses only information
    available before that year's summer. Subsequent years may use previously observed
    holdout production, just as a farmer can update a production forecast each spring.
    """
    milk = milk.sort_index().astype(float)
    if not milk.index.is_unique or (milk <= 0).any() or not np.isfinite(milk).all():
        raise ValueError("Milk yields must be unique by year, finite and positive")
    if method not in ("growth", "trend"):
        raise ValueError("Unknown baseline method")
    result = pd.Series(np.nan, index=milk.index, dtype=float)
    for year in milk.index:
        if method == "trend":
            earlier = milk[milk.index < year].tail(10)
            if len(earlier) >= 8:
                x = earlier.index.to_numpy(float) - year
                slope, intercept = np.linalg.lstsq(np.column_stack([x, np.ones(len(x))]),
                                                  np.log(earlier.to_numpy()), rcond=None)[0]
                result.loc[year] = float(np.exp(intercept))
            continue
        previous = milk.reindex(range(int(year) - growth_years - 1, int(year)))
        if previous.notna().all():
            result.loc[year] = float(previous.iloc[-1] * np.exp(np.log(previous).diff().dropna().mean()))
    return result


@dataclass(frozen=True)
class Cover:
    trigger: float
    slope: float
    limit: float = LIMIT_FRACTION

    def payout(self, index):
        values = np.asarray(index, float)
        return np.minimum(self.limit, self.slope * np.maximum(values - self.trigger, 0))


def fit_cover(years, index, loss, train_end=TRAIN_END, minimum=8) -> Cover:
    """One nonnegative slope; trigger is the earlier-period mean, with a fixed payout cap.

    No threshold search and no selection of the best validation-region result. Missing
    production forecasts exclude loss-fitting rows, but not earlier weather climatology.
    """
    years, index, loss = map(lambda x: np.asarray(x, float), (years, index, loss))
    earlier = (years <= train_end) & np.isfinite(index)
    usable = earlier & np.isfinite(loss)
    if usable.sum() < minimum:
        raise ValueError(f"Insufficient training shortfalls: {usable.sum()} < {minimum}")
    trigger = float(index[earlier].mean())
    z = np.maximum(index[usable] - trigger, 0)
    slope = max(float(z @ loss[usable] / (z @ z)), 0) if z @ z > 0 else 0.0
    return Cover(trigger, slope)


def earlier_premiums(years, index, cover: Cover, loading=0.10):
    """Model premium = expanding earlier-weather mean payout times (1 + loading).

    A load includes all frictions in this simple sensitivity, not verified market fees.
    No validation outcome or current-year weather enters that year's price estimate.
    """
    years, index = np.asarray(years), np.asarray(index, float)
    return np.array([float(cover.payout(index[years < year]).mean()) * (1 + loading)
                     if (years < year).any() else np.nan for year in years])


def protection_metrics(loss, payout, premium=None) -> dict:
    """Dimensionless metrics; target and payout are fractions of expected production.

    Net HE includes variable premiums. Tail shortfall is floored at zero; HE uses the
    signed residual, so overpayments are also penalized. A zero-variance target has no HE.
    """
    y, h = np.asarray(loss, float), np.asarray(payout, float)
    premium = np.zeros_like(y) if premium is None else np.asarray(premium, float)
    if y.shape != h.shape or y.shape != premium.shape or not len(y):
        raise ValueError("Need equal nonempty vectors")
    if not all(np.isfinite(a).all() for a in (y, h, premium)) or (y < 0).any() or (h < 0).any():
        raise ValueError("Need finite, nonnegative losses and payouts")
    residual, net = y - h, y - h + premium
    variance = float(np.var(y))
    denominator = float(y.sum())
    return {"n_test": len(y), "loss_years": int((y > 0).sum()),
        "he_gross": 1 - float(np.var(residual)) / variance if variance > 0 else np.nan,
        "he_net": 1 - float(np.var(net)) / variance if variance > 0 else np.nan,
        "nrmse": float(np.sqrt(np.mean(residual ** 2) / variance)) if variance > 0 else np.nan,
        "mean_loss_fraction": float(y.mean()), "mean_payout_fraction": float(h.mean()),
        "bias_fraction": float((h - y).mean()),
        "payout_recovery": float(np.minimum(y, h).sum() / denominator) if denominator else np.nan,
        "p95_shortfall_fraction": float(np.quantile(np.maximum(residual, 0), .95)),
        "p95_net_shortfall_fraction": float(np.quantile(np.maximum(net, 0), .95)),
        "unhedged_p95_fraction": float(np.quantile(y, .95)),
        "mean_premium_fraction": float(premium.mean()),
        "mean_net_benefit_fraction": float((h - premium).mean())}


def he_interval(loss, payout, seed=473, repetitions=2000):
    """Paired-year bootstrap interval for a fixed hedge, conditional on its fitted parameters.

    This is not an interval accounting for contract/model selection, nor a causality test.
    """
    y, h = np.asarray(loss, float), np.asarray(payout, float)
    rng = np.random.default_rng(seed)
    take = rng.integers(0, len(y), size=(repetitions, len(y)))
    yy, hh = y[take], h[take]
    v = np.var(yy, axis=1)
    valid = v > 0
    values = 1 - np.var(yy[valid] - hh[valid], axis=1) / v[valid]
    return np.quantile(values, [.025, .975]).tolist() if len(values) else [np.nan, np.nan]
