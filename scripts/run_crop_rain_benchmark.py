"""Kalshi rain contracts against private parametric rain cover for commercial crops (doc 29).

Run from the repo root (no network; run scripts/pull_crop_county_data.py once first):

    python scripts/run_crop_rain_benchmark.py            # full study (about 5 minutes)
    python scripts/run_crop_rain_benchmark.py --quick    # counties within 30 miles, no per-county check

Question. PRF insures forage, not commercial crops. For corn, soybeans, winter wheat, grain
sorghum and upland cotton, how much of a county's real yield loss does a Kalshi rain hedge
remove, at whole-inch strikes (listed today) and at third-inch strikes, and how does that
compare with a private parametric policy that settles on the county's own rain but costs more?

Target. Yield shortfall below the county's own quadratic trend, max(0, 1 - yield / trend), USDA
NASS county yields 1960-2025. This is a real loss, not a rain formula, so heat, pests and
everything else rain cannot see count against every rain contract alike.

Method. Rain explains a modest share of yield loss, so fitting a ladder county by county
overfits (Table I). Instead each crop x state gets one "template": a non-negative mix of puts
and calls on each season month's rain as a share of normal, fitted on the whole state's county
panel with each county's own rain, leaving the evaluated year out. The template is then paid on
    P_month      the county's own rain (NOAA nClimDiv county average): the private parametric benchmark
    P_season     the county's own season total (a put/call spread on one total, the usual private form)
    K_ideal      the nearest Kalshi station's rain, exact payoff (the limit of 0.01-inch strikes)
    K_third      the station's rain through third-inch monthly binaries
    K_today      the station's rain through today's whole-inch monthly binaries
    K_today_dry  the same, drought side (NO contracts) only
Each family gets one pooled minimum-variance hedge ratio per crop x distance band, also
estimated with the evaluated year left out.

Outputs
    data/processed/crop_benchmark_cases.parquet  one row per county x crop x family x eval set
    data/processed/crop_benchmark_summary.csv    pooled by crop, distance band and family
    data/processed/crop_benchmark_coverage.csv   share of crop acres near a Kalshi rain station
    data/processed/crop_benchmark_cost.csv       cost per unit of risk removed and break-even loads
    data/processed/crop_benchmark_templates.csv  fitted template coefficients by crop x state
    data/processed/crop_benchmark_percounty_check.csv
    docs/figures/x3_*.png
    tables between the AUTO markers of docs/analysis/29_row_crop_rain_benchmark.md
"""
from __future__ import annotations

import argparse
import re
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from agri_hedge import cropbench as cb  # noqa: E402
from agri_hedge import exotics as ex  # noqa: E402
from agri_hedge.config import DOCS, FIGURES, PROCESSED  # noqa: E402
from agri_hedge.replicate import fit_ladder, loyo_predictions, pooled_he  # noqa: E402

DOC = DOCS / "analysis" / "29_row_crop_rain_benchmark.md"
FIRST_YEAR, LAST_YEAR = 1960, 2025
YEARS = np.arange(FIRST_YEAR, LAST_YEAR + 1)
NY = len(YEARS)
MIN_YEARS = 45
MAX_DIST_MI = 100.0
MIN_ACRES = 5000.0
MIN_GROUP_COUNTIES = 8
MIN_CELL_CASES = 5
RIDGE_FINE, RIDGE_COARSE = 0.1, 0.03
HALF_SPREAD = 0.0225
TAIL_LOSS, CALM_LOSS = 0.20, 0.02      # "bad year" and "no-loss year" thresholds (share of expected revenue)
PRIVATE_LOADS = (1.5, 2.0, 2.5)
BANDS = [(0, 25, "0-25 mi"), (25, 50, "25-50 mi"), (50, 100, "50-100 mi")]
CROPS = ["corn", "soybeans", "winter_wheat", "sorghum", "cotton"]
FAMILIES = [
    ("K_today_dry", "Kalshi today: whole-inch monthly, drought side only", "station"),
    ("K_today", "Kalshi today: whole-inch monthly, both sides", "station"),
    ("K_third", "Kalshi third-inch monthly, both sides", "station"),
    ("K_ideal", "Station rain, exact payoff (0.01-inch strikes)", "station"),
    ("P_month", "Private benchmark: county's own rain, monthly", "county"),
    ("P_season", "Private benchmark: county's own rain, season total", "county"),
    ("K_today_lean", "Kalshi today, deep strikes only", "station"),
    ("K_third_lean", "Kalshi third-inch, deep strikes only", "station"),
    ("P_month_lean", "Private: county's own rain, monthly, deep strikes only", "county"),
    ("P_season_lean", "Private: county's own rain, season total, deep strikes only", "county"),
    ("K_season", "Station season total, whole-inch strikes (new contract)", "station"),
    ("K_season_lean", "Station season total, deep strikes only (new contract)", "station"),
]
ALL_FAMS = [k for k, _, _ in FAMILIES]
ORDER = ALL_FAMS[:6]                    # the main six, used in the by-crop and by-distance tables
FAM_LABEL = {k: lab for k, lab, _ in FAMILIES}
FAM_SHORT = {"K_today_dry": "Today, drought only", "K_today": "Today, both sides", "K_third": "Third-inch",
             "K_ideal": "Station, exact", "P_month": "Local rain, monthly", "P_season": "Local rain, season"}
FAM_SHORT.update({"K_today_lean": "Today, deep", "K_third_lean": "Third-inch, deep", "P_month_lean": "Local monthly, deep",
                  "P_season_lean": "Local season, deep", "K_season": "Station season total",
                  "K_season_lean": "Station season, deep"})
KALSHI_PRICED = ("K_today_dry", "K_today", "K_third", "K_today_lean", "K_third_lean", "K_season", "K_season_lean")
PRIVATE = ("P_month", "P_season", "P_month_lean", "P_season_lean")
#: like-for-like pairs for the break-even load: same template, station rain against the county's own rain
PAIRS = {"K_today": "P_month", "K_third": "P_month", "K_today_lean": "P_month_lean", "K_third_lean": "P_month_lean",
         "K_season": "P_season", "K_season_lean": "P_season_lean"}
C_BLUE, C_ORANGE, C_AQUA = "#2a78d6", "#eb6834", "#1baf7a"
C_TEXT, C_TEXT2, C_GRID = "#0b0b0b", "#52514e", "#e6e5e2"
IS_CALL_MONTH = np.array([False] * len(cb.MONTH_PUT_K) + [True] * len(cb.MONTH_CALL_K))
#: "deep strikes only" templates keep puts at or below 70% of normal and calls at or above 160% (monthly) / 150% (season),
#: so they pay in bad rain years only, like a policy with a deductible
LEAN_MONTH = np.array([k <= 0.7 for k in cb.MONTH_PUT_K] + [k >= 1.6 for k in cb.MONTH_CALL_K])
LEAN_SEASON = np.array([k <= 0.7 for k in cb.SEASON_PUT_K] + [k >= 1.5 for k in cb.SEASON_CALL_K])


def log(*a):
    print(*a, flush=True)


# ---------------------------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------------------------

