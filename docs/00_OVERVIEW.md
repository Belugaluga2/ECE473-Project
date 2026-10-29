# Milestone 1 Overview: Research Foundation & Baseline Metrics

**Project:** Agricultural Risk Management & Weather Derivative Replicating Platform (ECE473, Maya / Evan / Jack)
**Goal of Milestone 1:** understand current USDA rainfall insurance, understand Kalshi weather markets, gather the weather data, and measure the gaps between them.
**Status (2026-10-29):** 8 of 9 proposal cells done, plus both extra research questions. The PRF-vs-Kalshi dollar and cost comparison (Week 3, Evan) is not yet run; its plan is at the bottom of this page.

Every research document has a numbers table that gives a source for each number. Documents marked **VERIFIED** were re-checked line by line by an independent fact-checking pass. The others were not fact-checked because the run was trimmed to save usage, so check their key numbers before presenting.

## Where everything lives

| Proposal cell | Owner | Document | Status |
|---|---|---|---|
| W1 Farm exposures | Jack | [research/04_representative_farms.md](research/04_representative_farms.md), [farms.yaml](../data/scenarios/farms.yaml) | done, not fact-checked |
| W1 PRF rules and payout math | Maya | [research/01_usda_prf_mechanics.md](research/01_usda_prf_mechanics.md), [prf_rules.yaml](../data/processed/prf_rules.yaml) | done, not fact-checked (74 worked values match the calculator) |
| W1 Farmer scenarios: premiums, payouts, uncovered loss | Evan | [analysis/04b_farm_scenario_results.md](analysis/04b_farm_scenario_results.md) | done (forage elasticity set to 1.0; see next steps) |
| W2 Weather data and the CPC-to-NCEI change | Jack | [analysis/06b_index_validation.md](analysis/06b_index_validation.md) | done |
| W2 Kalshi weather markets: cost and trading | Maya | [research/05_kalshi_weather_markets.md](research/05_kalshi_weather_markets.md), [analysis/05b_kalshi_liquidity_stats.md](analysis/05b_kalshi_liquidity_stats.md) | done, not fact-checked |
| W2 Settlement: what proof each side uses | Evan | [research/06_settlement_and_data_sources.md](research/06_settlement_and_data_sources.md), [analysis/06c_station_vs_kalshi_settlement_check.md](analysis/06c_station_vs_kalshi_settlement_check.md) | done, not fact-checked |
| W3 Geographic basis risk | Jack | [analysis/07_geographic_basis_risk.md](analysis/07_geographic_basis_risk.md) | done |
| W3 Replication quality across locations | Maya | [analysis/08_replication_quality.md](analysis/08_replication_quality.md) | done |
| W3 PRF payouts vs Kalshi payouts | Evan | analysis/09_payout_comparison.md | **not run** (plan below; cost headline available from 02 and 08) |
| Extra: how rainfall moves crop yields ($ per inch) | team | [research/03a_rain_yield_corn_soybean.md](research/03a_rain_yield_corn_soybean.md) (VERIFIED), research/03b_rain_yield_forage_and_other_crops.md | corn/soy VERIFIED; forage and other crops in progress |
| Extra: how farmers buy weather insurance today | team | [research/02_how_farmers_buy_weather_insurance.md](research/02_how_farmers_buy_weather_insurance.md) | done, not fact-checked |
| Literature review and prior art | team | [research/10_literature_review.md](research/10_literature_review.md), [references.bib](research/references.bib) | VERIFIED |

## Study sites

Seven PRF sites pair a Kalshi monthly-rain settlement station with a PRF-heavy county. Chicago is a row-crop contrast. Coordinates and IDs are in `src/agri_hedge/locations.py`; grid IDs are in `data/processed/study_grids.csv`.

| Site | Kalshi series | Station | Farm county | Land use | Station-to-farm | Kalshi history |
|---|---|---|---|---|---|---|
| DFW | KXRAINDALM | DFW airport | Parker Co., TX | hay + grazing | 46 mi | since Nov 2025 |
| SAT | KXRAINSATXM | San Antonio Intl | Atascosa Co., TX | rangeland | 45 mi | first month Nov 2026 |
| OKC | KXRAINOKCM | Will Rogers | Grady Co., OK | pasture + hay | 30 mi | first month Nov 2026 |
| SGF | KXRAINSGFM | Springfield MO | Dade Co., MO | fescue hay + pasture | 29 mi | first month Nov 2026 |
| DEN | KXRAINDENM | Denver Intl | Elbert Co., CO | shortgrass rangeland | 47 mi | since Nov 2025 |
| ABQ | KXRAINABQM | Albuquerque Intl | Torrance Co., NM | arid rangeland | 53 mi | first month Nov 2026 |
| TPA | KXRAINTPAM | Tampa Intl | Hardee Co., FL | bahiagrass pasture | 55 mi | first month Nov 2026 |
| ORD (contrast) | KXRAINCHIM | O'Hare (Midway before Sep 2026) | Kane Co., IL | corn/soy | 26 mi | since Jun 2025 |

