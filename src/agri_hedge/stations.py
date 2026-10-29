"""Settlement-station precipitation: station lookup, daily data, monthly and PRF-interval totals.

This module serves workstream B3. It answers three questions for every Kalshi monthly-rain
contract:

1. Which weather station settles it? Kalshi's ``rules_primary`` text names an NWS climate
   report ("CLIDFW" = the daily Climatological Report for Dallas/Fort Worth airport). We map
   that code to the station's identifiers (ICAO, WBAN, GHCN-Daily, ACIS uid) with the ACIS
   StnMeta web service.
2. How much did it rain there? Daily precipitation comes from ACIS StnData
   (https://data.rcc-acis.org). NCEI's GHCN-Daily by-station CSV is a second, independent copy
   used only for cross-checking.
3. What did Kalshi settle? ``infer_settled_range`` turns a settled ladder of "Above X inches"
   binary markets into the interval of monthly totals consistent with the outcomes.

ACIS daily precipitation codes (as returned without the "add" option):
    "0.25"   measured amount in inches
    "T"      trace (less than 0.005 in): counted as 0.0 and flagged "T"
    "M"      missing: NaN, flagged "M"
    "S"      "subsequent": the amount is included in a later accumulated value: NaN, flagged "S"
    "1.30A"  accumulated multi-day total ending on this day: 1.30, flagged "A"

Daily values at first-order (airport ASOS) stations cover midnight to midnight local standard
time, the same day definition the NWS daily climate report (CLI) uses.
"""
from __future__ import annotations

import calendar
import json
import re
import time
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from .config import KALSHI_BASE_URL, RAW
from .prf_intervals import INTERVAL_MONTHS, INTERVAL_NAMES

ACIS_URL = "https://data.rcc-acis.org"
GHCN_ACCESS_URL = ("https://www.ncei.noaa.gov/data/global-historical-climatology-network-daily/"
                   "access/{ghcn}.csv")
IEM_CLI_URL = "https://mesonet.agron.iastate.edu/geojson/cli.py"

RAW_STATIONS = RAW / "stations"

# ACIS station-id type codes (the number after the space in an ACIS sid such as "DFW 3").
ACIS_SID_TYPES = {"1": "wban", "2": "coop", "3": "faa", "4": "wmo", "5": "icao",
                  "6": "ghcn", "7": "nwsli", "9": "threadex"}

# Kalshi contracts that name a place instead of a CLI code. Value = the 3-letter station code.
NAMED_LOCATIONS = {"central park": "NYC", "chicago midway": "MDW", "chicago o'hare": "ORD"}

_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": "agri-hedge ECE473 research (Princeton)"})


# ---------------------------------------------------------------------------------------------
# HTTP helpers with on-disk caching
# ---------------------------------------------------------------------------------------------
def _request_json(method: str, url: str, *, params=None, payload=None, retries: int = 5,
                  timeout: int = 120) -> dict:
    """GET or POST and return parsed JSON, retrying on network errors, HTTP 429 and 5xx."""
    delay = 1.0
    for attempt in range(retries):
        try:
            if method == "POST":
                r = _SESSION.post(url, json=payload, timeout=timeout)
            else:
                r = _SESSION.get(url, params=params, timeout=timeout)
            if r.status_code == 429 or r.status_code >= 500:
                raise requests.HTTPError(f"HTTP {r.status_code}")
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError):
            if attempt == retries - 1:
                raise
            time.sleep(delay)
            delay *= 2
    raise RuntimeError("unreachable")


def _cached_json(cache_path: Path | None, fetch) -> dict:
    """Return JSON from ``cache_path`` if present, else call ``fetch()`` and save the result."""
    if cache_path is not None and cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))
    data = fetch()
    if cache_path is not None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(data), encoding="utf-8")
    return data


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_")


