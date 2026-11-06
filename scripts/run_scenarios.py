"""Run the representative-farm PRF scenarios: premiums, payouts, and uncovered losses, 1951-2025.

Run from the repo root:
    python scripts/run_scenarios.py                       # real inputs (data/scenarios/farms.yaml)
    python scripts/run_scenarios.py --farms tests/fixtures/b4/farms_provisional.yaml   # smoke test

Inputs
  farms.yaml                 data/scenarios/farms.yaml (top-level key `farms`, a list of dicts with
                             farm_id, site, county, fips, lat, lon, intended_use, irrigation_practice,
                             organic, insured_acres, productivity_factor, coverage_level,
                             interval_allocation {interval name: fraction},
                             county_base_value_usd_per_acre, expected_production, expected_value_usd_per_acre,
                             rain_sensitivity_ref, rationale, sources; optional grid_id, share)
  official grid indices      data/processed/prf_official_index.csv (grid_id, year, interval_name,
                             interval_code, index_value on the 100 = normal scale)
  actuarial data             data/processed/prf_actuarial_study_grids.csv (scripts/pull_prf_actuarial.py)
  rainfall sensitivity       data/processed/crop_rain_sensitivity_other.csv, optional; the row whose
                             row_key equals the farm's rain_sensitivity_ref supplies an elasticity

Method (per farm, per year)
  * The farm's election (coverage level, productivity factor, acres, interval allocation, intended
    use, practice) is validated with agri_hedge.prf.validate_election against the actuarial
    min/max percent of value and the intervals offered for its grid.
  * Premium rates and county base value are those of one rate year (default crop year 2026, the
    latest complete actuarial filing) and are held fixed across all historical years: "what would
    a 2026 policy have paid in each past year". This is how RMA's Decision Support Tool presents
    history too.
  * Indemnity per interval = payment calculation factor x policy protection ("official" rounding:
    the handbook Exhibit 5 / ADM payment-factor convention), using the official final grid index.
  * net_to_producer = total indemnity - producer-paid premium.
  * Forage loss proxy (ASSUMPTION, stated in the results doc):
        weighted_index  W = sum over selected intervals of (percent of value x final grid index)
        forage_loss     = value_per_acre x insured acres x max(0, 1 - W/100) x elasticity
    value_per_acre is the farm's expected_value_usd_per_acre (fallback: county base value x
    productivity factor); elasticity comes from crop_rain_sensitivity_other.csv if available,
    else 1.0 (forage value falls one-for-one with seasonal rainfall shortfall).
        uncovered_loss  = forage_loss - indemnity   (negative = indemnity exceeded the proxy loss)
    Three sensitivity proxies: "no-offset" caps each interval index at 100 before weighting, so a
    wet interval cannot cancel a dry one; "season-span" uses the rainfall over the whole span of
    months from the first to the last insured month (precipitation-weighted), which also counts
    dry months that fall between the insured intervals; "cbvpf" values forage at county base
    value x productivity factor (the PRF protection basis) instead of the farm's own value.
  * Farm-independent grid analysis: premium rate vs historical burn per grid x interval, and the
    official ADM final indices vs the index file (index-vintage check).

Outputs
  data/processed/prf_scenario_results.csv   one row per farm x year
  docs/figures/b4_*.png                     figures
  docs/analysis/04b_farm_scenario_results.md  the block between the AUTO markers is regenerated
With a non-default --farms file (e.g. the provisional fixture) outputs go to
data/raw/prf_scenarios_provisional/ instead, so test inputs never overwrite real results.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import yaml  # noqa: E402

from agri_hedge.config import DOCS, FIGURES, PROCESSED, RAW, ROOT, SCENARIOS  # noqa: E402
from agri_hedge.prf import (  # noqa: E402
    PRFElection,
    PRFElectionError,
    simulate_years,
    summarize_years,
    validate_election,
)
from agri_hedge.loss_model import (  # noqa: E402  (shared with the rain-to-loss model, doc 13)
    elasticity_for,
    forage_loss_proxy,
    load_farms,
    weighted_index,
)
from agri_hedge.prf_grid import latlon_to_grid_id  # noqa: E402
from agri_hedge.prf_intervals import INTERVAL_MONTHS, INTERVAL_NAMES  # noqa: E402

DEFAULT_FARMS = SCENARIOS / "farms.yaml"
INDEX_CSV = PROCESSED / "prf_official_index.csv"
ACT_CSV = PROCESSED / "prf_actuarial_study_grids.csv"
SENS_CSV = PROCESSED / "crop_rain_sensitivity_other.csv"
OUT_CSV = PROCESSED / "prf_scenario_results.csv"
DOC = DOCS / "analysis" / "04b_farm_scenario_results.md"
PROVISIONAL_DIR = RAW / "prf_scenarios_provisional"
HEADLINE = (2015, 2025)
LAST_YEAR = 2025
AUTO_BEGIN = "<!-- BEGIN AUTO: farm results (scripts/run_scenarios.py) -->"
AUTO_END = "<!-- END AUTO: farm results -->"
AUTO_GRID_BEGIN = "<!-- BEGIN AUTO: grid analysis (scripts/run_scenarios.py) -->"
AUTO_GRID_END = "<!-- END AUTO: grid analysis -->"

# Categorical slots 1-3 of the project's reference palette (validated colorblind-safe).
C_BLUE, C_ORANGE, C_AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, GRID = "#0b0b0b", "#52514e", "#d9d8d4"


# ---------------------------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------------------------

def load_index(path: Path = INDEX_CSV) -> pd.DataFrame:
    """Official final grid indices, on the 100 scale (fractions are converted)."""
    idx = pd.read_csv(path, dtype={"grid_id": str})
    if idx["index_value"].median() < 5:  # given as fraction of normal
        idx["index_value"] = idx["index_value"] * 100
    return idx


def index_wide(idx: pd.DataFrame, grid_id: str, col: str = "index_value") -> pd.DataFrame:
    """Year x interval-name table for one grid (complete years up to LAST_YEAR)."""
    g = idx[(idx["grid_id"] == str(grid_id)) & (idx["year"] <= LAST_YEAR)]
    if g.empty:
        raise LookupError(f"grid {grid_id} not in the official index file")
    w = g.pivot_table(index="year", columns="interval_name", values=col, aggfunc="first")
    return w.reindex(columns=INTERVAL_NAMES)


def _get(farm: dict, *keys, default=None):
    for k in keys:
        if k in farm and farm[k] not in (None, ""):
            return farm[k]
    return default


def farm_grid_id(farm: dict) -> str:
    gid = _get(farm, "grid_id")
    if gid is not None:
        return str(gid)
    return str(latlon_to_grid_id(float(farm["lat"]), float(farm["lon"])))


def actuarial_for_farm(farm: dict, act: pd.DataFrame, election: PRFElection, rate_year: int) -> dict:
    """Rates, county base value, min/max percent of value for the farm's grid, county, use, practice."""
    gid = farm_grid_id(farm)
    sel = act[(act["crop_year"] == rate_year) & (act["grid_id"] == gid)
              & (act["intended_use"] == election.intended_use)
              & (act["irrigation_practice"] == election.irrigation_practice)
              & (act["organic_practice"] == election.organic_practice)
              & (np.isclose(act["coverage_level"], election.coverage_level))]
    if sel.empty:
        raise LookupError(f"no {rate_year} actuarial rows for grid {gid} / {election.intended_use} / "
                          f"{election.irrigation_practice} / {election.organic_practice} / {election.coverage_level}")
    fips = str(_get(farm, "fips", "county_fips", default="")).zfill(5)
    note = ""
    if fips in set(sel["county_fips"]):
        sel = sel[sel["county_fips"] == fips]
    else:
        first = sel["county_fips"].iloc[0]
        note = f"county {fips} not in actuarial file for grid {gid}; used {first} (grid rates are county-invariant)"
        sel = sel[sel["county_fips"] == first]
    sel = sel.drop_duplicates("interval_name").set_index("interval_name")
    return {
        "grid_id": gid,
        "county_fips": sel["county_fips"].iloc[0],
        "rates": sel["premium_rate"].to_dict(),
        "cbv": float(sel["county_base_value_usd_per_acre"].iloc[0]),
        "min_pov": sel["min_percent_of_value"].to_dict(),
        "max_pov": sel["max_percent_of_value"].to_dict(),
        "available": list(sel.index),
        "note": note,
    }


