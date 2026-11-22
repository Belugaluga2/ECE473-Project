"""Offline direct-tail experiment. Protocol and interpretation: doc 34.

No downloads, trading, or selection on evaluation years. All declared candidates
and loss sensitivities are retained, including failures and zero-purchase choices.
"""
from __future__ import annotations
import hashlib
import json
import sys
import numpy as np
import pandas as pd
import scipy
from agri_hedge.config import ROOT, PROCESSED, DOCS, FIGURES
from agri_hedge import hedge_builder as hb
from agri_hedge.loss_model import build_farm_model
from agri_hedge.prf_intervals import INTERVAL_MONTHS
from agri_hedge.paper_evidence import paired_year_blocks
from agri_hedge.direct_tail import cvar, cost, resize, fit_candidates, select_candidates

PROTOCOL = ROOT/'data/scenarios/maya_direct_protocol.json'
DOC = DOCS/'analysis/34_direct_tail_optimization.md'
BEGIN = '<!-- BEGIN AUTO: direct tail -->'
END = '<!-- END AUTO: direct tail -->'


def period(years, limits):
    return (years >= limits[0]) & (years <= limits[1])


def case_data(farm, cfg):
    years = np.arange(cfg['fit_years'][0], cfg['evaluation_years'][1]+1)
    rain = hb.station_rain(farm['site']).reindex(years)
    legs = [(m, float(k)) for m in cfg['instrument_months'] for k in cfg['instrument_strikes_inches']]
    X = np.column_stack([np.where(rain[m].isna(), np.nan, (rain[m] <= k).astype(float))
                         for m, k in legs])
    official = pd.read_csv(PROCESSED/'prf_official_index.csv')
    official = official[official.grid_id == farm['request'].grid_id].pivot(
        index='year', columns='interval_name', values='index_value').reindex(years)
    losses = {}
    for variant in cfg['loss_variants']:
        timing, basis = variant.split('_')
        model = build_farm_model(farm['farm'], timing=timing, value_basis=basis, curvature=True)
        losses[variant] = np.asarray(model.loss_usd(official, gains=False))
        if variant == cfg['primary_loss']:
            index = np.asarray(model.season_index(official))
    prf = farm['prf_ncei_usd'].reindex(years).to_numpy(float)
    complete = np.isfinite(X).all(axis=1) & np.isfinite(prf) & np.isfinite(index)
    for value in losses.values():
        complete &= np.isfinite(value)
    severe = official[list(farm['farm']['interval_allocation'])].min(axis=1).to_numpy() <= 30
    saved = pd.read_csv(PROCESSED/'kalshi_rain_orderbook_summary.csv')
    saved = saved[(saved.study_site == farm['site']) & (saved.contract_month == '2026-11')]
    assert set(cfg['instrument_strikes_inches']).issubset(set(saved.strike))
    books = {float(row.strike): row.yes_bids for row in saved.itertuples()}
    return dict(years=years, X=X, legs=legs, losses=losses, index=index, prf=prf,
                complete=complete, severe=severe, books=books)


