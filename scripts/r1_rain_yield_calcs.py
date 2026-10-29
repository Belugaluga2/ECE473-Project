"""R1: how monthly rainfall moves corn and soybean yields (bu/acre, %, $/acre).

Run from the repo root:

    python scripts/r1_rain_yield_calcs.py

Outputs
-------
* data/processed/crop_rain_sensitivity_corn_soy.csv  (one row per crop x region x window x source)
* docs/figures/r1_*.png                               (response curves, slopes by month, 2012)
* Auxiliary tables, regenerated every run and committed, in data/processed/crop_yield_aux/:
  r1_reestimate_coefficients.csv (own regression coefficients), r1_drought_2012.csv (2012 yields
  vs trend and June-July rain vs normal), r1_irrigation_share_2022.csv (2022 Census irrigated
  share), r1_season_quadratic_panel.csv (season-rain quadratic panel).

What it does
------------
1. Literature arithmetic. Published coefficients (Tannura, Irwin & Good 2008, Tables 2, 6, 8, 9;
   Westcott & Jewison 2013, Tables 6-7; Irwin & Hubbs 2020, Table 2) are typed in below with their
   table references. For a quadratic term Y = b1*P + b2*P^2 the local slope is dY/dP = b1 + 2*b2*P,
   the exact change for +d inches is b1*d + b2*((P+d)^2 - P^2), and the yield-maximising rainfall
   is P* = -b1 / (2*b2).
2. Data pulls (cached in data/raw/r1_rain_yield/, so reruns do not touch the network):
   NOAA NCEI "Climate at a Glance" statewide monthly precipitation / mean temperature (nClimDiv),
   and USDA NASS Quick Stats state yields, harvested acres and 2022 Census irrigated acres.
   Quick Stats is read through the same keyless CSV export the Quick Stats web page uses
   (/uuid/encode then /data/spreadsheet/<uuid>.csv). If NASS ever closes that path, switch to the
   official API (free key at https://quickstats.nass.usda.gov/api) with the same parameters.
3. Our own re-estimation of the Tannura et al. "modified Thompson" state model with data through
   2025, a rain-only variant (which lets rain absorb the heat that comes with dry months), and a
   Schlenker-Roberts-style season-total quadratic on a pooled state panel.
4. 2012 drought table, irrigation table, conversion to dollars with WASDE prices, figures.

All numbers produced here are labelled in the CSV as CONFIRMED (coefficients read in the primary
source, arithmetic by us) or COMPUTED (our own regression on public data).
"""
from __future__ import annotations

import time
import urllib.parse
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from agri_hedge.config import FIGURES, PROCESSED, RAW

RAW_DIR = RAW / "r1_rain_yield"
RAW_DIR.mkdir(parents=True, exist_ok=True)
DERIVED = PROCESSED / "crop_yield_aux"  # auxiliary tables (regenerated on every run, committed)
DERIVED.mkdir(parents=True, exist_ok=True)
HEADERS = {"User-Agent": "Mozilla/5.0 (ECE473 agri-hedge research; contact via Princeton)"}

OUT_CSV = PROCESSED / "crop_rain_sensitivity_corn_soy.csv"
CSV_COLUMNS = [
    "crop", "region", "month_or_window", "baseline_precip_in", "delta_yield_per_inch",
    "yield_units", "delta_yield_pct_per_inch", "delta_yield_plus2in", "price_usd_per_unit",
    "price_basis", "usd_per_acre_per_inch", "valid_range_note", "model_type", "source_short",
    "source_url", "verification",
]

# ---------------------------------------------------------------------------------------------
# Prices: USDA WASDE-676, October 9, 2026, pp. 12 (corn) and 15 (soybeans).
# Marketing-year weighted average price received by farmers, $/bu.
# ---------------------------------------------------------------------------------------------
WASDE_URL = "https://www.usda.gov/oce/commodity/wasde/wasde1026.pdf"
PRICES = {
    "corn": {"2024/25": 4.24, "2025/26 est": 4.16, "2026/27 proj": 4.70},
    "soybeans": {"2024/25": 10.00, "2025/26 est": 10.50, "2026/27 proj": 12.00},
}
PRICE_KEY = "2026/27 proj"
PRICE_BASIS = "2026/27 projected season-average farm price, USDA WASDE-676 (Oct 9 2026)"

# ---------------------------------------------------------------------------------------------
# Tannura, Irwin & Good (2008), farmdoc MORR 2008-01.
# Coefficients: Table 8 (corn, p.54) and Table 9 (soybeans, p.55); state data 1960-2006.
# Quadratic months are (b1, b2); preseason (Sep-Apr) and May are linear.
# Stars are significance as printed (* 10%, ** 5%, *** 1%) for (b1, b2) or b.
# ---------------------------------------------------------------------------------------------
TANNURA_URL = "https://ageconsearch.umn.edu/record/37501/files/morr_08-01.pdf"
TANNURA = {
    "corn": {
        "IL": {"pre": (0.38, ""), "may": (-1.45, "*"), "jun": (14.04, -1.50, "***/***"),
               "jul": (17.65, -1.50, "**/*"), "aug": (2.88, -0.28, "ns/ns")},
        "IN": {"pre": (0.29, ""), "may": (-2.43, "***"), "jun": (16.82, -1.81, "***/***"),
               "jul": (13.62, -1.06, "***/***"), "aug": (15.85, -1.78, "**/**")},
        "IA": {"pre": (1.02, "**"), "may": (-2.89, "***"), "jun": (8.93, -0.82, "*/*"),
               "jul": (19.95, -2.00, "***/***"), "aug": (4.37, -0.34, "ns/ns")},
    },
    "soybeans": {
        "IL": {"pre": (0.12, ""), "may": (-0.44, "*"), "jun": (2.21, -0.21, "ns/ns"),
               "jul": (2.57, -0.18, "ns/ns"), "aug": (3.16, -0.29, "ns/ns")},
        "IN": {"pre": (0.18, ""), "may": (-0.71, "**"), "jun": (5.13, -0.52, "***/***"),
               "jul": (3.52, -0.33, "***/**"), "aug": (3.95, -0.38, "*/ns")},
        "IA": {"pre": (0.29, "*"), "may": (-0.93, "**"), "jun": (2.56, -0.21, "ns/ns"),
               "jul": (3.45, -0.35, "***/***"), "aug": (4.42, -0.37, "***/***")},
    },
}
# Table 2 (p.48): mean, max, min of monthly precipitation (inches), 1960-2006.
TANNURA_PRECIP = {
    "IL": {"pre": (22.83, 30.80, 15.87), "may": (4.32, 8.71, 1.25), "jun": (4.00, 7.67, 1.05),
           "jul": (3.96, 7.27, 1.75), "aug": (3.60, 6.92, 1.69)},
    "IN": {"pre": (24.57, 33.39, 18.52), "may": (4.47, 7.75, 1.52), "jun": (4.07, 7.72, 0.74),
           "jul": (4.34, 8.65, 1.29), "aug": (3.72, 6.69, 1.67)},
    "IA": {"pre": (16.47, 24.29, 9.67), "may": (4.27, 7.86, 1.75), "jun": (4.57, 8.67, 1.72),
           "jul": (4.19, 10.50, 0.95), "aug": (4.01, 8.24, 1.04)},
}
# Table 6 (p.52): mean yield de-trended to 2006 technology (bu/acre) -> our % denominator.
TANNURA_TREND_2006 = {"corn": {"IL": 155.0, "IN": 149.6, "IA": 159.1},
                      "soybeans": {"IL": 46.0, "IN": 46.9, "IA": 47.8}}

