# How rain changes restaurant seated diners (OpenTable)

Purpose: an empirical rain-loss number for the restaurant segment of the wet-side demand model. Every number here comes from `scripts/run_rain_reservations.py` (run 2026-11-19, about 45 s once cached).

**Headline.** Using OpenTable's current dashboard (Sept 2025 to Nov 2026, 46 US cities), a day with at least 0.10 in of rain at the city's airport cuts that day's seated diners by about **4.4% (95% CI 3.3-5.5%)**. That is about **$220 for a restaurant with $1.8M a year in sales (CI $164-275)**, or $122 per $1M of annual sales. Rain during dinner hurts more: **6.5% (CI 4.6-8.3%)** when at least 0.10 in falls between about 5 and 9 pm. Rain only at other hours costs 3.3%. The loss is concentrated in Nov-Apr: 7.1% then, versus 2.3% in May-Oct. Much of the winter effect comes from snow and ice days (28%); cold liquid rain costs 3.6%. The live sample shows no rebound over the following week. The 2020-23 DB.nomics series gives a similar same-day effect, 5.5% (CI 4.7-6.3%). Over 1991-2025 rain, rain-day losses average **0.8% of monthly diners** across the 46 cities. City-month means run up to 2.9%, and the 95th-percentile month reaches 4% in Boston. That is about **$14k a year** for a $1.8M restaurant (median across cities; range $3k-30k).

Files:
- `data/processed/rain_reservations_effects.csv` (E): one row per sample × spec × group × era. Columns `effect_pct`, `ci95_lo_pct`, `ci95_hi_pct`, `se`, `se_date`, `se_city`, `n`. The `spec=dollars` rows add `usd_per_day_*`.
- `data/processed/rain_reservations_city_month_loss.csv` (L): 46 cities × 12 months.
- `data/processed/rain_reservations_base_test.csv` (B): which comparison day the series uses.
- `docs/figures/rain_reservations_effects.png`.

Citation shorthand used below: E[sample, spec, group, era]. The samples are `live` = `live_2025_26` and `db` = `dbnomics_2020_23`. The eras are t = "reservation day", b = "comparison day" and c = "combined". Unless a different column is named, the value is `effect_pct` with its 95% CI.

## 1. Data

