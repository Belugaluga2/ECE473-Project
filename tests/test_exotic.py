"""Tests for exotic payoff shapes and their replication by NO / YES ladders (synthetic + repo data)."""
import numpy as np
import pytest

from agri_hedge import exotic as ex
from agri_hedge import hedge_builder as hb
from agri_hedge import optimizer as op

IDX = np.linspace(0.0, 250.0, 251)


def test_shapes_are_bounded_and_ordered():
    lp = (0.5, -0.5)
    f = {s: ex.payoff(s, IDX, 0.9, lp) for s in ex.SHAPES if s != "persistence"}
    for s, v in f.items():
        assert np.all((v >= -1e-12) & (v <= 1 + 1e-12)), s
        assert v[0] == pytest.approx(1.0), s                      # total loss pays the full amount
    drought = [s for s in f if s != "both_tails"]
    for s in drought:
        assert np.all(f[s][IDX >= 90] == 0), s                    # nothing at or above the trigger
    deep = ex.shortfall(IDX, 0.9) >= 0.1                           # (near zero the exponential is ~linear)
    assert np.all(f["exponential"][deep] <= f["convex2"][deep] + 1e-12)
    assert np.all(f["convex2"] <= f["linear"] + 1e-12)
    assert np.all(f["linear"] <= f["capped"] + 1e-12)
    assert np.all(f["layered"] <= f["linear"] + 1e-12)
    assert f["both_tails"][-1] == pytest.approx(1.0)              # wet tail pays in full at 230%
    assert np.all(f["both_tails"][(IDX >= 90) & (IDX <= 130)] == 0)
    assert f["tiers"][IDX == 60][0] == pytest.approx(0.25)        # below 75 only
    assert f["tiers"][IDX == 50][0] == pytest.approx(0.5)         # below 75 and 55
    assert f["tiers"][IDX == 30][0] == pytest.approx(1.0)         # below 35 too


def test_loss_shape_is_convex_when_curvature_negative():
    f = ex.payoff("loss", IDX, 0.9, (0.5, -1.0))
    s = ex.shortfall(IDX, 0.9)
    m = (s > 0) & (s < 1)
    assert np.all(f[m] <= s[m] + 1e-12)                            # below the linear shape everywhere
    lin = ex.payoff("loss", IDX, 0.9, (0.5, 0.0))
    assert np.allclose(lin, s)                                     # zero curvature = PRF linear
    with pytest.raises(ValueError):
        ex.payoff("loss", IDX, 0.9)


def test_persistence_payoff():
    idx = np.array([30.0, 60.0, 95.0, np.nan])
    m1 = np.array([20.0, 50.0, 80.0, 50.0])
    m2 = np.array([40.0, 95.0, 80.0, 50.0])
    f = ex.persistence_payoff(idx, [m1, m2], 0.9)
    s = ex.shortfall(idx, 0.9)
    assert f[0] == pytest.approx((s[0] + 0.5) / 1.5)               # both months dry: bonus paid
    assert f[1] == pytest.approx(s[1] / 1.5)                       # one wet month: no bonus
    assert f[2] == pytest.approx(0.5 / 1.5)                        # window near normal, both months dry
    assert np.isnan(f[3])


def test_linear_shape_reproduces_prf_target():
    F = hb.load_farm_requests()[0]
    p = hb.build_problem(F["request"])
    y = ex.shape_target(p, "linear")
    ok = ~np.isnan(p.target)
    assert np.nanmax(np.abs(y[ok] - p.target[ok])) < 1e-6


def test_span_step_is_exact_and_long_only():
    strikes = [1.0, 2.0, 3.0, 4.0]
    rng = np.random.default_rng(1)
    rain = rng.gamma(2.0, 1.2, 500)
    vals = np.array([1.0, 0.5, 0.2, 0.0, 0.0])                     # drought shape: falls, then flat
    port = ex.span_step(vals, strikes)
    assert np.all(port.no_weights >= 0) and np.all(port.yes_weights == 0) and port.cash == 0
    b = ex.rain_bins(rain, strikes)
    assert np.allclose(port.payout(rain), vals[b])
    u = np.array([1.0, 0.3, 0.0, 0.4, 1.0])                        # both tails: falls, then rises
    pu = ex.span_step(u, strikes)
    assert pu.cash == pytest.approx(0.0) and np.all(pu.no_weights >= 0) and np.all(pu.yes_weights >= 0)
    assert np.allclose(pu.payout(rain), u[b])
    hump = np.array([0.0, 1.0, 0.0, 0.0, 0.0])                     # a hump needs negative cash
    assert ex.span_step(hump, strikes).cash < 0
    assert ex.is_quasi_convex(vals) and ex.is_quasi_convex(u) and not ex.is_quasi_convex(hump)


def test_binned_values_match_least_squares_ladder_fit():
    strikes = [1.0, 2.0, 3.0, 4.0, 5.0]
    rng = np.random.default_rng(2)
    rain = rng.gamma(2.0, 1.0, 300)
    f = ex.payoff("convex2", 100 * rain / rain.mean(), 0.9)
    vals = ex.binned_values(f, rain, strikes)
    port = ex.span_step(vals, strikes)
    X = np.column_stack([ex.no_pays(rain, k) for k in strikes])
    sol = op.solve_penalized(X, f, op.model_tranches(X.mean(axis=0)), 0.0, 1.0)
    assert np.allclose(sol.leg_contracts, port.no_weights, atol=1e-5)
    assert ex.convexity_ratio(vals) > 1                           # quadratic shape: first drop is the largest


