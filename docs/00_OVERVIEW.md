# Milestone 1 Overview: Research Foundation & Baseline Metrics

**Project:** Agricultural Risk Management & Weather Derivative Replicating Platform (ECE473, Maya / Evan / Jack)
**Goal of Milestone 1:** understand current USDA rainfall insurance, understand Kalshi weather markets, gather the weather data, and measure the gaps between them.
**Status:** IN PROGRESS (started 2026-10-29). This page is the index; it is updated as each piece lands.

## Where everything lives

| Proposal cell | Owner | Document | Status |
|---|---|---|---|
| W1 Current insurance: farm exposures | Jack | [research/04_representative_farms.md](research/04_representative_farms.md) | in progress |
| W1 Current insurance: PRF rules and payout math | Maya | [research/01_usda_prf_mechanics.md](research/01_usda_prf_mechanics.md) | in progress |
| W1 Current insurance: farmer scenarios (premiums, payouts, uncovered loss) | Evan | [analysis/04b_farm_scenario_results.md](analysis/04b_farm_scenario_results.md) | waiting on data |
| W2 Weather data and the CPC-to-NCEI change | Jack | [research/06_settlement_and_data_sources.md](research/06_settlement_and_data_sources.md) + `scripts/pull_cpc.py` | in progress |
| W2 Kalshi weather markets: cost and trading | Maya | [research/05_kalshi_weather_markets.md](research/05_kalshi_weather_markets.md) | in progress |
| W2 Settlement: what proof each side uses | Evan | [research/06_settlement_and_data_sources.md](research/06_settlement_and_data_sources.md) | in progress |
| W3 Geographic basis risk | Jack | [analysis/07_geographic_basis_risk.md](analysis/07_geographic_basis_risk.md) | waiting on data |
| W3 Replication quality across locations | Maya | [analysis/08_replication_quality.md](analysis/08_replication_quality.md) | waiting on data |
| W3 PRF payouts vs Kalshi payouts | Evan | [analysis/09_payout_comparison.md](analysis/09_payout_comparison.md) | waiting on data |
| Extra: how rainfall moves crop yields ($ per inch) | team | [research/03_crop_rain_sensitivity.md](research/03_crop_rain_sensitivity.md) | in progress |
| Extra: how farmers buy weather insurance today | team | [research/02_how_farmers_buy_weather_insurance.md](research/02_how_farmers_buy_weather_insurance.md) | in progress |
| Literature review and prior art | team | [research/10_literature_review.md](research/10_literature_review.md) | in progress |

## Study sites

Seven PRF sites, each pairing a Kalshi monthly-rain settlement station with a PRF-heavy county, plus a row-crop contrast. Coordinates and IDs are in `src/agri_hedge/locations.py`.

| Site | Kalshi series | Station | Farm county | Land use | Station-to-farm |
|---|---|---|---|---|---|
| DFW | KXRAINDALM | DFW airport | Parker Co., TX | hay + grazing | 46 mi |
| SAT | KXRAINSATXM | San Antonio Intl | Atascosa Co., TX | rangeland | 45 mi |
| OKC | KXRAINOKCM | Will Rogers | Grady Co., OK | pasture + hay | 30 mi |
| SGF | KXRAINSGFM | Springfield MO | Dade Co., MO | fescue hay + pasture | 29 mi |
| DEN | KXRAINDENM | Denver Intl | Elbert Co., CO | shortgrass rangeland | 47 mi |
| ABQ | KXRAINABQM | Albuquerque Intl | Torrance Co., NM | arid rangeland | 53 mi |
| TPA | KXRAINTPAM | Tampa Intl | Hardee Co., FL | bahiagrass pasture | 55 mi |
| ORD (contrast) | KXRAINCHIM | O'Hare | Kane Co., IL | corn/soy | 26 mi |

## Headline findings so far

- Kalshi lists monthly rainfall markets for about 35 US cities, each a ladder of "more than X inches" binary contracts settling on one NWS airport station.
- USDA's only rainfall-index policy is Pasture, Rangeland, Forage (PRF). It insures grazing and hay land, not row crops, so it is the replication benchmark.
- RMA is moving PRF's rainfall data from NOAA CPC to NOAA NCEI on 2026-08-31, with grids unchanged.
- Open Kalshi rain markets checked on 2026-10-29 (Dallas) showed no resting bids or asks, so liquidity is a first-order constraint.

(More findings are added as documents are verified.)

## Repository map

- `docs/research/` sourced research documents (one topic each, numbers table + citations)
- `docs/analysis/` quantitative results from our own code
- `docs/figures/` generated figures
- `src/agri_hedge/` Python package (data pulls, PRF calculator, Kalshi client, analysis)
- `scripts/` runnable entry points that regenerate data and figures
- `data/processed/` small derived datasets (committed); `data/raw/` downloads (gitignored)
- `tests/` pytest checks

## How to reproduce

```bash
pip install -e .
pytest
# data pulls and analysis scripts are listed in README.md once built
```