WINDOW_LABEL = {"pre": "Sep-Apr (preseason total)", "may": "May", "jun": "June", "jul": "July",
                "aug": "August"}

# ---------------------------------------------------------------------------------------------
# Westcott & Jewison (2013), USDA ERS FDS-13g-01, Tables 6 (corn) and 7 (soybeans), 1988-2012,
# national yield on acre-weighted 8-state (corn) / 7-state (soy) weather.
# ---------------------------------------------------------------------------------------------
WESTCOTT_URL = ("https://ers.usda.gov/sites/default/files/_laserfiche/outlooks/36651/"
                "39297_fds-13g-01.pdf")
WESTCOTT = {
    "corn_jul": (13.793, -1.522), "corn_jul_mean": 3.87,          # p.15
    "corn_jun_shortfall": -9.537, "corn_jun_mean": 4.33, "corn_jun_trigger": 1.82,  # p.17
    "soy_julaug": (5.083, -0.619),                                 # Table 7 (avg monthly precip)
    "soy_jun_shortfall": -1.279, "soy_jun_mean": 4.41, "soy_jun_trigger": 1.91,     # p.20
    "corn_expected_2013": 163.6, "soy_expected_2013": 44.5,        # pp.27-28
}
CORN8 = ["IA", "IL", "IN", "OH", "MO", "MN", "SD", "NE"]
SOY7 = ["IA", "IL", "IN", "OH", "MO", "MN", "NE"]

# Irwin & Hubbs (2020), farmdoc daily (10):121, Table 2: WAOB model re-estimated 1988-2019.
IRWIN_HUBBS_URL = ("https://farmdocdaily.illinois.edu/2020/07/"
                   "understanding-the-waob-crop-weather-model-for-corn.html")
IRWIN_HUBBS = {"jul": (13.460, -1.397), "jul_mean": 3.856, "forecast_2020": 178.5}

# NOAA NCEI Climate-at-a-Glance state codes (alphabetical 48-state numbering).
NOAA_STATE_CODES = {"IL": 11, "IN": 12, "IA": 13, "KS": 14, "KY": 15, "MI": 20, "MN": 21,
                    "MO": 23, "NE": 25, "ND": 32, "OH": 33, "SD": 39, "WI": 47}
STATE_NAMES = {"IL": "ILLINOIS", "IN": "INDIANA", "IA": "IOWA", "KS": "KANSAS",
               "KY": "KENTUCKY", "MI": "MICHIGAN", "MN": "MINNESOTA", "MO": "MISSOURI",
               "NE": "NEBRASKA", "ND": "NORTH DAKOTA", "OH": "OHIO", "SD": "SOUTH DAKOTA",
               "WI": "WISCONSIN"}
NOAA_CAG_URL = "https://www.ncei.noaa.gov/access/monitoring/climate-at-a-glance/statewide/time-series"
QS_URL = "https://quickstats.nass.usda.gov"
YIELD_ITEMS = {"corn": "CORN, GRAIN - YIELD, MEASURED IN BU / ACRE",
               "soybeans": "SOYBEANS - YIELD, MEASURED IN BU / ACRE"}
ACRE_ITEMS = {"corn": "CORN, GRAIN - ACRES HARVESTED", "soybeans": "SOYBEANS - ACRES HARVESTED"}
IRRIG_ITEMS = {"corn": "CORN, GRAIN, IRRIGATED - ACRES HARVESTED",
               "soybeans": "SOYBEANS, IRRIGATED - ACRES HARVESTED"}
NORMAL_YEARS = (1991, 2020)


# =============================================================================================
# 1. Small math helpers
# =============================================================================================
def quad_effects(b1: float, b2: float, p0: float) -> dict:
    """Effects of rain on yield for a term b1*P + b2*P^2 evaluated at baseline rainfall p0.

    Returns the local slope (yield per inch at p0), exact changes for +1, +2, -1, -2 inches,
    and the yield-maximising rainfall P* = -b1/(2*b2) (NaN if b2 >= 0).
    """
    def change(d):
        return b1 * d + b2 * ((p0 + d) ** 2 - p0 ** 2)

    return {
        "slope": b1 + 2 * b2 * p0,
        "plus1": change(1.0), "plus2": change(2.0),
        "minus1": change(-1.0), "minus2": change(-2.0),
        "optimum": (-b1 / (2 * b2)) if b2 < 0 else np.nan,
    }


def linear_effects(b: float) -> dict:
    """Effects for a linear rain term: constant slope, no optimum."""
    return {"slope": b, "plus1": b, "plus2": 2 * b, "minus1": -b, "minus2": -2 * b,
            "optimum": np.nan}


def ols(y: np.ndarray, X: np.ndarray) -> dict:
    """Ordinary least squares with classical standard errors (no statsmodels dependency)."""
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    n, k = X.shape
    sigma2 = resid @ resid / (n - k)
    cov = sigma2 * np.linalg.pinv(X.T @ X)
    r2 = 1 - (resid @ resid) / ((y - y.mean()) @ (y - y.mean()))
    return {"beta": beta, "se": np.sqrt(np.diag(cov)), "cov": cov, "r2": r2, "n": n,
            "rmse": float(np.sqrt(sigma2))}


# =============================================================================================
# 2. Data access (cached)
# =============================================================================================
def _get(url: str, tries: int = 5) -> requests.Response:
    """HTTP GET with simple exponential back-off on 429/5xx."""
    last = None
    for i in range(tries):
        last = requests.get(url, headers=HEADERS, timeout=180)
        if last.status_code == 200:
            return last
        if last.status_code in (429, 500, 502, 503, 504):
            time.sleep(2 ** i)
            continue
        last.raise_for_status()
    last.raise_for_status()
    return last


