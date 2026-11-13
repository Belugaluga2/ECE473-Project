"""Milestone 2, week 5 (Jack): the platform backend.

`quote(params)` is the one entry point the web app (and the app test, doc 19) calls. Given a farm
location, the months to cover, a coverage level and the dollars of protection, it

1. finds the farm's PRF grid and the nearest Kalshi monthly-rain station with data,
2. builds the target payout and the contract payoffs (`hedge_builder`),
3. prices every contract: from the live Kalshi order book if that market is listed now, else at an
   estimated price (fair value + half the typical spread), clearly flagged,
4. runs the optimizer (`optimizer`) for the efficient frontier and the recommended hedge,
5. returns an order ticket, the backtest, and a PRF benchmark, as plain JSON-ready dicts.

Live prices come from Kalshi's public market-data API (no key) through `LiveQuotes`, which caches
order books for `ttl` seconds and falls back to the latest saved snapshot
(`kalshi_rain_orderbook_summary.csv`) if the API cannot be reached.
"""
from __future__ import annotations

import json
import math
import threading
import time
from datetime import date, datetime, timezone

import numpy as np
import pandas as pd

from agri_hedge import hedge_builder as hb
from agri_hedge import optimizer as op
from agri_hedge.config import PROCESSED
from agri_hedge.pricing import FEE_TICK_RETAIL, taker_fee

HALF_SPREAD = 0.0225           # half the 4.5-cent median contested spread (doc 05)
SENSIBLE_TOL = 0.10            # doc 09: skip book levels more than 10 cents above fair value
#: Doc 09: across the 11 farms PRF costs the producer $0.61 per $1 of expected payout after subsidy
#: and $1.28 before it. Used only to *estimate* a PRF premium where we have no actuarial rates.
PRF_PRODUCER_PER_DOLLAR = 0.61
PRF_FULL_PER_DOLLAR = 1.28
#: Recommended hedge = cheapest frontier point with this share of the best in-sample fit. 0.95 scored
#: best out of sample across 44 farm and single-month cases (median HE 0.49 vs 0.46 at 0.90 and 0.48
#: with no cost limit; doc 21).
KNEE_SHARE = 0.95
#: Automatic station choice: stations up to this many miles farther than the nearest one are
#: compared by out-of-sample fit (doc 19: the nearest station was the worse choice for Tampa).
STATION_SLACK_MI = 25.0
MONTH_CODES = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


# ---------------------------------------------------------------------------------------------
# Live prices
# ---------------------------------------------------------------------------------------------

def contract_month_for(month: int, today: date | None = None) -> str:
    """The contract month ('YYYY-MM') a farmer covering calendar `month` would trade next.

    Cover starts with the next month that has not begun: the current month is already partly
    observed (its price reflects the rain so far, not climatology), so it rolls to next year too.
    """
    t = today or date.today()
    year = t.year if month > t.month else t.year + 1
    return f"{year}-{month:02d}"


def event_ticker(series: str, contract_month: str) -> str:
    y, m = contract_month.split("-")
    return f"{series}-{y[2:]}{MONTH_CODES[int(m) - 1]}"


class LiveQuotes:
    """Order books for open monthly-rain markets, cached per series."""

    def __init__(self, ttl: float = 60.0, client=None, offline: bool = False):
        self.ttl = ttl
        self.offline = offline
        self._client = client
        self._cache: dict = {}
        self._lock = threading.Lock()

    def _kalshi(self):
        if self._client is None:
            from agri_hedge import kalshi
            self._client = kalshi
        return self._client

    def series_books(self, series: str) -> dict:
        """{(contract_month, strike): {'ticker', 'yes_bids', 'source', 'as_of'}} for open markets."""
        now = time.time()
        with self._lock:
            hit = self._cache.get(series)
            if hit and now - hit[0] < self.ttl:
                return hit[1]
        books, source = {}, "live"
        try:
            if self.offline:
                raise RuntimeError("offline mode")
            k = self._kalshi()
            markets = k.list_markets(series_ticker=series, status="open")
            for m in markets:
                if m.get("strike_type") != "greater" or m.get("floor_strike") is None:
                    continue
                cm = k.event_contract_month(m["event_ticker"])
                if not cm:
                    continue
                ob = k.parse_orderbook(k.get_orderbook(m["ticker"]))
                books[(str(cm), float(m["floor_strike"]))] = {
                    "ticker": m["ticker"], "yes_bids": ob["yes_bids"], "source": "live",
                    "as_of": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                    "close_time": m.get("close_time")}
        except Exception as exc:  # network down, API change: fall back to the saved snapshot
            source = f"snapshot ({type(exc).__name__})"
            books = self.snapshot_books(series)
        with self._lock:
            self._cache[series] = (now, books)
        return books

    @staticmethod
    def snapshot_books(series: str) -> dict:
        ob = pd.read_csv(PROCESSED / "kalshi_rain_orderbook_summary.csv")
        ob = ob[ob["series_ticker"] == series]
        return {(str(r["contract_month"]), float(r["strike"])): {
            "ticker": r["ticker"], "yes_bids": [tuple(x) for x in json.loads(r["yes_bids"])],
            "source": "snapshot", "as_of": str(r["snapshot_utc"]), "close_time": None}
            for _, r in ob.iterrows()}


_DEFAULT_LIVE = LiveQuotes()


# ---------------------------------------------------------------------------------------------
# Quote
# ---------------------------------------------------------------------------------------------

def parse_request(params: dict) -> hb.CoverageRequest:
    """Build a CoverageRequest from JSON-style params (see `quote`)."""
    windows = [hb.window_from_label(w["label"], float(w["share"])) for w in params["windows"]]
    if not windows:
        raise ValueError("Pick at least one month or interval to cover.")
    if "protection" in params and params["protection"]:
        prot = float(params["protection"])
    else:
        prot = float(params["acres"]) * float(params["value_per_acre"]) * float(params.get("coverage", 0.9))
    cov = float(params.get("coverage", 0.9))
    if not 0.5 <= cov <= 1.0:
        raise ValueError("Coverage level must be between 50% and 100%.")
    if prot <= 0:
        raise ValueError("Protection must be positive.")
    return hb.CoverageRequest(float(params["lat"]), float(params["lon"]), windows, cov, prot,
                              station_key=params.get("station_key") or None,
                              strikes=params.get("strikes", "kalshi"))


