# USDA PRF Rainfall Index: exactly how coverage, index values, and payouts are calculated

**Proposal cell:** Week 1 / Maya (R3)  |  **Status:** VERIFIED (exceptions listed under "Unverified claims")  |  **Last updated:** 2026-10-29

Machine-readable companion: [`data/processed/prf_rules.yaml`](../../data/processed/prf_rules.yaml). It holds every rule below, with sources, plus the worked examples as unit-test vectors.

Status labels used here:
- **CONFIRMED**: we read it in the primary document, or in RMA's own data or tool.
- **DERIVED**: we computed it from CONFIRMED inputs. The method is shown.
- **UNVERIFIED**: from a secondary source, or our inference.

## Key findings

- **The payout is a put option on a rainfall index, paid separately for each grid and two-month interval.** For each unit:
  - indemnity = max(0, (T − I) / T) × policy protection, where T = 100 × coverage level and I is the final grid index.
  - policy protection = county base value × coverage × productivity factor × acres × percent of value × share.
  - Nobody inspects the ranch. Payment depends only on the index (Basic Provisions 27.1-RI §§7-8, 13).
- **The interval codes are confirmed: 625 = Jan-Feb through 635 = Nov-Dec.** The source is RMA's ADM interval table (A00480). The handbook's own example uses 628 = April-May and 631 = July-August. This agrees with `prf_intervals.py`, where the owner has already set `VERIFIED = True`.
- **2027 allocation rules:**
  - at least 2 intervals, with no month in two selected intervals;
  - at least 10% of value in each selected interval;
  - at most 50%, 60% or 70% per interval, depending on the state;
  - **Jan-Feb is newly capped at 25%** (California keeps 50%; the 25% cap is confirmed in PM-26-053, but PM-26-053 states no California exception, so the 50% rests on ADM27 A00810 and was not re-checked in the 2026-11-01 fact-check).
- **Coverage, productivity and subsidy:**
  - Coverage levels are 70-90% in 5-point steps, and the productivity factor runs from 60% to 150%.
  - Premium subsidy is 59% at 70-75% coverage, 55% at 80-85%, and 51% at 90%. It is identical in the 2025, 2026 and 2027 ADM.
  - The 2025 budget law (One Big Beautiful Bill Act) did **not** change PRF's base subsidy. For PRF it only lengthened beginning-farmer status to 10 years and set extra subsidy at +15/13/11/10 points.
  - The administrative fee is $30 per crop per county.
- **The rainfall data source changed for the 2027 crop year:**
  - from 2027: NOAA NCEI nClimGrid monthly data averaged onto the same 0.25° grid, with a 1951 to (crop year − 2) baseline;
  - through 2026: NOAA CPC data with a 1948 to (crop year − 2) baseline;
  - the final index is rounded to 0.1 point.
  - 2026 crop-year intervals, including those finalized after 2026-08-31, still settle on CPC.
- **At grid level, CPC and NCEI indices differ a lot.** We took the official Jun-Jul 2026 (CPC) payment factors for 49 randomly drawn grids that paid. RMA's own tool now shows NCEI-recomputed indices for those grids:
  - mean absolute difference: 15.8 index points; largest: 92.3;
  - 17 of the 49 grids would not have paid at 90% coverage under NCEI.
  - **The Decision Support Tool's history is therefore not what PRF actually paid.**
- **Rounding:**
  - RMA's official payment factor is round-half-up to 3 decimals. It reproduces 3,000 of 3,000 sampled ADM records exactly.
  - RMA's Decision Support Tool (DST) uses the unrounded factor. The two give answers $0-$5 apart in our examples.
  - We encode both and recommend the official rule for payouts.
- **Timing:**
  - Sales closing and acreage reporting: Dec 1 of the prior year. Premium billing: Sep 1.
  - In 2026, RMA published final indices 62-68 days after each interval ended. The indemnity is due within 60 days after publication.
- **Real 2027 numbers for our DFW farm grid (Parker County, TX, grid 15429):**
  - County base value: $27.60/acre for grazing, $181.00/acre for non-irrigated hay.
  - A 500-acre grazing policy at 90% coverage, split 50/50 between Apr-May and Jul-Aug, has $12,420 of protection and $2,180 total premium. The rancher pays $1,068 plus the $30 fee.
  - A final Apr-May index of 62 pays $1,931.

## Numbers table

