"""A1: measure geographic basis risk between Kalshi settlement stations and PRF grids.

Run from the repo root (no network; reads only data/processed):
    python scripts/run_basis_risk.py

Inputs (built by other workstreams, see docs/analysis/06b and 06c):
  station_monthly_precip.csv, station_map.csv, study_grids.csv, prf_ring100_grids.csv,
  ncei_interval_index.parquet + ncei_monthly_precip_grids.parquet   (NCEI regime, primary)
  cpc_interval_index.parquet  + cpc_monthly_precip_grids.parquet    (CPC regime, robustness)
  prf_official_index_ring100.parquet                                (DST check only)

Design
------
* Sites: the 7 PRF study sites + ORD (agri_hedge.locations.ALL_SITES).
* Primary sample: calendar years 1995-2025, the longest span in which all 8 settlement stations
  are single-station records (Denver Intl starts 1994-07). Station months with any missing day
  are dropped; an interval needs both months complete.
* Grid index, NCEI regime: our NCEI rebuild (= the DST to 0.03 points; base 1951-2025).
  CPC regime: our as-settled CPC rebuild (base 1948 to Y-2, what RMA paid on through 2026).
* Station index: 100 x station interval total / station mean for that interval over the SAME
  base years as the grid index (1951-2025 for NCEI; 1948 to Y-2 for CPC). Base years before
  1994-07 (DEN), 1974 (DFW) and 1958-11 (ORD) come from ACIS threaded predecessor sites.
  A "matched-base" variant (suffix _mb) recomputes both indexes on the sample years only.
* Grids: every 0.25-degree cell with data whose centre is within 150 mi of the station (the
  PRF-flagged subset within 100 mi is marked prf_flagged). Long-sample robustness: NCEI,
  1951-2025, same grids (threaded station years included, flagged in the doc).
* Distance decay: corr(d) = c0 exp(-d/L) fitted to the interval-index correlation of every
  grid within 150 mi, by site and season; 200 year-block bootstrap draws for NCEI.
* Best station per farm grid: every Kalshi monthly-rain station within 250 mi of the farm grid
  centre; two-station combinations (average index; payout portfolio) and a leave-one-year-out
  comparison of paired vs best single vs best pair.

Outputs
-------
  data/processed/basis_risk_pairs.csv         one row per (sample, regime, site, grid)
  data/processed/basis_risk_best_station.csv  one row per (regime, farm site, candidate)
  docs/figures/a1_*.png                       six figures
  Markdown tables on stdout (copied into docs/analysis/07_geographic_basis_risk.md).
"""
from __future__ import annotations

import sys
import time

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from agri_hedge.basis import (SEASONS, TRIGGER_FIELDS, best_weight, bootstrap_decay_length,  # noqa: E402
                              exp_decay, fit_exp_decay, index_metrics, loyo_station_selection,
                              payment_factor, pearson, rowwise_pearson, totals_metrics)
from agri_hedge.config import FIGURES, PROCESSED, RAW  # noqa: E402
from agri_hedge.cpc import compute_index, dst_base_end, handbook_base_end, interval_totals  # noqa: E402
from agri_hedge.locations import ALL_SITES  # noqa: E402
from agri_hedge.prf_intervals import INTERVAL_NAMES  # noqa: E402

SAMPLE = (1995, 2025)
LONG_SAMPLE = (1951, 2025)
RING_MI = 150.0
PRF_RING_MI = 100.0
CANDIDATE_MI = 250.0
N_BOOT = 200
SITE_ORDER = ["ABQ", "DEN", "SAT", "DFW", "OKC", "SGF", "TPA", "ORD"]  # roughly dry -> wet
ARID, HUMID = ("ABQ", "DEN"), ("SGF", "TPA")
DISTANCE_BINS = [0, 10, 25, 50, 75, 100, 150]
MIN_SHARE_FOR_CV = 0.75  # candidates enter pair / CV tests only with >= 75% of the best-covered candidate's data
NOT_SETTLING_NOW = {"MDW": "Chicago Midway settled KXRAINCHIM only through Aug 2026"}
REGIME_LABEL = {"ncei": "NCEI nClimGrid (PRF from 2026-08-31)",
                "cpc": "CPC as-settled (PRF through mid-2026)"}

# Palette (validated default categorical slots 1-3; recessive ink and grid).
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, MUTED, GRIDC, LIGHT = "#0b0b0b", "#52514e", "#d9d8d4", "#b7d3f6"
plt.rcParams.update({"font.size": 9, "axes.edgecolor": MUTED, "axes.labelcolor": INK,
                     "xtick.color": MUTED, "ytick.color": MUTED, "axes.grid": True,
                     "grid.color": GRIDC, "grid.linewidth": 0.6, "axes.axisbelow": True,
                     "figure.dpi": 150, "savefig.dpi": 150})


# =================================================================================================
# Helpers
# =================================================================================================
def haversine_vec(lat1, lon1, lat2, lon2):
    """Vectorised great-circle distance in statute miles (same radius as locations.haversine_miles)."""
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 2 * 3958.8 * np.arcsin(np.sqrt(a))


def grid_centres(grid_ids):
    """Vectorised grid_id -> (centre lat, centre lon), same formula as agri_hedge.prf_grid."""
    row, col = np.divmod(np.asarray(grid_ids, dtype=int) - 1, 300)
    return 20.0 + (row + 0.5) * 0.25, -130.0 + (col + 0.5) * 0.25


def fmt(x, nd=2):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "-"
    if isinstance(x, (int, np.integer)):
        return f"{x:,}"
    return f"{x:.{nd}f}"


def md_table(df: pd.DataFrame, nd=2) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for i in range(len(df)):
        vals = [df[c].iloc[i] for c in cols]
        lines.append("| " + " | ".join(v if isinstance(v, str) else fmt(v, nd) for v in vals) + " |")
    return "\n".join(lines)


def season_cols(cols: pd.MultiIndex, season: str) -> np.ndarray:
    return np.isin(cols.get_level_values("interval_name"), SEASONS[season])


# =================================================================================================
# Data loading
# =================================================================================================
def load_stations():
    """Complete station months, interval totals, station indexes (NCEI and CPC bases), threading."""
    m = pd.read_csv(PROCESSED / "station_monthly_precip.csv")
    m = m[(m["n_missing"] == 0) & (m["year"] >= 1948) & (m["year"] <= LONG_SAMPLE[1])].copy()
    m["threaded"] = m["source"] != "acis_station"
    iv = interval_totals(m, value_col="precip_in", id_col="station_key")
    # an interval is "threaded" if either month comes from a predecessor site
    thr = m.set_index(["station_key", "year", "month"])["threaded"]
    from agri_hedge.prf_intervals import INTERVAL_MONTHS
    m1 = iv["interval_name"].map(lambda n: INTERVAL_MONTHS[n][0])
    m2 = iv["interval_name"].map(lambda n: INTERVAL_MONTHS[n][1])
    k1 = pd.MultiIndex.from_arrays([iv["station_key"], iv["year"], m1])
    k2 = pd.MultiIndex.from_arrays([iv["station_key"], iv["year"], m2])
    iv["threaded"] = thr.reindex(k1).to_numpy(bool) | thr.reindex(k2).to_numpy(bool)
    ncei = compute_index(iv, "interval_precip_in", 1951, dst_base_end, id_col="station_key",
                         min_base_years=20)
    cpc = compute_index(iv, "interval_precip_in", 1948, handbook_base_end, id_col="station_key",
                        min_base_years=20)
    iv["index_ncei"] = ncei["index_value"].to_numpy()
    iv["index_cpc"] = cpc["index_value"].to_numpy()
    return m, iv


