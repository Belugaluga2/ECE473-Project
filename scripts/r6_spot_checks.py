"""R6 spot checks: how USDA PRF and Kalshi each decide how much it rained.

Run from the repo root:  python scripts/r6_spot_checks.py

What it does (all downloads cached under data/raw/r6/, so reruns are fast):
  1. Kalshi monthly-rain markets for DFW and DEN: rules text, strikes, results, expiration_value.
  2. NWS station totals for the same months from five archives: the Daily Climate Report (CLI,
     raw text via the Iowa Environmental Mesonet AFOS archive), the monthly Climate Report (CLM),
     the preliminary F-6 (CF6), ACIS, and GHCN-Daily (NCEI access API); plus The Weather
     Company's Kalshi portal ("TWC Report (Daily)").
  3. Checks every settled Kalshi strike against the unrounded NWS CLI month total.
  4. Grid values for the same months at the PRF grid containing each station: NCEI's 0.25-degree
     USDA files (the post-2026 PRF source) and CPC Unified (the pre-2027 PRF source).
  5. PRF Decision Support Tool (DST) API: confirms it now serves NCEI-based history from 1951,
     confirms the "normal" is the 1951-2025 mean, and reproduces DST totals from NCEI files.
  6. CPC-based (RMA 2026 crop-year bulk file) vs NCEI-based (DST) index for the study grids.
  7. Which CPC version (RT or UPDATED) reproduces RMA's CPC-era index ("implied normal" test).
  8. CPC gauge counts over time (sum of the per-box gauge-count field), saved as a figure.

Outputs: CSV tables in data/raw/r6/out/, figures docs/figures/r6_*.png, and markdown tables
printed to stdout (pasted into docs/research/06_settlement_and_data_sources.md).

Grid convention found here (useful to other modules): the RMA PRF grid ID equals the 1-based
index of the CPC 0.25-degree CONUS array, grid_id = 300*j + i + 1, where
i = floor((lon_east - 230.0)/0.25) and j = floor((lat - 20.0)/0.25); box center is
(20.125 + 0.25*j, 230.125 + 0.25*i). Verified against RMA's PRF_GRID map service for 3 points.
"""
from __future__ import annotations

import calendar
import datetime as dt
import gzip
import io
import json
import math
import re
import struct
import time
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from agri_hedge.config import FIGURES, KALSHI_BASE_URL, RAW
from agri_hedge.locations import ALL_SITES

R6 = RAW / "r6"
OUT = R6 / "out"
UA = {"User-Agent": "ECE473-agri-hedge-research (r6_spot_checks.py)"}

CPC_BASE = "https://ftp.cpc.ncep.noaa.gov/precip/CPC_UNI_PRCP/GAUGE_CONUS"
NCEI_USDA = "https://www.ncei.noaa.gov/pub/data/cirs/usda"
PRF_API = "https://public-rma.fpac.usda.gov/apps/PrfWebApi/PrfExternalIndexes/GetIndexValues"
RMA_BULK_2026CY = ("https://pubfs-rma.fpac.usda.gov/pub/Miscellaneous_Files/VI_RI_Data/"
                   "Rainfall_Index_HistoricData2026CY.zip")
IEM = "https://mesonet.agron.iastate.edu"
TWC_PRIMARY = "https://weather.com/kalshi/api/climate/primary"
MM_PER_IN = 25.4

# Spot-check design: two study stations with Kalshi history, four recent months that span the
# Kalshi rule change from "NWS Climatological Report (Daily)" to "TWC Report (Daily)".
SPOT_SITES = ["DFW", "DEN"]
SPOT_MONTHS = [(2026, 6), (2026, 7), (2026, 8), (2026, 9)]
INTERVAL_CODES = {625 + k: (k + 1, k + 2) for k in range(11)}  # 625 = Jan-Feb ... 635 = Nov-Dec
STUDY_GRIDS_CACHE: list = []  # grids whose RMA bulk subset is cached (set in main)


# ----------------------------------------------------------------------------------------------
# Generic cached HTTP helpers
# ----------------------------------------------------------------------------------------------
def http_get(url, params=None, headers=None, tries=5, sleep=0.25, timeout=90):
    """GET with polite pacing and exponential backoff on 429/5xx. Returns a Response."""
    for k in range(tries):
        try:
            r = requests.get(url, params=params, headers={**UA, **(headers or {})}, timeout=timeout)
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(2 ** k)
                continue
            time.sleep(sleep)
            return r
        except requests.RequestException:
            time.sleep(2 ** k)
    raise RuntimeError(f"GET failed after {tries} tries: {url} {params}")


def cached_json(url, path: Path, params=None, refresh=False):
    """Fetch JSON once and cache it at `path`."""
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))
    r = http_get(url, params=params)
    r.raise_for_status()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(r.text, encoding="utf-8")
    return r.json()


def cached_bytes(url, path: Path):
    """Fetch a binary/text file once and cache it at `path`. Returns bytes or None on 404."""
    if path.exists():
        return path.read_bytes()
    r = http_get(url)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(r.content)
    return r.content


