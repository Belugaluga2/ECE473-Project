# Rain-to-loss model: what a farm loses in a dry year, and how much PRF and Kalshi cover

**Proposal cell:** Milestone 2 foundation (loss model for hedge sizing and contract design)  |  **Status:** DRAFT (model and backtest done; not fact-checked by an independent pass)  |  **Last updated:** 2026-11-01

Code: [`src/agri_hedge/loss_model.py`](../../src/agri_hedge/loss_model.py) (model), [`scripts/run_loss_model.py`](../../scripts/run_loss_model.py) (backtest), [`tests/test_loss_model.py`](../../tests/test_loss_model.py) (78 tests). Outputs: `data/processed/loss_model_parameters.csv`, `loss_model_farm_year.csv` (1969-2025, every variant, merged with PRF and Kalshi payouts), `loss_model_coverage.csv`, `loss_model_hay_validation.csv`, figure [`l1_loss_vs_payouts_2015_2025.png`](../figures/l1_loss_vs_payouts_2015_2025.png).

## Key findings

- **We now have one reusable function from rain to dollars.** Given a farm from `farms.yaml` and rain (PRF interval indices, or monthly rain plus normals), `build_farm_model(farm).loss_usd(rain)` returns the dollar loss (positive) or gain (negative) versus a normal year. It covers interval timing weights, dry-versus-wet asymmetry, saturation in wet years, irrigation share, and three ways of valuing forage. A row-crop path (`load_rowcrop_model`) does the same for corn and soybeans from doc 03a, including the excess-rain penalty.
- **Every parameter comes from existing project research. Nothing was re-fitted here.** Elasticities are the doc-03b `scen_*` values (0.14-0.89). The asymmetry comes from the quadratic fits already stored in `crop_rain_sensitivity_other.csv`. With asymmetry off and gains floored at zero, the model reproduces doc 04b's forage-loss proxy to the cent for all 825 farm-years. `run_scenarios.py` now imports these shared functions instead of keeping its own copies.
- **The asymmetry is mild for most farms but strong in Missouri.** The curvature g ranges from 0 (Florida, where no asymmetry is detectable) to −1.92 (Missouri hay). For Missouri, a season at 80% of normal rain costs about 2.3 times what a season at 120% gains. At 70% versus 130% the ratio is 3.6, because Missouri gains saturate at a season index of 126.
- **The model points the right way against real yields, but it overstates the size of swings.** For the four hay farms, the predicted production change correlates 0.34-0.57 (central variant; 0.34-0.59 across variants) with detrended NASS statewide hay yields over 1975-2025. Part of the gap is expected, because state yields average many farms and the model uses one grid's rain. The regression slope of actual on modeled is 0.46-0.92 (central variant): the farm-grid model swings more than the state average. This check is not independent: the hay elasticities were fitted on statewide data over the same years (doc 03b).
- **Asymmetry helps a little in Texas and Oklahoma and is too strong in Missouri.** Adding curvature raises the hay-yield correlation from 0.45 to 0.46 (TX) and from 0.56 to 0.57 (OK), and cuts Oklahoma's RMSE from 0.142 to 0.122. In Missouri it lowers the correlation (0.44 to 0.40) and overstates drought years (−15% modeled vs −11.6% actual in the driest fifth of years). It still cuts Missouri's RMSE (0.124 to 0.108), mainly because saturation stops the model from predicting wet-year gains that never came.
- **Measured against modeled loss, both PRF and the Kalshi hedge over-pay, and neither misses a loss year.** Over 2015-2025, 11 farms:
  - At the doc-03b/04b value basis (hay at market price, grazing at cash rent), modeled losses total $158k. PRF paid $1.11M (7.0 times) and the Kalshi hedge $1.20M (7.7 times).
  - In none of the 34-35 farm-years with a material modeled loss (more than 5% of normal value) did PRF or Kalshi pay zero.
  - When grazing is valued at the cost of replacement hay, modeled losses rise to $700k. PRF then pays 1.6 times the loss, but only 59% of loss dollars are covered in the year they happen (Kalshi: 57%).
- **PRF tracks modeled loss better than the Kalshi hedge does.** The median farm correlation between yearly payout and modeled loss is 0.78 for PRF and 0.52 for Kalshi. With growth-curve timing it is 0.65 and 0.49.
  - Kalshi pays more often in years the model calls a gain: 58 farm-years versus 48 for PRF. It also sends 42% of its dollars to those years, against 22% for PRF.
  - In Florida the Kalshi hedge is uncorrelated with modeled loss (−0.20 grazing, −0.06 hay).
  - Part of PRF's edge is mechanical. In the central variant, the loss model and PRF weight the same intervals.
- **For most farms the payouts are too big to reduce risk.** Measured on modeled loss alone, the payouts add more variance than they remove on about half the farms. PRF lowers the standard deviation of (loss − payout) below that of loss for 5 of 11 farms at the rent value basis and 8 of 11 at the replacement basis. The Florida farms are the extreme: PRF pays 10-39 times the modeled loss, because hay yields there barely respond to rain (elasticity 0.14-0.15).
- **Implication for Milestone 2:** size a Kalshi hedge from this loss model, not by copying PRF's payout. A replica of PRF inherits PRF's over-payment relative to the loss. Over 2015-2025, PRF paid 2.8-39 times modeled loss per farm at rent value, and 1.0-12 times with growth timing at replacement value. So a loss-sized hedge would be smaller, and cheaper, than doc 09's $107k-per-year replica on most farms. We have not priced one.

## The model

### API (all in `agri_hedge.loss_model`)

