"""R8: pull county-level inputs for the representative farm exposures (data/scenarios/farms.yaml).

Run from the repo root:
    python scripts/r8_pull_county_data.py                # all steps
    python scripts/r8_pull_county_data.py --steps sob adm  # selected steps

Steps (each caches its raw downloads under data/raw/r8/, so reruns are fast and offline-safe):
  sob     RMA Summary of Business state/county/crop files (sobcov_YYYY.zip with policy counts,
          sobtpu_YYYY.zip with type = intended use and practice = index interval). Writes
          derived/prf_sob_county_year.csv, prf_sob_county_use_year.csv, prf_interval_share*.csv,
          prf_coverage_level_mix.csv.
  adm     2026 Actuarial Data Master (ADM) Price table (A00810, field 34 "County Base Value"), plus
          small reference tables. Only the needed members of the 2.7 GB 2026_ADM_YTD.zip are read,
          using HTTP Range requests, and only PRF (commodity 0088) rows for the study counties are
          kept. Writes derived/prf_county_base_values_2026.csv, derived/prf_interval_limits_2026.csv.
  dst     PRF Decision Support Tool public API (public-rma.fpac.usda.gov/apps/PrfWebApi). It serves
          the CURRENT crop year (2027 on 2026-10-29). Caches dst/*.json and writes
          derived/prf_county_base_values_dst2027.csv. Slow (about 3 minutes).
  nass    NASS Quick Stats (web query endpoints used by quickstats.nass.usda.gov; no API key):
          2022 Census of Agriculture county rows, hay price/yield, pasture cash rent, county cattle.
          Writes nass/*.csv and derived/census2022_county_profile.csv.
  ssurgo  NRCS Soil Data Access: area-weighted normal-year range production (component.rsprod_r)
          and NRCS non-irrigated forage/hay yields (cocropyld) by county.
          Writes derived/ssurgo_range_production.csv, ssurgo_top_ecosites.csv, ssurgo_forage_yields.csv.
  validate  Check data/scenarios/farms.yaml against the PRF allocation rules (offline).

Code facts other modules may need:
  - PRF practice codes encode the interval AND the intended use/practice: grazing 625-635,
    haying non-irrigated 525-535, haying irrigated 425-435, organic haying 465/485/565/585 + 0..10.
    The ADM "Interval Code" field is 625-635 for every use (see interval_from_practice()).
  - In sobtpu, a row's net acres = insured acres x percent of value in that interval, so acres sum
    across interval rows to the county total in sobcov.
  - PRF grid id = floor((lat - 20) / 0.25) * 300 + floor((lon + 130) / 0.25) + 1 (matches
    data/processed/study_grids.csv for all farm points).

All downloads are treated as data only (parsed as text, never executed).
"""
from __future__ import annotations

import argparse
import io
import json
import time
import zipfile
from pathlib import Path

import pandas as pd
import requests

from agri_hedge.config import RAW
from agri_hedge.locations import ALL_SITES, STUDY_SITES

R8 = RAW / "r8"
DERIVED = R8 / "derived"
UA = {"User-Agent": "ECE473-agri-hedge research script (Princeton course project)"}

SOB_BASE = "https://pubfs-rma.fpac.usda.gov/pub/Web_Data_Files/Summary_of_Business/state_county_crop"
ADM_YTD_2026 = "https://pubfs-rma.fpac.usda.gov/pub/References/actuarial_data_master/2026/2026_ADM_YTD.zip"
DST_API = "https://public-rma.fpac.usda.gov/apps/PrfWebApi"
QS = "https://quickstats.nass.usda.gov"
SDA = "https://sdmdataaccess.sc.egov.usda.gov/Tabular/post.rest"

PRF_COMMODITY = "0088"
SOB_YEARS = list(range(2015, 2027))  # 2026 is still developing (indemnities incomplete)

# FIPS (state, county) for the 7 PRF counties + the row-crop contrast county.
COUNTIES = {k: (v["farm_fips"][:2], v["farm_fips"][2:]) for k, v in ALL_SITES.items()}


# ----------------------------------------------------------------------------- helpers
def _get(url: str, dest: Path, **kw) -> Path:
    """Download url to dest once (cache)."""
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    r = requests.get(url, headers=UA, timeout=300, **kw)
    r.raise_for_status()
    dest.write_bytes(r.content)
    time.sleep(0.3)
    return dest


def _split_lines(text: str) -> list[str]:
    """RMA SOB files use bare CR line endings; normalise."""
    return [ln for ln in text.replace("\r\n", "\n").replace("\r", "\n").split("\n") if ln.strip()]


