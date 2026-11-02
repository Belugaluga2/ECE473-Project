# ECE473 Project: Agricultural Risk Management & Weather Derivative Replicating Platform

[![tests](https://github.com/Belugaluga2/ECE473-Project/actions/workflows/tests.yml/badge.svg)](https://github.com/Belugaluga2/ECE473-Project/actions/workflows/tests.yml)

Team: Maya, Evan, Jack.

We are building a platform that lets a farmer approximate USDA rainfall-index insurance
(Pasture, Rangeland, Forage, or PRF) with a portfolio of Kalshi weather event contracts, and
measuring where the remaining coverage error comes from.

**Start here:** [docs/00_OVERVIEW.md](docs/00_OVERVIEW.md) is the index of all research and results, with status and next steps.

## Layout

| Path | Contents |
|---|---|
| `docs/00_OVERVIEW.md` | Milestone overview, status, headline findings |
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
