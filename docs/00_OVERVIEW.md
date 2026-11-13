# Project Overview: Milestone 1 (Research Foundation), Milestone 2 (Contract Design & Platform), and the PRF Companion

**Project:** Agricultural Risk Management & Weather Derivative Replicating Platform (ECE473, Maya / Evan / Jack)
> **Current direction (2026-11-05): the PRF Companion.** Replacing PRF with Kalshi does not work (Milestone 1, docs 08-09: costlier than the subsidized policy, loose fit, thin books). Complementing it does: Kalshi hedges for the months PRF leaves open track the rancher's rain index with HE 0.61 on held-out years (doc 21). The rest of the project expands on the companion; the roadmap is in [DEMO.md](DEMO.md#roadmap-expanding-on-the-showcase-milestone-iii-and-beyond). Since 2026-11-08 the work extends the companion with an **insurance derivative layer**: exotic payoff shapes (convex, step-up, two-tailed, the farm's own loss curve) built from the same binary contracts, with the replicating portfolio in closed form ([analysis/23_exotic_payouts.md](analysis/23_exotic_payouts.md)), and since 2026-11-09 with the **utility-optimal payout**, an equal-premium re-test, the designer in the app and a prompt-driven advisor ([analysis/24_contract_design.md](analysis/24_contract_design.md)). For a short handoff (status, deadlines, how to work here) read [../AGENTS.md](../AGENTS.md).