def noaa_state_monthly(state: str, param: str) -> pd.DataFrame:
    """Statewide monthly series from NOAA NCEI Climate at a Glance (nClimDiv), 1895-2025.

    param is "pcp" (inches) or "tavg" (deg F). Returns a year x month (1..12) table.
    """
    path = RAW_DIR / f"noaa_cag_{state}_{param}.csv"
    if not path.exists():
        url = f"{NOAA_CAG_URL}/{NOAA_STATE_CODES[state]}/{param}/1/0/1895-2025/data.csv"
        path.write_text(_get(url).text, encoding="utf-8")
        time.sleep(0.3)
    df = pd.read_csv(path, comment="#")
    df = df[df["Value"] > -90]  # NOAA uses -99.99 style codes for missing values
    df["year"] = df["Date"] // 100
    df["month"] = df["Date"] % 100
    return df.pivot(index="year", columns="month", values="Value")


def nass_quickstats(params: dict, name: str) -> pd.DataFrame:
    """Download (and cache) a NASS Quick Stats query as a DataFrame via the keyless CSV export."""
    path = RAW_DIR / f"nass_{name}.csv"
    if not path.exists():
        query = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
        uuid = _get(f"{QS_URL}/uuid/encode?{query}").text.strip().strip('"')
        path.write_text(_get(f"{QS_URL}/data/spreadsheet/{uuid}.csv").text, encoding="utf-8")
        time.sleep(0.3)
    df = pd.read_csv(path, dtype=str)
    df["Value_num"] = pd.to_numeric(df["Value"].str.replace(",", "").str.strip(), errors="coerce")
    df["Year"] = pd.to_numeric(df["Year"], errors="coerce")
    return df


def state_series(crop: str, item: dict, label: str) -> pd.DataFrame:
    """Annual state and national NASS survey values (year x state abbreviation, plus 'US')."""
    frames = {}
    for level in ("STATE", "NATIONAL"):
        df = nass_quickstats({"source_desc": "SURVEY", "agg_level_desc": level,
                              "short_desc": item[crop], "reference_period_desc": "YEAR",
                              "year__GE": "1959"}, f"{label}_{crop}_{level.lower()}")
        df = df[df["Period"] == "YEAR"]
        if level == "STATE":
            inv = {v: k for k, v in STATE_NAMES.items()}
            df = df[df["State"].isin(inv)]
            df = df.assign(st=df["State"].map(inv))
        else:
            df = df.assign(st="US")
        frames[level] = df.pivot_table(index="Year", columns="st", values="Value_num",
                                       aggfunc="first")
    out = pd.concat(frames.values(), axis=1)
    out.index = out.index.astype(int)
    return out[out.index <= 2025]


def state_weather(state: str) -> pd.DataFrame:
    """Annual weather variables for one state (year index), built from monthly nClimDiv data."""
    P = noaa_state_monthly(state, "pcp")
    T = noaa_state_monthly(state, "tavg")
    years = [y for y in P.index if (y - 1) in P.index and y <= 2025]
    rows = []
    for y in years:
        rows.append({
            "year": y,
            "pre": P.loc[y - 1, [9, 10, 11, 12]].sum() + P.loc[y, [1, 2, 3, 4]].sum(),
            "may": P.loc[y, 5], "jun": P.loc[y, 6], "jul": P.loc[y, 7], "aug": P.loc[y, 8],
            "t_may": T.loc[y, 5], "t_jun": T.loc[y, 6], "t_jul": T.loc[y, 7], "t_aug": T.loc[y, 8],
            "mar_aug": P.loc[y, [3, 4, 5, 6, 7, 8]].sum(),
            "t_mar_aug": T.loc[y, [3, 4, 5, 6, 7, 8]].mean(),
            "jun_jul": P.loc[y, 6] + P.loc[y, 7],
            "julaug_avg": (P.loc[y, 7] + P.loc[y, 8]) / 2,
        })
    return pd.DataFrame(rows).set_index("year")


# =============================================================================================
# 3. Literature rows
# =============================================================================================
def _row(**kw) -> dict:
    return {c: kw.get(c, "") for c in CSV_COLUMNS}


