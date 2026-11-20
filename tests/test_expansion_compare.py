"""Helpers of scripts/run_expansion_compare.py (doc 25 head-to-head comparison)."""
import importlib.util
from pathlib import Path

import numpy as np

_spec = importlib.util.spec_from_file_location(
    "run_expansion_compare", Path(__file__).resolve().parents[1] / "scripts" / "run_expansion_compare.py")
cmp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cmp)


def test_weak_link_punishes_a_fatal_flaw_more_than_additive():
    w = np.array([0.5, 0.5])
    balanced = np.array([[3.0, 3.0]])
    flawed = np.array([[5.0, 1.0]])
    assert cmp.additive(balanced, w)[0] == cmp.additive(flawed, w)[0] == 3.0
    assert cmp.weak_link(flawed, w)[0] < cmp.weak_link(balanced, w)[0]


def test_ranks_desc_and_h2h():
    x = np.array([[1.0, 3.0, 2.0], [3.0, 1.0, 2.0]])
    assert cmp.ranks_desc(x).tolist() == [[3, 1, 2], [1, 3, 2]]
    H = cmp.h2h_matrix(x)
    assert np.allclose(H + H.T, 1.0)
    assert H[1, 2] == 0.5


def test_simulate_shapes_and_weights_sum_to_one():
    S = np.array([[5, 5], [1, 1]])
    rng = np.random.default_rng(0)
    sims = cmp.simulate(S, np.array([0.5, 0.5]), rng, 200, 40.0, noise=False)
    assert sims["weak_link"].shape == (200, 2)
    assert (sims["weak_link"][:, 0] > sims["weak_link"][:, 1]).all()
