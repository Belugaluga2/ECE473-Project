# Agent handoff: ECE473 AgriHedge

Read this first, then [docs/00_OVERVIEW.md](docs/00_OVERVIEW.md) (index of every doc, headline numbers, next steps).

## What the project is now (2026-11-05)

ECE473 team project (Maya, Evan, Jack). It started as "replicate USDA rainfall insurance (PRF) with Kalshi monthly-rain contracts". That failed: Kalshi costs about 1.8x subsidized PRF, airport gauges sit 30-55 miles from the farm, and order books are thin (docs 08-09, 16).

**Current direction: the PRF Companion.** Keep PRF, and use Kalshi contracts to cover the months PRF leaves open (mostly Nov-Feb), where the airport gauge tracks the farm's rain index well. Holdout HE 0.61 vs 0.23 for copying PRF's own intervals; recommended for 9 of 11 farms (doc 21). The binding limit is now order-book liquidity: 5-10x today's depth is needed (doc 22). The rest of the course builds on the companion.

## Deadlines

| Date | Deliverable | Where |
|---|---|---|
| 2026-11-12 | Milestone II write-up | `docs/milestone2/milestone2.tex` / `.pdf` (Overleaf-ready; build locally with `tectonic -X compile milestone2.tex`) |
| 2026-11-17 | Slides and presentations | Deck linked from [docs/DEMO.md](docs/DEMO.md) |
| 2026-12-15 | Final paper | not started; roadmap in DEMO.md |

## Where things are

- `docs/DEMO.md`: five-minute demo script, **roadmap of next steps** (7 items, each naming the module it extends), key numbers to quote.
- `docs/MILESTONE_2.md`: Milestone II summary table and reproduce commands with run times.
- `docs/research/` (sourced background, docs 01-10), `docs/analysis/` (our results, docs 04b-22, numbered in the order they were done).
- `src/agri_hedge/`: the package. The app's single entry point is `platform.quote` (custom hedge) and `platform.companion` (PRF Companion). Fitting is in `optimizer.py` + `hedge_builder.py`.
- `scripts/run_*.py` regenerate each analysis doc's numbers, CSVs and figures. `scripts/pull_*.py` download raw data into `data/raw/` (gitignored, currently empty; committed `data/processed/` is enough for tests, the app and the Milestone 2 scripts).
- `scripts/experiments/`: two one-off experiments cited in doc 21's numbers table. Keep them.

## Run it

```bash
.venv/bin/python -m pytest              # 402 tests, ~10 s
.venv/bin/python scripts/run_app.py     # http://localhost:8473/?demo  (PRF Companion, Dallas hay farm)
```

In the Claude desktop app, `.claude/launch.json` defines the `agrihedge` preview server on port 8473.

## Git state

- Work happens on `milestone-2`. It is pushed and open as GitHub PR 3 into `main`, and it already contains the branches of PRs 1 and 2. Merging is the team's call, not an agent's.
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
