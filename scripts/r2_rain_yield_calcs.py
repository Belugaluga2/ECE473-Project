"""R2: how rainfall moves forage, hay, wheat, sorghum, cotton and rice yields (lb, %, $ per acre).

Run from the repo root:

    python scripts/r2_rain_yield_calcs.py
    python scripts/r2_rain_yield_calcs.py --reprice-csv   # only re-price the hay rows of the CSV at
                                                         # the price constants below (no downloads)

Outputs
-------
* data/processed/crop_rain_sensitivity_other.csv   one row per crop x region x window x source,
  keyed by `row_key` (farm scenarios reference rows by this key; rows named `scen_<farm_id>`
  hold the elasticity for each farm in data/scenarios/farms.yaml).
* docs/figures/r2_*.png                             figures used by
  docs/research/03b_rain_yield_forage_and_other_crops.md
* Auxiliary tables (regenerated every run, gitignored) in data/raw/r2_rain_yield/derived/.

Inputs (downloaded once and cached under data/raw/r2_rain_yield/, so reruns are offline)
----------------------------------------------------------------------------------------
* USDA ARS Grass-Cast historical productivity, 1982-2019, 10 km grid (https://grasscast.unl.edu/Data.aspx).
  The per-cell ANPP in these files is a deterministic function of DayCent-simulated April-August
  actual evapotranspiration that was calibrated county by county to AVHRR NDVI (Hartman et al.
  2020, Ecosphere 11:e03280, Eqs. 1-5). It is a satellite-calibrated MODEL estimate, not clipped
  biomass. Reading the .xlsx needs openpyxl; the extracted study-county subset is cached as CSV.
* NRCS Ecological Site Descriptions (EDIT JSON services), reference-community annual production
  (low / representative / high lb/acre air-dry) and growth curves. The values are typed into ESDS
  below; the EDIT JSON and catalog pages they were read from are cached in data/raw/r2_rain_yield/esd/.
* USDA NASS Quick Stats (keyless CSV export used by the Quick Stats web page: /uuid/encode then
  /data/spreadsheet/<uuid>.csv): state and county "HAY, (EXCL ALFALFA)" yields; crop yields.
* NOAA NCEI Climate at a Glance statewide monthly precipitation (nClimDiv).
* Repo files written by other workstreams (read only): data/processed/ncei_monthly_precip_grids.parquet
  (NCEI nClimGrid monthly precipitation averaged to PRF 0.25-degree grids), data/processed/
  prf_official_index.csv (official RMA PRF interval index values), data/processed/study_grids.csv,
  data/scenarios/farms.yaml.

Method summary
--------------
1. Literature rows: published coefficients typed in with page/table references (CONFIRMED), with
   unit conversions done here (1 g/m2 = 8.9218 lb/acre; 1 inch = 25.4 mm).
2. ESD-implied slopes: Sala et al. (1988, Ecology 69:40, p.42) state that the SCS "favorable" and
   "unfavorable" production years are the wettest 10% and driest 10% of years. We therefore divide
   (High - Low) production by the difference between the mean annual precipitation of the wettest
   and driest deciles of 1951-2025 years on the farm's PRF grid. This attributes ALL of the
   favorable-unfavorable gap to precipitation, so it is an upper-end slope (DERIVED).
3. Grass-Cast county regressions: county-mean ANPP (1982-2019) on precipitation windows (COMPUTED).
4. NASS hay regressions: yield on a linear trend plus window precipitation, state (1975-2025) and
   county (Grady OK 1960-2018; Parker TX 1972-1986) (COMPUTED).
5. Scenario elasticities: for each farm in farms.yaml, regress production relative to its mean
   (or trend) on W/100, where W = sum over the farm's insured intervals of
   allocation x PRF index (the same weighted index scripts/run_scenarios.py uses). The slope is
   the elasticity "fraction of production lost per unit of fractional shortfall in W".
6. Dollars: hay at NASS final 2025 marketing-year prices ($/ton, Agricultural Prices Aug 2026); grazing at
   the county pasture cash rent per pound of normal-year forage (the same value basis as
   farms.yaml); crops at WASDE-676 (Oct 9 2026) 2026/27 season-average farm prices.
"""
from __future__ import annotations

import json
import time
import urllib.parse
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import yaml

from agri_hedge.config import FIGURES, PROCESSED, RAW, ROOT, SCENARIOS
from agri_hedge.prf_intervals import INTERVAL_MONTHS, INTERVAL_NAMES

RAW_DIR = RAW / "r2_rain_yield"
DERIVED = RAW_DIR / "derived"
for _d in (RAW_DIR, DERIVED, RAW_DIR / "nass", RAW_DIR / "noaa", RAW_DIR / "grasscast"):
    _d.mkdir(parents=True, exist_ok=True)
HEADERS = {"User-Agent": "Mozilla/5.0 (ECE473 agri-hedge research; Princeton)"}

OUT_CSV = PROCESSED / "crop_rain_sensitivity_other.csv"
CSV_COLUMNS = [
    "row_key", "crop", "region", "month_or_window", "baseline_precip_in", "delta_yield_per_inch",
    "yield_units", "delta_yield_pct_per_inch", "delta_yield_plus2in", "price_usd_per_unit",
    "price_basis", "usd_per_acre_per_inch", "valid_range_note", "model_type", "source_short",
    "source_url", "verification", "rain_elasticity",
]

# ---------------------------------------------------------------------------------------------
# Unit conversions
# ---------------------------------------------------------------------------------------------
LB_AC_PER_G_M2 = 8.92179      # 1 g/m2 = 10 kg/ha = 8.92179 lb/acre
LB_AC_PER_KG_HA = 0.892179
MM_PER_IN = 25.4
CM_PER_IN = 2.54
SHORT_TON_AC_PER_T_HA = 0.446090

# ---------------------------------------------------------------------------------------------
# Prices (all CONFIRMED in the primary report; page/table in the basis text)
# ---------------------------------------------------------------------------------------------
CROP_VALUES_URL = "https://usda.library.cornell.edu/sites/default/release-files/795791/cpvl0226.pdf"
AG_PRICES_URL = "https://release.nass.usda.gov/reports/agpr0826.pdf"
# Hay prices: FINAL 2025 marketing-year averages, NASS Agricultural Prices (Aug 31 2026), table
# "Hay Market Year Average Prices Received - States and United States: Marketing Years 2024 and
# 2025", p.33 (columns Other / Alfalfa, 2025). Crop Values 2025 Summary (Feb 2026) printed
# PRELIMINARY 2025 prices and lists the August 2026 Agricultural Prices as the release of the final
# hay prices (its p.45). These match Quick Stats "HAY, (EXCL ALFALFA) - PRICE RECEIVED, MARKETING
# YEAR" 2025 and the hay prices in data/scenarios/farms.yaml.
HAY_PRICE_2025 = {  # Other hay, $/ton, final 2025 MYA
    "TX": 130.0, "OK": 88.0, "MO": 113.0, "FL": 120.0, "CO": 153.0, "NM": 185.0, "US": 137.0}
HAY_PRICE_2025_PRELIM = {  # superseded: Crop Values 2025 Summary p.33, preliminary (kept for the record)
    "TX": 136.0, "OK": 90.0, "MO": 114.0, "FL": 120.0, "CO": 151.0, "NM": 184.0, "US": 138.0}
HAY_PRICE_BASIS = ("NASS Agricultural Prices (Aug 31 2026), Other hay, final 2025 marketing-year "
                   "average price received, p.33")
ALFALFA_PRICE_US_2025 = 172.0  # same table, US alfalfa hay $/ton, final 2025 (Crop Values prelim: 170)
ALFALFA_PRICE_BASIS = "NASS Agricultural Prices (Aug 31 2026), US alfalfa hay, final 2025 MYA, p.33"
WASDE_URL = "https://www.usda.gov/oce/commodity/wasde/wasde1026.pdf"
WASDE_BASIS = "USDA WASDE-676 (Oct 9 2026), 2026/27 projected season-average farm price"
CROP_PRICES = {  # (price, unit, page)
    "wheat": (6.30, "$/bu", "p.11"), "corn": (4.70, "$/bu", "p.12"),
    "sorghum": (4.50, "$/bu", "p.13"), "rice": (15.20, "$/cwt", "p.14"),
    "soybeans": (12.00, "$/bu", "p.15"), "cotton": (0.77, "$/lb", "p.17 (upland, 77.0 cents/lb)"),
}
GRAZING_FEE_URL = "https://usda.library.cornell.edu/sites/default/release-files/795747/agpr0126.pdf"
GRAZING_FEE_AUM_2025 = {"CO": 23.50, "OK": 11.00, "TX_2024": 14.50, "NM_2024": 17.50, "17state": 23.70}
LB_PER_AUM_AIRDRY = 912.5      # 30 lb air-dry/day (NRCS NRPH 645-H.33) x 30.4 days; Colorado ESDs use 912.5
HARVEST_EFFICIENCY = 0.25      # share of production a grazing animal can be allotted (ESD convention)

# ---------------------------------------------------------------------------------------------
# Study counties: farm PRF grid, Grass-Cast coverage, ESDs, season windows
# ---------------------------------------------------------------------------------------------
STATE_CODES_NOAA = {"TX": 41, "OK": 34, "MO": 23, "FL": 8, "CO": 5, "NM": 29}
STATE_NAMES = {"TX": "TEXAS", "OK": "OKLAHOMA", "MO": "MISSOURI", "FL": "FLORIDA",
               "CO": "COLORADO", "NM": "NEW MEXICO", "KS": "KANSAS", "AR": "ARKANSAS"}
COUNTIES = {
    # site: county name, state, FIPS, Grass-Cast domain, key growing season (months), PRF key interval
    "DFW": dict(county="Parker", st="TX", fips=48367, gc="GP", season=(4, 5, 6), key_int="Apr-May"),
    "SAT": dict(county="Atascosa", st="TX", fips=48013, gc=None, season=(4, 5, 6), key_int="May-Jun"),
    "OKC": dict(county="Grady", st="OK", fips=40051, gc="GP", season=(4, 5, 6), key_int="May-Jun"),
    "SGF": dict(county="Dade", st="MO", fips=29057, gc=None, season=(4, 5, 6), key_int="May-Jun"),
    "DEN": dict(county="Elbert", st="CO", fips=8039, gc="GP", season=(4, 5, 6, 7), key_int="May-Jun"),
    "ABQ": dict(county="Torrance", st="NM", fips=35057, gc="SW", season=(7, 8, 9), key_int="Jul-Aug"),
    "TPA": dict(county="Hardee", st="FL", fips=12049, gc=None, season=(3, 4, 5), key_int="Mar-Apr"),
}
SEASON_LABEL = {(4, 5, 6): "Apr-Jun", (4, 5, 6, 7): "Apr-Jul", (7, 8, 9): "Jul-Sep",
                (3, 4, 5): "Mar-May"}