# ---------------------------------------------------------------------------------------------
# ACIS station metadata
# ---------------------------------------------------------------------------------------------
def acis_stn_meta(sid: str, cache_dir: Path | None = None) -> list[dict]:
    """Look up one ACIS sid (e.g. "KDFW 5", "DFW 3", "DFWthr 9") with StnMeta.

    Returns a list of station metadata dicts (empty if ACIS does not know the sid). Each dict has
    uid, name, state, sids, ll ([lon, lat]), elev (feet) and valid_daterange for precipitation.
    ACIS errors on a multi-sid query if any sid is unknown, so query one sid at a time.
    """
    payload = {"sids": sid, "meta": "name,state,sids,ll,elev,uid,valid_daterange",
               "elems": "pcpn"}
    cache = None if cache_dir is None else Path(cache_dir) / f"stnmeta_{_slug(sid)}.json"
    data = _cached_json(cache, lambda: _request_json("POST", f"{ACIS_URL}/StnMeta",
                                                     payload=payload))
    return data.get("meta", []) if isinstance(data, dict) else []


def split_acis_sids(sids: list[str]) -> dict[str, list[str]]:
    """Group an ACIS ``sids`` list by id type, e.g. {"icao": ["KDFW"], "ghcn": ["USW00003927"]}."""
    out: dict[str, list[str]] = {}
    for s in sids:
        ident, _, code = s.rpartition(" ")
        kind = ACIS_SID_TYPES.get(code, f"type{code}")
        out.setdefault(kind, [])
        if ident not in out[kind]:
            out[kind].append(ident)
    return out


def resolve_station(code: str, cache_dir: Path | None = None) -> dict:
    """Map a 3-letter NWS climate-site code (the "DFW" in "CLIDFW") to one ACIS station.

    Tries ICAO "K<code>", FAA "<code>" and NWS location id "<code>" lookups. If they return
    different ACIS stations the mapping is flagged ambiguous and the station that has a GHCN
    "USW" (first-order/ASOS) id and the most recent data is chosen, because CLI reports come from
    ASOS airport sites. Also looks up the ACIS ThreadEx record "<code>thr 9".

    Returns a flat dict ready to become one row of station_map.csv.
    """
    candidates: dict[int, dict] = {}
    found_by: dict[int, list[str]] = {}
    for sid in (f"K{code} 5", f"{code} 3", f"{code} 7"):
        for m in acis_stn_meta(sid, cache_dir):
            if "uid" not in m:
                continue
            candidates[m["uid"]] = m
            found_by.setdefault(m["uid"], []).append(sid)
    notes: list[str] = []
    if not candidates:
        return {"cli_station": code, "ambiguous": True, "notes": "no ACIS station found"}

    def score(m):
        ids = split_acis_sids(m.get("sids", []))
        has_usw = any(g.startswith("USW") for g in ids.get("ghcn", []))
        end = (m.get("valid_daterange") or [["", ""]])[0][-1] or ""
        return (has_usw, end, len(found_by[m["uid"]]))

    best = max(candidates.values(), key=score)
    ambiguous = len(candidates) > 1
    if ambiguous:
        others = [f"uid {u} {c.get('name')} (via {', '.join(found_by[u])})"
                  for u, c in candidates.items() if u != best["uid"]]
        notes.append("ACIS id lookups disagree; chose ASOS site with USW id; rejected: "
                     + "; ".join(others))
    ids = split_acis_sids(best.get("sids", []))
    ghcn = next((g for g in ids.get("ghcn", []) if g.startswith("USW")),
                (ids.get("ghcn") or [""])[0])
    vdr = (best.get("valid_daterange") or [["", ""]])[0]
    if len(ids.get("faa", [])) > 1:
        notes.append("station has several FAA ids: " + ", ".join(ids["faa"]))
    row = {
        "cli_station": code,
        "acis_uid": best["uid"],
        "acis_sid": f"{ghcn} 6" if ghcn else f"{code} 3",
        "name": best.get("name", ""),
        "state": best.get("state", ""),
        "icao": ",".join(ids.get("icao", [])),
        "faa": ",".join(ids.get("faa", [])),
        "nwsli": ",".join(ids.get("nwsli", [])),
        "ghcn": ghcn,
        "wban": ",".join(ids.get("wban", [])),
        "coop": ",".join(ids.get("coop", [])),
        "lat": best["ll"][1] if best.get("ll") else np.nan,
        "lon": best["ll"][0] if best.get("ll") else np.nan,
        "elev_ft": best.get("elev", np.nan),
        "record_start": vdr[0] if vdr else "",
        "record_end": vdr[-1] if vdr else "",
    }
    thr = [m for m in acis_stn_meta(f"{code}thr 9", cache_dir) if "uid" in m]
    if thr:
        tvdr = (thr[0].get("valid_daterange") or [["", ""]])[0]
        row.update(thr_sid=f"{code}thr 9", thr_name=thr[0].get("name", ""),
                   thr_start=tvdr[0], thr_end=tvdr[-1])
    else:
        row.update(thr_sid="", thr_name="", thr_start="", thr_end="")
    row["ambiguous"] = ambiguous
    row["notes"] = "; ".join(notes)
    return row


