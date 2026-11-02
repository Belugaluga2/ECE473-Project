# Kalshi order-book depth after the liquidity rewards ended

**Proposal cell:** follow-up to W2 Kalshi weather markets (05b) and W3 PRF vs Kalshi payouts (09); overview "Next steps" item 3  |  **Status:** DRAFT (two snapshots, computed; not independently fact-checked)  |  **Last updated:** 2026-11-02

On 2026-10-29 the five PRF sites whose Kalshi rain markets were listed on 2026-10-25 (San Antonio,
Oklahoma City, Springfield MO, Albuquerque, Tampa) had much deeper order books than Dallas, Denver
or Chicago. Every November market at those cities was paying Kalshi "new_event" liquidity rewards
of $170 until 2026-11-01 03:59 UTC. Docs 05b and 09 suspected that the depth would not outlast the
rewards. This document tests that with a second snapshot of every open monthly-rain order book,
taken at 2026-11-02 01:34 UTC, about 21.6 hours after the rewards ended.

**Answer: the depth did not survive.** At the five new sites, the drought cover a farmer can buy at
$0.95 or less fell 77-97%, from $7,431-$39,859 to $416-$1,680 per city for the whole November
ladder. Dallas and Chicago did not lose depth, and Denver lost a little. Across all 36 monthly-rain
series, every series whose rewards ended on 2026-11-01 lost depth. Most series that had no rewards
at either date gained depth over the same three days.

## Key findings

- **New-site depth fell to the level of the established sites.** Drought payout buyable at
  $0.95 or less, all 7 November strikes: SAT $18,810 -> $859, OKC $12,836 -> $416,
  SGF $39,859 -> $1,237, ABQ $10,456 -> $1,585, TPA $7,431 -> $1,680. The five sites together fell
  from $89,391 to $5,776 (-94%). Counting offers at any price, including 98-99 cent NO that is not
  insurance, they fell from $820,490 to $12,850 (-98%).
- **The wet side (buy YES) collapsed even more,** by 97-98% at every new site (for example ABQ
  $148,786 -> $3,890).
- **The established books did not shrink.** DFW $436 -> $663 and ORD $428 -> $497 grew. DEN
  $4,017 -> $2,878 fell 28% but is still the deepest study-site book, all at the 1-inch strike.
  The DFW median bid-ask spread also tightened, from 17 to 9 cents.
- **The pattern is market-wide and lines up with the rewards.** Every one of the 20 series whose
  last reward ended on 2026-11-01 lost depth (median after/before ratio 0.05, range 0.01-0.23).
  Of the 16 series with no reward at either snapshot, 13 gained depth (median ratio 1.44). No new
  reward program had been listed by 2026-11-02. The 140 programs for 2026-10-26 to 2026-11-01
  were marked `paid_out` in the re-pull.
- **Hedge capacity for the 11 representative farms fell from 56% to 20%.** This is the share of
  each farm's yearly hedge contracts that a November-sized book could fill at a sensible price
  (at most 10 cents above fair value), weighted by contracts. At the new sites it fell from 17-100%
  to 8-33%. At DFW it rose from 10-17% to 17-30%; at DEN it fell from 46% to 33%.
- **What it implies.** Without subsidies, Kalshi's monthly-rain books hold about $400 to $3,000
  of reasonably priced drought cover per city per month at our sites. The median over the other 28
  cities is about $1,500. A single representative farm needs 2,300-13,600 contracts in its busiest
  month. A Kalshi PRF replica therefore cannot be bought today at any of the seven PRF sites unless
  someone pays for liquidity. The rewards show that paid liquidity does appear: about $1,190 per
  series over six days went with $5,800-$38,600 more resting drought cover at the new study sites.
  We did not measure whether that cover could actually be traded.

## Numbers table

"Computed" = produced by the scripts named in Reproduce, from the dated files in `data/processed/`.
"Before" = snapshot 2026-10-29T09:30:56Z (rewards running); "after" = 2026-11-02T01:34:56Z.

