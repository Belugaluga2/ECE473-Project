"""B3: do our station monthly totals reproduce how Kalshi actually settled its monthly-rain markets?

Run from the repo root after scripts/pull_stations.py:
    python scripts/check_kalshi_settlement.py [--refresh-kalshi] [--use-shared-parquet]

For every settled market of every mapped monthly-rain series this script
    1. reads the market's own settlement station from rules_primary (KXRAINCHIM switched from
       Chicago Midway to O'Hare in Sep 2026, so the station is resolved per market),
    2. infers each month's settled range from the ladder (total above the highest YES strike and
       at or below the lowest NO strike) and Kalshi's reported expiration_value,
    3. compares with (a) our ACIS station monthly total and (b) the NWS daily climate report (CLI)
       month-to-date total on the month's last day, as archived by the Iowa Environmental Mesonet,
    4. classifies every disagreement by likely cause.

Outputs
    data/processed/kalshi_settlement_vs_station.csv   one row per settled market
    docs/figures/b3_kalshi_value_minus_station.png    Kalshi settlement value minus station total
    docs/figures/b3_strike_margin_sensitivity.png     how often an error of e inches flips a strike
    data/raw/stations/settlement_check_tables.md      markdown tables used in docs/analysis/06c
"""
from __future__ import annotations

import argparse
import sys
from datetime import date

import numpy as np
import pandas as pd

from agri_hedge.config import FIGURES, PROCESSED
from agri_hedge.stations import (RAW_STATIONS, cli_value_to_inches, event_month,
                                 fetch_acis_daily, fetch_iem_cli_day, infer_settled_range,
                                 kalshi_series_markets, latest_complete_month, market_yes,
                                 month_end, normalize_market, parse_settlement_location,
                                 value_in_range)

KALSHI_DIR = RAW_STATIONS / "kalshi"
DAILY_DIR = RAW_STATIONS / "acis_daily"
IEM_DIR = RAW_STATIONS / "iem_cli"
SHARED_PARQUET = PROCESSED / "kalshi_rain_markets.parquet"


# ---------------------------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------------------------
def load_markets(smap: pd.DataFrame, refresh: bool, use_shared: bool) -> pd.DataFrame:
    """Normalized settled markets for every mapped series, one row per market."""
    series = smap["series_ticker"].dropna().unique()
    default_code = (smap.sort_values("events_to").groupby("series_ticker")["station_key"]
                    .last().to_dict())
    rows = []
    if use_shared and SHARED_PARQUET.exists():
        raw = pd.read_parquet(SHARED_PARQUET)
        raw = raw.rename(columns={"expiration_value_text": "expiration_value"})
        records = [r for r in raw.to_dict("records") if r.get("series_ticker") in series]
        source = "shared_parquet"
    else:
        records = []
        for s in series:
            for mk in kalshi_series_markets(s, KALSHI_DIR, refresh=refresh):
                mk["series_ticker"] = s
                records.append(mk)
        source = "kalshi_api"
    for mk in records:
        if (mk.get("result") or "") not in ("yes", "no"):
            continue
        n = normalize_market(mk)
        loc = parse_settlement_location(n.get("rules_primary"))
        ym = event_month(n["event_ticker"], n.get("rules_primary"))
        if ym is None:
            continue
        rows.append({
            "series_ticker": n["series_ticker"], "event_ticker": n["event_ticker"],
            "ticker": n["ticker"], "year": ym[0], "month": ym[1],
            "station_key": loc["code"] or default_code.get(n["series_ticker"], ""),
            "station_from_rules": bool(loc["code"]),
            "strike_type": n.get("strike_type"), "floor_strike": n.get("floor_strike"),
            "cap_strike": n.get("cap_strike"), "strike_inferred": bool(n.get("strike_inferred")),
            "result": n["result"], "expiration_value_in": n["expiration_value_in"],
            "settle_source": n["settle_source"], "close_time": n.get("close_time"),
            "settlement_ts": n.get("settlement_ts"), "status": n.get("status"),
            "volume": pd.to_numeric(n.get("volume_fp", n.get("volume")), errors="coerce"),
            "_raw": mk})
    df = pd.DataFrame(rows)
    print(f"{len(df)} settled markets from {source}")
    return df


