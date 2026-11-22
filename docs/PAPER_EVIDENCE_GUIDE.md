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
7. [Email drafts and one group handoff](OUTREACH_AND_HANDOFF.md): questions that can be
   answered by email, an Evan app request, and a calculation/source map. Nothing was sent.

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
& $py -m pytest
```

All three analyses work offline from committed inputs. The US runs regenerate
summary/year/ticket CSVs, policy curves, loss/capacity audits and their AUTO tables.
The Zambia run regenerates its seasonal replay, summary, and AUTO table. None submits orders. Preserve prose
outside AUTO blocks; use the scripts to change generated tables.

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

## Message Maya can send Evan

Hey! The backend already has public Kalshi market/order-book access, and the live Dallas
read worked. Could we focus the app polish on making the quote understandable? It would
help to show the station and distance, months, desired payout, total modeled/quoted cost,
and how much the book can actually fill, with clear labels for live, saved and estimated
prices. Please separate proposed third-inch/two-month contracts from contracts actually
listed, and explain HE as payout tracking rather than farmer-income protection. A paper
trade/partial-fill demo is enough; if we add order submission, let's use Kalshi's demo
environment. Also, which branch/deployed URL should we treat as the latest app so we
don't overwrite your work?

## Paper framing

Research track is the closest match to current evidence. Four pages of text, excluding
figures and references; lead with findings and link the repo. Keep the pivot history
brief. Catastrophe target-payout concentration is a design tradeoff; the historical
portfolio comparison decides how much of it survives geography, prices and capacity.
Do not claim arbitrage, commercial viability, insured farm-income improvement, or a
legally cleared international product from these experiments.

The supplied rubric images say **four pages of text maximum, excluding figures and
references**. The suggested order is question/main finding, evidence, further comparisons,
then conclusion/limitations/next steps. They do not explicitly authorize extra appendix
text or exempt tables. Ask the TA whether supplementary figure pages may also contain
captions, tables and prose; keep the question, essential methods and core evidence in
the main report. Paper drafting remains paused at Maya's request.

Verification on November 22: **410 tests passed** using the original project venv and
this branch's `src` on `PYTHONPATH`. New accounting, missing-offer, fitting-boundary and
zero-event-pricing checks are in the tests linked by the handoff. No dependencies were
installed. No live order or deployed app was tested by this evidence work.
