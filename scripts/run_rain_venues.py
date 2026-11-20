"""Expansion study: how rain moves attendance and revenue at outdoor venues (MLB ballparks).

Question: what does a rainy game day cost an outdoor venue, and what does the monthly loss
distribution look like, so that a wet-side contract (the venue's natural counterparty to a
farmer's dry-side put) can be sized? Notes: docs/research/expansion_notes/rain_venues.md.

Data (all free; raw downloads cached under data/raw/, which is gitignored)
  Retrosheet game logs 1990-2025 (date, park, attendance, day/night, doubleheader number) and
  original schedules 2000-2025 (postponement reason and makeup date):
    https://www.retrosheet.org/gamelogs/index.html, https://www.retrosheet.org/schedule/index.html
    -> data/raw/retrosheet/{gl,sched}/
  NOAA ACIS StnData daily precipitation and max temperature 1991-2025 at the airport station
    nearest each park (missing days filled from a second station) -> data/raw/stations/acis_venues/
  Iowa Environmental Mesonet ASOS hourly precipitation (p01i), Mar-Oct 2000-2025, summed over
    the hours around game time (day games 11:00-17:00, night games 16:00-23:00, local)
    -> data/raw/stations/iem_asos_venues/

Method
  1. Attendance: OLS of log(attendance) on same-day station rain bins, rain the day before,
     max-temperature bins, opponent, day of week, month, night, home opener, with home-team x
     season fixed effects absorbed (within transform) and standard errors clustered by home
     team x season. Single games only (no doubleheaders, no makeup dates). Seasons 2000-2025
     without 2020 (no fans) and 2021 (capacity limits). Open-air parks are the treatment sample;
     domes and retractable roofs are the placebo. A second spec (2012-2025) adds game-window rain;
     a third interacts rain with near-capacity team-seasons (median game >= 95% of the season's
     98th-percentile crowd).
  2. Rainouts: share of scheduled home games postponed for rain / wet grounds / inclement weather
     by park and month, and the postponement probability by same-day rain bin. Each postponed
     game is matched to its makeup in the game logs; the gate lost is 1 - (extra attendance on
     the makeup date) / (model-expected attendance on the original date), where "extra" is the
     makeup day's total minus the model-expected crowd for any game already scheduled that day.
  3. Dollars: lost fans x revenue per fan (ticket + in-park spend; sources and range in the notes).
  4. Monthly loss: every team's current open-air park, its 2023-2025 home-date templates laid on
     each year of 1991-2025 daily rain, with rainouts drawn from the fitted probabilities. Mean,
     90th and 95th percentile of the month's rain loss, and a parameter-draw CI on the mean.
  5. (second venue) Chicago Divvy bike-share daily trips 2014-2019 vs Midway/O'Hare rain.

Outputs
  data/processed/rain_venues_effects.csv          every estimate (model, term, coef, se, pct, CI, n)
  data/processed/rain_venues_team_month_loss.csv  team x month loss distribution in dollars
  data/processed/rain_venues_rainouts.csv         rainout rate by park x month
  data/processed/rain_venues_makeups.csv          each rainout, its makeup type and gate lost
  docs/figures/rain_venues_effects.png            attendance effects + rainout rates

Usage: python scripts/run_rain_venues.py [--offline] [--no-hourly] [--no-divvy]
(first run: about 60 ACIS requests, 29 IEM requests and 6 Divvy queries; then about 1 minute)
"""
from __future__ import annotations

import io
import sys
import time
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from agri_hedge.config import FIGURES, PROCESSED, RAW
from agri_hedge.locations import haversine_miles
from agri_hedge.stations import ACIS_URL, RAW_STATIONS, _cached_json, _request_json, _slug

RETRO = RAW / "retrosheet"
ACIS_CACHE = RAW_STATIONS / "acis_venues"
IEM_CACHE = RAW_STATIONS / "iem_asos_venues"
DIVVY_CACHE = RAW / "divvy"
GL_ZIPS = ["gl1990_99", "gl2000_09", "gl2010_19", "gl2020_25"]
GL_URL = "https://www.retrosheet.org/gamelogs/{name}.zip"
SCHED_URL = "https://www.retrosheet.org/schedule/schedule.zip"
IEM_URL = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"
DIVVY_URL = "https://data.cityofchicago.org/resource/fg6s-gzvg.json"

YEARS = range(2000, 2026)
DROP_REG = {2020, 2021}           # regression: no fans in 2020, capacity limits in 2021
WX_YEARS = (1991, 2025)           # weather record for the loss distribution
TEMPLATE_YEARS = (2023, 2024, 2025)
SEED = 473
N_DRAWS = 200                     # rainout Monte Carlo draws per (weather year, template)
N_PARAM = 400                     # parameter draws for the CI on the mean monthly loss

# revenue per fan (USD). Ticket: Team Marketing Report 2023 MLB Fan Cost Index average ticket $37.
# In-park spend: FCI basket per person from Statista 2024 average prices (hot dog 5.47, beer 7.18,
# soda 5.37: (4 dogs + 4 sodas + 2 beers) / 4 = 14.43) as the low case; $20 base and $30 high are
# assumptions (adds parking, merchandise, larger per-caps). See the notes for the sources.
TICKET_USD = 37.0
PERCAP_USD = {"low": 14.43, "base": 20.0, "high": 30.0}
TICKET_LOW_USD = 30.0             # assumption: walk-up mix and discounts below the list average

RAIN_BINS = [(-1, 0.005, "dry"), (0.005, 0.10, "r001_009"), (0.10, 0.50, "r010_049"),
             (0.50, 99, "r050plus")]
PO_BINS = [(-1, 0.005, "0"), (0.005, 0.10, "0.01-0.09"), (0.10, 0.25, "0.10-0.24"),
           (0.25, 0.50, "0.25-0.49"), (0.50, 1.00, "0.50-0.99"), (1.00, 2.00, "1.00-1.99"),
           (2.00, 99, "2.00+")]
TEMP_BINS = [(-99, 50, "t_lt50"), (50, 60, "t_50s"), (60, 70, "t_60s"), (70, 80, "t70s"),
             (80, 90, "t_80s"), (90, 95, "t_90_94"), (95, 199, "t_95plus")]
WINDOW = {"D": (11, 17), "N": (16, 23)}   # local hours (inclusive) summed for the game window
RAIN_WORDS = ("rain", "wet grounds", "inclement")
HOURLY_FROM = 2012                # IEM p01i is complete (0 on dry hours) from 2012 at these stations
PO_PRIOR = 10.0                   # pseudo-rainouts shrinking each park's rainout calibration toward 1
LOSS_EXCLUDE = {"TBA"}            # Rays: Steinbrenner Field in 2025 only, back under Tropicana's dome in 2026

