"""Offline tests for agri_hedge.kalshi (B2). Fixtures in tests/fixtures/b2/ are real API
responses saved on 2026-10-29, except LEGACY_MARKET below, which is a hand-written example of
the pre-migration integer-cent format."""
import json
import math
from pathlib import Path

import pandas as pd
import pytest

from agri_hedge import kalshi as K

FIX = Path(__file__).parent / "fixtures" / "b2"


def load(name):
    with open(FIX / name, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def markets():
    return {m["ticker"]: m for m in load("markets_sample.json")["markets"]}


# --------------------------------------------------------------------------- fees
@pytest.mark.parametrize("contracts,price,expected", [
    # Kalshi Fee Schedule (2nd iteration, 2022-09-22), general trading fee table, p.3-4
    (1, 0.50, 0.02), (100, 0.50, 1.75), (1, 0.01, 0.01), (100, 0.01, 0.07),
    (100, 0.05, 0.34), (100, 0.10, 0.63), (100, 0.30, 1.47), (100, 0.45, 1.74),
    (100, 0.55, 1.74), (100, 0.85, 0.90), (1, 0.15, 0.01), (1, 0.20, 0.02),
    (100, 0.99, 0.07), (1, 0.99, 0.01),
])
def test_fee_matches_published_table(contracts, price, expected):
    assert K.fee(contracts, price) == pytest.approx(expected)


def test_fee_maker_and_multiplier():
    # rain series are fee_type 'quadratic': makers pay nothing
    assert K.fee(100, 0.5, maker=True) == 0.0
    # series with maker fees: round up(0.0175 * 100 * 0.25) = 0.44
    assert K.fee(100, 0.5, maker=True, fee_type="quadratic_with_maker_fees") == pytest.approx(0.44)
    assert K.fee(100, 0.5, multiplier=0.5) == pytest.approx(0.88)
    assert K.fee(100, 0.5, round_up=False) == pytest.approx(1.75)
    assert K.fee(10, 0.37, round_up=False) == pytest.approx(0.07 * 10 * 0.37 * 0.63)
    # exact-cent results must not be bumped up by floating-point noise
    assert K.fee(100, 0.30) == pytest.approx(1.47)


# --------------------------------------------------------------------------- market parsing
def test_parse_live_market_new_field_names(markets):
    r = K.parse_market(markets["KXRAINDALM-26OCT-3"], series_ticker="KXRAINDALM")
    assert r["cli_code"] == "CLIDFW" and r["station_code"] == "CLIDFW"
    assert r["city"] == "Dallas"
    assert r["contract_month"] == "2026-10"
    assert r["period_start"] == "2026-10-01" and r["period_end"] == "2026-10-31"
    assert r["is_single_month"]
    assert r["strike"] == 3.0 and r["strike_type"] == "greater"
    assert r["volume"] == pytest.approx(1259.11)
    assert r["open_interest"] == pytest.approx(1259.11)
    assert r["last_price"] == pytest.approx(0.99)
    assert r["yes_bid"] == 0.0 and r["yes_ask"] == 1.0
    assert r["result"] == "yes" and r["settlement_value"] == 1.0
    assert r["expiration_value"] == pytest.approx(3.5)
    assert r["tick_size"] == pytest.approx(0.01)
    assert math.isnan(r["liquidity"])  # field no longer returned
    assert set(K.MARKET_COLUMNS) == set(r)


def test_parse_market_missing_strike_type_and_text_expiration(markets):
    r = K.parse_market(markets["KXRAINNYCM-25JAN-4"], series_ticker="KXRAINNYCM")
    assert r["strike"] == 4.0
    assert r["strike_type"] == "greater"  # recovered from rules text
    assert r["expiration_value"] == pytest.approx(0.61)  # "0.61 inches"
    assert r["city"] == "New York City" and r["cli_code"] == ""


def test_parse_legacy_ticker_and_seasonal_napa(markets):
    r = K.parse_market(markets["RAINNYCM-24OCT-4.5"], series_ticker="KXRAINNYCM")
    assert r["series_ticker"] == "KXRAINNYCM" and r["contract_month"] == "2024-10"
    assert r["strike"] == 4.5
    n = K.parse_market(markets["KXRAINNAPAM-01NOV26-31MAR27-T35"])
    assert n["series_ticker"] == "KXRAINNAPAM"
    assert n["station_code"] == "KAPC" and n["city"] == "Napa"
    assert n["period_start"] == "2026-11-01" and n["period_end"] == "2027-03-31"
    assert not n["is_single_month"]
    assert n["strike"] == 35.0


LEGACY_MARKET = {  # hand-written example of the pre-2026 integer-cent format
    "ticker": "KXRAINDALM-25NOV-3", "event_ticker": "KXRAINDALM-25NOV", "strike_type": "greater",
    "floor_strike": 3, "yes_bid": 41, "yes_ask": 45, "last_price": 43, "volume": 120,
    "open_interest": 80, "liquidity": 2500, "result": "", "status": "active",
    "rules_primary": "If the total precipitation at CLIDFW in Dallas in Nov 2025 is strictly "
                     "greater than 3 inches, then the market resolves to Yes.",
}


def test_parse_market_legacy_cents():
    r = K.parse_market(LEGACY_MARKET)
    assert r["yes_bid"] == pytest.approx(0.41) and r["yes_ask"] == pytest.approx(0.45)
    assert r["last_price"] == pytest.approx(0.43)
    assert r["volume"] == 120 and r["open_interest"] == 80
    assert r["liquidity"] == pytest.approx(25.0)
    assert r["contract_month"] == "2025-11"


def test_rules_and_ticker_helpers():
    p = K.parse_rain_rules("If the total precipitation at CLISPG in St. Petersburg in Jul 2026 is "
                           "strictly greater than 10 inches, then the market resolves to Yes.")
    assert p["cli_code"] == "CLISPG" and p["city"] == "St. Petersburg" and p["strike"] == 10
    assert K.event_contract_month("KXRAINNAPAM-01DEC26-31DEC26") == "2026-12"
    assert K.event_contract_month("RAINNYCM-24FEB") == "2024-02"
    assert K.event_contract_month("KXHIGHNY-26OCT29") == ""
    assert K.parse_number("Yes") != K.parse_number("Yes")  # NaN
    assert K.parse_number("") != K.parse_number("")


@pytest.mark.parametrize("ticker,title,freq,family", [
    ("KXRAINDALM", "Rain Dallas", "custom", "rain_monthly"),
    ("RAINNYCM", "Monthly rain in New York", "monthly", "rain_monthly"),
    ("KXRAINNYC", "NYC rain", "daily", "rain_daily"),
    ("KXRAINNYCW", "How much will it rain in NYC this week?", "weekly", "rain_weekly"),
    ("KXHIGHNY", "Highest temperature in NYC", "daily", "temp_high"),
    ("KXLOWTDAL", "Lowest temperature Dallas", "daily", "temp_low"),
    ("KXDENSNOWM", "Denver snowfall monthly", "monthly", "snow"),
    ("KXHURCTOT", "Number of hurricanes", "annual", "hurricane"),
    ("KXTORNADO", "Number of Tornadoes", "monthly", "other"),
    ("KXSNOWBIRDOPEN", "Snowbird Opening", "annual", "other"),
])
def test_series_family(ticker, title, freq, family):
    assert K.series_family(ticker, title, freq) == family


# --------------------------------------------------------------------------- candles / trades
def test_parse_candles_live_and_historical():
    live = K.parse_candles(load("candles_live.json")["candlesticks"], "KXRAINDALM-26OCT-3")
    assert live[0]["price_close"] == pytest.approx(0.99)
    assert live[0]["volume"] == pytest.approx(1256.11)
    assert live[0]["yes_bid_close"] == pytest.approx(0.99)
    assert live[0]["date"] == "2026-10-02"
    hist = K.parse_candles(load("candles_historical.json")["candlesticks"], "KXRAINDALM-26JUL-7")
    assert hist[0]["price_close"] == pytest.approx(0.06)
    assert hist[0]["open_interest"] == pytest.approx(164.0)
    assert hist[0]["yes_ask_close"] == pytest.approx(0.05)
    assert math.isnan(hist[0]["price_previous"])  # null in the payload
    legacy = K.parse_candles([{"end_period_ts": 0, "price": {"close": 43}, "volume": 7}])
    assert legacy[0]["price_close"] == pytest.approx(0.43) and legacy[0]["volume"] == 7


def test_parse_trades():
    rows = K.parse_trades(load("trades_historical.json")["trades"])
    assert rows and rows[0]["ticker"] == "KXRAINDALM-26JUL-7"
    assert rows[0]["count"] == pytest.approx(66.66)
    assert rows[0]["yes_price"] + rows[0]["no_price"] == pytest.approx(1.0)
    assert rows[0]["taker_side"] in ("yes", "no")


# --------------------------------------------------------------------------- order book
def test_orderbook_parse_and_summary():
    book = K.parse_orderbook(load("orderbook.json"))
    assert book["yes_bids"][0] == (0.33, 50.0)  # best (highest) first
    asks = K.yes_asks(book)
    assert asks[0] == (0.51, 50.0)  # NO bid 0.49 -> YES ask 0.51
    s = K.orderbook_summary(book)
    assert s["spread"] == pytest.approx(0.18) and s["mid"] == pytest.approx(0.42)
    assert s["yes_bid_depth"] == pytest.approx(157.0)
    filled, cost, avg = K.walk_book(asks, contracts=120)
    assert filled == pytest.approx(120) and cost == pytest.approx(50 * 0.51 + 70 * 0.81)
    filled, _, _ = K.walk_book(asks, max_price=0.6)
    assert filled == pytest.approx(50)
    legacy = K.parse_orderbook({"orderbook": {"yes": [[33, 50]], "no": [[49, 50]]}})
    assert legacy["yes_bids"] == [(0.33, 50.0)] and legacy["no_bids"] == [(0.49, 50.0)]


# --------------------------------------------------------------------------- ladder outcomes
def test_ladder_outcomes():
    rows = []
    for strike, res, ev in [(1, "yes", "1.4"), (2, "no", "1.4"), (3, "no", "1.4"), (0.5, "yes", "0.6")]:
        rows.append(K.parse_market({
            "ticker": f"KXRAINDALM-26JUL-{strike}", "event_ticker": "KXRAINDALM-26JUL",
            "strike_type": "greater", "floor_strike": strike, "result": res,
            "expiration_value": ev, "status": "finalized",
            "settlement_ts": "2026-08-01T15:00:00Z" if ev == "1.4" else "2026-07-05T15:00:00Z"}))
    out = K.ladder_outcomes(pd.DataFrame(rows)).iloc[0]
    assert out["highest_yes_strike"] == 1 and out["lowest_no_strike"] == 2
    assert out["consistent"]
    assert out["expiration_value_final"] == pytest.approx(1.4)  # from the last settlement


# --------------------------------------------------------------------------- client / pagination
class FakeResponse:
    def __init__(self, status, payload, headers=None):
        self.status_code = status
        self._payload = payload
        self.headers = headers or {}
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, dict(params or {})))
        return self.responses.pop(0)


