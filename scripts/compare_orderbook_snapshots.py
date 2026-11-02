"""Before/after comparison of two dated Kalshi order-book snapshots (doc 12).

Run from the repo root (no network):
    python scripts/compare_orderbook_snapshots.py --before 20261029 --after 20261102

Inputs (all in data/processed/, written by earlier steps):
    kalshi_rain_hedge_capacity_nov2026_<date>.csv   per-city Nov 2026 book capacity
                                                    (python scripts/pull_kalshi.py --stats [--orderbook ...])
    kalshi_rain_incentive_programs.csv              liquidity-reward programs (pull_kalshi.py)
    payout_comparison_summary_books<before>.csv     per-farm fill capacity on the BEFORE books
                                                    (run_payout_comparison.py --orderbook ... --summary-out ...)
    payout_comparison_summary.csv                   per-farm fill capacity on the AFTER (latest) books

Outputs:
    data/processed/kalshi_post_rewards_city_compare.csv   one row per monthly-rain series
    data/processed/kalshi_post_rewards_farm_compare.csv   one row per representative farm
and markdown tables on stdout (pasted into docs/analysis/12_post_rewards_liquidity.md).

A series is in the "rewarded until <cutoff>" group when its latest liquidity-reward program on
monthly-rain markets ended on the cutoff date (default 2026-11-01, UTC date of the end time).
Every other series had no reward running at either snapshot, so it serves as a control group.
"""
from __future__ import annotations

import argparse
import sys

import numpy as np
import pandas as pd

from agri_hedge.config import PROCESSED

CITY_METRICS = ["no_payout_all", "no_payout_useful", "no_net_useful", "max_strike_no_payout_useful",
                "no_payout_5c", "yes_payout_useful", "median_spread_cents", "two_sided_strikes"]
FARM_METRICS = ["cap_fill_share_any", "cap_fill_share_95", "cap_fill_share_sensible",
                "cap_fill_share_payout_sensible", "cap_busiest_month_contracts",
                "cap_busiest_month_fill_any", "cap_busiest_month_fill_sensible"]


def reward_groups(programs: pd.DataFrame, cutoff: str = "2026-11-01") -> dict[str, str]:
    """{series_ticker: 'rewarded' | 'control'}: 'rewarded' if the series' last program ended on cutoff."""
    if programs.empty:
        return {}
    last_end = programs.groupby("series_ticker")["end_date"].max().astype(str).str[:10]
    return {s: ("rewarded" if d == cutoff else "control") for s, d in last_end.items()}


def compare_cities(before: pd.DataFrame, after: pd.DataFrame, groups: dict[str, str]) -> pd.DataFrame:
    """One row per series present in both snapshots: metric_before, metric_after, and ratio
    after/before for the depth metrics (NaN when before is 0)."""
    keep = ["series_ticker", "site"] + CITY_METRICS
    b = before[keep].rename(columns={m: f"{m}_before" for m in CITY_METRICS})
    a = after[["series_ticker"] + CITY_METRICS].rename(columns={m: f"{m}_after" for m in CITY_METRICS})
    out = b.merge(a, on="series_ticker", how="inner")
    out["site"] = out["site"].fillna("")
    out.insert(2, "reward_group", out["series_ticker"].map(groups).fillna("control"))
    for m in ("no_payout_all", "no_payout_useful", "no_payout_5c", "yes_payout_useful"):
        den = out[f"{m}_before"].replace(0, np.nan)
        out[f"{m}_ratio"] = out[f"{m}_after"] / den
    return out.sort_values(["reward_group", "site", "series_ticker"], ascending=[False, False, True])


def group_medians(cmp: pd.DataFrame) -> pd.DataFrame:
    """Median before/after of the main depth metrics by reward group, plus the median per-city ratio."""
    rows = []
    for g, d in cmp.groupby("reward_group"):
        r = {"reward_group": g, "series": len(d)}
        for m in ("no_payout_all", "no_payout_useful", "max_strike_no_payout_useful", "yes_payout_useful"):
            r[f"{m}_before"] = d[f"{m}_before"].median()
            r[f"{m}_after"] = d[f"{m}_after"].median()
        r["median_ratio_useful_no"] = d["no_payout_useful_ratio"].median()
        r["series_useful_no_down"] = int((d["no_payout_useful_after"] < d["no_payout_useful_before"]).sum())
        rows.append(r)
    return pd.DataFrame(rows).sort_values("reward_group", ascending=False)


