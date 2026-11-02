# Representative farm exposures for the PRF study sites

**Proposal cell:** Week 1 / Jack (R8)  |  **Status:** DRAFT  |  **Last updated:** 2026-10-29

This document defines the 11 "typical" farms in `data/scenarios/farms.yaml` and records the county
data behind them: who farms in each study county, what they grow, how much land a commercial
operation uses, what PRF buyers there actually choose, and what the 2026 PRF policy terms are.
Later milestones use these farms as the exposures that a Kalshi rain-contract portfolio tries to
replicate.

Jargon used throughout:

- **PRF** (Pasture, Rangeland, Forage) is USDA's rainfall-index insurance for grazing land and hay.
  It pays when rain in a 0.25-degree **grid** cell during a two-month **index interval** falls
  below a trigger, no matter what happened on the farm itself.
- **Intended use** is either **grazing** (livestock eat the grass in place) or **haying** (the grass
  is cut, dried and baled).
- **County base value** ($/acre) is RMA's dollar value of one acre of forage in that county for that
  intended use. **Productivity factor** (PF, 60-150%) scales it up or down for a better or worse
  field. **Coverage level** (70-90%) sets the trigger: the policy pays when the grid's rain index
  falls below that percent of normal.
- **Policy protection** ($) = insured acres x county base value x PF x coverage level. The farmer
  then splits it across intervals using a **percent of value** for each selected interval.
- **Liability** in RMA reports means total policy protection. **Loss ratio** = indemnity (claim
  payments) / total premium. **Subsidy** is the share of premium the government pays (51-59% for PRF).
- **AU / AUM**: an animal unit is a 1,000 lb beef cow; an animal-unit month is the forage one AU eats
  in a month.
- **Cash rent** is what a rancher pays per acre per year to graze someone else's pasture.

## Key findings

- **2026 county base values (RMA Actuarial Data Master, ADM, Price table field 34)** for grazing range
  from $11.50/acre (Torrance NM) to $50.30 (Hardee FL); for non-irrigated haying from $113 (Atascosa
  TX) to $333 (Hardee FL). Haying is worth 4.4 to 17.4 times grazing per acre. The same values appear
  in the 2025 ADM and in RMA's 2027 Decision Support Tool, so they have not changed for three crop years.
- **Allocation rules (26-RI-PRF Crop Provisions + ADM 2026):** at least two intervals; at least 10% of
  value in each; at most 50% per interval in Texas, New Mexico and Florida counties and 60% in
  Oklahoma, Missouri, Colorado and Illinois; no month may appear in two selected intervals; shares sum
  to 100%; coverage 70-90% (5-point steps); PF 60-150% (1-point steps). For crop year 2027 the
  Decision Support Tool caps Jan-Feb at 25% in every study county. All 11 farms pass these checks
  (`python scripts/r8_pull_county_data.py --steps validate`).
- **Buyers pick a productivity factor at or near the 150% maximum.** Dividing 2026 county liability by acres x base
  value x coverage gives an average PF of 1.44-1.50 in 11 of the 14 PRF-county/use cells; only Grady OK
  (1.28 grazing, 1.39 haying) and Parker TX grazing (1.36) are lower. 90% coverage is the most common
  level everywhere except Atascosa TX (85% on 68% of acres) and Torrance NM (split 85%/90%).
- **PRF covers a large share of grazing land in the dry and southern counties.** 2026 insured acres
  equal about 87% of Hardee FL pasture plus hay land, 41% in Torrance NM, 31% in Atascosa TX and 27%
  in Elbert CO, but only 4-7% in Grady OK, Parker TX and Dade MO.
- **Loss ratios vary widely and are highest in Hardee and Atascosa**, two of the high-participation
  counties (Torrance and Elbert, also high-participation, are near 0.7). Pooled 2015-2025 loss ratios: Hardee
  1.57 (2.50 in 2025), Atascosa 1.01, Parker 0.90, Kane 0.82, Dade 0.80, Elbert 0.70, Torrance 0.69,
  Grady 0.50. Because about 52% of premium is subsidized, farmers got back 1.0 (Grady) to 3.2 (Hardee)
  dollars per dollar of premium they paid.

  *Fact-check note (2026-11-01): Parker 0.90 and Torrance 0.69 include RMA's masked "All Other Crops"
  (commodity 9999) Rainfall Index rows (Parker 2015-2021 and 2025; Torrance 2016 and 2019-2021), which
  may contain non-PRF commodities. PRF-only rows (commodity 0088) give Parker 1.08 (2022-2025 only) and
  Torrance 0.71 (2017-2025), the figures doc 02 uses. Both versions reproduce from the RMA files.*
- **Hardee FL haying is an outlier:** 59,897 acres were insured as haying in 2026 (79% of county
  liability), 7.4 times the 8,070 acres the 2022 Census counted as harvested for hay. The haying
  base value ($333) is 6.6 times the grazing value ($50.30).
- **Actual interval choices (RMA Summary of Business, type/practice file) rarely follow the growing
  season.** Hardee buyers put about 74% of grazing liability into the dry-season intervals Jan-Feb,
  Mar-Apr and Nov-Dec. In Atascosa, Grady and Kane, grazing buyers spread value nearly evenly over
  the six non-overlapping "odd" intervals (Jan-Feb, Mar-Apr, May-Jun, Jul-Aug, Sep-Oct, Nov-Dec).
  Our farms instead follow NRCS growing-season guidance, and we say so per farm.
- **Typical commercial herd and land base differ by a factor of 25 across sites.** Census 2022
  pasture per beef cow ranges from 3.7 acres (Dade MO) to about 95 acres (Torrance NM). In five of
  seven PRF counties the median beef cow lives in a 200-499 head herd; in Parker TX it is 20-49 and
  in Atascosa TX 50-99.
- **For grazing, PRF protection per acre is well above the market value of the grass.** At the
  farms' PF and coverage, protection per acre is 1.5 times the county pasture cash rent in Atascosa,
  Grady and Dade, about 2.5-2.9 times in Parker and Elbert, 6.0 times in Hardee and 8.6 times in
  Torrance. For hay farms, protection per acre is 0.98-1.46 times expected hay revenue.
- **The 11 farms carry $696,229 of 2026 policy protection** (from $26,827 for DFW_graze to $175,950
  for ABQ_graze); 2026 total premium is $4,350-$26,933 per farm ($117,054 in all), of which the
  farmer pays 45-49%.

## Numbers table

Verification codes: **CONFIRMED** = read by us in the primary source file, API response or PDF;
**DERIVED** = computed by us from CONFIRMED inputs (formula given); **OTHER-WS** = taken from another
workstream's committed file and not re-derived by us; **UNVERIFIED** = secondary source or assumption.
Grouped rows cover every cell of the named table.