def summarize(y, prf, payout, total_cost, reference_cost, years, severe, cfg, uncertainty=False):
    residual = y+total_cost-payout
    baseline = y+reference_cost-prf
    short, base_short = np.maximum(residual, 0), np.maximum(baseline, 0)
    top = np.argsort(y)[-min(5, len(y)):]
    base_var = np.var(y-prf)
    out = dict(n_years=len(y), portfolio_cvar=float(cvar(short, cfg['cvar_alpha'])),
               baseline_cvar=float(cvar(base_short, cfg['cvar_alpha'])),
               mean_net_gain_vs_prf=float((baseline-residual).mean()),
               mean_positive_outlay=float(short.mean()),
               worst5_shortfall_improvement=float((base_short[top]-short[top]).mean()),
               baseline_worst5_shortfall=float(base_short[top].mean()),
               annual_shortfall_wins=int(np.sum(short < base_short-1e-6)),
               annual_shortfall_worse=int(np.sum(short > base_short+1e-6)),
               residual_variance_reduction=1-float(np.var(y-payout))/base_var if base_var > 1e-12 else np.nan,
               severe_years=int(severe.sum()),
               severe_gross_payout_wins=int(np.sum(severe & (payout > prf+1e-6))),
               payout_exceeds_proxy_loss_years=int(np.sum(payout > y+1e-6)))
    out['cvar_improvement'] = out['baseline_cvar']-out['portfolio_cvar']
    keep = np.arange(len(y)) != int(np.argmax(y))
    out['cvar_improvement_drop_worst_year'] = float(
        cvar(base_short[keep], cfg['cvar_alpha'])-cvar(short[keep], cfg['cvar_alpha']))
    out['dropped_year'] = int(years[np.argmax(y)])
    if uncertainty:
        ix = paired_year_blocks(len(y), cfg['bootstrap_draws'], cfg['bootstrap_block_years'], cfg['seed'])
        diff = cvar(base_short[ix], cfg['cvar_alpha'])-cvar(short[ix], cfg['cvar_alpha'])
        out['cvar_ci_low'], out['cvar_ci_high'] = np.quantile(diff, [.025, .975])
        means = (baseline[ix]-residual[ix]).mean(axis=1)
        out['mean_gain_ci_low'], out['mean_gain_ci_high'] = np.quantile(means, [.025, .975])
    return out