def literature_rows() -> list[dict]:
    """CSV rows computed from published coefficients (Tannura 2008, Westcott 2013, Irwin 2020)."""
    rows = []
    for crop, states in TANNURA.items():
        price = PRICES[crop][PRICE_KEY]
        for st, terms in states.items():
            trend = TANNURA_TREND_2006[crop][st]
            for win, coef in terms.items():
                mean, pmax, pmin = TANNURA_PRECIP[st][win]
                if win in ("pre", "may"):
                    eff, stars = linear_effects(coef[0]), coef[1] or "ns"
                    form = "linear"
                else:
                    eff, stars = quad_effects(coef[0], coef[1], mean), coef[2]
                    form = f"quadratic, optimum {eff['optimum']:.2f} in"
                note = (f"Local slope at the 1960-2006 state mean ({mean:.2f} in); {form}; "
                        f"observed range {pmin:.2f}-{pmax:.2f} in; significance {stars}; "
                        f"exact +1 in = {eff['plus1']:+.2f}, -1 in = {eff['minus1']:+.2f}, -2 in = {eff['minus2']:+.2f} bu/ac; "
                        f"% is of the 2006-technology trend yield {trend} bu/ac (Table 6); "
                        f"monthly temperatures held fixed")
                rows.append(_row(
                    crop=crop, region=st, month_or_window=WINDOW_LABEL[win],
                    baseline_precip_in=round(mean, 2),
                    delta_yield_per_inch=round(eff["slope"], 3), yield_units="bu/acre",
                    delta_yield_pct_per_inch=round(100 * eff["slope"] / trend, 2),
                    delta_yield_plus2in=round(eff["plus2"], 3),
                    price_usd_per_unit=price, price_basis=PRICE_BASIS,
                    usd_per_acre_per_inch=round(eff["slope"] * price, 2),
                    valid_range_note=note,
                    model_type=("state time-series OLS 1960-2006, yield level on linear trend, "
                                "Sep-Apr & May rain (linear), Jun-Aug rain (quadratic), "
                                "May-Aug mean temp (linear)"),
                    source_short="Tannura, Irwin & Good 2008 (farmdoc MORR 2008-01), "
                                 f"Table {'8' if crop == 'corn' else '9'}",
                    source_url=TANNURA_URL,
                    verification="CONFIRMED (coefficients and means read in Tables 2, 6, 8, 9; "
                                 "slope arithmetic ours)"))

    # Westcott & Jewison 2013: corn July (national, 8-state weather)
    b1, b2 = WESTCOTT["corn_jul"]
    m = WESTCOTT["corn_jul_mean"]
    e = quad_effects(b1, b2, m)
    rows.append(_row(
        crop="corn", region="US (8-state acre-weighted weather: IA IL NE MN IN SD OH MO)",
        month_or_window="July", baseline_precip_in=m, delta_yield_per_inch=round(e["slope"], 3),
        yield_units="bu/acre",
        delta_yield_pct_per_inch=round(100 * e["slope"] / WESTCOTT["corn_expected_2013"], 2),
        delta_yield_plus2in=round(e["plus2"], 3), price_usd_per_unit=PRICES["corn"][PRICE_KEY],
        price_basis=PRICE_BASIS, usd_per_acre_per_inch=round(e["slope"] * PRICES["corn"][PRICE_KEY], 2),
        valid_range_note=(f"Local slope at the 8-state July mean {m} in; optimum {e['optimum']:.2f} in; "
                          f"t = 2.9 (linear) and -3.2 (squared); exact +1 in = {e['plus1']:+.2f}, -1 in = {e['minus1']:+.2f}, "
                          f"-2 in = {e['minus2']:+.2f} bu/ac; % of the model's 2013 expected yield "
                          f"163.6 bu/ac; July temperature held fixed"),
        model_type="national time-series OLS 1988-2012 (USDA WAOB crop-weather model)",
        source_short="Westcott & Jewison 2013, USDA ERS FDS-13g-01, Table 6",
        source_url=WESTCOTT_URL,
        verification="CONFIRMED (Table 6 coefficients and 3.87-in mean read in report; slope ours)"))
    # corn June shortfall (drought tail only)
    s = WESTCOTT["corn_jun_shortfall"]
    rows.append(_row(
        crop="corn", region="US (8-state acre-weighted weather)",
        month_or_window="June (shortfall, drought tail only)",
        baseline_precip_in=WESTCOTT["corn_jun_mean"], delta_yield_per_inch=round(-s, 3),
        yield_units="bu/acre",
        delta_yield_pct_per_inch=round(100 * -s / WESTCOTT["corn_expected_2013"], 2),
        delta_yield_plus2in="", price_usd_per_unit=PRICES["corn"][PRICE_KEY], price_basis=PRICE_BASIS,
        usd_per_acre_per_inch=round(-s * PRICES["corn"][PRICE_KEY], 2),
        valid_range_note=("Applies ONLY when June rain is at least 1.82 in below the 4.33-in "
                          "average (lowest 10% tail, e.g. 1988, 2012); once triggered the model "
                          "subtracts 9.54 bu/ac for every inch of the WHOLE shortfall from the "
                          "average (about 17.4 bu/ac at the 1.82-in trigger, 19.1 for a 2-in "
                          "shortfall, 18.7 for 2012's 1.96 in; Westcott & Jewison pp.17, 22), so it "
                          "acts as an on/off step, not a slope (sign here = yield gained per inch "
                          "less shortfall). Zero effect for normal Junes. t = -5.7"),
        model_type="national time-series OLS 1988-2012 (USDA WAOB crop-weather model)",
        source_short="Westcott & Jewison 2013, USDA ERS FDS-13g-01, Table 6",
        source_url=WESTCOTT_URL, verification="CONFIRMED (Table 6, p.17 text)"))
    # Irwin & Hubbs 2020 update of the WAOB corn model
    b1, b2 = IRWIN_HUBBS["jul"]
    m = IRWIN_HUBBS["jul_mean"]
    e = quad_effects(b1, b2, m)
    rows.append(_row(
        crop="corn", region="US (8-state acre-weighted weather)", month_or_window="July",
        baseline_precip_in=m, delta_yield_per_inch=round(e["slope"], 3), yield_units="bu/acre",
        delta_yield_pct_per_inch=round(100 * e["slope"] / IRWIN_HUBBS["forecast_2020"], 2),
        delta_yield_plus2in=round(e["plus2"], 3), price_usd_per_unit=PRICES["corn"][PRICE_KEY],
        price_basis=PRICE_BASIS, usd_per_acre_per_inch=round(e["slope"] * PRICES["corn"][PRICE_KEY], 2),
        valid_range_note=(f"Local slope at the 1988-2019 sample-average July rain {m} in; optimum "
                          f"{e['optimum']:.2f} in; t = 2.53 / -2.47; exact +1 in = {e['plus1']:+.2f}, -1 in = {e['minus1']:+.2f}, "
                          f"-2 in = {e['minus2']:+.2f} bu/ac; % of the 2020 WASDE trend 178.5 bu/ac"),
        model_type="national time-series OLS 1988-2019 (WAOB model re-estimated)",
        source_short="Irwin & Hubbs 2020, farmdoc daily (10):121, Table 2",
        source_url=IRWIN_HUBBS_URL,
        verification="CONFIRMED (Table 2 coefficients and 3.856-in average read; slope ours)"))
    return rows


def westcott_soy_rows(weather: dict, acres_soy: pd.DataFrame) -> tuple[list[dict], float]:
    """Soybean rows for Westcott & Jewison (2013) Table 7.

    The report does not print the 7-state mean of July-August average monthly rain, so we compute
    it from NOAA nClimDiv weighted by NASS harvested soybean acres, 1988-2012 (COMPUTED input).
    The model variable is the AVERAGE of July and August monthly totals; we convert to effects per
    inch of the July+August TOTAL (1 inch of total = 0.5 inch of the average).
    """
    yrs = range(1988, 2013)
    num = den = 0.0
    for y in yrs:
        for st in SOY7:
            a = acres_soy.loc[y, st]
            num += a * weather[st].loc[y, "julaug_avg"]
            den += a
    mean_avg = num / den
    b1, b2 = WESTCOTT["soy_julaug"]
    slope_avg = b1 + 2 * b2 * mean_avg
    slope_total = slope_avg / 2
    plus2_total = b1 * 1.0 + b2 * ((mean_avg + 1.0) ** 2 - mean_avg ** 2)
    price = PRICES["soybeans"][PRICE_KEY]
    rows = [_row(
        crop="soybeans", region="US (7-state acre-weighted weather: IA IL MN NE IN OH MO)",
        month_or_window="July+August (2-month total)", baseline_precip_in=round(2 * mean_avg, 2),
        delta_yield_per_inch=round(slope_total, 3), yield_units="bu/acre",
        delta_yield_pct_per_inch=round(100 * slope_total / WESTCOTT["soy_expected_2013"], 2),
        delta_yield_plus2in=round(plus2_total, 3), price_usd_per_unit=price, price_basis=PRICE_BASIS,
        usd_per_acre_per_inch=round(slope_total * price, 2),
        valid_range_note=(f"Model uses the Jul-Aug AVERAGE monthly rain (b1 5.083, b2 -0.619, "
                          f"t = 1.1 / -1.2, NOT statistically significant); optimum "
                          f"{-b1 / (2 * b2):.2f} in/month; baseline is our computed 1988-2012 "
                          f"7-state acre-weighted mean ({mean_avg:.2f} in/month); per inch of "
                          f"the Jul+Aug total; % of the model's 2013 expected yield 44.5 bu/ac"),
        model_type="national time-series OLS 1988-2012 (USDA WAOB crop-weather model)",
        source_short="Westcott & Jewison 2013, USDA ERS FDS-13g-01, Table 7",
        source_url=WESTCOTT_URL,
        verification=("CONFIRMED coefficients (Table 7); baseline mean COMPUTED from NOAA "
                      "nClimDiv + NASS acres"))]
    s = WESTCOTT["soy_jun_shortfall"]
    rows.append(_row(
        crop="soybeans", region="US (7-state acre-weighted weather)",
        month_or_window="June (shortfall, drought tail only)",
        baseline_precip_in=WESTCOTT["soy_jun_mean"], delta_yield_per_inch=round(-s, 3),
        yield_units="bu/acre",
        delta_yield_pct_per_inch=round(100 * -s / WESTCOTT["soy_expected_2013"], 2),
        delta_yield_plus2in="", price_usd_per_unit=price, price_basis=PRICE_BASIS,
        usd_per_acre_per_inch=round(-s * price, 2),
        valid_range_note=("Applies ONLY when June rain is at least 1.91 in below the 4.41-in "
                          "average; once triggered the model subtracts 1.28 bu/ac for every inch "
                          "of the WHOLE shortfall from the average (about 2.4 bu/ac at the trigger, "
                          "2.56 for a 2-in shortfall; Westcott & Jewison p.20). t = -1.8"),
        model_type="national time-series OLS 1988-2012 (USDA WAOB crop-weather model)",
        source_short="Westcott & Jewison 2013, USDA ERS FDS-13g-01, Table 7",
        source_url=WESTCOTT_URL, verification="CONFIRMED (Table 7, p.20 text)"))
    return rows, mean_avg


