"""Tests for agri_hedge.cpc: data readers, interval aggregation and the PRF index formula."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from agri_hedge.cpc import (MM_PER_INCH, comparison_stats, compute_index, dst_base_end,
                            fine_grid_to_prf, handbook_base_end, interval_totals,
                            mm_per_day_to_month_total_mm, read_cpc_daily_binary,
                            trigger_disagreement)
from agri_hedge.prf_grid import grid_id_to_rowcol
from agri_hedge.prf_intervals import INTERVAL_NAMES

FIX = Path(__file__).parent / "fixtures" / "b1"


@pytest.fixture
def monthly():
    # value = month + 10 * (year - 2000) (+100 for grid 8); grid 8 has no 2003-05 value
    return pd.read_csv(FIX / "monthly_synthetic.csv")


def test_interval_totals_synthetic(monthly):
    iv = interval_totals(monthly, value_col="precip_mm")
    assert list(iv.columns) == ["grid_id", "year", "interval_name", "interval_code",
                                "interval_precip_mm"]
    g7 = iv[(iv.grid_id == 7) & (iv.year == 2001)].set_index("interval_name")["interval_precip_mm"]
    assert list(g7.index) == INTERVAL_NAMES                       # 11 intervals, in order
    assert g7["Jan-Feb"] == (1 + 10) + (2 + 10)
    assert g7["Nov-Dec"] == (11 + 10) + (12 + 10)
    assert iv[(iv.grid_id == 7) & (iv.year == 2001) & (iv.interval_name == "Jan-Feb")
              ].interval_code.item() == 625
    # missing May 2003 for grid 8 removes Apr-May and May-Jun only
    g8 = iv[(iv.grid_id == 8) & (iv.year == 2003)]
    assert set(g8.interval_name) == set(INTERVAL_NAMES) - {"Apr-May", "May-Jun"}
    assert len(iv) == 2 * 4 * 11 - 2


def test_index_formula_fixed_base(monthly):
    iv = interval_totals(monthly, value_col="precip_mm")
    out = compute_index(iv, "interval_precip_mm", base_start=2000, base_end=2003)
    # grid 7 Jan-Feb totals: 3, 23, 43, 63 -> mean 33
    jf = out[(out.grid_id == 7) & (out.interval_name == "Jan-Feb")].set_index("year")
    assert jf["expected_interval_precip_mm"].unique() == pytest.approx([33.0])
    assert jf.loc[2000, "index_value"] == pytest.approx(100 * 3 / 33)
    assert jf.loc[2003, "index_value"] == pytest.approx(100 * 63 / 33)
    # the base-period mean of the index is 100 by construction
    assert jf["index_value"].mean() == pytest.approx(100.0)


def test_index_formula_rolling_base(monthly):
    iv = interval_totals(monthly, value_col="precip_mm")
    out = compute_index(iv, "interval_precip_mm", base_start=2000, base_end=handbook_base_end,
                        min_base_years=2)
    jf = out[(out.grid_id == 7) & (out.interval_name == "Jan-Feb")].set_index("year")
    assert np.isnan(jf.loc[2001, "index_value"])                 # base 2000..1999 is empty
    assert np.isnan(jf.loc[2002, "index_value"])                 # base 2000..2000: 1 year < 2
    assert jf.loc[2003, "expected_interval_precip_mm"] == pytest.approx((3 + 23) / 2)
    assert jf.loc[2003, "base_end"] == 2001


def test_dst_base_rule():
    assert dst_base_end(1951) == 2025
    assert dst_base_end(2025) == 2025
    assert dst_base_end(2026) == 2024
    assert dst_base_end(2027, current_crop_year=2028) == 2025


def test_dst_base_period_reproduces_official_expected_values():
    """Official DST values for grid 15432: expected = mean(1951..2025) for years <= 2025 and
    mean(1951..2024) for 2026; index = 100 * measurement / expected (rounded to 0.1)."""
    off = pd.read_csv(FIX / "dst_15432_official_series.csv")
    off["interval_name"] = off.interval_code.map({625: "Jan-Feb", 631: "Jul-Aug"})
    out = compute_index(off, "interval_precip_mm", base_start=1951, base_end=dst_base_end,
                        round_to=1)
    assert out["expected_interval_precip_mm"].to_numpy() == pytest.approx(
        out["expected_precip_mm"].to_numpy(), abs=1e-6)
    assert out["index_value"].to_numpy() == pytest.approx(
        (100 * out["percent_of_normal"]).to_numpy(), abs=0.051)
    # the match is specific to a 1951 start: starting one year later breaks it
    alt = compute_index(off[off.year >= 1951], "interval_precip_mm", base_start=1952,
                        base_end=dst_base_end)
    assert not np.allclose(alt["expected_interval_precip_mm"], alt["expected_precip_mm"])


def test_units():
    assert MM_PER_INCH == 25.4
    assert mm_per_day_to_month_total_mm(2.0, 2024, 2) == pytest.approx(58.0)   # leap February
    assert mm_per_day_to_month_total_mm(2.0, 2025, 2) == pytest.approx(56.0)


def test_read_cpc_daily_binary_orientation_and_units():
    rain = np.full((120, 300), -999.0, dtype="<f4")
    r, c = grid_id_to_rowcol(15432)
    rain[r, c] = 123.0               # 0.1 mm units -> 12.3 mm
    rain[0, 0] = 0.0
    buf = rain.tobytes() + np.ones((120, 300), dtype="<f4").tobytes()   # + gauge-count field
    out = read_cpc_daily_binary(buf)
    assert out.shape == (120, 300)
    assert out[r, c] == pytest.approx(12.3)
    assert out[0, 0] == 0.0
    assert np.isnan(out[5, 5])


def test_fine_grid_to_prf_synthetic():
    # 1/24-degree centres covering PRF grid 15432 (lat 32.75-33.00, lon -97.25 to -97.00)
    lat = 32.75 + (np.arange(6) + 0.5) / 24
    lon = -97.25 + (np.arange(6) + 0.5) / 24
    vals = np.arange(36, dtype=float).reshape(6, 6)
    vals[0, 0] = np.nan
    mean, count = fine_grid_to_prf(vals, lat, lon)
    r, c = grid_id_to_rowcol(15432)
    assert count[r, c] == 35
    assert mean[r, c] == pytest.approx(np.nanmean(vals))
    assert np.isnan(mean[r, c + 1])


def test_fine_grid_to_prf_reproduces_official_measurement():
    """36-cell mean of real nClimGrid-Monthly Mar+Apr 2025 equals the DST's 177.29 mm."""
    fx = json.loads((FIX / "nclimgrid_block_15432_2025MarApr.json").read_text())
    lat, lon = np.array(fx["lat"]), np.array(fx["lon"])
    r, c = grid_id_to_rowcol(15432)
    tot = 0.0
    for key in ("2025-03", "2025-04"):
        mean, count = fine_grid_to_prf(np.array(fx["prcp"][key], dtype=float), lat, lon)
        assert count[r, c] == 36
        tot += mean[r, c]
    assert tot == pytest.approx(177.29, abs=0.01)


