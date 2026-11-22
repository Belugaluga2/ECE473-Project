"""Doc 26: the two-way weather market and what an intermediary would cost, earn and risk.

Doc 25's two-way idea: dryland ranchers buy the dry side of a station's monthly rain (a put),
outdoor venues and other wet-weather losers buy the wet side (a call), and someone sits in the
middle. This script prices that middle seat. For each book of contracts and each kind of
intermediary it computes:

  capital      money that must sit idle so every payout can be met (full collateral on Kalshi,
               or a 1-in-200-year loss reserve for an insurer), per $1 of premium
  capital cost what tying that money up costs a year: capital x (required return - interest
               earned on it) x the share of the year it is held
  expenses     fees and commissions as a share of premium (Kalshi taker fee, fronting fee, MGA
               and broker commission, premium tax, administration)
  gains        expected underwriting profit: premium minus expected payouts, minus costs
  losses       the payout years: 1-in-20, 1-in-100, 1-in-200 and the worst historical year,
               plus an out-of-sample run (priced on 1951-1995, paid 1996-2025)
  break-even   the price load the intermediary must charge to cover expenses and capital cost

Contracts follow scripts/run_expansion_netting.py: put = clip((K30 - x) / K30, 0, 1) on the
station's monthly rain, call = clip((x - K70) / (K95 - K70), 0, 1), each scaled so its expected
payout is one premium unit. A put and a call on the same station-month cannot both pay.

Books (pure premium normalized to 1; dollar tables scale it to BOOK_EL):
  ranch_sc       south-central Nov-Feb ranch puts (DFW, OKC, SAT, AUS, CLL, HOU), station
                 weights from doc 25's rancher demand (weather_demand_depth.csv)
  two_way_obs    the same plus wet calls at a modeled wet:dry premium ratio (doc 25: 0.012)
  two_way_bal    the same plus an equal premium of wet calls at every station-month
  national_put   puts at every long-record Kalshi station, all 12 months, equal weight
  national_bal   puts and equal-premium calls at every long-record station, all months

Annual loss distributions: empirical (one value per season year, 1951-2025) and simulated from
a Gaussian copula of the book's station-month rain values with empirical margins (N_SIM draws),
so the 1-in-200 quantile is not read off 75 years.

Intermediaries: see STRUCTURES. Cost inputs are constants below with their sources; doc 26's
numbers table lists them.

Outputs: data/processed/intermediary_*.csv and the AUTO block in
docs/analysis/26_intermediary_capital.md.

Usage: python scripts/run_intermediary_capital.py   (about 30 s; committed data only)
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_expansion_netting as rx  # noqa: E402

from agri_hedge.config import DOCS, PROCESSED  # noqa: E402

DOC = DOCS / "analysis" / "26_intermediary_capital.md"
BEGIN = "<!-- BEGIN AUTO: intermediary capital (scripts/run_intermediary_capital.py) -->"
END = "<!-- END AUTO: intermediary capital (scripts/run_intermediary_capital.py) -->"

SEED = 473
N_SIM = 100_000
SIM_CHUNK = 10_000
NU_GRID = (None, 30, 10, 5)        # copula: Gaussian (None) or Student t with these degrees of freedom
N_CALIB = 20_000                   # draws per candidate when matching the empirical annual sd
MIN_RECORD_YEARS = 70              # long-record stations only (as in doc 25's pooling study)
SPLIT = rx.SPLIT                   # out-of-sample: price 1951-1995, pay 1996-2025
BOOK_EL = 10_000_000               # dollar tables: $10M of expected payouts a year (doc 25 rancher demand ~$12M premium)
LOAD = rx.LOAD                     # doc 24/25 base-case price load

SC = rx.REGIONS["south_central"]
WINTER = (11, 12, 1, 2)
WET_DRY_OBS = 0.012                # modeled, mismatched-wealth-frame scenario; not observed flow

# ---- cost inputs (doc 26 numbers table gives sources) ----------------------------------------
KALSHI_ALL_IN_REFERENCE = 1.09     # doc 09 modeled cost ALREADY includes spread, taker fee and capital
TAKER_FEE = 0.07                   # Kalshi taker fee = 0.07 * C * P * (1 - P); makers pay 0
P_PAY = 0.24                       # typical hit rate of the ranch put (doc 25 p_mm_loss) -> fee share 0.07 * (1 - P)
KALSHI_APY = 0.035                 # Kalshi interest on cash and positions (help center, Oct 2026)
TBILL = 0.042                      # 3-month T-bill 4.21% (2026-11-02), earned on an insurer's capital
MAKER_COE = 0.12                   # required return on a small trading firm's equity (assumption, doc 25 lens)
INSURER_COC = 0.105                # reinsurer cost of equity, 2026 (Guy Carpenter)
SOLVENCY_Q = 0.995                 # Solvency II style one-year 1-in-200 capital standard
FRONTING = 0.07                    # fronting fee, share of gross premium (5-10% quoted; doc 26)
MGA_COMM = 0.20                    # MGA commission incl. producer pay (20.6% in the IRMI case; >20% TWFG MGA)
PREMIUM_TAX = 0.02                 # state premium tax (Texas 1.6%, typical 1.75-2.5%; doc 26)
ADMIN = 0.04                       # policy admin, actuarial, claims (parametric: no adjusting); assumption
BROKER_COMM = 0.05                 # introducing-broker style commission on a routed Kalshi hedge (assumption)

EXPENSE_GRID = (0.06, 0.15, 0.25, 0.33)
INSURER_EXPENSE = FRONTING + MGA_COMM + PREMIUM_TAX + ADMIN
TAKER_SHARE = TAKER_FEE * (1 - P_PAY)

STRUCTURES = {
    # key: (label, capital measure, required return, interest earned, expense share, hedger-paid fee share)
    "kalshi_today": ("Hedger trades Kalshi directly (modeled all-in reference)", None, None, None, 0.0, 0.0),
    "maker_direcnet": ("Our on-exchange maker, Kalshi collateral return", "collat_direcnet", MAKER_COE, KALSHI_APY, 0.0, TAKER_SHARE),
    "maker_plain": ("Our on-exchange maker, no collateral return", "collat_separate", MAKER_COE, KALSHI_APY, 0.0, TAKER_SHARE),
    "broker": ("Broker routes the hedger to Kalshi (no capital)", None, None, None, 0.0, BROKER_COMM),
    "insurer": ("Insurer/MGA book, fronted and reinsured", "var995", INSURER_COC, TBILL, INSURER_EXPENSE, 0.0),
    "insurer_lean": ("Lean insurer book (existing carrier or captive, no MGA layer)", "var995", INSURER_COC, TBILL,
                     PREMIUM_TAX + ADMIN, 0.0),
}

BOOK_LABELS = {
    "ranch_sc": "Ranch puts only, south-central Nov-Feb",
    "two_way_obs": "Two-way, modeled low-wet-flow scenario (wet:dry 1:80)",
    "two_way_bal": "Two-way balanced (wet = dry)",
    "national_put": "One-way puts, 34 stations, all months",
    "national_bal": "Two-way balanced, 34 stations, all months",
}


# ---------------------------------------------------------------------------------------------
# contracts
# ---------------------------------------------------------------------------------------------
def season_year(year, month, start: int):
    """Season label: months >= start belong to that year, earlier months to the previous one."""
    year, month = np.asarray(year), np.asarray(month)
    return np.where(month >= start, year, year - 1) if start > 1 else year


def unit_table(rain: pd.DataFrame, fit_years: tuple[int, int]) -> pd.DataFrame:
    """Per station-month-year put and call payouts in units of their pure premium on fit_years.

    cap_* is the largest possible payout of one unit (the payout when the fraction is 1)."""
    parts = []
    for (st, mo), g in rain.groupby(["station_key", "month"]):
        fit = g[g["year"].between(*fit_years)]
        if len(fit) < rx.MIN_YEARS:
            continue
        xf = fit["rain_in"].to_numpy(float)
        kp, ep = rx.put_terms(xf, None)
        kc, ec = rx.call_terms(xf, False)
        mp, mc = rx.put_frac(xf, kp, ep).mean(), rx.call_frac(xf, kc, ec).mean()
        if mp <= 0 or mc <= 0:
            continue
        x = g["rain_in"].to_numpy(float)
        parts.append(pd.DataFrame({
            "station_key": st, "month": mo, "year": g["year"].to_numpy(), "rain_in": x,
            "put": rx.put_frac(x, kp, ep) / mp, "call": rx.call_frac(x, kc, ec) / mc,
            "cap_put": 1 / mp, "cap_call": 1 / mc, "kp": kp, "ep": ep, "kc": kc, "ec": ec, "mp": mp, "mc": mc}))
    return pd.concat(parts, ignore_index=True)


def ranch_weights() -> pd.Series:
    d = pd.read_csv(PROCESSED / "weather_demand_depth.csv").set_index("station")
    w = d.loc[SC, "dry_contracts_standalone"].astype(float)
    return w / w.sum()


def book_specs(units: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Each book: rows (station_key, month, w_put, w_call) with total pure premium 1, and its season start.

    Only station-months that have both contracts in `units` are kept (15 of 408 national ones drop out)."""
    have = units[["station_key", "month"]].drop_duplicates()
    stations = sorted(have["station_key"].unique())
    rw = ranch_weights()
    sc = pd.DataFrame([(s, m, rw[s] / len(WINTER)) for s in SC for m in WINTER],
                      columns=["station_key", "month", "w_put"])
    nat = pd.DataFrame([(s, m) for s in stations for m in range(1, 13)], columns=["station_key", "month"])
    books = {
        "ranch_sc": sc.assign(w_call=0.0),
        "two_way_obs": sc.assign(w_call=sc["w_put"] * WET_DRY_OBS),
        "two_way_bal": sc.assign(w_call=sc["w_put"]),
        "national_put": nat.assign(w_put=1.0, w_call=0.0),
        "national_bal": nat.assign(w_put=1.0, w_call=1.0),
    }
    out = {}
    for k, b in books.items():
        b = b.merge(have, on=["station_key", "month"])
        tot = b["w_put"].sum() + b["w_call"].sum()
        b = b.assign(w_put=b["w_put"] / tot, w_call=b["w_call"] / tot)
        b.attrs["start"] = 11 if k in ("ranch_sc", "two_way_obs", "two_way_bal") else 1
        out[k] = b
    return out


