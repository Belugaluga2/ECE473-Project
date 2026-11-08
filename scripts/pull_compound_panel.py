"""Public, cached county-yield and weather inputs for pre-specified doc 27; no accounts."""
from __future__ import annotations

import hashlib
import io
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import urlencode, quote

import pandas as pd
import requests

from agri_hedge.config import PROCESSED, RAW

COUNTIES = [
    ("17019", "IL", "Champaign", "development"), ("17099", "IL", "La Salle", "development"),
    ("17113", "IL", "McLean", "development"), ("17167", "IL", "Sangamon", "held_out"),
    ("19015", "IA", "Boone", "development"), ("19153", "IA", "Polk", "development"),
    ("19187", "IA", "Webster", "development"), ("19169", "IA", "Story", "held_out"),
    ("18007", "IN", "Benton", "development"), ("18023", "IN", "Clinton", "development"),
    ("18181", "IN", "White", "development"), ("18157", "IN", "Tippecanoe", "held_out"),
]
DEST = RAW / "compound_panel"
HEADERS = {"User-Agent": "Mozilla/5.0 (ECE473 student weather-cover research)"}


def cached(name, url, payload=None):
    path = DEST / name
    if not path.exists():
        if payload is None:
            response = requests.get(url, headers=HEADERS, timeout=60)
        else:
            response = requests.post(url, json=payload, headers=HEADERS, timeout=60)
        response.raise_for_status()
        if payload is not None and "error" in response.json():
            raise ValueError(response.json()["error"])
        path.write_bytes(response.content)
    content = path.read_bytes()
    return content, {"url": url, "payload": payload, "sha256": hashlib.sha256(content).hexdigest()}


def one_county(record):
    fips, state, name, role = record
    coords = pd.read_csv(PROCESSED / "rowcrop_county_station_distance.csv", dtype={"geoid": str}).set_index("geoid")
    lat, lon = float(coords.loc[fips, "lat"]), float(coords.loc[fips, "lon"])
    params = {"source_desc": "SURVEY", "agg_level_desc": "COUNTY", "state_alpha": state,
        "county_code": fips[2:], "short_desc": "CORN, GRAIN - YIELD, MEASURED IN BU / ACRE",
        "domain_desc": "TOTAL", "prodn_practice_desc": "ALL PRODUCTION PRACTICES",
        "reference_period_desc": "YEAR", "freq_desc": "ANNUAL", "year__GE": "1940"}
    qs = "https://quickstats.nass.usda.gov"
    uuid_bytes, uuid_source = cached(f"{fips}_uuid.txt", f"{qs}/uuid/encode?{urlencode(params, quote_via=quote)}")
    uuid = uuid_bytes.decode().strip().strip('"')
    if not uuid or "<" in uuid or len(uuid) > 200:
        raise ValueError(f"Unexpected Quick Stats export token for {fips}")
    content, yield_source = cached(f"{fips}_yield.csv", f"{qs}/data/spreadsheet/{uuid}.csv")
    raw = pd.read_csv(io.BytesIO(content), dtype=str)
    needed = {"Year", "Value", "County ANSI", "State ANSI", "Domain", "Period"}
    if not needed.issubset(raw.columns):
        raise ValueError(f"Unexpected NASS CSV for {fips}: {list(raw.columns)}")
    actual_fips = raw["State ANSI"].str.zfill(2) + raw["County ANSI"].str.zfill(3)
    if not (actual_fips == fips).all() or not raw.Period.eq("YEAR").all() or not raw.Domain.eq("TOTAL").all():
        raise ValueError(f"Unexpected location/domain/period for {fips}")
    yields = pd.DataFrame({"fips": fips, "year": pd.to_numeric(raw.Year), "source_value": raw.Value,
        "yield_bu_ac": pd.to_numeric(raw.Value.str.replace(",", "", regex=False).str.strip(), errors="coerce")})
    if yields.year.duplicated().any():
        raise ValueError(f"Ambiguous duplicate annual yields for {fips}")
    yields = yields[yields.year <= 2024].sort_values("year")
    payload = {"sdate": "1980-01-01", "edate": "2024-12-31", "elems": ["pcpn", "maxt", "mint"],
               "grid": "1", "loc": f"{lon},{lat}"}
    content, weather_source = cached(f"{fips}_weather.json", "https://data.rcc-acis.org/GridData", payload)
    response = json.loads(content)
    weather = pd.DataFrame(response["data"], columns=["date", "rain_in", "tmax_f", "tmin_f"])
    weather.date = pd.to_datetime(weather.date)
    for col in ("rain_in", "tmax_f", "tmin_f"):
        # Trace precipitation is numerically zero, flagged separately; other flags stay missing.
        if col == "rain_in":
            weather["rain_trace"] = weather[col].eq("T")
            weather[col] = weather[col].replace("T", "0")
        weather[col] = pd.to_numeric(weather[col], errors="coerce")
        weather.loc[weather[col] <= -100, col] = float("nan")
    weather = weather[weather.date.dt.month.isin((4, 5, 6, 7))]
    weather.insert(0, "fips", fips)
    metadata = {"fips": fips, "state": state, "county": name, "role": role, "lat": lat, "lon": lon}
    provenance = {"fips": fips, "query": uuid_source, "yields": yield_source, "weather": weather_source,
                  "n_yield_rows": len(yields), "n_weather_rows": len(weather),
                  "weather_missing": weather[["rain_in", "tmax_f", "tmin_f"]].isna().sum().to_dict()}
    print(fips, name, "yield years", len(yields), "weather missing", provenance["weather_missing"], flush=True)
    return metadata, yields, weather, provenance


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(one_county, COUNTIES))
    pd.DataFrame([x[0] for x in results]).to_csv(PROCESSED / "panel_counties.csv", index=False)
    pd.concat([x[1] for x in results], ignore_index=True).to_csv(PROCESSED / "panel_yields.csv", index=False)
    pd.concat([x[2] for x in results], ignore_index=True).to_csv(PROCESSED / "panel_daily_weather.csv", index=False, date_format="%Y-%m-%d")
    files = ("panel_counties.csv", "panel_yields.csv", "panel_daily_weather.csv")
    manifest = {"first_prepared_utc": datetime.now(timezone.utc).isoformat(),
        "coordinate_source": "committed rowcrop_county_station_distance.csv, Census Gazetteer internal points",
        "requests": [x[3] for x in results],
        "prepared_sha256": {f: hashlib.sha256((PROCESSED/f).read_bytes()).hexdigest() for f in files},
        "limitations": ["Revised NASS history, not vintage releases or individual-farm claims.",
            "NRCC gridded point weather is not a county cropland average or exchange settlement series.",
            "Convenience sample fixed in doc 27; nearby counties share weather shocks."]}
    (PROCESSED / "panel_source_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
