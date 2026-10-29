"""Pull PRF actuarial data (rates, county base values, subsidy) for the project's study grids.

Run from the repo root:  python scripts/pull_prf_actuarial.py [--years 2025 2026] [--refresh]

What it does
1. Study grids. Uses data/processed/study_grids.csv if another workstream has written it
   (needs a grid_id column; site/role columns are used if present). Otherwise it locates, for every
   PRF study site in agri_hedge.locations, the PRF grid containing the Kalshi settlement station
   and the grid containing the farm point, by querying the PRF grid map layer that the RMA PRF
   Decision Support Tool (DST) uses (through the DST's public proxy). The county containing each
   point, and every county that overlaps each grid, come from the same map service and the DST
   web API (GetCountiesAndStatesFromGridId).
2. Actuarial Data Master (ADM). PRF (commodity 0088, insurance plan 13 = Rainfall Index) is filed
   with the August 31 contract change date, so the crop-year zip "<year>_ADM_Filing_0831.zip"
   holds its insurance offers and prices; the area rate table A01135 is only in
   "<year>_ADM_YTD.zip". The zips are 0.6-2.7 GB, so instead of downloading them this script reads
   them in place with HTTP range requests (Python's zipfile over a seekable HTTP file) and streams
   only the needed members, keeping rows for our counties/grids:
     A00030 Insurance Offer   commodity, plan, county, intended use, practices, interval code
     A00810 Price             county base value, min/max percent of value, final index (by grid)
     A01130 Area Coverage Lvl grid x coverage level -> area rate ID, published payment factor
     A01135 Area Rate         area rate ID -> premium rate ("Base Rate")
     A00070 Subsidy Percent   plan 13 rows (record category 04): subsidy share by coverage level
     A00470/A00480/A00490/A00500 code tables (intended use, interval, irrigation, organic)
   The filtered extracts are cached under data/raw/prf_actuarial/adm/<year>/ (a few MB), so
   reruns make no network calls unless --refresh is given. Total streamed per crop year is about
   400 MB.
3. Premium subsidy. The subsidy share by coverage level comes from ADM A00070 (plan 13, record
   category 04, coverage type A) for each crop year, and is checked against
   agri_hedge.prf.PREMIUM_SUBSIDY_BY_COVERAGE and the DST ("SubsidyLevel" in GetPricingRates).
4. Writes data/processed/prf_actuarial_study_grids.csv (long format, one row per crop year x
   site x grid role x county x intended use x practice x interval x coverage level).

Downloaded files are treated as data only; nothing downloaded is executed.
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import time
import zipfile
from pathlib import Path

import pandas as pd
import requests

from agri_hedge.config import PROCESSED, RAW
from agri_hedge.locations import STUDY_SITES
from agri_hedge.prf import PREMIUM_SUBSIDY_BY_COVERAGE
from agri_hedge.prf_intervals import CODE_TO_INTERVAL, INTERVAL_CODES

ADM_BASE = "https://pubfs-rma.fpac.usda.gov/pub/References/actuarial_data_master"
DST_API = "https://public-rma.fpac.usda.gov/apps/PrfWebApi"
DST_PROXY = "https://public-rma.fpac.usda.gov/apps/prf/proxy/proxy.ashx?"
GRID_LAYER = "https://pdgis.rm.usda.net/arcgis/rest/services/PRF/PRF_GRID/MapServer/0/query"
COUNTY_LAYER = "https://pdgis.rm.usda.net/arcgis/rest/services/PRF/PRF_GRID/MapServer/1/query"

OUT_DIR = RAW / "prf_actuarial"
ADM_DIR = OUT_DIR / "adm"
GRID_CACHE = OUT_DIR / "grid_lookup.json"
DST_CACHE = OUT_DIR / "dst_subsidy_check.json"
OUT_CSV = PROCESSED / "prf_actuarial_study_grids.csv"

PRF_COMMODITY = "0088"
RI_PLAN = "13"
USE_NAMES = {"007": "grazing", "030": "haying"}
IRR_NAMES = {"002": "irrigated", "003": "non-irrigated", "997": "not specified"}
ORG_NAMES = {"997": "not organic", "001": "certified", "002": "transitional"}

SESSION = requests.Session()
SESSION.headers["User-Agent"] = "ECE473-agri-hedge research (Princeton)"


# ---------------------------------------------------------------------------------------------
# Remote zip access
# ---------------------------------------------------------------------------------------------

class HttpRangeFile(io.RawIOBase):
    """Read-only, seekable file over HTTP using Range requests (server must send Accept-Ranges)."""

    def __init__(self, url: str):
        super().__init__()
        self.url = url
        r = SESSION.head(url, timeout=60)
        r.raise_for_status()
        self.size = int(r.headers["Content-Length"])
        self.pos = 0
        self.n_requests = 0
        self.bytes_read = 0

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=io.SEEK_SET):
        if whence == io.SEEK_SET:
            self.pos = offset
        elif whence == io.SEEK_CUR:
            self.pos += offset
        else:
            self.pos = self.size + offset
        return self.pos

    def readinto(self, buf):
        n = len(buf)
        if n == 0 or self.pos >= self.size:
            return 0
        end = min(self.pos + n, self.size) - 1
        for attempt in range(5):
            try:
                r = SESSION.get(self.url, headers={"Range": f"bytes={self.pos}-{end}"}, timeout=180)
                r.raise_for_status()
                data = r.content
                break
            except requests.RequestException:
                if attempt == 4:
                    raise
                time.sleep(2 * (attempt + 1))
        buf[:len(data)] = data
        self.pos += len(data)
        self.n_requests += 1
        self.bytes_read += len(data)
        return len(data)


def open_remote_zip(url: str) -> tuple[zipfile.ZipFile, HttpRangeFile]:
    raw = HttpRangeFile(url)
    return zipfile.ZipFile(io.BufferedReader(raw, buffer_size=8 << 20)), raw


def stream_filter_member(zf: zipfile.ZipFile, member_suffix: str, out_path: Path,
                         keep: dict[str, set[str]]) -> int:
    """Stream a pipe-delimited ADM member and keep rows where every column in `keep` is in its set."""
    names = [n for n in zf.namelist() if n.endswith(member_suffix)]
    if not names:
        raise FileNotFoundError(f"{member_suffix} not in zip")
    kept = 0
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".part")
    with zf.open(names[0]) as fh, open(tmp, "w", encoding="utf-8", newline="\n") as w:
        txt = io.TextIOWrapper(fh, encoding="latin-1")
        header = txt.readline().rstrip("\r\n")
        cols = header.split("|")
        idx = [(cols.index(c), vals) for c, vals in keep.items()]
        w.write(header + "\n")
        for line in txt:
            parts = line.split("|")
            if all(parts[i] in vals for i, vals in idx):
                w.write(line.rstrip("\r\n") + "\n")
                kept += 1
    tmp.replace(out_path)
    return kept


def read_adm(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, sep="|", dtype=str, keep_default_na=False)


# ---------------------------------------------------------------------------------------------
# Study grids
# ---------------------------------------------------------------------------------------------

def _arcgis_point_query(layer_url: str, lat: float, lon: float, geometry: bool = False) -> dict:
    q = (f"{layer_url}?geometry={lon},{lat}&geometryType=esriGeometryPoint&inSR=4326"
         f"&spatialRel=esriSpatialRelIntersects&outFields=*&returnGeometry={'true' if geometry else 'false'}"
         f"&outSR=4326&f=json")
    r = SESSION.get(DST_PROXY + q, timeout=60)
    r.raise_for_status()
    feats = r.json().get("features", [])
    if not feats:
        raise LookupError(f"no feature at {lat},{lon} in {layer_url}")
    return feats[0]


def grid_counties(grid_id: str) -> list[dict]:
    r = SESSION.get(f"{DST_API}/PrfExternalStates/GetCountiesAndStatesFromGridId",
                    params={"gridId": grid_id, "gridName": grid_id}, timeout=60)
    r.raise_for_status()
    return [{"county_fips": c["StateCode"] + c["CountyCode"], "county_name": c["CountyName"],
             "state_name": c["StateName"]} for c in r.json()["locationData"]]


def lookup_study_grids(refresh: bool = False) -> pd.DataFrame:
    """Grid ID, bounds, point county, and overlapping counties for each site's station and farm points."""
    if GRID_CACHE.exists() and not refresh:
        rows = json.loads(GRID_CACHE.read_text())
    else:
        rows = []
        for site, s in STUDY_SITES.items():
            for role in ("station", "farm"):
                lat, lon = s[f"{role}_lat"], s[f"{role}_lon"]
                g = _arcgis_point_query(GRID_LAYER, lat, lon, geometry=True)
                ring = g["geometry"]["rings"][0]
                c = _arcgis_point_query(COUNTY_LAYER, lat, lon)["attributes"]
                gid = str(g["attributes"]["GRIDCODE"])
                rows.append({
                    "site": site, "grid_role": role, "point_lat": lat, "point_lon": lon,
                    "grid_id": gid,
                    "grid_lon_min": min(p[0] for p in ring), "grid_lon_max": max(p[0] for p in ring),
                    "grid_lat_min": min(p[1] for p in ring), "grid_lat_max": max(p[1] for p in ring),
                    "point_county_fips": c["AnsiStCntyFips"], "point_county_name": c["LONG_NM"],
                    "grid_counties": grid_counties(gid),
                })
                time.sleep(0.2)
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        GRID_CACHE.write_text(json.dumps(rows, indent=1))
    return pd.DataFrame(rows)


