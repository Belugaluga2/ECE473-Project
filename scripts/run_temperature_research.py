"""Temperature-risk research: Kalshi temperature contracts and station heat climatology.

Run from the repo root (needs internet; about 5-10 minutes, mostly the market pull):
    python scripts/run_temperature_research.py            # reuse cached market pull if present
    python scripts/run_temperature_research.py --refresh  # re-pull every market

Doc: docs/research/23_temperature_risk.md

What it does
1. Lists every Kalshi "Climate and Weather" series and keeps the US city temperature ones
   (daily high/low, weekly, monthly, degree-day, annual). International cities are dropped.
2. Pulls every market of those series from the live and historical tiers
   (cached at $AGRI_HEDGE_RAW_DIR/kalshi_temperature_markets.parquet).
3. Per series: settlement station from the rules text, first and last measured date, how far
   ahead of the measured period each event was listed (open_time vs the period start), and
   volume, overall and for Jun-Aug 2026.
4. For Jun-Aug 2026 daily-high events at the study cities: whether "high above X F" can be
   built from that day's ladder (X = 90, 95, 100), and the ladder's range.
5. Order-book snapshot of the newest open daily events at the study cities plus the open
   degree-day and monthly markets.
6. Jun-Aug heat indexes at the study stations from NOAA ACIS threaded daily Tmax, 1991-2025:
   days with Tmax > X and degree-days above X (sum of max(Tmax - X, 0)).
7. Cattle heat-stress days (temperature-humidity index, THI) at the seven PRF stations from
   Iowa Environmental Mesonet ASOS hourly data, 2005-2024 (cached at $AGRI_HEDGE_RAW_DIR/iem/).

Outputs (data/processed/): kalshi_temperature_series_summary.csv,
kalshi_temperature_ladder_coverage.csv, kalshi_temperature_orderbook_<YYYYMMDD>.csv,
station_summer_heat_index.csv, station_cattle_thi_days.csv. Plain-text tables on stdout.
`--climate-only` runs steps 6-7 without touching Kalshi.
"""
from __future__ import annotations

import argparse
import re
import time
from datetime import datetime, timezone

import pandas as pd
import requests

from agri_hedge.config import PROCESSED, RAW
from agri_hedge.kalshi import KalshiClient

US_SERIES = re.compile(r"KX(HIGH|LOW|AVGT|WEEKHT|HDD|CDD|MSNLOWT|SJCLOWT|MONTHLOW|YEARLOW|MAXTEMP|HEATA|"
                       r"HEATWARNING|DENHIGH|HOUHIGH|PHILHIGH|DVHIGH|MINNYC|AVGTEMP)")
# International daily series use ICAO-style codes (KXHIGHTEGLL London, KXLOWTRJTT Tokyo, ...).
INTL = re.compile(r"KX(HIGH|LOW)T(E[A-Z]{3}|L[A-Z]{3}|R[A-Z]{3}|V[A-Z]{3}|W[A-Z]{3}|Y[A-Z]{3}|Z[A-Z]{3}|"
                  r"O[A-Z]{3}|CYYZ|MMMX|SBGR)$")
STUDY_DAILY_HIGH = ["KXHIGHTDAL", "KXHIGHTSATX", "KXHIGHTOKC", "KXHIGHDEN", "KXHIGHCHI"]
BOOK_SERIES = ["KXHIGHTDAL", "KXHIGHTSATX", "KXHIGHTOKC", "KXHIGHDEN", "KXLOWTDAL", "KXHDDCVG", "KXSJCLOWT"]
PERIOD_SERIES = re.compile(r"KX(AVGT|HDD|SJC|HEAT|WEEK)")  # period start is read from the rules text
ACIS_STATIONS = ["DFW", "SAT", "OKC", "SGF", "DEN", "ABQ", "TPA", "ORD"]
MON3 = {m: i for i, m in enumerate("JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split(), 1)}
MONTHS = {m: i for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July",
                                      "August", "September", "October", "November", "December"], 1)}
CACHE = RAW / "kalshi_temperature_markets.parquet"
KEEP_FIELDS = ["ticker", "event_ticker", "title", "yes_sub_title", "status", "open_time", "close_time",
               "volume_fp", "open_interest_fp", "strike_type", "floor_strike", "cap_strike",
               "rules_primary", "result"]


