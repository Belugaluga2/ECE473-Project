# Expansion lenses: lender-book HE, ENSO in Kalshi prices, solar as a wet side

Research date: 2026-11-20. Script: `scripts/run_expansion_lenses.py` (about 130 s; the first run also downloads five small NASA POWER files into `data/raw/nasa_power/`; `--offline` reuses them). Tests: `tests/test_expansion_lenses.py`. Figure: `docs/figures/expansion_lenses.png`. All CSVs named below are in `data/processed/`. Everything here is a backtest of rain-index payouts. None of it measures farm income, real lender losses or real solar revenue.

## Bottom line

1. **Pooling helps a lender, but it has a ceiling.**
   - Treated as one book, the Companion's sample farms reach an out-of-sample HE of 0.83 (equal weight), against 0.61-0.66 for the median single farm.
   - A Farm Credit-style footprint of 40 farms around one station rises from 0.53-0.62 for the median farm to 0.65-0.77, and the gain is mostly reached by 10 farms.
   - Basis errors at one station are not independent. Their mean pairwise correlation is 0.50-0.60, because the station's own departure from the regional rain is common to every farm. That caps the book.
   - Weighting by dollars can erase the gain: in the 2001-2025 holdout, the 11-farm book scores 0.53 because the poorly hedged ABQ farm carries the largest protection.
2. **ENSO pricing in Kalshi cannot be confirmed or ruled out with the saved data.**
   - The only winter of candles, 2025-26, was ENSO-neutral by the report's rule (ASO ONI −0.43).
   - The Nov 2026 book is the only El Niño-season data. In the south-central region, November has almost no El Niño wet-call signal (0.95x climatology); December has 1.89x.
   - Across 34 stations, the market's departure from climatology does not line up with the El Niño-conditional departure: β = −0.22 (90% CI −0.42 to 0.18).
   - The Dec-Feb books, once listed, are the real test.
3. **Solar is a real but weak natural wet side for a Kalshi rain call.**
   - Winter irradiance and rain anomalies correlate at −0.44.
   - A listed Kalshi YES ladder removes only about 9% of a solar plant's Nov-Feb monthly energy variance, out of sample. An irradiance-indexed put would remove 57%, but it is not listed.
   - Paired with a rancher's put, a solar call cuts 95% capital per premium dollar from 3.62 to 1.75. A second, independent put already gets to 1.81, so the opposite side's value again shows up mainly in the worst year (2.00 versus 3.08).

## 1. Lender-portfolio hedge effectiveness

### Method

- **Per farm.** This exactly reproduces doc 21; the per-farm HEs match `m2_companion_holdout.csv` and `m2_companion_farms.csv`.
  - *Holdout:* gap months are picked on 1951-2000 (single-month LOYO HE ≥ 0.5). The package hedge is fit on 1951-2000 at the 95% knee with model prices, then scored on 2001-2025.
  - *LOYO:* months are picked on all years (`platform._score`). The package knee comes from all years, and each year's payout comes from a fit that left that calendar year out.
  - Each farm's target and hedge are kept by month (`loyo_leg_payouts`), so they can be regrouped into calendar years (doc 21's convention) or Jul-Jun seasons (for ENSO).
- **Pooled book.** HE of the sum of farm gap targets against the sum of farm hedge payouts.
  - *Dollar weight* uses each farm's own gap protection (policy protection / 6 per month).
  - *Equal weight* divides each farm by its gap protection.
  - `he_if_uncorrelated` = 1 − ΣVar(eᶠ)/ΣVar(yᶠ) is the pooled HE if no two farms co-moved. The gap above it is what cross-farm correlation adds.
- **Same-station footprints.** 40 random PRF grids within 100 miles of DFW, OKC, SAT and SGF (seed 473; median distance 65-74 mi).
  - Each grid carries the same Nov-Feb gap cover: PRF-style, 90% trigger, $100,000/6 per month, hedged at that one station.
  - Variants: the sum of per-farm hedges; one hedge refit to the pooled target (LOYO); and a book-size curve (200 random sub-books per size).
  - `he_limit` = 1 − mean off-diagonal Cov(e) / mean off-diagonal Cov(y) is the large-book limit.
