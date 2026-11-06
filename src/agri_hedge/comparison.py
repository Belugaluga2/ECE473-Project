"""Farmer-specific PRF replacement screen, with an untouched temporal holdout.

This builds *approximate* Kalshi hedges, not insurance policies. Model prices are
planning estimates. Only fresh, exact-dated books count toward available orders.
Neither an expected-value discount nor historical tracking proves arbitrage.
"""
from __future__ import annotations

import calendar
import math
from dataclasses import replace
from datetime import date, datetime, timezone

import numpy as np
import pandas as pd

from agri_hedge import hedge_builder as hb, optimizer as op
from agri_hedge.pricing import (
    DEFAULT_TBILL_RATE, capital_cost, cost_totals, price_legs, walk_no_book,
)

TRAIN = (1951, 2000)
TEST = (2001, 2025)
HALF_SPREAD = 0.0225
MAX_BOOK_AGE_SECONDS = 120


def _number(value, name):
    try:
        result = float(value)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite number.") from exc
    if not math.isfinite(result) or isinstance(value, bool):
        raise ValueError(f"{name} must be a finite number.")
    return result


def farms() -> list[dict]:
    """Known farm scenarios; premiums are saved actuarial terms, not county averages."""
    return [{"farm_id": f["farm_id"], "county": f["farm"]["county"],
             "acres": f["farm"]["insured_acres"], "protection_usd": f["protection"],
             "producer_premium_usd": f["producer_premium"]}
            for f in hb.load_farm_requests()]


def coverage_metrics(target, payout) -> dict:
    """Dollar shortfalls accompany HE: HE alone ignores constant underpayment."""
    y, h = np.asarray(target, float), np.asarray(payout, float)
    if y.shape != h.shape or y.ndim != 1 or not len(y):
        raise ValueError("Coverage needs equal nonempty payout vectors.")
    if not np.isfinite(y).all() or not np.isfinite(h).all() or (y < 0).any() or (h < 0).any():
        raise ValueError("Payouts must be finite and nonnegative.")
    short = np.maximum(y - h, 0)
    return {"he": op.hedge_effectiveness(y, h),
            "rmse_usd": float(np.sqrt(np.mean((y - h) ** 2))),
            "mean_prf_usd": float(y.mean()), "mean_hedge_usd": float(h.mean()),
            "mean_bias_usd": float((h - y).mean()),
            "payout_recovery": float(np.minimum(y, h).sum() / y.sum()) if y.sum() else None,
            "mean_shortfall_usd": float(short.mean()), "worst_shortfall_usd": float(short.max()),
            "shortfall_years": int((short > 1.0).sum()), "n_years": len(y)}


def fit_portfolios(X, y, years, protection: float) -> dict[str, np.ndarray]:
    """Fit weights and probabilities on training years only, then use whole contracts.

    The second portfolio matches mean training payout before rounding. It does not
    match state-by-state coverage, nor necessarily the mean on unseen years.
    """
    X, y, years = np.asarray(X, float), np.asarray(y, float), np.asarray(years)
    tr = ((years >= TRAIN[0]) & (years <= TRAIN[1]) & np.isfinite(y)
          & np.isfinite(X).all(axis=1))
    if tr.sum() < 20:
        raise ValueError("At least 20 complete training years are required.")
    q = X[tr].mean(axis=0)
    sol = op.solve_penalized(X[tr], y[tr], op.model_tranches(q), scale=protection)
    w = sol.leg_contracts
    mean = float(q @ w)
    if mean <= 0 or y[tr].mean() <= 0:
        raise ValueError("Training data do not support a positive drought hedge.")
    return {"best_fit": np.rint(w).astype(int),
            "equal_mean": np.rint(w * y[tr].mean() / mean).astype(int)}


def _time(value):
    if not value:
        return None
    try:
        t = datetime.fromisoformat(str(value).replace("Z", "+00:00").replace(" UTC", "+00:00"))
        return t.replace(tzinfo=timezone.utc) if t.tzinfo is None else t
    except (TypeError, ValueError):
        return None


def _fresh(book, now):
    stamp = _time(book.get("as_of"))
    close = _time(book.get("close_time"))
    return (book.get("source") == "live" and stamp is not None
            and 0 <= (now - stamp).total_seconds() <= MAX_BOOK_AGE_SECONDS
            and close is not None and close > now)


