"""Pilot numbers for docs/FINAL_PROJECT_PROPOSAL.md: how much risk is still open at listing.

Three computations:

1. Monthly rain (offline): for every settled single-month Kalshi rain market with a quote
   before the month began, H = E[p(1-p)] / E[pc(1-pc)] from the first quote with a spread of
   20 cents or less (p) and the 1991-2020 station climatology (pc), and the outcome-based
   H = E[(X-p)^2] / E[pc(1-pc)].
2. Daily highs (needs internet unless the quote cache exists): the last 40 settled days of
   KXHIGHNY, KXHIGHTPHX, KXHIGHTDAL. Kalshi centers each day's brackets on the forecast, so
   per-bracket climatology is biased; instead each day's six opening mids give an implied mean
   and variance of the high, compared with the 1991-2020 variance of the high for that date
   (+-7 days). H(price) = E[implied var] / E[clim var]; H(outcome) = E[(T - implied mean)^2] /
   E[clim var], with T from ACIS.
3. Pooling: holdout HE of a Kalshi hedge for the average PRF payout of N grids within 75
   miles of each site's airport (each site's first farm's elections), N = 1 ... all.

Writes data/processed/insurability_pilot_{rain,highs,pool}.csv and caches the Kalshi opening
quotes in data/processed/kalshi_high_opening_quotes.csv. Run time: under a minute offline,
about 5 minutes when it has to pull the daily-high quotes.
"""
from __future__ import annotations

import json
import re
import time
import urllib.request
from dataclasses import replace
from datetime import datetime

import numpy as np
import pandas as pd

from agri_hedge import hedge_builder as hb, optimizer as op
from agri_hedge.comparison import TEST, TRAIN
from agri_hedge.config import PROCESSED