def study_grids(refresh: bool = False) -> pd.DataFrame:
    """One row per PRF study site x role (station, farm), cross-checked with study_grids.csv.

    Our own map lookup supplies grid bounds and the county containing each point. If the shared
    data/processed/study_grids.csv exists (written by the index workstream), its grid IDs for the
    PRF study sites must agree with ours; any disagreement is reported. The row-crop contrast site
    (ORD) is excluded because PRF insures pasture, rangeland, and forage only.
    """
    ours = lookup_study_grids(refresh)
    shared = PROCESSED / "study_grids.csv"
    if shared.exists():
        sg = pd.read_csv(shared, dtype=str)
        if {"site", "role", "grid_id"} <= set(sg.columns):
            theirs = {(r.site, r.role): str(r.grid_id).strip() for r in sg.itertuples()}
            for r in ours.itertuples():
                other = theirs.get((r.site, r.grid_role))
                if other is not None and other != r.grid_id:
                    print(f"WARNING: {r.site} {r.grid_role}: our grid {r.grid_id} != study_grids.csv {other}")
            print(f"cross-checked {len(ours)} grids against {shared.name}")
    return ours


# ---------------------------------------------------------------------------------------------
# ADM pulls
# ---------------------------------------------------------------------------------------------

def pull_adm_year(year: int, county_fips: set[str], grid_ids: set[str], refresh: bool = False) -> dict[str, Path]:
    """Stream-filter the ADM members for one crop year; return paths of the cached extracts.

    Each extract is cached separately, so a rerun only streams the members that are missing.
    """
    ydir = ADM_DIR / str(year)
    paths = {t: ydir / f"{year}_{t}_prf_study.txt" for t in ("A00030", "A00810", "A01130", "A01135")}
    refs = {t: ydir / f"{year}_{t}.txt" for t in ("A00070", "A00470", "A00480", "A00490", "A00500")}
    need = lambda p: refresh or not p.exists()  # noqa: E731
    states = {f[:2] for f in county_fips}
    counties = {f[2:] for f in county_fips}
    filing_url = f"{ADM_BASE}/{year}/{year}_ADM_Filing_0831.zip"
    ytd_url = f"{ADM_BASE}/{year}/{year}_ADM_YTD.zip"
    if any(need(paths[t]) for t in ("A00030", "A00810", "A01130")):
        print(f"[{year}] opening {filing_url}")
        zf, raw = open_remote_zip(filing_url)
        if need(paths["A00030"]):
            n = stream_filter_member(zf, "A00030_InsuranceOffer_Filing.txt", paths["A00030"],
                                     {"Commodity Code": {PRF_COMMODITY}, "Insurance Plan Code": {RI_PLAN},
                                      "State Code": states, "County Code": counties})
            offers = read_adm(paths["A00030"])
            offers = offers[(offers["State Code"] + offers["County Code"]).isin(county_fips)]
            offers.to_csv(paths["A00030"], sep="|", index=False)
            print(f"[{year}] A00030: {len(offers)} PRF offers in {len(county_fips)} counties (pre-filter {n})")
        offer_ids = set(read_adm(paths["A00030"])["ADM Insurance Offer ID"])
        for t, suffix in (("A00810", "A00810_Price_Filing.txt"), ("A01130", "A01130_AreaCoverageLevel_Filing.txt")):
            if need(paths[t]):
                n = stream_filter_member(zf, suffix, paths[t],
                                         {"ADM Insurance Offer ID": offer_ids, "Sub County Code": grid_ids})
                print(f"[{year}] {t}: {n} rows")
        print(f"[{year}] streamed {raw.bytes_read / 1e6:.0f} MB from filing zip")
    if need(paths["A01135"]) or any(need(p) for p in refs.values()):
        print(f"[{year}] opening {ytd_url}")
        zy, rawy = open_remote_zip(ytd_url)
        if need(paths["A01135"]):
            rate_ids = set(read_adm(paths["A01130"])["Area Rate ID"])
            n = stream_filter_member(zy, "A01135_AreaRate_YTD.txt", paths["A01135"], {"Area Rate ID": rate_ids})
            print(f"[{year}] A01135: {n} of {len(rate_ids)} area rates found")
        if need(refs["A00070"]):
            stream_filter_member(zy, "A00070_SubsidyPercent_YTD.txt", refs["A00070"],
                                 {"Insurance Plan Code": {RI_PLAN}})
        for t, suffix in (("A00470", "A00470_IntendedUse_YTD.txt"), ("A00480", "A00480_Interval_YTD.txt"),
                          ("A00490", "A00490_IrrigationPractice_YTD.txt"),
                          ("A00500", "A00500_OrganicPractice_YTD.txt")):
            if need(refs[t]):
                stream_filter_member(zy, suffix, refs[t], {})
        print(f"[{year}] streamed {rawy.bytes_read / 1e6:.0f} MB from YTD zip")
    return {**paths, **refs}