| Quantity | Value | Units | Region / period | Source | Verification |
|---|---|---|---|---|---|
| Snapshot times | before 2026-10-29T09:30:56Z (353 open markets); after 2026-11-02T01:34:56Z (269 open markets) | UTC; count | all open monthly-rain markets | `GET /markets/{ticker}/orderbook` (api.elections.kalshi.com/trade-api/v2); `kalshi_rain_orderbook_summary_20261029.csv`, `kalshi_rain_orderbook_summary_20261102.csv` | CONFIRMED |
| Reward end time, new_event programs on Nov 2026 markets at the 20 new series | 2026-11-01T03:59:59.999999Z | timestamp | 20 series x 7 markets | `GET /incentive_programs`, `end_date`; `kalshi_rain_incentive_programs.csv` | CONFIRMED |
| Reward per market / per series | 170 / 1,190 (7 markets) | $ | 2026-10-26 04:02 to 2026-11-01 03:59 UTC | same (`period_reward` / 10,000; centi-cent unit from the OpenAPI description, see 05b) | CONFIRMED (unit per API docs) |
| Reward programs listed after the end time | 0 (762 programs, same IDs as on 2026-10-29) | count | monthly-rain markets, re-pulled 2026-11-02 | same | CONFIRMED |
| Programs whose `paid_out` flipped false -> true between pulls | 140 (761 of 762 now true) | count | same | same | CONFIRMED (computed) |
| Hours between reward end and second snapshot | 21.6 | hours | - | 03:59:59 Nov 1 to 01:34:56 Nov 2 UTC | DERIVED |
| Drought payout <= $0.95, Nov 2026, all strikes, before -> after: SAT / OKC / SGF / ABQ / TPA | 18,810 -> 859; 12,836 -> 416; 39,859 -> 1,237; 10,456 -> 1,585; 7,431 -> 1,680 | $ payout | Nov 2026 ladders | `kalshi_rain_hedge_capacity_nov2026_20261029.csv`, `..._20261102.csv`; `kalshi_post_rewards_city_compare.csv` | CONFIRMED (computed) |
| Same, DFW / DEN / ORD | 436 -> 663; 4,017 -> 2,878; 428 -> 497 | $ payout | same | same | CONFIRMED (computed) |
| Same, five new sites summed | 89,391 -> 5,776 (-94%) | $ payout | same | same | CONFIRMED (computed) |
| Drought payout at any price (incl. 98-99c NO), five new sites summed | 820,490 -> 12,850 (-98%) | $ payout | same | same, `no_payout_all` | CONFIRMED (computed) |
| Wet payout (buy YES) <= $0.95, new sites, after/before | SAT 0.023; OKC 0.021; SGF 0.027; ABQ 0.026; TPA 0.019 | ratio | same | same | CONFIRMED (computed) |
| Series in the rewarded group / with lower useful depth after | 20 / 20 | count | 36 series in both snapshots | `scripts/compare_orderbook_snapshots.py` | CONFIRMED (computed) |
| Rewarded group: median useful drought payout before -> after; median ratio (range) | 25,998 -> 1,429; 0.05 (0.01-0.23) | $; ratio | same | same | CONFIRMED (computed) |
| Control group (no reward at either snapshot): series / with lower depth after | 16 / 3 (DEN, LAX, PVD) | count | same | same | CONFIRMED (computed) |
| Control group: median useful drought payout before -> after; median ratio | 572 -> 1,171; 1.44 | $; ratio | same | same | CONFIRMED (computed) |
| Median useful drought payout, 28 non-study cities | 9,504 -> 1,466 | $ payout | same | `pull_kalshi.py --stats` output | CONFIRMED (computed) |
| Farm hedge share fillable at a sensible price (<= fair + 10c), contract-weighted, 11 farms | 56% -> 20% | share of contracts | busiest-month books applied to every month | `payout_comparison_summary_books20261029.csv`, `payout_comparison_summary.csv`; `kalshi_post_rewards_farm_compare.csv` | CONFIRMED (computed) |
| Same, fillable at any price up to 99c | 84% -> 46% | share of contracts | same | same | CONFIRMED (computed) |
| Contracts needed in a farm's busiest month | 2,332 (DFW_graze) to 13,550 (DEN_graze) | contracts | 11 farms | doc 09 Table 9 | CONFIRMED (computed) |
| 2026-10-29 capacity results reproduced from the dated before-file | max difference 1e-10 (per-city capacity), 3e-4 (farm summary, 4-dp rounding) | $ / share | - | `pull_kalshi.py --stats --orderbook ..._20261029.csv`; `run_payout_comparison.py --orderbook ... --summary-out ...` vs the committed 2026-10-29 outputs | CONFIRMED (computed) |
| Station rain on 2026-11-01 (already part of the November total at the second snapshot) | not yet published (ACIS returned "M" for all 8 stations on 2026-11-02) | in | KDFW, KSAT, KOKC, KSGF, KDEN, KABQ, KTPA, KORD | ACIS StnData, https://data.rcc-acis.org | UNVERIFIED |

