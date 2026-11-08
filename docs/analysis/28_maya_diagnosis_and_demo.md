# 28: Diagnose misses, freeze a demonstration contract, and audit replication

**2026-11-08, `maya-experiments`.** This is an exploratory diagnostic of already-inspected
doc 27 outcomes, not a new validation sample. Its fitted crop-payout models stay frozen.
The methods below are recorded before computing these new diagnostic comparisons. Preserve
docs 25-27 and the PRF Companion app. No trades, accounts, real-money settlement or deployment.

## Findings: what is established and what is not

The new evidence diagnoses **three different problems**, rather than a single bad coefficient:

1. **Contract size.** Both signals fire in the severe 2012 cases, yet payments are well below
   the observed shortfalls. For this one-feature payout shape, the chosen expected-payout budget
   forces its coefficient. Increasing the coefficient increases its modeled premium in the same
   proportion. We have not proved that this is the globally optimal insurance design.
2. **Coverage mismatch.** Some observed yield shortfalls occur without the selected drought/heat
   signals. Others have very little heat inside the covered season, or contextual stress outside
   it. The index can therefore miss a crop loss even when the code settles the formula correctly.
3. **Target uncertainty.** The estimated loss changes with the production forecast. All of the
   nine largest misses remain positive under every fixed forecast sensitivity, so these misses
   are not eliminated by simply swapping this forecast formula. None of the alternatives is
   established as the farmer's actual expected yield or insured loss.

The fixed rule should be described as **limited joint-stress cover**, not comprehensive crop
insurance. The observed sensitivity still depends heavily on the known disaster year. No new
crop fit or new evidence of arbitrage has been produced here.

### Specific cases: confirmed mechanics versus possible explanations

| Case | Confirmed in our data/formula | External context and what remains unknown |
| --- | --- | --- |
| Story, 2013 | June-July heat severity is tiny, so the minimum rule pays very little. August rain is below its earlier tenth percentile, outside the policy window. | NASS's Iowa summary describes a wet spring followed by dry conditions; delayed timing and late drought are plausible omitted exposures. We cannot allocate the county shortfall to those mechanisms. |
| Tippecanoe, 2015 | Both covered severities are zero; June-July rain is unusually high. The separate W benchmark covers April-May, so it does not measure this wet-summer episode. | Indiana's official annual summary documents excessive rainfall and crop damage. This supports investigating an omitted wet-summer peril, but does not establish its causal share of Tippecanoe's shortfall. |
| Story, 2020 | The contract pays, but only partially; August wind is absent from its formula. August also has a dry-context flag. | NWS records the August derecho and Story County wind reports. Wind is a credible missing peril alongside drought; our county data do not identify how much loss came from either one. |
| Other large misses | The trigger/budget explanations and forecast ranges are observable in the generated tables. | Specific causal attribution remains unknown. We do not invent a disease, flood, management or station explanation without evidence. |