def load_cli_month_totals(months: list[tuple[int, int]]) -> pd.DataFrame:
    """NWS CLI month-to-date precipitation on each month's last day (IEM archive)."""
    parts = []
    for y, m in months:
        day = month_end(y, m)
        d = fetch_iem_cli_day(day, IEM_DIR)
        d["year"], d["month"] = y, m
        parts.append(d)
    cli = pd.concat(parts, ignore_index=True)
    cli["cli_total_in"] = cli["precip_month"].map(cli_value_to_inches)
    cli["station_key"] = cli["station"].str[1:]
    return cli[["station_key", "year", "month", "cli_total_in", "product", "name"]]


def load_station_daily(smap: pd.DataFrame, end: str) -> dict[str, pd.DataFrame]:
    """Single-station daily frames from the ACIS cache written by pull_stations.py."""
    out = {}
    for _, r in smap.dropna(subset=["acis_uid"]).drop_duplicates("station_key").iterrows():
        out[r["station_key"]] = fetch_acis_daily(r["record_start"], end, uid=int(r["acis_uid"]),
                                                 cache_dir=DAILY_DIR)
    return out


# ---------------------------------------------------------------------------------------------
# Diagnosis
# ---------------------------------------------------------------------------------------------
def round_float_1(x: float) -> float:
    """Round a 2-decimal total to 0.1 in the way Kalshi's reported values are rounded.

    Kalshi's values match Python's round() on the binary double in all five half-way cases seen
    (0.65 -> 0.7, 2.35 -> 2.4, 6.15 -> 6.2, 6.95 -> 7.0 but 4.85 -> 4.8, because 4.85 is stored
    as 4.8499...). numpy's round (round-half-even after scaling) would give 0.6 for 0.65.
    """
    return round(round(float(x), 2), 1)


def value_note(r) -> str:
    """Why Kalshi's reported expiration_value differs from the station total (event level)."""
    kv, st, cl = r["kalshi_value_in"], r["station_total_in"], r["cli_total_in"]
    if pd.isna(kv) or pd.isna(st):
        return ""
    if abs(kv - st) < 0.005:
        return "exact"
    if abs(round_float_1(st) - kv) < 0.005:
        return "rounded to 0.1 in"
    if pd.notna(cl) and abs(kv - cl) < 0.005:
        return "matches NWS CLI month-end report; station archive revised later"
    return "matches neither station nor final CLI"


def shifted_totals(daily: pd.DataFrame, y: int, m: int) -> dict[str, float]:
    """Monthly total with the window moved one day earlier / later (month-boundary test)."""
    first = pd.Timestamp(y, m, 1)
    last = first + pd.offsets.MonthEnd(0)
    s = daily.set_index("date")["precip_in"]

    def tot(a, b):
        return round(float(s.loc[a:b].sum(min_count=1)), 2)
    return {"minus1": tot(first - pd.Timedelta(days=1), last - pd.Timedelta(days=1)),
            "plus1": tot(first + pd.Timedelta(days=1), last + pd.Timedelta(days=1))}


def classify(r: pd.Series, daily: pd.DataFrame | None, alt_totals: dict) -> str:
    """Most likely cause of a market where the station-implied outcome differs from Kalshi's."""
    k_yes = r["result"] == "yes"
    strike = r["floor_strike"]
    if r["n_missing"] and r["n_missing"] > 0:
        return f"missing station data ({int(r['n_missing'])} days)"
    if pd.notna(r["cli_total_in"]) and r["cli_yes"] == k_yes and \
            abs(r["cli_total_in"] - r["station_total_in"]) >= 0.005:
        return (f"late correction: NWS CLI month-end total {r['cli_total_in']:.2f} in matched "
                f"Kalshi; archive now {r['station_total_in']:.2f} in")
    if r["closed_early"] and k_yes:
        return ("early YES on preliminary intra-month data that was later revised down "
                f"(final {r['station_total_in']:.2f} in <= strike {strike:g})")
    kv = r["kalshi_value_in"]
    if pd.notna(kv):
        r1 = round_float_1(r["station_total_in"])
        if market_yes(r["strike_type"], r1, strike, r["cap_strike"]) == k_yes and                 abs(r1 - kv) < 0.005:
            return (f"rounding: Kalshi value {kv:g} in is the station total "
                    f"{r['station_total_in']:.2f} rounded to 0.1 in")
        if market_yes(r["strike_type"], kv, strike, r["cap_strike"]) == k_yes:
            src = "TWC" if r["settle_source"] == "TWC" else "settlement source"
            return (f"data error / source mismatch: Kalshi value {kv:g} in ({src}) vs station "
                    f"{r['station_total_in']:.2f} in and CLI {r['cli_total_in']:.2f} in")
        return f"Kalshi outcome inconsistent with its own reported value {kv:g} in"
    if r["station_total_in"] == 0 and r["n_trace"] > 0:
        return "trace handling (trace counted as 0)"
    if daily is not None:
        for tag, tot in shifted_totals(daily, r["year"], r["month"]).items():
            if market_yes(r["strike_type"], tot, strike, r["cap_strike"]) == k_yes:
                return f"month boundary / time zone (window shifted {tag} day gives {tot:.2f} in)"
    for code, tot in alt_totals.items():
        if market_yes(r["strike_type"], tot, strike, r["cap_strike"]) == k_yes:
            return f"wrong station mapping? CLI{code} total {tot:.2f} in matches Kalshi"
    return "unexplained"


