"""Expansion study: a loss-based demand estimate for station-settled weather hedges (doc 25).

Question: given what rain (and snow) costs each kind of firm, how much hedge premium would firms pay a
year, how does wet-side demand compare with the dry-side (rancher) demand it would net against, and
how much of it could Kalshi's resting order book fill? Every central value is an educated guess with
a low-high band; inputs marked "assumption" below are labeled as such in doc 25's numbers table.

Pipeline (one row per segment x station/club/farm x calendar month)
  1. Loss per firm-month, 1991-2025, from each Kalshi station's daily ACIS record (run_expansion_netting
     cache) or from the saved loss studies:
       restaurants, bars   OpenTable rain-bin x season effects (rain_reservations_effects.csv, live sample,
                           combined) applied to each day's station rain, x the city's shrunk scale
                           (rain_reservations_city_month_loss.csv), x sales per firm (demand_inputs.csv
                           metro rows), x contribution margin 0.65 (assumption)
       golf                monthly revenue x 2.2% of rounds per inch of rain above the month's mean x 0.7
                           contribution margin (assumption); playable months = station mean temp >= 50 F
       construction        excess wet workdays (>= 0.10 in, x 5/7) above the month's median x $1,250 per day
                           (= $2,500 liquidated damages x 50% of firm-months with an exposed project; assumption)
       snow cities         snow budget x (month's snowfall - its mean) / mean season snowfall (spend
                           proportional to snowfall; budgets from demand_inputs.csv or assumption)
       MLB clubs           rain_venues_team_month_loss.csv (gamma fitted to mean and p95 per club-month)
                           x 0.5 net of revenue sharing and concession costs (assumption)
       MiLB clubs          the median MLB club-month scaled by fans x revenue per fan (3,847 x $30 vs
                           29,816 x $57; assumption-heavy)
       ranchers (dry)      PRF Companion packages (m2_companion_farms.csv) scaled to the state's average
                           PRF policy, allocated to Kalshi stations by an assumed share of each state's policies
  2. Contract: a call on the station index (wet-day count; monthly rain for golf; monthly snow for cities)
     struck at the median and capped at the 95th percentile, sized by OLS on the firm's loss (expected
     excess loss given the index). Hedge effectiveness (HE) = variance removed. A firm sits rho_f away from
     the city/station loss (gauge distance, own sensitivity), so it buys rho_f x the station hedge and
     keeps HE_firm = rho_f^2 x HE_station. MLB uses its own loss-index correlation (0.52 wet home dates).
     Ranchers keep the Companion's out-of-sample HE (doc 21).
  3. Willingness to pay: CRRA gamma on wealth W. Losses are small next to W, so the CARA expansion
     WTP multiple = 1 + (gamma / W) * HE_firm * Var(L) / (2 E[H]) is used (checked against exact CRRA for
     restaurants). Broad frame (central): W = cash buffer + one month's profit. Narrow frame (behavioral
     ceiling): W = one month's operating profit (a city: its snow budget). Ranchers: WTP read off doc 24's
     utility-optimal contracts (m2_design_optimal.csv, the load at which the CE gain reaches zero).
  4. Take-up = t0 x m^elasticity x S(m), S = share of firms whose WTP exceeds the price multiple m, with
     gamma and W lognormal across firms (sd of logs 0.7 and 1.0; assumption). Standalone: t0 0.20, m 1.2
     (Kalshi all-in, doc 24). Embedded (POS, booking, lender): t0 0.45, m 1.3.
  5. Demand = firms x take-up x [premium = m E[H]; max payout; $1 contracts = max payout].
     Kalshi-23 = the 23 metros in demand_inputs.csv; national scales per-firm results by firm counts.
  6. Wet vs dry at stations that have both, Nov-Feb; November demand vs the Nov 2 (and Oct 29) books.
  7. Bands: 400 Monte Carlo draws of all parameters (triangular low/central/high), P10-P90; and a
     one-at-a-time tornado.

Outputs (data/processed/):
  weather_demand_city_month.csv    one row per segment x geography x month (Kalshi-23 scope)
  weather_demand_segment.csv       segment totals, Kalshi-23 and national, central + P10/P90, wet/dry ratio
  weather_demand_sensitivity.csv   one-at-a-time swings on three headline outputs
  weather_demand_depth.csv         November demand vs Kalshi resting depth per station
Figure: docs/figures/weather_demand.png

Usage: python scripts/run_weather_demand.py [--offline]   (about 5 s once the ACIS cache exists)
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
from scipy import optimize, stats

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_expansion_netting as rx  # noqa: E402

from agri_hedge.config import FIGURES, PROCESSED  # noqa: E402

CLIMO = (1991, 2025)
SEED = 473
N_MC = 400
WET_IN = 0.10
RAIN_BINS = [(0.01, 0.10, "r_lt010"), (0.10, 0.50, "r_010_050"), (0.50, 99.0, "r_ge050")]
WARM_MONTHS = (5, 6, 7, 8, 9, 10)
NOV_FEB = (11, 12, 1, 2)

# ---------------------------------------------------------------------------------------------
# parameters: (low, central, high). Sources in doc 25's numbers table; "a" = team assumption.
# ---------------------------------------------------------------------------------------------
P = {
    "m_standalone": (1.1, 1.2, 1.6),     # price / expected payout; 1.2 = Kalshi all-in (doc 24); 1.6 insurance line
    "m_embedded": (1.2, 1.3, 1.6),       # a: Kalshi 1.2 + ~10% distributor margin
    "t0_standalone": (0.10, 0.20, 0.35),  # take-up at fair price: CME 10% hedgers .. BI cover 35%
    "t0_embedded": (0.30, 0.45, 0.60),    # Ghana fair-price 0.40-0.50; Sensible attach claims
    "elasticity": (-2.5, -0.77, -0.66),   # Cole et al. -0.66..-0.88; Ghana arc about -2.5
    "gamma_med": (1.0, 2.0, 4.0),         # CRRA, doc 24 base 2
    "sd_ln_gamma": (0.7, 0.7, 0.7),       # a: firm dispersion of risk aversion
    "sd_ln_wealth": (1.0, 1.0, 1.0),      # a: firm dispersion of cash (JPMC quartiles, unverified)
    "rest_effect": (None, 1.0, None),     # x headline effect; CI ratios read from the loss CSV
    "rest_sales": (1.0, 1.8, 2.3),        # $M/yr per full-service restaurant (central = metro values)
    "rest_contrib": (0.55, 0.65, 0.70),   # contribution margin on lost sales (a)
    "rest_margin": (0.028, 0.028, 0.04),  # pre-tax margin, NRA FY2024 2.8% / 2019 4.0%
    "rest_buffer": (12.0, 16.0, 27.0),    # cash buffer days, JPMC
    "rest_rebound": (0.5, 1.0, 1.0),      # net / gross loss (live sample: no rebound)
    "rho_rest": (0.6, 0.8, 0.9),          # a: firm vs city-airport loss correlation
    "rho_golf": (0.5, 0.7, 0.85),         # a: facility vs station monthly-rain loss
    "rho_constr": (0.6, 0.8, 0.9),        # a: site vs station wet-day count
    "rho_snow": (0.7, 0.85, 0.95),        # a: city plowing cost vs airport snowfall
    "venue_rho_mult": (None, 1.0, 1.118),  # x corr(loss, wet home dates); low = monthly-total corr; high = HE x1.25
    "mlb_contrib": (0.4, 0.5, 0.7),       # a: net of revenue sharing and concession costs
    "mlb_wealth": (15e6, 30e6, 60e6),     # a: about one month of club revenue
    "mlb_profit_month": (2.5e6, 2.5e6, 2.5e6),  # a: narrow frame
    "milb_rev_fan": (20.0, 30.0, 40.0),   # demand_inputs (assumption)
    "golf_rev_bn": (20.0, 32.0, 45.0),    # on-course revenue, demand_inputs
    "golf_per_inch": (0.015, 0.022, 0.03),  # rounds lost per extra inch
    "constr_cost": (250.0, 1250.0, 2500.0),  # $ per excess wet workday (a)
    "constr_share": (0.05, 0.08, 0.10),   # share of establishments able to hedge (a)
    "snow_budget_mult": (0.6, 1.0, 1.5),  # x city snow budgets (mostly assumption)
    "ranch_share_mult": (0.5, 1.0, 1.5),  # x assumed share of state PRF policies near each station
}
C = {k: v[1] for k, v in P.items()}

GOLF_CONTRIB, GOLF_MARGIN, GOLF_BUFFER = 0.7, 0.10, 30.0          # a
CONSTR_REV, CONSTR_MARGIN, CONSTR_BUFFER = 8e6, 0.05, 30.0         # a
SNOW_RESERVE_MULT = 10.0                                            # a: broad W = 10 x snow budget
MILB_TEAMS, MILB_FANS_GAME, MILB_K23_SHARE, MILB_CONTRIB, MILB_MARGIN = 120, 3847, 0.2, 0.7, 0.10
MLB_AVG_FANS, MLB_USD_FAN = 29816, 57.0
GOLF_FACILITIES, GOLF_K23_SHARE = 14000, 0.25
CONSTR_ESTABS = 938478
RANCH_ELIGIBLE = 0.8          # share of near-station grids with a recommended package (m2_companion_sweep, <= 60 mi)
GRID_W = {1.0: 0.25, 2.0: 0.5, 4.0: 0.25}    # rancher gamma weights (doc 24 grid)
GRID_WEALTH = {1.25: 0.25, 2.0: 0.5, 4.0: 0.25}

# metro (demand_inputs name) -> (Kalshi station, OpenTable city or None)
METROS = {
    "New York": ("NYC", "new_york"), "Chicago": ("ORD", "chicago"), "Los Angeles": ("LAX", "los_angeles"),
    "Miami": ("MIA", "miami"), "Houston": ("HOU", "houston"), "Dallas-Fort Worth": ("DFW", "dallas"),
    "Austin": ("AUS", "austin"), "San Antonio": ("SAT", "san_antonio"), "Atlanta": ("ATL", "atlanta"),
    "Boston": ("BOS", "boston"), "Philadelphia": ("PHL", "philadelphia"), "Washington DC": ("DCA", "washington"),
    "Denver": ("DEN", "denver"), "Seattle": ("SEA", "seattle"), "Phoenix": ("PHX", "phoenix"),
    "Las Vegas": ("LAS", "las_vegas"), "New Orleans": ("MSY", "new_orleans"), "Minneapolis": ("MSP", "minneapolis"),
    "Detroit": ("DTW", None), "San Francisco": ("SFO", "san_francisco"), "Oklahoma City": ("OKC", None),
    "St. Louis": ("STL", "st_louis"), "Tampa": ("TPA", "tampa"),
}
SCALE_PROXY = {"Detroit": "midwest", "Oklahoma City": "texas_sw"}   # region-mean city scale
# Kalshi snow cities: station -> (snow budget $M, status)
SNOW_CITIES = {"NYC": (100, "demand_inputs"), "ORD": (25, "assumption (demand_inputs)"),
               "BOS": (20, "assumption"), "DCA": (6, "assumption"), "DEN": (10, "assumption (demand_inputs)"),
               "DTW": (8, "assumption"), "MKE": (8, "assumption"), "MSP": (12, "demand_inputs"),
               "PHL": (4.1, "demand_inputs (unverified)"), "PIT": (5, "assumption"), "SEA": (3, "assumption"),
               "TTN": (1, "assumption"), "SLC": (4, "assumption")}
K23_SNOW = {"NYC", "ORD", "BOS", "DCA", "DEN", "DTW", "MSP", "PHL", "SEA"}
# MLB club station -> Kalshi-23 station (None = outside the 23 metros)
CLUB_K23 = {"LGA": "NYC", "PHL": "PHL", "ATL": "ATL", "BOS": "BOS", "ORD": "ORD", "MDW": "ORD", "STL": "STL",
            "DTW": "DTW", "DEN": "DEN", "MSP": "MSP", "DCA": "DCA", "SFO": "SFO", "LAX": "LAX", "SNA": "LAX"}
# rancher stations: station -> (state, assumed share of the state's PRF policies within ~60 mi, rep farms)
RANCH = {"DFW": ("TX", 0.10, ["DFW_hay", "DFW_graze"]), "AUS": ("TX", 0.05, ["SAT_graze"]),
         "SAT": ("TX", 0.07, ["SAT_graze"]), "HOU": ("TX", 0.03, ["DFW_hay", "DFW_graze"]),
         "CLL": ("TX", 0.04, ["DFW_hay", "DFW_graze"]), "OKC": ("OK", 0.30, ["OKC_hay", "OKC_graze"]),
         "SGF": ("MO", 0.40, ["SGF_hay", "SGF_graze"]), "STL": ("MO", 0.10, ["SGF_hay", "SGF_graze"]),
         "TPA": ("FL", 0.20, ["TPA_hay", "TPA_graze"]), "DEN": ("CO", 0.20, ["DEN_graze"]),
         "ABQ": ("NM", 0.10, ["ABQ_graze"])}
MONTHS = {m: i for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct",
                                       "Nov", "Dec"], start=1)}
WET_SEGMENTS = ["restaurants", "bars", "construction", "golf", "mlb", "milb"]
LABEL = {"restaurants": "Full-service restaurants", "bars": "Bars (drinking places)",
         "construction": "Construction contractors (>= 20 staff)", "golf": "Golf facilities",
         "mlb": "MLB open-air clubs", "milb": "MiLB clubs (scaled from MLB)", "snow_city": "Snow-belt cities",
         "ranchers": "Dryland ranchers (Companion months)"}


# ---------------------------------------------------------------------------------------------
# inputs
# ---------------------------------------------------------------------------------------------
def demand_inputs() -> pd.DataFrame:
    return pd.read_csv(PROCESSED / "demand_inputs.csv")


def metro_table(di: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for metro in METROS:
        def val(kind, code):
            r = di[di["parameter"] == f"{metro}: {kind} ({code})"]
            return float(r["central"].iloc[0])
        rows.append({"metro": metro, "station": METROS[metro][0], "city": METROS[metro][1],
                     "rest_firms": val("full-service establishments", 722511),
                     "rest_sales_musd": val("full-service sales", 722511),
                     "bar_firms": val("drinking places establishments", 722410),
                     "bar_sales_musd": val("drinking places sales", 722410)})
    m = pd.DataFrame(rows)
    m["rest_sales_firm"] = m["rest_sales_musd"] * 1e6 / m["rest_firms"]
    m["bar_sales_firm"] = m["bar_sales_musd"] * 1e6 / m["bar_firms"]
    return m


def restaurant_effects() -> tuple[dict, float, float]:
    e = pd.read_csv(PROCESSED / "rain_reservations_effects.csv")
    e = e[(e["sample"] == "live_2025_26") & (e["spec"] == "bins_x_season") & (e["era"] == "combined (GLS of both)")]
    b = {r["group"]: float(r["effect_log"]) for _, r in e.iterrows()}
    loss = pd.read_csv(PROCESSED / "rain_reservations_city_month_loss.csv")
    lo = float((loss["pct_lost_mean_ci_lo"] / loss["pct_lost_mean"]).median())
    hi = float((loss["pct_lost_mean_ci_hi"] / loss["pct_lost_mean"]).median())
    return b, lo, hi


def city_scales() -> dict:
    loss = pd.read_csv(PROCESSED / "rain_reservations_city_month_loss.csv")
    s = loss.groupby("city")[["city_scale", "region"]].first()
    out = s["city_scale"].to_dict()
    for metro, region in SCALE_PROXY.items():
        out[f"region:{region}"] = float(s[s["region"] == region]["city_scale"].mean())
    return out


def station_months(offline: bool, beff: dict) -> pd.DataFrame:
    """Station x year x month weather and the restaurant loss fraction, 1991-2025."""
    need = {v[0] for v in METROS.values()} | set(SNOW_CITIES) | set(RANCH)
    st = rx.station_list()
    parts = []
    for _, s in st[st["station_key"].isin(need)].iterrows():
        d = rx.fetch_daily(s, offline)
        if d is not None:
            parts.append(d)
    if not parts:
        raise SystemExit("no ACIS daily data: run scripts/run_expansion_netting.py once online")
    d = pd.concat(parts, ignore_index=True)
    d = d[d["date"].dt.year.between(*CLIMO)].copy()
    d["year"], d["month"] = d["date"].dt.year, d["date"].dt.month
    warm = d["month"].isin(WARM_MONTHS).to_numpy().astype(int)
    pc = d["pcpn"].to_numpy()
    lf = np.zeros(len(d))
    for lo, hi, name in RAIN_BINS:
        m = (pc >= lo) & (pc < hi)
        for w in (0, 1):
            lf[m & (warm == w)] = 1 - np.exp(beff[f"{name} warm={w}"])
    lf[np.isnan(pc)] = np.nan
    d["rest_lf"] = lf
    d["wet"] = np.where(np.isnan(pc), np.nan, pc >= WET_IN)
    g = d.groupby(["station_key", "year", "month"])
    ym = pd.DataFrame({"n_days": g["date"].size(), "n_obs": g["pcpn"].count(), "rain_in": g["pcpn"].sum(),
                       "wet": g["wet"].mean(), "rest_lf": g["rest_lf"].mean(),
                       "snow_obs": g["snow"].count(), "snow_in": g["snow"].sum(), "temp_f": g["avgt"].mean()}
                      ).reset_index()
    ym = ym[ym["n_days"] - ym["n_obs"] <= 2].copy()
    ym["wet_days"] = ym["wet"] * ym["n_days"]
    ym["rain_in"] = ym["rain_in"] * ym["n_days"] / ym["n_obs"]
    ym.loc[ym["n_days"] - ym["snow_obs"] > 2, "snow_in"] = np.nan
    return ym


# ---------------------------------------------------------------------------------------------
# contract fit: call on the index, median strike, p95 cap, OLS size
# ---------------------------------------------------------------------------------------------
def fit_call(loss: np.ndarray, x: np.ndarray) -> dict:
    ok = ~(np.isnan(loss) | np.isnan(x))
    loss, x = loss[ok], x[ok]
    k, cap = np.quantile(x, 0.5), np.quantile(x, 0.95)
    if cap <= k:
        cap = x.max()
    c = np.clip(x - k, 0, max(cap - k, 0))
    vl, vc = loss.var(), c.var()
    out = {"n_years": int(ok.sum()), "mu": loss.mean(), "sd": np.sqrt(vl), "p95": np.quantile(loss, 0.95),
           "excess_mean": np.clip(loss - np.median(loss), 0, None).mean() if loss.min() < 0 else loss.mean(),
           "strike": k, "cap": cap, "eh": 0.0, "maxpay": 0.0, "he_s": 0.0}
    if vc <= 0 or vl <= 0:
        return out
    beta = np.cov(loss, c, bias=True)[0, 1] / vc
    if beta <= 0:
        return out
    h = beta * c
    out.update({"eh": h.mean(), "maxpay": beta * (cap - k), "he_s": 1 - np.var(loss - h) / vl})
    return out


def he_listed(loss: np.ndarray, rain: np.ndarray) -> float:
    return fit_call(loss, rain)["he_s"]


# ---------------------------------------------------------------------------------------------
# rows
# ---------------------------------------------------------------------------------------------
def rows_restaurants(ym, metros, scales) -> list[dict]:
    out = []
    for _, mt in metros.iterrows():
        cs = scales[mt["city"]] if isinstance(mt["city"], str) else scales[f"region:{SCALE_PROXY[mt['metro']]}"]
        for seg, firms, sales in (("restaurants", mt["rest_firms"], mt["rest_sales_firm"]),
                                  ("bars", mt["bar_firms"], mt["bar_sales_firm"])):
            for mo in range(1, 13):
                x = ym[(ym["station_key"] == mt["station"]) & (ym["month"] == mo)]
                days = float(x["n_days"].median())
                loss = (sales * days / 365 * cs * x["rest_lf"] * C["rest_contrib"] * C["rest_rebound"]).to_numpy()
                f = fit_call(loss, x["wet_days"].to_numpy())
                f["he_listed_s"] = he_listed(loss, x["rain_in"].to_numpy())
                f["pct_sales_lost_mean"] = 100 * float((cs * x["rest_lf"]).mean())
                out.append({"segment": seg, "geo": mt["metro"], "station": mt["station"], "month": mo,
                            "index": "wet days >= 0.10 in (day-count)", "firms": firms, "annual_rev": sales,
                            "city_scale": cs, **f})
    return out


def rows_golf(ym, metros) -> list[dict]:
    out = []
    share = metros["rest_firms"] / metros["rest_firms"].sum()
    rev = C["golf_rev_bn"] * 1e9 / GOLF_FACILITIES
    for (_, mt), sh in zip(metros.iterrows(), share):
        xs = ym[ym["station_key"] == mt["station"]]
        play = [mo for mo in range(1, 13) if xs[xs["month"] == mo]["temp_f"].mean() >= 50]
        for mo in play:
            x = xs[xs["month"] == mo]
            loss = (rev / len(play) * C["golf_per_inch"] * (x["rain_in"] - x["rain_in"].mean()) * GOLF_CONTRIB).to_numpy()
            f = fit_call(loss, x["rain_in"].to_numpy())
            f["he_listed_s"] = f["he_s"]
            out.append({"segment": "golf", "geo": mt["metro"], "station": mt["station"], "month": mo,
                        "index": "monthly rain (listed)", "firms": GOLF_FACILITIES * GOLF_K23_SHARE * sh,
                        "annual_rev": rev, "play_months": len(play), **f})
    return out


def rows_construction(ym, metros) -> list[dict]:
    out = []
    share = metros["rest_firms"] / 264208       # metro share of national activity, proxied by restaurants (a)
    for (_, mt), sh in zip(metros.iterrows(), share):
        for mo in range(1, 13):
            x = ym[(ym["station_key"] == mt["station"]) & (ym["month"] == mo)]
            wd = x["wet_days"].to_numpy() * 5 / 7
            loss = C["constr_cost"] * np.clip(wd - np.median(wd), 0, None)
            f = fit_call(loss, x["wet_days"].to_numpy())
            f["he_listed_s"] = he_listed(loss, x["rain_in"].to_numpy())
            out.append({"segment": "construction", "geo": mt["metro"], "station": mt["station"], "month": mo,
                        "index": "wet days >= 0.10 in (day-count)",
                        "firms": CONSTR_ESTABS * C["constr_share"] * sh, "annual_rev": CONSTR_REV, **f})
    return out


def rows_snow(ym) -> list[dict]:
    out = []
    for st, (budget, status) in SNOW_CITIES.items():
        xs = ym[(ym["station_key"] == st) & ym["month"].isin(rx.SNOW_MONTHS)].dropna(subset=["snow_in"])
        if xs.empty:
            continue
        mean_m = xs.groupby("month")["snow_in"].mean()
        season = float(mean_m.sum())
        for mo, mm in mean_m.items():
            if mm < 1.0:
                continue
            x = xs[xs["month"] == mo]
            loss = (budget * 1e6 * (x["snow_in"] - mm) / season).to_numpy()
            f = fit_call(loss, x["snow_in"].to_numpy())
            f["he_listed_s"] = f["he_s"]
            out.append({"segment": "snow_city", "geo": st, "station": st, "month": int(mo),
                        "index": "monthly snowfall (listed)", "firms": 1.0, "budget": budget * 1e6,
                        "budget_status": status, "k23": st in K23_SNOW, **f})
    return out


def gamma_from_mean_p95(mean: float, p95: float) -> tuple[float, float]:
    def gap(k):
        return stats.gamma.ppf(0.95, k, scale=mean / k) - p95
    lo, hi = 0.05, 60.0
    if gap(lo) * gap(hi) > 0:
        k = 1.0
    else:
        k = optimize.brentq(gap, lo, hi)
    return k, mean / k


def self_call(mean: float, p95: float, rng) -> dict:
    """Capped call on the club's own loss (rho = 1); basis enters through rho_f later."""
    k, sc = gamma_from_mean_p95(mean, p95)
    loss = rng.gamma(k, sc, 20000)
    f = fit_call(loss, loss)
    f["gamma_shape"] = k
    return f