def event_date(event_ticker):
    """Measured date from a daily ticker suffix like -26JUL04; NaT if absent."""
    m = re.search(r"-(\d{2})([A-Z]{3})(\d{2})$", event_ticker)
    if m and m.group(2) in MON3:
        return pd.Timestamp(2000 + int(m.group(1)), MON3[m.group(2)], int(m.group(3)))
    return pd.NaT


def period_start(rules):
    """First 'Month D, YYYY' (or 'Mon D, YYYY') in the rules text: start of a weekly/monthly period."""
    if not isinstance(rules, str):
        return pd.NaT
    m = re.search(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.? (\d{1,2}),? (\d{4})", rules)
    if not m:
        return pd.NaT
    return pd.Timestamp(int(m.group(3)), MON3[m.group(1).upper()], int(m.group(2)))


def pull_markets(client, refresh):
    if CACHE.exists() and not refresh:
        return pd.read_parquet(CACHE)
    series = client.list_series(category="Climate and Weather")
    keep = sorted(s["ticker"] for s in series
                  if US_SERIES.match(s["ticker"]) and not INTL.match(s["ticker"]) and s["ticker"] != "KXHIGHNYD")
    rows = []
    for t in keep:
        for m in client.list_all_markets(t):
            rows.append({k: m.get(k) for k in KEEP_FIELDS} | {"series": t, "tier": m["_tier"]})
        print(f"  {t}: {sum(r['series'] == t for r in rows)} markets", flush=True)
    df = pd.DataFrame(rows)
    df.to_parquet(CACHE)
    return df


def series_summary(df):
    df = df.copy()
    df["open"] = pd.to_datetime(df.open_time, utc=True, format="ISO8601")
    df["vol"] = pd.to_numeric(df.volume_fp, errors="coerce").fillna(0)
    df["station"] = df.rules_primary.str.extract(r"\((CLI[A-Z]{3})\)")[0].fillna(
        df.rules_primary.str.extract(r"\b(K[A-Z]{3})\b")[0])
    ev = df.groupby(["series", "event_ticker"]).agg(
        open=("open", "min"), vol=("vol", "sum"), station=("station", "first"),
        status=("status", "first"), rules=("rules_primary", "first")).reset_index()
    ev["start"] = ev.event_ticker.map(event_date)
    is_period = ev.series.str.match(PERIOD_SERIES)
    ev.loc[is_period, "start"] = ev.loc[is_period, "rules"].map(period_start)
    # "From this market's issuance ... through <date>" (KXMSNLOWT): the window opens at listing.
    from_issuance = ev.rules.str.contains("issuance", na=False)
    ev.loc[from_issuance, "start"] = ev.loc[from_issuance, "open"].dt.tz_convert(None).dt.normalize()
    # Lead = listing time to local midnight at the start of the measured period. Local midnight is
    # taken as 06:00 UTC (US Central standard time); Eastern/Mountain sites shift this by 1 h.
    ev["lead_h"] = (ev.start.dt.tz_localize("UTC") + pd.Timedelta(hours=6) - ev.open).dt.total_seconds() / 3600
    ev["listed_days_before"] = (ev.start - ev.open.dt.tz_convert(None).dt.normalize()).dt.days

    out = []
    for s, g in ev.groupby("series"):
        g = g.dropna(subset=["start"])
        if g.empty:
            continue
        summer = g[(g.start >= "2026-06-01") & (g.start <= "2026-08-31")]
        out.append({
            "series": s, "station": g.station.dropna().iloc[-1] if g.station.notna().any() else "",
            "n_events": len(g), "first_period": g.start.min().date(), "last_period": g.start.max().date(),
            "lead_h_median": round(g.lead_h.median(), 1), "lead_h_max": round(g.lead_h.max(), 1),
            "share_listed_day_before": round((g.listed_days_before == 1).mean(), 4),
            "max_days_before": int(g.listed_days_before.max()),
            "vol_per_event_median": round(g.vol.median()), "n_summer26": len(summer),
            "vol_per_event_summer26_median": round(summer.vol.median()) if len(summer) else None,
            "vol_summer26_total": round(summer.vol.sum()), "vol_total": round(g.vol.sum()),
            "n_open_events_now": int(g.status.isin(["active", "initialized"]).sum()),
        })
    return pd.DataFrame(out), ev


def ladder_coverage(df):
    d = df[df.series.isin(STUDY_DAILY_HIGH)].copy()
    d["start"] = d.event_ticker.map(event_date)
    d = d[(d.start >= "2026-06-01") & (d.start <= "2026-08-31")]
    rows = []
    for s, g0 in d.groupby("series"):
        lows_by_event = {}
        for et, g in g0.groupby("event_ticker"):
            lows = set()
            for _, r in g.iterrows():  # integer lower edge of each market's YES range
                if r.strike_type == "greater":
                    lows.add(int(r.floor_strike) + 1)
                elif r.strike_type == "between":
                    lows.add(int(r.floor_strike))
            lows_by_event[et] = lows
        caps = g0[g0.strike_type == "less"].groupby("event_ticker").cap_strike.first()
        floors = g0[g0.strike_type == "greater"].groupby("event_ticker").floor_strike.first()
        winners = g0[g0.result == "yes"]
        # Share of days the realized high fell inside the four middle 2F bins (not a tail): a
        # measure of how well the ladder, set the day before, already centers on the outcome.
        mid_share = round((winners.strike_type == "between").mean(), 2) if len(winners) else None
        for X in (90, 95, 100):
            ok = [X + 1 in lows for lows in lows_by_event.values()]
            rows.append({"series": s, "threshold_F": X, "days": len(ok),
                         "share_days_buildable": round(sum(ok) / len(ok), 2),
                         "ladder_low_tail_median": caps.median(), "ladder_high_tail_median": floors.median(),
                         "share_days_middle_bin_won": mid_share})
    return pd.DataFrame(rows)


def book_snapshot(client):
    now = datetime.now(timezone.utc)
    rows = []
    for s in BOOK_SERIES:
        ms = client.list_markets(series_ticker=s, status="open")
        if not ms:
            continue
        if s.startswith(("KXHIGH", "KXLOW")):
            last = max(m["event_ticker"] for m in ms)
            ms = [m for m in ms if m["event_ticker"] == last]
        for m in ms:
            ob = client.get_orderbook(m["ticker"]).get("orderbook_fp") or {}
            yes = [(float(p), float(q)) for p, q in (ob.get("yes_dollars") or [])]
            no = [(float(p), float(q)) for p, q in (ob.get("no_dollars") or [])]
            ask = round(1 - max(p for p, _ in no), 2) if no else None
            near = [(p, q) for p, q in no if ask is not None and 1 - p <= ask + 0.05 + 1e-9]
            rows.append({"series": s, "ticker": m["ticker"], "strike": m.get("yes_sub_title"),
                         "yes_bid": max((p for p, _ in yes), default=None), "yes_ask": ask,
                         "yes_contracts_within_5c": round(sum(q for _, q in near)),
                         "yes_cost_within_5c_usd": round(sum((1 - p) * q for p, q in near)),
                         "yes_contracts_all": round(sum(q for _, q in no)),
                         "no_contracts_all": round(sum(q for _, q in yes)),
                         "volume": m.get("volume_fp"), "open_interest": m.get("open_interest_fp"),
                         "snapshot_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ")})
    return pd.DataFrame(rows), now


