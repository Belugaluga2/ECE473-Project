"""Turn "where is the farm, which months, how much cover" into an optimizer problem.

Shared by the Milestone 2 analysis scripts (docs 15-17), the platform backend
(`agri_hedge.platform`) and the app test (doc 19), so every number comes from one code path.

Coverage windows
----------------
A window is one or more consecutive calendar months with a share of the farmer's protection.
Two-month windows that match a PRF interval ("Apr-May") are paid exactly like PRF: on the
grid's NCEI interval index (`ncei_interval_index.parquet`, our rebuild of what PRF pays on
from crop year 2027). Any other window (one month, three months) is a PRF-style payout on the
grid's own rainfall for those months:

    index_t = 100 x (grid rain in the window, year t) / (mean of that over NORMAL_YEARS)
    payout_t = share x protection x max(0, (100c - index_t) / (100c))

so a farmer can cover a single critical month, which PRF does not allow.

Hedge instruments are NO contracts on one Kalshi settlement station's monthly rain, at the
strikes Kalshi lists for that series and month (`kalshi_strike_sets`), or at a custom strike set.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Sequence

import numpy as np
import pandas as pd

from agri_hedge.config import PROCESSED
from agri_hedge.locations import haversine_miles
from agri_hedge.pricing import leg_probability, no_pays, rain_wide
from agri_hedge.prf import payment_calculation_factor, trigger_grid_index
from agri_hedge.prf_grid import grid_id_to_center, latlon_to_grid_id
from agri_hedge.prf_intervals import INTERVAL_MONTHS, INTERVAL_NAMES
from agri_hedge.replicate import DEFAULT_KALSHI_STRIKES, kalshi_strike_sets

YEARS = (1951, 2025)            # backtest years (NCEI grids start in 1951)
NORMAL_YEARS = (1951, 2025)     # normal for custom (non-PRF) windows
FAIR_WINDOW = (1991, 2025)      # climatology for fair contract prices (same as doc 09)
TRAIN = (1951, 2009)            # time split used in docs 08-09
TEST = (2010, 2025)
MAX_STATION_MI = 150.0          # gridded data in the repo reaches 150 miles from the study stations
MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


# ---------------------------------------------------------------------------------------------
# Data access (cached)
# ---------------------------------------------------------------------------------------------

@lru_cache(maxsize=1)
def station_table() -> pd.DataFrame:
    """Kalshi monthly-rain settlement stations that have a rain record in the repo."""
    sm = pd.read_csv(PROCESSED / "station_map.csv")
    sm = sm[sm["series_ticker"].str.startswith("KX")]
    have = set(_station_monthly()["station_key"].unique())
    sm = sm[sm["station_key"].isin(have)].drop_duplicates("station_key")
    return sm[["series_ticker", "station_key", "name", "state", "lat", "lon", "study_site"]].reset_index(drop=True)


@lru_cache(maxsize=1)
def _station_monthly() -> pd.DataFrame:
    return pd.read_csv(PROCESSED / "station_monthly_precip.csv")


@lru_cache(maxsize=64)
def station_rain(station_key: str) -> pd.DataFrame:
    """Year x month table of the station's complete monthly totals (inches)."""
    return rain_wide(_station_monthly(), station_key)


@lru_cache(maxsize=1)
def _grid_monthly_all() -> pd.DataFrame:
    return pd.read_parquet(PROCESSED / "ncei_monthly_precip_grids.parquet",
                           columns=["grid_id", "year", "month", "precip_in"])


@lru_cache(maxsize=1)
def _grid_interval_all() -> pd.DataFrame:
    d = pd.read_parquet(PROCESSED / "ncei_interval_index.parquet",
                        columns=["grid_id", "year", "interval_name", "index_value_ours"])
    d["interval_name"] = d["interval_name"].astype(str)
    return d


@lru_cache(maxsize=1)
def covered_grids() -> frozenset:
    return frozenset(int(g) for g in _grid_monthly_all()["grid_id"].unique())


@lru_cache(maxsize=256)
def grid_monthly(grid_id: int) -> pd.DataFrame:
    g = _grid_monthly_all()
    g = g[g["grid_id"] == int(grid_id)]
    return g.pivot_table(index="year", columns="month", values="precip_in", aggfunc="first").reindex(
        columns=range(1, 13)).sort_index()


@lru_cache(maxsize=256)
def grid_interval_index(grid_id: int) -> pd.DataFrame:
    g = _grid_interval_all()
    g = g[g["grid_id"] == int(grid_id)]
    return g.pivot_table(index="year", columns="interval_name", values="index_value_ours",
                         aggfunc="first").reindex(columns=INTERVAL_NAMES).sort_index()


@lru_cache(maxsize=1)
def _markets() -> pd.DataFrame:
    return pd.read_parquet(PROCESSED / "kalshi_rain_markets.parquet")


@lru_cache(maxsize=64)
def listed_strikes(series_ticker: str) -> dict:
    """{calendar month: strikes Kalshi has listed for the series} (whole inches 1-7 if none yet)."""
    return kalshi_strike_sets(_markets(), series_ticker, DEFAULT_KALSHI_STRIKES)


