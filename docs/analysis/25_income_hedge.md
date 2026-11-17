# 25: Insurance that steadies income: Kalshi hedges fit to row-crop revenue instead of an index payout

**Proposal cell:** Milestone III direction (the farmer's objective is stable income, not a copy of PRF; extends the row-crop exploration of doc 14 and the utility view of doc 24 to corn, soybeans, winter wheat, cotton and sorghum). Owner: Evan  |  **Status:** DRAFT (numbers reproducible with `python scripts/run_income_hedge.py`, about 15 minutes with downloads, 3 minutes from the cache; `--tables-only` redoes the tables from the saved CSVs; not yet independently reviewed)  |  **Last updated:** 2026-11-13

Code: `scripts/run_income_hedge.py` (downloads, site selection, payoff builders, the long-only ridge fit, leave-one-year-out scoring, utility sizing, tables).
Data written: `data/processed/m2_income_hedge_sites.csv` (one row per site and design), `m2_income_hedge_legs.csv` (the fitted tickets), `m2_income_hedge_drivers.csv` (weather-yield correlations), `m2_income_hedge_years.csv` (the yearly shortfalls), `m2_income_daily_high_depth_20261113T203120Z.csv` (a live snapshot of Kalshi daily-high order books). Raw downloads are cached in `data/raw/income/` (gitignored).

## Why this doc

Every hedge so far was fit to copy an insurance payout: PRF's, or a PRF-style rain index. But a farmer does not want a copy of PRF. They want income that is roughly the same every year. Write farm revenue as expected revenue times (1 - L), where L is the year's shortfall. Then the variance of income plus hedge is Var(L - hedge). So the right target is the farm's own shortfall, and the right score is the familiar hedge effectiveness with L in place of the PRF payout. This doc fits Kalshi contracts to that target directly, for the five main field crops, and asks three questions:

1. Does designing for income beat copying an index?
2. Which weather contracts matter for which crop?
3. Is the result worth buying at Kalshi's prices and fillable on its books?

## Key findings

"Income HE" is the share of the year-to-year variance of the farm's revenue that a hedge removes, scored on years the fit never saw (leave one year out). Medians over 128 county sites within 60 miles of a Kalshi rain station, 1971-2025.

- **Copying a rain index steadies income very little.** Kalshi contracts fit to copy a PRF-style payout on the county's own rain (design B, today's approach) remove a median 4% of income variance: 8% for corn, 9% for soybeans, 0% for wheat. Even a perfect rain-index policy on the county itself (design A) removes only 17% (corn 26%, soybeans 30%, wheat and sorghum 0%). A rain index is a weak proxy for crop income before Kalshi's basis risk is added.
- **Fitting straight to income only works with structure.** Letting the fit pick freely among about 40 strike contracts overfits: median income HE 0.03 on unseen years. A "per-inch" design does better at 80 of 128 sites. It pays a fixed amount per whole inch a month's rain falls below normal, which is exactly one NO contract at each whole-inch strike. But on the airport's rain alone it still removes almost nothing (0.01), because airport rain explains little of county yields: median correlation 0.26 for corn, against 0.36 for the county's own rain.
- **Heat is the missing piece for corn, and Kalshi already lists it.** Kalshi's daily high-temperature markets let a hedger build "pay $X per day the high reaches 95°F" by buying one YES each day. At the 26 corn sites with such a market within 60 miles, adding hot-day counts to the per-inch rain design (D2) lifts median income HE from 0.04 to 0.27; 17 of 26 sites improve. Around Chicago (O'Hare rain, Midway heat) the hedge goes from about 0 to 0.27-0.46. In the Mid-Atlantic it reaches 0.27-0.46 at 8 of 9 sites, and near Dallas and Houston 0.15-0.39. Corn yields move more with the peak-month daily high (median correlation -0.48) than with season rain (+0.36). It does not work in Minnesota or for Denver's mostly irrigated corn.
- **Contracts on the county's own weather would do far better (a proposal).** The same per-inch design settled on NOAA's county rain and county mean daily high (E2) removes a median 40% of corn income variance, 26% for soybeans and 21% across all sites. It beats the perfect rain index at 37 of 49 corn sites (median +0.11) and recovers 87% of corn's shortfall in the five worst years, against 30% for copying the index. Distance to an airport stops mattering, because the contract settles where the farm is.
- **Wheat, sorghum and cotton income is mostly not weather-index risk.** Wheat's rain risk is real but points in opposite directions by region, and it is small next to everything else.
  - In the East (16 sites), wet years hurt. Wheat falls 6.7% short of trend on average in the wettest fifth of seasons (previous Sep-Nov plus Mar-May), and 48% of the years more than 20% short fall in that fifth. Dry years help: the driest fifth comes in 5% above trend, likely because there is less disease at flowering, and even the driest seasons there had at least 13 inches. The median correlation of yield with season rain is -0.33.
  - In the Plains (11 sites), drought hurts: wheat falls 14% short in the driest 5% of seasons.
  - Both directions are in the designs: dry-side contracts on every growing month and wet-side contracts on May-Jun. A single contract on wet seasons alone, or one paying on both tails, still removes a median 0-4% out of sample. A wet fifth that averages 6.7% short, against a standard deviation of 13%, caps what a perfect wet-year payout could explain at about 7% of the variance even in sample (in-sample quadratic R² in season rain: median 0.12). Out of sample, estimation noise takes most of that. The rest is disease, freeze and hail. One in three of the wettest eastern seasons was still above trend.
  - Plains wheat near Oklahoma City and Denver reaches 0.10-0.25 with a perfect county rain index, and 0.04-0.18 with today's contracts. Cotton reaches 0.13 with county contracts and sorghum 0.04.
- **At Kalshi's markup, a typical farmer would buy little.** We size each hedge to maximize a risk-averse farmer's certainty-equivalent income: CRRA 2, a wealth buffer of one year's revenue, and a premium of 1.12 times the expected payout. On that basis the median gain is 0.5% of revenue for corn county contracts, 0.4% for the perfect index, and about 0 for anything tradable today. A thin-margin farm (buffer 0.4 years of revenue) gains 3.4% of revenue from county contracts, 1.9% from the perfect index, 0.2% from D2 and 0.1% from copying the index.
- **It still works as a top-up to crop insurance.** A 75% yield policy cuts corn's revenue swings from 16% to 13% of expected revenue (standard deviation). County contracts still remove 35% of what is left and D2 10%. The hedge's natural job is the layer under the insurance deductible.
- **Two execution problems decide feasibility.**
  - Depth: one heat strike needs a median 7,700 contracts a day per 1,000 acres of corn. On 2026-11-14 the daily-high books held a median 700-1,300 YES contracts within 10 cents per strike at the deeper cities, and 139 at Trenton. A rain strike needs about 25,000 per 1,000 acres, against the 245-374 on the Chicago rain book (doc 14).
  - Timing: daily-high markets are listed a day or two ahead, and monthly rain about a month ahead, so a farmer cannot lock in July heat cover in April. Bought late, the price already reflects the forecast.
