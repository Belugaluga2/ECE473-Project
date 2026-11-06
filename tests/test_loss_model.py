"""Tests for the rain-to-loss model (src/agri_hedge/loss_model.py, doc 13). No network."""
import importlib.util
import re

import numpy as np
import pandas as pd
import pytest

from agri_hedge import loss_model as lm
from agri_hedge.config import PROCESSED, ROOT
from agri_hedge.prf_intervals import INTERVAL_NAMES


@pytest.fixture(scope="module")
def sens():
    return lm.load_sensitivity()


@pytest.fixture(scope="module")
def farms():
    return {f["farm_id"]: f for f in lm.load_farms()}


def _flat_index(value=100.0, years=(2000,)):
    return pd.DataFrame({k: [value] * len(years) for k in INTERVAL_NAMES}, index=list(years))


# ---------------------------------------------------------------------------------------------
# Elasticities and the legacy doc-04b proxy
# ---------------------------------------------------------------------------------------------

def test_elasticity_for_reads_scen_rows(sens):
    e, src = lm.elasticity_for("scen_DEN_graze", sens)
    assert e == pytest.approx(0.742)
    assert "rain_elasticity" in src
    assert lm.elasticity_for("no_such_row", sens)[0] == 1.0
    assert lm.elasticity_for(None, sens)[0] == 1.0


def test_reproduces_committed_04b_forage_loss(farms, sens):
    """Zero curvature + gains floored at 0 must equal run_scenarios' forage_loss_usd exactly."""
    res = pd.read_csv(PROCESSED / "prf_scenario_results.csv")
    for fid, g in res.groupby("farm_id"):
        m = lm.build_farm_model(farms[fid], sens, curvature=False)
        assert m.elasticity == pytest.approx(g["elasticity"].iloc[0])
        assert m.value_per_acre == pytest.approx(g["value_per_acre_usd"].iloc[0])
        idx = g.set_index("year")[[f"index_{k}" for k in INTERVAL_NAMES]]
        idx.columns = INTERVAL_NAMES
        got = m.loss_usd(idx, gains=False)
        np.testing.assert_allclose(got.to_numpy(), g["forage_loss_usd"].to_numpy(), atol=0.01)
        np.testing.assert_allclose(m.season_index(idx).to_numpy(), g["weighted_index"].to_numpy(), atol=1e-6)


def test_legacy_proxy_matches_model(farms, sens):
    m = lm.build_farm_model(farms["DFW_hay"], sens, curvature=False)
    idx = pd.DataFrame({k: [60.0, 100.0, 140.0] for k in INTERVAL_NAMES}, index=[1, 2, 3])
    proxy = lm.forage_loss_proxy(m.value_per_acre, m.acres, m.season_index(idx), m.elasticity)
    np.testing.assert_allclose(m.loss_usd(idx, gains=False).to_numpy(), proxy.to_numpy())


# ---------------------------------------------------------------------------------------------
# Response curve
# ---------------------------------------------------------------------------------------------

def test_linear_response_is_symmetric():
    assert lm.production_response(0.2, 0.5) == pytest.approx(0.1)
    assert lm.production_response(-0.2, 0.5) == pytest.approx(-0.1)


def test_curvature_makes_dry_hurt_more():
    dry, wet = lm.production_response(-0.3, 0.5, -0.5), lm.production_response(0.3, 0.5, -0.5)
    assert -dry > wet > 0
    assert dry == pytest.approx(0.5 * (-0.3 - 0.5 * 0.09))


def test_saturation_and_excess_penalty():
    g = -1.0  # vertex at x* = 0.5
    peak = lm.production_response(0.5, 0.4, g)
    assert lm.production_response(1.0, 0.4, g) == pytest.approx(peak)          # saturates
    assert lm.production_response(1.0, 0.4, g, excess_penalty=True) < peak     # excess rain hurts
    assert lm.production_response(1.0, 0.4, g, excess_penalty=True) == pytest.approx(0.0)


