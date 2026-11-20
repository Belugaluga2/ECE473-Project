# Rain and outdoor venues: what a rainy day costs a ballpark

Research date: 2026-11-19. Script: `scripts/run_rain_venues.py` (about 20 s once the raw data is cached; the first run downloads about 60 ACIS requests, 29 IEM files and 6 Divvy queries). Every number below cites a column of a CSV the script writes, or a URL. CSV shorthand: **E** = `data/processed/rain_venues_effects.csv` (columns `model`, `sample`, `term`, `coef`, `se`, `pct`, `pct_lo`, `pct_hi`, `n`), **L** = `data/processed/rain_venues_team_month_loss.csv`, **R** = `data/processed/rain_venues_rainouts.csv`, **M** = `data/processed/rain_venues_makeups.csv`. Figure: `docs/figures/rain_venues_effects.png`.

## Takeaway

Over the sample, an MLB open-air park lost about **2.4% of its reported crowd on a played game with 0.10-0.49 in of station rain, and 3.7% at 0.50 in or more**. Dome and retractable-roof parks show no effect (the placebo). Rain the day before also shows no effect.

The bigger cost is the rainout. About **10% of home dates with at least 0.10 in of rain are postponed**. The average rainout loses about **31% of a game's gate**: makeup doubleheaders draw less, and a single-admission doubleheader loses a whole gate.

Combining the two with about $57 of revenue per fan gives an **expected loss of about $97k per rainy home game day (range $76k-$114k)**. For a typical eastern or midwestern open-air club, that becomes a **mean monthly loss of about $250k, a 90th percentile of about $600k and a 95th percentile of about $720k**. West Coast parks lose roughly a tenth as much.

Most of that tail is lumpy rainout risk. The station's monthly rain total tracks only part of it: the median correlation is 0.36, an R² of about 0.13. A game-day index, the number of wet home dates, does better at 0.52 (R² about 0.27).

Bike share is the contrast. Chicago Divvy trips fall 26% on a 0.10-0.49 in day, and casual riders fall 42%. Venues that pre-sell tickets are far less exposed than walk-up activities.

## Data

