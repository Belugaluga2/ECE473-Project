"""Rebuild PRF grid indexes from CPC (and NCEI) data and validate them against RMA's official values.

Run from the repo root after pull_prf_official_index.py and pull_cpc.py:
    python scripts/build_indices.py

Two official references exist and they are NOT the same numbers (see 06b_index_validation.md):
  A. As-settled final grid indexes from the Actuarial Data Master (ADM A00810 "Final Index Value"),
     crop years 2021-2026, 14 PRF study grids. These are what RMA actually paid on (CPC data).
     Read from the PRF actuarial workstream's cache data/raw/prf_actuarial/adm_final_index_history.csv
     (or data/processed/prf_actuarial_study_grids.csv for 2025-2026); skipped if neither exists.
  B. Historical index values served today by the PRF Decision Support Tool (DST), 1951-2026,
     from scripts/pull_prf_official_index.py. These are recomputed from NCEI nClimGrid.

Outputs:
  data/processed/cpc_interval_index.parquet   grid_id, year, interval_name, interval_code,
        interval_precip_in, expected_precip_in, index_value_ours, index_value_fixed_base
        (CPC, all cells within 150 mi of a station; index_value_ours uses RMA's as-settled
        handbook rule, base 1948 to Y-2, defined from 1969 when >= 20 base years exist;
        index_value_fixed_base uses one base for all years like the DST: 1948-2025, and
        1948-2024 for 2026; expected_precip_in belongs to index_value_ours; indexes are rounded
        to 0.1 point as RMA publishes them, rainfall to 0.0001 in, to keep files under 25 MB)
  data/processed/ncei_interval_index.parquet  same layout from NCEI nClimGrid (1951 on); here
        index_value_ours follows the DST convention (base 1951-2025; 2026: 1951-2024)
  data/processed/b1_index_validation_summary.csv   every metric quoted in 06b_index_validation.md
  docs/figures/b1_index_validation_scatter.png, docs/figures/b1_cpc_vs_official_by_year.png
Markdown tables are printed to stdout.
"""
from __future__ import annotations

import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from agri_hedge.config import FIGURES, PROCESSED, RAW  # noqa: E402
from agri_hedge.cpc import (MM_PER_INCH, comparison_stats, compute_index, dst_base_end,  # noqa: E402
                            handbook_base_end, interval_totals)
from agri_hedge.prf_grid import grid_id_to_rowcol  # noqa: E402

COVERAGE = 90.0
KEY = ["grid_id", "year", "interval_name"]
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#d9d8d4"

# label: (base_start, base_end rule, min_base_years)
CPC_CANDIDATES = {
    "Handbook as-settled, 1948 to Y-2": (1948, handbook_base_end, 20),
    "1951 to Y-2": (1951, handbook_base_end, 20),
    "Fixed 1948-2025 (2026: 1948-2024)": (1948, dst_base_end, 1),
    "Fixed 1951-2025 (2026: 1951-2024), DST rule": (1951, dst_base_end, 1),
    "Fixed 1981-2010 normal": (1981, 2010, 1),
    "Fixed 1991-2020 normal": (1991, 2020, 1),
}
AS_SETTLED = "Handbook as-settled, 1948 to Y-2"
FIXED = "Fixed 1948-2025 (2026: 1948-2024)"


def era(year: int) -> str:
    """Periods that differ in CPC version (V1.0 retrospective through 2006, real-time after) and,
    for 2026, in NCEI data vintage (the DST's 2026 values predate the current nClimGrid file)."""
    if year <= 2006:
        return "1951-2006"
    if year <= 2025:
        return "2007-2025"
    return "2026"


def load_monthly(path):
    m = pd.read_parquet(path)
    m["precip_mm"] = m["precip_in"].astype("float64") * MM_PER_INCH
    return m


