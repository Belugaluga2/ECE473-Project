# ECE473 AgriHedge contribution guide

Read this first, then [docs/00_OVERVIEW.md](docs/00_OVERVIEW.md) (index of every doc, headline numbers, next steps).

**Paper evidence branch (2026-11-22):** `maya-paper-evidence` is based on PR 12 (`492c274`),
in a separate worktree. Read [docs/PAPER_EVIDENCE_GUIDE.md](docs/PAPER_EVIDENCE_GUIDE.md).
It fixes double-counted taker fees, adds exploratory matched-premium diagnostics (doc 30)
and a Chipata rainfall-index feasibility pilot (doc 31). Docs 32-33 keep original PRF
with an extra 20% budget, audit six loss timing/valuation assumptions, and quantify
per-ticket capacity needs. `scripts/run_prf_addons.py` reuses frozen doc-30 tickets
offline; do not refit to the already-inspected replay. Read the loss-value and saved-book
limitations before quoting results. `docs/OUTREACH_AND_HANDOFF.md` contains outreach
drafts and a calculation map. Preserve the original Maya
branch and all teammate work. Evaluation years were already inspected; do not retune
or describe them as new confirmation. No app/order/insurance business was deployed.
Use the original checkout's `.venv/Scripts/python.exe` with this worktree's `src` on
`PYTHONPATH`; no installation is needed.

**Direct-risk experiment (doc 34):** `scripts/run_direct_tail.py` runs offline from
committed inputs. Protocol `data/scenarios/maya_direct_protocol.json` was committed
before outputs as `bb50e11`. It compares direct CVaR quantities with a declared
trigger/power family, selecting on 1986-2000 after fitting 1951-1985, then refitting
pre-2001 and replaying 2001-2025. Results are now inspected; do not retune on them.
All candidates and six loss sensitivities are retained. Albuquerque's unlimited-depth
add-on has a modest point-estimate gain; saved-depth and price stresses weaken it,
and primary selected add-on CVaR intervals include zero. No observed farm-income validation or
seasonal market availability is established. Read doc 34 before citing the figures.

## What the project is now (2026-11-13)

ECE473 team project (Maya, Evan, Jack). It started as "replicate USDA rainfall insurance (PRF) with Kalshi monthly-rain contracts". That failed: Kalshi costs about 1.8x subsidized PRF, airport gauges sit 30-55 miles from the farm, and order books are thin (docs 08-09, 16).

**Current direction: the PRF Companion and drought-weighted contract design.** Keep PRF, and use Kalshi contracts for months the sample farmers did not select (mostly Nov-Feb), where airport rain tracks their farm grids better. The companion's holdout HE is 0.61 versus 0.23 for copying selected PRF intervals; the app recommends it for 9 of 11 farms (doc 21). These are rain-index payout fits, not demonstrated farm-income protection. Order-book liquidity limits size: 5-10x the saved depth would be needed to restore the uncapped fit (doc 22). The newer design study asks which payout shape a modeled risk-averse farmer would prefer (docs 23-24).

**Added 2026-11-08: exotic payoffs (doc 23).** Nine payout shapes, a replicating NO/YES portfolio, a saved-book execution check, and `platform.exotic_quote` / `POST /api/exotic` (term sheet + ticket + farmer basis risk). A fully filled portfolio reproduces a station-settled payout on Kalshi's strike bins; it does not remove station-to-farm basis risk. Doc 23's apparent convex-shape depth advantage compares equal maximum payouts. Doc 24 shows that advantage disappears at equal premium.

**Added 2026-11-19: expansion research (doc 25).** Bridge insurance abroad fails (Kalshi country restrictions, no local stations, tiny tickets); pairing opposite weather hedgers mostly buys ordinary diversification and its worst-year benefit only exists on an insurer's own book. Second pass (2026-11-20) reversed the ranking. Lenders show no drought losses to hedge, so they are distributors. Kalshi already nets same-event collateral (`DIRECNET`). A 17-strategy head-to-head finds no clear winner: a loose pack led by 508(h), structuring software and a snow Companion; own-book pairings rank #10 or lower. Recommended combination: fix the menu, sell the engine, seed the book. Three independent logic reviews are in `docs/research/expansion_notes/logic_review_*.md`. Non-farm demand is unmeasured.

