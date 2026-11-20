# 25: Weather hedging expansion: uninsured farmers, a multi-sector market maker, and which pairings work

**Proposal cell:** post-Milestone II expansion research (bridge insurance where farm insurance is missing; a market maker pairing opposite weather hedgers). Owners: team  |  **Status:** DRAFT, second pass (six research tracks, four gap reviews, three new-lens tracks and independent logic reviews; notes in [`docs/research/expansion_notes/`](../research/expansion_notes/)). Reproduce with:
- `python scripts/run_expansion_netting.py`: netting numbers. About 2.5 minutes on the first run, which downloads NOAA ACIS daily data; about 45 s with `--offline`.
- `python scripts/run_weather_demand.py --offline`: the demand estimate, about 5 s after that.
- `python scripts/run_expansion_lenses.py`: lender-book HE, ENSO in Kalshi prices and solar, about 130 s.
- `python scripts/run_expansion_compare.py`: the head-to-head comparison, about 1 s.
- Review checks are in `scripts/experiments/expansion_review/`.

**Last updated:** 2026-11-20

**Headline: no expansion clearly wins. The ones that come closest sell the engine or change the rules, and none of them holds weather risk.**

Neither expansion idea works as originally pitched. The head-to-head comparison (section "Head-to-head comparison") scores 17 strategies on nine criteria. No pairing of opposite hedgers on the team's own or an insurer's book makes the top eight. The city snow book ranks #10, ranchers against solar #11, and the south-central rain pairing #16 of 17. The one pairing in the top half is two-sided quoting on Kalshi itself (#6), and it is untested.

The top of the ranking is a loose pack, not a winner:
- a USDA 508(h) endorsement for PRF;
- structuring and pricing software for parametric MGAs and carriers;
- a snow Companion for per-push plow contractors;
- embedded consumer weather guarantees;
- contract designs sold to Kalshi.

Their weak-link scores sit within 0.2 of each other (3.01 to 2.83). One of the top four ranks first in about 76% of draws, but all three top slots come from those four in only 19%. Drop the Dec 15 "time to proof" criterion, a course deadline rather than a business test, and 508(h) leads clearly: first in 63% of draws.

**Bias check.** The project's data and code are about PRF ranchers, so the report was checked for leaning on them. It did, in three places:
1. Rancher demand was modeled in a narrow wealth frame and every other segment in a strict cash frame.
2. New segments were judged as counterparties to ranchers rather than as businesses of their own.
3. One criterion rewards existing team code.

Corrected, the measured weather losses in the new sectors dwarf the ranchers'. Restaurants alone lose about $3.2B of profit a year to rain, against $0.2B for ranchers near Kalshi stations. Frame-matched wet-side demand is about $134M a year against ranchers' $14M.

In the data-neutral ranking, the on-exchange market maker, the original "farmers buy no-rain, venues buy yes-rain" idea in the form that needs no insurance license, rises from #6 to #2. The rancher Companion falls to #10 (section "Bias check").

The ideal combination follows from why the pack wins: **fix the menu, sell the engine, seed the book.**

1. **Fix the menu.** Take the same research package to two buyers:
   - Kalshi: a Nov-Feb strip listed before PRF's December 1 close, and a PRF-grid-settled index that removes station basis.
   - RMA: a 508(h) drought-weighted interval rule.
2. **Sell the engine** as structuring software to the firms that already hold weather books.
3. **Seed the book** with single-side Companions (ranchers through a financier; snow contractors) and an on-exchange maker quoting their other side. Paper-trade it on this winter's books first.

The percentages above measure how robust the ranking is to the team's own 1-5 scores. They are not odds of commercial success.

The second pass overturned three first-pass claims:

