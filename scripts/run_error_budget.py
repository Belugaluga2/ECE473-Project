"""Milestone 2, W4: hedge-error waterfall (doc 16, Maya) and contract proposals (doc 17, Evan).

Run from the repo root:   python scripts/run_error_budget.py

Part 1 (doc 16). For each of the 11 farms, and for each farm's insured windows on their own,
hedge effectiveness (HE) is measured after each restriction in turn: geography, settlement
source, monthly contracts, whole-inch strikes, order-book depth, and a budget equal to the PRF
producer premium (see `agri_hedge.error_budget`). Every step uses the optimizer's lowest-error
fit (doc 15) on the same years, scored in-sample and leave-one-year-out (LOYO).

Part 2 (doc 17). The same targets hedged with proposed contracts: half-inch monthly strikes,
two-month total contracts (1-inch and half-inch strikes), and binary contracts on the farm
grid's own PRF index (10- and 5-point steps). It also measures how much deeper the order book
would need to be to fill each farm's hedge.

Outputs: data/processed/m2_error_budget_farm.csv, m2_error_budget_window.csv,
m2_contract_proposals.csv, m2_liquidity_needed.csv, docs/figures/m2_error_waterfall.png,
m2_waterfall_by_farm.png, m2_proposals.png, and AUTO tables in docs/analysis/16_error_budget.md
and 17_contract_gaps_and_proposals.md. No network. Runs in a few minutes.
"""
from __future__ import annotations

import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from agri_hedge import error_budget as eb  # noqa: E402
from agri_hedge import hedge_builder as hb  # noqa: E402
from agri_hedge import optimizer as op  # noqa: E402
from agri_hedge.config import DOCS, FIGURES, PROCESSED  # noqa: E402
from agri_hedge.docs_util import write_auto_block  # noqa: E402
from agri_hedge.hedge_builder import CoverageRequest  # noqa: E402

DOC16 = DOCS / "analysis" / "16_error_budget.md"
DOC17 = DOCS / "analysis" / "17_contract_gaps_and_proposals.md"
STEPS = [("S0", "Perfect: contract on the farm's own grid index"),
         ("S1", "Geography: PRF formula on the station's grid"),
         ("S2", "Settlement source: PRF formula on the station gauge"),
         ("S3", "Monthly contracts (0.25-inch strikes)"),
         ("S4", "Kalshi's listed strikes (whole inches)"),
         ("S5", "Order-book depth (Nov 2026, post-rewards)"),
         ("S6", "Budget = PRF producer premium")]
PROPOSALS = [("today", "Today: monthly, whole-inch strikes"),
             ("P1", "Monthly, half-inch strikes from 0.5 in"),
             ("P2", "Two-month total, 1-inch strikes"),
             ("P3", "Two-month total, half-inch strikes"),
             ("P4", "Grid-index binaries, 10-point steps"),
             ("P5", "Grid-index binaries, 5-point steps")]


def station_grid(site: str) -> int:
    sg = pd.read_csv(PROCESSED / "study_grids.csv")
    return int(sg[(sg["site"] == site) & (sg["role"] == "station")]["grid_id"].iloc[0])


def fit_scores(X, y, mask, q, prot, caps=None, budget=None) -> dict:
    Xm, ym = X[mask], y[mask]
    tr = op.model_tranches(q)
    if caps is not None:
        for t, c in zip(tr, caps):
            t.capacity = float(c)
    if budget is None:
        sol = op.solve_penalized(Xm, ym, tr, 0.0, prot)
    else:
        sol = op.solve_budget(Xm, ym, tr, budget, prot)
    loyo = op.loyo_payout(Xm, ym, tr, budget, prot)
    ev = float(np.asarray(q) @ sol.leg_contracts)
    return {"he_in": op.hedge_effectiveness(ym, sol.payout), "he_loyo": op.hedge_effectiveness(ym, loyo),
            "var_y": float(np.var(ym / prot)), "var_resid_in": float(np.var((ym - sol.payout) / prot)),
            "var_resid_loyo": float(np.var((ym - loyo) / prot)), "n": int(mask.sum()),
            "cost": sol.cost, "expected_payout": ev, "n_instruments": X.shape[1],
            "max_leg_contracts": float(sol.leg_contracts.max()) if len(sol.leg_contracts) else 0.0,
            "leg_contracts": sol.leg_contracts}