def rows_venues(rng) -> list[dict]:
    L = pd.read_csv(PROCESSED / "rain_venues_team_month_loss.csv")
    out = []
    for _, r in L.iterrows():
        f = self_call(r["mean_usd"] * C["mlb_contrib"], r["p95_usd"] * C["mlb_contrib"], rng)
        out.append({"segment": "mlb", "geo": r["team"], "station": CLUB_K23.get(r["station"]), "club_station": r["station"],
                    "month": int(r["month"]), "index": "wet home dates (OTC day-count)", "firms": 1.0,
                    "rho_index": r["corr_simulated_loss_vs_wet_home_days"],
                    "rho_listed": r["corr_simulated_loss_vs_month_rain"], **f})
    med = L.groupby("month")[["mean_usd", "p95_usd", "corr_simulated_loss_vs_wet_home_days",
                              "corr_simulated_loss_vs_month_rain"]].median()
    s = MILB_FANS_GAME * C["milb_rev_fan"] / (MLB_AVG_FANS * MLB_USD_FAN)
    for mo, r in med.iterrows():
        f = self_call(r["mean_usd"] * s * MILB_CONTRIB, r["p95_usd"] * s * MILB_CONTRIB, rng)
        out.append({"segment": "milb", "geo": "MiLB (national)", "station": None, "month": int(mo),
                    "index": "wet home dates (OTC day-count)", "firms": float(MILB_TEAMS),
                    "rho_index": r["corr_simulated_loss_vs_wet_home_days"],
                    "rho_listed": r["corr_simulated_loss_vs_month_rain"], "milb_scale": s, **f})
    return out