# ESDs: (site, ESD id, MLRA, name, low, rv, high, growth-curve id, Jan..Dec percent) -- values read
# from EDIT (reference community 1.1 annual production, total lb/acre air-dry) on 2026-10-29.
# Hardee FL R155XY003FL is a legacy SCS range site (no RV; we use the midpoint).
EDIT_BASE = "https://edit.sc.egov.usda.gov/catalogs/esd"
ESDS = [
    ("DFW", "R084BY175TX", "084B", "Tight Sandy Loam 29-33 PZ", 2090, 3110, 4240, "TX5514",
     [2, 2, 8, 10, 20, 23, 5, 3, 10, 10, 5, 2]),
    ("DFW", "R085AY379TX", "085A", "Loamy Slope 30-38", 4000, 6000, 8000, "TX6011",
     [1, 2, 2, 18, 23, 17, 6, 4, 16, 6, 3, 2]),
    ("SAT", "R083AY024TX", "083A", "Tight Sandy Loam", 2000, 3550, 4800, "TX4525",
     [2, 2, 5, 10, 18, 15, 5, 9, 15, 9, 5, 5]),
    ("SAT", "R083AY022TX", "083A", "Loamy Sand", 2000, 3500, 5000, "TX4537",
     [0, 0, 5, 10, 20, 15, 5, 10, 15, 10, 5, 5]),
    ("OKC", "R080AY056OK", "080A", "Loamy Upland", 2500, 4700, 6000, "OK0001 (nearest 80A curve)",
     [0, 1, 5, 10, 20, 30, 10, 5, 10, 6, 2, 1]),
    ("OKC", "R084AY075OK", "084A", "Sandy Loam Savannah", 3200, 4400, 5600, "OK0003",
     [0, 2, 6, 9, 21, 24, 14, 6, 11, 4, 2, 1]),
    ("SGF", "R112XY103KS", "112X", "Loamy Upland", 3000, 4750, 6500, None, None),
    ("DEN", "R067BY024CO", "067B", "Sandy Plains", 800, 1650, 2200, "CO6709",
     [0, 0, 2, 7, 25, 35, 15, 10, 5, 1, 0, 0]),
    ("DEN", "R067BY002CO", "067B", "Loamy Plains", 600, 1300, 1800, "CO6701",
     [0, 0, 2, 8, 20, 28, 15, 12, 10, 5, 0, 0]),
    ("DEN", "R049XB210CO", "049X", "Sandy Foothill", 900, 1600, 2300, None, None),
    ("ABQ", "R042CY109NM", "042C", "Loamy", 395, 900, 1400, None, None),
    ("ABQ", "R042CY108NM", "042C", "Limy", 370, 890, 1390, "NM4208",
     [0, 0, 5, 7, 10, 15, 25, 25, 8, 5, 0, 0]),
    ("TPA", "R155XY003FL", "155", "South Florida Flatwoods (legacy SCS range site)", 3000, 4500, 6000,
     "FSG 155XB141FL Pensacola bahiagrass", [0, 1, 3, 14, 14, 17, 19, 17, 14, 3, 0, 0]),
]
ESD_PRIMARY = {"DFW": "R084BY175TX", "SAT": "R083AY024TX", "OKC": "R080AY056OK",
               "SGF": "R112XY103KS", "DEN": "R067BY002CO", "ABQ": "R042CY109NM", "TPA": "R155XY003FL"}
ESD_URL_FL = "https://ufdc.ufl.edu/UF00000110/00001"

NASS_QS = "https://quickstats.nass.usda.gov"
NOAA_CAG = "https://www.ncei.noaa.gov/access/monitoring/climate-at-a-glance/statewide/time-series"
GRASSCAST_URL = "https://grasscast.unl.edu/Data.aspx"
HAY_ITEM = "HAY, (EXCL ALFALFA) - YIELD, MEASURED IN TONS / ACRE"


# =============================================================================================
# 1. Data access (cached)
# =============================================================================================
def _get(url: str, tries: int = 5) -> requests.Response:
    """HTTP GET with exponential back-off on 429/5xx."""
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


def nass_quickstats(params: dict, name: str) -> pd.DataFrame:
    """NASS Quick Stats query via the keyless CSV export of the web page (cached)."""
    path = RAW_DIR / "nass" / f"{name}.csv"
    if not path.exists():
        query = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
        uuid = _get(f"{NASS_QS}/uuid/encode?{query}").text.strip().strip('"')
        path.write_text(_get(f"{NASS_QS}/data/spreadsheet/{uuid}.csv").text, encoding="utf-8")
        time.sleep(0.5)
    df = pd.read_csv(path, dtype=str)
    if "Value" not in df.columns:
        return pd.DataFrame(columns=["Year", "State", "County", "Value_num"])
    df["Value_num"] = pd.to_numeric(df["Value"].str.replace(",", "").str.strip(), errors="coerce")
    df["Year"] = pd.to_numeric(df["Year"], errors="coerce")
    return df[df["Period"] == "YEAR"]


def nass_state_yield(item: str, st: str, label: str) -> pd.Series:
    """Annual state yield series (index = year)."""
    df = nass_quickstats({"source_desc": "SURVEY", "agg_level_desc": "STATE",
                          "short_desc": item, "reference_period_desc": "YEAR",
                          "state_name": STATE_NAMES[st]}, f"{label}_{st}")
    s = df.groupby("Year")["Value_num"].first().dropna()
    s.index = s.index.astype(int)
    return s.sort_index()


def nass_county_hay(st: str, county: str) -> pd.Series:
    """County 'other hay' yields, tons/acre (index = year)."""
    df = nass_quickstats({"source_desc": "SURVEY", "agg_level_desc": "COUNTY",
                          "state_name": STATE_NAMES[st], "short_desc": HAY_ITEM,
                          "reference_period_desc": "YEAR"}, f"nass_hay_other_yield_county_{STATE_NAMES[st]}")
    df = df[df["County"].str.upper() == county.upper()]
    s = df.groupby("Year")["Value_num"].first().dropna()
    s.index = s.index.astype(int)
    return s.sort_index()


def noaa_state_monthly(st: str) -> pd.DataFrame:
    """Statewide monthly precipitation (in), nClimDiv, year x month table."""
    path = RAW_DIR / "noaa" / f"noaa_cag_{st}_pcp.csv"
    if not path.exists():
        url = f"{NOAA_CAG}/{STATE_CODES_NOAA[st]}/pcp/1/0/1895-2025/data.csv"
        path.write_text(_get(url).text, encoding="utf-8")
        time.sleep(0.3)
    df = pd.read_csv(path, comment="#")
    df = df[df["Value"] > -90]
    df["year"] = df["Date"] // 100
    df["month"] = df["Date"] % 100
    return df.pivot(index="year", columns="month", values="Value")


def farm_grid_ids() -> dict:
    """Farm-point PRF grid id per site (data/processed/study_grids.csv, role == farm)."""
    g = pd.read_csv(PROCESSED / "study_grids.csv", dtype={"grid_id": str})
    g = g[g["role"] == "farm"]
    return dict(zip(g["site"], g["grid_id"]))


_NCEI = None


def grid_monthly(grid_id: str) -> pd.DataFrame:
    """NCEI nClimGrid monthly precipitation (in) for one PRF grid, year x month, 1951-2025."""
    global _NCEI
    if _NCEI is None:
        _NCEI = pd.read_parquet(PROCESSED / "ncei_monthly_precip_grids.parquet")
        _NCEI["grid_id"] = _NCEI["grid_id"].astype(str)
    d = _NCEI[(_NCEI["grid_id"] == str(grid_id)) & (_NCEI["year"] <= 2025)]
    return d.pivot_table(index="year", columns="month", values="precip_in", aggfunc="first")


_IDX = None


def official_index(grid_id: str) -> pd.DataFrame:
    """Official PRF index (100 = normal), year x interval name, for one grid."""
    global _IDX
    if _IDX is None:
        _IDX = pd.read_csv(PROCESSED / "prf_official_index.csv", dtype={"grid_id": str})
    d = _IDX[(_IDX["grid_id"] == str(grid_id)) & (_IDX["year"] <= 2025)]
    w = d.pivot_table(index="year", columns="interval_name", values="index_value", aggfunc="first")
    if w.stack().median() < 5:
        w = w * 100
    return w.reindex(columns=INTERVAL_NAMES)


def grasscast_county(fips: int, domain: str) -> pd.DataFrame:
    """County-mean Grass-Cast ANPP (lb/acre) by year, 1982-2019, plus Grass-Cast's own Apr-Jul
    precipitation (GP domain only, inches). Cached as a study-county subset CSV."""
    gc = RAW_DIR / "grasscast"
    sub = gc / f"gc_{domain.lower()}_study_counties.csv"
    if not sub.exists():
        import csv
        import openpyxl  # only needed once, to extract the subset from the 60 MB workbooks
        src = gc / ("GrassCast_1982-2019_grid_ANPP_GP.xlsx" if domain == "GP"
                    else "GrassCast_1982-2019_grid_ANPP_SW.xlsx")
        if not src.exists():
            url = f"https://grasscast.unl.edu/docs/{src.name}"
            src.write_bytes(_get(url).content)
        want = {v["fips"] for v in COUNTIES.values()}
        wb = openpyxl.load_workbook(src, read_only=True)
        rows = wb.worksheets[0].iter_rows(values_only=True)
        with open(sub, "w", newline="") as fh:
            w = csv.writer(fh)
            hdr = next(rows)
            w.writerow(hdr[:27])
            for r in rows:
                if r[0] in want:
                    w.writerow(r[:27])
    d = pd.read_csv(sub)
    d = d[d["fips"] == fips]
    if domain == "GP":
        out = d.groupby("year").agg(anpp=("ANPP (lbs/ac)", "mean"), ppt_amjj_cm=("PPTamjj (cm)", "mean"),
                                    aet_amjja_cm=("AETamjja (cm)", "mean"), cells=("gridID", "nunique"))
        out["ppt_amjj_in"] = out["ppt_amjj_cm"] / CM_PER_IN
    else:  # SW: predicted Apr-Sep ANPP in g/m2 (the lb/ac columns are spreadsheet formulas)
        out = d.groupby("year").agg(anpp_g=("predicted_Total_ANPP (g biom/m2)", "mean"),
                                    cells=("gridID", "nunique"))
        out["anpp"] = out["anpp_g"] * LB_AC_PER_G_M2
    out.index = out.index.astype(int)
    return out


def load_farms() -> list[dict]:
    with open(SCENARIOS / "farms.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)["farms"]


# =============================================================================================
# 2. Small statistics helpers
# =============================================================================================
def ols(y, X) -> dict:
    """OLS with classical standard errors."""
    y = np.asarray(y, float)
    X = np.asarray(X, float)
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    n, k = X.shape
    s2 = resid @ resid / (n - k)
    cov = s2 * np.linalg.pinv(X.T @ X)
    r2 = 1 - (resid @ resid) / ((y - y.mean()) @ (y - y.mean()))
    return {"beta": beta, "se": np.sqrt(np.diag(cov)), "r2": r2, "n": n, "rmse": float(np.sqrt(s2))}


def window_sum(P: pd.DataFrame, months) -> pd.Series:
    """Sum of monthly precipitation over months (all within the same calendar year)."""
    return P[list(months)].sum(axis=1, min_count=len(months))


def fit_yield_on_rain(y: pd.Series, p: pd.Series, trend: bool, quad: bool = False) -> dict:
    """Regress y on [1, (year), P, (P^2)]. Returns slope at mean P, exact +/- effects, fit stats."""
    df = pd.concat({"y": y, "p": p}, axis=1).dropna()
    t = df.index.values.astype(float) - df.index.values.mean()
    cols = [np.ones(len(df))]
    if trend:
        cols.append(t)
    cols.append(df["p"].values)
    if quad:
        cols.append(df["p"].values ** 2)
    res = ols(df["y"].values, np.column_stack(cols))
    j = 2 if trend else 1
    b1 = res["beta"][j]
    b2 = res["beta"][j + 1] if quad else 0.0
    p0 = df["p"].mean()

    def change(d):
        return b1 * d + b2 * ((p0 + d) ** 2 - p0 ** 2)

    # fitted value at mean rain and at the last year's trend (denominator for %)
    if trend:
        y_ref_last = res["beta"][0] + res["beta"][1] * t[-1] + b1 * p0 + b2 * p0 ** 2
        # partial correlation of yield and rain, both detrended
        T = np.column_stack([np.ones(len(df)), t])
        ry = df["y"].values - T @ np.linalg.lstsq(T, df["y"].values, rcond=None)[0]
        rp = df["p"].values - T @ np.linalg.lstsq(T, df["p"].values, rcond=None)[0]
        r_corr = np.corrcoef(ry, rp)[0, 1]
    else:
        y_ref_last = df["y"].mean()
        r_corr = np.corrcoef(df["y"], df["p"])[0, 1]
    return {"slope": b1 + 2 * b2 * p0, "plus1": change(1), "plus2": change(2), "minus1": change(-1),
            "minus2": change(-2), "se": res["se"][j], "t": b1 / res["se"][j] if res["se"][j] else np.nan,
            "r2": res["r2"], "n": res["n"], "p_mean": p0, "y_mean": df["y"].mean(),
            "y_ref": y_ref_last, "years": (int(df.index.min()), int(df.index.max())),
            "r": r_corr, "p_sd": df["p"].std()}


def _row(**kw) -> dict:
    return {c: kw.get(c, "") for c in CSV_COLUMNS}


def _r(x, nd=2):
    return "" if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), nd)


