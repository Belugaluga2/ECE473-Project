"""Dairy heat-stress cover from Kalshi daily-high contracts (doc 24).

Question: a dairy loses milk on hot days. USDA dairy programs insure price and margin, not
heat. Can Kalshi's daily maximum-temperature contracts, which settle at a nearby airport,
cover a dairy's summer heat-stress loss?

Pieces:

- **Target.** Summer (June-September) heat load at the dairy, in degree-days above 80 F:
  sum over days of max(Tmax - 80, 0), from the NRCC interpolated grid at a point in the
  dairy county. It is turned into lost milk with a published slope (0.2 kg per cow per day
  for each THI unit above 72; about 0.67 THI units per F at moderate humidity), then into
  dollars at an assumed milk price. The insured amount is the loss *above the 1951-2000
  average*, like an insurance policy with a trigger. Hedge effectiveness (HE) does not depend
  on the dollar coefficients, only the dollar figures do.
- **Hedge.** A ladder of Kalshi "high above k F" YES contracts at the settlement airport. One
  leg = n contracts on strike k bought for every day of one month, so it pays n x (days in
  that month with airport high > k).
- **Fit and test.** Weights on 1951-2000, holdout 2001-2025, as in the rain studies.
- **Two price views.** (1) Seasonal: as if each contract could be bought before summer at its
  climatological odds plus half a spread (Kalshi does not list that far ahead). (2) Day ahead:
  the way the market works today. Each day's contract lists about a day before, priced off
  the forecast, so the buyer pays P(high > k | forecast) and is only paid for the forecast
  error. Forecasts are simulated as truth plus Gaussian error.

Nothing here places orders.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import norm

from agri_hedge import optimizer as op
from agri_hedge.config import PROCESSED
from agri_hedge.pricing import DEFAULT_TBILL_RATE, capital_cost, taker_fee

TRAIN = (1951, 2000)
TEST = (2001, 2025)
FAIR_WINDOW = (1991, 2025)
SEASON = (6, 7, 8, 9)
THRESHOLD_F = 80.0
STRIKES = tuple(range(78, 118, 2))      # "high above k" ladder considered for every site
HALF_SPREAD = 0.0225                    # doc 05 median contested rain spread / 2
FORECAST_SIGMA_F = 3.5                  # day-ahead max-temp forecast error (assumption, see doc 24)
PERSISTENCE_DAYS = 5                    # heat waves this long are assumed forecast a day ahead
MILK_KG_PER_THI = 0.2                   # Ravagnolo et al. 2000, per cow per day per THI unit > 72
THI_PER_F = 0.67                        # dTHI/dT at 40% relative humidity
MILK_PRICE_PER_CWT = 21.0               # assumed all-milk price, $/cwt
HERD = 1000                             # cows; scales dollars only
KG_TO_LB = 2.20462
#: dollars of milk lost per cow per degree-day above THRESHOLD_F
USD_PER_COW_DEGDAY = MILK_KG_PER_THI * THI_PER_F * KG_TO_LB * MILK_PRICE_PER_CWT / 100
MAX_MISSING_DAYS = 3                    # per season and source; years with more are dropped


@dataclass(frozen=True)
class DairySite:
    site_id: str
    county: str
    lat: float
    lon: float
    acis_sid: str        # Kalshi settlement airport (NWS CLI station)
    thread_sid: str      # NWS threaded city record, fills years before the airport opened
    series_ticker: str


SITES = (
    DairySite("AZ_maricopa", "Maricopa County, AZ", 33.37, -112.58, "PHX", "PHXthr", "KXHIGHTPHX"),
    DairySite("TX_erath", "Erath County, TX", 32.22, -98.20, "DFW", "DFWthr", "KXHIGHTDAL"),
    DairySite("CO_weld", "Weld County, CO", 40.35, -104.65, "DEN", "DENthr", "KXHIGHDEN"),
    DairySite("PA_lancaster", "Lancaster County, PA", 40.04, -76.30, "PHL", "PHLthr", "KXHIGHPHIL"),
    DairySite("MN_stearns", "Stearns County, MN", 45.55, -94.60, "MSP", "MSPthr", "KXHIGHTMIN"),
    DairySite("FL_okeechobee", "Okeechobee County, FL", 27.24, -80.83, "MIA", "MIAthr", "KXHIGHMIA"),
    DairySite("CA_tulare", "Tulare County, CA", 36.21, -119.35, "LAX", "LAXthr", "KXHIGHLAX"),
)
SITE_BY_ID = {s.site_id: s for s in SITES}


def load_daily() -> pd.DataFrame:
    df = pd.read_parquet(PROCESSED / "dairy_daily_tmax.parquet")
    df["date"] = pd.to_datetime(df["date"])
    return df


def distance_mi(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 3958.8 * 2 * math.asin(math.sqrt(a))


def heat_load(tmax, threshold: float = THRESHOLD_F) -> float:
    """Degree-days above `threshold`: sum of max(T - threshold, 0)."""
    t = np.asarray(tmax, float)
    return float(np.maximum(t - threshold, 0).sum())


@dataclass
class HeatProblem:
    site: DairySite
    years: np.ndarray
    farm_hl: np.ndarray          # farm degree-days by year
    airport_hl: np.ndarray       # airport degree-days by year
    X: np.ndarray                # years x legs: days in month with airport high > strike
    legs: list                   # (month, strike)
    q: np.ndarray                # per-day climatological P(high > strike) by leg, FAIR_WINDOW
    days: np.ndarray             # days per month by leg
    trigger_usd: float           # training-mean loss
    daily: pd.DataFrame          # season days with complete data (date, airport, farm)

    @property
    def loss_usd(self) -> np.ndarray:
        return self.farm_hl * USD_PER_COW_DEGDAY * HERD

    @property
    def target_usd(self) -> np.ndarray:
        """Insured loss: milk loss above the 1951-2000 average."""
        return np.maximum(self.loss_usd - self.trigger_usd, 0.0)

    def mask(self, span) -> np.ndarray:
        return (self.years >= span[0]) & (self.years <= span[1])


def build_problem(site: DairySite | str, daily: pd.DataFrame | None = None,
                  strikes=STRIKES) -> HeatProblem:
    site = SITE_BY_ID[site] if isinstance(site, str) else site
    daily = load_daily() if daily is None else daily
    d = daily[(daily.site == site.site_id) & daily.date.dt.month.isin(SEASON)].copy()
    d["year"], d["month"] = d.date.dt.year, d.date.dt.month
    d = d[(d.year >= TRAIN[0]) & (d.year <= TEST[1])]
    miss = d.groupby("year")[["airport_tmax_f", "farm_tmax_f"]].apply(lambda g: g.isna().sum().max())
    keep = miss[miss <= MAX_MISSING_DAYS].index
    d = d[d.year.isin(keep)]
    # Fill the few missing days with that month's mean so a year's counts are comparable.
    for col in ("airport_tmax_f", "farm_tmax_f"):
        d[col] = d[col].fillna(d.groupby(["year", "month"])[col].transform("mean"))
    years = np.array(sorted(d.year.unique()))
    fair = d[(d.year >= FAIR_WINDOW[0]) & (d.year <= FAIR_WINDOW[1])]
    train = d[(d.year >= TRAIN[0]) & (d.year <= TRAIN[1])]
    legs, q, days, cols = [], [], [], []
    for m in SEASON:
        tm = train[train.month == m].airport_tmax_f
        fm = fair[fair.month == m].airport_tmax_f
        for k in strikes:
            freq = float((tm > k).mean())
            if not 0.02 <= freq <= 0.98:     # nearly always or never: no information
                continue
            legs.append((m, float(k)))
            q.append(float((fm > k).mean()))
            days.append(pd.Period(f"2001-{m:02d}").days_in_month)
            cols.append(d[d.month == m].assign(hit=lambda x: x.airport_tmax_f > k)
                        .groupby("year").hit.sum().reindex(years, fill_value=0).to_numpy(float))
    by_year = d.groupby("year")
    farm_hl = by_year.farm_tmax_f.apply(heat_load).reindex(years).to_numpy()
    air_hl = by_year.airport_tmax_f.apply(heat_load).reindex(years).to_numpy()
    tr = (years >= TRAIN[0]) & (years <= TRAIN[1])
    trigger = float(farm_hl[tr].mean() * USD_PER_COW_DEGDAY * HERD)
    return HeatProblem(site, years, farm_hl, air_hl, np.column_stack(cols), legs, np.array(q),
                       np.array(days), trigger,
                       d[["date", "year", "month", "airport_tmax_f", "farm_tmax_f"]].reset_index(drop=True))


def fit_ladder(X, y, tr, q) -> np.ndarray:
    """Lowest-error whole contracts per day on each leg, training years only."""
    tranches = [op.Tranche(i, float(np.clip(qi + HALF_SPREAD, 0.01, 0.99)), np.inf, "model")
                for i, qi in enumerate(q)]
    sol = op.solve_penalized(X[tr], y[tr], tranches, scale=max(float(np.abs(y[tr]).max()), 1.0))
    return np.rint(sol.leg_contracts).astype(int)


def fit_index_option(air_hl, y, tr) -> tuple[float, float]:
    """Best call option on the airport's seasonal heat load: payout = b * max(HL - K, 0).

    This is the contract a seasonal heat-degree-day market would offer; it isolates basis
    risk (farm vs airport) from the limits of daily contracts. K is searched over training
    quantiles, b by least squares.
    """
    best = (np.inf, 0.0, 0.0)
    for K in np.quantile(air_hl[tr], np.linspace(0.0, 0.9, 46)):
        z = np.maximum(air_hl[tr] - K, 0)
        if not (z > 0).any():
            continue
        b = max(float(z @ y[tr] / (z @ z)), 0.0)
        err = float(np.mean((y[tr] - b * z) ** 2))
        if err < best[0]:
            best = (err, b, float(K))
    return best[1], best[2]


def seasonal_cost(p: HeatProblem, n, rate: float = DEFAULT_TBILL_RATE) -> dict:
    """Cost of buying the whole ladder before summer at climatological odds + half spread.

    Hypothetical: Kalshi lists daily highs about a day ahead. One order per leg per day
    (fees round up per order). Cash prepaid from May 1 to each month's mid-point.
    """
    n = np.asarray(n, float)
    price = np.clip(p.q + HALF_SPREAD, 0.01, 0.99)
    premium = float((n * p.days * price).sum())
    fees = float((taker_fee(n, price) * p.days).sum())
    lock = np.array([(pd.Timestamp(2001, m, 15) - pd.Timestamp(2001, 5, 1)).days for m, _ in p.legs])
    capital = float(sum(capital_cost(n[j] * p.days[j] * price[j], rate=rate, days=lock[j])
                        for j in range(len(n))))
    fair = float((n * p.days * p.q).sum())
    return {"premium_usd": premium, "fee_usd": fees, "capital_usd": capital,
            "cost_usd": premium + fees + capital, "fair_payout_usd": fair,
            "contract_days": float((n * p.days).sum())}


def simulate_forecasts(p: HeatProblem, sigma: float = FORECAST_SIGMA_F, seed: int = 473,
                       persistence_days: int = PERSISTENCE_DAYS):
    """Day-ahead forecasts consistent with the observed highs; returns (forecast, error sd).

    Each day's anomaly from its site-month mean is split into a slow part (centered
    `persistence_days` running mean within the season: heat waves, which a next-day forecast
    sees coming) and a fast day-to-day part D. The forecast knows the slow part and is a
    calibrated estimate of D: T = F + e with e independent of F and Var(e) = min(sigma^2,
    Var D). So F | T ~ N(slow + (1 - v/Var D) D, (Var D - v) v / Var D) with v = Var(e), and the
    price P(T > k | F) is fair: the buyer is paid only for e. persistence_days <= 1 gives the
    simpler model where the whole anomaly is "fast" (an upper bound on what day-ahead buying
    can hedge).
    """
    rng = np.random.default_rng(seed)
    d = p.daily
    t = d.airport_tmax_f.to_numpy(float)
    mu = d.groupby("month").airport_tmax_f.transform("mean").to_numpy()
    anom = pd.Series(t - mu, index=d.index)
    if persistence_days > 1:
        slow = anom.groupby(d.year).transform(
            lambda x: x.rolling(persistence_days, center=True, min_periods=1).mean()).to_numpy()
    else:
        slow = np.zeros(len(t))
    fast = anom.to_numpy() - slow
    vd = pd.Series(fast).groupby(d.month.to_numpy()).transform("var").to_numpy()
    v = np.minimum(sigma ** 2, vd)
    shrink = np.where(vd > 0, 1 - v / vd, 0.0)
    noise_sd = np.sqrt(np.maximum((vd - v) * v / np.maximum(vd, 1e-9), 0.0))
    f = mu + slow + shrink * fast + rng.normal(0.0, 1.0, len(t)) * noise_sd
    return f, np.sqrt(np.maximum(v, 1e-6))


def day_ahead_features(p: HeatProblem, sigma: float = FORECAST_SIGMA_F, seed: int = 473,
                       persistence_days: int = PERSISTENCE_DAYS):
    """Years x legs: sum over the month's days of (1[high > k] - P(high > k | forecast)).

    This is what a leg pays net of its price when bought one day ahead at a fair,
    forecast-informed price. Highs settle as whole degrees, so P(high > k) uses k + 0.5.
    """
    d = p.daily
    t = d.airport_tmax_f.to_numpy(float)
    f, sd = simulate_forecasts(p, sigma, seed, persistence_days)
    yi = np.searchsorted(p.years, d.year.to_numpy())
    F = np.zeros((len(p.years), len(p.legs)))
    for j, (m, k) in enumerate(p.legs):
        sel = d.month.to_numpy() == m
        price = norm.sf((k + 0.5 - f[sel]) / sd[sel])
        np.add.at(F[:, j], yi[sel], (t[sel] > k) - price)
    return F


def day_ahead_friction(p: HeatProblem, n, sigma: float = FORECAST_SIGMA_F, seed: int = 473,
                       persistence_days: int = PERSISTENCE_DAYS) -> float:
    """Expected annual spread + fee cost of buying the ladder one day at a time (holdout years)."""
    keep = ((p.daily.year >= TEST[0]) & (p.daily.year <= TEST[1])).to_numpy()
    d = p.daily[keep]
    f, sd = simulate_forecasts(p, sigma, seed, persistence_days)
    f, sd = f[keep], sd[keep]
    total = 0.0
    for j, (m, k) in enumerate(p.legs):
        if n[j] <= 0:
            continue
        sel = d.month.to_numpy() == m
        price = np.clip(norm.sf((k + 0.5 - f[sel]) / sd[sel]) + HALF_SPREAD, 0.01, 0.99)
        total += n[j] * HALF_SPREAD * sel.sum() + float(taker_fee(np.full(sel.sum(), n[j]), price).sum())
    return total / max(d.year.nunique(), 1)


def day_ahead_he(p: HeatProblem, n, y, sigma: float = FORECAST_SIGMA_F, seeds: int = 20,
                 persistence_days: int = PERSISTENCE_DAYS) -> float:
    """Median holdout HE of the ladder bought one day at a time; one scale (>= 0) fit on training."""
    tr, te = p.mask(TRAIN), p.mask(TEST)
    hes = []
    for s in range(seeds):
        z = day_ahead_features(p, sigma, 473 + s, persistence_days) @ n
        zt, yt = z[tr] - z[tr].mean(), y[tr] - y[tr].mean()
        beta = max(float(zt @ yt / (zt @ zt)), 0.0) if (zt @ zt) > 0 else 0.0
        hes.append(op.hedge_effectiveness(y[te], beta * z[te]))
    return float(np.median(hes))


def evaluate(site, daily=None, sigma: float = FORECAST_SIGMA_F, seeds: int = 20) -> dict:
    """Holdout HE and costs for one dairy, every hedge view."""
    p = build_problem(site, daily)
    tr, te = p.mask(TRAIN), p.mask(TEST)
    y = p.target_usd
    out = {"site_id": p.site.site_id, "county": p.site.county, "airport": p.site.acis_sid,
           "series": p.site.series_ticker,
           "distance_mi": distance_mi(p.site.lat, p.site.lon, *AIRPORT_LL[p.site.acis_sid]),
           "n_train": int(tr.sum()), "n_test": int(te.sum()), "n_legs": len(p.legs),
           "farm_hl_train": float(p.farm_hl[tr].mean()), "farm_hl_test": float(p.farm_hl[te].mean()),
           "hl_corr_test": float(np.corrcoef(p.farm_hl[te], p.airport_hl[te])[0, 1]),
           "he_linear_basis": float(np.corrcoef(p.farm_hl[te], p.airport_hl[te])[0, 1] ** 2),
           "mean_loss_usd": float(p.loss_usd[te].mean()), "trigger_usd": p.trigger_usd,
           "mean_target_usd": float(y[te].mean()), "sd_target_usd": float(y[te].std()),
           "years_paid_test": int((y[te] > 0).sum())}
    # 1. A seasonal heat-degree-day option on the airport (what a seasonal contract could do).
    b, K = fit_index_option(p.airport_hl, y, tr)
    out["he_index_option"] = op.hedge_effectiveness(y[te], b * np.maximum(p.airport_hl[te] - K, 0))
    # 2. Kalshi daily ladder, bought before summer (hypothetical listing).
    n = fit_ladder(p.X, y, tr, p.q)
    h = p.X[te] @ n
    out["he_ladder_seasonal"] = op.hedge_effectiveness(y[te], h)
    out["recovery_ladder"] = float(np.minimum(y[te], h).sum() / y[te].sum()) if y[te].sum() else float("nan")
    c = seasonal_cost(p, n)
    out.update({f"seasonal_{k}": v for k, v in c.items()})
    out["seasonal_loading"] = c["cost_usd"] / c["fair_payout_usd"] if c["fair_payout_usd"] else float("nan")
    out["seasonal_cost_per_cow"] = c["cost_usd"] / HERD
    # 3. The same ladder bought one day at a time, priced off the forecast (how Kalshi lists).
    out["he_day_ahead"] = day_ahead_he(p, n, y, sigma, seeds)
    out["he_day_ahead_upper"] = day_ahead_he(p, n, y, sigma, seeds, persistence_days=1)
    out["day_ahead_friction_usd"] = day_ahead_friction(p, n, sigma)
    out["contracts_per_day_max"] = int(n.max()) if len(n) else 0
    out["_problem"], out["_ladder"] = p, n
    return out


#: Settlement airport coordinates (ACIS StnMeta, 2026-11-06).
AIRPORT_LL = {"PHX": (33.4278, -112.00365), "DFW": (32.89744, -97.02196), "DEN": (39.84657, -104.65623),
              "PHL": (39.87326, -75.22681), "MSP": (44.88523, -93.23133), "MIA": (25.78805, -80.31694),
              "LAX": (33.93816, -118.3866)}
