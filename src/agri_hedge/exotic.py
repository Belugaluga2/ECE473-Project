"""Exotic insurance payoffs built from Kalshi monthly-rain ladders (doc 23).

Docs 15-22 hedge one payoff shape: PRF's linear factor max(0, (T - I) / T). A farmer's loss is not
linear in rain (doc 13: dry hurts more than wet helps, so loss is convex in the shortfall), and an
insurer can write any shape it likes. This module defines a menu of payoff shapes, works out which
portfolio of binary contracts replicates each one, and measures what is lost at every step from
the farm's own rain to an order that fills on today's book.

Payoff shapes (per $1 of maximum payout, on an index I with 100 = normal, trigger T = 100 x coverage,
shortfall s = max(0, (T - I) / T), so s = 1 is a total loss of the window's rain):

    linear       s                              PRF (the baseline)
    layered      0.5 s up to s = 0.5, then slope 1.5     reinsurance-style escalator (convex)
    convex2      s^2                            quadratic: pays extra for worse events
    exponential  (e^{4s} - 1) / (e^4 - 1)       catastrophe cover: almost nothing until deep drought
    tiers        0.25 below T-15, 0.5 below T-35, 1 below T-55   step-up fixed payments
    capped       min(1, 2s)                     stop-loss: full payment at half the shortfall (concave)
    both_tails   s + min(1, max(0, (I - 130) / 100))   drought and excess rain in one contract
    loss         the farm's doc-13 response curve e (x + g x^2), x = I/100 - 1, above a deductible
                 equal to the loss at the trigger, scaled to 1 at I = 0 (convex when g < 0)
    persistence  (s + 0.5 x [every month of the window below its own trigger]) / 1.5
                 a bonus for a drought that lasts: the one shape here that is not a function of the
                 window index alone, and so is not spanned by monthly ladders (see below)

Spanning (Ross 1976; Breeden and Litzenberger 1978 for digitals)
----------------------------------------------------------------
A ladder of binaries "rain above K_j" at strikes K_1 < ... < K_m splits rain into m + 1 bins. A
NO at K_j pays on every bin at or below K_j, a YES on every bin above it. Any step function on the
bins with values s_0, ..., s_m can be written

    s(R) = c + sum_j v_j NO_j + sum_j w_j YES_j,     v_j = max(0, s_{j-1} - s_j), w_j = max(0, s_j - s_{j-1}),
    c = s_m - sum_j w_j.

All weights are long positions. The cash term c is zero whenever the payoff is zero at normal rain and
quasi-convex (falls, then rises, or just one of the two), which covers every insurance shape above.
So on the exchange's own settlement variable (the station's monthly total) every single-month shape
is spanned exactly by today's contracts, up to the bin width (the "binning" error: a smooth shape
can only be matched by its average within each whole-inch bin). What is *not* spanned by monthly
ladders is anything non-additive across months: a payoff on the two-month total, or one that pays
extra when both months are dry. Those need two-month contracts (doc 17, P2).

Who bears the basis risk
------------------------
If the contract settles on the station ("exchange-settled"), the issuer's hedge is exact and the
farmer bears the station-vs-farm mismatch. If it settles on the farm's grid ("farm-settled", like
PRF), the issuer bears it and must hold capital against the shortfall. Both are the same number
measured here as the hedge effectiveness at step S4 (Kalshi strikes); the capital a farm-settled
issuer needs is `shortfall_capital`.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

import numpy as np
import pandas as pd

from agri_hedge.config import PROCESSED
from agri_hedge.error_budget import SENSIBLE_TOL, dedupe
from agri_hedge.hedge_builder import (FAIR_WINDOW, NORMAL_YEARS, HedgeProblem, Window, grid_monthly, station_rain,
                                      window_index)
from agri_hedge.loss_model import production_response
from agri_hedge.pricing import (DEFAULT_LOCKUP_DAYS, DEFAULT_TBILL_RATE, capital_cost, leg_probability,
                                no_asks_from_yes_bids, no_pays, walk_no_book)

SHAPES = {
    "linear": "Linear (PRF)",
    "layered": "Layered escalator",
    "convex2": "Quadratic (convex)",
    "exponential": "Exponential (catastrophe)",
    "tiers": "Step-up tiers",
    "capped": "Capped (stop-loss)",
    "both_tails": "Drought + excess rain",
    "loss": "Farm loss curve (doc 13)",
    "persistence": "Persistent-drought bonus",
}
DROUGHT_SHAPES = ("linear", "layered", "convex2", "exponential", "tiers", "capped", "loss", "persistence")
CONVEX_SHAPES = ("layered", "convex2", "exponential", "loss")
EXP_A = 4.0
TIER_OFFSETS = ((15.0, 0.25), (35.0, 0.25), (55.0, 0.50))   # (points below trigger, extra payment)
WET_START, WET_SPAN = 130.0, 100.0
PERSISTENCE_BONUS = 0.5


# ---------------------------------------------------------------------------------------------
# Payoff shapes
# ---------------------------------------------------------------------------------------------

def shortfall(index, coverage: float) -> np.ndarray:
    """s = max(0, (T - I) / T) with T = 100 x coverage, in [0, 1]; NaN index stays NaN."""
    idx = np.asarray(index, dtype=float)
    T = 100.0 * float(coverage)
    with np.errstate(invalid="ignore"):
        s = np.clip((T - idx) / T, 0.0, 1.0)
    return np.where(np.isnan(idx), np.nan, s)


def wet_excess(index, start: float = WET_START, span: float = WET_SPAN) -> np.ndarray:
    idx = np.asarray(index, dtype=float)
    with np.errstate(invalid="ignore"):
        w = np.clip((idx - start) / span, 0.0, 1.0)
    return np.where(np.isnan(idx), np.nan, w)


def loss_curve(index, elasticity: float, curvature: float) -> np.ndarray:
    """Doc-13 loss per $1 of normal value: max(0, -e (x + g x^2)), x = I / 100 - 1 (saturated, floored)."""
    idx = np.asarray(index, dtype=float)
    x = np.where(np.isnan(idx), 0.0, idx / 100.0 - 1.0)
    dp = np.asarray(production_response(x, elasticity, curvature), dtype=float)
    out = np.maximum(0.0, -dp)
    return np.where(np.isnan(idx), np.nan, out)


def payoff(shape: str, index, coverage: float, loss_params: tuple[float, float] | None = None) -> np.ndarray:
    """Payoff per $1 of maximum payout for `shape` at index values `index` (100 = normal).

    `loss_params` = (elasticity, curvature) for the "loss" shape.
    """
    idx = np.asarray(index, dtype=float)
    T = 100.0 * float(coverage)
    s = shortfall(idx, coverage)
    if shape == "linear":
        f = s
    elif shape == "layered":
        f = np.where(s <= 0.5, 0.5 * s, 0.25 + 1.5 * (s - 0.5))
    elif shape == "convex2":
        f = s ** 2
    elif shape == "exponential":
        f = np.expm1(EXP_A * s) / np.expm1(EXP_A)
    elif shape == "tiers":
        f = np.zeros_like(s)
        with np.errstate(invalid="ignore"):
            for off, pay in TIER_OFFSETS:
                f = f + pay * (idx < T - off)
    elif shape == "capped":
        f = np.minimum(1.0, 2.0 * s)
    elif shape == "both_tails":
        f = s + wet_excess(idx)
    elif shape == "loss":
        if loss_params is None:
            raise ValueError("the 'loss' shape needs loss_params=(elasticity, curvature)")
        e, g = loss_params
        L = loss_curve(idx, e, g)
        L_T = float(loss_curve(np.array([T]), e, g)[0])
        L_0 = float(loss_curve(np.array([0.0]), e, g)[0])
        if L_0 - L_T <= 0:
            raise ValueError("loss curve does not rise between the trigger and a total loss")
        f = np.maximum(0.0, L - L_T) / (L_0 - L_T)
    elif shape == "persistence":
        raise ValueError("the 'persistence' shape needs monthly indices: use persistence_payoff()")
    else:
        raise ValueError(f"unknown shape {shape!r}; choose from {sorted(SHAPES)}")
    return np.where(np.isnan(idx), np.nan, np.asarray(f, dtype=float))


def persistence_payoff(window_index_values, month_index_values: list, coverage: float) -> np.ndarray:
    """(s + bonus x [every month of the window is below the trigger]) / (1 + bonus), per $1 of max payout."""
    idx = np.asarray(window_index_values, dtype=float)
    T = 100.0 * float(coverage)
    s = shortfall(idx, coverage)
    both = np.ones_like(s, dtype=bool)
    with np.errstate(invalid="ignore"):
        for mi in month_index_values:
            both &= np.asarray(mi, dtype=float) < T
    f = (s + PERSISTENCE_BONUS * both) / (1.0 + PERSISTENCE_BONUS)
    bad = np.isnan(idx) | np.any([np.isnan(np.asarray(mi, float)) for mi in month_index_values], axis=0)
    return np.where(bad, np.nan, f)


def grid_month_index(grid_id: int, month: int, years, source: str = "ncei") -> np.ndarray:
    """A grid's single-month rain index 100 x rain / normal (NORMAL_YEARS mean), by year."""
    col = grid_monthly(int(grid_id), source)[int(month)]
    base = col[(col.index >= NORMAL_YEARS[0]) & (col.index <= NORMAL_YEARS[1])].mean()
    return (100.0 * col / base).reindex(years).to_numpy(float)