def main():
    cfg = json.loads(PROTOCOL.read_text(encoding='utf-8'))
    farms = {f['farm_id']: f for f in hb.load_farm_requests()}
    validations, selections, ticket_rows, price_rows, yearly, summaries, audits, fit_audits = [], [], [], [], [], [], [], []
    for fid in cfg['cases']:
        farm = farms[fid]
        d = case_data(farm, cfg)
        years, X, prf, complete = d['years'], d['X'], d['prf'], d['complete']
        primary = d['losses'][cfg['primary_loss']]
        fit = period(years, cfg['fit_years']) & complete
        validation = period(years, cfg['validation_years']) & complete
        refit = period(years, cfg['refit_years']) & complete
        evaluation = period(years, cfg['evaluation_years']) & complete
        C = float(farm['producer_premium'])
        for year, ok in zip(years, complete):
            position = int(np.flatnonzero(years == year)[0])
            audits.append(dict(farm_id=fid, year=int(year), complete=bool(ok),
                missing_airport_months=int((~np.isfinite(X[years == year][0].reshape(
                    len(cfg['instrument_months']), len(cfg['instrument_strikes_inches'])))).any(axis=1).sum()),
                missing_prf=not np.isfinite(prf[position]),
                missing_season_index=not np.isfinite(d['index'][position]),
                missing_loss_variants=sum(not np.isfinite(a[position]) for a in d['losses'].values())))
        for depth in cfg['depth_scenarios']:
            for arm, setting in cfg['budget_arms'].items():
                share, B = setting['prf_share'], setting['market_budget_share']*C
                base_payout, base_cost = share*prf, share*C
                early = fit_candidates(X, primary, d['index'], base_payout, base_cost, fit,
                                       B, d['legs'], d['books'], depth, cfg)
                chosen, scores = select_candidates(early, X, primary, base_payout, base_cost, validation, cfg)
                shape, _ = select_candidates(early, X, primary, base_payout, base_cost, validation, cfg, shapes_only=True)
                val_reference = float(cvar(np.maximum(primary[validation]+C-prf[validation], 0), cfg['cvar_alpha']))
                for row in scores:
                    validations.append(dict(farm_id=fid, depth=depth, arm=arm,
                                             selected=row['candidate'] == chosen,
                                             shape_selected=row['candidate'] == shape,
                                             validation_prf_cvar=val_reference, **row))
                final = fit_candidates(X, primary, d['index'], base_payout, base_cost, refit,
                                       B, d['legs'], d['books'], depth, cfg)
                selections.append(dict(farm_id=fid, depth=depth, arm=arm, selected=chosen,
                                       selected_shape=shape, fit_n=int(fit.sum()), validation_n=int(validation.sum()),
                                       refit_n=int(refit.sum()), test_n=int(evaluation.sum()),
                                       prf_share=share, market_budget=B, total_resources=base_cost+B))
                for stage, tickets in [('fit_validation', early), ('refit_evaluation', final)]:
                    fitting = fit if stage == 'fit_validation' else refit
                    ref = tickets['cash']
                    for j, (month, strike) in enumerate(d['legs']):
                        price_rows.append(dict(farm_id=fid, depth=depth, arm=arm, stage=stage,
                                               month=month, strike=strike, fair=ref['fair'][j],
                                               modeled_ask=ref['asks'][j], capacity=ref['limits'][j]))
                    for name, ticket in tickets.items():
                        training_outlay = np.maximum(primary[fitting]+base_cost+ticket['cost']-
                                                     base_payout[fitting]-X[fitting]@ticket['counts'], 0)
                        fit_audits.append(dict(farm_id=fid, depth=depth, arm=arm, stage=stage,
                                               candidate=name, fitting_years=int(fitting.sum()),
                                               training_cvar=float(cvar(training_outlay, cfg['cvar_alpha'])),
                                               continuous_training_reference=ticket.get('continuous_training_cvar', np.nan),
                                               market_cost=ticket['cost'], market_budget=B,
                                               budget_slack=B-ticket['cost'],
                                               contract_count=int(ticket['counts'].sum()),
                                               depth_feasible=bool((ticket['counts'] <= ticket['limits']).all())))
                        for j in np.flatnonzero(ticket['counts']):
                            month, strike = d['legs'][j]
                            ticket_rows.append(dict(farm_id=fid, depth=depth, arm=arm, stage=stage,
                                                    candidate=name, selected=name == chosen, month=month,
                                                    strike=strike, counts=int(ticket['counts'][j]),
                                                    ask=ticket['asks'][j], capacity=ticket['limits'][j]))
                for name, ticket in final.items():
                    selected, shape_selected = name == chosen, name == shape
                    for price, spread, days in [
                        ('central', cfg['central_half_spread'], cfg['central_carry_days']),
                        ('wide_spread', cfg['wide_half_spread'], cfg['central_carry_days']),
                        ('carry_180_days', cfg['central_half_spread'], cfg['long_carry_days'])]:
                        asks = np.clip(ticket['fair']+spread, *cfg['ask_bounds'])
                        counts, scale = resize(ticket['counts'], asks, B, cfg, days)
                        spent = cost(counts, asks, cfg, days)
                        assert spent <= B+1e-6 and (counts <= ticket['limits']).all()
                        total_cost, budget = base_cost+spent, base_cost+B
                        market = X[evaluation]@counts
                        payouts = base_payout[evaluation]+market
                        common = dict(farm_id=fid, depth=depth, arm=arm, candidate=name,
                                      selected=selected, shape_selected=shape_selected, price_scenario=price)
                        for i, year in enumerate(years[evaluation]):
                            yearly.append(dict(**common, year=int(year), loss_proxy=primary[evaluation][i],
                                               prf_payout=prf[evaluation][i], market_payout=market[i],
                                               total_payout=payouts[i], prf_share=share, market_cost=spent,
                                               total_premium=total_cost, total_budget=budget,
                                               cash_retained=B-spent, contract_count=int(counts.sum()),
                                               stress_quantity_scale=scale, severe=bool(d['severe'][evaluation][i])))
                        for variant, losses in d['losses'].items():
                            result = summarize(losses[evaluation], prf[evaluation], payouts, total_cost,
                                               C, years[evaluation], d['severe'][evaluation], cfg,
                                               uncertainty=selected or shape_selected or name == 'direct_cvar')
                            summaries.append(dict(**common, loss_variant=variant, market_cost=spent,
                                                  total_premium=total_cost, market_budget=B, cash_retained=B-spent,
                                                  contract_count=int(counts.sum()), **result))
        print(f'Completed {fid}: fit {fit.sum()}, validation {validation.sum()}, replay {evaluation.sum()} years', flush=True)
    tables = {'validation': validations, 'selection': selections, 'tickets': ticket_rows,
              'prices': price_rows, 'years': yearly, 'summary': summaries, 'missing_years': audits,
              'fit_audit': fit_audits}
    for suffix, rows in tables.items():
        pd.DataFrame(rows).to_csv(PROCESSED/f'maya_direct_{suffix}.csv', index=False)
    quote_audit = pd.DataFrame(ticket_rows).merge(pd.DataFrame(price_rows),
        on=['farm_id', 'depth', 'arm', 'stage', 'month', 'strike'], validate='many_to_one')
    quote_audit = quote_audit[(quote_audit.stage == 'refit_evaluation') & quote_audit.selected]
    audit_rows = []
    for key, g in quote_audit.groupby(['farm_id', 'depth', 'arm', 'candidate']):
        below_fair = g.ask < g.fair-1e-12
        audit_rows.append(dict(farm_id=key[0], depth=key[1], arm=key[2], candidate=key[3],
                               contracts=int(g.counts.sum()),
                               contracts_with_training_fair_one=int(g.loc[g.fair >= 1-1e-12, 'counts'].sum()),
                               contracts_with_clipped_ask_below_training_fair=int(g.loc[below_fair, 'counts'].sum())))
    pd.DataFrame(audit_rows).to_csv(PROCESSED/'maya_direct_price_boundary_audit.csv', index=False)
    inputs = ['data/scenarios/farms.yaml', 'data/scenarios/maya_direct_protocol.json',
              'data/processed/prf_official_index.csv', 'data/processed/prf_scenario_results.csv',
              'data/processed/station_monthly_precip.csv', 'data/processed/kalshi_rain_orderbook_summary.csv',
              'data/processed/crop_rain_sensitivity_other.csv', 'src/agri_hedge/loss_model.py',
              'src/agri_hedge/direct_tail.py', 'scripts/run_direct_tail.py']
    metadata = dict(protocol=cfg, protocol_commit='bb50e11',
                    environment=dict(python=sys.version, numpy=np.__version__, pandas=pd.__version__, scipy=scipy.__version__),
                    hashes={p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in inputs},
                    pricing='modeled; no live quotes; repeat-November depth; seasonal listings not established',
                    interpretation='exploratory; no observed farm-income validation or fresh confirmation')
    (PROCESSED/'maya_direct_method.json').write_text(json.dumps(metadata, indent=2)+'\n', encoding='utf-8')
    summary = pd.DataFrame(summaries)
    render(summary, pd.DataFrame(selections), cfg)