def compare_farms(before: pd.DataFrame, after: pd.DataFrame) -> pd.DataFrame:
    """One row per farm with each capacity metric before and after, plus a dollar-weighted total row
    (shares weighted by the farm's contracts per year)."""
    keep = ["farm_id", "site", "cap_contracts_per_year"] + FARM_METRICS
    b = before[keep].rename(columns={m: f"{m}_before" for m in FARM_METRICS})
    a = after[["farm_id"] + FARM_METRICS].rename(columns={m: f"{m}_after" for m in FARM_METRICS})
    out = b.merge(a, on="farm_id", how="inner")
    w = out["cap_contracts_per_year"]
    tot = {"farm_id": "ALL (contract-weighted)", "site": "", "cap_contracts_per_year": float(w.sum())}
    for m in FARM_METRICS:
        for s in ("before", "after"):
            col = f"{m}_{s}"
            tot[col] = (float((out[col] * w).sum() / w.sum()) if m.startswith("cap_fill_share")
                        else float(out[col].sum()))
    return pd.concat([out, pd.DataFrame([tot])], ignore_index=True)


def _md(df: pd.DataFrame, fmt: dict) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            if isinstance(v, (float, np.floating)) and not np.isfinite(v):
                cells.append("")
            elif c in fmt and isinstance(v, (int, float, np.integer, np.floating)):
                cells.append(format(v, fmt[c]))
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Compare two dated Kalshi order-book snapshots.")
    ap.add_argument("--before", default="20261029")
    ap.add_argument("--after", default="20261102")
    ap.add_argument("--cutoff", default="2026-11-01", help="reward end date that defines the treated group")
    args = ap.parse_args(argv)

    cap_b = pd.read_csv(PROCESSED / f"kalshi_rain_hedge_capacity_nov2026_{args.before}.csv")
    cap_a = pd.read_csv(PROCESSED / f"kalshi_rain_hedge_capacity_nov2026_{args.after}.csv")
    groups = reward_groups(pd.read_csv(PROCESSED / "kalshi_rain_incentive_programs.csv"), args.cutoff)
    cities = compare_cities(cap_b, cap_a, groups)
    cities.to_csv(PROCESSED / "kalshi_post_rewards_city_compare.csv", index=False, float_format="%.4f")

    farm_b = pd.read_csv(PROCESSED / f"payout_comparison_summary_books{args.before}.csv")
    farm_a = pd.read_csv(PROCESSED / "payout_comparison_summary.csv")
    want_a = f"{args.after[:4]}-{args.after[4:6]}-{args.after[6:]}"
    if "orderbook_snapshot" in farm_a and set(farm_a["orderbook_snapshot"].astype(str)) != {want_a}:
        raise SystemExit(f"payout_comparison_summary.csv is for books {set(farm_a['orderbook_snapshot'])}, "
                         f"not {want_a}; rerun scripts/run_payout_comparison.py")
    farms = compare_farms(farm_b, farm_a)
    farms.to_csv(PROCESSED / "kalshi_post_rewards_farm_compare.csv", index=False, float_format="%.4f")

    usd = ",.0f"
    study = cities[cities["site"] != ""][[
        "site", "series_ticker", "reward_group", "no_payout_all_before", "no_payout_all_after",
        "no_payout_useful_before", "no_payout_useful_after", "no_payout_useful_ratio",
        "max_strike_no_payout_useful_before", "max_strike_no_payout_useful_after",
        "yes_payout_useful_before", "yes_payout_useful_after",
        "median_spread_cents_before", "median_spread_cents_after",
        "two_sided_strikes_before", "two_sided_strikes_after"]]
    print(f"## Study-site books, Nov 2026 events: {args.before} vs {args.after}\n")
    print(_md(study, {c: usd for c in study.columns if "payout" in c and "ratio" not in c}
                  | {"no_payout_useful_ratio": ".2f", "median_spread_cents_before": ".0f",
                     "median_spread_cents_after": ".0f"}))
    gm = group_medians(cities)
    print("\n## Medians by reward group (all monthly-rain series in both snapshots)\n")
    print(_md(gm, {c: usd for c in gm.columns if c.endswith(("_before", "_after"))}
                  | {"median_ratio_useful_no": ".2f"}))
    show = farms[["farm_id", "site"] + [f"{m}_{s}" for m in ("cap_fill_share_any", "cap_fill_share_sensible",
                                                             "cap_fill_share_payout_sensible")
                                       for s in ("before", "after")]
                 + ["cap_busiest_month_contracts_before", "cap_busiest_month_fill_sensible_before",
                    "cap_busiest_month_fill_sensible_after"]]
    print("\n## Per-farm fill capacity (run_payout_comparison.py capacity block)\n")
    print(_md(show, {c: ".0%" for c in show.columns if "share" in c}
                    | {c: usd for c in show.columns if "busiest" in c}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