# =============================================================================================
# 3. Climatology of the farm grids
# =============================================================================================
def climatology() -> pd.DataFrame:
    """Farm-grid monthly normals (1991-2020), annual mean, driest/wettest-decile means (1951-2025)."""
    rows = []
    for site, gid in farm_grid_ids().items():
        if site not in COUNTIES:
            continue
        P = grid_monthly(gid)
        ann = P.sum(axis=1, min_count=12).dropna()
        ann = ann[(ann.index >= 1951) & (ann.index <= 2025)]
        n10 = max(1, int(round(0.10 * len(ann))))
        s = ann.sort_values()
        normals = P.loc[1991:2020].mean()
        rec = {"site": site, "grid_id": gid, "county": COUNTIES[site]["county"],
               "annual_mean_1951_2025": ann.mean(), "annual_cv": ann.std() / ann.mean(),
               "annual_normal_1991_2020": normals.sum(),
               "dry_decile_mean": s.iloc[:n10].mean(), "wet_decile_mean": s.iloc[-n10:].mean(),
               "p10": ann.quantile(0.10), "p90": ann.quantile(0.90), "n_years": len(ann)}
        for m in range(1, 13):
            rec[f"m{m:02d}"] = normals[m]
        for name, (a, b) in INTERVAL_MONTHS.items():
            v = P[[a, b]].sum(axis=1)
            rec[f"int_{name}_mean"] = v.loc[1991:2020].mean()
            rec[f"int_{name}_cv"] = v.loc[1951:2025].std() / v.loc[1951:2025].mean()
        rows.append(rec)
    out = pd.DataFrame(rows).set_index("site")
    out.to_csv(DERIVED / "r2_farm_grid_climatology.csv")
    return out


# =============================================================================================
# 4. Rangeland / pasture forage rows
# =============================================================================================
def county_value_basis(farms: list[dict]) -> dict:
    """Per site: grazing value ($/acre) and normal-year production (lb/acre) from farms.yaml."""
    out = {}
    for f in farms:
        if f["intended_use"] == "grazing":
            out[f["site"]] = (float(f["expected_value_usd_per_acre"]),
                              float(f["expected_production"]["value"]), f["farm_id"])
    return out


def esd_rows(clim: pd.DataFrame, values: dict) -> tuple[list[dict], pd.DataFrame]:
    """ESD-implied slope: (High - Low) / (wet-decile mean - dry-decile mean annual precip)."""
    rows, aux = [], []
    for site, esd, mlra, name, lo, rv, hi, curve, _ in ESDS:
        c = clim.loc[site]
        dp = c["wet_decile_mean"] - c["dry_decile_mean"]
        slope = (hi - lo) / dp
        pct = 100 * slope / rv
        elast = slope * c["annual_mean_1951_2025"] / rv
        rent, prod, farm_id = values.get(site, (np.nan, np.nan, ""))
        usd_lb = rent / prod if prod else np.nan
        cty = COUNTIES[site]
        url = ESD_URL_FL if site == "TPA" else f"{EDIT_BASE}/{mlra}/{esd}"
        key = f"forage_rangeland_{cty['st']}_{cty['county']}_{esd}_annual"
        aux.append({"site": site, "esd": esd, "low": lo, "rv": rv, "high": hi,
                    "dry_decile_in": c["dry_decile_mean"], "wet_decile_in": c["wet_decile_mean"],
                    "slope_lb_per_in": slope, "pct_per_in": pct, "elasticity": elast,
                    "p_annual_mean": c["annual_mean_1951_2025"],
                    "range_pct_of_rv": 100 * (hi - lo) / rv})
        rows.append(_row(
            row_key=key, crop="forage (rangeland, ESD reference community)",
            region=f"{cty['county']} Co., {cty['st']} (farm PRF grid {c['grid_id']})",
            month_or_window="annual (calendar-year precipitation)",
            baseline_precip_in=_r(c["annual_mean_1951_2025"]),
            delta_yield_per_inch=_r(slope, 1), yield_units="lb air-dry forage/acre",
            delta_yield_pct_per_inch=_r(pct), delta_yield_plus2in=_r(2 * slope, 1),
            price_usd_per_unit=_r(usd_lb, 5),
            price_basis=(f"grazing value: county pasture cash rent ${rent:.2f}/acre (farms.yaml {farm_id}) "
                         f"/ {prod:.0f} lb normal-year production = $/lb") if prod else "",
            usd_per_acre_per_inch=_r(slope * usd_lb, 3),
            valid_range_note=(f"ESD {esd} ({name}, MLRA {mlra}) low/RV/high = {lo}/{rv}/{hi} lb/ac; "
                              f"favorable/unfavorable years = wettest/driest 10% (Sala et al. 1988 p.42); "
                              f"farm-grid driest/wettest-decile annual precip {c['dry_decile_mean']:.1f}/"
                              f"{c['wet_decile_mean']:.1f} in (NCEI 1951-2025). Linear between the deciles; "
                              f"attributes the whole gap to rain, so an upper-end slope"),
            model_type="ESD favorable-minus-unfavorable range / decile precipitation range (DERIVED)",
            source_short=f"NRCS ESD {esd} reference community 1.1 production table; Sala et al. 1988",
            source_url=url, verification="DERIVED (ESD numbers CONFIRMED in EDIT; precipitation COMPUTED)",
            rain_elasticity=_r(elast, 3)))
    return rows, pd.DataFrame(aux)


def grasscast_rows(clim: pd.DataFrame, values: dict) -> tuple[list[dict], dict]:
    """Grass-Cast county ANPP regressions on season and PRF-interval precipitation."""
    rows, detail = [], {}
    gids = farm_grid_ids()
    for site, cty in COUNTIES.items():
        if not cty["gc"]:
            continue
        g = grasscast_county(cty["fips"], cty["gc"])
        P = grid_monthly(gids[site])
        season = cty["season"]
        slabel = SEASON_LABEL[season]
        p_season = window_sum(P, season)
        rent, prod, farm_id = values.get(site, (np.nan, np.nan, ""))
        usd_lb = rent / prod if prod else np.nan
        res = {}
        # (a) Grass-Cast's own county-mean Apr-Jul precipitation (GP only)
        if cty["gc"] == "GP":
            res["gc_amjj"] = fit_yield_on_rain(g["anpp"], g["ppt_amjj_in"], trend=False, quad=True)
        # (b) NCEI farm-grid season precipitation, linear and quadratic
        res["season_lin"] = fit_yield_on_rain(g["anpp"], p_season, trend=False)
        res["season_quad"] = fit_yield_on_rain(g["anpp"], p_season, trend=False, quad=True)
        res["annual"] = fit_yield_on_rain(g["anpp"], P.sum(axis=1, min_count=12), trend=False)
        # (c) each PRF interval separately (which intervals matter)
        ints = {}
        for name, (a, b) in INTERVAL_MONTHS.items():
            ints[name] = fit_yield_on_rain(g["anpp"], window_sum(P, (a, b)), trend=False)
        res["intervals"] = ints
        # (d) log-log elasticity w.r.t. season rain
        df = pd.concat({"y": np.log(g["anpp"]), "p": np.log(p_season)}, axis=1).dropna()
        df = df[np.isfinite(df["p"])]
        ll = ols(df["y"].values, np.column_stack([np.ones(len(df)), df["p"].values]))
        res["loglog_elasticity"] = ll["beta"][1]
        detail[site] = (g, res)

        domain_note = ("Grass-Cast Great Plains hindcast: ANPP is a function of DayCent-simulated Apr-Aug AET "
                       "calibrated to AVHRR NDVI" if cty["gc"] == "GP" else
                       "Grass-Cast Southwest: Apr-Sep ANPP PREDICTED from DayCent AET (spring part is an exact "
                       "function of simulated Jan-May AET), so this is model sensitivity, weaker evidence")
        base = dict(crop="forage (rangeland/pasture, Grass-Cast ANPP)",
                    region=f"{cty['county']} Co., {cty['st']} ({int(g['cells'].median())} Grass-Cast 10-km cells; "
                           f"rain on farm PRF grid {gids[site]})",
                    yield_units="lb/acre ANPP (Grass-Cast)",
                    model_type="county time series OLS, ANPP on window precipitation (COMPUTED)",
                    source_short="USDA-ARS Grass-Cast historical productivity 1982-2019 (Hartman et al. 2020) + NCEI nClimGrid",
                    source_url=GRASSCAST_URL, verification="COMPUTED")
        price_basis = (f"grazing value: county pasture cash rent ${rent:.2f}/acre (farms.yaml {farm_id}) / "
                       f"{prod:.0f} lb normal-year production = $/lb")
        # season row (quadratic gives curvature and +2 in)
        q, li = res["season_quad"], res["season_lin"]
        pct = 100 * li["slope"] / li["y_mean"]
        rows.append(_row(
            **base, row_key=f"forage_rangeland_{cty['st']}_{cty['county']}_{slabel.replace('-', '')}",
            month_or_window=f"{slabel} total (farm grid)", baseline_precip_in=_r(li["p_mean"]),
            delta_yield_per_inch=_r(li["slope"], 1), delta_yield_pct_per_inch=_r(pct),
            delta_yield_plus2in=_r(q["plus2"], 1), price_usd_per_unit=_r(usd_lb, 5), price_basis=price_basis,
            usd_per_acre_per_inch=_r(li["slope"] * usd_lb, 3),
            valid_range_note=(f"{li['years'][0]}-{li['years'][1]}, n={li['n']}, r={li['r']:.2f}, R2={li['r2']:.2f}, "
                              f"t={li['t']:.1f}; mean ANPP {li['y_mean']:.0f} lb/ac; season rain sd {li['p_sd']:.1f} in. "
                              f"Quadratic: slope at mean {q['slope']:.0f}, exact +1/-1/-2 in = {q['plus1']:.0f}/"
                              f"{q['minus1']:.0f}/{q['minus2']:.0f} lb/ac. Log-log elasticity "
                              f"{res['loglog_elasticity']:.2f}. {domain_note}"),
            rain_elasticity=_r(li["slope"] * li["p_mean"] / li["y_mean"], 3)))
        # annual row
        a = res["annual"]
        rows.append(_row(
            **base, row_key=f"forage_rangeland_{cty['st']}_{cty['county']}_annual",
            month_or_window="annual calendar-year total (farm grid)", baseline_precip_in=_r(a["p_mean"]),
            delta_yield_per_inch=_r(a["slope"], 1), delta_yield_pct_per_inch=_r(100 * a["slope"] / a["y_mean"]),
            delta_yield_plus2in=_r(2 * a["slope"], 1), price_usd_per_unit=_r(usd_lb, 5), price_basis=price_basis,
            usd_per_acre_per_inch=_r(a["slope"] * usd_lb, 3),
            valid_range_note=(f"{a['years'][0]}-{a['years'][1]}, n={a['n']}, r={a['r']:.2f}, R2={a['r2']:.2f}; "
                              f"linear. {domain_note}"),
            rain_elasticity=_r(a["slope"] * a["p_mean"] / a["y_mean"], 3)))
        # key PRF interval row
        k = cty["key_int"]
        ki = ints[k]
        rows.append(_row(
            **base, row_key=f"forage_rangeland_{cty['st']}_{cty['county']}_{k.replace('-', '')}",
            month_or_window=f"PRF interval {k} (farm grid)", baseline_precip_in=_r(ki["p_mean"]),
            delta_yield_per_inch=_r(ki["slope"], 1), delta_yield_pct_per_inch=_r(100 * ki["slope"] / ki["y_mean"]),
            delta_yield_plus2in=_r(2 * ki["slope"], 1), price_usd_per_unit=_r(usd_lb, 5), price_basis=price_basis,
            usd_per_acre_per_inch=_r(ki["slope"] * usd_lb, 3),
            valid_range_note=(f"single-interval regression (other months not held fixed), {ki['years'][0]}-"
                              f"{ki['years'][1]}, r={ki['r']:.2f}, t={ki['t']:.1f}; linear. {domain_note}"),
            rain_elasticity=_r(ki["slope"] * ki["p_mean"] / ki["y_mean"], 3)))
        # Grass-Cast's own Apr-Jul precipitation (cross-check for rain-measurement mismatch)
        if "gc_amjj" in res:
            r_ = res["gc_amjj"]
            rows.append(_row(
                **{**base, "source_short": "USDA-ARS Grass-Cast 1982-2019, ANPP and its own county-mean Apr-Jul precipitation"},
                row_key=f"forage_rangeland_{cty['st']}_{cty['county']}_AprJul_grasscastppt",
                month_or_window="Apr-Jul total (Grass-Cast weather, county mean)", baseline_precip_in=_r(r_["p_mean"]),
                delta_yield_per_inch=_r(r_["slope"], 1), delta_yield_pct_per_inch=_r(100 * r_["slope"] / r_["y_mean"]),
                delta_yield_plus2in=_r(r_["plus2"], 1), price_usd_per_unit=_r(usd_lb, 5), price_basis=price_basis,
                usd_per_acre_per_inch=_r(r_["slope"] * usd_lb, 3),
                valid_range_note=(f"quadratic, slope at mean; n={r_['n']}, r={r_['r']:.2f}, R2={r_['r2']:.2f}; exact +1/-1/-2 in = "
                                  f"{r_['plus1']:.0f}/{r_['minus1']:.0f}/{r_['minus2']:.0f} lb/ac. {domain_note}"),
                rain_elasticity=_r(r_["slope"] * r_["p_mean"] / r_["y_mean"], 3)))
    return rows, detail