def build_election(farm: dict, cbv: float | None = None) -> PRFElection:
    irr = _get(farm, "irrigation_practice", default=None)
    use = str(_get(farm, "intended_use", default="grazing")).lower()
    if use == "grazing" and (irr is None or str(irr).lower() in ("non-irrigated", "nonirrigated", "none", "n/a", "na", "not specified")):
        irr = "not specified"  # grazing is offered only with no irrigation practice specified
    return PRFElection(
        grid_id=farm_grid_id(farm),
        county_base_value=cbv if cbv is not None else float(_get(farm, "county_base_value_usd_per_acre", default=np.nan)),
        coverage_level=_get(farm, "coverage_level"),
        productivity_factor=_get(farm, "productivity_factor", default=1.0),
        insured_acres=float(_get(farm, "insured_acres")),
        allocation=_get(farm, "interval_allocation"),
        intended_use=use,
        irrigation_practice=irr,
        organic_practice=_get(farm, "organic", "organic_practice", default="not organic"),
        share=_get(farm, "share", "insurable_interest", default=1.0),
        county_fips=str(_get(farm, "fips", default="")),
        label=str(_get(farm, "farm_id")),
    )


# ---------------------------------------------------------------------------------------------
# Scenario arithmetic
# ---------------------------------------------------------------------------------------------

def span_intervals(allocation: dict) -> list[str]:
    """All intervals lying inside the span from the first to the last insured month."""
    months = [m for k, v in allocation.items() if v > 0 for m in INTERVAL_MONTHS[k]]
    lo, hi = min(months), max(months)
    return [k for k in INTERVAL_NAMES if INTERVAL_MONTHS[k][0] >= lo and INTERVAL_MONTHS[k][1] <= hi]


def span_index(precip: pd.DataFrame | None, expected: pd.DataFrame | None, index_by_year: pd.DataFrame,
               allocation: dict) -> pd.Series:
    """Season-span index: 100 x total precipitation / total expected precipitation over span intervals.

    Falls back to the mean of the span intervals' indices if precipitation columns are absent.
    """
    names = span_intervals(allocation)
    if precip is not None and expected is not None:
        num = precip[names].sum(axis=1, min_count=len(names))
        den = expected[names].sum(axis=1, min_count=len(names))
        return (100 * num / den).rename("span_index")
    return index_by_year[names].mean(axis=1).rename("span_index")