FINAL_INDEX_HISTORY = OUT_DIR / "adm_final_index_history.csv"


def pull_final_index_history(years: list[int], grid_ids: set[str], refresh: bool = False) -> pd.DataFrame:
    """Official final grid indices as published in ADM A00810 ("Final Index Value"), by crop year.

    These are the indices RMA actually paid on (NOAA CPC data through crop year 2026). The field
    exists from about crop year 2021 on; earlier ADM layouts do not carry it. Only the A00810
    member of each Filing_0831 zip is streamed (25-60 MB per year). Cached to
    data/raw/prf_actuarial/adm_final_index_history.csv.
    """
    old = pd.read_csv(FINAL_INDEX_HISTORY, dtype={"grid_id": str}) if FINAL_INDEX_HISTORY.exists() else None
    have = set() if old is None or refresh else set(old["crop_year"])
    frames = [] if old is None or refresh else [old]
    for year in years:
        if year in have:
            continue
        ydir = ADM_DIR / str(year)
        path = ydir / f"{year}_A00810_prf_study.txt"
        if not path.exists() or refresh:
            zf, raw = open_remote_zip(f"{ADM_BASE}/{year}/{year}_ADM_Filing_0831.zip")
            stream_filter_member(zf, "A00810_Price_Filing.txt", path,
                                 {"Commodity Code": {PRF_COMMODITY}, "Sub County Code": grid_ids})
            print(f"[{year}] A00810 for final index: streamed {raw.bytes_read / 1e6:.0f} MB")
        p = read_adm(path)
        if "Final Index Value" not in p.columns:
            print(f"[{year}] ADM A00810 has no Final Index Value field; skipped")
            continue
        p = p[p["Final Index Value"] != ""]
        f = (p.groupby(["Sub County Code", "Interval Code"])["Final Index Value"]
             .agg(lambda s: sorted(set(s))).reset_index())
        if (f["Final Index Value"].str.len() > 1).any():
            print(f"WARNING [{year}]: grid/interval with more than one final index value")
        frames.append(pd.DataFrame({
            "crop_year": year, "grid_id": f["Sub County Code"].str.strip(),
            "interval_code": f["Interval Code"].astype(int),
            "interval_name": f["Interval Code"].astype(int).map(CODE_TO_INTERVAL),
            "final_index_adm": f["Final Index Value"].str[0].astype(float) * 100}))
    hist = pd.concat(frames, ignore_index=True).sort_values(["grid_id", "crop_year", "interval_code"])
    hist.to_csv(FINAL_INDEX_HISTORY, index=False, float_format="%.6g")
    return hist