def load_grids(regime: str):
    """Monthly and interval grid data for a regime, years 1951-2025."""
    if regime == "ncei":
        iv = pd.read_parquet(PROCESSED / "ncei_interval_index.parquet",
                             columns=["grid_id", "year", "interval_name", "interval_precip_in",
                                      "index_value_ours"])
        mo = pd.read_parquet(PROCESSED / "ncei_monthly_precip_grids.parquet",
                             columns=["grid_id", "year", "month", "precip_in"])
    else:
        iv = pd.read_parquet(PROCESSED / "cpc_interval_index.parquet",
                             columns=["grid_id", "year", "interval_name", "interval_precip_in",
                                      "index_value_ours"])
        mo = pd.read_parquet(PROCESSED / "cpc_monthly_precip_grids.parquet",
                             columns=["grid_id", "year", "month", "precip_in"])
    iv = iv.rename(columns={"index_value_ours": "index_value"})
    iv["interval_name"] = iv["interval_name"].astype(str)
    iv = iv[(iv["year"] >= LONG_SAMPLE[0]) & (iv["year"] <= LONG_SAMPLE[1])]
    mo = mo[(mo["year"] >= LONG_SAMPLE[0]) & (mo["year"] <= LONG_SAMPLE[1])]
    return mo, iv


def wide_by_grid(df, col, keys, years):
    """grid_id x MultiIndex(keys) wide table restricted to `years` with a complete column grid."""
    sub = df[(df["year"] >= years[0]) & (df["year"] <= years[1])]
    return sub.set_index(["grid_id"] + keys)[col].unstack(keys)


def full_columns(keys, years):
    y = range(years[0], years[1] + 1)
    if keys[1] == "month":
        return pd.MultiIndex.from_product([y, range(1, 13)], names=keys)
    return pd.MultiIndex.from_product([y, INTERVAL_NAMES], names=keys)


def matched_index_wide(precip_wide: pd.DataFrame) -> pd.DataFrame:
    """Index on the sample's own base: 100 x value / mean over the sample years, per interval."""
    out = precip_wide.copy()
    names = precip_wide.columns.get_level_values("interval_name")
    for name in INTERVAL_NAMES:
        sel = names == name
        mean = precip_wide.loc[:, sel].mean(axis=1, skipna=True)
        out.loc[:, sel] = 100.0 * precip_wide.loc[:, sel].to_numpy() / mean.to_numpy()[:, None]
    return out


# =================================================================================================
# Pair metrics for all grids around each site
# =================================================================================================
def site_rows(site, regime, years, st_month, st_iv, grids, study, prf_ring):
    """Metric rows for every grid within RING_MI of one site's station."""
    s = ALL_SITES[site]
    mcols, icols = full_columns(["year", "month"], years), full_columns(["year", "interval_name"], years)
    sm = (st_month[st_month["station_key"] == site].set_index(["year", "month"])["precip_in"]
          .reindex(mcols).to_numpy())
    si_df = st_iv[st_iv["station_key"] == site].set_index(["year", "interval_name"])
    si = si_df["interval_precip_in"].reindex(icols).to_numpy()
    sx = si_df[f"index_{regime}"].reindex(icols).to_numpy()
    thr = si_df["threaded"].reindex(icols).fillna(False).to_numpy(bool)
    # matched base: station mean over the sample years, per interval
    sx_mb = np.full_like(si, np.nan)
    inames = icols.get_level_values("interval_name").to_numpy()
    for name in INTERVAL_NAMES:
        sel = inames == name
        sx_mb[sel] = 100.0 * si[sel] / np.nanmean(si[sel])
    gm, gi, gx, gx_mb = (grids["month"].reindex(columns=mcols), grids["iv"].reindex(columns=icols),
                         grids["idx"].reindex(columns=icols), grids["idx_mb"].reindex(columns=icols))
    lat, lon = grid_centres(gi.index.to_numpy())
    dist = haversine_vec(s["station_lat"], s["station_lon"], lat, lon)
    keep = np.flatnonzero(dist <= RING_MI)
    months_of = mcols.get_level_values("month").to_numpy()
    st_grid = int(study[(study.site == site) & (study.role == "station")]["grid_id"].item())
    farm_grid = int(study[(study.site == site) & (study.role == "farm")]["grid_id"].item())
    flagged = set(prf_ring[prf_ring.site == site]["grid_id"])
    rows = []
    gm_v, gi_v, gx_v, gxm_v = gm.to_numpy(), gi.to_numpy(), gx.to_numpy(), gx_mb.to_numpy()
    for j in keep:
        gid = int(gi.index[j])
        role = "station_grid" if gid == st_grid else ("farm_grid" if gid == farm_grid else "ring")
        row = {"sample": f"{years[0]}-{years[1]}", "regime": regime, "site": site, "grid_id": gid,
               "role": role, "grid_lat": lat[j], "grid_lon": lon[j], "distance_mi": dist[j],
               "prf_flagged": gid in flagged,
               "share_threaded_intervals": float(np.mean(thr[np.isfinite(si)])) if np.isfinite(si).any() else np.nan}
        row.update(totals_metrics(sm, gm_v[j], months_of, "month"))
        row.update(totals_metrics(si, gi_v[j], inames, "interval"))
        row.update(index_metrics(sx, gx_v[j], inames))
        mb = index_metrics(sx_mb, gxm_v[j], None)
        for k in ("r_index", "rmse_index", "bias_index", "hit_rate90", "miss_rate90",
                  "agreement90", "phi90", "miss_rate70", "p_station90", "p_grid90"):
            row[f"{k}_mb"] = mb[k]
        rows.append(row)
    # arrays for the bootstrap (official index, NCEI and CPC alike)
    arrays = {"gx": gx_v[keep], "sx": sx, "dist": dist[keep],
              "years": icols.get_level_values("year").to_numpy(), "inames": inames}
    return rows, arrays


def grid_tables(mo, iv, years):
    w_month = wide_by_grid(mo, "precip_in", ["year", "month"], years)
    w_iv = wide_by_grid(iv, "interval_precip_in", ["year", "interval_name"], years)
    w_idx = wide_by_grid(iv, "index_value", ["year", "interval_name"], years)
    w_iv = w_iv.reindex(columns=full_columns(["year", "interval_name"], years))
    w_idx = w_idx.reindex(index=w_iv.index, columns=w_iv.columns)
    w_month = w_month.reindex(index=w_iv.index)
    return {"month": w_month, "iv": w_iv, "idx": w_idx, "idx_mb": matched_index_wide(w_iv)}


