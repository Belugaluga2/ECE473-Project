# Temperature Risk: Heat on Forage and Cattle, and What Kalshi Temperature Contracts Can Hedge

**Proposal cell:** Roadmap item 5 (temperature risk, DEMO.md) / team  |  **Status:** DRAFT (not fact-checked; Kalshi numbers from our own API pull on 2026-11-06)  |  **Last updated:** 2026-11-06

Code: [`scripts/run_temperature_research.py`](../../scripts/run_temperature_research.py) (needs internet). Data: [`kalshi_temperature_series_summary.csv`](../../data/processed/kalshi_temperature_series_summary.csv), [`kalshi_temperature_ladder_coverage.csv`](../../data/processed/kalshi_temperature_ladder_coverage.csv), [`kalshi_temperature_orderbook_20261106.csv`](../../data/processed/kalshi_temperature_orderbook_20261106.csv), [`station_summer_heat_index.csv`](../../data/processed/station_summer_heat_index.csv), [`station_cattle_thi_days.csv`](../../data/processed/station_cattle_thi_days.csv).

Already covered elsewhere, not repeated here: heat and corn/soy yields (doc [03a](03a_rain_yield_corn_soybean.md): Schlenker & Roberts 29°C/30°C thresholds, Tannura July/August temperature, the 2012 loss split of 69% rain / 31% heat, Li et al. on drought plus heat); the overall Kalshi weather catalog (doc [05](05_kalshi_weather_markets.md)); CME HDD/CDD futures and Arbol (doc [02](02_how_farmers_buy_weather_insurance.md)); Luo 2026 and Crosier 2026 on Kalshi temperature markets (doc [10](10_literature_review.md)); the untested idea of a Chicago heat leg (doc [14](../analysis/14_rowcrop_exploration.md)).

**Vocabulary.**
- **THI (temperature-humidity index)**: one number for heat plus humidity. In °F: THI = T − (0.55 − 0.0055·RH)(T − 58). This is the same as the Celsius form 0.8·T + (RH/100)(T − 14.4) + 46.4.
- **LWSI (Livestock Weather Safety Index)**: the standard THI bands for cattle. Normal ≤ 74, alert 75-78, danger 79-83, emergency ≥ 84.
- **Degree-days above X (DD-X)**: the sum over days of max(Tmax − X, 0). For example, a 101°F day adds 6 to DD-95.
- **Listing lead**: the time from when Kalshi opens a market to the start of the period it measures.

## Key findings

1. **Kalshi temperature markets cannot give a farmer summer heat cover bought in advance.**
   - Every US daily high/low market opens about 10 AM Eastern the day before the day it measures. This holds for 17,955 of 17,981 daily events since August 2021; none opened two or more days ahead.
   - The weekly heat series opened at the start of its own week, and ran only from mid-August to October 11, 2026.
   - So in spring there is nothing to buy for July.
2. **Day-ahead markets already know most of the weather.** Kalshi centers each daily ladder on the forecast. In June-August 2026, the actual high landed inside the four middle 2°F bins on 75-95% of days at our cities. Buying day by day hedges the one-day forecast error, not a hot season. This last step is a hypothesis we have not yet tested on prices.
3. **Stations match well for four of our seven PRF sites.**
   - Dallas, San Antonio, Oklahoma City and Denver have daily high and low markets that settle on the same NWS stations as their rain markets (CLIDFW, CLISAT, CLIOKC, CLIDEN).
   - Springfield, Albuquerque and Tampa have no temperature market. Their nearest ones are 150-370 miles away.
   - Chicago's temperature markets settle at Midway (CLIMDW), not O'Hare.
4. **Volume is large; depth is not.**
   - Dallas daily-high events traded a median of 56,453 contracts per day in summer 2026 (5.5 million over June-August).
   - The order book for one next-day ladder held only about 2,563 YES contracts within 5 cents of the best ask, about $460 to buy. That snapshot was taken in November, not summer.
5. **The only seasonal degree-day contract is Cincinnati heating degree-days (KXHDDCVG, Oct-Dec 2026).**
   - It has no farm use and nearly no book: 79 contracts within 5 cents across 9 strikes.
   - Kalshi's filing for it is a class certification, so other places can be listed under the same terms. There is no cooling or heat degree-day contract.
6. **Kalshi can list temperature months ahead when it chooses to.** San Jose's "below 40°F in December 2026" market opened on 2026-08-21, 102 days early, and holds the deepest book in our sample (8,167 contracts within 5 cents). The binding limit is a listing choice, not a rule.
7. **Cattle, not grass, carry most of the heat risk at our sites.**
   - Our search found no estimate of hay yield lost per degree. Shortgrass rangeland production is not significantly related to temperature; rain dominates.
   - US heat-stress losses for beef were modeled at $369 million a year (2003 $): $87M for cows and $282M for feedlots. Texas alone accounts for $33M of the cow losses and $147M of the feedlot losses.
8. **Most exposed sites: Atascosa and Parker, TX, then Hardee, FL and Grady, OK. Least exposed: Elbert, CO and Torrance, NM.**
   - **Atascosa and Parker:** 119-139 days a year at THI ≥ 79, and 44-54 nights with no relief below THI 75.
   - **Hardee:** the most humid-heat days (156 at THI ≥ 79, 79 nights with no relief) but only 5 days a year at 95°F or above, so an "above 95°F" contract would miss its risk.
   - **Elbert and Torrance:** about 3 days a year at THI ≥ 79 and none at 84.
9. **Proposal (hypothesis): a seasonal heat contract.** List a June-August cumulative degree-days-above-95°F ladder (or a THI-day count for humid sites) by March at Dallas, San Antonio and Oklahoma City.
   - The underlying swings a lot. Dallas DD-95 averages 209 with a standard deviation of 135 (1991-2025), and reached 585 in 2011.
   - Kalshi's degree-day template already does this kind of cumulative sum.

## Numbers table