def acis_heat_index():
    rows = []
    for st in ACIS_STATIONS:
        j = requests.post("https://data.rcc-acis.org/StnData", timeout=120,
                          json={"sid": st + "thr", "sdate": "1991-01-01", "edate": "2025-12-31",
                                "elems": [{"name": "maxt"}]}).json()
        d = pd.DataFrame(j["data"], columns=["date", "tmax"])
        d["date"] = pd.to_datetime(d.date)
        d["tmax"] = pd.to_numeric(d.tmax, errors="coerce")  # "M" (missing) -> NaN
        d = d[d.date.dt.month.isin([6, 7, 8])].assign(yr=lambda x: x.date.dt.year)
        agg = {"miss": ("tmax", lambda s: int(s.isna().sum()))}
        for X in (90, 95, 100):
            d[f"dd{X}"] = (d.tmax - X).clip(lower=0)
            d[f"n{X}"] = (d.tmax > X).astype(float)
            agg[f"dd{X}"] = (f"dd{X}", "sum")
            agg[f"n{X}"] = (f"n{X}", "sum")
        y = d.groupby("yr").agg(**agg)
        y = y[y.miss <= 5]
        for c in ("n95", "n100", "dd90", "dd95"):
            rows.append({"station": st, "index": c, "years": len(y), "mean": round(y[c].mean(), 1),
                         "sd": round(y[c].std(), 1), "min": y[c].min(), "max": y[c].max(),
                         "max_year": int(y[c].idxmax())})
        time.sleep(0.5)
    return pd.DataFrame(rows)


