"""PRF grid IDs <-> latitude/longitude, and access to RMA's official PRF Decision Support Tool (DST).

How PRF grid IDs work (verified 2026-10-29 against RMA's own grid map, see scripts/pull_prf_official_index.py)
-----------------------------------------------------------------------------------------------------------
PRF grids in the contiguous US are the cells of NOAA CPC's 0.25-degree CONUS precipitation grid
(FCIC-18150 handbook, section 32A). That grid is 300 columns (west to east) by 120 rows (south to
north). Column 0 spans longitude -130.00 to -129.75 (CPC cell centre 230.125 E) and row 0 spans
latitude 20.00 to 20.25 (centre 20.125 N). The PRF grid ID is the 1-based position of the cell in
that array, counting west to east first and then south to north:

    grid_id = row * 300 + col + 1,   row = floor((lat - 20) / 0.25),  col = floor((lon + 130) / 0.25)

so moving one cell east adds 1 and moving one cell north adds 300. Example: DFW airport
(32.897 N, -97.022 E) is in row 51, col 131 -> grid 15432, which spans 32.75-33.00 N and
-97.25 to -97.00 E. This is also exactly CPC's own file order ("starts from the 0.25deg grid box
centering at (129.875W; 20.125N), going from west to east first, and then south to north",
CPC GAUGE_CONUS README). Only 13,626 of the 36,000 cells are PRF-insurable CONUS grids (the rest
are ocean, Canada, or Mexico); the DST's GetContinentalUsGridList endpoint flags them. Hawaii and
Puerto Rico grids use RMA-defined names (e.g. "U1303", "M2309") and are not handled here.

Points that fall exactly on a cell edge are assigned to the cell to their north / east (floor).

Official DST backend (public, no authentication; found by reading the DST page's JavaScript)
------------------------------------------------------------------------------------------
Page: https://public-rma.fpac.usda.gov/apps/PRF . Its embedded settings name these REST services:
  {DST_API}/PrfExternalIndexes/GetIndexValues?intervalType=BiMonthly&sampleYearMinimum=1948
        &sampleYearMaximum=2026&gridId=15432            -> historical final grid indexes
  {DST_API}/PrfExternalIndexes/GetListOfAvailableRainfallYears
  {DST_API}/PrfExternalNoaaGrids/GetContinentalUsGridList  -> all grid IDs + CONUS flag
  {DST_API}/PrfExternalNoaaGrids/GetNoaaGridId?gridName=...
  {DST_API}/PrfExternalStates/GetStates | GetCountiesByState?stateCode=48
        | GetCountiesAndStatesFromGridId?gridId=15432&gridName=15432
  {DST_API}/PrfExternalIntervalCodes/GetValidIntervalCodes?... (premium rate per interval)
  {DST_API}/PrfExternalPricingRates/GetPricingRates?...       (premium, subsidy, indemnity)
  {DST_API}/PrfExternalEstimatedIndemnities/GetEstimatedIndemnityValues?...
  {DST_API}/PrfExternalMaxAcrePercentage/GetMaxAcrePercentage?...
with DST_API = https://public-rma.fpac.usda.gov/apps/PrfWebApi . The grid map (lat/lon -> grid)
is an ArcGIS feature layer reached through the DST's proxy:
  https://public-rma.fpac.usda.gov/apps/prf/proxy/proxy.ashx?https://pdgis.rm.usda.net/arcgis/
        rest/services/PRF/PRF_GRID/MapServer/0/query?geometry=<lon>,<lat>&geometryType=
        esriGeometryPoint&inSR=4326&spatialRel=esriSpatialRelIntersects&outFields=GRIDCODE
        &returnGeometry=true&outSR=4326&f=json
(layer 1 of the same MapServer is counties). GetIndexValues returns, per year and interval code
(625 = Jan-Feb ... 635 = Nov-Dec): PercentOfNormal (index / 100, rounded to 3 decimals),
IntervalMeasurement (interval precipitation, mm), AverageIntervalMeasurement (the expected
interval precipitation, mm) and FilingStatusId.

IMPORTANT data-vintage finding (2026-10-29): the DST's history now starts in 1951 and its
IntervalMeasurement values equal NOAA NCEI nClimGrid monthly precipitation averaged over the 36
nClimGrid cells (1/24 degree) inside each PRF grid, not CPC values. See
docs/analysis/06b_index_validation.md.
"""
from __future__ import annotations

import gzip
import json
import math
import time
from pathlib import Path

from agri_hedge.locations import haversine_miles

# --- Grid geometry (CPC CONUS 0.25-degree grid) -------------------------------------------------
CELL_DEG = 0.25
LON_WEST = -130.0   # west edge of column 0
LAT_SOUTH = 20.0    # south edge of row 0
N_COLS = 300
N_ROWS = 120
MAX_GRID_ID = N_COLS * N_ROWS  # 36000

