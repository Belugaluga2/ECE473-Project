"""Rain-to-loss model backtest (doc 13): modeled farm loss vs PRF and Kalshi hedge payouts.

Run from the repo root:   python scripts/run_loss_model.py            (add --offline to skip NASS)

Steps
1. Builds the rain-to-loss model (src/agri_hedge/loss_model.py) for the 11 farms in
   data/scenarios/farms.yaml, in four variants: timing = PRF allocation or NRCS growth curve, and
   value basis = rent (farms.yaml) or replacement hay (grazing farms only differ).
2. Runs it on the CPC "as paid" interval index of each farm's PRF grid
   (data/processed/cpc_interval_index.parquet, index_value_ours; doc 06b: reproduces the paid
   final indexes to 0.002 points), 1969-2025.
3. Backtest 2015-2025: compares modeled loss with the PRF indemnity as paid
   (prf_cpc_as_paid_usd) and the doc-09 Kalshi hedge payout (h3_cpc_train_usd: real Kalshi
   strikes, weights fit on 1951-2009, so out of sample) from
   data/processed/payout_comparison_farm_year.csv.
4. External check: model production change for the four hay farms vs detrended NASS statewide
   other-hay yields, 1975-2025 (NASS Quick Stats keyless CSV export, cached in the raw dir).
5. Corn illustration: the 2012 drought through the doc-03a row-crop model.

Outputs: data/processed/loss_model_{parameters,farm_year,coverage,hay_validation}.csv,
docs/figures/l1_loss_vs_payouts_2015_2025.png, and the block between the AUTO markers in
docs/analysis/13_rain_to_loss_model.md.
"""
from __future__ import annotations

import argparse
import sys
import time
import urllib.parse

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from agri_hedge import loss_model as lm  # noqa: E402
from agri_hedge.config import DOCS, FIGURES, PROCESSED, RAW  # noqa: E402
from agri_hedge.prf_intervals import INTERVAL_NAMES  # noqa: E402

BACKTEST = (2015, 2025)
HISTORY = (1969, 2025)          # CPC as-paid regime available on the farm grids (doc 09)
VALIDATION = (1975, 2025)       # same window as the doc-03b hay regressions
MATERIAL = 0.05                 # a "loss year": modeled loss > 5% of normal value (doc 09 convention)
VARIANTS = {                    # name -> (timing, value basis, curvature)
    "alloc_rent": ("allocation", "rent", True),
    "alloc_repl": ("allocation", "replacement", True),
    "growth_rent": ("growth", "rent", True),
    "growth_repl": ("growth", "replacement", True),
    "alloc_rent_linear": ("allocation", "rent", False),
}
CENTRAL = "alloc_rent"
INSTRUMENTS = {"prf": "prf_cpc_as_paid_usd", "kalshi": "h3_cpc_train_usd"}
HAY_STATE = {"DFW_hay": "TEXAS", "OKC_hay": "OKLAHOMA", "SGF_hay": "MISSOURI", "TPA_hay": "FLORIDA"}
HAY_ITEM = "HAY, (EXCL ALFALFA) - YIELD, MEASURED IN TONS / ACRE"
NASS_QS = "https://quickstats.nass.usda.gov"
DOC = DOCS / "analysis" / "13_rain_to_loss_model.md"
FIG = FIGURES / "l1_loss_vs_payouts_2015_2025.png"
AUTO_BEGIN = "<!-- BEGIN AUTO: loss model results (scripts/run_loss_model.py) -->"
AUTO_END = "<!-- END AUTO: loss model results -->"
C_BLUE, C_ORANGE, C_AQUA = "#2a78d6", "#eb6834", "#1baf7a"   # project palette (run_scenarios.py)
INK2, GRID = "#52514e", "#d9d8d4"


# ---------------------------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------------------------

def load_cpc(grids: list[int]) -> pd.DataFrame:
    c = pd.read_parquet(PROCESSED / "cpc_interval_index.parquet",
                        columns=["grid_id", "year", "interval_name", "index_value_ours"])
    c = c[c["grid_id"].isin(grids)].copy()
    c["interval_name"] = c["interval_name"].astype(str)
    return c


