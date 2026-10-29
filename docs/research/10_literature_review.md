# Literature review and prior art: prediction-market weather contracts as farm rainfall hedges

**Proposal cell:** Milestone 1 / R7 (literature and prior art)  |  **Status:** VERIFIED 2026-10-29 (see Verification log)  |  **Last updated:** 2026-10-29

Companion file: [`references.bib`](references.bib) (BibTeX, one entry per citation, with DOI or URL and a
`note` field saying how each entry was verified). Citation keys such as `[luo2026]` below match that file.
PDFs we could download are in `data/raw/lit/` (gitignored).

## Key findings

- **The two closest papers both find that the contract is priced reasonably but pays on the wrong
  thing.** Luo (2026), on Kalshi daily *temperature* markets, finds a mean residual basis risk of 0.386
  across 30 station pairs, rising with distance, while the cost of building a degree-day payoff from
  Kalshi's binary bins is only about 1% of exposure variance [luo2026, abstract]. Iturbide (2026), on
  Kalshi's daily New York *rain* contract, finds it well calibrated (Brier 0.143 vs 0.146 for the NWS
  forecast) but 69% of its payouts fall on evenings with no business loss [iturbide2026, abstract and
  replication CSVs].
- **Neither paper studies monthly precipitation ladders, agriculture, gridded indices, or a government
  insurance benchmark.** Luo uses degree days and a station-to-station "customer proxy"; Iturbide uses
  one daily yes/no rain contract and reconstructed bar revenues. Our project (monthly "Above X inches"
  ladders vs the USDA PRF grid index, station grid vs farm grid) is not covered by either. (For Luo
  this rests on the abstract; the full text could not be accessed.)
- **The proposal's claim that "geographic and settlement differences create significant basis risk" is
  supported, but needs sharpening.** In Luo the dominant friction is geography. In Iturbide it is the
  settlement *window and definition* (whole day vs 6 p.m.-1 a.m.; trace counted or not). Re-scoring
  the same NYC days under the rule Kalshi adopted on 2026-07-15 (trace rain no longer counts) raises
  the payout-loss correlation from 0.44 to 0.55 [iturbide2026, `results/trigger_trace_rule.csv`].
- **Kalshi prices show a favorite-longshot bias that makes tail hedges expensive.** Across 313,972
  Kalshi contract prices (2021 to April 2025), contracts costing 10 cents or less lost over 60% of the
  money put into them on average; the average return was -20% before fees and -22% after fees; takers
  averaged -31.46% and makers -11.99% after fees [burgi2026, pp. 3, 18-19, 36]. The bias is also
  significant in the Climate & Weather category (Table 8, p. 25). A drought hedge on a monthly ladder is exactly such a
  low-price, low-probability contract.
- **Liquidity, not calibration, is likely the binding cost.** For the NYC daily rain contract the median
  bid-ask spread at the planned purchase time was $0.10 per $1 contract and the median open interest at
  that time was 2 contracts [iturbide2026, `results/price.csv`, `results/liquidity.csv`]. Our own team
  saw no bids, asks, or volume on the open Oct/Nov 2026 Dallas monthly rain markets (to be rechecked:
  this may partly reflect renamed API fields, see Implications item 4).
- **PRF basis risk is already large in the agricultural literature.** The probability that a producer
  has a forage loss but PRF pays nothing (the "false negative probability") is 26%-43% on Kansas and
  Nebraska ranches (model-based) [yu2019, p. 180, Table 5 p. 189]. On California rangeland it is
  31%-46% that one of the two insured intervals fails to pay a loss and 14%-25% that both fail
  [keller2022, abstract]. Across 176 Nebraska grids the chance that neither interval pays averages 12%
  (nearly 30% in several Sandhills cells) [belgacem2025, abstract]. Yu et al. find the index design
  itself (two-month grid index instead of on-ranch rain) adds only 5-9 percentage points; most basis
  risk comes from non-rain factors.
- **PRF interval choice is distorted by subsidies.** Several papers find producers increasingly insure
  non-growing-season (winter) intervals that raise rather than lower income risk, because subsidies
  and expected returns are higher there [goodrich2020; westerhold2018; cho2026aepp]. A market hedge has no
  subsidy, so any comparison with PRF must separate risk reduction from subsidy transfer.
- **The finance theory for our replication is old and solid.** Ross (1976) shows complex payoffs can be
  built from portfolios of simple options; Breeden and Litzenberger (1978) show option prices imply
  state prices; Carr and Madan (2001) state the strike-by-strike spanning formula (in the paper's
  body; standard knowledge, not in its abstract). A Kalshi "Above K"
  ladder is a discretized risk-neutral survival function, and the Federal Reserve's FEDS paper builds
  Kalshi densities by differencing adjacent strikes [diercks2026, p. 13].
- **Methods we can lift directly:** the local / geographic / product basis-risk decomposition
  [woodard2008]; false-negative and false-positive probabilities from a payout-loss contingency table
  [elabed2013; yu2019; iturbide2026]; Ederington hedging effectiveness and the effective loading
  "premium per dollar of useful payout" [ederington1979; iturbide2026]; Luo's geography-vs-binarization
  decomposition; out-of-sample hedge selection; and mean-variance / CVaR interval portfolios for the
  Milestone 2 optimizer [diersen2015; zapata2022; rockafellar2000].

## Numbers table

Verification labels: **CONFIRMED** = read in the primary source's full text or the authors' own
published results files; **CONFIRMED (abstract)** = read in the paper's official abstract (publisher,
Crossref deposit, arXiv, or repository page), full text not read, no page/table available;
**UNVERIFIED** = secondary source only; **DERIVED** = our arithmetic on confirmed inputs.
Verifier rule (2026-10-29): numbers that rest only on the author's abstract of an SSRN working paper
whose full text could not be opened (Luo, Shah, Krause, and the abstract-only Iturbide items) are
labeled **UNVERIFIED (abstract only)**. Abstracts of peer-reviewed articles, theses, and arXiv preprints
keep **CONFIRMED (abstract)**. Page numbers are the numbers printed on the page (for Burgi et al. the
printed page is the PDF page minus 2; for Diercks et al. the PDF page minus 1).