# --- Official DST endpoints ---------------------------------------------------------------------
DST_PAGE_URL = "https://public-rma.fpac.usda.gov/apps/PRF"
DST_API = "https://public-rma.fpac.usda.gov/apps/PrfWebApi"
DST_INDEX_URL = DST_API + "/PrfExternalIndexes/GetIndexValues"
DST_YEARS_URL = DST_API + "/PrfExternalIndexes/GetListOfAvailableRainfallYears"
DST_GRID_LIST_URL = DST_API + "/PrfExternalNoaaGrids/GetContinentalUsGridList"
DST_COUNTIES_FOR_GRID_URL = DST_API + "/PrfExternalStates/GetCountiesAndStatesFromGridId"
DST_PROXY_URL = "https://public-rma.fpac.usda.gov/apps/prf/proxy/proxy.ashx"
ARCGIS_GRID_LAYER = "https://pdgis.rm.usda.net/arcgis/rest/services/PRF/PRF_GRID/MapServer/0"
USER_AGENT = "agri-hedge ECE473 research (Princeton); contact via repo"


# =================================================================================================
# Pure geometry (no network)
# =================================================================================================
def latlon_to_rowcol(lat: float, lon: float) -> tuple[int, int]:
    """Return (row, col) of the 0.25-degree CPC/PRF cell containing (lat, lon).

    Longitude may be given in -180..180 or 0..360 degrees east. Raises ValueError outside the
    CPC CONUS domain (20-50 N, 130-55 W).
    """
    if lon > 180:
        lon -= 360.0
    row = math.floor((lat - LAT_SOUTH) / CELL_DEG + 1e-9)
    col = math.floor((lon - LON_WEST) / CELL_DEG + 1e-9)
    if not (0 <= row < N_ROWS and 0 <= col < N_COLS):
        raise ValueError(f"({lat}, {lon}) is outside the CPC CONUS 0.25-degree grid")
    return row, col


def latlon_to_grid_id(lat: float, lon: float) -> int:
    """PRF grid ID of the CONUS grid containing the point (lat in degrees N, lon in degrees E)."""
    row, col = latlon_to_rowcol(lat, lon)
    return row * N_COLS + col + 1


def grid_id_to_rowcol(grid_id: int) -> tuple[int, int]:
    """(row, col) indices (0-based, row from the south, col from the west) of a PRF grid ID.

    These are also the (lat, lon) array indices of the cell in CPC CONUS netCDF/binary files.
    """
    grid_id = int(grid_id)
    if not 1 <= grid_id <= MAX_GRID_ID:
        raise ValueError(f"grid_id {grid_id} is not a CONUS PRF grid (1..{MAX_GRID_ID})")
    row, col = divmod(grid_id - 1, N_COLS)
    return row, col


def grid_id_to_center(grid_id: int) -> tuple[float, float]:
    """(lat, lon) of the centre of a PRF grid, lon in -180..180 (e.g. 15432 -> (32.875, -97.125))."""
    row, col = grid_id_to_rowcol(grid_id)
    return (LAT_SOUTH + (row + 0.5) * CELL_DEG, LON_WEST + (col + 0.5) * CELL_DEG)


def grid_id_to_bounds(grid_id: int) -> tuple[float, float, float, float]:
    """(lat_south, lat_north, lon_west, lon_east) edges of a PRF grid in degrees."""
    row, col = grid_id_to_rowcol(grid_id)
    lat_s = LAT_SOUTH + row * CELL_DEG
    lon_w = LON_WEST + col * CELL_DEG
    return (lat_s, lat_s + CELL_DEG, lon_w, lon_w + CELL_DEG)


def rowcol_to_grid_id(row: int, col: int) -> int:
    """Inverse of grid_id_to_rowcol."""
    if not (0 <= row < N_ROWS and 0 <= col < N_COLS):
        raise ValueError(f"row/col ({row}, {col}) outside the 120 x 300 CPC CONUS grid")
    return int(row) * N_COLS + int(col) + 1


def grid_ids_within_radius(lat: float, lon: float, radius_mi: float,
                           valid_ids: set[int] | None = None) -> list[int]:
    """All grid IDs whose CENTRES lie within radius_mi statute miles of (lat, lon), sorted.

    valid_ids: optional set to filter by (e.g. the DST's CONUS-flagged PRF grids, or CPC land cells).
    """
    dlat = radius_mi / 69.0 + CELL_DEG
    dlon = radius_mi / (69.0 * max(math.cos(math.radians(lat)), 0.1)) + CELL_DEG
    r0, c0 = latlon_to_rowcol(max(min(lat - dlat, 49.99), 20.0), max(lon - dlon, -129.99))
    r1, c1 = latlon_to_rowcol(max(min(lat + dlat, 49.99), 20.0), min(lon + dlon, -55.01))
    out = []
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            gid = rowcol_to_grid_id(r, c)
            if valid_ids is not None and gid not in valid_ids:
                continue
            clat, clon = grid_id_to_center(gid)
            if haversine_miles(lat, lon, clat, clon) <= radius_mi:
                out.append(gid)
    return sorted(out)