def check_interval_codes(interval_table: Path) -> None:
    """Confirm agri_hedge.prf_intervals codes against ADM A00480 (e.g. 628 = 'APR - MAY INDEX INTERVAL')."""
    t = read_adm(interval_table)
    t = t[t["Interval Code"].astype(int).between(625, 635)]
    month_abbr = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
    for _, row in t.iterrows():
        code = int(row["Interval Code"])
        name = CODE_TO_INTERVAL[code]
        a, b = name.split("-")
        expect = f"{a.upper()}-{b.upper()}"
        if row["Interval Abbreviation"].strip() != expect:
            raise AssertionError(f"interval {code}: ADM says {row['Interval Abbreviation']}, repo says {name}")
        assert month_abbr.index(a.upper()) + 1 == int(row["Interval Start Date"][:2])
    print(f"interval codes 625-635 match ADM A00480 ({interval_table.name})")


def dst_subsidy_check(refresh: bool = False) -> dict:
    """Ask the DST for the subsidy share at each coverage level (DST uses the current insurance year)."""
    if DST_CACHE.exists() and not refresh:
        return json.loads(DST_CACHE.read_text())
    out = {}
    for cov in (70, 75, 80, 85, 90):
        p = dict(intervalType="BiMonthly", irrigationPracticeCode="997", organicPracticeCode="997",
                 intendedUseCode="007", stateCode="48", countyCode="367", productivityFactor=100,
                 insurableInterest=100, insuredAcres=1000, sampleYear=2025,
                 intervalPercentOfValues=json.dumps([0, 0, 0, 50, 0, 0, 50, 0, 0, 0, 0]),
                 coverageLevelPercent=cov, gridId="15429", gridName="15429")
        r = SESSION.get(f"{DST_API}/PrfExternalPricingRates/GetPricingRates", params=p, timeout=60)
        r.raise_for_status()
        out[str(cov)] = r.json()["returnData"]["PricingRateSummary"]["SubsidyLevel"]
        time.sleep(0.2)
    settings = {"retrieved": time.strftime("%Y-%m-%d"), "subsidy_by_coverage_percent": out,
                "note": "DST insurance data year at retrieval: 2027 (page Settings.ReinsuranceYear)"}
    DST_CACHE.write_text(json.dumps(settings, indent=1))
    return settings


