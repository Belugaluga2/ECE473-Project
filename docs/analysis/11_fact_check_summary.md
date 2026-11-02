# Fact-check of research docs 01, 02, 03b, 04, 05, 06

**Proposal cell:** Milestone 1 follow-up (overview next step 2)  |  **Status:** DONE for the claims listed. Many claims were not re-checked; the per-doc logs list them  |  **Last updated:** 2026-11-01

## What was done

- **Headline numbers first.** We checked the numbers the overview quotes from docs 01, 02, 03b, 04, 05 and 06, and tried the Luo numbers in doc 10 (SSRN unreachable; see below). We re-read each one in a primary source on 2026-11-01: the U.S. Code, RMA bulletins and reports, CPC documentation, the Kalshi API and contract terms, NASS reports, CRS, and the cited papers.
- **PRF market numbers re-derived independently.** We downloaded RMA Summary of Business `sobcov` files for 2015-2025 again and summed them with a new script, [`scripts/factcheck_sob.py`](../../scripts/factcheck_sob.py), which shares no code with `pull_rma_sob.py`. Tests are in [`tests/test_factcheck_sob.py`](../../tests/test_factcheck_sob.py).
- **Logs and edits.** Each doc now ends with a "Fact-check log" table (claim, source checked, verdict). Wrong numbers were corrected in place and marked "corrected".
- **Independent review and merge.** This branch (`final/factcheck`) is `run/factcheck-2` plus reviewed pieces of `run/factcheck-1` (rows 6-8 of the corrections table, the doc 10 log) and one reviewer fix (row 4). Every grafted number was recomputed by the reviewer on 2026-11-01 from `sobcov_2015..2025` or `data/processed/kalshi_rain_calibration.csv`.
- **What the verdicts mean.**
  - **confirmed**: re-read and matching.
  - **corrected**: wrong, and fixed.
  - **qualified**: true only under a stated condition.
  - **unverifiable**: the source could not be opened or parsed with the tools available, or the claim was not re-checked in this pass. It does not mean the number is wrong.

## Corrections and their downstream impact

| # | Doc | Claim as written | Correct value | Source | Downstream impact |
|---|---|---|---|---|---|
| 1 | 02 (numbers table, sec. 1.4 table) | 2023 crop book: liability 208.04, premium 19.19, subsidy 11.75, indemnity 19.03 $B; LR 0.99; subsidy share 61.2% | 181.62 / 18.11 / 11.33 / 17.80 $B; LR 0.98; share **62.6%** | RMA `sobrpt2023-2026.pdf` p.1, "Combined Business" (as of 2026-11-02); matches our `sobcov_2023` sum (181.619 / 18.105 / 11.328 / 17.795). The old values came from `sobrpt2014-2023.pdf`, whose 2022 and 2023 columns run $21-26B of liability above the crop-only basis used for 2024-2026 | Doc-only. The overview headline (62.9% in 2025) is unchanged. No code or data uses the 2023 row |
| 2 | 05 (key findings, numbers table, sec. 1) | Kalshi a DCM "since the order of 2020-11-04" | Order dated **2020-11-03**, announced 2020-11-04 | CFTC release 8302-20 ("today announced that it has issued an Order of Designation"); order PDF `orgkexkalshidesignation201103.pdf` | Doc-only. Doc 02 already had the right dates |
| 3 | 05 (numbers table) | Fee on 1 contract at $0.20 = $0.02 (10% of premium) | **Qualified**: $0.02 under the 2022 "next cent" rule and for FCM-cleared accounts. About $0.0112 for direct members under Kalshi's current fee-rounding rule (round up to $0.000001; balance precision $0.0001) | https://docs.kalshi.com/getting_started/fee_rounding | None for our results. `kalshi.fee()` rounds each order up to the cent, which matches the 100-contract example exactly ($1.12) and overstates single-contract fees by under 1 cent. Hedge orders in doc 09 are many contracts, so the effect is negligible. Code unchanged |
| 4 | 02 (key findings, numbers table, sec. 3.2) | "LFP paid $1.78 billion in FY2023, more than PRF's 2023 indemnities of $1.07 billion"; numbers table "2022 dollars" | Same numbers, but the LFP figure is **inflation-adjusted with no base year stated** for the FY series, and the PRF figure is nominal. **Units corrected**: the earlier "2022 dollars" label came from the Figure 2 note, which covers calendar years 2008-2022, not FY2019-2023; footnote 42 uses 2023 dollars for calendar-year values | CRS R48082 text ("LFP payments, in inflation-adjusted dollars, ..."), Figure 2 note, footnote 42 | Wording only. The overview's headline "It paid $1.78 billion in FY2023" should add "(inflation-adjusted)" when the lead updates it |
| 5 | 01 (key findings, numbers table) | Jan-Feb cap 25% "(California keeps 50%)" | 25% **confirmed**. The California exception is **unverifiable** here: PM-26-053 states no exception, and the claim rests on ADM27 A00810, which we did not re-download | PM-26-053 | `prf_rules.yaml` keeps the California exception (line `exception: {state_fips: "06", ...}`). No study site is in California, so no result changes. Left as is and flagged |
| 6 | 01 (sec. 1) | PRF is RMA's "only rainfall-index insurance" | PRF is the largest product under the Rainfall Index plan (13), not the only one: 2025 liability PRF $6,547.0M, Annual Forage $1,222.1M, Apiculture $461.8M (plus $432.7M masked) | RMA `sobcov_2025` plan 13 by commodity | Doc wording only. **The overview repeats it** ("USDA's only rainfall-index policy"); the lead should reword. No code impact |
| 7 | 04 (key findings) | Pooled 2015-2025 loss ratios Parker 0.90, Torrance 0.69 | **Clarification**: both include RMA's masked "All Other Crops" (9999) Rainfall Index rows. PRF-only (0088) rows give Parker 1.08 (2022-2025 only) and Torrance 0.71, the values doc 02 uses | `sobcov_2015..2025`, county 48367 and 35057 | Doc note only. Quote the PRF-only figures when comparing with doc 02 |
| 8 | 05 (key findings) | Monthly rain, 7 days out: YES < $0.20 averaged 4.7 cents, won 1.6% | **Clarification**: that is on last-trade prices (505 contract-days). On mid-quotes the same bins give 6.6 cents and 4.7% YES (253 contract-days) | `data/processed/kalshi_rain_calibration.csv` | Doc note only. State the price measure when quoting the longshot result |