def run_farm(farm: dict, idx: pd.DataFrame, act: pd.DataFrame, sens: pd.DataFrame | None,
             rate_year: int) -> tuple[pd.DataFrame, dict]:
    """All years for one farm. Returns (per-year frame, farm metadata)."""
    e0 = build_election(farm)
    a = actuarial_for_farm(farm, act, e0, rate_year)
    yaml_cbv = _get(farm, "county_base_value_usd_per_acre")
    e = build_election(farm, cbv=a["cbv"])
    validate_election(e, max_percent_of_value=a["max_pov"], min_percent_of_value=a["min_pov"],
                      available_intervals=a["available"])
    iw = index_wide(idx, a["grid_id"])
    has_precip = {"interval_precip_mm", "expected_precip_mm"} <= set(idx.columns)
    pw = index_wide(idx, a["grid_id"], "interval_precip_mm") if has_precip else None
    ew = index_wide(idx, a["grid_id"], "expected_precip_mm") if has_precip else None
    long = simulate_years(e, a["rates"], iw, rounding="official", validate=False)
    yr = summarize_years(long)
    ow = official_index_wide(a["grid_id"], act)
    if ow is not None:
        paid = summarize_years(simulate_years(e, a["rates"], ow, rounding="official", validate=False))
        as_paid = paid["indemnity"].where(paid["n_intervals_missing"] == 0).reindex(yr.index)
    else:
        as_paid = pd.Series(np.nan, index=yr.index)
    ind_wide = long.pivot(index="year", columns="interval_name", values="indemnity")
    value_pa = float(_get(farm, "expected_value_usd_per_acre", default=a["cbv"] * e.productivity_factor))
    elast, elast_src = elasticity_for(_get(farm, "rain_sensitivity_ref"), sens)
    W = weighted_index(iw, e.allocation)
    Wc = weighted_index(iw, e.allocation, cap=100.0)
    S = span_index(pw, ew, iw, e.allocation)
    out = pd.DataFrame({
        "farm_id": e.label, "site": _get(farm, "site", default=""), "grid_id": a["grid_id"],
        "county_fips": a["county_fips"], "intended_use": e.intended_use,
        "irrigation_practice": e.irrigation_practice, "organic_practice": e.organic_practice,
        "rate_year": rate_year, "coverage_level": e.coverage_level,
        "productivity_factor": e.productivity_factor, "insured_acres": e.insured_acres,
        "county_base_value_usd_per_acre": a["cbv"], "value_per_acre_usd": value_pa,
        "elasticity": elast,
        "year": yr.index,
        "policy_protection_usd": yr["policy_protection"].to_numpy(),
        "total_premium_usd": yr["total_premium"].to_numpy(),
        "premium_subsidy_usd": yr["premium_subsidy"].to_numpy(),
        "producer_premium_usd": yr["producer_premium"].to_numpy(),
        "indemnity_usd": yr["indemnity"].to_numpy(),
        "net_to_producer_usd": yr["net_to_producer"].to_numpy(),
        "indemnity_official_adm_index_usd": as_paid.to_numpy(),
        "n_intervals_paid": yr["n_intervals_paid"].to_numpy(),
        "weighted_index": W.reindex(yr.index).to_numpy(),
        "forage_loss_usd": forage_loss_proxy(value_pa, e.insured_acres, W.reindex(yr.index), elast).to_numpy(),
        "weighted_index_capped": Wc.reindex(yr.index).to_numpy(),
        "forage_loss_nooffset_usd": forage_loss_proxy(value_pa, e.insured_acres, Wc.reindex(yr.index), elast).to_numpy(),
        "span_index": S.reindex(yr.index).to_numpy(),
        "forage_loss_span_usd": forage_loss_proxy(value_pa, e.insured_acres, S.reindex(yr.index), elast).to_numpy(),
        "forage_loss_cbvpf_usd": forage_loss_proxy(a["cbv"] * e.productivity_factor, e.insured_acres,
                                                   W.reindex(yr.index), elast).to_numpy(),
    })
    out["uncovered_loss_usd"] = out["forage_loss_usd"] - out["indemnity_usd"]
    out["uncovered_loss_nooffset_usd"] = out["forage_loss_nooffset_usd"] - out["indemnity_usd"]
    out["uncovered_loss_span_usd"] = out["forage_loss_span_usd"] - out["indemnity_usd"]
    out["uncovered_loss_cbvpf_usd"] = out["forage_loss_cbvpf_usd"] - out["indemnity_usd"]
    for k in INTERVAL_NAMES:
        out[f"index_{k}"] = iw[k].reindex(yr.index).to_numpy()
        out[f"indemnity_{k}"] = ind_wide[k].reindex(yr.index).to_numpy() if k in ind_wide else np.nan
    meta = {"farm_id": e.label, "site": out["site"].iloc[0], "grid_id": a["grid_id"],
            "county_fips": a["county_fips"], "cbv_adm": a["cbv"], "cbv_yaml": yaml_cbv,
            "allocation": e.allocation, "elasticity_source": elast_src, "note": a["note"],
            "trigger": e.trigger, "subsidy_rate": e.subsidy_rate, "value_per_acre": value_pa,
            "intended_use": e.intended_use, "coverage_level": e.coverage_level,
            "productivity_factor": e.productivity_factor, "insured_acres": e.insured_acres,
            "span_intervals": span_intervals(e.allocation)}
    return out, meta


# ---------------------------------------------------------------------------------------------
# Summaries, figures, doc
# ---------------------------------------------------------------------------------------------

def _year_span(years: pd.Series) -> str:
    return f"{int(years.min())}-{int(years.max())}" if len(years) else ""