def cpc_wide(cpc: pd.DataFrame, grid_id: int) -> pd.DataFrame:
    g = cpc[(cpc["grid_id"] == int(grid_id)) & cpc["year"].between(*HISTORY)]
    return g.pivot_table(index="year", columns="interval_name", values="index_value_ours",
                         aggfunc="first").reindex(columns=INTERVAL_NAMES)


def nass_state_hay(state: str) -> pd.Series | None:
    """State other-hay yield (t/ac) by year from NASS Quick Stats (cached); None if unreachable."""
    path = RAW / "loss_model" / f"nass_hay_other_yield_{state}.csv"
    if not path.exists():
        import requests
        params = {"source_desc": "SURVEY", "agg_level_desc": "STATE", "short_desc": HAY_ITEM,
                  "reference_period_desc": "YEAR", "state_name": state}
        try:
            q = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
            hdr = {"User-Agent": "agri_hedge research (ECE473)"}
            uuid = requests.get(f"{NASS_QS}/uuid/encode?{q}", headers=hdr, timeout=60).text.strip().strip('"')
            txt = requests.get(f"{NASS_QS}/data/spreadsheet/{uuid}.csv", headers=hdr, timeout=120).text
        except Exception as exc:  # network optional
            print(f"  NASS unreachable for {state}: {exc}")
            return None
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(txt, encoding="utf-8")
        time.sleep(0.5)
    df = pd.read_csv(path, dtype=str)
    if "Value" not in df.columns:
        return None
    df = df[df["Period"] == "YEAR"]
    s = pd.to_numeric(df["Value"].str.replace(",", ""), errors="coerce")
    out = pd.Series(s.to_numpy(), index=pd.to_numeric(df["Year"]).astype(int)).groupby(level=0).first()
    return out.dropna().sort_index()


# ---------------------------------------------------------------------------------------------
# Model runs and metrics
# ---------------------------------------------------------------------------------------------

def run_models(farms, sens, cpc) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows, params = [], []
    for f in farms:
        gid = int(pd.read_csv(PROCESSED / "payout_comparison_farm_year.csv", usecols=["farm_id", "grid_id"])
                  .query("farm_id == @f['farm_id']")["grid_id"].iloc[0])
        wide = cpc_wide(cpc, gid)
        out = pd.DataFrame({"farm_id": f["farm_id"], "year": wide.index, "grid_id": gid})
        for name, (timing, basis, curv) in VARIANTS.items():
            m = lm.build_farm_model(f, sens, timing=timing, value_basis=basis, curvature=curv)
            t = m.table(wide)
            out[f"season_index_{timing}"] = t["season_index"].to_numpy()
            out[f"production_change_{name}"] = t["production_change"].to_numpy()
            out[f"loss_{name}_usd"] = t["loss_usd"].to_numpy()
            out[f"normal_value_{name}_usd"] = m.normal_value_usd
            params.append({"farm_id": m.farm_id, "variant": name, "timing": m.timing, "value_basis": basis,
                           "acres": m.acres, "value_per_acre_usd": round(m.value_per_acre, 2),
                           "normal_value_usd": round(m.normal_value_usd, 0), "elasticity": m.elasticity,
                           "curvature": round(m.curvature, 3),
                           "saturation_index": (round(100 * (1 - 1 / (2 * m.curvature)), 1)
                                                if m.curvature < 0 else np.nan),
                           "irrigated_share": m.irrigated_share,
                           "timing_weights": "; ".join(f"{k} {v:.2f}" for k, v in m.timing_weights.items()),
                           "elasticity_source": m.elasticity_source, "curvature_source": m.curvature_source})
        legacy = lm.forage_loss_proxy(float(f["expected_value_usd_per_acre"]), float(f["insured_acres"]),
                                      out["season_index_allocation"], params[-1]["elasticity"])
        out["loss_legacy_04b_proxy_usd"] = legacy.to_numpy()
        rows.append(out)
    return pd.concat(rows, ignore_index=True), pd.DataFrame(params)