# ---------------------------------------------------------------------------------------------
# Build processed table
# ---------------------------------------------------------------------------------------------

def build_year_table(year: int, paths: dict[str, Path]) -> pd.DataFrame:
    offers = read_adm(paths["A00030"])
    price = read_adm(paths["A00810"])
    acl = read_adm(paths["A01130"])
    rate = read_adm(paths["A01135"])
    price_cols = ["ADM Insurance Offer ID", "Sub County Code", "County Base Value",
                  "Minimum Acre Percent", "Maximum Acre Percent", "Expected Index Value", "Final Index Value"]
    m = (acl[["ADM Insurance Offer ID", "Sub County Code", "Coverage Level Percent", "Payment Factor", "Area Rate ID"]]
         .merge(rate[["Area Rate ID", "Base Rate"]], on="Area Rate ID", how="left")
         .merge(price[price_cols], on=["ADM Insurance Offer ID", "Sub County Code"], how="left")
         .merge(offers[["ADM Insurance Offer ID", "State Code", "County Code", "Intended Use Code",
                        "Irrigation Practice Code", "Organic Practice Code", "Interval Code"]],
                on="ADM Insurance Offer ID", how="left"))
    num = lambda s: pd.to_numeric(s.replace("", pd.NA), errors="coerce")
    out = pd.DataFrame({
        "crop_year": year,
        "grid_id": m["Sub County Code"].str.strip(),
        "county_fips": m["State Code"] + m["County Code"],
        "intended_use": m["Intended Use Code"].map(USE_NAMES),
        "irrigation_practice": m["Irrigation Practice Code"].map(IRR_NAMES),
        "organic_practice": m["Organic Practice Code"].map(ORG_NAMES),
        "interval_code": m["Interval Code"].astype(int),
        "coverage_level": num(m["Coverage Level Percent"]),
        "premium_rate": num(m["Base Rate"]),
        "county_base_value_usd_per_acre": num(m["County Base Value"]),
        "min_percent_of_value": num(m["Minimum Acre Percent"]),
        "max_percent_of_value": num(m["Maximum Acre Percent"]),
        "expected_index": num(m["Expected Index Value"]) * 100,
        "final_index_adm": num(m["Final Index Value"]) * 100,
        "payment_factor_adm": num(m["Payment Factor"]),
        "intended_use_code": m["Intended Use Code"],
        "irrigation_practice_code": m["Irrigation Practice Code"],
        "organic_practice_code": m["Organic Practice Code"],
        "adm_insurance_offer_id": m["ADM Insurance Offer ID"],
        "area_rate_id": m["Area Rate ID"],
    })
    out["interval_name"] = out["interval_code"].map(CODE_TO_INTERVAL)
    sub = read_adm(paths["A00070"])
    sub = sub[(sub["Insurance Plan Code"] == RI_PLAN) & (sub["Coverage Type Code"] == "A")]
    adm_sub = {round(float(c), 2): float(v) for c, v in zip(sub["Coverage Level Percent"], sub["Subsidy Percent"])}
    for c, v in adm_sub.items():
        if abs(PREMIUM_SUBSIDY_BY_COVERAGE.get(c, -1) - v) > 1e-9:
            print(f"WARNING [{year}]: ADM subsidy {c:.2f} -> {v} differs from prf.py")
    out["subsidy_rate"] = out["coverage_level"].round(2).map(adm_sub)
    if out["premium_rate"].isna().any():
        print(f"WARNING [{year}]: {out['premium_rate'].isna().sum()} rows without a premium rate")
    return out


