"""Pull RMA Summary of Business (SOB) files and summarize the PRF Rainfall Index program.

Source: USDA RMA Summary of Business, State/County/Crop with Coverage Level ("sobcov") files,
https://pubfs-rma.fpac.usda.gov/pub/Web_Data_Files/Summary_of_Business/state_county_crop/
Record layout: SOB_State_County_Crop_with_Coverage_Level_1989_Forward.pdf in that folder
(28 pipe-delimited fields, no header row).

PRF is commodity code 0088 ("Pasture,Rangeland,Forage") under insurance plan code 13 ("RI",
Rainfall Index). Both codes were verified by tabulating the 2015-2027 files: commodity 0088 appears
only with plan 13, except in 2015 when the retired Vegetation Index plan (code 14, "VI") was still
sold. This script keeps plan 13 only.

The optional type/practice/unit ("sobtpu") file is used for one extra table: liability by PRF
index interval. In that file the PRF practice code identifies the two-month interval
(grazing 625-635 = Jan-Feb ... Nov-Dec; non-irrigated haying 525-535; irrigated haying 425-435;
organic variants 465-475, 485-495, 565-575, 585-595).

Outputs
- data/processed/prf_summary_of_business_state.csv  (state x year, 2015-2026)
- docs/figures/r4_prf_national_timeseries.png
- docs/figures/r4_prf_state_returns.png
- printed markdown tables used in docs/research/02_how_farmers_buy_weather_insurance.md

Run from the repo root:  python -I scripts/pull_rma_sob.py
Raw zips are cached in data/raw/rma_sob/ so reruns do not download again.
"""
from __future__ import annotations

import io
import time
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from agri_hedge.config import FIGURES, PROCESSED, RAW

SOB_URL = "https://pubfs-rma.fpac.usda.gov/pub/Web_Data_Files/Summary_of_Business/state_county_crop/"
RAW_DIR = RAW / "rma_sob"
PRF_COMMODITY_CODE = 88
RAINFALL_INDEX_PLAN_CODE = 13
YEARS = list(range(2015, 2027))  # 2026 is still incomplete (late intervals unpaid) as of 2026-10
LATEST_COMPLETE_YEAR = 2025
STUDY_STATES = ["TX", "OK", "MO", "CO", "NM", "FL"]
# Farm counties of the study sites (state FIPS, county FIPS), from src/agri_hedge/locations.py.
STUDY_COUNTIES = {
    "DFW": ("48", "367"), "SAT": ("48", "013"), "OKC": ("40", "051"), "SGF": ("29", "057"),
    "DEN": ("08", "039"), "ABQ": ("35", "057"), "TPA": ("12", "049"),
}

SOBCOV_COLUMNS = [
    "year", "state_fips", "state_abbr", "county_fips", "county_name", "commodity_code",
    "commodity_name", "plan_code", "plan_abbr", "coverage_category", "delivery_type",
    "coverage_level", "policies_sold", "policies_earning_premium", "policies_indemnified",
    "units_earning_premium", "units_indemnified", "quantity_type", "net_reported_quantity",
    "endorsed_companion_acres", "liability", "total_premium", "subsidy", "state_private_subsidy",
    "additional_subsidy", "efa_premium_discount", "indemnity", "loss_ratio_reported",
]
SOBTPU_COLUMNS = [
    "year", "state_fips", "state_name", "state_abbr", "county_fips", "county_name",
    "commodity_code", "commodity_name", "plan_code", "plan_abbr", "coverage_type",
    "coverage_level", "delivery_id", "type_code", "type_name", "practice_code", "practice_name",
    "unit_code", "unit_name", "net_reported_quantity", "quantity_type", "liability",
    "total_premium", "subsidy", "indemnity", "loss_ratio_reported", "endorsed_quantity",
]
SUM_FIELDS = [
    "policies_sold", "policies_earning_premium", "policies_indemnified", "units_earning_premium",
    "units_indemnified", "net_reported_quantity", "liability", "total_premium", "subsidy",
    "state_private_subsidy", "additional_subsidy", "efa_premium_discount", "indemnity",
]


