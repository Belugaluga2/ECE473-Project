# Paper evidence: start here

This guide belongs to **`maya-paper-evidence`**, based on Jack's PR 12 (`492c274`).
It adds a fee correction, matched-budget and PRF-kept comparisons, a loss audit,
capacity requirements and a small Zambia index pilot. It preserves the companion app
and all earlier research. This is a separate review branch, not an agreed new direction.

## Read in this order

1. [PRF-kept add-ons and loss audit](analysis/32_prf_addons_and_loss_audit.md): why
   extra spending differs from reallocation, six loss sensitivities, and conditional results.
2. [Liquidity requirements](analysis/33_liquidity_requirements.md): required contracts,
   missing offers and depth multipliers for the same frozen add-ons.
3. [Matched-premium drought study](analysis/30_matched_premium_drought.md): definitions,
   formulas, actual PRF curves and the original budget-reallocation experiment.
4. [Intermediary model](analysis/26_intermediary_capital.md): corrected once-only fees.
5. [Chipata pilot](analysis/31_chipata_index_feasibility.md): local public rainfall data
   outside DRIVE's countries. It demonstrates feasibility, not improved farmer protection.
6. [Earlier contract-design study](analysis/24_contract_design.md): why equal premium and
   equal maximum payout answer different questions.
7. [Outreach drafts and calculation sources](OUTREACH_AND_HANDOFF.md): research
   questions that can be answered by email and a map from claims to calculations.

The fixed-budget US replay did **not** establish better worst-loss protection than
subsidized PRF in its three fixed cases. It finds isolated higher gross payouts, while the
target curves show the catastrophe tradeoff more clearly than the airport portfolios.
Keeping all PRF and buying extra cover produces modest conditional Albuquerque
improvements under the existing feed-replacement loss proxy. The HE sign changes under
rent valuation; Dallas worsens residual variation and San Antonio is mixed. Extra cover
costs extra money, and these are not validated farm-income results.
The Zambia pilot establishes data/settlement feasibility and exposes product and
window sensitivity; it does not establish farmer benefit or a new commercial market.

HE means **hedge effectiveness**: `1-Var(target-payout)/Var(target)`. It measures remaining
variation, not percentage accuracy or profit. Always say what the target is. A portfolio
may track PRF while failing to track real crop losses. Constant bias is invisible to HE.

## Run without installing or changing the original checkout

From this worktree, use the interpreter in Maya's original checkout:

```powershell
$py = 'C:\Users\mayad\Downloads\COS-470-Final-Project\.venv\Scripts\python.exe'
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
& $py scripts/run_matched_premium.py
& $py scripts/run_prf_addons.py
& $py scripts/run_chipata_pilot.py
& $py scripts/inspect_paper_results.py
& $py -m pytest
```

All three analyses work offline from committed inputs. The US runs regenerate
summary/year/ticket CSVs, policy curves, loss/capacity audits and their AUTO tables.
The Zambia run regenerates its seasonal replay, summary, and AUTO table. None submits orders. Preserve prose
outside AUTO blocks; use the scripts to change generated tables.

The optional inspection command fits nothing: it joins the frozen matched-budget
portfolios to all six loss sensitivities and writes `maya_matched_loss_audit.csv`.
Doc 32 gives retrospective Albuquerque 2009/2018 examples of higher/lower payouts,
and balances them against the full-family worst-loss results. It distinguishes an
individual existing-strike win from proposed-market results and overall protection.

The first new US analysis used the inherited exponential shape. The later family audit
adds the prior deck's disaster-only and binary designs after that first run, retaining
all results. These data were already inspected; no fresh-confirmation claim is made.

## Which branch contains what?

| Branch / commit at review | Purpose | Integration note |
|---|---|---|
| `main` / `a62f8dd` | Merged companion and contract designer, through PR 10 | Shared baseline |
| `research/expansion-options` / `ce2a5ee` | Jack's PR 11, expansion research | Open PR |
| `research/intermediary-capital` / `492c274` | Jack's PR 12, capital model | Stacked on PR 11 |
| `maya-paper-evidence` | This fee correction, add-on/loss/capacity audits and Zambia pilot | Separate review branch; based on PR 12 |
| `exotic-payouts` / `d530848` | Evan's newer app code and income study | Renames package to `raincheck`; not merged |
| `milestone-1` / `4f786c0` | Third-inch and row-crop studies behind the final slides | Different scripts/data from similarly named main files |
| `maya-experiments` / `34410e9` | Maya's dairy/corn validation and offline demo | Preserved in the original checkout |