def analyse(p: hb.HedgeProblem, site: str, prot: float, budget: float, depth: dict) -> tuple[list, list, dict]:
    y = p.target
    inst = {}
    inst["S1"] = eb.station_grid_index_cols(p, station_grid(site))
    inst["S2"] = eb.station_gauge_index_cols(p)
    inst["S3"] = eb.monthly_ladder_cols(p, np.round(np.arange(0.25, 15.01, 0.25), 2))
    inst["S4"] = eb.dedupe(p.X, p.legs, p.q)
    inst["P1"] = eb.monthly_ladder_cols(p, np.round(np.arange(0.5, 15.01, 0.5), 2))
    inst["P2"] = eb.window_total_ladder_cols(p, 1.0)
    inst["P3"] = eb.window_total_ladder_cols(p, 0.5)
    inst["P4"] = eb.grid_index_ladder_cols(p, 10.0)
    inst["P5"] = eb.grid_index_ladder_cols(p, 5.0)
    mask = ~np.isnan(y)
    for X, _, _ in inst.values():
        mask &= ~np.isnan(X).any(axis=1)
    vy = float(np.var(y[mask] / prot))
    wf = [{"step": "S0", "he_in": 1.0, "he_loyo": 1.0, "var_y": vy, "var_resid_in": 0.0, "var_resid_loyo": 0.0,
           "n": int(mask.sum())}]
    for s in ("S1", "S2", "S3", "S4"):
        X, lab, q = inst[s]
        r = fit_scores(X, y, mask, q, prot)
        r.pop("leg_contracts")
        wf.append({"step": s, **r})
    X4, lab4, q4 = inst["S4"]
    caps = [depth.get(k, 0.0) for (_, k) in lab4]
    r = fit_scores(X4, y, mask, q4, prot, caps=caps)
    r.pop("leg_contracts")
    wf.append({"step": "S5", **r})
    r = fit_scores(X4, y, mask, q4, prot, caps=caps, budget=budget)
    r.pop("leg_contracts")
    wf.append({"step": "S6", **r})
    props, legs_today = [], None
    for key, _ in PROPOSALS:
        X, lab, q = inst["S4" if key == "today" else key]
        r = fit_scores(X, y, mask, q, prot)
        lc = r.pop("leg_contracts")
        if key == "today":
            legs_today = (lab, lc)
        props.append({"proposal": key, **r})
    return wf, props, {"labels": legs_today[0], "contracts": legs_today[1], "caps": caps}


def pooled(d: pd.DataFrame, col: str) -> float:
    return float(1 - (d["n"] * d[col]).sum() / (d["n"] * d["var_y"]).sum())