class HttpRangeFile(io.RawIOBase):
    """Read-only, seekable file over HTTP Range requests (lets zipfile read one member of a
    multi-GB remote archive without downloading the whole archive)."""

    def __init__(self, url: str):
        self.url = url
        self.session = requests.Session()
        self.size = int(self.session.head(url, headers=UA, timeout=60).headers["Content-Length"])
        self.pos = 0

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, off, whence=0):
        self.pos = {0: off, 1: self.pos + off, 2: self.size + off}[whence]
        return self.pos

    def readinto(self, b):
        if self.pos >= self.size:
            return 0
        end = min(self.pos + len(b), self.size) - 1
        for attempt in range(5):
            try:
                r = self.session.get(self.url, headers={**UA, "Range": f"bytes={self.pos}-{end}"},
                                     timeout=300)
                r.raise_for_status()
                break
            except requests.RequestException:
                time.sleep(2 ** attempt)
        else:
            raise IOError(f"range read failed at {self.pos}")
        data = r.content
        b[: len(data)] = data
        self.pos += len(data)
        return len(data)


# ----------------------------------------------------------------------------- SOB
SOBCOV_COLS = ["year", "state_code", "state_abbr", "county_code", "county_name", "commodity_code",
               "commodity_name", "plan_code", "plan_abbr", "coverage_category", "delivery_type",
               "coverage_level", "policies_sold", "policies_earning", "policies_indemnified",
               "units_earning", "units_indemnified", "quantity_type", "net_acres",
               "endorsed_acres", "liability", "total_premium", "subsidy", "state_private_subsidy",
               "additional_subsidy", "efa_discount", "indemnity", "loss_ratio"]
SOBTPU_COLS = ["year", "state_code", "state_name", "state_abbr", "county_code", "county_name",
               "commodity_code", "commodity_name", "plan_code", "plan_abbr", "coverage_type",
               "coverage_level", "delivery_id", "type_code", "type_name", "practice_code",
               "practice_name", "unit_structure_code", "unit_structure_name", "net_acres",
               "reporting_level_type", "liability", "total_premium", "subsidy", "indemnity",
               "loss_ratio", "endorsed_acres"]


def _read_sob_zip(path: Path, cols: list[str]) -> pd.DataFrame:
    """Parse the PRF rows for our counties from one SOB zip."""
    z = zipfile.ZipFile(path)
    text = z.read(z.namelist()[0]).decode("latin-1")
    keep = {(s, c) for s, c in COUNTIES.values()}
    rows = []
    for ln in _split_lines(text):
        f = [x.strip() for x in ln.split("|")]
        if len(f) < len(cols):
            continue
        rec = dict(zip(cols, f))
        # RMA rolls a county's small commodities into "All Other Crops" (9999) for
        # confidentiality; keep the Rainfall Index plan (13) part of it, flagged as masked.
        masked = rec["commodity_code"] == "9999" and rec["plan_code"] == "13"
        if rec["commodity_code"] != PRF_COMMODITY and not masked:
            continue
        rec["masked_ri"] = masked
        if (rec["state_code"].zfill(2), rec["county_code"].zfill(3)) not in keep:
            continue
        rows.append(rec)
    df = pd.DataFrame(rows, columns=cols + ["masked_ri"])
    num = [c for c in cols if c in ("coverage_level", "policies_sold", "policies_earning",
                                    "policies_indemnified", "units_earning", "units_indemnified",
                                    "net_acres", "endorsed_acres", "liability", "total_premium",
                                    "subsidy", "state_private_subsidy", "additional_subsidy",
                                    "efa_discount", "indemnity", "loss_ratio")]
    for c in num:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["fips"] = df["state_code"].str.zfill(2) + df["county_code"].str.zfill(3)
    df["year"] = df["year"].astype(int)
    return df


def interval_from_practice(code: str) -> str | None:
    """Map a PRF SOB/ADM practice code to an interval name. Grazing uses 625-635, haying
    non-irrigated 525-535, haying irrigated 425-435, organic variants 465/485/565/585 + 0..10."""
    from agri_hedge.prf_intervals import INTERVAL_NAMES
    try:
        p = int(code)
    except ValueError:
        return None
    for base in (625, 525, 425, 465, 485, 565, 585):
        if base <= p <= base + 10:
            return INTERVAL_NAMES[p - base]
    return None