# ----------------------------------------------------------------------------------------------
# Grid helpers (CPC / PRF / NCEI-USDA share the same 0.25-degree boxes)
# ----------------------------------------------------------------------------------------------
def prf_grid(lat, lon):
    """Return dict with CPC array indices, box center, and RMA PRF grid ID for a point."""
    lon_e = lon % 360.0
    i = int(math.floor((lon_e - 230.0) / 0.25))
    j = int(math.floor((lat - 20.0) / 0.25))
    return {"i": i, "j": j, "cell": 300 * j + i, "grid_id": 300 * j + i + 1,
            "lat_c": round(20.125 + 0.25 * j, 3), "lon_c": round(230.125 + 0.25 * i - 360.0, 3)}


def site_grids(site):
    s = ALL_SITES[site]
    return prf_grid(s["station_lat"], s["station_lon"]), prf_grid(s["farm_lat"], s["farm_lon"])


# ----------------------------------------------------------------------------------------------
# CPC Unified gauge analysis (pre-2027 PRF source)
# ----------------------------------------------------------------------------------------------
def cpc_url(day: dt.date, version: str) -> str:
    stamp = day.strftime("%Y%m%d")
    stem = f"PRCP_CU_GAUGE_V1.0CONUS_0.25deg.lnx.{stamp}"
    if version == "V1.0":
        return f"{CPC_BASE}/V1.0/{day.year}/{stem}.gz"
    if version == "RT":
        suffix = ".RT.gz" if day.year <= 2008 else ".RT"
        return f"{CPC_BASE}/RT/{day.year}/{stem}{suffix}"
    if version == "UPDATED":
        return f"{CPC_BASE}/UPDATED/{day.year}/{stem}.UPDATED"
    raise ValueError(version)


_POINT_CACHE_PATH = R6 / "cpc_point_cache.json"
_point_cache = None


def cpc_point_mm(day: dt.date, cell: int, version: str):
    """Daily CPC precipitation (mm) at one 0.25-degree box using a 4-byte HTTP range request.

    The daily file holds two 300x120 little-endian float32 fields: precipitation in 0.1 mm and
    gauge count. Returns None if the file does not exist, NaN if the box is missing (-999).
    Only works for uncompressed files (RT 2009+, UPDATED).
    """
    global _point_cache
    if _point_cache is None:
        _point_cache = json.loads(_POINT_CACHE_PATH.read_text()) if _POINT_CACHE_PATH.exists() else {}
    key = f"{version}|{day.isoformat()}|{cell}"
    if key not in _point_cache:
        off = 4 * cell
        r = http_get(cpc_url(day, version), headers={"Range": f"bytes={off}-{off + 3}"}, sleep=0.05)
        if r.status_code == 404:
            _point_cache[key] = None
        else:
            if r.status_code != 206 or len(r.content) != 4:
                raise RuntimeError(f"range request failed {r.status_code} {cpc_url(day, version)}")
            v = struct.unpack("<f", r.content)[0]
            _point_cache[key] = None if v < -998 else v / 10.0
            if v < -998:
                _point_cache[key] = float("nan")
    v = _point_cache[key]
    return v


def save_point_cache():
    if _point_cache is not None:
        _POINT_CACHE_PATH.write_text(json.dumps(_point_cache))


def cpc_full_day(day: dt.date, version: str):
    """Full CPC field for one day -> (precip_mm[120,300], nstn[120,300]) or None if absent."""
    url = cpc_url(day, version)
    raw = cached_bytes(url, R6 / "cpc_full" / version / Path(url).name)
    if raw is None:
        return None
    if url.endswith(".gz"):
        raw = gzip.decompress(raw)
    a = np.frombuffer(raw, dtype="<f4")
    if a.size != 2 * 300 * 120:
        raise RuntimeError(f"unexpected size {a.size} for {url}")
    a = a.reshape(2, 120, 300).astype(float)
    a[a < -998] = np.nan
    return a[0] / 10.0, a[1]


def cpc_sum_mm(start: dt.date, end: dt.date, cell: int, version: str):
    """Sum of CPC daily files dated start..end inclusive (each file = 12Z day-1 to 12Z day)."""
    tot, n = 0.0, 0
    d = start
    while d <= end:
        v = cpc_point_mm(d, cell, version)
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return None
        tot += v
        n += 1
        d += dt.timedelta(days=1)
    return tot


# ----------------------------------------------------------------------------------------------
# NCEI USDA 0.25-degree files (post-2026 PRF source, nClimGrid-Monthly re-gridded)
# ----------------------------------------------------------------------------------------------
def ncei_usda_month(year, month):
    """Return (DataFrame lat/lon/precipitation mm, status 'final'|'initial') for a month."""
    stamp = f"{year}{month:02d}"
    for status in ("final", "initial"):
        url = f"{NCEI_USDA}/monthly/{status}/{stamp}.usda.csv"
        raw = cached_bytes(url, R6 / "ncei_usda" / status / f"{stamp}.usda.csv")
        if raw is not None and raw[:8] == b"latitude":
            df = pd.read_csv(io.BytesIO(raw))
            df["key"] = list(zip(df["latitude"].round(3), df["longitude"].round(3)))
            return df.set_index("key"), status
    return None, None


def ncei_usda_point_mm(year, month, g):
    df, status = ncei_usda_month(year, month)
    if df is None:
        return None, None
    v = df["precipitation"].get((g["lat_c"], g["lon_c"]))
    return (None if v is None else float(v)), status