def summarize_window(res: pd.DataFrame, start: int, end: int) -> pd.DataFrame:
    rows = []
    for fid, g in res[(res["year"] >= start) & (res["year"] <= end)].groupby("farm_id", sort=False):
        worst = g.loc[g["weighted_index"].idxmin()]
        unc = g["uncovered_loss_usd"]
        rows.append({
            "farm_id": fid, "site": g["site"].iloc[0], "grid_id": g["grid_id"].iloc[0],
            "years": f"{int(g['year'].min())}-{int(g['year'].max())}", "n_years": len(g),
            "avg_total_premium": g["total_premium_usd"].mean(),
            "avg_producer_premium": g["producer_premium_usd"].mean(),
            "avg_indemnity": g["indemnity_usd"].mean(),
            "loss_ratio": g["indemnity_usd"].sum() / g["total_premium_usd"].sum(),
            "payout_frequency": (g["indemnity_usd"] > 0).mean(),
            "avg_net_to_producer": g["net_to_producer_usd"].mean(),
            "worst_year": int(worst["year"]), "worst_weighted_index": worst["weighted_index"],
            "worst_forage_loss": worst["forage_loss_usd"], "worst_indemnity": worst["indemnity_usd"],
            "worst_uncovered": worst["uncovered_loss_usd"],
            "avg_forage_loss": g["forage_loss_usd"].mean(),
            "uncovered_mean": unc.mean(), "uncovered_median": unc.median(),
            "uncovered_p90": unc.quantile(0.9), "uncovered_max": unc.max(),
            "shortfall_mean": unc.clip(lower=0).mean(),
            "share_years_uncovered_gt0": (unc > 0.5).mean(),
            "indemnity_over_loss": g["indemnity_usd"].sum() / g["forage_loss_usd"].sum()
            if g["forage_loss_usd"].sum() > 0 else np.nan,
            "uncovered_nooffset_mean": g["uncovered_loss_nooffset_usd"].mean(),
            "uncovered_nooffset_p90": g["uncovered_loss_nooffset_usd"].quantile(0.9),
            "uncovered_span_mean": g["uncovered_loss_span_usd"].mean(),
            "uncovered_span_p90": g["uncovered_loss_span_usd"].quantile(0.9),
            "uncovered_cbvpf_mean": g["uncovered_loss_cbvpf_usd"].mean(),
            "uncovered_cbvpf_p90": g["uncovered_loss_cbvpf_usd"].quantile(0.9),
            "official_years": _year_span(g.loc[g["indemnity_official_adm_index_usd"].notna(), "year"]),
            "avg_ind_official": g["indemnity_official_adm_index_usd"].mean(),
            "avg_ind_file_same_years": g.loc[g["indemnity_official_adm_index_usd"].notna(), "indemnity_usd"].mean(),
        })
    return pd.DataFrame(rows)


def _style(ax):
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(INK2)
    ax.tick_params(colors=INK2, labelsize=8)