# Decision Support Tool probes used as test fixtures: (coverage %, productivity factor %, acres,
# percent of value by interval Jan-Feb..Nov-Dec, sample year, intended use, irrigation, organic,
# state, county, grid). Chosen to exercise odd acres, odd productivity factors, and losses.
DST_PROBES = [
    (85, 113, 333.3, [0, 0, 0, 37, 0, 0, 63, 0, 0, 0, 0], 2020, "007", "997", "997", "48", "367", "15429"),
    (90, 100, 1000, [0, 0, 0, 50, 0, 0, 50, 0, 0, 0, 0], 2020, "007", "997", "997", "48", "367", "15429"),
    (75, 147, 777.7, [0, 0, 0, 0, 30, 0, 40, 0, 30, 0, 0], 2022, "007", "997", "997", "48", "367", "15429"),
    (70, 61, 51.5, [0, 0, 23, 0, 27, 0, 0, 0, 0, 0, 50], 2011, "007", "997", "997", "48", "367", "15429"),
    (90, 150, 245, [0, 0, 0, 60, 0, 0, 40, 0, 0, 0, 0], 2011, "007", "997", "997", "48", "367", "15429"),
    (80, 100, 100, [0, 0, 0, 0, 0, 0, 50, 0, 50, 0, 0], 2011, "007", "997", "997", "48", "497", "15429"),
    (85, 125, 640, [0, 0, 0, 0, 50, 0, 50, 0, 0, 0, 0], 2018, "030", "003", "997", "48", "367", "15429"),
]