def step_sob() -> None:
    """Download SOB files and summarise PRF participation for the study counties."""
    out = R8 / "sob"
    cov, tpu = [], []
    for y in SOB_YEARS:
        cov.append(_read_sob_zip(_get(f"{SOB_BASE}/sobcov_{y}.zip", out / f"sobcov_{y}.zip"), SOBCOV_COLS))
        tpu.append(_read_sob_zip(_get(f"{SOB_BASE}/sobtpu_{y}.zip", out / f"sobtpu_{y}.zip"), SOBTPU_COLS))
    cov = pd.concat(cov, ignore_index=True)
    tpu = pd.concat(tpu, ignore_index=True)
    DERIVED.mkdir(parents=True, exist_ok=True)
    cov.to_csv(DERIVED / "prf_sob_cov_rows.csv", index=False)
    tpu.to_csv(DERIVED / "prf_sob_tpu_rows.csv", index=False)

    # County-year totals (policies only exist in sobcov). Policy counts can double count a
    # policy holding several coverage levels only if it is split; in sobcov each row is a
    # coverage level, and a PRF policy has one coverage level per crop/county, so summing is fine.
    # Use explicit PRF rows when the county-year has them; otherwise fall back to the masked
    # Rainfall Index rows (flagged; these may also contain Annual Forage or Apiculture).
    has_prf = cov[~cov.masked_ri].groupby(["fips", "year"]).size().rename("n").reset_index()
    cov = cov.merge(has_prf, on=["fips", "year"], how="left")
    cov = cov[(~cov.masked_ri) | cov["n"].isna()].drop(columns="n")
    g = cov.groupby(["fips", "county_name", "state_abbr", "year", "masked_ri"], as_index=False)[
        ["policies_sold", "policies_earning", "policies_indemnified", "net_acres", "liability",
         "total_premium", "subsidy", "indemnity"]].sum()
    g["loss_ratio"] = g["indemnity"] / g["total_premium"]
    g["subsidy_share"] = g["subsidy"] / g["total_premium"]
    g.to_csv(DERIVED / "prf_sob_county_year.csv", index=False)

    # Coverage-level mix (acres by coverage level, buy-up only), pooled over years.
    cl = cov[cov.coverage_category == "A"].groupby(["fips", "coverage_level"], as_index=False)["net_acres"].sum()
    cl["share"] = cl["net_acres"] / cl.groupby("fips")["net_acres"].transform("sum")
    cl.to_csv(DERIVED / "prf_coverage_level_mix.csv", index=False)

    # Intended use split. In sobtpu each PRF row is one index-interval unit, and its net acres
    # are the insured acres times the percent of value placed in that interval (check: summing
    # the interval rows reproduces the sobcov county acreage). So acres, liability, premium and
    # indemnity are all additive across interval rows.
    tpu = tpu[~tpu.masked_ri].copy()  # masked rows have no PRF type/practice detail
    tpu["interval"] = tpu["practice_code"].map(interval_from_practice)
    tpu["use"] = tpu["type_name"]
    tpu["irrigated"] = tpu["practice_name"].str.contains(r"\(Irr", regex=True)
    u = tpu.groupby(["fips", "year", "use"], as_index=False)[
        ["net_acres", "liability", "total_premium", "subsidy", "indemnity"]].sum()
    u["liability_per_acre"] = u["liability"] / u["net_acres"]
    u["loss_ratio"] = u["indemnity"] / u["total_premium"]
    u.to_csv(DERIVED / "prf_sob_county_use_year.csv", index=False)

    # Interval choice: share of liability placed in each interval, by county and intended use.
    iv = tpu[tpu["interval"].notna()]
    s = iv.groupby(["fips", "use", "interval"], as_index=False)[["liability", "net_acres"]].sum()
    s["liability_share"] = s["liability"] / s.groupby(["fips", "use"])["liability"].transform("sum")
    s.to_csv(DERIVED / "prf_interval_share.csv", index=False)
    s2 = iv[iv.year >= 2021].groupby(["fips", "use", "interval"], as_index=False)[["liability", "net_acres"]].sum()
    s2["liability_share"] = s2["liability"] / s2.groupby(["fips", "use"])["liability"].transform("sum")
    s2.to_csv(DERIVED / "prf_interval_share_2021_2025.csv", index=False)
    print("sob: wrote", sorted(p.name for p in DERIVED.glob("prf_*.csv")))


# ----------------------------------------------------------------------------- ADM
ADM_MEMBERS = {
    "price": "2026_A00810_Price_YTD.txt",
    "interval": "2026_A00480_Interval_YTD.txt",
    "intended_use": "2026_A00470_IntendedUse_YTD.txt",
    "practice": "2026_A00510_Practice_YTD.txt",
    "type": "2026_A00540_Type_YTD.txt",
    "statement": "2026_A01210_Statement_YTD.txt",
    "subsidy": "2026_A00070_SubsidyPercent_YTD.txt",
}


def step_adm() -> None:
    """Range-read selected members of the 2026 ADM YTD zip; keep PRF rows of the Price table."""
    out = R8 / "adm"
    out.mkdir(parents=True, exist_ok=True)
    price_out = out / "2026_A00810_Price_PRF.txt"
    need = {k: m for k, m in ADM_MEMBERS.items()
            if not (out / (m if k != "price" else price_out.name)).exists()}
    keep = set(COUNTIES.values())
    if need:
        f = io.BufferedReader(HttpRangeFile(ADM_YTD_2026), buffer_size=16 << 20)
        z = zipfile.ZipFile(f)
        for k, m in need.items():
            print("adm: reading", m)
            if k == "price":
                with z.open(m) as src, open(price_out, "w", encoding="utf-8", newline="") as dst:
                    header = None
                    for raw in io.TextIOWrapper(src, encoding="latin-1", newline=""):
                        if header is None:
                            header = raw
                            dst.write(raw.rstrip("\r\n") + "\n")
                            continue
                        f = raw.split("|")
                        # keep PRF rows for the study counties only (fields 6, 8, 9: commodity,
                        # state, county); the all-county PRF table is ~450 MB
                        if f[5] == PRF_COMMODITY and (f[7], f[8]) in keep:
                            dst.write(raw.rstrip("\r\n") + "\n")
            else:
                (out / m).write_bytes(z.read(m))
    _summarise_adm(out, price_out)