- **What this means for the product.** Design to the farm's income, not to an index. Use per-inch rain plus hot-day counts. Aim it at corn, and at soybeans in the Mid-Atlantic, near stations that have both markets: Chicago, Philadelphia, Trenton, Washington, Dallas, Houston, Austin and San Antonio. The contract changes to ask Kalshi for are seasonal hot-day-count contracts listed before planting, and county-settled rain and heat indices. Together they would lift corn's median income HE from 0.09 with today's contracts (0.27 where a heat market exists) to 0.40, and remove the distance limit.

## Results

<!-- BEGIN AUTO: income hedge tables (scripts/run_income_hedge.py) -->
### 1. How much of the farm's income swing each design removes (median income HE, unseen years)

Income HE = 1 - Var(L - hedge) / Var(L), L = revenue shortfall per $1 of expected revenue; each year scored with a fit that never saw it. A-E as in Method. D2 is shown only where Kalshi lists a daily-high market within 60 miles, next to C2 on the same sites.

| Crop | Sites | A | B | C | C2 | D2 (heat sites) | C2 same sites | Heat sites | E | E2 |
|---|---|---|---|---|---|---|---|---|---|---|
| corn | 49 | 0.26 | 0.08 | 0.05 | 0.06 | 0.27 | 0.04 | 26 | 0.26 | 0.40 |
| soybeans | 33 | 0.30 | 0.09 | 0.04 | 0.03 | 0.10 | 0.02 | 13 | 0.19 | 0.26 |
| winter wheat | 27 | 0.00 | 0.00 | -0.04 | -0.02 | 0.04 | -0.01 | 14 | -0.02 | 0.00 |
| cotton | 7 | 0.05 | 0.02 | -0.02 | -0.01 | 0.04 | -0.00 | 5 | 0.15 | 0.13 |
| sorghum | 12 | -0.03 | -0.01 | 0.01 | -0.01 | 0.03 | -0.01 | 11 | 0.00 | 0.04 |
| all | 128 | 0.17 | 0.04 | 0.03 | 0.01 | 0.09 | -0.00 | 69 | 0.14 | 0.21 |

### 2. Head to head, site by site

| Crop | Sites | best tradable (C2/D2) beats copying (B) | median gain over B | heat helps (D2 > C2), heat sites | per-inch beats free (C2 > C) | county per-inch beats index (E2 > A) | median E2 - A |
|---|---|---|---|---|---|---|---|
| corn | 49 | 30 of 49 | 0.02 | 17 of 26 | 33 of 49 | 37 of 49 | 0.11 |
| soybeans | 33 | 16 of 33 | -0.00 | 12 of 13 | 19 of 33 | 17 of 33 | 0.01 |
| winter wheat | 27 | 8 of 27 | -0.02 | 11 of 14 | 18 of 27 | 10 of 27 | -0.01 |
| cotton | 7 | 3 of 7 | -0.01 | 4 of 5 | 5 of 7 | 6 of 7 | 0.07 |
| sorghum | 12 | 10 of 12 | 0.04 | 6 of 11 | 5 of 12 | 10 of 12 | 0.07 |
| all | 128 | 67 of 128 | 0.01 | 50 of 69 | 80 of 128 | 80 of 128 | 0.04 |

### 2b. By region (median income HE)

| Crop | Region | Sites | A | B | best tradable (C2/D2) | D2 (heat sites) | Heat sites | E2 |
|---|---|---|---|---|---|---|---|---|
| corn | Corn Belt and Lakes | 25 | 0.31 | 0.06 | 0.07 | 0.12 | 6 | 0.46 |
| corn | Mid-Atlantic | 12 | 0.35 | 0.15 | 0.33 | 0.36 | 9 | 0.35 |
| corn | Plains and Texas | 12 | 0.12 | 0.05 | 0.21 | 0.15 | 11 | 0.31 |
| soybeans | Corn Belt and Lakes | 24 | 0.27 | 0.09 | 0.03 | 0.00 | 6 | 0.20 |
| soybeans | Mid-Atlantic | 9 | 0.38 | 0.14 | 0.10 | 0.10 | 7 | 0.28 |
| winter wheat | Corn Belt and Lakes | 12 | 0.00 | 0.00 | -0.03 |  | 0 | -0.01 |
| winter wheat | Mid-Atlantic | 4 | 0.00 | 0.00 | -0.03 | -0.03 | 4 | -0.02 |
| winter wheat | Plains and Texas | 11 | 0.10 | 0.02 | 0.09 | 0.09 | 10 | 0.07 |
| cotton | Plains and Texas | 7 | 0.05 | 0.02 | -0.00 | 0.04 | 5 | 0.13 |
| sorghum | Plains and Texas | 12 | -0.03 | -0.01 | 0.03 | 0.03 | 11 | 0.04 |

### 3. Bad years, cost, and what a risk-averse farmer gains (medians)

Worst-5-year recovery = held-out payout in the 5 worst years / shortfall in those years. CE gain = certainty-equivalent income with the hedge minus without, CRRA risk aversion 2, wealth buffer of one year's revenue, premium = 1.12 x the expected payout (doc 14 central Kalshi cost). 'Utility size' scales each hedge (0 to 1.5 x) to maximise the farmer's CE on the training years. 'Thin margin' repeats it with a wealth buffer of 0.4 x revenue.