def choose_station(req: hb.CoverageRequest) -> list[dict]:
    """Rank stations within STATION_SLACK_MI of the nearest by out-of-sample fit (best first).

    Each candidate gets the lowest-error hedge at model prices, refit leaving out each year. The
    winner's out-of-sample score is slightly optimistic because it was picked as the best of a few.
    Returns [] when only one station is in range.
    """
    near = hb.nearest_stations(req.lat, req.lon, 4)
    cand = near[near["distance_mi"] <= near["distance_mi"].iloc[0] + STATION_SLACK_MI]
    if len(cand) < 2:
        return []
    out = []
    for _, c in cand.iterrows():
        r = hb.CoverageRequest(req.lat, req.lon, req.windows, req.coverage, req.protection,
                               station_key=c["station_key"], strikes=req.strikes, grid_id=req.grid_id)
        try:
            pc = hb.build_problem(r)
        except (KeyError, ValueError):
            continue
        ok = pc.ok
        if ok.sum() < 30:
            continue
        tr = op.model_tranches(pc.q)
        he = op.hedge_effectiveness(pc.target[ok], op.loyo_payout(pc.X[ok], pc.target[ok], tr, None, req.protection))
        out.append({"station_key": c["station_key"], "series": c["series_ticker"],
                    "distance_mi": round(float(c["distance_mi"]), 1), "he_out_of_sample_lowest_error": round(he, 3),
                    "years": int(ok.sum())})
    return sorted(out, key=lambda d: -d["he_out_of_sample_lowest_error"])


def build_tranches(p: hb.HedgeProblem, books: dict, today: date | None, price_source: str):
    """One list of tranches for the problem's legs, plus a per-leg pricing record."""
    tranches, info = [], []
    for j, (m, k) in enumerate(p.legs):
        cm = contract_month_for(m, today)
        book = books.get((cm, float(k))) if price_source != "model" else None
        rec = {"leg": j, "month": m, "strike_in": k, "contract_month": cm, "q": float(p.q[j]),
               "ticker": f"{event_ticker(p.station['series_ticker'], cm)}-{int(k) if float(k).is_integer() else k}"}
        if book is not None:
            tr = op.book_tranches(j, book["yes_bids"], max_price=float(p.q[j]) + SENSIBLE_TOL)
            rec.update(price_source=book["source"], ticker=book["ticker"], as_of=book["as_of"],
                       best_no_ask=tr[0].price if tr else None,
                       depth_contracts=float(sum(t.capacity for t in tr)))
            tranches += tr
        else:
            price = float(np.clip(p.q[j] + HALF_SPREAD, 0.01, 0.99))
            rec.update(price_source="estimated (not listed yet)" if price_source != "model" else "estimated",
                       best_no_ask=price, depth_contracts=None)
            tranches.append(op.Tranche(j, price, np.inf, "model"))
        info.append(rec)
    return tranches, info


def order_ticket(sol: op.HedgeSolution, info: list) -> list[dict]:
    """Whole-contract orders per leg with limit price, fee and all-in cost."""
    rows = []
    by_leg: dict = {}
    for t, x in zip(sol.tranches, sol.contracts):
        if x > 1e-6:
            by_leg.setdefault(t.leg, []).append((t.price, x))
    for leg, fills in by_leg.items():
        n = sum(x for _, x in fills)
        whole = int(round(n))
        if whole <= 0:
            continue
        cost = sum(p * x for p, x in fills) * whole / n
        limit = max(p for p, _ in fills)
        avg = cost / whole
        fee = float(taker_fee([whole], [avg], tick=FEE_TICK_RETAIL)[0])
        r = info[leg]
        rows.append({"ticker": r["ticker"], "contract_month": r["contract_month"],
                     "side": "NO", "meaning": f"pays $1 per contract if {hb.MONTH_ABBR[r['month'] - 1]} rain "
                                              f"at the station is {r['strike_in']:g} in or less",
                     "contracts": whole, "limit_price": round(float(limit), 2), "avg_price": round(float(avg), 4),
                     "premium_usd": round(float(cost), 2), "fee_usd": round(fee, 2),
                     "price_source": r["price_source"], "fair_probability": round(r["q"], 3)})
    return sorted(rows, key=lambda r: (r["contract_month"], -r["contracts"]))


def quote(params: dict, live: LiveQuotes | None = None, today: date | None = None, loyo: bool = True) -> dict:
    """Price a custom rain hedge.

    params: lat, lon, windows [{label: 'Apr-May' | 'Jul' | 'Jun-Aug', share}], coverage (0.7-0.9),
    protection ($) or acres + value_per_acre, optional station_key, budget ($; omit for the
    recommended 90% knee; 'lowest_error' for no cost limit), price_source ('auto' | 'model').
    """
    t0 = time.time()
    req = parse_request(params)
    choice = choose_station(req) if not req.station_key else []
    if choice:
        req.station_key = choice[0]["station_key"]
    p = hb.build_problem(req)
    live = live or _DEFAULT_LIVE
    price_source = params.get("price_source", "auto")
    books = live.series_books(p.station["series_ticker"]) if price_source != "model" else {}
    tranches, info = build_tranches(p, books, today, price_source)
    ok = p.ok
    X, y = p.X[ok], p.target[ok]
    prot = req.protection
    fr = op.efficient_frontier(X, y, tranches, n_points=13, scale=prot, q=p.q)
    budget = params.get("budget")
    if budget in (None, "", "recommended"):
        b = op.knee_budget(fr, KNEE_SHARE)
        mode = "recommended (cheapest hedge with 95% of the best fit)"
    elif budget == "lowest_error":
        b, mode = None, "lowest error (no cost limit)"
    else:
        b, mode = float(budget), f"budget ${float(budget):,.0f}"
    sol = op.solve_penalized(X, y, tranches, 0.0, prot) if b is None else op.solve_budget(X, y, tranches, b, prot)
    he_in = op.hedge_effectiveness(y, sol.payout)
    he_loyo = op.hedge_effectiveness(y, op.loyo_payout(X, y, tranches, b, prot)) if loyo else None
    ev = float(p.q @ sol.leg_contracts)
    years = p.years[ok]
    tkt = order_ticket(sol, info)
    n_live = sum(1 for r in tkt if r["price_source"] in ("live", "snapshot"))
    # PRF benchmark (only meaningful when every window is a PRF interval)
    prf_ok = all(w.prf_interval for w in req.windows)
    exp_target = float(np.mean(y))
    bench = {"valid_prf_election": prf_ok and len(req.windows) >= 2,
             "expected_payout_usd": exp_target,
             "est_producer_premium_usd": exp_target * PRF_PRODUCER_PER_DOLLAR,
             "est_full_premium_usd": exp_target * PRF_FULL_PER_DOLLAR,
             "note": ("PRF premiums are estimates: expected payout x $0.61 (producer, after subsidy) and x $1.28 "
                      "(full), the 11-farm averages from doc 09. Real rates vary by grid.")}
    worst = int(np.argmax(y - sol.payout))
    live_ref = live_reference(p, books)
    return {
        "request": {"lat": req.lat, "lon": req.lon, "coverage": req.coverage, "protection_usd": prot,
                    "windows": [{"label": w.label, "share": w.share} for w in req.windows]},
        "grid": {"grid_id": p.grid_id, "center": list(p.grid_center)},
        "station": {"key": p.station["station_key"], "series": p.station["series_ticker"],
                    "name": p.station.get("name"), "distance_mi": round(p.distance_mi, 1)},
        "station_choice": choice,
        "alternatives": hb.nearest_stations(req.lat, req.lon, 3)[["station_key", "series_ticker", "distance_mi"]]
                          .round(1).to_dict("records"),
        "mode": mode,
        "hedge": {"cost_usd": round(sol.cost, 2), "expected_payout_usd": round(ev, 2),
                  "cost_per_dollar_expected": round(sol.cost / ev, 3) if ev > 0 else None,
                  "he_in_sample": round(he_in, 3), "he_out_of_sample": None if he_loyo is None else round(he_loyo, 3),
                  "max_payout_usd": round(float(sol.leg_contracts.sum()), 0),
                  "legs_priced_from_order_book": n_live, "legs": len(tkt)},
        "ticket": tkt,
        "frontier": fr[["cost", "he", "rmse", "expected_payout_fair"]].round(4).to_dict("records"),
        "backtest": {"years": years.tolist(), "target_usd": np.round(y, 0).tolist(),
                     "hedge_usd": np.round(sol.payout, 0).tolist(),
                     "worst_year": int(years[worst]), "worst_shortfall_usd": round(float((y - sol.payout)[worst]), 0),
                     "years_target_paid": int((y > 0).sum()),
                     "years_target_paid_hedge_under_half": int(((y > 0.02 * prot) & (sol.payout < 0.5 * y)).sum())},
        "prf_benchmark": bench,
        "legs_pricing": info,
        "live_reference": live_ref,
        "notes": p.notes + [
            "Backtest years 1951-2025; target = PRF-style payout on the NCEI grid index; hedge = NO contracts "
            "on the station's monthly rain.",
            "In-sample hedge effectiveness overstates real performance; the out-of-sample number refits without "
            "each year in turn."],
        "elapsed_s": round(time.time() - t0, 2),
    }