def test_ladder_cols_yes_side_is_complement():
    F = hb.load_farm_requests()[0]
    p = hb.build_problem(F["request"])
    X, lab, q = ex.ladder_cols(p, ex.kalshi_strikes_for(p), ("NO", "YES"))
    by = {l: j for j, l in enumerate(lab)}
    m, k, _ = lab[0]
    if (m, k, "YES") in by and (m, k, "NO") in by:
        a, b = by[(m, k, "NO")], by[(m, k, "YES")]
        ok = ~np.isnan(X[:, a])
        assert np.allclose(X[ok, a] + X[ok, b], 1.0) and q[a] + q[b] == pytest.approx(1.0)


def test_execute_portfolio_walks_cheapest_levels_first():
    port = ex.span_step([1.0, 0.4, 0.0], [1.0, 2.0])
    books = {1.0: {"ticker": "A", "yes_bids": [(0.80, 50), (0.70, 50)], "no_bids": []},
             2.0: {"ticker": "B", "yes_bids": [(0.60, 10)], "no_bids": []}}
    fair = {1.0: 0.20, 2.0: 0.40}
    exd = ex.execute_portfolio(port, 100.0, books, fair, rate=0.0, days=0)
    a = exd[exd["strike_in"] == 1.0].iloc[0]
    assert a["contracts_wanted"] == pytest.approx(60) and a["contracts_filled"] == pytest.approx(60)
    assert a["vwap"] == pytest.approx((50 * 0.20 + 10 * 0.30) / 60)
    b = exd[exd["strike_in"] == 2.0].iloc[0]
    assert b["contracts_wanted"] == pytest.approx(40) and b["contracts_filled"] == pytest.approx(10)
    s = ex.execution_summary(exd, 100.0, 0.3)
    assert s["fill_share"] == pytest.approx(70 / 100) and s["spread_cost_usd"] > 0


def test_tail_metrics():
    y = np.array([0, 0, 0, 10, 0, 0, 0, 0, 0, 100.0])
    h = np.array([0, 0, 5, 10, 0, 0, 0, 0, 0, 50.0])
    assert ex.tail_concentration(y, 0.1) == pytest.approx(100 / 110)
    assert ex.tail_capture(y, h, 0.1) == pytest.approx(0.5)
    assert ex.shortfall_capital(y, h, 100.0, 1.0) == pytest.approx(0.5)
    assert ex.shortfall_capital(y, h, 100.0, 0.5) == pytest.approx(0.0)


def test_exotic_quote_builds_term_sheet_and_ticket():
    from agri_hedge import platform as pf
    q = pf.exotic_quote({"lat": 32.7771, "lon": -97.8059, "month": 11, "shape": "convex2", "max_payout": 6000,
                         "price_source": "model"})
    assert q["product"]["station"] == "DFW" and q["product"]["max_payout_usd"] == 6000
    pays = [t["payout_usd"] for t in q["term_sheet"]]
    assert pays[0] == max(pays) and all(a >= b for a, b in zip(pays, pays[1:]))      # drought shape: falls with rain
    assert q["replication"]["cash_leg"] == pytest.approx(0.0) and q["replication"]["quasi_convex"]
    assert all(t["side"] == "NO" and t["contracts"] > 0 for t in q["ticket"])
    assert sum(t["contracts"] for t in q["ticket"]) == pytest.approx(pays[0], abs=len(q["ticket"]))
    assert 0 < q["pricing"]["fair_premium_usd"] < 6000 and q["pricing"]["fill_share"] == pytest.approx(1.0)
    assert q["farm_basis_risk"] and q["farm_basis_risk"]["he_exchange_vs_farm"] is not None
    assert len(q["backtest"]["years"]) == len(q["backtest"]["payout_usd"])


def test_exotic_quote_both_tails_uses_yes_legs_and_snapshot_books():
    from agri_hedge import platform as pf
    from datetime import date
    q = pf.exotic_quote({"station_key": "DFW", "month": 11, "shape": "both_tails", "max_payout": 1000},
                        live=pf.LiveQuotes(offline=True), today=date(2026, 10, 20))
    sides = {t["side"] for t in q["ticket"]}
    assert sides == {"NO", "YES"}
    assert q["pricing"]["legs_priced_from_order_book"] == len(q["ticket"])
    assert all(t["price_source"] == "snapshot" for t in q["ticket"])
    assert q["pricing"]["fill_share"] is not None and 0 <= q["pricing"]["fill_share"] <= 1
    assert q["farm_basis_risk"] is None                                                # no lat/lon given
    with pytest.raises(ValueError):
        pf.exotic_quote({"station_key": "DFW", "month": 11, "shape": "persistence", "max_payout": 1000})


def test_binned_values_fill_empty_bins_from_the_shape():
    strikes = [1.0, 2.0, 3.0, 4.0]
    rain = np.array([0.2, 0.5, 1.5, 2.5, 2.8])                      # nothing observed above 3 inches
    normal = 2.0
    f = ex.payoff("linear", 100 * rain / normal, 0.9)
    shape_fn = lambda r: float(ex.payoff("linear", np.array([100 * r / normal]), 0.9)[0])  # noqa: E731
    vals = ex.binned_values(f, rain, strikes, shape_fn)
    assert vals[3] == pytest.approx(0.0) and vals[4] == pytest.approx(0.0)   # empty upper bins: the shape, i.e. 0
    assert ex.span_step(vals, strikes).cash == pytest.approx(0.0)
    borrowed = ex.binned_values(f, rain, strikes)                     # without a shape the last bin is borrowed
    assert borrowed[3] == pytest.approx(vals[2])
    wet = ex.binned_values(ex.payoff("both_tails", 100 * rain / normal, 0.9), rain, strikes,
                           lambda r: float(ex.payoff("both_tails", np.array([100 * r / normal]), 0.9)[0]))
    assert wet[4] > wet[3] > 0                                         # the wet tail is filled from the shape