def build_comparison(mk: pd.DataFrame, monthly: pd.DataFrame, cli: pd.DataFrame,
                     daily: dict[str, pd.DataFrame], smap: pd.DataFrame) -> tuple:
    """Per-market and per-event comparison tables."""
    mon = monthly[monthly["source"] == "acis_station"][
        ["station_key", "year", "month", "precip_in", "n_missing", "n_trace"]].rename(
        columns={"precip_in": "station_total_in"})
    ev_rows = []
    for ev, g in mk.groupby("event_ticker"):
        rng = infer_settled_range(list(g["_raw"]))
        ev_rows.append({"event_ticker": ev, "range_label": rng["label"], "range_lo": rng["lo"],
                        "range_hi": rng["hi"], "range_consistent": rng["consistent"],
                        "kalshi_value_in": rng["expiration_value"],
                        "event_early_close": rng["early_close"], "rng": rng})
    ev = pd.DataFrame(ev_rows)
    df = mk.merge(ev[["event_ticker", "kalshi_value_in", "range_label", "range_consistent"]],
                  on="event_ticker", how="left")
    df = df.merge(mon, on=["station_key", "year", "month"], how="left")
    df = df.merge(cli[["station_key", "year", "month", "cli_total_in"]],
                  on=["station_key", "year", "month"], how="left")
    month_end_ts = pd.to_datetime(df.apply(lambda r: month_end(r["year"], r["month"]), axis=1),
                                  utc=True) + pd.Timedelta(hours=24)
    df["closed_early"] = pd.to_datetime(df["close_time"], utc=True, format="ISO8601") < month_end_ts - \
        pd.Timedelta(hours=12)
    df["kalshi_yes"] = df["result"] == "yes"
    df["station_yes"] = [market_yes(r.strike_type, r.station_total_in, r.floor_strike,
                                    r.cap_strike) for r in df.itertuples()]
    df["cli_yes"] = [market_yes(r.strike_type, r.cli_total_in, r.floor_strike, r.cap_strike)
                     for r in df.itertuples()]
    df["agree_station"] = pd.Series([None if a is None else a == k for a, k in
                                     zip(df["station_yes"], df["kalshi_yes"])],
                                    index=df.index, dtype=object)
    df["agree_cli"] = pd.Series([None if a is None else a == k for a, k in
                                 zip(df["cli_yes"], df["kalshi_yes"])],
                                index=df.index, dtype=object)
    df["strike_distance_in"] = (df["station_total_in"] - df["floor_strike"]).round(2)

    # Alternate stations for series that changed station (wrong-mapping test).
    series_codes = smap.groupby("series_ticker")["station_key"].apply(list).to_dict()
    causes = []
    for _, r in df.iterrows():
        if r["agree_station"] is True:
            causes.append("")
            continue
        if pd.isna(r["station_total_in"]):
            causes.append("no station total")
            continue
        alts = {}
        for c in series_codes.get(r["series_ticker"], []):
            if c != r["station_key"]:
                hit = mon[(mon.station_key == c) & (mon.year == r["year"]) &
                          (mon.month == r["month"])]
                if len(hit):
                    alts[c] = float(hit["station_total_in"].iloc[0])
        causes.append(classify(r, daily.get(r["station_key"]), alts))
    df["likely_cause"] = causes
    # Event-level: is the station total inside the ladder-implied range?
    ev = ev.merge(df.groupby("event_ticker").agg(
        series_ticker=("series_ticker", "first"), station_key=("station_key", "first"),
        year=("year", "first"), month=("month", "first"),
        station_total_in=("station_total_in", "first"), cli_total_in=("cli_total_in", "first"),
        n_missing=("n_missing", "first"), n_markets=("ticker", "size"),
        n_disagree=("agree_station", lambda a: int((a == False).sum())),  # noqa: E712
        settle_source=("settle_source", lambda s: "/".join(sorted(set(s)))),
        volume=("volume", "sum")).reset_index(), on="event_ticker")
    ev["station_in_range"] = [value_in_range(t, g) for t, g in zip(ev["station_total_in"], ev["rng"])]
    ev["cli_in_range"] = [value_in_range(t, g) for t, g in zip(ev["cli_total_in"], ev["rng"])]
    return df.drop(columns=["_raw"]), ev.drop(columns=["rng"])