# =================================================================================================
# Distance decay
# =================================================================================================
def decay_fits(pairs: pd.DataFrame, arrays: dict, boot: bool) -> pd.DataFrame:
    out = []
    for (sample, regime, site), sub in pairs.groupby(["sample", "regime", "site"], sort=False):
        for season, col in (("all", "r_index"), ("warm", "r_index_warm"), ("cool", "r_index_cool")):
            for rmax in (RING_MI, PRF_RING_MI):
                ss = sub[sub["distance_mi"] <= rmax]
                f = fit_exp_decay(ss["distance_mi"], ss[col])
                row = {"sample": sample, "regime": regime, "site": site, "season": season,
                       "max_distance_mi": rmax, **f, "L_lo": np.nan, "L_hi": np.nan,
                       "r_station_grid": sub.loc[sub.role == "station_grid", col].mean(),
                       "r_at_50mi_fit": float(exp_decay(50, f["c0"], f["L"])) if np.isfinite(f["L"]) else np.nan,
                       "d_r080_mi": (float(f["L"] * np.log(f["c0"] / 0.8))
                                     if np.isfinite(f["L"]) and f["c0"] > 0.8 else 0.0 if np.isfinite(f["L"]) else np.nan)}
                key = (sample, regime, site)
                if boot and rmax == RING_MI and key in arrays:
                    a = arrays[key]
                    cols = np.isin(a["inames"], SEASONS[season]) & np.isfinite(a["sx"])
                    m = a["gx"][:, cols]
                    good = np.isfinite(m).all(axis=1)
                    bl = bootstrap_decay_length(m[good], a["sx"][cols], a["dist"][good],
                                                a["years"][cols], n_boot=N_BOOT,
                                                seed=10 * SITE_ORDER.index(site)
                                                + list(SEASONS).index(season))
                    bl = bl[np.isfinite(bl)]
                    if bl.size:
                        row["L_lo"], row["L_hi"] = np.percentile(bl, [2.5, 97.5])
                out.append(row)
    return pd.DataFrame(out)


# =================================================================================================
# Best station per farm grid
# =================================================================================================
def best_station(st_iv, station_map, study, grid_idx_long, regime, years) -> pd.DataFrame:
    rows = []
    icols = full_columns(["year", "interval_name"], years)
    inames = icols.get_level_values("interval_name").to_numpy()
    yrs = icols.get_level_values("year").to_numpy()
    stations = station_map.drop_duplicates("station_key")
    for site in SITE_ORDER:
        farm_gid = int(study[(study.site == site) & (study.role == "farm")]["grid_id"].item())
        flat, flon = grid_centres([farm_gid])
        gx = grid_idx_long.loc[farm_gid].reindex(icols).to_numpy()
        d = haversine_vec(flat[0], flon[0], stations["lat"].to_numpy(), stations["lon"].to_numpy())
        cand = stations.assign(distance_mi=d)[d <= CANDIDATE_MI].sort_values("distance_mi")
        sx_by = {}
        for c in cand.itertuples():
            sx = (st_iv[st_iv.station_key == c.station_key].set_index(["year", "interval_name"])
                  [f"index_{regime}"].reindex(icols).to_numpy())
            sx_by[c.station_key] = sx
            r = {"regime": regime, "farm_site": site, "farm_grid_id": farm_gid,
                 "kind": "single", "candidate": c.station_key, "station_a": c.station_key,
                 "station_b": "", "weight_a": 1.0, "distance_mi": c.distance_mi,
                 "distance_b_mi": np.nan, "series_ticker": c.series_ticker,
                 "is_paired_station": c.station_key == site,
                 "settles_kalshi_now": c.station_key not in NOT_SETTLING_NOW,
                 "kalshi_first_event": c.events_from}
            r.update(index_metrics(sx, gx, inames))
            rows.append(r)
        single = pd.DataFrame([x for x in rows if x["farm_site"] == site and x["regime"] == regime])
        single = single.sort_values("r_index", ascending=False)
        rank = {k: i + 1 for i, k in enumerate(single["candidate"])}
        for x in rows:
            if x["farm_site"] == site and x["regime"] == regime and x["kind"] == "single":
                x["rank_r_index"] = rank[x["candidate"]]
        n_ok = {k: int((np.isfinite(v) & np.isfinite(gx)).sum()) for k, v in sx_by.items()}
        live = [k for k in sx_by if k not in NOT_SETTLING_NOW
                and n_ok[k] >= MIN_SHARE_FOR_CV * max(n_ok.values())]
        dmap = dict(zip(cand["station_key"], cand["distance_mi"]))
        tgt = payment_factor(gx, 90.0)
        for i, a in enumerate(live):
            for b in live[i + 1:]:
                avg = (sx_by[a] + sx_by[b]) / 2.0
                r = {"regime": regime, "farm_site": site, "farm_grid_id": farm_gid,
                     "kind": "avg_index", "candidate": f"{a}+{b}", "station_a": a, "station_b": b,
                     "weight_a": 0.5, "distance_mi": dmap[a], "distance_b_mi": dmap[b],
                     "is_paired_station": False, "settles_kalshi_now": True}
                r.update(index_metrics(avg, gx, inames))
                rows.append(r)
                ok = np.isfinite(sx_by[a]) & np.isfinite(sx_by[b]) & np.isfinite(gx)
                pa, pb = payment_factor(sx_by[a][ok], 90.0), payment_factor(sx_by[b][ok], 90.0)
                w, rr = best_weight(tgt[ok], pa, pb)
                rows.append({"regime": regime, "farm_site": site, "farm_grid_id": farm_gid,
                             "kind": "payout_portfolio", "candidate": f"{a}+{b}", "station_a": a,
                             "station_b": b, "weight_a": w, "distance_mi": dmap[a],
                             "distance_b_mi": dmap[b], "is_paired_station": False,
                             "settles_kalshi_now": True, "n_index": int(ok.sum()),
                             "r_payout90": rr})
        # leave-one-year-out comparison on observations where every live candidate has data
        ok = np.isfinite(gx)
        for k in live:
            ok &= np.isfinite(sx_by[k])
        pays = {k: payment_factor(sx_by[k][ok], 90.0) for k in live}
        cv = loyo_station_selection(tgt[ok], pays, yrs[ok], paired=site)
        rows.append({"regime": regime, "farm_site": site, "farm_grid_id": farm_gid,
                     "kind": "loyo_cv", "candidate": ";".join(live), "station_a": site,
                     "n_index": cv["n"], "is_paired_station": False,
                     "settles_kalshi_now": True,
                     "oos_r_paired": cv["oos_r_paired"], "oos_r_best_single": cv["oos_r_best_single"],
                     "oos_r_best_pair": cv["oos_r_best_pair"],
                     "chosen_single_mode": cv["chosen_single_mode"],
                     "chosen_single_share": cv["chosen_single_share"],
                     "chosen_pair_mode": cv["chosen_pair_mode"],
                     "chosen_pair_share": cv["chosen_pair_share"]})
    return pd.DataFrame(rows)


