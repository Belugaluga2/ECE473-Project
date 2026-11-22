# 34 Direct optimization of drought cover under budgets and depth limits

**Exploratory protocol declared November 22, 2026, before this experiment's outputs.**
The evaluation years have already been inspected elsewhere in this project. This is
a controlled extension, not fresh independent confirmation. All earlier studies remain.

## Question and fixed protocol

Does choosing contract counts directly to reduce bad-year shortfalls improve on
fitting a desired payout curve and scaling it to a premium budget?

The machine-readable specification is
[`maya_direct_protocol.json`](../../data/scenarios/maya_direct_protocol.json).
Its choices are fixed before generating results:

- Dallas hay, San Antonio pasture and Albuquerque pasture cases, unchanged from doc 30.
- Fit 1951-1985; select using 1986-2000; refit the selected method on 1951-2000;
  replay 2001-2025. All candidates' replay results are retained. Evaluation outcomes
  do not select the trigger, exponent, method, cost scenario or loss valuation.
- Primary loss is the existing growth-timed, replacement-feed-valued model. Freeze
  the resulting portfolios and evaluate all six existing timing/valuation variants.
  This does not validate actual farm losses, the inherited elasticity or curvature.
- Compare market-only replacement, 80% PRF/20% market reallocation, and 100% PRF
  with an additional 20% budget. Always allow unspent cash. PRF-alone is the common
  reference; the add-on comparison gives that reference the same extra resources.
- Use long NO positions at the saved stations' observed whole-inch strikes 1-7,
  repeated over all twelve calendar months. No proposed finer or two-month strikes.
  This is a full-season market-availability what-if; it is not a claim all those
  contracts can be bought together today. Both methods use exactly this same menu.
- Compare unlimited depth with the saved November 2 book repeated across months,
  with the inherited 10-cent price cutoff. Direct optimization includes these caps
  while choosing quantities; target fitting scales then caps the quantities.
- Candidate curves are `M*clip((T-I)/T,0,1)^p`, with T in {70,90,100}, p in {1,2,3},
  plus the inherited exponential k=5 with shortfall measured from index 100.
  I is the primary model's growth-weighted seasonal farm-grid rainfall index.
  The nine power combinations plus exponential, direct optimization and cash are
  the entire declared family. M is determined by the budget, not selected on replay.
- Primary objective is empirical CVaR at 80%: the average of the worst 20% of positive
  `loss + premium - payout` outcomes. This differs from the separate metric averaging
  shortfalls in the five worst underlying-loss years; report both.
- Select on validation CVaR. Within one cent, prefer lower mean positive net outlay,
  then lower cost, then stable candidate order. Also report the direct method and
  best validation-selected shape even when the overall selector chooses cash.

## Pricing, rounding and controls

The fitting-stage purchase probability is the empirical station frequency in the
fitting years only, plus the inherited 2.25-cent half-spread, bounded to 1-99 cents.
Refitting updates those probabilities using pre-2001 years only. Use a 7% taker-fee
formula with per-leg cent rounding and 4.05% annual carry over 31 days, as in doc 30.
These are modeled prices, not historical quotes or current conditional forecasts.

The direct method solves a continuous linear programme for nonnegative contract
counts, then floors counts to whole contracts. Its budget reserves one cent per
possible leg for fee rounding. A second solve minimizes cost within one cent of
the best training CVaR. Exact rounded fees and budget/depth feasibility are checked
after rounding. Fractional optimization is a relaxation, not a proof of the optimal
integer portfolio.

Wider 6.55-cent spreads and 180-day carry are separate stresses. Freeze the selected
method and contract proportions; reduce quantities only if necessary to preserve the
original budget. No stress scenario selects a new winning method. The instrument menu,
seasonal index and inherited loss calibration are contemporary counterfactual inputs,
so the split is not a fully historical information-set backtest.

Compare target fitting and direct optimization on the same expanded monthly menu.
Differences from doc 30 can also reflect this menu and the annual seasonal target;
do not attribute all changes relative to that earlier study to the optimizer alone.

## Evaluation and uncertainty

Report premiums, cash, quantities, CVaR, worst-five-loss-year shortfalls, annual mean
net outlay, HE against the stated loss proxy and severe-interval payout misses.
Use the declared paired two-year-block bootstrap (2,000 draws, seed 473) for selected
methods and the direct method, and remove the single worst underlying-loss year.
These sensitivities do not capture all model, selection or climate uncertainty and
cannot add unobserved catastrophes. Report sensitivity disagreements explicitly.

## Results

Pending the first run. Generated tables will be inserted here by the experiment script.

<!-- BEGIN AUTO: direct tail -->
<!-- END AUTO: direct tail -->

## Sources and reproducibility

Fixed choices are sourced to the protocol JSON, inherited prices to doc 30, and loss
assumptions to docs 13/32. Numerical results will be sourced to the experiment's
committed yearly, ticket, validation and summary CSVs. No real orders, external
messages, installations or app changes are part of this experiment.
