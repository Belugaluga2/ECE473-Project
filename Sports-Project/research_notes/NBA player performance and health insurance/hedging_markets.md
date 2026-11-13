# Tradable markets as hedging instruments for an NBA owner's player-performance and player-health exposure (state as of 11 November 2026)

Reading notes for the report writer:
- Every item is dated where the source gave a date. "(search summary)" means the fact came from a search-result summary and the page itself was not opened; treat those as lower confidence than items marked "(page read)".
- Several Front Office Sports pages show the viewing date in their header, so dates on FOS items were taken from the article body or corroborating URLs, not the header.
- Dollar "volume" on prediction markets is notional contract volume and, in late 2026, is dominated by combos (parlays); it is not comparable one-for-one with sportsbook handle or with available order-book depth.

## 1. Kalshi: NBA contracts listed, contract structure, fees, limits, liquidity, regulatory status, API

### Takeaway
Kalshi is the deepest US venue for NBA event contracts and lists the full menu (game winners, spreads, totals, player props, win totals, make-playoffs, conference, champion, awards, combos), but nothing on injuries or games played. Liquidity is concentrated in single games and the championship market; season-long team markets that an owner would care about (make-playoffs, win totals) trade thinly, the listed position accountability level is $25,000 per strike, and the legal footing of sports contracts is split across federal circuits with a CFTC rule proposed but not final.

### Cited Findings

