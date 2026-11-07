# Final project proposal: "Insure before you know"

**One line:** a prediction market can only insure the risk that is still unresolved when its contract lists. We prove that bound, measure it for every Kalshi weather family directly from opening prices, and use it to explain all of our results so far (and to design the contracts and pooling mechanism that would fix them).

Course fit: idea 3a (insurance from event-contract primitives). Its rubric asks us to "decompose hedge error into binning, geography, settlement source, liquidity, and capital cost" and says "theory is useful for spanning bounds". Our contribution is a sixth component the list leaves out, **listing horizon**, with a bound, an estimator that needs only market prices, and evidence across two weather families. It also borrows from 3b (building longer exposures from expiring contracts): the same bound says when that is possible.

## 1. The idea

Kalshi lists a monthly-rain contract about a month ahead and a daily-high contract about a day ahead. By the time the daily-high contract opens, the forecast has already priced most of tomorrow's heat. A dairy that buys it pays for the heat it was trying to insure against. This is the Hirshleifer effect (Hirshleifer 1971, *American Economic Review*, "The Private and Social Value of Information and the Reward to Inventive Activity"): public information that arrives before trading destroys the insurance a market could otherwise provide.

**Proposition (listing-horizon bound).** Let X be a contract's payoff, p_L = E[X | information at listing] its fair price at listing, and suppose a hedger whose loss is c·X plans before listing and can buy only at listing, at fair price. Whatever quantity they buy, the variance of their net position, measured before listing, is at least c²·Var(p_L). So the best possible hedge effectiveness is

  H = E[Var(X | F_L)] / Var(X) = 1 − Var(p_L) / Var(X),

the share of the contract's risk still unresolved at listing. Geography, binning, liquidity and capital (doc 16) only lower HE further.

**Estimator from prices alone.** For a binary contract, E[Var(X | F_L)] = E[p_L(1 − p_L)] and Var(X) = p_c(1 − p_c), with p_c the climatological probability. So H can be read off opening prices and climatology, with no outcomes needed, for any market. With outcomes, E[(X − p_L)²] (the Brier score of the opening price) gives a second estimate that also checks calibration.

**Corollary (aggregation makes it worse).** For a seasonal exposure built by buying many short-dated contracts, each at its own listing, the persistent part of the season (a heat wave, a wet pattern) is priced into every listing price, and only the day-to-day surprises are paid out. Those surprises are nearly independent and cancel over a season. So a season's H can be far below a single day's H. This is why the dairy ladder has HE 0.32-0.64 if bought before summer but 0.03 bought day by day (doc 24).

## 2. Pilot evidence (2026-11-06; `scripts/experiments/insurability_pilot.py`, under a minute with the cached Kalshi quotes (needs internet for ACIS station data), outputs `data/processed/insurability_pilot_*.csv`)

| Market family | Listing lead | Sample | H from prices | H from outcomes | Opening Brier skill vs climatology |
|---|---|---:|---:|---:|---:|
| Kalshi monthly rain, 9 cities, 2024-2026 | about 30 days | 129 | 0.99 | 0.95 | 0.09 |
| Kalshi daily high, NYC (Sep 2024 - Nov 2026), PHX and DFW (Feb - Nov 2026) | about 39 hours to close | 351 days, all seasons | 0.08 | 0.05 | n/a (brackets move with the forecast) |
| ... of which summer (Jun-Aug) | | 73 days | 0.14 | 0.12 | |
| ... of which winter (Dec-Feb) | | 45 days | 0.06 | 0.02 | |

Rain uses each market's opening price against its 1991-2020 climatological probability. Daily highs need a different unit: Kalshi centers each day's six 2 F brackets on the forecast, so judging a bracket against climatology is biased (the naive per-bracket H comes out above 1). Instead, each day's six opening prices give the market's implied forecast of the high and its spread, compared with the 1991-2020 spread of the high for that date. At listing the market already pins the high to about 2 F (typical miss 1.9 F), against 8 F for climatology. Summer has the most risk left (H 0.12-0.14) only because summer highs vary less, so climatology's spread is smaller (5.9 F). Doc 24 assumed a 3.5 F forecast error, so its day-ahead result (HE 0.03) is if anything optimistic.

**At least a tenfold gap in every season: 95-99% of a month's rain risk is still open when the contract lists, but only 5-8% of a day's heat risk (12-14% in summer).**