def load_adm():
    """As-settled ADM final grid indexes (other workstream's cache), or None."""
    hist = RAW / "prf_actuarial" / "adm_final_index_history.csv"
    if hist.exists():
        h = pd.read_csv(hist).rename(columns={"crop_year": "year"})
        src = "ADM A00810 Final Index Value, crop years 2021-2026 (data/raw/prf_actuarial cache)"
    else:
        p = PROCESSED / "prf_actuarial_study_grids.csv"
        if not p.exists():
            return None, None
        h = (pd.read_csv(p).dropna(subset=["final_index_adm"])
             .drop_duplicates(["crop_year", "grid_id", "interval_code"])
             .rename(columns={"crop_year": "year"}))
        src = "ADM final index via data/processed/prf_actuarial_study_grids.csv (2025-2026)"
    h["grid_id"] = h["grid_id"].astype(int)
    return h[["grid_id", "year", "interval_name", "final_index_adm"]], src


def stats_table(df, ours_col, off_col, by=None):
    """comparison_stats overall or per group, as a DataFrame."""
    if by is None:
        return pd.DataFrame([comparison_stats(df[ours_col], df[off_col], COVERAGE)])
    rows = []
    for key, g in df.groupby(by, observed=True):
        st = comparison_stats(g[ours_col], g[off_col], COVERAGE)
        st.update(dict(zip(by, key)) if isinstance(key, tuple) else {by: key})
        rows.append(st)
    return pd.DataFrame(rows)


def md(df, floatfmt=".3f"):
    """Small Markdown table writer (no tabulate dependency)."""
    cols = list(df.columns)
    out = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            if isinstance(v, (float, np.floating)):
                cells.append(format(v, floatfmt) if np.isfinite(v) else "")
            else:
                cells.append(str(v))
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


def payment_factor(index, coverage=COVERAGE):
    """PRF payment calculation factor: (trigger - final index) / trigger, floored at 0."""
    return np.clip((coverage - np.asarray(index, dtype=float)) / coverage, 0, None)


def exact_share(a, b, tol=0.051):
    a, b = np.asarray(a, float), np.asarray(b, float)
    ok = np.isfinite(a) & np.isfinite(b)
    return float(np.mean(np.abs(a[ok] - b[ok]) <= tol))