| Quantity | Value | Units | Region / period | Source (URL + page/table) | Verification |
|---|---|---|---|---|---|
| Grid size | 0.25 × 0.25 | degrees lat × lon | Lower 48 | [BP27](#sources) §1 "Grid", p.3; [HB27](#sources) ¶32A, p.12 | CONFIRMED |
| Grid N-S extent | 17.27 | miles | all grids | haversine on cell edges | DERIVED |
| Grid E-W extent at 32.875°N (grid 15429) | 14.51 | miles | Parker Co. TX | haversine on cell edges | DERIVED |
| Grid area at 32.875°N | 250.6 | sq mi | Parker Co. TX | product of the two above | DERIVED |
| Grid size per RMA fact sheet | "approximately 17 by 17" | miles at equator | general | [FACTSHEET](#sources) p.1 | CONFIRMED |
| Grid-ID formula constants | 300 columns; origin 20.0°N, 130.0°W | — | Lower 48 | fitted to 16 lookups on [GRID_LAYER](#sources) + HB26 ¶75-76 McLouth KS grids 22939/22940 | DERIVED |
| Number of index intervals | 11 | two-month intervals | all | [HB26](#sources) ¶32B, pp.11-12; [ADM27](#sources) A00480 | CONFIRMED |
| Interval codes | 625 (Jan-Feb) … 635 (Nov-Dec) | code | all | [ADM27](#sources) A00480; HB26 Exhibit 5 p.52 (628, 631); [DST](#sources) JS (625-635) | CONFIRMED |
| Other RI interval codes not used by PRF | 636-639 | code | all | [ADM27](#sources) A00480 | CONFIRMED |
| Minimum intervals selected | 2 | intervals | all | HB26 ¶32C, p.12; [CP27](#sources) §2(a), p.1 | CONFIRMED |
| Max non-overlapping intervals | 6 | intervals | all | from CP27 §2(b) non-overlap rule | DERIVED |
| Minimum percent of value per selected interval | 10 | % | all | CP27 §2(a), p.1; ADM27 A00810 (every record) | CONFIRMED |
| Max percent of value, Jan-Feb (625) | 25 (California: 50) | % | 2027, all states | [PM26053](#sources) (25% confirmed in fact-check: "Limit the percent of value for the January-February interval to 25 percent"); ADM27 A00810 (California 50%) | CONFIRMED (25%); California exception UNVERIFIED in fact-check |
| Max percent of value, other intervals | 50 (11 states incl. TX, NM, FL); 60 (21 states incl. OK, MO, CO); 70 (17 states) | % | 2027 | ADM27 A00810 "Maximum Acre Percent" | CONFIRMED |
| Coverage levels | 70, 75, 80, 85, 90 | % | all | CP27 §5(a)(1), p.2; ADM27 A00070; DST validation | CONFIRMED |
| Productivity factor range | 60-150, 1% steps | % | PRF (Hawaii 60-120) | CP27 §5(a)(2), p.2; HB26 ¶13, p.5 | CONFIRMED |
| CAT coverage (defined, not offered for PRF) | 65% coverage × 45% productivity | % | — | BP27 §1 "CAT", p.2; CP27 §5, p.2 | CONFIRMED |
| Stocking-rate requirement (grazing) | ≥ 25 | % of stocking rate in owned livestock | 2027+ | CP27 §4(j), p.2; HB27 Exh. 4 item 8 p.49, Exh. 6 p.58 | CONFIRMED |
| Native sod protection factor; subsidy cut | 65%; −50 points | — | IA, MN, MT, NE, ND, SD | CP27 §4(g), p.2 | CONFIRMED |
| Native sod exemption | ≤ 5 acres per grid; applies 4 of first 10 years after tillage after 2018-12-20 | acres; years | same states | CP27 §4(h)-(i), p.2 | CONFIRMED |
| Expected grid index | 100 (ADM value 1.0000) | index | every grid-interval | BP27 §1, p.2; ADM27 A00810 | CONFIRMED |
| Historical baseline, NCEI era | 1951 to CY−2 (2027: 1951-2025) | years | 2027+ | [RIDATA27](#sources) p.1; HB27 ¶33D, p.14 | CONFIRMED |
| Historical baseline, CPC era | 1948 to CY−2 (2025: 1948-2023) | years | ≤ 2026 | HB26 ¶33D, p.13 | CONFIRMED |
| Final index rounding | 3 decimals of ratio (0.1 index point) | — | 2027+ | RIDATA27 p.1 | CONFIRMED |
| NCEI USDA grid cells | 13,533 | cells | Lower 48 | count of rows in NCEI 202504.usda.csv | CONFIRMED |
| NCEI posting schedule | 4th business day of month; "initial" = last month, "final" = through 2 months ago | — | 2026 | [NCEI_GUIDE](#sources) | CONFIRMED |
| NCEI final-file timestamps | Jun 2026: 2026-08-07; Jul: 2026-09-09; Aug: 2026-10-12 | date | 2026 | NCEI directory listing, 2026-10-29 | CONFIRMED |
| RMA final-index release dates (CPC era) | Nov-Dec 2025: 2026-03-05; Mar-Apr: 07-07; Apr-May: 08-03; May-Jun: 09-01; Jun-Jul: 10-01 | date | 2026 | [PM_FINALS](#sources) (PM-26-015, -039, -044, -050, -063) | CONFIRMED |
| Lag from interval end to final index | 62-68 | days | 2026 releases above | from dates above | DERIVED |
| Indemnity payment deadline | ≤ 60 days after final index published; interest from day 61 | days | all | BP27 §8(d), p.13; §21(a), p.19; PM-26-039 | CONFIRMED |
| Final-index correction window | < 1 year, NCEI written notice + Administrator approval | — | all | BP27 §8(e), p.13 | CONFIRMED |
| Premium subsidy by coverage | 70%: 59; 75%: 59; 80%: 55; 85%: 55; 90%: 51 | % of premium | 2025, 2026, 2027 | ADM27 A00070 cat. 04, plan 13 (also 2025 and 2026 A00070); DST "SubsidyLevel"; [USC1508](#sources) (e)(7) | CONFIRMED |
| Beginning farmer extra subsidy | +15 (yrs 1-2), +13 (yr 3), +11 (yr 4), +10 (yrs 5-10) | percentage points | 2026+ | BP27 §11(g), p.15; [OBBA](#sources); [MGR25006](#sources) | CONFIRMED |
| Beginning farmer definition | ≤ 10 crop years operating | years | 2026+ | OBBA; MGR25006 | CONFIRMED |
| Veteran extra subsidy | +10 | percentage points | all | BP27 §11(g)(2), p.15 | CONFIRMED |
| Administrative fee | 30 | USD per crop per county | additional coverage | USC1508 (c)(10)(A); BP27 §11(e), pp.14-15 | CONFIRMED |
| CAT administrative fee (not offered for PRF) | 655 | USD per crop per county | — | USC1508 (b)(5)(A) | CONFIRMED |
| Late-payment interest | 1.25 | % simple per month | all | BP27 §20(a), p.18 | CONFIRMED |
| Sales closing / acreage reporting / cancellation | 2026-12-01 | date | 2027 crop year | ADM27 A00200 (all 232,184 PRF records); CP27 §9, p.3 | CONFIRMED |
| Premium billing date | 2027-09-01 | date | 2027 crop year | ADM27 A00200 | CONFIRMED |
| Termination date | 2027-12-01 | date | 2027 crop year | ADM27 A00200 | CONFIRMED |
| Insurance period | 2027-01-01 to 2027-12-31 | dates | 2027 crop year | BP27 §12(a), p.15; ADM27 A00200 | CONFIRMED |
| Contract change date | Aug 31 (2027 rules out by 2026-08-31) | date | annual | BP27 summary of changes; HB27 issue date 2026-08-31; ADM27 A00200 | CONFIRMED |
| PRF commodity / plan codes | 0088 / 13 | code | all | ADM27 A00420, A00460 | CONFIRMED |
| Intended use codes | grazing 007, haying 030 | code | all | ADM27 A00470 | CONFIRMED |
| Practice codes | irrigation 002/003/997; organic 001/002/997 | code | all | ADM27 A00490, A00500 | CONFIRMED |
| PRF states | 49 | states (48 + HI) | 2027 | ADM27 A00030 | CONFIRMED |
| Parker Co. TX county base values (grid 15429) | grazing 27.60; hay non-irr 181.00; hay irr 118.00; hay non-irr organic 218.00 | USD/acre | 2027 | ADM27 A00810; DST GetPricingRates | CONFIRMED |
| Grid 15429 premium rates, 90% coverage | Jan-Feb 0.2396 … Apr-May 0.1581 … Nov-Dec 0.2094 (full table in YAML) | $ premium per $ protection | 2027 | DST GetPricingRates / GetValidIntervalCodes | CONFIRMED |
| Grid 15429 premium rates, 70% coverage | Apr-May 0.0725 … Jan-Feb 0.1764 | $ per $ | 2027 | DST | CONFIRMED |
| Study-grid 90% rate range | 0.0470 (Hardee FL Jul-Aug) to 0.2985 (Torrance NM Apr-May) | $ per $ | 2027 | DST (14 grids) | CONFIRMED |
| Study-county CBVs | grazing 10.10 (Bernalillo NM) to 50.30 (Hardee FL); hay non-irr 113 (Atascosa TX) to 397 (Hillsborough FL) | USD/acre | 2027 | DST (cross-checked ADM A00810) | CONFIRMED |
| Grid 15429 Apr-May 2025 rainfall | 167.33 + 159.76 = 327.09 | mm | NCEI final | NCEI 202504/202505.usda.csv at (32.875, −97.875) | CONFIRMED |
| Grid 15429 Apr-May 1951-2025 mean | 203.094 | mm | NCEI | DST "AverageIntervalMeasurement" | CONFIRMED |
| Grid 15429 Apr-May 2025 index | 161.1 | index | NCEI basis | DST; 327.09 / 203.094 = 1.6105 | CONFIRMED |
| Official payment factor rule fit | 3,000 of 3,000 (half-up); 2,648 of 3,000 (half-even) | offers | Jun-Jul 2026 | [ADM26D](#sources) A01130 | DERIVED |
| Share of grids with zero Jun-Jul 2026 payment at 90% | 55.2% of 13,201 | % | 2026 (CPC) | ADM26D A01130 | DERIVED |
| CPC vs NCEI Jun-Jul 2026 index gap (paying grids) | n = 49; mean diff +10.8; median +8.8; mean abs 15.8; SD 19.7; max abs 92.3; 17/49 NCEI ≥ 90; corr 0.47 | index points | 2026 | ADM26D (CPC, implied) vs DST (NCEI) | DERIVED |
| Grid 14511 Jun-Jul 2026 | CPC 77.9 (payment factor 0.134 at 90%) vs NCEI 53.0 (22.34 + 23.45 = 45.79 mm / 86.4245) | index | 2026 | ADM26D; NCEI 202606/202607; DST | CONFIRMED |
| RMA statement on CPC→NCEI loss ratios | "overall loss ratios remain nearly identical" | — | national | [NEWS0430](#sources) | CONFIRMED |
| Handbook example inputs | CBV 20.00; 90%; PF 120%; rates 0.1000 / 0.1100; subsidy 51%; 645 acres, 4 grids | — | illustrative | HB26 Exhibit 5, pp.50-57 | CONFIRMED |
| Handbook example outputs | protection 10,692; premium 1,114; subsidy 568; producer 546; indemnities 167 / 1,332 / 1,705 | USD | illustrative | HB26 Exhibit 5, pp.53-57 | CONFIRMED |
| Worked example 1 (grazing) every value in Table 9.1 | e.g. protection 12,420; premium 2,180; producer 1,068; indemnity 1,931 | USD | 2027 Parker Co. | §9 of this doc | DERIVED (inputs CONFIRMED; premium/subsidy cross-checked in DST) |
| Worked example 2 (haying) every value in Table 10.1 | e.g. protection 81,450; premium 13,561; producer 6,645; indemnity 12,665 | USD | 2027 Parker Co. | §10 of this doc | DERIVED (inputs CONFIRMED; premium/subsidy cross-checked in DST) |
| Payout slope, example 1 Apr-May | 69.00 per index pt = 33.97 per mm = 863 per inch | USD | grid 15429 | 6,210 / 90; 203.094 mm / 100 per point | DERIVED |
| Break-even index, example 1 / 2 | 74.09 / 75.25 | index | grid 15429 | §9, §10 | DERIVED |

## Detail

### 1. What PRF is, in one paragraph

PRF (Pasture, Rangeland, Forage) is by far the largest product under the USDA Risk Management Agency's (RMA) Rainfall Index plan (plan code 13). It is not the only one: the same plan also insures Annual Forage and Apiculture ($1,222.1 million and $461.8 million of 2025 liability, against $6,547.0 million for PRF; RMA Summary of Business `sobcov_2025`). *[Corrected 2026-11-01: earlier text said PRF was RMA's "only rainfall-index insurance".]* It is sold by private "approved insurance providers" (AIPs), which must offer it to everyone in the offer area (HB26 ¶1E, p.2).

It is an **area index plan**. The rancher is not paid for their own loss. They are paid when an official rainfall index for the surrounding grid cell falls below a trigger.

The rancher picks:
- a coverage level (how far below normal rain must fall before PRF pays);
- a productivity factor (how much dollar value per acre to insure);
- which two-month **index intervals** to insure, and how to split the value across them.

The only insurable cause of loss is "a final grid index less than my trigger grid index" (HB26 Exhibit 4, item 6, p.49).

Jargon used below:
- **Premium**: the price of insurance.
- **Subsidy**: the share of the premium the federal government pays.
- **Liability / policy protection**: the maximum dollar payout.
- **Indemnity**: the payout.
- **ADM**: the Actuarial Data Master, RMA's bulk files of rates, dates and values.
- **DST**: RMA's online PRF Decision Support Tool.

### 2. What can be insured: land, intended use, practices, units

**Intended use** (CP27 §1, §3; HB26 ¶16, p.6). Every insured acre is declared **grazing** (code 007) or **haying** (code 030), never both in the same year.
- **Grazing**: "used solely as pasture for livestock to roam and feed on." It has no irrigated or organic split; the ADM uses practice code 997 = none.
- **Haying**: "severance of the plant from its root by mechanical equipment and cured." It is split into irrigated (002) or non-irrigated (003). Each of those is conventional (997), certified organic (001) or transitional organic (002). Organic options exist only where the actuarial documents offer them (CP27 §6(d)).
- In the ADM, the haying practice code is the interval code minus 200, 160, 140, 100, 60 or 40, one offset per irrigation/organic combination (DERIVED from every 2027 record; see YAML).

**Insurable land** (CP27 §§3-4, pp.1-2):
- Perennial forage only: planted before July 1 of the previous year, naturally present native grass, or self-seeding annuals kept by grazing. Annually planted acreage is excluded; over-seeding is allowed.
- Land too steep, too far from water, or otherwise unfit for grazing is not insurable for grazing.
- Land too steep, wooded, cactus-covered or flooded for normal hay equipment is not insurable for haying.
- Public grazing land without a current-year use authorization is excluded (new for 2027).
- Leases, or a signed Lease Certification Form, must be in by the acreage reporting date (HB26 ¶21; BP27 §9(d)).
- A rancher may insure any part of their insurable acres in the county, but no more than 100% of them (CP27 §4(a)).

**New for 2027, grazing only:** the insured must have an insurable interest in livestock equal to **at least 25% of the stocking rate** for the insured acres (CP27 §4(j); PM-26-053). The stocking rate comes from the FSA National Crop Table or a state/federal lease. Records must be kept for 3 years.

The handbook's example: 150 acres at 1 animal unit per 3 acres is 50 AU. 25% of that is 13 AU, which is 52 sheep (HB27 Exhibit 6, p.58).

**Native sod** (never-tilled grassland) in IA, MN, MT, NE, ND and SD gets two penalties (CP27 §4(g)-(i)):
- liability is computed with a 65% protection factor;
- subsidy is 50 percentage points lower;
- this applies for 4 of the first 10 years after tillage, for land tilled after 2018-12-20.

None of our study sites are in those states.

**Unit** (BP27 §1, p.4): "the insured acres by crop, intended use, index interval, share, irrigated practice, organic practice, and county within or assigned to a grid."
- Every (grid × interval × use × practice × share) combination is its own unit with its own protection, premium and payout.
- Optional, enterprise and whole-farm units do not exist for PRF (HB26 ¶12, p.5).

### 3. Grids: what they are and how a rancher picks one

A **grid** is a 0.25° latitude × 0.25° longitude cell with a numeric grid ID (BP27 §1, p.3). Cells follow lines of latitude and longitude, not county lines. One grid can sit in several counties: grid 15429 lies in both Parker and Wise Counties, TX.

- **Size.** North-south is 17.27 miles everywhere. East-west shrinks with latitude: 14.51 miles at Parker County (32.9°N), so about 250 square miles or 160,000 acres (DERIVED). RMA's fact sheet says "approximately 17 by 17 miles at the equator."
- **Cell edges** are at multiples of 0.25°. Grid 15429 spans 32.75-33.00°N and 98.00-97.75°W (GRID_LAYER). The precipitation value is attached to the cell center, e.g. (32.875, −97.875) (RIDATA27 p.1).
- **Grid ID formula** (DERIVED, matches all 16 of our lookups and the handbook's McLouth, KS example):

  `grid_id = 300 * floor((lat - 20.0)/0.25) + floor((lon + 130.0)/0.25) + 1`

  For points on a cell edge, use RMA's grid layer. The official lookup is RMA's Grid Locator map: https://public-rma.fpac.usda.gov/apps/PRF.
- **How a rancher picks** (HB26 ¶¶15, 71-76, pp.6, 15-38):
  - They click a **point of reference** inside the field on the Grid Locator map; that point fixes the grid and county.
  - Separate (noncontiguous) fields each need their own point.
  - A field that straddles a grid line may be assigned entirely to either grid, or split in any proportion (the total cannot exceed the field's acres).
  - A field that crosses a state line is insured in the state holding most of its acres, unless split.
  - The rancher certifies the grid on the acreage report (BP27 §9(b)(4)).

**Our study grids** (looked up 2026-10-29 on RMA's grid layer; 2027 offers from the DST, county base values cross-checked against the ADM):

| Site | Station grid (county) | Farm grid (county) | Farm county CBV grazing / hay non-irr ($/ac) | Max % per interval (Jan-Feb) |
|---|---|---|---|---|
| DFW | 15432 (Dallas 48113) | 15429 (Parker 48367) | 27.60 / 181.00 | 50% (25%) |
| SAT | 11527 (Bexar 48029) | 10626 (Atascosa 48013) | 18.20 / 113.00 | 50% (25%) |
| OKC | 18430 (Oklahoma 40109) | 18129 (Grady 40051) | 31.60 / 172.00 | 60% (25%) |
| SGF | 20547 (Greene 29077) | 20845 (Dade 29057) | 41.40 / 184.00 | 60% (25%) |
| DEN | 23802 (Denver 08031) | 23204 (Elbert 08039) | 13.50 / 171.00 | 60% (25%) |
| ABQ | 18094 (Bernalillo 35001) | 17497 (Torrance 35057) | 11.50 / 200.00 | 50% (25%) |
| TPA | 9490 (Hillsborough 12057) | 8893 (Hardee 12049) | 50.30 / 333.00 | 50% (25%) |
| ORD (contrast) | 26269 | 26267 | not studied | — |

Station-grid county base values: Dallas 26.80/198.00, Bexar 27.20/199.00, Oklahoma 31.60/172.00, Greene 41.40/184.00, Denver 13.50/171.00, Bernalillo 10.10/146.00, Hillsborough 41.70/397.00.
- Most grids span several counties: grid 18430 touches 5 counties, 15432 touches Dallas, Denton and Tarrant.
- Premium rates are set by grid, so they are identical whichever county the grid is priced in.
- County base values are set by county. In the grids we checked, the neighboring counties' CBVs happened to be equal (Dallas = Tarrant, Canadian = Oklahoma, Christian = Greene, Adams = Denver).

The 90% premium rates for all 14 grids are in the YAML under `reference_offers_2027.study_sites_90pct`.

### 4. The 11 index intervals and how protection is allocated

PRF splits the year into 11 overlapping two-month **index intervals**. The ADM interval table (A00480) gives the codes:

| Code | Interval | Code | Interval |
|---|---|---|---|
| 625 | Jan-Feb | 631 | Jul-Aug |
| 626 | Feb-Mar | 632 | Aug-Sep |
| 627 | Mar-Apr | 633 | Sep-Oct |
| 628 | Apr-May | 634 | Oct-Nov |
| 629 | May-Jun | 635 | Nov-Dec |
| 630 | Jun-Jul | | |

The handbook's example uses "index interval 628 (April-May) and 631 (July-August)" (HB26 Exhibit 5, p.52). The DST's JavaScript hard-codes `IntervalCodeStart = 625; IntervalCodeEnd = 635`. **The guess in `src/agri_hedge/prf_intervals.py` (625 + i) is correct.**

**Allocation rules:**

1. **At least 2 intervals** (HB26 ¶32C, p.12; CP27 §2(a): "more than one index interval").
2. **No overlapping months** (CP27 §2(b)). Choosing Apr-May rules out Mar-Apr and May-Jun for the same grid, use, practice and share. At most 6 intervals can be chosen (DERIVED).
3. **"Percent of value"**, in whole percents (BP27 §1, p.3), is spread over the chosen intervals and must **sum to 100%** (HB26 ¶14, p.6).
4. **Minimum 10%** in each chosen interval (CP27 §2(a); every ADM record).
5. **Maximum per interval** comes from the Special Provisions (the ADM field "Maximum Acre Percent"). In 2027:
   - Jan-Feb (625): 25% everywhere except California (50%). This is new for 2027 (PM-26-053).
   - All other intervals: 50% in AL, AZ, CA, FL, GA, LA, MS, NM, NC, SC, TX; 70% in CT, ID, ME, MA, MI, MN, MT, NH, NY, ND, OR, RI, SD, VT, WA, WI, WY; 60% in the other 21 states (ADM27 A00810).
6. **No difference by intended use.** At every study grid, grazing and haying had the same limits.
7. Interval choice need not match lease dates (HB26 ¶21C, p.10). The handbook warns that insuring months when rain is not needed is "not an effective use" (¶32C, p.12).
8. Insurance covers all 12 months, but pays only for the chosen intervals (BP27 §12, p.15).

Changing the allocation moves protection between intervals; it does **not** change the total. In the handbook example, $21.60 × 1,000 acres = $21,600 total, split $12,960 / $8,640 (HB26 ¶14, p.6).

### 5. Coverage and dollars of protection

- **County base value (CBV):** FCIC's dollar value per acre for the county, intended use and practice (BP27 §1, p.2; ADM A00810 "County Base Value"). It is set by county, not by grid.
- **Coverage level:** 70, 75, 80, 85 or 90%. One per county, crop, intended use and practice (CP27 §5(a)(1)).
- **Productivity factor:** 60-150% in 1% steps. It lets a rancher who thinks their land is better (or worse) than the county average scale protection up (or down) (HB26 ¶13, p.5; CP27 §5(a)(2)).
- If nothing is changed by the sales closing date, last year's coverage and productivity factor carry over (BP27 §7(d)).

Formulas (BP27 §7(a), (c), p.12):

```
dollar amount of protection per acre   ppa = CBV × coverage_level × productivity_factor
policy protection per unit             PP  = ppa × insured_acres × percent_of_value × share
total policy protection                     = Σ PP over units  (= ppa × acres × share when percents sum to 100%)
```

Parker County 2027 CBVs (ADM27 A00810, same in the DST):
- grazing: $27.60;
- non-irrigated hay: $181.00 conventional, $218.00 certified organic, $181.00 transitional;
- irrigated hay: $118.00 for all three.

Irrigated hay valued below non-irrigated is surprising, but both RMA sources agree (see open questions).

### 6. The rainfall index

**Definition** (RIDATA27 p.1; HB27 ¶33D, pp.14-15). For grid g, interval i and crop year Y:

```
P[g,i,Y]       = sum of the two monthly precipitation totals (mm) in interval i of year Y
final_index    = 100 × P[g,i,Y] / mean( P[g,i,y] for y = first_year … Y−2 )
first_year     = 1951 (NCEI, crop year 2027 on)   |   1948 (CPC, crop year 2026 and earlier)
rounding       = ratio to 3 decimals, i.e. index to 0.1 point ("Final grid indexes are rounded to 3 decimals")
```

- The **expected grid index** is 100 by construction: the mean is normalized to 100, and every 2027 ADM record has Expected Index Value = 1.0000.
- Each interval stands alone. Rain in Apr-May does not affect the Jun-Jul index (HB26 ¶33D, p.14).
- The 2-year lag exists because Y−2 is the last complete year when rates are filed at the Aug 31 contract change date (RIDATA27 p.1).

**Check against RMA's tool.** For grid 15429, Apr-May 2025:
- NCEI's final files give 167.33 mm (April) + 159.76 mm (May) = **327.09 mm** at the cell center (32.875, −97.875).
- That equals the DST's "IntervalMeasurement" exactly.
- The DST's 1951-2025 mean is 203.094 mm, so 327.09 / 203.094 = 1.6105, which rounds to 1.611. The index is **161.1**, as the DST reports (CONFIRMED).

**Data source and the NCEI switch:**
- Through the 2026 crop year, PRF used the NOAA Climate Prediction Center's (CPC) gridded, interpolated daily gauge analysis, with history from 1948 (HB26 ¶¶31-33).
- From the **2027 crop year** (contract change date 2026-08-31), it uses NOAA NCEI's nClimGrid-Monthly. That is a 1/24° station-based grid, averaged by NCEI onto the same 0.25° PRF cells, with history from 1951 (BP27 summary of changes; HB27 ¶¶31-33; RIDATA27 p.1; NCEI_GUIDE).
- PM-26-053 confirms the timing: the Basic Provisions changes (including CPC → NCEI) take effect for 2027 for all crops except Annual Forage, which switches in 2028.
- Grids and grid IDs are unchanged. RMA says "overall loss ratios remain nearly identical" and expects faster releases (NEWS0430).
- **2026 crop-year intervals still settle on CPC**, including those finalized after 2026-08-31. The Jun-Jul 2026 finals issued on 2026-10-01 do not match NCEI (next paragraph).
- NCEI data: https://www.ncei.noaa.gov/pub/data/cirs/usda/monthly/final/YYYYMM.usda.csv, with header `latitude,longitude,precipitation`, precipitation in mm, and 13,533 cells.

**CPC and NCEI can disagree a lot for a single grid.** Method:
- From the ADM daily file of 2026-10-01 (A01130), we took the official Jun-Jul 2026 PRF payment factors. These are CPC-based.
- We recovered each grid's implied final index from its factors at the 70-90% coverage levels.
- We compared that with the NCEI-based 2026 index the DST now shows, for 49 random grids that paid at 90% coverage.

Results:
- NCEI minus CPC: mean +10.8 points, median +8.8, mean absolute difference 15.8, largest 92.3.
- 17 of the 49 grids would not have paid at 90% under NCEI.
- The correlation between the two indices was 0.47 in this sample.
- Example: grid 14511 (West Texas) had an official CPC index of 77.9 (payment factor 0.134 at 90%). NCEI shows 53.0 (45.79 mm against an 86.42 mm mean; we confirmed this in NCEI's raw files).

Caveat: we sampled only grids that paid under CPC. That selection pushes the mean difference upward (regression to the mean), and an unconditional comparison is still needed (open questions). Even so, the absolute gaps are large.

Two consequences:
1. **The DST's "Historical Indexes" tab now shows NCEI-recomputed history.** It is not the index that actually paid in 2026 or earlier. RMA says so: bulk files "cannot be used to find the final index values that were used to issue indemnities. The Actuarial Information Browser is the definitive source" (RIDATA27 p.4).
2. Basis-risk results computed on CPC history may not carry over to 2027+ contracts.

**Preliminary vs final, and timing:**
- **NCEI** posts each month's files on the 4th business day of the following month. The "initial" (preliminary) file covers last month; "final" files cover everything through 2 months ago (NCEI_GUIDE). Observed final-file timestamps: June 2026 on 2026-08-07, July on 2026-09-09, August on 2026-10-12.
- So data for an interval ending in month M becomes final early in month M+2.
- **RMA** publishes final grid indices and payment factors by Product Management bulletin, the same day, in the ADM daily file and the Actuarial Information Browser (PM-26-039 and others).
- In 2026 (CPC data) the lag was 62-68 days after the interval ended: Nov-Dec 2025 → Mar 5; Mar-Apr → Jul 7; Apr-May → Aug 3; May-Jun → Sep 1; Jun-Jul → Oct 1.
- On 2026-10-29 the DST showed 2026 values only through Jun-Jul, i.e. only published finals.
- Once published, a final index changes only if NCEI reports an error in writing, the RMA Administrator approves, and less than a year has passed (BP27 §8(e)).

### 7. Trigger, payment calculation factor, indemnity, and rounding

```
trigger grid index      T   = expected_grid_index × coverage_level = 100 × coverage_level      (BP27 §1, p.4)
payment calc. factor    PCF = (T − final_index) / T   if final_index < T,  else 0               (BP27 §8(a)-(b), pp.12-13)
indemnity per unit          = PCF × PP                                                          (BP27 §8(c), p.13)
```

- A final index equal to the trigger pays nothing. In HB26 Exhibit 5, an index of 90 against a trigger of 90 pays $0.
- The maximum payout per unit is PP, reached at an index of 0.
- Payouts are linear in the shortfall. Each index point below T is worth PP/T dollars.

**Rounding.** No policy text gives a rounding rule for the payment factor. We established it from RMA data:

| Item | Official (ADM / handbook) | RMA Decision Support Tool |
|---|---|---|
| Final index | 0.1 point (RIDATA27) | 0.1 point |
| Protection per acre | not stated | rounded to cents (e.g. 26.979 → 26.98) |
| Unit protection PP | whole dollars (HB26 Exh. 5 tables) | nearest whole dollar (4,687.308 → 4,687) |
| Premium, subsidy | whole dollars. The handbook takes subsidy on the **total** premium (1,114 × 0.51 = 568) | whole dollars, per unit, half up. Per unit, the handbook example would give 566 |
| Payment factor | **round half up to 3 decimals**. All 3,000 sampled 2026 ADM factors are reproduced exactly; half-even fits only 2,648. The handbook uses 0.111, 0.333, 0.056, 0.222, 0.278 | **unrounded** (index 40.1 at 90% → 0.55444…) |
| Indemnity | 3-decimal factor × PP, whole dollars. This reproduces the handbook totals $167 / $1,332 / $1,705 (one handbook line uses unrounded PP 2,116.80) | unrounded factor × PP, whole dollars |

Our tests of the DST rules: four input sets (8 units), including odd ones such as 333 acres, productivity factor 115% and coverage 85%. The rules in the right-hand column reproduce every DST output (YAML `dst_oracle_*`).

The only gap with the official rule is the 3-decimal factor. Examples:
- Index 62 at 90% coverage: official factor 0.311 vs exact 0.3111…, worth $1-$5 here.
- Index 63.4 at 80%: the factor is exactly 0.2075, so the official factor (0.208) pays $380 while the DST pays $379.

**Our recommendation:** compute indemnities with the official 3-decimal factor, and keep a switch to reproduce DST output.

**How and when it pays** (BP27 §§3(f), 8(d), 21; HB26 ¶20):
- There is no claim form and no loss adjustment; RMA computes the payment and the AIP processes it.
- Payment is due within 60 days after RMA publishes the final index, and interest runs from day 61.
- Premium and fees owed are deducted from the payment, even before the premium billing date.

### 8. Premium, subsidy, fees and dates

```
total premium per unit      = PP × premium_rate[grid, interval, coverage]      (BP27 §11(c), p.14)
subsidy per unit            = total premium × subsidy_rate[coverage]          (ADM A00070; + BFR/VFR points)
producer premium            = total premium − subsidy
producer cost               = Σ producer premium + $30 administrative fee      (USC1508 (c)(10)(A); BP27 §11(e))
```

**How premium rates vary.** We saw this directly in the DST and ADM:
- Rates vary **by grid and interval**, and rise with **coverage level**. At grid 15429, Apr-May costs 0.0725 per $ of protection at 70% coverage and 0.1581 at 90%.
- Rates are **identical for grazing and haying**, and for every haying practice, within a grid. The dollar premium differs only because the CBV differs.
- Across our 14 study grids at 90% coverage, rates run from **0.0470** (Hardee FL, Jul-Aug, the reliable summer wet season) to **0.2985** (Torrance NM, Apr-May, the dry spring).
- The rancher pays rate × (1 − subsidy). At 90% coverage Apr-May in Parker County that is 0.1581 × 0.49 = 0.0775 per $ of protection (DERIVED).

**Premium subsidy** (ADM A00070, record category 04, plan 13; identical in 2025, 2026 and 2027):

| Coverage | 70% | 75% | 80% | 85% | 90% |
|---|---|---|---|---|---|
| Subsidy (share of premium paid by FCIC) | 59% | 59% | 55% | 55% | 51% |

- These match the statute's area-yield schedule (7 U.S.C. 1508(e)(7): 59% for 70-<80%, 55% for 80-<90%, 51% for 90%).
- The DST returns the same "SubsidyLevel."
- **OBBBA (enacted 2025-07-04)** reached PRF through the 25-OBBA amendment to the Rainfall Index Basic Provisions. That amendment changed only the **beginning farmer or rancher (BFR)** rules:
  - BFR status now lasts up to 10 crop years;
  - extra subsidy is +15 points in years 1-2, +13 in year 3, +11 in year 4, +10 in years 5-10 (BP27 §11(g), p.15; MGR-25-006).
- Veterans get +10 points (BP27 §11(g)(2)). The 2026 subsidy records were re-released on 2025-08-21, right after OBBBA, with the same 59/55/51.
- **No change to PRF's base subsidy** (CONFIRMED).

**Administrative fee:** $30 per crop per county (USC1508 (c)(10)(A); BP27 §11(e)).
- It is waived for beginning, veteran and limited-resource farmers, and not owed if a zero-acre report is filed.
- Grazing and haying are the same crop (PRF), so one fee covers both in a county.

**Other premium rules:**
- Premium is earned when the acreage is reported and billed no earlier than the premium billing date (CP27 §7; BP27 §11(a)).
- Unpaid amounts accrue 1.25% simple interest per month (BP27 §20).
- If premium plus fee would exceed liability on some acres, those acres are not insured (BP27 §11(f)).
- Third-party "premium funding" deals void the indemnity (BP27 §11(i), new in 27.1-RI).

**Program dates, 2027 crop year.** These come from ADM A00200, where all 232,184 PRF date records are identical:

| Date | Value | Meaning |
|---|---|---|
| Contract change | Aug 31 (2026-08-31 for 2027 rules) | RMA publishes rules, rates and CBVs for the next crop year |
| Sales closing | 2026-12-01 | last day to apply or change coverage, intervals and allocation |
| Acreage reporting | 2026-12-01 | acres, grid, use and practice reported; leases due |
| Cancellation | 2026-12-01 | policy renews automatically unless cancelled |
| Insurance period | 2027-01-01 to 2027-12-31 | coverage attaches |
| Premium billing | 2027-09-01 | earliest premium bill |
| Termination | 2027-12-01 | unpaid premium ends coverage for the next year |

### 9. Worked example 1: grazing, Parker County TX, grid 15429 (2027 offer)

Inputs:
- Real 2027 values from the DST, checked against the ADM: CBV $27.60, 90% rates 0.1581 (Apr-May) and 0.1929 (Jul-Aug), subsidy 51%.
- Hypothetical final indices: 62 for Apr-May, 105 for Jul-Aug.
- 500 acres, 100% share, productivity factor 100%, coverage 90%, Apr-May 50% and Jul-Aug 50%.

**Table 9.1**

| Step | Formula | Apr-May (628) | Jul-Aug (631) | Total |
|---|---|---|---|---|
| 1. Protection per acre | 27.60 × 0.90 × 1.00 | $24.84 | $24.84 | |
| 2. Unit protection | 24.84 × 500 × 0.50 × 1.00 | 6,210.00 → **$6,210** | 6,210.00 → **$6,210** | **$12,420** |
| 3. Premium rate (90%) | ADM/DST | 0.1581 | 0.1929 | |
| 4. Total premium | PP × rate | 981.801 → **$982** | 1,197.909 → **$1,198** | **$2,180** |
| 5. Subsidy (51%) | premium × 0.51 | 500.82 → **$501** | 610.98 → **$611** | **$1,112** |
| 6. Producer premium | premium − subsidy | **$481** | **$587** | **$1,068** |
| 7. + administrative fee | | | | $30 → **$1,098** out of pocket |
| 8. Trigger | 100 × 0.90 | 90.0 | 90.0 | |
| 9. Final index (hypothetical) | | 62.0 | 105.0 | |
| 10. Payment factor | (90 − I)/90 | 28/90 = 0.31111… → **0.311** | 105 ≥ 90 → **0** | |
| 11. Indemnity, official | 0.311 × 6,210 | 1,931.31 → **$1,931** | **$0** | **$1,931** |
| 11b. Indemnity, DST rule | 0.31111… × 6,210 | 1,932.00 → **$1,932** | $0 | $1,932 |
| 12. Net to rancher | indemnity − producer premium − fee | | | 1,931 − 1,068 − 30 = **$833** (DST: $834) |

Notes:
- Per acre: $24.84 of protection, $4.36 total premium, $2.136 paid by the rancher.
- Steps 2-6 equal what the DST returned for these inputs on 2026-10-29.
- Each Apr-May index point below 90 is worth 6,210 / 90 = $69.00. The 1951-2025 Apr-May mean is 203.094 mm, so one index point is 2.03 mm. The payout slope is therefore about **$34 per mm, or $863 per inch**, of grid-average rain shortfall (DERIVED).
- With this allocation, the Apr-May unit alone repays the whole $1,098 cost once the index is at or below 90 × (1 − 1,098/6,210) = **74.1**.

### 10. Worked example 2: haying (non-irrigated, conventional), Parker County TX, grid 15429 (2027 offer)

Inputs:
- Real 2027 values: CBV $181.00 for non-irrigated hay, 90% rates 0.1740 (Mar-Apr) and 0.1590 (May-Jun), subsidy 51%.
- Hypothetical final indices: 105 for Mar-Apr, 62 for May-Jun.
- 500 acres, 100% share, productivity factor 100%, coverage 90%, Mar-Apr 50% and May-Jun 50%. The two intervals are adjacent but do not overlap.

**Table 10.1**

| Step | Formula | Mar-Apr (627) | May-Jun (629) | Total |
|---|---|---|---|---|
| 1. Protection per acre | 181.00 × 0.90 × 1.00 | $162.90 | $162.90 | |
| 2. Unit protection | 162.90 × 500 × 0.50 | 40,725.00 → **$40,725** | **$40,725** | **$81,450** |
| 3. Premium rate (90%) | ADM/DST | 0.1740 | 0.1590 | |
| 4. Total premium | PP × rate | 7,086.15 → **$7,086** | 6,475.275 → **$6,475** | **$13,561** |
| 5. Subsidy (51%) | premium × 0.51 | 3,613.86 → **$3,614** | 3,302.25 → **$3,302** | **$6,916** |
| 6. Producer premium | | **$3,472** | **$3,173** | **$6,645** |
| 7. + administrative fee | | | | $30 → **$6,675** |
| 8. Trigger | | 90.0 | 90.0 | |
| 9. Final index (hypothetical) | | 105.0 | 62.0 | |
| 10. Payment factor | | **0** | 0.31111… → **0.311** | |
| 11. Indemnity, official | 0.311 × 40,725 | **$0** | 12,665.475 → **$12,665** | **$12,665** |
| 11b. Indemnity, DST rule | 0.31111… × 40,725 | $0 | 12,670.00 → **$12,670** | $12,670 |
| 12. Net to rancher | | | | 12,665 − 6,645 − 30 = **$5,990** (DST: $5,995) |

Notes:
- Per acre: $162.90 of protection, $27.12 total premium, $13.29 paid by the rancher.
- Hay protection per acre is 6.6 times grazing protection in the same grid, because the CBV is higher. The premium rates are the same.
- Steps 2-6 match the DST.
- Break-even May-Jun index: 90 × (1 − 6,675/40,725) = **75.25**.

### 11. Cross-checks against RMA's own calculations

- **Handbook Exhibit 5** (HB26 pp.50-57; illustrative values: CBV $20.00, 90%, productivity 120%, 60/40 split over four grids):
  - Our formulas reproduce every unit protection ($1,296 … $3,175 / $2,117), every unit premium ($130 … $233), the total premium $1,114, subsidy $568 and producer premium $546.
  - The scenario totals $167, $1,332 and $1,705 come out using the 3-decimal factor. The YAML records the two handbook quirks: subsidy on the total, and one line using unrounded protection.
- **DST oracle cases** (YAML `dst_oracle_a` … `_d`): every protection, premium, subsidy, producer premium and indemnity the DST returned is reproduced by the DST rounding rules.
- **ADM payment factors**: 3,000 of 3,000 sampled Jun-Jul 2026 offers are reproduced by `round_half_up((T − I)/T, 3)`.
- **The project calculator `src/agri_hedge/prf.py`** was written by the calculator workstream; we ran it read-only on 2026-10-29. It agrees with every vector in the YAML:
  - both worked examples, the four DST oracle cases, and handbook Exhibit 5 (subsidy $568, producer premium $546, scenario-3 indemnity $1,705);
  - in its "official" and "dst" modes, with zero disagreements in indemnities or totals.
- The one convention difference is per-unit subsidy. `prf.py`'s official mode keeps unit subsidy unrounded ($500.82, $610.98) and rounds once on the policy total, as the handbook does. The tables above round each unit ($501, $611). Totals are identical in every case.
- DST oracle cases B-D allocate 60-70% to one interval in a Texas grid. That is above Texas's 50% cap; the DST pricing API does not enforce caps. Those cases test arithmetic only, so run them with validation turned off.
- Note for the calculator owner: `prf.py` documents the 2025-2026 caps. In 2027, Jan-Feb is capped at 25% (California 50%) and 17 states allow 70%.

### 12. Limitations: what PRF does not do

1. **No adjustment for actual loss.** "There are no loss adjustment activities" (HB26 ¶20, p.8). A rancher can lose forage and get nothing, or get paid with no loss (BP27 §13; HB26 ¶34B).
2. **Single peril.** PRF pays only on below-normal rain in the chosen intervals. It is not drought, heat, wind, fire, flood or hail insurance, and a drought declaration does not trigger it (HB26 ¶¶31, 34A).
3. **Basis risk**, in three layers:
   - the grid average vs the rain that fell on the ranch. A grid is about 250 square miles, interpolated from stations that may lie outside it (HB26 ¶33A);
   - the rain vs actual forage growth: timing within the interval, temperature, soil moisture carried over from earlier months, and the fact that each interval is scored independently;
   - CPC vs NCEI from 2027 (§6).
4. **Relative to the grid's own normal.** The index measures departure from the grid's own 1951-2025 average. A chronically dry place gets no extra protection. One very wet month can mask one very dry month within an interval.
5. **Allocation is the hedge decision.**
   - Total protection is fixed by CBV × coverage × productivity × acres. The only choice is how to spread it over intervals, between 10% and the cap, with no overlaps.
   - Each interval is effectively a put option with its own price (rate × (1 − subsidy)). Loading 50-70% on one interval buys a concentrated hedge of that period; spreading buys smaller payouts more often.
   - The choice is locked on Dec 1 for the whole next year and cannot respond to forecasts. Premium is owed even if the lease ends (HB26 ¶21).
   - The productivity factor (up to 150%) lets a rancher insure more than the county value, so protection is not tied to the ranch's real exposure.

## Implications for our replication design

1. **Target payoff.** For each (grid, interval) unit, PRF pays `PP × max(0, T − I)/T`. That is a put option on a two-month grid-average rainfall index, with strike T, payout slope PP/T per index point, and a cap of PP. Kalshi's monthly "above X inches" binary ladders can approximate such a put as a step function of **station** monthly rainfall. To compare in dollars, convert index points to mm with the grid's interval mean: 1 point = mean/100 mm, e.g. 2.03 mm for grid 15429 Apr-May.
2. **Two months, two contracts.** A PRF interval sums two calendar months, while Kalshi settles each month separately. The replica needs a two-month portfolio, and the payoff is non-linear in the sum. Kalshi settles on one airport station (CLI/TWC); PRF uses a 0.25° grid average. Both basis layers should be measured: the station grid against the station, and the farm grid against the station.
3. **Use the right history.** For "what PRF actually paid" before 2027, use ADM payment factors or the Actuarial Information Browser (CPC era), **not** the DST history, which is now NCEI-recomputed. For forward-looking 2027+ contracts, use NCEI nClimGrid (`ncei.noaa.gov/pub/data/cirs/usda/monthly/final`). The weather-data workstream should note that the two differ a lot by grid.
4. **Compare costs correctly.** Benchmark Kalshi hedge cost against both the PRF **total** premium (the actuarial price) and the **producer** premium (after 49-59% subsidy plus the $30 fee). The subsidy roughly halves the rancher's PRF cost, an advantage an unsubsidized Kalshi replica cannot match.
5. **Timing and flexibility.**
   - PRF locks choices 13 months ahead (Dec 1) and pays about 2-4 months after an interval ends: 62-68 days to publication in 2026, plus up to 60 days to payment.
   - Kalshi can be traded month by month and settles days after the month ends.
   - Both differences belong in the comparison.
6. **Calculator spec.** `src/agri_hedge/prf.py` already implements the formulas with "official" and "dst" rounding modes, and it matches every vector in `prf_rules.yaml` (§11). Those vectors can serve directly as pytest cases. The allocation validator should use the 2027 caps: ≥ 2 intervals; whole percents summing to 100; ≥ 10% each; ≤ the state cap (50/60/70%; 25% for Jan-Feb, 50% in California); no shared months.
7. **IDs for joining.** Interval codes are 625-635. The grid ID is the ADM "Sub County Code." Commodity 0088 and plan 13. Grid IDs for all 16 study points are in §3, and the formula is in the YAML.

## Unverified claims and open questions

- **That AIPs pay with the published 3-decimal factor** (UNVERIFIED, inferred). The ADM publishes it at 3 decimals, and the handbook computes with 3-decimal factors, but we have not seen an actual indemnity statement. The handbook also uses unrounded protection in one line, so whether protection is rounded before multiplying is ambiguous. Our examples avoid this because their protections are whole dollars.
- **CPC vs NCEI gap size.** Our 49-grid sample includes only grids that paid under CPC in one interval (Jun-Jul 2026), which biases the mean difference upward. A proper comparison would use RMA's crop-year-2026 bulk index file (CPC, 1948-2024 basis, at https://pubfs-rma.fpac.usda.gov/pub/Miscellaneous_Files/VI_RI_Data/index.html) against NCEI history for all grids and intervals. This is suggested for the weather-data / basis-risk workstream.
- **Release timing under NCEI.** RMA says it will be faster, but no 2027 interval has been finalized yet. NCEI's schedule suggests finals about 5-6 weeks after an interval ends (UNVERIFIED inference).
- **How RMA sets county base values and premium rates.** We did not review the rating methodology. Why irrigated hay CBV ($118) is below non-irrigated ($181) in Parker County is unexplained, although both the ADM and the DST show it.
- **Special Provisions text.** We used the ADM fields that feed the Special Provisions (dates, caps, CBVs) rather than a rendered Special Provisions PDF. The 2026 Jan-Feb cap (before the new 25% rule) was not checked.
- **"Approximately 17 by 17 miles"** is RMA's fact-sheet wording. Our own computation shows the east-west width is smaller away from the equator (14.5 miles in North Texas).
- **Hawaii** (5 km grids, HCDP data, productivity factor up to 120%) is outside scope and not described here.
- **Preliminary indices under CPC.** We found no primary source describing whether the DST showed preliminary current-year values before finals in the CPC era. On 2026-10-29 it showed only published finals.

## Sources

Local copies are under `data/raw/rma_docs/` (gitignored; re-downloadable from the URLs).

- **[BP27]** FCIC. *Rainfall Index Plan Common Policy, Basic Provisions (27.1-RI)*, released August 2026. https://www.rma.usda.gov/sites/default/files/2026-08/Rainfall%20Index%20Plan%20Common%20Policy%2027.1-Ri.pdf
- **[CP27]** FCIC. *Rainfall Index Pasture, Rangeland, Forage (PRF) Crop Provisions (27-RI-PRF)*, released August 2026. https://www.rma.usda.gov/sites/default/files/2026-09/rainfall-index-pasture-rangeland-forage-crop-provisions-27-ri-prf.pdf
- **[HB26]** FCIC. *Rainfall Index Insurance Standards Handbook, FCIC-18150 (08-2025)*, 2026 and succeeding crop years, issued 2025-08-29. https://www.rma.usda.gov/sites/default/files/2025-08/2026-18150-Rainfall-Index-Handbook.pdf
- **[HB27]** FCIC. *Rainfall Index Insurance Standards Handbook, FCIC-18150-1 (08-2026)*, 2027 and succeeding crop years, issued 2026-08-31. https://www.rma.usda.gov/sites/default/files/2026-08/Rainfall%20Index%20Insurance%20Standards%20Handbook%202027-18150.pdf
- **[PM26053]** RMA. *PM-26-053: Rainfall Index Crop Insurance Policy Changes Effective for the 2027 and Succeeding Crop Years*, 2026-09-08. https://www.rma.usda.gov/policy-procedure/bulletins-memos/product-management-bulletin/pm-26-053-rainfall-index-crop
- **[PM_FINALS]** RMA final-grid-index bulletins:
  - PM-26-015 (2026-03-05): https://www.rma.usda.gov/policy-procedure/bulletins-memos/product-management-bulletin/pm-26-015-25-cy-rainfall-index-nov-dec
  - PM-26-039 (2026-07-07): https://www.rma.usda.gov/policy-procedure/bulletins-memos/product-management-bulletin/pm-26-039-2026-crop-year-rainfall
  - PM-26-044 (2026-08-03): https://www.rma.usda.gov/policy-procedure/bulletins-memos/product-management-bulletin/pm-26-044-2026-crop-year-rainfall
  - PM-26-050 (2026-09-01): https://www.rma.usda.gov/policy-procedure/bulletins-memos/product-management-bulletin/pm-26-050-2026-crop-year-rainfall
  - PM-26-063 (2026-10-01): https://www.rma.usda.gov/policy-procedure/bulletins-memos/product-management-bulletin/pm-26-063-2026-crop-year-rainfall
  - Issue dates are from RMA's bulletin listing pages.
- **[RIDATA27]** RMA. *Rainfall Index Data - 2027 and Beyond Rainfall Index Processing* (posted 2026-06). https://www.rma.usda.gov/sites/default/files/2026-06/Rainfall%20Indexa%20Data%202027%20and%20Beyond%20Rainfall%20Index%20Processing.pdf
- **[NEWS0430]** RMA. *USDA Risk Management Agency Upgrades Rainfall Data Source*, news release, 2026-04-30. https://www.rma.usda.gov/news-events/news/2026/washington-dc/usda-risk-management-agency-upgrades-rainfall-data-source
- **[NCEI_GUIDE]** NOAA NCEI. *USDA Gridded Data - Consumer Guide*, updated 2026-03-26 (Readme.docx), and monthly files: https://www.ncei.noaa.gov/pub/data/cirs/usda/ (served from https://www.ncei.noaa.gov/monitoring-content/data/us/usda/monthly/final/)
- **[ADM27]** RMA. *Actuarial Data Master, 2027* (2027_ADM_Filing_0831.zip; 2027_ADM_YTD.zip), records A00030, A00070, A00200, A00420, A00460, A00470, A00480, A00490, A00500, A00810. https://pubfs-rma.fpac.usda.gov/pub/References/actuarial_data_master/2027/ . Also 2025 and 2026 A00070 from the corresponding YTD zips.
- **[ADM_LAYOUT]** RMA. *ADM Record Layout for 2027* (AdmLayout.pdf, as of 2026-05-31). https://pubfs-rma.fpac.usda.gov/pub/References/actuarial_data_master/2027/AdmLayout.zip
- **[ADM26D]** RMA. *2026_ADM_Daily_261001.zip*, record A01130 (Jun-Jul 2026 payment factors), joined to 2026 A00030 (YTD). https://pubfs-rma.fpac.usda.gov/pub/References/actuarial_data_master/2026/
- **[DST]** RMA. *PRF Decision Support Tool* (commodity year 2027), https://public-rma.fpac.usda.gov/apps/PRF . Public API at https://public-rma.fpac.usda.gov/apps/PrfWebApi/ , queried 2026-10-29:
  - `PrfExternalPricingRates/GetPricingRates`, with parameters intervalType=BiMonthly, intendedUseCode 007/030, irrigationPracticeCode 997/002/003, organicPracticeCode 997/001/002, stateCode, countyCode, gridId, gridName, productivityFactor (percent, e.g. 100), coverageLevelPercent (e.g. 90), insuredAcres, insurableInterest (percent), sampleYear, and intervalPercentOfValues as a JSON array of 11 percents;
  - `PrfExternalMaxAcrePercentage/GetMaxAcrePercentage`;
  - `PrfExternalIntervalCodes/GetValidIntervalCodes`;
  - `PrfExternalIndexes/GetIndexValues`;
  - `PrfExternalStates/GetCountiesAndStatesFromGridId`.
- **[GRID_LAYER]** RMA. PRF grid feature layer `PRF/PRF_GRID/MapServer/0` (field GRIDCODE), queried via https://public-rma.fpac.usda.gov/apps/prf/proxy/proxy.ashx?https://pdgis.rm.usda.net/arcgis/rest/services/PRF/PRF_GRID/MapServer/0/query?geometry=LON,LAT&geometryType=esriGeometryPoint&inSR=4326&outFields=GRIDCODE&returnGeometry=true&f=json
- **[OBBA]** FCIC. *25-OBBA One Big Beautiful Amendment*, released August 2025. https://www.rma.usda.gov/sites/default/files/2025-09/25-OBBA-One-Big-Beautiful-Amendment.pdf
- **[MGR25006]** RMA. *MGR-25-006: One Big Beautiful Bill Act Amendment*, 2025-08-20. https://www.rma.usda.gov/policy-procedure/bulletins-memos/managers-bulletin/mgr-25-006-one-big-beautiful-bill-act-amendment
- **[USC1508]** 7 U.S.C. § 1508 (Federal Crop Insurance Act § 508), subsections (b)(5)(A), (c)(10)(A), (e)(7). https://www.law.cornell.edu/uscode/text/7/1508
- **[FACTSHEET]** RMA. *Pasture, Rangeland, Forage Pilot Insurance Program* fact sheet, September 2025. https://www.rma.usda.gov/sites/default/files/2024-02/Pasture-Rangeland-Forage-Pilot-Insurance-Program-Fact-Sheet.pdf
- RMA. *Rainfall Index* policy page (current document links). https://www.rma.usda.gov/policy-procedure/general-policies/rainfall-index
- RMA. *Summary Overview of Rainfall Index Insurance plan for PRF* (CPC-era background). https://www.rma.usda.gov/sites/default/files/2024-05/risummary.pdf

## Fact-check log

Independent fact-check run 2026-11-01 (branch `run/factcheck-2`) against primary sources. Summary and downstream impact: [11_fact_check_summary.md](../analysis/11_fact_check_summary.md). "Confirmed" means the checker re-read the number in the named source on 2026-11-01. "Unverifiable" means the checker could not open or parse the source with the tools available; it does not mean the number is wrong.

| Claim in this doc | Source checked (2026-11-01) | Verdict |
|---|---|---|
| PRF is RMA's "only rainfall-index insurance" (§1) | RMA Summary of Business `sobcov_2025.zip`, plan 13 (Rainfall Index) liability by commodity: PRF 0088 $6,547.0M, Annual Forage 0332 $1,222.1M, Apiculture 1191 $461.8M, masked 9999 $432.7M (found by `run/factcheck-1`; re-summed by the reviewer on 2026-11-01) | **corrected** in §1: PRF is the largest Rainfall Index product, not the only one. The overview repeats the error ("USDA's only rainfall-index policy") |
| Premium subsidy 59% (70-75% coverage), 55% (80-85%), 51% (90%) | 7 U.S.C. 1508(e)(7), Cornell LII text: tiers 70-<80% = 59%, 80-<90% = 55%, ≥90% = 51% | confirmed |
| Administrative fee $30 per crop per county; CAT fee $655 | 7 U.S.C. 1508(c)(10)(A) and (b)(5)(A) | confirmed |
| Beginning farmer extra subsidy +15 / +13 / +11 / +10 points | 7 U.S.C. 1508(e)(8) (+10 points) plus (e)(9)(B)(i) (+5 in years 1-2, +3 in year 3, +1 in year 4) | confirmed |
| Beginning farmer = up to 10 crop years | 7 U.S.C. 1502 not opened | unverifiable (not re-checked) |
| Jan-Feb capped at 25% of value from 2027; grazing needs livestock ≥ 25% of an average stocking rate; records kept 3 years; PM-26-053 dated 2026-09-08 | PM-26-053 web page | confirmed |
| California keeps 50% Jan-Feb cap | PM-26-053 states no exception; the claim rests on ADM27 A00810, which was not downloaded | unverifiable (flagged in the numbers table) |
| PRF switches from CPC to NCEI data on 2026-08-31 (crop year 2027); "overall loss ratios remain nearly identical" | RMA news release 2026-04-30 | confirmed |
| NCEI-era baseline 1951 to CY−2 (2027: 1951-2025); final index rounded to 3 decimals; CPC era started 1948 | RMA "Rainfall Index Data - 2027 and Beyond" PDF (text extracted) | confirmed |
| CPC analysis released on a 0.25° grid | CPC "Conceptual Description of the CPC Gauge Analysis Procedure" (2021), sec. 1 | confirmed |
| Handbook Exhibit 5 inputs and outputs (protection 10,692; premium 1,114; indemnities 167 / 1,332 / 1,705) | HB26 PDF downloaded; Exhibit 5 tables could not be extracted (no PDF renderer available). The repo's unit tests reproduce these values from `prf_rules.yaml`, but that is not an independent read | unverifiable |
| State caps (11 states at 50%, 21 at 60%, 17 at 70%), study-grid premium rates, county base values, 3,000/3,000 payment-factor fit, CPC vs NCEI gap on 49 grids | ADM27 / ADM26 daily files and the DST API were not re-pulled (DST API returned empty bodies to a plain request) | unverifiable (not re-checked) |

No number in this doc was changed; one sentence in §1 was corrected (PRF is not RMA's only rainfall-index product). No change to `prf_rules.yaml`.