def main() -> int:
    farms = hb.load_farm_requests()
    wf_rows, wwf_rows, prop_rows, liq_rows = [], [], [], []
    for F in farms:
        req, site, prot = F["request"], F["site"], F["protection"]
        series = hb.station_table().set_index("station_key").loc[req.station_key, "series_ticker"]
        depth, snap = eb.book_depth_by_strike(series, req.station_key)
        p = hb.build_problem(req)
        wf, props, legs = analyse(p, site, prot, F["producer_premium"], depth)
        for r in wf:
            wf_rows.append({"farm_id": F["farm_id"], "site": site, **r})
        for r in props:
            prop_rows.append({"farm_id": F["farm_id"], "site": site, "scope": "farm", "window": "all", **r})
        # liquidity needed: contracts per leg vs depth at a sensible price
        for (m, k), c, cap in zip(legs["labels"], legs["contracts"], legs["caps"]):
            if c > 1e-6:
                liq_rows.append({"farm_id": F["farm_id"], "site": site, "month": m, "strike_in": k,
                                 "contracts_needed": c, "depth_sensible": cap, "book_snapshot": snap})
        # each window on its own
        for w in req.windows:
            r1 = CoverageRequest(req.lat, req.lon, [hb.Window(w.months, 1.0)], req.coverage, prot * w.share,
                                 station_key=req.station_key, strikes="kalshi", grid_id=req.grid_id)
            pw = hb.build_problem(r1)
            wfw, propw, _ = analyse(pw, site, prot * w.share, F["producer_premium"] * w.share, depth)
            for r in wfw:
                wwf_rows.append({"farm_id": F["farm_id"], "site": site, "window": w.label, "share": w.share, **r})
            for r in propw:
                prop_rows.append({"farm_id": F["farm_id"], "site": site, "scope": "window", "window": w.label, **r})
        print(F["farm_id"], "done", flush=True)
    wf = pd.DataFrame(wf_rows)
    wwf = pd.DataFrame(wwf_rows)
    prop = pd.DataFrame(prop_rows)
    liq = pd.DataFrame(liq_rows)
    wf.to_csv(PROCESSED / "m2_error_budget_farm.csv", index=False)
    wwf.to_csv(PROCESSED / "m2_error_budget_window.csv", index=False)
    prop.to_csv(PROCESSED / "m2_contract_proposals.csv", index=False)
    liq.to_csv(PROCESSED / "m2_liquidity_needed.csv", index=False)
    figures(wf, prop)
    t16, t17 = tables16(wf, wwf), tables17(prop, wwf, liq)
    write_auto_block(DOC16, "error budget tables (scripts/run_error_budget.py)", t16)
    write_auto_block(DOC17, "contract proposal tables (scripts/run_error_budget.py)", t17)
    print(t16)
    print(t17)
    return 0


def figures(wf: pd.DataFrame, prop: pd.DataFrame) -> None:
    steps = [s for s, _ in STEPS]
    pin = [pooled(wf[wf["step"] == s], "var_resid_in") for s in steps]
    plo = [pooled(wf[wf["step"] == s], "var_resid_loyo") for s in steps]
    fig, ax = plt.subplots(figsize=(10, 4.6))
    x = np.arange(len(steps))
    ax.bar(x - 0.2, pin, 0.4, color="#2a6f97", label="in-sample 1951-2025")
    ax.bar(x + 0.2, plo, 0.4, color="#f4a261", label="out of sample (LOYO)")
    for i, (a, b) in enumerate(zip(pin, plo)):
        ax.text(i - 0.2, a + 0.01, f"{a:.2f}", ha="center", fontsize=8)
        ax.text(i + 0.2, b + 0.01, f"{b:.2f}", ha="center", fontsize=8)
    ax.set_xticks(x, ["Perfect", "Geography", "Settlement\nsource", "Monthly\ncontracts", "Whole-inch\nstrikes",
                      "Order-book\ndepth", "Budget =\nPRF premium"], fontsize=8)
    ax.set_ylabel("Pooled hedge effectiveness, 11 farms")
    ax.set_ylim(0, 1.08)
    ax.legend(fontsize=8)
    ax.grid(axis="y", alpha=0.3)
    ax.set_title("Hedge error waterfall: what each real-world restriction costs")
    fig.tight_layout()
    fig.savefig(FIGURES / "m2_error_waterfall.png", dpi=150)
    plt.close(fig)

    piv = wf.pivot(index="farm_id", columns="step", values="he_loyo").reindex(
        list(dict.fromkeys(wf["farm_id"])))[steps]
    fig, ax = plt.subplots(figsize=(8, 5))
    im = ax.imshow(piv.clip(lower=-0.2).to_numpy(), cmap="viridis", vmin=-0.2, vmax=1, aspect="auto")
    ax.set_xticks(range(len(steps)), steps)
    ax.set_yticks(range(len(piv)), piv.index)
    for i in range(piv.shape[0]):
        for j in range(piv.shape[1]):
            v = piv.iloc[i, j]
            ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=7, color="w" if v < 0.6 else "k")
    fig.colorbar(im, ax=ax, label="HE, LOYO")
    ax.set_title("Waterfall by farm (out of sample)")
    fig.tight_layout()
    fig.savefig(FIGURES / "m2_waterfall_by_farm.png", dpi=150)
    plt.close(fig)

    d = prop[prop["scope"] == "farm"]
    keys = [k for k, _ in PROPOSALS]
    pin = [pooled(d[d["proposal"] == k], "var_resid_in") for k in keys]
    plo = [pooled(d[d["proposal"] == k], "var_resid_loyo") for k in keys]
    fig, ax = plt.subplots(figsize=(10, 4.4))
    x = np.arange(len(keys))
    ax.bar(x - 0.2, pin, 0.4, color="#2a6f97", label="in-sample")
    ax.bar(x + 0.2, plo, 0.4, color="#f4a261", label="out of sample (LOYO)")
    for i, (a, b) in enumerate(zip(pin, plo)):
        ax.text(i - 0.2, a + 0.01, f"{a:.2f}", ha="center", fontsize=8)
        ax.text(i + 0.2, b + 0.01, f"{b:.2f}", ha="center", fontsize=8)
    ax.set_xticks(x, [lab.replace(", ", ",\n") for _, lab in PROPOSALS], fontsize=8)
    ax.set_ylim(0, 1.08)
    ax.set_ylabel("Pooled hedge effectiveness, 11 farms")
    ax.legend(fontsize=8)
    ax.grid(axis="y", alpha=0.3)
    ax.set_title("Proposed contracts: hedge quality with no depth or budget limit")
    fig.tight_layout()
    fig.savefig(FIGURES / "m2_proposals.png", dpi=150)
    plt.close(fig)