# park -> (name, lat, lon, roof, station, fallback station, timezone). Station = the nearest
# first-order (Kalshi-style) airport ASOS; fallback fills missing ACIS days. Canadian parks
# (TOR02, MON02) are left out: ACIS has no Canadian stations.
PARKS = {
    "ANA01": ("Angel Stadium", 33.8003, -117.8827, "open", "SNA", "LAX", "America/Los_Angeles"),
    "ARL02": ("Globe Life Park", 32.7513, -97.0828, "open", "DFW", "DAL", "America/Chicago"),
    "ARL03": ("Globe Life Field", 32.7473, -97.0847, "retractable", "DFW", "DAL", "America/Chicago"),
    "ATL02": ("Turner Field", 33.7350, -84.3900, "open", "ATL", "PDK", "America/New_York"),
    "ATL03": ("Truist Park", 33.8908, -84.4678, "open", "ATL", "PDK", "America/New_York"),
    "BAL12": ("Camden Yards", 39.2840, -76.6217, "open", "BWI", "DCA", "America/New_York"),
    "BOS07": ("Fenway Park", 42.3467, -71.0972, "open", "BOS", "ORH", "America/New_York"),
    "CHI11": ("Wrigley Field", 41.9484, -87.6553, "open", "ORD", "MDW", "America/Chicago"),
    "CHI12": ("Rate Field", 41.8299, -87.6338, "open", "MDW", "ORD", "America/Chicago"),
    "CIN08": ("Cinergy Field", 39.0975, -84.5066, "open", "CVG", "LUK", "America/New_York"),
    "CIN09": ("Great American Ball Park", 39.0979, -84.5082, "open", "CVG", "LUK", "America/New_York"),
    "CLE08": ("Progressive Field", 41.4962, -81.6852, "open", "CLE", "BKL", "America/New_York"),
    "DEN02": ("Coors Field", 39.7559, -104.9942, "open", "DEN", "DENthr 9", "America/Denver"),
    "DET05": ("Comerica Park", 42.3390, -83.0485, "open", "DTW", "DET", "America/Detroit"),
    "HOU03": ("Daikin Park", 29.7573, -95.3555, "retractable", "HOU", "IAH", "America/Chicago"),
    "KAN06": ("Kauffman Stadium", 39.0517, -94.4803, "open", "MCI", "MKC", "America/Chicago"),
    "LOS03": ("Dodger Stadium", 34.0739, -118.2400, "open", "LAX", "BUR", "America/Los_Angeles"),
    "MIA01": ("Sun Life Stadium", 25.9580, -80.2389, "open", "MIA", "FLL", "America/New_York"),
    "MIA02": ("loanDepot park", 25.7781, -80.2196, "retractable", "MIA", "FLL", "America/New_York"),
    "MIL05": ("County Stadium", 43.0280, -87.9712, "open", "MKE", "MWC", "America/Chicago"),
    "MIL06": ("American Family Field", 43.0280, -87.9712, "retractable", "MKE", "MWC", "America/Chicago"),
    "MIN03": ("Metrodome", 44.9738, -93.2581, "dome", "MSP", "STP", "America/Chicago"),
    "MIN04": ("Target Field", 44.9817, -93.2776, "open", "MSP", "STP", "America/Chicago"),
    "NYC16": ("Yankee Stadium (old)", 40.8274, -73.9259, "open", "LGA", "JFK", "America/New_York"),
    "NYC17": ("Shea Stadium", 40.7571, -73.8458, "open", "LGA", "JFK", "America/New_York"),
    "NYC20": ("Citi Field", 40.7571, -73.8458, "open", "LGA", "JFK", "America/New_York"),
    "NYC21": ("Yankee Stadium", 40.8296, -73.9262, "open", "LGA", "JFK", "America/New_York"),
    "OAK01": ("Oakland Coliseum", 37.7516, -122.2005, "open", "OAK", "SFO", "America/Los_Angeles"),
    "PHI12": ("Veterans Stadium", 39.9061, -75.1665, "open", "PHL", "PNE", "America/New_York"),
    "PHI13": ("Citizens Bank Park", 39.9061, -75.1665, "open", "PHL", "PNE", "America/New_York"),
    "PHO01": ("Chase Field", 33.4455, -112.0667, "retractable", "PHX", "DVT", "America/Phoenix"),
    "PIT07": ("Three Rivers Stadium", 40.4469, -80.0158, "open", "PIT", "AGC", "America/New_York"),
    "PIT08": ("PNC Park", 40.4469, -80.0057, "open", "PIT", "AGC", "America/New_York"),
    "SAC01": ("Sutter Health Park", 38.5803, -121.5136, "open", "SAC", "SMF", "America/Los_Angeles"),
    "SAN01": ("Qualcomm Stadium", 32.7831, -117.1196, "open", "SAN", "MYF", "America/Los_Angeles"),
    "SAN02": ("Petco Park", 32.7073, -117.1566, "open", "SAN", "MYF", "America/Los_Angeles"),
    "SEA03": ("T-Mobile Park", 47.5914, -122.3325, "retractable", "SEA", "BFI", "America/Los_Angeles"),
    "SFO03": ("Oracle Park", 37.7786, -122.3893, "open", "SFO", "OAK", "America/Los_Angeles"),
    "STL09": ("Busch Stadium II", 38.6226, -90.1928, "open", "STL", "CPS", "America/Chicago"),
    "STL10": ("Busch Stadium", 38.6226, -90.1928, "open", "STL", "CPS", "America/Chicago"),
    "STP01": ("Tropicana Field", 27.7682, -82.6534, "dome", "TPA", "PIE", "America/New_York"),
    "TAM02": ("Steinbrenner Field", 27.9803, -82.5067, "open", "TPA", "PIE", "America/New_York"),
    "WAS10": ("RFK Stadium", 38.8898, -76.9719, "open", "DCA", "IAD", "America/New_York"),
    "WAS11": ("Nationals Park", 38.8730, -77.0074, "open", "DCA", "IAD", "America/New_York"),
}
# airport coordinates (for the park-to-station distance column only)
STATION_LL = {"SNA": (33.680, -117.866), "DFW": (32.898, -97.019), "ATL": (33.630, -84.442),
              "BWI": (39.173, -76.684), "BOS": (42.361, -71.010), "ORD": (41.995, -87.934),
              "MDW": (41.786, -87.752), "CVG": (39.044, -84.672), "CLE": (41.405, -81.853),
              "DEN": (39.847, -104.656), "DTW": (42.231, -83.331), "HOU": (29.638, -95.282),
              "MCI": (39.297, -94.731), "LAX": (33.938, -118.389), "MIA": (25.788, -80.317),
              "MKE": (42.947, -87.897), "MSP": (44.883, -93.229), "LGA": (40.779, -73.880),
              "OAK": (37.721, -122.221), "PHL": (39.873, -75.227), "PHX": (33.434, -112.012),
              "PIT": (40.485, -80.214), "SAC": (38.507, -121.495), "SAN": (32.734, -117.183),
              "SEA": (47.449, -122.309), "SFO": (37.619, -122.375), "STL": (38.753, -90.374),
              "TPA": (27.962, -82.540), "DCA": (38.848, -77.034)}

GL_COLS = {0: "date", 1: "num", 2: "dow", 3: "vis", 6: "home", 11: "outs", 12: "dn",
           13: "completion", 16: "park", 17: "att"}


# ---------------------------------------------------------------------------------------------
# downloads (cached)
# ---------------------------------------------------------------------------------------------
def _download(url: str, dest: Path, offline: bool) -> Path | None:
    if dest.exists():
        return dest
    if offline:
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    r = requests.get(url, timeout=120, headers={"User-Agent": "agri-hedge ECE473 research"})
    r.raise_for_status()
    dest.write_bytes(r.content)
    return dest


def load_gamelogs(offline: bool) -> pd.DataFrame:
    frames = []
    for name in GL_ZIPS:
        z = _download(GL_URL.format(name=name), RETRO / f"{name}.zip", offline)
        if z is None:
            raise SystemExit(f"missing {z}; run once without --offline")
        with zipfile.ZipFile(z) as zf:
            for member in sorted(zf.namelist()):
                if not member.lower().startswith("gl") or not member.lower().endswith(".txt"):
                    continue
                d = pd.read_csv(io.BytesIO(zf.read(member)), header=None, usecols=list(GL_COLS),
                                dtype=str).rename(columns=GL_COLS)
                frames.append(d)
    g = pd.concat(frames, ignore_index=True)
    g["date"] = pd.to_datetime(g["date"], format="%Y%m%d")
    g["year"] = g["date"].dt.year
    g["att"] = pd.to_numeric(g["att"], errors="coerce")
    g["outs"] = pd.to_numeric(g["outs"], errors="coerce")
    g["dn"] = g["dn"].str.upper()
    return g