**Timeline:**
- 2026-10-29: Milestone 1 done (all 9 proposal cells plus two extra research questions, docs 01-10).
- 2026-11-02: Milestone 2 prep (docs 11-14: fact-check, post-rewards liquidity, rain-to-loss model, row crops). The team agreed to stop trying to *replace* PRF with Kalshi; docs 01-14 are background for that decision.
- 2026-11-05: Milestone 2 built as planned in the submitted Milestone I (docs 15-20) plus the PRF Companion showcase (docs 21-22). Summary and write-up: [MILESTONE_2.md](MILESTONE_2.md); see [Milestone 2 results](#milestone-2-results-2026-11-05).
- 2026-11-08: Exotic payoffs (doc 23): nine payoff shapes replicated from the ladder, their error waterfall, executable prices on the 2026-11-02 book, and a product designer (`platform.exotic_quote`, `POST /api/exotic`). See [Exotic payoffs](#exotic-payoffs-2026-11-08).
- 2026-11-09: Contract design (doc 24): the shapes re-compared at equal premium (the convex depth advantage disappears), a holdout term sheet, the expected-utility-optimal payout on the ladder (a deep-drought digital at Kalshi's load; the exponential and quadratic shapes capture 90%+ of its value, linear two thirds), the designer and a shape comparison in the app, and an advisor that designs a contract from a sentence (`advisor.py`, Claude with the project's tools when a key is set). See [Contract design](#contract-design-and-the-advisor-2026-11-09).

Every research document has a numbers table that gives a source for each number. Documents marked **VERIFIED** were re-checked line by line by an independent fact-checking pass. The others were not fact-checked because the run was trimmed to save usage, so check their key numbers before presenting.

## Where everything lives

| Proposal cell | Owner | Document | Status |
|---|---|---|---|
| W1 Farm exposures | Jack | [research/04_representative_farms.md](research/04_representative_farms.md), [farms.yaml](../data/scenarios/farms.yaml) | done, fact-checked 2026-11-01 (doc 11) |
| W1 PRF rules and payout math | Maya | [research/01_usda_prf_mechanics.md](research/01_usda_prf_mechanics.md), [prf_rules.yaml](../data/processed/prf_rules.yaml) | done, fact-checked 2026-11-01 (doc 11) (74 worked values match the calculator) |
| W1 Farmer scenarios: premiums, payouts, uncovered loss | Evan | [analysis/04b_farm_scenario_results.md](analysis/04b_farm_scenario_results.md) | done (uses per-farm forage elasticities from doc 03b) |
| W2 Weather data and the CPC-to-NCEI change | Jack | [analysis/06b_index_validation.md](analysis/06b_index_validation.md) | done |
| W2 Kalshi weather markets: cost and trading | Maya | [research/05_kalshi_weather_markets.md](research/05_kalshi_weather_markets.md), [analysis/05b_kalshi_liquidity_stats.md](analysis/05b_kalshi_liquidity_stats.md) | done, fact-checked 2026-11-01 (doc 11) |
| W2 Settlement: what proof each side uses | Evan | [research/06_settlement_and_data_sources.md](research/06_settlement_and_data_sources.md), [analysis/06c_station_vs_kalshi_settlement_check.md](analysis/06c_station_vs_kalshi_settlement_check.md) | done, fact-checked 2026-11-01 (doc 11) |
| W3 Geographic basis risk | Jack | [analysis/07_geographic_basis_risk.md](analysis/07_geographic_basis_risk.md) | done |
| W3 Replication quality across locations | Maya | [analysis/08_replication_quality.md](analysis/08_replication_quality.md) | done |
| W3 PRF payouts vs Kalshi payouts | Evan | [analysis/09_payout_comparison.md](analysis/09_payout_comparison.md) | done |
| Extra: how rainfall moves crop yields ($ per inch) | team | [research/03a_rain_yield_corn_soybean.md](research/03a_rain_yield_corn_soybean.md), [research/03b_rain_yield_forage_and_other_crops.md](research/03b_rain_yield_forage_and_other_crops.md) | corn/soy VERIFIED; forage and other crops done, fact-checked 2026-11-01 (doc 11) |
| Extra: how farmers buy weather insurance today | team | [research/02_how_farmers_buy_weather_insurance.md](research/02_how_farmers_buy_weather_insurance.md) | done, fact-checked 2026-11-01 (doc 11) |
| Literature review and prior art | team | [research/10_literature_review.md](research/10_literature_review.md), [references.bib](research/references.bib) | VERIFIED |
| M2 W4 Optimizer: lowest-error / lowest-cost portfolio | Jack | [analysis/15_hedge_optimizer.md](analysis/15_hedge_optimizer.md) | done 2026-11-05 |
| M2 W4 Decompose the hedge error | Maya | [analysis/16_error_budget.md](analysis/16_error_budget.md) | done 2026-11-05 |
| M2 W4 Exposures that fail; proposed contracts and mechanisms | Evan | [analysis/17_contract_gaps_and_proposals.md](analysis/17_contract_gaps_and_proposals.md) | done 2026-11-05 |
| M2 W5 Live-price backend and farmer screen | Jack, Maya | [analysis/18_platform.md](analysis/18_platform.md) | working prototype (`python scripts/run_app.py`) |
| M2 W5 Test the app against the USDA benchmark | Evan | [analysis/19_app_test.md](analysis/19_app_test.md) | done 2026-11-05 |
| M2 refinements from the submitted M1 update: complement PRF, CPC as-paid backtest | team | [analysis/20_complementing_prf.md](analysis/20_complementing_prf.md) | done 2026-11-05 |
| M2 showcase: PRF Companion (app tab) | team | [analysis/21_prf_companion.md](analysis/21_prf_companion.md), [DEMO.md](DEMO.md) | working prototype |
| M2 showcase follow-up: liquidity, cover design, excess rain, two-month what-if | team | [analysis/22_making_it_better.md](analysis/22_making_it_better.md) | done 2026-11-05 |
| M3 direction: exotic payoffs (insurance derivative layer on binary contracts) | team | [analysis/23_exotic_payouts.md](analysis/23_exotic_payouts.md) | done 2026-11-08 |
| M3: contract design (equal premium, holdout term sheet, utility-optimal payout), the designer tab and the advisor | team | [analysis/24_contract_design.md](analysis/24_contract_design.md) | done 2026-11-09 |

## Study sites

Seven PRF sites pair a Kalshi monthly-rain settlement station with a PRF-heavy county. Chicago is a row-crop contrast. Coordinates and IDs are in `src/agri_hedge/locations.py`; grid IDs are in `data/processed/study_grids.csv`.

| Site | Kalshi series | Station | Farm county | Land use | Station-to-farm | Kalshi history |
|---|---|---|---|---|---|---|
| DFW | KXRAINDALM | DFW airport | Parker Co., TX | hay + grazing | 46 mi | since Nov 2025 |
| SAT | KXRAINSATXM | San Antonio Intl | Atascosa Co., TX | rangeland | 45 mi | first month Nov 2026 |
| OKC | KXRAINOKCM | Will Rogers | Grady Co., OK | pasture + hay | 30 mi | first month Nov 2026 |
| SGF | KXRAINSGFM | Springfield MO | Dade Co., MO | fescue hay + pasture | 29 mi | first month Nov 2026 |
| DEN | KXRAINDENM | Denver Intl | Elbert Co., CO | shortgrass rangeland | 47 mi | since Nov 2025 |
| ABQ | KXRAINABQM | Albuquerque Intl | Torrance Co., NM | arid rangeland | 53 mi | first month Nov 2026 |
| TPA | KXRAINTPAM | Tampa Intl | Hardee Co., FL | bahiagrass pasture | 55 mi | first month Nov 2026 |
| ORD (contrast) | KXRAINCHIM | O'Hare (Midway before Sep 2026) | Kane Co., IL | corn/soy | 26 mi | since Jun 2025 |

## Headline findings

### 1. How farmers buy weather insurance today (doc 02)
- Farmers buy federal crop insurance from 12 private insurance companies through licensed agents. USDA's Risk Management Agency (RMA) writes and prices the policies, and taxpayers paid 62.9% of 2025 crop insurance premiums.
- Pasture, Rangeland, Forage (PRF) is the largest product under USDA's Rainfall Index plan (Annual Forage and Apiculture also use it, $1.7B of 2025 liability between them). It insures grazing and hay land, not row crops, so it is our benchmark. In 2025 it covered 298 million acres and $6.55 billion of liability.
- PRF is a very good deal for ranchers. Over 2015-2025 they got back $2.11 in payouts for every $1 they paid, because the subsidy is 51-59% of premium. Payouts beat premiums in 43 of 44 states.
- A free USDA drought program, the Livestock Forage Disaster Program, pays on the US Drought Monitor and stacks with PRF. It paid $1.78 billion in FY2023 (inflation-adjusted, base year not stated by CRS).
- Row-crop farmers mostly buy yield or revenue policies that pay on actual losses, not on rainfall.

### 2. How PRF pays (docs 01, 04b)
- Payout for each chosen two-month interval = max(0, (trigger − index) / trigger) × policy protection. The trigger is the coverage level times 100, and the index is the grid's rainfall as a percent of normal.
- Policy protection = acres × county base value × coverage level × productivity factor × percent of value allocated to the interval. Payouts do not depend on the rancher's actual loss.
- Ranchers must pick at least two non-overlapping intervals, at least 10% each, with a cap of 50-70% per interval by state. Jan-Feb is capped at 25% from 2027.
- Our calculator reproduces the USDA handbook example and every published payment factor checked. All 11 representative farms come out ahead long-run, at loss ratios of 0.70-0.86 on the full premium.

### 3. Weather data (docs 06, 06b)
- PRF paid on NOAA's Climate Prediction Center (CPC) gridded rainfall through crop year 2026. From crop year 2027 it pays on NOAA NCEI's nClimGrid data averaged into the same 0.25-degree grids.
- USDA's online PRF tool now shows a recomputed NCEI history. It is not what ranchers were actually paid. It differs from the paid indexes by 12.6 index points on average for 2021-2026.
- Our CPC rebuild reproduces the paid final indexes almost exactly (mean error 0.002 points over 854 values). The team has both regimes for backtests.

### 4. Kalshi weather markets (docs 05, 05b, 06c)
- Kalshi is a CFTC-regulated exchange. It lists monthly rainfall ladders for about 35 cities, as "more than X inches" binary contracts at whole inches, usually 1 to 7. Each settles on one NWS airport station's daily climate report.
- The fee is round-up(0.07 × contracts × price × (1 − price)), charged to takers only. For example, 100 contracts at 20 cents cost $20 plus a $1.12 fee.
- Station data reproduce all 922 settled monthly-rain outcomes checked, so backtests with station data are reliable.
- Five of our seven PRF sites only got markets on 2026-10-25. Only Dallas and Denver have about a year of trading history.
- Depth is tiny. Dallas's November 2026 book held about $436 of drought payout across all strikes. Larger books at the new cities sit on liquidity rewards that ended 2026-11-01.
- Cheap longshots are overpriced. Contracts under 20 cents averaged 4.7 cents but paid out only 1.6% of the time.
- There is no strike below 1 inch. At Denver and Albuquerque the 1-inch contract is already below the median month for most of the year, so dry-month triggers are missing.

### 5. The gaps (docs 07, 08)
- **Geography:** an airport gauge tracks its own PRF grid closely (correlation 0.92-0.97). It tracks the farm grid 24-58 miles away less well (0.74-0.89), with a 17% chance PRF pays when the station signal does not. Correlation decays with an e-folding distance of about 256 miles.
- **Coverage:** only 7.4% of US PRF grids lie within 50 miles of a Kalshi rain station. The median grid is 171 miles away.
- **Replication:** the best mix of today's Kalshi contracts captures about 43% of the variance of PRF payouts (hedge effectiveness 0.43). An ideal contract on the station's own two-month index would reach 0.73.
- **Error breakdown:** effectiveness falls from 1.0 to 0.73 from geography and gauge-versus-grid, then to 0.54 because Kalshi contracts are monthly while PRF intervals are two months, then to 0.43 from whole-inch strikes. Arid sites lose most to strike binning.
- **Tails:** the Kalshi ladder rarely misses a PRF payout (1%). But it often pays in years PRF does not, and it pays only 62% of PRF's payout in deep droughts.
### 6. What farmers get paid and what it costs: PRF vs Kalshi (doc 09)
- **Payouts, 2015-2025:** across the 11 farms, PRF as actually paid totaled $1.10 million and the matching Kalshi hedges would have paid $1.20 million. Only 70% of PRF's dollars were matched in the same year.
- **Timing:** the median correlation between the two yearly payout streams is 0.40 per farm. In 39 farm-years Kalshi paid without PRF, and in 13 PRF paid without Kalshi. The largest single miss was the Hardee hay farm in 2021, $37,300 short.
- **Cost per $1 of expected payout:** PRF costs the rancher about $0.61 after subsidy, while the Kalshi hedge costs about $1.09 (range $0.89 to $1.31 across pricing assumptions). For all 11 farms together, the hedges cost $107,500 a year against $56,000 of PRF premiums, or 1.9 times more.
- **Subsidy:** before subsidy PRF costs $1.28 per $1 of expected payout, which is more than Kalshi. Matching PRF's net benefit would take a Kalshi subsidy of about $44,600 a year, 41% of the hedge cost.
- **Pricing:** drought (NO) contracts traded slightly below fair value, not above it. The longshot overpricing applies to the YES side. The bid-ask spread is the largest trading cost, and fees add only 1.6 to 4.2% of the premium.
- **Depth:** Dallas farms could fill only 10 to 17% of their hedge from today's order book, and Denver 46%. The new cities looked deeper only because of liquidity rewards; after they ended on 2026-11-01, drought depth at the five new cities fell 94% and all 11 farms together can fill 20% of their hedge at a sensible price, down from 56% (doc 12).

### 7. How rain moves crop yields (doc 03a VERIFIED, doc 03b)
- **Hay and pasture:** one extra inch of spring rain (April to June) adds about 2 to 4% to hay yield in Texas, Oklahoma, and Missouri, or about $5 to $10 per acre. Florida hay barely responds (+0.5%).
- **Dry rangeland:** dry places respond more in percentage terms. Elbert County, Colorado gains about 6 to 8% per inch of April-July rain, and Torrance County, New Mexico about 7 to 10%.
- **Timing:** spring rain drives forage almost everywhere. Late-summer intervals matter in New Mexico, and fall rain barely helps.
- **PRF vs actual loss:** valued at grazing cash rent, PRF pays 2 to 43 times the forage loss per index point. Valued at the cost of replacement hay, it roughly matches the loss on Plains and Southwest grazing farms.
- **Other crops:** about 0.7 of an extra inch of in-season rain is used by the crop. That makes an inch worth about 3.2 bushels of Kansas wheat (about $20 per acre) and 6.6 bushels of sorghum (about $30). Rice is fully irrigated and does not respond.
- **Corn:** one extra inch of July rain near normal adds about 3 to 7 bushels per acre, or 2 to 3.5% of yield. That is about $24 to $33 per acre at $4.70 corn.
- **Asymmetry:** dry hurts more than wet helps. In Illinois, 2 inches below normal in July costs about 17.5 to 22.6 bushels per acre depending on the model, while 2 inches above gains about 6.
- **Soybeans:** August rain matters most, at about 1 to 2 bushels per acre per inch, or roughly $13 to $23 per acre at $12 soybeans.
- **Excess rain:** too much rain also hurts. May rain lowers corn yields, and extreme wet seasons cut maize yields about as much as extreme droughts.
- **Irrigation:** irrigated acres barely respond to rain. That covers 13.6% of US corn but 52.7% of Nebraska corn.

### 8. Prior art (doc 10, VERIFIED)
- Luo studies Kalshi temperature contracts and finds basis risk rises with distance. Iturbide studies New York City daily rain and finds the contract is well calibrated, but 69% of payouts land on days with no loss.
- Neither study covers monthly rain ladders, agriculture, or a PRF benchmark. That is our gap.

## What this means for Milestone 2
- **Market gaps:** the biggest fixable gaps are contract design, not geography. Two-month or seasonal contracts would recover about 0.19 of effectiveness. Strikes below 1 inch, or 0.25-inch steps, would recover about 0.11 and matter most at arid sites.
- **Subsidy:** Kalshi cannot beat subsidized PRF on cost for the same risk. Realistic niches are coverage above what PRF allows, periods or perils PRF leaves open, row-crop rain risk (especially excess rain), and producers who cannot buy PRF.
- **Liquidity:** today's books cannot fill even one small ranch's hedge. The platform needs a liquidity plan, such as market-maker partners or pooled orders.

## Milestone 2 prep (2026-11-02)
Each item below was done by two independent agent runs and then checked by a separate reviewer, who reran the code, spot-checked the numbers, and picked the better run.

- **Fact-check (doc 11):** about 75 claims checked across docs 01-06. Corrections: doc 02's 2023 crop-book row (now $181.6B liability, 62.6% subsidy share), "only rainfall-index policy" (fixed above), the LFP units, the Kalshi designation date, and the 1-contract fee example. Doc 04 county loss ratios and the doc 05 longshot result got clarifications. Every PRF headline number reproduced (`scripts/factcheck_sob.py`). Still unverified: Luo's SSRN numbers and the California Jan-Feb exception.
- **Hay prices:** farms.yaml was already right. 130/88/113 are NASS's final 2025 prices; the 136/90/114 in Crop Values were preliminary. Doc 03b and its CSV were moved to the final prices (hay $/inch falls 1-4%). Doc 04b is unchanged.
- **Post-rewards liquidity (doc 12):** drought payout buyable at $0.95 or less at the five new cities fell from $89,391 to $5,776 (-94%). All 20 rewarded series lost depth, and 13 of 16 unrewarded series gained. Unsubsidized depth is about $400-3,000 of drought cover per city per month. This is one snapshot, 22 hours after the rewards ended.
- **Rain-to-loss model (doc 13, `loss_model.py`):** turns a farm and its rainfall into dollars of loss, with timing weights, dry/wet asymmetry, a wet plateau, an irrigated share, and corn/soy support. It also gives marginal $ per index point, which the optimizer will need. Over 2015-2025, PRF and the Kalshi hedges each pay about 7x modeled loss at rent value, but cover only about 58% of in-year loss at replacement-hay value. Median correlation with modeled loss: PRF 0.78, Kalshi 0.52; Kalshi is close to useless in Florida. In the check against NASS state hay yields (correlation 0.34-0.57) the model overstates the size of swings.
- **Row crops (doc 14):** against actual Kane County yields, Chicago July/August rain hedges remove no variance (leave-one-year-out effectiveness about -0.06). In 2012, O'Hare got near-normal July rain while Kane corn fell 37.5 bu/ac. The excess-rain side does not help either. Only 7.1% of corn and soy acres lie within 50 miles of a Kalshi rain station, and none of Iowa, Nebraska or the Dakotas within 100. Verdict: not a main Milestone 2 direction with today's contracts; defensible only as a contract-design study (area index, heat or multi-month windows, Corn Belt stations).

## Milestone 2 results (2026-11-05)
All numbers: 11 farms, NCEI PRF index, 1951-2025, hedge effectiveness (HE) out of sample (leave one year out).

- **Optimizer (doc 15):**
  - The efficient frontier includes prices, fees, capital and order-book depth.
  - The lowest-error hedges cost $104,970 a year (doc 09 priced the same hedges at $107,500).
  - The cheapest hedge with 90% of the best fit costs $81,516 with the same out-of-sample HE (0.36 vs 0.37).
  - In-sample HE overstates real HE by about 40%.
- **Error breakdown (doc 16):** HE falls from 1.00 to 0.17:
  - geography -0.35, settlement source -0.13 (together two thirds of the total loss);
  - monthly instead of two-month contracts -0.19;
  - whole-inch strikes about 0 out of sample;
  - order-book depth -0.16;
  - a budget equal to the PRF producer premium -0.01.
- **Gaps and proposals (doc 17):**
  - 3 of 36 insured windows replicate well today. Summer convective and monsoon rain fails.
  - Two-month contracts raise pooled HE from 0.34 to 0.48. Half-inch strikes do not help.
  - Binaries on the farm grid's PRF index reach 0.98, but that is PRF without the subsidy.
  - The busiest leg needs 5-28x today's sensible depth.
  - Mechanisms: earlier listing, a drought-side market maker, pooled orders.
- **Platform (doc 18):**
  - A farmer clicks a location and picks any months.
  - The app prices from live Kalshi books where listed and estimates elsewhere (flagged).
  - It returns a verdict, frontier, backtest, order ticket and PRF comparison.
- **App test (doc 19):**
  - Recommended hedges cost 1.71x PRF producer premiums (median) and copy a bit over a third of PRF's swings (median HE 0.38).
  - Median HE is 0.47 within 25 miles of a station and 0.15 beyond 100 miles.
  - On 2026-11-05 no month after the current one was listed, so no real season could be priced live.
- **Complementing PRF (doc 20):**
  - Months PRF leaves uncovered (mostly Nov-Feb) hedge best: median HE 0.52, December 0.68.
  - A top-up above PRF's 90% cap copies poorly (0.14).
  - Excess-rain cover needs two-month contracts (0.22 to 0.40).
  - Backtests on the CPC index PRF actually paid give the same picture, slightly lower.
- **Showcase, PRF Companion (doc 21):**
  - Keeps PRF and covers the months it leaves open.
  - Recommended for 9 of 11 farms.
  - Median HE 0.66 on unseen years (0.61 on the 2001-2025 holdout), against 0.38 / 0.23 for hedging PRF's own intervals.
- **Making it better (doc 22):**
  - Liquidity is now the binding limit: capped at today's near-fair depth, companion HE falls from 0.67 to 0.18; 5-10x today's depth restores it.
  - Today a rancher keeps 90% of the fit on about a fifth of the requested cover; the app shows the depth check and suggested size.
  - Payout design matters little (keep PRF-style linear at 90%). Excess-rain cover is offered where its HE is at least 0.5.

## Exotic payoffs (2026-11-08)
Doc 23. Nine payoff shapes (linear, layered escalator, quadratic, exponential, step-up tiers, capped, drought plus excess rain, the farm's doc-13 loss curve, a persistent-drought bonus), same farms and years, HE out of sample.

- **Any single-month shape is a long-only portfolio of today's NO and YES contracts** (spanning), exact up to the strike grid. The issuer of a contract settled on the station keeps no rain risk.
- **Binning is the only replication error for such products and it hits convex shapes hardest:** whole-inch strikes span 89% of the linear shape's variance, 80% of the quadratic, 63% of the exponential; half-inch strikes give 97 / 94 / 86%.
- **The data-optimal station payout is convex even for a linear farm payoff** (first drop 2.3x the next ones; 52 of 62 months), because a very dry airport month almost surely means a dry farm while a 2-3 inch month says little.
- **Farm-settled, convex shapes lose more to geography and the monthly split** (pooled HE at Kalshi strikes 0.36 linear, 0.26 quadratic, 0.19 exponential) **but a third of the contracts means a third of the depth problem:** at today's depth they beat the linear shape (0.22 layered vs 0.19 linear; layered wins 31 of 36 windows) and need less issuer capital (19% vs 30% of protection).
- **Executable now, small:** a $6,000 quadratic November contract at Dallas (pays $3,727 at 1 inch or less, $862 at 1-2 inches) is 3,727 contracts; the 2026-11-02 book fills 13%; the largest fully fillable size is $595; all-in cost 1.32 per $1 expected (linear 1.20).
- `platform.exotic_quote` / `POST /api/exotic` writes the term sheet, the replicating ticket from live or saved books, and the farmer's basis risk.

## Contract design and the advisor (2026-11-09)
Doc 24. Same farms and years; CRRA farmer with risk aversion 2, a 20% price load (Kalshi's all-in cost) and wealth of twice the month's insured value as the base case.

- **At equal premium the convex shapes' depth advantage disappears.** Scaled to the linear shape's premium they beat it at today's depth in 0 of 36 windows (31 / 25 / 22 at the same maximum payout) and need more contracts and more issuer capital per premium dollar. Doc 23's result was about limit per contract, not fit per dollar.
- **The term sheet is stable out of sample** (bin payouts move 0.02 per $1, premiums 1%); the farmer's basis risk is worse on 2001-2025 (linear 0.52 to 0.41, quadratic 0.43 to 0.25; Nov-Jan 0.65 to 0.56 and 0.56 to 0.48), the same whether the bins are fitted on the training years or on all years.
- **The utility-optimal payout is doc 23's convex ladder at a fair price and a deep-drought digital at Kalshi's load:** 5 bins paying for 28% of the month's value with no load, 1 bin for 7% at a 20% load (CE gain 1.0% of value; 21 of 132 farm-months buy nothing). The exponential shape captures 93% of the optimum's value, the quadratic 90%, PRF's linear shape 67%; the raw optimum overfits (the exponential beats it out of sample in 42 of 132 farm-months), so the product is a smooth convex shape sized at about a quarter of the month's value for a 7-8% premium.
- **In the app:** a "Design a contract" tab (nine shapes, term sheet, exact ticket, fill, basis risk, and a compare-every-shape table at equal payout and equal premium with the utility ranking) and an "Ask the advisor" tab (describe the farm in a sentence; Claude runs the project's tools when an API key is set, a rule-based parser otherwise; `?demo=exotic`, `?demo=advisor`).

## Next steps
The full roadmap (wet-side cover, two-month mock market, national coverage, loss-based target, temperature, demo-exchange orders, liquidity plan) is in [DEMO.md](DEMO.md#roadmap-expanding-on-the-showcase-milestone-iii-and-beyond). Near-term:

1. **Milestone II submission (due 2026-11-12):** the write-up is [milestone2/milestone2.tex](milestone2/milestone2.tex) / `.pdf`. Branch `milestone-2` is pushed and open as GitHub PR 3 into `main`; it already contains PRs 1 (`milestone-2-prep`) and 2 (`repo-setup`), so merging PR 3 lets those two be closed.
2. **Slides (due 2026-11-17):** the deck is linked from [DEMO.md](DEMO.md). Rehearse the live demo; keep `docs/figures/m2_companion_full.png` as an offline fallback.
3. **Second post-rewards order-book snapshot**, to confirm doc 12's one-day result and refresh doc 22's depth numbers (`scripts/pull_kalshi.py`, `scripts/compare_orderbook_snapshots.py`).
4. **Pick the first roadmap items for the final paper (due 2026-12-15).** Doc 22 points to the liquidity plan (roadmap 7) and the two-month mock market (roadmap 2) as the most direct wins.
5. **Contract design (docs 23-24):** the designer and the advisor are on the app screen. Next: run the advisor against the live API with a key and tune its prompt on real farmer phrasings, ask farmers about risk preference (the one input the utility model guesses), and pitch half-inch strikes plus a market maker for the 1-inch strike that every convex product loads.

Open loose ends from Milestone 1 (low priority):
- **Luo SSRN numbers** (doc 10) are still unverified; download the PDF in a browser.
- **Doc 04b** uses the NCEI index from the USDA tool, not what RMA actually paid. Doc 09 has the as-paid CPC payouts in the `prf_cpc_as_paid_usd` column.

## Repository map
- `docs/research/` sourced research documents, one topic each
- `docs/analysis/` results from our own code
- `docs/figures/` generated figures
- `src/agri_hedge/` Python package:
  - `prf.py`: PRF calculator
  - `prf_grid.py`, `cpc.py`: grids and indexes
  - `kalshi.py`: market data client and fee function
  - `stations.py`: station rain
  - `basis.py`: basis-risk metrics
  - `replicate.py`: hedge fitting
  - `pricing.py`: hedge pricing and order-book fills
  - `locations.py`: study sites
  - `optimizer.py`, `hedge_builder.py`, `error_budget.py`: Milestone 2 optimizer and error breakdown
  - `platform.py`, `webapp/`: Milestone 2 live-price backend and farmer screen
  - `loss_model.py`: rain-to-dollar-loss model for each farm (doc 13)
  - `exotic.py`: exotic payoff shapes, closed-form spanning by NO/YES ladders, order-book execution (doc 23)
  - `design.py`: equal-premium scaling, holdout split, the utility-optimal step payout and certainty-equivalent comparison (doc 24)
  - `advisor.py`: the prompt-driven contract designer (Claude tool loop with a rule-based fallback) and its crop table (doc 24)
  - `rowcrop.py`: corn/soy farm exposure and hedge backtest (doc 14)
- `scripts/` runnable entry points that pull data and regenerate every result
- `data/processed/` small derived datasets (committed); `data/raw/` downloads (gitignored, recreated by scripts)
- `tests/` pytest checks (379 passing)

## How to reproduce

```bash
.venv/bin/python -m pip install -e .
.venv/bin/python -m pytest                        # 379 tests, ~10 s
# Milestone 1
.venv/bin/python scripts/run_basis_risk.py        # doc 07
.venv/bin/python scripts/run_replication.py       # doc 08
.venv/bin/python scripts/run_scenarios.py         # doc 04b
.venv/bin/python scripts/run_payout_comparison.py # doc 09
```
Milestone 2 and companion scripts (docs 15-22) and their run times are listed in [MILESTONE_2.md](MILESTONE_2.md#reproduce).