def _f(v, nd=2):
    return "" if pd.isna(v) else f"{v:,.{nd}f}"


def tables16(wf: pd.DataFrame, wwf: pd.DataFrame) -> str:
    out = ["### Pooled over the 11 farms", "",
           "Pooled HE = 1 - sum(n x residual variance) / sum(n x PRF payout variance), with payouts per $1 of "
           "protection so each farm counts by its risk, not its size.", "",
           "| Step | Restriction added | Pooled HE in-sample | Drop | Pooled HE LOYO | Drop | Median farm HE LOYO |",
           "|---|---|---|---|---|---|---|"]
    prev_in = prev_lo = None
    for s, lab in STEPS:
        d = wf[wf["step"] == s]
        a, b = pooled(d, "var_resid_in"), pooled(d, "var_resid_loyo")
        out.append(f"| {s} | {lab} | {_f(a)} | {'' if prev_in is None else _f(prev_in - a)} | {_f(b)} "
                   f"| {'' if prev_lo is None else _f(prev_lo - b)} | {_f(d['he_loyo'].median())} |")
        prev_in, prev_lo = a, b
    out += ["", "### Each farm, out of sample (HE LOYO after each step)", "",
            "| Farm | " + " | ".join(s for s, _ in STEPS) + " | Largest single drop |",
            "|---|" + "---|" * (len(STEPS) + 1)]
    for fid, d in wf.groupby("farm_id", sort=False):
        v = d.set_index("step")["he_loyo"].reindex([s for s, _ in STEPS])
        drops = (-v.diff()).iloc[1:]
        big = drops.idxmax()
        out.append(f"| {fid} | " + " | ".join(_f(x) for x in v) + f" | {big} ({_f(drops.max())}) |")
    out += ["", "### Which step costs most, counted over every insured window (LOYO)", "",
            "| Step | Windows where it is the largest drop | Mean drop |", "|---|---|---|"]
    rows = []
    for (fid, w), d in wwf.groupby(["farm_id", "window"], sort=False):
        v = d.set_index("step")["he_loyo"].reindex([s for s, _ in STEPS])
        drops = (-v.diff()).iloc[1:]
        rows.append({"farm_id": fid, "window": w, "largest": drops.idxmax(), **drops.to_dict()})
    rr = pd.DataFrame(rows)
    for s, lab in STEPS[1:]:
        out.append(f"| {s} {lab.split(':')[0]} | {(rr['largest'] == s).sum()} of {len(rr)} | {_f(rr[s].mean())} |")
    return "\n".join(out)