| Quantity | Value | Units | Region / period | Source (URL + page/table) | Verification |
|---|---|---|---|---|---|
| Luo: price observations analyzed | 287,909 | price observations | Kalshi daily weather (temperature) markets; dates not stated in abstract | [luo2026] https://doi.org/10.2139/ssrn.7138562 abstract | UNVERIFIED (abstract only) |
| Luo: resolved contracts | 15,994 | contracts | same | same | UNVERIFIED (abstract only) |
| Luo: station pairs in basis-risk map | 30 | settlement-station / customer-proxy pairs | US, 24 years of weather data | same | UNVERIFIED (abstract only) |
| Luo: trigger types | 2 | heating and cooling degree days | same | same | UNVERIFIED (abstract only) |
| Luo: mean residual basis risk | 0.386 | unitless (definition not visible in abstract) | 30 pairs, 2 triggers, 24 years | same | UNVERIFIED (abstract only) |
| Luo: share of cases where a multi-station portfolio beats the best single station out of sample | 43 | % of cases | same | same | UNVERIFIED (abstract only) |
| Luo: share of days realized temperature falls outside Kalshi's "8 degree F bin ladder" (the ladder spans 8 degree F; see Section 1.1) | 17 | % of days | warm-season sample | same | UNVERIFIED (abstract only) |
| Luo: binarization (replication) cost of a degree-day claim built from binary bins | ~1 | % of exposure variance | warm-season sample | same | UNVERIFIED (abstract only) |
| Luo: median increase in residual basis risk when the ideal index is replaced by the bin strip | +0.007 | unitless | daily-level joint decomposition | same | UNVERIFIED (abstract only) |
| Luo: implied-temperature bias (market-implied minus realized settlement value) | ~0 | degrees F | same | same | UNVERIFIED (abstract only) |
| Iturbide: season days analyzed, NYC | 355 | days (May 1-Sep 30) | NYC, seasons 2021, 2022, 2025, 2026 | [iturbide2026] repo `results/trigger.csv` (columns n, annees); abstract | CONFIRMED |
| Iturbide: days excluded for missing station data, NYC | 4 | days | same | repo `results/trigger.csv` (n_exclus_station) | CONFIRMED |
| Iturbide: Brier score, Kalshi price at noon the day before | 0.143 | Brier score (0 best) | NYC, 237 priced days | repo `results/price.csv` (brier_brier = 0.1430); abstract | CONFIRMED |
| Iturbide: Brier score, NWS MOS forecast, same days | 0.146 | Brier score | same | repo `results/price.csv` (brier_mos_brier = 0.1460); abstract | CONFIRMED |
| Iturbide: share of payouts on evenings with no loss (false positives) | 69 (95% CI 62-75) | % of payouts | NYC, 355 days; loss = at least 1 mm rain 6 p.m.-1 a.m. | repo `results/trigger.csv` (FP = 0.694, CI 0.625-0.753); abstract | CONFIRMED |
| Iturbide: P(contract pays) | 0.451 | probability per season day | NYC, 355 days | repo `results/trigger.csv` (P_Y) | CONFIRMED |
| Iturbide: P(lost evening) | 0.138 | probability per season day | NYC, 355 days | repo `results/trigger.csv` (P_D) | CONFIRMED |
| Iturbide: correlation of payout and loss | 0.442 (CI 0.392-0.498) | correlation | NYC, 355 days | repo `results/trigger.csv` (rho) | CONFIRMED |
| Iturbide: premium plus fee per dollar of useful payout | 2.75 (CI 2.14-3.60) | $ per $ of payout on a lost evening | NYC, 237 priced days | repo `results/price.csv` (Lambda = 2.754); abstract | CONFIRMED |
| Iturbide: false-positive share, old rule (trace counts as rain) vs new rule (trace excluded) | 0.694 vs 0.602 | share of payouts | NYC, 355 days, both rules applied to same days | repo `results/trigger_trace_rule.csv` (FP_A, FP_B) | CONFIRMED |
| Iturbide: payout-loss correlation, old vs new rule | 0.442 vs 0.550 | correlation | same | repo `results/trigger_trace_rule.csv` (rho_A, rho_B) | CONFIRMED |
| Iturbide: settlement rule change date (trace no longer counts) | 2026-07-15 | date | Kalshi rain markets | repo `preregistration.md` section 5; `src/02_trigger.py` (RULE_CHANGE) | CONFIRMED |
| Iturbide: median bid-ask spread at purchase time | 0.10 | $ per $1 contract | NYC, noon the day before | repo `results/price.csv` (spread_median = 0.0999) | CONFIRMED |
| Iturbide: mean bid-ask spread at purchase time | 0.249 | $ per $1 contract | same | repo `results/price.csv` (spread_moyen) | CONFIRMED |
| Iturbide: median daily volume | 3,226.66 | contracts per market | NYC | repo `results/liquidity.csv` (volume_median) | CONFIRMED |
| Iturbide: median open interest at purchase time | 2.0 | contracts | NYC, noon the day before | repo `results/liquidity.csv` (oi_achat_median) | CONFIRMED |
| Iturbide (verifier addition): raw loading lambda = mean price / P(pays) - 1 | -0.078 (CI -0.167 to 0.028) | share (0 = price equals payout frequency) | NYC, 237 priced days | repo `results/price.csv` (lambda) | CONFIRMED |
| Iturbide: maximum in-sample hedging effectiveness, current contract, no information | 0.195 | share of variance removed | NYC, 355 days | repo `results/optimal_program_bound.csv` (e_max_in) | CONFIRMED |
| Iturbide: same, under the no-trace (TWC) rule | 0.302 | share of variance removed | same | same | CONFIRMED |
| Iturbide: gain from counterfactual evening-window contract | 1-3 | % of revenue, worst-of-twenty season | 10 NYC venues | abstract; repo `results/hedge_perfect.csv` shows 0.8-3.4% for one setting (zero loading, old rule), exact setting behind "1 to 3" not identified | UNVERIFIED (abstract only) |
| Iturbide: fee formula used | 0.07 x p x (1 - p) | $ per contract, p = price in $ | Kalshi | repo `preregistration.md` section 2 | CONFIRMED |
| Iturbide: lost-evening definition | at least 1 mm rain, 18:00-01:00 local | mm; hours | NYC Central Park ASOS | repo `preregistration.md` section 2 | CONFIRMED |
| Iturbide: uncovered losses (loss but no payout) | 0 | share of lost evenings | NYC, 355 days | repo `results/trigger.csv` (UC) | CONFIRMED |
| Iturbide: bootstrap design | 7-day moving blocks, 5,000 draws | days; draws | all intervals | repo `preregistration.md` section 5 | CONFIRMED |
| Iturbide: hedging settings searched out of sample | 132 | settings | NYC 2025 vs 2026 | repo `preregistration_deviations.md` item 7; `src/06_hedge_kalshi.py` | CONFIRMED |
| Iturbide: 2022 contracts with other thresholds excluded | 126 | contracts | NYC 2022 | repo `preregistration_deviations.md` item 4 | CONFIRMED |
| Iturbide: secondary cities | 57 days each | days | Miami, Chicago, 2026 | repo `results/trigger.csv` | CONFIRMED |
| Iturbide: venues | 10 | rooftop bars (reconstructed revenue) | NYC | abstract; repo README ("the ten venues") | CONFIRMED |
| Maisashvili: best PRF coverage level in all Texas regions tested | 90 | % coverage level | selected Texas counties | [maisashvili2011] abstract (repository page) | CONFIRMED (abstract) |
| Burgi et al.: Kalshi sample | 46,282 contracts, 12,403 events, 313,972 prices | counts | Kalshi, 2021 to April 2025; volume at least $1,000; final spread at most 20 cents; hourly markets excluded | [burgi2026] pp. 10-11 (Section 3.1) | CONFIRMED |
| Burgi et al.: Kalshi fee | 0.07 x p x (1 - p), total rounded up to the next cent | $ per contract | Kalshi (as described by authors) | pp. 5, 18 | CONFIRMED |
| Burgi et al.: average loss on contracts costing 10 cents or less | over 60 | % of money invested | all categories | p. 3; p. 18; Figure 5 on p. 19 | CONFIRMED |
| Burgi et al.: average return, before fees / after fees | -20 / -22 | % | all contracts | p. 3; pp. 18-19 | CONFIRMED |
| Burgi et al.: fee on buying 100 contracts at 5 cents | 34 cents (almost 7% of cost) | $ and % | worked example; check: 0.07 x 0.05 x 0.95 x 100 = 33.25 cents, rounded up to 34 | p. 19 | CONFIRMED |
| Burgi et al.: average return, makers / takers | -11.99 / -31.46 | % (after fees) | all contracts | p. 36 (Section 5; Figure 11) | CONFIRMED |
| Burgi et al.: Mincer-Zarnowitz regression, Climate & Weather (profit = a + b x price) | b = 0.031 (SE 0.005); a = -0.997 (SE 0.243); N = 29,924 | regression coefficients (price and profit in cents: not stated in the table, implied by p. 20 and the size of the constants) | Kalshi Climate & Weather, 2021-Apr 2025 | Table 8, p. 25 | CONFIRMED |
| Implied break-even price in that regression (a + b x p = 0) | ~32 | cents | same | 0.997 / 0.031 = 32.2; same formula on the full sample gives 1.736 / 0.034 = 51 cents, matching the paper's statement that contracts above 50 cents earn small positive returns (p. 3) | DERIVED |
| Diercks et al.: example of strike differencing | 0.40 - 0.22 = 0.18 | probability for one bin | Fed funds Dec 2025 contract, July 22 2025 | [diercks2026] p. 13 | CONFIRMED |
| Yu et al.: false negative probability, rain-only yield model / PRF-index model | 21 / 26 | % | 3 university ranches, Kansas and Nebraska; ranch-level data, 42 obs | [yu2019] Table 5, p. 189 | CONFIRMED |
| Yu et al.: same with field-level BBR data | 33.9 / 42.7 | % | same, 118 obs | Table 5, p. 189 | CONFIRMED |
| Yu et al.: overall PRF basis risk range / index-related part | 26-43 / 5-9 | % / percentage points | Kansas and Nebraska | p. 180; pp. 189-190 | CONFIRMED |
| Keller and Saitone: area studied | nearly 63 million | acres of rangeland | California | [keller2022] abstract | CONFIRMED (abstract) |
| Keller and Saitone: false negative probability, one / both intervals fail to pay a loss | 31-46 / 14-25 | % | California rangeland | abstract | CONFIRMED (abstract) |
| Keller and Saitone: share of paid cases where indemnity is below the forage loss | 36 | % of indemnified cases | California | abstract | CONFIRMED (abstract) |
| Keller and Saitone: average indemnity shortfall | 1.74-2.73 | $ per acre | California | abstract | CONFIRMED (abstract) |
| Belgacem: grids and years | 176 grids, 1988-2023 | grids, years | Nebraska (abstract names the Sandhills) | [belgacem2025] abstract | CONFIRMED (abstract) |
| Belgacem: peak rainfall-forage correlation | 0.45 | correlation | same | abstract | CONFIRMED (abstract) |
| Belgacem: probability neither insured interval pays during a forage loss | 12 average; nearly 30 in several Sandhills cells; below 10 with the best late-spring + summer pair | % | same | abstract | CONFIRMED (abstract) |
| Goodrich et al.: policyholder data | Nebraska and Kansas, 2013-2017 | states, years | RI-PRF participants | [goodrich2020] abstract | CONFIRMED (abstract) |
| Cho and Diersen: period of rising non-production interval selection | 2013-2024 | years | South Dakota | [cho2026aepp] abstract | CONFIRMED (abstract) |
| Cho and ShalekBriski: data | 66 counties, 1948-2024; loss ratios for 43 states, 2016-2024 | counts, years | South Dakota; US | [cho2026afr] abstract | CONFIRMED (abstract) |
| Zapata et al.: out-of-sample test | 116 grids, 2018-2022; prediction error cut 5-14% | grids; % | Texas | [zapata2024] abstract | CONFIRMED (abstract) |
| Ifft et al.: effect of PRF availability on pasture values | at least +4 | % | US, field-level panel | [ifft2014] abstract | CONFIRMED (abstract) |
| Jensen et al.: covariate risk removed / share of original risk left | 63 / 69 | % | index-based livestock insurance, northern Kenya | [jensen2016] abstract | CONFIRMED (abstract) |
| Elabed et al.: demand drop from compound risk aversion / demand gain from multiscale contract | 13 percentage points / ~40% | pp / % | Mali cotton (simulation) | [elabed2013] abstract | CONFIRMED (abstract) |
| Leppert et al.: risk premium reduction from heat-index insurance / gain from interpolation over nearest station | 27-29 / 2-3 | % | corn, Illinois and Iowa | [leppert2021] abstract | CONFIRMED (abstract) |
| Vedenov and Barnett: crop reporting districts studied | 6 | districts | US corn, cotton, soybeans | [vedenov2004] p. 387 abstract | CONFIRMED |
| Crosier: Kalshi high-temperature market vs best public forecast (NBM) | beats NBM in 6 of 7 cities; pooled over all city-days, ~10% lower RMSE than the best single public forecast from the end of the first trading hour | count; % RMSE | 7 US cities, ~5 years | [crosier2026] abstract | CONFIRMED (abstract) |
| Shah: settled markets tested | 26,192 | markets | Kalshi sports and daily weather | [shah2026] abstract | UNVERIFIED (abstract only) |
| Shah: last-trade artifact, lowest price range | 16 won of 17,612, vs ~229 expected | markets | same | abstract | UNVERIFIED (abstract only) |
| Shah: pre-outcome re-test, MLB underdogs (not weather) | 40.6 win rate vs 42.6 average price (gap 2.0 points, p = 0.24) | % | 810 MLB games, 2026 | [shah2026] abstract | UNVERIFIED (abstract only) |
| Krause: unemployment longshots (price below $0.30) | bias -0.077; win rate 4.0% | probability points; % | 287 Kalshi contracts, Jul 2021-Mar 2026 | [krause2026] abstract | UNVERIFIED (abstract only) |
| Davis: mean grid-level PRF loss ratio, baseline enrollment / interval strategy chosen by rainfall uncertainty | 0.79 (SD 0.20) / 0.83 (SD 0.33) | indemnity / premium | US South, PRF policy years 2017-2024 | [davis2025sat] Southern Ag Today 5(46.1), text under Figures 1-2, https://sat-wp.afpc.tamu.edu/2025/11/10/understanding-interval-based-enrollment-risk-in-prf-how-interval-selection-strategies-can-impact-protection-across-the-south/ | CONFIRMED (extension column, not peer reviewed; not from the Davis et al. journal article) |

## Detail

### 1. The two closest papers

#### 1.1 Luo (2026), "Prediction Markets as Weather Hedges" [luo2026]

**Access.** SSRN's PDF and abstract pages returned HTTP 403 (Cloudflare bot check) on 2026-10-29, and
no other copy (arXiv, GitHub, author page, Wayback) was found. The verifier repeated the search on
2026-10-29 (web search, arXiv API, Semantic Scholar API, GitHub search) and found no other copy either. Everything below comes from the
author's abstract as deposited with Crossref (DOI 10.2139/ssrn.7138562, record created 2026-08-03).
Page and table numbers could not be checked. OpenAlex lists the author's affiliation as Duke
University.

**Question.** Can Kalshi's CFTC-regulated weather markets, which settle daily on official NWS station
observations, *transfer* weather risk and not just predict weather?

**Data.** 287,909 price observations from 15,994 resolved Kalshi contracts. The settlement layer is
Kalshi's daily temperature bin ladder, which the abstract calls "Kalshi's 8 degree F bin ladder." (Verifier
check on the Kalshi public API, 2026-10-29: the New York high-temperature event KXHIGHNY-26OCT27 has four
2 degree F bins covering 60-67 degrees F plus two open-ended tail bins, so 8 degree F is the span of the
ladder, not the width of each bin.) The hedging layer is a degree-day index at each
contract's settlement station versus a "customer-proxy local exposure index" (a degree-day index at
another location), for 30 station pairs, two trigger types (heating degree days, HDD; cooling degree
days, CDD), over 24 years. The main sample is warm season. *Not verifiable from the abstract:* which
cities and stations, the price sample dates, whether any precipitation contracts are included, and the
exact definition of "residual basis risk."