def load_schedules(offline: bool) -> pd.DataFrame:
    z = _download(SCHED_URL, RETRO / "schedule.zip", offline)
    frames = []
    with zipfile.ZipFile(z) as zf:
        for y in YEARS:
            if y == 2020:
                continue
            d = pd.read_csv(io.BytesIO(zf.read(f"{y}schedule.csv")), dtype=str)
            d = d.rename(columns={"Date": "date", "Num": "num", "Visitor": "vis", "Home": "home",
                                  "Day/Night": "dn", "Postponed": "postponed", "Makeup": "makeup",
                                  "Location": "location"})
            frames.append(d[[c for c in ("date", "num", "vis", "home", "dn", "postponed", "makeup",
                                         "location") if c in d.columns]])
    s = pd.concat(frames, ignore_index=True)
    s["date"] = pd.to_datetime(s["date"], format="%Y%m%d")
    s["year"] = s["date"].dt.year
    s["postponed"] = s["postponed"].fillna("")
    s["makeup"] = s["makeup"].fillna("")
    low = s["postponed"].str.lower()
    s["rain_po"] = low.apply(lambda v: any(w in v for w in RAIN_WORDS))
    s["hurricane_po"] = low.str.contains("hurrican")
    s["cold_po"] = low.str.contains("snow|cold")
    return s


def fetch_acis(code: str, offline: bool) -> pd.DataFrame | None:
    sdate, edate = f"{WX_YEARS[0]}-01-01", f"{WX_YEARS[1]}-12-31"
    sid = code if " " in code else f"K{code} 5"          # full ACIS sid, or an ICAO K-code
    cache = ACIS_CACHE / f"stndata_{_slug(sid)}_{sdate}_{edate}_pcpn_maxt.json"
    if offline and not cache.exists():
        return None
    payload = {"sid": sid, "sdate": sdate, "edate": edate, "meta": "name,uid",
               "elems": [{"name": "pcpn"}, {"name": "maxt"}]}
    try:
        data = _cached_json(cache, lambda: _request_json("POST", f"{ACIS_URL}/StnData", payload=payload))
    except Exception as e:  # noqa: BLE001
        print(f"  ACIS fetch failed for {code}: {e}")
        return None
    rows = data.get("data", []) if isinstance(data, dict) else []
    if not rows:
        return None
    df = pd.DataFrame(rows, columns=["date", "pcpn", "maxt"])
    df["date"] = pd.to_datetime(df["date"])
    for c in ("pcpn", "maxt"):
        df[c] = df[c].map(_acis_value)
    return df.set_index("date")


def _acis_value(raw) -> float:
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


def station_daily(offline: bool) -> dict[str, pd.DataFrame]:
    """Primary station daily pcpn/maxt with missing days filled from the fallback station."""
    out, raw = {}, {}
    pairs = {(p[4], p[5]) for p in PARKS.values()}
    for prim, fb in sorted(pairs):
        for c in (prim, fb):
            if c not in raw:
                raw[c] = fetch_acis(c, offline)
        a, b = raw[prim], raw[fb]
        if a is None:
            continue
        d = a.copy()
        d["filled"] = False
        if b is not None:
            b = b.reindex(d.index)
            miss = d["pcpn"].isna() & b["pcpn"].notna()
            d.loc[miss, "pcpn"] = b.loc[miss, "pcpn"]
            d.loc[miss, "filled"] = True
            mt = d["maxt"].isna()
            d.loc[mt, "maxt"] = b.loc[mt, "maxt"]
        out[(prim, fb)] = d
    return out


def fetch_iem(code: str, tz: str, offline: bool) -> pd.DataFrame | None:
    """Hourly ASOS precip (p01i) for 2000-2025 in local time: one IEM request per station."""
    y0, y1 = YEARS[0], YEARS[-1]
    cache = IEM_CACHE / f"{code}_{y0}_{y1}_p01i.csv"
    if not cache.exists():
        if offline:
            return None
        params = {"station": code, "data": "p01i", "year1": y0, "month1": 1, "day1": 1,
                  "year2": y1 + 1, "month2": 1, "day2": 1, "tz": tz, "format": "onlycomma",
                  "latlon": "no", "missing": "M", "trace": "T", "direct": "no", "report_type": 3}
        for attempt in range(5):
            try:
                r = requests.get(IEM_URL, params=params, timeout=300,
                                 headers={"User-Agent": "agri-hedge ECE473 research"})
                r.raise_for_status()
                if not r.text.startswith("station,valid,p01i"):
                    raise requests.RequestException("unexpected IEM response")
                break
            except requests.RequestException:
                time.sleep(15 * (attempt + 1))         # IEM answers 429 to rapid requests
        else:
            print(f"  IEM fetch failed for {code}")
            return None
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(r.text, encoding="utf-8")
        time.sleep(3)
    d = pd.read_csv(cache, dtype={"p01i": str})
    if d.empty:
        return None
    d["valid"] = pd.to_datetime(d["valid"])
    d["p"] = pd.to_numeric(d["p01i"].replace({"T": "0"}), errors="coerce")
    return d[["valid", "p"]]


def game_windows(code: str, tz: str, offline: bool) -> pd.DataFrame:
    """Per date: rain summed over the day-game and night-game windows, and hours observed."""
    d = fetch_iem(code, tz, offline)
    if d is None:
        return pd.DataFrame()
    d = d.dropna(subset=["p"])
    # before 2012 the archive leaves p01i missing (not 0) on most dry hours, so a "hours observed"
    # filter would keep mostly wet days; use the complete 2012+ record only
    d = d[d["valid"].dt.month.between(3, 10) & (d["valid"].dt.year >= HOURLY_FROM)]
    # one value per clock hour: the routine METAR's p01i is the accumulation since the last hour
    d["hour"] = d["valid"].dt.floor("h")
    h = d.groupby("hour")["p"].max().reset_index()
    h["date"], h["hr"] = h["hour"].dt.normalize(), h["hour"].dt.hour
    cols = []
    for dn, (h0, h1) in WINDOW.items():
        w = h[h["hr"].between(h0, h1)].groupby("date")["p"].agg(["sum", "count"])
        w.columns = [f"win_{dn}", f"nobs_{dn}"]
        cols.append(w)
    return pd.concat(cols, axis=1, sort=True)


# ---------------------------------------------------------------------------------------------
# regression helpers
# ---------------------------------------------------------------------------------------------
def _bin(x: pd.Series, bins) -> pd.Series:
    out = pd.Series(pd.NA, index=x.index, dtype="object")
    for lo, hi, name in bins:
        out[(x >= lo) & (x < hi)] = name          # [lo, hi), matching np.digitize below
    return out