**Added 2026-11-20: intermediaries (doc 26), corrected 2026-11-21.** Balanced hypothetical wet and dry flow at the same station-months cuts modeled capital about 60%; the low-wet-demand 1:80 scenario saves little, but it is not measured flow. A fronted insurer/MGA adds about 33% of premium (hedger pays 1.49-1.59 per $1 expected payout). The direct-Kalshi reference is 1.09, already including taker fees; it must not be charged a fee again. A lean carrier and our own Kalshi maker break even near a 14% seller load on the ranch book. Priced on 1951-1995, south-central books lose money in 1996-2025 under the stated cost/price scenarios. These are model results, not operating businesses.

**Added 2026-11-09: contract design and the advisor (doc 24).** At equal premium, convex shapes beat linear in 0 of 36 insured windows at the saved book's depth. Under a modeled farmer with risk aversion 2, wealth twice the month's insured value and a 20% price load, smooth exponential and quadratic shapes capture 93% and 90% of the utility-optimal contract's modeled value, versus 67% for linear. The raw optimum overfits; these are modeled utility results, not observed income gains. The app has a contract designer and advisor. The rule-based advisor runs in the demo; the Claude path has scripted-client tests but no live API test yet.

## Deadlines

| Date | Deliverable | Where |
|---|---|---|
| 2026-11-12 | Milestone II write-up and update | `docs/milestone2/milestone2.tex` / `.pdf`, `milestone2_update.tex` / `.pdf` |
| 2026-11-16 11:59pm | Slides due | Deck linked from [docs/DEMO.md](docs/DEMO.md) |
| From 2026-11-17 | Presentations | 10-minute talk plus 5-minute Q&A |
| 2026-12-15 | Final paper | not started; roadmap in DEMO.md |

## Where things are

- `docs/DEMO.md`: demo guide, presentation links, roadmap, and key numbers to quote.
- `docs/MILESTONE_2.md`: Milestone II summary table and reproduce commands with run times.
- `docs/research/` (sourced background, docs 01-10), `docs/analysis/` (our results, docs 04b-24, numbered in the order they were done).
- `archive/`: alternative-topic research kept for provenance, outside the current TA reading path.
- `src/agri_hedge/`: the package. The app's single entry point is `platform.quote` (custom hedge) and `platform.companion` (PRF Companion). Fitting is in `optimizer.py` + `hedge_builder.py`.
- `scripts/run_*.py` regenerate each analysis doc's numbers, CSVs and figures. `scripts/pull_*.py` download raw data into `data/raw/` (gitignored, currently empty; committed `data/processed/` is enough for tests, the app and the Milestone 2 scripts).
- `scripts/experiments/`: two one-off experiments cited in doc 21's numbers table. Keep them.
- `src/agri_hedge/exotic.py` + `scripts/run_exotic_payouts.py`: exotic payoff shapes and their replication (doc 23). The full run takes about 30 minutes; `--tables-only` redoes figures and doc tables from the saved CSVs, `--quick` runs two farms, `--only=months,execution` recomputes named parts.
- `src/agri_hedge/design.py` + `scripts/run_exotic_design.py`: equal-premium comparison, holdout term sheet, utility-optimal payout (doc 24; about 5 minutes, same flags). `src/agri_hedge/advisor.py`: the prompt-driven designer (crop table, geocoders, tool schemas, system prompt, rule-based fallback). The app's exotic entry points are `platform.exotic_quote`, `platform.exotic_compare` and `advisor.advise`.
- `scripts/run_expansion_netting.py`: counterparty-netting backtest for the multi-sector market-maker idea (doc 25; downloads NOAA ACIS daily data into `data/raw/stations/acis_expansion/` on first run, about 2.5 minutes; `--offline` about 45 s). Research notes and the four gap reviews are in `docs/research/expansion_notes/`; the reviews' checks are in `scripts/experiments/expansion_review/`.
- `scripts/run_expansion_lenses.py` (about 130 s; caches NASA POWER in `data/raw/nasa_power/`, `--offline`): lender-book HE, ENSO in Kalshi prices, solar. `scripts/run_expansion_compare.py` (about 1 s): head-to-head of the strategies scored in `data/processed/expansion_strategy_scores.csv`. Edit the scores CSV, not the script; it rewrites doc 25's AUTO block.
- `scripts/run_intermediary_capital.py` (about 10 s, committed data only): doc 26, the two-way market's middle seat. Capital, capital cost, break-even load and 1996-2025 gains and losses for a Kalshi maker, a lean carrier and a fronted insurer/MGA; cost inputs are constants at the top of the script, sourced in doc 26's numbers table. Rewrites doc 26's AUTO block.
- Demand from losses (doc 25 "Demand estimate" section): `scripts/run_rain_reservations.py` (OpenTable seated diners vs rain), `scripts/run_rain_venues.py` (Retrosheet MLB attendance vs rain, Divvy), `scripts/run_weather_demand.py` (loss-based demand by segment; about 5 s). The live OpenTable file `data/raw/opentable/opentable_soti_20261119.json` was saved by hand from the dashboard's data endpoint (opentable.com/c/wapi/r9-ot-soti/v1/data, which blocks scripted downloads); data/raw is gitignored, so teammates rerunning the reservations script need to save that file themselves. The committed `data/processed/rain_reservations_*.csv` are enough for the demand script.

