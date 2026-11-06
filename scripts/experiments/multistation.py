"""Doc 21 experiment: hedges using contracts from 1-3 nearby stations. Run: python scripts/experiments/multistation.py"""
import numpy as np, pandas as pd
from agri_hedge import hedge_builder as hb, optimizer as op
from agri_hedge.pricing import no_pays, leg_probability
rows=[]
for F in hb.load_farm_requests():
    r=F['request']; prot=F['protection']
    p=hb.build_problem(r)
    near=hb.nearest_stations(r.lat, r.lon, 6)
    near=near[(near.distance_mi<=150)]
    # keep stations with >=50 complete years in the months
    months=sorted({m for w in r.windows for m in w.months})
    good=[]
    for _,s in near.iterrows():
        rain=hb.station_rain(s.station_key).reindex(p.years)
        if rain[months].notna().all(axis=1).sum()>=50: good.append((s.station_key, s.series_ticker, s.distance_mi))
    res={'farm':F['farm_id'],'stations':[g[0] for g in good][:3]}
    for k in (1,2,3):
        use=good[:k]
        cols=[];q=[]
        for key,ser,_ in use:
            rain=hb.station_rain(key); rr=rain.reindex(p.years)
            for m in months:
                for K in hb.strike_set(ser,m,'kalshi'):
                    cols.append(no_pays(rr[m].to_numpy(),K)); q.append(leg_probability(rain,m,K,hb.FAIR_WINDOW))
        X=np.column_stack(cols); q=np.array(q)
        ok=~np.isnan(p.target)&~np.isnan(X).any(1)
        tr=op.model_tranches(q)
        for nm,b in (('free',None),('knee','knee')):
            if b=='knee':
                fr=op.efficient_frontier(X[ok],p.target[ok],tr,13,prot,q=q); b=op.knee_budget(fr,0.9)
            l=op.loyo_payout(X[ok],p.target[ok],tr,b,prot)
            res[f'k{k}_{nm}']=round(op.hedge_effectiveness(p.target[ok],l),3)
        res[f'k{k}_n']=int(ok.sum())
    rows.append(res); print(res, flush=True)
d=pd.DataFrame(rows); print(d.median(numeric_only=True))
