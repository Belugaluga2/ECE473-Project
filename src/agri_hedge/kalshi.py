"""Kalshi public market-data client, response parsers, fee model, and ladder helpers.

Everything here uses Kalshi's unauthenticated REST market-data endpoints
(https://docs.kalshi.com, base URL in ``agri_hedge.config.KALSHI_BASE_URL``). No API key is
needed for any function in this module.

Field-name migration (checked against live responses on 2026-10-29)
-------------------------------------------------------------------
Kalshi moved to fixed-point string fields ("Fixed-Point Representation",
https://docs.kalshi.com/getting_started/fixed_point_migration, last updated 2026-08-20):

* prices are dollar strings with a ``_dollars`` suffix, e.g. ``yes_bid_dollars = "0.0400"``;
* contract counts are strings with an ``_fp`` suffix and may be fractional, e.g.
  ``volume_fp = "1259.11"``, ``open_interest_fp``, ``count_fp`` (trades);
* the legacy integer-cent fields (``yes_bid``, ``yes_ask``, ``last_price``, ``volume``,
  ``open_interest``, ``liquidity``) are no longer returned, which is why they read as None.
  ``liquidity`` has no replacement on market objects; use the order book instead.

Endpoint quirks this module handles:

* live candlesticks use ``price.close_dollars``, ``volume_fp``, ``open_interest_fp``; the
  historical candlestick endpoint uses ``price.close``, ``volume``, ``open_interest`` (still dollar
  and contract strings, just without suffixes). ``_price``/``_count`` accept every variant and
  treat bare integers as legacy cents.
* the order book is ``{"orderbook_fp": {"yes_dollars": [[price, size], ...], "no_dollars": ...}}``.
  Both lists are BIDS. The YES ask is 1 minus the best NO bid.
* market ``status`` values are ``initialized``, ``active``, ``closed``, ``finalized`` ... but the
  ``status`` query filter takes ``unopened|open|paused|closed|settled``.
* markets that settled before ``GET /historical/cutoff`` -> ``market_settled_ts`` exist only under
  ``/historical/markets`` (``GET /markets/{ticker}`` returns 404 for them), and their candles only
  under ``/historical/markets/{ticker}/candlesticks``. Trades before ``trades_created_ts`` exist
  only under ``/historical/trades``. Events and series are never archived.
* page-size caps: /markets, /historical/markets, trades: 1000; /events: 200 (larger -> HTTP 400);
  /incentive_programs: 10000 and its cursor field is ``next_cursor`` (not ``cursor``).
* legacy-ticker events (e.g. ``RAINNYCM-24OCT``) are listed under the KX series
  (``/events?series_ticker=KXRAINNYCM``); ``/events?series_ticker=RAINNYCM`` is empty.
* ``expiration_value`` is a free-text string: ``"3.5"``, ``"0.61 inches"``, ``""`` or ``"Yes"``.
  On "greater than" rain markets that close early (``can_close_early``), it is the running total
  at the early close, not the final monthly total.
"""
from __future__ import annotations

import calendar
import json
import math
import re
import time
from datetime import datetime, timezone
from decimal import ROUND_CEILING, Decimal
from pathlib import Path

import requests

from agri_hedge.config import KALSHI_BASE_URL

RETRY_STATUSES = {429, 500, 502, 503, 504}
PAGE_LIMITS = {"/events": 200}  # every other paginated endpoint accepts limit=1000
DEFAULT_PAGE_LIMIT = 1000


class KalshiAPIError(RuntimeError):
    """Non-retryable HTTP error from the Kalshi API (status_code holds the HTTP status)."""

    def __init__(self, status_code, url, body=""):
        super().__init__(f"HTTP {status_code} for {url}: {body[:200]}")
        self.status_code = status_code
        self.url = url


