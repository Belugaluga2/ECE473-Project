# Brief for the slides agent: Milestone II section (3 slides)

Written 2026-11-15 for the Claude agent building the Google Slides deck. The Milestone II section is three slides: two information slides and one slide that holds a demo video of the app (no content needed beyond a title and caption). Everything below is sourced from the project's analysis docs; doc numbers are given so the presenter can answer questions. Numbers marked "not fact-checked" come from docs that have not had an independent review pass.

## Project in one line

ECE473 (Princeton) team project, Maya / Evan / Jack: can a farmer use Kalshi weather event contracts as rainfall insurance, measured against USDA's Pasture, Rangeland, Forage (PRF) rainfall-index policy? Milestone I answered "copying PRF does not work well". Milestone II diagnosed why, built an optimizer and a working app, pivoted to complementing PRF (the "PRF Companion"), and tested finer strikes and exotic, personalized payouts.

Vocabulary the slides may use (define once, briefly): **HE** (hedge effectiveness) = share of the year-to-year variance of the insured payout that the hedge removes; 1 is perfect, 0 is useless. "Out of sample" = scored on years the hedge was not fitted to. All HE figures below are out of sample unless stated. **Load** = cost per $1 of expected payout; PRF costs the farmer about $0.61 because of the federal subsidy, Kalshi about $1.10.

## Slide 1 (information): "Milestone II: why a Kalshi copy of PRF falls short, and what works instead"

Suggested layout: a left column of 4-5 short bullets, a right-hand visual of the error waterfall. Keep numbers to one decimal.

Bullets (pick 4-5):
- **Where the fit goes.** Starting from a perfect hedge (HE 1.00), the loss splits as: geography between the airport gauge and the farm 24-58 miles away -0.35; gauge-vs-gridded settlement data -0.13; monthly contracts instead of PRF's two-month intervals -0.19; whole-inch strikes about 0; thin order books -0.16; a budget equal to the PRF premium -0.01. What is left is HE 0.17. Two thirds of the loss is paying on the wrong rain, which no payoff design fixes. (doc 16)
- **An optimizer that knows prices and depth.** It returns the whole price-versus-fit frontier with Kalshi fees, spreads and order-book depth. In-sample fit overstates real fit by about 40% (median 0.64 in sample, 0.37 out of sample); the cheapest hedge with 90% of the best fit costs 22% less and performs the same out of sample. (doc 15)
- **The pivot: cover the months PRF leaves open.** The farms' PRF elections leave 60 farm-months uncovered, mostly November to February, when frontal rain is spread evenly and the airport gauge tracks the farm. Those months hedge with median HE 0.52 (December 0.68), against 0.34-0.38 for PRF's own intervals. (doc 20)
- **The PRF Companion.** Keep PRF; the app scores each open month at the rancher's location and builds one order. Recommended for 9 of 11 farms; median HE 0.66 on unseen years (0.61 on a strict 2001-2025 holdout) versus 0.38 (0.23) for hedging PRF's intervals. Priced fairly, about $1.10 per $1 of expected payout, with no subsidy. (doc 21)
- **Liquidity is now the binding limit.** Capped at today's order-book depth, the companion's fit falls from 0.67 to 0.18; five to ten times today's depth restores it. Unsubsidized books hold about $400-3,000 of sensible drought cover per city per month. (docs 12, 22)
- **What we would ask Kalshi for.** Two-month-total contracts (PRF-interval HE 0.34 to 0.48, excess-rain 0.22 to 0.40), ladders listed 6-12 months ahead, and a drought-side market maker. Grid-index contracts would reach 0.98 but are PRF without the subsidy. (doc 17)

Visual: the error waterfall, `docs/figures/m2_error_waterfall.png` on the milestone-2 branch (full path: `C:\Users\evanc\OneDrive - Princeton University\Desktop\ECE473 Project\.claude\worktrees\multi-peril\docs\figures\m2_error_waterfall.png`). Alternative: `m2_companion_farms.png` in the same folder (companion HE by farm and month).

Speaker note: "Milestone I said copying PRF costs 1.9 times the farmer's PRF premium and tracks 43% of its swings. Milestone II shows the loss is mostly geography and the two-month mismatch, builds the tool, and finds the niche where the gauge actually tracks the farm: the winter months PRF does not cover."

## Slide 2 (information): "Finer strikes and personalized payouts: what a ladder can do that PRF cannot"