# =============================================================================================
# 4. Our own re-estimation of the Tannura et al. model
# =============================================================================================
THOMPSON_COLS = ["t", "pre", "may", "jun", "jun2", "jul", "jul2", "aug", "aug2",
                 "t_may", "t_jun", "t_jul", "t_aug"]


def thompson_design(w: pd.DataFrame, years, with_temps: bool = True) -> tuple[np.ndarray, list]:
    """Design matrix of the modified Thompson model (Tannura et al. 2008, eq. 2)."""
    d = w.loc[list(years)].copy()
    d["t"] = d.index - 1959
    for m in ("jun", "jul", "aug"):
        d[m + "2"] = d[m] ** 2
    cols = [c for c in THOMPSON_COLS if with_temps or not c.startswith("t_")]
    X = np.column_stack([np.ones(len(d))] + [d[c].to_numpy(float) for c in cols])
    return X, ["const"] + cols


def fit_thompson(yields: pd.Series, w: pd.DataFrame, start: int, end: int,
                 log: bool = False, with_temps: bool = True) -> dict:
    """Fit the modified Thompson model for one state and crop over [start, end]."""
    years = [y for y in range(start, end + 1) if y in yields.index and y in w.index
             and pd.notna(yields.get(y))]
    X, names = thompson_design(w, years, with_temps)
    y = yields.loc[years].to_numpy(float)
    res = ols(np.log(y) if log else y, X)
    res.update({"names": names, "years": years, "X": X})
    return res


def slopes_from_fit(res: dict, base: dict) -> dict:
    """Per-window effects from a fitted Thompson model at baseline rainfall `base`."""
    b = dict(zip(res["names"], res["beta"]))
    se = dict(zip(res["names"], res["se"]))
    out = {}
    for win in ("pre", "may"):
        out[win] = linear_effects(b[win]) | {"t1": b[win] / se[win], "t2": np.nan}
    for win in ("jun", "jul", "aug"):
        out[win] = quad_effects(b[win], b[win + "2"], base[win]) | {
            "t1": b[win] / se[win], "t2": b[win + "2"] / se[win + "2"]}
    return out


def trend_yield_at(res: dict, w: pd.DataFrame, year: int, base: dict) -> float:
    """Fitted yield in `year` with weather at the baseline (normal) values."""
    b = dict(zip(res["names"], res["beta"]))
    val = b["const"] + b["t"] * (year - 1959)
    for k, v in b.items():
        if k in ("const", "t"):
            continue
        if k.endswith("2"):
            val += v * base[k[:-1]] ** 2
        else:
            val += v * base[k]
    return float(val)


def normals(w: pd.DataFrame) -> dict:
    """1991-2020 means of the model's weather variables."""
    sub = w.loc[NORMAL_YEARS[0]:NORMAL_YEARS[1]]
    return {c: float(sub[c].mean()) for c in w.columns}