# =================================================================================================
# Figures
# =================================================================================================
def fig_decay(pairs, fits, path):
    p = pairs[pairs["sample"] == f"{SAMPLE[0]}-{SAMPLE[1]}"]
    fig, axes = plt.subplots(2, 4, figsize=(11, 5.4), sharex=True, sharey=True)
    dd = np.linspace(0, RING_MI, 200)
    for ax, site in zip(axes.ravel(), SITE_ORDER):
        for regime, color, mk, alpha in (("cpc", ORANGE, "x", 0.35), ("ncei", BLUE, "o", 0.45)):
            s = p[(p.regime == regime) & (p.site == site)]
            ax.scatter(s["distance_mi"], s["r_index"], s=6 if mk == "o" else 7, marker=mk,
                       color=color, alpha=alpha, linewidths=0.6 if mk == "x" else 0,
                       label=f"{regime.upper()} grid" if site == SITE_ORDER[0] else None)
            f = fits[(fits["sample"] == f"{SAMPLE[0]}-{SAMPLE[1]}") & (fits.regime == regime)
                     & (fits.site == site) & (fits.season == "all") & (fits.max_distance_mi == RING_MI)].iloc[0]
            ax.plot(dd, exp_decay(dd, f.c0, f.L), color=color, lw=2,
                    ls="-" if regime == "ncei" else "--",
                    label=f"{regime.upper()} fit" if site == SITE_ORDER[0] else None)
        s = p[(p.regime == "ncei") & (p.site == site)]
        for role, mk, lab in (("station_grid", "*", "station's own grid"), ("farm_grid", "^", "farm grid")):
            r = s[s.role == role]
            ax.scatter(r["distance_mi"], r["r_index"], marker=mk, s=70 if mk == "*" else 40,
                       color=INK, edgecolor="white", linewidth=0.8, zorder=5,
                       label=lab if site == SITE_ORDER[0] else None)
        fn = fits[(fits["sample"] == f"{SAMPLE[0]}-{SAMPLE[1]}") & (fits.regime == "ncei")
                  & (fits.site == site) & (fits.season == "all") & (fits.max_distance_mi == RING_MI)].iloc[0]
        ax.set_title(f"{site}: L = {fn.L:,.0f} mi, c0 = {fn.c0:.2f} (NCEI)", fontsize=9)
        ax.set_ylim(0, 1)
        ax.set_xlim(0, RING_MI)
    for ax in axes[1]:
        ax.set_xlabel("Grid centre to station (miles)")
    for ax in axes[:, 0]:
        ax.set_ylabel("Corr(station index, grid index)")
    fig.legend(loc="lower center", ncol=6, frameon=False, fontsize=8, markerscale=1.5)
    fig.suptitle("Station-vs-grid PRF index correlation falls with distance "
                 f"(two-month intervals, {SAMPLE[0]}-{SAMPLE[1]}); lines: c0 exp(-d/L)", fontsize=10)
    fig.tight_layout(rect=(0, 0.05, 1, 0.96))
    fig.savefig(path)
    plt.close(fig)


def fig_miss(pairs, path):
    p = pairs[(pairs["sample"] == f"{SAMPLE[0]}-{SAMPLE[1]}") & (pairs.regime == "ncei")].copy()
    p["bin"] = pd.cut(p["distance_mi"], DISTANCE_BINS)
    fig, axes = plt.subplots(2, 4, figsize=(11, 5.4), sharex=True, sharey=True)
    for ax, site in zip(axes.ravel(), SITE_ORDER):
        s = p[p.site == site]
        ax.scatter(s["distance_mi"], s["miss_rate90"], s=5, color=LIGHT, alpha=0.9, linewidths=0,
                   label="each grid, 90%" if site == SITE_ORDER[0] else None)
        b = s.groupby("bin", observed=True).agg(d=("distance_mi", "mean"), m90=("miss_rate90", "mean"),
                                                m70=("miss_rate70", "mean"))
        ax.plot(b["d"], b["m90"], "-o", color=BLUE, lw=2, ms=4,
                label="bin mean, 90% coverage" if site == SITE_ORDER[0] else None)
        ax.plot(b["d"], b["m70"], "--s", color=ORANGE, lw=2, ms=4,
                label="bin mean, 70% coverage" if site == SITE_ORDER[0] else None)
        ax.axhline(s["miss_if_independent90"].mean(), color=MUTED, ls=":", lw=1.2,
                   label="unrelated hedge, 90%" if site == SITE_ORDER[0] else None)
        st = s[s.role == "station_grid"]
        ax.scatter(st["distance_mi"], st["miss_rate90"], marker="*", s=70, color=INK,
                   edgecolor="white", linewidth=0.8, zorder=5,
                   label="station's own grid, 90%" if site == SITE_ORDER[0] else None)
        ax.set_title(site, fontsize=9)
        ax.set_ylim(0, 1)
        ax.set_xlim(0, RING_MI)
    for ax in axes[1]:
        ax.set_xlabel("Grid centre to station (miles)")
    for ax in axes[:, 0]:
        ax.set_ylabel("Miss rate (share of grid triggers)")
    fig.legend(loc="lower center", ncol=5, frameon=False, fontsize=8, markerscale=1.5)
    fig.suptitle("Miss rate = P(station index not below trigger | grid index below trigger): how often a "
                 f"Kalshi-station hedge misses a PRF payment (NCEI, {SAMPLE[0]}-{SAMPLE[1]})", fontsize=9.5)
    fig.tight_layout(rect=(0, 0.05, 1, 0.96))
    fig.savefig(path)
    plt.close(fig)


