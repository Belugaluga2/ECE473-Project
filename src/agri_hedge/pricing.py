"""Pricing Kalshi monthly-rain hedges and comparing their payouts with PRF (Milestone 1, A3).

This module answers two questions for one farm:

1. *What would the hedge have paid?* A hedge is a set of "legs". Each leg is a number of $1 NO
   contracts on one Kalshi monthly-rain market ("Above X inches" for one station and calendar
   month). A NO pays $1 iff the station's monthly total is <= X (Kalshi resolves YES iff the total
   is strictly greater than X). The leg sizes come from the replication weights of doc 08
   (`data/processed/replication_weights.csv`): contracts = weight per $ of interval protection x
   the interval's share of the policy x the policy's total protection.

2. *What would it cost?* Every contract is bought outright (fully prepaid). The cost of a leg is
   contracts x price + taker fee + the cost of the cash being locked up until settlement. The
   price can be

   - fair value: the leg's climatological probability of paying (share of past months with rain
     <= strike), optionally plus half the bid-ask spread for an order that takes liquidity;
   - a calibrated market price: the price a market with Kalshi's historical price-vs-outcome
     pattern (doc 05b, `kalshi_rain_calibration.csv`) would quote for that probability;
   - an observed price: a historical candle or a live order book walked level by level.

Everything here is plain arithmetic on pandas/numpy objects so that tests can use synthetic data
and the Milestone 2 optimizer can import the same functions. Data loading and the study loop
live in `scripts/run_payout_comparison.py`.

Units: contracts are $1-notional contracts, prices are dollars per contract (0-1), money is US
dollars, rates are annual decimals (0.0405 = 4.05% per year).
"""
from __future__ import annotations

import math
from typing import Iterable, Mapping, Sequence

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from agri_hedge.kalshi import fee as kalshi_fee

#: 3-month Treasury bill rate (secondary market, discount basis), FRED series DTB3 on
#: 2026-10-27: 4.05%. https://fred.stlouisfed.org/series/DTB3 (retrieved 2026-10-29).
DEFAULT_TBILL_RATE = 0.0405
#: Interest Kalshi pays on cash and open positions (variable), doc 05 / help.kalshi.com "APY on Kalshi".
KALSHI_APY = 0.035
#: Days the purchase price is locked up: a monthly market lists about 30 days before it closes
#: (doc 05b markets table: 28-32 days for DFW/DEN 2025-26) and settles about a day after close.
DEFAULT_LOCKUP_DAYS = 31
#: Bid-ask spread assumptions (dollars): median of hourly contested quotes (doc 05) and mean of
#: daily closing spreads over all monthly-rain markets (doc 05b). A taker pays half the spread.
SPREAD_LOW = 0.045
SPREAD_HIGH = 0.131
#: Kalshi trades between 1 and 99 cents.
PRICE_MIN = 0.01
PRICE_MAX = 0.99
#: Fee rounding: FCM-cleared (retail) accounts are rounded up to $0.01 per order; direct
#: members to $0.0001 (docs.kalshi.com/getting_started/fee_rounding).
FEE_TICK_RETAIL = 0.01
FEE_TICK_DIRECT = 0.0001


# ---------------------------------------------------------------------------------------------
# Building a farm's hedge
# ---------------------------------------------------------------------------------------------

