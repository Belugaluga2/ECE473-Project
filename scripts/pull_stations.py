"""B3: map every Kalshi monthly-rain series to its settlement station and pull station precipitation.

Run from the repo root:  python scripts/pull_stations.py [--refresh-kalshi]

Outputs
    data/processed/station_map.csv                one row per Kalshi monthly-rain series
    data/processed/station_monthly_precip.csv     calendar-month totals for every mapped station
    data/processed/station_daily_precip_study.parquet  daily values for the 8 study-site stations
    docs/figures/b3_station_record_coverage.png   record length per station (single vs threaded)

Method
    1. List Kalshi "Climate and Weather" series; keep monthly-rain ones (RAIN...M tickers).
    2. Parse the settlement station from each series' market rules_primary ("CLIDFW" -> DFW).
    3. Resolve the code with ACIS StnMeta (ICAO, FAA and NWS-id lookups; ThreadEx "<code>thr").
    4. Pull daily precipitation from ACIS StnData for the single station from its record start to
       the latest complete month. If the single-station record starts after 1948-01-01 and a
       ThreadEx record exists, months before the first full single-station month come from the
       threaded record, starting 1948-01 (the start of PRF's rainfall-index history).
    5. Cross-check the study stations against NCEI GHCN-Daily by-station files.
Raw downloads are cached under data/raw/stations/ so reruns are fast and offline-safe.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date

import numpy as np
import pandas as pd

from agri_hedge.config import FIGURES, PROCESSED
from agri_hedge.locations import ALL_SITES
from agri_hedge.stations import (RAW_STATIONS, event_month, fetch_acis_daily,
                                 fetch_ghcn_daily, is_monthly_rain_series, kalshi_get,
                                 kalshi_series_markets, latest_complete_month, month_end,
                                 monthly_totals, normalize_market, parse_settlement_location,
                                 resolve_station)

THREAD_START = "1948-01-01"
KALSHI_DIR = RAW_STATIONS / "kalshi"
META_DIR = RAW_STATIONS / "acis_meta"
DAILY_DIR = RAW_STATIONS / "acis_daily"
GHCN_DIR = RAW_STATIONS / "ghcn"

MONTHLY_COLS = ["station_key", "cli_code", "ghcn", "year", "month", "precip_in", "n_days",
                "n_missing", "n_trace", "n_accum", "n_subseq", "source"]


def load_series(refresh: bool) -> list[dict]:
    """Kalshi Climate and Weather series (cached), filtered to monthly-rain series."""
    import json
    path = KALSHI_DIR / "series_climate_and_weather.json"
    if refresh or not path.exists():
        data = kalshi_get("/series", {"category": "Climate and Weather"})
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")
    data = json.loads(path.read_text(encoding="utf-8"))
    return sorted((s for s in data["series"] if is_monthly_rain_series(s)),
                  key=lambda s: s["ticker"])


def _event_key(event_ticker: str, rules: str | None) -> tuple[int, int]:
    return event_month(event_ticker, rules) or (0, 0)


def series_locations(series: dict, markets: list[dict]) -> list[dict]:
    """Settlement stations named by a series' markets, one dict per station code.

    A series can switch stations (KXRAINCHIM named Chicago Midway through Aug 2026 and O'Hare
    from Sep 2026), so every code is kept with the range of event months that use it. A series
    with no markets (legacy RAINNYCM) falls back to the CLI product in its settlement-source URL.
    """
    by_code: dict[str, dict] = {}
    for mk in markets:
        loc = parse_settlement_location(mk.get("rules_primary"))
        if not loc["code"]:
            continue
        d = by_code.setdefault(loc["code"], {"code": loc["code"], "how": set(), "events": set(),
                                              "n_markets": 0, "n_settled": 0, "twc": set()})
        d["how"].add(loc["how"])
        d["n_markets"] += 1
        d["events"].add(_event_key(mk["event_ticker"], mk.get("rules_primary")))
        if mk.get("result") in ("yes", "no"):
            d["n_settled"] += 1
        if normalize_market(mk)["settle_source"] == "TWC":
            d["twc"].add(_event_key(mk["event_ticker"], mk.get("rules_primary")))
    if not by_code:
        for src in series.get("settlement_sources", []):
            url = src.get("url", "")
            if "issuedby=" in url:
                code = url.split("issuedby=")[-1][:3].upper()
                by_code[code] = {"code": code, "how": {"source_url"}, "events": set(),
                                 "n_markets": 0, "n_settled": 0, "twc": set()}
    out = []
    for d in by_code.values():
        ev = sorted(e for e in d["events"] if e != (0, 0))
        fmt = lambda e: f"{e[0]:04d}-{e[1]:02d}"  # noqa: E731
        out.append({"code": d["code"], "how": "+".join(sorted(d["how"])),
                    "n_markets": d["n_markets"], "n_settled": d["n_settled"],
                    "events_from": fmt(ev[0]) if ev else "", "events_to": fmt(ev[-1]) if ev else "",
                    "twc_from": fmt(min(d["twc"])) if d["twc"] else ""})
    return sorted(out, key=lambda d: d["events_from"])


def settlement_source_names(series: dict) -> str:
    return "; ".join(s.get("name", "") for s in series.get("settlement_sources", []))


def build_station_map(refresh_kalshi: bool) -> pd.DataFrame:
    """One row per (Kalshi monthly-rain series, settlement station) with identifiers and flags."""
    rows = []
    resolved: dict[str, dict] = {}
    for s in load_series(refresh_kalshi):
        tkr = s["ticker"]
        markets = kalshi_series_markets(tkr, KALSHI_DIR, refresh=refresh_kalshi)
        locs = series_locations(s, markets)
        if not locs:
            rows.append({"series_ticker": tkr, "series_title": s.get("title", ""),
                         "ambiguous": True, "notes": "no settlement station found"})
            continue
        for loc in locs:
            code = loc["code"]
            row = {"series_ticker": tkr, "series_title": s.get("title", ""),
                   "frequency": s.get("frequency", ""),
                   "settlement_sources": settlement_source_names(s),
                   "contract_terms_url": s.get("contract_terms_url", ""),
                   "location_parsed_from": loc["how"], "cli_code": f"CLI{code}",
                   "station_key": code, "n_markets": loc["n_markets"],
                   "n_settled_markets": loc["n_settled"], "events_from": loc["events_from"],
                   "events_to": loc["events_to"], "twc_rules_from": loc["twc_from"],
                   "series_n_stations": len(locs)}
            notes, ambiguous = [], False
            if code not in resolved:
                resolved[code] = resolve_station(code, META_DIR)
            st = dict(resolved[code])
            ambiguous |= bool(st.pop("ambiguous", False))
            if st.get("notes"):
                notes.append(st.pop("notes"))
            st.pop("notes", None)
            st.pop("cli_station", None)
            row.update(st)
            if len(locs) > 1:
                ambiguous = True
                notes.append("series changed settlement station: " + ", ".join(
                    f"CLI{d['code']} {d['events_from']}..{d['events_to']}" for d in locs))
            if "name" in loc["how"]:
                ambiguous = True
                notes.append("some or all rules give a place name, not a CLI code "
                             "(e.g. 'Central Park, New York City', 'Chicago Midway, IL')")
            if loc["how"] == "source_url":
                ambiguous = True
                notes.append("API lists no markets; station taken from settlement-source URL")
            if "icao" in loc["how"]:
                ambiguous = True
                notes.append(f"rules name airport K{code}, not a CLI report; settlement source is "
                             "The Weather Company only (RAINGLOBALPERIOD terms)")
            site_key = next((k for k, v in ALL_SITES.items()
                             if v["kalshi_series"] == tkr and v["cli_code"] == f"CLI{code}"), "")
            series_site = next((k for k, v in ALL_SITES.items() if v["kalshi_series"] == tkr), "")
            row["study_site"] = site_key
            if series_site and not site_key:
                notes.append(f"series is study site {series_site}, but locations.py names "
                             f"{ALL_SITES[series_site]['cli_code']}; this row is the earlier station")
            if site_key and ALL_SITES[site_key]["ghcn"] != row.get("ghcn"):
                ambiguous = True
                notes.append(f"GHCN differs from locations.py ({ALL_SITES[site_key]['ghcn']})")
            row["ambiguous"] = ambiguous
            row["notes"] = " | ".join(n for n in notes if n)
            rows.append(row)
    return pd.DataFrame(rows)


def station_monthly(row: pd.Series, end: str) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Monthly totals and spliced daily series for one station; plus threaded-overlap stats."""
    start = row["record_start"]
    single = fetch_acis_daily(start, end, uid=int(row["acis_uid"]), cache_dir=DAILY_DIR)
    single["source"] = "acis_station"
    s0 = pd.Timestamp(start)
    switch = s0 if s0.day == 1 else (s0 + pd.offsets.MonthBegin(1))
    info = {"monthly_start": "", "thr_used_until": "", "thr_overlap_months": 0,
            "thr_overlap_match_frac": np.nan}
    mon_single = monthly_totals(single[single["date"] >= switch], switch.strftime("%Y-%m-%d"),
                                end)
    mon_single["source"] = "acis_station"
    parts_m, parts_d = [mon_single], [single[single["date"] >= switch]]
    if row.get("thr_sid") and s0 > pd.Timestamp(THREAD_START):
        thr_start = max(pd.Timestamp(THREAD_START), pd.Timestamp(row["thr_start"]))
        thr = fetch_acis_daily(thr_start.strftime("%Y-%m-%d"), end, sid=row["thr_sid"],
                               cache_dir=DAILY_DIR)
        tag = "acis_threaded:" + row["thr_sid"].split()[0]
        thr["source"] = tag
        pre = thr[thr["date"] < switch]
        mon_thr = monthly_totals(pre, thr_start.strftime("%Y-%m-%d"),
                                 (switch - pd.Timedelta(days=1)).strftime("%Y-%m-%d"))
        mon_thr["source"] = tag
        parts_m.insert(0, mon_thr)
        parts_d.insert(0, pre)
        info["thr_used_until"] = (switch - pd.Timedelta(days=1)).strftime("%Y-%m")
        # Does the threaded record reproduce the single station where both exist?
        post = monthly_totals(thr[thr["date"] >= switch], switch.strftime("%Y-%m-%d"), end)
        j = post.merge(mon_single, on=["year", "month"], suffixes=("_t", "_s"))
        j = j[(j["n_missing_t"] == 0) & (j["n_missing_s"] == 0)]
        info["thr_overlap_months"] = len(j)
        if len(j):
            info["thr_overlap_match_frac"] = round(
                float(((j["precip_in_t"] - j["precip_in_s"]).abs() <= 0.005).mean()), 4)
    mon = pd.concat(parts_m, ignore_index=True)
    daily = pd.concat(parts_d, ignore_index=True)
    info["monthly_start"] = f"{int(mon['year'].iloc[0]):04d}-{int(mon['month'].iloc[0]):02d}"
    return mon, daily, info


