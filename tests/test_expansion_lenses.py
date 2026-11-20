"""Helpers of scripts/run_expansion_lenses.py (doc 25 follow-ups: lender book, ENSO pricing, solar)."""
import importlib.util
from pathlib import Path

import numpy as np

from agri_hedge import optimizer as op

_spec = importlib.util.spec_from_file_location(
    "run_expansion_lenses", Path(__file__).resolve().parents[1] / "scripts" / "run_expansion_lenses.py")
lens = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lens)


def test_enso_phase_and_season_year():
    assert lens.enso_phase([2.46, 0.5, 0.49, -0.43, -0.5]).tolist() == ["El Nino", "El Nino", "neutral", "neutral", "La Nina"]
    assert lens.season_year([2026, 2027, 2026], [11, 1, 6]).tolist() == [2026, 2026, 2025]


def test_aso_oni_reads_current_value():
    aso = lens.load_aso_oni()
    assert aso.loc[2026] == 2.46
    assert aso.loc[2025] == -0.43


def test_survival_uses_kalshi_above_convention_and_skips_nan():
    x = np.array([0.5, 1.0, 1.5, 3.0, np.nan])
    # "Above 1 inch" is NO at exactly 1.0 (pricing.no_pays)
    assert lens.survival(x, [1, 2]).tolist() == [0.5, 0.25]


def test_implied_mean_matches_truncated_mean_of_uniform():
    ks = np.arange(1, 8)
    s = np.clip(1 - ks / 7.0, 0, 1)          # X ~ U(0, 7): E[min(X, 7)] = 3.5
    assert abs(lens.implied_mean(ks, s) - 3.5) < 1e-12


def test_quote_mid_rejects_wide_or_empty_quotes():
    m = lens.quote_mid([0.40, 0.0, 0.10, 0.50], [0.45, 0.30, 0.95, 1.0])
    assert abs(m[0] - 0.425) < 1e-12 and np.isnan(m[1:]).all()


def test_book_stats_pooling_helps_only_with_common_signal_and_independent_basis():
    rng = np.random.default_rng(0)
    n, k = 4000, 20
    common = rng.normal(size=(n, 1))
    y = common + rng.normal(size=(n, k))        # each farm: common signal + own basis
    h = np.repeat(common, k, axis=1)             # hedge captures the common signal only
    s = lens.book_stats(y, h, limit=True)
    assert abs(s["he_farm_median"] - 0.5) < 0.05
    assert s["he_pooled"] > 0.9 and abs(s["he_if_uncorrelated"] - 0.5) < 0.05
    assert abs(s["rho_y"] - 0.5) < 0.05 and abs(s["rho_e"]) < 0.05
    assert s["he_limit"] > 0.98
    # same basis error for every farm: pooling adds nothing
    y2 = common + np.repeat(rng.normal(size=(n, 1)), k, axis=1)
    s2 = lens.book_stats(y2, h)
    assert abs(s2["he_pooled"] - s2["he_farm_median"]) < 0.02


def test_loyo_leg_payouts_sum_to_optimizer_loyo():
    rng = np.random.default_rng(1)
    rain = rng.gamma(2.0, 1.0, 60)
    X = np.column_stack([(rain <= k).astype(float) for k in (1.0, 2.0, 3.0)])
    y = np.clip(2.5 - rain, 0, None) * 1000
    tr = op.model_tranches(X.mean(0))
    legs = lens.loyo_leg_payouts(X, y, tr, 800.0, 3000.0)
    tot = op.loyo_payout(X, y, tr, 800.0, 3000.0)
    assert legs.shape == X.shape
    assert np.allclose(legs.sum(1), tot)


def test_nnls_loyo_he():
    rng = np.random.default_rng(2)
    x = rng.normal(size=(80, 2))
    assert lens.nnls_loyo_he(x, 2 * x[:, 0] + 0.5 * x[:, 1]) > 0.999
    # a hedge that would need a negative weight is not allowed: HE about zero or below
    assert lens.nnls_loyo_he(x[:, :1], -x[:, 0]) < 0.05
