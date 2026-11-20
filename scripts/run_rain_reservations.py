"""Expansion study: how rain changes restaurant seated diners (OpenTable), and what that costs a restaurant.

Data (two samples; the live one is primary)
  live_2025_26 (PRIMARY): OpenTable "State of the Industry" dashboard, 46 US cities, daily 2025-09-01 to
  2026-11-17, dailyYoY = % change in seated diners from ONLINE reservations (methodology since June 2024)
  vs the same day of the same week a year earlier (t-364). Saved by hand on 2026-11-19 to
  data/raw/opentable/opentable_soti_20261119.json (the endpoint blocks scripts; never refetched here).
  dbnomics_2020_23 (secondary): the same OpenTable series (online, phone and walk-in) mirrored on DB.nomics
  (dataset OpenTable/SRI, 145 series; 46 US cities plus the NYC "yoy_open" variant), daily 2020-02-18 to
  2023-02-10, cached at data/raw/opentable/all_series_obs.json. Comparison day moves by year (part A).
  Daily rain (pcpn) and max temperature (maxt), 1991-2025 and 2024-01 to 2026-11, from ACIS StnData for each
  city's main airport (ICAO sid, e.g. "KATL 5"), cached under data/raw/stations/acis_reservations/.
  Hourly precipitation (ASOS p01i, local time) 2018-12-25 to 2023-02-15 and 2024-08-25 to 2026-11-18 from the
  Iowa Environmental Mesonet,
  cached under data/raw/stations/iem_asos_reservations/; gives rain during dinner (hourly buckets ending
  17:xx-20:xx local, i.e. about 4:50-8:50 pm).

Model
  y = log(1 + value/100) = log D_t - log D_base. The comparison day is checked from the data (part A,
  rain_reservations_base_test.csv: rain on the true base day raises y): live -> t-364; DB.nomics -> t-364
  in 2020, t-728 in 2021, t-1092 in 2022 and Jan-Feb 2023. Regressions of y on rain at t and rain on the
  base day, with max-temperature bins at both and holidays (at t or base) dropped. Fixed effects: city x
  month + city x weekday x year (live); city x week + city x weekday x year (DB.nomics, to absorb COVID
  reopening); each is also run with the other. Standard errors: two-way clustered by date and city, or
  date-clustered when that is larger (always for per-city terms); se_date and se_city are also reported.
  The rain-at-t coefficient is the effect in the reservation year; minus the base-day coefficient is the
  effect in the comparison year; "combined" is their GLS average. effect_pct = 100 (exp(b) - 1).
  The monthly loss distribution applies the primary sample's combined rain-bin x season effects to each
  city's 1991-2025 daily airport rain (see loss_distribution()).

Outputs (data/processed/):
  rain_reservations_effects.csv     one row per (sample, spec, group, era): effect, SEs, CI, n; spec=dollars
                                    converts effects to $ per rainy day
  rain_reservations_city_month_loss.csv  monthly loss distribution by city x calendar month, 1991-2025
  rain_reservations_base_test.csv   part A: base-day rain coefficient by year x candidate lag
Figure: docs/figures/rain_reservations_effects.png

Usage: python scripts/run_rain_reservations.py [--offline]   (about 1 minute once cached; first run ~100 requests)
"""
from __future__ import annotations

import json
import sys
import time
import warnings

import matplotlib
import numpy as np
import pandas as pd
import requests

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from agri_hedge.config import FIGURES, PROCESSED, RAW  # noqa: E402
from agri_hedge.stations import ACIS_URL, RAW_STATIONS, _cached_json, _request_json  # noqa: E402

DBNOMICS_URL = "https://api.db.nomics.world/v22/series/OpenTable/SRI?observations=1&limit=1000"
IEM_ASOS_URL = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"
OT_CACHE = RAW / "opentable" / "all_series_obs.json"
LIVE_CACHE = RAW / "opentable" / "opentable_soti_20261119.json"
ACIS_CACHE = RAW_STATIONS / "acis_reservations"
IEM_CACHE = RAW_STATIONS / "iem_asos_reservations"
CLIMO = (1991, 2025)
HOURLY = ("2018-12-25", "2023-02-15")      # DB.nomics sample (2020-23) and its 2019 comparison days
LIVE_DAILY = ("2024-01-01", "2026-11-18")  # live sample (2025-09 .. 2026-11) and its t-364 comparison days
LIVE_HOURLY = ("2024-08-25", "2026-11-18")
DINNER_END_HOURS = (17, 18, 19, 20)   # hourly buckets ending at these local hours -> rain from ~4:50 to ~8:50 pm
SAMPLE_START = "2020-07-01"           # after the spring-2020 closures; robustness runs from 2020-03-01
MIN_VALUE = -85.0                     # drop city-days with < 15% of base diners (log transform unstable)
WET = 0.10                            # a "rainy day": >= 0.10 in at the airport
RAIN_BINS = [(0.01, 0.10, "r_lt010"), (0.10, 0.50, "r_010_050"), (0.50, 99.0, "r_ge050")]
TEMP_EDGES = [-99, 32, 45, 55, 65, 75, 85, 95, 199]   # maxt bins (F); 65-75 is the reference
TEMP_REF = "t65_75"
WARM_MONTHS = (5, 6, 7, 8, 9, 10)
WEEKEND = (4, 5, 6)                   # Fri-Sun
BASE_LAG_CANDIDATES = (364, 728, 1092, 1456)
FE_TOL, FE_MAXIT = 1e-10, 500

# Dollars. Sales per full-service establishment (NAICS 722511): central $1.80M/yr = BLS sectoral output 2023
# ($475.1B, FRED IPUTN722511T300000000) / QCEW 2024 establishments (264,208), the same central value as
# data/processed/demand_inputs.csv ("Full-service sales per establishment", low 1.0, high 2.3). Cross-checks:
# Census monthly retail trade full-service sales summed over 2019 = $314.2B (FRED SM722511USN); receipts
# $381.8B / 257,282 establishments = $1.48M (Economic Census figures via data.mewayz.com, year unstated).
# OpenTable restaurants skew larger and more upscale, so $/day is also reported per $1M of annual sales.
ANNUAL_SALES_USD = 1.80e6
OPEN_DAYS = 360