# ---------------------------------------------------------------------------------------------
# book loss distributions
# ---------------------------------------------------------------------------------------------
def annual_payouts(units: pd.DataFrame, book: pd.DataFrame, years: tuple[int, int] | None = None) -> pd.Series:
    """Payout per season year (pure premium of the book = 1). Years missing >10% of the book's
    weight are dropped; the rest are rescaled to the full book."""
    u = units.merge(book, on=["station_key", "month"])
    u = u.assign(sy=season_year(u["year"], u["month"], book.attrs["start"]),
                 pay=u["w_put"] * u["put"] + u["w_call"] * u["call"], w=u["w_put"] + u["w_call"])
    g = u.groupby("sy").agg(pay=("pay", "sum"), w=("w", "sum"))
    g = g[g["w"] >= 0.9]
    if years is not None:
        g = g[(g.index >= years[0]) & (g.index <= years[1])]
    return g["pay"] / g["w"]


def kalshi_collateral(units: pd.DataFrame, book: pd.DataFrame, months: list[int]) -> dict:
    """Collateral-months per $1 of pure premium if every station-month is a Kalshi event.

    separate: each side posts its own maximum loss. direcnet: Kalshi's directional collateral
    return posts only the event's worst case, and the put and call cannot both pay."""
    caps = units.groupby(["station_key", "month"])[["cap_put", "cap_call"]].first().reset_index()
    b = book.merge(caps, on=["station_key", "month"])
    b = b.assign(sep=b["w_put"] * b["cap_put"] + b["w_call"] * b["cap_call"],
                 net=np.maximum(b["w_put"] * b["cap_put"], b["w_call"] * b["cap_call"]),
                 el=b["w_put"] + b["w_call"])
    m = b.groupby("month")[["sep", "net", "el"]].sum().loc[months]
    return {"collat_separate_max": b["sep"].sum(), "collat_direcnet_max": b["net"].sum(),
            "_month_separate": m["sep"].to_numpy(), "_month_direcnet": m["net"].to_numpy(),
            "_month_el": m["el"].to_numpy(), "n_events": len(b), "active_months": b["month"].nunique()}