| Call | What it does |
|---|---|
| `load_farms()`, `load_sensitivity()` | read `farms.yaml` and `crop_rain_sensitivity_other.csv` |
| `build_farm_model(farm, timing="allocation" \| "growth" \| {interval: w}, value_basis="rent" \| "replacement" \| "protection", curvature=True \| False \| g, excess_penalty=False)` | returns a `FarmLossModel` |
| `FarmLossModel.loss_usd(index, gains=True)` | dollar loss (+) / gain (−) for a year×interval DataFrame of PRF-style indices (100 = normal) or one year's `{interval: index}` |
| `FarmLossModel.loss_from_monthly(monthly, normals)` | same, from monthly rain (year×month) and monthly normals; e.g. Kalshi station rain |
| `FarmLossModel.table(index)` | season index, production change and loss per year |
| `FarmLossModel.marginal_loss_per_point(index)`, `.marginal_loss_per_inch(index, interval_normals_in)` | one year's $ of extra loss per index point (or per inch) that each weighted interval falls: the local slope a hedge optimizer needs (0 on the wet plateau and at the −100% floor) |
| `production_response(x, e, g, excess_penalty)` | the response curve on its own |
| `interval_index_from_monthly`, `weighted_index`, `growth_timing_weights`, `curvature_for_row`, `value_per_acre`, `irrigated_share_of` | building blocks |
| `forage_loss_proxy`, `elasticity_for`, `weighted_index` | moved unchanged from `scripts/run_scenarios.py`, which now imports them |
| `load_rowcrop_model(crop, state, spec)` → `RowCropModel.yield_change_bu(rain)`, `.loss_usd(rain, acres, irrigated_share)` | corn and soybeans, IL/IN/IA, doc 03a regressions |
| `irrigated_share_for(state, crop)` | 2022 Census irrigated share |

### Forage and hay farms

For each year:

1. **Season index.** R = Σ_k w_k × I_k / 100, where I_k is the two-month interval rain index (100 = normal) and the weights w_k sum to 1 over non-overlapping intervals. Monthly rain is first converted to interval indices as 100 × (rain in the two months) / (normal of the two months), the PRF construction.
2. **Production response.** With x = R − 1, the fractional production change is dP = e × (x + g × x²).
   - e is the farm's elasticity. g ≤ 0 is the curvature: with g < 0 a dry anomaly costs more than an equal wet anomaly gains.
   - Saturation: for g < 0 the curve peaks at x* = −1/(2g). Beyond the peak the response is held flat by default, because very wet years cannot raise forage much (doc 03b section 6). `excess_penalty=True` lets it fall instead.
   - dP is floored at −1.
3. **Dollars.** loss_usd = −dP × value per acre × acres × (1 − irrigated share).

**Timing weights.** Two built-in choices:
- `allocation` uses the farm's PRF interval allocation. This is the weighting the doc-03b hay elasticities were fitted against, and the default.
- `growth` derives weights on the six calendar pairs (Jan-Feb, Mar-Apr, ..., Nov-Dec) from NRCS monthly growth curves. Rain in month m is credited half to growth in m and half to growth in m+1. This is independent of the insurance election, so it is the fairer test of whether PRF pays when the grass is actually short.

**Value basis** (doc 03b section 7):
- `rent`: farms.yaml value. Hay is yield × state price; grazing is county pasture cash rent.
- `replacement`: grazing only. Production × 25% harvest efficiency × state hay price, i.e. the cost of buying hay for the grass that did not grow. Hay farms keep the rent value.
- `protection`: county base value × productivity factor, the doc-04b "cbvpf" basis.

**Irrigation.** Irrigated acres are treated as rain-insensitive (doc 03a section 7: irrigated acres "barely respond"). An `irrigated_share` key wins; otherwise an `irrigation_practice` of "irrigated" gives 1 and anything else gives 0. All 11 farms are 0, because PRF grazing has no irrigation practice and all hay farms are non-irrigated.

### Corn and soybeans

`RowCropModel` evaluates the doc-03a state regressions month by month: Δyield = Σ b1 (r − n) + b2 (r² − n²).
- Quadratic months (June, July, August) peak at r* = −b1/(2 b2). Rain above that lowers yield: the excess-rain penalty.
- May is linear with a negative slope (planting delays). Sep-Apr is linear.
- The default spec is the rain-only 1980-2025 re-estimate, as doc 03a Implication 3 recommends for sizing a rain-only hedge. The spec holding temperature fixed is available too.
- Irrigated acres are removed with `irrigated_share`. Dollars use the CSV price ($4.70 corn, $12.00 soybeans).
- Tests check the model against every "exact +1/−1/−2 in" value in the CSV notes (48 month rows, 144 values), to within 0.05 bu/ac.

There is no corn farm in `farms.yaml`, so the row-crop path is not part of the backtest. Table F below runs it on the 2012 drought as a check.

## Numbers table

Every number used to build or calibrate the model. "Repo" = read from a committed project file; "DERIVED" = arithmetic here.