- **ENSO.** Each season is Jul-Jun, with its phase from that year's ASO ONI (`scripts/experiments/expansion_review/dl/oni.txt`; El Niño ≥ 0.5, La Niña ≤ −0.5). HE is computed within the seasons of each phase.

**Mechanism.** Var(ΣY − ΣH) / Var(ΣY) falls as farms are added only if the residuals eᶠ = yᶠ − hᶠ are less correlated across farms (ρₑ) than the targets are (ρᵧ). That happens when the hedges capture a shared rain signal and the leftover basis error is farm-specific. If the residual is shared, for example the station's own error against the region, pooling cannot remove it.

### Results: the 11 sample farms as one book

The 11 farms sit on only 6 grids, since the hay and graze farms at each site share a grid, so "one farm per grid" is also shown.

| Book | Version | Farms | Median farm HE | Pooled HE | HE if uncorrelated | ρᵧ | ρₑ |
|---|---|---|---|---|---|---|---|
| 11 farms, dollar weight | holdout 2001-2025 | 10 | 0.611 | **0.528** | 0.449 | 0.118 | −0.006 |
| 11 farms, equal weight | holdout 2001-2025 | 10 | 0.611 | **0.833** | 0.597 | 0.118 | −0.006 |
| one farm per grid, equal | holdout 2001-2025 | 6 | 0.611 | 0.734 | 0.607 | 0.059 | 0.001 |
| 11 farms, dollar weight | LOYO 1951-2025 | 9 | 0.659 | **0.751** | 0.586 | 0.254 | 0.088 |
| 11 farms, equal weight | LOYO 1951-2025 | 9 | 0.659 | **0.827** | 0.654 | 0.254 | 0.088 |
| one farm per grid, equal | LOYO 1951-2025 | 5 | 0.651 | 0.816 | 0.645 | 0.173 | −0.010 |

Source: `expansion_lens_lender_books.csv` (period = calendar year, phase = all). Per-farm HE and months: `expansion_lens_lender_farms.csv`.

These farms sit at different stations, so their basis errors are essentially independent (ρₑ ≈ 0). Their targets still share a weak regional winter signal (ρᵧ 0.12-0.25). The pooled book therefore gains 0.17-0.24 over "if uncorrelated".

The dollar-weighted holdout book is the exception. ABQ_graze has the largest protection ($175,950) and a holdout HE of only 0.25, and it pulls the book below the median farm.

### Results: same-station footprints (Nov-Feb, 40 grids each, equal weight)

| Station | Version | Median farm HE | Pooled HE (sum of hedges) | One hedge refit to book | HE if uncorrelated | ρᵧ | ρₑ | Large-book limit |
|---|---|---|---|---|---|---|---|---|
| DFW | LOYO | 0.600 | **0.750** | 0.744 | 0.613 | 0.826 | 0.529 | 0.755 |
| OKC | LOYO | 0.525 | **0.648** | 0.651 | 0.524 | 0.822 | 0.603 | 0.651 |
| SAT | LOYO | 0.551 | **0.682** | 0.681 | 0.559 | 0.829 | 0.600 | 0.685 |
| SGF | LOYO | 0.622 | **0.771** | 0.776 | 0.622 | 0.818 | 0.500 | 0.776 |
| DFW | holdout | 0.497 | 0.625 | | 0.497 | 0.815 | 0.606 | 0.629 |
| OKC | holdout | 0.513 | 0.686 | | 0.507 | 0.761 | 0.478 | 0.692 |
| SAT | holdout | 0.566 | 0.786 | | 0.609 | 0.762 | 0.413 | 0.792 |
| SGF | holdout | 0.586 | 0.703 | | 0.578 | 0.824 | 0.577 | 0.707 |

Source: `expansion_lens_lender_books.csv` (calendar year, phase all); refit rows have version "loyo, one hedge refit to book".

Book-size curve (LOYO, median pooled HE over 200 sub-books; `expansion_lens_lender_booksize.csv`):

| Farms | DFW | OKC | SAT | SGF |
|---|---|---|---|---|
| 1 | 0.594 | 0.525 | 0.559 | 0.595 |
| 2 | 0.687 | 0.593 | 0.609 | 0.708 |
| 5 | 0.727 | 0.623 | 0.659 | 0.745 |
| 10 | 0.741 | 0.641 | 0.671 | 0.762 |
| 40 | 0.750 | 0.648 | 0.682 | 0.771 |