# ---------------------------------------------------------------------------------------------
# PRF Companion: keep the rancher's PRF policy and cover the gaps it leaves
# ---------------------------------------------------------------------------------------------

GOOD_HE = 0.5      # recommend a gap month if its hedge tracks at least this well out of sample
OK_HE = 0.3


def _score(X, y, q, prot, share=KNEE_SHARE):
    ok = ~np.isnan(y) & ~np.isnan(X).any(axis=1)
    X, y = X[ok], y[ok]
    if len(y) < 30 or np.var(y) == 0:
        return None
    tr = op.model_tranches(q)
    fr = op.efficient_frontier(X, y, tr, n_points=13, scale=prot, q=q)
    b = op.knee_budget(fr, share)
    sol = op.solve_budget(X, y, tr, b, prot)
    he = op.hedge_effectiveness(y, op.loyo_payout(X, y, tr, b, prot))
    ev = float(np.asarray(q) @ sol.leg_contracts)
    return {"he_out_of_sample": round(he, 3), "cost_usd": round(sol.cost, 2),
            "expected_payout_usd": round(ev, 2), "cost_per_dollar_expected": round(sol.cost / ev, 3) if ev > 0 else None,
            "target_mean_usd": round(float(y.mean()), 2), "years": int(len(y))}



EXCESS_START, EXCESS_SPAN = 130.0, 100.0
EXCESS_SHARE_OF_PROTECTION = 1.0


def _he_quick(X, y, q, prot):
    """Out-of-sample HE of the lowest-error hedge (no cost limit): used for what-if comparisons."""
    ok = ~np.isnan(y) & ~np.isnan(X).any(axis=1)
    X, y = X[ok], y[ok]
    if len(y) < 30 or np.var(y) == 0:
        return None
    return round(op.hedge_effectiveness(y, op.loyo_payout(X, y, op.model_tranches(q), None, prot)), 3)


def _wet_package(items, prot, req) -> dict:
    """One YES-contract hedge for the excess-rain cover on the recommended intervals (estimated prices)."""
    cols, legs, q, y = [], [], [], None
    st = items[0][1].station
    for w, pw, yw in items:
        for j, (m, k) in enumerate(pw.legs):
            cols.append(1.0 - pw.X[:, j])
            legs.append((m, k))
            q.append(1.0 - pw.q[j])
        y = yw if y is None else y + yw
    from agri_hedge.error_budget import dedupe
    X, legs, q = dedupe(np.column_stack(cols), legs, q)   # strikes that paid in the same years are one contract
    ok = ~np.isnan(y) & ~np.isnan(X).any(axis=1)
    tr = op.model_tranches(q)
    fr = op.efficient_frontier(X[ok], y[ok], tr, n_points=13, scale=prot, q=q)
    b = op.knee_budget(fr, KNEE_SHARE)
    sol = op.solve_budget(X[ok], y[ok], tr, b, prot)
    he = op.hedge_effectiveness(y[ok], op.loyo_payout(X[ok], y[ok], tr, b, prot))
    ticket = []
    for (m, k), c, qq in zip(legs, sol.leg_contracts, q):
        n = int(round(c))
        if n <= 0:
            continue
        price = float(np.clip(qq + HALF_SPREAD, 0.01, 0.99))
        cm = contract_month_for(m)
        ticket.append({"ticker": f"{event_ticker(st['series_ticker'], cm)}-{int(k) if float(k).is_integer() else k}",
                       "contract_month": cm, "side": "YES",
                       "meaning": f"pays $1 per contract if {hb.MONTH_ABBR[m - 1]} rain at the station is above {k:g} in",
                       "contracts": n, "limit_price": round(price, 2), "premium_usd": round(n * price, 2),
                       "fee_usd": float(taker_fee([n], [price], tick=FEE_TICK_RETAIL)[0]),
                       "price_source": "estimated", "fair_probability": round(float(qq), 3)})
    ev = float(q @ sol.leg_contracts)
    return {"intervals": [w.label for w, _, _ in items], "cost_usd": round(sol.cost, 2), "expected_payout_usd": round(ev, 2),
            "cost_per_dollar_expected": round(sol.cost / ev, 3) if ev > 0 else None, "he_out_of_sample": round(he, 3),
            "ticket": sorted(ticket, key=lambda r: r["contract_month"])}