def rancher_wtp() -> pd.DataFrame:
    """Max load multiple at which doc 24's utility-optimal contract still has a positive CE gain."""
    d = pd.read_csv(PROCESSED / "m2_design_optimal.csv")
    d = d[(d["target"] == "linear")]
    rows = []
    for (farm, month, kind, g, w), x in d.groupby(["farm_id", "month", "kind", "gamma", "wealth"]):
        x = x.sort_values("load")
        ld, gn = x["load"].to_numpy(), x["ce_gain_pct"].to_numpy()
        if gn[0] <= 1e-9:
            z = 0.0
        elif (gn > 1e-9).all():       # still positive at 0.3: extrapolate from the last two points (conservative)
            slope = (gn[-1] - gn[-2]) / (ld[-1] - ld[-2])
            z = ld[-1] + (gn[-1] / -slope if slope < 0 else 0.5)
            z = min(z, 1.0)
        else:
            i = int(np.argmax(gn <= 1e-9))
            z = ld[i - 1] + (ld[i] - ld[i - 1]) * gn[i - 1] / (gn[i - 1] - gn[i])
        rows.append({"farm_id": farm, "month": MONTHS[month], "kind": kind, "gamma": g, "wealth": w, "wtp": 1 + z})
    return pd.DataFrame(rows)