def thi_days():
    """Cattle heat-stress days per year, 2005-2024, from IEM ASOS hourly temperature and humidity.

    THI (F) = T - (0.55 - 0.0055 RH)(T - 58), the same index as the NRC (1971) Celsius form
    0.8 T + (RH/100)(T - 14.4) + 46.4 used by Mader et al. (2006). Days need >= 18 hourly
    observations; local day = UTC plus the station's standard-time offset (no DST).
    Counts: days with daily max THI >= 75 / 79 / 84 (LWSI alert / danger / emergency),
    nights with daily min THI >= 75 (no night relief), and days with hourly Tmax >= 95 F.
    """
    offsets = {"DFW": -6, "SAT": -6, "OKC": -6, "SGF": -6, "DEN": -7, "ABQ": -7, "TPA": -5}
    cache = RAW / "iem"
    cache.mkdir(parents=True, exist_ok=True)
    rows = []
    for st, off in offsets.items():
        f = cache / f"{st}.csv"
        if not f.exists():
            url = ("https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station=" + st +
                   "&data=tmpf&data=relh&year1=2005&month1=1&day1=1&year2=2025&month2=1&day2=1"
                   "&tz=Etc/UTC&format=onlycomma&latlon=no&missing=M&report_type=3")
            f.write_bytes(requests.get(url, timeout=600).content)
            time.sleep(1)
        d = pd.read_csv(f, na_values="M")
        d = d.dropna(subset=["tmpf", "relh"])
        d["local"] = pd.to_datetime(d.valid) + pd.Timedelta(hours=off)
        d["day"] = d.local.dt.normalize()
        d["thi"] = d.tmpf - (0.55 - 0.0055 * d.relh) * (d.tmpf - 58)
        g = d.groupby("day").agg(n=("thi", "size"), mx=("thi", "max"), mn=("thi", "min"), tmax=("tmpf", "max"))
        g = g[(g.n >= 18) & (g.index.year >= 2005) & (g.index.year <= 2024)]
        y = pd.DataFrame({"max_thi_ge75": g.mx >= 75, "max_thi_ge79": g.mx >= 79, "max_thi_ge84": g.mx >= 84,
                          "min_thi_ge75": g.mn >= 75, "tmax_ge95": g.tmax >= 95}).groupby(g.index.year).sum()
        rows.append({"station": st, "years": len(y), **{c: round(y[c].mean(), 1) for c in y.columns}})
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="re-pull every market (ignore cache)")
    ap.add_argument("--climate-only", action="store_true", help="skip Kalshi; only the station heat tables")
    args = ap.parse_args()
    client = KalshiClient()

    if args.climate_only:
        return climate_tables()
    print("Pulling markets ...")
    df = pull_markets(client, args.refresh)
    summ, _ = series_summary(df)
    summ.to_csv(PROCESSED / "kalshi_temperature_series_summary.csv", index=False)
    print("\n## Series summary\n")
    print(summ.to_string(index=False))

    cov = ladder_coverage(df)
    cov.to_csv(PROCESSED / "kalshi_temperature_ladder_coverage.csv", index=False)
    print("\n## Jun-Aug 2026 ladder coverage\n")
    print(cov.to_string(index=False))

    book, now = book_snapshot(client)
    book.to_csv(PROCESSED / f"kalshi_temperature_orderbook_{now:%Y%m%d}.csv", index=False)
    print(f"\n## Order books at {now:%Y-%m-%d %H:%M} UTC\n")
    print(book.drop(columns="snapshot_utc").to_string(index=False))
    print(book.groupby("series")[["yes_contracts_within_5c", "yes_cost_within_5c_usd"]].sum().to_string())
    climate_tables()


def climate_tables():
    heat = acis_heat_index()
    heat.to_csv(PROCESSED / "station_summer_heat_index.csv", index=False)
    print("\n## Jun-Aug heat indexes, 1991-2025\n")
    print(heat.to_string(index=False))
    thi = thi_days()
    thi.to_csv(PROCESSED / "station_cattle_thi_days.csv", index=False)
    print("\n## Cattle heat-stress (THI) days per year, 2005-2024\n")
    print(thi.to_string(index=False))


if __name__ == "__main__":
    main()