Every number used anywhere in this doc appears here. "Our pull" means `scripts/run_temperature_research.py`, run 2026-11-06 (market data from `api.elections.kalshi.com/trade-api/v2`, live + historical tiers; book snapshot 2026-11-06 20:07 UTC). "Full text" or "abstract" says what was read.

| Quantity | Value | Units | Region / period | Source (URL + page/table) | Verification |
|---|---|---|---|---|---|
| **Kalshi: listing and structure** | | | | | |
| US daily high/low temperature series open now | 24 high + 24 low | series | US cities | our pull (`n_open_events_now`) | CONFIRMED (API) |
| Daily high/low events analyzed | 17,981 | events | 49 series, Aug 2021 - Nov 7 2026 | our pull | CONFIRMED (API) |
| Daily events listed the day before / same day / ≥2 days before | 17,955 / 26 / 0 | events | same | our pull (`listed_days_before`) | CONFIRMED (API) |
| Listing time of 2026 daily events | 14:00 UTC (9,646 events) or 15:00 UTC (1,762) = 10 AM Eastern | UTC hour | 2026 | our pull | CONFIRMED (API) |
| Listing lead, daily events (median = max) | 16 | hours before local midnight | all daily series | our pull (`lead_h_median`, `lead_h_max`; midnight taken as 06:00 UTC) | CONFIRMED (API), ±1 h by time zone |
| Open daily events at pull time | Nov 6 and Nov 7 only | dates | all US cities | our pull | CONFIRMED (API) |
| Markets per daily event | 6 (two tails + four 2°F bins spanning 8°F) | markets | all | our pull; e.g. KXHIGHTDAL-26JUL01: ≤95, 96-97, 98-99, 100-101, 102-103, ≥104 | CONFIRMED (API) |
| Dallas summer ladder, median low-tail cap / high-tail floor | 96 / 103 | °F | Jun-Aug 2026 | `kalshi_temperature_ladder_coverage.csv` | CONFIRMED (API) |
| San Antonio / Oklahoma City / Denver / Chicago, same | 93/100; 94/101; 87/94; 80/87 | °F | Jun-Aug 2026 | same | CONFIRMED (API) |
| Share of summer days on which "high > 95°F" was exactly buildable from the ladder | DAL 0.20, SAT 0.28, OKC 0.24, DEN 0.25, CHI 0.08 | share of 92 days | Jun-Aug 2026 | same (`share_days_buildable`) | CONFIRMED (API) |
| Same for "high > 100°F" | DAL 0.37, SAT 0.37, OKC 0.26, DEN 0.09, CHI 0.02 | share | same | same | CONFIRMED (API) |
| Share of summer days the realized high fell in a middle bin (not a tail) | DAL 0.87, SAT 0.95, OKC 0.75, DEN 0.83, CHI 0.85 | share of 92 days | Jun-Aug 2026 | same (`share_days_middle_bin_won`) | CONFIRMED (API) |
| Daily-high series first measured date in API | DAL, SAT, OKC 2026-02-11; DEN 2024-11-20; CHI 2021-08-19 | date | | `kalshi_temperature_series_summary.csv` (`first_period`) | CONFIRMED (API) |
| Daily-low series first measured date | DAL, SAT, OKC 2026-04-03; DEN, CHI 2025-12-13 | date | | same | CONFIRMED (API) |
| Settlement station in rules text | KXHIGHTDAL/KXLOWTDAL CLIDFW; KXHIGHTSATX/KXLOWTSATX CLISAT; KXHIGHTOKC/KXLOWTOKC CLIOKC; KXHIGHDEN/KXLOWTDEN CLIDEN; KXHIGHCHI/KXLOWTCHI CLIMDW | NWS CLI code | | `rules_primary` of each market, e.g. "maximum temperature recorded at Dallas (CLIDFW) for Nov 7, 2026 ... according to The Weather Company" | CONFIRMED (API) |
| Daily temperature source hierarchy | The Weather Company, then NWS, then national service | | GLOBALTEMPERATURE terms | https://assets.kalshi.com/contract_terms/GLOBALTEMPERATURE.pdf p.1 "Source Agency" | CONFIRMED |
| Position accountability level, daily temperature and HDD | 25,000 | $ per strike per member | | GLOBALTEMPERATURE terms p.2; HDDAREA terms p.4 | CONFIRMED |
| Latest expiration, daily temperature | 3 months after the period | | | GLOBALTEMPERATURE terms p.2 "Expiration Date" | CONFIRMED |
| Nearest Kalshi temperature city to SGF / ABQ / TPA farm points | OKC 252; PHX 359 (DEN 372); MIA 150 | miles | | our calc, farm points from `locations.py`, airport coordinates approximate | UNVERIFIED (airport coordinates not from a cited source; ±2 mi) |
| Midway / O'Hare to Kane Co. farm point | 36 / 26 | miles | | same | UNVERIFIED (Midway coordinates approximate) |
| Station-to-farm distance, DFW / SAT / OKC / DEN | 46 / 45 / 30 / 47 | miles | | 00_OVERVIEW study-site table (from `locations.py`) | CONFIRMED (doc) |
| Chicago monthly-rain settlement moved Midway → O'Hare | Sep 2026 | | | doc 05, Key findings (line "Chicago also switched stations") | CONFIRMED (doc 05) |
| Weekly Phoenix average (KXHEATAPHX) / Atlanta weekly (KXAVGTATL) listing lead | −39.5 / −15.5 (listed after the week began) | hours | Aug 2026 | series summary | CONFIRMED (API) |
| Monthly-rain family volume, live window | 1.8 | million contracts | all cities, after 2026-08-30 cutoff | doc 05 catalog table | CONFIRMED (doc 05) |
| Orders for a season-long daily-binary DD-95 hedge | 92 days × 4-5 strikes ≈ 370-460 | orders | Jun-Aug | our arithmetic | derived |
| **Kalshi: volume and depth** | | | | | |
| Dallas daily high, median volume per day | 56,453 | contracts (all 6 strikes) | Jun-Aug 2026 | series summary (`vol_per_event_summer26_median`) | CONFIRMED (API) |
| Dallas daily high, total volume | 5,488,595 (Jun-Aug 2026); 15,452,362 (all) | contracts | | same | CONFIRMED (API) |
| Median volume per summer day, other study cities | SAT 20,566; OKC 31,329; DEN 48,998; CHI 110,441 | contracts | Jun-Aug 2026 | same | CONFIRMED (API) |
| Median volume per summer day, daily lows | DAL 10,622; SAT 7,635; OKC 11,670; DEN 14,761 | contracts | Jun-Aug 2026 | same | CONFIRMED (API) |
| Next-day ladder depth, YES within 5¢ of best ask, all 6 strikes | DAL 2,563 ($460); SAT 2,380 ($465); OKC 1,150 ($170); DEN 2,314 ($580); DAL low 649 ($127) | contracts (cost) | Nov 7 2026 events, snapshot 2026-11-06 20:07 UTC | `kalshi_temperature_orderbook_20261106.csv` | CONFIRMED (one snapshot, November) |
| Dallas "74°F or above" (upper tail), YES ask / depth within 5¢ | $0.02 / 885 contracts | | same | same | CONFIRMED (one snapshot) |
| **Kalshi: weekly, monthly, seasonal** | | | | | |
| Weekly heat series (KXAVGTK*), cities | 10 (incl. DFW, SAT, OKC, DEN) + KXAVGTATL | series | Aug 17 - Oct 11 2026 | series summary | CONFIRMED (API) |
| Weekly heat contract | "N+ consecutive days with daily average > 90°F", N = 2-6, TWC hourly at KDFW etc. | | | KXAVGTKDFW `rules_primary` / `rules_secondary` | CONFIRMED (API) |
| Weekly heat events per city / open now | 8 / 0 | events | | series summary | CONFIRMED (API) |
| Weekly heat listing lead | median 2 h, max 6 h (opens at start of its week) | hours | | series summary | CONFIRMED (API) |
| Weekly heat total volume | DFW 61,262; SAT 42,858; OKC 153,619; DEN 11,861 | contracts | 8 weeks | series summary (`vol_total`) | CONFIRMED (API) |
| KXHDDCVG period / listed / lead | Oct 1 - Dec 31 2026 / 2026-09-19 01:00 UTC / 12 days | | Cincinnati KCVG | series summary; market rules | CONFIRMED (API) |
| KXHDDCVG strikes / total volume | 9 ("below 1,250" to "below 1,650", step 50) / 23,954 | contracts | | series summary; book CSV | CONFIRMED (API) |
| KXHDDCVG depth within 5¢, all strikes | 79 contracts ($24); typical quotes 0.86 bid / 0.99 ask | | snapshot 2026-11-06 | book CSV | CONFIRMED (one snapshot) |
| HDDAREA definition | HDD = 65°F − daily mean, floored at 0; TWC "HDD (65)" column; cumulative sum over the period | | | https://assets.kalshi.com/contract_terms/HDDAREA.pdf p.1-2 | CONFIRMED |
| HDDAREA certification | class certification under 40.2(d), listed after close 2026-09-18; terms allow "iterations ... corresponding to variations of <area>" | | | https://assets.kalshi.com/regulatory/product-certifications/HDDAREA.pdf p.1; terms p.1 | CONFIRMED |
| Cooling / heat degree-day series | none | | full weather catalog, 501 series | our pull of `/series?category=Climate and Weather` | CONFIRMED (API) |
| KXSJCLOWT (San Jose < 40°F in Dec 2026): listed / lead | 2026-08-21 / 102 days | | | series summary | CONFIRMED (API) |
| KXSJCLOWT volume / depth within 5¢ | 6,821 / 8,167 contracts ($7,081) | | snapshot 2026-11-06 | book CSV | CONFIRMED (one snapshot) |
| TEMPTHRESHOLD certification date | 2026-03-05 | | | https://assets.kalshi.com/regulatory/product-certifications/TEMPTHRESHOLD.pdf p.1 | CONFIRMED |
| KXMSNLOWT (Madison) | window runs from listing (2026-10-13) to Oct 31; 7,487 contracts | | | market rules; series summary | CONFIRMED (API) |
| KXMAXTEMP100, KXHEATWARNING, KXWEEKHT* | 0 markets in API | | | our pull | CONFIRMED (API) |
| **Station heat climatology (our calc)** | | | | | |
| Jun-Aug DD-95, mean / SD / max (year) | DFW 209 / 135 / 585 (2011); SAT 194 / 131 / 550 (2023); OKC 120 / 121 / 558 (2011); SGF 29 / 39 / 165; DEN 36 / 28 / 143; ABQ 50 / 35 / 159; TPA 4 / 5 / 20; ORD 5 / 10 / 47 | °F-days | 1991-2025 | `station_summer_heat_index.csv`, from NOAA ACIS threaded daily Tmax (data.rcc-acis.org) | CONFIRMED (our calc) |
| Jun-Aug DD-95, minimum year | DFW 37 | °F-days | 1991-2025 | same | CONFIRMED (our calc) |
| Jun-Aug days with Tmax > 100°F, mean / SD / max | DFW 15.0 / 14.4 / 56; SAT 11.1 / 13.2 / 55; OKC 8.5 / 11.5 / 52; TPA 0 | days | 1991-2025 | same | CONFIRMED (our calc) |
| Jun-Aug days with Tmax > 95°F, mean | DFW 46.6; SAT 48.1; OKC 26.5; SGF 8.9; DEN 12.9; ABQ 18.0; TPA 2.9 | days | 1991-2025 | same | CONFIRMED (our calc) |
| Days/yr max THI ≥ 79 / ≥ 84; nights min THI ≥ 75; days Tmax ≥ 95°F (all year) | DFW 119 / 29.0 / 44.0 / 62.8; SAT 139 / 22.6 / 53.7 / 68.3; OKC 88 / 16.5 / 3.7 / 31.4; SGF 59 / 5.8 / 1.8 / 12.0; DEN 2.9 / 0 / 0 / 16.2; ABQ 3.4 / 0 / 0 / 19.3; TPA 156 / 18.8 / 79.4 / 5.0 | days per year | 2005-2024 | `station_cattle_thi_days.csv`, from Iowa Environmental Mesonet ASOS hourly (mesonet.agron.iastate.edu) | CONFIRMED (our calc) |
| **Cattle heat stress** | | | | | |
| LWSI categories | normal ≤ 74; alert 74 < THI < 79; danger 79 ≤ THI < 84; emergency ≥ 84 | THI | | Mader, Davis & Brown-Brandl 2006, J. Anim. Sci. 84:712, p.714 | CONFIRMED (full text) |
| THI formula (°C) | 0.8·T + (RH/100)(T − 14.4) + 46.4 | | | Mader et al. 2006 table footnotes; Amundson et al. 2006 p.3416 | CONFIRMED (full text) |
| Pregnancy rate per unit of heat, first 21 days of breeding | −2.06 per THI unit; −3.79 per °C of daily minimum temperature | % pregnancy rate | SE Nebraska, 10 years, Bos taurus | Amundson, Mader, Rasby & Hu 2006, J. Anim. Sci. 84:3415, abstract | CONFIRMED (full text) |
| Pregnancy thresholds | daily average THI 72.9; daily min temperature 16.7°C | | same | Amundson et al. 2006, abstract and Table 4 | CONFIRMED (full text) |
| Heat Load Index threshold, black Bos taurus / Brahman | 86 / 96 | HLI | Australian feedlots | Gaughan, Mader, Holt & Lisle 2008, J. Anim. Sci. 86:226 | abstract only |
| Bull semen quality | motility down by week 2 of heat; normal 8 weeks after heat ended | weeks | Angus bulls, Oklahoma chambers | Meyerhoeffer et al. 1985, J. Anim. Sci. 60:352 | abstract only |
| US livestock heat-stress loss, no / optimal cooling | 2.4 / 1.7 | $ billion/yr (2003 $) | US | St-Pierre, Cobanov & Schnitkey 2003, J. Dairy Sci. 86(E.Suppl):E52, abstract | CONFIRMED (full text) |
| By industry | dairy 897, beef 369, swine 299, poultry 128 | $ million/yr | US | same, abstract | CONFIRMED (full text) |
| Beef cows / finishing cattle | 86.98 / 282.44 | $ million/yr | US | same, Table 14 p.E71 | CONFIRMED (full text) |
| Beef-cow loss per head | 2.60 (US); 6.07 (TX) | $/cow/yr | | same, p.E68 | CONFIRMED (full text) |
| State beef-cow losses | TX 33.18; OK 8.02; MO 5.05; FL 4.94; CO 0.33; NM 0.30 | $ million/yr | | same, Table 14 | CONFIRMED (full text) |
| State feedlot losses | TX 146.58; OK 15.74; CO 7.58; NM 3.29; MO, FL 0 | $ million/yr | | same, Table 14 | CONFIRMED (full text) |
| Beef-cow heat-stress hours per year | FL 2,400; TX 1,991; OK 1,504; MO 1,105; CO 313; US mean 1,216 | hours/yr | long-run weather | same, Table 8 p.E65 (NM printed as 9005, likely a typo) | CONFIRMED (full text) |
| Beef-cow deaths and extra days open (TX) | 2.7 per 1,000; 1.6 days | | TX | same, Table 8 | CONFIRMED (full text) |
| Model THI thresholds | beef cows 75; finishing cattle 72 | THI | | same, Table 1 p.E55 | CONFIRMED (full text) |
| Humid heat wave death toll at moderate temperature | "several hundred" feedlot cattle at max 90-95°F, 50-70% RH | | Nebraska, Aug 6-10 1992 | Hahn & Nienaber 1993, USMARC Beef Research Progress Report 4:146 | abstract only |
| Kansas feedlot heat deaths | ≥ 2,000 head (KDHE); later 2,773 carcasses | head | SW Kansas, June 11-13 2022 | AP via PBS NewsHour; KCUR 2022-07-28 (news quoting KDHE) | UNVERIFIED (secondary) |
| Global cattle heat-stress loss by 2085 | 39.94 (SSP5-8.5); 14.89 (SSP1-2.6) | $ billion/yr (2005 $) | global | Thornton et al. 2022, Lancet Planet. Health 6:e192 | abstract only |
| US dairy heat-stress cost | about 1.2 | $ billion/yr | US, 2010 | Key & Sneeringer, USDA ERS Amber Waves, Nov 2014 | CONFIRMED (full article) |
| **Forage** | | | | | |
| Fescue toxicosis: steer gain, high vs low endophyte | MO 0.97 vs 1.41; TX 0.99 vs 2.14 | lb/day | multi-state trials | Naumann, MU Extension G4669 (rev. Apr 2026), Table 1 | CONFIRMED (full text) |
| Fescue toxicosis cost to US beef | > 609 | $ million/yr (1990 data) | US | same | CONFIRMED (full text) |
| Tall fescue acres in Missouri | about 17 million | acres | MO | same | CONFIRMED (full text) |
| Tall fescue production by July 1 | 60-70 | % of annual | Illinois | NRCS Illinois Grazing Manual, "Tall Fescue" fact sheet | CONFIRMED (full text) |
| Tall fescue leaf growth range / optimum | 4-35 / 20-25 | °C | | Oregon State Tall Fescue Monograph | UNVERIFIED (search snippet) |
| Bahiagrass production Apr-Sep | > 85 | % of annual | Florida | Newman, Vendramini & Blount, UF/IFAS EDIS SS-AGR-332 | CONFIRMED (full text) |
| Heifer gain on bahiagrass, Jun-Jul vs Aug-Sep | 1.2-1.3 vs 0.3-0.4 | lb/day | Florida | same, "Animal Performance" | CONFIRMED (full text) |
| Forage degradability per +1°C | −0.39 (roughages); −0.55 (all feeds) | % per °C | meta-analysis | Moyo & Nsahlai 2021, Animals 11:172 | abstract only |
| Shortgrass forage vs temperature | not significantly related (52-year record) | | Central Plains Experimental Range, CO | Lauenroth & Sala 1992, Ecol. Appl. 2:397 | abstract only |
| Hay production per unit of drought intensity | −12 | % | US counties, 2000-2022 | Rodziewicz, Dice & Cowley 2023, KC Fed RWP 23-06, pp.3-4 | CONFIRMED (full text) |
| Texas 2011 drought and heat ag losses | 7.62 | $ billion | Texas 2011 | AgriLife Extension via TWRI newsletter, Mar 2012 | CONFIRMED (full text) |
| **Programs** | | | | | |
| LIP payment rate; heat eligible | 75% of prior-year market value; "excessive heat" listed | | US | FSA news release 2023-08-25 | CONFIRMED (full page) |
| LIP 2023 rate, beef > 800 lb | raised from $1,244 to $1,618 per head | $/head | 2023 | same | CONFIRMED (full page) |
| PRF sales closing for crop year 2027 | 2026-12-01 | date | | doc 01 numbers table | CONFIRMED (doc 01) |