**Method.** Three steps. (1) Test whether post-hoc recalibration of prices (isotonic regression, Platt
scaling) improves out-of-sample probabilistic accuracy. (2) Map residual basis risk between the
settlement-station index and the exposure index, and test static hedge constructions: best single
station, multi-station portfolios, and ridge-shrunk portfolios, out of sample. (3) Measure the
"contract layer": implied-temperature bias, and the binarization (replication) cost of building a
degree-day claim out of binary bins, including a joint daily-level decomposition of geography versus
binarization error. A winter test is pre-specified with locked quantitative predictions.

**Key quantitative findings (abstract only; UNVERIFIED against the full text).**

| Finding | Value |
|---|---|
| Recalibration (isotonic, Platt) improves out-of-sample accuracy? | No |
| Mean residual basis risk | 0.386 |
| Pattern | Rises with station distance; lower for HDD than CDD triggers |
| Multi-station portfolio beats best single station out of sample | 43% of cases; ridge shrinkage does not change this |
| Implied-temperature bias | about 0 |
| Days realized temperature falls outside the bin ladder | 17% |
| Binarization (replication) cost | about 1% of exposure variance, an order of magnitude below geographic basis risk |
| Raising residual basis risk by replacing the ideal index with the bin strip | median +0.007; near-zero correlation between geography and replication errors |
| Author's conclusion | The basis-risk map, not the contract price, is the first-order pricing object for parametric risk transfer |

**Limitations (as far as the abstract shows).** Temperature only; the "customer" is another weather
station, not an actual business or farm loss; warm season only (winter test pending); static hedges
only; the result that replication is cheap rests on a ladder of narrow bins, even though the realized temperature falls outside the ladder's
8 degree F span on 17% of days.

**How our project differs.** (a) We hedge *monthly cumulative precipitation*, whose distribution is
skewed with a mass near zero, using a ladder of "Above X inches" strikes whose spacing and range may be
much coarser relative to the tails than Luo's temperature bins. (b) Our exposure is not another station
but an agricultural benchmark: the PRF grid index (0.25 degree NOAA grid) and forage loss. (c) We
separate *station-vs-grid measurement mismatch* (grid containing the station) from *geographic
distance* (grid containing the farm). Luo's distance gradient is station-to-station only. (d) We compare
against an existing subsidized product, not only against an ideal index. (e) We face a time mismatch
(calendar months vs PRF two-month intervals) that Luo's daily degree-day design does not have.

**What we can reuse.** The decomposition of total hedge error into a geography term and a binarization
term, measured as shares of exposure variance; the out-of-sample "portfolio beats best single station"
win rate with ridge shrinkage as a check against overfitting; the recalibration test as a check on
whether prices need correction; the distance gradient (basis risk vs miles); and the practice of locking
predictions before running a new test.

#### 1.2 Iturbide (2026), "Basis Risk in Prediction Markets: Can a Rain Contract Hedge New York Rooftop Bars?" [iturbide2026]

**Access.** SSRN PDF blocked (HTTP 403). We read the author abstract (Crossref, record created
2026-10-02) and the public replication repository in full
(https://github.com/pauliturbide21-blip/kalshi-rain-basis-risk; copy in `data/raw/lit/iturbide_repo/`,
which the verifier confirmed is byte-identical to GitHub by git blob hash):
README, pre-registration (in French, time-stamped 2026-09-16 19:11 UTC), deviations list, result CSVs,
and scripts. The README maps "Table 1" to trigger and price results and "Table 2" to hedging results;
page numbers are not available. All numbers below match the repository CSVs.

**Question.** Kalshi markets its daily rain contract to small businesses as a weather hedge. Does it
work for New York rooftop bars, "the case where it should work best"?

**Data.** Kalshi daily "Will it rain in [city] on [date]?" markets: the per-city series (e.g.
`KXRAINNYC`) and, from 2026-07-15, the multi-city series `KXRAIN`, pulled from the public API including
`/historical/markets` and hourly candlesticks. Season = May 1 to Sep 30. NYC: 355 season days in 2021,
2022, 2025, and 2026 (4 days dropped for station gaps); Miami and Chicago: 57 days each in 2026 as
secondary cases. Hourly precipitation from ASOS stations (Central Park for NYC, MIA, ORD) via the Iowa
Environmental Mesonet; NWS MOS (NBS) forecasts as the calibration benchmark; ten reconstructed venue
revenue profiles. 126 2022 contracts with other thresholds (e.g. "more than 0.05 inch") were excluded.

**Method.** Definitions were pre-registered before any download. Loss day D = 1 if at least 1 mm of
rain falls from 6 p.m. to 1 a.m.; payout Y = 1 if the contract settles Yes; hedge price = last trade
before noon the day before (else bid-ask midpoint); fee = 0.07 p (1 - p). Metrics: the 2x2 table of Y
and D; false-positive share FP = P(D = 0 | Y = 1); uncovered-loss share UC = P(Y = 0 | D = 1);
correlation; Brier score with reliability decomposition against MOS; raw loading and *effective
loading* Lambda = (mean price + mean fee) / P(Y = 1 and D = 1), i.e. dollars of premium per dollar
of payout that lands on a loss; minimum-variance hedge ratio and Ederington effectiveness (checked
equal to the squared correlation at the daily level; at the season level, with a varying purchase
price, effectiveness at the optimal ratio is 0.144 instead of 0.225, `preregistration_deviations.md`
item 2); 7-day moving-block bootstrap (5,000 draws) for all intervals;
out-of-sample hedge choice (pick the best of 132 settings on 2025, test on 2026 and vice versa);
counterfactuals (an evening-window contract, a better-informed buyer using forecasts, and an optimal
trading-program bound). A natural experiment compares the old rule (trace rain counts as Yes) with the
new rule from 2026-07-15 (trace excluded; settled on The Weather Company data) on the same days.

**Key quantitative findings.**

| Finding | Value | Source in repo |
|---|---|---|
| Brier score, Kalshi vs NWS MOS | 0.143 vs 0.146 (237 days) | `results/price.csv` |
| Payouts on evenings with no loss | 69% (CI 62-75) | `results/trigger.csv` |
| Losses with no payout | 0% (every lost evening fell on a Yes day) | `results/trigger.csv` (UC) |
| Payout-loss correlation | 0.44 | `results/trigger.csv` |
| Raw loading, mean price / P(pays) - 1 (verifier addition) | -0.078 (CI -0.167 to 0.028): price about equal to payout frequency | `results/price.csv` (lambda) |
| Premium + fee per $ of useful payout | $2.75 (CI 2.14-3.60) | `results/price.csv` |
| Trace rule change: false positives / correlation | 0.69 to 0.60 / 0.44 to 0.55 | `results/trigger_trace_rule.csv` |
| Median / mean bid-ask spread at purchase | $0.10 / $0.25 | `results/price.csv` |
| Median open interest at purchase / median daily volume | 2 / 3,227 contracts | `results/liquidity.csv` |
| Max hedge effectiveness, current rule / no-trace rule | 0.195 / 0.302 | `results/optimal_program_bound.csv` |
| Evening-window counterfactual | raises worst-of-twenty season by 1-3% of revenue at all ten venues | abstract |

The author's conclusion: "The binding constraint is contract design, not price or buyer
sophistication." Hedging gains with the real contract are small and vanish under realistic execution.

**Limitations.** One city with four seasons; revenues are reconstructed, so dollar results are softer
than the timing result (the author says so); one binary threshold, so there is no ladder to replicate
with; the venue panel and counterfactuals were designed after pre-registration and are labeled
exploratory; high-frequency daily setting differs from monthly agriculture.

**How our project differs.** (a) Monthly totals and a multi-strike ladder, so we can *build* a payoff
(a put on rainfall) instead of taking one fixed trigger. (b) The exposure is an agricultural index
with its own fixed rules (PRF), so the "wrong window" problem becomes calendar month vs PRF two-month
interval, and the "wrong definition" problem becomes station settlement (NWS climate report, now TWC) vs
NOAA gridded index (CPC, moving to NCEI). (c) We add geographic distance (station grid vs farm grid).
(d) We benchmark against a subsidized insurance premium rather than a hypothetical private insurer.

**What we can reuse.** The contingency-table metrics (FP, UC, phi), the effective loading Lambda as a
single "price of useful protection" number we can compute for both Kalshi replicas and PRF, the
Ederington check e = rho^2, block bootstrap intervals (we should block by year), the pre-registration
discipline, the trace-rule natural experiment as a template for our settlement-source comparison, and
the practical data handling in `src/01_download_data.py`, `src/02_trigger.py`, and `src/03_price.py`
(see Implications).

#### 1.3 Side-by-side

| Dimension | Luo (2026) | Iturbide (2026) | Our project |
|---|---|---|---|
| Weather variable | Daily temperature (degree days) | Daily rain yes/no | Monthly rain total |
| Kalshi contract | Daily temperature bin ladder (2 degree F bins spanning about 8 degree F, plus open tails) | Single daily binary | Monthly "Above X inches" ladder |
| Exposure | Degree-day index at another station | Reconstructed bar revenue, 6 p.m.-1 a.m. rain | PRF grid index; forage loss proxy |
| Benchmark | Ideal (non-binarized) index | Counterfactual evening contract; hypothetical insurer | USDA PRF Rainfall Index policy |
| Places | 30 station pairs (cities not visible) | NYC (plus MIA, CHI in 2026) | 7 PRF sites + 1 row-crop contrast |
| Dominant friction found | Geography | Settlement window and definition | To be measured: grid vs station, distance, interval, ladder, price |
| Main metrics | Residual basis risk; binarization cost | FP/UC, Brier, Lambda, Ederington e | All of these, plus PRF loss and payout gaps |

### 2. Annotated bibliography by theme

Each entry: question, method, finding, relevance. Verification status for each is in `references.bib`.

#### 2.1 Building payoffs from state-contingent securities (spanning and static replication)

- **Arrow (1964)** [arrow1964]. Shows that a complete set of securities each paying in one state of the
  world lets a competitive economy reach an efficient allocation of risk. This is the "Arrow-Debreu
  security" idea; a Kalshi binary that pays $1 if an event happens is exactly such a security
  (Diercks et al. call Kalshi contracts "simple Arrow-Debreu securities," p. 2).
- **Ross (1976), "Options and Efficiency"** [ross1976]. Argues that options on existing assets expand the
  set of insurable contingencies, and that complex contracts can be "built up" as portfolios of simple
  options (abstract). This is the theoretical basis of our proposal: a farmer's custom rainfall payout
  is built from a portfolio of simple Kalshi rain binaries.
- **Breeden and Litzenberger (1978)** [breeden1978]. Show that the price of a $1 claim paid if an
  underlying lands between two levels follows from the second derivative of the call price with
  respect to strike (abstract). With binary "Above K" contracts the step is simpler: the price of
  "Above K" is the risk-neutral probability that rain exceeds K, and differences between adjacent
  strikes give bin probabilities.
- **Jackwerth and Rubinstein (1996)** [jackwerth1996]. Recover full risk-neutral distributions from S&P 500
  option prices with a smoothness-penalized optimization. Relevant if our ladder has few strikes and we
  need a smooth, monotone implied distribution between and beyond strikes.
- **Derman, Ergener and Kani (1995)** [derman1995] and **Carr, Ellis and Gupta (1998)** [carr1998].
  Static replication: hedge an exotic payoff with a fixed portfolio of standard options bought once and
  held. Our hedge is static by construction (buy the ladder at the start of the month and hold to
  settlement), so this is the right frame for measuring replication error.
