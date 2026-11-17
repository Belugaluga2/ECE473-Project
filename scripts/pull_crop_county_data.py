"""Pull county crop yields, county rain and county centroids for the row-crop benchmark (doc 29).

Run from the repo root (network needed on the first run; raw files are cached):

    python scripts/pull_crop_county_data.py

Sources
    USDA NASS Quick Stats county survey yields 1960-2025 (keyless CSV export, the same path
    scripts/r1_rain_yield_calcs.py uses) for corn grain, soybeans, winter wheat, grain sorghum and
    upland cotton, all practices and non-irrigated; acres harvested 2018-2022.
    NOAA NCEI nClimDiv county monthly precipitation (climdiv-pcpncy), 1895-present.
    US Census 2023 Gazetteer county centroids.

Outputs (committed, small)
    data/processed/county_crop_yields.parquet   crop, fips, state, county, year, practice, yield, unit
    data/processed/county_crop_acres.csv        crop, fips, mean acres harvested 2018-2022
    data/processed/county_monthly_precip.parquet fips, year, month, precip_in (1950-2025, crop counties only)
    data/processed/county_centroids.csv         fips, name, state, lat, lon
"""
from __future__ import annotations

import io
import re
import time
import urllib.parse
import zipfile

import numpy as np
import pandas as pd
import requests

from agri_hedge.config import PROCESSED, RAW

RAW_DIR = RAW / "r9_crop_benchmark"
RAW_DIR.mkdir(parents=True, exist_ok=True)
HEADERS = {"User-Agent": "Mozilla/5.0 (university research project)"}
QS_URL = "https://quickstats.nass.usda.gov"
CLIMDIV_URL = "https://www.ncei.noaa.gov/pub/data/cirs/climdiv/"
GAZ_URL = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2023_Gazetteer/2023_Gaz_counties_national.zip"

#: crop -> (Quick Stats item stem, yield unit)
CROPS = {
    "corn": ("CORN, GRAIN", "BU / ACRE"),
    "soybeans": ("SOYBEANS", "BU / ACRE"),
    "winter_wheat": ("WHEAT, WINTER", "BU / ACRE"),
    "sorghum": ("SORGHUM, GRAIN", "BU / ACRE"),
    "cotton": ("COTTON, UPLAND", "LB / ACRE"),
}
DECADES = [(1960, 1969), (1970, 1979), (1980, 1989), (1990, 1999), (2000, 2009), (2010, 2019), (2020, 2025)]
#: nClimDiv state codes are 01-48 in alphabetical order of the contiguous states; map to FIPS.
_CONUS_FIPS = [1, 4, 5, 6, 8, 9, 10, 12, 13, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33,
               34, 35, 36, 37, 38, 39, 40, 41, 42, 44, 45, 46, 47, 48, 49, 50, 51, 53, 54, 55, 56]
CLIMDIV_TO_FIPS = {i + 1: f for i, f in enumerate(_CONUS_FIPS)}


def _get(url: str, tries: int = 6) -> requests.Response:
    last = None
    for i in range(tries):
        try:
            last = requests.get(url, headers=HEADERS, timeout=300)
        except requests.RequestException:
            time.sleep(2 ** i)
            continue
        if last.status_code == 200:
            return last
        time.sleep(2 ** i)
    if last is None:
        raise RuntimeError(f"no response from {url}")
    last.raise_for_status()
    return last


def nass(params: dict, name: str, years: tuple[int, int]) -> pd.DataFrame:
    """One cached Quick Stats export. Years are sent as a repeated `year` parameter: the keyless
    export ignores `year__LE`, and returns only a summary line when a query exceeds 50,000 rows."""
    path = RAW_DIR / f"nass_{name}.csv"
    if not path.exists():
        pairs = list(params.items()) + [("year", str(y)) for y in range(years[0], years[1] + 1)]
        query = urllib.parse.urlencode(pairs, quote_via=urllib.parse.quote)
        uuid = _get(f"{QS_URL}/uuid/encode?{query}").text.strip().strip('"')
        text = _get(f"{QS_URL}/data/spreadsheet/{uuid}.csv").text
        if not text.startswith('"Program"'):
            raise RuntimeError(f"unexpected NASS response for {name}: {text[:200]}")
        path.write_text(text, encoding="utf-8")
        time.sleep(0.4)
    df = pd.read_csv(path, dtype=str)
    df["value"] = pd.to_numeric(df["Value"].str.replace(",", "").str.strip(), errors="coerce")
    df["year"] = pd.to_numeric(df["Year"], errors="coerce")
    return df


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df[(df["Period"] == "YEAR") & df["County ANSI"].notna() & df["value"].notna()].copy()
    df["fips"] = (df["State ANSI"].astype(int) * 1000 + df["County ANSI"].astype(int)).astype(int)
    return df