## 1. What heat does to forage

- **No one has a "hay lost per degree" number.** We found no county-level estimate of hay or pasture yield per °C or per degree-day. The nearest studies show that drought drives hay losses (−12% hay production per unit of drought intensity, Rodziewicz et al. 2023) or that rain dominates and temperature adds little: Kansas alfalfa (Baral et al. 2022, abstract only) and the 52-year shortgrass record (Lauenroth & Sala 1992). So heat's direct effect on forage is an open gap, not a known parameter.
- **Cool-season grass (Dade Co., MO, tall fescue).** Fescue does 60-70% of its growing before July 1 and slumps in summer heat. Heat also hurts the cattle through fescue toxicosis, which is worse in hot weather: steers on toxic fescue gained 0.97 vs 1.41 lb/day in Missouri.
- **Warm-season grass (Hardee Co., FL, bahiagrass).** Bahiagrass grows best in heat (over 85% of its production comes April-September). Heat lowers quality, not quantity: heifer gain falls from 1.2-1.3 lb/day in June-July to 0.3-0.4 in August-September.
- **Rangeland (Elbert Co., CO; Torrance Co., NM).** Rain is the main driver. Heat acts mostly by drying the soil, which PRF's rain index already partly captures.
- **Heat compounds drought.** Texas lost $7.62 billion in farm value in 2011, a drought-plus-heat year. That was also the record year for DD-95 at Dallas (585) and Oklahoma City (558).