def gauge_month_index(station_key: str, month: int, years) -> np.ndarray:
    """The station gauge's single-month rain index 100 x rain / normal, by year."""
    col = station_rain(station_key)[int(month)]
    base = col[(col.index >= NORMAL_YEARS[0]) & (col.index <= NORMAL_YEARS[1])].mean()
    return (100.0 * col / base).reindex(years).to_numpy(float)


def shape_curve(shape: str, coverage: float = 0.9, loss_params=None, n: int = 251) -> pd.DataFrame:
    """The shape evaluated on an index grid 0..250 (for figures and tables)."""
    idx = np.linspace(0.0, 250.0, n)
    return pd.DataFrame({"index": idx, "payoff": payoff(shape, idx, coverage, loss_params)})


def fair_premium(y_per_dollar) -> float:
    """Expected payoff per $1 of maximum payout (the actuarially fair premium rate)."""
    return float(np.nanmean(np.asarray(y_per_dollar, dtype=float)))


# ---------------------------------------------------------------------------------------------
# Spanning: step functions on the ladder's bins
# ---------------------------------------------------------------------------------------------

def rain_bins(rain, strikes) -> np.ndarray:
    """Bin index per observation: 0 for rain <= K_1, j for K_j < rain <= K_{j+1}, m for rain > K_m; -1 for NaN."""
    r = np.asarray(rain, dtype=float)
    ks = np.asarray(sorted(float(k) for k in strikes), dtype=float)
    b = np.digitize(np.nan_to_num(r, nan=-1.0), ks + 1e-9, right=True)
    return np.where(np.isnan(r), -1, b)