def make_client(responses):
    sleeps = []
    c = K.KalshiClient(session=FakeSession(responses), delay=0, sleep=sleeps.append, backoff=1.0)
    return c, sleeps


def test_paginate_follows_cursor_until_empty():
    c, _ = make_client([
        FakeResponse(200, {"markets": [{"ticker": "A"}, {"ticker": "B"}], "cursor": "c1"}),
        FakeResponse(200, {"markets": [{"ticker": "C"}], "cursor": "c2"}),
        FakeResponse(200, {"markets": [], "cursor": ""}),
    ])
    out = c.list_markets(series_ticker="KXRAINDALM", status="open")
    assert [m["ticker"] for m in out] == ["A", "B", "C"]
    calls = c.session.calls
    assert calls[0][0].endswith("/markets") and "cursor" not in calls[0][1]
    assert calls[0][1]["limit"] == 1000 and calls[0][1]["status"] == "open"
    assert calls[1][1]["cursor"] == "c1" and calls[2][1]["cursor"] == "c2"
    assert "event_ticker" not in calls[0][1]  # None params are dropped


def test_paginate_events_uses_200_limit_and_stops_on_repeated_cursor():
    c, _ = make_client([
        FakeResponse(200, {"events": [{"event_ticker": "E1"}], "cursor": "same"}),
        FakeResponse(200, {"events": [{"event_ticker": "E2"}], "cursor": "same"}),
    ])
    out = c.list_events("KXRAINDALM")
    assert len(out) == 2 and c.session.calls[0][1]["limit"] == 200


