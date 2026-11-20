"""Expansion lenses (doc 25 follow-ups): lender-book HE, ENSO in Kalshi prices, solar as a wet side.

Three checks, each printed and written to data/processed/expansion_lens_*.csv.

1. Lender-portfolio hedge effectiveness (doc 25 "key test of shortlist #1").
   a) The PRF Companion's 11 sample farms, one per farm, built exactly as doc 21:
      - holdout: months picked and hedges fit on 1951-2000, scored on 2001-2025
        (scripts/run_companion_holdout.py);
      - LOYO: months picked on all years (platform._score, HE >= 0.5), package hedge at the 95% knee,
        each year predicted by a fit that left that calendar year out.
   b) The pooled book: sum of farm gap targets against the sum of the farms' hedge payouts.
   c) Same-station footprints: up to 40 random PRF grids within 100 miles of DFW, OKC, SAT and SGF,
      each with the same Nov-Feb gap cover (PRF-style, 90% trigger, $100k/6 per month) hedged at that
      one station. Book HE for the sum of per-farm hedges and for one hedge refit to the pooled target;
      book-size curve; mean pairwise correlation of targets (rho_y) and of hedge residuals (rho_e).
   Each is split by ENSO phase of the season (Jul-Jun season, phase from that year's Aug-Oct ONI:
   El Nino >= 0.5, La Nina <= -0.5, scripts/experiments/expansion_review/dl/oni.txt).

2. Does Kalshi price ENSO? Market-implied P(rain > K) against 1991-2025 and 1951-2025 climatology and
   ENSO-conditional climatology (station_monthly_precip.csv):
   - winter 2025-26 candles (only season with history; ASO 2025 ONI -0.43, neutral by the rule above);
   - Nov 2026 book mids (kalshi_rain_orderbook_summary_20261102.csv) and the last pre-month candles,
     against El Nino-conditional climatology (ASO 2026 ONI +2.46). Cross-station regression of
     (market - climatology) on (El Nino-conditional - climatology), bootstrap over seasons.

3. Solar as a wet-side counterparty. NASA POWER monthly ALLSKY_SFC_SW_DWN, 1984-2025, at DFW, AUS, SAT,
   HOU and OKC (cached in data/raw/nasa_power/). Irradiance vs rain anomaly correlation; share of a
   solar plant's monthly energy variance (output proportional to irradiance) removed by Kalshi YES
   contracts (LOYO, non-negative fit) and by a single 70th/95th-percentile rain call; netting of a
   rancher's rain put (30th percentile) with the solar owner's wet call, or with an irradiance put,
   at equal premium with a 20% load (run_expansion_netting.py conventions), against a second
   independent put (year-shuffled) as the pure-diversification baseline.

Usage: python scripts/run_expansion_lenses.py [--offline]   (about 2-3 minutes)
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import nnls

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_expansion_netting as rx  # noqa: E402

from agri_hedge import hedge_builder as hb  # noqa: E402
from agri_hedge import optimizer as op  # noqa: E402
from agri_hedge.config import FIGURES, PROCESSED, RAW, ROOT  # noqa: E402
from agri_hedge.hedge_builder import CoverageRequest, Window  # noqa: E402
from agri_hedge.locations import haversine_miles  # noqa: E402
from agri_hedge.platform import GOOD_HE, KNEE_SHARE, _score  # noqa: E402
from agri_hedge.prf_grid import grid_id_to_center  # noqa: E402
from agri_hedge.stations import _cached_json, _request_json  # noqa: E402

TRAIN, TEST = (1951, 2000), (2001, 2025)
ONI_FILE = ROOT / "scripts" / "experiments" / "expansion_review" / "dl" / "oni.txt"
EL_NINO, LA_NINA, STRONG = 0.5, -0.5, 1.5
PHASES = ("El Nino", "neutral", "La Nina")
SEED = 473

FOOT_STATIONS = ["DFW", "OKC", "SAT", "SGF"]
FOOT_RADIUS_MI = 100.0
FOOT_N = 40
FOOT_MONTHS = (11, 12, 1, 2)
FOOT_PROTECTION = 100_000.0          # PRF policy protection; gap cover = protection / 6 per month (doc 21)
FOOT_COVERAGE = 0.90
BOOK_SIZES = (1, 2, 5, 10, 20, 40)
N_SUBSETS = 200

SOUTH_CENTRAL = rx.REGIONS["south_central"]
SOUTHEAST = rx.REGIONS["southeast"]
MAX_SPREAD = 0.20                    # use a quote's mid only if the spread is at most 20 cents
N_BOOT = 500

SOLAR_STATIONS = ["DFW", "AUS", "SAT", "HOU", "OKC"]
POWER_URL = "https://power.larc.nasa.gov/api/temporal/monthly/point"
POWER_YEARS = (1984, 2025)
POWER_DIR = RAW / "nasa_power"
WINTER = (11, 12, 1, 2)
N_SHUFFLE = 200


# =============================================================================================
# shared helpers (tested in tests/test_expansion_lenses.py)
# =============================================================================================
def load_aso_oni(path: Path = ONI_FILE) -> pd.Series:
    """Aug-Oct ONI by year (CPC table: SEAS YR TOTAL ANOM)."""
    oni = pd.read_csv(path, sep=r"\s+")
    return oni[oni["SEAS"] == "ASO"].set_index("YR")["ANOM"].astype(float).rename("aso_oni")


def enso_phase(oni) -> np.ndarray:
    o = np.asarray(oni, float)
    return np.select([o >= EL_NINO, o <= LA_NINA], ["El Nino", "La Nina"], "neutral")


def season_year(year, month) -> np.ndarray:
    """Jul-Jun season labelled by the year it starts: Nov 2026 -> 2026, Jan 2027 -> 2026."""
    y, m = np.asarray(year), np.asarray(month)
    return np.where(m >= 7, y, y - 1)


def mean_offdiag(m: np.ndarray) -> float:
    m = np.asarray(m, float)
    if m.shape[0] < 2:
        return float("nan")
    return float(m[~np.eye(m.shape[0], dtype=bool)].mean())


def book_stats(Y: np.ndarray, H: np.ndarray, limit: bool = False) -> dict:
    """Y, H: seasons/years x farms (complete cases). Pooled HE and the correlation structure behind it.

    he_if_uncorrelated = 1 - sum Var(e_f) / sum Var(y_f): the pooled HE if no two farms co-moved, so
    he_pooled - he_if_uncorrelated is what cross-farm correlation adds (e = y - h).
    he_limit (only when limit=True, for same-station books) is the large-book limit with these average
    covariances: 1 - mean off-diagonal Cov(e) / mean off-diagonal Cov(y).
    """
    Y, H = np.asarray(Y, float), np.asarray(H, float)
    E = Y - H
    out = {"n_farms": Y.shape[1], "n_years": Y.shape[0],
           "he_pooled": op.hedge_effectiveness(Y.sum(1), H.sum(1)),
           "he_farm_median": float(np.nanmedian([op.hedge_effectiveness(Y[:, j], H[:, j]) for j in range(Y.shape[1])]))}
    if Y.shape[1] >= 2:
        cy, ce = np.cov(Y, rowvar=False), np.cov(E, rowvar=False)
        out["rho_y"] = mean_offdiag(np.corrcoef(Y, rowvar=False))
        out["rho_e"] = mean_offdiag(np.corrcoef(E, rowvar=False))
        out["he_if_uncorrelated"] = float(1 - np.trace(ce) / np.trace(cy))
        oy = mean_offdiag(cy)
        if limit:
            out["he_limit"] = 1 - mean_offdiag(ce) / oy if oy > 0 else float("nan")
    return out


def loyo_leg_payouts(X, y, tranches, budget, scale) -> np.ndarray:
    """Like optimizer.loyo_payout, but keeps each leg's out-of-sample payout (years x legs)."""
    X, y = np.asarray(X, float), np.asarray(y, float)
    ok = ~np.isnan(y) & ~np.isnan(X).any(axis=1)
    out = np.full(X.shape, np.nan)
    for i in np.flatnonzero(ok):
        keep = ok.copy()
        keep[i] = False
        sol = (op.solve_penalized(X[keep], y[keep], tranches, 0.0, scale) if budget is None else
               op.solve_budget(X[keep], y[keep], tranches, budget, scale, tol=1e-3))
        out[i] = X[i] * sol.leg_contracts
    return out