# city series -> (label, airport, IEM id, tz, region). Airports are the city's main first-order station;
# where Kalshi lists a city rain market the same station is used (NYC = Central Park, HOU = Hobby).
CITIES = {
    "atlanta": ("Atlanta", "ATL", "America/New_York", "southeast"),
    "austin": ("Austin", "AUS", "America/Chicago", "texas_sw"),
    "baltimore": ("Baltimore", "BWI", "America/New_York", "northeast"),
    "beverly_hills": ("Beverly Hills", "LAX", "America/Los_Angeles", "west_coast"),
    "boca_raton": ("Boca Raton", "FLL", "America/New_York", "southeast"),
    "boston": ("Boston", "BOS", "America/New_York", "northeast"),
    "brooklyn": ("Brooklyn", "JFK", "America/New_York", "northeast"),
    "cambridge_us": ("Cambridge", "BOS", "America/New_York", "northeast"),
    "charlotte": ("Charlotte", "CLT", "America/New_York", "southeast"),
    "chicago": ("Chicago", "ORD", "America/Chicago", "midwest"),
    "cincinnati": ("Cincinnati", "CVG", "America/New_York", "midwest"),
    "cleveland": ("Cleveland", "CLE", "America/New_York", "midwest"),
    "columbus": ("Columbus", "CMH", "America/New_York", "midwest"),
    "dallas": ("Dallas", "DFW", "America/Chicago", "texas_sw"),
    "denver": ("Denver", "DEN", "America/Denver", "west_mtn"),
    "fort_lauderdale": ("Fort Lauderdale", "FLL", "America/New_York", "southeast"),
    "honolulu": ("Honolulu", "HNL", "Pacific/Honolulu", "west_coast"),
    "houston": ("Houston", "HOU", "America/Chicago", "texas_sw"),
    "indianapolis": ("Indianapolis", "IND", "America/Indiana/Indianapolis", "midwest"),
    "kansas_city": ("Kansas City", "MCI", "America/Chicago", "midwest"),
    "las_vegas": ("Las Vegas", "LAS", "America/Los_Angeles", "texas_sw"),
    "los_angeles": ("Los Angeles", "LAX", "America/Los_Angeles", "west_coast"),
    "louisville": ("Louisville", "SDF", "America/Kentucky/Louisville", "midwest"),
    "miami": ("Miami", "MIA", "America/New_York", "southeast"),
    "miami_beach": ("Miami Beach", "MIA", "America/New_York", "southeast"),
    "milwaukee": ("Milwaukee", "MKE", "America/Chicago", "midwest"),
    "minneapolis": ("Minneapolis", "MSP", "America/Chicago", "midwest"),
    "naples_us": ("Naples", "APF", "America/New_York", "southeast"),
    "nashville": ("Nashville", "BNA", "America/Chicago", "southeast"),
    "new_orleans": ("New Orleans", "MSY", "America/Chicago", "southeast"),
    "new_york": ("New York", "NYC", "America/New_York", "northeast"),
    "orlando": ("Orlando", "MCO", "America/New_York", "southeast"),
    "philadelphia": ("Philadelphia", "PHL", "America/New_York", "northeast"),
    "phoenix": ("Phoenix", "PHX", "America/Phoenix", "texas_sw"),
    "pittsburgh": ("Pittsburgh", "PIT", "America/New_York", "northeast"),
    "portland": ("Portland", "PDX", "America/Los_Angeles", "west_coast"),
    "raleigh": ("Raleigh", "RDU", "America/New_York", "southeast"),
    "san_antonio": ("San Antonio", "SAT", "America/Chicago", "texas_sw"),
    "san_diego": ("San Diego", "SAN", "America/Los_Angeles", "west_coast"),
    "san_francisco": ("San Francisco", "SFO", "America/Los_Angeles", "west_coast"),
    "scottsdale": ("Scottsdale", "SDL", "America/Phoenix", "texas_sw"),
    "seattle": ("Seattle", "SEA", "America/Los_Angeles", "west_coast"),
    "st_louis": ("St. Louis", "STL", "America/Chicago", "midwest"),
    "tampa": ("Tampa", "TPA", "America/New_York", "southeast"),
    "tucson": ("Tucson", "TUS", "America/Phoenix", "texas_sw"),
    "washington": ("Washington DC", "DCA", "America/New_York", "northeast"),
}
SUNBELT = {"southeast", "texas_sw"}               # regions; plus SUNBELT_EXTRA cities
SUNBELT_EXTRA = {"los_angeles", "beverly_hills", "san_diego", "honolulu"}
DUPLICATE_STATION_CITIES = {"beverly_hills", "cambridge_us", "miami_beach", "fort_lauderdale"}  # share an airport


def icao(code: str) -> str:
    return "PHNL" if code == "HNL" else f"K{code}"


# ---------------------------------------------------------------------------------------------
# data
# ---------------------------------------------------------------------------------------------
def load_opentable(offline: bool) -> pd.DataFrame:
    if offline and not OT_CACHE.exists():
        raise SystemExit(f"{OT_CACHE} missing; run once without --offline")
    data = _cached_json(OT_CACHE, lambda: _request_json("GET", DBNOMICS_URL))
    rows = []
    for doc in data["series"]["docs"]:
        area, loc, topic = doc["series_code"].split(".")
        if loc != "city" or area not in CITIES or topic not in ("yoy", "yoy_open"):
            continue
        rows.append(pd.DataFrame({"city": area, "topic": topic, "date": pd.to_datetime(doc["period"]),
                                  "value": pd.to_numeric(pd.Series(doc["value"]), errors="coerce")}))
    return pd.concat(rows, ignore_index=True)


LIVE_NAMES = {"Cambridge (US)": "cambridge_us", "Naples (US)": "naples_us"}


def load_live() -> pd.DataFrame:
    """OpenTable State of the Industry dashboard (online reservations only since June 2024), saved by hand
    on 2026-11-19 (the endpoint blocks scripts): dailyYoY = % change vs the same day of the same week a
    year earlier. Returns the same long format as load_opentable(), topic 'live'."""
    if not LIVE_CACHE.exists():
        print(f"  {LIVE_CACHE} not found: live sample skipped")
        return pd.DataFrame(columns=["city", "topic", "date", "value"])
    sd = json.loads(LIVE_CACHE.read_text(encoding="utf-8"))["seatedDiners"]
    dates = pd.to_datetime(sd["dailyHeaders"])
    rows = []
    for c in sd["cities"]:
        if c.get("country") != "United States":
            continue
        key = LIVE_NAMES.get(c["name"], c["name"].lower().replace(".", "").replace(" ", "_"))
        if key not in CITIES:
            print(f"  live city {c['name']} has no station mapping; skipped")
            continue
        rows.append(pd.DataFrame({"city": key, "topic": "live", "date": dates,
                                  "value": pd.to_numeric(pd.Series(c["dailyYoY"]), errors="coerce")}))
    return pd.concat(rows, ignore_index=True)


def _acis_num(raw) -> float:
    s = str(raw).strip()
    if s in ("", "M"):
        return np.nan
    if s in ("T", "S"):
        return 0.0
    s = s.rstrip("A")
    try:
        return float(s)
    except ValueError:
        return np.nan


def fetch_daily(code: str, offline: bool, sdate: str = f"{CLIMO[0]}-01-01",
                edate: str = f"{CLIMO[1]}-12-31") -> pd.DataFrame | None:
    cache = ACIS_CACHE / f"stndata_{icao(code)}_{sdate}_{edate}_pcpn_maxt.json"
    if offline and not cache.exists():
        return None
    payload = {"sid": f"{icao(code)} 5", "sdate": sdate, "edate": edate, "meta": "name,sids",
               "elems": [{"name": "pcpn"}, {"name": "maxt"}]}
    try:
        data = _cached_json(cache, lambda: _request_json("POST", f"{ACIS_URL}/StnData", payload=payload))
    except Exception as e:  # noqa: BLE001 - a failed station is reported and skipped
        print(f"  ACIS fetch failed for {code}: {e}")
        return None
    rows = data.get("data", []) if isinstance(data, dict) else []
    if not rows:
        return None
    df = pd.DataFrame(rows, columns=["date", "pcpn", "maxt"])
    df["date"] = pd.to_datetime(df["date"])
    df["pcpn"] = df["pcpn"].map(_acis_num)
    df["maxt"] = df["maxt"].map(_acis_num)
    df["station"] = code
    return df


def fetch_hourly(code: str, tz: str, offline: bool, span: tuple[str, str] = HOURLY) -> pd.DataFrame | None:
    """ASOS routine + special reports, local time. Returns per-day dinner and total rain from p01i."""
    cache = IEM_CACHE / f"asos_{code}_{span[0]}_{span[1]}_p01i.csv"
    if not cache.exists():
        if offline:
            return None
        y1, m1, d1 = span[0].split("-")
        y2, m2, d2 = span[1].split("-")
        params = {"station": icao(code) if code == "HNL" else code, "data": "p01i", "year1": y1, "month1": int(m1), "day1": int(d1),
                  "year2": y2, "month2": int(m2), "day2": int(d2), "tz": tz, "format": "onlycomma",
                  "latlon": "no", "missing": "M", "trace": "T", "direct": "no", "report_type": [3, 4]}
        for attempt in range(4):
            try:
                r = requests.get(IEM_ASOS_URL, params=params, timeout=300,
                                 headers={"User-Agent": "agri-hedge ECE473 research"})
                r.raise_for_status()
                if not r.text.startswith("station,valid"):
                    raise ValueError(r.text[:200])
                IEM_CACHE.mkdir(parents=True, exist_ok=True)
                cache.write_text(r.text, encoding="utf-8")
                break
            except (requests.RequestException, ValueError) as e:
                if attempt == 3:
                    print(f"  IEM fetch failed for {code}: {e}")
                    return None
                time.sleep(5 * (attempt + 1))
        time.sleep(1.0)
    return hourly_to_daily(pd.read_csv(cache, dtype=str))


