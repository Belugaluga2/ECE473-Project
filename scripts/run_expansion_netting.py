"""Expansion study: how much a market maker's book nets out when it pairs opposite weather hedgers.

A market maker (MM) sells a dry-side put to one hedger and a wet-side call to another, both
settled on the same Kalshi station and calendar month, and keeps the premium. This script
measures how much the two sides offset compared with writing one side only, and how much
capital beyond the collected premium the book would need.

Pairings (put side / call side; both settle on the airport station's monthly record):
  rain_total   dryland farmer: put on monthly rain     / outdoor venue: call on monthly rain
  rain_days    dryland farmer: put on monthly rain     / outdoor venue: call on wet Fri-Sun days (>= 0.10 in)
  snow_total   ski resort:     put on monthly snowfall / plow contractor or city: call on monthly snowfall
  snow_events  ski resort:     put on monthly snowfall / plow contractor: call on days with >= 2 in of snow
  temp         cold-side hedger: put on monthly mean temperature / warm-side hedger: call on it

Contract terms, fitted on each station-month's sample:
  put  = clip((K - x) / (K - E), 0, 1), K = 30th percentile, E = 0 (rain, snow) or the 5th percentile (temp)
  call = clip((x - K) / (E - K), 0, 1), K = 70th percentile, E = 95th percentile (counts: E >= K + 1)
Each contract is scaled so that its expected payout is 1 premium unit (pure premium), which
means the two sides are sized at equal premium. The MM charges (1 + LOAD) per unit.

Books (n put units, n call units): put (1,0), call (0,1), pair (1,1), put3_call1 (3,1),
put1_call3 (1,3), put3 (3,0). Net loss L = n_p*put + n_c*call - premium. Every metric is
reported per unit of premium collected:
  sd, VaR95 / TVaR95 (empirical, 1951-2025), VaR99 / TVaR99 (from 100k draws of a fitted
  zero-inflated gamma for rain and snow, or a normal for temperature; not computed for the
  count pairings), capital95/99 = max(0, VaR), collateral = the largest possible net loss
  (Kalshi-style full collateral), P(MM loses money in the month), P(neither side pays),
  and the variance reduction from netting = 1 - Var(net) / (sum of the two sides' variances).
Out-of-sample check: strikes and premiums fitted on 1951-1995, payouts realized 1996-2025.

Pooling (no venue side): one farmer put per station per month across stations (national,
and by region), plus the correlation of dry-month indicators (rain < 30th pct) by distance.

Data: data/processed/station_monthly_precip.csv (rain_total, pooling) and ACIS StnData daily
pcpn/snow/avgt for the Kalshi stations (threaded city records, 1951-2025), cached under
data/raw/stations/acis_expansion/ (about 40 requests on the first run, then offline). If ACIS is
unreachable and nothing is cached, the daily pairings are skipped.

Outputs (data/processed/):
  expansion_netting_station_month.csv  one row per (pairing, station, month, book)
  expansion_netting_summary.csv        medians across station-months by pairing x book
  expansion_netting_months.csv         rain_total and snow_total pair medians by calendar month
  expansion_netting_pooling.csv        pooled (cross-station) books vs same-station netting
  expansion_netting_dry_corr.csv       dry-month indicator correlation by distance bin
  expansion_netting_dry_corr_pairs.csv the same for every station pair x month
  expansion_kalshi_families.csv        Kalshi weather series by family and frequency

Usage: python scripts/run_expansion_netting.py [--offline]   (about 1 minute once cached)
"""
from __future__ import annotations

import sys
import time

import numpy as np
import pandas as pd
from scipy import stats

from agri_hedge.config import PROCESSED
from agri_hedge.locations import haversine_miles
from agri_hedge.stations import ACIS_URL, RAW_STATIONS, _cached_json, _request_json, _slug