def rows_ranchers(wtp: pd.DataFrame) -> list[dict]:
    farms = pd.read_csv(PROCESSED / "m2_companion_farms.csv").set_index("farm_id")
    liq = pd.read_csv(PROCESSED / "m2_improve_liquidity.csv").drop_duplicates("farm_id").set_index("farm_id")
    sob = pd.read_csv(PROCESSED / "prf_summary_of_business_state.csv", dtype={"state_fips": str})
    sob = sob[sob["year"] == 2025].set_index("state_abbr")
    out = []
    for st, (state, share, reps) in RANCH.items():
        pol = float(sob.loc[state, "policies_earning_premium"])
        avg_prem = float(sob.loc[state, "producer_paid_premium"]) / pol
        for farm in reps:
            fr = farms.loc[farm]
            rec = [MONTHS[m.strip()] for m in str(fr["recommended"]).split(",")] if isinstance(fr["recommended"], str) else []
            months = rec if rec else [11, 12, 1, 2]
            scale = avg_prem / float(fr["prf_producer_premium_usd"])
            n = max(len(rec), 1)
            eh = float(fr["package_expected_payout_usd"]) / n * scale if rec else 0.0
            cont = float(liq.loc[farm, "contracts_needed"]) / n * scale if (rec and farm in liq.index) else 0.0
            loss_m = float(fr["gap_cover_expected_usd"]) / float(fr["uncovered_months"]) * scale if rec else np.nan
            for mo in months:
                w = wtp[(wtp["farm_id"] == farm) & (wtp["month"] == mo) & (wtp["kind"] == "open")]
                out.append({"segment": "ranchers", "geo": f"{st} ({farm})", "station": st, "month": mo,
                            "index": "monthly rain put (listed ladder)", "state": state, "rep_farm": farm,
                            "firms": pol * share * RANCH_ELIGIBLE / len(reps), "policy_scale": scale,
                            "mu": loss_m, "excess_mean": loss_m, "p95": np.nan, "eh": eh if mo in rec else 0.0,
                            "maxpay": cont if mo in rec else 0.0,
                            "he_s": float(fr["package_he_oos"]) if rec else 0.0,
                            "wtp_grid": {(r.gamma, r.wealth): r.wtp for r in w.itertuples()},
                            "proxy": st != farm.split("_")[0]})
    return out


# ---------------------------------------------------------------------------------------------
# evaluation (vectorized over rows; params can be swapped for sensitivity and Monte Carlo)
# ---------------------------------------------------------------------------------------------
def _screen(K, W, m, p) -> np.ndarray:
    s = np.sqrt(p["sd_ln_gamma"] ** 2 + p["sd_ln_wealth"] ** 2)
    with np.errstate(divide="ignore", invalid="ignore"):
        z = (np.log((m - 1) / K) - np.log(p["gamma_med"] / W)) / s
    out = 1 - stats.norm.cdf(z)
    out = np.where(K > 0, out, 0.0)
    return np.where(m <= 1, 1.0, out)


def rancher_screen(grid: dict, m: float, p: dict, frame: str) -> float:
    gw = GRID_W if p["gamma_med"] == 2.0 else {min(GRID_W, key=lambda g: abs(g - p["gamma_med"])): 1.0}
    ww = {"broad": GRID_WEALTH, "rational": {4.0: 1.0}, "narrow": {1.25: 1.0}}[frame]
    tot = num = 0.0
    for g, a in gw.items():
        for w, b in ww.items():
            if (g, w) in grid:
                tot += a * b
                num += a * b * (grid[(g, w)] > m)
    return num / tot if tot else 0.0


