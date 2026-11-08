"""Download daily Midway and Kane-grid temperatures for the compound corn pilot (doc 26).

Reads public ACIS endpoints, caches raw responses, and commits a small June-August subset.
No credentials, positions or orders. Rainfall/yields reuse the project's committed inputs.
"""
from __future__ import annotations

import hashlib
import json
import pandas as pd
import requests

from agri_hedge.config import PROCESSED, RAW
from agri_hedge.locations import ALL_SITES

ACIS = "https://data.rcc-acis.org"


def fetch(name, endpoint, payload):
    directory = RAW / "compound"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.json"
    if path.exists():
        content = path.read_bytes()
    else:
        response = requests.post(f"{ACIS}/{endpoint}", json=payload, timeout=45)
        response.raise_for_status()
        content = response.content
        parsed = json.loads(content)
        if "error" in parsed:
            raise ValueError(parsed["error"])
        path.write_bytes(content)
    return json.loads(content), {"endpoint": f"{ACIS}/{endpoint}", "payload": payload,
                                "sha256": hashlib.sha256(content).hexdigest()}


def main():
    site = ALL_SITES["ORD"]
    common = {"sdate": "1980-01-01", "edate": "2025-12-31", "elems": ["maxt", "mint"]}
    station, station_source = fetch("mdw_1980_2025", "StnData", dict(common, sid="MDW"))
    backup, backup_source = fetch("mdw_3sw_1980_2025", "StnData", dict(common, sid="USC00111577"))
    grid, grid_source = fetch("kane_1980_2025", "GridData",
        dict(common, grid="1", loc=f"{site['farm_lon']},{site['farm_lat']}"))
    frames = []
    for name, response in (("mdw", station), ("mdw_3sw", backup), ("kane", grid)):
        frame = pd.DataFrame(response["data"], columns=["date", f"{name}_tmax_f", f"{name}_tmin_f"])
        frame.date = pd.to_datetime(frame.date)
        for column in frame.columns[1:]:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
            frame.loc[frame[column] <= -100, column] = float("nan")
        frames.append(frame)
    combined = frames[0].merge(frames[1], on="date", validate="one_to_one", how="outer")
    combined = combined.merge(frames[2], on="date", validate="one_to_one", how="outer")
    for extreme in ("max", "min"):
        original, substitute = f"mdw_t{extreme}_f", f"mdw_3sw_t{extreme}_f"
        combined[f"mdw_t{extreme}_from_3sw"] = combined[original].isna() & combined[substitute].notna()
        combined[original] = combined[original].fillna(combined[substitute])
        combined = combined.drop(columns=substitute)
    combined = combined[combined.date.dt.month.isin((6, 7, 8))].sort_values("date")
    combined.to_csv(PROCESSED / "compound_daily_temperature.csv", index=False, date_format="%Y-%m-%d")
    manifest = {"sources": {"mdw": station_source, "mdw_3sw": backup_source, "kane": grid_source},
        "station_meta": station.get("meta"), "backup_meta": backup.get("meta"), "grid_meta": grid.get("meta"),
        "units": "degrees Fahrenheit", "prepared_rows": len(combined),
        "prepared_sha256": hashlib.sha256((PROCESSED / "compound_daily_temperature.csv").read_bytes()).hexdigest(),
        "limitations": ["Kane grid value is a point estimate, not an observed farm thermometer.",
            "Missing Midway airport days use nearby COOP Midway AP 3SW; per-element substitutions are flagged.",
            "Chicago heat and rain settle at different stations; the area diagnostic is hypothetical."]}
    (PROCESSED / "compound_weather_source.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(station.get("meta"), flush=True)
    print("Prepared", len(combined), "daily rows; missing values:", combined.isna().sum().to_dict(), flush=True)


if __name__ == "__main__":
    main()
