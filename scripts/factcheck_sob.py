"""Independent re-derivation of the PRF headline numbers in docs/research/02 (fact-check, 2026-11-01).

This script is deliberately written separately from scripts/pull_rma_sob.py, so it is a second
check rather than a re-run. It downloads (or reuses) the RMA Summary of Business
"sobcov" files for 2015-2025 into RAW/rma_sob/. It sums the national crop book and the PRF Rainfall
Index rows (commodity 0088, plan 13), then prints the totals that doc 02 and the overview quote.

Run from the repo root:
    PYTHONPATH=src python -I scripts/factcheck_sob.py

Field positions (0-based) follow SOB_State_County_Crop_with_Coverage_Level_1989_Forward.pdf:
2 state_abbr, 5 commodity_code, 7 plan_code, 13 policies_earning_premium, 14 policies_indemnified,
17 quantity_type, 18 net_reported_quantity, 20 liability, 21 total_premium, 22 subsidy, 26 indemnity.
"""
from __future__ import annotations

import zipfile
from pathlib import Path

import pandas as pd

SOB_URL = "https://pubfs-rma.fpac.usda.gov/pub/Web_Data_Files/Summary_of_Business/state_county_crop/"
YEARS = range(2015, 2026)
PRF_COMMODITY, RI_PLAN = 88, 13
NUM_COLS = {13: "pol_ep", 14: "pol_ind", 18: "qty", 20: "liab", 21: "prem", 22: "sub", 26: "ind"}


def tidy(raw: pd.DataFrame) -> pd.DataFrame:
    """Turn the 28 unnamed string columns of a sobcov file into named numeric columns."""
    out = pd.DataFrame({
        "state": raw[2].astype(str).str.strip(),
        "commodity": pd.to_numeric(raw[5].astype(str).str.strip(), errors="coerce"),
        "plan": pd.to_numeric(raw[7].astype(str).str.strip(), errors="coerce"),
        "qty_type": raw[17].astype(str).str.strip(),
    })
    for idx, name in NUM_COLS.items():
        out[name] = pd.to_numeric(raw[idx].astype(str).str.strip().str.replace(",", ""), errors="coerce")
    return out


def year_totals(df: pd.DataFrame) -> dict:
    """National crop-book totals and PRF totals for one tidy sobcov year."""
    prf = df[(df.commodity == PRF_COMMODITY) & (df.plan == RI_PLAN)]
    acres = df[df.qty_type == "Acres"]
    return {
        "all_liab": df.liab.sum(), "all_prem": df.prem.sum(), "all_sub": df["sub"].sum(),
        "all_ind": df.ind.sum(), "all_acres": acres.qty.sum(),
        "prf_liab": prf.liab.sum(), "prf_prem": prf.prem.sum(), "prf_sub": prf["sub"].sum(),
        "prf_ind": prf.ind.sum(), "prf_acres": prf.qty.sum(),
        "prf_pol_ep": prf.pol_ep.sum(), "prf_pol_ind": prf.pol_ind.sum(),
    }


def pooled(prem: float, sub: float, ind: float) -> dict:
    """Loss ratio, return per producer-paid dollar, and subsidy share for pooled totals."""
    return {"loss_ratio": ind / prem, "return_per_producer_dollar": ind / (prem - sub),
            "subsidy_share": sub / prem}


def state_pooled(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Pool PRF premium, subsidy and indemnity by state across years; add loss ratio and return."""
    parts = [f[(f.commodity == PRF_COMMODITY) & (f.plan == RI_PLAN)].groupby("state")[["prem", "sub", "ind"]].sum()
             for f in frames]
    st = pd.concat(parts).groupby(level=0).sum()
    st["loss_ratio"] = st.ind / st.prem
    st["ret"] = st.ind / (st.prem - st["sub"])
    return st


def read_sobcov(path: Path) -> pd.DataFrame:
    with zipfile.ZipFile(path) as z:
        with z.open(z.namelist()[0]) as fh:
            return pd.read_csv(fh, sep="|", header=None, dtype=str, quoting=3)


def main() -> None:
    import requests

    from agri_hedge.config import RAW

    raw_dir = RAW / "rma_sob"
    raw_dir.mkdir(parents=True, exist_ok=True)
    frames, rows = [], []
    for y in YEARS:
        path = raw_dir / f"sobcov_{y}.zip"
        if not path.exists():
            r = requests.get(f"{SOB_URL}sobcov_{y}.zip", timeout=300)
            r.raise_for_status()
            path.write_bytes(r.content)
        df = tidy(read_sobcov(path))
        frames.append(df)
        rows.append({"year": y, **year_totals(df)})
    t = pd.DataFrame(rows).set_index("year")
    pd.set_option("display.width", 200)
    print((t[["all_liab", "all_prem", "all_sub", "all_ind"]] / 1e9).round(3))
    print((t[["prf_liab", "prf_prem", "prf_sub", "prf_ind"]] / 1e6).round(1))
    y25 = t.loc[2025]
    print(f"2025 subsidy share, crop book: {y25.all_sub / y25.all_prem:.4f}")
    print(f"2025 PRF: liability ${y25.prf_liab / 1e6:,.1f}M, acres {y25.prf_acres / 1e6:.2f}M, "
          f"policies {y25.prf_pol_ep:,.0f}, share of acres {y25.prf_acres / y25.all_acres:.4f}, "
          f"share of liability {y25.prf_liab / y25.all_liab:.4f}, indemnified {y25.prf_pol_ind / y25.prf_pol_ep:.4f}")
    p = pooled(t.prf_prem.sum(), t.prf_sub.sum(), t.prf_ind.sum())
    print(f"Pooled 2015-2025 PRF ($M): premium {t.prf_prem.sum() / 1e6:,.1f}, subsidy {t.prf_sub.sum() / 1e6:,.1f}, "
          f"indemnity {t.prf_ind.sum() / 1e6:,.1f}; {p}")
    print(f"Liability growth 2015-2025: x{t.prf_liab.loc[2025] / t.prf_liab.loc[2015]:.2f}")
    st = state_pooled(frames)
    print(f"States: {len(st)}; return > 1: {(st.ret > 1).sum()}; loss ratio > 1: {(st.loss_ratio > 1).sum()}")
    print(st.loc[["FL", "NM", "TX", "CO", "OK", "MO"], ["loss_ratio", "ret"]].round(2))


if __name__ == "__main__":
    main()
