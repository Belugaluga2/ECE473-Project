"""Milestone 2, week 4: where the hedge error comes from, and what new contracts would fix it.

Instrument builders for the error waterfall (doc 16, Maya) and the contract proposals (doc 17,
Evan). Each builder returns (payoff matrix years x instruments, labels, fair probabilities) for a
`HedgeProblem` from `hedge_builder`, so any instrument set can be dropped into the optimizer.

Waterfall order (each step adds one real-world restriction to the step before):

    S0 perfect          a contract on the farm's own grid index: hedge effectiveness 1 by definition
    S1 geography        the same PRF formula on the *station's* grid (another 0.25-degree cell)
    S2 settlement       the PRF formula on the station gauge's own index (one rain gauge, the NWS
                        climate report, instead of NOAA's gridded analysis)
    S3 monthly          contracts on each calendar month separately (0.25-inch strikes) instead of
                        on the two-month total
    S4 binning          only the strikes Kalshi lists (whole inches, usually 1-7)
    S5 liquidity        at most the depth on today's order book at a sensible price
    S6 capital          total spend capped at the farm's PRF producer premium
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from agri_hedge.config import PROCESSED
from agri_hedge.hedge_builder import (FAIR_WINDOW, NORMAL_YEARS, HedgeProblem, grid_interval_index,
                                      grid_monthly, station_rain, window_target_per_dollar)
from agri_hedge.pricing import leg_probability, no_asks_from_yes_bids, no_pays
from agri_hedge.prf import payment_calculation_factor, trigger_grid_index

SENSIBLE_TOL = 0.10   # doc 09: a "sensible" price is at most 10 cents above fair value


def _fair(col: np.ndarray, years: np.ndarray) -> float:
    m = (years >= FAIR_WINDOW[0]) & (years <= FAIR_WINDOW[1]) & ~np.isnan(col)
    return float(np.mean(col[m])) if m.any() else float("nan")


def dedupe(X: np.ndarray, labels: list, q) -> tuple[np.ndarray, list, np.ndarray]:
    """Drop instruments whose payoff vector repeats an earlier one, or that never pay / always pay
    identically to another. Keeps the first (lowest strike) of each group."""
    q = np.asarray(q, float)
    keep, seen = [], set()
    for j in range(X.shape[1]):
        key = tuple(np.nan_to_num(X[:, j], nan=-1).round(9))
        if key in seen:
            continue
        seen.add(key)
        keep.append(j)
    return X[:, keep], [labels[j] for j in keep], q[keep]


def station_grid_index_cols(p: HedgeProblem, station_grid_id: int):
    """S1: one 'ideal' contract per window paying the PRF factor on the station's grid."""
    cols, labels, q = [], [], []
    for w in p.request.windows:
        c = window_target_per_dollar(station_grid_id, w, p.request.coverage, p.years)
        cols.append(c)
        labels.append(("station_grid_index", w.label))
        q.append(_fair(c, p.years))
    return np.column_stack(cols), labels, np.array(q)


def station_gauge_index_cols(p: HedgeProblem):
    """S2: one 'ideal' contract per window paying the PRF factor on the station gauge's own index."""
    rain = station_rain(p.station["station_key"]).reindex(p.years)
    trig = float(trigger_grid_index(p.request.coverage))
    full = station_rain(p.station["station_key"])
    cols, labels, q = [], [], []
    for w in p.request.windows:
        tot = rain[list(w.months)].sum(axis=1, min_count=len(w.months)).to_numpy(float)
        ftot = full[list(w.months)].sum(axis=1, min_count=len(w.months))
        normal = ftot[(ftot.index >= NORMAL_YEARS[0]) & (ftot.index <= NORMAL_YEARS[1])].mean()
        idx = 100.0 * tot / normal
        c = np.where(np.isnan(idx), np.nan, np.asarray(payment_calculation_factor(idx, trig, decimals=None), float))
        cols.append(c)
        labels.append(("station_gauge_index", w.label))
        q.append(_fair(c, p.years))
    return np.column_stack(cols), labels, np.array(q)