## Run it

```bash
.venv/bin/python -m pytest              # 420 passed on paper-evidence branch, 2026-11-22
.venv/bin/python scripts/run_app.py     # http://localhost:8473/?demo  (PRF Companion, Dallas hay farm); ?demo=exotic, ?demo=advisor
```

On Windows the venv's interpreter is `.venv\Scripts\python.exe` (create it with `python -m venv .venv` and `.venv\Scripts\python.exe -m pip install -e .`).

The advisor uses Claude (`claude-opus-5-5`, Anthropic SDK) when `ANTHROPIC_API_KEY` is set in the server's environment or a key is pasted into the tab; otherwise it runs a rule-based parser. Geocoding (Census, Nominatim) needs internet.

In the Claude desktop app, `.claude/launch.json` defines the `agrihedge` preview server on port 8473.

## Git state

- `main` contains Milestone II through merged PR 3 and the exotic payout study, corrected update, presentation, and archive through merged PR 9. PRs 4-8 are parallel work; see [archive/README.md](archive/README.md).
- `main` is shared: never commit to it directly. Branch per piece of work and open a PR; CI runs pytest.
- Local branches `run/datafix-2`, `run/factcheck-1`, `run/lossmodel-2`, `run/rowcrop-2` are the losing alternates of reviewed two-run comparisons (see doc 11 and the 2026-11-01 merge commits). Kept only for reference.

## Conventions

- Write project documentation for any contributor. Keep personal team messages in chat,
  and use guides for methods, results, limitations and run instructions. Do not describe
  guides as written for an automated reader. Keep research attribution accurate.

- Every number in a doc goes in that doc's numbers table with a source, or is marked unverified.
- Report hedge effectiveness (HE) out of sample (leave one year out, or the 2001-2025 holdout). In-sample HE overstates by about 40%.
- When adding a doc or changing a headline number, update `docs/00_OVERVIEW.md` (and `DEMO.md` key numbers if quoted there).
- Analysis scripts rewrite the AUTO tables in their doc; edit prose around them, not the tables.
- Use the project `.venv` explicitly; don't touch shared environments.
- Live Kalshi prices need internet; everything else falls back to the committed snapshots and is marked "estimated".

## Good first tasks for a new agent

1. Pick up a roadmap item from DEMO.md. Most direct: the liquidity plan (simulate a market maker / pooled orders across ranches) and the two-month contract mock market.
2. Take a second post-rewards order-book snapshot and refresh doc 12 / doc 22 depth numbers.
3. Start the final-paper outline from the Milestone II tex, framed as problem, Milestone I "no", diagnosis, companion, liquidity limit.
4. Run the advisor (doc 24) against the live API with a key, read a dozen transcripts for real farmer phrasings, and tune `advisor.SYSTEM_PROMPT` and the crop table (`advisor.CROPS`, rough values, unverified). Then add a second month and the wet side to what it can design.
