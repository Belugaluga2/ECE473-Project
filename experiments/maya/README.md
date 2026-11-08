# Maya's experiments — start here

This folder is the entry point for the work on **`maya-experiments`**. It preserves the original
rainfall/PRF work and the dairy attempt. The new work asks whether proposed weather payments
can offset crop shortfalls and whether separate event contracts could reproduce those payments.
**No arbitrage, production insurance offer, actual trade or blockchain deployment is established.**

## Open the demo

You can double-click [index.html](index.html): its committed data and scripts work offline, with
no Python or installation needed. Alternatively, from the repository root in PowerShell:

```powershell
& .\.venv\Scripts\python.exe scripts\run_maya_demo.py
```

Open **http://127.0.0.1:8474/**. Ctrl+C stops the server. Use this workspace's existing `.venv`.
The server serves only this demonstration folder, binds localhost and makes no market requests.
The existing PRF Companion remains separate:

```powershell
& .\.venv\Scripts\python.exe scripts\run_app.py --port 8473
```

Its example is **http://127.0.0.1:8473/?demo**. We did not change that app. It may check live prices
and otherwise uses its existing snapshot/estimated-price behavior.

## What to try in the new demo

- Explore a historical county/year: compare the estimated crop shortfall with the fixed payment.
- Click **Show a missed-loss case**. Read why the formula pays little; context clues are not
  proven causes of crop damage.
- Move the hypothetical drought/heat sliders. They change a proposed payment, not predicted yield.
- Read **Why that coefficient?** and expand the evidence explanation. Positive point estimates remain
  uncertain and strongly disaster-dependent.
- Compare proposed payment vs counterfactual separate-contract baskets. The summer listings and
  some primitives are invented scenarios; the dated availability check is displayed separately.
- Download an illustrative receipt, or use the stricter CLI daily-data replay below.

## The mathematical model

The target shortfall is `L = max(0, 1 - observed yield / earlier-only expected yield)`.
The original expected-yield forecast is a linear trend over earlier available observations.
It is not an actual farmer claim or a causal heat-damage estimate.

Earlier county weather defines clipped severity scores:

```text
D = clip((rain trigger - June–July rain) / rain scale, 0, 1)
H = clip((June–July heat exposure - heat trigger) / heat scale, 0, 1)
W = clip((April–May rain - wet trigger) / wet scale, 0, 1)

Selected payment = E × a × min(D,H)
Mixed alternative = E × (wD×D + wH×H + wW×W + wDH×D×H)
```

`E` is declared expected crop value. `min` takes the smaller severity, so both inputs must be
positive. Heat exposure approximates time spent above the heat threshold using each day's
minimum and maximum temperature. Season-total heat and dryness need not occur on the same day.

### Why these coefficients?

For the selected one-feature rule, let `Z=min(D,H)`. Its equal-price constraint is:

```text
premium = (1 + loading) × mean_training(a × Z)
a = premium / ((1 + loading) × mean_training(Z))
```

Thus the coefficient is **determined by the price budget once the shape and triggers are fixed**.
It is a contract-size parameter, not a biological estimate. The audit JSON below gives the exact
mean and arithmetic. The family was chosen using earlier temporal validation, not the final scores.

For multi-feature models, the fit minimizes centered payment error plus a ridge penalty:

```text
mean(((L - mean(L)) - (Xw - mean(Xw)))²) + lambda × sum(w²)
```

Weights are nonnegative, their sum is capped, and the primary comparison matches the training
expected-payout budget. Ridge discourages unstable allocations. The penalty is selected using
earlier validation years. This is not proof of a globally optimal contract or of no overfitting.

### Frozen numbers and defaults

| Quantity | Value | Source |
| --- | --- | --- |
| Selected coefficient a | 0.10700902149239477 | `data/processed/maya_coefficient_audit.json` |
| Mean training min(D,H) | 0.08495460442608747 | same audit, recomputed from frozen transforms |
| Modeled premium / load | 1% expected crop value / 10% | same audit; chosen experimental assumptions |
| Maximum selected payment | 10.700902149239477% expected crop value | `maya_contract_specs.json`; one-feature maximum |
| General fitting cap | 30% expected production | `compound_panel.py`, `LIMIT` |
| Training sample | 1980–2009, 270 development county-years | `panel_models.json` / coefficient audit |
| Expected-yield baseline | Previous 20 available yields, minimum 15 | `compound.preseason_yields` |
| Covered season | June–July; 61 complete daily observations | `maya_contract_specs.json` |
| Triggers / scales | D and H: earlier medians; W: earlier 75th percentile; scales: 90th–10th ranges; severities clipped to [0,1] | `panel_models.json`, `compound_panel.fit_model` |
| Heat threshold | 29°C | fixed prior-literature-motivated proxy, docs 26–27 |
| Browser/CLI default crop value | $100,000, illustrative | `index.html`, `run_maya_demo.py` |
| New demo / existing app ports | 8474 / 8473 | respective entry scripts |