SAMPLE = (1951, 2025)
SPLIT = 1995                      # out-of-sample: fit on SAMPLE[0]..SPLIT, realize SPLIT+1..SAMPLE[1]
LOAD = 0.20                       # price load on pure premium (doc 24's base case)
PUT_Q, CALL_Q, CALL_CAP_Q, TEMP_FLOOR_Q = 0.30, 0.70, 0.95, 0.05
MIN_YEARS = 40
N_SIM = 100_000
SEED = 473
WET_DAY_IN = 0.10
SNOW_EVENT_IN = 2.0
WEEKEND = (4, 5, 6)               # Fri, Sat, Sun (pandas dayofweek)
SNOW_MONTHS = (11, 12, 1, 2, 3, 4)
SNOW_MIN_STRIKE_IN = 1.0          # a ski-resort put needs a 30th-percentile snowfall of at least 1 in
CACHE = RAW_STATIONS / "acis_expansion"
DROP_STATIONS = {"MDW"}           # Chicago now settles on ORD; keep one Chicago station
# Kalshi monthly-snow cities that settle on an airport/city record we can pull (catalog, family == snow)
SNOW_STATIONS = ["BOS", "ORD", "DCA", "DEN", "DTW", "MKE", "MSP", "NYC", "PHL", "PIT", "SEA", "TTN", "SLC"]
EXTRA_STATIONS = {"SLC": {"sid": "SLCthr 9", "lat": 40.7883, "lon": -111.9778}}
REGIONS = {
    "south_central": ["DFW", "OKC", "SAT", "AUS", "CLL", "HOU"],
    "midwest": ["ORD", "MKE", "MSP", "IND", "STL", "SGF", "CMH", "DTW", "LEX"],
    "northeast": ["BOS", "NYC", "EWR", "PHL", "TTN", "PVD", "DCA", "PIT"],
    "southeast": ["ATL", "MIA", "TPA", "DJT", "MSY"],
    "west": ["ABQ", "DEN", "PHX", "LAS", "LAX", "SFO", "SEA"],
}
BOOKS = {"put": (1, 0), "call": (0, 1), "pair": (1, 1), "put3_call1": (3, 1),
         "put1_call3": (1, 3), "put3": (3, 0)}
PAIRINGS = {
    "rain_total": ("dryland farmer (low monthly rain)", "outdoor venue (high monthly rain)"),
    "rain_days": ("dryland farmer (low monthly rain)", "outdoor venue (wet Fri-Sun days)"),
    "snow_total": ("ski resort (low monthly snow)", "plow contractor / city (high monthly snow)"),
    "snow_events": ("ski resort (low monthly snow)", "plow contractor (days >= 2 in snow)"),
    "temp": ("cold-side hedger (cold month)", "warm-side hedger (warm month)"),
}
DIST_BINS = [0, 100, 250, 500, 1000, 3000]


# ---------------------------------------------------------------------------------------------
# data
# ---------------------------------------------------------------------------------------------
def station_list() -> pd.DataFrame:
    smap = pd.read_csv(PROCESSED / "station_map.csv").drop_duplicates("station_key")
    smap = smap[~smap["station_key"].isin(DROP_STATIONS)]
    rows = [{"station_key": r.station_key, "sid": r.thr_sid if isinstance(r.thr_sid, str) else None,
             "uid": None if isinstance(r.thr_sid, str) else int(r.acis_uid), "lat": r.lat, "lon": r.lon}
            for r in smap.itertuples()]
    for k, v in EXTRA_STATIONS.items():
        rows.append({"station_key": k, "sid": v["sid"], "uid": None, "lat": v["lat"], "lon": v["lon"]})
    return pd.DataFrame(rows)


def _acis_value(raw) -> float:
    """ACIS daily string -> float. T (trace) and S (in a later accumulated total) -> 0, M -> NaN."""
    s = str(raw).strip()
    if s in ("", "M"):
        return np.nan
    if s in ("T", "S", "TA"):
        return 0.0
    if s.endswith("A"):
        s = s[:-1]
    try:
        return float(s)
    except ValueError:
        return np.nan