| Crop | Design | income HE | worst-5-year recovery | premium, % of revenue | CE gain at 12% load, variance size, % rev | utility size: buys in % of years | utility size: premium % rev | CE gain at 12% load, utility size, % rev | thin margin: buys in % of years | thin margin: CE gain, % rev |
|---|---|---|---|---|---|---|---|---|---|---|
| corn | A: index insurance on county rain | 0.26 | 0.48 | 5.55 | 0.28 | 100.00 | 3.89 | 0.39 | 100.00 | 1.90 |
| corn | B: Kalshi copies the index | 0.08 | 0.30 | 5.87 | -0.13 | 100.00 | 3.72 | 0.00 | 100.00 | 0.08 |
| corn | D2: station rain + heat, per-inch | 0.09 | 0.42 | 11.45 | -0.21 | 100.00 | 5.41 | 0.00 | 100.00 | 0.16 |
| corn | E2: county contracts, per-inch | 0.40 | 0.87 | 13.04 | 0.37 | 100.00 | 8.14 | 0.54 | 100.00 | 3.38 |
| soybeans | A: index insurance on county rain | 0.30 | 0.55 | 4.47 | 0.08 | 100.00 | 2.45 | 0.17 | 100.00 | 1.71 |
| soybeans | B: Kalshi copies the index | 0.09 | 0.30 | 4.83 | -0.23 | 92.59 | 0.43 | 0.00 | 100.00 | 0.17 |
| soybeans | D2: station rain + heat, per-inch | 0.06 | 0.31 | 6.89 | -0.45 | 39.62 | 0.14 | 0.00 | 100.00 | 0.27 |
| soybeans | E2: county contracts, per-inch | 0.26 | 0.66 | 8.85 | -0.43 | 100.00 | 3.12 | -0.00 | 100.00 | 1.50 |
| winter wheat | A: index insurance on county rain | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| winter wheat | B: Kalshi copies the index | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| winter wheat | D2: station rain + heat, per-inch | -0.01 | 0.04 | 1.43 | -0.13 | 2.13 | 0.01 | 0.00 | 98.15 | -0.18 |
| winter wheat | E2: county contracts, per-inch | 0.00 | 0.07 | 1.74 | -0.18 | 97.96 | 1.00 | 0.00 | 100.00 | -0.16 |
| cotton | A: index insurance on county rain | 0.05 | 0.23 | 6.16 | -0.55 | 0.00 | 0.00 | 0.00 | 98.15 | -0.47 |
| cotton | B: Kalshi copies the index | 0.02 | 0.25 | 6.33 | -0.45 | 0.00 | 0.00 | 0.00 | 100.00 | -0.17 |
| cotton | D2: station rain + heat, per-inch | -0.01 | 0.25 | 4.44 | -0.15 | 100.00 | 1.97 | 0.00 | 100.00 | -0.18 |
| cotton | E2: county contracts, per-inch | 0.13 | 0.39 | 8.19 | -0.19 | 100.00 | 3.51 | 0.03 | 100.00 | 0.96 |
| sorghum | A: index insurance on county rain | -0.03 | 0.00 | 0.33 | -0.12 | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| sorghum | B: Kalshi copies the index | -0.01 | 0.00 | 0.35 | -0.04 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| sorghum | D2: station rain + heat, per-inch | 0.02 | 0.15 | 4.91 | -0.20 | 100.00 | 3.24 | 0.00 | 100.00 | -0.64 |
| sorghum | E2: county contracts, per-inch | 0.04 | 0.23 | 4.91 | -0.10 | 100.00 | 3.96 | -0.09 | 100.00 | -0.81 |
| all | A: index insurance on county rain | 0.17 | 0.36 | 4.56 | 0.00 | 100.00 | 2.34 | 0.04 | 100.00 | 0.41 |
| all | B: Kalshi copies the index | 0.04 | 0.25 | 4.87 | -0.13 | 73.91 | 0.35 | 0.00 | 100.00 | 0.00 |
| all | D2: station rain + heat, per-inch | 0.05 | 0.27 | 6.17 | -0.29 | 98.11 | 1.81 | 0.00 | 100.00 | 0.00 |
| all | E2: county contracts, per-inch | 0.21 | 0.55 | 9.61 | -0.17 | 100.00 | 4.11 | 0.00 | 100.00 | 1.05 |

### 4. As a top-up to 75% yield insurance (county-yield proxy)

Target = min(L, 0.25): what a 75% yield-protection policy leaves the farmer (the deductible layer). sd in % of expected revenue.

| Crop | A HE on what insurance leaves | A CE gain utility size, % rev | D2 HE on what insurance leaves | D2 CE gain utility size, % rev | E2 HE on what insurance leaves | E2 CE gain utility size, % rev | sd of shortfall, no insurance | sd left by 75% yield insurance |
|---|---|---|---|---|---|---|---|---|
| corn | 0.22 | 0.10 | 0.10 | 0.00 | 0.35 | 0.06 | 16.16 | 13.01 |
| soybeans | 0.31 | 0.08 | 0.08 | 0.00 | 0.28 | 0.00 | 13.88 | 12.81 |
| winter wheat | 0.00 | 0.00 | -0.01 | 0.00 | 0.00 | 0.00 | 17.19 | 16.80 |
| cotton | 0.05 | 0.00 | -0.00 | 0.00 | 0.13 | 0.07 | 28.53 | 24.59 |
| sorghum | -0.02 | 0.00 | 0.01 | 0.00 | 0.01 | -0.01 | 21.63 | 19.21 |
| all | 0.15 | 0.01 | 0.05 | 0.00 | 0.19 | 0.00 | 16.57 | 13.81 |

### 5. What moves yields (median correlation with the yield, over sites)

Season = the crop's rain months (Method). Positive = more of it, higher yield.

| Crop | yield vs station season rain | yield vs county season rain | station vs county rain | yield vs county peak-month daily high | yield vs station hot days (heat sites) |
|---|---|---|---|---|---|
| corn | 0.26 | 0.36 | 0.75 | -0.48 | -0.21 |
| soybeans | 0.26 | 0.33 | 0.76 | -0.38 | -0.16 |
| winter wheat | -0.20 | -0.26 | 0.80 | -0.01 | -0.28 |
| cotton | 0.08 | 0.04 | 0.81 | -0.10 | -0.22 |
| sorghum | 0.20 | 0.15 | 0.82 | -0.01 | -0.24 |

### 6. By distance to the rain station (median income HE, all crops)

| County to rain station | Sites | A | B | C2 | D2 | E2 |
|---|---|---|---|---|---|---|
| 0-30 mi | 18 | 0.13 | 0.08 | 0.04 | 0.09 | 0.17 |
| 30-45 mi | 54 | 0.17 | 0.02 | 0.03 | 0.07 | 0.23 |
| 45-60 mi | 56 | 0.18 | 0.04 | -0.00 | 0.03 | 0.21 |

### 7. What the contract looks like: the best tradable site per crop (fit on all years)

**Corn, Northampton County, PA (station TTN, 42 mi; D2).** Income HE 0.46 on unseen years vs 0.35 for copying the index; expected revenue $736/acre; fair premium $116/acre; contracts 1,089,367 per 1,000 acres.

| Pays | $ per acre per unit | contracts per 1,000 acres | expected payout $/acre |
|---|---|---|---|
| $ per whole inch Jun station rain falls below 4 in (1 NO each at 1, 2, 3, 4 in) | 5.57 | 22,286.49 | 6.60 |
| $ per whole inch Jul station rain falls below 5 in (1 NO each at 1, 2, 3, 4, 5 in) | 33.69 | 168,456.94 | 48.67 |
| $ per whole inch May station rain exceeds 5 in, up to 6 in (1 YES each at 5-10 in) | 10.45 | 62,673.68 | 5.42 |
| $ per Jul day with a daily high of 95F or above (1 YES each day, KXHIGHTTTN) | 11.34 | 351,421.70 | 33.17 |
| $ per Aug day with a daily high of 90F or above (1 YES each day, KXHIGHTTTN) | 1.74 | 53,865.59 | 9.85 |
| $ per Aug day with a daily high of 95F or above (1 YES each day, KXHIGHTTTN) | 13.89 | 430,662.48 | 20.07 |

**Soybeans, Burlington County, NJ (station TTN, 29 mi; D2).** Income HE 0.51 on unseen years vs 0.18 for copying the index; expected revenue $461/acre; fair premium $77/acre; contracts 532,745 per 1,000 acres.

