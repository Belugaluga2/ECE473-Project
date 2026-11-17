"""Subsidy-capture trade: a rancher holds PRF and sells the matching Kalshi drought replica.

Inputs (all produced by earlier scripts, see docs/analysis/09_payout_comparison.md):
  data/processed/payout_comparison_farm_year.csv   PRF as paid, producer premium, out-of-sample H3 replica payout, fair value
  data/processed/payout_comparison_summary.csv     per-farm premiums, subsidy, Kalshi price scenarios, contract counts
  data/processed/kalshi_rain_orderbook_summary.csv 2026-10-29 books (resting NO bids = drought demand a seller can hit)
  data/processed/kalshi_rain_liquidity_by_series.csv
  data/processed/prf_summary_of_business_state.csv RMA summary of business by state and year

Outputs:
  data/processed/subsidy_capture_farm.csv   one row per farm
  data/processed/subsidy_capture_books.csv  one row per site: resting drought demand on 2026-10-29
  printed markdown tables for docs/research/26_prf_kalshi_subsidy_capture.md

Position convention. The rancher is long PRF (pays producer premium, receives the as-paid CPC indemnity)
and short the doc-08 H3 replica (receives the Kalshi premium, pays the replica's station-settled payout).
"beta" scales the short leg; beta = 1 sells the full replica, beta* is the minimum-variance size.
"""
from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data" / "processed"
HALF_SPREAD_NARROW = 0.0225  # half of the 4.5 cent median two-sided spread (doc 09 scenario a1)
HALF_SPREAD_WIDE = 0.0655    # half of the 13.1 cent spread (doc 09 scenario a2)
JUNK_BID = 0.05              # NO bids below this price are ignored as filler


def trade_stats(x: pd.DataFrame, beta: float, receipt_scale: float = 1.0) -> dict:
    """P&L of long PRF + beta x short replica. receipt_scale rescales the Kalshi premium received."""
    prf_net = x.prf_cpc_as_paid_usd - x.producer_premium_usd
    k_net = receipt_scale * x.kalshi_fair_value_usd - x.h3_cpc_loyo_usd
    arb = prf_net + beta * k_net
    return {
        "prf_mean": prf_net.mean(),
        "prf_sd": prf_net.std(),
        "prf_min": prf_net.min(),
        "prf_share_loss": (prf_net < 0).mean(),
        "arb_mean": arb.mean(),
        "arb_sd": arb.std(),
        "arb_min": arb.min(),
        "arb_share_loss": (arb < 0).mean(),
        "var_cut": 1 - arb.var() / prf_net.var(),
        "kalshi_leg_mean": (beta * k_net).mean(),
    }


def min_variance_beta(x: pd.DataFrame) -> float:
    prf_net = x.prf_cpc_as_paid_usd - x.producer_premium_usd
    c = np.cov(prf_net, x.h3_cpc_loyo_usd)
    return float(c[0, 1] / c[1, 1])


def farm_table() -> pd.DataFrame:
    fy = pd.read_csv(P / "payout_comparison_farm_year.csv")
    sm = pd.read_csv(P / "payout_comparison_summary.csv").set_index("farm_id")
    fy = fy[fy.prf_cpc_as_paid_usd.notna() & fy.h3_cpc_loyo_usd.notna()].copy()
    rows = []
    for farm, x in fy.groupby("farm_id"):
        s = sm.loc[farm]
        fair = s["kalshi_fair_value_1991_2025_usd"]
        contracts = s["contracts_per_dollar_fair_value"] * fair
        # what the seller receives per year under each price assumption, as a share of fair value
        receipt = {
            "fair": 1.0,
            "maker_narrow": (fair + contracts * HALF_SPREAD_NARROW) / fair,
            "maker_wide": (fair + contracts * HALF_SPREAD_WIDE) / fair,
            # doc 09 scenarios a1 and b1 share spread and fee; their gap is the calibration effect on the
            # drought (NO) side. Kalshi has priced NO below its true frequency, so a NO seller receives less.
            "calibrated": (fair - (s["kalshi_cost_a1_fair_taker_spread4.5c_usd"]
                                   - s["kalshi_cost_b1_calibrated_taker_spread4.5c_usd"])) / fair,
        }
        beta = min_variance_beta(x)
        recent = x[x.year >= 2015]
        r = {
            "farm_id": farm,
            "site": x.site.iloc[0],
            "years": f"{x.year.min()}-{x.year.max()}",
            "n_years": len(x),
            "policy_protection_usd": s["policy_protection_usd"],
            "total_premium_usd": s["prf_total_premium_usd"],
            "producer_premium_usd": s["prf_producer_premium_usd"],
            "subsidy_usd": s["prf_subsidy_usd"],
            "subsidy_share_of_protection": s["prf_subsidy_usd"] / s["policy_protection_usd"],
            "kalshi_fair_value_usd": fair,
            "contracts_per_year": contracts,
            "n_legs": s["n_legs_h3"],
            "corr_prf_replica": np.corrcoef(x.prf_cpc_as_paid_usd, x.h3_cpc_loyo_usd)[0, 1],
            "beta_min_var": beta,
            "receipt_calibrated_share": receipt["calibrated"],
            "receipt_maker_narrow_share": receipt["maker_narrow"],
            "receipt_maker_wide_share": receipt["maker_wide"],
            # years where the short leg loses while PRF does not cover the producer premium
            "years_kalshi_pays_prf_not": int(((x.h3_cpc_loyo_usd > x.kalshi_fair_value_usd)
                                              & (x.prf_cpc_as_paid_usd < x.producer_premium_usd)).sum()),
        }
        for tag, b in (("b1", 1.0), ("bstar", beta)):
            st = trade_stats(x, b)
            r.update({f"{tag}_{k}": v for k, v in st.items()})
        for tag, scale in (("calib", receipt["calibrated"]), ("maker_narrow", receipt["maker_narrow"]),
                           ("maker_wide", receipt["maker_wide"])):
            st = trade_stats(x, beta, scale)
            r[f"bstar_{tag}_arb_mean"] = st["arb_mean"]
        st15 = trade_stats(recent, beta)
        r.update({f"recent_{k}": v for k, v in st15.items()})
        r["recent_n_years"] = len(recent)
        rows.append(r)
    out = pd.DataFrame(rows)
    out["bstar_sharpe"] = out.bstar_arb_mean / out.bstar_arb_sd
    out["prf_sharpe"] = out.bstar_prf_mean / out.bstar_prf_sd
    out["worst_year_over_subsidy"] = -out.bstar_arb_min / out.subsidy_usd
    out["capture_share_of_subsidy"] = out.bstar_arb_mean / out.subsidy_usd
    return out