## Method

1. **Two snapshots, nothing overwritten.** `scripts/pull_kalshi.py --orderbooks-only` re-lists the
   live markets of all 37 monthly-rain series (without rewriting the market, candle, trade or
   outcome files), re-pulls the incentive-program list, and saves every open order book. Each
   snapshot is written to `kalshi_rain_orderbook_summary_<YYYYMMDD>.csv`.
   `kalshi_rain_orderbook_summary.csv` is a copy of the latest one. The 2026-10-29 file was saved
   under its dated name before the re-pull.
2. **Per-city capacity.** `pull_kalshi.py --stats [--orderbook <file>]` turns one snapshot into
   `kalshi_rain_hedge_capacity_nov2026_<YYYYMMDD>.csv`. This is the 05b Table 4 calculation: buying
   NO lifts resting YES bids at price 1 - bid. "Useful" levels are NO priced at $0.95 or less, and
   premium includes the taker fee.
3. **Per-farm capacity.** `run_payout_comparison.py` walks each farm's doc-09 hedge legs through
   the November book of its site, "at all" (any price up to 99 cents) and "at a sensible price"
   (the strike with the closest chance of paying, at most 10 cents above fair value). The default
   run uses the latest books. `--orderbook <dated file> --summary-out <csv>` reruns only the
   summary on an earlier snapshot.
4. **Treated and control series.** A series counts as "rewarded" if its latest reward program on
   monthly-rain markets ended on 2026-11-01. That is all 20 series listed on 2026-10-25, including
   the five new PRF sites. The other 16 series had their last rewards end on 2026-10-04 or earlier,
   so no reward was running at either snapshot. If the rewards held the depth up, rewarded series
   should lose depth and control series should not.
5. `scripts/compare_orderbook_snapshots.py --before 20261029 --after 20261102` joins the two
   snapshots and writes the tables below.

## Results

### Per-site books, November 2026 ladders

Dollars of payout (= contracts) a buyer could take from resting orders. "Useful" = NO at $0.95 or
less. Spread = median best bid-ask over the strikes, in cents.

| Site | Series | Group | Drought payout, useful: before -> after | After / before | Max at one strike: before -> after | Drought payout, any price: before -> after | Wet payout (YES), useful: before -> after | Spread (c): before -> after | Two-sided strikes: before -> after |
|---|---|---|---|---|---|---|---|---|---|
| SAT | KXRAINSATXM | rewarded | 18,810 -> 859 | 0.05 | 5,968 -> 551 | 126,251 -> 2,127 | 61,340 -> 1,384 | 12 -> 13 | 7 -> 7 |
| OKC | KXRAINOKCM | rewarded | 12,836 -> 416 | 0.03 | 6,175 -> 267 | 139,890 -> 3,890 | 52,034 -> 1,111 | 14 -> 12 | 7 -> 7 |
| SGF | KXRAINSGFM | rewarded | 39,859 -> 1,237 | 0.03 | 12,710 -> 454 | 100,388 -> 1,955 | 34,844 -> 932 | 9 -> 14 | 7 -> 7 |
| ABQ | KXRAINABQM | rewarded | 10,456 -> 1,585 | 0.15 | 6,533 -> 799 | 327,005 -> 2,707 | 148,786 -> 3,890 | 1 -> 8 | 7 -> 4 |
| TPA | KXRAINTPAM | rewarded | 7,431 -> 1,680 | 0.23 | 7,287 -> 716 | 126,957 -> 2,171 | 58,276 -> 1,132 | 14 -> 8 | 7 -> 5 |
| DFW | KXRAINDALM | control | 436 -> 663 | 1.52 | 120 -> 285 | 626 -> 883 | 807 -> 1,572 | 17 -> 9 | 7 -> 7 |
| DEN | KXRAINDENM | control | 4,017 -> 2,878 | 0.72 | 4,017 -> 2,878 | 6,487 -> 5,633 | 1,707 -> 2,549 | 9 -> 4 | 4 -> 4 |
| ORD | KXRAINCHIM | control | 428 -> 497 | 1.16 | 135 -> 221 | 2,891 -> 2,984 | 752 -> 1,350 | 17 -> 8 | 6 -> 6 |