Contract menu
- Kalshi NBA market types listed as of November 2026: game winners, spreads, totals, player props, playoff qualification, conference winner, NBA champion, awards (MVP, DPOY, ROY, COY), plus combos of up to 10 NBA outcomes and live trading (page read; page states "Last Updated: Nov 10, 2026"). — [RotoWire](https://www.rotowire.com/prediction-markets/nba)
- A Stokastic guide dated 7 August 2026 describes a Kalshi make-the-playoffs board and a win-total ladder for every franchise (search summary). — [Stokastic](https://www.stokastic.com/articles/prediction-markets/kalshi-nba-playoffs-odds)
- Kalshi added NBA player props on 14 November 2025: over/unders on points, rebounds, assists and three-pointers, for roughly 50 players only, with individual users limited to $10,000 per trade on NBA props; current and former NBA players, coaches and staff barred; monitoring via IC360 (page read). — [Front Office Sports](https://frontofficesports.com/kalshi-adds-nba-prop-markets-as-betting-crackdowns-surge/)
- Kalshi self-certified player-stat contracts of the form "Will <player> have <count> <statistic> in <time period> of <game>?" in September 2025 (search summary). — [CFTC filing copy](https://www.ingame.com/wp-content/uploads/2025/09/footballplayerstat.pdf)
- Kalshi also lists player-movement markets: LeBron James "next team" drew more than $200 million on Kalshi (more than $250 million across prediction markets) by 23 July 2026; Kawhi Leonard about $760,000; Bronny James $395,000 (page read). — [Washington Post via Anchorage Daily News, 23 Jul 2026](https://www.adn.com/sports/national-sports/2026/07/23/the-hottest-market-on-kalshi-is-one-the-nba-doesnt-think-should-exist/)
- A Kalshi market on whether Giannis Antetokounmpo would be traded generated $23 million in volume (February 2026) (page read). — [RotoWire](https://www.rotowire.com/prediction-markets/nba)

Contract structure (primary source, Kalshi contract terms "BASKETBALLPOINTSRACE", PDF metadata dated 15 Dec 2025, read in full)
- Binary event contract, settlement value $1.00, minimum tick $0.01. — [Kalshi contract terms](https://kalshi-public-docs.s3.amazonaws.com/contract_terms/BASKETBALLPOINTSRACE.pdf)
- "Position Accountability Level for the Contract shall be $25,000 per strike, per Member." This is an accountability level, not stated as a hard cap. — [Kalshi contract terms](https://kalshi-public-docs.s3.amazonaws.com/contract_terms/BASKETBALLPOINTSRACE.pdf)
- The same $25,000 per strike, per Member accountability level appears in Kalshi's WNBA wins contract terms (search summary). — [Kalshi WNBAWINS terms](https://kalshi-public-docs.s3.amazonaws.com/contract_terms/WNBAWINS.pdf)
- Source agencies in order: the league, ESPN, Fox Sports, the official broadcast partner. Post-expiration stat revisions are ignored. — [Kalshi contract terms](https://kalshi-public-docs.s3.amazonaws.com/contract_terms/BASKETBALLPOINTSRACE.pdf)
- Cancellation rules: if a game is cancelled before the start, or delayed more than two weeks, markets "resolve to the last fair price as determined by the Exchange in its sole discretion"; "If a season is truncated mid-season, all markets deemed to be affected (e.g. total points over a season) by the Exchange may resolve to the last fair price." — [Kalshi contract terms](https://kalshi-public-docs.s3.amazonaws.com/contract_terms/BASKETBALLPOINTSRACE.pdf)
- Trading prohibitions written into the contract (Appendix B): current and former players, coaches and staff of the league; paid employees of the league and league participants; "Ultimate beneficial owners of teams and the league"; and household members and immediate family of all of these. (Eligibility is out of scope for this project, but it is a written contract term, so it is recorded here once.) — [Kalshi contract terms](https://kalshi-public-docs.s3.amazonaws.com/contract_terms/BASKETBALLPOINTSRACE.pdf)

Fees
- General taker fee formula per secondary sources: 0.07 x C x (1 - C) per contract (peak 1.75 cents at a 50-cent price); maker fees reported at 25% of the taker fee (search summary). — [pm.wiki](https://pm.wiki/uk/learn/kalshi-fees-explained); [Allium](https://allium.so/blog/kalshi-fees-why-the-cost-peaks-near-50-cents/)
- A fee guide published 15 May 2026 and updated 27 July 2026 gives the formula as round(multiplier x price x (1 - price), 2), states 0.07 for most categories, but its table implies about 6% for Sports (peak about 1.5 cents at 50 cents); it says player props "sometimes use slightly different multipliers" and combos have their own schedule; the guide is internally inconsistent (page read). — [prediction.com](https://prediction.com/blog/kalshi-fees-complete-guide-2026)
- Same guide: ACH deposits and withdrawals free; debit card about 3%; no settlement fee mentioned (page read). — [prediction.com](https://prediction.com/blog/kalshi-fees-complete-guide-2026)
- One secondary source says resting limit orders fill fee-free on most sports markets and there is no settlement fee (search summary); this conflicts with the "maker = 25% of taker" description above. — [Stokastic](https://www.stokastic.com/articles/prediction-markets/kalshi-fees-vs-dfs-rake)
- Measured all-in cost: for events starting 12-18 October 2026, Kalshi's median "hold" on main lines (ask prices including taker fee) was 4.53% across 1,278 markets, versus DraftKings 4.93%, FanDuel 4.96%, Pinnacle 3.79%, Novig 1.13%, ProphetX 2.09% (page read; NBA was preseason that week so no NBA-only table). — [SharpAPI Hold Report, 23 Oct 2026](https://sharpapi.io/research/hold-report)
- On the 20 October 2026 opening-night game (Detroit v Boston), Kalshi's moneyline overround before fees was 1.00%, versus Pinnacle 2.86%, Betfair 2.98%, Polymarket US 4.00%, Novig 4.99% (snapshot taken 12 Oct 2026) (page read). — [OddsPapi](https://oddspapi.io/blog/?p=4992)

Volume and open interest
- Final weekend of October 2026: Kalshi traded $10.06 billion of a record $14 billion-plus in two-day prediction-market notional volume (Aldrin Research data). NBA volume on the Saturday was $212 million (scope appears to be all tracked operators). Kalshi's most-traded NBA game on Sunday was Memphis-Sacramento at $15.2 million. Nine operators reported $9.6 billion in combo plays (page read). — [Covers, 27 Oct 2026](https://www.covers.com/industry/kalshi-generates-10-billion-of-14-billion-in-weekend-trading-oct-27-2026)
- The Kalshi NBA championship market "nearly" reached $125 million in volume (search summary, date not captured); a Stacker piece lists a 2026 Pro Basketball Champion market at $335,653,533 (scope unclear); a Kalshi team page showed the 2027 NBA Champion market at $25,498,490 volume (snapshot date unknown). — [Sports Illustrated](https://www.si.com/betting/prediction-market/nba/one-team-is-controlling-a-kalshi-nba-championship-market-that-has-nearly-hit-125-million); [Stacker](https://stacker.com/stories/sports-betting/nba-finals-presidential-elections-whats-trading-highest-dollar-prediction); [Kalshi](https://kalshi.com/teams/basketball-team/sac-kings)
- Open interest: the Pro Basketball Champion market held $74.9 million in open interest, the largest on the platform, in spring 2026, later reported dropping from $76.5 million to $45.9 million (search summary). — [DeFi Rate](https://defirate.com/news/kalshi-posts-record-3-9b-volume-extends-lead-over-polymarket-parlays-surge/)
- Sports drive more than 80% of Kalshi's monthly volume, reaching a record 92.0% share in September 2026 (search summary). — [DeFi Rate](https://defirate.com/news/volume-report-surge-14-1-billion-nfl-kickoff/)
- Kalshi sports volume rose from $540 million in July 2025 to $9.9 billion in March 2026; basketball and NFL together are 72% of sports volume (search summary; the same item contains inconsistent headline figures). — [KuCoin news](https://www.kucoin.com/news/flash/kalshi-s-sports-prediction-market-volume-surges-80x-in-one-year)
- A third-party tracker put cumulative trading on NBA outcomes across prediction markets at more than $13.86 billion as of October 2026 (search summary). — [Oddpool](https://www.oddpool.com/explore/nba)

Liquidity and spreads in season-long markets (SportsGrid daily wraps, 2025-26 season, exact dates unclear, search summary)
- Make-playoffs: Milwaukee's qualification contract moved from 15c to 14c on 1,354 contracts traded in 24 hours. — [SportsGrid](https://www.sportsgrid.com/nba/article/nba-kalshi-update-jan-17-bucks-playoff-odds-crash-jokic-mvp-drop)
- MVP: Cade Cunningham's MVP contract traded 450,205 contracts in 24 hours at 14c; Nikola Jokic's showed 39,626 contracts in one snapshot. — [SportsGrid](https://www.sportsgrid.com/nba/article/daily-nba-prediction-markets-wrapped-kalshi-market-movers-14)
- Spreads: Boston Eastern Conference one-seed quoted 6c bid / 19c ask (13 cents wide); a thin award market was 4c / 33c with zero volume and zero open interest. — [SportsGrid](https://www.sportsgrid.com/nba/article/daily-nba-prediction-markets-wrapped-kalshi-market-movers-10)

Order-book depth on games (snapshot 12 Oct 2026, eight days before opening night, page read)
- Kalshi median thin-side resting size on NBA moneylines was 1,474 (currency units not specified) over three price levels across the three games it had priced; on Detroit v Boston the thin side was 688 over three levels. Kalshi had not yet listed spreads or totals for those games. The author notes depth should grow nearer to tip-off. — [OddsPapi](https://oddspapi.io/blog/?p=4992)

Regulatory status
- Appellate split: the Third Circuit ruled 2-1 for Kalshi that the Commodity Exchange Act preempts New Jersey gambling law; on 25 September 2026 a Sixth Circuit panel held Kalshi's sports contracts are not "swaps", allowing Ohio and Tennessee to enforce their gambling laws (search summary). — [SBC Americas, 25 Sep 2026](https://sbcamericas.com/2026/09/25/kalshi-sixth-circuit-sides-oh-tn/); [Foley litigation tracker](https://www.foley.com/?p=130779)
- A Connecticut federal judge denied Kalshi a preliminary injunction on 10 August 2026, finding sports contracts are not swaps; a New York federal judge also refused to block enforcement and Kalshi appealed to the Second Circuit (search summary). — [Crowdfund Insider](https://www.crowdfundinsider.com/2026/08/296440-connecticut-judge-rules-kalshi-sports-contracts-never-qualified-as-swaps/); [DeFi Rate](https://defirate.com/?p=15740)
- The DOJ and CFTC sued Illinois, Arizona and Connecticut over state enforcement (search summary). — [Foley litigation tracker](https://www.foley.com/?p=130779)
- CFTC March 2026 advisory: sports contracts are less susceptible to manipulation when outcomes depend on many participants over an extended competition; risk is heightened when a contract turns on one individual or a small group (page read). — [Washington Post via ADN, 23 Jul 2026](https://www.adn.com/sports/national-sports/2026/07/23/the-hottest-market-on-kalshi-is-one-the-nba-doesnt-think-should-exist/)
- CFTC proposed rule released 10 June 2026 (comments due 27 July 2026): replaces the blanket gaming prohibition with contract-by-contract review; disfavors contracts on player injuries (perverse incentives, medical confidentiality, lack of objective settlement criteria) and single-action micro-contracts ("specific shot taken by a specific player"); treats aggregate outcomes including "individual or team statistical performance" more favorably. No final rule was found as of 11 November 2026 (search summary). — [Akin Gump](https://www.akingump.com/en/insights/alerts/cftc-proposes-new-framework-for-regulating-prediction-markets); [Greenberg Traurig](https://www.gtlaw.com/en/insights/2026/6/cftc-proposes-new-rules-for-events-contracts-on-prediction-markets)
- On 26 October 2026 the NBA named Kalshi and Polymarket "preferred prediction market partners" (IP rights, official Sportradar data, an NBA-CFTC memorandum of understanding on information sharing; financial terms undisclosed). Partners must follow the NBA's October 2026 sportsbook prop restrictions (page read). — [Front Office Sports, 26 Oct 2026](https://frontofficesports.com/article/nba-tips-off-prediction-market-era-with-kalshi-polymarket/)
- State availability is restricted in places: one platform running on a CFTC exchange restricts sports trading in IL, MA, MD, MI, NJ, NV and OH (reported for OG.com; Kalshi's own state list was not captured) (page read). — [RotoWire](https://www.rotowire.com/prediction-markets/nba)

API and historical data
- Kalshi's official docs split data into live and historical tiers. Cutoffs come from `GET /historical/cutoff`; the live window targets about 3 months. Older data is served from `GET /historical/markets`, `GET /historical/markets/{ticker}/candlesticks` and `GET /historical/trades` (search summary of official docs). — [Kalshi docs](https://docs.kalshi.com/getting_started/historical_data); [cutoff endpoint](https://docs.kalshi.com/api-reference/historical/get-historical-cutoff-timestamps)
- A third-party blog updated October 2026 says the candlestick and trade endpoints are public without an API key (not confirmed in official docs). — [botforkalshi](https://www.botforkalshi.com/blog/kalshi-historical-data)

### Inferences
- The contracts most useful to an owner (make/miss playoffs, win-total ladders, star-player season awards) exist, but the observed activity in them (about 1,350 contracts in 24 hours on a playoff-qualification strike; double-digit-cent spreads on some futures) is orders of magnitude below single-game markets ($15 million on a routine regular-season game). A hedge built from season-long contracts would have to be accumulated slowly as a maker or through negotiated block liquidity.
- Illustrative arithmetic: at a 0.07 x P x (1 - P) taker fee, a contract bought at 30c costs 1.47c in fees, about 4.9% of premium; at 50c, 1.75c or 3.5% of premium. Fees are small next to the spread cost in thin futures markets.
- "Last fair price" settlement on cancellation or a truncated season means a hedge does not pay out as insurance would in a lockout or shortened-season scenario.
- Because much headline volume is combos, headline notional overstates the depth available in any single-leg season-long market.
- The team's existing Kalshi tooling should transfer: the same API structure (events, markets, candlesticks, trades) applies to sports, with the caveat that settled markets older than about 3 months must be pulled from the `/historical/*` endpoints.

### Gaps
- The official Kalshi fee schedule PDF (kalshi.com/docs/kalshi-fee-schedule.pdf) returned HTTP 429; the sports multiplier (7% vs about 6%), maker fee treatment and combo fees are therefore from secondary sources that disagree.
- No contract-terms document for NBA season win totals, make-playoffs or player-stat props was read, so their accountability levels and did-not-play settlement rules are unverified; the $25,000 figure is confirmed only for the points-race and WNBA wins contracts.
- Whether the $10,000-per-trade and roughly-50-player prop restrictions from November 2025 still apply in the 2026-27 season was not confirmed.
- No current (2026-27) open interest or spread data for win-total or make-playoffs markets was found; this needs a live API pull.
- The date of the Third Circuit ruling was not captured. A PYMNTS headline refers to "a second federal appeals court" ruling sports contracts are not swaps, which may mean a second adverse circuit beyond the Sixth; this was not resolved. The outcome of a First Circuit argument scheduled for 4 November 2026 was not found.
- The DeFi Rate figure of a "$19.03 billion" Kalshi week (5-11 October 2026) conflicts with another figure in the same summary and was not verified.

## 2. Other US event-contract venues and exchanges (Polymarket US, Crypto.com/OG, Robinhood, DraftKings Predictions, FanDuel Predicts, Fanatics Markets, Novig, ProphetX, Sporttrade) and overseas exchanges

### Takeaway
By late 2026 there are close to a dozen CFTC-regulated venues or front-ends listing NBA contracts, but Kalshi holds roughly 70% of volume; the others add modest incremental depth, mostly in the same game-level markets, and none was found listing injury or games-played contracts. Overseas exchanges (Betfair, Matchbook, Smarkets) show thinner NBA books than Kalshi or Pinnacle.

### Cited Findings

Market share (final weekend of October 2026, Aldrin Research via Covers, page read)
- Kalshi $10.06 billion; Polymarket US over $1.5 billion ($811.2 million Saturday, $755.4 million Sunday); DraftKings Predictions $684 million (third place, up from $567 million the prior weekend); total over $14 billion across 10 of 11 tracked operators. — [Covers, 27 Oct 2026](https://www.covers.com/industry/kalshi-generates-10-billion-of-14-billion-in-weekend-trading-oct-27-2026)

Polymarket US
- Lists NBA moneyline, spread, total, player props, award markets, team futures and playoff bracket markets; operates through CFTC-licensed exchange QCEX; RotoWire reports a flat 0.10% taker fee (page read). — [RotoWire](https://www.rotowire.com/prediction-markets/nba)
- Conflicting fee descriptions: Bleacher Nation describes a price-based taker formula with a small maker rebate; Sacra says global Polymarket began charging 0.75% on sports in January 2026 with a blended take of about 0.3% of volume (search summary). — [Bleacher Nation](https://www.bleachernation.com/prediction-markets/sports/nba/finals/); [Sacra](https://sacra.com/research/polymarket-at-375m-year-revenue/)
- Polymarket US notional volume was about $255.9 million in March 2026, sports-only at that point; weekly volume reached $88.8 million in the week of 30 March 2026 (search summary). — [DeFi Rate](https://defirate.com/news/polymarket-us-posts-256m-march-launches-politics-built-to-scale/)
- Polymarket hosts over 214 active NBA markets; an OKC-Boston game-winner contract generated over $1 million (page read). — [RotoWire](https://www.rotowire.com/prediction-markets/nba)
- In a 12 October 2026 snapshot, Polymarket US showed zero resting size on every NBA opening-week rung (flagged inactive at that time) (page read). — [OddsPapi](https://oddspapi.io/blog/?p=4992)
- LeBron James has a Polymarket endorsement deal reported at $15 million per year; MLB's Polymarket deal is reported at up to $300 million over four years (page read). — [Front Office Sports, 26 Oct 2026](https://frontofficesports.com/article/nba-tips-off-prediction-market-era-with-kalshi-polymarket/)

Crypto.com / OG.com
- OG.com (launched February 2026, on Crypto.com's exchange) lists NBA game winners, spreads, totals, player props and multi-leg parlays (legs must be from different games); $0.02 per contract entry fee; available in 49 states plus DC excluding New York and Arizona, with sports restricted in IL, MA, MD, MI, NJ, NV, OH (page read). — [RotoWire](https://www.rotowire.com/prediction-markets/nba)

Robinhood
- Lists NBA game winners, spreads, totals and live player props (page read). — [RotoWire](https://www.rotowire.com/prediction-markets/nba)
- On the Q4 2025 earnings call the CEO said NBA contracts produce more volume than NFL contracts on Robinhood; 12 billion event contracts traded in 2025 (8.5 billion in Q4), 8.8 billion in Q1 2026 (search summary). — [Sports Market Ticker](https://sportsmarketticker.beehiiv.com/p/nba-contracts-now-outpace-nfl-on-robinhood-prediction-markets); [DeFi Rate](https://defirate.com/?p=10193)
- Fees: from 1 June 2026 commission varies with contract price and order size and never exceeds $0.01 per contract; Robinhood also began routing contracts to its affiliate exchange Rothera (search summary). Earlier pricing was $0.01 commission plus $0.01 exchange fee. — [Robinhood newsroom, 4 Jun 2026](https://robinhood.com/newsroom/the-world-cup-is-now-trading-on-robinhood-and-rothera/); [DeFi Rate](https://defirate.com/prediction-markets/robinhood/)

DraftKings Predictions, FanDuel Predicts, Fanatics Markets
- DraftKings Predictions partnered with Crypto.com Derivatives North America to add player-specific NFL and NBA event contracts (search summary); DraftKings' NBA sportsbook partnership was expanded on 26 October 2026 to cover prediction markets (page read). — [Action Network](https://www.actionnetwork.com/news/draftkings-partners-with-crypto-com-to-expand-prediction-markets-offerings); [Front Office Sports, 26 Oct 2026](https://frontofficesports.com/article/nba-tips-off-prediction-market-era-with-kalshi-polymarket/)
- FanDuel Predicts launched in five states without legal sports betting (Alabama, Alaska, South Carolina, North Dakota, South Dakota), on a CME Group exchange, covering baseball, basketball, football and hockey (search summary; launch date not captured). — [Legal Sports Report](https://www.legalsportsreport.com/249756/fanduel-predicts-launches-in-5-states-without-legal-sports-betting/)
- Fanatics Markets (launched 3 December, year per source context 2025) lists NBA game outcomes and season futures (championship, conference winner, regular-season games) (page read / search summary). — [RotoWire](https://www.rotowire.com/prediction-markets/nba)

Sports-native exchanges
- Novig (Ludlow Exchange) received CFTC designation as a contract market on 16 June 2026; ProphetX was approved in June 2026 and launched one week later; Sporttrade's DCM and DCO applications (filed 27 January 2026) were still pending as of mid-2026 (search summary). — [SBC Americas, 17 Jun 2026](https://sbcamericas.com/2026/06/17/novig-prediction-market-cftc-approval/); [Covers, 18 Jun 2026](https://www.covers.com/industry/prophetx-launches-prediction-markets-in-us-one-week-after-cftc-approval-june-18-2026); [DeFi Rate](https://defirate.com/news/sporttrade-files-for-dcm-status-under-cftc-to-put-the-consumer-first/)
- In the week of 19 October 2026 the CFTC told Novig and ProphetX not to list certain self-certified sports contracts (the types leagues gave the "most negative feedback" about, including "scorigami" and micro-contracts) and to explain their compliance (search summary). — [Front Office Sports, 22 Oct 2026](https://frontofficesports.com/novig-prophetx-told-to-pause-scorigami-micro-contract-plans/)
- Novig was expected to finalize an authorized NBA partnership in the week of 26 October 2026 (page read). — [Front Office Sports, 26 Oct 2026](https://frontofficesports.com/article/nba-tips-off-prediction-market-era-with-kalshi-polymarket/)
- Median hold at close, 12-18 October 2026: Novig 1.13%, SX Bet 1.48%, ProphetX 2.09%, Matchbook 2.75% and Betfair 3.60% (both before commission), Smarkets 4.87% (page read). — [SharpAPI Hold Report](https://sharpapi.io/research/hold-report)
- NBA opening-week depth (12 October 2026 snapshot, median thin-side size on the main line): Pinnacle limit 1,350 moneyline / 2,341 spread / 894 total; Novig 587 / 702 / 648; SX Bet 400 / 78 / 290; Betfair Exchange 376 / 91 / 211. In June 2026 NBA Finals Game 5, Novig's stored limit ran from 1,909 to 3,847 on the first six moneyline prices (page read; currency units not specified). — [OddsPapi](https://oddspapi.io/blog/?p=4992)

Overseas exchanges
- Smarkets charges 2% commission on net winnings; Matchbook 2% (UK) / 4% (rest of world); Betfair uses a market base rate with 5% commonly cited; sources disagree on NBA depth (search summary, affiliate sources). — [pm.wiki](https://pm.wiki/id/compare/betfair-exchange-vs-smarkets)

### Inferences
- Spreading a hedge across venues adds little: the non-Kalshi US venues together are under 30% of volume and list the same contract types, so they do not supply a missing "injury" or "games played" instrument.
- Low-hold exchanges (Novig about 1.1%, ProphetX about 2.1%) are the cheapest places to trade game lines, but posted sizes of a few hundred to a few thousand units per price level make them irrelevant at an owner's scale.
- Rapid entry of regulated front-ends (DraftKings, FanDuel on CME, Fanatics, Robinhood/Rothera) suggests depth is still growing; any liquidity estimate from 2026 will age quickly.

### Gaps
- No venue-level NBA open interest was found for any platform other than Kalshi.
- Polymarket US fee schedule was not verified against primary documentation (0.10% flat vs price-based formula).
- Position limits for Polymarket US, Crypto.com/OG, Robinhood, DraftKings Predictions, FanDuel Predicts, Novig and ProphetX were not found.
- Betfair NBA matched volumes were not found from a reliable source; one unsourced blog cited "$200K+" average daily volume for NBA championship markets and is not relied on.
- Sporttrade's current DCM status (November 2026) was not confirmed.

## 3. Traditional sportsbooks: health/performance-related markets, hold by market type, stake limits, limiting of accounts

### Takeaway
Sportsbooks list the richest set of player-linked markets (per-game props, awards, season win totals, make/miss playoffs), but the markets most relevant to hedging carry the highest margins (roughly 6-12% on props, 15-30% on futures per industry estimates) and the lowest limits (low thousands of dollars on props), and books restrict accounts they consider sharp.

### Cited Findings
- Theoretical hold by market type (industry and affiliate estimates, not operator data): standard -110 sides about 4.5-4.8%; player props about 6-12%; futures 15-30% or more on large fields; parlays and same-game parlays 15-30% (search summary). — [DeucesCracked](https://www.deucescracked.com/blog/sportsbook-hold-percentage-explained-vig-by-market-2026); [CardPlayer](https://cardplayer.com/cardplayer-poker-magazines/66405-oaks-card-club-the-place-to-play-in-the-bay-32-6/articles/23628-multiway-markets-and-parlays)
- Measured median hold on main lines at close (moneyline, spread, total combined; props and futures excluded), 12-18 October 2026: Pinnacle 3.79%, Circa 4.58%, DraftKings 4.93%, FanDuel 4.96%, BetMGM 5.03%, Fanatics 5.11%, Caesars 5.67%, BetRivers 6.71% (page read). — [SharpAPI Hold Report](https://sharpapi.io/research/hold-report)
- Stake limits (secondary sources): one article gives DraftKings NBA totals limits of $5,000-$10,000 and player props $1,000-$5,000; a FanDuel guide lists player props at "$2,500 - $50,000" (unclear whether stake or payout) and says spreads and totals always carry higher limits than props (search summary). — [skaynews](https://skaynews.pages.dev/front-page-news/betting-limits-draft-kings-betmgm-caesars-circa-32914); [Bleacher Nation, 17 May 2026](https://www.bleachernation.com/betting/2026/05/17/fanduel-maximum-bet-2026/)
- Pinnacle's default pre-season NBA limits in a 12 October 2026 data pull were 1,350 on moneylines, about 2,300 on spreads and about 890 on totals, expected to rise once trading starts (page read). — [OddsPapi](https://oddspapi.io/blog/?p=4992)
- Circa is described as taking limits 5-10x mainstream books on NFL sides and totals and not limiting winners, but offers props only on roughly the starting five or six players per NBA team (search summary). — [Covers](https://www.covers.com/industry/circa-sports-new-app-launch-iowa-missouri-stevens-interview-betting-october-2025)
- Account limiting: Massachusetts data showed 0.64% of sports-betting accounts limited as of 10 December 2024, with regulators finding a correlation between consistent winning and harsh limits; UK Gambling Commission data showed 48% of limited account holders were in lifetime profit versus 25% of unrestricted accounts (search summary). — [Birches Health](https://bircheshealth.com/resources/limiting-bettors); [SBC Americas, 25 Jul 2025](https://sbcamericas.com/2025/07/25/uk-regulator-sports-betting-limits/)
- Speed of limiting varies: "some accounts are limited within a handful of bets, while others operate for years" (commercial source, opinion) (search summary). — [DeucesCracked](https://www.deucescracked.com/blog/sportsbook-account-limits-2026-why-winners-get-limited)
- Awards markets are tied to availability: players need at least 65 regular-season games to be eligible for MVP and All-NBA honors, so award odds lengthen as a player nears the cutoff (search summary). — [BetMGM](https://sports.betmgm.com/en/blog/nba/what-is-the-nba-games-minimum-bm06/)
- Large negotiated futures bets are possible for known recreational customers: in 2022 Jim "Mattress Mack" McIngvale bet about $10 million across online sportsbooks, about $3 million of it at Caesars, which paid about $30 million (search summary). — [CardPlayer](https://cardplayer.com/poker-news/27409-furniture-store-owner-mattress-mack-scores-75m-sports-betting-payout)

### Inferences
- A hedger who systematically buys "bad outcome" positions tied to private knowledge of player health looks to a sportsbook exactly like an informed bettor; props limits in the $1,000-$5,000 range and account restriction make sportsbooks unusable for anything beyond token amounts on player-level markets.
- Futures (make/miss playoffs, win totals) can be bet in much larger size by negotiation, as the McIngvale bets show, but at 15-30% theoretical hold the cost is several times a prediction-market fee.

### Gaps
- No operator-published table of maximum stakes for NBA props, season win totals, make/miss playoffs or awards was found; limits are account- and event-specific.
- No NBA-specific measured hold for props or futures was found (the SharpAPI report excludes both and had no NBA regular-season data).
- No reliable data on how quickly DraftKings or FanDuel specifically limit accounts.
- Whether any US book currently lists season-long player stat totals (for example season points over/under) was not confirmed.

## 4. Markets that directly reference injuries or games played; void rules; integrity restrictions and the Porter / Rozier fallout

### Takeaway
No listed "games played" or "games missed" contract was found on any US sportsbook or prediction market, and the direction of travel is against them: the NBA has asked the CFTC to prohibit injury markets, the CFTC's June 2026 proposal disfavors them, and since October 2026 the NBA has barred several prop types (notably low-probability unders and same-player under parlays) at sportsbooks and at its prediction-market partners. The closest available proxies are award futures (through the 65-game rule), per-game props (which generally void when a player does not play, so they do not pay on absence) and team futures.

### Cited Findings
- A targeted search found no sportsbook page listing a games-played over/under or "will player X play at least N games" market; the nearest proxy is MVP pricing through the 65-game eligibility rule (search summary). — [BetMGM](https://sports.betmgm.com/en/blog/nba/what-is-the-nba-games-minimum-bm06/)
- NBA letter to the CFTC (April 2026, Dan Spillane): "Markets relating to officiating, injuries, league disciplinary actions, player or team transactions" should be prohibited as "readily susceptible to manipulation and/or improper use of confidential information." The NBA also asked that exchanges consult leagues before listing, share trading data and bar insiders (page read). — [Washington Post via ADN, 23 Jul 2026](https://www.adn.com/sports/national-sports/2026/07/23/the-hottest-market-on-kalshi-is-one-the-nba-doesnt-think-should-exist/)
- CFTC proposed rule (10 June 2026) disfavors contracts on player injuries, citing perverse financial incentives, medical confidentiality and lack of objective settlement criteria (search summary). — [Akin Gump](https://www.akingump.com/en/insights/alerts/cftc-proposes-new-framework-for-regulating-prediction-markets)
- NBA restrictions for 2026-27 (letter to operators reported 16 October 2026): no "first-of" player markets (first points, rebound, assist, steal, block); no bets on whether a player misses a specific shot; no opening-tip bets; no "low likelihood, high payout bets" based on statistical unders, including parlays with multiple under legs on one player. "The league is not banning all under bets." Applies to the WNBA from 2027. DraftKings, FanDuel, Fanatics and Caesars said they support or comply (page read). — [Front Office Sports, 16 Oct 2026](https://frontofficesports.com/article/nba-draws-new-lines-fans-bet/)
- Other reports of the same letter: unders on players expected to play fewer than 12 minutes are prohibited, and alternate-line unders with larger payouts are barred (search summary; details differ by outlet). — [Covers, 16 Oct 2026](https://www.covers.com/industry/nba-bans-certain-bet-types-ahead-of-new-season-oct-16-2026); [Gambling.com](https://www.gambling.com/us/news/nba-bans-same-player-under-parlays-and-other-props-at-sportsbooks)
- Earlier restrictions (after the Porter case): no bets on players on 10-day or two-way contracts, plus restrictions on props for turnovers, fouls and missed free throws (search summary). — [Casino.org](https://www.casino.org/news/sports-betting-nba-restrictions-amid-gambling-scandals/); [Legal Sports Report](https://www.legalsportsreport.com/239853/nba-players-union-back-more-limits-on-prop-bets/)
- The October 2026 sportsbook restrictions initially "relate only to traditional sportsbook partners"; ten days later, the NBA's prediction-market partners (Kalshi, Polymarket, DraftKings) were required to follow them (page read). — [Front Office Sports, 16 Oct 2026](https://frontofficesports.com/article/nba-draws-new-lines-fans-bet/); [Front Office Sports, 26 Oct 2026](https://frontofficesports.com/article/nba-tips-off-prediction-market-era-with-kalshi-polymarket/)
- The NBA says it built an in-house AI-based monitoring platform for unusual betting activity; "Players and league and team employees will not be allowed to trade on NBA event contracts" (page read). — [Front Office Sports, 16 Oct 2026](https://frontofficesports.com/article/nba-draws-new-lines-fans-bet/); [Front Office Sports, 26 Oct 2026](https://frontofficesports.com/article/nba-tips-off-prediction-market-era-with-kalshi-polymarket/)
- Jontay Porter: banned for life by the NBA in 2024; pleaded guilty to conspiracy to commit wire fraud after manipulating his performance in two 2023-24 games so that unders would win; sentencing scheduled for 10 December 2026 (page read / search summary). — [Front Office Sports, 16 Oct 2026](https://frontofficesports.com/article/nba-draws-new-lines-fans-bet/); [Casino.org](https://www.casino.org/news/sports-betting-nba-restrictions-amid-gambling-scandals/)
- Terry Rozier: arrested 23 October 2025, among more than 30 people charged in two federal cases; accused of telling an associate he would leave a March 2023 game early, after which bettors placed roughly $200,000-$259,000 on his unders (figures vary by outlet); he has pleaded not guilty. Chauncey Billups was charged in the separate rigged-poker case, not the betting case; Damon Jones was also indicted (search summary). — [NBC Sports](https://www.nbcsports.com/nba/news/what-to-know-about-terry-rozier-chauncey-billups-indictments-amid-sprawling-fbi-investigations); [Covers, 23 Oct 2025](https://www.covers.com/industry/terry-rozier-chauncey-billups-arrested-fbi-sports-betting-investigations-oct-23-2025)
- Virginia regulators were evaluating restrictions on certain prop wagers, particularly NBA (search summary). — [Casino.org](https://www.casino.org/news/sports-betting-nba-restrictions-amid-gambling-scandals/)
- Sportsbook void rules: props are generally cancelled when the player is inactive or does not play; if the player takes the court but records no stats, overs lose and unders win; Fanatics reportedly refunds over bets when a player is injured in the first quarter of an NBA game ("fair play" policy) (search summary). — [Action Network](https://www.actionnetwork.com/education/prop-betting-rules-what-happens-if-player-doesnt-play); [Action Network on Fanatics](https://www.actionnetwork.com/education/does-fanatics-sportsbook-void-player-props-for-injuries-fair-play-explained)
- Injury-adjacent information demonstrably moves prediction markets: after the Miami Heat accidentally posted a "LeBron James Introductory Press Conference" stream in July 2026, Miami's implied probability on Kalshi rose from about 37% to 47% (page read). — [Washington Post via ADN, 23 Jul 2026](https://www.adn.com/sports/national-sports/2026/07/23/the-hottest-market-on-kalshi-is-one-the-nba-doesnt-think-should-exist/)

### Inferences
- The exact payoff the project wants ("pay when a star misses games") is the payoff regulators and the league are most determined to keep off the market: it is an under-style, single-individual, injury-linked contract. It should be treated as unavailable and unlikely to be listed.
- Per-game unders are a poor proxy for absence because they void, rather than pay, when the player sits; they pay only on in-game underperformance or early exits, which is precisely the Porter/Rozier manipulation pattern.
- Usable proxies are therefore indirect: team make-playoffs / win-total contracts (team-level, CFTC-favored "aggregate outcomes"), and "No" positions on a player's season awards (which lose value as the 65-game threshold slips away). Both carry large basis risk relative to a specific player's games missed.

### Gaps
- Kalshi's and Polymarket's settlement rule for a player prop when the player does not play was not verified from contract terms.
- The full text of the NBA's October 2026 letter was not obtained; outlets differ on the 12-minute and alternate-line details.
- No sportsbook house-rules document was read directly for NBA did-not-play wording.
- Whether any offshore or overseas book lists games-played props was not checked.

## 5. How much could a hedger realistically place, compared with tens of millions of dollars of salary exposure?

### Takeaway
On the evidence found, realistically achievable hedge sizes are in the tens of thousands of dollars per contract strike on player-linked markets and, with patience or negotiation, perhaps low millions on headline team futures; that is one to three orders of magnitude short of an eight-figure salary exposure.

### Cited Findings
- Kalshi position accountability level: $25,000 per strike, per Member on a basketball contract. — [Kalshi contract terms](https://kalshi-public-docs.s3.amazonaws.com/contract_terms/BASKETBALLPOINTSRACE.pdf)
- Kalshi NBA props at launch: $10,000 per trade per user, about 50 players. — [Front Office Sports, 14 Nov 2025](https://frontofficesports.com/kalshi-adds-nba-prop-markets-as-betting-crackdowns-surge/)
- Largest pool of NBA open interest found: $74.9 million in the championship market (spring 2026), falling to $45.9 million. — [DeFi Rate](https://defirate.com/news/kalshi-posts-record-3-9b-volume-extends-lead-over-polymarket-parlays-surge/)
- Routine game volume: $15.2 million on Kalshi's most-traded NBA game on one late-October 2026 Sunday; $212 million NBA volume on the Saturday. — [Covers, 27 Oct 2026](https://www.covers.com/industry/kalshi-generates-10-billion-of-14-billion-in-weekend-trading-oct-27-2026)
- Season-long team market activity: 1,354 contracts in 24 hours on a make-playoffs strike in one snapshot. — [SportsGrid](https://www.sportsgrid.com/nba/article/nba-kalshi-update-jan-17-bucks-playoff-odds-crash-jokic-mvp-drop)
- Resting depth eight days before a game: about 700-1,500 units on the thin side over three levels at Kalshi; Pinnacle limits 900-2,300; Betfair under 400. — [OddsPapi](https://oddspapi.io/blog/?p=4992)
- Sportsbook prop limits about $1,000-$5,000 (DraftKings, secondary source). — [skaynews](https://skaynews.pages.dev/front-page-news/betting-limits-draft-kings-betmgm-caesars-circa-32914)
- Upper bound precedent for a negotiated retail futures position: about $10 million staked across books, $3 million at one book (2022). — [CardPlayer](https://cardplayer.com/poker-news/27409-furniture-store-owner-mattress-mack-scores-75m-sports-betting-payout)
- Prediction-market venues market themselves as never restricting winning traders (general claim). — [RotoWire](https://www.rotowire.com/prediction-markets/nba)

### Inferences
- Illustrative arithmetic: a $10 million payout from a binary contract trading at 30c requires 10 million contracts and $3 million of premium. Against 24-hour volume of roughly 1,350 contracts in a make-playoffs strike, that position is thousands of days of observed turnover; against a $25,000 accountability level it is about 120 times the level at which the exchange may ask questions.
- A $25,000 position is 0.05% of a $50 million exposure. Even the largest NBA open-interest pool found ($45-75 million, championship market) is the same order of magnitude as one star's annual salary, and that pool is spread across 30 teams.
- Single-game markets are deep enough for six- or low-seven-figure trades on big games, but a per-game hedge is repeated up to 82 times, cannot reference a player's absence directly, and prices in public injury news before a hedger without an information edge could act.
- The only route to size is the futures-style team contracts, accumulated as a maker over weeks, or bilateral or over-the-counter deals with market makers; no evidence of block or RFQ facilities for NBA futures was found.
- Practical conclusion for the project: these markets can demonstrate payoff construction and pricing (as the farm project did), and can supply market-implied probabilities for pricing an insurance-like product, but cannot carry the risk at an owner's scale in 2026.

### Gaps
- No source states a hard position limit (as opposed to an accountability level) for Kalshi NBA contracts, or how Kalshi treats members who exceed the level.
- No data on market-maker willingness to quote large blocks in NBA season-long contracts, and no evidence either way on OTC or block-trade facilities.
- Depth figures are from a single pre-season snapshot; in-season game-day depth was not measured.
- No sourced salary figures were collected here (the "tens of millions" scale comes from the assignment).

## 6. Efficiency and calibration of NBA betting and prediction markets

### Takeaway
Academic evidence says NBA closing lines are close to efficient and absorb player-absence news by the close, with small documented biases (early-season totals, some win-total patterns); sports prediction-market prices are well calibrated away from expiry but show favorite-longshot-style losses on cheap contracts and systematic overpricing of parlays. Prices are good enough to use as probability inputs, with adjustments for horizon and product type.

### Cited Findings
- Dare, Dennis and Paul (Finance Research Letters, 2015): NBA lines move away from the team with player absences, especially meaningful players; no profitable strategy exists betting at the closing line, so the information is incorporated by the close (search summary). — [EconPapers](https://econpapers.repec.org/RePEc:eee:finlet:v:13:y:2015:i:c:p:130-136)
- "Learning, Price Formation and the Early Season Bias in the NBA": totals lines are significantly biased early in each season while sides are not; lines move in the right direction from open to close but do not remove the bias; a simple strategy against closing totals won 56.72% (search summary). — [ETSU](https://dc.etsu.edu/etsu-works/17780)
- Woodland and Woodland, "Testing Profitability in the NBA Season Wins Total Betting Market": the NBA win-total market is somewhat more efficient than the NFL's, yet some profitable strategies were found (abstract only, search summary). — [FiT Publishing](https://fitpublishing.com/node/1114)
- Nylon Calculus (2018, one season): Bovada's preseason win totals had the lowest mean absolute error of six forecast sources; the 30 totals summed to about 1,242 against 1,230 actual wins, indicating upward shading (search summary). — [FanSided / Nylon Calculus](https://fansided.com/2018/04/13/nylon-calculus-evaluating-preseason-win-predictions)
- Bürgi, Deng and Whelan (2026), "Makers and Takers: The Economics of the Kalshi Prediction Market": prices become more accurate near close; a favorite-longshot pattern exists in which cheap contracts lose money after fees; the average return on Kalshi contracts is about minus 20%, and the bias is stronger for takers (search summary; covers all categories, sports not broken out in the summary). — [UCD working paper](https://www.ucd.ie/economics/t4media/WP2025_19.pdf); [CEPR VoxEU](https://cepr.org/index%2Ephp/voxeu/columns/economics-kalshi-prediction-market)
- Kagan and Baiocchi (August 2026), "Calibration in Prediction Markets: Theory and Evidence": sports calibration "tracks the 45 degree line closely" at one-week, one-day and one-hour horizons (search summary). — [GWU working paper 2026-001](https://www2.gwu.edu/~forcpgm/2026-001.pdf)
- Le (2026), "Decomposing Crowd Wisdom": 292 million trades on Kalshi and Polymarket; calibration has domain-specific components; sports is near 1 at short horizons and bias worsens at the longest horizons (search summary). — [arXiv 2602.19520](https://arxiv.org/html/2602.19520v1)
- Moshrefi (15 July 2026), "Prices, Probabilities, and Parlays": using 23 million Kalshi moneyline trades across major leagues, calibration is near-perfect mid-contract and departs sharply near expiry (step-like in the final ten minutes); cross-game parlays are priced above the product of their leg prices, with overpricing growing in leg count (abstract read; no NBA-specific numbers). — [arXiv 2607.14430](https://arxiv.org/abs/2607.14430)
- Kalshi-published research on 22 million resolved markets reports prices track observed outcomes (search summary; venue-authored). — [LiquidityFinder](https://liquidityfinder.com/news/kalshi-research-study-of-22-million-resolved-markets-finds-prices-track-observed-outcomes)
- Practitioner claim: player-prop pricing lags for one to two games after a rest announcement (single unverified source); practitioner pieces assert injury news moves NBA lines within minutes but give no measured latency (search summary). — [Action Network](https://www.actionnetwork.com/education/how-injuries-affect-betting-lines-a-guide-to-market-movement)

### Inferences
- For pricing an insurance-like payoff, single-leg game and mid-horizon sports prices on Kalshi can be read as approximately calibrated probabilities; long-dated futures and cheap longshot strikes (exactly where "star has a bad season" payoffs live) are where bias is largest and buyers overpay.
- Because closing lines already embed public injury information, a hedger gains nothing by reacting to announced injuries; a hedge has to be in place before the news, which is when it most resembles informed trading from the venue's perspective.
- The season-long win-total market is accurate on average but shaded toward overs, which slightly cheapens "under" style protection relative to fair value at sportsbooks.

### Gaps
- No peer-reviewed study was found measuring how fast (in seconds or minutes) NBA injury news is priced into sportsbook or prediction-market prices.
- No study of favorite-longshot bias specific to NBA moneylines or NBA futures was found.
- No multi-season academic measurement of preseason win-total error (MAE) was found; the Woodland paper was seen only as an abstract.
- No calibration study specific to NBA awards, make-playoffs or player-prop contracts on prediction markets was found.

## 7. Precedents for hedging real business exposure with sports markets

### Takeaway
There are real precedents (retailers hedging promotions through a mix of prize-indemnity insurance and multi-million-dollar futures bets, and in 2026 a CME / FutureSports proposal for team-performance index futures explicitly pitched at sponsors, vendors and franchises), but none found involves a team hedging player-health or salary risk, and the earlier attempt at exchange-listed sports futures for commercial hedgers (Eris, 2020) was withdrawn.

### Cited Findings
- Jim "Mattress Mack" McIngvale, 2017 Astros promotion: about $5 million liability hedged through insurance and Las Vegas bets; "The vast, vast majority of the hedge was through the insurance companies"; insurance premium of 10-20% of the refund amount plus more than $1 million in hedge bets (search summary). — [Las Vegas Review-Journal](https://www.reviewjournal.com/sports/sports-columns/todd-dewey/houston-furniture-store-owner-hedges-promotion-with-bets-on-astros/amp)
- McIngvale later said the insurance market takes more margin than sportsbooks; in 2019 insurers withdrew after a hurricane, so he hedged with bets and lost "more than $13 million" when the Astros lost, saying "I feel like I hedged perfectly" (search summary). — [Action Network](https://www.actionnetwork.com/mlb/mattress-mack-world-series-bets-loses-millions); [NPR Planet Money via APR, 27 Oct 2020](https://www.apr.org/business-education/2020-10-27/why-a-man-dressed-as-a-mattress-needed-to-win-a-9-million-sports-bet)
- In 2022 he bet about $10 million across online sportsbooks (about $3 million at Caesars, which paid about $30 million) (search summary). — [CardPlayer](https://cardplayer.com/poker-news/27409-furniture-store-owner-mattress-mack-scores-75m-sports-betting-payout)
- CME / FutureSports "FSPI" sports index futures: per-team indexes for all 32 NHL teams open at 7,500 points each season and move with official in-game statistics; standard contracts are 10x the index and micro contracts one-tenth; margin typically 3-10% of contract value; around-the-clock trading; listing planned for 28 September 2026 pending CFTC review. Pitched hedgers: season-ticket holders, corporate sponsors hedging "key injuries or underperformance", parking operators, retailers and sports franchises. Indexes tied to select NHL athletes are planned. No NBA plans were mentioned. Backers include Marquee Ventures (Cubs ownership), Elysian Park Ventures (Dodgers ownership), Robinhood, CME and John Henry. NHL players, coaches and staff are barred from trading (page read). — [Chicago Sun-Times, 15 Aug 2026](https://chicago.suntimes.com/money/2026/08/15/chicago-startups-futuresports-cme-nhl-etf-bet-sports); [CME product overview](https://www.cmegroup.com/education/lessons/cme-fspi-sports-indexes-product-overview)
- Institutions are 94% of CME volume and observers doubt institutional adoption without a structural reason to hold the contracts (page read). — [Chicago Sun-Times, 15 Aug 2026](https://chicago.suntimes.com/money/2026/08/15/chicago-startups-futuresports-cme-nhl-etf-bet-sports)
- Eris Exchange (2020) proposed NFL-linked futures so casino operators and others economically affected by games could hedge; the CFTC raised sports-gambling concerns and Eris withdrew (page read). — [Chicago Sun-Times, 15 Aug 2026](https://chicago.suntimes.com/money/2026/08/15/chicago-startups-futuresports-cme-nhl-etf-bet-sports)
- Kalshi's contract terms describe new listings as "corresponding to the risk management needs of Members", the exchange's formal hedging rationale. — [Kalshi contract terms](https://kalshi-public-docs.s3.amazonaws.com/contract_terms/BASKETBALLPOINTSRACE.pdf)
- Professional trading firms are structurally involved: Robinhood's Rothera exchange was built with Susquehanna (search summary). — [Zacks](https://www.zacks.com/stock/news/2934984/{https:/www.zackstrade.com/2019-1-dollar})
- Team and athlete commercial ties to venues are forming: Giannis Antetokounmpo became a Kalshi shareholder and partner in February 2026; the Warriors and Kalshi were reported close to a deal in October 2026 (page read). — [RotoWire](https://www.rotowire.com/prediction-markets/nba); [Front Office Sports, 26 Oct 2026](https://frontofficesports.com/article/nba-tips-off-prediction-market-era-with-kalshi-polymarket/)

### Inferences
- The McIngvale history is the closest analogue to the project: a real business liability contingent on a sports outcome, hedged with a blend of insurance (10-20% premium) and bets, with the bet leg sized in the low millions to about $10 million. It hedged a team-level championship outcome, the deepest futures market there is, not a player-level outcome.
- The FutureSports/CME design (continuous index, margin, athlete-level indexes, sponsors hedging "key injuries") is the nearest thing to a purpose-built instrument for the project's use case, but it covers the NHL only, was still awaiting CFTC review in the last report found, and has no demonstrated liquidity.
- Traditional contract-specific insurance (disability, prize indemnity) remains the instrument sized for eight-figure exposures; markets are a complement for pricing and for small, liquid, team-level slices.

### Gaps
- Whether the CME FSPI futures actually launched on 28 September 2026, and any volume since, was not confirmed.
- No sources were collected on bookmakers laying off liability with other books or exchanges, or on funds trading sports outcomes as an asset class; these were not researched within the time available.
- No published proposal for NBA-specific sports derivatives for teams or leagues was found.
- No example was found of a team, league or owner hedging salary or injury exposure through betting or prediction markets.
