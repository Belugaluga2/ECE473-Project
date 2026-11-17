"""Fair prices for third-inch rain strikes at every Kalshi monthly-rain station (doc 27).

Run from the repo root (no network; uses data/processed/station_monthly_precip.csv and
kalshi_rain_markets.parquet):

    python scripts/run_third_inch_pricing.py

Outputs
    data/processed/third_inch_fair_prices.csv      one row per station x calendar month x strike
    data/processed/third_inch_ladder_resolution.csv one row per station x month x ladder
    data/processed/third_inch_station_summary.csv  one row per station
    docs/figures/x1_*.png
    tables between the AUTO markers of docs/analysis/27_third_inch_fair_pricing.md (or
    data/processed/third_inch_tables.md if the doc does not exist yet)

Method. For each station and calendar month the fair YES price of "more than K inches" is the
share of past complete months whose total exceeded K. Windows: 1991-2025 (35 years, the
climatology doc 09 used), 1951-2025 (75 years), the full record, and 1951-1990 for a trend
check. A 90% Wilson interval shows sampling error on the 1991-2025 share. A zero-inflated
gamma fit to 1951-2025 gives a smoothed price that does not jump in 1/75 steps. Ladder
resolution compares the strikes Kalshi lists today with the same range in third-inch and
half-inch steps: number of strikes priced 5-95 cents, the coarsest probability bin, and how
well the best long-only NO ladder copies a PRF-style monthly put (90% of the month's mean).
"""
from __future__ import annotations

import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from agri_hedge import exotics as ex  # noqa: E402
from agri_hedge.config import DOCS, FIGURES, PROCESSED  # noqa: E402
from agri_hedge.kalshi import fee as kalshi_fee  # noqa: E402

DOC = DOCS / "analysis" / "27_third_inch_fair_pricing.md"
WINDOWS = {"recent35": (1991, 2025), "std75": (1951, 2025), "early40": (1951, 1990), "full": (1800, 2025)}
PRIMARY = "recent35"
MONTHS = list(range(1, 13))
MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
PRF_SITES = {"DFW", "SAT", "OKC", "SGF", "DEN", "ABQ", "TPA"}
TOP_VOLUME_N = 10
#: default Kalshi ladder for series that have only listed one month so far
DEFAULT_LADDER = tuple(float(k) for k in range(1, 8))
#: palette (dataviz skill reference instance)
C_BLUE, C_ORANGE, C_AQUA, C_YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
C_TEXT, C_TEXT2, C_GRID = "#0b0b0b", "#52514e", "#e6e5e2"
SEQ_BLUES = ["#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7", "#3987e5", "#2a78d6",
             "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b"]


def log(*a):
    print(*a, flush=True)


# ---------------------------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------------------------

def load_stations() -> pd.DataFrame:
    sm = pd.read_csv(PROCESSED / "station_map.csv")
    sm = sm[sm["series_ticker"].str.startswith("KX")].copy()
    sm = sm[sm["station_key"] != "MDW"]  # Chicago settles at O'Hare since Sep 2026 (doc 06c)
    vol = pd.read_csv(PROCESSED / "kalshi_rain_markets_summary.csv")[["series_ticker", "total_volume"]]
    sm = sm.merge(vol, on="series_ticker", how="left")
    sm["total_volume"] = sm["total_volume"].fillna(0.0)
    top = set(sm.sort_values("total_volume", ascending=False)["series_ticker"].head(TOP_VOLUME_N))
    sm["is_prf_site"] = sm["study_site"].isin(PRF_SITES)
    sm["is_top_volume"] = sm["series_ticker"].isin(top)
    sm["important"] = sm["is_prf_site"] | sm["is_top_volume"]
    sm["city"] = (sm["series_title"].str.replace(r"(?i)^(rain in|rain|monthly rain in)\s*", "", regex=True)
                  .str.replace(r"(?i)\s*(rainfall totals|rain monthly)$", "", regex=True).str.strip().str.title())
    return sm[["series_ticker", "city", "station_key", "study_site", "name", "state", "record_start",
               "total_volume", "is_prf_site", "is_top_volume", "important"]].reset_index(drop=True)