def survival(x, strikes) -> np.ndarray:
    """P(X > K) for each strike, Kalshi 'Above K inches' convention (pricing.no_pays: NO pays x <= K)."""
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    return np.array([(x > float(k) + 1e-9).mean() for k in strikes])


def implied_mean(strikes, s) -> float:
    """E[min(X, Kmax)] from survival probabilities at whole-inch strikes, S(0) = 1, trapezoid rule."""
    k = np.concatenate([[0.0], np.asarray(strikes, float)])
    sv = np.concatenate([[1.0], np.asarray(s, float)])
    return float(np.sum(np.diff(k) * (sv[1:] + sv[:-1]) / 2))


def nnls_loyo_he(X, y) -> float:
    """Out-of-sample HE of a non-negative linear hedge with a free intercept (leave one year out)."""
    X, y = np.atleast_2d(np.asarray(X, float).T).T, np.asarray(y, float)
    n = len(y)
    pred = np.empty(n)
    for i in range(n):
        k = np.arange(n) != i
        xm, ym = X[k].mean(0), y[k].mean()
        w, _ = nnls(X[k] - xm, y[k] - ym)
        pred[i] = ym + (X[i] - xm) @ w
    return float(1 - np.var(y - pred) / np.var(y)) if np.var(y) > 0 else float("nan")


def zscore_by(df: pd.DataFrame, col: str, by: list[str]) -> pd.Series:
    g = df.groupby(by)[col]
    return (df[col] - g.transform("mean")) / g.transform("std")


# =============================================================================================
# 1. lender-portfolio HE
# =============================================================================================
def fit_package(lat, lon, months, coverage, gap, station_key, grid_id, mode: str) -> pd.DataFrame | None:
    """Long frame (year, month, y, h) for one farm's gap-month package.

    mode 'holdout': knee hedge fit on TRAIN years, applied to every year (score on TEST).
    mode 'loyo': knee budget from all years, each year's payout from a fit leaving that year out.
    """
    months = list(months)
    prot = gap * len(months)
    req = CoverageRequest(lat, lon, [Window((m,), 1.0 / len(months)) for m in months], coverage, prot,
                          station_key=station_key, grid_id=grid_id)
    try:
        p = hb.build_problem(req)
    except ValueError:
        return None
    yrs = p.years
    tr = op.model_tranches(p.q)
    if mode == "holdout":
        m = (yrs >= TRAIN[0]) & (yrs <= TRAIN[1]) & p.ok
        if m.sum() < 30:
            return None
        fr = op.efficient_frontier(p.X[m], p.target[m], tr, n_points=13, scale=prot, q=p.q)
        sol = op.solve_budget(p.X[m], p.target[m], tr, op.knee_budget(fr, KNEE_SHARE), prot)
        leg_pay = p.X * sol.leg_contracts
        leg_pay[~p.ok] = np.nan
    else:
        ok = p.ok
        if ok.sum() < 40:
            return None
        fr = op.efficient_frontier(p.X[ok], p.target[ok], tr, n_points=13, scale=prot, q=p.q)
        leg_pay = loyo_leg_payouts(p.X, np.where(ok, p.target, np.nan), tr, op.knee_budget(fr, KNEE_SHARE), prot)
    leg_month = np.array([lm for lm, _ in p.legs])
    rows = []
    for mo in months:
        y = np.asarray(p.target_by_window[hb.MONTH_ABBR[mo - 1]], float)
        h = leg_pay[:, leg_month == mo].sum(axis=1)
        h[np.isnan(leg_pay[:, leg_month == mo]).any(axis=1)] = np.nan
        rows.append(pd.DataFrame({"year": yrs, "month": mo, "y": np.where(p.ok, y, np.nan), "h": h}))
    out = pd.concat(rows, ignore_index=True)
    out["distance_mi"] = p.distance_mi
    return out


