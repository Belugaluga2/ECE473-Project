# Team handoff: Maya's research extension

November 8, 2026. Branch: **`maya-experiments`**, proposed into `main` for review.
[Branch comparison](https://github.com/Belugaluga2/ECE473-Project/compare/main...maya-experiments).

Hey Evan and Jack — I worked through these experiments with Codex. This extends our research;
it does not replace the team's existing work or imply that we have agreed on a new final direction.
Jack's dairy pilot is explicitly credited and reused, followed by separate observed-production
validation. The original rainfall results, Companion app, optimizer and Milestone II materials
remain in the branch. The purpose is to make our claims more precise and investigate what a new
insurance instrument could add, without inventing an arbitrage or a positive result.

## Start here

1. [Experiment README](README.md): formulas, coefficient arithmetic, commands, files and limitations.
2. [Offline demo](index.html): open this local file after checking out the branch; no Python,
   installation or network is needed. Keep its sibling `demo.js` and `demo_data.js` files present.
3. [Plain-English project guide](../../docs/MAYA_PROJECT_GUIDE.md): what PRF, companion, dairy,
   hedging, exotic, basis risk and the current model mean.
4. [Doc 28](../../docs/analysis/28_maya_diagnosis_and_demo.md): diagnosis, confirmed mechanics vs
   possible explanations, contract specification, settlement replay and replication audit.
5. [Doc 27](../../docs/analysis/27_compound_county_panel.md): the stronger county-panel evaluation,
   fixed test plan, all results and uncertainty. Docs 25–26 cover the earlier experiments.

In the demo, try **Show a missed-loss case**, compare historical shortfalls/payments, move the
synthetic D/H sliders, read **Why that coefficient?**, and inspect the counterfactual portfolios.
The observed-loss target is a county yield shortfall below a pre-season trend forecast, not an
individual insurance claim. Sliders change the payment, not a crop-loss prediction.

## How this connects to the existing project

**Rainfall / PRF:** replacing subsidized PRF with Kalshi ran into price, geography, payoff-design
and depth limitations. The Companion keeps PRF and explores additional protection for periods
left open by the farmer's selected allocation. That app and its results remain useful. Its strong
rain-index tracking should not be presented as the same thing as demonstrated farm-income protection.

**Dairy:** seasonal heat cover looked promising against a loss formula itself defined using heat.
The next question was whether it protects observed milk-production shortfalls. Our simple regional
validation did not establish improvement. This is a limitation of the tested design/data, not a
proof that heat does not hurt cows or that every dairy policy is impossible. Dairy-RP also includes
regional yield changes; the reused pilot's blanket price/margin-only description is corrected.

**Compound corn cover:** explore a payout based on both heat and drought, with observed county
corn yields as the target. The initial single-county pilot suggested an improvement but depended
strongly on the known disaster year, and its validation-selected station strategy failed later.
We therefore expanded locations, reduced tuning, reserved counties and compared at matched modeled
premiums. These are exploratory extensions, not team-approved replacements for the Companion.

The original topic asks what insurance payoffs event contracts can replicate and what needs new
contracts/mechanisms. Our contract design, static spanning argument and replication gaps fit that
question. We still need to respect the difference between executable orders and hypothetical
seasonal instruments. This complements the listing-horizon issue explored in the pending proposal;
we have not independently reproduced every result or novelty claim in that proposal.

## The actual model and why the coefficient has that value

`D` is clipped drought severity from June–July rainfall; `H` is clipped June–July heat severity.
The heat index uses daily Tmin and Tmax to approximate time-and-temperature exposure above a fixed
threshold. Both are calibrated to earlier county weather. The selected rule is:

```text
payment = expected crop value × a × min(D,H)
a = modeled premium / ((1 + loading) × mean_training(min(D,H)))
```

The coefficient is contract size forced by the price budget once this one-feature shape is fixed.
It is not a causal biological effect. Multi-feature alternatives fit nonnegative weights using
centered-error regression plus ridge under the same expected-payout budget and payment cap.
Earlier validation chooses the family/penalty; final results do not select a replacement winner.

| Fixed quantity | Value | Source |
| --- | --- | --- |
| Coefficient a | 0.10700902149239477 | `maya_coefficient_audit.json` |
| Mean training min(D,H) | 0.08495460442608747 | same audit |
| Modeled premium / load | 1% expected crop value / 10% | chosen assumptions, same audit |
| Maximum selected payment | 10.700902149239477% of expected crop value | `maya_contract_specs.json` |
| Calibration / final evaluation | fit through 2009; planned final period 2010–2024 | doc 27 protocol / `panel_models.json` |
| County panel | 12 counties in IL/IA/IN; 9 development and 3 held out | `panel_counties.csv` |
| Final complete common sample | 11 years; 33 held-out county-years | `panel_models.json`, `panel_cohort_audit.csv` |

## Results: encouraging point estimates, insufficient confirmation

The table below describes the **selected** matched-price policy, not whichever family had the
best final score. HE is variance reduction, not profit or the fraction of losses reimbursed.
Net error skill is reduction in squared signed loss-minus-payment-plus-premium error versus no hedge.

| Result | Value | Source |
| --- | --- | --- |
| Held-out county HE | 0.248 | `panel_summary.csv`, primary weakest-link/all years |
| Held-out net error skill | 0.154 | same row |
| Conditional net-skill interval | approximately [-0.126, 0.317] | same row; whole-year bootstrap |
| Share of observed shortfalls matched by payouts | approximately 11.5% | same row, recovery metric |
| Without 2012: HE / net error skill | 0.047 / -0.058 | primary weakest-link/without-2012 row |
| Mixed minus additive net skill | 0.0546; interval approximately [-0.0442, 0.1125] | `panel_incremental.csv`, held-out primary/all |
| Held-out counties where mixed beats additive | 2 of 3 | `panel_models.json`, evidence checks |
| Interaction evidence checks | failed | same evidence object |

Missing yields reduce the complete shared cohort; there is no imputation or replacement of
counties to improve the scores. Counties in the same year share weather shocks, so the uncertainty
calculation resamples whole years. Intervals condition on fitted models and omit selection/serial
uncertainty. The final data are now inspected; further changes need a separate confirmation sample.

## What the missed-loss diagnosis found

Confirmed payment mechanics, separate from causal hypotheses:

- **Limited payment size:** the severe disaster cases activate protection, but the premium budget
  buys partial cover. Increasing this shape's coefficient raises its modeled cost proportionally.
- **Missing triggers:** other yield shortfalls happen when either D or H is zero, so the joint
  rule correctly settles at zero while failing to protect that crop shortfall.
- **Wrong peril/season candidates:** the diagnosed wet-summer and late-season cases suggest
  exposure design matters. The separate W benchmark measures April–May rain, not wet summer soil.
- **Forecast sensitivity:** all ranked large misses remain shortfalls under every fixed production
  forecast sensitivity, though magnitudes change. None is established as a farmer's true expectation.
- **Wind is absent:** the documented Iowa derecho is relevant context for Story's loss year, but
  we cannot attribute a measured share of county loss to wind versus drought/other causes.

Doc 28 links the official weather/crop reports and labels plausible explanations explicitly.
It does not invent a causal account for cases where the available evidence cannot establish one.

## What is implemented versus hypothetical

Implemented: reproducible analyses, committed public inputs and provenance, fixed contract specs,
strict daily-data settlement replay, coefficient audit, constrained replication diagnostics and
an isolated interactive demo. The settlement replay checks missing/duplicate/invalid observations,
rounds cents, reports required mock collateral and hashes inputs. No collateral is actually held;
hashes do not attest that an oracle tells the truth.

The checked open Chicago listings do not supply the required pre-season summer portfolio.
November prices/depth cannot be used as actual summer quotes. The comparison baskets are explicitly
counterfactual: some primitives are synthetic, summer listing availability is assumed, and costs
use earlier average payouts plus a loading. No verified fees, integer fills or liquidity execution.
Daily-high contracts also omit Tmin, which our heat-duration index needs. Exact static separate
payoffs have a mathematical gap for the min rule over the full severity domain; approximate fit
on observed weather can still be useful. Neither good replication nor a working UI proves farm benefit.

This is **not a dApp or testnet deployment**. A fixed-rule escrow/oracle demonstration could be a
later course component if needed; it does not resolve the economic or data questions.

## How this combines with everyone's branches

At publication review, current `main` includes merged [PR 3](https://github.com/Belugaluga2/ECE473-Project/pull/3).
Our branch descends from that merge. The existing `platform.py`, `webapp/`, PRF calculator,
optimizer, hedge builder, app entry point, Milestone II write-up and original demo guide are
unchanged relative to current `main`. Shared documentation gets new links/status notes; package
metadata gains only optional dairy data-pull dependencies. Original results remain available.

The additional pending work is distinct:

- [PR 4](https://github.com/Belugaluga2/ECE473-Project/pull/4): per-farmer comparison and `/compare`
  page, based on `main`. Those app features are not included here, but our app files do not edit
  them. A read-only three-way preview flags the shared `docs/00_OVERVIEW.md` for reconciliation.
- [PR 5](https://github.com/Belugaluga2/ECE473-Project/pull/5): dairy pilot stacked on PR 4. We
  selectively reused its computation files, not its whole parent stack. Preview flags the index,
  dairy document, dairy module and generated summary. The module's executable AST matches PR 5
  after excluding the corrected explanatory docstring. Summary differences are floating-point
  regeneration only; keep the government-coverage correction when resolving documentation.
- [PR 6](https://github.com/Belugaluga2/ECE473-Project/pull/6): listing-horizon proposal stacked on
  PR 5. It remains a separate candidate; preview inherits the same dairy/index overlaps.

These previews did not merge or modify anyone's branch. They are integration guidance, not a
guarantee that later branch updates remain conflict-free. If the stack merges first, reconcile
the shared docs and duplicate dairy files while retaining both experiments and corrected claims,
then rerun the tests. Do not discard the comparison app or replace the team direction implicitly.

## Run/reproduce

To obtain the branch: `git fetch origin`, then `git switch --track origin/maya-experiments` if it
is not already local (otherwise `git switch maya-experiments`). Use a separate checkout if your
current working tree contains work you want to keep in place.

Open `experiments/maya/index.html` locally for the dependency-free demo, or on Windows:

```powershell
& .\.venv\Scripts\python.exe scripts\run_maya_demo.py
# http://127.0.0.1:8474/

& .\.venv\Scripts\python.exe scripts\run_maya_diagnostics.py
& .\.venv\Scripts\python.exe scripts\run_compound_panel.py
& .\.venv\Scripts\python.exe scripts\run_dairy_validation.py
& .\.venv\Scripts\python.exe scripts\run_maya_demo.py --settle --county 19169 --year 2013 --value 100000
& .\.venv\Scripts\python.exe -m pytest -q
```

On macOS/Linux substitute `.venv/bin/python` for the Windows executable/call operator. A fresh
checkout needs the project environment for Python commands; the standalone HTML needs none.
Committed inputs suffice for the analyses above. Source-pull scripts need internet and are
separate from reproduction. The original app remains `scripts/run_app.py` with its existing
`?demo` example. The README explains inputs, outputs and all formula files.

| Validation / integration fact | Result | Evidence |
| --- | --- | --- |
| Python suite | 420 passed | full pytest run on the published code before handoff-only edits |
| Diagnostic reproducibility | 19 artifact hashes matched | repeated `run_maya_diagnostics.py` check |
| Browser verification | desktop and narrow-layout interactions passed, HTTP and local file | isolated Chrome checks, selectors/sliders/invalid inputs/receipt calculations |
| Original main base | `dd0c464`, PR 3 merged November 6 | Git ancestry and GitHub PR metadata |
| Dairy source code overlap | executable AST identical; explanatory docstring differs | read-only PR 5 comparison |
| Dairy generated summary overlap | maximum absolute difference about 1.33e-15 | numeric comparison; allclose check |

## Useful questions before more work

- Do we keep the Companion as the main tool and use this as a contract-design/limitations chapter?
- Should PR 6's listing-horizon framing organize the final paper, with these measured-loss and
  joint-payoff findings as supporting experiments?
- What does the TA actually expect for a blockchain component: tool, mock settlement or testnet?
- Can anyone supply a better-defined insured-loss target, farm-level data or crop-stage/soil
  measurements? More threshold searches on the already-seen sample are not the next priority.

My recommendation is to review this before another wholesale pivot: we have a working demonstration
and useful evidence about why designs fail, but no confirmed arbitrage, commercial advantage or
reliable superiority of an exotic policy. Preserve the research attempts and agree on one coherent
paper/tool narrative before adding more formulas.