# ---------------------------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------------------------
class KalshiClient:
    """Small unauthenticated REST client with politeness delay, retries, and cursor pagination.

    Args:
        base_url: API root, default ``KALSHI_BASE_URL``.
        session: anything with a ``requests.Session``-like ``get(url, params=, timeout=)``
            method (tests pass a fake).
        delay: minimum seconds between consecutive requests (politeness; default 0.2 s).
        max_retries: retries on HTTP 429/5xx and connection errors.
        backoff: base seconds for exponential backoff (backoff * 2**attempt, capped at 60 s);
            a ``Retry-After`` header, when present, takes precedence.
        timeout: per-request timeout in seconds.
        sleep: injectable sleep function (tests pass a no-op).
    """

    def __init__(self, base_url=KALSHI_BASE_URL, session=None, delay=0.2, max_retries=6,
                 backoff=1.0, timeout=30, sleep=time.sleep):
        self.base_url = base_url.rstrip("/")
        self.session = session if session is not None else requests.Session()
        self.delay = delay
        self.max_retries = max_retries
        self.backoff = backoff
        self.timeout = timeout
        self._sleep = sleep
        self._last_request = 0.0
        self.n_requests = 0

    # -- transport ------------------------------------------------------------------------
    def get(self, path, params=None):
        """GET ``base_url + path`` and return parsed JSON, retrying on 429/5xx with backoff."""
        url = self.base_url + path
        params = {k: v for k, v in (params or {}).items() if v is not None}
        for attempt in range(self.max_retries + 1):
            wait = self.delay - (time.monotonic() - self._last_request)
            if wait > 0:
                self._sleep(wait)
            self._last_request = time.monotonic()
            self.n_requests += 1
            try:
                resp = self.session.get(url, params=params, timeout=self.timeout)
            except (requests.ConnectionError, requests.Timeout):
                if attempt == self.max_retries:
                    raise
                self._sleep(min(60.0, self.backoff * 2 ** attempt))
                continue
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code in RETRY_STATUSES and attempt < self.max_retries:
                retry_after = (getattr(resp, "headers", None) or {}).get("Retry-After")
                try:
                    pause = float(retry_after)
                except (TypeError, ValueError):
                    pause = min(60.0, self.backoff * 2 ** attempt)
                self._sleep(pause)
                continue
            raise KalshiAPIError(resp.status_code, url, getattr(resp, "text", ""))
        raise KalshiAPIError(-1, url, "retries exhausted")  # pragma: no cover

    def paginate(self, path, key, params=None, limit=None, max_pages=10_000, cursor_key="cursor"):
        """Follow Kalshi cursor pagination and return the concatenated ``key`` lists.

        Stops when the returned cursor is empty/None, repeats (defensive), or after
        ``max_pages`` pages. ``cursor_key`` is the response field holding the next cursor
        ("cursor" everywhere except /incentive_programs, which uses "next_cursor").
        """
        params = dict(params or {})
        params["limit"] = limit or PAGE_LIMITS.get(path, DEFAULT_PAGE_LIMIT)
        out, cursor, seen = [], None, set()
        for _ in range(max_pages):
            if cursor:
                params["cursor"] = cursor
            page = self.get(path, params)
            out.extend(page.get(key) or [])
            cursor = page.get(cursor_key)
            if not cursor or cursor in seen:
                break
            seen.add(cursor)
        return out

    # -- series / events / markets ---------------------------------------------------------
    def list_series(self, category=None, tags=None):
        """All series, optionally filtered by category (e.g. "Climate and Weather")."""
        return self.paginate("/series", "series", {"category": category, "tags": tags})

    def get_series(self, series_ticker):
        return self.get(f"/series/{series_ticker}")["series"]

    def list_events(self, series_ticker=None, status=None, with_nested_markets=False):
        params = {"series_ticker": series_ticker, "status": status}
        if with_nested_markets:
            params["with_nested_markets"] = "true"
        return self.paginate("/events", "events", params)

    def get_event(self, event_ticker):
        return self.get(f"/events/{event_ticker}")

    def list_markets(self, series_ticker=None, status=None, event_ticker=None, tickers=None,
                     **filters):
        """Live-tier markets. ``status`` in {unopened, open, paused, closed, settled} or None
        (all). Extra filters (min_close_ts, max_close_ts, min_settled_ts, ...) pass through."""
        params = {"series_ticker": series_ticker, "status": status,
                  "event_ticker": event_ticker, "tickers": tickers, **filters}
        return self.paginate("/markets", "markets", params)

    def get_market(self, ticker):
        return self.get(f"/markets/{ticker}")["market"]

    def get_orderbook(self, ticker, depth=None):
        """Raw order book JSON (``orderbook_fp`` with ``yes_dollars``/``no_dollars`` bid lists)."""
        return self.get(f"/markets/{ticker}/orderbook", {"depth": depth})

    def get_candlesticks(self, series_ticker, ticker, start_ts, end_ts, period_interval=1440):
        """Live-tier candlesticks (period_interval in minutes: 1, 60 or 1440)."""
        return self.get(f"/series/{series_ticker}/markets/{ticker}/candlesticks",
                        {"start_ts": int(start_ts), "end_ts": int(end_ts),
                         "period_interval": period_interval}).get("candlesticks") or []

    def list_trades(self, ticker=None, min_ts=None, max_ts=None):
        return self.paginate("/markets/trades", "trades",
                             {"ticker": ticker, "min_ts": min_ts, "max_ts": max_ts})

    def list_incentive_programs(self, status=None, incentive_type=None):
        """Liquidity/volume incentive programs (GET /incentive_programs). ``status`` in
        {all, active, upcoming, closed, paid_out}; ``period_reward`` is in centi-cents
        (1/10000 dollar)."""
        return self.paginate("/incentive_programs", "incentive_programs",
                             {"status": status, "type": incentive_type}, limit=10000,
                             cursor_key="next_cursor")

    # -- historical tier ---------------------------------------------------------------------
    def historical_cutoff(self):
        """Dict of cutoff timestamps: market_settled_ts, trades_created_ts, orders_updated_ts,
        market_positions_last_updated_ts (ISO strings)."""
        return self.get("/historical/cutoff")

    def list_historical_markets(self, series_ticker=None, event_ticker=None, tickers=None):
        return self.paginate("/historical/markets", "markets",
                             {"series_ticker": series_ticker, "event_ticker": event_ticker,
                              "tickers": tickers})

    def get_historical_market(self, ticker):
        return self.get(f"/historical/markets/{ticker}")["market"]

    def get_historical_candlesticks(self, ticker, start_ts, end_ts, period_interval=1440):
        return self.get(f"/historical/markets/{ticker}/candlesticks",
                        {"start_ts": int(start_ts), "end_ts": int(end_ts),
                         "period_interval": period_interval}).get("candlesticks") or []

    def list_historical_trades(self, ticker=None, min_ts=None, max_ts=None):
        return self.paginate("/historical/trades", "trades",
                             {"ticker": ticker, "min_ts": min_ts, "max_ts": max_ts})

    # -- convenience: live + historical combined --------------------------------------------
    def list_all_markets(self, series_ticker):
        """Every market ever listed for a series (live tier first, then historical), deduped by
        ticker. Each raw dict gets a ``_tier`` key ("live" or "historical")."""
        seen, out = set(), []
        for tier, fetch in (("live", self.list_markets), ("historical", self.list_historical_markets)):
            for m in fetch(series_ticker=series_ticker):
                if m["ticker"] not in seen:
                    seen.add(m["ticker"])
                    out.append({**m, "_tier": tier})
        return out

    def get_candles_any(self, series_ticker, ticker, start_ts, end_ts, historical,
                        period_interval=1440):
        """Candles from the right tier; falls back to the other tier if the first is empty/404."""
        order = [True, False] if historical else [False, True]
        for hist in order:
            try:
                if hist:
                    c = self.get_historical_candlesticks(ticker, start_ts, end_ts, period_interval)
                else:
                    c = self.get_candlesticks(series_ticker, ticker, start_ts, end_ts,
                                              period_interval)
            except KalshiAPIError as e:
                if e.status_code in (400, 404):
                    continue
                raise
            if c:
                return c, ("historical" if hist else "live")
        return [], None

    def list_all_trades(self, ticker):
        """Trades from both tiers, deduped by trade_id (a market's trades can straddle the
        trades cutoff)."""
        out, seen = [], set()
        for fetch in (self.list_trades, self.list_historical_trades):
            for t in fetch(ticker=ticker):
                if t.get("trade_id") not in seen:
                    seen.add(t.get("trade_id"))
                    out.append(t)
        return out


