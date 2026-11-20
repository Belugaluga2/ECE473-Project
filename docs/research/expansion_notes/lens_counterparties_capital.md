# Lens: counterparties, capital and Kalshi mechanics that doc 25 missed

Research track, 2026-11-20. Scope: gaps in [doc 25](../../analysis/25_weather_hedging_expansion.md) only. It does not repeat what doc 25 or the other notes in this folder already cover: restaurants, MLB, golf demand, ski, city snow, feedlots, dairy, CME utilities, bad-weather winners or smallholders. Every number has a source in the table at the end. Items marked **(computed)** are my calculations from public data, with the method stated. Items marked **(inference)** are my judgment.

## What this changes for doc 25

1. **Kalshi already nets opposite-side collateral within one station-month.** Every monthly rain event checked has `collateral_return_type: DIRECNET`: Dallas Sep 2025-Nov 2026, plus Oklahoma City, San Antonio and NYC November 2026. Kalshi's opt-in "collateral return" refunds the part of a directional pair that cannot be lost. A trader holding YES on a low strike and NO on a high strike posts only cost − $1. That is exactly the market maker's position against a dry-side farmer and a wet-side buyer at the same station and month. Doc 25 says this is "unverified" and that netting capital "only reaches a firm running its own book." For same-event pairs, that is wrong: the collateral saving is available on-exchange. In doc 25's backtest, collateral is about 5.4 per premium for an equal-premium put and call held separately (6.36 and 4.49 each) against 2.68 netted. It does not apply across stations or months, and positions with returned collateral may become unsellable. (Interpreting DIRECNET as the "directional" group in Kalshi's help text is an inference: the API docs do not define the code.)
2. **Kalshi pays 3.50% APY on cash and open positions**, marked at the last traded price. That is about 70 bp below the 3-month T-bill (4.21% on Nov 2). Collateral therefore costs a seller only the spread between their cost of capital and 3.5%. With an assumed 12% cost of equity and one-month listings, the capital charge on a one-month put is about 4.5% of premium unnetted and about 1.9% for a netted pair. That is far below the 20% load (computed). **Capital is not the binding constraint on Kalshi.** Distribution and demand are, which reinforces doc 25's "sell wholesale first."
3. **Texas PRF is already heaviest in Nov-Feb.** In RMA's 2025 Summary of Business, Jan-Feb (16%) and Nov-Dec (12%) are the two largest Texas PRF intervals by liability. Together they hold 27% of liability and 33% of premium; Oklahoma is similar. Over 2018-2025 they paid a pooled 1.11 loss ratio, against 1.02 for the other intervals (computed). Doc 21's sample farms left Nov-Feb open, but the median insured Texas PRF dollar does not. The Companion's addressable "months PRF leaves open" market is therefore smaller than the sample implies. This needs a check against the 11-farm sample before doc 25's rancher demand ($12.1M) is quoted again.
4. **PRF insurers sit on the rancher's side, and FCIC already gives them a cheap exit.** AIPs are short the same winter drought. Under the 2027 SRA they can cede up to 75% of a state's book to the Assigned Risk Fund at 20% retention, and keep only 7.5% / 6% / 3% of losses in the 100-160 / 160-220 / 220-500% loss-ratio bands. In a winter like 2025 (Texas winter-interval loss ratio 1.75), retained underwriting loss on Texas winter PRF is roughly $1-24M depending on fund placement (computed). AIPs are a dry-side buyer comparable to lenders, not a wet-side partner. Their marginal demand is small because the federal reinsurance is cheaper than anything Kalshi offers (inference).
5. **The best same-region, same-month wet-side loser is utility-scale solar, not hospitality.** ERCOT has about 34-36 GW. Nov-Feb monthly irradiance at five Kalshi stations (DFW, SAT, AUS, OKC, HOU) correlates −0.39 to −0.55 with the station's monthly rain. Wet-tercile months run 5-7.5% below mean irradiance, and the monthly SD is about 12% (computed, NASA POWER 1984-2024). Owners already buy weather-volume hedges: Nephila/Allianz proxy-generation PPAs, including a 153 MW Texas deal, and kWh Analytics' production insurance on about 3 GW. This El Niño winter they are also the buyer who would pick off a climatology-priced wet call. Rain explains only about 15-30% of irradiance variance, so they would prefer an irradiance index (inference).
6. **Golf already transfers rain risk, but golfers pay, not courses.** Sensible Weather sells tee-time refunds through GolfNow, Troon and Courserev. Doc 25 scores golf "Hedging evidence: 1, no hedging found." Consumer attach rates are 12%, 30-31% and "approaching 50%" (company figures). They support an embedded consumer guarantee far above 2%. They do not support restaurants buying for themselves, which remains doc 25's 2% case.
7. **Hedges must be bought month by month.** Across the saved metadata, most monthly rain events opened within about a day of the 1st of the month (2025-26 winter: −0.2 days, i.e. about 23:55 ET on the last day before the month; 2024-25 winter: 3-4 days ahead). November 2026 was the first to list about 30 days ahead. As of Nov 20, no Dallas December event exists (computed, Kalshi API). A rancher cannot buy the Nov-Feb season before the ENSO forecast. Each month is priced after ONI is public, so ENSO risk itself is unhedgeable on Kalshi. PRF, by contrast, closes sales on Dec 1 at climatology-based rates, so it is the ENSO option. Texas Jan-Feb PRF share dipped to about 13% in the two crop years after El Niño autumns, against about 15% after La Niña autumns (computed, 8 years, suggestive only).
8. **The risk-capital market is flush.** Reinsurance capital is a record $800B and alternative capital $144.5B (Aon, mid-2026). Cat bonds outstanding passed $66B. The average cat-bond multiple fell to about 2.4x expected loss in 2026, from 3.71x in 2024. Premium Markel fronted for Nephila fell to $1.0B in H1 2026 from $1.7B. Capital chases scarce risk, so the pairing idea solves a problem the market does not have. What is scarce is origination of standardized, well-measured risk, which is the wholesale/structuring route (inference).