# ---------------------------------------------------------------------------------------------
# Daily precipitation
# ---------------------------------------------------------------------------------------------
def parse_acis_precip(raw) -> tuple[float, str]:
    """Parse one ACIS daily precipitation string into (inches, flag).

    flag is "" (measured), "T" (trace, value 0.0), "M" (missing, NaN), "S" (amount included in a
    later accumulated value, NaN) or "A" (accumulated multi-day total ending this day).
    Anything unparseable is treated as missing.
    """
    if raw is None:
        return np.nan, "M"
    if isinstance(raw, list):  # value returned with the "add" option: [value, flag, ...]
        raw = raw[0]
    s = str(raw).strip()
    if s in ("", "M"):
        return np.nan, "M"
    if s == "T":
        return 0.0, "T"
    if s == "S":
        return np.nan, "S"
    flag = ""
    if s.endswith("A"):
        flag, s = "A", s[:-1]
    if s == "T":  # "TA": trace accumulation
        return 0.0, "T"
    try:
        return float(s), flag
    except ValueError:
        return np.nan, "M"


def acis_daily_from_json(data: dict) -> pd.DataFrame:
    """Convert an ACIS StnData response (elems=pcpn) into a daily DataFrame.

    Columns: date (datetime64), raw (str), precip_in (float), flag (str).
    """
    rows = data.get("data", []) if isinstance(data, dict) else []
    recs = []
    for d, v in rows:
        val, flag = parse_acis_precip(v)
        recs.append((d, v[0] if isinstance(v, list) else v, val, flag))
    df = pd.DataFrame(recs, columns=["date", "raw", "precip_in", "flag"])
    df["date"] = pd.to_datetime(df["date"])
    return df


def fetch_acis_daily(sdate: str, edate: str, *, sid: str | None = None, uid: int | None = None,
                     cache_dir: Path | None = None) -> pd.DataFrame:
    """Fetch daily precipitation (inches) from ACIS StnData for one station and date range.

    Give either an ACIS ``sid`` (e.g. "USW00003927 6", "DENthr 9") or a numeric ``uid``.
    Dates are "YYYY-MM-DD". Responses are cached under ``cache_dir`` keyed by station and dates.
    Returns the frame from ``acis_daily_from_json``.
    """
    if (sid is None) == (uid is None):
        raise ValueError("give exactly one of sid or uid")
    payload = {"sdate": sdate, "edate": edate, "elems": [{"name": "pcpn"}],
               "meta": "name,uid,sids"}
    key = f"uid{uid}" if uid is not None else _slug(sid)
    if uid is not None:
        payload["uid"] = uid
    else:
        payload["sid"] = sid
    cache = None if cache_dir is None else Path(cache_dir) / f"stndata_{key}_{sdate}_{edate}.json"
    data = _cached_json(cache, lambda: _request_json("POST", f"{ACIS_URL}/StnData",
                                                     payload=payload))
    if isinstance(data, dict) and "error" in data:
        raise RuntimeError(f"ACIS StnData error for {key}: {data['error']}")
    return acis_daily_from_json(data)


