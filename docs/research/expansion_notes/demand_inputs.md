# Demand inputs for a loss-based weather-hedge demand estimate (segments A-G)

Purpose: market-size, financial and willingness-to-pay parameters that turn the empirical rain-loss estimates (OpenTable reservations, MLB attendance, done by other agents) into a demand number per segment. Every parameter has a low / central / high value. Machine-readable copy: [`data/processed/demand_inputs.csv`](../../../data/processed/demand_inputs.csv) (301 rows: segment, parameter, low, central, high, unit, source, status). Researched 2026-11-19.

Status labels: **verified** means the number came from the primary source (an API or the repo's own data, or the source's own text as retrieved this pass). **secondary** means a press or aggregator report of a primary figure. **unverified** means the number appeared only in search summaries or practitioner blogs, or came from memory. **assumption** is a labeled team assumption with a range.

Method notes:
- The Census CBP API (`api.census.gov/data/2022/cbp`) now redirects keyless requests to `missing_key.html`; checked 2026-11-19 with HTTP 302. Metro counts therefore come from the keyless **BLS QCEW open-data API** (2024 annual averages, private ownership, MSA level). That is a comparable and newer establishment census; QCEW counts run about 3% above CBP-style counts.
- Where BLS suppresses metro payroll for disclosure, payroll is imputed as establishments times the US payroll per establishment. Those cells are marked `*`.

## A. Restaurants and bars (NAICS 722511 full-service, 722410 drinking places)

### Takeaway
The 23 Kalshi rain metros hold about 106k full-service restaurants (40% of the US 264k) with about $214B of sales, plus about 14k bars with about $16B. The typical restaurant earns a 2.8-4% pre-tax margin and holds about 16 days of cash. A rained-out weekend can therefore wipe out a month's profit, but monthly sales move only about 1 point between wet and dry months.

### Cited Findings

National parameters