| Quantity | Value | Units | Region / period | Source | Verification |
|---|---|---|---|---|---|
| Farm elasticities e | DFW_hay 0.486; DFW_graze 0.573; SAT 0.477; OKC_hay 0.494; OKC_graze 0.672; SGF_hay 0.397; SGF_graze 0.462; DEN 0.742; ABQ 0.888; TPA_graze 0.155; TPA_hay 0.144 | - | per farm | `crop_rain_sensitivity_other.csv` rows `scen_*`, column `rain_elasticity` (doc 03b section 8) | Repo (03b: COMPUTED/DERIVED, not fact-checked) |
| Quadratic +1 / −1 / −2 in used for curvature | TX hay Apr-Sep +0.059/−0.061/−0.125 t; OK hay Apr-Sep +0.035/−0.038/−0.079 t; MO hay Apr-Jun +0.031/−0.041/−0.093 t; Grady hay +0.047/−0.052/−0.109 t; Parker forage +46/−53/−114 lb; Elbert +70/−73/−150 lb; Torrance +35/−40/−84 lb; FL hay +0.013/−0.007/−0.008 t | yield units | 1975-2025 (hay), 1982-2019 (Grass-Cast), 1960-2018 (Grady) | same CSV, `valid_range_note` of the rows named in table A | Repo (03b: COMPUTED) |
| Window normals for curvature | 16.55, 22.0, 13.84, 12.1, 11.76, 9.8, 6.85, 10.43 (same order) | in | same | same CSV, `baseline_precip_in` | Repo |
| Curvature g = (a/b) × N | −0.28, −0.90, −1.92, −0.61, −0.83, −0.21, −0.46; FL +3.13 set to 0 | - | per row | a = (y₊₁ + y₋₁)/2, b = (y₊₁ − y₋₁)/2 | DERIVED; each quadratic reproduces its own −2 in value within 2% (test) |
| Pooled curvature (SAT_graze, no Atascosa series) | −0.53 | - | median of 10 non-Florida quadratics | same CSV | DERIVED |
| Growth curves (Jan..Dec %) | TX5514, TX6011, TX4525, TX5520, OK0001, OK0003, CO6701, CO6709, NM4208, FL bahiagrass FSG (values in code) | % of annual | per ESD | doc 03b numbers table (NRCS EDIT / FSG) | Repo (03b: CONFIRMED) |
| Missouri fescue curve | Mar-Jun 16.7% each, Sep-Nov 11.1% each | % | Dade Co. | our construction from MU Extension "two-thirds spring, one-third fall" (doc 03b) | ASSUMPTION (no NRCS curve exists) |
| One-month rain lead in growth weights | weight_m = (g_m + g_m+1)/2 | - | all | this doc | ASSUMPTION |
| State hay prices, 2025 | TX 136, OK 90, MO 114, FL 120, CO 151, NM 184 | $/ton | 2025 marketing year | NASS Crop Values 2025 Summary p.33, via doc 03b | Repo (03b: CONFIRMED) |
| Harvest efficiency | 25% | - | ESD convention | doc 03b (R067BY002CO) | Repo (03b: CONFIRMED) |
| Replacement values per acre | DFW 67.03; SAT 57.44; OKC 52.26; SGF 54.15; DEN 25.75; ABQ 27.42; TPA 81.60 | $/ac | 2025 prices | production × 0.25 × price / 2000; matches doc 03b's 67.0 / 57.4 / 52.3 / 54.2 / 25.7 / 27.4 / 81.6 (test) | DERIVED |
| Rent values, acres, allocations | per farm | - | - | `data/scenarios/farms.yaml` | Repo (doc 04 not fact-checked) |
| Corn/soy coefficients | e.g. IL corn rain-only: July 34.91, −3.092; June 14.42, −1.451; May −2.345 | bu/ac per in, per in² | state 1980-2025 | `crop_yield_aux/r1_reestimate_coefficients.csv` | Repo (03a VERIFIED) |
| Corn/soy normals, prices, trend yields | e.g. IL Jul 4.06 in, Jun 4.65, May 4.77; $4.70 corn, $12.00 soy; 211.5 bu/ac | - | 1991-2020 normals | `crop_rain_sensitivity_corn_soy.csv` | Repo (03a VERIFIED) |
| Irrigated shares | e.g. NE corn 52.7%, IL corn 3.3%, AR soy 76.0% | % | 2022 Census | `crop_yield_aux/r1_irrigation_share_2022.csv` | Repo (03a VERIFIED) |
| 2012 rain and yields (table F) | e.g. IL Jun+Jul 3.13 in, Jul 1.40 in, Aug 98% of normal; corn −41.1% vs trend | - | 2012 | `crop_yield_aux/r1_drought_2012.csv` | Repo (03a VERIFIED) |
| Rain driving the backtest | CPC interval index `index_value_ours` on each farm's PRF grid | index | 1969-2025 | `cpc_interval_index.parquet`; reproduces paid final indexes to 0.002 points (doc 06b) | Repo |
| PRF payout as paid; Kalshi hedge payout; producer premium; Kalshi central cost | `prf_cpc_as_paid_usd`, `h3_cpc_train_usd` (fit 1951-2009, out of sample), `producer_premium_usd`, `kalshi_cost_central_usd` | $ | 2015-2025 | `payout_comparison_farm_year.csv` (doc 09) | Repo; totals $1,110,071 and $1,200,959 match doc 09's $1.10M / $1.20M |
| NASS statewide other-hay yields | TX, OK, MO, FL | t/ac | 1975-2025 | NASS Quick Stats keyless CSV export, downloaded 2026-11-01, cached in the raw dir | COMPUTED (regenerated by the script; not committed) |
| Everything in tables A-F below | - | - | - | `scripts/run_loss_model.py` | COMPUTED |

## Backtest design