**No corrected number feeds code or committed data.** `prf_rules.yaml`, `farms.yaml` and all processed datasets are unchanged, so no affected tests needed a rerun beyond the full suite.

## Overview next step 1 (hay prices): settled, no change

The overview flagged that `farms.yaml` uses TX $130, OK $88 and MO $113 per ton, while the "NASS Crop Values 2025 summary" says $136, $90 and $114.

- **Both are real NASS numbers.** We re-queried NASS Quick Stats (period "MARKETING YEAR") on 2026-11-01 and got exactly 130 / 88 / 113 (and every other doc 04 state value).
- **The Crop Values figures are preliminary.** The Crop Values 2025 Summary (2026-02-26) marks its 2025 column "Preliminary". The hay marketing year runs May 2025 to April 2026, so a February number cannot be the full-year average.
- **Not a definitional difference for these states.** The table's alfalfa-mixture footnotes (3/ "Alfalfa and alfalfa mixtures included in all other hay" and 4/ "Beginning in 2024 ...") are attached to other states (for example Florida and Arkansas), not to Texas, Oklahoma or Missouri (reviewer check of `cpvl0226.txt`, p.33).
- **Decision.** Quick Stats carries the current value, so `farms.yaml` stays as it is.
- **Remaining inconsistency.** Doc 03b's replacement-value calculations use the preliminary 136 / 90 / 114. For consistency, switch doc 03b to the Quick Stats values. That changes its "$ per inch" and PRF-to-loss ratios by 1-5% at the Texas, Oklahoma and Missouri sites. Not done here, because those numbers come from `scripts/r2_rain_yield_calcs.py`, which needs raw re-downloads.

## Headline numbers that were confirmed

