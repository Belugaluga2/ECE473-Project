# ECE473 Project: Agricultural Risk Management & Weather Derivative Replicating Platform

[![tests](https://github.com/Belugaluga2/ECE473-Project/actions/workflows/tests.yml/badge.svg)](https://github.com/Belugaluga2/ECE473-Project/actions/workflows/tests.yml)

Team: Maya, Evan, Jack.

**Maya's experimental branch:** start with [experiments/maya/README.md](experiments/maya/README.md)
for the new offline demo, formula/coefficient explanations, diagnosis and runnable commands.
The experiments preserve the existing PRF Companion and do not change the team's approved direction.

We set out to build a platform that lets a farmer approximate USDA rainfall-index insurance
(Pasture, Rangeland, Forage, or PRF) with a portfolio of Kalshi weather event contracts, and
to measure where the remaining coverage error comes from.

**Status (2026-11-05):** replicating PRF with Kalshi did not work (Milestone I). Milestone II is built
([docs/MILESTONE_2.md](docs/MILESTONE_2.md)) and the project now centres on the **PRF Companion**: keep
your USDA rainfall insurance and use Kalshi contracts to cover the months it leaves open. It is recommended
for 9 of 11 farms and tracks rain-index cover with hedge effectiveness 0.61 on held-out years (doc 21).
Order-book depth is the remaining limit (doc 22). Demo script and roadmap: [docs/DEMO.md](docs/DEMO.md).

**Try the app:**

```bash
.venv/bin/python scripts/run_app.py   # then open http://localhost:8473/?demo
```

**Start here:** [AGENTS.md](AGENTS.md) is a one-page handoff (status, deadlines, conventions). [docs/00_OVERVIEW.md](docs/00_OVERVIEW.md) is the index of all research and results, with next steps.

## Layout

| Path | Contents |
|---|---|
| `AGENTS.md` | Handoff for new contributors and agents |
| `docs/00_OVERVIEW.md` | Milestone overview, status, headline findings |
| `docs/DEMO.md`, `docs/MILESTONE_2.md` | Demo script + roadmap; Milestone II summary |
| `docs/milestone2/` | Milestone II LaTeX write-up and PDF |
| `docs/research/` | Sourced research documents, one topic each |
| `docs/analysis/` | Results produced by our own code |
| `docs/figures/` | Generated figures |
| `src/agri_hedge/` | Python package (data clients, PRF calculator, analysis) |
| `scripts/` | Runnable entry points that pull data and regenerate results |
| `data/processed/` | Small derived datasets (committed) |
| `data/scenarios/` | Representative farm definitions |
| `data/raw/` | Raw downloads (gitignored, recreated by scripts) |
| `tests/` | pytest checks |

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