def fe_ols(df: pd.DataFrame, y: str, xcols: list[str], fe: str, cluster: str) -> dict:
    """OLS with one absorbed fixed effect and cluster-robust SEs (CR1)."""
    d = df.dropna(subset=[y] + xcols)
    g = d[fe].to_numpy()
    X = d[xcols].to_numpy(float)
    Y = d[y].to_numpy(float)
    codes, inv = np.unique(g, return_inverse=True)
    cnt = np.bincount(inv)

    def demean(a):
        if a.ndim == 1:
            return a - (np.bincount(inv, a) / cnt)[inv]
        return a - np.stack([np.bincount(inv, a[:, j]) / cnt for j in range(a.shape[1])], 1)[inv]

    Xd, Yd = demean(X), demean(Y)
    keep = Xd.std(0) > 1e-10
    Xd, cols = Xd[:, keep], [c for c, k in zip(xcols, keep) if k]
    XtX_inv = np.linalg.pinv(Xd.T @ Xd)
    b = XtX_inv @ Xd.T @ Yd
    u = Yd - Xd @ b
    cl_codes, cl = np.unique(d[cluster].to_numpy(), return_inverse=True)
    G, n, k = len(cl_codes), len(Yd), Xd.shape[1] + len(codes)
    S = np.zeros((Xd.shape[1], Xd.shape[1]))
    scores = np.zeros((G, Xd.shape[1]))
    np.add.at(scores, cl, Xd * u[:, None])
    S = scores.T @ scores
    V = XtX_inv @ S @ XtX_inv * (G / (G - 1)) * ((n - 1) / (n - k))
    se = np.sqrt(np.clip(np.diag(V), 0, None))
    # fixed effects for prediction: mean of (y - Xb) within group (on the kept columns)
    Xk = X[:, keep]
    fe_vals = np.bincount(inv, Y - Xk @ b) / cnt
    resid = Y - Xk @ b - fe_vals[inv]
    return {"coef": dict(zip(cols, b)), "se": dict(zip(cols, se)), "V": V, "cols": cols, "n": n,
            "n_clusters": G, "fe": dict(zip(codes, fe_vals)), "smear": float(np.mean(np.exp(resid))),
            "r2_within": 1 - (u @ u) / (Yd @ Yd), "resid_sd": float(resid.std())}


def effect_rows(model: str, res: dict, terms: list[str], sample: str) -> list[dict]:
    rows = []
    for t in terms:
        if t not in res["coef"]:
            continue
        b, s = res["coef"][t], res["se"][t]
        rows.append({"model": model, "sample": sample, "term": t, "coef": b, "se": s,
                     "pct": 100 * (np.exp(b) - 1), "pct_lo": 100 * (np.exp(b - 1.96 * s) - 1),
                     "pct_hi": 100 * (np.exp(b + 1.96 * s) - 1), "n": res["n"],
                     "n_clusters": res["n_clusters"]})
    return rows


def add_dummies(df: pd.DataFrame, col: str, ref, prefix: str) -> list[str]:
    names = []
    for v in sorted(df[col].dropna().unique(), key=str):
        if v == ref:
            continue
        n = f"{prefix}{v}"
        df[n] = (df[col] == v).astype(float)
        names.append(n)
    return names


# ---------------------------------------------------------------------------------------------
# build the game panel
# ---------------------------------------------------------------------------------------------
def main_parks(g: pd.DataFrame) -> pd.DataFrame:
    """(home, year) -> the park where that team played most home games (>= 40)."""
    c = g.groupby(["home", "year", "park"]).size().rename("n").reset_index()
    c = c.sort_values("n").groupby(["home", "year"]).tail(1)
    return c[c["n"] >= 40][["home", "year", "park"]]


def attach_weather(df: pd.DataFrame, daily: dict, windows: dict) -> pd.DataFrame:
    parts = []
    for park, sub in df.groupby("park"):
        if park not in PARKS:
            continue
        _, _, _, roof, prim, fb, _ = PARKS[park]
        wx = daily.get((prim, fb))
        if wx is None:
            continue
        sub = sub.copy()
        sub["roof"], sub["station"] = roof, prim
        dts = sub["date"]
        sub["rain"] = wx["pcpn"].reindex(dts).to_numpy()
        sub["rain_prev"] = wx["pcpn"].reindex(dts - pd.Timedelta(days=1)).to_numpy()
        sub["tmax"] = wx["maxt"].reindex(dts).to_numpy()
        w = windows.get(prim)
        if w is not None and len(w):
            wd = w.reindex(dts)
            dn = sub["dn"].fillna("N").to_numpy()
            win = np.where(dn == "D", wd["win_D"].to_numpy(), wd["win_N"].to_numpy())
            nobs = np.where(dn == "D", wd["nobs_D"].to_numpy(), wd["nobs_N"].to_numpy())
            sub["rain_window"] = np.where(nobs >= 4, win, np.nan)
        else:
            sub["rain_window"] = np.nan
        parts.append(sub)
    return pd.concat(parts, ignore_index=True)