- **Bakshi and Madan (2000)** [bakshi2000]. Use the characteristic function of the underlying to value
  and span derivative payoffs (bibliographic record confirmed; no abstract available to us, so this
  one-line description is from standard knowledge of the paper). Background for treating the strike ladder as a basis of functions.
- **Carr and Madan (2001), "Optimal positioning in derivative securities"** [carr2001]. Solve for the
  optimal payoff an investor should hold when beliefs or preferences differ from the market's, so that
  investors hold options individually even though options are not held in aggregate (abstract). The
  paper's body also states the strike-by-strike spanning formula (any smooth payoff = bond + underlying
  + a strip of puts and calls weighted by the payoff's second derivative); that part is standard
  knowledge of the paper, not in the abstract. Relevant to Milestone 2: first choose the
  optimal payout as a function of rainfall, then implement it with the ladder.

#### 2.2 Hedging-effectiveness and risk metrics

- **Ederington (1979)** [ederington1979]. Defines hedging effectiveness as the share of variance removed
  by the minimum-variance hedge, which equals the squared correlation between exposure and hedge. This
  is the standard metric used by Iturbide (who verifies e = rho^2) and by most weather-hedging papers.
- **Rockafellar and Uryasev (2000)** [rockafellar2000]. Show that minimizing conditional value-at-risk
  (expected loss in the worst alpha% of outcomes) can be written as a linear program. A natural
  objective for the Milestone 2 optimizer, since farmers care about bad years, not variance.

#### 2.3 Weather-index insurance and basis risk

- **Turvey (2001)** [turvey2001]. Prices rain- and heat-based puts and calls for Ontario crops from the
  historical crop-weather relationship, at a location and across space (abstract). Early demonstration
  that event-specific weather derivatives can act as crop insurance.
- **Martin, Barnett and Coble (2001)** [martin2001]. Propose a precipitation contract whose indemnity
  function is chosen by the buyer and price it for Mississippi cotton harvest. Close in spirit to our
  "personalized rainfall insurance" (abstract read by the verifier on RePEc/DataCite; full text not
  read).
- **Vedenov and Barnett (2004)** [vedenov2004]. Build weather derivatives for corn, cotton, and soybeans
  in six crop reporting districts and test risk reduction in and out of sample (full text read). The
  best designs vary widely by crop and region and need complex weather combinations. Warns that a
  generic ladder may not fit every farm.
- **Barnett and Mahul (2007)** [barnett2007]. Reviews weather index insurance for lower-income countries:
  why indices cut moral hazard, adverse selection, and loss-adjustment costs, and what implementation
  requires. Standard reference for the basic trade-off: lower cost in exchange for basis risk.
- **Woodard and Garcia (2008)** [woodard2008]. Split basis risk into *local* (imperfect weather-yield
  link at the same place), *geographic* (extra risk from using a non-local contract), and *product*
  (difference between instruments), each measured as a change in a risk measure such as semivariance
  or expected shortfall under the optimal hedge ratio (conference version, pp. 4-6). For U.S. corn,
  geographic basis risk falls as exposures are aggregated and cross-hedging works better with
  temperature than with precipitation derivatives (journal abstract); precipitation hedges add product
  basis risk relative to temperature hedges (conference version, abstract p. 2 and p. 16). Our two-grid design maps directly onto this split.
- **Manfredo and Richards (2009)** [manfredo2009]. Because yields respond nonlinearly to weather, options
  (nonlinear payoffs) reduce basis risk more than swaps or futures, and station choice may matter less
  than modeling the yield-weather relationship (abstract). Supports building nonlinear payoffs from the
  ladder.
- **Musshoff, Odening and Xu (2011)** [musshoff2011]. Simulate precipitation options for wheat in
  northeast Germany and separate local from geographic basis risk (abstract). Another template for the
  decomposition, specifically for rainfall.
- **Miranda and Farrin (2012)** [miranda2012]. Survey of index insurance theory and practice in
  developing countries: lower transaction costs, weaker individual protection (abstract). Background.
- **Norton, Turvey and Osgood (2013)** [norton2013]. Compare payouts at nearby stations: geography is a
  poor predictor of payout differences, the payout at a nearby station is the best predictor, and
  distance raises payout differences for precipitation (abstract). Directly supports measuring basis
  risk vs distance for rain and suggests a multi-station "risk portfolio."
- **Elabed, Bellemare, Carter and Guirkinger (2013)** [elabed2013]. Measure basis risk by the false
  negative probability (loss but no payout; the definition is reproduced in Yu et al. 2019, footnote 14,
  p. 189) and show compound-risk aversion cuts demand 13 percentage
  points; a multiscale contract raises demand about 40% (abstract). FNP is the metric Yu et al. and
  Keller and Saitone use for PRF, so using it lets us compare directly.
- **Ritter, Musshoff and Odening (2014)** [ritter2014]. Fit a daily multi-site rainfall model and derive
  optimal portfolio weights across stations; this cuts geographic basis risk more than inverse-distance
  weighting (abstract). Relevant if a farm sits between two Kalshi cities, but see Luo's 43% warning.
- **Dalhaus and Finger (2016)** [dalhaus2016]. For German wheat, gridded precipitation performs the same
  as station data, while timing the index to observed plant phenology significantly helps (abstract).
  Suggests our station-vs-grid term may be small and the timing term large.
- **Jensen, Barrett and Mude (2016)** [jensen2016]. Measure basis risk of index-based livestock
  insurance in Kenya with household panel data: it removes 63% of covariate risk but leaves 69% of
  original risk because idiosyncratic risk dominates (abstract). Model for decomposing basis risk into
  design error and idiosyncratic loss.
- **Clarke (2016)** [clarke2016]. Shows that with basis risk, rational demand for index insurance is
  zero for infinitely risk-averse buyers and non-monotonic in risk aversion, wealth, and price
  (abstract). Key
  caution for the app: a hedge with large basis risk can make some farmers worse off.
- **Jensen and Barrett (2017)** [jensen2017] and **Carter et al. (2017)** [carter2017]. Reviews of
  agricultural index insurance quality and its challenges. Background for "product quality evaluation"
  before promotion.
- **Clement, Botzen, Brouwer and Aerts (2018)** [clement2018]. Global review of basis risk: index design,
  data quality and sampling, estimation methods, and the effect on demand; recommends a systematic way
  to quantify basis risk (abstract). Good checklist for our measurement section.
- **Leppert, Dalhaus and Lagerkvist (2021)** [leppert2021]. Heat-index insurance for Illinois and Iowa
  corn cuts relative risk premiums 27%-29%, and interpolated indices beat the nearest station by 2%-3%,
  more so when stations are sparse (abstract). A quantified example of geographic basis risk and the
  "cost of risk" metric (risk premium reduction).

#### 2.4 Weather-derivative pricing

- **Jewson and Brix (2005)** [jewson2005]. Standard textbook on valuing weather derivatives: burn
  analysis, index modeling, daily simulation, and the trade-off between basis risk and price (cited
  this way by Woodard and Garcia). Reference for "fair price" baselines from historical data.
- **Richards, Manfredo and Sanders (2004)** [richards2004]. Compare burn-rate, Black-Scholes, and
  equilibrium Monte Carlo prices for Fresno cooling-degree-day options and find significant differences
  (abstract). Shows the actuarial ("burn") price is only one of several defensible baselines.
- **Campbell and Diebold (2005)** [campbell2005]. Time-series models of daily temperature reveal strong
  conditional variance dynamics, useful for long-horizon predictive densities in weather pricing
  (abstract). Temperature-focused; relevant mainly as method.
- **Carmona and Diko (2005)** [carmona2005]. Model precipitation as a jump Markov (pulse Poisson) process
  and price rainfall contracts by utility indifference (abstract). One of few precipitation-specific
  pricing papers.
- **Xu, Odening and Musshoff (2008)** [xu2008]. Use indifference pricing to get farmers' willingness to
  pay for weather insurance; it varies by production program and region (abstract). A way to value a
  Kalshi hedge to a specific farm when market prices are missing.
- **Lopez Cabrera, Odening and Ritter (2013)** [cabrera2013]. Price CME rainfall futures (listed 2011)
  with a normal-inverse-Gaussian index model and the Esscher transform, and estimate the market price
  of risk (abstract). The closest exchange-traded precedent for monthly U.S. rainfall contracts.

#### 2.5 PRF and Annual Forage rainfall-index insurance

What exists: a modest but growing literature, mostly from Kansas State, Nebraska, South Dakota State,
Oklahoma State, Texas A&M (College Station; AgriLife Extension at Weslaco), and UC Davis. We found no paper that evaluates PRF against
market weather derivatives, and no peer-reviewed hedging-effectiveness study for our specific sites
(Texas, Oklahoma, Missouri, Colorado, New Mexico, Florida). Every PRF paper we found is listed below
and in the Sources list. The list is not exhaustive: the verifier also saw a 2022 conference
presentation (Collins, "Potential Changes to Improve the Pasture, Rangeland, Forage Insurance Program,"
AgEcon Search record 322574) that was not reviewed.

- **Maisashvili (2011)** [maisashvili2011]. Texas A&M thesis simulating PRF returns in Texas counties with
  stochastic efficiency (SERF, SDRF) ranking: 90% coverage was best in all regions tested, December-
  January was a critical interval, and West Texas gained more than south and east Texas (abstract).
  Closest work to our DFW and SAT sites.
- **Nadolnyak and Vedenov (2013)** [nadolnyak2013]. In the Southeast, skillful ENSO forecasts let
  insured producers pick intervals strategically, creating intertemporal adverse selection that
  forecast-conditional premiums could prevent (abstract). Relevant to TPA (Florida) and to any buyer who
  times Kalshi purchases with forecasts.
- **Ifft, Wu and Kuethe (2014)** [ifft2014]. PRF availability raised pasture values by at least 4%
  (abstract). Shows subsidized PRF benefits are partly capitalized into land.
- **Diersen, Gurung and Fausti (2015)** [diersen2015]. Markowitz efficient frontier over PRF intervals for
  South Dakota hay: May-June and July-August matter most; subsidized enrollment gives higher return and
  lower risk; without subsidy mean return falls but risk reduction remains (abstract). This is the
  "Diersen et al." PRF-portfolio work; template for our optimizer.
- **Maples, Brorsen and Biermacher (2016)** [maples2016]. For annual ryegrass at Burneyville, Oklahoma,
  the Annual Forage rainfall index tracks site rainfall closely but gives little yield-loss protection
  (full text). Rain matching is not the same as loss matching.
- **Westerhold et al. (2018)** [westerhold2018]. With two Nebraska ranches' forage records, growing-season
  intervals lower net-income variance while winter intervals raise it; one risk-increasing scenario
  had the highest net income (abstract). Sorts interval choices into four zones by whether they reduce
  risk and whether the subsidy is working as intended (abstract).
- **Yu, Vandeveer, Volesky and Harmoney (2019)** [yu2019]. Elastic-net models of forage yield on monthly
  rain and on PRF indices at three Kansas/Nebraska ranches; false negative probability 26%-43% (26%
  with ranch-level data, 42.7% with field-level data for one ranch), of which only 5-9 percentage points
  (21% vs 26%; 33.9% vs 42.7%) is due to index design (two-month grid index vs site rain) (full text,
  Table 5 p. 189, pp. 189-190). The authors call these index-related estimates upper bounds because
  Nebraska rain stations are sparse. The most direct estimate of PRF's "index-related" basis risk; our
  grid-vs-station term should be compared with their 5-9 points.