Suggested layout: a headline table or bar chart of out-of-sample HE by contract family on the left, 3-4 bullets on the right. This slide covers the newest work (docs 27 and 28, dated 2026-11-15, not fact-checked). All numbers assume enough volume: every leg filled at fair value plus half a 4.5-cent spread plus Kalshi's fee.

Bullets (pick 3-4):
- **Third-inch strikes (0.33, 0.67, 1.00, ...) are priced for all 37 Kalshi rain stations and 12 months from station history.** They triple the number of usable strikes (5.3 to 15.7 per station-month). The gain is in dry months, which are PRF's problem months: where more than half of months end at 1 inch or less, today's ladder copies 25% of a monthly put and a third-inch ladder 67%. Albuquerque goes from 9 unusable months to none, Denver from 5 to none. Kalshi's rules already allow 0.01-inch strikes, and New York traded half-inch strikes in 2024. Caveat: a single strike's climatological price is only known to about plus or minus 10 cents from 35 years of data, so quotes should come from a smoothed curve. (doc 27)
- **Against PRF, one exotic matters: the two-month total.** Out-of-sample HE at the farm grid: today's monthly whole-inch ladder 0.36; third-inch monthly 0.45; two-month total at whole-inch strikes 0.52; two-month total at third-inch strikes 0.57, equal to an ideal contract on the station's own index (0.58). It halves false alarms (48% to 22%) and costs less. Joint "both months dry" digitals reach 0.51. Worst-month lookbacks (0.26), dry-spell barriers (0.17) and one-day-rain flood digitals (0.10) are different perils, not index replicas. (doc 28)
- **Personalized shapes.** A ladder lets the farmer choose the payoff curve; PRF cannot (lowest coverage 70%, linear payout). For a tail-heavy buyer who ignores a 10% shortfall and wants a lot at 70% (an exponential payout), today's ladder removes 20% of the variance, third-inch strikes 32%, the two-month total at third-inch strikes 45%. The 70%-shortfall strike sits below 1 inch in most months at every site, so today's ladder has no strike where that payout lives. The costs: deep shortfalls transfer worse across 24-58 miles, and the hedge lives on cheap, thinly priced legs, so loads rise from 1.11 to 1.15-1.30. (doc 28, convex section)
- **Against what a farm actually loses, a single season-total contract is the best station-settled option.** Against the farms' forage-loss proxy, today's ladder scores 0.30, PRF-shaped interval totals 0.45, and one contract on the season's total rain 0.57 (7 of 11 farms at or above 0.5), with no interval elections. It does not beat PRF on fit: PRF settles on the farm's own grid, and resized to the loss it scores 0.66 (as sold, PRF pays several times the modeled loss, so it adds variance rather than removing it). The season total's advantages are simplicity and choice of months. Row crops need a two-sided collar: drought plus excess, 0.58 of an Illinois corn loss curve on Chicago rain (no geography in that number). (doc 28)
- **Cost does not separate the families.** Every drought-side family loads at 1.07-1.14 per $1 of expected payout, the same as today's ladder. Only wet-side tails rest on thin history.