def test_retry_on_429_and_5xx_with_backoff():
    c, sleeps = make_client([
        FakeResponse(429, {}, headers={"Retry-After": "3"}),
        FakeResponse(503, {}),
        FakeResponse(200, {"series": {"ticker": "KXRAINDALM"}}),
    ])
    assert c.get_series("KXRAINDALM")["ticker"] == "KXRAINDALM"
    assert sleeps == [3.0, 2.0]  # Retry-After honoured, then backoff * 2**1


def test_non_retryable_error_raises():
    c, _ = make_client([FakeResponse(404, {"error": {"code": "not_found"}})])
    with pytest.raises(K.KalshiAPIError) as e:
        c.get_market("NOPE")
    assert e.value.status_code == 404


def test_candles_fall_back_to_other_tier():
    c, _ = make_client([
        FakeResponse(404, {}),
        FakeResponse(200, load("candles_historical.json")),
    ])
    candles, tier = c.get_candles_any("KXRAINDALM", "KXRAINDALM-26JUL-7", 0, 1, historical=False)
    assert tier == "historical" and len(candles) == len(load("candles_historical.json")["candlesticks"])


def test_load_or_fetch_json_caches(tmp_path):
    calls = []
    f = tmp_path / "x.json"
    assert K.load_or_fetch_json(f, lambda: calls.append(1) or {"a": 1}) == {"a": 1}
    assert K.load_or_fetch_json(f, lambda: calls.append(1) or {"a": 2}) == {"a": 1}
    assert K.load_or_fetch_json(f, lambda: calls.append(1) or {"a": 3}, refresh=True) == {"a": 3}
    assert len(calls) == 2