## 1. Wet-side losers in the rancher's region and months

### 1a. Utility-scale solar (ERCOT, SPP)

- **Fleet.** EIA-860M via Cleanview: 237 operating ERCOT solar farms, 34 GW (Nov 2026). S&P Global: 35.998 GW at end of Q1 2026, the largest of any US grid operator. Modo: 4.49 GW synchronized Jan-Sep 2026, 19% below 2025, with a full-year forecast of 6.8-8.4 GW. EIA expects Texas to get about 40% of US 2026 solar additions.
- **Location.** West and Far West Texas hold 40% of the queue but received only 23% of capacity built since 2023; North Texas received the most (Modo). New capacity is moving toward the DFW/central stations Kalshi lists (inference). Kalshi has no West Texas rain station: none in its catalog for Midland, Lubbock, El Paso or Amarillo (repo `kalshi_weather_series_catalog.csv`).
- **Rain-irradiance link (computed).** NASA POWER monthly all-sky GHI at each station's coordinates, joined to the repo's `station_monthly_precip.csv`, Nov-Feb 1984-2024:

  | Station | n months | Pearson r (GHI anomaly, rain) | GHI anomaly, wettest 30% | GHI anomaly, driest 30% | Monthly SD | P10 month |
  |---|---|---|---|---|---|---|
  | DFW | 164 | −0.49 | −6.4% | +7.0% | 11.8% | −16.0% |
  | SAT | 164 | −0.43 | −5.4% | +5.8% | 12.3% | −15.3% |
  | AUS | 160 | −0.41 | −5.2% | +8.5% | 12.6% | −16.5% |
  | OKC | 164 | −0.52 | −7.5% | +7.9% | 11.6% | −15.4% |
  | HOU | 163 | −0.39 | −5.3% | +3.8% | 11.8% | −15.6% |

  Solcast data show how large single-month swings get: South Texas December 2023 irradiance ran up to 30% above average, and utility-scale output 20% above (pv magazine).
- **Exposure size (inference, rough).** Assume a winter capacity factor of about 17%. EIA reports average winter 2023-24 output of 3.3 GW, when installed capacity was about 16 GW in 2023 and growing. At 34 GW that gives about 4.2 TWh a month. A 1-SD irradiance month (12%) is then about 0.5 TWh, or about $15M at an assumed $30/MWh capture price. About a quarter of that variance is rain-explained (r² 0.15-0.30). The rain-hedgeable 1-SD swing is therefore of order $5-8M a month fleet-wide, the same order as the ranchers' $8.8M Nov-Feb premium at shared stations. Doc 25's restaurants come in at 1:15 to 1:80 of that (doc 25).
- **Existing hedges.**
  - Nephila Climate, Allianz and REsurety pioneered proxy revenue swaps and proxy-generation PPAs. AGCS and Nephila signed a pgPPA "intended to manage weather related risk" for Lightsource bp's 153 MW Briar Creek project in Texas (Jan 2021), the first pgPPA for a US solar project. Settlement is on a proxy-generation index, not metered output.
  - kWh Analytics' Solar Revenue Put guarantees up to 95% of expected energy and covers irradiance shortfall among other perils. It had insured "nearly 3GW" by Nov 2022 (company release, via search; page blocked).
  - No public pricing or terms were found for any of these. No 2025-2026 ERCOT solar-volume deal announcements were found.