def hourly_to_daily(h: pd.DataFrame) -> pd.DataFrame:
    """p01i accumulates since the last routine (:5x) report, so each hour's rain = max p01i over the reports
    in the bucket ending at that routine report. Day totals and the dinner window are sums of hour buckets."""
    h = h[h["p01i"].notna()].copy()
    h["p01i"] = h["p01i"].where(h["p01i"] != "M")
    h["valid"] = pd.to_datetime(h["valid"])
    h["p"] = h["p01i"].replace({"T": "0", "M": np.nan}).astype(float)
    h = h[h["p"].notna()]
    if h.empty:
        return pd.DataFrame(columns=["date", "hr_total", "dinner_rain"])
    routine_min = int(h["valid"].dt.minute.mode().iloc[0])
    end = h["valid"].dt.floor("h") + pd.Timedelta(minutes=routine_min)
    end = end.where(h["valid"].dt.minute <= routine_min, end + pd.Timedelta(hours=1))
    h["end"] = end
    b = h.groupby("end")["p"].max().reset_index()
    b["date"] = b["end"].dt.normalize()
    b["hour"] = b["end"].dt.hour
    b["dinner"] = b["hour"].isin(DINNER_END_HOURS)
    g = b.groupby("date")
    out = pd.DataFrame({"hr_total": g["p"].sum(min_count=1), "hr_n": g["p"].count(),
                        "dinner_rain": b[b["dinner"]].groupby("date")["p"].sum(min_count=1),
                        "dinner_n": b[b["dinner"]].groupby("date")["p"].count()}).reset_index()
    # require all four dinner buckets and >= 20 of 24 buckets reported
    out.loc[out["dinner_n"] < len(DINNER_END_HOURS), "dinner_rain"] = np.nan
    out.loc[out["hr_n"] < 20, "hr_total"] = np.nan
    return out[["date", "hr_total", "dinner_rain"]]


# ---------------------------------------------------------------------------------------------
# holidays (dropped when they fall on the reservation day or its comparison day)
# ---------------------------------------------------------------------------------------------
def _nth_weekday(y, m, wd, n):
    d = pd.Timestamp(y, m, 1)
    d += pd.Timedelta(days=(wd - d.day_of_week) % 7)
    return d + pd.Timedelta(weeks=n - 1)


def _last_weekday(y, m, wd):
    d = pd.Timestamp(y, m, 1) + pd.offsets.MonthEnd(0)
    return d - pd.Timedelta(days=(d.day_of_week - wd) % 7)


EASTER = {2014: "04-20", 2024: "03-31", 2025: "04-20", 2026: "04-05", 2015: "04-05", 2016: "03-27", 2017: "04-16", 2018: "04-01", 2019: "04-21", 2020: "04-12",
          2021: "04-04", 2022: "04-17", 2023: "04-09"}


def holiday_dates(years) -> set:
    out = set()
    for y in years:
        th = _nth_weekday(y, 11, 3, 4)
        days = [pd.Timestamp(y, 1, 1), pd.Timestamp(y, 2, 14), pd.Timestamp(y, 7, 4), pd.Timestamp(y, 10, 31),
                pd.Timestamp(y, 12, 31), _nth_weekday(y, 1, 0, 3), _nth_weekday(y, 2, 0, 3),
                _nth_weekday(y, 2, 6, 1), _nth_weekday(y, 5, 6, 2), _nth_weekday(y, 6, 6, 3),
                _last_weekday(y, 5, 0), _nth_weekday(y, 9, 0, 1), th - pd.Timedelta(days=1), th,
                th + pd.Timedelta(days=1), pd.Timestamp(f"{y}-{EASTER[y]}"), pd.Timestamp(y, 3, 17)]
        days += list(pd.date_range(f"{y}-12-20", f"{y + 1}-01-03"))
        days += [pd.Timestamp(y, 2, 13), pd.Timestamp(y, 2, 15)]   # Valentine's spills over
        out.update(d.normalize() for d in days)
    return out


# ---------------------------------------------------------------------------------------------
# fixed-effects OLS with clustered standard errors
# ---------------------------------------------------------------------------------------------
def demean(mat: np.ndarray, groups: list[np.ndarray]) -> np.ndarray:
    m = mat.copy()
    for _ in range(FE_MAXIT):
        before = m.copy()
        for g in groups:
            cnt = np.bincount(g)
            sums = np.vstack([np.bincount(g, weights=m[:, j], minlength=len(cnt)) for j in range(m.shape[1])]).T
            m -= (sums / np.maximum(cnt, 1)[:, None])[g]
        if np.max(np.abs(m - before)) < FE_TOL:
            break
    return m


def _meat(xu: np.ndarray, cl: np.ndarray) -> tuple[np.ndarray, int]:
    codes, inv = np.unique(cl, return_inverse=True)
    s = np.zeros((len(codes), xu.shape[1]))
    np.add.at(s, inv, xu)
    g = len(codes)
    return (g / (g - 1)) * s.T @ s, g


def fe_ols(df: pd.DataFrame, y: str, xs: list[str], fes: list[list[str]],
           clusters=(("date",), ("city",))) -> dict:
    d = df.dropna(subset=[y] + xs).copy()
    xs = [x for x in xs if d[x].std() > 0]
    groups = [d.groupby(f, sort=False).ngroup().to_numpy() for f in fes]
    # drop singleton FE cells (no within variation)
    keep = np.ones(len(d), bool)
    for g in groups:
        keep &= np.bincount(g)[g] > 1
    d = d[keep]
    groups = [d.groupby(f, sort=False).ngroup().to_numpy() for f in fes]
    mat = demean(d[[y] + xs].to_numpy(float), groups)
    yy, X = mat[:, 0], mat[:, 1:]
    xtx_inv = np.linalg.pinv(X.T @ X)
    b = xtx_inv @ X.T @ yy
    u = yy - X @ b
    n, k = X.shape
    xu = X * u[:, None]
    adj = (n - 1) / (n - k)
    vs, ng = {}, {}
    for cl in clusters:
        key = "_".join(cl)
        lab = d[list(cl)].astype(str).agg("|".join, axis=1).to_numpy()
        meat, g = _meat(xu, lab)
        vs[key], ng[key] = adj * xtx_inv @ meat @ xtx_inv, g
    if ("date",) in clusters and ("city",) in clusters:
        lab = (d["date"].astype(str) + "|" + d["city"]).to_numpy()
        meat_i, _ = _meat(xu, lab)
        v2 = vs["date"] + vs["city"] - adj * xtx_inv @ meat_i @ xtx_inv
        ev, evec = np.linalg.eigh(v2)
        vs["twoway"] = evec @ np.diag(np.maximum(ev, 0)) @ evec.T
    return {"b": pd.Series(b, xs), "V": {k_: pd.DataFrame(v, xs, xs) for k_, v in vs.items()}, "n": n,
            "n_cities": d["city"].nunique(), "n_dates": d["date"].nunique(), "n_clusters": ng,
            "y_sd": float(d[y].std())}