def design(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    d = df.copy()
    d["ly"] = np.log(d["att"])
    d["rbin"] = _bin(d["rain"], RAIN_BINS)
    d["tbin"] = _bin(d["tmax"], TEMP_BINS)
    terms = {"rain": [], "temp": [], "ctrl": []}
    for _, _, name in RAIN_BINS[1:]:
        d[name] = (d["rbin"] == name).astype(float)
        terms["rain"].append(name)
    d["rain_prev_010"] = (d["rain_prev"] >= 0.10).astype(float)
    terms["rain"].append("rain_prev_010")
    for _, _, name in TEMP_BINS:
        if name == "t70s":
            continue
        d[name] = (d["tbin"] == name).astype(float)
        terms["temp"].append(name)
    d["night"] = (d["dn"] == "N").astype(float)
    d["month_c"] = d["date"].dt.month.clip(4, 9)           # Mar -> Apr, Oct -> Sep
    terms["ctrl"] += ["night", "opener"]
    terms["ctrl"] += add_dummies(d, "dow", "Wed", "dow_")
    terms["ctrl"] += add_dummies(d, "month_c", 6, "m_")
    terms["ctrl"] += add_dummies(d, "vis", "ZZZ", "opp_")
    d = d[d["rbin"].notna() & d["rain_prev"].notna() & d["tbin"].notna()]
    return d, terms


def prediction_log(res: dict, row: pd.Series) -> float:
    fe = res["fe"].get(row["ts"])
    if fe is None:
        return np.nan
    return fe + sum(res["coef"][c] * float(row.get(c, 0.0)) for c in res["cols"])


# ---------------------------------------------------------------------------------------------
# analysis pieces
# ---------------------------------------------------------------------------------------------
def attendance_models(panel: pd.DataFrame) -> tuple[list[dict], dict, pd.DataFrame]:
    rows = []
    d, terms = design(panel)
    xs = terms["rain"] + terms["temp"] + terms["ctrl"]
    reg = d[~d["year"].isin(DROP_REG)]
    open_ = reg[reg["roof"] == "open"]
    closed = reg[reg["roof"] != "open"]
    resA = fe_ols(open_, "ly", xs, "ts", "ts")
    rows += effect_rows("A_daily", resA, terms["rain"] + terms["temp"] + ["night"], "open_air")
    resP = fe_ols(closed, "ly", xs, "ts", "ts")
    rows += effect_rows("A_daily", resP, terms["rain"] + terms["temp"], "dome_retractable_placebo")
    # cluster by date instead (weather shocks are shared within a date across parks)
    resA_d = fe_ols(open_.assign(dcl=open_["date"].astype(str)), "ly", xs, "ts", "dcl")
    rows += effect_rows("A_daily_cluster_date", resA_d, terms["rain"], "open_air")
    # B: add the game-window hourly rain (rain that falls around game time)
    ob = open_[open_["rain_window"].notna()].copy()
    if len(ob) < 1000:
        print("  no hourly game-window rain; skipping spec B")
        return _rest_models(rows, open_, closed, terms, xs, resA, resP, d)
    return _window_models(rows, ob, open_, closed, terms, xs, resA, resP, d)


def _window_models(rows, ob, open_, closed, terms, xs, resA, resP, d):
    ob["win_001_009"] = ((ob["rain_window"] >= 0.005) & (ob["rain_window"] < 0.10)).astype(float)
    ob["win_010plus"] = (ob["rain_window"] >= 0.10).astype(float)
    wterms = ["win_001_009", "win_010plus"]
    resB = fe_ols(ob, "ly", wterms + xs, "ts", "ts")
    rows += effect_rows("B_window", resB, wterms + terms["rain"], "open_air")
    resB0 = fe_ols(ob, "ly", wterms + terms["temp"] + terms["ctrl"] + ["rain_prev_010"], "ts", "ts")
    rows += effect_rows("B_window_only", resB0, wterms + ["rain_prev_010"], "open_air")
    cb = closed[closed["rain_window"].notna()].copy()
    cb["win_001_009"] = ((cb["rain_window"] >= 0.005) & (cb["rain_window"] < 0.10)).astype(float)
    cb["win_010plus"] = (cb["rain_window"] >= 0.10).astype(float)
    resBP = fe_ols(cb, "ly", wterms + xs, "ts", "ts")
    rows += effect_rows("B_window", resBP, wterms + terms["rain"], "dome_retractable_placebo")
    return _rest_models(rows, open_, closed, terms, xs, resA, resP, d)


def _rest_models(rows, open_, closed, terms, xs, resA, resP, d):
    # C: near-capacity team-seasons (sellout clubs) vs the rest
    oc = open_.copy()
    cap = oc.groupby(["park", "year"])["att"].transform(lambda s: s.quantile(0.98))
    oc["fill"] = oc["att"] / cap
    oc["near_cap"] = (oc.groupby("ts")["fill"].transform("median") >= 0.95).astype(float)
    inter = []
    for t in terms["rain"]:
        oc[f"{t}_x_cap"] = oc[t] * oc["near_cap"]
        inter.append(f"{t}_x_cap")
    resC = fe_ols(oc, "ly", inter + xs, "ts", "ts")
    rows += effect_rows("C_capacity", resC, terms["rain"] + inter, "open_air")
    share = oc.drop_duplicates("ts")["near_cap"].mean()
    rows.append({"model": "C_capacity", "sample": "open_air", "term": "share_ts_near_capacity",
                 "coef": share, "n": int(oc["ts"].nunique())})
    # D: weekend vs weekday (walk-up heavy weeknights?)
    od = open_.copy()
    od["weekend"] = od["dow"].isin(["Fri", "Sat", "Sun"]).astype(float)
    wk = []
    for t in terms["rain"]:
        od[f"{t}_x_wkend"] = od[t] * od["weekend"]
        wk.append(f"{t}_x_wkend")
    resD = fe_ols(od, "ly", wk + xs, "ts", "ts")
    rows += effect_rows("D_weekend", resD, terms["rain"] + wk, "open_air")
    return rows, {"A": resA, "P": resP, "terms": terms, "xs": xs}, d


def rainouts(sched: pd.DataFrame, parks_by: pd.DataFrame, daily: dict,
             g: pd.DataFrame, resA: dict, dpanel: pd.DataFrame, terms: dict) -> tuple:
    s = sched.copy()
    s = s.merge(parks_by, on=["home", "year"], how="left")
    if "location" in s.columns:
        s["park"] = s["location"].where(s["location"].notna() & (s["location"] != ""), s["park"])
    s = s[s["park"].isin(PARKS)]
    s = attach_weather(s.assign(dn=s["dn"].str.upper()), daily, {})
    s["month"] = s["date"].dt.month
    so = s[s["roof"] == "open"].copy()
    # postponement rate by park and month
    rate = (so.groupby(["park", "month"]).agg(scheduled=("rain_po", "size"), rain_po=("rain_po", "sum"),
                                               seasons=("year", "nunique")).reset_index())
    rate["rate"] = rate["rain_po"] / rate["scheduled"]
    rate["po_per_season"] = rate["rain_po"] / rate["seasons"]
    rate["park_name"] = rate["park"].map(lambda p: PARKS[p][0])
    # P(postponed | same-day rain bin), open-air pooled
    so["pobin"] = _bin(so["rain"], PO_BINS)
    pob = so.dropna(subset=["pobin"]).groupby("pobin").agg(n=("rain_po", "size"), k=("rain_po", "sum"))
    pob["p"] = pob["k"] / pob["n"]
    pob = pob.reindex([b[2] for b in PO_BINS])
    # calibration check of the pooled bin model, park by park
    so["p_hat"] = so["pobin"].map(pob["p"])
    cal = so.groupby(["park", "month"])["p_hat"].sum().rename("pred_rain_po")
    rate = rate.merge(cal.reset_index(), on=["park", "month"], how="left")
    # placebo: postponements at closed parks
    sc = s[s["roof"] != "open"]
    closed_rate = sc["rain_po"].mean()

    # makeup matching: gate lost per rainout
    gi = g.copy()
    gi["key"] = gi["date"].dt.strftime("%Y%m%d") + gi["home"]
    by_day = gi.groupby("key").agg(att_total=("att", lambda a: np.nansum(a)), n_games=("att", "size"))
    po = so[so["rain_po"]].copy()
    po["mk"] = po["makeup"].str.split(";").str[-1].str.strip()
    po["mk_date"] = pd.to_datetime(po["mk"], format="%Y%m%d", errors="coerce")
    po["no_makeup"] = po["postponed"].str.lower().str.contains("no makeup") | po["mk_date"].isna()
    # expected attendance on the original date with dry weather
    expected = _expected_att(po, resA, dpanel, terms)
    po["exp_orig"] = expected
    out = []
    for r in po.itertuples():
        rec = {"date": r.date, "home": r.home, "vis": r.vis, "park": r.park, "exp_orig": r.exp_orig}
        if r.no_makeup:
            rec.update(kind="not_made_up", lost=1.0)
            out.append(rec)
            continue
        if r.mk_date.year != r.date.year:
            rec.update(kind="next_season", lost=np.nan)
            out.append(rec)
            continue
        key = r.mk_date.strftime("%Y%m%d") + r.home
        day = gi[gi["key"] == key]
        if day.empty or (day["park"] != r.park).all():
            rec.update(kind="other_site", lost=1.0)
            out.append(rec)
            continue
        # other games the home team had scheduled on the makeup date (not makeups themselves)
        same = s[(s["date"] == r.mk_date) & (s["home"] == r.home) & ~s["rain_po"]]
        n_mk = int(((po["mk_date"] == r.mk_date) & (po["home"] == r.home)).sum())
        exp_sched = _expected_att(same, resA, dpanel, terms).sum() if len(same) else 0.0
        incr = (by_day.loc[key, "att_total"] - exp_sched) / max(n_mk, 1)
        if len(day) == 1:
            kind = "single_game"
        elif (day["att"].fillna(0) == 0).any():
            kind = "single_admission_dh"
        else:
            kind = "split_dh"
        lost = 1 - incr / r.exp_orig if r.exp_orig and np.isfinite(r.exp_orig) else np.nan
        rec.update(kind=kind, lost=float(np.clip(lost, -1.0, 1.0)) if np.isfinite(lost) else np.nan,
                   makeup_att=float(by_day.loc[key, "att_total"]), exp_sched_same_day=exp_sched)
        out.append(rec)
    mk = pd.DataFrame(out)
    return rate, pob, mk, closed_rate, so


def _expected_att(rows: pd.DataFrame, res: dict, dpanel: pd.DataFrame, terms: dict) -> np.ndarray:
    """Model-expected attendance (dry weather, actual temperature) for schedule rows."""
    r = rows.copy()
    r["ts"] = r["home"] + r["year"].astype(str)
    r["dow"] = r["date"].dt.day_name().str[:3]
    r["att"] = 1.0
    r["tmax"] = r["tmax"].fillna(75)
    r["rain"], r["rain_prev"] = 0.0, 0.0
    r["opener"] = 0.0
    dd, _ = design(r)
    dd = dd.reindex(r.index)
    for c in res["cols"]:
        if c not in dd.columns:
            dd[c] = 0.0
    dd = dd.fillna({c: 0.0 for c in res["cols"]})
    fe = r["ts"].map(res["fe"]).to_numpy(float)
    xb = dd[res["cols"]].to_numpy(float) @ np.array([res["coef"][c] for c in res["cols"]])
    return np.exp(fe + xb) * res["smear"]


# ---------------------------------------------------------------------------------------------
# monthly loss distribution
# ---------------------------------------------------------------------------------------------
def team_month_loss(sched: pd.DataFrame, parks_by: pd.DataFrame, daily: dict, g: pd.DataFrame,
                    resA: dict, pob: pd.DataFrame, lost_frac: float, lost_se: float,
                    rate: pd.DataFrame) -> pd.DataFrame:
    """Monthly rain loss per open-air club: 2023-2025 home-date templates x 1991-2025 daily rain.

    The pooled P(rainout | same-day rain) is scaled per park by (actual + PO_PRIOR) /
    (predicted + PO_PRIOR) rainouts in 2000-2025, a shrunk calibration factor (drainage, tarp
    crews, station distance and scheduling habits differ by park).
    """
    cal = rate.groupby("park")[["rain_po", "pred_rain_po"]].sum()
    park_scale = ((cal["rain_po"] + PO_PRIOR) / (cal["pred_rain_po"] + PO_PRIOR)).to_dict()
    rng = np.random.default_rng(SEED)
    cur = parks_by[parks_by["year"] == 2025].set_index("home")["park"]
    teams = [(t, p) for t, p in cur.items()
             if p in PARKS and PARKS[p][3] == "open" and t not in LOSS_EXCLUDE]
    cols = resA["cols"]
    idx = [cols.index(c) for c in ("r001_009", "r010_049", "r050plus", "rain_prev_010")]
    V = resA["V"][np.ix_(idx, idx)]
    bvec = np.array([resA["coef"][cols[i]] for i in idx])
    p_po, k_po, n_po = (pob[c].to_numpy(float) for c in ("p", "k", "n"))
    edges = [b[1] for b in PO_BINS[:-1]]
    per_fan = {"low": TICKET_LOW_USD + PERCAP_USD["low"], "base": TICKET_USD + PERCAP_USD["base"],
               "high": TICKET_USD + PERCAP_USD["high"]}
    # parameter draws shared by every team-month
    B = rng.multivariate_normal(bvec, V, N_PARAM)
    LF = np.clip(rng.normal(lost_frac, lost_se, N_PARAM), 0, 1)
    PP = rng.beta(k_po + 0.5, n_po - k_po + 0.5, (N_PARAM, len(p_po)))

    def played_lost(r, rp, b):
        """Fraction of the crowd lost on a played game; b is (4,) or (n_draws, 4)."""
        b = np.atleast_2d(b)
        eff = (np.outer(b[:, 0], (r >= 0.005) & (r < 0.10)) + np.outer(b[:, 1], (r >= 0.10) & (r < 0.50))
               + np.outer(b[:, 2], r >= 0.50) + np.outer(b[:, 3], rp >= 0.10))
        return -(np.exp(eff) - 1)

    rows = []
    for team, park in teams:
        wx = daily.get((PARKS[park][4], PARKS[park][5]))
        if wx is None:
            continue
        scale = park_scale.get(park, 1.0)
        p_park = np.clip(p_po * scale, 0, 1)
        recent = g[(g["home"] == team) & (g["park"] == park) & (g["num"] == "0") & (g["year"] >= 2023)
                   & (g["att"] > 0)]
        e_att = float(recent["att"].mean())
        tmpl = sched[(sched["home"] == team) & sched["year"].isin(TEMPLATE_YEARS)]
        tmpl = tmpl.merge(parks_by, on=["home", "year"], how="left")
        if "location" in tmpl.columns:
            tmpl["park"] = tmpl["location"].where(tmpl["location"].fillna("") != "", tmpl["park"])
        tmpl = tmpl[tmpl["park"] == park]
        for month in range(4, 10):
            sims, means, pmeans, games, rain_days, month_rain, home_rain = [], [], [], [], [], [], []
            for ty in sorted(tmpl["year"].unique()):
                md = tmpl[(tmpl["year"] == ty) & (tmpl["date"].dt.month == month)]["date"]
                if md.empty:
                    continue
                for wy in range(WX_YEARS[0], WX_YEARS[1] + 1):
                    dts = pd.to_datetime(pd.DataFrame({"year": wy, "month": md.dt.month, "day": md.dt.day}),
                                         errors="coerce").dropna()
                    r = wx["pcpn"].reindex(dts).to_numpy()
                    rp = wx["pcpn"].reindex(dts - pd.Timedelta(days=1)).to_numpy()
                    ok = np.isfinite(r) & np.isfinite(rp)
                    r, rp = r[ok], rp[ok]
                    if len(r) < 0.8 * len(md):
                        continue
                    games.append(len(r))
                    mon = wx["pcpn"][(wx.index.year == wy) & (wx.index.month == month)]
                    month_rain.append(float(mon.sum()))
                    rain_days.append(int((r >= 0.10).sum()))
                    home_rain.append(float(r.sum()))
                    pb = np.digitize(r, edges)
                    pp = p_park[pb]
                    pl = played_lost(r, rp, bvec)[0]
                    po = rng.random((N_DRAWS, len(r))) < pp
                    sims.append(np.where(po, lost_frac, pl[None, :]).sum(1) * e_att)
                    means.append((pp * lost_frac + (1 - pp) * pl).sum() * e_att)
                    ppd = np.clip(PP[:, pb] * scale, 0, 1)
                    pmeans.append(((ppd * LF[:, None]) + (1 - ppd) * played_lost(r, rp, B)).sum(1) * e_att)
            if not sims:
                continue
            L = np.concatenate(sims)
            pm = np.mean(np.stack(pmeans), 0)
            pf = per_fan["base"]
            mr = np.asarray(month_rain)
            mr_rep = np.repeat(mr, N_DRAWS)
            rows.append({
                "team": team, "park": park, "park_name": PARKS[park][0], "station": PARKS[park][4],
                "month": month, "rainout_scale_vs_pooled": scale,
                "home_games_per_month": float(np.mean(games)),
                "rain_days_ge010_per_month": float(np.mean(rain_days)), "expected_att": e_att,
                "n_weather_template_combos": len(games), "usd_per_fan_base": pf,
                "mean_fans_lost": float(L.mean()), "p90_fans_lost": float(np.quantile(L, 0.90)),
                "p95_fans_lost": float(np.quantile(L, 0.95)),
                "mean_usd": float(L.mean() * pf), "p50_usd": float(np.quantile(L, 0.50) * pf),
                "p90_usd": float(np.quantile(L, 0.90) * pf), "p95_usd": float(np.quantile(L, 0.95) * pf),
                "max_usd": float(L.max() * pf),
                "mean_usd_param_lo": float(np.quantile(pm, 0.025) * pf),
                "mean_usd_param_hi": float(np.quantile(pm, 0.975) * pf),
                "mean_usd_lo_fan": float(np.mean(means) * per_fan["low"]),
                "mean_usd_hi_fan": float(np.mean(means) * per_fan["high"]),
                "mean_usd_ci_lo": float(np.quantile(pm, 0.025) * per_fan["low"]),
                "mean_usd_ci_hi": float(np.quantile(pm, 0.975) * per_fan["high"]),
                # how well the station's whole-month rain total tracks the loss (Kalshi-style index)
                "corr_expected_loss_vs_month_rain": float(np.corrcoef(means, mr)[0, 1]),
                "corr_simulated_loss_vs_month_rain": float(np.corrcoef(L, mr_rep)[0, 1]),
                # a game-day index: number of home dates with >= 0.10 in at the station
                "corr_simulated_loss_vs_wet_home_days": float(np.corrcoef(L, np.repeat(rain_days, N_DRAWS))[0, 1]),
                "corr_simulated_loss_vs_home_day_rain_in": float(np.corrcoef(L, np.repeat(home_rain, N_DRAWS))[0, 1]),
            })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------------------------
# second venue: Chicago Divvy daily trips
# ---------------------------------------------------------------------------------------------
def divvy(daily: dict, offline: bool) -> list[dict]:
    """log(daily Divvy trips) on Midway rain bins, Apr-Oct 2014-2019, by rider type."""
    frames = []
    for y in range(2014, 2020):
        cache = DIVVY_CACHE / f"divvy_daily_trips_{y}.json"
        if not cache.exists():
            if offline:
                continue
            params = {"$select": "date_trunc_ymd(start_time) AS d, user_type, count(*) AS n",
                      "$group": "d, user_type", "$limit": 5000,
                      "$where": f"start_time >= '{y}-01-01T00:00:00' AND start_time < '{y + 1}-01-01T00:00:00'"}
            try:
                data = _request_json("GET", DIVVY_URL, params=params, timeout=300)
            except Exception as e:  # noqa: BLE001
                print(f"  Divvy fetch failed for {y}: {e}")
                continue
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(pd.DataFrame(data).to_json(orient="records"), encoding="utf-8")
        frames.append(pd.read_json(cache, orient="records", dtype=False))
    if not frames:
        return []
    raw = pd.concat(frames, ignore_index=True)
    raw["date"] = pd.to_datetime(raw["d"]).dt.normalize()
    raw["n"] = pd.to_numeric(raw["n"])
    raw["user_type"] = raw["user_type"].fillna("Unknown")
    wx = daily.get(("MDW", "ORD"))
    rows = []
    groups = {"all_riders": raw.groupby("date")["n"].sum().reset_index(),
              "subscribers": raw[raw["user_type"] == "Subscriber"][["date", "n"]],
              "casual_customers": raw[raw["user_type"] == "Customer"][["date", "n"]]}
    for label, d in groups.items():
        d = d.copy()
        d["rain"] = wx["pcpn"].reindex(d["date"]).to_numpy()
        d["rain_prev"] = wx["pcpn"].reindex(d["date"] - pd.Timedelta(days=1)).to_numpy()
        d["tmax"] = wx["maxt"].reindex(d["date"]).to_numpy()
        d = d[(d["n"] > 0) & d["date"].dt.month.between(4, 10)].dropna()
        d["ly"] = np.log(d["n"])
        d["ym"] = d["date"].dt.strftime("%Y%m")
        d["rbin"] = _bin(d["rain"], RAIN_BINS)
        for _, _, name in RAIN_BINS[1:]:
            d[name] = (d["rbin"] == name).astype(float)
        d["rain_prev_010"] = (d["rain_prev"] >= 0.10).astype(float)
        d["tbin"] = _bin(d["tmax"], TEMP_BINS)
        tt = []
        for _, _, name in TEMP_BINS:
            if name != "t70s":
                d[name] = (d["tbin"] == name).astype(float)
                tt.append(name)
        d["dow"] = d["date"].dt.day_name().str[:3]
        dd = add_dummies(d, "dow", "Wed", "dow_")
        d["wk"] = d["date"].dt.strftime("%G%V")
        terms = ["r001_009", "r010_049", "r050plus", "rain_prev_010"]
        res = fe_ols(d, "ly", terms + tt + dd, "ym", "wk")
        rows += effect_rows("E_divvy", res, terms, f"chicago_divvy_{label}_apr_oct_2014_2019")
    return rows


# ---------------------------------------------------------------------------------------------
# figure
# ---------------------------------------------------------------------------------------------
def figure(eff: pd.DataFrame, rate: pd.DataFrame) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    blue, orange, ink, muted = "#2a78d6", "#eb6834", "#0b0b0b", "#52514e"
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.2), facecolor="#fcfcfb")
    labels = {"r001_009": "0.01-0.09 in", "r010_049": "0.10-0.49 in", "r050plus": ">= 0.50 in",
              "rain_prev_010": "day before >= 0.10"}
    a = eff[eff["model"] == "A_daily"]
    x = np.arange(len(labels))
    for i, (sample, col, name) in enumerate([("open_air", blue, "Open-air parks"),
                                              ("dome_retractable_placebo", orange, "Dome / retractable (placebo)")]):
        s = a[a["sample"] == sample].set_index("term").reindex(list(labels))
        ax[0].bar(x + (i - 0.5) * 0.36, s["pct"], 0.34, color=col, label=name,
                  yerr=[s["pct"] - s["pct_lo"], s["pct_hi"] - s["pct"]], ecolor=muted, capsize=3)
    ax[0].axhline(0, color=muted, lw=0.8)
    ax[0].set_xticks(x, list(labels.values()), fontsize=9)
    ax[0].set_ylabel("% change in reported attendance", color=ink)
    ax[0].set_title("Same-day station rain vs a dry day (95% CI)", fontsize=10, color=ink)
    ax[0].legend(frameon=False, fontsize=9)
    m = rate.groupby("month").agg(k=("rain_po", "sum"), n=("scheduled", "sum"))
    m = m[m.index.isin(range(3, 11))]
    ax[1].bar(m.index, 100 * m["k"] / m["n"], 0.6, color=blue)
    ax[1].set_xticks(m.index, ["Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct"][:len(m)], fontsize=9)
    ax[1].set_ylabel("% of scheduled home games postponed", color=ink)
    ax[1].set_title("Rainouts at open-air parks, 2000-2025 (no 2020)", fontsize=10, color=ink)
    for axis in ax:
        axis.set_facecolor("#fcfcfb")
        for sp in ("top", "right"):
            axis.spines[sp].set_visible(False)
        axis.tick_params(colors=muted)
        axis.grid(axis="y", color="#e5e4df", lw=0.6)
        axis.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(FIGURES / "rain_venues_effects.png", dpi=150)
    plt.close(fig)


