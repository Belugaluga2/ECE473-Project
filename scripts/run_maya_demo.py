"""Offline research demo or settlement replay. Run --help for examples; no live trading."""
from __future__ import annotations

import argparse
import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import pandas as pd

from agri_hedge.config import PROCESSED, ROOT
from agri_hedge.maya_contract import settle


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8474, help="local demo port; existing companion uses 8473")
    parser.add_argument("--settle", action="store_true", help="print an offline settlement receipt instead of starting the demo")
    parser.add_argument("--county", default="17167", help="17167 Sangamon, 19169 Story, 18157 Tippecanoe")
    parser.add_argument("--year", type=int, default=2012, help="historical replay year, 1980-2024")
    parser.add_argument("--value", default="100000", help="illustrative expected crop value in dollars")
    parser.add_argument("--list", action="store_true", help="show the available demonstration counties and years")
    args = parser.parse_args()
    specs = json.loads((PROCESSED / "maya_contract_specs.json").read_text())
    if args.list:
        for fips, spec in specs.items():
            print(f"{fips}: {spec['county']}, {spec['state']}; replay input years 1980-2024")
        print("Interactive history uses doc 27's shared final-year cohort; all data are committed.")
        return 0
    if args.settle:
        if args.county not in specs:
            parser.error("Choose one of the counties listed by --list")
        daily = pd.read_csv(PROCESSED / "panel_daily_weather.csv", dtype={"fips": str}, parse_dates=["date"])
        season = daily[(daily.fips == args.county) & (daily.date.dt.year == args.year) & daily.date.dt.month.isin((6, 7))]
        try:
            receipt = settle(specs[args.county], season, args.year, args.value)
        except (ValueError, ArithmeticError) as exc:
            parser.error(str(exc))
        print(json.dumps(receipt, indent=2))
        return 0
    directory = ROOT / "experiments/maya"
    handler = partial(SimpleHTTPRequestHandler, directory=str(directory))
    with ThreadingHTTPServer(("127.0.0.1", args.port), handler) as server:
        print(f"Maya research demo: http://127.0.0.1:{args.port}/", flush=True)
        print("Offline data; hypothetical prices; no trades or deployment. Ctrl+C stops the server.", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
