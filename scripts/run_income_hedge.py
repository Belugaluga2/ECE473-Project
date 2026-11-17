"""Doc 25: Kalshi hedges designed to steady a row-crop farm's income instead of copying an index payout.

Run from the repo root:
    python scripts/run_income_hedge.py            # pulls (cached under data/raw/income/), study, tables
    python scripts/run_income_hedge.py --pull     # downloads only
    python scripts/run_income_hedge.py --tables-only   # redo doc tables from the saved CSVs

Question. Every earlier hedge in the project was fit to copy an insurance payout (PRF's, or a
PRF-style index). A farmer wants steady income. Here the target is the farm's own revenue shortfall,
and the contracts are chosen to offset it directly.

Target. County yields (NASS survey, 1971-2025) for corn, soybeans, winter wheat, upland cotton and
grain sorghum, in counties whose centroid is within 60 miles of a Kalshi monthly-rain station. The
income target is L_t = 1 - yield_t / trend_t: the revenue shortfall per $1 of expected revenue at a
fixed price (positive = a bad year, negative = a good year). Var(income + hedge) = Var(L - hedge),
so the score is the same hedge-effectiveness formula as before with L as the target.

Strategies (each scored leave-one-year-out: weights, scale and ridge chosen without the scored year):
  A  index insurance: a PRF-style payout on the county's own two-month rain index for the crop's
     critical intervals, sized to minimise income variance. What a perfect rain-index product does.
  B  Kalshi copies A: the station NO ladder fit to A's payout (today's approach), sized as in A.
  C  income-targeted, station rain: NO and YES contracts on the station's monthly rain, fit to L.
  D  C plus heat: counts of days at or above a temperature threshold, built by buying one YES on the
     station's daily-high market each day of the month (only where Kalshi lists one within 60 mi).
  E  proposal: the same fit on contracts that settle on the county's own monthly rain (NOAA nClimGrid
     county series) and the county's monthly mean maximum temperature.

Fits are long-only (non-negative) ridge least squares on centred, standardised payoffs; the ridge
strength is picked by 5-fold CV inside each training set.

Data (all public, no keys): NASS Quick Stats keyless CSV export; ACIS StnData daily max temperature;
NOAA Climate at a Glance county monthly precipitation and maximum temperature; Census 2024 county
Gazetteer; committed station rain (data/processed/station_monthly_precip.csv).
"""
from __future__ import annotations

import argparse
import io
import json
import time
import urllib.parse
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from scipy.optimize import nnls

from raincheck.config import PROCESSED, RAW

RAW_INC = RAW / "income"
RAW_INC.mkdir(parents=True, exist_ok=True)
HEADERS = {"User-Agent": "ECE473-raincheck research script"}
QS_URL = "https://quickstats.nass.usda.gov"
GAZ_URL = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_counties_national.zip"
CAG_COUNTY = "https://www.ncei.noaa.gov/access/monitoring/climate-at-a-glance/county/time-series"
ACIS_URL = "https://data.rcc-acis.org/StnData"

YEARS = (1971, 2025)
MAX_MI = 60.0
MIN_YEARS = 45

# crop -> NASS items, states to pull, minimum recent harvested acres, price ($ per unit, WASDE-676 Oct 2026
# via doc 03b), unit
CROPS = {
    "corn": dict(item="CORN, GRAIN", unit="BU", ni="CORN, GRAIN, NON-IRRIGATED",
                 states=["IL", "IN", "OH", "MN", "WI", "MI", "MO", "KY", "PA", "NJ", "MD", "DE", "TX", "OK", "CO", "GA"],
                 min_acres=15000, price=4.70),
    "soybeans": dict(item="SOYBEANS", unit="BU", ni="SOYBEANS, NON-IRRIGATED",
                     states=["IL", "IN", "OH", "MN", "WI", "MI", "MO", "KY", "PA", "NJ", "MD", "DE"],
                     min_acres=15000, price=12.00),
    "winter wheat": dict(item="WHEAT, WINTER", unit="BU", ni="WHEAT, WINTER, NON-IRRIGATED",
                         states=["OK", "TX", "CO", "IL", "IN", "OH", "MO", "KY", "MI", "PA", "MD", "WA"],
                         min_acres=10000, price=6.30),
    "cotton": dict(item="COTTON, UPLAND", unit="LB", ni="COTTON, UPLAND, NON-IRRIGATED",
                   states=["TX", "OK", "GA", "LA", "MO"], min_acres=10000, price=0.77),   # AZ: irrigated
    "sorghum": dict(item="SORGHUM, GRAIN", unit="BU", ni="SORGHUM, GRAIN, NON-IRRIGATED",
                    states=["TX", "OK", "CO", "MO"], min_acres=5000, price=4.50),
}
NONIRR_STATES = {"TX", "CO", "OK"}

# Crop calendars. Months are (year offset, month): offset -1 = the autumn before harvest (winter wheat).
# rain: months with station NO legs (dry) ; wet: months that also get YES legs (excess rain);
# heat: months with hot-day counts, at the listed thresholds (deg F); index: PRF-style two-month intervals.
SEASONS = {
    "corn": dict(rain=[(0, 5), (0, 6), (0, 7), (0, 8)], wet=[(0, 5), (0, 6), (0, 7)],
                 heat=[(0, 6), (0, 7), (0, 8)], thr=[90, 95], index=[((0, 6), (0, 7))]),
    "soybeans": dict(rain=[(0, 6), (0, 7), (0, 8), (0, 9)], wet=[(0, 6), (0, 9)],
                     heat=[(0, 7), (0, 8)], thr=[90, 95], index=[((0, 7), (0, 8))]),
    "winter wheat": dict(rain=[(-1, 9), (-1, 10), (-1, 11), (0, 3), (0, 4), (0, 5)], wet=[(0, 5), (0, 6)],
                         heat=[(0, 4), (0, 5)], thr=[85, 90], index=[((-1, 10), (-1, 11)), ((0, 3), (0, 4))]),
    "cotton": dict(rain=[(0, 5), (0, 6), (0, 7), (0, 8), (0, 9)], wet=[(0, 9), (0, 10)],
                   heat=[(0, 7), (0, 8)], thr=[95, 100], index=[((0, 6), (0, 7)), ((0, 8), (0, 9))]),
    "sorghum": dict(rain=[(0, 6), (0, 7), (0, 8)], wet=[(0, 9)],
                    heat=[(0, 7), (0, 8)], thr=[95, 100], index=[((0, 7), (0, 8))]),
}

# Kalshi daily-high series by settlement station (doc 05 catalog, has_open_markets = True)
TEMP_MARKETS = {"MDW": "KXHIGHCHI", "MSP": "KXHIGHTMIN", "OKC": "KXHIGHTOKC", "DFW": "KXHIGHTDAL",
                "DEN": "KXHIGHDEN", "AUS": "KXHIGHAUS", "SAT": "KXHIGHTSATX", "PHL": "KXHIGHPHIL",
                "TTN": "KXHIGHTTTN", "EWR": "KXHIGHTEWR", "ATL": "KXHIGHTATL", "DCA": "KXHIGHTDC",
                "HOU": "KXHIGHTHOU", "MSY": "KXHIGHTNOLA", "PHX": "KXHIGHTPHX", "SEA": "KXHIGHTSEA"}