def literature_forage_rows() -> list[dict]:
    """Published forage-precipitation relationships, converted to lb/acre per inch."""
    rows = []
    ls_url = "https://mountainscholar.org/bitstream/10217/81174/1/NREL_Lauenroth_EcolApp_2.pdf"
    # Lauenroth & Sala 1992, CPER (Weld Co., CO), 1939-1990. Eq. 2 and 3, p.399; Table 1 means.
    mean_forage_lb = 66 * LB_AC_PER_G_M2
    s_ann = 0.172 * LB_AC_PER_G_M2 * MM_PER_IN
    s_gs = 0.210 * LB_AC_PER_G_M2 * MM_PER_IN
    gs_mean_mm = (66 - 17) / 0.210  # season mean implied by the fit through the means (assumption)
    rows.append(_row(
        row_key="forage_rangeland_CO_CPER_annual_lit", crop="forage (shortgrass steppe, air-dry)",
        region="Central Plains Experimental Range, Weld Co., CO (about 90 mi N of Elbert Co.)",
        month_or_window="annual precipitation", baseline_precip_in=_r(321 / MM_PER_IN),
        delta_yield_per_inch=_r(s_ann, 1), yield_units="lb air-dry forage/acre",
        delta_yield_pct_per_inch=_r(100 * s_ann / mean_forage_lb), delta_yield_plus2in=_r(2 * s_ann, 1),
        valid_range_note=("Forage = 13 + 0.172 x PPT (g/m2, mm), r2=0.39, 1939-1990 (50 yr); mean forage 66 g/m2 "
                          "(589 lb/ac), cv 44%; mean PPT 321 mm, cv 31%; intercept not significant; slopes converted with "
                          "1 g/m2 = 8.92 lb/ac. Lags: poor years followed the 1954 and 1964 droughts despite normal rain"),
        model_type="site time series OLS (published)", source_short="Lauenroth & Sala 1992, Ecol. Appl. 2:397, Eq. 2 p.399, Table 1",
        source_url=ls_url, verification="CONFIRMED (equation and means read in the paper; unit conversion ours)",
        rain_elasticity=_r(0.172 * 321 / 66, 3)))
    rows.append(_row(
        row_key="forage_rangeland_CO_CPER_AprSep_lit", crop="forage (shortgrass steppe, air-dry)",
        region="Central Plains Experimental Range, Weld Co., CO",
        month_or_window="Apr-Sep precipitation", baseline_precip_in=_r(gs_mean_mm / MM_PER_IN),
        delta_yield_per_inch=_r(s_gs, 1), yield_units="lb air-dry forage/acre",
        delta_yield_pct_per_inch=_r(100 * s_gs / mean_forage_lb), delta_yield_plus2in=_r(2 * s_gs, 1),
        valid_range_note=("Forage = 17 + 0.210 x Apr-Sep PPT (g/m2, mm), r2=0.43 (Eq. 3). Baseline Apr-Sep rain "
                          "is implied by the fit through the means (ASSUMPTION, about 233 mm). Events of 15-30 mm "
                          "carry most of the signal (Eq. 4: 0.26 g/m2 per mm in 15-30 mm events vs 0.05 for >30 mm)"),
        model_type="site time series OLS (published)", source_short="Lauenroth & Sala 1992, Eq. 3 p.399",
        source_url=ls_url, verification="CONFIRMED (equation; baseline rain is our inference)",
        rain_elasticity=_r(0.210 * gs_mean_mm / 66, 3)))
    s_sp = 0.6 * LB_AC_PER_G_M2 * MM_PER_IN
    rows.append(_row(
        row_key="forage_rangeland_CentralGrassland_spatial_lit", crop="forage (ANPP, all grassland types)",
        region="Central Grassland region, 100 MLRAs (9,498 SCS sites)", month_or_window="mean annual precipitation (SPATIAL)",
        baseline_precip_in="", delta_yield_per_inch=_r(s_sp, 1), yield_units="lb/acre ANPP (air-dry)",
        valid_range_note=("ANPP = -34 + 0.6 x MAP (g/m2, mm), r2=0.90, across places (200-1,200 mm), NOT across years. "
                          "Lauenroth & Sala 1992 show the year-to-year slope at one site is far flatter (0.13 vs 0.60). "
                          "Do not use for insurance; shown to explain the space-for-time trap"),
        model_type="spatial cross-section (published)", source_short="Sala et al. 1988, Ecology 69:40, Fig. 2 p.42",
        source_url="https://mountainscholar.org/bitstream/10217/81175/1/NREL_Sala_Ecol_69.pdf",
        verification="CONFIRMED", rain_elasticity=""))
    yu_url = "https://doi.org/10.22004/ag.econ.281319"
    for m, b, se in (("May", 125.9, 29.6), ("June", 60.4, 11.1), ("July", 80.0, 21.4), ("March", 101.9, 59.3)):
        rows.append(_row(
            row_key=f"forage_rangeland_KSNE_{m[:3]}_lit", crop="forage (mixed-grass range, clipped)",
            region="Hays KS + 2 Nebraska Sandhills ranches", month_or_window=m,
            delta_yield_per_inch=_r(b, 1), yield_units="lb/acre (units as reported; we read them as lb/ac)",
            delta_yield_plus2in=_r(2 * b, 1),
            valid_range_note=(f"post-elastic-net OLS, ranch-level data, robust SE {se}; R2=0.905, n=42 ranch-years "
                              "(1999-2016 era); previous fall/winter rain had little effect (footnote 12)"),
            model_type="multi-site panel OLS on monthly precipitation (published)",
            source_short="Yu, Vandeveer, Volesky & Harmoney 2019, JARE 44:179, Table 3", source_url=yu_url,
            verification="CONFIRMED (coefficients read in Table 3; yield units not restated in the extracted text)"))
    rows.append(_row(
        row_key="forage_rangeland_KSNE_MayJun_index_lit", crop="forage (mixed-grass range, clipped)",
        region="Hays KS + 2 Nebraska Sandhills ranches", month_or_window="PRF May-Jun index (per index point)",
        delta_yield_per_inch=7.35, yield_units="lb/acre per PRF index point (not per inch)",
        valid_range_note=("Table 4: May-Jun index 7.35 (SE 1.95) lb/ac per point; Jun-Jul -0.12; Jul-Aug 3.06; R2=0.778. "
                          "False-negative probability 21% (rain model) vs 26% (PRF index model), Table 5"),
        model_type="post-elastic-net OLS on PRF interval indices (published)",
        source_short="Yu et al. 2019, JARE 44:179, Tables 4-5", source_url=yu_url, verification="CONFIRMED"))
    return rows


# =============================================================================================
# 5. Hay rows (NASS)
# =============================================================================================
HAY_WINDOWS = {"Apr-Jun": (4, 5, 6), "Apr-Jul": (4, 5, 6, 7), "May-Aug": (5, 6, 7, 8),
               "Apr-Sep": (4, 5, 6, 7, 8, 9), "Mar-May": (3, 4, 5), "Mar-Jun": (3, 4, 5, 6)}
HAY_PRIMARY = {"TX": "Apr-Jun", "OK": "Apr-Jun", "MO": "Apr-Jun", "FL": "Mar-May"}
HAY_SPECIES = {"TX": "bermudagrass and other warm-season hay", "OK": "bermudagrass/native/OWB hay",
               "MO": "tall fescue and mixed cool-season hay", "FL": "bahiagrass/bermudagrass/limpograss hay"}


def hay_state_rows() -> tuple[list[dict], pd.DataFrame]:
    """State 'other hay' yield on trend + window precipitation, 1975-2025."""
    rows, aux = [], []
    for st in ("TX", "OK", "MO", "FL"):
        y = nass_state_yield(HAY_ITEM, st, "nass_hay_other_yield_state")
        y = y[(y.index >= 1975) & (y.index <= 2025)]
        P = noaa_state_monthly(st)
        for wname, months in HAY_WINDOWS.items():
            r = fit_yield_on_rain(y, window_sum(P, months), trend=True)
            rq = fit_yield_on_rain(y, window_sum(P, months), trend=True, quad=True)
            aux.append({"state": st, "window": wname, "slope_t_per_in": r["slope"], "t": r["t"], "r2": r["r2"],
                        "pct_per_in": 100 * r["slope"] / r["y_ref"], "p_mean": r["p_mean"],
                        "elasticity": r["slope"] * r["p_mean"] / r["y_ref"], "n": r["n"],
                        "quad_plus1": rq["plus1"], "quad_minus1": rq["minus1"], "quad_minus2": rq["minus2"],
                        "trend_yield_last": r["y_ref"]})
            if wname != HAY_PRIMARY[st] and not (st in ("TX", "OK") and wname == "Apr-Sep"):
                continue
            price = HAY_PRICE_2025[st]
            pct = 100 * r["slope"] / r["y_ref"]
            rows.append(_row(
                row_key=f"hay_other_{st}_state_{wname.replace('-', '')}", crop=f"hay, other (excl. alfalfa): {HAY_SPECIES[st]}",
                region=f"{STATE_NAMES[st].title()} statewide", month_or_window=f"{wname} statewide total",
                baseline_precip_in=_r(r["p_mean"]), delta_yield_per_inch=_r(r["slope"], 3), yield_units="tons/acre",
                delta_yield_pct_per_inch=_r(pct), delta_yield_plus2in=_r(rq["plus2"], 3),
                price_usd_per_unit=price, price_basis=HAY_PRICE_BASIS, usd_per_acre_per_inch=_r(r["slope"] * price),
                valid_range_note=(f"{r['years'][0]}-{r['years'][1]}, n={r['n']}, t={r['t']:.1f}, R2={r['r2']:.2f} (with trend); "
                                  f"% is of the fitted {r['years'][1]} trend yield {r['y_ref']:.2f} t/ac at mean rain; "
                                  f"quadratic exact +1/-1/-2 in = {rq['plus1']:+.3f}/{rq['minus1']:+.3f}/{rq['minus2']:+.3f} t/ac. "
                                  "Statewide yields mix irrigated, fertilized and unfertilized fields, so slopes are diluted"),
                model_type="state time series OLS: yield on linear trend + window precipitation (COMPUTED)",
                source_short="NASS Quick Stats HAY (EXCL ALFALFA) yield; NOAA nClimDiv statewide precipitation",
                source_url=f"{NASS_QS} ; {NOAA_CAG}", verification="COMPUTED",
                rain_elasticity=_r(r["slope"] * r["p_mean"] / r["y_ref"], 3)))
    aux = pd.DataFrame(aux)
    aux.to_csv(DERIVED / "r2_hay_state_windows.csv", index=False)
    return rows, aux