def vcov(res: dict, names: list[str]) -> np.ndarray:
    """Reported covariance: two-way (date, city) clustered, but never below date-clustered. Terms that vary
    within one city only (per-city effects) have a degenerate city-cluster score, so date clustering binds."""
    vt = res["V"]["twoway"].loc[names, names].to_numpy()
    if "date" not in res["V"]:
        return vt
    vd = res["V"]["date"].loc[names, names].to_numpy()
    return vt if np.trace(vt) >= np.trace(vd) else vd


def lincom(res: dict, w: dict) -> tuple[float, float]:
    names = [k for k in w if k in res["b"].index]
    wv = np.array([w[k] for k in names])
    est = float(wv @ res["b"][names].to_numpy())
    v = vcov(res, names)
    return est, float(np.sqrt(max(wv @ v @ wv, 0.0)))


# ---------------------------------------------------------------------------------------------
# panel
# ---------------------------------------------------------------------------------------------
def temp_bin_names() -> list[str]:
    lo = TEMP_EDGES[:-1]
    hi = TEMP_EDGES[1:]
    return [("tlt32" if a == -99 else "tge95" if b == 199 else f"t{a}_{b}") for a, b in zip(lo, hi)]


def weather_frame(daily: dict, hourly: dict) -> pd.DataFrame:
    parts = []
    for code, d in daily.items():
        w = d.set_index("date")[["pcpn", "maxt"]]
        h = hourly.get(code)
        if h is not None and len(h):
            w = w.join(h.set_index("date")[["hr_total", "dinner_rain"]], how="left")
        else:
            w["hr_total"], w["dinner_rain"] = np.nan, np.nan
        w["station"] = code
        parts.append(w.reset_index())
    return pd.concat(parts, ignore_index=True)


def add_weather(p: pd.DataFrame, wx: pd.DataFrame, lag_col: str | None, suffix: str, shift_days: int = 0):
    """Merge station weather for date - (lag) - shift_days onto panel rows, with columns suffixed."""
    key = p["date"] - pd.to_timedelta(p[lag_col] if lag_col else 0, unit="D") - pd.Timedelta(days=shift_days)
    m = pd.DataFrame({"station": p["station"].to_numpy(), "date": key.to_numpy()})
    m = m.merge(wx, on=["station", "date"], how="left")
    out = {}
    pc, tx = m["pcpn"].to_numpy(), m["maxt"].to_numpy()
    out[f"pcpn{suffix}"] = pc
    out[f"any{suffix}"] = np.where(np.isnan(pc), np.nan, (pc >= 0.01).astype(float))
    out[f"wet{suffix}"] = np.where(np.isnan(pc), np.nan, (pc >= WET).astype(float))
    for lo, hi, name in RAIN_BINS:
        out[f"{name}{suffix}"] = np.where(np.isnan(pc), np.nan, ((pc >= lo) & (pc < hi)).astype(float))
    names = temp_bin_names()
    idx = np.digitize(tx, TEMP_EDGES[1:-1], right=False)
    for i, nm in enumerate(names):
        out[f"{nm}{suffix}"] = np.where(np.isnan(tx), np.nan, (idx == i).astype(float))
    out[f"maxt{suffix}"] = tx
    dn, tot = m["dinner_rain"].to_numpy(), m["hr_total"].to_numpy()
    out[f"dinner_rain{suffix}"] = dn
    ok = ~np.isnan(dn) & ~np.isnan(tot)
    other = tot - dn
    out[f"dn_any{suffix}"] = np.where(ok, (dn >= 0.01).astype(float), np.nan)
    out[f"dn_lt010{suffix}"] = np.where(ok, ((dn >= 0.01) & (dn < 0.10)).astype(float), np.nan)
    out[f"dn_ge010{suffix}"] = np.where(ok, (dn >= 0.10).astype(float), np.nan)
    # rain outside dinner on a day with no dinner rain
    out[f"out_only_wet{suffix}"] = np.where(ok, ((dn < 0.01) & (other >= WET)).astype(float), np.nan)
    out[f"out_only_lt{suffix}"] = np.where(ok, ((dn < 0.01) & (other >= 0.01) & (other < WET)).astype(float), np.nan)
    out[f"hr_wet{suffix}"] = np.where(ok, (tot >= WET).astype(float), np.nan)
    return pd.DataFrame(out, index=p.index)


def build_panel(ot: pd.DataFrame, wx: pd.DataFrame, base_lag: dict, topic: str = "yoy",
                start: str = SAMPLE_START, min_value: float = MIN_VALUE, drop_holidays: bool = True) -> pd.DataFrame:
    p = ot[(ot["topic"] == topic) & ot["value"].notna()].copy()
    p = p[(p["date"] >= start) & (p["value"] > min_value)]
    p["station"] = p["city"].map(lambda c: CITIES[c][1])
    p["region"] = p["city"].map(lambda c: CITIES[c][3])
    p["year"] = p["date"].dt.year
    p["lag"] = p["year"].map(base_lag)
    p["base_date"] = p["date"] - pd.to_timedelta(p["lag"], unit="D")
    p["y"] = np.log1p(p["value"] / 100.0)
    if drop_holidays:
        hol = holiday_dates(range(2014, 2027))
        p = p[~p["date"].isin(hol) & ~p["base_date"].isin(hol)]
    p = p.reset_index(drop=True)
    p = pd.concat([p, add_weather(p, wx, None, "_t"), add_weather(p, wx, "lag", "_b")], axis=1)
    for k in range(1, 7):
        lagw = add_weather(p, wx, None, "", shift_days=k)
        p[f"wet_l{k}"] = lagw["wet"]
        p[f"wet_bl{k}"] = add_weather(p, wx, "lag", "", shift_days=k)["wet"]
    p["wet_f1"] = add_weather(p, wx, None, "", shift_days=-1)["wet"]
    p["dow"] = p["date"].dt.day_of_week
    p["month"] = p["date"].dt.month
    iso = p["date"].dt.isocalendar()
    p["week"] = iso["year"].astype(str) + "-" + iso["week"].astype(str)
    p["ym"] = p["date"].dt.to_period("M").astype(str)
    p["warm"] = p["month"].isin(WARM_MONTHS).astype(int)
    p["weekend"] = p["dow"].isin(WEEKEND).astype(int)
    p["sunbelt"] = (p["region"].isin(SUNBELT) | p["city"].isin(SUNBELT_EXTRA)).astype(int)
    p["period"] = p["year"].astype(str) + np.where(p["month"] <= 6, "H1", "H2")
    return p


def temp_terms(suffix: str) -> list[str]:
    return [f"{n}{suffix}" for n in temp_bin_names() if n != TEMP_REF]


FE_WEEK = [["city", "week"], ["city", "dow", "year"]]
FE_MONTH = [["city", "ym"], ["city", "dow", "year"]]
FE_NAME = {"week": "city x week + city x weekday x year", "month": "city x month + city x weekday x year"}

# Two samples. 'live' is primary: post-COVID, a single documented comparison day (t-364). 'dbnomics' is the
# 2020-23 COVID-era series whose comparison day moves (t-364 in 2020, t-728 in 2021, t-1092 from 2022),
# so it needs week fixed effects to absorb reopening dynamics.
SAMPLES = {
    "live_2025_26": {
        "label": "OpenTable dashboard, online reservations, 2025-09-01 to 2026-11-17, vs same day a year earlier",
        "topic": "live", "base_lag": {2025: 364, 2026: 364}, "start": "2025-09-01", "min_value": MIN_VALUE,
        "fe": "month", "candidates": (357, 364, 371, 728), "years_t": "2025-26", "years_b": "2024-25"},
    "dbnomics_2020_23": {
        "label": "OpenTable via DB.nomics, online+phone+walk-in, 2020-07-01 to 2023-02-10, vs 2019 (2023: early 2020)",
        "topic": "yoy", "base_lag": {2020: 364, 2021: 728, 2022: 1092, 2023: 1092}, "start": SAMPLE_START,
        "min_value": MIN_VALUE, "fe": "week", "candidates": (364, 728, 1092, 1456),
        "years_t": "2020-23", "years_b": "2019-20"},
}
PRIMARY, SECONDARY = "live_2025_26", "dbnomics_2020_23"
ERA_T = "reservation day (coef on rain at t)"
ERA_B = "comparison day (minus coef on rain at base day)"
ERA_C = "combined (GLS of both)"
Z95 = 1.959964