## 2. What heat does to beef cattle

- **The thresholds are standard.** The LWSI bands (alert above 74, danger from 79, emergency from 84) are the usual guide. Amundson et al. found pregnancy rates start to fall at a daily *average* THI of 72.9, which corresponds to a much hotter daily peak.
- **The losses come from three places:**
  - Lower conception: −2.06 percentage points of pregnancy rate per THI unit in the first 21 days of breeding.
  - Lower gain and feed intake, mostly in feedlots.
  - Deaths in humid heat waves with no night cooling. In Nebraska in 1992 several hundred cattle died at only 90-95°F, and in Kansas in 2022 at least 2,000 died (news reports, UNVERIFIED).
- **The money is in feedlots and in Texas.** St-Pierre et al. (2003) put beef heat-stress losses at $369M a year: $282M for finishing cattle and $87M for cows. Texas accounts for $33M of the cow losses and $147M of the feedlot losses. Per cow the loss is small: $2.60 for the US average and $6.07 in Texas. For a cow-calf rancher, heat is a tail risk of rare mass-death and conception-loss years, not a steady cost.
- **Breed matters.** Brahman-type cattle tolerate about 10 more Heat Load Index units than black Bos taurus cattle (96 vs 86). Florida and South Texas herds are often part-Brahman, which lowers their real exposure.
- **The safety net is thin.** LIP pays 75% of market value for heat deaths above normal mortality. No federal insurance product pays on heat for pasture: PRF pays on rain, and LRP and LGM cover price. THI index insurance has been studied for dairy (Deng et al. 2007, Georgia, abstract only), but we found nothing for US beef.

