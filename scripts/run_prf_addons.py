"""Reuse frozen doc-30 tickets; audit loss scale and compare PRF-kept add-ons.

    python scripts/run_prf_addons.py

No refitting, tuning, network, or orders. These evaluation years were already
inspected. See doc 32 for the prospective specification of this follow-up.
"""
from __future__ import annotations
import json
import numpy as np
import pandas as pd
from agri_hedge.config import PROCESSED,DOCS
from agri_hedge import hedge_builder as hb
from agri_hedge.loss_model import build_farm_model
from agri_hedge.prf_intervals import INTERVAL_NAMES
from agri_hedge.paper_followup import keep_prf,addon_statistics,required_depth_multiplier

CASES=('DFW_hay','SAT_graze','ABQ_graze')
PRIMARY='growth_replacement'
VARIANTS=[(t,b) for t in ('growth','allocation') for b in ('rent','replacement','protection')]
POLICIES={'prf80_companion20':'winter_companion','prf80_tail_exp520':'tail_exp5',
          'prf80_tail_deep5020':'tail_deep50','prf80_tail_digital3020':'tail_digital30'}
BEGIN='<!-- BEGIN AUTO: prf addons -->';END='<!-- END AUTO: prf addons -->'


def write_table(path,begin,end,table):
    text=path.read_text(encoding='utf-8');a=text.index(begin)+len(begin);b=text.index(end)
    path.write_text(text[:a]+'\n\n'+table+'\n\n'+text[b:],encoding='utf-8')


def main():
    old=pd.read_csv(PROCESSED/'maya_matched_premium_years.csv')
    farms={f['farm_id']:f for f in hb.load_farm_requests()}
    primitive=pd.read_csv(PROCESSED/'prf_official_index.csv')
    losses=[];audit=[]
    for fid in CASES:
        f=farms[fid];frame=primitive[primitive.grid_id==f['request'].grid_id].pivot(
            index='year',columns='interval_name',values='index_value')
        for timing,basis in VARIANTS:
            variant=f'{timing}_{basis}'
            model=build_farm_model(f['farm'],timing=timing,value_basis=basis,curvature=True)
            proxy=model.loss_usd(frame,gains=False)
            training=(proxy.index<=2000)&(proxy.index>=1951)
            test=(proxy.index>=2001)&(proxy.index<=2025)
            audit.append(dict(farm_id=fid,variant=variant,normal_value_per_acre=model.value_per_acre,
                              normal_value=model.normal_value_usd,policy_protection=f['protection'],
                              protection_to_normal_value=f['protection']/model.normal_value_usd,
                              producer_premium=f['producer_premium'],elasticity=model.elasticity,
                              curvature=model.curvature,elasticity_source=model.elasticity_source,
                              curvature_source=model.curvature_source,
                              loss_if_all_indices_zero=model.loss_usd({name:0.0 for name in INTERVAL_NAMES},gains=False),
                              mean_training_loss=float(proxy[training].mean()),mean_test_loss=float(proxy[test].mean())))
            for year,value in proxy.items():
                losses.append(dict(farm_id=fid,year=int(year),loss_variant=variant,loss_proxy=float(value)))
    losses=pd.DataFrame(losses)
    pd.DataFrame(audit).to_csv(PROCESSED/'maya_loss_scale_audit.csv',index=False)
    losses.to_csv(PROCESSED/'maya_addon_loss_variants.csv',index=False)

    addon=[]
    for key,g in old.groupby(['price_scenario','farm_id','depth','policy'],sort=True):
        price,fid,depth,policy=key
        if policy not in POLICIES and policy!='prf_only':continue
        f=farms[fid];C=f['producer_premium'];A=.2*C
        g=g.sort_values('year')
        if policy=='prf_only':
            component=np.zeros(len(g));spent=0.0;name='cash'
            pay=g.prf_reference.to_numpy();premium=C;cash=A
        else:
            restored=keep_prf(g.prf_reference,g.payout,float(g.premium.iloc[0]),C)
            component=restored['component'];spent=restored['component_cost'];name=POLICIES[policy]
            pay=restored['total_payout'];premium=restored['total_premium'];cash=restored['cash_retained']
        for j,r in enumerate(g.itertuples()):
            addon.append(dict(price_scenario=price,farm_id=fid,depth=depth,policy=name,year=r.year,
                              evaluation=r.evaluation,original_prf_payout=r.prf_reference,
                              market_payout=float(component[j]),total_payout=float(pay[j]),
                              original_prf_premium=C,additional_budget=A,market_cost=spent,
                              total_premium=premium,total_budget=C+A,cash_retained=cash))
    addon=pd.DataFrame(addon)
    assert ((addon.total_premium+addon.cash_retained-addon.total_budget).abs()<1e-6).all()
    addon.to_csv(PROCESSED/'maya_prf_addon_years.csv',index=False)
    merged=addon.merge(losses,on=['farm_id','year'],validate='many_to_many')
    rows=[]
    for key,g in merged.groupby(['price_scenario','farm_id','depth','policy','evaluation','loss_variant'],sort=True):
        price,fid,depth,policy,evaluation,variant=key;g=g.sort_values('year')
        if evaluation!='test':continue
        stats=addon_statistics(g.loss_proxy,g.original_prf_payout,g.market_payout,
                               g.original_prf_premium.iloc[0],g.market_cost.iloc[0])
        stats.update(dict(price_scenario=price,farm_id=fid,depth=depth,policy=policy,
                          evaluation=evaluation,loss_variant=variant,additional_budget=g.additional_budget.iloc[0],
                          cash_retained=g.cash_retained.iloc[0]))
        rows.append(stats)
    summary=pd.DataFrame(rows)
    summary.to_csv(PROCESSED/'maya_prf_addon_summary.csv',index=False)
    meta=dict(original_policies_kept=True,additional_budget_fraction=.20,
              source='doc 30 frozen reallocation tickets decomposed; no refit',
              primary_loss_variant=PRIMARY,all_loss_variants=[f'{t}_{b}' for t,b in VARIANTS],
              pricing='central and wide-spread inherited modeled prices; not live quotes',
              loss_validation='proxy sensitivities only, no observed farm-income validation',
              status='exploratory; evaluation years already inspected; no new held-out confirmation',
              cash='Unspent extra cash; foregone 31-day interest already included in market economic cost')
    (PROCESSED/'maya_prf_addon_method.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf-8')
    view=summary[(summary.price_scenario=='central')&(summary.depth=='unlimited')&(summary.loss_variant==PRIMARY)]
    cols=['farm_id','policy','mean_net_gain_vs_cash','residual_variance_reduction','worst5_shortfall_reduction']
    print(view[cols].round(3).to_string(index=False))
    lines=['| Farm | Extra-budget use | Mean net gain vs cash ($/yr) | Residual variance reduction | Worst-five shortfall reduction ($) |',
           '|---|---|---:|---:|---:|']
    for r in view.itertuples():
        lines.append(f'| {r.farm_id} | {r.policy} | {r.mean_net_gain_vs_cash:.0f} | {r.residual_variance_reduction:.3f} | {r.worst5_shortfall_reduction:.0f} |')
    write_table(DOCS/'analysis/32_prf_addons_and_loss_audit.md',BEGIN,END,'\n'.join(lines))
    liquidity()