- **Farms and years:** the 11 `farms.yaml` farms, 2015-2025, which is doc 09's headline window. Modeled losses are also saved for 1969-2025.
- **Rain:** the CPC "as paid" interval index on each farm's own PRF grid. This is the index RMA actually paid on, so loss and PRF use the same rain. The Kalshi hedge settles on the airport station 24-58 miles away, so its basis risk appears in the comparison.
- **Instruments:**
  - PRF: indemnity as paid under the 2026 election.
  - Kalshi: the doc-09 H3 hedge on real Kalshi strikes, with weights fit on 1951-2009 (out of sample for 2015-2025). Kalshi is missing for 5 farm-years because station months are incomplete.
  - Costs: producer premium and the Kalshi central cost, from doc 09.
- **Loss variants:** four combinations of timing (allocation, growth) × value (rent, replacement), plus a linear version of the central variant (allocation, rent).
- **Metrics per farm and instrument:**
  - Payout / loss: total payout ÷ total positive modeled loss.
  - Capped coverage: Σ min(payout, loss) ÷ Σ loss. This is the share of loss dollars paid in the same year, with no credit for over-payment.
  - Correlation of yearly payout with signed modeled loss (n = 10-11, so each one is noisy).
  - Loss years (modeled loss above 5% of normal value), and how many of those got no payout.
  - Years paid while the model shows a gain.
  - sd ratio: sd(loss − payout) ÷ sd(loss). Below 1 means the instrument reduced the year-to-year swing in loss.

## Results

<!-- BEGIN AUTO: loss model results (scripts/run_loss_model.py) -->

Generated by `python scripts/run_loss_model.py`. Do not edit by hand.

### A. Model parameters per farm

| Farm | Elasticity e | Curvature g | Saturates at season index | Normal value, rent | Normal value, replacement | Allocation weights | Growth weights |
|---|---|---|---|---|---|---|---|
| DFW_hay | 0.486 | -0.28 | 281 | $37,440 | $37,440 | Apr-May 0.40; Jun-Jul 0.35; Aug-Sep 0.25 | Mar-Apr 0.21; May-Jun 0.38; Jul-Aug 0.17; Sep-Oct 0.21; Nov-Dec 0.04 |
| DFW_graze | 0.573 | -0.83 | 160 | $10,800 | $53,625 | Feb-Mar 0.15; Apr-May 0.35; Jun-Jul 0.25; Sep-Oct 0.25 | Jan-Feb 0.05; Mar-Apr 0.27; May-Jun 0.34; Jul-Aug 0.13; Sep-Oct 0.17; Nov-Dec 0.05 |
| SAT_graze | 0.477 | -0.53 | 194 | $23,250 | $86,164 | Mar-Apr 0.20; May-Jun 0.40; Sep-Oct 0.40 | Jan-Feb 0.06; Mar-Apr 0.22; May-Jun 0.27; Jul-Aug 0.19; Sep-Oct 0.19; Nov-Dec 0.09 |
| OKC_hay | 0.494 | -0.90 | 155 | $29,740 | $29,740 | Apr-May 0.35; Jun-Jul 0.40; Aug-Sep 0.25 | Jan-Feb 0.04; Mar-Apr 0.23; May-Jun 0.43; Jul-Aug 0.17; Sep-Oct 0.11; Nov-Dec 0.02 |
| OKC_graze | 0.672 | -0.61 | 182 | $24,500 | $52,256 | Mar-Apr 0.30; May-Jun 0.40; Jul-Aug 0.20; Sep-Oct 0.10 | Jan-Feb 0.04; Mar-Apr 0.23; May-Jun 0.43; Jul-Aug 0.17; Sep-Oct 0.11; Nov-Dec 0.02 |
| SGF_hay | 0.397 | -1.92 | 126 | $32,205 | $32,205 | Mar-Apr 0.40; May-Jun 0.40; Sep-Oct 0.20 | Jan-Feb 0.08; Mar-Apr 0.33; May-Jun 0.25; Jul-Aug 0.06; Sep-Oct 0.22; Nov-Dec 0.06 |
| SGF_graze | 0.462 | -1.92 | 126 | $17,500 | $27,075 | Mar-Apr 0.30; May-Jun 0.30; Aug-Sep 0.20; Oct-Nov 0.20 | Jan-Feb 0.08; Mar-Apr 0.33; May-Jun 0.25; Jul-Aug 0.06; Sep-Oct 0.22; Nov-Dec 0.06 |
| DEN_graze | 0.742 | -0.21 | 343 | $42,700 | $180,218 | Apr-May 0.45; Jun-Jul 0.35; Aug-Sep 0.20 | Jan-Feb 0.01; Mar-Apr 0.20; May-Jun 0.50; Jul-Aug 0.22; Sep-Oct 0.07 |
| ABQ_graze | 0.888 | -0.46 | 210 | $20,400 | $328,992 | Apr-May 0.20; Jun-Jul 0.30; Aug-Sep 0.50 | Jan-Feb 0.03; Mar-Apr 0.15; May-Jun 0.33; Jul-Aug 0.42; Sep-Oct 0.09 |
| TPA_graze | 0.155 | 0.00 | none (linear) | $11,000 | $81,600 | Mar-Apr 0.40; May-Jun 0.40; Oct-Nov 0.20 | Jan-Feb 0.02; Mar-Apr 0.22; May-Jun 0.33; Jul-Aug 0.33; Sep-Oct 0.10 |
| TPA_hay | 0.144 | 0.00 | none (linear) | $65,280 | $65,280 | Mar-Apr 0.30; May-Jun 0.40; Sep-Oct 0.30 | Jan-Feb 0.02; Mar-Apr 0.22; May-Jun 0.33; Jul-Aug 0.33; Sep-Oct 0.10 |