def book_table() -> pd.DataFrame:
    """Resting NO bids on 2026-10-29: the drought demand a seller could hit, by site and strike band."""
    ob = pd.read_csv(P / "kalshi_rain_orderbook_summary.csv")
    rows = []
    for (site, series, month), g in ob.groupby(["study_site", "series_ticker", "contract_month"], dropna=False):
        rec = {"site": site, "series": series, "contract_month": month, "strikes": len(g)}
        for band, mask in (("le3", g.strike <= 3), ("all", g.strike > -1)):
            payout = premium = payout_junk = 0.0
            for lst in g.loc[mask, "no_bids"].fillna("[]"):
                for price, size in ast.literal_eval(lst):
                    if price >= JUNK_BID:
                        payout += size
                        premium += price * size
                    else:
                        payout_junk += size
            rec[f"no_bid_contracts_{band}"] = payout
            rec[f"no_bid_premium_usd_{band}"] = premium
            rec[f"no_bid_contracts_{band}_below5c"] = payout_junk
        rows.append(rec)
    return pd.DataFrame(rows)


def national_table() -> tuple[pd.DataFrame, pd.DataFrame]:
    sb = pd.read_csv(P / "prf_summary_of_business_state.csv")
    yr = sb.groupby("year").agg(liability=("liability", "sum"), total_premium=("total_premium", "sum"),
                                subsidy=("subsidy", "sum"), producer_paid=("producer_paid_premium", "sum"),
                                indemnity=("indemnity", "sum"), acres=("net_reported_acres", "sum"),
                                policies=("policies_earning_premium", "sum"))
    yr["loss_ratio"] = yr.indemnity / yr.total_premium
    yr["producer_return"] = yr.indemnity / yr.producer_paid
    yr["net_transfer"] = yr.indemnity - yr.producer_paid
    last = sb[sb.year == sb.year.max()]
    st = last.groupby("state_abbr").agg(subsidy=("subsidy", "sum"), liability=("liability", "sum"),
                                       producer_paid=("producer_paid_premium", "sum"),
                                       indemnity=("indemnity", "sum")).sort_values("subsidy", ascending=False)
    return yr, st


def md(df: pd.DataFrame, cols: dict, fmt: dict | None = None) -> str:
    fmt = fmt or {}
    head = "| " + " | ".join(cols.values()) + " |\n|" + "---|" * len(cols) + "\n"
    body = ""
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            f = fmt.get(c, "{:,.0f}" if isinstance(v, (int, float, np.floating, np.integer)) else "{}")
            cells.append(f.format(v))
        body += "| " + " | ".join(cells) + " |\n"
    return head + body