# --------------------------------------------------------------------------- calibration helpers
def test_wilson_and_calibration_table():
    lo, hi = K.wilson_interval(0, 10)
    assert lo == pytest.approx(0.0, abs=1e-12) and 0.25 < hi < 0.35
    ct = K.calibration_table([0.02, 0.03, 0.5, 0.55, 0.97], [0, 0, 1, 0, 1])
    first = ct.iloc[0]
    assert first["n"] == 2 and first["yes_rate"] == 0 and first["mean_price"] == pytest.approx(0.025)
    assert ct["n"].sum() == 5


def test_prices_at_horizon_excludes_closed_and_uses_last_trade():
    day = 86400
    mk = pd.DataFrame([
        # resolved YES early (closed day 5): excluded at a 7-day horizon from day 30
        {"ticker": "E-1", "event_ticker": "E", "series_ticker": "S", "strike": 1.0,
         "result": "yes", "open_time": "1970-01-01T00:00:00Z", "close_time": "1970-01-06T00:00:00Z"},
        # ran to the scheduled close on day 30
        {"ticker": "E-2", "event_ticker": "E", "series_ticker": "S", "strike": 2.0,
         "result": "no", "open_time": "1970-01-01T00:00:00Z", "close_time": "1970-01-31T00:00:00Z"},
    ])
    cd = pd.DataFrame([
        {"ticker": "E-2", "end_period_ts": 20 * day, "price_close": 0.30, "yes_bid_close": 0.28,
         "yes_ask_close": 0.32},
        {"ticker": "E-2", "end_period_ts": 22 * day, "price_close": float("nan"),
         "yes_bid_close": 0.20, "yes_ask_close": 0.26},
        {"ticker": "E-2", "end_period_ts": 25 * day, "price_close": 0.90, "yes_bid_close": 0.0,
         "yes_ask_close": 1.0},  # after the evaluation time: must be ignored
    ])
    out = K.prices_at_horizon(mk, cd, horizon_days=7)  # t_eval = day 23
    assert list(out["ticker"]) == ["E-2"]
    r = out.iloc[0]
    assert r["last_price"] == pytest.approx(0.30) and r["stale_days"] == pytest.approx(3.0)
    assert r["mid"] == pytest.approx(0.23) and r["outcome"] == 0
