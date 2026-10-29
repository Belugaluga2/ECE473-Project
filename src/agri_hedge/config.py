"""Shared paths and constants. Raw data can be redirected off OneDrive with AGRI_HEDGE_RAW_DIR."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RAW = Path(os.environ.get("AGRI_HEDGE_RAW_DIR", DATA / "raw"))
PROCESSED = DATA / "processed"
SCENARIOS = DATA / "scenarios"
DOCS = ROOT / "docs"
FIGURES = DOCS / "figures"

for _p in (RAW, PROCESSED, SCENARIOS, FIGURES):
    _p.mkdir(parents=True, exist_ok=True)

KALSHI_BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"