def evaluate(R: pd.DataFrame, p: dict, frame: str = "broad") -> pd.DataFrame:
    """frame: 'broad' = cash buffer + month's profit (central); 'narrow' = month's profit (behavioral)."""
    seg = R["segment"].to_numpy()
    lm = np.ones(len(R))           # loss multiplier vs the central build
    rho = np.ones(len(R))
    firms = R["firms"].to_numpy(dtype=float).copy()
    W = np.full(len(R), np.nan)
    rest = np.isin(seg, ["restaurants", "bars"])
    sm = p["rest_sales"] / C["rest_sales"]
    lm[rest] = sm * p["rest_contrib"] / C["rest_contrib"] * p["rest_effect"] * p["rest_rebound"] / C["rest_rebound"]
    rev = R["annual_rev"].to_numpy(dtype=float)
    if frame == "narrow":
        W[rest] = rev[rest] * sm * p["rest_margin"] / 12
    else:
        W[rest] = rev[rest] * sm * ((1 - p["rest_margin"]) * p["rest_buffer"] / 365 + p["rest_margin"] / 12)
    rho[rest] = p["rho_rest"]
    g = seg == "golf"
    gm = p["golf_rev_bn"] / C["golf_rev_bn"]
    lm[g] = gm * p["golf_per_inch"] / C["golf_per_inch"]
    W[g] = rev[g] * gm * (GOLF_MARGIN / 12 if frame == "narrow" else GOLF_BUFFER / 365 + GOLF_MARGIN / 12)
    rho[g] = p["rho_golf"]
    c = seg == "construction"
    lm[c] = p["constr_cost"] / C["constr_cost"]
    firms[c] *= p["constr_share"] / C["constr_share"]
    W[c] = CONSTR_REV * (CONSTR_MARGIN / 12 if frame == "narrow" else CONSTR_BUFFER / 365 + CONSTR_MARGIN / 12)
    rho[c] = p["rho_constr"]
    s = seg == "snow_city"
    lm[s] = p["snow_budget_mult"]
    bud = R["budget"].to_numpy(dtype=float)
    W[s] = bud[s] * p["snow_budget_mult"] * (1.0 if frame == "narrow" else SNOW_RESERVE_MULT)
    rho[s] = p["rho_snow"]
    v = np.isin(seg, ["mlb", "milb"])
    ri = R["rho_index"].to_numpy(dtype=float)
    vm = p["venue_rho_mult"]
    rho[v] = np.minimum(R["rho_listed"].to_numpy(dtype=float)[v] if vm is None else ri[v] * vm, 1.0)
    ml = seg == "mlb"
    lm[ml] = p["mlb_contrib"] / C["mlb_contrib"]
    W[ml] = p["mlb_profit_month"] if frame == "narrow" else p["mlb_wealth"]
    mi = seg == "milb"
    rm = p["milb_rev_fan"] / C["milb_rev_fan"]
    lm[mi] = rm
    milb_rev = MILB_FANS_GAME * 70 * C["milb_rev_fan"] * rm        # about 70 home dates a season (a)
    W[mi] = milb_rev * (MILB_MARGIN / 12 if frame == "narrow" else 1 / 12)
    rn = seg == "ranchers"
    firms[rn] *= p["ranch_share_mult"]

    eh_s, max_s, he_s, sd = (R[k].to_numpy(dtype=float) for k in ("eh", "maxpay", "he_s", "sd"))
    out = pd.DataFrame(index=R.index)
    out["firms"] = firms
    out["rho_f"] = np.where(rn, np.nan, rho)
    out["he_firm"] = np.where(rn, he_s, rho ** 2 * he_s)
    out["eh_firm"] = np.where(rn, eh_s, rho * eh_s * lm)
    out["maxpay_firm"] = np.where(rn, max_s, rho * max_s * lm)
    out["loss_mean"] = R["mu"].to_numpy(dtype=float) * np.where(rn, 1, lm)
    out["loss_excess_mean"] = R["excess_mean"].to_numpy(dtype=float) * np.where(rn, 1, lm)
    out["loss_p95"] = R["p95"].to_numpy(dtype=float) * np.where(rn, 1, lm)
    with np.errstate(divide="ignore", invalid="ignore"):
        K = np.where(eh_s > 0, rho * he_s * (sd * lm) ** 2 / (2 * eh_s * lm), 0.0)
    out["wealth"] = W
    out["wtp_multiple"] = np.where(rn, np.nan, 1 + p["gamma_med"] / W * K)
    for ch in ("standalone", "embedded"):
        m = p[f"m_{ch}"]
        S = _screen(K, W, m, p)
        if rn.any():
            fr = {"broad": "broad", "narrow": "narrow", "rational": "rational"}[frame]
            S[rn] = [rancher_screen(gr, m, p, fr) if e > 0 else 0.0
                     for gr, e in zip(R.loc[rn, "wtp_grid"], eh_s[rn])]
        tu = p[f"t0_{ch}"] * m ** p["elasticity"] * S
        tu = np.where(out["eh_firm"] > 0, tu, 0.0)
        out[f"screen_{ch}"] = S
        out[f"takeup_{ch}"] = tu
        out[f"buyers_{ch}"] = firms * tu
        out[f"premium_{ch}"] = firms * tu * m * out["eh_firm"]
        out[f"notional_{ch}"] = firms * tu * out["maxpay_firm"]
    if rn.any():   # rancher representative WTP: doc 24 base (gamma 2, wealth 2)
        out.loc[rn, "wtp_multiple"] = [gr.get((2.0, 2.0), np.nan) for gr in R.loc[rn, "wtp_grid"]]
    return out


def crra_check(R: pd.DataFrame, ym: pd.DataFrame, rng) -> float:
    """Exact CRRA WTP for central restaurant rows vs the CARA expansion; returns the max abs gap."""
    ev = evaluate(R, C)
    gaps = []
    rr = R[R["segment"] == "restaurants"].sample(25, random_state=SEED)
    for i, r in rr.iterrows():
        x = ym[(ym["station_key"] == r["station"]) & (ym["month"] == r["month"])]
        days = float(x["n_days"].median())
        loss = (r["annual_rev"] * days / 365 * r["city_scale"] * x["rest_lf"] * C["rest_contrib"]).to_numpy()
        wd = x["wet_days"].to_numpy()
        k, cap = r["strike"], r["cap"]
        cc = np.clip(wd - k, 0, cap - k)
        h_s = cc * (r["maxpay"] / (cap - k) if cap > k else 0)
        rho = C["rho_rest"]
        eps = rng.standard_normal((len(loss), 200))
        L = loss.mean() + rho * (loss[:, None] - loss.mean()) + np.sqrt(1 - rho ** 2) * loss.std() * eps
        H = rho * h_s[:, None] * np.ones_like(eps)
        W = ev.loc[i, "wealth"]
        g = C["gamma_med"]
        u = lambda w: (w ** (1 - g) - 1) / (1 - g)  # noqa: E731
        base = u(W - L).mean()
        prem = H.mean()
        if prem <= 0:
            continue
        lo, hi = 0.5, 3.0
        for _ in range(60):
            mid = (lo + hi) / 2
            if u(W - L + H - mid * prem).mean() > base:
                lo = mid
            else:
                hi = mid
        gaps.append(abs(lo - ev.loc[i, "wtp_multiple"]))
    return float(max(gaps)) if gaps else float("nan")


# ---------------------------------------------------------------------------------------------
# aggregation
# ---------------------------------------------------------------------------------------------
NAT_FIRMS = {"restaurants": 264208, "bars": 42624}


def national_factor(R: pd.DataFrame) -> dict:
    f = {}
    for sg in ("restaurants", "bars"):
        k23 = R[(R["segment"] == sg) & (R["month"] == 1)]["firms"].sum()
        f[sg] = NAT_FIRMS[sg] / k23
    f["golf"] = 1 / GOLF_K23_SHARE
    f["construction"] = 264208 / R[(R["segment"] == "restaurants") & (R["month"] == 1)]["firms"].sum()
    f["mlb"], f["milb"], f["snow_city"], f["ranchers"] = 1.0, 1.0, 1.0, 1.0
    return f


def in_k23(R: pd.DataFrame) -> np.ndarray:
    seg = R["segment"].to_numpy()
    k = np.ones(len(R), dtype=bool)
    k[seg == "mlb"] = R.loc[seg == "mlb", "station"].notna().to_numpy()
    k[seg == "snow_city"] = R.loc[seg == "snow_city", "k23"].astype(bool).to_numpy()
    return k


def totals(R: pd.DataFrame, ev: pd.DataFrame, nat: dict) -> pd.DataFrame:
    """Premium / notional per segment x scope (k23, national)."""
    rows = []
    k23 = in_k23(R)
    for sg in list(LABEL):
        msk = (R["segment"] == sg).to_numpy()
        for scope in ("kalshi23", "national"):
            if sg == "milb":
                w = np.where(scope == "kalshi23", MILB_K23_SHARE, 1.0)
                mm = msk
            else:
                w = 1.0 if scope == "kalshi23" else nat[sg]
                mm = msk & k23 if scope == "kalshi23" else msk
            if sg == "mlb" and scope == "national":
                w = 1.0
            e = ev[mm]
            rows.append({"segment": sg, "scope": scope,
                         **{f"{k}_{ch}": float(e[f"{k}_{ch}"].sum()) * w
                            for k in ("premium", "notional", "buyers") for ch in ("standalone", "embedded")}})
    return pd.DataFrame(rows)


