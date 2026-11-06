"""Checks for the 2026-11 data fixes: final NASS hay prices, dated order-book snapshots, and the
before/after snapshot comparison (docs 03b, 04b, 05b, 09, 12)."""
import importlib.util

import numpy as np
import pandas as pd
import pytest
import yaml

from agri_hedge.config import PROCESSED, ROOT, SCENARIOS


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


r2 = _load("r2_calcs", "scripts/r2_rain_yield_calcs.py")
pk = _load("pull_kalshi_mod", "scripts/pull_kalshi.py")
rpc = _load("run_payout_mod", "scripts/run_payout_comparison.py")
cmp_ = _load("compare_snapshots", "scripts/compare_orderbook_snapshots.py")

# Final 2025 MYA "other hay" prices, NASS Agricultural Prices (Aug 31 2026) p.33.
FINAL_HAY = {"TX": 130.0, "OK": 88.0, "MO": 113.0, "FL": 120.0, "CO": 153.0, "NM": 185.0, "US": 137.0}


# ---------------------------------------------------------------- hay prices
def test_r2_uses_final_nass_hay_prices():
    assert r2.HAY_PRICE_2025 == FINAL_HAY
    assert r2.ALFALFA_PRICE_US_2025 == 172.0
    assert "Agricultural Prices (Aug 31 2026)" in r2.HAY_PRICE_BASIS


def test_farms_yaml_hay_values_match_final_prices():
    """Haying value per acre = expected tons/acre x final state price (to the cent of rounding)."""
    st = {"DFW": "TX", "OKC": "OK", "SGF": "MO", "TPA": "FL"}
    farms = yaml.safe_load((SCENARIOS / "farms.yaml").read_text(encoding="utf-8"))["farms"]
    hay = [f for f in farms if f["intended_use"] == "haying"]
    assert len(hay) == 4
    for f in hay:
        implied_price = f["expected_value_usd_per_acre"] / f["expected_production"]["value"]
        # OKC yield is 1.69 t/ac stored with 2 decimals; allow that rounding
        assert implied_price == pytest.approx(FINAL_HAY[st[f["site"]]], abs=0.1), f["farm_id"]


def test_sensitivity_csv_hay_rows_at_final_prices():
    d = pd.read_csv(PROCESSED / "crop_rain_sensitivity_other.csv").set_index("row_key")
    assert d.loc["hay_other_TX_state_AprJun", "price_usd_per_unit"] == 130.0
    assert d.loc["hay_other_OK_Grady_AprJun", "price_usd_per_unit"] == 88.0
    assert d.loc["hay_other_MO_state_AprJun", "price_usd_per_unit"] == 113.0
    assert d.loc["hay_bermuda_TXOK_wateruse_lowN", "price_usd_per_unit"] == pytest.approx(0.065)
    assert d.loc["hay_alfalfa_CA_ET_lit", "usd_per_acre_per_inch"] == pytest.approx(34.4)
    assert not d["price_basis"].fillna("").str.contains("Crop Values 2025 Summary").any()


def test_hay_row_price_mapping():
    assert r2.hay_row_price("hay_other_OK_state_AprSep") == (88.0, r2.HAY_PRICE_BASIS)
    assert r2.hay_row_price("hay_bermuda_TXOK_wateruse_lowN")[0] == pytest.approx(0.065)
    assert r2.hay_row_price("hay_alfalfa_NM_ET_lit")[0] == 172.0
    assert r2.hay_row_price("scen_DFW_hay") is None
    assert r2.hay_row_price("hay_other_XX_state_AprJun") is None


def test_reprice_hay_rows_scales_and_is_idempotent():
    df = pd.DataFrame({
        "row_key": ["hay_other_TX_state_AprJun", "hay_other_FL_state_MarMay", "wheat_KS_x"],
        "price_usd_per_unit": [136.0, 120.0, 5.0],
        "price_basis": ["old", r2.HAY_PRICE_BASIS, "WASDE"],
        "usd_per_acre_per_inch": [9.59, 1.59, 20.0]})
    out, changed = r2.reprice_hay_rows(df)
    assert changed == ["hay_other_TX_state_AprJun"]
    assert out.loc[0, "price_usd_per_unit"] == 130.0
    assert out.loc[0, "usd_per_acre_per_inch"] == pytest.approx(round(9.59 * 130 / 136, 2))
    assert out.loc[0, "price_basis"] == r2.HAY_PRICE_BASIS
    assert out.loc[2].tolist() == df.loc[2].tolist()          # non-hay row untouched
    again, changed2 = r2.reprice_hay_rows(out)
    assert changed2 == [] and again.equals(out)


# ---------------------------------------------------------------- dated snapshots
def test_snapshot_paths_are_dated():
    assert pk.snapshot_day("20261102T013456Z") == "20261102"
    assert pk.orderbook_summary_path("20261102T013456Z").name == "kalshi_rain_orderbook_summary_20261102.csv"
    assert pk.capacity_path("20261029T093056Z").name == "kalshi_rain_hedge_capacity_nov2026_20261029.csv"
    with pytest.raises(ValueError):
        pk.snapshot_day("latest")


