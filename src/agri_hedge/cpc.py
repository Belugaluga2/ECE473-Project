"""Gridded precipitation on PRF grids, and the PRF rainfall-index formula.

Two gridded data sources matter for PRF:
* NOAA CPC Unified Gauge-Based Analysis of Daily Precipitation over CONUS (0.25 degree). This was
  PRF's official source through 2026-08-30 (FCIC-18150 handbook, section 33A). Its 0.25-degree
  cells ARE the PRF grids (see agri_hedge.prf_grid). We read it from
  - NOAA PSL's monthly-mean file precip.V1.0.mon.mean.nc (units mm/day; 1948-01 to 2024-05 as of
    2026-10-29; "Monthly Values after 2006 are from the real time files (RT)"), via OPeNDAP, and
  - CPC's own daily binary files (units 0.1 mm/day) from 2019 on: the reprocessed "UPDATED"
    analysis when it exists (2019 onward, lagging ~2 months) and the real-time "RT" analysis
    otherwise.
* NOAA NCEI nClimGrid (1/24 degree, ~5 km). RMA switched PRF to NCEI effective 2026-08-31, and as
  of 2026-10-29 the official Decision Support Tool's historical values equal nClimGrid-Monthly
  precipitation averaged over the 36 nClimGrid cells inside each 0.25-degree PRF grid.

Units: all monthly and interval totals are millimetres (mm) unless the column says _in (inches,
mm / 25.4). PSL monthly means are mm/day, so monthly total (mm) = mean (mm/day) x days in month.

PRF index (FCIC-18150 section 33D): for grid g, interval k and crop year Y,
    final grid index = 100 x interval precipitation(g, k, Y) / expected precipitation(g, k, Y)
where the expected precipitation is the mean interval precipitation over a base period. The
handbook says CPC data "from 1948 to two years prior to the crop year". The DST (2026-10-29)
instead uses 1951 to two years before the crop year for the 2026 crop year, and re-indexes all
past years 1951-2025 against the current (1951-2025) mean. RMA reports the index rounded to 0.1.
"""
from __future__ import annotations

import calendar
from typing import Callable

import numpy as np
import pandas as pd

from agri_hedge.prf_grid import CELL_DEG, LAT_SOUTH, LON_WEST, N_COLS, N_ROWS
from agri_hedge.prf_intervals import INTERVAL_CODES, INTERVAL_MONTHS, INTERVAL_NAMES

MM_PER_INCH = 25.4

# --- Source locations (verified 2026-10-29) ----------------------------------------------------
PSL_MONTHLY_OPENDAP = ("https://psl.noaa.gov/thredds/dodsC/Datasets/cpc_us_precip/"
                       "precip.V1.0.mon.mean.nc")
PSL_MONTHLY_DOWNLOAD = "https://downloads.psl.noaa.gov/Datasets/cpc_us_precip/precip.V1.0.mon.mean.nc"
PSL_DAILY_V10 = "https://downloads.psl.noaa.gov/Datasets/cpc_us_precip/precip.V1.0.{year}.nc"      # 1948-2006
PSL_DAILY_RT = "https://downloads.psl.noaa.gov/Datasets/cpc_us_precip/RT/precip.V1.0.{year}.nc"    # 2007-
CPC_FTP = "https://ftp.cpc.ncep.noaa.gov/precip/CPC_UNI_PRCP/GAUGE_CONUS"
NCLIMGRID_MONTHLY_URL = "https://www.ncei.noaa.gov/data/nclimgrid-monthly/access/nclimgrid_prcp.nc"
NCLIMGRID_DAILY_URL = ("https://www.ncei.noaa.gov/data/nclimgrid-daily/access/grids/{year}/"
                       "ncdd-{year}{month:02d}-grd-scaled.nc")


def days_in_month(year: int, month: int) -> int:
    return calendar.monthrange(int(year), int(month))[1]


def mm_per_day_to_month_total_mm(mm_per_day, year: int, month: int):
    """Convert a monthly-mean rate (mm/day, as in PSL's mon.mean file) to a monthly total (mm)."""
    return mm_per_day * days_in_month(year, month)