def wet_dry(R: pd.DataFrame, ev: pd.DataFrame) -> dict:
    """Wet vs dry demand, Nov-Feb, at stations that have both a Kalshi-23 metro and rancher demand."""
    shared = sorted(set(RANCH) & {v[0] for v in METROS.values()})
    msk = R["station"].isin(shared).to_numpy() & R["month"].isin(NOV_FEB).to_numpy()
    wet = msk & R["segment"].isin(["restaurants", "bars", "construction", "golf"]).to_numpy()
    dry = msk & (R["segment"] == "ranchers").to_numpy()
    out = {"stations": ",".join(shared)}
    for ch in ("standalone", "embedded"):
        for k in ("premium", "notional"):
            wv, dv = float(ev.loc[wet, f"{k}_{ch}"].sum()), float(ev.loc[dry, f"{k}_{ch}"].sum())
            out[f"wet_{k}_{ch}"], out[f"dry_{k}_{ch}"] = wv, dv
            out[f"wet_dry_{k}_{ch}"] = wv / dv if dv > 0 else np.nan
    return out


def headline(R, ev, nat) -> dict:
    t = totals(R, ev, nat)
    nat_t = t[t["scope"] == "national"].set_index("segment")
    k23_t = t[t["scope"] == "kalshi23"].set_index("segment")
    wd = wet_dry(R, ev)
    return {"restaurants_national": nat_t.loc["restaurants", "premium_standalone"],
            "wet_national": nat_t.loc[WET_SEGMENTS, "premium_standalone"].sum(),
            "wet_k23": k23_t.loc[WET_SEGMENTS, "premium_standalone"].sum(),
            "dry_k23": k23_t.loc["ranchers", "premium_standalone"],
            "wet_dry_ratio": wd["wet_dry_premium_standalone"],
            "wet_dry_ratio_embedded": wd["wet_dry_premium_embedded"]}


def draw_params(rng, R) -> dict:
    p = {}
    for k, (lo, c, hi) in P.items():
        if lo is None or hi is None or lo == hi:
            p[k] = c
        else:
            p[k] = float(rng.triangular(lo, c, hi))
    return p


def set_effect_ci(lo: float, hi: float) -> None:
    P["rest_effect"] = (lo, 1.0, hi)


def venue_low_mult(R) -> float:
    v = R[R["segment"] == "mlb"]
    return float((v["rho_listed"] / v["rho_index"]).median())


def monte_carlo(R, nat, rng) -> pd.DataFrame:
    rows = []
    vlo = venue_low_mult(R)
    for _ in range(N_MC):
        p = draw_params(rng, R)
        p["venue_rho_mult"] = float(rng.triangular(vlo, 1.0, 1.118))
        p["gamma_med"] = float(rng.choice([1.0, 2.0, 4.0], p=[0.25, 0.5, 0.25]))
        ev = evaluate(R, p)
        t = totals(R, ev, nat)
        wd = wet_dry(R, ev)
        for _, r in t.iterrows():
            rows.append({"segment": r["segment"], "scope": r["scope"], **{k: r[k] for k in r.index if "_" in k}})
        rows.append({"segment": "_wet_dry", "scope": "shared_nov_feb",
                     "premium_standalone": wd["wet_dry_premium_standalone"],
                     "premium_embedded": wd["wet_dry_premium_embedded"]})
    return pd.DataFrame(rows)


SENS = [  # (label, parameter, low value, high value)
    ("Base take-up, standalone (0.10 / 0.35)", "t0_standalone", 0.10, 0.35),
    ("Price elasticity (-2.5 / -0.66)", "elasticity", -2.5, -0.66),
    ("Restaurant effect size, 95% CI", "rest_effect", None, None),
    ("Sales per restaurant ($1.0M / $2.3M)", "rest_sales", 1.0, 2.3),
    ("Contribution margin (0.55 / 0.70)", "rest_contrib", 0.55, 0.70),
    ("Restaurant firm-to-airport rho (0.6 / 0.9)", "rho_rest", 0.6, 0.9),
    ("Construction site-to-airport rho (0.6 / 0.9)", "rho_constr", 0.6, 0.9),
    ("Golf facility-to-airport rho (0.5 / 0.85)", "rho_golf", 0.5, 0.85),
    ("Golf rounds lost per extra inch (1.5% / 3.0%)", "golf_per_inch", 0.015, 0.03),
    ("Venue index (listed monthly total / game-window)", "venue_rho_mult", None, 1.118),
    ("Risk aversion gamma (1 / 4)", "gamma_med", 1.0, 4.0),
    ("Restaurant cash buffer (27 / 12 days)", "rest_buffer", 27.0, 12.0),
    ("Restaurant rebound (net = 50% / 100% of gross)", "rest_rebound", 0.5, 1.0),
    ("Price multiple, standalone (1.6 / 1.1)", "m_standalone", 1.6, 1.1),
    ("Construction delay cost ($250 / $2,500 per day)", "constr_cost", 250.0, 2500.0),
    ("Rancher share of state policies (x0.5 / x1.5)", "ranch_share_mult", 0.5, 1.5),
    ("Wealth frame (broad / narrow: one month's profit)", "_frame", "broad", "narrow"),
]


def sensitivity(R, nat) -> pd.DataFrame:
    base = headline(R, evaluate(R, C), nat)
    rows = []
    for label, k, lo, hi in SENS:
        res = {}
        for side, v in (("low", lo), ("high", hi)):
            p, frame = dict(C), "broad"
            if k == "_frame":
                frame = v
            elif k == "rest_effect":
                p[k] = P["rest_effect"][0] if side == "low" else P["rest_effect"][2]
            elif k == "venue_rho_mult" and v is None:
                p[k] = venue_low_mult(R)
            else:
                p[k] = v
            res[side] = headline(R, evaluate(R, p, frame), nat)
        for metric in ("restaurants_national", "wet_national", "wet_dry_ratio"):
            lo_v, hi_v = res["low"][metric], res["high"][metric]
            rows.append({"assumption": label, "parameter": k, "metric": metric, "central": base[metric],
                         "low_case": lo_v, "high_case": hi_v, "swing": abs(hi_v - lo_v),
                         "swing_ratio": (max(lo_v, hi_v) / min(lo_v, hi_v)) if min(lo_v, hi_v) > 0 else np.inf})
    s = pd.DataFrame(rows)
    return s.sort_values(["metric", "swing"], ascending=[True, False]).reset_index(drop=True)


def depth_table(R: pd.DataFrame, ev: pd.DataFrame) -> pd.DataFrame:
    smap = pd.read_csv(PROCESSED / "station_map.csv")[["series_ticker", "station_key"]]
    smap = smap[smap["station_key"] != "MDW"].drop_duplicates("series_ticker")
    snaps = {"20261102": "post-rewards (Nov 2)", "20261029": "rewards on (Oct 29)"}
    books = []
    for tag, lab in snaps.items():
        ob = pd.read_csv(PROCESSED / f"kalshi_rain_orderbook_summary_{tag}.csv")
        ob = ob[ob["contract_month"] == "2026-11"].merge(smap, on="series_ticker")
        g = ob.groupby("station_key").agg(yes=("yes_ask_depth", "sum"), no=("yes_bid_depth", "sum"))
        g.columns = [f"yes_depth_{tag}", f"no_depth_{tag}"]
        books.append(g)
    book = pd.concat(books, axis=1)
    nov = (R["month"] == 11).to_numpy() & R["station"].notna().to_numpy()
    wet = nov & R["segment"].isin(["restaurants", "bars", "construction", "golf", "mlb"]).to_numpy()
    dry = nov & (R["segment"] == "ranchers").to_numpy()
    rows = []
    for st in sorted(set(R.loc[wet | dry, "station"].dropna())):
        r = {"station": st}
        for ch in ("standalone", "embedded"):
            r[f"wet_contracts_{ch}"] = float(ev.loc[wet & (R["station"] == st).to_numpy(), f"notional_{ch}"].sum())
            r[f"dry_contracts_{ch}"] = float(ev.loc[dry & (R["station"] == st).to_numpy(), f"notional_{ch}"].sum())
        if st in book.index:
            r.update(book.loc[st].to_dict())
        rows.append(r)
    d = pd.DataFrame(rows)
    tot = {"station": "_total"}
    for c in d.columns[1:]:
        tot[c] = float(d[c].sum())
    for tag in snaps:       # total fill = sum over stations of min(depth, demand) / total demand
        for side, col in (("wet", "yes"), ("dry", "no")):
            for ch in ("standalone", "embedded"):
                dem = d[f"{side}_contracts_{ch}"]
                tot[f"{side}_fill_{ch}_{tag}"] = float(np.minimum(dem, d[f"{col}_depth_{tag}"].fillna(0)).sum() / dem.sum())
                act = dem > 0
                tot[f"{side}_depth_at_demand_stations_{tag}"] = float(d.loc[act, f"{col}_depth_{tag}"].sum())
    for tag in snaps:
        for side, col in (("wet", "yes"), ("dry", "no")):
            for ch in ("standalone", "embedded"):
                dem = d[f"{side}_contracts_{ch}"]
                d[f"{side}_fill_{ch}_{tag}"] = np.where(dem > 0, np.minimum(1, d[f"{col}_depth_{tag}"] / dem), np.nan)
    d = d[d["station"] != "_total"]
    return pd.concat([d, pd.DataFrame([tot])], ignore_index=True)


