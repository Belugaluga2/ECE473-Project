"""Download daily maximum temperature for the dairy heat-stress study (doc 24).

For each dairy region: the Kalshi settlement airport (ACIS station data) and a point in the
dairy county (ACIS grid 1, NRCC interpolated, 1950-present). May-September only, 1951-2025.
Missing airport days are filled from the NWS threaded climate record (ThreadEx, the series
NWS uses for the city's climate history) and flagged, because several airports opened after
1951. Writes data/processed/dairy_daily_tmax.parquet (committed, so tests run offline).

Source: Applied Climate Information System, https://www.rcc-acis.org/docs_webservices.html
"""
from __future__ import annotations

import json
import time
import urllib.request

import pandas as pd

from agri_hedge.config import PROCESSED
from agri_hedge.dairy import SITES

ACIS = "https://data.rcc-acis.org"
START, END = "1951-01-01", "2025-12-31"


def _post(endpoint: str, body: dict) -> dict:
    req = urllib.request.Request(f"{ACIS}/{endpoint}", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json",
                                          "User-Agent": "agri-hedge-research"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                out = json.loads(r.read())
            if "error" in out:
                raise RuntimeError(out["error"])
            return out
        except Exception:
            if attempt == 3:
                raise
            time.sleep(3 * (attempt + 1))
    raise RuntimeError("unreachable")


def _series(rows) -> pd.Series:
    s = pd.Series({pd.Timestamp(d): v for d, v in rows})
    return pd.to_numeric(s.replace({"M": None, "S": None, -999: None}), errors="coerce").astype(float)


def main() -> int:
    frames = []
    for site in SITES:
        stn = _post("StnData", {"sid": site.acis_sid, "sdate": START, "edate": END, "elems": "maxt"})
        thr = _post("StnData", {"sid": site.thread_sid, "sdate": START, "edate": END, "elems": "maxt"})
        grid = _post("GridData", {"loc": f"{site.lon},{site.lat}", "sdate": START, "edate": END,
                                  "grid": "1", "elems": "maxt"})
        a, t, g = _series(stn["data"]), _series(thr["data"]), _series(grid["data"])
        df = pd.DataFrame({"airport_tmax_f": a, "thread_tmax_f": t, "farm_tmax_f": g})
        df["airport_filled_from_thread"] = df.airport_tmax_f.isna() & df.thread_tmax_f.notna()
        df["airport_tmax_f"] = df.airport_tmax_f.fillna(df.thread_tmax_f)
        df = df.drop(columns="thread_tmax_f")
        df = df[df.index.month.isin(range(5, 10))].rename_axis("date").reset_index()
        df.insert(0, "site", site.site_id)
        frames.append(df)
        print(f"{site.site_id}: airport {stn['meta']['name']} ({site.acis_sid}); "
              f"thread-filled days {int(df.airport_filled_from_thread.sum())}; "
              f"missing airport {int(df.airport_tmax_f.isna().sum())}, farm {int(df.farm_tmax_f.isna().sum())}",
              flush=True)
    out = pd.concat(frames, ignore_index=True)
    path = PROCESSED / "dairy_daily_tmax.parquet"
    out.to_parquet(path, index=False)
    print(path, len(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