def coverage_metrics(loss: pd.Series, pay: pd.Series, normal_value: float, cost: float) -> dict:
    ok = loss.notna() & pay.notna()
    L, P = loss[ok].to_numpy(float), pay[ok].to_numpy(float)
    Lp = np.clip(L, 0, None)
    loss_year = Lp > MATERIAL * normal_value
    resid = L - P
    return {
        "n_years": int(ok.sum()),
        "modeled_loss_sum_usd": Lp.sum(), "modeled_net_sum_usd": L.sum(),
        "payout_sum_usd": P.sum(),
        "payout_to_loss": P.sum() / Lp.sum() if Lp.sum() > 0 else np.nan,
        "capped_coverage": np.minimum(P, Lp).sum() / Lp.sum() if Lp.sum() > 0 else np.nan,
        "corr": float(np.corrcoef(L, P)[0, 1]) if L.std() > 0 and P.std() > 0 else np.nan,
        "n_loss_years": int(loss_year.sum()), "n_loss_years_unpaid": int((loss_year & (P <= 0)).sum()),
        "n_paid_no_loss": int(((P > 0) & (L <= 0)).sum()),
        "sd_loss_usd": L.std(ddof=0), "sd_residual_usd": resid.std(ddof=0),
        "sd_ratio": resid.std(ddof=0) / L.std(ddof=0) if L.std() > 0 else np.nan,
        "annual_cost_usd": cost,
        "mean_net_outcome_usd": float(np.mean(P - L) - cost),
        "mean_net_outcome_no_hedge_usd": float(-np.mean(L)),
    }


