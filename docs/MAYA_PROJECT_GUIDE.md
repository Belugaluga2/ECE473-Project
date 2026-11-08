# The project, in everyday language

We are studying **how to turn weather-event contracts into useful insurance-like protection**,
and where their limitations require a different contract. We are not claiming guaranteed profit.

## The vocabulary

| Term | Meaning here |
| --- | --- |
| PRF | Pasture, Rangeland, Forage: subsidized insurance for pasture/hay exposures. Its payments depend on a rainfall index, rather than an inspection of your farm's actual loss. |
| Event contract | A contract that pays when a specified event occurs, such as rainfall below a threshold. Kalshi is the exchange studied in this project. |
| Premium | What you pay for insurance/protection. |
| Payout | What the contract pays after the outcome is known. |
| Hedge | A position intended to offset an existing risk. A farmer still bears risk; protection need not earn a positive average return to reduce uncertainty. |
| Arbitrage | In the strict sense, a set of trades that locks in a gain without exposure to the relevant outcome risk. Different weather indexes and farm losses do not create this automatically. None is established here. |
| Parametric insurance | Payment follows a specified measurement/formula, instead of adjustment of an individual loss claim. |
| Basis risk | The protection and your actual loss fail to match: the airport is dry when your field is wet, or your crop fails for a cause the contract does not cover. |
| Exotic | A contract with a more involved payment rule, such as one depending jointly on drought and heat. It does not imply cryptocurrency, novelty or superior performance. |
| Interaction | The effect of one input depends on another. A heat-times-drought payment grows only when both severities are positive. |
| Model | A simplified rule fitted to data. Here it maps weather to a proposed payout that might offset crop shortfalls. It is not primarily a forecast of next summer's weather. |
| Hyperparameter | A modeling choice such as a threshold, time window or amount of regularization. Coefficients fitted within that choice are parameters. |
| Overfitting | A rule captures quirks in the data used to develop it and performs poorly on other years or places. |
| Holdout | Data reserved from fitting/selection to assess whether a rule transfers. Once used to choose further changes, it no longer serves as a fresh final test. |
| Regularization | Penalizing large/complex fitted coefficients to discourage unstable fits. It reduces one source of overfitting without eliminating it. |
| HE | Hedge effectiveness: reduction in the variance of remaining losses. It is not profit or the proportion of losses paid back. |
| Replication | Combining underlying contracts to reproduce a desired payment. Reproducing a payment well does not establish that the payment protects a real farm well. |
| Liquidity | How much can actually be bought or sold at a reasonable price. A useful formula alone supplies no willing counterparty. |
| Oracle | The mechanism that supplies outside data, such as a weather observation, to a smart contract. A mock oracle demonstrates software but not trustworthy real-world data delivery. |

## What happened, and why

**Initial rainfall attempt:** copy government PRF protection using Kalshi rainfall contracts.
The research found the subsidized government policy was hard to beat on price. Station/grid
differences, available contract shapes and thin order books also limited replication.

**PRF Companion:** keep PRF and buy additional protection for periods its chosen allocation
leaves uncovered. Imagine your policy emphasizes growing-season intervals; the companion
looks for useful protection in other periods. Its app and rainfall-index results are the most
developed existing work. Matching an uncovered rain index is not proof of farm-income benefit:
those months must matter to the farmer, and orders must be available in sufficient size.

**Dairy heat experiment:** hot conditions can harm milk production, so test heat-linked payments.
An earlier temperature-based loss simulation looked encouraging. Testing observed regional milk
shortfalls did not establish useful protection. This weakens that particular design, not every
possible dairy policy. Regional output, management, weather measurement, other causes of losses,
listing horizons and existing insurance all complicate it. See docs 24-25.

**Corn with combined weather:** use observed corn yields to test separate drought/heat payments
and special joint payments. We added a wet-spring benchmark and expanded to other counties.
Some joint rules help in major-disaster years, but reliable advantage over simpler cover remains
unproven. The county outcomes and weather points are still proxies for an individual farm.
See docs 26-27 for every comparison and its uncertainty.

## What the code is doing now

Earlier crop yields -> estimate expected production -> measure observed shortfall.

Earlier weather -> fix local triggers/scales -> fit shared payout coefficients on development
counties -> choose among a small set using earlier validation years -> freeze the policy ->
evaluate later years and reserved counties, including premium costs and uncertainty.

The aim is accurate, repeatable protection at a stated cost. More complicated math and more
payments are not automatically better. We keep negative results because they identify which
parts of the original instrument-design idea work and which need different measurements or
new markets. None of these experiments proves arbitrage or superiority to government insurance.

The strongest project combines the existing research/tool with honest validation, a clear
replication gap and a modest demonstration. Blockchain could demonstrate escrow and settlement;
it cannot resolve a mismatch between the weather measurement and a farmer's actual loss.

Sources: [RMA's PRF explanation](https://www.rma.usda.gov/about-crop-insurance/frequently-asked-questions/pasture-rangeland-forage),
project [overview](00_OVERVIEW.md), [dairy validation](analysis/25_maya_dairy_validation.md),
[first compound experiment](analysis/26_compound_heat_drought.md),
and [multi-county validation](analysis/27_compound_county_panel.md).
