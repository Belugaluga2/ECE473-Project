# 32: Keep PRF, compare the extra budget, and audit the loss scale

**Frozen follow-up specification, 2026-11-22. Exploratory; no fresh validation.**
The earlier doc 30 tested reallocating a fixed PRF-sized budget: 80% PRF plus 20%
market cover. This tests a different decision: keep the original policy and decide
how to use an additional 20% budget. The market contracts are exactly the previously
fitted portfolios; nothing is refit or selected to improve the result.

## Fixed comparison

- Same Dallas hay, San Antonio grazing and Albuquerque grazing profiles.
- Every arm keeps 100% of the original PRF policy and has the same extra resources.
- Extra resources are 20% of the original PRF producer premium. Compare retained cash,
  the fixed winter companion, and the existing exponential, disaster-only and binary
  tail designs. All families are reported; there is no winning-shape selection.
- Actual listed monthly strike payoffs remain the instruments. November saved-book
  capacity is a stress proxy, not an executable full-season or historical book.
- Same 1951-2000 fitting period and 2001-2025 replay from doc 30; already-inspected years.
- The original cash reference retains its extra budget, rather than being forced to
  spend it. Differences in premiums are included in dollar shortfalls and net gains.

For example, a $1,000 original PRF premium previously became $800 PRF plus up to $200
market cover. Here it remains $1,000 PRF, with an extra $200 available for either cash
or market cover. Any improved payout must therefore be assessed against that extra
expense. The 20% allocation is an illustration, not an optimized recommendation.
This does not exhaust all changes to an existing PRF policy: Dallas and Albuquerque
already use the 150% productivity-factor ceiling, while San Antonio uses 145%
(`farms.yaml`; permitted range in doc 01). Increasing every policy by another 20%
through that factor would not be a valid alternative for these profiles.

The primary loss sensitivity is **growth timing with replacement-feed valuation**,
chosen before this follow-up's results because replacement feed is closer to a rancher's
direct drought expense than land rent. Growth/rent, growth/protection and all three
allocation-timing variants are also retained. No valuation is established as observed
farm loss. The same model coefficients are used throughout.

## Why audit loss assumptions?

The old default monetizes hay as yield times hay price but grazing as pasture cash rent.
PRF's maximum indemnity instead uses county base value, productivity factor and coverage.
Those are different economic quantities. A large maximum indemnity relative to a mean
modeled loss is not automatically a calculation error or evidence of excessive insurance.
It can reflect different valuations, a weak rainfall-loss proxy or omitted actual costs.

The audit records, per profile and valuation: normal value per acre and in total, maximum
policy protection, producer premium, elasticity and curvature sources, loss if all rainfall
indices are zero, and average proxy loss. Replacement hay uses the existing 25% harvest
efficiency and state hay prices, rather than a new coefficient selected for this result.
The protection-valued variant is a scale sensitivity tied to PRF's value basis, not an
independent measurement of farm losses.

Existing doc 13 already cautions that hay validation uses statewide yields and is not
independent of calibration; San Antonio uses pooled curvature and Albuquerque's forage
calibration is model-based and weak. This follow-up diagnoses those boundaries rather
than quietly replacing the old target with one that makes the hedge win.

## Metrics

- Mean net gain versus cash = average market payout minus additional economic premium.
- Incremental HE = `1-Var(loss-PRF-market)/Var(loss-PRF)`: reduction in residual variation
  after PRF, distinct from doc 21's rain-payout fit and doc 30's total loss-proxy HE.
- Worst-five shortfall reduction compares `max(loss+premium-payout,0)` in each loss
  variant's five worst replay years. Positive means less uncovered shortfall.
- Paired two-year-block bootstrap intervals, wider spread prices, and dropping the
  single worst proxy-loss year. They are conditional historical sensitivities, not
  future guarantees or new catastrophe observations.

Here "shortfall" is a premium-inclusive positive net outlay relative to normal farm
value, not a test of cash-on-hand solvency or a measured loss after using a reserve.
Both arms start with the same additional resources; retained cash is not charged as a
premium. Variance ignores constant payout bias, so HE cannot establish adequate coverage.

## Results: replacement/growth sensitivity, unlimited depth

<!-- BEGIN AUTO: prf addons -->

| Farm | Extra-budget use | Mean net gain vs cash ($/yr) | Residual variance reduction | Worst-five shortfall reduction ($) |
|---|---|---:|---:|---:|
| ABQ_graze | cash | 0 | 0.000 | 0 |
| ABQ_graze | tail_deep50 | 124 | 0.014 | 588 |
| ABQ_graze | tail_digital30 | 190 | 0.023 | 896 |
| ABQ_graze | tail_exp5 | 43 | 0.014 | 479 |
| ABQ_graze | winter_companion | -136 | 0.007 | 66 |
| DFW_hay | cash | 0 | 0.000 | 0 |
| DFW_hay | tail_deep50 | -6 | -0.143 | 7 |
| DFW_hay | tail_digital30 | -27 | -0.163 | -4 |
| DFW_hay | tail_exp5 | 10 | -0.132 | 25 |
| DFW_hay | winter_companion | -113 | -0.048 | 42 |
| SAT_graze | cash | 0 | 0.000 | 0 |
| SAT_graze | tail_deep50 | 128 | -0.035 | 216 |
| SAT_graze | tail_digital30 | 108 | -0.038 | 189 |
| SAT_graze | tail_exp5 | 123 | -0.030 | 240 |
| SAT_graze | winter_companion | 36 | 0.010 | 134 |