def load_monthly() -> dict[str, pd.DataFrame]:
    st = pd.read_csv(PROCESSED / "station_monthly_precip.csv")
    st.loc[st["n_missing"].fillna(1) != 0, "precip_in"] = np.nan
    out = {}
    for key, g in st.groupby("station_key"):
        w = g.pivot_table(index="year", columns="month", values="precip_in", aggfunc="first")
        out[key] = w.reindex(columns=MONTHS).sort_index()
    return out


def listed_ladders() -> dict[str, tuple[float, ...]]:
    """Whole-inch strikes each series has ever listed (union over months), or the default 1-7."""
    m = pd.read_parquet(PROCESSED / "kalshi_rain_markets.parquet",
                        columns=["series_ticker", "floor_strike", "is_single_month", "strike_type"])
    m = m[m["is_single_month"].astype(bool) & (m["strike_type"] == "greater")].dropna(subset=["floor_strike"])
    out = {}
    for s, g in m.groupby("series_ticker"):
        ks = sorted({float(k) for k in g["floor_strike"] if float(k) == int(float(k))})
        out[s] = tuple(ks) if ks else DEFAULT_LADDER
    return out


# ---------------------------------------------------------------------------------------------
# Pricing
# ---------------------------------------------------------------------------------------------

def price_station(key: str, rain: pd.DataFrame, ladder_max: float) -> pd.DataFrame:
    rows = []
    for mon in MONTHS:
        s = rain[mon].dropna()
        if len(s) < 20:
            continue
        top = max(ladder_max, float(np.ceil(s.max())))
        strikes = ex.third_inch_strikes(top)
        t = ex.fair_price_table(s, strikes, WINDOWS, ci_window=PRIMARY, gamma_window="std75")
        # stop the table at the first strike no month on record has exceeded
        t = t[(t["p_yes_full"] > 0) | (t["strike_in"] <= ladder_max)]
        t.insert(0, "month", mon)
        t.insert(0, "station_key", key)
        rows.append(t)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def add_prices_and_fees(t: pd.DataFrame) -> pd.DataFrame:
    p = t[f"p_yes_{PRIMARY}"].to_numpy(float)
    t["fair_yes_cents"] = np.round(100 * p, 1)
    t["fair_no_cents"] = np.round(100 * (1 - p), 1)
    pc = np.clip(p, 0.01, 0.99)
    t["taker_fee_cents_per_contract"] = np.round(100 * 0.07 * pc * (1 - pc), 2)
    t["is_whole_inch"] = np.isclose(t["strike_in"] % 1, 0)
    t["informative_recent35"] = (p >= ex.INFORMATIVE_LO) & (p <= ex.INFORMATIVE_HI)
    t["ci90_width"] = t["ci90_hi"] - t["ci90_lo"]
    t["p_yes_shift_early_to_recent"] = t[f"p_yes_{PRIMARY}"] - t["p_yes_early40"]
    return t


def resolution_station(key: str, rain: pd.DataFrame, listed: tuple[float, ...]) -> pd.DataFrame:
    """Resolution of today's ladder vs third-inch and half-inch ladders over the same range."""
    rows = []
    top = max(listed)
    ladders = {
        "today (listed whole inches)": np.array(listed, dtype=float),
        "half-inch to same max": ex.strike_grid(0.5, top),
        "third-inch to same max": ex.strike_grid(ex.THIRD_IN, top),
    }
    for mon in MONTHS:
        s = rain[mon].loc[1951:2025].dropna()
        if len(s) < 20:
            continue
        for name, ks in ladders.items():
            r = ex.ladder_resolution(s.to_numpy(), ks)
            rows.append({"station_key": key, "month": mon, "ladder": name, "max_strike_in": top,
                         "median_rain_in": float(s.median()), "mean_rain_in": float(s.mean()),
                         "p_le_1in": float((s <= 1.0 + 1e-9).mean()), **r})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------------------------