# ----------------------------------------------------------------------------------------------
# Kalshi
# ----------------------------------------------------------------------------------------------
def kalshi_markets(series):
    """All markets (live + historical) for a series, deduplicated by ticker."""
    rows = {}
    ev = cached_json(f"{KALSHI_BASE_URL}/events", R6 / "kalshi" / f"events_{series}.json",
                     params={"series_ticker": series, "limit": 200}, refresh=True)
    for e in ev.get("events", []):
        et = e["event_ticker"]
        d = cached_json(f"{KALSHI_BASE_URL}/markets", R6 / "kalshi" / f"markets_{et}.json",
                        params={"event_ticker": et, "limit": 200})
        for m in d.get("markets", []):
            rows[m["ticker"]] = m
    cur, page = "", 0
    while True:
        params = {"series_ticker": series, "limit": 1000}
        if cur:
            params["cursor"] = cur
        d = cached_json(f"{KALSHI_BASE_URL}/historical/markets",
                        R6 / "kalshi" / f"hist_{series}_p{page}.json", params=params)
        for m in d.get("markets", []):
            rows.setdefault(m["ticker"], m)
        cur, page = d.get("cursor") or "", page + 1
        if not cur:
            break
    return pd.DataFrame(rows.values())


def rules_regime(text: str) -> str:
    t = text or ""
    if "TWC Report" in t:
        return "TWC Report (Daily)"
    if "Climate Data Online" in t:
        return "NOAA CDO daily sum (fallback CLM, then CLI)"
    if "NWS Climatological Report (Daily)" in t:
        return "NWS Climatological Report (Daily)"
    return "other"


def kalshi_yes(total_in, strike_type, floor, cap):
    """Payout criterion evaluated on a number (trace already converted to 0)."""
    if total_in is None:
        return None
    if strike_type == "greater":
        return total_in > floor
    if strike_type == "less":
        return total_in < cap
    if strike_type == "between":
        return floor <= total_in < cap
    if strike_type in ("greater_or_equal",):
        return total_in >= floor
    return None


# ----------------------------------------------------------------------------------------------
# NWS station products via Iowa Environmental Mesonet (IEM) AFOS archive
# ----------------------------------------------------------------------------------------------
def afos_products(pil, day: dt.date):
    """List of (entered_utc, product_id) for an AFOS PIL on a UTC date."""
    d = cached_json(f"{IEM}/api/1/nws/afos/list.json", R6 / "iem" / "afos_list" / f"{pil}_{day}.json",
                    params={"pil": pil, "date": day.isoformat()})
    return [(x["entered"], x["product_id"]) for x in d.get("data", [])]


def afos_text(product_id):
    raw = cached_bytes(f"{IEM}/api/1/nwstext/{product_id}", R6 / "iem" / "text" / f"{product_id}.txt")
    return raw.decode("utf-8", errors="replace") if raw else ""


def _num(tok):
    """Precip token -> (float inches with T as 0.0, flag) ; MM -> (None, 'M')."""
    tok = tok.strip()
    if tok == "T":
        return 0.0, "T"
    if tok in ("MM", "M"):
        return None, "M"
    try:
        return float(tok), ""
    except ValueError:
        return None, "?"


def parse_cli(text):
    """Parse a CLI product: summary date, intermediate flag, month-to-date precip."""
    m = re.search(r"CLIMATE SUMMARY FOR ([A-Z]+) (\d{1,2}) (\d{4})", text)
    if not m:
        return None
    summ = dt.datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%B %d %Y").date()
    valid = re.search(r"VALID (?:TODAY )?AS OF\s+(\d{4})\s*(AM|PM)?\s*LOCAL TIME", text)
    block = text.split("PRECIPITATION (IN)", 1)
    mtd = flag = None
    if len(block) == 2:
        mm = re.search(r"MONTH TO DATE\s+(\S+)", block[1])
        if mm:
            mtd, flag = _num(mm.group(1))
    issued = re.search(r"\n(\d{3,4} [AP]M [A-Z]{3} [A-Z]{3} [A-Z]{3} \d{2} \d{4})", text)
    return {"summary_date": summ, "valid_as_of": valid.group(1) if valid else "",
            "intermediate": bool(valid), "mtd_in": mtd, "mtd_flag": flag,
            "issued_local": issued.group(1) if issued else ""}


def cli_month_reports(code3, year, month):
    """All CLI products whose summary date is the last day of the month, in issue order."""
    last = dt.date(year, month, calendar.monthrange(year, month)[1])
    out = []
    for k in range(0, 5):
        for entered, pid in afos_products(f"CLI{code3}", last + dt.timedelta(days=k)):
            p = parse_cli(afos_text(pid))
            if p and p["summary_date"] == last:
                out.append({"entered_utc": entered, "product_id": pid, **p})
    return sorted(out, key=lambda r: r["entered_utc"])


def clm_total(code3, year, month):
    """First CLM for the month: (TOTALS precip inches, flag, product_id)."""
    first = dt.date(year, month, calendar.monthrange(year, month)[1]) + dt.timedelta(days=1)
    target = calendar.month_name[month].upper()
    for k in range(0, 6):
        for entered, pid in sorted(afos_products(f"CLM{code3}", first + dt.timedelta(days=k))):
            t = afos_text(pid)
            if re.search(rf"FOR THE MONTH OF {target} {year}", t):
                sec = t.split("PRECIPITATION (INCHES)", 1)
                mm = re.search(r"TOTALS\s+(\S+)", sec[1]) if len(sec) == 2 else None
                if mm:
                    v, f = _num(mm.group(1))
                    return v, f, pid
    return None, None, None