| Pays | $ per acre per unit | contracts per 1,000 acres | expected payout $/acre |
|---|---|---|---|
| $ per whole inch Jul station rain falls below 5 in (1 NO each at 1, 2, 3, 4, 5 in) | 9.44 | 47,183.62 | 13.14 |
| $ per whole inch Aug station rain falls below 4 in (1 NO each at 1, 2, 3, 4 in) | 20.99 | 83,948.76 | 23.24 |
| $ per whole inch Jun station rain exceeds 6 in, up to 6 in (1 YES each at 6-11 in) | 7.83 | 46,967.33 | 3.91 |
| $ per Jul day with a daily high of 90F or above (1 YES each day, KXHIGHTTTN) | 1.02 | 31,541.61 | 9.52 |
| $ per Jul day with a daily high of 95F or above (1 YES each day, KXHIGHTTTN) | 2.44 | 75,671.93 | 6.89 |
| $ per Aug day with a daily high of 90F or above (1 YES each day, KXHIGHTTTN) | 2.64 | 81,802.46 | 14.98 |
| $ per Aug day with a daily high of 95F or above (1 YES each day, KXHIGHTTTN) | 5.34 | 165,629.64 | 7.44 |

**Winter wheat, Blaine County, OK (station OKC, 58 mi; D2).** Income HE 0.18 on unseen years vs 0.14 for copying the index; expected revenue $202/acre; fair premium $25/acre; contracts 209,830 per 1,000 acres.

| Pays | $ per acre per unit | contracts per 1,000 acres | expected payout $/acre |
|---|---|---|---|
| $ per whole inch prev Oct station rain falls below 3 in (1 NO each at 1, 2, 3 in) | 7.62 | 22,868.02 | 7.34 |
| $ per whole inch prev Nov station rain falls below 2 in (1 NO each at 1, 2 in) | 5.38 | 10,764.25 | 5.28 |
| $ per whole inch Mar station rain falls below 2 in (1 NO each at 1, 2 in) | 12.38 | 24,753.01 | 6.19 |
| $ per whole inch Apr station rain falls below 3 in (1 NO each at 1, 2, 3 in) | 4.72 | 14,174.65 | 4.29 |
| $ per Apr day with a daily high of 85F or above (1 YES each day, KXHIGHTOKC) | 2.53 | 75,981.69 | 5.68 |
| $ per Apr day with a daily high of 90F or above (1 YES each day, KXHIGHTOKC) | 1.74 | 52,347.64 | 0.87 |
| $ per May day with a daily high of 85F or above (1 YES each day, KXHIGHTOKC) | 0.29 | 8,940.26 | 2.37 |

**Cotton, Ellis County, TX (station DFW, 40 mi; D2).** Income HE 0.30 on unseen years vs 0.19 for copying the index; expected revenue $528/acre; fair premium $99/acre; contracts 575,399 per 1,000 acres.

| Pays | $ per acre per unit | contracts per 1,000 acres | expected payout $/acre |
|---|---|---|---|
| $ per whole inch Jun station rain falls below 3 in (1 NO each at 1, 2, 3 in) | 5.78 | 17,349.68 | 5.47 |
| $ per whole inch Jul station rain falls below 2 in (1 NO each at 1, 2 in) | 16.86 | 33,728.29 | 15.33 |
| $ per whole inch Aug station rain falls below 2 in (1 NO each at 1, 2 in) | 10.13 | 20,256.45 | 9.02 |
| $ per whole inch Sep station rain falls below 2 in (1 NO each at 1, 2 in) | 8.91 | 17,821.74 | 7.29 |
| $ per whole inch Oct station rain exceeds 6 in, up to 6 in (1 YES each at 6-11 in) | 3.85 | 23,095.20 | 2.59 |
| $ per Jul day with a daily high of 100F or above (1 YES each day, KXHIGHTDAL) | 3.58 | 111,064.45 | 27.42 |
| $ per Jul day with a daily high of 105F or above (1 YES each day, KXHIGHTDAL) | 6.54 | 202,653.89 | 7.96 |
| $ per Aug day with a daily high of 100F or above (1 YES each day, KXHIGHTDAL) | 2.01 | 62,220.79 | 17.92 |
| $ per Aug day with a daily high of 105F or above (1 YES each day, KXHIGHTDAL) | 2.81 | 87,208.47 | 3.89 |

**Sorghum, Caddo County, OK (station OKC, 47 mi; D2).** Income HE 0.27 on unseen years vs 0.01 for copying the index; expected revenue $225/acre; fair premium $27/acre; contracts 200,362 per 1,000 acres.

| Pays | $ per acre per unit | contracts per 1,000 acres | expected payout $/acre |
|---|---|---|---|
| $ per whole inch Jun station rain falls below 4 in (1 NO each at 1, 2, 3, 4 in) | 12.39 | 49,577.90 | 12.95 |
| $ per whole inch Jul station rain falls below 3 in (1 NO each at 1, 2, 3 in) | 1.87 | 5,605.35 | 2.03 |
| $ per Jul day with a daily high of 105F or above (1 YES each day, KXHIGHTOKC) | 2.02 | 62,743.43 | 2.47 |
| $ per Aug day with a daily high of 100F or above (1 YES each day, KXHIGHTOKC) | 2.66 | 82,435.11 | 11.58 |

### 8. The sites