def test_floor_and_positive_curvature_rejected():
    assert lm.production_response(-1.0, 1.5, -1.0) == -1.0
    with pytest.raises(ValueError):
        lm.production_response(0.1, 0.5, 0.2)


def test_series_in_series_out():
    x = pd.Series([-0.5, 0.0, 0.5], index=[2020, 2021, 2022])
    out = lm.production_response(x, 0.5)
    assert isinstance(out, pd.Series) and list(out.index) == [2020, 2021, 2022]


# ---------------------------------------------------------------------------------------------
# Curvature calibration from the CSV quadratics
# ---------------------------------------------------------------------------------------------

def test_parse_quadratic_note():
    assert lm.parse_quadratic_note("quadratic exact +1/-1/-2 in = +0.067/-0.084/-0.185 t/ac") == (0.067, -0.084, -0.185)
    with pytest.raises(ValueError):
        lm.parse_quadratic_note("no quadratic here")


def test_curvature_formula_hand_value(sens):
    # Elbert: +70 / -73 lb, Apr-Jul normal 9.8 in -> a = -1.5, b = 71.5, g = -1.5/71.5*9.8
    c = lm.curvature_for_row(sens, "forage_rangeland_CO_Elbert_AprJul")
    assert c["curvature_raw"] == pytest.approx(-1.5 / 71.5 * 9.8)


@pytest.mark.parametrize("row", lm.POOLED_CURVATURE_ROWS)
def test_quadratic_reproduces_documented_minus2(sens, row):
    """The quadratic implied by +1/-1 must reproduce the separately documented -2 in value."""
    c = lm.curvature_for_row(sens, row)
    assert c["minus2_implied"] == pytest.approx(c["minus2"], abs=max(0.02 * abs(c["minus2"]), 0.003))


def test_farm_curvature_rules(sens):
    g_fl, src = lm.curvature_for_farm("TPA_hay", sens)
    assert g_fl == 0.0 and "clamped" in src
    g_sat, src = lm.curvature_for_farm("SAT_graze", sens)
    assert g_sat == pytest.approx(lm.pooled_curvature(sens)) and "pooled" in src
    assert all(lm.curvature_for_farm(f, sens)[0] <= 0 for f in lm.FARM_CURVATURE_ROW)


# ---------------------------------------------------------------------------------------------
# Timing weights and rain inputs
# ---------------------------------------------------------------------------------------------

def test_growth_weights_hand_value():
    curve = [0] * 12
    curve[5] = 100  # all growth in June
    w = lm.growth_timing_weights(curve, lead=True)   # rain credited half to May, half to June
    assert w == pytest.approx({"May-Jun": 1.0})
    curve[5], curve[6] = 50, 50                      # June + July growth
    w = lm.growth_timing_weights(curve, lead=True)   # May 0.25, Jun 0.5, Jul 0.25
    assert w["May-Jun"] == pytest.approx(0.75) and w["Jul-Aug"] == pytest.approx(0.25)
    assert lm.growth_timing_weights(curve, lead=False)["May-Jun"] == pytest.approx(0.5)


@pytest.mark.parametrize("fid", list(lm.FARM_GROWTH_CURVES))
def test_farm_growth_weights_valid(fid):
    w = lm.farm_growth_weights(fid)
    assert sum(w.values()) == pytest.approx(1.0)
    assert set(w) <= set(lm.CALENDAR_PAIRS)


def test_growth_curves_sum_near_100():
    for name, c in lm.GROWTH_CURVES.items():
        assert len(c) == 12
        assert 99 <= sum(c) <= 102, name   # FSG bahiagrass curve sums to 102 as published


def test_normalize_weights_rejects_overlap():
    with pytest.raises(ValueError):
        lm.normalize_weights({"Apr-May": 0.5, "May-Jun": 0.5})
    assert lm.normalize_weights({"Apr-May": 2, "Jul-Aug": 2, "Sep-Oct": 0}) == {"Apr-May": 0.5, "Jul-Aug": 0.5}


