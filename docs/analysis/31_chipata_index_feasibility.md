# 31: A local public-data index pilot near Chipata, Zambia

**Status: exploratory feasibility, 2026-11-21.** This tests whether the contract-design
machinery can be applied to a public local rainfall series outside DRIVE's countries.
It does not identify an uninsured population, an existing Kalshi market, legal permission
to sell cover, or an improvement in observed agricultural losses.

## Why this place, and existing protection

Chipata is an illustrative maize-growing area in Zambia's Eastern Province. The
2023/24 drought is the motivating event; it was known before this pilot, so it is not
an independent surprise validation. USDA reports that the drought affected Eastern
Province and that January-February dry spells overlapped with important crop stages
([USDA report](https://apps.fas.usda.gov/newgainapi/api/Report/DownloadReportByFileName?fileName=Zambia+Depends+on+Corn+Imports+to+Maintain+Food+Security_Pretoria_Zambia_ZA2024-0001.pdf)).

DRIVE means **De-risking, Inclusion and Value Enhancement of Pastoral Economies**.
Its regional project covers Djibouti, Ethiopia, Kenya and Somalia, rather than Zambia
([World Bank](https://www.worldbank.org/en/news/press-release/2022/06/23/world-bank-boosts-pastoral-economies-and-climate-action-in-the-horn-of-africa)).
Zambia nevertheless has insurance and government support. WFP's R4 evaluation describes
crop insurance integrated into its Farmer Input Support Programme and gaps in insurance
literacy and delivery ([WFP evaluation](https://www.wfp.org/publications/zambia-evaluation-wfps-rural-risk-resilience-initiative-2014-2025)).
Absence of DRIVE or US PRF is not evidence of absence of insurance.

## Data and frozen illustrative design

- ClimateSERV **Global CHIRPS datatype 0**, daily area-mean rainfall over the box
  longitude 32.60-32.70, latitude -13.70 to -13.60. This is about a 10 km area, not an
  individual farm observation. The archive version is not confirmed as CHIRPS v3.
  [Provider API](https://github.com/SERVIR/ClimateSERV/blob/master/docs/api.rst).
- Complete 1981-2025 daily record; inputs are committed as
  `maya_chipata_chirps_daily.csv`. Raw responses and download jobs are cached under
  `data/raw/africa`; the processed CSV is sufficient for offline reproduction.
- NASA POWER/MERRA-2 monthly precipitation near the box center is a dataset sensitivity,
  not a second farm measurement. Its meteorological grid is about 0.5 by 0.625 degrees,
  so "NASA" does not automatically mean better localization
  ([NASA documentation](https://power.larc.nasa.gov/docs/tutorials/service-data-request/api/)).
- Two fixed windows: November-March (harvest-year labeling, using the previous November
  and December), and January-February. Choosing a critical-stage window after knowing
  the motivating 2024 disaster means this remains an illustrative design sensitivity.
- Fit normal rainfall and prices on harvest seasons 1982-2005 (24 seasons); replay
  2006-2025 (20 seasons). No trigger or shape coefficient is tuned to replay outcomes.
- Reuse linear 90%, exponential k=5, disaster-only below index 50 and digital index 30
  targets. Hypothetical premium is 1.20 times the fitting-period average target payout.
  This 20% loading is an assumption, not an obtained quote or a measured local expense.
- If a target never pays in fitting years, its price is **not established**. We do not
  infer free catastrophe cover from zero observed events.

## Results

<!-- BEGIN AUTO: chipata -->

| Window | Shape | Training payout years / 24 | 2024 rain index | Hypothetical premium per unit limit | 2024 target payout per premium |
|---|---|---:|---:|---:|---:|
| Nov-Mar | linear | 7 / 24 | 75.8 | 0.0277 | 5.69 |
| Nov-Mar | exp5 | 11 / 24 | 75.8 | 0.0041 | 3.91 |
| Nov-Mar | deep50 | 0 / 24 | 75.8 | unpriced (no training payouts) | not established |
| Nov-Mar | digital30 | 0 / 24 | 75.8 | unpriced (no training payouts) | not established |
| Jan-Feb | linear | 6 / 24 | 80.5 | 0.0471 | 2.24 |
| Jan-Feb | exp5 | 12 / 24 | 80.5 | 0.0068 | 1.65 |
| Jan-Feb | deep50 | 0 / 24 | 80.5 | unpriced (no training payouts) | not established |
| Jan-Feb | digital30 | 0 / 24 | 80.5 | unpriced (no training payouts) | not established |

<!-- END AUTO: chipata -->

## Interpretation and limits

In the selected CHIRPS area, the 2024 Nov-Mar index is about 75.8 and Jan-Feb about
80.5 relative to fitting-period normals. The below-50 and below-30 catastrophe targets
therefore do not pay in this motivating season. Neither had a positive fitting-period
payout, so their premiums cannot be established by the simple historical mean.
The zero-event 24-year binomial interval still allows a positive event probability;
zero observations do not imply zero risk or free cover.

The NASA/MERRA-2 sensitivity gives 2024 indexes of about 106.9 and 142.8 for those
windows, respectively. This disagreement is itself a reason to validate data products
against local gauges and losses before selecting a settlement index. We do not infer
that one source is correct or that a national drought implies the same shortfall at
this particular location. No alternate location was searched to obtain a better result.

This is a working public-data settlement illustration. The replay answers what these
formulas would have paid on the selected rainfall product, including the 2024 event.
It cannot tell us whether those payments matched a farmer's losses. We deliberately
do not compute HE against the same rainfall formula: that would mainly grade the
formula against itself and manufacture apparent effectiveness.

The CSV contains exact binomial intervals for the frequency of a positive target payout
and bootstrap intervals for the modeled premium. These describe historical-sample
uncertainty only. A sample with no disaster observations cannot identify the missing
tail through bootstrap resampling. Comparison with NASA values exposes dataset choice;
neither product is ground-truth farm loss. There is no executable order book, observed
buyer demand, fitted loss model, local currency/expense model, or independent validation
of improved farmer welfare.

Zambia is not named in the Kalshi restricted-jurisdiction list inspected on 2026-11-21
([Member Agreement](https://kalshi-public-docs.s3.amazonaws.com/kalshi-member-agreement.pdf)),
but that is not a determination of local legality, account eligibility, or availability
of a Zambian weather contract. No account or order is created. A real product would need
an appropriate issuer, funding, distribution, settlement version and local legal review.

## Zambia follow-up checked November 22

Zambia already has substantial index-insurance experience. WFP's 2025 evaluation
reports that R4 reached 17,835 southern smallholders and helped integrate insurance
into FISP, extending coverage to over one million farmers. It also reports weaknesses
in insurance literacy, credit, aggregation and integration. These are possible research
questions, not evidence that Chipata households lack all cover
([WFP evaluation](https://www.wfp.org/publications/zambia-evaluation-wfps-rural-risk-resilience-initiative-2014-2025)).
R4 and FISP are different programmes; being outside an R4 project district does not
establish ineligibility for FISP.

WFP's technical work with Zambia's agriculture ministry and IRI already redesigned
the FISP index using farmer focus-group information from almost 1,000 agricultural
camps. A new contract would need to show value beyond that existing work, rather
than claim that public rainfall data alone is novel
([2021 technical report](https://www.wfp.org/publications/2021-technical-report-zambias-farmer-input-support-program-fisp-index-insurance)).
CGAP's April 2026 case study emphasizes government distribution and combining insurance
with other tools, reinforcing that listing an exchange contract would solve only one
part of delivery
([CGAP case study](https://www.cgap.org/research/publication/scaling-inclusive-insurance-through-government-systems-lessons-world-food)).

The Kalshi restricted-country list was rechecked November 22: Zambia is not named,
but the agreement also requires compliance with applicable local law. That is not a
finding that Kalshi is licensed locally or a promise of account access. Zambia's
Insurance Act 38 of 2021, section 166, generally requires local interests to be insured
through a licensed insurer, subject to a written authorization exception. SEC Zambia
also states that intermediaries conducting derivatives business need appropriate
licensing unless exempt. The Betting Control Act regulates bookmaking. These sources
do not resolve how a particular overseas weather event contract would be classified
or whether an individual may access it. No claim of a blanket ban or permission is made.

- [Insurance Act, section 166](https://www.parliament.gov.zm/sites/default/files/documents/acts/Act%20No.%2038%20OF%202021%2C%20THE%20INSURANCE%20ACTpdf_0.pdf)
- [SEC licensing statement](https://www.seczambia.org.zm/investor-protection/licensing/list-of-securities-exchange-license/)
- [Betting Control Act](https://www.parliament.gov.zm/node/909)
- [Kalshi Member Agreement](https://kalshi-public-docs.s3.amazonaws.com/kalshi-member-agreement.pdf)

### What a hypothetical expansion calculation means

Under this pilot's assumed historical-mean-plus-20% pricing, $100 of premium would buy
about $569 of 2024 Nov-Mar linear-target payout, or $224 for the Jan-Feb target, on CHIRPS.
Those are the AUTO table's payout/premium ratios multiplied by $100. They are proposed
index payments, not observed quotes, replicated Kalshi fills or estimated farm losses
covered. NASA's replay would not trigger even the linear target in that season.
Changing the data provider can therefore change a positive illustrative payout to zero.

A defensible short paper extension is: public local data makes a geographically local
event-contract design technically possible, but a useful product would still need a
validated settlement source, losses and unmet needs, locally appropriate distribution,
funding, listings and regulatory treatment. The present US Kalshi portfolios cannot
be exported to Zambia unchanged. No alternate region or threshold was searched until
it produced a more attractive drought result.

## Reproduce and sources

Offline from this branch's processed inputs:

```powershell
$env:PYTHONPATH = 'src'
python scripts/run_chipata_pilot.py
```

Refresh only when needed: `scripts/pull_chipata_chirps.py --submit`, followed later by
`--collect`. Provider jobs are public subset requests split at its 20-year limit.

Every result in the AUTO table comes from `maya_chipata_pilot_summary.csv` via
`scripts/run_chipata_pilot.py`; seasonal inputs and all replayed targets are in
`maya_chipata_payout_replay.csv`. Provider metadata and geometry are in
`maya_chipata_source.json`. This pilot is future-work evidence, rather than a new team
direction or a reason to discard the US rainfall studies.