def nearest_pd(c: np.ndarray) -> np.ndarray:
    """Clip negative eigenvalues (the national books have more station-months than years)."""
    vals, vecs = np.linalg.eigh(c)
    c = vecs @ np.diag(np.clip(vals, 1e-6, None)) @ vecs.T
    d = np.sqrt(np.diag(c))
    return c / np.outer(d, d)


def simulate_payouts(units: pd.DataFrame, book: pd.DataFrame, rng: np.random.Generator,
                     n: int = N_SIM, nu: int | None = None) -> tuple[np.ndarray, np.ndarray, list[int]]:
    """Book payouts from a Gaussian (nu None) or Student-t copula with empirical rain margins.

    Returns (annual payouts, payouts by calendar month in season order, that month order)."""
    u = units.merge(book, on=["station_key", "month"])
    u = u.assign(sy=season_year(u["year"], u["month"], book.attrs["start"]))
    u["var"] = u["station_key"] + "_" + u["month"].astype(str)
    x = u.pivot_table(index="sy", columns="var", values="rain_in")
    z = x.rank() / (x.count() + 1)
    z = pd.DataFrame(stats.norm.ppf(z), index=x.index, columns=x.columns)
    corr = nearest_pd(z.corr(min_periods=30).fillna(0).to_numpy())
    meta = u.groupby("var")[["w_put", "w_call", "kp", "ep", "kc", "ec", "mp", "mc"]].first().loc[x.columns]
    sorted_x = [np.sort(x[c].dropna().to_numpy()) for c in x.columns]
    chol = np.linalg.cholesky(corr)
    start_m = book.attrs["start"]
    months = sorted(meta.index.str.split("_").str[1].astype(int).unique(), key=lambda m: (m - start_m) % 12)
    col_month = [months.index(int(c.split("_")[1])) for c in meta.index]
    out = []
    for start in range(0, n, SIM_CHUNK):
        m = min(SIM_CHUNK, n - start)
        g = rng.standard_normal((m, len(x.columns))) @ chol.T
        uu = stats.norm.cdf(g) if nu is None else stats.t.cdf(g * np.sqrt(nu / rng.chisquare(nu, m))[:, None], nu)
        pay = np.zeros((m, len(months)))
        for j, (c, r) in enumerate(meta.iterrows()):
            xs = sorted_x[j]
            sim = np.quantile(xs, uu[:, j], method="inverted_cdf")
            pay[:, col_month[j]] += (r.w_put * rx.put_frac(sim, r.kp, r.ep) / r.mp
                                     + r.w_call * rx.call_frac(sim, r.kc, r.ec) / r.mc)
        out.append(pay)
    monthly = np.vstack(out)
    return monthly.sum(axis=1), monthly, months