def fetch_daily(st: pd.Series, offline: bool) -> pd.DataFrame | None:
    sdate, edate = f"{SAMPLE[0]}-01-01", f"{SAMPLE[1]}-12-31"
    sid = st["sid"] if isinstance(st["sid"], str) else None
    key = _slug(sid) if sid else f"uid{int(st['uid'])}"
    cache = CACHE / f"stndata_{key}_{sdate}_{edate}_pcpn_snow_avgt.json"
    if offline and not cache.exists():
        return None
    payload = {"sdate": sdate, "edate": edate, "meta": "name,sids",
               "elems": [{"name": "pcpn"}, {"name": "snow"}, {"name": "avgt"}]}
    payload.update({"sid": sid} if sid else {"uid": int(st["uid"])})
    try:
        data = _cached_json(cache, lambda: _request_json("POST", f"{ACIS_URL}/StnData", payload=payload))
    except Exception as e:  # noqa: BLE001 - network failure just skips the daily pairings for this station
        print(f"  ACIS fetch failed for {st['station_key']}: {e}")
        return None
    rows = data.get("data", []) if isinstance(data, dict) else []
    if not rows:
        return None
    df = pd.DataFrame(rows, columns=["date", "pcpn", "snow", "avgt"])
    df["date"] = pd.to_datetime(df["date"])
    for c in ("pcpn", "snow", "avgt"):
        df[c] = df[c].map(_acis_value)
    df["station_key"] = st["station_key"]
    return df


def monthly_from_daily(daily: pd.DataFrame) -> pd.DataFrame:
    d = daily.copy()
    d["year"], d["month"] = d["date"].dt.year, d["date"].dt.month
    d["wet_wkend"] = (d["pcpn"] >= WET_DAY_IN) & d["date"].dt.day_of_week.isin(WEEKEND)
    d["snow_event"] = d["snow"] >= SNOW_EVENT_IN
    g = d.groupby(["station_key", "year", "month"])
    out = pd.DataFrame({
        "rain_in": g["pcpn"].sum(min_count=1), "rain_missing": g["pcpn"].apply(lambda s: s.isna().sum()),
        "wet_wkend_days": g["wet_wkend"].sum(), "snow_in": g["snow"].sum(min_count=1),
        "snow_missing": g["snow"].apply(lambda s: s.isna().sum()), "snow_events": g["snow_event"].sum(),
        "temp_f": g["avgt"].mean(), "temp_missing": g["avgt"].apply(lambda s: s.isna().sum()),
    }).reset_index()
    out.loc[out["rain_missing"] > 0, ["rain_in", "wet_wkend_days"]] = np.nan
    out.loc[out["snow_missing"] > 0, ["snow_in", "snow_events"]] = np.nan
    out.loc[out["temp_missing"] > 2, "temp_f"] = np.nan
    return out


def load_monthly_rain() -> pd.DataFrame:
    m = pd.read_csv(PROCESSED / "station_monthly_precip.csv")
    m = m[(m["n_missing"] == 0) & m["year"].between(*SAMPLE) & ~m["station_key"].isin(DROP_STATIONS)]
    return m[["station_key", "year", "month", "precip_in"]].rename(columns={"precip_in": "rain_in"})


# ---------------------------------------------------------------------------------------------
# contracts and book metrics
# ---------------------------------------------------------------------------------------------
def put_terms(x: np.ndarray, floor_q: float | None) -> tuple[float, float]:
    k = float(np.quantile(x, PUT_Q))
    e = 0.0 if floor_q is None else float(np.quantile(x, floor_q))
    return k, e


def call_terms(x: np.ndarray, count: bool) -> tuple[float, float]:
    k, e = float(np.quantile(x, CALL_Q)), float(np.quantile(x, CALL_CAP_Q))
    if count:
        k = float(np.floor(k))
        e = max(float(np.ceil(e)), k + 1.0)
    return k, e


def put_frac(x, k, e):
    return np.clip((k - np.asarray(x, float)) / (k - e), 0.0, 1.0) if k > e else np.zeros(len(x))