_DEFAULT_CLIENT = None


def default_client():
    """Module-level shared client (lazily created)."""
    global _DEFAULT_CLIENT
    if _DEFAULT_CLIENT is None:
        _DEFAULT_CLIENT = KalshiClient()
    return _DEFAULT_CLIENT


# Module-level wrappers so callers can do ``kalshi.list_markets("KXRAINDALM", "open")``.
def list_series(category=None):
    return default_client().list_series(category)


def get_series(series_ticker):
    return default_client().get_series(series_ticker)


def list_events(series_ticker):
    return default_client().list_events(series_ticker)


def list_markets(series_ticker=None, status=None, **filters):
    return default_client().list_markets(series_ticker, status, **filters)


def get_market(ticker):
    return default_client().get_market(ticker)


def get_orderbook(ticker, depth=None):
    return default_client().get_orderbook(ticker, depth)


def get_candlesticks(series_ticker, ticker, start_ts, end_ts, period_interval=1440):
    return default_client().get_candlesticks(series_ticker, ticker, start_ts, end_ts,
                                             period_interval)


def list_trades(ticker=None, min_ts=None, max_ts=None):
    return default_client().list_trades(ticker, min_ts, max_ts)


def historical_cutoff():
    return default_client().historical_cutoff()


def list_historical_markets(series_ticker=None, event_ticker=None, tickers=None):
    return default_client().list_historical_markets(series_ticker, event_ticker, tickers)


def get_historical_candlesticks(ticker, start_ts, end_ts, period_interval=1440):
    return default_client().get_historical_candlesticks(ticker, start_ts, end_ts,
                                                        period_interval)


def list_historical_trades(ticker=None, min_ts=None, max_ts=None):
    return default_client().list_historical_trades(ticker, min_ts, max_ts)


# ---------------------------------------------------------------------------------------------
# Raw JSON cache helper
# ---------------------------------------------------------------------------------------------
def load_or_fetch_json(path, fetch, max_age_s=None, refresh=False):
    """Return JSON cached at ``path``; call ``fetch()`` and save if missing, stale, or refresh.

    ``max_age_s=None`` means a cached file never goes stale (use for settled markets).
    """
    path = Path(path)
    if path.exists() and not refresh:
        age = time.time() - path.stat().st_mtime
        if max_age_s is None or age <= max_age_s:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
    data = fetch()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f)
    tmp.replace(path)
    return data


# ---------------------------------------------------------------------------------------------
# Field normalisation
# ---------------------------------------------------------------------------------------------
def to_float(x):
    """float(x) for numbers and numeric strings; NaN for None, '' and non-numeric strings."""
    if x is None or isinstance(x, bool):
        return math.nan
    if isinstance(x, (int, float)):
        return float(x)
    try:
        return float(str(x).strip())
    except ValueError:
        return math.nan


