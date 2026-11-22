"""Frozen, offline, exploratory paper evidence; see docs/analysis/30_matched_premium_drought.md.

No model or case is selected on these already-inspected evaluation years. This
is a diagnostic comparison, not a newly untouched confirmation sample.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
from agri_hedge import hedge_builder as hb
from agri_hedge.config import ROOT, PROCESSED, FIGURES, DOCS
from agri_hedge.loss_model import build_farm_model
from agri_hedge.prf_intervals import INTERVAL_MONTHS
from agri_hedge.replicate import fit_ladder
from agri_hedge.paper_evidence import (drought_payoff, all_in_cost, budget_ticket,
                                     saved_depth_cap, summarize, effectiveness, paired_year_blocks)

CASES = ("DFW_hay", "SAT_graze", "ABQ_graze")
YEARS = np.arange(1951, 2026)
TRAIN_END = 2000
MIX = 0.80
SEED = 473
BOOTSTRAPS = 2000
DOC = DOCS/"analysis/30_matched_premium_drought.md"
BEGIN = "<!-- BEGIN AUTO: matched premium -->"
END = "<!-- END AUTO: matched premium -->"


def design(rain, months, strikes, proposed=False, intervals=None):
    columns, legs = [], []
    if proposed:
        for name in intervals:
            m1,m2 = INTERVAL_MONTHS[name]
            r = rain[m1].to_numpy()+rain[m2].to_numpy()
            top = np.nanmax(r[YEARS <= TRAIN_END])
            for k in np.arange(1, int(np.ceil(top*3))+1)/3:
                columns.append(np.where(np.isnan(r), np.nan, (r <= k).astype(float)))
                legs.append((name,float(k)))
    else:
        for month in months:
            r = rain[month].to_numpy()
            for k in strikes.get(month, tuple(range(1,8))):
                columns.append(np.where(np.isnan(r), np.nan, (r <= k).astype(float)))
                legs.append((month,float(k)))
    return np.column_stack(columns), legs


def fitted_ticket(X, y, train, budget, half_spread, ridge):
    ok = train & np.isfinite(y) & np.isfinite(X).all(axis=1)
    if ok.sum() < 35:
        raise ValueError("Insufficient complete fitting years")
    fit = fit_ladder(X[ok], y[ok], ridge=ridge)
    q = X[ok].mean(axis=0)
    asks = np.clip(q+half_spread,0.01,0.99)
    counts, scale = budget_ticket(fit.weights, asks, budget)
    return dict(X=X, counts=counts, asks=asks, fair=q, intended=y*scale,
                train_n=int(ok.sum()), cost=all_in_cost(counts,asks))


def run_case(F, half_spread):
    f, fid = F['farm'], F['farm_id']
    req = F['request']
    rain = hb.station_rain(F['site']).reindex(YEARS)
    grid_rain = hb.grid_monthly(req.grid_id).reindex(YEARS)
    official = pd.read_csv(PROCESSED/'prf_official_index.csv')
    official = official[official.grid_id == req.grid_id].pivot(index='year',columns='interval_name',values='index_value').reindex(YEARS)
    prf = F['prf_ncei_usd'].reindex(YEARS).to_numpy(float)
    loss_model = build_farm_model(f,timing='growth',curvature=True)
    loss = np.asarray(loss_model.loss_usd(official,gains=False),float)
    train = YEARS <= TRAIN_END
    allocations = f['interval_allocation']
    selected = sorted({m for name in allocations for m in INTERVAL_MONTHS[name]})
    opened = [m for m in (1,2,11,12) if m not in selected]
    if not opened:
        raise ValueError('No prespecified winter companion months')
    strikes = hb.listed_strikes(hb.station_table().set_index('station_key').loc[F['site'],'series_ticker'])
    linear = sum(share*drought_payoff(official[name].to_numpy(),coverage=f['coverage_level'])
                 for name,share in allocations.items())
    tails = {shape:sum(share*drought_payoff(official[name].to_numpy(),shape)
                       for name,share in allocations.items())
             for shape in ('exp5','deep50','digital30')}
    companion = sum(drought_payoff(100*grid_rain[m].to_numpy()/grid_rain.loc[train,m].mean()) for m in opened)/len(opened)
    X, legs = design(rain,selected,strikes)
    C, clegs = design(rain,opened,strikes)
    P, plegs = design(rain,selected,strikes,True,allocations)
    budget = float(F['producer_premium'])
    configs = {
        'market_linear': (X,legs,linear,budget,0.0,0.03,False),
        'prf80_companion20': (C,clegs,companion,(1-MIX)*budget,MIX,0.03,False),
    }
    # These two additional shape sensitivities are inherited from the prior deck.
    # They were added after inspecting the first exp5 run and are explicitly exploratory.
    for shape,tail in tails.items():
        configs[f'tail_{shape}_listed']=(X,legs,tail,budget,0.0,0.03,False)
        configs[f'tail_{shape}_proposed_sum_third']=(P,plegs,tail,budget,0.0,0.10,True)
        configs[f'prf80_tail_{shape}20']=(X,legs,tail,(1-MIX)*budget,MIX,0.03,False)
    assert f['productivity_factor']*MIX >= 0.60
    books = pd.read_csv(PROCESSED/'kalshi_rain_orderbook_summary.csv')
    books = books[(books.study_site == F['site']) & (books.contract_month == '2026-11')]
    bmap = {float(r.strike):r.yes_bids for r in books.itertuples()}
    common = (np.isfinite(loss) & np.isfinite(prf) & np.isfinite(P).all(axis=1)
              & np.isfinite(X).all(axis=1) & np.isfinite(C).all(axis=1)
              & np.isfinite(official[list(allocations)].to_numpy()).all(axis=1))
    severe = official[list(allocations)].min(axis=1).to_numpy() <= 30
    annual, tickets, curves = [], [], []
    methods = [('prf_only', 'unlimited', prf,prf,budget,None,1.0)]
    methods += [('prf_only','saved_depth_proxy',prf,prf,budget,None,1.0)]
    for name,(matrix,ls,target,b,prf_share,ridge,proposed) in configs.items():
        ticket = fitted_ticket(matrix,target,train,b,half_spread,ridge)
        desired = ticket['counts']
        n0 = desired.sum()
        for state in ('unlimited',) if proposed else ('unlimited','saved_depth_proxy'):
            counts = desired if state == 'unlimited' else saved_depth_cap(desired,ls,bmap,ticket['fair'])
            pay = matrix@counts + prf_share*prf
            intended = ticket['intended']+prf_share*prf
            cost = all_in_cost(counts,ticket['asks'])+prf_share*budget
            methods.append((name,state,pay,intended,cost,counts,float(counts.sum()/n0) if n0 else 0.0))
            for j,(label,k) in enumerate(ls):
                if desired[j]:
                    tickets.append(dict(farm_id=fid,policy=name,depth=state,period=str(label),strike=k,
                                        desired=int(desired[j]),filled_proxy=int(counts[j]),
                                        training_fair=float(ticket['fair'][j]),modeled_ask=float(ticket['asks'][j])))
        if name == 'tail_exp5_proposed_sum_third':
            tail=tails['exp5']
            for I in range(101):
                curves.append(dict(farm_id=fid,index=I,producer_premium=budget,
                                   protection=F['protection'],
                                   prf_payout_per_premium=F['protection']/budget*float(drought_payoff(I,coverage=f['coverage_level'])),
                                   tail_target_per_premium=float(drought_payoff(I,'exp5'))*float(ticket['intended'][0]/tail[0] if tail[0] > 0 else fitted_scale(ticket,tail))/budget))
    for name,state,pay,intended,cost,counts,fill in methods:
        assert cost <= budget+1e-6
        for j in np.flatnonzero(common):
            annual.append(dict(farm_id=fid,policy=name,depth=state,year=int(YEARS[j]),
                               evaluation='train' if train[j] else 'test',
                               loss_proxy=float(loss[j]),prf_reference=float(prf[j]),payout=float(pay[j]),
                               desired_target=float(intended[j]),premium=float(cost),budget=budget,
                               cash_retained=budget-cost,severe=bool(severe[j]),contract_fill_fraction=fill))
    return annual,tickets,curves


def fitted_scale(ticket,target):
    ok = target > 0
    return float(np.median(ticket['intended'][ok]/target[ok]))


def collect_metrics(annual):
    rows=[]
    for key,g in annual.groupby(['price_scenario','farm_id','policy','depth','evaluation'],sort=True):
        g=g.sort_values('year')
        m=summarize(g.loss_proxy,g.payout,g.premium.iloc[0],g.prf_reference,g.severe.to_numpy(bool))
        m.update(dict(zip(['price_scenario','farm_id','policy','depth','evaluation'],key)))
        m['budget']=g.budget.iloc[0]
        m['cash_retained']=g.cash_retained.iloc[0]
        m['contract_fill_fraction']=g.contract_fill_fraction.iloc[0]
        m['target_rmse']=float(np.sqrt(np.mean((g.desired_target-g.payout)**2)))
        m['target_he']=effectiveness(g.desired_target,g.payout)
        if key[-1] == 'test':
            base=annual[(annual.price_scenario==key[0])&(annual.farm_id==key[1])&
                        (annual.policy=='prf_only')&(annual.depth==key[3])&(annual.evaluation=='test')].set_index('year').loc[g.year]
            y,h=g.loss_proxy.to_numpy(),g.payout.to_numpy()
            base_h=base.payout.to_numpy()
            wins=h>base_h+0.01
            m['payout_win_years_vs_prf']=int(wins.sum())
            m['severe_payout_win_years_vs_prf']=int((wins & g.severe.to_numpy(bool)).sum())
            desired_wins=g.desired_target.to_numpy()>base_h+0.01
            m['desired_target_win_years_vs_prf']=int(desired_wins.sum())
            m['desired_target_severe_win_years_vs_prf']=int((desired_wins & g.severe.to_numpy(bool)).sum())
            net=np.maximum(y+g.premium.iloc[0]-h,0)
            base_net=np.maximum(y+base.premium.iloc[0]-base_h,0)
            worst=np.argsort(y)[-5:]
            m['worst5_improvement_vs_prf']=float((base_net[worst]-net[worst]).mean())
            blocks=paired_year_blocks(len(g),BOOTSTRAPS,seed=SEED)
            he_draws=[];tail_draws=[]
            for b in blocks:
                he_draws.append(effectiveness(y[b],h[b]))
                top=b[np.argsort(y[b])[-5:]]
                tail_draws.append(float((base_net[top]-net[top]).mean()))
            m['he_ci_low'],m['he_ci_high']=np.nanquantile(he_draws,[0.025,0.975])
            m['worst5_improvement_ci_low'],m['worst5_improvement_ci_high']=np.quantile(tail_draws,[0.025,0.975])
            leave=np.arange(len(g)) != int(np.argmax(y))
            keep=np.flatnonzero(leave)
            top=keep[np.argsort(y[keep])[-5:]]
            m['worst5_improvement_drop_worst_year']=float((base_net[top]-net[top]).mean())
            m['dropped_worst_year']=int(g.year.iloc[np.argmax(y)])
        rows.append(m)
    return pd.DataFrame(rows)


def main():
    farms={f['farm_id']:f for f in hb.load_farm_requests()}
    all_years=[];all_tickets=[];all_curves=[]
    for price,spread in [('central',0.0225),('wide_spread',0.0655)]:
        for fid in CASES:
            years,tickets,curves=run_case(farms[fid],spread)
            for collection in (years,tickets,curves):
                for row in collection: row['price_scenario']=price
            all_years+=years;all_tickets+=tickets;all_curves+=curves
    annual=pd.DataFrame(all_years)
    summary=collect_metrics(annual)
    annual.to_csv(PROCESSED/'maya_matched_premium_years.csv',index=False)
    pd.DataFrame(all_tickets).to_csv(PROCESSED/'maya_matched_premium_tickets.csv',index=False)
    curves=pd.DataFrame(all_curves)
    curves.to_csv(PROCESSED/'maya_actual_prf_curves.csv',index=False)
    summary.to_csv(PROCESSED/'maya_matched_premium_summary.csv',index=False)
    metadata=dict(cases=CASES,fit=[1951,TRAIN_END],evaluate=[2001,2025],mix_prf_share=MIX,
                  tail_shapes='exp5, deep50, digital30 inherited from prior study; not retuned',
                  family_audit='deep50/digital30 added after first exp5 results; all retained as exploratory sensitivities',
                  bootstrap=dict(draws=BOOTSTRAPS,block_years=2,seed=SEED),
                  status='exploratory; evaluation years already inspected in prior work',
                  loss='modeled forage-loss proxy, NRCS growth weights; not observed farm income',
                  proposed='two-month third-inch instruments are not listed',
                  depth='November 2026 ladder repeated across calendar months: capacity stress, not historical fills',
                  input_files=['prf_scenario_results.csv','prf_official_index.csv','station_monthly_precip.csv',
                               'ncei_monthly_precip_grids.parquet','kalshi_rain_orderbook_summary.csv'],
                  actual_prf='2026 actuarial terms applied counterfactually to NCEI historical index, not actual historical payments')
    (PROCESSED/'maya_matched_premium_method.json').write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf-8')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,3,figsize=(12,3.6),sharey=True)
    for ax,fid in zip(axes,CASES):
        c=curves[(curves.farm_id==fid)&(curves.price_scenario=='central')]
        ax.plot(c['index'],c.prf_payout_per_premium,label='Actual PRF terms',color='#1f5fa8')
        ax.plot(c['index'],c.tail_target_per_premium,label='Proposed tail target',color='#d9822b')
        ax.set(title=fid,xlabel='Rainfall index (% of normal)',xlim=(100,0))
        ax.grid(alpha=.2)
    axes[0].set_ylabel('Target payout per $1 producer budget')
    axes[0].legend(fontsize=8)
    fig.suptitle('Common-index illustration; target payouts, not guaranteed portfolio payments',fontsize=10)
    fig.tight_layout()
    fig.savefig(FIGURES/'maya_actual_prf_curves.png',dpi=180)
    fig.savefig(FIGURES/'maya_actual_prf_curves.pdf')
    plt.close(fig)
    view=summary[(summary.evaluation=='test')&(summary.price_scenario=='central')]
    cols=['farm_id','policy','depth','loss_proxy_he','mean_payout','worst5_net_shortfall','worst5_improvement_vs_prf','contract_fill_fraction']
    print(view[cols].round(3).to_string(index=False))
    lines=['| Farm | Policy | Capacity | Loss-proxy HE | Mean payout ($) | Worst-five shortfall ($) | Improvement vs PRF ($) |',
           '|---|---|---|---:|---:|---:|---:|']
    for r in view.itertuples():
        lines.append(f'| {r.farm_id} | {r.policy} | {r.depth} | {r.loss_proxy_he:.3f} | {r.mean_payout:.0f} | {r.worst5_net_shortfall:.0f} | {r.worst5_improvement_vs_prf:.0f} |')
    if DOC.exists():
        text=DOC.read_text(encoding='utf-8')
        a,b=text.index(BEGIN)+len(BEGIN),text.index(END)
        DOC.write_text(text[:a]+'\n\n'+'\n'.join(lines)+'\n\n'+text[b:],encoding='utf-8')


if __name__=='__main__':
    main()