def call_frac(x, k, e):
    return np.clip((np.asarray(x, float) - k) / (e - k), 0.0, 1.0) if e > k else np.zeros(len(x))


def book_metrics(p: np.ndarray, c: np.ndarray, n_p: int, n_c: int, cap_p: float, cap_c: float,
                 same_variable: bool, tail: bool = True) -> dict:
    """p, c: payouts in premium units (mean 1 on the pricing sample). Returns metrics per premium."""
    prem = (1 + LOAD) * (n_p + n_c)
    payout = n_p * p + n_c * c
    loss = payout - prem
    out = {"premium": prem, "sd_per_prem": loss.std() / prem}
    q95 = np.quantile(loss, 0.95)
    out["var95_per_prem"] = q95 / prem
    out["tvar95_per_prem"] = loss[loss >= q95].mean() / prem
    out["capital95_per_prem"] = max(0.0, q95) / prem
    if tail:
        q99 = np.quantile(loss, 0.99)
        out["var99_per_prem"] = q99 / prem
        out["tvar99_per_prem"] = loss[loss >= q99].mean() / prem
        out["capital99_per_prem"] = max(0.0, q99) / prem
    worst = max(n_p * cap_p, n_c * cap_c) if same_variable else n_p * cap_p + n_c * cap_c
    out["collateral_per_prem"] = (worst - prem) / prem
    out["p_mm_loss"] = float((loss > 0).mean())
    out["p_neither_pays"] = float((((p == 0) | (n_p == 0)) & ((c == 0) | (n_c == 0))).mean())
    out["p_both_pay"] = float(((p > 0) & (c > 0)).mean()) if (n_p and n_c) else 0.0
    # absolute amounts in units of one contract's pure premium (its expected payout)
    for k in ("capital95", "capital99", "collateral"):
        if f"{k}_per_prem" in out:
            out[f"{k}_units"] = out[f"{k}_per_prem"] * prem
    gross_var = n_p ** 2 * p.var() + n_c ** 2 * c.var()
    out["var_reduction"] = 1 - payout.var() / gross_var if (n_p and n_c and gross_var > 0) else 0.0
    out["sd_netting_benefit"] = (1 - payout.std() / (n_p * p.std() + n_c * c.std())) if (n_p and n_c) else 0.0
    return out


def fit_sampler(x: np.ndarray, kind: str, rng: np.random.Generator):
    """Fitted distribution for the 1-in-100 tail: zero-inflated gamma (rain, snow) or normal (temp)."""
    if kind == "normal":
        mu, sd = x.mean(), x.std(ddof=1)
        return lambda n: rng.normal(mu, sd, n)
    pos = x[x >= 0.005]
    p0 = 1 - len(pos) / len(x)
    if len(pos) < 10:
        return None
    a, _, scale = stats.gamma.fit(pos, floc=0)
    return lambda n: np.where(rng.random(n) < p0, 0.0, rng.gamma(a, scale, n))