- **Goodrich, Yu and Vandeveer (2020)** [goodrich2020]. Policyholder-level Nebraska and Kansas data,
  2013-2017: cluster analysis shows growing numbers of participants with low-risk-aversion interval
  patterns, linked to higher subsidies and returns in non-growing-season months (abstract).
- **ShalekBriski et al. (2021)** [shalekbriski2021]. Winter annual forage yields correlate weakly and
  inconsistently with the Annual Forage index; authors call the program a "risk-increasing income-
  transfer" (abstract).
- **Keller and Saitone (2022)** [keller2022]. NDVI-based forage proxy for California rangeland: false
  negative probability 31%-46% for one interval and 14%-25% for both; 36% of paid cases under-
  compensated by $1.74-$2.73 per acre (abstract). Model for using satellite vegetation as the "true
  loss" when ranch data are missing.
- **Zapata and Garcia (2022)** [zapata2022]. Three risk-efficient portfolio strategies for choosing PRF
  coverage parameters, illustrated for a South Texas grid (abstract). Optimizer template.
- **Shrum and Travis (2022)** [shrum2022]. Randomized ranch-management simulations find PRF does not
  change herd size or drought investment, suggesting limited moral hazard (abstract).
- **Davidson and Goodrich (2023)** [davidson2023]. Framed field experiment: framing PRF as forage-loss
  risk management raises enrollment, but a nudge does not change interval choice (abstract). Relevant
  to how the app presents hedges.
- **Zapata, Villavicencio and Xicay (2024)** [zapata2024]. Shrinkage and ensemble learning for PRF
  coverage choice on 116 Texas grids, 2018-2022; ensembles more stable, 5%-14% lower prediction error
  out of sample (abstract).
- **Belgacem (2025)** [belgacem2025]. UNL dissertation: 176 Nebraska grids, 1988-2023, using Rangeland
  Analysis Platform biomass; the chance neither insured interval pays during a forage loss averages
  12% (nearly 30% in several Sandhills cells), below 10% with the best late-spring plus summer pair
  (abstract).
- **Cho and Diersen (2026)** [cho2026aepp]. South Dakota, 2013-2024: rising selection of non-production
  intervals; a mean-variance portfolio model shows uniform subsidy rates push producers toward them
  (abstract). Newest evidence on subsidy distortion.
- **Cho and ShalekBriski (2026)** [cho2026afr]. Drier counties and intervals have more variable indices
  and higher loss ratios; assuming a truncated normal index overstates expected payouts relative to
  the empirical distribution (abstract). Relevant to premium rating and to how we model the PRF payout
  distribution (use empirical, not normal).
- **Davis, Connor, Popp and Rider (2025)** [davis2025]. Profitability of PRF in three Arkansas counties
  across interval-selection strategies and wetness levels: profitable in drier-to-median counties,
  weaker in the wettest county (abstract on AgEcon Search; located by the verifier). A separate Southern
  Ag Today column by the first author [davis2025sat] reports a mean grid-level PRF loss ratio of 0.79
  (SD 0.20) across the South, 2017-2024, under baseline enrollment, and 0.83 (SD 0.33) under an interval
  strategy chosen by rainfall uncertainty. Those loss ratios come from the column, not from the journal
  article.

#### 2.6 Prediction markets: accuracy and favorite-longshot bias

- **Griffith (1949)** [griffith1949] and **Thaler and Ziemba (1988)** [thaler1988]. The original
  horse-racing evidence and the classic review: longshots are overbet and favorites underbet. The
  "favorite-longshot bias" (FLB) is one of the most robust anomalies in betting markets.
- **Wolfers and Zitzewitz (2004)** [wolfers2004]. Prediction-market forecasts are typically accurate and
  beat moderately sophisticated benchmarks; contract design (binary, index, spread) reveals
  probabilities, means, and medians (abstract). Foundational for reading Kalshi prices as forecasts.
- **Manski (2006)** [manski2006] and **Wolfers and Zitzewitz (2006)** [wolfers2006]. Manski shows prices
  need not equal mean beliefs; Wolfers and Zitzewitz give conditions under which they do and show they
  are usually close, though sometimes biased (abstract). Justifies treating prices as approximate
  probabilities while testing for bias.
- **Ottaviani and Sorensen (2008)** [ottaviani2008]. Handbook overview of explanations for the FLB (risk
  preferences, misperceptions, information, market structure). Background.
- **Snowberg and Wolfers (2010)** [snowberg2010]. Using exotic racetrack bets, they find misperception of
  probabilities (as in prospect theory), not risk-love, drives the FLB (abstract). Implication: the bias
  reflects how people weight small probabilities, so it may persist in tail rain contracts.
- **Page and Clemen (2013)** [page2013]. On a large set of prediction-market trades, prices are well
  calibrated close to expiry but show FLB for events far in the future (abstract). A monthly contract
  bought weeks ahead is in the more biased zone.

#### 2.7 Kalshi-specific evidence

- **Burgi, Deng and Whelan (2026), "Makers and Takers"** [burgi2026]. Transaction data on 313,972
  contract prices, 2021 to April 2025 (full text). Prices are informative and improve near close, but
  contracts at 10 cents or less lose over 60%; average return -20% before and -22% after fees;
  takers (market orders) lose -31.46% vs -11.99% for makers (limit orders) after fees (p. 36); the
  Mincer-Zarnowitz test rejects unbiasedness in every category including Climate & Weather (Table 8,
  p. 25). The core
  evidence on what it costs to buy low-probability Kalshi contracts.
- **Diercks, Katz and Wright (2026), FEDS 2026-010** [diercks2026]. Build Kalshi-implied distributions for
  CPI, unemployment, and Fed funds by differencing adjacent "above" strikes, carrying forward the last
  trade when a strike does not trade, and enforcing a monotone CDF outward from the mode to stop stale
  tail prices contaminating the rest (pp. 13-14). Bid-ask midpoints performed worse because of large
  tail spreads (Appendix A, p. 40). Probability integral transforms are generally close to uniform, with borderline rejections in some
  cases (pp. 27-28).
  Directly reusable recipe for our rain ladders.
- **Crosier (2026)** [crosier2026]. Using five years of Kalshi daily high-temperature markets in 7 US
  cities, the market-implied forecast beats the National Blend of Models (NBM) in 6 of 7 cities; pooled
  over all city-days it beats the best single public forecast by about 10% in RMSE from the end of the
  first trading hour (abstract).
  Evidence that weather markets aggregate information well at short horizons.
- **Shah (2026)** [shah2026]. On 26,192 settled sports and daily weather markets, an apparent huge FLB
  computed from last trades (16 of 17,612 lowest-price markets won, vs about 229 expected) is a
  measurement artifact: game markets stay open until the game ends, so the last trade comes after the
  winner is known, and prices cannot go below 1 cent. Re-measured with pre-outcome prices on 810 MLB
  games and 4,000 fifteen-minute Bitcoin markets (not weather markets), the bias is small (2.0 points
  for MLB underdogs, p = 0.24) and not tradable (abstract only; SSRN full text not accessible). Warning
  for our pricing: use pre-outcome quotes. The abstract does not say how large the artifact is for
  weather markets.
- **Krause (2026)** [krause2026]. Kalshi unemployment contracts, Jul 2021-Mar 2026: longshots below $0.30
  are overpriced by 7.7 percentage points, favorites are calibrated (abstract). Another Kalshi FLB
  estimate, though on a small sample.
- **Luo (2026)** and **Iturbide (2026)**: see Section 1.

### 3. Implications for the cost of hedging tail rain events

A rancher worried about drought wants money when the month is *dry*. On a ladder of "Above X inches"
contracts, that means buying **No** on low strikes (No on "Above 1 inch" pays if rain is 1 inch or
less). In most months such an outcome is unlikely, so these No contracts trade at low prices: they are
longshots. The literature says:

1. **Longshots are overpriced on Kalshi.** Contracts at 10 cents or less returned worse than -60% on
   average [burgi2026, p. 18; Figure 5, p. 19], and the Climate & Weather category shows the same
   pattern (Table 8, p. 25). In that regression the implied break-even price is about 32 cents (DERIVED;
   prices and profits are in cents, see Numbers table), so the
   cheap tail contracts a drought hedge needs sit in the loss region.
2. **Fees hit cheap contracts hardest.** Fee = 0.07 p (1 - p) per contract, with the order total rounded up
   to the next cent; on one hundred 5-cent contracts that is 34 cents, almost 7% of the cost
   [burgi2026, pp. 5, 18-19]. Kalshi's current fee schedule for weather
   series should be re-checked (see open questions).
3. **Being a taker is expensive.** Takers lost -31.46% vs -11.99% for makers after fees [burgi2026, p. 36]. A farmer
   hedge that posts limit orders and waits will be cheaper but may not fill in thin markets.
4. **Longer horizon, more bias.** FLB grows with time to expiry [page2013]; a monthly contract bought at
   the start of the month or earlier is in that zone.
5. **Thin markets.** Median open interest of 2 contracts and a $0.10 median spread at purchase time for
   NYC daily rain [iturbide2026]; apparently empty books on the open Dallas monthly markets we checked
   (pending a recheck with the new API field names). Spread, not the fair price, may dominate cost.
6. **But the center of the distribution is priced well.** Brier score matching the NWS [iturbide2026],
   beating the NBM for temperature [crosier2026], implied-temperature bias near zero and no gain from
   recalibration [luo2026]. So the cost problem is concentrated in tails, fees, and liquidity.
7. **Measure cost the right way.** Use the effective loading Lambda (price + fee per dollar of payout
   that lands on a real loss) [iturbide2026], evaluated at the ask (taker) and at a maker scenario, and
   never last trades near settlement [shah2026].

### 4. The gap we fill

Luo shows that for daily temperature contracts the binding problem is geography, and that building a
payoff from Kalshi's dense bins is cheap; Iturbide shows that for a daily rain binary the binding
problem is that the contract settles on the wrong window and definition, even though it is well
calibrated (Brier 0.143 vs 0.146; raw loading -8%, confidence interval includes zero). As far as Luo's
abstract and Iturbide's abstract and replication files show, neither studies monthly precipitation
ladders, agricultural exposure, gridded indices, or an existing insurance benchmark (Iturbide's insurer
comparison uses a hypothetical premium swept from 1.8% to 18% of the sum insured, pre-registration
section 5), and neither separates station-vs-grid measurement error from geographic
distance. We fill that gap by replicating the USDA PRF rainfall-index payout with Kalshi monthly rain
ladders at seven grazing sites (plus a row-crop contrast), decomposing the gap into (i) station vs grid
measurement, (ii) distance to the farm, (iii) calendar month vs PRF two-month interval, (iv) ladder
discretization, and (v) settlement source (NWS/TWC station report vs NOAA CPC/NCEI grid), and then
pricing what is left, including the favorite-longshot and liquidity costs of tail rain, against PRF's
subsidized premium.

### 5. Methods we will borrow

