"""Pull gridded monthly precipitation for every PRF/CPC 0.25-degree cell near our stations.

Run from the repo root:  python scripts/pull_cpc.py [--skip-ncei] [--radius 150]

Outputs (data/processed/):
  cpc_monthly_precip_grids.parquet   grid_id, year, month, precip_in, source   (CPC, 1948-01 on)
  ncei_monthly_precip_grids.parquet  grid_id, year, month, precip_in, n_subcells, source
                                     (NCEI nClimGrid averaged to PRF grids, 1951-01 on)
for all cells whose centres lie within --radius miles (default 150) of any settlement station in
agri_hedge.locations.ALL_SITES and that have data (ocean cells are dropped).

CPC route (smallest that reaches the latest complete month with the vintage RMA settled on):
  1. 1948-01 .. 2018-12: PSL monthly means precip.V1.0.mon.mean.nc (mm/day), OPeNDAP subset of a
     bounding box around the stations (~30 MB). Values through 2006 are CPC V1.0 (retrospective);
     after 2006 they come from CPC's real-time (RT) analysis. (The file itself ends 2024-05.)
  2. 2019-01 (--daily-from) .. latest complete month: CPC's own daily binary files (0.1 mm/day),
     using the reprocessed UPDATED analysis where it exists (2019 on, ~2 months behind) and RT
     otherwise. RMA's as-settled final indexes match UPDATED far better than RT (see
     docs/analysis/06b_index_validation.md). Each day is ~288 KB (~815 MB transfer for 2019-01 to 2026-09);
     only monthly CONUS totals are cached (data/raw/cpc/cpc_daily_monthly/).
NCEI route: nClimGrid-Monthly nclimgrid_prcp.nc (mm) read month by month with HTTP byte-range
requests (netCDF "#mode=bytes"; ~1.1 MB per month transferred, nothing large stored), averaged
over the 36 nClimGrid cells in each PRF grid, cached per year under data/raw/nclimgrid/.

Units: PSL mon.mean is mm/day -> x days in month -> mm; CPC daily 0.1 mm -> mm; nClimGrid mm.
precip_in = mm / 25.4. All caches make reruns fast; delete a cache file to force a re-pull.
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
import time

import numpy as np
import pandas as pd
import requests

from agri_hedge.config import PROCESSED, RAW
from agri_hedge.cpc import (MM_PER_INCH, NCLIMGRID_MONTHLY_URL, PSL_DAILY_RT, PSL_MONTHLY_OPENDAP,
                            cpc_daily_url, days_in_month, fine_grid_to_prf, read_cpc_daily_binary)
from agri_hedge.locations import ALL_SITES
from agri_hedge.prf_grid import N_COLS, grid_id_to_rowcol, grid_ids_within_radius

RAW_CPC = RAW / "cpc"
RAW_NCEI = RAW / "nclimgrid"
TODAY = dt.date(2026, 10, 29)


def target_cells(radius_mi: float) -> list[int]:
    """Union of CPC/PRF cells within radius_mi of any settlement station."""
    ids = set()
    for site in ALL_SITES.values():
        ids.update(grid_ids_within_radius(site["station_lat"], site["station_lon"], radius_mi))
    return sorted(ids)


def with_retry(fn, what: str, tries: int = 6):
    delay = 5.0
    for k in range(tries):
        try:
            return fn()
        except Exception as e:  # HTTP 429 from THREDDS shows up as RuntimeError / OSError
            if k == tries - 1:
                raise
            print(f"  {what}: {e!r}; retrying in {delay:.0f}s", flush=True)
            time.sleep(delay)
            delay *= 2


# ------------------------------------------------------------------------------------------------
# CPC part 1: PSL monthly means via OPeNDAP
# ------------------------------------------------------------------------------------------------
def pull_psl_monthly(r0: int, r1: int, c0: int, c1: int):
    """Return (precip_mm[T, R, C], months[(year, month)]) for rows r0..r1, cols c0..c1."""
    import netCDF4
    cache = RAW_CPC / f"psl_mon_mean_r{r0}-{r1}_c{c0}-{c1}.npz"
    if cache.exists():
        z = np.load(cache)
        return z["precip_mm"], [tuple(x) for x in z["months"]]
    RAW_CPC.mkdir(parents=True, exist_ok=True)
    ds = with_retry(lambda: netCDF4.Dataset(PSL_MONTHLY_OPENDAP), "open PSL OPeNDAP")
    var = ds.variables["precip"]
    tvar = ds.variables["time"]
    times = netCDF4.num2date(tvar[:], tvar.units, only_use_cftime_datetimes=False)
    months = [(t.year, t.month) for t in times]
    lat = ds.variables["lat"][r0:r1 + 1]
    lon = ds.variables["lon"][c0:c1 + 1]
    assert abs(float(lat[0]) - (20.125 + 0.25 * r0)) < 1e-4, "unexpected PSL latitude grid"
    assert abs(float(lon[0]) - (230.125 + 0.25 * c0)) < 1e-4, "unexpected PSL longitude grid"
    chunks = []
    for t0 in range(0, len(months), 120):
        t1 = min(t0 + 120, len(months))
        a = with_retry(lambda: var[t0:t1, r0:r1 + 1, c0:c1 + 1], f"PSL months {t0}-{t1}")
        chunks.append(np.ma.filled(np.ma.asarray(a, dtype=np.float64), np.nan))
        print(f"  PSL monthly means: months {t0}-{t1 - 1} of {len(months)}", flush=True)
        time.sleep(1.0)
    rate = np.concatenate(chunks, axis=0)  # mm/day
    ndays = np.array([days_in_month(y, m) for y, m in months], dtype=np.float64)
    precip_mm = rate * ndays[:, None, None]
    np.savez_compressed(cache, precip_mm=precip_mm.astype(np.float32), months=np.array(months))
    return precip_mm.astype(np.float32), months


# ------------------------------------------------------------------------------------------------
# CPC part 2: CPC daily binaries -> monthly CONUS totals
# ------------------------------------------------------------------------------------------------
def cpc_month_total(year: int, month: int, session: requests.Session):
    """Monthly CONUS total (120 x 300 mm) from CPC daily files, or None if the month is incomplete.

    Uses UPDATED when available for a day, else RT. Returns (total, label) where label records
    which analysis versions went in ("UPDATED", "RT" or "UPDATED+RT").
    """
    cache_dir = RAW_CPC / "cpc_daily_monthly"
    cache = cache_dir / f"{year:04d}{month:02d}.npz"
    if cache.exists():
        z = np.load(cache)
        return z["total"], str(z["label"])
    nd = days_in_month(year, month)
    if dt.date(year, month, nd) >= TODAY:
        return None, None
    total = np.zeros((120, 300))
    kinds = set()
    for d in range(1, nd + 1):
        buf = None
        for kind in ("UPDATED", "RT"):
            if kind == "UPDATED" and year < 2019:
                continue
            url = cpc_daily_url(year, month, d, kind)
            r = with_retry(lambda: session.get(url, timeout=60), f"CPC {url[-30:]}")
            if r.status_code == 200 and len(r.content) >= 288000:
                buf = r.content
                kinds.add(kind)
                break
        if buf is None:
            print(f"  CPC daily missing for {year}-{month:02d}-{d:02d}; month incomplete")
            return None, None
        total += read_cpc_daily_binary(buf)  # NaN anywhere -> NaN month (ocean cells)
    label = "+".join(k for k in ("UPDATED", "RT") if k in kinds)
    cache_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(cache, total=total.astype(np.float32), label=np.array(label))
    return total.astype(np.float32), label


# ------------------------------------------------------------------------------------------------
# NCEI nClimGrid monthly (byte-range reads) -> PRF-grid means
# ------------------------------------------------------------------------------------------------
def pull_nclimgrid(start_year: int):
    """Yield (year, month, mean[120,300], count[120,300]) for every nClimGrid month >= start_year."""
    import netCDF4
    ds = None
    lat = lon = None
    idx = None
    RAW_NCEI.mkdir(parents=True, exist_ok=True)
    year = start_year
    while True:
        cache = RAW_NCEI / f"nclimgrid_prf_{year}.npz"
        if cache.exists() and year < TODAY.year:
            z = np.load(cache)
            for k, m in enumerate(z["months"]):
                yield year, int(m), z["mean"][k], z["count"]
            year += 1
            continue
        if ds is None:
            ds = with_retry(lambda: netCDF4.Dataset(NCLIMGRID_MONTHLY_URL + "#mode=bytes"),
                            "open nClimGrid")
            lat = ds.variables["lat"][:]
            lon = ds.variables["lon"][:]
            tv = ds.variables["time"]
            dates = netCDF4.num2date(tv[:], tv.units, only_use_cftime_datetimes=False)
            idx = {(d.year, d.month): k for k, d in enumerate(dates)}
            print(f"  nClimGrid monthly available {dates[0]:%Y-%m} to {dates[-1]:%Y-%m}")
        months = [m for m in range(1, 13) if (year, m) in idx]
        if not months:
            break
        means = []
        count = None
        for m in months:
            a = with_retry(lambda: ds.variables["prcp"][idx[(year, m)], :, :], f"nClimGrid {year}-{m}")
            mean, count = fine_grid_to_prf(a, lat, lon)
            means.append(mean.astype(np.float32))
        means = np.stack(means)
        np.savez_compressed(cache, mean=means, count=count.astype(np.int16), months=np.array(months))
        print(f"  nClimGrid {year}: {len(months)} months", flush=True)
        for k, m in enumerate(months):
            yield year, m, means[k], count
        if len(months) < 12:
            break
        year += 1


def to_frame(cells, rc, getter, months, source_of):
    """Build a long DataFrame for cells from per-month arrays (getter(k) -> 2-D array)."""
    rows_idx = np.array([r for r, _ in rc])
    cols_idx = np.array([c for _, c in rc])
    frames = []
    for k, (y, m) in enumerate(months):
        vals = getter(k)[rows_idx, cols_idx]
        frames.append(pd.DataFrame({"grid_id": cells, "year": y, "month": m, "precip_mm": vals,
                                    "source": source_of(y, m)}))
    return pd.concat(frames, ignore_index=True)


def finish(df: pd.DataFrame, extra_cols=()):
    df = df.dropna(subset=["precip_mm"]).copy()
    df["precip_in"] = (df["precip_mm"] / MM_PER_INCH).astype("float32")
    df["grid_id"] = df["grid_id"].astype("int32")
    df["year"] = df["year"].astype("int16")
    df["month"] = df["month"].astype("int8")
    df["source"] = df["source"].astype("category")
    cols = ["grid_id", "year", "month", "precip_in", *extra_cols, "source"]
    return df[cols].sort_values(["grid_id", "year", "month"]).reset_index(drop=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--radius", type=float, default=150.0, help="miles around each station")
    ap.add_argument("--skip-ncei", action="store_true")
    ap.add_argument("--ncei-start", type=int, default=1951)
    ap.add_argument("--daily-from", default="2019-01",
                    help="first month (YYYY-MM) taken from CPC daily files instead of PSL monthly")
    ap.add_argument("--rt-check-year", type=int, default=2025,
                    help="also cache PSL's CPC real-time daily file for this year (~10 MB) so "
                         "build_indices.py can compare RT with UPDATED; 0 to skip")
    args = ap.parse_args(argv)

    if args.rt_check_year:
        rt_path = RAW_CPC / "daily" / f"precip.V1.0.{args.rt_check_year}.nc"
        if not rt_path.exists():
            rt_path.parent.mkdir(parents=True, exist_ok=True)
            url = PSL_DAILY_RT.format(year=args.rt_check_year)
            print(f"Downloading {url} (RT-vs-UPDATED check)")
            r = with_retry(lambda: requests.get(url, timeout=600), "PSL RT daily")
            r.raise_for_status()
            rt_path.write_bytes(r.content)

    cells = target_cells(args.radius)
    rc = [grid_id_to_rowcol(g) for g in cells]
    r0, r1 = min(r for r, _ in rc), max(r for r, _ in rc)
    c0, c1 = min(c for _, c in rc), max(c for _, c in rc)
    print(f"{len(cells)} cells within {args.radius:.0f} mi of {len(ALL_SITES)} stations; "
          f"bbox rows {r0}-{r1}, cols {c0}-{c1}")

    # ---- CPC -----------------------------------------------------------------------------------
    print("CPC step 1: PSL monthly means (OPeNDAP)")
    psl, psl_months = pull_psl_monthly(r0, r1, c0, c1)
    rc_local = [(r - r0, c - c0) for r, c in rc]
    dfy, dfm = (int(x) for x in args.daily_from.split("-"))
    keep = [k for k, ym in enumerate(psl_months) if ym < (dfy, dfm)]
    psl, psl_months = psl[keep], [psl_months[k] for k in keep]
    cpc = to_frame(cells, rc_local, lambda k: psl[k], psl_months,
                   lambda y, m: "CPC V1.0 (PSL monthly mean)" if y <= 2006
                   else "CPC RT (PSL monthly mean)")
    last = psl_months[-1]
    print(f"  PSL monthly means used through {last[0]}-{last[1]:02d}")

    print("CPC step 2: CPC daily files for later months")
    sess = requests.Session()
    sess.headers["User-Agent"] = "agri-hedge ECE473 research"
    y, m = last
    extra = []
    while True:
        m += 1
        if m == 13:
            y, m = y + 1, 1
        if dt.date(y, m, 1) >= TODAY:
            break
        total, label = cpc_month_total(y, m, sess)
        if total is None:
            break
        extra.append(((y, m), total, label))
        print(f"  {y}-{m:02d}: {label}", flush=True)
    if extra:
        cpc_daily = to_frame(cells, rc, lambda k: extra[k][1], [e[0] for e in extra],
                             lambda yy, mm: f"CPC {dict((e[0], e[2]) for e in extra)[(yy, mm)]}"
                                            " (CPC daily files)")
        cpc = pd.concat([cpc, cpc_daily], ignore_index=True)
    cpc = finish(cpc)
    out = PROCESSED / "cpc_monthly_precip_grids.parquet"
    cpc.to_parquet(out, index=False)
    print(f"Wrote {out}: {len(cpc)} rows, {cpc.grid_id.nunique()} cells, "
          f"{cpc.year.min()}-{cpc.year.max()}; sources {cpc.source.value_counts().to_dict()}")

    # ---- NCEI ----------------------------------------------------------------------------------
    if not args.skip_ncei:
        print("NCEI: nClimGrid-Monthly averaged to PRF grids")
        recs = []
        rows_idx = np.array([r for r, _ in rc])
        cols_idx = np.array([c for _, c in rc])
        for yy, mm, mean, count in pull_nclimgrid(args.ncei_start):
            recs.append(pd.DataFrame({"grid_id": cells, "year": yy, "month": mm,
                                      "precip_mm": mean[rows_idx, cols_idx],
                                      "n_subcells": count[rows_idx, cols_idx].astype("int8"),
                                      "source": "NCEI nClimGrid-Monthly (36-cell mean)"}))
        ncei = finish(pd.concat(recs, ignore_index=True), extra_cols=("n_subcells",))
        out = PROCESSED / "ncei_monthly_precip_grids.parquet"
        ncei.to_parquet(out, index=False)
        print(f"Wrote {out}: {len(ncei)} rows, {ncei.grid_id.nunique()} cells, "
              f"{ncei.year.min()}-{ncei.year.max()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