def test_interval_index_from_monthly():
    monthly = pd.DataFrame({m: [1.0] for m in range(1, 13)}, index=[2020])
    monthly[4], monthly[5] = 1.0, 3.0
    normals = {m: 2.0 for m in range(1, 13)}
    idx = lm.interval_index_from_monthly(monthly, normals)
    assert idx.loc[2020, "Apr-May"] == pytest.approx(100.0)      # (1 + 3) / (2 + 2)
    assert idx.loc[2020, "Jan-Feb"] == pytest.approx(50.0)


def test_loss_from_monthly_matches_interval_path(farms, sens):
    m = lm.build_farm_model(farms["DEN_graze"], sens)
    rng = np.random.default_rng(0)
    monthly = pd.DataFrame(rng.uniform(0.2, 4.0, size=(5, 12)), columns=range(1, 13), index=range(2001, 2006))
    normals = {mo: 2.0 for mo in range(1, 13)}
    idx = lm.interval_index_from_monthly(monthly, normals)
    np.testing.assert_allclose(m.loss_from_monthly(monthly, normals).to_numpy(), m.loss_usd(idx).to_numpy())


# ---------------------------------------------------------------------------------------------
# Values, irrigation, signs
# ---------------------------------------------------------------------------------------------

def test_value_bases(farms):
    den, hay = farms["DEN_graze"], farms["DFW_hay"]
    assert lm.value_per_acre(den, "rent") == pytest.approx(6.1)
    assert lm.value_per_acre(den, "replacement") == pytest.approx(1364 * 0.25 * 151 / 2000)   # 03b: 25.7
    assert lm.value_per_acre(hay, "replacement") == lm.value_per_acre(hay, "rent")
    assert lm.value_per_acre(den, "protection") == pytest.approx(13.5 * 1.45)
    with pytest.raises(ValueError):
        lm.value_per_acre(den, "bogus")


def test_replacement_values_match_doc_03b(farms):
    doc = {"DFW_graze": 67.0, "SAT_graze": 57.4, "OKC_graze": 52.3, "SGF_graze": 54.2,
           "DEN_graze": 25.7, "ABQ_graze": 27.4, "TPA_graze": 81.6}
    for fid, v in doc.items():
        assert lm.value_per_acre(farms[fid], "replacement") == pytest.approx(v, abs=0.06)


def test_irrigation_share_scales_loss(farms, sens):
    f = dict(farms["DFW_hay"])
    dry = _flat_index(50.0)
    base = lm.build_farm_model(f, sens).loss_usd(dry).iloc[0]
    f["irrigated_share"] = 0.4
    assert lm.build_farm_model(f, sens).loss_usd(dry).iloc[0] == pytest.approx(0.6 * base)
    f.pop("irrigated_share")
    f["irrigation_practice"] = "irrigated"
    assert lm.build_farm_model(f, sens).loss_usd(dry).iloc[0] == 0.0
    assert all(lm.irrigated_share_of(x) == 0.0 for x in farms.values())


def test_signs_and_normal_year(farms, sens):
    for f in farms.values():
        m = lm.build_farm_model(f, sens, timing="growth", value_basis="replacement")
        assert m.loss_usd(_flat_index(100.0)).iloc[0] == pytest.approx(0.0, abs=1e-9)
        assert m.loss_usd(_flat_index(60.0)).iloc[0] > 0
        assert m.loss_usd(_flat_index(140.0)).iloc[0] <= 0
        assert m.loss_usd({k: 60.0 for k in m.timing_weights}) == pytest.approx(m.loss_usd(_flat_index(60.0)).iloc[0])