def cf6_total(code3, year, month):
    """First CF6 issued after month end that covers the month: (TOTAL FOR MONTH, flag, pid)."""
    first = dt.date(year, month, calendar.monthrange(year, month)[1]) + dt.timedelta(days=1)
    target = calendar.month_name[month].upper()
    for k in range(0, 5):
        for entered, pid in sorted(afos_products(f"CF6{code3}", first + dt.timedelta(days=k))):
            t = afos_text(pid)
            if re.search(rf"MONTH:\s+{target}\s", t) and re.search(rf"YEAR:\s+{year}", t):
                mm = re.search(r"TOTAL FOR MONTH:\s+(\S+)", t)
                if mm:
                    v, f = _num(mm.group(1))
                    return v, f, pid
    return None, None, None


# ----------------------------------------------------------------------------------------------
# ACIS, GHCN-Daily, TWC
# ----------------------------------------------------------------------------------------------
def acis_month(ghcn, year, month):
    ym = f"{year}-{month:02d}"
    body = {"sid": ghcn, "sdate": ym, "edate": ym,
            "elems": [{"name": "pcpn", "interval": "mly", "duration": "mly",
                       "reduce": {"reduce": "sum", "add": "mcnt"}}]}
    path = R6 / "acis" / f"{ghcn}_{ym}.json"
    if not path.exists():
        r = requests.post("https://data.rcc-acis.org/StnData", json=body, headers=UA, timeout=60)
        r.raise_for_status()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(r.text)
        time.sleep(0.25)
    d = json.loads(path.read_text())
    val, mcnt = d["data"][0][1]
    v, f = _num(val)
    return v, f, int(mcnt)


def ghcnd_month(ghcn, year, month):
    """Sum of GHCN-Daily PRCP (inches) from NCEI's access service; returns (sum, ndays, ntrace)."""
    last = calendar.monthrange(year, month)[1]
    params = {"dataset": "daily-summaries", "stations": ghcn, "dataTypes": "PRCP",
              "startDate": f"{year}-{month:02d}-01", "endDate": f"{year}-{month:02d}-{last:02d}",
              "units": "standard", "format": "json", "includeAttributes": "true"}
    d = cached_json("https://www.ncei.noaa.gov/access/services/data/v1",
                    R6 / "ghcnd" / f"{ghcn}_{year}{month:02d}.json", params=params)
    vals = [float(x["PRCP"]) for x in d if x.get("PRCP") not in (None, "")]
    ntrace = sum(1 for x in d if (x.get("PRCP_ATTRIBUTES") or "").startswith("T"))
    return round(sum(vals), 2), len(vals), ntrace


def twc_month(icao, year, month):
    """Sum of The Weather Company's Kalshi-portal daily precipitation (trace = 0)."""
    tot, ndays, ntrace, missing = 0.0, 0, 0, 0
    for day in range(1, calendar.monthrange(year, month)[1] + 1):
        date = f"{year}-{month:02d}-{day:02d}"
        d = cached_json(TWC_PRIMARY, R6 / "twc" / f"primary_{date}.json", params={"date": date})
        row = next((r for r in d.get("results", []) if r["station"]["icao"] == icao), None)
        p = (row or {}).get("data") or {}
        val = p.get("precipitation")
        if val is None:
            missing += 1
        elif val == "T":
            ntrace += 1
            ndays += 1
        else:
            tot += float(val)
            ndays += 1
    return round(tot, 2), ndays, ntrace, missing


# ----------------------------------------------------------------------------------------------
# PRF Decision Support Tool API and RMA bulk index file
# ----------------------------------------------------------------------------------------------
def prf_dst(grid_id):
    d = cached_json(PRF_API, R6 / "prf_api" / f"grid{grid_id}_1948_2026.json",
                    params={"intervalType": "BiMonthly", "sampleYearMinimum": 1948,
                            "sampleYearMaximum": 2026, "gridId": grid_id})
    rows = []
    for yr in d["HistoricalIndexRows"]:
        for c in yr["HistoricalIndexDataColumns"]:
            if c["PercentOfNormal"] is None:
                continue
            rows.append({"grid_id": grid_id, "year": yr["Year"], "code": int(c["IntervalCode"]),
                         "index": c["PercentOfNormal"], "total_mm": c["IntervalMeasurement"],
                         "normal_mm": c["AverageIntervalMeasurement"]})
    return pd.DataFrame(rows)


def rma_cpc_index(grid_ids):
    """CPC-based historical indices (1948-2024) from RMA's 2026 crop-year bulk file."""
    ids = sorted(int(g) for g in grid_ids)
    subset = R6 / "rma_bulk" / f"cpc_index_2026CY_{'_'.join(map(str, ids))}.csv"
    if subset.exists():
        return pd.read_csv(subset)
    zpath = R6 / "rma_bulk" / "Rainfall_Index_HistoricData2026CY.zip"
    cached_bytes(RMA_BULK_2026CY, zpath)
    z = zipfile.ZipFile(zpath)
    name = z.namelist()[0]
    keep, want = [], {str(g) for g in ids}
    with z.open(name) as f:
        # grid_id is read as text: the file mixes numeric IDs with a few non-numeric ones.
        for chunk in pd.read_csv(f, sep="|", chunksize=2_000_000, dtype={"grid_id": str},
                                 usecols=["grid_id", "Year", "PracticeCode", "ActualIndex"]):
            keep.append(chunk[chunk["grid_id"].str.strip().isin(want)])
    df = pd.concat(keep)
    df["grid_id"] = df["grid_id"].str.strip().astype(int)
    df = df.drop_duplicates(["grid_id", "Year", "PracticeCode"])
    df = df.rename(columns={"Year": "year", "PracticeCode": "code", "ActualIndex": "cpc_index"})
    df.to_csv(subset, index=False)
    return df