| Quantity | Value | Units | Region / period | Source (URL + page/table) | Verification |
|---|---|---|---|---|---|
| County base value, grazing / haying non-irrigated / haying irrigated / organic certified (Table D) | see Table D | $/acre | 8 study counties, crop year 2026 | RMA ADM 2026, `2026_A00810_Price_YTD.txt` inside https://pubfs-rma.fpac.usda.gov/pub/References/actuarial_data_master/2026/2026_ADM_YTD.zip, field 34 "County Base Value" (layout: ADMLayout.zip, AdmLayout.pdf pp. 64-66) | CONFIRMED |
| County base values unchanged 2025 to 2026 | identical in all cells checked | $/acre | 7 PRF counties | `data/processed/prf_actuarial_study_grids.csv` (ADM2025 and ADM2026 rows) | OTHER-WS (matches our ADM 2026 pull) |
| County base values, crop year 2027 | same as 2026 (e.g. Parker grazing 27.60) | $/acre | 7 PRF counties | PRF Decision Support Tool API `GetPricingRates`, https://public-rma.fpac.usda.gov/apps/PrfWebApi/PrfExternalPricingRates/GetPricingRates (page settings say CommodityYear 2027), queried 2026-10-29 | CONFIRMED |
| Min percent of value per interval | 10 | % | all PRF | 26-RI-PRF Crop Provisions sec. 2(a), https://www.rma.usda.gov/sites/default/files/2025-08/Rainfall-Index-Pasture-Rangeland-Forage-Crop-Provisions-26-RI-PRF.pdf p. 1; ADM 2026 Price field 51 = 0.10 | CONFIRMED |
| Max percent of value per interval | 50 (Parker, Atascosa, Torrance, Hardee); 60 (Grady, Dade, Elbert, Kane) | % | crop year 2026, every grid in each county | ADM 2026 Price field 52 "Maximum Acre Percent"; crop provisions sec. 2(a) says max is in Special Provisions; ADM Statement table A01210 codes 24931/24932 ("maximum percent of value allowed is 50% / 60%") | CONFIRMED |
| Jan-Feb max percent of value, 2027 | 25 | % | all 7 PRF counties | DST API `GetMaxAcrePercentage` responses, saved in `data/raw/r8/dst/maxpct_*.json` | CONFIRMED |
| No month in two selected intervals | rule | - | all PRF | 26-RI-PRF sec. 2(b), p. 1 | CONFIRMED |
| Minimum number of intervals | 2 ("more than one") | intervals | all PRF | 26-RI-PRF sec. 2(a); handbook FCIC-18150 (Aug 2025) para. 32C p. 12, https://www.rma.usda.gov/sites/default/files/2025-08/2026-18150-Rainfall-Index-Handbook.pdf | CONFIRMED |
| Percents must sum to 100 | 100 | % | all PRF | FCIC-18150 para. 14, p. 6 | CONFIRMED |
| Coverage level range | 70-90 | % | all PRF | 26-RI-PRF sec. 5(a)(1), p. 2; DST offers 70/75/80/85/90 | CONFIRMED |
| Productivity factor range | 60-150, 1% steps | % | PRF (not Hawaii) | FCIC-18150 para. 13, p. 5; 26-RI-PRF sec. 5(a)(2) | CONFIRMED |
| Premium subsidy, plan 13 | 59 (70-75% cov.), 55 (80-85%), 51 (90%) | % | crop year 2026 | ADM 2026 A00070 SubsidyPercent, record category 04, plan 13 | CONFIRMED |
| Cancellation / termination (sales closing) date | December 1 | date | PRF | 26-RI-PRF sec. 9, p. 2 | CONFIRMED |
| PRF commodity / plan / type / practice codes | 0088 / 13 RI / 007 grazing, 030 haying / practices 625-635 grazing, 525-535 haying non-irr., 425-435 haying irr., 465/485/565/585+ organic | codes | all | SOB `sobtpu_2025.zip`; ADM 2026 Price table; A00480 Interval table (Interval Code 625-635 = Jan-Feb to Nov-Dec, 636 = Dec-Jan) | CONFIRMED |
| SOB county PRF totals by year: policies, acres, liability, premium, subsidy, indemnity, loss ratio (Tables C1-C4) | see tables | count, acres, $ | 8 counties, 2015-2026 | RMA Summary of Business `sobcov_YYYY.zip`, https://pubfs-rma.fpac.usda.gov/pub/Web_Data_Files/Summary_of_Business/state_county_crop/ (layout PDF fields 13-28) | CONFIRMED |
| SOB rows masked as "All Other Crops" (commodity 9999, plan 13) | Parker 2015-2021, Torrance 2016, Kane 2018-2023 | years | as listed | same files | CONFIRMED |
| SOB interval, intended-use, coverage splits (Tables C5, C6, C8) | see tables | acres, $, % | 2021-2026 | RMA SOB `sobtpu_YYYY.zip` (layout `SOBTPU_External_All_Years.pdf` fields 14-27) and `sobcov_YYYY.zip` | CONFIRMED (shares DERIVED) |
| Sum of interval-row acres in sobtpu = county acres in sobcov | exact match, all counties 2024-2026 | acres | 8 counties | our check in `scripts/r8_pull_county_data.py` output | DERIVED |
| Implied average productivity factor (Table C7) | 1.28-1.50 | ratio | 2026 | liability / (acres x base value x coverage) per sobtpu row, summed by county and use | DERIVED |
| PRF penetration (2026 insured acres / (Census all pasture + hay acres)) | 86.6% Hardee ... 3.8% Grady (Table C1) | % | 2026 vs 2022 | SOB 2026 + Census 2022 | DERIVED |
| Pooled loss ratio and indemnity per farmer-paid premium 2015-2025 (Table C1) | 0.50-1.57; 1.04-3.20 | ratio | 8 counties | sum(indemnity)/sum(premium); sum(indemnity)/sum(premium - subsidy) from sobcov | DERIVED |
| Census 2022 farms, land, sizes, pasture, hay, cattle, beef cows, sales (Tables A1-A3) | see tables | count, acres, head, $ | 8 counties, 2022 | NASS Quick Stats, source CENSUS, year 2022, county level, https://quickstats.nass.usda.gov/ (queried 2026-10-29); cross-checked against county profile PDFs, e.g. https://www.nass.usda.gov/Publications/AgCensus/2022/Online_Resources/County_Profiles/Texas/cp48367.pdf p. 1 (Parker: 4,379 farms, 341,108 acres, 78 acre average, 209,968 acres pastureland) | CONFIRMED |
| Beef cows withheld (D) in Census totals | Atascosa, Grady, Torrance | - | 2022 | same | CONFIRMED |
| Pasture acres per beef cow (Table A3) | 3.7 (Dade) to 95.1 (Torrance) | acres/cow | 2022 | Census "AG LAND, PASTURELAND - ACRES" / beef cows (size-class sum where total withheld) | DERIVED |
| Hay acres per hay operation | Parker 33, Atascosa 63, Grady 178, Dade 128, Elbert 108, Torrance 98, Hardee 134, Kane 37 | acres | 2022 | Census hay acres / "HAY - OPERATIONS WITH AREA HARVESTED" | DERIVED |
| Census county hay yield | Parker 1.49 ... Hardee 3.75 (Table B) | tons/acre | 2022 | Census hay tons / hay acres | DERIVED |
| Hay price received, marketing year 2025: other hay / alfalfa (Table B) | TX 130/232, OK 88/164, MO 113/170, CO 153/164, NM 185/246, FL 120/-, IL 106/161; US 137/172 | $/ton | state, MY 2025 | NASS Quick Stats, SURVEY, HAY, PRICE RECEIVED, period MARKETING YEAR; the same values are the final 2025 MYA prices in NASS Agricultural Prices (Aug 31 2026) p.33, https://release.nass.usda.gov/reports/agpr0826.pdf (re-checked 2026-11-01; the Crop Values 2025 Summary's TX 136 / OK 90 / MO 114 are the earlier preliminary values) | CONFIRMED |
| Other-hay yield 2016-2025 (Table B) | TX 1.92, OK 1.69, MO 1.90, FL 2.72 mean (min-max in table) | tons/acre | state | NASS Quick Stats, SURVEY, "HAY, (EXCL ALFALFA) - YIELD" | CONFIRMED (means DERIVED) |
| County other-hay yield | Grady 0.9-2.15 (2010-2018), Dade 1.5-2.6 (2010-2018) | tons/acre | county | NASS Quick Stats county survey (no TX or FL county estimates in 2010-2025; OK, MO, CO county series end in 2018) | CONFIRMED |
| Pasture cash rent (Table B) | county: Parker 13.5 (2024), Atascosa 15.5, Grady 24.5, Dade 35, Elbert 6.1, Torrance 1.7 (2025), Hardee 11 (2024); state 2025: TX 7.7, OK 18, MO 38.5, CO 7.0, NM 4.1, FL 20, IL 49 | $/acre/yr | as listed | NASS Quick Stats, SURVEY, "RENT, CASH, PASTURELAND - EXPENSE, MEASURED IN $ / ACRE" | CONFIRMED |
| NRCS normal-year range production, area-weighted (Table B) | Parker 3,943; Atascosa 3,379; Grady 4,645; Elbert 1,364; Torrance 1,192; Hardee 4,832 | lb air-dry/acre/yr | county soils | NRCS SSURGO `component.rsprod_r` (and rsprod_l, rsprod_h for unfavorable/favorable years) via Soil Data Access, https://sdmdataaccess.sc.egov.usda.gov/Tabular/post.rest, weighted by map-unit acres in county (`muaoverlap`) x component percent | CONFIRMED inputs, weighting DERIVED |
| Stocking formula: AUM/acre = production x 25% harvest efficiency / 912.5 lb per AUM; AU = 1,000 lb beef cow | 25%; 912.5 lb | %, lb/AUM | NRCS Colorado ESDs | ESD R067BY002CO Loamy Plains, grazing interpretations, https://edit.sc.egov.usda.gov/services/descriptions/esd/067B/R067BY002CO.json ; also R049XB210CO | CONFIRMED |
| ESD example: Loamy Plains reference community | 1,300 lb/ac, 0.36 AUM/ac | lb/ac, AUM/ac | MLRA 67B | ESD R067BY002CO | CONFIRMED |
| ESD example: Sandy Foothill reference community | 1,600 lb/ac, 0.44 AUM/ac | lb/ac, AUM/ac | MLRA 49 | ESD R049XB210CO, https://edit.sc.egov.usda.gov/services/descriptions/esd/049X/R049XB210CO.json | CONFIRMED |
| Seasonality statements: Torrance 75% of precipitation Apr-Oct; Elbert ~75% Mar-Sep, cool-season growth starts ~Apr 1, warm-season ~May 1; Elbert plains two-thirds mid-Apr to late Sep; Hardee ~60% Jun-Sep; Atascosa peak late spring, secondary early fall, July hot and dry; Dade June ~3-4x January | as stated | % / months | ESD sites | ESD climate narratives: R042CY109NM, R049XB210CO, R067BY002CO, F155XY120FL, R083AY024TX, R116BY021MO (URLs in Sources) | CONFIRMED |
| NRCS high-management forage yield ratings (Table B2) | e.g. bahiagrass 8.05 AUM/ac Hardee, improved bermudagrass 5.41 Parker, 4.81 Grady | AUM/acre, tons/acre | county soils | SSURGO `cocropyld.nonirryield_r`, area-weighted | CONFIRMED inputs, weighting DERIVED |
| Monthly precipitation normals and CV at farm grids (Table F) | see table | inches, ratio | 1991-2020 | `data/processed/cpc_monthly_precip_grids.parquet` (CPC Unified gauge analysis) | OTHER-WS (means/CVs DERIVED) |
| Farm-point PRF grid IDs | DFW 15429, SAT 10626, OKC 18129, SGF 20845, DEN 23204, ABQ 17497, TPA 8893 | grid id | farm points | `data/processed/study_grids.csv`; our formula `row*300 + col + 1` with row = floor((lat-20)/0.25), col = floor((lon+130)/0.25) reproduces them | OTHER-WS, consistent with DERIVED |
| 2026 premium rates on farm grids | used for Table E premiums | fraction | 2026 | `data/processed/prf_actuarial_study_grids.csv` (source ADM2026) | OTHER-WS (DFW_graze total premium $5,579 vs $5,314 from DST 2027 rates; protection $26,827 vs DST $26,824) |
| Farm acres, PF, coverage, allocations, protection, premiums (Table E) | see table | acres, $, % | 2026 | `data/scenarios/farms.yaml`; protection = acres x base value x PF x coverage | DERIVED |
| Totals over 11 farms: protection / protection at PF 1.0 / total premium / farmer-paid premium | 696,229 / 477,942 / 117,054 / 55,995 | $ | 2026 | sums of Table E | DERIVED |
| Per-interval protection (e.g. ABQ_graze Aug-Sep 87,975; OKC_graze Sep-Oct 3,697) | see section 7 | $ | 2026 | protection x interval share | DERIVED |
| Protection per acre / county pasture rent (grazing farms); / expected hay revenue (hay farms) | 1.45-8.62; 0.98-1.46 | ratio | 2026 terms, 2024-2025 rents and prices | Table E columns | DERIVED |
| Grazing base value / county pasture rent | 1.17 (Atascosa) to 6.76 (Torrance) | ratio | 2026 base value, 2024-2025 rent | Tables B and D | DERIVED |
| Average insured acres per PRF policy, 2026 | Parker 603, Atascosa 1,235, Grady 658, Dade 533, Elbert 8,281, Torrance 15,230, Hardee 641, Kane 69 | acres/policy | 2026 | sobcov acres / policies earning premium | DERIVED |
| Hardee haying insured acres / Census hay acres | 59,897 / 8,070 = 7.4 | ratio | 2026 vs 2022 | sobtpu 2026; Census 2022 | DERIVED |
| Station-to-farm distance, ABQ | 53 | miles | Albuquerque Intl to Torrance farm point | `src/agri_hedge/locations.py` (project canonical sites) | CONFIRMED |
| Old Texas extension guidance example | "April-May for spring and August-September for Fall"; max 50% per interval in Texas | text | Texas, 2011 policies | Pena, J.G. (2010), AG-ECO News vol. 26 issue 25, Texas AgriLife Extension, https://agecoext.tamu.edu/wp-content/uploads/2013/08/09-02-2010.pdf p. 2 | CONFIRMED (dated) |