def pick_months(F: dict, mode: str) -> list[int]:
    r, gap = F["request"], F["protection"] / 6
    covered = {m for w in r.windows for m in w.months}
    picked = []
    for m in sorted(set(range(1, 13)) - covered):
        pm = hb.build_problem(CoverageRequest(r.lat, r.lon, [Window((m,), 1.0)], r.coverage, gap,
                                              station_key=r.station_key, grid_id=r.grid_id))
        if mode == "holdout":
            msk = (pm.years >= TRAIN[0]) & (pm.years <= TRAIN[1]) & pm.ok
            X, y = pm.X[msk], pm.target[msk]
            tr = op.model_tranches(pm.q)
            fr = op.efficient_frontier(X, y, tr, n_points=13, scale=gap, q=pm.q)
            b = op.knee_budget(fr, KNEE_SHARE)
            if np.var(y) > 0 and op.hedge_effectiveness(y, op.loyo_payout(X, y, tr, b, gap)) >= GOOD_HE:
                picked.append(m)
        else:
            sc = _score(pm.X, pm.target, pm.q, gap)
            if sc and sc["he_out_of_sample"] >= GOOD_HE:
                picked.append(m)
    return picked


def aggregate(long: pd.DataFrame, by: str, years: tuple | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """long: farm, year, month, y, h (+ weight). Returns (Y, H) wide by period x farm, complete cases only.

    by 'calendar' sums each calendar year's months (doc 21's convention); 'season' sums Jul-Jun seasons.
    """
    d = long.copy()
    d["period"] = d["year"] if by == "calendar" else season_year(d["year"], d["month"])
    n_mon = d.groupby("farm")["month"].nunique()
    g = d.groupby(["farm", "period"])
    agg = pd.DataFrame({"y": g["y"].sum(min_count=1), "h": g["h"].sum(min_count=1),
                        "n": g["y"].count(), "nh": g["h"].count()}).reset_index()
    agg = agg[(agg["n"] == agg["farm"].map(n_mon)) & (agg["nh"] == agg["n"])]
    if years is not None:
        agg = agg[agg["period"].between(*years)]
    Y = agg.pivot(index="period", columns="farm", values="y").dropna()
    H = agg.pivot(index="period", columns="farm", values="h").reindex(index=Y.index, columns=Y.columns)
    return Y, H


def book_rows(label: str, version: str, long: pd.DataFrame, aso: pd.Series, period_years: tuple,
              weight: str = "dollar", limit: bool = False) -> list[dict]:
    d = long.copy()
    if weight == "equal":
        d["y"], d["h"] = d["y"] / d["gap"], d["h"] / d["gap"]
    rows = []
    Yc, Hc = aggregate(d, "calendar", period_years)
    r = {"book": label, "version": version, "weight": weight, "period": "calendar year", "phase": "all"}
    r.update(book_stats(Yc.values, Hc.values, limit))
    rows.append(r)
    season_years = (period_years[0], period_years[1] - 1)
    Ys, Hs = aggregate(d, "season", season_years)
    ph = pd.Series(enso_phase(aso.reindex(Ys.index).values), index=Ys.index)
    for phase in ("all",) + PHASES:
        m = np.ones(len(Ys), bool) if phase == "all" else (ph == phase).values
        if m.sum() < 5:
            continue
        r = {"book": label, "version": version, "weight": weight, "period": "Jul-Jun season", "phase": phase}
        r.update(book_stats(Ys.values[m], Hs.values[m], limit))
        r["mean_target_vs_all"] = Ys.values[m].sum(1).mean() / Ys.values.sum(1).mean()
        r["mean_hedge_vs_all"] = Hs.values[m].sum(1).mean() / Hs.values.sum(1).mean()
        rows.append(r)
    return rows


def lender_check() -> dict:
    t0 = time.time()
    aso = load_aso_oni()
    farms = hb.load_farm_requests()
    farm_rows, longs = [], {"holdout": [], "loyo": []}
    for F in farms:
        r, gap = F["request"], F["protection"] / 6
        for mode in ("holdout", "loyo"):
            picked = pick_months(F, mode)
            row = {"farm_id": F["farm_id"], "station": r.station_key, "grid_id": r.grid_id, "version": mode,
                   "months": ", ".join(hb.MONTH_ABBR[m - 1] for m in picked), "gap_per_month_usd": gap}
            if picked:
                lg = fit_package(r.lat, r.lon, picked, r.coverage, gap, r.station_key, r.grid_id, mode)
                lg["farm"], lg["gap"] = F["farm_id"], gap
                longs[mode].append(lg)
                yrs = TEST if mode == "holdout" else hb.YEARS
                Y, H = aggregate(lg, "calendar", yrs)
                row["he_calendar"] = op.hedge_effectiveness(Y.values[:, 0], H.values[:, 0])
            farm_rows.append(row)
    farm_df = pd.DataFrame(farm_rows)
    book = []
    for mode, yrs in (("holdout", TEST), ("loyo", hb.YEARS)):
        lg = pd.concat(longs[mode], ignore_index=True)
        for w in ("dollar", "equal"):
            book += book_rows("11 sample farms", mode, lg, aso, yrs, w)
        # one farm per distinct grid (the 11 farms sit on 6 grids; same-grid pairs share all basis)
        first = farm_df[(farm_df["version"] == mode) & (farm_df["months"] != "")].drop_duplicates("grid_id")["farm_id"]
        book += book_rows("one farm per grid", mode, lg[lg["farm"].isin(first)], aso, yrs, "equal")
    print(f"  11-farm book done in {time.time() - t0:.0f} s", flush=True)

    # ---- same-station footprints
    rng = np.random.default_rng(SEED)
    st_tab = hb.station_table().set_index("station_key")
    grids = np.array(sorted(hb.covered_grids()))
    centers = np.array([grid_id_to_center(int(g)) for g in grids])
    curve_rows, foot_farm_rows = [], []
    gap = FOOT_PROTECTION / 6
    for st in FOOT_STATIONS:
        t1 = time.time()
        slat, slon = st_tab.loc[st, "lat"], st_tab.loc[st, "lon"]
        dist = np.array([haversine_miles(slat, slon, a, b) for a, b in centers])
        cand = grids[dist <= FOOT_RADIUS_MI]
        pick = rng.choice(cand, size=min(FOOT_N, len(cand)), replace=False)
        lg_by_mode = {"holdout": [], "loyo": []}
        for gid in pick:
            lat, lon = grid_id_to_center(int(gid))
            for mode in ("holdout", "loyo"):
                lg = fit_package(lat, lon, FOOT_MONTHS, FOOT_COVERAGE, gap, st, int(gid), mode)
                if lg is None:
                    continue
                lg["farm"], lg["gap"] = f"{st}_{gid}", gap
                lg_by_mode[mode].append(lg)
        for mode, yrs in (("holdout", TEST), ("loyo", hb.YEARS)):
            lg = pd.concat(lg_by_mode[mode], ignore_index=True)
            book += book_rows(f"{st} footprint ({FOOT_RADIUS_MI:.0f} mi)", mode, lg, aso, yrs, "equal", limit=True)
            Y, H = aggregate(lg, "calendar", yrs)
            for j, f in enumerate(Y.columns):
                foot_farm_rows.append({"station": st, "farm": f, "version": mode,
                                       "distance_mi": float(lg.loc[lg["farm"] == f, "distance_mi"].iloc[0]),
                                       "he_calendar": op.hedge_effectiveness(Y.values[:, j], H.values[:, j])})
            # book-size curve (sum of per-farm hedges)
            for n in BOOK_SIZES:
                if n > Y.shape[1]:
                    continue
                hs = [op.hedge_effectiveness(Y.values[:, s].sum(1), H.values[:, s].sum(1))
                      for s in (rng.choice(Y.shape[1], n, replace=False) for _ in range(N_SUBSETS if n > 1 else Y.shape[1]))]
                curve_rows.append({"station": st, "version": mode, "book_size": n, "he_median": np.median(hs),
                                   "he_p10": np.quantile(hs, 0.1), "he_p90": np.quantile(hs, 0.9)})
        # one hedge refit on the pooled target (LOYO; every farm uses the same station legs)
        lg = pd.concat(lg_by_mode["loyo"], ignore_index=True)
        farms_ok = lg["farm"].unique()
        req = CoverageRequest(slat, slon, [Window((m,), 0.25) for m in FOOT_MONTHS], FOOT_COVERAGE, gap * 4,
                              station_key=st, grid_id=int(pick[0]))
        p = hb.build_problem(req)
        ysum = lg.groupby(["year"])["y"].sum(min_count=len(farms_ok) * 4).reindex(p.years).to_numpy()
        ok = ~np.isnan(ysum) & ~np.isnan(p.X).any(axis=1)
        tr = op.model_tranches(p.q)
        scale = gap * 4 * len(farms_ok)
        fr = op.efficient_frontier(p.X[ok], ysum[ok], tr, n_points=13, scale=scale, q=p.q)
        hpool = op.loyo_payout(p.X[ok], ysum[ok], tr, op.knee_budget(fr, KNEE_SHARE), scale)
        book.append({"book": f"{st} footprint ({FOOT_RADIUS_MI:.0f} mi)", "version": "loyo, one hedge refit to book",
                     "weight": "equal", "period": "calendar year", "phase": "all", "n_farms": len(farms_ok),
                     "n_years": int(ok.sum()), "he_pooled": op.hedge_effectiveness(ysum[ok], hpool)})
        print(f"  footprint {st}: {len(farms_ok)} grids in {time.time() - t1:.0f} s", flush=True)

    farm_df = pd.concat([farm_df, pd.DataFrame(foot_farm_rows).rename(columns={"farm": "farm_id"})], ignore_index=True)
    books, curve = pd.DataFrame(book), pd.DataFrame(curve_rows)
    farm_df.to_csv(PROCESSED / "expansion_lens_lender_farms.csv", index=False)
    books.to_csv(PROCESSED / "expansion_lens_lender_books.csv", index=False)
    curve.to_csv(PROCESSED / "expansion_lens_lender_booksize.csv", index=False)
    return {"farms": farm_df, "books": books, "curve": curve}


# =============================================================================================
# 2. ENSO in Kalshi prices
# =============================================================================================
def series_station() -> dict:
    s = pd.read_csv(PROCESSED / "station_map.csv")
    s = s[~s["station_key"].isin(rx.DROP_STATIONS)]
    return dict(zip(s["series_ticker"], s["station_key"]))


def climatology_table(rain: pd.DataFrame, aso: pd.Series, keys: pd.DataFrame) -> pd.DataFrame:
    """keys: station_key, month, strike. Adds clim91, clim51, cond_<phase>, cond_strong_nino and n's."""
    out = []
    for (st, mo), g in keys.groupby(["station_key", "month"]):
        r = rain[(rain["station_key"] == st) & (rain["month"] == mo)]
        if len(r) < 40:
            continue
        ph = enso_phase(aso.reindex(season_year(r["year"], mo)).values)
        o = aso.reindex(season_year(r["year"], mo)).values
        ks = g["strike"].to_numpy(float)
        base = {"clim91": survival(r.loc[r["year"] >= 1991, "rain_in"], ks),
                "clim51": survival(r["rain_in"], ks),
                "cond_el_nino": survival(r.loc[ph == "El Nino", "rain_in"], ks),
                "cond_la_nina": survival(r.loc[ph == "La Nina", "rain_in"], ks),
                "cond_neutral": survival(r.loc[ph == "neutral", "rain_in"], ks),
                "cond_strong_nino": survival(r.loc[o >= STRONG, "rain_in"], ks)}
        d = g.copy()
        for k, v in base.items():
            d[k] = v
        d["n_el_nino"], d["n_la_nina"], d["n_strong"] = (ph == "El Nino").sum(), (ph == "La Nina").sum(), (o >= STRONG).sum()
        out.append(d)
    return pd.concat(out, ignore_index=True)


def tilt_regression(d: pd.DataFrame, cond: str, rain: pd.DataFrame, aso: pd.Series, phase_rule) -> dict:
    """mkt - clim51 = a + beta (cond - clim51) + c clim51; bootstrap seasons for the climatology terms."""
    def fit(clim, cnd):
        A = np.column_stack([np.ones(len(d)), cnd - clim, clim])
        coef, *_ = np.linalg.lstsq(A, d["mid"].to_numpy() - clim, rcond=None)
        return coef[1]
    beta = fit(d["clim51"].to_numpy(), d[cond].to_numpy())
    # bootstrap: resample seasons 1951-2024 jointly for all stations
    seasons = np.arange(1951, 2025)
    rng = np.random.default_rng(SEED)
    groups = []   # (row positions in d, strikes, rain by season aligned to `seasons`)
    for (st, mo), g in d.groupby(["station_key", "month"]):
        r = rain[(rain["station_key"] == st) & (rain["month"] == mo)]
        vec = r.set_index(season_year(r["year"], mo))["rain_in"].reindex(seasons).to_numpy(float)
        groups.append((g.index.to_numpy(), g["strike"].to_numpy(float), vec))
    aso_s = aso.reindex(seasons).to_numpy(float)
    betas = []
    for _ in range(N_BOOT):
        idx = rng.integers(0, len(seasons), len(seasons))
        inphase = phase_rule(aso_s[idx])
        clim, cnd = np.full(len(d), np.nan), np.full(len(d), np.nan)
        for pos, ks, vec in groups:
            x = vec[idx]
            ok = ~np.isnan(x)
            okc = ok & inphase
            if ok.any() and okc.any():
                clim[pos] = (x[ok][:, None] > ks[None, :] + 1e-9).mean(0)
                cnd[pos] = (x[okc][:, None] > ks[None, :] + 1e-9).mean(0)
        if np.isfinite(clim).all() and np.isfinite(cnd).all():
            betas.append(fit(clim, cnd))
    return {"beta": beta, "beta_lo": np.quantile(betas, 0.05), "beta_hi": np.quantile(betas, 0.95),
            "n_quotes": len(d), "n_stations": d["station_key"].nunique()}


def quote_mid(bid, ask) -> np.ndarray:
    bid, ask = np.asarray(bid, float), np.asarray(ask, float)
    ok = (bid > 0) & (ask < 1) & (ask - bid <= MAX_SPREAD + 1e-9) & (ask >= bid)
    return np.where(ok, (bid + ask) / 2, np.nan)


def history_snapshots(sst: dict) -> pd.DataFrame:
    """First usable quote of each Dec 2025-Mar 2026 market, within 3 days of the month's start."""
    c = pd.read_parquet(PROCESSED / "kalshi_rain_daily_candles.parquet")
    m = pd.read_parquet(PROCESSED / "kalshi_rain_markets.parquet")
    m = m[m["contract_month"].isin(["2025-12", "2026-01", "2026-02", "2026-03"])]
    c = c[c["ticker"].isin(m["ticker"])].copy()
    c["mid"] = quote_mid(c["yes_bid_close"], c["yes_ask_close"])
    c = c.dropna(subset=["mid"]).merge(m[["ticker", "series_ticker", "contract_month", "strike", "result"]],
                                       on=["ticker", "series_ticker"])
    c["date"] = pd.to_datetime(c["date"])
    start = pd.to_datetime(c["contract_month"] + "-01")
    c["day_of_month"] = (c["date"] - start).dt.days + 1     # <= 0: before the month starts
    c = c[c["day_of_month"] <= 3].sort_values("date").groupby("ticker").head(1)
    c["station_key"] = c["series_ticker"].map(sst)
    c["month"] = c["contract_month"].str[5:].astype(int)
    c["yes"] = (c["result"] == "yes").astype(float)
    return c[["ticker", "station_key", "contract_month", "month", "strike", "date", "day_of_month", "mid", "yes"]]


def enso_check() -> dict:
    aso = load_aso_oni()
    rain = rx.load_monthly_rain()
    sst = series_station()
    region = {s: r for r, ss in rx.REGIONS.items() for s in ss}
    out = {}

    # --- Nov 2026 book (Nov 2 snapshot) and last pre-month candles
    b = pd.read_csv(PROCESSED / "kalshi_rain_orderbook_summary_20261102.csv")
    b = b[b["contract_month"] == "2026-11"].copy()
    b["mid"] = quote_mid(b["best_yes_bid"], b["best_yes_ask"])
    b["station_key"], b["month"] = b["series_ticker"].map(sst), 11
    b = b.dropna(subset=["mid", "station_key"])
    nov = climatology_table(rain, aso, b[["station_key", "month", "strike", "mid", "spread", "ticker"]])
    nov["source"] = "book 2026-11-02"
    c = pd.read_parquet(PROCESSED / "kalshi_rain_daily_candles.parquet")
    c = c[c["ticker"].str.contains("-26NOV-") & (c["date"] <= "2026-10-31")].copy()
    c["mid"] = quote_mid(c["yes_bid_close"], c["yes_ask_close"])
    c = c.dropna(subset=["mid"]).sort_values("date").groupby("ticker").tail(1)
    c = c[c["date"] >= "2026-10-20"]
    c["strike"] = c["ticker"].str.rsplit("-", n=1).str[1].astype(float)
    c["station_key"], c["month"], c["spread"] = c["series_ticker"].map(sst), 11, c["yes_ask_close"] - c["yes_bid_close"]
    pre = climatology_table(rain, aso, c.dropna(subset=["station_key"])[["station_key", "month", "strike", "mid", "spread", "ticker"]])
    pre["source"] = "last candle 2026-10-20..31"
    q = pd.concat([nov, pre], ignore_index=True)
    q["region"] = q["station_key"].map(region).fillna("other")
    q.to_csv(PROCESSED / "expansion_lens_enso_nov2026_quotes.csv", index=False)

    st_rows = []
    for (src, st), g in q.groupby(["source", "station_key"]):
        g = g.sort_values("strike")
        if src.startswith("book") and len(g) < 5:
            continue
        ks = g["strike"].to_numpy()
        r = {"source": src, "station_key": st, "region": g["region"].iloc[0], "n_strikes": len(g),
             "strikes": ",".join(f"{k:g}" for k in ks), "median_spread": g["spread"].median(),
             "n_el_nino_seasons": int(g["n_el_nino"].iloc[0]), "n_strong_seasons": int(g["n_strong"].iloc[0])}
        for col in ("mid", "clim91", "clim51", "cond_el_nino", "cond_strong_nino"):
            r[f"mean_p_{col}"] = g[col].mean()
            if len(g) >= 5 and np.allclose(np.diff(ks), 1) and ks[0] == 1:
                r[f"implied_mean_in_{col}"] = implied_mean(ks, g[col].to_numpy())
        r["closer_to"] = "El Nino-conditional" if (np.abs(g["mid"] - g["cond_el_nino"]).mean()
                                                  < np.abs(g["mid"] - g["clim91"]).mean()) else "climatology (1991-2025)"
        st_rows.append(r)
    st = pd.DataFrame(st_rows)
    st.to_csv(PROCESSED / "expansion_lens_enso_nov2026_stations.csv", index=False)
    out["nov_stations"] = st

    reg_rows = []
    book = q[q["source"].str.startswith("book")]
    # dry side (the Companion's NO contracts sit at the low strikes): mean P(rain > K) by region,
    # with the other stations in the book as a control for any general market-vs-climatology gap
    low = book[book["strike"].isin([1.0, 2.0])].copy()
    low["group"] = np.where(low["region"].isin(["south_central", "southeast"]), low["region"], "other stations")
    ls = low.groupby(["group", "strike"]).agg(n_stations=("station_key", "nunique"), mid=("mid", "mean"),
                                              clim91=("clim91", "mean"), clim51=("clim51", "mean"),
                                              cond_el_nino=("cond_el_nino", "mean"),
                                              cond_strong_nino=("cond_strong_nino", "mean")).reset_index()
    ls["mid_minus_clim51"] = ls["mid"] - ls["clim51"]
    ls["el_nino_minus_clim51"] = ls["cond_el_nino"] - ls["clim51"]
    ls.to_csv(PROCESSED / "expansion_lens_enso_nov2026_lowstrikes.csv", index=False)
    out["low_strikes"] = ls
    for lab, sub in (("all Nov 2026 book stations", book),
                     ("south-central + southeast", book[book["region"].isin(["south_central", "southeast"])])):
        for cond, rule in (("cond_el_nino", lambda o: o >= EL_NINO), ("cond_strong_nino", lambda o: o >= STRONG)):
            r = {"sample": lab, "conditional": cond, "snapshot": "Nov 2026 book"}
            r.update(tilt_regression(sub.reset_index(drop=True), cond, rain, aso, rule))
            r["mean_mkt_minus_clim51"] = (sub["mid"] - sub["clim51"]).mean()
            r["mean_cond_minus_clim51"] = (sub[cond] - sub["clim51"]).mean()
            reg_rows.append(r)

    # --- winter 2025-26 history (ASO 2025 ONI -0.43: neutral by the rule; La Nina by SON)
    h = history_snapshots(sst).dropna(subset=["station_key"])
    hist = climatology_table(rain, aso, h)
    hist["region"] = hist["station_key"].map(region).fillna("other")
    hist.to_csv(PROCESSED / "expansion_lens_enso_history.csv", index=False)
    for cond, rule in (("cond_la_nina", lambda o: o <= LA_NINA), ("cond_neutral", lambda o: (o > LA_NINA) & (o < EL_NINO))):
        r = {"sample": "Dec 2025-Mar 2026, all stations with candles", "conditional": cond,
             "snapshot": "first quote, day <= 3"}
        r.update(tilt_regression(hist.reset_index(drop=True), cond, rain, aso, rule))
        r["mean_mkt_minus_clim51"] = (hist["mid"] - hist["clim51"]).mean()
        r["mean_cond_minus_clim51"] = (hist[cond] - hist["clim51"]).mean()
        reg_rows.append(r)
    hb_rows = []
    for lab, sub in (("all", hist), ("south-central + southeast", hist[hist["region"].isin(["south_central", "southeast"])])):
        r = {"sample": lab, "n_quotes": len(sub), "n_events": sub.groupby(["station_key", "month"]).ngroups,
             "stations": ",".join(sorted(sub["station_key"].unique())),
             "median_day_of_month": sub["day_of_month"].median()}
        for col in ("mid", "clim91", "clim51", "cond_la_nina", "cond_neutral"):
            r[f"brier_{col}"] = float(((sub[col] - sub["yes"]) ** 2).mean())
            r[f"mean_p_{col}"] = sub[col].mean()
        hb_rows.append(r)
    out["history"] = pd.DataFrame(hb_rows)
    out["history"].to_csv(PROCESSED / "expansion_lens_enso_history_summary.csv", index=False)
    out["regress"] = pd.DataFrame(reg_rows)
    out["regress"].to_csv(PROCESSED / "expansion_lens_enso_regression.csv", index=False)
    # how strong is the ENSO signal month by month? (netting-script put/call units, climatology = 1.00)
    u = rx.unit_payouts(rain)
    u = u[u["month"].isin([11, 12, 1, 2, 3])].copy()
    u["phase"] = enso_phase(aso.reindex(season_year(u["year"], u["month"])).values)
    u["region"] = u["station_key"].map(region)
    u = u[u["region"].isin(["south_central", "southeast"]) & u["year"].between(1951, 2025)]
    mt = u.groupby(["region", "month", "phase"])[["put", "call"]].mean().unstack("phase")
    mt.columns = [f"{a}_after_{b.replace(' ', '_')}" for a, b in mt.columns]
    out["month_signal"] = mt.reset_index()
    out["month_signal"].to_csv(PROCESSED / "expansion_lens_enso_month_signal.csv", index=False)
    cov = pd.read_parquet(PROCESSED / "kalshi_rain_daily_candles.parquet").groupby("series_ticker")["date"].agg(["min", "max"])
    out["coverage"] = cov
    return out


# =============================================================================================
# 3. solar
# =============================================================================================
def fetch_power(st: str, lat: float, lon: float, offline: bool) -> pd.DataFrame | None:
    cache = POWER_DIR / f"power_monthly_ALLSKY_SFC_SW_DWN_{st}_{POWER_YEARS[0]}_{POWER_YEARS[1]}.json"
    if offline and not cache.exists():
        return None
    params = {"parameters": "ALLSKY_SFC_SW_DWN", "community": "RE", "longitude": round(lon, 4),
              "latitude": round(lat, 4), "start": POWER_YEARS[0], "end": POWER_YEARS[1], "format": "JSON"}
    try:
        data = _cached_json(cache, lambda: _request_json("GET", POWER_URL, params=params))
    except Exception as e:  # noqa: BLE001
        print(f"  NASA POWER fetch failed for {st}: {e}")
        return None
    vals = data["properties"]["parameter"]["ALLSKY_SFC_SW_DWN"]
    rows = [{"station_key": st, "year": int(k[:4]), "month": int(k[4:]), "ghi": float(v)}
            for k, v in vals.items() if 1 <= int(k[4:]) <= 12 and float(v) > -900]
    return pd.DataFrame(rows)


def solar_check(offline: bool) -> dict | None:
    smap = pd.read_csv(PROCESSED / "station_map.csv").drop_duplicates("station_key").set_index("station_key")
    parts = [fetch_power(s, smap.loc[s, "lat"], smap.loc[s, "lon"], offline) for s in SOLAR_STATIONS]
    parts = [p for p in parts if p is not None]
    if not parts:
        print("  no NASA POWER data (offline with an empty cache): solar check skipped")
        return None
    sol = pd.concat(parts, ignore_index=True)
    rain = rx.load_monthly_rain()
    d = sol.merge(rain, on=["station_key", "year", "month"]).dropna()
    d["energy"] = d["ghi"] * pd.to_datetime(dict(year=d["year"], month=d["month"], day=1)).dt.days_in_month
    d["z_ghi"] = zscore_by(d, "ghi", ["station_key", "month"])
    d["z_rain"] = zscore_by(d, "rain_in", ["station_key", "month"])
    d["winter"] = d["month"].isin(WINTER)

    corr_rows = []
    for st in SOLAR_STATIONS + ["all five"]:
        g0 = d if st == "all five" else d[d["station_key"] == st]
        w = g0[g0["winter"]]
        for lab, g in (("Nov-Feb", w), ("all months", g0), ("Nov-Feb 1984-2000", w[w["year"] <= 2000]),
                       ("Nov-Feb 2001-2025", w[w["year"] >= 2001])):
            per_m = g.groupby(["station_key", "month"]).apply(lambda x: x["ghi"].corr(x["rain_in"]), include_groups=False)
            corr_rows.append({"station_key": st, "months": lab, "n": len(g),
                              "pearson_z": g["z_ghi"].corr(g["z_rain"]),
                              "spearman_z": g["z_ghi"].corr(g["z_rain"], method="spearman"),
                              "median_monthly_pearson": per_m.median()})
    corr = pd.DataFrame(corr_rows)

    rng = np.random.default_rng(SEED)
    hedge_rows, net_rows = [], []
    for (st, mo), g in d.groupby(["station_key", "month"]):
        g = g.sort_values("year")
        x, e, ghi = g["rain_in"].to_numpy(), g["energy"].to_numpy(), g["ghi"].to_numpy()
        short = e.mean() - e                              # solar owner's shortfall (MWh-proportional)
        ks = hb.listed_strikes(smap.loc[st, "series_ticker"])[mo]
        yes = np.column_stack([(x > k + 1e-9).astype(float) for k in ks])
        yes = yes[:, yes.std(0) > 0]
        kc, ec = rx.call_terms(x, False)
        call = rx.call_frac(x, kc, ec)
        kp, ep = rx.put_terms(x, None)
        put = rx.put_frac(x, kp, ep)
        kg, eg = rx.put_terms(ghi, rx.TEMP_FLOOR_Q)        # irradiance put: K = 30th pct, exhausts at 5th pct
        gput = rx.put_frac(ghi, kg, eg)
        hedge_rows.append({"station_key": st, "month": mo, "n_years": len(g),
                           "energy_cv": e.std() / e.mean(),
                           "corr_energy_rain": np.corrcoef(e, x)[0, 1],
                           "he_kalshi_yes_ladder_loyo": nnls_loyo_he(yes, short),
                           "he_rain_call_70_95_loyo": nnls_loyo_he(call[:, None], short),
                           "he_rain_call_70_95_insample": np.corrcoef(call, short)[0, 1] ** 2,
                           "he_irradiance_put_loyo": nnls_loyo_he(gput[:, None], short)})
        if put.mean() <= 0 or call.mean() <= 0 or gput.mean() <= 0:
            continue
        p, cr, cg = put / put.mean(), call / call.mean(), gput / gput.mean()
        caps = (1 / put.mean(), 1 / call.mean(), 1 / gput.mean())
        base = {"station_key": st, "month": mo, "n_years": len(g)}
        # (book, side payout, n_put, n_side, side cap, same index variable)
        specs = {"rancher put alone": (cr, 1, 0, caps[1], True),
                 "solar rain call alone": (cr, 0, 1, caps[1], True),
                 "solar irradiance put alone": (cg, 0, 1, caps[2], False),
                 "put + solar rain call": (cr, 1, 1, caps[1], True),
                 "put + solar irradiance put": (cg, 1, 1, caps[2], False)}
        for bk, (side, n_p, n_c, cap_s, same) in specs.items():
            mtr = rx.book_metrics(p, side, n_p, n_c, caps[0], cap_s, same, tail=False)
            prem = (1 + rx.LOAD) * (n_p + n_c)
            net_rows.append(dict(base, book=bk, payout_corr=np.corrcoef(p, side)[0, 1] if n_p and n_c else np.nan,
                                 capital95_per_prem=mtr["capital95_per_prem"], tvar95_per_prem=mtr["tvar95_per_prem"],
                                 worst_year_per_prem=(n_p * p + n_c * side - prem).max() / prem))
        # pure-diversification baseline: a second put whose years are shuffled (independent, same marginal)
        shuf = []
        for _ in range(N_SHUFFLE):
            q2 = rng.permutation(p)
            mtr = rx.book_metrics(p, q2, 1, 1, caps[0], caps[0], False, tail=False)
            shuf.append((mtr["capital95_per_prem"], mtr["tvar95_per_prem"], (p + q2 - 2 * (1 + rx.LOAD)).max() / (2 * (1 + rx.LOAD))))
        s = np.mean(shuf, axis=0)
        net_rows.append(dict(base, book="put + independent second put", payout_corr=0.0, capital95_per_prem=s[0],
                             tvar95_per_prem=s[1], worst_year_per_prem=s[2]))
    hedge = pd.DataFrame(hedge_rows)
    net = pd.DataFrame(net_rows)
    hedge["winter"] = hedge["month"].isin(WINTER)
    net["winter"] = net["month"].isin(WINTER)
    hs = hedge.groupby("winter")[[c for c in hedge.columns if c.startswith(("he_", "energy_cv", "corr_"))]].median()
    hs.index = hs.index.map({True: "Nov-Feb", False: "Mar-Oct"})
    hs.loc["all months"] = hedge[[c for c in hs.columns]].median()
    ns = pd.concat([net[net["winter"]].groupby("book")[["payout_corr", "capital95_per_prem", "tvar95_per_prem", "worst_year_per_prem"]]
                    .median().assign(months="Nov-Feb"),
                    net.groupby("book")[["payout_corr", "capital95_per_prem", "tvar95_per_prem", "worst_year_per_prem"]]
                    .median().assign(months="all months")]).reset_index()
    corr.to_csv(PROCESSED / "expansion_lens_solar_corr.csv", index=False)
    hedge.to_csv(PROCESSED / "expansion_lens_solar_hedge.csv", index=False)
    net.to_csv(PROCESSED / "expansion_lens_solar_netting_station_month.csv", index=False)
    ns.to_csv(PROCESSED / "expansion_lens_solar_netting.csv", index=False)
    return {"corr": corr, "hedge": hedge, "hedge_summary": hs.reset_index(names="months"), "netting": ns,
            "years": (int(d["year"].min()), int(d["year"].max()))}


# =============================================================================================
# figure
# =============================================================================================
def figure(lend: dict, enso: dict, solar: dict | None) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    colors = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
    ink, muted = "#0b0b0b", "#52514e"
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    ax = axes[0]
    cv = lend["curve"][lend["curve"]["version"] == "loyo"]
    for i, st in enumerate(FOOT_STATIONS):
        g = cv[cv["station"] == st]
        ax.plot(g["book_size"], g["he_median"], color=colors[i], lw=2, marker="o", ms=5, label=st)
        ax.fill_between(g["book_size"], g["he_p10"], g["he_p90"], color=colors[i], alpha=0.12, lw=0)
    ax.set_xscale("log")
    ax.set_xticks(BOOK_SIZES, [str(b) for b in BOOK_SIZES])
    ax.set_xlabel("farms in the book (same station, within 100 mi)", color=muted)
    ax.set_ylabel("pooled hedge effectiveness, LOYO", color=muted)
    ax.set_title("Lender book: Nov-Feb gap cover", loc="left", color=ink, fontsize=11)
    ax.legend(frameon=False, fontsize=9, title="station", title_fontsize=9)
    ax = axes[1]
    st = enso["nov_stations"]
    st = st[st["source"].str.startswith("book") & st["region"].isin(["south_central", "southeast"])].copy()
    st = st.dropna(subset=["implied_mean_in_mid"]).sort_values(["region", "station_key"])
    xs = np.arange(len(st))
    for j, (col, lab) in enumerate((("implied_mean_in_clim91", "climatology 1991-2025"),
                                    ("implied_mean_in_cond_el_nino", "El Nino years 1951-2025"),
                                    ("implied_mean_in_mid", "Kalshi mid, Nov 2 book"))):
        ax.bar(xs + (j - 1) * 0.27, st[col], width=0.25, color=colors[j], label=lab)
    ax.set_xticks(xs, st["station_key"])
    ax.set_ylabel("implied Nov rain, E[min(X, 7 in)] (in)", color=muted)
    ax.set_title("November 2026: market vs climatology", loc="left", color=ink, fontsize=11)
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    for a in axes:
        a.spines[["top", "right"]].set_visible(False)
        a.grid(axis="y", color="#e6e5e0", lw=0.6)
        a.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(FIGURES / "expansion_lenses.png", dpi=150)
    plt.close(fig)


# =============================================================================================
def main(argv=None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    offline = "--offline" in args
    t0 = time.time()
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 40)

    print("=== 1. Lender-portfolio HE ===", flush=True)
    lend = lender_check()
    f = lend["farms"]
    show = f[f["farm_id"].str.contains("_hay|_graze")]
    print(show.pivot(index="farm_id", columns="version", values=["months", "he_calendar"]).to_string())
    cols = ["book", "version", "weight", "period", "phase", "n_farms", "n_years", "he_farm_median", "he_pooled",
            "he_if_uncorrelated", "rho_y", "rho_e", "he_limit", "mean_target_vs_all", "mean_hedge_vs_all"]
    print(lend["books"][cols].round(3).to_string(index=False))
    print(lend["curve"].round(3).to_string(index=False))
    print(f"[{time.time() - t0:.0f} s]", flush=True)

    print("\n=== 2. ENSO in Kalshi prices ===", flush=True)
    enso = enso_check()
    print("candle coverage by series:\n", enso["coverage"].to_string())
    ns = enso["nov_stations"]
    print(ns[ns["region"].isin(["south_central", "southeast"])].round(3).to_string(index=False))
    print(enso["regress"].round(3).to_string(index=False))
    print(enso["history"].round(3).to_string(index=False))
    print(enso["month_signal"].round(2).to_string(index=False))
    print(enso["low_strikes"].round(3).to_string(index=False))
    print(f"[{time.time() - t0:.0f} s]", flush=True)

    print("\n=== 3. Solar as a wet-side counterparty ===", flush=True)
    solar = solar_check(offline)
    if solar:
        print(f"years {solar['years']}")
        print(solar["corr"].round(3).to_string(index=False))
        print(solar["hedge_summary"].round(3).to_string(index=False))
        print(solar["netting"].round(3).to_string(index=False))
    figure(lend, enso, solar)
    print(f"done in {time.time() - t0:.0f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