def fe_of(name: str):
    return FE_WEEK if name == "week" else FE_MONTH


def panel_for(ot, wx, skey, **kw) -> pd.DataFrame:
    s = SAMPLES[skey]
    args = {"topic": s["topic"], "start": s["start"], "min_value": s["min_value"]} | kw
    return build_panel(ot, wx, s["base_lag"], **args)


# ---------------------------------------------------------------------------------------------
# effects table helpers
# ---------------------------------------------------------------------------------------------
def _row(spec, group, term, era, est, se, res, extra=None) -> dict:
    r = {"spec": spec, "group": group, "term": term, "era": era, "effect_log": est, "se": se,
         "effect_pct": 100 * (np.exp(est) - 1), "ci95_lo_pct": 100 * (np.exp(est - Z95 * se) - 1),
         "ci95_hi_pct": 100 * (np.exp(est + Z95 * se) - 1), "t_stat": est / se if se > 0 else np.nan,
         "n": res["n"], "n_cities": res["n_cities"], "n_dates": res["n_dates"]}
    r.update(extra or {})
    return r


def _se_cols(res, term) -> dict:
    return {f"se_{k}": float(np.sqrt(v.loc[term, term])) for k, v in res["V"].items() if k in ("date", "city")}


def effect_rows(res, spec, pairs: dict, extra=None) -> list[dict]:
    """pairs: group -> (t_term, b_term). Rows for the reservation-day effect (coef on rain at t), the
    comparison-day effect (minus the coef on rain at the base day), and their GLS combination."""
    rows = []
    for group, (tt, bt) in pairs.items():
        ex = dict(extra or {})
        have_t, have_b = tt in res["b"].index, bt is not None and bt in res["b"].index
        if have_t:
            est, se = lincom(res, {tt: 1.0})
            rows.append(_row(spec, group, tt, ERA_T, est, se, res, ex | _se_cols(res, tt)))
        if have_b:
            est, se = lincom(res, {bt: -1.0})
            rows.append(_row(spec, group, bt, ERA_B, est, se, res, ex | _se_cols(res, bt)))
        if have_t and have_b:
            v = vcov(res, [tt, bt]) * np.array([[1, -1], [-1, 1]])
            b = np.array([res["b"][tt], -res["b"][bt]])
            vi = np.linalg.pinv(v)
            w = vi.sum(axis=1) / vi.sum()
            est, se = float(w @ b), float(np.sqrt(max(w @ v @ w, 0.0)))
            rows.append(_row(spec, group, f"{tt}|{bt}", ERA_C, est, se, res, ex | {"w_t": float(w[0])}))
    return rows


def interact(p: pd.DataFrame, var: str, by: str, levels) -> list[str]:
    names = []
    for lv in levels:
        nm = f"{var}__{by}_{lv}"
        p[nm] = p[var] * (p[by] == lv).astype(float)
        names.append(nm)
    return names


# ---------------------------------------------------------------------------------------------
# A. which comparison day?
# ---------------------------------------------------------------------------------------------
def base_test(ot, wx, skey) -> pd.DataFrame:
    s = SAMPLES[skey]
    p = panel_for(ot, wx, skey)
    for lag in s["candidates"]:
        p[f"wet_lag{lag}"] = add_weather(p, wx, None, "", shift_days=lag)["wet"]
    rows = []
    for yr in sorted(p["year"].unique()):
        d = p[p["year"] == yr]
        terms = ["wet_t"] + [f"wet_lag{lag}" for lag in s["candidates"]]
        r = fe_ols(d, "y", terms + temp_terms("_t"), fe_of(s["fe"]))
        for x in terms:
            lag = 0 if x == "wet_t" else int(x[7:])
            est, se = lincom(r, {x: 1.0})
            rows.append({"sample": skey, "year": yr, "term": x, "lag_days": lag,
                         "lag_year_mid": (d["date"].min() + (d["date"].max() - d["date"].min()) / 2
                                          - pd.Timedelta(days=lag)).year,
                         "coef": est, "se": se, "t_stat": est / se, "n": r["n"],
                         "chosen": lag > 0 and lag == s["base_lag"][yr]})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------------------------
# B-F. effects
# ---------------------------------------------------------------------------------------------
REBOUND_T = ["wet_t"] + [f"wet_l{k}" for k in range(1, 7)]
REBOUND_B = ["wet_b"] + [f"wet_bl{k}" for k in range(1, 7)]


