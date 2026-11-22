# 33: How much additional market depth would these small add-ons require?

**Exploratory capacity audit, 2026-11-22.** These are the same frozen 20%-extra-budget
portfolios as doc 32. Contract counts and prices are not tuned to find a feasible book.

## What can be calculated

For each station/calendar-month/strike, required depth divided by saved useful depth
gives the multiplier that would fill that leg at unchanged prices. A complete ticket
needs the largest ratio. A leg with no offer inside the modeled 10-cent price cutoff
cannot be fixed by multiplying its zero quantity; a new useful quote is needed.

The reference is the **November 2, 2026** snapshot, applied as a capacity proxy to each
calendar month. This cannot establish executable spring/summer or historical trades.
The script records the source date, counts, strike, cutoff and missing-offer status for
every leg. It does not walk live prices, estimate a market maker's profit, or imply that
a subsidy of a specific dollar amount would produce this depth.

## Results

<!-- BEGIN AUTO: liquidity -->

| Farm | Extra cover | Required contracts | Fraction at saved proxy depth | Zero-capacity legs | Max multiplier where offers exist |
|---|---|---:|---:|---:|---:|
| ABQ_graze | tail_deep50 | 3255 | 60% | 1 | 1.5 |
| ABQ_graze | tail_digital30 | 3899 | 40% | 1 | 96.8 |
| ABQ_graze | tail_exp5 | 3089 | 65% | 1 | 1.5 |
| ABQ_graze | winter_companion | 2570 | 91% | 0 | 1.2 |
| DFW_hay | tail_deep50 | 1915 | 52% | 2 | 2.8 |
| DFW_hay | tail_digital30 | 1883 | 49% | 1 | 2.8 |
| DFW_hay | tail_exp5 | 1866 | 48% | 3 | 2.5 |
| DFW_hay | winter_companion | 1666 | 94% | 0 | 1.3 |
| SAT_graze | tail_deep50 | 2508 | 4% | 7 | 254.0 |
| SAT_graze | tail_digital30 | 2674 | 4% | 3 | 488.0 |
| SAT_graze | tail_exp5 | 2346 | 4% | 9 | 135.0 |
| SAT_graze | winter_companion | 1235 | 54% | 2 | 5.2 |

<!-- END AUTO: liquidity -->

These are **small add-ons**, not the original full-size replacement portfolios. The
Dallas winter ticket needs about 1.3x saved useful depth and Albuquerque about 1.2x,
under the repeated-November proxy. San Antonio's winter ticket has two legs with no
useful offers, and some catastrophe tickets need orders where none were available.
There is no single credible "5x fixes everything" number for all products.

The summary CSV also records missing contract counts, modeled buyer cost before fees
and carry, and `gross_unnetted_other_side_stake = sum(n*(1-ask))`. That last column is a
stand-alone paired-contract collateral benchmark: a NO buyer pays `ask`, while the
opposite side contributes `1-ask` toward a $1 settlement. It is not a required grant,
a market maker's operating capital, or an aggregate margin estimate. Same-event netting,
existing positions, price changes, holding time and willingness to quote would matter.

## What more depth cannot solve

1. A month or strike not listed at the required purchase date needs a listing, not more
   units at an unrelated currently listed event.
2. More quantities do not remove airport-to-farm basis risk or a poor loss model.
3. Taking orders can move prices; multiplying depth at unchanged quotes is a scenario.
4. Multiple customers sharing a station/event compete for the same book. Per-farm
   capacity is not proof that all farms can fill simultaneously.

Kalshi controls market/strike listings and operates liquidity programs; counterparties
supply orders. Government support could conceivably subsidize premiums, research or
market-making through a properly authorized arrangement, but this project establishes
no such program, funding entitlement or approved mechanism. USDA cannot create Kalshi
contracts by adding dollars to this calculation.

Official channels:
- [Request additional strikes](https://help.kalshi.com/en/articles/13823834-request-additional-strikes)
- [Suggest a new market](https://help.kalshi.com/en/articles/13823833-suggesting-a-new-market)
- [Liquidity provider program](https://kalshi.com/regulatory/liquidity-provider-program)

## Sources, numbers and reproduction

Run `scripts/run_prf_addons.py`. The source tickets are
`maya_matched_premium_tickets.csv`; the source books are
`kalshi_rain_orderbook_summary.csv` (November 2). Per-leg calculations are in
`maya_liquidity_requirements_legs.csv`; the table is generated from
`maya_liquidity_requirements_summary.csv`. No new market or capital is manufactured.