1. **Lenders are not the buyer of the hedge.** In the drought episodes checked, ag lenders showed no charge-off spike. Bank ag-production charge-offs were 0.24% in 2011 and 0.25% in 2012, against 0.77% in 2010, a post-crisis peak ([FRED CORLAGACBS](https://fred.stlouisfed.org/series/CORLAGACBS)). Capital Farm Credit had 0.0% net charge-offs in every year 2019-2023 and record income of $286M in 2022 ([CFC 2023](https://www.capitalfarmcredit.com/wp-content/uploads/2025/05/cfc-2023-annual-report.pdf)).

   Part of the reason is that borrowers' crop insurance is assigned to the lender. Part is that 2011-12 brought high crop prices and land values. What lenders do lose is loan volume and some later repayment slippage, not principal. Their regulator calls speculative or risk-increasing derivatives "unsafe and unsound" ([FCA EM-61.3](https://ww3.fca.gov/readingrm/exammanual/New%20Exam%20Manual/61.3.pdf)). The lender's role is to distribute and finance the premium, where the pay-at-harvest evidence points ([lens_lender_reality.md](../research/expansion_notes/lens_lender_reality.md)).

   Pooling still helps whoever does hold a book. Forty farms around one station hedge at a pooled HE of 0.65-0.77 leaving one year out (0.63-0.79 on the 2001-2025 holdout), against 0.53-0.62 for the median farm. Every farm shares the station's own error, so the gain stops at about 10 farms ([lens_quant.md](../research/expansion_notes/lens_quant.md)).
2. **Kalshi already nets opposite sides within a station-month.** All 37 monthly rain series carry Kalshi's `DIRECNET` collateral tag. Under Kalshi's opt-in directional collateral return, a position of YES at a low strike plus NO at a higher strike posts only its worst-case loss ([Kalshi Help](https://help.kalshi.com/en/articles/13823816-collateral-return); [events API](https://api.elections.kalshi.com/trade-api/v2/events?series_ticker=KXRAINDALM&limit=3)). That the tag means directional return is inferred from its name and the help page.

   The setting is fixed per event at the first order, and returned-collateral positions may not be sellable. Kalshi also pays 3.50% APY on cash and open positions ([Kalshi Help](https://help.kalshi.com/en/articles/13823847-apy-on-kalshi)). The first pass said netting "saves nothing for a trader." That is wrong for same-station, same-month pairs and still right across stations or months.

   It matters less than it sounds. At an 80:1 dry-heavy flow, most of a maker's book is unpaired and fully collateralized.
3. **Capital is abundant in reinsurance and scarce on Kalshi's rain books.** Global reinsurance capital is a record of about $800B ([Reinsurance News, Aon](https://www.reinsurancene.ws/record-800bn-reinsurance-capital-offers-insurers-growth-opportunities-heading-into-1-1-aon/)). Catastrophe-bond multiples have tightened to about 2.4x expected loss, from 3.71x in 2024 ([Artemis](https://www.artemis.bm/news/as-cat-bond-loss-multiples-tighten-am-best-urges-investors-towards-greater-selectivity/)). Rancher demand, meanwhile, is about 330 times the resting NO depth. Pairing hedgers saves capital in general; the binding problem is getting capital into the order book and buyers to it.

Five nuances also matter:
- **Texas ranchers already insure the winter.** Nov-Dec and Jan-Feb are two of the three largest Texas PRF intervals. Together they hold 27% of liability and 33% of premium in 2025, with a 1.11 loss ratio over 2018-25. The doc 21 sample farmers left Nov-Feb open; the median insured Texas dollar does not. The $12.1M central rancher demand below is biased high by an unknown amount, and executable depth caps it far lower.
- **Kalshi sells winter one month at a time.** Monthly rain markets open at the start of the month, often hours after it begins. November 2026 was the exception, listed weeks ahead. As of November 20 only NYC has a December event scheduled, opening November 27. A rancher cannot lock in Nov-Feb before the ENSO forecast, and Kalshi never sells protection against ENSO itself. PRF can, because it closes on December 1 at climatology-based rates.
- **Solar is the best wet-side partner in the rancher's own region and months.** ERCOT has about 34 GW, and winter irradiance correlates −0.44 with station rain. But a listed rain contract removes only 9% of a solar plant's winter energy variance. An irradiance put with no basis would remove 57%; a real plant would get less. Solar owners already buy volume hedges from Nephila and kWh Analytics.
- **Whether Kalshi prices El Niño is untested, and the November test had almost no power.** The saved history holds one ENSO-neutral winter. The November 2026 book gives β = −0.22 (bootstrap interval −0.42 to 0.18), but November carries little El Niño signal in the south-central region. Its ENSO-conditional climatology rests on about 20 seasons, so the regressor's reliability is about 0.2. Even a market that priced El Niño fully would show β near 0. December, with a 1.89x signal, is the real test.
- **Free federal drought aid competes with the product.** The Livestock Forage Disaster Program (LFP) pays grazing losses at no premium when the Drought Monitor reaches set levels. From 2026 the first payment comes after 4 weeks of D2 drought. LFP paid $1.78B in FY2023, more than PRF's $1.07B of 2023 indemnities, and it stacks with PRF ([doc 02](../research/02_how_farmers_buy_weather_insurance.md)). Neither the demand model nor doc 24's rancher willingness to pay accounts for it.

Bridge insurance abroad still fails. Kalshi restricts the best-studied index-insurance countries. Its only farm-region contract outside US cities (Saskatchewan) has never traded, and retail tickets are about 60 times smaller than Kalshi's wire minimum.

Climate drift and ENSO still decide pricing for any book. The August-October 2026 ONI is +2.46, and history-priced Texas and Southeast winter wet calls ran 35-48% underpriced after El Niño autumns ([review_checks_output.txt](../../scripts/experiments/expansion_review/review_checks_output.txt)).

## What changed from the first draft

Four independent reviews checked the first draft's facts, numbers and framing (section "How this report was checked"). The changes that move conclusions are below. Everything else in this report was rewritten to match them.

| First draft said | Revised finding | Why |
|---|---|---|
| Same-station pairing "halves capital per premium dollar" | About 88% of that drop comes from writing any second independent contract. The opposite-side benefit is in the worst year and in collateral. | Two far-apart puts need 1.96 vs 1.72-1.76 for a pair; worst year 3.50 vs 2.16 ([review_data_design.md](../research/expansion_notes/review_data_design.md) §7.1) |
| National pair pool needs 0.33 per month, about 0 per year | Those pools were priced in sample. Out of sample, the national annual venue-call pool loses its whole load, and a demand-weighted south-central winter book needs 1.32, not 0.13. | [review_checks_output.txt](../../scripts/experiments/expansion_review/review_checks_output.txt) §1, §5 |
| Snow book viable "only if trend-adjusted pricing restores the load" | Last-15-year or payout-trend pricing does restore it: snow pair loss ratio 1.05 / 1.01 vs 1.15. | same file, §3c |
| Winter wet side "priced fairly"; it subsidizes the drifting dry side | That is the 30-year average. Conditional on this winter's El Niño, the south-central wet call is the dangerous side (1.35x), and buyers can time it. | same file, §4 |
| Venue day counts net almost as well, so the timescale mismatch is cheap | True for capital, but no Kalshi monthly ladder can synthesize a venue payout (R² 0.27), and the daily >0-inch strip reaches only 0.53 and is priced off the forecast. | same file, §6; [daycheck.py](../../scripts/experiments/expansion_review/daycheck.py) |
| ECP route: "many farms" qualify via $1M net worth | That test is for entities only. Individuals, including sole-proprietor farmers, need over $10M invested, or over $5M if hedging. | [7 U.S.C. 1a(18)](https://www.law.cornell.edu/uscode/text/7/1a) |
| Kalshi snow settles at city airports; daily-rain cities unverified; no contract near non-US farm regions | Kalshi lists 536 climate series, including a 36-city daily rain series, resort-reported snowfall (some on Vail's own reports), and a Saskatchewan Apr-Jul precipitation contract. Almost none of it trades. | [Kalshi API](https://api.elections.kalshi.com/trade-api/v2/series?category=Climate%20and%20Weather), per [review_risks_factcheck.md](../research/expansion_notes/review_risks_factcheck.md) |
| Shortlist #1 was the winter rain pairing | First pass: #1 became the wholesale Companion and the rain pairing dropped to #3. The second pass reframed #1 again (section "Second pass"). | All of the above |

## Second pass: new lenses (2026-11-20)

Three more tracks then looked for what both drafts missed: other counterparties and the cost of capital, the lender's own economics, and the quantitative tests the first pass left unrun. What they changed:

| Lens | Finding | What it changes | Source |
|---|---|---|---|
| Lender's own P&L | No drought charge-off spike in the episodes checked: banks 0.24-0.25% in 2011-12, against a post-crisis 0.77% in 2010; Capital Farm Credit 0.0% net in 2019-23. High crop prices and land values in 2011-12 helped. Borrowers' PRF is already assigned to the lender, and Dallas Fed bankers said crop insurance was paying down credit lines in 2011. | The wholesale "lender holds the hedge" #1 has little principal loss to hedge, only lost volume, and a regulator who would call the hedge speculative. It is reframed as lender-financed distribution. | [lens_lender_reality.md](../research/expansion_notes/lens_lender_reality.md) |
| Pay-later evidence, second study | Deferred payment raised take-up only from 8% to 24% in Ethiopia, with high default, against 5% to 72% in Kenya, where the buyer controlled the harvest ([J-PAL](https://www.povertyactionlab.org/print/pdf/node/4519?lang=en)). | The pay-at-harvest lever is real but conditional on the financier controlling the sale. A hay buyer or an auction barn fits better than a bank. | same |
| PRF third-party payments | RMA ruled in March 2026 that a third party paying PRF premium for a share of indemnities is illegal rebating ([COM-26-003](https://www.rma.usda.gov/policy-procedure/bulletins-memos/informational-memorandum/com-26-003-rainfall-index-ri-pasture)). | It does not touch a Kalshi hedge, but any bundle sold alongside PRF must keep the two apart. | same |
| Lender-book HE (the "key test" left unrun) | 40 farms around one station: pooled HE 0.65-0.77 leaving one year out (0.63-0.79 on the 2001-2025 holdout), against 0.53-0.62 for the median farm. The four stations were chosen as Companion sites, not at random. Most of the gain comes by 10 farms. Basis errors correlate 0.50-0.60 across farms, so the book stops improving. Dollar weighting can erase the gain (11-farm holdout 0.53, because ABQ carries the largest protection). | Pooling helps whoever holds a book (an insurer, an MGA, a wholesale buyer), but the ceiling sits well below 1. | [lens_quant.md](../research/expansion_notes/lens_quant.md) §1 |
| Kalshi collateral | All 37 monthly rain series are tagged `DIRECNET`; reading the tag as directional collateral return is an inference from its name and the help page. With the opt-in return, YES-low plus NO-high in one event posts only the pair's worst-case loss. The setting is locked per event at the first order. Kalshi also pays 3.50% APY on positions. | Same-station, same-month netting is available on the exchange to any account, including a two-sided quoter, which revives an on-exchange maker. At an 80:1 dry-heavy flow, little of the book is paired. Cross-station and cross-month netting still needs a book. | [Kalshi Help](https://help.kalshi.com/en/articles/13823816-collateral-return); [APY](https://help.kalshi.com/en/articles/13823847-apy-on-kalshi) |
| Capital supply | Reinsurance capital is about $800B (Aon, June 30, 2026), and catastrophe-bond multiples are near 2.4x expected loss. Premium Markel fronted for Nephila was about $1.1B in the first nine months of 2026, against $1.8B a year earlier. | Capital is abundant in reinsurance and scarce on Kalshi's rain books. The binding constraint is getting it into the book, and buyers to it. | [Reinsurance News, Aon](https://www.reinsurancene.ws/record-800bn-reinsurance-capital-offers-insurers-growth-opportunities-heading-into-1-1-aon/); [Artemis](https://www.artemis.bm/news/as-cat-bond-loss-multiples-tighten-am-best-urges-investors-towards-greater-selectivity/); [lens_counterparties_capital.md](../research/expansion_notes/lens_counterparties_capital.md) |
| PRF interval choice | Texas Nov-Dec plus Jan-Feb: two of the three largest intervals (Mar-Apr edges Nov-Dec), 27% of PRF liability and 33% of premium (2025), loss ratio 1.11 over 2018-25. | The Companion's open-month market is smaller than the 11-farm sample implies. The 27% liability share is not 27% of ranchers, since PRF caps each interval, so rancher demand is biased high by an unknown amount. | same; RMA Summary of Business |
| Listing lead time | Monthly rain markets open at the start of the month, often hours after it begins (median lead 0 days). November 2026 was the exception, listed weeks ahead. As of Nov 20 only NYC (opens Nov 27) and Napa have December events; there is no Dallas December event. | A winter cannot be locked in, and ENSO risk is unhedgeable on Kalshi. PRF, sold at climatology rates by Dec 1, is the ENSO option, and Texas Jan-Feb PRF share dips after El Niño autumns (13% vs 15%, 8 years). | same |
| PRF insurers (AIPs) | They are short the same drought. In a 2025-type winter they retain about $1-24M of Texas winter PRF loss, depending on Assigned Risk Fund placement under the 2027 SRA. | AIPs sit on the rancher's side, not opposite it. They are a structuring-software client, and FCIC already offers them cheaper reinsurance. | same |
| Solar (ERCOT, 34 GW) | Winter irradiance vs station rain −0.44. A listed rain YES ladder removes 9% of a plant's winter energy variance. An irradiance put written on the plant's own index, with no basis, removes 57%; a real plant would get less. Rancher put plus solar call: 95% capital 1.75 against 1.81 for any second put, a difference within noise. The worst year is the robust gap: 2.00 vs 3.08. | Solar is the right region and months, but listed rain contracts are the wrong index for it, and Nephila and kWh Analytics already serve it. | [lens_quant.md](../research/expansion_notes/lens_quant.md) §3 |
| Kalshi and ENSO | One neutral winter of history. The November 2026 book gives β −0.22 (bootstrap interval −0.42 to 0.18). The regressor's reliability is about 0.2, so even a fully ENSO-aware market would show β near 0. The market was not shown to be sharper than climatology in 2025-26 (Brier 0.131 vs 0.118-0.123, 35 events). | The November test has almost no power. December's 1.89x signal, with shrunk regional climatology, is the real test. | [lens_quant.md](../research/expansion_notes/lens_quant.md) §2 |
| Golf and bookings | Sensible Weather sells tee-time refunds through GolfNow, Troon and Courserev. Its published attach rates, 12-31% (company figures), are for camping and lodging bookings; no golf rate is public. | Golf rain risk is already transferred, by golfers. Consumer-embedded guarantees have real demand, far above the 2% restaurant guess, but that market is crowded. | [lens_counterparties_capital.md](../research/expansion_notes/lens_counterparties_capital.md) |

## Bridge insurance fails abroad and needs a wholesale buyer at home

The US gap is real but narrow. **About 13% of US farms took part in federal crop insurance in 2022**: 62% of row-crop farms against 9% of specialty-crop farms ([USDA ERS](https://ers.usda.gov/data-products/charts-of-note/104817)). NAP pays only losses beyond 50% of yield, at 55% of price, capped at $125,000 ([CRS R48245](https://www.everycrsreport.com/reports/R48245.html)). Congress spent **almost $40 billion on ad hoc aid in FY2018-FY2025**, which CRS warns discourages insurance purchases ([CRS IF12101](https://www.everycrsreport.com/reports/IF12101.html)). A Kalshi hedge costs about 1.8 times subsidized PRF for the same expected payout ([doc 09](09_payout_comparison.md)).

Calling it "preliminary insurance" is the single most avoidable legal risk. A loss-linked product marketed as insurance falls toward state insurance law. "A rain-index hedge, not insurance" is the safer framing ([Insurance Business](https://www.insurancebusinessmag.com/us/news/catastrophe/is-a-kalshistyle-weather-contract-insurance-look-to-insurable-interest-596536.aspx); [review_risks_factcheck.md](../research/expansion_notes/review_risks_factcheck.md)).

Internationally the barriers stack. **About 1.3% of Africa's 51 million smallholders were insured, later updated to about 3.5%** ([EDE review](https://www.cambridge.org/core/product/6FB330C15BEE881A0358E1159DFF3199/core-reader)). Even Kilimo Salama reached under 10% of maize farmers in Embu ([Rural21](https://www.rural21.com/english/news/detail/article/weather-index-insurance-for-smallholder-farmers-insights-from-kenya.html)). Demand elasticity runs −0.66 to −0.88 ([Cole et al. 2013](https://dash.harvard.edu/server/api/core/bitstreams/7312037d-6130-6bd4-e053-0100007fdf3b/content)), and pilot loads run "well above 50 percent" ([UC Davis i4](https://i4.ucdavis.edu/node/2481)).

Kalshi's restricted list reportedly includes Kenya, Ethiopia and India, with India confirmed by news reports in June 2026 ([Cointelegraph](https://cointelegraph.com/news/kalshi-adds-india-restricted-jurisdictions?rand=6792)). Kenya and Ethiopia come only from a secondary list ([Datawallet](https://www.datawallet.com/crypto/kalshi-restricted-countries)). The largest thin-insurance market the reviewers found is Australia, where about 1% of NSW winter-crop growers held multi-peril cover ([Deloitte](https://www.deloitte.com/au/en/Industries/consumer-products/perspectives/multi-peril-crop-insurance-australia-barriers-opportunities.html)). It is also on the restricted list. Kalshi's foreign daily-temperature contracts (Mexico City, São Paulo, Tokyo and others) serve traders, not farmers.

The one farm-region contract outside US cities is the Saskatchewan Apr-Jul precipitation index (Saskatoon, Regina, Swift Current). It had zero volume, with a 0¢ bid and 99¢ ask ([Kalshi API](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXSKPRECPERIOD&status=open)). Canada is reportedly restricted too. Ticket sizes kill retail use: a $16 WFP premium in Côte d'Ivoire ([GIIF/WFP](https://docs.wfp.org/api/documents/WFP-0000154976/download)) against Kalshi's **$1,000 international wire minimum** ([Kalshi Help](https://help.kalshi.com/en/articles/14026044-can-i-trade-on-kalshi-from-outside-the-united-states)). Selling abroad would mean steering users around restrictions, which is a non-starter.

The reviews changed what the bridge idea should become, not whether it works. Take-up depends on when farmers pay, not only how much. In the Kenyan experiment, 5% of farmers bought when paying upfront and 72% when the premium came out of harvest proceeds; a 30% discount reached only about 6% ([Casaburi & Willis, AER 2018](https://www.aeaweb.org/doi/10.1257/aer.20171526)). Kalshi demands full collateral at purchase. So the lever available to the team is a third party that fronts the premium and recovers it at sale: a hay buyer, co-op or lender.

Lenders and co-ops already buy index cover on their loan books abroad. Examples include CLIMBS in the Philippines, the Jamaican credit union league with about 100,000 smallholder borrowers, and One Acre Fund through Global Parametrics ([ICMIF](https://www.icmif.org/weather-protection-insurance-for-farmers-in-the-philippines/); [Intelligent Insurer](https://www.intelligentinsurer.com/news/munich-re-howden-skyline-tie-up-to-develop-new-parametric-hurricane-cover-29176); [Reinsurance News](https://www.reinsurancene.ws/global-parametrics-and-one-acre-fund-deliver-parametric-solution-for-zambia-and-malawi-farmers/)). Kenyan risk-contingent credit trials report higher loan uptake, but the size of the effect conflicts across reports: 80% versus 20% per 3ie, 40% versus 30% per IFPRI 2017 ([3ie](https://www.3ieimpact.org/sites/default/files/2025-07/TW13.1028-IE-brief.pdf); [IFPRI](https://ifpri.org/wp-content/uploads/2019/07/fly_2017_rcc_v3_web.pdf)).

A US Farm Credit association already sells PRF ([Capital Farm Credit](https://www.capitalfarmcredit.com/insurance/crop-insurance/pasture-rangeland-forage-insurance/)). The first pass inferred that such an association would hold the hedge itself as one sophisticated account. The second pass rejects that: lenders' charge-offs fall in droughts, and their regulator treats risk-increasing derivatives as unsafe (section "Second pass"). The association's role is to distribute and finance the premium; the farmer holds the contract.

## Pairing mostly buys diversification; its real value is the worst year

Doc 26 ([26_intermediary_capital.md](26_intermediary_capital.md)) prices the middle seat of this pairing in dollars: capital, capital cost, break-even load and 1996-2025 gains and losses for a Kalshi maker, a lean carrier and a fronted insurer/MGA.

The netting backtest (`scripts/run_expansion_netting.py`) sells equal-premium linear contracts on each Kalshi station's 1951-2025 record. Puts pay below the 30th percentile and calls above the 70th, with a 20% load. The review added the missing baseline, a second independent contract:

| Book (rain, monthly total) | Capital95 / premium | Worst year / premium | Source |
|---|---|---|---|
| One farmer put | 3.57 | n/a | [expansion_netting_summary.csv](../../data/processed/expansion_netting_summary.csv) |
| Two farmer puts more than 1,000 mi apart | **1.96** | **3.50** | [review_data_design.md](../research/expansion_notes/review_data_design.md) §7.1, reproduced for this report over the same 2,943 station-pair-months |
| Farmer put + venue call, same station | **1.74-1.76** | **2.16** | summary CSV; same reproduction |
| Farmer put + venue call 50-200 mi away | 1.75-1.77 | n/a (both pay in 1.3-2.7% of months) | [crosspair.py](../../scripts/experiments/expansion_review/crosspair.py) |
| Farmer put + venue call, Fri-Sun day count (`rain_days`) | 1.84 | full collateral 5.68 vs 2.68 | summary CSV |

At the 95% level, the opposite side adds only about 0.2 per premium of benefit over any second contract. In the worst year it adds about 1.3. Exact same-station matching is unnecessary: a call 50-200 miles away nets as well at 95%. It does, however, break full-collateral netting, because both sides can then pay in the same month.

Snow and temperature pairs show the same mechanics: 95% capital per premium of 1.75 and 1.74, against 3.32 and 4.14 for one side ([expansion_netting_summary.csv](../../data/processed/expansion_netting_summary.csv)).

Collateral rules decide who captures any of this. Kalshi contracts are prepaid and fully collateralized ([Withum](https://www.withum.com/resources/prediction-markets-contracts-and-federal-income-tax-wagering-investing-or-something-else/)). The second pass verified that Kalshi does net within one event. Monthly rain events carry the `DIRECNET` tag, and with the opt-in collateral return a YES-low plus NO-high position posts only its worst-case loss ([Kalshi Help](https://help.kalshi.com/en/articles/13823816-collateral-return)). A same-station, same-month pair therefore nets for any account on the exchange. Pairs across stations or months do not, and the capital savings there belong only to a firm that is the counterparty itself. Netting customers off-exchange looks like operating an unregistered exchange or acting as a swap dealer ([review_risks_factcheck.md](../research/expansion_notes/review_risks_factcheck.md), inference). For cross-station and cross-month pairs, the netting benefit in practice lives on an insurer's or MGA's balance sheet, as at Demex, which sells both low-snow and high-snow cover backed by Nephila ([Artemis](https://www.artemis.bm/news/demex-launches-parametric-snow-covers-backed-by-nephila-reinsurers/)).

Pooling across stations diversifies weather but not drift, and real demand is concentrated. Dry-month correlation falls from 0.54 under 100 miles to about 0 beyond 1,000 ([expansion_netting_dry_corr.csv](../../data/processed/expansion_netting_dry_corr.csv)). But that average hides ENSO structure. The southern tier co-moves (mean pairwise winter-put correlation 0.25 across 12 stations), while south-central winter dryness correlates −0.34 with Seattle. A Texas rancher's put therefore partly offsets a Pacific Northwest farmer's put, which is netting without a venue ([review_checks_output.txt](../../scripts/experiments/expansion_review/review_checks_output.txt) §4).

The pooling results also change once demand and out-of-sample pricing are applied ([review_checks_output.txt](../../scripts/experiments/expansion_review/review_checks_output.txt) §1, §5):

| Pool | Capital95 / premium |
|---|---|
| South-central Nov-Feb farmer puts (DFW, OKC, SAT, AUS, CLL, HOU), the Companion's real demand | **1.32** (worst year +1.90) |
| Plains and West growing-season farmer pool | 0.34 |
| Equal-weight national pool, all months | 0.13 |
| National annual pair pool, in sample (first draft) | 0.000 |
| National annual pair pool, priced 1951-1995 and realized 1996-2025 | 0.038 |
| National annual venue-call pool, out of sample | 0.33 |

The national annual venue-call pool earns a mean margin of −0.002 out of sample: the whole 20% load is gone.

## Price on recent windows and ENSO, not on 75 years of climatology

Out of sample, history-priced contracts underpay whichever side the climate drifted toward. Pooled ratio-of-sums loss ratios are 1.20 for wet monthly calls and 1.03 for dry puts. The first draft's medians (1.17 and 0.99) understate this. A year-shuffle placebo puts the call drift outside all 300 null draws (null 95% band 0.87-1.08), and the result holds for any split year from 1980 to 2005 (calls 1.20-1.29).

Part of the drift may be the gauges themselves. ASOS heated tipping buckets, deployed around 1992-97 across the 1995 split, under-measured by 2-10% ([NRC 2012](https://www.nap.edu/read/13216/chapter/13)). That means wet-call drift is probably understated and dry-put drift overstated. Snow drift (low-snow puts 1.27) is partly a measurement artifact of inhomogeneous airport snow records ([Kunkel et al. 2007](https://climate.rutgers.edu/stateclim_v1/robinson_pubs/refereed/Kunkel_et_al_2007.pdf)).

The fix is mostly a pricing choice. In a walk-forward test where each year 1996-2025 is priced only on prior years ([review_checks_output.txt](../../scripts/experiments/expansion_review/review_checks_output.txt) §3), the pair loss ratio changes as follows:

| Variable | Full-history burn | Last 15 years | Linear trend in payout | Detrended index |
|---|---|---|---|---|
| Rain | 1.09 | 1.05 | **1.02** | 1.08 (and wrong for rain puts, 1.25) |
| Snow | 1.15 | 1.05 | **1.01** | 1.13 |
| Temperature | 1.18 | 1.14 | 1.10 | **1.06** |

Temperature drift persists even after the fix: the warm-side call is still 1.20 detrended. Recent windows are noisier per contract, so they should be pooled or shrunk toward the long-run value.

ENSO is the larger near-term risk, because it is public before the season and buyers can time it. Over 1951-2025 there were 20 El Niño, 18 La Niña and 38 neutral Nov-Mar seasons, classified on the August-October ONI. Payouts after each phase, relative to climatology, were ([review_checks_output.txt](../../scripts/experiments/expansion_review/review_checks_output.txt) §4):

| Region | Dry put after La Niña | Wet call after El Niño |
|---|---|---|
| South-central | **1.49** | **1.35** |
| Southeast | 1.37 | **1.48** |

The Companion's stations vary. Wet calls after El Niño paid 1.42 at OKC, 1.43 at SAT, 1.56 at ABQ and 1.60 at TPA, but only 1.01 at DFW. Tampa's dry put paid 0.37 after El Niño. A buyer who trades only on the favorable signal produces loss ratios of 1.17-1.64, above the 1.20 load in most regions.

The **August-October 2026 ONI is +2.46** ([oni.txt](../../scripts/experiments/expansion_review/dl/oni.txt)). A maker that prices Texas or Southeast winter wet calls on climatology this winter is selling into the signal. The same history implies the Companion's Texas dry hedges are less likely to pay this winter, which is about 0.66 times climatology in the south-central region. The advisor should show farmers that conditional expectation. Whether Kalshi's prices already embed El Niño was tested on the November 2026 book only. That test has almost no power (section "Second pass").

Timescale is the last design constraint. Across 37 stations, no function of the monthly total explains more than a median 27% of a wet-weekend-day payout's variance. A strip of Kalshi daily ">0 inch" binaries on Fri-Sun explains 53% at a 0.10-inch threshold ([review_checks_output.txt](../../scripts/experiments/expansion_review/review_checks_output.txt) §6; [daycheck.py](../../scripts/experiments/expansion_review/daycheck.py)). Daily markets list close to the date, so a venue buying them pays a forecast-informed price and hedges forecast surprises, not a bad season.

A seasonal venue product therefore needs an OTC day-count contract priced on nClimGrid-Daily or MRMS history. The settlement version should be frozen, for example MRMS Pass 2 at about 2 hours' latency ([NOAA MRMS](https://repository.library.noaa.gov/view/noaa/15285/noaa_15285_DS1.pdf)). One logarithmic market scoring rule over a station-month's strike bins would quote farmer and venue sides from a single probability vector, with a capped worst-case subsidy of b·ln n ([Chen & Pennock](https://arxiv.org/pdf/1206.5252)).

## Settlement, legal and demand risks the first draft missed

Kalshi's weather menu is far larger than the first draft assumed. It has **536 Climate and Weather series**, including a daily "Where will it rain" series across **36 US cities**, about 25 per-city daily rain series, and resort-reported snowfall. The resort series are Alta and Big Sky (monthly) and Park City, Beaver Creek, Keystone, Stowe, Northstar and Mammoth (season-to-date) ([Kalshi API](https://api.elections.kalshi.com/trade-api/v2/series?category=Climate%20and%20Weather)).

That corrects the first draft's "resort series unverified" caveat. Alta settles on Alta Ski Area and OnTheSnow reports, and Big Sky on OnTheSnow. **Park City and Stowe list "Vail Resorts" as a source**, so a Vail-owned resort hedging there would settle on its own report. These series fix station-to-mountain basis risk but create moral hazard, and Alta's December strip had traded about $300 ([KXALTASNOW](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXALTASNOW&status=open)).

The settlement source is shifting. **The Weather Company is a named source on 254 of the 536 series**, against 142 for NWS and 76 for NOAA. The daily KXRAIN rules state that "missing daily precipitation values are counted as 0 inches" ([KXRAIN rules](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXRAIN&status=open)). A data outage therefore pays the dry side and hurts the wet side, a one-sided risk for any farmer-against-venue book that the backtests (built on NWS and GHCN data) do not model.

Two other settlement risks sit underneath. NWS lost more than 600 staff in 2025 and has rehired about 200 ([E&E News](https://www.eenews.net/articles/national-weather-service-in-transition-as-hurricane-season-begins/)). And sensor tampering is practical: Météo-France referred a Paris CDG temperature spike to police after Polymarket payouts, and Kalshi lists a daily CDG rain series ([Decrypt](https://decrypt.co/365276/french-weather-agency-alerts-police-to-sensor-interference-after-35k-polymarket-payouts)).

The legal stack has more triggers than routing. The ECP test shuts most small buyers out of bilateral swaps. Entities need over $10M in assets, or over $1M net worth when hedging. Individuals, including sole-proprietor farmers, need over $10M invested, or over $5M when hedging ([7 U.S.C. 1a(18)](https://www.law.cornell.edu/uscode/text/7/1a)). Lenders, co-ops, feedlot companies and insurers mostly qualify; many ranchers and restaurants do not. The team's own product triggers further registration questions, all inferences that need counsel:

- **CTA:** charging for individualized trade recommendations, which is what `advisor.py` produces, may require Commodity Trading Advisor registration.
- **IB:** routing orders requires introducing-broker registration, which one source puts at 3-6 months ([KPMG](https://kpmg.com/kpmg-us/content/dam/kpmg/pdf/2025/current-state-prediction-markets.pdf)).
- **CPO:** the DEMO.md roadmap item "pooled orders across ranches" resembles a commodity pool.

Tax treatment is unsettled. The IRS has issued no event-contract guidance, and wager treatment would cap deductible losses at winnings under §165(d) ([Withum](https://www.withum.com/resources/prediction-markets-contracts-and-federal-income-tax-wagering-investing-or-something-else/)). The courts are split on CEA preemption for sports contracts, with the Third Circuit against the Ninth and Sixth, and New Jersey filed a cert petition on September 2, 2026 ([The Block](https://theblock.co/news/regulation/2026-09-02-new-jersey-asks-supreme-court-to-decide-who-regulates-sports-betting-on-prediction-markets-413398)). The CFTC's June 10, 2026 proposed event-contract rule targets gaming and war, not weather ([WilmerHale](https://www.wilmerhale.com/en/insights/client-alerts/20260618-10-takeaways-from-the-cftc-event-contracts-proposed-rulemaking)).

Demand precedents are mostly negative. In 2008 only about 1 in 10 weather-sensitive mid-size and large firms had ever used weather derivatives ([CME 2008](https://www.cmegroup.com/media-room/press-releases/2008/4/29/survey_finance_executivessayglobalclimatechangewillrequirechange.html)). CME delisted rain and snow contracts with "no open interest" ([CME SER-7216](https://cmegroup.com/tools-information/lookups/advisories/ser/SER-7216.html)). WeatherBill survived by becoming an insurer ([Full Stack Researcher](https://fullstackresearcher.substack.com/p/deconstructing-a-successful-startup-pivot?r=4swq6)). Retail parametric products have closed, such as AXA's Fizzy ([CAS](https://ar.casact.org/indexing-the-future-the-rise-of-parametric-insurance-and-its-expanding-ecosystem/)).

A few named small businesses do hedge on Kalshi: a kayak operator (rain), an ice-cream shop (cold) and an online farmers market (heat). Brokers cite liquidity, basis and payment-reliability concerns, and Kalshi block trades require at least 25,000 contracts and ECP status ([Business Insurance](https://www.businessinsurance.com/prediction-markets-gain-role-in-risk-transfer/)). A same-day snapshot shows how thin the books are: NYC November rain about $3.1K, Denver December snow about $10K ([review_risks_factcheck.md](../research/expansion_notes/review_risks_factcheck.md)).

A direct competitor now exists for the advisor. **Blanket** (August 2026) maps a small business's described risks to Kalshi contracts and logs "near misses" as demand signals. Fortune, opened by a reviewer, describes it as built by an independent founder without Kalshi's compliance team ([Fortune](https://fortune.com/2026/08/07/exclusive-kalshi-blanket-small-business-hedge-hypergamblification/)); other outlets present it as Kalshi's ([Crypto Briefing](https://cryptobriefing.com/kalshi-blanket-small-business-hedging-tool/)). AgriHedge differs on what Blanket, as described, lacks: out-of-sample HE, a station-to-farm basis-risk report, executable-depth checks against saved books, PRF interval integration and utility-optimal payout shapes (docs 21-24).

## Demand estimate: what losses imply buyers would pay

This section turns measured weather losses into an educated guess at hedge demand: premium per year, contracts and take-up. Each figure has a P10-P90 band. The numbers come from `scripts/run_weather_demand.py` (about 5 s once the netting script's ACIS cache exists; outputs `data/processed/weather_demand_*.csv` and [weather_demand.png](../figures/weather_demand.png)). They are model estimates, not observed purchases. Every input marked "assumption" in the numbers table is a team guess with a stated range.

**Headline.** A rational firm that weighs a hedge against its cash pays almost nothing for rain protection at Kalshi's 1.2x price. Rain losses are real but small next to a firm's cash. Ranchers appear to be the exception, paying up to about 1.4x, but that partly reflects a different wealth frame. Their WTP comes from doc 24, where wealth is 1.25-4 times the month's insured value. A restaurant's cash frame is about 100 times its insured value.
- **Dry side (ranchers near Kalshi stations):** about **$12M a year** standalone (P10-P90 $2.4-17M), and $24M if a lender bundles it. The $24M restates the assumed embedded take-up (0.45 vs 0.20); it is not evidence for the lender channel.
- **Wet side, all rain segments nationally:** about **$13M a year** ($1.3-26M). Golf is $12M of that. Restaurants are about $0.35M.
- **Snow-belt cities:** about $1.6M a year.
- **Wet against dry, same stations, Nov-Feb:** about **1:80** in premium (P10-P90 1:400 to 1:40). That compares rational wet firms with narrow-frame ranchers. With both sides in the narrow frame the ratio is **about 1:3** (0.31), which is the like-for-like figure.

The "central" values set every input at its most likely value. Because demand sits in the tail of a lognormal, they lie near the top of their own bands. The Monte Carlo medians, recomputed by the logic review, are lower: restaurants about $30k, golf $5.8M, ranchers $9.1M, and wet:dry 1:133. The two fixed spreads across firms (the sd of log γ and log W) are not varied in the bands. Moving them moves restaurant demand about 230 times, so the bands understate the uncertainty ([logic_review_quant.md](../research/expansion_notes/logic_review_quant.md) §4).

If firms judge hedges against one month's profit instead of their cash (a "narrow frame", which is how people actually buy small insurance), wet demand rises tenfold to about $134M. That is the largest single uncertainty.

**Our best guess for restaurants: about 2% take-up, $6M a year in the Kalshi metros, $15M nationally.** The cash-frame model is a floor, not a forecast: expected-utility models with realistic risk aversion predict almost no purchase of small-stakes insurance, yet households pay several times expected losses for low deductibles ([Sydnor 2010](https://www.aeaweb.org/articles?id=10.1257/app.2.4.177)), and 29-46% of small businesses carry business-interruption cover ([demand_inputs.md](../research/expansion_notes/demand_inputs.md)). The narrow frame ($39M nationally) is meant as a ceiling. The CARA expansion was validated only in the broad frame, and exact CRRA would give more, so treat it as a rough high case rather than a bound. Between them we use an adoption analog: about 10% of weather-sensitive firms have used weather derivatives, mostly large firms ([demand_inputs.md](../research/expansion_notes/demand_inputs.md), CME 2008), so we take one fifth of that, **2% (range 1-5%)**, for restaurants offered a dinner-rain cover through their POS or reservation system. The arithmetic, from the model's per-firm contract (`weather_demand_segment.csv`: expected payout $190 per firm-month, maximum payout $795):

| Take-up | Buyers, Kalshi-23 / national | Premium per buyer per year (1.2x) | Premium per year, Kalshi-23 / national | $1 contracts per month, Kalshi-23 |
|---|---|---|---|---|
| 1% | 1,057 / 2,642 | $2,737 | $2.9M / $7.2M | 0.84M |
| **2% (best guess)** | **2,113 / 5,284** | **$2,737** | **$5.8M / $14.5M** | **1.68M** |
| 5% | 5,284 / 13,210 | $2,737 | $14.5M / $36.2M | 4.20M |

At the best guess, restaurant demand alone is about 17 times the resting YES depth at the same stations on the Nov 2 book (98,607 contracts, `weather_demand_depth.csv`), and it would come from a daily dinner-hour contract that Kalshi does not list. Restaurant demand is also year-round and peaks in Nov-Apr (winter rainy days cost 7.1% of diners versus 2.3% in summer, [rain_reservations_effects.csv](../../data/processed/rain_reservations_effects.csv)), so it overlaps the Companion's dry-side months better than patio-season reasoning suggested. Across all Kalshi metros the best guess ($5.8M) is about half the ranchers' dry premium ($12.1M), but the two sit in different places. At the eight stations and four months where ranchers actually buy (AUS, DEN, DFW, HOU, OKC, SAT, STL, TPA; Nov-Feb), best-guess restaurant premium is $0.58M against $8.6M of rancher premium, **about 1:15** (1:6 at 5% take-up; computed from `weather_demand_city_month.csv`, `firms × take-up × eh_firm × 1.2`). That is far short of the 3:1 balance at which netting keeps about 62% of its benefit. So even on the best guess, restaurants are a separate wet-side business in the big rainy metros (NYC, Boston, Chicago, Philadelphia), not the counterparty that balances a Texas rancher book. Restaurant demand at 2% also needs a POS or booking partner; standalone, the cash-frame result (near zero) is the better guide.

### Evidence: rain losses by segment

- **Restaurants.** A day with at least 0.10 in of airport rain cuts OpenTable seated diners by 4.4% (95% CI 3.3-5.5%). Dinner-hour rain cuts 6.5%, with no rebound later in the week. That is about $219 of sales per rainy day for a $1.8M restaurant. Applied to 1991-2025 daily rain, a typical restaurant loses $1,231 of sales in a mean month and $2,024 in a 95th-percentile month. Sources: [rain_reservations.md](../research/expansion_notes/rain_reservations.md), [rain_reservations_effects.csv](../../data/processed/rain_reservations_effects.csv), [rain_reservations_city_month_loss.csv](../../data/processed/rain_reservations_city_month_loss.csv).
- **Ballparks.** Open-air MLB parks lose 2.4-3.7% of attendance on played rainy games. Rainouts hit 1.81% of games and cost 31% of a gate, so a rainy home date costs about $97k. A club-month loses $251k on average, $597k at the 90th percentile and $721k at the 95th. The club loss correlates only 0.36 with the station's monthly total, and 0.52 with a count of wet home dates. Divvy casual bike trips fall 42-57% on rainy days. Sources: [rain_venues.md](../research/expansion_notes/rain_venues.md), [rain_venues_team_month_loss.csv](../../data/processed/rain_venues_team_month_loss.csv).
- **Other inputs:** firm counts, sales, margins, cash buffers, golf, construction and snow budgets, PRF premiums, and take-up evidence. All are in [demand_inputs.md](../research/expansion_notes/demand_inputs.md) and [demand_inputs.csv](../../data/processed/demand_inputs.csv).

### Method

1. **Loss per firm-month,** 1991-2025, at each Kalshi station. The model rebuilds each segment's loss from the station's daily record:
   - **Restaurants and bars:** OpenTable rain-bin × season effects, each city's shrunk scale, metro sales per firm, and a 0.65 contribution margin. Rebuilt at the Kalshi stations, the loss matches the reservation study's city-month means exactly (median ratio 1.000).
   - **Golf:** 2.2% of rounds lost per inch of monthly rain above the mean, months with mean temperature of at least 50 F, and a 0.7 margin.
   - **Construction:** excess wet workdays above the month's median × $1,250 per day.
   - **Snow cities:** the snow budget × the month's snowfall deviation, divided by mean season snowfall.
   - **MLB:** a gamma fit to each club-month's mean and p95, × 0.5 net of revenue sharing.
   - **MiLB:** the median MLB club scaled to 3,847 fans at $30.
   - **Ranchers:** the Companion packages of doc 21, scaled to the state's average PRF policy.
2. **Contract and hedgeable share.**
   - The contract is a call on the station index, struck at the median and capped at the 95th percentile. It is sized by OLS to the expected excess loss given the index.
   - Indexes: the wet-day count for restaurants, construction and venues; the listed monthly total for golf; monthly snowfall for cities.
   - HE is the share of loss variance removed. A firm is not the city average: its loss correlates ρ with the airport-settled loss, so it holds ρ × the station hedge and keeps ρ² × HE.
   - ρ values (assumptions): restaurants 0.8 (0.6-0.9), construction 0.8, golf 0.7, cities 0.85.
   - MLB uses its measured 0.52 (0.36 on the listed monthly total). Ranchers keep the Companion's out-of-sample HE.
3. **Willingness to pay.**
   - Utility is CRRA with γ = 2, applied to W = cash buffer + one month's profit. For a restaurant: 16 days of outflows plus 2.8% of a month's sales, about $81k.
   - Losses are small next to W, so the CARA expansion WTP = 1 + (γ/W) × HE × Var(L) / (2 E[payout]) is used. Exact CRRA differs by at most 0.0004.
   - Ranchers' WTP is the load at which doc 24's utility-optimal contract stops adding certainty-equivalent value ([m2_design_optimal.csv](../../data/processed/m2_design_optimal.csv)).
4. **Take-up** = t₀ × m^ε × S(m).
   - S is the share of firms whose WTP exceeds the price multiple m. γ and W are lognormal across firms (sd of logs 0.7 and 1.0, assumption).
   - Standalone: t₀ = 0.20 (0.10-0.35) is take-up at a fair price (m = 1), scaled by m^ε at Kalshi's all-in m = 1.2. t₀ is an observed rate that already reflects willingness to pay, so multiplying by S(m) counts price sensitivity twice. That is why restaurants come out near zero and the 2% best guess is used instead.
   - Embedded via POS, booking or lender: t₀ = 0.45 (0.30-0.60) at m = 1.3, adding a distributor margin.
   - ε = −0.77 (−2.5 to −0.66).
5. **Demand** = firms × take-up × (premium m·E[payout], and maximum payout = number of $1 contracts).
   - Kalshi-23 means the 23 metros in `demand_inputs.csv`. For ranchers it means the 11 Kalshi stations near Companion farms.
   - National scales per-firm results by national firm counts.
   - Bands are P10-P90 over 400 joint draws of all parameters, each triangular between low and high.

### Headline by segment (standalone unless noted; national)

| Segment | Firms, national / Kalshi-23 | Loss per firm-month, mean / p95 | Hedgeable share (HE, firm) | WTP multiple: cash frame / narrow frame | Take-up: standalone / embedded | Premium $/yr: P10 / central / P90 | Embedded central | Kalshi-23 central | $1 contracts per station-month |
|---|---|---|---|---|---|---|---|---|---|
| Full-service restaurants | 264,208 / 105,671 | $1,012 / $1,673 profit | 0.44 (0.69 at the station; 0.57 on the listed monthly total) | 1.004 / 1.08 | 0.026% / 0.019% | $1k / **$350k** / $445k | $289k | $140k | 1,768 |
| Bars | 42,624 / 13,934 | $584 / $960 | 0.44 | 1.004 / 1.09 | 0.026% / 0.019% | $0.1k / **$30k** / $39k | $25k | $10k | 126 |
| Construction (≥ 20 staff) | 75,078 / 30,028 | $878 / $3,469 | 0.61 | 1.002 / 1.05 | 0.003% / 0.001% | $0.1k / **$25k** / $184k | $16k | $10k | 131 |
| Golf facilities | 14,000 / 3,500 | $4k / $15k swing above a normal month | 0.42 | 1.04 / 1.42 | 1.6% / 1.9% | $1.3M / **$12.1M** / $25.1M | $15.8M | $3.0M | 56,546 |
| MLB open-air clubs | 22 / 15 | $122k / $350k | 0.23 | 1.003 / 1.04 | 0.009% / 0.006% | $9 / **$812** / $3k | $591 | $726 | 27 |
| MiLB clubs (scaled) | 120 / 24 | $12k / $35k | 0.24 | 1.013 / 1.13 | 0.20% / 0.17% | $208 / **$6.5k** / $18k | $6.0k | $1.3k | 4,633 (national, all clubs) |
| **Wet rain total** | | | | | | $1.3M / **$12.6M** / $26.1M | $16.1M | $3.2M | |
| Snow-belt cities (13 Kalshi snow stations) | 13 / 9 | $1.8M / $5.9M overrun | 0.65 | 1.03 / 1.26 | 0.89% / 1.0% | $146k / **$1.6M** / $3.3M | $1.9M | $1.5M | 96,110 |
| **Dryland ranchers** (eligible PRF policies near 11 Kalshi stations) | 5,816 | $2,915 expected gap loss / n/a | 0.66 (doc 21, out of sample) | 1.42 (doc 24 grid; 1.10 at DEN and ABQ, which get no package) | 15.2% / 27.6% | $2.4M / **$12.1M** / $16.8M | $23.5M | same | 716,799 |

How to read the table:
- **Losses.** Restaurant, bar and construction losses are profit. MLB losses are net of revenue sharing. Golf and city losses are symmetric around a normal month, so the table shows the mean overrun above the median and the p95 month. City budgets are partly assumptions.
- **Embedded below standalone.** Embedded take-up is lower than standalone wherever the rational screen binds: the higher embedded price (1.3x) fails more firms than the higher base take-up adds.
- **Narrow frame.** If firms weigh a hedge against one month's operating profit (a city: its snow budget), national standalone premium becomes:

  | Segment | Narrow-frame premium |
  |---|---|
  | Restaurants | $39M |
  | Bars | $3.5M |
  | Construction | $17M |
  | Golf | $74M |
  | MLB | $117k |
  | MiLB | $194k |
  | Cities | $14.6M |
  | Ranchers | $14.0M (wealth 1.25 per $ insured) |
  | Wet total | $134M |

  With ranchers' wealth at 4 per $ insured, the more rational frame, ranchers fall to $7.7M.

Golf leads the wet side for two reasons. Its loss is a direct function of the listed monthly total, and a facility's monthly swing is about 4% of its cash, against 0.5% for a restaurant. The 2.2%-per-inch rule is a national rule of thumb, so golf's figure is the least anchored wet-side number.

### Wet against dry, and what Kalshi's book could fill

Wet and dry demand compared at the stations with both (AUS, DEN, DFW, HOU, OKC, SAT, STL, TPA), Nov-Feb:

| Scenario | Wet premium | Dry premium | Wet:dry premium (P10-P90) | Wet:dry maximum payout |
|---|---|---|---|---|
| Standalone, cash frame (central) | $104k | $8.6M | **0.012** (0.0024-0.024) | 0.022 |
| Embedded, cash frame | $117k | $16.3M | 0.007 (0.0026-0.018) | 0.013 |
| Standalone, narrow frame | $3.1M | $10.0M | 0.31 | 0.51 |
| Embedded, narrow frame | $5.0M | $22.9M | 0.22 | 0.36 |

The netting backtest found the 1:1 book best, and a 3:1 farmer-to-venue book keeps about 62% of the 95% capital benefit ([netting_quant.md](../research/expansion_notes/netting_quant.md)). The central demand mix is about 80:1 dry-heavy, so same-station netting has almost no wet partner to net against. Only the narrow-frame case reaches the 3:1 regime.

November 2026 demand compared with resting depth on the listed monthly ladders ([weather_demand_depth.csv](../../data/processed/weather_demand_depth.csv); `kalshi_rain_orderbook_summary_{20261102,20261029}.csv`). Fill counts each station's depth only up to that station's demand; wet demand is mostly a day-count contract, compared here with the monthly ladder as a proxy.

| November, $1 contracts | Wet side (buys YES) | Dry side (buys NO) |
|---|---|---|
| Demand, standalone / embedded | 373,745 / 383,986 | 6,192,536 / 9,800,301 |
| Resting depth at those stations, Nov 2 (rewards off) | 98,607 | 18,918 |
| Fillable share, Nov 2 | **11.7%** / 10.6% | **0.31%** / 0.19% |
| Resting depth, Oct 29 (rewards on) | 1,100,986 | 460,981 |
| Fillable share, Oct 29 | 37% / 37% | 7.1% / 4.7% |

Depth sums every price level, including far strikes, so the fill shares are upper bounds. Rancher demand alone is about 330 times the post-rewards NO depth at its stations. This is the doc 22 liquidity limit restated at market scale.

### Sensitivity: what moves the answer

One assumption at a time, from the low to the high case, with everything else central ([weather_demand_sensitivity.csv](../../data/processed/weather_demand_sensitivity.csv)). Central values: restaurants $350k, wet national $12.6M, wet:dry 0.012.

| Assumption (low / high) | Restaurants, national | Wet total, national | Wet:dry ratio |
|---|---|---|---|
| Wealth frame (cash + profit / one month's profit) | $350k / $39.1M | $12.6M / $134M | 0.012 / 0.313 |
| Price multiple, standalone (1.6 / 1.1) | $19k / $1.58M | $2.3M / $27.8M | 0.005 / 0.031 |
| Risk aversion γ (1 / 4) | $58k / $1.61M | $4.4M / $28.4M | 0.004 / 0.030 |
| Golf rounds lost per inch (1.5% / 3.0%) | no effect | $5.3M / $24.6M | 0.006 / 0.023 |
| Base take-up, standalone (0.10 / 0.35) | $175k / $613k | $6.3M / $22.0M | no effect |
| Golf facility-to-airport ρ (0.5 / 0.85) | no effect | $5.9M / $19.2M | 0.006 / 0.018 |
| Price elasticity (−2.5 / −0.66) | $256k / $358k | $9.2M / $12.8M | no effect |
| Restaurant effect size, 95% CI | $126k / $740k | $12.3M / $13.0M | 0.011 / 0.014 |
| Restaurant cash buffer (27 / 12 days) | $98k / $657k | $12.3M / $12.9M | 0.011 / 0.014 |
| Restaurant firm-to-airport ρ (0.6 / 0.9) | $129k / $521k | $12.3M / $12.7M | 0.011 / 0.013 |
| Restaurant rebound (net = 50% / 100% of gross) | $29k / $350k | $12.2M / $12.6M | 0.010 / 0.012 |
| Contribution margin (0.55 / 0.70) | $197k / $450k | $12.4M / $12.7M | 0.011 / 0.013 |
| Sales per restaurant ($1.0M / $2.3M) | $195k / $448k | $12.4M / $12.7M | 0.011 / 0.013 |
| Rancher share of state policies (×0.5 / ×1.5) | no effect | no effect | 0.024 / 0.008 |

How the model behaves (the remaining rows, for construction and venues, move totals by under 3%):
- **Wealth frame and price dominate.** The rational screen sits in the tail of a lognormal, so how firms frame the purchase and the price multiple move demand by 10-100x.
- **Inputs to the screen move restaurants more than proportionally.** Effect size, cash buffer and ρ feed the screen, which is why they move restaurant demand more than they move expected loss.
- **Some inputs cancel in the ratio.** Base take-up and elasticity scale wet and dry alike, so they leave the wet:dry ratio unchanged.

### What this changes in the ranking

These numbers fed the first-pass ranking. The section "Head-to-head comparison" now supersedes it.

- **Restaurants.** The modeled demand of single restaurants is essentially zero at any realistic price (central $350k a year nationally, against $14k of annual rain loss per restaurant). This confirms their low place in both the segment matrix and the head-to-head (#13).
- **The winter rain pairing (head-to-head #16; first pass #3).** The wet side it needs barely exists among the firms modeled here: about 1% of rancher premium at the same stations and months. That is consistent with the report's advice to source the wet side from wholesale counterparties, which this model does not cover.
- **Dry-side demand.** Ranchers' dry demand is the largest rational demand found, and it doubles when a lender fronts it. The doubling restates the assumed embedded take-up, so it is not evidence for the lender channel. The figure is biased high, because Texas already puts 27% of PRF liability in Nov-Feb, and executable depth caps it far lower (section "Second pass").
- **Golf.** Golf is the largest wet segment on paper and fits a listed monthly contract. It rests on a rule-of-thumb sensitivity, so its "Hedging evidence" score of 1 stays.

No scores in the matrix were changed. The model does not cover feedlots, promotions, insurers or solar owners. The second pass found solar the best-matched wet side in the rancher's region and months, though badly served by listed rain contracts.

## Segment scoring matrix (first pass; superseded for ranking by the head-to-head)

This matrix scores weather segments (who has the exposure). The section "Head-to-head comparison" scores strategies (how a team would make money) and supersedes it for ranking. The lender row predates the second pass, whose lender findings move "Hedging evidence" for a lender holding its own book to 1. Scores run 1-5, where 5 is best for a small platform; they are the team's judgment from the cited evidence. "Netting value" credits the worst-year and collateral benefit of a same-index opposite side, not the 95% diversification any second contract gives. "Pricing stability" scores drift under the best walk-forward method plus ENSO timing exposure. The unweighted total is a sorting aid only.

| Segment (side) | Exposure | Station measurability | Fit to listed contracts | Hedging evidence | Legal path | Netting value | Pricing stability | Basis (5 = low) | Total /40 | Key evidence |
|---|---|---|---|---|---|---|---|---|---|---|
| Per-push plow contractors, salt suppliers (low snow) | 4 | 5 | 4 | 3 | 3 | 4 | 3 | 4 | **30** | Compass salt −15% in a mild winter; low-snow put 1.12 with last-15 pricing |
| Cities, fixed-fee plow contractors (high snow) | 5 | 5 | 3 | 2 | 2 | 4 | 4 | 5 | **30** | Boston about $47M over; Logan settlement; reserves, not hedges; public procurement |
| Weather-contingent retail promotions (wet/snow day) | 2 | 5 | 3 | 3 | 4 | 3 | 3 | 5 | **28** | TMHCC/BUA contingency cover; zero basis if written on the settlement station; Nov-Feb |
| Ag lenders, co-ops, hay buyers (wholesale dry hedge) | 4 | 4 | 4 | 3 | 4 | 3 | 2 | 3 | **27** | Meso cover abroad; entity ECP; portfolio averages farm basis; ENSO-exposed |
| Dryland ranchers, Nov-Feb, retail (dry put) | 3 | 4 | 4 | 5 | 3 | 4 | 2 | 2 | **27** | PRF 298M acres; La Niña puts pay 1.49x; 29-55 mi basis |
| Gas and electric utilities (temperature) | 5 | 3 | 3 | 5 | 4 | 2 | 1 | 4 | **27** | Already on CME; no Kalshi monthly mean; warm call 1.20 even detrended |
| Construction contractors (wet days) | 4 | 4 | 2 | 4 | 3 | 4 | 2 | 3 | **26** | Zurich/Descartes covers; no listed ≥0.10-in day-count contract; El Niño wet calls 1.35x |
| Insurers and MGAs with wet-day or snow books (wholesale counterparty) | 4 | 3 | 2 | 4 | 3 | 4 | 3 | 3 | **26** | Sensible 1M+ guarantees; Vortex, Demex; one B2B deal replaces thousands of venues |
| Large venues: festivals, MLB/MiLB, parks (wet day) | 4 | 3 | 2 | 4 | 3 | 3 | 3 | 3 | **25** | Event insurance market; hour windows; daily strip R² 0.53 |
| Golf courses (wet monthly) | 2 | 4 | 4 | 1 | 4 | 4 | 2 | 3 | **24** | 2.2% of rounds per inch; no hedging found |
| Feedlots (mud: wet and cold, Nov-Mar Plains) | 3 | 3 | 3 | 2 | 4 | 4 | 2 | 2 | **23** | 14-25% lower gain in mud; the only farm-side wet-loser in the Companion's months; no product |
| Ski resorts (low snow, resort-reported series) | 4 | 3 | 2 | 3 | 2 | 3 | 3 | 3 | **23** | Resort series fix basis but Vail self-settlement and about $300 of volume |
| Dairy heat stress (hot days) | 4 | 2 | 2 | 3 | 3 | 2 | 1 | 2 | **19** | $1.2-1.65B/yr; four THI products; Kalshi has daily highs only in AZ/TX, no humidity |
| Single restaurants, patio bars (wet) | 1 | 3 | 2 | 1 | 3 | 3 | 3 | 2 | **18** | Monthly comps move about 1.6 points; patios off-season in winter |
| Hydro and wind generators | 5 | 1 | 1 | 4 | 3 | 1 | 2 | 1 | **18** | Basin or turbine indices; bespoke deals |
| US uninsured and NAP specialty growers, retail bridge | 2 | 2 | 2 | 2 | 2 | 3 | 2 | 2 | **17** | 9% specialty FCIP use; ad hoc aid crowds out demand; insurance-label risk |
| Seasonal retail, beverage, airlines | 3 | 2 | 2 | 1 | 3 | 1 | 2 | 2 | **16** | National footprints; analytics, not hedges |
| International smallholders via an aggregator | 3 | 1 | 2 | 3 | 2 | 1 | 2 | 1 | **15** | GIIF 4M+ contracts, all subsidized; no listed stations in target countries |
| "Bad-weather winners": delivery, cinemas, generators | 3 | 2 | 1 | 1 | 3 | 1 | 2 | 2 | **15** | They gain when wet, so they sit on the farmer's side, not opposite it; none hedges its upside |
| International smallholders, direct | 1 | 1 | 1 | 2 | 1 | 1 | 2 | 1 | **10** | $16 premiums against a $1,000 minimum; restricted countries |

Several entries rest on single sources or old data. The feedlot mud figures come from K-State, partly from 1970s trials and simulations ([K-State MF2673](https://bookstore.ksre.ksu.edu/download/how-feeding-site-mud-and-temperature-affect-animal-performance_MF2673)). The dairy figures are ERS (2010 data) and a Cornell summary ([ERS](https://www.ers.usda.gov/amber-waves/2014/november/greater-heat-stress-from-climate-change-could-lower-dairy-productivity); [Food Ingredients First](https://www.foodingredientsfirst.com/news/heat-stress-dairy-ingredient-quality-cornell.html)). The bad-weather-winner evidence comes from DoorDash's own statements and Generac's filings ([DoorDash](https://about.doordash.com/en-us/news/winter-storm-fern); [Generac](https://quantisnow.com/insight/generac-reports-third-quarter-2024-results-5744805)). Promotion pricing (1.5-5.5% of promoted sales) dates from 2010 and is unverified ([CNN Money](https://money.cnn.com/2010/12/30/smallbusiness/snow_jewelry_full_refunds/)).

Measurement disputes are the promotions' failure mode. A Coeur d'Alene jeweler's roughly $500K snow promotion was first denied when the insurer's weather vendor measured below the threshold, then approved after the vendor revised its reading ([KREM](https://www.krem.com/article/news/local/coeur-dalene-jewelers-500k-snowfall-promotion-payout-approved-by-insurance/293-320eecff-b282-4ebd-9cad-a233269c203c)). A promotion written on a Kalshi settlement station inherits Kalshi's settlement instead of a vendor's.

The first pass also scored delivery mechanisms and business models, which decide who holds the risk rather than which weather it is. The table below is kept for the record. The head-to-head supersedes it: wholesale to lenders is reframed, PRF insurers are a weaker software customer, and on-exchange quoting gained collateral netting.

| Model | Capital needed (5 = least) | Legal clarity | Demand evidence | Fit with team code | Testable by Dec 15 | Total /25 | Main risk |
|---|---|---|---|---|---|---|---|
| Wholesale to lenders, co-ops or hay buyers, premium recovered at sale | 5 | 4 | 3 | 5 | 4 | **21** | No US precedent; passing protection to farmers as a promise makes it insurance |
| Structuring and pricing SaaS for insurers, MGAs and lenders | 5 | 3 | 3 | 5 | 4 | **20** | Blanket, CelsiusPro, Riskwolf and Arbol's platform already compete; CTA question |
| USDA 508(h) or index-weather plan submission | 4 | 5 | 4 | 4 | 1 | **18** | Years of review; no weather 508(h) approval in 2025 FCIC minutes |
| IB or FCM routing of retail hedgers to Kalshi | 4 | 3 | 2 | 4 | 2 | **15** | NFA registration; thin books; tiny tickets |
| Quoting as a Kalshi liquidity provider | 3 | 4 | 1 | 3 | 2 | **13** | Weather not in program; incentives cut after CFTC advisory |
| Embedded B2B2C guarantees via partners | 2 | 3 | 4 | 2 | 1 | **12** | Crowded (Sensible 1M+ guarantees; WeatherPromise $12.8M Series A) |
| Own book or MGA netting two-sided books | 2 | 2 | 2 | 3 | 1 | **10** | Needs carrier and reinsurer; this is where netting capital savings actually live |

Sources: [Casaburi & Willis](https://www.aeaweb.org/doi/10.1257/aer.20171526); [CelsiusPro](https://www.celsiuspro.com/white-label-platform); [RMA 508(h)](https://legacy.rma.usda.gov/fcic/privatesector.html); [FCIC minutes May 2025](https://www.rma.usda.gov/sites/default/files/2025-08/FCIC%20Minutes-May%202025%20signed.pdf); [Business Wire, Sensible](https://www.businesswire.com/news/home/20250825060512/en); [PR Newswire, WeatherPromise](https://tools.prnewswire.com/en-us/live/20823/release/20260113EN61932); [Kalshi DLP program](https://help.kalshi.com/en/articles/15410219-liquidity-provider-program).

## Bias check: is this report leaning on PRF because PRF has the data?

The team's data, code and backtests (docs 04-24) are about PRF ranchers. Every new idea in this report was therefore judged against an incumbent with 75 years of measured payouts, out-of-sample HE and a working app. That can make new ideas look worse because they are less measured, not because they are worse. This section checks where that happened.

**Where the bias entered.**

1. **Demand frames differed.** Rancher willingness to pay (1.42x) comes from doc 24, where wealth is 1.25-4 times the month's insured value, a narrow frame. Every other segment was screened in a strict cash frame, about 100 times insured value for a restaurant, which by construction gives near-zero demand for small risks. Matched frames reverse the size comparison ([weather_demand_segment.csv](../../data/processed/weather_demand_segment.csv)):

   | Segment (national) | Annual profit lost to weather (firms × mean monthly loss × 12) | Premium, narrow frame, standalone |
   |---|---|---|
   | Restaurants | about $3.2B | $39M |
   | Construction (≥ 20 staff) | $0.79B | $17M |
   | Golf | $0.67B (swing above a normal month) | $74M |
   | Bars | $0.30B | $3.5M |
   | Snow-belt cities | $0.28B (overrun above a normal month) | $15M |
   | **Ranchers near Kalshi stations, Companion months** | **$0.20B** | **$14M** |
   | Wet side total | | $134M |

   The rancher row covers only the 5,816 eligible PRF policies near the 11 Kalshi stations, so it is not the national rancher loss. It is, however, the market the Companion can actually serve.
2. **New segments were judged as the rancher's counterparty.** Restaurants were dismissed partly because they balance ranchers only 1:15 at the ranchers' own stations. That is a fact about netting, not about whether a restaurant product is a business. Frame-matched, the wet:dry ratio at those stations is about 1:3, where a 3:1 dry-to-wet book keeps about 62% of the netting benefit ([netting_quant.md](../research/expansion_notes/netting_quant.md)).
3. **The criteria favor what the team already built.** "Time to proof" asks what can be shown by December 15 with existing code. Only farm hedges have measured out-of-sample HE, and unmeasured hedge quality was capped at 3.

**Where it did not.** Several negative verdicts on new ideas rest on measured facts, not on missing data:
- **Restaurants and venues:** Kalshi lists no daily dinner-hour or day-count contract. A monthly ladder explains a median 27% of a venue's payout and a daily strip 53%. Restaurants are not eligible contract participants, so a product for them needs a licensed carrier.
- **Solar:** a listed rain contract removes 9% of a plant's winter energy variance (measured).
- **International bridge insurance:** Kalshi restricts the target countries, and tickets sit 60 times below its wire minimum.
- **Ski resorts:** about $300 of volume, and self-settlement on resort reports.
- **The south-central rain pairing on an own book:** El Niño wet calls pay 1.35x (December 1.89x).

**Result.** The bias check reruns the head-to-head without the time-to-proof criterion and with six frame-matched score changes, listed with their reasons in the AUTO section below and in [expansion_strategy_overrides.csv](../../data/processed/expansion_strategy_overrides.csv).
- **The on-exchange two-sided maker rises from #6 to #2.** This is the user's original idea, farmers buying no-rain and venues buying yes-rain, in the one form that needs no insurance license. With frame-matched flow, about a third of its dry book at the rancher stations pairs and nets under Kalshi's directional collateral return.
- **The rancher Companion falls from #8 to #10.** Its market is a tenth of the wet side's.
- **Restaurants rise from #13 to #11.** They stay low because of the missing contract and the carrier requirement, not because of missing data.
- **508(h) stays first.** It is PRF-adjacent, but its lead comes from the subsidized delivery channel and from not needing Kalshi depth, not from data volume. It is also a different project from a Kalshi product.

These overrides correct one identified bias in one direction. They are not a full re-score: scores that may favor new ideas, such as the snow Companion's unmeasured hedge quality, were left alone.

**What this changes.** The new sectors are not "not worth it". They hold the larger weather losses and the larger frame-matched demand. What they lack is:
- a listed contract shaped like their loss: daily dinner-hour rain, wet-day counts, irradiance;
- a channel that reaches them: POS and booking platforms, carriers;
- a counterparty: the market maker.

All three are things the recommended combination builds: fix the menu, sell the engine, seed the book. The rancher work is the proof of method, not the market.

## Head-to-head comparison

The scoring matrix above ranks weather segments. This section ranks strategies, meaning ways the team could make money. It covers 17 strategies on nine criteria:
- the first pass's shortlist and the options it parked;
- the second pass's new candidates;
- three added by the logic review: contract designs sold to Kalshi, a hay-dealer supply contract, and a snow Companion for contractors.

The scores and their one-line evidence are in [expansion_strategy_scores.csv](../../data/processed/expansion_strategy_scores.csv). `scripts/run_expansion_compare.py` does the rest. After the logic review the comparison has a ninth criterion, liquidity, which asks whether a strategy can execute at today's Kalshi depth or does not need that depth. Several scores were also changed to apply the criteria consistently; the reasons are in [logic_review_argument.md](../research/expansion_notes/logic_review_argument.md).

The main ranking uses a weak-link score, a weighted geometric mean. It is only a mild extra penalty on low scores: a 1 instead of a 3 on a 0.10-weight criterion multiplies the score by 0.90. It is not a gate, so the additive score is shown beside it. The long-run rank drops the Dec 15 "time to proof" criterion.

The scores are judgment, so the script reruns the ranking 20,000 times. Each run moves every weight by about ±0.05. Judgment scores move by ±1 with probability 0.4, and measured ones (hedge quality, market size, liquidity) with probability 0.2. A second check draws the weights uniformly. Two caveats:
- These percentages measure how robust the ranking is to the team's scoring, not the odds of commercial success.
- The noise is independent across strategies, but the leaders share facts (the Companion HE, the 27% already-insured share), so a shared error would move them together.

<!-- BEGIN AUTO: head-to-head comparison (scripts/run_expansion_compare.py) -->

Scores (1-5, 5 = best) with base weights in the header. Weak-link = weighted geometric mean; additive = weighted mean; long-run = weak-link without the Dec 15 time-to-proof criterion. P(first) and P(top 3) come from 20,000 draws of weights around the base and ±1 score noise; "any weights" draws weights uniformly. They measure robustness to the team's scoring, not odds of commercial success.

| # | Strategy | Demand evidence (0.16) | Market size (0.10) | Hedge quality (0.12) | Legal path (0.13) | Capital light (0.09) | Pricing risk (0.09) | Time to proof (0.10) | Defensibility (0.09) | Liquidity (0.12) | Weak-link | Additive | P(first) | P(top 3) | P(top 3), any weights | Long-run rank |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | USDA 508(h) endorsement for PRF (drought-weighted intervals) | 2 | 3 | 3 | 5 | 3 | 4 | 1 | 4 | 5 | **3.01** | 3.32 | 29% | 58% | 52% | 1 |
| 2 | Structuring and pricing software for parametric MGAs and carriers | 2 | 2 | 4 | 4 | 5 | 4 | 3 | 2 | 3 | **3.01** | 3.17 | 18% | 50% | 46% | 2 |
| 3 | Snow Companion for per-push plow contractors and salt distributors (listed monthly snow) | 3 | 2 | 3 | 4 | 5 | 3 | 3 | 3 | 2 | **2.98** | 3.09 | 14% | 46% | 37% | 3 |
| 4 | Embedded consumer weather guarantees (bookings, events, tee times) | 5 | 4 | 4 | 2 | 2 | 3 | 2 | 1 | 4 | **2.86** | 3.16 | 14% | 36% | 27% | 4 |
| 5 | Sell contract designs and demand data to Kalshi (seasonal strip, PRF-grid index, day count) | 2 | 1 | 4 | 5 | 5 | 4 | 4 | 2 | 2 | **2.83** | 3.18 | 8% | 27% | 31% | 8 |
| 6 | Two-sided Kalshi quoting per station-month (collateral-netted, ENSO-aware) | 2 | 2 | 3 | 5 | 3 | 2 | 3 | 2 | 4 | **2.78** | 2.94 | 3% | 18% | 15% | 5 |
| 7 | Zero-basis weather promotions settled at Kalshi stations | 3 | 1 | 3 | 3 | 4 | 4 | 4 | 3 | 2 | **2.77** | 2.96 | 5% | 21% | 23% | 10 |
| 8 | Lender- or buyer-financed Companion (farmer holds hedge; financier fronts premium) | 3 | 3 | 3 | 3 | 5 | 3 | 3 | 3 | 1 | **2.75** | 2.94 | 5% | 19% | 26% | 7 |
| 9 | Hay dealer or auction barn sells rain-indexed supply contracts and lays off the residual on Kalshi | 2 | 2 | 3 | 3 | 3 | 3 | 2 | 4 | 3 | **2.66** | 2.73 | 1% | 8% | 11% | 6 |
| 10 | City snow book on an insurance (MGA) balance sheet | 3 | 2 | 4 | 2 | 2 | 3 | 2 | 2 | 4 | **2.61** | 2.73 | 1% | 6% | 7% | 9 |
| 11 | Ranchers against ERCOT solar owners on an MGA book | 3 | 4 | 2 | 2 | 2 | 3 | 3 | 1 | 4 | **2.52** | 2.70 | 1% | 6% | 10% | 11 |
| 12 | Lender holds hedges on its own loan book (old #1) | 1 | 2 | 4 | 3 | 4 | 3 | 4 | 3 | 2 | **2.52** | 2.77 | 1% | 6% | 16% | 12 |
| 13 | Restaurant dinner-rain cover through POS or booking partner | 2 | 3 | 3 | 2 | 2 | 3 | 2 | 2 | 2 | **2.27** | 2.31 | <1% | <1% | 1% | 13 |
| 14 | Ski resort low-snow hedges on resort-reported series | 2 | 1 | 3 | 3 | 4 | 3 | 2 | 2 | 1 | **2.10** | 2.30 | 0% | <1% | <1% | 14 |
| 15 | Retail routing of hedgers to Kalshi (introducing broker) | 2 | 2 | 3 | 2 | 4 | 3 | 2 | 1 | 1 | **2.00** | 2.18 | 0% | 0% | <1% | 15 |
| 16 | South-central winter rain pairing on an own book | 1 | 2 | 3 | 2 | 2 | 1 | 2 | 3 | 3 | **1.92** | 2.08 | 0% | <1% | <1% | 16 |
| 17 | International smallholder bridge via an aggregator | 2 | 2 | 1 | 1 | 3 | 3 | 1 | 2 | 1 | **1.55** | 1.71 | 0% | 0% | <1% | 17 |

One of the top four ranks first in 76% of draws; all three top slots come from the top four in 19%.

Head to head among the top six: the chance the row strategy outscores the column strategy (weak-link).

| Row beats column | vs #1 | vs #2 | vs #3 | vs #4 | vs #5 | vs #6 |
|---|---|---|---|---|---|---|
| #1 USDA 508(h) endorsement for PRF (drought-weighted intervals) | – | 56% | 58% | 65% | 69% | 78% |
| #2 Structuring and pricing software for parametric MGAs and carriers | 44% | – | 52% | 60% | 67% | 73% |
| #3 Snow Companion for per-push plow contractors and salt distributors (listed monthly snow) | 42% | 48% | – | 59% | 65% | 72% |
| #4 Embedded consumer weather guarantees (bookings, events, tee times) | 35% | 40% | 41% | – | 54% | 62% |
| #5 Sell contract designs and demand data to Kalshi (seasonal strip, PRF-grid index, day count) | 31% | 33% | 35% | 46% | – | 58% |
| #6 Two-sided Kalshi quoting per station-month (collateral-netted, ENSO-aware) | 22% | 27% | 28% | 38% | 42% | – |

Why each strategy trails the leader (USDA 508(h) endorsement for PRF (drought-weighted intervals)): the largest weighted gaps, and where it beats the leader.

| Strategy | Loses most on | Beats the leader on |
|---|---|---|
| Structuring and pricing software for parametric MGAs and carriers | Liquidity (3 vs 5); Defensibility (2 vs 4); Legal path (4 vs 5) | Time to proof (3 vs 1) |
| Snow Companion for per-push plow contractors and salt distributors (listed monthly snow) | Liquidity (2 vs 5); Legal path (4 vs 5); Market size (2 vs 3) | Time to proof (3 vs 1) |
| Embedded consumer weather guarantees (bookings, events, tee times) | Legal path (2 vs 5); Defensibility (1 vs 4); Liquidity (4 vs 5) | Demand evidence (5 vs 2) |
| Sell contract designs and demand data to Kalshi (seasonal strip, PRF-grid index, day count) | Liquidity (2 vs 5); Market size (1 vs 3); Defensibility (2 vs 4) | Time to proof (4 vs 1) |
| Two-sided Kalshi quoting per station-month (collateral-netted, ENSO-aware) | Pricing risk (2 vs 4); Defensibility (2 vs 4); Liquidity (4 vs 5) | Time to proof (3 vs 1) |
| Zero-basis weather promotions settled at Kalshi stations | Liquidity (2 vs 5); Legal path (3 vs 5); Market size (1 vs 3) | Time to proof (4 vs 1) |
| Lender- or buyer-financed Companion (farmer holds hedge; financier fronts premium) | Liquidity (1 vs 5); Legal path (3 vs 5); Pricing risk (3 vs 4) | Time to proof (3 vs 1) |
| Hay dealer or auction barn sells rain-indexed supply contracts and lays off the residual on Kalshi | Legal path (3 vs 5); Liquidity (3 vs 5); Market size (2 vs 3) | Time to proof (2 vs 1) |
| City snow book on an insurance (MGA) balance sheet | Legal path (2 vs 5); Defensibility (2 vs 4); Liquidity (4 vs 5) | Demand evidence (3 vs 2) |
| Ranchers against ERCOT solar owners on an MGA book | Legal path (2 vs 5); Defensibility (1 vs 4); Hedge quality (2 vs 3) | Time to proof (3 vs 1) |
| Lender holds hedges on its own loan book (old #1) | Liquidity (2 vs 5); Legal path (3 vs 5); Demand evidence (1 vs 2) | Time to proof (4 vs 1) |
| Restaurant dinner-rain cover through POS or booking partner | Legal path (2 vs 5); Liquidity (2 vs 5); Defensibility (2 vs 4) | Time to proof (2 vs 1) |
| Ski resort low-snow hedges on resort-reported series | Liquidity (1 vs 5); Legal path (3 vs 5); Market size (1 vs 3) | Time to proof (2 vs 1) |
| Retail routing of hedgers to Kalshi (introducing broker) | Liquidity (1 vs 5); Legal path (2 vs 5); Defensibility (1 vs 4) | Time to proof (2 vs 1) |
| South-central winter rain pairing on an own book | Legal path (2 vs 5); Pricing risk (1 vs 4); Liquidity (3 vs 5) | Time to proof (2 vs 1) |
| International smallholder bridge via an aggregator | Legal path (1 vs 5); Liquidity (1 vs 5); Hedge quality (1 vs 3) | – |

Bias check (data-neutral view): the ranking without the time-to-proof criterion and with the frame-matched overrides in [expansion_strategy_overrides.csv](../../data/processed/expansion_strategy_overrides.csv).

| Override | Score | Reason |
|---|---|---|
| Restaurant dinner-rain cover through POS or booking partner: Demand evidence | 2 → 3 | Loss is measured (rain cuts diners 4.4%; about $3.2B a year of profit nationally, the largest weather-loss pool found). Its demand was scored in the strict cash frame while ranchers were scored in the narrow frame |
| Restaurant dinner-rain cover through POS or booking partner: Market size | 3 → 4 | Frame-matched (narrow) premium $39M a year against ranchers' $14M |
| South-central winter rain pairing on an own book: Demand evidence | 1 → 2 | Frame-matched wet:dry at the rancher stations is about 1:3, not 1:80 |
| Two-sided Kalshi quoting per station-month (collateral-netted, ENSO-aware): Demand evidence | 2 → 3 | Frame-matched wet:dry about 1:3, so a two-sided quoter at the rancher stations sees real flow on both sides |
| Two-sided Kalshi quoting per station-month (collateral-netted, ENSO-aware): Capital light | 3 → 4 | At 1:3 rather than 80:1, about a third of the dry book pairs and nets under directional collateral return |
| Lender- or buyer-financed Companion (farmer holds hedge; financier fronts premium): Market size | 3 → 2 | Rancher demand is $14M frame-matched, a tenth of the $134M wet side; ranchers looked large only because they were scored in a different frame |

| Data-neutral rank | Strategy | Main rank | Weak-link (neutral) | P(first) | P(top 3) |
|---|---|---|---|---|---|
| 1 | USDA 508(h) endorsement for PRF (drought-weighted intervals) | 1 | 3.41 | 60% | 85% |
| 2 | Two-sided Kalshi quoting per station-month (collateral-netted, ENSO-aware) | 6 | 3.04 | 8% | 45% |
| 3 | Structuring and pricing software for parametric MGAs and carriers | 2 | 3.01 | 7% | 41% |
| 4 | Snow Companion for per-push plow contractors and salt distributors (listed monthly snow) | 3 | 2.98 | 6% | 35% |
| 5 | Embedded consumer weather guarantees (bookings, events, tee times) | 4 | 2.97 | 13% | 44% |
| 6 | Hay dealer or auction barn sells rain-indexed supply contracts and lays off the residual on Kalshi | 9 | 2.75 | 1% | 10% |
| 7 | Sell contract designs and demand data to Kalshi (seasonal strip, PRF-grid index, day count) | 5 | 2.72 | 1% | 11% |
| 8 | City snow book on an insurance (MGA) balance sheet | 10 | 2.69 | 1% | 8% |
| 9 | Zero-basis weather promotions settled at Kalshi stations | 7 | 2.66 | 1% | 7% |
| 10 | Lender- or buyer-financed Companion (farmer holds hedge; financier fronts premium) | 8 | 2.61 | 1% | 5% |
| 11 | Restaurant dinner-rain cover through POS or booking partner | 13 | 2.55 | <1% | 3% |
| 12 | Ranchers against ERCOT solar owners on an MGA book | 11 | 2.47 | <1% | 3% |
| 13 | Lender holds hedges on its own loan book (old #1) | 12 | 2.39 | <1% | 1% |
| 14 | South-central winter rain pairing on an own book | 16 | 2.17 | <1% | <1% |
| 15 | Ski resort low-snow hedges on resort-reported series | 14 | 2.11 | 0% | <1% |
| 16 | Retail routing of hedgers to Kalshi (introducing broker) | 15 | 2.00 | 0% | <1% |
| 17 | International smallholder bridge via an aggregator | 17 | 1.63 | 0% | 0% |

Full matrix: [expansion_compare_h2h.csv](../../data/processed/expansion_compare_h2h.csv); scores and justifications: [expansion_strategy_scores.csv](../../data/processed/expansion_strategy_scores.csv); figure: [expansion_compare.png](../figures/expansion_compare.png).

<!-- END AUTO: head-to-head comparison (scripts/run_expansion_compare.py) -->

**What the comparison says.**

- **No winner, a loose pack of five.** 508(h), structuring software, the snow Companion, consumer-embedded guarantees and contract design for Kalshi score 3.01 down to 2.83 on the weak-link score. Each ranks first in 8-29% of draws. Head to head, the leader beats the others only 56-69% of the time. The ordering inside the pack is not meaningful.
- **What separates the pack from the rest is structure, not weather.** None of the five holds weather risk on the team's balance sheet, and each targets an existing institution: RMA, MGAs and carriers, contractors, booking platforms, the exchange. None of those institutions has been asked.
- **The long run favors 508(h).** Without the course deadline, it is first in 63% of draws. It fixes the 1.8x subsidy gap and does not depend on Kalshi depth. It also uses neither Kalshi nor airport stations, so it is a different project built on this research, not an extension of the Kalshi product.
- **Own-book pairings rank #10 or lower.** These are the city snow book (#10), solar (#11) and the south-central rain pairing (#16). They need an insurance balance sheet, which costs them on both capital and legal path. That counts one fact twice, with combined weight 0.22, and it is a known bias of this scoring. The wet side then either barely exists (the rain pairing) or is badly served by listed contracts (solar).
- **The rancher Companion falls to #8 once depth is scored.** Financed or not, ranchers' NO orders would fill 0.3% of modeled demand at the November 2 book. The Companion needs a seller of NO: an on-exchange maker (#6) or outside capital quoting in the same events. That makes the maker a precondition for the rancher product, not an alternative to it. Together they are the "seed the book" piece of the combination.
- **The old #1 falls to #12.** A lender holding its own book scores 1 on demand evidence. It still has the best measured HE.
- **The snow Companion is the surprise.** It is the same capital-light, single-side play as the rancher Companion. It sells listed monthly snow contracts to per-push plow contractors and salt distributors, who lose in mild winters. It faces no subsidized competitor, and Demex already sells low-snow cover to the same buyers. Its contractor HE has not been measured, and the December snow books are about $10K deep.

## Ranked combinations: fix the menu, sell the engine, seed the book

The pack is not a set of rivals. Its members share one research base and engine (docs 21-24), and each answers a different failure this report found:
- the menu: one month at a time, airport-settled, no day counts;
- the subsidy gap;
- the thin book;
- no legal route to holding risk.

**1. Fix the menu: contract designs for Kalshi, and a 508(h) submission for RMA.** One package of evidence goes to two buyers.

For Kalshi:
- A Nov-Feb seasonal strip listed before PRF's December 1 close. It fixes the lock-in and ENSO-timing problem.
- A contract settled on the NOAA CPC grid index that PRF uses. It removes station-to-farm basis, the project's original failure.
- A wet-day count, which fixes the venue R² of 0.27.

Kalshi lists 536 weather series, so it is willing to list. The risk is that new listings do not trade, as with Saskatchewan.

For RMA, a 508(h) drought-weighted interval rule. An approved concept proposal can get 50% of expected R&D costs advanced, per RMA's private-submission page, which could not be re-opened in the second pass ([RMA](https://legacy.rma.usda.gov/fcic/privatesector.html)). The concrete ask has to be more than "cover winter": subsidized winter intervals already exist, and Texas uses them. It would be a change to the per-interval caps or productivity factor for drought-weighted months. Texas winter loss ratios of 1.11 argue against cheaper winter cover, so the actuarial case needs work.

**2. Sell the engine: structuring and pricing software for parametric MGAs and carriers.** The customers are firms that hold weather books: Demex and Vortex in snow, Sensible-type guarantee carriers, and solar-volume hedge providers. The engine's differentiators are:
- out-of-sample HE;
- station-to-farm basis reports;
- book-level HE (pooled 0.63-0.79 around one station);
- ENSO-conditional and recent-window pricing.

PRF insurers are a weaker customer than the first draft thought. They cannot price PRF, and they can cede risk to the federal Assigned Risk Fund cheaply. The red-team risk is that the engine's edge is Kalshi-specific, while these carriers mostly write OTC.

**3. Seed the book: single-side Companions plus a maker on the other side.**
- **Ranchers.** A financier fronts the Companion's premium until sale, and the farmer holds the hedge. The pay-later lever worked best when the financier controlled the sale: 5% to 72% take-up in Kenya, against 8% to 24% in Ethiopia. So a hay dealer or auction barn may fit better than a bank. Four conditions:
  - Target ranchers who have not insured Nov-Feb.
  - Show the El Niño-conditional expectation; this winter's dry payout is about 0.66 of climatology.
  - Keep the hedge legally separate from PRF (RMA COM-26-003).
  - Get a counsel read on CTA and IB questions.
- **Snow contractors.** Per-push plow contractors and salt distributors buy listed monthly low-snow contracts at the settlement airport.
- **The maker.** An on-exchange two-sided quoter sells the NO the Companions need. Where wet buyers exist in the same event, it nets them under directional collateral return. It trades for its own account on a DCM, so it needs no registration. Its risk is adverse selection, because buyers can time ENSO. Paper-trade it against the December-February books before committing capital.
- **Launch timing.** Dry protection is worth least in this El Niño winter. It is worth most in the La Niña that often follows, when dry puts paid 1.49x climatology. A pilot that sells now most likely collects premium from ranchers who receive nothing, and index-insurance take-up falls after non-payout seasons. Build the channel and paper-trade this winter. Sell in the next La Niña autumn, with ENSO-conditional quotes, so the maker is not the side being adversely selected.

**Also in contention: embedded consumer guarantees (#4)** have the strongest demand evidence of any strategy: Sensible's 12-31% attach on camping and lodging bookings. They also need a carrier and face funded incumbents. Their most useful role for the team is as a software customer segment. **Zero-basis promotions (#7)** have zero settlement basis but are not zero-risk: the retailer's liability starts at announcement, weeks before the daily market lists, and the hedge is forecast-priced once it does.

**Second tier: insurance-paper books.** The city snow book (#10) remains the best two-sided book, for the reasons the first pass gave:
- February nets best (1.65 per premium).
- Last-15-year or payout-trend pricing restores the 20% load.
- Boston ran about $47M over its snow budget ([GBH](https://www.wgbh.org/news/politics/2026-03-30/boston-projects-48m-budget-deficit-next-fiscal-year-driven-by-snow-removal-costs)).
- Compass Minerals' salt sales fell 15% in a mild quarter ([Compass 10-K](https://www.sec.gov/Archives/edgar/data/0001227654/000122765416000082/cmp-20151231x10k.htm)).

It needs a carrier and a reinsurer, which is the Demex model. The rancher-solar pair (#11) fits on region, months and counterparty size but has the wrong index. The hay-dealer supply contract (#9) is the most natural pairing found: hay sellers gain in drought and already sell to ranchers. It has no precedent and an unchecked commodity-law status.

Drop or park:
- **Restaurants through POS (#13).** At 2% take-up they are a separate wet-side business in rainy metros, not the rancher's counterparty.
- **Ski resorts (#14).**
- **Retail routing (#15).** Kalshi already reaches all 50 states through Coinbase and Robinhood.
- **The south-central rain pairing on an own book (#16).** The wet side runs 1:80 to 1:3 against ranchers depending on the wealth frame, and history-priced El Niño wet calls pay 1.35x (December 1.89x).
- **International retail bridge insurance (#17).**
- **Temperature and dairy books, hydro, wind and airlines.** Their indices and timescales do not match the listed contracts.

## Legal and business route: research and software first, own-account trading second, insurance paper last

1. **Now:**
   - Send the contract-design proposals to Kalshi and a 508(h) concept to RMA.
   - License structuring and pricing to entities that hold weather books.
   - Pitch the financed Companion to a lender, hay dealer or auction barn as distributors.

   None of this needs retail onboarding, routing registration or an insurance label. Two things need counsel before anything is charged for: the advisor's individualized recommendations (CTA), and a distributor recommending trades (CTA or IB).
2. **This winter:** paper-trade the on-exchange maker against the December-February books. Trading for the team's own account on a DCM needs no registration.
3. **Later, only if needed:** an MGA wrapper with a fronting carrier and reinsurer, for a two-sided book that cannot be netted on the exchange. That means the city snow book, cross-station pools or day-count wet sides. Arbol, Demex and Vortex all use this structure ([Reinsurance News](https://www.reinsurancene.ws/vortex-launches-parametric-snow-insurance/)).

Bilateral OTC swaps with individuals are out under the corrected ECP thresholds, and so is pooling ranchers' money without commodity-pool registration.

## How this report was checked

Six research tracks fed the first draft. Each is a note in [`docs/research/expansion_notes/`](../research/expansion_notes/):

- `uninsured_farmers.md`: US and international insurance gaps
- `hospitality_venues.md`: wet-side venue exposure
- `ski_snow.md`: snow and winter-temperature risk
- `other_sectors.md`: other weather-exposed sectors
- `market_maker_model.md`: business model and regulation
- `netting_quant.md`: the backtest in `scripts/run_expansion_netting.py`

Four independent reviews then challenged the draft:

| Review | What it changed |
|---|---|
| [review_products_models.md](../research/expansion_notes/review_products_models.md) | Added pay-at-harvest (Casaburi & Willis), lenders and co-ops as wholesale buyers, weather-contingent promotions, SaaS structuring, Blanket as a competitor, and the 508(h) route. These produced the new #1 and the pilot. It also updated Sensible's scale and added WeatherPromise. |
| [review_segments_geographies.md](../research/expansion_notes/review_segments_geographies.md) | Added dairy heat stress and feedlot mud. Showed that bad-weather winners sit on the farmer's side. Recast insurers and MGAs as wholesale counterparties. Found Kalshi's foreign temperature contracts and Australia's restricted status. |
| [review_data_design.md](../research/expansion_notes/review_data_design.md) | Reframed the netting gain as mostly diversification. Repriced the pools out of sample and demand-weighted them. Added walk-forward pricing, ENSO conditioning and adverse selection, the ladder-versus-day-count test, the ASOS gauge caveat and the exchange-collateral framing. This demoted the rain pairing and strengthened the snow book. |
| [review_risks_factcheck.md](../research/expansion_notes/review_risks_factcheck.md) | Corrected the ECP thresholds and Kalshi's menu (536 series, 36-city daily rain, resort-reported snow, Saskatchewan). Added TWC settlement and the missing-equals-zero rule, tampering, Vail self-settlement, and the CTA, commodity-pool, tax and litigation risks. |

A second pass (2026-11-20) added three new-lens tracks:
- [lens_counterparties_capital.md](../research/expansion_notes/lens_counterparties_capital.md): solar, harvest-season and drought-winner counterparties; capital supply; Kalshi collateral, APY and listing lead time; PRF insurers; golf attach rates.
- [lens_lender_reality.md](../research/expansion_notes/lens_lender_reality.md): lender charge-offs in droughts, FCA derivative rules, and lender-portfolio precedents.
- [lens_quant.md](../research/expansion_notes/lens_quant.md), with `scripts/run_expansion_lenses.py`: lender-book HE, ENSO in Kalshi prices, and solar.

I verified the collateral-return finding directly against Kalshi's help page and events API. Independent logic reviews on a separate model then checked the revised report; see section "Logic reviews".

The reviews' verification scripts are in [scripts/experiments/expansion_review/](../../scripts/experiments/expansion_review/). For this revision I re-ran `crosspair.py` and `daycheck.py`, which reproduced 1.79/1.77/1.75/1.79 and 0.53. I also independently reproduced the two-distant-puts baseline (1.96 against 1.76, worst year 3.50 against 2.16), whose original script `twocontract.py` was not committed.

## Next steps for the December 15 paper

The paper's arc stays the same: the problem, Milestone I's "no", the diagnosis, the Companion, and the liquidity limit. This research supplies the ending. The liquidity limit is a demand-aggregation problem. The cheapest aggregators are the parties that already finance or insure the farmer, used as distributors rather than risk holders. A cross-sector market maker saves capital, which is abundant, and Kalshi already nets same-event pairs. Every weather book has to be priced on recent climate and the current ENSO state.

| Step | What to do | Why it matters |
|---|---|---|
| 1 | Done (second pass): pooled HE 0.65-0.77 for 40 farms around one station, against 0.53-0.62 for the median farm (`run_expansion_lenses.py`). Next, run the β test on the Dec 2026-Feb 2027 books as they list (about Nov 26 onward). | Decides whether this winter's ENSO adverse selection is live and whether the on-exchange maker has an edge |
| 2 | Make pricing a parameter of `run_expansion_netting.py` (last-15, payout trend, detrended temperature, ENSO-conditional). Add the second-independent-contract baseline and out-of-sample, demand-weighted pools. Update `DEMO.md` with the second-pass numbers. | Replaces the first draft's in-sample framing in the project record |
| 3 | Add the ENSO-conditional expectation to the advisor, and an LFP offset to rancher demand. For the December β test, shrink the conditional climatology by region, use one implied mean per station and bootstrap stations. | Without these the advisor and the demand model overstate this winter's value to ranchers |
| 4 | Measure TWC-settled values against GHCN for a year of settled markets, and model the missing-equals-zero rule. | Checks the backtests against what contracts actually settle on |
| 5 | Cross-check the drift on nClimGrid cells around each station. | Separates gauge change from climate |
| 6 | Add a "differences from Blanket" paragraph. Get a counsel read on CTA and commodity-pool exposure for the advisor and the pooled-orders roadmap. Verify Kalshi's restricted list against the Member Agreement PDF. | Positioning and the main open legal questions |
| 7 | If time allows, hold three to five conversations with a Farm Credit association (as a distributor and premium financier, not a hedger), a Texas hay buyer or auction barn, a PRF insurer and a Northeast public-works office. | Demand for every non-farm segment remains unmeasured |
| 8 | Recompute rancher demand for ranchers who have not insured Nov-Feb, using the RMA interval shares (27% of Texas liability already sits there). | The $12.1M rancher demand is biased high |

## Logic reviews

Three independent reviewers on a separate model (Fable) checked the second-pass report: one on quantitative soundness, one on argument logic as a red team, one on sources. All three returned "sound with fixes". Their notes:
- [logic_review_quant.md](../research/expansion_notes/logic_review_quant.md);
- [logic_review_argument.md](../research/expansion_notes/logic_review_argument.md);
- [logic_review_sources.md](../research/expansion_notes/logic_review_sources.md).

What they changed:

| Review | Main findings | What changed in this report |
|---|---|---|
| Quantitative | The arithmetic and the Monte Carlo were reproduced exactly, but the readings were off. "Top three in almost every draw" was really 66%. The 1:80 wet:dry ratio compared different wealth frames. The "central" demand values sit near the top of their bands. The ENSO β test has almost no power. Weak-link is only a mild penalty, and the time-to-proof criterion decides 508(h)'s rank. | The headline was rewritten. Frame-matched 1:3 and Monte Carlo medians were added. The β-power caveat was added. Noise was tiered, a long-run ranking without the deadline added, and the solar and HE labels fixed. |
| Argument and red team | Five blockers: the headline claims and "bottom half" wording; the top strategies ignore depth, so the maker is a precondition; and lender "profits" was inference stated as fact. About ten first-pass leftovers. Inconsistent scores for legal path, promotions' hedge quality, 508(h) demand and software demand. New lenses: contract design for Kalshi, LFP, launch timing in La Niña, persistence, PRF agents as the channel, and hay dealers or auction barns as the natural opposite side. | A liquidity criterion was added and the scores re-applied. Three strategies were added (contract design, snow Companion, hay dealer). The lender language was softened. The combination became "fix the menu, sell the engine, seed the book", and La Niña launch timing was added. |
| Sources | 26 claims: 16 confirmed, 9 partly right, 0 wrong, 1 unverifiable. Corrections: listing lead time (start of month, not a day before); December listings (only NYC and Napa); CFC record income was 2022 only; the 80.7% real-estate share is from 2011; 12 CFR 615.5140 carries no "unsafe and unsound" language; the $800B citation; Nephila's nine-month figures; Sensible's attach rates are for camping and lodging, not golf. | All corrected in the text and numbers table. The 508(h) 50% advance is marked unverified. |

Not changed:
- **Persistence.** The rancher's loss is cumulative while the contract is monthly. It is noted here; HE against a monthly index does not see a run of dry months, and a cumulative-deficit contract needs months listed together, which is the contract-design proposal.
- **PRF agents as the channel.** They decide which intervals ranchers leave open and earn no commission on Kalshi. They are the likeliest sponsor or opponent and are added to the step 7 conversations.

## Conclusion

Both passes moved the center of gravity from risk-bearing to distribution, and the reviews moved it further. Netting opposite hedgers is real, but most of its capital saving is diversification any second contract provides. The capital it saves is abundant in reinsurance; what is scarce is capital in Kalshi's rain books and buyers to meet it. For same-station pairs, Kalshi nets collateral already. The lender, the first pass's #1 buyer, showed no drought losses to hedge in the episodes checked.

No single expansion wins on the evidence available. A loose pack leads, and every member of it sells the engine or changes the rules instead of holding weather risk. The combination that uses the pack's strengths is:
1. Take contract designs (a seasonal strip, a PRF-grid index, a day count) to Kalshi and a drought-weighted rule to RMA.
2. License the structuring engine to the carriers that hold weather books.
3. Seed the book with single-side Companions plus an on-exchange maker. Paper-trade it this winter and sell in the next La Niña.

The single most decision-relevant fact for this winter is not in the order book. It is the +2.46 ONI. A platform that quotes Texas winter rain on 75 years of climatology right now would be selling the wet side at roughly a quarter off, and more in December, to anyone who reads CPC's ENSO forecast. Whether Kalshi's own prices make that mistake is the question this winter's December books can begin to answer.

## Numbers table

| Number | Value | Source | Status |
|---|---|---|---|
| Kalshi cost vs subsidized PRF for same expected payout | about 1.8x | [docs/analysis/09_payout_comparison.md](09_payout_comparison.md); [08_replication_quality.md](08_replication_quality.md) | internal |
| Station-to-farm distance, study sites | 29-55 mi | [docs/00_OVERVIEW.md](../00_OVERVIEW.md) | internal |
| Companion holdout HE vs PRF intervals | 0.61 vs 0.23 | [docs/analysis/21_prf_companion.md](21_prf_companion.md) | internal |
| PRF acres insured, 2025 | 298M | [docs/research/02_how_farmers_buy_weather_insurance.md](../research/02_how_farmers_buy_weather_insurance.md) | internal |
| US farms in federal crop insurance, 2022; row-crop vs specialty | about 13%; 62% vs 9% | [USDA ERS](https://ers.usda.gov/data-products/charts-of-note/104817) | sourced |
| NAP basic coverage; payment cap | 50% yield / 55% price; $125,000 | [CRS R48245](https://www.everycrsreport.com/reports/R48245.html) | sourced |
| Ad hoc farm disaster aid, FY2018-FY2025 | almost $40B | [CRS IF12101](https://www.everycrsreport.com/reports/IF12101.html) | sourced |
| African smallholders insured | about 1.3%, updated to about 3.5%, of 51M | [EDE review](https://www.cambridge.org/core/product/6FB330C15BEE881A0358E1159DFF3199/core-reader) | sourced |
| Kilimo Salama uptake in Embu | under 10% | [Rural21](https://www.rural21.com/english/news/detail/article/weather-index-insurance-for-smallholder-farmers-insights-from-kenya.html) | sourced |
| India rainfall insurance price elasticity | −0.66 to −0.88 | [Cole et al. 2013](https://dash.harvard.edu/server/api/core/bitstreams/7312037d-6130-6bd4-e053-0100007fdf3b/content) | sourced |
| Pilot index-insurance loads | "well above 50 percent" | [UC Davis i4](https://i4.ucdavis.edu/node/2481) | sourced |
| Take-up, upfront vs pay-at-harvest; with 30% discount | 5% vs 72%; about 6% | [Casaburi & Willis 2018](https://www.aeaweb.org/doi/10.1257/aer.20171526) | sourced (experiment dates unverified) |
| RCC vs traditional loan uptake, Kenya | 80% vs 20% (3ie); 40% vs 30% (IFPRI 2017) | [3ie](https://www.3ieimpact.org/sites/default/files/2025-07/TW13.1028-IE-brief.pdf); [IFPRI](https://ifpri.org/wp-content/uploads/2019/07/fly_2017_rcc_v3_web.pdf) | sources conflict |
| JCCUL smallholder borrowers | about 100,000 | [Intelligent Insurer](https://www.intelligentinsurer.com/news/munich-re-howden-skyline-tie-up-to-develop-new-parametric-hurricane-cover-29176) | sourced |
| Kalshi restricted jurisdictions | 55, incl. India (June 2026); Kenya, Ethiopia, Australia, Canada per secondary list | [Cointelegraph](https://cointelegraph.com/news/kalshi-adds-india-restricted-jurisdictions?rand=6792); [Datawallet](https://www.datawallet.com/crypto/kalshi-restricted-countries) | partly verified; PDF unread |
| NSW winter-crop growers with multi-peril cover | about 1% | [Deloitte](https://www.deloitte.com/au/en/Industries/consumer-products/perspectives/multi-peril-crop-insurance-australia-barriers-opportunities.html) | sourced (old, about 2015) |
| Saskatchewan Apr-Jul precip contract volume; quotes | $0; 0¢ bid / 99¢ ask | [Kalshi API](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXSKPRECPERIOD&status=open) | snapshot 2026-11-19 |
| Kalshi international wire minimum | $1,000 | [Kalshi Help](https://help.kalshi.com/en/articles/14026044-can-i-trade-on-kalshi-from-outside-the-united-states) | sourced |
| Côte d'Ivoire WFP premium / sum insured; ratio to wire minimum | $16 / $160; about 60x | [GIIF/WFP](https://docs.wfp.org/api/documents/WFP-0000154976/download) | sourced; ratio team computation |
| Capital95 / premium: one put; call; same-station pair | 3.57; 4.31; 1.74 | [expansion_netting_summary.csv](../../data/processed/expansion_netting_summary.csv) | backtest |
| Capital95 / premium: two puts >1,000 mi apart vs same-station pair (same station-pair-months) | 1.96 vs 1.76 | [review_data_design.md](../research/expansion_notes/review_data_design.md) §7.1 | backtest; reproduced for this report (2,943 station-pair-months; script not committed) |
| Worst year / premium: two distant puts vs same-station pair | 3.50 vs 2.16 | same | backtest; reproduced |
| Share of 3.57→1.74 drop explained by any second contract | about 85% | [review_data_design.md](../research/expansion_notes/review_data_design.md) | review computation |
| Cross-station pair capital95 by distance 0-50 / 50-100 / 100-200 / 200-300 mi | 1.79 / 1.77 / 1.75 / 1.79 | [crosspair.py](../../scripts/experiments/expansion_review/crosspair.py) | backtest; re-run for this report |
| Months both sides pay, cross-station 50-100 / 100-200 / 200-300 mi | 1.3% / 2.7% / 4.0% | same | backtest |
| rain_days pair capital95; collateral vs rain_total pair | 1.84; 5.68 vs 2.68 | [expansion_netting_summary.csv](../../data/processed/expansion_netting_summary.csv) | backtest |
| Snow / temp capital95 per premium, pair vs one side | 1.75 vs 3.32; 1.74 vs 4.14 | same | backtest |
| Snow station-months; stations | 43; 12 | same, `n_station_months`, `n_stations` | backtest |
| Dry-month correlation <100 mi; >1,000 mi | 0.54; about 0.00 | [expansion_netting_dry_corr.csv](../../data/processed/expansion_netting_dry_corr.csv) | backtest |
| Southern-tier mean pairwise winter-put corr; south-central vs SEA | 0.25 (12 stations); −0.34 | [review_checks_output.txt](../../scripts/experiments/expansion_review/review_checks_output.txt) §4 | backtest |
| National annual pools OOS capital95/prem: put / call / pair; call mean margin | 0.100 / 0.332 / 0.038; −0.002 | same, §1 | backtest (price 1951-95, realize 1996-2025) |
| National monthly pools OOS capital95/prem: put / pair | 0.552 / 0.379 | same, §1 | backtest |
| In-sample national monthly put / pair pool | 0.89 / 0.33 | [expansion_netting_pooling.csv](../../data/processed/expansion_netting_pooling.csv) | backtest (in sample) |
| South-central Nov-Feb pool capital95/prem; worst year | 1.32; +1.90 | [review_checks_output.txt](../../scripts/experiments/expansion_review/review_checks_output.txt) §5 | backtest (in sample) |
| Plains+West Apr-Sep pool; national equal-weight | 0.34; 0.13 | same | backtest (in sample) |
| Pooled OOS loss ratios (ratio of sums): put / call / pair | 1.028 / 1.203 / 1.116 | same, §1 | backtest |
| Median OOS loss ratios: put / call | 0.99 / 1.17 | same; [expansion_netting_summary.csv](../../data/processed/expansion_netting_summary.csv) | backtest |
| Placebo null 95% band for median call ratio; draws | 0.865-1.084; 300 | [review_checks_output.txt](../../scripts/experiments/expansion_review/review_checks_output.txt) §2 | backtest |
| Call loss ratio across split years 1980-2005 | 1.20-1.29 | same, §7 | backtest |
| Low-snow put / warm temp call OOS loss ratio (history-priced) | 1.27 / 2.02 | [expansion_netting_summary.csv](../../data/processed/expansion_netting_summary.csv) | backtest |
| ASOS tipping-bucket under-measurement | 2-10% | [NRC 2012](https://www.nap.edu/read/13216/chapter/13) | sourced |
| Walk-forward pair loss ratio, rain: all / last 15 / payout trend / detrended (put) | 1.09 / 1.05 / 1.02 / 1.08 (1.25) | [review_checks_output.txt](../../scripts/experiments/expansion_review/review_checks_output.txt) §3 | backtest |
| Walk-forward pair loss ratio, snow: all / last 15 / payout trend; last-15 put | 1.15 / 1.05 / 1.01; 1.12 | same, §3c | backtest |
| Walk-forward temp: all / last 15 / payout trend / detrended pair; detrended call | 1.18 / 1.14 / 1.10 / 1.06; 1.20 | same, §3b | backtest |
| ENSO seasons, 1951-2025: El Niño / La Niña / neutral | 20 / 18 / 38 | same, §4; [oni.txt](../../scripts/experiments/expansion_review/dl/oni.txt) | data |
| South-central put after La Niña / El Niño; call after El Niño | 1.49 / 0.66; 1.35 | [review_checks_output.txt](../../scripts/experiments/expansion_review/review_checks_output.txt) §4 | backtest (directional; 18-20 seasons) |
| Southeast put after La Niña; call after El Niño | 1.37; 1.48 | same | backtest |
| Wet call after El Niño: OKC / SAT / ABQ / TPA / DFW; TPA put after El Niño | 1.42 / 1.43 / 1.56 / 1.60 / 1.01; 0.37 | same | backtest |
| ENSO-timed buyer loss ratios | 1.17-1.64 | same | backtest |
| ASO 2026 ONI | +2.46 | [oni.txt](../../scripts/experiments/expansion_review/dl/oni.txt) (CPC) | data |
| R² of wet-weekend-day payout from monthly total (median; 10th-90th pct); all wet days | 0.27 (0.16-0.42); 0.44 | [review_checks_output.txt](../../scripts/experiments/expansion_review/review_checks_output.txt) §6 | backtest |
| R² of ≥0.10 / ≥0.25 in weekend-day payout from daily >0 strip | 0.53 / 0.38 | [daycheck.py](../../scripts/experiments/expansion_review/daycheck.py) | backtest; re-run for this report |
| Nov-Feb pair loss ratio, day-count (median) | 0.97 | [expansion_netting_station_month.csv](../../data/processed/expansion_netting_station_month.csv), months 11-2 | computed for first draft |
| MRMS Pass 2 latency | about 120 min | [NOAA MRMS](https://repository.library.noaa.gov/view/noaa/15285/noaa_15285_DS1.pdf) | sourced |
| Kalshi climate series; TWC / NWS / NOAA named sources | 536; 254 / 142 / 76 | [Kalshi API](https://api.elections.kalshi.com/trade-api/v2/series?category=Climate%20and%20Weather) | snapshot 2026-11-19, per review |
| KXRAIN daily cities; per-city daily rain series | 36; about 25 | [KXRAIN](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXRAIN&status=open) | snapshot, per review |
| Volume snapshots: NYC Nov rain; DEN Dec snow; Alta Dec snow | about $3.1K; about $10K; about $300 | [Kalshi API](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXRAINNYCM&status=open) | single snapshot |
| NWS staff lost / rehired | more than 600 / about 200 | [E&E News](https://www.eenews.net/articles/national-weather-service-in-transition-as-hurricane-season-begins/) | sourced |
| ECP thresholds: entity; individual | >$10M assets, or >$1M net worth hedging; >$10M invested, or >$5M hedging | [7 U.S.C. 1a(18)](https://www.law.cornell.edu/uscode/text/7/1a) | sourced |
| IB registration time | 3-6 months | [KPMG 2025](https://kpmg.com/kpmg-us/content/dam/kpmg/pdf/2025/current-state-prediction-markets.pdf) | single source |
| Kalshi block trade minimum | 25,000 contracts, ECPs only | [Business Insurance](https://www.businessinsurance.com/prediction-markets-gain-role-in-risk-transfer/) | sourced |
| Firms that had used weather derivatives, 2008 | about 1 in 10 | [CME 2008](https://www.cmegroup.com/media-room/press-releases/2008/4/29/survey_finance_executivessayglobalclimatechangewillrequirechange.html) | sourced |
| NJ cert petition filed | 2026-09-02 | [The Block](https://theblock.co/news/regulation/2026-09-02-new-jersey-asks-supreme-court-to-decide-who-regulates-sports-betting-on-prediction-markets-413398) | sourced |
| CFTC proposed event-contract rule | 2026-06-10 | [WilmerHale](https://www.wilmerhale.com/en/insights/client-alerts/20260618-10-takeaways-from-the-cftc-event-contracts-proposed-rulemaking) | sourced |
| Sensible guarantees sold; partners | more than 1M; more than 8,000 | [Business Wire, Aug 2025](https://www.businesswire.com/news/home/20250825060512/en) | company claim |
| WeatherPromise Series A | $12.8M (Jan 2026) | [PR Newswire](https://tools.prnewswire.com/en-us/live/20823/release/20260113EN61932) | sourced |
| Weather promotion pricing | 1.5-5.5% of promoted sales | [CNN Money 2010](https://money.cnn.com/2010/12/30/smallbusiness/snow_jewelry_full_refunds/) | unverified, old |
| Coeur d'Alene snow promotion | about $500K | [KREM](https://www.krem.com/article/news/local/coeur-dalene-jewelers-500k-snowfall-promotion-payout-approved-by-insurance/293-320eecff-b282-4ebd-9cad-a233269c203c) | sourced |
| Feedlot gain loss in 4-8 / 12-24 in. mud | about 14% / 25% | [K-State MF2673](https://bookstore.ksre.ksu.edu/download/how-feeding-site-mud-and-temperature-affect-animal-performance_MF2673) | sourced (old) |
| US dairy heat-stress losses | $1.2B/yr (2010 data) to about $1.65B/yr | [ERS](https://www.ers.usda.gov/amber-waves/2014/november/greater-heat-stress-from-climate-change-could-lower-dairy-productivity); [Food Ingredients First](https://www.foodingredientsfirst.com/news/heat-stress-dairy-ingredient-quality-cornell.html) | sourced; Cornell via news summary |
| Golf rounds lost per extra inch of monthly rain | about 2.2% | [NGF](https://www.ngf.org/wp-content/uploads/2026/08/July-2026-National-Rounds-Played-Report.pdf) | rule of thumb |
| QSR June comps, <5 vs >5 rainy days | +5.1% vs +3.5% | [QSR Web](https://www.qsrweb.com/news/rain-impacts-june-restaurant-sales/) | sourced |
| Boston snow overrun, 2025-26 | about $47M | [GBH](https://www.wgbh.org/news/politics/2026-03-30/boston-projects-48m-budget-deficit-next-fiscal-year-driven-by-snow-removal-costs) | sourced |
| Compass Minerals FY2015 salt sales | −15% to $849.0M | [Compass 10-K](https://www.sec.gov/Archives/edgar/data/0001227654/000122765416000082/cmp-20151231x10k.htm) | sourced |
| Snow pair capital95 by month, February | 1.65 | [expansion_netting_months.csv](../../data/processed/expansion_netting_months.csv) | backtest |
| 508(h) R&D advance after approved concept | 50% | [RMA](https://legacy.rma.usda.gov/fcic/privatesector.html) | sourced (legacy page) |
| LMSR worst-case subsidy | b·ln n | [Chen & Pennock](https://arxiv.org/pdf/1206.5252) | sourced |
| Scoring-matrix scores and totals | 1-5 per criterion | this report | team judgment, unweighted |
| Winter wet-side demand: construction modeled (see demand rows); feedlots and promotions | construction about $25k/yr national; feedlots and promotions not quantified | [weather_demand_segment.csv](../../data/processed/weather_demand_segment.csv) | model estimate; rest unverified inference |
| Demand model: station-based restaurant loss vs reservation study city-month means | median ratio 1.000 | `run_weather_demand.py` log | check |
| Demand model: exact CRRA vs CARA WTP multiple, max gap (25 restaurant rows) | 0.0004 | same | check |
| Restaurant hedge: HE at station, day-count / listed monthly total; HE for one firm | 0.69 / 0.57; 0.44 | [weather_demand_segment.csv](../../data/processed/weather_demand_segment.csv), `he_station`, `he_firm`; [weather_demand_city_month.csv](../../data/processed/weather_demand_city_month.csv) `he_listed_s` | model estimate |
| Firm-to-airport loss correlation ρ: restaurants / construction / golf / cities | 0.8 (0.6-0.9) / 0.8 (0.6-0.9) / 0.7 (0.5-0.85) / 0.85 (0.7-0.95) | `run_weather_demand.py` `P` | assumption |
| Restaurant wealth for the WTP screen (cash buffer + month's profit), median | about $81k | [weather_demand_city_month.csv](../../data/processed/weather_demand_city_month.csv) `wealth` | model (JPMC 16 days, NRA 2.8%) |
| Firm dispersion of risk aversion / wealth (sd of logs) | 0.7 / 1.0 | `run_weather_demand.py` `P` | assumption |
| Price multiple: standalone (Kalshi all-in) / embedded | 1.2 (1.1-1.6) / 1.3 (1.2-1.6) | doc 24; `run_weather_demand.py` | 1.2 internal; 1.3 assumption |
| Base take-up at fair price: standalone / embedded | 0.20 (0.10-0.35) / 0.45 (0.30-0.60) | [demand_inputs.csv](../../data/processed/demand_inputs.csv) (CME 10%, BI 35%, Ghana 40-50%) | assumption anchored on sources |
| Golf: facility revenue; contribution margin; cash (days of revenue) | $2.29M/yr; 0.7; 30 days | demand_inputs ($32B / 14,000); `run_weather_demand.py` | secondary; assumption; assumption |
| Construction: hedge-capable firms; cost per excess wet workday; revenue | 75,078 (8% of 938,478); $1,250 ($2,500 LD × 50% exposed); $8M | [demand_inputs.csv](../../data/processed/demand_inputs.csv); `run_weather_demand.py` | assumption |
| MLB: net share of lost revenue; club cash (one month of revenue) | 0.5 (0.4-0.7); $30M ($15-60M) | `run_weather_demand.py` | assumption |
| MiLB: loss scale vs MLB; clubs in Kalshi-23 metros | 0.068 (3,847 × $30 vs 29,816 × $57); 20% | [demand_inputs.csv](../../data/processed/demand_inputs.csv); [rain_venues.md](../research/expansion_notes/rain_venues.md) | assumption |
| City snow budgets: NYC / Chicago / Minneapolis / Denver / Philadelphia; others | $100M / $25M / $12M / $10M / $4.1M; $1-20M | [demand_inputs.csv](../../data/processed/demand_inputs.csv); `run_weather_demand.py` `SNOW_CITIES` | NYC, Chicago and Denver are assumption ranges; others assumption |
| Rancher policies near Kalshi stations: assumed state shares; eligible policies | TX 29%, OK 30%, MO 50%, FL 20%, CO 20%, NM 10% (× 0.8 with a package); 5,816 | `run_weather_demand.py` `RANCH`; [m2_companion_sweep.csv](../../data/processed/m2_companion_sweep.csv) (80% of grids within 60 mi get a package) | assumption |
| Demand, national standalone premium (P10 / central / P90): restaurants; bars; construction | $1k / $350k / $445k; $0.1k / $30k / $39k; $0.1k / $25k / $184k | [weather_demand_segment.csv](../../data/processed/weather_demand_segment.csv) | model estimate |
| Demand, national standalone premium: golf; MLB; MiLB | $1.3M / $12.1M / $25.1M; $9 / $812 / $3k; $208 / $6.5k / $18k | same | model estimate |
| Demand: wet rain total, national, standalone / embedded; Kalshi-23 standalone | $12.6M ($1.3-26.1M) / $16.1M; $3.2M ($0.3-6.7M) | same, `_wet_total` | model estimate |
| Demand: snow-belt cities (13), standalone / embedded | $1.6M ($0.15-3.3M) / $1.9M | same | model estimate |
| Demand: ranchers near Kalshi stations, standalone / embedded; wealth 4 per $ | $12.1M ($2.4-16.8M) / $23.5M ($3.1-29.4M); $7.7M | same | model estimate |
| WTP multiple, cash frame / narrow frame: restaurants; golf; cities; MLB; ranchers | 1.004 / 1.08; 1.04 / 1.42; 1.03 / 1.26; 1.003 / 1.04; 1.42 (doc 24 grid) | same, `wtp_multiple`, `wtp_multiple_narrow` | model estimate |
| Take-up standalone / embedded: restaurants; golf; cities; ranchers | 0.026% / 0.019%; 1.6% / 1.9%; 0.89% / 1.0%; 15.2% / 27.6% | same | model estimate |
| Narrow-frame national premium: restaurants / golf / construction / wet total | $39M / $74M / $17M / $134M | same, `premium_standalone_narrow` | model estimate (behavioral ceiling) |
| $1 contracts per station-month: restaurants / golf / cities / ranchers | 1,768 / 56,546 / 96,110 / 716,799 | same, `contracts_per_station_month_standalone` | model estimate |
| Wet:dry premium, shared stations Nov-Feb: standalone (P10-P90); embedded; narrow frame | 0.012 (0.0024-0.024); 0.007; 0.31 | same, `_wet_dry_ratio` | model estimate |
| Best-guess restaurant take-up (POS/booking-embedded dinner-rain cover) | 2% (1-5%) | team assumption: one fifth of the ~10% weather-derivative use among weather-sensitive firms ([demand_inputs.md](../research/expansion_notes/demand_inputs.md)) | assumption |
| Restaurant per-firm contract: expected payout / max payout per firm-month | $190 / $795 | [weather_demand_segment.csv](../../data/processed/weather_demand_segment.csv), `expected_payout_firm_month`, `max_payout_firm_month` | model estimate |
| Best-guess restaurant premium per buyer per year (1.2x) | $2,737 | $190 × 12 × 1.2 | model estimate |
| Best-guess restaurant demand, Kalshi-23 / national (1%, 2%, 5% take-up) | $2.9M / $7.2M; **$5.8M / $14.5M**; $14.5M / $36.2M a year | `firms` × take-up × $2,737, weather_demand_segment.csv | model estimate |
| Best-guess restaurant $1 contracts per month, Kalshi-23 (2%) | 1.68M (0.84M-4.20M) | `firms` × take-up × `max_payout_firm_month` | model estimate |
| Resting YES depth at restaurant demand stations, Nov 2 book | 98,607 contracts (best guess about 17x that) | [weather_demand_depth.csv](../../data/processed/weather_demand_depth.csv), `yes_depth_20261102` | internal |
| Best-guess restaurant vs rancher premium, shared stations Nov-Feb | $0.58M vs $8.8M, about 1:15 (1:6 at 5% take-up) | [weather_demand_city_month.csv](../../data/processed/weather_demand_city_month.csv), `firms × take-up × eh_firm × 1.2` (ranchers at take-up 0.1522) | model estimate |
| Households pay several times expected loss for low deductibles (small-stakes over-insurance) | qualitative | [Sydnor 2010, AEJ: Applied](https://www.aeaweb.org/articles?id=10.1257/app.2.4.177) | published, not re-read this session |
| November demand vs Nov 2 depth: wet 373,745 vs 98,607 YES; dry 6,192,536 vs 18,918 NO; fillable share | 11.7%; 0.31% | [weather_demand_depth.csv](../../data/processed/weather_demand_depth.csv) | model vs snapshot |
| Fillable share with the Oct 29 (rewards-on) book: wet / dry | 37% / 7.1% | same | model vs snapshot |
| Largest sensitivities (wet total, low / high case) | wealth frame $12.6M / $134M; price 1.6x / 1.1x $2.3M / $27.8M; γ 1 / 4 $4.4M / $28.4M | [weather_demand_sensitivity.csv](../../data/processed/weather_demand_sensitivity.csv) | model estimate |
| Golf monthly loss SD / cash; restaurant | 4.1%; 0.44% | [weather_demand_city_month.csv](../../data/processed/weather_demand_city_month.csv) `sd` / `wealth` | model estimate |
| Commercial-bank ag-production net charge-off rate: 2010 / 2011 / 2012 | 0.77% / 0.24% / 0.25% | [FRED CORLAGACBS](https://fred.stlouisfed.org/series/CORLAGACBS), via [lens_lender_reality.md](../research/expansion_notes/lens_lender_reality.md) | external |
| Capital Farm Credit net charge-offs 2011 / 2019-23; net income 2022 / 2023; real-estate-secured share 2011 / 2023 | 0.2% / 0.0% each year; $286M (record) / $270M; 80.7% / 72.9% | [CFC 2011](https://www.capitalfarmcredit.com/wp-content/uploads/2025/05/cfc-2011-annual-report.pdf), [CFC 2023](https://www.capitalfarmcredit.com/wp-content/uploads/2025/05/cfc-2023-annual-report.pdf) annual reports | external |
| Farm Credit System charge-offs during the 2012 drought | $500M to $236M | [FCA 2012 annual report](https://www.fca.gov/template-fca/download/AnnualReports/2012AnnualReport.pdf) | external |
| FCA: speculative or risk-increasing derivatives "unsafe and unsound" | qualitative | [FCA EM-61.3](https://ww3.fca.gov/readingrm/exammanual/New%20Exam%20Manual/61.3.pdf); FCA Bookletter BL-023 (named in EM-61.3); [12 CFR 615.5140](https://www.ecfr.gov/current/title-12/chapter-VI/subchapter-B/part-615/subpart-E/section-615.5140) limits eligible investments but does not contain the phrase | external |
| Ethiopia deferred-payment take-up | 8% to 24%, with high default | [J-PAL](https://www.povertyactionlab.org/print/pdf/node/4519?lang=en) | external |
| RMA: third party paying PRF premium for a share of indemnities is rebating | March 2026 | [RMA COM-26-003](https://www.rma.usda.gov/policy-procedure/bulletins-memos/informational-memorandum/com-26-003-rainfall-index-ri-pasture) | external |
| Lender-book HE, 40 grids around one station (LOYO): DFW / OKC / SAT / SGF, median farm to pooled | 0.60→0.75 / 0.53→0.65 / 0.55→0.68 / 0.62→0.77 | `data/processed/expansion_lens_*` from [run_expansion_lenses.py](../../scripts/run_expansion_lenses.py); [lens_quant.md](../research/expansion_notes/lens_quant.md) §1 | computed |
| 11-farm book HE: holdout equal / dollar weight; LOYO equal / dollar | 0.83 / 0.53; 0.83 / 0.75 (median farm 0.61 / 0.66) | same | computed |
| Basis-error correlation across farms at one station | 0.50-0.60 | same | computed |
| Kalshi monthly rain collateral return type | `DIRECNET` on all 37 monthly rain series (read as directional collateral return, opt-in; the meaning is inferred) | [Kalshi events API](https://api.elections.kalshi.com/trade-api/v2/events?series_ticker=KXRAINDALM&limit=3) (checked 2026-11-20); [Kalshi Help](https://help.kalshi.com/en/articles/13823816-collateral-return) | tag verified; meaning inferred |
| Kalshi APY on cash and open positions | 3.50% | [Kalshi Help](https://help.kalshi.com/en/articles/13823847-apy-on-kalshi), via [lens_counterparties_capital.md](../research/expansion_notes/lens_counterparties_capital.md) | external |
| Reinsurance capital; catastrophe-bond multiple 2024 / 2026 | about $800B (June 30, 2026); 3.71x / 2.4x expected loss | [Reinsurance News, Aon](https://www.reinsurancene.ws/record-800bn-reinsurance-capital-offers-insurers-growth-opportunities-heading-into-1-1-aon/); [Artemis](https://www.artemis.bm/news/as-cat-bond-loss-multiples-tighten-am-best-urges-investors-towards-greater-selectivity/) | external |
| Texas Nov-Dec + Jan-Feb PRF share of liability / premium (2025); loss ratio 2018-25 winter vs other intervals | 27.4% / 32.5%; 1.11 vs 1.02 | computed from [RMA Summary of Business](https://pubfs-rma.fpac.usda.gov/pub/Web_Data_Files/Summary_of_Business/state_county_crop/) files, lens_counterparties_capital.md | computed |
| AIP retained loss, Texas winter PRF in a 2025-type year (Commercial 100% / 35% / Assigned Risk Fund) | about $24M / $8M / $1M | computed from RMA SOB and [SRA 2027](https://www.rma.usda.gov/sites/default/files/2026-03/SRA_2027.pdf) | computed (inference-heavy) |
| Monthly rain listing lead time | median 0 days, often hours after the month begins (Nov 2026 listed weeks ahead); December 2026 events on Nov 20: NYC (opens Nov 27) and Napa only | Kalshi API metadata, lens_counterparties_capital.md | computed |
| ERCOT utility-scale solar | about 34 GW | [Cleanview / EIA-860M](https://www.cleanview.co/power-projects/operating/solar-farms/ercot) | external |
| Winter irradiance vs station rain anomaly correlation (5 stations) | −0.44 (all months −0.52) | NASA POWER, [lens_quant.md](../research/expansion_notes/lens_quant.md) §3 | computed |
| Solar winter energy variance removed: listed YES ladder / one rain call / zero-basis irradiance put on the plant's own index (LOYO) | 9% / 3% / 57% | same | computed |
| Rancher put + solar call: 95% capital, worst year; vs independent second put | 1.75, 2.00; vs 1.81, 3.08 | same | computed |
| ENSO tilt in the Nov 2026 Kalshi book (β, bootstrap interval); regressor reliability | −0.22 (−0.42 to 0.18); about 0.2 | lens_quant.md §2; [logic_review_quant.md](../research/expansion_notes/logic_review_quant.md) §5 | computed; test has almost no power |
| 2025-26 Brier, market vs climatology (all stations) | 0.131 vs 0.118-0.123 | same | computed |
| South-central El Niño-conditional wet-call payout, Nov / Dec | 0.95x / 1.89x climatology | same | computed |
| Sensible Weather attach rates on camping and lodging bookings (no golf rate public) | 12-31% (company figures) | lens_counterparties_capital.md (Business Wire, Issuu, TechCrunch) | external, company-reported |
| Head-to-head (17 strategies, 9 criteria): weak-link scores of the top five; P(first) range | 3.01-2.83; 8-29% | [expansion_compare_summary.csv](../../data/processed/expansion_compare_summary.csv) | computed from team scores (robustness to scoring, not odds of success) |
| P(one of the top four ranks first); P(all top three from the top four) | 76%; 19% | [expansion_compare_cluster.csv](../../data/processed/expansion_compare_cluster.csv) | computed from team scores |
| 508(h) P(first) without the time-to-proof criterion | 63% | expansion_compare_summary.csv, `p_first_longrun` | computed from team scores |
| Wet:dry premium, both sides in the narrow frame | 0.31 (about 1:3) | [weather_demand_segment.csv](../../data/processed/weather_demand_segment.csv), `wet_dry_premium_standalone` narrow row | model estimate |
| Monte Carlo medians (national, standalone): restaurants / golf / ranchers; wet:dry | $30k / $5.8M / $9.1M; 1:133 | [logic_review_quant.md](../research/expansion_notes/logic_review_quant.md) §4 (recomputed, seed 473, 400 draws) | model estimate |
| LFP payments FY2023 vs PRF 2023 indemnities | $1.78B (inflation-adjusted) vs $1.07B | [doc 02](../research/02_how_farmers_buy_weather_insurance.md), CRS R48082 | external |
| Annual profit lost to weather, national: restaurants / construction / golf / bars / snow cities / ranchers near Kalshi stations | $3.2B / $0.79B / $0.67B / $0.30B / $0.28B / $0.20B | [weather_demand_segment.csv](../../data/processed/weather_demand_segment.csv), `firms × loss_excess_mean_firm_month × 12` | model estimate |
| Frame-matched (narrow) premium: wet side total vs ranchers | $134M vs $14M | same, `premium_standalone_narrow` | model estimate |
| Data-neutral ranks: on-exchange maker / rancher Companion / restaurants (main view) | #2 / #10 / #11 (#6 / #8 / #13) | [expansion_compare_summary.csv](../../data/processed/expansion_compare_summary.csv), `rank_neutral` | computed from team scores and overrides |