def _summarise_adm(out: Path, price_out: Path) -> None:
    DERIVED.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(price_out, sep="|", dtype=str)
    df.columns = [c.strip() for c in df.columns]
    df["fips"] = df["State Code"].str.zfill(2) + df["County Code"].str.zfill(3)
    keep = {s + c for s, c in COUNTIES.values()}
    sub = df[df["fips"].isin(keep)].copy()
    sub.to_csv(DERIVED / "adm2026_price_prf_study_counties.csv", index=False)
    for c in ("County Base Value", "Minimum Acre Percent", "Maximum Acre Percent"):
        sub[c] = pd.to_numeric(sub[c], errors="coerce")
    cbv = (sub.groupby(["fips", "Intended Use Code", "Irrigation Practice Code", "Organic Practice Code"],
                       as_index=False)["County Base Value"].agg(["min", "max", "count"]))
    cbv.to_csv(DERIVED / "prf_county_base_values_2026.csv", index=False)
    lim = (sub.groupby(["fips", "Intended Use Code", "Irrigation Practice Code", "Organic Practice Code",
                        "Interval Code"], as_index=False)[["Minimum Acre Percent", "Maximum Acre Percent"]].first())
    lim.to_csv(DERIVED / "prf_interval_limits_2026.csv", index=False)
    print("adm: base values\n", cbv.to_string())


# ----------------------------------------------------------------------------- DST (2027)
def dst_pricing(state: str, county: str, grid: int, use: str, ipov: list[float], coverage: int = 90,
                pf: int = 100, acres: float = 100.0, irrigation: str = "997", organic: str = "997",
                sample_year: int = 2025) -> dict:
    """Call the PRF Decision Support Tool pricing endpoint (current crop year).

    use: '007' grazing or '030' haying. irrigation: '997' (grazing: not applicable), '002'
    irrigated, '003' non-irrigated. ipov: 11 percents (Jan-Feb ... Nov-Dec) summing to 100.
    """
    params = {"intervalType": "BiMonthly", "irrigationPracticeCode": irrigation,
              "organicPracticeCode": organic, "intendedUseCode": use, "stateCode": state,
              "countyCode": county, "productivityFactor": pf, "insurableInterest": 100,
              "insuredAcres": acres, "sampleYear": sample_year,
              "intervalPercentOfValues": json.dumps(ipov), "coverageLevelPercent": coverage,
              "gridId": grid, "gridName": str(grid)}
    r = requests.get(f"{DST_API}/PrfExternalPricingRates/GetPricingRates", params=params,
                     headers=UA, timeout=120)
    r.raise_for_status()
    time.sleep(0.3)
    return r.json()


def dst_grids(state: str, county: str) -> list[int]:
    r = requests.get(f"{DST_API}/PrfExternalStates/GetSubCountiesByCountyAndState",
                     params={"stateCode": state, "countyCode": county}, headers=UA, timeout=60)
    r.raise_for_status()
    return [g["NoaaGridId"] for g in r.json()["subCounties"]]


def dst_max_acre_pct(state: str, county: str, grid: int, use: str, irrigation: str = "997") -> dict:
    r = requests.get(f"{DST_API}/PrfExternalMaxAcrePercentage/GetMaxAcrePercentage",
                     params={"intervalType": "BiMonthly", "irrigationPracticeCode": irrigation,
                             "organicPracticeCode": "997", "intendedUseCode": use, "stateCode": state,
                             "countyCode": county, "gridId": grid, "gridName": str(grid)},
                     headers=UA, timeout=60)
    r.raise_for_status()
    return r.json()


def step_dst() -> None:
    """Record 2027 county base values (DST) and the interval percent limits for each county."""
    out = R8 / "dst"
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    flat = [0, 0, 0, 50, 0, 50, 0, 0, 0, 0, 0]  # any valid allocation; base value does not depend on it
    for site, (st, co) in COUNTIES.items():
        if site not in STUDY_SITES:
            continue
        cache = out / f"grids_{st}{co}.json"
        if not cache.exists():
            cache.write_text(json.dumps(dst_grids(st, co)))
        grids = json.loads(cache.read_text())
        for use, irr in (("007", "997"), ("030", "003")):
            pc = out / f"pricing_{st}{co}_{use}_{irr}_{grids[0]}.json"
            if not pc.exists():
                pc.write_text(json.dumps(dst_pricing(st, co, grids[0], use, flat, irrigation=irr)))
            d = json.loads(pc.read_text())
            mc = out / f"maxpct_{st}{co}_{use}_{irr}_{grids[0]}.json"
            if not mc.exists():
                try:
                    mc.write_text(json.dumps(dst_max_acre_pct(st, co, grids[0], use, irr)))
                except requests.RequestException as e:
                    mc.write_text(json.dumps({"error": str(e)}))
            summ = d.get("returnData", {}).get("PricingRateSummary", {}) if isinstance(d, dict) else {}
            rows.append({"site": site, "fips": st + co, "intended_use": use, "irrigation": irr,
                         "grid_used": grids[0], "n_grids_in_county": len(grids),
                         "county_base_value_2027": summ.get("CountyBaseValue"),
                         "subsidy_level_90": summ.get("SubsidyLevel"),
                         "raw": "" if summ else json.dumps(d)[:300]})
    DERIVED.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(DERIVED / "prf_county_base_values_dst2027.csv", index=False)
    print(pd.DataFrame(rows).drop(columns="raw").to_string())