def make_figures(res: pd.DataFrame, figdir: Path, tag: str = "") -> list[Path]:
    figdir.mkdir(parents=True, exist_ok=True)
    farms = list(dict.fromkeys(res["farm_id"]))
    n = len(farms)
    paths = []
    suffix = " (PROVISIONAL TEST INPUT)" if tag else ""

    # Figure 1: annual indemnity vs producer premium, small multiples.
    ncol = 2 if n > 1 else 1
    nrow = int(np.ceil(n / ncol))
    height = 2.0 * nrow + 1.4
    fig, axes = plt.subplots(nrow, ncol, figsize=(10, height), sharex=True, squeeze=False)
    rate_year = int(res["rate_year"].iloc[0])
    for ax, fid in zip(axes.ravel(), farms):
        g = res[res["farm_id"] == fid]
        ax.axvspan(HEADLINE[0] - 0.5, HEADLINE[1] + 0.5, color=GRID, alpha=0.5, linewidth=0, zorder=0)
        ax.bar(g["year"], g["indemnity_usd"] / 1000, width=0.8, color=C_BLUE, label="Indemnity", zorder=2)
        ax.plot(g["year"], g["producer_premium_usd"] / 1000, color=C_ORANGE, linewidth=2,
                linestyle="--", label="Producer-paid premium", zorder=3)
        ax.plot(g["year"], g["forage_loss_usd"] / 1000, color=INK, linewidth=0, marker="o",
                markersize=2.5, label="Forage loss proxy", zorder=4)
        ax.set_title(f"{fid} (grid {g['grid_id'].iloc[0]})", fontsize=9, color=INK, loc="left")
        ax.set_ylabel("$ thousand", fontsize=8, color=INK2)
        _style(ax)
    for ax in axes.ravel()[n:]:
        ax.set_visible(False)
    for ax in axes[-1]:
        ax.set_xlabel("Year", fontsize=8, color=INK2)
    handles, labels = axes.ravel()[0].get_legend_handles_labels()
    top = 1 - 1.25 / height
    fig.subplots_adjust(left=0.07, right=0.98, bottom=0.45 / height + 0.02, top=top, hspace=0.45, wspace=0.18)
    fig.legend(handles, labels, loc="lower center", ncol=3, frameon=False, fontsize=8,
               bbox_to_anchor=(0.5, top + 0.35 / height))
    fig.suptitle(f"PRF indemnity vs producer-paid premium by year: {rate_year} rates applied to "
                 f"{int(res.year.min())}-{LAST_YEAR} grid indices{suffix}\n"
                 f"(shaded: headline window {HEADLINE[0]}-{HEADLINE[1]})", fontsize=10, color=INK,
                 y=1 - 0.08 / height)
    p = figdir / f"b4_annual_indemnity_vs_premium{tag}.png"
    fig.savefig(p, dpi=150)
    plt.close(fig)
    paths.append(p)

    # Figure 2: distribution of uncovered loss per farm ($/acre), long run vs headline window.
    fig, ax = plt.subplots(figsize=(max(6, 1.1 * n + 2), 4))
    data_lr = [(res[res.farm_id == f]["uncovered_loss_usd"] / res[res.farm_id == f]["insured_acres"]).to_numpy()
               for f in farms]
    pos = np.arange(n)
    bp = ax.boxplot(data_lr, positions=pos, widths=0.5, whis=(5, 95), showfliers=False,
                    patch_artist=True, medianprops=dict(color=INK, linewidth=1.5))
    for b in bp["boxes"]:
        b.set(facecolor="white", edgecolor=C_BLUE, linewidth=1.5, hatch="///")
    for f_i, f in enumerate(farms):
        g = res[(res.farm_id == f) & (res.year >= HEADLINE[0])]
        ax.scatter(np.full(len(g), f_i) + 0.33, g["uncovered_loss_usd"] / g["insured_acres"], s=14,
                   color=C_ORANGE, marker="D", zorder=3, label="headline years" if f_i == 0 else None)
    ax.axhline(0, color=INK2, linewidth=0.8)
    ax.set_xticks(pos, farms, rotation=20, ha="right", fontsize=8)
    ax.set_ylabel("Uncovered loss, $ per insured acre per year", fontsize=8, color=INK2)
    ax.set_title(f"Uncovered loss = forage loss proxy - PRF indemnity{suffix}\nboxes: {int(res.year.min())}-{LAST_YEAR}"
                 f" (5th-95th pct whiskers); diamonds: each year {HEADLINE[0]}-{HEADLINE[1]}; "
                 f"below 0 = indemnity exceeded the proxy loss",
                 fontsize=10, color=INK, loc="left")
    ax.legend(frameon=False, fontsize=8, loc="upper right")
    _style(ax)
    fig.tight_layout()
    p = figdir / f"b4_uncovered_loss_distribution{tag}.png"
    fig.savefig(p, dpi=150)
    plt.close(fig)
    paths.append(p)

    # Figure 3: forage loss proxy vs indemnity, per acre, all farm-years.
    fig, ax = plt.subplots(figsize=(5.5, 5))
    x = res["forage_loss_usd"] / res["insured_acres"]
    y = res["indemnity_usd"] / res["insured_acres"]
    for use, color, marker in (("haying", C_BLUE, "o"), ("grazing", C_ORANGE, "D")):
        sel = res["intended_use"] == use
        if sel.any():
            ax.scatter(x[sel], y[sel], s=10 if marker == "o" else 8, color=color, alpha=0.6, marker=marker,
                       edgecolor="none", label=f"{use} farm-year")
    lim = float(np.nanmax([x.max(), y.max(), 1])) * 1.05
    ax.plot([0, lim], [0, lim], color=INK2, linewidth=1, linestyle=":", label="indemnity = loss")
    ax.set_xlim(0, lim)
    ax.set_ylim(0, lim)
    ax.set_xlabel("Forage loss proxy, $ per insured acre", fontsize=8, color=INK2)
    ax.set_ylabel("PRF indemnity, $ per insured acre", fontsize=8, color=INK2)
    ax.set_title(f"PRF indemnity vs forage loss proxy\nall farms, {int(res.year.min())}-{LAST_YEAR}"
                 f"{suffix}", fontsize=10, color=INK, loc="left")
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    _style(ax)
    ax.grid(axis="x", color=GRID, linewidth=0.6)
    fig.tight_layout()
    p = figdir / f"b4_loss_vs_indemnity{tag}.png"
    fig.savefig(p, dpi=150)
    plt.close(fig)
    paths.append(p)
    return paths


def _fmt_money(v):
    return "" if pd.isna(v) else f"${v:,.0f}"


def _fmt_pct(v):
    return "" if pd.isna(v) else f"{100 * v:.0f}%"