## Headline findings

### 1. How farmers buy weather insurance today (doc 02)
- Farmers buy federal crop insurance from 12 private insurance companies through licensed agents. USDA's Risk Management Agency (RMA) writes and prices the policies, and taxpayers paid 62.9% of 2025 crop insurance premiums.
- Pasture, Rangeland, Forage (PRF) is USDA's only rainfall-index policy. It insures grazing and hay land, not row crops, so it is our benchmark. In 2025 it covered 298 million acres and $6.55 billion of liability.
- PRF is a very good deal for ranchers. Over 2015-2025 they got back $2.11 in payouts for every $1 they paid, because the subsidy is 51-59% of premium. Payouts beat premiums in 43 of 44 states.
- A free USDA drought program, the Livestock Forage Disaster Program, pays on the US Drought Monitor and stacks with PRF. It paid $1.78 billion in FY2023.
- Row-crop farmers mostly buy yield or revenue policies that pay on actual losses, not on rainfall.

### 2. How PRF pays (docs 01, 04b)
- Payout for each chosen two-month interval = max(0, (trigger − index) / trigger) × policy protection. The trigger is the coverage level times 100, and the index is the grid's rainfall as a percent of normal.
- Policy protection = acres × county base value × coverage level × productivity factor × percent of value allocated to the interval. Payouts do not depend on the rancher's actual loss.
- Ranchers must pick at least two non-overlapping intervals, at least 10% each, with a cap of 50-70% per interval by state. Jan-Feb is capped at 25% from 2027.
- Our calculator reproduces the USDA handbook example and every published payment factor checked. All 11 representative farms come out ahead long-run, at loss ratios of 0.70-0.86 on the full premium.

### 3. Weather data (docs 06, 06b)
- PRF paid on NOAA's Climate Prediction Center (CPC) gridded rainfall through crop year 2026. From crop year 2027 it pays on NOAA NCEI's nClimGrid data averaged into the same 0.25-degree grids.
- USDA's online PRF tool now shows a recomputed NCEI history. It is not what ranchers were actually paid. It differs from the paid indexes by 12.6 index points on average for 2021-2026.
- Our CPC rebuild reproduces the paid final indexes almost exactly (mean error 0.002 points over 854 values). The team has both regimes for backtests.

### 4. Kalshi weather markets (docs 05, 05b, 06c)
- Kalshi is a CFTC-regulated exchange. It lists monthly rainfall ladders for about 35 cities, as "more than X inches" binary contracts at whole inches, usually 1 to 7. Each settles on one NWS airport station's daily climate report.
- The fee is round-up(0.07 × contracts × price × (1 − price)), charged to takers only. For example, 100 contracts at 20 cents cost $20 plus a $1.12 fee.
- Station data reproduce all 922 settled monthly-rain outcomes checked, so backtests with station data are reliable.
- Five of our seven PRF sites only got markets on 2026-10-25. Only Dallas and Denver have about a year of trading history.
- Depth is tiny. Dallas's November 2026 book held about $436 of drought payout across all strikes. Larger books at the new cities sit on liquidity rewards that ended 2026-11-01.
- Cheap longshots are overpriced. Contracts under 20 cents averaged 4.7 cents but paid out only 1.6% of the time.
- There is no strike below 1 inch. At Denver and Albuquerque the 1-inch contract is already below the median month for most of the year, so dry-month triggers are missing.