def station_month(pairing: str, st: str, month: int, df: pd.DataFrame, rng) -> list[dict]:
    """df has columns year, x_put, x_call for one station-month (complete years only)."""
    df = df.dropna()
    if len(df) < MIN_YEARS:
        return []
    count_call = pairing in ("rain_days", "snow_events")
    same_var = pairing in ("rain_total", "snow_total", "temp")
    kind = "normal" if pairing == "temp" else "gamma"
    floor_q = TEMP_FLOOR_Q if pairing == "temp" else None
    xp, xc = df["x_put"].to_numpy(float), df["x_call"].to_numpy(float)

    kp, ep = put_terms(xp, floor_q)
    kc, ec = call_terms(xc, count_call)
    if pairing.startswith("snow") and kp < SNOW_MIN_STRIKE_IN:
        return []
    fp, fc = put_frac(xp, kp, ep), call_frac(xc, kc, ec)
    if fp.mean() <= 0 or fc.mean() <= 0:
        return []
    p, c = fp / fp.mean(), fc / fc.mean()
    cap_p, cap_c = 1 / fp.mean(), 1 / fc.mean()
    corr = float(np.corrcoef(p, c)[0, 1])

    # parametric tail (same-variable pairings only)
    sim = None
    if same_var:
        sampler = fit_sampler(xp, kind, rng)
        if sampler is not None:
            xs = sampler(N_SIM)
            sp, sc = put_frac(xs, kp, ep), call_frac(xs, kc, ec)
            if sp.mean() > 0 and sc.mean() > 0:
                sim = (sp / sp.mean(), sc / sc.mean(), 1 / sp.mean(), 1 / sc.mean())

    # out of sample: fit 1951-SPLIT, realize SPLIT+1..2025
    tr, te = df[df["year"] <= SPLIT], df[df["year"] > SPLIT]
    oos = {}
    if len(tr) >= 30 and len(te) >= 20:
        kp0, ep0 = put_terms(tr["x_put"].to_numpy(float), floor_q)
        kc0, ec0 = call_terms(tr["x_call"].to_numpy(float), count_call)
        m_p, m_c = put_frac(tr["x_put"], kp0, ep0).mean(), call_frac(tr["x_call"], kc0, ec0).mean()
        if m_p > 0 and m_c > 0:
            oos = {"oos_put": put_frac(te["x_put"], kp0, ep0).mean() / m_p,
                   "oos_call": call_frac(te["x_call"], kc0, ec0).mean() / m_c}

    base = {"pairing": pairing, "station_key": st, "month": month, "n_years": len(df),
            "put_strike": kp, "put_exhaust": ep, "call_strike": kc, "call_exhaust": ec,
            "corr_put_call": corr}
    rows = []
    for book, (n_p, n_c) in BOOKS.items():
        r = dict(base, book=book, n_put=n_p, n_call=n_c)
        r.update(book_metrics(p, c, n_p, n_c, cap_p, cap_c, same_var, tail=False))
        if sim is not None:
            sm = book_metrics(sim[0], sim[1], n_p, n_c, sim[2], sim[3], same_var, tail=True)
            r.update({k: sm[k] for k in ("var99_per_prem", "tvar99_per_prem", "capital99_per_prem",
                                          "capital99_units")})
            r["sim_var95_per_prem"] = sm["var95_per_prem"]
        if oos:
            pure = (n_p * oos["oos_put"] + n_c * oos["oos_call"]) / (n_p + n_c)
            r["oos_pure_loss_ratio"] = pure
            r["oos_mm_margin_per_prem"] = 1 - pure / (1 + LOAD)
        rows.append(r)
    return rows


def run_pairings(rain: pd.DataFrame, daily_m: pd.DataFrame | None, rng) -> pd.DataFrame:
    rows = []
    for (st, mo), g in rain.groupby(["station_key", "month"]):
        rows += station_month("rain_total", st, mo, pd.DataFrame(
            {"year": g["year"], "x_put": g["rain_in"], "x_call": g["rain_in"]}), rng)
    if daily_m is not None:
        for (st, mo), g in daily_m.groupby(["station_key", "month"]):
            if st != "SLC":
                rows += station_month("rain_days", st, mo, pd.DataFrame(
                    {"year": g["year"], "x_put": g["rain_in"], "x_call": g["wet_wkend_days"]}), rng)
                rows += station_month("temp", st, mo, pd.DataFrame(
                    {"year": g["year"], "x_put": g["temp_f"], "x_call": g["temp_f"]}), rng)
            if st in SNOW_STATIONS and mo in SNOW_MONTHS:
                rows += station_month("snow_total", st, mo, pd.DataFrame(
                    {"year": g["year"], "x_put": g["snow_in"], "x_call": g["snow_in"]}), rng)
                rows += station_month("snow_events", st, mo, pd.DataFrame(
                    {"year": g["year"], "x_put": g["snow_in"], "x_call": g["snow_events"]}), rng)
    return pd.DataFrame(rows)