# ----------------------------------------------------------------------------------------------
# Analyses
# ----------------------------------------------------------------------------------------------
def md(df: pd.DataFrame) -> str:
    """Markdown table without the optional tabulate dependency."""
    cols = list(df.columns)
    lines = ["| " + " | ".join(map(str, cols)) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join("" if pd.isna(v) else str(v) for v in r.values) + " |")
    return "\n".join(lines)


def spot_station_table():
    """One row per site-month: Kalshi value vs every station archive vs the two grids."""
    rows, strikes = [], []
    for site in SPOT_SITES:
        s = ALL_SITES[site]
        code3 = s["cli_code"][3:]
        mk = kalshi_markets(s["kalshi_series"])
        g_st, _ = site_grids(site)
        for (y, m) in SPOT_MONTHS:
            ev = f"{s['kalshi_series']}-{str(y)[2:]}{calendar.month_abbr[m].upper()}"
            em = mk[mk["event_ticker"] == ev]
            exp_val = em["expiration_value"].dropna().astype(str).unique().tolist()
            cli = cli_month_reports(code3, y, m)
            first = cli[0] if cli else {}
            first_final = next((c for c in cli if not c["intermediate"]), {})
            last = cli[-1] if cli else {}
            clm_v, clm_f, _ = clm_total(code3, y, m)
            cf6_v, cf6_f, _ = cf6_total(code3, y, m)
            acis_v, acis_f, acis_miss = acis_month(s["ghcn"], y, m)
            gh_v, gh_n, gh_t = ghcnd_month(s["ghcn"], y, m)
            twc_v, twc_n, twc_t, twc_miss = twc_month(s["icao"], y, m)
            nc_mm, nc_status = ncei_usda_point_mm(y, m, g_st)
            d0, d1 = dt.date(y, m, 1), dt.date(y, m, calendar.monthrange(y, m)[1])
            cpc_upd = cpc_sum_mm(d0, d1, g_st["cell"], "UPDATED")
            cpc_rt = cpc_sum_mm(d0, d1, g_st["cell"], "RT")
            rows.append({
                "site": site, "month": f"{y}-{m:02d}",
                "kalshi_rules": rules_regime(em["rules_secondary"].iloc[0]) if len(em) else "",
                "kalshi_expiration_value": ";".join(exp_val),
                "kalshi_settled_utc": (em["settlement_ts"].dropna().min() or "")[:16] if len(em) else "",
                "cli_n_reports_for_last_day": len(cli),
                "cli_first_mtd_in": first.get("mtd_in"),
                "cli_first_issued": first.get("issued_local", ""),
                "cli_first_final_mtd_in": first_final.get("mtd_in"),
                "cli_first_final_issued": first_final.get("issued_local", ""),
                "cli_last_mtd_in": last.get("mtd_in"),
                "clm_total_in": clm_v, "cf6_total_in": cf6_v,
                "acis_in": acis_v, "acis_flag": acis_f, "acis_missing_days": acis_miss,
                "ghcnd_in": gh_v, "ghcnd_days": gh_n, "ghcnd_trace_days": gh_t,
                "twc_sum_in": twc_v, "twc_days": twc_n, "twc_missing_days": twc_miss,
                "grid_id": g_st["grid_id"],
                "ncei_grid_in": None if nc_mm is None else round(nc_mm / MM_PER_IN, 2),
                "ncei_status": nc_status,
                "cpc_updated_grid_in": None if cpc_upd is None else round(cpc_upd / MM_PER_IN, 2),
                "cpc_rt_grid_in": None if cpc_rt is None else round(cpc_rt / MM_PER_IN, 2),
            })
            truth = first_final.get("mtd_in")
            for _, r in em.iterrows():
                floor = r.get("floor_strike")
                cap = r.get("cap_strike")
                exp = kalshi_yes(truth, r["strike_type"], floor, cap)
                strikes.append({"site": site, "month": f"{y}-{m:02d}", "ticker": r["ticker"],
                                "strike_type": r["strike_type"], "floor": floor, "cap": cap,
                                "kalshi_result": r.get("result"),
                                "result_implied_by_cli": None if exp is None else ("yes" if exp else "no")})
    save_point_cache()
    return pd.DataFrame(rows), pd.DataFrame(strikes)