def hay_county_rows() -> tuple[list[dict], dict]:
    """County 'other hay' yields (Grady OK, Parker TX) on farm-grid window precipitation."""
    rows, detail = [], {}
    gids = farm_grid_ids()
    for site, st, county, wname in (("OKC", "OK", "Grady", "Apr-Jun"), ("DFW", "TX", "Parker", "Apr-Jun")):
        y = nass_county_hay(st, county)
        P = grid_monthly(gids[site])
        r = fit_yield_on_rain(y, window_sum(P, HAY_WINDOWS[wname]), trend=True)
        rq = fit_yield_on_rain(y, window_sum(P, HAY_WINDOWS[wname]), trend=True, quad=True)
        ints = {name: fit_yield_on_rain(y, window_sum(P, mm), trend=True) for name, mm in INTERVAL_MONTHS.items()}
        detail[site] = (y, r, ints)
        price = HAY_PRICE_2025[st]
        rows.append(_row(
            row_key=f"hay_other_{st}_{county}_{wname.replace('-', '')}", crop="hay, other (excl. alfalfa)",
            region=f"{county} Co., {st} (rain on farm PRF grid {gids[site]})", month_or_window=f"{wname} total (farm grid)",
            baseline_precip_in=_r(r["p_mean"]), delta_yield_per_inch=_r(r["slope"], 3), yield_units="tons/acre",
            delta_yield_pct_per_inch=_r(100 * r["slope"] / r["y_ref"]), delta_yield_plus2in=_r(rq["plus2"], 3),
            price_usd_per_unit=price, price_basis=HAY_PRICE_BASIS, usd_per_acre_per_inch=_r(r["slope"] * price),
            valid_range_note=(f"{r['years'][0]}-{r['years'][1]}, n={r['n']}, t={r['t']:.1f}, R2={r['r2']:.2f}; % of fitted "
                              f"{r['years'][1]} trend yield {r['y_ref']:.2f} t/ac; quadratic exact +1/-1/-2 in = "
                              f"{rq['plus1']:+.3f}/{rq['minus1']:+.3f}/{rq['minus2']:+.3f}"
                              + ("; SHORT RECORD (NASS stopped Texas county hay estimates), low confidence" if st == "TX" else "")),
            model_type="county time series OLS: yield on linear trend + window precipitation (COMPUTED)",
            source_short="NASS Quick Stats county HAY (EXCL ALFALFA) yield; NCEI nClimGrid on PRF grid",
            source_url=NASS_QS, verification="COMPUTED",
            rain_elasticity=_r(r["slope"] * r["p_mean"] / r["y_ref"], 3)))
    return rows, detail


def literature_hay_rows() -> list[dict]:
    """Water-use rules of thumb for bermudagrass and alfalfa (per inch of water, not rain)."""
    rows = []
    osu = ("https://extension.okstate.edu/announcements/west-district-ag-insights-newsletter/2026/"
           "ag-insights-august-2026")
    for lab, inches_per_ton in (("low N", 17.6), ("adequate N", 3.9)):
        lb = 2000 / inches_per_ton
        rows.append(_row(
            row_key=f"hay_bermuda_TXOK_wateruse_{lab.replace(' ', '')}", crop="hay, bermudagrass",
            region="Texas A&M research as summarized by OSU Extension (West District)", month_or_window="per inch of water used",
            delta_yield_per_inch=_r(lb, 0), yield_units="lb hay/acre per inch of water",
            delta_yield_plus2in=_r(2 * lb, 0), price_usd_per_unit=HAY_PRICE_2025["TX"] / 2000,
            price_basis=HAY_PRICE_BASIS + " (TX, converted to $/lb)", usd_per_acre_per_inch=_r(lb * HAY_PRICE_2025["TX"] / 2000),
            valid_range_note=(f"{inches_per_ton} inches of water per ton of forage ({lab}); per inch of WATER USED, "
                              "not per inch of rain; multiply by a rain-to-ET efficiency (about 0.5-0.8 in season)"),
            model_type="water-use efficiency rule of thumb (secondary summary)",
            source_short="OSU Extension West District Ag Insights, Aug 2026 (citing Texas A&M)", source_url=osu,
            verification="CONFIRMED in the extension newsletter; original Texas A&M study not seen"))
    rows.append(_row(
        row_key="hay_alfalfa_CA_ET_lit", crop="hay, alfalfa (irrigated)", region="San Joaquin Valley, CA",
        month_or_window="per inch of seasonal ET", delta_yield_per_inch=0.2, yield_units="tons/acre per inch ET",
        delta_yield_plus2in=0.4, price_usd_per_unit=ALFALFA_PRICE_US_2025,
        price_basis=ALFALFA_PRICE_BASIS,
        usd_per_acre_per_inch=_r(0.2 * ALFALFA_PRICE_US_2025),
        valid_range_note="yield (t/ac) = 0.2 x ET (in) - 0.6; about 5 in of ET per ton; per inch of ET, not rain",
        model_type="water production function (field observation)",
        source_short="Sanden, Klonsky, Putnam, Schwankl & Bali 2011, Western Alfalfa & Forage Symposium, Fig. 2b",
        source_url="https://alfalfasymposium.ucdavis.edu/+symposium/2011/files/talks/11WAS-19_Sanden_CostsEfficiencies.pdf",
        verification="CONFIRMED"))
    s = 0.12 * CM_PER_IN * SHORT_TON_AC_PER_T_HA
    rows.append(_row(
        row_key="hay_alfalfa_NM_ET_lit", crop="hay, alfalfa (irrigated)", region="New Mexico",
        month_or_window="per inch of seasonal ET", delta_yield_per_inch=_r(s, 3), yield_units="tons/acre per inch ET",
        delta_yield_plus2in=_r(2 * s, 3), price_usd_per_unit=ALFALFA_PRICE_US_2025,
        price_basis=ALFALFA_PRICE_BASIS, usd_per_acre_per_inch=_r(s * ALFALFA_PRICE_US_2025),
        valid_range_note="y = 0.14 + 0.12 ET (t/ha, cm), R2 = 0.78 (Sammis 1981, Agron. J. 73:323); converted to short tons/acre per inch",
        model_type="water production function (published)", source_short="NMSU Irrigation Management, alfalfa WPF (Sammis 1981)",
        source_url="https://irrigationmanagement.nmsu.edu/crop/alfalfa.html",
        verification="CONFIRMED on the NMSU page; Sammis (1981) original not opened"))
    return rows


# =============================================================================================
# 6. Row crops (water production functions; per inch of ET vs per inch of rain)
# =============================================================================================
RAIN_EFF = 0.7       # central fraction of an extra inch of growing-season rain that becomes crop ET
RAIN_EFF_RANGE = (0.55, 0.85)
STONE06 = "https://www.irrigationtoolbox.com/ReferenceDocuments/TechnicalPapers/CPIA/2006/Stone06.pdf"
L934 = "https://bookstore.ksre.ksu.edu/pubs/agricultural-crop-water-use_L934.pdf"
MOBERLY = "https://opensiuc.lib.siu.edu/jcwre/vol162/iss1/6"


