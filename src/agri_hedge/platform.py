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
KNEE_SHARE = 0.9
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
        mode = "recommended (cheapest hedge with 90% of the best fit)"
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