def parse_ghcn_csv(path_or_buf) -> pd.DataFrame:
    """Parse a GHCN-Daily by-station access CSV into daily precipitation.

    PRCP is stored in tenths of millimetres; we convert to inches and round to 0.01 in, which
    recovers the original US hundredths-of-an-inch observation. PRCP_ATTRIBUTES is
    "mflag,qflag,sflag[,time]"; mflag "T" marks a trace. Rows with a non-blank quality flag are
    treated as missing (GHCN flagged them as failing a QC check).
    Columns: date, precip_in, flag ("" / "T" / "M" / "Q"), qflag.
    """
    df = pd.read_csv(path_or_buf, usecols=lambda c: c in ("DATE", "PRCP", "PRCP_ATTRIBUTES"),
                     dtype={"PRCP_ATTRIBUTES": str}, low_memory=False)
    if "PRCP" not in df.columns:
        return pd.DataFrame(columns=["date", "precip_in", "flag", "qflag"])
    df = df[df["PRCP"].notna()].copy()
    attrs = df["PRCP_ATTRIBUTES"].fillna(",,").str.split(",", expand=True)
    mflag = attrs[0].fillna("").str.strip()
    qflag = attrs[1].fillna("").str.strip() if attrs.shape[1] > 1 else ""
    precip = (pd.to_numeric(df["PRCP"], errors="coerce") / 254.0).round(2)
    flag = np.where(mflag == "T", "T", "")
    bad_q = qflag != ""
    precip = precip.where(~bad_q)
    flag = np.where(bad_q, "Q", flag)
    out = pd.DataFrame({"date": pd.to_datetime(df["DATE"]), "precip_in": precip.values,
                        "flag": flag, "qflag": np.asarray(qflag)})
    return out.reset_index(drop=True)


def fetch_ghcn_daily(ghcn_id: str, cache_dir: Path | None = None,
                     refresh: bool = False) -> pd.DataFrame:
    """Download (or read cached) NCEI GHCN-Daily by-station CSV and return daily precipitation.

    URL: https://www.ncei.noaa.gov/data/global-historical-climatology-network-daily/access/<ID>.csv
    Files are ~10 MB per airport station. Used for cross-checking ACIS, not as the primary source.
    """
    cache_dir = Path(cache_dir) if cache_dir is not None else RAW_STATIONS / "ghcn"
    path = cache_dir / f"{ghcn_id}.csv"
    if refresh or not path.exists():
        cache_dir.mkdir(parents=True, exist_ok=True)
        r = _SESSION.get(GHCN_ACCESS_URL.format(ghcn=ghcn_id), timeout=300)
        r.raise_for_status()
        path.write_bytes(r.content)
    return parse_ghcn_csv(path)


# ---------------------------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------------------------
def monthly_totals(daily: pd.DataFrame, start: str | None = None,
                   end: str | None = None) -> pd.DataFrame:
    """Aggregate a daily frame (date, precip_in, flag) to calendar-month totals.

    Every calendar day in each month counts, so days absent from ``daily`` are missing.
    ``start``/``end`` ("YYYY-MM-DD") limit the months considered; by default the span of the data.

    Output columns:
        year, month,
        precip_in   sum over non-missing days (trace = 0); NaN only if every day is missing.
                    Use n_missing to decide whether a month is usable (0 = complete).
        n_days      calendar days in the month
        n_missing   days flagged "M" or absent
        n_trace     days with a trace ("T")
        n_accum     days holding a multi-day accumulated value ("A")
        n_subseq    days whose amount is folded into a later "A" value ("S"). These are not
                    missing, but if the "A" day falls in the next month this month is low.
    """
    d = daily[["date", "precip_in", "flag"]].copy()
    d["date"] = pd.to_datetime(d["date"])
    if d.empty and (start is None or end is None):
        return pd.DataFrame(columns=["year", "month", "precip_in", "n_days", "n_missing",
                                     "n_trace", "n_accum", "n_subseq"])
    lo = pd.Timestamp(start) if start else d["date"].min()
    hi = pd.Timestamp(end) if end else d["date"].max()
    lo = lo.replace(day=1)
    hi = hi.replace(day=calendar.monthrange(hi.year, hi.month)[1])
    full = pd.DataFrame({"date": pd.date_range(lo, hi, freq="D")})
    d = full.merge(d.drop_duplicates("date"), on="date", how="left")
    d["flag"] = d["flag"].fillna("M")
    d["year"], d["month"] = d["date"].dt.year, d["date"].dt.month
    g = d.groupby(["year", "month"])
    out = pd.DataFrame({
        "precip_in": g["precip_in"].sum(min_count=1),
        "n_days": g.size(),
        "n_missing": g["flag"].apply(lambda f: int((f == "M").sum())),
        "n_trace": g["flag"].apply(lambda f: int((f == "T").sum())),
        "n_accum": g["flag"].apply(lambda f: int((f == "A").sum())),
        "n_subseq": g["flag"].apply(lambda f: int((f == "S").sum())),
    }).reset_index()
    out["precip_in"] = out["precip_in"].round(2)
    return out


