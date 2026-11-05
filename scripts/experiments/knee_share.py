"""Doc 21 experiment: which frontier share (knee) does best out of sample. Run: python scripts/experiments/knee_share.py"""
import numpy as np, pandas as pd
from agri_hedge import hedge_builder as hb, optimizer as op
from agri_hedge.hedge_builder import CoverageRequest, Window
rows=[]
def run(name,X,y,q,prot):
    ok=~np.isnan(y)&~np.isnan(X).any(1); X,y=X[ok],y[ok]
    tr=op.model_tranches(q); fr=op.efficient_frontier(X,y,tr,21,prot,q=q)
    r={'case':name}
    for s in (0.6,0.75,0.85,0.9,0.95,1.0):
        b=op.knee_budget(fr,s) if s<1 else None
        r[s]=op.hedge_effectiveness(y,op.loyo_payout(X,y,tr,b,prot))
    rows.append(r)
for F in hb.load_farm_requests():
    r=F['request']; p=hb.build_problem(r); run(F['farm_id'],p.X,p.target,p.q,F['protection'])
    cov={m for w in r.windows for m in w.months}
    for m in sorted(set(range(1,13))-cov)[:3]:
        pm=hb.build_problem(CoverageRequest(r.lat,r.lon,[Window((m,),1.0)],0.9,F['protection']/6,station_key=r.station_key,grid_id=r.grid_id))
        run(F['farm_id']+'_'+str(m),pm.X,pm.target,pm.q,F['protection']/6)
d=pd.DataFrame(rows).set_index('case'); print(d.round(2).to_string()); print(d.median().round(3)); print(d.mean().round(3))