| Overview headline | Doc | Check | Verdict |
|---|---|---|---|
| 12 private insurance companies | 02 | RMA AIP API, RY2027: 12 companies; 2026 D00100: 12 plus a test code | confirmed |
| Taxpayers paid 62.9% of 2025 premiums | 02 | RMA national report and our `sobcov_2025` sum: 10.590 / 16.835 = 62.90% | confirmed |
| PRF 2025: 298 million acres, $6.55 billion liability | 02 | `sobcov_2025` sum: 298.33M acres, $6,546.98M | confirmed |
| $2.11 back per $1 paid, 2015-2025 | 02 | pooled indemnity 7,836.3 / producer premium 3,717.0 = 2.108 | confirmed |
| Subsidy 51-59% | 01, 02 | 7 U.S.C. 1508(e)(7) | confirmed |
| Payouts beat premiums in 43 of 44 states | 02 | state pooling: 43 of 44 (New Jersey below 1) | confirmed |
| LFP $1.78 billion in FY2023 | 02 | CRS R48082: $1.777B, inflation-adjusted, base year not stated | confirmed (units corrected, #4) |
| PRF pays on CPC through 2026 and NCEI nClimGrid from crop year 2027; 1951 baseline | 01, 06 | RMA release 2026-04-30; RMA "2027 and Beyond" processing PDF | confirmed |
| Jan-Feb capped at 25% from 2027 | 01, 02 | PM-26-053 | confirmed |
| $30 administrative fee | 01 | 7 U.S.C. 1508(c)(10)(A) | confirmed |
| Kalshi is CFTC-regulated; monthly rain ladders in about 35 cities; one NWS station each | 05, 06 | CFTC 8302-20; API: 37 `KXRAIN*M` series (35 cities + NYC + Napa); RAINM terms | confirmed |
| Fee round up(0.07 × C × P × (1 − P)), takers only; 100 at 20 cents = $1.12 | 05 | Bürgi et al. p.6; API: all weather series `quadratic`, multiplier 1; arithmetic | confirmed |
| Five of seven PRF sites only got markets on 2026-10-25; only DFW and DEN have about a year of history | 05 | API on 2026-11-01: one event (Nov 2026) each for OKC, SGF, ABQ, TPA, SAT; 13 each for DFW and DEN | confirmed |
| Position accountability $25,000 per strike per member | 02, 05 | RAINM contract terms | confirmed |
| Favorite-longshot bias on Kalshi (makers −9.6%, takers −31.5%) | 05 | Bürgi, Deng & Whelan (2026) p.27 | confirmed |
| CPC gauge analysis: 0.25° release, 8,000-9,000 gauges/day | 06 | CPC procedure description (2021) | confirmed |
| Sala et al. 1988 spatial rain-production model | 03b | paper p.42 | confirmed |
| Hay prices 2025 (all other hay and alfalfa) | 03b, 04 | Crop Values 2025 Summary (03b); Quick Stats (04) | confirmed (different releases; see above) |
| WASDE prices ($4.70 corn, $12 soybeans) | 03b | WASDE-676 | confirmed |

## Not verified in this pass

- **Luo (2026), doc 10.** SSRN returned HTTP 403 to the fetch tool, and a web search found no other copy. All Luo numbers stay UNVERIFIED (abstract only). Someone needs to download the PDF in a browser.
- **RMA handbook Exhibit 5 example (doc 01).** The PDF downloaded, but its exhibit tables could not be extracted: no PDF renderer or text library is installed in the project venv, and nothing was installed. The repo's tests reproduce these values from `prf_rules.yaml`, but that is not an independent read.
- **ADM-based values (docs 01 and 04).** State interval caps (50/60/70), study-grid premium rates, county base values and the 3,000-record payment-factor fit were not re-checked. ADM files were not re-downloaded, and the DST API returned empty bodies to plain requests.
- **County-level SOB statistics (doc 04)** were not re-computed. Only national and state totals were.
- **Not re-opened.** Most literature numbers in docs 02, 03b and 06 (beyond those listed above), NWS and ASOS specifications, Polymarket and CME details, and FSA ad hoc program amounts.
- **Internal computations** (docs 05b, 06c, the doc 06 spot checks, and all COMPUTED regressions in doc 03b) are out of scope for a web fact-check and were not re-run.

## Numbers table

| Quantity | Value | Units | Region / period | Source | Verification |
|---|---|---|---|---|---|
| Crop book 2023: liability / premium / subsidy / indemnity / LR | 181.62 / 18.11 / 11.33 / 17.80 / 0.98 | $ billion | U.S. 2023 | RMA sobrpt2023-2026.pdf p.1 (as of 2026-11-02), https://pubfs-rma.fpac.usda.gov/pub/sob/current_week/ | CONFIRMED |
| Same per older report | 208.04 / 19.19 / 11.75 / 19.03 / 0.99 | $ billion | U.S. 2023 | RMA sobrpt2014-2023.pdf (as of 2026-11-02) | CONFIRMED (as printed; inconsistent basis) |
| Crop book 2025 subsidy share | 62.90 | % | U.S. 2025 | sobrpt2023-2026.pdf; `scripts/factcheck_sob.py` | CONFIRMED |
| PRF 2025 liability; acres; policies earning premium | 6,546.98; 298.33; 67,872 | $M; M acres; policies | U.S. 2025 | `scripts/factcheck_sob.py` on sobcov_2025 (file dated 2026-10-26) | DERIVED |
| PRF 2015-2025 pooled premium / subsidy / indemnity | 7,933.57 / 4,216.58 / 7,836.32 | $M | U.S. | same script | DERIVED |
| PRF pooled loss ratio; return per producer $; subsidy share | 0.988; 2.108; 53.1% | ratio | U.S. 2015-2025 | same script | DERIVED |
| States with pooled return > 1; loss ratio > 1 | 43 of 44; 12 of 44 | states | 2015-2025 | same script | DERIVED |
| LFP payments FY2023 | 1,777 | $M (inflation-adjusted, base year not stated) | U.S. | CRS R48082 text, https://www.everycrsreport.com/reports/R48082.html | CONFIRMED |
| Rainfall Index plan 2025 liability: PRF / Annual Forage / Apiculture / masked | 6,547.0 / 1,222.1 / 461.8 / 432.7 | $ million | U.S. 2025 | RMA `sobcov_2025.zip`, plan 13 by commodity | CONFIRMED |
| Pooled 2015-2025 loss ratio, Parker TX: with masked rows / PRF-only | 0.90 / 1.08 (2022-2025) | ratio | county 48367 | RMA `sobcov_2015..2025` | DERIVED |
| Pooled 2015-2025 loss ratio, Torrance NM: with masked rows / PRF-only | 0.69 / 0.71 (2017-2025) | ratio | county 35057 | RMA `sobcov_2015..2025` | DERIVED |
| Monthly rain, 7 days out, YES < $0.20: mean price / YES rate, last trade vs mid | 0.047 / 0.016 (n 505) vs 0.066 / 0.047 (n 253) | dollars / share | 139 settled events | `data/processed/kalshi_rain_calibration.csv` | DERIVED |
| Kalshi DCM order date / announcement | 2020-11-03 / 2020-11-04 | date | KalshiEX LLC | https://www.cftc.gov/filings/documents/2020/orgkexkalshidesignation201103.pdf ; https://www.cftc.gov/PressRoom/PressReleases/8302-20 | CONFIRMED |
| Kalshi weather series with fee_type quadratic, multiplier 1 | 500 of 500 | series | 2026-11-01 | https://api.elections.kalshi.com/trade-api/v2/series?category=Climate%20and%20Weather | CONFIRMED |
| Kalshi monthly-rain series | 37 (35 cities + NYC + Napa) | series | 2026-11-01 | same API | CONFIRMED |
| Events per series, new-cohort study sites / DFW, DEN | 1 / 13 | events | 2026-11-01 | API `/events?series_ticker=` | CONFIRMED |
| Fee on 1 contract at $0.20, direct member, current rounding | about 0.0112 | $ | 2026 | https://docs.kalshi.com/getting_started/fee_rounding ; 0.07 × 0.2 × 0.8 | DERIVED |
| Other hay price MY2025, Quick Stats: TX / OK / MO | 130 / 88 / 113 | $/ton | 2025 | NASS Quick Stats (re-queried 2026-11-01) | CONFIRMED |
| Other hay price 2025 (preliminary), Crop Values: TX / OK / MO | 136 / 90 / 114 | $/ton | 2025 | NASS Crop Values 2025 Summary, https://release.nass.usda.gov/reports/cpvl0226.txt | CONFIRMED |
| Sala et al. 1988 regional model | ANPP = −34 + 0.6·MAP, r² = 0.90 | g/m², mm | 100 MLRAs | Sala et al. 1988, Ecology 69:40, p.42 | CONFIRMED |
| CPC daily gauges over CONUS; spacing | 8,000-9,000; about 30 km | stations/day; km | CONUS | CPC procedure description (2021), sec. 1 | CONFIRMED |

## Reproduce

```bash
PYTHONPATH=src AGRI_HEDGE_RAW_DIR=<raw dir> python -I scripts/factcheck_sob.py   # re-derives every doc 02 PRF headline
PYTHONPATH=src python -m pytest -q tests/test_factcheck_sob.py
```