def main():
    summary = []

    def note(section, metric, value, units="", detail=""):
        summary.append({"section": section, "metric": metric, "value": value, "units": units,
                        "detail": detail})

    study = pd.read_csv(PROCESSED / "study_grids.csv")
    study_ids = sorted(study.grid_id.unique())
    lab = study.groupby("grid_id").apply(
        lambda g: "/".join(f"{s} {r}" for s, r in zip(g.site, g.role)), include_groups=False)
    off_path = PROCESSED / "prf_official_index_ring100.parquet"
    dst = (pd.read_parquet(off_path) if off_path.exists()
           else pd.read_csv(PROCESSED / "prf_official_index.csv"))
    dst["interval_name"] = dst["interval_name"].astype(str)
    dst = dst[KEY + ["interval_code", "index_value", "interval_precip_mm", "expected_precip_mm"]]
    adm, adm_src = load_adm()

    # ---- 0. The DST's own numbers obey index = measurement / mean(1951..base_end) --------------
    chk = compute_index(dst, "interval_precip_mm", base_start=1951, base_end=dst_base_end,
                        round_to=1)
    d_exp = (chk["expected_interval_precip_mm"] - chk["expected_precip_mm"]).abs()
    d_idx = (chk["index_value"] - dst["index_value"]).abs()
    note("dst_formula", "DST rows checked", len(chk), "grid-interval-years",
         f"{dst.grid_id.nunique()} grids")
    note("dst_formula", "max |expected recomputed - DST expected|", d_exp.max(), "mm",
         "expected = mean(1951..2025) for years<=2025, mean(1951..2024) for 2026")
    note("dst_formula", "share of DST index values reproduced to 0.1", float((d_idx < 0.051).mean()),
         "share")
    print(f"DST formula check on {len(chk)} rows: max expected diff {d_exp.max():.2e} mm; index "
          f"reproduced to 0.1 in {(d_idx < 0.051).mean():.4%} of rows (max diff {d_idx.max():.2f})")

    # ---- 1. CPC rebuild and base-period choice -------------------------------------------------
    cpc_m = load_monthly(PROCESSED / "cpc_monthly_precip_grids.parquet")
    cpc_iv = interval_totals(cpc_m, "precip_mm")
    print(f"CPC: {cpc_iv.grid_id.nunique()} cells, {len(cpc_iv)} interval rows, "
          f"{cpc_iv.year.min()}-{cpc_iv.year.max()}; sources "
          f"{cpc_m.groupby('source', observed=True).year.agg(['min', 'max']).to_dict('index')}")

    cand = {}
    sub_iv = cpc_iv[cpc_iv.grid_id.isin(study_ids)]
    for label, (start, end, min_n) in CPC_CANDIDATES.items():
        cand[label] = compute_index(sub_iv, "interval_precip_mm", base_start=start, base_end=end,
                                    min_base_years=min_n, round_to=1).set_index(KEY)["index_value"]
    for ref_name, ref, ref_col in (("ADM as-settled 2021-2026", adm, "final_index_adm"),
                                   ("DST (NCEI-based) 1970-2026", dst, "index_value")):
        if ref is None:
            continue
        common = ref[ref.grid_id.isin(study_ids) & (ref.year >= 1970)].set_index(KEY)[[ref_col]]
        for label, s in cand.items():
            common = common.join(s.rename(label), how="left")
        common = common.dropna()
        rows = []
        for label in cand:
            st = comparison_stats(common[label], common[ref_col], COVERAGE)
            st["exact_0.1"] = exact_share(common[label], common[ref_col])
            st["candidate"] = label
            rows.append(st)
            note(f"cpc_base_vs_{ref_name.split()[0].lower()}", f"MAE: {label}", st["mae"],
                 "index points", f"n={st['n']}, r={st['r']:.4f}, exact to 0.1 "
                 f"{st['exact_0.1']:.3f}, trigger disagreement {st['trigger_disagree']:.3f}")
        t = pd.DataFrame(rows)[["candidate", "n", "r", "mae", "exact_0.1", "trigger_disagree"]]
        print(f"\n### CPC base-period candidates vs {ref_name} (study grids)\n")
        print(md(t))

    settled = compute_index(cpc_iv, "interval_precip_mm", *CPC_CANDIDATES[AS_SETTLED][:2],
                            min_base_years=CPC_CANDIDATES[AS_SETTLED][2])
    fixed = compute_index(cpc_iv, "interval_precip_mm", *CPC_CANDIDATES[FIXED][:2])
    cpc_idx = settled.rename(columns={"index_value": "cpc_settled"})
    cpc_idx["cpc_fixed"] = fixed["index_value"]
    pd.DataFrame({
        "grid_id": cpc_idx.grid_id.astype("int32"), "year": cpc_idx.year.astype("int16"),
        "interval_name": cpc_idx.interval_name.astype("category"),
        "interval_code": cpc_idx.interval_code.astype("int16"),
        "interval_precip_in": (cpc_idx.interval_precip_mm / MM_PER_INCH).round(4).astype("float32"),
        "expected_precip_in": (cpc_idx.expected_interval_precip_mm / MM_PER_INCH).round(4).astype("float32"),
        "index_value_ours": cpc_idx.cpc_settled.round(1).astype("float32"),
        "index_value_fixed_base": cpc_idx.cpc_fixed.round(1).astype("float32"),
    }).to_parquet(PROCESSED / "cpc_interval_index.parquet", index=False)
    print(f"\nWrote cpc_interval_index.parquet ({len(cpc_idx)} rows)")

    # ---- 2. NCEI rebuild -----------------------------------------------------------------------
    ncei_path = PROCESSED / "ncei_monthly_precip_grids.parquet"
    ncei_idx = None
    if ncei_path.exists():
        ncei_iv = interval_totals(load_monthly(ncei_path), "precip_mm")
        ncei_idx = compute_index(ncei_iv, "interval_precip_mm", base_start=1951,
                                 base_end=dst_base_end)
        pd.DataFrame({
            "grid_id": ncei_idx.grid_id.astype("int32"), "year": ncei_idx.year.astype("int16"),
            "interval_name": ncei_idx.interval_name.astype("category"),
            "interval_code": ncei_idx.interval_code.astype("int16"),
            "interval_precip_in": (ncei_idx.interval_precip_mm / MM_PER_INCH).round(4).astype("float32"),
            "expected_precip_in": (ncei_idx.expected_interval_precip_mm / MM_PER_INCH).round(4).astype("float32"),
            "index_value_ours": ncei_idx.index_value.round(1).astype("float32"),
        }).to_parquet(PROCESSED / "ncei_interval_index.parquet", index=False)
        print(f"Wrote ncei_interval_index.parquet ({len(ncei_idx)} rows)")

    # One wide comparison frame over every grid with DST values
    wide = dst.merge(cpc_idx[KEY + ["interval_precip_mm", "cpc_settled", "cpc_fixed"]].rename(
        columns={"interval_precip_mm": "cpc_precip_mm"}), on=KEY, how="left")
    for c in ("cpc_settled", "cpc_fixed"):
        wide[c] = wide[c].round(1)
    if ncei_idx is not None:
        wide = wide.merge(ncei_idx[KEY + ["interval_precip_mm", "index_value"]].rename(
            columns={"interval_precip_mm": "ncei_precip_mm", "index_value": "ncei"}),
            on=KEY, how="left")
        wide["ncei"] = wide["ncei"].round(1)
    wide["era"] = wide["year"].map(era)
    study_w = wide[wide.grid_id.isin(study_ids)].copy()
    study_w["grid_label"] = study_w.grid_id.map(lab)

    # ---- 3. Reference A: ADM as-settled ---------------------------------------------------------
    adm_w = None
    if adm is not None:
        adm_w = adm.merge(wide.drop(columns=["interval_code"]), on=KEY, how="left")
        adm_w["grid_label"] = adm_w.grid_id.map(lab)
        print(f"\n### Reference A: {adm_src}; {adm_w.grid_id.nunique()} grids, {len(adm_w)} rows\n")
        cols = [("cpc_settled", "our CPC rebuild, as-settled rule"),
                ("index_value", "DST value shown today")]
        if ncei_idx is not None:
            cols.append(("ncei", "our NCEI rebuild"))
        rows = []
        for col, name in cols:
            for yr, g in [("all", adm_w)] + list(adm_w.groupby("year")):
                st = comparison_stats(g[col], g["final_index_adm"], COVERAGE)
                rows.append({"compared with ADM": name, "year": yr, "n": st["n"], "r": st["r"],
                             "mae": st["mae"], "max_abs": float(np.nanmax(np.abs(g[col] - g.final_index_adm))),
                             "exact_0.1": exact_share(g[col], g.final_index_adm),
                             "trigger_disagree_n": int(np.nansum((g[col] < COVERAGE)
                                                                 != (g.final_index_adm < COVERAGE)))})
                note(f"adm_vs_{col}", f"{yr}", st["mae"], "index points MAE",
                     f"n={st['n']}, r={st['r']:.4f}, exact {rows[-1]['exact_0.1']:.3f}, "
                     f"max {rows[-1]['max_abs']:.2f}, trigger disagreements {rows[-1]['trigger_disagree_n']}")
        print(md(pd.DataFrame(rows)))

    # ---- 4. Reference B: DST values ------------------------------------------------------------
    sections = [("cpc_fixed", "CPC rebuild (fixed 1948-2025 base)")]
    if ncei_idx is not None:
        sections.insert(0, ("ncei", "NCEI rebuild (DST rule)"))
    for col, name in sections:
        ov = stats_table(study_w, col, "index_value")
        print(f"\n### {name} vs DST, 16 study grids, 1951-2026\n")
        print(md(ov[["n", "r", "mae", "bias", "trigger_disagree", "official_trigger_rate",
                     "ours_trigger_rate"]]))
        for m in ("n", "r", "mae", "bias", "trigger_disagree", "official_trigger_rate",
                  "ours_trigger_rate"):
            note(f"dst_vs_{col}_study", m, float(ov.iloc[0][m]),
                 "index points" if m in ("mae", "bias") else "")
        by_era = stats_table(study_w, col, "index_value", by="era")
        print(f"\n#### {name} vs DST by period\n")
        print(md(by_era[["era", "n", "r", "mae", "bias", "trigger_disagree"]]))
        for _, r in by_era.iterrows():
            note(f"dst_vs_{col}_by_era", f"MAE {r['era']}", r["mae"], "index points",
                 f"n={r['n']}, r={r['r']:.3f}, trigger disagreement {r['trigger_disagree']:.3f}")
        by_grid = stats_table(study_w, col, "index_value", by=["grid_id", "grid_label"])
        print(f"\n#### {name} vs DST by study grid\n")
        print(md(by_grid[["grid_label", "grid_id", "n", "r", "mae", "bias", "trigger_disagree"]]))
        for _, r in by_grid.iterrows():
            note(f"dst_vs_{col}_by_grid", f"MAE grid {r['grid_id']} ({r['grid_label']})",
                 r["mae"], "index points",
                 f"r={r['r']:.3f}, trigger disagreement {r['trigger_disagree']:.3f}")
        ring = stats_table(wide, col, "index_value")
        print(f"\n#### {name} vs DST, all {wide.grid_id.nunique()} grids (study + 100-mile rings)\n")
        print(md(ring[["n", "r", "mae", "bias", "trigger_disagree"]]))
        for m in ("n", "r", "mae", "bias", "trigger_disagree"):
            note(f"dst_vs_{col}_ring", m, float(ring.iloc[0][m]),
                 "index points" if m in ("mae", "bias") else "", f"{wide.grid_id.nunique()} grids")

    # interval precipitation (mm), before indexing
    for tag, pcol in (("cpc", "cpc_precip_mm"), ("ncei", "ncei_precip_mm")):
        if pcol not in study_w:
            continue
        dmm = study_w[pcol] - study_w["interval_precip_mm"]
        rel = dmm.abs() / study_w["interval_precip_mm"].replace(0, np.nan)
        note(f"{tag}_precip_vs_dst", "MAE interval precipitation, study grids",
             float(dmm.abs().mean()), "mm")
        note(f"{tag}_precip_vs_dst", "median |relative difference|, study grids",
             float(rel.median()), "share")
        note(f"{tag}_precip_vs_dst", "share within 0.05 mm, study grids",
             float((dmm.abs() <= 0.05).mean()), "share")
        print(f"{tag}: interval precip vs DST: MAE {dmm.abs().mean():.2f} mm, median |rel| "
              f"{rel.median():.3%}, within 0.05 mm {(dmm.abs() <= 0.05).mean():.2%}")

    if ncei_idx is not None:
        res = study_w.assign(d=(study_w.ncei_precip_mm - study_w.interval_precip_mm).abs())
        worst = res.groupby("year").d.agg(["mean", "max"]).sort_values("mean", ascending=False).head(4)
        print("\nNCEI-vs-DST precip residual by year (largest 4, mm):\n", worst.round(3).to_string())
        for y, r in worst.iterrows():
            note("ncei_precip_by_year", f"mean |diff| {y}", float(r["mean"]), "mm",
                 f"max {r['max']:.2f} mm")
        y26 = study_w[study_w.year == 2026]
        rows = []
        for _, g in y26.groupby("interval_code"):
            r = {"interval": g.interval_name.iloc[0], "n_grids": len(g),
                 "dst_mean_index": g.index_value.mean(),
                 "ncei_now_mae_pts": np.mean(np.abs(g.ncei - g.index_value)),
                 "ncei_now_mae_mm": np.mean(np.abs(g.ncei_precip_mm - g.interval_precip_mm))}
            rows.append(r)
            note("dst_2026_vintage", f"{r['interval']} current-nClimGrid MAE", r["ncei_now_mae_pts"],
                 "index points", f"{r['ncei_now_mae_mm']:.2f} mm")
        print("\n#### 2026 DST values vs current nClimGrid, by interval (16 study grids)\n")
        print(md(pd.DataFrame(rows)))

    # payment factor at 90% coverage: CPC-based vs NCEI-based index, same grids and years
    for scope, frame in (("study", study_w), ("ring", wide)):
        f = frame.dropna(subset=["cpc_fixed", "index_value"])
        pf_dst, pf_cpc = payment_factor(f["index_value"]), payment_factor(f["cpc_fixed"])
        where = "16 study grids" if scope == "study" else f"{f.grid_id.nunique()} grids"
        note(f"payment_factor_{scope}", "mean payment factor at 90%, DST (NCEI)", float(pf_dst.mean()),
             "share of protection", f"{where}, all intervals, 1951-2026")
        note(f"payment_factor_{scope}", "mean payment factor at 90%, CPC fixed base",
             float(pf_cpc.mean()), "share of protection", where)
        note(f"payment_factor_{scope}", "ratio CPC / NCEI", float(pf_cpc.mean() / pf_dst.mean()), "", where)
        note(f"payment_factor_{scope}", "mean |difference|", float(np.mean(np.abs(pf_cpc - pf_dst))),
             "share of protection", where)
        print(f"payment factor at 90% ({where}): NCEI/DST {pf_dst.mean():.4f}, CPC {pf_cpc.mean():.4f}"
              f" (ratio {pf_cpc.mean() / pf_dst.mean():.3f}), mean |diff| {np.mean(np.abs(pf_cpc - pf_dst)):.4f}")

    # CPC real-time (PSL RT daily file) vs CPC UPDATED (our 2025 months) on the 150-mile cells
    rt_file = RAW / "cpc" / "daily" / "precip.V1.0.2025.nc"
    if rt_file.exists():
        import xarray as xr
        with xr.open_dataset(rt_file) as ds:
            mon = ds.precip.resample(time="MS").sum(skipna=False).load()
        upd = cpc_m[cpc_m.year == 2025]
        rr, cc = zip(*[grid_id_to_rowcol(g) for g in upd.grid_id])
        rt_vals = mon.values[upd.month.to_numpy() - 1, np.array(rr), np.array(cc)]
        dmm = np.abs(rt_vals - upd.precip_mm.to_numpy())
        ok = np.isfinite(dmm)
        note("cpc_rt_vs_updated_2025", "monthly MAE, |RT - UPDATED|", float(dmm[ok].mean()), "mm",
             f"{upd.grid_id.nunique()} cells x 12 months of 2025")
        note("cpc_rt_vs_updated_2025", "share of cell-months within 1 mm", float((dmm[ok] <= 1).mean()),
             "share")
        note("cpc_rt_vs_updated_2025", "max |RT - UPDATED|", float(dmm[ok].max()), "mm")
        print(f"CPC 2025 RT vs UPDATED monthly totals: MAE {dmm[ok].mean():.2f} mm, "
              f"{(dmm[ok] <= 1).mean():.1%} of cell-months within 1 mm, max {dmm[ok].max():.1f} mm")
        if adm is not None:
            # Which CPC vintage did RMA settle 2025 on? Swap our UPDATED 2025 months for RT.
            rt_m = cpc_m[cpc_m.grid_id.isin(adm.grid_id.unique())].copy()
            sel = (rt_m.year == 2025).to_numpy()
            rr, cc = zip(*[grid_id_to_rowcol(g) for g in rt_m.loc[sel, "grid_id"]])
            rt_m.loc[sel, "precip_mm"] = mon.values[rt_m.loc[sel, "month"].to_numpy() - 1,
                                                    np.array(rr), np.array(cc)]
            for vlabel, frame in (("UPDATED", cpc_m[cpc_m.grid_id.isin(adm.grid_id.unique())]),
                                  ("RT", rt_m)):
                x = compute_index(interval_totals(frame, "precip_mm"), "interval_precip_mm", 1948,
                                  handbook_base_end, round_to=1)
                j = adm[adm.year == 2025].merge(x[KEY + ["index_value"]], on=KEY)
                dd = (j.index_value - j.final_index_adm).abs()
                note("adm_2025_by_cpc_vintage", f"MAE using CPC {vlabel} for 2025 months",
                     float(dd.mean()), "index points",
                     f"n={len(j)}, exact {np.mean(dd <= 0.051):.3f}, max {dd.max():.2f}")
                print(f"ADM 2025 with CPC {vlabel}: MAE {dd.mean():.3f}, exact "
                      f"{np.mean(dd <= 0.051):.3f}, max {dd.max():.2f}")

    # spread of the two indexes and size of the gap before/after 1990
    both = wide.dropna(subset=["cpc_fixed", "index_value"])
    note("index_spread", "std of index, DST (NCEI)", float(both.index_value.std()), "index points",
         f"{both.grid_id.nunique()} grids, 1951-2026")
    note("index_spread", "std of index, CPC fixed base", float(both.cpc_fixed.std()), "index points")
    note("index_spread", "mean shortfall below 90 when triggered, DST",
         float((COVERAGE - both.index_value[both.index_value < COVERAGE]).mean()), "index points")
    note("index_spread", "mean shortfall below 90 when triggered, CPC",
         float((COVERAGE - both.cpc_fixed[both.cpc_fixed < COVERAGE]).mean()), "index points")
    gap = (study_w.cpc_fixed - study_w.index_value).abs()
    for lo, hi in ((1951, 1989), (1990, 2025)):
        sel = (study_w.year >= lo) & (study_w.year <= hi)
        note("dst_vs_cpc_fixed_by_era", f"MAE {lo}-{hi}", float(gap[sel].mean()), "index points",
             "16 study grids")

    pd.DataFrame(summary).to_csv(PROCESSED / "b1_index_validation_summary.csv", index=False)
    print(f"\nWrote {PROCESSED / 'b1_index_validation_summary.csv'} ({len(summary)} metrics)")

    # ---- 5. Figures ----------------------------------------------------------------------------
    plt.rcParams.update({"font.size": 9, "axes.edgecolor": MUTED, "axes.labelcolor": INK,
                         "xtick.color": MUTED, "ytick.color": MUTED, "axes.titlesize": 9.5})
    panels = []
    if adm_w is not None:
        panels.append((adm_w, "final_index_adm", "cpc_settled", BLUE, "o", 14,
                       "(a) What RMA paid on: ADM final index\nvs our CPC rebuild (1948 to Y-2 base)",
                       "As-settled final grid index (ADM, 2021-2026)"))
    if ncei_idx is not None:
        panels.append((study_w, "index_value", "ncei", ORANGE, "s", 6,
                       "(b) What the DST shows now: DST value\nvs our NCEI nClimGrid rebuild",
                       "DST historical index (2026-10-29), 1951-2026"))
    panels.append((study_w, "index_value", "cpc_fixed", AQUA, "^", 6,
                   "(c) Data-source gap: DST (NCEI) value\nvs our CPC rebuild (fixed base)",
                   "DST historical index (2026-10-29), 1951-2026"))
    fig, axes = plt.subplots(1, len(panels), figsize=(4.6 * len(panels), 4.9), squeeze=False)
    for ax, (frame, xcol, ycol, color, marker, size, title, xlabel) in zip(axes[0], panels):
        ok = frame[[xcol, ycol]].dropna()
        st = comparison_stats(ok[ycol], ok[xcol], COVERAGE)
        ax.scatter(ok[xcol], ok[ycol], s=size, alpha=0.4, color=color, marker=marker,
                   linewidths=0, rasterized=True)
        lim = (0, 400)
        ax.plot(lim, lim, color=INK, lw=1.0, ls="--", label="1:1 line")
        ax.axvline(COVERAGE, color=MUTED, lw=0.8, ls=":")
        ax.axhline(COVERAGE, color=MUTED, lw=0.8, ls=":", label="90% coverage trigger")
        ax.set_xlim(lim)
        ax.set_ylim(lim)
        ax.set_aspect("equal")
        ax.grid(color=GRID, lw=0.5)
        ax.set_xlabel(f"{xlabel}, index points")
        ax.set_ylabel("Our rebuilt index, index points")
        ax.set_title(title, color=INK)
        mae_txt = f"{st['mae']:.3f}" if st["mae"] < 0.1 else f"{st['mae']:.2f}"
        ax.text(0.03, 0.97, f"n = {st['n']:,}\nr = {st['r']:.3f}\nMAE = {mae_txt} pts\n"
                f"trigger disagreement = {st['trigger_disagree']:.1%}", transform=ax.transAxes,
                va="top", ha="left", color=INK, bbox=dict(boxstyle="round", fc="white", ec=GRID))
        ax.legend(loc="lower right", frameon=False, fontsize=8)
    fig.suptitle("PRF grid index: our rebuilds vs RMA's two official sources, study grids, "
                 "all 11 intervals", color=INK)
    fig.tight_layout()
    fig.savefig(FIGURES / "b1_index_validation_scatter.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.5, 3.8))
    yr = study_w.groupby("year").apply(lambda g: pd.Series({
        "cpc": np.nanmean(np.abs(g.cpc_fixed - g.index_value)),
        "ncei": np.nanmean(np.abs(g.ncei - g.index_value)) if "ncei" in g else np.nan}),
        include_groups=False)
    ax.plot(yr.index, yr["cpc"], color=AQUA, lw=2, marker="^", ms=4,
            label="CPC rebuild vs DST (data-source gap)")
    if ncei_idx is not None:
        ax.plot(yr.index, yr["ncei"], color=ORANGE, lw=2, ls="--", marker="s", ms=4,
                label="NCEI rebuild vs DST")
    if adm_w is not None:
        ya = adm_w.groupby("year").apply(lambda g: np.nanmean(np.abs(g.cpc_settled - g.final_index_adm)),
                                         include_groups=False)
        ax.plot(ya.index, ya.values, color=BLUE, lw=0, marker="o", ms=6,
                label="CPC rebuild (as-settled rule) vs ADM")
    ax.axvspan(2006.5, 2026.5, color=GRID, alpha=0.4, lw=0)
    top = ax.get_ylim()[1]
    ax.text(1978, top * 0.93, "CPC V1.0 (retrospective) years", ha="center", color=MUTED)
    ax.text(2016.5, top * 0.93, "CPC real-time years", ha="center", color=MUTED)
    ax.set_xlabel("Year")
    ax.set_ylabel("Mean |rebuilt - official|, index points")
    ax.set_title("Rebuild error by year, study grids x 11 intervals", color=INK)
    ax.grid(color=GRID, lw=0.5)
    ax.legend(frameon=False, loc="upper left", bbox_to_anchor=(0.0, 0.88))
    fig.tight_layout()
    fig.savefig(FIGURES / "b1_cpc_vs_official_by_year.png", dpi=150)
    plt.close(fig)
    print(f"Wrote figures to {FIGURES}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