def download(filename: str, raw_dir: Path = RAW_DIR) -> Path:
    """Download one file from the SOB folder into raw_dir unless it is already cached."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / filename
    if path.exists() and path.stat().st_size > 0:
        return path
    for attempt in range(4):
        resp = requests.get(SOB_URL + filename, timeout=120)
        if resp.status_code == 200:
            path.write_bytes(resp.content)
            return path
        time.sleep(2 ** attempt)
    resp.raise_for_status()
    return path


def _read_zipped_text(path: Path) -> str:
    """Return the text of the single member of an RMA zip. Records may end in CR, LF or CRLF."""
    with zipfile.ZipFile(path) as zf:
        name = zf.namelist()[0]
        raw = zf.read(name).decode("latin-1")
    return raw.replace("\r\n", "\n").replace("\r", "\n")


def read_sobcov(path: Path) -> pd.DataFrame:
    """Parse a sobcov_<year>.zip file into a DataFrame with named, typed columns."""
    df = pd.read_csv(io.StringIO(_read_zipped_text(path)), sep="|", header=None,
                     names=SOBCOV_COLUMNS, dtype=str, keep_default_na=False)
    return _clean(df, numeric=SUM_FIELDS + ["year", "commodity_code", "plan_code",
                                            "coverage_level", "loss_ratio_reported",
                                            "endorsed_companion_acres"])


def read_sobtpu(path: Path) -> pd.DataFrame:
    """Parse a sobtpu_<year>.zip file (type/practice/unit detail) into a DataFrame."""
    df = pd.read_csv(io.StringIO(_read_zipped_text(path)), sep="|", header=None,
                     names=SOBTPU_COLUMNS, dtype=str, keep_default_na=False)
    return _clean(df, numeric=["year", "commodity_code", "plan_code", "coverage_level",
                               "net_reported_quantity", "liability", "total_premium", "subsidy",
                               "indemnity", "loss_ratio_reported", "endorsed_quantity"])


def _clean(df: pd.DataFrame, numeric: list[str]) -> pd.DataFrame:
    """Strip padding from text fields and convert numeric fields (blank -> 0)."""
    for col in df.columns:
        df[col] = df[col].str.strip()
    for col in numeric:
        df[col] = pd.to_numeric(df[col].replace("", "0"), errors="coerce").fillna(0)
    df = df[df["year"] > 0].copy()
    df["year"] = df["year"].astype(int)
    return df


def prf_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Keep PRF Rainfall Index rows (commodity 0088, plan 13)."""
    keep = (df["commodity_code"] == PRF_COMMODITY_CODE) & (df["plan_code"] == RAINFALL_INDEX_PLAN_CODE)
    return df[keep].copy()


def add_ratios(agg: pd.DataFrame) -> pd.DataFrame:
    """Add derived columns to an aggregated table that has the SUM_FIELDS columns.

    producer_paid_premium = total premium minus every subsidy/discount field.
    loss_ratio            = indemnity / total premium (RMA's definition).
    subsidy_rate          = federal subsidy / total premium.
    producer_return_per_dollar = indemnity / producer-paid premium (what a rancher got back
                                 per dollar out of pocket).
    """
    out = agg.copy()
    out["producer_paid_premium"] = (out["total_premium"] - out["subsidy"]
                                    - out["state_private_subsidy"] - out["additional_subsidy"]
                                    - out["efa_premium_discount"])
    tp = out["total_premium"].replace(0, np.nan)
    out["loss_ratio"] = out["indemnity"] / tp
    out["subsidy_rate"] = out["subsidy"] / tp
    out["premium_rate"] = out["total_premium"] / out["liability"].replace(0, np.nan)
    out["producer_return_per_dollar"] = out["indemnity"] / out["producer_paid_premium"].replace(0, np.nan)
    out["net_transfer_to_producers"] = out["indemnity"] - out["producer_paid_premium"]
    acres = out["net_reported_quantity"].replace(0, np.nan)
    out["liability_per_acre"] = out["liability"] / acres
    out["producer_premium_per_acre"] = out["producer_paid_premium"] / acres
    return out