def _price(obj, base):
    """Dollar price from ``<base>_dollars`` (new) or ``<base>`` (historical dollar string, or
    legacy integer cents). Returns NaN if absent."""
    if not isinstance(obj, dict):
        return math.nan
    v = obj.get(f"{base}_dollars")
    if v is not None:
        return to_float(v)
    v = obj.get(base)
    if v is None:
        return math.nan
    if isinstance(v, str):
        return to_float(v)
    return float(v) / 100.0  # legacy integer cents


def _count(obj, base):
    """Contract count from ``<base>_fp`` (new) or ``<base>`` (historical string / legacy int)."""
    if not isinstance(obj, dict):
        return math.nan
    v = obj.get(f"{base}_fp")
    if v is None:
        v = obj.get(base)
    return to_float(v)


def parse_number(text):
    """First number in a free-text field such as expiration_value ('0.61 inches' -> 0.61)."""
    if text is None:
        return math.nan
    if isinstance(text, (int, float)):
        return float(text)
    m = re.search(r"-?\d+(?:\.\d+)?", str(text))
    return float(m.group()) if m else math.nan


def iso_to_ts(s):
    """ISO-8601 'Z' string -> Unix seconds (float); NaN for None/''."""
    if not s:
        return math.nan
    return datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()


_MONTHS = {m.upper(): i for i, m in enumerate(calendar.month_abbr) if m}
_RULE_RE = re.compile(
    r"at\s+(?P<station>.+?)\s+in\s+(?P<month>[A-Z][a-z]+)\s+(?P<year>\d{4})"
    r"(?:\s+through\s+(?P<month2>[A-Z][a-z]+)\s+(?P<year2>\d{4}))?\s+is\s+strictly\s+"
    r"(?P<dir>greater|less)\s+than\s+(?P<strike>-?\d+(?:\.\d+)?)", re.S)
_CLI_RE = re.compile(r"\bCLI[A-Z0-9]{3,4}\b")


def parse_cli_code(text):
    """First NWS climate-report code ('CLIDFW') in a rules string, else ''."""
    m = _CLI_RE.search(text or "")
    return m.group() if m else ""


def parse_rain_rules(rules_primary):
    """Parse a monthly-rain rules_primary string.

    Example: 'If the total precipitation at CLIDFW in Dallas in Oct 2026 is strictly greater
    than 3 inches, then the market resolves to Yes.' ->
    {'station_text': 'CLIDFW in Dallas', 'cli_code': 'CLIDFW', 'city': 'Dallas',
     'contract_month': '2026-10', 'direction': 'greater', 'strike': 3.0}
    Older NYC text uses 'at Central Park, New York City in Oct 2024'; Napa uses an ICAO code and
    a full month name ('at KAPC in Napa in December 2026').
    """
    out = {"station_text": "", "cli_code": "", "city": "", "contract_month": "",
           "direction": "", "strike": math.nan}
    text = rules_primary or ""
    m = _RULE_RE.search(text)
    if not m:
        out["cli_code"] = parse_cli_code(text)
        return out
    station = m.group("station").strip()
    out["station_text"] = station
    out["cli_code"] = parse_cli_code(station)
    sm = re.match(r"(\S+)\s+in\s+(.+)$", station)
    if sm:
        out["city"] = sm.group(2).strip()
    elif "," in station:  # "Central Park, New York City"
        out["city"] = station.split(",", 1)[1].strip()
    else:
        out["city"] = station
    mon = _MONTHS.get(m.group("month")[:3].upper())
    if mon:
        out["contract_month"] = f"{m.group('year')}-{mon:02d}"
    out["direction"] = m.group("dir")
    out["strike"] = float(m.group("strike"))
    return out


def event_contract_month(event_ticker):
    """'KXRAINDALM-26OCT' -> '2026-10'; 'KXRAINNAPAM-01DEC26-31DEC26' -> '2026-12'; else ''."""
    parts = (event_ticker or "").split("-")[1:]
    for p in parts:
        m = re.fullmatch(r"(\d{2})([A-Z]{3})", p)  # YYMON, monthly events
        if m and m.group(2) in _MONTHS:
            return f"20{m.group(1)}-{_MONTHS[m.group(2)]:02d}"
    # DDMONYY-DDMONYY date ranges (Napa). A lone 7-char date is ambiguous (daily series use
    # YYMONDD), so require a start-end pair and report the start month.
    ranges = [re.fullmatch(r"\d{2}([A-Z]{3})(\d{2})", p) for p in parts]
    ranges = [m for m in ranges if m and m.group(1) in _MONTHS]
    if len(ranges) >= 2:
        return f"20{ranges[0].group(2)}-{_MONTHS[ranges[0].group(1)]:02d}"
    return ""


def market_strike(m):
    """Strike (inches) for a binary 'greater'/'less' market, with fallbacks for markets whose
    strike_type/floor_strike are missing (seen on a few 2025 NYC markets)."""
    st = m.get("strike_type")
    if st in ("greater", "greater_or_equal") and m.get("floor_strike") is not None:
        return float(m["floor_strike"])
    if st in ("less", "less_or_equal") and m.get("cap_strike") is not None:
        return float(m["cap_strike"])
    parsed = parse_rain_rules(m.get("rules_primary")).get("strike")
    if not math.isnan(parsed):
        return parsed
    tail = (m.get("ticker") or "").rsplit("-", 1)[-1].lstrip("T")
    return to_float(tail)


