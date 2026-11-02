"""Tests for the independent SOB fact-check aggregation (scripts/factcheck_sob.py)."""
import importlib.util
from pathlib import Path

import pandas as pd
import pytest

_SPEC = importlib.util.spec_from_file_location(
    "factcheck_sob", Path(__file__).resolve().parents[1] / "scripts" / "factcheck_sob.py")
fc = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(fc)


def _row(state, commodity, plan, qty_type, qty, liab, prem, sub, ind, pol_ep=1, pol_ind=0):
    r = [""] * 28
    r[2], r[5], r[7], r[17] = f"{state} ", f"{commodity:04d}", f"{plan:02d}", f"{qty_type}   "
    r[13], r[14], r[18] = str(pol_ep), str(pol_ind), str(qty)
    r[20], r[21], r[22], r[26] = str(liab), str(prem), str(sub), str(ind)
    return r


def _frame():
    rows = [
        _row("TX", 88, 13, "Acres", 1000, 20000, 4000, 2000, 6000, pol_ep=2, pol_ind=2),
        _row("OK", 88, 13, "Acres", 500, 10000, 2000, 1100, 900, pol_ep=1, pol_ind=0),
        _row("TX", 41, 2, "Acres", 300, 90000, 9000, 5000, 3000),  # corn RP, not PRF
        _row("TX", 88, 14, "Acres", 50, 700, 100, 50, 0),  # retired VI plan, excluded from PRF
    ]
    return fc.tidy(pd.DataFrame(rows))


def test_year_totals_separates_prf_from_crop_book():
    t = fc.year_totals(_frame())
    assert t["all_liab"] == 20000 + 10000 + 90000 + 700
    assert t["all_acres"] == 1850
    assert t["prf_liab"] == 30000
    assert t["prf_prem"] == 6000 and t["prf_sub"] == 3100 and t["prf_ind"] == 6900
    assert t["prf_pol_ep"] == 3 and t["prf_pol_ind"] == 2


def test_pooled_ratios():
    p = fc.pooled(prem=7933.567178, sub=4216.584981, ind=7836.317918)
    assert p["loss_ratio"] == pytest.approx(0.9877, abs=1e-4)
    assert p["return_per_producer_dollar"] == pytest.approx(2.108, abs=1e-3)
    assert p["subsidy_share"] == pytest.approx(0.5315, abs=1e-4)


def test_state_pooled_sums_across_years():
    f = _frame()
    st = fc.state_pooled([f, f])
    assert st.loc["TX", "prem"] == 8000
    assert st.loc["TX", "loss_ratio"] == pytest.approx(1.5)
    assert st.loc["TX", "ret"] == pytest.approx(12000 / 4000)
    assert st.loc["OK", "ret"] == pytest.approx(1800 / 1800)
