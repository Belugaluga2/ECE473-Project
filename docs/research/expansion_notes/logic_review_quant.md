# Logic review: quantitative soundness of doc 25 (second pass)

Review date: 2026-11-20. Scope: `docs/analysis/25_weather_hedging_expansion.md` (sections "Second pass: new lenses", "Head-to-head comparison", "Demand estimate", "Pairing mostly buys diversification"), the four scripts behind them, their CSVs in `data/processed/`, and the methods notes `lens_quant.md` and `demand_inputs.md`. Everything below was recomputed from the committed CSVs or by importing the scripts' functions in memory with `.venv/bin/python`; no script `main()` was run and no repo file other than this note was written.

## Verdict

**Sound with fixes.** The arithmetic is right almost everywhere: every CSV-backed number I spot-checked reproduces, the Monte Carlo and head-to-head matrix are computed correctly, and the hedge fits are honestly out of sample apart from small, disclosed leaks. The problems are in what the numbers are said to mean. Two headline sentences are contradicted by the report's own CSVs (issues 1 and 2), the wet:dry 1:80 ratio compares two different wealth frames (issue 3), the demand "central" values sit near the 80th-90th percentile of their own Monte Carlo (issue 4), and the ENSO β cannot distinguish "no tilt" from "full tilt" (issue 5). None of these reverses the report's direction (distribution over risk-bearing), but each overstates how firmly a number supports it.

## Issues

### 1. "The four together take the top three slots in almost every draw" is false: it is 66% of draws. Severity: blocker (headline claim)

- Evidence: doc 25 line 20. `expansion_compare_summary.csv`: `p_top3_weak_link` for the four is 0.754, 0.694, 0.652, 0.542, which sums to 2.64 of 3 slots; `consumer_embedded` is in the top three in 26.2% of draws, so the claim cannot exceed 74%.
- Recomputed with the script's own `CRITERIA`, weights and noise (20,000 draws): all three top slots belong to the four in **65.7%** of draws (weak-link), 60.0% (additive), 54.5% (uniform weights). What is true: one of the four is *first* in 94% of draws.
- Fix: replace with "one of the four ranks first in 94% of draws, and all of the top three are from the four in about two thirds." Have `run_expansion_compare.py` compute and write this joint probability so the sentence is sourced.

### 2. "No strategy that pairs opposite weather hedgers makes the top half" is false on the report's own table. Severity: blocker (headline claim)