def interval_totals(monthly: pd.DataFrame, by: list[str] | None = None) -> pd.DataFrame:
    """Sum calendar-month totals into PRF two-month intervals (names from prf_intervals).

    ``monthly`` needs year, month, precip_in, n_missing (plus any ``by`` key columns, e.g.
    ["station_key"]). Output columns: by..., year, interval, precip_in, n_missing, complete.
    precip_in is NaN when either month is absent from ``monthly`` (an absent month counts all its
    days as missing); complete means both months are present with zero missing days.
    """
    by = list(by or [])
    m = monthly[by + ["year", "month", "precip_in", "n_missing"]]
    parts = []
    for name in INTERVAL_NAMES:
        m1, m2 = INTERVAL_MONTHS[name]
        a = m[m["month"] == m1].drop(columns="month")
        b = m[m["month"] == m2].drop(columns="month")
        j = a.merge(b, on=by + ["year"], how="outer", suffixes=("_1", "_2"))
        days1 = j["year"].map(lambda y: calendar.monthrange(int(y), m1)[1])
        days2 = j["year"].map(lambda y: calendar.monthrange(int(y), m2)[1])
        present = j["n_missing_1"].notna() & j["n_missing_2"].notna()
        out = j[by + ["year"]].copy()
        out["interval"] = name
        out["precip_in"] = (j["precip_in_1"] + j["precip_in_2"]).round(2)
        out["n_missing"] = (j["n_missing_1"].fillna(days1) + j["n_missing_2"].fillna(days2)
                            ).astype(int)
        out["complete"] = present & (out["n_missing"] == 0)
        parts.append(out)
    res = pd.concat(parts, ignore_index=True)
    res["_order"] = res["interval"].map({n: i for i, n in enumerate(INTERVAL_NAMES)})
    res = res.sort_values(by + ["year", "_order"]).drop(columns="_order")
    return res.reset_index(drop=True)


def latest_complete_month(today: date | None = None) -> tuple[int, int]:
    """(year, month) of the last fully elapsed calendar month before ``today``."""
    today = today or date.today()
    if today.month == 1:
        return today.year - 1, 12
    return today.year, today.month - 1


def month_end(year: int, month: int) -> str:
    """Last calendar day of a month as "YYYY-MM-DD"."""
    return f"{year:04d}-{month:02d}-{calendar.monthrange(year, month)[1]:02d}"


# ---------------------------------------------------------------------------------------------
# NWS CLI reports archived by the Iowa Environmental Mesonet (diagnostic third source)
# ---------------------------------------------------------------------------------------------
def fetch_iem_cli_day(day: str, cache_dir: Path | None = None) -> pd.DataFrame:
    """All NWS daily climate reports (CLI) for one date, as parsed and archived by IEM.

    On a month's last day, ``precip_month`` is the report's month-to-date total, i.e. the number
    Kalshi's NWS-based rules settle on. Columns: station (ICAO), name, valid, product,
    precip, precip_month (str values kept: "T" or "M" possible).
    """
    cache = None if cache_dir is None else Path(cache_dir) / f"iem_cli_{day}.json"
    data = _cached_json(cache, lambda: _request_json("GET", IEM_CLI_URL, params={"dt": day}))
    rows = [f.get("properties", {}) for f in data.get("features", [])]
    cols = ["station", "name", "valid", "product", "precip", "precip_month"]
    return pd.DataFrame([{c: r.get(c) for c in cols} for r in rows], columns=cols)


def cli_value_to_inches(v) -> float:
    """Convert a CLI precip value (float, "T", "M", None) to inches (trace = 0.0, missing = NaN)."""
    if v is None:
        return np.nan
    if isinstance(v, str):
        v = v.strip()
        if v == "T":
            return 0.0
        try:
            return float(v)
        except ValueError:
            return np.nan
    return float(v)


# ---------------------------------------------------------------------------------------------
# Kalshi contract helpers (public market-data API, no auth)
# ---------------------------------------------------------------------------------------------
def kalshi_get(path: str, params: dict | None = None) -> dict:
    """GET a Kalshi public market-data endpoint (relative to KALSHI_BASE_URL)."""
    out = _request_json("GET", KALSHI_BASE_URL + path, params=params or {})
    time.sleep(0.2)
    return out


