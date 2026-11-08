"""Read-only dated availability check for the three selected daily-temperature series.

No account, authentication, positions or order submission. This checks daily contracts only;
it is not an exhaustive audit of every seasonal weather or CME alternative.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone

import requests

from agri_hedge.config import KALSHI_BASE_URL, PROCESSED

SERIES = {"CO_weld": "KXHIGHDEN", "PA_lancaster": "KXHIGHPHIL", "TX_erath": "KXHIGHTDAL"}
MONTHS = {name: n for n, name in enumerate("JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split(), 1)}


def main():
    now = datetime.now(timezone.utc)
    target_year = now.year + 1
    rows = []
    for site, series in SERIES.items():
        url = f"{KALSHI_BASE_URL}/markets"
        response = requests.get(url, params={"series_ticker": series, "status": "open", "limit": 1000}, timeout=20)
        response.raise_for_status()
        body = response.json()
        if body.get("cursor"):
            raise RuntimeError("Availability check needs pagination; refusing a partial answer")
        markets = body["markets"]
        events = sorted({m["event_ticker"] for m in markets})
        days = []
        for event in events:
            match = re.search(r"-(\d{2})([A-Z]{3})(\d{2})$", event)
            if not match:
                raise ValueError(f"Unrecognized daily event date: {event}")
            yy, mm, dd = match.groups()
            days.append(date(2000 + int(yy), MONTHS[mm], int(dd)))
        summer_days = [day for day in days if day.year == target_year and day.month in (6, 7, 8, 9)]
        rows.append({"site": site, "series": series, "source_url": response.url,
            "open_markets": len(markets), "open_event_dates": [d.isoformat() for d in days],
            "target_summer_year": target_year, "listed_summer_days": len(summer_days),
            "fully_bookable_before_summer": len(summer_days) == 122})
        print(series, rows[-1]["open_event_dates"], "summer days:", len(summer_days), flush=True)
    path = PROCESSED / "maya_dairy_market_check.json"
    path.write_text(json.dumps({"observed_at_utc": now.isoformat(), "rows": rows,
        "limitations": ["Only daily-high series checked; no orders submitted.",
            "No future contract price or depth is inferred from today's books."]}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