def kalshi_vs_cli_all_months():
    """For every settled DFW/DEN event: Kalshi expiration_value vs IEM-parsed CLI month total."""
    rows = []
    for site in SPOT_SITES:
        s = ALL_SITES[site]
        mk = kalshi_markets(s["kalshi_series"])
        cli = []
        for yr in (2025, 2026):
            d = cached_json(f"{IEM}/json/cli.py", R6 / "iem" / f"cli_{s['icao']}_{yr}.json",
                            params={"station": s["icao"], "year": yr}, refresh=(yr == 2026))
            cli += d["results"]
        by = {r["valid"]: r for r in cli}
        for ev, em in mk.groupby("event_ticker"):
            mon = dt.datetime.strptime(ev.split("-")[1], "%y%b")
            last = dt.date(mon.year, mon.month, calendar.monthrange(mon.year, mon.month)[1])
            if last >= dt.date.today():
                continue
            r = by.get(last.isoformat(), {})
            ev_res = em[em["result"].isin(["yes", "no"])]
            cli_val, _ = _num(str(r.get("precip_month"))) if r else (None, None)
            n_bad = 0
            for _, mrow in ev_res.iterrows():
                exp = kalshi_yes(cli_val, mrow["strike_type"], mrow.get("floor_strike"), mrow.get("cap_strike"))
                if exp is not None and ("yes" if exp else "no") != mrow["result"]:
                    n_bad += 1
            settled = em["settlement_ts"].dropna().min() or ""
            # Climate month ends at local-standard midnight: 06Z (Central) or 07Z (Mountain).
            utc_off = 7 if site == "DEN" else 6
            month_end = dt.datetime(last.year, last.month, last.day) + dt.timedelta(days=1, hours=utc_off)
            lag_h = (round((dt.datetime.fromisoformat(settled[:19]) - month_end).total_seconds() / 3600, 1)
                     if settled else None)
            rows.append({"site": site, "event": ev,
                         "rules": rules_regime(em["rules_secondary"].iloc[0]),
                         "kalshi_expiration_value": ";".join(em["expiration_value"].dropna().astype(str).unique()),
                         "cli_month_total_in": r.get("precip_month"),
                         "n_strikes_settled": len(ev_res),
                         "strikes_inconsistent_with_cli": n_bad,
                         "settled_utc": settled[:16],
                         "hours_after_climate_month_end": lag_h})
    return pd.DataFrame(rows).sort_values(["site", "event"])


def dst_checks(grid_ids):
    """Verify the DST normal and reproduce DST totals from NCEI USDA monthly files."""
    out = []
    for gid in grid_ids:
        d = prf_dst(gid)
        for code, sub in d.groupby("code"):
            hist = sub[sub["year"] <= 2025]
            out.append({"grid_id": gid, "interval_code": code, "first_year": int(sub["year"].min()),
                        "n_years_1951_2025": int(len(hist)),
                        "mean_total_1951_2025_mm": round(hist["total_mm"].mean(), 4),
                        "dst_normal_mm_for_1951_2025_rows": round(hist["normal_mm"].iloc[0], 4),
                        "mean_total_1951_2024_mm": round(sub[sub["year"] <= 2024]["total_mm"].mean(), 4),
                        "dst_normal_mm_for_2026_row": round(sub[sub["year"] == 2026]["normal_mm"].iloc[0], 4)
                        if (sub["year"] == 2026).any() else None})
    normals = pd.DataFrame(out)
    # Reproduce a few DST interval totals from NCEI files (Jan-Feb 1951, Jan-Feb 2025, Jul-Aug 2024).
    repro = []
    for gid in grid_ids:
        d = prf_dst(gid).set_index(["year", "code"])
        j, i = divmod(gid - 1, 300)
        g = {"lat_c": round(20.125 + 0.25 * j, 3), "lon_c": round(230.125 + 0.25 * i - 360, 3)}
        for (yr, code) in [(1951, 625), (2025, 625), (2024, 631)]:
            m1, m2 = INTERVAL_CODES[code]
            a, _ = ncei_usda_point_mm(yr, m1, g)
            b, _ = ncei_usda_point_mm(yr, m2, g)
            repro.append({"grid_id": gid, "year": yr, "interval_code": code,
                          "dst_total_mm": d.loc[(yr, code), "total_mm"],
                          "ncei_usda_sum_mm": round(a + b, 2)})
    return normals, pd.DataFrame(repro)


def cpc_vs_ncei_index(grid_ids):
    """Merge RMA's CPC-era index (2026CY file) with the DST's NCEI index for 1951-2024."""
    cpc = rma_cpc_index(grid_ids)
    ncei = pd.concat([prf_dst(g) for g in grid_ids]).rename(columns={"index": "ncei_index"})
    m = cpc.merge(ncei[["grid_id", "year", "code", "ncei_index"]], on=["grid_id", "year", "code"])
    m = m[(m["year"] >= 1951) & (m["year"] <= 2024)]
    summ = []
    for gid, sub in m.groupby("grid_id"):
        diff = (sub["ncei_index"] - sub["cpc_index"]) * 100
        pay_cpc = sub["cpc_index"] < 0.90
        pay_nc = sub["ncei_index"] < 0.90
        pf_cpc = ((0.90 - sub["cpc_index"]) / 0.90).clip(lower=0).mean()
        pf_nc = ((0.90 - sub["ncei_index"]) / 0.90).clip(lower=0).mean()
        summ.append({"grid_id": gid, "n_interval_years": len(sub),
                     "corr": round(sub["cpc_index"].corr(sub["ncei_index"]), 3),
                     "mean_abs_diff_pts": round(diff.abs().mean(), 1),
                     "p90_abs_diff_pts": round(diff.abs().quantile(0.9), 1),
                     "max_abs_diff_pts": round(diff.abs().max(), 1),
                     "trigger90_cpc_share": round(pay_cpc.mean(), 3),
                     "trigger90_ncei_share": round(pay_nc.mean(), 3),
                     "trigger90_disagree_share": round((pay_cpc != pay_nc).mean(), 3),
                     "payment_factor90_ncei_over_cpc": round(pf_nc / pf_cpc, 3)})
    return m, pd.DataFrame(summ)