def test_trigger_and_stats():
    a = [80, 95, 89.9, np.nan]
    b = [85, 85, 90.0, 50]
    assert trigger_disagreement(a, b, 90) == pytest.approx(2 / 3)
    st = comparison_stats([1, 2, 3, 4], [1, 2, 3, 5])
    assert st["n"] == 4 and st["mae"] == pytest.approx(0.25) and st["bias"] == pytest.approx(-0.25)


def test_handbook_rule_reproduces_adm_as_settled_index():
    """CPC interval totals for grid 15432 (our pull: PSL monthly means to 2018, CPC UPDATED daily
    from 2019) with the FCIC-18150 base period 1948..Y-2 reproduce the as-settled ADM final grid
    indexes for crop years 2021-2026 to RMA's 0.1-point rounding."""
    iv = pd.read_csv(FIX / "cpc_15432_intervals_with_adm.csv")
    out = compute_index(iv, "interval_precip_mm", base_start=1948, base_end=handbook_base_end,
                        round_to=1)
    chk = out.dropna(subset=["final_index_adm"])
    assert len(chk) >= 11
    assert np.abs(chk["index_value"] - chk["final_index_adm"]).max() <= 0.1 + 1e-9
    # the DST's 1951 start would not reproduce the settled values as well
    alt = compute_index(iv, "interval_precip_mm", base_start=1951, base_end=handbook_base_end,
                        round_to=1).dropna(subset=["final_index_adm"])
    assert (np.abs(alt["index_value"] - alt["final_index_adm"]).mean()
            > np.abs(chk["index_value"] - chk["final_index_adm"]).mean())