def book_risk(units, book, rng) -> dict:
    emp = annual_payouts(units, book)
    # pick the copula whose annual sd is closest to the empirical one (tail dependence in ENSO winters)
    sds = {nu: simulate_payouts(units, book, rng, N_CALIB, nu)[0].std() for nu in NU_GRID}
    nu = min(sds, key=lambda k: abs(sds[k] - emp.std()))
    sim, monthly, months = simulate_payouts(units, book, rng, N_SIM, nu)
    r = {"n_years": len(emp), "copula": "Gaussian" if nu is None else f"t({nu})", "emp_mean": emp.mean(), "emp_q95": np.quantile(emp, 0.95),
         "emp_worst": emp.max(), "emp_worst_year": int(emp.idxmax()), "sim_mean": sim.mean(),
         "sim_q95": np.quantile(sim, 0.95), "sim_q99": np.quantile(sim, 0.99),
         "sim_q995": np.quantile(sim, SOLVENCY_Q), "sim_sd": sim.std(), "emp_sd": emp.std()}
    r.update(kalshi_collateral(units, book, months))
    r["_monthly"] = monthly                      # simulated payouts by season month (not saved)
    return r


# ---------------------------------------------------------------------------------------------
# intermediary economics
# ---------------------------------------------------------------------------------------------
def break_even_load(expense: float, carry: float, hold: float, capital_multiple: float) -> float:
    """Closed form for a reserve held against one loss quantile Q = capital_multiple * EL.

    lam * EL = expense * P + carry * hold * max(0, Q - P), with P = (1 + lam) * EL. Solved for lam."""
    lam = (expense + carry * hold * (capital_multiple - 1)) / (1 - expense + carry * hold)
    return lam if 1 + lam < capital_multiple else expense / (1 - expense)


