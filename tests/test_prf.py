"""Tests for agri_hedge.prf, the PRF premium/indemnity calculator.

1. Every number in the worked examples of the 2026 Rainfall Index Handbook (FCIC-18150) para 14
   and Exhibit 5 is reproduced exactly ("official" rounding).
2. RMA's Decision Support Tool outputs for 7 odd elections (fixture tests/fixtures/b4/
   dst_pricing_probes.json) are reproduced exactly ("dst" rounding).
3. Payment calculation factors equal RMA's published ADM "Payment Factor" (fixture
   adm_payment_factor_sample.csv), including half-way rounding cases.
4. Edge cases and election validation.
No network access is needed.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from agri_hedge import prf
from agri_hedge.prf import (
    PRFElection,
    PRFElectionError,
    dollar_amount_of_protection_per_acre,
    indemnity_per_unit,
    payment_calculation_factor,
    policy_protection_per_unit,
    policy_table,
    policy_totals,
    premium_per_unit,
    premium_subsidy_rate,
    round_half_up,
    simulate_years,
    summarize_years,
    trigger_grid_index,
    validate_election,
)
from agri_hedge.prf_intervals import INTERVAL_CODES, INTERVAL_NAMES, VERIFIED

FIX = Path(__file__).parent / "fixtures" / "b4"


# ---------------------------------------------------------------------------------------------
# Handbook para 14 (Percent of Value) example
# ---------------------------------------------------------------------------------------------

def test_handbook_para14_percent_of_value_example():
    # $20.00 CBV, 90% coverage, 120% productivity factor, 1,000 acres, 60/40 Apr-May/Jul-Aug.
    ppa = dollar_amount_of_protection_per_acre(20.00, 0.90, 1.20)
    assert ppa == pytest.approx(21.60)
    assert policy_protection_per_unit(ppa, 1000, 1.0) == pytest.approx(21_600)
    assert policy_protection_per_unit(ppa, 1000, 0.60, 1.00) == pytest.approx(12_960)
    assert policy_protection_per_unit(ppa, 1000, 0.40, 1.00) == pytest.approx(8_640)


# ---------------------------------------------------------------------------------------------
# Handbook Exhibit 5: four grids, two intervals (628 Apr-May 60%, 631 Jul-Aug 40%)
# ---------------------------------------------------------------------------------------------

EX5_RATES = {628: 0.1000, 631: 0.1100}
EX5_ACRES = {1: 100.0, 2: 50.0, 3: 100.0, 4: 245.0}
# Final grid indexes in each scenario: {scenario: {grid: (index 628, index 631)}}
EX5_SCENARIOS = {
    1: {1: (120, 90), 2: (120, 90), 3: (120, 85), 4: (120, 85)},
    2: {1: (80, 70), 2: (80, 70), 3: (95, 65), 4: (95, 65)},
    3: {1: (80, 120), 2: (80, 120), 3: (60, 120), 4: (60, 120)},
}


def _ex5_election(grid):
    return PRFElection(grid_id=grid, county_base_value=20.00, coverage_level=0.90,
                       productivity_factor=1.20, insured_acres=EX5_ACRES[grid],
                       allocation={628: 0.60, 631: 0.40}, intended_use="grazing")


def test_exhibit5_protection_and_premium():
    tables = [policy_table(_ex5_election(g), EX5_RATES, rounding="official") for g in (1, 2, 3, 4)]
    assert tables[0].attrs["totals"]["protection_per_acre"] == pytest.approx(21.60)
    protection = [list(t["policy_protection"]) for t in tables]
    assert protection == [[1296, 864], [648, 432], [1296, 864], [3175, 2117]]
    premium = [list(t["total_premium"]) for t in tables]
    assert premium == [[130, 95], [65, 48], [130, 95], [318, 233]]
    tot = policy_totals(tables, rounding="official")
    assert tot["policy_protection"] == 10_692
    assert tot["total_premium"] == 1_114
    assert tot["premium_subsidy"] == 568          # 51% subsidy at 90% coverage
    assert tot["producer_premium"] == 546
    assert premium_subsidy_rate(0.90) == 0.51
    assert trigger_grid_index(0.90) == pytest.approx(90.0)


def test_exhibit5_payment_calculation_factors():
    pcf = payment_calculation_factor(np.array([80, 60, 85, 70, 65, 90, 95, 120]), 90.0)
    assert list(pcf) == [0.111, 0.333, 0.056, 0.222, 0.278, 0.0, 0.0, 0.0]


@pytest.mark.parametrize("scenario,expected_units,expected_total", [
    # expected indemnity per grid: (interval 628, interval 631)
    (1, {1: (0, 0), 2: (0, 0), 3: (0, 48), 4: (0, 119)}, 167),
    (2, {1: (144, 192), 2: (72, 96), 3: (0, 240), 4: (0, 588)}, 1_332),
    (3, {1: (144, 0), 2: (72, 0), 3: (432, 0), 4: (1_057, 0)}, 1_705),
])
def test_exhibit5_indemnity_scenarios(scenario, expected_units, expected_total):
    total = 0
    for grid, (i628, i631) in EX5_SCENARIOS[scenario].items():
        t = policy_table(_ex5_election(grid), EX5_RATES, {628: i628, 631: i631}, rounding="official")
        assert tuple(t["indemnity"]) == expected_units[grid], (scenario, grid)
        total += t.attrs["totals"]["indemnity"]
    assert total == expected_total


# ---------------------------------------------------------------------------------------------
# RMA Decision Support Tool reproduction
# ---------------------------------------------------------------------------------------------

def _dst_probes():
    path = FIX / "dst_pricing_probes.json"
    if not path.exists():
        pytest.skip("DST fixture missing; run scripts/pull_prf_actuarial.py --fixtures")
    return json.loads(path.read_text())["probes"]


def test_dst_probes_reproduced_exactly():
    for probe in _dst_probes():
        p = probe["params"]
        rows = probe["PricingRateRows"]
        use = {"007": "grazing", "030": "haying"}[p["intendedUseCode"]]
        e = PRFElection(
            grid_id=p["gridId"], county_base_value=probe["PricingRateSummary"]["CountyBaseValue"],
            coverage_level=p["coverageLevelPercent"], productivity_factor=p["productivityFactor"],
            insured_acres=p["insuredAcres"], share=p["insurableInterest"],
            allocation={int(r["IntervalCode"]): r["PercentOfValue"] for r in rows},
            intended_use=use, irrigation_practice=p["irrigationPracticeCode"],
            organic_practice=p["organicPracticeCode"])
        rates = {int(r["IntervalCode"]): r["PremiumRate"] for r in rows}
        final = {int(r["IntervalCode"]): r["PercentOfNormal"] * 100 for r in rows}
        t = policy_table(e, rates, final, rounding="dst", max_percent_of_value=0.63)
        assert t.attrs["totals"]["subsidy_rate"] == probe["PricingRateSummary"]["SubsidyLevel"]
        for col, key in [("policy_protection", "PolicyProtection"), ("total_premium", "TotalPremium"),
                         ("premium_subsidy", "PremiumSubsidy"), ("producer_premium", "ProducerPremium"),
                         ("indemnity", "Indemnity")]:
            assert list(t[col]) == [r[key] for r in rows], (p, col)
        tot = probe["PricingRateRowTotalSummary"]
        assert t.attrs["totals"]["policy_protection"] == tot["PolicyProtection"]
        assert t.attrs["totals"]["total_premium"] == tot["TotalPremium"]
        assert t.attrs["totals"]["premium_subsidy"] == tot["PremiumSubsidy"]
        assert t.attrs["totals"]["indemnity"] == tot["Indemnity"]


# ---------------------------------------------------------------------------------------------
# ADM published payment factors
# ---------------------------------------------------------------------------------------------

def test_payment_factor_matches_adm_published_values():
    path = FIX / "adm_payment_factor_sample.csv"
    if not path.exists():
        pytest.skip("ADM fixture missing; run scripts/pull_prf_actuarial.py --fixtures")
    df = pd.read_csv(path)
    pcf = payment_calculation_factor(df["final_index_adm"], trigger_grid_index(df["coverage_level"]))
    assert isinstance(pcf, pd.Series)
    np.testing.assert_allclose(pcf.to_numpy(), df["payment_factor_adm"].to_numpy(), atol=1e-12)


# ---------------------------------------------------------------------------------------------
# Edge cases and vectorization
# ---------------------------------------------------------------------------------------------

def test_index_exactly_at_trigger_pays_nothing():
    assert payment_calculation_factor(90.0, 90.0) == 0.0
    assert payment_calculation_factor(70.0, trigger_grid_index(0.70)) == 0.0
    assert payment_calculation_factor(89.9, 90.0, decimals=None) == pytest.approx(0.1 / 90)


def test_index_zero_pays_full_unit_protection():
    assert payment_calculation_factor(0.0, 90.0) == 1.0
    assert indemnity_per_unit(1.0, 12_960.0) == 12_960.0
    e = _ex5_election(1)
    t = policy_table(e, EX5_RATES, {628: 0.0, 631: 0.0}, rounding="official")
    assert list(t["indemnity"]) == list(t["policy_protection"])


def test_missing_index_gives_nan_not_zero():
    pcf = payment_calculation_factor(np.array([np.nan, 50.0]), 90.0)
    assert np.isnan(pcf[0]) and pcf[1] == pytest.approx(0.444)


def test_vectorized_over_years_keeps_series_index():
    idx = pd.Series([120.0, 80.0, 45.5, 90.0], index=[2019, 2020, 2021, 2022], name="Apr-May")
    pcf = payment_calculation_factor(idx, 90.0, decimals=None)
    assert isinstance(pcf, pd.Series) and list(pcf.index) == [2019, 2020, 2021, 2022]
    np.testing.assert_allclose(pcf.to_numpy(), [0, 10 / 90, 44.5 / 90, 0])
    ind = indemnity_per_unit(pcf, 1000.0)
    np.testing.assert_allclose(ind.to_numpy(), [0, 1000 * 10 / 90, 1000 * 44.5 / 90, 0])
    prem = premium_per_unit(np.array([1000.0, 2000.0]), np.array([0.1, 0.2]))
    np.testing.assert_allclose(prem, [100.0, 400.0])
    np.testing.assert_allclose(premium_subsidy_rate(np.array([0.7, 0.8, 0.9])), [0.59, 0.55, 0.51])


def test_round_half_up():
    assert round_half_up(2.5) == 3.0
    assert round_half_up(317.5) == 318.0
    assert round_half_up(3175 * 0.1) == 318.0          # float 317.49999... still rounds up
    assert round_half_up(0.3025, 3) == 0.303
    assert round_half_up(0.1105, 3) == 0.111
    np.testing.assert_allclose(round_half_up(np.array([1.4999, 1.5, 2.5])), [1, 2, 3])


def test_simulate_years_matches_single_year_tables():
    e = _ex5_election(4)
    years = pd.DataFrame({"Apr-May": [120, 95, 60], "Jul-Aug": [85, 65, 120]}, index=[2001, 2002, 2003])
    long = simulate_years(e, EX5_RATES, years, rounding="official")
    summ = summarize_years(long)
    for y, (a, b) in zip(years.index, years.itertuples(index=False)):
        t = policy_table(e, EX5_RATES, {"Apr-May": a, "Jul-Aug": b}, rounding="official")
        assert summ.loc[y, "indemnity"] == t.attrs["totals"]["indemnity"]
    assert list(summ["indemnity"]) == [119, 588, 1057]
    assert summ["total_premium"].iloc[0] == 551
    assert summ.loc[2003, "net_to_producer"] == pytest.approx(1057 - 551 * 0.49)
    # unrounded mode is smooth and close to the official numbers
    raw = summarize_years(simulate_years(e, EX5_RATES, years, rounding="none"))
    np.testing.assert_allclose(raw["indemnity"], summ["indemnity"], atol=3)


# ---------------------------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------------------------

def _valid(**kw):
    base = dict(grid_id=15429, county_base_value=27.60, coverage_level=0.90, productivity_factor=1.0,
                insured_acres=500, allocation={"Apr-May": 0.5, "Jul-Aug": 0.5})
    base.update(kw)
    return PRFElection(**base)


def test_valid_election_passes_and_accepts_percent_inputs():
    assert validate_election(_valid()) == []
    e = _valid(coverage_level=85, productivity_factor=150, allocation={"628": 50, "Jul-Aug": 50})
    assert e.coverage_level == 0.85 and e.productivity_factor == 1.5
    assert validate_election(e) == []
    assert validate_election(_valid(intended_use="haying", irrigation_practice="non-irrigated",
                                    organic_practice="certified")) == []


@pytest.mark.parametrize("kwargs,fragment", [
    (dict(coverage_level=0.65), "coverage level"),
    (dict(coverage_level=0.95), "coverage level"),
    (dict(coverage_level=0.72), "coverage level"),
    (dict(productivity_factor=0.59), "productivity factor"),
    (dict(productivity_factor=1.51), "productivity factor"),
    (dict(productivity_factor=1.005), "whole percent"),
    (dict(intended_use="silage"), "intended use"),
    (dict(irrigation_practice="irrigated"), "not offered for grazing"),
    (dict(intended_use="haying"), "not offered for haying"),
    (dict(allocation={"Apr-May": 1.0}), "at least 2"),
    (dict(allocation={"Apr-May": 0.5, "May-Jun": 0.5}), "overlap"),
    (dict(allocation={"Apr-May": 0.5, "Jul-Aug": 0.4}), "sum to 100%"),
    (dict(allocation={"Apr-May": 0.45, "Jul-Aug": 0.45, "Oct-Nov": 0.05, "Jan-Feb": 0.05}), "below minimum"),
    (dict(allocation={"Apr-May": 0.7, "Jul-Aug": 0.3}), "above maximum"),
    (dict(insured_acres=0), "insured acres"),
    (dict(share=1.5), "share"),
    (dict(county_base_value=0), "county base value"),
])
def test_invalid_elections_rejected(kwargs, fragment):
    with pytest.raises(PRFElectionError) as err:
        validate_election(_valid(**kwargs), max_percent_of_value=0.60)
    assert any(fragment in m for m in err.value.errors), err.value.errors


def test_state_specific_maximum_and_available_intervals():
    e = _valid(allocation={"Apr-May": 0.55, "Jul-Aug": 0.45})
    assert validate_election(e, max_percent_of_value=0.60) == []
    errs = validate_election(e, max_percent_of_value={"Apr-May": 0.50}, raise_on_error=False)
    assert errs and "above maximum 50%" in errs[0]
    errs = validate_election(_valid(), available_intervals=[625, 626, 627, 628], raise_on_error=False)
    assert errs == ["intervals not offered in the actuarial documents for this grid: ['Jul-Aug']"]


def test_all_errors_reported_together():
    e = _valid(coverage_level=0.6, productivity_factor=2.0, allocation={"Apr-May": 0.9, "May-Jun": 0.2})
    errs = validate_election(e, raise_on_error=False)
    assert len(errs) >= 4


def test_interval_codes_confirmed():
    # RMA ADM table A00480 (2025, 2026): 625 = JAN-FEB ... 635 = NOV-DEC; HB Exhibit 5: 628 Apr-May, 631 Jul-Aug.
    assert VERIFIED is True
    assert INTERVAL_CODES["Jan-Feb"] == 625 and INTERVAL_CODES["Apr-May"] == 628
    assert INTERVAL_CODES["Jul-Aug"] == 631 and INTERVAL_CODES["Nov-Dec"] == 635
    assert prf.interval_name(628) == "Apr-May" and prf.interval_name("631") == "Jul-Aug"
    assert len(INTERVAL_NAMES) == 11


# ---------------------------------------------------------------------------------------------
# Scenario-runner helpers (scripts/run_scenarios.py)
# ---------------------------------------------------------------------------------------------

def _load_runner():
    import importlib.util
    path = Path(__file__).resolve().parents[1] / "scripts" / "run_scenarios.py"
    spec = importlib.util.spec_from_file_location("run_scenarios", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_forage_loss_proxy_and_weighted_index():
    rs = _load_runner()
    idx = pd.DataFrame({"Apr-May": [120.0, 50.0, 200.0], "Jul-Aug": [80.0, 70.0, 40.0]}, index=[1, 2, 3])
    alloc = {"Apr-May": 0.6, "Jul-Aug": 0.4}
    w = rs.weighted_index(idx, alloc)
    np.testing.assert_allclose(w, [104.0, 58.0, 136.0])
    wc = rs.weighted_index(idx, alloc, cap=100.0)          # wet intervals cannot offset dry ones
    np.testing.assert_allclose(wc, [92.0, 58.0, 76.0])
    loss = rs.forage_loss_proxy(50.0, 100.0, w, elasticity=1.0)
    np.testing.assert_allclose(loss, [0.0, 50 * 100 * 0.42, 0.0])
    np.testing.assert_allclose(rs.forage_loss_proxy(50.0, 100.0, wc, 0.5), [200.0, 1050.0, 600.0])
    assert rs.span_intervals(alloc) == ["Apr-May", "May-Jun", "Jun-Jul", "Jul-Aug"]
    assert rs.elasticity_for(None, None)[0] == 1.0
    sens = pd.DataFrame({"row_key": ["hay_tx"], "yield_elasticity_precip": [0.8]})
    assert rs.elasticity_for("hay_tx", sens)[0] == 0.8
    assert rs.elasticity_for("other", sens)[0] == 1.0
