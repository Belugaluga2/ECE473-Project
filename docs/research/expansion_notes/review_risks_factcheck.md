# Devil's-advocate review: risks to the expansion ideas, and a fact-check of the six notes

Reviewed 2026-11-19. Part A (risk scan) was researched on the web before reading the notes. Part B checks 14 load-bearing claims. Where possible it uses primary sources: the Kalshi public API (`api.elections.kalshi.com/trade-api/v2/series` and `/markets`, pulled 2026-11-19), the statute text and original articles. Kalshi's fee-schedule and Member Agreement PDFs sit behind a bot check (HTTP 429) and could not be read, so claims that rest on them are marked accordingly.

## Top 5 findings

1. **The ECP claim is wrong for unincorporated farms.** The $1M-net-worth hedging test applies to entities only. An individual, including a sole-proprietor farmer, needs more than $10M invested on a discretionary basis, or more than $5M when hedging ([7 U.S.C. 1a(18)(A)(xi)](https://www.law.cornell.edu/uscode/text/7/1a)). The note's statement that "many farms may qualify through the $1M net worth plus hedging prong" holds only for farms organized as entities. For bilateral OTC weather swaps, retail-sized buyers must therefore go through a DCM such as Kalshi, which supports the market-maker note's option (a).
2. **Kalshi's weather menu is much larger than the notes say, but it trades very little.** The API lists 536 Climate and Weather series. They include a daily "Where will it rain" series covering **36 US cities**, about 25 per-city daily rain series, and **resort-reported snowfall** series (Alta, Big Sky, Park City, Beaver Creek, Keystone, Stowe, Northstar, Mammoth). There is also a Saskatchewan Apr-Jul precipitation contract settled on ECCC data. The ski note says "all settle at city or airport stations"; that is now false. Liquidity is the real limit. The Saskatchewan contract had zero volume, with a 0¢ bid and 99¢ ask. Alta's December snowfall strip had about $300 of total volume ([Kalshi API](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXALTASNOW&status=open)).
3. **The settlement source has moved, and it can harm one side of a pair.** The Weather Company (TWC) is now a named settlement source on 254 of the 536 climate series. The daily KXRAIN rules say the official value is "as reported by the Weather Company" and "missing daily precipitation values are counted as 0 inches" ([Kalshi API, KXRAIN rules](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXRAIN&status=open)). A data outage therefore pays the dry side and hurts the wet side, which matters for a book that pairs farmers with restaurants. AgriHedge's backtests use NWS/GHCN data, not TWC's quality-controlled values. That data risk is growing: NWS lost more than 600 staff in 2025 and has rehired only about 200 ([E&E News, Jun 2026](https://www.eenews.net/articles/national-weather-service-in-transition-as-hurricane-season-begins/)).
4. **Manipulation and self-settlement are real risks.** In April 2026, Polymarket's Paris CDG temperature sensor showed a +3°C spike that Météo-France referred to police ([Decrypt](https://decrypt.co/365276/french-weather-agency-alerts-police-to-sensor-interference-after-35k-polymarket-payouts); [Claims Journal, Aug 31 2026](https://www.claimsjournal.com/news/national/2026/08/31/339851.htm)). Kalshi now lists a daily Paris CDG rain series (KXRAINDPARIS). Separately, Park City and Stowe snowfall settle on reports from "Vail Resorts", so a Vail-owned resort hedging on those contracts would settle on its own report. Resort-reported series cut station-to-site basis risk but create moral hazard, and a market maker would be the counterparty.
5. **The legal and demand case is weaker than the notes imply.**
   - **Legal status is unsettled.** There is a 3rd-vs-6th/9th Circuit split over whether event contracts preempt state gaming law, and New Jersey's cert petition (filed Sept 2, 2026) is pending. The CFTC also proposed event-contract rules on June 10, 2026 and signalled more rulemaking.
   - **"Preliminary insurance" is the wrong label.** A loss-linked payout looks like insurance under state law ([Insurance Business, Nov 9 2026](https://www.insurancebusinessmag.com/us/news/catastrophe/is-a-kalshistyle-weather-contract-insurance-look-to-insurable-interest-596536.aspx)).
   - **Tax treatment is uncertain.** The IRS has issued no guidance on event contracts, and wager treatment is possible ([Withum](https://www.withum.com/resources/prediction-markets-contracts-and-federal-income-tax-wagering-investing-or-something-else/)).
   - **Small businesses rarely hedge this way.** About 1 in 10 weather-sensitive mid-size and large firms had ever used weather derivatives in 2008 ([CME/Storm Exchange](https://www.cmegroup.com/media-room/press-releases/2008/4/29/survey_finance_executivessayglobalclimatechangewillrequirechange.html)). Schwarcz says very few platform users hedge.

## A1. Regulatory and legal threats

### Takeaway
Weather contracts on a DCM are federally regulated swaps and event contracts, and the CFTC's 2026 rulemaking targets sports, gaming and war, not weather. The danger for AgriHedge is in what it adds on top:
- calling the product insurance;
- giving individualized trade recommendations, which may require CTA registration;
- routing orders, which may require IB registration;
- pooling ranchers' orders, which may make AgriHedge a commodity pool operator;
- selling abroad.

### Cited Findings
- **CFTC proposed rule (June 10, 2026).** The CFTC proposed amending Reg 40.11 and adding Part 40 Appendix F, which defines "gaming" and sets out when event contracts are contrary to the public interest. Comments were due July 27, 2026. Sports contracts on league data are largely permitted; injury, terrorism, assassination and war contracts are likely barred. If the 90-day review ends without an order, listing may continue. The proposal follows a March 2026 ANPRM, and the CFTC said more rulemaking may follow — [WilmerHale](https://www.wilmerhale.com/en/insights/client-alerts/20260618-10-takeaways-from-the-cftc-event-contracts-proposed-rulemaking); [Katten](https://katten.com/insights/advisories/game-plan-or-game-changer-the-cftc-proposes-new-rules-for-event-contracts-and-prediction-markets)
- **Pace of listings.** Event-contract listings rose from under 150 a year (2021-24) to about 1,600 in 2025. DCM applications more than doubled — [KPMG](https://kpmg.com/us/en/articles/2026/prediction-markets-cftc-advisory-and-anpr-reg-alert.html)
- **Circuit split (sports contracts):**
  - 3rd Cir. (Apr 2026, 2-1): for Kalshi against New Jersey.
  - 9th Cir. (Aug 28, 2026, 3-0): against Kalshi. The sports contracts are "sports gambling, regardless of whether Kalshi calls them swaps." This was a preliminary-injunction posture; election contracts were remanded.
  - 6th Cir. (Sept 2026, unanimous): against Kalshi; Ohio and Tennessee may enforce.
  - 4th Cir. (Maryland): argued May 2026.
  - Sources: [gambling.com](https://www.gambling.com/us/news/ninth-circuit-rules-against-kalshi-backs-nevada-gambling-law); [Holland & Knight](https://hklaw.com/en/insights/publications/2026/08/ninth-circuit-upholds-state-and-tribal-authority-over-sports-related); [Bloomberg Gov](https://news.bgov.com/crypto/kalshi-subject-to-ohio-tennessee-enforcement-after-new-ruling); [The Block](https://theblock.co/news/regulation/2026-09-02-new-jersey-asks-supreme-court-to-decide-who-regulates-sports-betting-on-prediction-markets-413398)
- **Supreme Court petition.** New Jersey petitioned on Sept 2, 2026; no grant or denial was found as of this review — [Front Office Sports](https://frontofficesports.com/prediction-markets-arrive-on-supreme-courts-doorstep/); [covers.com](https://www.covers.com/industry/new-jersey-scotus-review-sports-prediction-markets-filed-september-2026)
- **Insurance or swap?** Under the 2012 CFTC/SEC insurance safe harbor, a contract is insurance if the buyer has an insurable interest, bears the loss, and is paid no more than that interest. Schwarcz: "If it's a specific insured's lost sales, then that sounds like insurance"; "Federal law is pretty clear that swaps are not regulated as insurance"; very few platform users hedge; and "Small businesses are going to have a much harder time" because of basis risk — [Insurance Business, Nov 9 2026](https://www.insurancebusinessmag.com/us/news/catastrophe/is-a-kalshistyle-weather-contract-insurance-look-to-insurable-interest-596536.aspx)
- **State regulators have disagreed before.** The NAIC once argued weather derivatives should be regulated as insurance; New York pushed back. The articles are undated and probably from the early 2000s — [GlobalCapital](https://www.globalcapital.com/article/28mssnrew086objmjwc2b/derivatives/new-york-state-may-side-against-naic-on-weather-contracts). California's insurance department applies the insurable-interest, risk-transfer and proof-of-loss tests to parametric products — [Artemis](https://www.artemis.bm/news/new-california-legal-opinion-sets-guardrails-for-parametric-insurance-deployment-ceres/)
- **Tax.**
  - The IRS has issued no prediction-market guidance. Whether event contracts are Section 1256 contracts is contested because they are prepaid without variation margin.
  - If they are treated as wagers, gains are ordinary income and losses fall under §165(d), deductible only up to winnings — [Withum](https://www.withum.com/resources/prediction-markets-contracts-and-federal-income-tax-wagering-investing-or-something-else/).
  - §1256(e) excludes hedging transactions from mark-to-market treatment — [26 U.S.C. 1256](https://www.law.cornell.edu/uscode/26/1256.html).
  - Farm hedges of commodity price risk are ordinary income or loss on the farm schedule (practitioner blog) — [CLA](https://blogs.claconnect.com/agribusiness/hedging-versus-speculation/email/)
- **Advisory and intermediary registration.**
  - CFTC registration categories include intermediaries that introduce customers to platforms — [Mondaq overview](https://webiis08.mondaq.com/unitedstates/commoditiesderivativesstock-exchanges/1775432/want-to-get-into-cftc-regulated-event-contract-markets-heres-how-it-works).
  - In the market-maker note, Robinhood, Webull and Moomoo access Kalshi as introducing broker or FCM, which requires NFA registration.
- **CFTC scrutiny of incentive programs.** DMO Staff Letter 26-23 (Aug 12, 2026) warned that volume-based incentives risk wash trading. Kalshi filed to end its Volume Incentive Program no earlier than Oct 13, 2026 — [Willkie](https://www.willkie.com/publications/2026/08/cftc-advisory-on-incentive-programs-for-prediction-markets); [The Block](https://theblock.co/news/business/2026-09-30-kalshi-ends-trader-incentive-program-417247)
- **International access.**
  - Kalshi's Member Agreement restricts 55 jurisdictions. India was added in June 2026 after it declared prediction markets illegal under its new gaming law.
  - Brazil, Spain and the Czech Republic ordered ISP blocks without being on the list. Kalshi has not published its criteria — [Cointelegraph](https://cointelegraph.com/news/kalshi-adds-india-restricted-jurisdictions?rand=6792); [Datawallet](https://www.datawallet.com/crypto/kalshi-restricted-countries)

### Inferences
- **Labelling.** Marketing the product as "preliminary insurance" for uninsured farmers is the single most avoidable legal risk. Pairing an insurance label with a loss-linked sizing tool (the advisor sizes to the farm's loss) moves the product toward insurance and away from the safe-harbor swap reading. Language like "a rain-index hedge, not insurance" is safer.
- **Registration triggers.** The AgriHedge advisor recommends specific contracts and sizes for a specific farm. That is individualized commodity advice. If it is charged for, CTA registration (or an exemption) may be required. I did not verify the Reg 4.14 exemptions, which may cover non-tailored advice; counsel is needed. Under the DEMO.md roadmap's "pooled orders across ranches", collecting several ranchers' money to trade together resembles a commodity pool, which is CPO territory. Netting customers against each other without a DCM in the middle looks like operating an unregistered exchange or acting as a swap dealer. Each of these items is an inference.
- **Litigation exposure.** The sports-contract litigation does not touch weather directly. A Supreme Court ruling for the states would still mean CEA preemption does not shield DCM contracts that fall within a state's gaming definition. Weather's commercial-hedging character makes it the least exposed category, but not immune.
- **Tax uncertainty is a sales problem.** Hedge accounting under §1221 covers price, interest-rate and currency risk. Whether a rain-index hedge of volume or yield risk qualifies is unclear (unverified). If it does not, a farmer could face capital or wager treatment, with losses not deductible against farm income.

### Gaps
- Reg 4.14 and CTA exemption details for software advice: no 2026 guidance found.
- Whether any state insurance department has acted on Kalshi weather contracts specifically: none found.
- Kalshi's official restricted-jurisdiction PDF could not be read (HTTP 429).

## A2. Market, settlement and counterparty risks

### Takeaway
Thin books are the documented problem. The new problems are settlement-source drift (from NWS to The Weather Company), asymmetric missing-data rules, sensor tampering, and series churn. Counterparty risk looks low because Kalshi contracts are fully prepaid.

### Cited Findings
- **Settlement sources.** In Kalshi's 536 Climate and Weather series, the named sources are The Weather Company (254 series), NWS (142) and NOAA (76). Every climate series carries `fee_type` "quadratic", multiplier 1 — [Kalshi API /series](https://api.elections.kalshi.com/trade-api/v2/series?category=Climate%20and%20Weather)
- **Daily rain rules.** KXRAIN (daily, 36 cities) resolves Yes if precipitation is strictly above 0 in. The official value is "as reported by the Weather Company" (weather.com/kalshi), and "Trace amounts (T) and missing daily precipitation values are counted as 0 inches" — [Kalshi API markets?series_ticker=KXRAIN](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXRAIN&status=open)
- **TWC partnership.** Kalshi and TWC partnered in August 2026. TWC screens observations against nearby stations and model analysis, and uses more than 400,000 personal weather stations among its inputs — [Claims Journal, Aug 31 2026](https://www.claimsjournal.com/news/national/2026/08/31/339851.htm)
- **Settlement review.** Kalshi's rulebook allows a discretionary Market Outcome Review before settlement, and expiration can be delayed if a source report has a material error — [CFTC filing](https://www.cftc.gov/filings/orgrules/rules09022622971.pdf). A third-party guide claims CLI-based markets settle on the first CLI and do not re-settle (unverified) — [precipitation-ai](https://precipitation-ai.pages.dev/learn/nws-settlement-data)
- **NWS staffing.**
  - 2025: suspended or reduced balloon launches at 11 sites (Omaha, Rapid City, Albany, Gray ME and others) — [Inside Climate News](https://insideclimatenews.org/news/25032025/noaa-cuts-weather-balloon-launches-due-to-staff-shortages-after-doge-layoffs/).
  - 2026: more than 600 staff lost, about 200 rehired, with forecast offices prioritized — [E&E News](https://www.eenews.net/articles/national-weather-service-in-transition-as-hurricane-season-begins/).
  - The surface observations (ASOS/CLI) that settle rain contracts were not reported as affected.
- **Sensor tampering.** At Paris CDG, a Météo-France sensor spiked more than 3°C on Apr 6 and Apr 15, 2026, while neighbouring stations were normal. Polymarket payouts were reportedly about $21-35K. Météo-France complained to police, and Polymarket moved its source to Le Bourget — [Decrypt](https://decrypt.co/365276/french-weather-agency-alerts-police-to-sensor-interference-after-35k-polymarket-payouts). Kalshi lists KXRAINDPARIS at LFPG (CDG) — [Kalshi API](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXRAINDPARIS&status=open)
- **Self-reported settlement.** Park City and Stowe snowfall list "Vail Resorts" and WSJ as sources. Alta settles on Alta Ski Area and OnTheSnow, and Big Sky on OnTheSnow — [Kalshi API /series](https://api.elections.kalshi.com/trade-api/v2/series?category=Climate%20and%20Weather)
- **Liquidity snapshot (2026-11-19):**

  | Series | Volume | Notes |
  |---|---|---|
  | KXRAINNYCM (Nov) | about $3.1K | across 5 strikes |
  | KXDENSNOWM (Dec) | about $10K | |
  | KXALTASNOW (Dec) | about $300 | |
  | KXSKPRECPERIOD (Apr-Jul 2027) | $0 | bid 0¢, ask 99¢ |
  | KXRAIN | about $4K | one day's market, 72 open markets |

  Source: [Kalshi API /markets](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXRAINNYCM&status=open)
- **Series churn.** Legacy duplicates (RAINNYC, KXRAINNYC with 0 open markets; KXDENSNOWM and KXDENSNOWMB) sit beside newer KXRAIND* daily series — [Kalshi API](https://api.elections.kalshi.com/trade-api/v2/series?category=Climate%20and%20Weather). CME delisted its rain and snow products for lack of open interest (see B, row 6).
- **Counterparty risk.** Event contracts are prepaid, without fluctuating collateral — [Withum](https://www.withum.com/resources/prediction-markets-contracts-and-federal-income-tax-wagering-investing-or-something-else/)

### Inferences
- **Backtest validity.** AgriHedge's hedge-effectiveness backtests settle on GHCN/NWS values. Live contracts on TWC-sourced series settle on TWC's quality-controlled values. The basis between the two has not been measured, so the gap should be checked on a year of settled markets before any claim of "replication".
- **Missing data favours one side.** Under the missing-equals-zero rule, a station outage shifts value from wet-side to dry-side holders. A market maker pairing ranchers (dry side) with venues (wet side) carries that one-sided risk. The netting note's correlation analysis does not include it.
- **Manipulation incentive.** In a thin market the ratio of payout to tampering cost is high. The Paris case shows it is practical. Snow and rain gauges are easier to bias than temperature sensors (inference).
- **Counterparty.** Risk sits with Kalshi as DCO and its FCM partners; it does not arise between paired customers. If AgriHedge nets customers off-exchange, the counterparty becomes AgriHedge itself.

### Gaps
- No documented Kalshi weather settlement dispute was found. One anonymous 2025 Reddit claim of an NWS glitch is unverified.
- TWC versus NWS CLI agreement rates were not found.

## A3. Demand evidence and failed precedents

### Takeaway
Evidence that small businesses and smallholders hedge weather is scarce and mostly negative. The precedents that survived did so by becoming insurance (WeatherBill to Climate Corp) or by embedding the product in a purchase (Sensible). Retail parametric MGAs are closing.

### Cited Findings
- **Corporate adoption.**
  - 2008 CME/Storm Exchange survey: only about 1 in 10 weather-sensitive firms (mostly mid-market and Fortune 1000) had used weather options or futures — [CME 2008](https://www.cmegroup.com/media-room/press-releases/2008/4/29/survey_finance_executivessayglobalclimatechangewillrequirechange.html).
  - French corporates: 95% had no climate hedging programme, and 88% had no plans for one (undated) — [Treasury Management International](https://treasury-management.com/article/1/100/875/graphics/TMI165-P1-Leader.jpg)
- **Kenya index insurance.** In Embu, fewer than 10% of maize farmers bought Kilimo Salama. Complexity worsened uptake, and basis risk was the main reason farmers with losses went uncompensated — [Rural21](https://www.rural21.com/english/news/detail/article/weather-index-insurance-for-smallholder-farmers-insights-from-kenya.html); [Tegemeo brief 15](https://tegemeo.egerton.ac.ke/images/_tegemeo_institute/downloads/publications/policy_briefs/policy_brief15.pdf)
- **Retail parametric failures.**
  - OTT Risk, a Lloyd's Lab parametric MGA, ceased operations — [The Insurer](https://theinsurer.com/?p=39778). The Insurer also ran "MGA closures highlight challenges of retail parametric" (paywalled; reasons not read) — [The Insurer](https://theinsurer.com/?p=40402).
  - AXA's Fizzy, a flight-delay parametric product, was quietly discontinued. CAS attributes this to a "mismatch between the simplicity promised and the complexity experienced" — [CAS](https://ar.casact.org/indexing-the-future-the-rise-of-parametric-insurance-and-its-expanding-ecosystem/)

### Inferences
- **Sales channel.** The hospitality and other-sector notes size exposure, not willingness to pay. The demand evidence suggests a single-site restaurant will not buy a monthly or daily station-rain contract through a prediction-market app. The plausible channel is embedded or B2B2C, as with Sensible and booking partners, or a co-op or association buying for members.

### Gaps
- No recent (2020s) survey of small-business derivative or weather-hedge use was found.

## A4. Ethical concerns (selling to unsophisticated or low-income farmers)

### Takeaway
The main harm in the index-insurance literature is a farmer who pays, suffers a loss, and gets nothing because of basis risk, while not understanding why. Selling through a gambling-coded venue that is banned in key target countries raises the stakes.

### Cited Findings
- **Basis risk and comprehension.** Households suffered losses without payouts, and the reverse; low comprehension undermined confidence; transparency raised willingness to pay more than basis-risk reduction did — [Tegemeo](https://tegemeo.egerton.ac.ke/images/_tegemeo_institute/downloads/publications/policy_briefs/policy_brief15.pdf); [Sibiko et al. via AgEcon](https://ageconsearch.umn.edu/record/256213)
- **Compensating missed farmers.** In the WFP/Oxfam R4 programme (Senegal), a separate basis-risk fund paid farmers the index missed (cited in uninsured_farmers.md).
- **Platform terms.** Schwarcz notes the platform, not the buyer, sets the terms — [Insurance Business](https://www.insurancebusinessmag.com/us/news/catastrophe/is-a-kalshistyle-weather-contract-insurance-look-to-insurable-interest-596536.aspx)

### Inferences
- **Selling abroad.** Kalshi is legally unavailable in India and in Kenya, Ethiopia and other African countries per secondary sources. Any "abroad" offering would mean steering users around restrictions, which is a non-starter, or building a separate locally licensed insurance product. That is a different business.
- **Sales disclosures.** A responsible US version would show the farmer the holdout miss rate (the share of loss years with no payout) before purchase. It would cap size relative to income and avoid the word insurance.

### Gaps
- No peer-reviewed ethics framework specific to selling event contracts to smallholders was found.

## B. Fact-check of load-bearing claims in the six notes

### Takeaway
Most numbers check out. These need correcting:
- the ECP thresholds for individuals (Top 5, finding 1);
- "all snow contracts settle at city or airport stations";
- the "unverified" daily-rain city list, now known: 36 cities in KXRAIN;
- the settlement source, which is increasingly TWC rather than NWS.

### Cited Findings

| # | Claim (note) | Verdict | Correct value / comment | Source |
|---|---|---|---|---|
| 1 | Kalshi lists daily rain markets: NYC daily plus a multi-city "Where will it rain today?" series; city list unverified (hospitality) | **Confirmed, expanded** | KXRAIN (daily) covers 36 US cities and resolves Yes if precipitation is above 0 in. About 25 per-city "Daily Rain" series (KXRAIND*) also exist, plus weekly NYC (KXRAINNYCW), weekend (KXRAINWKND) and Paris CDG daily. Most are TWC-settled; missing data counts as 0. | [Kalshi API series](https://api.elections.kalshi.com/trade-api/v2/series?category=Climate%20and%20Weather); [KXRAIN markets](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXRAIN&status=open) |
| 2 | Kalshi monthly snowfall: NYC, Boston, Chicago, Detroit, Dallas and others; "all settle at city or airport" stations (ski) | **Corrected** | City list confirmed and longer: also Denver, DC, Minneapolis, Philadelphia, Pittsburgh, Milwaukee, Seattle, SLC, LA, SF, Houston, Austin, Trenton, Aspen and Jackson WY. Resort-reported series exist: Alta (monthly), Big Sky (monthly), and Park City, Beaver Creek, Keystone, Stowe, Northstar and Mammoth (season-to-date). Very thin (Alta Dec about $300). | [Kalshi API series](https://api.elections.kalshi.com/trade-api/v2/series?category=Climate%20and%20Weather); [KXALTASNOW](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXALTASNOW&status=open) |
| 3 | No exchange-traded weather contract reaches farm regions outside US cities (uninsured_farmers) | **Corrected (minor)** | KXSKPRECPERIOD pays on mean Apr-Jul 2027 precipitation at Saskatoon, Regina and Swift Current (ECCC data), a Prairie crop-region index. It had zero volume (bid 0¢, ask 99¢). | [Kalshi API](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXSKPRECPERIOD&status=open) |
| 4 | Kalshi restricts 55 jurisdictions, incl. Kenya, Ethiopia, India and other African countries (uninsured_farmers) | **Partly confirmed** | 55 and India (added June 2026) confirmed by news reports. Kenya and Ethiopia appear only via Datawallet's secondary list; the Member Agreement PDF was blocked (429). | [Cointelegraph](https://cointelegraph.com/news/kalshi-adds-india-restricted-jurisdictions?rand=6792); [Datawallet](https://www.datawallet.com/crypto/kalshi-restricted-countries) |
| 5 | Kalshi weather and climate volume: about 500% YoY growth, pacing toward about $1.1B annualized (Aug 2026) (market_maker) | **Confirmed (company claim)** | "Annualized volume is tracking toward $1.1 billion, according to Kalshi"; up 500% YoY in 2026 to date. This is Kalshi's own forward-looking figure. | [Claims Journal, Aug 31 2026](https://www.claimsjournal.com/news/national/2026/08/31/339851.htm) |
| 6 | CME delisted rain and snow products in 2013-15 with zero open interest (market_maker, ski) | **Not independently re-verified** | The CME SER-6940 page timed out. The notes cite primary CME SER-6935/6940 (Dec 2, 2013, binaries) and CME Submission 14-384 (Oct 20, 2014, strips), which is consistent. | [CME SER-6940](https://www.cmegroup.com/tools-information/lookups/advisories/market-regulation/SER-6940.html) (timed out) |
| 7 | Kalshi fee: taker ceil(0.07·C·P·(1−P)); standard makers pay no fee (market_maker) | **Confirmed (secondary) / qualified** | Secondary sources give the taker formula; non-standard series carry a maker fee of 0.0175·C·P·(1−P). The help center says only "in some cases" markets have maker fees. The API shows every climate series as `fee_type: quadratic`, multiplier 1, so no weather-specific multiplier (resolves the note's gap). | [Kalshi help: fees](https://help.kalshi.com/en/articles/13823805-fees); [predictionhunt](https://www.predictionhunt.com/blog/kalshi-fees-complete-guide-2026); [Kalshi API](https://api.elections.kalshi.com/trade-api/v2/series?category=Climate%20and%20Weather) |
| 8 | WeatherBill pivoted to farmers; Monsanto bought Climate Corp for $930M in 2013; crop-insurance book sold to AmTrust in 2015 (market_maker) | **Confirmed in part** | About $930M cash, announced Oct 2013 (about $1.1B with retention). The 2015 AmTrust sale was not verified in this session. | [Global Venturing](https://globalventuring.com/blog/2013/10/08/monsanto-acquires-climate-corporation-for-930m/) |
| 9 | Sensible Weather guarantees cost about 8-12% of booking (hospitality) | **Confirmed (dated company claim)** | CEO Cavanaugh: "We often wind up with a Weather Guarantee that costs 8-12% of the trip cost" (Apr 20, 2023). | [Entrepreneur](https://www.entrepreneur.com/living/one-company-will-pay-you-to-enjoy-bad-weather-on-vacation/449743) |
| 10 | Roth Tran: a moderately bad day cuts about 25% of a day's sales, a very bad day about 40%; losses are not recovered (hospitality) | **Confirmed** | As stated, from one national sporting-goods and apparel retailer; published in Management Science 69(12), 2023. | [FRBSF Economic Letter 2022-23](https://www.frbsf.org/research-and-insights/publications/economic-letter/2022/08/impact-of-weather-on-retail-sales/) |
| 11 | Vail 2025-26: NA skier visits −14.9%, lift revenue −5.6%, Rockies −25% (ski) | **Confirmed** | Through Apr 19, 2026. Also ski school −12%, dining −11.7%, retail and rental −6.6%. | [TownLift, Apr 2026](https://townlift.com/2026/04/vail-resorts-visitation-drops-nearly-15-as-weak-winter-drives-revenue-declines/) |
| 12 | 3rd Cir. Apr 6 (2-1, pro-Kalshi); 9th Cir. for Nevada; 6th Cir. Sept 25 against Kalshi; cert petition pending (hospitality, market_maker) | **Confirmed** | All in 2026. 9th Cir. Aug 28, 2026, 3-0 (PI posture; election contracts remanded). 6th Cir. late Sept 2026 (Ohio, Tennessee). New Jersey cert petition filed Sept 2, 2026; no decision found. 4th Cir. (Maryland) argued May 2026. | [The Block (3rd)](https://www.theblock.co/news/regulation/2026-04-06-kalshi-wins-appeal-new-jersey-sports-event-contracts-396437); [H&K (9th)](https://hklaw.com/en/insights/publications/2026/08/ninth-circuit-upholds-state-and-tribal-authority-over-sports-related); [BGov (6th)](https://news.bgov.com/crypto/kalshi-subject-to-ohio-tennessee-enforcement-after-new-ruling); [The Block (cert)](https://theblock.co/news/regulation/2026-09-02-new-jersey-asks-supreme-court-to-decide-who-regulates-sports-betting-on-prediction-markets-413398) |
| 13 | ECP = entity with over $10M assets, or over $1M net worth when hedging; "many farms may qualify" (market_maker) | **Corrected** | Correct for entities (§1a(18)(A)(v)). Individuals (§1a(18)(A)(xi)) need over $10M invested on a discretionary basis, or over $5M if hedging. Sole-proprietor farms fall under the individual test. | [7 U.S.C. 1a](https://www.law.cornell.edu/uscode/text/7/1a) |
| 14 | CFTC DMO advisory Aug 12, 2026; Kalshi filed Sept 28 to end its Volume Incentive Program on Oct 13 (market_maker) | **Confirmed** | Staff Letter 26-23 (Aug 12, 2026). Kalshi's filing ends the program "no earlier than Oct 13". Whether it has actually ended was not confirmed. | [Willkie](https://www.willkie.com/publications/2026/08/cftc-advisory-on-incentive-programs-for-prediction-markets); [The Block](https://theblock.co/news/business/2026-09-30-kalshi-ends-trader-incentive-program-417247) |
| 15 | Kalshi and TWC partnership (Aug 2026): TWC becomes the designated settlement-verification source (market_maker) | **Confirmed** | Announced late Aug 2026. TWC is a listed settlement source on 254 of 536 climate series, and KXRAIN rules name TWC as the "official and final value". | [Claims Journal](https://www.claimsjournal.com/news/national/2026/08/31/339851.htm); [Kalshi API](https://api.elections.kalshi.com/trade-api/v2/series?category=Climate%20and%20Weather) |

### Inferences
- **Basis risk for ski resorts.** Rows 2 and 15 together change the ski thesis. Resort basis risk can be largely removed with resort-reported series, but that brings in self-reporting and moral hazard and leaves essentially no liquidity. Doc 22's liquidity limit applies with more force.
- **Netting.** Row 1 (36-city daily rain) means the netting note's daily wet-side pairing is mechanically possible today. The missing-equals-zero rule (A2) must be modelled first.

### Gaps
- The Kalshi fee-schedule and Member Agreement PDFs and the CME SER-6940 page could not be fetched. Rows 4, 6 and 7 rest on secondary or cited-primary evidence.
- Volume figures are a single snapshot (2026-11-19 morning), not period totals.