def crop_rows() -> list[dict]:
    """WPF slopes (per inch ET) and implied per-inch-of-rain slopes for wheat, sorghum, cotton,
    corn, soybean; dryland cotton rain regression; rice."""
    rows = []
    # Baseline yields for % (NASS state 2021-2025 means, pulled below)
    ks_wheat = nass_state_yield("WHEAT, WINTER - YIELD, MEASURED IN BU / ACRE", "KS", "nass_wheat_winter_yield")
    ks_sorg = nass_state_yield("SORGHUM, GRAIN - YIELD, MEASURED IN BU / ACRE", "KS", "nass_sorghum_yield")
    ks_corn = nass_state_yield("CORN, GRAIN - YIELD, MEASURED IN BU / ACRE", "KS", "nass_corn_yield")
    ks_soy = nass_state_yield("SOYBEANS - YIELD, MEASURED IN BU / ACRE", "KS", "nass_soy_yield")
    base = {"wheat": ks_wheat.loc[2021:2025].mean(), "sorghum": ks_sorg.loc[2021:2025].mean(),
            "corn": ks_corn.loc[2021:2025].mean(), "soybeans": ks_soy.loc[2021:2025].mean()}
    pd.Series(base).to_csv(DERIVED / "r2_ks_yields_2021_2025.csv")
    wpf = [  # crop, long-term slope bu/in ET, good-year slope, threshold in, max ET in
        ("wheat", "winter wheat", 4.6, 6.0, 10.0, 24),
        ("sorghum", "grain sorghum", 9.4, 12.2, 6.9, 21),
        ("corn", "corn", 13.3, 16.9, 10.9, 25),
        ("soybeans", "soybean", 3.8, 4.6, 7.8, 24),
    ]
    for crop, label, lt, good, thr, mx in wpf:
        price, unit, page = CROP_PRICES[crop]
        y0 = base[crop]
        common = dict(region="Kansas / Central High Plains (K-State water budget)", yield_units="bu/acre",
                      price_usd_per_unit=price, price_basis=f"{WASDE_BASIS}, {page}",
                      source_short="Stone & Schlegel 2006 CPIA Proc. Table 1 p.174; K-State L934 Table 4",
                      source_url=f"{STONE06} ; {L934}")
        rows.append(_row(
            **common, row_key=f"{crop}_KS_WPF_perET", crop=f"{label} (dryland)",
            month_or_window="per inch of seasonal crop ET above threshold",
            delta_yield_per_inch=lt, delta_yield_pct_per_inch=_r(100 * lt / y0), delta_yield_plus2in=2 * lt,
            usd_per_acre_per_inch=_r(lt * price),
            valid_range_note=(f"linear from {thr} in ET (zero yield) to about {mx} in (max ET); long-term slope {lt}, "
                              f"good-year slope {good} bu/ac per in; % is of the 2021-2025 Kansas mean yield {y0:.1f} bu/ac; "
                              "PER INCH OF ET, NOT RAIN"),
            model_type="water production function, linear above threshold (published)", verification="CONFIRMED"))
        rain = lt * RAIN_EFF
        rows.append(_row(
            **common, row_key=f"{crop}_KS_WPF_perRain", crop=f"{label} (dryland)",
            month_or_window="per inch of growing-season rain (WPF x rain efficiency)",
            delta_yield_per_inch=_r(rain, 2), delta_yield_pct_per_inch=_r(100 * rain / y0),
            delta_yield_plus2in=_r(2 * rain, 2), usd_per_acre_per_inch=_r(rain * price),
            valid_range_note=(f"= {lt} bu per in ET x {RAIN_EFF} (in-season rain that becomes ET; range "
                              f"{RAIN_EFF_RANGE[0]}-{RAIN_EFF_RANGE[1]} -> {lt*RAIN_EFF_RANGE[0]:.1f}-{lt*RAIN_EFF_RANGE[1]:.1f}). "
                              "Only once the ET threshold is met; fallow/off-season rain is worth 0.2-0.35 of this"),
            model_type="DERIVED: WPF slope x rainfall-efficiency factor", verification="DERIVED (inputs CONFIRMED)",
            rain_elasticity=""))
    # Direct rain/water-supply regressions at Tribune, KS (Stone & Schlegel 2006, Figs. 2-3)
    for crop, label, b, a, n, r2, x0 in (("wheat", "winter wheat", 3.78, -27.3, 253, 0.64, 7.2),
                                       ("sorghum", "grain sorghum", 6.70, -35.9, 142, 0.60, 5.4)):
        price, unit, page = CROP_PRICES[crop]
        rows.append(_row(
            row_key=f"{crop}_KS_Tribune_watersupply", crop=f"{label} (dryland)", region="Tribune, KS (SW Kansas)",
            month_or_window="per inch of water supply (soil water at emergence + in-season rain)",
            delta_yield_per_inch=b, yield_units="bu/acre", delta_yield_pct_per_inch=_r(100 * b / base[crop]),
            delta_yield_plus2in=2 * b, price_usd_per_unit=price, price_basis=f"{WASDE_BASIS}, {page}",
            usd_per_acre_per_inch=_r(b * price),
            valid_range_note=(f"Y = {a} + {b} x WS (bu/ac, in), n={n}, r2={r2}; zero yield below {x0} in; "
                              f"% of 2021-2025 Kansas mean {base[crop]:.1f} bu/ac"),
            model_type="experiment-station regression on water supply (published)",
            source_short=f"Stone & Schlegel 2006 CPIA Proc., Fig. {'3' if crop == 'wheat' else '2'}",
            source_url=STONE06, verification="CONFIRMED"))
    # Wheat timing: Oklahoma and Kansas
    rows.append(_row(
        row_key="wheat_OK_timing_lit", crop="winter wheat", region="Oklahoma statewide, 1941-1970",
        month_or_window="Oct-Nov and March (+); May and June (-)", yield_units="standardized coefficients",
        valid_range_note=("standardized regression coefficients: Oct-Nov rain +0.34, March +0.36, May -0.31, June -0.50; "
                          "R2 = 0.73; not per inch. Rain at harvest hurts"),
        model_type="state time series regression (published)", source_short="Greene, Sutherland & Kirkham 1979, Climatic Change 2:21, Table I",
        source_url="(no URL found; read in the copy reproduced in M.B. Kirkham, OWRRI project completion report, Oklahoma State Univ., 1980, saved in data/raw/r2_rain_yield/wpf/)",
        verification="CONFIRMED (Table I as reproduced in the OWRRI report)"))
    # Cotton
    price = CROP_PRICES["cotton"][0]
    lint = 57.6
    rows.append(_row(
        row_key="cotton_TX_Bushland_WPF_perET", crop="cotton, upland (lint)", region="Bushland, TX (lysimeters, 2000-2001)",
        month_or_window="per inch of seasonal ET", delta_yield_per_inch=lint, yield_units="lb lint/acre",
        delta_yield_pct_per_inch=_r(100 * lint / 342), delta_yield_plus2in=2 * lint, price_usd_per_unit=price,
        price_basis=f"{WASDE_BASIS}, {CROP_PRICES['cotton'][2]}", usd_per_acre_per_inch=_r(lint * price),
        valid_range_note=("our linear fit to Howell et al. 2002 Table 4 (n=6): threshold about 8.7 in ET, valid 15-31 in ET "
                          "(325-1,338 lb lint); % is of 342 lb/ac, the median dryland lint yield in NASS District 12 (Southern "
                          "High Plains) 2012-2016 (Mauget et al. 2020); PER INCH OF ET"),
        model_type="water production function (fit by R2 to published table)",
        source_short="Howell, Evett, Tolk & Schneider 2002, USCID/EWRI, Table 4 p.332",
        source_url="https://mountainscholar.org/bitstream/10217/206909/1/121_2002-USCID_Howell.pdf",
        verification="DERIVED (table CONFIRMED; fit ours)"))
    # Dryland cotton, TAWC fields: Y = -1826.25 + 282.26 R - 7.5246 R^2
    b1, b2, c0 = 282.26, -7.5246, -1826.25
    for R0 in (10.0, 13.0):
        slope = b1 + 2 * b2 * R0
        ylev = c0 + b1 * R0 + b2 * R0 ** 2
        plus2 = b1 * 2 + b2 * ((R0 + 2) ** 2 - R0 ** 2)
        rows.append(_row(
            row_key=f"cotton_TX_SHP_dryland_rain_{int(R0)}in", crop="cotton, upland (lint), dryland",
            region="Southern High Plains, TX (TAWC producer fields, Floyd/Hale Cos.)",
            month_or_window=f"growing-season rain, evaluated at {R0:.0f} in", baseline_precip_in=R0,
            delta_yield_per_inch=_r(slope, 0), yield_units="lb lint/acre", delta_yield_pct_per_inch=_r(100 * slope / ylev),
            delta_yield_plus2in=_r(plus2, 0), price_usd_per_unit=price, price_basis=f"{WASDE_BASIS}, p.17",
            usd_per_acre_per_inch=_r(slope * price),
            valid_range_note=(f"Y = -1826.25 + 282.26 R - 7.5246 R^2 (lb/ac, in), R2=0.68, n=11 field-years 2005-2016 plus a forced "
                              f"(0,0) point; zero yield below about 8.3 in; predicted yield at {R0:.0f} in = {ylev:.0f} lb; "
                              "marginal value falls fast as rain rises (132 lb at 10 in, 57 lb at 15 in)"),
            model_type="field regression on seasonal rain, quadratic (published)",
            source_short="Black, Johnson & McCallister 2018, Beltwide Cotton Conf., Table 5",
            source_url="https://www.cotton.org/beltwide/proceedings/2005-2022/data/conferences/2018/papers/18131.pdf",
            verification="CONFIRMED",
            rain_elasticity=_r(slope * R0 / ylev, 3)))
    # Rice
    rows.append(_row(
        row_key="rice_US_irrigated", crop="rice", region="United States (AR, LA, MS, MO, TX, CA)",
        month_or_window="any month", delta_yield_per_inch=0, yield_units="cwt/acre",
        delta_yield_pct_per_inch=0, delta_yield_plus2in=0, price_usd_per_unit=CROP_PRICES["rice"][0],
        price_basis=f"{WASDE_BASIS}, p.14 (all rice $/cwt)", usd_per_acre_per_inch=0,
        valid_range_note=("100% of 2,279,958 harvested acres irrigated (2022 Census Table 24); US applies 30 in of irrigation water "
                          "per acre (2023 IWMS Table 39). Rain substitutes for pumped water (a cost saving of a few $/ac per inch, "
                          "not computed here); excess rain at planting/harvest is a delay risk, not a yield-per-inch effect"),
        model_type="structural argument (irrigated flooded crop)", source_short="NASS 2022 Census of Agriculture Table 24; NASS 2023 IWMS Table 39; ERS Rice Sector at a Glance",
        source_url="https://www.nass.usda.gov/Publications/AgCensus/2022/", verification="CONFIRMED (via R2 crop-WPF pull)",
        rain_elasticity=0))
    return rows


# =============================================================================================
# 7. Scenario elasticities for the farms in farms.yaml
# =============================================================================================
def weighted_index(idx: pd.DataFrame, alloc: dict) -> pd.Series:
    """W = sum_i alloc_i x index_i (100 = normal), as in scripts/run_scenarios.py."""
    w = sum(float(a) * idx[name] for name, a in alloc.items())
    return w.dropna()


def state_weighted_index(st: str, alloc: dict) -> pd.Series:
    """Same W built from statewide precipitation (interval rain / its 1951-2025 mean x 100)."""
    P = noaa_state_monthly(st)
    P = P[(P.index >= 1951) & (P.index <= 2025)]
    out = 0
    for name, a in alloc.items():
        m1, m2 = INTERVAL_MONTHS[name]
        v = P[m1] + P[m2]
        out = out + float(a) * 100 * v / v.mean()
    return out.dropna()


def rel_production_vs_w(y: pd.Series, W: pd.Series, detrend: bool) -> dict:
    """Regress production relative to its mean (or fitted trend) on W/100.

    rel_t = a + beta * W_t/100. beta is the elasticity used by the scenario forage-loss proxy:
    a W shortfall of x% of normal cuts production by about beta*x%."""
    df = pd.concat({"y": y, "w": W / 100}, axis=1).dropna()
    t = df.index.values.astype(float) - df.index.values.mean()
    if detrend:  # yield on trend + W, scaled by the mean trend yield at W = 1
        res = ols(df["y"].values, np.column_stack([np.ones(len(df)), t, df["w"].values]))
        trend_at_w1 = res["beta"][0] + res["beta"][1] * t + res["beta"][2]
        beta = res["beta"][2] / np.mean(trend_at_w1)
        se = res["se"][2] / np.mean(trend_at_w1)
        T = np.column_stack([np.ones(len(df)), t])
        ry = df["y"].values - T @ np.linalg.lstsq(T, df["y"].values, rcond=None)[0]
        rw = df["w"].values - T @ np.linalg.lstsq(T, df["w"].values, rcond=None)[0]
        r = np.corrcoef(ry, rw)[0, 1]
    else:
        res = ols(df["y"].values / df["y"].mean(), np.column_stack([np.ones(len(df)), df["w"].values]))
        beta, se = res["beta"][1], res["se"][1]
        r = np.corrcoef(df["y"], df["w"])[0, 1]
    return {"beta": beta, "se": se, "r2": res["r2"], "n": res["n"],
            "years": (int(df.index.min()), int(df.index.max())), "r": r}


# Typical correlation between annual rain and annual forage at one site, used to turn the
# range-based ESD elasticity (which attributes all year-to-year variation to rain) into a
# regression-style elasticity: Lauenroth & Sala 1992 r = sqrt(0.39) = 0.62 (annual) and
# sqrt(0.43) = 0.66 (Apr-Sep); in Elbert Co. CO the Grass-Cast annual-rain elasticity (0.85) is
# 0.64-0.70 of the two ESD-implied elasticities (1.33, 1.22).
ESD_R_ADJ = 0.65

# Which evidence each farm's recommended elasticity uses (see the doc, section "Scenario
# elasticities"): direct yield data first, then ESD x ESD_R_ADJ. Grass-Cast is a cross-check only
# outside Colorado because it understated the 2011 southern-Plains drought several-fold.
SCEN_RULE = {
    "DFW_hay": "state_hay", "DFW_graze": "esd_adj", "SAT_graze": "esd_adj", "OKC_hay": "state_hay",
    "OKC_graze": "esd_adj", "SGF_hay": "state_hay", "SGF_graze": "state_hay", "DEN_graze": "ls_cper",
    "ABQ_graze": "esd_adj", "TPA_graze": "state_hay", "TPA_hay": "state_hay",
}
RULE_TEXT = {
    "state_hay": "statewide other-hay yield vs statewide W (1975-2025)",
    "esd_adj": f"ESD-implied elasticity x {ESD_R_ADJ} (range-to-regression adjustment)",
    "ls_cper": "Lauenroth & Sala 1992 CPER clipped forage, Apr-Sep rain elasticity (50 yr)",
}