MARKET_COLUMNS = [
    "ticker", "event_ticker", "series_ticker", "tier", "title", "yes_sub_title", "city",
    "station_text", "cli_code", "contract_month", "strike", "strike_type", "floor_strike",
    "cap_strike", "station_code", "period_start", "period_end", "is_single_month", "created_time", "open_time", "close_time", "expected_expiration_time",
    "expiration_time", "latest_expiration_time", "settlement_ts", "status", "result",
    "expiration_value_text", "expiration_value", "settlement_value", "can_close_early",
    "volume", "volume_24h", "open_interest", "last_price", "previous_price", "yes_bid", "yes_ask",
    "no_bid", "no_ask", "yes_bid_size", "yes_ask_size", "liquidity", "notional_value",
    "price_level_structure", "tick_size", "fee_waiver_expiration_time", "rules_primary",
    "rules_secondary",
]


def parse_market(m, series_ticker=None, tier=None):
    """Flatten one raw market dict (old or new field names) into a row (see MARKET_COLUMNS).

    Prices are in dollars per contract (0-1), counts in contracts. ``strike_type`` is filled
    from the rules text when missing.
    """
    rules = parse_rain_rules(m.get("rules_primary"))
    ranges = m.get("price_ranges") or []
    ticks = [to_float(r.get("step")) for r in ranges if isinstance(r, dict)]
    ev = m.get("event_ticker") or ""
    liquidity = _price(m, "liquidity")
    month = event_contract_month(ev) or rules["contract_month"]
    custom = m.get("custom_strike") if isinstance(m.get("custom_strike"), dict) else {}
    if month:
        y, mo = int(month[:4]), int(month[5:7])
        start = f"{month}-01"
        end = f"{month}-{calendar.monthrange(y, mo)[1]:02d}"
    else:
        start = end = ""
    start = custom.get("start_date") or start
    end = custom.get("end_date") or end
    row = {
        "ticker": m.get("ticker"),
        "event_ticker": ev,
        "series_ticker": series_ticker or ev.split("-")[0],
        "tier": tier or m.get("_tier") or "",
        "title": m.get("title"),
        "yes_sub_title": m.get("yes_sub_title") or m.get("subtitle"),
        "city": rules["city"],
        "station_text": rules["station_text"],
        "cli_code": rules["cli_code"] or parse_cli_code(m.get("rules_secondary")),
        "contract_month": month,
        "strike": market_strike(m),
        "strike_type": m.get("strike_type") or rules["direction"] or None,
        "floor_strike": to_float(m.get("floor_strike")),
        "cap_strike": to_float(m.get("cap_strike")),
        "station_code": rules["cli_code"] or custom.get("station") or "",
        "period_start": start,
        "period_end": end,
        "is_single_month": bool(start and end and start[:7] == end[:7]),
        "created_time": m.get("created_time"),
        "open_time": m.get("open_time"),
        "close_time": m.get("close_time"),
        "expected_expiration_time": m.get("expected_expiration_time"),
        "expiration_time": m.get("expiration_time"),
        "latest_expiration_time": m.get("latest_expiration_time"),
        "settlement_ts": m.get("settlement_ts"),
        "status": m.get("status"),
        "result": m.get("result") or "",
        "expiration_value_text": m.get("expiration_value") or "",
        "expiration_value": parse_number(m.get("expiration_value")),
        "settlement_value": _price(m, "settlement_value"),
        "can_close_early": bool(m.get("can_close_early")),
        "volume": _count(m, "volume"),
        "volume_24h": _count(m, "volume_24h"),
        "open_interest": _count(m, "open_interest"),
        "last_price": _price(m, "last_price"),
        "previous_price": _price(m, "previous_price"),
        "yes_bid": _price(m, "yes_bid"),
        "yes_ask": _price(m, "yes_ask"),
        "no_bid": _price(m, "no_bid"),
        "no_ask": _price(m, "no_ask"),
        "yes_bid_size": _count(m, "yes_bid_size"),
        "yes_ask_size": _count(m, "yes_ask_size"),
        "liquidity": liquidity,
        "notional_value": _price(m, "notional_value"),
        "price_level_structure": m.get("price_level_structure"),
        "tick_size": min(ticks) if ticks else math.nan,
        "fee_waiver_expiration_time": m.get("fee_waiver_expiration_time"),
        "rules_primary": m.get("rules_primary"),
        "rules_secondary": m.get("rules_secondary"),
    }
    return row