def farm_hedge_legs(weights: pd.DataFrame, allocation: Mapping[str, float], protection: float) -> pd.DataFrame:
    """Turn per-$ replication weights into a farm's leg sizes (number of $1 NO contracts).

    Args:
        weights: rows of `replication_weights.csv` already filtered to one target index, hedge
            family, fit window, site, grid role and coverage. Needs the columns `interval_name`,
            `contract_month`, `strike_in`, `weight_per_dollar_protection`. Rows for intervals the
            farm did not insure are ignored.
        allocation: {interval name: share of the policy's value}, e.g. {"Apr-May": 0.4, ...}.
        protection: the policy's total protection in dollars (all intervals together).

    Returns one row per (contract_month, strike_in) with `contracts` = sum over intervals of
    weight x share x protection, plus the per-$ weight and the interval it came from. PRF
    forbids two insured intervals from sharing a month, so in practice each leg comes from one
    interval; legs are still summed in case they do not.
    """
    alloc = {k: float(v) for k, v in allocation.items() if float(v) > 0}
    w = weights[weights["interval_name"].astype(str).isin(alloc)].copy()
    if w.empty:
        return pd.DataFrame(columns=["contract_month", "strike_in", "interval_name", "alloc",
                                     "weight_per_dollar_protection", "contracts"])
    w["alloc"] = w["interval_name"].astype(str).map(alloc)
    w["contracts"] = w["weight_per_dollar_protection"].astype(float) * w["alloc"] * float(protection)
    keep = {"interval_name": "first", "alloc": "first", "weight_per_dollar_protection": "sum",
            "contracts": "sum"}
    for extra in ("leg_prob_pays_fit_window", "strike_listed_on_kalshi", "kalshi_series"):
        if extra in w.columns:
            keep[extra] = "first"
    legs = (w.groupby(["contract_month", "strike_in"], as_index=False).agg(keep)
            .sort_values(["contract_month", "strike_in"]).reset_index(drop=True))
    legs["contract_month"] = legs["contract_month"].astype(int)
    legs["strike_in"] = legs["strike_in"].astype(float)
    return legs


def rain_wide(station_monthly: pd.DataFrame, station_key: str | None = None) -> pd.DataFrame:
    """Year x month (1-12) table of station monthly totals in inches.

    Months with any missing day (`n_missing` != 0) are set to NaN: the true total is unknown, so
    the NO outcome is unknown. `station_monthly` has the columns of
    `data/processed/station_monthly_precip.csv` (station_key, year, month, precip_in, n_missing).
    """
    s = station_monthly
    if station_key is not None:
        s = s[s["station_key"] == station_key]
    s = s.copy()
    if "n_missing" in s.columns:
        s.loc[s["n_missing"].fillna(1) != 0, "precip_in"] = np.nan
    w = s.pivot_table(index="year", columns="month", values="precip_in", aggfunc="first", dropna=False)
    return w.reindex(columns=range(1, 13)).sort_index()


def no_pays(rain, strike: float) -> np.ndarray:
    """1.0 where a NO on "Above `strike` inches" pays (rain <= strike), 0.0 where not, NaN if unknown."""
    r = np.asarray(rain, dtype=float)
    out = (r <= float(strike) + 1e-9).astype(float)
    out[np.isnan(r)] = np.nan
    return out


def hedge_payout_by_year(legs: pd.DataFrame, rain: pd.DataFrame, years: Iterable[int] | None = None) -> pd.Series:
    """Dollar payout of a hedge in each year: sum over legs of contracts x 1(rain <= strike).

    A year is NaN if any month the hedge needs is incomplete. `rain` is a `rain_wide` table.
    """
    idx = pd.Index(sorted(years) if years is not None else rain.index, name="year")
    total = pd.Series(0.0, index=idx)
    if legs.empty:
        return total
    r = rain.reindex(idx)
    for _, leg in legs.iterrows():
        pay = no_pays(r[int(leg["contract_month"])].to_numpy(), leg["strike_in"])
        total = total + float(leg["contracts"]) * pay
    return total.rename("hedge_payout_usd")


def leg_probability(rain: pd.DataFrame, month: int, strike: float, window: tuple[int, int]) -> float:
    """Share of complete months in `window` (inclusive years) with rain <= strike (fair NO price)."""
    col = rain.loc[(rain.index >= window[0]) & (rain.index <= window[1]), int(month)]
    pay = no_pays(col.to_numpy(), strike)
    pay = pay[~np.isnan(pay)]
    return float(pay.mean()) if len(pay) else float("nan")


def add_leg_probabilities(legs: pd.DataFrame, rain: pd.DataFrame, window: tuple[int, int],
                          column: str = "q") -> pd.DataFrame:
    """Copy of `legs` with a column of climatological NO probabilities over `window`."""
    out = legs.copy()
    out[column] = [leg_probability(rain, int(m), float(k), window)
                   for m, k in zip(out["contract_month"], out["strike_in"])]
    return out


def expected_payout(legs: pd.DataFrame, prob_column: str = "q") -> float:
    """Expected dollar payout of a hedge: sum of contracts x probability of paying."""
    return float((legs["contracts"] * legs[prob_column]).sum())


# ---------------------------------------------------------------------------------------------
# Prices, fees and capital
# ---------------------------------------------------------------------------------------------