Pooling at one station raises HE by 0.12-0.15 (LOYO) or 0.12-0.22 (holdout), and the curve flattens by about 10 farms.

The limit is set by ρₑ ≈ 0.5-0.6. Farms 30-100 miles from the same airport share the station's own error against the region, so a lender cannot diversify it away. Refitting one hedge to the whole book gives the same HE as summing the farms' hedges (within 0.006).

### Results: by ENSO phase (Jul-Jun seasons)

| Book | Phase | Seasons | Pooled HE | Median farm HE | Book loss vs all-season mean | Hedge payout vs all-season mean |
|---|---|---|---|---|---|---|
| 11 farms, equal, LOYO | all | 74 | 0.819 | 0.691 | 1.00 | 1.00 |
| | El Niño | 20 | 0.786 | 0.704 | 0.80 | 0.85 |
| | neutral | 37 | 0.803 | 0.640 | 1.00 | 1.01 |
| | La Niña | 17 | 0.858 | 0.626 | 1.23 | 1.16 |
| 11 farms, dollar, LOYO | El Niño / neutral / La Niña | 20 / 37 / 17 | 0.745 / 0.716 / 0.835 | | 0.75 / 1.00 / 1.29 | 0.83 / 1.00 / 1.19 |
| DFW footprint, LOYO | El Niño / neutral / La Niña | 20 / 37 / 17 | 0.677 / 0.770 / 0.746 | | 0.79 / 0.99 / 1.27 | 0.86 / 1.03 / 1.10 |
| OKC footprint, LOYO | same | 20 / 37 / 17 | 0.672 / 0.688 / 0.605 | | 0.85 / 1.04 / 1.10 | 0.82 / 1.04 / 1.14 |
| SAT footprint, LOYO | same | 20 / 37 / 17 | 0.759 / 0.761 / 0.839 | | 0.62 / 0.99 / 1.47 | 0.69 / 1.03 / 1.29 |
| SGF footprint, LOYO | same | 20 / 37 / 17 | 0.743 / 0.688 / 0.756 | | 1.03 / 0.99 / 0.99 | 1.15 / 0.89 / 1.06 |
| 11 farms, equal, holdout | El Niño / neutral / La Niña | 7 / 11 / 6 | 0.830 / 0.771 / 0.834 | | 0.70 / 1.13 / 1.11 | 0.78 / 1.12 / 1.03 |

Source: `expansion_lens_lender_books.csv` (period = Jul-Jun season; columns `he_pooled`, `he_farm_median`, `mean_target_vs_all`, `mean_hedge_vs_all`).

Book HE has no consistent ENSO pattern; within-phase differences are up to about 0.1 and change sign across stations. What does change is the level. In El Niño seasons, south-central books lose 0.62-0.85 of their average gap cover and the hedge pays 0.69-0.86 of its average. In La Niña seasons, losses run 1.10-1.47 and hedge payouts 1.10-1.29.

So the hedge pays slightly more than the loss in El Niño years and under-covers La Niña spikes. A lender buying at climatological prices this El Niño winter overpays for a hedge expected to pay less (doc 25 already says this). Holdout splits have only 6-7 seasons per phase and are noise; for example, one DFW footprint holdout El Niño value is −0.42 from 7 seasons.

## 2. Does Kalshi already price ENSO?

### What the saved data contain

- **Candles with history** (`kalshi_rain_daily_candles.parquet`):
  - AUS, DFW (KXRAINDALM), HOU and MIA (south-central and Southeast), plus DEN, LAX, SEA, SFO, NYC and Chicago.
  - They start 2025-11-15. The Nov 2025 markets opened on Nov 14, mid-month, so they are unusable; Dec 2025 onward opened on or just before the 1st.
  - This is **one winter, 2025-26**. Its ASO 2025 ONI is −0.43, neutral by the doc 25 rule (SON −0.57; CPC called a weak La Niña).