def load_stations() -> tuple[pd.DataFrame, dict[str, pd.DataFrame], dict[str, tuple[float, ...]]]:
    """Stations with a long complete monthly record, their year x month rain, listed whole-inch strikes."""
    sm = pd.read_csv(PROCESSED / "station_map.csv")
    sm = sm[sm["series_ticker"].str.startswith("KXRAIN")].drop_duplicates("station_key")
    st = pd.read_csv(PROCESSED / "station_monthly_precip.csv")
    st.loc[st["n_missing"].fillna(1) != 0, "precip_in"] = np.nan
    markets = pd.read_parquet(PROCESSED / "kalshi_rain_markets.parquet",
                              columns=["series_ticker", "floor_strike", "is_single_month", "strike_type"])
    markets = markets[markets["is_single_month"].astype(bool) & (markets["strike_type"] == "greater")]
    monthly, listed, keep = {}, {}, []
    for _, r in sm.iterrows():
        g = st[st["station_key"] == r["station_key"]]
        w = g.pivot_table(index="year", columns="month", values="precip_in", aggfunc="first")
        w = w.reindex(index=np.arange(FIRST_YEAR - 1, LAST_YEAR + 1), columns=range(1, 13))
        # Napa, St Petersburg and Trenton start in 1998; Chicago is represented by O'Hare, not Midway
        if w.loc[FIRST_YEAR:].notna().all(axis=1).sum() < 60 or r["station_key"] == "MDW":
            continue
        monthly[r["station_key"]] = w
        m = markets[markets["series_ticker"] == r["series_ticker"]]
        ks = sorted({float(k) for k in m["floor_strike"].dropna() if float(k) == int(float(k)) and float(k) <= 7.0})
        listed[r["station_key"]] = tuple(ks) or tuple(float(k) for k in range(1, 8))
        keep.append(r["station_key"])
    sm = sm[sm["station_key"].isin(keep)][["station_key", "series_ticker", "name", "state", "lat", "lon"]]
    return sm.reset_index(drop=True), monthly, listed


def load_counties(stations: pd.DataFrame) -> pd.DataFrame:
    """County centroids with the nearest usable Kalshi rain station and its distance."""
    c = pd.read_csv(PROCESSED / "county_centroids.csv")
    d = cb.haversine_mi(c["lat"].to_numpy()[:, None], c["lon"].to_numpy()[:, None],
                        stations["lat"].to_numpy()[None, :], stations["lon"].to_numpy()[None, :])
    j = d.argmin(axis=1)
    c["station_key"] = stations["station_key"].to_numpy()[j]
    c["distance_mi"] = d.min(axis=1)
    return c


def choose_series(y: pd.DataFrame) -> pd.DataFrame:
    """One yield series per crop x county: non-irrigated if it has MIN_YEARS years, else all practices."""
    n = y.groupby(["crop", "fips", "practice"])["year"].nunique().unstack("practice").fillna(0)
    for col in ("all", "non_irrigated"):
        if col not in n.columns:
            n[col] = 0
    pick = np.where(n["non_irrigated"] >= MIN_YEARS, "non_irrigated", np.where(n["all"] >= MIN_YEARS, "all", ""))
    sel = pd.DataFrame({"practice": pick}, index=n.index).reset_index()
    sel = sel[sel["practice"] != ""]
    return y.merge(sel, on=["crop", "fips", "practice"])


def band_of(d: float) -> str:
    for lo, hi, lab in BANDS:
        if lo <= d < hi or (hi == BANDS[-1][1] and d == hi):
            return lab
    return ""


# ---------------------------------------------------------------------------------------------
# Panel and templates
# ---------------------------------------------------------------------------------------------

def monthly_basis(rain: dict[str, np.ndarray]) -> np.ndarray:
    """Month-by-month relative basis, stacked side by side."""
    return np.column_stack([cb.relative_basis(r, float(np.nanmean(r)))[0] for r in rain.values()])


def season_basis(rain: dict[str, np.ndarray]) -> np.ndarray:
    tot = cb.season_total(rain)
    return cb.relative_basis(tot, float(np.nanmean(tot)), cb.SEASON_PUT_K, cb.SEASON_CALL_K)[0]


def build_panel(counties: pd.DataFrame) -> list[dict]:
    """Every county x crop with a long yield record: loss, local-rain bases, group key."""
    y = choose_series(pd.read_parquet(PROCESSED / "county_crop_yields.parquet"))
    y = y[y["year"].between(FIRST_YEAR, LAST_YEAR)]
    acres = pd.read_csv(PROCESSED / "county_crop_acres.csv").set_index(["crop", "fips"])["acres_harvested_2018_2022"]
    rain = pd.read_parquet(PROCESSED / "county_monthly_precip.parquet")
    wide = rain.set_index(["fips", "year", "month"])["precip_in"].unstack("month").reindex(columns=range(1, 13))
    all_years = np.arange(FIRST_YEAR - 1, LAST_YEAR + 1)
    rain_by = {f: g.droplevel("fips").reindex(all_years) for f, g in wide.groupby(level="fips")}
    cmeta = counties.set_index("fips")
    panel = []
    for (crop, fips), g in y.groupby(["crop", "fips"]):
        if fips not in rain_by or fips not in cmeta.index:
            continue
        ys = g.set_index("year")["yield"].reindex(YEARS).to_numpy(float)
        loss, trend = cb.yield_loss_fraction(YEARS, ys)
        if np.sum(~np.isnan(loss)) < MIN_YEARS or not np.nanvar(loss) > 0:
            continue
        rc = cb.season_rain(rain_by[fips], cb.SEASONS[crop], YEARS)
        c = cmeta.loc[fips]
        panel.append({"crop": crop, "fips": int(fips), "state": c["state"], "county": c["name"], "loss": loss,
                      "rc": rc, "B_month": monthly_basis(rc), "B_season": season_basis(rc), "co_month": rain_by[fips],
                      "station_key": c["station_key"], "distance_mi": float(c["distance_mi"]),
                      "acres": float(acres.get((crop, fips), np.nan)), "practice": g["practice"].iloc[0],
                      "trend_yield_2025": float(trend[-1])})
    n = pd.Series([(p["crop"], p["state"]) for p in panel]).value_counts()
    for p in panel:
        p["group"] = (p["crop"], p["state"] if n[(p["crop"], p["state"])] >= MIN_GROUP_COUNTIES else "other")
    return panel


