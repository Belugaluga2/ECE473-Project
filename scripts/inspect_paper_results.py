"""Audit frozen matched-budget outcomes under every existing loss sensitivity.

No fitting, parameter search, downloads or orders. All replay years are already
inspected. Writes a diagnostic CSV; individual examples are retrospective.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from agri_hedge.config import PROCESSED


def main():
    old = pd.read_csv(PROCESSED / 'maya_matched_premium_years.csv')
    old = old[old.evaluation == 'test']
    losses = pd.read_csv(PROCESSED / 'maya_addon_loss_variants.csv')
    frame = old.drop(columns='loss_proxy').merge(losses, on=['farm_id', 'year'],
                                               validate='many_to_many')
    keys = ['price_scenario', 'farm_id', 'policy', 'depth', 'loss_variant']
    rows = []
    for key, group in frame.groupby(keys):
        group = group.sort_values('year')
        assert not group.year.duplicated().any()
        loss = group.loss_proxy.to_numpy()
        short = np.maximum(loss + group.premium.to_numpy() - group.payout.to_numpy(), 0)
        base = np.maximum(loss + group.budget.to_numpy() - group.prf_reference.to_numpy(), 0)
        top = np.argsort(loss)[-5:]
        difference = base - short
        rows.append(dict(zip(keys, key)) | {
            'n_years': len(group),
            'annual_shortfall_win_years': int(np.sum(difference > 1e-6)),
            'annual_shortfall_worse_years': int(np.sum(difference < -1e-6)),
            'baseline_worst5_shortfall': float(base[top].mean()),
            'portfolio_worst5_shortfall': float(short[top].mean()),
            'worst5_shortfall_improvement': float(difference[top].mean()),
        })
    summary = pd.DataFrame(rows)
    reference = pd.read_csv(PROCESSED / 'maya_matched_premium_summary.csv')
    check = summary[summary.loss_variant == 'growth_rent'].merge(
        reference[reference.evaluation == 'test'],
        on=['price_scenario', 'farm_id', 'policy', 'depth'], validate='one_to_one')
    assert np.allclose(check.worst5_shortfall_improvement, check.worst5_improvement_vs_prf)
    summary.to_csv(PROCESSED / 'maya_matched_loss_audit.csv', index=False)
    view = summary[(summary.price_scenario == 'central') &
                   (summary.loss_variant == 'growth_replacement') &
                   (summary.policy != 'prf_only')]
    print('Full frozen-family audit, growth/replacement proxy; positive = improvement')
    print(view[['farm_id', 'policy', 'depth', 'annual_shortfall_win_years',
                'annual_shortfall_worse_years', 'worst5_shortfall_improvement']]
          .round(2).to_string(index=False))
    examples = frame[(frame.price_scenario == 'central') &
                     (frame.loss_variant == 'growth_replacement') &
                     (frame.farm_id == 'ABQ_graze') & (frame.depth == 'unlimited') &
                     frame.year.isin([2009, 2018]) & frame.policy.isin([
                         'prf_only', 'tail_digital30_listed',
                         'tail_deep50_proposed_sum_third'])].copy()
    examples['premium_inclusive_shortfall'] = np.maximum(
        examples.loss_proxy + examples.premium - examples.payout, 0)
    print('\nRetrospective illustrations; unlimited modeled depth, not executed trades')
    print(examples[['year', 'policy', 'loss_proxy', 'payout', 'premium',
                    'premium_inclusive_shortfall', 'severe']].round(2).to_string(index=False))


if __name__ == '__main__':
    main()