| Crop | County | St | Rain station | mi | Heat station | Years | Harvested acres (2006+ mean) | Revenue $/acre | sd of shortfall % | Worst year | Worst shortfall % |
|---|---|---|---|---|---|---|---|---|---|---|---|
| corn | Williamson County | TX | AUS | 33 | AUS | 52 | 89,315 | 387 | 31 | 2011 | 76 |
| corn | Falls County | TX | CLL | 57 |  | 52 | 65,217 | 447 | 28 | 1990 | 60 |
| corn | Milam County | TX | CLL | 39 | AUS | 51 | 35,368 | 399 | 29 | 2011 | 66 |
| corn | Champaign County | OH | CMH | 48 |  | 55 | 83,600 | 924 | 14 | 2002 | 39 |
| corn | Madison County | OH | CMH | 29 |  | 55 | 89,820 | 937 | 13 | 1981 | 32 |
| corn | Pickaway County | OH | CMH | 25 |  | 55 | 88,305 | 875 | 17 | 1999 | 50 |
| corn | Kent County | MD | DCA | 56 | DCA | 55 | 39,825 | 862 | 21 | 2002 | 46 |
| corn | Queen Anne's County | MD | DCA | 53 | DCA | 52 | 49,412 | 866 | 21 | 1987 | 47 |
| corn | Talbot County | MD | DCA | 47 | DCA | 53 | 30,022 | 789 | 20 | 2002 | 46 |
| corn | Adams County | CO | DEN | 17 | DEN | 53 | 21,213 | 202 | 25 | 2003 | 56 |
| corn | Morgan County | CO | DEN | 53 | DEN | 51 | 44,031 | 792 | 9 | 1995 | 26 |
| corn | Weld County | CO | DEN | 51 | DEN | 54 | 69,989 | 825 | 9 | 2022 | 26 |
| corn | Collin County | TX | DFW | 33 | DFW | 52 | 17,952 | 349 | 34 | 1990 | 71 |
| corn | Ellis County | TX | DFW | 40 | DFW | 55 | 33,565 | 372 | 30 | 1996 | 63 |
| corn | Grayson County | TX | DFW | 54 | DFW | 49 | 17,692 | 340 | 27 | 2006 | 47 |
| corn | Fulton County | OH | DTW | 60 |  | 55 | 76,380 | 917 | 11 | 2012 | 29 |
| corn | Lenawee County | MI | DTW | 45 |  | 55 | 88,805 | 896 | 13 | 1988 | 48 |
| corn | Monroe County | MI | DTW | 23 |  | 55 | 56,165 | 870 | 13 | 2012 | 35 |
| corn | Fort Bend County | TX | HOU | 31 | HOU | 53 | 15,583 | 555 | 27 | 1998 | 64 |
| corn | Clinton County | IN | IND | 41 |  | 54 | 109,495 | 1,038 | 14 | 1974 | 45 |
| corn | Montgomery County | IN | IND | 39 |  | 53 | 117,111 | 1,060 | 14 | 1974 | 43 |
| corn | Rush County | IN | IND | 44 |  | 55 | 105,005 | 984 | 14 | 2012 | 54 |
| corn | Shelby County | KY | LEX | 36 |  | 55 | 17,620 | 899 | 21 | 1983 | 76 |
| corn | Dodge County | WI | MKE | 52 |  | 55 | 119,380 | 953 | 10 | 1988 | 32 |
| corn | Jefferson County | WI | MKE | 44 |  | 54 | 74,921 | 898 | 13 | 1988 | 44 |
| corn | Walworth County | WI | MKE | 38 |  | 55 | 95,170 | 960 | 14 | 1988 | 42 |
| corn | Goodhue County | MN | MSP | 42 | MSP | 55 | 145,370 | 1,005 | 11 | 1993 | 39 |
| corn | McLeod County | MN | MSP | 51 | MSP | 55 | 110,745 | 901 | 15 | 1976 | 47 |
| corn | Sibley County | MN | MSP | 53 | MSP | 55 | 150,645 | 928 | 16 | 1976 | 48 |
| corn | DeKalb County | IL | ORD | 43 | MDW | 54 | 211,474 | 1,055 | 10 | 1974 | 30 |
| corn | Grundy County | IL | ORD | 52 | MDW | 52 | 106,541 | 1,004 | 18 | 1988 | 57 |
| corn | Kankakee County | IL | ORD | 57 | MDW | 52 | 189,800 | 955 | 18 | 1988 | 60 |
| corn | Berks County | PA | PHL | 53 | PHL | 52 | 38,806 | 794 | 18 | 1999 | 60 |
| corn | Kent County | DE | PHL | 56 | PHL | 55 | 52,245 | 913 | 18 | 1971 | 35 |
| corn | Lancaster County | PA | PHL | 55 | PHL | 55 | 69,520 | 960 | 16 | 1999 | 51 |
| corn | Butler County | PA | PIT | 33 |  | 52 | 16,347 | 655 | 14 | 2002 | 40 |
| corn | Columbiana County | OH | PIT | 36 |  | 55 | 19,895 | 771 | 14 | 2002 | 43 |
| corn | Mercer County | PA | PIT | 56 |  | 54 | 29,368 | 745 | 11 | 2002 | 43 |
| corn | Guadalupe County | TX | SAT | 32 | SAT | 54 | 18,990 | 329 | 37 | 2011 | 77 |
| corn | Medina County | TX | SAT | 40 | SAT | 54 | 23,168 | 534 | 13 | 2021 | 28 |
| corn | Barton County | MO | SGF | 55 |  | 54 | 53,316 | 664 | 24 | 1980 | 77 |
| corn | Dade County | MO | SGF | 29 |  | 54 | 15,574 | 578 | 27 | 1980 | 81 |
| corn | Jasper County | MO | SGF | 52 |  | 48 | 26,408 | 563 | 25 | 1980 | 74 |
| corn | Greene County | IL | STL | 42 |  | 55 | 113,050 | 995 | 14 | 1983 | 42 |
| corn | Macoupin County | IL | STL | 43 |  | 55 | 189,390 | 960 | 15 | 1983 | 52 |
| corn | Montgomery County | IL | STL | 58 |  | 54 | 165,721 | 995 | 16 | 2012 | 58 |
| corn | Lehigh County | PA | TTN | 47 | TTN | 28 | 21,065 | 773 | 19 | 2002 | 57 |
| corn | Northampton County | PA | TTN | 42 | TTN | 27 | 23,968 | 736 | 19 | 1999 | 60 |
| corn | Warren County | NJ | TTN | 41 | TTN | 19 | 17,509 | 829 | 24 | 1999 | 82 |
| cotton | Williamson County | TX | AUS | 33 | AUS | 51 | 14,917 | 614 | 25 | 2011 | 60 |
| cotton | Burleson County | TX | CLL | 17 |  | 54 | 11,410 | 754 | 20 | 1978 | 32 |
| cotton | Robertson County | TX | CLL | 31 |  | 48 | 13,493 | 863 | 22 | 2001 | 41 |
| cotton | Ellis County | TX | DFW | 40 | DFW | 55 | 18,795 | 528 | 30 | 1998 | 63 |
| cotton | Fort Bend County | TX | HOU | 31 | HOU | 55 | 32,530 | 679 | 29 | 1998 | 62 |
| cotton | Caddo County | OK | OKC | 47 | OKC | 51 | 16,338 | 1,048 | 30 | 1995 | 59 |
| cotton | Medina County | TX | SAT | 40 | SAT | 48 | 11,388 | 904 | 29 | 1977 | 50 |
| sorghum | Travis County | TX | AUS | 4 | AUS | 46 | 7,596 | 206 | 20 | 1971 | 45 |
| sorghum | Williamson County | TX | AUS | 33 | AUS | 47 | 13,258 | 212 | 19 | 2018 | 41 |
| sorghum | Falls County | TX | CLL | 57 |  | 49 | 5,001 | 316 | 18 | 2009 | 46 |
| sorghum | Milam County | TX | CLL | 39 | AUS | 50 | 7,490 | 315 | 23 | 2011 | 56 |
| sorghum | Collin County | TX | DFW | 33 | DFW | 50 | 8,880 | 282 | 18 | 2006 | 41 |
| sorghum | Denton County | TX | DFW | 22 | DFW | 51 | 7,774 | 180 | 25 | 2011 | 64 |
| sorghum | Ellis County | TX | DFW | 40 | DFW | 50 | 14,437 | 231 | 26 | 2018 | 66 |
| sorghum | Fort Bend County | TX | HOU | 31 | HOU | 53 | 21,906 | 377 | 19 | 2011 | 51 |
| sorghum | Caddo County | OK | OKC | 47 | OKC | 45 | 6,585 | 225 | 20 | 1980 | 51 |
| sorghum | Guadalupe County | TX | SAT | 32 | SAT | 53 | 13,266 | 250 | 26 | 2006 | 61 |
| sorghum | Medina County | TX | SAT | 40 | SAT | 51 | 8,424 | 281 | 24 | 1989 | 52 |
| sorghum | Wilson County | TX | SAT | 35 | SAT | 47 | 5,225 | 358 | 25 | 2006 | 69 |
| soybeans | Fayette County | OH | CMH | 43 |  | 54 | 109,074 | 708 | 13 | 1999 | 46 |
| soybeans | Madison County | OH | CMH | 29 |  | 55 | 121,880 | 710 | 13 | 1999 | 36 |
| soybeans | Pickaway County | OH | CMH | 25 |  | 55 | 114,265 | 654 | 16 | 1999 | 53 |
| soybeans | Kent County | MD | DCA | 56 | DCA | 55 | 42,595 | 661 | 16 | 2007 | 40 |
| soybeans | Queen Anne's County | MD | DCA | 53 | DCA | 53 | 53,589 | 625 | 17 | 2002 | 40 |
| soybeans | Talbot County | MD | DCA | 47 | DCA | 51 | 40,194 | 600 | 17 | 2002 | 48 |
| soybeans | Fulton County | OH | DTW | 60 |  | 54 | 84,026 | 666 | 10 | 2001 | 22 |
| soybeans | Lenawee County | MI | DTW | 45 |  | 55 | 118,565 | 608 | 13 | 2008 | 27 |
| soybeans | Monroe County | MI | DTW | 23 |  | 55 | 77,545 | 581 | 13 | 2001 | 30 |
| soybeans | Clinton County | IN | IND | 41 |  | 54 | 100,174 | 802 | 11 | 1974 | 43 |
| soybeans | Montgomery County | IN | IND | 39 |  | 54 | 114,105 | 808 | 11 | 1974 | 37 |
| soybeans | Rush County | IN | IND | 44 |  | 54 | 101,316 | 758 | 9 | 2012 | 26 |
| soybeans | Dodge County | WI | MKE | 52 |  | 55 | 72,955 | 719 | 14 | 1974 | 32 |
| soybeans | Jefferson County | WI | MKE | 44 |  | 55 | 50,960 | 674 | 14 | 1988 | 39 |
| soybeans | Walworth County | WI | MKE | 38 |  | 53 | 51,778 | 677 | 15 | 2003 | 37 |
| soybeans | Goodhue County | MN | MSP | 42 | MSP | 54 | 91,468 | 715 | 11 | 1974 | 27 |
| soybeans | McLeod County | MN | MSP | 51 | MSP | 55 | 84,005 | 611 | 14 | 2003 | 34 |
| soybeans | Sibley County | MN | MSP | 53 | MSP | 55 | 111,810 | 673 | 13 | 2003 | 33 |
| soybeans | DeKalb County | IL | ORD | 43 | MDW | 54 | 108,463 | 792 | 10 | 2003 | 30 |
| soybeans | Kankakee County | IL | ORD | 57 | MDW | 53 | 125,222 | 722 | 13 | 1988 | 53 |
| soybeans | Will County | IL | ORD | 35 | MDW | 54 | 100,684 | 696 | 13 | 1988 | 34 |
| soybeans | Kent County | DE | PHL | 56 | PHL | 52 | 61,894 | 613 | 16 | 2007 | 36 |
| soybeans | New Castle County | DE | PHL | 30 | PHL | 52 | 22,559 | 595 | 14 | 2002 | 39 |
| soybeans | Salem County | NJ | PHL | 22 | PHL | 54 | 24,210 | 491 | 18 | 2002 | 35 |
| soybeans | Columbiana County | OH | PIT | 36 |  | 54 | 22,320 | 582 | 14 | 1989 | 36 |
| soybeans | Mahoning County | OH | PIT | 47 |  | 53 | 15,522 | 592 | 12 | 2002 | 31 |
| soybeans | Barton County | MO | SGF | 55 |  | 55 | 84,630 | 475 | 22 | 1984 | 54 |
| soybeans | Jasper County | MO | SGF | 52 |  | 53 | 50,844 | 449 | 24 | 1984 | 66 |
| soybeans | St. Clair County | MO | SGF | 59 |  | 51 | 33,581 | 428 | 25 | 1980 | 53 |
| soybeans | Macoupin County | IL | STL | 43 |  | 55 | 151,255 | 824 | 12 | 1983 | 38 |
| soybeans | Montgomery County | IL | STL | 58 |  | 53 | 146,889 | 837 | 12 | 1983 | 30 |
| soybeans | Washington County | IL | STL | 59 |  | 55 | 146,205 | 628 | 18 | 2007 | 50 |
| soybeans | Burlington County | NJ | TTN | 29 | TTN | 28 | 21,110 | 461 | 14 | 2010 | 44 |
| winter wheat | Williamson County | TX | AUS | 33 | AUS | 49 | 10,783 | 277 | 25 | 1971 | 48 |
| winter wheat | Falls County | TX | CLL | 57 |  | 50 | 14,225 | 284 | 18 | 2017 | 40 |
| winter wheat | Crawford County | OH | CMH | 59 |  | 54 | 15,384 | 529 | 10 | 1996 | 38 |
| winter wheat | Pickaway County | OH | CMH | 25 |  | 51 | 13,041 | 514 | 13 | 1996 | 44 |
| winter wheat | Union County | OH | CMH | 33 |  | 53 | 10,057 | 500 | 15 | 1996 | 50 |
| winter wheat | Frederick County | MD | DCA | 47 | DCA | 54 | 15,312 | 468 | 12 | 2003 | 35 |
| winter wheat | Kent County | MD | DCA | 56 | DCA | 52 | 19,747 | 561 | 13 | 2003 | 47 |
| winter wheat | Queen Anne's County | MD | DCA | 53 | DCA | 50 | 23,987 | 491 | 13 | 2003 | 46 |
| winter wheat | Adams County | CO | DEN | 17 | DEN | 49 | 136,788 | 213 | 20 | 2022 | 42 |
| winter wheat | Morgan County | CO | DEN | 53 | DEN | 44 | 50,808 | 222 | 17 | 2002 | 29 |
| winter wheat | Weld County | CO | DEN | 51 | DEN | 47 | 107,493 | 227 | 19 | 1977 | 38 |
| winter wheat | Collin County | TX | DFW | 33 | DFW | 51 | 23,856 | 352 | 21 | 1982 | 43 |
| winter wheat | Ellis County | TX | DFW | 40 | DFW | 54 | 21,174 | 321 | 20 | 1989 | 56 |
| winter wheat | Grayson County | TX | DFW | 54 | DFW | 54 | 24,856 | 326 | 21 | 2009 | 50 |
| winter wheat | Fulton County | OH | DTW | 60 |  | 52 | 15,622 | 556 | 11 | 1982 | 31 |
| winter wheat | Lenawee County | MI | DTW | 45 |  | 54 | 31,584 | 567 | 11 | 1993 | 25 |
| winter wheat | Monroe County | MI | DTW | 23 |  | 54 | 20,842 | 541 | 12 | 1982 | 27 |
| winter wheat | Blaine County | OK | OKC | 58 | OKC | 54 | 133,754 | 202 | 21 | 2011 | 43 |
| winter wheat | Canadian County | OK | OKC | 24 | OKC | 53 | 120,717 | 220 | 19 | 2009 | 45 |
| winter wheat | Kingfisher County | OK | OKC | 43 | OKC | 54 | 158,294 | 230 | 22 | 2014 | 47 |
| winter wheat | Lancaster County | PA | PHL | 55 | PHL | 47 | 12,625 | 584 | 11 | 2003 | 23 |
| winter wheat | Barton County | MO | SGF | 55 |  | 51 | 42,312 | 488 | 19 | 2007 | 46 |
| winter wheat | Dade County | MO | SGF | 29 |  | 54 | 18,683 | 440 | 20 | 2010 | 38 |
| winter wheat | Jasper County | MO | SGF | 52 |  | 53 | 29,433 | 483 | 20 | 2007 | 45 |
| winter wheat | Clinton County | IL | STL | 52 |  | 51 | 33,431 | 508 | 17 | 1991 | 45 |
| winter wheat | Randolph County | IL | STL | 57 |  | 55 | 34,765 | 561 | 14 | 1991 | 43 |
| winter wheat | Washington County | IL | STL | 59 |  | 55 | 57,245 | 552 | 16 | 1991 | 46 |
<!-- END AUTO: income hedge tables (scripts/run_income_hedge.py) -->