def price_portfolio(problem, contracts, books, contract_year, now, checked, rate=DEFAULT_TBILL_RATE):
    """Price a complete model hedge and separately walk fresh exact-month books.

    Quotes use a two-day settlement assumption after each calendar month ends.
    Money is assumed prepaid now, so capital cost extends to each maturity.
    Execution fees use the repository's standard retail taker assumption; fee
    schedules must be confirmed before trading. This function never places orders.
    """
    rows, priced_rows = [], []
    filled_total = partial_cost = 0.0
    requested = int(np.sum(contracts))
    all_live = bool(requested)
    for j, n in enumerate(contracts):
        if n <= 0:
            continue
        month, strike = problem.legs[j]
        cm = f"{contract_year}-{month:02d}"
        end = date(contract_year, month, calendar.monthrange(contract_year, month)[1])
        days = max((end - now.date()).days + 2, 0)
        price = float(np.clip(problem.q[j] + HALF_SPREAD, 0.01, 0.99))
        priced = price_legs(pd.DataFrame({"contracts": [n]}), [price], rate=rate, days=days)
        priced_rows.append(priced)
        book = books.get((cm, float(strike)))
        fresh = bool(book and _fresh(book, now))
        all_live &= fresh
        fill = {"filled": 0, "cost_usd": 0, "fee_usd": 0, "vwap": None}
        if fresh:
            # All displayed prices are eligible; slippage is paid level by level.
            # No invented liquidity or fair-value cutoff conceals the actual cost.
            fill = walk_no_book(book["yes_bids"], contracts=int(n))
        outlay = fill["cost_usd"] + fill["fee_usd"]
        fill_cost = float(outlay + capital_cost(outlay, rate=rate, days=days))
        partial_cost += fill_cost
        filled_total += fill["filled"]
        rows.append({"contract_month": cm, "strike_in": strike, "side": "NO", "contracts": int(n),
                     "estimated_price": price, "estimated_cost_usd": float(priced.cost_usd.iloc[0]),
                     "ticker": book.get("ticker") if book else None,
                     "source": "live" if fresh else ("stale/snapshot" if book else
                               "no verified book / estimated" if checked else "not checked / estimated"),
                     "as_of": book.get("as_of") if book else None,
                     "fillable_contracts": float(fill["filled"]), "fill_cost_usd": fill_cost,
                     "days_prepaid": days})
    costs = cost_totals(pd.concat(priced_rows, ignore_index=True)) if priced_rows else {
        "premium_usd": 0., "fee_usd": 0., "capital_usd": 0., "cost_usd": 0.}
    full = all_live and filled_total >= requested - 1e-8
    return costs, rows, {"checked": bool(checked), "all_legs_live": all_live,
                         "fully_fillable": bool(full), "requested_contracts": requested,
                         "fillable_contracts": filled_total,
                         "fill_fraction": filled_total / requested if requested else 0.,
                         "partial_cost_usd": partial_cost,
                         "full_cost_usd": partial_cost if full else None}