def summarize_by_state(prf: pd.DataFrame) -> pd.DataFrame:
    """Aggregate PRF rows to state x year and add derived ratios."""
    grp = prf.groupby(["year", "state_fips", "state_abbr"], as_index=False)
    agg = grp[SUM_FIELDS].sum()
    counties = grp["county_fips"].nunique().rename(columns={"county_fips": "counties_with_policies"})
    agg = agg.merge(counties, on=["year", "state_fips", "state_abbr"])
    agg = add_ratios(agg).rename(columns={"net_reported_quantity": "net_reported_acres"})
    agg["year_complete"] = agg["year"] <= LATEST_COMPLETE_YEAR
    return agg.sort_values(["year", "state_abbr"]).reset_index(drop=True)


def national(state_df: pd.DataFrame) -> pd.DataFrame:
    """Sum the state table to a national year series and recompute ratios."""
    fields = [c if c != "net_reported_quantity" else "net_reported_acres" for c in SUM_FIELDS]
    nat = state_df.groupby("year", as_index=False)[fields + ["counties_with_policies"]].sum()
    nat = add_ratios(nat.rename(columns={"net_reported_acres": "net_reported_quantity"}))
    nat = nat.rename(columns={"net_reported_quantity": "net_reported_acres"})
    nat["states"] = state_df.groupby("year")["state_abbr"].nunique().values
    return nat


def pooled_by_state(state_df: pd.DataFrame, first: int, last: int) -> pd.DataFrame:
    """Pool several years per state (sum dollars first, then take ratios)."""
    fields = [c if c != "net_reported_quantity" else "net_reported_acres" for c in SUM_FIELDS]
    sub = state_df[(state_df["year"] >= first) & (state_df["year"] <= last)]
    pooled = sub.groupby("state_abbr", as_index=False)[fields].sum()
    pooled = add_ratios(pooled.rename(columns={"net_reported_acres": "net_reported_quantity"}))
    pooled = pooled.rename(columns={"net_reported_quantity": "net_reported_acres"})
    pooled["years_loss_ratio_above_1"] = sub.assign(above=sub["loss_ratio"] > 1).groupby(
        "state_abbr")["above"].sum().reindex(pooled["state_abbr"]).values
    pooled["years_return_above_1"] = sub.assign(
        above=sub["producer_return_per_dollar"] > 1).groupby("state_abbr")["above"].sum().reindex(
        pooled["state_abbr"]).values
    return pooled


def coverage_level_mix(prf: pd.DataFrame, year: int) -> pd.DataFrame:
    """National share of acres, liability and policies by PRF coverage level for one year."""
    sub = prf[prf["year"] == year]
    mix = sub.groupby("coverage_level", as_index=False)[
        ["policies_earning_premium", "net_reported_quantity", "liability", "total_premium",
         "subsidy", "indemnity"]].sum()
    for col in ["policies_earning_premium", "net_reported_quantity", "liability"]:
        mix[col + "_share"] = mix[col] / mix[col].sum()
    mix["subsidy_rate"] = mix["subsidy"] / mix["total_premium"]
    return mix


def interval_mix(tpu_prf: pd.DataFrame, states: list[str] | None = None) -> pd.DataFrame:
    """Share of PRF liability by two-month index interval (practice code mod 100 -> 25..35)."""
    sub = tpu_prf[tpu_prf["practice_code"].astype(int) > 0].copy()
    if states:
        sub = sub[sub["state_abbr"].isin(states)]
    # Last two digits 25-35 (conventional) or 65-75 / 85-95 (organic) -> 0..10, 0 = Jan-Feb.
    sub["interval_idx"] = (sub["practice_code"].astype(int) % 100 - 25) % 20
    names = ["Jan-Feb", "Feb-Mar", "Mar-Apr", "Apr-May", "May-Jun", "Jun-Jul", "Jul-Aug",
             "Aug-Sep", "Sep-Oct", "Oct-Nov", "Nov-Dec"]
    sub = sub[(sub["interval_idx"] >= 0) & (sub["interval_idx"] <= 10)]
    sub["interval"] = sub["interval_idx"].map(dict(enumerate(names)))
    out = sub.groupby(["interval_idx", "interval"], as_index=False)[
        ["liability", "total_premium", "indemnity"]].sum()
    out["liability_share"] = out["liability"] / out["liability"].sum()
    out["premium_rate"] = out["total_premium"] / out["liability"]
    out["loss_ratio"] = out["indemnity"] / out["total_premium"]
    return out