Curvature sources: DFW_hay: hay_other_TX_state_AprSep (+1/-1 in = 0.059/-0.061, normal 16.55 in); DFW_graze: forage_rangeland_TX_Parker_AprJun (+1/-1 in = 46.0/-53.0, normal 11.76 in); SAT_graze: pooled median of 10 forage/hay quadratics; OKC_hay: hay_other_OK_state_AprSep (+1/-1 in = 0.035/-0.038, normal 22.0 in); OKC_graze: hay_other_OK_Grady_AprJun (+1/-1 in = 0.047/-0.052, normal 12.1 in); SGF_hay: hay_other_MO_state_AprJun (+1/-1 in = 0.031/-0.041, normal 13.84 in); SGF_graze: hay_other_MO_state_AprJun (+1/-1 in = 0.031/-0.041, normal 13.84 in); DEN_graze: forage_rangeland_CO_Elbert_AprJul (+1/-1 in = 70.0/-73.0, normal 9.8 in); ABQ_graze: forage_rangeland_NM_Torrance_JulSep (+1/-1 in = 35.0/-40.0, normal 6.85 in); TPA_graze: hay_other_FL_state_MarMay (+1/-1 in = 0.013/-0.007, normal 10.43 in); fitted +3.13 > 0 clamped to 0; TPA_hay: hay_other_FL_state_MarMay (+1/-1 in = 0.013/-0.007, normal 10.43 in); fitted +3.13 > 0 clamped to 0

### B. Backtest 2015-2025, all 11 farms pooled

Modeled loss counts only years with a loss (positive part). Capped coverage = sum over years of min(payout, loss) / sum of losses. Loss year = modeled loss above 5% of normal value.

| Loss variant | Instrument | Farm-years | Modeled loss | Payouts | Payout / loss | Capped coverage | Median farm corr | Loss years | ...unpaid | Paid with no loss | Farms with lower risk (sd ratio < 1) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| alloc_rent | prf | 121 | $157,792 | $1,110,071 | 7.04 | 99% | 0.78 | 35 | 0 | 48 | 5 of 11 |
| alloc_rent | kalshi | 116 | $156,939 | $1,200,959 | 7.65 | 97% | 0.52 | 34 | 0 | 58 | 6 of 11 |
| alloc_repl | prf | 121 | $699,548 | $1,110,071 | 1.59 | 59% | 0.78 | 35 | 0 | 48 | 8 of 11 |
| alloc_repl | kalshi | 116 | $695,315 | $1,200,959 | 1.73 | 57% | 0.52 | 34 | 0 | 58 | 8 of 11 |
| growth_rent | prf | 121 | $120,769 | $1,110,071 | 9.19 | 99% | 0.65 | 28 | 0 | 57 | 4 of 11 |
| growth_rent | kalshi | 116 | $119,030 | $1,200,959 | 10.09 | 98% | 0.49 | 28 | 0 | 69 | 5 of 11 |
| growth_repl | prf | 121 | $501,404 | $1,110,071 | 2.21 | 70% | 0.65 | 28 | 0 | 57 | 7 of 11 |
| growth_repl | kalshi | 116 | $497,400 | $1,200,959 | 2.41 | 63% | 0.49 | 28 | 0 | 69 | 8 of 11 |
| alloc_rent_linear | prf | 121 | $139,685 | $1,110,071 | 7.95 | 99% | 0.76 | 35 | 0 | 48 | 6 of 11 |
| alloc_rent_linear | kalshi | 116 | $138,912 | $1,200,959 | 8.65 | 99% | 0.51 | 34 | 0 | 58 | 7 of 11 |

### C. Per farm, 2015-2025, loss variant `alloc_rent`

| Farm | Modeled loss (sum) | Net loss incl. gains (sum) | PRF paid | PRF payout / loss | PRF capped coverage | PRF corr | Kalshi paid | Kalshi payout / loss | Kalshi capped coverage | Kalshi corr | Loss years (unpaid PRF / Kalshi) | sd ratio PRF / Kalshi |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DFW_hay | $25,694 | -$1,660 | $81,844 | 3.19 | 100% | 0.80 | $68,070 (10 yr) | 2.65 | 97% | 0.54 | 4 (0 / 0) | 0.60 / 0.85 |
| DFW_graze | $7,985 | $2,671 | $60,206 | 7.54 | 100% | 0.74 | $50,410 (10 yr) | 7.07 | 100% | 0.52 | 5 (0 / 0) | 1.41 / 1.14 |
| SAT_graze | $23,261 | $12,965 | $71,487 | 3.07 | 100% | 0.85 | $70,837 (10 yr) | 3.05 | 95% | 0.58 | 4 (0 / 0) | 0.80 / 0.94 |
| OKC_hay | $2,389 | -$15,014 | $35,667 | 14.93 | 100% | 0.24 | $67,295 (11 yr) | 28.17 | 100% | 0.34 | 0 (0 / 0) | 1.59 / 1.67 |
| OKC_graze | $5,263 | -$20,053 | $39,906 | 7.58 | 100% | 0.49 | $56,466 (11 yr) | 10.73 | 100% | 0.63 | 2 (0 / 0) | 1.04 / 0.80 |
| SGF_hay | $11,217 | $1,058 | $31,565 | 2.81 | 100% | 0.93 | $47,439 (10 yr) | 4.23 | 70% | 0.44 | 2 (0 / 0) | 0.38 / 0.91 |
| SGF_graze | $5,185 | -$651 | $26,532 | 5.12 | 100% | 0.81 | $39,665 (10 yr) | 7.65 | 100% | 0.39 | 3 (0 / 0) | 0.71 / 1.03 |
| DEN_graze | $26,852 | -$34,459 | $96,372 | 3.59 | 96% | 0.76 | $230,390 (11 yr) | 8.58 | 100% | 0.57 | 3 (0 / 0) | 0.68 / 0.88 |
| ABQ_graze | $21,109 | -$2,342 | $216,647 | 10.26 | 100% | 0.78 | $278,282 (11 yr) | 13.18 | 100% | 0.60 | 5 (0 / 0) | 3.40 / 0.82 |
| TPA_graze | $5,071 | $4,835 | $198,906 | 39.22 | 100% | 0.88 | $140,248 (11 yr) | 27.65 | 100% | -0.20 | 5 (0 / 0) | 26.59 / 11.88 |
| TPA_hay | $23,766 | $20,556 | $250,939 | 10.56 | 100% | 0.76 | $151,858 (11 yr) | 6.39 | 100% | -0.06 | 2 (0 / 0) | 5.23 / 2.54 |