# =================================================================================================
# Official DST access (network). Each function takes an optional requests.Session.
# =================================================================================================
def _session(session=None):
    import requests
    if session is not None:
        return session
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT})
    return s


def _get_json(url: str, params: dict | None = None, session=None, retries: int = 5,
              timeout: float = 60.0, pause: float = 0.25):
    """GET a JSON document with simple exponential back-off on HTTP 429/5xx and network errors."""
    s = _session(session)
    delay = 2.0
    last_err = None
    for _ in range(retries):
        try:
            r = s.get(url, params=params, timeout=timeout)
            if r.status_code == 200:
                time.sleep(pause)
                return r.json()
            last_err = f"HTTP {r.status_code}: {r.text[:200]}"
            if r.status_code not in (429, 500, 502, 503, 504):
                break
        except Exception as e:  # network hiccup
            last_err = repr(e)
        time.sleep(delay)
        delay *= 2
    raise RuntimeError(f"GET {url} {params} failed: {last_err}")


def official_grid_lookup(lat: float, lon: float, session=None) -> dict:
    """Ask RMA's PRF grid map (ArcGIS layer behind the DST grid locator) which grid holds a point.

    Returns {"grid_id": int, "lat_south", "lat_north", "lon_west", "lon_east"} from the polygon.
    """
    query = (f"{ARCGIS_GRID_LAYER}/query?geometry={lon},{lat}&geometryType=esriGeometryPoint"
             "&inSR=4326&spatialRel=esriSpatialRelIntersects&outFields=GRIDCODE"
             "&returnGeometry=true&outSR=4326&f=json")
    data = _get_json(f"{DST_PROXY_URL}?{query}", session=session)
    feats = data.get("features", [])
    if not feats:
        raise RuntimeError(f"no PRF grid polygon found at ({lat}, {lon})")
    f = feats[0]
    ring = f["geometry"]["rings"][0]
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    return {"grid_id": int(f["attributes"]["GRIDCODE"]),
            "lat_south": round(min(ys), 4), "lat_north": round(max(ys), 4),
            "lon_west": round(min(xs), 4), "lon_east": round(max(xs), 4)}


def fetch_counties_for_grid(grid_id: int, session=None) -> list[dict]:
    """Counties (state/county names and FIPS parts) that the DST associates with a grid."""
    data = _get_json(DST_COUNTIES_FOR_GRID_URL, {"gridId": grid_id, "gridName": str(grid_id)},
                     session=session)
    return data.get("locationData", [])


def fetch_conus_grid_list(session=None) -> list[dict]:
    """All DST grid records ({NoaaGridId, NoaaGridName, IsContinentalUsFlag, ...}); ~5 MB."""
    return _get_json(DST_GRID_LIST_URL, session=session, timeout=120)["noaaGridList"]


def fetch_index_values(grid_id: int, year_min: int = 1948, year_max: int = 2026,
                       session=None) -> dict:
    """Raw GetIndexValues JSON for one grid (bi-monthly intervals, all requested years)."""
    params = {"intervalType": "BiMonthly", "sampleYearMinimum": year_min,
              "sampleYearMaximum": year_max, "gridId": int(grid_id)}
    return _get_json(DST_INDEX_URL, params, session=session)


def parse_index_values(raw: dict, grid_id: int | None = None) -> list[dict]:
    """Flatten GetIndexValues JSON into rows; years/intervals without a published value are dropped.

    Row keys: grid_id, year, interval_code, percent_of_normal, interval_precip_mm,
    expected_precip_mm, filing_status_id.
    """
    rows = []
    for yr in raw.get("HistoricalIndexRows", []):
        for c in yr.get("HistoricalIndexDataColumns", []):
            if c.get("PercentOfNormal") is None:
                continue
            rows.append({
                "grid_id": int(c.get("GridId") or grid_id),
                "year": int(c["Year"]),
                "interval_code": int(c["IntervalCode"]),
                "percent_of_normal": float(c["PercentOfNormal"]),
                "interval_precip_mm": (None if c.get("IntervalMeasurement") is None
                                       else float(c["IntervalMeasurement"])),
                "expected_precip_mm": (None if c.get("AverageIntervalMeasurement") is None
                                       else float(c["AverageIntervalMeasurement"])),
                "filing_status_id": int(c.get("FilingStatusId") or 0),
            })
    return rows


def cached_index_values(grid_id: int, cache_dir: Path, session=None, refresh: bool = False,
                        year_max: int = 2026) -> dict:
    """fetch_index_values with an on-disk gzip JSON cache (cache_dir/<grid_id>.json.gz)."""
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{int(grid_id)}.json.gz"
    if path.exists() and not refresh:
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            return json.load(fh)
    raw = fetch_index_values(grid_id, year_max=year_max, session=session)
    tmp = path.with_suffix(".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8") as fh:
        json.dump(raw, fh)
    tmp.replace(path)
    return raw