def _depth_check(req, rec: list, gap_prot: float) -> dict:
    """Refit the recommended package with each leg capped at today's order-book depth near fair value.

    Depth per strike comes from the latest saved snapshot of the station's listed ladder (contracts offered
    within 10 cents of fair value; doc 22), taken as the depth for every month. Capping contracts at k x depth
    is the same as buying 1/k of the cover at today's depth, so the largest cover per month that keeps 90% of
    the uncapped fit is gap_prot / (smallest k that reaches it).
    """
    from agri_hedge import error_budget as eb
    months = [hb.MONTH_ABBR.index(m) + 1 for m in rec]
    p = hb.build_problem(hb.CoverageRequest(req.lat, req.lon, [hb.Window((m,), 1.0 / len(months)) for m in months],
                                            req.coverage, gap_prot * len(months), station_key=req.station_key,
                                            grid_id=req.grid_id))
    ok = p.ok
    X, y = p.X[ok], p.target[ok]
    scale = gap_prot * len(months)
    depth, snap = eb.book_depth_by_strike(p.station["series_ticker"], p.station["station_key"])
    free = op.hedge_effectiveness(y, op.loyo_payout(X, y, op.model_tranches(p.q), None, scale))
    rows, need = [], None
    for k in (1, 2, 5, 10, 25):
        tr = op.model_tranches(p.q)
        for t, (_, s_) in zip(tr, p.legs):
            t.capacity = k * depth.get(s_, 0.0)
        h = op.hedge_effectiveness(y, op.loyo_payout(X, y, tr, None, scale))
        rows.append({"depth_multiple": k, "he_out_of_sample": round(h, 3)})
        if need is None and h >= 0.9 * free:
            need = k
    return {"snapshot": snap, "he_no_limit": round(free, 3), "by_depth": rows,
            "depth_multiple_for_90pct": need,
            "max_cover_per_month_usd": round(gap_prot / need, 0) if need else None,
            "he_at_today_depth": rows[0]["he_out_of_sample"]}

def companion(params: dict, live: LiveQuotes | None = None, today: date | None = None) -> dict:
    """Score the gaps a PRF election leaves and build a Kalshi hedge for the ones that track well.

    params: lat, lon, prf_intervals [{label: 'Apr-May', share}], coverage, protection (the PRF policy's
    dollars), optional gap_protection_per_month (default protection / 6, about one interval's share),
    station_key, price_source ('auto' | 'model'), min_he (default 0.5).
    """
    t0 = time.time()
    prf_windows = [{"label": w["label"], "share": float(w["share"])} for w in params["prf_intervals"]]
    base = dict(params, windows=prf_windows, price_source="model")
    req = parse_request(base)
    choice = choose_station(req) if not req.station_key else []
    if choice:
        req.station_key = choice[0]["station_key"]
    prf = hb.build_problem(req)
    prot = req.protection
    gap_prot = float(params.get("gap_protection_per_month") or prot / 6)
    min_he = float(params.get("min_he", GOOD_HE))
    covered = sorted({m for w in req.windows for m in w.months})
    months = []
    for m in range(1, 13):
        row = {"month": m, "name": hb.MONTH_ABBR[m - 1], "covered_by_prf": m in covered}
        if m not in covered:
            r1 = hb.CoverageRequest(req.lat, req.lon, [hb.Window((m,), 1.0)], req.coverage, gap_prot,
                                    station_key=req.station_key, grid_id=req.grid_id)
            pm = hb.build_problem(r1)
            sc = _score(pm.X, pm.target, pm.q, gap_prot)
            if sc:
                row.update(sc)
                row["verdict"] = ("recommended" if sc["he_out_of_sample"] >= min_he else
                                  "possible" if sc["he_out_of_sample"] >= OK_HE else "poor match")
        months.append(row)
    rec = [r["name"] for r in months if r.get("verdict") == "recommended"]
    # wet side (excess rain) and the two-month what-if, on each insured interval
    from agri_hedge import error_budget as eb
    wet, whatif, wet_rec = [], [], []
    for w in req.windows:
        pw = hb.build_problem(hb.CoverageRequest(req.lat, req.lon, [hb.Window(w.months, 1.0)], req.coverage,
                                                 prot * w.share, station_key=req.station_key, grid_id=req.grid_id))
        idx = hb.window_index(pw.grid_id, w, pw.years)
        y_wet = np.where(np.isnan(idx), np.nan, prot * w.share * EXCESS_SHARE_OF_PROTECTION *
                         np.clip((idx - EXCESS_START) / EXCESS_SPAN, 0, 1))
        sc = _score(1.0 - pw.X, y_wet, 1.0 - pw.q, prot * w.share)
        if sc:
            sc["verdict"] = "recommended" if sc["he_out_of_sample"] >= min_he else "needs two-month contracts"
            wet.append({"interval": w.label, **sc})
            if sc["verdict"] == "recommended":
                wet_rec.append((w, pw, y_wet))
        X2, _, q2 = eb.window_total_ladder_cols(pw, 1.0)
        q2 = np.asarray(q2, float)
        whatif.append({"interval": w.label,
                       "drought_today": _he_quick(pw.X, pw.target, pw.q, prot * w.share),
                       "drought_two_month": _he_quick(X2, pw.target, q2, prot * w.share),
                       "wet_today": _he_quick(1.0 - pw.X, y_wet, 1.0 - pw.q, prot * w.share),
                       "wet_two_month": _he_quick(1.0 - X2, y_wet, 1.0 - q2, prot * w.share)})
    wet_package = _wet_package(wet_rec, prot, req) if wet_rec else None
    out = {"station": {"key": prf.station["station_key"], "series": prf.station["series_ticker"],
                       "name": prf.station.get("name"), "distance_mi": round(prf.distance_mi, 1)},
           "station_choice": choice, "grid": {"grid_id": prf.grid_id, "center": list(prf.grid_center)},
           "prf": {"intervals": prf_windows, "coverage": req.coverage, "protection_usd": prot,
                   "expected_payout_usd": round(float(np.nanmean(prf.target)), 2),
                   "est_producer_premium_usd": round(float(np.nanmean(prf.target)) * PRF_PRODUCER_PER_DOLLAR, 2),
                   "months_covered": [hb.MONTH_ABBR[m - 1] for m in covered]},
           "gap_protection_per_month_usd": gap_prot, "months": months, "excess_rain": wet,
           "recommended_months": rec, "package": None, "wet_package": wet_package, "two_month_whatif": whatif}
    depth = None
    if rec:
        depth = _depth_check(req, rec, gap_prot)
        q = quote({"lat": req.lat, "lon": req.lon, "coverage": req.coverage, "protection": gap_prot * len(rec),
                   "windows": [{"label": m, "share": 1.0 / len(rec)} for m in rec],
                   "station_key": req.station_key, "price_source": params.get("price_source", "auto")},
                  live=live, today=today)
        yrs = np.array(q["backtest"]["years"])
        prf_pay = pd.Series(prf.target, index=prf.years).reindex(yrs)
        q["backtest"]["prf_usd"] = [None if np.isnan(v) else round(float(v), 0) for v in prf_pay]
        out["package"] = q
        tot_gap = float(np.mean(q["backtest"]["target_usd"]))
        out["depth_check"] = depth
        out["summary"] = {
            "months_added": rec, "package_cost_usd": q["hedge"]["cost_usd"],
            "package_expected_payout_usd": q["hedge"]["expected_payout_usd"],
            "package_he_out_of_sample": q["hedge"]["he_out_of_sample"],
            "gap_cover_expected_usd": round(tot_gap, 2),
            "years_gap_cover_paid": int((np.array(q["backtest"]["target_usd"]) > 0).sum())}
    out["elapsed_s"] = round(time.time() - t0, 2)
    out["notes"] = [
        "Gap months are covered with a PRF-style payout on your grid's rain for that month (90% trigger unless "
        "you chose another coverage level), hedged with Kalshi NO contracts at the settlement station.",
        f"Recommended = out-of-sample hedge effectiveness at least {min_he:.1f}: the hedge removes at least that "
        "share of the year-to-year swing in the gap cover, tested on years it was not fitted to.",
        f"Excess-rain cover pays {EXCESS_SHARE_OF_PROTECTION:.0%} of the interval's protection in full when grid rain reaches "
        f"{EXCESS_START + EXCESS_SPAN:.0f}% of normal, starting at {EXCESS_START:.0f}%, hedged with YES contracts.",
        "The two-month what-if shows the fit if Kalshi listed contracts on two-month rain totals (our proposal, doc 17); "
        "it uses the lowest-error hedge.",
        "Cool-season rain matters less for warm-season forage; gap cover suits winter pasture, stock water and wheat.",
        "Depth check: Kalshi books are thin. The app refits the package with orders capped at the depth near fair value "
        "on the latest saved book, and suggests the largest cover per month that keeps 90% of the fit (doc 22)."]
    return out


