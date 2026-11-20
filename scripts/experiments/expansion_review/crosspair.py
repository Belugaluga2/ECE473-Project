import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
import numpy as np, pandas as pd
import run_expansion_netting as rx
from agri_hedge.locations import haversine_miles
rain=rx.load_monthly_rain(); u=rx.unit_payouts(rain); st=rx.station_list().set_index("station_key")
keys=sorted(u.station_key.unique()); L=1.2
def cap(loss,prem): return max(0,np.quantile(loss,.95))/prem
rows=[]
for i,a in enumerate(keys):
    for b in keys:
        if a==b: continue
        d=haversine_miles(st.loc[a,"lat"],st.loc[a,"lon"],st.loc[b,"lat"],st.loc[b,"lon"])
        if d>300: continue
        for mo in range(1,13):
            pa=u[(u.station_key==a)&(u.month==mo)].set_index("year").put
            cb=u[(u.station_key==b)&(u.month==mo)].set_index("year").call
            ca=u[(u.station_key==a)&(u.month==mo)].set_index("year").call
            j=pd.concat([pa,cb,ca],axis=1,keys=["p","c","cs"]).dropna()
            if len(j)<50: continue
            rows.append({"a":a,"b":b,"d":d,"mo":mo,
              "cross_pair":cap(j.p+j.c-2*L,2*L),"same_pair":cap(j.p+j.cs-2*L,2*L),"put_only":cap(j.p-L,L),
              "p_both":((j.p>0)&(j.c>0)).mean()})
r=pd.DataFrame(rows); r["bin"]=pd.cut(r.d,[0,50,100,200,300])
print(r.groupby("bin",observed=True)[["cross_pair","same_pair","put_only","p_both"]].median().round(3))
print(r.groupby("bin",observed=True).size())
print(r.groupby("bin",observed=True)[["a","b"]].apply(lambda x: sorted(set(map(tuple,np.sort(x.values,axis=1))))[:8]))