HIGH_SERIES = {"KXHIGHNY": "NYC", "KXHIGHTPHX": "PHX", "KXHIGHTDAL": "DFW"}
QUOTES = PROCESSED / "kalshi_high_opening_quotes.csv"
MON = {m: i + 1 for i, m in enumerate("JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split())}


def _acis_maxt(sid: str, start: str, end: str) -> pd.Series:
    body = json.dumps({"sid": sid, "sdate": start, "edate": end, "elems": "maxt"}).encode()
    for attempt in range(5):
        try:
            req = urllib.request.Request("https://data.rcc-acis.org/StnData", data=body,
                                         headers={"Content-Type": "application/json"})
            rows = json.loads(urllib.request.urlopen(req, timeout=120).read())["data"]
            break
        except Exception:
            if attempt == 4:
                raise
            time.sleep(4 * (attempt + 1))
    s = pd.Series({pd.Timestamp(d): v for d, v in rows})
    return pd.to_numeric(s, errors="coerce").dropna()


def _first_quote(bids, asks):
    for b, a in zip(bids, asks):
        if pd.notna(b) and pd.notna(a) and 0 < a - b <= 0.2:
            return (a + b) / 2
    return None


def rain_listing() -> pd.DataFrame:
    sm = pd.read_csv(PROCESSED / "station_monthly_precip.csv")
    m = pd.read_parquet(PROCESSED / "kalshi_rain_markets.parquet")
    c = pd.read_parquet(PROCESSED / "kalshi_rain_daily_candles.parquet")
    m = m[(m.status == "finalized") & m.is_single_month & m.result.isin(["yes", "no"])
          & m.cli_code.isin(sm.cli_code.unique())]
    rows = []
    for _, mk in m.iterrows():
        y, mo = map(int, str(mk.contract_month).split("-"))
        hist = sm[(sm.cli_code == mk.cli_code) & (sm.month == mo) & sm.year.between(1991, 2020)].precip_in
        cs = c[(c.ticker == mk.ticker) & (pd.to_datetime(c.date) < pd.Timestamp(y, mo, 1))].sort_values("date")
        p = _first_quote(cs.yes_bid_close, cs.yes_ask_close)
        if p is None:
            continue
        rows.append({"ticker": mk.ticker, "cli_code": mk.cli_code, "contract_month": mk.contract_month,
                     "strike_in": float(mk.floor_strike), "open_mid": p,
                     "clim_p": float(np.clip((hist > mk.floor_strike).mean(), 0.005, 0.995)),
                     "outcome": float(mk.result == "yes")})
    return pd.DataFrame(rows)


def _pull_high_quotes(n_days: int = 40) -> pd.DataFrame:
    from agri_hedge.kalshi import KalshiClient
    k = KalshiClient(timeout=20, max_retries=2)
    rows = []
    for series in HIGH_SERIES:
        ms = k.list_markets(series, status="settled")
        ms = ms if isinstance(ms, list) else ms.get("markets", [])
        ms = sorted(ms, key=lambda m: m.get("close_time", ""))[-6 * n_days:]
        for m in ms:
            ot = int(datetime.fromisoformat(m["open_time"].replace("Z", "+00:00")).timestamp())
            cs = k.get_candlesticks(series, m["ticker"], ot, ot + 6 * 3600, period_interval=60)
            cs = cs.get("candlesticks", cs) if isinstance(cs, dict) else cs
            bids, asks = [], []
            for cd in cs:
                yb, ya = cd.get("yes_bid") or {}, cd.get("yes_ask") or {}
                try:
                    b = float(yb.get("close_dollars") or yb.get("close"))
                    a = float(ya.get("close_dollars") or ya.get("close"))
                except (TypeError, ValueError):
                    continue
                if b > 1:
                    b, a = b / 100, a / 100
                bids.append(b), asks.append(a)
            rows.append({"series": series, "ticker": m["ticker"], "event": m["event_ticker"],
                         "open_time": m["open_time"], "close_time": m["close_time"],
                         "strike_type": m.get("strike_type"), "floor": m.get("floor_strike"),
                         "cap": m.get("cap_strike"), "result": m.get("result"),
                         "open_mid": _first_quote(bids, asks)})
    out = pd.DataFrame(rows)
    out.to_csv(QUOTES, index=False)
    return out


def highs_listing() -> pd.DataFrame:
    q = pd.read_csv(QUOTES) if QUOTES.exists() else _pull_high_quotes()

    def day(ev):
        g = re.search(r"-(\d{2})([A-Z]{3})(\d{2})$", ev)
        return pd.Timestamp(2000 + int(g.group(1)), MON[g.group(2)], int(g.group(3)))

    q["day"] = q.event.map(day)
    lo, hi = q.day.min(), q.day.max()
    rows = []
    for series, sid in HIGH_SERIES.items():
        clim = _acis_maxt(sid, "1991-01-01", "2020-12-31")
        actual = _acis_maxt(sid, lo.strftime("%Y-%m-%d"), hi.strftime("%Y-%m-%d"))
        doy = clim.index.day_of_year
        for ev, g in q[q.series == series].groupby("event"):
            g = g.dropna(subset=["open_mid"])
            if len(g) < 3:
                continue
            v = np.where(g.strike_type == "less", g.cap - 1.5,
                         np.where(g.strike_type == "greater", g.floor + 1.5, (g.floor + g.cap) / 2))
            p = g.open_mid.to_numpy() / g.open_mid.sum()
            mu = float(p @ v)
            var = float(p @ (v - mu) ** 2) + 4 / 12          # plus the spread inside a 2 F bracket
            d = g.day.iloc[0]
            near = clim[(abs(doy - d.day_of_year) <= 7) | (abs(doy - d.day_of_year) >= 358)]
            rows.append({"series": series, "day": d.date(), "implied_mean_f": mu, "implied_var": var,
                         "actual_f": actual.get(d, np.nan), "clim_mean_f": float(near.mean()),
                         "clim_var": float(near.var()), "sum_open_mids": float(g.open_mid.sum()),
                         "lead_hours": (pd.to_datetime(g.close_time.iloc[0]) - pd.to_datetime(g.open_time.iloc[0]))
                         .total_seconds() / 3600})
    return pd.DataFrame(rows).dropna(subset=["actual_f"])


def pooling(radius_mi: float = 75, reps: int = 30, seed: int = 473) -> pd.DataFrame:
    ring = pd.read_csv(PROCESSED / "prf_ring100_grids.csv")
    covered = hb.covered_grids()
    rng = np.random.default_rng(seed)
    rows, seen = [], set()
    for f in hb.load_farm_requests():
        site, req = f["site"], f["request"]
        if site in seen:
            continue
        seen.add(site)
        probs = {}
        for g in ring[(ring.site == site) & (ring.distance_to_station_mi <= radius_mi)].grid_id:
            if int(g) in covered:
                probs[int(g)] = hb.build_problem(replace(req, grid_id=int(g), protection=1.0))
        first = next(iter(probs.values()))
        years, X = first.years, first.X
        Y = np.column_stack([p.target for p in probs.values()])
        ok = np.isfinite(Y).all(axis=1) & np.isfinite(X).all(axis=1)
        tr = ok & (years >= TRAIN[0]) & (years <= TRAIN[1])
        te = ok & (years >= TEST[0]) & (years <= TEST[1])
        tranches = op.model_tranches(X[tr].mean(axis=0))
        for n in sorted({1, 3, 10, 30, len(probs)}):
            hes = []
            for _ in range(reps if n < len(probs) else 1):
                y = Y[:, rng.choice(len(probs), size=n, replace=False)].mean(axis=1) * 1000.0
                w = op.solve_penalized(X[tr], y[tr], tranches, scale=1000.0).leg_contracts
                hes.append(op.hedge_effectiveness(y[te], X[te] @ w))
            rows.append({"site": site, "grids_in_radius": len(probs), "pool_size": n,
                         "he_median": float(np.median(hes)), "he_p25": float(np.percentile(hes, 25)),
                         "he_p75": float(np.percentile(hes, 75))})
    return pd.DataFrame(rows)


def main() -> int:
    rain = rain_listing()
    rain.to_csv(PROCESSED / "insurability_pilot_rain.csv", index=False)
    v = rain.clim_p * (1 - rain.clim_p)
    print(f"Monthly rain: {len(rain)} markets; H(price) {(rain.open_mid * (1 - rain.open_mid)).sum() / v.sum():.2f}, "
          f"H(outcome) {((rain.open_mid - rain.outcome) ** 2).sum() / v.sum():.2f}, Brier skill of opening price "
          f"{1 - ((rain.open_mid - rain.outcome) ** 2).mean() / ((rain.clim_p - rain.outcome) ** 2).mean():.2f}")
    highs = highs_listing()
    highs.to_csv(PROCESSED / "insurability_pilot_highs.csv", index=False)
    for name, g in list(highs.groupby("series")) + [("all", highs)]:
        err = (g.actual_f - g.implied_mean_f) ** 2
        print(f"Daily high {name}: {len(g)} days; implied sd {np.sqrt(g.implied_var.mean()):.1f} F, "
              f"miss RMSE {np.sqrt(err.mean()):.1f} F, climatology sd {np.sqrt(g.clim_var.mean()):.1f} F; "
              f"H(price) {g.implied_var.mean() / g.clim_var.mean():.2f}, H(outcome) {err.mean() / g.clim_var.mean():.2f}")
    pool = pooling()
    pool.to_csv(PROCESSED / "insurability_pilot_pool.csv", index=False)
    print(pool.pivot(index="site", columns="pool_size", values="he_median").round(2).to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