# ---------------------------------------------------------------------------------------------
# Exotic payoffs: exchange-settled products built in closed form from the ladder (docs 23, 24)
# ---------------------------------------------------------------------------------------------

DEFAULT_ELASTICITY = 0.5     # doc 03b scen_* values run 0.14-0.89; 0.5 is a round central value
OPTIMAL = "optimal"          # the utility-optimal step payout (doc 24, design.optimal_step_payout)
COMPARE_SHAPES = ("linear", "layered", "convex2", "exponential", "tiers", "capped", "loss", OPTIMAL)


def exotic_shapes() -> dict:
    """Shape key -> label for the product designer (doc 23 shapes plus the doc 24 optimum)."""
    from agri_hedge import exotic as ex
    d = {k: v for k, v in ex.SHAPES.items() if k != "persistence"}
    d[OPTIMAL] = "Data-optimal for this land (utility-based)"
    return d


def _resolve_station(params: dict):
    lat, lon = params.get("lat"), params.get("lon")
    if params.get("station_key"):
        st = hb.station_table().set_index("station_key").loc[params["station_key"]].to_dict()
        st["station_key"] = params["station_key"]
        dist = haversine(lat, lon, st) if lat is not None and lon is not None else None
    elif lat is not None and lon is not None:
        nn = hb.nearest_stations(float(lat), float(lon), 1).iloc[0]
        st, dist = nn.to_dict(), float(nn["distance_mi"])
    else:
        raise ValueError("give a station_key or a lat/lon")
    return st, dist, lat, lon