Sources for context, not causal identification:
[NASS Iowa annual bulletin, crop/weather summary](https://publications.iowa.gov/43209/1/2014_Iowa_Annual_Bulletin.pdf#page=6),
[NASS Indiana annual bulletin, crop/weather summary](https://data.nass.usda.gov/Statistics_by_State/Indiana/Publications/Annual_Statistical_Bulletin/1516/IN1516Bulletin.pdf#page=32),
and [NWS August derecho report](https://www.weather.gov/dmx/2020derecho).
All measured case values and percentile flags are in this document's generated tables and
`maya_case_diagnosis.csv`; prose does not convert a state/regional report into a farm claim.

### What the replication exercise establishes

The checked open Chicago markets do not supply a pre-season summer portfolio for this contract.
Even the numerical counterfactuals are restricted retrospective approximations, not executable
orders. Local continuous primitives track the proposed payment better than the tested Chicago
baskets; binary ladders, regularization, geography and measurement all change the comparison.
We do not isolate geography as the sole cause or prove the chosen portfolio family optimal.

The endpoint argument does establish a general static spanning gap for the min rule over its
whole severity domain. Approximate replication can still be useful on the weather states that
actually occur. Meanwhile, accurate payout replication alone would not establish useful crop
loss protection. These distinctions directly address the original event-contract project topic.

### Recommended direction after this diagnosis

Preserve the existing PRF Companion and use the new demo as a research extension. Present the
contract's limited purpose and its coverage/replication gaps honestly. The best next empirical
question is whether a better-defined insured-loss target and crop-stage/soil-moisture measurements
can justify a broader exposure design on a separate confirmation sample. Do not select a new
window or threshold because it rescues the already-inspected cases here. A new wet-summer or
late-season contract would be a new hypothesis, requiring its own evaluation and settlement rule.

The current demonstration already implements a fixed specification and offline settlement replay.
A later testnet component could demonstrate escrow/oracle plumbing if the course requires it;
it would not make the economic evidence stronger. Source revision, counterparty, licensing and
dispute arrangements are unresolved requirements for any real product.

## Fixed diagnostic plan

Use doc 27's selected **equal-premium weakest-link** rule on its three held-out counties and
its original common final-year cohort. Rank the nine largest net shortfalls and up to five
positive overpayments. Classify the **mechanical payment reason**, separately from possible causes of
crop loss. Check which drought/heat triggers fired and whether payment size was insufficient.
Do not infer a causal crop-damage explanation from a weather association.

Keep the original forecast target primary. As diagnostic sensitivities only, recalculate
shortfalls using an earlier-only ten-observation linear trend (minimum eight), twenty-observation
log-linear trend (minimum fifteen), and previous five available yields' mean (minimum five).
Do not choose the forecast that makes protection look best, refit payouts, or call these new
out-of-sample policy results. Also show a hypothetical ten-percentage-point deductible, clearly
distinct from actual USDA policy terms. This checks how much a miss depends on our target.

Add August rainfall and heat context at the same held-out county points, from the existing
public ACIS grid request (or its identical cached/refetched input). August drought below its
earlier tenth percentile, or heat above its earlier ninetieth, is an **outside-window clue**,
not proof of loss causation. Calibrate these context thresholds through 2009 only. Record
missingness and source hashes. No new feature or trigger is added to the fitted payout.
June-July rain above its earlier ninetieth percentile is a wet-summer context flag, separate
from W's April-May window. These diagnostic flags are not new policy triggers.

## Coefficients and a fixed demonstration contract

Explain the exact coefficient arithmetic: with one feature `Z=min(D,H)` and fixed modeled
premium `pi`, equality of the training payout budget forces
`a = pi / ((1 + load) * mean_training(Z))`. Therefore `a` is a contract-size coefficient, not
a causal biological response or a freely optimized coefficient once the budget is fixed.
For multi-feature families, document the constrained centered-error/ridge objective, training
sample, temporal validation scores, triggers and fitted weights from `panel_models.json`.

Freeze an **illustrative**, parameterized contract for each reserved county, using that saved
model and its county normalizers. Its declared notional is expected crop value, not verified
farm revenue. Observe all June-July source days; use ACIS NRCC grid 1 at the committed county
point and the source's daily observation convention. No actual listed contract uses this exact
specification. Training climate is frozen through 2009. The selected family's actual maximum
payment is its single coefficient times notional, below the optimizer's general cap.

Demonstrate offline deterministic settlement from committed daily readings, with cents rounding,
source/input hashes, a premium scenario and sufficient capped mock collateral. Reject incomplete,
duplicate, negative-rain or invalid temperature observations. This is a replay of a proposed
rule, not an oracle attestation, enforceable insurance policy, dApp or testnet transaction.
For a future-season template, coverage must be bought before the observation period; an example
final data snapshot is August 15 at 12:00 UTC. Missing data leaves settlement pending. Revisions,
disputes, source licensing and a real counterparty require further decisions, not invented answers.

## Replication audit: separate what is listed from what is hypothetical

Refresh a separate, dated public Chicago rain/heat listing snapshot. Keep old market inputs
unchanged. Check future-season availability, station/source, observed strike structure and whether
Tmin is an underlying. Today's November asks/depth cannot price or supply a summer portfolio.
If no requested summer contracts are listed, report **not currently constructible**, rather than
producing an executable portfolio or an arbitrage claim.

For an explicitly **counterfactual** numerical comparison, fit nonnegative static portfolios
to the frozen contract payout, using earlier weather only (not crop losses):

| Basis | Meaning / limitation |
| --- | --- |
| local continuous | D and H treated as hypothetical continuous primitives |
| local synthetic ladders | Separate binary YES/NO severity thresholds 0.10, 0.25, 0.50, 0.75 |
| Chicago rain structure | June/July O'Hare YES/NO rainfall thresholds at 1-7 inches; transplant the checked monthly structure to unlisted summer months |
| Chicago rain + hypothetical summer heat | Above plus Midway Tmax counts at 80, 85, 90, 95, 100 F; these summer strikes/pre-season listings are invented scenarios |

Use the same complete Chicago/local weather years for all bases. Missing Midway days retain the
prior pilot's flagged 3SW substitutions. With only a short annual record, heat positions share
weights across days; this is a restricted portfolio family, not a search over every daily position.
Require nonnegative positions and a conservative sum-of-coefficients limit equal to the proposed
contract's maximum payout fraction. No free negative cash, shorting or unmodeled borrowing.
Select ridge from 0.01, 0.10, 1.0 on earlier temporal folds only, by target-payoff MSE. Refit
through 2009; keep final years out of fitting. Fit per county, because each has different triggers.
These are retrospective diagnostics, not untouched tests of a newly selected crop hedge.

Report target-payoff RMSE/bias, gross payoff-replication HE, inferred historical fair cost and
a 10% loading scenario. Costs are not quotes and do not verify fees, integer fills, capital or
liquidity. Any crop-loss metric is secondary and cannot be used to select a replica. Never
equate accurate replication of the proposed payment with useful farm-loss protection.

For the actual joint rule `a*min(D,H)`, show the rectangular cross-difference. Additive separate
payoffs have zero cross-difference; this rule has `a` at the four endpoint states. Thus any
additive static approximation on that whole severity domain has worst-case absolute error at
least `a/4`. This is a spanning bound, not a probability-weighted prediction of realized error.
Show also that equal Tmax does not identify our heat-duration index when Tmin differs.

## Deliverables

- A short entry README in `experiments/maya/`, explaining formulas, coefficient choices,
  known limitations, files, offline commands and what to present.
- An isolated interactive demo with historical loss/payment comparisons, synthetic what-ifs,
  selected misses and a clear separation of listed contracts from hypothetical instruments.
- A CLI settlement replay and meaningful tests. Preserve the existing companion app.
- Generated diagnostic tables and findings, with numbers sourced to committed outputs.

## Results

Generated findings follow. Missing causal evidence remains labeled unknown; possible explanations
must not be promoted to confirmed reasons.

<!-- AUTO: maya diagnosis start -->
## Generated diagnosis and numbers tables

Reproduce offline: `.venv/Scripts/python.exe scripts/run_maya_diagnostics.py`.

### Why this coefficient?

| Quantity | Value | Source |
| --- | --- | --- |
| premium_fraction | 0.01 | maya_coefficient_audit.json / saved panel model |
| load | 0.1 | maya_coefficient_audit.json / saved panel model |
| mean_training_min_D_H | 0.08495460442608747 | maya_coefficient_audit.json / saved panel model |
| coefficient_from_budget | 0.10700902149239477 | maya_coefficient_audit.json / saved panel model |
| saved_coefficient | 0.10700902149239477 | maya_coefficient_audit.json / saved panel model |
| training_rows | 270 | maya_coefficient_audit.json / saved panel model |
| training_years | [1980, 1981, 1982, 1983, 1984, 1985, 1986, 1987, 1988, 1989, 1990, 1991, 1992, 1993, 1994, 1995, 1996, 1997, 1998, 1999, 2000, 2001, 2002, 2003, 2004, 2005, 2006, 2007, 2008, 2009] | maya_coefficient_audit.json / saved panel model |

With one feature, the equal-price constraint fixes its coefficient. Different ridge penalties cannot materially change that single coefficient under the same equality. Multi-feature fits choose how to allocate that budget by centered error plus ridge. These are contract weights, not causal crop-response coefficients.

### Earlier validation scores, primary models

| Family | Ridge | CV net error skill | Years | County-year rows |
| --- | --- | --- | --- | --- |
| drought | 0.0 | -0.004959 | 15 | 135 |
| drought | 0.01 | -0.004959 | 15 | 135 |
| drought | 0.1 | -0.004959 | 15 | 135 |
| heat | 0.0 | -0.028109 | 15 | 135 |
| heat | 0.01 | -0.028109 | 15 | 135 |
| heat | 0.1 | -0.028109 | 15 | 135 |
| rain_two_sided | 0.0 | -0.004959 | 15 | 135 |
| rain_two_sided | 0.01 | -0.004959 | 15 | 135 |
| rain_two_sided | 0.1 | -0.004959 | 15 | 135 |
| additive | 0.0 | -0.028109 | 15 | 135 |
| additive | 0.01 | -0.028109 | 15 | 135 |
| additive | 0.1 | -0.026762 | 15 | 135 |
| product | 0.0 | -0.043733 | 15 | 135 |
| product | 0.01 | -0.043733 | 15 | 135 |
| product | 0.1 | -0.043733 | 15 | 135 |
| weakest_link | 0.0 | 0.013130 | 15 | 135 |
| weakest_link | 0.01 | 0.013130 | 15 | 135 |
| weakest_link | 0.1 | 0.013130 | 15 | 135 |
| mixed | 0.0 | -0.043733 | 15 | 135 |
| mixed | 0.01 | -0.043733 | 15 | 135 |
| mixed | 0.1 | -0.029723 | 15 | 135 |
| worst_peril | 0.0 | -0.023246 | 15 | 135 |
| worst_peril | 0.01 | -0.023246 | 15 | 135 |
| worst_peril | 0.1 | -0.023246 | 15 | 135 |

### Largest nine net shortfalls: mechanical explanations

| County | Year | Forecast shortfall | Payment | D | H | Why payment is small/zero |
| --- | --- | --- | --- | --- | --- | --- |
| Tippecanoe | 2012 | 36.83% | 7.84% | 0.732 | 1.000 | both met; budget-sized payment is below shortfall |
| Story | 2013 | 25.69% | 0.15% | 0.342 | 0.014 | both met, but smaller severity is weak |
| Tippecanoe | 2015 | 20.53% | 0.00% | 0.000 | 0.000 | neither drought nor heat trigger met |
| Sangamon | 2012 | 27.79% | 9.12% | 0.853 | 1.000 | both met; budget-sized payment is below shortfall |
| Sangamon | 2010 | 17.98% | 0.00% | 0.000 | 0.000 | neither drought nor heat trigger met |
| Story | 2020 | 21.13% | 3.63% | 0.447 | 0.339 | both met; budget-sized payment is below shortfall |
| Story | 2010 | 13.98% | 0.00% | 0.000 | 0.000 | neither drought nor heat trigger met |
| Tippecanoe | 2011 | 12.58% | 0.00% | 0.000 | 0.498 | drought trigger not met; joint payment is zero |
| Story | 2011 | 13.09% | 0.57% | 0.054 | 0.490 | both met, but smaller severity is weak |

### Baseline and missing-peril context for the same cases

| County | Year | Loss range across fixed forecasts | Loss after hypothetical 10pp deductible | Jun-Jul rain in | Wet-summer clue | August rain in | August dry clue | August hot clue |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Tippecanoe | 2012 | 34.44%–37.33% | 26.83% | 3.15 | False | 5.54 | False | False |
| Story | 2013 | 13.70%–27.68% | 15.69% | 5.42 | False | 0.48 | True | False |
| Tippecanoe | 2015 | 11.86%–20.79% | 10.53% | 14.80 | True | 1.05 | True | False |
| Sangamon | 2012 | 24.56%–27.79% | 17.79% | 1.60 | False | 1.69 | False | False |
| Sangamon | 2010 | 15.57%–20.25% | 7.98% | 14.21 | True | 3.94 | False | False |
| Story | 2020 | 20.67%–28.30% | 11.13% | 4.43 | False | 1.65 | True | False |
| Story | 2010 | 7.62%–16.23% | 3.98% | 17.98 | True | 9.40 | False | False |
| Tippecanoe | 2011 | 6.68%–15.25% | 2.58% | 8.73 | False | 4.08 | False | False |
| Story | 2011 | 5.49%–15.17% | 3.09% | 8.14 | False | 2.50 | False | False |

These are diagnostics of a frozen policy, not refitted results or causal attribution. Range endpoints include all four predeclared production forecasts; none is chosen as correct. The deductible is an illustration, not a verified crop-insurance calculation.

| County FIPS | August rain p10 (in) | August heat p90 (C-days) | Jun-Jul rain p90 (in) |
| --- | --- | --- | --- |
| 17167 | 1.4060 | 28.9610 | 11.3850 |
| 18157 | 2.2480 | 18.2408 | 12.5610 |
| 19169 | 1.9780 | 13.3545 | 15.1200 |

### Up to five largest positive overpayments

| County | Year | Forecast shortfall | Payment | Overpayment |
| --- | --- | --- | --- | --- |
| Story | 2017 | 0.00% | 1.19% | 1.19% |
| Sangamon | 2017 | 0.00% | 1.11% | 1.11% |

### Existing market availability

| Item | Value | Source |
| --- | --- | --- |
| Public snapshot UTC | 2026-11-08T06:56:28.197760+00:00 | maya_market_snapshot.json |
| KXRAINCHIM | KXRAINCHIM-26NOV | public open-market list in snapshot |
| KXHIGHCHI | KXHIGHCHI-26NOV07, KXHIGHCHI-26NOV08 | public open-market list in snapshot |
| Rain thresholds checked | 1–7 inches, strictly greater YES / complementary NO | snapshot strike metadata |
| Summer-heat scenario thresholds | 80, 85, 90, 95, 100 F | protocol; invented seasonal scenario |
| Replica ridge grid | 0.01, 0.10, 1.0 | maya_replica_cv.csv |
| Current summer portfolio | not demonstrated / not currently constructible from checked listings | snapshot; no future summer events listed |

### Counterfactual long-only replication of the proposed payment

| County | Basis | Earlier years | Final years | Ridge | Target RMSE / expected crop value | Payoff replication HE | Modeled cost incl. 10% load |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Sangamon | local_continuous | 28 | 11 | 0.01 | 1.25% | 0.774 | 0.78% |
| Sangamon | local_ladders | 28 | 11 | 0.1 | 1.66% | 0.605 | 0.77% |
| Sangamon | chicago_rain | 28 | 11 | 1.0 | 2.51% | 0.106 | 0.73% |
| Sangamon | chicago_rain_hypothetical_heat | 28 | 11 | 0.01 | 2.07% | 0.372 | 0.94% |
| Story | local_continuous | 28 | 11 | 0.01 | 0.65% | 0.751 | 0.72% |
| Story | local_ladders | 28 | 11 | 0.01 | 0.79% | 0.627 | 0.73% |
| Story | chicago_rain | 28 | 11 | 1.0 | 1.24% | 0.101 | 0.63% |
| Story | chicago_rain_hypothetical_heat | 28 | 11 | 1.0 | 1.24% | 0.108 | 0.64% |
| Tippecanoe | local_continuous | 28 | 11 | 0.1 | 1.30% | 0.679 | 0.86% |
| Tippecanoe | local_ladders | 28 | 11 | 1.0 | 1.68% | 0.468 | 0.86% |
| Tippecanoe | chicago_rain | 28 | 11 | 1.0 | 2.08% | 0.173 | 1.04% |
| Tippecanoe | chicago_rain_hypothetical_heat | 28 | 11 | 1.0 | 2.06% | 0.184 | 1.07% |

All positions are nonnegative, no free intercept/cash; their conservative total face bound does not exceed the proposed contract's maximum payment. This constrained, restricted family is not a proof of the best achievable portfolio. Prices are inferred from earlier historical payouts, not quotes; fractional positions, fees, financing and fills are not verified. June-July rain structures and summer heat listings are counterfactual. Local synthetic ladders are not exchange products. Chicago also changes geography and data source. Do not attribute the score difference to geography alone.

| County | Earlier MDW Tmax elements from 3SW | Final MDW Tmax elements from 3SW |
| --- | --- | --- |
| Sangamon | 57.14% | 0.00% |
| Story | 57.14% | 0.00% |
| Tippecanoe | 57.14% | 0.00% |

### Exact spanning facts

| Quantity | Value | Source |
| --- | --- | --- |
| coefficient | 0.10700902149239477 | maya_spanning_bound.json; analytic formula |
| rectangular_cross_difference | 0.10700902149239477 | maya_spanning_bound.json; analytic formula |
| additive_global_worst_case_error_lower_bound_fraction | 0.026752255373098693 | maya_spanning_bound.json; analytic formula |
| same_tmax_35c_daily_heat_if_tmin_15c | 1.4413178175178163 | maya_spanning_bound.json; analytic formula |
| same_tmax_35c_daily_heat_if_tmin_25c | 2.123487819316327 | maya_spanning_bound.json; analytic formula |

For any separate additive payoff f(D)+g(H), the four endpoint payments have zero rectangular cross-difference. Our min rule has a nonzero difference equal to its coefficient. If all four errors were smaller than coefficient/4, their signed sum could not equal that difference. Thus an exact static additive replication is impossible over the whole severity domain. Realized sample error can be much smaller; this does not assume equally likely states. Equal Tmax with different Tmin also gives different duration-based heat readings, another information gap relative to daily-high-only markets.

### Frozen policy evidence retained from doc 27

| Family | Cohort | HE | Net squared-error reduction |
| --- | --- | --- | --- |
| weakest_link | all | 0.248 | 0.154 |
| weakest_link | without_2012 | 0.047 | -0.058 |

Settlement specifications and all historical replay receipts are in `maya_contract_specs.json` and `maya_settlement_replays.json`. No money or collateral is actually held. Exact replica positions, scores and predictions are retained in `maya_replica_*` files. Source hashes are in `maya_diagnostic_provenance.json`.
<!-- AUTO: maya diagnosis end -->