def study_counties(prf: pd.DataFrame, years: list[int]) -> pd.DataFrame:
    """PRF totals for each study-site farm county, pooled over `years`."""
    rows = []
    for site, (st, co) in STUDY_COUNTIES.items():
        sub = prf[(prf["state_fips"] == st) & (prf["county_fips"] == co) & prf["year"].isin(years)]
        agg = sub[SUM_FIELDS].sum().to_frame().T
        agg.insert(0, "site", site)
        agg.insert(1, "county", f"{sub['county_name'].iloc[0]} {sub['state_abbr'].iloc[0]}" if len(sub) else "")
        rows.append(agg)
    return add_ratios(pd.concat(rows, ignore_index=True))


# ----------------------------------------------------------------------------- figures

def plot_national(nat: pd.DataFrame, path: Path) -> None:
    """Stacked bars of producer-paid premium and subsidy, with indemnity line, by year."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    d = nat[nat["year"] <= LATEST_COMPLETE_YEAR]
    yrs = d["year"].values
    fig, ax = plt.subplots(figsize=(8, 4.6), dpi=150)
    ax.bar(yrs, d["producer_paid_premium"] / 1e6, color="#a3a29c", edgecolor="white", linewidth=1.5,
           label="Premium paid by ranchers")
    ax.bar(yrs, d["subsidy"] / 1e6, bottom=d["producer_paid_premium"] / 1e6, color="#2a78d6",
           edgecolor="white", linewidth=1.5, label="Premium paid by taxpayers (subsidy)")
    ax.plot(yrs, d["indemnity"] / 1e6, color="#0b0b0b", marker="o", markersize=6, linewidth=2,
            label="Indemnities paid to ranchers")
    ax.set_xticks(yrs)
    ax.set_xlabel("Crop year")
    ax.set_ylabel("Million US dollars (nominal)")
    ax.set_title("PRF Rainfall Index: premium vs. indemnity, all states, 2015-2025")
    ax.grid(axis="y", linewidth=0.4, alpha=0.6)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, loc="upper left")
    fig.text(0.01, 0.01, "Source: USDA RMA Summary of Business (sobcov files, data as of 2026-10-26); "
             "commodity 0088, plan 13.", fontsize=7, color="#444444")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(path)
    plt.close(fig)


def plot_state_returns(pooled: pd.DataFrame, path: Path, top_n: int = 15) -> None:
    """Horizontal bars: loss ratio and indemnity per producer dollar, top states by liability."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    d = pooled.sort_values("liability", ascending=False).head(top_n).iloc[::-1]
    y = np.arange(len(d))
    fig, ax = plt.subplots(figsize=(8, 6.2), dpi=150)
    ax.barh(y + 0.2, d["producer_return_per_dollar"], height=0.38, color="#2a78d6",
            label="Indemnity per $1 of rancher-paid premium")
    ax.barh(y - 0.2, d["loss_ratio"], height=0.38, color="#a3a29c", hatch="///", edgecolor="white",
            linewidth=0, label="Loss ratio (indemnity / total premium)")
    for yi, val in zip(y, d["producer_return_per_dollar"]):
        ax.text(val + 0.03, yi + 0.2, f"{val:.2f}", va="center", fontsize=7, color="#52514e",
                bbox=dict(facecolor="white", edgecolor="none", pad=0.4))
    for yi, val in zip(y, d["loss_ratio"]):
        ax.text(val + 0.03, yi - 0.2, f"{val:.2f}", va="center", fontsize=7, color="#52514e",
                bbox=dict(facecolor="white", edgecolor="none", pad=0.4))
    ax.axvline(1.0, color="#0b0b0b", linewidth=1, linestyle="--")
    ax.set_yticks(y)
    ax.set_yticklabels(d["state_abbr"])
    ax.set_xlabel("Dollars returned per dollar of premium (pooled 2015-2025)")
    ax.set_title(f"PRF: what ranchers got back, {top_n} largest states by liability")
    ax.grid(axis="x", linewidth=0.4, alpha=0.6)
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_xlim(0, max(3.0, d["producer_return_per_dollar"].max() + 0.3))
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.09), ncol=2, fontsize=8)
    fig.text(0.01, 0.01, "Right of the dashed line = more paid out than paid in. Source: USDA RMA Summary "
             "of Business (sobcov), dollars summed over 2015-2025 before taking ratios.",
             fontsize=7, color="#444444")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(path)
    plt.close(fig)


