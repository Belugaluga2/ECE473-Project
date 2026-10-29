"""Map study sites to PRF grids and pull RMA's official historical PRF grid index values.

Run from the repo root:  python scripts/pull_prf_official_index.py [--skip-ring] [--refresh]

Steps (all network results are cached under data/raw/prf_official/, so reruns are fast):
 1. Download the DST grid list (which of the 36,000 CPC cells are CONUS PRF grids).
 2. For every site point in ALL_SITES (station and farm) plus extra check points, ask RMA's own
    grid map (ArcGIS layer behind the DST grid locator) for the grid ID and polygon, and check that
    agri_hedge.prf_grid.latlon_to_grid_id / grid_id_to_bounds give the same answer.
 3. Write data/processed/study_grids.csv.
 4. Pull GetIndexValues (all 11 intervals, every published year) for each study grid and, unless
    --skip-ring, every CONUS PRF grid whose centre is within 100 miles of a settlement station.
 5. Write data/processed/prf_official_index.csv (study grids),
    data/processed/prf_official_index_ring100.parquet (study + ring grids) and
    data/processed/prf_ring100_grids.csv (station-to-grid distances for the ring).

Endpoints used are listed in src/agri_hedge/prf_grid.py and printed at the end of the run.
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys

import pandas as pd

from agri_hedge.config import PROCESSED, RAW
from agri_hedge.locations import ALL_SITES, haversine_miles
from agri_hedge.prf_grid import (ARCGIS_GRID_LAYER, DST_API, DST_COUNTIES_FOR_GRID_URL,
                                 DST_GRID_LIST_URL, DST_INDEX_URL, DST_PROXY_URL, _session,
                                 cached_index_values, fetch_conus_grid_list,
                                 fetch_counties_for_grid, grid_id_to_bounds, grid_id_to_center,
                                 grid_ids_within_radius, latlon_to_grid_id, official_grid_lookup,
                                 parse_index_values)
from agri_hedge.prf_intervals import CODE_TO_INTERVAL

OUT_RAW = RAW / "prf_official"
INDEX_CACHE = OUT_RAW / "index_json"
RING_RADIUS_MI = 100.0
RETRIEVED = "2026-10-29"
SOURCE = "RMA PRF Decision Support Tool GetIndexValues (NCEI nClimGrid-based history)"
# DST convention observed 2026-10-29 (ReinsuranceYear 2027 in the page settings): years up to 2025
# are indexed against the 1951-2025 mean; the 2026 crop year against the 1951-2024 mean.
DST_FIRST_YEAR = 1951

# Extra check points (not study sites) to test the grid formula across the country.
EXTRA_CHECK_POINTS = {
    "check_Seattle": (47.45, -122.31), "check_Maine": (45.03, -68.93),
    "check_Montana": (46.6, -110.4), "check_Nebraska": (41.31, -100.07),
    "check_Georgia": (32.1, -83.6), "check_Kansas": (38.53, -98.81),
    # Points exactly on a cell edge/corner touch 2-4 polygons; ArcGIS returns one of them (the
    # southern one in our tests) while latlon_to_grid_id assigns the northern/eastern cell.
    "edge_lat_45": (45.0, -68.9), "edge_corner": (33.0, -97.0),
}


def load_json_cache(path, fetch):
    """Return cached JSON at path, or call fetch() and cache the result (gzip)."""
    if path.exists():
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            return json.load(fh)
    data = fetch()
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        json.dump(data, fh)
    return data


def base_period_label(year: int) -> str:
    return f"{DST_FIRST_YEAR}-2024" if year >= 2026 else f"{DST_FIRST_YEAR}-2025"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--skip-ring", action="store_true", help="only pull the study grids")
    ap.add_argument("--refresh", action="store_true", help="ignore cached index JSON")
    args = ap.parse_args(argv)
    s = _session()

    # 1. Grid list -------------------------------------------------------------------------------
    grid_list = load_json_cache(OUT_RAW / "conus_grid_list.json.gz", lambda: fetch_conus_grid_list(s))
    conus_ids = {int(g["NoaaGridId"]) for g in grid_list if g["IsContinentalUsFlag"]}
    print(f"DST grid list: {len(grid_list)} records, {len(conus_ids)} CONUS PRF grids")

    # 2. Official lookups vs our formula ---------------------------------------------------------
    points = {}
    for key, site in ALL_SITES.items():
        points[(key, "station")] = (site["station_lat"], site["station_lon"])
        points[(key, "farm")] = (site["farm_lat"], site["farm_lon"])
    for key, ll in EXTRA_CHECK_POINTS.items():
        points[(key, "check")] = ll

    lk_path = OUT_RAW / "arcgis_grid_lookups.json.gz"
    lookups = load_json_cache(lk_path, dict) if lk_path.exists() else {}
    missing = {k: ll for k, ll in points.items() if f"{k[0]}|{k[1]}|{ll[0]}|{ll[1]}" not in lookups}
    for k, (lat, lon) in missing.items():
        lookups[f"{k[0]}|{k[1]}|{lat}|{lon}"] = official_grid_lookup(lat, lon, session=s)
    if missing:
        with gzip.open(lk_path, "wt", encoding="utf-8") as fh:
            json.dump(lookups, fh)

    def lookup(key, role):
        lat, lon = points[(key, role)]
        return lookups[f"{key}|{role}|{lat}|{lon}"]

    n_ok = 0
    print("\nGrid-ID validation against RMA's grid map (ArcGIS PRF_GRID layer):")
    print(f"{'point':28s} {'lat':>9s} {'lon':>10s} {'official':>8s} {'ours':>6s} bounds-match")
    for (key, role), (lat, lon) in points.items():
        off = lookup(key, role)
        ours = latlon_to_grid_id(lat, lon)
        b = grid_id_to_bounds(off["grid_id"])
        bounds_ok = (abs(b[0] - off["lat_south"]) < 1e-3 and abs(b[1] - off["lat_north"]) < 1e-3
                     and abs(b[2] - off["lon_west"]) < 1e-3 and abs(b[3] - off["lon_east"]) < 1e-3)
        ok = ours == off["grid_id"] and bounds_ok
        n_ok += ok
        edge = key.startswith("edge")
        print(f"{key + '/' + role:28s} {lat:9.4f} {lon:10.4f} {off['grid_id']:8d} {ours:6d} "
              f"{'yes' if bounds_ok else 'NO'}"
              f"{'' if ok else ('   (edge point, expected)' if edge else '   <-- MISMATCH')}")
    print(f"{n_ok}/{len(points)} lookups agree (edge points touch 2-4 polygons;"
          " ArcGIS returns one of them, so an edge mismatch is not a formula error)")

    # 3. study_grids.csv -------------------------------------------------------------------------
    rows = []
    for key, site in ALL_SITES.items():
        for role in ("station", "farm"):
            lat, lon = site[f"{role}_lat"], site[f"{role}_lon"]
            gid = latlon_to_grid_id(lat, lon)
            clat, clon = grid_id_to_center(gid)
            rows.append({
                "site": key, "role": role, "lat": lat, "lon": lon, "grid_id": gid,
                "grid_center_lat": clat, "grid_center_lon": clon,
                # distance from the grid CENTRE to the Kalshi settlement station
                "distance_to_station_mi": round(haversine_miles(clat, clon, site["station_lat"],
                                                                site["station_lon"]), 2),
                "official_grid_id": lookup(key, role)["grid_id"],
                "is_prf_conus_grid": gid in conus_ids,
            })
    study = pd.DataFrame(rows)

    def do_counties():
        return {str(g): fetch_counties_for_grid(int(g), session=s) for g in study.grid_id.unique()}
    counties = load_json_cache(OUT_RAW / "grid_counties.json.gz", do_counties)
    study["grid_counties"] = [
        "; ".join(f"{c['CountyName']} {c['StateName']} ({c['StateCode']}{c['CountyCode']})"
                  for c in counties.get(str(g), [])) for g in study.grid_id]
    study.to_csv(PROCESSED / "study_grids.csv", index=False)
    print(f"\nWrote {PROCESSED / 'study_grids.csv'} ({len(study)} rows)")
    print(study[["site", "role", "grid_id", "distance_to_station_mi", "grid_counties"]]
          .to_string(index=False))

    # 4. Which grids to pull ---------------------------------------------------------------------
    study_ids = sorted(set(study.grid_id))
    ring_rows = []
    if not args.skip_ring:
        for key, site in ALL_SITES.items():
            for gid in grid_ids_within_radius(site["station_lat"], site["station_lon"],
                                              RING_RADIUS_MI, valid_ids=conus_ids):
                clat, clon = grid_id_to_center(gid)
                ring_rows.append({"site": key, "grid_id": gid, "grid_center_lat": clat,
                                  "grid_center_lon": clon,
                                  "distance_to_station_mi": round(haversine_miles(
                                      site["station_lat"], site["station_lon"], clat, clon), 2)})
    ring = pd.DataFrame(ring_rows)
    all_ids = sorted(set(study_ids) | set(ring.grid_id if len(ring) else []))
    print(f"\nPulling official indexes for {len(study_ids)} study grids + ring -> {len(all_ids)} grids")

    records = []
    for i, gid in enumerate(all_ids, 1):
        raw = cached_index_values(gid, INDEX_CACHE, session=s, refresh=args.refresh)
        recs = parse_index_values(raw, grid_id=gid)
        for r in recs:
            r["grid_id"] = gid
        records.extend(recs)
        if i % 50 == 0 or i == len(all_ids):
            print(f"  {i}/{len(all_ids)} grids done", flush=True)

    df = pd.DataFrame(records)
    df["interval_name"] = df["interval_code"].map(CODE_TO_INTERVAL)
    df["index_value"] = (df["percent_of_normal"] * 100).round(1)
    df["source"] = SOURCE
    df["base_period"] = df["year"].map(base_period_label)
    cols = ["grid_id", "year", "interval_name", "interval_code", "index_value", "source",
            "interval_precip_mm", "expected_precip_mm", "base_period", "filing_status_id"]
    df = df[cols].sort_values(["grid_id", "year", "interval_code"]).reset_index(drop=True)

    # 5. Outputs ---------------------------------------------------------------------------------
    df[df.grid_id.isin(study_ids)].to_csv(PROCESSED / "prf_official_index.csv", index=False)
    print(f"Wrote {PROCESSED / 'prf_official_index.csv'} "
          f"({df.grid_id.isin(study_ids).sum()} rows, {len(study_ids)} grids)")
    if len(ring):
        ring.to_csv(PROCESSED / "prf_ring100_grids.csv", index=False)
        out = df.copy()
        out["source"] = out["source"].astype("category")
        out["interval_name"] = out["interval_name"].astype("category")
        out["base_period"] = out["base_period"].astype("category")
        out.to_parquet(PROCESSED / "prf_official_index_ring100.parquet", index=False)
        print(f"Wrote {PROCESSED / 'prf_ring100_grids.csv'} ({len(ring)} site-grid pairs) and "
              f"prf_official_index_ring100.parquet ({len(out)} rows, {out.grid_id.nunique()} grids)")

    yrs = df.groupby("grid_id").year.agg(["min", "max"])
    print(f"\nYears published: {yrs['min'].min()}-{yrs['max'].max()}; "
          f"latest interval per grid (2026): "
          f"{df[df.year == 2026].groupby('grid_id').interval_code.max().map(CODE_TO_INTERVAL).value_counts().to_dict()}")

    print("\nEndpoints used:")
    for u in (DST_INDEX_URL, DST_GRID_LIST_URL, DST_COUNTIES_FOR_GRID_URL,
              f"{DST_PROXY_URL}?{ARCGIS_GRID_LAYER}/query", DST_API):
        print("  ", u)
    return 0


if __name__ == "__main__":
    sys.exit(main())