| Source | What | Use |
|---|---|---|
| Retrosheet game logs, 1990-2025 ([index](https://www.retrosheet.org/gamelogs/index.html), [field guide](https://www.retrosheet.org/gamelogs/glfields.txt)) | date, park ID, attendance, day/night, doubleheader number | attendance panel |
| Retrosheet original schedules, 2000-2026 ([schedule page](https://www.retrosheet.org/schedule/index.html)) | postponement reason (field 11), makeup date (field 12), park from 2024 | rainouts, makeups, home-date templates |
| Retrosheet park codes ([parkcode.txt](https://www.retrosheet.org/parkcode.txt)) | park ID to name and city | park table (roof type and coordinates were added by hand in the script's `PARKS`) |
| NOAA ACIS StnData ([data.rcc-acis.org](https://data.rcc-acis.org)) | daily precipitation and max temperature, 1991-2025, at the nearest first-order airport (`station` in R / L); missing days are filled from a second station (Denver pre-1995 from the ACIS threaded record) | rain bins, temperature controls, the 35-year weather record |
| Iowa Environmental Mesonet ASOS ([asos.py](https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py)) | hourly `p01i`, 2012-2025 | rain in the game window (day games 11:00-17:00 local, night games 16:00-23:00) |
| Chicago Data Portal, Divvy Trips ([fg6s-gzvg](https://data.cityofchicago.org/resource/fg6s-gzvg.json)) | daily trip counts by rider type, 2014-2019 | second venue type |

Park-to-station distance is 2.2-21.6 miles (R `station_miles`). Kauffman (MCI, 21.6 mi), Coors (DEN, 19.0) and Truist (ATL, 18.1) are the farthest. Canadian parks (Toronto, Montreal 2000-04) are excluded because ACIS has no Canadian stations.

Before 2012, the IEM archive leaves most dry hours missing rather than 0. A coverage filter on those years would keep mostly wet days, so the game-window spec uses 2012-2025 only.

## Method

1. **Attendance.** OLS of log(attendance) on same-day station rain bins (0.01-0.09, 0.10-0.49 and 0.50+ in, with dry as the reference), rain of at least 0.10 in the day before, and max-temperature bins (70s as the reference). Controls are opponent, day of week, month, night and home opener, with home-team × season fixed effects absorbed. Standard errors are clustered by team-season (547 clusters, E `n_clusters`).
   - The sample is single games at each team's main park, 2000-2025 without 2020 (no fans) or 2021 (capacity limits). Doubleheaders and makeup dates are dropped.
   - The open-air sample has 42,725 games (E `A_daily` `n`). The placebo sample (2 domes and 6 retractable roofs) has 11,612.
   - Promotions such as bobbleheads and fireworks are not in the data. They are not correlated with same-day rain, so their omission adds noise, not bias.
   - Same-day rain stands in for the forecast: fans decide that morning. Spec B separates the forecast effect from rain falling at game time.
2. **Rainouts.** A game counts as a rainout if the schedule's postponement field mentions rain, wet grounds or inclement weather. Snow, cold and hurricanes are tracked separately and left out.
   - Rates are computed by park × month (R), along with P(postponed | same-day rain bin), pooled over open-air parks (E `R_po_prob`).
   - Each rainout is matched to its makeup date in the game logs. Gate lost = 1 − (makeup-day attendance − model-expected crowd of any game already scheduled that day) / (model-expected crowd on the original date with dry weather), in M `lost`.
3. **Dollars.** Lost fans are multiplied by revenue per fan, using three cases (low, base, high) described under Dollars below.
4. **Monthly loss.** For each club's 2025 open-air park, the 2023-2025 scheduled home dates (the templates) are laid on each year of 1991-2025 station rain, giving 105 template-weather combinations per team-month (L `n_weather_template_combos`).
   - Played games lose the regression's percentage. Rainouts are drawn 200 times per combination from P(postponed | rain), scaled per park by a shrunk calibration factor (L `rainout_scale_vs_pooled`), and each costs 31% of a gate.
   - The CI on the mean comes from 400 joint draws of the attendance coefficients, the gate-lost fraction and the bin probabilities.
   - The Rays are excluded: they played 2025 at Steinbrenner Field but return to the domed Tropicana Field in 2026. The Athletics' 2025 Sacramento park is included as is.

## Headline effects (attendance)

| Same-day station rain vs a dry day | Open-air parks | Dome / retractable placebo | Source |
|---|---|---|---|
| 0.01-0.09 in | **−1.0%** [−1.7, −0.3] | +0.8% [−0.6, +2.2] | E `A_daily`, term `r001_009`, `pct` [`pct_lo`, `pct_hi`] |
| 0.10-0.49 in | **−2.4%** [−3.2, −1.7] | −0.3% [−1.5, +0.9] | E `A_daily`, `r010_049` |
| 0.50 in or more | **−3.7%** [−4.6, −2.8] | +0.2% [−1.3, +1.8] | E `A_daily`, `r050plus` |
| Day before ≥ 0.10 in | +0.2% [−0.4, +0.8] | −0.1% [−1.2, +1.0] | E `A_daily`, `rain_prev_010` |

- **The placebo passes.** All placebo rain coefficients are within ±1% and insignificant (E `A_daily`, `sample` = `dome_retractable_placebo`). The open-air effect is therefore about rain at the park, not a regional economic shock. Placebo parks still show the temperature effect, for example −8.1% for a 50s day (`t_50s`), which fits a climate-controlled roof only partly helping (fans still commute).
- **Clustering by date instead of team-season** leaves the CIs essentially unchanged: −2.4% [−3.1, −1.7] (E `A_daily_cluster_date`).
- **Game window vs forecast (spec B, 2012-2025, n = 21,254).** Rain of at least 0.10 in during the game window alone gives −3.7% [−5.0, −2.5] (E `B_window_only`, `win_010plus`). With both in the model, window rain gives −2.0% [−3.5, −0.5] (E `B_window`, `win_010plus`) and daily rain still adds −1.7% [−2.8, −0.5] at 0.10-0.49 in and −2.6% [−4.0, −1.2] at 0.50+ in. About half of the effect is fans staying away on a rainy day even when the game-time hours are dry. That looks like a forecast or "threat of rain" effect. The placebo window terms are insignificant (E `B_window`, placebo rows).
- **Walk-up vs sellout clubs.** In 11.3% of team-seasons the median game was within 5% of the season's 98th-percentile crowd (E `C_capacity`, `share_ts_near_capacity`). For those clubs the 0.10-0.49 in effect is −2.7% + 2.2% ≈ −0.5% (E `C_capacity`, `r010_049` + `r010_049_x_cap`; the interaction CI is [+0.6, +3.9]). Clubs that sell out in advance show almost no reported-attendance effect.
- **Weekend vs weekday.** No difference at 0.10 in and above. The interaction is −0.3% [−1.8, +1.2] (E `D_weekend`, `r010_049_x_wkend`).
- **Temperature matters more than rain:**
  - below 50°F: −13.0% (E `A_daily`, `t_lt50`)
  - 50s: −7.7% (`t_50s`)
  - 95°F and above: −2.0% (`t_95plus`)

  This matches the heat and cold effects in [Kuruc, LoPalo & O'Connor](https://nbviewer.org/github/kevinkuruc/Papers_for_Download/blob/main/Baseball.pdf).

**What "attendance" measures.** Since 2000 every club reports tickets sold, not turnstile counts ([MPR News 2016](https://mprnews.org/story/2016/09/24/the-big-lie-baseball-attendance)). The coefficients therefore capture lost walk-up and late sales. They miss pre-sold no-shows, who cost concessions and parking but not the ticket. In-park losses on a rainy day are larger than these numbers, and we cannot measure by how much.

## Rainouts

- **Frequency.** 1.81% of scheduled home games at open-air parks were rained out (E `R_po_prob`, `rate_all`, n = 46,077), or 1.46 per team-season (SE 0.06; `rainouts_per_team_season`). Dome and retractable parks had 0.008% (placebo `rate_all`).
- **By month** (R, summing `rain_po` / `scheduled` over parks): Mar 4.3%, Apr 3.6%, May 2.6%, Jun 1.5%, Jul 1.0%, Aug 0.85%, Sep 1.3%, Oct 1.7% (the March and October cells are small).
- **By park** (R summed over months):
  - The highest rates are Shea / Citi Field (3.4% / 2.9%), Nationals Park 3.3%, Progressive Field 3.1%, Fenway 3.0%, Yankee Stadium 2.9% and Comerica 2.9%.
  - Dodger Stadium (0.05%), Petco (0.18%) and the Oakland Coliseum (0.15%) are near zero.
- **P(postponed | same-day station rain)**, open-air parks pooled (E `R_po_prob`):

  | Rain (in) | 0 | 0.01-0.09 | 0.10-0.24 | 0.25-0.49 | 0.50-0.99 | 1.00-1.99 | 2.00+ |
  |---|---|---|---|---|---|---|---|
  | P(postponed) | 0.03% | 0.7% | 3.1% | 6.9% | 14.0% | 21.0% | 34.0% |

  Even 2 in of rain at the airport cancels only a third of games, because rain timing and station distance matter. Pooled bins over- or under-predict individual parks by 0.26x-1.5x (R `rain_po` vs `pred_rain_po`). Coors (1.5x), Comerica (1.44x) and Progressive (1.39x) postpone more than their station rain predicts; Great American Ball Park (0.55x) and Kauffman (0.74x) postpone less.
- **What happens to the game** (832 rainouts; E `R_makeup`, `coef` = share, `pct` = mean gate lost):

  | Outcome | Share | Mean gate lost |
  |---|---|---|
  | Split (separate-admission) doubleheader | 41.6% | 6.8% |
  | Single-admission doubleheader | 32.6% | 87.1% |
  | Separate single game (off day) | 23.3% | −8.2% (makeups on off days draw slightly *more* than the original date would have) |
  | Not made up | 1.9% | 100% |
  | Played at another site | 0.6% | 100% |
  | **All matched rainouts** | | **31.2% [27.4, 34.7]** (E `gate_lost_frac_all`, bootstrap CI, n = 778; 2021 rainouts lack a fitted team-season effect and drop out) |

  The per-game detail is in M.

## Dollars

Revenue per fan:

| | Ticket | In-park spend | Total |
|---|---|---|---|
| Base | $37 | $20 | **$57** |
| Low | $30 | $14.43 | $44.43 |
| High | $37 | $30 | $67 |

(E `USD_rainy_day`, `usd_per_fan`.)

- **Ticket.** $37 is Team Marketing Report's 2023 MLB Fan Cost Index average ticket (2023 FCI $266.58 for a family of four) ([TMR 2023 FCI](https://teammarketing.com/?p=18460); figure taken from the search-result headline, because the page returned 404 when fetched on 2026-11-19). TMR's 2022 average was $35.93 ([TMR 2022 FCI](https://teammarketing.com/?p=17731), also via search snippet). The low case's $30 is an assumption for discounted walk-up and group tickets.
- **In-park spend.** The low case is the FCI basket per person at Statista's 2024 average prices: hot dog $5.47, beer $7.18, soft drink $5.37, and (4 hot dogs + 4 soft drinks + 2 beers) / 4 = $14.43 ([Statista](https://statista.com/statistics/202619/concession-stand-prices-in-mlb)). The $20 base and $30 high cases are **assumptions** that add parking, merchandise and real per-capita spending above the minimum basket. A FinanceBuzz survey puts party-level concession spending at $74 per game, which is not per person ([FinanceBuzz](https://financebuzz.com/mlb-fan-spending)).

Not modeled:
- **Revenue sharing.** MLB clubs share net local revenue, so the club's net loss is smaller than the gross figures here.
- **Makeup operating costs:** staff, security and an extra travel day.
- **Pre-sold no-shows' lost concessions.**

All three move the true cost in different directions.

| Per rainy home date (≥ 0.10 in), average open-air club (29,816 fans, E `avg_att_2023_2025`) | Low | Base | High |
|---|---|---|---|
| Played game: 2.89% of the crowd lost (E `played_frac_lost_rain_ge_010`) | $38k | **$49k** | $58k |
| Rainout: 31.2% of a gate | $413k | **$529k** | $622k |
| Expected per rainy date (P(postponed) = 10.0%, E `p_po_given_rain_ge_010`) | $76k | **$97k** | $114k |

(E `USD_rainy_day`, `usd_played_game_loss`, `usd_per_rainout`, `usd_expected_per_rainy_day`.)

## Monthly loss distribution (per club, base $57 per fan)

Across the 22 clubs × Apr-Sep (132 team-months, L), the medians across team-months are **$251k** for the mean monthly loss, $597k for the 90th percentile and $721k for the 95th percentile. May is the worst month, with medians of $300k (mean) and $850k (95th percentile). September is the mildest, at $190k and $649k (L `mean_usd`, `p90_usd`, `p95_usd`, median by `month`).

| Club (park, station) | Season mean, Apr-Sep (sum of L `mean_usd`) | CI on the mean (sum of `mean_usd_ci_lo` / `_hi`)* | Worst month's p95 (max `p95_usd`) |
|---|---|---|---|
| Yankees (Yankee Stadium, LGA) | $2.84M | $1.89M-$3.89M | $1.58M |
| Phillies (Citizens Bank, PHL) | $2.46M | $1.61M-$3.39M | $1.51M |
| Braves (Truist, ATL) | $2.26M | $1.47M-$3.12M | $1.12M |
| Cubs (Wrigley, ORD) | $2.25M | $1.47M-$3.09M | $1.05M |
| Red Sox (Fenway, BOS) | $2.20M | $1.46M-$3.01M | $1.33M |
| Mets (Citi Field, LGA) | $2.13M | $1.40M-$2.93M | $1.27M |
| Cardinals (Busch, STL) | $1.98M | $1.29M-$2.73M | $1.32M |
| Guardians (Progressive, CLE) | $1.85M | $1.22M-$2.52M | $1.00M |
| Tigers (Comerica, DTW) | $1.78M | $1.18M-$2.43M | $1.01M |
| Rockies (Coors, DEN) | $1.25M | $0.81M-$1.75M | $0.84M |
| Pirates (PNC, PIT) | $1.21M | $0.78M-$1.70M | $0.57M |
| Royals (Kauffman, MCI) | $1.12M | $0.73M-$1.55M | $0.76M |
| Giants (Oracle, SFO) | $0.30M | $0.18M-$0.43M | $0.71M |
| Padres (Petco, SAN) | $0.20M | $0.12M-$0.30M | $0.73M |
| Dodgers (Dodger Stadium, LAX) | $0.19M | $0.12M-$0.28M | $0.22M |
| Athletics (Sutter Health Park, SAC) | $0.08M | $0.05M-$0.12M | $0.20M |

\*The CI combines 400 parameter draws (attendance coefficients, gate-lost fraction, rainout probabilities) with the $44 / $67 per-fan range. Summing monthly bounds overstates the season-level width a little. The remaining clubs (White Sox, Twins, Reds, Orioles, Nationals, Angels) are in L.

**How well a weather index tracks the loss** (median over team-months, L):

| Index | Correlation with the monthly loss | Source column |
|---|---|---|
| Station whole-month rain total (Kalshi-style monthly contract) | 0.61 on the expected loss; **0.36** once rainouts are drawn | `corr_expected_loss_vs_month_rain`, `corr_simulated_loss_vs_month_rain` |
| Count of home dates with ≥ 0.10 in | **0.52** | `corr_simulated_loss_vs_wet_home_days` |
| Rain inches summed over home dates | 0.53 | `corr_simulated_loss_vs_home_day_rain_in` |

A monthly-rain contract on the airport station would hedge about 13% of the variance of a club's simulated monthly rain loss (0.36²). A contract on home-date rain roughly doubles that, to about 27%. The rest is rainout lumpiness: whether a 0.5 in day falls during the game, and how the makeup is scheduled. That residual comes from simulated draws, so it is a modeled bound, not an observed hedge result.

## Second venue: Chicago Divvy bike share (Apr-Oct 2014-2019, 1,284 days)

Regression of log(daily trips) on Midway rain bins, with temperature bins, day of week and year-month fixed effects, clustered by ISO week (E `E_divvy`):

| Riders | 0.01-0.09 in | 0.10-0.49 in | ≥ 0.50 in | Day before ≥ 0.10 |
|---|---|---|---|---|
| All | −11.6% [−14.7, −8.4] | **−26.4%** [−29.1, −23.6] | −39.5% [−43.5, −35.3] | −1.7% [−4.4, +1.1] |
| Subscribers (commuters) | −8.5% | −21.1% | −33.9% | −0.5% |
| Casual customers (leisure) | −20.6% | **−41.6%** [−45.5, −37.4] | −57.2% | −4.6% |

Leisure activity bought on the day is 10-20x more rain-sensitive than pre-ticketed ballgames (−41.6% vs −2.4%). For a wet-side hedger, the strongest natural buyers are walk-up businesses: patio bars, bike and boat rentals, mini golf, food trucks. A ballpark is a weaker buyer, and its exposure is mostly the rainout tail.

## Caveats

- **Measurement.** Attendance is tickets sold, so no-shows are invisible (see above). The airport station is 2-22 miles from the park, and daily totals include rain that fell after the game. Both bias the played-game effect toward zero. Spec B's window rain helps only partly.
- **Selection.** Rained-out games are not in the attendance panel. Games played through heavy rain are those where the rain missed game time or the club pushed through, so the played-game effect is conditional on the game being played. The rainout component covers the rest.
- **Makeup accounting.** The gate-lost fraction compares realized makeup-day crowds with model-expected crowds on the original date. The expectation uses the team-season effect, so a team's mid-season collapse or surge shifts it. The method gives single-admission doubleheaders no credit for longer stays (more concessions per fan), which would lower their true cost.
- **Dollars.** League-average ticket and in-park spend are applied to every club; the Yankees' and Red Sox' real prices are well above average, and the Royals' and Pirates' are below. The $20 and $30 in-park figures and the $30 low ticket are assumptions. Revenue sharing, makeup costs and no-show concessions are not modeled.
- **Rainout model.** P(postponed | rain) is pooled across parks and scaled by a shrunk per-park factor (`PO_PRIOR` = 10 pseudo-rainouts). Rainout decisions also depend on the forecast, the visiting team's schedule and the season stage, none of which are modeled. Clubs that are out of the race may play through rain more often.
- **Weather record.** Daily rain for 1991-2025 is assumed stationary. Climate trends in heavy-rain frequency are not modeled. Station gaps were filled from a second station: Midway 20%, Oakland 26% and Santa Ana 23% of Mar-Oct days. Santa Ana has no daily record before 1999, so the Angels' 1991-1998 weather comes from LAX.
- **Promotions are not available.** This adds noise but not bias, since promotions are scheduled before the weather is known.
- **2021 is excluded** from the regressions because of capacity limits. Its rainouts appear in the frequency counts but drop out of the gate-lost estimate.
- **Divvy** covers only 2014-2019, because the open dataset stops there, and only Chicago.