METRICS = ["corr_put_call", "var_reduction", "sd_netting_benefit", "sd_per_prem", "var95_per_prem",
           "tvar95_per_prem", "capital95_per_prem", "var99_per_prem", "tvar99_per_prem",
           "capital99_per_prem", "collateral_per_prem", "capital95_units", "capital99_units",
           "collateral_units", "p_mm_loss", "p_neither_pays", "p_both_pay",
           "oos_pure_loss_ratio", "oos_mm_margin_per_prem"]


def summarize(sm: pd.DataFrame) -> pd.DataFrame:
    g = sm.groupby(["pairing", "book"])
    out = g[[c for c in METRICS if c in sm.columns]].median()
    out.insert(0, "n_station_months", g.size())
    out.insert(1, "n_stations", g["station_key"].nunique())
    out = out.reset_index()
    out["stat"] = "median"
    order = {k: i for i, k in enumerate(BOOKS)}
    porder = {k: i for i, k in enumerate(PAIRINGS)}
    out["put_side"] = out["pairing"].map(lambda p: PAIRINGS[p][0])
    out["call_side"] = out["pairing"].map(lambda p: PAIRINGS[p][1])
    return out.sort_values(["pairing", "book"], key=lambda s: s.map(porder) if s.name == "pairing"
                           else s.map(order)).reset_index(drop=True)


def by_month(sm: pd.DataFrame) -> pd.DataFrame:
    d = sm[(sm["book"] == "pair") & sm["pairing"].isin(["rain_total", "snow_total", "rain_days"])]
    cols = ["corr_put_call", "var_reduction", "capital95_per_prem", "capital99_per_prem",
            "collateral_per_prem", "p_mm_loss", "oos_pure_loss_ratio"]
    g = d.groupby(["pairing", "month"])
    out = g[cols].median()
    out.insert(0, "n_stations", g.size())
    single = sm[(sm["book"] == "put") & sm["pairing"].isin(["rain_total", "snow_total", "rain_days"])] \
        .groupby(["pairing", "month"])[["capital95_per_prem", "capital99_per_prem"]].median() \
        .add_prefix("put_only_")
    return out.join(single).reset_index()


# ---------------------------------------------------------------------------------------------
# cross-station pooling
# ---------------------------------------------------------------------------------------------
def unit_payouts(rain: pd.DataFrame) -> pd.DataFrame:
    """Per station-month-year farmer put and venue call units (rain_total terms) and the dry indicator."""
    parts = []
    for (st, mo), g in rain.groupby(["station_key", "month"]):
        if len(g) < MIN_YEARS:
            continue
        x = g["rain_in"].to_numpy(float)
        kp, ep = put_terms(x, None)
        kc, ec = call_terms(x, False)
        fp, fc = put_frac(x, kp, ep), call_frac(x, kc, ec)
        if fp.mean() <= 0 or fc.mean() <= 0:
            continue
        parts.append(pd.DataFrame({"station_key": st, "month": mo, "year": g["year"].to_numpy(),
                                   "put": fp / fp.mean(), "call": fc / fc.mean(), "dry": (x < kp).astype(float)}))
    return pd.concat(parts, ignore_index=True)


def pooled_metrics(loss_by_year: np.ndarray, prem: float) -> dict:
    q95 = np.quantile(loss_by_year, 0.95)
    return {"n_years": len(loss_by_year), "sd_per_prem": loss_by_year.std() / prem,
            "var95_per_prem": q95 / prem, "tvar95_per_prem": loss_by_year[loss_by_year >= q95].mean() / prem,
            "capital95_per_prem": max(0.0, q95) / prem,
            "worst_year_per_prem": loss_by_year.max() / prem, "p_mm_loss": float((loss_by_year > 0).mean())}