| Method | Source | How we use it | Milestone |
|---|---|---|---|
| Basis-risk decomposition into local, geographic, product | [woodard2008]; [musshoff2011] | Station-grid run isolates measurement; farm-grid run adds distance; Kalshi vs PRF payout adds product | 1 |
| Geography vs binarization (replication) cost as shares of exposure variance | [luo2026] | Ladder strip vs ideal continuous payoff on the same station data | 1 |
| Index-related vs total basis risk | [yu2019] | Compare our grid-vs-station term with their 5-9 percentage points | 1 |
| False negative / false positive probabilities from a payout-loss 2x2 table | [elabed2013]; [yu2019]; [keller2022]; [iturbide2026] | "PRF pays but Kalshi replica does not" and vice versa, per site and interval | 1 |
| Ederington effectiveness e = 1 - Var(hedged)/Var(unhedged) = rho^2 at the min-variance ratio | [ederington1979]; [iturbide2026] | Replication quality metric | 1 |
| Downside metrics: semivariance, expected shortfall, CVaR | [woodard2008]; [rockafellar2000] | Tail-focused replication quality; optimizer objective | 1-2 |
| Effective loading Lambda = (price + fee) / P(payout and loss) | [iturbide2026] | Cost of useful protection, Kalshi vs PRF | 1-2 |
| Strike differencing, carry-forward, monotone CDF from the mode | [diercks2026]; [breeden1978] | Implied monthly-rain distribution from the ladder | 1 |
| Digital strip replication: f(R) ~ f(K0) + sum_i [f(K_{i+1}) - f(K_i)] x 1{R > K_i}; a put on rain = buy No on each strike below the trigger, sized by the strike gap | [ross1976]; [carr2001]; [carr1998] | Build PRF-like payouts from "Above K" binaries | 1-2 |
| Calibration: Brier score, reliability bins, Mincer-Zarnowitz y - p = a + b p, PIT uniformity | [iturbide2026]; [burgi2026]; [diercks2026] | Check whether rain-ladder prices are biased, especially in tails | 1 |
| Out-of-sample discipline (choose on early years, test on later; leave-one-year-out; ridge) | [luo2026]; [iturbide2026]; [yu2019]; [zapata2024] | Hedge ratios and strike choice | 1-2 |
| Block bootstrap confidence intervals | [iturbide2026] | Resample whole years (monthly data) | 1 |
| Pre-registration of definitions before pulling prices | [iturbide2026]; [luo2026] | Fix loss and payout definitions before analysis | 1 |
| Mean-variance and risk-efficient interval portfolios | [diersen2015]; [zapata2022]; [cho2026aepp] | Optimizer over strikes and months | 2 |
| Multi-station portfolios with shrinkage | [ritter2014]; [norton2013]; [luo2026] | Optional, only if out-of-sample gain is shown | 2 |

## Implications for our replication design

1. **Report a decomposition, not one number.** Following Woodard and Garcia and Luo, compute replication
   quality at (a) the station's own data vs the station grid's PRF index, (b) station vs farm grid,
   (c) monthly vs two-month timing, (d) continuous payoff vs ladder strip. Each step's increase in
   residual risk is one component.
2. **Use the same loss metrics as the PRF papers** (false negative probability, Ederington e, downside
   risk) so our numbers sit next to Yu et al. (26%-43%), Keller and Saitone (14%-25% that both
   intervals miss a loss; 31%-46% that one misses), and Belgacem (12% that both miss) in the final report.
3. **Model PRF payouts from the empirical index distribution,** not a normal or truncated normal
   (Cho and ShalekBriski 2026).
4. **Price with quotes, not last trades.** Use ask (taker) and a maker scenario; carry forward and
   enforce a monotone CDF as Diercks et al. do; record when no quote exists. Iturbide's code reads
   Kalshi fields `volume_fp`, `open_interest_fp`, and candlestick `price.close` / `price.close_dollars`,
   `yes_bid.close(_dollars)`, `yes_ask.close(_dollars)`, `end_period_ts` (observed in
   `data/raw/lit/iturbide_repo/src/02_trigger.py` and `src/03_price.py`; consistent with our note that old field names now
   return None).
5. **Expect tail costs.** Budget for longshot overpricing and fees on low-strike No contracts; report
   cost both with and without them.
6. **Separate subsidy from protection.** PRF premiums are subsidized and producers pick intervals for
   subsidy capture (Goodrich; Westerhold; Cho and Diersen). Compare Kalshi replicas to PRF on both the
   farmer-paid premium and the unsubsidized (total) premium.
7. **Treat the July 2026 trace-rule and TWC switch as a natural experiment,** as Iturbide does; check
   which settlement rule applied to each monthly market in our sample.
8. **Guard against overfitting** in strike and station choice (Luo's 43% out-of-sample win rate for
   multi-station portfolios).

## Unverified claims and open questions

- **Luo full text not read.** The definition and units of "residual basis risk" (0.386), the cities and
  stations used, the price sample period, whether any rain contracts are included, and all page/table
  locations are unknown. Someone with SSRN access in a normal browser should download the PDF and
  check.
- **Iturbide paper text not read.** Numbers come from the abstract and the replication CSVs, which
  agree. Page numbers are unknown; README says Table 1 = trigger and price, Table 2 = hedging.
- **Davis et al. (2025)**: the article is now located (Journal of the ASFMRA 2025, DOI
  10.22004/ag.econ.410248; abstract only). Its page range (132-146) comes only from the Southern Ag Today
  reference list. The 0.79 / 0.83 loss ratios are from the Southern Ag Today column [davis2025sat], an
  extension piece that is not peer reviewed.