# ---------------------------------------------------------------------------------------------
# figure
# ---------------------------------------------------------------------------------------------
COL_SA, COL_EM, COL_NA, COL_DRY, INK, MUTED, GRID = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#0b0b0b", "#52514e", "#eeede9"


def figure(seg: pd.DataFrame, depth: pd.DataFrame, path) -> None:
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(13.5, 6.2), gridspec_kw={"width_ratios": [1.15, 1]})
    s = seg[(seg["scope"] == "national") & seg["segment"].isin(LABEL)].copy()
    s["order"] = s["segment"].map({k: i for i, k in enumerate(LABEL)})
    s = s.sort_values("order")
    floor = 1e3
    for i, r in enumerate(s.itertuples()):
        lo, hi = max(r.premium_standalone_p10, floor), max(r.premium_standalone_p90, floor)
        ax.plot([lo, hi], [i - 0.15, i - 0.15], color=COL_SA, lw=2, solid_capstyle="round")
        ax.plot(max(r.premium_standalone, floor), i - 0.15, "o", ms=8, color=COL_SA, mec="white", mew=1.5,
                label="standalone, central (P10-P90)" if i == 0 else None)
        lo, hi = max(r.premium_embedded_p10, floor), max(r.premium_embedded_p90, floor)
        ax.plot([lo, hi], [i + 0.15, i + 0.15], color=COL_EM, lw=2, solid_capstyle="round")
        ax.plot(max(r.premium_embedded, floor), i + 0.15, "s", ms=8, color=COL_EM, mec="white", mew=1.5,
                label="embedded (POS / booking / lender)" if i == 0 else None)
        ax.plot(max(r.premium_standalone_narrow, floor), i - 0.15, "D", ms=7, mfc="none", mec=COL_NA, mew=1.6,
                label="standalone, narrow wealth frame" if i == 0 else None)
    ax.set_yticks(range(len(s)))
    ax.set_yticklabels([LABEL[k] for k in s["segment"]], fontsize=9, color=INK)
    ax.invert_yaxis()
    ax.set_xscale("log")
    ax.set_xlim(floor * 0.7, None)
    ax.set_xlabel("expected hedge premium, $ per year (log; national; values below $1k drawn at $1k)", color=INK)
    ax.set_title("Loss-based demand by segment", loc="left", fontsize=11, color=INK)
    ax.legend(loc="upper center", bbox_to_anchor=(0.45, -0.11), fontsize=8.5, frameon=False, ncol=2)
    ax.grid(axis="x", color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)

    depth = depth[depth["station"] != "_total"]
    dry = depth[depth["dry_contracts_standalone"] > 0].sort_values("dry_contracts_standalone", ascending=False)
    wet = depth[depth["dry_contracts_standalone"] <= 0].nlargest(6, "wet_contracts_standalone")
    d = pd.concat([dry, wet])
    x = np.arange(len(d))
    w = 0.2
    pos = lambda col: d[col].where(d[col] > 0)  # noqa: E731 - zero demand is left blank, not drawn at the floor
    ax2.bar(x - 1.5 * w, pos("wet_contracts_standalone"), w, color=COL_SA, label="wet demand, standalone")
    ax2.bar(x - 0.5 * w, pos("dry_contracts_standalone"), w, color=COL_DRY, label="dry (rancher) demand, standalone")
    ax2.bar(x + 0.5 * w, pos("yes_depth_20261102"), w, color="#9fc3ee", label="YES ask depth, Nov 2 book")
    ax2.bar(x + 1.5 * w, pos("no_depth_20261102"), w, color="#f6d58a", label="NO ask depth, Nov 2 book")
    ax2.axvline(len(dry) - 0.5, color=MUTED, lw=0.8, ls=":")
    ax2.text(len(dry) - 0.6, 3e6, "rancher stations", ha="right", fontsize=8, color=MUTED)
    ax2.text(len(dry) - 0.4, 3e6, "largest wet-only", ha="left", fontsize=8, color=MUTED)
    ax2.set_ylim(300, 6e6)
    ax2.set_yscale("log")
    ax2.set_xticks(x)
    ax2.set_xticklabels(d["station"], fontsize=9, color=INK, rotation=45)
    ax2.set_ylabel("$1 contracts, November 2026 (log)", color=INK)
    ax2.set_title("November demand vs Kalshi resting depth", loc="left", fontsize=11, color=INK)
    ax2.legend(fontsize=8, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.11), ncol=2)
    ax2.grid(axis="y", color=GRID, lw=0.6)
    ax2.set_axisbelow(True)
    for sp in ("top", "right"):
        ax2.spines[sp].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