def render(summary, selection, cfg):
    view = summary[summary.selected & (summary.price_scenario == 'central') &
                   (summary.loss_variant == cfg['primary_loss'])]
    lines = ['| Farm | Budget decision | Depth | Validation-selected method | CVaR improvement vs PRF ($/yr) | 95% paired interval | Worst-five-loss-year improvement ($/yr) |',
             '|---|---|---|---|---:|---|---:|']
    for r in view.itertuples():
        lines.append(f'| {r.farm_id} | {r.arm} | {r.depth} | {r.candidate} | {r.cvar_improvement:.0f} | [{r.cvar_ci_low:.0f}, {r.cvar_ci_high:.0f}] | {r.worst5_shortfall_improvement:.0f} |')
    text = DOC.read_text(encoding='utf-8')
    a, b = text.index(BEGIN)+len(BEGIN), text.index(END)
    DOC.write_text(text[:a]+'\n\n'+'\n'.join(lines)+'\n\n'+text[b:], encoding='utf-8')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.2))
    arms = list(cfg['budget_arms'])
    for ax, fid in zip(axes, cfg['cases']):
        for offset, depth, color, label in [(-.18, 'unlimited', '#2563A6', 'Unlimited depth'),
                                             (.18, 'saved_depth_proxy', '#C0782B', 'Saved-depth proxy')]:
            group = view[(view.farm_id == fid) & (view.depth == depth)].set_index('arm').loc[arms]
            ax.bar(np.arange(3)+offset, group.cvar_improvement, width=.34, color=color, label=label)
        ax.axhline(0, color='#555555', linewidth=.8)
        ax.set_title(fid.replace('_', ' '))
        ax.set_xticks(np.arange(3), ['Replace', '80/20 mix', 'PRF + extra'])
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f'${v:,.0f}'))
        ax.grid(axis='y', alpha=.2)
    axes[0].set_ylabel('Reduction in worst-20% positive net outlay\nrelative to PRF (positive = better)')
    axes[0].legend(fontsize=8)
    fig.suptitle('Validation-selected portfolios; modeled replacement-feed losses and prices', fontsize=11)
    fig.text(.5, .01, 'Exploratory 2001-2025 replay. Seasonal availability is hypothetical; saved November depth is repeated across months.',
             ha='center', fontsize=8)
    fig.tight_layout(rect=(0, .05, 1, .95))
    fig.savefig(FIGURES/'maya_direct_tail_results.png', dpi=180)
    fig.savefig(FIGURES/'maya_direct_tail_results.pdf')
    plt.close(fig)
    addon = view[view.arm == 'addon'].set_index(['farm_id', 'depth'])
    fig, ax = plt.subplots(figsize=(8.8, 4.5))
    for offset, depth, color, label in [(-.18, 'unlimited', '#2563A6', 'Unlimited depth'),
                                       (.18, 'saved_depth_proxy', '#C0782B', 'Saved-depth proxy')]:
        group = addon.loc[[(fid, depth) for fid in cfg['cases']]]
        values = group.cvar_improvement.to_numpy()
        intervals = np.vstack([values-group.cvar_ci_low.to_numpy(), group.cvar_ci_high.to_numpy()-values])
        ax.bar(np.arange(3)+offset, values, width=.34, color=color, label=label)
        ax.errorbar(np.arange(3)+offset, values, yerr=np.maximum(intervals, 0),
                    fmt='none', ecolor='#303030', capsize=4, linewidth=1)
    ax.axhline(0, color='#555555', linewidth=.8)
    ax.set_xticks(np.arange(3), ['Dallas hay', 'San Antonio pasture', 'Albuquerque pasture'])
    ax.set_ylabel('Reduction in tail shortfall vs PRF ($/year)')
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f'${v:,.0f}'))
    ax.set_title('Keep PRF: small, uncertain gains from extra cover')
    ax.grid(axis='y', alpha=.2)
    ax.legend(fontsize=9)
    fig.text(.5, .035, 'Validation-selected portfolios; growth/replacement loss proxy; paired 95% intervals.\n'
             'CVaR averages the worst 20% of positive net outlays. Seasonal market availability is hypothetical.',
             ha='center', fontsize=8)
    fig.tight_layout(rect=(0, .12, 1, 1))
    fig.savefig(FIGURES/'maya_direct_addon_uncertainty.png', dpi=180)
    fig.savefig(FIGURES/'maya_direct_addon_uncertainty.pdf')
    plt.close(fig)
    print(view[['farm_id', 'arm', 'depth', 'candidate', 'cvar_improvement',
                'cvar_ci_low', 'cvar_ci_high', 'worst5_shortfall_improvement']].round(2).to_string(index=False))


if __name__ == '__main__':
    main()