def rt_vs_updated_test(grid_id, codes=(628, 631), years=range(2019, 2025)):
    """Which CPC version reproduces RMA's CPC-era index? Implied normal = total / index must be
    the same for every year if the version (and day alignment) is the one RMA used."""
    cpc = rma_cpc_index(STUDY_GRIDS_CACHE or [grid_id])
    cpc = cpc[cpc["grid_id"] == grid_id].set_index(["year", "code"])["cpc_index"]
    cell = grid_id - 1
    rows = []
    for code in codes:
        m1, m2 = INTERVAL_CODES[code]
        for yr in years:
            d0 = dt.date(yr, m1, 1)
            d1 = dt.date(yr, m2, calendar.monthrange(yr, m2)[1])
            idx = cpc.get((yr, code))
            for version in ("RT", "UPDATED"):
                for shift in (0, 1):
                    tot = cpc_sum_mm(d0 + dt.timedelta(days=shift), d1 + dt.timedelta(days=shift), cell, version)
                    rows.append({"code": code, "year": yr, "version": version, "shift_days": shift,
                                 "total_mm": tot, "rma_cpc_index": idx,
                                 "implied_normal_mm": None if (tot is None or not idx) else tot / idx})
    save_point_cache()
    df = pd.DataFrame(rows)
    summ = (df.groupby(["code", "version", "shift_days"])["implied_normal_mm"]
              .agg(lambda s: round(100 * s.std() / s.mean(), 3)).rename("implied_normal_cv_pct").reset_index())
    return df, summ


def gauge_count_history(sites=("DFW", "DEN"), days=((1, 15), (4, 15), (7, 15), (10, 15))):
    """Total CPC gauges over CONUS (sum of per-box counts) on sample days, 1948-2026."""
    rows = []
    cells = {s: site_grids(s)[0] for s in sites}
    for yr in range(1948, 2027):
        versions = ["V1.0"] if yr <= 2006 else (["RT", "UPDATED"] if yr >= 2019 else ["RT"])
        for version in versions:
            for (mo, dy) in days:
                day = dt.date(yr, mo, dy)
                if day >= dt.date.today() - dt.timedelta(days=3):
                    continue
                f = cpc_full_day(day, version)
                if f is None:
                    continue
                prcp, nstn = f
                row = {"date": day.isoformat(), "year": yr, "version": version,
                       "conus_gauges": int(np.nansum(nstn))}
                for s, g in cells.items():
                    j, i = g["j"], g["i"]
                    row[f"{s}_box_gauges"] = int(np.nan_to_num(nstn[j, i]))
                    row[f"{s}_3x3_gauges"] = int(np.nansum(nstn[j - 1:j + 2, i - 1:i + 2]))
                rows.append(row)
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------------------------
# Figures
# ----------------------------------------------------------------------------------------------
INK, INK2, GRID = "#0b0b0b", "#52514e", "#d9d8d4"
BLUE, ORANGE = "#2a78d6", "#eb6834"