def pooling_study(units: pd.DataFrame, stations: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    keep = units.groupby("station_key")["year"].nunique()
    keep = keep[keep >= 70].index           # long records only (drops APC, SPG)
    u = units[units["station_key"].isin(keep)].copy()
    rows = []

    def pool(sub: pd.DataFrame, label: str, scope: str, month, side: str):
        cols = {"put": ["put"], "pair": ["put", "call"]}[side]
        n_side = len(cols)
        # per-year average payout per premium unit; years need >= 90% of the pool's stations
        y = sub.groupby("year").agg(n=("station_key", "size"), pay=(cols[0], "mean"))
        if side == "pair":
            y["pay"] = (sub.groupby("year")["put"].mean() + sub.groupby("year")["call"].mean()) / 2
        y = y[y["n"] >= 0.9 * sub["station_key"].nunique()]
        if len(y) < 30:
            return
        prem = 1 + LOAD
        loss = (y["pay"] - prem).to_numpy()
        # N_eff: sum of standalone sds squared over the pooled variance
        per = sub.pivot_table(index="year", columns="station_key", values=cols[0]) if side == "put" else \
            (sub.assign(v=(sub["put"] + sub["call"]) / 2)
             .pivot_table(index="year", columns="station_key", values="v"))
        per = per.loc[y.index]
        n = per.shape[1]
        n_eff = (per.std().mean() ** 2) / per.mean(axis=1).var(ddof=0) if per.mean(axis=1).var() > 0 else np.nan
        r = {"pool": label, "scope": scope, "month": month, "side": side, "n_stations": n,
             "n_contracts_per_station": n_side, "n_effective_independent": min(n_eff, n) if np.isfinite(n_eff) else np.nan}
        r.update(pooled_metrics(loss, prem))
        rows.append(r)

    for mo in range(1, 13):
        um = u[u["month"] == mo]
        pool(um, "national", "month", mo, "put")
        pool(um, "national", "month", mo, "pair")
        for reg, sts in REGIONS.items():
            pool(um[um["station_key"].isin(sts)], reg, "month", mo, "put")
    # annual books: every month of every station in one year
    ua = u.groupby(["station_key", "year"]).agg(put=("put", "mean"), call=("call", "mean"),
                                                n=("month", "size")).reset_index()
    ua = ua[ua["n"] == 12]
    pool(ua, "national", "annual", "all", "put")
    pool(ua, "national", "annual", "all", "pair")
    for reg, sts in REGIONS.items():
        pool(ua[ua["station_key"].isin(sts)], reg, "annual", "all", "put")
    pooled = pd.DataFrame(rows)
    num = [c for c in pooled.columns if c not in ("pool", "scope", "month", "side")]
    med = pooled[pooled["scope"] == "month"].groupby(["pool", "side"], sort=False)[num].median().reset_index()
    med["scope"], med["month"] = "month_median", "median of 12"
    pooled = pd.concat([pooled, med[pooled.columns]], ignore_index=True)

    # dry indicator correlation by distance
    pos = stations.set_index("station_key")[["lat", "lon"]]
    keys = sorted(keep)
    corr_rows = []
    for mo in range(1, 13):
        piv = u[u["month"] == mo].pivot_table(index="year", columns="station_key", values="dry")
        cm = piv.corr(min_periods=40)
        pc = u[u["month"] == mo].pivot_table(index="year", columns="station_key", values="put").corr(min_periods=40)
        for i, a in enumerate(keys):
            for b in keys[i + 1:]:
                if a in cm and b in cm and np.isfinite(cm.loc[a, b]):
                    corr_rows.append({"month": mo, "a": a, "b": b, "dry_corr": cm.loc[a, b], "put_corr": pc.loc[a, b],
                                      "dist_mi": haversine_miles(pos.loc[a, "lat"], pos.loc[a, "lon"],
                                                                 pos.loc[b, "lat"], pos.loc[b, "lon"])})
    cr = pd.DataFrame(corr_rows)
    cr.to_csv(PROCESSED / "expansion_netting_dry_corr_pairs.csv", index=False)
    labels = [f"{a}-{b} mi" for a, b in zip(DIST_BINS[:-1], DIST_BINS[1:])]
    cr["dist_bin"] = pd.cut(cr["dist_mi"], DIST_BINS, right=False, labels=labels)
    g = cr.groupby("dist_bin", observed=True)
    binned = pd.DataFrame({"n_pairs_x_months": g.size(), "mean_dry_corr": g["dry_corr"].mean(),
                           "median_dry_corr": g["dry_corr"].median(), "mean_put_corr": g["put_corr"].mean(),
                           "share_dry_corr_gt_0p3": g["dry_corr"].apply(lambda s: (s > 0.3).mean())}).reset_index()
    binned["dist_bin"] = binned["dist_bin"].astype(str)
    binned = pd.concat([binned, pd.DataFrame([{"dist_bin": "all", "n_pairs_x_months": len(cr),
                                               "mean_dry_corr": cr["dry_corr"].mean(),
                                               "median_dry_corr": cr["dry_corr"].median(),
                                               "mean_put_corr": cr["put_corr"].mean(),
                                               "share_dry_corr_gt_0p3": (cr["dry_corr"] > 0.3).mean()}])],
                       ignore_index=True)
    return pooled, binned


def kalshi_families() -> pd.DataFrame:
    c = pd.read_csv(PROCESSED / "kalshi_weather_series_catalog.csv")
    g = c.groupby(["family", "frequency"])
    out = pd.DataFrame({"n_series": g.size(), "n_with_open_markets": g["has_open_markets"].sum(),
                        "titles": g["title"].apply(lambda s: "; ".join(sorted(set(s.str.strip()))))}).reset_index()
    return out


def main(argv=None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    offline = "--offline" in args
    t0 = time.time()
    rng = np.random.default_rng(SEED)
    stations = station_list()
    rain = load_monthly_rain()

    daily_parts = []
    for _, st in stations.iterrows():
        d = fetch_daily(st, offline)
        if d is not None:
            daily_parts.append(d)
    daily_m = monthly_from_daily(pd.concat(daily_parts, ignore_index=True)) if daily_parts else None
    if daily_m is not None:
        chk = daily_m.merge(rain, on=["station_key", "year", "month"], suffixes=("_daily", "_monthly")).dropna()
        match = (chk["rain_in_daily"] - chk["rain_in_monthly"]).abs().le(0.015).mean()
        print(f"daily ACIS: {daily_m['station_key'].nunique()} stations; monthly rain matches "
              f"station_monthly_precip.csv within 0.01 in for {match:.1%} of {len(chk)} station-months")
    else:
        print("daily ACIS data unavailable: only rain_total and pooling are computed")

    sm = run_pairings(rain, daily_m, rng)
    sm.to_csv(PROCESSED / "expansion_netting_station_month.csv", index=False)
    summ = summarize(sm)
    summ.to_csv(PROCESSED / "expansion_netting_summary.csv", index=False)
    months = by_month(sm)
    months.to_csv(PROCESSED / "expansion_netting_months.csv", index=False)
    pooled, binned = pooling_study(unit_payouts(rain), stations)
    pooled.to_csv(PROCESSED / "expansion_netting_pooling.csv", index=False)
    binned.to_csv(PROCESSED / "expansion_netting_dry_corr.csv", index=False)
    kalshi_families().to_csv(PROCESSED / "expansion_kalshi_families.csv", index=False)

    pd.set_option("display.width", 250)
    show = ["pairing", "book", "n_station_months", "corr_put_call", "var_reduction", "sd_per_prem",
            "capital95_per_prem", "capital99_per_prem", "collateral_per_prem", "p_mm_loss",
            "p_neither_pays", "oos_pure_loss_ratio"]
    print(summ[show].round(3).to_string(index=False))
    print(months.round(3).to_string(index=False))
    print(pooled.round(3).to_string(index=False))
    print(binned.round(3).to_string(index=False))
    print(f"done in {time.time() - t0:.0f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