- **Candles for Nov 2026 only:** OKC, SATX, TPA, ATL and NOLA (Oct 26-29, 2026); CLL (Oct 2026).
- **Book:** Nov 2026 book of Nov 2 (`kalshi_rain_orderbook_summary_20261102.csv`), all 36 series, mostly strikes 1-7 in. It was taken one day into the month.
- **What this rules out:** there is no El Niño winter in the price history. Dec 2026-Feb 2027, the months with the strongest El Niño signal, are not listed yet.

### How strong is the signal by month?

Netting-script units (30th-percentile put, 70th/95th call), climatology = 1.00, 1951-2025 (`expansion_lens_enso_month_signal.csv`):

| Region | Month | Put after El Niño | Call after El Niño | Put after La Niña | Call after La Niña |
|---|---|---|---|---|---|
| South-central | Nov | 0.60 | **0.95** | 1.63 | 0.53 |
| South-central | Dec | 0.56 | **1.89** | 1.13 | 0.78 |
| South-central | Jan | 0.63 | 1.45 | 1.31 | 0.63 |
| South-central | Feb | 0.80 | 1.33 | 1.65 | 0.85 |
| Southeast | Nov | 0.40 | 1.37 | 1.10 | 1.04 |
| Southeast | Dec | 0.44 | 1.75 | 1.20 | 0.52 |

In south-central November the El Niño signal sits only on the dry side (put 0.60). The wet call is unchanged. November is therefore a weak month for testing whether Kalshi prices El Niño wetness.

### Nov 2026 book against climatology (south-central and Southeast)

Implied E[min(X, 7 in)] from the strike ladder, in inches (`expansion_lens_enso_nov2026_stations.csv`; mids with spread ≤ 20¢):

| Station | Kalshi mid | Climatology 1991-2025 | Climatology 1951-2025 | El Niño years (n = 19-20) | Strong El Niño, ASO ≥ 1.5 (n = 3-4) |
|---|---|---|---|---|---|
| AUS | 2.44 | 2.32 | 2.44 | 2.58 | 2.00 |
| CLL | 2.94 | 2.88 | 3.01 | 3.47 | 4.17 |
| DFW | 2.61 | 2.66 | 2.47 | 2.48 | 2.88 |
| HOU | 3.56 | 3.53 | 3.58 | 4.05 | 3.75 |
| OKC | 2.06 | 1.83 | 1.79 | 1.85 | 2.00 |
| SAT | 2.28 | 1.86 | 2.16 | 2.03 | 1.50 |
| ATL | 3.47 | 3.66 | 3.59 | 4.33 | 3.88 |

MIA, TPA and DJT lack a 1-7 ladder in the book. Their mids at high strikes are far above climatology (for example MIA mean P 0.45 against 0.21), which suggests Nov 1 rain or a short-range forecast. They are in `expansion_lens_enso_nov2026_quotes.csv` but should not be read as an ENSO signal.

**Dry side, which the Companion's NO contracts use.** Mean P(rain > K) (`expansion_lens_enso_nov2026_lowstrikes.csv`):

| Group | Strike | Stations | Mid | Climatology 1951-2025 | El Niño | Mid − climatology | El Niño − climatology |
|---|---|---|---|---|---|---|---|
| South-central | 1 in | 6 | 0.796 | 0.745 | 0.799 | +0.051 | +0.054 |
| South-central | 2 in | 6 | 0.545 | 0.520 | 0.580 | +0.025 | +0.060 |
| Other stations (control) | 1 in | 19 | 0.848 | 0.749 | 0.726 | +0.099 | −0.023 |
| Other stations (control) | 2 in | 22 | 0.641 | 0.524 | 0.518 | +0.116 | −0.006 |

South-central low-strike mids sit near the El Niño-conditional level. But the market sits even further above climatology at stations where El Niño predicts nothing. The general gap is about +0.10 at 1-2 in, from Nov 1 rain, the spread or bias. So the south-central match is not evidence of ENSO pricing.

**Cross-station regression.** The model is (mid − clim51) = a + β (cond − clim51) + c·clim51. Its 90% CI comes from 500 bootstraps of seasons, which covers climatology sampling only (`expansion_lens_enso_regression.csv`):