## 3. Which study sites are most exposed

| Site (farm county) | Days THI ≥ 79 / ≥ 84 | Nights no relief (min THI ≥ 75) | Jun-Aug DD-95 mean (SD) | State cow + feedlot loss, $M/yr | Kalshi temperature market at the station? | Rank |
|---|---|---|---|---|---|---|
| SAT (Atascosa, TX) | 139 / 22.6 | 53.7 | 194 (131) | TX 33.2 + 146.6 | yes, CLISAT daily high/low | 1 |
| DFW (Parker, TX) | 119 / 29.0 | 44.0 | 209 (135) | TX | yes, CLIDFW daily high/low | 1 |
| TPA (Hardee, FL) | 156 / 18.8 | 79.4 | 4 (5) | FL 4.9 + 0 | no (Miami, 150 mi) | 3 |
| OKC (Grady, OK) | 88 / 16.5 | 3.7 | 120 (121) | OK 8.0 + 15.7 | yes, CLIOKC daily high/low | 4 |
| SGF (Dade, MO) | 59 / 5.8 | 1.8 | 29 (39) | MO 5.1 + 0 | no (Oklahoma City, 252 mi) | 5 (plus fescue toxicosis) |
| ABQ (Torrance, NM) | 3.4 / 0 | 0 | 50 (35) | NM 0.3 + 3.3 | no (Phoenix 359 mi, Denver 372 mi) | 6 |
| DEN (Elbert, CO) | 2.9 / 0 | 0 | 36 (28) | CO 0.3 + 7.6 | yes, CLIDEN daily high/low | 6 |

