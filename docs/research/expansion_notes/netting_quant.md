# Netting opposite weather hedgers: quantitative check

Research date: 2026-11-19. Script: `scripts/run_expansion_netting.py` (about 2.5 minutes on the first run while ACIS downloads, then about 45 s with `--offline`). Every number below names the CSV in `data/processed/` and the column it comes from. Medians are taken across station-months unless stated otherwise. These are backtests on station climatology. No real demand, prices or order books are modeled.

## Question

Suppose a market maker (MM) sells a dry-side put to one hedger and a wet-side call to another hedger, both settled on the same Kalshi station and month, and keeps the premium. How much of the risk cancels, how much capital beyond the premium does the book need, and how does that compare with writing one side only, or with pooling one side across many stations?

## Method

**Pairings.** Both sides of each pairing settle on the same airport station's monthly record.

| pairing | put side (pays on low outcome) | call side (pays on high outcome) |
|---|---|---|
| `rain_total` | dryland farmer: monthly rain | outdoor venue: monthly rain |
| `rain_days` | dryland farmer: monthly rain | outdoor venue: number of Fri-Sun days with at least 0.10 in |
| `snow_total` | ski resort: monthly snowfall | plow contractor or city: monthly snowfall |
| `snow_events` | ski resort: monthly snowfall | plow contractor: days with at least 2 in of snow |
| `temp` | cold-side hedger: monthly mean temperature | warm-side hedger: monthly mean temperature |