def ghcn_crosscheck(key: str, ghcn: str, mon_acis: pd.DataFrame) -> dict:
    """Compare ACIS single-station monthly totals with GHCN-Daily monthly totals."""
    g = fetch_ghcn_daily(ghcn, GHCN_DIR)
    a = mon_acis[mon_acis["source"] == "acis_station"]
    gm = monthly_totals(g, f"{int(a['year'].min())}-{int(a['month'].iloc[0]):02d}-01",
                        f"{int(a['year'].max())}-{int(a['month'].iloc[-1]):02d}-01")
    j = gm.merge(a, on=["year", "month"], suffixes=("_g", "_a"))
    j = j[(j["n_missing_g"] == 0) & (j["n_missing_a"] == 0)]
    diff = (j["precip_in_g"] - j["precip_in_a"]).abs()
    recent = j[j["year"] >= 2015]
    return {"station_key": key, "ghcn": ghcn, "months_compared": len(j),
            "match_frac": round(float((diff <= 0.005).mean()), 4) if len(j) else np.nan,
            "within_0p05_frac": round(float((diff <= 0.05).mean()), 4) if len(j) else np.nan,
            "max_abs_diff_in": round(float(diff.max()), 2) if len(j) else np.nan,
            "months_2015plus": len(recent),
            "match_frac_2015plus": round(float(((recent["precip_in_g"] - recent["precip_in_a"])
                                                .abs() <= 0.005).mean()), 4)
            if len(recent) else np.nan}


