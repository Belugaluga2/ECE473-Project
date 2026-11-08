"""Read-only public listing/settlement snapshot for doc 26; no credentials or orders."""
import json
from datetime import datetime, timezone

import requests

from agri_hedge.config import KALSHI_BASE_URL, PROCESSED, RAW


def main():
    output = {"checked_utc": datetime.now(timezone.utc).isoformat(),
              "scope": "Public series metadata and all currently open markets, not historical quotes.",
              "series": {}}
    raw = RAW / "compound"
    raw.mkdir(parents=True, exist_ok=True)
    for ticker in ("KXHIGHCHI", "KXRAINCHIM"):
        response = requests.get(f"{KALSHI_BASE_URL}/series/{ticker}", timeout=30)
        response.raise_for_status()
        series = response.json()["series"]
        markets, cursor = [], None
        while True:
            params = {"series_ticker": ticker, "status": "open", "limit": 1000}
            if cursor:
                params["cursor"] = cursor
            response = requests.get(f"{KALSHI_BASE_URL}/markets", params=params, timeout=30)
            response.raise_for_status()
            payload = response.json()
            markets.extend(payload["markets"])
            cursor = payload.get("cursor")
            if not cursor:
                break
        (raw / f"{ticker}_market_snapshot.json").write_text(
            json.dumps({"checked_utc": output["checked_utc"], "series": series, "markets": markets}, indent=2), encoding="utf-8")
        keep = ("ticker", "event_ticker", "title", "subtitle", "rules_primary", "rules_secondary",
                "close_time", "expected_expiration_time")
        compact = {"metadata_url": f"{KALSHI_BASE_URL}/series/{ticker}", "metadata": series,
                   "open_market_count": len(markets),
                   "open_event_tickers": sorted({m["event_ticker"] for m in markets}),
                   "sample_markets": [{k: m.get(k) for k in keep} for m in markets[:2]]}
        output["series"][ticker] = compact
        print(ticker, compact["open_event_tickers"], compact["sample_markets"], flush=True)
    (PROCESSED / "compound_market_check.json").write_text(json.dumps(output, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