def scenario_rows(farms: list[dict], esd_aux: pd.DataFrame, values: dict) -> tuple[list[dict], pd.DataFrame]:
    """One row per farm: recommended elasticity plus every candidate estimate in the note."""
    rows, aux = [], []
    gids = farm_grid_ids()
    ls_aprsep = 0.210 * ((66 - 17) / 0.210) / 66  # Lauenroth & Sala Eq. 3 elasticity at the means
    for f in farms:
        fid, site, use, alloc = f["farm_id"], f["site"], f["intended_use"], f["interval_allocation"]
        cty, st = COUNTIES[site], COUNTIES[site]["st"]
        W = weighted_index(official_index(gids[site]), alloc)
        months = sorted({m for name in alloc for m in INTERVAL_MONTHS[name]})
        P = grid_monthly(gids[site])
        cand, lin_by = {}, {}
        # state hay vs statewide W
        ys = nass_state_yield(HAY_ITEM, st, "nass_hay_other_yield_state")
        ys = ys[(ys.index >= 1975) & (ys.index <= 2025)]
        r_ = rel_production_vs_w(ys, state_weighted_index(st, alloc), detrend=True)
        cand["state_hay"] = r_
        lin_by["state_hay"] = (fit_yield_on_rain(ys, window_sum(noaa_state_monthly(st), months), trend=True),
                               "tons/acre", f"{STATE_NAMES[st].title()} other hay")
        # county hay (Grady only has a long record)
        if site == "OKC":
            yc = nass_county_hay("OK", "Grady")
            cand["county_hay"] = rel_production_vs_w(yc, W, detrend=True)
            lin_by["county_hay"] = (fit_yield_on_rain(yc, window_sum(P, months), trend=True), "tons/acre",
                                    "Grady Co. other hay")
        # Grass-Cast
        if cty["gc"]:
            g = grasscast_county(cty["fips"], cty["gc"])
            cand["grasscast"] = rel_production_vs_w(g["anpp"], W, detrend=False)
            lin_by["grasscast"] = (fit_yield_on_rain(g["anpp"], window_sum(P, months), trend=False),
                                   "lb/acre ANPP", "Grass-Cast ANPP")
        # ESD
        e = esd_aux[esd_aux["esd"] == ESD_PRIMARY[site]].iloc[0]
        cand["esd_raw"] = {"beta": e["elasticity"]}
        cand["esd_adj"] = {"beta": e["elasticity"] * ESD_R_ADJ}
        if site == "DEN":
            cand["ls_cper"] = {"beta": ls_aprsep}
        rule = SCEN_RULE.get(fid, "esd_adj")
        beta = cand[rule]["beta"]
        # per-inch numbers: from the matching linear fit when there is one, else from the ESD
        if rule in lin_by:
            lin, units, lab = lin_by[rule]
            ymean = lin["y_ref"] if "hay" in rule else lin["y_mean"]
            slope, pct, base_p = lin["slope"], 100 * lin["slope"] / ymean, lin["p_mean"]
            per_inch_note = f"per inch of total rain in the insured months ({lab}, {lin['years'][0]}-{lin['years'][1]})"
        elif rule == "ls_cper":  # Lauenroth & Sala 1992 Eq. 3 (Apr-Sep), converted to lb/acre per inch
            slope = 0.210 * LB_AC_PER_G_M2 * MM_PER_IN
            pct, base_p = 100 * slope / (66 * LB_AC_PER_G_M2), ((66 - 17) / 0.210) / MM_PER_IN
            units = "lb air-dry forage/acre (CPER, Lauenroth & Sala 1992)"
            per_inch_note = "per inch of Apr-Sep rain at the CPER (Lauenroth & Sala 1992 Eq. 3)"
        else:
            slope, pct, base_p = (e["slope_lb_per_in"] * ESD_R_ADJ, e["pct_per_in"] * ESD_R_ADJ,
                                  e["p_annual_mean"])
            units = f"lb air-dry forage/acre (ESD x {ESD_R_ADJ})"
            per_inch_note = f"per inch of annual rain (ESD-implied slope x {ESD_R_ADJ})"
        value = float(f["expected_value_usd_per_acre"])
        prod = float(f["expected_production"]["value"])
        cand_txt = "; ".join(
            f"{k}={v['beta']:.2f}" + (f" (SE {v['se']:.2f}, r={v['r']:.2f}, n={v['n']})" if "se" in v else "")
            for k, v in cand.items())
        rec = {"farm_id": fid, "recommended": beta, "rule": rule}
        rec.update({f"cand_{k}": v["beta"] for k, v in cand.items()})
        aux.append(rec)
        is_hay = use == "haying"
        rows.append(_row(
            row_key=f"scen_{fid}", crop=("hay" if is_hay else "forage (grazing)"),
            region=f"{cty['county']} Co., {st} (farm PRF grid {gids[site]})",
            month_or_window="farm's insured PRF intervals: " + ", ".join(f"{k} {v:.0%}" for k, v in alloc.items()),
            baseline_precip_in=_r(base_p), delta_yield_per_inch=_r(slope, 3 if "tons" in units else 1),
            yield_units=units, delta_yield_pct_per_inch=_r(pct),
            delta_yield_plus2in=_r(2 * slope, 3 if "tons" in units else 1),
            price_usd_per_unit=_r(value / prod, 2 if is_hay else 5),
            price_basis=(f"farms.yaml expected_value_usd_per_acre ${value:.2f} / expected_production {prod} "
                         f"{f['expected_production']['units']}"),
            usd_per_acre_per_inch=_r(pct / 100 * value, 3),
            valid_range_note=(f"rain_elasticity = fractional production change per unit fractional change in the "
                              f"farm's weighted PRF index W/100 (run_scenarios.py: forage_loss = value x max(0, 1 - W/100) "
                              f"x elasticity). RECOMMENDED = {beta:.2f} from {RULE_TEXT[rule]}. All candidates: {cand_txt}. "
                              f"delta_yield_per_inch is {per_inch_note}"),
            model_type="scenario elasticity (relative production regressed on W/100, or ESD/literature)",
            source_short=RULE_TEXT[rule],
            source_url=(f"{NASS_QS} ; {NOAA_CAG}" if rule == "state_hay" else
                        "https://mountainscholar.org/bitstream/10217/81174/1/NREL_Lauenroth_EcolApp_2.pdf"
                        if rule == "ls_cper" else
                        (ESD_URL_FL if site == "TPA" else
                         f"{EDIT_BASE}/{[x for x in ESDS if x[1] == ESD_PRIMARY[site]][0][2]}/{ESD_PRIMARY[site]}")),
            verification=("COMPUTED" if rule == "state_hay" else "DERIVED"), rain_elasticity=_r(beta, 3)))
    return rows, pd.DataFrame(aux)


# =============================================================================================
# 8. Figures
# =============================================================================================
INK, INK2, GRID = "#0b0b0b", "#52514e", "#d9d8d4"
C1, C2, C3, C4 = "#2a78d6", "#eb6834", "#1baf7a", "#8a5cc2"


def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 9, "axes.edgecolor": INK2, "axes.labelcolor": INK, "xtick.color": INK2,
                         "ytick.color": INK2, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
                         "axes.spines.top": False, "axes.spines.right": False})
    return plt