def markdown_tables(meta: list[dict], head: pd.DataFrame, lr: pd.DataFrame, rate_year: int,
                    figs: list[Path], doc_dir: Path) -> str:
    out = []
    out.append(f"Generated by `scripts/run_scenarios.py` with crop-year {rate_year} rates and county base "
               f"values; indices from `data/processed/prf_official_index.csv`.\n")
    out.append("#### Farm elections\n")
    out.append("| Farm | Site | Grid | County | Use | Coverage | Prod. factor | Acres | Intervals (percent of value) | CBV $/ac (ADM) | Value $/ac (loss proxy) | Elasticity |")
    out.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for m in meta:
        alloc = ", ".join(f"{k} {100 * v:.0f}%" for k, v in m["allocation"].items() if v > 0)
        out.append(f"| {m['farm_id']} | {m['site']} | {m['grid_id']} | {m['county_fips']} | {m['intended_use']} | "
                   f"{100 * m['coverage_level']:.0f}% | {100 * m['productivity_factor']:.0f}% | {m['insured_acres']:,.0f} | "
                   f"{alloc} | {m['cbv_adm']:.2f} | {m['value_per_acre']:.2f} | {m['elasticity_source']} |")
    notes = [f"- {m['farm_id']}: {m['note']}" for m in meta if m["note"]]
    notes += [f"- {m['farm_id']}: farms.yaml county base value {m['cbv_yaml']} differs from ADM {m['cbv_adm']:.2f}; ADM used."
              for m in meta if m["cbv_yaml"] not in (None, "") and abs(float(m["cbv_yaml"]) - m["cbv_adm"]) > 0.01 * m["cbv_adm"]]
    if notes:
        out.append("\n" + "\n".join(notes))
    for title, t in ((f"Headline window {HEADLINE[0]}-{HEADLINE[1]}", head), ("Long-run window", lr)):
        out.append(f"\n#### {title}: premiums and payouts (dollars per year, whole farm)\n")
        out.append("| Farm | Years | Avg total premium | Avg producer premium | Avg indemnity | Loss ratio | Payout frequency | Avg net to producer | Worst year (W) | Worst-year loss proxy | Worst-year indemnity |")
        out.append("|---|---|---|---|---|---|---|---|---|---|---|")
        for r in t.itertuples():
            out.append(f"| {r.farm_id} | {r.years} | {_fmt_money(r.avg_total_premium)} | {_fmt_money(r.avg_producer_premium)} | "
                       f"{_fmt_money(r.avg_indemnity)} | {r.loss_ratio:.2f} | {_fmt_pct(r.payout_frequency)} | "
                       f"{_fmt_money(r.avg_net_to_producer)} | {r.worst_year} ({r.worst_weighted_index:.0f}) | "
                       f"{_fmt_money(r.worst_forage_loss)} | {_fmt_money(r.worst_indemnity)} |")
        out.append(f"\n#### {title}: uncovered loss (forage loss proxy minus indemnity, dollars per year)\n")
        out.append("| Farm | Avg loss proxy | Mean uncovered | Median | 90th pct | Max | Mean shortfall (uncovered > 0 part) | Years with uncovered > 0 | Indemnity / loss proxy | Mean / 90th pct uncovered, no-offset proxy | Mean / 90th pct uncovered, season-span proxy | Mean / 90th pct uncovered, value = CBV x PF |")
        out.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
        for r in t.itertuples():
            out.append(f"| {r.farm_id} | {_fmt_money(r.avg_forage_loss)} | {_fmt_money(r.uncovered_mean)} | "
                       f"{_fmt_money(r.uncovered_median)} | {_fmt_money(r.uncovered_p90)} | {_fmt_money(r.uncovered_max)} | "
                       f"{_fmt_money(r.shortfall_mean)} | {_fmt_pct(r.share_years_uncovered_gt0)} | "
                       f"{'' if pd.isna(r.indemnity_over_loss) else f'{r.indemnity_over_loss:.2f}'} | "
                       f"{_fmt_money(r.uncovered_nooffset_mean)} / {_fmt_money(r.uncovered_nooffset_p90)} | "
                       f"{_fmt_money(r.uncovered_span_mean)} / {_fmt_money(r.uncovered_span_p90)} | "
                       f"{_fmt_money(r.uncovered_cbvpf_mean)} / {_fmt_money(r.uncovered_cbvpf_p90)} |")
    if head["official_years"].astype(bool).any():
        out.append("\n#### As-paid check: indemnity on RMA's official ADM final indices vs on the index file (same years)\n")
        out.append("| Farm | Years | Avg indemnity, official ADM indices | Avg indemnity, prf_official_index.csv |")
        out.append("|---|---|---|---|")
        for r in head.itertuples():
            out.append(f"| {r.farm_id} | {r.official_years} | {_fmt_money(r.avg_ind_official)} | "
                       f"{_fmt_money(r.avg_ind_file_same_years)} |")
    out.append("\n#### Figures\n")
    for p in figs:
        rel = Path("..") / "figures" / p.name if p.parent == FIGURES else Path(p)
        out.append(f"![{p.stem}]({rel.as_posix()})\n")
    return "\n".join(out)


# ---------------------------------------------------------------------------------------------
# Farm-independent grid analysis (real data; runs even before farms.yaml exists)
# ---------------------------------------------------------------------------------------------

def grid_burn_table(idx: pd.DataFrame, act: pd.DataFrame, rate_year: int, coverage: float = 0.90,
                    windows=((1951, LAST_YEAR), HEADLINE)) -> pd.DataFrame:
    """Per study grid x interval: premium rate vs historical burn (mean payment factor).

    burn = mean over years of the payment calculation factor at `coverage` = expected indemnity per
    dollar of policy protection. loss_ratio = burn / premium rate (1.0 = premium equals the average
    historical payout); the producer pays (1 - subsidy) of the premium, so the producer's return
    per dollar paid is loss_ratio / (1 - subsidy).
    """
    from agri_hedge.prf import payment_calculation_factor, trigger_grid_index
    a = act[(act["crop_year"] == rate_year) & np.isclose(act["coverage_level"], coverage)
            & (act["intended_use"] == "grazing")].drop_duplicates(["site", "grid_role", "interval_name"])
    rows = []
    for r in a.itertuples():
        g = idx[(idx["grid_id"] == r.grid_id) & (idx["interval_name"] == r.interval_name)]
        rec = {"site": r.site, "grid_role": r.grid_role, "grid_id": r.grid_id, "interval_name": r.interval_name,
               "interval_code": r.interval_code, "premium_rate": r.premium_rate, "subsidy_rate": r.subsidy_rate}
        for lo, hi in windows:
            s = g[(g["year"] >= lo) & (g["year"] <= hi)]["index_value"]
            pcf = payment_calculation_factor(s.to_numpy(), trigger_grid_index(coverage))
            tag = "lr" if lo != HEADLINE[0] else "hl"
            rec[f"burn_{tag}"] = float(np.mean(pcf)) if len(pcf) else np.nan
            rec[f"freq_{tag}"] = float(np.mean(pcf > 0)) if len(pcf) else np.nan
            yrs = g[(g["year"] >= lo) & (g["year"] <= hi)]["year"]
            rec[f"years_{tag}"] = f"{int(yrs.min())}-{int(yrs.max())}" if len(yrs) else ""
        rows.append(rec)
    t = pd.DataFrame(rows)
    t["loss_ratio_lr"] = t["burn_lr"] / t["premium_rate"]
    t["loss_ratio_hl"] = t["burn_hl"] / t["premium_rate"]
    return t