def test_hand_computed_farm_loss(farms, sens):
    # DEN_graze, all intervals at 70: x = -0.3, dP = 0.742 (-0.3 + g 0.09), loss = -dP x 6.1 x 7000
    m = lm.build_farm_model(farms["DEN_graze"], sens)
    g = -1.5 / 71.5 * 9.8
    expected = -0.742 * (-0.3 + g * 0.09) * 6.1 * 7000
    assert m.loss_usd(_flat_index(70.0)).iloc[0] == pytest.approx(expected)


def test_irrigated_share_for():
    assert lm.irrigated_share_for("NEBRASKA", "corn") == pytest.approx(0.527)
    assert lm.irrigated_share_for("arkansas", "soybeans") == pytest.approx(0.760)


# ---------------------------------------------------------------------------------------------
# Row crops: must reproduce doc 03a (VERIFIED) exact changes from the CSV notes
# ---------------------------------------------------------------------------------------------

_EXACT = re.compile(r"exact \+1 in = ([+\-]?[\d.]+) bu/ac, -1 in = ([+\-]?[\d.]+) bu/ac, -2 in = ([+\-]?[\d.]+) bu/ac")
_TERM = {"May": "may", "June": "jun", "July": "jul", "August": "aug"}


@pytest.mark.parametrize("spec", ["update 1980-2025", "rain-only 1980-2025"])
@pytest.mark.parametrize("crop", ["corn", "soybeans"])
@pytest.mark.parametrize("state", ["IL", "IN", "IA"])
def test_rowcrop_matches_csv_exact_changes(spec, crop, state):
    m = lm.load_rowcrop_model(crop, state, spec)
    s = pd.read_csv(lm.SENS_CORN_SOY_CSV)
    s = s[(s["crop"] == crop) & (s["region"] == state) & s["model_type"].str.endswith(lm._SPEC_MODEL_TYPE[spec])]
    checked = 0
    for _, r in s.iterrows():
        term = _TERM.get(r["month_or_window"])
        mt = _EXACT.search(str(r["valid_range_note"]))
        if term is None or mt is None:
            continue
        n = m.normals[term]
        for delta, want in zip((1, -1, -2), map(float, mt.groups())):
            # tolerance 0.05 bu/ac: the CSV stores normals rounded to 0.01 in, while the r1 script
            # evaluated at unrounded normals (largest observed gap 0.04 bu/ac, IA corn July)
            assert m.yield_change_bu({term: n + delta}) == pytest.approx(want, abs=0.05), (term, delta)
        checked += 1
    assert checked == 4


def test_rowcrop_headline_and_excess_rain():
    m = lm.load_rowcrop_model("corn", "IL", "update 1980-2025")
    n = m.normals
    assert m.yield_change_bu({"jul": n["jul"] - 2}) == pytest.approx(-22.6, abs=0.06)   # doc 03a headline
    assert m.optimum_in("jul") == pytest.approx(5.76, abs=0.01)
    assert m.yield_change_bu({"may": n["may"] + 1}) < 0                                   # wet May hurts
    past = m.optimum_in("jun") + 2
    assert m.yield_change_bu({"jun": past}) < m.yield_change_bu({"jun": m.optimum_in("jun")})
    assert m.loss_usd({"jul": n["jul"] - 2}, acres=1000) == pytest.approx(22.55 * 4.70 * 1000, rel=0.003)
    assert m.loss_usd({"jul": n["jul"] - 2}, acres=1000, irrigated_share=0.5) == pytest.approx(
        0.5 * m.loss_usd({"jul": n["jul"] - 2}, acres=1000))
    assert m.yield_change_bu({}) == 0.0


# ---------------------------------------------------------------------------------------------
# Backtest helper
# ---------------------------------------------------------------------------------------------