def clip_price(p):
    """Limit prices to Kalshi's 1-99 cent band (vectorized)."""
    return np.clip(np.asarray(p, dtype=float), PRICE_MIN, PRICE_MAX)


def taker_fee(contracts, price, tick: float = FEE_TICK_RETAIL) -> np.ndarray:
    """Kalshi taker fee per order, 0.07 x C x P x (1 - P), rounded up to `tick` dollars.

    Vectorized over legs (one order per leg). Uses `agri_hedge.kalshi.fee` for the formula and
    then rounds up to `tick` ($0.01 for FCM-cleared retail accounts, $0.0001 for direct members).
    Climate series have no maker fee, so a resting limit order pays nothing.
    """
    c = np.atleast_1d(np.asarray(contracts, dtype=float))
    p = np.broadcast_to(np.atleast_1d(np.asarray(price, dtype=float)), c.shape)
    out = np.zeros(c.shape)
    for i, (ci, pi) in enumerate(zip(c, p)):
        if ci <= 0 or not np.isfinite(pi) or not np.isfinite(ci):
            out[i] = 0.0 if ci <= 0 else np.nan
            continue
        raw = kalshi_fee(round(float(ci), 6), round(float(pi), 6), round_up=False)
        out[i] = math.ceil(raw / tick - 1e-9) * tick
    return out


def capital_cost(outlay, rate: float = DEFAULT_TBILL_RATE, days: float = DEFAULT_LOCKUP_DAYS,
                 credited_rate: float = 0.0):
    """Opportunity cost of prepaying `outlay` dollars for `days` days.

    The cash could have earned `rate` (T-bill). If the exchange credits `credited_rate` on open
    positions (Kalshi's APY), only the difference is lost. Simple interest, 365-day year.
    """
    return np.asarray(outlay, dtype=float) * max(rate - credited_rate, 0.0) * float(days) / 365.0


def logistic_calibration_fit(cal: pd.DataFrame, price_col: str = "mean_price", rate_col: str = "yes_rate",
                             n_col: str = "n") -> tuple[float, float]:
    """Fit logit(outcome rate) = a + b x logit(price) to binned calibration data.

    `cal` has one row per price bin with the mean price, the share of those markets that resolved
    YES and the number of markets (the layout of `kalshi_rain_calibration.csv`). The fit
    maximizes the binomial likelihood of the bin counts, so bins with 0% or 100% outcomes are
    handled. a < 0 with b near 1 means YES contracts are priced above how often they win.
    Returns (a, b).
    """
    d = cal.dropna(subset=[price_col, rate_col, n_col])
    d = d[d[n_col] > 0]
    x = _logit(np.clip(d[price_col].to_numpy(float), 0.005, 0.995))
    k = d[rate_col].to_numpy(float) * d[n_col].to_numpy(float)
    n = d[n_col].to_numpy(float)

    def nll(theta):
        z = theta[0] + theta[1] * x
        # log(1 + exp(z)) computed stably
        return float(np.sum(n * np.logaddexp(0.0, z) - k * z))

    res = minimize(nll, x0=np.array([0.0, 1.0]), method="Nelder-Mead",
                   options={"xatol": 1e-8, "fatol": 1e-10, "maxiter": 5000})
    return float(res.x[0]), float(res.x[1])


def calibrated_yes_price(p_true, a: float, b: float) -> np.ndarray:
    """Price a market with calibration (a, b) quotes for a YES whose true probability is `p_true`.

    Inverts logit(p_true) = a + b x logit(price). Result is clipped to the 1-99 cent band.
    """
    p = np.clip(np.asarray(p_true, dtype=float), 1e-6, 1 - 1e-6)
    return clip_price(_expit((_logit(p) - a) / b))


def calibrated_no_price(q_no, a: float, b: float) -> np.ndarray:
    """Calibrated price of a NO that pays with probability `q_no`: 1 - YES price at 1 - q."""
    q = np.asarray(q_no, dtype=float)
    return clip_price(1.0 - calibrated_yes_price(1.0 - q, a, b))