Figures: [before](../figures/b2_orderbook_depth_study_sites_20261029.png),
[after](../figures/b2_orderbook_depth_study_sites_20261102.png) (05b Figure 3).

How to read this:
- On 2026-10-29 the new-site books looked like a market maker quoting thousands of contracts on
  both sides of every strike, often at 98-99 cents (ABQ's 1-cent median spread). On 2026-11-02 that
  quoting was gone. What remains is a few hundred contracts per strike, like Dallas.
- Spreads did not widen much at the new sites. The tight quotes survived but the size behind
  them did not, so a farmer can still see a fair price but cannot fill much at it.

### Rewarded vs control series (all 36 monthly-rain series in both snapshots)

| Group | Series | Useful drought payout, median: before -> after | Max single strike, median: before -> after | Useful wet payout, median: before -> after | Median after/before | Series with less depth after |
|---|---|---|---|---|---|---|
| rewarded (rewards ended 2026-11-01) | 20 | 25,998 -> 1,429 | 9,735 -> 563 | 51,896 -> 1,036 | 0.05 | 20 of 20 |
| control (no reward at either date) | 16 | 572 -> 1,171 | 193 -> 513 | 769 -> 1,446 | 1.44 | 3 of 16 |

After the rewards ended, the two groups look alike: rewarded series have a median of about $1,400
and control series about $1,200. Before, rewarded series were about 45 times deeper.

### Hedge capacity per farm (doc 09 method)

Share of each farm's yearly hedge contracts that a November-sized book at its site could fill.
"Sensible" = at most 10 cents above fair value. "Payout" = share of expected payout. Busiest
month = contracts the farm's hedge needs in its largest month, and how many the book fills at a
sensible price.

| Farm | Site | At all: before -> after | Sensible: before -> after | Sensible, payout-weighted: before -> after | Busiest month: needed | Filled at a sensible price: before -> after |
|---|---|---|---|---|---|---|
| DFW_hay | DFW | 15% -> 25% | 10% -> 17% | 11% -> 16% | 3,640 | 326 -> 566 |
| DFW_graze | DFW | 26% -> 41% | 17% -> 30% | 21% -> 29% | 2,332 | 326 -> 566 |
| SAT_graze | SAT | 100% -> 44% | 100% -> 9% | 100% -> 13% | 3,777 | 3,777 -> 253 |
| OKC_hay | OKC | 100% -> 65% | 17% -> 8% | 16% -> 9% | 6,000 | 675 -> 359 |
| OKC_graze | OKC | 100% -> 74% | 26% -> 13% | 27% -> 16% | 4,525 | 675 -> 359 |
| SGF_hay | SGF | 100% -> 49% | 89% -> 20% | 75% -> 25% | 5,015 | 4,890 -> 673 |
| SGF_graze | SGF | 100% -> 68% | 89% -> 33% | 77% -> 40% | 2,918 | 2,866 -> 600 |
| DEN_graze | DEN | 59% -> 55% | 46% -> 33% | 52% -> 38% | 13,550 | 3,217 -> 2,078 |
| ABQ_graze | ABQ | 100% -> 37% | 72% -> 14% | 72% -> 14% | 8,256 | 3,845 -> 765 |
| TPA_graze | TPA | 100% -> 34% | 69% -> 25% | 51% -> 26% | 7,357 | 4,091 -> 1,285 |
| TPA_hay | TPA | 100% -> 26% | 74% -> 17% | 54% -> 18% | 7,558 | 4,202 -> 1,285 |
| **All 11** (contract-weighted) | | 84% -> 46% | 56% -> 20% | 51% -> 22% | 64,927 (sum) | 28,890 -> 8,789 |

How to read this:
- "At all" is still 26-74% at the new sites only because each leg can lift NO offers up to 99
  cents. A 99-cent NO bought for a leg worth 25 cents is prepaid money, not insurance. The
  "sensible" column is the one that matters.
- The two DFW farms read off the same book, and so do the OKC, SGF and TPA pairs, so the farms at
  one site cannot both fill what the table shows.

## What this implies

1. **Plan on unsubsidized depth.** Without rewards, a monthly-rain book at our sites holds about
   $400-$3,000 of drought cover at reasonable prices across all strikes, with at most $220-$2,900
   at one strike. That is 8-33% of one representative farm's hedge, not the 17-100% the
   reward-era books suggested. Doc 09's capacity tables now use the post-rewards books.
2. **The listing rewards are a measured liquidity cost.** About $1,190 per series over six days
   ($170 x 7 markets) went with resting drought cover at the five new PRF sites that was
   $5,751 (TPA) to $38,622 (SGF) larger than after the rewards ended. That is roughly $0.03-$0.21 of
   reward per dollar of extra resting cover over those six days. This is an inference, not a measured cost of trading:
   resting orders may be pulled when a large order arrives, and we did not see who placed them.
   It does give Milestone 2 an order of magnitude for a market-maker or liquidity-partner budget.
   For comparison, doc 09 estimates $44,600 a year of subsidy to give the 11 farms PRF's net gain.
3. **Snapshot depth before pricing a hedge.** Liquidity changes within days. Any quoted capacity
   should carry its snapshot time, and `pull_kalshi.py --orderbooks-only` now keeps every snapshot
   under a dated name for that purpose.
4. **The PRF-replica conclusion of doc 09 is stronger, not weaker.** Cost was already about 1.9
   times PRF's producer premium. Now even the best-supplied site cannot fill a third of one farm's
   hedge at a sensible price.

## Caveats and open questions

- **One snapshot after the rewards.** It was taken 21.6 hours after the end. Market makers may
  come back later in November, or Kalshi may list new rewards. More snapshots are needed to say
  how deep the books settle.
- **One day of November is already in the price.** At the second snapshot the November 1 rain is
  partly known, which shifts fair values; ACIS had not yet published it. This can move prices,
  for example TPA's best NO ask is now 0.29 below climatology (doc 09), but it cannot explain a
  95% drop in resting size across 20 cities while the 16 control cities grew.
- **Cause.** The timing and the control group point to the rewards. We did not see order-level
  data, so we cannot prove that the same participants placed and then withdrew the depth.
- **Static depth.** Doc 09's capacity applies November's book to every month and does not test
  request-for-quote or block trades.

## Reproduce

```bash
# from the repo root; AGRI_HEDGE_RAW_DIR may point anywhere outside the repo
python scripts/pull_kalshi.py --orderbooks-only        # new dated snapshot + incentive list (network, ~430 requests)
python scripts/pull_kalshi.py --stats                  # capacity for the latest snapshot
python scripts/pull_kalshi.py --stats --orderbook data/processed/kalshi_rain_orderbook_summary_20261029.csv
python scripts/run_payout_comparison.py                # doc 09 on the latest books
python scripts/run_payout_comparison.py --orderbook data/processed/kalshi_rain_orderbook_summary_20261029.csv \
    --summary-out data/processed/payout_comparison_summary_books20261029.csv
python scripts/compare_orderbook_snapshots.py --before 20261029 --after 20261102
```

`--stats` also rewrites `kalshi_rain_liquidity_by_series.csv`, `kalshi_rain_calibration.csv` and
three b2 figures. Their content does not depend on the order books, and the committed versions were
kept.

## Sources

- Kalshi Trade API v2, public market-data endpoints `GET /markets`, `GET /markets/{ticker}/orderbook`,
  `GET /incentive_programs`, https://api.elections.kalshi.com/trade-api/v2 , retrieved 2026-10-29
  and 2026-11-02. Raw JSON for the 2026-11-02 pull: `orderbooks_20261102T013456Z.json` and
  `incentive_programs_rain_monthly.json` under `$AGRI_HEDGE_RAW_DIR/kalshi/`. These are not
  committed, as with all raw data.
- Kalshi API documentation, "Get Incentives" (OpenAPI),
  https://docs.kalshi.com/api-reference/incentive-programs/get-incentives (centi-cent unit of
  `period_reward`; see 05b).
- ACIS StnData, https://data.rcc-acis.org , queried 2026-11-02 for 2026-10-30 to 2026-11-01.
- Project docs: [05b](05b_kalshi_liquidity_stats.md) (book method, Tables 4 and 4b),
  [09](09_payout_comparison.md) (farm hedges and capacity method).
