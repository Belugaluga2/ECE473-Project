# Independent review: data, index design and quantitative angles for the weather-risk expansion

Research date: 2026-11-19. Scope: settlement indices and data, teleconnections, pricing under trend, adverse selection, market-making mechanisms, venue contract design, and a critique of `netting_quant.md` / `scripts/run_expansion_netting.py`. I changed no repo scripts or data. My read-only checks are committed here:
- `scripts/experiments/expansion_review/review_checks.py` and its output `review_checks_output.txt` (copied from the review scratchpad and re-run; `crosspair.py`, `daycheck.py` alongside)
- `tailcheck.py` and `twocontract.py` were not kept; their figures are cited from this note only

Those checks import the repo script's functions and reuse its contract terms: 30th and 70th percentile strikes, equal premium, and a 20% load. They read the committed `station_monthly_precip.csv` and the cached ACIS daily files. "Unverified" means I found no primary source in this session.

## Top 5 additions

1. **Most of the "venue halves capital" result is ordinary two-contract diversification, not opposite-side netting.**
   - Two farmer puts at stations more than 1,000 mi apart need **1.96** capital95 per premium. A same-station farmer-plus-venue pair needs 1.72-1.76, and one put alone needs 3.57.
   - So about 85% of the drop from 3.57 to 1.74 comes from writing any second independent contract.
   - The opposite-side benefit shows up in the worst case: the worst year costs 2.2 per premium for a same-station pair against 3.5 for two distant puts. That makes it a collateral and extreme-tail argument.
   - A venue call at a different station within 250 mi nets about as well as the same station (1.77 against 1.72), so exact same-station matching is not needed.
2. **The climate drift is a common factor that pooling cannot diversify.**
   - Priced on 1951-1995 and realized 1996-2025, the national annual pool's call side earns a mean margin of −0.002 per premium, so the whole load is gone. Its capital95 is 0.33 per premium, against about 0 in-sample. The national pair pool needs 0.038 against 0.000.
   - A placebo that shuffles years puts the call drift outside every one of 300 null draws (p < 0.004). The drift holds for any split year from 1980 to 2005 (call loss ratio 1.20-1.29).
   - Walk-forward pricing on only the last 15 years, or with a linear trend in the payout, cuts the pair loss ratio from 1.09 to 1.02-1.05 for rain and from 1.15 to 1.01-1.05 for snow. For temperature, detrending cuts it from 1.18 to 1.06.
3. **ENSO is a forecastable common factor. It creates adverse selection now, and also natural cross-region pairs.**
   - Nov-Mar dry puts in the south-central region (DFW, OKC, SAT, AUS, CLL, HOU) pay 1.49x climatology after a La Niña Aug-Oct (ASO) ONI and 0.66x after an El Niño one. The Southeast's figures are 1.37x and 0.51x.
   - A hedger who buys only on the favorable signal produces loss ratios of 1.17-1.64, above the 1.20 load in most cases.
   - **CPC's ASO 2026 ONI is +2.46, a strong El Niño.** Historically that means Texas and Southeast winter wet calls pay 1.35-1.48x. A market maker that prices those calls on climatology this winter is selling into the signal.
   - South-central winter dryness correlates −0.34 with Seattle's and −0.18 with the Ohio Valley's, so those are natural pairs. The southern tier co-moves (+0.25 to +0.37).
   - A book concentrated where demand actually sits, south-central farmer puts for Nov-Feb, needs **1.32** capital95 per premium. The equal-weight national annual pool needs 0.13.
4. **Venue contracts need daily or hourly settlement, and the pricing has to be timed.**
   - No function of the monthly total replicates a wet-weekend-day payout. The best in-sample fit explains a median 27% of its variance (44% for all wet days).
   - A strip of Kalshi-style daily ">0 in" binaries on Fri-Sun explains 53% of a ≥0.10 in weekend-day payout.
   - Daily markets list close to the date, so their prices already contain the forecast. A venue can only hedge forecast error that way, not the seasonal risk at a climatological price.
   - For hyperlocal settlement, the candidate is MRMS hourly QPE at 1 km. Its gauge-corrected Pass 2 product arrives about 2 hours late.
   - Any gridded index needs a version-freeze rule. PRISM stays "provisional" for 1-6 months.