def index_vintage_comparison(idx: pd.DataFrame, act: pd.DataFrame) -> pd.DataFrame:
    """Official ADM final grid indices (what RMA paid on) vs the index file, per crop year."""
    hist_path = RAW / "prf_actuarial" / "adm_final_index_history.csv"
    if hist_path.exists():
        h = pd.read_csv(hist_path, dtype={"grid_id": str})
    else:
        h = (act.dropna(subset=["final_index_adm"])
             .drop_duplicates(["crop_year", "grid_id", "interval_code"])
             [["crop_year", "grid_id", "interval_code", "final_index_adm"]])
    m = h.merge(idx, left_on=["crop_year", "grid_id", "interval_code"],
                right_on=["year", "grid_id", "interval_code"], how="inner")
    m["diff"] = m["index_value"] - m["final_index_adm"]
    rows = []
    for (lab, g) in list(m.groupby("crop_year")) + [("all", m)]:
        rows.append({"crop_year": lab, "n": len(g), "mean_diff": g["diff"].mean(),
                     "mean_abs_diff": g["diff"].abs().mean(), "max_abs_diff": g["diff"].abs().max(),
                     "corr": g["final_index_adm"].corr(g["index_value"]),
                     "trigger90_disagree": ((g["final_index_adm"] < 90) != (g["index_value"] < 90)).mean()})
    return pd.DataFrame(rows)


def official_index_wide(grid_id: str, act: pd.DataFrame) -> pd.DataFrame | None:
    """Year x interval table of official ADM final indices for one grid (as-paid check), if cached."""
    hist_path = RAW / "prf_actuarial" / "adm_final_index_history.csv"
    if hist_path.exists():
        h = pd.read_csv(hist_path, dtype={"grid_id": str})
    else:
        h = act.dropna(subset=["final_index_adm"]).drop_duplicates(["crop_year", "grid_id", "interval_code"])
    h = h[(h["grid_id"] == str(grid_id)) & (h["crop_year"] <= LAST_YEAR)]
    if h.empty:
        return None
    w = h.pivot_table(index="crop_year", columns="interval_name", values="final_index_adm", aggfunc="first")
    return w.reindex(columns=INTERVAL_NAMES)


def make_grid_figure(t: pd.DataFrame, figdir: Path, rate_year: int) -> Path:
    """Heat map of long-run loss ratio (burn / premium rate) by study grid and interval."""
    from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
    t = t.copy()
    t["label"] = t["site"] + " " + t["grid_role"] + " (" + t["grid_id"] + ")"
    order = [f"{s} {r} ({g})" for s, r, g in t[["site", "grid_role", "grid_id"]].drop_duplicates().itertuples(index=False)]
    mat = t.pivot(index="label", columns="interval_name", values="loss_ratio_lr").reindex(index=order, columns=INTERVAL_NAMES)
    cmap = LinearSegmentedColormap.from_list("div", [C_ORANGE, "#f2f1ee", C_BLUE])
    vals = mat.to_numpy(dtype=float)
    half = max(0.5, float(np.nanmax(np.abs(vals - 1.0))))
    norm = TwoSlopeNorm(vmin=1.0 - half, vcenter=1.0, vmax=1.0 + half)
    fig, ax = plt.subplots(figsize=(10, 0.36 * len(order) + 1.8))
    im = ax.imshow(mat.to_numpy(), cmap=cmap, norm=norm, aspect="auto")
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            v = mat.iat[i, j]
            if pd.notna(v):
                ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=7, color=INK)
    ax.set_xticks(range(len(INTERVAL_NAMES)), INTERVAL_NAMES, fontsize=8)
    ax.set_yticks(range(len(order)), order, fontsize=8)
    ax.tick_params(length=0, colors=INK2)
    for s in ax.spines.values():
        s.set_visible(False)
    cb = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    cb.set_label("loss ratio (mean indemnity / total premium)", fontsize=8, color=INK2)
    cb.ax.tick_params(labelsize=7)
    yrs = t["years_lr"].iloc[0]
    ax.set_title(f"PRF loss ratio by grid and interval: crop-year {rate_year} premium rates at 90% coverage vs "
                 f"{yrs} grid indices\nloss ratio = average indemnity / full premium; below 1 (orange) the average "
                 f"payout was less than the full premium (the producer pays 49% of it)", fontsize=9.5, color=INK,
                 loc="left")
    fig.tight_layout()
    p = figdir / "b4_grid_interval_loss_ratio.png"
    fig.savefig(p, dpi=150)
    plt.close(fig)
    return p