## How to read the example tickets

Each row of a ticket in table 7 is one payout rule and the contracts that build it exactly.

- **A dry-month rule.** "$33.69 per acre per whole inch July rain falls below 5 in" is 33.69 NO contracts per acre on each of the 1, 2, 3, 4 and 5-inch strikes of Kalshi's July rain market. If July gets 2.4 inches, the 3, 4 and 5-inch NOs pay, so the hedge pays 3 × $33.69 per acre.
- **A heat rule.** "$11.34 per July day the high reaches 95°F" is 11.34 YES contracts per acre on the 95°F-or-above strike of each day's daily-high market. A July with nine such days pays 9 × $11.34.

The fair premium is the expected payout at climatological odds. The Kalshi price adds spread and fee (about 12%, doc 14). Contract counts are per 1,000 acres and grow in proportion to farm size.

## Method

**Sites.** We take NASS county yields from the survey, all practices, 1971-2025, for corn grain, soybeans, winter wheat, upland cotton and grain sorghum, in 15 states around Kalshi's monthly-rain stations. A county qualifies if its centroid (Census 2024 Gazetteer) is within 60 miles of a station, it has at least 45 years of yields, and its average harvested area since 2006 is at least 15,000 acres (corn, soybeans), 10,000 (wheat, cotton) or 5,000 (sorghum). We keep the three largest counties per crop and station: 128 sites. Midway (MDW) is used only for heat, because Kalshi's Chicago rain series now settles at O'Hare. Arizona cotton is excluded because it is irrigated, so rain cannot explain it.