def backtest(fy: pd.DataFrame, pc: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    keep = ["farm_id", "year", "prf_cpc_as_paid_usd", "h3_cpc_train_usd", "producer_premium_usd",
            "kalshi_cost_central_usd"]
    m = fy.merge(pc[keep], on=["farm_id", "year"], how="left")
    rows = []
    bt = m[m["year"].between(*BACKTEST)]
    for fid, g in bt.groupby("farm_id", sort=False):
        for v in VARIANTS:
            for inst, col in INSTRUMENTS.items():
                cost = g["producer_premium_usd"].iloc[0] if inst == "prf" else g["kalshi_cost_central_usd"].iloc[0]
                rows.append({"farm_id": fid, "variant": v, "instrument": inst,
                             **coverage_metrics(g[f"loss_{v}_usd"], g[col], g[f"normal_value_{v}_usd"].iloc[0], cost)})
    return m, pd.DataFrame(rows)


def pooled(cov: pd.DataFrame, bt: pd.DataFrame) -> pd.DataFrame:
    """All-farm totals per variant x instrument (corr pooled over farm-years of farm-scaled values)."""
    out = []
    for (v, inst), g in cov.groupby(["variant", "instrument"], sort=False):
        col = INSTRUMENTS[inst]
        b = bt[bt["year"].between(*BACKTEST)].dropna(subset=[col])
        L, P = b[f"loss_{v}_usd"].clip(lower=0), b[col]
        out.append({"variant": v, "instrument": inst, "n_farm_years": int(g["n_years"].sum()),
                    "modeled_loss_sum_usd": g["modeled_loss_sum_usd"].sum(),
                    "payout_sum_usd": g["payout_sum_usd"].sum(),
                    "payout_to_loss": g["payout_sum_usd"].sum() / g["modeled_loss_sum_usd"].sum(),
                    "capped_coverage": np.minimum(P, L).sum() / L.sum(),
                    "median_farm_corr": g["corr"].median(),
                    "n_loss_years": int(g["n_loss_years"].sum()),
                    "n_loss_years_unpaid": int(g["n_loss_years_unpaid"].sum()),
                    "n_paid_no_loss": int(g["n_paid_no_loss"].sum()),
                    "farms_sd_reduced": int((g["sd_ratio"] < 1).sum())})
    return pd.DataFrame(out)


def hay_validation(fy: pd.DataFrame, offline: bool) -> pd.DataFrame:
    rows = []
    for fid, state in HAY_STATE.items():
        y = None if offline else nass_state_hay(state)
        if y is None or y.empty:
            continue
        y = y[(y.index >= VALIDATION[0]) & (y.index <= VALIDATION[1])]
        yrs = y.index.to_numpy(float)
        b = np.polyfit(yrs, y.to_numpy(float), 1)
        anom = y / np.polyval(b, yrs) - 1.0
        g = fy[fy["farm_id"] == fid].set_index("year")
        for v in ("alloc_rent", "alloc_rent_linear", "growth_rent"):
            pred = g[f"production_change_{v}"].reindex(anom.index)
            ok = pred.notna() & anom.notna()
            p, a = pred[ok].to_numpy(float), anom[ok].to_numpy(float)
            slope = float(np.polyfit(p, a, 1)[0]) if p.std() > 0 else np.nan
            dry = p < np.quantile(p, 0.2)
            rows.append({"farm_id": fid, "state": state, "variant": v, "years": f"{int(anom.index[ok].min())}-{int(anom.index[ok].max())}",
                         "n": int(ok.sum()), "corr": float(np.corrcoef(p, a)[0, 1]),
                         "slope_actual_on_model": slope, "rmse": float(np.sqrt(np.mean((a - p) ** 2))),
                         "mean_model_driest_quintile": float(p[dry].mean()),
                         "mean_actual_driest_quintile": float(a[dry].mean()),
                         "corr_2015_2025": float(np.corrcoef(p[anom.index[ok] >= 2015], a[anom.index[ok] >= 2015])[0, 1])})
    return pd.DataFrame(rows)


def corn_2012() -> pd.DataFrame:
    d = pd.read_csv(PROCESSED / "crop_yield_aux" / "r1_drought_2012.csv").set_index("region")
    rows = []
    for st in ("IL", "IN", "IA"):
        if st not in d.index:
            continue
        r = d.loc[st]
        for spec in ("rain-only 1980-2025", "update 1980-2025"):
            m = lm.load_rowcrop_model("corn", st, spec)
            rain = {"jun": r["jun_jul_2012_in"] - r["jul_2012_in"], "jul": r["jul_2012_in"],
                    "aug": m.normals["aug"] * r["aug_2012_pct_normal"] / 100.0}
            dy = m.yield_change_bu(rain)
            rows.append({"state": st, "spec": spec, "jun_in": round(rain["jun"], 2), "jul_in": r["jul_2012_in"],
                         "aug_in": round(rain["aug"], 2), "model_change_bu": dy,
                         "model_change_pct_of_trend": 100 * dy / r["corn_trend_1988_2011"],
                         "actual_pct_vs_trend": r["corn_pct_vs_trend"],
                         "loss_usd_1000ac_rainfed": m.loss_usd(rain, acres=1000),
                         "loss_usd_1000ac_state_irrigated_share": m.loss_usd(
                             rain, acres=1000, irrigated_share=lm.irrigated_share_for(lm._STATE_NAME[st], "corn")),
                         "irrigated_share": lm.irrigated_share_for(lm._STATE_NAME[st], "corn")})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------------------------
# Figure and doc
# ---------------------------------------------------------------------------------------------

def make_figure(bt: pd.DataFrame, path) -> None:
    farms = list(dict.fromkeys(bt["farm_id"]))
    yrs = np.arange(BACKTEST[0], BACKTEST[1] + 1)
    fig, axes = plt.subplots(6, 2, figsize=(10, 14), sharex=True, squeeze=False)
    w = 0.27
    for ax, fid in zip(axes.ravel(), farms):
        g = bt[(bt["farm_id"] == fid) & bt["year"].between(*BACKTEST)].set_index("year").reindex(yrs)
        ax.bar(yrs - w, g[f"loss_{CENTRAL}_usd"] / 1e3, w * 0.92, color=C_ORANGE, label="Modeled loss (+) / gain (-)")
        ax.bar(yrs, g["prf_cpc_as_paid_usd"] / 1e3, w * 0.92, color=C_BLUE, label="PRF paid (CPC as paid)")
        ax.bar(yrs + w, g["h3_cpc_train_usd"] / 1e3, w * 0.92, color=C_AQUA, label="Kalshi hedge (doc 09 H3)")
        ax.axhline(0, color=INK2, linewidth=0.6)
        ax.set_title(fid, fontsize=9, loc="left")
        ax.grid(axis="y", color=GRID, linewidth=0.6)
        ax.set_axisbelow(True)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        ax.tick_params(labelsize=7, colors=INK2, labelbottom=True)
        ax.set_ylabel("$ thousand", fontsize=7, color=INK2)
    axes.ravel()[-1].axis("off")
    h, lab = axes.ravel()[0].get_legend_handles_labels()
    axes.ravel()[-1].legend(h, lab, loc="center", frameon=False, fontsize=9)
    fig.suptitle("Modeled rain loss vs PRF and Kalshi payouts, 2015-2025 (allocation timing, rent value)",
                 fontsize=11, x=0.02, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.98))
    fig.savefig(path, dpi=130)
    plt.close(fig)


