# ECE473 Project: Agricultural Risk Management & Weather Derivative Replicating Platform

[![tests](https://github.com/Belugaluga2/ECE473-Project/actions/workflows/tests.yml/badge.svg)](https://github.com/Belugaluga2/ECE473-Project/actions/workflows/tests.yml)

Team: Maya, Evan, Jack.

We set out to build a platform that lets a farmer approximate USDA rainfall-index insurance
(Pasture, Rangeland, Forage, or PRF) with a portfolio of Kalshi weather event contracts, and
to measure where the remaining coverage error comes from.

**Status (2026-11-13):** Milestone I tested replacing USDA PRF with Kalshi rain contracts. That failed
on cost, geographic fit and order-book depth. Milestone II therefore built the **PRF Companion**: keep
PRF and use Kalshi for months a farmer did not select. It is recommended for 9 of 11 sample farms and
tracks a rain-index payout with hedge effectiveness 0.61 on held-out years (doc 21). That fit is not a
measured reduction in farm-income loss. The [Milestone II summary](docs/MILESTONE_2.md) and
[November 12 update](docs/milestone2/milestone2_update.pdf) record the progression.

**Next question (2026-11-08):** the project now also designs **drought-weighted payoffs** on the same contracts
([docs/analysis/23_exotic_payouts.md](docs/analysis/23_exotic_payouts.md)): convex, step-up, two-tailed and
loss-matched shapes. A fully filled long-only portfolio of NO and YES contracts matches the chosen
station-settled payout on the listed strike bins; it does not remove the farmer's station-to-farm basis risk.
`platform.exotic_quote` writes the term sheet and the ticket.

**Correction and design result (2026-11-09):** [doc 24](docs/analysis/24_contract_design.md) re-tests the
shapes at equal premium. The apparent convex depth advantage in doc 23 disappears (0 of 36 windows beat
linear). Under the stated modeled farmer and price assumptions, exponential and quadratic shapes capture
93% and 90% of the utility-optimal contract's value; linear captures 67%. These are modeled utility results,
and the full Dallas example cannot be filled on the saved book. The app has a "Design a contract" tab and
an advisor. Its rule-based path runs in the demo; the Claude path has scripted tests but no live API test yet.

**Try the app:**

```bash
.venv/bin/python scripts/run_app.py   # then open http://localhost:8473/?demo
```

**TA reading path:** [AGENTS.md](AGENTS.md) for status and deadlines; [docs/00_OVERVIEW.md](docs/00_OVERVIEW.md)
for the evidence index; [docs/MILESTONE_2.md](docs/MILESTONE_2.md) and the
[November 12 update](docs/milestone2/milestone2_update.pdf) for the submitted milestone; then
[docs/DEMO.md](docs/DEMO.md) for the presentation and app. Separate topic research is preserved in
[archive/](archive/README.md).

## Layout

| Path | Contents |
|---|---|
| `AGENTS.md` | Handoff for new contributors and agents |
| `docs/00_OVERVIEW.md` | Milestone overview, status, headline findings |
| `docs/DEMO.md`, `docs/MILESTONE_2.md` | Demo script + roadmap; Milestone II summary |
| `docs/milestone2/` | Milestone II write-up, November 12 update, and PDFs |
| `docs/presentation/` | Ten-minute presentation and handoff |
| `docs/research/` | Sourced research documents, one topic each |
| `docs/analysis/` | Results produced by our own code |
| `docs/figures/` | Generated figures |
| `src/agri_hedge/` | Python package (data clients, PRF calculator, analysis) |
| `scripts/` | Runnable entry points that pull data and regenerate results |
| `data/processed/` | Committed derived datasets for offline reproduction |
| `data/scenarios/` | Representative farm definitions |
| `data/raw/` | Raw downloads (gitignored, recreated by scripts) |
| `tests/` | pytest checks |
| `archive/` | Research for alternate topics, kept outside the AgriHedge reading path |

## Setup

Requires Python 3.11+. Use a project virtual environment so the shared one stays untouched:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m pytest
```

Raw downloads default to `data/raw/`. Set `AGRI_HEDGE_RAW_DIR` to keep them outside OneDrive.

## Workflow

- `main` is the shared branch. Don't commit to it directly.
- Do each piece of work on its own branch (e.g. `maya/hedge-optimizer`), then open a pull request into `main`.
- GitHub Actions runs the test suite on every pull request; merge only when it passes and a teammate has looked at it.
- Every number in a doc needs a source in that doc's numbers table, or a note that it is unverified.
- Update `docs/00_OVERVIEW.md` when you add a doc or change a headline finding.