| Sample | Conditional | Quotes / stations | β | 90% CI |
|---|---|---|---|---|
| Nov 2026 book, all stations | El Niño | 213 / 34 | −0.22 | −0.42 to 0.18 |
| Nov 2026 book, all stations | strong El Niño | 213 / 34 | 0.01 | −0.07 to 0.09 |
| Nov 2026 book, south-central + SE | El Niño | 72 / 11 | −0.68 | −1.06 to 0.51 |
| Dec 2025-Mar 2026 first quotes (day ≤ 3) | La Niña | 192 / 10 | 0.18 | −0.12 to 0.29 |
| Dec 2025-Mar 2026 first quotes | neutral | 192 / 10 | −0.40 | −0.61 to 0.21 |

β = 1 would mean prices fully tilt to ENSO-conditional climatology, and β = 0 means no tilt. No estimate is distinguishable from 0, and none is near 1.

**Winter 2025-26 scored against outcomes.** 35 events and 192 quotes; median snapshot on day 2 of the month (`expansion_lens_enso_history_summary.csv`). Brier scores (lower is better):
- All stations: market 0.131, climatology 1991-2025 0.123, climatology 1951-2025 0.118, La Niña-conditional 0.119, neutral-conditional 0.115.
- AUS, DFW, HOU and MIA (14 events): market 0.149, climatology 1991-2025 0.135, climatology 1951-2025 0.122, La Niña-conditional 0.106. The market's mean P was 0.347, against 0.252 for La Niña-conditional climatology.

The market did not lean dry ahead of a La Niña-leaning winter that turned out dry in Texas. With 14 correlated events, this is suggestive only.

### What can and cannot be concluded

- **Can:** the saved prices show no detectable ENSO tilt, and the market was not sharper than plain climatology in 2025-26.
- **Cannot:** whether Kalshi prices this El Niño in Dec-Feb.
  - No El Niño winter is in the history.
  - The one El Niño-season book is November, where the wet signal is absent in the south-central region.
  - It was taken a day into the month, so Nov 1 rain and short-range forecasts dominate any seasonal signal.
  - The ENSO-conditional climatology rests on about 20 seasons (3-4 for strong El Niño), and the noise in it biases β toward 0.
- **Next step:** rerun the regression on the Dec 2026, Jan 2027 and Feb 2027 books as they list. For a pre-month snapshot, the Dec books will appear about Nov 26-Dec 1. Test β against the El Niño-conditional climatology (Dec south-central call 1.89x).

## 3. Solar as a wet-side counterparty

### Data and method