def _m(v, nd=0):
    if pd.isna(v):
        return "n/a"
    return f"${v:,.{nd}f}" if v >= 0 else f"-${-v:,.{nd}f}"


def _f(v, nd=2):
    return "n/a" if pd.isna(v) else f"{v:.{nd}f}"


def doc_block(params, cov, pool, val, corn, bt) -> str:
    L = [AUTO_BEGIN, "", "Generated by `python scripts/run_loss_model.py`. Do not edit by hand.", ""]
    L += ["### A. Model parameters per farm", "",
          "| Farm | Elasticity e | Curvature g | Saturates at season index | Normal value, rent | Normal value, replacement | Allocation weights | Growth weights |",
          "|---|---|---|---|---|---|---|---|"]
    p = params.set_index(["farm_id", "variant"])
    for fid in dict.fromkeys(params["farm_id"]):
        a, r, g = p.loc[(fid, "alloc_rent")], p.loc[(fid, "alloc_repl")], p.loc[(fid, "growth_rent")]
        sat = "none (linear)" if pd.isna(a["saturation_index"]) else f"{a['saturation_index']:.0f}"
        L.append(f"| {fid} | {a['elasticity']:.3f} | {a['curvature']:.2f} | {sat} | {_m(a['normal_value_usd'])} | "
                 f"{_m(r['normal_value_usd'])} | {a['timing_weights']} | {g['timing_weights']} |")
    L += ["", "Curvature sources: " + "; ".join(
        f"{fid}: {p.loc[(fid, 'alloc_rent')]['curvature_source']}" for fid in dict.fromkeys(params["farm_id"])), ""]

    L += ["### B. Backtest 2015-2025, all 11 farms pooled", "",
          "Modeled loss counts only years with a loss (positive part). Capped coverage = sum over years of "
          "min(payout, loss) / sum of losses. Loss year = modeled loss above 5% of normal value.", "",
          "| Loss variant | Instrument | Farm-years | Modeled loss | Payouts | Payout / loss | Capped coverage | Median farm corr | Loss years | ...unpaid | Paid with no loss | Farms with lower risk (sd ratio < 1) |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for _, r in pool.iterrows():
        L.append(f"| {r['variant']} | {r['instrument']} | {r['n_farm_years']} | {_m(r['modeled_loss_sum_usd'])} | "
                 f"{_m(r['payout_sum_usd'])} | {_f(r['payout_to_loss'])} | {r['capped_coverage']:.0%} | "
                 f"{_f(r['median_farm_corr'])} | {r['n_loss_years']} | {r['n_loss_years_unpaid']} | "
                 f"{r['n_paid_no_loss']} | {r['farms_sd_reduced']} of 11 |")

    for v in (CENTRAL, "growth_repl"):
        L += ["", f"### C. Per farm, 2015-2025, loss variant `{v}`", "",
              "| Farm | Modeled loss (sum) | Net loss incl. gains (sum) | PRF paid | PRF payout / loss | PRF capped coverage | PRF corr | Kalshi paid | Kalshi payout / loss | Kalshi capped coverage | Kalshi corr | Loss years (unpaid PRF / Kalshi) | sd ratio PRF / Kalshi |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        c = cov[cov["variant"] == v].set_index(["farm_id", "instrument"])
        for fid in dict.fromkeys(cov["farm_id"]):
            a, k = c.loc[(fid, "prf")], c.loc[(fid, "kalshi")]
            L.append(f"| {fid} | {_m(a['modeled_loss_sum_usd'])} | {_m(a['modeled_net_sum_usd'])} | {_m(a['payout_sum_usd'])} | "
                     f"{_f(a['payout_to_loss'])} | {a['capped_coverage']:.0%} | {_f(a['corr'])} | "
                     f"{_m(k['payout_sum_usd'])} ({k['n_years']} yr) | {_f(k['payout_to_loss'])} | {k['capped_coverage']:.0%} | {_f(k['corr'])} | "
                     f"{a['n_loss_years']} ({a['n_loss_years_unpaid']} / {k['n_loss_years_unpaid']}) | "
                     f"{_f(a['sd_ratio'])} / {_f(k['sd_ratio'])} |")

    L += ["", "### D. Modeled loss by year, central variant (`alloc_rent`), $ (negative = gain)", "",
          "| Farm | " + " | ".join(str(y) for y in range(BACKTEST[0], BACKTEST[1] + 1)) + " |",
          "|---|" + "---|" * (BACKTEST[1] - BACKTEST[0] + 1)]
    b = bt[bt["year"].between(*BACKTEST)]
    for fid, g in b.groupby("farm_id", sort=False):
        L.append(f"| {fid} | " + " | ".join(f"{v:,.0f}" for v in g[f"loss_{CENTRAL}_usd"]) + " |")

    L += ["", "### E. External check: model vs detrended NASS statewide other-hay yield", ""]
    if val.empty:
        L.append("NASS data were not available on this run (offline); check not performed.")
    else:
        L += ["Model input is the farm-grid CPC index; the yield is the statewide average, so a perfect model "
              "would still show an attenuated slope and correlation.", "",
              "| Farm (state) | Variant | Years | n | Corr | Slope (actual on model) | RMSE | Driest-quintile mean: model / actual | Corr 2015-2025 |",
              "|---|---|---|---|---|---|---|---|---|"]
        for _, r in val.iterrows():
            L.append(f"| {r['farm_id']} ({r['state'].title()}) | {r['variant']} | {r['years']} | {r['n']} | {r['corr']:.2f} | "
                     f"{r['slope_actual_on_model']:.2f} | {r['rmse']:.3f} | {r['mean_model_driest_quintile']:+.1%} / "
                     f"{r['mean_actual_driest_quintile']:+.1%} | {r['corr_2015_2025']:.2f} |")

    L += ["", "### F. Row-crop path: corn in the 2012 drought (doc 03a model, statewide rain)", "",
          "| State | Spec | Jun / Jul / Aug rain (in) | Model change (bu/ac) | Model % of 1988-2011 trend | Actual % vs trend | Loss on 1,000 rain-fed ac | Same, at state irrigated share |",
          "|---|---|---|---|---|---|---|---|"]
    for _, r in corn.iterrows():
        L.append(f"| {r['state']} | {r['spec']} | {r['jun_in']} / {r['jul_in']} / {r['aug_in']} | {r['model_change_bu']:.1f} | "
                 f"{r['model_change_pct_of_trend']:.1f}% | {r['actual_pct_vs_trend']:.1f}% | {_m(r['loss_usd_1000ac_rainfed'])} | "
                 f"{_m(r['loss_usd_1000ac_state_irrigated_share'])} ({r['irrigated_share']:.1%}) |")
    L += ["", AUTO_END]
    return "\n".join(L)


def write_doc_block(block: str) -> None:
    if not DOC.exists():
        print(f"  {DOC} missing; block printed only")
        print(block)
        return
    text = DOC.read_text(encoding="utf-8")
    i, j = text.find(AUTO_BEGIN), text.find(AUTO_END)
    if i < 0 or j < 0:
        raise SystemExit(f"AUTO markers not found in {DOC}")
    DOC.write_text(text[:i] + block + text[j + len(AUTO_END):], encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--offline", action="store_true", help="skip the NASS hay-yield check")
    args = ap.parse_args(argv)
    farms = lm.load_farms()
    sens = lm.load_sensitivity()
    pc = pd.read_csv(PROCESSED / "payout_comparison_farm_year.csv")
    cpc = load_cpc(sorted(pc["grid_id"].unique().tolist()))
    fy, params = run_models(farms, sens, cpc)
    bt, cov = backtest(fy, pc)
    pool = pooled(cov, bt)
    val = hay_validation(fy, args.offline)
    corn = corn_2012()

    params.to_csv(PROCESSED / "loss_model_parameters.csv", index=False)
    bt.round(4).to_csv(PROCESSED / "loss_model_farm_year.csv", index=False)
    cov.round(4).to_csv(PROCESSED / "loss_model_coverage.csv", index=False)
    if not val.empty:
        val.round(4).to_csv(PROCESSED / "loss_model_hay_validation.csv", index=False)
    make_figure(bt, FIG)
    write_doc_block(doc_block(params, cov, pool, val, corn, bt))
    pd.set_option("display.width", 200)
    print(pool.round(3).to_string(index=False))
    print(val.round(3).to_string(index=False) if not val.empty else "no NASS check")
    print(corn.round(2).to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