## Detail

### 1. How the farms were built

1. **County facts** came from the 2022 Census of Agriculture (NASS Quick Stats; the Quick Stats web
   page's own query endpoints were used, so no API key was needed) and from NASS annual surveys (hay
   prices and yields, cash rents).
2. **PRF behavior** came from the RMA Summary of Business (SOB). The `sobcov` files give policies,
   acres, liability, premium, subsidy and indemnity by coverage level. The `sobtpu` files add the
   commodity **type** (007 grazing, 030 haying) and **practice**, and for PRF the practice code is
   the index interval. Each `sobtpu` row is one interval unit; its acres are the insured acres
   times the percent of value placed in that interval, so summing rows over intervals reproduces the
   county acreage exactly. That lets us measure acres by intended use, interval choices, and an
   implied average productivity factor.
3. **Policy terms** (base values, interval limits, subsidy) came from the 2026 Actuarial Data Master.
   We read only the needed members of the 2.7 GB `2026_ADM_YTD.zip` with HTTP Range requests and kept
   the PRF rows for our 8 counties (6,699 rows). The PRF Decision Support Tool's public API gave the
   2027 values as a cross-check.
4. **Forage production** came from NRCS soil surveys (SSURGO), which store a normal-year,
   unfavorable-year and favorable-year range production for each soil component. We weighted them
   by the acres of each soil in the county. Stocking capacity uses the NRCS formula quoted in the
   Colorado Ecological Site Descriptions (ESDs): AUM/acre = lb/acre x 0.25 / 912.5.
5. **Farm size** was set from the Census herd-size distribution (the herd class that contains the
   median beef cow) and the county's realized pasture acres per beef cow, cross-checked against the
   average PRF policy size. We aimed for a typical commercial unit, not the largest ranch.
6. **Coverage level** = the county's most common level (by insured acres, 2021-2025). **PF** = the
   county's implied 2026 average, rounded to 0.05. **Intervals** follow the months when NRCS and the
   farm grid's rainfall record say rain drives forage growth, kept inside the PRF limits.