def fig_efold(fits, path):
    f = fits[(fits["sample"] == f"{SAMPLE[0]}-{SAMPLE[1]}") & (fits.regime == "ncei")
             & (fits.max_distance_mi == RING_MI)]
    fig, ax = plt.subplots(figsize=(8.5, 3.8))
    width = 0.26
    x = np.arange(len(SITE_ORDER))
    for k, (season, color, hatch, lab) in enumerate((("all", BLUE, "", "all intervals"),
                                                    ("warm", ORANGE, "///", "warm season (May-Sep)"),
                                                    ("cool", AQUA, "...", "cool season (Oct-Mar)"))):
        s = f[f.season == season].set_index("site").reindex(SITE_ORDER)
        L = s["L"].to_numpy()
        lo = np.clip(L - s["L_lo"].to_numpy(), 0, None)
        hi = np.clip(s["L_hi"].to_numpy() - L, 0, None)
        ax.bar(x + (k - 1) * width, L, width - 0.03, color=color, hatch=hatch, edgecolor="white",
               linewidth=0.5, label=lab)
        ax.errorbar(x + (k - 1) * width, L, yerr=[lo, hi], fmt="none", ecolor=INK, lw=0.8, capsize=2)
    ax.set_xticks(x, SITE_ORDER)
    ax.set_ylabel("e-folding distance L (miles)")
    ax.set_xlabel("Site (ordered roughly from arid to humid)")
    ax.set_title("Distance over which station-grid index correlation falls by a factor e "
                 f"(NCEI, {SAMPLE[0]}-{SAMPLE[1]}; bars: 95% year-bootstrap)", fontsize=9)
    ax.legend(frameon=False, fontsize=8, ncol=3, loc="upper left")
    top = np.nanmax(f["L_hi"].to_numpy()) if np.isfinite(f["L_hi"]).any() else np.nanmax(f["L"])
    ax.set_ylim(0, min(top * 1.1, 3000))
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def fig_maps(pairs, study, path):
    p = pairs[(pairs["sample"] == f"{SAMPLE[0]}-{SAMPLE[1]}") & (pairs.regime == "ncei")]
    fig, axes = plt.subplots(2, 4, figsize=(11, 5.8))
    vmin, vmax = 0.2, 1.0
    cmap = plt.get_cmap("Blues")
    im = None
    for ax, site in zip(axes.ravel(), SITE_ORDER):
        s = p[p.site == site]
        row, col = np.divmod(s["grid_id"].to_numpy() - 1, 300)
        r0, c0 = row.min(), col.min()
        arr = np.full((row.max() - r0 + 1, col.max() - c0 + 1), np.nan)
        arr[row - r0, col - c0] = s["r_index"].to_numpy()
        lons = -130.0 + (np.arange(c0, col.max() + 2)) * 0.25
        lats = 20.0 + (np.arange(r0, row.max() + 2)) * 0.25
        im = ax.pcolormesh(lons, lats, np.ma.masked_invalid(arr), cmap=cmap, vmin=vmin, vmax=vmax,
                           shading="flat")
        st = ALL_SITES[site]
        ax.plot(st["station_lon"], st["station_lat"], "*", color=ORANGE, ms=11, mec=INK, mew=0.7)
        ax.plot(st["farm_lon"], st["farm_lat"], "^", color="white", ms=7, mec=INK, mew=0.9)
        th = np.linspace(0, 2 * np.pi, 200)
        for rad in (50, 100):
            ax.plot(st["station_lon"] + rad / (69.0 * np.cos(np.radians(st["station_lat"]))) * np.cos(th),
                    st["station_lat"] + rad / 69.0 * np.sin(th), color=MUTED, lw=0.7, ls=":")
        ax.set_aspect(1 / np.cos(np.radians(st["station_lat"])))
        ax.set_title(site, fontsize=9)
        ax.grid(False)
        ax.tick_params(labelsize=7)
    fig.subplots_adjust(left=0.05, right=0.9, bottom=0.07, top=0.88, wspace=0.25, hspace=0.3)
    cax = fig.add_axes([0.92, 0.15, 0.015, 0.65])
    cb = fig.colorbar(im, cax=cax)
    cb.set_label("Corr(station index, grid index)")
    fig.suptitle("Correlation of each 0.25-degree PRF grid's index with the Kalshi station index "
                 f"(NCEI, {SAMPLE[0]}-{SAMPLE[1]}).\nStar = settlement station, triangle = farm point, "
                 "dotted rings = 50 and 100 mi. Axes: longitude / latitude (degrees).", fontsize=9)
    fig.savefig(path)
    plt.close(fig)