# ----------------------------------------------------------------------------- NASS Quick Stats
STATE_NAMES = {"48": "TEXAS", "40": "OKLAHOMA", "29": "MISSOURI", "08": "COLORADO",
               "35": "NEW MEXICO", "12": "FLORIDA", "17": "ILLINOIS"}


def qs_query(params: list[tuple[str, str]], dest: Path) -> pd.DataFrame:
    """Run one Quick Stats query through the public web endpoints (/row_counts, /uuid/encode,
    /data/spreadsheet/<uuid>.csv), the same calls the Quick Stats web page makes. Cached."""
    if not dest.exists():
        s = requests.Session()
        s.headers.update(UA)
        s.get(QS + "/", timeout=60)
        n = s.post(QS + "/row_counts", data=params, timeout=300).json()
        if n["rowcnt"] > 50000:
            raise ValueError(f"query too large: {n}")
        uuid = s.post(QS + "/uuid/encode", data=params, timeout=300).json()
        r = s.get(f"{QS}/data/spreadsheet/{uuid}.csv", timeout=300)
        r.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(r.content)
        time.sleep(1.0)
    return pd.read_csv(dest, dtype=str)


def _num(v: str) -> float | None:
    try:
        return float(str(v).replace(",", "").strip())
    except ValueError:
        return None  # (D) withheld, (Z) less than half unit, (NA)


# Census items for the county profile table: short label -> (Data Item, Domain Category)
CENSUS_ITEMS = {
    "farms": ("FARM OPERATIONS - NUMBER OF OPERATIONS", "NOT SPECIFIED"),
    "land_in_farms_ac": ("FARM OPERATIONS - ACRES OPERATED", "NOT SPECIFIED"),
    "avg_farm_size_ac": ("FARM OPERATIONS - AREA OPERATED, MEASURED IN ACRES / OPERATION", "NOT SPECIFIED"),
    "median_farm_size_ac": ("FARM OPERATIONS - AREA OPERATED, MEASURED IN ACRES / OPERATION, MEDIAN", "NOT SPECIFIED"),
    "pasture_range_ac": ("AG LAND, PASTURELAND, (EXCL CROPLAND & WOODLAND) - ACRES", "NOT SPECIFIED"),
    "pasture_range_ops": ("AG LAND, PASTURELAND, (EXCL CROPLAND & WOODLAND) - NUMBER OF OPERATIONS", "NOT SPECIFIED"),
    "cropland_pastured_ac": ("AG LAND, CROPLAND, PASTURED ONLY - ACRES", "NOT SPECIFIED"),
    "woodland_pastured_ac": ("AG LAND, WOODLAND, PASTURED - ACRES", "NOT SPECIFIED"),
    "all_pasture_ac": ("AG LAND, PASTURELAND - ACRES", "NOT SPECIFIED"),
    "hay_haylage_ac": ("HAY & HAYLAGE - ACRES HARVESTED", "NOT SPECIFIED"),
    "hay_ac": ("HAY - ACRES HARVESTED", "NOT SPECIFIED"),
    "hay_tons": ("HAY - PRODUCTION, MEASURED IN TONS", "NOT SPECIFIED"),
    "hay_alfalfa_ac": ("HAY, ALFALFA - ACRES HARVESTED", "NOT SPECIFIED"),
    "hay_excl_alfalfa_ac": ("HAY, (EXCL ALFALFA) - ACRES HARVESTED", "NOT SPECIFIED"),
    "hay_irrigated_ac": ("HAY, IRRIGATED - ACRES HARVESTED", "NOT SPECIFIED"),
    "hay_ops": ("HAY - OPERATIONS WITH AREA HARVESTED", "NOT SPECIFIED"),
    "cattle_head": ("CATTLE, INCL CALVES - INVENTORY", "NOT SPECIFIED"),
    "cattle_ops": ("CATTLE, INCL CALVES - OPERATIONS WITH INVENTORY", "NOT SPECIFIED"),
    "beef_cows_head": ("CATTLE, COWS, BEEF - INVENTORY", "NOT SPECIFIED"),
    "beef_cow_ops": ("CATTLE, COWS, BEEF - OPERATIONS WITH INVENTORY", "NOT SPECIFIED"),
    "livestock_sales_usd": ("ANIMAL TOTALS, INCL PRODUCTS - SALES, MEASURED IN $", "NOT SPECIFIED"),
    "cattle_sales_usd": ("CATTLE, INCL CALVES - SALES, MEASURED IN $", "NOT SPECIFIED"),
    "crop_sales_usd": ("CROP TOTALS - SALES, MEASURED IN $", "NOT SPECIFIED"),
    "all_sales_usd": ("COMMODITY TOTALS - SALES, MEASURED IN $", "NOT SPECIFIED"),
    "corn_grain_ac": ("CORN, GRAIN - ACRES HARVESTED", "NOT SPECIFIED"),
    "soy_ac": ("SOYBEANS - ACRES HARVESTED", "NOT SPECIFIED"),
}