def write_test_fixtures(fixture_dir: Path) -> None:
    """Save small, network-free fixtures for tests/test_prf.py.

    dst_pricing_probes.json: DST GetPricingRates inputs and outputs (RMA's own arithmetic).
    adm_payment_factor_sample.csv: published ADM final index and payment factor rows, including
    every row whose unrounded factor ends in 5 at the 4th decimal (tests half-up rounding).
    """
    fixture_dir.mkdir(parents=True, exist_ok=True)
    probes = []
    for cov, pf, acres, ipov, year, use, irr, org, st, co, grid in DST_PROBES:
        p = dict(intervalType="BiMonthly", irrigationPracticeCode=irr, organicPracticeCode=org,
                 intendedUseCode=use, stateCode=st, countyCode=co, productivityFactor=pf,
                 insurableInterest=100, insuredAcres=acres, sampleYear=year,
                 intervalPercentOfValues=json.dumps(ipov), coverageLevelPercent=cov, gridId=grid, gridName=grid)
        r = SESSION.get(f"{DST_API}/PrfExternalPricingRates/GetPricingRates", params=p, timeout=60)
        r.raise_for_status()
        d = r.json()["returnData"]
        rows = [x for x in d["PricingRateRows"] if x["PercentOfValue"] > 0]
        probes.append({"params": p, "PricingRateSummary": d["PricingRateSummary"],
                       "PricingRateRowTotalSummary": d["PricingRateRowTotalSummary"],
                       "PricingRateRows": [{k: x[k] for k in ("IntervalCode", "PercentOfValue", "PolicyProtection",
                                                              "PremiumRate", "TotalPremium", "PremiumSubsidy",
                                                              "ProducerPremium", "PercentOfNormal", "Indemnity")}
                                           for x in rows]})
        time.sleep(0.2)
    meta = {"source": f"{DST_API}/PrfExternalPricingRates/GetPricingRates",
            "retrieved": time.strftime("%Y-%m-%d"),
            "note": "DST insurance data year 2027 at retrieval; PercentOfNormal is the sample-year final index as a fraction"}
    (fixture_dir / "dst_pricing_probes.json").write_text(json.dumps({"meta": meta, "probes": probes}, indent=1))
    act = pd.read_csv(OUT_CSV, dtype={"grid_id": str, "county_fips": str})
    a = act.dropna(subset=["final_index_adm", "payment_factor_adm"]).drop_duplicates(
        ["crop_year", "grid_id", "interval_code", "coverage_level"])
    raw = (a["coverage_level"] * 100 - a["final_index_adm"]).clip(lower=0) / (a["coverage_level"] * 100)
    half = ((raw * 1e4).round(6) % 10 == 5)
    sample = pd.concat([a[half], a[~half & (a["payment_factor_adm"] > 0)].sample(40, random_state=0),
                        a[a["payment_factor_adm"] == 0].sample(10, random_state=0)])
    sample[["crop_year", "grid_id", "interval_code", "coverage_level", "final_index_adm", "payment_factor_adm"]] \
        .sort_values(["crop_year", "grid_id", "interval_code", "coverage_level"]) \
        .to_csv(fixture_dir / "adm_payment_factor_sample.csv", index=False)
    print(f"wrote fixtures to {fixture_dir} ({int(half.sum())} half-way rounding cases)")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--years", nargs="+", type=int, default=[2025, 2026])
    ap.add_argument("--refresh", action="store_true", help="re-download even if cached")
    ap.add_argument("--final-index-years", nargs="*", type=int, default=[2021, 2022, 2023, 2024, 2025, 2026],
                    help="crop years whose ADM final grid indices to cache (raw, for validation)")
    ap.add_argument("--fixtures", action="store_true",
                    help="also (re)write tests/fixtures/b4 DST and ADM fixtures (needs network)")
    args = ap.parse_args(argv)

    grids = study_grids(args.refresh)
    pairs = []  # (site, role, grid_id, county_fips, county_name, is_point_county)
    for _, g in grids.iterrows():
        for c in g["grid_counties"]:
            pairs.append({"site": g["site"], "grid_role": g["grid_role"], "grid_id": g["grid_id"],
                          "county_fips": c["county_fips"],
                          "county_name": f"{c['county_name']} County, {c['state_name']}",
                          "is_point_county": c["county_fips"] == g.get("point_county_fips", "")})
    pairs = pd.DataFrame(pairs)
    print(grids[["site", "grid_role", "grid_id", "point_county_name"]].to_string(index=False))
    county_fips = set(pairs["county_fips"])
    grid_ids = set(pairs["grid_id"])

    sub = dst_subsidy_check(args.refresh)
    for cov, s in sub["subsidy_by_coverage_percent"].items():
        ours = PREMIUM_SUBSIDY_BY_COVERAGE[round(int(cov) / 100, 2)]
        flag = "ok" if abs(ours - s) < 1e-9 else "MISMATCH"
        print(f"subsidy {cov}%: DST {s:.2f}, prf.py {ours:.2f} {flag}")

    tables = []
    for year in args.years:
        paths = pull_adm_year(year, county_fips, grid_ids, args.refresh)
        check_interval_codes(paths["A00480"])
        tables.append(build_year_table(year, paths))
    adm = pd.concat(tables, ignore_index=True)
    out = pairs.merge(adm, on=["grid_id", "county_fips"], how="inner")
    out["source"] = "ADM" + out["crop_year"].astype(str)
    cols = ["crop_year", "site", "grid_role", "grid_id", "county_fips", "county_name", "is_point_county",
            "intended_use", "irrigation_practice", "organic_practice", "interval_code", "interval_name",
            "coverage_level", "premium_rate", "subsidy_rate", "county_base_value_usd_per_acre",
            "min_percent_of_value", "max_percent_of_value", "expected_index", "final_index_adm",
            "payment_factor_adm", "intended_use_code", "irrigation_practice_code", "organic_practice_code",
            "adm_insurance_offer_id", "area_rate_id", "source"]
    out = out[cols].sort_values(["crop_year", "site", "grid_role", "county_fips", "intended_use",
                                 "irrigation_practice", "organic_practice", "coverage_level",
                                 "interval_code"]).reset_index(drop=True)
    missing = pairs[~pairs.set_index(["grid_id", "county_fips"]).index.isin(
        out.set_index(["grid_id", "county_fips"]).index)]
    if len(missing):
        print("WARNING: no ADM rows for these grid/county pairs:\n" + missing.to_string(index=False))
    out.to_csv(OUT_CSV, index=False, float_format="%.6g")
    print(f"wrote {OUT_CSV} ({len(out)} rows, {OUT_CSV.stat().st_size / 1e6:.1f} MB)")
    if args.final_index_years:
        hist = pull_final_index_history(args.final_index_years, grid_ids, args.refresh)
        print(f"cached {len(hist)} official ADM final grid indices -> {FINAL_INDEX_HISTORY}")
    if args.fixtures:
        write_test_fixtures(Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "b4")
    return 0


if __name__ == "__main__":
    sys.exit(main())