def kalshi_list_markets(series_ticker: str, *, historical: bool = False,
                        status: str | None = None, cache_path: Path | None = None) -> list[dict]:
    """All markets of a series from /markets (live) or /historical/markets, following cursors.

    Raw market objects are returned unchanged so callers can see Kalshi's current field names
    (prices now come as *_dollars strings and sizes as *_fp strings).
    """
    def fetch():
        path = "/historical/markets" if historical else "/markets"
        out, cursor = [], None
        while True:
            params = {"series_ticker": series_ticker, "limit": 1000}
            if status:
                params["status"] = status
            if cursor:
                params["cursor"] = cursor
            page = kalshi_get(path, params)
            out.extend(page.get("markets", []))
            cursor = page.get("cursor")
            if not cursor:
                return out
    return _cached_json(cache_path, fetch)


_CLI_RE = re.compile(r"\bCLI([A-Z0-9]{3})\b")
_ICAO_RE = re.compile(r"\bat (K[A-Z0-9]{3})\b")


def parse_settlement_location(rules_primary: str | None) -> dict:
    """Find the settlement station named in a Kalshi rain contract's rules_primary text.

    Returns {"code": 3-letter station code or "", "cli_code": "CLIxxx" or "", "how": ...}.
    "how" is "cli" (explicit CLIxxx code), "icao" (e.g. "at KAPC"), "name" (a place name from
    NAMED_LOCATIONS such as "Central Park") or "none".
    """
    text = rules_primary or ""
    m = _CLI_RE.search(text)
    if m:
        return {"code": m.group(1), "cli_code": f"CLI{m.group(1)}", "how": "cli"}
    m = _ICAO_RE.search(text)
    if m:
        return {"code": m.group(1)[1:], "cli_code": f"CLI{m.group(1)[1:]}", "how": "icao"}
    low = text.lower()
    for name, code in NAMED_LOCATIONS.items():
        if name in low:
            return {"code": code, "cli_code": f"CLI{code}", "how": "name"}
    return {"code": "", "cli_code": "", "how": "none"}


_MONTHS = {m.upper(): i for i, m in enumerate(calendar.month_abbr) if m}
_EVENT_RE = re.compile(r"-(\d{2})([A-Z]{3})$")
_EVENT_RANGE_RE = re.compile(r"-(\d{2})([A-Z]{3})(\d{2})-(\d{2})([A-Z]{3})(\d{2})$")
_RULES_MONTH_RE = re.compile(r"\bin ([A-Z][a-z]+) (\d{4})\b")


def event_month(event_ticker: str, rules_primary: str | None = None) -> tuple[int, int] | None:
    """(year, month) of a monthly-rain event, from its ticker ("KXRAINDALM-26OCT") or rules.

    Also handles date-range tickers such as "KXRAINNAPAM-01DEC26-31DEC26" when the range is one
    full calendar month. Returns None if no month can be determined.
    """
    m = _EVENT_RE.search(event_ticker or "")
    if m and m.group(2) in _MONTHS:
        return 2000 + int(m.group(1)), _MONTHS[m.group(2)]
    m = _EVENT_RANGE_RE.search(event_ticker or "")
    if m and m.group(2) in _MONTHS and m.group(5) in _MONTHS:
        y1, mo1, y2, mo2 = 2000 + int(m.group(3)), _MONTHS[m.group(2)], 2000 + int(m.group(6)), \
            _MONTHS[m.group(5)]
        if (y1, mo1) == (y2, mo2) and int(m.group(1)) == 1 and \
                int(m.group(4)) == calendar.monthrange(y1, mo1)[1]:
            return y1, mo1
    for name, year in _RULES_MONTH_RE.findall(rules_primary or ""):
        key = name[:3].upper()
        if key in _MONTHS:
            return int(year), _MONTHS[key]
    return None