def _script():
    spec = importlib.util.spec_from_file_location("run_loss_model", ROOT / "scripts" / "run_loss_model.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_coverage_metrics_hand_example():
    r = _script()
    loss = pd.Series([100.0, -50.0, 0.0, 300.0])
    pay = pd.Series([150.0, 20.0, 0.0, 0.0])
    m = r.coverage_metrics(loss, pay, normal_value=1000.0, cost=10.0)
    assert m["modeled_loss_sum_usd"] == 400.0 and m["payout_sum_usd"] == 170.0
    assert m["capped_coverage"] == pytest.approx(100 / 400)
    assert m["n_loss_years"] == 2 and m["n_loss_years_unpaid"] == 1 and m["n_paid_no_loss"] == 1
    assert m["mean_net_outcome_usd"] == pytest.approx((170 - 350) / 4 - 10)


# ---------------------------------------------------------------------------------------------
# Review fixes (final/lossmodel): curvature window matching and marginal $ per point / inch
# ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("fid", ["DFW_hay", "OKC_hay"])
def test_hay_curvature_window_matches_elasticity_window(sens, fid):
    """DFW_hay and OKC_hay elasticities use rain over the insured Apr-Sep months (scen rows'
    baseline 16.55 / 22.0 in), so their curvature must come from the Apr-Sep quadratic."""
    key = lm.FARM_CURVATURE_ROW[fid]
    scen = sens[sens["row_key"] == f"scen_{fid}"].iloc[0]
    row = sens[sens["row_key"] == key].iloc[0]
    assert key.endswith("AprSep")
    assert row["baseline_precip_in"] == pytest.approx(scen["baseline_precip_in"])


def test_okc_hay_curvature_hand_value(sens):
    # OK Apr-Sep: +0.035 / -0.038 t, normal 22.0 in -> a = -0.0015, b = 0.0365, g = a/b*22
    g, src = lm.curvature_for_farm("OKC_hay", sens)
    assert g == pytest.approx(-0.0015 / 0.0365 * 22.0)
    c = lm.curvature_for_row(sens, "hay_other_OK_state_AprSep")
    assert c["minus2_implied"] == pytest.approx(c["minus2"], abs=0.003)


@pytest.mark.parametrize("fid", ["DFW_hay", "SGF_hay", "DEN_graze", "TPA_hay"])
@pytest.mark.parametrize("level", [45.0, 80.0, 97.0, 110.0])
def test_marginal_loss_per_point_matches_finite_difference(farms, sens, fid, level):
    m = lm.build_farm_model(farms[fid], sens)
    base = {k: level for k in m.timing_weights}
    marg = m.marginal_loss_per_point(base)
    h = 1e-4
    for k in m.timing_weights:
        lo = dict(base, **{k: level - h})
        hi = dict(base, **{k: level + h})
        fd = (m.loss_usd(lo) - m.loss_usd(hi)) / (2 * h)   # extra loss per point of LESS rain
        assert marg[k] == pytest.approx(fd, rel=1e-4, abs=1e-6)


def test_marginal_loss_zero_on_plateau_and_when_gains_off(farms, sens):
    m = lm.build_farm_model(farms["SGF_hay"], sens)        # saturates at season index ~126
    wet = {k: 200.0 for k in m.timing_weights}
    assert all(v == 0.0 for v in m.marginal_loss_per_point(wet).values())
    mild_wet = {k: 110.0 for k in m.timing_weights}
    assert all(v > 0 for v in m.marginal_loss_per_point(mild_wet).values())
    assert all(v == 0.0 for v in m.marginal_loss_per_point(mild_wet, gains=False).values())
    with pytest.raises(TypeError):
        m.marginal_loss_per_point(_flat_index())


def test_marginal_loss_per_inch_scales_by_interval_normal(farms, sens):
    m = lm.build_farm_model(farms["DEN_graze"], sens)
    idx = {k: 70.0 for k in m.timing_weights}
    normals = {k: 2.0 + i for i, k in enumerate(m.timing_weights)}
    pp, pi = m.marginal_loss_per_point(idx), m.marginal_loss_per_inch(idx, normals)
    for k in m.timing_weights:
        assert pi[k] == pytest.approx(pp[k] * 100.0 / normals[k])