# ---------------------------------------------------------------------------------------------
# Requests and windows
# ---------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Window:
    months: tuple[int, ...]
    share: float

    @property
    def label(self) -> str:
        if len(self.months) == 2 and self.prf_interval:
            return self.prf_interval
        return "-".join(MONTH_ABBR[m - 1] for m in self.months)

    @property
    def prf_interval(self) -> str | None:
        for name, mm in INTERVAL_MONTHS.items():
            if tuple(mm) == tuple(self.months):
                return name
        return None


def window_from_label(label: str, share: float) -> Window:
    """'Apr-May' -> PRF interval; 'Jul' -> one month; 'Jun-Aug' -> June to August."""
    if label in INTERVAL_MONTHS:
        return Window(tuple(INTERVAL_MONTHS[label]), float(share))
    parts = [MONTH_ABBR.index(p.strip()[:3].title()) + 1 for p in label.split("-")]
    if len(parts) == 1:
        return Window((parts[0],), float(share))
    a, b = parts[0], parts[-1]
    months = tuple(range(a, b + 1)) if b >= a else tuple(list(range(a, 13)) + list(range(1, b + 1)))
    return Window(months, float(share))


@dataclass
class CoverageRequest:
    lat: float
    lon: float
    windows: list            # list[Window]
    coverage: float = 0.9    # 0.70-0.90 like PRF (any value 0.5-1.0 accepted)
    protection: float = 100_000.0   # total dollars of protection across windows
    station_key: str | None = None  # None = nearest station with data
    strikes: str | Sequence[float] = "kalshi"   # "kalshi", "fine" (0.25 in), or explicit list
    grid_id: int | None = None       # override the grid (e.g. a farm's official grid)


@dataclass
class HedgeProblem:
    request: CoverageRequest
    grid_id: int
    grid_center: tuple
    station: dict
    distance_mi: float
    years: np.ndarray
    target: np.ndarray            # dollars per year (NaN where unknown)
    target_by_window: dict        # label -> dollars per year
    X: np.ndarray                 # years x legs NO payoffs
    legs: list                    # [(month, strike)]
    q: np.ndarray                 # fair NO probability per leg over FAIR_WINDOW
    notes: list = field(default_factory=list)

    @property
    def ok(self) -> np.ndarray:
        return ~np.isnan(self.target) & ~np.isnan(self.X).any(axis=1)

    def legs_frame(self, contracts=None) -> pd.DataFrame:
        d = pd.DataFrame(self.legs, columns=["contract_month", "strike_in"])
        d["month_name"] = [MONTH_ABBR[m - 1] for m in d["contract_month"]]
        d["q"] = self.q
        if contracts is not None:
            d["contracts"] = np.asarray(contracts, float)
        return d


def nearest_stations(lat: float, lon: float, k: int = 3) -> pd.DataFrame:
    st = station_table().copy()
    st["distance_mi"] = [haversine_miles(lat, lon, a, b) for a, b in zip(st["lat"], st["lon"])]
    return st.sort_values("distance_mi").head(k).reset_index(drop=True)


def window_target_per_dollar(grid_id: int, w: Window, coverage: float, years: np.ndarray) -> np.ndarray:
    """PRF payment factor per $1 of the window's protection, by year (NaN if data are missing)."""
    trig = float(trigger_grid_index(coverage))
    if w.prf_interval:
        idx = grid_interval_index(grid_id)[w.prf_interval].reindex(years).to_numpy(float)
    else:
        gm = grid_monthly(grid_id)
        tot = gm[list(w.months)].sum(axis=1, min_count=len(w.months))
        base = tot[(tot.index >= NORMAL_YEARS[0]) & (tot.index <= NORMAL_YEARS[1])].mean()
        idx = (100.0 * tot / base).reindex(years).to_numpy(float)
    out = payment_calculation_factor(idx, trig, decimals=None)
    return np.where(np.isnan(idx), np.nan, np.asarray(out, float))


def strike_set(series: str, month: int, strikes) -> tuple:
    if isinstance(strikes, str):
        if strikes == "kalshi":
            return tuple(listed_strikes(series)[month])
        if strikes == "fine":
            return tuple(np.round(np.arange(0.25, 12.01, 0.25), 2))
        if strikes == "half":
            return tuple(np.round(np.arange(0.5, 12.01, 0.5), 2))
        raise ValueError(f"unknown strike set {strikes!r}")
    return tuple(float(s) for s in strikes)