7. Everything is reproducible with `python scripts/r8_pull_county_data.py` (steps `sob adm dst nass
   ssurgo validate`). Raw downloads (about 146 MB on disk; the ADM Price member, about 154 MB compressed, is streamed and
   only our counties' rows are kept) are cached in `data/raw/r8/`.

### 2. PRF allocation rules we checked

| Rule | Where it is written | How farms.yaml satisfies it |
|---|---|---|
| Percent of value must go to more than one interval (at least 2) | 26-RI-PRF sec. 2(a); FCIC-18150 para. 32C | every farm uses 3 or 4 intervals |
| Each selected interval gets at least 10% | 26-RI-PRF sec. 2(a); ADM field 51 = 0.10 | smallest share is 10% (OKC_graze Sep-Oct) |
| Each interval at most the county maximum: 50% (TX, NM, FL), 60% (OK, MO, CO, IL) | 26-RI-PRF sec. 2(a) points to the Special Provisions; ADM 2026 field 52, same value for every grid and interval in each county | largest shares: 50% ABQ Aug-Sep (NM max 50%), 45% DEN Apr-May (CO max 60%) |
| The same month cannot be in two selected intervals | 26-RI-PRF sec. 2(b) (example: picking Apr-May rules out Mar-Apr and May-Jun) | checked pairwise with `agri_hedge.prf_intervals.overlaps` |
| Shares sum to 100% for each grid, use, practice and share | FCIC-18150 para. 14 | all sum to 1.00 |
| Coverage level 70-90% | 26-RI-PRF sec. 5(a)(1) | 0.85 or 0.90 |
| Productivity factor 60-150% in 1% steps | FCIC-18150 para. 13; 26-RI-PRF sec. 5(a)(2) | 1.30-1.50 |
| 2027 only: Jan-Feb at most 25% | DST `GetMaxAcrePercentage` for 2027, all study counties | no farm uses Jan-Feb |
| Not all intervals offered in every county | FCIC-18150 para. 32B | all 11 intervals are in the 2026 ADM for every study county |

### 3. County context (2022 Census of Agriculture)

**Table A1. Farms, land and hay.** "Perm. pasture & range" is pastureland other than cropland and
woodland; "All pasture" adds cropland and woodland that were pastured. (D) = withheld by NASS.

| County (site) | Farms | Land in farms (ac) | Avg size (ac) | Median size (ac) | Perm. pasture & range (ac) | All pasture (ac) | Hay harvested (ac) | of which alfalfa | other hay | Hay (tons) |
|---|---|---|---|---|---|---|---|---|---|---|
| Parker TX (DFW) | 4,379 | 341,108 | 78 | 17 | 209,968 | 246,440 | 35,001 | 1,408 | 33,593 | 52,034 |
| Atascosa TX (SAT) | 1,673 | 688,382 | 411 | 80 | 519,046 | 590,599 | 17,679 | 161 | 17,518 | 26,860 |
| Grady OK (OKC) | 1,567 | 693,892 | 443 | 104 | 394,398 | 445,495 | 94,975 | 19,026 | 75,949 | 145,173 |
| Dade MO (SGF) | 703 | 313,523 | 446 | 130 | 142,524 | 169,006 | 45,497 | 4,137 | 41,360 | 80,607 |
| Elbert CO (DEN) | 1,714 | 929,434 | 542 | 60 | 740,876 | 754,726 | 14,206 | 5,711 | 8,495 | 27,984 |
| Torrance NM (ABQ) | 577 | 1,692,413 | 2,933 | 283 | 1,563,638 | 1,659,800 | 4,319 | 2,217 | 2,102 | 13,599 |
| Hardee FL (TPA) | 920 | 290,694 | 316 | 40 | 156,917 | 185,798 | 8,070 | (D) | (D) | 30,238 |
| Kane IL (ORD, row-crop contrast) | 509 | 146,717 | 288 | 46 | 2,433 | 4,029 | 4,913 | 3,410 | 1,503 | 17,874 |

**Table A2. Livestock and sales.**

| County | Cattle & calves (head) | Beef cows (head) | Beef-cow operations | Livestock sales ($) | Cattle sales ($) | All sales ($) | Corn grain (ac) | Soybeans (ac) |
|---|---|---|---|---|---|---|---|---|
| Parker TX | 44,486 | 23,989 | 1,854 | 59,965,000 | 22,925,000 | 68,496,000 | 153 | - |
| Atascosa TX | 65,442 | (D) | 1,058 | 49,102,000 | 45,704,000 | 65,106,000 | 1,931 | - |
| Grady OK | 128,974 | (D) | 952 | 173,716,000 | 71,797,000 | 199,811,000 | 3,063 | 7,954 |
| Dade MO | 83,715 | 46,158 | 458 | 104,805,000 | 56,857,000 | 144,472,000 | 16,548 | 39,937 |
| Elbert CO | 35,783 | 21,397 | 601 | 31,477,000 | 27,221,000 | 47,118,000 | 7,343 | - |
| Torrance NM | 32,755 | (D) | 326 | 33,350,000 | (D) | 45,619,000 | 720 | - |
| Hardee FL | 71,991 | 40,938 | 523 | 62,439,000 | 30,221,000 | 228,514,000 | - | - |
| Kane IL | 11,478 | 1,064 | 41 | 58,190,000 | 26,942,000 | 284,003,000 | 67,315 | 57,349 |

**Table A3. Beef-cow herd sizes: operations / cows in each herd-size class**, plus derived measures.

| County | 1-9 | 10-19 | 20-49 | 50-99 | 100-199 | 200-499 | 500+ | Class holding the median cow | Pasture ac per beef cow |
|---|---|---|---|---|---|---|---|---|---|
| Parker TX | 1,274 / 5,105 | 288 / 3,753 | 224 / 6,020 | 40 / 2,656 | 14 / (D) | 13 / 4,041 | 1 / (D) | 20-49 | 10.3 |
| Atascosa TX | 430 / (D) | 253 / 3,332 | 240 / 6,765 | 85 / 5,618 | 25 / 3,175 | 16 / 4,829 | 9 / 7,190 | 50-99 | 19.1 (upper bound) |
| Grady OK | 243 / (D) | 170 / 2,262 | 294 / 8,630 | 117 / 8,136 | 59 / 7,616 | 46 / 13,664 | 23 / 14,542 | 200-499 | 8.1 (upper bound) |
| Dade MO | 101 / 576 | 63 / 906 | 110 / 3,253 | 68 / 4,717 | 57 / 8,273 | 48 / 15,854 | 11 / 12,579 | 200-499 | 3.7 |
| Elbert CO | 320 / 1,206 | 97 / 1,274 | 111 / 3,160 | 29 / 2,103 | 19 / 2,592 | 21 / 7,275 | 4 / 3,787 | 200-499 | 35.3 |
| Torrance NM | 116 / (D) | 88 / 1,173 | 37 / 1,051 | 38 / 2,554 | 20 / 2,935 | 24 / 6,674 | 3 / 3,058 | 200-499 | 95.1 (upper bound) |
| Hardee FL | 179 / 882 | 102 / 1,370 | 97 / 2,761 | 56 / 3,924 | 25 / 3,730 | 45 / 11,897 | 19 / 16,374 | 200-499 | 4.5 |
| Kane IL | 9 / (D) | 19 / 240 | 8 / 285 | 2 / (D) | 3 / 366 | - | - | 100-199 | 3.8 |

Where the county total is withheld, we used the sum of the published size classes (it misses the
withheld 1-9 head class, a few thousand cows at most), so acres per cow is an upper bound. "All
pasture" is shared with stocker cattle and horses, so acres per beef cow overstates the land a cow
actually needs. Parker County is mostly small rural-residential farms near Fort Worth (median farm 17
acres, 52% of farms are 10-49 acres per the county profile), which is why its median herd is small.

### 4. Forage, hay, prices and rents

**Table B. Forage production, hay and market values.** Prices and state yields are "other hay"
(HAY excluding alfalfa) unless labeled. NRCS production is total air-dry plant production in a
normal year, with the unfavorable-favorable year range in parentheses; it shows how much forage moves
with rainfall (unfavorable years give 44-69% of normal).

| County | Other-hay price 2025 MY ($/ton, state) | Alfalfa price 2025 ($/ton) | Other-hay yield 2016-25 mean (min-max) t/ac, state | Census 2022 county hay t/ac | Pasture cash rent, county ($/ac) | Pasture cash rent 2025, state ($/ac) | NRCS normal-yr production lb/ac (unfav-fav) | Share of county soils rated | AUM/ac at 25% (NRCS) |
|---|---|---|---|---|---|---|---|---|---|
| Parker TX | 130 | 232 | 1.92 (1.50-2.45) | 1.49 | 13.5 (2024) | 7.7 | 3,943 (2,653-5,119) | 87% | 1.08 |
| Atascosa TX | 130 | 232 | 1.92 (1.50-2.45) | 1.52 | 15.5 (2025) | 7.7 | 3,379 (2,165-4,188) | 86% | 0.93 |
| Grady OK | 88 | 164 | 1.69 (1.25-1.95) | 1.53 | 24.5 (2025) | 18 | 4,645 (3,091-6,077) | 71% | 1.27 |
| Dade MO | 113 | 170 | 1.90 (1.20-2.15) | 1.77 | 35 (2025) | 38.5 | 4,626 (2,989-6,204) | 5% | (not used) |
| Elbert CO | 153 | 164 | 1.69 (1.35-1.95) | 1.97 | 6.1 (2025) | 7.0 | 1,364 (800-1,868) | 83% | 0.37 |
| Torrance NM | 185 | 246 | 1.84 (1.40-2.20) | 3.15 | 1.7 (2025) | 4.1 | 1,192 (525-1,833) | 86% | 0.33 |
| Hardee FL | 120 | - | 2.72 (2.30-3.10) | 3.75 | 11 (2024) | 20 | 4,832 (3,324-6,308) | 100% | 1.32 |
| Kane IL | 106 | 161 | 2.33 (2.00-2.70) | 3.64 | - | 49 | - | 0% | - |

Notes. 2022 was a drought year in Texas and Oklahoma (state other-hay yields 1.50 and 1.25 t/ac), so
Census 2022 county hay yields there are low. Torrance and Kane county hay yields are high because
they are mostly irrigated or alfalfa hay. Only 5% of Dade County soils carry a range rating (the
county is improved fescue pasture and woodland), so for Dade we use the hay-yield proxy instead.
Parker and Hardee had no 2025 county rent estimate; we use 2024.

**Dominant NRCS ecological sites** (top 3 by soil acres in the county; normal-year lb/acre):
Parker: Tight Sandy Loam 29-33" PZ (R084BY175TX, 4,211), Loamy Slope 30-38 (R085AY379TX, 5,000), Sandy
Loam 29-33" PZ (R084BY174TX, 4,517). Atascosa: Tight Sandy Loam (R083AY024TX, 3,038), Loamy Sand
(R083AY022TX, 3,205), Western Clay Loam (R083AY027TX, 3,700). Grady: Loamy Upland (R080AY056OK, 4,742),
Sandy Loam Savannah (R084AY075OK, 3,900), Loamy Bottomland (R080AY050OK, 6,100). Dade: Chert Upland
Woodland (F116BY003MO), Chert Upland Prairie (R116BY021MO), Loamy Upland (R112XY103KS, 5,101). Elbert:
Sandy Foothill (R049XB210CO, 1,503), Sandy Plains (R067BY024CO, 1,628), Loamy Plains (R067BY002CO,
1,281). Torrance: Loamy (R042CY109NM, 1,043), Limy (R042CY108NM, 981), Sandy (R042CY112NM, 1,205).
Hardee: Sandy Flatwoods and Hammocks (F155XY120FL, 4,658), Sandy Freshwater Isolated Marshes and
Swamps (R155XY070FL, 6,881), Sandy Flatwoods on Rises and Knolls (F155XY150FL, 3,393).

**Table B2. NRCS soil-survey forage ratings (high management, non-irrigated), area-weighted.**
These are potential yields under good fertility and management, usually above what typical farms
get, so we report them only as an upper reference.

| County | Rating |
|---|---|
| Parker | improved bermudagrass 5.41 AUM/ac; introduced bluestem 4.62 AUM/ac |
| Atascosa | improved bermudagrass 3.43 AUM/ac; kleingrass 2.52 AUM/ac |
| Grady | improved bermudagrass 4.81 AUM/ac; introduced bluestem 4.93 AUM/ac |
| Dade | tall fescue 5.40 tons/ac (6.93 AUM/ac on the few soils rated in AUM) |
| Hardee | bahiagrass 8.05 AUM/ac; improved bermudagrass 9.47 AUM/ac |

**Realized vs. formula stocking.** The NRCS rangeland formula (25% harvest efficiency) and the
Census's realized pasture acres per cow agree well in Parker (11 vs 10 acres per AU), Grady (9 vs 8)
and Elbert (32 vs 35). Atascosa (13 vs 19) and especially Torrance (37 vs 95) are stocked well below
the formula, consistent with brush, drought and degraded range. Dade and Hardee, which are mostly
improved (fertilized, planted) pasture, carry 2-3 times more cattle per acre than the rangeland
formula implies.

### 5. PRF participation (RMA Summary of Business)

**Table C1. 2025 totals and long-run results.** Penetration = 2026 insured acres / (Census 2022 all
pasture + hay acres).

| County | Policies earning prem. (2025) | Insured acres (2025) | Liability ($) | Total premium ($) | Subsidy ($) | Indemnity ($) | Loss ratio 2025 | Pooled LR 2015-25 | Pooled indemnity / farmer-paid premium | Penetration 2026 |
|---|---|---|---|---|---|---|---|---|---|---|
| Parker TX | 27 | 13,437 | 717,789 | 148,348 | 76,182 | 111,090 | 0.75 | 0.90 | 1.90 | 6.9% |
| Atascosa TX | 141 | 184,787 | 6,225,373 | 1,504,955 | 815,272 | 1,864,056 | 1.24 | 1.01 | 2.20 | 31.1% |
| Grady OK | 31 | 21,377 | 1,237,462 | 225,109 | 117,422 | 203,017 | 0.90 | 0.50 | 1.04 | 3.8% |
| Dade MO | 16 | 6,073 | 444,386 | 72,303 | 37,470 | 107,926 | 1.49 | 0.80 | 1.69 | 6.0% |
| Elbert CO | 25 | 200,979 | 3,550,553 | 720,352 | 371,684 | 221,482 | 0.31 | 0.70 | 1.46 | 26.9% |
| Torrance NM | 39 | 504,760 | 7,407,073 | 1,672,154 | 900,599 | 1,701,926 | 1.02 | 0.69 | 1.49 | 41.2% |
| Hardee FL | 215 | 153,663 | 29,138,339 | 6,481,807 | 3,306,560 | 16,186,454 | 2.50 | 1.57 | 3.20 | 86.6% |
| Kane IL | 7 | 698 | 383,126 | 55,779 | 28,449 | 45,665 | 0.82 | 0.82 (2018-25) | 1.68 | 8.5% |

**Table C2. Insured acres by year.** Blank = no PRF or masked rows in that year. Parker 2015-2021,
Torrance 2016 and Kane 2018-2023 come from RMA's "All Other Crops" rows for the Rainfall Index plan
(RMA hides small commodities this way); they may include Annual Forage or Apiculture.

| Site | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DFW (Parker) | 9,143 | 8,103 | 11,009 | 10,601 | 11,464 | 8,270 | 9,437 | 12,596 | 15,843 | 16,851 | 13,437 | 19,324 |
| SAT (Atascosa) | 111,560 | 90,796 | 89,432 | 86,761 | 81,901 | 97,649 | 129,629 | 137,903 | 171,572 | 170,929 | 184,787 | 188,972 |
| OKC (Grady) | 48,454 | 54,353 | 55,341 | 59,831 | 58,099 | 51,702 | 42,938 | 32,563 | 25,330 | 17,690 | 21,377 | 20,402 |
| SGF (Dade) | 295 | 313 | 733 | 2,421 | 3,082 | 2,538 | 3,518 | 2,794 | 3,932 | 5,355 | 6,073 | 12,794 |
| DEN (Elbert) | 146,515 | 77,589 | 103,748 | 100,634 | 113,333 | 106,313 | 114,122 | 180,907 | 230,234 | 198,336 | 200,979 | 207,029 |
| ABQ (Torrance) |  | 172,321 | 245,970 | 38,836 | 91,539 | 163,850 | 300,818 | 542,447 | 632,842 | 502,767 | 504,760 | 685,388 |
| TPA (Hardee) | 148,746 | 28,193 | 74,092 | 99,134 | 101,833 | 94,888 | 118,718 | 123,815 | 123,538 | 142,214 | 153,663 | 167,962 |
| ORD (Kane) |  |  |  | 208 | 208 | 66 | 201 | 434 | 460 | 653 | 698 | 764 |

**Table C3. Loss ratio (indemnity / total premium) by year.** 2026 is incomplete: the SOB files are
dated 2026-10-26 and the last intervals of 2026 have not been settled.

| Site | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 (partial) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DFW | 0.19 | 0.41 | 0.58 | 0.77 | 0.72 | 0.69 | 0.37 | 1.43 | 1.44 | 0.85 | 0.75 | 0.41 |
| SAT | 0.44 | 0.30 | 0.44 | 0.79 | 1.42 | 0.66 | 1.07 | 1.90 | 1.05 | 0.89 | 1.24 | 0.64 |
| OKC | 0.24 | 0.62 | 0.69 | 0.49 | 0.28 | 0.11 | 0.82 | 0.69 | 0.40 | 0.51 | 0.90 | 0.83 |
| SGF | 1.47 | 2.32 | 0.82 | 0.75 | 0.26 | 0.28 | 0.56 | 0.71 | 0.65 | 0.73 | 1.49 | 0.13 |
| DEN | 0.04 | 1.14 | 0.77 | 0.78 | 0.13 | 1.22 | 1.92 | 1.26 | 0.31 | 0.41 | 0.31 | 0.30 |
| ABQ |  | 0.29 | 0.38 | 1.46 | 0.45 | 1.33 | 1.32 | 0.36 | 0.61 | 0.46 | 1.02 | 1.14 |
| TPA | 0.18 | 1.31 | 1.78 | 1.08 | 0.34 | 0.74 | 1.57 | 1.99 | 1.79 | 1.53 | 2.50 | 0.73 |
| ORD |  |  |  | 0.83 | 0.57 | 0.96 | 2.38 | 0.70 | 0.81 | 0.58 | 0.82 | 0.17 |

**Table C4. Policies earning premium by year.**

| Site | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DFW | 11 | 10 | 12 | 11 | 13 | 15 | 19 | 17 | 24 | 28 | 27 | 32 |
| SAT | 89 | 71 | 68 | 65 | 63 | 70 | 99 | 106 | 131 | 130 | 141 | 153 |
| OKC | 79 | 83 | 79 | 83 | 77 | 63 | 50 | 38 | 31 | 29 | 31 | 31 |
| SGF | 3 | 3 | 5 | 6 | 7 | 8 | 6 | 5 | 10 | 16 | 16 | 24 |
| DEN | 22 | 15 | 20 | 17 | 19 | 19 | 27 | 36 | 36 | 28 | 25 | 25 |
| ABQ |  | 18 | 23 | 13 | 13 | 21 | 29 | 38 | 42 | 44 | 39 | 45 |
| TPA | 85 | 51 | 80 | 103 | 104 | 109 | 131 | 153 | 173 | 196 | 215 | 262 |
| ORD |  |  |  | 2 | 2 | 2 | 3 | 3 | 3 | 8 | 7 | 11 |

Average insured acres per policy in 2026: Parker 603, Atascosa 1,235, Grady 658, Dade 533, Elbert
8,281, Torrance 15,230, Hardee 641, Kane 69. Grady is the one county where PRF use has shrunk
(83 policies in 2018, 31 in 2026); Hardee, Atascosa, Torrance and Dade have grown quickly.

**Table C5. Grazing vs. haying, 2026** (sobtpu type code 007 vs 030).

| County | Grazing acres | Haying acres | Haying share of liability | Grazing liability/acre ($) | Haying liability/acre ($) |
|---|---|---|---|---|---|
| Parker TX | 17,847 | 1,477 | 37% | 33.36 | 235.29 |
| Atascosa TX | 168,988 | 19,984 | 41% | 22.54 | 133.17 |
| Grady OK | 17,776 | 2,626 | 47% | 34.95 | 206.35 |
| Dade MO | 11,729 | 1,065 | 28% | 54.60 | 237.69 |
| Elbert CO | 206,546 | 483 | 2% | 17.72 | 173.32 |
| Torrance NM | 682,324 | 3,064 | 6% | 14.81 | 223.11 |
| Hardee FL | 108,065 | 59,897 | 79% | 66.05 | 441.40 |
| Kane IL | 10 | 754 | 100% | 108.10 | 567.66 |

About 27% of Atascosa's haying liability is irrigated haying (practice codes 425-435); elsewhere
irrigated haying is 0-8% (Torrance 2026: 5%).

**Table C6. Coverage level chosen, share of insured acres 2021-2025 (buy-up only).**

| County | 70% | 75% | 80% | 85% | 90% |
|---|---|---|---|---|---|
| Parker TX | 0% | 0% | 0% | 30% | 70% |
| Atascosa TX | 0% | 6% | 0% | 68% | 26% |
| Grady OK | 6% | 8% | 4% | 10% | 73% |
| Dade MO | 0% | 4% | 4% | 38% | 55% |
| Elbert CO | 0% | 0% | 4% | 18% | 78% |
| Torrance NM | 0% | 20% | 2% | 42% | 37% |
| Hardee FL | 0% | 0% | 0% | 1% | 99% |
| Kane IL | 0% | 0% | 0% | 0% | 100% |

**Table C7. Implied average productivity factor, 2026** = sum of liability / sum of (acres x
county base value x coverage level) over all sobtpu rows (organic and irrigated rows use their own
base values).

| County | Grazing | Haying |
|---|---|---|
| Parker TX | 1.36 | 1.50 |
| Atascosa TX | 1.44 | 1.49 |
| Grady OK | 1.28 | 1.39 |
| Dade MO | 1.48 | 1.45 |
| Elbert CO | 1.47 | 1.50 |
| Torrance NM | 1.49 | 1.50 |
| Hardee FL | 1.46 | 1.49 |
| Kane IL | (10 acres) | 1.49 |

**Table C8. Which intervals buyers choose: share of liability in each interval, 2021-2025 (%).**
This is the "interval selection" data the task asked for; it comes straight from the practice codes
in the `sobtpu` files. Shares are liability-weighted, which is the same as weighting by percent of
value.

| County | Use | Jan-Feb | Feb-Mar | Mar-Apr | Apr-May | May-Jun | Jun-Jul | Jul-Aug | Aug-Sep | Sep-Oct | Oct-Nov | Nov-Dec |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Parker TX | Grazing | 12 | 5 | 7 | 12 | 9 | 7 | 8 | 12 | 9 | 5 | 15 |
| Parker TX | Haying | 4 | 20 | 2 | 14 | 3 | 14 | 5 | 13 | 7 | 6 | 12 |
| Atascosa TX | Grazing | 16 | 3 | 14 | 3 | 13 | 4 | 13 | 5 | 12 | 6 | 12 |
| Atascosa TX | Haying | 15 | 4 | 13 | 4 | 13 | 5 | 13 | 5 | 12 | 5 | 11 |
| Grady OK | Grazing | 14 | 4 | 15 | 3 | 15 | 4 | 13 | 5 | 12 | 2 | 13 |
| Grady OK | Haying | 5 | 7 | 13 | 7 | 12 | 9 | 12 | 12 | 10 | 4 | 8 |
| Dade MO | Grazing | 18 | 5 | 5 | 5 | 5 | 15 | 8 | 8 | 12 | 1 | 18 |
| Dade MO | Haying | 14 | 1 | 5 | 2 | 4 | 15 | 14 | 12 | 7 | 2 | 24 |
| Elbert CO | Grazing | 6 | 4 | 8 | 3 | 14 | 3 | 7 | 19 | 5 | 21 | 10 |
| Elbert CO | Haying | 0 | 0 | 13 | 2 | 28 | 0 | 0 | 28 | 3 | 2 | 25 |
| Torrance NM | Grazing | 15 | 12 | 12 | 7 | 12 | 2 | 6 | 13 | 4 | 4 | 12 |
| Torrance NM | Haying | 0 | 24 | 0 | 23 | 0 | 11 | 0 | 24 | 0 | 12 | 6 |
| Hardee FL | Grazing | 28 | 10 | 25 | 3 | 2 | 1 | 0 | 0 | 2 | 7 | 21 |
| Hardee FL | Haying | 26 | 14 | 27 | 3 | 3 | 2 | 0 | 0 | 1 | 10 | 15 |
| Kane IL | Grazing | 15 | 0 | 18 | 0 | 18 | 0 | 18 | 0 | 18 | 0 | 13 |
| Kane IL | Haying | 4 | 0 | 22 | 0 | 5 | 1 | 9 | 24 | 5 | 0 | 29 |

What this shows. (1) In Atascosa, Grady and Kane, grazing buyers spread value nearly evenly across
the six odd intervals, which covers all 12 months with no overlap. (2) Hardee buyers concentrate on
the dry season (Nov-Dec, Jan-Feb, Mar-Apr hold 74% of grazing liability and 68% of haying liability)
and almost ignore the June-September rainy season. (3) Elbert grazing buyers put the most value on
Oct-Nov (21%) and Aug-Sep (19%), outside the spring growth period that NRCS describes. (4) Winter
intervals (Nov-Dec, Jan-Feb) are popular almost everywhere, although the NRCS site descriptions we
read place the forage growing season in the warmer months at every site. We
did not find a primary source that explains these choices; see open questions.

### 6. County base values for 2026

**Table D. 2026 county base value ($/acre) by intended use and practice** (ADM 2026, A00810 Price,
field 34; identical across every grid ("sub county") and interval within each county).

| County | Grazing | Haying non-irrigated | Haying irrigated | Haying non-irrigated, organic certified | PRF grids listed for county |
|---|---|---|---|---|---|
| Parker TX | 27.6 | 181.0 | 118.0 | 218.0 | 8 |
| Atascosa TX | 18.2 | 113.0 | 85.0 | 136.0 | 11 |
| Grady OK | 31.6 | 172.0 | 105.0 | 206.0 | 12 |
| Dade MO | 41.4 | 184.0 | 81.0 | 220.0 | 6 |
| Elbert CO | 13.5 | 171.0 | 35.0 | 188.0 | 18 |
| Torrance NM | 11.5 | 200.0 | 48.0 | 221.0 | 19 |
| Hardee FL | 50.3 | 333.0 | 233.0 | 366.0 | 6 |
| Kane IL | 79.2 | 414.0 | 112.0 | 497.0 | 7 |

Exact source: `2026_A00810_Price_YTD.txt`, Record Category 03 (sub county), Commodity 0088, Plan 13,
Filing Date 2025-08-31, Released 2026-10-01, no deleted rows. Organic transitional rows carry the
conventional value. Irrigated haying is worth less than non-irrigated haying in every county,
presumably because irrigated hay depends less on rain (RMA does not say why in the files we read). The 2027 values from the Decision Support Tool's
`GetPricingRates` (grazing and non-irrigated haying, all 7 PRF counties) are identical.

Comparing base values with market values: the grazing base value is 1.2 times the county pasture
cash rent in Atascosa and Dade, 1.3 in Grady, 2.0 in Parker, 2.2 in Elbert, 4.6 in Hardee and 6.8 in
Torrance. PRF therefore insures far more than the rental value of grass in the arid and Florida sites.

### 7. The 11 farms in plain English

Per-interval dollar protection = policy protection x that interval's share. Premiums use the 2026
rates on the farm-point grid (OTHER-WS file, see Numbers table).

**DFW_hay (Parker County, TX; 150 acres of dryland bermudagrass hay).** A commercial hay producer
west of Fort Worth. Expected
crop 1.92 tons/acre (Texas 10-year average; 1.50 in the 2022 drought), worth about $250/acre at
$130/ton. Rain from spring through early fall decides how many cuttings and how heavy they are. The
farmer insures Apr-May ($14,661), Jun-Jul ($12,828) and Aug-Sep ($9,163): $36,652 total at 90%
coverage and PF 1.50, about $244 of protection per acre, roughly equal to expected revenue. Premium
$7,518, farmer pays $3,684.

**DFW_graze (Parker County, TX; 800 acres of pasture, about 75-80 cows).** A cow-calf ranch (the cows raise
calves that are sold after weaning) on Cross Timbers range and introduced grasses. NRCS normal-year
production 3,943 lb/acre (2,653 in a dry year), enough for about 1.08 AUM/acre. Grazing land rents
for $13.50/acre. A dry spring means less grass, so the rancher buys hay or sells cows early. Insures
Feb-Mar 15%, Apr-May 35%, Jun-Jul 25%, Sep-Oct 25% (two rain peaks: May and October): $26,827 of
protection at PF 1.35, premium $5,579 ($2,734 farmer-paid).

**SAT_graze (Atascosa County, TX; 1,500 acres of South Texas brush range, about 80 cows).** Normal
production 3,379 lb/acre, ranging from 2,165 to 4,188 with rain. NRCS describes a late-spring rain
peak, a hot dry July and a second peak in early fall, so the rancher puts 40% each on May-Jun and
Sep-Oct and 20% on Mar-Apr. 85% coverage (Atascosa's usual choice; 55% subsidy), PF 1.45: $33,647
protection, premium $7,106 ($3,198 farmer-paid). Pasture rents for $15.50/acre, so protection per
acre ($22.43) is 1.45 times the rent.

**OKC_hay (Grady County, OK; 200 acres of dryland bermudagrass/native hay).** Expected 1.69 tons/acre
(Oklahoma 10-year average; 1.25 in 2022), $149/acre at Oklahoma's low $88/ton price. We assume rain in
April-June sets the first cutting and summer rain the regrowth. Insures Apr-May 35%, Jun-Jul 40%,
Aug-Sep 25% (Oklahoma allows up to 60% per interval): $43,344 protection at PF 1.40, 1.46 times
expected revenue per acre, premium $7,435 ($3,643 farmer-paid).

**OKC_graze (Grady County, OK; 1,000 acres of mixed-grass prairie and bermudagrass, about 120
cows).** Normal production 4,645 lb/acre (Loamy Upland is the main site). Rain peaks in May (4.8 in
on the farm grid). Insures Mar-Apr 30%, May-Jun 40%, Jul-Aug 20%, Sep-Oct 10%: $36,972 protection at
PF 1.30 (Grady buyers choose the lowest PF of any county), premium $6,385 ($3,129 farmer-paid).

**SGF_hay (Dade County, MO; 150 acres of tall fescue hay).** Southwest Missouri cool-season grass
hay, expected 1.90 tons/acre (1.20 in the 2023 drought), $215/acre at $113/ton. We assume the main
cutting comes in late spring, so spring rain matters most, with some fall regrowth. Insures Mar-Apr 40%,
May-Jun 40%, Sep-Oct 20%: $36,018 protection at PF 1.45, premium $5,435 ($2,663 farmer-paid).

**SGF_graze (Dade County, MO; 500 acres of fescue pasture, about 135 cows).** Dade has the most
productive pasture of our sites (3.7 acres per cow; rent $35/acre). A dry spring or a dry late
summer cuts grazing days and forces hay feeding. Insures Mar-Apr 30%, May-Jun 30%, Aug-Sep 20%,
Oct-Nov 20%: $27,945 protection at PF 1.50, premium $4,350 ($2,131 farmer-paid).

**DEN_graze (Elbert County, CO; 7,000 acres of shortgrass and foothill range, about 200 cows).**
Normal production only 1,364 lb/acre (800 in a dry year), so a cow needs about 35 acres. Cool-season
grasses start about April 1 and warm-season grasses about May 1 (NRCS). Insures Apr-May 45%, Jun-Jul
35%, Aug-Sep 20%: $123,322 protection at PF 1.45, premium $19,041 ($9,330 farmer-paid). Rent is only
$6.10/acre, so protection per acre ($17.62) is 2.9 times the rent.

**ABQ_graze (Torrance County, NM; 12,000 acres of blue-grama range, about 125 cows).** The driest
site: 13.9 in of rain a year on the farm grid, 5.0 in of it in July-August monsoon storms; normal
production 1,192 lb/acre (525 in a dry year). Insures Apr-May 20%, Jun-Jul 30%, Aug-Sep 50% (the New
Mexico maximum): $175,950 protection at 85% coverage and PF 1.50, the largest of our farms, premium
$26,933 ($12,120 farmer-paid). Pasture rents for $1.70/acre, so PRF protection ($14.66/acre) is 8.6
times the rent.

**TPA_graze (Hardee County, FL; 1,000 acres of bahiagrass pasture, about 220 cows).** Central Florida
gets about 60% of its rain in June-September, which is dependable (CV 0.30-0.49 on the farm grid); we
assume the main forage risk is a dry spring (March-May, CV 0.63-0.81) and an early end to the rains. Insures Mar-Apr 40%, May-Jun 40%,
Oct-Nov 20%: $65,642 protection at PF 1.45, premium $12,369 ($6,061 farmer-paid). Protection per acre
($65.64) is 6.0 times the $11 rent.

**TPA_hay (Hardee County, FL; 200 acres of bahiagrass/bermudagrass hay).** Expected 2.72 tons/acre
(Florida average; the Census 2022 Hardee figure is 3.75), $326/acre at $120/ton. Insures Mar-Apr 30%,
May-Jun 40%, Sep-Oct 30%: $89,910 protection at PF 1.50 ($449.55/acre, the highest per-acre
protection of any farm), premium $14,903 ($7,302 farmer-paid).

Kane County IL (ORD) gets no farm: it is the row-crop contrast site (67,315 acres of corn and 57,349
of soybeans in 2022), PRF does not insure row crops, and `farms.yaml` sites must be keys of
`STUDY_SITES`. For reference, 754 of Kane's 764 PRF acres (2026) are haying, at a $414/acre base
value.

### 8. Summary of all farms

**Table E. Farm summary** (crop year 2026 terms). Policy protection = acres x base value x PF x
coverage. "At PF 1.0" shows the protection a farmer would have at the unadjusted county value.

| Farm | County | Use | Acres | Intervals (share) | Base value ($/ac) | PF | Cov. | Protection/ac ($) | Policy protection ($) | At PF 1.0 ($) | Expected value/ac ($) | Premium 2026 ($, total / farmer) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DFW_hay | Parker County, TX | haying | 150 | Apr-May 40%, Jun-Jul 35%, Aug-Sep 25% | 181.0 | 1.50 | 0.90 | 244.35 | 36,652 | 24,435 | 249.6 | 7,518 / 3,684 |
| DFW_graze | Parker County, TX | grazing | 800 | Feb-Mar 15%, Apr-May 35%, Jun-Jul 25%, Sep-Oct 25% | 27.6 | 1.35 | 0.90 | 33.53 | 26,827 | 19,872 | 13.5 | 5,579 / 2,734 |
| SAT_graze | Atascosa County, TX | grazing | 1,500 | Mar-Apr 20%, May-Jun 40%, Sep-Oct 40% | 18.2 | 1.45 | 0.85 | 22.43 | 33,647 | 23,205 | 15.5 | 7,106 / 3,198 |
| OKC_hay | Grady County, OK | haying | 200 | Apr-May 35%, Jun-Jul 40%, Aug-Sep 25% | 172.0 | 1.40 | 0.90 | 216.72 | 43,344 | 30,960 | 148.7 | 7,435 / 3,643 |
| OKC_graze | Grady County, OK | grazing | 1,000 | Mar-Apr 30%, May-Jun 40%, Jul-Aug 20%, Sep-Oct 10% | 31.6 | 1.30 | 0.90 | 36.97 | 36,972 | 28,440 | 24.5 | 6,385 / 3,129 |
| SGF_hay | Dade County, MO | haying | 150 | Mar-Apr 40%, May-Jun 40%, Sep-Oct 20% | 184.0 | 1.45 | 0.90 | 240.12 | 36,018 | 24,840 | 214.7 | 5,435 / 2,663 |
| SGF_graze | Dade County, MO | grazing | 500 | Mar-Apr 30%, May-Jun 30%, Aug-Sep 20%, Oct-Nov 20% | 41.4 | 1.50 | 0.90 | 55.89 | 27,945 | 18,630 | 35.0 | 4,350 / 2,131 |
| DEN_graze | Elbert County, CO | grazing | 7,000 | Apr-May 45%, Jun-Jul 35%, Aug-Sep 20% | 13.5 | 1.45 | 0.90 | 17.62 | 123,322 | 85,050 | 6.1 | 19,041 / 9,330 |
| ABQ_graze | Torrance County, NM | grazing | 12,000 | Apr-May 20%, Jun-Jul 30%, Aug-Sep 50% | 11.5 | 1.50 | 0.85 | 14.66 | 175,950 | 117,300 | 1.7 | 26,933 / 12,120 |
| TPA_graze | Hardee County, FL | grazing | 1,000 | Mar-Apr 40%, May-Jun 40%, Oct-Nov 20% | 50.3 | 1.45 | 0.90 | 65.64 | 65,642 | 45,270 | 11.0 | 12,369 / 6,061 |
| TPA_hay | Hardee County, FL | haying | 200 | Mar-Apr 30%, May-Jun 40%, Sep-Oct 30% | 333.0 | 1.50 | 0.90 | 449.55 | 89,910 | 59,940 | 326.4 | 14,903 / 7,302 |

Total policy protection $696,229 ($477,942 at PF 1.0); total 2026 premium $117,054 (farmer-paid $55,995). Expected value
per acre is hay revenue (yield x price) for hay farms and county pasture cash rent for grazing farms.

Cross-check: the Decision Support Tool, given DFW_graze's exact inputs on grid 15429, returned
protection of $26,824 (ours $26,827; the tool rounds per interval) and a 2027-rate premium of $5,314.

### 9. Rainfall seasonality at the farm grids

**Table F. 1991-2020 mean monthly precipitation (inches) on each farm-point grid**, from the CPC
gauge analysis file produced by another workstream. The second block is the coefficient of variation
(standard deviation / mean): higher means that month's rain is less dependable.

| Grid (site) | Jan | Feb | Mar | Apr | May | Jun | Jul | Aug | Sep | Oct | Nov | Dec | Year |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 15429 DFW | 1.79 | 2.32 | 2.96 | 2.66 | 4.11 | 3.60 | 2.02 | 2.56 | 3.00 | 3.66 | 2.60 | 2.08 | 33.35 |
| 10626 SAT | 1.57 | 1.60 | 2.24 | 2.19 | 3.52 | 3.28 | 2.23 | 2.30 | 3.34 | 2.54 | 1.95 | 1.69 | 28.45 |
| 18129 OKC | 1.30 | 1.59 | 2.54 | 3.72 | 4.82 | 4.21 | 2.87 | 3.38 | 3.48 | 3.24 | 1.97 | 1.98 | 35.10 |
| 20845 SGF | 2.24 | 2.16 | 3.54 | 4.97 | 6.08 | 5.14 | 4.21 | 3.69 | 4.50 | 3.69 | 3.45 | 2.52 | 46.18 |
| 23204 DEN | 0.42 | 0.48 | 1.01 | 1.74 | 2.35 | 2.11 | 2.76 | 2.77 | 1.16 | 1.02 | 0.61 | 0.44 | 16.86 |
| 17497 ABQ | 0.54 | 0.45 | 0.63 | 0.56 | 0.98 | 1.19 | 2.60 | 2.42 | 1.81 | 1.33 | 0.64 | 0.74 | 13.90 |
| 8893 TPA | 2.32 | 1.98 | 2.40 | 2.55 | 3.50 | 8.47 | 7.80 | 8.19 | 7.15 | 2.74 | 1.64 | 1.90 | 50.65 |
| 26267 ORD | 2.10 | 1.86 | 2.30 | 3.84 | 4.80 | 4.44 | 3.99 | 4.06 | 3.34 | 3.44 | 2.64 | 2.16 | 38.97 |

| CV | Jan | Feb | Mar | Apr | May | Jun | Jul | Aug | Sep | Oct | Nov | Dec |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DFW | 0.73 | 0.88 | 0.59 | 0.59 | 0.59 | 0.76 | 0.76 | 0.70 | 0.85 | 0.79 | 0.95 | 0.91 |
| SAT | 0.83 | 1.06 | 0.79 | 0.87 | 0.72 | 0.82 | 1.15 | 1.30 | 0.68 | 0.82 | 1.07 | 1.12 |
| OKC | 0.79 | 0.80 | 0.69 | 0.55 | 0.71 | 0.69 | 0.72 | 0.69 | 0.58 | 0.66 | 0.91 | 0.68 |
| SGF | 0.60 | 0.68 | 0.50 | 0.54 | 0.49 | 0.52 | 0.59 | 0.62 | 0.68 | 0.65 | 0.77 | 0.71 |
| DEN | 0.61 | 0.74 | 0.63 | 0.64 | 0.63 | 0.62 | 0.45 | 0.46 | 0.83 | 0.77 | 0.76 | 0.82 |
| ABQ | 0.75 | 0.83 | 0.80 | 0.96 | 0.93 | 0.84 | 0.44 | 0.43 | 0.61 | 0.78 | 0.91 | 0.91 |
| TPA | 0.65 | 0.82 | 0.81 | 0.63 | 0.75 | 0.43 | 0.33 | 0.30 | 0.49 | 0.65 | 1.08 | 0.99 |
| ORD | 0.56 | 0.67 | 0.49 | 0.42 | 0.44 | 0.48 | 0.45 | 0.47 | 0.75 | 0.65 | 0.58 | 0.61 |

Dry-season months have the highest CV (Hardee Nov 1.08; Atascosa Aug 1.30), which is one plausible
reason buyers favor them: a two-month index far below normal is more likely there.

## Implications for our replication design

- **Use `farms.yaml` as the exposure set.** For each farm and interval, the PRF indemnity to
  replicate is protection x share x payment factor, where the payment factor depends on how far the
  grid's final index falls below the coverage trigger (B4 owns that formula). The largest single
  interval exposures are ABQ_graze Aug-Sep ($87,975), DEN_graze Apr-May ($55,495) and ABQ_graze
  Jun-Jul ($52,785); the smallest are OKC_graze Sep-Oct ($3,697) and DFW_graze Feb-Mar ($4,024).
- **Each PRF interval spans two Kalshi months.** Every farm needs contracts in 6-8 calendar months,
  and the two-month index is a sum, so a replicating portfolio should be built on the two-month
  total, not on single months.
- **Hardee and Torrance are the hardest cases.** Hardee buyers insure the dry season, when monthly
  totals on the Hardee farm grid are about 1.6-2.6 in and highly variable (CV 0.63-1.08 for
  Nov-Apr), so Kalshi strikes would need to sit low in the ladder. Torrance pays on Jul-Aug monsoon totals of about 2.4-2.6 in per
  month on the farm grid, and the Kalshi station (Albuquerque) is 53 miles away.
- **Separate the benchmark from the economic loss.** For grazing farms, PRF protection is 1.5-8.6
  times the rental value of the grass, so "replicate PRF" and "hedge the rancher's real loss" are
  different targets. The YAML carries both: protection (via base value, PF, coverage) and
  `expected_value_usd_per_acre`.
- **Run sensitivities on PF and coverage.** Buyers choose PF near 1.5; at PF 1.0 the same farms have
  23-33% less protection ($477,942 instead of $696,229 in total; Table E). Subsidy is 51% at 90% coverage but 55-59% at 70-85%,
  which matters when comparing the farmer's net cost with an unsubsidized Kalshi portfolio.
- **Also test the "revealed" allocations.** Our farms follow growing-season logic. A second scenario
  set using each county's actual interval mix (Table C8) would show how replication quality depends
  on interval choice.
- **2027 terms:** base values are unchanged, but Jan-Feb is capped at 25%. Any optimizer that picks
  intervals for 2027 must enforce that cap in addition to the 2026 rules (implemented in
  `validate_farm` in `scripts/r8_pull_county_data.py`).

## Unverified claims and open questions

- **Extension guidance on interval choice was not gathered.** The shared web-search quota ran out
  early in this task and university extension sites (e.g. Oklahoma State fact sheets) blocked
  scripted downloads, so the only extension source read is a 2010 Texas AgriLife newsletter (Pena
  2010), which suggests "April-May for spring and August-September for Fall". Interval choices in
  `farms.yaml` therefore rest on NRCS ESD climate narratives, the farm-grid rainfall record and the
  handbook's instruction to insure the months when rain is needed for forage. A follow-up should
  read current extension PRF guides for each state.
- **Why buyers pick dry-season and "every other interval" patterns** (Table C8) is unexplained. A
  likely explanation is that buyers pick intervals with high expected payouts relative to the
  subsidized premium, but we have no source for that.
- **Agronomic statements** (bermudagrass and bahiagrass are warm-season grasses; tall fescue is a
  cool-season grass that slumps in summer) are general knowledge we did not cite to a primary source.
- **Hardee haying gap.** 59,897 acres insured as haying vs 8,070 acres harvested for hay in the 2022
  Census. Possible reasons (land changing use after 2022, acreage that could be hayed but is grazed,
  Census undercount, or misreported intended use) are not verified.
- **SSURGO forage numbers** are NRCS estimates by soil type, not measurements on these farms; the
  Table B2 crop ratings assume high management. Range production is total plant production, not
  only forage that cattle eat.
- **Grazing expected value** uses cash rent as a proxy for the value of a year's grass. Rent
  reflects land markets and hunting/recreation value, not only forage.
- **Withheld Census values**: beef cow totals for Atascosa, Grady and Torrance and the Hardee hay
  split are withheld; we used size-class sums (lower bounds).
- **Masked SOB years** (Parker 2015-2021, Torrance 2016, Kane 2018-2023) come from "All Other Crops"
  Rainfall Index rows and could include Annual Forage or Apiculture. 2026 SOB results are partial.
- **Implied PF** assumes the base value in the 2026 ADM applies to every row; it can exceed 1.50 by
  rounding (Kane grazing, 10 acres).
- **Premium rates** in Table E come from another workstream's ADM 2026 extract
  (`data/processed/prf_actuarial_study_grids.csv`); we checked base values and protection against our
  own pull and the DST, but not each premium rate.
- **Hay prices** are state averages; local Parker or Hardee prices may differ. The 2025 marketing-year
  price is NASS's final value (Agricultural Prices, Aug 31 2026, p.33; re-checked 2026-11-01). It
  supersedes the preliminary Crop Values 2025 Summary figures (TX $136, OK $90, MO $114).
- **Herd sizes** in the farm descriptions are acres / county pasture acres per beef cow and are
  approximate.

## Sources

USDA Risk Management Agency (RMA)
- RMA. Actuarial Data Master, crop year 2026, `2026_ADM_YTD.zip` (members A00810 Price, A00480
  Interval, A00470 Intended Use, A00510 Practice, A00540 Type, A01210 Statement, A00070 Subsidy
  Percent) and `ADMLayout.zip` (AdmLayout.pdf, "ADM Record Layout for 2026", as of 7/1/2025).
  https://pubfs-rma.fpac.usda.gov/pub/References/actuarial_data_master/2026/
- RMA. Summary of Business, state/county/crop files `sobcov_2015.zip` ... `sobcov_2026.zip` and
  `sobtpu_2015.zip` ... `sobtpu_2026.zip`, with layouts
  `SOB_State_County_Crop_with_Coverage_Level_1989_Forward.pdf` and `SOBTPU_External_All_Years.pdf`.
  https://pubfs-rma.fpac.usda.gov/pub/Web_Data_Files/Summary_of_Business/state_county_crop/
- FCIC. Rainfall Index Pasture, Rangeland, Forage (PRF) Crop Provisions, 26-RI-PRF (released August
  2025). https://www.rma.usda.gov/sites/default/files/2025-08/Rainfall-Index-Pasture-Rangeland-Forage-Crop-Provisions-26-RI-PRF.pdf
- FCIC. Rainfall Index Insurance Standards Handbook, FCIC-18150 (August 2025), paras. 13, 14, 32.
  https://www.rma.usda.gov/sites/default/files/2025-08/2026-18150-Rainfall-Index-Handbook.pdf
- RMA. PRF Decision Support Tool, https://public-rma.fpac.usda.gov/apps/PRF ; public API endpoints
  `PrfExternalStates/GetSubCountiesByCountyAndState`, `PrfExternalStates/GetCountiesAndStatesFromGridId`,
  `PrfExternalPricingRates/GetPricingRates`, `PrfExternalMaxAcrePercentage/GetMaxAcrePercentage` under
  https://public-rma.fpac.usda.gov/apps/PrfWebApi/ (queried 2026-10-29; serves crop year 2027).

USDA National Agricultural Statistics Service (NASS)
- NASS Quick Stats, https://quickstats.nass.usda.gov/ : 2022 Census of Agriculture county data;
  SURVEY HAY price received (marketing year 2023-2025) and yield (state 2016-2025, county 2010-2025);
  SURVEY RENT cash rent (county 2021-2025, state 2023-2025); SURVEY CATTLE county inventory 2022-2026.
  Queried 2026-10-29.
- NASS. 2022 Census of Agriculture County Profiles: Parker TX
  https://www.nass.usda.gov/Publications/AgCensus/2022/Online_Resources/County_Profiles/Texas/cp48367.pdf ;
  Atascosa TX .../Texas/cp48013.pdf ; Grady OK .../Oklahoma/cp40051.pdf ; Dade MO .../Missouri/cp29057.pdf ;
  Elbert CO .../Colorado/cp08039.pdf ; Torrance NM .../New_Mexico/cp35057.pdf ; Hardee FL
  .../Florida/cp12049.pdf ; Kane IL .../Illinois/cp17089.pdf (all under
  https://www.nass.usda.gov/Publications/AgCensus/2022/Online_Resources/County_Profiles/).

USDA Natural Resources Conservation Service (NRCS)
- NRCS. Soil Survey Geographic Database (SSURGO) via Soil Data Access, tables `laoverlap`,
  `muaoverlap`, `component` (rsprod_l/r/h), `coecoclass`, `cocropyld`.
  https://sdmdataaccess.sc.egov.usda.gov/Tabular/post.rest (queried 2026-10-29).
- NRCS Ecological Site Descriptions, Ecosystem Dynamics Interpretive Tool (EDIT) services, retrieved
  2026-10-29:
  R067BY002CO Loamy Plains https://edit.sc.egov.usda.gov/services/descriptions/esd/067B/R067BY002CO.json ;
  R049XB210CO Sandy Foothill https://edit.sc.egov.usda.gov/services/descriptions/esd/049X/R049XB210CO.json ;
  R042CY109NM Loamy https://edit.sc.egov.usda.gov/services/descriptions/esd/042C/R042CY109NM.json ;
  F155XY120FL Sandy Flatwoods and Hammocks https://edit.sc.egov.usda.gov/services/descriptions/esd/155X/F155XY120FL.json ;
  R083AY024TX Tight Sandy Loam https://edit.sc.egov.usda.gov/services/descriptions/esd/083A/R083AY024TX.json ;
  R116BY021MO Chert Upland Prairie https://edit.sc.egov.usda.gov/services/descriptions/esd/116B/R116BY021MO.json ;
  also read: R084BY175TX, R084BY174TX, R083AY022TX, R080AY056OK, R112XY103KS (same URL pattern).

University extension
- Pena, J.G. (2010). "Revised Pasture, Rangeland, Forage Risk Management Insurance Program." AG-ECO
  News 26(25), Texas AgriLife Extension, 2 September 2010.
  https://agecoext.tamu.edu/wp-content/uploads/2013/08/09-02-2010.pdf

Project files from other workstreams (read, not modified)
- `data/processed/study_grids.csv` (farm and station PRF grid IDs).
- `data/processed/prf_actuarial_study_grids.csv` (ADM 2025/2026 premium rates, base values, limits).
- `data/processed/cpc_monthly_precip_grids.parquet` (CPC monthly precipitation by grid).

## Fact-check log

Independent fact-check run 2026-11-01 (branch `run/factcheck-2`). Summary: [11_fact_check_summary.md](../analysis/11_fact_check_summary.md).

| Claim in this doc | Source checked (2026-11-01) | Verdict |
|---|---|---|
| Hay price received, MY2025, other hay: TX 130, OK 88, MO 113, CO 153, NM 185, FL 120, IL 106; alfalfa TX 232, OK 164, MO 170, CO 164, NM 246, IL 161 | NASS Quick Stats re-queried (same public endpoints as `r8_pull_county_data.py`), period "MARKETING YEAR" | confirmed (all 13 state values) |
| Same prices vs NASS Crop Values 2025 Summary (TX 136, OK 90, MO 114) | Crop Values 2025 Summary (2026-02-26) marks 2025 as "Preliminary". The hay marketing year ends April 30, 2026, so the February figure cannot be the final full-year average | not an error. Quick Stats holds the current value, so **no change to `farms.yaml`**. This settles overview next step 1: keep 130/88/113, or switch doc 03b to the Quick Stats values for consistency |
| Subsidy 59/55/51; at least 2 intervals; at least 10% each; Jan-Feb 25% cap for 2027 | 7 U.S.C. 1508(e)(7); PM-26-053 | confirmed |
| SOB pooled county loss ratios and returns (Hardee 1.57 / 3.20 ... Grady 0.50 / 1.04) | Parker and Torrance re-summed by the reviewer from `sobcov_2015..2025` (finding from `run/factcheck-1`): Parker 0.90 with masked 9999 rows, 1.08 PRF-only (2022-2025); Torrance PRF-only 0.71. Other counties not re-computed | Parker 0.90 confirmed with a **clarification** (includes masked rows; note added under Key findings). Others unverifiable (not re-checked) |
| 2026 county base values, max-percent caps, implied productivity factors, Census 2022 county data, NRCS SSURGO production, cash rents | ADM 2026, the DST API (empty response to a plain request), Census and SSURGO not re-pulled | unverifiable (not re-checked) |
| Station-to-farm distance and grid IDs | internal (repo `locations.py`, `study_grids.csv`) | out of scope (internal) |

No number in this doc or in `farms.yaml` was changed.