def own_reestimate(weather: dict, yields: dict) -> tuple[list[dict], pd.DataFrame, dict]:
    """Re-estimate Tannura's model: replication 1960-2006, update 1980-2025, rain-only 1980-2025."""
    rows, coef_rows, summary = [], [], {}
    specs = [("replication 1960-2006", 1960, 2006, True, False),
             ("update 1960-2025", 1960, 2025, True, False),
             ("update 1980-2025", 1980, 2025, True, False),
             ("rain-only 1980-2025", 1980, 2025, False, False),
             ("log update 1980-2025", 1980, 2025, True, True)]
    for crop in ("corn", "soybeans"):
        price = PRICES[crop][PRICE_KEY]
        for st in ("IL", "IN", "IA"):
            w = weather[st]
            base = normals(w)
            for label, a, z, temps, log in specs:
                res = fit_thompson(yields[crop][st], w, a, z, log=log, with_temps=temps)
                for n_, b_, s_ in zip(res["names"], res["beta"], res["se"]):
                    coef_rows.append({"crop": crop, "state": st, "spec": label, "term": n_,
                                      "coef": b_, "se": s_, "r2": res["r2"], "n": res["n"],
                                      "rmse": res["rmse"]})
                if label.startswith("replication"):
                    sample_mean = {c: float(w.loc[a:z, c].mean()) for c in w.columns}
                    summary[(crop, st, label)] = {"fit": res, "eff": slopes_from_fit(res, sample_mean),
                                                  "base": sample_mean}
                    continue
                eff = slopes_from_fit(res, base)
                trend25 = (np.exp(trend_yield_at(res, w, 2025, base)) if log
                           else trend_yield_at(res, w, 2025, base))
                summary[(crop, st, label)] = {"fit": res, "eff": eff, "base": base,
                                              "trend2025": trend25}
                if label == "update 1960-2025":
                    continue  # kept for the doc's robustness table, not the CSV
                for win, e in eff.items():
                    t_txt = (f"t = {e['t1']:.1f}" if np.isnan(e["t2"])
                             else f"t = {e['t1']:.1f} / {e['t2']:.1f}")
                    opt = ("" if np.isnan(e["optimum"]) else f"optimum {e['optimum']:.2f} in; ")
                    if log:
                        # slope is in log points per inch: convert to % and to bu/ac at the
                        # model's own fitted 2025 yield (constant-% assumption)
                        pct = 100 * e["slope"]
                        slope_bu = e["slope"] * trend25
                        plus2_bu = (np.exp(e["plus2"]) - 1) * trend25
                        p1 = f"{100 * (np.exp(e['plus1']) - 1):+.2f}%"
                        m1 = f"{100 * (np.exp(e['minus1']) - 1):+.2f}%"
                        m2 = f"{100 * (np.exp(e['minus2']) - 1):+.2f}%"
                    else:
                        pct = 100 * e["slope"] / trend25
                        slope_bu, plus2_bu = e["slope"], e["plus2"]
                        p1 = f"{e['plus1']:+.2f} bu/ac"
                        m1, m2 = f"{e['minus1']:+.2f} bu/ac", f"{e['minus2']:+.2f} bu/ac"
                    rows.append(_row(
                        crop=crop, region=st, month_or_window=WINDOW_LABEL[win],
                        baseline_precip_in=round(base[win], 2),
                        delta_yield_per_inch=round(slope_bu, 3), yield_units="bu/acre",
                        delta_yield_pct_per_inch=round(pct, 2),
                        delta_yield_plus2in=round(plus2_bu, 3), price_usd_per_unit=price,
                        price_basis=PRICE_BASIS, usd_per_acre_per_inch=round(slope_bu * price, 2),
                        valid_range_note=(f"Local slope at the 1991-2020 normal ({base[win]:.2f} in); "
                                          f"{opt}{t_txt}; exact +1 in = {p1}, -1 in = {m1}, "
                                          f"-2 in = {m2}; "
                                          + ("constant-% model, bu/ac = % x fitted 2025 yield "
                                             if log else "% of fitted 2025 yield ")
                                          + f"at normal weather ({trend25:.1f} bu/ac); "
                                          f"n = {res['n']}, R2 = {res['r2']:.2f}"
                                          + ("; temperatures OMITTED so rain also proxies for the "
                                             "heat that accompanies dry months" if not temps else
                                             "; monthly temperatures held fixed")),
                        model_type=(f"state time-series OLS {a}-{z}, Tannura et al. specification"
                                    + (" without temperature terms" if not temps else "")
                                    + (", log(yield)" if log else ", yield level (bu/ac)")),
                        source_short=f"Own re-estimate ({label}), NASS yields + NOAA nClimDiv",
                        source_url=("https://quickstats.nass.usda.gov ; "
                                    "https://www.ncei.noaa.gov/access/monitoring/climate-at-a-glance/"),
                        verification="COMPUTED (own OLS on public data; not peer reviewed)"))
    return rows, pd.DataFrame(coef_rows), summary


# =============================================================================================
# 5. Schlenker-Roberts-style season-total quadratic on a state panel
# =============================================================================================
PANEL_STATES = ["IL", "IN", "IA", "OH", "MO", "MN", "WI", "MI", "KY"]


def season_quadratic_panel(weather: dict, yields: dict) -> dict:
    """log(yield) on a quadratic in March-August rain and mean temperature, state fixed effects
    and state-specific quadratic trends, 1960-2025, nine mostly rain-fed eastern states.

    This mimics only the precipitation part of Schlenker & Roberts (2009), who used county data,
    1950-2005, and degree days; it is a rough, state-level analog used to show the curvature.
    """
    out = {}
    for crop in ("corn", "soybeans"):
        recs = []
        for st in PANEL_STATES:
            for y in range(1960, 2026):
                yv = yields[crop].get(st, pd.Series(dtype=float)).get(y)
                if yv is None or pd.isna(yv) or y not in weather[st].index:
                    continue
                recs.append({"st": st, "year": y, "lny": np.log(yv),
                             "p": weather[st].loc[y, "mar_aug"],
                             "tm": weather[st].loc[y, "t_mar_aug"]})
        d = pd.DataFrame(recs)
        cols, names = [], []
        for st in PANEL_STATES:
            ind = (d["st"] == st).astype(float).to_numpy()
            tt = (d["year"] - 1990).to_numpy(float)
            cols += [ind, ind * tt, ind * tt ** 2]
            names += [f"fe_{st}", f"tr_{st}", f"tr2_{st}"]
        cols += [d["p"].to_numpy(), d["p"].to_numpy() ** 2, d["tm"].to_numpy(),
                 d["tm"].to_numpy() ** 2]
        names += ["p", "p2", "tm", "tm2"]
        res = ols(d["lny"].to_numpy(), np.column_stack(cols))
        b = dict(zip(names, res["beta"]))
        se = dict(zip(names, res["se"]))
        popt = -b["p"] / (2 * b["p2"])
        pmean = float(d["p"].mean())
        out[crop] = {
            "b1": b["p"], "b2": b["p2"], "se1": se["p"], "se2": se["p2"], "optimum": popt,
            "mean": pmean, "sd": float(d["p"].std()), "n": res["n"], "r2": res["r2"],
            "slope_pct_at_mean": 100 * (b["p"] + 2 * b["p2"] * pmean),
            **{f"loss_pct_{k}in_from_optimum": 100 * (np.exp(b["p2"] * k ** 2) - 1) for k in (2, 4, 6, 8)},
            "pmin": float(d["p"].min()), "pmax": float(d["p"].max()),
        }
    return out


# =============================================================================================
# 6. 2012 drought and irrigation tables
# =============================================================================================
DROUGHT_STATES = ["IA", "IL", "NE", "MN", "IN", "SD", "OH", "MO"]


def drought_2012(weather: dict, yields: dict) -> pd.DataFrame:
    """2012 yield vs a 1988-2011 linear trend, and June-July 2012 rain vs the 1991-2020 normal."""
    recs = []
    for st in DROUGHT_STATES + ["US"]:
        rec = {"region": st}
        for crop in ("corn", "soybeans"):
            s = yields[crop][st].dropna()
            hist = s.loc[1988:2011]
            k, c = np.polyfit(hist.index.to_numpy(float), hist.to_numpy(float), 1)
            trend = k * 2012 + c
            rec[f"{crop}_2012"] = float(s.loc[2012])
            rec[f"{crop}_trend_1988_2011"] = round(trend, 1)
            rec[f"{crop}_pct_vs_trend"] = round(100 * (s.loc[2012] / trend - 1), 1)
        if st != "US":
            w = weather[st]
            nj = float(w.loc[NORMAL_YEARS[0]:NORMAL_YEARS[1], "jun_jul"].mean())
            nju = float(w.loc[NORMAL_YEARS[0]:NORMAL_YEARS[1], "jul"].mean())
            rec.update({"jun_jul_2012_in": round(float(w.loc[2012, "jun_jul"]), 2),
                        "jun_jul_normal_in": round(nj, 2),
                        "jun_jul_pct_normal": round(100 * w.loc[2012, "jun_jul"] / nj, 0),
                        "jul_2012_in": round(float(w.loc[2012, "jul"]), 2),
                        "jul_normal_in": round(nju, 2),
                        "aug_2012_pct_normal": round(float(100 * w.loc[2012, "aug"] / w.loc[NORMAL_YEARS[0]:NORMAL_YEARS[1], "aug"].mean()), 0),
                        "jul_temp_2012_F": float(w.loc[2012, "t_jul"]),
                        "jul_temp_normal_F": round(float(
                            w.loc[NORMAL_YEARS[0]:NORMAL_YEARS[1], "t_jul"].mean()), 1)})
        recs.append(rec)
    return pd.DataFrame(recs)