What the table shows:
- **Dry heat and humid heat need different indexes.** Tampa has the most THI-danger days but almost no 95°F days. A contract on air temperature would miss Florida's cattle risk, which needs THI or nighttime-minimum contracts.
- **The markets sit where the heat is.** The three hot Plains sites (Dallas, San Antonio, Oklahoma City) are where Kalshi already has daily markets on the right station.
- **The station-to-farm gap still applies.** At the four sites with markets, the farm counties are 30-47 miles from the airport (overview). Denver's and Albuquerque's farm counties are probably cooler than the airport (UNVERIFIED).

## 4. Kalshi temperature contracts in detail

### 4.1 Which markets exist at our stations

| Study station | Daily high | Daily low | Weekly heat (Aug-Oct 2026 only) | Monthly / seasonal |
|---|---|---|---|---|
| DFW | KXHIGHTDAL (CLIDFW), since 2026-02-11 | KXLOWTDAL, since 2026-04-03 | KXAVGTKDFW (KDFW) | none |
| SAT | KXHIGHTSATX (CLISAT), since 2026-02-11 | KXLOWTSATX, since 2026-04-03 | KXAVGTKSAT | none |
| OKC | KXHIGHTOKC (CLIOKC), since 2026-02-11 | KXLOWTOKC, since 2026-04-03 | KXAVGTKOKC | none (KXYEARLOWOKC has no markets) |
| DEN | KXHIGHDEN (CLIDEN), since 2024-11-20 | KXLOWTDEN, since 2025-12-13 | KXAVGTKDEN | none |
| SGF, ABQ, TPA | none | none | none | none |
| ORD (contrast) | KXHIGHCHI (**CLIMDW, Midway**), since 2021-08-19 | KXLOWTCHI (CLIMDW) | none | none |

- **Settlement.** Daily markets settle on "the maximum [minimum] temperature recorded at <city> (CLIxxx) ... according to The Weather Company". Under the GLOBALTEMPERATURE terms, The Weather Company comes first and the NWS is the backup, and the first non-preliminary report counts.
- **The settlement station is the same one as the rain markets** at Dallas, San Antonio, Oklahoma City and Denver. Chicago is the exception: the temperature markets use Midway, while the monthly-rain markets moved to O'Hare in September 2026 (doc 05).
- **Older series settled on the NWS report directly.** Examples are HIGHNY and the legacy Chicago tickers.

### 4.2 How far ahead markets are listed

| Product | Listed | Lead before the measured period |
|---|---|---|
| Daily high/low, all 49 US series | ~10 AM Eastern the day before | about 16 h; 17,955 of 17,981 events listed the day before, 26 the same day, none earlier |
| Weekly heat (KXAVGTK*) | at the start of its own week (Monday, about local midnight) | 2-6 h |
| Weekly Phoenix average (KXHEATAPHX), Atlanta (KXAVGTATL) | after the week started | negative |
| Madison "below 30°F" (KXMSNLOWT) | 2026-10-13, window "from issuance" to Oct 31 | 0 by design |
| Cincinnati HDD (KXHDDCVG), Oct-Dec | 2026-09-19 | 12 days |
| San Jose "below 40°F" in December (KXSJCLOWT) | 2026-08-21 | 102 days |

**Answer for a farmer:** Kalshi lists no summer heat cover in advance. The daily markets that hold the volume appear one day ahead, so a rancher cannot lock in July heat cover in March, or by December 1 when PRF choices are made. The San Jose and Cincinnati listings show that Kalshi's month- and season-long temperature templates can be listed weeks to months early. It has just not done so for summer heat at any of our cities.

### 4.3 Ladder shape and depth

- **Each daily event has six markets:** two open tails and four 2°F bins, 8°F wide in all, centered on the forecast. In Dallas the summer ladder ran from "95°F or below" to "104°F or above" at the median.
- **"High above X" exists only when X sits on a bin edge inside the ladder.** In Dallas that was true on 20% of summer 2026 days for 95°F and 37% for 100°F. On other days the threshold sits outside the 8°F window (where the outcome is nearly certain anyway) or on an odd degree.
- **Volume is large.** A Dallas summer day traded a median of 56,453 contracts. That is far more than any monthly rain market (doc 05: the whole monthly-rain family traded 1.8M contracts in its live window).
- **Depth is thin.** The next-day ladders on 2026-11-06 held 1,150-2,563 YES contracts within 5 cents of the best ask across all six strikes at each study city ($170-580 to buy). The Dallas upper tail had 885 contracts at about 2 cents. That is a few hundred to a few thousand dollars of payout per city per day, similar in scale to the rain books (doc 12). This was one November snapshot taken a few hours after listing; summer depth is UNVERIFIED.

### 4.4 Degree-day and monthly series

- **KXHDDCVG (Cincinnati heating degree-days, Oct 1 - Dec 31, 2026)** is Kalshi's only cumulative degree-day contract. It is a "below X" ladder with 9 strikes from 1,250 to 1,650.
  - Each day contributes 65°F minus the day's mean temperature, floored at zero, using The Weather Company's "HDD (65)" column at KCVG. The period total is the sum.
  - It has traded 23,954 contracts in all. The book is nearly empty: 79 contracts within 5 cents across all strikes, and quotes like 0.86 bid / 0.99 ask.
  - The filing is a class certification, so Kalshi can list "variations of <area>" under the same terms.
- **Cooling degree-days:** none, and no other seasonal heat index either.
- **Monthly thresholds:** KXSJCLOWT and KXMSNLOWT are cold-side, for San Jose and Madison. The old national US average temperature series (KXAVGTEMP) has been dead since 2023. KXMAXTEMP100 and KXHEATWARNING have no markets.

## 5. Design: a degree-day heat hedge

### 5.1 Building it from daily binaries (works on paper)