- **Units in Burgi et al. Table 8** are not printed in the table, but the text (p. 20: the No
  contract's price and profit are "100c minus the Yes contract values") and the size of the constants
  imply cents. The full-sample coefficients give a break-even of 1.736 / 0.034 = 51 cents, matching the
  paper's statement that contracts above 50 cents earn small positive returns. The 32-cent Climate &
  Weather break-even is our arithmetic and ignores the standard errors.
- **Kalshi's current fee schedule** for weather series (2026) may differ from the 0.07 p (1 - p) formula
  described for 2021-2025; the Kalshi workstream should confirm, including any maker fees.
- **Do Kalshi FLB results transfer to monthly rain ladders?** Burgi et al. require at least $1,000
  volume and spreads at most 20 cents, so thin monthly rain markets may be outside their sample.
- **Woodard and Garcia (2008)**: definitions were read in the same-titled 2007 conference version; the
  AFR journal version was not read.
- **Martin, Barnett and Coble (2001)**: abstract read on RePEc/DataCite by the verifier; full text not
  read.
- **Shah (2026) and Krause (2026)**: SSRN abstracts only (full text blocked by the same Cloudflare check);
  their numbers are labeled UNVERIFIED (abstract only).
- **UCD WP2025_19** (the version of "Makers and Takers" named in the task) returned HTTP 403; we read the
  later CESifo version (January 2026), which states the original was September 2025.
- **Gaps we searched for and did not find:** a peer-reviewed PRF hedging-effectiveness study for TX, OK,
  MO, CO, NM, or FL sites using ranch data; any paper comparing PRF to exchange-traded or prediction-
  market weather contracts; any study of Kalshi monthly rain ladders.

## Sources

Search tools used on 2026-10-29: Crossref API bibliographic search and DOI lookup, OpenAlex, Semantic
Scholar, arXiv API, GitHub API, RePEc/IDEAS, AgEcon Search, publisher pages, web search. SSRN pages
were blocked (HTTP 403).

**Closest prior art**
- Luo, Z. (2026). Prediction Markets as Weather Hedges: Geographic Basis Risk, Settlement Constraints, and Contract Replication. SSRN 7138562. https://doi.org/10.2139/ssrn.7138562
- Iturbide, P. (2026). Basis Risk in Prediction Markets: Can a Rain Contract Hedge New York Rooftop Bars? SSRN 7552699. https://doi.org/10.2139/ssrn.7552699 ; replication files https://github.com/pauliturbide21-blip/kalshi-rain-basis-risk

**Spanning, replication, metrics**
- Arrow, K. J. (1964). The Role of Securities in the Optimal Allocation of Risk-bearing. Review of Economic Studies 31(2):91-96. https://doi.org/10.2307/2296188
- Ross, S. A. (1976). Options and Efficiency. Quarterly Journal of Economics 90(1):75-89. https://doi.org/10.2307/1886087
- Breeden, D. T., and R. H. Litzenberger (1978). Prices of State-Contingent Claims Implicit in Option Prices. Journal of Business 51(4):621-651. https://doi.org/10.1086/296025
- Jackwerth, J. C., and M. Rubinstein (1996). Recovering Probability Distributions from Option Prices. Journal of Finance 51(5):1611-1631. https://doi.org/10.1111/j.1540-6261.1996.tb05219.x
- Derman, E., D. Ergener, and I. Kani (1995). Static Options Replication. Journal of Derivatives 2(4):78-95. https://doi.org/10.3905/jod.1995.407927
- Carr, P., K. Ellis, and V. Gupta (1998). Static Hedging of Exotic Options. Journal of Finance 53(3):1165-1190. https://doi.org/10.1111/0022-1082.00048
- Bakshi, G., and D. Madan (2000). Spanning and Derivative-Security Valuation. Journal of Financial Economics 55(2):205-238. https://doi.org/10.1016/S0304-405X(99)00050-1
- Carr, P., and D. Madan (2001). Optimal Positioning in Derivative Securities. Quantitative Finance 1(1):19-37. https://doi.org/10.1080/713665549
- Ederington, L. H. (1979). The Hedging Performance of the New Futures Markets. Journal of Finance 34(1):157-170. https://doi.org/10.1111/j.1540-6261.1979.tb02077.x
- Rockafellar, R. T., and S. Uryasev (2000). Optimization of Conditional Value-at-Risk. Journal of Risk 2(3):21-41. https://doi.org/10.21314/JOR.2000.038

**Weather-index insurance and basis risk**
- Turvey, C. G. (2001). Weather Derivatives for Specific Event Risks in Agriculture. Review of Agricultural Economics 23(2):333-351. https://doi.org/10.1111/1467-9353.00065
- Martin, S. W., B. J. Barnett, and K. H. Coble (2001). Developing and Pricing Precipitation Insurance. Journal of Agricultural and Resource Economics 26(1):261-274. https://doi.org/10.22004/ag.econ.31155
- Vedenov, D. V., and B. J. Barnett (2004). Efficiency of Weather Derivatives as Primary Crop Insurance Instruments. Journal of Agricultural and Resource Economics 29(3):387-403. https://doi.org/10.22004/ag.econ.30916
- Barnett, B. J., and O. Mahul (2007). Weather Index Insurance for Agriculture and Rural Areas in Lower-Income Countries. American Journal of Agricultural Economics 89(5):1241-1247. https://doi.org/10.1111/j.1467-8276.2007.01091.x
- Woodard, J. D., and P. Garcia (2008). Basis Risk and Weather Hedging Effectiveness. Agricultural Finance Review 68(1):99-117. https://doi.org/10.1108/00214660880001221 ; conference version (2007, 101st EAAE Seminar, Berlin) https://doi.org/10.22004/ag.econ.9254
- Manfredo, M. R., and T. J. Richards (2009). Hedging with Weather Derivatives: A Role for Options in Reducing Basis Risk. Applied Financial Economics 19(2):87-97. https://doi.org/10.1080/09603100701765166
- Musshoff, O., M. Odening, and W. Xu (2011). Management of Climate Risks in Agriculture - Will Weather Derivatives Permeate? Applied Economics 43(9):1067-1077. https://doi.org/10.1080/00036840802600210
- Miranda, M. J., and K. Farrin (2012). Index Insurance for Developing Countries. Applied Economic Perspectives and Policy 34(3):391-427. https://doi.org/10.1093/aepp/pps031
- Norton, M. T., C. Turvey, and D. Osgood (2013). Quantifying Spatial Basis Risk for Weather Index Insurance. Journal of Risk Finance 14(1):20-34. https://doi.org/10.1108/15265941311288086
- Elabed, G., M. F. Bellemare, M. R. Carter, and C. Guirkinger (2013). Managing Basis Risk with Multiscale Index Insurance. Agricultural Economics 44(4-5):419-431. https://doi.org/10.1111/agec.12025
- Ritter, M., O. Musshoff, and M. Odening (2014). Minimizing Geographical Basis Risk of Weather Derivatives Using a Multi-Site Rainfall Model. Computational Economics 44(1):67-86. https://doi.org/10.1007/s10614-013-9410-y
- Dalhaus, T., and R. Finger (2016). Can Gridded Precipitation Data and Phenological Observations Reduce Basis Risk of Weather Index-Based Insurance? Weather, Climate, and Society 8(4):409-419. https://doi.org/10.1175/WCAS-D-16-0020.1
- Jensen, N. D., C. B. Barrett, and A. G. Mude (2016). Index Insurance Quality and Basis Risk: Evidence from Northern Kenya. American Journal of Agricultural Economics 98(5):1450-1469. https://doi.org/10.1093/ajae/aaw046
- Clarke, D. J. (2016). A Theory of Rational Demand for Index Insurance. American Economic Journal: Microeconomics 8(1):283-306. https://doi.org/10.1257/mic.20140103
- Jensen, N., and C. Barrett (2017). Agricultural Index Insurance for Development. Applied Economic Perspectives and Policy 39(2):199-219. https://doi.org/10.1093/aepp/ppw022
- Carter, M., A. de Janvry, E. Sadoulet, and A. Sarris (2017). Index Insurance for Developing Country Agriculture: A Reassessment. Annual Review of Resource Economics 9:421-438. https://doi.org/10.1146/annurev-resource-100516-053352
- Clement, K. Y., W. J. W. Botzen, R. Brouwer, and J. C. J. H. Aerts (2018). A Global Review of the Impact of Basis Risk on the Functioning of and Demand for Index Insurance. International Journal of Disaster Risk Reduction 28:845-853. https://doi.org/10.1016/j.ijdrr.2018.01.001
- Leppert, D., T. Dalhaus, and C.-J. Lagerkvist (2021). Accounting for Geographic Basis Risk in Heat Index Insurance: How Spatial Interpolation Can Reduce the Cost of Risk. Weather, Climate, and Society 13(2):273-286. https://doi.org/10.1175/WCAS-D-20-0070.1

**Weather-derivative pricing**
- Jewson, S., and A. Brix, with C. Ziehmann (2005). Weather Derivative Valuation. Cambridge University Press. https://doi.org/10.1017/CBO9780511493348
- Richards, T. J., M. R. Manfredo, and D. R. Sanders (2004). Pricing Weather Derivatives. American Journal of Agricultural Economics 86(4):1005-1017. https://doi.org/10.1111/j.0002-9092.2004.00649.x
- Campbell, S. D., and F. X. Diebold (2005). Weather Forecasting for Weather Derivatives. Journal of the American Statistical Association 100(469):6-16. https://doi.org/10.1198/016214504000001051
- Carmona, R., and P. Diko (2005). Pricing Precipitation Based Derivatives. International Journal of Theoretical and Applied Finance 8(7):959-988. https://doi.org/10.1142/S0219024905003311
- Xu, W., M. Odening, and O. Musshoff (2008). Indifference Pricing of Weather Derivatives. American Journal of Agricultural Economics 90(4):979-993. https://doi.org/10.1111/j.1467-8276.2008.01154.x
- Lopez Cabrera, B., M. Odening, and M. Ritter (2013). Pricing Rainfall Futures at the CME. Journal of Banking & Finance 37(11):4286-4298. https://doi.org/10.1016/j.jbankfin.2013.07.042

**PRF and Annual Forage**
- Maisashvili, A. (2011). The Value of Pasture, Rangeland, Forage Rainfall Index Insurance to Texas Ranchers. Texas A&M University thesis. https://tdl-ir.tdl.org/handle/1969.1/ETD-TAMU-2010-05-7991
- Nadolnyak, D., and D. Vedenov (2013). Information Value of Climate Forecasts for Rainfall Index Insurance for Pasture, Rangeland, and Forage in the Southeast United States. Journal of Agricultural and Applied Economics 45(1):109-124. https://doi.org/10.1017/S1074070800004612
- Ifft, J., S. Wu, and T. Kuethe (2014). The Impact of Pasture Insurance on Farmland Values. Agricultural and Resource Economics Review 43(3):390-405. https://doi.org/10.1017/S1068280500005505
- Diersen, M., P. Gurung, and S. Fausti (2015). Optimal Allocation of Index Insurance Intervals for Commodities. SAEA Annual Meeting, Atlanta. https://doi.org/10.22004/ag.econ.196793
- Maples, J. G., B. W. Brorsen, and J. T. Biermacher (2016). The Rainfall Index Annual Forage Pilot Program as a Risk Management Tool for Cool-Season Forage. Journal of Agricultural and Applied Economics 48(1):29-51. https://doi.org/10.1017/aae.2016.3
- Westerhold, A., C. Walters, K. Brooks, M. Vandeveer, J. Volesky, and W. Schacht (2018). Risk Implications from the Selection of Rainfall Index Insurance Intervals. Agricultural Finance Review 78(5):514-531. https://doi.org/10.1108/AFR-10-2017-0097
- Yu, J., M. Vandeveer, J. D. Volesky, and K. Harmoney (2019). Estimating the Basis Risk of Rainfall Index Insurance for Pasture, Rangeland, and Forage. Journal of Agricultural and Resource Economics 44(1):179-193. https://doi.org/10.22004/ag.econ.281319
- Goodrich, B., J. Yu, and M. Vandeveer (2020). Participation Patterns of the Rainfall Index Insurance for Pasture, Rangeland and Forage Programme. Geneva Papers on Risk and Insurance - Issues and Practice 45(1):29-51. https://doi.org/10.1057/s41288-019-00149-3
- ShalekBriski, A., W. Brorsen, J. K. Rogers, J. T. Biermacher, D. Marburger, and J. Edwards (2021). Design of the Rainfall Index Annual Forage Program. Agricultural Finance Review 81(1):114-131. https://doi.org/10.1108/AFR-11-2019-0120
- Keller, J. B., and T. L. Saitone (2022). Basis Risk in the Pasture, Rangeland, and Forage Insurance Program: Evidence from California. American Journal of Agricultural Economics 104(4):1203-1223. https://doi.org/10.1111/ajae.12282
- Zapata, S. D., and J. M. Garcia (2022). Risk-Efficient Coverage Selection Strategies for the Pasture, Rangeland, Forage (PRF) Insurance Program. Journal of Agricultural and Applied Economics 54(2):286-305. https://doi.org/10.1017/aae.2022.7
- Shrum, T. R., and W. R. Travis (2022). Experiments in Ranching: Rain-Index Insurance and Investment in Production and Drought Risk Management. Applied Economic Perspectives and Policy 44(3):1513-1533. https://doi.org/10.1002/aepp.13304
- Davidson, K. A., and B. K. Goodrich (2023). Nudge to Insure. Applied Economic Perspectives and Policy 45(1):534-554. https://doi.org/10.1002/aepp.13215
- Zapata, S. D., X. Villavicencio, and A. Xicay (2024). A Statistical Learning Approach to Pasture, Rangeland, Forage (PRF) Insurance Coverage Selection. Applied Economic Perspectives and Policy 46(4):1429-1449. https://doi.org/10.1002/aepp.13447
- Belgacem, W. (2025). Two Essays on Index-based Risk Management in U.S. Rangeland and Livestock Production. PhD dissertation, University of Nebraska-Lincoln. https://digitalcommons.unl.edu/dissunl/368
- Cho, W., and M. Diersen (2026). Effectiveness of the PRF-RI Program: Interval Selections With Uniform Premium Subsidy Rates. Applied Economic Perspectives and Policy (early view). https://doi.org/10.1002/aepp.70130
- Cho, W., and A. ShalekBriski (2026). Linking Rainfall Index Variability and Program Performance. Agricultural Finance Review 86(5):763-773. https://doi.org/10.1108/AFR-02-2026-0042
- Davis, W., L. Connor, M. Popp, and S. Rider (2025). Is PRF Profitable in a Wetter State? Evidence from Arkansas. Journal of the ASFMRA 2025 (pages 132-146 per the column below; not verified). https://doi.org/10.22004/ag.econ.410248
- Davis, W. (2025). Understanding Interval-Based Enrollment Risk in PRF: How Interval Selection Strategies Can Impact Protection Across the South. Southern Ag Today 5(46.1), November 10, 2025. https://sat-wp.afpc.tamu.edu/2025/11/10/understanding-interval-based-enrollment-risk-in-prf-how-interval-selection-strategies-can-impact-protection-across-the-south/ (reprinted at https://www.oklahomafarmreport.com/?p=154049)

**Prediction markets and Kalshi**
- Griffith, R. M. (1949). Odds Adjustments by American Horse-Race Bettors. American Journal of Psychology 62(2):290-294. https://doi.org/10.2307/1418469
- Thaler, R. H., and W. T. Ziemba (1988). Anomalies: Parimutuel Betting Markets: Racetracks and Lotteries. Journal of Economic Perspectives 2(2):161-174. https://doi.org/10.1257/jep.2.2.161
- Wolfers, J., and E. Zitzewitz (2004). Prediction Markets. Journal of Economic Perspectives 18(2):107-126. https://doi.org/10.1257/0895330041371321
- Wolfers, J., and E. Zitzewitz (2006). Interpreting Prediction Market Prices as Probabilities. NBER Working Paper 12200. https://doi.org/10.3386/w12200
- Manski, C. F. (2006). Interpreting the Predictions of Prediction Markets. Economics Letters 91(3):425-429. https://doi.org/10.1016/j.econlet.2006.01.004
- Ottaviani, M., and P. N. Sorensen (2008). The Favorite-Longshot Bias: An Overview of the Main Explanations. In Hausch and Ziemba (eds.), Handbook of Sports and Lottery Markets, Elsevier, 83-101. https://doi.org/10.1016/B978-044450744-0.50009-3
- Snowberg, E., and J. Wolfers (2010). Explaining the Favorite-Long Shot Bias: Is it Risk-Love or Misperceptions? Journal of Political Economy 118(4):723-746. https://doi.org/10.1086/655844
- Page, L., and R. T. Clemen (2013). Do Prediction Markets Produce Well-Calibrated Probability Forecasts? Economic Journal 123(568):491-513. https://doi.org/10.1111/j.1468-0297.2012.02561.x
- Burgi, C., W. Deng, and K. Whelan (2026). Makers and Takers: The Economics of the Kalshi Prediction Market. CESifo Working Paper 12122 (orig. Sept. 2025; also UCD WP2025_19, SSRN 5502658). https://doi.org/10.65864/s9kc4p0b7t ; PDF https://www.ifo.de/DocDL/cesifo1_wp12122.pdf
- Diercks, A. M., J. D. Katz, and J. H. Wright (2026). Kalshi and the Rise of Macro Markets. FEDS 2026-010, Federal Reserve Board. https://doi.org/10.17016/FEDS.2026.010 ; PDF https://www.federalreserve.gov/econres/feds/files/2026010pap.pdf
- Crosier, A. W. (2026). Prediction Markets Beat the Weather Forecast on Tomorrow's High Temperature. arXiv:2609.23969. https://arxiv.org/abs/2609.23969
- Shah, D. (2026). Why the Last Trade Is the Wrong Price: Measuring Favorite-Longshot Bias on Kalshi. SSRN 7658058. https://doi.org/10.2139/ssrn.7658058
- Krause, D. (2026). Market Efficiency and the Favorite-Longshot Bias in Unemployment Prediction Markets. SSRN 7110758. https://doi.org/10.2139/ssrn.7110758

## Verification log

Independent fact-check on 2026-10-29. Method: every DOI was resolved through the Crossref API
(`api.crossref.org/works/<doi>`) or, for the four AgEcon Search DOIs (prefix 10.22004), the DataCite API;
entries without a DOI were checked on their repository or arXiv pages. Abstracts were read from
Crossref, OpenAlex, RePEc/IDEAS, Semantic Scholar, DataCite, or the repository page. Numbers attributed
to full texts were re-located with page-level text extraction of the PDFs in `data/raw/lit/` (pypdf);
Iturbide numbers were re-read from the repository CSVs, whose local copies are byte-identical to GitHub
(git blob hashes). SSRN pages were not accessed (Cloudflare check; no attempt to get around it). A
fresh search for other legitimate copies of Luo and Iturbide (web search, arXiv API, Semantic Scholar
API, GitHub) found none. Verifier working files: `data/raw/verify/10_lit/` (gitignored).

**Counts.** 250 claims checked: 67 citations, 70 Numbers-table rows, 104 text claims (each annotation,
key-finding bullet, Section 3 item, Methods-table row, and Implications item), and 9 formulas or derived
numbers. 188 confirmed, 42 corrected, 20 unverifiable.

- Citations: 66 of 67 exist with the stated authors, year, title, venue, volume/pages, and DOI. 1
  corrected (Davis et al. 2025). No fabricated or unresolvable entry was found. 1 entry added
  (`davis2025sat`), so `references.bib` now has 68 entries.
- Numbers table: no numeric value was wrong. 13 rows had wrong page numbers, units, wording, or
  attribution (corrected). 14 rows rest only on SSRN abstracts and are now labeled UNVERIFIED (abstract
  only). 43 confirmed as written.
- Text: 28 claims corrected (wording that overstated or misattributed, or wrong pages); 6 rest only on
  bibliographic metadata or standard knowledge of the paper (Luo's full-text details, and the Arrow,
  Bakshi-Madan, Ederington, Ottaviani-Sorensen, and Barnett-Mahul descriptions); 70 confirmed.
- Formulas and derived numbers recomputed and confirmed: Lambda = (0.4086 + 0.0097) / 0.1519 = 2.754;
  FP = 0.3127 / 0.4507 = 0.694; e = rho^2 (0.442^2 = 0.195 and 0.550^2 = 0.302, matching
  `optimal_program_bound.csv`); fee on 100 x 5 cents = 33.25 cents, rounded up to 34 (6.8%); break-even
  0.997 / 0.031 = 32.2 cents; Mincer-Zarnowitz form y - p = a + b p (Burgi eq. 4); FNP definition (Yu
  eq. 4); digital-strip formula (a valid step approximation that takes f at the upper strike of each
  bin); raw loading 0.4086 / 0.4430 - 1 = -0.078.

**Corrections.**

| Item | Old | New | Source |
|---|---|---|---|
| Burgi et al. page numbers (all) | pp. 4, 6, 11, 19-20, 26 (Table 8), 37 | pp. 3, 5, 10-11, 18-19, 25 (Table 8), 36. The draft used PDF page minus 1; the paper prints PDF page minus 2 | CESifo WP 12122 PDF, page headers |
| Burgi makers/takers returns | -11.99 / -31.46 % | same values, labeled after fees | p. 36 (text on Figure 11, post-fee returns) |
| Burgi Table 8 units | "units not stated; likely cents"; break-even "assumes cents" | cents, implied by p. 20 ("100c minus the Yes contract values") and the constants; full-sample check 1.736 / 0.034 = 51 cents matches the paper's statement that contracts above 50 cents earn positive returns | pp. 3, 20, 25 |
| Luo bin ladder | "8 degree F bins"; "dense 8 degree F ladder that rarely misses" | ladder spans 8 degree F (2 degree F bins plus open tails); misses on 17% of days | Luo abstract; Kalshi API, event KXHIGHNY-26OCT27 |
| Luo, Shah, Krause, Iturbide 1-3% (14 rows) | CONFIRMED (abstract) | UNVERIFIED (abstract only) | lead's rule for SSRN papers whose full text is blocked |
| Davis et al. (2025) citation | UNVERIFIED; "Is PRF Profitable in a Wetter State?"; S. Ryder; no DOI | located: "... Evidence from Arkansas", S. Rider, Journal of the ASFMRA 2025, doi:10.22004/ag.econ.410248 | DataCite; https://ideas.repec.org/a/ags/jasfmr/410248.html |
| PRF loss ratio 0.79 / 0.83 | attributed to Davis et al. (2025) journal article, UNVERIFIED | attributed to Davis (2025), Southern Ag Today 5(46.1), CONFIRMED (extension column) | https://sat-wp.afpc.tamu.edu/2025/11/10/understanding-interval-based-enrollment-risk-in-prf-how-interval-selection-strategies-can-impact-protection-across-the-south/ |
| Yu et al. index-related basis risk | "5%-9%" | 5-9 percentage points (21 vs 26%; 33.9 vs 42.7%), upper bounds per the authors | Yu et al. 2019, Table 5 p. 189, p. 190 |
| Keller and Saitone wording | "31%-46% for one insured interval" | "31%-46% that one of the two insured intervals fails to pay"; Implications item 2 no longer merges this into "14%-46%" | Keller and Saitone 2022 abstract |
| Belgacem region | "Nebraska Sandhills and Panhandle"; "~30" | Nebraska, 176 grids (abstract names the Sandhills; Panhandle not mentioned); "nearly 30% in several Sandhills cells" | https://digitalcommons.unl.edu/dissunl/368 |
| Crosier | "beats NBM in 6 of 7 cities by about 10% in RMSE" | beats NBM in 6 of 7 cities; the ~10% RMSE gain is pooled over all city-days vs the best single public forecast | arXiv 2609.23969 abstract |
| Shah | bias small when "measured before the outcome" (implied for weather too) | pre-outcome re-test was on 810 MLB games and 4,000 Bitcoin 15-minute markets, not weather; artifact explanation is for game markets | SSRN 7658058 abstract (Crossref) |
| Woodard and Garcia | product-basis-risk statement cited to "(abstract)" | the journal abstract says cross-hedging works better with temperature; the product-basis-risk statement is in the 2007 conference version (abstract p. 2, p. 16); conference DOI 10.22004/ag.econ.9254 added | Crossref abstract; conference PDF |
| Carr and Madan (2001) | spanning formula "(abstract)" | formula is in the paper's body (standard knowledge), not the abstract | OpenAlex abstract |
| Bakshi and Madan (2000) | "payoffs ... replicated from a continuum of option prices" | softened to a characteristic-function valuation/spanning description, flagged as standard knowledge (no abstract available) | Crossref/RePEc metadata only |
| Westerhold et al. | "risk-reducing vs subsidy-capturing" zones (in quotes) | four zones by risk effect and whether the subsidy works as intended | AFR 2018 abstract |
| Elabed et al. | "Define basis risk as the false negative probability" | measure basis risk by FNP; definition as reproduced in Yu et al. 2019 fn. 14 | Yu et al. 2019 p. 189 |
| PRF literature institutions | "Texas A&M Kingsville" | Texas A&M (College Station; AgriLife Extension, Weslaco) | OpenAlex affiliations for zapata2022, zapata2024 |
| Martin, Barnett and Coble (2001) | "content from a search snippet" | abstract read (DataCite, RePEc); pages 261-274 confirmed by two citing papers | DataCite; Vedenov and Barnett 2004 references |
| Diercks et al. PITs | "close to uniform" | "generally close to uniform, with borderline rejections in some cases" | FEDS 2026-010 pp. 27-28 |
| Iturbide Ederington check | e = rho^2 | holds at the daily level; at the season level effectiveness at the optimal ratio is 0.144 instead of 0.225 | `preregistration_deviations.md` item 2 |
| Iturbide Kalshi field names | observed in `src/03_price.py` | `src/02_trigger.py` (volume_fp, open_interest_fp) and `src/03_price.py` (candlestick fields) | repo source |
| Gap section | Iturbide's contract "fairly priced"; "neither studies ..." stated flatly | "well calibrated (Brier 0.143 vs 0.146; raw loading -8%, CI includes zero)"; "as far as Luo's abstract and Iturbide's abstract and files show"; Iturbide's insurer benchmark is hypothetical (premium swept 1.8%-18%) | `results/price.csv`; `preregistration.md` section 5 |
| Status line | DRAFT | VERIFIED 2026-10-29 | this log |

**Added by the verifier.** Iturbide raw loading (-0.078, CI -0.167 to 0.028), which supports "well
calibrated"; Shah's MLB pre-outcome numbers; the Kalshi bin-ladder check; the Davis (2025) Southern
Ag Today entry; a note that the PRF list is not exhaustive (Collins 2022, AgEcon Search 322574, not
reviewed).

**Remaining caveats.**

- Luo (2026): every number rests on the author's abstract. The definition and units of "residual basis
  risk" (0.386), the cities, the sample dates, and whether any rain contracts are included are still
  unknown. Someone should download the SSRN PDF in a normal browser and check before presenting Luo's
  numbers as findings.
- Iturbide (2026): the repository numbers are solid, but the paper text was not read. The "1 to 3
  percent" counterfactual gain is abstract-only; `hedge_perfect.csv` shows 0.8%-3.4% for one setting,
  and the exact setting behind the abstract's range was not identified.
- Shah and Krause are single-author SSRN working papers known only from abstracts; treat them as
  supporting, not core, evidence.
- Davis et al. (2025) page range (132-146) is unverified; the loss ratios cited are from an extension
  column, not peer reviewed.
- The "gap we fill" holds based on everything readable: no paper found studies Kalshi monthly rain
  ladders, PRF, or station-vs-grid basis risk. The verifier's extra searches (web, arXiv listing of
  Kalshi papers, GitHub) found no counterexample. This could change if Luo's full text covers
  precipitation.
- Headline findings still stand: both closest papers find calibrated prices but mismatched payouts;
  PRF basis risk is large (false negative probability 12%-46% depending on study and definition);
  Kalshi longshots lose money on average (over 60% for contracts at 10 cents or less); and liquidity is
  thin in the one rain market measured.