SKIP_RAIN = {"SPG", "APC", "MDW"}   # short records; Kalshi Chicago rain now settles at ORD (MDW = heat only)
HEAT_THRESHOLDS = (85, 90, 95, 100, 105)


# ---------------------------------------------------------------------------------------------
# downloads (cached)
# ---------------------------------------------------------------------------------------------

def _get(url: str, tries: int = 5, **kw) -> requests.Response:
    last = None
    for i in range(tries):
        try:
            last = requests.get(url, headers=HEADERS, timeout=180, **kw)
        except requests.RequestException:
            time.sleep(2 ** i)
            continue
        if last.status_code == 200:
            return last
        if last.status_code in (400, 404):
            return last
        time.sleep(2 ** i)
    if last is None:
        raise RuntimeError(f"no response from {url}")
    return last


def nass(params: dict, name: str) -> pd.DataFrame:
    path = RAW_INC / "nass" / f"{name}.csv"
    path.parent.mkdir(exist_ok=True)
    if not path.exists():
        q = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
        r = _get(f"{QS_URL}/uuid/encode?{q}")
        uuid = r.text.strip().strip('"')
        r2 = _get(f"{QS_URL}/data/spreadsheet/{uuid}.csv")
        txt = r2.text if r2.status_code == 200 and r2.text.startswith('"Program"') else ""
        path.write_text(txt, encoding="utf-8")
        time.sleep(0.3)
    if path.stat().st_size == 0:
        return pd.DataFrame()
    df = pd.read_csv(path, dtype=str)
    df["value"] = pd.to_numeric(df["Value"].str.replace(",", "").str.strip(), errors="coerce")
    df["year"] = pd.to_numeric(df["Year"], errors="coerce")
    return df


def county_yields() -> pd.DataFrame:
    """Long frame: crop, practice (all / nonirr), geoid, year, yield, acres."""
    rows = []
    for crop, c in CROPS.items():
        for st in c["states"]:
            items = [("all", c["item"])] + ([("nonirr", c["ni"])] if st in NONIRR_STATES else [])
            for practice, item in items:
                parts = {}
                for what, suffix in (("yield", f" - YIELD, MEASURED IN {c['unit']} / ACRE"),
                                     ("acres", " - ACRES HARVESTED")):
                    d = nass({"source_desc": "SURVEY", "agg_level_desc": "COUNTY", "state_alpha": st,
                              "short_desc": item + suffix, "reference_period_desc": "YEAR"},
                             f"{crop.replace(' ', '_')}_{practice}_{what}_{st}")
                    if d.empty:
                        continue
                    d = d[(d["Period"] == "YEAR") & d["County ANSI"].fillna("").str.strip().ne("")]
                    d["geoid"] = d["State ANSI"].str.zfill(2) + d["County ANSI"].str.strip().str.zfill(3)
                    parts[what] = d.groupby(["geoid", "year"])["value"].first()
                if "yield" not in parts:
                    continue
                f = pd.DataFrame({"yield": parts["yield"]})
                f["acres"] = parts["acres"] if "acres" in parts else np.nan
                f = f.reset_index()
                f["crop"], f["practice"], f["state"] = crop, practice, st
                rows.append(f)
        print("nass", crop, flush=True)
    return pd.concat(rows, ignore_index=True)


def gazetteer() -> pd.DataFrame:
    path = RAW_INC / "2024_Gaz_counties_national.zip"
    if not path.exists():
        path.write_bytes(_get(GAZ_URL).content)
    with zipfile.ZipFile(path) as z:
        txt = z.read([n for n in z.namelist() if n.endswith(".txt")][0]).decode("latin-1")
    g = pd.read_csv(io.StringIO(txt), sep="\t", dtype={"GEOID": str})
    g.columns = [c.strip() for c in g.columns]
    return g[["GEOID", "USPS", "NAME", "INTPTLAT", "INTPTLONG"]].rename(
        columns={"GEOID": "geoid", "USPS": "usps", "NAME": "county", "INTPTLAT": "lat", "INTPTLONG": "lon"})