# ---------------------------------------------------------------------------------------------
def segment_summary(R, ev_c, ev_n, ev_r, mc, nat) -> pd.DataFrame:
    t_c, t_n, t_r = totals(R, ev_c, nat), totals(R, ev_n, nat), totals(R, ev_r, nat)
    rows = []
    for _, r in t_c.iterrows():
        sg, sc = r["segment"], r["scope"]
        msk = (R["segment"] == sg).to_numpy()
        if sc == "kalshi23" and sg != "milb":
            msk = msk & in_k23(R)
        e, rr = ev_c[msk], R[msk]
        act = e["eh_firm"] > 0
        fm = e["firms"].where(act, 0)
        wavg = (lambda col: float(np.average(e.loc[act, col], weights=fm[act])) if act.any() else np.nan)
        firms = float(rr.groupby("geo")["firms"].first().sum()) if sg != "ranchers" else float(
            rr.groupby(["geo"])["firms"].first().sum())
        if sg == "milb":
            firms = MILB_TEAMS * (MILB_K23_SHARE if sc == "kalshi23" else 1)
        elif sc == "national":
            firms *= nat[sg]
        q = mc[(mc["segment"] == sg) & (mc["scope"] == sc)]
        nmon = rr.loc[act.to_numpy(), "month"].nunique()
        row = {"segment": sg, "label": LABEL[sg], "scope": sc, "firms": firms, "active_months": nmon,
               "loss_mean_firm_month": wavg("loss_mean"), "loss_excess_mean_firm_month": wavg("loss_excess_mean"),
               "loss_p95_firm_month": wavg("loss_p95"), "he_firm": wavg("he_firm"),
               "he_station": float(np.average(rr.loc[act.to_numpy(), "he_s"], weights=fm[act])) if act.any() else np.nan,
               "wtp_multiple": wavg("wtp_multiple"),
               "wtp_multiple_narrow": float(np.average(ev_n.loc[msk][act]["wtp_multiple"], weights=fm[act])) if act.any() else np.nan,
               "expected_payout_firm_month": wavg("eh_firm"), "max_payout_firm_month": wavg("maxpay_firm")}
        for ch in ("standalone", "embedded"):
            row[f"screen_{ch}"] = wavg(f"screen_{ch}")
            row[f"takeup_{ch}"] = wavg(f"takeup_{ch}")
            row[f"premium_{ch}"] = r[f"premium_{ch}"]
            row[f"premium_{ch}_p10"] = float(q[f"premium_{ch}"].quantile(0.10))
            row[f"premium_{ch}_p90"] = float(q[f"premium_{ch}"].quantile(0.90))
            row[f"premium_{ch}_narrow"] = float(t_n[(t_n["segment"] == sg) & (t_n["scope"] == sc)][f"premium_{ch}"].iloc[0])
            row[f"premium_{ch}_rational"] = float(t_r[(t_r["segment"] == sg) & (t_r["scope"] == sc)][f"premium_{ch}"].iloc[0])
            row[f"notional_{ch}"] = r[f"notional_{ch}"]
            row[f"contracts_per_active_month_{ch}"] = r[f"notional_{ch}"] / nmon if nmon else 0.0
            nsm = rr.loc[act.to_numpy()].drop_duplicates(["station", "month"]).shape[0] if sg not in ("milb",) else nmon
            if sg == "mlb":
                nsm = int(act.sum())
            row[f"contracts_per_station_month_{ch}"] = (r[f"notional_{ch}"] / nsm if nsm else 0.0) / (
                nat[sg] if sc == "national" and sg not in ("mlb", "milb") else 1.0)
        rows.append(row)
    s = pd.DataFrame(rows)
    for sc in ("kalshi23", "national"):
        for name, segs in (("_wet_total", WET_SEGMENTS), ("_dry_total", ["ranchers"]), ("_snow_total", ["snow_city"])):
            x = s[(s["scope"] == sc) & s["segment"].isin(segs)]
            q = mc[(mc["scope"] == sc) & mc["segment"].isin(segs)]
            row = {"segment": name, "label": name.strip("_").replace("_", " "), "scope": sc}
            for ch in ("standalone", "embedded"):
                for col in (f"premium_{ch}", f"premium_{ch}_narrow", f"premium_{ch}_rational", f"notional_{ch}"):
                    row[col] = float(x[col].sum())
            # MC totals: rows are appended in a fixed order per draw, so group by draw id
            for ch in ("standalone", "embedded"):
                qq = q.copy()
                qq["draw"] = np.arange(len(qq)) // max(len(segs), 1)
                tot = qq.groupby("draw")[f"premium_{ch}"].sum()
                row[f"premium_{ch}_p10"], row[f"premium_{ch}_p90"] = float(tot.quantile(0.1)), float(tot.quantile(0.9))
            s = pd.concat([s, pd.DataFrame([row])], ignore_index=True)
    wd = mc[mc["segment"] == "_wet_dry"]
    return s, wd


def main(argv=None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    offline = "--offline" in args
    t0 = time.time()
    rng = np.random.default_rng(SEED)
    di = demand_inputs()
    metros = metro_table(di)
    beff, ci_lo, ci_hi = restaurant_effects()
    set_effect_ci(ci_lo, ci_hi)
    scales = city_scales()
    ym = station_months(offline, beff)
    print(f"daily ACIS: {ym['station_key'].nunique()} stations, {ym['year'].min()}-{ym['year'].max()}, "
          f"{len(ym)} station-months; restaurant effect CI x{ci_lo:.2f}-x{ci_hi:.2f}")

    rows = (rows_restaurants(ym, metros, scales) + rows_golf(ym, metros) + rows_construction(ym, metros)
            + rows_snow(ym) + rows_venues(rng) + rows_ranchers(rancher_wtp()))
    R = pd.DataFrame(rows)
    for col in ("budget", "rho_index", "rho_listed", "annual_rev", "he_listed_s"):
        if col not in R:
            R[col] = np.nan
    R["k23"] = R["k23"].fillna(True) if "k23" in R else True
    nat = national_factor(R)

    # check: station-based restaurant loss vs the reservation study's city-month means
    loss = pd.read_csv(PROCESSED / "rain_reservations_city_month_loss.csv")
    chk = R[R["segment"] == "restaurants"].merge(
        metros[["metro", "city"]], left_on="geo", right_on="metro").merge(
        loss[["city", "month", "pct_lost_city_mean"]], on=["city", "month"])
    ratio = (chk["pct_sales_lost_mean"] / chk["pct_lost_city_mean"])
    print(f"restaurant % lost at Kalshi station vs reservation study: median ratio {ratio.median():.3f} "
          f"(p10 {ratio.quantile(0.1):.3f}, p90 {ratio.quantile(0.9):.3f}), {len(chk)} metro-months")

    ev_c = evaluate(R, C)
    ev_n = evaluate(R, C, "narrow")
    ev_r = evaluate(R, C, "rational")
    print(f"CRRA check: max |exact - CARA| restaurant WTP multiple over 25 rows = {crra_check(R, ym, rng):.5f}")
    mc = monte_carlo(R, nat, rng)
    seg, wdmc = segment_summary(R, ev_c, ev_n, ev_r, mc, nat)
    wd_c, wd_n = wet_dry(R, ev_c), wet_dry(R, ev_n)
    wd_rows = []
    for name, wdx in (("central", wd_c), ("narrow frame", wd_n)):
        wd_rows.append({"segment": "_wet_dry_ratio", "label": f"wet:dry premium ratio, {name}",
                        "scope": "shared stations Nov-Feb", **{k: v for k, v in wdx.items()},
                        "premium_standalone": wdx["wet_dry_premium_standalone"],
                        "premium_embedded": wdx["wet_dry_premium_embedded"]})
    wd_rows[0]["premium_standalone_p10"] = float(wdmc["premium_standalone"].quantile(0.1))
    wd_rows[0]["premium_standalone_p90"] = float(wdmc["premium_standalone"].quantile(0.9))
    wd_rows[0]["premium_embedded_p10"] = float(wdmc["premium_embedded"].quantile(0.1))
    wd_rows[0]["premium_embedded_p90"] = float(wdmc["premium_embedded"].quantile(0.9))
    seg = pd.concat([seg, pd.DataFrame(wd_rows)], ignore_index=True)
    seg.to_csv(PROCESSED / "weather_demand_segment.csv", index=False)

    cm = pd.concat([R.drop(columns=["wtp_grid"]), ev_c], axis=1)
    cm = cm.loc[:, ~cm.columns.duplicated(keep="last")]
    cm["premium_standalone_narrow"] = ev_n["premium_standalone"]
    cm["premium_embedded_narrow"] = ev_n["premium_embedded"]
    cm["wtp_multiple_narrow"] = ev_n["wtp_multiple"]
    cm["in_kalshi23"] = in_k23(R)
    cm.to_csv(PROCESSED / "weather_demand_city_month.csv", index=False)

    sens = sensitivity(R, nat)
    sens.to_csv(PROCESSED / "weather_demand_sensitivity.csv", index=False)
    depth = depth_table(R, ev_c)
    depth.to_csv(PROCESSED / "weather_demand_depth.csv", index=False)
    figure(seg, depth, FIGURES / "weather_demand.png")

    pd.set_option("display.width", 260)
    pd.set_option("display.max_columns", 60)
    pd.set_option("display.max_rows", 200)
    show = ["segment", "scope", "firms", "loss_mean_firm_month", "loss_excess_mean_firm_month", "loss_p95_firm_month",
            "he_station", "he_firm", "wtp_multiple", "wtp_multiple_narrow", "screen_standalone", "takeup_standalone",
            "takeup_embedded", "premium_standalone", "premium_standalone_p10", "premium_standalone_p90",
            "premium_embedded", "premium_embedded_p10", "premium_embedded_p90", "premium_standalone_narrow",
            "premium_embedded_narrow", "premium_standalone_rational", "contracts_per_active_month_standalone",
            "contracts_per_active_month_embedded"]
    print(seg[show].to_string(index=False, float_format=lambda v: f"{v:,.4g}"))
    print(pd.DataFrame(wd_rows).T.to_string())
    print(sens.to_string(index=False, float_format=lambda v: f"{v:,.4g}"))
    print(depth.round(3).to_string(index=False))
    tot = depth[depth["station"] == "_total"].iloc[0]
    print("Nov totals:", {k: round(float(tot[k]), 3) for k in tot.index if k != "station"})
    print(f"done in {time.time() - t0:.0f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