def monthly_ladder_cols(p: HedgeProblem, strikes) -> tuple:
    """S3/S4 and proposal P1: NO contracts on each month at the given strikes (deduplicated)."""
    rain = station_rain(p.station["station_key"])
    r = rain.reindex(p.years)
    months = sorted({m for w in p.request.windows for m in w.months})
    cols, labels, q = [], [], []
    for m in months:
        ks = strikes(m) if callable(strikes) else strikes
        for k in ks:
            cols.append(no_pays(r[m].to_numpy(), k))
            labels.append((m, float(k)))
            q.append(leg_probability(rain, m, k, FAIR_WINDOW))
    return dedupe(np.column_stack(cols), labels, q)


def window_total_ladder_cols(p: HedgeProblem, step: float, max_in: float = 30.0) -> tuple:
    """Proposal P2/P3: NO contracts on the station's whole-window rain total ('two-month rain
    below K inches'), strikes every `step` inches."""
    rain = station_rain(p.station["station_key"])
    r = rain.reindex(p.years)
    cols, labels, q = [], [], []
    for w in p.request.windows:
        tot = r[list(w.months)].sum(axis=1, min_count=len(w.months)).to_numpy(float)
        ftot = rain[list(w.months)].sum(axis=1, min_count=len(w.months))
        fw = ftot[(ftot.index >= FAIR_WINDOW[0]) & (ftot.index <= FAIR_WINDOW[1])].dropna().to_numpy()
        for k in np.arange(step, max_in + 1e-9, step):
            cols.append(no_pays(tot, k))
            labels.append((w.label, float(round(k, 2))))
            q.append(float(np.mean(fw <= k + 1e-9)) if len(fw) else np.nan)
    return dedupe(np.column_stack(cols), labels, q)


def grid_index_ladder_cols(p: HedgeProblem, step: float = 10.0) -> tuple:
    """Proposal P4/P5: binary contracts on the farm grid's own PRF index ('index at or below K'),
    K every `step` points from `step` to the trigger. Settles on the same NOAA data as PRF."""
    gid = p.grid_id
    cols, labels, q = [], [], []
    trig = 100.0 * p.request.coverage
    for w in p.request.windows:
        if w.prf_interval:
            idx = grid_interval_index(gid)[w.prf_interval].reindex(p.years).to_numpy(float)
        else:
            gm = grid_monthly(gid)
            tot = gm[list(w.months)].sum(axis=1, min_count=len(w.months))
            base = tot[(tot.index >= NORMAL_YEARS[0]) & (tot.index <= NORMAL_YEARS[1])].mean()
            idx = (100.0 * tot / base).reindex(p.years).to_numpy(float)
        for k in np.arange(step, trig + 1e-9, step):
            c = np.where(np.isnan(idx), np.nan, (idx < k).astype(float))
            cols.append(c)
            labels.append((w.label, float(k)))
            q.append(_fair(c, p.years))
    return dedupe(np.column_stack(cols), labels, q)


# ---------------------------------------------------------------------------------------------
# Order-book depth (liquidity step)
# ---------------------------------------------------------------------------------------------

def book_depth_by_strike(series: str, station_key: str, path=None, month_of_book: int = 11) -> dict:
    """{strike: NO contracts offered within SENSIBLE_TOL of fair value} from the latest snapshot.

    Only one month (Nov 2026) is listed per series, so its per-strike depth stands in for every
    month (an assumption: real depth varies by month and over the life of a market).
    """
    ob = pd.read_csv(path or PROCESSED / "kalshi_rain_orderbook_summary.csv")
    ob = ob[(ob["series_ticker"] == series) & (ob["contract_month"].astype(str).str[5:7].astype(int) == month_of_book)]
    rain = station_rain(station_key)
    out = {}
    for _, r in ob.iterrows():
        k = float(r["strike"])
        fair = leg_probability(rain, month_of_book, k, FAIR_WINDOW)
        asks = no_asks_from_yes_bids(json.loads(r["yes_bids"]))
        out[k] = float(sum(s for pr, s in asks if pr <= fair + SENSIBLE_TOL + 1e-12))
    return out, str(ob["snapshot_utc"].iloc[0]) if len(ob) else ""