def run_effects(ot, wx, skey) -> tuple[pd.DataFrame, pd.DataFrame]:
    s = SAMPLES[skey]
    p = panel_for(ot, wx, skey)
    FE, alt = fe_of(s["fe"]), ("week" if s["fe"] == "month" else "month")
    T = temp_terms("_t") + temp_terms("_b")
    bins_t = [f"{n}_t" for _, _, n in RAIN_BINS]
    bins_b = [f"{n}_b" for _, _, n in RAIN_BINS]
    rows: list[dict] = []
    tag = {"fe": FE_NAME[s["fe"]], "subsample": "main"}
    pair = {"rain >= 0.10 in": ("wet_t", "wet_b")}

    def add(xs, spec, pairs, d=None, fe=None, extra=None):
        r = fe_ols(p if d is None else d, "y", xs, FE if fe is None else fe)
        rows.extend(effect_rows(r, spec, pairs, tag | (extra or {})))
        return r

    # B. headline specs
    add(["wet_t", "wet_b"] + T, "wet010", pair)
    add(["any_t", "any_b"] + T, "any001", {"rain >= 0.01 in": ("any_t", "any_b")})
    add(bins_t + bins_b + T, "bins", {f"{lo:.2f}-{hi:.2f} in" if hi < 99 else f">= {lo:.2f} in": (f"{n}_t", f"{n}_b")
                                      for lo, hi, n in RAIN_BINS})
    for _, _, n in RAIN_BINS:   # bins x season (feeds the loss distribution)
        interact(p, f"{n}_t", "warm", (0, 1))
        interact(p, f"{n}_b", "warm", (0, 1))
    add([f"{n}_{x}__warm_{w}" for _, _, n in RAIN_BINS for x in "tb" for w in (0, 1)] + T, "bins_x_season",
        {f"{n} warm={w}": (f"{n}_t__warm_{w}", f"{n}_b__warm_{w}") for _, _, n in RAIN_BINS for w in (0, 1)})
    p["wet_diff"] = p["wet_t"] - p["wet_b"]   # restricted: equal and opposite effects at t and base
    add(["wet_diff"] + T, "wet010_restricted", {"rain >= 0.10 in (t minus base)": ("wet_diff", None)})

    # C. dinner-hour rain (hourly ASOS, buckets ending 17-20 local); categories are exclusive
    dn_t = ["dn_lt010_t", "dn_ge010_t", "out_only_lt_t", "out_only_wet_t"]
    add(dn_t + [x[:-2] + "_b" for x in dn_t] + T, "dinner",
        {"dinner rain 0.01-0.10 in": ("dn_lt010_t", "dn_lt010_b"),
         "dinner rain >= 0.10 in": ("dn_ge010_t", "dn_ge010_b"),
         "no dinner rain, other hours 0.01-0.10 in": ("out_only_lt_t", "out_only_lt_b"),
         "no dinner rain, other hours >= 0.10 in": ("out_only_wet_t", "out_only_wet_b")})
    add(["dn_any_t", "dn_any_b", "hr_wet_t", "hr_wet_b"] + T, "dinner_vs_day",
        {"any dinner rain (given daily total)": ("dn_any_t", "dn_any_b"),
         "daily >= 0.10 in (hourly total)": ("hr_wet_t", "hr_wet_b")})

    # D. rebound: 6 daily lags of rain; city x month FE so a shift within the week is not absorbed
    for fe in ("month", "week"):
        spec, ftag = f"rebound_{fe}", tag | {"fe": FE_NAME[fe]}
        r = fe_ols(p, "y", REBOUND_T + ["wet_f1"] + REBOUND_B + T, fe_of(fe))
        rows += effect_rows(r, spec, {f"rain {k} days earlier" if k else "same day":
                                      (REBOUND_T[k], REBOUND_B[k]) for k in range(7)}, ftag)
        rows += effect_rows(r, spec, {"rain tomorrow (lead)": ("wet_f1", None)}, ftag)
        est, se = lincom(r, {x: 1.0 for x in REBOUND_T})
        rows.append(_row(spec, "net 7-day (same day + 6 lags)", "+".join(REBOUND_T), ERA_T, est, se, r, ftag))
        est, se = lincom(r, {x: -1.0 for x in REBOUND_B})
        rows.append(_row(spec, "net 7-day (same day + 6 lags)", "+".join(REBOUND_B), ERA_B, est, se, r, ftag))

    # E. heterogeneity
    p["freeze"] = (p["maxt_t"] < 40).astype(int)
    p["freeze_b"] = (p["maxt_b"] < 40).astype(int)
    for by, levels, label in (("warm", (0, 1), {0: "Nov-Apr", 1: "May-Oct"}),
                              ("weekend", (0, 1), {0: "Mon-Thu", 1: "Fri-Sun"}),
                              ("sunbelt", (0, 1), {0: "not Sun Belt", 1: "Sun Belt"}),
                              ("region", sorted(p["region"].unique()), None),
                              ("period", sorted(p["period"].unique()), None)):
        xt, xb = interact(p, "wet_t", by, levels), interact(p, "wet_b", by, levels)
        add(xt + xb + T, f"by_{by}", {(label or {}).get(lv, str(lv)): (a, b) for lv, a, b in zip(levels, xt, xb)})
    p["wet_t_liquid"], p["wet_t_cold"] = p["wet_t"] * (1 - p["freeze"]), p["wet_t"] * p["freeze"]
    p["wet_b_liquid"], p["wet_b_cold"] = p["wet_b"] * (1 - p["freeze_b"]), p["wet_b"] * p["freeze_b"]
    add(["wet_t_liquid", "wet_t_cold", "wet_b_liquid", "wet_b_cold"] + T, "by_freezing",
        {"max temp >= 40F": ("wet_t_liquid", "wet_b_liquid"),
         "max temp < 40F (snow/ice likely)": ("wet_t_cold", "wet_b_cold")})
    xs, pairs = [], {}
    for w, wl in ((1, "May-Oct"), (0, "Nov-Apr")):
        for liq, ll in ((1, "max temp >= 40F"), (0, "max temp < 40F")):
            mt = ((p["warm"] == w) & ((1 - p["freeze"]) == liq)).astype(float)
            mb = ((p["warm"] == w) & ((1 - p["freeze_b"]) == liq)).astype(float)
            a, b = f"wet_t__w{w}l{liq}", f"wet_b__w{w}l{liq}"
            p[a], p[b] = p["wet_t"] * mt, p["wet_b"] * mb
            if p[a].sum() >= 30 and p[b].sum() >= 30:
                xs += [a, b]
                pairs[f"{wl}, {ll}"] = (a, b)
    add(xs + T, "by_season_x_freezing", pairs)
    cities = sorted(p["city"].unique())
    xt, xb = interact(p, "wet_t", "city", cities), interact(p, "wet_b", "city", cities)
    r = fe_ols(p, "y", xt + xb + T, FE)
    rows += shrink_city(effect_rows(r, "by_city", {c: (a, b) for c, a, b in zip(cities, xt, xb)}, tag))

    # F. robustness
    add(["wet_t", "wet_b"] + T, f"robust_city_{alt}_fe", pair, fe=fe_of(alt), extra={"fe": FE_NAME[alt]})
    add(["wet_t"] + temp_terms("_t"), "robust_no_base_controls", {"rain >= 0.10 in": ("wet_t", None)})
    add(["wet_t", "wet_b"] + T, "robust_unique_stations", pair, d=p[~p["city"].isin(DUPLICATE_STATION_CITIES)],
        extra={"subsample": "drop cities sharing an airport"})
    add(["wet_t", "wet_b"] + T, "robust_keep_holidays", pair, d=panel_for(ot, wx, skey, drop_holidays=False),
        extra={"subsample": "holidays kept"})
    if skey == PRIMARY:
        last = p["date"].max() - pd.Timedelta(days=365)
        add(["wet_t", "wet_b"] + T, "robust_last_12_months", pair, d=p[p["date"] > last],
            extra={"subsample": "last 365 days"})
    else:
        add(["wet_t", "wet_b"] + T, "robust_2022_23", pair, d=p[p["date"] >= "2022-01-01"],
            extra={"subsample": "2022-01 on"})
        add(["wet_t", "wet_b"] + T, "robust_drop_2023", pair, d=p[p["year"] < 2023],
            extra={"subsample": "2020-07 to 2022-12"})
        add(["wet_t", "wet_b"] + T, "robust_from_2020_03", pair,
            d=panel_for(ot, wx, skey, start="2020-03-01", min_value=-95.0),
            extra={"subsample": "2020-03 on, value > -95"})
        for topic in ("yoy", "yoy_open"):
            d = panel_for(ot[ot["city"] == "new_york"], wx, skey, topic=topic)
            r = fe_ols(d, "y", ["wet_t", "wet_b"] + T, FE_WEEK, clusters=(("date",), ("week",)))
            r["V"]["twoway"] = r["V"]["date"]
            rows += effect_rows(r, f"nyc_{topic}", pair,
                                tag | {"subsample": f"New York only, series {topic}; date-clustered SE"})
    eff = pd.DataFrame(rows)
    eff.insert(0, "sample", skey)
    eff["years_t"], eff["years_b"] = s["years_t"], s["years_b"]
    return eff, p


def shrink_city(rows: list[dict]) -> list[dict]:
    """Empirical-Bayes shrinkage of per-city effects toward the precision-weighted mean (per era)."""
    df = pd.DataFrame(rows)
    out = []
    for era, g in df.groupby("era", sort=False):
        w = 1 / g["se"] ** 2
        mu = float((w * g["effect_log"]).sum() / w.sum())
        tau2 = max(float(g["effect_log"].var() - (g["se"] ** 2).mean()), 0.0)
        k = tau2 / (tau2 + g["se"] ** 2) if tau2 > 0 else 0.0 * g["se"]
        g = g.assign(effect_log_shrunk=mu + k * (g["effect_log"] - mu), shrink_weight=k, tau_between=np.sqrt(tau2))
        g["effect_pct_shrunk"] = 100 * (np.exp(g["effect_log_shrunk"]) - 1)
        out.append(g)
    return pd.concat(out).to_dict("records")


# ---------------------------------------------------------------------------------------------
# G. dollars and the monthly loss distribution
# ---------------------------------------------------------------------------------------------
def _pick(eff, sample, spec, group, era=ERA_C) -> pd.Series:
    m = eff[(eff["sample"] == sample) & (eff["spec"] == spec) & (eff["group"] == group) & (eff["era"] == era)]
    if m.empty:
        raise KeyError((sample, spec, group, era))
    return m.iloc[0]