# ---------------------------------------------------------------------------------------------
# Figures and tables
# ---------------------------------------------------------------------------------------------
OUTLIER_NOTES = {
    "KXRAINHOUM-26JAN": "HOU Jan 2026: CLI listed Jan 21 as missing\n(counted 0); archive later has 0.39 in",
    "RAINNYCM-24JUN": "NYC Jun 2024: value from 4 PM\npreliminary report of Jun 30",
    "KXRAINHOUM-26FEB": "HOU Feb 2026: 1.70 in no NWS product\n(CLI and CLM both 1.59)",
}


def plot_value_residuals(ev: pd.DataFrame, path) -> None:
    """Kalshi reported value minus ACIS station total, per settled city-month."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    d = ev.dropna(subset=["kalshi_value_in", "station_total_in"]).copy()
    d["resid"] = d["kalshi_value_in"] - d["station_total_in"]
    fig, ax = plt.subplots(figsize=(7.5, 4.8))
    xmax = d["station_total_in"].max() * 1.04 + 0.2
    ax.axhspan(-0.05, 0.05, color="#e8e8e8", zorder=0)
    ax.text(xmax - 0.1, -0.08, "grey band: within 0.05 in (rounding to 0.1 in)", ha="right",
            fontsize=7, color="#555555")
    ax.axhline(0, color="#888888", linewidth=0.8, zorder=1)
    nws = d[d["settle_source"] != "TWC"]
    twc = d[d["settle_source"] == "TWC"]
    ax.scatter(nws["station_total_in"], nws["resid"], s=34, color="#2a78d6", edgecolor="white",
               linewidth=1.0, zorder=3, label=f"NWS-report rules (n={len(nws)})")
    ax.scatter(twc["station_total_in"], twc["resid"], s=40, marker="s", color="#eb6834",
               edgecolor="white", linewidth=1.0, zorder=3, label=f"TWC-report rules (n={len(twc)})")
    offsets = {"KXRAINHOUM-26JAN": (20, 10), "RAINNYCM-24JUN": (24, -16),
               "KXRAINHOUM-26FEB": (20, 4)}
    for _, r in d[d["event_ticker"].isin(OUTLIER_NOTES)].iterrows():
        ax.annotate(OUTLIER_NOTES[r["event_ticker"]], (r["station_total_in"], r["resid"]),
                    xytext=offsets.get(r["event_ticker"], (10, 0)), textcoords="offset points",
                    fontsize=7, color="#333333", va="center",
                    arrowprops={"arrowstyle": "-", "color": "#888888", "linewidth": 0.6})
    ax.set_xlim(0, xmax)
    ax.set_ylim(-0.45, 0.2)
    ax.set_xlabel("ACIS station monthly total (inches)")
    ax.set_ylabel("Kalshi value minus station total (inches)")
    ax.set_title(f"Kalshi's reported settlement value vs our station total, {len(d)} city-months\n"
                 f"(the other {len(ev) - len(d)} settled months have a blank expiration_value)",
                 fontsize=10)
    ax.grid(color="#eeeeee", linewidth=0.6)
    ax.set_axisbelow(True)
    ax.legend(loc="lower right", fontsize=8, frameon=False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def strike_margins(df: pd.DataFrame) -> pd.Series:
    """Per event: smallest |station total - strike| over the event's ladder (inches)."""
    return (df.assign(d=(df["station_total_in"] - df["floor_strike"]).abs())
            .groupby("event_ticker")["d"].min())