def plot_coverage(smap: pd.DataFrame, path) -> None:
    """Horizontal bars: years covered by the single-station and threaded records."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    st = smap.drop_duplicates("station_key").dropna(subset=["record_start"]).copy()
    st["single_start"] = pd.to_datetime(st["record_start"])
    st["mstart"] = pd.to_datetime(st["monthly_start"] + "-01")
    st = st.sort_values("single_start", ascending=False).reset_index(drop=True)
    end = pd.to_datetime(st["record_end"]).max()
    fig, ax = plt.subplots(figsize=(8, 9))
    for i, r in st.iterrows():
        s = r["single_start"]
        ax.barh(i, (end - s).days / 365.25, left=s.year + s.dayofyear / 365.25, height=0.7,
                color="#2a78d6", edgecolor="none")
        if r["mstart"] < s:
            ax.barh(i, (s - r["mstart"]).days / 365.25, left=r["mstart"].year, height=0.7,
                    color="#b7d3f6", edgecolor="#1c5cab", hatch="///", linewidth=0.5)
    labels = [f"{r['station_key']}{' *' if r['study_site'] else ''}" for _, r in st.iterrows()]
    ax.set_yticks(range(len(st)), labels, fontsize=8)
    ax.axvline(1948, color="black", linestyle="--", linewidth=0.8)
    ax.text(1948.5, len(st) - 0.4, "1948: earliest month taken from a threaded record",
            fontsize=8, va="bottom")
    ax.set_xlim(1840, end.year + 2)
    ax.set_xlabel("Year")
    ax.set_title("Daily precipitation record behind each Kalshi monthly-rain station\n"
                 "solid = single station (ACIS); hatched = ACIS ThreadEx predecessor sites used"
                 " (* = study site)", fontsize=10)
    ax.grid(axis="x", color="#dddddd", linewidth=0.6)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--refresh-kalshi", action="store_true",
                    help="re-download Kalshi series/market lists instead of using the cache")
    ap.add_argument("--today", default=None, help="override today's date (YYYY-MM-DD)")
    args = ap.parse_args(argv)
    today = date.fromisoformat(args.today) if args.today else date.today()
    ly, lm = latest_complete_month(today)
    end = month_end(ly, lm)
    print(f"Latest complete month: {ly}-{lm:02d} (end {end})")

    smap = build_station_map(args.refresh_kalshi)
    print(f"{len(smap)} monthly-rain series, {smap['station_key'].nunique()} distinct stations")

    monthly_parts, daily_parts, infos, xchecks = [], [], {}, []
    stations = smap[smap["acis_uid"].notna()].drop_duplicates("station_key")
    for _, row in stations.iterrows():
        key = row["station_key"]
        mon, daily, info = station_monthly(row, end)
        infos[key] = info
        mon.insert(0, "station_key", key)
        mon.insert(1, "cli_code", row["cli_code"])
        mon.insert(2, "ghcn", row["ghcn"])
        monthly_parts.append(mon[MONTHLY_COLS])
        site = next((k for k, v in ALL_SITES.items() if v["cli_code"] == row["cli_code"]), None)
        if site:
            d = daily.copy()
            d.insert(0, "station_key", key)
            d.insert(1, "cli_code", row["cli_code"])
            d.insert(2, "ghcn", row["ghcn"])
            daily_parts.append(d)
            xchecks.append(ghcn_crosscheck(key, row["ghcn"], mon))
        print(f"  {key:4s} {row['name'][:32]:32s} monthly from {info['monthly_start']}"
              f" (thread until {info['thr_used_until'] or '-'}, overlap match "
              f"{info['thr_overlap_match_frac']})")

    for col in ("monthly_start", "thr_used_until", "thr_overlap_months",
                "thr_overlap_match_frac"):
        smap[col] = smap["station_key"].map(lambda k: infos.get(k, {}).get(col, ""))
    xc = pd.DataFrame(xchecks)
    for col in ("months_compared", "match_frac", "max_abs_diff_in"):
        smap["ghcn_xcheck_" + col] = smap["station_key"].map(
            dict(zip(xc["station_key"], xc[col])) if len(xc) else {})

    order = ["series_ticker", "series_title", "study_site", "cli_code", "station_key",
             "location_parsed_from", "name", "state", "icao", "faa", "nwsli", "ghcn", "wban",
             "coop", "acis_uid", "acis_sid", "lat", "lon", "elev_ft", "record_start",
             "record_end", "thr_sid", "thr_name", "thr_start", "thr_used_until",
             "thr_overlap_months", "thr_overlap_match_frac", "monthly_start",
             "ghcn_xcheck_months_compared", "ghcn_xcheck_match_frac",
             "ghcn_xcheck_max_abs_diff_in", "frequency", "settlement_sources",
             "contract_terms_url", "series_n_stations", "events_from", "events_to",
             "twc_rules_from", "n_markets", "n_settled_markets", "ambiguous", "notes"]
    smap = smap[[c for c in order if c in smap.columns]]
    smap.to_csv(PROCESSED / "station_map.csv", index=False)

    monthly = pd.concat(monthly_parts, ignore_index=True)
    monthly.to_csv(PROCESSED / "station_monthly_precip.csv", index=False)
    daily = pd.concat(daily_parts, ignore_index=True)
    daily = daily[["station_key", "cli_code", "ghcn", "date", "precip_in", "flag", "raw",
                   "source"]]
    daily.to_parquet(PROCESSED / "station_daily_precip_study.parquet", index=False)
    xc.to_csv(RAW_STATIONS / "ghcn_crosscheck_study.csv", index=False)
    plot_coverage(smap, FIGURES / "b3_station_record_coverage.png")

    print(f"wrote station_map.csv ({len(smap)} rows), station_monthly_precip.csv "
          f"({len(monthly)} rows), station_daily_precip_study.parquet ({len(daily)} rows)")
    print("GHCN cross-check (study stations):")
    print(xc.to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
