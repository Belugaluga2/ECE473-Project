"""Pull Kalshi weather-market data (B2): series catalog, monthly-rain markets, daily candles,
trades, order-book snapshots, and ladder-implied monthly outcomes.

Run from the repo root:
    python scripts/pull_kalshi.py              # everything (cached raw JSON is reused)
    python scripts/pull_kalshi.py --refresh    # re-download market lists / open-market data
    python scripts/pull_kalshi.py --skip-catalog --skip-trades
    python scripts/pull_kalshi.py --orderbooks-only   # fresh books + incentive list only; leaves
                                                      # markets/candles/trades/outcomes untouched
    python scripts/pull_kalshi.py --stats [--orderbook data/processed/kalshi_rain_orderbook_summary_20261029.csv]

Raw JSON goes to data/raw/kalshi/ (settled-market candles and trades are cached forever, lists of
markets for 6 hours, the catalog for 24 hours). Processed outputs go to data/processed/:
    kalshi_weather_series_catalog.csv
    kalshi_rain_markets.parquet, kalshi_rain_markets_summary.csv
    kalshi_rain_daily_candles.parquet
    kalshi_rain_trades.parquet
    kalshi_rain_monthly_outcomes.csv
    kalshi_rain_orderbook_summary_<YYYYMMDD>.csv  one per snapshot day, never overwritten by a
                                        later day (parsed from data/raw/kalshi/orderbooks_<UTC>.json)
    kalshi_rain_orderbook_summary.csv   copy of the LATEST snapshot (what other scripts read)
    kalshi_rain_incentive_programs.csv  (liquidity rewards on monthly-rain markets)
    with --stats: kalshi_rain_liquidity_by_series.csv, kalshi_rain_calibration.csv,
                  kalshi_rain_hedge_capacity_nov2026_<YYYYMMDD>.csv (date of the order-book
                  snapshot used), docs/figures/b2_*.png
Liquidity statistics and figures for docs/analysis/05b are produced by
``python scripts/pull_kalshi.py --stats`` (see ``make_stats``), which needs no network.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from agri_hedge import kalshi as K
from agri_hedge.config import FIGURES, PROCESSED, RAW
from agri_hedge.locations import ALL_SITES

RAW_K = RAW / "kalshi"
CATEGORY = "Climate and Weather"
LIST_TTL = 6 * 3600
CATALOG_TTL = 24 * 3600
STUDY_SERIES = [s["kalshi_series"] for s in ALL_SITES.values()]
FINAL_STATUSES = {"finalized", "settled", "determined"}
DAY = 86400


def log(*a):
    print(*a, flush=True)


# ---------------------------------------------------------------------------------------------
# 1. Series catalog
# ---------------------------------------------------------------------------------------------
def build_catalog(client, refresh=False):
    series = K.load_or_fetch_json(RAW_K / "series_climate_weather.json",
                                  lambda: client.list_series(CATEGORY), CATALOG_TTL, refresh)
    log(f"catalog: {len(series)} series in '{CATEGORY}'")
    rows = []
    for i, s in enumerate(series):
        t = s["ticker"]

        def probe(t=t):
            open_m = client.list_markets(series_ticker=t, status="open")
            sample = open_m[:1]
            if not sample:
                sample = client.get("/markets", {"series_ticker": t, "limit": 1}).get("markets") or []
            if not sample:
                sample = client.get("/historical/markets",
                                    {"series_ticker": t, "limit": 1}).get("markets") or []
            return {"n_open": len(open_m), "sample": sample[:1]}

        pr = K.load_or_fetch_json(RAW_K / "catalog_probe" / f"{t}.json", probe, CATALOG_TTL, refresh)
        m = pr["sample"][0] if pr["sample"] else {}
        rules = m.get("rules_primary") or ""
        parsed = K.parse_market(m) if m else {"station_code": "", "station_text": ""}
        srcs = s.get("settlement_sources") or []
        rows.append({
            "ticker": t,
            "title": s.get("title"),
            "frequency": s.get("frequency"),
            "family": K.series_family(t, s.get("title"), s.get("frequency")),
            "cli_code": K.parse_cli_code(rules) or K.parse_cli_code(m.get("rules_secondary")),
            "station_code": parsed["station_code"],
            "station_text": parsed["station_text"],
            "settlement_sources": "; ".join(x.get("name", "") for x in srcs),
            "settlement_source_urls": "; ".join(x.get("url", "") for x in srcs),
            "contract_terms_url": s.get("contract_terms_url"),
            "fee_type": s.get("fee_type"),
            "fee_multiplier": s.get("fee_multiplier"),
            "tags": "; ".join(s.get("tags") or []),
            "has_open_markets": pr["n_open"] > 0,
            "n_open_markets": pr["n_open"],
            "sample_market": m.get("ticker", ""),
            "sample_rules_primary": rules,
        })
        if (i + 1) % 50 == 0:
            log(f"  probed {i + 1}/{len(series)}")
    cat = pd.DataFrame(rows).sort_values(["family", "ticker"])
    cat.to_csv(PROCESSED / "kalshi_weather_series_catalog.csv", index=False)
    log("wrote kalshi_weather_series_catalog.csv", cat["family"].value_counts().to_dict())
    return cat


# ---------------------------------------------------------------------------------------------
# 2. Monthly-rain markets (live + historical tiers)
# ---------------------------------------------------------------------------------------------
def rain_series_list(client, refresh=False):
    series = K.load_or_fetch_json(RAW_K / "series_climate_weather.json",
                                  lambda: client.list_series(CATEGORY), CATALOG_TTL, refresh)
    return sorted(s["ticker"] for s in series
                  if K.series_family(s["ticker"], s.get("title"), s.get("frequency")) == "rain_monthly")


def pull_rain_markets(client, refresh=False, write=True):
    """All monthly-rain markets (live + historical). write=False returns the table without
    rewriting kalshi_rain_markets.parquet / _summary.csv (used by --orderbooks-only)."""
    rows, raw_events = [], {}
    for t in rain_series_list(client, refresh):
        d = RAW_K / "markets"
        events = K.load_or_fetch_json(d / f"{t}_events.json", lambda: client.list_events(t),
                                      LIST_TTL, refresh)
        live = K.load_or_fetch_json(d / f"{t}_live.json", lambda: client.list_markets(series_ticker=t),
                                    LIST_TTL, refresh)
        hist = K.load_or_fetch_json(d / f"{t}_historical.json",
                                    lambda: client.list_historical_markets(series_ticker=t),
                                    LIST_TTL, refresh)
        seen = {m["ticker"] for m in live}
        markets = [(m, "live") for m in live] + [(m, "historical") for m in hist
                                                   if m["ticker"] not in seen]
        # Events whose markets did not come back under the series filter (defensive).
        have_ev = {m["event_ticker"] for m, _ in markets}
        for e in events:
            if e["event_ticker"] not in have_ev:
                ev = e["event_ticker"]
                extra = K.load_or_fetch_json(
                    d / "by_event" / f"{ev}.json",
                    lambda ev=ev: {"live": client.list_markets(event_ticker=ev),
                                   "historical": client.list_historical_markets(event_ticker=ev)},
                    LIST_TTL, refresh)
                markets += [(m, "live") for m in extra["live"]]
                markets += [(m, "historical") for m in extra["historical"]]
        raw_events[t] = events
        for m, tier in markets:
            rows.append(K.parse_market(m, series_ticker=t, tier=tier))
        log(f"markets {t}: {len(events)} events, {len(live)} live + {len(hist)} historical")
    df = pd.DataFrame(rows, columns=K.MARKET_COLUMNS).drop_duplicates("ticker")
    df["study_site"] = df["series_ticker"].map(
        {s["kalshi_series"]: k for k, s in ALL_SITES.items()}).fillna("")
    for c in ("open_time", "close_time", "settlement_ts", "created_time"):
        df[c + "_utc"] = pd.to_datetime(df[c], utc=True, errors="coerce", format="ISO8601")
    df = df.sort_values(["series_ticker", "contract_month", "strike"]).reset_index(drop=True)
    if not write:
        log(f"markets: {len(df)} markets ({int((df['status'] == 'active').sum())} active); not written")
        return df
    df.to_parquet(PROCESSED / "kalshi_rain_markets.parquet", index=False)

    g = df.groupby("series_ticker")
    summ = pd.DataFrame({
        "city": g["city"].agg(lambda s: s[s != ""].mode().iat[0] if (s != "").any() else ""),
        "station_code": g["station_code"].agg(lambda s: ",".join(sorted(set(s) - {""}))),
        "study_site": g["study_site"].first(),
        "first_month": g["contract_month"].min(),
        "last_month": g["contract_month"].max(),
        "n_events": g["event_ticker"].nunique(),
        "n_markets": g.size(),
        "n_open": g["status"].apply(lambda s: int((s == "active").sum())),
        "n_finalized": g["status"].apply(lambda s: int(s.isin(FINAL_STATUSES).sum())),
        "total_volume": g["volume"].sum().round(2),
    }).reset_index()
    summ.to_csv(PROCESSED / "kalshi_rain_markets_summary.csv", index=False)
    log(f"wrote kalshi_rain_markets.parquet ({len(df)} markets, {df.event_ticker.nunique()} events)")
    return df


# ---------------------------------------------------------------------------------------------
# 3. Daily candles
# ---------------------------------------------------------------------------------------------
def pull_candles(client, markets, cutoff, refresh=False):
    settled_cut = K.iso_to_ts(cutoff["market_settled_ts"])
    now = time.time()
    todo = markets[markets["volume"].fillna(0) > 0]
    log(f"candles: {len(todo)} markets with volume > 0")
    rows = []
    for i, m in enumerate(todo.itertuples(index=False)):
        final = m.status in FINAL_STATUSES
        historical = final and K.iso_to_ts(m.settlement_ts) < settled_cut
        start = K.iso_to_ts(m.open_time) - DAY
        end = min(K.iso_to_ts(m.close_time) + 2 * DAY, now)

        def fetch(m=m, start=start, end=end, historical=historical):
            c, tier = client.get_candles_any(m.series_ticker, m.ticker, start, end, historical)
            return {"ticker": m.ticker, "tier": tier, "start_ts": start, "end_ts": end,
                    "candles": c}

        raw = K.load_or_fetch_json(RAW_K / "candles" / f"{m.ticker}.json", fetch,
                                   None if final else LIST_TTL, refresh and not final)
        for r in K.parse_candles(raw["candles"], m.ticker):
            r["series_ticker"] = m.series_ticker
            r["candle_tier"] = raw["tier"]
            rows.append(r)
        if (i + 1) % 100 == 0:
            log(f"  candles {i + 1}/{len(todo)} (requests so far {client.n_requests})")
    df = pd.DataFrame(rows)
    df.to_parquet(PROCESSED / "kalshi_rain_daily_candles.parquet", index=False)
    log(f"wrote kalshi_rain_daily_candles.parquet ({len(df)} rows)")
    return df


# ---------------------------------------------------------------------------------------------
# 4. Trades
# ---------------------------------------------------------------------------------------------
def pull_trades(client, markets, series=None, refresh=False):
    todo = markets[markets["volume"].fillna(0) > 0]
    if series is not None:
        todo = todo[todo["series_ticker"].isin(series)]
    log(f"trades: {len(todo)} markets in {todo.series_ticker.nunique()} series")
    rows = []
    for i, m in enumerate(todo.itertuples(index=False)):
        final = m.status in FINAL_STATUSES
        raw = K.load_or_fetch_json(RAW_K / "trades" / f"{m.ticker}.json",
                                   lambda m=m: client.list_all_trades(m.ticker),
                                   None if final else LIST_TTL, refresh and not final)
        for r in K.parse_trades(raw):
            r["series_ticker"] = m.series_ticker
            rows.append(r)
        if (i + 1) % 100 == 0:
            log(f"  trades {i + 1}/{len(todo)} ({len(rows)} trades, {client.n_requests} requests)")
    df = pd.DataFrame(rows)
    if len(df):
        df["created_time_utc"] = pd.to_datetime(df["created_time"], utc=True, format="ISO8601")
        df = (df.drop(columns="created_time")  # keep the parsed timestamp only (file size)
              .sort_values(["ticker", "created_ts"]).reset_index(drop=True))
    df.to_parquet(PROCESSED / "kalshi_rain_trades.parquet", index=False)
    log(f"wrote kalshi_rain_trades.parquet ({len(df)} trades)")
    return df


# ---------------------------------------------------------------------------------------------
# 5. Order-book snapshot of open monthly-rain markets
# ---------------------------------------------------------------------------------------------
def snapshot_orderbooks(client, markets):
    open_m = markets[markets["status"] == "active"]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    books, rows = {}, []
    log(f"orderbooks: {len(open_m)} open markets")
    for m in open_m.itertuples(index=False):
        raw = client.get_orderbook(m.ticker)
        books[m.ticker] = raw
        book = K.parse_orderbook(raw)
        s = K.orderbook_summary(book)
        no_bids_as_no_asks = [(round(1 - p, 4), q) for p, q in book["yes_bids"]]  # buy NO
        rows.append({
            "snapshot_utc": stamp, "ticker": m.ticker, "series_ticker": m.series_ticker,
            "study_site": m.study_site, "event_ticker": m.event_ticker,
            "contract_month": m.contract_month, "strike": m.strike, **s,
            "no_ask_depth_dollars": sum(p * q for p, q in no_bids_as_no_asks),
            "yes_bids": json.dumps(book["yes_bids"]), "no_bids": json.dumps(book["no_bids"]),
        })
    path = RAW_K / f"orderbooks_{stamp}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"snapshot_utc": stamp, "books": books}, f)
    df = pd.DataFrame(rows)
    dated = orderbook_summary_path(stamp)
    df.to_csv(dated, index=False)
    df.to_csv(PROCESSED / "kalshi_rain_orderbook_summary.csv", index=False)
    log(f"wrote {path.name}, {dated.name} and kalshi_rain_orderbook_summary.csv (latest; {len(df)} books)")
    return df


def snapshot_day(stamp):
    """'20261102T013000Z' -> '20261102' (the date tag used in dated output names)."""
    s = str(stamp)
    if len(s) < 8 or not s[:8].isdigit():
        raise ValueError(f"not a UTC snapshot stamp: {stamp!r}")
    return s[:8]


def orderbook_summary_path(stamp):
    """Dated order-book summary for one snapshot day; earlier days are never overwritten."""
    return PROCESSED / f"kalshi_rain_orderbook_summary_{snapshot_day(stamp)}.csv"


def capacity_path(stamp):
    """Per-city Nov 2026 hedge-capacity table for the order-book snapshot taken on that day."""
    return PROCESSED / f"kalshi_rain_hedge_capacity_nov2026_{snapshot_day(stamp)}.csv"


# ---------------------------------------------------------------------------------------------
# 5b. Liquidity incentive programs on monthly-rain markets
# ---------------------------------------------------------------------------------------------
def pull_incentives(client, refresh=False):
    """All incentive programs (GET /incentive_programs, ~390k rows, ~40 requests), filtered to
    monthly-rain markets. period_reward is in centi-cents, so reward_usd = period_reward/1e4."""
    def fetch():
        return [x for x in client.list_incentive_programs()
                if K.RAIN_MONTHLY_RE.match((x.get("market_ticker") or "").split("-")[0])]

    raw = K.load_or_fetch_json(RAW_K / "incentive_programs_rain_monthly.json", fetch,
                               CATALOG_TTL, refresh)
    df = pd.DataFrame(raw)
    if len(df):
        df["series_ticker"] = df["market_ticker"].str.split("-").str[0]
        df["reward_usd"] = df["period_reward"] / 10_000
        df["days"] = (pd.to_datetime(df["end_date"], utc=True, format="ISO8601")
                      - pd.to_datetime(df["start_date"], utc=True, format="ISO8601")
                      ).dt.total_seconds() / DAY
        df = df.sort_values(["series_ticker", "start_date", "market_ticker"])
    df.to_csv(PROCESSED / "kalshi_rain_incentive_programs.csv", index=False)
    log(f"wrote kalshi_rain_incentive_programs.csv ({len(df)} programs)")
    return df


# ---------------------------------------------------------------------------------------------
# 6. Ladder-implied monthly outcomes
# ---------------------------------------------------------------------------------------------
def write_outcomes(markets):
    out = K.ladder_outcomes(markets)
    per = markets.groupby("event_ticker").agg(
        station_code=("station_code", "first"), is_single_month=("is_single_month", "first"),
        period_start=("period_start", "first"), period_end=("period_end", "first"),
        min_strike=("strike", "min"), max_strike=("strike", "max"),
        event_volume=("volume", "sum"))
    out = out.merge(per, on="event_ticker", how="left")
    out["study_site"] = out["series_ticker"].map(
        {s["kalshi_series"]: k for k, s in ALL_SITES.items()}).fillna("")
    out = out.sort_values(["series_ticker", "contract_month"])
    out.to_csv(PROCESSED / "kalshi_rain_monthly_outcomes.csv", index=False)
    log(f"wrote kalshi_rain_monthly_outcomes.csv ({len(out)} events)")
    return out


# ---------------------------------------------------------------------------------------------
# 6b. Cross-check settled ladders against ACIS station monthly totals (optional, --acis-check)
# ---------------------------------------------------------------------------------------------
ACIS_URL = "https://data.rcc-acis.org/StnData"


def acis_sid(station_code, series_ticker):
    """ACIS station id for a Kalshi settlement station: 'CLIDFW' -> 'DFW', 'KAPC' -> 'APC',
    NYC (Central Park, no CLI code in the rules) -> 'NYC'."""
    if station_code.startswith("CLI"):
        return station_code[3:]
    if len(station_code) == 4 and station_code.startswith("K"):
        return station_code[1:]
    return "NYC" if series_ticker == "KXRAINNYCM" else ""


def acis_check(refresh=False):
    """Fetch ACIS monthly precipitation for each settled single-month event's settlement
    station and compare with the ladder bounds and expiration_value. Writes
    data/raw/kalshi/acis_check.csv (ACIS 'T' = trace is recorded as 0.0)."""
    import requests

    oc = pd.read_csv(PROCESSED / "kalshi_rain_monthly_outcomes.csv")
    oc = oc[oc["is_single_month"] & oc["all_settled"]].copy()
    oc["station_code"] = oc["station_code"].fillna("")
    oc["sid"] = [acis_sid(s, t) for s, t in zip(oc["station_code"], oc["series_ticker"])]
    rows = []
    for (sid, code), g in oc[oc["sid"] != ""].groupby(["sid", "station_code"]):
        q = {"sid": sid, "sdate": g["contract_month"].min(), "edate": g["contract_month"].max(),
             "elems": [{"name": "pcpn", "interval": "mly", "reduce": "sum", "maxmissing": 0}]}
        data = K.load_or_fetch_json(
            RAW_K / "acis" / f"{sid}_{q['sdate']}_{q['edate']}.json",
            lambda q=q: requests.post(ACIS_URL, json=q, timeout=60).json(), None, refresh)
        vals = {m: v for m, v in data.get("data", [])}
        for r in g.itertuples(index=False):
            v = vals.get(r.contract_month)
            acis = 0.0 if v == "T" else K.to_float(v)
            lo, hi = r.implied_low, r.implied_high
            rows.append({"series_ticker": r.series_ticker, "event_ticker": r.event_ticker,
                         "contract_month": r.contract_month, "station_code": code,
                         "acis_sid": sid, "acis_name": data.get("meta", {}).get("name", ""),
                         "acis_total_in": acis, "acis_raw": v,
                         "kalshi_expiration_value": r.expiration_value_final,
                         "implied_low": lo, "implied_high": hi,
                         "acis_within_ladder": (math.nan if math.isnan(acis) else
                                                bool((math.isnan(lo) or acis > lo)
                                                     and (math.isnan(hi) or acis <= hi))),
                         "abs_diff_in": abs(acis - r.expiration_value_final)})
        time.sleep(0.2)
    df = pd.DataFrame(rows)
    df.to_csv(RAW_K / "acis_check.csv", index=False)
    log(f"wrote acis_check.csv ({len(df)} events; within ladder: "
        f"{int((df['acis_within_ladder'] == True).sum())}/{int(df['acis_within_ladder'].notna().sum())})")  # noqa: E712
    return df


# ---------------------------------------------------------------------------------------------
# 7. Liquidity statistics and figures for docs/analysis/05b (offline)
# ---------------------------------------------------------------------------------------------
BLUE, ORANGE, GRAY, INK, MUTED = "#2a78d6", "#eb6834", "#a8a69f", "#0b0b0b", "#52514e"
HORIZONS = (1, 3, 7, 14, 21)


def _style(ax, title, xlabel, ylabel):
    ax.set_title(title, fontsize=11, color=INK, loc="left")
    ax.set_xlabel(xlabel, color=MUTED)
    ax.set_ylabel(ylabel, color=MUTED)
    ax.grid(True, color="#e4e3df", linewidth=0.6, zorder=0)
    ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_color("#bdbcb6")
    ax.tick_params(colors=MUTED)


def _md(df, floatfmt=None):
    """Tiny markdown-table writer (avoids an optional 'tabulate' dependency)."""
    floatfmt = floatfmt or {}
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            if isinstance(v, (float, np.floating)):
                cells.append("" if math.isnan(v) else format(v, floatfmt.get(c, ",.2f")))
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def market_level_liquidity(mk, cd):
    """Per-market OI at close, mean two-sided spread, and share of days with a two-sided quote
    (from daily candles while the market was open)."""
    t = mk[["ticker", "open_time", "close_time"]].copy()
    t["open_ts"] = t["open_time"].map(K.iso_to_ts)
    t["close_ts"] = t["close_time"].map(K.iso_to_ts)
    c = cd.merge(t[["ticker", "open_ts", "close_ts"]], on="ticker")
    c = c[(c["end_period_ts"] > c["open_ts"]) & (c["end_period_ts"] <= c["close_ts"] + DAY)]
    c = c.sort_values(["ticker", "end_period_ts"])
    two = ((c["yes_bid_close"] > 0) & (c["yes_ask_close"] < 1)
           & (c["yes_ask_close"] > c["yes_bid_close"]))
    c["spread"] = np.where(two, c["yes_ask_close"] - c["yes_bid_close"], np.nan)
    c["two_sided"] = two
    g = c.groupby("ticker")
    return pd.DataFrame({
        "oi_at_close": g["open_interest"].last(),
        "mean_spread": g["spread"].mean(),
        "share_days_two_sided": g["two_sided"].mean(),
        "n_candle_days": g.size(),
    }).reset_index()


def _series_row(df_all, df_fin, label=None):
    ev = df_all.groupby("event_ticker").size()
    evf = df_fin.groupby("event_ticker").agg(v=("volume", "sum"), oi=("oi_at_close", "sum"))
    has_fin = len(df_fin) > 0
    return {
        "series": label or df_all["series_ticker"].iat[0],
        "city": "" if label else df_all["city"].mode().iat[0],
        "site": "" if label else df_all["study_site"].iat[0],
        "first_month": df_all["contract_month"].min(),
        "events": df_all["event_ticker"].nunique(),
        "markets": len(df_all),
        "settled_markets": len(df_fin),
        "strikes_per_event": ev.median(),
        "total_volume": df_all["volume"].sum(),
        "median_vol_per_settled_mkt": df_fin["volume"].median() if has_fin else math.nan,
        "mean_vol_per_settled_mkt": df_fin["volume"].mean() if has_fin else math.nan,
        "share_zero_vol_settled": (df_fin["volume"] <= 0).mean() if has_fin else math.nan,
        "share_zero_vol_all": (df_all["volume"] <= 0).mean(),
        "median_event_volume_settled": evf["v"].median() if has_fin else math.nan,
        "median_oi_at_close_per_mkt": df_fin["oi_at_close"].median() if has_fin else math.nan,
        "median_event_oi_at_close": evf["oi"].median() if has_fin else math.nan,
        "mean_spread_cents": 100 * df_all["mean_spread"].mean(),
        "share_days_two_sided": df_all["share_days_two_sided"].mean(),
    }


def _boot_gap(sub, kind, rng, reps=1000):
    """Mean(outcome - price) with a 95% event-cluster bootstrap interval."""
    if len(sub) == 0:
        return math.nan, math.nan, math.nan
    evs = sub["event_ticker"].unique()
    by = {e: (sub.loc[sub["event_ticker"] == e, "outcome"] - sub.loc[sub["event_ticker"] == e, kind])
          for e in evs}
    sums = np.array([by[e].sum() for e in evs])
    cnts = np.array([len(by[e]) for e in evs])
    gaps = []
    for _ in range(reps):
        idx = rng.integers(0, len(evs), len(evs))
        gaps.append(sums[idx].sum() / cnts[idx].sum())
    return (float(sums.sum() / cnts.sum()), float(np.percentile(gaps, 2.5)),
            float(np.percentile(gaps, 97.5)))


USEFUL_MAX_PRICE = 0.95  # ignore offers above 95c: $1 of cover would cost >= 95c


def _take(bids, within=None, max_price=None):
    """Lift resting bids on the opposite side: buying NO at 1 - (YES bid), or YES at
    1 - (NO bid). Optional filters: only levels within ``within`` dollars of the best price,
    or priced at most ``max_price``. Returns (contracts = $ payout, premium $, taker fees $)."""
    lv = sorted([(round(1 - p, 4), q) for p, q in bids], key=lambda x: x[0])
    if within is not None and lv:
        lv = [(p, q) for p, q in lv if p <= lv[0][0] + within + 1e-9]
    if max_price is not None:
        lv = [(p, q) for p, q in lv if p <= max_price + 1e-9]
    q = sum(q for _, q in lv)
    cost = sum(p * q for p, q in lv)
    fees = sum(K.fee(q, p) for p, q in lv if 0 < p < 1)
    return q, cost, fees


def make_stats(orderbook_csv=None):
    """Compute the liquidity statistics, calibration tables, and figures for doc 05b.
    orderbook_csv: order-book summary to use (default: the latest, kalshi_rain_orderbook_summary.csv).
    Only the hedge-capacity table and the depth figure depend on it."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    mk_all = pd.read_parquet(PROCESSED / "kalshi_rain_markets.parquet")
    cd = pd.read_parquet(PROCESSED / "kalshi_rain_daily_candles.parquet")
    oc = pd.read_csv(PROCESSED / "kalshi_rain_monthly_outcomes.csv")
    ob = pd.read_csv(orderbook_csv or PROCESSED / "kalshi_rain_orderbook_summary.csv")
    trp = PROCESSED / "kalshi_rain_trades.parquet"
    tr = pd.read_parquet(trp) if trp.exists() else pd.DataFrame()
    mk = mk_all[mk_all["is_single_month"]].copy()
    out = []

    # ---- per-series liquidity table -------------------------------------------------------
    mk = mk.merge(market_level_liquidity(mk, cd), on="ticker", how="left")
    fin_mask = mk["status"].isin(FINAL_STATUSES)
    mk["oi_at_close"] = np.where(fin_mask, mk["oi_at_close"].fillna(0.0), np.nan)
    f = mk[fin_mask]
    rows = [_series_row(g, f[f["series_ticker"] == s]) for s, g in mk.groupby("series_ticker")]
    rows.append(_series_row(mk, f, label="ALL"))
    tab = pd.DataFrame(rows)
    tab.to_csv(PROCESSED / "kalshi_rain_liquidity_by_series.csv", index=False)
    show = tab[["series", "city", "site", "first_month", "events", "markets", "strikes_per_event",
                "total_volume", "median_vol_per_settled_mkt", "share_zero_vol_settled",
                "median_oi_at_close_per_mkt", "median_event_oi_at_close", "mean_spread_cents",
                "share_days_two_sided"]]
    out.append("## Liquidity by series\n" + _md(show, {
        "total_volume": ",.0f", "median_vol_per_settled_mkt": ",.0f",
        "share_zero_vol_settled": ".0%", "median_oi_at_close_per_mkt": ",.0f",
        "median_event_oi_at_close": ",.0f", "mean_spread_cents": ".1f",
        "share_days_two_sided": ".0%", "strikes_per_event": ".0f"}))

    # ---- outcome sanity ---------------------------------------------------------------------
    ocs = oc[oc["is_single_month"] & oc["all_settled"]]
    vib = ocs["value_in_bounds"].map({True: True, False: False, "True": True, "False": False})
    out.append(f"## Outcomes\nsettled single-month events: {len(ocs)}; ladder consistent: "
               f"{int(ocs['consistent'].sum())}; expiration_value present: "
               f"{int(ocs['expiration_value_final'].notna().sum())}; value within ladder bounds: "
               f"{int((vib == True).sum())} / {int(vib.notna().sum())}; "  # noqa: E712
               f"all-YES (value is a lower bound only): {int(ocs['final_is_lower_bound'].sum())}")

    acp = RAW_K / "acis_check.csv"
    if acp.exists():
        ac = pd.read_csv(acp)
        ac["regime"] = pd.cut(pd.to_datetime(ac["contract_month"]),
                              pd.to_datetime(["2000-01-01", "2025-10-31", "2026-02-28",
                                              "2026-08-31", "2030-12-31"]),
                              labels=["to 2025-10", "2025-11 to 2026-02", "2026-03 to 2026-08",
                                      "2026-09 on"])
        reg = ac.groupby("regime", observed=True).agg(
            events=("event_ticker", "size"),
            acis_in_ladder=("acis_within_ladder", lambda s: int((s == True).sum())),  # noqa: E712
            with_value=("kalshi_expiration_value", "count"),
            exact=("abs_diff_in", lambda s: int((s < 0.005).sum())),
            within_005=("abs_diff_in", lambda s: int((s <= 0.05 + 1e-9).sum())),
            max_abs_diff=("abs_diff_in", "max")).reset_index()
        reg["regime"] = reg["regime"].astype(str)
        ev = oc.dropna(subset=["expiration_value_final"]).copy()
        ev["tenth"] = np.isclose(np.round(ev["expiration_value_final"] * 10, 6) % 1, 0)
        ev["regime"] = np.where(ev["contract_month"] >= "2026-02", "2026-02 on", "before 2026-02")
        tenth = ev.groupby("regime")["tenth"].agg(["mean", "size"])
        out.append("## Ladder vs ACIS station monthly totals\n" + _md(reg, {
            "events": ".0f", "acis_in_ladder": ".0f", "with_value": ".0f", "exact": ".0f",
            "within_005": ".0f", "max_abs_diff": ".2f"})
            + "\nshare of expiration values that are whole tenths: "
            + "; ".join(f"{k}: {v['mean']:.0%} of {int(v['size'])}" for k, v in tenth.iterrows()))

    # ---- volume vs strike distance from the series' median realised outcome -----------------
    med = (ocs.dropna(subset=["expiration_value_final"]).groupby("series_ticker")
           ["expiration_value_final"].median().rename("median_outcome"))
    fv = f.merge(med, left_on="series_ticker", right_index=True, how="inner")
    fv["dist"] = fv["strike"] - fv["median_outcome"]
    edges = [-np.inf, -2.5, -1.5, -0.5, 0.5, 1.5, 2.5, 3.5, 5.5, np.inf]
    labels = ["< -2.5", "-2.5 to -1.5", "-1.5 to -0.5", "-0.5 to 0.5", "0.5 to 1.5",
              "1.5 to 2.5", "2.5 to 3.5", "3.5 to 5.5", "> 5.5"]
    fv["dist_bin"] = pd.cut(fv["dist"], edges, labels=labels)
    dv = fv.groupby("dist_bin", observed=False).agg(
        markets=("ticker", "size"), total_volume=("volume", "sum"),
        median_volume=("volume", "median"), share_zero=("volume", lambda v: (v <= 0).mean()))
    dv["share_of_volume"] = dv["total_volume"] / dv["total_volume"].sum()
    dvo = dv.reset_index()
    dvo["dist_bin"] = dvo["dist_bin"].astype(str)
    out.append("## Volume vs strike distance (strike - series median outcome, inches)\n"
               + _md(dvo, {"total_volume": ",.0f", "median_volume": ",.0f", "share_zero": ".0%",
                           "share_of_volume": ".1%", "markets": ".0f"})
               + "\nseries medians (in): " + ", ".join(f"{k}={v:.2f}" for k, v in med.items()))

    fig, ax = plt.subplots(figsize=(8, 4.4), dpi=150)
    x = np.arange(len(dv))
    ax.bar(x, dv["median_volume"].fillna(0), color=BLUE, width=0.7, zorder=3)
    top = np.nanmax(dv["median_volume"].values)
    for i, (n, v) in enumerate(zip(dv["markets"], dv["median_volume"].fillna(0))):
        ax.text(i, v + top * 0.02, f"n={n}", ha="center", fontsize=8, color=MUTED)
    ax.set_xticks(x, labels, rotation=30, ha="right", fontsize=8)
    _style(ax, "Median volume per settled monthly-rain market, by strike distance",
           "strike minus the series' median realised monthly total (inches)",
           "median volume per market (contracts)")
    fig.tight_layout()
    fig.savefig(FIGURES / "b2_volume_vs_strike_distance.png")
    plt.close(fig)

    # ---- calibration -----------------------------------------------------------------------
    cal_rows, cal_tabs = [], []
    for h in HORIZONS:
        ph = K.prices_at_horizon(f, cd, h)
        cal_rows.append(ph)
        for kind in ("last_price", "mid"):
            ct = K.calibration_table(ph[kind], ph["outcome"])
            ct.insert(0, "price_kind", kind)
            ct.insert(0, "horizon_days", h)
            cal_tabs.append(ct)
    cal = pd.concat(cal_tabs, ignore_index=True)
    cal.to_csv(PROCESSED / "kalshi_rain_calibration.csv", index=False)
    ph_all = pd.concat(cal_rows, ignore_index=True)

    rng = np.random.default_rng(473)
    summ = []
    for h in HORIZONS:
        for kind in ("last_price", "mid"):
            d = ph_all[ph_all["horizon_days"] == h].dropna(subset=[kind])
            ls, fav = d[d[kind] < 0.20], d[d[kind] > 0.80]
            g_ls, lo_ls, hi_ls = _boot_gap(ls, kind, rng)
            g_f, lo_f, hi_f = _boot_gap(fav, kind, rng)
            summ.append({"horizon_days": h, "price": kind, "n": len(d),
                         "events": d["event_ticker"].nunique(),
                         "brier": float(((d[kind] - d["outcome"]) ** 2).mean()) if len(d) else math.nan,
                         "n_longshot(<0.20)": len(ls), "longshot_mean_price": ls[kind].mean(),
                         "longshot_yes_rate": ls["outcome"].mean(), "longshot_gap": g_ls,
                         "longshot_gap_ci": f"[{lo_ls:.3f}, {hi_ls:.3f}]",
                         "n_favorite(>0.80)": len(fav), "favorite_mean_price": fav[kind].mean(),
                         "favorite_yes_rate": fav["outcome"].mean(), "favorite_gap": g_f,
                         "favorite_gap_ci": f"[{lo_f:.3f}, {hi_f:.3f}]",
                         "median_stale_days": d["stale_days"].median()})
    summ = pd.DataFrame(summ)
    summ.to_csv(RAW_K / "calibration_summary.csv", index=False)
    out.append("## Calibration summary (gap = realised YES rate - mean price; 95% CI from event "
               "cluster bootstrap)\n" + _md(summ, {
                   "brier": ".3f", "longshot_gap": ".3f", "favorite_gap": ".3f",
                   "longshot_mean_price": ".3f", "longshot_yes_rate": ".3f",
                   "favorite_mean_price": ".3f", "favorite_yes_rate": ".3f",
                   "median_stale_days": ".1f"}))
    c7 = cal[(cal["horizon_days"] == 7) & (cal["price_kind"] == "last_price")]
    out.append("## Calibration bins, last traded price 7 days before scheduled close\n" + _md(
        c7[["bin_lo", "bin_hi", "n", "mean_price", "yes_rate", "ci_lo", "ci_hi", "gap"]],
        {"bin_lo": ".2f", "bin_hi": ".2f", "mean_price": ".3f", "yes_rate": ".3f",
         "ci_lo": ".3f", "ci_hi": ".3f", "gap": ".3f"}))

    fig, ax = plt.subplots(figsize=(5.8, 5.6), dpi=150)
    ax.plot([0, 1], [0, 1], linestyle="--", color=GRAY, linewidth=1.2, zorder=2,
            label="perfect calibration")
    for h, color, marker, off in ((7, BLUE, "o", -0.006), (1, ORANGE, "s", 0.006)):
        ct = cal[(cal["horizon_days"] == h) & (cal["price_kind"] == "last_price") & (cal["n"] > 0)]
        ax.errorbar(ct["mean_price"] + off, ct["yes_rate"],
                    yerr=[ct["yes_rate"] - ct["ci_lo"], ct["ci_hi"] - ct["yes_rate"]],
                    fmt=marker, color=color, markersize=7, capsize=2, linewidth=1.2, zorder=3,
                    markeredgecolor="white", markeredgewidth=1,
                    label=f"{h} day{'s' if h > 1 else ''} before close (n={int(ct['n'].sum())})")
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.02, 1.02)
    _style(ax, "Pooled calibration, Kalshi monthly-rain markets",
           "last traded YES price (dollars = implied probability)",
           "share resolving YES (Wilson 95% CI)")
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    fig.tight_layout()
    fig.savefig(FIGURES / "b2_calibration.png")
    plt.close(fig)

    # ---- volume by series figure -----------------------------------------------------------
    t2 = tab[tab["series"] != "ALL"].sort_values("total_volume")
    fig, ax = plt.subplots(figsize=(8, 9), dpi=150)
    y = np.arange(len(t2))
    colors = [BLUE if s else GRAY for s in t2["site"]]
    ax.barh(y, t2["total_volume"].clip(lower=1), color=colors, height=0.7, zorder=3)
    ax.set_xscale("log")
    ax.set_yticks(y, [f"{c} ({s})" if s else c for c, s in zip(t2["city"], t2["site"])],
                  fontsize=8)
    for yi, (v, fm) in enumerate(zip(t2["total_volume"], t2["first_month"])):
        ax.text(max(v, 1) * 1.15, yi, f"{v:,.0f}  (first month {fm})", va="center", fontsize=7,
                color=MUTED)
    ax.set_xlim(1, t2["total_volume"].max() * 40)
    _style(ax, "Kalshi monthly-rain series: total contracts traded through 2026-10-29",
           "total volume (contracts, log scale; zero plotted at 1)", "")
    ax.text(0.99, 0.02, "blue = project study site; gray = other cities", transform=ax.transAxes,
            ha="right", fontsize=8, color=MUTED)
    fig.tight_layout()
    fig.savefig(FIGURES / "b2_volume_by_series.png")
    plt.close(fig)

    # ---- order-book depth and hedge capacity -----------------------------------------------
    # A farmer hedging drought BUYS NO on "above X inches" (pays $1 if the month is dry), which
    # lifts resting YES bids at NO price 1 - bid. A wet-side hedge buys YES, lifting NO bids.
    # "Useful" levels exclude near-certain contracts: a NO bought at 0.99 costs 99c for $1.
    ob = ob.copy()
    ob["yes_bids_l"] = ob["yes_bids"].map(json.loads)
    ob["no_bids_l"] = ob["no_bids"].map(json.loads)
    cap = []
    for r in ob.itertuples(index=False):
        q, c, fe = _take(r.yes_bids_l)
        qu, cu, feu = _take(r.yes_bids_l, max_price=USEFUL_MAX_PRICE)
        q5, c5, fe5 = _take(r.yes_bids_l, within=0.05)
        yq, yc, _ = _take(r.no_bids_l)
        yqu, _, _ = _take(r.no_bids_l, max_price=USEFUL_MAX_PRICE)
        cap.append({"series_ticker": r.series_ticker, "study_site": r.study_site,
                    "event_ticker": r.event_ticker, "contract_month": r.contract_month,
                    "strike": r.strike, "best_yes_bid": r.best_yes_bid,
                    "best_yes_ask": r.best_yes_ask, "spread": r.spread,
                    "no_payout_all": q, "no_premium_all": c, "no_net_all": q - c,
                    "no_payout_useful": qu, "no_premium_useful": cu + feu,
                    "no_net_useful": qu - cu - feu,
                    "no_payout_5c": q5, "no_premium_5c": c5 + fe5,
                    "yes_payout_all": yq, "yes_payout_useful": yqu})
    cap = pd.DataFrame(cap)
    snap = ob["snapshot_utc"].iat[0] if len(ob) else ""
    nov = cap[cap["contract_month"] == "2026-11"].copy()
    nov["study_site"] = nov["study_site"].fillna("")
    per_city = nov.groupby("series_ticker").agg(
        site=("study_site", "first"), strikes=("strike", "size"),
        two_sided_strikes=("spread", lambda s: int(s.notna().sum())),
        median_spread_cents=("spread", lambda s: 100 * s.median()),
        no_payout_all=("no_payout_all", "sum"), no_net_all=("no_net_all", "sum"),
        no_payout_useful=("no_payout_useful", "sum"),
        no_premium_useful=("no_premium_useful", "sum"),
        no_net_useful=("no_net_useful", "sum"),
        max_strike_no_payout_useful=("no_payout_useful", "max"),
        no_payout_5c=("no_payout_5c", "sum"),
        yes_payout_useful=("yes_payout_useful", "sum")).reset_index()
    per_city.insert(1, "snapshot_utc", snap)
    per_city.to_csv(capacity_path(snap), index=False)
    log(f"wrote {capacity_path(snap).name}")
    study = per_city[per_city["site"] != ""].drop(columns="snapshot_utc")
    others = per_city[per_city["site"] == ""]
    fmt0 = {c: ",.0f" for c in per_city.columns if c.startswith(("no_", "yes_", "max_"))}
    fmt0["median_spread_cents"] = ".0f"
    out.append(f"## Hedge capacity, Nov 2026 events, order books at {snap}\n"
               f"(payout = $ paid if the contract wins = contracts; 'useful' = levels priced "
               f"<= {USEFUL_MAX_PRICE:.2f}; net = payout - premium - taker fees)\n"
               + _md(study, fmt0)
               + f"\nOther cities (n={len(others)}): median useful NO payout "
                 f"{others['no_payout_useful'].median():,.0f}; median useful net "
                 f"{others['no_net_useful'].median():,.0f}; median max single strike "
                 f"{others['max_strike_no_payout_useful'].median():,.0f}")

    fig, axes = plt.subplots(2, 4, figsize=(11.5, 5.8), dpi=150, sharey=True)
    sub = nov[nov["study_site"] != ""]
    ymax = max(10.0, sub[["no_payout_useful", "yes_payout_useful"]].max().max())
    for ax, site in zip(axes.flat, ALL_SITES):
        d = sub[sub["study_site"] == site].sort_values("strike")
        xs = np.arange(len(d))
        ax.bar(xs - 0.19, d["no_payout_useful"], width=0.36, color=BLUE, zorder=3,
               label="buy NO (pays if dry)")
        ax.bar(xs + 0.19, d["yes_payout_useful"], width=0.36, color="white", edgecolor=ORANGE,
               hatch="////", linewidth=0.8, zorder=3, label="buy YES (pays if wet)")
        ax.set_xticks(xs, [f"{s:g}" for s in d["strike"]], fontsize=7)
        ax.set_yscale("symlog", linthresh=10)
        ax.set_ylim(0, ymax * 2)
        _style(ax, f"{site} ({ALL_SITES[site]['kalshi_series']})", "strike (inches)", "")
        ax.title.set_fontsize(9)
    for a in axes[:, 0]:
        a.set_ylabel("$ payout purchasable", color=MUTED)
    axes[0, 0].legend(frameon=False, fontsize=7, loc="upper right")
    fig.suptitle(f"Resting depth at prices <= ${USEFUL_MAX_PRICE:.2f}, Nov 2026 monthly-rain "
                 f"events (order books {snap}; symlog scale)", fontsize=10.5, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(FIGURES / f"b2_orderbook_depth_study_sites_{snapshot_day(snap)}.png")
    plt.close(fig)

    # ---- liquidity incentive programs ------------------------------------------------------
    ipp = PROCESSED / "kalshi_rain_incentive_programs.csv"
    if ipp.exists():
        ip = pd.read_csv(ipp)
        g = ip.groupby(["incentive_description"]).agg(
            programs=("id", "size"), markets=("market_ticker", "nunique"),
            total_reward_usd=("reward_usd", "sum"), median_reward_usd=("reward_usd", "median"),
            median_days=("days", "median"), first_start=("start_date", "min"),
            last_end=("end_date", "max")).reset_index()
        g["first_start"] = g["first_start"].str[:10]
        g["last_end"] = g["last_end"].str[:10]
        st = ip[ip["series_ticker"].isin(STUDY_SERIES)].groupby("series_ticker").agg(
            programs=("id", "size"), total_reward_usd=("reward_usd", "sum"),
            latest_end=("end_date", "max")).reset_index()
        out.append("## Liquidity incentive programs on monthly-rain markets\n"
                   + _md(g, {"programs": ",.0f", "markets": ",.0f", "total_reward_usd": ",.0f",
                             "median_reward_usd": ",.0f", "median_days": ".1f"})
                   + "\n\nStudy-site series:\n" + _md(st, {"programs": ",.0f",
                                                           "total_reward_usd": ",.0f"}))

    # ---- trades (study sites) --------------------------------------------------------------
    if len(tr):
        trm = tr.merge(mk_all[["ticker", "close_time", "study_site"]], on="ticker", how="left")
        trm["days_to_close"] = (trm["close_time"].map(K.iso_to_ts) - trm["created_ts"]) / DAY
        rows = []
        for s, d in trm.groupby("series_ticker"):
            tot = d["count"].sum()
            rows.append({"series": s, "site": d["study_site"].iat[0], "trades": len(d),
                         "contracts": tot, "median_trade_size": d["count"].median(),
                         "p90_trade_size": d["count"].quantile(0.9),
                         "max_trade_size": d["count"].max(),
                         "share_contracts_last_7d": d.loc[d["days_to_close"] <= 7, "count"].sum() / tot,
                         "share_taker_yes": d.loc[d["taker_side"] == "yes", "count"].sum() / tot,
                         "yes_premium_usd": (d["count"] * d["yes_price"]).sum()})
        tt = pd.DataFrame(rows)
        out.append("## Trades at study-site series\n" + _md(tt, {
            "trades": ",.0f", "contracts": ",.0f", "median_trade_size": ",.1f",
            "p90_trade_size": ",.0f", "max_trade_size": ",.0f",
            "share_contracts_last_7d": ".0%", "share_taker_yes": ".0%",
            "yes_premium_usd": ",.0f"}))

    text = "\n\n".join(out)
    (RAW_K / "liquidity_stats.md").write_text(text, encoding="utf-8")
    print(text)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--refresh", action="store_true", help="re-download lists and open-market data")
    ap.add_argument("--skip-catalog", action="store_true")
    ap.add_argument("--skip-candles", action="store_true")
    ap.add_argument("--skip-trades", action="store_true")
    ap.add_argument("--skip-orderbooks", action="store_true")
    ap.add_argument("--all-trades", action="store_true", help="trades for every rain series")
    ap.add_argument("--stats", action="store_true", help="only compute stats/figures (offline)")
    ap.add_argument("--acis-check", action="store_true",
                    help="compare settled ladders with ACIS station monthly totals")
    ap.add_argument("--orderbooks-only", action="store_true",
                    help="refresh live market lists (not written), the incentive-program list and "
                         "a new dated order-book snapshot; leaves markets/candles/trades/outcomes as they are")
    ap.add_argument("--orderbook", default=None,
                    help="with --stats: order-book summary CSV to use (default: latest)")
    args = ap.parse_args(argv)

    if args.acis_check:
        acis_check(args.refresh)
        return 0
    if args.stats:
        make_stats(args.orderbook)
        return 0

    client = K.KalshiClient()
    if args.orderbooks_only:
        markets = pull_rain_markets(client, refresh=True, write=False)
        pull_incentives(client, refresh=True)
        snapshot_orderbooks(client, markets)
        log(f"done; {client.n_requests} HTTP requests this run")
        return 0
    cutoff = K.load_or_fetch_json(RAW_K / "historical_cutoff.json", client.historical_cutoff,
                                  LIST_TTL, args.refresh)
    log("historical cutoff:", cutoff)
    if not args.skip_catalog:
        build_catalog(client, args.refresh)
    markets = pull_rain_markets(client, args.refresh)
    write_outcomes(markets)
    if not args.skip_candles:
        pull_candles(client, markets, cutoff, args.refresh)
    if not args.skip_trades:
        pull_trades(client, markets, None if args.all_trades else STUDY_SERIES, args.refresh)
    pull_incentives(client, args.refresh)
    if not args.skip_orderbooks:
        snapshot_orderbooks(client, markets)
    log(f"done; {client.n_requests} HTTP requests this run")
    return 0


if __name__ == "__main__":
    sys.exit(main())