def plot_strike_margin(df: pd.DataFrame, monthly: pd.DataFrame, keys: list[str], path) -> dict:
    """Share of months in which a data error of e inches would flip at least one strike."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    m_settled = strike_margins(df.dropna(subset=["station_total_in"])).values
    h = monthly[(monthly["station_key"].isin(keys)) & (monthly["source"] == "acis_station") &
                (monthly["n_missing"] == 0) & (monthly["year"].between(1991, 2025))]
    strikes = np.arange(1, 8)
    m_hist = np.abs(h["precip_in"].values[:, None] - strikes[None, :]).min(axis=1)
    e = np.round(np.arange(0, 0.601, 0.01), 2)
    cdf_s = [(m_settled <= x + 1e-9).mean() * 100 for x in e]
    cdf_h = [(m_hist <= x + 1e-9).mean() * 100 for x in e]
    fig, ax = plt.subplots(figsize=(7, 4.6))
    ax.plot(e, cdf_h, color="#2a78d6", linewidth=2,
            label=f"station months 1991-2025, strikes 1-7 in (n={len(m_hist):,})")
    ax.plot(e, cdf_s, color="#eb6834", linewidth=2, drawstyle="steps-post",
            label=f"settled Kalshi months, real ladders (n={len(m_settled)})")
    marks = {0.05: ("0.05 in: 0.1-in rounding", 30), 0.39: ("0.39 in: HOU Jan 2026 revision", 3)}
    for x, (lab, ytxt) in marks.items():
        ax.axvline(x, color="#555555", linewidth=0.8)
        ax.text(x + 0.008, ytxt, lab, rotation=90, fontsize=7, color="#333333", va="bottom")
    ax.set_xlim(0, 0.6)
    ax.set_ylim(0, 100)
    ax.set_xlabel("Size of a monthly-total error, e (inches)")
    ax.set_ylabel("Months with a strike within e of the total (%)")
    ax.set_title("How often a data error of a given size could flip a Kalshi strike\n"
                 "(a month is at risk if its total lies within e of any strike)", fontsize=10)
    ax.grid(color="#eeeeee", linewidth=0.6)
    ax.set_axisbelow(True)
    ax.legend(loc="upper left", fontsize=8, frameon=False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    pick = {f"hist_within_{x:.2f}": round(float(cdf_h[int(round(x * 100))]), 1)
            for x in (0.01, 0.05, 0.10, 0.39)}
    pick.update({f"settled_within_{x:.2f}": round(float(cdf_s[int(round(x * 100))]), 1)
                 for x in (0.01, 0.05, 0.10, 0.39)})
    pick["hist_months"] = len(m_hist)
    return pick


def md_table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join("" if pd.isna(v) else str(v) for v in r.values) + " |")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--refresh-kalshi", action="store_true")
    ap.add_argument("--use-shared-parquet", action="store_true",
                    help=f"read markets from {SHARED_PARQUET.name} (another workstream) instead")
    ap.add_argument("--today", default=None)
    args = ap.parse_args(argv)
    today = date.fromisoformat(args.today) if args.today else date.today()
    ly, lm = latest_complete_month(today)
    end = month_end(ly, lm)

    smap = pd.read_csv(PROCESSED / "station_map.csv", dtype={"wban": str, "coop": str})
    smap = smap[smap["acis_uid"].notna()]
    monthly = pd.read_csv(PROCESSED / "station_monthly_precip.csv")
    mk = load_markets(smap, args.refresh_kalshi, args.use_shared_parquet)
    complete = (mk["year"] * 100 + mk["month"]) <= ly * 100 + lm
    partial = mk[~complete]
    mk = mk[complete].copy()
    print(f"{len(mk)} markets in complete months; {len(partial)} early-settled markets in the "
          f"current month left out")
    months = sorted({(int(y), int(m)) for y, m in zip(mk["year"], mk["month"])})
    cli = load_cli_month_totals(months)
    daily = load_station_daily(smap, end)
    df, ev = build_comparison(mk, monthly, cli, daily, smap)

    # Current-month early closes: station month-to-date must already exceed the strike.
    mtd_rows = []
    for key, g in partial.groupby("station_key"):
        r = smap[smap["station_key"] == key].iloc[0]
        y, m = int(g["year"].iloc[0]), int(g["month"].iloc[0])
        d = fetch_acis_daily(f"{y}-{m:02d}-01", (pd.Timestamp(today) - pd.Timedelta(days=1))
                             .strftime("%Y-%m-%d"), uid=int(r["acis_uid"]), cache_dir=DAILY_DIR)
        mtd = round(float(d["precip_in"].sum()), 2)
        for _, x in g.iterrows():
            mtd_rows.append({"ticker": x["ticker"], "station_key": key, "result": x["result"],
                             "strike": x["floor_strike"], "station_mtd_in": mtd,
                             "station_days": len(d),
                             "agree": market_yes(x["strike_type"], mtd, x["floor_strike"],
                                                 x["cap_strike"]) == (x["result"] == "yes")})
    mtd = pd.DataFrame(mtd_rows)

    out_cols = ["series_ticker", "event_ticker", "ticker", "year", "month", "station_key",
                "station_from_rules", "strike_type", "floor_strike", "strike_inferred", "result",
                "kalshi_value_in", "range_label", "range_consistent", "settle_source",
                "closed_early", "settlement_ts", "volume", "station_total_in", "n_missing",
                "n_trace", "strike_distance_in", "station_yes", "agree_station", "cli_total_in",
                "cli_yes", "agree_cli", "likely_cause"]
    df[out_cols].sort_values(["series_ticker", "year", "month", "floor_strike"]).to_csv(
        PROCESSED / "kalshi_settlement_vs_station.csv", index=False)

    # Per-city summary.
    df["city_station"] = df["station_key"]
    city = df.groupby(["series_ticker", "station_key"]).agg(
        months=("event_ticker", "nunique"), n_markets=("ticker", "size"),
        n_agree=("agree_station", lambda a: int((a == True).sum())),  # noqa: E712
        n_agree_cli=("agree_cli", lambda a: int((a == True).sum())),  # noqa: E712
        n_cli=("agree_cli", lambda a: int(a.notna().sum())),
        first=("year", lambda s: ""), ).reset_index()
    span = df.groupby(["series_ticker", "station_key"]).apply(
        lambda g: f"{g['year'].min()}-{g.loc[g['year'] == g['year'].min(), 'month'].min():02d}"
                  f" to {g['year'].max()}-{g.loc[g['year'] == g['year'].max(), 'month'].max():02d}",
        include_groups=False)
    city["period"] = [span[(a, b)] for a, b in zip(city["series_ticker"], city["station_key"])]
    city["market_agree_rate"] = city["n_agree"] / city["n_markets"]
    evc = ev.groupby(["series_ticker", "station_key"]).agg(
        months_in_range=("station_in_range", lambda a: int((a == True).sum())),  # noqa: E712
        months_ok=("n_disagree", lambda a: int((a == 0).sum()))).reset_index()
    city = city.merge(evc, on=["series_ticker", "station_key"])
    city["station"] = city["station_key"]
    city = city.drop(columns=["first"])
    plot_value_residuals(ev, FIGURES / "b3_kalshi_value_minus_station.png")
    margin_stats = plot_strike_margin(df, monthly, sorted(df["station_key"].unique()),
                                      FIGURES / "b3_strike_margin_sensitivity.png")

    # Value agreement statistics (final, not early-close values).
    v = ev.dropna(subset=["kalshi_value_in", "station_total_in"]).copy()
    v["abs_diff"] = (v["kalshi_value_in"] - v["station_total_in"]).abs()
    v["exact"] = v["abs_diff"] < 0.005
    v["round1"] = (v["station_total_in"].map(round_float_1) - v["kalshi_value_in"]
                   ).abs() < 0.005
    v["value_note"] = v.apply(value_note, axis=1)
    c2 = ev.dropna(subset=["cli_total_in", "station_total_in"]).copy()
    c2["abs_diff"] = (c2["cli_total_in"] - c2["station_total_in"]).abs()

    tables = []
    tables.append("## Per-city agreement\n\n" + md_table(city[[
        "series_ticker", "station", "period", "months", "n_markets", "n_agree",
        "market_agree_rate", "months_ok", "months_in_range", "n_agree_cli", "n_cli"]].assign(
        market_agree_rate=lambda x: (x["market_agree_rate"] * 100).round(1))))
    tot = {"markets": len(df), "agree": int((df["agree_station"] == True).sum()),  # noqa: E712
           "events": len(ev), "events_ok": int((ev["n_disagree"] == 0).sum()),
           "events_in_range": int((ev["station_in_range"] == True).sum()),  # noqa: E712
           "cli_markets": int(df["agree_cli"].notna().sum()),
           "cli_agree": int((df["agree_cli"] == True).sum()),  # noqa: E712
           "range_inconsistent": int((~ev["range_consistent"]).sum()),
           "values": len(v), "values_exact": int(v["exact"].sum()),
           "values_round1": int(v["round1"].sum()),
           "values_within_0p05": int((v["abs_diff"] <= 0.05).sum()),
           "value_max_diff": round(float(v["abs_diff"].max()), 2) if len(v) else np.nan,
           "cli_station_events": len(c2), "cli_station_exact": int((c2["abs_diff"] < 0.005)
                                                                    .sum()),
           "cli_station_max_diff": round(float(c2["abs_diff"].max()), 2) if len(c2) else np.nan,
           "partial_markets": len(mtd),
           "partial_agree": int(mtd["agree"].sum()) if len(mtd) else 0,
           "strike_inferred": int(df["strike_inferred"].sum()),
           "markets_closed_early": int(df["closed_early"].sum()),
           "events_with_early_close": int(ev["event_early_close"].sum()),
           "months_with_trace_days": int((ev.merge(df[["event_ticker", "n_trace"]]
                                               .drop_duplicates("event_ticker"),
                                               on="event_ticker")["n_trace"] > 0).sum()),
           "min_strike": float(df["floor_strike"].min()),
           "min_abs_strike_distance": float(df["strike_distance_in"].abs().min()),
           "total_volume_contracts": round(float(df["volume"].sum()), 0),
           "near_strike_0p05": int((df["strike_distance_in"].abs() <= 0.05).sum()),
           **margin_stats}
    tables.append("## Totals\n\n" + "\n".join(f"- {k}: {val}" for k, val in tot.items()))
    dis = df[df["agree_station"] != True].sort_values(  # noqa: E712
        ["series_ticker", "year", "month", "floor_strike"])
    tables.append("## Disagreements (station vs Kalshi)\n\n" + md_table(dis[[
        "ticker", "station_key", "floor_strike", "result", "kalshi_value_in", "station_total_in",
        "cli_total_in", "n_missing", "n_trace", "closed_early", "settle_source",
        "likely_cause"]]))
    vd = v[~v["exact"]].sort_values("abs_diff", ascending=False)
    tables.append("## Kalshi value != station total (events)\n\n" + md_table(vd[[
        "event_ticker", "station_key", "kalshi_value_in", "station_total_in", "cli_total_in",
        "settle_source", "event_early_close", "value_note", "n_disagree"]]))
    tables.append("## Value-note counts\n\n" + md_table(
        v["value_note"].value_counts().rename_axis("value_note").reset_index()))
    cd = c2[c2["abs_diff"] >= 0.005].sort_values("abs_diff", ascending=False)
    tables.append("## NWS CLI month-end total != ACIS station total (events)\n\n" + md_table(cd[[
        "event_ticker", "station_key", "cli_total_in", "station_total_in", "kalshi_value_in",
        "n_missing"]]))
    if len(mtd):
        tables.append("## Current-month early closes vs station month-to-date\n\n" +
                      md_table(mtd))
    # Value-reporting precision by period.
    v["decimals"] = v["kalshi_value_in"].map(lambda x: len(f"{x:g}".split(".")[1])
                                             if "." in f"{x:g}" else 0)
    prec = v.groupby(["year", "month"]).agg(
        n=("event_ticker", "size"), exact=("exact", "sum"), round1=("round1", "sum"),
        max_decimals=("decimals", "max")).reset_index()
    tables.append("## Kalshi value precision by month\n\n" + md_table(prec))
    near = df[df["strike_distance_in"].abs() <= 0.10][[
        "ticker", "floor_strike", "station_total_in", "kalshi_value_in", "result",
        "agree_station"]]
    tables.append("## Markets within 0.10 in of the strike\n\n" + md_table(near))
    (RAW_STATIONS / "settlement_check_tables.md").write_text("\n\n".join(tables),
                                                             encoding="utf-8")
    ev = ev.merge(v[["event_ticker", "value_note"]], on="event_ticker", how="left")
    ev.to_csv(RAW_STATIONS / "settlement_check_events.csv", index=False)
    print("\n\n".join(tables))
    return 0


if __name__ == "__main__":
    sys.exit(main())
