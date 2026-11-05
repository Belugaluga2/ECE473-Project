"""Tests for the hedge builder, error-budget instruments and platform backend (repo data, offline)."""
from datetime import date

import numpy as np
import pytest

from agri_hedge import error_budget as eb
from agri_hedge import hedge_builder as hb
from agri_hedge import platform as pf
from agri_hedge.webapp.server import _clean


def test_window_labels():
    assert hb.window_from_label("Apr-May", 0.4).prf_interval == "Apr-May"
    assert hb.window_from_label("Jul", 1).months == (7,)
    assert hb.window_from_label("Jun-Aug", 1).months == (6, 7, 8)
    assert hb.window_from_label("Nov-Jan", 1).months == (11, 12, 1)
    assert hb.window_from_label("Jun-Aug", 1).prf_interval is None


def test_contract_month_rolls_current_month():
    t = date(2026, 11, 5)
    assert pf.contract_month_for(12, t) == "2026-12"
    assert pf.contract_month_for(11, t) == "2027-11"
    assert pf.contract_month_for(4, t) == "2027-04"
    assert pf.event_ticker("KXRAINDALM", "2027-04") == "KXRAINDALM-27APR"


def test_farm_target_matches_prf_indemnity():
    F = hb.load_farm_requests()[0]
    p = hb.build_problem(F["request"])
    prf = F["prf_ncei_usd"].reindex(p.years).to_numpy(float)
    ok = ~np.isnan(prf) & ~np.isnan(p.target)
    assert np.nanmax(np.abs(p.target[ok] - prf[ok])) < 0.01 * F["protection"]


def test_dedupe_drops_identical_columns():
    X = np.array([[1, 1, 0], [0, 0, 1], [1, 1, 1]], float)
    Xd, lab, q = eb.dedupe(X, ["a", "b", "c"], [0.1, 0.2, 0.3])
    assert lab == ["a", "c"] and Xd.shape == (3, 2)


def test_grid_index_binaries_nearly_replicate_prf():
    F = hb.load_farm_requests()[0]
    p = hb.build_problem(F["request"])
    X, _, q = eb.grid_index_ladder_cols(p, 5.0)
    from agri_hedge import optimizer as op
    ok = p.ok & ~np.isnan(X).any(axis=1)
    sol = op.solve_penalized(X[ok], p.target[ok], op.model_tranches(q), 0.0, F["protection"])
    assert op.hedge_effectiveness(p.target[ok], sol.payout) > 0.97


def test_quote_offline_model_prices():
    q = pf.quote({"lat": 32.78, "lon": -97.81, "coverage": 0.9, "protection": 50000,
                  "windows": [{"label": "Apr-May", "share": 0.5}, {"label": "Jul", "share": 0.5}],
                  "price_source": "model", "budget": 2000}, loyo=False)
    assert q["station"]["key"] == "DFW"
    assert q["hedge"]["cost_usd"] <= 2000 * 1.001
    assert q["hedge"]["legs_priced_from_order_book"] == 0
    assert all(t["side"] == "NO" and t["contracts"] > 0 for t in q["ticket"])
    assert len(q["backtest"]["years"]) == len(q["backtest"]["hedge_usd"])


def test_quote_rejects_bad_input():
    with pytest.raises(ValueError):
        pf.parse_request({"lat": 32.8, "lon": -97.8, "windows": [], "protection": 1})
    with pytest.raises(ValueError):
        pf.quote({"lat": 44.0, "lon": -120.0, "windows": [{"label": "Jul", "share": 1}], "protection": 1000,
                  "price_source": "model"}, loyo=False)


def test_live_quotes_fall_back_to_snapshot():
    lq = pf.LiveQuotes(offline=True)
    books = lq.series_books("KXRAINDALM")
    assert books and all(v["source"] == "snapshot" for v in books.values())


def test_json_clean():
    assert _clean({"a": float("nan"), "b": [np.float64(1.5), np.int64(2)]}) == {"a": None, "b": [1.5, 2]}


def test_cpc_index_target_matches_as_paid_prf():
    import pandas as pd
    from agri_hedge.config import PROCESSED
    F = hb.load_farm_requests()[0]
    r = F["request"]
    req = hb.CoverageRequest(r.lat, r.lon, r.windows, r.coverage, r.protection, station_key=r.station_key,
                             grid_id=r.grid_id, index="cpc")
    p = hb.build_problem(req, years=hb.CPC_YEARS)
    fy = pd.read_csv(PROCESSED / "payout_comparison_farm_year.csv")
    a = fy[fy["farm_id"] == F["farm_id"]].set_index("year")["prf_cpc_as_paid_usd"].reindex(p.years).to_numpy(float)
    ok = ~np.isnan(a) & ~np.isnan(p.target)
    assert ok.sum() > 50 and np.max(np.abs(a[ok] - p.target[ok])) < 0.005 * F["protection"]


def test_companion_scores_only_uncovered_months():
    c = pf.companion({"lat": 32.78, "lon": -97.81, "coverage": 0.9, "protection": 36000,
                      "prf_intervals": [{"label": "Apr-May", "share": 0.5}, {"label": "Jul-Aug", "share": 0.5}],
                      "price_source": "model"})
    covered = {m["name"] for m in c["months"] if m["covered_by_prf"]}
    assert covered == {"Apr", "May", "Jul", "Aug"}
    open_months = [m for m in c["months"] if not m["covered_by_prf"]]
    assert all("he_out_of_sample" in m for m in open_months)
    assert set(c["recommended_months"]) <= {m["name"] for m in open_months}
    if c["package"]:
        assert c["package"]["hedge"]["legs"] > 0 and len(c["package"]["backtest"]["prf_usd"]) == len(c["package"]["backtest"]["years"])