def rebound_ratio(eff, sample) -> float:
    """Net 7-day effect / same-day effect (city x month FE), averaged over the two eras, clipped to [0, 1]."""
    ratios = [_pick(eff, sample, "rebound_month", "net 7-day (same day + 6 lags)", era)["effect_log"]
              / _pick(eff, sample, "rebound_month", "same day", era)["effect_log"] for era in (ERA_T, ERA_B)]
    return float(np.clip(np.mean(ratios), 0.0, 1.0))


def dollar_rows(eff) -> list[dict]:
    rows = []
    day_usd = ANNUAL_SALES_USD / OPEN_DAYS
    for sample in eff["sample"].unique():
        for spec, group in (("wet010", "rain >= 0.10 in"), ("any001", "rain >= 0.01 in"),
                            ("bins", "0.01-0.10 in"), ("bins", "0.10-0.50 in"), ("bins", ">= 0.50 in"),
                            ("dinner", "dinner rain >= 0.10 in"),
                            ("dinner", "no dinner rain, other hours >= 0.10 in")):
            for era in (ERA_T, ERA_B, ERA_C):
                r = _pick(eff, sample, spec, group, era)
                rows.append({"sample": sample, "spec": "dollars", "group": f"{spec}: {group}", "term": r["term"],
                             "era": era, "effect_log": r["effect_log"], "se": r["se"],
                             "effect_pct": r["effect_pct"], "ci95_lo_pct": r["ci95_lo_pct"],
                             "ci95_hi_pct": r["ci95_hi_pct"],
                             "usd_per_day_per_1m_sales": -r["effect_pct"] / 100 * 1e6 / OPEN_DAYS,
                             "usd_per_day_typical": -r["effect_pct"] / 100 * day_usd,
                             "usd_per_day_typical_ci_lo": -r["ci95_hi_pct"] / 100 * day_usd,
                             "usd_per_day_typical_ci_hi": -r["ci95_lo_pct"] / 100 * day_usd,
                             "annual_sales_usd": ANNUAL_SALES_USD, "open_days": OPEN_DAYS,
                             "years_t": r["years_t"], "years_b": r["years_b"]})
    return rows


def daily_loss_fraction(eff, sample, pc: np.ndarray, warm: np.ndarray) -> np.ndarray:
    loss = np.zeros(len(pc))
    for lo, hi, n in RAIN_BINS:
        m = (pc >= lo) & (pc < hi)
        for w in (0, 1):
            loss[m & (warm == w)] = 1 - np.exp(_pick(eff, sample, "bins_x_season", f"{n} warm={w}")["effect_log"])
    loss[np.isnan(pc)] = np.nan
    return loss


def loss_distribution(eff, wx) -> pd.DataFrame:
    """Monthly share of revenue lost to rain, 1991-2025, by city x calendar month.

    Each day loses 1 - exp(b) of its diners, b = the PRIMARY sample's combined effect of that day's rain bin
    in that season (spec bins_x_season); days are weighted equally (rain is independent of weekday). 'net'
    scales by the 7-day rebound ratio. ci_lo/hi rescale by the 95% CI of the pooled >= 0.10 in effect. 'city'
    columns rescale by the city's shrunk effect relative to the pooled one (by_city, combined).
    pct_lost_mean_dbnomics repeats the mean with the 2020-23 sample's effects."""
    head = _pick(eff, PRIMARY, "wet010", "rain >= 0.10 in")
    base_loss = 1 - np.exp(head["effect_log"])
    scale_lo = (1 - np.exp(head["effect_log"] + Z95 * head["se"])) / base_loss
    scale_hi = (1 - np.exp(head["effect_log"] - Z95 * head["se"])) / base_loss
    reb = rebound_ratio(eff, PRIMARY)
    cityf = eff[(eff["sample"] == PRIMARY) & (eff["spec"] == "by_city") & (eff["era"] == ERA_C)].set_index("group")
    city_scale = ((1 - np.exp(cityf["effect_log_shrunk"])) / base_loss).clip(lower=0)
    d = wx[(wx["date"].dt.year >= CLIMO[0]) & (wx["date"].dt.year <= CLIMO[1])][["station", "date", "pcpn"]].copy()
    d["year"], d["month"] = d["date"].dt.year, d["date"].dt.month
    warm = d["month"].isin(WARM_MONTHS).astype(int).to_numpy()
    pc = d["pcpn"].to_numpy()
    d["loss"] = daily_loss_fraction(eff, PRIMARY, pc, warm)
    d["loss_db"] = daily_loss_fraction(eff, SECONDARY, pc, warm)
    for c, thr in (("wet", WET), ("any", 0.01), ("heavy", 0.50)):
        d[c] = np.where(np.isnan(pc), np.nan, pc >= thr)
    g = d.groupby(["station", "year", "month"])
    ym = pd.DataFrame({"n_days": g["date"].size(), "n_obs": g["pcpn"].count(), "loss": g["loss"].mean(),
                       "loss_db": g["loss_db"].mean(), "wet": g["wet"].mean(), "any": g["any"].mean(),
                       "heavy": g["heavy"].mean(), "rain_in": g["pcpn"].sum()}).reset_index()
    ym = ym[ym["n_days"] - ym["n_obs"] <= 2]
    for c in ("wet", "any", "heavy"):           # counts scaled to the full month
        ym[f"{c}_days"] = ym[c] * ym["n_days"]
    ym["pct_lost"] = 100 * ym["loss"]
    rows = []
    for city, (label, st, _, region) in CITIES.items():
        cs = float(city_scale.get(city, np.nan))
        for mo in range(1, 13):
            x = ym[(ym["station"] == st) & (ym["month"] == mo)]
            if len(x) < 20:
                continue
            pl, wd = x["pct_lost"], x["wet_days"]
            month_usd = ANNUAL_SALES_USD * float(x["n_days"].median()) / 365.0
            q90, q95 = pl.quantile(0.9), pl.quantile(0.95)
            rows.append({
                "city": city, "label": label, "station": st, "region": region, "month": mo,
                "n_years": len(x), "years": f"{x['year'].min()}-{x['year'].max()}",
                "rain_in_mean": x["rain_in"].mean(), "any_days_mean": x["any_days"].mean(),
                "wet_days_mean": wd.mean(), "wet_days_sd": wd.std(), "wet_days_p50": wd.quantile(0.5),
                "wet_days_p90": wd.quantile(0.9), "wet_days_p95": wd.quantile(0.95), "wet_days_max": wd.max(),
                "heavy_days_mean": x["heavy_days"].mean(), "heavy_days_p95": x["heavy_days"].quantile(0.95),
                "pct_lost_mean": pl.mean(), "pct_lost_sd": pl.std(), "pct_lost_p50": pl.quantile(0.5),
                "pct_lost_p90": q90, "pct_lost_p95": q95, "pct_lost_max": pl.max(),
                "pct_lost_mean_ci_lo": pl.mean() * scale_lo, "pct_lost_mean_ci_hi": pl.mean() * scale_hi,
                "pct_lost_p95_ci_lo": q95 * scale_lo, "pct_lost_p95_ci_hi": q95 * scale_hi,
                "pct_lost_net_mean": pl.mean() * reb, "pct_lost_net_p95": q95 * reb, "rebound_ratio": reb,
                "city_scale": cs, "pct_lost_city_mean": pl.mean() * cs, "pct_lost_city_p90": q90 * cs,
                "pct_lost_city_p95": q95 * cs,
                "pct_lost_mean_dbnomics": 100 * x["loss_db"].mean(),
                "usd_lost_mean": month_usd * pl.mean() / 100, "usd_lost_sd": month_usd * pl.std() / 100,
                "usd_lost_p90": month_usd * q90 / 100, "usd_lost_p95": month_usd * q95 / 100,
                "usd_lost_city_mean": month_usd * pl.mean() * cs / 100, "usd_lost_city_p95": month_usd * q95 * cs / 100,
                "monthly_sales_usd": month_usd, "effects_sample": PRIMARY,
            })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------------------------