- **Irradiance.** NASA POWER monthly `ALLSKY_SFC_SW_DWN` (kWh/m²/day), 1984-2025, at the station coordinates in `station_map.csv`. Raw JSON is cached in `data/raw/nasa_power/`.
- **Rain.** `station_monthly_precip.csv`.
- **Anomalies.** z-scores within station-month.
- **Plant output** is proportional to irradiance × days. The shortfall is the station-month mean minus that month's output.
- **Hedges** are scored out of sample (leave one year out) with non-negative weights and a free intercept:
  - the listed Kalshi YES ladder (`hedge_builder.listed_strikes`, 1-7 in);
  - one netting-convention rain call (70th/95th percentile, linear);
  - an irradiance put (K = 30th percentile, exhausting at the 5th percentile, as the netting script's temperature put does).
- **Netting** follows `run_expansion_netting.py`: rancher put at the 30th percentile with E = 0, each side scaled to equal premium, 20% load, and 95% capital per premium dollar = max(0, VaR95)/premium.
  - Baseline: the put plus a year-shuffled copy of itself (a second independent contract with the same distribution, averaged over 200 shuffles).
  - Medians are over station-months (20 for Nov-Feb, 60 for all months).

### Results

Irradiance-rain anomaly correlation (`expansion_lens_solar_corr.csv`, `pearson_z`):

| Station | Nov-Feb | All months |
|---|---|---|
| DFW | −0.45 | −0.54 |
| AUS | −0.42 | −0.52 |
| SAT | −0.41 | −0.51 |
| HOU | −0.40 | −0.49 |
| OKC | −0.53 | −0.55 |
| All five (n = 819 / 2,460) | **−0.44** (Spearman −0.45) | **−0.52** (Spearman −0.53) |
| All five, Nov-Feb 1984-2000 / 2001-2025 | −0.50 / −0.38 | |

Share of a solar plant's monthly energy variance removed, median over station-months (`expansion_lens_solar_hedge.csv`; summary printed by the script):

| Months | Energy CV | Kalshi YES ladder (LOYO) | One 70/95 rain call (LOYO) | Same, in sample | Irradiance put (LOYO, not listed) |
|---|---|---|---|---|---|
| Nov-Feb | 0.120 | **0.089** | 0.034 | 0.117 | 0.569 |
| Mar-Oct | 0.082 | 0.203 | 0.132 | 0.220 | 0.592 |
| All months | 0.093 | 0.172 | 0.114 | 0.202 | 0.584 |

Rancher put paired with a solar owner's hedge, median 95% capital per premium dollar (`expansion_lens_solar_netting.csv`; station-month rows in `expansion_lens_solar_netting_station_month.csv`):

| Book | Payout correlation | Capital95, Nov-Feb | Worst year, Nov-Feb | Capital95, all months | Worst year, all months |
|---|---|---|---|---|---|
| Rancher put alone | | 3.62 | 4.51 | 3.50 | 4.38 |
| Solar rain call alone | | 4.40 | 4.47 | 4.17 | 4.32 |
| Solar irradiance put alone | | 3.98 | 4.04 | 3.95 | 4.02 |
| Put + solar rain call | −0.27 | **1.75** | 2.00 | 1.66 | 1.95 |
| Put + solar irradiance put | −0.24 | **1.63** | 1.95 | 1.58 | 1.96 |
| Put + independent second put | 0 | **1.81** | 3.08 | 1.79 | 3.03 |

### Reading

- **Solar owners are naturally on the wet side.** A wet month is a cloudy month (r ≈ −0.44 in winter).
- **A listed monthly rain contract is a poor hedge for them, though.**
  - It removes about 9% of winter energy variance out of sample, and only 3% for the single call a market maker would write.
  - Clouds without rain, and rain on a few days, decouple the two.
  - Their rational demand for Kalshi rain calls is small. An irradiance index would hedge 57%, but Kalshi does not list one.
- **The netting arithmetic matches doc 25's rain pairing.**
  - Most of the drop from 3.62 to 1.75 per premium dollar comes from writing any second independent contract (1.81).
  - The opposite side adds about 0.06-0.18 of capital at the 95% level. Its real contribution is in the worst year: about 2.0, against 3.1 for an independent second put.
- **Solar fits the wholesale/MGA counterparty profile in doc 25, not retail Kalshi demand.** The plants are large entities, ECP-eligible, and want an irradiance index.

## Caveats

- **Lender check: index payouts only.** Gap targets are PRF-style rain-index payouts on the farm's grid, not loan losses. "Lender HE" is the HE of the index-payout pool.
- **Lender check: footprint design.** Grids are PRF grid centers, sampled at random within 100 miles, each with identical cover. Real borrowers cluster and carry different PRF elections and sizes.
- **Lender check: the 11-farm book** has 6 grids and 6 stations, so it is a multi-region book, not a single association.
- **Model prices.** All hedges use model prices (fair climatology 1991-2025 plus a 2.25¢ half-spread), as doc 21 does. Depth limits (doc 22) are not applied, and a 40-farm book needs 40 times the depth.
- **ENSO split.** Seasons run Jul-Jun. Jul-Aug months in a farm's package (SAT_graze Jul, DFW_graze Aug in the holdout) are assigned to the ASO value of the same year, which is not yet known in July.
- **ENSO check.**
  - Nov 2 book mids include one day of November rain and short-range forecasts.
  - The bootstrap covers climatology sampling only, not quote noise or the attenuation of β from a noisy regressor.
  - The ENSO-conditional samples are 17-20 seasons (3-4 for ASO ≥ 1.5).
- **NASA POWER.**
  - It is a gridded satellite and reanalysis product (about 0.5-1°), not a meter. Plant output also depends on temperature, clipping and curtailment.
  - Its correlation with station rain is weaker after 2001 (−0.38 against −0.50 in winter), possibly a source change in the record. This is not investigated.
- **Capital figures** are empirical 95% quantiles of 42 years per station-month, so they are noisy individually. The tables use medians.

## Numbers table

| Quantity | Value | Source (data/processed/) |
|---|---|---|
| Per-farm holdout HE reproduces doc 21 (median of 10 farms with a pick) | 0.611 | `expansion_lens_lender_farms.csv` (`he_calendar`, version holdout); matches `m2_companion_holdout.csv` |
| Per-farm LOYO package HE, median of 9 farms | 0.659 | same (version loyo); matches `m2_companion_farms.csv` `package_he_oos` |
| 11-farm book, holdout: pooled HE dollar / equal; if uncorrelated (equal) | 0.528 / 0.833; 0.597 | `expansion_lens_lender_books.csv` |
| 11-farm book, LOYO: pooled HE dollar / equal; if uncorrelated (equal) | 0.751 / 0.827; 0.654 | same |
| 11-farm book ρᵧ / ρₑ (holdout; LOYO) | 0.118 / −0.006; 0.254 / 0.088 | same |
| One farm per grid, pooled HE holdout / LOYO | 0.734 / 0.816 | same |
| Footprint median farm → pooled HE, LOYO: DFW, OKC, SAT, SGF | 0.600→0.750, 0.525→0.648, 0.551→0.682, 0.622→0.771 | same |
| Footprint median farm → pooled HE, holdout: DFW, OKC, SAT, SGF | 0.497→0.625, 0.513→0.686, 0.566→0.786, 0.586→0.703 | same |
| Footprint ρᵧ; ρₑ (LOYO) | 0.82-0.83; 0.50-0.60 | same |
| Footprint one-hedge refit HE, DFW / OKC / SAT / SGF | 0.744 / 0.651 / 0.681 / 0.776 | same |
| Book-size curve, 10 farms (LOYO): DFW / OKC / SAT / SGF | 0.741 / 0.641 / 0.671 / 0.762 | `expansion_lens_lender_booksize.csv` |
| 11-farm equal LOYO HE by phase, El Niño / neutral / La Niña | 0.786 / 0.803 / 0.858 (20/37/17 seasons) | `expansion_lens_lender_books.csv` |
| South-central El Niño-season loss vs mean; hedge vs mean | 0.62-0.85; 0.69-0.86 | same (`mean_target_vs_all`, `mean_hedge_vs_all`; DFW, OKC, SAT footprints and 11-farm book) |
| ASO ONI 2025 / 2026 | −0.43 / +2.46 | `scripts/experiments/expansion_review/dl/oni.txt` |
| Candle history start, south-central and SE | 2025-11-15 (AUS, DFW, HOU, MIA) | `kalshi_rain_daily_candles.parquet` (printed by script) |
| South-central Nov / Dec call after El Niño | 0.95 / 1.89 | `expansion_lens_enso_month_signal.csv` |
| Nov 2026 implied mean, mid vs clim91 vs El Niño (DFW) | 2.61 / 2.66 / 2.48 in | `expansion_lens_enso_nov2026_stations.csv` |
| Low-strike mid − clim51, south-central vs other stations (1 in) | +0.051 vs +0.099 | `expansion_lens_enso_nov2026_lowstrikes.csv` |
| β, Nov 2026 all stations, El Niño (90% CI) | −0.22 (−0.42 to 0.18) | `expansion_lens_enso_regression.csv` |
| β, Dec 2025-Mar 2026, La Niña (90% CI) | 0.18 (−0.12 to 0.29) | same |
| Brier 2025-26 SC+SE: market / clim91 / clim51 / La Niña | 0.149 / 0.135 / 0.122 / 0.106 | `expansion_lens_enso_history_summary.csv` |
| Irradiance-rain anomaly correlation, Nov-Feb / all months | −0.44 / −0.52 | `expansion_lens_solar_corr.csv` |
| Solar energy variance removed, Nov-Feb: YES ladder / one call / irradiance put | 0.089 / 0.034 / 0.569 | `expansion_lens_solar_hedge.csv` (medians) |
| Capital95 per premium, Nov-Feb: put / put+solar call / put+irradiance put / put+independent put | 3.62 / 1.75 / 1.63 / 1.81 | `expansion_lens_solar_netting.csv` |
| Worst year per premium, Nov-Feb: same books | 4.51 / 2.00 / 1.95 / 3.08 | same |
| Payout correlation, put vs solar call / irradiance put | −0.27 / −0.24 | same |