def grid_markdown(t: pd.DataFrame, vint: pd.DataFrame, rate_year: int, fig: Path) -> str:
    out = [f"Generated by `scripts/run_scenarios.py`: crop-year {rate_year} grazing premium rates at 90% "
           f"coverage (rates are identical for haying) against `data/processed/prf_official_index.csv`.\n"]
    out.append("| Site | Grid role | Grid | Mean premium rate (11 intervals) | Long-run mean payment factor | Long-run loss ratio | Lowest / highest interval loss ratio | Payout frequency per interval (long run) | Headline-window loss ratio |")
    out.append("|---|---|---|---|---|---|---|---|---|")
    for (site, role, gid), g in t.groupby(["site", "grid_role", "grid_id"], sort=False):
        lo = g.loc[g["loss_ratio_lr"].idxmin()]
        hi = g.loc[g["loss_ratio_lr"].idxmax()]
        out.append(f"| {site} | {role} | {gid} | {g.premium_rate.mean():.3f} | {g.burn_lr.mean():.3f} | "
                   f"{g.burn_lr.mean() / g.premium_rate.mean():.2f} | {lo.loss_ratio_lr:.2f} ({lo.interval_name}) / "
                   f"{hi.loss_ratio_lr:.2f} ({hi.interval_name}) | {100 * g.freq_lr.mean():.0f}% | "
                   f"{g.burn_hl.mean() / g.premium_rate.mean():.2f} |")
    allr = t.burn_lr.mean() / t.premium_rate.mean()
    allh = t.burn_hl.mean() / t.premium_rate.mean()
    out.append(f"\nAll {t.grid_id.nunique()} grids x 11 intervals: long-run loss ratio {allr:.2f} "
               f"({t.years_lr.iloc[0]}), headline-window loss ratio {allh:.2f} ({HEADLINE[0]}-{HEADLINE[1]}). "
               f"Share of grid-intervals with long-run loss ratio above 1: {100 * (t.loss_ratio_lr > 1).mean():.0f}%.\n")
    out.append(f"![b4_grid_interval_loss_ratio](../figures/{fig.name})\n")
    out.append("**Index vintage check: official ADM final grid index vs `prf_official_index.csv`** "
               "(index points; same grid, interval, and year)\n")
    out.append("| Crop year | Grid-intervals compared | Mean difference (file - ADM) | Mean absolute difference | Max absolute difference | Correlation | Share disagreeing on payout at 90% trigger |")
    out.append("|---|---|---|---|---|---|---|")
    for r in vint.itertuples():
        out.append(f"| {r.crop_year} | {r.n} | {r.mean_diff:+.1f} | {r.mean_abs_diff:.1f} | {r.max_abs_diff:.1f} | "
                   f"{r.corr:.3f} | {100 * r.trigger90_disagree:.1f}% |")
    return "\n".join(out)


def write_doc_block(block: str, doc: Path = DOC, begin: str = AUTO_BEGIN, end: str = AUTO_END) -> None:
    text = doc.read_text(encoding="utf-8")
    if begin not in text or end not in text:
        raise ValueError(f"{doc} lacks the markers {begin!r} / {end!r}")
    pre, rest = text.split(begin, 1)
    _, post = rest.split(end, 1)
    doc.write_text(pre + begin + "\n" + block.strip() + "\n" + end + post, encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description="PRF farm scenarios")
    ap.add_argument("--farms", type=Path, default=DEFAULT_FARMS)
    ap.add_argument("--index", type=Path, default=INDEX_CSV)
    ap.add_argument("--actuarial", type=Path, default=ACT_CSV)
    ap.add_argument("--rate-year", type=int, default=2026)
    ap.add_argument("--no-doc", action="store_true", help="do not rewrite the results doc block")
    args = ap.parse_args(argv)

    farms_path = args.farms if args.farms.is_absolute() else ROOT / args.farms
    provisional = farms_path.resolve() != DEFAULT_FARMS.resolve()
    idx = load_index(args.index)
    act = pd.read_csv(args.actuarial, dtype={"grid_id": str, "county_fips": str})

    # Farm-independent grid analysis (real data); always refreshed in the doc.
    burn = grid_burn_table(idx, act, args.rate_year)
    vint = index_vintage_comparison(idx, act)
    gfig = make_grid_figure(burn, FIGURES, args.rate_year)
    print(f"grid analysis: long-run loss ratio {burn.burn_lr.mean() / burn.premium_rate.mean():.2f}; wrote {gfig}")
    if not args.no_doc and DOC.exists():
        write_doc_block(grid_markdown(burn, vint, args.rate_year, gfig), DOC, AUTO_GRID_BEGIN, AUTO_GRID_END)
        print(f"updated grid block in {DOC}")

    if not farms_path.exists():
        print(f"{farms_path} not found: farm results stay pending. For a smoke test run with "
              f"--farms tests/fixtures/b4/farms_provisional.yaml")
        return 0
    farms = load_farms(farms_path)
    sens = pd.read_csv(SENS_CSV) if SENS_CSV.exists() else None

    results, meta = [], []
    for farm in farms:
        try:
            r, m = run_farm(farm, idx, act, sens, args.rate_year)
        except (PRFElectionError, LookupError, KeyError) as exc:
            print(f"SKIP {farm.get('farm_id')}: {exc}")
            continue
        results.append(r)
        meta.append(m)
        print(f"{m['farm_id']}: grid {m['grid_id']}, {len(r)} years, avg indemnity "
              f"${r['indemnity_usd'].mean():,.0f}, producer premium ${r['producer_premium_usd'].iloc[0]:,.0f}")
    if not results:
        print("no farms could be run")
        return 1
    res = pd.concat(results, ignore_index=True)
    out_csv = OUT_CSV if not provisional else PROVISIONAL_DIR / "prf_scenario_results_provisional.csv"
    figdir = FIGURES if not provisional else PROVISIONAL_DIR
    tag = "" if not provisional else "_provisional"
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    res.to_csv(out_csv, index=False, float_format="%.4f")
    print(f"wrote {out_csv} ({len(res)} rows)")
    head = summarize_window(res, *HEADLINE)
    lr = summarize_window(res, int(res["year"].min()), LAST_YEAR)
    figs = make_figures(res, figdir, tag)
    block = markdown_tables(meta, head, lr, args.rate_year, figs, DOC.parent)
    if provisional:
        (PROVISIONAL_DIR / "summary_provisional.md").write_text(
            "# PROVISIONAL smoke-test output (illustrative farms, not results)\n\n" + block, encoding="utf-8")
        print(f"provisional outputs in {PROVISIONAL_DIR}; results doc left unchanged")
    elif not args.no_doc:
        write_doc_block(block, DOC, AUTO_BEGIN, AUTO_END)
        print(f"updated farm block in {DOC}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
