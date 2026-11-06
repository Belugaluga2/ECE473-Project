"""Coverage, holdout, and executable-price checks for farmer comparisons."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import numpy as np
import pytest

from agri_hedge import comparison as cmp
from agri_hedge import hedge_builder as hb
from agri_hedge.kalshi import KalshiClient
from agri_hedge.platform import LiveQuotes


NOW = datetime(2026, 11, 6, 12, 0, tzinfo=timezone.utc)


def training_example():
    years = np.arange(1951, 2026)
    X = np.column_stack((years % 2 == 0, years % 3 == 0)).astype(float)
    y = X @ np.array([100.4, 25.6])
    return X, y, years


@pytest.fixture
def synthetic_farm(monkeypatch):
    request = hb.CoverageRequest(32.8, -97.8,
                                 [hb.Window((4, 5), 0.5), hb.Window((6, 7), 0.5)],
                                 protection=1000., station_key="DFW", grid_id=1)
    farm = {"farm_id": "TEST", "farm": {"county": "Test County", "insured_acres": 10},
            "request": request, "protection": 1000., "producer_premium": 100.,
            "total_premium": 200.}
    monkeypatch.setattr(hb, "load_farm_requests", lambda: [farm])

    def build(req):
        X, y, years = training_example()
        return hb.HedgeProblem(req, 1, (32.8, -97.8),
                               {"station_key": "DFW", "series_ticker": "KXRAINDALM"},
                               40., years, y * req.protection / 1000., {}, X,
                               [(4, 1.), (6, 2.)], np.array([0.4, 0.7]))

    monkeypatch.setattr(hb, "build_problem", build)
    return farm


def live_book(**updates):
    book = {"source": "live", "as_of": NOW.isoformat(),
            "close_time": "2027-05-01T00:00:00Z", "ticker": "KXRAINDALM-27APR-1",
            "yes_bids": [(0.9, 1), (0.8, 2)]}
    book.update(updates)
    return book


def test_he_one_does_not_mean_equal_coverage():
    metrics = cmp.coverage_metrics([10., 20., 30.], [5., 15., 25.])
    assert metrics["he"] == pytest.approx(1.)
    assert metrics["rmse_usd"] == pytest.approx(5.)
    assert metrics["mean_bias_usd"] == pytest.approx(-5.)
    assert metrics["worst_shortfall_usd"] == pytest.approx(5.)
    assert metrics["payout_recovery"] == pytest.approx(0.75)


@pytest.mark.parametrize("target,payout", [([], []), ([1], [1, 2]),
                                           ([float("nan")], [0]), ([1], [-1])])
def test_coverage_rejects_invalid_payout_vectors(target, payout):
    with pytest.raises(ValueError):
        cmp.coverage_metrics(target, payout)


def test_holdout_outcomes_cannot_change_fitted_contracts():
    X, y, years = training_example()
    before = cmp.fit_portfolios(X, y, years, 1000.)
    X[years >= 2001] = 1. - X[years >= 2001]
    y[years >= 2001] = 1_000_000.
    after = cmp.fit_portfolios(X, y, years, 1000.)
    for name in before:
        np.testing.assert_array_equal(before[name], after[name])
        assert np.issubdtype(before[name].dtype, np.integer)
        assert (before[name] >= 0).all()
    np.testing.assert_array_equal(before["best_fit"], [100, 26])


def test_acres_scale_exposure_and_saved_premium_with_integer_rounding(synthetic_farm):
    base = cmp.compare({"farm_id": "TEST"}, now=NOW)
    doubled = cmp.compare({"farm_id": "TEST", "acres": 20}, now=NOW)
    assert doubled["farm"]["protection_usd"] == 2 * base["farm"]["protection_usd"]
    assert doubled["prf"]["producer_premium_usd"] == 2 * base["prf"]["producer_premium_usd"]
    assert doubled["prf"]["total_premium_usd"] == 2 * base["prf"]["total_premium_usd"]
    for b, d in zip(base["strategies"], doubled["strategies"]):
        assert d["metrics"]["mean_prf_usd"] == pytest.approx(2 * b["metrics"]["mean_prf_usd"])
        assert len(b["ticket"]) == len(d["ticket"])
        for bt, dt in zip(b["ticket"], d["ticket"]):
            assert isinstance(dt["contracts"], int)
            assert abs(dt["contracts"] - 2 * bt["contracts"]) <= 1


def test_farmer_quote_is_a_total_premium_override(synthetic_farm):
    result = cmp.compare({"farm_id": "TEST", "acres": 20, "producer_premium_usd": 17.25}, now=NOW)
    assert result["prf"]["producer_premium_usd"] == 17.25
    assert result["prf"]["total_premium_usd"] == 400.
    assert result["prf"]["source"].startswith("farmer-supplied")
    for strategy in result["strategies"]:
        assert strategy["price_gap_usd"] == pytest.approx(17.25 - strategy["cost"]["cost_usd"])


@pytest.mark.parametrize("params", [
    None, [], {}, {"farm_id": "unknown"}, {"farm_id": ["TEST"]},
    {"farm_id": "TEST", "acres": float("nan")},
    {"farm_id": "TEST", "acres": float("inf")},
    {"farm_id": "TEST", "acres": -1},
    {"farm_id": "TEST", "acres": 0},
    {"farm_id": "TEST", "producer_premium_usd": float("nan")},
    {"farm_id": "TEST", "producer_premium_usd": -1},
    {"farm_id": "TEST", "contract_year": 2027.5},
    {"farm_id": "TEST", "contract_year": float("nan")},
    {"farm_id": "TEST", "contract_year": float("inf")},
    {"farm_id": "TEST", "contract_year": -1},
    {"farm_id": "TEST", "contract_year": 2030},
    {"farm_id": "TEST", "contract_year": 2026},
    {"farm_id": "TEST", "price_source": "snapshot"},
])
def test_compare_rejects_invalid_inputs_and_past_months(synthetic_farm, params):
    with pytest.raises(ValueError):
        cmp.compare(params, now=NOW)


def test_fresh_exact_year_books_use_level_costs_fees_and_funding():
    problem = SimpleNamespace(legs=[(4, 1.)], q=np.array([0.2]))
    costs, ticket, execution = cmp.price_portfolio(
        problem, [3], {("2027-04", 1.): live_book()}, 2027, NOW, True, rate=0.1)
    # One NO at $0.10 plus two at $0.20, with separately rounded fees of $0.01 and $0.03.
    days = 177  # Apr 30 minus Nov 6, plus the two-day settlement allowance.
    expected = 0.54 * (1. + 0.1 * days / 365.)
    assert ticket[0]["days_prepaid"] == days
    assert execution["fully_fillable"] is True
    assert execution["fill_fraction"] == 1.
    assert execution["full_cost_usd"] == pytest.approx(expected)
    assert ticket[0]["fill_cost_usd"] == pytest.approx(expected)
    assert costs["cost_usd"] > 0


@pytest.mark.parametrize("book,key", [
    (live_book(as_of=(NOW - timedelta(seconds=121)).isoformat()), ("2027-04", 1.)),
    (live_book(source="snapshot"), ("2027-04", 1.)),
    (live_book(close_time=NOW.isoformat()), ("2027-04", 1.)),
    (live_book(close_time=None), ("2027-04", 1.)),
    (live_book(as_of=(NOW + timedelta(seconds=1)).isoformat()), ("2027-04", 1.)),
    (live_book(as_of="invalid"), ("2027-04", 1.)),
    (live_book(), ("2026-04", 1.)),
    (live_book(), ("2027-05", 1.)),
    (live_book(), ("2027-04", 2.)),
])
def test_unavailable_books_never_count_as_executable(book, key):
    problem = SimpleNamespace(legs=[(4, 1.)], q=np.array([0.2]))
    costs, ticket, execution = cmp.price_portfolio(problem, [3], {key: book}, 2027, NOW, True)
    assert execution["checked"] is True
    assert execution["fully_fillable"] is False
    assert execution["all_legs_live"] is False
    assert execution["fillable_contracts"] == 0
    assert execution["full_cost_usd"] is None
    assert costs["cost_usd"] > 0  # A planning price remains available, not an executable quote.
    assert ticket[0]["source"] != "live"


def test_partial_depth_reports_cost_only_for_filled_quantity():
    problem = SimpleNamespace(legs=[(4, 1.)], q=np.array([0.2]))
    _, _, execution = cmp.price_portfolio(
        problem, [5], {("2027-04", 1.): live_book()}, 2027, NOW, True, rate=0.)
    assert execution["all_legs_live"] is True
    assert execution["fully_fillable"] is False
    assert execution["fillable_contracts"] == 3
    assert execution["fill_fraction"] == pytest.approx(0.6)
    assert execution["partial_cost_usd"] == pytest.approx(0.54)
    assert execution["full_cost_usd"] is None


def test_live_quotes_accepts_native_kalshi_client(monkeypatch):
    client = KalshiClient(delay=0, max_retries=0)
    calls = []

    def response(path, params=None):
        calls.append((path, params))
        if path == "/markets":
            return {"markets": [{"ticker": "KXRAINDALM-27APR-1", "event_ticker": "KXRAINDALM-27APR",
                                 "strike_type": "greater", "floor_strike": 1,
                                 "close_time": "2027-05-01T00:00:00Z"}]}
        assert path == "/markets/KXRAINDALM-27APR-1/orderbook"
        return {"orderbook_fp": {"yes_dollars": [["0.8000", "2.00"]], "no_dollars": []}}

    monkeypatch.setattr(client, "get", response)
    quotes = LiveQuotes(client=client)
    books = quotes.series_books("KXRAINDALM")
    assert len(calls) == 2
    assert books[("2027-04", 1.)]["source"] == "live"
    assert books[("2027-04", 1.)]["yes_bids"] == [(0.8, 2.)]
    assert calls[0][1]["status"] == "open"


def test_real_dfw_comparison_offline():
    result = cmp.compare({"farm_id": "DFW_hay", "price_source": "model", "contract_year": 2027}, now=NOW)
    assert result["farm"]["station"] == "DFW"
    assert result["farm"]["acres"] == 150
    assert result["prf"]["producer_premium_usd"] == pytest.approx(3683.33)
    assert result["training"]["n_years"] >= 20
    assert result["holdout"]["n_years"] >= 10
    assert result["verdict"]["arbitrage"] is False
    assert result["verdict"]["same_coverage"] is False
    for strategy in result["strategies"]:
        assert strategy["cost"]["cost_usd"] > 0
        assert np.isfinite(strategy["metrics"]["he"])
        assert strategy["metrics"]["worst_shortfall_usd"] > 0
        assert all(2001 <= row["year"] <= 2025 for row in strategy["backtest"])
        assert all(isinstance(row["contracts"], int) for row in strategy["ticket"])
        assert strategy["execution"]["checked"] is False
        assert strategy["execution"]["full_cost_usd"] is None


def test_subsidy_trade_selling_kalshi_lowers_mean_pnl():
    rec = hb.load_farm_requests()[0]
    rows = {r["trade"]: r for r in cmp.subsidy_trade(rec)}
    alone = rows["PRF only"]
    sold = rows["PRF + sell Kalshi hedge"]
    assert alone["sale_proceeds_usd"] == 0
    assert sold["sale_proceeds_usd"] < sold["fair_value_sold_usd"]  # spread, fees, collateral
    assert sold["mean_pnl_usd"] < alone["mean_pnl_usd"]
    assert alone["worst_pnl_usd"] == pytest.approx(-alone["prf_producer_usd"], abs=1)