### C. Per farm, 2015-2025, loss variant `growth_repl`

| Farm | Modeled loss (sum) | Net loss incl. gains (sum) | PRF paid | PRF payout / loss | PRF capped coverage | PRF corr | Kalshi paid | Kalshi payout / loss | Kalshi capped coverage | Kalshi corr | Loss years (unpaid PRF / Kalshi) | sd ratio PRF / Kalshi |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DFW_hay | $16,934 | -$7,150 | $81,844 | 4.83 | 100% | 0.65 | $68,070 (10 yr) | 4.30 | 98% | 0.43 | 3 (0 / 0) | 0.89 / 0.97 |
| DFW_graze | $30,582 | $1,302 | $60,206 | 1.97 | 64% | 0.70 | $50,410 (10 yr) | 1.77 | 57% | 0.63 | 2 (0 / 0) | 0.77 / 0.86 |
| SAT_graze | $64,994 | $25,047 | $71,487 | 1.10 | 66% | 0.60 | $70,837 (10 yr) | 1.10 | 50% | 0.49 | 4 (0 / 0) | 0.81 / 0.89 |
| OKC_hay | $4,423 | -$13,397 | $35,667 | 8.06 | 92% | 0.32 | $67,295 (11 yr) | 15.21 | 100% | 0.31 | 1 (0 / 0) | 1.41 / 1.56 |
| OKC_graze | $10,277 | -$40,857 | $39,906 | 3.88 | 99% | 0.60 | $56,466 (11 yr) | 5.49 | 100% | 0.72 | 2 (0 / 0) | 0.81 / 0.77 |
| SGF_hay | $6,687 | -$1,566 | $31,565 | 4.72 | 92% | 0.77 | $47,439 (10 yr) | 7.09 | 100% | 0.67 | 1 (0 / 0) | 1.22 / 0.80 |
| SGF_graze | $6,543 | -$1,532 | $26,532 | 4.06 | 100% | 0.75 | $39,665 (10 yr) | 6.06 | 100% | 0.38 | 3 (0 / 0) | 0.68 / 0.96 |
| DEN_graze | $89,898 | -$214,454 | $96,372 | 1.07 | 76% | 0.67 | $230,390 (11 yr) | 2.56 | 100% | 0.64 | 3 (0 / 0) | 0.87 / 0.88 |
| ABQ_graze | $221,545 | -$335,079 | $216,647 | 0.98 | 58% | 0.51 | $278,282 (11 yr) | 1.26 | 37% | 0.57 | 3 (0 / 0) | 0.89 / 0.97 |
| TPA_graze | $28,408 | $21,580 | $198,906 | 7.00 | 97% | 0.58 | $140,248 (11 yr) | 4.94 | 100% | -0.22 | 3 (0 / 0) | 2.79 / 1.87 |
| TPA_hay | $21,113 | $16,039 | $250,939 | 11.89 | 100% | 0.74 | $151,858 (11 yr) | 7.19 | 100% | -0.10 | 3 (0 / 0) | 4.64 / 2.36 |

### D. Modeled loss by year, central variant (`alloc_rent`), $ (negative = gain)

| Farm | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| DFW_hay | -8,012 | -4,209 | -4,487 | 1,038 | -3,907 | 3,126 | -6,430 | 8,054 | 11,001 | 2,475 | -310 |
| DFW_graze | -1,861 | -594 | 992 | -1,062 | -745 | -282 | -770 | 3,720 | 1,778 | 642 | 852 |
| SAT_graze | -5,081 | 439 | 2,093 | -2,615 | 604 | -1,290 | 495 | 10,180 | -1,311 | 4,732 | 4,717 |
| OKC_hay | -4,062 | -45 | -1,500 | -926 | -3,183 | 315 | -3,758 | 1,218 | 517 | 339 | -3,928 |
| OKC_graze | -6,151 | 854 | -2,568 | 2,162 | -4,837 | -1,494 | -4,212 | 184 | 1,454 | 609 | -6,055 |
| SGF_hay | -239 | 414 | -1,663 | 8,610 | -1,663 | -1,601 | -1,663 | -1,003 | 2,193 | -890 | -1,439 |
| SGF_graze | -1,019 | 1,133 | -1,052 | 2,845 | -1,052 | -768 | -844 | -416 | 1,207 | -403 | -282 |
| DEN_graze | -17,893 | -841 | -6,069 | 6,913 | 1,173 | 10,543 | -1,970 | 8,223 | -23,208 | -4,420 | -6,910 |
| ABQ_graze | -6,501 | -6,129 | -3,628 | 4,212 | -248 | 9,494 | 1,172 | -1,666 | 5,139 | 1,092 | -5,279 |
| TPA_graze | 426 | 117 | 205 | -236 | 113 | 257 | 915 | 963 | 629 | 597 | 850 |
| TPA_hay | 2,242 | -868 | -1,175 | -1,168 | 1,688 | 2,162 | 5,681 | 2,506 | 2,667 | 2,959 | 3,861 |