### 5. The gaps (docs 07, 08)
- **Geography:** an airport gauge tracks its own PRF grid closely (correlation 0.92-0.97). It tracks the farm grid 24-58 miles away less well (0.74-0.89), with a 17% chance PRF pays when the station signal does not. Correlation decays with an e-folding distance of about 256 miles.
- **Coverage:** only 7.4% of US PRF grids lie within 50 miles of a Kalshi rain station. The median grid is 171 miles away.
- **Replication:** the best mix of today's Kalshi contracts captures about 43% of the variance of PRF payouts (hedge effectiveness 0.43). An ideal contract on the station's own two-month index would reach 0.73.
- **Error breakdown:** effectiveness falls from 1.0 to 0.73 from geography and gauge-versus-grid, then to 0.54 because Kalshi contracts are monthly while PRF intervals are two months, then to 0.43 from whole-inch strikes. Arid sites lose most to strike binning.
- **Tails:** the Kalshi ladder rarely misses a PRF payout (1%). But it often pays in years PRF does not, and it pays only 62% of PRF's payout in deep droughts.
- **Cost:** at fair odds the Kalshi ladder costs about $0.179 per $1 of protection per interval. A PRF rancher pays about $0.098 after subsidy. Real Kalshi prices add fees, spreads, and the longshot markup, so a rancher pays 2-3 times more per dollar of expected payout on Kalshi.

### 6. How rain moves crop yields (doc 03a, VERIFIED; 03b in progress)
- **Corn:** one extra inch of July rain near normal adds about 3 to 7 bushels per acre, or 2 to 3.5% of yield. That is about $24 to $33 per acre at $4.70 corn.
- **Asymmetry:** dry hurts more than wet helps. In Illinois, 2 inches below normal in July costs about 17.5 to 22.6 bushels per acre depending on the model, while 2 inches above gains about 6.
- **Soybeans:** August rain matters most, at about 1 to 2 bushels per acre per inch, or roughly $13 to $23 per acre at $12 soybeans.
- **Excess rain:** too much rain also hurts. May rain lowers corn yields, and extreme wet seasons cut maize yields about as much as extreme droughts.
- **Irrigation:** irrigated acres barely respond to rain. That covers 13.6% of US corn but 52.7% of Nebraska corn.

### 7. Prior art (doc 10, VERIFIED)
- Luo studies Kalshi temperature contracts and finds basis risk rises with distance. Iturbide studies New York City daily rain and finds the contract is well calibrated, but 69% of payouts land on days with no loss.
- Neither study covers monthly rain ladders, agriculture, or a PRF benchmark. That is our gap.

## What this means for Milestone 2
- **Market gaps:** the biggest fixable gaps are contract design, not geography. Two-month or seasonal contracts would recover about 0.19 of effectiveness. Strikes below 1 inch, or 0.25-inch steps, would recover about 0.11 and matter most at arid sites.
- **Subsidy:** Kalshi cannot beat subsidized PRF on cost for the same risk. Realistic niches are coverage above what PRF allows, periods or perils PRF leaves open, row-crop rain risk (especially excess rain), and producers who cannot buy PRF.
- **Liquidity:** today's books cannot fill even one small ranch's hedge. The platform needs a liquidity plan, such as market-maker partners or pooled orders.

## Next steps (left open by this run)
1. **Payout comparison (doc 09, Evan W3):** for each farm, compare PRF payouts (CPC as-paid for history, NCEI going forward) with the Kalshi ladder payouts from `data/processed/replication_weights.csv`. Use cost under fair value, fair value plus the longshot markup, and real prices (Dallas and Denver candles, current order books), plus fees and capital lock-up.
2. **Forage elasticities:** when doc 03b and `data/processed/crop_rain_sensitivity_other.csv` exist, fill `rain_sensitivity_ref` in farms.yaml and rerun `python scripts/run_scenarios.py` to update the uncovered-loss numbers in doc 04b.
3. **Fact-check** docs 01, 02, 04, 05, and 06 before presenting their numbers. Luo's numbers rest only on his SSRN abstract; download the PDF in a browser.
4. **Re-pull order books** after 2026-11-01 (`python scripts/pull_kalshi.py`) to see whether depth at the new cities survives the end of the liquidity rewards.

## Repository map
- `docs/research/` sourced research documents, one topic each
- `docs/analysis/` results from our own code
- `docs/figures/` generated figures
- `src/agri_hedge/` Python package:
  - `prf.py`: PRF calculator
  - `prf_grid.py`, `cpc.py`: grids and indexes
  - `kalshi.py`: market data client and fee function
  - `stations.py`: station rain
  - `basis.py`: basis-risk metrics
  - `replicate.py`: hedge fitting
  - `locations.py`: study sites
- `scripts/` runnable entry points that pull data and regenerate every result
- `data/processed/` small derived datasets (committed); `data/raw/` downloads (gitignored, recreated by scripts)
- `tests/` pytest checks (208 passing)

## How to reproduce

```bash
python -m pip install -e .
python -m pytest
python scripts/run_basis_risk.py      # doc 07
python scripts/run_replication.py     # doc 08
python scripts/run_scenarios.py       # doc 04b
```