def price_legs(legs: pd.DataFrame, mid, half_spread: float = 0.0, taker: bool = True,
               rate: float = DEFAULT_TBILL_RATE, days: float = DEFAULT_LOCKUP_DAYS,
               credited_rate: float = 0.0, fee_tick: float = FEE_TICK_RETAIL) -> pd.DataFrame:
    """Cost of buying every leg at `mid` + `half_spread` (clipped to 1-99 cents).

    Args:
        legs: needs `contracts`.
        mid: per-leg mid price (array or column name in `legs`). NaN means no price exists.
        half_spread: added to the mid for an order that crosses the spread (a taker).
        taker: True adds Kalshi's taker fee; False models a resting limit order (no fee on
            climate series). A maker normally also avoids the spread: pass half_spread=0.
    Returns a copy of `legs` with columns price, premium_usd, fee_usd, capital_usd, cost_usd.
    """
    out = legs.copy()
    m = out[mid].to_numpy(float) if isinstance(mid, str) else np.asarray(mid, dtype=float)
    price = clip_price(m + half_spread)
    price = np.where(np.isnan(m), np.nan, price)
    c = out["contracts"].to_numpy(float)
    out["price"] = price
    out["premium_usd"] = c * price
    out["fee_usd"] = taker_fee(c, price, tick=fee_tick) if taker else 0.0
    out["capital_usd"] = capital_cost(out["premium_usd"] + out["fee_usd"], rate, days, credited_rate)
    out["cost_usd"] = out["premium_usd"] + out["fee_usd"] + out["capital_usd"]
    return out


def cost_totals(priced: pd.DataFrame) -> dict:
    """Sum the cost columns of `price_legs` output over the legs that have a price."""
    ok = priced["price"].notna()
    return {
        "premium_usd": float(priced.loc[ok, "premium_usd"].sum()),
        "fee_usd": float(priced.loc[ok, "fee_usd"].sum()),
        "capital_usd": float(priced.loc[ok, "capital_usd"].sum()),
        "cost_usd": float(priced.loc[ok, "cost_usd"].sum()),
        "contracts_priced": float(priced.loc[ok, "contracts"].sum()),
        "contracts_unpriced": float(priced.loc[~ok, "contracts"].sum()),
    }


# ---------------------------------------------------------------------------------------------
# Order books
# ---------------------------------------------------------------------------------------------

def no_asks_from_yes_bids(yes_bids: Sequence[Sequence[float]]) -> list[tuple[float, float]]:
    """NO offers implied by resting YES bids: a YES bid at p for q contracts lets you buy q NO at 1 - p.

    Returns [(no_price, size)] sorted cheapest first. Zero-size and out-of-band levels are dropped.
    """
    out = [(round(1.0 - float(p), 6), float(q)) for p, q in yes_bids if float(q) > 0 and 0 < float(p) < 1]
    return sorted(out, key=lambda x: x[0])


def walk_no_book(yes_bids: Sequence[Sequence[float]], contracts: float | None = None,
                 max_price: float | None = None, fee_tick: float = FEE_TICK_RETAIL) -> dict:
    """Buy up to `contracts` NO contracts against resting YES bids, cheapest first.

    Stops when the order is filled, the book runs out, or the next level costs more than
    `max_price`. The taker fee is charged per price level filled (each level is a separate
    trade) and rounded up to `fee_tick`.

    Returns {filled, cost_usd (price only), fee_usd, vwap, levels_used, depth_available}.
    """
    asks = no_asks_from_yes_bids(yes_bids)
    filled = cost = fees = 0.0
    used = 0
    depth = sum(q for p, q in asks if max_price is None or p <= max_price + 1e-12)
    for p, q in asks:
        if max_price is not None and p > max_price + 1e-12:
            break
        take = q if contracts is None else min(q, float(contracts) - filled)
        if take <= 1e-12:
            break
        filled += take
        cost += take * p
        fees += float(taker_fee([take], [p], tick=fee_tick)[0])
        used += 1
    return {"filled": filled, "cost_usd": cost, "fee_usd": fees,
            "vwap": cost / filled if filled else float("nan"), "levels_used": used,
            "depth_available": depth}


# ---------------------------------------------------------------------------------------------
# Payout comparison and cost comparison
# ---------------------------------------------------------------------------------------------