def binned_values(f_values, rain, strikes, shape_fn=None) -> np.ndarray:
    """L2-best step approximation of a payoff: its mean within each rain bin (m + 1 values).

    Bins with no observed year are filled with `shape_fn(rain)` at the bin's midpoint (the top bin:
    half an inch above its lower edge) when a shape function is given, so the step function is the
    shape itself where there are no data. Without `shape_fn`, empty bins borrow the nearest lower
    non-empty bin's value (or the first non-empty bin above).
    """
    f = np.asarray(f_values, dtype=float)
    ks = np.asarray(sorted(float(k) for k in strikes), dtype=float)
    b = rain_bins(rain, ks)
    m = len(ks)
    vals = np.full(m + 1, np.nan)
    for j in range(m + 1):
        sel = (b == j) & ~np.isnan(f)
        if sel.any():
            vals[j] = float(f[sel].mean())
    if shape_fn is not None:
        edges = np.concatenate([[0.0], ks, [ks[-1] + 1.0]]) if m else np.array([0.0, 1.0])
        for j in range(m + 1):
            if np.isnan(vals[j]):
                vals[j] = float(shape_fn(0.5 * (edges[j] + edges[j + 1])))
        return np.where(np.isnan(vals), 0.0, vals)
    if np.isnan(vals).all():
        return np.zeros(m + 1)
    last = np.nan
    for j in range(m + 1):
        if np.isnan(vals[j]):
            vals[j] = last
        else:
            last = vals[j]
    first = vals[~np.isnan(vals)][0]
    return np.where(np.isnan(vals), first, vals)