def main() -> None:
    farms = farm_table()
    farms.to_csv(P / "subsidy_capture_farm.csv", index=False)
    books = book_table()
    books.to_csv(P / "subsidy_capture_books.csv", index=False)
    yr, st = national_table()

    pct = "{:.0%}"
    print("## Table A. The prize: subsidy per farm (2026 policy)\n")
    print(md(farms, {"farm_id": "Farm", "policy_protection_usd": "Protection $", "total_premium_usd": "Full premium $",
                     "producer_premium_usd": "Producer pays $", "subsidy_usd": "Subsidy $",
                     "subsidy_share_of_protection": "Subsidy / protection", "kalshi_fair_value_usd": "Replica fair value $",
                     "contracts_per_year": "Contracts / yr", "n_legs": "Legs"},
             {"subsidy_share_of_protection": "{:.1%}"}))

    print("\n## Table B. Long PRF alone vs long PRF + minimum-variance short replica, Kalshi sold at fair value, 1969-2025\n")
    print(md(farms, {"farm_id": "Farm", "n_years": "Years", "corr_prf_replica": "Corr", "beta_min_var": "beta*",
                     "bstar_prf_mean": "PRF mean $/yr", "bstar_prf_sd": "PRF sd $", "bstar_prf_share_loss": "PRF loss yrs",
                     "bstar_arb_mean": "Trade mean $/yr", "bstar_arb_sd": "Trade sd $", "bstar_var_cut": "Variance cut",
                     "bstar_arb_min": "Worst year $", "bstar_arb_share_loss": "Trade loss yrs",
                     "years_kalshi_pays_prf_not": "Yrs Kalshi pays, PRF not"},
             {"corr_prf_replica": "{:.2f}", "beta_min_var": "{:.2f}", "bstar_prf_share_loss": pct,
              "bstar_var_cut": pct, "bstar_arb_share_loss": pct}))

    print("\n## Table C. What the seller actually receives, and what is left of the subsidy (beta*, 1969-2025)\n")
    print(md(farms, {"farm_id": "Farm", "subsidy_usd": "Subsidy $", "bstar_arb_mean": "Mean at fair $",
                     "receipt_calibrated_share": "Receipt at Kalshi's historical prices / fair",
                     "bstar_calib_arb_mean": "Mean at historical prices $",
                     "receipt_maker_narrow_share": "Receipt as maker, 4.5c spread / fair",
                     "bstar_maker_narrow_arb_mean": "Mean as maker, 4.5c $",
                     "bstar_maker_wide_arb_mean": "Mean as maker, 13.1c $",
                     "bstar_sharpe": "Mean/sd", "worst_year_over_subsidy": "Worst year / subsidy"},
             {"receipt_calibrated_share": "{:.2f}", "receipt_maker_narrow_share": "{:.2f}",
              "bstar_sharpe": "{:.2f}", "worst_year_over_subsidy": "{:.1f}x"}))

    print("\n## Table D. Same trade, recent years only (2015-2025, beta*)\n")
    print(md(farms, {"farm_id": "Farm", "recent_n_years": "Years", "recent_prf_mean": "PRF mean $",
                     "recent_prf_sd": "PRF sd $", "recent_arb_mean": "Trade mean $", "recent_arb_sd": "Trade sd $",
                     "recent_var_cut": "Variance cut", "recent_arb_min": "Worst year $",
                     "recent_arb_share_loss": "Trade loss yrs"},
             {"recent_var_cut": pct, "recent_arb_share_loss": pct}))

    print("\n## Table E. Drought demand resting on the books, 2026-10-29 snapshot (NO bids at 5 cents or more)\n")
    b = books.sort_values("site", na_position="last")
    b = b[b.site.notna()]
    print(md(b, {"site": "Site", "series": "Series", "contract_month": "Month", "no_bid_contracts_le3": "NO-bid contracts, strikes <= 3 in",
                 "no_bid_premium_usd_le3": "Premium a seller would collect $", "no_bid_contracts_all": "NO-bid contracts, all strikes",
                 "no_bid_contracts_all_below5c": "Filler bids under 5c (contracts)"}))
    need = farms.set_index("farm_id").contracts_per_year
    print("\nFarm replica contracts per year (need buyers for all of these):")
    print(need.round(0).to_string())

    print("\n## Table F. PRF nationally, from RMA summary of business\n")
    yr2 = yr.reset_index()
    print(md(yr2, {"year": "Year", "policies": "Policies", "acres": "Acres", "liability": "Liability $",
                   "total_premium": "Total premium $", "subsidy": "Subsidy $", "producer_paid": "Producer paid $",
                   "indemnity": "Indemnity $", "loss_ratio": "Loss ratio", "producer_return": "Producer return per $1"},
             {"loss_ratio": "{:.2f}", "producer_return": "{:.2f}"}))
    print(f"\nSum of subsidy 2015-{yr.index.max()}: ${yr.subsidy.sum():,.0f}; net transfer to producers ${yr.net_transfer.sum():,.0f}")
    print(f"\nTop states by subsidy in {sb_year(yr)}:")
    print(st.head(8).round(0).to_string())

    liq = pd.read_csv(P / "kalshi_rain_liquidity_by_series.csv")
    print(f"\nKalshi monthly-rain series: {len(liq)}; total contracts traded to date across all series: {liq.total_volume.sum():,.0f}; "
          f"settled markets {liq.settled_markets.sum():,.0f}; median volume per settled market {liq.median_vol_per_settled_mkt.median():,.0f} contracts")
    print(f"Accountability level if every strike of every city were used by one member: 35 cities x 7 strikes x $25,000 = ${35*7*25000:,.0f} per month")


def sb_year(yr: pd.DataFrame) -> int:
    return int(yr.index.max())


if __name__ == "__main__":
    main()