def season_capital(risk: dict, key: str, load: float) -> float:
    """Capital per $1 of pure premium that the intermediary must have on hand at the start of the season.

    insurer: the 1-in-200 season loss net of premium (Solvency II style).
    Kalshi maker: to keep quoting all season it must, before each month k, cover the 1-in-200
    cumulative loss of the months already settled plus month k's full collateral (Kalshi posts the
    maximum loss up front). The requirement is the largest of these over the season."""
    cap = STRUCTURES[key][1]
    prem = 1 + load
    if cap == "var995":
        return max(0.0, risk["sim_q995"] - prem)
    side = cap.split("_")[1]
    coll, el = risk[f"_month_{side}"], risk["_month_el"]
    monthly = risk["_monthly"]
    cum = np.zeros(len(monthly))
    need = 0.0
    for k in range(len(el)):
        prior = max(0.0, float(np.quantile(cum, SOLVENCY_Q)))
        need = max(need, prior + max(0.0, coll[k] - prem * el[k]))
        cum = cum + monthly[:, k] - prem * el[k]
    return need


def capital_terms(key: str, risk: dict, load: float, coc: float | None = None,
                  expense: float | None = None) -> dict:
    """Capital, its cost and expected profit for one intermediary on one book at a given load."""
    _, cap, coc0, rate, expense0, _ = STRUCTURES[key]
    coc = coc0 if coc is None else coc
    expense = expense0 if expense is None else expense
    prem = 1 + load
    hold = min(12, risk["active_months"] + 1) / 12      # the season plus about a month to settle
    peak = season_capital(risk, key, load)
    carry = coc - rate
    years = peak * hold
    profit = load - expense * prem - carry * years    # economic profit: after paying investors their required return
    cash = load - expense * prem + rate * years       # expected accounting profit, interest on capital included
    return {"hold_years": hold, "carry": carry, "capital_peak_per_el": peak, "capital_years_per_el": years,
            "capital_cost_per_el": carry * years, "profit_per_el": profit,
            "return_on_peak": cash / peak if peak > 0 else np.nan}


def solve_break_even(key: str, risk: dict, coc: float | None = None, expense: float | None = None) -> float:
    """Load at which expected economic profit is zero."""
    from scipy.optimize import brentq
    f = lambda lam: capital_terms(key, risk, lam, coc, expense)["profit_per_el"]  # noqa: E731
    return brentq(f, -0.5, 10.0)


def structure_rows(book_key: str, risk: dict) -> list[dict]:
    rows = []
    for key, (label, cap, coc, rate, expense, hedger_fee) in STRUCTURES.items():
        r = {"book": book_key, "structure": key, "label": label, "expense_share": expense,
             "hedger_fee_share": hedger_fee}
        if cap is None:
            # Unlike a new maker's break-even price, this reference is already
            # buyer-all-in. Add only a separate broker commission, never a second taker fee.
            lam = KALSHI_ALL_IN_REFERENCE - 1
            r.update({"capital_per_prem": 0.0, "hold_years": 0.0, "carry": 0.0, "capital_cost_per_prem": 0.0,
                      "break_even_load": np.nan, "price_load": lam, "hedger_cost_per_1": (1 + lam) * (1 + hedger_fee)})
            rows.append(r)
            continue
        lam = solve_break_even(key, risk)
        t = capital_terms(key, risk, lam)
        r.update({"capital_per_prem": t["capital_peak_per_el"] / (1 + lam), "hold_years": t["hold_years"],
                  "carry": t["carry"], "capital_cost_per_prem": t["capital_cost_per_el"] / (1 + lam),
                  "break_even_load": lam, "price_load": lam, "hedger_cost_per_1": (1 + lam) * (1 + hedger_fee)})
        rows.append(r)
    return rows