@dataclass
class SpanPortfolio:
    strikes: np.ndarray
    no_weights: np.ndarray     # long NO at each strike (drop in the step function there)
    yes_weights: np.ndarray    # long YES at each strike (rise there)
    cash: float                # riskless payoff needed (0 for quasi-convex shapes that are 0 at normal)
    values: np.ndarray         # the step values replicated

    def payout(self, rain) -> np.ndarray:
        r = np.asarray(rain, dtype=float)
        out = np.full(r.shape, self.cash, dtype=float)
        for k, v, w in zip(self.strikes, self.no_weights, self.yes_weights):
            no = no_pays(r, k)
            out = out + v * no + w * (1.0 - no)
        return np.where(np.isnan(r), np.nan, out)

    @property
    def contracts_per_dollar(self) -> float:
        return float(self.no_weights.sum() + self.yes_weights.sum())


def span_step(values, strikes) -> SpanPortfolio:
    """Long-only NO / YES weights that replicate a step function on the ladder's bins exactly.

    `values` has one entry per bin (len(strikes) + 1). The cash term is s_m - sum(rises); it is 0
    for every payoff that is zero at normal rain and quasi-convex (see module docstring).
    """
    s = np.asarray(values, dtype=float)
    ks = np.asarray(sorted(float(k) for k in strikes), dtype=float)
    if len(s) != len(ks) + 1:
        raise ValueError("need one step value per bin: len(strikes) + 1")
    d = s[:-1] - s[1:]
    v = np.maximum(0.0, d) + 0.0
    w = np.maximum(0.0, -d) + 0.0
    c = float(s[-1] - w.sum())
    return SpanPortfolio(ks, v, w, c, s.copy())


def is_quasi_convex(values, tol: float = 1e-12) -> bool:
    """True if the step values fall (weakly) and then rise (weakly): at most one direction change."""
    d = np.diff(np.asarray(values, dtype=float))
    d = d[np.abs(d) > tol]
    sign = np.sign(d)
    return bool(len(sign) == 0 or np.all(np.diff(sign) >= 0))


# ---------------------------------------------------------------------------------------------
# Instruments for the error waterfall, generic in the payoff shape
# ---------------------------------------------------------------------------------------------

def shape_target(p: HedgeProblem, shape: str, loss_params=None, source: str | None = None) -> np.ndarray:
    """Dollars per year: sum over windows of share x protection x payoff(shape, grid window index)."""
    req = p.request
    src = source or req.index
    y = np.zeros(len(p.years))
    for w in req.windows:
        idx = window_index(p.grid_id, w, p.years, src)
        if shape == "persistence":
            f = persistence_payoff(idx, [grid_month_index(p.grid_id, m, p.years, src) for m in w.months], req.coverage)
        else:
            f = payoff(shape, idx, req.coverage, loss_params)
        y = y + w.share * req.protection * f
    return y


def _gauge_window_index(station_key: str, w: Window, years) -> np.ndarray:
    full = station_rain(station_key)
    tot_all = full[list(w.months)].sum(axis=1, min_count=len(w.months))
    normal = tot_all[(tot_all.index >= NORMAL_YEARS[0]) & (tot_all.index <= NORMAL_YEARS[1])].mean()
    return (100.0 * tot_all / normal).reindex(years).to_numpy(float)