def payout_comparison(prf, hedge, protection: float, years=None, material: float = 0.05,
                      ratio: float = 0.5) -> dict:
    """Compare yearly PRF indemnities with yearly hedge payouts (both in dollars).

    Years where either is NaN are dropped. Definitions (per $ of policy protection P):

    - corr: Pearson correlation across years.
    - he: hedge effectiveness 1 - Var(PRF - hedge) / Var(PRF).
    - payout_ratio: total hedge payout / total PRF payout.
    - recovery: sum over years of min(hedge, PRF) / total PRF payout, i.e. the share of PRF's
      dollars that the hedge matched in the same year (overpayments in other years do not count).
    - prf_only_years: PRF paid at least `material` x P but the hedge paid less than `ratio` x PRF.
    - kalshi_only_years: the hedge paid at least `material` x P but PRF paid less than `ratio` x hedge.
    - largest shortfall / overpay: the worst year for each direction, in dollars.
    """
    p = np.asarray(prf, dtype=float)
    h = np.asarray(hedge, dtype=float)
    yrs = np.asarray(years) if years is not None else np.arange(len(p))
    ok = ~(np.isnan(p) | np.isnan(h))
    p, h, yrs = p[ok], h[ok], yrs[ok]
    n = len(p)
    out = {"n_years": n}
    if n == 0:
        return out
    thr = material * float(protection)
    prf_only = (p >= thr) & (h < ratio * p)
    k_only = (h >= thr) & (p < ratio * h)
    gap = p - h
    out.update({
        "mean_prf_usd": float(p.mean()), "mean_hedge_usd": float(h.mean()),
        "corr": float(np.corrcoef(p, h)[0, 1]) if n > 2 and p.std() > 0 and h.std() > 0 else float("nan"),
        "he": float(1 - np.var(p - h) / np.var(p)) if np.var(p) > 0 else float("nan"),
        "rmse_usd": float(np.sqrt(np.mean(gap ** 2))),
        "payout_ratio": float(h.sum() / p.sum()) if p.sum() > 0 else float("nan"),
        "recovery": float(np.minimum(h, p).sum() / p.sum()) if p.sum() > 0 else float("nan"),
        "mean_shortfall_usd": float(np.clip(gap, 0, None).mean()),
        "mean_overpay_usd": float(np.clip(-gap, 0, None).mean()),
        "years_prf_paid": int((p >= thr).sum()), "years_hedge_paid": int((h >= thr).sum()),
        "prf_only_years": int(prf_only.sum()), "kalshi_only_years": int(k_only.sum()),
        "prf_only_list": ",".join(str(int(y)) for y in yrs[prf_only]),
        "kalshi_only_list": ",".join(str(int(y)) for y in yrs[k_only]),
        "worst_shortfall_year": int(yrs[np.argmax(gap)]), "worst_shortfall_usd": float(gap.max()),
        "worst_overpay_year": int(yrs[np.argmin(gap)]), "worst_overpay_usd": float(-gap.min()),
    })
    return out


def load_factor(cost: float, expected: float) -> float:
    """Cost per $1 of expected payout (the "load"): 1 = fair, < 1 = subsidized, > 1 = marked up."""
    return float(cost) / float(expected) if expected else float("nan")


def subsidy_to_match(kalshi_cost: float, kalshi_expected: float, prf_producer_premium: float,
                     prf_expected: float) -> dict:
    """Subsidy a Kalshi hedge would need to give the farmer what PRF gives.

    - dollars_same_net: S such that E[hedge] - (cost - S) = E[PRF] - producer premium, i.e. the
      same expected net gain per year.
    - share_same_net: that S as a share of the hedge's cost.
    - share_same_load: share s of the cost that must be paid so that the farmer's cost per $1 of
      expected payout equals PRF's: (1 - s) x cost / E[hedge] = producer premium / E[PRF].
    """
    s_dollars = float(kalshi_cost - kalshi_expected + (prf_expected - prf_producer_premium))
    s_load = 1.0 - (prf_producer_premium / prf_expected) * (kalshi_expected / kalshi_cost)
    return {"dollars_same_net": s_dollars, "share_same_net": s_dollars / kalshi_cost,
            "share_same_load": float(s_load)}


# ---------------------------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------------------------

def _logit(p):
    p = np.asarray(p, dtype=float)
    return np.log(p) - np.log1p(-p)


def _expit(z):
    return 1.0 / (1.0 + np.exp(-np.asarray(z, dtype=float)))