<!-- END AUTO: prf addons -->

## What the follow-up establishes

The add-on decision differs from the reallocation decision. It gives some positive
conditional results without establishing a generally superior product. Dallas's extra
cover increases residual variation under every tested valuation/timing combination.
San Antonio is mixed and sensitive to the loss definition. Albuquerque has the clearest
incremental improvement under feed-replacement valuation, but its HE sign reverses
under the rent-valued loss target. The result depends on what loss we think is insured.

The following values are from `maya_loss_scale_audit.csv` and
`maya_prf_addon_summary.csv`, central prices, test years, unless stated otherwise:

| Audit or sensitivity | Value | Interpretation |
|---|---:|---|
| Albuquerque normal pasture rent / acre | $1.70 | Existing default valuation, not all drought expenses |
| Albuquerque feed-replacement value / acre | $27.42 | Existing production, 25% harvest efficiency and hay-price convention |
| Albuquerque policy protection / normal rent value | 8.62x | Different value bases; not proof of PRF overpayment |
| Albuquerque digital add-on: extra annual budget | $2,423.97 | 20% of the original $12,119.85 producer premium |
| Same, unlimited depth: residual variance reduction | 2.3% | Relative to full PRF, under growth/replacement proxy |
| Same, unlimited depth: worst-five shortfall reduction | $896/year | Average of the five worst modeled-loss replay years |
| Same: mean net gain vs cash, paired 95% interval | $190/year, [-$189, $527] | Positive mean does not establish a reliably positive return |
| Same, saved capacity proxy: worst-five reduction | $152/year | Limited fills substantially reduce the benefit |
| Same, saved capacity proxy: mean net gain | -$65/year | Extra cover can reduce selected tail shortfalls while costing money on average |

The unlimited-depth Albuquerque digital result is one reported member of the whole
fixed family, not a selected product recommendation. Bootstrap intervals remain
conditional on the short observed replay; they cannot discover unobserved catastrophes.
Rent-to-replacement conversion changes valuation, not rainfall sensitivity calibration
or geographic mismatch. Actual feed purchases, stocking changes and farm income would
be needed to validate protection. Do not inflate a proxy merely to make a hedge win.

## Can an existing-strike portfolio win in an individual year?

Yes, under the modeled prices and full-fill assumption. This retrospective illustration
uses frozen doc-30 portfolios and the growth/replacement loss sensitivity. It is not
selection on a new confirmation sample or an actual trade. The 2009 year is outside
doc 30's very specific severe-state flag (any selected PRF interval index <=30), even
though the growth/replacement proxy estimates a substantial annual forage loss.

| Albuquerque example | PRF payout | Portfolio payout | Replacement loss proxy | Interpretation |
|---|---:|---:|---:|---|
| 2009, existing monthly digital-target portfolio | $2,059 | $19,495 | $62,072 | Lower modeled shortfall in this year at approximately the same $12,120 budget; assumes unlimited depth |
| 2018, same existing-monthly portfolio | $25,055 | $15,625 | $68,900 | Pays less than PRF in this severe-flagged year |
| 2018, proposed two-month third-inch deep50 portfolio | $25,055 | $26,560 | $68,900 | Higher payout and lower modeled shortfall; proposed instruments, unlimited depth |

Source: join `maya_matched_premium_years.csv` and `maya_addon_loss_variants.csv` on
farm/year, central prices, test years, growth/replacement variant. Exact costs and
premium-inclusive shortfalls are printed by `scripts/inspect_paper_results.py`.

The full frozen-family audit is saved as `maya_matched_loss_audit.csv`, including all
six loss variants and both price scenarios. Under growth/replacement and central prices,
the Albuquerque monthly digital-target portfolio has lower premium-inclusive shortfall
than PRF in 8 of 25 replay years and higher shortfall in 15, with 2 ties. Its mean
shortfall in the five worst modeled-loss years is about $28,547 worse than PRF with
unlimited depth. Across these three cases, no tested replacement or reallocation
strategy improves that five-worst-years metric under this valuation. These numbers
are sourced to the audit CSV via the inspection script, which checks that its rent
variant reproduces doc 30. Annual wins can also result from spending less and retaining
cash; a win count is not a sufficient insurance-quality score.

Thus "sometimes pays more" is supported, including an existing-strike illustration.
"Protects the worst losses better overall" is not supported for these frozen replacements.
The PRF-kept add-ons answer a separate extra-budget question, as reported above.

## Reproduce, sources and numbers

```powershell
$env:PYTHONPATH='src'
python scripts/run_prf_addons.py
python scripts/inspect_paper_results.py
```

Use the original project `.venv` as shown in the entry guide. The script is offline.
Inputs are the frozen doc-30 yearly payouts/tickets, farms.yaml, official PRF index and
existing loss-model calibration. Outputs: `maya_prf_addon_years.csv`,
`maya_prf_addon_summary.csv`, `maya_loss_scale_audit.csv`,
`maya_addon_loss_variants.csv`, and `maya_prf_addon_method.json`.
Every result in the table comes from the summary CSV via this script. These are
weather-driven loss proxies, not verified income protection, buyer demand or arbitrage.