def irrigation_2022() -> pd.DataFrame:
    """2022 Census of Agriculture irrigated share of harvested acres, corn for grain and soybeans."""
    recs = {}
    for crop, commodity in (("corn", "CORN"), ("soybeans", "SOYBEANS")):
        for level in ("STATE", "NATIONAL"):
            df = nass_quickstats({"source_desc": "CENSUS", "year": "2022",
                                  "agg_level_desc": level, "commodity_desc": commodity,
                                  "statisticcat_desc": "AREA HARVESTED", "domain_desc": "TOTAL"},
                                 f"census2022_{crop}_{level.lower()}")
            for _, r in df.iterrows():
                key = "US" if level == "NATIONAL" else r["State"]
                if r["Data Item"] == ACRE_ITEMS[crop]:
                    recs.setdefault(key, {})[f"{crop}_acres"] = r["Value_num"]
                elif r["Data Item"] == IRRIG_ITEMS[crop]:
                    recs.setdefault(key, {})[f"{crop}_irrigated_acres"] = r["Value_num"]
    df = pd.DataFrame.from_dict(recs, orient="index")
    for crop in ("corn", "soybeans"):
        df[f"{crop}_irrigated_pct"] = (100 * df[f"{crop}_irrigated_acres"] /
                                       df[f"{crop}_acres"]).round(1)
    df.index.name = "state"
    return df.sort_values("corn_acres", ascending=False)


# =============================================================================================
# 7. Figures
# =============================================================================================
COLORS = {"IL": "#2a78d6", "IN": "#eb6834", "IA": "#1baf7a"}
STYLES = {"IL": "-", "IN": "--", "IA": ":"}
MARKERS = {"IL": "o", "IN": "s", "IA": "^"}


def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False,
                         "axes.edgecolor": "#898781", "axes.grid": True, "grid.color": "#e1e0d9",
                         "grid.linewidth": 0.6, "figure.facecolor": "#fcfcfb",
                         "axes.facecolor": "#fcfcfb"})
    return plt


