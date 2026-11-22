# AgriHedge outreach drafts and team handoff

These drafts ask for answers by email. Their goal is to check real needs, loss
assumptions, data availability and market constraints before making product claims.
No messages have been sent. Start with the regional RMA office and local extension;
use the other drafts for specific gaps rather than sending every message at once.

## RMA regional office

Recipient: **rsook@usda.gov**, Oklahoma City Regional Office, serving Texas, Oklahoma
and New Mexico. [Official directory](https://www.rma.usda.gov/rmalocal/oklahoma-city-ok),
checked November 22, 2026.

Subject: Student questions about gaps alongside PRF

Hello,

We're a student team studying whether rainfall event contracts could supplement PRF
for hay producers and ranchers. Our comparisons have found important cost, location
and market-depth limitations, so we're trying to understand where extra coverage
would actually be useful.

Could you help us with two questions by email?

1. Are there recurring drought expenses or timing gaps that producers find PRF does
   not address well, including alongside other available assistance?
2. What outcome or public dataset would you recommend for evaluating supplemental
   cover: replacement-feed expenses, forage production, or something else?

A brief reply or a link to an existing resource would be very helpful for our final
paper. Thank you!

Maya, Evan and Jack

## Parker County agricultural extension

Recipient: **cpmartin@ag.tamu.edu**, Charlie Martin, County Extension Agent for
Agriculture and Natural Resources. This is university extension, not an RMA official.
[Official directory](https://agrilifepeople.tamu.edu/people/view/11991), checked November 22.

Subject: Student questions about drought costs for hay and pasture operations

Hello Mr. Martin,

We're a student team comparing rainfall-based coverage with PRF, using an illustrative
Parker County hay operation among our cases. We would appreciate your perspective
on two assumptions:

1. For pasture operations, is replacement-feed cost a useful starting point for
   valuing drought losses? What important costs would it miss?
2. Are there public local budgets or historical forage/hay data you recommend for
   checking whether our modeled dollar losses are realistic?

We've found that using pasture rent versus feed-replacement value changes our
conclusions substantially. A short email response or resource link would help us
avoid overstating the results. Thank you!

Maya, Evan and Jack

## RMA Product Management

Optional recipient: **deputyadministrator@usda.gov**.
[Official contact page](https://www.rma.usda.gov/about-rma/contact-us), checked November 22.
Use for programme-design criteria; the regional office is the more direct first contact.

Subject: Student question about evaluating supplemental rainfall coverage

Hello,

We're a student team studying supplemental rainfall cover alongside PRF. Our research
compares broad linear payouts with cover that concentrates a fixed premium budget
on severe droughts, while accounting for geographic mismatch and limited trading depth.

What evidence would be most important before taking such a supplemental design
seriously, and is there a public guide to evaluating privately developed index
products or potential gaps in existing coverage? We're seeking feedback for a course
paper, rather than proposing a ready-to-launch product. A brief email reply or
resource link would be greatly appreciated.

Thank you,
Maya, Evan and Jack

## USDA NASS data question

Optional recipient: **nassrfospr@usda.gov**, Southern Plains Regional Field Office,
Texas and Oklahoma. [Official directory](https://www.nass.usda.gov/Statistics_by_State/RFO/),
checked November 22. Ask for published data, not confidential farm records.

Subject: Public historical hay data for a student rainfall-insurance study

Hello,

We're a student team testing rainfall-based insurance designs for hay and pasture
operations. Are county-level historical hay yield and harvested-acreage series
available for Parker or Atascosa County, Texas? If suppression makes those series
incomplete, is there a public regional series or dataset you would recommend instead?

We are trying to validate a rainfall-to-loss model using agricultural outcomes,
rather than rainfall alone. A link or brief guidance by email would be very helpful.

Thank you,
Maya, Evan and Jack

## Kalshi market design and liquidity question

Optional recipient: **auctions@kalshi.com**, the contact on the
[Liquidity Provider Program page](https://kalshi.com/regulatory/liquidity-provider-program),
checked November 22. Ask them to route listing questions; this address is not presented
as the sole market-listing authority. The page's current programme dates are temporary.

Subject: Student questions about seasonal rainfall hedges and liquidity

Hello,

We're a student team researching agricultural hedges built from Kalshi rainfall
contracts. Our prototype already reads public market and order-book data; we are
not placing real orders. Our studies suggest that listing horizon, rainfall thresholds
and available size can prevent seasonal hedge portfolios from being filled.

Could you point us to the right team or answer two questions by email?

1. What determines whether additional rainfall strikes or multiple future months
   can be listed, including possible two-month rainfall contracts?
2. What information would a liquidity provider need to assess demand for these
   hedges, and are there relevant research or liquidity programmes we should read about?

Our goal is to distinguish missing contract designs from missing counterparties in
a course paper. A brief response or resource link would be appreciated. Thank you!

Maya, Evan and Jack

Related official routes: [request strikes](https://help.kalshi.com/en/articles/13823834-request-additional-strikes),
[suggest a market](https://help.kalshi.com/en/articles/13823833-suggesting-a-new-market).
No government grant or Kalshi market-maker admission is assumed in the experiments.

## One message Maya can send the group

Hey! I put the paper checks on `maya-paper-evidence`, based on Jack's PR 12. Please
start at `docs/PAPER_EVIDENCE_GUIDE.md`; it maps the branches, results, formulas and
reproduce commands, and should work as an entry point for your AIs too. Nothing was
merged over your work, and the earlier rainfall/dairy/corn attempts are preserved.

Main findings:

- Fixed PR 12's double-counted taker fee: the old direct-buyer reference is $1.09
  all-in per $1 expected payout; adding the same fee again was incorrect. This does
  not overturn the capital/demand limitations.
- Reconstructed case-specific subsidized PRF curves from policy terms. The ~$5.5
  market-priced linear target in the slides isn't actual subsidized PRF. See doc 30.
- Compared both reallocating an existing budget and keeping all original PRF with
  a 20% extra budget. These answer different questions. The add-on experiment uses
  exactly the frozen Kalshi portfolios, with cash as an alternative use of the extra
  money. No refitting to the evaluation outcomes. See doc 32.
- Found an important loss-value issue: pasture rent is much smaller than the existing
  feed-replacement estimate. Albuquerque has modest tail improvements under the
  replacement-cost proxy, but the HE sign changes under rent valuation. Dallas
  worsens residual variation; San Antonio is mixed. We still cannot claim validated
  farm-income improvement. All six timing/valuation variants and uncertainty checks
  are retained, not just the favorable result.
- Quantified required quantities and missing offers per ticket. Some small winter
  add-ons need modest extra depth in the saved-book proxy; some tail designs lack
  useful offers entirely. These are repeated-November capacity scenarios, not
  executable annual quotes. See doc 33 and the per-leg CSV.
- Zambia already has FISP/R4 index insurance. The Chipata pilot is a hypothetical
  local settlement example, not an available Kalshi product. CHIRPS and NASA disagree
  enough to change the motivating 2024 payout, so we should keep it as a short,
  qualified extension rather than another main pivot. See doc 31.

Evan: the backend already has public Kalshi price/order-book access; a live Dallas
read worked. For app polish, could we show station/distance, months, desired payout,
total cost and actual fillable size together, clearly separating live/saved/estimated
prices and listed/proposed contracts? Explain HE as tracking a stated target, not
farmer-income accuracy. A paper-trade/partial-fill demo is enough; any order prototype
should use Kalshi's separate mock-funded demo. Please confirm the app branch and URL
you are presenting: `exotic-payouts` has newer code than `main`, and the package rename
to `raincheck` needs care when integrating.

Jack: doc 26 has the fee correction; docs 32-33 give extra-cover and capacity audits
that can qualify the intermediary story. Matching wet and dry demand still requires
real customers; current calculations don't establish those customers exist.

For the paper, research track fits best: lead with the final question/findings, then
evidence, comparisons and limitations. Four pages of text excludes figures/references;
appendix text isn't explicitly authorized. Keep pivot history brief. I saved short
email-answerable outreach drafts in `docs/OUTREACH_AND_HANDOFF.md`; nothing has been sent.
The immediate priority is external validation of losses/unmet needs and app clarity,
not another large topic pivot or retuning the already-inspected test years.

## Calculation and source map

| Question | Explanation | Calculation or input |
|---|---|---|
| Correct PR 12 costs? | `analysis/26_intermediary_capital.md` | `scripts/run_intermediary_capital.py`, `intermediary_economics.csv` |
| What is actual PRF per premium? | `analysis/30_matched_premium_drought.md` | `scripts/run_matched_premium.py`, `maya_actual_prf_curves.csv` |
| Same money reallocated? | Doc 30 | `maya_matched_premium_{years,summary,tickets}.csv`, method JSON |
| Keep PRF and spend extra? | `analysis/32_prf_addons_and_loss_audit.md` | `scripts/run_prf_addons.py`, `paper_followup.py`, `maya_prf_addon_*.csv` |
| Why do loss values differ? | Doc 32 and existing doc 13 | `loss_model.py`, `maya_loss_scale_audit.csv`, `maya_addon_loss_variants.csv` |
| How much market depth? | `analysis/33_liquidity_requirements.md` | `maya_liquidity_requirements_{legs,summary}.csv` |
| Zambia data and existing cover? | `analysis/31_chipata_index_feasibility.md` | `scripts/run_chipata_pilot.py`, `maya_chipata_*.csv`, source JSON |
| Unit checks? | `tests/` | `test_paper_evidence.py`, `test_paper_followup.py`, `test_chipata_pilot.py`, intermediary/advisor tests |

Processed filenames in this table live under `data/processed/`; modules live under
`src/agri_hedge/`. This branch retains the merged app rather than silently importing
Evan's separate package rename. Main, open PRs, experimental branches and a deployed
server are different states; the guide records the exact reviewed commits.