- **Why it matters.** Solar is a large, ECP-qualifying wet-side loser in exactly the rancher's months and region. It already buys from the same capital (Nephila) that backs Demex's two-sided snow book. This El Niño winter it is also the buyer most likely to lift underpriced wet calls (doc 25: south-central wet calls pay 1.35x after El Niño). It belongs in doc 25's matrix as a wholesale wet-side counterparty, scored above feedlots (inference).

### 1b. Harvest-season wet losers

- **Louisiana sugarcane (Oct-Jan harvest).** After two rainy weekends in 2015, sugar recovery fell "about 10 to 20 percent" (LSU AgCenter's Gravois). Those weekends brought about the 15-16 inches a whole harvest normally gets. About 380,000 acres were harvested for 11 mills. The 2024 crop was 536,482 acres, valued at $1.579B at first processing (LSU). Kalshi lists a New Orleans monthly rain series (`KXRAINNOLAM`, opened Oct 26), so a mill-level wet-harvest call is technically listable. No sugarcane weather hedging was found.
- **Texas cotton (harvest into December).** Rain on open bolls causes seed sprouting, staining, a dingy color and a second defoliation. "Poor quality will be reflected in discounted cash prices" to individual growers, not in futures (Texas Farm Bureau, Farm Progress; old seasons, mostly 2016 and 2018). No dollar figure or hedging was found. The loss is a grade discount after classing, which is hard to index to a monthly airport total (inference).
- **Pecans (Nov-Jan, TX/NM/GA).** Wet weather delays harvest and lowers quality. In clay-soil Las Cruces orchards, December rain makes fields inaccessible "until substantial drying takes place" (Farm Progress, undated). One unattributed report put losses at 70M lb (GA), 75M lb (NM) and 30M lb (TX); its year and cause could not be verified, so it is not used.
- **Rice.** The Gulf harvest is Aug-Oct, outside Nov-Feb, so it is not pursued.
- **Takeaway.** These are real wet-side losers in the right months, but they are farmers with federal crop insurance, mostly not ECPs, and exposed to day-timing and quality rather than monthly totals. Sugar mills (cooperatives in Louisiana) are the only entity-scale candidate (inference).

### 1c. Drought winners who lose in wet years

- **Irrigation makers.**
  - Lindsay's FY2026 10-K: "Demand for irrigation equipment is often positively affected by ... prolonged periods of drought ... Conversely, demand ... can be negatively affected during periods of more predictable or abundant natural precipitation." Weather "particularly leading up to the planting and early growing season" drives purchases.
  - Lindsay's derivatives cover only interest rates and FX. North America irrigation revenue was $262.1M in FY2026.
  - The exposure is spring and multi-year, not Nov-Feb monthly, and unhedged. Valmont (CIK 102729, FY2025 10-K filed 2026-02-24) was not read.
- **Water utilities.** Austin Water collected $37.2M in Q1 FY2010, a $12M shortfall, citing restrictions, heavier rainfall and the economy. A separate undated item cites a $3.7M shortfall from a wet winter. Austin holds a 120-day Water Revenue Stability Reserve: it uses reserves, not hedges, matching doc 25's city-snow finding. A 2014 Alliance for Water Efficiency white paper covers weather hedges for water utilities. No Texas water utility weather hedge was found.
- **Hay sellers.** National all-hay prices were up 43% year on year in June 2011, with alfalfa at a record $180-186 a ton. Texas Panhandle hay reached $410 a ton in Jan 2023. Hay sellers are the cleanest "same-index" wet-side loser: the rancher's drought loss is largely the hay seller's gain (inference). They are small, many are ranchers themselves, and no hedging was found.

## 2. Capital supply: who backs weather risk, at what load

- **Capital is at record levels.**
  - Aon: global reinsurance capital about $800B at June 30, 2026, with record alternative capital of $144.5B. Cat bond issuance over the 12 months to June 30, 2026 was $24.9B.
  - Artemis: cat bonds outstanding passed $66B (Nov 17, 2026), with 2026 issuance over $20.37B.
- **Price of risk is falling.**
  - AM Best via Artemis: average cat-bond loss multiple 2.5x in H1 2026, down from 3.28x in H1 2025; 2026 year to date 2.4x against 3.0x for 2025 and 3.71x for 2024.
  - An Artemis piece cited by search put the Q3 spread at 4.89% over 2.61% expected loss, about 1.9x (not opened; secondary).
- **Nephila.**
  - Third-party AuM of $7.9B (Jun 30, 2026). Fund-management revenue of $120.3M in 9M 2026, up about 42%.
  - Markel-fronted premium ceded to Nephila fell to $1.0B in H1 2026 from $1.7B in H1 2025. Artemis ties that to softening property-cat pricing.
  - Nephila Climate runs renewable volume, shape and price hedges, including a newer hourly wind-volume index product.
- **Loads.** No public loading for small, frequent weather risks was found. Cat-bond multiples of 2-4x apply to remote tails (expected loss about 2-3%). The rancher's 30th-percentile put pays in about 24% of months (`p_mm_loss`, doc 25 netting CSV), and doc 25 assumes 1.2x for it. Applying cat-bond multiples to frequent monthly rain risk would overstate cost (inference). Doc 25's own sources say pilot index-insurance loads run "well above 50 percent."
- **Collateral cost on Kalshi (computed, with an assumed 12% cost of equity).**

  | Book | Collateral / premium (doc 25 backtest) | Monthly carry at 12% / 0% interest | Monthly carry at 12% / 3.5% Kalshi interest |
  |---|---|---|---|
  | One put | 6.36 | 6.4% of premium | 4.5% |
  | Put + call, netted (same event, collateral return) | 2.68 | 2.7% | 1.9% |

  Against a 20% load, collateral carry is small, and interest cuts it by about 30%.
- **Is pairing solving the wrong problem?** Mostly yes (inference). Capital is abundant and cheapening, and Kalshi already nets same-event collateral and pays interest. The pairing's capital saving is worth about 2-4% of premium a month. The binding constraints are demand (doc 25: wet:dry 1:80), order-book depth (doc 22) and origination. That supports doc 25's #1 (wholesale Companion plus structuring software) and argues against building any capital-intensive two-sided book.

## 3. Kalshi mechanics

- **Interest.** Kalshi help, dated Oct 20, 2026: "Rate: 3.50% APY. This rate is variable." It applies to net portfolio value, "including available account funds and open positions valued at last traded prices." It accrues daily at 12am ET and is paid monthly. It needs an average monthly balance of $250 and an SSN for interest over $10 a year, and is US only.
  - The launch rate was 4.05% (Kalshi blog). Third-party sites cite 3.75% (Sept 2026, secondary).
  - Perps can earn 7% under a capped program. It is irrelevant to rain.
- **Comparison.** The 3-month constant-maturity Treasury was 4.21% on 2026-11-02, with fed funds at 3.75-4.00% after the Oct 28 FOMC. ForecastEx pays an "incentive coupon" at IBKR's benchmark minus 50 bp. IBKR pages quoted 3.14% and 3.83% APY at different times (IBKR pages blocked; via search).
- **Collateral return.**
  - Kalshi help: the feature is opt-in, "disabled by default for new users," and covers "mutually exclusive and directional" market groups. The directional example is YES on a lower threshold at 80¢ plus NO on a higher one at 70¢, with a maximum loss of $0.50.
  - Restrictions: "Enabling this feature may make you unable to sell positions." The setting is locked per event and subaccount at the first order; a workaround is to create an API subaccount.
  - The Kalshi API returns `collateral_return_type: DIRECNET` for every monthly rain event checked: Dallas Sep 2025 through Nov 2026; OKC, SAT and NYC Nov 2026.
- **Listing lead time (computed from the repo's `kalshi_rain_markets.parquet`, 187 events).**
  - The median event opens about 1 day before its month. Nov 2025-Feb 2026 events opened at 04:55 UTC on the 1st, about 23:55 ET the night before.
  - 2024-25 events opened 3-4 days ahead. Nov 2026 events opened Oct 2 for 14 cities and Oct 26 for 20 more, including OKC and SAT, about 30 days ahead.
  - Only Napa (Dec 1-31, opened Oct 2) and NYC Dec 2026 were listed for December as of the data pull. The live API on Nov 20 has no `KXRAINDALM-26DEC`.
- **Implications.**
  - A seasonal Nov-Feb hedge cannot be locked in during the PRF sign-up window, which closes Dec 1.
  - Collateral is tied up about one month per contract.
  - Prices already reflect the ENSO state by the time any month lists.
  - Doc 25's adverse-selection worry applies to a maker quoting on climatology. A farmer on Kalshi never gets a pre-forecast price.
- **Demand context.** Kalshi weather volume was $564M through July 2026 (WSJ via Benzinga), above all of 2025, and is "tracking toward $1.1 billion" annualized, up about 500%. The Weather Company's weather.com and app began showing Kalshi probabilities to "some users" (Aug 2026). Most of the rain-book counterparty flow is likely retail speculation arriving through Robinhood, Coinbase (all 50 states via Kalshi since Jan 28, 2026) and weather.com (inference). That is the real "wet side" a farmer trades against today.

## 4. PRF insurers (AIPs)

- **Loss ratios (computed from RMA Summary of Business `sobcov`, commodity 0088).**

  | Year | TX premium / indemnity | TX loss ratio (producer LR) | US loss ratio |
  |---|---|---|---|
  | 2011 | $58M / $131M | 2.25 (5.02) | 1.62 |
  | 2020 | $130M / $128M | 0.98 | 1.29 |
  | 2021 | $159M / $173M | 1.09 | 1.15 |
  | 2022 | $181M / $247M | 1.37 (3.00) | 1.35 |
  | 2023 | $225M / $221M | 0.98 | 0.84 |
  | 2024 | $238M / $201M | 0.84 | 0.91 |
  | 2025 | $253M / $274M | 1.08 | 1.02 |

  - Oklahoma's 2022 loss ratio was 1.30. PRF was 8-15% of Texas all-crop premium in 2020-2025.
  - UNL/RightRisk gives national 2022 PRF premium as $1.07B with a loss ratio of 1.34 (producer 2.87), and a 2018-22 producer loss ratio of 2.41. That is a different snapshot from the SOB file's $973M.
  - Texas all-crop loss ratio was 2.14 in 2022. AM Best's MPCI combined ratio for 2022 was 102.8%.
- **Winter concentration (computed, `sobtpu` practice codes).** Texas Nov-Dec plus Jan-Feb liability share is 27.4% in 2025 and 27.6% in 2022; premium share is 32.5% and 33.1%. Oklahoma is 26.3% of liability. Uniform allocation would be about 18% for two of 11 intervals. Texas winter-interval loss ratio, 2018-2025: 1.18, 1.34, 0.83, 1.47, 1.26, 0.80, 0.38 and 1.75. The pooled ratio is 1.11, against 1.02 for the other intervals.
- **SRA risk sharing (2027 SRA, July 1, 2026 version).**
  - Assigned Risk Fund: the company retains 20%, capped at 75% of its net book premium per state. Retained underwriting loss is 7.5% of the 100-160% loss-ratio band, 6% of 160-220% and 3% of 220-500%; FCIC takes 100% above 500%.
  - Commercial Fund: at least 35% retention, in 5% steps. In State Groups 2 and 3, which include Texas and Oklahoma, retained loss is 42.5% / 20% / 5% of the same bands.
  - There is also a 6.5% net book quota share to FCIC.
- **Retained exposure (computed).**

  | Case | Commercial Fund, 100% retention | Commercial Fund, 35% retention | Assigned Risk Fund |
  |---|---|---|---|
  | 2025 Texas winter PRF ($83M premium, LR 1.75) | ≈$24M | ≈$8M | ≈$1M |
  | 2011-type year (LR 2.25) on all 2025 Texas PRF ($253M) | ≈$95M | ≈$33M | ≈$4M |

  AIPs also keep underwriting gains in good years.
- **Their own reinsurance.** AIPs buy private quota share and stop loss on retained books. Insurance Insider reports that M&A among primary crop writers has cut quota-share demand (paywalled; headline only). No PRF-specific reinsurance figures were found.
- **Verdict (inference).** AIPs are dry-side buyers in the same months, so they deepen the dry imbalance rather than offset it. Their marginal demand for Kalshi puts is small because the ARF and FCIC's high-band sharing are far cheaper. They also hold statewide grid exposure, which a basket of 6-8 Kalshi stations would track better than any single farm. They are a plausible structuring-software client, not a counterparty.

## 5. Other venues and consumer guarantees

- **ForecastEx (IBKR).** It lists Daily Precipitation Forecast Contracts; the CFTC filing of Aug 12, 2026 amended the region list, which per search includes Atlanta and Austin. Payout is a binary "precipitation occurs in region on date." It pays an incentive coupon (§3). It has no monthly totals, so it is a venue-type product, not a rancher hedge.
- **Polymarket.** It runs monthly NYC Central Park precipitation bins, with volume of $17.4K (May 2026) and $7.2K (June 2026) per Lines.com snapshots. No Texas rain markets were found. Polymarket US operates as an intermediated DCM after acquiring QCEX, and no weather self-certification was found (secondary sources).
- **Coinbase.** Kalshi-powered prediction markets went live in all 50 states on Jan 28, 2026. Coinbase help lists a weather category resolved on NWS data. Robinhood is already in `market_maker_model.md`.
- **CME.** A monthly CDD page exists. No 2025-26 weather volume figures were found. Doc 25 already covers the rain and snow delisting.
- **Sensible Weather take-up (validates embedded consumer demand, not the restaurant guess).**
  - Attach rates: about 30-31% of Tentrr guests in 2022 or the first full year (Sensible-sourced); about 12% of bookings at one partner (2023, via Pressreader/Bloomberg); "approaching 50%" in early channels (CEO, TechCrunch 2022).
  - Inntopia reports a 5-19% conversion lift from offering the guarantee.
  - Golf: launched at 23 Myrtle Beach courses (Oct 2023, PGA of America partnership), Troon Partners Network (2024), GolfNow (Jan 2025) and Courserev (Aug 2025). It refunds green fees automatically when "rainfall surpasses a pre-set threshold."
  - The Tentrr reimbursement is described as triggered when rain is forecast for the stay, so payouts follow forecasts, not settled totals (per search summaries of the Tentrr release; page blocked).
  - Implication: 12-31% attach for a consumer-paid, checkout-embedded refund is 6-15x doc 25's 2%. Doc 25's 2% is for a firm buying protection for itself, and nothing here contradicts that. Golf's "no hedging found" should become "risk transferred by golfers via Sensible, not by courses."

## Open items

- Valmont 10-K weather language (not read).
- Public pricing for solar volume hedges.
- ARF usage share for PRF.
- Texas PRF winter share for the 11 sample farms against statewide.
- Whether Kalshi's DIRECNET netting applies across a YES/NO pair placed by two different subaccounts. Per the help text, it is locked per subaccount.

## Numbers table

| Number | Source |
|---|---|
| Kalshi interest 3.50% APY on cash + open positions at last price; $250 avg balance; daily accrual, monthly pay; article dated 2026-10-20 | https://help.kalshi.com/en/articles/13823847-apy-on-kalshi |
| Kalshi launch interest rate 4.05% | https://kalshi.com/blog/article/interest-cash-open-positions (via search) |
| Collateral return: opt-in, mutually exclusive and directional groups; 80¢ YES + 70¢ NO max loss $0.50; locked per event/subaccount | https://help.kalshi.com/en/articles/13823816-collateral-return |
| Collateral return original announcement (2022-12-01), mutually exclusive NO example $1.30 cost, $0.30 max loss | https://news.kalshi.com/p/collateral-return |
| Monthly rain events `collateral_return_type` = DIRECNET (DAL Sep 2025-Nov 2026; OKC, SAT, NYC Nov 2026) | https://api.elections.kalshi.com/trade-api/v2/events?series_ticker=KXRAINDALM ; https://api.elections.kalshi.com/trade-api/v2/events/KXRAINDALM-26NOV (fetched 2026-11-20) |
| MECNET/DIRECNET events get no settlement floor (only mention in docs) | https://docs.kalshi.com/getting_started/settlement_bounds |
| Rain event listing lead: median about −1 day; Nov 2026 opened Oct 2 (14 cities) and Oct 26 (20 cities); no KXRAINDALM-26DEC on Nov 20 | repo `data/processed/kalshi_rain_markets.parquet` (computed); https://api.elections.kalshi.com/trade-api/v2/markets?event_ticker=KXRAINDALM-26DEC |
| Collateral / premium: one put 6.36, one call 4.49, netted pair 2.68 | repo `data/processed/expansion_netting_summary.csv` (`collateral_per_prem`) |
| Monthly collateral carry 4.5% (put) / 1.9% (pair) of premium at 12% cost of equity, 3.5% interest | computed; 12% is an assumption |
| 3-month Treasury 4.21% (2026-11-02) | https://fred.stlouisfed.org/series/dgs3mo (via search) |
| Fed funds 3.75-4.00% after 2026-10-28 FOMC | https://www.federalreserve.gov/newsevents/pressreleases/monetary20261028a.htm (via search) |
| ForecastEx coupon = IBKR benchmark − 50 bp; quoted 3.14% / 3.83% APY | https://www.interactivebrokers.com/support/faq/content/forecastex-forecast-contracts-offer-incentive-663032988 (403; via search) |
| ForecastEx Daily Precipitation Forecast Contracts amended 2026-08-12, effective 2026-08-26 | https://www.cftc.gov/filings/orgrules/rules08122616577.pdf |
| ERCOT solar 34 GW, 237 farms (EIA-860M, Nov 2026) | https://www.cleanview.co/power-projects/operating/solar-farms/ercot (via search) |
| ERCOT solar 35.998 GW end Q1 2026 | https://www.spglobal.com/energy/en/news-research/latest-news/electric-power/062626-us-solar-tracker-additions-expected-to-reach-an-all-time-high-of-38-gw-in-2026 (via search) |
| ERCOT solar synced 4.49 GW Jan-Sep 2026 (−19%); 2026 forecast 6.8-8.4 GW; West/Far West 40% of queue, 23% of builds since 2023 | https://modoenergy.com/research/en/ercot-generation-buildout-queue-q3-2026 (via search) |
| ERCOT winter average solar output 1.9 GW (2022-23), 3.3 GW (2023-24); TX capacity about 16 GW in 2023 | https://www.eia.gov/todayinenergy/detail.php?id=61783 |
| South Texas Dec 2023 irradiance up to +30%; TX utility solar output +20% vs long-term average | http://pv-magazine-usa.com/2024/01/05/texas-solar-generation-surges-amidst-north-americas-contrasting-december-patterns/ |
| Nov-Feb GHI vs rain r = −0.39 to −0.55; wet-tercile GHI −5.2 to −7.5%; SD 11.6-12.6% | computed: https://power.larc.nasa.gov/api/temporal/monthly/point (ALLSKY_SFC_SW_DWN, 1984-2024) + repo `station_monthly_precip.csv` |
| Fleet rain-hedgeable winter swing about $5-8M per month | inference from the rows above; $30/MWh and 17% capacity factor are assumptions |
| Briar Creek 153 MW Texas pgPPA, AGCS + Nephila Climate, 2021-01-08 | https://www.reinsurancene.ws/allianz-agcs-nephila-provide-hedge-structure-for-texas-solar-project/ |
| Proxy revenue swap: fixed quarterly payment vs proxy generation index | https://www.projectfinance.law/publications/2018/june/proxy-revenue-swaps-for-solar |
| kWh Analytics Solar Revenue Put: up to 95% of expected output; nearly 3 GW insured (2022) | https://www.businesswire.com/news/home/20221108005454/en (403; via search) |
| Louisiana sugarcane: recovery −10 to −20% after rain; 15-16 in. typical season rain; 380,000 acres; 11 mills (2015) | https://apps.lsuagcenter.com/news_archive/2015/November/headline_news/Rain-plays-havoc-with-sugarcane-harvest.htm |
| Louisiana sugarcane 2024: 536,482 acres; $1.579B value | https://www.lsuagcenter.com/profiles/lblack/articles/page1785772314716 (via search) |
| Cotton: wet-harvest quality loss shows in discounted cash prices to growers | https://www.farmprogress.com/crops/wet-conditions-continue-to-slow-cotton-harvest-reduce-quality ; https://texasfarmbureau.org/rains-stain-texas-cotton-cause-mold-produce-sprouts-in-bolls/ |
| Pecans: December rain blocks access to Las Cruces clay-soil orchards | https://www.farmprogress.com/orchard-crops/in-new-mexico-it-is-not-good-nutty-weather |
| Lindsay: demand falls with "abundant natural precipitation"; derivatives only rates and FX; NA irrigation revenue $262.1M FY2026 | https://www.sec.gov/Archives/edgar/data/836157/000119312526428926/lnn-20260831.htm |
| Austin Water Q1 FY2010 $37.2M collected, $12M shortfall (heavier rain cited) | https://www.austinmonitor.com/stories/2010/02/austin-water-utility-facing-fy2010-budget-shortfall/ |
| Austin Water 120-day Revenue Stability Reserve | https://www.austintexas.gov/sites/default/files/files/Water/WaterForward/FY20%20Water%20Forward%20Annual%20Report.PDF (via search) |
| All-hay +43% YoY (Jun 2011); alfalfa $180 (NASS) / record $186 (May 2011) | https://www.dairyherd.com/news/hay-prices-continue-higher ; https://www.bloomberg.com/news/articles/2011-07-25/drought-withers-smallest-u-s-hay-crop-in-a-century-to-boost-cost-of-beef |
| Texas Panhandle hay $410/ton (Jan 2023) | https://agrilifetoday.tamu.edu/2023/02/01/hay-supplies |
| Reinsurance capital about $800B; alternative $144.5B; cat bonds $24.9B in 12 months to 2026-06-30 | https://www.reinsurancene.ws/record-800bn-reinsurance-capital-offers-insurers-growth-opportunities-heading-into-1-1-aon/ ; https://aon.mediaroom.com/2026-08-28-ILS-Becomes-Foundational-Reinsurance-Capital-as-Sector-Reaches-New-Heights-Aon-Report (via search) |
| Cat bonds outstanding over $66B; 2026 issuance over $20.37B (2026-11-17) | https://www.artemis.bm/news/cat-bond-issuance-hits-20bn-at-fastest-pace-in-2026-market-size-exceeds-66bn-for-first-time/ |
| Cat bond multiple 2.5x H1 2026 vs 3.28x H1 2025; 2.4x YTD 2026 vs 3.0x (2025), 3.71x (2024) | https://www.artemis.bm/news/as-cat-bond-loss-multiples-tighten-am-best-urges-investors-towards-greater-selectivity/ |
| Q3 2026 spread 4.89% vs expected loss 2.61% (about 1.9x) | https://www.artemis.bm/wp-content/uploads/2026/09/How-Soft-is-the-Soft-Market-9_28_2026.pdf (via search; not opened) |
| Nephila AuM $7.9B (2026-06-30); 9M 2026 revenue $120.3M; fronted premium $1.0B H1 2026 vs $1.7B | https://www.artemis.bm/ils_fund_managers/nephila-capital/ ; https://www.artemis.bm/news/nephila-capital-ils-fund-revenues-keep-rising-even-as-soft-market-evident-in-fronted-premium/ (via search) |
| PRF TX / OK / US premium, indemnity, loss ratio 2011 and 2020-2025 | computed from https://pubfs-rma.fpac.usda.gov/pub/Web_Data_Files/Summary_of_Business/state_county_crop/sobcov_{year}.zip (commodity 0088) |
| TX Nov-Dec + Jan-Feb PRF: 27.4% liability, 32.5% premium (2025); winter loss ratio by year; pooled 1.11 vs 1.02 (2018-25) | computed from https://pubfs-rma.fpac.usda.gov/pub/Web_Data_Files/Summary_of_Business/state_county_crop/sobtpu_{year}.zip (practice codes 4xx/5xx/6xx intervals) |
| TX+OK Jan-Feb PRF liability share by crop year 13.0-15.5% | same files (computed); ONI from repo `scripts/experiments/expansion_review/dl/oni.txt` |
| National PRF 2022: $1.07B premium, LR 1.34, producer LR 2.87; 2018-22 producer LR 2.41 | https://cap.unl.edu/news/pasture-rangeland-forage-insurance-summary-sales-and-performance-history/ |
| 2022 MPCI combined ratio 102.8%; TX/OK loss ratios over 200% | https://www.reinsurancene.ws/us-crop-insurance-premiums-reach-record-high-in-2022-widespread-drought-drives-losses-am-best/ (via search) |
| SRA 2027: ARF 20% retention, 75% cap; ARF loss shares 7.5/6/3%; Commercial at least 35%; Group 2-3 shares 42.5/20/5%; TX and OK in Group 2; 6.5% net book quota share | https://www.rma.usda.gov/sites/default/files/2026-03/SRA_2027.pdf |
| AIP retained loss, TX winter PRF 2025: about $24M / $8M / $1M | computed from the SOB and SRA rows above |
| PRF sales closing Dec 1 (2027 crop year) | https://www.farmcrediteast.com/about/NewsRoom/press-releases/20251008-ReminderPastureRangelandForageSalesClosingDeadlineIsDecember1 ; https://www.rfdtv.com/producers-urged-to-review-prf-insurance-ahead-of-deadline |
| Crop M&A cutting quota-share demand | https://www.insuranceinsider.com/article/2876fnf4db62x2rbjcdu7/m-a-causes-us-crop-reinsurance-premium-drought (headline) |
| Kalshi weather volume $564M through Jul 2026; $1.1B expected 2026; +500% | https://www.webull.ca/news-detail/15475678967514112 (Benzinga 2026-08-27, citing WSJ) |
| Weather.com shows Kalshi probabilities to some users; about $1.1B annualized | https://www.claimsjournal.com/news/national/2026/08/31/339851.htm |
| Coinbase prediction markets (Kalshi) in all 50 states, 2026-01-28 | https://www.theblock.co/news/markets/2026-01-28-coinbase-prediction-markets-go-live-in-all-50-us-states-via-kalshi-387416 |
| Polymarket NYC monthly precipitation; $17.4K (May 2026), $7.2K (Jun 2026) volume | https://polymarket.com/event/precipitation-in-nyc-in-june ; https://www.lines.com/prediction-markets/science/precipitation-in-nyc-in-may (via search) |
| Sensible attach: 30-31% Tentrr; about 12% one partner; "approaching 50%" CEO | https://issuu.com/parksmanagement1/docs/gba_february_2023/s/19379552 ; https://www.pressreader.com/south-africa/business-day/20230405/281715503887252 ; https://techcrunch.com/2022/05/05/it-is-like-raaaaaaaaaaain-on-your-wedding-day/ (via search) |
| Inntopia: guarantee lifts conversion 5-19% | https://corp.inntopia.com/commerce/sensible-weather/ (via search) |
| Sensible golf: 23 Myrtle Beach courses (Oct 2023); Troon (2024); GolfNow (Jan 2025); Courserev (Aug 2025); green-fee refunds on rainfall threshold | https://businesswire.com/news/home/20231023600378/en/Sensible-Weather-Launches-Weather-Guarantees-at-23-Golf-Courses-Following-Partnership-With-PGA-of-America ; https://troon.com/press-releases/troon-partners-network-announces-sensible-weather-as-official-weather-protection-provider ; https://coverager.com/golfnow-adds-weather-protection-for-tee-time-bookings/ ; https://thegolfwire.com/courserev-sensible-weather |
