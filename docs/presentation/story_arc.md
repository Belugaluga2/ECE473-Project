# Presentation story arc: Milestone I to Milestone II to future work

Written 2026-11-15 for the team. One storyline: **prediction markets can't replace federal rain insurance, but they can fill the gaps it leaves.** Every beat below supports that line. Numbers come from the project docs named in brackets.

## 0. Hook: one rancher (1 slide)

A hay farmer in Parker County, Texas, west of Dallas: 150 acres of bermudagrass. They buy USDA's rainfall insurance (PRF) for April through September, paying $3,683 a year after subsidy [doc 04, 09].
- **PRF is a good deal.** Over 2015-2025 ranchers got back $2.11 for every $1 they paid, because taxpayers cover 51-59% of the premium [doc 02].
- **But it is rigid.** The rancher picks two-month windows in advance, at most 90% coverage, with a payout that is linear below the trigger. Six months of their year are uncovered, and from 2027 January-February cover is capped at 25% [doc 01].
- **Meanwhile, Kalshi lists rain contracts for Dallas.** Anyone can buy any month, any amount, settled about two weeks after the month ends, on a CFTC-regulated exchange [doc 05].

**The question:** can prediction markets give farmers flexible rain insurance?

## 1. Why it matters (1 slide)

- **Scale.** PRF covered 298 million acres and $6.55 billion of liability in 2025 [doc 02].
- **Cost to taxpayers.** Taxpayers paid 62.9% of 2025 crop insurance premiums. A market-based option tests whether that subsidy is the only way to make this cover affordable [doc 02].
- **Real gaps.** PRF is USDA's only rainfall-index policy, and it covers only grazing and hay land. Row-crop farmers have no rain-index product. Ranchers' winter months are often uncovered [docs 02, 20].

## 2. Milestone I: can Kalshi copy PRF? No. (2-3 slides)

- **We could trust the data.** Station records reproduce 922 of 922 settled Kalshi rain markets, so the backtests are sound [doc 06c].
- **The fit is partial.** The best mix of today's contracts copies 43% of PRF's year-to-year payouts [doc 08].
- **It costs 1.9 times what the rancher pays for PRF.** That is about $1.09 per $1 of expected payout against $0.61. The whole gap is the subsidy: before subsidy PRF costs $1.28 [doc 09].
- **The books are tiny.** Dallas held $436 of drought cover for a month [doc 05b].

Transition: "So the answer to 'replace PRF' is no. Milestone II asked why, and what is left."

## 3. Milestone II: why it fails, and the pivot (2 slides, the first of your Milestone II info slides)

- **Where the fit goes.** About two thirds of the loss is paying on the wrong rain. Geography costs -0.35, because the airport gauge is 24-58 miles from the farm, and settlement data -0.13. Monthly contracts against PRF's two-month windows cost -0.19 [doc 16].
- **The pivot: complement, don't replace.** Winter rain is spread evenly, so the gauge tracks the farm in exactly the months PRF leaves open. Those months hedge at 0.52, with December at 0.68 [doc 20].
- **The PRF Companion.** It keeps PRF and covers the open months. It is recommended for 9 of 11 farms and scores 0.66 on unseen years, against 0.38 for copying PRF [doc 21]. For the Parker County farmer it recommends January, March, October, November and December, at a fit of 0.68 for $6,740 a year.

## 4. Demo (1 slide: the video)

Show the Companion on the Parker County farm. Then show the app saying "poor match" 120 miles from a station, to make the geography point visible.

## 5. Today: what better contracts could do (1 slide, your second Milestone II info slide)

- **Finer strikes.** Third-inch strikes triple the usable strikes. Dry sites like Albuquerque and Denver go from 9 and 5 unusable months to none [doc 27].
- **A two-month contract.** On a total at third-inch strikes, a station hedge goes from 0.36 to 0.57, as good as any contract on that station can be [doc 28].
- **Shapes PRF can't sell.** One example is cover that ignores a 10% shortfall and pays a lot at 70%. Today's ladder copies 20% of that payout, and the improved contracts copy 45% [doc 28].
- **Honest limit.** PRF still wins on price, and on fit in the months it covers. Liquidity is the binding constraint: at today's depth the Companion's fit falls from 0.67 to 0.18 [doc 22].

## 6. Future work (1 slide)

- **Ask Kalshi for four changes.** Sub-inch strikes at dry stations, a two-month-total series, ladders listed 6-12 months ahead, and a drought-side market maker. The first is a parameter change: the contract rules already allow 0.01-inch strikes [docs 17, 27].
- **Engineer liquidity.** Simulate a market maker and pooled orders across ranches. Five to ten times today's depth restores the fit [doc 22].
- **Hedge losses, not PRF.** Size cover to the farm's modeled loss [doc 13].
- **Go national.** Extend the app from 8 stations to all 37 Kalshi rain stations.
- **Final paper due 2026-12-15.**

## 7. Close (1 line)

"Prediction markets won't replace subsidized insurance. But for the months, sizes and payout shapes that insurance won't sell, they can work today, and with a few contract changes they could work well."