- Evidence: doc 25 line 14 and line 444 ("Every pairing strategy ranks in the bottom half. That covers the city snow book (#7)..."). There are 14 strategies, so #7 is the top half. `expansion_compare_summary.csv`: `snow_mga` `rank_weak_link` = 7 (2.469, against 2.457 for #8, a 0.012 margin); `rank_additive` = 8.
- The on-exchange maker (#6) is also a two-sided strategy that nets YES-low against NO-high, so "pairing" needs a definition that excludes it.
- In the simulation `snow_mga` is in the top seven in 32% of draws, `solar_pair` in 28%, `onexchange_maker` in 63%.
- Fix: say "no own-book pairing strategy ranks above #7, and none reaches the top three in more than 1% of draws" (true: 0.8%, 0.8%, 0.0%).

### 3. The wet:dry 1:80 ratio and "ranchers are the exception (1.4x)" compare different wealth frames. Severity: should-fix (changes a headline number by about 25x)

- Evidence: `run_weather_demand.py` lines 393-411 and 457-467 take rancher WTP from doc 24's grid, where wealth is 1.25, 2 or 4 dollars **per dollar of the month's insured value** (`src/agri_hedge/design.py` lines 20-21, 34). Wet-side firms in the central ("broad") frame get W = cash buffer + a month's profit (lines 482-485): the median restaurant has W = $80,900 against a maximum payout of about $590-$795, so W is roughly 100 times insured value (recomputed: max payout / W = 0.007).
- So the rancher is modeled in a narrow frame (wealth 1.25-4x insured value) and the restaurant in a broad one (about 100x). The rancher's WTP of 1.42 against the restaurant's 1.004 is mostly this choice, not a difference in exposure. A rancher with land equity many times one month's gap cover would, under the same broad frame, also have WTP close to 1.00.
- The like-for-like row already exists: narrow frame for both gives 0.31 (about 1:3; `weather_demand_segment.csv` row 23, `wet_dry_premium_standalone` 0.3134). Broad for both cannot be computed from doc 24's grid but would cut the dry side sharply.
- Fix: lead with the frame-matched 1:3 and present 1:80 as "rational wet firms against narrow-frame ranchers", or rerun doc 24's WTP with rancher wealth at 50-100x insured value and report that. Reword "Ranchers are the exception: they would pay up to about 1.4x" to say this follows from doc 24's wealth convention. The "largest rational demand found" bullet (line 327) needs the same caveat.

### 4. Demand "central" values are not central: they sit near the top of their own P10-P90 bands. Severity: should-fix

- Evidence: doc 25 segment table, e.g. restaurants "$1k / **$350k** / $445k". Re-running `monte_carlo` in memory (seed 473, 400 draws) gives national standalone medians of: restaurants **$30k** (central $350k), golf **$5.8M** ($12.1M), snow cities $0.73M ($1.6M), ranchers $9.1M ($12.1M), wet:dry ratio **0.0075**, about 1:133 (central 0.012).
- Cause: the central case sets every parameter at its mode, but several triangular ranges are one-sided (`m_standalone` 1.1/1.2/1.6, `rest_rebound` 0.5/1.0/1.0, `elasticity` -2.5/-0.77/-0.66), and demand is the tail of a lognormal, so the mode-of-inputs is far above the median output.
- The bands also omit the two parameters that matter most. `sd_ln_gamma` and `sd_ln_wealth` are fixed at (0.7, 1.0) (`P` dict, lines 87-88; `draw_params` skips lo == hi) and are missing from the sensitivity table. Moving them to (0.5, 0.7) or (1.0, 1.3) moves restaurants from $9k to $2.2M (230x), golf from $5.6M to $18.5M, and wet:dry from 0.003 to 0.032. The wealth frame is also fixed at broad in every draw.
- Fix: report the MC median next to (or instead of) the modal case and call the modal case "all inputs at their most likely value". Give the two sds a range, include them in `SENS` and in the draws, and say in the text that bands exclude the frame.

### 5. The ENSO β regression cannot tell "no tilt" from "full tilt", and doc 25 does not say so. Severity: should-fix

- Evidence: `run_expansion_lenses.py` `tilt_regression` (lines 420-451); `expansion_lens_enso_regression.csv` (β -0.216, 90% CI -0.415 to 0.176); doc 25 lines 34 and 68.
- The regressor (El Niño-conditional minus climatological P(rain > K)) is estimated from 19-20 seasons per station. From `expansion_lens_enso_nov2026_quotes.csv`: its variance across the 213 quotes is 0.0062, and its mean binomial sampling variance, p(1-p)(1/n_c - 1/75), is 0.0048. Reliability is therefore about **0.23**. A split-half test on the El Niño seasons gives a correlation of -0.01 between the two halves' regressors, i.e. reliability indistinguishable from 0. Even if Kalshi priced the true El Niño tilt one for one, the expected estimate would be about 0 to 0.25.
- The 90% CI is not a CI for β. The bootstrap resamples seasons, which re-noises the regressor, so each bootstrap β is attenuated again; that is why the point estimate (-0.22) sits near the lower edge of its own interval (bootstrap median -0.13). It also holds the quotes fixed, so it carries no quote noise, and it treats 213 quotes from 34 ladders as independent rows although strikes within a ladder are cumulative.
- `lens_quant.md` does note that noise "biases β toward 0" and that the bootstrap covers climatology only, but then concludes "none is near 1", which the CI cannot support. Doc 25 quotes β and the CI with no attenuation caveat at all (grep for "attenuat", "toward 0": no hits).
- Minor inconsistency: the point estimate uses `clim51` over 1951-2025, while the bootstrap resamples seasons 1951-2024 (line 428); the same regression on 1951-2024 gives -0.234.
- The Brier comparison (0.131 against 0.118-0.123) is 35 events from one winter with no interval; `clim51` includes December 2025 itself. It supports "not shown to be sharper", not "was not sharper".
- Fix: in doc 25 say "the test has almost no power: the regressor's reliability is about 0.2 or less, so a fully ENSO-aware market would also give β near 0". Drop "none is near 1" from `lens_quant.md`. For the Dec-Feb rerun, shrink the conditional climatology (pool stations by region, or regress on a fitted ENSO effect), use one summary per station (implied mean) rather than every strike, and bootstrap stations as well as seasons. December has a far stronger true signal (1.89x), which is the real remedy.

### 6. The weak-link score does not do what the text says, and the ranking turns on a class-deadline criterion. Severity: should-fix

- Evidence: `run_expansion_compare.py` `weak_link` (lines 82-84); doc 25 lines 382.
- "A business with one fatal flaw fails however good the rest is" is not implemented. On a 1-5 scale a weighted geometric mean penalizes a 1 only mildly: a 1 instead of a 3 on a 0.12-weight criterion multiplies the score by 3^-0.12 = 0.88. Two of the four leaders carry a 1 (508(h) on time to proof, promotions on market size) and still rank #3 and #4. Weak-link and additive ranks differ by at most two places. The geometric mean also assumes a ratio scale; the result depends on labelling the worst case 1 rather than 0.
- `time_to_proof` is "can be shown working by the Dec 15 paper". That is a course constraint, not a determinant of whether a strategy succeeds, yet it carries weight 0.12. Without it, 508(h) leads clearly: weak-link 3.73 against 3.25 (software), 3.18 (lender-financed), 3.06 (consumer-embedded), 2.99 (promotions). Under the additive rule with noise, 508(h) already has the highest P(first) (32.3% against 30.0%).
- Fix: describe weak-link as "a mild penalty on low scores", or add a real gate (drop any strategy with a 1 on legal path or demand). Report the ranking with and without `time_to_proof`, or rename the question to "which should the team pursue by Dec 15".

### 7. P(first) and the head-to-head odds measure sensitivity to the team's own scores, not likelihood of success. Severity: should-fix (framing)

- The computation is correct. Re-simulating with an independent seed reproduces P(first) 0.318 / 0.219 / 0.264 / 0.142 and head-to-head 0.562 / 0.558 / 0.506, matching `expansion_compare_summary.csv` and `expansion_compare_h2h.csv`. `ranks_desc`, `h2h_matrix` (ties half) and the Dirichlet(40 x w) weights (sd about 0.05) are right.
- What it measures: almost all of the spread comes from the ±1 score noise, not the weights. With weights perturbed and no score noise, software is first in 50% of draws and promotions in 4%; with noise, 32% and 14%. So "each ranks first in 14-32%" is largely a statement about the assumed noise level (0.4 chance of a move on every cell).
- Noise is the same for every cell. A measured score (hedge quality from an out-of-sample HE) gets the same ±1 as a guess (legal path, defensibility). Noise is also independent across strategies, although the top three share the same underlying facts (Companion HE 0.61, the Texas 27% already-insured fact, the same engine); a shared error would move them together and would not show up in their odds against each other.
- Criteria overlap. Across the 14 strategies, `capital_light` correlates 0.54 with `pricing_risk`, 0.47 with `time_to_proof` and 0.43 with `legal_path`; `hedge_quality` correlates 0.53 with `time_to_proof`; `demand_evidence` 0.48 with `market_size`. "Needs an insurance balance sheet" is counted under both capital and legal (the report says so itself at line 444: "capital and legal both score 2"), a combined weight of 0.24. This double count is what sinks the own-book strategies.
- Clipping at 1 and 5 makes the noise one-sided at the ends. The effect is small (expected weak-link shift between x0.96 and x1.03; `snow_mga` -4%, `intl_aggregator` +3%) and does not change any rank that matters.
- Fix: say in the text that the percentages are robustness to the scoring, not probabilities of commercial success. Give evidence-backed cells less noise than judgment cells. Merge or down-weight capital and legal for strategies where one fact drives both.

### 8. "Out-of-sample HE 0.65-0.77 vs 0.53-0.62" is the LOYO figure; label it, and note the residual leaks. Severity: minor

- Evidence: doc 25 lines 26 and 61; `expansion_lens_lender_books.csv` rows "footprint (100 mi)", calendar year, phase all. LOYO pooled 0.648-0.771 against median farm 0.525-0.622. The true 2001-2025 holdout rows give pooled 0.625-0.786 against median 0.497-0.586. Both support the claim; the holdout is the cleaner one and should be quoted alongside.
- What I checked for leakage and found clean: holdout knee, frontier and fit all use 1951-2000 only (`fit_package` lines 202-209); footprint months are fixed in advance (Nov-Feb), not selected; strikes are Kalshi's listed strikes; grids are a seeded random draw; LOYO refits without the scored year.
- Residual leaks, all small and inherited from doc 21: (a) LOYO knee budget is chosen on all years (line 214); (b) model prices `q` use the 1991-2025 window (`hedge_builder.FAIR_WINDOW`), which contains every holdout test year, and feed the budget-constrained leg choice; (c) for the 11-farm LOYO book, months are picked on all years by their own LOYO HE (selection on the scored sample). HE ignores price, so (b) cannot inflate HE much.
- The four footprint stations (DFW, OKC, SAT, SGF) are not a random sample of stations; say how they were chosen.
- Like-for-like: pooled HE of a sum against the median of single-farm HEs is a fair statement of the pooling gain, because the script also reports `he_if_uncorrelated` (0.52-0.62), which equals the median to within 0.01. The 0.12-0.15 gain is the cross-farm covariance effect and is real. The 11-farm holdout and LOYO books contain different farms (10 and 9) and different months, so those two rows should not be compared with each other.
- Fix: write "pooled HE 0.65-0.77 (leave one year out; 0.63-0.79 on the 2001-2025 holdout)".

### 9. Solar: "an irradiance index removes 57%" is a zero-basis payoff-shape number, and the 1.75 vs 1.81 gap is noise. Severity: minor

- Evidence: `run_expansion_lenses.py` lines 643-659. Plant energy is defined as the NASA POWER cell's irradiance x days, and the "irradiance put" is written on that same series. The 57% is therefore the share of a variable's variance that a 30th-to-5th-percentile put on itself captures; a linear swap on the same index would give 100%. It says nothing about a real plant's basis to an index. The 9% for the rain ladder is a genuine cross-variable result (median of 20 station-months, range -0.16 to 0.39).
- The call and irradiance-put strikes are full-sample percentiles (`rx.call_terms`, `rx.put_terms`) inside a fit labelled LOYO. Small, but it is a strike chosen on the scored sample.
- Netting: 95% capital 1.75 (pair) against 1.81 (independent put) are medians of 20 station-months, each a 95% quantile of 42 years. From `expansion_lens_solar_netting_station_month.csv` the per-station-month difference has mean 0.11 and sd 0.47, and the pair is better in only 55% of them. The report already reads this as "small"; it should say "indistinguishable". The worst-year gap is robust (pair 1.70-2.42, independent 2.52-3.41 across all 20), though partly by construction: a put and a call on one index cannot both pay.
- Premiums are scaled to the full-sample mean payout (in-sample pricing), the same framing the first-pass review faulted.
- Fix: write "an irradiance put with no basis removes 57%; a real plant would get less", and "the 95% figures do not differ".

### 10. The narrow-frame figures use the CARA expansion outside the range where it was checked. Severity: minor

- Evidence: `crra_check` (lines 548-580) calls `evaluate(R, C)` in the broad frame only; I reproduce its 0.0004. In the narrow frame the median restaurant has W = $4,200, mean loss 16% of W, p95 loss 27% and maximum payout 14%. "Losses are small next to W" does not hold there, and with W lognormal (sd of logs 1.0) roughly 9% of firms have W below their p95 loss, where CRRA utility is undefined.
- The $134M / $39M "ceiling" is therefore an extrapolation; exact CRRA would be higher, so it is not a ceiling.
- Fix: say the expansion was validated for the broad frame only, or run the exact check in the narrow frame.

### 11. The take-up formula applies price sensitivity twice. Severity: minor (assumption-labelled, but it drives the result)

- Evidence: line 536, `tu = t0 * m ** elasticity * S`. `t0` is an observed take-up rate (CME 10%, BI cover 35%), which already reflects who was willing to pay; `m^ε` is an observed price response; S(m) is a second, modelled price response (share with WTP > m). For restaurants S = 0.0015, so the product is 0.026% and the empirical inputs are irrelevant. That is why the report has to override the model with a 2% "best guess".
- Doc 25 line 222 reads "t₀ = 0.20 at m = 1.2", which looks as if t₀ were take-up at 1.2x; in the code it is take-up at m = 1 (the factor at 1.2 is 0.87).
- The rancher screen is a nine-point grid (three γ x three wealth), so rancher take-up is a step function of price.
- Fix: present the model as two separate estimates, a rational screen (S) and an empirical analog (t₀·m^ε), instead of their product; fix the t₀ wording.

### 12. Small numeric and wording slips. Severity: minor

- Doc 25 line 198: "$0.58M against $8.8M of rancher premium". `weather_demand_city_month.csv` gives $8.62M (the table two sections later says $8.6M). The 1:15 ratio is right (14.9).
- Line 44: "About 85% of that drop comes from writing any second independent contract." (3.57 - 1.96) / (3.57 - 1.74) = 88%; with 1.76 it is 89%.
- Best-guess restaurant table: a POS-embedded product is priced at the standalone 1.2x; the model's own embedded multiple is 1.3x (+8% premium).
- The best-guess table's contracts per month (1.68M) is an all-month average, compared with November depth.
- `expansion_lens_lender_booksize.csv`: at n = 40 every sub-book is the full book, so p10 = p90; the band in the figure collapses there by construction.

## What I checked and found correct

Leakage and method:
- Holdout hedges (`fit_package`, mode "holdout") use only 1951-2000 for the frontier, the knee and the fit; scored on 2001-2025.
- LOYO payouts (`loyo_leg_payouts`) refit without the scored year; the "one hedge refit to book" row is also LOYO.
- `hedge_effectiveness` is 1 - Var(y - h) / Var(y) on common years, used consistently.
- `book_stats`: pooled HE, `he_if_uncorrelated` and `he_limit` formulas are right; equal weighting is a true equal weighting because footprint farms share one gap size.
- CARA WTP algebra: with the firm holding ρ x the station hedge and Cov(L, h) = Var(h), the variance removed is ρ²·HE·Var(L), and the multiple 1 + (γ/W)·ρ·HE_s·Var(L) / (2·E[h]) matches both the code (`K`, line 526) and the doc's formula. ρ is the variance-minimizing hedge ratio.
- `crra_check` reproduces: maximum |exact - CARA| = 0.00043 in the broad frame.
- Comparison engine: `additive`, `weak_link`, `ranks_desc`, `h2h_matrix` are correct; my independent re-simulation matches to within Monte Carlo error.
- The two-distant-puts baseline, whose script was not committed: I rebuilt it from `rx.unit_payouts` over the same 2,943 station-pair-months and get 95% capital 1.96 and worst year 3.50, against 1.76 and 2.17 for the same-station pair (doc: 1.96 / 3.50 / 1.76 / 2.16).

Numbers recomputed from the CSVs (all match unless listed under issues):
1. P(first) 14-32% for the four (0.139, 0.221, 0.267, 0.320).
2. Head-to-head among the four 51-66%; against #5 and #6 69-94%.
3. Uniform-weight P(top 3) 54-68%; old #1 lender book 13%.
4. Footprint pooled HE 0.65-0.77 against median farm 0.53-0.62 (LOYO rows).
5. 11-farm dollar-weighted holdout HE 0.53 (0.528); equal-weighted 0.83.
6. Basis-error correlation ρₑ 0.50-0.60 (LOYO; holdout 0.41-0.61).
7. Solar: winter irradiance-rain correlation -0.44; YES ladder 0.089; irradiance put 0.569.
8. Solar netting: 3.62 / 1.75 / 1.81; worst year 2.00 / 3.08.
9. ENSO: β -0.216, CI -0.415 to 0.176; Brier 0.131 against 0.123 and 0.118.
10. Netting summary: one put 3.57; pair 1.74; day-count pair 1.84; full collateral 5.68 against 2.68; snow and temperature pairs 1.75 and 1.74 against 3.32 and 4.14.
11. Dry-month correlation 0.54 under 100 miles, -0.001 beyond 1,000.
12. Demand: ranchers $12.05M (embedded $23.5M); wet national $12.55M; golf $12.14M; restaurants $350k; snow cities $1.6M; narrow-frame wet $133.8M.
13. Wet:dry 0.012 (P10-P90 0.0024-0.0243), i.e. 1:83, 1:417 to 1:41.
14. Restaurant best-guess table: $190 x 12 x 1.2 = $2,737; buyers 1,057 / 2,113 / 5,284 and 2,642 / 5,284 / 13,210; premium $2.9M / $5.8M / $14.5M and $7.2M / $14.5M / $36.2M; contracts 0.84M / 1.68M / 4.20M (2,113 x $795).
15. 17x depth: 1.68M / 98,607, and 98,607 is YES depth at the same Kalshi-23 stations, so the comparison is like for like.
16. 1:15 at the eight shared stations, Nov-Feb: $577.6k against $8.62M = 1:14.9; 1:6 at 5%.
17. Rancher demand about 330x post-rewards NO depth: 6,192,536 / 18,918 = 327.