The aim is to pay $1 for each degree-day above 95°F at DFW over June 1 - August 31.
- **Count version.** Buy one "high > 95°F" contract every day. The season's payout equals the number of days above 95.
- **Degree-day version.** On each day, also buy "high > 97", "> 99", "> 101" and so on, each sized 2 (the bins are 2°F wide). The payout then approximates DD-95 to within the 2°F step.
- **Size.** Over a season this is 92 days × 4-5 strikes, about 370-460 small orders, placed by a bot each morning at 10 AM Eastern.

### 5.2 The timing problem (why it is not insurance)

- **Each price is set after the forecast is known.** The ladder is centered on the forecast, and the actual high fell inside its middle 8°F on 75-95% of summer days. So when a heat wave is forecast, "high > 100" already costs close to $1. The rancher pays for the heat wave on the day it arrives, and the hedge pays back roughly what it cost.
- **What it does cover is the forecast miss.** The day-by-day strategy hedges only the gap between each day's forecast and the outcome.
- **Hypothesis H1:** summed over a season, these one-day forecast errors have a much smaller spread than the season index itself. For DFW, DD-95 swings with an SD of 135 around a mean of 209.
  - If H1 holds, the daily-binary hedge removes little of the year-to-year heat risk a rancher actually faces.
  - Test: pull the first-hour price of each Jun-Aug 2026 Dallas ladder (candlesticks) and compare the season's sum of (outcome − price) with the 1991-2025 spread of DD-95. Repeat in summer 2027.
- **Hypothesis H2:** buying 370-460 orders a season across 2-cent spreads costs more in spread and fees than the forecast-error cover is worth. Not tested.
- **Bottom line on timing.** In March, or on PRF's December 1 sales closing, there is nothing to buy for July. That is the core problem, not geography or depth.

### 5.3 What to propose instead (hypothesis)

- **Contract.** "Will cumulative degree-days above 95°F at Dallas-Fort Worth (CLIDFW), June 1 - August 31, 2027, be above X?" Use strikes at 100, 200, 300, 400 and 500, which span the 1991-2025 range of 37 to 585 at DFW.
  - It is the HDDAREA template with Tmax − 95 in place of 65 − mean.
  - List it at DFW, SAT and OKC by March 1 (ideally by December 1, to pair with PRF elections).
  - The variant for cattle and humid sites is a count of days with daily max THI ≥ 84, or nights with min THI ≥ 75, during June-August. These matter for Tampa and San Antonio. They would need hourly humidity in the settlement data and a new certification (UNVERIFIED).
- **Why this design.**
  - (a) The underlying swings a lot from year to year (DFW DD-95 SD 135). Its peaks (2011 at DFW and OKC, 2023 at SAT) were Texas drought years. Whether it stacks with PRF or overlaps it is untested: summer is inside PRF's insurable intervals, unlike the companion's Nov-Feb.
  - (b) One contract a season replaces about 370-460 daily orders.
  - (c) Kalshi already lists season-long temperature markets with month-plus lead (San Jose 102 days, Cincinnati 12 days). The HDD terms are a class certification that allows new areas, though a cooling version probably needs new terms (UNVERIFIED).
- **Untested for our use (hypothesis H3).** We have not shown that DD-95 at the airport tracks a ranch's real heat loss. Neither the forage studies nor St-Pierre give a per-ranch dollar link. The first test would be DD-95 or THI-days against Texas and Oklahoma cow-calf outcomes, such as state calf crop or weaning weights from NASS. The size of the gain is unknown.
- **Liquidity.** Kalshi's only seasonal degree-day market (Cincinnati HDD) has an empty book. A summer heat ladder would need the same market-maker plan as the rain companion (doc 22, roadmap 7).

## Implications for our replication design

- A temperature leg cannot be added to the PRF Companion with today's listings. The companion is bought ahead for Nov-Feb, and temperature markets list one day ahead.
- The realistic Milestone III item is a contract proposal (5.3) plus the H1 test on summer 2026 prices. A live hedge is not possible yet.
- If we model heat for cattle, use THI, not air temperature, and treat Florida separately.
- Do not pair the Chicago row-crop farm with KXHIGHCHI without noting that it settles at Midway.

## Unverified claims and open questions

- **Summer order-book depth.** We took one book snapshot, in November. Take one during a June-August 2027 week.
- **H1-H3** in section 5. None are tested.
- **Forage heat effects.** There is no hay yield-per-degree estimate. The tall fescue 20-25°C optimum and an 86°F growth stop are snippet-only. We found no forage-specific bermudagrass optimum. Khusru, Tronstad & Aradhyula (2025, AAEA), on PRF and beef cows using degree-days above 34°C, could not be opened; its coefficients would be the closest link to our question.
- **Cattle deaths.** The 2022 Kansas toll comes from news reports quoting KDHE, not KDHE itself. Busby & Loy (1996) on the 1995 Iowa deaths (3,750 head) is snippet-only and not used above. We did not open the original 1970 LCI document for the LWSI bands; we took them as cited by Mader et al. 2006.
- **Feed-intake effects.** We could not open the NRC (1981) temperature adjustments.
- **Distances.** The nearest-market distances use approximate airport coordinates.
- **Elevation.** Elbert and Torrance counties are probably cooler than their airports; not checked.
- **Whether a CDD or Tmax degree-day contract needs a new CFTC filing**, or fits under HDDAREA, is our reading of the terms, not Kalshi's statement.
- **Lead-time arithmetic** treats local midnight as 06:00 UTC, which is off by ±1 hour for Eastern and Mountain stations. The day counts (listed the day before) do not depend on this.
- **Luo (2026) temperature basis-risk numbers** remain abstract-only (doc 10).

## Sources