def md_table(df: pd.DataFrame, cols: list[str], headers: list[str] | None = None, fmt: dict | None = None) -> str:
    headers = headers or cols
    fmt = fmt or {}
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            f = fmt.get(c)
            if f is not None:
                cells.append(f(v))
            elif isinstance(v, float):
                cells.append("" if np.isnan(v) else f"{v:.2f}")
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def replace_between_markers(path: Path, begin: str, end: str, text: str, fallback: Path) -> None:
    block = f"{begin}\n{text}\n{end}"
    if path.exists():
        doc = path.read_text(encoding="utf-8")
        pat = re.compile(re.escape(begin) + r".*?" + re.escape(end), re.S)
        if pat.search(doc):
            path.write_text(pat.sub(lambda _m: block, doc), encoding="utf-8")
            log(f"updated tables in {path}")
            return
    fallback.write_text(block, encoding="utf-8")
    log(f"wrote tables to {fallback}")


def build_tables(prices: pd.DataFrame, res: pd.DataFrame, stations: pd.DataFrame, summary: pd.DataFrame) -> str:
    cents = lambda v: "" if pd.isna(v) else f"{100 * v:.0f}"  # noqa: E731
    parts = []
    parts.append("Generated by `scripts/run_third_inch_pricing.py`. Fair YES price = share of complete months "
                 "1991-2025 whose total exceeded the strike, in cents. \"Smoothed\" = zero-inflated gamma fit to "
                 "1951-2025. CI = 90% Wilson interval on the 1991-2025 share. Informative = priced 5-95 cents.\n")

    # Table 1: station summary
    parts.append("**Table 1. Each Kalshi rain station: how many strikes carry information, today's ladder vs a third-inch ladder "
                 "(mean over the 12 calendar months, 1951-2025).** Coarsest bin = largest share of months the ladder lumps "
                 "into one outcome bin. Put fit = share of a PRF-style monthly put's variance the best NO ladder copies.")
    s = summary.sort_values(["important", "informative_today"], ascending=[False, True])
    parts.append(md_table(s, ["city", "station_key", "flag", "median_month_in", "p_le_1in", "informative_today",
                              "informative_third", "max_bin_today", "max_bin_third", "r2_today", "r2_third"],
                          ["City", "Station", "Why it matters", "Median month (in)", "P(month <= 1 in)",
                           "Informative strikes today", "Third-inch", "Coarsest bin today", "Third-inch",
                           "Put fit today", "Third-inch"],
                          {"p_le_1in": lambda v: f"{v:.2f}", "informative_today": lambda v: f"{v:.1f}",
                           "informative_third": lambda v: f"{v:.1f}", "max_bin_today": lambda v: f"{v:.2f}",
                           "max_bin_third": lambda v: f"{v:.2f}", "r2_today": lambda v: f"{v:.2f}",
                           "r2_third": lambda v: f"{v:.2f}", "median_month_in": lambda v: f"{v:.2f}"}))
    parts.append("")

    # Table 2: third-inch fair prices for the important stations, growing-season months
    for key in ["DFW", "OKC", "SGF", "SAT", "TPA", "DEN", "ABQ", "ORD"]:
        p = prices[(prices["station_key"] == key) & (prices["strike_in"] <= 4.0 + 1e-9)]
        if p.empty:
            continue
        city = stations.loc[stations["station_key"] == key, "city"].iloc[0]
        wide = p.pivot_table(index="strike_in", columns="month", values=f"p_yes_{PRIMARY}")
        wide = wide.reindex(columns=MONTHS)
        wide.columns = MONTH_ABBR
        wide.index = [f"> {k:.2f}" for k in wide.index]
        parts.append(f"**Table 2-{key}. {city} ({key}): fair YES price in cents of \"more than K inches\" by month, 1991-2025.** "
                     "Rows at whole inches are what Kalshi lists today; the others are the third-inch additions.")
        lines = ["| Strike | " + " | ".join(MONTH_ABBR) + " |", "|---|" + "---|" * 12]
        for idx, row in wide.iterrows():
            lines.append(f"| {idx} | " + " | ".join(cents(v) for v in row.values) + " |")
        parts.append("\n".join(lines))
        parts.append("")

    # Table 3: sampling uncertainty: CI width by price band
    q = prices.dropna(subset=["ci90_width"]).copy()
    q["band"] = pd.cut(q[f"p_yes_{PRIMARY}"], [-0.001, 0.05, 0.2, 0.4, 0.6, 0.8, 0.95, 1.0],
                       labels=["0-5c", "5-20c", "20-40c", "40-60c", "60-80c", "80-95c", "95-100c"])
    g = q.groupby("band", observed=True).agg(n=("strike_in", "count"), ci_width=("ci90_width", "mean"),
                                             gamma_gap=("p_yes_gamma", lambda x: np.nan)).reset_index()
    q["gap"] = (q["p_yes_gamma"] - q[f"p_yes_{PRIMARY}"]).abs()
    g["gamma_gap"] = q.groupby("band", observed=True)["gap"].mean().values
    g["shift"] = q.groupby("band", observed=True)["p_yes_shift_early_to_recent"].apply(lambda x: x.abs().mean()).values
    parts.append("**Table 3. How precise a climatological price is.** All station-months and third-inch strikes. CI width = "
                 "mean 90% Wilson interval width on the 1991-2025 share (35 years). Smoothed gap = mean absolute difference "
                 "between the gamma-smoothed and the empirical price. Trend shift = mean absolute change in the fair price "
                 "from 1951-1990 to 1991-2025.")
    parts.append(md_table(g, ["band", "n", "ci_width", "gamma_gap", "shift"],
                          ["Fair price band", "Strike-months", "CI width (cents)", "Smoothed gap (cents)", "Trend shift (cents)"],
                          {"ci_width": cents, "gamma_gap": cents, "shift": cents, "n": lambda v: f"{int(v)}"}))
    parts.append("")

    # Table 4: resolution pooled by aridity class
    r = res.copy()
    r["arid"] = np.where(r["p_le_1in"] > 0.5, "dry month (P(<=1 in) > 0.5)",
                         np.where(r["p_le_1in"] > 0.2, "mid (0.2-0.5)", "wet month (P(<=1 in) <= 0.2)"))
    g4 = (r.groupby(["arid", "ladder"]).agg(n=("month", "count"), informative=("informative", "mean"),
                                           max_bin=("max_bin", "mean"), r2=("approx_r2", "mean"),
                                           legs=("approx_legs", "mean")).reset_index())
    parts.append("**Table 4. Ladder resolution by how dry the month is (all 37 stations x 12 months, 1951-2025).** "
                 "Legs = strikes the best put-copying ladder actually uses.")
    parts.append(md_table(g4, ["arid", "ladder", "n", "informative", "max_bin", "r2", "legs"],
                          ["Month class", "Ladder", "Station-months", "Informative strikes", "Coarsest bin", "Put fit (R2)", "Legs used"],
                          {"n": lambda v: f"{int(v)}", "informative": lambda v: f"{v:.1f}", "legs": lambda v: f"{v:.1f}"}))
    parts.append("")

    # Table 5: fee at fair price for whole vs third strikes (important stations)
    f = prices[prices["station_key"].isin(stations.loc[stations["important"], "station_key"])].copy()
    f["kind"] = np.where(f["is_whole_inch"], "whole-inch strikes", "third-inch additions")
    g5 = f.groupby("kind").agg(n=("strike_in", "count"), informative=("informative_recent35", "mean"),
                               fee=("taker_fee_cents_per_contract", "mean"),
                               fee_inf=("taker_fee_cents_per_contract",
                                        lambda x: x[f.loc[x.index, "informative_recent35"]].mean())).reset_index()
    parts.append("**Table 5. Taker fee at the fair price, 0.07 x P x (1 - P) per contract, important stations.** "
                 "Fees are highest near 50 cents, so informative strikes cost more to trade than the near-certain ones.")
    parts.append(md_table(g5, ["kind", "n", "informative", "fee", "fee_inf"],
                          ["Strikes", "Strike-months", "Share informative", "Mean fee (cents)", "Mean fee, informative only (cents)"],
                          {"n": lambda v: f"{int(v)}", "informative": lambda v: f"{100 * v:.0f}%"}))
    return "\n".join(parts)