# ----------------------------------------------------------------------------- printing

def _money(x: float) -> str:
    return f"{x / 1e6:,.1f}"


def print_tables(state_df: pd.DataFrame, nat: pd.DataFrame, pooled: pd.DataFrame,
                 cov: pd.DataFrame, intervals: pd.DataFrame, counties: pd.DataFrame) -> None:
    """Print the markdown tables that go into the R4 research doc."""
    print("\n### National PRF series ($ million)")
    print("| Year | States | Policies sold | Policies earning premium | Acres (M) | Liability | "
          "Total premium | Subsidy | Producer-paid | Indemnity | Loss ratio | Subsidy rate | "
          "Return per producer $ |")
    print("|" + "---|" * 13)
    for _, r in nat.iterrows():
        flag = " (incomplete)" if r["year"] > LATEST_COMPLETE_YEAR else ""
        print(f"| {int(r['year'])}{flag} | {int(r['states'])} | {r['policies_sold']:,.0f} | "
              f"{r['policies_earning_premium']:,.0f} | {r['net_reported_acres'] / 1e6:,.1f} | "
              f"{_money(r['liability'])} | {_money(r['total_premium'])} | {_money(r['subsidy'])} | "
              f"{_money(r['producer_paid_premium'])} | {_money(r['indemnity'])} | "
              f"{r['loss_ratio']:.2f} | {r['subsidy_rate']:.1%} | {r['producer_return_per_dollar']:.2f} |")

    y = LATEST_COMPLETE_YEAR
    d = state_df[state_df["year"] == y].sort_values("liability", ascending=False)
    tot = d["liability"].sum()
    print(f"\n### Top 10 states by liability, {y} ($ million)")
    print("| Rank | State | Policies earning premium | Acres (M) | Liability | Share of US liability | "
          "Total premium | Subsidy | Producer-paid | Indemnity | Loss ratio | Return per producer $ |")
    print("|" + "---|" * 12)
    for i, (_, r) in enumerate(d.head(10).iterrows(), 1):
        print(f"| {i} | {r['state_abbr']} | {r['policies_earning_premium']:,.0f} | "
              f"{r['net_reported_acres'] / 1e6:,.1f} | {_money(r['liability'])} | "
              f"{r['liability'] / tot:.1%} | {_money(r['total_premium'])} | {_money(r['subsidy'])} | "
              f"{_money(r['producer_paid_premium'])} | {_money(r['indemnity'])} | "
              f"{r['loss_ratio']:.2f} | {r['producer_return_per_dollar']:.2f} |")
    print(f"Top-10 share of liability: {d.head(10)['liability'].sum() / tot:.1%}; "
          f"top-3: {d.head(3)['liability'].sum() / tot:.1%}")

    print(f"\n### Study states by year (loss ratio / return per producer $ / liability $M)")
    for st in STUDY_STATES:
        s = state_df[state_df["state_abbr"] == st]
        cells = [f"{int(r['year'])}: LR {r['loss_ratio']:.2f}, ret {r['producer_return_per_dollar']:.2f}, "
                 f"liab {_money(r['liability'])}, pol {r['policies_earning_premium']:,.0f}, "
                 f"acres {r['net_reported_acres'] / 1e6:.2f}M" for _, r in s.iterrows()]
        print(st, " | ".join(cells))

    print("\n### Study states, latest complete year and pooled 2015-2025")
    print("| State | 2025 policies earning premium | 2025 acres (M) | 2025 liability | 2025 total premium | "
          "2025 subsidy | 2025 producer-paid | 2025 indemnity | 2025 loss ratio | Pooled 2015-25 loss ratio | "
          "Pooled return per producer $ | Years LR>1 (of 11) |")
    print("|" + "---|" * 12)
    for st in STUDY_STATES:
        r = state_df[(state_df["state_abbr"] == st) & (state_df["year"] == y)].iloc[0]
        p = pooled[pooled["state_abbr"] == st].iloc[0]
        print(f"| {st} | {r['policies_earning_premium']:,.0f} | {r['net_reported_acres'] / 1e6:,.2f} | "
              f"{_money(r['liability'])} | {_money(r['total_premium'])} | {_money(r['subsidy'])} | "
              f"{_money(r['producer_paid_premium'])} | {_money(r['indemnity'])} | {r['loss_ratio']:.2f} | "
              f"{p['loss_ratio']:.2f} | {p['producer_return_per_dollar']:.2f} | "
              f"{int(p['years_loss_ratio_above_1'])} |")

    print("\n### Pooled 2015-2025 by state (sorted by liability)")
    print("| State | Liability | Total premium | Subsidy rate | Loss ratio | Return per producer $ | Years LR>1 | Years return>1 |")
    print("|" + "---|" * 8)
    for _, p in pooled.sort_values("liability", ascending=False).iterrows():
        print(f"| {p['state_abbr']} | {_money(p['liability'])} | {_money(p['total_premium'])} | "
              f"{p['subsidy_rate']:.1%} | {p['loss_ratio']:.2f} | {p['producer_return_per_dollar']:.2f} | "
              f"{int(p['years_loss_ratio_above_1'])} | {int(p['years_return_above_1'])} |")
    n_ret = (pooled["producer_return_per_dollar"] > 1).sum()
    n_lr = (pooled["loss_ratio"] > 1).sum()
    print(f"States: {len(pooled)}; pooled return per producer $ > 1 in {n_ret}; pooled LR > 1 in {n_lr}")
    big = pooled[pooled["liability"] > pooled["liability"].sum() * 0.01]
    print(f"States with >1% of liability: {len(big)}; of those return>1: "
          f"{(big['producer_return_per_dollar'] > 1).sum()}; LR>1: {(big['loss_ratio'] > 1).sum()}")

    print(f"\n### Coverage level mix, {y}")
    print("| Coverage level | Policies share | Acres share | Liability share | Subsidy rate |")
    print("|---|---|---|---|---|")
    for _, r in cov.iterrows():
        print(f"| {r['coverage_level']:.0%} | {r['policies_earning_premium_share']:.1%} | "
              f"{r['net_reported_quantity_share']:.1%} | {r['liability_share']:.1%} | {r['subsidy_rate']:.1%} |")

    print(f"\n### Liability share by interval, {y} (US and study states)")
    print(intervals.to_string(index=False))

    print("\n### Study-site farm counties, pooled 2015-2025")
    print("| Site | County | Liability 2015-25 | Total premium | Subsidy | Indemnity | Loss ratio | Return per producer $ |")
    print("|" + "---|" * 8)
    for _, r in counties.iterrows():
        print(f"| {r['site']} | {r['county']} | {_money(r['liability'])} | {_money(r['total_premium'])} | "
              f"{_money(r['subsidy'])} | {_money(r['indemnity'])} | {r['loss_ratio']:.2f} | "
              f"{r['producer_return_per_dollar']:.2f} |")


