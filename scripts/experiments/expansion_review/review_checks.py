"""Read-only review checks of run_expansion_netting.py. Writes nothing into the repo."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts"))
import run_expansion_netting as rx  # noqa: E402

SCR = Path(__file__).parent
rng = np.random.default_rng(1)
LOAD = rx.LOAD
rain = rx.load_monthly_rain()
stations = rx.station_list()


def pf(x, k, e):
    return rx.put_frac(x, k, e)


def cf(x, k, e):
    return rx.call_frac(x, k, e)


# ------------------------------------------------------------------ 1. OOS pooled book
def oos_units(df, split=rx.SPLIT, var="rain_in", floor_q=None):
    rows = []
    for (st, mo), g in df.groupby(["station_key", "month"]):
        g = g.dropna(subset=[var])
        if len(g) < rx.MIN_YEARS:
            continue
        tr, te = g[g.year <= split], g[g.year > split]
        if len(tr) < 30 or len(te) < 20:
            continue
        x = tr[var].to_numpy(float)
        kp, ep = rx.put_terms(x, floor_q)
        kc, ec = rx.call_terms(x, False)
        mp, mc = pf(x, kp, ep).mean(), cf(x, kc, ec).mean()
        if mp <= 0 or mc <= 0:
            continue
        rows.append(pd.DataFrame({"station_key": st, "month": mo, "year": te.year.to_numpy(),
                                  "put": pf(te[var], kp, ep) / mp, "call": cf(te[var], kc, ec) / mc}))
    return pd.concat(rows, ignore_index=True)


print("=== 1. Out-of-sample national pools (price 1951-1995, realize 1996-2025) ===")
u = oos_units(rain)
keep = rain.groupby("station_key").year.nunique()
u = u[u.station_key.isin(keep[keep >= 70].index)]
# per station-month loss ratio
sm = u.groupby(["station_key", "month"])[["put", "call"]].mean()
print("median of station-month loss ratios: put %.3f call %.3f" % (sm.put.median(), sm.call.median()))
print("pooled (ratio of sums) loss ratios:  put %.3f call %.3f pair %.3f" % (u.put.mean(), u.call.mean(), (u.put.mean() + u.call.mean()) / 2))
ann = u.groupby("year").agg(put=("put", "mean"), call=("call", "mean"))
ann["pair"] = (ann.put + ann.call) / 2
for side in ["put", "call", "pair"]:
    loss = ann[side] - (1 + LOAD)
    q95 = np.quantile(loss, 0.95)
    print(f"national annual {side:4s} OOS: mean loss/prem {loss.mean()/(1+LOAD):+.3f}  capital95/prem {max(0,q95)/(1+LOAD):.3f}  worst {loss.max()/(1+LOAD):+.3f}  P(loss) {(loss>0).mean():.2f}")
mon = u.groupby(["year", "month"]).agg(put=("put", "mean"), call=("call", "mean"))
mon["pair"] = (mon.put + mon.call) / 2
for side in ["put", "pair"]:
    caps = []
    for mo, g in mon.groupby(level="month"):
        loss = g[side] - (1 + LOAD)
        caps.append(max(0, np.quantile(loss, 0.95)) / (1 + LOAD))
    print(f"national monthly {side} OOS capital95/prem median of months {np.median(caps):.3f}")

# ------------------------------------------------------------------ 2. placebo null for OOS drift
print("\n=== 2. Placebo: shuffle years (same permutation for all stations), split 45/30 ===")
years = np.arange(1951, 2026)
wide = rain[rain.year.between(1951, 2025)]
null_call, null_put, null_pool_call = [], [], []
for i in range(0 if "part2" in sys.argv else 300):
    perm = dict(zip(years, rng.permutation(years)))
    w = wide.copy()
    w["year"] = w["year"].map(perm)
    uu = oos_units(w)
    uu = uu[uu.station_key.isin(keep[keep >= 70].index)]
    s2 = uu.groupby(["station_key", "month"])[["put", "call"]].mean()
    null_call.append(s2.call.median()); null_put.append(s2.put.median()); null_pool_call.append(uu.call.mean())
null_call, null_put, null_pool_call = map(np.array, (null_call, null_put, null_pool_call))
if len(null_call):
    print("null median call ratio: mean %.3f, 2.5-97.5%% [%.3f, %.3f]; actual %.3f; p(one-sided) %.3f" % (
        null_call.mean(), *np.quantile(null_call, [0.025, 0.975]), sm.call.median(), (null_call >= sm.call.median()).mean()))
    print("null median put ratio:  mean %.3f, 2.5-97.5%% [%.3f, %.3f]; actual %.3f" % (
        null_put.mean(), *np.quantile(null_put, [0.025, 0.975]), sm.put.median()))
    print("null pooled call ratio: 2.5-97.5%% [%.3f, %.3f]; actual %.3f; p %.3f" % (
        *np.quantile(null_pool_call, [0.025, 0.975]), u.call.mean(), (null_pool_call >= u.call.mean()).mean()))

# ------------------------------------------------------------------ 3. walk-forward pricing methods
def walk_forward(df, var, floor_q=None, first=1996, last=2025):
    """For each test year t, set strikes on all prior years and price with several methods."""
    out = []
    for (st, mo), g in df.groupby(["station_key", "month"]):
        g = g.dropna(subset=[var]).sort_values("year")
        if len(g) < 60:
            continue
        for t in range(first, last + 1):
            hist, now = g[g.year < t], g[g.year == t]
            if len(now) == 0 or len(hist) < 40:
                continue
            x, yr = hist[var].to_numpy(float), hist.year.to_numpy(float)
            kp, ep = rx.put_terms(x, floor_q)
            kc, ec = rx.call_terms(x, False)
            xt = float(now[var].iloc[0])
            real_p, real_c = float(pf([xt], kp, ep)[0]), float(cf([xt], kc, ec)[0])
            prem = {}
            for name, sel in (("all", slice(None)), ("last30", slice(-30, None)), ("last15", slice(-15, None))):
                prem[name] = (pf(x[sel], kp, ep).mean(), cf(x[sel], kc, ec).mean())
            # linear detrend of the index, re-centred on year t (burn on detrended data)
            b = np.polyfit(yr, x, 1)
            xd = x - np.polyval(b, yr) + np.polyval(b, t)
            if floor_q is None:
                xd = np.clip(xd, 0, None)
            prem["detrend"] = (pf(xd, kp, ep).mean(), cf(xd, kc, ec).mean())
            # trend in the payout itself (burn-trend), floored at 25% of the mean
            for side, f in (("p", pf(x, kp, ep)), ("c", cf(x, kc, ec))):
                bb = np.polyfit(yr, f, 1)
                prem.setdefault("payout_trend", [None, None])
                prem["payout_trend"][0 if side == "p" else 1] = max(np.polyval(bb, t), 0.25 * f.mean())
            for m, (pp, pc) in prem.items():
                out.append({"station_key": st, "month": mo, "year": t, "method": m,
                            "prem_put": pp, "prem_call": pc, "pay_put": real_p, "pay_call": real_c})
    return pd.DataFrame(out)


def report_wf(wf, label):
    print(f"--- {label}: pooled loss ratio (sum payout / sum pure premium), 1996-2025, prior-years strikes")
    rows = []
    for m, g in wf.groupby("method", sort=False):
        lp = g.pay_put.sum() / g.prem_put.sum()
        lc = g.pay_call.sum() / g.prem_call.sum()
        # per station-month dispersion of the loss ratio (how wrong a single contract's price is)
        sm_ = g.groupby(["station_key", "month"]).agg(pp=("pay_put", "sum"), qp=("prem_put", "sum"),
                                                       pc=("pay_call", "sum"), qc=("prem_call", "sum"))
        rp, rc = sm_.pp / sm_.qp, sm_.pc / sm_.qc
        rows.append({"method": m, "put_LR": lp, "call_LR": lc, "pair_LR": (g.pay_put.sum() + g.pay_call.sum()) / (g.prem_put.sum() + g.prem_call.sum()),
                     "put_LR_mad_log": np.nanmedian(np.abs(np.log(rp.clip(lower=0.05)))),
                     "call_LR_mad_log": np.nanmedian(np.abs(np.log(rc.clip(lower=0.05)))),
                     "share_pair_LR_gt_1.2": float(((sm_.pp + sm_.pc) / (sm_.qp + sm_.qc) > 1.2).mean())})
    print(pd.DataFrame(rows).round(3).to_string(index=False))


print("\n=== 3. Walk-forward pricing, rain_total ===")
if "part2" not in sys.argv:
    wf_rain = walk_forward(rain, "rain_in")
    report_wf(wf_rain, "rain")

# daily data for temp, wet-days ladder test
daily = []
for _, st in stations.iterrows():
    d = rx.fetch_daily(st, offline=True)
    if d is not None:
        daily.append(d)
dm = rx.monthly_from_daily(pd.concat(daily, ignore_index=True))
print("\n=== 3b. Walk-forward pricing, temp (monthly mean, put floor 5th pct) ===")
if "part2" not in sys.argv:
    wf_temp = walk_forward(dm[dm.station_key != "SLC"], "temp_f", floor_q=rx.TEMP_FLOOR_Q)
    report_wf(wf_temp, "temp")
print("\n=== 3c. Walk-forward pricing, snow_total (13 snow cities, Nov-Apr) ===")
sn = dm[dm.station_key.isin(rx.SNOW_STATIONS) & dm.month.isin(rx.SNOW_MONTHS)]
# keep station-months with 30th pct >= 1 in
ok = sn.groupby(["station_key", "month"]).snow_in.quantile(0.3)
ok = ok[ok >= 1.0].index
sn = sn.set_index(["station_key", "month"]).loc[ok].reset_index()
if "part2" not in sys.argv:
    wf_snow = walk_forward(sn, "snow_in")
    report_wf(wf_snow, "snow")

# ------------------------------------------------------------------ 4. ENSO
print("\n=== 4. ENSO conditioning ===")
oni = pd.read_csv(SCR / "dl" / "oni.txt", sep=r"\s+")
seas_mid = {"DJF": 1, "JFM": 2, "FMA": 3, "MAM": 4, "AMJ": 5, "MJJ": 6, "JJA": 7, "JAS": 8, "ASO": 9, "SON": 10, "OND": 11, "NDJ": 12}
oni["month"] = oni.SEAS.map(seas_mid)
oni = oni.rename(columns={"YR": "year", "ANOM": "oni"})[["year", "month", "oni"]]
# predictor known before the contract: ASO value of the preceding autumn for Nov-Mar months
aso = oni[oni.month == 9].set_index("year").oni
units = rx.unit_payouts(rain)
units = units[units.station_key.isin(keep[keep >= 70].index)]
units["season_year"] = np.where(units.month >= 11, units.year, units.year - 1)
win = units[units.month.isin([11, 12, 1, 2, 3])].copy()
win["aso"] = win.season_year.map(aso)
win["phase"] = np.select([win.aso >= 0.5, win.aso <= -0.5], ["El Nino", "La Nina"], "neutral")
reg = {s: r for r, ss in rx.REGIONS.items() for s in ss}
win["region"] = win.station_key.map(reg)
tab = win.groupby(["region", "phase"])[["put", "call"]].mean().unstack("phase").round(2)
print("Nov-Mar unit payouts (climatological mean = 1.00) by preceding ASO ONI phase:")
print(tab.to_string())
print("seasons per phase:", win.drop_duplicates("season_year").phase.value_counts().to_dict())
for s in ["DFW", "OKC", "SAT", "AUS", "HOU", "ABQ", "PHX", "LAX", "SEA", "CMH", "IND", "LEX", "PIT", "MIA", "TPA"]:
    g = win[win.station_key == s]
    if len(g):
        r = g.groupby("phase")[["put", "call"]].mean()
        print(f"  {s}: put LaNina {r.loc['La Nina','put']:.2f} ElNino {r.loc['El Nino','put']:.2f} | call LaNina {r.loc['La Nina','call']:.2f} ElNino {r.loc['El Nino','call']:.2f}")
# national winter put pool: how much of its year-to-year variance does ENSO explain?
pool = win.groupby("season_year").agg(put=("put", "mean"), call=("call", "mean"), aso=("aso", "first"))
pool = pool[(pool.index >= 1951) & (pool.index <= 2024)]
print("national Nov-Mar put pool: corr with ASO ONI %.2f (R2 %.2f); call pool corr %.2f" % (
    pool.put.corr(pool.aso), pool.put.corr(pool.aso) ** 2, pool.call.corr(pool.aso)))
sc = win[win.region == "south_central"].groupby("season_year").put.mean()
print("south_central Nov-Mar put pool corr with ONI %.2f (R2 %.2f)" % (sc.corr(pool.aso), sc.corr(pool.aso) ** 2))
# cross-region natural pair: south_central dry vs SEA/OH-valley dry
for other in (["SEA"], ["CMH", "IND", "LEX", "PIT"], ["MIA", "TPA"], ["PHX", "LAX", "ABQ"]):
    o = win[win.station_key.isin(other)].groupby("season_year").put.mean()
    j = pd.concat([sc, o], axis=1, keys=["sc", "o"]).dropna()
    print(f"  corr(south_central winter put, {'+'.join(other)} winter put) = {j.sc.corr(j.o):.2f}")
# within-phase vs unconditional mean pairwise correlations of winter put among southern-tier stations
south = ["DFW", "OKC", "SAT", "AUS", "HOU", "ABQ", "PHX", "LAX", "MIA", "TPA", "ATL", "MSY"]
piv = win[win.station_key.isin(south)].pivot_table(index="season_year", columns="station_key", values="put")
c = piv.corr().values
print("southern-tier winter put mean pairwise corr: %.2f over %d stations" % (c[np.triu_indices_from(c, 1)].mean(), piv.shape[1]))
# adverse selection: hedger buys only when the ASO ONI signals the side that pays
print("Adverse selection, Nov-Mar: loss ratio to MM priced at climatology (1.00 = fair; load is 1.20)")
for lab, mask, side in (("south_central put, bought only after La Nina ASO", (win.region == "south_central") & (win.phase == "La Nina"), "put"),
                         ("south_central call, bought only after El Nino ASO", (win.region == "south_central") & (win.phase == "El Nino"), "call"),
                         ("west put, bought only after La Nina ASO", (win.region == "west") & (win.phase == "La Nina"), "put"),
                         ("southeast put, La Nina", (win.region == "southeast") & (win.phase == "La Nina"), "put"),
                         ("southeast call, El Nino", (win.region == "southeast") & (win.phase == "El Nino"), "call"),
                         ("SEA call, La Nina", (win.station_key == "SEA") & (win.phase == "La Nina"), "call"),
                         ("midwest+OH put, El Nino", (win.region == "midwest") & (win.phase == "El Nino"), "put")):
    print(f"  {lab}: {win.loc[mask, side].mean():.2f}  (n station-months {mask.sum()})")
print("current ASO 2026 ONI:", oni[(oni.year == 2026) & (oni.month == 9)].oni.tolist())

# ------------------------------------------------------------------ 5. demand-weighted farmer pool
print("\n=== 5. Demand-concentrated farmer put pool (south_central+west, Apr-Sep) vs equal-weight national ===")
for lab, sts, months in (("plains+west growing season", rx.REGIONS["south_central"] + rx.REGIONS["west"] + ["SGF", "STL"], range(4, 10)),
                         ("south_central only, Nov-Feb (companion months)", rx.REGIONS["south_central"], [11, 12, 1, 2]),
                         ("national all months (equal weight)", list(units.station_key.unique()), range(1, 13))):
    sub = units[units.station_key.isin(sts) & units.month.isin(list(months))]
    sub = sub.assign(sy=np.where(sub.month >= 11, sub.year, sub.year - 1) if 11 in list(months) else sub.year)
    a = sub.groupby("sy").agg(pay=("put", "mean"), n=("put", "size"))
    a = a[a.n >= 0.9 * a.n.max()]
    loss = a.pay - (1 + LOAD)
    print(f"  {lab}: {len(sts)} stations, {len(a)} years, capital95/prem {max(0, np.quantile(loss, .95))/(1+LOAD):.3f}, worst {loss.max()/(1+LOAD):+.3f}")

# ------------------------------------------------------------------ 6. can a monthly-total ladder replicate day counts?
print("\n=== 6. Ladder (any function of the monthly total) vs wet-day count payouts ===")
dd = pd.concat(daily, ignore_index=True)
dd["year"], dd["month"] = dd.date.dt.year, dd.date.dt.month
dd["wet"] = dd.pcpn >= 0.10
dd["wkwet"] = dd.wet & dd.date.dt.dayofweek.isin([4, 5, 6])
g = dd.groupby(["station_key", "year", "month"]).agg(tot=("pcpn", "sum"), wet=("wet", "sum"), wk=("wkwet", "sum"), miss=("pcpn", lambda s: s.isna().sum()))
g = g[g.miss == 0].reset_index()
res = []
for (st, mo), h in g.groupby(["station_key", "month"]):
    if len(h) < 60 or st == "SLC":
        continue
    for var in ("wet", "wk"):
        y = h[var].to_numpy(float)
        k, e = rx.call_terms(y, True)
        pay = rx.call_frac(y, k, e)
        if pay.var() == 0:
            continue
        # best ladder = conditional mean of the payout given the monthly-total decile (in-sample, optimistic)
        bins = pd.qcut(h.tot.rank(method="first"), 10, labels=False)
        fit = pd.Series(pay).groupby(bins.to_numpy()).transform("mean").to_numpy()
        r2_pay = 1 - ((pay - fit) ** 2).mean() / pay.var()
        res.append({"st": st, "mo": mo, "var": var, "corr_count_total": np.corrcoef(y, h.tot)[0, 1], "r2_payout_from_total": r2_pay})
res = pd.DataFrame(res)
print(res.groupby("var")[["corr_count_total", "r2_payout_from_total"]].median().round(3).to_string())
print(res.groupby("var")[["r2_payout_from_total"]].quantile([0.1, 0.9]).round(3).to_string())

# ------------------------------------------------------------------ 7. split sensitivity (ASOS deployment 1992-1997)
print("\n=== 7. OOS split-year sensitivity, rain_total pooled loss ratios ===")
for sp in (1980, 1985, 1990, 1995, 2000, 2005):
    uu = oos_units(rain, split=sp)
    uu = uu[uu.station_key.isin(keep[keep >= 70].index)]
    print(f"  split {sp}: put {uu.put.mean():.3f} call {uu.call.mean():.3f}")
