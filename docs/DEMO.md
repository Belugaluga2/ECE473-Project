# AgriHedge demo guide (Milestone II showcase)

**One-line pitch:** keep your USDA rainfall insurance (PRF), and use Kalshi weather contracts to cover the months PRF leaves open. The app tells you, month by month, where that works at your location, and builds the order.

**Slides (11/17):** [Rain Insurance on Prediction Markets](https://claude.ai/artifact/1542eCG6kPUgw4itzm9N4P), a 16-slide deck with speaker notes. It tells the story from the problem through Milestone I's "no", the diagnosis, the turn to complementing PRF, the PRF Companion and its holdout test, to the liquidity limit and the road to the final paper.

## Start it

```bash
.venv/bin/python scripts/run_app.py      # http://localhost:8473
```

- `http://localhost:8473/?demo` runs the PRF Companion for the Dallas hay farm on load.
- `?demo=custom` runs the stand-alone custom hedge.
- `?demo=exotic` designs a quadratic November contract for the Dallas hay farm (term sheet, exact ticket, basis risk); the "Compare every shape" button prices all nine at equal payout and equal premium.
- `?demo=advisor` sends "I grow hay on 150 acres at 32.7771, -97.8059 near Weatherford, TX. Cover November; I mostly worry about a deep drought." to the advisor. With `ANTHROPIC_API_KEY` set (or a key pasted into the tab) Claude answers; without one the rule-based designer does.
- With no internet the app still works on estimated prices. The map tiles need internet.

## Five-minute walkthrough

1. **The problem (30 s).** PRF pays ranchers when rain on their 0.25-degree grid is below normal, but only in the two-month intervals they choose, at most 90% coverage, with a 51-59% federal subsidy. Milestone I showed that copying PRF with Kalshi costs about 1.8x and tracks poorly (docs 08-09).
2. **What we found (1 min).** Docs 16-17: the hedge loses most of its fit to geography (the airport is 30-55 miles away) and to monthly-vs-two-month contracts. Doc 20: the months PRF leaves open are where the airport gauge tracks the farm well. Cool-season frontal rain is spread evenly, and those months score HE 0.5-0.7 out of sample.
3. **Live demo (2 min).** Open `?demo`. Point out:
   - the 12-month strip: grey = covered by PRF; green = a month where a Kalshi hedge tracks well enough to recommend;
   - the recommendation sentence and the hedge-effectiveness number, scored on years the hedge never saw;
   - the depth check: today's books keep a fit of 0.18 against 0.67 with unlimited depth, and the app suggests the order size that keeps 90% of the fit (doc 22);
   - the backtest: PRF payouts next to the gap cover wanted and what the Kalshi companion paid, 1951-2025;
   - the order ticket: real Kalshi tickers, contracts, limit prices, fees, and whether each price is live or estimated;
   - the excess-rain table: Jun-Jul tracks well enough to offer (0.58), while Apr-May and Aug-Sep need two-month contracts;
   - the two-month what-if for this rancher's own intervals, which leads to our proposal.
   Then click somewhere far from a station (e.g. 120 miles out) and run it again to show the app saying "poor match".
4. **What would make it better (1 min).** Doc 17:
   - two-month contracts (no new data needed) take PRF-interval HE from 0.34 to 0.48 and excess-rain HE from 0.22 to 0.40;
   - ladders listed 6-12 months ahead;
   - a drought-side market maker (depth is 5-28x too thin);
   - grid-index contracts (0.98, but that is unsubsidized PRF).
5. **Close (30 s).** Every number on screen comes from the same code as the analysis docs (doc 19 checks the app reproduces them to the cent), with 379 automated tests.

## Roadmap: expanding on the showcase (Milestone III and beyond)

Ordered by how directly each builds on what exists. Each item names the module it extends.

| # | Expansion | Builds on | Why |
|---|---|---|---|
| 1 | **Wet-side cover in the app** (excess rain, YES contracts) for hay-harvest and planting windows | `platform.companion` (already scores it), `optimizer` | Second gap PRF leaves. Usable today where HE is at least 0.5, better with two-month contracts. |
| 2 | **Two-month contract mock market**: list synthetic two-month ladders priced at fair value and let the companion use them | `error_budget.window_total_ladder_cols`, `platform.build_tranches` | Turns doc 17's proposal into a working demo for the exchange pitch. |
| 3 | **National coverage**: pull NCEI grids for every Kalshi station (38) instead of 8 | `scripts/pull_cpc.py`, `build_indices.py`, `hedge_builder` | Today's app serves 2,036 grids near 8 stations. |
| 4 | **Loss-based target**: hedge the rancher's modeled forage loss (doc 13), not the PRF formula | `loss_model.py` → `quote(target=...)` | What a farmer actually cares about. The optimizer takes any target. |
| 5 | **Temperature risk** (the Milestone I "if time permits" item): Kalshi daily/monthly temperature markets for heat stress on hay and cattle | `kalshi.py` client, `optimizer` | Weather risk PRF does not cover at all. |
| 6 | **Order placement in Kalshi's demo environment** | `platform.order_ticket`, Kalshi authenticated API | Closes the loop from quote to trade. |
| 7 | **Liquidity plan**: simulate a market maker or pooled orders across many ranches | `optimizer` tranches, doc 12 depth data | Depth is the binding constraint after geography. |
| 8 | **Exotic payoffs in the app** (done 2026-11-09, docs 23-24): the "Design a contract" tab with nine shapes, the term sheet, the exact ticket, the basis-risk verdict and a compare-every-shape table | `exotic.py`, `design.py`, `POST /api/exotic`, `POST /api/exotic_compare` | The issuer's hedge is exact; the exponential and quadratic shapes capture 90%+ of a risk-averse farmer's best contract at Kalshi's load. |
| 9 | **Advisor** (done 2026-11-09, doc 24): describe the farm in a sentence, get a designed contract; Claude with the project's tools when a key is set, a rule-based parser otherwise | `advisor.py`, `POST /api/advise` | Next: test against the live API with a key, tune the prompt on real farmer phrasings, verify the crop table. |

## Key numbers to quote

| Claim | Number | Doc |
|---|---|---|
| Farms where the PRF Companion is recommended | 9 of 11 | 21 |
| Companion median HE on unseen years (2001-2025 holdout), vs hedging PRF's own intervals | 0.66 (0.61) vs 0.38 (0.23) | 21 |
| Companion HE at today's order-book depth; depth that restores it | 0.67 to 0.18; 5-10x | 22 |
| Months PRF leaves open, median HE of a Kalshi hedge | 0.52 (Dec 0.68) | 20 |
| Hedging the PRF intervals themselves, median HE | 0.34-0.37 | 15-17 |
| Kalshi cost vs subsidized PRF per $1 of expected payout | about $1.10 vs $0.61 | 09, 15 |
| Waterfall: geography / settlement / monthly / binning / depth | -0.35 / -0.13 / -0.19 / ~0 / -0.16 | 16 |
| Two-month contracts: PRF intervals; excess rain | 0.34 to 0.48; 0.22 to 0.40 | 17, 20 |
| Exotic shapes: pooled HE at Kalshi strikes, linear / quadratic / exponential; at today's depth | 0.36 / 0.26 / 0.19; 0.19 / 0.20 / 0.18 | 23 |
| Whole-inch strikes span the linear / quadratic / exponential shape on station rain | 89% / 80% / 63% (half-inch: 97 / 94 / 86%) | 23 |
| Dallas Nov 2026 $6,000 quadratic contract: fair premium; book fills; largest fillable | $1,205; 13%; $595 | 23 |
| Convex shapes beating linear at today's depth: same max payout; same premium (layered / quadratic / exponential) | 31 / 25 / 22 of 36; 0 / 0 / 0 of 36 | 24 |
| Utility-optimal payout at a fair price; at Kalshi's 20% load (bins paying, premium as % of the month's value) | 5 bins, 28%; 1 bin, 7% | 24 |
| Share of the optimal contract's value captured: exponential / quadratic / linear | 93% / 90% / 67% | 24 |
| Exchange-settled basis risk, Nov-Jan, in sample vs 2001-2025 holdout: linear; quadratic | 0.65 vs 0.56; 0.56 vs 0.48 | 24 |
| US PRF grids within 50 miles of a Kalshi station | 7.4% | 07 |