def exotic_quote(params: dict, live: LiveQuotes | None = None, today: date | None = None, _keep: dict | None = None) -> dict:
    """Design and price an exchange-settled exotic rain contract for one calendar month.

    The contract pays a function of the station's monthly rain total (Kalshi's settlement variable), so
    it is replicated exactly by long NO and YES contracts (doc 23, spanning), up to the strike grid.

    params: station_key or lat/lon (nearest station), month (1-12), shape (one of exotic.SHAPES except
    'persistence', or 'optimal' for the utility-optimal step payout of doc 24, which needs lat/lon),
    max_payout ($, paid when the month's rain is 0), coverage (trigger / 100, default 0.9),
    price_source ('auto' = live book, else saved snapshot, else estimate; 'model' = estimate only),
    elasticity and curvature for the 'loss' shape (defaults: 0.5 and doc 13's pooled curvature);
    for 'optimal': risk_aversion (CRRA, default 2), load (default 0.2), wealth_multiple (default 2),
    value_at_risk ($ of the month's production the farmer stands to lose; default max_payout) and
    loss_shape ('loss' = the doc-13 curve, 'linear' = PRF's payoff) for the farmer's loss.
    `_keep` (internal) receives the farm loss and station bins for `exotic_compare`.
    """
    from agri_hedge import design as dg
    from agri_hedge import exotic as ex
    from agri_hedge.loss_model import load_sensitivity, pooled_curvature
    from agri_hedge.pricing import capital_cost, leg_probability, no_asks_from_yes_bids, walk_no_book

    t0 = time.time()
    shape = str(params.get("shape", "convex2"))
    if shape != OPTIMAL and (shape not in ex.SHAPES or shape == "persistence"):
        raise ValueError(f"shape must be one of {list(exotic_shapes())}")
    month = int(params["month"])
    if not 1 <= month <= 12:
        raise ValueError("month must be 1-12")
    max_payout = float(params.get("max_payout", 0) or 0)
    if max_payout <= 0:
        raise ValueError("max_payout must be positive")
    cov = float(params.get("coverage", 0.9))
    if not 0.5 <= cov <= 1.0:
        raise ValueError("Coverage level must be between 50% and 100%.")
    st, dist, lat, lon = _resolve_station(params)
    key, series = st["station_key"], st["series_ticker"]
    lp = None
    loss_shape = str(params.get("loss_shape", "loss"))
    if shape == "loss" or loss_shape == "loss":        # the farm's loss curve is also the basis-risk target
        g = params.get("curvature")
        lp = (float(params.get("elasticity", DEFAULT_ELASTICITY)),
              float(g) if g is not None else float(pooled_curvature(load_sensitivity())))
    gamma = float(params.get("risk_aversion", dg.DEFAULT_GAMMA))
    load = float(params.get("load", dg.DEFAULT_LOAD))
    wealth = float(params.get("wealth_multiple", dg.DEFAULT_WEALTH))
    value_at_risk = float(params.get("value_at_risk") or max_payout)

    rain_all = hb.station_rain(key)
    R = rain_all[month]
    normal = float(R[(R.index >= hb.NORMAL_YEARS[0]) & (R.index <= hb.NORMAL_YEARS[1])].mean())
    Rv = R.to_numpy(float)
    gidx = 100.0 * Rv / normal
    ok = ~np.isnan(Rv)

    # the ladder: the listed month's strikes if a book exists, else the strikes Kalshi has listed for this month
    live = live or _DEFAULT_LIVE
    price_source = params.get("price_source", "auto")
    cm = contract_month_for(month, today)
    books_all = live.series_books(series) if price_source != "model" else {}
    listed = {k: b for (c, k), b in books_all.items() if c == cm}
    strikes = sorted(listed) if listed else list(hb.listed_strikes(series)[month])
    fair_no = {float(k): leg_probability(rain_all, month, k, hb.FAIR_WINDOW) for k in strikes}

    # the farm side: the farmer's own payoff for this month on their PRF grid (for the optimum and the basis risk)
    farm_shape = loss_shape if shape == OPTIMAL else shape
    p1 = y_farm = None
    if lat is not None and lon is not None:
        try:
            p1 = hb.build_problem(hb.CoverageRequest(float(lat), float(lon), [hb.Window((month,), 1.0)], cov, max_payout,
                                                     station_key=key))
            y_farm = ex.shape_target(p1, farm_shape, lp)
        except (KeyError, ValueError):
            p1 = None
    design = None
    if shape == OPTIMAL:
        if p1 is None:
            raise ValueError("The data-optimal shape needs the farm's latitude and longitude inside the served area.")
        Rs = R.reindex(p1.years).to_numpy(float)
        loss = y_farm / max_payout
        m = ~np.isnan(loss) & ~np.isnan(Rs)
        bins = ex.rain_bins(Rs[m], strikes)
        opt = dg.optimal_step_payout(loss[m], bins, len(strikes) + 1, gamma, load, wealth)
        if opt.max_payout <= 1e-9:
            raise ValueError("The utility-optimal contract is empty here: for a farmer with these settings the "
                             "station's rain says too little about this land's shortfall to buy any cover.")
        vals = opt.shape
        design = {"risk_aversion": gamma, "load": load, "wealth_multiple": wealth, "loss_shape": farm_shape,
                  "value_at_risk_usd": value_at_risk,
                  "recommended_max_payout_usd": round(opt.max_payout * value_at_risk, 2),
                  "recommended_premium_usd": round(opt.premium * value_at_risk, 2),
                  "recommended_fair_premium_usd": round(opt.fair_premium * value_at_risk, 2),
                  "ce_gain_pct_of_value": round(100 * opt.ce_gain, 3), "years": int(m.sum()),
                  "converged": bool(opt.converged)}
        if _keep is not None:
            _keep.update({"loss": loss[m], "bins": bins, "strikes": list(strikes), "years": p1.years[m]})
    else:
        f = ex.payoff(shape, gidx, cov, lp)
        ok = ok & ~np.isnan(f)
        vals = ex.binned_values(f[ok], Rv[ok], strikes,
                                lambda rr: float(ex.payoff(shape, np.array([100.0 * rr / normal]), cov, lp)[0]))
        if _keep is not None and p1 is not None:
            Rs = R.reindex(p1.years).to_numpy(float)
            loss = ex.shape_target(p1, loss_shape, lp) / max_payout
            m = ~np.isnan(loss) & ~np.isnan(Rs)
            _keep.update({"loss": loss[m], "bins": ex.rain_bins(Rs[m], strikes), "strikes": list(strikes),
                          "years": p1.years[m]})
    port = ex.span_step(vals, strikes)
    hp = port.payout(Rv)
    fw = np.asarray((R.index >= hb.FAIR_WINDOW[0]) & (R.index <= hb.FAIR_WINDOW[1])) & ok
    fair_rate = float(np.mean(hp[fw])) if fw.any() else float("nan")

    # term sheet: what the contract pays in each rain bin
    edges = [0.0] + [float(k) for k in strikes]
    terms = []
    bins_all = ex.rain_bins(Rv[ok], strikes)
    for j, v in enumerate(vals):
        lo = edges[j]
        hi = edges[j + 1] if j + 1 < len(edges) else None
        rng = (f"{hi:g} in or less" if j == 0 else f"more than {lo:g} in" if hi is None else f"{lo:g} to {hi:g} in")
        terms.append({"bin": j, "rain": rng, "payout_usd": round(float(v) * max_payout, 2),
                      "years_in_bin": int((bins_all == j).sum()), "years_total": int(ok.sum())})

    # the order: one leg per strike and side, priced from the book where listed, else estimated
    ticket, n_live = [], 0
    for k, v, w in zip(port.strikes, port.no_weights, port.yes_weights):
        for side, wt in (("NO", v), ("YES", w)):
            n = int(round(wt * max_payout))
            if n <= 0:
                continue
            fq = fair_no[float(k)]
            fair = fq if side == "NO" else 1.0 - fq
            b = listed.get(float(k))
            tick = b["ticker"] if b else f"{event_ticker(series, cm)}-{int(k) if float(k).is_integer() else k}"
            if b is not None:
                levels = b["yes_bids"] if side == "NO" else b.get("no_bids", [])
                asks = no_asks_from_yes_bids(levels)
                fill = walk_no_book(levels, n, max_price=fair + SENSIBLE_TOL)
                filled = int(round(fill["filled"]))
                price = fill["vwap"] if filled else None
                src = b["source"]
                n_live += 1
            else:
                asks, filled, price, src = [], n, float(np.clip(fair + HALF_SPREAD, 0.01, 0.99)), "estimated"
            prem = (price or 0.0) * (filled if b is not None else n)
            fee = float(taker_fee([filled if b is not None else n], [price or fair], tick=FEE_TICK_RETAIL)[0]) if (price or 0) > 0 else 0.0
            depth = float(sum(s for pr, s in asks if pr <= fair + SENSIBLE_TOL)) if b is not None else None
            ticket.append({"ticker": tick, "contract_month": cm, "side": side, "strike_in": float(k),
                           "meaning": (f"pays $1 per contract if {hb.MONTH_ABBR[month - 1]} rain at {key} is "
                                       f"{'at most' if side == 'NO' else 'above'} {k:g} in"),
                           "contracts": n, "contracts_filled": filled if b is not None else None,
                           "fair_probability": round(float(fair), 3), "avg_price": None if price is None else round(float(price), 4),
                           "premium_usd": round(float(prem), 2), "fee_usd": round(fee, 2), "price_source": src,
                           "depth_sensible": depth, "weight_per_dollar": float(wt)})
    prem_paid = sum(r["premium_usd"] for r in ticket)
    fees = sum(r["fee_usd"] for r in ticket)
    want = sum(r["contracts"] for r in ticket)
    got = sum((r["contracts_filled"] if r["contracts_filled"] is not None else r["contracts"]) for r in ticket)
    fair_prem = sum(r["fair_probability"] * (r["contracts_filled"] if r["contracts_filled"] is not None else r["contracts"])
                    for r in ticket)
    fill_share = got / want if want else None
    cap = float(capital_cost(prem_paid + fees))
    booked = [r for r in ticket if r["depth_sensible"] is not None and r["weight_per_dollar"] > 0]
    largest = (min(r["depth_sensible"] / r["weight_per_dollar"] for r in booked) if booked and len(booked) == len(ticket)
               else None)

    # the farmer's basis risk: the same shape on their own grid for this month, vs the exchange-settled product
    basis = None
    if p1 is not None:
        y = y_farm
        h = pd.Series(hp * max_payout, index=R.index).reindex(p1.years).to_numpy(float)
        m = ~np.isnan(y) & ~np.isnan(h)
        he = op.hedge_effectiveness(y[m], h[m]) if m.sum() > 10 and np.var(y[m]) > 0 else None
        basis = {"grid_id": p1.grid_id, "distance_mi": round(p1.distance_mi, 1), "years": int(m.sum()),
                 "farm_shape": farm_shape,
                 "he_exchange_vs_farm": None if he is None else round(he, 3),
                 "tail_capture": round(ex.tail_capture(y[m], h[m]), 3) if m.any() else None,
                 "farm_expected_payout_usd": round(float(np.mean(y[m])), 2) if m.any() else None,
                 "verdict": (None if he is None else "good match" if he >= GOOD_HE else
                             "partial match" if he >= OK_HE else "poor match")}
    yrs_ok = R.index.to_numpy()[ok]
    return {
        "product": {"shape": shape, "shape_label": exotic_shapes()[shape], "station": key, "series": series,
                    "station_name": st.get("name"), "distance_mi": None if dist is None else round(float(dist), 1),
                    "month": hb.MONTH_ABBR[month - 1], "month_number": month, "contract_month": cm, "coverage": cov,
                    "trigger_in": round(normal * cov, 2), "normal_in": round(normal, 2), "max_payout_usd": max_payout,
                    "loss_params": lp, "settles_on": f"{hb.MONTH_ABBR[month - 1]} rain total at {key} (NWS climate report)",
                    "farm_lat": None if lat is None else float(lat), "farm_lon": None if lon is None else float(lon)},
        "term_sheet": terms,
        "replication": {"contracts_per_dollar": round(port.contracts_per_dollar, 4), "cash_leg": round(port.cash, 6),
                        "quasi_convex": ex.is_quasi_convex(vals), "exact_on_bins": True,
                        "strikes": [float(k) for k in strikes], "step_values": [round(float(v), 6) for v in vals]},
        "pricing": {"fair_rate": round(fair_rate, 4), "fair_premium_usd": round(fair_rate * max_payout, 2),
                    "premium_filled_fair_usd": round(float(fair_prem), 2), "premium_paid_usd": round(prem_paid, 2),
                    "spread_cost_usd": round(prem_paid - fair_prem, 2), "fee_usd": round(fees, 2),
                    "capital_usd": round(cap, 2), "all_in_usd": round(prem_paid + fees + cap, 2),
                    "cost_per_dollar_expected": (round((prem_paid + fees + cap) / (fair_rate * max_payout * fill_share), 3)
                                                 if fill_share and fair_rate > 0 else None),
                    "fill_share": None if fill_share is None else round(fill_share, 3),
                    "largest_fillable_max_payout_usd": None if largest is None else round(float(largest), 0),
                    "legs_priced_from_order_book": n_live},
        "ticket": ticket,
        "backtest": {"years": yrs_ok.tolist(), "rain_in": np.round(Rv[ok], 2).tolist(),
                     "payout_usd": np.round(hp[ok] * max_payout, 0).tolist(),
                     "years_paid": int((hp[ok] > 0).sum())},
        "farm_basis_risk": basis,
        "design": design,
        "notes": [
            "The contract pays the step function in the term sheet on the station's official monthly total; the ticket "
            "matches it on the listed rain bins if every leg fills; unfilled legs leave the issuer exposed, and the farmer still bears basis risk.",
            ("The data-optimal shape maximizes the expected utility of a risk-averse farmer over the 1951-2025 history of "
             "station rain and this land's shortfall, priced with the stated load (doc 24)." if shape == OPTIMAL else
             "Payouts in each bin are the shape's average over the years that fell in that bin (1951-2025 where the "
             "record allows); finer strikes would track the smooth shape more closely (doc 23)."),
            "farm_basis_risk compares this exchange-settled product with the farmer's own payoff on their PRF grid: "
            "that mismatch is the farmer's to bear, not the issuer's."],
        "elapsed_s": round(time.time() - t0, 2),
    }