def fit_templates(panel: list[dict], key: str, keep_legs: np.ndarray | None = None) -> dict[tuple, dict]:
    """Per group: full-sample coefficients and one set per left-out year (NNLS with a free intercept).

    `keep_legs` (one flag per basis leg of one month, or of the season) restricts the template to those legs.
    """
    groups: dict[tuple, list[dict]] = {}
    for p in panel:
        groups.setdefault(p["group"], []).append(p)
    out = {}
    for gkey, members in groups.items():
        B = np.vstack([m[key] for m in members])
        if keep_legs is not None:
            B = B * np.tile(keep_legs, B.shape[1] // len(keep_legs))
        y = np.concatenate([m["loss"] for m in members])
        yr = np.tile(YEARS, len(members))
        full = fit_ladder(B, y, fit_intercept=True)
        loyo = np.zeros((NY, B.shape[1]))
        for i, t in enumerate(YEARS):
            keep = yr != t
            loyo[i] = fit_ladder(B[keep], y[keep], fit_intercept=True).weights
        out[gkey] = {"full": full.weights, "loyo": loyo, "intercept": full.intercept, "n_counties": len(members)}
    return out


def _block_diag(mats: list[np.ndarray]) -> np.ndarray:
    out = np.zeros((sum(m.shape[0] for m in mats), sum(m.shape[1] for m in mats)))
    i = j = 0
    for m in mats:
        out[i:i + m.shape[0], j:j + m.shape[1]] = m
        i += m.shape[0]
        j += m.shape[1]
    return out


def station_design(crop: str, st_month: pd.DataFrame, listed: tuple[float, ...]) -> dict:
    """Exact template basis on station rain and its carry-over onto whole-inch and third-inch binaries.

    Returns B (years x basis) and, for each ladder, the binary payoff matrix X (years x binaries)
    and D (binaries x basis), the long-only binary weights that copy each basis leg.
    """
    rs = cb.season_rain(st_month, cb.SEASONS[crop], YEARS)
    ladders = {"whole": np.asarray(listed, dtype=float), "third": ex.strike_grid(ex.THIRD_IN, max(listed))}
    Bs, Xs, Ds = [], {k: [] for k in ladders}, {k: [] for k in ladders}
    for r in rs.values():
        B, legs = cb.relative_basis(r, float(np.nanmean(r)))
        Bs.append(B)
        for name, ks in ladders.items():
            D = np.zeros((2 * len(ks), B.shape[1]))
            for j, (kind, _) in enumerate(legs):
                w = cb.digital_approximation(r, B[:, j], kind, ks)
                if kind == "put":
                    D[:len(ks), j] = w
                else:
                    D[len(ks):, j] = w
            Xs[name].append(cb.digital_matrix(r, ks))
            Ds[name].append(D)
    X = {k: np.column_stack(v) for k, v in Xs.items()}
    D = {k: _block_diag(v) for k, v in Ds.items()}
    # the season-total template on a whole-inch ladder of the season total (a contract Kalshi does not list)
    tot = cb.season_total(rs)
    Bt, legs = cb.relative_basis(tot, float(np.nanmean(tot)), cb.SEASON_PUT_K, cb.SEASON_CALL_K)
    ks = ex.strike_grid(1.0, float(np.nanmax(tot)))
    Dt = np.zeros((2 * len(ks), Bt.shape[1]))
    for j, (kind, _) in enumerate(legs):
        w = cb.digital_approximation(tot, Bt[:, j], kind, ks)
        if kind == "put":
            Dt[:len(ks), j] = w
        else:
            Dt[len(ks):, j] = w
    X["season"], D["season"] = cb.digital_matrix(tot, ks), Dt
    return {"B": np.column_stack(Bs), "rs": rs, "X": X, "D": D}


def _rowdot(M: np.ndarray, A: np.ndarray) -> np.ndarray:
    """Row-wise sum(M[t] * A[t]); rows of M with a NaN stay NaN."""
    bad = np.isnan(M).any(axis=1)
    out = np.einsum("ij,ij->i", np.where(np.isnan(M), 0.0, M), A)
    out[bad] = np.nan
    return out


def raw_payoffs(p: dict, sd: dict, tm: dict, ts: dict, tm_lean: dict, ts_lean: dict) -> dict[str, dict]:
    """Unscaled template payoffs of every family: per-year LOYO and full-sample, plus binary weights."""
    am, a_full = tm["loyo"], tm["full"]
    al, al_full = tm_lean["loyo"], tm_lean["full"]
    call = np.tile(IS_CALL_MONTH, len(cb.SEASONS[p["crop"]]))
    am_dry, a_dry = am * ~call, a_full * ~call
    out = {
        "P_month": {"loyo": _rowdot(p["B_month"], am), "full": p["B_month"] @ a_full},
        "P_season": {"loyo": _rowdot(p["B_season"], ts["loyo"]), "full": p["B_season"] @ ts["full"]},
        "K_ideal": {"loyo": _rowdot(sd["B"], am), "full": sd["B"] @ a_full},
        "P_month_lean": {"loyo": _rowdot(p["B_month"], al), "full": p["B_month"] @ al_full},
        "P_season_lean": {"loyo": _rowdot(p["B_season"], ts_lean["loyo"]), "full": p["B_season"] @ ts_lean["full"]},
    }
    for fam, lad, A, a in (("K_third", "third", am, a_full), ("K_today", "whole", am, a_full),
                           ("K_today_dry", "whole", am_dry, a_dry), ("K_third_lean", "third", al, al_full),
                           ("K_today_lean", "whole", al, al_full), ("K_season", "season", ts["loyo"], ts["full"]),
                           ("K_season_lean", "season", ts_lean["loyo"], ts_lean["full"])):
        X, D = sd["X"][lad], sd["D"][lad]
        out[fam] = {"loyo": _rowdot(X, A @ D.T), "full": X @ (D @ a), "w": D @ a, "X": X}
    return out


def evaluate(panel: list[dict], monthly, listed, tmpl: dict, max_dist: float) -> pd.DataFrame:
    cases = [p for p in panel if p["distance_mi"] <= max_dist and p["acres"] >= MIN_ACRES]
    log(f"{len(cases)} county-crop cases within {max_dist:.0f} miles with at least {MIN_ACRES:.0f} acres")
    raws, rss = [], []
    for i, p in enumerate(cases):
        sd = station_design(p["crop"], monthly[p["station_key"]], listed[p["station_key"]])
        rss.append(sd["rs"])
        raws.append(raw_payoffs(p, sd, *(tmpl[k][p["group"]] for k in ("month", "season", "month_lean", "season_lean"))))
        if (i + 1) % 250 == 0:
            log(f"  payoffs {i + 1}/{len(cases)}")
    cell: dict[tuple, list[int]] = {}
    by_crop: dict[str, list[int]] = {}
    for i, p in enumerate(cases):
        cell.setdefault((p["crop"], band_of(p["distance_mi"])), []).append(i)
        by_crop.setdefault(p["crop"], []).append(i)
    rows = []
    for (crop, band), idx in cell.items():
        # one pooled hedge ratio per crop x band (crop-wide if the cell is small), evaluated year left out
        src = idx if len(idx) >= MIN_CELL_CASES else by_crop[crop]
        Y = np.vstack([cases[i]["loss"] for i in src])
        for fam in ALL_FAMS:
            Hl = np.vstack([raws[i][fam]["loyo"] for i in src])
            Hf = np.vstack([raws[i][fam]["full"] for i in src])
            b_full = cb.pooled_hedge_ratio(Y, Hf)
            b_loyo = np.array([cb.pooled_hedge_ratio(Y, Hl, leave_out=t) for t in range(NY)])
            for i in idx:
                p, r = cases[i], raws[i][fam]
                y = p["loss"]
                tot_s, tot_c = cb.season_total(rss[i]), cb.season_total(p["rc"])
                okr = ~np.isnan(tot_s) & ~np.isnan(tot_c)
                price = {"fair_cost": np.nan, "load": np.nan, "thin_share": np.nan, "n_legs": np.nan, "contracts": np.nan}
                if fam in KALSHI_PRICED:
                    okx = ~np.isnan(r["X"]).any(axis=1)
                    pr = ex.hedge_pricing(b_full * r["w"], r["X"][okx], half_spread=HALF_SPREAD)
                    price = {k: pr[k] for k in price}
                else:
                    price["fair_cost"] = float(np.nanmean(b_full * r["full"]))
                meta = {"crop": crop, "fips": p["fips"], "county": p["county"], "state": p["state"],
                        "station_key": p["station_key"], "distance_mi": p["distance_mi"], "band": band, "acres": p["acres"],
                        "practice": p["practice"], "group_state": p["group"][1],
                        "revenue_per_acre": p["trend_yield_2025"] * cb.PRICES[crop],
                        "station_month_mean_in": float(np.nanmean(tot_s)) / len(cb.SEASONS[crop]),
                        "station_county_rain_corr": float(np.corrcoef(tot_s[okr], tot_c[okr])[0, 1])}
                for ev, pred, b in (("loyo", b_loyo * r["loyo"], float(np.mean(b_loyo))),
                                    ("in_sample", b_full * r["full"], b_full)):
                    ok = ~np.isnan(y) & ~np.isnan(pred)
                    yy, pp = y[ok], pred[ok]
                    e = yy - pp
                    vy = float(np.var(yy))
                    tail, calm = yy > TAIL_LOSS, yy < CALM_LOSS
                    rows.append({**meta, "family": fam, "eval_set": ev, "n_years": int(ok.sum()), "hedge_ratio": b,
                                 "n_tail": int(tail.sum()), "tail_loss_sum": float(yy[tail].sum()),
                                 "tail_hedge_sum": float(pp[tail].sum()), "n_calm": int(calm.sum()),
                                 "calm_hedge_sum": float(pp[calm].sum()),
                                 "var_prf": vy, "var_resid": float(np.var(e)), "he": float(1 - np.var(e) / vy),
                                 "corr": float(np.corrcoef(yy, pp)[0, 1]) if np.std(pp) > 0 else np.nan,
                                 "sd_loss": float(np.sqrt(vy)), "sd_resid": float(np.std(e)),
                                 "mean_loss": float(np.mean(yy)), "mean_hedge": float(np.mean(pp)),
                                 "p_loss_gt10": float(np.mean(yy > 0.10)), **price})
    return pd.DataFrame(rows)


def template_table(tmpl_m: dict) -> pd.DataFrame:
    rows = []
    for (crop, state), t in tmpl_m.items():
        j = 0
        for off, mon in cb.SEASONS[crop]:
            for kind, ks in (("put", cb.MONTH_PUT_K), ("call", cb.MONTH_CALL_K)):
                for k in ks:
                    rows.append({"crop": crop, "state": state, "n_counties": t["n_counties"], "year_offset": off,
                                 "month": mon, "kind": kind, "strike_share_of_normal": k, "coef": float(t["full"][j]),
                                 "intercept": t["intercept"]})
                    j += 1
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------------------------
# Per-county fitting check (why the template approach is used)
# ---------------------------------------------------------------------------------------------

def percounty_case(task: dict) -> list[dict]:
    y = task["loss"]
    rs = cb.season_rain(task["st_month"], cb.SEASONS[task["crop"]], YEARS)
    rc = cb.season_rain(task["co_month"], cb.SEASONS[task["crop"]], YEARS)
    top = max(task["listed"])
    fams = {"Station rain, whole-inch": (cb.collar_columns(rs, 1.0, strikes=task["listed"]), RIDGE_COARSE),
            "Station rain, third-inch": (cb.collar_columns(rs, ex.THIRD_IN, max_strike=top), RIDGE_FINE),
            "County rain, third-inch": (cb.collar_columns(rc, ex.THIRD_IN, max_strike=top), RIDGE_FINE)}
    rows = []
    for fam, (cols, ridge) in fams.items():
        X, _ = ex.design_from_columns(cols)
        ok = ~np.isnan(y) & ~np.isnan(X).any(axis=1)
        f = fit_ladder(X[ok], y[ok], ridge=ridge, fit_intercept=True)
        for ev, pred in (("in_sample", f.predict(X[ok])),
                         ("loyo", loyo_predictions(X, y, ridge=ridge, fit_intercept=True)[ok])):
            e = y[ok] - pred
            rows.append({"crop": task["crop"], "fips": task["fips"], "family": fam, "eval_set": ev, "n_years": int(ok.sum()),
                         "var_prf": float(np.var(y[ok])), "var_resid": float(np.var(e)),
                         "he": float(1 - np.var(e) / np.var(y[ok])), "n_legs": int(np.sum(f.weights > 1e-10))})
    return rows


def percounty_check(panel, monthly, listed, workers: int, n_sample: int = 120) -> pd.DataFrame:
    cases = [p for p in panel if p["distance_mi"] <= MAX_DIST_MI and p["acres"] >= MIN_ACRES]
    pick = np.random.default_rng(473).choice(len(cases), size=min(n_sample, len(cases)), replace=False)
    tasks = [{"crop": cases[i]["crop"], "fips": cases[i]["fips"], "loss": cases[i]["loss"],
              "st_month": monthly[cases[i]["station_key"]], "co_month": cases[i]["co_month"],
              "listed": listed[cases[i]["station_key"]]} for i in pick]
    rows = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for r in pool.map(percounty_case, tasks, chunksize=4):
            rows.extend(r)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------------------------
# Summaries
# ---------------------------------------------------------------------------------------------

def summarize(res: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for gname, keys in (("crop", ["crop"]), ("crop_band", ["crop", "band"]), ("band", ["band"]), ("all", [])):
        for key, g in res.groupby(keys + ["family", "eval_set"]):
            d = dict(zip(keys + ["family", "eval_set"], key))
            w = g["acres"]
            rows.append({"grouping": gname, "crop": d.get("crop", "all"), "band": d.get("band", "all"),
                         "family": d["family"], "eval_set": d["eval_set"], "n_cases": len(g),
                         "he_pooled": pooled_he(g), "he_median": g["he"].median(),
                         "he_q25": g["he"].quantile(0.25), "he_q75": g["he"].quantile(0.75),
                         "share_he_ge_02": float((g["he"] >= 0.2).mean()),
                         "hedge_ratio": g["hedge_ratio"].mean(),
                         "p_tail": g["n_tail"].sum() / g["n_years"].sum(),
                         "tail_mean_loss": g["tail_loss_sum"].sum() / max(1, g["n_tail"].sum()),
                         "tail_mean_payout": g["tail_hedge_sum"].sum() / max(1, g["n_tail"].sum()),
                         "calm_mean_payout": g["calm_hedge_sum"].sum() / max(1, g["n_calm"].sum()),
                         "sd_loss": float(np.average(g["sd_loss"], weights=w)),
                         "sd_resid": float(np.average(g["sd_resid"], weights=w)),
                         "mean_loss": float(np.average(g["mean_loss"], weights=w)),
                         "fair_cost": float(np.average(g["fair_cost"], weights=w)),
                         "load": (float(np.average(g["load"][g["load"].notna()], weights=w[g["load"].notna()]))
                                  if g["load"].notna().any() else np.nan),
                         "thin_share": (float(np.average(g["thin_share"].fillna(0), weights=w))
                                        if g["load"].notna().any() else np.nan),
                         "n_legs": g["n_legs"].mean(),
                         "revenue_per_acre": float(np.average(g["revenue_per_acre"], weights=w))})
    return pd.DataFrame(rows)


def cost_table(summ: pd.DataFrame) -> pd.DataFrame:
    """Risk removed and yearly net cost of every design, with like-for-like break-even private loads."""
    lo = summ[summ["eval_set"] == "loyo"]
    rows = []
    for (grouping, crop, band), g in lo.groupby(["grouping", "crop", "band"]):
        f = g.set_index("family")
        for fam in ALL_FAMS:
            if fam == "K_ideal" or fam not in f.index:
                continue
            s_ = f.loc[fam]
            risk = s_["sd_loss"] - s_["sd_resid"]
            row = {"grouping": grouping, "crop": crop, "band": band, "family": fam, "n_cases": int(s_["n_cases"]),
                   "he": s_["he_pooled"], "sd_loss": s_["sd_loss"], "risk_removed": risk, "fair_cost": s_["fair_cost"],
                   "load_kalshi": s_["load"], "revenue_per_acre": s_["revenue_per_acre"]}
            if fam in KALSHI_PRICED:
                row["net_cost"] = (s_["load"] - 1) * s_["fair_cost"]
                row["cost_per_risk"] = row["net_cost"] / risk if risk > 0 else np.nan
                if fam in PAIRS:
                    pv = f.loc[PAIRS[fam]]
                    row["paired_private"] = PAIRS[fam]
                    row["breakeven_private_load"] = cb.breakeven_load(s_["load"], s_["fair_cost"], risk, pv["fair_cost"],
                                                                      pv["sd_loss"] - pv["sd_resid"])
            else:
                for L in PRIVATE_LOADS:
                    row[f"net_cost_{L}"] = (L - 1) * s_["fair_cost"]
                    row[f"cost_per_risk_{L}"] = (L - 1) * s_["fair_cost"] / risk if risk > 0 else np.nan
            rows.append(row)
    return pd.DataFrame(rows)


def coverage_table(counties: pd.DataFrame) -> pd.DataFrame:
    a = pd.read_csv(PROCESSED / "county_crop_acres.csv").merge(counties[["fips", "distance_mi"]], on="fips", how="left")
    rows = []
    for crop, g in a.groupby("crop"):
        col = "acres_harvested_2018_2022"
        tot = g[col].sum()
        known = g.dropna(subset=["distance_mi"]).sort_values("distance_mi")
        row = {"crop": crop, "acres_million": tot / 1e6, "counties": len(g)}
        for d in (25, 50, 100):
            row[f"share_within_{d}mi"] = known.loc[known["distance_mi"] <= d, col].sum() / tot
        cum = known[col].cumsum() / known[col].sum()
        row["acre_weighted_median_distance_mi"] = float(known["distance_mi"][cum >= 0.5].iloc[0])
        rows.append(row)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------------------------
# Tables and figures
# ---------------------------------------------------------------------------------------------

def md_table(df: pd.DataFrame, cols, headers, fmt=None) -> str:
    fmt = fmt or {}
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            f = fmt.get(c)
            if f is not None:
                cells.append(f(v))
            elif isinstance(v, (float, np.floating)):
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


def build_tables(res, summ, cost, cov, pc, n_stations) -> str:
    f2 = lambda v: "" if pd.isna(v) else f"{v:.2f}"  # noqa: E731
    f3 = lambda v: "" if pd.isna(v) else f"{v:.3f}"  # noqa: E731
    pct = lambda v: "" if pd.isna(v) else f"{100 * v:.0f}%"  # noqa: E731
    pct1 = lambda v: "" if pd.isna(v) else f"{100 * v:.1f}%"  # noqa: E731
    cents = lambda v: "" if pd.isna(v) else f"{100 * v:.2f}"  # noqa: E731
    count = lambda v: f"{int(v)}"  # noqa: E731
    parts = ["Generated by `scripts/run_crop_rain_benchmark.py`. Target = county yield shortfall below trend per $1 of "
             "expected revenue, NASS 1960-2025. HE = share of the year-to-year variance of that loss the hedge removes, "
             "pooled over counties; LOYO = the evaluated year is left out of both the payoff template and the hedge ratio. "
             "Fair cost = expected payout per $1 of expected revenue. Load = all-in Kalshi cost (fair + half a 4.5c spread "
             "+ taker fee) per $1 of expected payout.\n"]

    cov = cov.copy()
    cov["label"] = cov["crop"].map(cb.CROP_LABEL)
    cov["order"] = cov["crop"].map({c: i for i, c in enumerate(CROPS)})
    parts.append(f"**Table A. Where the crops are relative to Kalshi's rain stations** (acres harvested, NASS 2018-2022 mean; "
                 f"{n_stations} stations with a complete record since 1960; distance from the county centroid).")
    parts.append(md_table(cov.sort_values("order"),
                          ["label", "acres_million", "share_within_25mi", "share_within_50mi", "share_within_100mi",
                           "acre_weighted_median_distance_mi"],
                          ["Crop", "Acres (M)", "Within 25 mi", "Within 50 mi", "Within 100 mi", "Median acre's distance (mi)"],
                          {"acres_million": lambda v: f"{v:.1f}", "share_within_25mi": pct1, "share_within_50mi": pct1,
                           "share_within_100mi": pct1, "acre_weighted_median_distance_mi": lambda v: f"{v:.0f}"}))
    parts.append("")

    a = summ[summ["grouping"] == "all"]
    t = a[a["eval_set"] == "loyo"].set_index("family").reindex(ALL_FAMS).copy()
    t["he_in"] = a[a["eval_set"] == "in_sample"].set_index("family")["he_pooled"]
    t["label"] = [FAM_LABEL[k] for k in t.index]
    parts.append(f"**Table B. All crops, all counties within {MAX_DIST_MI:.0f} miles of a station "
                 f"({int(a['n_cases'].max())} county-crop cases).** The load column is Kalshi's trading cost; a private "
                 "policy carries the insurer's loading instead (Table F).")
    parts.append(md_table(t.reset_index(), ["label", "he_pooled", "he_in", "he_median", "share_he_ge_02", "hedge_ratio",
                                            "fair_cost", "load", "thin_share", "n_legs"],
                          ["Contract", "HE LOYO", "HE in-sample", "Median county HE", "Counties with HE >= 0.2", "Hedge ratio",
                           "Fair cost ($/$)", "Kalshi load", "Thin", "Legs"],
                          {"he_pooled": f2, "he_in": f2, "he_median": f2, "share_he_ge_02": pct, "hedge_ratio": f2,
                           "fair_cost": f3, "load": f2, "thin_share": lambda v: "" if pd.isna(v) else pct(v),
                           "n_legs": lambda v: "" if pd.isna(v) else f"{v:.1f}"}))
    parts.append("")
    t["tail_share"] = t["tail_mean_payout"] / t["tail_mean_loss"]
    t["lift"] = t["tail_mean_payout"] - t["fair_cost"]
    parts.append(f"**Table B2. Does the hedge pay in the bad years?** Bad year = county loss above {100 * TAIL_LOSS:.0f}% of expected "
                 f"revenue ({100 * t['p_tail'].iloc[0]:.0f}% of county-years, mean loss {100 * t['tail_mean_loss'].iloc[0]:.0f} cents "
                 f"per $1); no-loss year = loss under {100 * CALM_LOSS:.0f}%. Payouts are out of sample, in cents per $1 of expected revenue.")
    parts.append(md_table(t.reset_index(), ["label", "fair_cost", "tail_mean_payout", "calm_mean_payout", "lift", "tail_share"],
                          ["Contract", "Average payout", "Payout in bad years", "Payout in no-loss years",
                           "Bad-year payout above average", "Share of the bad-year loss paid"],
                          {"fair_cost": cents, "tail_mean_payout": cents, "calm_mean_payout": cents, "lift": cents, "tail_share": pct}))
    parts.append("")

    c = summ[(summ["grouping"] == "crop") & (summ["eval_set"] == "loyo")]
    piv = c.pivot_table(index="crop", columns="family", values="he_pooled").reindex(CROPS)
    piv["n"] = c.groupby("crop")["n_cases"].max()
    piv["mean_loss"] = c.groupby("crop")["mean_loss"].first()
    piv["sd_loss"] = c.groupby("crop")["sd_loss"].first()
    piv = piv.dropna(subset=["n"]).reset_index()
    piv["label"] = piv["crop"].map(cb.CROP_LABEL)
    parts.append("**Table C. Pooled LOYO HE by crop** (mean loss and its standard deviation are per $1 of expected revenue, "
                 "acre-weighted).")
    parts.append(md_table(piv, ["label", "n", "mean_loss", "sd_loss"] + ORDER,
                          ["Crop", "Cases", "Mean loss", "SD of loss"] + [FAM_SHORT[k] for k in ORDER],
                          {"n": count, "mean_loss": f3, "sd_loss": f3, **{k: f2 for k in ORDER}}))
    parts.append("")

    b = summ[(summ["grouping"] == "band") & (summ["eval_set"] == "loyo")]
    piv = b.pivot_table(index="band", columns="family", values="he_pooled").reindex([lab for *_, lab in BANDS])
    piv["n"] = b.groupby("band")["n_cases"].max()
    lo = res[res["eval_set"] == "loyo"]
    piv["rain_corr"] = lo.groupby("band")["station_county_rain_corr"].mean()
    piv = piv.dropna(subset=["n"]).reset_index()
    parts.append("**Table D. Pooled LOYO HE by distance from the station** (all crops). Rain correlation = station season "
                 "total against the county's own. The local-rain columns do not use the station; they vary across bands only "
                 "because the counties differ.")
    parts.append(md_table(piv, ["band", "n", "rain_corr"] + ORDER,
                          ["Distance", "Cases", "Rain correlation"] + [FAM_SHORT[k] for k in ORDER],
                          {"n": count, "rain_corr": f2, **{k: f2 for k in ORDER}}))
    parts.append("")

    cb_ = summ[(summ["grouping"] == "crop_band") & (summ["eval_set"] == "loyo")]
    piv = cb_.pivot_table(index=["crop", "band"], columns="family", values="he_pooled")
    piv["n"] = cb_.groupby(["crop", "band"])["n_cases"].max()
    piv = piv.reset_index()
    piv["label"] = piv["crop"].map(cb.CROP_LABEL)
    piv["o1"] = piv["crop"].map({c_: i for i, c_ in enumerate(CROPS)})
    piv["o2"] = piv["band"].map({lab: i for i, (*_, lab) in enumerate(BANDS)})
    parts.append("**Table D2. Pooled LOYO HE by crop and distance.** Cells with fewer than 5 cases share the crop-wide hedge ratio.")
    parts.append(md_table(piv.sort_values(["o1", "o2"]), ["label", "band", "n"] + ORDER,
                          ["Crop", "Distance", "Cases"] + [FAM_SHORT[k] for k in ORDER], {"n": count, **{k: f2 for k in ORDER}}))
    parts.append("")

    w = lo.pivot_table(index=["crop", "fips"], columns="family", values="he")
    meta = lo.drop_duplicates(["crop", "fips"]).set_index(["crop", "fips"])
    w["dry"] = pd.cut(meta["station_month_mean_in"], [0, 2, 3, 4, 99], labels=["under 2 in", "2-3 in", "3-4 in", "over 4 in"])
    rows = []
    for lab, g in w.groupby("dry", observed=True):
        sub = lo.merge(g.reset_index()[["crop", "fips"]], on=["crop", "fips"])
        row = {"dry": lab, "n": len(g)}
        for fam in ("K_today", "K_third", "K_ideal", "P_month"):
            row[fam] = pooled_he(sub[sub["family"] == fam])
        d = g["K_third"] - g["K_today"]
        row["better"], row["worse"] = float((d > 0.02).mean()), float((d < -0.02).mean())
        rows.append(row)
    parts.append("**Table E. What third-inch strikes add, by how wet the station's season months are** (mean rain per season "
                 "month at the station). Better / worse = share of counties where third-inch strikes beat / trail today's "
                 "whole-inch strikes by more than 0.02 of HE.")
    parts.append(md_table(pd.DataFrame(rows), ["dry", "n", "K_today", "K_third", "K_ideal", "better", "worse", "P_month"],
                          ["Station season-month mean", "Cases", "Today, both sides", "Third-inch", "Station, exact", "Better",
                           "Worse", "Local rain, monthly"],
                          {"n": count, "K_today": f2, "K_third": f2, "K_ideal": f2, "better": pct, "worse": pct, "P_month": f2}))
    parts.append("")

    def frontier(sub: pd.DataFrame) -> pd.DataFrame:
        out = []
        for _, r in sub.iterrows():
            base = {"label": FAM_LABEL[r["family"]], "he": r["he"], "risk": r["risk_removed"], "fair": r["fair_cost"]}
            if r["family"] in KALSHI_PRICED:
                out.append({**base, "pricing": f"Kalshi, load {r['load_kalshi']:.2f}", "net": r["net_cost"],
                            "cpr": r["cost_per_risk"], "be": r.get("breakeven_private_load", np.nan)})
            else:
                for L in PRIVATE_LOADS:
                    out.append({**base, "pricing": f"private at {L}x", "net": r[f"net_cost_{L}"], "cpr": r[f"cost_per_risk_{L}"],
                                "be": np.nan})
        return pd.DataFrame(out)

    fam_rank = {k: i for i, k in enumerate(ALL_FAMS)}
    for crop, title in (("all", "all crops"), ("corn", "corn"), ("soybeans", "soybeans")):
        sub = cost[(cost["grouping"] == ("all" if crop == "all" else "crop")) & (cost["crop"] == crop)
                   & (cost["family"] != "K_today_dry")].copy()
        sub = sub.sort_values("family", key=lambda x: x.map(fam_rank))
        head = ("**Table F. Risk removed against what it costs, " + title + ".** Risk removed = fall in the standard deviation of "
                "the loss, cents per $1 of expected revenue, out of sample. Net cost = what the buyer gives up a year in "
                "expectation, (load - 1) x expected payout. Cost per unit of risk = net cost / risk removed. Break-even private "
                "load = the loading at which the same template paid on the county's own rain costs the same per unit of risk; "
                "a private policy priced above it is the worse buy on this measure."
                if crop == "all" else f"**Table F-{crop}. The same for {title}.**")
        parts.append(head)
        parts.append(md_table(frontier(sub), ["label", "pricing", "he", "fair", "risk", "net", "cpr", "be"],
                              ["Design", "Priced at", "HE", "Expected payout (c)", "Risk removed (c)", "Net cost a year (c)",
                               "Cost per unit of risk", "Break-even private load"],
                              {"he": f2, "fair": cents, "risk": cents, "net": cents, "cpr": f2, "be": f2}))
        parts.append("")

    cbd = cost[(cost["grouping"] == "band") & cost["family"].isin(list(PAIRS))].copy()
    cbd["fam"] = cbd["family"].map(FAM_LABEL)
    cbd["o"] = cbd["band"].map({lab: i for i, (*_, lab) in enumerate(BANDS)})
    cbd["o2"] = cbd["family"].map(fam_rank)
    parts.append("**Table F2. Kalshi designs by distance** (all crops).")
    parts.append(md_table(cbd.sort_values(["o", "o2"]),
                          ["band", "fam", "n_cases", "he", "risk_removed", "load_kalshi", "net_cost", "cost_per_risk",
                           "breakeven_private_load"],
                          ["Distance", "Kalshi design", "Cases", "HE", "Risk removed (c)", "Kalshi load", "Net cost a year (c)",
                           "Cost per unit of risk", "Break-even private load"],
                          {"n_cases": count, "he": f2, "risk_removed": cents, "load_kalshi": f2, "net_cost": cents,
                           "cost_per_risk": f2, "breakeven_private_load": f2}))
    parts.append("")

    usd = lambda v: "" if pd.isna(v) else f"${v:,.2f}"  # noqa: E731
    usd0 = lambda v: "" if pd.isna(v) else f"${v:,.0f}"  # noqa: E731
    cc = cost[cost["grouping"] == "crop"].set_index(["crop", "family"])
    rows = []
    for crop in CROPS:
        if (crop, "K_third_lean") not in cc.index:
            continue
        k, pm, ps = cc.loc[(crop, "K_third_lean")], cc.loc[(crop, "P_month_lean")], cc.loc[(crop, "P_season_lean")]
        rev = k["revenue_per_acre"]
        rows.append({"label": cb.CROP_LABEL[crop], "rev": rev, "sd": k["sd_loss"] * rev,
                     "k_prem": k["load_kalshi"] * k["fair_cost"] * rev, "k_net": k["net_cost"] * rev, "k_risk": k["risk_removed"] * rev,
                     "pm_prem": 1.5 * pm["fair_cost"] * rev, "pm_net": pm["net_cost_1.5"] * rev, "pm_risk": pm["risk_removed"] * rev,
                     "ps_prem": 1.5 * ps["fair_cost"] * rev, "ps_net": ps["net_cost_1.5"] * rev, "ps_risk": ps["risk_removed"] * rev})
    parts.append("**Table G. Dollars per acre, deep-strike designs** (each at its minimum-variance size; expected revenue = 2025 "
                 "trend yield x the 2026/27 WASDE price, acre-weighted over the study counties; private premiums at 1.5x).")
    parts.append(md_table(pd.DataFrame(rows), ["label", "rev", "sd", "k_prem", "k_net", "k_risk", "pm_prem", "pm_net", "pm_risk",
                                                "ps_prem", "ps_net", "ps_risk"],
                          ["Crop", "Expected revenue", "SD of yield loss", "Kalshi third-inch: cost", "net cost a year", "SD removed",
                           "Private monthly: premium", "net cost a year", "SD removed", "Private season total: premium",
                           "net cost a year", "SD removed"],
                          {"rev": usd0, "sd": usd0, **{c_: usd for c_ in ["k_prem", "k_net", "k_risk", "pm_prem", "pm_net", "pm_risk",
                                                                         "ps_prem", "ps_net", "ps_risk"]}}))
    parts.append("")

    rows = []
    for sk, gsk in lo.groupby("station_key"):
        row = {"station": sk, "n": gsk.drop_duplicates(["crop", "fips"]).shape[0],
               "month_mean": gsk["station_month_mean_in"].mean(), "dist": gsk["distance_mi"].mean(),
               "rain_corr": gsk["station_county_rain_corr"].mean()}
        for fam in ("K_today", "K_third", "K_ideal", "P_month"):
            row[fam] = pooled_he(gsk[gsk["family"] == fam])
        rows.append(row)
    hs = pd.DataFrame(rows).sort_values("n", ascending=False)
    hs = hs[hs["n"] >= 5]
    parts.append("**Table H. By station** (stations with at least 5 county-crop cases).")
    parts.append(md_table(hs, ["station", "n", "dist", "month_mean", "rain_corr", "K_today", "K_third", "K_ideal", "P_month"],
                          ["Station", "Cases", "Mean distance (mi)", "Season-month mean (in)", "Rain correlation",
                           "Today, both sides", "Third-inch", "Station, exact", "Local rain, monthly"],
                          {"n": count, "dist": lambda v: f"{v:.0f}", "month_mean": f2, "rain_corr": f2,
                           "K_today": f2, "K_third": f2, "K_ideal": f2, "P_month": f2}))
    parts.append("")

    if pc is not None and not pc.empty:
        rows = []
        for fam, gp in pc.groupby("family", sort=False):
            rows.append({"family": fam, "n": len(gp[gp["eval_set"] == "loyo"]),
                         "he_in": pooled_he(gp[gp["eval_set"] == "in_sample"]),
                         "he_lo": pooled_he(gp[gp["eval_set"] == "loyo"]),
                         "med_lo": gp[gp["eval_set"] == "loyo"]["he"].median(),
                         "legs": gp[gp["eval_set"] == "loyo"]["n_legs"].mean()})
        parts.append("**Table I. Check: fitting a ladder county by county instead of using a state template** (random sample "
                     "of cases, NNLS with a free intercept and doc 08's ridge penalties). The gap between in-sample and "
                     "out-of-sample fit is the reason the template method is used.")
        parts.append(md_table(pd.DataFrame(rows), ["family", "n", "he_in", "he_lo", "med_lo", "legs"],
                              ["Ladder", "Cases", "HE in-sample", "HE LOYO", "Median county HE (LOYO)", "Legs used"],
                              {"n": count, "he_in": f2, "he_lo": f2, "med_lo": f2, "legs": lambda v: f"{v:.1f}"}))
    return "\n".join(parts)


def _style(ax):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(C_GRID)
    ax.tick_params(colors=C_TEXT2, labelsize=8.5, length=0)
    ax.set_axisbelow(True)


def fig_by_crop(summ: pd.DataFrame, path: Path):
    c = summ[(summ["grouping"] == "crop") & (summ["eval_set"] == "loyo")]
    crops = [k for k in CROPS if k in set(c["crop"])]
    show = [("K_today", C_BLUE, "Kalshi today (whole-inch strikes)"), ("K_third", C_AQUA, "Kalshi third-inch strikes"),
            ("P_month", C_ORANGE, "Private benchmark (county's own rain)")]
    fig, ax = plt.subplots(figsize=(10.5, 4.6), facecolor="#fcfcfb")
    x = np.arange(len(crops))
    w = 0.26
    for i, (fam, col, lab) in enumerate(show):
        v = [float(c[(c["crop"] == k) & (c["family"] == fam)]["he_pooled"].iloc[0]) for k in crops]
        ax.bar(x + (i - 1) * w, v, width=w - 0.03, color=col, label=lab)
        for xi, vi in zip(x + (i - 1) * w, v):
            ax.text(xi, max(vi, 0) + 0.006, f"{vi:.2f}", ha="center", fontsize=8, color=C_TEXT)
    ax.set_xticks(x)
    ax.set_xticklabels([cb.CROP_LABEL[k] for k in crops], color=C_TEXT)
    ax.set_ylabel("share of yield-loss variance removed (out of sample)", fontsize=8.5, color=C_TEXT2)
    ax.yaxis.grid(True, color=C_GRID, linewidth=0.8)
    ax.axhline(0, color=C_TEXT2, linewidth=0.8)
    ax.legend(frameon=False, fontsize=8.5, loc="upper left")
    ax.set_title("Rain contracts against real county yield losses, counties within 100 miles of a Kalshi station",
                 fontsize=11, color=C_TEXT, loc="left")
    _style(ax)
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def fig_distance(res: pd.DataFrame, path: Path):
    lo = res[res["eval_set"] == "loyo"]
    edges = np.array([0, 20, 30, 40, 50, 60, 70, 80, 90, 100.001])
    mids = 0.5 * (edges[:-1] + edges[1:])
    fig, ax = plt.subplots(figsize=(8.5, 4.6), facecolor="#fcfcfb")
    for fam, col, lab in (("P_month", C_ORANGE, "Private benchmark (county's own rain)"),
                          ("K_third", C_AQUA, "Kalshi third-inch strikes (station rain)"),
                          ("K_today", C_BLUE, "Kalshi today (station rain)")):
        g = lo[lo["family"] == fam]
        v = [pooled_he(g[(g["distance_mi"] >= a) & (g["distance_mi"] < b)]) for a, b in zip(edges[:-1], edges[1:])]
        ax.plot(mids, v, color=col, linewidth=2, marker="o", markersize=4, label=lab)
    ax.set_xlabel("distance from the station to the county centroid, miles", fontsize=8.5, color=C_TEXT2)
    ax.set_ylabel("pooled HE (out of sample)", fontsize=8.5, color=C_TEXT2)
    ax.yaxis.grid(True, color=C_GRID, linewidth=0.8)
    ax.axhline(0, color=C_TEXT2, linewidth=0.8)
    ax.legend(frameon=False, fontsize=8.5)
    ax.set_title("Geography: the station contract fades with distance, the local contract does not", fontsize=11,
                 color=C_TEXT, loc="left")
    _style(ax)
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def fig_frontier(cost: pd.DataFrame, path: Path):
    """Risk removed against yearly net cost for every design, all crops: lower right is better."""
    c = cost[(cost["grouping"] == "all") & (cost["family"] != "K_today_dry")].set_index("family")
    fig, ax = plt.subplots(figsize=(9.5, 5.4), facecolor="#fcfcfb")
    for fam in [k for k in KALSHI_PRICED if k in c.index and k != "K_today_dry"]:
        r = c.loc[fam]
        new = fam.startswith("K_season")
        ax.scatter(100 * r["risk_removed"], 100 * r["net_cost"], s=70, color=C_BLUE if not new else "#86b6ef", zorder=3,
                   edgecolor="white", linewidth=0.8)
    if "K_third" in c.index:
        r = c.loc["K_third"]
        ax.annotate("Kalshi monthly ladders:\nwhole-inch, third-inch,\nwith and without deep strikes",
                    (100 * r["risk_removed"], 100 * r["net_cost"]), textcoords="offset points", xytext=(-6, 26), fontsize=8,
                    color=C_TEXT, ha="center", arrowprops={"arrowstyle": "-", "color": C_TEXT2, "linewidth": 0.6})
    if "K_season" in c.index:
        r = c.loc["K_season"]
        ax.annotate("Station season total,\nfull and deep", (100 * r["risk_removed"], 100 * r["net_cost"]),
                    textcoords="offset points", xytext=(-22, 78), fontsize=8, color=C_TEXT, ha="center",
                    arrowprops={"arrowstyle": "-", "color": C_TEXT2, "linewidth": 0.6})
    for fam in [k for k in PRIVATE if k in c.index]:
        r = c.loc[fam]
        x = 100 * r["risk_removed"]
        lo, hi = 100 * r[f"net_cost_{PRIVATE_LOADS[0]}"], 100 * r[f"net_cost_{PRIVATE_LOADS[-1]}"]
        ax.plot([x, x], [lo, hi], color=C_ORANGE, linewidth=3, alpha=0.55, zorder=2, solid_capstyle="round")
        ax.scatter([x], [lo], s=70, color=C_ORANGE, zorder=3, edgecolor="white", linewidth=0.8)
        ax.annotate(FAM_SHORT[fam], (x, lo), textcoords="offset points", xytext=(7, -3), fontsize=8, color=C_TEXT)
    ax.scatter([], [], s=70, color=C_BLUE, label="Kalshi monthly contracts on station rain (at Kalshi trading cost)")
    ax.scatter([], [], s=70, color="#86b6ef", label="Station season-total contract (not listed)")
    ax.plot([], [], color=C_ORANGE, linewidth=3, marker="o", markevery=[0],
            label=f"Private policy on the county's own rain (dot = {PRIVATE_LOADS[0]}x, bar up to {PRIVATE_LOADS[-1]}x)")
    ax.set_xlabel("risk removed: fall in the standard deviation of yield loss, cents per $1 of expected revenue", fontsize=8.5,
                  color=C_TEXT2)
    ax.set_ylabel("net cost a year, cents per $1 of expected revenue", fontsize=8.5, color=C_TEXT2)
    ax.set_xlim(0, None)
    ax.set_ylim(0, None)
    ax.yaxis.grid(True, color=C_GRID, linewidth=0.8)
    ax.xaxis.grid(True, color=C_GRID, linewidth=0.8)
    ax.legend(frameon=False, fontsize=8.5, loc="upper left")
    ax.set_title("What each rain hedge removes and what it costs (all crops, counties within 100 miles; lower right is better)",
                 fontsize=10.5, color=C_TEXT, loc="left")
    _style(ax)
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def fig_templates(tmpl_m: dict, path: Path):
    show = [("corn", "IL"), ("soybeans", "OH"), ("winter_wheat", "OK"), ("cotton", "TX")]
    show = [s for s in show if s in tmpl_m]
    if not show:
        return
    x = np.linspace(0, 3, 301)
    palette = [C_BLUE, C_ORANGE, C_AQUA, "#eda100", "#e87ba4"]
    names = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun", 7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"}
    fig, axes = plt.subplots(1, len(show), figsize=(3.6 * len(show), 3.8), facecolor="#fcfcfb", sharey=True)
    for ax, key in zip(np.atleast_1d(axes), show):
        a = tmpl_m[key]["full"]
        nb = len(IS_CALL_MONTH)
        for j, (off, mon) in enumerate(cb.SEASONS[key[0]]):
            co = a[j * nb:(j + 1) * nb]
            pay = sum(c_ * np.clip(k - x, 0, None) for c_, k in zip(co[:len(cb.MONTH_PUT_K)], cb.MONTH_PUT_K)) \
                + sum(c_ * np.clip(x - k, 0, None) for c_, k in zip(co[len(cb.MONTH_PUT_K):], cb.MONTH_CALL_K))
            ax.plot(100 * x, 100 * pay, color=palette[j % len(palette)], linewidth=2,
                    label=names[mon] + (" (prior year)" if off < 0 else ""))
        ax.set_title(f"{cb.CROP_LABEL[key[0]]}, {key[1]} ({tmpl_m[key]['n_counties']} counties)", fontsize=9.5, color=C_TEXT, loc="left")
        ax.set_xlabel("month's rain, % of normal", fontsize=8.5, color=C_TEXT2)
        ax.yaxis.grid(True, color=C_GRID, linewidth=0.8)
        ax.legend(frameon=False, fontsize=8)
        _style(ax)
    np.atleast_1d(axes)[0].set_ylabel("template payout, % of expected revenue", fontsize=8.5, color=C_TEXT2)
    fig.suptitle("Fitted payoff templates: what each month's rain says about yield loss", fontsize=11, color=C_TEXT, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()
    t0 = time.time()

    stations, monthly, listed = load_stations()
    counties = load_counties(stations)
    log(f"{len(stations)} stations with a complete record")
    cov = coverage_table(counties)
    panel = build_panel(counties)
    log(f"panel: {len(panel)} county-crop series, {len({p['group'] for p in panel})} crop-state groups ({time.time() - t0:.0f}s)")
    tmpl = {"month": fit_templates(panel, "B_month"), "season": fit_templates(panel, "B_season"),
            "month_lean": fit_templates(panel, "B_month", LEAN_MONTH),
            "season_lean": fit_templates(panel, "B_season", LEAN_SEASON)}
    tmpl_m = tmpl["month"]
    log(f"templates fitted ({time.time() - t0:.0f}s)")
    res = evaluate(panel, monthly, listed, tmpl, 30.0 if args.quick else MAX_DIST_MI)
    summ = summarize(res)
    cost = cost_table(summ)
    log(summ[summ["grouping"] == "all"][["family", "eval_set", "n_cases", "he_pooled", "he_median", "hedge_ratio", "fair_cost", "load"]]
        .round(3).to_string())
    if args.quick:
        return
    log("per-county fitting check ...")
    pc = percounty_check(panel, monthly, listed, args.workers)
    cov.to_csv(PROCESSED / "crop_benchmark_coverage.csv", index=False)
    res.to_parquet(PROCESSED / "crop_benchmark_cases.parquet", index=False)
    summ.to_csv(PROCESSED / "crop_benchmark_summary.csv", index=False)
    cost.to_csv(PROCESSED / "crop_benchmark_cost.csv", index=False)
    pc.to_csv(PROCESSED / "crop_benchmark_percounty_check.csv", index=False)
    template_table(tmpl_m).to_csv(PROCESSED / "crop_benchmark_templates.csv", index=False)
    fig_by_crop(summ, FIGURES / "x3_crop_he_by_contract.png")
    fig_distance(res, FIGURES / "x3_crop_he_by_distance.png")
    fig_frontier(cost, FIGURES / "x3_crop_risk_vs_cost.png")
    fig_templates(tmpl_m, FIGURES / "x3_crop_templates.png")
    text = build_tables(res, summ, cost, cov, pc, len(stations))
    replace_between_markers(DOC, "<!-- BEGIN AUTO: crop benchmark tables (scripts/run_crop_rain_benchmark.py) -->",
                            "<!-- END AUTO: crop benchmark tables (scripts/run_crop_rain_benchmark.py) -->",
                            text, PROCESSED / "crop_benchmark_tables.md")
    log(f"done ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
