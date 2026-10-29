"""Offline tests for agri_hedge.stations (B3). Fixtures live in tests/fixtures/b3/.

acis_dfw_2026_06_07.json  real ACIS StnData response, DFW airport, Jun-Jul 2026
acis_flags_synthetic.json synthetic ACIS response with T, M, S and A codes and two absent days
ghcn_dfw_2026_07.csv      real NCEI GHCN-Daily access-CSV rows, DFW, Jul 2026
kalshi_ladders.json       real Kalshi market objects: DFW Jul 2026 ladder, DFW Oct 2026 early
                          close (3 settled + 7 open), and one 2025 NYC market without strike fields
"""
import json
import math
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from agri_hedge.stations import (acis_daily_from_json, event_month, infer_settled_range,
                                 interval_totals, latest_complete_month, market_yes, month_end,
                                 monthly_totals, normalize_market, parse_acis_precip,
                                 parse_ghcn_csv, parse_settlement_location, split_acis_sids,
                                 value_in_range)

FIX = Path(__file__).parent / "fixtures" / "b3"


def load_json(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------------------------
# ACIS value parsing
# ---------------------------------------------------------------------------------------------
@pytest.mark.parametrize("raw, value, flag", [
    ("0.25", 0.25, ""),
    ("0.00", 0.0, ""),
    ("T", 0.0, "T"),
    ("1.30A", 1.30, "A"),
    (["0.07", " ", 24], 0.07, ""),
])
def test_parse_acis_precip_values(raw, value, flag):
    v, f = parse_acis_precip(raw)
    assert f == flag
    assert v == pytest.approx(value)


@pytest.mark.parametrize("raw, flag", [("M", "M"), ("", "M"), (None, "M"), ("S", "S"),
                                       ("garbage", "M")])
def test_parse_acis_precip_missing_and_subsequent(raw, flag):
    v, f = parse_acis_precip(raw)
    assert f == flag
    assert math.isnan(v)


# ---------------------------------------------------------------------------------------------
# Monthly and PRF-interval aggregation
# ---------------------------------------------------------------------------------------------
def test_monthly_totals_real_dfw_match_nws_cli():
    """DFW Jun/Jul 2026 totals equal the NWS CLI month-end values (8.07 and 1.36 in)."""
    daily = acis_daily_from_json(load_json("acis_dfw_2026_06_07.json"))
    m = monthly_totals(daily).set_index("month")
    assert m.loc[6, "precip_in"] == pytest.approx(8.07)
    assert m.loc[7, "precip_in"] == pytest.approx(1.36)
    assert m.loc[7, "n_days"] == 31 and m.loc[7, "n_missing"] == 0
    assert m.loc[6, "n_trace"] == 3 and m.loc[7, "n_trace"] == 4


def test_monthly_totals_flags_synthetic():
    daily = acis_daily_from_json(load_json("acis_flags_synthetic.json"))
    m = monthly_totals(daily).set_index("month")
    mar, apr = m.loc[3], m.loc[4]
    # 0.25 + 1.30 (accumulated) + 0.40; traces count 0; missing day excluded.
    assert mar["precip_in"] == pytest.approx(1.95)
    assert (mar["n_days"], mar["n_missing"], mar["n_trace"]) == (31, 1, 2)
    assert (mar["n_accum"], mar["n_subseq"]) == (1, 2)
    # Apr 29-30 absent from the data -> counted missing.
    assert apr["precip_in"] == pytest.approx(1.05)
    assert (apr["n_days"], apr["n_missing"], apr["n_trace"]) == (30, 2, 1)


def test_monthly_totals_all_missing_month_is_nan():
    daily = pd.DataFrame({"date": pd.to_datetime(["2021-02-01"]), "precip_in": [float("nan")],
                          "flag": ["M"]})
    m = monthly_totals(daily, "2021-02-01", "2021-02-28")
    assert len(m) == 1 and math.isnan(m["precip_in"].iloc[0])
    assert m["n_missing"].iloc[0] == 28


def test_interval_totals_synthetic():
    daily = acis_daily_from_json(load_json("acis_flags_synthetic.json"))
    iv = interval_totals(monthly_totals(daily)).set_index("interval")
    assert set(iv.index) == {"Feb-Mar", "Mar-Apr", "Apr-May"}
    assert iv.loc["Mar-Apr", "precip_in"] == pytest.approx(3.00)
    assert iv.loc["Mar-Apr", "n_missing"] == 3
    assert not iv.loc["Mar-Apr", "complete"]
    # February is absent: total undefined and its 28 days count as missing.
    assert math.isnan(iv.loc["Feb-Mar", "precip_in"])
    assert iv.loc["Feb-Mar", "n_missing"] == 28 + 1


def test_interval_totals_complete_and_grouped():
    monthly = pd.DataFrame({"station_key": ["A", "A", "B", "B"], "year": [2026] * 4,
                            "month": [6, 7, 6, 7], "precip_in": [8.07, 1.36, 1.0, 2.0],
                            "n_missing": [0, 0, 0, 1]})
    iv = interval_totals(monthly, by=["station_key"])
    a = iv[(iv.station_key == "A") & (iv.interval == "Jun-Jul")].iloc[0]
    b = iv[(iv.station_key == "B") & (iv.interval == "Jun-Jul")].iloc[0]
    assert a["precip_in"] == pytest.approx(9.43) and bool(a["complete"])
    assert b["precip_in"] == pytest.approx(3.0) and not bool(b["complete"])
    assert list(iv[iv.station_key == "A"]["interval"]) == ["May-Jun", "Jun-Jul", "Jul-Aug"]


# ---------------------------------------------------------------------------------------------
# GHCN-Daily cross-check parser
# ---------------------------------------------------------------------------------------------
def test_parse_ghcn_csv_converts_and_flags_trace():
    g = parse_ghcn_csv(FIX / "ghcn_dfw_2026_07.csv")
    assert len(g) == 31
    assert g.loc[g["date"] == "2026-07-13", "precip_in"].iloc[0] == pytest.approx(1.29)
    assert list(g.loc[g["flag"] == "T", "date"].dt.day) == [6, 12, 16, 24]
    m = monthly_totals(g)
    assert m["precip_in"].iloc[0] == pytest.approx(1.36)  # same as ACIS


# ---------------------------------------------------------------------------------------------
# Kalshi ladder decoding
# ---------------------------------------------------------------------------------------------
def test_infer_settled_range_dfw_july_2026():
    ladder = load_json("kalshi_ladders.json")["KXRAINDALM-26JUL"]
    rng = infer_settled_range(ladder)
    assert (rng["lo"], rng["lo_closed"], rng["hi"], rng["hi_closed"]) == (1, False, 2, True)
    assert rng["label"] == "(1, 2]"
    assert rng["consistent"] and rng["n_yes"] == 1 and rng["n_no"] == 6
    assert rng["expiration_value"] == pytest.approx(1.4)
    assert value_in_range(1.36, rng) is True
    assert value_in_range(2.0, rng) is True      # "Above 2" settled NO, so 2.00 is allowed
    assert value_in_range(1.0, rng) is False     # "Above 1" settled YES needs > 1.00


def test_infer_settled_range_early_close_ignores_open_markets():
    ladder = load_json("kalshi_ladders.json")["KXRAINDALM-26OCT"]
    rng = infer_settled_range(ladder)
    assert rng["n_markets"] == 3 and rng["n_yes"] == 3
    assert rng["lo"] == 3 and rng["hi"] is None and rng["label"] == "(3, inf)"


def test_infer_settled_range_flags_inconsistent_ladder():
    ladder = [{"strike_type": "greater", "floor_strike": 4, "result": "yes"},
              {"strike_type": "greater", "floor_strike": 3, "result": "no"}]
    assert infer_settled_range(ladder)["consistent"] is False


def test_infer_settled_range_less_and_between():
    ladder = [{"strike_type": "less", "cap_strike": 2, "result": "no"},      # total >= 2
              {"strike_type": "between", "floor_strike": 2, "cap_strike": 3, "result": "yes"}]
    rng = infer_settled_range(ladder)
    assert (rng["lo"], rng["lo_closed"], rng["hi"], rng["hi_closed"]) == (2, True, 3, False)
    assert value_in_range(2.0, rng) and not value_in_range(3.0, rng)


def test_normalize_market_without_strike_fields():
    mk = load_json("kalshi_ladders.json")["NYC_NO_STRIKE"][0]
    assert "strike_type" not in mk
    n = normalize_market(mk)
    assert n["strike_type"] == "greater" and n["floor_strike"] == 4.0
    assert n["expiration_value_in"] == pytest.approx(0.61)      # parsed from "0.61 inches"
    rng = infer_settled_range([mk])
    assert rng["hi"] == 4.0 and rng["hi_closed"]


@pytest.mark.parametrize("stype, total, floor, cap, expected", [
    ("greater", 3.00, 3, None, False),          # strictly greater: equal is NO
    ("greater", 3.01, 3, None, True),
    ("greater", 0.0, 0, None, False),           # trace month (0.00) vs strike 0
    ("greater_or_equal", 3.00, 3, None, True),
    ("less", 2.99, None, 3, True),
    ("between", 3.00, 2, 3, False),             # RAINM terms: [lower, upper)
    ("between", 2.00, 2, 3, True),
    ("greater", float("nan"), 3, None, None),
])
def test_market_yes(stype, total, floor, cap, expected):
    assert market_yes(stype, total, floor, cap) == expected


# ---------------------------------------------------------------------------------------------
# Rules text, tickers, ids, dates
# ---------------------------------------------------------------------------------------------
@pytest.mark.parametrize("text, code, how", [
    ("If the total precipitation at CLIDFW in Dallas in Oct 2026 is strictly greater than 3 "
     "inches, then the market resolves to Yes.", "DFW", "cli"),
    ("If the total precipitation at KAPC in Napa in December 2026 is strictly greater than 8 "
     "inches", "APC", "icao"),
    ("If the total precipitation at Central Park, New York City in Jan 2025 is strictly greater",
     "NYC", "name"),
    ("If the total precipitation at Chicago Midway, IL in || Month || is strictly greater than 4",
     "MDW", "name"),
    ("no station here", "", "none"),
    (None, "", "none"),
])
def test_parse_settlement_location(text, code, how):
    loc = parse_settlement_location(text)
    assert (loc["code"], loc["how"]) == (code, how)


@pytest.mark.parametrize("ticker, rules, expected", [
    ("KXRAINDALM-26OCT", None, (2026, 10)),
    ("RAINNYCM-24JUN", None, (2024, 6)),
    ("KXRAINNAPAM-01DEC26-31DEC26", None, (2026, 12)),
    ("KXRAINNAPAM-01DEC26-15DEC26", None, None),
    ("WEIRD", "total precipitation at CLIDFW in Dallas in Oct 2026 is", (2026, 10)),
])
def test_event_month(ticker, rules, expected):
    assert event_month(ticker, rules) == expected


def test_split_acis_sids():
    sids = ["03927 1", "412242 2", "DFW 3", "72259 4", "KDFW 5", "USW00003927 6", "DFW 7",
            "USW00003927 32"]
    ids = split_acis_sids(sids)
    assert ids["icao"] == ["KDFW"] and ids["ghcn"] == ["USW00003927"]
    assert ids["wban"] == ["03927"] and ids["faa"] == ["DFW"]


def test_latest_complete_month_and_month_end():
    assert latest_complete_month(date(2026, 10, 29)) == (2026, 9)
    assert latest_complete_month(date(2027, 1, 5)) == (2026, 12)
    assert month_end(2024, 2) == "2024-02-29"