# figure
# ---------------------------------------------------------------------------------------------
COL_T, COL_B, COL_DB, INK, MUTED = "#2a78d6", "#eb6834", "#1baf7a", "#0b0b0b", "#52514e"


def figure(eff, loss, path):
    items = [("bins", "0.01-0.10 in"), ("bins", "0.10-0.50 in"), ("bins", ">= 0.50 in"),
             ("dinner", "dinner rain 0.01-0.10 in"), ("dinner", "dinner rain >= 0.10 in"),
             ("dinner", "no dinner rain, other hours >= 0.10 in"),
             ("by_warm", "May-Oct"), ("by_warm", "Nov-Apr"), ("by_weekend", "Fri-Sun"), ("by_weekend", "Mon-Thu"),
             ("by_sunbelt", "Sun Belt"), ("by_sunbelt", "not Sun Belt"),
             ("rebound_month", "same day"), ("rebound_month", "net 7-day (same day + 6 lags)")]
    p, sdb = SAMPLES[PRIMARY], SAMPLES[SECONDARY]
    marks = [(PRIMARY, ERA_T, COL_T, f"{p['years_t']}, rain on the day (dashboard, online)"),
             (PRIMARY, ERA_B, COL_B, f"{p['years_b']}, rain on the comparison day (dashboard)"),
             (SECONDARY, ERA_C, COL_DB, f"{sdb['years_t']} series, both days combined (DB.nomics)")]
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(13.5, 7.0), gridspec_kw={"width_ratios": [1.25, 1]})
    for i, (spec, group) in enumerate(items):
        for j, (sample, era, col, lab) in enumerate(marks):
            m = eff[(eff["sample"] == sample) & (eff["spec"] == spec) & (eff["group"] == group) & (eff["era"] == era)]
            if m.empty:   # e.g. no combined net 7-day row: the two eras' rebounds differ in kind
                continue
            r = m.iloc[0]
            yy = i + (j - 1) * 0.26
            ax.plot([r["ci95_lo_pct"], r["ci95_hi_pct"]], [yy, yy], color=col, lw=2, solid_capstyle="round")
            ax.plot(r["effect_pct"], yy, "o", ms=7, color=col, mec="white", mew=1.5, label=lab if i == 0 else None)
    ax.set_yticks(range(len(items)))
    ax.set_yticklabels([g for _, g in items], fontsize=9, color=INK)
    ax.invert_yaxis()
    ax.axvline(0, color=MUTED, lw=0.8)
    for y0 in (2.5, 5.5, 11.5):
        ax.axhline(y0, color="#e4e3df", lw=0.8)
    ax.set_xlabel("change in seated diners on the day (%), 95% CI", color=INK)
    ax.set_title("Rain and OpenTable seated diners, 46 US cities", loc="left", fontsize=11, color=INK)
    ax.legend(loc="upper center", bbox_to_anchor=(0.42, -0.09), fontsize=8.5, frameon=False, ncol=1)
    ax.grid(axis="x", color="#eeede9", lw=0.6)
    ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)

    show = ["seattle", "new_york", "chicago", "miami", "houston", "los_angeles", "phoenix"]
    cols = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6"]
    for c, col in zip(show, cols):
        x = loss[loss["city"] == c].sort_values("month")
        ax2.plot(x["month"], x["pct_lost_city_mean"], lw=2, color=col, label=CITIES[c][0])
        ax2.text(12.15, x["pct_lost_city_mean"].iloc[-1], CITIES[c][0], fontsize=8, color=INK, va="center")
    ax2.set_xticks(range(1, 13))
    ax2.set_xticklabels(list("JFMAMJJASOND"))
    ax2.set_xlim(0.7, 13.6)
    ax2.set_ylim(bottom=0)
    ax2.set_ylabel("mean share of monthly diners lost to rain (%)", color=INK)
    ax2.set_title("Expected monthly loss to rain, 1991-2025", loc="left", fontsize=11, color=INK)
    ax2.legend(fontsize=8, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.09), ncol=4)
    ax2.grid(axis="y", color="#eeede9", lw=0.6)
    for sp in ("top", "right"):
        ax2.spines[sp].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


# ---------------------------------------------------------------------------------------------
def load_weather(offline: bool) -> pd.DataFrame:
    daily, hourly = {}, {}
    for _, (_, st, tz, _) in CITIES.items():
        if st in daily:
            continue
        parts = [fetch_daily(st, offline), fetch_daily(st, offline, *LIVE_DAILY)]
        parts = [x for x in parts if x is not None]
        if not parts:
            raise SystemExit(f"no ACIS daily data for {st}")
        daily[st] = pd.concat(parts).drop_duplicates("date", keep="first").sort_values("date")
        hp = [fetch_hourly(st, tz, offline, span) for span in (HOURLY, LIVE_HOURLY)]
        hp = [x for x in hp if x is not None and len(x)]
        hourly[st] = pd.concat(hp).drop_duplicates("date", keep="first") if hp else None
    return weather_frame(daily, hourly)


def main(argv=None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    offline = "--offline" in args
    warnings.simplefilter("ignore", pd.errors.PerformanceWarning)   # many interaction columns added to one frame
    t0 = time.time()
    ot = pd.concat([load_opentable(offline), load_live()], ignore_index=True)
    wx = load_weather(offline)
    chk = wx.dropna(subset=["pcpn", "hr_total"])
    print(f"cities by series: {ot.groupby('topic')['city'].nunique().to_dict()}; {wx['station'].nunique()} stations; "
          f"hourly vs ACIS daily: wet-day agreement {((chk['pcpn'] >= WET) == (chk['hr_total'] >= WET)).mean():.1%}, "
          f"corr {np.corrcoef(chk['pcpn'], chk['hr_total'])[0, 1]:.3f} ({len(chk)} station-days)")
    samples = [k for k in SAMPLES if (ot["topic"] == SAMPLES[k]["topic"]).any()]
    if PRIMARY not in samples:
        raise SystemExit("live dashboard data missing; it is the primary sample")
    bt = pd.concat([base_test(ot, wx, k) for k in samples], ignore_index=True)
    bt.to_csv(PROCESSED / "rain_reservations_base_test.csv", index=False)
    effs, panels = [], {}
    for k in samples:
        e, panels[k] = run_effects(ot, wx, k)
        effs.append(e)
    eff = pd.concat(effs, ignore_index=True)
    eff = pd.concat([eff, pd.DataFrame(dollar_rows(eff))], ignore_index=True)
    eff.to_csv(PROCESSED / "rain_reservations_effects.csv", index=False)
    loss = loss_distribution(eff, wx)
    loss.to_csv(PROCESSED / "rain_reservations_city_month_loss.csv", index=False)
    figure(eff, loss, FIGURES / "rain_reservations_effects.png")

    pd.set_option("display.width", 250)
    pd.set_option("display.max_rows", 1000)
    print(bt.round(4).to_string(index=False))
    show = ["sample", "spec", "group", "era", "effect_pct", "ci95_lo_pct", "ci95_hi_pct", "t_stat", "n"]
    print(eff[~eff["spec"].isin(["by_city", "dollars"])][show].round(2).to_string(index=False))
    for k, p in panels.items():
        print(f"{k}: {len(p)} city-days, {p['city'].nunique()} cities, {p['date'].min().date()} to "
              f"{p['date'].max().date()}, share of days >= {WET} in: {p['wet_t'].mean():.3f}; "
              f"rebound ratio {rebound_ratio(eff, k):.2f}")
    print(loss.groupby("region")[["wet_days_mean", "pct_lost_mean", "pct_lost_p95", "usd_lost_mean"]].mean().round(2))
    print(f"done in {time.time() - t0:.0f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