def liquidity():
    tickets=pd.read_csv(PROCESSED/'maya_matched_premium_tickets.csv')
    books=pd.read_csv(PROCESSED/'kalshi_rain_orderbook_summary.csv')
    tickets=tickets[(tickets.price_scenario=='central')&(tickets.depth=='unlimited')&tickets.policy.isin(POLICIES)]
    rows=[]
    for r in tickets.itertuples():
        matches=books[(books.study_site==r.farm_id.split('_')[0])&(books.contract_month=='2026-11')&
                      np.isclose(books.strike,r.strike)]
        levels=[] if matches.empty else json.loads(matches.iloc[0].yes_bids)
        cap=sum(float(size) for bid,size in levels if 1-float(bid)<=r.training_fair+.10+1e-10)
        rows.append(dict(farm_id=r.farm_id,policy=POLICIES[r.policy],month=int(r.period),strike=r.strike,
                         desired=r.desired,saved_eligible_capacity=cap,
                         multiplier=r.desired/cap if cap>0 else np.inf,
                         zero_capacity=cap<=0,listed_in_saved_november=not matches.empty,
                         modeled_ask=r.modeled_ask,training_fair=r.training_fair,
                         saved_snapshot='2026-11-02',capacity_scope='November proxy repeated across months'))
    legs=pd.DataFrame(rows);legs.to_csv(PROCESSED/'maya_liquidity_requirements_legs.csv',index=False)
    summaries=[]
    for key,g in legs.groupby(['farm_id','policy']):
        k,missing=required_depth_multiplier(g.desired,g.saved_eligible_capacity)
        finite=g.multiplier[np.isfinite(g.multiplier)]
        summaries.append(dict(farm_id=key[0],policy=key[1],required_contracts=int(g.desired.sum()),
                              required_reference_cost=float((g.desired*g.modeled_ask).sum()),
                              gross_unnetted_other_side_stake=float((g.desired*(1-g.modeled_ask)).sum()),
                              missing_contracts_at_proxy=int((g.desired-np.minimum(g.desired,np.floor(g.saved_eligible_capacity))).sum()),
                              missing_useful_offer_legs=missing,full_ticket_depth_multiplier=k,
                              max_multiplier_among_positive_capacity_legs=float(finite.max()) if len(finite) else np.nan,
                              snapshot_fraction_filled=float(np.minimum(g.desired,np.floor(g.saved_eligible_capacity)).sum()/g.desired.sum())))
    s=pd.DataFrame(summaries);s.to_csv(PROCESSED/'maya_liquidity_requirements_summary.csv',index=False)
    lines=['| Farm | Extra cover | Required contracts | Fraction at saved proxy depth | Zero-capacity legs | Max multiplier where offers exist |',
           '|---|---|---:|---:|---:|---:|']
    for r in s.itertuples():
        lines.append(f'| {r.farm_id} | {r.policy} | {r.required_contracts} | {r.snapshot_fraction_filled:.0%} | {r.missing_useful_offer_legs} | {r.max_multiplier_among_positive_capacity_legs:.1f} |')
    write_table(DOCS/'analysis/33_liquidity_requirements.md','<!-- BEGIN AUTO: liquidity -->','<!-- END AUTO: liquidity -->','\n'.join(lines))


if __name__=='__main__':main()