Document numbers collide across branches. For a paper citation or handoff, include the
descriptive filename and commit. Merge or selectively integrate changes with tests;
do not overwrite another branch's `run_exotic_payouts.py` because its name matches.
No branch, experimental result, or teammate file was deleted or renumbered in this work.

## Continue on another computer

The Windows interpreter path above is specific to Maya's current machine. On another
computer, use that machine's project environment and the README's dependency setup;
the virtual environment itself is not transferred by Git. For a separate fresh checkout:

```text
git clone --branch maya-paper-evidence https://github.com/Belugaluga2/ECE473-Project.git ECE473-paper-evidence
cd ECE473-paper-evidence
```

Set `PYTHONPATH` to this checkout's `src` and run the three analysis commands above
using the local Python environment. They need no Kalshi credentials or data download.
Read AGENTS.md before edits and preserve the previously inspected evaluation results.

On November 22, all three scripts ran from an export of commit `8673ad7`, containing
only committed files and no local raw caches. Ten key result CSVs matched the committed
outputs within floating-point tolerance: the four matched-budget/curve CSVs; add-on
years and summary; loss-scale audit; liquidity summary; Chipata replay and summary.
This verifies data portability with the existing environment, not installation on a
second operating system. Older generated slide drafts in the original checkout's
untracked `output/` are separate local artifacts, not part of this research branch.

## Files available from GitHub

| Material | Location or transfer requirement |
|---|---|
| Current evidence documents and calculations | This branch, `docs/analysis/30` through `33`, `scripts/`, `src/agri_hedge/` |
| New PRF comparison figure | This branch, `docs/figures/maya_actual_prf_curves.png` and `.pdf` |
| New analysis inputs and result tables | This branch, `data/processed/maya_*`; enough for the offline evidence runs |
| Earlier dairy/corn experiments | Remote `maya-experiments`, commit `34410e9`; fetch that branch separately |
| Original course PDFs, uploaded decks and screenshots | Separate source files outside the repository; transfer privately if needed |
| Older generated slide drafts and review notes | Local `output/`; transfer separately if needed |
| Raw download caches and temporary review exports | Gitignored; not needed for the current evidence runs |
| Python environment | Local `.venv`; use the new computer's environment and README setup |

Some earlier data-download pipelines may need their own raw inputs or a fresh download;
the offline reproduction check above applies to the three named evidence analyses.

## What the app does, and API status

This branch retains the merged app: custom portfolio quotes, PRF companion, exotic
payoff design, equal-premium comparison, and the advisor (rules fallback or optional
model integration). The pricing backend already reads public Kalshi markets/order books,
falling back to snapshots or modeled prices. There is no order-submission path here.

On 2026-11-21 a separate check using Evan's `d530848` app code returned seven **live**
Dallas November books. Thin books do not stop API access; they limit fills. No server
was listening on local port 8473 when checked. This does not identify what version
someone else might have deployed or loaded in a remote browser.

For a proof of concept, show real read-only quotes and a simulated, partially filled
ticket. If actual order plumbing is needed, use Kalshi's mock-funded demo environment
with separate credentials, not blockchain testnet assumptions. Demo market prices and
behavior do not validate production liquidity.

Official references:
- [Public market data](https://docs.kalshi.com/getting_started/quick_start_market_data)
- [Mock-funded demo](https://docs.kalshi.com/getting_started/demo_env)

## Quote display requirements

A quote should identify its station and distance, covered months, desired payout,
total cost and fillable quantity. Distinguish live, saved and estimated prices, and
listed contracts from proposed instruments. Define HE against the stated target;
it is not measured farm-income accuracy. The deployed branch and commit should be
visible so a demonstration can be reproduced.

## Paper framing

Research track is the closest match to current evidence. Four pages of text, excluding
figures and references; lead with findings and link the repo. Keep the pivot history
brief. Catastrophe target-payout concentration is a design tradeoff; the historical
portfolio comparison decides how much of it survives geography, prices and capacity.
Do not claim arbitrage, commercial viability, insured farm-income improvement, or a
legally cleared international product from these experiments.

The course rubric specifies **four pages of text maximum, excluding figures and
references**. The suggested order is question/main finding, evidence, further comparisons,
then conclusion/limitations/next steps. They do not explicitly authorize extra appendix
text or exempt tables. Ask the TA whether supplementary figure pages may also contain
captions, tables and prose; keep the question, essential methods and core evidence in
the main report.

Verification on November 22: **410 tests passed** using the original project venv and
this branch's `src` on `PYTHONPATH`. New accounting, missing-offer, fitting-boundary and
zero-event-pricing checks are in `tests/`. No dependencies were
installed. No live order or deployed app was tested by this evidence work.