def tables17(prop: pd.DataFrame, wwf: pd.DataFrame, liq: pd.DataFrame) -> str:
    d = prop[prop["scope"] == "farm"]
    out = ["### Proposed contracts, pooled over the 11 farms (lowest-error hedge, no depth or budget limit)", "",
           "| Contract set | Pooled HE in | Pooled HE LOYO | Median farm HE LOYO | Farms with HE LOYO >= 0.6 "
           "| Total cost / yr | Cost per $1 expected |", "|---|---|---|---|---|---|---|"]
    for k, lab in PROPOSALS:
        x = d[d["proposal"] == k]
        out.append(f"| {k}: {lab} | {_f(pooled(x, 'var_resid_in'))} | {_f(pooled(x, 'var_resid_loyo'))} "
                   f"| {_f(x['he_loyo'].median())} | {(x['he_loyo'] >= 0.6).sum()} of {len(x)} "
                   f"| ${x['cost'].sum():,.0f} | {_f(x['cost'].sum() / x['expected_payout'].sum())} |")
    w = prop[prop["scope"] == "window"]
    piv = w.pivot_table(index=["farm_id", "window"], columns="proposal", values="he_loyo", sort=False)
    out += ["", "### Every insured window: out-of-sample HE today and with each proposal", "",
            "Class: replicable = today's HE LOYO >= 0.6; partial = 0.3-0.6; not replicable = below 0.3.", "",
            "| Farm | Window | Today | P1 | P2 | P3 | P4 | P5 | Class today |", "|---|---|---|---|---|---|---|---|---|"]
    for (fid, win), r in piv.iterrows():
        t = r["today"]
        cls = "replicable" if t >= 0.6 else ("partial" if t >= 0.3 else "not replicable")
        out.append(f"| {fid} | {win} | " + " | ".join(_f(r[k]) for k in ("today", "P1", "P2", "P3", "P4", "P5"))
                   + f" | {cls} |")
    cls = pd.cut(piv["today"], [-np.inf, 0.3, 0.6, np.inf], right=False,
                 labels=["not replicable", "partial", "replicable"]).value_counts()
    out += ["", "Windows by class today: " + ", ".join(f"{k} {v}" for k, v in cls.items()) + f" (of {len(piv)}).",
            "", "### Order-book depth needed (lowest-error hedge with today's strikes)", "",
            "Depth = NO contracts offered within 10 cents of fair value on the Nov 2026 book (2026-11-02 snapshot), "
            "taken as the depth for every month.", "",
            "| Farm | Legs used | Contracts in busiest leg | Depth at that strike | Busiest leg / depth "
            "| Share of all contracts fillable |", "|---|---|---|---|---|---|"]
    for fid, x in liq.groupby("farm_id", sort=False):
        b = x.loc[x["contracts_needed"].idxmax()]
        fill = np.minimum(x["contracts_needed"], x["depth_sensible"]).sum() / x["contracts_needed"].sum()
        ratio = b["contracts_needed"] / b["depth_sensible"] if b["depth_sensible"] > 0 else np.inf
        out.append(f"| {fid} | {len(x)} | {b['contracts_needed']:,.0f} | {b['depth_sensible']:,.0f} "
                   f"| {'no depth' if not np.isfinite(ratio) else f'{ratio:,.0f}x'} | {fill:.0%} |")
    tot_fill = np.minimum(liq["contracts_needed"], liq["depth_sensible"]).sum() / liq["contracts_needed"].sum()
    out += ["", f"All farms together: {tot_fill:.0%} of the contracts could be filled at a sensible price, "
            "if each farm had the book to itself."]
    return "\n".join(out)


if __name__ == "__main__":
    sys.exit(main())
