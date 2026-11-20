# Independent review: overlooked customer segments, natural counterparties and geographies

Reviewer pass, 2026-11-19. I researched first (about 25 web searches and fetches), then compared against the six existing notes in this folder. I did not edit those notes. "Unverified" marks anything without a primary source. "(old)" marks data from before 2020. Kalshi listings come from the team's own `data/processed/expansion_kalshi_families.csv` (series listed; not all have open markets).

## Top 5 additions

1. **Dairy (and feedlot/poultry) summer heat stress is the missing summer book.** `other_sectors.md` lists dairy heat stress as "not sourced". It is well sourced: US losses run $1.2B/yr (USDA ERS, 2010 data) to about $1.65B/yr (Cornell, including milk fat and protein). At least four parametric THI products already sell (NFU Mutual/Markel UK, Arbol, Rokstone/AIR, SCOR's Heat Stress Protect), which shows people will pay. USDA's LIP pays for heat deaths but not for lost milk, so the yield loss is a real coverage gap. The natural counterparties are those hurt by cool summers (electric utilities, HVAC distributors, beverage sellers). Two problems: Kalshi only lists daily dry-bulb highs, and the dairy belts sit far from the listed cities. Also, warm-side calls paid about 2x their 1951-1995 price (`netting_quant.md`), so pricing needs trend adjustment.
2. **Feedlots are a wet-side counterparty for Plains ranchers in the same winter months.** Mud cuts feedlot cattle gain by about 14% (4-8 in. of mud) to 25% (12-24 in.) (K-State). The loss falls in wet, cold Nov-Mar months in KS/NE/TX/OK, the same season and region the PRF Companion targets. No existing notes mention it. No mud product exists. Feedlots already hedge cattle and corn on CME, so they know how hedging works. This is the only ag segment I found that sits on the *opposite* side from ranchers.
3. **Kalshi launched "Blanket" (Aug 2026), an AI tool that recommends Kalshi hedges to small businesses.** That is a direct competitor to the AgriHedge advisor (doc 24). Business Insurance (Oct 26 2026) names real small-business weather hedgers on Kalshi: a kayak operator (rain), an ice-cream shop (cold), and an online farmers market (heat). Positioning should stress what Blanket lacks: farm-grid basis risk, PRF integration, and payout design.
4. **Aggregators beat retail as counterparties.** Weather-guarantee MGAs such as Sensible (300k+ Campspot guarantees, film shoots since Jul 2026) and snow-cover writers (Vortex/MSI) already hold concentrated wet-day or snow books. Pairing the farmers' dry book against one such book is far cheaper than recruiting thousands of restaurants (my inference). On the farm side, Farm Credit associations already sell PRF, which makes them a channel rather than a counterparty.
5. **Two corrections to the framing.**
   - *Bad-weather winners* (delivery apps, e-commerce, cinemas, generator makers, roofers) gain when it is wet, so they sit on the **same side as farmers**. They are counterparties for the *venue* book, not the farmer book. I found no evidence that any of them hedges its weather upside. Restaurants that also deliver are partly self-hedged, which shrinks venue demand.
   - *International.* Kalshi does list daily high/low temperature contracts for Mexico City, São Paulo, Tokyo, Sydney, Toronto, Mumbai and others, which partly contradicts `uninsured_farmers.md` ("no ... Latin American" contracts). But Australia, Canada and India are on Kalshi's restricted list, and Brazil ISP-blocks it. Australia has the biggest thin-insurance gap I found (multi-peril crop insurance taken by about 1% of NSW winter-crop growers), yet it is closed to Kalshi.

## Q1. Overlooked segments hurt by weather, with evidence they pay

### Takeaway
Livestock heat stress is the strongest new segment. The losses are sourced and large, commercial index products exist, and federal programs leave a gap. Feedlot mud is a smaller but structurally valuable wet-side ag hedger. Poultry, bees, cruise, wildfire and aquaculture add little for a station-contract platform.

### Cited Findings
**Dairy heat stress**
- ERS: heat stress cut 2010 milk output on the average dairy by about 183,000 lb (about $39,000). That scales to $1.2B/yr nationally. The upper critical THI for lactating cows is about 70. Dairy is concentrated in the CA Central Valley, ID, WI, NY and PA, which have lower heat loads. The largest heat increases are projected for the South (old data, published 2014) — [USDA ERS Amber Waves, 2014](https://www.ers.usda.gov/amber-waves/2014/november/greater-heat-stress-from-climate-change-could-lower-dairy-productivity)
- Cornell (6.5M cows, 43 states, 2007-2016): counting milk fat and protein losses roughly doubles the damage, to about $1.65B/yr. Heat response varied little by region or farm size (news summary of an Environmental Research Letters paper; full text not read) — [Food Ingredients First](https://www.foodingredientsfirst.com/news/heat-stress-dairy-ingredient-quality-cornell.html)
- Arbol (Jul 2025): production loss starts above THI 68. It cites a loss of 3% at THI 68-71, 8% at 72-79, 15% at 80-89 and 25% above 89, or $4.16-$14.42 per cow-day (vendor figures). It offers THI, stress-hour and max-temperature triggers as insurance or as derivatives, and says indemnity policies usually exclude production loss — [Arbol](https://www.arbol.io/post/dairy-heat-stress-parametric-insurance-coverage-gaps)
- NFU Mutual (UK) with Skyline Partners, Markel and Gallagher: a parametric heat-stress trial from May 2023 with four coverage levels. 41% of surveyed dairy farmers named heat stress a top concern. No uptake figures were given — [Reinsurance News, 2023-05-23](https://www.reinsurancene.ws/nfu-mutual-launches-innovative-parametric-heat-stress-insurance-for-dairy-farmers/). A later page lists a THI-based product sold to existing customers 1 Sep 2025-1 May 2026 — [ICMIF](https://www.icmif.org/news_story/nfu-mutual-launches-new-parametric-insurance-to-protect-dairy-farmers-from-heat-stress-losses/)
- Other THI products: Rokstone with AIR Parametric (US), and Heat Stress Protect (SCOR, ITK, Skyline; France, embedded in a herd-monitoring system) — [Rokstone](https://rokstoneuw.com/news/tackling-heat-stress-a-new-era-of-protection-for-dairy-farmers); search summary of related pages, not fetched individually
- USDA LIP pays 75% of average fair market value for deaths "directly caused by extreme heat". It does not cover lost production — [FSA LIP fact sheet 2025](https://www.fsa.usda.gov/sites/default/files/2025-04/FSA_LIP_LivestockImdemnityProgram_Factsheet_2025%20FINAL.pdf)

**Feedlots**
- Heat: in June 2022 Kansas reported at least 2,000 heat deaths (counted from carcass-disposal requests). Industry estimated about 10,000 head at about $2,000 each. Humidity spiked while wind dropped to about 5 mph — [CBS/AP, 2022](https://www.cbsnews.com/news/heat-stress-cattle-deaths-kansas); [DTN, 2022](https://www.dtnpf.com/agriculture/web/ag/news/article/2022/06/14/heat-stress-kills-estimated-10-000)
- Mud: 4-8 in. of mud cuts gain about 14%, and 12-24 in. about 25% (K-State). One Michigan State pen trial found a 35.5% ADG loss. Nebraska simulations range 4-36% (2011). Wet plus cold is worst. Many figures come from the 1970s or from simulations (old) — [K-State MF2673](https://bookstore.ksre.ksu.edu/download/how-feeding-site-mud-and-temperature-affect-animal-performance_MF2673); [MSU Extension](https://www.canr.msu.edu/news/don-t-let-the-performance-of-your-cattle-get-stuck-in-the-mud); [UNL](https://Beef.unl.edu/c9405542-1c41-4b9c-a143-f192e1e72917.pdf)

**Poultry**
- The BC heat dome (2021) killed at least 651,000 farm animals, mostly poultry. Fraser Valley broiler growers lost about 400,000 birds, about 20% of a week's production. "Heat prostration" insurance is available to growers with ventilation systems — [Country Life in BC](https://countrylifeinbc.com/record-temps-kill-poultry); [Canadian Poultry](https://www.canadianpoultrymag.com/heat-dome-caused-heartbreaking-losses-for-b-c-livestock-farmers-documents-show/)
- Mississippi extension: many summer losses come from power outages (birds die within 15-30 minutes), not from outside heat alone (old, 1998) — [MSU Extension](https://extension.msstate.edu/news/feature-story/1998/hot-summer-affects-poultry-industry?page=25)

**Beekeeping**
- RMA's Apiculture Pilot already exists as a rainfall index on PRF 0.25° grids (it covers honey, pollen, wax and breeding stock). Fewer than 2% of Illinois colonies were enrolled in 2023 — [RMA API fact sheet](https://www.rma.usda.gov/sites/default/files/2024-02/Apiculture-Pilot-2017-Fact-Sheet.pdf); [farmdoc daily, Oct 2025](https://farmdocdaily.illinois.edu/?p=40686)

**Cruise / tourism**
- Carnival put Hurricane Jeanne's cost at about $0.02/share, on top of $0.03-0.04 from Frances and other 2004 storms (old). Lines reroute: "99 percent" of guests accept the changed itinerary — [MarineLink](https://www.marinelink.com/amp/news/financial-hurricane317511); [CruiseHive](https://www.cruisehive.com/carnival-reveals-what-really-happens-when-a-hurricane-threatens-your-cruise)

### Inferences
- Dairy fits a "count of hot days at station X in Jul/Aug" product, which could be built from a strip of Kalshi daily-high contracts. Kalshi lists daily highs for Phoenix, Dallas, San Antonio, Austin, Houston, Miami, LA and others (team CSV). It lists none for Tulare/Fresno, Boise, Madison or the PA/NY dairy counties, so basis risk is large outside AZ/TX. Kalshi also has no humidity contract.
- Feedlot mud versus rancher drought gives the platform a second *ag* hedger on the opposite side, in the same Plains winter months as the PRF Companion. The gap is still a monthly rain total versus mud days, and feedlots may care more about wet-plus-cold. The pairing is my reasoning, not measured.
- Beekeepers are on the same side as ranchers and are already covered by an under-used RMA product. At most, the PRF Companion's logic could extend to API holders.

### Gaps
- No US dairy heat-stress premium, uptake or loss-ratio data were found for any vendor.
- No study measured the correlation between feedlot mud losses and the monthly rain total.
- Aquaculture, forestry and wildfire weather, school snow days, beach hotels and weddings: I found no usable quantified sensitivity in this pass. Wildfire parametric cover (Arbol, Kettle) is already in `market_maker_model.md`, and Kalshi lists no fire-weather contract.

## Q2. Businesses that benefit from bad weather (natural sellers)

### Takeaway
Wet-weather winners are real, but their gains are daily, national and event-driven. None was found to hedge or sell its weather upside. They are counterparties for venues, not farmers, and only in theory.

### Cited Findings
- **Delivery.** DoorDash says demand "can dramatically outpace" Dasher supply in bad weather. It charges a Weather Impact Fee and ran its Severe Weather Protocol in 500+ locations in 2024 — [DoorDash, 2026](https://about.doordash.com/en-us/news/winter-storm-fern). Hurricane Hilary order volume was +43.82% versus an average Saturday (newsletter, unverified) — [Modern Delivery](https://moderndelivery.substack.com/p/severe-weathers-impact-on-delivery). Peer-reviewed evidence of rain effects on takeaway orders comes from China's Meituan — [Kybernetes 2022](https://unpaywall.org/10.1108%2FK-05-2020-0322)
- **Taxi/ride-hail.** Rain raises demand but drivers do not earn more. Supply falls (about 2.4% fewer paid miles) and the extra demand goes unmet (NYC TLC, 2009-2013) — [Farber, NBER w20604 / QJE](https://www.nber.org/papers/w20604)
- **E-commerce.** Adobe (2023, with The Weather Company): 0.8-1.0 in. of rain lifts online spending about 4.4%, and heavier rain lowers it. Other analysts find little effect — [Spectrum News, 2023](https://spectrumlocalnews.com/us/snplus/weather/2023/11/22/how-the-weather-impacts-online-sales)
- **Cinemas.** Weather shifts movie sales (Dahl and DellaVigna, QJE 2009). Snowstorms cut attendance. One analyst says ordinary bad weather "isn't much of a box office deterrent", and Hurricane Sandy weekend was -28%. The sign is ambiguous — [Dahl-DellaVigna NBER w13718](https://www.nber.org/system/files/working_papers/w13718/w13718.pdf); [CMU snowstorm study](https://www.cmu.edu/entertainment-analytics/documents/technology-impact-on-entertainment/the-perfect-storm.pdf); [CinemaBlend](https://cinemablend.com/new/Weather-Has-Major-Impact-Summer-Moviegoing-Habits-7323.html)
- **Generators (storm/hurricane winners).** Generac's Q4 2024 domestic sales rose 20% to $1.07B after the highest US outage hours since 2010. Helene and Milton raised its 2024 guidance — [Generac Q3 2024 release](https://quantisnow.com/insight/generac-reports-third-quarter-2024-results-5744805); [Generac 10-K 2023](https://sec.gov/Archives/edgar/data/1474735/000143774924005040/gnrc20231231_10k.htm)
- **Roofing.** Beacon Roofing guided 2024 residential shipments lower "on lower expected storm demand" — [Roofing Contractor](https://www.roofingcontractor.com/articles/99212-beacon-wows-in-q4-earnings-call-reports-record-sales-shares-fall-after-hours)
- **Cool-summer losers** (the counterparty for dairy heat): Watsco tied a 12% same-store quarterly drop partly to cooler summer temperatures (year not stated) — [MDM](https://mdm.com/?p=23036)

### Inferences
- A farmer buys dry protection, so the farmer's counterparty must gain when it is dry, that is, be hurt by wet. Delivery, e-commerce, cinemas, roofers and Generac gain when it is wet, the same side as the farmer. They can offset the *venue* book but would compete with farmers for wet-side sellers. For the farmer book, the scarce side is still wet-hurt hedgers: construction and golf (in `other_sectors.md`), plus the feedlots added above.
- Winners do not sell their upside. Historically the weather market's other side came from two-sided energy books, dealers and reinsurers (`market_maker_model.md`). Speculators already provide that on Kalshi, which the WSJ (via search summary) put at $564M of weather volume through July 2026.
- Kalshi's hurricane-landfall binaries (Miami, Tampa, Houston, New Orleans and others) could pair coastal tourism, which loses, against roofing and generator demand, which gains. Neither side hedges today, so this is a novelty rather than a product.

### Gaps
- No DoorDash, Uber or cinema filing quantifies rain sensitivity. The delivery figures are anecdotal.
- No source found any weather *winner* selling protection.

## Q3. Intermediaries, competitors and liquidity

### Takeaway
The most decision-relevant new fact is Kalshi's own small-business hedging tool. Insurers holding weather books and ag lenders work better as wholesale counterparties and distribution channels than as retail segments do.

### Cited Findings
- Kalshi **Blanket** (public week of Aug 7 2026, tryblanket.app): a user describes the business, and an AI identifies exposures and recommends Kalshi contracts (weather, elections, energy, tariffs). It is a "recommendation layer, not a trading platform" and does not execute orders. The article cites about 33M US small businesses as the market — [Crypto Briefing, Aug 2026](https://cryptobriefing.com/kalshi-blanket-small-business-hedging-tool/)
- Business Insurance (Oct 26 2026): businesses hedging on Kalshi include a kayak operator (rain), an ice-cream shop (cold days) and an online farmers market (heat). Kalshi block trades require at least 25,000 contracts and eligible contract participants. Brokers at Aon, Marsh and Alliant cite liquidity, basis and payment-reliability concerns. ForecastEx lists wind-gust contracts near dozens of US cities. The article names no insurer or reinsurer hedging on prediction markets. A search snippet claiming an insurer hedged a $3M coaching bonus could not be traced, so it is unverified — [Business Insurance, 2026-10-26](https://www.businessinsurance.com/prediction-markets-gain-role-in-risk-transfer/)
- Farm Credit associations sell PRF (for example Capital Farm Credit). In a Southeast study, the share of delinquent FCS loans fell 1.5-2 pp after La Niña years. I found no FCS portfolio-level weather hedge — [Capital Farm Credit](https://www.capitalfarmcredit.com/insurance/crop-insurance/pasture-rangeland-forage-insurance/); [AgEcon Search](https://ageconsearch.umn.edu/record/266442/files/Climate%20v%20and%20Ag%20Loand%20Delinquency%20IJEF.pdf)
- Kalshi's liquidity programs: the Market Maker Program was renamed the Designated Liquidity Provider program in May 2026. Rebates apply to block trades of at least 50,000 contracts. Susquehanna is its first institutional market maker. This is already mostly covered in `market_maker_model.md` — [Kalshi Help](https://help.kalshi.com/en/articles/15410219-liquidity-provider-program); [CFTC filing](https://www.cftc.gov/filings/orgrules/rules10142633803.pdf)

### Inferences
- Blanket weakens a pitch built on "an AI advisor for Kalshi hedges". AgriHedge's edge is farm-specific: grid-to-station basis risk, PRF interval selection and payout-shape design (docs 21-24).
- A Sensible-type MGA with a large wet-weekend book is a single counterparty with the opposite sign to a pooled farmer dry book. `netting_quant.md` shows a national book of pairs needs 0.34 capital per premium monthly, versus 0.89 for farmers alone. One B2B deal with such a book could supply the "venue" side.
- Farm Credit and ag lenders fit as a farm-side distribution channel (they already sell PRF) or as buyers of portfolio drought protection. I found no evidence they buy portfolio cover.

### Gaps
- Blanket's usage numbers, pricing and whether it covers farm risk were not found.
- Whether any MGA (Sensible, Vortex, Arbol) lays off risk on Kalshi or CME was not found.

## Q4. Geographies

### Takeaway
Where farm insurance is thinnest and weather contracts are wanted (Australia, India, Kenya/Ethiopia), Kalshi is restricted. Where Kalshi is open (Mexico, Japan, UK/EU, Philippines), it lists only urban daily temperature, not farm-region rain. The US territories are open but have no local contracts.

### Cited Findings
- **Australia.** About 1% of NSW winter-crop producers held multi-peril crop insurance, against about 75% with named-peril cover. Multi-peril premiums run 5-10% of crop value, versus 0.55-3.5% for named-peril (Deloitte; scoping study about 2015, old). Index drought products "haven't developed" (ABARES Outlook 2024). CelsiusPro/WeatherPro sell local derivatives and paid AU$2m+ after La Niña floods — [Deloitte](https://www.deloitte.com/au/en/Industries/consumer-products/perspectives/multi-peril-crop-insurance-australia-barriers-opportunities.html); [Farm Online](https://www.farmonline.com.au/story/8552428/move-over-multi-peril-parametric-insurance-may-be-the-best-dry-bet/); [Artemis](https://www.artemis.bm/news/weatherpro-to-pay-out-more-than-au2m-to-farmers-for-flood-damage-to-crops). Australia and Canada are on Kalshi's restricted list (secondary source, per `uninsured_farmers.md`)
- **Japan.** Historically a diverse corporate market: temperature about 60% and rainfall about 30% of contracts, with wind and snow also used (undated, likely early 2000s). Mitsui Sumitomo launched a parametric "Weather Insurance Index" covering temperature, rain, wind, snow and sunshine (2025), and earlier sold discomfort-index (temperature/humidity) derivatives — [GlobalCapital](https://www.globalcapital.com/article/28mssnrew086objpsagbl/derivatives/japan-develops-as-a-center-for-weather-derivatives); [Reinsurance News](https://www.reinsurancene.ws/mitsui-sumitomo-insurance-launches-parametric-weather-insurance-product); [Risk.net](https://www.risk.net/node/1501292). Kalshi lists Tokyo daily highs and lows (team CSV). Whether Japanese residents can use Kalshi is unverified
- **UK/EU.** NFU Mutual's dairy heat product (above) shows a farm mutual distributing parametric cover. Kalshi lists daily highs for London, Paris, Amsterdam, Berlin, Frankfurt, Brussels and Geneva (team CSV). Polymarket's London market settles at London City Airport (`uninsured_farmers.md`)
- **Philippines.** PCIC covered 6% of paddy farmers as of 2012 (old). A parametric typhoon rice cover based on storm track and wind was piloted for the 2025 wet season — [Oxford Business Group](https://oxfordbusinessgroup.com/reports/philippines/2015-report/economy/the-philippines-broadens-its-natural-disaster-insurance-schemes); [Dept. of Agriculture](https://www.da.gov.ph/pcic-launches-parametric-insurance-to-expedite-claims-payouts/)
- **Puerto Rico.** Local crop insurance is run through Puerto Rico's Agriculture Department insurer, and FCIC shares only part of the risk. An official warned it may lack funds after a storm if it cannot reinsure. Federal catastrophic coverage costs a $655 admin fee per crop. Coffee is the largest insured crop (2,222 crop and 2,190 plantation policies, 2024 RY) — [News is my Business](https://newsismybusiness.com/puerto-ricos-agriculture-insurance-program-fails-to-address-storm-losses-leaving-farmers-vulnerable); [RMA PR SOB 2024](https://www.rma.usda.gov/sites/default/files/2025-04/PUERTO%20RICO%202024RY%20Summary%20of%20Business%20All%20Policies.pdf)

### Inferences
- **Australia:** the largest unmet need, but a local insurer or CelsiusPro partnership would have to sell it, not Kalshi. **Mexico:** open to Kalshi per the secondary list, but only Mexico City temperature is listed, which does not help rain-fed maize. **Puerto Rico:** a US territory (Kalshi access assumed, unverified) with a stated reinsurance gap for plantain and banana storm risk. Kalshi's hurricane contracts list mainland cities, not San Juan.
- Kalshi's foreign city contracts serve traders, not local hedgers. They do not support international bridge insurance.

### Gaps
- Kalshi's restricted list was not checked against the Member Agreement PDF (same gap as `uninsured_farmers.md`). Eurex's current weather listings and any Betfair weather markets were not checked; my belief that Eurex dropped weather futures is unverified.
- Canadian crop-insurance coverage was not researched, since Kalshi is restricted there anyway.

## Segment scorecard (new or materially changed versus existing notes)

| Segment / pair | Variable | Hurt by | Timescale | Quantified sensitivity | Existing hedging | Best counterparty | Kalshi-style fit | Verdict |
|---|---|---|---|---|---|---|---|---|
| Dairy heat stress | THI / daily max temp | Hot, humid days | Days, summed over Jul-Aug | $1.2B/yr (ERS 2014, 2010 data); about $1.65B (Cornell); 3-25% milk loss by THI band (Arbol 2025, vendor) | NFU Mutual, Arbol, Rokstone/AIR, Heat Stress Protect; LIP covers deaths only | Cool-summer losers: electric utilities, HVAC distributors, beverage, water parks | Partial: daily-high strips in AZ/TX only; no humidity; warm-drift pricing risk | **Worth adding** |
| Feedlot mud | Monthly rain plus cold | Wet winters | Month/season (Nov-Mar) | 14-25% lower gain (K-State, old) | None found; feedlots use CME cattle/corn | Dryland ranchers and wheat growers (dry-hurt), same region and months | Monthly rain at OKC/DEN/DFW; Panhandle basis risk | **Worth adding** |
| Feedlot/poultry heat deaths | Max temp, humidity, wind | Heat waves | Days | KS 2022: at least 2,000 (about 10,000 est.) head at about $2,000; BC 2021: about 400k broilers | LIP (75% FMV); heat-prostration insurance | As dairy | Daily highs; event-day | Minor (deaths already covered) |
| Beekeepers | Grid rainfall | Dry | 2-month intervals | Not found | RMA API, <2% IL uptake | Same side as ranchers | Same as PRF | Minor (PRF Companion extension only) |
| Weather-guarantee MGAs / insurers | Rain days, snow | Wet days (book losses) | Day to season | Sensible 300k+ guarantees (vendor) | Reinsurance | Pooled farmer dry book | High (same stations) | **Worth adding** (B2B counterparty) |
| Delivery / ride-hail / e-commerce | Rain, snow | Dry/fine days (lower demand) | Day | Adobe +4.4% at 0.8-1 in. (2023); taxi supply falls (Farber) | Surge fees | Venues (opposite) | Daily, national | Not useful (no hedging; same side as farmers) |
| Cinemas | Rain, snow | Snowstorms; sign of rain effect unclear | Weekend | Sandy -28% weekend | None | Unclear | Poor | Not useful |
| Generators / roofing | Hurricanes, outages, hail | Calm seasons | Season | Generac domestic +20% in Q4 2024 | None (they keep the upside) | Coastal tourism | Kalshi hurricane binaries | Minor |
| Cruise lines | Hurricanes | Storm seasons | Week | $0.02-0.04/share per storm (2004) | Rerouting | - | Poor | Not useful |
| Ag lenders (Farm Credit) | Regional drought | Dry years | Year | Delinquency -1.5 to -2 pp after La Niña (Southeast) | Sell PRF to borrowers | - | Channel, not hedger | Minor (distribution channel) |
| Australia growers | Rain | Dry | Season | MPCI about 1% NSW uptake (Deloitte, old) | CelsiusPro/WeatherPro | - | Kalshi restricted | Not useful via Kalshi |
| Puerto Rico | Hurricanes, rain | Storms | Event | Reinsurance gap stated (no $) | PR insurer, partial FCIC | - | No San Juan contracts | Minor |