Visual options (main repo, `docs/figures/`; full path prefix `C:\Users\evanc\OneDrive - Princeton University\Desktop\ECE473 Project\docs\figures\`):
- `x2_drought_families_he.png`: horizontal bars of HE by contract family, station grid and farm grid (best single image for this slide).
- `x2_he_by_site_family.png`: heatmap of HE by site and family.
- `x1_third_inch_fair_price_heatmaps.png`: fair prices at third-inch strikes for the eight study stations (dense; use only if the slide is about pricing).
- `x1_informative_strikes_by_station.png`: usable strikes today vs third-inch, by station.
- `x2_farm_families_he.png`: farm-level families vs PRF payout and vs forage loss.

Suggested compact table for the slide (out-of-sample HE at the farm grid, 7 PRF sites):

| Contract | PRF-style linear | Tail-heavy (exponential) |
|---|---|---|
| Today's whole-inch monthly ladder | 0.36 | 0.20 |
| Third-inch monthly strikes | 0.45 | 0.32 |
| Two-month total, third-inch strikes | 0.57 | 0.45 |
| Ideal contract on the station's index | 0.58 | 0.55 |

Speaker note: "Finer strikes are a rule change Kalshi could make tomorrow; the two-month total is a new series on the same settlement data. Together they get a farm within 24-58 miles of a gauge to the best any station contract can do. What a ladder adds over PRF is the choice of payoff shape and of months, not a lower price."

## Slide 3 (app demo video): "The app: PRF Companion and custom cover"

No content needed beyond a title and a one-line caption. Suggested caption: "A rancher enters a location and their PRF election; the app scores the months PRF leaves open at that spot, prices a hedge from live Kalshi books, shows a 1951-2025 backtest and the order ticket, and warns when today's depth is too thin." If a fallback still image is wanted: `.claude\worktrees\multi-peril\docs\figures\m2_companion_screenshot.png`. Facts behind the app, if asked: it serves 2,036 PRF grids within about 150 miles of 8 stations, reproduces the analysis to the cent (doc 19), prices from live order books where listed and flags estimates elsewhere (doc 18), and the repo has 353 automated tests on the milestone-2 branch (238 on the branch holding docs 27-28).

## Numbers with sources (for the presenter)

| Claim | Number | Doc |
|---|---|---|
| Milestone I: Kalshi ladder copies PRF payout variance / cost vs farmer's PRF premium | HE 0.43 / 1.9x ($1.09 vs $0.61 per $1 expected) | 08, 09 |
| Error waterfall: geography / settlement / monthly / strikes / depth / budget | -0.35 / -0.13 / -0.19 / ~0 / -0.16 / -0.01, ending at 0.17 | 16 |
| Optimizer: in-sample vs out-of-sample median HE; 90% knee saving | 0.64 vs 0.37; 22% cheaper, same fit | 15 |
| Months PRF leaves open: median HE; December | 0.52; 0.68 | 20 |
| PRF Companion: farms recommended; HE unseen years (holdout) vs PRF intervals | 9 of 11; 0.66 (0.61) vs 0.38 (0.23) | 21 |
| Companion at today's depth; depth needed | 0.67 to 0.18; 5-10x | 22 |
| Unsubsidized depth per city per month | $400-3,000 of drought cover | 12 |
| Two-month contracts: PRF intervals; excess rain | 0.34 to 0.48; 0.22 to 0.40 | 17, 20 |
| US PRF grids within 50 miles of a Kalshi station | 7.4% | 07 |
| Third-inch strikes: usable strikes per station-month; dry-month put fit | 5.3 to 15.7; 25% to 67% | 27 |
| Third-inch strikes: price uncertainty from 35 years | 90% interval about 21 cents wide | 27 |
| Exotic families vs PRF, farm grid: today / third / 2-month third / ideal | 0.36 / 0.45 / 0.57 / 0.58 | 28 |
| Same for exponential (tail-heavy) payout | 0.20 / 0.32 / 0.45 / 0.55 | 28 |
| False alarms: today vs two-month total | 48% vs 22% of no-PRF years | 28 |
| Season-total contract vs forage loss; farms >= 0.5 | 0.57; 7 of 11 (today's ladder 0.30) | 28 |
| Dry spell / flood digital as index cover | 0.17 / 0.10 | 28 |
| Corn collar on Chicago rain (no geography): drought-only vs two-sided third-inch | 0.49 vs 0.58 | 28 |
| Loads, drought families | 1.07-1.14 per $1 expected (convex tail cover 1.15-1.30) | 28 |

## Style and caveats

- Say "assuming enough volume" wherever doc 28 numbers appear; the real books are thin (doc 12).
- Docs 27 and 28 are dated 2026-11-15 and not independently fact-checked; docs 15-22 are the team's Milestone II submission of 2026-11-05.
- HE against "PRF payout" measures how well Kalshi copies PRF, so PRF itself is 1 by definition there. It is not a claim that PRF is perfect insurance.
- Do not claim a Kalshi contract fits farm losses better than PRF; resized to the loss, PRF scores 0.66 against 0.57 for the best Kalshi contract.
- Do not claim Kalshi can be cheaper than PRF for the farmer; the subsidy makes PRF about half the price for the same expected payout. The advantages are months, payoff shape, speed of settlement and access.
- The existing 16-slide deck ("Rain Insurance on Prediction Markets", linked from the milestone-2 branch's DEMO.md) tells the story from the problem through Milestone I's "no" to the companion and the liquidity limit; these three slides should slot into that arc after the diagnosis.
- Plain language, no em-dashes, numbers to one decimal, one idea per bullet.