def backtest(units_oos: pd.DataFrame, book: pd.DataFrame, load: float, expense: float,
             capital_cost: float) -> dict:
    """Annual P&L per $1 of priced pure premium, paid out 1996-2025 on 1951-1995 pricing."""
    pay = annual_payouts(units_oos, book, (SPLIT + 1, rx.SAMPLE[1]))
    pnl = (1 + load) * (1 - expense) - capital_cost - pay
    cum = pnl.cumsum()
    return {"oos_years": len(pay), "oos_loss_ratio": pay.mean(), "oos_mean_pnl": pnl.mean(),
            "oos_worst_pnl": pnl.min(), "oos_worst_year": int(pnl.idxmin()), "oos_loss_years": int((pnl < 0).sum()),
            "oos_cum_pnl": cum.iloc[-1], "oos_max_drawdown": float((cum.cummax().clip(lower=0) - cum).max())}


PNL_BOOKS = ("ranch_sc", "two_way_bal", "national_bal")
PNL_STRUCTURES = ("maker_direcnet", "insurer_lean", "insurer")
# These are assumed seller-price loads, not observed maker margins. The buyer's
# 1.09 all-in reference cannot be interpreted as a 9% maker revenue margin.
PNL_LOADS = (0.09, LOAD)


def pnl_rows(book_key: str, risk: dict, units_oos: pd.DataFrame, book: pd.DataFrame) -> list[dict]:
    rows = []
    for load in PNL_LOADS:
        for key in PNL_STRUCTURES:
            t = capital_terms(key, risk, load)
            r = {"book": book_key, "structure": key, "load": load, **t}
            r.update(backtest(units_oos, book, load, STRUCTURES[key][4], t["capital_cost_per_el"]))
            rows.append(r)
    return rows


def sensitivity(risks: dict) -> pd.DataFrame:
    rows = []
    for book in PNL_BOOKS:
        r = risks[book]
        for coc in (0.075, INSURER_COC, 0.15):
            for exp in EXPENSE_GRID:
                rows.append({"book": book, "who": "insurer", "required_return": coc, "expense_share": exp,
                             "break_even_load": solve_break_even("insurer", r, coc, exp)})
        for coe in (0.08, MAKER_COE, 0.20):
            for key in ("maker_direcnet", "maker_plain"):
                rows.append({"book": book, "who": key, "required_return": coe, "expense_share": 0.0,
                             "break_even_load": solve_break_even(key, r, coe, 0.0)})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------------------------
# doc block
# ---------------------------------------------------------------------------------------------
def fmt(x, d=2, pct=False):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "n/a"
    return f"{100 * x:.{max(d - 2, 0)}f}%" if pct else f"{x:,.{d}f}"


def money(x):
    return "n/a" if not np.isfinite(x) else (f"-${abs(x) / 1e6:,.2f}M" if x < 0 else f"${x / 1e6:,.2f}M")