## What we learned

- The original replacement of subsidized PRF faced price, basis and liquidity problems. The
  Companion keeps PRF and explores additional periods; rain-index tracking is not farm-income proof.
- Dairy's observed-milk validation did not establish protection, despite encouraging weather-based
  simulation. It remains a documented attempt.
- The compound corn study has encouraging but uncertain point estimates. Its interaction checks
  fail, and removing the major disaster year weakens the evidence substantially.
- Diagnosis identifies missing triggers, insufficient payment size and omitted peril/time-window
  candidates. Alternative production forecasts change magnitudes but do not erase the largest misses.
- A correct settlement calculation does not make the cover economically useful. A close replica
  of that payment would not automatically protect crop losses either.
- No checked pre-season summer portfolio is currently demonstrated. Counterfactual baskets and
  modeled costs are explicitly labeled. Some portfolio design gaps have mathematical explanations.

## Commands for results and settlement

From the repository root; these analysis/replay commands use committed inputs and no internet:

```powershell
# New missed-loss diagnosis, coefficient audit, replication tables and demo data
& .\.venv\Scripts\python.exe scripts\run_maya_diagnostics.py

# Broader county study: original fitting, temporal validation and reserved-county results
& .\.venv\Scripts\python.exe scripts\run_compound_panel.py

# Earlier single-county experiment
& .\.venv\Scripts\python.exe scripts\run_compound.py

# Earlier observed-milk validation
& .\.venv\Scripts\python.exe scripts\run_dairy_validation.py

# Settlement replay: actual committed daily observations, cents, hashes and mock collateral
& .\.venv\Scripts\python.exe scripts\run_maya_demo.py --settle --county 19169 --year 2013 --value 100000
& .\.venv\Scripts\python.exe scripts\run_maya_demo.py --list

# Whole repository tests, or just these diagnostics
& .\.venv\Scripts\python.exe -m pytest -q
& .\.venv\Scripts\python.exe -m pytest tests\test_maya_diagnostics.py -q
```

Analysis scripts regenerate their own result files/AUTO tables. No command above submits an order,
deploys anything or changes a branch. To explicitly refresh the **new** public listing snapshot
and August context, use `scripts/pull_maya_diagnostic_inputs.py`; that command needs internet and
changes the dated snapshot. It preserves the old market snapshots. Regenerate diagnostics afterward.

## Read these files in this order

| File | Why read it? |
| --- | --- |
| [Beginner project guide](../../docs/MAYA_PROJECT_GUIDE.md) | PRF, companion, dairy, exotic, hedge, arbitrage and model definitions |
| [New diagnosis and contract audit](../../docs/analysis/28_maya_diagnosis_and_demo.md) | Confirmed mechanics, plausible explanations, unknowns, market gap and sourced numbers |
| [Multi-county study](../../docs/analysis/27_compound_county_panel.md) | Fixed plan, scores, uncertainty, every model and failed evidence checks |
| [Formula/fitting code](../../src/agri_hedge/compound_panel.py) | Feature transforms, constraints, regression and selection |
| [Daily heat/baseline math](../../src/agri_hedge/compound.py) | Analytic within-day heat integral and earlier-only yield forecasts |
| [Settlement code](../../src/agri_hedge/maya_contract.py) | Frozen specification, complete-data validation, hashes and cents rounding |
| [Diagnostic/replication code](../../src/agri_hedge/maya_diagnostics.py) | Fixed baseline sensitivities and long-only static portfolio fitting |

Raw results are in `data/processed/`: `panel_models.json` has all fitted coefficients, climate
normalizers and selected models; `panel_cv.csv` has every earlier validation score.
`maya_case_diagnosis.csv` contains every inspected case; `maya_top_misses.csv` is the ranked subset.
`maya_coefficient_audit.json`, `maya_contract_specs.json`, `maya_settlement_replays.json`,
`maya_replication_summary.csv` and `maya_replica_models.json` hold the detailed new evidence.

The scripts remain outside this folder to follow the repository's existing package/data conventions.
The demo has no external libraries or network calls. It is not a dApp. If the course requires
blockchain, this specification/replay can inform an escrow-and-oracle testnet demonstration, with
explicit decisions still needed about source revisions, disputes, capital and counterparties.