**Target.** Each county gets a quadratic yield trend over its own record. The shortfall is L = 1 - yield / trend, per $1 of expected revenue at a fixed price. It is positive in bad years and negative in good ones. Dollar figures use the WASDE-676 2026/27 season-average price projections (doc 03b): corn $4.70, soybeans $12.00, wheat $6.30, sorghum $4.50, cotton 77 cents/lb.

**Crop calendars.**

| Crop | Rain months (dry side) | Wet-side months | Heat months | County-index intervals (design A) |
|---|---|---|---|---|
| Corn | May-Aug | May-Jul | Jun-Aug | Jun-Jul |
| Soybeans | Jun-Sep | Jun, Sep | Jul-Aug | Jul-Aug |
| Winter wheat | previous Sep-Nov, Mar-May | May-Jun | Apr-May | previous Oct-Nov, Mar-Apr |
| Cotton | May-Sep | Sep-Oct | Jul-Aug | Jun-Jul, Aug-Sep |
| Sorghum | Jun-Aug | Sep | Jul-Aug | Jul-Aug |

**Designs.** All are scored leave one year out: weights, sizes and the ridge strength are chosen without the scored year.

| Design | Contracts | Fit to |
|---|---|---|
| A | A PRF-style payout, max(0, (90 - I) / 90), on the county's own two-month rain index (NOAA nClimGrid county series) | Sized by beta = argmin Var(L - beta × payout) |
| B | Kalshi NO ladders on the station's months in A's intervals, whole-inch strikes | NNLS to A's payout, then sized like A (today's approach) |
| C | Every whole-inch NO (dry months) and YES (wet months) at the station | L, free long-only ridge |
| C2 | Per-inch features: whole inches below the month's median (one NO at each strike up to it); whole inches above the upper quartile, up to 6 (YES) | L, long-only ridge |
| D, D2 | C or C2 plus hot-day counts from the nearest Kalshi daily-high market within 60 mi, at the two thresholds (85-105°F) with 0.5-12 hot days a month on average | L |
| E, E2 | Proposed county-settled contracts: E = binaries on a half-inch grid and mean-daily-high strikes; E2 = inches below the county median, inches above its upper quartile, °F above the median monthly mean daily high | L |

The fit is non-negative least squares on centred payoffs with a ridge penalty on standardised weights. The ridge strength comes from 5-fold cross-validation inside each training set. Hedges are long-only, so every design is something a farmer can buy.