def step_nass() -> None:
    """2022 Census county rows + survey hay price, hay yield, pasture cash rent."""
    out = R8 / "nass"
    profile = []
    for site, (st, co) in COUNTIES.items():
        name = ALL_SITES[site]["farm_county"].split(" County")[0].upper()
        df = qs_query([("source_desc", "CENSUS"), ("year", "2022"), ("agg_level_desc", "COUNTY"),
                       ("state_name", STATE_NAMES[st]), ("county_name", name)],
                      out / f"census2022_{st}{co}.csv")
        rec = {"site": site, "fips": st + co, "county": ALL_SITES[site]["farm_county"]}
        for k, (item, dom) in CENSUS_ITEMS.items():
            m = df[(df["Data Item"] == item) & (df["Domain Category"] == dom)]
            rec[k] = m["Value"].iloc[0].strip() if len(m) else ""
        # beef cow herd-size distribution
        for item, tag in (("CATTLE, COWS, BEEF - OPERATIONS WITH INVENTORY", "beefcow_ops_"),
                          ("CATTLE, COWS, BEEF - INVENTORY", "beefcow_head_")):
            bc = df[(df["Data Item"] == item) & (df["Domain"] == "INVENTORY OF BEEF COWS")]
            for _, r in bc.iterrows():
                rec[tag + r["Domain Category"].split(": ")[1].strip("()")] = r["Value"].strip()
        profile.append(rec)
    DERIVED.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(profile).to_csv(DERIVED / "census2022_county_profile.csv", index=False)

    states = [STATE_NAMES[s] for s in sorted({st for st, _ in COUNTIES.values()})]
    sp = [("source_desc", "SURVEY"), ("commodity_desc", "HAY"), ("statisticcat_desc", "PRICE RECEIVED"),
          ("agg_level_desc", "STATE"), ("year", "2023"), ("year", "2024"), ("year", "2025")]
    sp += [("state_name", s) for s in states] + [("state_name", "US TOTAL")]
    qs_query(sp, out / "survey_hay_price_state_2023_2025.csv")
    sp = [("source_desc", "SURVEY"), ("commodity_desc", "HAY"), ("statisticcat_desc", "PRICE RECEIVED"),
          ("agg_level_desc", "NATIONAL"), ("year", "2025")]
    qs_query(sp, out / "survey_hay_price_us_2025.csv")
    yp = [("source_desc", "SURVEY"), ("commodity_desc", "HAY"), ("statisticcat_desc", "YIELD"),
          ("agg_level_desc", "STATE")] + [("year", str(y)) for y in range(2016, 2026)]
    yp += [("state_name", s) for s in states]
    qs_query(yp, out / "survey_hay_yield_state_2016_2025.csv")
    yc = [("source_desc", "SURVEY"), ("commodity_desc", "HAY"), ("statisticcat_desc", "YIELD"),
          ("agg_level_desc", "COUNTY")] + [("year", str(y)) for y in range(2010, 2026)]
    yc += [("state_name", s) for s in states]
    qs_query(yc, out / "survey_hay_yield_county_2010_2025.csv")
    cp = [("source_desc", "SURVEY"), ("commodity_desc", "CATTLE"), ("statisticcat_desc", "INVENTORY"),
          ("agg_level_desc", "COUNTY")] + [("year", str(y)) for y in (2022, 2023, 2024, 2025, 2026)]
    cp += [("state_name", s) for s in states]
    qs_query(cp, out / "survey_cattle_inventory_county_2022_2026.csv")
    rp = [("source_desc", "SURVEY"), ("commodity_desc", "RENT"), ("agg_level_desc", "COUNTY")]
    rp += [("year", str(y)) for y in (2021, 2022, 2023, 2024, 2025)] + [("state_name", s) for s in states]
    qs_query(rp, out / "survey_rent_county_2021_2025.csv")
    rs = [("source_desc", "SURVEY"), ("commodity_desc", "RENT"), ("agg_level_desc", "STATE")]
    rs += [("year", str(y)) for y in (2023, 2024, 2025)] + [("state_name", s) for s in states]
    qs_query(rs, out / "survey_rent_state_2023_2025.csv")
    print("nass: wrote", sorted(p.name for p in out.glob("*.csv")))


# ----------------------------------------------------------------------------- SSURGO
# SSURGO laoverlap.areasymbol for a county is state postal code + county FIPS, e.g. "TX367".
STATE_ABBR = {"48": "TX", "40": "OK", "29": "MO", "08": "CO", "35": "NM", "12": "FL", "17": "IL"}


def sda(query: str) -> list[list[str]]:
    r = requests.post(SDA, json={"query": query, "format": "JSON+COLUMNNAME"}, headers=UA, timeout=300)
    r.raise_for_status()
    time.sleep(0.5)
    return r.json().get("Table", [])


