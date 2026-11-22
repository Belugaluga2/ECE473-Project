"""Budget, fee, capacity and fitting-boundary checks for the paper diagnostic."""
import importlib.util
from pathlib import Path
import numpy as np
from agri_hedge.paper_evidence import (all_in_cost,budget_ticket,saved_depth_cap,
                                     drought_payoff,effectiveness,paired_year_blocks)


def test_actual_prf_curve_endpoints_and_constant_offset_limit_of_he():
    assert np.allclose(drought_payoff([0,90,100]),[1,0,0])
    assert np.allclose(drought_payoff([0,100],'exp5'),[1,0])
    assert effectiveness([0,100,200],[10,110,210]) == 1


def test_budget_counts_include_one_fee_and_financing_and_preserve_cash():
    # Ten 50c contracts cost $5 plus 18c after rounding the 17.5c fee.
    assert np.isclose(all_in_cost([10],[.5],annual_rate=0),5.18)
    n,scale=budget_ticket([2,1],[.2,.6],10)
    assert (n>=0).all() and np.equal(n,np.floor(n)).all() and scale>0
    assert all_in_cost(n,[.2,.6]) <= 10
    assert budget_ticket([0,0],[.2,.6],10)[0].sum()==0


def test_depth_proxy_caps_quantity_and_rejects_expensive_or_absent_strikes():
    books={1.0:'[[0.8, 3.8], [0.1, 100]]'}
    n=saved_depth_cap([10,10],[(11,1.0),(12,2.0)],books,[.2,.2])
    assert n.tolist()==[3,0]


def test_fitted_ticket_does_not_use_evaluation_payoffs_or_targets():
    script=Path(__file__).resolve().parents[1]/'scripts/run_matched_premium.py'
    spec=importlib.util.spec_from_file_location('matched_premium',script)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    rng=np.random.default_rng(473)
    X=(rng.random((60,3))<.3).astype(float)
    y=X@np.array([.1,.4,.2]);train=np.arange(60)<45
    a=mod.fitted_ticket(X,y,train,100,.0225,.03)
    XX=X.copy();yy=y.copy();XX[~train]=1-XX[~train];yy[~train]+=100
    b=mod.fitted_ticket(XX,yy,train,100,.0225,.03)
    assert np.array_equal(a['counts'],b['counts'])
    assert np.array_equal(a['asks'],b['asks'])


def test_bootstrap_keeps_year_pairs_and_has_reproducible_blocks():
    a=paired_year_blocks(25,10,seed=473)
    assert a.shape==(10,25) and np.array_equal(a,paired_year_blocks(25,10,seed=473))
    assert np.all((a[:,1::2]-a[:,0:24:2])%25==1)