### E. External check: model vs detrended NASS statewide other-hay yield

Model input is the farm-grid CPC index; the yield is the statewide average, so a perfect model would still show an attenuated slope and correlation.

| Farm (state) | Variant | Years | n | Corr | Slope (actual on model) | RMSE | Driest-quintile mean: model / actual | Corr 2015-2025 |
|---|---|---|---|---|---|---|---|---|
| DFW_hay (Texas) | alloc_rent | 1975-2025 | 51 | 0.46 | 0.46 | 0.164 | -24.8% / -12.3% | 0.34 |
| DFW_hay (Texas) | alloc_rent_linear | 1975-2025 | 51 | 0.45 | 0.44 | 0.167 | -22.0% / -12.3% | 0.32 |
| DFW_hay (Texas) | growth_rent | 1975-2025 | 51 | 0.47 | 0.56 | 0.151 | -17.1% / -10.3% | 0.21 |
| OKC_hay (Oklahoma) | alloc_rent | 1975-2025 | 51 | 0.57 | 0.62 | 0.122 | -21.2% / -11.5% | 0.59 |
| OKC_hay (Oklahoma) | alloc_rent_linear | 1975-2025 | 51 | 0.56 | 0.48 | 0.142 | -15.9% / -11.5% | 0.56 |
| OKC_hay (Oklahoma) | growth_rent | 1975-2025 | 51 | 0.59 | 0.88 | 0.110 | -13.5% / -12.3% | 0.46 |
| SGF_hay (Missouri) | alloc_rent | 1975-2025 | 51 | 0.40 | 0.52 | 0.108 | -15.0% / -11.6% | 0.49 |
| SGF_hay (Missouri) | alloc_rent_linear | 1975-2025 | 51 | 0.44 | 0.45 | 0.124 | -9.6% / -11.6% | 0.52 |
| SGF_hay (Missouri) | growth_rent | 1975-2025 | 51 | 0.42 | 0.73 | 0.101 | -10.4% / -6.9% | 0.55 |
| TPA_hay (Florida) | alloc_rent | 1975-2025 | 51 | 0.34 | 0.92 | 0.094 | -5.7% / -5.1% | 0.39 |
| TPA_hay (Florida) | alloc_rent_linear | 1975-2025 | 51 | 0.34 | 0.92 | 0.094 | -5.7% / -5.1% | 0.39 |
| TPA_hay (Florida) | growth_rent | 1975-2025 | 51 | 0.34 | 1.10 | 0.093 | -4.9% / -2.6% | 0.30 |

### F. Row-crop path: corn in the 2012 drought (doc 03a model, statewide rain)

| State | Spec | Jun / Jul / Aug rain (in) | Model change (bu/ac) | Model % of 1988-2011 trend | Actual % vs trend | Loss on 1,000 rain-fed ac | Same, at state irrigated share |
|---|---|---|---|---|---|---|---|
| IL | rain-only 1980-2025 | 1.73 / 1.4 / 3.49 | -63.1 | -35.4% | -41.1% | $296,752 | $286,960 (3.3%) |
| IL | update 1980-2025 | 1.73 / 1.4 / 3.49 | -50.1 | -28.1% | -41.1% | $235,259 | $227,495 (3.3%) |
| IN | rain-only 1980-2025 | 1.29 / 2.53 / 4.07 | -58.3 | -35.0% | -40.6% | $274,068 | $256,802 (6.3%) |
| IN | update 1980-2025 | 1.29 / 2.53 / 4.07 | -51.5 | -30.9% | -40.6% | $242,055 | $226,805 (6.3%) |
| IA | rain-only 1980-2025 | 2.81 / 1.17 / 2.89 | -45.5 | -24.3% | -26.6% | $213,651 | $211,087 (1.2%) |
| IA | update 1980-2025 | 2.81 / 1.17 / 2.89 | -38.5 | -20.6% | -26.6% | $181,094 | $178,921 (1.2%) |

<!-- END AUTO: loss model results -->

How to read the results:
- **Table B:** PRF and Kalshi pay something in every material loss year, under every variant. They differ in how much they pay and when.
  - At rent value they pay about 7-10 times the modeled loss. Capped coverage is near 100% simply because payouts are large.
  - At replacement value the scale is closer: PRF pays 1.6-2.2 times the loss. Capped coverage falls to 59-70% for PRF and 57-63% for Kalshi, because payouts land in the wrong years or are too small in the worst years. ABQ_graze at replacement value is the clearest case: PRF covers 58% and Kalshi 37% of loss dollars, even though total payouts roughly equal total loss.
- **Table C:** the over-payment is largest in Florida. The model gives Hardee County almost no rain sensitivity, so PRF there behaves like a rainfall-linked payment, as doc 03b noted. The Kalshi hedge for the Tampa farms has negative correlation with modeled loss.
- **Table D:** 2022 is the big Texas loss year (DFW_hay $8.1k, SAT_graze $10.2k at rent value). 2023 is the big DFW_hay year ($11.0k). 2018 is the big Missouri year (SGF_hay $8.6k). 2020 is a loss year in Colorado and New Mexico.
- **Table E:** directionally right, too large in magnitude, and asymmetry is mixed (see Key findings).
- **Table F:** with statewide 2012 rain, the rain-only corn model predicts −24% to −35% of trend. Actual yields were −27% to −41%. The rest is consistent with heat, which doc 03a puts at about 31% of the USDA model's 2012 loss.
  - The temperature-held-fixed spec predicts less (−21% to −31%), as it should, because it leaves heat out.
  - At each state's irrigated share (1.2-6.3%), the dollar loss falls by the same proportion.