# =================================================================================================
# CPC daily binary files (CPC FTP)
# =================================================================================================
def cpc_daily_url(year: int, month: int, day: int, kind: str = "UPDATED") -> str:
    """URL of one CPC CONUS daily analysis file; kind is 'UPDATED' (2019-) or 'RT' (2007-)."""
    ymd = f"{year:04d}{month:02d}{day:02d}"
    return f"{CPC_FTP}/{kind}/{year:04d}/PRCP_CU_GAUGE_V1.0CONUS_0.25deg.lnx.{ymd}.{kind}"


def read_cpc_daily_binary(buf: bytes) -> np.ndarray:
    """Decode a CPC CONUS daily file into a (120, 300) float array of precipitation in mm.

    Format (CPC GAUGE_CONUS README / .ctl): two little-endian float32 fields of 300 x 120, first
    the analysed precipitation in 0.1 mm/day, then the gauge count; undefined = -999. Rows run
    south to north from 20.125 N and columns west to east from 129.875 W, i.e. array[row, col]
    is PRF grid row * 300 + col + 1. Missing cells are NaN.
    """
    a = np.frombuffer(buf, dtype="<f4")
    if a.size < N_ROWS * N_COLS:
        raise ValueError(f"CPC daily buffer too short ({a.size} floats)")
    rain = a[: N_ROWS * N_COLS].reshape(N_ROWS, N_COLS).astype(np.float64)
    rain[rain < -998] = np.nan
    return rain / 10.0