def fig_grasscast(detail: dict, path: Path) -> None:
    plt = _plt()
    sites = [s for s in ("DEN", "ABQ", "OKC", "DFW") if s in detail]
    fig, axes = plt.subplots(1, len(sites), figsize=(3.1 * len(sites), 3.2))
    gids = farm_grid_ids()
    for ax, site in zip(np.atleast_1d(axes), sites):
        g, res = detail[site]
        cty = COUNTIES[site]
        p = window_sum(grid_monthly(gids[site]), cty["season"]).reindex(g.index)
        ax.scatter(p, g["anpp"], s=16, color=C1, edgecolor="white", linewidth=0.4, zorder=3)
        q = res["season_quad"]
        xs = np.linspace(p.min(), p.max(), 50)
        li = res["season_lin"]
        a0 = li["y_mean"] - li["slope"] * li["p_mean"]
        ax.plot(xs, a0 + li["slope"] * xs, color=INK, lw=1.2, label=f"{li['slope']:.0f} lb/ac per in")
        ax.set_title(f"{cty['county']} Co., {cty['st']}", fontsize=9)
        ax.set_xlabel(f"{SEASON_LABEL[cty['season']]} rain on farm grid (in)")
        ax.legend(frameon=False, fontsize=8, loc="upper left")
        ax.text(0.98, 0.04, f"r = {li['r']:.2f}\n{100*li['slope']/li['y_mean']:.1f}% per in",
                transform=ax.transAxes, ha="right", va="bottom", fontsize=8, color=INK2)
    np.atleast_1d(axes)[0].set_ylabel("Grass-Cast ANPP (lb/acre)")
    fig.suptitle("Forage production vs key-season rainfall, 1982-2019 (Grass-Cast county means; NCEI farm-grid rain)",
                 fontsize=9.5)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fig_interval_r(detail: dict, hay_detail: dict, path: Path) -> None:
    plt = _plt()
    series = []
    for site in ("DEN", "ABQ", "OKC", "DFW"):
        if site in detail:
            series.append((f"{COUNTIES[site]['county']} {COUNTIES[site]['st']} forage", detail[site][1]["intervals"]))
    if "OKC" in hay_detail:
        series.append(("Grady OK hay (NASS)", hay_detail["OKC"][2]))
    fig, ax = plt.subplots(figsize=(8.6, 3.6))
    x = np.arange(len(INTERVAL_NAMES))
    wdt = 0.8 / len(series)
    colors = [C1, C2, C3, C4, INK2]
    hatches = ["", "///", "...", "xx", "\\\\"]
    for i, (lab, ints) in enumerate(series):
        vals = [ints[n]["r"] if n in ints else np.nan for n in INTERVAL_NAMES]
        ax.bar(x - 0.4 + wdt * (i + 0.5), vals, wdt, label=lab, color=colors[i % 5], edgecolor=INK,
               linewidth=0.3, hatch=hatches[i % 5])
    ax.axhline(0, color=INK, lw=0.8)
    ax.set_xticks(x, INTERVAL_NAMES, rotation=0, fontsize=8)
    ax.set_ylabel("correlation with interval rain (r)")
    ax.set_title("Which PRF two-month intervals move forage? Correlation of annual production with each interval's rain",
                 fontsize=9.5)
    ax.legend(frameon=False, fontsize=7.5, ncol=3, loc="upper right")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fig_growth_curves(path: Path) -> None:
    plt = _plt()
    fig, ax = plt.subplots(figsize=(7.6, 3.6))
    styles = ["-", "--", "-.", ":", "-", "--", "-."]
    markers = ["o", "s", "^", "D", "v", "P", "X"]
    shown = {}
    for site, esd, mlra, name, *_vals, curve, pct in ESDS:
        if pct is None or site in shown:
            continue
        shown[site] = (esd, curve, pct)
    for i, (site, (esd, curve, pct)) in enumerate(shown.items()):
        cty = COUNTIES[site]
        ax.plot(range(1, 13), pct, styles[i % 7], marker=markers[i % 7], ms=3.5, lw=1.1, color=[C1, C2, C3, C4, INK2, INK, "#b8860b"][i % 7],
                label=f"{cty['county']} {cty['st']}: {curve.split(' ')[0]}")
    ax.set_xticks(range(1, 13), ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"])
    ax.set_ylabel("% of annual growth in month")
    ax.set_title("When forage grows: NRCS growth curves for the dominant site in each study county", fontsize=9.5)
    ax.legend(frameon=False, fontsize=7.5, ncol=2)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fig_aridity(esd_aux: pd.DataFrame, clim: pd.DataFrame, gc_rows: list[dict], path: Path) -> None:
    plt = _plt()
    fig, ax = plt.subplots(figsize=(5.6, 3.6))
    e = esd_aux.merge(clim[["annual_mean_1951_2025"]], left_on="site", right_index=True)
    ax.scatter(e["annual_mean_1951_2025"], e["pct_per_in"], marker="o", s=26, color=C1, label="ESD-implied (annual rain)")
    for _, r in e.drop_duplicates("site").iterrows():
        ax.annotate(COUNTIES[r["site"]]["county"], (r["annual_mean_1951_2025"], r["pct_per_in"]), fontsize=7,
                    xytext=(3, 3), textcoords="offset points", color=INK2)
    g = [r for r in gc_rows if r["row_key"].endswith("_annual") and r["source_url"] == GRASSCAST_URL]
    ax.scatter([float(r["baseline_precip_in"]) for r in g], [float(r["delta_yield_pct_per_inch"]) for r in g],
               marker="s", s=26, color=C2, label="Grass-Cast regression (annual rain)")
    ax.scatter([321 / MM_PER_IN], [100 * 0.172 * MM_PER_IN / 66], marker="^", s=34, color=C3,
               label="Lauenroth & Sala 1992, CPER clipped forage")
    ax.set_xlabel("mean annual precipitation on farm grid (in)")
    ax.set_ylabel("% change in forage per extra inch")
    ax.set_title("Drier places respond more, in percent, to each inch", fontsize=9.5)
    ax.legend(frameon=False, fontsize=7.5)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


# =============================================================================================
# 9. PRF payout per index point vs forage loss per index point; Grass-Cast validation
# =============================================================================================
def prf_vs_loss_table(farms: list[dict], s_aux: pd.DataFrame) -> pd.DataFrame:
    """Per farm and acre: PRF indemnity per point of W below the trigger vs the forage-loss proxy
    per point of W below 100. PRF: indemnity = CBV x PF x coverage x share x (trigger - index)/trigger
    with trigger = 100 x coverage, so each index point below trigger pays CBV x PF x share / 100."""
    rows = []
    beta = dict(zip(s_aux["farm_id"], s_aux["recommended"]))
    for f in farms:
        cbv, pf, cov = float(f["county_base_value_usd_per_acre"]), float(f["productivity_factor"]), float(f["coverage_level"])
        value = float(f["expected_value_usd_per_acre"])
        b = beta[f["farm_id"]]
        prf_pt = cbv * pf / 100
        loss_pt = value * b / 100
        rec = {"farm_id": f["farm_id"], "use": f["intended_use"], "cbv": cbv, "pf": pf, "coverage": cov,
               "value_usd_ac": value, "elasticity": b, "prf_usd_ac_per_point": prf_pt, "loss_usd_ac_per_point": loss_pt,
               "ratio_prf_to_loss": prf_pt / loss_pt if loss_pt else np.nan,
               "loss_at_W70": value * b * 0.30, "prf_at_W70": cbv * pf * cov * (100 * cov - 70) / (100 * cov)}
        if f["intended_use"] == "grazing":
            # replacement-feed valuation: grazed share of normal production replaced with hay
            st = COUNTIES[f["site"]]["st"]
            lb = float(f["expected_production"]["value"])
            repl = lb * HARVEST_EFFICIENCY * HAY_PRICE_2025[st] / 2000
            rec["replacement_value_usd_ac"] = repl
            rec["loss_pt_replacement"] = repl * b / 100
        rows.append(rec)
    out = pd.DataFrame(rows)
    out.to_csv(DERIVED / "r2_prf_vs_loss_per_point.csv", index=False)
    # Per interval: dollars per INCH of shortfall (what a Kalshi rain ladder must pay per inch),
    # using the PRF expected (normal) interval rain on the farm grid.
    global _IDX
    official_index(farm_grid_ids()["DFW"])  # make sure the index table is loaded
    per_in = []
    for f in farms:
        gid = farm_grid_ids()[f["site"]]
        d = _IDX[(_IDX["grid_id"] == str(gid)) & (_IDX["year"] == 2025)]
        normal_in = dict(zip(d["interval_name"], d["expected_precip_mm"] / MM_PER_IN))
        b = beta[f["farm_id"]]
        cbv, pf = float(f["county_base_value_usd_per_acre"]), float(f["productivity_factor"])
        value = float(f["expected_value_usd_per_acre"])
        repl = None
        if f["intended_use"] == "grazing":
            repl = (float(f["expected_production"]["value"]) * HARVEST_EFFICIENCY
                    * HAY_PRICE_2025[COUNTIES[f["site"]]["st"]] / 2000)
        for name, a in f["interval_allocation"].items():
            n_in = normal_in[name]
            per_in.append({"farm_id": f["farm_id"], "interval": name, "share": float(a), "normal_in": n_in,
                           "inch_per_index_point": n_in / 100,
                           "loss_usd_ac_per_inch_short": value * b * float(a) / n_in,
                           "loss_usd_ac_per_inch_short_replacement": (repl * b * float(a) / n_in) if repl else np.nan,
                           "prf_usd_ac_per_inch_below_trigger": cbv * pf * float(a) / n_in,
                           "trigger_inches": n_in * float(f["coverage_level"])})
    pd.DataFrame(per_in).to_csv(DERIVED / "r2_dollars_per_inch_by_interval.csv", index=False)
    return out


def grasscast_validation() -> pd.DataFrame:
    """Grass-Cast vs drought years and vs Grady Co. NASS hay (detrended)."""
    rows = []
    for site in ("DFW", "OKC", "DEN", "ABQ"):
        c = COUNTIES[site]
        g = grasscast_county(c["fips"], c["gc"])
        rel = g["anpp"] / g["anpp"].mean()
        rows.append({"site": site, "county": c["county"], "anpp_mean": g["anpp"].mean(),
                     "anpp_cv": g["anpp"].std() / g["anpp"].mean(), "rel_2011": rel.get(2011), "rel_2012": rel.get(2012),
                     "rel_2002": rel.get(2002), "min_year": int(rel.idxmin()), "min_rel": rel.min()})
    g = grasscast_county(40051, "GP")
    y = nass_county_hay("OK", "Grady")
    d = pd.concat({"gc": g["anpp"], "hay": y}, axis=1).dropna()
    t = d.index.values.astype(float) - d.index.values.mean()
    T = np.column_stack([np.ones(len(d)), t])
    hd = d["hay"].values - T @ np.linalg.lstsq(T, d["hay"].values, rcond=None)[0]
    tr = T @ np.linalg.lstsq(T, d["hay"].values, rcond=None)[0]
    out = pd.DataFrame(rows)
    out["grady_gc_vs_hay_r"] = np.corrcoef(d["gc"], hd)[0, 1]
    out["grady_hay_rel_2011"] = float(d.loc[2011, "hay"] / tr[list(d.index).index(2011)])
    out["grady_hay_detrended_cv"] = np.std(hd / tr)
    out.to_csv(DERIVED / "r2_grasscast_validation.csv", index=False)
    return out


# =============================================================================================
# 10. Main
# =============================================================================================
def hay_row_price(row_key: str) -> tuple[float, str] | None:
    """Current price and basis for a hay row of the CSV, from its row_key; None for other rows.
    hay_other_<ST>_* -> state other-hay $/ton; hay_bermuda_TXOK_* -> Texas other hay in $/lb;
    hay_alfalfa_* -> US alfalfa $/ton."""
    parts = str(row_key).split("_")
    if row_key.startswith("hay_other_") and len(parts) > 2 and parts[2] in HAY_PRICE_2025:
        return HAY_PRICE_2025[parts[2]], HAY_PRICE_BASIS
    if row_key.startswith("hay_bermuda_TXOK_"):
        return HAY_PRICE_2025["TX"] / 2000, HAY_PRICE_BASIS + " (TX, converted to $/lb)"
    if row_key.startswith("hay_alfalfa_"):
        return ALFALFA_PRICE_US_2025, ALFALFA_PRICE_BASIS
    return None


def reprice_hay_rows(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Re-price the hay rows of crop_rain_sensitivity_other.csv at the current constants without
    re-running the regressions (which need the Grass-Cast workbooks and openpyxl).

    usd_per_acre_per_inch scales with the price: new = old x new_price / old_price, rounded to cents.
    Because 'old' is already rounded to cents, the result can differ from a full rerun by 1 cent
    (e.g. hay_alfalfa_NM_ET_lit: 23.38 here vs 23.39 = 0.13597 t/ac x $172). Rows already at the
    current price and basis are left alone (idempotent).
    Returns the new frame and the row_keys that changed."""
    out = df.copy()
    changed = []
    for i, r in out.iterrows():
        cur = hay_row_price(r["row_key"])
        if cur is None:
            continue
        new_p, basis = cur
        old_p = float(r["price_usd_per_unit"])
        if abs(old_p - new_p) < 1e-12 and r["price_basis"] == basis:
            continue
        out.at[i, "usd_per_acre_per_inch"] = round(float(r["usd_per_acre_per_inch"]) * new_p / old_p, 2)
        out.at[i, "price_usd_per_unit"] = new_p
        out.at[i, "price_basis"] = basis
        changed.append(r["row_key"])
    return out, changed


def main() -> None:
    import sys
    if "--reprice-csv" in sys.argv[1:]:
        old = pd.read_csv(OUT_CSV)
        df, changed = reprice_hay_rows(old)
        # rewrite only the changed lines so untouched rows keep their exact text
        orig = OUT_CSV.read_text(encoding="utf-8").splitlines(keepends=True)
        new = df.to_csv(index=False).splitlines(keepends=True)
        if len(orig) != len(new) or len(orig) != len(df) + 1:
            raise ValueError("CSV has embedded newlines; cannot rewrite line by line")
        keep = set(changed)
        lines = [orig[0]] + [new[i + 1] if df["row_key"].iat[i] in keep else orig[i + 1] for i in range(len(df))]
        OUT_CSV.write_text("".join(lines), encoding="utf-8")
        print(f"re-priced {len(changed)} hay rows in {OUT_CSV.relative_to(ROOT)}: {changed}")
        return
    farms = load_farms()
    values = county_value_basis(farms)
    clim = climatology()
    rows = []
    e_rows, esd_aux = esd_rows(clim, values)
    esd_aux.to_csv(DERIVED / "r2_esd_implied.csv", index=False)
    g_rows, gc_detail = grasscast_rows(clim, values)
    hs_rows, hay_aux = hay_state_rows()
    hc_rows, hay_detail = hay_county_rows()
    s_rows, s_aux = scenario_rows(farms, esd_aux, values)
    rows = (s_rows + g_rows + e_rows + literature_forage_rows() + hc_rows + hs_rows
            + literature_hay_rows() + crop_rows())
    out = pd.DataFrame(rows, columns=CSV_COLUMNS)
    dup = out["row_key"][out["row_key"].duplicated()]
    if len(dup):
        raise ValueError(f"duplicate row_key: {dup.tolist()}")
    out.to_csv(OUT_CSV, index=False)
    # interval detail table for the doc
    det = []
    for site, (g, res) in gc_detail.items():
        for name, r in res["intervals"].items():
            det.append({"series": f"{COUNTIES[site]['county']} forage (Grass-Cast)", "interval": name,
                        "slope_per_in": r["slope"], "pct_per_in": 100 * r["slope"] / r["y_mean"], "r": r["r"], "t": r["t"],
                        "p_mean": r["p_mean"]})
    for site, (y, r0, ints) in hay_detail.items():
        for name, r in ints.items():
            det.append({"series": f"{COUNTIES[site]['county']} hay (NASS)", "interval": name, "slope_per_in": r["slope"],
                        "pct_per_in": 100 * r["slope"] / r["y_ref"], "r": r["r"], "t": r["t"], "p_mean": r["p_mean"]})
    pd.DataFrame(det).to_csv(DERIVED / "r2_interval_regressions.csv", index=False)
    s_aux.to_csv(DERIVED / "r2_scenario_elasticities.csv", index=False)
    print(prf_vs_loss_table(farms, s_aux).round(3).to_string(index=False))
    print(grasscast_validation().round(3).to_string(index=False))
    fig_grasscast(gc_detail, FIGURES / "r2_forage_vs_season_rain.png")
    fig_interval_r(gc_detail, hay_detail, FIGURES / "r2_interval_correlations.png")
    fig_growth_curves(FIGURES / "r2_growth_curves.png")
    fig_aridity(esd_aux, clim, g_rows, FIGURES / "r2_pct_response_vs_aridity.png")
    print(f"wrote {OUT_CSV.relative_to(ROOT)} ({len(out)} rows)")
    print(s_aux.to_string(index=False))


if __name__ == "__main__":
    main()