# ---------------------------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------------------------

def _style(ax):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(C_GRID)
    ax.tick_params(colors=C_TEXT2, labelsize=8, length=0)
    ax.yaxis.grid(True, color=C_GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def fig_heatmaps(prices: pd.DataFrame, stations: pd.DataFrame, keys: list[str], path: Path):
    cmap = matplotlib.colors.LinearSegmentedColormap.from_list("blues", SEQ_BLUES)
    fig, axes = plt.subplots(2, 4, figsize=(15, 7.2), facecolor="#fcfcfb")
    for ax, key in zip(axes.ravel(), keys):
        p = prices[(prices["station_key"] == key) & (prices["strike_in"] <= 5.0 + 1e-9)]
        wide = p.pivot_table(index="strike_in", columns="month", values=f"p_yes_{PRIMARY}").reindex(columns=MONTHS)
        img = ax.imshow(wide.to_numpy() * 100, aspect="auto", cmap=cmap, vmin=0, vmax=100, origin="lower")
        ax.set_yticks(range(len(wide.index)))
        ax.set_yticklabels([f"{k:.2f}" for k in wide.index], fontsize=7, color=C_TEXT2)
        for i, k in enumerate(wide.index):
            if np.isclose(k % 1, 0):
                ax.get_yticklabels()[i].set_fontweight("bold")
        ax.set_xticks(range(12))
        ax.set_xticklabels([m[0] for m in MONTH_ABBR], fontsize=7, color=C_TEXT2)
        city = stations.loc[stations["station_key"] == key, "city"].iloc[0]
        ax.set_title(f"{city} ({key})", fontsize=10, color=C_TEXT, loc="left")
        ax.tick_params(length=0)
        for s in ax.spines.values():
            s.set_visible(False)
        for i in range(len(wide.index)):
            for j in range(12):
                v = wide.to_numpy()[i, j]
                if not np.isnan(v):
                    ax.text(j, i, f"{100 * v:.0f}", ha="center", va="center", fontsize=5.5,
                            color="#f0efec" if v > 0.55 else C_TEXT)
    cb = fig.colorbar(img, ax=axes.ravel().tolist(), fraction=0.015, pad=0.01)
    cb.set_label("fair YES price, cents (share of months 1991-2025 above the strike)", fontsize=8, color=C_TEXT2)
    cb.ax.tick_params(labelsize=7, colors=C_TEXT2)
    fig.suptitle("Fair price of \"more than K inches\" at third-inch strikes (bold rows = strikes Kalshi lists today)",
                 fontsize=12, color=C_TEXT, x=0.01, ha="left")
    fig.text(0.01, 0.005, "Strike in inches on the y axis, calendar month on the x axis. Source: NWS station totals via ACIS; "
             "complete months only.", fontsize=7.5, color=C_TEXT2)
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def fig_informative(summary: pd.DataFrame, path: Path):
    s = summary.sort_values("p_le_1in", ascending=False).reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(13, 5.2), facecolor="#fcfcfb")
    x = np.arange(len(s))
    w = 0.38
    ax.bar(x - w / 2, s["informative_today"], width=w - 0.04, color=C_BLUE, label="today's whole-inch ladder")
    ax.bar(x + w / 2, s["informative_third"], width=w - 0.04, color=C_ORANGE, label="third-inch ladder, same top strike")
    ax.set_xticks(x)
    ax.set_xticklabels(s["station_key"], rotation=0, fontsize=7.5, color=C_TEXT2)
    ax.set_ylabel("strikes priced 5-95 cents (mean over 12 months)", fontsize=8.5, color=C_TEXT2)
    ax.set_title("Driest stations on the left: today's ladder leaves them with one or two usable strikes",
                 fontsize=11, color=C_TEXT, loc="left")
    ax.legend(frameon=False, fontsize=8.5, loc="upper left")
    _style(ax)
    ax2 = ax.secondary_xaxis("bottom")
    ax2.set_xticks(x)
    ax2.set_xticklabels([f"{v:.0%}" for v in s["p_le_1in"]], fontsize=6.5, color=C_TEXT2)
    ax2.tick_params(pad=14, length=0)
    ax2.spines["bottom"].set_visible(False)
    fig.text(0.01, -0.02, "Second row under each station: share of months 1951-2025 with 1 inch or less (the lowest strike Kalshi lists).",
             fontsize=7.5, color=C_TEXT2)
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def fig_uncertainty(prices: pd.DataFrame, stations: pd.DataFrame, cases: list[tuple[str, int]], path: Path):
    fig, axes = plt.subplots(1, len(cases), figsize=(4.2 * len(cases), 4.2), facecolor="#fcfcfb", sharey=True)
    for ax, (key, mon) in zip(np.atleast_1d(axes), cases):
        p = prices[(prices["station_key"] == key) & (prices["month"] == mon) & (prices["strike_in"] <= 6 + 1e-9)]
        k = p["strike_in"].to_numpy()
        y = 100 * p[f"p_yes_{PRIMARY}"].to_numpy()
        ax.fill_between(k, 100 * p["ci90_lo"], 100 * p["ci90_hi"], color=C_BLUE, alpha=0.15, linewidth=0, label="90% interval (1991-2025)")
        ax.plot(k, y, color=C_BLUE, linewidth=2, label="empirical 1991-2025")
        ax.plot(k, 100 * p["p_yes_std75"], color=C_AQUA, linewidth=2, label="empirical 1951-2025")
        ax.plot(k, 100 * p["p_yes_gamma"], color=C_ORANGE, linewidth=2, linestyle="--", label="gamma-smoothed 1951-2025")
        whole = p[p["is_whole_inch"]]
        ax.scatter(whole["strike_in"], 100 * whole[f"p_yes_{PRIMARY}"], s=36, color=C_BLUE, zorder=3,
                   edgecolor="#fcfcfb", linewidth=1.2)
        city = stations.loc[stations["station_key"] == key, "city"].iloc[0]
        ax.set_title(f"{city}, {MONTH_ABBR[mon - 1]}", fontsize=10, color=C_TEXT, loc="left")
        ax.set_xlabel("strike K (inches)", fontsize=8.5, color=C_TEXT2)
        _style(ax)
        ax.set_ylim(0, 100)
    np.atleast_1d(axes)[0].set_ylabel("fair YES price, cents", fontsize=8.5, color=C_TEXT2)
    np.atleast_1d(axes)[0].legend(frameon=False, fontsize=7.5, loc="upper right")
    fig.suptitle("Fair price curves: the whole-inch dots are all today's ladder can quote", fontsize=11, color=C_TEXT,
                 x=0.01, ha="left")
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def fig_putfit(res: pd.DataFrame, stations: pd.DataFrame, keys: list[str], path: Path):
    fig, axes = plt.subplots(2, 4, figsize=(15, 6.4), facecolor="#fcfcfb", sharey=True)
    colors = {"today (listed whole inches)": C_BLUE, "half-inch to same max": C_AQUA, "third-inch to same max": C_ORANGE}
    for ax, key in zip(axes.ravel(), keys):
        r = res[res["station_key"] == key]
        for name, g in r.groupby("ladder"):
            g = g.sort_values("month")
            ax.plot(g["month"], g["approx_r2"], color=colors[name], linewidth=2, marker="o", markersize=4,
                    markeredgecolor="#fcfcfb", label=name)
        city = stations.loc[stations["station_key"] == key, "city"].iloc[0]
        ax.set_title(f"{city} ({key})", fontsize=10, color=C_TEXT, loc="left")
        ax.set_xticks(MONTHS)
        ax.set_xticklabels([m[0] for m in MONTH_ABBR], fontsize=7.5, color=C_TEXT2)
        ax.set_ylim(0, 1.02)
        _style(ax)
    axes[0, 0].set_ylabel("put variance copied (R2)", fontsize=8, color=C_TEXT2)
    axes[1, 0].set_ylabel("put variance copied (R2)", fontsize=8, color=C_TEXT2)
    axes[0, 0].legend(frameon=False, fontsize=7.5, loc="lower left")
    fig.suptitle("How well each ladder copies a PRF-style monthly put (trigger 90% of the month's mean, 1951-2025)",
                 fontsize=11, color=C_TEXT, x=0.01, ha="left")
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------------------------