**Kalshi (all retrieved 2026-11-06)**
- Kalshi public market-data API, https://api.elections.kalshi.com/trade-api/v2: `/series?category=Climate and Weather`, `/markets`, `/historical/markets`, `/markets/{ticker}/orderbook`. Pulled by `scripts/run_temperature_research.py`.
- GLOBALTEMPERATURE contract terms, https://assets.kalshi.com/contract_terms/GLOBALTEMPERATURE.pdf, and certification (2025-12-08), https://assets.kalshi.com/regulatory/product-certifications/GLOBALTEMPERATURE.pdf.
- HDDAREA contract terms, https://assets.kalshi.com/contract_terms/HDDAREA.pdf, and class certification (2026-09-18), https://assets.kalshi.com/regulatory/product-certifications/HDDAREA.pdf.
- TEMPTHRESHOLD certification (2026-03-05), https://assets.kalshi.com/regulatory/product-certifications/TEMPTHRESHOLD.pdf.
- GLOBALTEMPERATURESUSTAINED (weekly) terms, https://assets.kalshi.com/contract_terms/GLOBALTEMPERATURESUSTAINED.pdf.

**Weather data**
- NOAA Regional Climate Centers, ACIS StnData (threaded station records DFWthr, SATthr, OKCthr, SGFthr, DENthr, ABQthr, TPAthr, ORDthr), https://data.rcc-acis.org.
- Iowa Environmental Mesonet ASOS archive (hourly temperature and relative humidity, 2005-2024), https://mesonet.agron.iastate.edu/request/download.phtml.

**Cattle**
- Mader, T. L., Davis, M. S., & Brown-Brandl, T. (2006). Environmental factors influencing heat stress in feedlot cattle. J. Anim. Sci. 84:712-719. https://doi.org/10.2527/2006.843712x
- Amundson, J. L., Mader, T. L., Rasby, R. J., & Hu, Q. S. (2006). Environmental effects on pregnancy rate in beef cattle. J. Anim. Sci. 84:3415-3420. https://doi.org/10.2527/jas.2005-611
- St-Pierre, N. R., Cobanov, B., & Schnitkey, G. (2003). Economic losses from heat stress by US livestock industries. J. Dairy Sci. 86(E. Suppl.):E52-E77. https://doi.org/10.3168/jds.S0022-0302(03)74040-5
- Gaughan, J. B., Mader, T. L., Holt, S. M., & Lisle, A. (2008). A new heat load index for feedlot cattle. J. Anim. Sci. 86:226-234. https://doi.org/10.2527/jas.2007-0305
- Meyerhoeffer, D. C., et al. (1985). Reproductive criteria of beef bulls during and after exposure to increased ambient temperature. J. Anim. Sci. 60:352-357. https://doi.org/10.2527/jas1985.602352x
- Hahn, G. L., & Nienaber, J. A. (1993). Characterizing stress in feedlot cattle. USMARC Beef Research Progress Report No. 4:146-148. https://digitalcommons.unl.edu/hruskareports/120
- Thornton, P., Nelson, G., Mayberry, D., & Herrero, M. (2022). Impacts of heat stress on global cattle production during the 21st century. Lancet Planet. Health 6:e192-e201. https://doi.org/10.1016/S2542-5196(22)00002-X
- Key, N., & Sneeringer, S. (2014). Greater heat stress from climate change could lower dairy productivity. USDA ERS Amber Waves, November 2014. https://www.ers.usda.gov/amber-waves/2014/november/greater-heat-stress-from-climate-change-could-lower-dairy-productivity
- Deng, X., Barnett, B. J., Vedenov, D. V., & West, J. W. (2007). Hedging dairy production losses using weather-based index insurance. Agric. Econ. 36:271-280. https://doi.org/10.1111/j.1574-0862.2007.00204.x
- Kansas 2022 deaths: AP via PBS NewsHour, https://www.pbs.org/newshour/economy/heat-stress-blamed-for-thousands-of-cattle-deaths-in-kansas ; KCUR, 2022-07-28, https://www.kcur.org/news/2022-07-28/the-heat-killed-so-many-kansas-cattle-in-june-that-the-only-place-to-take-carcasses-was-a-landfill

**Forage**
- Naumann, H. Tall Fescue Toxicosis. University of Missouri Extension G4669 (rev. April 2026). https://extension.missouri.edu/publications/g4669
- USDA NRCS Illinois. Grazing Manual fact sheet: Tall Fescue. https://www.nrcs.usda.gov/sites/default/files/2022-09/TallFescue.pdf
- Newman, Y., Vendramini, J., & Blount, A. Bahiagrass (Paspalum notatum): Overview and Management. UF/IFAS EDIS SS-AGR-332. https://journals.flvc.org/edis/article/download/118607/116535/173967
- Moyo, M., & Nsahlai, I. (2021). Consequences of increases in ambient temperature and effect of climate type on digestibility of forages by ruminants. Animals 11:172. https://doi.org/10.3390/ani11010172
- Lauenroth, W. K., & Sala, O. E. (1992). Long-term forage production of North American shortgrass steppe. Ecol. Appl. 2:397-403. https://doi.org/10.2307/1941874
- Baral, R., et al. (2022). Agronomy 12:2190. https://doi.org/10.3390/agronomy12092190
- Rodziewicz, D., Dice, J., & Cowley, C. (2023). Drought and cattle: implications for ranchers. Federal Reserve Bank of Kansas City RWP 23-06. https://doi.org/10.18651/RWP2023-06
- Texas A&M AgriLife Extension, 2011 drought losses, via TWRI Drought newsletter, March 2012. https://twri.tamu.edu/wp-content/uploads/2024/04/2012-03-21.pdf
- Oregon State University Tall Fescue Online Monograph (snippet only). https://forages.oregonstate.edu/tallfescuemonograph

**Programs**
- USDA FSA (2023-08-25). USDA updates Livestock Disaster Payment Rate to assist producers hard-hit by heat and humidity. https://www.fsa.usda.gov/news-room/news-releases/2023/usda-updates-livestock-disaster-payment-rate-to-assist-producers-hard-hit-by-heat-and-humidity
- USDA FSA. Livestock Indemnity Program. https://www.fsa.usda.gov/resources/programs/livestock-indemnity-program-lip