# =================================================================================================
# Aggregating finer grids (nClimGrid, 1/24 degree) to PRF grids
# =================================================================================================
def fine_grid_to_prf(values: np.ndarray, lat: np.ndarray, lon: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Average a fine lat/lon grid (e.g. nClimGrid) onto the 0.25-degree PRF grid.

    values: array (nlat, nlon) with NaN (or masked) for missing; lat, lon: cell-centre vectors.
    Returns (mean, count): two (120, 300) arrays; mean is NaN where no fine cell has data.
    Each fine cell is assigned to the PRF cell that contains its centre; with nClimGrid's
    1/24-degree cells that is exactly 6 x 6 = 36 fine cells per PRF grid. This is the
    aggregation that reproduces RMA's DST values (see docs/analysis/06b_index_validation.md).
    """
    v = np.ma.filled(np.ma.asarray(values, dtype=np.float64), np.nan)
    rows = np.floor((np.asarray(lat, dtype=np.float64) - LAT_SOUTH) / CELL_DEG).astype(int)
    cols = np.floor((np.asarray(lon, dtype=np.float64) - LON_WEST) / CELL_DEG).astype(int)
    rr, cc = np.meshgrid(rows, cols, indexing="ij")
    ok = (np.isfinite(v) & (rr >= 0) & (rr < N_ROWS) & (cc >= 0) & (cc < N_COLS))
    flat = rr[ok] * N_COLS + cc[ok]
    s = np.bincount(flat, weights=v[ok], minlength=N_ROWS * N_COLS)
    n = np.bincount(flat, minlength=N_ROWS * N_COLS)
    with np.errstate(invalid="ignore", divide="ignore"):
        mean = np.where(n > 0, s / np.maximum(n, 1), np.nan)
    return mean.reshape(N_ROWS, N_COLS), n.reshape(N_ROWS, N_COLS)


# =================================================================================================
# PRF interval totals and index
# =================================================================================================
def interval_totals(monthly: pd.DataFrame, value_col: str = "precip_mm",
                    id_col: str = "grid_id") -> pd.DataFrame:
    """Sum monthly totals into the 11 PRF two-month intervals.

    monthly: one row per (id_col, year, month) with a monthly total in value_col.
    Returns columns [id_col, year, interval_name, interval_code, interval_<value_col>]; an
    interval is produced only when both of its months are present and non-missing. Intervals
    never cross a calendar year (Nov-Dec is the last), matching PRF.
    """
    m = monthly[[id_col, "year", "month", value_col]].dropna(subset=[value_col])
    wide = m.pivot_table(index=[id_col, "year"], columns="month", values=value_col, aggfunc="first")
    out = []
    for name in INTERVAL_NAMES:
        m1, m2 = INTERVAL_MONTHS[name]
        if m1 not in wide.columns or m2 not in wide.columns:
            continue
        tot = (wide[m1] + wide[m2]).dropna()
        df = tot.rename(f"interval_{value_col}").reset_index()
        df["interval_name"] = name
        df["interval_code"] = INTERVAL_CODES[name]
        out.append(df)
    res = pd.concat(out, ignore_index=True)
    cols = [id_col, "year", "interval_name", "interval_code", f"interval_{value_col}"]
    return res[cols].sort_values([id_col, "year", "interval_code"]).reset_index(drop=True)


def dst_base_end(year: int, current_crop_year: int = 2027) -> int:
    """Last base-period year the DST uses for a given index year (observed 2026-10-29).

    The DST (ReinsuranceYear 2027) shows the 2026 crop year against a base ending 2024 (= Y - 2)
    and every earlier year against the current base ending 2025 (= current_crop_year - 2).
    """
    return year - 2 if year >= current_crop_year - 1 else current_crop_year - 2


def handbook_base_end(year: int) -> int:
    """FCIC-18150 'as-settled' rule: the base period ends two years before the crop year."""
    return year - 2


def compute_index(intervals: pd.DataFrame, value_col: str, base_start: int,
                  base_end: int | Callable[[int], int], id_col: str = "grid_id",
                  min_base_years: int = 1, round_to: int | None = None) -> pd.DataFrame:
    """Add expected precipitation and the PRF index (100 = normal) to an interval table.

    intervals: output of interval_totals (or any frame with id_col, year, interval_name and
    value_col). base_start: first base year. base_end: last base year, either a fixed int or a
    function of the index year (e.g. dst_base_end, handbook_base_end). The expected value for
    (grid, interval, base window) is the plain mean of value_col over base years that have data.
    Rows whose base window has fewer than min_base_years years get NaN. round_to: decimals for
    the index (RMA publishes 1 decimal); None keeps full precision.

    Returns a copy with added columns expected_<value_col>, base_start, base_end, index_value.
    """
    df = intervals.copy()
    if callable(base_end):
        df["base_end"] = df["year"].map(base_end).astype(int)
    else:
        df["base_end"] = int(base_end)
    df["base_start"] = int(base_start)
    exp_col = f"expected_{value_col}"
    parts = []
    for end, sub in df.groupby("base_end", sort=False):
        base = df[(df["year"] >= base_start) & (df["year"] <= end)]
        stats = (base.groupby([id_col, "interval_name"])[value_col]
                 .agg(["mean", "count"]).rename(columns={"mean": exp_col, "count": "_n"}))
        merged = sub.join(stats, on=[id_col, "interval_name"])
        merged.loc[merged["_n"].fillna(0) < min_base_years, exp_col] = np.nan
        parts.append(merged.drop(columns="_n"))
    out = pd.concat(parts).sort_index()
    out["index_value"] = 100.0 * out[value_col] / out[exp_col]
    if round_to is not None:
        out["index_value"] = out["index_value"].round(round_to)
    return out


def trigger_disagreement(index_a, index_b, coverage: float = 90.0) -> float:
    """Share of cases where two index series disagree on whether a PRF payment triggers.

    PRF pays for an interval when the final grid index is below the trigger index
    (coverage level x expected index of 100), i.e. index < coverage.
    """
    a = np.asarray(index_a, dtype=float)
    b = np.asarray(index_b, dtype=float)
    ok = np.isfinite(a) & np.isfinite(b)
    return float(np.mean((a[ok] < coverage) != (b[ok] < coverage))) if ok.any() else float("nan")


def comparison_stats(ours, official, coverage: float = 90.0) -> dict:
    """Pearson r, mean absolute error, bias (ours - official) and trigger disagreement."""
    a = np.asarray(ours, dtype=float)
    b = np.asarray(official, dtype=float)
    ok = np.isfinite(a) & np.isfinite(b)
    a, b = a[ok], b[ok]
    if a.size < 2:
        return {"n": int(a.size), "r": np.nan, "mae": np.nan, "bias": np.nan,
                "trigger_disagree": np.nan}
    return {"n": int(a.size), "r": float(np.corrcoef(a, b)[0, 1]),
            "mae": float(np.mean(np.abs(a - b))), "bias": float(np.mean(a - b)),
            "trigger_disagree": trigger_disagreement(a, b, coverage),
            "official_trigger_rate": float(np.mean(b < coverage)),
            "ours_trigger_rate": float(np.mean(a < coverage))}
