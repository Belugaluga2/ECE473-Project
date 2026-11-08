"""Optional public inputs for doc 28. Keeps old snapshots unchanged; no credentials/orders."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests

from agri_hedge.compound import sinusoidal_excess
from agri_hedge.config import KALSHI_BASE_URL, PROCESSED, RAW


def main():
    directory = RAW / "maya_diagnostics"
    directory.mkdir(parents=True, exist_ok=True)
    counties = pd.read_csv(PROCESSED / "panel_counties.csv", dtype={"fips": str})
    rows, sources = [], []
    for county in counties[counties.role == "held_out"].itertuples():
        payload = {"sdate": "1980-01-01", "edate": "2024-12-31", "elems": ["pcpn", "maxt", "mint"],
                   "grid": "1", "loc": f"{county.lon},{county.lat}"}
        path = RAW / "compound_panel" / f"{county.fips}_weather.json"
        if not path.exists():
            path = directory / f"{county.fips}_weather.json"
            if not path.exists():
                response = requests.post("https://data.rcc-acis.org/GridData", json=payload, timeout=60)
                response.raise_for_status()
                parsed = response.json()
                if "error" in parsed:
                    raise ValueError(parsed["error"])
                path.write_bytes(response.content)
        content = path.read_bytes()
        weather = pd.DataFrame(json.loads(content)["data"], columns=["date", "rain", "high", "low"])
        weather.date = pd.to_datetime(weather.date)
        for column in ("rain", "high", "low"):
            weather[column] = pd.to_numeric(weather[column].replace("T", "0"), errors="coerce")
            weather.loc[weather[column] <= -100, column] = np.nan
        august = weather[weather.date.dt.month == 8]
        for year, group in august.groupby(august.date.dt.year):
            complete = len(group) == 31 and np.isfinite(group[["rain", "high", "low"]].to_numpy()).all()
            rows.append({"fips": county.fips, "year": year, "complete": complete,
                         "rain_in": float(group.rain.sum()) if complete else np.nan,
                         "heat_dd29": float(sinusoidal_excess((group.low.to_numpy()-32)*5/9,
                                                 (group.high.to_numpy()-32)*5/9).sum()) if complete else np.nan})
        sources.append({"fips": county.fips, "url": "https://data.rcc-acis.org/GridData", "payload": payload,
                        "sha256": hashlib.sha256(content).hexdigest()})
    pd.DataFrame(rows).to_csv(PROCESSED / "maya_august_context.csv", index=False)
    (PROCESSED / "maya_august_source.json").write_text(json.dumps(sources, indent=2), encoding="utf-8")
    snapshot = {"checked_utc": datetime.now(timezone.utc).isoformat(), "series": {}}
    for ticker in ("KXRAINCHIM", "KXHIGHCHI"):
        response = requests.get(f"{KALSHI_BASE_URL}/series/{ticker}", timeout=30)
        response.raise_for_status()
        metadata = response.json()["series"]
        markets, cursor = [], None
        while True:
            params = {"series_ticker": ticker, "status": "open", "limit": 1000}
            if cursor:
                params["cursor"] = cursor
            response = requests.get(f"{KALSHI_BASE_URL}/markets", params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            markets.extend(data["markets"])
            cursor = data.get("cursor")
            if not cursor:
                break
        fields = ("ticker", "event_ticker", "title", "yes_sub_title", "no_sub_title", "strike_type",
                  "floor_strike", "cap_strike", "rules_primary", "rules_secondary", "close_time",
                  "yes_ask_dollars", "no_ask_dollars", "yes_ask", "no_ask")
        snapshot["series"][ticker] = {"metadata": metadata, "metadata_url": f"{KALSHI_BASE_URL}/series/{ticker}",
            "open_events": sorted({m["event_ticker"] for m in markets}),
            "markets": [{key: market.get(key) for key in fields} for market in markets]}
    (PROCESSED / "maya_market_snapshot.json").write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    print("August rows", len(rows), "incomplete", sum(not row["complete"] for row in rows))
    print("Market snapshot", snapshot["checked_utc"], {k: v["open_events"] for k, v in snapshot["series"].items()})


if __name__ == "__main__":
    main()