def compare(params: dict, live=None, now: datetime | None = None) -> dict:
    """Build and evaluate farmer-specific replacement portfolios without making trades.

    Inputs: farm_id, optional acres, producer_premium_usd (a farmer-supplied
    total quote for those acres), contract_year, price_source='model'|'auto'.
    Saved terms remain a 2026 scenario, even for forward contract dates.
    """
    if not isinstance(params, dict):
        raise ValueError("Supply a JSON object with farm_id.")
    records = {f["farm_id"]: f for f in hb.load_farm_requests()}
    farm_id = params.get("farm_id")
    if not isinstance(farm_id, str) or farm_id not in records:
        raise ValueError("Choose a farm_id from /api/farms.")
    f = records[farm_id]
    fixed_clock = now is not None
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    acres = _number(params.get("acres", f["farm"]["insured_acres"]), "Acres")
    if not math.isfinite(acres) or not 0 < acres <= 1_000_000:
        raise ValueError("Acres must be positive and no more than 1,000,000.")
    ratio = acres / f["farm"]["insured_acres"]
    premium = _number(params.get("producer_premium_usd", f["producer_premium"] * ratio), "PRF premium")
    if not math.isfinite(premium) or premium < 0:
        raise ValueError("PRF producer premium must be finite and nonnegative.")
    year_value = _number(params.get("contract_year", now.year + 1), "Contract year")
    year = int(year_value)
    if float(year_value) != year or not now.year <= year <= now.year + 3:
        raise ValueError("Contract year must be a whole year within the next three years.")
    source = params.get("price_source", "model")
    if source not in ("model", "auto"):
        raise ValueError("price_source must be model or auto.")
    req = replace(f["request"], protection=f["protection"] * ratio)
    if any(date(year, m, 1) <= now.date() for w in req.windows for m in w.months):
        raise ValueError("Every insured month must start in the future; use the next contract year.")
    p = hb.build_problem(req)
    if not np.isfinite(p.q).all():
        raise ValueError("Insufficient rainfall history to estimate contract prices.")
    tr = p.ok & (p.years >= TRAIN[0]) & (p.years <= TRAIN[1])
    te = p.ok & (p.years >= TEST[0]) & (p.years <= TEST[1])
    if te.sum() < 10:
        raise ValueError("At least 10 complete holdout years are required.")
    weights = fit_portfolios(p.X, p.target, p.years, req.protection)
    books = {}
    market_data = {"source": "not checked", "error": None, "books_count": 0,
                   "observed_contract_months": []}
    if source == "auto":
        from agri_hedge.platform import LiveQuotes
        from agri_hedge.kalshi import KalshiClient
        # Bound the request; unavailable data are estimates, never executable.
        live = live or LiveQuotes(client=KalshiClient(timeout=8, max_retries=0))
        books = live.series_books(p.station["series_ticker"])
        market_data = dict(getattr(live, "status", {}).get(p.station["series_ticker"],
                           {"source": "unverified", "error": None, "books_count": len(books)}))
        market_data["observed_contract_months"] = sorted({cm for cm, _ in books})
        if not fixed_clock:
            now = datetime.now(timezone.utc)
    strategies = []
    labels = {"best_fit": "Best training fit", "equal_mean": "Match average training payout"}
    for key, w in weights.items():
        h, y = p.X[te] @ w, p.target[te]
        costs, ticket, execution = price_portfolio(p, w, books, year, now, source == "auto")
        strategies.append({"id": key, "label": labels[key], "cost": costs,
                           "price_gap_usd": premium - costs["cost_usd"],
                           "cost_ratio": costs["cost_usd"] / premium if premium else None,
                           "metrics": coverage_metrics(y, h), "ticket": ticket, "execution": execution,
                           "backtest": [{"year": int(t), "prf_usd": float(a), "hedge_usd": float(b),
                                         "shortfall_usd": float(max(a - b, 0))}
                                        for t, a, b in zip(p.years[te], y, h)]})
    cheaper = strategies[0]["price_gap_usd"] > 0
    reasons = ["Monthly airport rainfall and two-month farm-grid rainfall have different payouts.",
               "Matching an average payout does not match coverage in each weather outcome.",
               "No tradable short position in the farmer's PRF policy is identified; a premium saving alone is not arbitrage."]
    if not strategies[0]["execution"]["fully_fillable"]:
        reasons.append("The complete hedge is not verified fillable from fresh books for the requested contract dates.")
    return {"farm": {"farm_id": farm_id, "county": f["farm"]["county"], "acres": acres,
                     "protection_usd": req.protection, "coverage": req.coverage,
                     "grid_id": p.grid_id, "station": p.station["station_key"], "distance_mi": p.distance_mi,
                     "windows": [{"label": w.label, "share": w.share} for w in req.windows]},
            "prf": {"producer_premium_usd": premium, "total_premium_usd": f["total_premium"] * ratio,
                    "terms_year": 2026, "source": "farmer-supplied producer quote; full premium remains the saved scenario"
                    if "producer_premium_usd" in params else "saved 2026 actuarial scenario, scaled by acres"},
            "contract_year": year, "as_of": now.isoformat(), "market_data": market_data,
            "training": {"start": TRAIN[0], "end": TRAIN[1], "n_years": int(tr.sum())},
            "holdout": {"start": TEST[0], "end": TEST[1], "n_years": int(te.sum())},
            "verdict": {"label": "Cheaper estimated hedge, different coverage" if cheaper else
                        "Estimated hedge costs more than PRF, with different coverage",
                        "arbitrage": False, "same_coverage": False, "reasons": reasons},
            "strategies": strategies,
            "assumptions": [
                "Research scenarios for the listed farms; acre changes keep their location, elections and per-acre terms.",
                "Targets use reconstructed NCEI PRF-style payouts without official dollar rounding, not historical checks or measured crop losses.",
                "Weights and fitting probabilities use 1951–2000 only; 2001–2025 scores are held out. Published index normals and today's strike menu are treated as fixed contract specifications.",
                "Forward planning prices use 1991–2025 climatology plus a 2.25-cent half spread; they are not historical trade prices or weather forecasts.",
                "Costs assume standard retail taker fees, 4.05% annual funding from the quote date to two days after each month, and no interest credit. These are scenario assumptions, not verified current fee/rate quotes.",
                "PRF uses saved 2026 actuarial terms (excluding any administrative fee) unless you enter a producer quote; target-year premiums must be confirmed for identical elections.",
                "Book availability is an observation, not an execution guarantee. Snapshot, stale, closed and wrong-date books never count as available orders.",
                "No policy is issued and no order is submitted. A positive price gap means estimated premium savings, not risk-free profit."
            ]}