def auto_block(risk: pd.DataFrame, econ: pd.DataFrame, bt: pd.DataFrame, sens: pd.DataFrame) -> str:
    L = [BEGIN, "",
         "**Table A. How much each book can lose, per $1 of expected payout (pure premium).** "
         "Empirical = 75 season years 1951-2025; 1-in-100 and 1-in-200 from the copula simulation. "
         "Kalshi collateral = total maximum loss posted across the book's monthly events (each held about one month).", "",
         "| Book | Station-months | Copula | Worst year (season) | 1-in-20 | 1-in-100 | 1-in-200 | Kalshi collateral, separate | Kalshi collateral, netted |",
         "|---|---|---|---|---|---|---|---|---|"]
    for _, r in risk.iterrows():
        L.append(f"| {BOOK_LABELS[r.book]} | {int(r.n_events)} | {r.copula} | {fmt(r.emp_worst)} ({int(r.emp_worst_year)}) | "
                 f"{fmt(r.sim_q95)} | {fmt(r.sim_q99)} | {fmt(r.sim_q995)} | {fmt(r.collat_separate_max)} | "
                 f"{fmt(r.collat_direcnet_max)} |")
    L += ["", "Simulation check (simulated vs empirical over the season years with data): " + "; ".join(
        f"{BOOK_LABELS[r.book]}: sd {fmt(r.sim_sd)} vs {fmt(r.emp_sd)}, 1-in-20 {fmt(r.sim_q95)} vs {fmt(r.emp_q95)} "
        f"({int(r.n_years)} seasons)" for _, r in risk.iterrows()) + ".", ""]

    L += ["**Table B. Break-even load: what each intermediary must charge above expected payouts.** "
          "Capital = money on hand for the season: an insurer's 1-in-200 season loss net of premium; for a Kalshi maker, "
          "the 1-in-200 loss on months already settled plus the current month's full collateral, at its largest. "
          "Capital cost = capital x (required return - interest earned) x years held. Break-even load covers expenses plus "
          "capital cost. The hedger's all-in cost adds fees the hedger pays (Kalshi taker fee, broker commission). "
          "Direct-Kalshi uses doc 09's modeled 1.09 all-in buyer reference, with no additional taker fee; "
          "the broker adds only its assumed commission. New maker rows add a taker fee once to the seller price.", "",
          "| Book | Intermediary | Capital per $1 premium, at that price | Held (yrs) | Capital cost, % premium | Expenses, % premium | Break-even load | Hedger pays per $1 expected payout |",
          "|---|---|---|---|---|---|---|---|"]
    for _, r in econ.iterrows():
        if r.book not in PNL_BOOKS or (r.book == "ranch_sc" and r.structure == "maker_plain"):
            continue                       # with no calls, collateral return changes nothing
        cap = "0 (seller on Kalshi posts it)" if r.structure in ("kalshi_today", "broker") else fmt(r.capital_per_prem)
        be = "n/a (market price)" if not np.isfinite(r.break_even_load) else fmt(r.break_even_load, 3, True)
        L.append(f"| {BOOK_LABELS[r.book]} | {r.label} | {cap} | {fmt(r.hold_years)} | "
                 f"{fmt(r.capital_cost_per_prem, 3, True)} | {fmt(r.expense_share, 3, True)} | {be} | "
                 f"{fmt(r.hedger_cost_per_1)} |")
    L.append("")

    L += [f"**Table C. Gains and losses on a ${BOOK_EL / 1e6:.0f}M book (expected payouts a year).** "
          "Loads 9% and 20% are assumed seller-price scenarios; the 1.09 buyer-all-in reference is not a maker margin. "
          "Peak capital = most money tied up at once. Expected profit is after expenses and after paying for capital "
          "(required return minus interest). Return on peak capital = expected profit before the capital charge, plus interest, "
          "over peak capital. Out-of-sample (OOS) columns price on 1951-1995 and pay 1996-2025 (30 seasons), "
          "charging expenses and capital cost every year.", "",
          "| Book | Intermediary | Load | Peak capital | Expected profit / yr | Return on peak capital | OOS loss ratio | OOS mean P&L / yr | OOS worst year (season) | OOS losing years | OOS 30-yr total | OOS max drawdown |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for _, r in bt.iterrows():
        L.append(f"| {BOOK_LABELS[r.book]} | {STRUCTURES[r.structure][0]} | {fmt(r.load, 2, True)} | "
                 f"{money(r.capital_peak_per_el * BOOK_EL)} | "
                 f"{money(r.profit_per_el * BOOK_EL)} | {fmt(r.return_on_peak, 3, True)} | {fmt(r.oos_loss_ratio)} | "
                 f"{money(r.oos_mean_pnl * BOOK_EL)} | {money(r.oos_worst_pnl * BOOK_EL)} ({int(r.oos_worst_year)}) | "
                 f"{int(r.oos_loss_years)} of {int(r.oos_years)} | {money(r.oos_cum_pnl * BOOK_EL)} | "
                 f"{money(r.oos_max_drawdown * BOOK_EL)} |")
    L.append("")

    L += ["**Table D. Break-even load under other cost assumptions.** Insurer rows vary the required return on capital "
          "and the expense share (6% = lean, 33% = fronted MGA). Maker rows have no expenses; only the required return varies.", "",
          "| Book | Who | Required return | Expenses 6% | 15% | 25% | 33% |", "|---|---|---|---|---|---|---|"]
    for (book, who, rr), g in sens.groupby(["book", "who", "required_return"], sort=False):
        if book == "ranch_sc" and who == "maker_plain":
            continue
        vals = g.set_index("expense_share")["break_even_load"]
        if who == "insurer":
            cells = " | ".join(fmt(vals[e], 3, True) for e in EXPENSE_GRID)
        else:
            cells = f"{fmt(vals[0.0], 3, True)} (no expenses) | | | "
        who = {"insurer": "insurer", "maker_direcnet": "maker, collateral return", "maker_plain": "maker, no collateral return"}[who]
        L.append(f"| {BOOK_LABELS[book]} | {who} | {fmt(rr, 2, True)} | {cells} |")
    L += ["", END]
    return "\n".join(L)


def write_doc(block: str) -> None:
    if not DOC.exists():
        print(f"{DOC} missing; AUTO block not written")
        return
    text = DOC.read_text()
    if BEGIN not in text or END not in text:
        print("doc has no AUTO markers; skipped")
        return
    pre, rest = text.split(BEGIN, 1)
    _, post = rest.split(END, 1)
    DOC.write_text(pre + block + post)
    print("updated doc 26 AUTO block")


def main(argv=None) -> int:
    t0 = time.time()
    rng = np.random.default_rng(SEED)
    rain = rx.load_monthly_rain()
    yrs = rain.groupby("station_key")["year"].nunique()
    rain = rain[rain["station_key"].isin(yrs[yrs >= MIN_RECORD_YEARS].index)]
    units = unit_table(rain, rx.SAMPLE)
    units_oos = unit_table(rain, (rx.SAMPLE[0], SPLIT))
    books = book_specs(units)

    risks, econ, bts = {}, [], []
    for key, book in books.items():
        r = book_risk(units, book, rng)
        risks[key] = r
        econ += structure_rows(key, r)
        if key in PNL_BOOKS:
            bts += pnl_rows(key, r, units_oos, book)
        print(f"{key}: {r['n_events']} events, worst {r['emp_worst']:.2f} ({r['emp_worst_year']}), "
              f"q95 sim {r['sim_q95']:.2f} emp {r['emp_q95']:.2f}, q995 {r['sim_q995']:.2f}, "
              f"collateral sep {r['collat_separate_max']:.2f} net {r['collat_direcnet_max']:.2f}")

    risk = pd.DataFrame([{"book": k, **{a: b for a, b in v.items() if not a.startswith("_")}}
                         for k, v in risks.items()])
    econ = pd.DataFrame(econ)
    bt = pd.DataFrame(bts)
    sens = sensitivity(risks)
    risk.to_csv(PROCESSED / "intermediary_book_risk.csv", index=False)
    econ.to_csv(PROCESSED / "intermediary_economics.csv", index=False)
    bt.to_csv(PROCESSED / "intermediary_backtest.csv", index=False)
    sens.to_csv(PROCESSED / "intermediary_sensitivity.csv", index=False)

    pd.set_option("display.width", 250)
    print(econ[["book", "structure", "capital_per_prem", "hold_years", "capital_cost_per_prem", "expense_share",
                "break_even_load", "hedger_cost_per_1"]].round(3).to_string(index=False))
    print(bt[["book", "structure", "load", "capital_peak_per_el", "capital_years_per_el", "profit_per_el",
              "return_on_peak", "oos_loss_ratio", "oos_mean_pnl", "oos_worst_pnl", "oos_worst_year",
              "oos_loss_years", "oos_cum_pnl", "oos_max_drawdown"]].round(3).to_string(index=False))
    write_doc(auto_block(risk, econ, bt, sens))
    print(f"done in {time.time() - t0:.0f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