- **Rain: timing is fine, geography binds.** Almost all of a month's rain risk is still open when the contract lists, so the bound is not the problem. The problem is that the airport is 30-55 miles from the farm (docs 07, 16).
- **Temperature: geography is fine, timing binds.** Farm and airport seasonal heat load track closely (median R² 0.66, doc 24), but the contract lists after the forecast knows the answer.
- **Pooling fixes geography where the airport sees the regional weather.** Averaging PRF payouts over every grid within 75 miles of the airport raises holdout HE from 0.35 to 0.53 (Denver), 0.36 to 0.51 (Tampa), 0.40 to 0.56 (San Antonio) and 0.18 to 0.25 (Albuquerque). It does not help where summer storms are local (Dallas 0.16 to 0.15, Oklahoma City 0.14 to 0.08, Springfield below 0). A pool also removes the "which grid am I on" lottery: the spread of single-grid HE (interquartile 0.18-0.45 at Tampa) collapses.
- **Money is a separate, third limit.** The subsidy makes PRF about half price; Kalshi is priced near PRF's unsubsidized premium, and buying PRF while selling Kalshi loses money at all 11 farms (doc 23).

## 2b. What is new, checked against the literature (searched 2026-11-06)

| Prior work | What it shows | What it does not do (as far as we can read it) |
|---|---|---|
| Luo (2026), "Prediction Markets as Weather Hedges", SSRN 7138562 (**the course's own reference for 3a**; abstract only, doc 10) | For Kalshi daily temperature markets, geography is the first-order hedge error; building degree days from bins costs about 1% of variance | Treats the bin strip as if it could be held for the whole season. **Our pilot says the opposite ranking for temperature: geography is second-order (median farm-airport R² 0.66), and timing binds, because 92-95% of a day's risk is priced before the contract lists (351 days)** |
| Iturbide (2026), basis risk of a Kalshi daily rain contract for NYC rooftop bars, SSRN (abstract only, doc 10) | Settlement window and definition dominate; gains vanish under realistic execution | Single venue type, single contract; no listing-horizon measure |
| Crosier (2026), "Prediction Markets Beat the Weather Forecast on Tomorrow's High Temperature", [arXiv 2609.23969](https://arxiv.org/abs/2609.23969) | Kalshi's implied next-day high beats the National Blend of Models within the first hour of trading | Forecasting only; does not ask what that accuracy means for hedging. It is the mechanism behind our small H for daily highs |
| Hirshleifer (1971), AER; Ball (2013), J. Accounting Research | Public information arriving before trade destroys risk sharing; tested on earnings announcements | Never applied to prediction-market insurance or measured from contract prices |
| Luo, Skees & Marchant (1994), Review of Agricultural Economics; Carriquiry & Osgood (2012), J. Risk and Insurance; PRF climate-forecast study, J. Agricultural and Applied Economics | Weather forecasts before a crop-insurance sales closing date create intertemporal adverse selection; forecast-conditional premiums fix it | The insurer's side of the same coin: a fixed price set early is exploitable. A market that reprices continuously is not exploitable, but then cannot insure. Nobody has put the two side by side |
| Campbell & Diebold (2003), NBER w10141 | Weather risk is the unpredictable component of weather | Conceptual; no measure tied to a contract's listing date |
| Four Pillars Research (2026), turnover study of 1,265 Kalshi markets | Weather contracts show some hedging demand (low turnover, held to expiry) | Behavioral; no hedge-effectiveness or timing analysis |

We found no paper that (1) treats listing horizon as a component of event-contract hedge error, (2) estimates the unresolved share from opening prices, (3) shows that summing short-dated contracts cannot build seasonal cover, or (4) puts prediction markets and fixed-premium insurance on one timing trade-off. That is a literature search, not proof of novelty: SSRN full texts were blocked (HTTP 403), so Luo and Iturbide are judged from abstracts.

**The timing trade-off, in one line.** PRF sells cover by December 1 of the prior year (doc 01), so nearly all its risk is still open when it "lists", but a fixed price set that early invites buyers with forecasts. A prediction market reprices continuously, so it cannot be gamed that way, but by listing time the insurable risk is gone. Insurance needs a contract that is *priced* early; a market *lists* late.

## 2c. How the proposal meets the instructor's 3a criteria

Quoted from the course project list ("Tokenized Finance Projects Fall26"), idea 3a.

| Criterion (verbatim) | Where we meet it |
|---|---|
| "identify a real exposure and settlement rule" | USDA PRF grid-index payouts for 11 farms (docs 04b, 08); dairy milk loss from heat (doc 24); settlement on NWS CLI reports (doc 06c) |
| "build an executable replicating portfolio using bid/ask prices" | Optimizer and live order-book walk with fees and capital cost (docs 15, 18, 23); fill checks against fresh books only |
| "decompose hedge error into binning, geography, settlement source, liquidity, and capital cost" | Doc 16 already does all five; the final paper adds **listing horizon** as a sixth term |
| "study which types of insurance exposures can be replicated well and which require new contracts or market mechanisms" | The space-versus-time map (rain: space binds; heat: time binds), with the fixes tested: earlier listing, pooling, priced vault |
| "theory is useful for spanning bounds or an optimal parametric payout" | The listing-horizon bound is a spanning bound in time: no portfolio bought at listing can exceed H |

The rubric is the instructor's written criteria; we have not seen a grading scheme beyond it.

## 3. What the final paper would show

1. **Theory (Section 2 of the paper).** The listing-horizon bound, the price-only estimator, and the aggregation corollary, with the Hirshleifer connection. Short proofs; a two-factor (slow + fast) model gives a closed form for the seasonal H.
2. **A map of insurable event markets.** H for every Kalshi weather family with history: monthly rain, daily high and low, monthly snow, hurricanes. If time allows, one non-weather family (monthly CPI or Fed decisions) to show the measure is general. Each family gets a point on a "space vs time" chart: geography R² on one axis, H on the other. Only the top-right corner is insurable.
3. **The full error budget with the new term.** Add listing horizon to the doc 16 decomposition (geography, settlement source, monthly binning, strikes, depth, budget, now timing) for rain and temperature.
4. **Design: three fixes, each tested.**
   - *List earlier:* a monthly "days above 95 F" contract listed in spring. H is about 1 at that lead (forecast skill beyond 2-3 weeks is small); doc 24's ladder backtest prices it.
   - *Pool space:* a mutual pool (a tokenized vault in the course's framing) that insures many ranches and reinsures the regional part on Kalshi. Report pool HE vs size and the capital the vault needs for a 1-in-100-year shortfall, with and without the Kalshi reinsurance.
   - *Price the remaining risk:* what a vault would have to charge to sell seasonal cover it cannot hedge, at today's capital cost, compared with the PRF premium.
5. **Demo.** The app gets a "can this be insured?" panel: pick an exposure, see geography R², H, and the binding limit.

## 4. Why this should grade well

- **Original question with a general answer.** Not "does Kalshi replicate PRF" (no), but "which event markets can insure anything, and why", with a measure any venue can compute from its own prices.
- **Theory where the rubric asks for it:** a spanning-type bound, a closed form for aggregation, and a classic result (Hirshleifer) applied to a new setting.
- **Rigorous empirics already in place:** out-of-sample HE, executable prices, fees and capital cost, 400+ tests; two independent estimates of H that agree on rain.
- **It turns our negative results into one story:** rain fails on space, heat fails on time, the subsidy wins on money; pooling and earlier listing are the fixes.

## 5. Plan to 2026-12-15

| Week | Deliverable | Owner (proposed) |
|---|---|---|
| Nov 17-23 | Present Milestone II; move pilot scripts into `src/agri_hedge/insurability.py` + `scripts/run_insurability.py` with tests | Jack |
| Nov 17-23 | Write up the proposition, estimator and aggregation corollary (theory section) | Maya |
| Nov 24-30 | Pull opening prices for all Kalshi weather families (rain, high, low, snow, hurricanes); compute H and geography R²; space-vs-time map | Jack |
| Nov 24-30 | Pooling study: pool HE vs size for all sites; vault capital at 1-in-100 with and without Kalshi | Evan |
| Dec 1-7 | Error budget with the timing term (doc 16 extended); earlier-listing contract backtest | Maya, Evan |
| Dec 1-7 | App panel "can this be insured?" | Jack |
| Dec 8-15 | Paper: problem, Milestone I "no", the three limits, the bound, the map, the fixes | all |

## 6. Risks and how we handle them

- **Opening quotes are thin.** Use the first quote with a spread of 20 cents or less, and report H from prices and from outcomes side by side; they agree for rain (0.99 vs 0.95).
- **Kalshi history is short (2024-2026).** H needs only cross-sectional opening prices, not long histories; climatology comes from 1991-2020 station records.
- **Climatology vs a moving climate.** Report H with a 1991-2020 and a recent-15-year climatology.
- **Daily-high brackets move with the forecast.** Handled by working with the implied distribution of the high, not single brackets (Section 2). Other bracketed families (daily lows, snow) need the same treatment.
- **Daily-high sample.** 351 days: every 5th settled day for NYC since Sep 2024 plus Kalshi's 2026 Phoenix and Dallas series (they launched in Feb 2026), and the last 40 days for all three. The full study uses every settled day for every city.
- **Rain sample.** 129 monthly markets with a quote before the month began, 9 cities, 2024-2026: small but enough for a 0.95-0.99 vs 0.05-0.08 contrast. The full study adds the remaining stations' climatology (30 Kalshi rain cities).