| Parameter | Low | Central | High | Unit | Source (year) | Status |
|---|---|---|---|---|---|---|
| Full-service establishments (722511) | 257,282 | 264,208 | 264,208 | estabs | [BLS QCEW API](https://data.bls.gov/cew/data/api/2024/a/industry/722511.csv) (2024); low from a CBP-style aggregator, [Mewayz](https://data.mewayz.com/industry/722511) (year unstated) | verified |
| Full-service payroll | 163.6 | 163.6 | 163.6 | $bn/yr | QCEW (2024) | verified |
| Full-service sales | 424 | 475 | 500 | $bn/yr | [BLS sectoral output, FRED IPUTN722511T300000000](https://fred.stlouisfed.org/series/IPUTN722511T300000000) (2023); low from [Vertical IQ](https://verticaliq.com/product/full-service-restaurants) (undated) | secondary |
| Sales per full-service establishment | 1.0 | 1.80 | 2.3 | $M/yr | 475.1bn ÷ 264,208; low and high are assumptions (independents vs chains) | assumption |
| Payroll / sales, full service | 0.30 | 0.344 | 0.40 | ratio | QCEW payroll ÷ BLS output. Consistent with NRA's median labor cost of 34.2% of sales ([NRA](https://restaurant.org/research-and-media/research/restaurant-economic-insights/analysis-commentary/elevated-labor-costs-had-a-significant-impact-on-restaurant-profitability-in-2024/), 2025) | secondary |
| Drinking-place establishments (722410) | 42,624 | 42,624 | 42,624 | estabs | [QCEW API](https://data.bls.gov/cew/data/api/2024/a/industry/722410.csv) (2024) | verified |
| Drinking-place payroll | 11.0 | 11.0 | 11.0 | $bn/yr | QCEW (2024) | verified |
| Drinking-place sales | 27.5 | 36.7 | 44 | $bn/yr | payroll ÷ an assumed payroll/sales ratio of 0.25-0.40. No 2022 Economic Census figure was retrievable without an API key | assumption |
| Full-service median pre-tax margin | 0.028 | 0.04 | 0.06 | share of sales | NRA Operations Data Abstract: 2.8% for FY2024, 4.0% in 2019 ([NRA](https://restaurant.org/research-and-media/research/restaurant-economic-insights/analysis-commentary/elevated-labor-costs-had-a-significant-impact-on-restaurant-profitability-in-2024/), 2025). High is the vendor range of 3-6% | verified |
| Limited-service median pre-tax margin | 0.04 | 0.04 | 0.06 | share | Same NRA source (2024 4.0%, 2019 6.0%) | verified |
| Fixed-cost share of sales (rent, salaried staff, utilities, insurance, depreciation) | 0.15 | 0.20 | 0.30 | share | Inference; no direct survey retrieved | assumption |
| Contribution margin lost per $ of lost sales | 0.55 | 0.65 | 0.70 | share | 1 minus food and beverage cost (about 30-35%) minus flexible hourly labor | assumption |
| Median small-restaurant cash buffer | 12 | 16 | 27 | days of outflows | [JPMC Institute "Cash is King"](https://www.jpmorganchase.com/institute/all-topics/business-growth-and-entrepreneurship/report-cash-flows-balances-and-buffer-days) (2016): restaurants 16, all small businesses 27. Low is the Orlando all-SMB median of 12.8 ([JPMC metro report](https://www.jpmorganchase.com/institute/all-topics/business-growth-and-entrepreneurship/small-business-cash-liquidity-in-25-metro-areas), 2025 data; the national median there is 17.6) | verified |
| Full-service operators with outdoor dining, peak season | 0.57 | 0.72 | 0.72 | share | [NRA](https://www.restaurant.org/articles/news/customer-demand-for-outdoor-dining-rose) (Sept 2021): 72% full service, 57% limited service, 65% all | verified |
| Operators with outdoor dining in winter (Feb) | 0.30 | 0.40 | 0.49 | share | Same NRA page: 40% Feb, 49% Nov (year probably 2020-21) | secondary |
| Patio operators with >40% of daily sales outdoors | 0.20 | 0.35 | 0.35 | share | Same NRA page (2021) | verified |
| Patio share of in-season sales (patio operators) | 0.10 | 0.20 | 0.40 | share | Inference from the line above | assumption |
| Diners choosing a restaurant for outdoor seating | 0.41 | 0.41 | 0.70 | share of diners | [Toast survey](https://pos.toasttab.com/blog/data/restaurant-outdoor-seating-insights) (undated): 41% choose for it; 70% will wait longer for it | secondary |
| Monthly comp-sales gap, rainy vs dry month | 0.008 | 0.012 | 0.016 | share of sales | APT, June/July 2015 ([QSR Web](https://www.qsrweb.com/news/rain-impacts-june-restaurant-sales/)) | secondary |

Metro table (QCEW 2024, private sector; sales = payroll ÷ 0.344 for full service and ÷ 0.30 for bars; `*` = payroll imputed)

| Metro (Kalshi rain city) | Full-service estabs | Full-service payroll $M | Full-service sales $M (central) | Bar estabs | Bar payroll $M | Bar sales $M (central) |
|---|---|---|---|---|---|---|
| New York | 19,470 | 12,706 | 36,936 | 2,592 | 982 | 3,272 |
| Chicago | 7,256 | 4,492* | 13,060 | 1,554 | 402* | 1,338 |
| Los Angeles | 10,896 | 8,583 | 24,951 | 879 | 357 | 1,189 |
| Miami | 6,230 | 4,979 | 14,474 | 447 | 289 | 963 |
| Houston | 5,050 | 3,127* | 9,089 | 677 | 175* | 583 |
| Dallas-Fort Worth | 5,730 | 4,349 | 12,642 | 515 | 133* | 443 |
| Austin | 1,676 | 1,038* | 3,017 | 387 | 174 | 581 |
| San Antonio | 1,770 | 1,304 | 3,791 | 392 | 101* | 338 |
| Atlanta | 5,349 | 3,312* | 9,627 | 360 | 93* | 310 |
| Boston | 4,278 | 3,740 | 10,872 | 230 | 106 | 355 |
| Philadelphia | 4,318 | 2,674* | 7,772 | 777 | 174 | 581 |
| Washington DC | 4,959 | 3,070* | 8,926 | 319 | 82* | 275 |
| Denver | 2,292 | 1,419* | 4,125 | 424 | 110* | 365 |
| Seattle | 3,935 | 2,597 | 7,550 | 480 | 194 | 647 |
| Phoenix | 2,838 | 2,744 | 7,976 | 378 | 168 | 560 |
| Las Vegas | 1,805 | 2,136 | 6,208 | 280 | 256 | 852 |
| New Orleans | 1,292 | 711 | 2,067 | 485 | 125* | 418 |
| Minneapolis | 2,481 | 1,536* | 4,465 | 397 | 103* | 342 |
| Detroit | 3,140 | 1,680 | 4,883 | 538 | 196 | 652 |
| San Francisco | 4,939 | 3,321 | 9,654 | 666 | 223 | 742 |
| Oklahoma City | 1,227 | 760* | 2,208 | 136 | 35* | 117 |
| St. Louis | 1,980 | 1,226* | 3,564 | 560 | 145* | 482 |
| Tampa | 2,760 | 1,979 | 5,752 | 461 | 158 | 527 |
| **Total (23 metros)** | **105,671** | **73,482** | **213,609** | **13,934** | **4,780** | **15,932** |

Source: [BLS QCEW open-data API](https://data.bls.gov/cew/data/api/2024/a/industry/722511.csv), MSA codes C####. Sales low and high bracket central at roughly -14% / +15% (full service) and -25% / +20% (bars) via the payroll ratios in the CSV. Pittsburgh is a Kalshi rain station but was not found under the MSA code tried. Kalshi rain stations come from `data/processed/kalshi_weather_series_catalog.csv`, which has 38 monthly series.

### Inferences
- Exposed sales: a metro's patio-exposed in-season sales ≈ full-service sales × 0.72 (have patios) × 0.20 (patio share of sales). For DFW that is about $1.8B a year; in Nov-Feb it falls to about 0.40/0.72 of that.
- Hedgeable loss for one firm ≈ exposed sales × rain-day loss share (from the OpenTable work) × 0.65 contribution margin. Against a 2.8-4% margin and 16 days of cash, a 2-3 weekend washout in a month is a severe liquidity event for a patio-heavy independent, but small in annual terms.
- Metro payroll per establishment is far above the national average in Las Vegas ($1.18M) and Boston ($0.87M), versus $0.62M nationally. Using national sales per establishment would understate those metros.

### Gaps
- No 2022 Economic Census sales-per-establishment figure was retrieved, because the Census API needs a key. The BLS output proxy (2023) is a sales-like output measure, not Census receipts.
- No post-2021 operator-side survey of patio prevalence was found. Toast and OpenTable publish diner-side preferences only.
- No direct survey of restaurant fixed-cost share was found.

## B. Outdoor venues and events

### Takeaway
The large wet-side venues are few and concentrated: 30 MLB teams (71.4M fans), 120 MiLB teams (30.4M fans), about 1,300 amusement and theme park establishments (about 300M North American visits, $32B spending), about 14,000 golf facilities (about 540M rounds, about $32B on-course revenue) and roughly 500-1,100 music festivals.

### Cited Findings

| Parameter | Low | Central | High | Unit | Source (year) | Status |
|---|---|---|---|---|---|---|
| MLB teams | 30 | 30 | 30 | teams | league structure | verified |
| MLB attendance | 71.4 | 71.4 | 71.4 | M fans | [Front Office Sports](https://frontofficesports.com/mlb-tops-71-4-million-fans-first-3-year-growth-run-since-2007/) (2025 season) | secondary |
| Share of MLB parks open to rain | 0.70 | 0.77 | 0.80 | share | about 7 of 30 have roofs | assumption |
| MiLB affiliated teams | 120 | 120 | 120 | teams | [MiLB.com](https://www.milb.com/news/dragons-finish-3-among-120-teams-in-attendance-in-2025) (2025) | verified |
| MiLB attendance | 30.36 | 30.36 | 30.36 | M fans | same: 30,360,682, 3,847 per game, -2.9% vs 2024 | verified |
| MiLB revenue per fan | 20 | 30 | 40 | $ | not found | assumption |
| Spectator-sports team establishments (711211) | 3,803 | 3,803 | 3,803 | estabs | [QCEW](https://data.bls.gov/cew/data/api/2024/a/industry/711211.csv) (2024); payroll $30.9bn | verified |
| US music festivals per year | 512 | 1,120 | 1,140 | festivals | Music Festival Wizard 2023 (512 US); [JamBase](https://www.jambase.com/article/music-festivals-by-the-numbers-year-in-review-2024) (1,120 in 2023, 1,140 in 2019; may include non-US) | secondary |
| Festivals over 50,000 attendance | 18 | 18 | 30 | festivals | Music Festival Wizard 2023 (via search summary); high is an assumption | secondary |
| Amusement and theme park establishments (713110) | 1,338 | 1,338 | 1,338 | estabs | [QCEW](https://data.bls.gov/cew/data/api/2024/a/industry/713110.csv) (2024); payroll $7.88bn | verified |
| North American theme park visits | 300 | 300 | 335 | M visits | [IAAPA forecast](https://iaapa.org/iaapa-announces-2024-summer-travel-trends) (2024); 335M is a third-party figure, unverified | secondary |
| North American theme park spending | 32 | 32 | 32 | $bn | same IAAPA (2024 forecast) | secondary |
| Quarterly park attendance swing blamed on rain | 0.06 | 0.10 | 0.17 | share | company filings in repo note [hospitality_venues.md](hospitality_venues.md) | secondary |
| US golf facilities | 13,900 | 14,000 | 14,000 | facilities | [NGF](https://www.ngf.org/short-game/golfs-state-of-industry-in-3-minutes-3/) (end-2025): about 16,000 courses at nearly 14,000 facilities | verified |
| Golf and country club establishments (713910) | 11,106 | 11,106 | 11,106 | estabs | [QCEW](https://data.bls.gov/cew/data/api/2024/a/industry/713910.csv) (2024); payroll $15.55bn | verified |
| Rounds played | 531 | 540 | 545 | M rounds | [NGF](https://www.ngf.org/short-game/record-rounds-again-in-2025-with-2k-fewer-courses/) (2025 record, +1.2% per Golf Datatech); 540M from a secondary summary | secondary |
| Average 18-hole public green fee | 35 | 41 | 60 | $/round | NGF via [Golf Digest](https://www.golfdigest.com/story/green-fees-may-be-surging-post-pandemic--but-not-as-much-as-you-); high is an assumption including resorts | secondary |
| Revenue per occupied tee time / green fee | 1.30 | 1.45 | 1.60 | multiple | NGF RevPOTT, about 45% above playing fees (same) | secondary |
| On-course golf revenue | 20 | 32 | 45 | $bn/yr | 540M × $41 × 1.45 | assumption |
| Rounds lost per extra inch of monthly rain | 0.015 | 0.022 | 0.03 | share | repo note [other_sectors.md](other_sectors.md) | secondary |

### Inferences
- MiLB revenue at risk per rainout ≈ 3,847 fans × $30 ≈ $115k gross per lost home date, before make-ups (an assumption-driven estimate). MLB attendance-loss estimates from the other agent should be applied to the roughly 23 open-air parks only.
- For golf, about $32B × 2.2% per inch ≈ $700M of revenue per extra inch of rain nationally, spread over 14,000 facilities. That is about $50k per facility per inch-year, which is small. Golf is a long tail, not an anchor buyer (consistent with doc 25's score of 24).

### Gaps
- No US count of outdoor amphitheaters or Live Nation outdoor venues was found.
- No MiLB rainout counts or per-game revenue were found.
- No IAAPA count of US water parks was found; water parks partly sit in NAICS 713990, not 713110.

## C. Construction (wet-day exposure)

### Takeaway
There are about 938k construction establishments with $659B of payroll, and weather costs are large in aggregate (a secondhand estimate of about $40B a year). Purchase of weather-delay cover is close to zero: the only adoption signal found says "few" US contractors buy it. Realistic buyers are the roughly 5-10% of firms large enough to carry liquidated damages.

### Cited Findings

| Parameter | Low | Central | High | Unit | Source (year) | Status |
|---|---|---|---|---|---|---|
| Construction establishments (NAICS 23) | 938,478 | 938,478 | 938,478 | estabs | [QCEW](https://data.bls.gov/cew/data/api/2024/a/industry/23.csv) (2024) | verified |
| Construction payroll | 659.4 | 659.4 | 659.4 | $bn/yr | same | verified |
| Value of construction put in place | 2,000 | 2,150 | 2,200 | $bn/yr | Census VIP; not fetched this pass (recalled about $2.1-2.2T for 2024) | unverified |
| Share of workdays lost to weather (East/South) | 0.08 | 0.14 | 0.20 | share of days | Asheville NC study, about 14% (51 days a year); [ALDOT/Auburn workday method](https://eng.auburn.edu/files/centers/hrc/aldot-930987-final1.pdf) | secondary |
| Rain-day allowance in contracts | 10 | 15 | 25 | days per 6-month project | practitioner example ([Projul](https://projul.com/blog/construction-weather-delay-management-guide/), undated) | secondary |
| Liquidated damages | 500 | 2,500 | 5,000 | $/day | practitioner blogs (Projul, [CMiC](https://cmicglobal.com/resources/article/How-to-Track-the-True-Cost-of-a-Weather-Lost-Day)), undated | unverified |
| Share of projects delayed by weather each year | 0.21 | 0.45 | 0.60 | share | conflicting vendor figures | unverified |
| US annual cost of weather delays | 20 | 40 | 80 | $bn/yr | secondhand $40B ([Cordulus blog](https://www.cordulus.com/blog/the-impact-of-weather-on-construction-costs)) | unverified |
| Deductible in a parametric delay cover | 30 | 42 | 60 | days | Descartes structure for an $18M project ([Insurance Business](https://www.insurancebusinessmag.com/au/news/breaking-news/parametric-construction-delay-cover-inside-an-18-million-structure-597584.aspx), Nov 2026) | verified |
| Contractors buying weather-delay parametric cover | 0.002 | 0.01 | 0.03 | share of firms | [ENR](https://www.enr.com/articles/48588-will-contractors-limit-weather-risk-with-indexed-insurance) says "few" have bought (date unclear); the numbers are assumptions | assumption |
| Share of construction establishments big enough to hedge (≥20 employees) | 0.05 | 0.08 | 0.10 | share | assumption | assumption |

Products in market: [Zurich NA Construction Weather Parametric](https://www.zurichna.com/industries/construction/weather-parametric) and [Descartes excess rain](https://descartesunderwriting.com/solutions/parametric-excessive-rain-insurance-na).

### Inferences
- Hedgeable universe: about 938k × 8% ≈ 75k firms. If each faces about 10 excess rain days a year beyond its allowance at $2,500/day of liquidated damages, the exposure is about $25k a year per firm, or about $1.9B in aggregate (assumption chain).
- Because take-up is about 1% today, central demand is about $20-40M of expected loss covered a year, before any price-elasticity uplift.

### Gaps
- No survey of contractor weather-delay insurance penetration was found, and no Census VIP figure was fetched this pass.

## D. Snow (cities, plow contractors, salt)

### Takeaway
City snow budgets are tens of millions of dollars and are set to 5-year averages, so heavy years blow through them. Boston was $47.1M over in FY26. Massachusetts spent $156.5M against $85M (1.84x). The private snow industry is about $17-21B a year across roughly 110k mostly one-person firms. Salt suppliers lose about 15% of segment sales in mild winters.

### Cited Findings

| Parameter | Low | Central | High | Unit | Source (year) | Status |
|---|---|---|---|---|---|---|
| Boston FY26 snow and winter supplemental | 47.1 | 47.1 | 47.1 | $M | [Boston supplemental appropriation](https://content.boston.gov/sites/default/files/file/2026/05/%2447120292%20Snow%20Winter.pdf) (2026) | verified |
| Boston projected deficit driven by snow | 48.4 | 48.4 | 48.4 | $M | [GBH](https://www.wgbh.org/news/politics/2026-03-30/boston-projects-48m-budget-deficit-next-fiscal-year-driven-by-snow-removal-costs) (Mar 2026) | verified |
| Massachusetts FY26 snow budget / spend | 85 / 156.5 | | | $M | [NBC Boston](https://www.nbcboston.com/news/local/massachusetts-winter-cleanup-tab-tops-156m-could-surpass-2015s-snowmaggedon/3914139/?amp=1) (2026) | verified |
| Baltimore 2026 snow cost | 80 | 88 | 88 | $M | [Fox Baltimore](https://foxbaltimore.com/news/local/baltimore-spent-88m-on-snow-removal-in-2026-heres-what-the-city-plans-to-change) (2026) | secondary |
| Minneapolis snow budget | 11 | 12 | 13 | $M/yr | [Smart Cities Dive](https://smartcitiesdive.com/news/budgeting-for-winter-weather-in-an-era-of-climate-uncertainty/512243) ($11M, older) vs an aggregator ($13M) | secondary |
| Philadelphia FY26 snow operations budget (probable) | 4.1 | 4.1 | 4.1 | $M | [Inquirer](https://www.inquirer.com/weather/city-spending-snow-removal-workforce-20260218.html) (Feb 2026); the snippet did not name the city, and it mentions a $50M general-fund transfer | unverified |
| NYC snow budget | 60 | 100 | 150 | $M/yr | Charter rule: budget = prior 5-year average ([NYC Comptroller](https://comptroller.nyc.gov/reports/the-slippery-cost-slope-of-ice-and-snow-removal-in-new-york-city), 2015); dollar range is an assumption | assumption |
| Chicago snow budget | 15 | 25 | 40 | $M/yr | not found | assumption |
| Denver snow budget | 5 | 10 | 15 | $M/yr | not found (2026 budget kept snow removal uncut) | assumption |
| Heavy-year overrun | 0.5 | 1.0 | 2.0 | multiple of budget | MA 1.84x; Barrie about 1.8x; Boston +$47M (repo note [ski_snow.md](ski_snow.md)) | secondary |
| Private snow and ice removal revenue | 16.8 | 18 | 20.8 | $bn/yr | [SIMA 2017 via Buildings.com](https://www.buildings.com/articles/28533/private-snow-removal-168-billion-industry); $20.8B from a secondary blog citing SIMA 2024/25 | secondary |
| Private snow workers | 110,000 | 110,000 | 180,000 | workers | SIMA 2017 (88,000 sole practitioners); high is secondary | secondary |
| Snow removal businesses | 88,000 | 110,000 | 116,000 | firms | SIMA; [IBISWorld](https://www.ibisworld.com/united-states/industry/snowplowing-services/5400/) about 116k (older) | secondary |
| Commercial contractors able to hedge (>$1M revenue) | 3,000 | 6,000 | 10,000 | firms | assumption | assumption |
| Landscaping establishments (561730; many plow) | 123,133 | 123,133 | 123,133 | estabs | [QCEW](https://data.bls.gov/cew/data/api/2024/a/industry/561730.csv) (2024) | verified |
| Salt sales drop in a mild winter | 0.15 | 0.15 | 0.15 | share | [Compass Minerals 10-K FY2015](https://www.sec.gov/Archives/edgar/data/0001227654/000122765416000082/cmp-20151231x10k.htm) (salt $849.0M) | verified |

### Inferences
- City demand: a high-snow call sized to the overrun. Using Boston's $47M overrun in a roughly 1-in-10 heavy year, the expected loss is about $4-5M a year per large city. Across about 10 Kalshi snow cities that gives about $20-60M of expected loss, if cities can buy at all (public procurement; doc 25 scores the legal path 2).
- Contractor and salt demand (low-snow put): the hedgeable universe is a few thousand firms, not 110k.

### Gaps
- No adopted FY26 snow line was found for NYC, Chicago, Denver, Detroit, DC or Minneapolis. These are the largest assumption cells and should be pulled from budget books.
- SIMA's split of per-push versus seasonal contracts was not retrieved.

## E. Farmers and ranchers (dry side), Companion states

### Takeaway
In the nine Companion states, PRF covered 112M acres in 2025 with $677M of total premium ($318M paid by producers) on 45,402 policies. That is 38% of US PRF acres (298M) and 46% of premium ($1.46B). Producers got back $1.97 per producer-paid dollar over 2015-2025, so any unsubsidized product starts from a heavily subsidized benchmark.

### Cited Findings
PRF by state (`data/processed/prf_summary_of_business_state.csv`, RMA Summary of Business; 2025, the latest complete year; the CSV gives 2023-2025 min/max as low/high) — verified

| State | Insured acres (M) | Total premium ($M) | Producer-paid premium ($M) | Policies earning premium |
|---|---|---|---|---|
| TX | 38.88 | 253.4 | 116.3 | 15,058 |
| NM | 27.88 | 97.2 | 45.0 | 1,745 |
| CO | 12.48 | 44.4 | 21.2 | 1,715 |
| NE | 9.34 | 59.8 | 28.5 | 5,849 |
| SD | 8.10 | 67.2 | 32.4 | 5,956 |
| KS | 5.88 | 67.9 | 31.9 | 6,289 |
| ND | 5.21 | 39.7 | 19.3 | 3,983 |
| OK | 3.67 | 34.3 | 16.3 | 2,563 |
| MO | 0.64 | 13.5 | 6.6 | 2,244 |
| **9-state total** | **112.07** (2023: 102.1) | **677.4** (2023: 577.7) | **317.6** (2023: 270.2) | **45,402** (2023: 39,446) |

| Parameter | Low | Central | High | Unit | Source (year) | Status |
|---|---|---|---|---|---|---|
| US PRF acres | 273.7 | 298.3 | 298.3 | M acres | repo CSV (2024 / 2025) | verified |
| US PRF total premium | 1,308 | 1,458 | 1,458 | $M | repo CSV (2024 / 2025) | verified |
| 9-state PRF loss ratio | 0.38 | 0.91 | 1.34 | indemnity / total premium | repo CSV, 2015-2025 (central pooled; 2015 low, 2022 high) | verified |
| 9-state producer return per producer-paid $ | 1.0 | 1.97 | 2.9 | $ | repo CSV pooled 2015-2025 (range is an assumption) | verified |
| PRF subsidy share | 0.51 | 0.53 | 0.59 | share | repo CSV pooled; range by coverage level | verified |
| US farms with beef cows | 622,000 | 622,000 | 622,000 | farms | 2022 Census of Agriculture (29.2M cows, average 47) via [Iowa Beef Center](https://iowabeefcenter.org/gb/2024/June2024Census.html) | secondary |
| Feedlots ≥1,000 head | 2,105 | 2,105 | 2,105 | lots | NASS Jan 1 2025 via [Drovers](https://www.drovers.com/markets/market-reports/review-feedlot-structure-and-2024-marketings) (87.2% of 2024 marketings) | secondary |
| Feedlots <1,000 head | 24,000 | 24,000 | 24,000 | lots | same (12.8% of marketings) | secondary |
| Cattle on feed in ≥1,000-head lots | 11.1 | 11.7 | 11.7 | M head | [DTN](https://www.dtnpf.com/agriculture/web/ag/livestock/article/2025/12/22/dec-1-cattle-feed-2-year-ago-11) (Dec 1 2025); low is Sep 1 2025 | secondary |
| Feedlot gain lost in mud | 0.14 | 0.20 | 0.25 | share of daily gain | [K-State MF2673](https://bookstore.ksre.ksu.edu/download/how-feeding-site-mud-and-temperature-affect-animal-performance_MF2673) (old trials) | secondary |
| Farm Credit System loans outstanding | 401.2 | 429.3 | 429.3 | $bn | [FCA YBS report](https://www.fca.gov/newsroom/pr_detail/fca-board-receives-2025-annual-report-on-the-farm-credit-systems-young-beginning-and-small-farmers-mission-performance) (YE2025; low YE2024) | secondary |
| Farm Credit System number of loans | 1,059,214 | 1,122,979 | 1,122,979 | loans | same | secondary |
| Farm Credit associations | 50 | 55 | 60 | associations | not found (FCA examined 50 in 2025) | assumption |
| Share of a 9-state lender book exposed to rangeland drought | 0.10 | 0.20 | 0.30 | share | assumption | assumption |

### Inferences
- The retail Companion's ceiling is the producer-paid premium for the Nov-Feb gap months, a slice of the $318M a year. The wholesale route (doc 25 rank 1) scales instead with lender exposure: roughly 20% of a Plains Farm Credit book that is itself a slice of $429B.
- Feedlots: about 2,105 large lots in the Plains are the only farm-side wet-loser in Companion months.

### Gaps
- No state-level count of beef-cow operations or feedlot capacity was found (Census of Ag Table 15/16; the NASS PDF returned 404). No Texas-specific Farm Credit loan volume was pulled; Capital Farm Credit and Texas Farm Credit quarterly reports exist but were not read.

## F. Willingness to pay and take-up

### Takeaway
Demand collapses as the price multiple rises. About 40-50% buy index insurance at fair price, under 20% at about 1.4-1.5x fair (Ghana), and the price elasticity is about -0.66 to -0.88 (India). US farmers' median WTP is at or below the fair premium net of a 50%+ subsidy. Only about 10% of weather-sensitive US firms have ever hedged, and 29-46% of small businesses carry business-interruption cover. Timing and bundling beat price: deferring the premium to harvest raised take-up from 5% to 72%.

### Cited Findings

| Parameter | Low | Central | High | Unit | Source (year) | Status |
|---|---|---|---|---|---|---|
| Index-insurance price elasticity (India) | -0.88 | -0.77 | -0.66 | elasticity | Cole et al. 2013 AEJ Applied ([EconPapers](https://econpapers.repec.org/RePEc:aea:aejapp:v:5:y:2013:i:1:p:104-35)); figure carried from repo note [uninsured_farmers.md](uninsured_farmers.md); full text returned 403 this pass | unverified |
| Take-up gain from a liquidity grant of one premium | 1.0 | 1.4 | 1.4 | relative | Cole et al. 2013 (repo note) | secondary |
| Take-up gain from a trusted endorser | 0.36 | 0.36 | 0.36 | relative | [World Bank abstract](https://openknowledge.worldbank.org/entities/publication/60c08adb-cb0c-5880-96fe-891d2c744aaf/full) | verified |
| Take-up at fair price (Ghana) | 0.40 | 0.45 | 0.50 | share | Karlan et al. 2014 QJE, [J-PAL](https://www.povertyactionlab.org/evaluation/examining-underinvestment-agriculture-returns-capital-and-insurance-among-farmers-ghana) | verified |
| Take-up at market price, about 1.4-1.5x fair (Ghana) | 0.10 | 0.15 | 0.20 | share | same (<20%) | verified |
| Take-up after a marketing visit (India) | 0.35 | 0.40 | 0.45 | share | Mobarak & Rosenzweig, [J-PAL](https://www.povertyactionlab.org/print/pdf/node/1721); demand falls with basis risk | secondary |
| Take-up, premium deferred to harvest / upfront (Kenya) | 0.72 / 0.05 | | | share | [Casaburi & Willis 2018 AER](https://www.aeaweb.org/doi/10.1257/aer.20171526) | verified |
| US crop insurance median WTP / fair premium | 0.4 | 0.5 | 1.0 | multiple | Feng, Du & Hennessy (2020; AJAE 2017 [companion paper](https://econpapers.repec.org/RePEc:oup:ajagec:v:99:y:2017:i:3:p:732-756.)): median WTP ≤ fair premium net of a ≥50% subsidy | secondary |
| Coverage-demand elasticity, 75% level, Southern Plains | -0.9 | -0.654 | -0.3 | elasticity | [Yi, Richardson & Bryant AAEA 2016](https://ideas.repec.org/p/ags/aaea16/236249.html) (range is an assumption) | secondary |
| Fall in high-coverage purchase if subsidies were decoupled | 0.36 | 0.36 | 0.36 | relative | [Babcock & Hart 2005](https://econpapers.repec.org/RePEc:ias:cpaper:05-wp393) | verified |
| Small businesses with business-interruption insurance | 0.29 | 0.35 | 0.46 | share | Nationwide 2015 (66% lack; [Insurance Journal](https://www.insurancejournal.com/news/national/2015/09/02/380367.htm)), 2017 (71% lack), NAIC 2007 (35% have) | secondary |
| Weather-sensitive firms that used weather derivatives | 0.05 | 0.10 | 0.15 | share | CME/Storm Exchange 2008, 205 firms ([Artemis](https://www.artemis.bm/news/cme-group-and-storm-exchange-weather-risk-study-released/)); sponsor bias | verified |
| Weather-sensitive firms that quantified exposure | 0.42 | 0.42 | 0.42 | share | same | verified |
| Sensible Weather attach rate | 0.05 | 0.12 | 0.50 | share of bookings | 12% at one partner (Yonder); 50% is a CEO claim for early channels ([TechCrunch](https://techcrunch.com/2022/05/05/it-is-like-raaaaaaaaaaain-on-your-wedding-day/), 2022) | secondary |
| Sensible guarantee price | 0.08 | 0.10 | 0.12 | share of booking | repo note [hospitality_venues.md](hospitality_venues.md) | secondary |
| Sensible guarantees sold | 1.0 | 1.0 | 1.0 | M | [Business Wire](https://www.businesswire.com/news/home/20250825060512/en) (2025) | secondary |
| Weather-promotion premium | 0.015 | 0.03 | 0.055 | share of promoted sales | [CNN Money](https://money.cnn.com/2010/12/30/smallbusiness/snow_jewelry_full_refunds/index.htm) (2010; jeweler 2.2%) | secondary |
| Weather-promotion payout probability | 0.01 | 0.03 | 0.05 | probability | same (1-5%; 5 of 100 paid) | secondary |
| Implied promotion price multiple | 1.0 | 1.5 | 3.0 | premium / expected loss | inference from the two rows above | assumption |
| Event rain cover rate on line (one example) | 0.084 | 0.084 | 0.084 | premium / limit | 2008 event: $63k for a $750k limit (search summary only) | unverified |
| Lloyd's attritional loss ratio, all classes | 0.47 | 0.47 | 0.48 | ratio | [Lloyd's FY2024](https://www.lloyds.com/insights/media-centre/press-releases/lloyds-reports-preliminary-full-year-results-2024) (47.1%; 2023 48.3%) | verified |
| Price multiple buyers accept on parametric or event lines | 1.3 | 1.6 | 2.5 | premium / expected loss | anchored on Lloyd's about 47% attritional and promotion pricing | assumption |
| Kalshi cost vs subsidized PRF | 1.8 | 1.8 | 1.8 | multiple | repo docs 08-09 | verified |

### Inferences
- **Conversion recipe (proposed).** Demand$ = N_firms × P(hedge | segment) × expected covered loss per firm × price multiple m. Set P(hedge) = t₀ × (m / m₀)^ε with ε ≈ -0.77.
  - Anchors: t₀ ≈ 0.45 at m₀ = 1 for bundled or embedded offers (Ghana fair price; Sensible 12%+ attach). For standalone SMB or corporate offers, use t₀ ≈ 0.10 (the CME 10% hedgers) to 0.35 (business-interruption penetration).
  - At Kalshi-plus-platform loads (m ≈ 1.5-1.8), standalone take-up falls to roughly 6-7% of firms. Embedded take-up falls to about 28-33%.
  - Deferred payment or a lender bundle can multiply take-up several-fold (5% to 72%), which matters more than price.
- Ghana's drop from 45% to below 20% for a 1.4-1.5x price rise implies an arc elasticity of about -2.5 to -3 (ln(0.15-0.18 / 0.45) ÷ ln(1.45)). That is much steeper than India's figure. Use -0.77 as central and -2.5 as a high-sensitivity case.

### Gaps
- No event-cancellation loss ratio or premium pool was found (Lockton's contingency report gives only qualitative "stable" rates). No take-up by event size was found. Cole et al.'s elasticity needs checking against the paper text.

## G. Kalshi weather liquidity (scale comparison)

### Takeaway
Kalshi's whole weather category is pacing about $1.1B a year. But resting depth across all 36 monthly rain series was only $84k YES / $160k NO once rewards ended (Nov 2). It was $1.05M / $3.13M with rewards on (Oct 29). A single ranch Companion needs about 21k contracts against about 3k near fair value. Exchange depth, not demand, binds first.

### Cited Findings

| Parameter | Oct 29 2026 (rewards on) | Nov 2 2026 (rewards off) | Unit | Source | Status |
|---|---|---|---|---|---|
| Total YES ask depth, all rain markets | 1,053,904 | 83,532 | $ | `data/processed/kalshi_rain_orderbook_summary_{20261029,20261102}.csv` | verified |
| Total NO ask depth | 3,133,381 | 159,662 | $ | same | verified |
| Median YES ask depth per series (36 series) | 27,922 | 1,083 | $ | same (353 and 269 markets) | verified |
| Median spread | 0.12 | 0.12 | $ per $1 contract | same | verified |

| Parameter | Low | Central | High | Unit | Source | Status |
|---|---|---|---|---|---|---|
| Depth multiple for 90% of uncapped Companion fit | 5 | 5 | 25 | × saved depth | [doc 22](../../analysis/22_making_it_better.md) table A (median Companion HE 0.18 at 1x, 0.50 at 5x, 0.66 at 10x, 0.68 at 25x) | verified |
| Contracts needed, DFW hay farm | 21,472 | 21,472 | 21,472 | contracts | doc 22 (depth near fair value 2,986) | verified |
| Kalshi weather/climate volume pace | 0.564 | 1.1 | 1.1 | $bn/yr | [Markets Media](https://marketsmedia.com/kalshi-partners-with-the-weather-company) (Aug 28 2026; +500% YoY); low is $564M year to date through July (WSJ via search, secondary) | verified |

### Inferences
- Total depth sums all price levels, including 1-cent orders at far strikes. Near-fair depth is smaller still (doc 22).
- Even the small segment totals above, such as about $20-60M of city snow expected loss or about $318M of producer-paid PRF, are 100-1,000x the post-rewards resting rain depth. Any demand estimate should report a liquidity-capped figure alongside the uncapped one, or route through an insurer or MGA book as doc 25 recommends.

### Gaps
- The category's annual volume is not broken out into rain vs temperature vs snow, and no post-rewards depth snapshot of the snow markets is in the repo.