def main():
    stations = load_stations()
    monthly = load_monthly()
    ladders = listed_ladders()
    log(f"{len(stations)} stations; {len(monthly)} station records")

    prices, res = [], []
    for _, s in stations.iterrows():
        key = s["station_key"]
        if key not in monthly:
            log(f"  no station record for {key}, skipping")
            continue
        listed = ladders.get(s["series_ticker"], DEFAULT_LADDER)
        p = price_station(key, monthly[key], max(listed))
        if p.empty:
            log(f"  {key}: too short, skipping")
            continue
        p.insert(0, "series_ticker", s["series_ticker"])
        p.insert(1, "city", s["city"])
        prices.append(p)
        r = resolution_station(key, monthly[key], listed)
        r.insert(0, "series_ticker", s["series_ticker"])
        r.insert(1, "city", s["city"])
        res.append(r)
    prices = add_prices_and_fees(pd.concat(prices, ignore_index=True))
    res = pd.concat(res, ignore_index=True)

    # consistency check against doc 08's training-window leg probabilities (DFW Jan, 1 in, 1951-2009)
    dfw = monthly["DFW"][1].loc[1951:2009].dropna()
    chk = float((dfw <= 1.0 + 1e-9).mean())
    log(f"check: P(DFW Jan <= 1 in | 1951-2009) = {chk:.6f} (doc 08 weights file: 0.305085)")
    assert abs(chk - 0.305085) < 1e-4, "station climatology no longer matches doc 08"

    # station summary
    piv = res.pivot_table(index="station_key", columns="ladder",
                          values=["informative", "max_bin", "approx_r2"], aggfunc="mean")
    summary = stations.set_index("station_key").loc[piv.index, ["series_ticker", "city", "important", "is_prf_site", "is_top_volume", "total_volume"]].copy()
    summary["informative_today"] = piv[("informative", "today (listed whole inches)")]
    summary["informative_half"] = piv[("informative", "half-inch to same max")]
    summary["informative_third"] = piv[("informative", "third-inch to same max")]
    summary["max_bin_today"] = piv[("max_bin", "today (listed whole inches)")]
    summary["max_bin_third"] = piv[("max_bin", "third-inch to same max")]
    summary["r2_today"] = piv[("approx_r2", "today (listed whole inches)")]
    summary["r2_half"] = piv[("approx_r2", "half-inch to same max")]
    summary["r2_third"] = piv[("approx_r2", "third-inch to same max")]
    clim = res[res["ladder"].str.startswith("today")].groupby("station_key").agg(
        median_month_in=("median_rain_in", "median"), p_le_1in=("p_le_1in", "mean"), max_strike_in=("max_strike_in", "first"))
    summary = summary.join(clim)
    summary["flag"] = np.where(summary["is_prf_site"] & summary["is_top_volume"], "PRF site, top-10 volume",
                               np.where(summary["is_prf_site"], "PRF study site",
                                        np.where(summary["is_top_volume"], "top-10 volume", "")))
    summary = summary.reset_index()

    prices.to_csv(PROCESSED / "third_inch_fair_prices.csv", index=False)
    res.to_csv(PROCESSED / "third_inch_ladder_resolution.csv", index=False)
    summary.to_csv(PROCESSED / "third_inch_station_summary.csv", index=False)
    log(f"prices: {len(prices)} rows; resolution: {len(res)} rows; summary: {len(summary)} stations")

    keys = ["DFW", "OKC", "SGF", "SAT", "TPA", "DEN", "ABQ", "ORD"]
    fig_heatmaps(prices, stations, keys, FIGURES / "x1_third_inch_fair_price_heatmaps.png")
    fig_informative(summary, FIGURES / "x1_informative_strikes_by_station.png")
    fig_uncertainty(prices, stations, [("ABQ", 7), ("DEN", 5), ("DFW", 5), ("ORD", 7)], FIGURES / "x1_fair_price_uncertainty.png")
    fig_putfit(res, stations, keys, FIGURES / "x1_put_fit_by_ladder.png")

    text = build_tables(prices, res, stations, summary)
    replace_between_markers(DOC, "<!-- BEGIN AUTO: third-inch pricing tables (scripts/run_third_inch_pricing.py) -->",
                            "<!-- END AUTO: third-inch pricing tables (scripts/run_third_inch_pricing.py) -->",
                            text, PROCESSED / "third_inch_tables.md")

    # headline numbers for the doc
    imp = summary[summary["important"]]
    log("\nHEADLINES")
    log(f"  important stations: {len(imp)}; mean informative strikes today {imp['informative_today'].mean():.2f} "
        f"vs third-inch {imp['informative_third'].mean():.2f}; all stations {summary['informative_today'].mean():.2f} vs {summary['informative_third'].mean():.2f}")
    log(f"  put fit R2 today {summary['r2_today'].mean():.3f}, half {summary['r2_half'].mean():.3f}, third {summary['r2_third'].mean():.3f}")
    dry = res[res["p_le_1in"] > 0.5]
    for lad, g in dry.groupby("ladder"):
        log(f"  dry months ({len(g)}): {lad}: informative {g['informative'].mean():.2f}, max_bin {g['max_bin'].mean():.2f}, r2 {g['approx_r2'].mean():.2f}")
    inf = prices[prices["informative_recent35"]]
    log(f"  informative strike-months: CI width mean {inf['ci90_width'].mean():.3f}, median {inf['ci90_width'].median():.3f}")
    log(f"  |gamma - empirical| mean {np.nanmean((prices['p_yes_gamma'] - prices['p_yes_recent35']).abs()):.3f}")
    sh = prices.dropna(subset=["p_yes_shift_early_to_recent"])
    log(f"  trend: mean |shift| {sh['p_yes_shift_early_to_recent'].abs().mean():.3f}; share > 0.15: {(sh['p_yes_shift_early_to_recent'].abs() > 0.15).mean():.3f}; "
        f"mean signed shift {sh['p_yes_shift_early_to_recent'].mean():+.3f}")
    by_st = sh[sh['informative_recent35']].groupby("station_key")["p_yes_shift_early_to_recent"].mean().sort_values()
    log("  signed shift by station (informative strikes): " + ", ".join(f"{k} {v:+.2f}" for k, v in by_st.items()))


if __name__ == "__main__":
    main()