**Contract terms.** These are fitted on each station-month's own 1951-2025 sample:
- Put: payout fraction is `clip((K - x)/(K - E), 0, 1)`. K is the 30th percentile. E is 0 for rain and snow, so the put pays in full only on a zero month, which mirrors PRF's linear trigger. For temperature, E is the 5th percentile.
- Call: payout fraction is `clip((x - K)/(E - K), 0, 1)`, with K at the 70th percentile and E at the 95th. For the count variables, K is rounded down and E is at least K + 1.
- Each contract is scaled so its expected payout is 1 unit. Both sides are therefore sold at **equal premium**. The MM charges a 20% load (doc 24's base-case load), so it collects 1.2 units per contract.
- Snow puts are written only for Nov-Apr station-months whose 30th-percentile snowfall is at least 1 in. That leaves 43 station-months at 13 stations (`expansion_netting_summary.csv`, `n_station_months`).

**Books.** Each book is (put units, call units): `put` (1,0), `call` (0,1), `pair` (1,1), `put3_call1` (3,1), `put1_call3` (1,3) and `put3` (3,0). Net loss is L = payouts − premium. The metrics are:
- `capital95` and `capital99`: max(0, VaR) of L. This is the capital needed beyond the premium already collected.
- The 95% figures are empirical over 75 years.
- The 99% figures (the 1-in-100 month) come from 100,000 draws of a fitted distribution: a zero-inflated gamma for rain and snow, a normal for temperature. They are computed for the same-variable pairings only.
- `collateral`: the largest possible net loss. This is the Kalshi-style full-collateral requirement.
- `var_reduction` = 1 − Var(net payout) / (Var(put) + Var(call)).
- `_per_prem` columns divide by the premium collected. `_units` columns are in units of one contract's expected payout.

**Out of sample.** Strikes and premiums are fitted on 1951-1995, then payouts are realized on 1996-2025. Reported as `oos_pure_loss_ratio`, where 1.0 means fairly priced and above 1 means the side was underpriced.

**Pooling.** One farmer put per station per month is pooled across stations, nationally and in five regions (`REGIONS` in the script). The pool includes stations with at least 70 years of data, which drops Napa and St Petersburg. I also compute the correlation of dry-month indicators (rain below the 30th percentile) for every station pair and month, binned by distance.

**Data sources.**
- `data/processed/station_monthly_precip.csv`: the committed ACIS station record for 37 Kalshi rain stations. MDW is dropped because Chicago now settles on ORD. This drives `rain_total` and the pooling.
- ACIS StnData daily pcpn, snow and avgt, 1951-2025, for 38 stations: the same 37 plus Salt Lake City for the snow ladder. These use threaded city records where ACIS has them and are cached in `data/raw/stations/acis_expansion/` (38 MB, gitignored). They drive `rain_days`, the snow pairings and `temp`. Monthly totals derived from the daily file match the committed monthly CSV to within 0.01 in for 98.7% of 29,579 station-months (printed by the script).
- `kalshi_weather_series_catalog.csv` is summarized in `expansion_kalshi_families.csv`.

## What Kalshi lists (from `expansion_kalshi_families.csv`)

| family | frequency | series (`n_series`) | with open markets (`n_with_open_markets`) |
|---|---|---|---|
| rain_monthly | monthly + custom | 26 + 12 | 24 + 12 |
| rain_daily / rain_weekly | daily / weekly | 10 / 2 | 4 / 1 |
| snow | monthly | 24 | 13 |
| snow | custom / annual / one-off (resorts, White Christmas) | 9 / 3 / 9 | 5 / 1 / 0 |
| temp_high | daily | 57 | 24 |
| temp_low | daily / monthly | 54 / 5 | 24 / 2 |
| hurricane | annual / custom / one-off | 8 / 55 / 5 | 3 / 7 / 4 |

- **Monthly-snow cities:** Boston, Chicago O'Hare, DC, Denver, Detroit, Milwaukee, Minneapolis, NYC, Philadelphia, Pittsburgh, Seattle, Trenton and Salt Lake City, plus thin-snow cities (Austin, Dallas, Houston, LA, SF, Miami) and Aspen, Jackson WY and Big Sky. Big Sky settles on an OnTheSnow resort report.
- **Resort series** (seasonal or custom): Alta, Beaver Creek, Keystone, Mammoth, Northstar, Park City and Stowe.
- **Monthly temperature:** Kalshi has no monthly mean, HDD or CDD contract. The monthly temperature series are minimum-temperature thresholds (NYC, Madison, San Jose). The `temp` pairing is therefore a what-if on a contract Kalshi does not list.

## Headline numbers

### 1. Same-station netting: rain (`expansion_netting_summary.csv`, pairing `rain_total`, 393 station-months, 34 stations)

| book | corr_put_call | var_reduction | capital95_per_prem | capital99_per_prem | collateral_per_prem | capital95_units | capital99_units | p_mm_loss |
|---|---|---|---|---|---|---|---|---|
| put only | — | 0 | 3.57 | 4.87 | 6.36 | 4.29 | 5.84 | 0.24 |
| call only | — | 0 | 4.31 | 4.45 | 4.49 | 5.17 | 5.34 | 0.23 |
| pair 1:1 | −0.263 | 0.262 | **1.74** | **2.03** | **2.68** | 4.17 | 4.86 | 0.36 |
| 3 farmers : 1 venue | | 0.160 | 2.43 | 3.40 | 4.52 | 11.66 | 16.32 | 0.32 |
| 1 farmer : 3 venues | | 0.156 | 2.98 | 3.09 | 3.12 | 14.31 | 14.83 | 0.29 |
| put × 3 (no venue) | | 0 | 3.57 | 4.87 | 6.36 | 12.86 | 17.52 | 0.24 |

- **The venue side roughly halves capital per dollar of premium:** 3.57 to 1.74 at 95%, 4.87 to 2.03 at 99%, and 6.36 to 2.68 for full collateral (`capital95_per_prem`, `capital99_per_prem`, `collateral_per_prem`).
- **In absolute terms, the second side's premium needs no extra capital.** The pair needs 4.17 units of capital at 95% versus 4.29 for the put alone, and 4.86 versus 5.84 at 99% (`capital95_units`, `capital99_units`). A put and a call on the same monthly total can never both pay, so the venue's premium is a buffer against the farmer's tail, and vice versa.
- **Variance reduction is only about 26%.** The two payouts are mutually exclusive but not mirror images: each is zero 70% of the time, so their correlation is bounded near −0.26 (`corr_put_call`), and `var_reduction` equals that magnitude when the variances are equal. The tails are where netting pays off, not the variance. Pair TVaR95 is 1.92 against 4.48 for the put alone (`tvar95_per_prem`).
- **Middle months pay neither side.** No payout is made in 38.7% of months (`p_neither_pays`, pair). The MM loses money in a month more often with the pair, 36% against 24% for the put alone (`p_mm_loss`), but it loses far less when it does.
- **Expected margin against tail.** At a 20% load, the in-sample margin is 0.2/1.2 = 16.7% of premium by construction. A 1-in-100 month costs the pair about 2.03 / 0.167 ≈ 12 months of margin, against about 29 for the put alone (`capital99_per_prem` divided by the load share).
- **Mismatched demand.** One venue per three farmers recovers (3.57 − 2.43) / (3.57 − 1.74) ≈ 62% of the 1:1 capital benefit at 95%, with `var_reduction` at 0.160. Absolute 95% capital falls from 12.86 to 11.66 units (`capital95_units`, `put3` vs `put3_call1`). The unmatched farmer excess still has to be capitalized or laid off.
- **Spread across station-months is narrow.** Pair `var_reduction` runs 0.20-0.33 and `capital95_per_prem` runs 1.07-2.59 across all 393 rain station-months (`expansion_netting_station_month.csv`, book `pair`). Because strikes are percentiles, the netting mechanics are nearly the same everywhere. What differs between stations is the pricing drift covered in item 4.

### 2. Venue exposure as wet weekend days (`rain_days`)

- **Weaker link to the farmer side.** The venue's realistic index, wet Fri-Sun days, is less tied to the farmer's monthly total: `corr_put_call` is −0.234 against −0.263, and `var_reduction` is 0.231 against 0.262.
- **Both sides can pay in the same month** (1.3% of months, `p_both_pay`), so full collateral can no longer be netted. The worst case is the sum, and pair `collateral_per_prem` jumps to 5.68 from 2.68.
- **95% capital is almost unchanged:** 1.84 against 1.74 (`capital95_per_prem`). A day-count venue contract keeps most of the netting benefit, but an exchange that requires full collateral would not credit it.

### 3. Snow and temperature

- **`snow_total` pair** (43 station-months, 13 stations): `var_reduction` 0.271, `capital95_per_prem` 1.75 against 3.32 for the ski put alone, `capital99_per_prem` 1.91 against 4.30, `collateral_per_prem` 1.96 against 4.39.
- **`snow_events`** (plow call on days with at least 2 in): netting is similar (`var_reduction` 0.268, `capital95_per_prem` 1.79), but collateral rises to 4.45 because both sides can pay.
- **By month** (`expansion_netting_months.csv`, pairing `snow_total`): February has the lowest median `capital95_per_prem` among months with at least 8 stations (1.65, 11 stations). December is the highest (1.91).
- **`temp` pair** (420 station-months): `var_reduction` 0.267, `capital95_per_prem` 1.74 against 4.14 for one side, `collateral_per_prem` 1.79.

### 4. Out of sample: climate drift is the larger risk (`oos_pure_loss_ratio`, `oos_mm_margin_per_prem`)

| pairing | put side | call side | pair | pair margin per premium |
|---|---|---|---|---|
| rain_total | 0.99 | **1.17** | 1.10 | 0.079 |
| rain_days | 0.99 | 1.00 | 1.00 | 0.170 |
| snow_total | **1.27** | 1.04 | 1.25 | −0.045 |
| temp | 0.36 | **2.02** | 1.24 | −0.034 |

- **Prices fitted on 1951-1995 underprice whichever side the climate has drifted toward.**
  - Rain: wet-side calls paid 17% more than they were priced, and the call side is underpriced in 58.8% of rain station-months.
  - Snow: low-snow puts paid 27% more.
  - Temperature: warm-side calls paid about twice what they were priced, and the call side is underpriced in 96.2% of temperature station-months.
  - The 58.8% and 96.2% shares come from comparing `oos_pure_loss_ratio` for books `call` and `put` per station-month in `expansion_netting_station_month.csv`.
- **Pairing halves the drift but does not remove it.** The pair's loss ratio is the average of its two sides, so the 20% load is mostly or fully used up: pair margin per premium falls from 0.167 in sample to 0.079 for rain, and goes to −0.045 for snow and −0.034 for temperature. A two-sided book needs trend-adjusted or recent-window pricing. That pricing choice matters more than the netting.
- **Rain stations where both sides stayed near fair:** Atlanta (put 0.88, call 0.90), Newark (1.05, 1.09), Austin (0.99, 1.04) and Houston (0.89, 1.10). These are medians over months of `oos_pure_loss_ratio`, books `put` and `call`, `rain_total`.
- **Stations that drifted most:** San Antonio (1.46, 1.17), College Station (1.34, 1.28) and DFW (1.13, 1.37). Texas months became both drier and wetter in the tails.

### 5. Pooling across stations beats same-station netting, if demand is spread out (`expansion_netting_pooling.csv`)

| book (one contract per station) | capital95_per_prem | tvar95_per_prem | n_effective_independent |
|---|---|---|---|
| single-station put (summary, `rain_total`/`put`) | 3.57 | 4.48 | 1 |
| same-station pair (summary, `rain_total`/`pair`) | 1.74 | 1.92 | — |
| regional put pools, monthly (scope `month_median`) | 1.40 (west) to 2.42 (northeast); south_central 2.18 | 1.84 to 3.56 | 1.8 to 3.7 |
| national put pool, monthly (33.5 stations, `month_median`) | 0.89 | 1.25 | 9.6 |
| national pair pool, monthly (`month_median`) | 0.34 | 0.47 | 13.8 |
| national put pool, annual (30 stations × 12 months, scope `annual`) | 0.15 | 0.31 | 6.5 |
| national pair pool, annual | 0.00 | 0.00 | 11.9 |

- **Station-to-station dryness correlation by distance** (`expansion_netting_dry_corr.csv`, `mean_dry_corr`):

  | distance | mean dry-month correlation |
  |---|---|
  | under 100 mi | 0.54 |
  | 100-250 mi | 0.35 |
  | 250-500 mi | 0.20 |
  | 500-1000 mi | 0.05 |
  | over 1000 mi | 0.00 |

  Over all 6,251 station-pair-months the mean is 0.07. Dry months are close to independent beyond about 500 mi.
- **A regional farmer-only book is no better than same-station netting.** The south-central pool (DFW, OKC, SAT, AUS, CLL, HOU) needs 2.18 capital per premium against 1.74 for a same-station pair. Only a national, cross-season book diversifies much better.
- **Combining both mechanisms is strongest.** A national book of pairs needs 0.34 per premium monthly and essentially nothing beyond the load over a year: its worst year is 0.02 per premium (`worst_year_per_prem`).

## Best pairings, months, stations

1. **Rain, farmer against venue on the same monthly total, is the cleanest product.**
   - Pair capital95 per premium by station (median over months, `expansion_netting_station_month.csv`, `rain_total`/`pair`): Pittsburgh 1.52, LA 1.56, Detroit 1.57, Indianapolis 1.61 and SFO 1.62 are lowest; Boston 1.99, Tampa 1.95, Lexington 1.92 and DC 1.92 are highest. The range is narrow.
   - For the study stations: DFW 1.65, OKC 1.68, SGF 1.64, SAT 1.66, ABQ 1.73, DEN 1.82 and TPA 1.95.
   - **Choose stations on drift and demand, not on the netting statistics.** Atlanta, Newark, Austin and Houston priced stably out of sample.
2. **The best months are October and January-February,** but the differences are small. Pair `capital95_per_prem` in `expansion_netting_months.csv` (`rain_total`) runs from 1.64 in October to 1.87 in June. These are also the months the PRF Companion targets (doc 21), so a venue side for winter rain is the most relevant match to the current direction.
3. **Snow** nets as well as rain. It has 13 cities with at least 1 in at the 30th percentile, mostly December-March, and February has the lowest capital. But the out-of-sample low-snow drift (1.27) wipes out the 20% load.
4. **Temperature** nets as well, but Kalshi lists no contract to settle on, and the warming drift (warm calls at 2.02) makes historical pricing unusable.
5. **Mismatched demand is the norm.** A 3:1 farmer-to-venue book keeps about 62% of the 95% capital benefit, so even partial matching helps. National cross-station pooling helps more than same-station matching.

## Caveats

- **Sample size.** 75 years per station-month: 95% figures are empirical, but 99% figures depend on the gamma or normal fit, and the count pairings have no 99% figure. Out-of-sample tests use 30 years, and snow has only 41-43 station-months.
- **Percentile strikes make the netting results nearly universal.** About 26% variance reduction and halved capital per premium follow from the 30/70 strikes and equal premium. Different strikes, such as 20/80, or a convex shape (doc 24) would change the numbers. Contracts here are linear payouts; Kalshi lists whole-inch binary ladders, and doc 23 shows how to approximate linear payouts from them, with liquidity limits (doc 22).
- **Basis risk sits with the hedgers, not the MM.** Both sides settle on the same station, so the MM carries no basis risk. Venues in the city near the airport have small basis risk. Farms 30-55 mi away have more: station-to-farm correlations are in doc 07, and dry indicators at under 100 mi correlate only about 0.54 even between stations. Ski resorts are in the mountains, not at the city airports these snow series settle on (Denver and SLC airport snow are weak proxies for resort snow), so the `snow_*` pairings overstate how well a resort is hedged.
- **Not modeled:**
  - Forecast-driven adverse selection. Venues buy rain cover after a wet forecast, and farmers buy after an ENSO or drought outlook, so demand would cluster on the side that is about to pay.
  - Demand elasticity, Kalshi fees and the MM's own operating cost.
  - Correlation between station-months in the same year beyond what the annual pools capture.
- **Equal-premium sizing assumes one premium unit per hedger.** Real demand is lumpy. A large ranch could equal hundreds of bars.
- **Pooling rows weight all stations and months equally.** Real farmer demand concentrates in Plains and West growing seasons, so the national-pool numbers are an upper bound on diversification.
- **Data quality.** Threaded ACIS records splice predecessor sites before the airport station opened. Daily S/A (accumulated) flags are treated as 0 or as the reported total, which slightly distorts day counts.

## Files

- `scripts/run_expansion_netting.py`
- `data/processed/expansion_netting_station_month.csv`: one row per pairing × station × month × book (7,824 rows)
- `data/processed/expansion_netting_summary.csv`: medians by pairing × book
- `data/processed/expansion_netting_months.csv`: pair medians by calendar month (`rain_total`, `rain_days`, `snow_total`)
- `data/processed/expansion_netting_pooling.csv`: national and regional pools (monthly, annual, and median of months)
- `data/processed/expansion_netting_dry_corr.csv` and `expansion_netting_dry_corr_pairs.csv`: dry-month correlation by distance, and for every station pair
- `data/processed/expansion_kalshi_families.csv`: Kalshi weather series by family
- Cache: `data/raw/stations/acis_expansion/` (gitignored)