def _style(ax):
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_color(INK2)
    ax.tick_params(colors=INK2)
    ax.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def fig_gauge_counts(g: pd.DataFrame, path: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ann = g.groupby(["year", "version"])["conus_gauges"].mean().reset_index()
    fig, ax = plt.subplots(figsize=(8, 4.2), dpi=150)
    styles = {"V1.0": (BLUE, "-", "o", "Retrospective V1.0 (1948-2006)"),
              "RT": (ORANGE, "-", "s", "Real-time RT (2007-present)"),
              "UPDATED": (INK2, "--", "^", "UPDATED, manual QC (2019-present)")}
    for v, (c, ls, mk, lab) in styles.items():
        sub = ann[ann["version"] == v]
        ax.plot(sub["year"], sub["conus_gauges"], color=c, linestyle=ls, marker=mk, markersize=4,
                linewidth=2, label=lab)
    ax.axvline(2006.5, color=INK2, linewidth=1, linestyle=":")
    ax.text(2006.8, ax.get_ylim()[1] * 0.97, "V1.0 -> RT switch", color=INK2, fontsize=8, va="top")
    ax.set_xlabel("Year")
    ax.set_ylabel("Gauges in CONUS analysis (count per day)")
    ax.set_title("CPC Unified gauge analysis: daily gauge count over CONUS\n"
                 "(mean of Jan 15, Apr 15, Jul 15, Oct 15 each year; sum of per-box gauge counts)",
                 color=INK, fontsize=10)
    _style(ax)
    ax.legend(frameon=False, fontsize=8, loc="lower left")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def fig_cpc_vs_ncei(m: pd.DataFrame, labels: dict, path: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    gids = list(labels)
    fig, axes = plt.subplots(1, len(gids), figsize=(4.2 * len(gids), 4.2), dpi=150, squeeze=False)
    for ax, gid in zip(axes[0], gids):
        sub = m[m["grid_id"] == gid]
        ax.scatter(sub["cpc_index"] * 100, sub["ncei_index"] * 100, s=14, color=BLUE, alpha=0.55,
                   edgecolors="none")
        lim = max(sub["cpc_index"].max(), sub["ncei_index"].max()) * 100 + 10
        ax.plot([0, lim], [0, lim], color=INK2, linewidth=1)
        ax.axvline(90, color=ORANGE, linestyle="--", linewidth=1)
        ax.axhline(90, color=ORANGE, linestyle="--", linewidth=1)
        r = sub["cpc_index"].corr(sub["ncei_index"])
        ax.set_title(f"{labels[gid]}\nr = {r:.3f}, n = {len(sub)}", color=INK, fontsize=9)
        ax.set_xlabel("CPC-based final grid index (RMA 2026 CY file)")
        ax.set_ylabel("NCEI-based grid index (PRF tool, 2027 CY)")
        ax.set_xlim(0, lim)
        ax.set_ylim(0, lim)
        _style(ax)
    fig.suptitle("Same PRF grid, two government rain datasets, 1951-2024 (all 11 intervals)\n"
                 "dashed = 90 (the trigger at 90% coverage)", color=INK, fontsize=10)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


# ----------------------------------------------------------------------------------------------
def main():
    OUT.mkdir(parents=True, exist_ok=True)
    pd.set_option("display.width", 250)

    print("\n## Grid IDs")
    gid_rows = []
    for site in SPOT_SITES:
        st, fm = site_grids(site)
        gid_rows.append({"site": site, "station_grid": st["grid_id"], "station_box_center": (st["lat_c"], st["lon_c"]),
                         "farm_grid": fm["grid_id"], "farm_box_center": (fm["lat_c"], fm["lon_c"])})
    print(md(pd.DataFrame(gid_rows)))

    print("\n## Kalshi expiration_value vs NWS CLI month total (all settled events)")
    allm = kalshi_vs_cli_all_months()
    allm.to_csv(OUT / "kalshi_vs_cli_all_months.csv", index=False)
    print(md(allm))

    print("\n## Spot months: station archives vs Kalshi vs grids")
    spot, strikes = spot_station_table()
    spot.to_csv(OUT / "spot_months.csv", index=False)
    strikes.to_csv(OUT / "spot_strikes.csv", index=False)
    print(md(spot))
    bad = strikes[strikes["kalshi_result"] != strikes["result_implied_by_cli"]]
    print(f"\nStrikes checked: {len(strikes)}; inconsistent with first final CLI: {len(bad)}")
    if len(bad):
        print(md(bad))
    print(md(strikes.groupby(["site", "month"]).agg(
        n=("ticker", "size"), strikes=("floor", lambda s: ",".join(str(int(x)) for x in s if pd.notna(x))),
        yes=("kalshi_result", lambda s: int((s == "yes").sum()))).reset_index()))

    grids = sorted({g for site in SPOT_SITES for g in (site_grids(site)[0]["grid_id"], site_grids(site)[1]["grid_id"])})
    STUDY_GRIDS_CACHE[:] = grids
    print("\n## PRF tool (DST) normal check and NCEI reproduction")
    normals, repro = dst_checks(grids)
    normals.to_csv(OUT / "dst_normals.csv", index=False)
    repro.to_csv(OUT / "dst_ncei_repro.csv", index=False)
    print(md(normals[normals["interval_code"].isin([625, 628, 631])]))
    print(md(repro))

    print("\n## CPC-era vs NCEI-era index, same grids, 1951-2024")
    merged, summ = cpc_vs_ncei_index(grids)
    merged.to_csv(OUT / "cpc_vs_ncei_index.csv", index=False)
    print(md(summ))
    labels = {}
    for site in SPOT_SITES:
        st, fm = site_grids(site)
        labels[st["grid_id"]] = f"{site} station grid {st['grid_id']}"
    fig_cpc_vs_ncei(merged, labels, FIGURES / "r6_cpc_vs_ncei_index.png")

    print("\n## Which CPC version did RMA use? (implied-normal coefficient of variation, %)")
    st_dfw = site_grids("DFW")[0]["grid_id"]
    rt, rts = rt_vs_updated_test(st_dfw)
    rt.to_csv(OUT / "cpc_rt_vs_updated_test.csv", index=False)
    print(md(rts))

    print("\n## CPC gauge counts")
    gc = gauge_count_history()
    gc.to_csv(OUT / "cpc_gauge_counts.csv", index=False)
    ann = gc.groupby(["year", "version"]).mean(numeric_only=True).round(1).reset_index()
    print(md(ann[ann["year"].isin([1948, 1960, 1970, 1980, 1990, 1995, 2000, 2004, 2005, 2006, 2007,
                                   2008, 2010, 2015, 2018, 2019, 2020, 2024, 2025, 2026])]))
    eras = {"1950-1991": (1950, 1991), "1992-2003": (1992, 2003), "2004-2006": (2004, 2006),
            "2007-2018": (2007, 2018), "2019-2026": (2019, 2026)}
    main_v = ann[ann["version"].isin(["V1.0", "RT"])]
    era_rows = []
    for lab, (y0, y1) in eras.items():
        sub = main_v[(main_v["year"] >= y0) & (main_v["year"] <= y1)]
        era_rows.append({"period": lab, **sub.drop(columns=["year", "version"]).mean().round(1).to_dict()})
    print(md(pd.DataFrame(era_rows)))
    fig_gauge_counts(gc, FIGURES / "r6_cpc_gauge_counts.png")
    save_point_cache()
    print("\nDone. Tables in", OUT)


if __name__ == "__main__":
    main()