def ideal_index_cols(p: HedgeProblem, shape: str, where: str, station_grid_id: int | None = None,
                     loss_params=None):
    """One idealized contract per window paying the shape on a station-side index.

    where = "station_grid": the shape on the station's own PRF grid (geography only);
    where = "station_gauge": the shape on the gauge's window index 100 x total / normal (adds settlement source).
    """
    req = p.request
    cols, labels, q = [], [], []
    for w in req.windows:
        if where == "station_grid":
            if station_grid_id is None:
                raise ValueError("station_grid_id is needed for where='station_grid'")
            idx = window_index(int(station_grid_id), w, p.years, req.index)
            months = [grid_month_index(int(station_grid_id), m, p.years, req.index) for m in w.months]
        elif where == "station_gauge":
            idx = _gauge_window_index(p.station["station_key"], w, p.years)
            months = [gauge_month_index(p.station["station_key"], m, p.years) for m in w.months]
        else:
            raise ValueError("where must be 'station_grid' or 'station_gauge'")
        if shape == "persistence":
            c = persistence_payoff(idx, months, req.coverage)
        else:
            c = payoff(shape, idx, req.coverage, loss_params)
        cols.append(c)
        labels.append((where, w.label))
        m = (p.years >= FAIR_WINDOW[0]) & (p.years <= FAIR_WINDOW[1]) & ~np.isnan(c)
        q.append(float(np.mean(c[m])) if m.any() else np.nan)
    return np.column_stack(cols), labels, np.asarray(q, float)


def ladder_cols(p: HedgeProblem, strikes, sides=("NO",)):
    """NO (and optionally YES) contracts on each calendar month of the request at `strikes`.

    `strikes` is a sequence or a callable month -> sequence. Labels are (month, strike, side).
    Duplicate payoff columns are dropped.
    """
    rain_all = station_rain(p.station["station_key"])
    r = rain_all.reindex(p.years)
    months = sorted({m for w in p.request.windows for m in w.months})
    cols, labels, q = [], [], []
    for m in months:
        ks = strikes(m) if callable(strikes) else strikes
        for k in ks:
            no = no_pays(r[m].to_numpy(), k)
            qn = leg_probability(rain_all, m, k, FAIR_WINDOW)
            if "NO" in sides:
                cols.append(no)
                labels.append((m, float(k), "NO"))
                q.append(qn)
            if "YES" in sides:
                cols.append(np.where(np.isnan(no), np.nan, 1.0 - no))
                labels.append((m, float(k), "YES"))
                q.append(1.0 - qn)
    return dedupe(np.column_stack(cols), labels, q)


def kalshi_strikes_for(p: HedgeProblem):
    """month -> the strikes the problem already uses (Kalshi's listed ladder for that month)."""
    by_month: dict[int, list] = {}
    for m, k in p.legs:
        by_month.setdefault(int(m), []).append(float(k))
    return lambda m: tuple(sorted(set(by_month.get(int(m), ()))))


def combo_cols(p: HedgeProblem, strikes):
    """Proposed 'both months dry' contracts: pays $1 iff month 1 rain <= k1 AND month 2 rain <= k2.

    One column per pair of strikes for each two-month window (a product of two NO payoffs, which no
    long-only sum of monthly contracts can reproduce). Labels are (window, k1, k2, "COMBO").
    """
    rain_all = station_rain(p.station["station_key"])
    r = rain_all.reindex(p.years)
    cols, labels, q = [], [], []
    fw = (rain_all.index >= FAIR_WINDOW[0]) & (rain_all.index <= FAIR_WINDOW[1])
    for w in p.request.windows:
        if len(w.months) != 2:
            continue
        m1, m2 = w.months
        k1s = strikes(m1) if callable(strikes) else strikes
        k2s = strikes(m2) if callable(strikes) else strikes
        for k1 in k1s:
            for k2 in k2s:
                c = no_pays(r[m1].to_numpy(), k1) * no_pays(r[m2].to_numpy(), k2)
                full = no_pays(rain_all.loc[fw, m1].to_numpy(), k1) * no_pays(rain_all.loc[fw, m2].to_numpy(), k2)
                cols.append(c)
                labels.append((w.label, float(k1), float(k2), "COMBO"))
                q.append(float(np.nanmean(full)) if np.isfinite(full).any() else np.nan)
    if not cols:
        return np.zeros((len(p.years), 0)), [], np.zeros(0)
    return dedupe(np.column_stack(cols), labels, q)


# ---------------------------------------------------------------------------------------------
# Order books: depth by side, executable portfolios
# ---------------------------------------------------------------------------------------------