def step_ssurgo() -> None:
    """Area-weighted NRCS normal-year range production and forage/hay yields per county."""
    out = R8 / "ssurgo"
    out.mkdir(parents=True, exist_ok=True)
    prod_rows, crop_rows, eco_rows = [], [], []
    for site, (st, co) in COUNTIES.items():
        cache = out / f"components_{st}{co}.json"
        if not cache.exists():
            q = f"""
            SELECT mao.areaovacres AS mu_acres_in_county, c.cokey, c.comppct_r, c.compname, c.majcompflag,
                   c.rsprod_l, c.rsprod_r, c.rsprod_h, ce.ecoclassid, ce.ecoclassname, mu.mukey
            FROM laoverlap la
            JOIN muaoverlap mao ON mao.lareaovkey = la.lareaovkey
            JOIN mapunit mu ON mu.mukey = mao.mukey
            JOIN component c ON c.mukey = mu.mukey
            LEFT JOIN coecoclass ce ON ce.cokey = c.cokey AND ce.ecoclasstypename LIKE 'NRCS%Site'
            WHERE la.areatypename = 'County or Parish' AND la.areasymbol = '{STATE_ABBR[st]}{co}'
            """
            cache.write_text(json.dumps(sda(q)))
        t = json.loads(cache.read_text())
        df = pd.DataFrame(t[1:], columns=t[0]) if t else pd.DataFrame()
        for c in ("mu_acres_in_county", "comppct_r", "rsprod_l", "rsprod_r", "rsprod_h"):
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df = df.drop_duplicates(subset=["mukey", "cokey"])
        df["comp_acres"] = df["mu_acres_in_county"] * df["comppct_r"] / 100.0
        has = df[df["rsprod_r"].notna() & (df["rsprod_r"] > 0)]
        w = has["comp_acres"]
        rec = {"site": site, "fips": st + co, "county_soil_acres": df.drop_duplicates("mukey")["mu_acres_in_county"].sum(),
               "acres_with_range_prod": w.sum()}
        for c in ("rsprod_l", "rsprod_r", "rsprod_h"):
            rec[c + "_wmean_lb_ac"] = (has[c] * w).sum() / w.sum() if w.sum() > 0 else None
        prod_rows.append(rec)
        eco = (df[df["ecoclassid"].notna()].groupby(["ecoclassid", "ecoclassname"], as_index=False)["comp_acres"].sum()
               .sort_values("comp_acres", ascending=False).head(8))
        eco["site"] = site
        e = df[df["ecoclassid"].notna() & df["rsprod_r"].notna()].copy()
        e["w"] = e["rsprod_r"] * e["comp_acres"]
        ep = e.groupby("ecoclassid")["w"].sum() / e.groupby("ecoclassid")["comp_acres"].sum()
        eco["rsprod_r_wmean"] = eco["ecoclassid"].map(ep)
        eco_rows.append(eco)

        cc = out / f"cropyld_{st}{co}.json"
        if not cc.exists():
            q = f"""
            SELECT mao.areaovacres AS mu_acres_in_county, c.cokey, c.comppct_r, mu.mukey, y.cropname, y.yldunits,
                   y.nonirryield_r, y.irryield_r
            FROM laoverlap la
            JOIN muaoverlap mao ON mao.lareaovkey = la.lareaovkey
            JOIN mapunit mu ON mu.mukey = mao.mukey
            JOIN component c ON c.mukey = mu.mukey
            JOIN cocropyld y ON y.cokey = c.cokey
            WHERE la.areatypename = 'County or Parish' AND la.areasymbol = '{STATE_ABBR[st]}{co}'
            """
            cc.write_text(json.dumps(sda(q)))
        t = json.loads(cc.read_text())
        y = pd.DataFrame(t[1:], columns=t[0]) if t else pd.DataFrame(
            columns=["mu_acres_in_county", "cokey", "comppct_r", "mukey", "cropname", "yldunits", "nonirryield_r", "irryield_r"])
        for c in ("mu_acres_in_county", "comppct_r", "nonirryield_r"):
            y[c] = pd.to_numeric(y[c], errors="coerce")
        y = y.drop_duplicates(subset=["cokey", "cropname", "yldunits"])
        y["comp_acres"] = y["mu_acres_in_county"] * y["comppct_r"] / 100.0
        y = y[y["nonirryield_r"].notna()]
        if len(y):
            y["w"] = y["nonirryield_r"] * y["comp_acres"]
            g = y.groupby(["cropname", "yldunits"], as_index=False)[["comp_acres", "w"]].sum()
            g["nonirr_yield_wmean"] = g["w"] / g["comp_acres"]
            g = g.rename(columns={"comp_acres": "acres_rated"}).drop(columns="w")
            g["site"] = site
            crop_rows.append(g)
    DERIVED.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(prod_rows).to_csv(DERIVED / "ssurgo_range_production.csv", index=False)
    pd.concat(eco_rows).to_csv(DERIVED / "ssurgo_top_ecosites.csv", index=False)
    if crop_rows:
        pd.concat(crop_rows).to_csv(DERIVED / "ssurgo_forage_yields.csv", index=False)
    print(pd.DataFrame(prod_rows).to_string())


