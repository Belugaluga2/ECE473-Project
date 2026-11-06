"""Holdout check for the PRF Companion (doc 21): no peeking at the test years.

Run:  python scripts/run_companion_holdout.py

For each farm: score each month PRF leaves open using 1951-2000 only (leave-one-year-out inside that
window), pick months with HE >= 0.5, fit the combined hedge on 1951-2000 at the app's 95% knee, then
score it on 2001-2025, which played no part in any choice. Compared with the same procedure for the
farm's PRF intervals. Writes data/processed/m2_companion_holdout.csv and an AUTO table in doc 21.
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from agri_hedge import hedge_builder as hb
from agri_hedge import optimizer as op
from agri_hedge.config import DOCS, PROCESSED
from agri_hedge.docs_util import write_auto_block
from agri_hedge.hedge_builder import CoverageRequest, Window
from agri_hedge.platform import GOOD_HE, KNEE_SHARE

TRAIN, TEST = (1951, 2000), (2001, 2025)


def fit_train(p, prot):
    tr_mask = (p.years >= TRAIN[0]) & (p.years <= TRAIN[1]) & p.ok
    X, y = p.X[tr_mask], p.target[tr_mask]
    tr = op.model_tranches(p.q)
    fr = op.efficient_frontier(X, y, tr, n_points=13, scale=prot, q=p.q)
    b = op.knee_budget(fr, KNEE_SHARE)
    return X, y, tr, b, op.solve_budget(X, y, tr, b, prot)


def test_he(p, sol):
    m = (p.years >= TEST[0]) & (p.years <= TEST[1]) & p.ok
    y, h = p.target[m], p.X[m] @ sol.leg_contracts
    return op.hedge_effectiveness(y, h), float(np.corrcoef(y, h)[0, 1]) if np.std(h) > 0 and np.std(y) > 0 else np.nan, int(m.sum())


def main() -> int:
    rows = []
    for F in hb.load_farm_requests():
        r, prot = F["request"], F["protection"]
        gap = prot / 6
        covered = {m for w in r.windows for m in w.months}
        picked = []
        for m in sorted(set(range(1, 13)) - covered):
            pm = hb.build_problem(CoverageRequest(r.lat, r.lon, [Window((m,), 1.0)], r.coverage, gap,
                                                  station_key=r.station_key, grid_id=r.grid_id))
            X, y, tr, b, _ = fit_train(pm, gap)
            if np.var(y) > 0 and op.hedge_effectiveness(y, op.loyo_payout(X, y, tr, b, gap)) >= GOOD_HE:
                picked.append(m)
        row = {"farm_id": F["farm_id"], "picked_on_1951_2000": ", ".join(hb.MONTH_ABBR[m - 1] for m in picked)}
        if picked:
            pc = hb.build_problem(CoverageRequest(r.lat, r.lon, [Window((m,), 1.0 / len(picked)) for m in picked],
                                                  r.coverage, gap * len(picked), station_key=r.station_key, grid_id=r.grid_id))
            _, _, _, _, sol = fit_train(pc, gap * len(picked))
            row["companion_he_2001_2025"], row["companion_corr_2001_2025"], row["test_years"] = test_he(pc, sol)
        pp = hb.build_problem(r)
        _, _, _, _, sol = fit_train(pp, prot)
        row["prf_intervals_he_2001_2025"], row["prf_intervals_corr_2001_2025"], _ = test_he(pp, sol)
        rows.append(row)
        print(row, flush=True)
    d = pd.DataFrame(rows)
    d.to_csv(PROCESSED / "m2_companion_holdout.csv", index=False)
    f = lambda v: "" if pd.isna(v) else f"{v:.2f}"  # noqa: E731
    out = ["### Holdout: months chosen and hedges fit on 1951-2000, scored on 2001-2025", "",
           "| Farm | Months picked (1951-2000 data only) | Companion HE 2001-2025 | Hedging the PRF intervals, HE 2001-2025 |",
           "|---|---|---|---|"]
    for _, x in d.iterrows():
        out.append(f"| {x['farm_id']} | {x['picked_on_1951_2000'] or 'none'} | {f(x.get('companion_he_2001_2025'))} "
                   f"| {f(x['prf_intervals_he_2001_2025'])} |")
    has = d.dropna(subset=["companion_he_2001_2025"]) if "companion_he_2001_2025" in d else d.iloc[0:0]
    out += ["", f"Median over farms with a pick: companion {f(has['companion_he_2001_2025'].median())} vs PRF intervals "
            f"{f(has['prf_intervals_he_2001_2025'].median())}; companion better on {(has['companion_he_2001_2025'] > has['prf_intervals_he_2001_2025']).sum()} "
            f"of {len(has)} farms. All 11 farms, PRF intervals: {f(d['prf_intervals_he_2001_2025'].median())}."]
    write_auto_block(DOCS / "analysis" / "21_prf_companion.md", "companion holdout (scripts/run_companion_holdout.py)", "\n".join(out))
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