def load_book(series: str, path=None, contract_month: str | None = None) -> pd.DataFrame:
    """Rows of an order-book snapshot for one series (latest saved snapshot by default)."""
    ob = pd.read_csv(path or PROCESSED / "kalshi_rain_orderbook_summary.csv")
    ob = ob[ob["series_ticker"] == series]
    if contract_month:
        ob = ob[ob["contract_month"].astype(str) == contract_month]
    return ob.reset_index(drop=True)


def books_by_strike(ob: pd.DataFrame) -> dict:
    """{strike: {"ticker", "yes_bids", "no_bids"}} from snapshot rows (for `execute_portfolio`)."""
    return {float(r["strike"]): {"ticker": r["ticker"], "yes_bids": json.loads(r["yes_bids"]),
                                 "no_bids": json.loads(r["no_bids"])} for _, r in ob.iterrows()}


def book_depth_by_side(series: str, station_key: str, side: str = "NO", path=None,
                       month_of_book: int = 11) -> tuple[dict, str]:
    """{strike: contracts offered on `side` within SENSIBLE_TOL of fair value} from a snapshot.

    NO offers come from resting YES bids; YES offers from resting NO bids. One month (Nov 2026) is
    listed per series, so its depth stands in for every month (the doc 16 / 22 assumption).
    """
    ob = load_book(series, path)
    ob = ob[ob["contract_month"].astype(str).str[5:7].astype(int) == month_of_book]
    rain = station_rain(station_key)
    out = {}
    for _, r in ob.iterrows():
        k = float(r["strike"])
        qn = leg_probability(rain, month_of_book, k, FAIR_WINDOW)
        if side == "NO":
            asks, fair = no_asks_from_yes_bids(json.loads(r["yes_bids"])), qn
        else:
            asks, fair = no_asks_from_yes_bids(json.loads(r["no_bids"])), 1.0 - qn
        out[k] = float(sum(s for pr, s in asks if pr <= fair + SENSIBLE_TOL + 1e-12))
    return out, (str(ob["snapshot_utc"].iloc[0]) if len(ob) else "")


def caps_for(labels, depth_no: dict, depth_yes: dict | None = None) -> list[float]:
    """Capacity per ladder column from per-strike depth on each side."""
    caps = []
    for lab in labels:
        if len(lab) == 3:
            _, k, side = lab
        elif len(lab) == 2:
            _, k = lab
            side = "NO"
        else:
            caps.append(np.inf)          # proposed contracts have no book yet
            continue
        d = depth_no if side == "NO" else (depth_yes or {})
        caps.append(float(d.get(float(k), 0.0)))
    return caps


def execute_portfolio(port: SpanPortfolio, max_payout: float, books: dict, fair_no: dict,
                      rate: float = DEFAULT_TBILL_RATE, days: float = DEFAULT_LOCKUP_DAYS,
                      sensible_tol: float = SENSIBLE_TOL) -> pd.DataFrame:
    """Fill an exact-span portfolio against a live or saved book, leg by leg.

    books: {strike: {"yes_bids": [...], "no_bids": [...], "ticker": ...}}; fair_no: {strike: NO probability}.
    Each leg is bought cheapest-first up to `sensible_tol` above fair value. Returns one row per leg with
    contracts wanted and filled, fair premium, premium paid, spread cost (paid minus fair), fee, capital
    cost, and the unfilled contracts.
    """
    rows = []
    for k, v, w in zip(port.strikes, port.no_weights, port.yes_weights):
        for side, wt in (("NO", v), ("YES", w)):
            n = wt * max_payout
            if n <= 1e-9:
                continue
            b = books.get(float(k), {})
            fq = fair_no.get(float(k), np.nan)
            fair = fq if side == "NO" else 1.0 - fq
            levels = b.get("yes_bids" if side == "NO" else "no_bids", [])
            fill = walk_no_book(levels, n, max_price=(fair + sensible_tol) if np.isfinite(fair) else None)
            filled, paid, fee = fill["filled"], fill["cost_usd"], fill["fee_usd"]
            cap = float(capital_cost(paid + fee, rate, days))
            rows.append({"strike_in": float(k), "side": side, "ticker": b.get("ticker"),
                         "contracts_wanted": float(n), "contracts_filled": float(filled),
                         "fair_price": float(fair), "vwap": fill["vwap"],
                         "premium_fair_usd": float(filled * fair) if np.isfinite(fair) else np.nan,
                         "premium_paid_usd": float(paid),
                         "spread_cost_usd": float(paid - filled * fair) if np.isfinite(fair) else np.nan,
                         "fee_usd": float(fee), "capital_usd": cap, "all_in_usd": float(paid + fee + cap),
                         "unfilled": float(n - filled), "depth_sensible": fill["depth_available"]})
    return pd.DataFrame(rows)