# ---------------------------------------------------------------------------------------------
def main(argv=None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    offline = "--offline" in args
    t0 = time.time()
    print("Retrosheet game logs and schedules ...")
    g = load_gamelogs(offline)
    sched = load_schedules(offline)
    g = g[g["year"].isin(YEARS) | g["year"].between(2023, 2025)]
    parks_by = main_parks(g)
    print("ACIS daily weather ...")
    daily = station_daily(offline)
    windows = {}
    if "--no-hourly" not in args:
        print("IEM hourly game-window rain ...")
        tzs = {p[4]: p[6] for p in PARKS.values()}
        for code, tz in sorted(tzs.items()):
            windows[code] = game_windows(code, tz, offline)

    # game panel: single regular-season games at the team's main park, attendance > 0
    gm = g.merge(parks_by, on=["home", "year", "park"], how="inner")
    gm = gm[(gm["num"] == "0") & (gm["att"] > 0) & (gm["year"] != 2020)].copy()
    first = gm.groupby(["home", "year"])["date"].transform("min")
    gm["opener"] = (gm["date"] == first).astype(float)
    po_keys = sched.loc[sched["rain_po"] | sched["cold_po"] | sched["hurricane_po"], ["home", "makeup"]]
    mk_keys = set()
    for r in po_keys.itertuples():
        for m in str(r.makeup).split(";"):
            if m.strip():
                mk_keys.add(m.strip() + r.home)
    gm["is_makeup_day"] = (gm["date"].dt.strftime("%Y%m%d") + gm["home"]).isin(mk_keys)
    gm = gm[~gm["is_makeup_day"]]
    gm["ts"] = gm["home"] + gm["year"].astype(str)
    panel = attach_weather(gm, daily, windows)
    print(f"  panel {len(panel):,} games; open-air {int((panel['roof'] == 'open').sum()):,}")

    print("Attendance models ...")
    rows, mods, dpanel = attendance_models(panel)
    resA = mods["A"]
    print("Rainouts and makeups ...")
    rate, pob, mk, closed_rate, so = rainouts(sched, parks_by, daily, g, resA, dpanel, mods["terms"])
    mk_ok = mk.dropna(subset=["lost"])
    rng = np.random.default_rng(SEED)
    boots = [rng.choice(mk_ok["lost"].to_numpy(), len(mk_ok)).mean() for _ in range(2000)]
    lost_frac, lost_se = float(mk_ok["lost"].mean()), float(np.std(boots))
    for kind, sub in mk.groupby("kind"):
        rows.append({"model": "R_makeup", "sample": "open_air", "term": f"kind_{kind}",
                     "coef": len(sub) / len(mk), "n": len(sub),
                     "pct": 100 * sub["lost"].mean() if sub["lost"].notna().any() else np.nan})
    rows.append({"model": "R_makeup", "sample": "open_air", "term": "gate_lost_frac_all",
                 "coef": lost_frac, "se": lost_se, "pct": 100 * lost_frac,
                 "pct_lo": 100 * np.quantile(boots, 0.025), "pct_hi": 100 * np.quantile(boots, 0.975),
                 "n": len(mk_ok)})
    for b, r in pob.iterrows():
        rows.append({"model": "R_po_prob", "sample": "open_air", "term": f"rain_{b}",
                     "coef": r["p"], "se": np.sqrt(r["p"] * (1 - r["p"]) / r["n"]) if r["n"] else np.nan,
                     "pct": 100 * r["p"], "n": int(r["n"])})
    rows.append({"model": "R_po_prob", "sample": "dome_retractable_placebo", "term": "rate_all",
                 "coef": closed_rate, "pct": 100 * closed_rate})
    tot = rate[["scheduled", "rain_po"]].sum()
    rows.append({"model": "R_po_prob", "sample": "open_air", "term": "rate_all",
                 "coef": tot["rain_po"] / tot["scheduled"], "pct": 100 * tot["rain_po"] / tot["scheduled"],
                 "n": int(tot["scheduled"])})
    seasons_po = so.groupby(["home", "year"])["rain_po"].sum()
    rows.append({"model": "R_po_prob", "sample": "open_air", "term": "rainouts_per_team_season",
                 "coef": seasons_po.mean(), "se": seasons_po.std() / np.sqrt(len(seasons_po)),
                 "n": len(seasons_po)})

    # dollars per rainy game day (average open-air club, 2023-2025 crowd)
    eff = pd.DataFrame(rows)
    open_now = parks_by[(parks_by["year"] >= 2023) & parks_by["park"].map(lambda p: PARKS.get(p, ("",) * 4)[3] == "open")]
    att_now = g.merge(open_now, on=["home", "year", "park"])
    att_now = float(att_now[(att_now["num"] == "0") & (att_now["att"] > 0)]["att"].mean())
    rainy = dpanel[(dpanel["roof"] == "open") & ~dpanel["year"].isin(DROP_REG) & (dpanel["rain"] >= 0.10)]
    b = resA["coef"]
    share50 = float((rainy["rain"] >= 0.50).mean())
    played_frac = -((1 - share50) * (np.exp(b["r010_049"]) - 1) + share50 * (np.exp(b["r050plus"]) - 1))
    p_rainy = float((so["rain_po"] & (so["rain"] >= 0.10)).sum() / (so["rain"] >= 0.10).sum())
    per_fan = {"low": TICKET_LOW_USD + PERCAP_USD["low"], "base": TICKET_USD + PERCAP_USD["base"],
               "high": TICKET_USD + PERCAP_USD["high"]}
    for case, pf in per_fan.items():
        played = played_frac * att_now * pf
        po_cost = lost_frac * att_now * pf
        rows.append({"model": "USD_rainy_day", "sample": f"open_air_{case}", "term": "usd_played_game_loss",
                     "coef": played, "n": len(rainy)})
        rows.append({"model": "USD_rainy_day", "sample": f"open_air_{case}", "term": "usd_per_rainout",
                     "coef": po_cost})
        rows.append({"model": "USD_rainy_day", "sample": f"open_air_{case}", "term": "usd_expected_per_rainy_day",
                     "coef": p_rainy * po_cost + (1 - p_rainy) * played})
    rows.append({"model": "USD_rainy_day", "sample": "open_air", "term": "avg_att_2023_2025", "coef": att_now})
    rows.append({"model": "USD_rainy_day", "sample": "open_air", "term": "p_po_given_rain_ge_010", "coef": p_rainy})
    rows.append({"model": "USD_rainy_day", "sample": "open_air", "term": "played_frac_lost_rain_ge_010",
                 "coef": played_frac})
    for case, pf in per_fan.items():
        rows.append({"model": "USD_rainy_day", "sample": case, "term": "usd_per_fan", "coef": pf})

    if "--no-divvy" not in args:
        print("Divvy second venue ...")
        rows += divvy(daily, offline)

    print("Monthly loss distribution ...")
    loss = team_month_loss(sched, parks_by, daily, g, resA, pob, lost_frac, lost_se, rate)

    eff = pd.DataFrame(rows)
    eff.to_csv(PROCESSED / "rain_venues_effects.csv", index=False)
    loss.to_csv(PROCESSED / "rain_venues_team_month_loss.csv", index=False)
    rate["station"] = rate["park"].map(lambda p: PARKS[p][4])
    rate["station_miles"] = rate["park"].map(
        lambda p: haversine_miles(PARKS[p][1], PARKS[p][2], *STATION_LL[PARKS[p][4]]))
    rate.to_csv(PROCESSED / "rain_venues_rainouts.csv", index=False)
    mk.to_csv(PROCESSED / "rain_venues_makeups.csv", index=False)
    figure(eff, rate)
    print(f"done in {time.time() - t0:.0f} s")
    show = eff[eff["model"].isin(["A_daily", "B_window", "C_capacity", "R_makeup", "USD_rainy_day", "E_divvy"])]
    with pd.option_context("display.width", 200, "display.max_rows", 200):
        print(show[["model", "sample", "term", "coef", "se", "pct", "pct_lo", "pct_hi", "n"]].round(4))
        print(loss.groupby("month")[["mean_usd", "p90_usd", "p95_usd"]].median().round(0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