| Item | Primary: `live_2025_26` | Secondary: `dbnomics_2020_23` |
|---|---|---|
| Source | OpenTable State of the Industry dashboard, saved by hand on 2026-11-19 to `data/raw/opentable/opentable_soti_20261119.json` (the endpoint blocks scripts) | Same OpenTable series mirrored on DB.nomics (`OpenTable/SRI`), cached at `data/raw/opentable/all_series_obs.json` |
| Measure | YoY % change in seated diners from **online reservations only** (methodology changed June 2024) | % change in seated diners from online, phone **and walk-in** |
| Dates | 2025-09-01 to 2026-11-17; 18,324 city-days used (E[live, wet010, …, `n`]) | 2020-07-01 to 2023-02-10; 36,059 city-days used (E[db, wet010, …, `n`]) |
| Comparison day | Same day of the same week a year earlier, t-364 (OpenTable's stated method; confirmed in B) | Moves by year; see section 2 |
| Cities | 46 US cities, identical in both samples | |

Weather comes from each city's main airport, a first-order station. Daily data are from ACIS StnData (`pcpn`, `maxt`), 1991-2026. Hourly data are from IEM ASOS `p01i` in local time and cover 2018-12 to 2023-02 and 2024-08 to 2026-11. Kalshi settlement stations are used where they exist: NYC = Central Park, Houston = Hobby, Dallas = DFW, Chicago = O'Hare. Other mappings:

| City | Station |
|---|---|
| Brooklyn | JFK |
| Beverly Hills | LAX |
| Cambridge | BOS |
| Miami Beach | MIA |
| Boca Raton | FLL |
| Scottsdale | SDL |
| Naples | APF |

The daily ≥ 0.10 in flag computed from hourly totals agrees with ACIS daily on 98.9% of station-days (correlation 0.976, script log). Dinner rain is the sum of hourly buckets ending 17:5x-20:5x local, which covers roughly 4:50-8:50 pm.

## 2. Method

- **Outcome.** y = log(1 + value/100) = log diners(t) − log diners(base). Rain on day t should lower y. Rain on the comparison day lowers that day's diners and so should *raise* y. Minus the base-day coefficient is therefore a second, independent estimate of the rain effect, measured in the comparison year.
- **Which comparison day.** B regresses y on rain at t and at several candidate lags. Only the true base day carries a significant positive coefficient:

  | Sample, year | Base day | Coefficient (t-stat) | Other candidate lags |
  |---|---|---|---|
  | live 2026 | t-364 | +0.053 (t = 4.7) | t-357, t-371, t-728 all \|t\| < 0.6 |
  | live 2025 | t-364 | +0.071 (t = 2.5) | |
  | db 2020 | t-364 (2019) | t = 4.4 | |
  | db 2021 | t-728 (2019) | t = 7.5 | |
  | db 2022 | t-1092 (2019) | t = 8.2 | |
  | db Jan-Feb 2023 | t-1092 (Jan-Feb 2020) | t = 2.7 | see note |

  For the Jan-Feb 2023 rows, t-1456 (2019) is also positive (t = 2.9). t-1092 was chosen because 2023-02-10 drops 34% in the US series, which matches a comparison against Valentine's Friday 2020 (t-1092). OpenTable's documentation for 2023 was not found. Dropping 2023 leaves the result unchanged (E[db, robust_drop_2023]).
- **Regression.** y on rain indicators at t and at the base day, plus daily max-temperature bins (< 32, 32-45, …, ≥ 95 F) at both days. Days where t or the base day is a holiday are dropped: New Year, Valentine's ±1, Super Bowl, Easter, Mother's and Father's Day, July 4, Halloween, Thanksgiving ±1, Dec 20-Jan 3, and others.
- **Fixed effects.** Live: city × month plus city × weekday × year, as requested. DB.nomics: city × week plus city × weekday × year, because COVID reopening moved levels within a month. Each sample is also run with the other FE set.
- **Standard errors.** Two-way clustered by date and city, or date-clustered when that is larger (always the case for per-city terms).
- **Combined estimate.** "Combined" is the GLS average of the reservation-day and comparison-day estimates, using their covariance.
- **City effects.** Per-city effects are shrunk toward the pooled mean by empirical Bayes (`effect_pct_shrunk`).

## 3. Headline effects (≥ 0.10 in of airport rain)

| Estimate | Live 2025-26 (primary) | DB.nomics 2020-23 |
|---|---|---|
| Rain on the reservation day (t) | −3.6% (−5.1, −2.2) | −6.1% (−7.0, −5.2) |
| Rain on the comparison day (minus sign) | −5.6% (−7.4, −3.8), year 2024-25 | −4.7% (−5.7, −3.8), year 2019-20 |
| **Combined** | **−4.4% (−5.5, −3.3)** | **−5.5% (−6.3, −4.7)** |
| Restricted (one coefficient on rain_t − rain_base) | −4.6% (−5.7, −3.5) | −5.4% (−6.2, −4.6) |
| Any rain ≥ 0.01 in, combined | −3.3% (−4.2, −2.4) | −4.4% (−5.1, −3.7) |

Sources: E[·, wet010, rain >= 0.10 in, t/b/c]; E[·, wet010_restricted]; E[·, any001, rain >= 0.01 in, c].

**Best single number:** −4.4%, with a range of −3.3% to −6.3% across both samples' CIs. In the live data the reservation-day and comparison-day estimates overlap, and the 2020-23 series is about 1 point larger. COVID-era diners were more weather-sensitive (outdoor-only dining). The 2020H2-2021H1 reservation-day effect is −8.4% to −8.8% (E[db, by_period, 2020H2/2021H1, t]); by 2022H2 it is −4.7%.

**Intensity** (combined; E[·, bins, *, c]):

| Rain at the airport | Live | DB.nomics |
|---|---|---|
| 0.01-0.10 in | −1.2% (−1.9, −0.6) | −2.1% |
| 0.10-0.50 in | −3.6% (−4.8, −2.5) | −4.8% |
| ≥ 0.50 in | −6.3% (−7.9, −4.6) | −7.5% |

**Robustness** (live, combined):

| Variant | Effect | Source |
|---|---|---|
| City × week FE | −4.7% | E[live, robust_city_week_fe] |
| Drop cities that share an airport | −4.6% | E[live, robust_unique_stations] |
| Keep holidays | −4.1% | E[live, robust_keep_holidays] |
| Last 12 months only | −4.1% | E[live, robust_last_12_months] |
| No base-day controls (reservation day only) | −3.5% | E[live, robust_no_base_controls] |

DB.nomics variants range from −4.8% to −5.5% (E[db, robust_*]).

## 4. Dinner-hour rain (the contract a restaurant would want)

Categories are mutually exclusive; the reference is no rain. Combined effects, live first (E[·, dinner, *, c]):

| Rain pattern | Live | DB.nomics |
|---|---|---|
| Dinner rain ≥ 0.10 in | **−6.5% (−8.3, −4.6)** | −7.8% (−8.9, −6.6) |
| Dinner rain 0.01-0.10 in | −3.6% (−5.0, −2.1) | −5.2% |
| No dinner rain, ≥ 0.10 in at other hours | −3.3% (−4.5, −2.1) | −4.3% |
| No dinner rain, 0.01-0.10 in at other hours | −1.0% (−1.8, −0.2) | −1.7% |

Holding the daily total fixed, any rain during dinner subtracts another 2.2% (CI 1.1-3.4%) in the live data and 2.9% in DB.nomics (E[·, dinner_vs_day, any dinner rain, c]).

Rain at dinner costs about twice as much as the same amount at other hours. A contract that settles on rain in a 5-9 pm window fits restaurant losses better than one on the daily total. Kalshi lists only monthly and daily station totals, so such a window would be a new product.

## 5. Heterogeneity (live combined, then DB.nomics combined)

**Season** (E[·, by_warm]; E[·, by_season_x_freezing]; E[·, by_freezing]):

| Condition | Live | DB.nomics |
|---|---|---|
| Nov-Apr | −7.1% (−9.4, −4.8) | −6.8% |
| May-Oct | −2.3% (−3.2, −1.3) | −4.5% |
| Nov-Apr, max temp ≥ 40 F | −3.6% (−4.9, −2.3) | −4.6% |
| Max temp < 40 F (snow or ice likely) | −28% (−36, −18) | −16% (−19, −13) |

The winter gap is mostly snow and ice. ACIS "precipitation" includes melted snow, so a rain-total contract pays on snow days too. Once freezing days are removed, cold liquid rain (−3.6%) and warm-season rain (−2.3%) are close. There is no sign that patio-season rain hurts more. The live freezing estimate is imprecise because few such days fall in the sample.

**Weekend versus weekday** (E[·, by_weekend]):

| Days | Live | DB.nomics |
|---|---|---|
| Fri-Sun | −4.5% (−6.3, −2.7) | −5.6% |
| Mon-Thu | −4.1% (−5.2, −2.9) | −5.3% |

There is no meaningful difference.

**Region** (E[·, by_region]; E[·, by_sunbelt]):

| Region | Live | DB.nomics |
|---|---|---|
| Northeast | −6.8% (−8.5, −5.0) | −7.2% |
| Midwest | −5.2% | −5.4% |
| Texas and Southwest | −5.2% | −3.5% |
| Denver | −4.2% | −7.2% |
| West Coast | −2.4% | −2.1% |
| Southeast | −1.4% (−2.7, −0.1) | −4.7% |
| Sun Belt, all | −3.0% (−4.3, −1.6) | −4.5% |
| Not Sun Belt | −5.4% (−6.7, −4.0) | −6.1% |

Where rain is frequent and showery (Florida, the Southeast, the Pacific Northwest), each rainy day costs less. This matches the retail adaptation result in `hospitality_venues.md`, where losses are about 80% smaller where heavy rain is common.

**Cities** (E[live, by_city, *, c]; columns `effect_pct` and `effect_pct_shrunk`):
- The between-city SD is about 2 log points (`tau_between` = 0.02).
- Largest shrunk effects: Brooklyn −6.1%, Boston −5.9%, New York −5.5%, Philadelphia −5.3%, Milwaukee −5.2%.
- Smallest: Miami −1.1%, Boca Raton −1.4%, Fort Lauderdale −1.6%, Miami Beach −1.7%, Portland −2.0%, Atlanta −2.0%.
- Single-city CIs are wide (about ±3 points). Use the shrunk values.

**Rebound** (E[·, rebound_month, *]: six daily lags of rain, city × month FE):

| Sample and era | Same-day effect | Net 7-day effect |
|---|---|---|
| Live, reservation year | −3.7% | −4.2% (−8.0, −0.2) |
| Live, comparison year | −5.4% | −8.5% (−12.8, −3.9) |
| DB.nomics, 2020-23 | −5.8% | −5.8% (no rebound) |
| DB.nomics, 2019 comparison year | −3.6% | 0.0% (−2.7, +2.8), full rebound |
| DB.nomics, 2019, city × week FE | −4.6% | −3.0%, about 35% recovered (E[db, rebound_week]) |

In the live data the lagged coefficients are small and mostly negative, so lost diners are not made up later in the week. The loss file's `rebound_ratio` is therefore 1.00: net loss equals gross. Only the 2019 comparison year shows a rebound.

**Conclusion:** treat rainy-day losses as mostly lost, not shifted, with the net effect 50-100% of the gross. Use 100% (the live estimate) as central and the DB.nomics ratio of 0.50 as a low case.

## 6. Dollars

Assumption: a typical full-service restaurant has **$1.80M a year in sales**, matching `data/processed/demand_inputs.csv` ("Full-service sales per establishment", low 1.0, high 2.3). That figure is BLS sectoral output for NAICS 722511 ($475.1B, 2023) divided by QCEW establishments (264,208, 2024). Cross-checks: Census full-service restaurant sales summed over 2019 were $314.2B (FRED SM722511USN). A secondary source gives $381.8B across 257,282 establishments, or $1.48M each (data.mewayz.com, year unstated, unverified). OpenTable restaurants skew larger than average.

Daily sales = annual / 360 open days, and lost sales = effect × daily sales. Values are E[·, dollars, `usd_per_day_typical` with `_ci_lo`/`_ci_hi`; `usd_per_day_per_1m_sales`]:

| Rain day | Live, $ per day (95% CI) | Live, per $1M sales | DB.nomics, $ per day |
|---|---|---|---|
| ≥ 0.10 in | **$219 ($164-275)** | $122 | $274 ($235-313) |
| ≥ 0.01 in | $164 | $91 | $218 |
| ≥ 0.50 in | $314 ($230-397) | $175 | $373 |
| Dinner rain ≥ 0.10 in | **$323 ($231-414)** | $180 | $389 |
| ≥ 0.10 in, none at dinner | $164 | $91 | $213 |

These are lost **sales**. At the 0.65 contribution margin in `demand_inputs.csv` (an assumption), the profit loss on a ≥ 0.10 in day is about $140.

## 7. Monthly loss distribution (for the demand model)

**Construction.** For each city's airport and each day of 1991-2025, the day loses 1 − exp(b) of its diners. Here b is the live combined effect for that day's rain bin and season (E[live, bins_x_season, *, c]). These are averaged over each month; months missing more than 2 days are dropped (23-35 years per city-month, L `n_years`). Rain is independent of weekday, so days are weighted equally. Main columns:

| Column | Meaning |
|---|---|
| `pct_lost_*` | Pooled effects |
| `pct_lost_city_*` | Rescaled by the city's shrunk effect (`city_scale`) |
| `pct_lost_mean_ci_lo/hi` | Rescaled by the 95% CI of the headline effect (×0.75 / ×1.25) |
| `pct_lost_net_*` | Times `rebound_ratio` (1.00 here) |
| `pct_lost_mean_dbnomics` | Same calculation with the 2020-23 effects |
| `usd_lost_*` | At $1.8M a year |

**Across all 552 city-months** (L, column means):

| Measure | Mean | Median | Max |
|---|---|---|---|
| Rainy days (≥ 0.10 in) per month | 5.3 | | |
| 95th-percentile month, rainy days (`wet_days_p95`) | 9.1 | | 21.6 |
| % of monthly diners lost, pooled (`pct_lost_mean`) | 1.02% | | |
| % lost, city-adjusted (`pct_lost_city_mean`) | 0.82% | 0.61% | 2.85% |
| % lost in the 95th-percentile month, city-adjusted (`pct_lost_city_p95`) | 1.35% | | 4.0% |
| Typical restaurant, $ per month, city-adjusted (`usd_lost_city_mean`) | $1,231 | | |
| Same, 95th-percentile month (`usd_lost_city_p95`) | $2,024 | | |

With the 2020-23 effects the mean is 1.28% instead of 1.02% (`pct_lost_mean_dbnomics`). Expected loss runs about three times higher in Nov-Apr (1.49%) than in May-Oct (0.54%).

**Annual**, summing `usd_lost_city_mean` over 12 months per city:

| Measure | Value |
|---|---|
| Median city | $13.8k (0.77% of sales) |
| Mean | $14.8k |
| Lowest | Tucson $3.1k, Las Vegas $3.7k, Phoenix $4.6k |
| Highest | Boston $30.5k, Brooklyn $30.2k, New York $28.5k (1.6-1.7% of sales) |

**Example city-months** (L):

| City, month | Mean rainy days (sd; p95) | % lost, mean | % lost, p95 month | $ mean / $ p95 |
|---|---|---|---|---|
| New York, Dec | 7.4 (2.2; 11) | 2.62 | 3.67 | $4,012 / $5,611 |
| New York, Jul | 7.0 (2.6; 10.3) | 0.85 | 1.33 | $1,300 / $2,027 |
| Boston, Mar | 7.0 (2.5; 11) | 2.65 | 4.03 | $4,052 / $6,168 |
| Chicago, Apr | 7.1 (2.6; 10) | 1.86 | 2.73 | $2,748 / $4,036 |
| Seattle, Nov | 13.0 (4.0; 19.3) | 1.95 | 2.96 | $2,886 / $4,383 |
| Los Angeles, Jan | 4.3 (3.4; 10.6) | 1.13 | 2.72 | $1,725 / $4,160 |
| Houston, Jun | 7.1 (3.0; 11.3) | 0.62 | 1.10 | $912 / $1,622 |
| Miami, Aug | 13.3 (3.1; 17.6) | 0.34 | 0.45 | $517 / $680 |
| Phoenix, Jul | 1.9 (1.6; 5.3) | 0.16 | 0.34 | $245 / $522 |

The monthly loss is small and fairly stable. Within a city-month, the SD of % lost averages 0.41 points (`pct_lost_sd`), so even a bad month costs a restaurant 1-4% of sales. The per-day hit is larger and concentrated: 4-6% of a day's diners, and 6-9% on a wet dinner or heavy-rain day. This supports a daily or dinner-window trigger over a monthly-total contract.

## 8. Caveats

- **Sample.** The live data cover only 14.5 months: one winter and one summer for the reservation-day estimate, plus the 2024-25 comparison year. The DB.nomics series is COVID-era. The two agree within about 1 point, and the live estimate is primary. The live series counts **online reservations only**; walk-ins, often more weather-sensitive, are excluded, so the live number may understate total-diner losses. The 2020-23 series includes walk-ins but has COVID dynamics.
- **Who is in the data.** OpenTable skews to full-service, reservation-taking, often upscale restaurants. Limited-service, takeout and patio-only bars are not measured. Delivery may offset part of the dine-in loss for the restaurant, but not in these data.
- **Comparison day.** The live base (t-364) is documented by OpenTable and confirmed in B. For the DB.nomics series the base is inferred from the data; Jan-Feb 2023 is ambiguous, and dropping it changes nothing.
- **Airport versus city rain.** One airport gauge per city, often 10-20 miles from the restaurants, gives classical measurement error. That error biases effects toward zero, so true neighborhood-rain effects are likely somewhat larger. The same gauge would settle a contract, so these are the right effects for station-settled basis risk.
- **Snow.** Precipitation totals include melted snow, and freezing days drive much of the winter effect (section 5). A rain-only contract would need a temperature or precipitation-type condition.
- **Dollars.** Revenue per establishment is an assumption (range $1.0-2.3M). Losses are in sales, not profit. Average check is assumed unaffected by rain.
- **Holidays and outliers.** Holidays are dropped. City-days below −85% are dropped (log transform). The dashboard is not adjusted for events or tourism, and city × month FE plus clustering absorb only part of that noise.
- **Loss distribution.** It uses pooled bin × season effects (or city-shrunk scaling), equal day weights and no rebound. Hourly dinner rain is not used for 1991-2025, because the long hourly record was not pulled.
- **Note on `yoy_open`.** OpenTable's "open restaurants only" NYC series (2020-23) shows smaller effects than the main NYC series: −2.7% versus −6.4% (E[db, nyc_yoy_open / nyc_yoy, c]). This holds even for the 2019 comparison-day estimate, so it is not just closures. That series' construction is undocumented here; it is not used elsewhere.

## Reproduce

```bash
.venv/bin/python scripts/run_rain_reservations.py            # first run: ~170 ACIS/IEM requests
.venv/bin/python scripts/run_rain_reservations.py --offline  # from caches, ~45 s
```

Raw caches are gitignored:
- `data/raw/opentable/` (the live JSON must be saved by hand)
- `data/raw/stations/acis_reservations/`
- `data/raw/stations/iem_asos_reservations/`