def cag_county(usps: str, geoid: str, var: str) -> pd.Series:
    """NOAA Climate at a Glance county monthly series (pcp inches / tmax deg F), indexed by (year, month)."""
    path = RAW_INC / "cag" / f"{geoid}_{var}.csv"
    path.parent.mkdir(exist_ok=True)
    if not path.exists():
        url = f"{CAG_COUNTY}/{usps}-{geoid[2:]}/{var}/1/0/1950-2025/data.csv"
        r = _get(url)
        path.write_text(r.text if r.status_code == 200 else "", encoding="utf-8")
        time.sleep(0.2)
    txt = path.read_text(encoding="utf-8")
    if "Date,Value" not in txt:
        return pd.Series(dtype=float)
    df = pd.read_csv(io.StringIO(txt[txt.index("Date,Value"):]))
    df = df[df["Value"] > -90]
    return pd.Series(df["Value"].to_numpy(float), index=pd.MultiIndex.from_arrays(
        [df["Date"] // 100, df["Date"] % 100], names=["year", "month"]))


def acis_tmax(sid: str, key: str) -> pd.DataFrame:
    path = RAW_INC / "acis" / f"tmax_{key}.json"
    path.parent.mkdir(exist_ok=True)
    if not path.exists():
        payload = {"sid": sid, "sdate": "1950-01-01", "edate": "2025-12-31", "elems": [{"name": "maxt"}],
                   "meta": "name,sids"}
        for i in range(5):
            try:
                r = requests.post(ACIS_URL, json=payload, timeout=180)
                if r.status_code == 200:
                    path.write_text(r.text, encoding="utf-8")
                    break
            except requests.RequestException:
                pass
            time.sleep(2 ** i)
    data = json.loads(path.read_text(encoding="utf-8"))
    df = pd.DataFrame(data["data"], columns=["date", "tmax"])
    df["date"] = pd.to_datetime(df["date"])
    df["tmax"] = pd.to_numeric(df["tmax"], errors="coerce")
    return df


def stations() -> pd.DataFrame:
    sm = pd.read_csv(PROCESSED / "station_map.csv", dtype=str)
    sm = sm.drop_duplicates("station_key", keep="last")
    sm["lat"], sm["lon"] = sm["lat"].astype(float), sm["lon"].astype(float)
    sm["sid"] = sm["thr_sid"].where(sm["thr_sid"].notna() & sm["thr_sid"].ne(""), sm["acis_sid"])
    return sm[["station_key", "name", "state", "lat", "lon", "sid", "acis_sid"]]


def hot_days(st: pd.DataFrame) -> pd.DataFrame:
    """Days per month with Tmax >= each threshold, for every Kalshi daily-high station. Long frame."""
    out = []
    for key in TEMP_MARKETS:
        row = st[st["station_key"] == key]
        if row.empty:
            continue
        sid = row["acis_sid"].iloc[0] if key == "MDW" else row["sid"].iloc[0]
        d = acis_tmax(sid, key)
        if key == "MDW":
            # Midway (Kalshi's Chicago settlement station) has gaps; fill them from the O'Hare threaded
            # record, about 10 miles away.
            o = acis_tmax("ORDthr 9", "ORD").rename(columns={"tmax": "ord"})
            d = d.merge(o, on="date", how="outer")
            d["tmax"] = d["tmax"].fillna(d["ord"])
            d = d[["date", "tmax"]]
        d["year"], d["month"] = d["date"].dt.year, d["date"].dt.month
        g = d.groupby(["year", "month"])
        valid = g["tmax"].count()
        for thr in HEAT_THRESHOLDS:
            n = d.assign(h=(d["tmax"] >= thr).astype(float).where(d["tmax"].notna())).groupby(
                ["year", "month"])["h"].sum()
            n = n.where(valid >= 25)
            out.append(pd.DataFrame({"station_key": key, "thr": thr, "hot_days": n}).reset_index())
        print("acis", key, flush=True)
    return pd.concat(out, ignore_index=True)


def haversine_mi(lat1, lon1, lat2, lon2):
    r = 3958.8
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


# ---------------------------------------------------------------------------------------------
# sites
# ---------------------------------------------------------------------------------------------

def select_sites(yl: pd.DataFrame, gz: pd.DataFrame, st: pd.DataFrame) -> pd.DataFrame:
    """One row per (crop, county): counties within MAX_MI of a rain station with a long yield record.

    Non-irrigated yields are used where NASS publishes them for MIN_YEARS (TX, CO, OK); otherwise all
    practices. Up to three counties per (crop, station), the largest by recent harvested acres."""
    rain_keys = set(pd.read_csv(PROCESSED / "station_monthly_precip.csv", usecols=["station_key"])
                    ["station_key"].unique()) - SKIP_RAIN
    rs = st[st["station_key"].isin(rain_keys)]
    ts = st[st["station_key"].isin(TEMP_MARKETS)]
    y = yl[(yl["year"] >= YEARS[0]) & (yl["year"] <= YEARS[1])]
    rec = (y.dropna(subset=["yield"]).groupby(["crop", "practice", "geoid"])
           .agg(n_years=("year", "nunique"), state=("state", "first")).reset_index())
    acres = (yl[yl["practice"] == "all"].query("year >= 2006").groupby(["crop", "geoid"])["acres"].mean()
             .rename("acres_recent").reset_index())
    rec = rec[rec["n_years"] >= MIN_YEARS].copy()
    # prefer non-irrigated where it exists with a long record
    rec["pref"] = (rec["practice"] == "nonirr").astype(int)
    rec = rec.sort_values("pref").drop_duplicates(["crop", "geoid"], keep="last")
    rec = rec.merge(acres, on=["crop", "geoid"], how="left").merge(gz, on="geoid", how="left")
    d = haversine_mi(rec["lat"].to_numpy()[:, None], rec["lon"].to_numpy()[:, None],
                     rs["lat"].to_numpy()[None, :], rs["lon"].to_numpy()[None, :])
    rec["station"] = rs["station_key"].to_numpy()[d.argmin(1)]
    rec["dist_mi"] = d.min(1)
    dt = haversine_mi(rec["lat"].to_numpy()[:, None], rec["lon"].to_numpy()[:, None],
                      ts["lat"].to_numpy()[None, :], ts["lon"].to_numpy()[None, :])
    rec["heat_station"] = np.where(dt.min(1) <= MAX_MI, ts["station_key"].to_numpy()[dt.argmin(1)], "")
    rec["heat_dist_mi"] = np.where(dt.min(1) <= MAX_MI, dt.min(1), np.nan)
    rec["min_acres"] = rec["crop"].map({k: v["min_acres"] for k, v in CROPS.items()})
    rec = rec[(rec["dist_mi"] <= MAX_MI) & (rec["acres_recent"] >= rec["min_acres"])]
    rec = (rec.sort_values("acres_recent", ascending=False).groupby(["crop", "station"]).head(3)
           .sort_values(["crop", "station", "acres_recent"], ascending=[True, True, False]))
    return rec[["crop", "practice", "geoid", "usps", "county", "lat", "lon", "station", "dist_mi",
                "heat_station", "heat_dist_mi", "n_years", "acres_recent"]].reset_index(drop=True)


def pull_all():
    st = stations()
    yl = county_yields()
    yl.to_csv(RAW_INC / "county_yields_long.csv", index=False)
    gz = gazetteer()
    sites = select_sites(yl, gz, st)
    sites.to_csv(RAW_INC / "sites.csv", index=False)
    print(sites.groupby("crop").size().to_string(), flush=True)
    for _, s in sites.drop_duplicates("geoid").iterrows():
        cag_county(s["usps"], s["geoid"], "pcp")
        cag_county(s["usps"], s["geoid"], "tmax")
    print("cag done", flush=True)
    hd = hot_days(st)
    hd.to_csv(RAW_INC / "hot_days.csv", index=False)
    return st, yl, sites, hd


# ---------------------------------------------------------------------------------------------
# panel and payoffs
# ---------------------------------------------------------------------------------------------

W0 = 1.0          # farm wealth buffer per $1 of expected revenue, for the CRRA check
W0_THIN = 0.4     # sensitivity: a thin-margin farm
GAMMA = 2.0
LOAD = 0.12       # Kalshi all-in cost per $1 of expected payout: 1.12 (doc 14 central case)
INS_COVERAGE = 0.75
RIDGE_GRID = (0.01, 0.03, 0.1, 0.3, 1.0, 3.0)
DAYS = {1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30, 7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31}
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def quadratic_trend(years: np.ndarray, y: np.ndarray):
    mid = years.mean()
    t = (years - mid) / 10.0
    A = np.column_stack([np.ones_like(t), t, t ** 2])
    coef, *_ = np.linalg.lstsq(A, y, rcond=None)
    return A @ coef, coef, mid


def trend_at(coef, mid, year):
    t = (year - mid) / 10.0
    return coef[0] + coef[1] * t + coef[2] * t ** 2


def monthly_lookup(series: pd.Series, years: np.ndarray, off: int, month: int) -> np.ndarray:
    idx = pd.MultiIndex.from_arrays([years + off, np.full(len(years), month)])
    return series.reindex(idx).to_numpy(float)


def mlabel(off: int, m: int) -> str:
    return ("prev " if off < 0 else "") + MONTHS[m - 1]


def _binary(cond: np.ndarray, x: np.ndarray) -> np.ndarray:
    out = cond.astype(float)
    out[np.isnan(x)] = np.nan
    return out


def station_rain_legs(rain: pd.Series, years, season):
    cols, legs = [], []
    for off, m in season["rain"]:
        r = monthly_lookup(rain, years, off, m)
        kmax = int(min(10, max(2, np.ceil(np.nanquantile(r, 0.9)))))
        for k in range(1, kmax + 1):
            cols.append(_binary(r <= k, r))
            legs.append(dict(kind="dry", src="station", month=mlabel(off, m), strike=k,
                             desc=f"NO on {mlabel(off, m)} station rain above {k} in"))
    for off, m in season["wet"]:
        r = monthly_lookup(rain, years, off, m)
        lo = max(1, int(np.floor(np.nanquantile(r, 0.5))))
        for k in range(lo, int(np.ceil(np.nanquantile(r, 0.95))) + 1):
            cols.append(_binary(r > k, r))
            legs.append(dict(kind="wet", src="station", month=mlabel(off, m), strike=k,
                             desc=f"YES on {mlabel(off, m)} station rain above {k} in"))
    return np.column_stack(cols), legs


def heat_legs(hd: pd.DataFrame, station: str, years, season):
    cols, legs = [], []
    if not station:
        return np.empty((len(years), 0)), legs
    h = hd[hd["station_key"] == station]
    for off, m in season["heat"]:
        # thresholds where hot days are uncommon (0.5-12 a month on average), so the farmer is not
        # paying the markup on near-certain payments; the two closest to 4 days, or the nearest one
        cand = []
        for thr in HEAT_THRESHOLDS:
            s = h[h["thr"] == thr].set_index(["year", "month"])["hot_days"]
            v = monthly_lookup(s, years, off, m)
            cand.append((thr, v, float(np.nanmean(v))))
        good = [c for c in cand if 0.5 <= c[2] <= 12]
        pick = sorted(good, key=lambda c: abs(c[2] - 4))[:2] if good else [min(cand, key=lambda c: abs(c[2] - 4))]
        for thr, v, _ in sorted(pick, key=lambda c: c[0]):
            cols.append(v)
            legs.append(dict(kind="heat", src="station", month=mlabel(off, m), strike=thr,
                             desc=f"YES each day of {mlabel(off, m)}: daily high {thr}F or above ({TEMP_MARKETS[station]})"))
    return np.column_stack(cols), legs


def county_legs(pcp: pd.Series, tmax: pd.Series, years, season):
    """Proposed county-settled contracts: rain NO/YES on a half-inch grid, monthly mean Tmax YES."""
    cols, legs = [], []
    for off, m in season["rain"]:
        r = monthly_lookup(pcp, years, off, m)
        for k in np.arange(np.floor(np.nanquantile(r, 0.1) * 2) / 2, np.nanquantile(r, 0.9), 0.5)[1:]:
            cols.append(_binary(r <= k, r))
            legs.append(dict(kind="dry", src="county", month=mlabel(off, m), strike=float(k),
                             desc=f"county {mlabel(off, m)} rain at or below {k:.1f} in"))
    for off, m in season["wet"]:
        r = monthly_lookup(pcp, years, off, m)
        for k in np.arange(np.ceil(np.nanquantile(r, 0.5) * 2) / 2, np.nanquantile(r, 0.95), 0.5):
            cols.append(_binary(r > k, r))
            legs.append(dict(kind="wet", src="county", month=mlabel(off, m), strike=float(k),
                             desc=f"county {mlabel(off, m)} rain above {k:.1f} in"))
    for off, m in season["heat"]:
        t = monthly_lookup(tmax, years, off, m)
        for q in (0.6, 0.75, 0.9):
            k = round(float(np.nanquantile(t, q)), 1)
            cols.append(_binary(t > k, t))
            legs.append(dict(kind="heat", src="county", month=mlabel(off, m), strike=k,
                             desc=f"county {mlabel(off, m)} mean daily high above {k:.1f}F"))
    return np.column_stack(cols), legs


def index_payout(pcp: pd.Series, years, season, coverage: float = 0.9) -> np.ndarray:
    """PRF-style payout on the county's own two-month rain index, averaged over the crop's intervals."""
    total = np.zeros(len(years))
    for (o1, m1), (o2, m2) in season["index"]:
        r = monthly_lookup(pcp, years, o1, m1) + monthly_lookup(pcp, years, o2, m2)
        idx = 100 * r / np.nanmean(r)
        total = total + np.maximum(0, (100 * coverage - idx) / (100 * coverage))
    return total / len(season["index"])


def interval_no_ladder(rain: pd.Series, years, season) -> np.ndarray:
    cols = []
    for pair in season["index"]:
        for off, m in pair:
            r = monthly_lookup(rain, years, off, m)
            kmax = int(min(10, max(2, np.ceil(np.nanquantile(r, 0.9)))))
            cols += [_binary(r <= k, r) for k in range(1, kmax + 1)]
    return np.column_stack(cols)


# ---------------------------------------------------------------------------------------------
# fitting
# ---------------------------------------------------------------------------------------------

def ridge_nnls(X: np.ndarray, y: np.ndarray, lam: float) -> np.ndarray:
    """min |(y - ybar) - (X - Xbar) w|^2 + lam * n * |D w|^2 over w >= 0, D = column sd (the penalty is
    on standardised weights). Returns raw-unit weights; constant columns get 0."""
    n, k = X.shape
    sd = X.std(0)
    keep = sd > 1e-9
    w = np.zeros(k)
    if not keep.any():
        return w
    Z = (X[:, keep] - X[:, keep].mean(0)) / sd[keep]
    yc = y - y.mean()
    A = np.vstack([Z, np.sqrt(lam * n) * np.eye(int(keep.sum()))])
    b = np.concatenate([yc, np.zeros(int(keep.sum()))])
    v, _ = nnls(A, b, maxiter=50 * A.shape[1])
    w[keep] = v / sd[keep]
    return w


def choose_lambda(X, y, seed: int = 0) -> float:
    n = len(y)
    folds = np.random.default_rng(seed).permutation(n) % 5
    best, best_lam = np.inf, RIDGE_GRID[-1]
    for lam in RIDGE_GRID:
        sse = 0.0
        for f in range(5):
            tr, te = folds != f, folds == f
            w = ridge_nnls(X[tr], y[tr], lam)
            pred = (X[te] - X[tr].mean(0)) @ w + y[tr].mean()
            sse += ((y[te] - pred) ** 2).sum()
        if sse < best - 1e-12:
            best, best_lam = sse, lam
    return best_lam


def best_scale(L_tr: np.ndarray, h_tr: np.ndarray, load: float = LOAD, w0: float = W0) -> float:
    """Size (0-1.5 x the variance-optimal hedge) that maximises the farmer's CRRA certainty equivalent on
    the training years, paying (1 + load) x the training-mean payout. 0 = buy nothing."""
    prem = h_tr.mean()
    best_s, best_ce = 0.0, crra_ce(w0 - L_tr)
    for s in np.linspace(0.05, 1.5, 30):
        ce = crra_ce(w0 - L_tr + s * (h_tr - (1 + load) * prem))
        if ce > best_ce + 1e-12:
            best_s, best_ce = float(s), ce
    return best_s


def loyo(fit, L: np.ndarray):
    """Leave one year out. fit(train_mask) returns the payout in every year from a fit on train_mask.
    Returns the held-out payout, its premium (training-mean payout) and the utility-optimal size."""
    n = len(L)
    h, prem, s = np.full(n, np.nan), np.full(n, np.nan), np.full((n, 2), np.nan)
    for i in range(n):
        tr = np.arange(n) != i
        hall = fit(tr)
        h[i], prem[i] = hall[i], hall[tr].mean()
        s[i] = best_scale(L[tr], hall[tr]), best_scale(L[tr], hall[tr], w0=W0_THIN)
    return h, prem, s


def ridge_fit(X: np.ndarray, L: np.ndarray):
    def fit(tr):
        return X @ ridge_nnls(X[tr], L[tr], choose_lambda(X[tr], L[tr]))
    return fit


def _beta(L, P):
    c = np.cov(L, P)
    return max(0.0, c[0, 1] / c[1, 1]) if c[1, 1] > 0 else 0.0


def index_fit(P: np.ndarray, L: np.ndarray):
    """Strategy A: beta x the county index payout, beta = argmin Var(L - beta P) on the training years."""
    return lambda tr: _beta(L[tr], P[tr]) * P


def copy_fit(Xs: np.ndarray, P: np.ndarray, L: np.ndarray):
    """Strategy B: station NO ladder fit to the index payout P (NNLS), then sized like A."""
    def fit(tr):
        w = ridge_nnls(Xs[tr], P[tr], 1e-6)
        return _beta(L[tr], P[tr]) * np.maximum(0.0, (Xs - Xs[tr].mean(0)) @ w + P[tr].mean())
    return fit


def crra_ce(w: np.ndarray, gamma: float = GAMMA) -> float:
    w = np.maximum(w, 0.05)
    if gamma == 1:
        return float(np.exp(np.mean(np.log(w))))
    return float(np.mean(w ** (1 - gamma)) ** (1 / (1 - gamma)))


def metrics(L: np.ndarray, h: np.ndarray, prem: np.ndarray, s: np.ndarray, load: float = LOAD) -> dict:
    ok = ~np.isnan(L) & ~np.isnan(h)
    L, h, prem, s = L[ok], h[ok], prem[ok], s[ok]
    worst = np.argsort(-L)[:5]
    base = crra_ce(W0 - L)
    return {"he": float(1 - np.var(L - h) / np.var(L)),
            "sd_before": float(np.std(L)), "sd_after": float(np.std(L - h)),
            "tail5": float(h[worst].sum() / L[worst].sum()) if L[worst].sum() > 0 else np.nan,
            "premium": float(prem.mean()),
            "ce_gain_fair": crra_ce(W0 - L + h - prem) - base,
            "ce_gain_load": crra_ce(W0 - L + h - prem * (1 + load)) - base,
            "opt_scale": float(s[:, 0].mean()), "opt_buy_share": float((s[:, 0] > 0).mean()),
            "opt_premium": float((s[:, 0] * prem).mean()),
            "ce_gain_opt": crra_ce(W0 - L + s[:, 0] * (h - prem * (1 + load))) - base,
            "thin_buy_share": float((s[:, 1] > 0).mean()), "thin_premium": float((s[:, 1] * prem).mean()),
            "ce_gain_thin": (crra_ce(W0_THIN - L + s[:, 1] * (h - prem * (1 + load)))
                             - crra_ce(W0_THIN - L))}


# structured payouts: a few interpretable features, each exactly a stack of listed contracts

def station_structured(rain: pd.Series, years, season):
    """Per rain month: whole inches below the median (= one NO contract at each whole-inch strike from
    1 in up to the median). Per wet month: whole inches above the upper quartile, up to 6 (= one YES at
    each strike from the quartile up)."""
    cols, feats = [], []
    for off, m in season["rain"]:
        r = monthly_lookup(rain, years, off, m)
        kn = max(1, int(round(np.nanmedian(r))))
        cols.append(np.nansum([_binary(r <= k, r) for k in range(1, kn + 1)], axis=0) + 0 * r)
        feats.append(dict(kind="dry", src="station", month=mlabel(off, m), strikes=list(range(1, kn + 1)), per_day=False,
                          desc=f"$ per whole inch {mlabel(off, m)} station rain falls below {kn} in "
                               f"(1 NO each at {', '.join(str(k) for k in range(1, kn + 1))} in)"))
    for off, m in season["wet"]:
        r = monthly_lookup(rain, years, off, m)
        kw = max(1, int(np.ceil(np.nanquantile(r, 0.75))))
        ks = list(range(kw, kw + 6))
        cols.append(np.nansum([_binary(r > k, r) for k in ks], axis=0) + 0 * r)
        feats.append(dict(kind="wet", src="station", month=mlabel(off, m), strikes=ks, per_day=False,
                          desc=f"$ per whole inch {mlabel(off, m)} station rain exceeds {kw} in, up to 6 in "
                               f"(1 YES each at {ks[0]}-{ks[-1]} in)"))
    return np.column_stack(cols), feats


def heat_features(hd: pd.DataFrame, station: str, years, season):
    X, legs = heat_legs(hd, station, years, season)
    feats = [dict(kind="heat", src="station", month=lg["month"], strikes=[lg["strike"]], per_day=True,
                  desc=f"$ per {lg['month']} day with a daily high of {lg['strike']}F or above "
                       f"(1 YES each day, {TEMP_MARKETS[station]})") for lg in legs]
    return X, feats


def county_structured(pcp: pd.Series, tmax: pd.Series, years, season):
    """Proposal: continuous county payouts. Inches below the county's median rain, inches above its
    upper quartile (wet months), degrees F the monthly mean daily high exceeds its median."""
    cols, feats = [], []
    for off, m in season["rain"]:
        r = monthly_lookup(pcp, years, off, m)
        med = float(np.nanmedian(r))
        cols.append(np.maximum(0, med - r))
        feats.append(dict(kind="dry", src="county", month=mlabel(off, m), strikes=[round(med, 2)], per_day=False,
                          desc=f"$ per inch county {mlabel(off, m)} rain falls below {med:.2f} in"))
    for off, m in season["wet"]:
        r = monthly_lookup(pcp, years, off, m)
        q = float(np.nanquantile(r, 0.75))
        cols.append(np.minimum(6, np.maximum(0, r - q)))
        feats.append(dict(kind="wet", src="county", month=mlabel(off, m), strikes=[round(q, 2)], per_day=False,
                          desc=f"$ per inch county {mlabel(off, m)} rain exceeds {q:.2f} in"))
    for off, m in season["heat"]:
        t = monthly_lookup(tmax, years, off, m)
        med = float(np.nanmedian(t))
        cols.append(np.maximum(0, t - med))
        feats.append(dict(kind="heat", src="county", month=mlabel(off, m), strikes=[round(med, 1)], per_day=False,
                          desc=f"$ per degree county {mlabel(off, m)} mean daily high exceeds {med:.1f}F"))
    return np.column_stack(cols), feats


def ticket_rows(base: dict, strat: str, X: np.ndarray, L: np.ndarray, feats: list, rev: float) -> list:
    lam = choose_lambda(X, L)
    w = ridge_nnls(X, L, lam)
    rows = []
    for j in np.flatnonzero(w > 1e-9):
        f = feats[j]
        mon = MONTHS.index(f["month"].replace("prev ", "")) + 1
        per_strike = w[j] * rev * 1000            # contracts per strike (or per day) per 1,000 acres
        n_contracts = per_strike * (DAYS[mon] if f["per_day"] else len(f["strikes"])) if f["src"] == "station" else np.nan
        rows.append(dict(base, strategy=strat, ridge=lam, feature=f["desc"], kind=f["kind"], src=f["src"],
                         month=f["month"], weight=float(w[j]), dollars_per_acre_per_unit=float(w[j] * rev),
                         contracts_per_strike_per_1000_acres=float(per_strike) if f["src"] == "station" else np.nan,
                         contracts_per_1000_acres=float(n_contracts),
                         expected_payout_share=float((X[:, j] * w[j]).mean())))
    return rows


# ---------------------------------------------------------------------------------------------
# study
# ---------------------------------------------------------------------------------------------

def _load_inputs():
    yl = pd.read_csv(RAW_INC / "county_yields_long.csv", dtype={"geoid": str})
    sites = pd.read_csv(RAW_INC / "sites.csv", dtype={"geoid": str})
    sites["heat_station"] = sites["heat_station"].fillna("")
    hd = pd.read_csv(RAW_INC / "hot_days.csv")
    sr = pd.read_csv(PROCESSED / "station_monthly_precip.csv", usecols=["station_key", "year", "month", "precip_in"])
    return yl, sites, hd, sr


def study_site(s: dict, yl: pd.DataFrame, hd: pd.DataFrame, sr: pd.DataFrame):
    crop, season = s["crop"], SEASONS[s["crop"]]
    y = yl[(yl["crop"] == crop) & (yl["practice"] == s["practice"]) & (yl["geoid"] == s["geoid"])
           & yl["year"].between(*YEARS)].dropna(subset=["yield"]).sort_values("year")
    years_all = y["year"].to_numpy(int)
    trend, coef, mid = quadratic_trend(years_all.astype(float), y["yield"].to_numpy(float))
    L_all = 1 - y["yield"].to_numpy(float) / trend
    rain = sr[sr["station_key"] == s["station"]].set_index(["year", "month"])["precip_in"]
    pcp = cag_county(s["usps"], s["geoid"], "pcp")
    tmax = cag_county(s["usps"], s["geoid"], "tmax")

    mats = {"Xr": station_rain_legs(rain, years_all, season)[0],
            "Xh": heat_features(hd, s["heat_station"], years_all, season)[0],
            "Xe": county_legs(pcp, tmax, years_all, season)[0],
            "Xs": interval_no_ladder(rain, years_all, season),
            "Fr": station_structured(rain, years_all, season)[0],
            "Fe": county_structured(pcp, tmax, years_all, season)[0],
            "P": index_payout(pcp, years_all, season)[:, None]}
    feats = {"Fr": station_structured(rain, years_all, season)[1],
             "Fh": heat_features(hd, s["heat_station"], years_all, season)[1],
             "Fe": county_structured(pcp, tmax, years_all, season)[1]}
    ok = ~np.isnan(L_all)
    for M in mats.values():
        ok &= ~np.isnan(M).any(1)
    years, L = years_all[ok], L_all[ok]
    mats = {k: v[ok] for k, v in mats.items()}
    P = mats["P"][:, 0]
    has_heat = mats["Xh"].shape[1] > 0
    Xd = np.column_stack([mats["Xr"], mats["Xh"]])
    Fd = np.column_stack([mats["Fr"], mats["Xh"]])

    out = {}
    out["A"] = metrics(L, *loyo(index_fit(P, L), L))
    out["B"] = metrics(L, *loyo(copy_fit(mats["Xs"], P, L), L))
    out["C"] = metrics(L, *loyo(ridge_fit(mats["Xr"], L), L))
    out["C2"] = metrics(L, *loyo(ridge_fit(mats["Fr"], L), L))
    out["D"] = metrics(L, *loyo(ridge_fit(Xd, L), L)) if has_heat else dict(out["C"])
    out["D2"] = metrics(L, *loyo(ridge_fit(Fd, L), L)) if has_heat else dict(out["C2"])
    out["E"] = metrics(L, *loyo(ridge_fit(mats["Xe"], L), L))
    out["E2"] = metrics(L, *loyo(ridge_fit(mats["Fe"], L), L))
    L_ins = np.minimum(L, 1 - INS_COVERAGE)
    out["A_ins"] = metrics(L_ins, *loyo(index_fit(P, L_ins), L_ins))
    out["D2_ins"] = metrics(L_ins, *loyo(ridge_fit(Fd, L_ins), L_ins))
    out["E2_ins"] = metrics(L_ins, *loyo(ridge_fit(mats["Fe"], L_ins), L_ins))

    rev = trend_at(coef, mid, 2025) * CROPS[crop]["price"]
    base = {k: s[k] for k in ("crop", "practice", "geoid", "usps", "county", "station", "dist_mi",
                              "heat_station", "heat_dist_mi", "acres_recent")}
    base.update(has_heat=bool(has_heat), n_years=int(len(years)), first_year=int(years.min()),
                last_year=int(years.max()), trend_yield_2025=float(trend_at(coef, mid, 2025)),
                revenue_per_acre=float(rev), worst_year=int(years[np.argmax(L)]), worst_loss=float(L.max()))
    rows = [dict(base, strategy=k, **v) for k, v in out.items()]

    leg_rows = (ticket_rows(base, "D2" if has_heat else "C2", Fd, L, feats["Fr"] + feats["Fh"], rev)
                + ticket_rows(base, "E2", mats["Fe"], L, feats["Fe"], rev))

    def tot(series, months):
        return np.nansum([monthly_lookup(series, years, o, m) for o, m in months], axis=0)
    st_tot, co_tot = tot(rain, season["rain"]), tot(pcp, season["rain"])
    main_heat = monthly_lookup(tmax, years, *season["heat"][len(season["heat"]) // 2])
    diag = dict(base, corr_station_season_rain=float(np.corrcoef(-L, st_tot)[0, 1]),
                corr_county_season_rain=float(np.corrcoef(-L, co_tot)[0, 1]),
                corr_station_vs_county_rain=float(np.corrcoef(st_tot, co_tot)[0, 1]),
                corr_county_peak_tmax=float(np.corrcoef(-L, main_heat)[0, 1]),
                corr_station_hotdays=(float(np.corrcoef(-L, mats["Xh"][:, len(season["heat"]) // 2])[0, 1])
                                      if has_heat else np.nan))
    yr = pd.DataFrame({"crop": crop, "geoid": s["geoid"], "year": years, "L": L, "index_payout": P})
    return rows, leg_rows, diag, yr




def _run_one(args):
    s, = args
    yl, _, hd, sr = _load_inputs()
    t = time.time()
    res = study_site(s, yl, hd, sr)
    print(f"{s['crop']:13s} {s['county']:28s} {s['station']} {time.time() - t:5.1f}s", flush=True)
    return res


def run_study(workers: int = 8, only_crops=None):
    from concurrent.futures import ProcessPoolExecutor
    _, sites, _, _ = _load_inputs()
    if only_crops:
        sites = sites[sites["crop"].isin(only_crops)]
    jobs = [(s,) for s in sites.to_dict("records")]
    with ProcessPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(_run_one, jobs))
    rows = [r for res in results for r in res[0]]
    legs = [r for res in results for r in res[1]]
    diags = [res[2] for res in results]
    yrs = pd.concat([res[3] for res in results], ignore_index=True)
    pd.DataFrame(rows).to_csv(PROCESSED / "m2_income_hedge_sites.csv", index=False)
    pd.DataFrame(legs).to_csv(PROCESSED / "m2_income_hedge_legs.csv", index=False)
    pd.DataFrame(diags).to_csv(PROCESSED / "m2_income_hedge_drivers.csv", index=False)
    yrs.to_csv(PROCESSED / "m2_income_hedge_years.csv", index=False)


# ---------------------------------------------------------------------------------------------
# tables
# ---------------------------------------------------------------------------------------------

DOC = Path(__file__).resolve().parents[1] / "docs" / "analysis" / "25_income_hedge.md"
CROP_ORDER = ["corn", "soybeans", "winter wheat", "cotton", "sorghum"]
REGION = {**{k: "Plains and Texas" for k in ("OKC", "DEN", "DFW", "AUS", "SAT", "CLL", "HOU")},
          **{k: "Corn Belt and Lakes" for k in ("ORD", "IND", "CMH", "STL", "MSP", "MKE", "DTW", "SGF", "LEX")},
          **{k: "Mid-Atlantic" for k in ("PHL", "TTN", "DCA", "PIT", "EWR")}}
STRAT_NAME = {"A": "A: index insurance on county rain", "B": "B: Kalshi copies the index",
              "C": "C: station rain, free ladder", "C2": "C2: station rain, per-inch",
              "D": "D: station rain + heat, free", "D2": "D2: station rain + heat, per-inch",
              "E": "E: county contracts, free", "E2": "E2: county contracts, per-inch"}


def _md(df: pd.DataFrame, fmt: str = "{:.2f}") -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(str(c) for c in cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            if isinstance(v, (float, np.floating)):
                cells.append("" if np.isnan(v) else fmt.format(v))
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def tables() -> str:
    from raincheck.docs_util import write_auto_block
    r = pd.read_csv(PROCESSED / "m2_income_hedge_sites.csv", dtype={"geoid": str})
    legs = pd.read_csv(PROCESSED / "m2_income_hedge_legs.csv", dtype={"geoid": str})
    drv = pd.read_csv(PROCESSED / "m2_income_hedge_drivers.csv", dtype={"geoid": str})
    piv = r.pivot_table(index=["crop", "geoid"], columns="strategy", values="he").reset_index()
    site = r[r["strategy"] == "A"].set_index(["crop", "geoid"])
    piv = piv.merge(site[["has_heat", "dist_mi", "county", "usps", "station"]].reset_index(), on=["crop", "geoid"])
    out = []

    # 1. headline: median out-of-sample income HE by crop and strategy
    t = []
    for crop in CROP_ORDER + ["all"]:
        p = piv if crop == "all" else piv[piv["crop"] == crop]
        h = p[p["has_heat"]]
        t.append({"Crop": crop, "Sites": len(p), "A": p["A"].median(), "B": p["B"].median(),
                  "C": p["C"].median(), "C2": p["C2"].median(),
                  "D2 (heat sites)": h["D2"].median() if len(h) else np.nan,
                  "C2 same sites": h["C2"].median() if len(h) else np.nan,
                  "Heat sites": len(h), "E": p["E"].median(), "E2": p["E2"].median()})
    out.append("### 1. How much of the farm's income swing each design removes (median income HE, unseen years)\n\n"
               "Income HE = 1 - Var(L - hedge) / Var(L), L = revenue shortfall per $1 of expected revenue; each year "
               "scored with a fit that never saw it. A-E as in Method. D2 is shown only where Kalshi lists a daily-high "
               "market within 60 miles, next to C2 on the same sites.\n\n" + _md(pd.DataFrame(t)))

    # 2. head to head
    t = []
    for crop in CROP_ORDER + ["all"]:
        p = piv if crop == "all" else piv[piv["crop"] == crop]
        best_k = p[["C2", "D2"]].max(axis=1)
        t.append({"Crop": crop, "Sites": len(p),
                  "best tradable (C2/D2) beats copying (B)": f"{int((best_k > p['B']).sum())} of {len(p)}",
                  "median gain over B": float((best_k - p["B"]).median()),
                  "heat helps (D2 > C2), heat sites": f"{int((p['D2'] > p['C2'] + 1e-9)[p['has_heat']].sum())} of {int(p['has_heat'].sum())}",
                  "per-inch beats free (C2 > C)": f"{int((p['C2'] > p['C']).sum())} of {len(p)}",
                  "county per-inch beats index (E2 > A)": f"{int((p['E2'] > p['A']).sum())} of {len(p)}",
                  "median E2 - A": float((p["E2"] - p["A"]).median())})
    out.append("### 2. Head to head, site by site\n\n" + _md(pd.DataFrame(t)))

    # 2b. by region
    piv["region"] = piv["station"].map(REGION).fillna("other")
    t = []
    for (crop, reg), p in piv.groupby(["crop", "region"]):
        h = p[p["has_heat"]]
        t.append({"Crop": crop, "Region": reg, "Sites": len(p), "A": p["A"].median(), "B": p["B"].median(),
                  "best tradable (C2/D2)": p[["C2", "D2"]].max(axis=1).median(),
                  "D2 (heat sites)": h["D2"].median() if len(h) else np.nan, "Heat sites": len(h),
                  "E2": p["E2"].median()})
    t = pd.DataFrame(t)
    t["o"] = t["Crop"].map({c: i for i, c in enumerate(CROP_ORDER)})
    out.append("### 2b. By region (median income HE)\n\n" + _md(t.sort_values(["o", "Region"]).drop(columns="o")))

    # 3. tails, cost and value to a risk-averse farmer
    t = []
    for crop in CROP_ORDER + ["all"]:
        rr = r if crop == "all" else r[r["crop"] == crop]
        for k in ("A", "B", "D2", "E2"):
            q = rr[rr["strategy"] == k]
            t.append({"Crop": crop, "Design": STRAT_NAME[k], "income HE": q["he"].median(),
                      "worst-5-year recovery": q["tail5"].median(),
                      "premium, % of revenue": 100 * q["premium"].median(),
                      "CE gain at 12% load, variance size, % rev": 100 * q["ce_gain_load"].median(),
                      "utility size: buys in % of years": 100 * q["opt_buy_share"].median(),
                      "utility size: premium % rev": 100 * q["opt_premium"].median(),
                      "CE gain at 12% load, utility size, % rev": 100 * q["ce_gain_opt"].median(),
                      "thin margin: buys in % of years": 100 * q["thin_buy_share"].median(),
                      "thin margin: CE gain, % rev": 100 * q["ce_gain_thin"].median()})
    out.append("### 3. Bad years, cost, and what a risk-averse farmer gains (medians)\n\n"
               "Worst-5-year recovery = held-out payout in the 5 worst years / shortfall in those years. CE gain = "
               "certainty-equivalent income with the hedge minus without, CRRA risk aversion 2, wealth buffer of one "
               "year's revenue, premium = 1.12 x the expected payout (doc 14 central Kalshi cost). 'Utility size' "
               "scales each hedge (0 to 1.5 x) to maximise the farmer's CE on the training years. 'Thin margin' repeats "
               "it with a wealth buffer of 0.4 x revenue.\n\n"
               + _md(pd.DataFrame(t), "{:.2f}"))

    # 4. on top of crop insurance
    t = []
    for crop in CROP_ORDER + ["all"]:
        rr = r if crop == "all" else r[r["crop"] == crop]
        row = {"Crop": crop}
        for k in ("A_ins", "D2_ins", "E2_ins"):
            q = rr[rr["strategy"] == k]
            row[f"{k[:-4]} HE on what insurance leaves"] = q["he"].median()
            row[f"{k[:-4]} CE gain utility size, % rev"] = 100 * q["ce_gain_opt"].median()
        row["sd of shortfall, no insurance"] = 100 * rr[rr["strategy"] == "A"]["sd_before"].median()
        row["sd left by 75% yield insurance"] = 100 * rr[rr["strategy"] == "A_ins"]["sd_before"].median()
        t.append(row)
    out.append("### 4. As a top-up to 75% yield insurance (county-yield proxy)\n\n"
               "Target = min(L, 0.25): what a 75% yield-protection policy leaves the farmer (the deductible layer). "
               "sd in % of expected revenue.\n\n" + _md(pd.DataFrame(t)))

    # 5. drivers
    t = []
    for crop in CROP_ORDER:
        d = drv[drv["crop"] == crop]
        t.append({"Crop": crop, "yield vs station season rain": d["corr_station_season_rain"].median(),
                  "yield vs county season rain": d["corr_county_season_rain"].median(),
                  "station vs county rain": d["corr_station_vs_county_rain"].median(),
                  "yield vs county peak-month daily high": d["corr_county_peak_tmax"].median(),
                  "yield vs station hot days (heat sites)": d["corr_station_hotdays"].median()})
    out.append("### 5. What moves yields (median correlation with the yield, over sites)\n\n"
               "Season = the crop's rain months (Method). Positive = more of it, higher yield.\n\n" + _md(pd.DataFrame(t)))

    # 6. distance
    piv["band"] = pd.cut(piv["dist_mi"], [0, 30, 45, 60], labels=["0-30 mi", "30-45 mi", "45-60 mi"])
    t = []
    for b, p in piv.groupby("band", observed=True):
        t.append({"County to rain station": str(b), "Sites": len(p), "A": p["A"].median(), "B": p["B"].median(),
                  "C2": p["C2"].median(), "D2": p["D2"].median(), "E2": p["E2"].median()})
    out.append("### 6. By distance to the rain station (median income HE, all crops)\n\n" + _md(pd.DataFrame(t)))

    # 7. example tickets
    blocks = []
    for crop in CROP_ORDER:
        p = piv[piv["crop"] == crop].copy()
        p["best"] = p[["C2", "D2"]].max(axis=1)
        top = p.sort_values("best", ascending=False).iloc[0]
        strat = "D2" if top["has_heat"] else "C2"
        lg = legs[(legs["crop"] == crop) & (legs["geoid"] == top["geoid"]) & (legs["strategy"] == strat)]
        meta = r[(r["crop"] == crop) & (r["geoid"] == top["geoid"]) & (r["strategy"] == strat)].iloc[0]
        tab = lg[["feature", "dollars_per_acre_per_unit", "contracts_per_1000_acres", "expected_payout_share"]].copy()
        tab["expected_payout_share"] = tab["expected_payout_share"] * meta["revenue_per_acre"]
        tab.columns = ["Pays", "$ per acre per unit", "contracts per 1,000 acres", "expected payout $/acre"]
        blocks.append(f"**{crop.capitalize()}, {top['county']}, {top['usps']} (station {top['station']}, "
                      f"{top['dist_mi']:.0f} mi; {strat}).** Income HE {top[strat]:.2f} on unseen years vs "
                      f"{top['B']:.2f} for copying the index; expected revenue ${meta['revenue_per_acre']:,.0f}/acre; "
                      f"fair premium ${meta['premium'] * meta['revenue_per_acre']:,.0f}/acre; contracts "
                      f"{lg['contracts_per_1000_acres'].sum():,.0f} per 1,000 acres.\n\n"
                      + _md(tab, "{:,.2f}"))
    out.append("### 7. What the contract looks like: the best tradable site per crop (fit on all years)\n\n"
               + "\n\n".join(blocks))

    # 8. sites
    s = r[r["strategy"] == "D2"][["crop", "county", "usps", "station", "dist_mi", "heat_station", "n_years",
                                   "acres_recent", "revenue_per_acre", "sd_before", "worst_year", "worst_loss"]].copy()
    s["sd_before"], s["worst_loss"] = 100 * s["sd_before"], 100 * s["worst_loss"]
    s = s.sort_values(["crop", "station", "county"])
    s.columns = ["Crop", "County", "St", "Rain station", "mi", "Heat station", "Years", "Harvested acres (2006+ mean)",
                 "Revenue $/acre", "sd of shortfall %", "Worst year", "Worst shortfall %"]
    out.append("### 8. The sites\n\n" + _md(s, "{:,.0f}"))

    block = "\n\n".join(out)
    write_auto_block(DOC, "income hedge tables (scripts/run_income_hedge.py)", block)
    return block


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pull", action="store_true")
    ap.add_argument("--tables-only", action="store_true")
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args(argv)
    if not a.tables_only:
        if not (RAW_INC / "hot_days.csv").exists() or a.pull:
            pull_all()
        if a.pull:
            return 0
        run_study(a.workers)
    tables()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