**Utility sizing.** Each fitted hedge is scaled by 0-1.5 times to maximize mean CRRA utility (risk aversion 2) of W0 - L + s(hedge - 1.12 × premium) on the training years. W0 = 1 (one year's revenue as a buffer), or 0.4 for the thin-margin case. The scale is then applied to the held-out year.

**Insurance layer.** The target becomes min(L, 0.25): what remains after a 75% yield policy that pays max(0, 0.75 - yield / trend). County yield stands in for the farm's yield.

**Hot days.** These are ACIS daily maximum temperatures at each Kalshi daily-high station, using the threaded long record where ACIS has one. Midway's gaps (16 of 56 Julys) are filled from the O'Hare thread. A month needs at least 25 valid days.

**Depth.** On 2026-11-13 (20:31 UTC) we read the public order books for the next day's event of 10 daily-high series. Depth is the YES contracts buyable within 10 cents of the mid, per market and summed over the event's six markets. These are November markets; summer depth is not measured.

## Limits and open questions

- **County, not farm, yields.** A farm's yield has its own noise that no weather index sees, so farm-level HE is lower. If farm and county yields correlate at rho and the extra noise is independent, farm HE is about rho² times county HE: a correlation of 0.7 halves it. This is unverified with farm data. Jack's backtest of real farms is the place to measure it.
- **Fixed price.** Revenue here moves only with yield. National price often rises in short-crop years, a natural hedge for Corn Belt farms, and revenue insurance and futures already cover price. Rain and heat contracts cannot hedge price.
- **Selection.** The example tickets in table 7 are the best tradable site per crop, picked on held-out HE, so they flatter. Medians are the honest summary. Heat thresholds were chosen on full-sample hot-day frequencies, a mild look-ahead in strike placement only.
- **Execution.** Kalshi lists daily-high markets about a day ahead and monthly rain about a month ahead. The per-day heat legs therefore cannot be bought before the season at climatological prices; the study assumes they can. Depth (table above and doc 14) covers a few percent of a farm-sized order on most strikes.
- **Few heat sites in the Corn Belt core.** Indianapolis, Columbus, St. Louis, Detroit, Milwaukee and Springfield have rain markets but no daily-high market. Their corn and soybean sites can only use rain (C2), which removes almost nothing.
- **Trend choice.** A quadratic trend fitted on all years. A different trend changes the year-by-year shortfalls slightly.

## Numbers table

"Computed" = produced by `scripts/run_income_hedge.py` (run 2026-11-13) from the inputs in Method.

| Quantity | Value | Units | Region / period | Source | Verification |
|---|---|---|---|---|---|
| Sites | 128 (corn 49, soybeans 33, winter wheat 27, cotton 7, sorghum 12); 69 with a daily-high market within 60 mi | county-crop | 15 states, 1971-2025 | table 1, `m2_income_hedge_sites.csv` | CONFIRMED (computed) |
| Median income HE, all sites: A / B / C / C2 / E / E2 | 0.17 / 0.04 / 0.03 / 0.01 / 0.14 / 0.21 | share of variance | LOYO | table 1 | CONFIRMED (computed) |
| Median income HE, corn: A / B / E2 | 0.26 / 0.08 / 0.40 | share | 49 sites | table 1 | CONFIRMED (computed) |
| Median income HE, soybeans: A / B / E2 | 0.30 / 0.09 / 0.26 | share | 33 sites | table 1 | CONFIRMED (computed) |
| Corn heat sites: C2 vs D2 | 0.04 vs 0.27; D2 better at 17 of 26 | share | 26 sites | tables 1-2 | CONFIRMED (computed) |
| Chicago corn (Kankakee, DeKalb, Grundy): B / D2 | -0.01-0.08 / 0.27-0.46 | share | ORD rain, MDW heat | site rows, `m2_income_hedge_sites.csv` | CONFIRMED (computed) |
| E2 beats A, corn | 37 of 49, median +0.11 | sites, share | LOYO | table 2 | CONFIRMED (computed) |
| Worst-5-year recovery, corn: B / D2 / E2 | 0.30 / 0.42 / 0.87 | share of shortfall | LOYO | table 3 | CONFIRMED (computed) |
| Median correlation of corn yield with county season rain / station season rain / county peak-month mean daily high | 0.36 / 0.26 / -0.48 | r | 1971-2025 | table 5 | CONFIRMED (computed) |
| Median correlation, winter wheat yield vs county season rain | -0.26 (East -0.33, Plains +0.21) | r | 27 sites (16 East, 11 Plains) | table 5, `m2_income_hedge_drivers.csv` | CONFIRMED (computed) |
| Winter wheat mean shortfall by county season rain (prev Sep-Nov + Mar-May): East wettest 20% / driest 20%; Plains driest 5% / driest 20% | +6.7% / -5.1%; +14.0% / +5.4% | share of trend revenue | pooled site-years 1971-2025 | `m2_income_hedge_years.csv` + NOAA county rain; scratch check 2026-11-13, not in the script | CONFIRMED (computed, ad hoc) |
| East wheat years >20% short that fall in the wettest 20% of seasons | 48% (29 of 61) | share | pooled | same | CONFIRMED (computed, ad hoc) |
| Wheat LOYO HE, single wet-season contract / two-tailed contract (county rain) | East 0.00 / 0.00; Plains 0.00 / 0.04 | share | median | same | CONFIRMED (computed, ad hoc) |
| CE gain at 12% load, utility-sized, corn: A / B / D2 / E2 | 0.39 / 0.00 / 0.00 / 0.54 | % of revenue | CRRA 2, W0 = 1 | table 3 | CONFIRMED (computed) |
| Same, thin margin (W0 = 0.4) | 1.90 / 0.08 / 0.16 / 3.38 | % of revenue | CRRA 2 | table 3 | CONFIRMED (computed) |
| Corn shortfall sd: no insurance / after 75% yield policy | 16.2 / 13.0 | % of expected revenue | median | table 4 | CONFIRMED (computed) |
| HE on the layer insurance leaves, corn: D2 / E2 | 0.10 / 0.35 | share | LOYO | table 4 | CONFIRMED (computed) |
| Median revenue per acre at 2026/27 prices: corn / soybeans / wheat / cotton / sorghum | 866 / 661 / 483 / 754 / 266 | $/acre | 2025 trend yield | `m2_income_hedge_sites.csv` | CONFIRMED (computed) |
| Median fair premium, corn, variance-sized: B / D2 / E2 (utility-sized) | 48 (27) / 81 (36) / 108 (65) | $/acre | | same | CONFIRMED (computed) |
| Contracts needed per strike per 1,000 acres of corn: heat (per day) / rain | 7,730 / 25,178 | contracts | median site | `m2_income_hedge_legs.csv` | CONFIRMED (computed) |
| Daily-high YES depth within 10 cents, per market (median over the event's 6 markets) | CHI 1,293; OKC 792; DAL 919; MIN 695; DEN 726; AUS 839; SATX 197; PHIL 867; TTN 139; DC 973 | contracts | events of 2026-11-14, read 2026-11-13 20:31 UTC | `m2_income_daily_high_depth_20261113T203120Z.csv` | CONFIRMED (snapshot) |
| Chicago monthly-rain book depth | 245-374 contracts at a sensible price | contracts | 2026-10-29 / 11-02 | doc 14 | CONFIRMED (doc 14) |
| Kalshi all-in cost per $1 of expected payout | 1.12 | $ | central case | doc 14 Table 4 | CONFIRMED (doc 14) |
| Season-average price projections 2026/27 | corn 4.70, soybeans 12.00, wheat 6.30, sorghum 4.50 ($/bu); cotton 77.0 cents/lb | | U.S. | WASDE-676 (Oct 9 2026), via doc 03b | CONFIRMED (doc 03b) |
| Farm vs county yield attenuation (HE x rho²) | rho = 0.7 halves HE | | | assumption, not measured | UNVERIFIED |

## Sources

- USDA NASS Quick Stats, county survey yields and harvested acres (keyless CSV export): https://quickstats.nass.usda.gov
- NOAA NCEI Climate at a Glance, county monthly precipitation and maximum temperature (nClimGrid): https://www.ncei.noaa.gov/access/monitoring/climate-at-a-glance/county/time-series
- Applied Climate Information System (ACIS) StnData, daily maximum temperature: https://data.rcc-acis.org
- U.S. Census Bureau, 2024 Gazetteer county file: https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/
- Kalshi public API, daily-high series and order books: https://api.elections.kalshi.com/trade-api/v2
- USDA WASDE-676, October 9 2026 (prices, via doc 03b): https://www.usda.gov/oce/commodity/wasde/wasde1026.pdf