def market_yes(strike_type: str, total: float, floor_strike=None, cap_strike=None):
    """Would a market resolve YES for a monthly total? None if undecidable.

    Semantics from Kalshi's RAINM contract terms (assets.kalshi.com/contract_terms/RAINM.pdf):
    "greater" ("Above") = strictly above floor_strike; "greater_or_equal" ("at least") = at or
    above floor; "less" ("below") = strictly below cap_strike; "less_or_equal" = at or below cap;
    "between" = floor <= total < cap (inclusive lower, exclusive upper bound). Totals are
    compared after rounding to 0.01 in. Trace counts as 0.00.
    """
    if total is None or pd.isna(total):
        return None
    t = round(float(total), 2)
    if strike_type == "greater" and floor_strike is not None:
        return t > float(floor_strike)
    if strike_type == "greater_or_equal" and floor_strike is not None:
        return t >= float(floor_strike)
    if strike_type == "less" and cap_strike is not None:
        return t < float(cap_strike)
    if strike_type == "less_or_equal" and cap_strike is not None:
        return t <= float(cap_strike)
    if strike_type == "between" and floor_strike is not None and cap_strike is not None:
        return float(floor_strike) <= t < float(cap_strike)
    return None


_NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")


def _num(x):
    """Float from a number or a string such as "3.5" or "0.61 inches"; None if absent."""
    if x is None or x == "" or (isinstance(x, float) and np.isnan(x)):
        return None
    if isinstance(x, (int, float, np.integer, np.floating)):
        return float(x)
    m = _NUM_RE.search(str(x))
    return float(m.group(0)) if m else None


_ABOVE_RE = re.compile(r"^\s*(?:Above|More than|Over)\s+(\d+(?:\.\d+)?)", re.I)


def normalize_market(mk: dict) -> dict:
    """Copy of a Kalshi rain market with strike fields filled in when the API omits them.

    The Jan 2025 NYC markets have no strike_type/floor_strike; their yes_sub_title reads
    "Above 1 inches" and the ticker ends in "-1". Such markets are treated as "greater" with the
    parsed strike. Adds "expiration_value_in" (float or None) parsed from strings such as
    "0.61 inches", and "settle_source" ("TWC", "NWS" or "unspecified") from rules_secondary.
    """
    out = dict(mk)
    if not out.get("strike_type") or out.get("floor_strike") in (None, ""):
        for field in ("yes_sub_title", "subtitle", "no_sub_title"):
            m = _ABOVE_RE.match(out.get(field) or "")
            if m:
                out["strike_type"] = out.get("strike_type") or "greater"
                out["floor_strike"] = float(m.group(1))
                out["strike_inferred"] = True
                break
    out["expiration_value_in"] = _num(out.get("expiration_value"))
    sec = out.get("rules_secondary") or ""
    if "TWC" in sec or "Weather Company" in sec:
        out["settle_source"] = "TWC"
    elif "NWS" in sec or "National Weather" in sec or "Climatological" in sec:
        out["settle_source"] = "NWS"
    else:
        out["settle_source"] = "unspecified"
    return out


