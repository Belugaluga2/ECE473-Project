"""Helpers of scripts/run_intermediary_capital.py (doc 26: intermediary capital, costs and break-even loads)."""
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_scripts = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(_scripts))
_spec = importlib.util.spec_from_file_location("run_intermediary_capital", _scripts / "run_intermediary_capital.py")
ic = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ic)


def _risk(monthly, coll, el, q995=3.0):
    return {"sim_q995": q995, "_monthly": np.asarray(monthly, float), "_month_direcnet": np.asarray(coll, float),
            "_month_separate": np.asarray(coll, float), "_month_el": np.asarray(el, float),
            "active_months": len(el)}


def test_season_year_rolls_jan_feb_back():
    assert ic.season_year([2008, 2008, 2009, 2009], [11, 12, 1, 2], 11).tolist() == [2008, 2008, 2008, 2008]
    assert ic.season_year([2008, 2008], [1, 12], 1).tolist() == [2008, 2008]


def test_closed_form_break_even_zeroes_profit():
    e, carry, hold, q = 0.33, 0.063, 5 / 12, 4.0
    lam = ic.break_even_load(e, carry, hold, q)
    prem = 1 + lam
    assert abs(lam - e * prem - carry * hold * (q - prem)) < 1e-12
    # when premium already exceeds the reserve quantile, only expenses need covering
    assert abs(ic.break_even_load(0.33, 0.063, 1.0, 1.1) - 0.33 / 0.67) < 1e-12


def test_insurer_capital_is_quantile_net_of_premium():
    r = _risk(np.zeros((10, 2)), [2, 2], [0.5, 0.5], q995=3.0)
    assert abs(ic.season_capital(r, "insurer", 0.2) - 1.8) < 1e-12
    assert ic.season_capital(r, "insurer", 2.5) == 0.0


def test_maker_capital_adds_prior_tail_loss_to_current_collateral():
    # two months, each 0.5 of expected payout, full collateral 2.0 each; month 1 always pays 2.0
    monthly = np.column_stack([np.full(1000, 2.0), np.zeros(1000)])
    r = _risk(monthly, [2.0, 2.0], [0.5, 0.5])
    load = 0.0
    # month 1: 2.0 - 0.5 = 1.5; month 2: prior loss 1.5 plus 1.5 = 3.0
    assert abs(ic.season_capital(r, "maker_direcnet", load) - 3.0) < 1e-9


def test_solve_break_even_matches_closed_form_for_insurer():
    r = _risk(np.zeros((10, 4)), [1, 1, 1, 1], [0.25] * 4, q995=4.0)
    lam = ic.solve_break_even("insurer", r)
    hold = min(12, 5) / 12
    expect = ic.break_even_load(ic.INSURER_EXPENSE, ic.INSURER_COC - ic.TBILL, hold, 4.0)
    assert abs(lam - expect) < 1e-8


def test_books_have_unit_pure_premium_and_balanced_book_is_half_calls():
    units = pd.DataFrame([(s, m) for s in ic.SC + ["ORD"] for m in range(1, 13)], columns=["station_key", "month"])
    books = ic.book_specs(units)
    for b in books.values():
        assert abs(b["w_put"].sum() + b["w_call"].sum() - 1) < 1e-12
    assert abs(books["two_way_bal"]["w_call"].sum() - 0.5) < 1e-12
    assert set(books["ranch_sc"]["month"]) == {11, 12, 1, 2}
    assert books["ranch_sc"].attrs["start"] == 11 and books["national_bal"].attrs["start"] == 1