def test_both_snapshots_committed_and_latest_is_newest():
    b = pd.read_csv(PROCESSED / "kalshi_rain_orderbook_summary_20261029.csv")
    a = pd.read_csv(PROCESSED / "kalshi_rain_orderbook_summary_20261102.csv")
    latest = pd.read_csv(PROCESSED / "kalshi_rain_orderbook_summary.csv")
    assert set(b["snapshot_utc"]) == {"20261029T093056Z"} and len(b) == 353
    assert set(a["snapshot_utc"]) == {"20261102T013456Z"} and len(a) == 269
    assert set(latest["snapshot_utc"]) == set(a["snapshot_utc"])
    for d in ("20261029", "20261102"):
        assert (PROCESSED / f"kalshi_rain_hedge_capacity_nov2026_{d}.csv").exists()


def test_book_date():
    ob = pd.DataFrame({"snapshot_utc": ["20261102T013456Z"] * 3})
    assert rpc.book_date(ob) == "2026-11-02"
    with pytest.raises(ValueError):
        rpc.book_date(pd.DataFrame({"snapshot_utc": ["20261029T093056Z", "20261102T013456Z"]}))


# ---------------------------------------------------------------- before/after comparison
def _cap(rows):
    base = {m: 0.0 for m in cmp_.CITY_METRICS}
    return pd.DataFrame([{**base, **r} for r in rows])


def test_reward_groups():
    progs = pd.DataFrame({"series_ticker": ["A", "A", "B", "C"],
                          "end_date": ["2026-10-04T03:59:59Z", "2026-11-01T03:59:59.999999Z",
                                       "2026-10-04T03:59:59Z", "2026-08-01T03:59:00Z"]})
    assert cmp_.reward_groups(progs) == {"A": "rewarded", "B": "control", "C": "control"}
    assert cmp_.reward_groups(pd.DataFrame()) == {}


def test_compare_cities_and_group_medians():
    before = _cap([{"series_ticker": "A", "site": "SAT", "no_payout_useful": 1000.0},
                   {"series_ticker": "B", "site": np.nan, "no_payout_useful": 100.0},
                   {"series_ticker": "Z", "site": np.nan, "no_payout_useful": 0.0}])
    after = _cap([{"series_ticker": "A", "no_payout_useful": 50.0},
                  {"series_ticker": "B", "no_payout_useful": 150.0},
                  {"series_ticker": "Z", "no_payout_useful": 10.0}])
    out = cmp_.compare_cities(before, after, {"A": "rewarded", "B": "control"})
    r = out.set_index("series_ticker")
    assert r.loc["A", "no_payout_useful_ratio"] == pytest.approx(0.05)
    assert r.loc["B", "no_payout_useful_ratio"] == pytest.approx(1.5)
    assert np.isnan(r.loc["Z", "no_payout_useful_ratio"])     # before = 0 -> no ratio
    assert r.loc["Z", "reward_group"] == "control"             # unknown series default to control
    assert r.loc["B", "site"] == ""
    gm = cmp_.group_medians(out).set_index("reward_group")
    assert gm.loc["rewarded", "series_useful_no_down"] == 1
    assert gm.loc["control", "series_useful_no_down"] == 0


def test_compare_farms_weighted_total():
    cols = {m: 0.0 for m in cmp_.FARM_METRICS}
    before = pd.DataFrame([{"farm_id": "f1", "site": "X", "cap_contracts_per_year": 100.0, **cols,
                            "cap_fill_share_sensible": 1.0, "cap_busiest_month_contracts": 50.0},
                           {"farm_id": "f2", "site": "Y", "cap_contracts_per_year": 300.0, **cols,
                            "cap_fill_share_sensible": 0.0, "cap_busiest_month_contracts": 70.0}])
    after = before.drop(columns=["site", "cap_contracts_per_year"]).assign(cap_fill_share_sensible=[0.5, 0.5])
    out = cmp_.compare_farms(before, after).set_index("farm_id")
    tot = out.loc["ALL (contract-weighted)"]
    assert tot["cap_fill_share_sensible_before"] == pytest.approx(0.25)
    assert tot["cap_fill_share_sensible_after"] == pytest.approx(0.5)
    assert tot["cap_busiest_month_contracts_before"] == pytest.approx(120.0)  # counts are summed


def test_committed_comparison_headline():
    """Doc 12 headline: every rewarded series lost depth; most control series did not."""
    c = pd.read_csv(PROCESSED / "kalshi_post_rewards_city_compare.csv")
    rew, ctl = c[c["reward_group"] == "rewarded"], c[c["reward_group"] == "control"]
    assert len(rew) == 20 and len(ctl) == 16
    assert (rew["no_payout_useful_after"] < rew["no_payout_useful_before"]).all()
    assert (ctl["no_payout_useful_after"] < ctl["no_payout_useful_before"]).sum() == 3
    f = pd.read_csv(PROCESSED / "kalshi_post_rewards_farm_compare.csv").set_index("farm_id")
    tot = f.loc["ALL (contract-weighted)"]
    assert tot["cap_fill_share_sensible_before"] == pytest.approx(0.56, abs=0.005)
    assert tot["cap_fill_share_sensible_after"] == pytest.approx(0.20, abs=0.005)