def infer_settled_range(markets: list[dict]) -> dict:
    """Infer the monthly-total interval implied by one event's settled ladder.

    ``markets`` are raw Kalshi market dicts of one event (fields used: strike_type, floor_strike,
    cap_strike, result, expiration_value, settlement_ts). For "Above X" ladders the total lies
    above the highest strike that settled YES and at or below the lowest strike that settled NO.

    Returns dict:
        lo, lo_closed   lower bound (None = no bound) and whether it is inclusive
        hi, hi_closed   upper bound and whether it is inclusive
        label           e.g. "(3, 4]" inches
        consistent      False if the outcomes contradict each other (e.g. YES above 4, NO above 3)
        n_markets, n_yes, n_no
        expiration_value  value reported on the last-settled market (Kalshi's settlement figure;
                        markets that closed early show a partial-month figure, so they are skipped
                        when a later one exists), None if blank everywhere
        early_close     True if any market settled before the others (event hit before month end)
    """
    lo, lo_closed, hi, hi_closed = None, False, None, False
    n_yes = n_no = 0

    def raise_lo(v, closed):
        nonlocal lo, lo_closed
        if lo is None or v > lo or (v == lo and not closed):
            lo, lo_closed = v, closed

    def lower_hi(v, closed):
        nonlocal hi, hi_closed
        if hi is None or v < hi or (v == hi and not closed):
            hi, hi_closed = v, closed

    markets = [normalize_market(mk) for mk in markets]
    for mk in markets:
        res = (mk.get("result") or "").lower()
        if res not in ("yes", "no"):
            continue
        st = mk.get("strike_type")
        f, c = _num(mk.get("floor_strike")), _num(mk.get("cap_strike"))
        yes = res == "yes"
        n_yes += yes
        n_no += not yes
        if st == "greater" and f is not None:  # YES: total > f ; NO: total <= f
            if yes:
                raise_lo(f, False)
            else:
                lower_hi(f, True)
        elif st == "greater_or_equal" and f is not None:  # YES: total >= f ; NO: total < f
            if yes:
                raise_lo(f, True)
            else:
                lower_hi(f, False)
        elif st == "less" and c is not None:  # YES: total < c ; NO: total >= c
            if yes:
                lower_hi(c, False)
            else:
                raise_lo(c, True)
        elif st == "less_or_equal" and c is not None:  # YES: total <= c ; NO: total > c
            if yes:
                lower_hi(c, True)
            else:
                raise_lo(c, False)
        elif st == "between" and f is not None and c is not None and yes:  # f <= total < c
            raise_lo(f, True)
            lower_hi(c, False)
    consistent = True
    if lo is not None and hi is not None:
        consistent = lo < hi or (lo == hi and lo_closed and hi_closed)
    label = ("[" if lo_closed else "(") + ("-inf" if lo is None else f"{lo:g}") + ", " + \
            ("inf" if hi is None else f"{hi:g}") + ("]" if hi_closed else ")")
    settled = [mk for mk in markets if mk.get("settlement_ts")]
    settled.sort(key=lambda mk: mk["settlement_ts"])
    early = len({mk["settlement_ts"][:13] for mk in settled}) > 1
    exp_val = None
    for mk in reversed(settled):
        v = _num(mk.get("expiration_value"))
        if v is not None:
            exp_val = v
            break
    return {"lo": lo, "lo_closed": lo_closed, "hi": hi, "hi_closed": hi_closed, "label": label,
            "consistent": consistent, "n_markets": n_yes + n_no, "n_yes": n_yes, "n_no": n_no,
            "expiration_value": exp_val, "early_close": early}


def value_in_range(total: float, rng: dict) -> bool | None:
    """True if ``total`` lies inside an ``infer_settled_range`` result (None if total is NaN)."""
    if total is None or pd.isna(total):
        return None
    t = round(float(total), 2)
    if rng["lo"] is not None and (t < rng["lo"] or (t == rng["lo"] and not rng["lo_closed"])):
        return False
    if rng["hi"] is not None and (t > rng["hi"] or (t == rng["hi"] and not rng["hi_closed"])):
        return False
    return True


def kalshi_series_markets(series_ticker: str, cache_dir: Path | None = None,
                          refresh: bool = False) -> list[dict]:
    """Every market of a series, live (/markets, all statuses) plus /historical/markets.

    Kalshi moves markets settled before its "historical cutoff" (2026-08-30 when checked on
    2026-10-29) to /historical/markets, so both endpoints are needed. Duplicates are dropped,
    preferring the live copy. Each dict gains "_endpoint": "live" or "historical".
    Raw pages are cached as JSON under ``cache_dir`` (default data/raw/stations/kalshi).
    """
    cache_dir = Path(cache_dir) if cache_dir is not None else RAW_STATIONS / "kalshi"
    live_path = cache_dir / f"{series_ticker}_live.json"
    hist_path = cache_dir / f"{series_ticker}_historical.json"
    if refresh:
        for p in (live_path, hist_path):
            p.unlink(missing_ok=True)
    live = kalshi_list_markets(series_ticker, cache_path=live_path)
    hist = kalshi_list_markets(series_ticker, historical=True, cache_path=hist_path)
    out, seen = [], set()
    for endpoint, rows in (("live", live), ("historical", hist)):
        for mk in rows:
            if mk.get("ticker") in seen:
                continue
            seen.add(mk.get("ticker"))
            out.append({**mk, "_endpoint": endpoint})
    return out


def is_monthly_rain_series(series: dict) -> bool:
    """Kalshi monthly-rain series: ticker contains RAIN and ends in "M" (e.g. KXRAINDALM)."""
    t = series.get("ticker", "")
    return "RAIN" in t and t.endswith("M") and series.get("frequency") in ("monthly", "custom")