def execution_summary(ex: pd.DataFrame, max_payout: float, expected_per_dollar: float) -> dict:
    """Totals of `execute_portfolio` plus cost per $1 of expected payout and the share filled."""
    if ex.empty:
        return {"contracts_wanted": 0.0, "contracts_filled": 0.0, "fill_share": np.nan}
    want, got = ex["contracts_wanted"].sum(), ex["contracts_filled"].sum()
    paid, fair = ex["premium_paid_usd"].sum(), ex["premium_fair_usd"].sum()
    fee, cap = ex["fee_usd"].sum(), ex["capital_usd"].sum()
    share = got / want if want > 0 else np.nan
    exp_filled = expected_per_dollar * max_payout * share   # expected payout of the filled fraction
    return {"contracts_wanted": float(want), "contracts_filled": float(got), "fill_share": float(share),
            "premium_fair_usd": float(fair), "premium_paid_usd": float(paid), "spread_cost_usd": float(paid - fair),
            "fee_usd": float(fee), "capital_usd": float(cap), "all_in_usd": float(paid + fee + cap),
            "cost_per_dollar_expected": float((paid + fee + cap) / exp_filled) if exp_filled > 0 else np.nan,
            "max_payout_filled_usd": float(max_payout * share)}


# ---------------------------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------------------------

def tail_capture(y, h, share: float = 0.10) -> float:
    """Hedge payout in the worst `share` of years (by target) divided by the target payout in those years."""
    y = np.asarray(y, float)
    h = np.asarray(h, float)
    ok = ~np.isnan(y) & ~np.isnan(h)
    y, h = y[ok], h[ok]
    if len(y) == 0:
        return np.nan
    k = max(1, int(np.ceil(share * len(y))))
    top = np.argsort(-y)[:k]
    tot = y[top].sum()
    return float(h[top].sum() / tot) if tot > 0 else np.nan


def tail_concentration(y, share: float = 0.10) -> float:
    """Share of all target dollars paid in the worst `share` of years (how 'catastrophe-shaped' a payoff is)."""
    y = np.asarray(y, float)
    y = y[~np.isnan(y)]
    if len(y) == 0 or y.sum() <= 0:
        return np.nan
    k = max(1, int(np.ceil(share * len(y))))
    return float(np.sort(y)[::-1][:k].sum() / y.sum())


def shortfall_capital(y, h, scale: float, pct: float = 0.95) -> float:
    """The `pct` quantile of max(0, target - hedge) per $1 of `scale`: capital a farm-settled issuer needs."""
    y = np.asarray(y, float)
    h = np.asarray(h, float)
    ok = ~np.isnan(y) & ~np.isnan(h)
    if not ok.any():
        return np.nan
    gap = np.maximum(0.0, y[ok] - h[ok]) / float(scale)
    return float(np.quantile(gap, pct))


def convexity_ratio(values) -> float:
    """For a non-increasing step function on rain bins: the first drop over the mean of the next two.

    > 1 means the payout rises faster as rain falls towards zero (convex in the shortfall);
    < 1 means the opposite (concave). NaN if there are not enough drops to compare.
    """
    s = np.asarray(values, dtype=float)
    d = s[:-1] - s[1:]
    if len(d) < 3 or d[0] <= 0:
        return np.nan
    rest = d[1:3]
    return float(d[0] / rest.mean()) if rest.mean() > 0 else np.inf