def pull_yields() -> pd.DataFrame:
    frames = []
    for crop, (stem, unit) in CROPS.items():
        for practice, item in (("all", f"{stem} - YIELD, MEASURED IN {unit}"),
                               ("non_irrigated", f"{stem}, NON-IRRIGATED - YIELD, MEASURED IN {unit}")):
            for y0, y1 in DECADES:
                df = nass({"source_desc": "SURVEY", "agg_level_desc": "COUNTY", "short_desc": item},
                          f"yield_{crop}_{practice}_{y0}", (y0, y1))
                df = _clean(df)
                if len(df) > 49000:
                    raise RuntimeError(f"{crop} {practice} {y0}: {len(df)} rows, near the 50k export limit")
                frames.append(pd.DataFrame({"crop": crop, "fips": df["fips"], "state": df["State"].str.title(),
                                            "county": df["County"].str.title(), "year": df["year"].astype(int),
                                            "practice": practice, "yield": df["value"], "unit": unit}))
                print(f"  {crop:13s} {practice:14s} {y0}-{y1}: {len(df)} rows", flush=True)
    out = pd.concat(frames, ignore_index=True).drop_duplicates(["crop", "fips", "year", "practice"])
    return out.sort_values(["crop", "fips", "practice", "year"]).reset_index(drop=True)


def pull_acres() -> pd.DataFrame:
    frames = []
    for crop, (stem, _) in CROPS.items():
        df = _clean(nass({"source_desc": "SURVEY", "agg_level_desc": "COUNTY", "short_desc": f"{stem} - ACRES HARVESTED"},
                         f"acres_{crop}_2018", (2018, 2022)))
        g = df.groupby("fips")["value"].mean().rename("acres_harvested_2018_2022").reset_index()
        g.insert(0, "crop", crop)
        frames.append(g)
        print(f"  acres {crop}: {len(g)} counties, {g['acres_harvested_2018_2022'].sum() / 1e6:.1f} M acres", flush=True)
    return pd.concat(frames, ignore_index=True)


def pull_centroids() -> pd.DataFrame:
    path = RAW_DIR / "gaz_counties_2023.txt"
    if not path.exists():
        z = zipfile.ZipFile(io.BytesIO(_get(GAZ_URL).content))
        path.write_bytes(z.read(z.namelist()[0]))
    g = pd.read_csv(path, sep="\t", dtype=str)
    g.columns = [c.strip() for c in g.columns]
    return pd.DataFrame({"fips": g["GEOID"].astype(int), "name": g["NAME"], "state": g["USPS"],
                         "lat": g["INTPTLAT"].astype(float), "lon": g["INTPTLONG"].astype(float)})


def pull_county_precip(keep_fips: set[int]) -> pd.DataFrame:
    path = RAW_DIR / "climdiv-pcpncy.txt"
    if not path.exists():
        listing = _get(CLIMDIV_URL).text
        name = sorted(set(re.findall(r"climdiv-pcpncy-v[0-9.]+-[0-9]{8}", listing)))[-1]
        path.write_text(_get(CLIMDIV_URL + name).text, encoding="utf-8")
        (RAW_DIR / "climdiv-pcpncy.source.txt").write_text(CLIMDIV_URL + name, encoding="utf-8")
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            code = line[:11]
            if len(code) < 11 or not code.isdigit():
                continue
            st, cty, year = int(code[:2]), int(code[2:5]), int(code[7:11])
            if st not in CLIMDIV_TO_FIPS or year < 1950 or year > 2025:
                continue
            fips = CLIMDIV_TO_FIPS[st] * 1000 + cty
            if fips not in keep_fips:
                continue
            vals = line[11:].split()
            for m, v in enumerate(vals[:12], start=1):
                x = float(v)
                rows.append((fips, year, m, np.nan if x < -9 else x))
    return pd.DataFrame(rows, columns=["fips", "year", "month", "precip_in"])


def main():
    print("NASS county yields ...", flush=True)
    y = pull_yields()
    y.to_parquet(PROCESSED / "county_crop_yields.parquet", index=False)
    print(f"  {len(y)} yield rows, {y['fips'].nunique()} counties")
    a = pull_acres()
    a.to_csv(PROCESSED / "county_crop_acres.csv", index=False)
    c = pull_centroids()
    c.to_csv(PROCESSED / "county_centroids.csv", index=False)
    keep = set(y["fips"]) | set(a["fips"])
    p = pull_county_precip(keep)
    p.to_parquet(PROCESSED / "county_monthly_precip.parquet", index=False)
    print(f"  county rain: {p['fips'].nunique()} counties, {len(p)} rows; centroids: {len(c)}")


if __name__ == "__main__":
    main()
