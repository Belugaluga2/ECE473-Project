import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
import numpy as np, pandas as pd
import run_expansion_netting as rx
st=rx.station_list(); parts=[rx.fetch_daily(s,True) for _,s in st.iterrows()]
d=pd.concat([p for p in parts if p is not None]); d=d[d.station_key!="SLC"]
d["year"],d["month"]=d.date.dt.year,d.date.dt.month
wk=d.date.dt.dayofweek.isin([4,5,6])
d["w01"]=(d.pcpn>0)&wk; d["w10"]=(d.pcpn>=0.10)&wk; d["w25"]=(d.pcpn>=0.25)&wk
g=d.groupby(["station_key","year","month"]).agg(w01=("w01","sum"),w10=("w10","sum"),w25=("w25","sum"),miss=("pcpn",lambda s:s.isna().sum())).reset_index()
g=g[g.miss==0]
r=[]
for (s,m),h in g.groupby(["station_key","month"]):
    if len(h)<60: continue
    for tgt in ("w10","w25"):
        y=h[tgt].to_numpy(float); k,e=rx.call_terms(y,True); pay=rx.call_frac(y,k,e)
        if pay.var()==0: continue
        fit=pd.Series(pay).groupby(h.w01.to_numpy()).transform("mean").to_numpy()
        r.append({"tgt":tgt,"corr":np.corrcoef(h.w01,h[tgt])[0,1],"r2":1-((pay-fit)**2).mean()/pay.var()})
r=pd.DataFrame(r); print(r.groupby("tgt").median().round(3))