def fig_response_curves(path: Path) -> None:
    """Yield contribution of July rain (corn) and August rain (soybeans), Tannura et al. (2008)."""
    plt = _plt()
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.8))
    for ax, crop, win, title in ((axes[0], "corn", "jul", "Corn: July rain"),
                                 (axes[1], "soybeans", "aug", "Soybeans: August rain")):
        p = np.linspace(0.5, 9.5, 200)
        for st in ("IL", "IN", "IA"):
            b1, b2, _ = TANNURA[crop][st][win]
            mean = TANNURA_PRECIP[st][win][0]
            y = b1 * p + b2 * p ** 2 - (b1 * mean + b2 * mean ** 2)
            pct = 100 * y / TANNURA_TREND_2006[crop][st]
            ax.plot(p, pct, STYLES[st], color=COLORS[st], lw=2, label=st)
            ax.plot([mean], [0], MARKERS[st], color=COLORS[st], ms=8, mec="#fcfcfb", mew=1.5)
            opt = -b1 / (2 * b2)
            if opt < 9.5:
                yo = 100 * (b1 * opt + b2 * opt ** 2 - (b1 * mean + b2 * mean ** 2)) / \
                    TANNURA_TREND_2006[crop][st]
                ax.plot([opt], [yo], "|", color=COLORS[st], ms=12, mew=2)
        ax.axhline(0, color="#c3c2b7", lw=1)
        ax.set_title(title)
        ax.set_xlabel("Monthly statewide precipitation (inches)")
        ax.set_ylim(-40 if crop == "corn" else -25, 8)
        ax.legend(title="State (marker = 1960-2006 mean,\n| = yield-maximising rain)",
                  fontsize=8, title_fontsize=7, loc="lower right", frameon=False)
    axes[0].set_ylabel("Yield change vs. average-rain month\n(% of 2006 trend yield)")
    fig.suptitle("Yield response to one month's rain is a hill: steep when dry, flat near the top "
                 "(Tannura, Irwin & Good 2008)", fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fig_slopes_by_month(lit_rows: list[dict], path: Path) -> None:
    """Grouped bars: % yield change per +1 inch at the mean, by month, state and crop."""
    plt = _plt()
    df = pd.DataFrame(lit_rows)
    df = df[df["source_short"].str.startswith("Tannura")]
    months = ["May", "June", "July", "August"]
    hatches = {"IL": "", "IN": "///", "IA": "..."}
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.6), sharey=True)
    for ax, crop in zip(axes, ("corn", "soybeans")):
        sub = df[df["crop"] == crop]
        x = np.arange(len(months))
        for i, st in enumerate(("IL", "IN", "IA")):
            vals = [float(sub[(sub["region"] == st) & (sub["month_or_window"] == m)]
                          ["delta_yield_pct_per_inch"].iloc[0]) for m in months]
            ax.bar(x + (i - 1) * 0.26, vals, width=0.24, color=COLORS[st], hatch=hatches[st],
                   edgecolor="#fcfcfb", linewidth=0.8, label=st)
        ax.axhline(0, color="#898781", lw=1)
        ax.set_xticks(x, months)
        ax.set_title(f"{crop.capitalize()}")
        ax.set_xlabel("Month of the extra inch")
    axes[0].set_ylabel("Yield change for +1 inch at average rain\n(% of 2006 trend yield)")
    axes[1].legend(frameon=False, fontsize=8)
    fig.suptitle("Local slope of yield to rain by month (Tannura, Irwin & Good 2008; "
                 "temperature held fixed)", fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fig_2012(dr: pd.DataFrame, path: Path) -> None:
    """2012: June-July rain as % of normal and corn/soy yield vs trend, by state."""
    plt = _plt()
    d = dr[dr["region"] != "US"].copy()
    d = d.sort_values("corn_pct_vs_trend")
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.6), sharey=True)
    y = np.arange(len(d))
    axes[0].barh(y, d["jun_jul_pct_normal"], color="#2a78d6", height=0.6)
    axes[0].axvline(100, color="#898781", lw=1, ls="--")
    axes[0].set_xlabel("June+July 2012 rain (% of 1991-2020 normal)")
    axes[0].set_yticks(y, d["region"])
    for yi, v in zip(y, d["jun_jul_pct_normal"]):
        axes[0].text(v + 2, yi, f"{v:.0f}%", va="center", fontsize=8, color="#52514e")
    axes[1].barh(y - 0.17, d["corn_pct_vs_trend"], height=0.32, color="#eb6834", label="Corn")
    axes[1].barh(y + 0.17, d["soybeans_pct_vs_trend"], height=0.32, color="#1baf7a",
                 hatch="///", edgecolor="#fcfcfb", label="Soybeans")
    axes[1].axvline(0, color="#898781", lw=1)
    axes[1].set_xlabel("2012 yield vs 1988-2011 linear trend (%)")
    axes[1].legend(frameon=False, fontsize=8, loc="upper left")
    fig.suptitle("The 2012 drought: dry, hot June-July and yield shortfalls by state "
                 "(NOAA nClimDiv, USDA NASS)", fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


# =============================================================================================
# main
# =============================================================================================
def main() -> None:
    states = sorted(set(CORN8 + SOY7 + PANEL_STATES + DROUGHT_STATES))
    weather = {st: state_weather(st) for st in states}
    yields = {c: state_series(c, YIELD_ITEMS, "yield") for c in ("corn", "soybeans")}
    acres = {c: state_series(c, ACRE_ITEMS, "acres") for c in ("corn", "soybeans")}

    # Check our 8-state corn-acre-weighted July mean against Westcott's published 3.87 in.
    num = den = 0.0
    for y in range(1988, 2013):
        for st in CORN8:
            num += acres["corn"].loc[y, st] * weather[st].loc[y, "jul"]
            den += acres["corn"].loc[y, st]
    print(f"8-state corn-acre-weighted July rain 1988-2012: {num / den:.2f} in "
          f"(Westcott & Jewison report 3.87)")

    lit = literature_rows()
    soy_rows, soy_mean = westcott_soy_rows(weather, acres["soybeans"])
    print(f"7-state soy-acre-weighted Jul-Aug average monthly rain 1988-2012: {soy_mean:.2f} in")
    own_rows, coefs, summary = own_reestimate(weather, yields)
    coefs.to_csv(DERIVED / "r1_reestimate_coefficients.csv", index=False)

    rows = lit + soy_rows + own_rows
    out = pd.DataFrame(rows, columns=CSV_COLUMNS)
    out.to_csv(OUT_CSV, index=False)
    print(f"wrote {OUT_CSV} ({len(out)} rows)")

    # Replication check vs Tannura Table 8/9 (printed for the doc)
    print("\nReplication 1960-2006 (our data) vs Tannura published slope at mean, bu/ac per inch")
    for crop in ("corn", "soybeans"):
        for st in ("IL", "IN", "IA"):
            s = summary[(crop, st, "replication 1960-2006")]
            pub = {r["month_or_window"]: r["delta_yield_per_inch"] for r in lit
                   if r["crop"] == crop and r["region"] == st}
            txt = ", ".join(f"{WINDOW_LABEL[w][:3]} {s['eff'][w]['slope']:+.2f} "
                            f"(pub {pub[WINDOW_LABEL[w]]:+.2f})" for w in ("may", "jun", "jul", "aug"))
            print(f"  {crop:8s} {st}: R2 {s['fit']['r2']:.2f} | {txt}")

    print("\nUpdated models, slope at 1991-2020 normal (bu/ac per inch) and % of fitted 2025 yield")
    for crop in ("corn", "soybeans"):
        for st in ("IL", "IN", "IA"):
            for label in ("update 1960-2025", "update 1980-2025", "rain-only 1980-2025",
                          "log update 1980-2025"):
                s = summary[(crop, st, label)]
                if label.startswith("log"):
                    txt = ", ".join(f"{WINDOW_LABEL[w][:3]} {100 * s['eff'][w]['slope']:+.2f}%"
                                    for w in ("may", "jun", "jul", "aug"))
                else:
                    txt = ", ".join(f"{WINDOW_LABEL[w][:3]} {s['eff'][w]['slope']:+.2f} "
                                    f"({100 * s['eff'][w]['slope'] / s['trend2025']:+.2f}%)"
                                    for w in ("may", "jun", "jul", "aug"))
                print(f"  {crop:8s} {st} {label:22s} R2 {s['fit']['r2']:.2f} trend2025 "
                      f"{s['trend2025']:.1f} | {txt}")
            base = summary[(crop, st, "update 1980-2025")]["base"]
            print(f"     normals 1991-2020: " + ", ".join(f"{k} {base[k]:.2f}" for k in
                                                       ("pre", "may", "jun", "jul", "aug",
                                                        "t_jul", "t_aug")))

    panel = season_quadratic_panel(weather, yields)
    print("\nSeason (Mar-Aug) rain quadratic, 9-state panel, log yield")
    for crop, r in panel.items():
        print(f"  {crop}: b1 {r['b1']:.4f} ({r['se1']:.4f}) b2 {r['b2']:.5f} ({r['se2']:.5f}) "
              f"optimum {r['optimum']:.1f} in, mean {r['mean']:.1f} sd {r['sd']:.1f} "
              f"[{r['pmin']:.1f}-{r['pmax']:.1f}], slope at mean {r['slope_pct_at_mean']:.2f}%/in, "
              f"loss at optimum+/-k in: " +
              ", ".join(f"{k}: {r[f'loss_pct_{k}in_from_optimum']:.1f}%" for k in (2, 4, 6, 8)) +
              f"; n {r['n']} R2 {r['r2']:.3f}")
    pd.DataFrame(panel).T.to_csv(DERIVED / "r1_season_quadratic_panel.csv")

    dr = drought_2012(weather, yields)
    dr.to_csv(DERIVED / "r1_drought_2012.csv", index=False)
    print("\n2012 drought table")
    print(dr.to_string(index=False))

    irr = irrigation_2022()
    irr.to_csv(DERIVED / "r1_irrigation_share_2022.csv")
    print("\n2022 Census irrigated share (top 15 corn states + US)")
    print(irr.head(16).to_string())

    fig_response_curves(FIGURES / "r1_response_curves_tannura.png")
    fig_slopes_by_month(lit, FIGURES / "r1_slope_by_month_tannura.png")
    fig_2012(dr, FIGURES / "r1_drought_2012.png")
    print("figures written")


if __name__ == "__main__":
    main()