## Assumptions and limits

1. **Elasticities are borrowed, not estimated for these farms.** The hay elasticities come from statewide yields. The grazing ones come mostly from NRCS ESD ranges × 0.65, a project synthesis rather than a published constant (doc 03b). None has been fact-checked. Statewide data dilute single-farm sensitivity, while ESD ranges may overstate it.
2. **Curvature is borrowed by window and data source.**
   - The quadratics were fitted on seasonal rain in inches over a different window than the farm's weighted index. We convert them through the window normal, which assumes the same proportional shape.
   - Atascosa has no series and uses the pooled median.
   - Florida's fit is not significant and is set to linear. Positive fitted curvature is clamped to 0, because it contradicts the documented direction.
   - The Missouri curvature (−1.92) looks too strong against the state yield check.
   - No standard errors were stored for the quadratic terms, so their significance is unknown.
3. **Saturation is our modeling choice for forage.** The quadratic peak (126-343 on the season index; Florida none) caps gains. Doc 03b documents saturation but gives no cap value.
4. **Timing.** Allocation weights reflect the farmer's insurance choice, not biology. In the central variant this makes PRF and the loss model use the same intervals, which flatters PRF's correlation. Growth weights rest on ESD curves, an assumed one-month rain lead, and a constructed Missouri curve.
5. **One season, one year.** There is no carryover of soil moisture or drought damage, no heat term for forage, and no price response. Doc 03b notes carryover and price effects as further sources of basis risk.
6. **Grid rain stands in for farm rain.** The farm sits inside a 0.25-degree grid. The loss is driven by the CPC grid index, the same rain PRF pays on, so this backtest has no "farm vs grid" basis risk by construction.
7. **Value basis dominates the coverage numbers.** Rent and replacement values differ by 1.5-16 times for grazing farms (ABQ: $1.70 vs $27.42 per acre). Coverage results must always be quoted with their basis.
8. **Short window.** Eleven years and 2-5 loss years per farm. Per-farm correlations and sd ratios are noisy; pooled totals are more reliable.
9. **The row-crop path has no farm and no backtest.** It is only checked against doc 03a's documented values and the 2012 drought. Its coefficients are for statewide rain in IL, IN and IA only.

## Verification

- `tests/test_loss_model.py`: 78 tests, all passing, no network (57 from run/lossmodel-1 plus 21 added in the independent review). The full suite is 300 passed (222 before). The tests check:
  - The model reproduces the committed doc-04b `forage_loss_usd` and `weighted_index` for all 11 farms × 75 years, to within $0.01.
  - Hand-computed values for the response curve, curvature, growth weights, interval indices and a full farm loss (DEN_graze at 70% rain).
  - Each forage/hay quadratic reproduces its documented −2 in value.
  - Replacement values match doc 03b.
  - The row-crop model reproduces all doc-03a "exact" changes (IL/IN/IA, corn/soy, both specs, May-August), including the 22.6 bu/ac headline.
  - Irrigation scaling, sign conventions, and the coverage-metric arithmetic.
- `run_scenarios.py` after the refactor: rerunning it gives identical `prf_scenario_results.csv` values in every column except `indemnity_official_adm_index_usd`. That column needs the raw ADM index history, which was not present in this checkout, and the difference is unrelated to the refactor. The regenerated outputs were discarded, so the committed results are unchanged.
- Backtest inputs: PRF and Kalshi totals match doc 09.

## Independent review changes (final/lossmodel)

This doc was produced on branch run/lossmodel-1 and selected over a second independent run (run/lossmodel-2) by a reviewer, who reran the tests and the script (the committed outputs reproduced exactly, including the NASS check) and made these changes:

- **OKC_hay curvature now comes from the Oklahoma Apr-Sep quadratic** (`hay_other_OK_state_AprSep`, +0.035/−0.038 in, normal 22.0 in, g = −0.90) instead of Apr-Jun (g = −0.31). The `scen_OKC_hay` elasticity is defined on rain over the insured Apr-Sep months (baseline 22.0 in), so this applies the same "same data and window" rule already used for DFW_hay. Effect: OKC_hay saturates at a season index of 155 instead of 263, its wet-year gains shrink, and pooled 2015-2025 modeled loss moves by under $300 (for example $157,721 to $157,792 at rent value). No headline ratio changes by more than 0.02.
- **Added `marginal_loss_per_point` and `marginal_loss_per_inch`** to `FarmLossModel`, an idea taken from run/lossmodel-2. They are tested against finite differences of `loss_usd`.
- Corrected the code comment on `POOLED_CURVATURE_ROWS`: the pool is not "every" quadratic in the CSV (it leaves out the Grass-Cast-weather duplicates and the Oklahoma Apr-Sep row). The pooled value (−0.53, used only for SAT_graze) is unchanged.

## Open questions and next steps

- Fit farm-level curvature with standard errors (e.g. county hay yields where NASS publishes them), and check whether Missouri's −1.92 survives.
- Find an observed forage series for Atascosa, Dade or Hardee (doc 03b open item) to replace the borrowed parameters.
- Add a farm-vs-grid basis term, so that loss is not driven by exactly the rain PRF pays on.
- Use `FarmLossModel.loss_from_monthly` with Kalshi station rain to size a loss-matched ladder, and compare its cost with doc 09's PRF replica.
