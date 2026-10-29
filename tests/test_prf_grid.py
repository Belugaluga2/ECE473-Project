"""Tests for agri_hedge.prf_grid (no network)."""
import json
import random
from pathlib import Path

import pytest

from agri_hedge.locations import ALL_SITES, haversine_miles
from agri_hedge.prf_grid import (MAX_GRID_ID, grid_id_to_bounds, grid_id_to_center,
                                 grid_id_to_rowcol, grid_ids_within_radius, latlon_to_grid_id,
                                 parse_index_values, rowcol_to_grid_id)

FIX = Path(__file__).parent / "fixtures" / "b1"

# Grid IDs returned by RMA's own PRF grid map (ArcGIS layer PRF/PRF_GRID/MapServer/0 behind the
# DST grid locator, queried 2026-10-29 by scripts/pull_prf_official_index.py).
OFFICIAL_SITE_GRIDS = {
    ("DFW", "station"): 15432, ("DFW", "farm"): 15429,
    ("SAT", "station"): 11527, ("SAT", "farm"): 10626,
    ("OKC", "station"): 18430, ("OKC", "farm"): 18129,
    ("SGF", "station"): 20547, ("SGF", "farm"): 20845,
    ("DEN", "station"): 23802, ("DEN", "farm"): 23204,
    ("ABQ", "station"): 18094, ("ABQ", "farm"): 17497,
    ("TPA", "station"): 9490, ("TPA", "farm"): 8893,
    ("ORD", "station"): 26269, ("ORD", "farm"): 26267,
}
OFFICIAL_CHECK_POINTS = [  # (lat, lon, grid_id)
    (47.45, -122.31, 32731), (45.03, -68.93, 30245), (46.6, -110.4, 31879),
    (41.31, -100.07, 25620), (32.1, -83.6, 14586), (38.53, -98.81, 22325),
]


@pytest.mark.parametrize("key,role", list(OFFICIAL_SITE_GRIDS))
def test_site_grid_ids_match_official_map(key, role):
    s = ALL_SITES[key]
    assert latlon_to_grid_id(s[f"{role}_lat"], s[f"{role}_lon"]) == OFFICIAL_SITE_GRIDS[(key, role)]


@pytest.mark.parametrize("lat,lon,gid", OFFICIAL_CHECK_POINTS)
def test_check_points_match_official_map(lat, lon, gid):
    assert latlon_to_grid_id(lat, lon) == gid


def test_bounds_match_official_polygon():
    # ArcGIS polygon for GRIDCODE 15432: lon -97.25..-97.00, lat 32.75..33.00
    assert grid_id_to_bounds(15432) == pytest.approx((32.75, 33.0, -97.25, -97.0))
    assert grid_id_to_center(15432) == pytest.approx((32.875, -97.125))


def test_neighbours_east_and_north():
    lat, lon = grid_id_to_center(15432)
    assert latlon_to_grid_id(lat, lon + 0.25) == 15433
    assert latlon_to_grid_id(lat + 0.25, lon) == 15732


def test_round_trip_many_ids():
    rng = random.Random(0)
    ids = [1, 300, 301, MAX_GRID_ID, 15432] + [rng.randint(1, MAX_GRID_ID) for _ in range(500)]
    for gid in ids:
        assert latlon_to_grid_id(*grid_id_to_center(gid)) == gid
        assert rowcol_to_grid_id(*grid_id_to_rowcol(gid)) == gid
        lat_s, lat_n, lon_w, lon_e = grid_id_to_bounds(gid)
        # any interior point maps back to the same grid
        assert latlon_to_grid_id(lat_s + 0.01, lon_e - 0.01) == gid


def test_cpc_longitude_convention_and_edges():
    assert latlon_to_grid_id(32.875, 262.875) == 15432          # 0..360 degrees east
    assert latlon_to_grid_id(33.0, -97.0) == 15733              # corner -> cell to the N and E
    assert grid_id_to_center(1) == pytest.approx((20.125, -129.875))
    with pytest.raises(ValueError):
        latlon_to_grid_id(19.9, -97.0)
    with pytest.raises(ValueError):
        grid_id_to_center(MAX_GRID_ID + 1)


def test_grids_within_radius():
    s = ALL_SITES["DFW"]
    ids = grid_ids_within_radius(s["station_lat"], s["station_lon"], 30)
    assert 15432 in ids
    for g in ids:
        assert haversine_miles(s["station_lat"], s["station_lon"], *grid_id_to_center(g)) <= 30
    # a 30-mile disc holds roughly pi*30^2 / (17.3 * 14.5 sq mi per cell) ~ 11 cells
    assert 6 <= len(ids) <= 20
    assert grid_ids_within_radius(s["station_lat"], s["station_lon"], 30, valid_ids={15432}) == [15432]


def test_parse_index_values_fixture():
    raw = json.loads((FIX / "dst_index_15432_sample.json").read_text())
    rows = parse_index_values(raw, grid_id=15432)
    years = {r["year"] for r in rows}
    assert years == {2025, 2026}                     # 1950 rows are all null -> dropped
    assert sum(r["year"] == 2025 for r in rows) == 11
    assert sum(r["year"] == 2026 for r in rows) == 6  # Jan-Feb .. Jun-Jul published by 2026-10-29
    r = next(r for r in rows if r["year"] == 2025 and r["interval_code"] == 625)
    assert r["interval_precip_mm"] == pytest.approx(137.59)
    assert r["expected_precip_mm"] == pytest.approx(108.77)
    # PercentOfNormal = IntervalMeasurement / AverageIntervalMeasurement rounded to 3 decimals
    for r in rows:
        assert r["percent_of_normal"] == pytest.approx(
            round(r["interval_precip_mm"] / r["expected_precip_mm"], 3), abs=1.1e-3)