def exotic_compare(params: dict, live: LiveQuotes | None = None, today: date | None = None) -> dict:
    """Every shape for one location and month, at the same maximum payout and at the same premium.

    Adds, for a CRRA farmer (risk_aversion, load, wealth_multiple as in `exotic_quote`), the certainty-
    equivalent gain of each shape at its best size and the share of the utility-optimal contract's gain it
    captures (doc 24). params: as `exotic_quote` plus optional `shapes` (list of shape keys).
    """
    from agri_hedge import design as dg

    t0 = time.time()
    shapes = list(params.get("shapes") or COMPARE_SHAPES)
    base = {k: v for k, v in params.items() if k not in ("shape", "shapes")}
    max_payout = float(base.get("max_payout", 0) or 0)
    quotes, errors, keep = {}, {}, {}
    for s in shapes:
        try:
            quotes[s] = exotic_quote({**base, "shape": s}, live, today, _keep=keep)
        except ValueError as exc:
            errors[s] = str(exc)
    if not quotes:
        raise ValueError(next(iter(errors.values())))
    ref_key = "linear" if "linear" in quotes else next(iter(quotes))
    ref_prem = quotes[ref_key]["pricing"]["fair_premium_usd"]
    gamma = float(base.get("risk_aversion", dg.DEFAULT_GAMMA))
    load = float(base.get("load", dg.DEFAULT_LOAD))
    wealth = float(base.get("wealth_multiple", dg.DEFAULT_WEALTH))
    ce = None
    if keep.get("loss") is not None:
        fixed = {s: np.asarray(q["replication"]["step_values"], float) for s, q in quotes.items() if s != OPTIMAL}
        ce = dg.ce_shares(keep["loss"], keep["bins"], len(keep["strikes"]) + 1, fixed, gamma, load, wealth)
    value_at_risk = float(base.get("value_at_risk") or max_payout)
    rows = []
    for s, q in quotes.items():
        pr, fb = q["pricing"], q["farm_basis_risk"] or {}
        fp = pr["fair_premium_usd"]
        eq_mp = max_payout * ref_prem / fp if fp > 0 else None
        eq_fill = pr["fill_share"]
        if eq_mp is not None and abs(eq_mp - max_payout) > 1.0 and base.get("price_source", "auto") != "model":
            try:
                eq_fill = exotic_quote({**base, "shape": s, "max_payout": eq_mp}, live, today)["pricing"]["fill_share"]
            except ValueError:
                eq_fill = None
        c = (ce or {}).get(s)
        rows.append({
            "shape": s, "shape_label": q["product"]["shape_label"],
            "fair_premium_usd": fp, "premium_per_dollar_max_payout": round(pr["fair_rate"], 4),
            "all_in_usd": pr["all_in_usd"], "cost_per_dollar_expected": pr["cost_per_dollar_expected"],
            "contracts": sum(t["contracts"] for t in q["ticket"]),
            "contracts_per_dollar": q["replication"]["contracts_per_dollar"],
            "fill_share": pr["fill_share"], "largest_fillable_max_payout_usd": pr["largest_fillable_max_payout_usd"],
            "max_payout_equal_premium_usd": None if eq_mp is None else round(eq_mp, 0),
            "fill_share_equal_premium": None if eq_fill is None else round(float(eq_fill), 3),
            "farm_he": fb.get("he_exchange_vs_farm"), "farm_verdict": fb.get("verdict"),
            "tail_capture": fb.get("tail_capture"),
            "term_sheet_usd": [t["payout_usd"] for t in q["term_sheet"]],
            "ce_gain_pct_of_value": None if c is None else round(100 * c["ce_gain"], 3),
            "ce_share_of_optimal": None if c is None or not np.isfinite(c["share"]) else round(float(c["share"]), 3),
            "utility_best_max_payout_usd": None if c is None else round(c["max_payout"] * value_at_risk, 0),
            "utility_best_premium_usd": None if c is None else round(c["premium"] * value_at_risk, 2),
        })
    bins = [t["rain"] for t in quotes[ref_key]["term_sheet"]]
    scored = [r for r in rows if r["ce_share_of_optimal"] is not None]
    worth = ce is not None and ce["optimal"]["ce_gain"] > 1e-12
    if ce is not None and not worth:
        best = next((r for r in rows if r["shape"] == "convex2"), rows[0])
        rec = {"shape": best["shape"], "best_fixed_shape": None, "worth_buying": False,
               "why": (f"For a farmer with risk aversion {gamma:g} and a {load:.0%} load, no contract on this ladder is worth its "
                       "premium: the station's rain says too little about this land's shortfall in this month. The quadratic "
                       "shape is shown as the doc-23 default.")}
    elif scored:
        best = max(scored, key=lambda r: r["ce_share_of_optimal"])
        fixed_rows = [r for r in scored if r["shape"] != OPTIMAL]
        best_fixed = max(fixed_rows, key=lambda r: r["ce_share_of_optimal"]) if fixed_rows else best
        lin = next((r for r in rows if r["shape"] == "linear"), None)
        why = (f"For a farmer with risk aversion {gamma:g} and a {load:.0%} load, {best_fixed['shape_label']} captures "
               f"{best_fixed['ce_share_of_optimal']:.0%} of the gain of the best possible contract on this ladder"
               + (f" (PRF's linear shape: {lin['ce_share_of_optimal']:.0%})." if lin and lin is not best_fixed and lin["ce_share_of_optimal"] is not None else "."))
        rec = {"shape": best["shape"], "best_fixed_shape": best_fixed["shape"], "worth_buying": True, "why": why}
    else:
        best = next((r for r in rows if r["shape"] == "convex2"), rows[0])
        rec = {"shape": best["shape"], "best_fixed_shape": best["shape"], "worth_buying": None,
               "why": "No farm location was given, so the utility ranking is unavailable; the quadratic shape is the doc-23 default."}
    return {"product": {k: quotes[ref_key]["product"][k] for k in ("station", "series", "station_name", "distance_mi", "month",
                                                                   "month_number", "contract_month", "coverage", "max_payout_usd")},
            "equal_premium_reference": ref_key, "reference_fair_premium_usd": ref_prem, "bins": bins, "rows": rows,
            "farmer": {"risk_aversion": gamma, "load": load, "wealth_multiple": wealth, "value_at_risk_usd": value_at_risk,
                       "years": None if keep.get("years") is None else int(len(keep["years"]))},
            "recommendation": rec, "errors": errors, "elapsed_s": round(time.time() - t0, 2)}