def parse_candles(candles, ticker=None):
    """Flatten candlesticks (live ``*_dollars``/``*_fp`` or historical bare names) into rows.

    Columns: ticker, end_period_ts, date (UTC calendar date of the period end; Kalshi daily
    candles end at 04:00 UTC = midnight US Eastern daylight time, so 'date' D covers the Eastern
    calendar day D-1), price_open/high/
    low/close/mean/previous, yes_bid_open/high/low/close, yes_ask_open/high/low/close, volume,
    open_interest. Price fields are NaN when no trade happened in the period.
    """
    rows = []
    for c in candles or []:
        ts = int(c.get("end_period_ts"))
        row = {"ticker": ticker or c.get("ticker"), "end_period_ts": ts,
               "date": datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")}
        for block, fields in (("price", ("open", "high", "low", "close", "mean", "previous")),
                              ("yes_bid", ("open", "high", "low", "close")),
                              ("yes_ask", ("open", "high", "low", "close"))):
            sub = c.get(block) or {}
            for f in fields:
                row[f"{block}_{f}"] = _price(sub, f)
        row["volume"] = _count(c, "volume")
        row["open_interest"] = _count(c, "open_interest")
        rows.append(row)
    return rows


def parse_trades(trades):
    """Flatten trades into rows: trade_id, ticker, created_time, created_ts, yes_price,
    no_price, count, taker_side, is_block_trade."""
    rows = []
    for t in trades or []:
        rows.append({
            "trade_id": t.get("trade_id"),
            "ticker": t.get("ticker"),
            "created_time": t.get("created_time"),
            "created_ts": iso_to_ts(t.get("created_time")),
            "yes_price": _price(t, "yes_price"),
            "no_price": _price(t, "no_price"),
            "count": _count(t, "count"),
            "taker_side": t.get("taker_side") or t.get("taker_outcome_side"),
            "is_block_trade": bool(t.get("is_block_trade")),
        })
    return rows


# ---------------------------------------------------------------------------------------------
# Order book
# ---------------------------------------------------------------------------------------------
def parse_orderbook(resp):
    """Normalise an order-book response into {'yes_bids': [(price, size)], 'no_bids': [...]},
    each sorted best (highest) price first. Accepts ``orderbook_fp`` (new) or ``orderbook``
    (legacy integer cents)."""
    ob = resp.get("orderbook_fp") or resp.get("orderbook") or {}
    out = {}
    for side in ("yes", "no"):
        levels = ob.get(f"{side}_dollars")
        if levels is None:
            levels = [[(p / 100.0 if not isinstance(p, str) else to_float(p)), q]
                      for p, q in (ob.get(side) or [])]
        clean = [(to_float(p), to_float(q)) for p, q in (levels or [])]
        out[f"{side}_bids"] = sorted([lv for lv in clean if lv[1] > 0], key=lambda x: -x[0])
    return out


def yes_asks(book):
    """YES offers implied by NO bids: a NO bid at q is a YES ask at 1 - q. Best (lowest) first."""
    return sorted([(round(1.0 - p, 4), q) for p, q in book["no_bids"]], key=lambda x: x[0])


def orderbook_summary(book):
    """Best bid/ask, spread, mid, and total resting size on each side of the YES market."""
    asks = yes_asks(book)
    bids = book["yes_bids"]
    best_bid = bids[0][0] if bids else math.nan
    best_ask = asks[0][0] if asks else math.nan
    return {
        "best_yes_bid": best_bid,
        "best_yes_bid_size": bids[0][1] if bids else 0.0,
        "best_yes_ask": best_ask,
        "best_yes_ask_size": asks[0][1] if asks else 0.0,
        "spread": best_ask - best_bid if bids and asks else math.nan,
        "mid": (best_ask + best_bid) / 2 if bids and asks else math.nan,
        "yes_bid_depth": sum(q for _, q in bids),
        "yes_ask_depth": sum(q for _, q in asks),
        "yes_ask_depth_dollars": sum(p * q for p, q in asks),
        "n_yes_bid_levels": len(bids),
        "n_yes_ask_levels": len(asks),
    }


def walk_book(levels, contracts=None, max_price=None):
    """Take liquidity from price levels (best first) until ``contracts`` are filled or the
    price exceeds ``max_price``. Returns (filled_contracts, total_cost_dollars, avg_price)."""
    filled = cost = 0.0
    for p, q in levels:
        if max_price is not None and p > max_price + 1e-12:
            break
        take = q if contracts is None else min(q, contracts - filled)
        if take <= 0:
            break
        filled += take
        cost += take * p
    return filled, cost, (cost / filled if filled else math.nan)


# ---------------------------------------------------------------------------------------------
# Fees
# ---------------------------------------------------------------------------------------------
TAKER_RATE = Decimal("0.07")
MAKER_RATE = Decimal("0.0175")


def fee(contracts, price, maker=False, fee_type="quadratic", multiplier=1.0, round_up=True):
    """Kalshi trading fee in dollars for one order of ``contracts`` at ``price`` dollars.

    Taker (general) formula, from Kalshi's Fee Schedule, "2nd Iteration, September 22, 2022",
    p.2 (filed with the CFTC: https://www.cftc.gov/filings/orgrules/rule091222kexdcm003.pdf):

        fees = round up(0.07 x C x P x (1 - P)),  P = price in dollars, C = contracts,
        "round up = rounds to the next cent".

    The same filing's table (p.3-4) gives e.g. 1 contract @ $0.50 -> $0.02 and
    100 contracts @ $0.50 -> $1.75; these are the unit-test cases. The current schedule
    (https://kalshi.com/docs/kalshi-fee-schedule.pdf, not retrievable on 2026-10-29: HTTP 429)
    keeps this formula with a per-series multiplier and adds a maker fee of
    round up(0.0175 x C x P x (1 - P)) only on series flagged for maker fees. The API exposes
    this per series as ``fee_type`` ('quadratic' = taker-only, 'quadratic_with_maker_fees',
    'flat', ...) and ``fee_multiplier``. All monthly-rain series checked on 2026-10-29 report
    ``fee_type='quadratic', fee_multiplier=1``, i.e. 7% taker coefficient and no maker fee.

    Since Kalshi's fixed-point migration the exchange computes the fee to $0.000001 and then
    charges a rounding fee to bring a non-direct (retail/FCM) member's balance back to whole
    cents ("Fee Rounding", https://docs.kalshi.com/getting_started/fee_rounding). For whole-
    cent prices and whole contracts this equals rounding the order's fee up to the cent, which
    is what ``round_up=True`` does. ``round_up=False`` returns the unrounded model fee.

    Args:
        contracts: number of contracts C (may be fractional).
        price: fill price P in dollars (0 < P < 1).
        maker: True if the order rested on the book before filling.
        fee_type: series fee type from the API.
        multiplier: series ``fee_multiplier``.
    """
    if fee_type == "flat":
        raise NotImplementedError("flat fee series are not modelled")
    if maker and fee_type not in ("quadratic_with_maker_fees", "quadratic_with_combo_maker_fees"):
        return 0.0
    rate = MAKER_RATE if maker else TAKER_RATE
    p = Decimal(str(price))
    raw = rate * Decimal(str(multiplier)) * Decimal(str(contracts)) * p * (1 - p)
    if not round_up:
        return float(raw)
    return float(raw.quantize(Decimal("0.01"), rounding=ROUND_CEILING))


# ---------------------------------------------------------------------------------------------
# Series classification and ladders
# ---------------------------------------------------------------------------------------------
RAIN_MONTHLY_RE = re.compile(r"^(KX)?RAIN[A-Z]+M$")


def series_family(ticker, title="", frequency=""):
    """Classify a Climate-and-Weather series into rain_monthly, rain_daily, rain_weekly,
    temp_high, temp_low, snow, hurricane, or other (rules documented in the doc 05b)."""
    t = (ticker or "").upper()
    ttl = (title or "").lower()
    if RAIN_MONTHLY_RE.match(t):
        return "rain_monthly"
    if "RAIN" in t:
        if frequency == "daily":
            return "rain_daily"
        if frequency == "weekly":
            return "rain_weekly"
        return "other"
    if "SNOW" in t and "OPEN" not in t:
        return "snow"
    if "HUR" in t or "TROPSTORM" in t or "NAMEDSTORM" in t:
        return "hurricane"
    is_temp = "temp" in ttl or "heat" in ttl
    if (t.startswith(("KXHIGH", "HIGH")) or t.endswith("HIGH") or "TMAX" in t
            or t.startswith("KXWEEKHT") or "MAXTEMP" in t
            or (is_temp and ("high" in ttl or "max" in ttl))):
        return "temp_high"
    if (t.startswith(("KXLOW", "LOW")) or "LOWT" in t or "TMIN" in t or t.endswith("MINNYC")
            or (is_temp and ("low" in ttl or "min" in ttl))):
        return "temp_low"
    return "other"


def ladder_outcomes(markets):
    """Per event, the monthly total implied by settled 'greater than' ladder results.

    Args:
        markets: pandas DataFrame of ``parse_market`` rows (one series or many).

    Returns a DataFrame with one row per event: series_ticker, event_ticker, contract_month,
    city, cli_code, n_markets, n_settled, highest_yes_strike (total > this), lowest_no_strike
    (total <= this), implied_low / implied_high (same bounds, NaN if open-ended),
    consistent (no YES strike at or above a NO strike), expiration_value_final (value reported
    on the market that settled last, i.e. at the scheduled end of month), expiration_value_max,
    all_settled, final_is_lower_bound (every strike resolved YES, so the last market closed
    early and its expiration_value is only a lower bound on the monthly total), and
    value_in_bounds (expiration_value_final is > highest YES strike and <= lowest NO strike).
    """
    import pandas as pd

    rows = []
    for ev, g in markets.groupby("event_ticker", sort=True):
        g = g[g["strike_type"].fillna("greater").str.startswith("greater")]
        settled = g[g["result"].isin(["yes", "no"])]
        yes = settled.loc[settled["result"] == "yes", "strike"]
        no = settled.loc[settled["result"] == "no", "strike"]
        hy = yes.max() if len(yes) else math.nan
        ln = no.min() if len(no) else math.nan
        ev_final = math.nan
        if len(settled):
            ts = settled["settlement_ts"].map(iso_to_ts)
            vals = settled.assign(_ts=ts).sort_values("_ts")["expiration_value"].dropna()
            ev_final = vals.iloc[-1] if len(vals) else math.nan
        first = g.iloc[0] if len(g) else markets[markets["event_ticker"] == ev].iloc[0]
        rows.append({
            "series_ticker": first["series_ticker"],
            "event_ticker": ev,
            "contract_month": first["contract_month"],
            "city": first["city"],
            "cli_code": first["cli_code"],
            "n_markets": len(g),
            "n_settled": len(settled),
            "highest_yes_strike": hy,
            "lowest_no_strike": ln,
            "implied_low": hy,
            "implied_high": ln,
            "consistent": bool(math.isnan(hy) or math.isnan(ln) or hy < ln),
            "expiration_value_final": ev_final,
            "expiration_value_max": settled["expiration_value"].max() if len(settled) else math.nan,
            "all_settled": bool(len(g) and len(settled) == len(g)),
            "final_is_lower_bound": bool(len(settled) and len(no) == 0),
            "value_in_bounds": (math.nan if math.isnan(ev_final) else
                                bool((math.isnan(hy) or ev_final > hy)
                                     and (math.isnan(ln) or ev_final <= ln))),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------------------------
# Liquidity / calibration helpers (used by scripts/pull_kalshi.py --stats)
# ---------------------------------------------------------------------------------------------
def wilson_interval(k, n, z=1.96):
    """Wilson score interval for a binomial proportion k/n; (nan, nan) when n == 0."""
    if n == 0:
        return math.nan, math.nan
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return centre - half, centre + half


def prices_at_horizon(markets, candles, horizon_days):
    """Price of each settled market ``horizon_days`` before its event's scheduled close.

    The scheduled close of an event is the latest ``close_time`` among its markets (markets that
    resolve NO run to the scheduled end; 'greater than' markets that resolve YES may close
    early). A market is included only if it was open at the evaluation time t = scheduled
    close - horizon (opened before t and not yet closed), so no outcome information leaks in.

    Returns one row per included market: ticker, event_ticker, series_ticker, t_eval,
    last_price (last traded YES price at or before t, from daily candles), mid (YES bid/ask
    midpoint of the last daily candle ending at or before t, NaN unless both sides quoted),
    spread, stale_days (days since the last trade), outcome (1 = YES).
    """
    import pandas as pd

    mk = markets[markets["result"].isin(["yes", "no"])].copy()
    mk["open_ts"] = mk["open_time"].map(iso_to_ts)
    mk["close_ts"] = mk["close_time"].map(iso_to_ts)
    mk["sched_close_ts"] = mk.groupby("event_ticker")["close_ts"].transform("max")
    mk["t_eval"] = mk["sched_close_ts"] - horizon_days * 86400
    mk = mk[(mk["open_ts"] < mk["t_eval"]) & (mk["close_ts"] > mk["t_eval"])]
    c = candles[candles["ticker"].isin(mk["ticker"])].merge(
        mk[["ticker", "t_eval"]], on="ticker")
    c = c[c["end_period_ts"] <= c["t_eval"]].sort_values(["ticker", "end_period_ts"])
    rows = []
    for tkr, g in c.groupby("ticker", sort=False):
        traded = g[g["price_close"].notna()]
        last = g.iloc[-1]
        bid, ask = last["yes_bid_close"], last["yes_ask_close"]
        two_sided = bid > 0 and ask < 1 and ask > bid
        rows.append({
            "ticker": tkr,
            "last_price": traded["price_close"].iloc[-1] if len(traded) else math.nan,
            "stale_days": ((last["t_eval"] - traded["end_period_ts"].iloc[-1]) / 86400
                           if len(traded) else math.nan),
            "mid": (bid + ask) / 2 if two_sided else math.nan,
            "spread": ask - bid if two_sided else math.nan,
        })
    out = mk[["ticker", "event_ticker", "series_ticker", "strike", "t_eval", "result"]].merge(
        pd.DataFrame(rows, columns=["ticker", "last_price", "stale_days", "mid", "spread"]),
        on="ticker", how="inner")
    out["outcome"] = (out["result"] == "yes").astype(int)
    out["horizon_days"] = horizon_days
    return out


CALIBRATION_BINS = (0.0, 0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 0.95, 1.0001)


def calibration_table(prices, outcomes, bins=CALIBRATION_BINS):
    """Bin YES prices and compare the mean price with the realised YES frequency.

    Returns a DataFrame: bin_lo, bin_hi, n, mean_price, yes_rate, ci_lo, ci_hi (Wilson 95%),
    gap (yes_rate - mean_price; negative = contracts in that bin were overpriced).
    """
    import numpy as np
    import pandas as pd

    p = np.asarray(prices, dtype=float)
    y = np.asarray(outcomes, dtype=float)
    keep = ~np.isnan(p)
    p, y = p[keep], y[keep]
    rows = []
    for lo, hi in zip(bins[:-1], bins[1:]):
        sel = (p >= lo) & (p < hi)
        n = int(sel.sum())
        k = int(y[sel].sum())
        lo_ci, hi_ci = wilson_interval(k, n)
        rows.append({"bin_lo": lo, "bin_hi": min(hi, 1.0), "n": n,
                     "mean_price": p[sel].mean() if n else math.nan,
                     "yes_rate": k / n if n else math.nan, "ci_lo": lo_ci, "ci_hi": hi_ci,
                     "gap": (k / n - p[sel].mean()) if n else math.nan})
    return pd.DataFrame(rows)
