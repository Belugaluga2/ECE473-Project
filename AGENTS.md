# Agent handoff: ECE473 AgriHedge

Read this first, then [docs/00_OVERVIEW.md](docs/00_OVERVIEW.md) (index of every doc, headline numbers, next steps).

## What the project is now (2026-11-13)

ECE473 team project (Maya, Evan, Jack). It started as "replicate USDA rainfall insurance (PRF) with Kalshi monthly-rain contracts". That failed: Kalshi costs about 1.8x subsidized PRF, airport gauges sit 30-55 miles from the farm, and order books are thin (docs 08-09, 16).

**Current direction: the PRF Companion and drought-weighted contract design.** Keep PRF, and use Kalshi contracts for months the sample farmers did not select (mostly Nov-Feb), where airport rain tracks their farm grids better. The companion's holdout HE is 0.61 versus 0.23 for copying selected PRF intervals; the app recommends it for 9 of 11 farms (doc 21). These are rain-index payout fits, not demonstrated farm-income protection. Order-book liquidity limits size: 5-10x the saved depth would be needed to restore the uncapped fit (doc 22). The newer design study asks which payout shape a modeled risk-averse farmer would prefer (docs 23-24).

**Added 2026-11-08: exotic payoffs (doc 23).** Nine payout shapes, a replicating NO/YES portfolio, a saved-book execution check, and `platform.exotic_quote` / `POST /api/exotic` (term sheet + ticket + farmer basis risk). A fully filled portfolio reproduces a station-settled payout on Kalshi's strike bins; it does not remove station-to-farm basis risk. Doc 23's apparent convex-shape depth advantage compares equal maximum payouts. Doc 24 shows that advantage disappears at equal premium.

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

## Run it

```bash
.venv/bin/python -m pytest              # 379 tests, ~10 s (~35 s on Windows)
.venv/bin/python scripts/run_app.py     # http://localhost:8473/?demo  (PRF Companion, Dallas hay farm); ?demo=exotic, ?demo=advisor
```

On Windows the venv's interpreter is `.venv\Scripts\python.exe` (create it with `python -m venv .venv` and `.venv\Scripts\python.exe -m pip install -e .`).

The advisor uses Claude (`claude-opus-5-5`, Anthropic SDK) when `ANTHROPIC_API_KEY` is set in the server's environment or a key is pasted into the tab; otherwise it runs a rule-based parser. Geocoding (Census, Nominatim) needs internet.

In the Claude desktop app, `.claude/launch.json` defines the `agrihedge` preview server on port 8473.

## Git state

- `main` already contains Milestone II through merged PR 3. The newer exotic payout work began on `exotic-payouts` and is being organized for review separately. PRs 4-8 are parallel work; see [archive/README.md](archive/README.md).
- `main` is shared: never commit to it directly. Branch per piece of work and open a PR; CI runs pytest.
- Local branches `run/datafix-2`, `run/factcheck-1`, `run/lossmodel-2`, `run/rowcrop-2` are the losing alternates of reviewed two-run comparisons (see doc 11 and the 2026-11-01 merge commits). Kept only for reference.

## Conventions

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