def haversine(lat, lon, st: dict) -> float:
    from agri_hedge.locations import haversine_miles
    return float(haversine_miles(float(lat), float(lon), float(st["lat"]), float(st["lon"])))


def live_reference(p: hb.HedgeProblem, books: dict) -> list[dict]:
    """Today's open ladder(s) for the station: best NO ask vs fair value and depth near fair value."""
    from agri_hedge.pricing import leg_probability, no_asks_from_yes_bids
    rows = []
    rain = hb.station_rain(p.station["station_key"])
    for (cm, k), b in sorted(books.items()):
        m = int(cm[5:7])
        q = leg_probability(rain, m, k, hb.FAIR_WINDOW)
        asks = no_asks_from_yes_bids(b["yes_bids"])
        rows.append({"ticker": b["ticker"], "contract_month": cm, "strike_in": k, "source": b["source"],
                     "as_of": b["as_of"], "fair_no_climatology": round(q, 3),
                     "best_no_ask": asks[0][0] if asks else None,
                     "no_depth_contracts": round(float(sum(s for _, s in asks)), 1),
                     "no_depth_within_10c_of_fair": round(float(sum(s for pr, s in asks if pr <= q + SENSIBLE_TOL)), 1)})
    return rows


def coverage_points() -> list[dict]:
    """Grid centers the app can serve (for the map), with the nearest station."""
    from agri_hedge.prf_grid import grid_id_to_center
    out = []
    for g in sorted(hb.covered_grids()):
        lat, lon = grid_id_to_center(g)
        out.append({"grid_id": g, "lat": lat, "lon": lon})
    return out


def stations() -> list[dict]:
    return hb.station_table().to_dict("records")


def json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return None if math.isnan(o) else float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    return str(o)
