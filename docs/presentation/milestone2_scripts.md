# One-minute scripts: slides 7-9 (Milestone II)

Revised 2026-11-16 to follow the deck order: slide 6 ends on Milestone I's three limits (cost, rainfall mismatch, limited supply). About 150 spoken words each.

Sources: slide 7 from docs 07, 28 (Table A) and 27; slide 8 from doc 28 (convex section, two-month third-inch hedge, farm grid, 7 PRF sites); slide 9 from docs 18, 20, 21, 22.

## Slide 7: "Finer strikes and closer stations close most of the gap"

Chart: `docs/figures/slide7_strikes_and_stations.png` (for the dark slide).

On the last slide, the airport got rain and the farm didn't. That's the core problem: Kalshi pays on the airport's rain, but the farmer loses money on their own. So in Milestone Two we asked how much of that gap better contracts could close.

Each bar is a grade out of 100 for how closely the contracts' payouts move with PRF's, tested on years they never saw.

Today's contracts score 36. Part of that is the contracts themselves. Kalshi only sells whole inches, so in a dry month there's often nothing useful to buy. Adding third-inch thresholds, plus a contract on two months of rain combined, the way PRF measures it, raises the grade to 57.

The rest is distance. The same contracts for a farm right next to the gauge score 83. Today only about 7 percent of PRF land is even within 50 miles of a Kalshi station, so more stations near farmland would matter most.

So far we've only tried to copy PRF. Next: payouts PRF doesn't offer at all.

## Slide 8: "Farmers could choose the shape of their cover"

Chart: `docs/figures/slide8_equal_premium.png` (for the cream slide).

PRF gives every rancher the same deal: payouts start at a small shortfall and grow in a straight line. But some ranchers can ride out a mild dry year. What they fear is the disaster.

With contracts, they can choose. It's the staircase from slide three: buy more contracts at low rainfall thresholds and fewer at high ones, and the payout bends toward severe droughts.

Say a rancher spends $1,000 on cover. In a mild drought, PRF-style cover pays back about $900, and disaster-only cover pays nothing. But if the season comes in 70 percent dry, PRF-style pays $3,700, disaster-only pays $6,500, and all-or-nothing pays $14,700. Skipping the mild years buys much more protection when it counts.

The catch is in the legend. The sharper the shape, the harder it is to track with one airport's rain, from 57 percent down to 31, because severe droughts are more local.

So how would a farmer actually buy cover like this? That's what our app does.

## Slide 9: app demo video (narrate over the video)

Our app puts this into practice with what we call the PRF Companion. The farmer keeps PRF and uses Kalshi for the months PRF leaves open. Winter rain comes from big storm fronts, so the airport gauge tracks the farm well in exactly those months. We recommend it for 9 of our 11 farms.

Here it is for our Dallas hay farmer. They click their location and enter the PRF policy they already have.

This strip shows the twelve months. Grey months are covered by PRF. Green months are where Kalshi contracts track the farm's rain well enough to recommend, each with its grade.

Below is a backtest from 1951 to 2025: what PRF paid, what the farmer wanted in the open months, and what the contracts paid.

This is the order ticket, with real Kalshi contracts and live prices. The depth check warns that today's market is thin and suggests a smaller order.

And far from any station, the app says it's a poor match.