def fig_zero(st_iv, grids_ncei, study, path):
    icols = full_columns(["year", "interval_name"], SAMPLE)
    fig, axes = plt.subplots(2, 4, figsize=(11, 5.6), sharex=True, sharey=True)
    lim = 350
    for ax, site in zip(axes.ravel(), SITE_ORDER):
        gid = int(study[(study.site == site) & (study.role == "station")]["grid_id"].item())
        gx = grids_ncei["idx"].loc[gid].reindex(icols).to_numpy()
        sx = (st_iv[st_iv.station_key == site].set_index(["year", "interval_name"])["index_ncei"]
              .reindex(icols).to_numpy())
        ok = np.isfinite(gx) & np.isfinite(sx)
        ax.scatter(np.clip(gx[ok], 0, lim), np.clip(sx[ok], 0, lim), s=6, color=BLUE, alpha=0.5,
                   linewidths=0)
        ax.plot([0, lim], [0, lim], color=INK, lw=0.8)
        ax.axvline(90, color=MUTED, ls=":", lw=0.9)
        ax.axhline(90, color=MUTED, ls=":", lw=0.9)
        n_clip = int(((gx[ok] > lim) | (sx[ok] > lim)).sum())
        r = pearson(gx, sx)
        e = float(np.sqrt(np.nanmean((sx - gx) ** 2)))
        ax.text(0.03, 0.97, f"r = {r:.2f}\nRMSE = {e:.0f} pts" + (f"\n{n_clip} pts clipped" if n_clip else ""),
                transform=ax.transAxes, va="top", fontsize=7.5, color=INK)
        ax.set_title(f"{site} (grid {gid})", fontsize=9)
        ax.set_xlim(0, lim)
        ax.set_ylim(0, lim)
    for ax in axes[1]:
        ax.set_xlabel("Grid index, station's own grid (NCEI)")
    for ax in axes[:, 0]:
        ax.set_ylabel("Station index")
    fig.suptitle("Zero-distance mismatch: airport gauge vs the 0.25-degree grid that contains it "
                 f"(two-month intervals, {SAMPLE[0]}-{SAMPLE[1]}; dotted = 90% trigger)", fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(path)
    plt.close(fig)


def fig_best(best, path):
    b = best[(best.regime == "ncei")]
    fig, axes = plt.subplots(2, 4, figsize=(11, 5.4), sharex=True)
    for ax, site in zip(axes.ravel(), SITE_ORDER):
        s = b[(b.farm_site == site) & (b.kind == "single")].sort_values("r_index")
        pr = b[(b.farm_site == site) & (b.kind == "avg_index")].sort_values("r_index").tail(1)
        labels = [f"{c} ({d:.0f} mi)" + ("" if ok else " *") for c, d, ok in
                  zip(s["candidate"], s["distance_mi"], s["settles_kalshi_now"])]
        colors = [BLUE if p else LIGHT for p in s["is_paired_station"]]
        y = np.arange(len(s))
        ax.barh(y, s["r_index"], color=colors, edgecolor="white", height=0.7)
        if len(pr):
            ax.barh(len(s), pr["r_index"].item(), color=AQUA, hatch="///", edgecolor="white", height=0.7)
            labels.append(f"avg {pr['candidate'].item()}")
        else:
            ax.text(0.5, 3.0, "only Kalshi station\nwithin 250 mi", ha="center", va="center",
                    fontsize=8, color=MUTED)
        ax.set_yticks(range(len(labels)), labels, fontsize=7.5)
        ax.set_ylim(-0.6, 5.6)
        ax.set_xlim(0, 1)
        ax.set_title(f"{site} farm grid", fontsize=9)
        ax.grid(axis="y", visible=False)
    for ax in axes[1]:
        ax.set_xlabel("Index correlation with farm grid")
    fig.suptitle("Which Kalshi station tracks each farm grid best? (NCEI, "
                 f"{SAMPLE[0]}-{SAMPLE[1]}; dark = paired station, hatched = best two-station "
                 "average, * = no longer settles)", fontsize=9.5)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(path)
    plt.close(fig)


# =================================================================================================
# Main
# =================================================================================================
def main() -> int:
    t0 = time.time()
    study = pd.read_csv(PROCESSED / "study_grids.csv")
    prf_ring = pd.read_csv(PROCESSED / "prf_ring100_grids.csv")
    station_map = pd.read_csv(PROCESSED / "station_map.csv")
    st_month, st_iv = load_stations()
    print(f"stations loaded ({time.time() - t0:.1f} s)", file=sys.stderr)

    all_rows, arrays, grid_long, grids_primary = [], {}, {}, {}
    for regime in ("ncei", "cpc"):
        mo, iv = load_grids(regime)
        grid_long[regime] = iv.set_index(["grid_id", "year", "interval_name"])["index_value"]
        samples = [SAMPLE] + ([LONG_SAMPLE] if regime == "ncei" else [])
        for years in samples:
            grids = grid_tables(mo, iv, years)
            if years == SAMPLE:
                grids_primary[regime] = grids
            for site in SITE_ORDER:
                rows, arr = site_rows(site, regime, years, st_month, st_iv, grids, study, prf_ring)
                all_rows.extend(rows)
                arrays[(f"{years[0]}-{years[1]}", regime, site)] = arr
        print(f"{regime} pairs done ({time.time() - t0:.1f} s)", file=sys.stderr)
    pairs = pd.DataFrame(all_rows)

    # DST check: our NCEI rebuild vs the DST values on the 956 ring grids, sample years
    dst = pd.read_parquet(PROCESSED / "prf_official_index_ring100.parquet",
                          columns=["grid_id", "year", "interval_name", "index_value"])
    dst["interval_name"] = dst["interval_name"].astype(str)
    dst = dst[(dst.year >= SAMPLE[0]) & (dst.year <= SAMPLE[1])]
    ours = grid_long["ncei"].reindex(pd.MultiIndex.from_frame(dst[["grid_id", "year", "interval_name"]]))
    dst_mae = float(np.nanmean(np.abs(ours.to_numpy() - dst["index_value"].to_numpy())))

    fits = decay_fits(pairs[pairs["sample"] == f"{SAMPLE[0]}-{SAMPLE[1]}"],
                      {k: v for k, v in arrays.items() if k[1] == "ncei"}, boot=True)
    fits_long = decay_fits(pairs[pairs["sample"] == f"{LONG_SAMPLE[0]}-{LONG_SAMPLE[1]}"], {}, boot=False)
    fits = pd.concat([fits, fits_long], ignore_index=True)
    print(f"decay fits done ({time.time() - t0:.1f} s)", file=sys.stderr)

    best = []
    for regime in ("ncei", "cpc"):
        gl = grid_long[regime].reset_index()
        gl = gl[(gl.year >= SAMPLE[0]) & (gl.year <= SAMPLE[1])]
        farm_ids = study[study.role == "farm"]["grid_id"].tolist()
        gl = gl[gl.grid_id.isin(farm_ids)].set_index(["grid_id", "year", "interval_name"])["index_value"]
        best.append(best_station(st_iv, station_map, study, gl, regime, SAMPLE))
    best = pd.concat(best, ignore_index=True)

    # ---- write data
    float_cols = pairs.select_dtypes("float").columns
    pairs[float_cols] = pairs[float_cols].round(4)
    pairs.to_csv(PROCESSED / "basis_risk_pairs.csv", index=False)
    fcols = best.select_dtypes("float").columns
    best[fcols] = best[fcols].round(4)
    best.to_csv(PROCESSED / "basis_risk_best_station.csv", index=False)

    # ---- figures
    fig_decay(pairs, fits, FIGURES / "a1_distance_decay_index_corr.png")
    fig_miss(pairs, FIGURES / "a1_trigger_miss_rate_vs_distance.png")
    fig_efold(fits, FIGURES / "a1_efolding_distance_by_season.png")
    fig_maps(pairs, study, FIGURES / "a1_correlation_maps.png")
    fig_zero(st_iv, grids_primary["ncei"], study, FIGURES / "a1_zero_distance_scatter.png")
    fig_best(best, FIGURES / "a1_best_station_per_farm.png")
    print(f"figures done ({time.time() - t0:.1f} s)", file=sys.stderr)

    print_tables(pairs, fits, best, dst_mae, st_iv)
    coverage_table(station_map, pairs, fits)
    print(f"total {time.time() - t0:.1f} s", file=sys.stderr)
    return 0


def coverage_table(station_map, pairs, fits):
    """How many PRF grids lie near a Kalshi monthly-rain station, and the pooled decay fit.

    Uses the DST's CONUS grid list cached by scripts/pull_prf_official_index.py
    (data/raw/prf_official/conus_grid_list.json.gz, gitignored); skipped if it is absent.
    """
    import gzip
    import json
    S = f"{SAMPLE[0]}-{SAMPLE[1]}"
    p = pairs[(pairs["sample"] == S) & (pairs.regime == "ncei")]
    f = fit_exp_decay(p["distance_mi"], p["r_index"])
    fw = fit_exp_decay(p.loc[p.distance_mi <= PRF_RING_MI, "distance_mi"],
                       p.loc[p.distance_mi <= PRF_RING_MI, "r_index"])
    print(f"\nPooled NCEI decay fit, all 8 sites, grids <= {RING_MI:.0f} mi: c0 = {f['c0']:.3f}, "
          f"L = {f['L']:.0f} mi, rmse {f['rmse']:.3f}, n = {f['n']}; r = 0.8 at "
          f"{f['L'] * np.log(f['c0'] / 0.8):.0f} mi; grids <= 100 mi: c0 = {fw['c0']:.3f}, L = {fw['L']:.0f} mi")
    path = RAW / "prf_official" / "conus_grid_list.json.gz"
    if not path.exists():
        print(f"(coverage table skipped: {path} not found)")
        return
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        grids = [g["NoaaGridId"] for g in json.load(fh) if g.get("IsContinentalUsFlag")]
    lat, lon = grid_centres(grids)
    st = station_map.drop_duplicates("station_key")
    st = st[~st.station_key.isin(list(NOT_SETTLING_NOW))]
    dmin = np.full(len(grids), np.inf)
    for r in st.itertuples():
        dmin = np.minimum(dmin, haversine_vec(r.lat, r.lon, lat, lon))
    rows = [{"within_mi": d, "n_grids": int((dmin <= d).sum()), "share": float((dmin <= d).mean()),
             "pooled_fit_r_at_d": float(exp_decay(d, f["c0"], f["L"]))} for d in (25, 50, 100, 150, 250)]
    print(f"\n### PRF CONUS grids near a current Kalshi monthly-rain station ({len(st)} stations, "
          f"{len(grids):,} grids)\n")
    print(md_table(pd.DataFrame(rows), 3))
    print(f"\nMedian distance from a PRF grid centre to the nearest Kalshi station: {np.median(dmin):.0f} mi")


def print_tables(pairs, fits, best, dst_mae, st_iv):
    S = f"{SAMPLE[0]}-{SAMPLE[1]}"
    L = f"{LONG_SAMPLE[0]}-{LONG_SAMPLE[1]}"
    print(f"## Checks\n\nNCEI rebuild vs DST, 956 ring grids, {S}: MAE {dst_mae:.4f} index points")
    p = pairs[pairs["sample"] == S]
    n_grids = p.groupby(["regime", "site"]).agg(n=("grid_id", "size"),
                                                 n100=("distance_mi", lambda d: int((d <= 100).sum())),
                                                 n_prf=("prf_flagged", "sum"))
    print("\nGrids per site within 150 / 100 mi, and PRF-flagged within 100 mi\n")
    print(md_table(n_grids.reset_index(), 0))
    thr = st_iv[(st_iv.year >= 1951) & (st_iv.year <= 2025)].groupby("station_key")["threaded"].mean()
    print("\nShare of 1951-2025 station intervals from threaded predecessors: "
          + ", ".join(f"{k} {v:.1%}" for k, v in thr.items() if v > 0))

    for regime in ("ncei", "cpc"):
        t = p[(p.regime == regime) & p.role.isin(["station_grid", "farm_grid"])].copy()
        t["site"] = pd.Categorical(t["site"], SITE_ORDER)
        t = t.sort_values(["site", "distance_mi"])
        cols = ["site", "role", "grid_id", "distance_mi", "n_month", "r_month", "rho_month",
                "r_month_anom", "rho_month_anom", "n_interval", "r_interval", "r_interval_anom",
                "rho_interval_anom"]
        print(f"\n### Totals correlations, {REGIME_LABEL[regime]}, {S}\n")
        print(md_table(t[cols].assign(site=t.site.astype(str)), 2))
        cols = ["site", "role", "distance_mi", "n_index", "r_index", "rho_index", "rmse_index",
                "bias_index", "sd_ratio_index", "r_payout90", "hit_rate90", "miss_rate90",
                "false_alarm90", "phi90", "hit_rate70", "miss_rate70", "false_alarm70"]
        print(f"\n### Index agreement, {REGIME_LABEL[regime]}, {S}\n")
        print(md_table(t[cols].assign(site=t.site.astype(str)), 2))
        cols = ["site", "role", "both90", "grid_only90", "station_only90", "neither90",
                "both70", "grid_only70", "station_only70", "neither70"]
        print(f"\n### Confusion matrices, {REGIME_LABEL[regime]}, {S}\n")
        print(md_table(t[cols].assign(site=t.site.astype(str)), 0))
        cols = ["site", "role", "rmse_index", "rmse_index_mb", "bias_index", "bias_index_mb",
                "miss_rate90", "miss_rate90_mb", "agreement90", "agreement90_mb", "miss_rate70",
                "miss_rate70_mb"]
        print(f"\n### Official base vs matched base, {REGIME_LABEL[regime]}, {S}\n")
        print(md_table(t[cols].assign(site=t.site.astype(str)), 2))

    # station grid vs best grid nearby
    print("\n### Own grid vs best-correlated grid within 25 mi (NCEI)\n")
    rows = []
    for site in SITE_ORDER:
        s = p[(p.regime == "ncei") & (p.site == site)]
        own = s[s.role == "station_grid"].iloc[0]
        near = s[s.distance_mi <= 25].sort_values("r_index", ascending=False).iloc[0]
        rows.append({"site": site, "own_grid": int(own.grid_id), "own_dist": own.distance_mi,
                     "own_r": own.r_index, "best_grid": int(near.grid_id), "best_dist": near.distance_mi,
                     "best_r": near.r_index,
                     "n_within_25": int((s.distance_mi <= 25).sum())})
    print(md_table(pd.DataFrame(rows), 2))

    # NCEI vs CPC summary
    print("\n### NCEI vs CPC, mean over all grids within 100 mi and at station / farm grid\n")
    rows = []
    for regime in ("ncei", "cpc"):
        s = p[p.regime == regime]
        for lab, sel in (("station grid", s.role == "station_grid"), ("farm grid", s.role == "farm_grid"),
                         ("all grids <= 100 mi", s.distance_mi <= 100), ("50-100 mi", (s.distance_mi > 50) & (s.distance_mi <= 100))):
            q = s[sel]
            rows.append({"regime": regime, "set": lab, "n_grids": len(q), "r_index": q.r_index.mean(),
                         "rmse_index": q.rmse_index.mean(), "miss_rate90": q.miss_rate90.mean(),
                         "miss_rate70": q.miss_rate70.mean(), "phi90": q.phi90.mean()})
    print(md_table(pd.DataFrame(rows), 3))

    # residual basis risk 1 - r^2 (share of variance an optimal linear hedge cannot remove)
    rows = []
    for regime in ("ncei", "cpc"):
        for role in ("station_grid", "farm_grid"):
            q = p[(p.regime == regime) & (p.role == role)].set_index("site").reindex(SITE_ORDER)
            row = {"regime": regime, "role": role}
            for site in SITE_ORDER:
                row[site] = 1 - q.loc[site, "r_payout90"] ** 2
            row["mean"] = float(np.mean([row[k] for k in SITE_ORDER]))
            row["mean_index"] = float(np.mean(1 - q["r_index"] ** 2))
            rows.append(row)
    print("\n### Residual basis risk 1 - r^2 of PRF payout (90%) on station payout; "
          "mean_index uses the index r\n")
    print(md_table(pd.DataFrame(rows), 3))
    q = p.copy()
    q["bin"] = pd.cut(q["distance_mi"], DISTANCE_BINS)
    q["resid_payout"] = 1 - q["r_payout90"] ** 2
    b = q.pivot_table(index="regime", columns="bin", values="resid_payout", aggfunc="mean", observed=True)
    b.columns = [str(c) for c in b.columns]
    print("\nMean residual 1 - r_payout90^2 by distance bin, all 8 sites\n")
    print(md_table(b.reset_index(), 3))

    # seasonal agreement at the farm and station grids
    t = p[p.role.isin(["station_grid", "farm_grid"])].copy()
    t["site"] = pd.Categorical(t["site"], SITE_ORDER)
    t = t.sort_values(["regime", "site", "role"], ascending=[False, True, False])
    print("\n### Seasonal agreement, station and farm grids\n")
    print(md_table(t[["regime", "site", "role", "r_index_warm", "r_index_cool", "miss_rate90_warm",
                      "miss_rate90_cool"]].assign(site=t.site.astype(str)), 2))

    # long sample
    pl = pairs[(pairs["sample"] == L) & pairs.role.isin(["station_grid", "farm_grid"])].copy()
    ps = p[(p.regime == "ncei") & p.role.isin(["station_grid", "farm_grid"])]
    m = pl.merge(ps, on=["site", "role"], suffixes=("_long", "_short"))
    m["site"] = pd.Categorical(m["site"], SITE_ORDER)
    m = m.sort_values(["site", "role"])
    print(f"\n### Long sample {L} vs {S} (NCEI)\n")
    print(md_table(m[["site", "role", "n_index_long", "share_threaded_intervals_long", "r_index_long",
                      "r_index_short", "rmse_index_long", "rmse_index_short", "miss_rate90_long",
                      "miss_rate90_short"]].assign(site=m.site.astype(str)), 2))

    # decay fits
    for sample in (S, L):
        for regime in ("ncei", "cpc"):
            f = fits[(fits["sample"] == sample) & (fits.regime == regime)]
            if f.empty:
                continue
            f = f.copy()
            f["site"] = pd.Categorical(f["site"], SITE_ORDER)
            f = f.sort_values(["site", "max_distance_mi", "season"])
            w = f[f.max_distance_mi == RING_MI].pivot(index="site", columns="season",
                                                     values=["c0", "L", "L_lo", "L_hi", "r_at_50mi_fit", "d_r080_mi", "rmse"])
            w.columns = [f"{a}_{b}" for a, b in w.columns]
            cols = [c for c in ["c0_all", "L_all", "L_lo_all", "L_hi_all", "r_at_50mi_fit_all", "d_r080_mi_all",
                                "rmse_all", "d_r080_mi_warm", "d_r080_mi_cool",
                                "c0_warm", "L_warm", "L_lo_warm", "L_hi_warm", "c0_cool", "L_cool",
                                "L_lo_cool", "L_hi_cool"] if c in w.columns and w[c].notna().any()]
            print(f"\n### Distance-decay fits, {REGIME_LABEL[regime]}, {sample}, grids <= {RING_MI:.0f} mi\n")
            print(md_table(w[cols].reset_index().assign(site=lambda d: d.site.astype(str)), 2))
            w100 = f[f.max_distance_mi == PRF_RING_MI].pivot(index="site", columns="season", values=["c0", "L"])
            w100.columns = [f"{a}_{b}" for a, b in w100.columns]
            print(f"\nSame, grids <= {PRF_RING_MI:.0f} mi\n")
            print(md_table(w100.reset_index().assign(site=lambda d: d.site.astype(str)), 2))

    f = fits[(fits["sample"] == S) & (fits.regime == "ncei") & (fits.max_distance_mi == RING_MI)]
    for season in ("all", "warm", "cool"):
        q = f[f.season == season].set_index("site")
        print(f"\nArid (ABQ, DEN) mean L {season}: {q.loc[list(ARID), 'L'].mean():.0f} mi; "
              f"humid (SGF, TPA) mean L: {q.loc[list(HUMID), 'L'].mean():.0f} mi")

    # binned miss rates
    for regime in ("ncei", "cpc"):
        q = p[p.regime == regime].copy()
        q["bin"] = pd.cut(q["distance_mi"], DISTANCE_BINS)
        b = q.pivot_table(index="site", columns="bin", values="miss_rate90", aggfunc="mean", observed=True)
        b = b.reindex(SITE_ORDER)
        b.columns = [str(c) for c in b.columns]
        b["unrelated"] = q.groupby("site")["miss_if_independent90"].mean().reindex(SITE_ORDER)
        print(f"\n### Mean miss rate at 90% by distance bin (mi), {REGIME_LABEL[regime]}, {S}\n")
        print(md_table(b.reset_index(), 2))
        b = q.pivot_table(index="site", columns="bin", values="r_index", aggfunc="mean", observed=True)
        b = b.reindex(SITE_ORDER)
        b.columns = [str(c) for c in b.columns]
        print(f"\n### Mean index correlation by distance bin (mi), {REGIME_LABEL[regime]}, {S}\n")
        print(md_table(b.reset_index(), 2))
        b = q.pivot_table(index="site", columns="bin", values="miss_rate70", aggfunc="mean", observed=True)
        b.columns = [str(c) for c in b.columns]
        print(f"\n### Mean miss rate at 70% by distance bin (mi), {REGIME_LABEL[regime]}, {S}\n")
        print(md_table(b.reindex(SITE_ORDER).reset_index(), 2))

    # best station
    for regime in ("ncei", "cpc"):
        b = best[(best.regime == regime) & (best.kind == "single")].copy()
        b["farm_site"] = pd.Categorical(b["farm_site"], SITE_ORDER)
        b = b.sort_values(["farm_site", "rank_r_index"])
        cols = ["farm_site", "candidate", "distance_mi", "rank_r_index", "is_paired_station",
                "settles_kalshi_now", "n_index", "r_index", "rho_index", "rmse_index", "r_payout90",
                "hit_rate90", "miss_rate90", "phi90", "miss_rate70"]
        print(f"\n### Candidate stations per farm grid, {REGIME_LABEL[regime]}, {S}\n")
        print(md_table(b[cols].assign(farm_site=b.farm_site.astype(str),
                                      is_paired_station=b.is_paired_station.map({True: "yes", False: ""}),
                                      settles_kalshi_now=b.settles_kalshi_now.map({True: "yes", False: "no"})), 2))
        a = best[(best.regime == regime) & (best.kind == "avg_index")].copy()
        if len(a):
            a = a.sort_values("r_index", ascending=False).groupby("farm_site").head(2)
            a["farm_site"] = pd.Categorical(a["farm_site"], SITE_ORDER)
            a = a.sort_values(["farm_site", "r_index"], ascending=[True, False])
            print(f"\n### Best two-station average index, {REGIME_LABEL[regime]}\n")
            print(md_table(a[["farm_site", "candidate", "n_index", "r_index", "rmse_index", "r_payout90",
                              "hit_rate90", "miss_rate90", "phi90"]].assign(farm_site=a.farm_site.astype(str)), 2))
        pp = best[(best.regime == regime) & (best.kind == "payout_portfolio")].copy()
        if len(pp):
            pp = pp.sort_values("r_payout90", ascending=False).groupby("farm_site").head(1)
            print(f"\n### Best in-sample payout portfolio (90%), {REGIME_LABEL[regime]}\n")
            print(md_table(pp[["farm_site", "candidate", "weight_a", "n_index", "r_payout90"]], 2))
        cv = best[(best.regime == regime) & (best.kind == "loyo_cv")].copy()
        cv["farm_site"] = pd.Categorical(cv["farm_site"], SITE_ORDER)
        cv = cv.sort_values("farm_site")
        print(f"\n### Leave-one-year-out payout correlation (90%), {REGIME_LABEL[regime]}\n")
        print(md_table(cv[["farm_site", "candidate", "n_index", "oos_r_paired", "oos_r_best_single",
                           "chosen_single_mode", "chosen_single_share", "oos_r_best_pair",
                           "chosen_pair_mode", "chosen_pair_share"]].assign(farm_site=cv.farm_site.astype(str)), 3))


if __name__ == "__main__":
    sys.exit(main())