def build_problem(req: CoverageRequest, years: tuple = YEARS) -> HedgeProblem:
    """Assemble target payouts and the NO-contract payoff matrix for one request."""
    notes = []
    gid = int(req.grid_id) if req.grid_id is not None else latlon_to_grid_id(req.lat, req.lon)
    if gid not in covered_grids():
        raise ValueError(f"No gridded rainfall in the repo for PRF grid {gid} (lat {req.lat}, lon {req.lon}). "
                         f"Coverage is limited to grids within {MAX_STATION_MI:.0f} miles of the study stations.")
    if req.station_key:
        st = station_table().set_index("station_key").loc[req.station_key].to_dict()
        st["station_key"] = req.station_key
        dist = haversine_miles(req.lat, req.lon, st["lat"], st["lon"])
    else:
        nn = nearest_stations(req.lat, req.lon, 1).iloc[0]
        st, dist = nn.to_dict(), float(nn["distance_mi"])
    if dist > MAX_STATION_MI:
        notes.append(f"Nearest Kalshi rain station is {dist:.0f} miles away; expect large basis risk.")
    yrs = np.arange(years[0], years[1] + 1)
    shares = np.array([w.share for w in req.windows], float)
    if abs(shares.sum() - 1.0) > 1e-6:
        notes.append(f"Window shares sum to {shares.sum():.2f}; protection is split in those proportions.")
    tgt_w, total = {}, np.zeros(len(yrs))
    for w in req.windows:
        pdol = window_target_per_dollar(gid, w, req.coverage, yrs) * w.share * req.protection
        tgt_w[w.label] = pdol
        total = total + pdol
    rain = station_rain(st["station_key"]).reindex(yrs)
    months = sorted({m for w in req.windows for m in w.months})
    cols, legs, q = [], [], []
    for m in months:
        for k in strike_set(st["series_ticker"], m, req.strikes):
            cols.append(no_pays(rain[m].to_numpy(), k))
            legs.append((m, float(k)))
            q.append(leg_probability(station_rain(st["station_key"]), m, k, FAIR_WINDOW))
    X = np.column_stack(cols) if cols else np.zeros((len(yrs), 0))
    n_ok = int((~np.isnan(total) & ~np.isnan(X).any(axis=1)).sum())
    if n_ok < 40:
        notes.append(f"Station {st['station_key']} has only {n_ok} complete years for these months; "
                     "the backtest and the out-of-sample score are unreliable.")
    return HedgeProblem(req, gid, grid_id_to_center(gid), st, float(dist), yrs, total, tgt_w, X, legs,
                        np.asarray(q, float), notes)


def add_columns(prob: HedgeProblem, payoffs: np.ndarray, legs: list, q) -> HedgeProblem:
    """Copy of a problem with extra instrument columns (used for proposed new contracts)."""
    return HedgeProblem(prob.request, prob.grid_id, prob.grid_center, prob.station, prob.distance_mi, prob.years,
                        prob.target, prob.target_by_window, np.column_stack([prob.X, payoffs]),
                        prob.legs + list(legs), np.concatenate([prob.q, np.asarray(q, float)]), list(prob.notes))


def replace_columns(prob: HedgeProblem, payoffs: np.ndarray, legs: list, q) -> HedgeProblem:
    """Copy of a problem whose instruments are replaced by `payoffs`."""
    return HedgeProblem(prob.request, prob.grid_id, prob.grid_center, prob.station, prob.distance_mi, prob.years,
                        prob.target, prob.target_by_window, np.asarray(payoffs, float), list(legs),
                        np.asarray(q, float), list(prob.notes))


# ---------------------------------------------------------------------------------------------
# The 11 representative farms (data/scenarios/farms.yaml)
# ---------------------------------------------------------------------------------------------

def load_farm_requests(strikes="kalshi") -> list[dict]:
    """One entry per representative farm: its CoverageRequest plus its PRF terms.

    The grid is the farm's PRF grid (study_grids role = farm, as in prf_scenario_results.csv),
    the station is its study site's Kalshi station, protection and premiums are the 2026 terms
    from doc 04b, and `prf_ncei_usd` is the PRF indemnity by year on the NCEI index (official
    Decision Support Tool history) for comparison with the rebuilt target.
    """
    import yaml
    from agri_hedge.config import SCENARIOS
    farms = yaml.safe_load((SCENARIOS / "farms.yaml").read_text(encoding="utf-8"))["farms"]
    sc = pd.read_csv(PROCESSED / "prf_scenario_results.csv", dtype={"grid_id": str, "county_fips": str})
    out = []
    for f in farms:
        s = sc[sc["farm_id"] == f["farm_id"]].set_index("year").sort_index()
        site = f["site"]
        station = "ORD" if site == "ORD" else site
        req = CoverageRequest(float(f["lat"]), float(f["lon"]),
                              [window_from_label(k, v) for k, v in f["interval_allocation"].items()],
                              float(f["coverage_level"]), float(s["policy_protection_usd"].iloc[0]),
                              station_key=station, strikes=strikes, grid_id=int(s["grid_id"].iloc[0]))
        out.append({"farm": f, "farm_id": f["farm_id"], "site": site, "request": req,
                    "protection": float(s["policy_protection_usd"].iloc[0]),
                    "producer_premium": float(s["producer_premium_usd"].iloc[0]),
                    "total_premium": float(s["total_premium_usd"].iloc[0]),
                    "prf_ncei_usd": s["indemnity_usd"]})
    return out