5. **Use a single coherent pricing engine for both sides of a station-month.**
   - An LMSR (logarithmic market scoring rule) over the strike partition prices farmer puts and venue calls from one probability vector, with a known maximum subsidy of b·ln n. Logit-space Avellaneda-Stoikov quoting (arXiv 2510.15205; arXiv 2607.17991, Jul 2026) adds inventory and time-to-settlement skew.
   - Feed it an ENSO-conditional and trend-adjusted prior (items 2 and 3).
   - Settlement can be outsourced to a neutral agent. Speedwell, now part of Xweather, is CME's weather settlement data supplier and states alignment with the IOSCO (International Organization of Securities Commissions) benchmark principles.

---

## 1. Index and data alternatives that cut basis risk

The existing notes and doc 06 already cover the ASOS gauge biases, CPC and nClimGrid (PRF moves to nClimGrid-Monthly from crop year 2027, doc 01), Arbol's ERA5 snow product, and CHIRPS/TAHMO in Africa (`uninsured_farmers.md`). What follows is new or sharper.

| Product | Resolution / cadence | Latency and revisions | Best use here | Evidence | Verdict |
|---|---|---|---|---|---|
| **MRMS multi-sensor QPE** (radar plus gauges) | 1 km, 2-min mosaic; QPE accumulations of 1-72 h | Pass 1: 60 min, about 60-65% of gauges. Pass 2: 120 min, about 99% of gauges. | Venue "rain between 4 and 10 pm at this address" contracts, with the farmer settled on the same grid | [NOAA MRMS doc](https://repository.library.noaa.gov/view/noaa/15285/noaa_15285_DS1.pdf); [Planetary Computer, MRMS 1h Pass 2](https://planetarycomputer.microsoft.com/api/stac/v1/collections/noaa-mrms-qpe-1h-pass2); [IEM archive](https://mesonet.agron.iastate.edu/archive) | **Worth adding** (venue side) |
| MRMS known errors | Radar-only products underestimate in the cool season; melting-layer errors; stuck gauges (10-18% of hourly gauge reports in a winter case) | — | Restrict to warm-season venue contracts, or settle winter on gauges | [NOAA cool-season eval](https://repository.library.noaa.gov/view/noaa/14632/noaa_14632_DS1.pdf); [OU REU 2020](https://reu.caps.ou.edu/reu20/finalpapers/Santer-finalpaper.pdf) (student report) | Design constraint |
| **nClimGrid-Daily** | About 5 km daily, 1951 to present, from GHCN-D | Preliminary 2-3 days after the date; occasional delays | A 75-year back-history at any address, the same family as the PRF index from 2027 | [NCEI product page](https://www.ncei.noaa.gov/products/land-based-station/nclimgrid-daily); [user guide](https://ncei.noaa.gov/pub/data/daily-grids/v1-0-0/nclimgrid-daily_v1-0-0_user-guide.pdf) | **Worth adding** (pricing history for grid-settled contracts) |
| PRISM daily | 4 km daily (800 m on request) | "Provisional" for 1-6 months, "stable" after 6. The day ends at 7 am EST, not midnight. | Farmer-side backtests; poor for weekend or evening venue windows | [PRISM Explorer](https://www.prism.oregonstate.edu/explorer/); [PRISM formats](https://prism.oregonstate.edu/formats) | Minor; the revision lag is a settlement hazard |
| Stage IV (NCEP radar-gauge) | About 4 km hourly, 2002 onward | Unverified | A longer radar back-history than MRMS for pricing hourly contracts | none found this session | Unverified, check |
| ERA5 reanalysis | About 28-31 km, hourly | About 5 days for ERA5T (unverified) | Mountain snow when SNOTEL is absent (Arbol uses it, `ski_snow.md`) | [Earth Map ERA5 note](https://help.earthmap.org/datasets/climate) | Minor for the US |
| CHIRPS v3 / IMERG | CHIRPS about 5 km pentad/daily/monthly; IMERG 0.1°, 30 min (unverified) | — | International bridge insurance only. CHIRPS underestimates extreme intensity (Arbol's own post). | [Arbol CHIRPS post](https://arbol.io/post/working-with-the-chirps-dataset); [CHC CHIRPS](https://chc.ucsb.edu/node/497); [CHIRPS review](https://uwe-repository.worktribe.com/OutputFile/11391527) | Minor (US); useful abroad |
| Satellite soil moisture (SMAP, ASCAT) | About 9-36 km | — | A drought trigger closer to plant-available water than rain. African Risk Capacity uses satellite soil moisture. | [Vreugdenhil, CCCA 2024 poster](https://ccca.ac.at/fileadmin/00_DokumenteHauptmenue/05_Veranstaltungen/Klimatag/2024/P_21_Vreugdenhil.pdf); [rain vs soil moisture for WII](https://core.ac.uk/download/150158966.pdf) | Worth noting. I found no head-to-head study against a rain index on the same contracts. |
| NDVI (IBLI) | eMODIS: free, with a **5-week lag**; BOKU is filtered in near real time | — | Pastoral and forage index. IBLI covers only 62-77% of herd-mortality risk, mostly because losses differ between households. | [BASIS Brief 1](https://basis.ucdavis.edu/sites/g/files/dgvnsk466/files/2017-02/BASIS-BRIEF1.pdf); [UC Davis NDVI comparison](https://basis.ucdavis.edu/node/2936) | Minor here: the lag is incompatible with monthly settlement |
| WeatherXM and private stations | Dense hobbyist and DePIN stations with hourly quality scoring (QoD) | — | Farm or venue site gauges. Quality is self-scored; meteoblue filters low-QoD stations (Aug 2025). | [WeatherXM QoD docs](https://docs.weatherxm.com/rewards/data-quality); [meteoblue changelog](https://business.meteoblue.com/changelog/weatherxm-station-quality-filtering) | Not useful as a settlement source; vendor-only validation and tamper risk (see the Paris-CDG case in doc 05) |

**Why it matters.**
- The team's binding constraint is the 30-55 mi station-to-farm basis (docs 07-09). A grid-settled contract removes that basis for the hedger and moves it to the market maker whenever the two sides settle on different cells.
- The cross-station check in item 7.10 shows this costs little at 95% within 250 mi. It does break full-collateral netting, because both sides can now pay in the same month: 1.3% of months at 50-100 mi and 2.7% at 100-200 mi.

**Settlement mechanics to copy.**
- Freeze the version used for settlement. Settle on MRMS Pass 2 at T+3 h, or nClimGrid preliminary at T+5 days, and never re-settle afterwards.
- Name a fallback, such as the nearest ASOS station, for outages.
- PRF already handles revisions this way through RMA's index rules (doc 01). The specific T+ choices are my proposal.

## 2. Oracles and settlement agents in use

| Agent | What it does | Evidence | Verdict |
|---|---|---|---|
| **Speedwell Settlement Services, now part of Xweather (Vaisala)** | Supplies verified station observations to settle CME weather contracts and forward curves for margining. The page cites "18 exchange-listed stations settled daily". Data adjustments are documented with audit trails, and it states alignment with the IOSCO benchmark principles. | [Artemis: CME to use Speedwell](https://www.artemis.bm/news/cme-weather-contracts-to-use-speedwell-data-for-settlement-valuation/); [CFTC filing](https://cftc.gov/filings/ptc/ptc0504231386.pdf); [Xweather settlement services](https://www.xweather.com/products/settlement-services) | **Worth adding.** It is the template for an independent calculation agent if the team runs an OTC book. Not mentioned in the existing notes. |
| Chainlink with AccuWeather node | AccuWeather has run a Chainlink node since 2021, with crop and disaster parametric insurance named as uses. Arbol's contracts pay out through Chainlink-delivered data. | [AccuWeather press](https://www.accuweather.com/en/press/chainlink-and-accuweather-to-bring-world-class-weather-data-on-to-blockchains/994046); [Arbol and Chainlink](https://www.arbol.io/post/businesses-and-farmers-can-now-hedge-weather-risk-through-the-arbol-platform-and-chainlink-data) | Minor. The oracle only transports data; index quality still comes from the source (NOAA/ERA5/CHIRPS). |
| dClimate (Arbol spin-out) | A decentralized climate-data network. Arbol settles "leveraging climate data and models from dClimate" (NOAA, NASA, ESA plus commercial). | [Intro to dClimate](https://www.arbol.io/post/an-introduction-to-dclimate-a-decentralized-network-for-climate-data-2); [About Arbol](https://arbol.io/about-arbol) | Minor |
| Ensuro + WeatherXM; Open-Meteo in hackathon projects | DeFi insurers pulling hobbyist or free-API data | [WeatherXM insurance page](https://weatherxm.com/industry-insurance); [Clim Protocol (Chainlink hackathon)](https://chain.link/hack-26/projects/clim-protocol) | Not useful. These are marketing-grade claims. |

**Inference.** Real money settles on audited official data (Kalshi on NWS CLI reports, CME through Speedwell, PRF on NOAA grids). Oracles are plumbing. A small platform's credibility will come from the index and the freeze rule, not from blockchain.

## 3. Climate teleconnections: ENSO and cross-region structure

**Literature.**
- Ropelewski and Halpert (1986, Mon. Wea. Rev. 114) mapped North American regions with consistent ENSO precipitation responses ([IRI summary](https://iridl.ldeo.columbia.edu/maproom/ENSO/New/ropelewskihalpert.html); [NOAA bulletin](https://repository.library.noaa.gov/view/noaa/33759/noaa_33759_DS1.pdf)). Not every event follows the composite, and the Western US signal varies over time ([WRCC La Niña handout 2020](https://www.weather.gov/media/vef/wrcc_la_nina_handout_december_2020_final.pdf)).
- Singh et al. (2022, Nature Climate Change) find ENSO is the main driver of concurrent droughts across regions, and project rising exposure to compound drought ([ORNL](https://www.ornl.gov/publication/enhanced-risk-concurrent-regional-droughts-increased-enso-variability-and-warming)).

**New numbers: Nov-Mar, 1951-2025.**
- The phase is classified on the ASO ONI before the season (≥ +0.5 El Niño, ≤ −0.5 La Niña), using [CPC oni.ascii.txt](https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt) retrieved 2026-11-19. That gives 20 El Niño, 18 La Niña and 38 neutral seasons.
- Unit payouts use the netting script's rain terms, so 1.00 equals climatology.

| region | put after El Niño | put after La Niña | call after El Niño | call after La Niña |
|---|---|---|---|---|
| south_central | 0.66 | **1.49** | **1.35** | 0.70 |
| southeast | 0.51 | 1.37 | **1.48** | 0.71 |
| west | 0.82 | 1.17 | 1.23 | 0.80 |
| midwest | 1.26 | 0.78 | 0.99 | 1.10 |
| northeast | 0.86 | 0.96 | 1.33 | 0.87 |

- **Stations:** Tampa's put pays 0.37 after El Niño and 1.49 after La Niña. Phoenix: 0.50 and 1.59. San Antonio: 0.53 and 1.76. Seattle's call pays 1.64 after La Niña. Lexington's put pays 1.60 after El Niño and 0.35 after La Niña.
- **Diversification:** ENSO explains only 8% of the year-to-year variance of the national winter put pool (corr −0.28), but 16% of the south-central pool's (corr −0.40). The southern tier co-moves: mean pairwise winter-put correlation across 12 southern stations is 0.25, and south-central correlates 0.37 with PHX/LAX/ABQ and 0.31 with MIA/TPA.
- **Natural cross-region pairs:** south-central winter dryness correlates −0.34 with SEA and −0.18 with CMH/IND/LEX/PIT. A Texas rancher's winter put therefore partly offsets a Pacific Northwest or Ohio Valley farmer's winter put. That is netting without needing a venue.
- **Why it matters:** the netting note's mean dry correlation of about 0.00 beyond 1,000 mi averages positive same-tier pairs with negative dipole pairs. A book whose demand sits in the southern tier (Texas ranchers, the PRF Companion's Nov-Feb months) is much less diversified than the equal-weight pool suggests (item 7.3).
- **Verdict: worth adding.** Add an ENSO-conditional table to the netting study, and an ENSO-state prior to any quote.

## 4. Pricing under climate trends

**Literature.**
- Jewson and Brix (2005, *Weather Derivative Valuation*, CUP) treat burn analysis as the first step, detrended burn as its extension, and index modelling (fitting a distribution) as more stable when the distribution is well estimated ([Cambridge chapter](https://www.cambridge.org/core/books/abs/weather-derivative-valuation/valuation-of-single-contracts-using-burn-analysis/D64AFD3531EBA2D9DB7FC6B0C25A5FD9)).
- Clements, Hurn and Lindsay find raw historical burn "particularly poor" when temperature trends ([QUT](https://eprints.qut.edu.au/219929/1/62792.pdf)).
- Practitioner rule of thumb: 10-20 year lookbacks with the trend handled ([GlobalCapital primer](https://www.globalcapital.com/article/k6b949lwmyxj/and-now-the-weather-part-iii-an-introduction-to-weather-derivatives)).

**New walk-forward test.**
- For each year from 1996 to 2025, strikes are set on all prior years and the premium is set by one of five methods. The loss ratio is pooled: sum of payouts over sum of pure premiums, where 1.00 is fair and the load is 1.20.
- "Disp." is the median |log| of the per-station-month loss ratio: how wrong one contract's price is.

| variable | method | put LR | call LR | pair LR | call disp. | share of station-months with pair LR > 1.2 |
|---|---|---|---|---|---|---|
| rain | all history (current script) | 1.03 | 1.14 | 1.09 | 0.30 | 33% |
| rain | last 30 yr | 1.08 | 1.05 | 1.06 | 0.24 | 22% |
| rain | **last 15 yr** | 1.07 | 1.04 | **1.05** | **0.16** | **15%** |
| rain | linear-detrended index | **1.25** | 0.99 | 1.08 | 0.22 | 34% |
| rain | **linear trend in payout** | 1.12 | 0.96 | **1.02** | 0.22 | 21% |
| temp | all history | 0.45 | **1.90** | 1.18 | 0.60 | 45% |
| temp | **detrended index** (Jewson-Brix standard) | 0.72 | 1.20 | **1.06** | 0.26 | 27% |
| temp | last 15 yr | 0.79 | 1.26 | 1.14 | 0.23 | 32% |
| snow | all history | 1.25 | 1.05 | 1.15 | 0.22 | 44% |
| snow | last 15 yr | 1.12 | 0.99 | 1.05 | 0.12 | 12% |
| snow | linear trend in payout | 1.08 | 0.93 | 1.01 | 0.15 | 21% |

- **Takeaways:**
  - Recent-window burn (15 years) or payout-trend pricing roughly halves the drift for rain and snow.
  - Index detrending is right for temperature but wrong for rain puts (1.25): a linear additive trend in a zero-bounded, skewed variable distorts the lower tail.
  - Even detrended, warm-side temperature calls are still underpriced by 20%, which suggests the warming has accelerated.
  - Recent windows are noisier for any single contract (last-15 put dispersion could not be computed because some desert months have zero premium), so use them pooled or shrunk toward the long-run value.
- **Verdict: worth adding.** It turns the note's "needs trend-adjusted pricing" into a concrete method choice.

## 5. Forecast-driven adverse selection and its timing

- **What exists:** `market_maker_model.md` already cites CPC week 3-4 skill (temperature about 3x precipitation) and late-month resolution risk.
- **New: seasonal (ENSO) adverse selection is large and known months ahead.** The ASO ONI is public by early November, before the Nov-Mar contracts. A buyer who trades only on the favorable signal produces these loss ratios against a market maker priced on climatology:
  - south-central puts after La Niña: 1.49
  - south-central calls after El Niño: 1.35
  - Southeast puts after La Niña: 1.37
  - Southeast calls after El Niño: 1.48
  - Seattle calls after La Niña: 1.64
  - Midwest puts after El Niño: 1.26
  - West puts after La Niña: 1.17

  All but the West exceed the 1.20 load.
- **Fixes:**
  - Condition the price on the ENSO state (CPC's probabilistic ENSO outlook).
  - Or sell season contracts only before the ENSO outlook firms up, for example by July for winter cover.
  - Jewson and Caballero (2003, Meteorol. Appl. 10:377) show how to blend forecasts into the expected payoff ([Cambridge listing](https://resolve-he.cambridge.org/core/journals/meteorological-applications/article/use-of-weather-forecasts-in-the-pricing-of-weather-derivatives/2FC83860F500F1EDA45F42C988D86E9B)).
- **This winter:** with ASO 2026 ONI at +2.46, climatology-priced Texas and Southeast venue rain calls would be sold at roughly 1.35-1.48x underpricing. The PRF Companion's Nov-Feb dry-side hedges for Texas farms historically pay about 0.66x climatology in El Niño winters.
  - Whether Kalshi's prices already reflect El Niño is testable from the saved candles (`kalshi_rain_daily_candles.parquet`). I did not test it.
- **Verdict: worth adding.** It is the sharpest near-term risk, and it is in the team's own region.

## 6. Market-making mechanisms for binary and event contracts

| Mechanism | Key property | Evidence | Fit for the team |
|---|---|---|---|
| **LMSR** (Hanson) | Cost C(q) = b·ln Σ e^{q_i/b}. Prices sum to 1, and the worst-case loss is **b·ln n**, set in advance. Equivalent to an exponential-utility market maker (Chen and Pennock). | [Chen and Pennock, arXiv 1206.5252](https://arxiv.org/pdf/1206.5252); [Complexity of combinatorial MMs, arXiv 0802.1362](https://arxiv.org/pdf/0802.1362) | **Worth adding.** One LMSR over a station-month's n outcome bins (Kalshi's ladder) quotes the farmer's low bins and the venue's high bins coherently. Opposite trades move prices back toward the prior automatically, and the subsidy cap answers "how much capital". With b = $1,000 and n = 8 bins, the worst case is about $2,079 per station-month (my arithmetic). |
| **Logit-space Avellaneda-Stoikov** | Reservation price in log-odds, shifted by inventory, risk aversion and time to resolution; jump-diffusion beliefs | [Daedalus, arXiv 2510.15205](https://arxiv.org/html/2510.15205v2); [Optimal MM in prediction markets, arXiv 2607.17991 (Jul 2026)](https://arxiv.org/pdf/2607.17991) | **Worth adding** for quoting on Kalshi as a maker. Skewing quotes toward the side that reduces the net exposure is exactly the farmer/venue netting in quote form. |
| Empirical check | One Polymarket market fits a logit AS benchmark only loosely | [Tartu thesis](https://dspace.ut.ee/items/b6ff7a3f-17e4-4009-86f6-899560034b3a) | Minor |

## 7. Critique of `netting_quant.md` and `run_expansion_netting.py`

| # | Issue | Severity | Evidence (my checks) | Suggested fix |
|---|---|---|---|---|
| 7.1 | **The per-premium normalization credits netting with what is mostly diversification.** Doubling the contracts doubles the premium buffer. | **High** (changes the headline) | Two puts more than 1,000 mi apart: capital95 1.96 per premium. A put plus a call at a distant station: 1.97. Same-station pair: 1.72-1.76. Single put: 3.57. The opposite-side benefit is real in the worst year: 2.16-2.29 for the same-station pair against 3.50-3.57 for distant pairs (`twocontract.py`). | Add a "second independent contract" baseline row. Present the netting benefit as the gap between that baseline and the pair (about 0.2 at 95%, about 1.3 in the worst year). Lead with collateral and worst year, where the netting really shows. |
| 7.2 | **Pooling results are priced in-sample.** The mean loss is exactly −load by construction, so the "annual pair pool capital 0.00" finding is an artifact. Drift is common across stations. | **High** | Priced on 1951-1995 and realized 1996-2025, national annual pool: put capital95 0.10 per premium (worst year +0.22); call 0.33 (mean margin −0.002, P(loss) 0.53); pair 0.038 (worst +0.055). Monthly national put: 0.55 against 0.89 in-sample, which is lower because the put side happened to drift favorably. | Run the pooling on the out-of-sample or walk-forward units, and report pooled loss ratios as ratios of sums. |
| 7.3 | **Equal-weight national pooling overstates diversification.** The note says so; the size of the effect is large. | **High** | South-central Nov-Feb farmer pool (the companion months): capital95 **1.32** per premium, worst year +1.90. Plains and West Apr-Sep pool: 0.34. Equal-weight national annual: 0.13. ENSO co-movement in item 3. | Report demand-weighted scenarios, plus ENSO-conditional capital (for example, capital95 for La Niña winters only). |
| 7.4 | **The out-of-sample split has no significance test, and the medians carry a finite-sample bias.** | Medium | A placebo of 300 year-shuffles keeping cross-station structure gives a null median call ratio of 0.98 (95% band 0.87-1.08) against the actual 1.175, so the drift is real. The null median put ratio is 1.03 (0.92-1.15), so the put's 0.99 is consistent with no drift, or a slightly wet one. Ratio of sums: put 1.028 and call 1.203, against medians of 0.992 and 1.175. | Report placebo or bootstrap bands, and ratio-of-sums alongside medians. |
| 7.5 | **The only pricing method is full-history burn.** | Medium | Walk-forward table in item 4: last-15 or payout-trend pricing gives a pair loss ratio of 1.02-1.05 for rain and 1.01-1.05 for snow; detrending gives 1.06 for temperature. | Make pricing a parameter of the script (window, payout trend, index detrend for temperature), and show the loss ratio and dispersion for each. |
| 7.6 | **Adverse selection is "not modeled", but it is measurable from history.** | Medium-high | ENSO-timed buying gives loss ratios of 1.17-1.64 (item 5). | Add an ENSO-conditional loss-ratio table, and a sales-cutoff or conditional-price rule. |
| 7.7 | **The 99% tail uses a renormalized simulated premium, and the call's 99% figure is capped by design.** | Low-medium | The simulation divides payouts by their simulated mean, not by the premium actually charged on empirical data. That is harmless in the median: simulated var95 is 3.568 against empirical 3.571. Pooled PIT check: 1.31% of months fall below the fitted 1st percentile and 2.35% below the 2nd (`tailcheck.py`, in-sample), so the gamma slightly understates extreme dryness. Call capital99 (4.45) is close to its collateral (4.49), so the 99% figure says nothing new for calls. | Price the simulation with the empirical premium. Add parameter uncertainty (bootstrap the gamma fit) or a lower-tail check. Drop capital99 for capped calls. |
| 7.8 | **The put and call designs are asymmetric.** The put exhausts at 0 in; the call exhausts at the 95th percentile. | Low-medium | Collateral is 6.36 for the put against 4.49 for the call, so the put-only versus call-only comparison is design-driven. | Add a sensitivity run with symmetric 5th/95th exhausts and 20/80 strikes. |
| 7.9 | **The record changes in the middle of the record.** ASOS deployment (about 1992-97) straddles the 1995 split. | Medium (sign matters) | The ASOS heated tipping bucket under-measured by 2-10% against manual gauges, more in heavy rain and snow, with a modified gauge from 1996 ([NRC 2012 retrospective](https://www.nap.edu/read/13216/chapter/13)). That biases post-split totals down, so the wet-call drift is probably understated and dry-put drift overstated. Airport snowfall records are known to be inhomogeneous ([Kunkel et al. 2007](https://climate.rutgers.edu/stateclim_v1/robinson_pubs/refereed/Kunkel_et_al_2007.pdf)), so part of the 1.27 snow drift may be measurement. Split-year sensitivity: the call loss ratio is 1.20-1.29 for splits from 1980 to 2005 and the put 0.97-1.03, so the result is not a single-break artifact. HO-83 temperature-sensor warm bias: unverified this session. | Cross-check the drift on nClimGrid cells around each station (the team already has `ncei_monthly_precip_grids.parquet`). Flag snow drift as partly measurement. |
| 7.10 | **The same-station assumption hides the market maker's own basis** if sides settle on different stations or grid cells. | Low | A put at A and a call at B, by A-B distance: capital95 1.79 (0-50 mi), 1.77 (50-100), 1.75 (100-200) and 1.79 (200-300), against about 1.72-1.81 for the same station. The share of months in which both sides pay rises from 0 to 1.3%, 2.7% and 4.0% (`crosspair.py`). | Report it. Netting at 95% survives; full-collateral netting does not. |
| 7.11 | Minor code points | Low | `n_effective_independent` mixes std ddof=1 with var ddof=0. The West annual pool has only 3 stations (its n_eff is capped at 3.0). Daily S/A flags are set to 0, as the note already says. | Label it; use one ddof. |
| 7.12 | **Exchange collateral.** On Kalshi each contract is fully collateralized, so a market maker holding both sides does not get capital95 netting unless it is the counterparty itself (OTC or a platform book). | Medium (framing) | Note section 2 says this for `rain_days` only. Whether Kalshi nets collateral across mutually exclusive bins within one event: unverified. | State that capital95 and capital99 are for an OTC or own-book market maker, and that collateral is what applies on Kalshi. |

**Conclusions that survive:** pairing helps; a February snow and October-to-February rain focus; drift dominates; basis sits with the hedgers.

**Conclusions that change:**
- The 95% benefit is mostly diversification (7.1).
- Pooling does not diversify drift (7.2).
- Real demand-weighted books need about 10x the equal-weight national capital (7.3).
- ENSO adverse selection is already larger than the load (7.6).

## 8. Contract design for venues

- **The monthly ladder cannot replace day counts.** Across 37 stations and all months, the monthly total correlates 0.53 (median) with wet Fri-Sun days at ≥0.10 in. The best in-sample function of the monthly total explains a median 27% of a wet-weekend-day call's variance (10th-90th percentile: 16-42%), and 44% for all wet days (`review_checks.py` section 6). Doc 23's strike-bin replication cannot synthesize a rainy-day payout. **Verdict: worth adding**, because it settles the question.
- **Strip of daily binaries.** Kalshi's daily rain markets settle on more than 0 in (`hospitality_venues.md`, secondary sources). Fri-Sun counts of >0 in days correlate 0.77 with ≥0.10 in counts. They explain 53% of a ≥0.10 in weekend-day payout's variance, and 38% at ≥0.25 in (`daycheck.py`).
  - Daily markets are short-dated, so the venue pays a forecast-informed price. A strip bought day by day hedges forecast surprises, not a bad season.
  - A seasonal venue product needs a rolling or count contract written before the forecast horizon (for example, a "number of wet Fri/Sat evenings in Jun-Aug" swap priced on nClimGrid-Daily or MRMS history).
- **Hourly windows** (for example, 4-10 pm) need MRMS or a site gauge. Station daily totals use a midnight-to-midnight local-standard-time day, and PRISM's day ends at 7 am EST. Descartes uses temporary on-site stations for event cover ([Descartes festival case](https://descartesunderwriting.com/case-studies/how-parametric-rainfall-insurance-could-protect-major-music-festival-barcelona)). Lockton describes gauge, satellite or radar triggers over sub-daily peak hours, with a 10 mm example ([Lockton](https://global.lockton.com/gb/en/news-insights/weathering-the-storm-utilising-parametric-insurance-to-tackle-event-cancellation)).
- **Multi-trigger** (rain AND temperature, for example a rainy day with high below 65°F for patios) is not implemented. With the cached ACIS daily `avgt`, the team could test it cheaply. It reduces premium and false positives for venues but breaks the clean put/call mutual exclusivity with farmers. **Minor** until a venue partner states its loss driver.
- **An ENSO-conditioned season contract** (venue wet call and farmer dry put sold together before the outlook) also falls out of items 3 and 5.

## Gaps and unverified items

- No head-to-head study of SMAP versus rain-index basis risk for US forage or pasture was found.
- Stage IV, IMERG and ERA5 latency figures are unverified (no primary page fetched).
- Whether Kalshi nets collateral across bins within one event is unverified.
- The ENSO conditional numbers rest on 18-20 seasons per phase: they are directional, with no confidence bands computed.
- Walk-forward results use the netting script's percentile strikes, reset each year. A real product would fix strikes for a season.
- All new numbers are backtests on station climatology, not observed demand or prices.
