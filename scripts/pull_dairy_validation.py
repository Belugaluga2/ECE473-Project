"""Fetch only small source members of the published U.S. dairy replication archive.

Source: Gisbert-Queral et al. (2021), https://doi.org/10.5281/zenodo.4818011.
Does not download the 4.3 GB archive. Raw members are cached under data/raw/.
Requires the optional dairy extra: python -m pip install -e ".[dairy]".
"""
from __future__ import annotations

import hashlib
import json
import zipfile

from agri_hedge.config import RAW, PROCESSED
from agri_hedge.remote_archive import HTTPRangeFile

URL = "https://zenodo.org/records/4818011/files/ClimateDairy.zip?download=1"
MEMBERS = ("DataGenerated/panel_final.rds", "DataRaw/milk_state.xlsx",
           "PreparePanelFinal.R", "PreparePanelTHI.R", "PrepareMilkData.R",
           "PrepareWeatherData.R", "CalcFrequenciesTHI_Temp.R", "CreateFigure2a.R")


def main():
    destination = RAW / "dairy_validation"
    destination.mkdir(parents=True, exist_ok=True)
    missing = [name for name in MEMBERS if not (destination / name.split("/")[-1]).exists()]
    if not missing:
        print(f"All source members cached at {destination}")
        prepare(destination)
        return 0
    remote = HTTPRangeFile(URL)
    records = []
    with zipfile.ZipFile(remote) as archive:
        for name in MEMBERS:
            candidates = [entry for entry in archive.infolist() if entry.filename.endswith(name)]
            if len(candidates) != 1:
                raise ValueError(f"Expected one archive member ending in {name}, got {len(candidates)}")
            entry = candidates[0]
            if entry.file_size > 16 * 1024 * 1024:
                raise ValueError(f"Source member unexpectedly large: {name}")
            path = destination / name.split("/")[-1]
            if not path.exists():
                path.write_bytes(archive.read(entry))
            records.append({"member": entry.filename, "bytes": path.stat().st_size,
                            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
            print(name, path.stat().st_size, flush=True)
    (destination / "source_manifest.json").write_text(json.dumps({"url": URL, "members": records,
        "bytes_transferred_this_run": remote.bytes_received}, indent=2), encoding="utf-8")
    print(f"Transferred {remote.bytes_received:,} bytes from a {remote.size:,}-byte archive")
    prepare(destination)
    return 0


def prepare(destination):
    """Commit a small, audited subset so the experiment runs offline without R readers."""
    import numpy as np
    import pandas as pd
    import pyreadr
    from agri_hedge.dairy_validation import STATES

    source = pyreadr.read_r(str(destination / "panel_final.rds"))[None]
    source = source[source.State.isin(STATES)].copy()
    dates = pd.to_datetime(source.time)
    raw_milk = pd.read_excel(destination / "milk_state.xlsx")
    raw_milk["month"] = pd.to_datetime(raw_milk.Period, format="%b", errors="coerce").dt.month
    raw_milk["Month"] = raw_milk.month.map(lambda m: f"{m:02.0f}" if pd.notna(m) else "")
    audit = source.merge(raw_milk, on=["State", "Year", "Month"], how="left", suffixes=("", "_raw"))
    values = pd.to_numeric(audit.Value.astype(str).str.replace(",", "", regex=False), errors="coerce")
    expected = values * 0.45359237 / audit.nDays
    if expected.isna().any() or not np.allclose(expected, audit.MilkYield, atol=1e-8, rtol=0):
        raise ValueError("Prepared milk yield does not match the raw NASS source conversion")
    out = pd.DataFrame({"state": source.State, "year": dates.dt.year, "month": dates.dt.month,
        "milk_kg_cow_day": source.MilkYield, "days": source.nDays,
        "thi69_share": source.hotdays, "thi79_share": source.thihot,
        "source_bin_share_sum": source.rowsums})
    if not np.allclose(out.source_bin_share_sum, 1, atol=1e-8):
        raise ValueError("Weather bin shares do not sum to one")
    out = out.sort_values(["state", "year", "month"])
    out.to_csv(PROCESSED / "maya_dairy_state_month.csv", index=False, float_format="%.12g")
    manifest = json.loads((destination / "source_manifest.json").read_text(encoding="utf-8"))
    manifest.pop("bytes_transferred_this_run", None)
    manifest.update(rows=len(out), states=list(STATES), milk_units="kg/cow/day",
        study_doi="10.1038/s43016-021-00372-z", record_doi="10.5281/zenodo.4818011",
        source_conversion_max_abs_error=float(np.max(np.abs(expected - audit.MilkYield))),
        limitations=["State averages are not individual-farm records.",
            "Published exposure weights use 2002-2012 cow inventories as fixed geographic weights.",
            "THI 69.4/79.3 cutoffs follow the publication's bin edges, not universal cow thresholds."])
    (PROCESSED / "maya_dairy_source.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("Prepared", len(out), "observed state-month records; raw milk conversion verified")


if __name__ == "__main__":
    raise SystemExit(main())
