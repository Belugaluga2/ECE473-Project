"""Offline index-design feasibility pilot for Chipata, Zambia; not loss validation.

No Kalshi weather market, local insurance offer, or farmer-income benefit is
asserted. Prices are hypothetical 1.20 times training-average target payouts.
"""
from __future__ import annotations
import calendar
import json
import numpy as np
import pandas as pd
from scipy.stats import beta
from agri_hedge.config import PROCESSED,RAW,DOCS
from agri_hedge.paper_evidence import drought_payoff

WINDOWS={'Nov-Mar':(11,12,1,2,3),'Jan-Feb':(1,2)}
TRAIN_END=2005
DOC=DOCS/'analysis/31_chipata_index_feasibility.md'
BEGIN='<!-- BEGIN AUTO: chipata -->';END='<!-- END AUTO: chipata -->'


def seasonal_totals(monthly,months):
    out={}
    for harvest_year in range(1982,2026):
        keys=[(harvest_year-1 if m>=11 else harvest_year,m) for m in months]
        vals=[monthly.get(k,np.nan) for k in keys]
        out[harvest_year]=sum(vals) if np.isfinite(vals).all() else np.nan
    return pd.Series(out,dtype=float)


def binomial_interval(k,n):
    return (0.0 if k==0 else beta.ppf(.025,k,n-k+1),
            1.0 if k==n else beta.ppf(.975,k+1,n-k))


def main():
    daily=pd.read_csv(PROCESSED/'maya_chipata_chirps_daily.csv',parse_dates=['date'])
    daily['year']=daily.date.dt.year;daily['month']=daily.date.dt.month
    chirps=daily.groupby(['year','month']).rain_mm.sum().to_dict()
    sources={'CHIRPS_area':chirps}
    nasa_path=RAW/'africa/nasa_power_chipata_monthly.json'
    if nasa_path.exists():
        raw=json.loads(nasa_path.read_text())
        rates=raw['properties']['parameter']['PRECTOTCORR']
        nasa={}
        for key,value in rates.items():
            y,m=int(key[:4]),int(key[4:])
            if 1<=m<=12 and float(value)>=0:nasa[(y,m)]=float(value)*calendar.monthrange(y,m)[1]
        sources['NASA_POWER_MERRA2_grid']=nasa
        pd.DataFrame([{'year':y,'month':m,'rain_mm':v} for (y,m),v in sorted(nasa.items())]).to_csv(
            PROCESSED/'maya_chipata_nasa_monthly.csv',index=False)
    elif (PROCESSED/'maya_chipata_nasa_monthly.csv').exists():
        nasa=pd.read_csv(PROCESSED/'maya_chipata_nasa_monthly.csv')
        sources['NASA_POWER_MERRA2_grid']={(int(r.year),int(r.month)):r.rain_mm for r in nasa.itertuples()}
    annual=[];summary=[]
    for source,monthly in sources.items():
        for label,months in WINDOWS.items():
            rain=seasonal_totals(monthly,months)
            if rain.isna().any():raise ValueError('Incomplete season')
            train=rain.index<=TRAIN_END
            normal=rain[train].mean()
            index=100*rain/normal
            for shape in ('linear','exp5','deep50','digital30'):
                target=drought_payoff(index.to_numpy(),shape)
                mean=float(target[train].mean())
                price=1.2*mean if mean>0 else np.nan
                n=int(train.sum());k=int(np.sum(target[train]>0))
                lo,hi=binomial_interval(k,n)
                rng=np.random.default_rng(473)
                draws=target[train][rng.integers(n,size=(2000,n))].mean(axis=1)*1.2
                summary.append(dict(source=source,window=label,shape=shape,
                                    fitting_seasons=n,evaluation_seasons=int((~train).sum()),
                                    normal_rain_mm=normal,index_2024=float(index.loc[2024]),
                                    training_pay_years=k,pay_frequency_ci_low=lo,pay_frequency_ci_high=hi,
                                    hypothetical_premium_per_unit_limit=price,
                                    price_bootstrap_low=float(np.quantile(draws,.025)),
                                    price_bootstrap_high=float(np.quantile(draws,.975)),
                                    target_payout_2024_per_premium=float(target[rain.index==2024][0]/price) if mean else np.nan,
                                    target_pays_in_evaluation=int(np.sum(target[~train]>0))))
                for y,r,I,t in zip(rain.index,rain,index,target):
                    annual.append(dict(source=source,window=label,shape=shape,harvest_year=y,rain_mm=r,index=I,
                                       evaluation='train' if y<=TRAIN_END else 'test',
                                       desired_payout_per_unit_limit=t,
                                       hypothetical_payout_per_premium=t/price if mean else np.nan))
    pd.DataFrame(annual).to_csv(PROCESSED/'maya_chipata_payout_replay.csv',index=False)
    summary=pd.DataFrame(summary)
    summary.to_csv(PROCESSED/'maya_chipata_pilot_summary.csv',index=False)
    view=summary[(summary.source=='CHIRPS_area')]
    print(view[['window','shape','normal_rain_mm','index_2024','training_pay_years',
                'hypothetical_premium_per_unit_limit','target_payout_2024_per_premium']].round(4).to_string(index=False))
    if DOC.exists():
        lines=['| Window | Shape | Training payout years / 24 | 2024 rain index | Hypothetical premium per unit limit | 2024 target payout per premium |',
               '|---|---|---:|---:|---:|---:|']
        for r in view.itertuples():
            price=f'{r.hypothetical_premium_per_unit_limit:.4f}' if np.isfinite(r.hypothetical_premium_per_unit_limit) else 'unpriced (no training payouts)'
            payout=f'{r.target_payout_2024_per_premium:.2f}' if np.isfinite(r.target_payout_2024_per_premium) else 'not established'
            lines.append(f'| {r.window} | {r.shape} | {r.training_pay_years} / 24 | {r.index_2024:.1f} | {price} | {payout} |')
        text=DOC.read_text(encoding='utf-8');a=text.index(BEGIN)+len(BEGIN);b=text.index(END)
        DOC.write_text(text[:a]+'\n\n'+'\n'.join(lines)+'\n\n'+text[b:],encoding='utf-8')


if __name__=='__main__':main()