# ----------------------------------------------------------------------------- farms.yaml checks
# Max percent of value per interval, crop year 2026 (ADM 2026 Price table, fields 51-52, checked
# for every grid of the study counties). Min is 10% everywhere (26-RI-PRF sec. 2(a)).
MAX_PCT_2026 = {"48": 0.50, "35": 0.50, "12": 0.50, "40": 0.60, "29": 0.60, "08": 0.60, "17": 0.60}
MIN_PCT = 0.10
JAN_FEB_MAX_2027 = 0.25  # PRF Decision Support Tool, crop year 2027, all study counties
COVERAGE_LEVELS = (0.70, 0.75, 0.80, 0.85, 0.90)


def load_farms(path: Path | None = None) -> list[dict]:
    """Load data/scenarios/farms.yaml as a list of farm dicts."""
    import yaml
    from agri_hedge.config import SCENARIOS
    path = path or SCENARIOS / "farms.yaml"
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))["farms"]


def policy_protection(farm: dict) -> float:
    """Total policy protection ($) = acres x county base value x productivity factor x coverage."""
    return (farm["insured_acres"] * farm["county_base_value_usd_per_acre"]
            * farm["productivity_factor"] * farm["coverage_level"])


def validate_farm(farm: dict, base_values: pd.DataFrame | None = None) -> list[str]:
    """Return a list of PRF-rule violations for one farm (empty list = valid).

    Rules: 26-RI-PRF Crop Provisions sec. 2(a) (more than one interval, >= 10% each, max from the
    Special Provisions), 2(b) (no month in two selected intervals), 5(a) (coverage 70-90%,
    productivity factor 60-150%); handbook FCIC-18150 para. 14 (shares sum to 100%).
    """
    from itertools import combinations
    from agri_hedge.prf_intervals import INTERVAL_NAMES, overlaps
    p = []
    if farm["site"] not in STUDY_SITES:
        p.append("site not in STUDY_SITES")
    elif STUDY_SITES[farm["site"]]["farm_fips"] != farm["fips"]:
        p.append("fips does not match site")
    if farm["intended_use"] not in ("haying", "grazing"):
        p.append("intended_use must be haying or grazing")
    if round(farm["coverage_level"], 2) not in COVERAGE_LEVELS:
        p.append("coverage_level not in 70-90% by 5")
    pf = farm["productivity_factor"]
    if not (0.60 - 1e-9 <= pf <= 1.50 + 1e-9) or abs(round(pf * 100) - pf * 100) > 1e-6:
        p.append("productivity_factor must be 0.60-1.50 in 0.01 steps")
    alloc = farm["interval_allocation"]
    bad = [k for k in alloc if k not in INTERVAL_NAMES]
    if bad:
        p.append(f"unknown interval names {bad}")
        return p
    if len(alloc) < 2:
        p.append("need at least two intervals")
    if abs(sum(alloc.values()) - 1.0) > 1e-9:
        p.append(f"allocation sums to {sum(alloc.values())}")
    mx = MAX_PCT_2026[farm["fips"][:2]]
    for k, v in alloc.items():
        if v < MIN_PCT - 1e-9 or v > mx + 1e-9:
            p.append(f"{k}={v} outside [{MIN_PCT}, {mx}]")
        if k == "Jan-Feb" and v > JAN_FEB_MAX_2027 + 1e-9:
            p.append("Jan-Feb above the 2027 25% cap")
    for a, b in combinations(alloc, 2):
        if overlaps(a, b):
            p.append(f"{a} and {b} share a month")
    if base_values is not None:
        use = "007" if farm["intended_use"] == "grazing" else "030"
        irr = "997" if use == "007" else ("002" if farm["irrigation_practice"] == "irrigated" else "003")
        org = "001" if farm["organic"] else "997"
        m = base_values[(base_values["fips"] == farm["fips"]) & (base_values["Intended Use Code"] == use)
                        & (base_values["Irrigation Practice Code"] == irr)
                        & (base_values["Organic Practice Code"] == org)]
        if len(m) and abs(float(m["min"].iloc[0]) - farm["county_base_value_usd_per_acre"]) > 1e-6:
            p.append(f"county base value {farm['county_base_value_usd_per_acre']} != ADM 2026 {m['min'].iloc[0]}")
    return p


def step_validate() -> None:
    """Check every farm in farms.yaml against the PRF rules and print a protection summary."""
    bv_path = DERIVED / "prf_county_base_values_2026.csv"
    bv = pd.read_csv(bv_path, dtype=str) if bv_path.exists() else None
    farms = load_farms()
    ok = True
    for f in farms:
        probs = validate_farm(f, bv)
        ok &= not probs
        print(f"{f['farm_id']:10s} acres={f['insured_acres']:>6} protection=${policy_protection(f):>10,.0f} "
              f"{'OK' if not probs else probs}")
    print("all farms valid" if ok else "SOME FARMS INVALID")


STEPS = {"sob": step_sob, "adm": step_adm, "dst": step_dst, "nass": step_nass, "ssurgo": step_ssurgo,
         "validate": step_validate}

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--steps", nargs="*", default=list(STEPS), choices=list(STEPS))
    a = ap.parse_args()
    for s in a.steps:
        print(f"=== {s}")
        STEPS[s]()