def plan_totals(df: pd.DataFrame) -> pd.DataFrame:
    """National totals by insurance plan for one sobcov year (all commodities)."""
    agg = df.groupby(["plan_code", "plan_abbr"], as_index=False)[SUM_FIELDS].sum()
    agg = add_ratios(agg)
    return agg.sort_values("liability", ascending=False)


def main() -> None:
    frames = []
    for year in YEARS:
        path = download(f"sobcov_{year}.zip")
        df = read_sobcov(path)
        frames.append(prf_rows(df))
        if year == LATEST_COMPLETE_YEAR:
            plans = plan_totals(df)
            df_latest = df
    prf = pd.concat(frames, ignore_index=True)

    state_df = summarize_by_state(prf)
    nat = national(state_df)
    pooled = pooled_by_state(state_df, 2015, LATEST_COMPLETE_YEAR)
    cov = coverage_level_mix(prf, LATEST_COMPLETE_YEAR)

    tpu = prf_rows(read_sobtpu(download(f"sobtpu_{LATEST_COMPLETE_YEAR}.zip")))
    iv_us = interval_mix(tpu).assign(region="US")
    iv_st = interval_mix(tpu, STUDY_STATES).assign(region="study states")
    intervals = pd.concat([iv_us, iv_st], ignore_index=True)[
        ["region", "interval", "liability_share", "premium_rate", "loss_ratio"]]
    type_split = tpu.groupby("type_name")[["net_reported_quantity", "liability"]].sum()

    counties = study_counties(prf, list(range(2015, LATEST_COMPLETE_YEAR + 1)))

    out_cols = ["year", "year_complete", "state_fips", "state_abbr", "counties_with_policies",
                "policies_sold", "policies_earning_premium", "policies_indemnified",
                "units_earning_premium", "units_indemnified", "net_reported_acres", "liability",
                "total_premium", "subsidy", "state_private_subsidy", "additional_subsidy",
                "efa_premium_discount", "producer_paid_premium", "indemnity", "loss_ratio",
                "subsidy_rate", "premium_rate", "producer_return_per_dollar",
                "net_transfer_to_producers", "liability_per_acre", "producer_premium_per_acre"]
    csv_path = PROCESSED / "prf_summary_of_business_state.csv"
    state_df[out_cols].to_csv(csv_path, index=False, float_format="%.6g")
    print(f"wrote {csv_path} ({len(state_df)} rows)")

    plot_national(nat, FIGURES / "r4_prf_national_timeseries.png")
    plot_state_returns(pooled, FIGURES / "r4_prf_state_returns.png")
    print("wrote figures r4_prf_national_timeseries.png, r4_prf_state_returns.png")

    print_tables(state_df, nat, pooled, cov, intervals, counties)
    print("\n### PRF grazing vs haying, 2025 (acres, liability)")
    print(type_split.assign(acre_share=type_split["net_reported_quantity"] / type_split["net_reported_quantity"].sum(),
                            liab_share=type_split["liability"] / type_split["liability"].sum()).to_string())
    print(f"\n### All plans, national {LATEST_COMPLETE_YEAR} ($ million)")
    show = plans.head(25)
    for _, r in show.iterrows():
        print(f"{int(r['plan_code']):>3} {r['plan_abbr']:<8} liab {_money(r['liability']):>12} "
              f"prem {_money(r['total_premium']):>10} subs {_money(r['subsidy']):>10} "
              f"indem {_money(r['indemnity']):>10} pol {r['policies_earning_premium']:>10,.0f} "
              f"acres {r['net_reported_quantity'] / 1e6:>8.1f}M")
    ri = df_latest[df_latest["plan_code"] == RAINFALL_INDEX_PLAN_CODE].groupby(
        ["commodity_code", "commodity_name"], as_index=False)[SUM_FIELDS].sum()
    print("\nRainfall Index plan by commodity (9999 = RMA's masked 'All Other Crops' cells):")
    for _, r in ri.iterrows():
        print(f"  {int(r['commodity_code']):>4} {r['commodity_name']:<26} liab {_money(r['liability'])} "
              f"prem {_money(r['total_premium'])} subs {_money(r['subsidy'])} "
              f"indem {_money(r['indemnity'])} pol {r['policies_earning_premium']:,.0f}")
    tpu_liab = tpu["liability"].sum()
    sob_liab = prf.loc[prf["year"] == LATEST_COMPLETE_YEAR, "liability"].sum()
    print(f"PRF liability {LATEST_COMPLETE_YEAR}: sobcov {_money(sob_liab)} vs sobtpu {_money(tpu_liab)} "
          f"(sobtpu/sobcov = {tpu_liab / sob_liab:.4f}); difference = small cells masked as 9999")
    tot = plans[SUM_FIELDS].sum()
    print(f"ALL plans: liab {_money(tot['liability'])} prem {_money(tot['total_premium'])} "
          f"subs {_money(tot['subsidy'])} indem {_money(tot['indemnity'])} "
          f"policies earning premium {tot['policies_earning_premium']:,.0f}")


if __name__ == "__main__":
    main()
