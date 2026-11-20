# Weather-Risk Market Maker / Opposite-Side Matching Platform: Business, Market-Structure and Regulatory Feasibility

Research date: 2026-11-19. Figures carry their year. "Unverified" means a source was not found or not opened. Internal project findings (docs 08-09, 12, 16, 21-22 in `docs/analysis/`) are cited as internal.

## 1. Market size and structure of the existing weather-risk market

### Takeaway
The OTC/exchange weather-derivative market has been energy-dominated and cyclical. WRMA/PwC surveys peaked at about $45B notional (2005-06) and fell to roughly $12-15B by 2009-2011, and no newer WRMA survey was found. The growth since 2024 is in parametric insurance (market-research estimates of $3.5-19B, depending on definition) and in retail event contracts. Kalshi's climate/weather category was pacing about $1.1B annualized volume in 2026, still only a small share of a sports-dominated platform.

### Cited Findings
**WRMA / PwC survey history (all dated; the series appears to end around 2011)**
- 2002 survey: 3,937 contracts, $4.3B notional. The next survey nearly tripled the contract count while notional dipped to $4.2B — [Business Insurance / risk.net coverage via search results](https://www.businessinsurance.com/number-uses-of-weather-risk-contracts-expanding/)
- Notional rose from $9.7B (April 2005) to $45.2B (March 2006), about 5x — [Canadian Underwriter](https://www.canadianunderwriter.ca/insurance/value-of-weather-risk-management-contracts-soars-1000054177/)
- About $19B for 2006-07, attributed to a shift from seasonal to monthly CME contracts. Then up 76% to $32B in 2007-08 — [Insurance Journal 2007](https://www.insurancejournal.com/news/national/2007/05/14/79653.htm); [Claims Journal 2009](https://www.claimsjournal.com/news/national/2009/06/03/101075.htm)
- 2008-09: notional about $15B, down 53% from $32B, with trade count down about 39% (PwC for WRMA) — [Claims Journal, 2009-06-03](https://www.claimsjournal.com/news/national/2009/06/03/101075.htm)
- 2010-11: overall market $11.8B, up about 20%. OTC-only notional $2.4B, so the exchange (CME) share dominated — [Artemis 2011](https://www.artemis.bm/news/weather-derivatives-market-grew-by-20-in-2010-2011-says-wrma/)
- Weather derivatives hedge volume (demand) risk, not price risk. The canonical example is a utility fearing a warm winter. Insurers and reinsurers (Swiss Re, Munich Re) and specialist weather firms are described as the natural counterparties — [Munich Re energy & weather](https://munichre.com/en/solutions/for-industry-clients/energy-weather.html); [Ryan O'Connell explainer](https://ryanoconnellfinance.com/weather-derivatives/)
- Empirical benefit to end users: energy firms that hedge with weather derivatives get loan spreads about 21 bp lower, using the 1997 introduction of weather derivatives as a natural experiment — [J. Business Finance & Accounting, vol. 51 (via search result)](https://onlinelibrary.wiley.com/doi/full/10.1111/jbfa.12800)

**CME**
- CME overall set a record 28.1M contracts ADV in 2025 (up 6%) and a record Henry Hub natural gas futures and options ADV of 904K. Weather-driven gas hedging was cited. No 2025 weather-futures-specific record was found — [CME 2025 annual ADV release via Barchart](https://www.barchart.com/story/news/36882764/cme-group-reports-record-annual-adv-of-28-1-million-contracts-in-2025-up-6-year-over-year); [CME Jan 2026 commodities update](https://www.cmegroup.com/newsletters/currently-in-commodities/january-2026-commodities-update.html)
- January 2006 monthly weather volume was 108,000 contracts, versus 42,000 in January 2005 — [Insurance Journal 2006](https://www.insurancejournal.com/news/east/2006/02/26/65933.htm)
- CME weather volume page (CDD monthly) exists for live data, but no figure was extracted — [CME CDD volume](https://cmegroup.com/markets/weather/temperature/us-monthly-weather-cooling.volume.html)

**Parametric insurance (market-research estimates; methodologies unverified and widely divergent)**
- $19.4B (2025), projected to $63.8B by 2035 at a 12.2% CAGR — [Global Market Insights](https://www.gminsights.com/industry-analysis/parametric-insurance-market)
- $18.24B (2025), projected to $59.75B (2035) — [DataM Intelligence](https://www.datamintelligence.com/research-report/parametric-insurance-market)
- $18B (2025), projected to $52B (2035) — [Astute Analytica](https://www.astuteanalytica.com/industry-report/parametric-insurance-market)
- $15.55B (2025), projected to $32.95B (2035) — [Market Research Future](https://www.marketresearchfuture.com/reports/parametric-insurance-Market-24564)
- $3.48B (2025), $4.02B (2026), a much narrower definition — [Research and Markets](https://www.researchandmarkets.com/reports/6260243/parametric-insurance-market-share-analysis)
- Context: Swiss Re Institute puts 2025 global nat-cat economic losses at $220B, of which $107B was insured, and projects $148B insured nat-cat losses for 2026. This is not a parametric-specific figure — [search summary of Swiss Re Institute sigma; primary not opened]

**Event-contract (retail) weather markets**
- Kalshi says its climate/weather category grew about 500% YoY and is pacing toward about $1.1B annualized volume (Aug 2026). The figure is Kalshi's own and forward-looking — [Artemis, 2026-08-28](https://artemis.bm/news/prediction-market-kalshi-partners-with-the-weather-company-for-weather-hedge-settlements)
- Weather markets reportedly reached $564M in volume through July 2026, already above the full-year 2025 total. Sports were about 83% of Kalshi's July volume — [search summary citing Action Network / CasinoBeats](https://www.actionnetwork.com/news/inside-the-boom-weather-prediction-markets)
- Daily high/low temperature and precipitation markets averaged about $3.06M/day combined (Jan 1 - Apr 20, 2026), roughly equal to UFC — [CasinoBeats 2026-04-23](https://casinobeats.com/2026/04/23/weather-markets-ufc-generate-similar-trading-volumes-kalshi-sports-still-dominate/)
- Kalshi and The Weather Company partnership (Aug 2026): TWC enterprise data feeds become the designated source for verifying weather settlements, and Kalshi probabilities appear in the Weather Channel app. Kalshi claims ice-cream shops (cool summers) and logistics firms (precipitation) hedge on the platform. Farmers are not mentioned — [Artemis 2026-08-28](https://artemis.bm/news/prediction-market-kalshi-partners-with-the-weather-company-for-weather-hedge-settlements)
- ForecastEx (Interactive Brokers' CFTC-regulated DCM) launched Aug 2024 with US/global temperature and CO2 contracts. It added daily high-temperature markets in Nov 2025, settled on airport ASOS/METAR. IBKR's own analyses (2026) claim the implied forecasts beat comparable NWS products — [IBKR launch, 2024-08-01](https://marketsmedia.com/interactive-brokers-launches-forecast-contracts); [IBKR Traders' Insight weather posts 2026](https://www.interactivebrokers.com/campus/traders-insight/prediction-market/fair-value-weather-climate-monday-august-3-2026/)

**Key players with sourced figures**
- Arbol: $60M Series B (Apr 2024, co-led by Giant Ventures and BNP Paribas' VC arm). Revenue grew nearly 50% in 2023. About $71M total funding (aggregator figure). Over $250M gross written premium transacted in 2023 (Dealroom). In 2025 it launched parametric wildfire cover backed by Lloyd's Somers Syndicate, with limits up to $10M. No 2025 revenue disclosure found — [Insurance Journal 2024-04-30](https://www.insurancejournal.com/news/national/2024/04/30/772109.htm); [Artemis](https://www.artemis.bm/news/arbol-raises-60m-to-scale-parametrics-make-climate-risk-an-investable-asset-class); [Dealroom](https://app.dealroom.co/companies/arbol); [Arbol wildfire release](https://www.arbol.io/post/arbol-launches-new-wildfire-parametric-insurance-product-to-fill-growing-coverage-gap-in-the-western-u-s)
- Sensible Weather (consumer "Weather Guarantee" embedded at booking for travel and attractions): $4M seed (Dec 2021, Wonder Ventures, Walkabout), $12M Series A (May 2022, Infinity Ventures lead; Certares, Derive, Group1001), over $20M total. Over 50,000 guarantees sold and attach rates up to 5x travel insurance, per a company claim (Oct 2023). Payouts are hourly, by hours of disruption. No post-2023 round found — [Coverager](https://coverager.com/sensible-weather-raises-12-million/); [PhocusWire](https://www.phocuswire.com/Sensible-Weather-warms-up-with-12-million-round); [Pulse 2.0](https://pulse2.com/sensible-weather-funding/amp/)

### Inferences
- The historic weather market was a dealer and reinsurer market built around energy load risk, sized in notional (tens of $B at peak), with few non-energy end users. The small-business and agriculture segments the AgriHedge platform targets were never the core.
- Retail event-contract weather volume (about $1B/yr on Kalshi in 2026) is now comparable in dollar terms to the 2010-11 OTC-only notional ($2.4B). Most of it is very short-dated (daily highs) and speculative rather than hedging. This matches the internal finding (doc 22) that monthly-rain books are thin.
- The successful companies (Arbol, Sensible) are risk-transfer intermediaries backed by (re)insurance capacity. They embed products at the point of sale or underwrite with carriers. None of them earns money by matching opposite-side end users.

### Gaps
- No WRMA survey after about 2011 was found. WRMA may have stopped publishing, or newer surveys are paywalled.
- No CME weather-futures volume figures for 2023-2026 were found in a primary source. Needs the CME monthly volume report or the weather product page.
- No sourced figures for Nephila (Nephila Climate), Descartes Underwriting, Swiss Re Corporate Solutions, Munich Re weather, Kettle or Floodbase funding and premium. From memory and unverified: Descartes raised about $120M Series B (2022), Kettle raised about $23M+ for California wildfire reinsurance, and Nephila Climate is Nephila's weather/energy unit. Verify before use.
- Polymarket weather markets: no data gathered.

## 2. Precedents: why past attempts succeeded or failed

### Takeaway
The closest precedent, WeatherBill, sold online weather contracts to small and midsize businesses across many industries. It struggled for about 3 years, then pivoted to farmers once it was on insurance paper as a licensed insurer (2010), later becoming The Climate Corporation. Monsanto bought it for $930M in 2013. It sold the crop-insurance book in 2015 to focus on data. CME's rainfall and snowfall products were delisted in 2013-2015 with zero open interest. Both precedents point to fragmented, hard-to-sell demand for multi-sector weather hedges.

### Cited Findings
- WeatherBill (2007) offered an online platform for small and midsize businesses to insure against adverse weather — [TechCrunch 2007-01-02](https://techcrunch.com/2007/01/02/use-weatherbill-to-bet-on-the-weather/amp/)
- In its first year, the team cold-called companies "from every weather-impacted industry" and floundered for about 3 years before a May 2010 pivot. Farmers would not buy unless the product was on insurance paper, so the company became a licensed insurer in 2010. By Oct 2011 it converted over 50% of farmers pitched. This is secondary analysis, and the founder quotes are reported secondhand — [Full Stack Researcher Substack](https://fullstackresearcher.substack.com/p/deconstructing-a-successful-startup-pivot?r=4swq6)
- Commentary: the market was "fragmented, sales cycles were long, and loss ratios were uncertain across niches" (secondary blog) — [Capitaly.vc](https://www.capitaly.vc/blog/weather-insurance-ag-risk-david-friedberg-climate-corp-lessons)
- The product filled a gap left by federal crop-program limits and paid automatically on weather triggers, with no field inspection — [Farm Progress](https://www.farmprogress.com/forage/the-climate-corporation-offers-precise-weather-insurance-coverage)
- Renamed The Climate Corporation, Oct 2011 — [Artemis 2011](https://www.artemis.bm/news/weatherbill-changes-company-name-to-the-climate-corporation)
- Monsanto acquisition ($930M, Oct 2013). In 2015 the crop-insurance business was sold to AmTrust so the company could focus on its digital-ag platform — [Wikipedia: The Climate Corporation](https://www.wikipedia.org/wiki/Weatherbill)
- CME snowfall futures launched 2006 for Boston and NYC. Rainfall contracts for nine US cities were announced Oct 2010 — [CME 2006 release](https://www.cmegroup.com/media-room/press-releases/2006/2/09/cme_will_launch_snowfallindexcontractsforbostonandnewyorkcity.html); [CME 2010 release](https://www.cmegroup.com/media-room/press-releases/2010/10/14/cme_group_to_launchrainfallcontractsinnineuscities.html)
- CME delisted snowfall and rainfall binary options (Dec 2013; a CFTC filing notes no open interest). It later delisted monthly and seasonal strip snowfall, rainfall and frost contracts plus hurricane chapters, with "no open interest", and delisted Canadian, Australian, Pacific Rim, and some US and European weather products in June 2015 — [CME SER-6935](https://www.cmegroup.com/tools-information/lookups/advisories/ser/SER-6935.html); [CME SER-7216](https://cmegroup.com/tools-information/lookups/advisories/ser/SER-7216.html); [CME Chadv15-158](https://www.cmegroup.com/tools-information/lookups/advisories/clearing/Chadv15-158.html)
- Kalshi now advertises weather "hedging" by small businesses (ice-cream shops, logistics) — [Artemis 2026](https://artemis.bm/news/prediction-market-kalshi-partners-with-the-weather-company-for-weather-hedge-settlements). Prof. Daniel Schwarcz (Univ. of Minnesota, former NAIC consumer representative) says "very few" users of such platforms use them to mitigate risk, and that "Small businesses are going to have a much harder time using this than large" businesses because of basis risk — [Insurance Business, 2026-11-09](https://www.insurancebusinessmag.com/us/news/catastrophe/is-a-kalshistyle-weather-contract-insurance-look-to-insurable-interest-596536.aspx)

### Inferences
- WeatherBill's arc is nearly the startup idea being evaluated: a multi-sector SMB weather marketplace. It found that (a) customer acquisition across many niches was too slow, (b) farmers trusted insurance paper over derivatives, and (c) value lay in data and distribution, not in the risk book itself. A matching platform would need a fix for each.
- CME precipitation and snow contracts dying with zero open interest (2013-2015) shows that listing standardized non-temperature contracts does not create natural hedger demand. Kalshi's 2026 precipitation growth appears speculation-driven (daily, retail), which is a different liquidity source from hedgers.

### Gaps
- No primary WeatherBill or Climate Corp statement of why the SMB product was abandoned (only secondary accounts).
- Kalshi's designated market makers for weather were not identified. Susquehanna (SIG) is publicly reported as a Kalshi market maker in general (from memory, 2024; unverified here); no weather-specific source was found.
- No data on what fraction of Kalshi weather volume is hedging versus speculation.

## 3. Natural counterparties and netting: how much of a book can be matched

### Takeaway
No published analysis or "risk-matching platform" was found that quantifies how much opposite-side end-user weather risk can be netted. The traditional market solved the other side with reinsurers, energy dealers and hedge funds, not by pairing end users. Netting requires the same index (station, variable, period, strike). Farmer drought exposure and venue wet-weather exposure rarely align in station, month and shape, so most of the book would need outside capital.

### Cited Findings
- Insurers and reinsurers (Swiss Re, Munich Re) and specialist weather-risk firms are described as the natural counterparties, because they can price weather and have capital to absorb it — [Munich Re](https://munichre.com/en/solutions/for-industry-clients/energy-weather.html); [explainer](https://ryanoconnellfinance.com/weather-derivatives/)
- Weather cannot be priced by Black-Scholes or no-arbitrage methods because the underlying (temperature) is not traded, so dealers must hold model risk or find offsets — [explainer](https://ryanoconnellfinance.com/weather-derivatives/)
- OTC-only notional was a small share ($2.4B of $11.8B) in 2010-11, meaning most risk was laid off on exchange — [Artemis 2011](https://www.artemis.bm/news/weather-derivatives-market-grew-by-20-in-2010-2011-says-wrma/)
- Internal: in AgriHedge's target months (Nov-Feb, the farm-companion window), airport rain is the settlement index, and books are thin. 5-10x the saved depth would be needed to restore the uncapped fit — internal doc 22 (`docs/analysis/`), doc 21

### Inferences
- An exchange order book already nets opposite views automatically: a farmer buying "rain below X at station S in month M" is matched by anyone selling that, including a venue that wants "rain above X". A matching platform therefore adds value only by (a) aggregating many small orders into standard strikes, or (b) warehousing the mismatch, which is underwriting.
- Seasonal mismatch: farmers in the companion buy Nov-Feb dry protection, while outdoor restaurants and venues need warm-season (Apr-Oct) wet protection. Ski resorts (low snow) and snow-plow contractors (high snow) do share a season and a variable, so they are the most natural pairing. Even there, plow contractors are paid on events and inches, ski resorts on season snowpack and temperature, so shapes differ. The netted share of a book is likely small without a common index design. This is an inference; no study was found.
- The residual must be backed by reinsurance or an ILS fund (Nephila- or Arbol-style), or laid off on Kalshi or CME. That makes the startup a capacity-dependent MGA or dealer rather than a pure matcher.

### Gaps
- No academic or industry study was found quantifying cross-sector weather-exposure correlation or achievable netting ratios (searched "natural counterparties offsetting exposures"). Classic references (Considine 2000; Brockett, Wang & Yang 2005; Vedenov & Barnett 2004) were not opened. A targeted Google Scholar pass is still needed.
- No information on any live "risk-matching" weather platform (for example, peer-to-peer weather swaps).

## 4. Market-maker economics on event contracts

### Takeaway
On Kalshi, standard maker orders pay no fee and takers pay ceil(0.07·C·P·(1−P)). A maker earns the spread plus liquidity-incentive rebates and carries inventory and adverse-selection risk. Designated market makers get reduced fees and adjusted position limits in exchange for quoting obligations. CFTC scrutiny in 2026 led Kalshi to end its volume-incentive program early. For monthly precipitation, subseasonal forecast skill is low (CPC: temperature skill about 3x precipitation at weeks 3-4), so early-month adverse selection is limited. Informed flow concentrates in the last ~2 weeks, when deterministic forecasts become skillful.

### Cited Findings
**Fees (third-party summary, "last verified Nov 4, 2026")**
- Taker fee = ceil(M × 0.07 × C × P × (1−P)). Maker fee = ceil(M × 0.0175 × C × P × (1−P)). The standard taker M = 1 and the standard maker M = 0, so makers pay nothing. Some markets use non-standard multipliers (for example, US gas price markets carry a maker M = 1) — [BettingUSA Kalshi fees, 2026](https://www.bettingusa.com/prediction-markets/reviews/kalshi/fees/)
- Examples: taker fee at P = $0.50 is $1.75 per 100 contracts; at P = $0.10 or $0.90 it is $0.63 per 100. There is no settlement fee. ACH deposits and all withdrawals are free; card deposits cost up to 2% — [BettingUSA](https://www.bettingusa.com/prediction-markets/reviews/kalshi/fees/)

**Market Maker Program (Kalshi help center, 2026-04-28)**
- Requires "consistent, two-sided liquidity" and defined quoting and volume requirements. Benefits are reduced fees and adjusted position limits. Status is granted after review of financial resources, trading experience and reputation. Listed products include KXINX, KXBTC, KXNBA and KXCPI (weather not listed). The availability requirement is 98% of each 1-hour increment. Market makers bear their own trading risk — [Kalshi Help: Market Maker Program](https://help.kalshi.com/en/articles/13823819-kalshi-api)

**Incentive programs and CFTC scrutiny (2026)**
- The Liquidity Incentive Program pays for qualifying resting orders that improve the book, even if they never fill. It was filed Aug 2025 and amended Feb 2026 — [Kalshi Help, Volume Incentive Program](https://help.kalshi.com/faq/what-is-the-volume-incentive-program); [CFTC filing Feb 2026](https://www.cftc.gov/sites/default/files/filings/orgrules/26/02/rules02112639183.pdf)
- CFTC DMO advisory (Aug 12, 2026) warned that volume-based incentives risk wash and prearranged trading. On Sept 28 Kalshi filed to end the Volume Incentive Program on Oct 13 instead of Oct 1, 2027. Members with market-maker agreements were excluded from volume rewards. The CFTC was reported reviewing incentives industry-wide (Oct 22) — [DeFi Rate](https://defirate.com/news/kalshi-volume-rewards-cftc-scrutinizes-prediction-markets/)
- Commentary on liquidity rewards enabling small ("garage-band") market makers — [fiftycentdollars Substack](https://fiftycentdollars.substack.com/p/kalshis-new-liquidity-incentives)

**Forecast skill (adverse selection)**
- CPC (April 2026): week 3-4 operational temperature and precipitation outlooks are skillful on average, but temperature skill is roughly 3x precipitation skill. Some regions and seasons show no skill — [CPC/Gottschalck, 49th CDPW, 2026-04-29](https://www.weather.gov/media/climateservices/S2S-CDPW49th-W34-20260429-Gottschalck.pdf)
- Multimodel study: at weeks 3-4, near-surface temperature skill is considerably higher than precipitation skill — [NOAA repository](https://repository.library.noaa.gov/view/noaa/54496/noaa_54496_DS1.pdf)
- Week 3-4 precipitation skill is highest on the US East Coast and Southwest in winter, and only modestly linked to ENSO and the MJO — [core.ac.uk study](https://core.ac.uk/download/161458479.pdf)
- ForecastEx claims its market-implied daily high-temperature forecasts beat comparable NWS products (broker's own analysis, 2026). This means short-dated markets are populated by forecast-informed traders — [IBKR Traders' Insight](https://www.interactivebrokers.com/campus/traders-insight/prediction-market/fair-value-weather-climate-monday-august-3-2026/)

### Inferences
- Spread revenue arithmetic (illustrative, not sourced): at a 2¢ quoted spread, a maker earns about 1¢ per contract per side filled. Gross spread income per station-month is roughly 0.01 × (contracts traded against the maker). The depth figures to plug in are in internal docs 12 and 22 (saved order-book snapshots), which were not re-read for this note. Given those books are thin, spread income alone looks too small to fund a business without incentive rebates or much larger hedger flow.
- Taker fees fall on hedgers: a farmer lifting 1,000 contracts at P = 0.2 pays about 0.07 × 0.16 × 1,000 ≈ $11.20. That is small next to the internal finding of a ~1.8x premium over subsidized PRF, which comes mostly from spread and price load, not exchange fees.
- Inventory risk: a monthly-rain maker holds a binary that resolves 0/1 at month end. Inventory cannot be hedged with a related liquid instrument (unlike HDD versus nat gas), so risk must be diversified across stations and months or capitalized. Adverse selection is low at the month's start (low S2S precipitation skill) but rises sharply in the final ~7-10 days, when deterministic forecasts and partial accumulated rain are known. Makers should widen or pull quotes as the month progresses. Temperature markets face more informed flow throughout.
- Regulatory risk to the incentive model: the CFTC's 2026 scrutiny means rebate-subsidized market making is not a dependable revenue line.

### Gaps
- Kalshi's official fee schedule PDF was not opened. Fee multipliers specific to weather (KXRAIN*/KXHIGH*) are unverified.
- The size of Kalshi liquidity-incentive pools for weather markets was not found.
- Market-maker capital requirements on Kalshi (minimum financial resources) were not published in the help page.
- No public P&L data for any event-contract market maker.

## 5. US regulatory path for a small company offering weather hedges

### Takeaway
There are three routes. (a) Route customers to an existing DCM (Kalshi or ForecastEx) as an introducing broker or FCM, as Robinhood, Webull and Moomoo do; this needs NFA registration and suits non-ECP farmers and restaurants. (b) Act as an insurance producer or MGA with a fronting carrier, as WeatherBill, Arbol and Sensible did; this suits buyers who want "insurance paper" and payouts tied to their own loss. (c) Offer OTC swaps directly; this is limited to eligible contract participants (entities with over $10M assets, or over $1M net worth when hedging), which excludes most small restaurants. Whether a weather contract sold to a restaurant is "insurance" turns on the CFTC/SEC insurance safe harbor: insurable interest, risk of loss and payment limited to loss. Area-wide parametric triggers look like swaps. The 2026 state-versus-Kalshi litigation concerns sports, but the circuit split on CEA preemption is a live risk for any DCM-based model.

### Cited Findings
**Swap versus insurance**
- Dodd-Frank: a swap "shall not be considered to be insurance" and may not be regulated as insurance under state law. Derivatives fall under the CEA and CFTC, and insurance falls under state commissioners — [NatLawReview, Weather & Climate Risk Mgmt Part III (via search summary)](https://natlawreview.com/node/271309/printable/print)
- The 2012 joint CFTC/SEC swap definition carries an insurance safe harbor: the beneficiary must have an insurable interest and bear the risk of loss, and payment is limited to the value of that interest. Products meeting it are insurance and state-regulable; others are classified case by case. "If it's a specific insured's lost sales, then that sounds like insurance", while an area-wide trigger "sounds like a swap" (Schwarcz) — [Insurance Business, 2026-11-09](https://www.insurancebusinessmag.com/us/news/catastrophe/is-a-kalshistyle-weather-contract-insurance-look-to-insurable-interest-596536.aspx)
- Earlier conflict: the NAIC moved to treat weather derivatives as insurance, while the New York department took the position that they were capital-markets products (GlobalCapital, undated, likely early 2000s) — [GlobalCapital](https://www.globalcapital.com/article/28mssnrew086objmjwc2b/derivatives/new-york-state-may-side-against-naic-on-weather-contracts)
- Farmers "wouldn't buy unless the product was on insurance paper", so WeatherBill became a licensed insurer (2010) — [Full Stack Researcher](https://fullstackresearcher.substack.com/p/deconstructing-a-successful-startup-pivot?r=4swq6)

**Eligible contract participant (CEA §1a(18), 7 U.S.C. 1a)**
- An entity qualifies with total assets over $10,000,000, or net worth over $1,000,000 if the transaction is in connection with its business or manages risk from an owned or expected asset or liability. An individual qualifies with over $10,000,000 invested on a discretionary basis, or over $5,000,000 if hedging — [7 U.S.C. 1a, Cornell LII](https://www.law.cornell.edu/uscode/text/7/1a)
- "Excluded commodity" §1a(19)(iv) includes "an occurrence, extent of an occurrence, or contingency" beyond the parties' control and "associated with a financial, commercial, or economic consequence". This is the statutory hook for weather event contracts — [7 U.S.C. 1a](https://www.law.cornell.edu/uscode/text/7/1a)
- Trade option exemption (17 CFR 32.3) references the offeror being an ECP and the option being used solely for business purposes. The full conditions were not extracted — [17 CFR 32.3 (FindLaw)](https://codes.findlaw.com/cfr/title-17-commodity-and-securities-exchanges/cfr-sect-17-32-3/)

**Brokerage route to a DCM**
- Robinhood offers Kalshi (and ForecastEx) contracts as an FCM but cannot list its own markets; its hub launched March 2025. Webull is an SEC broker-dealer and CFTC-registered FCM, and its Kalshi partnership was announced Feb 2025 — [Finance Magnates](https://www.financemagnates.com/forex/webull-dares-to-enter-prediction-markets-where-robinhood-failed/); [Bloomberg 2025-02-12](https://www.bloomberg.com/news/articles/2025-02-12/webull-partners-with-kalshi-to-offer-event-contract-wagers)
- Moomoo Financial was approved as an NFA member, FCM and swap firm on May 1 (2026) to route customers to DCM-listed event contracts without listing them — [DeFi Rate](https://defirate.com/news/moomoo-joins-retail-brokerage-push-into-prediction-markets/)
- An introducing broker must route all customer orders and funds through a registered FCM and register with the NFA. One source cites 3-6 months for complete applications. KPMG describes IB registration as the quicker entry path but notes it needs a DCM/DCO partner — [KPMG 2025](https://kpmg.com/kpmg-us/content/dam/kpmg/pdf/2025/current-state-prediction-markets.pdf); [KPMG 2026 paths to entry](https://kpmg.com/kpmg-us/content/dam/kpmg/pdf/2026/prediction-markets-paths-to-entry.pdf)
- Kalshi affiliate Kinetic Markets LLC received FCM registration (and swap firm listing) from the NFA on 2026-03-24, enabling margin trading — [Bitcoin.com News](https://news.bitcoin.com/kalshi-approved-for-margin-trading-after-affiliate-kinetic-markets-gets-fcm-registration)

**State challenges to Kalshi (2025-2026, sports contracts)**
- Third Circuit (2026-04-06, 2-1): affirmed a preliminary injunction against New Jersey. Sports event contracts are swaps and the CEA preempts state gambling law. Judge Roth dissented — [Skadden](https://www.skadden.com/insights/publications/2026/04/third-circuit-affirms-kalshis-preliminary-injunction); [Holland & Knight](https://www.hklaw.com/en/insights/publications/2026/04/federal-appeals-court-cftc-jurisdiction-over-sports-event-contracts)
- Ninth Circuit ruled against Kalshi in the Nevada case (Aug 28, 2026). The Sixth Circuit ruled against Kalshi on Ohio and Tennessee (Sept 2026), leaving Kalshi "1-for-3" in circuit decisions and widening the split — [The Block, 2026-09-26](https://www.theblock.co/news/regulation/2026-09-26-kalshi-loses-appeal-over-ohio-and-tennessee-sports-betting-laws-widening-circuit-split-416937)
- More than a dozen states have taken action against Kalshi. The CFTC itself sued Illinois, Arizona and Connecticut over attempts to bar sports contracts — [search summary of PYMNTS / Front Office Sports](https://pymnts.com/legal/2026/appeals-court-rules-cftc-has-exclusive-jurisdiction-over-event-contracts)
- None of these cases targets weather contracts. Schwarcz notes the litigating state actors are gaming regulators, not insurance regulators — [Insurance Business 2026-11-09](https://www.insurancebusinessmag.com/us/news/catastrophe/is-a-kalshistyle-weather-contract-insurance-look-to-insurable-interest-596536.aspx)

### Inferences
- The cheapest legal entry for a student-scale startup is software plus routing, not market making: build the hedge designer (AgriHedge already has it) and send orders to Kalshi through a broker or API partnership, registering as an IB or partnering with an existing FCM. Running a designated market-maker desk on Kalshi needs trading capital and Kalshi approval, but no separate CFTC registration was identified for proprietary trading. That is inference; confirm with counsel.
- Selling bespoke OTC weather swaps to restaurants is mostly blocked by ECP rules. Many farms may qualify through the $1M net worth plus hedging prong, but small restaurants and venues often will not. The trade option exemption likely does not fit cash-settled weather (inference: trade options are designed around physical commodities; unverified because 32.3's full text was not read).
- If the startup sells loss-linked protection (paying on the restaurant's own lost sales), it is insurance and needs a producer license plus a fronting carrier or MGA arrangement, as WeatherBill, Arbol and Sensible did. That shifts the business model to underwriting and distribution, with reinsurance holding the unmatched risk.
- A circuit split on CEA preemption heading toward possible Supreme Court review means event-contract-based weather hedges sit on a legal foundation still being litigated. Weather contracts are not the target, and an adverse ruling for sports would not automatically reach them, but state attorneys general could attempt broader theories. This is speculative.

### Gaps
- No NAIC or state insurance department position on parametric weather products sold to businesses was found for 2024-2026. The GlobalCapital items are undated and old.
- The full text of 17 CFR 32.3 (trade option) conditions was not read.
- No source was found for Kalshi's terms for third-party brokers or API "broker partners" (onboarding requirements, revenue share).
- Whether New Jersey sought en banc review or certiorari after the Third Circuit ruling was not confirmed.
- No source on whether a non-FCM software company can lawfully "assist" customers in placing Kalshi orders without IB registration (CFTC staff letters, if any).
- No USDA data was gathered on the share of farms with over $1M net worth (for the ECP prong).
