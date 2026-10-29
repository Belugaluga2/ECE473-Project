"""R5: a modest sample of Kalshi weather-market structure, liquidity, and order-book depth.

This is research support for docs/research/05_kalshi_weather_markets.md. It is NOT the full Kalshi
dataset pipeline (that is scripts/pull_kalshi.py / data/processed/kalshi_*). It produces:

1. A catalog of weather/climate product families: number of series, number with open markets,
   and contracts traded in the API's "live" window (markets still open or settled after the
   historical cutoff, roughly the last 60 days).
2. A per-city history of monthly-rain events (strikes, contracts traded per event).
3. A deep dive on ~12 settled monthly-rain events across 8 cities: strikes, volume, open interest
   at close, bid-ask spreads from hourly candlesticks, trade sizes, early closes, settlement lag.
4. A timestamped snapshot of the order books of open monthly-rain markets for the study sites,
   with the number of YES contracts a farmer could buy at the quoted prices.
5. Two figures (docs/figures/r5_*.png).

Run from the repo root:  python scripts/r5_kalshi_sample.py
Raw API responses are cached as JSON under data/raw/r5_kalshi/cache/ so reruns are fast. Order
books and open-market lists are always re-pulled (they are snapshots) and saved with a timestamp.

Field-name notes (checked 2026-10-29): prices are dollar strings with a ``_dollars`` suffix,
contract counts are strings with an ``_fp`` suffix and may be fractional. Live candlesticks use
``price.close_dollars``/``open_interest_fp``; historical candlesticks use ``price.close``/
``open_interest``. The order book lists only BIDS for each side; a YES ask at price p is a NO bid
at 1 - p.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import requests  # noqa: E402

from agri_hedge.config import FIGURES, KALSHI_BASE_URL, RAW  # noqa: E402
from agri_hedge.locations import CONTRAST_SITES, STUDY_SITES  # noqa: E402

OUT = RAW / "r5_kalshi"
CACHE = OUT / "cache"
ET = ZoneInfo("America/New_York")
SESSION = requests.Session()
TODAY = datetime.now(timezone.utc).strftime("%Y%m%d")  # cache tag for lists that change daily

# Settled monthly-rain events sampled for the deep dive. Only DFW and DEN (plus the ORD contrast
# site) have settled history; OKC, SGF, ABQ, TPA, SAT first listed on 2026-10-26 (Nov 2026 events).
SAMPLE_EVENTS = [
    ("KXRAINDALM", "KXRAINDALM-26SEP"), ("KXRAINDALM", "KXRAINDALM-26MAY"),
    ("KXRAINDENM", "KXRAINDENM-26SEP"), ("KXRAINDENM", "KXRAINDENM-26JUL"),
    ("KXRAINCHIM", "KXRAINCHIM-26SEP"), ("KXRAINCHIM", "KXRAINCHIM-26APR"),
    ("KXRAINHOUM", "KXRAINHOUM-26SEP"), ("KXRAINAUSM", "KXRAINAUSM-26SEP"),
    ("KXRAINMIAM", "KXRAINMIAM-26SEP"), ("KXRAINLAXM", "KXRAINLAXM-26FEB"),
    ("KXRAINSEAM", "KXRAINSEAM-26JAN"), ("KXRAINNYCM", "KXRAINNYCM-26SEP"),
]


# --------------------------------------------------------------------------------------------
# HTTP helpers
# --------------------------------------------------------------------------------------------
def kalshi_get(path: str, params: dict | None = None, cache: bool = True,
               max_tries: int = 6, cache_tag: str = "") -> dict:
    """GET a Kalshi public market-data endpoint, with a JSON file cache and 429 back-off.

    Args:
        path: endpoint path such as "/markets".
        params: query parameters.
        cache: if True, reuse a cached response for the same path and parameters.
        max_tries: retries on HTTP 429/5xx with exponential back-off.
        cache_tag: extra text mixed into the cache key (e.g. a date, so a pull refreshes daily).
    """
    params = {k: v for k, v in (params or {}).items() if v is not None}
    key = hashlib.sha1((path + json.dumps(params, sort_keys=True) + cache_tag).encode()
                      ).hexdigest()[:20]
    fpath = CACHE / f"{key}.json"
    if cache and fpath.exists():
        return json.loads(fpath.read_text(encoding="utf-8"))
    for attempt in range(max_tries):
        try:
            r = SESSION.get(KALSHI_BASE_URL + path, params=params, timeout=60)
        except requests.exceptions.RequestException:  # connection reset, timeout, ...
            time.sleep(2 ** attempt)
            continue
        time.sleep(0.2)
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(2 ** attempt)
            continue
        r.raise_for_status()
        data = r.json()
        if cache:
            CACHE.mkdir(parents=True, exist_ok=True)
            fpath.write_text(json.dumps({"_path": path, "_params": params, **data}),
                             encoding="utf-8")
        return data
    raise RuntimeError(f"Kalshi GET failed after {max_tries} tries: {path} {params}")


def paginate(path: str, key: str, params: dict | None = None, cache: bool = True,
             limit: int = 1000, cache_tag: str = "") -> list:
    """Collect every item under ``key`` across cursor pages."""
    out, cursor = [], None
    while True:
        p = dict(params or {}, limit=limit)
        if cursor:
            p["cursor"] = cursor
        d = kalshi_get(path, p, cache=cache, cache_tag=cache_tag)
        out += d.get(key) or []
        cursor = d.get("cursor")
        if not cursor:
            return out


def num(x) -> float:
    """Parse a Kalshi fixed-point string (or number/None) to float (NaN if missing)."""
    if x is None or x == "":
        return float("nan")
    try:
        return float(x)
    except (TypeError, ValueError):
        m = re.search(r"-?\d+(\.\d+)?", str(x))
        return float(m.group()) if m else float("nan")


def pick(d: dict | None, *names):
    """Return the first present key among names (handles _dollars/_fp/legacy variants)."""
    d = d or {}
    for n in names:
        if n in d and d[n] is not None:
            return d[n]
    return None


def ts(s: str | None) -> pd.Timestamp:
    """ISO string to UTC Timestamp (NaT if missing)."""
    return pd.Timestamp(s) if s else pd.NaT


# --------------------------------------------------------------------------------------------
# Fees
# --------------------------------------------------------------------------------------------
def taker_fee(contracts: float, price: float, rate: float = 0.07, multiplier: float = 1.0,
              round_to: float | None = 0.01) -> float:
    """Kalshi general (quadratic) trading fee in dollars for one order.

    fee = rate x multiplier x C x P x (1 - P), rounded UP to ``round_to`` dollars
    (the classic fee-schedule rule rounds up to the next cent; since 2026 the exchange computes
    the fee to $0.000001 and aligns balances to $0.01 for FCM-cleared members and $0.0001 for
    direct members, see https://docs.kalshi.com/getting_started/fee_rounding).
    Weather series report fee_type="quadratic", fee_multiplier=1 (taker-only, no maker fee).
    """
    raw = rate * multiplier * contracts * price * (1.0 - price)
    if not round_to:
        return raw
    return math.ceil(round(raw / round_to, 9)) * round_to


# --------------------------------------------------------------------------------------------
# Catalog of weather product families
# --------------------------------------------------------------------------------------------
def classify_family(s: dict) -> str:
    """Assign a weather/climate series to a coarse product family (heuristic on ticker/title)."""
    t, title = s["ticker"].upper(), (s.get("title") or "").upper()
    terms = (s.get("contract_terms_url") or "").split("/")[-1].upper()
    freq = s.get("frequency") or ""
    if "RAIN" in t:
        return "Rain, monthly total" if (freq == "monthly" or terms in ("RAINM.PDF", "RAINNYCM.PDF")) \
            else "Rain, daily / weekly / storm"
    if any(k in t for k in ("OPEN", "CLOSE")) or terms in ("VAILSNOW.PDF", "IKONSNOW.PDF",
                                                         "SNOWRESORTS.PDF"):
        return "Ski resort opening / closing / snowfall"
    if "SNOW" in t:
        return "Snowfall (monthly, seasonal, holiday)"
    if "HUR" in t or "STORM" in t:
        return "Hurricanes and tropical storms"
    if any(k in t for k in ("EMERGENCY", "QUAKE", "ERUPT", "KILAUEA", "VEI4", "TSUNAMI",
                            "TORNADO", "FEMA", "FLARE")):
        return "Natural disasters and geophysical"
    if any(k in t for k in ("DROUGHT", "MEAD", "CORIVER")):
        return "Drought and water levels"
    if terms in ("INTERNATIONALTEMPERATURE.PDF", "GLOBALTEMPERATURECELSIUS.PDF"):
        return "Temperature, daily high/low (international cities)"
    if freq == "hourly" and ("TEMP" in t or "HIGH" in t):
        return "Temperature, hourly direction"
    if t.startswith(("KXWEEKHT", "KXAVGT", "KXHEATA")):
        return "Temperature, weekly high / average"
    if freq == "daily" and ("HIGH" in t or "LOW" in t or "TEMP" in title):
        return "Temperature, daily high/low (US cities)"
    if t.startswith(("KXSJCLOWT", "KXMSNLOWT", "KXMONTHLOW", "MINNYC", "KXMINNYC", "KXHDD",
                     "KXMAXTEMP", "KXHIGHTEMPDEN", "KXPHILHIGH", "KXHOLIDAYT", "KXTXURI",
                     "KXHOBBY", "KXHEATWARN")):
        return "Temperature, monthly / threshold / other"
    return "Global climate indicators and other"


def catalog_activity() -> pd.DataFrame:
    """Per-series activity in the live API window (one /markets call per series)."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    series = paginate("/series", "series", {"category": "Climate and Weather"}, cache_tag=stamp)
    (OUT / "series_climate.json").write_text(json.dumps(series, indent=1), encoding="utf-8")
    rows = []
    for s in series:
        ms = paginate("/markets", "markets", {"series_ticker": s["ticker"]}, cache_tag=stamp)
        n_open = sum(m.get("status") == "active" for m in ms)
        rows.append({
            "series_ticker": s["ticker"], "title": s.get("title"), "frequency": s.get("frequency"),
            "family": classify_family(s), "fee_type": s.get("fee_type"),
            "fee_multiplier": s.get("fee_multiplier"),
            "contract_terms": (s.get("contract_terms_url") or "").split("/")[-1],
            "settlement_sources": "; ".join(x.get("name", "") for x in
                                            (s.get("settlement_sources") or [])),
            "live_markets": len(ms), "open_markets": n_open,
            "live_window_contracts": sum(num(m.get("volume_fp")) for m in ms
                                         if not math.isnan(num(m.get("volume_fp")))),
        })
    return pd.DataFrame(rows)


def family_table(cat: pd.DataFrame) -> pd.DataFrame:
    """Summarize the per-series catalog by product family."""
    g = cat.groupby("family")
    out = pd.DataFrame({
        "series": g.size(),
        "series_with_open_markets": g.apply(lambda d: int((d.open_markets > 0).sum())),
        "live_window_contracts": g.live_window_contracts.sum().round(0),
        "frequencies": g.frequency.apply(lambda f: ", ".join(sorted(set(f.dropna())))),
        "top_series_by_volume": g.apply(lambda d: ", ".join(
            d.sort_values("live_window_contracts", ascending=False).series_ticker.head(3))),
    }).sort_values("live_window_contracts", ascending=False)
    return out.reset_index()


# --------------------------------------------------------------------------------------------
# Monthly-rain history and event deep dive
# --------------------------------------------------------------------------------------------
def series_markets(series_ticker: str) -> list[dict]:
    """All markets of a series, live and historical, tagged with their source."""
    live = paginate("/markets", "markets", {"series_ticker": series_ticker}, cache_tag=TODAY)
    hist = paginate("/historical/markets", "markets", {"series_ticker": series_ticker})
    for m in live:
        m["_source"] = "live"
    for m in hist:
        m["_source"] = "historical"
    seen, out = set(), []
    for m in live + hist:
        if m["ticker"] not in seen:
            seen.add(m["ticker"])
            out.append(m)
    return out


def rain_history(series_list: list[str]) -> pd.DataFrame:
    """One row per monthly-rain event: strikes, contracts traded, status."""
    rows = []
    for s in series_list:
        for ev, grp in pd.DataFrame(series_markets(s)).groupby("event_ticker"):
            rows.append({
                "series_ticker": s, "event_ticker": ev, "n_markets": len(grp),
                "strikes": ",".join(f"{x:g}" for x in sorted(grp.floor_strike.dropna())),
                "contracts_traded": grp.volume_fp.map(num).sum(),
                "first_open": grp.open_time.min(), "all_finalized": (grp.status == "finalized").all(),
            })
    return pd.DataFrame(rows)


def month_end_et(event_ticker: str) -> pd.Timestamp:
    """End of the event month (23:59:59 ET) as UTC, from a ticker suffix like -26SEP."""
    code = event_ticker.split("-")[-1]
    year, mon = 2000 + int(code[:2]), datetime.strptime(code[2:], "%b").month
    nxt = datetime(year + (mon == 12), mon % 12 + 1, 1, tzinfo=ET)
    return pd.Timestamp(nxt).tz_convert("UTC") - pd.Timedelta(seconds=1)


def candles(series_ticker: str, m: dict, interval: int = 60) -> pd.DataFrame:
    """Hourly candlesticks for a market over its whole life, normalized to flat columns."""
    start = int(ts(m["open_time"]).timestamp()) - 3600
    end = int(ts(m["close_time"]).timestamp()) + 3600
    if m["_source"] == "historical":
        path = f"/historical/markets/{m['ticker']}/candlesticks"
    else:
        path = f"/series/{series_ticker}/markets/{m['ticker']}/candlesticks"
    d = kalshi_get(path, {"start_ts": start, "end_ts": end, "period_interval": interval})
    rows = []
    for c in d.get("candlesticks") or []:
        bid, ask, pr = c.get("yes_bid") or {}, c.get("yes_ask") or {}, c.get("price") or {}
        rows.append({
            "t": pd.Timestamp(c["end_period_ts"], unit="s", tz="UTC"),
            "bid": num(pick(bid, "close_dollars", "close")),
            "ask": num(pick(ask, "close_dollars", "close")),
            "last": num(pick(pr, "close_dollars", "close")),
            "volume": num(pick(c, "volume_fp", "volume")),
            "oi": num(pick(c, "open_interest_fp", "open_interest")),
        })
    df = pd.DataFrame(rows, columns=["t", "bid", "ask", "last", "volume", "oi"])
    df["ticker"], df["strike"] = m["ticker"], m.get("floor_strike")
    return df


def trades(m: dict) -> pd.DataFrame:
    """All trades for a market (live or historical endpoint)."""
    path = "/historical/trades" if m["_source"] == "historical" else "/markets/trades"
    tr = paginate(path, "trades", {"ticker": m["ticker"]})
    if not tr:
        return pd.DataFrame(columns=["t", "count", "yes_price", "taker"])
    return pd.DataFrame({
        "t": pd.to_datetime([x["created_time"] for x in tr], utc=True, format="ISO8601"),
        "count": [num(x.get("count_fp")) for x in tr],
        "yes_price": [num(x.get("yes_price_dollars")) for x in tr],
        "taker": [x.get("taker_outcome_side") or x.get("taker_side") for x in tr],
    })


def summarize_event(series_ticker: str, event_ticker: str):
    """Deep-dive statistics for one settled monthly-rain event.

    Returns (event_row, market_rows, candle_frame).
    Spread is measured on hourly candle closes, only where a two-sided quote existed
    (0 < bid and ask < 1; Kalshi reports an empty side as bid 0.00 / ask 1.00).
    """
    ms = [m for m in series_markets(series_ticker) if m["event_ticker"] == event_ticker]
    mend = month_end_et(event_ticker)
    mrows, cfs, trs = [], [], []
    for m in sorted(ms, key=lambda x: x.get("floor_strike") or 0):
        c = candles(series_ticker, m)
        tr = trades(m)
        close = ts(m["close_time"])
        c_life = c[c.t <= close + pd.Timedelta(hours=1)]
        two = c_life[(c_life.bid > 0) & (c_life.ask < 1)]
        mid = (two.bid + two.ask) / 2
        contested = two[(mid >= 0.10) & (mid <= 0.90)]
        oi_close = c_life.oi.dropna().iloc[-1] if c_life.oi.notna().any() else float("nan")
        last7 = tr[tr.t >= mend - pd.Timedelta(days=7)]
        mrows.append({
            "event_ticker": event_ticker, "ticker": m["ticker"], "strike": m.get("floor_strike"),
            "strike_type": m.get("strike_type"), "result": m.get("result"),
            "created": m.get("created_time"), "close_time": m["close_time"],
            "closed_early": close < mend - pd.Timedelta(hours=1),
            "settlement_ts": m.get("settlement_ts"),
            "expiration_value": m.get("expiration_value"),
            "volume": num(m.get("volume_fp")), "oi_at_close": oi_close,
            "max_oi": c_life.oi.max(), "n_candles": len(c_life),
            "pct_hours_two_sided": len(two) / len(c_life) if len(c_life) else float("nan"),
            "median_spread": (two.ask - two.bid).median(),
            "median_spread_contested": (contested.ask - contested.bid).median(),
            "n_trades": len(tr), "median_trade": tr["count"].median(),
            "premium_yes_usd": (tr["count"] * tr.yes_price).sum(),
            "vol_last7d": last7["count"].sum(),
            "vol_at_1c_or_99c": tr.loc[(tr.yes_price <= 0.01) | (tr.yes_price >= 0.99), "count"].sum(),
        })
        cfs.append(c)
        tr["ticker"] = m["ticker"]
        trs.append(tr)
    mdf = pd.DataFrame(mrows)
    allc = pd.concat(cfs, ignore_index=True)
    alltr = pd.concat(trs, ignore_index=True)
    two_all = allc[(allc.bid > 0) & (allc.ask < 1)]
    final = mdf.loc[~mdf.closed_early, "expiration_value"]
    first_created = pd.to_datetime(mdf.created, utc=True, format="ISO8601").min()
    added_later = (pd.to_datetime(mdf.created, utc=True, format="ISO8601")
                   > first_created + pd.Timedelta(days=1)).sum()
    settle = pd.to_datetime(mdf.loc[~mdf.closed_early, "settlement_ts"], utc=True,
                            format="ISO8601")
    erow = {
        "event_ticker": event_ticker, "series_ticker": series_ticker,
        "n_strikes": len(mdf), "strikes": ",".join(f"{x:g}" for x in mdf.strike),
        "strikes_added_after_listing": int(added_later),
        "realized_total_in": num(final.iloc[0]) if len(final) else float("nan"),
        "n_closed_early": int(mdf.closed_early.sum()),
        "contracts_traded": mdf.volume.sum(), "premium_yes_usd": mdf.premium_yes_usd.sum(),
        "oi_at_close_sum": mdf.oi_at_close.sum(), "max_oi_sum": mdf.max_oi.sum(),
        "n_trades": int(mdf.n_trades.sum()),
        "median_trade_contracts": alltr["count"].median(),
        "p90_trade_contracts": alltr["count"].quantile(0.9),
        "pct_strike_hours_two_sided": len(two_all) / len(allc) if len(allc) else float("nan"),
        "median_spread_all": (two_all.ask - two_all.bid).median(),
        "median_spread_contested": float(np.nanmedian(
            ((two_all.ask - two_all.bid)[((two_all.bid + two_all.ask) / 2).between(0.10, 0.90)])
        )) if len(two_all) else float("nan"),
        "share_vol_last7d": mdf.vol_last7d.sum() / mdf.volume.sum() if mdf.volume.sum() else np.nan,
        "share_vol_at_1c_99c": mdf.vol_at_1c_or_99c.sum() / alltr["count"].sum()
        if alltr["count"].sum() else np.nan,
        "settle_lag_hours_after_month_end": ((settle.max() - mend).total_seconds() / 3600)
        if len(settle) else np.nan,
    }
    return erow, mrows, allc


# --------------------------------------------------------------------------------------------
# Order-book snapshot for open markets
# --------------------------------------------------------------------------------------------
def _side_depth(offers: list[tuple[float, float]], within: float, max_price: float) -> dict:
    """Depth of one side's offers (price, size), cheapest first."""
    offers = sorted(offers)
    useful = [(p, q) for p, q in offers if p <= max_price + 1e-9]
    if not useful:
        return {"best_ask": float("nan"), "best_ask_size": 0.0, "buyable_within_5c": 0.0,
                "cost_within_5c_usd": 0.0, "buyable_useful": 0.0, "cost_useful_usd": 0.0}
    best = useful[0][0]
    near = [(p, q) for p, q in useful if p <= best + within + 1e-9]
    return {"best_ask": best, "best_ask_size": sum(q for p, q in useful if p == best),
            "buyable_within_5c": sum(q for _, q in near),
            "cost_within_5c_usd": sum(p * q for p, q in near),
            "buyable_useful": sum(q for _, q in useful),
            "cost_useful_usd": sum(p * q for p, q in useful)}


def book_depth(ob: dict, within: float = 0.05, max_price: float = 0.95) -> dict:
    """Summarize an order book from both a YES buyer's and a NO buyer's point of view.

    The book lists bids only: yes_dollars = bids to buy YES, no_dollars = bids to buy NO.
    A NO bid at q is a YES offer at 1 - q, and a YES bid at q is a NO offer at 1 - q.
    For an "Above X inches" market a farmer hedging DROUGHT buys NO (pays $1 if the month's
    total is X inches or less); a farmer hedging a WET month buys YES.
    Offers priced above ``max_price`` (e.g. a 1-cent bid on the other side, which shows up as a
    99-cent offer) are excluded from the "useful" totals.
    """
    book = ob.get("orderbook_fp") or ob.get("orderbook") or {}
    yes_bids = [(num(p), num(q)) for p, q in (book.get("yes_dollars") or [])]
    no_bids = [(num(p), num(q)) for p, q in (book.get("no_dollars") or [])]
    yes_side = _side_depth([(round(1 - p, 4), q) for p, q in no_bids], within, max_price)
    no_side = _side_depth([(round(1 - p, 4), q) for p, q in yes_bids], within, max_price)
    best_yes_bid = max((p for p, _ in yes_bids), default=float("nan"))
    yes_ask_any = min((round(1 - p, 4) for p, _ in no_bids), default=float("nan"))
    return {
        "best_yes_bid": best_yes_bid, "best_yes_ask": yes_ask_any,
        "spread": yes_ask_any - best_yes_bid,
        **{f"yes_{k}": v for k, v in yes_side.items()},
        **{f"no_{k}": v for k, v in no_side.items()},
        "n_yes_bid_levels": len(yes_bids), "n_no_bid_levels": len(no_bids),
    }


def walk_book(ob: dict, side: str, target: float, max_price: float = 0.95) -> dict:
    """Fill ``target`` contracts of ``side`` ("YES" or "NO") by lifting offers cheapest first.

    Returns contracts filled, total premium (dollars), average price, and the taker fee if the
    whole fill were one order (quadratic fee, 7% coefficient, rounded up to the cent).
    """
    book = ob.get("orderbook_fp") or {}
    other = book.get("no_dollars" if side == "YES" else "yes_dollars") or []
    offers = sorted((round(1 - num(p), 4), num(q)) for p, q in other)
    filled = cost = fee = 0.0
    for p, q in offers:
        if p > max_price + 1e-9 or filled >= target:
            break
        take = min(q, target - filled)
        filled += take
        cost += take * p
        fee += taker_fee(take, p, round_to=None)
    return {"side": side, "target": target, "filled": filled, "premium_usd": cost,
            "avg_price": cost / filled if filled else float("nan"),
            "fee_usd": math.ceil(round(fee * 100, 9)) / 100 if filled else 0.0}


def hedge_fill_table(raw_books: dict, strikes=(1, 2), targets=(100, 1000, 10000),
                     event_suffix: str = "-26NOV") -> pd.DataFrame:
    """Drought-hedge fills: buy NO on 'Above k inches' for each study-site Nov 2026 ladder."""
    rows = []
    for tk, ob in raw_books.items():
        if event_suffix not in tk or not any(tk.endswith(f"-{k}") for k in strikes):
            continue
        for tgt in targets:
            rows.append({"ticker": tk, **walk_book(ob, "NO", tgt)})
    return pd.DataFrame(rows)


def snapshot_orderbooks(series_list: list[str]) -> pd.DataFrame:
    """Snapshot every open market of the given series (no cache; saved with a timestamp)."""
    now = datetime.now(timezone.utc)
    rows, raw = [], {}
    for s in series_list:
        ms = paginate("/markets", "markets", {"series_ticker": s, "status": "open"}, cache=False)
        for m in ms:
            ob = kalshi_get(f"/markets/{m['ticker']}/orderbook", cache=False)
            raw[m["ticker"]] = ob
            rows.append({"snapshot_utc": now.isoformat(timespec="seconds"), "series_ticker": s,
                         "event_ticker": m["event_ticker"], "ticker": m["ticker"],
                         "strike": m.get("floor_strike"), "close_time": m.get("close_time"),
                         "volume": num(m.get("volume_fp")),
                         "open_interest": num(m.get("open_interest_fp")),
                         "last_price": num(m.get("last_price_dollars")),
                         **book_depth(ob)})
    stamp = now.strftime("%Y%m%dT%H%MZ")
    (OUT / f"orderbooks_{stamp}.json").write_text(json.dumps(raw), encoding="utf-8")
    hedge_fill_table(raw).to_csv(OUT / "r5_drought_hedge_fills.csv", index=False)
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------------------------
# Figures
# --------------------------------------------------------------------------------------------
def plot_price_paths(cdict: dict, mdfs: pd.DataFrame, events: list[str], path: Path) -> None:
    """Daily closing YES mid (or last trade) per strike over the month, one panel per event."""
    fig, axes = plt.subplots(2, 2, figsize=(11, 7.5), sharey=True)
    styles = ["-", "--", ":", "-."]
    for ax, ev in zip(axes.flat, events):
        c = cdict[ev].copy()
        c["mid"] = np.where((c.bid > 0) & (c.ask < 1), (c.bid + c.ask) / 2, c["last"])
        c["day"] = c.t.dt.tz_convert(ET).dt.floor("D")
        m = mdfs[mdfs.event_ticker == ev].set_index("ticker")
        for i, (tk, g) in enumerate(c.groupby("ticker", sort=False)):
            daily = g.groupby("day").mid.last().dropna()
            if daily.empty:
                continue
            res = m.loc[tk, "result"] if tk in m.index else ""
            ax.plot(daily.index, daily.values, styles[i % 4], color=str(0.15 + 0.1 * (i % 7)),
                    lw=1.4, label=f">{m.loc[tk, 'strike']:g} in ({res})")
        realized = mdfs.loc[(mdfs.event_ticker == ev) & ~mdfs.closed_early, "expiration_value"]
        rv = num(realized.iloc[0]) if len(realized) else float("nan")
        label = f"settled total {rv:.2f} in" if not math.isnan(rv) else "value not in API"
        ax.set_title(f"{ev}  ({label})", fontsize=10)
        ax.set_ylabel("YES price (dollars per $1 contract)")
        ax.set_ylim(-0.02, 1.02)
        ax.tick_params(axis="x", rotation=30, labelsize=8)
        ax.legend(fontsize=7, ncol=2, loc="center left")
        ax.grid(alpha=0.3)
    fig.suptitle("Kalshi monthly-rain ladders: daily YES price by strike "
                 "(mid of bid/ask when two-sided, else last trade)", fontsize=11)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_depth(book: pd.DataFrame, path: Path) -> None:
    """Drought-hedge depth: NO contracts offered within 5c of the best NO ask, per strike/site."""
    nov = book[book.event_ticker.str.endswith("-26NOV")].copy()
    sites = sorted(nov.series_ticker.unique())
    fig, ax = plt.subplots(figsize=(11, 5))
    width = 0.8 / max(len(sites), 1)
    hatches = ["", "//", "\\\\", "xx", "..", "--", "++", "oo"]
    strikes = sorted(nov.strike.dropna().unique())
    for i, s in enumerate(sites):
        d = nov[nov.series_ticker == s].set_index("strike").reindex(strikes)
        vals = d.no_buyable_within_5c.where(d.no_buyable_within_5c > 0)  # no bar = no offer
        ax.bar(np.arange(len(strikes)) + i * width, vals,
               width, color=str(0.15 + 0.7 * i / max(len(sites) - 1, 1)), edgecolor="black",
               hatch=hatches[i % len(hatches)], label=s.replace("KXRAIN", "").rstrip("M"))
    ax.set_yscale("log")
    ax.set_xticks(np.arange(len(strikes)) + 0.4 - width / 2)
    ax.set_xticklabels([f"Above {x:g} in" for x in strikes])
    ax.set_xlabel("Market (NO pays $1 if the Nov 2026 total is at or below the strike). "
                  "Missing bar = no NO offer at or below 95 cents.")
    ax.set_ylabel("NO contracts offered within 5c of best ask (log scale)")
    snap = nov.snapshot_utc.iloc[0] if len(nov) else ""
    ax.set_title(f"How much drought protection is on the book: Nov 2026 monthly-rain markets "
                 f"(snapshot {str(snap)[:16].replace('T', ' ')} UTC)", fontsize=10)
    ax.set_ylim(bottom=1)
    ax.legend(fontsize=8, ncol=8, title="Kalshi city code", title_fontsize=8,
              loc="upper center", bbox_to_anchor=(0.5, -0.2), frameon=False)
    ax.grid(axis="y", alpha=0.3, which="both")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def site_summary(book: pd.DataFrame, event_suffix: str = "-26NOV") -> pd.DataFrame:
    """One row per series for the given event month: spreads and purchasable depth."""
    b = book[book.event_ticker.str.endswith(event_suffix)]
    two = b[b.best_yes_bid.gt(0) & b.best_yes_ask.lt(1)]
    g, g2 = b.groupby("series_ticker"), two.groupby("series_ticker")
    return pd.DataFrame({
        "snapshot_utc": g.snapshot_utc.first(), "n_strikes": g.size(),
        "n_two_sided": g2.size().reindex(g.size().index).fillna(0).astype(int),
        "median_spread": g2.spread.median(), "max_spread": g2.spread.max(),
        "median_no_best_ask_size": g.no_best_ask_size.median(),
        "no_within_5c_total": g.no_buyable_within_5c.sum(),
        "no_within_5c_cost_usd": g.no_cost_within_5c_usd.sum(),
        "no_within_5c_min_strike": g.no_buyable_within_5c.min(),
        "yes_within_5c_total": g.yes_buyable_within_5c.sum(),
        "contracts_traded_so_far": g.volume.sum(),
    }).reset_index()


def city_history_summary(hist: pd.DataFrame) -> pd.DataFrame:
    """Per series: number of events, first event, and contracts traded per event."""
    h = hist.copy()
    g = h.groupby("series_ticker")
    return pd.DataFrame({
        "events": g.size(), "first_open": g.first_open.min(),
        "median_contracts_per_event": g.contracts_traded.median(),
        "max_contracts_per_event": g.contracts_traded.max(),
        "total_contracts": g.contracts_traded.sum(),
    }).sort_values("total_contracts", ascending=False).reset_index()


# --------------------------------------------------------------------------------------------
def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    sites = {**STUDY_SITES, **CONTRAST_SITES}
    site_series = [v["kalshi_series"] for v in sites.values()]

    print("1) catalog of weather product families ...")
    cat = catalog_activity()
    cat.to_csv(OUT / "r5_series_catalog.csv", index=False)
    fam = family_table(cat)
    fam.to_csv(OUT / "r5_family_table.csv", index=False)
    print(fam.to_string(index=False))

    print("2) monthly-rain event history ...")
    rain_series = sorted(cat.loc[cat.family == "Rain, monthly total", "series_ticker"])
    rain_series = [s for s in rain_series if not s.startswith("RAIN")]  # legacy listed under KX
    hist = rain_history(rain_series)
    hist.to_csv(OUT / "r5_rain_event_history.csv", index=False)

    print("3) deep dive on sampled settled events ...")
    erows, mrows, cdict = [], [], {}
    for s, ev in SAMPLE_EVENTS:
        e, mr, c = summarize_event(s, ev)
        erows.append(e)
        mrows += mr
        cdict[ev] = c
        print(f"   {ev}: {e['n_strikes']} strikes, {e['contracts_traded']:.0f} contracts")
    edf, mdf = pd.DataFrame(erows), pd.DataFrame(mrows)
    edf.to_csv(OUT / "r5_sample_events.csv", index=False)
    mdf.to_csv(OUT / "r5_sample_markets.csv", index=False)

    print("4) order-book snapshot of open monthly-rain markets for study sites ...")
    book = snapshot_orderbooks(site_series)
    book.to_csv(OUT / "r5_orderbook_snapshot.csv", index=False)
    site_summary(book).to_csv(OUT / "r5_orderbook_site_summary.csv", index=False)
    print(site_summary(book).to_string(index=False))

    print("   per-city monthly-rain history ...")
    city_history_summary(hist).to_csv(OUT / "r5_rain_city_history_summary.csv", index=False)

    print("5) figures ...")
    plot_price_paths(cdict, mdf, ["KXRAINDALM-26MAY", "KXRAINDENM-26JUL",
                                  "KXRAINCHIM-26APR", "KXRAINDALM-26SEP"],
                     FIGURES / "r5_rain_ladder_price_paths.png")
    plot_depth(book, FIGURES / "r5_orderbook_depth_nov2026.png")

    print("Worked fee example: 100 contracts at $0.20 ->",
          f"${taker_fee(100, 0.20):.2f} (one order) vs",
          f"${100 * taker_fee(1, 0.20):.2f} (100 one-contract orders, old per-order cent rounding)")
    print("done")


if __name__ == "__main__":
    main()
