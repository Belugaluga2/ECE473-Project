"""Every representative farm in data/scenarios/farms.yaml must satisfy the PRF election rules."""
import importlib.util

import pytest

from agri_hedge.config import ROOT

_spec = importlib.util.spec_from_file_location("r8_county", ROOT / "scripts" / "r8_pull_county_data.py")
r8 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(r8)

FARMS = r8.load_farms()


def test_farms_file_not_empty():
    assert len(FARMS) >= 7


def test_farm_ids_unique():
    ids = [f["farm_id"] for f in FARMS]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("farm", FARMS, ids=[f["farm_id"] for f in FARMS])
def test_farm_obeys_prf_rules(farm):
    assert r8.validate_farm(farm) == []


def test_validator_rejects_overlapping_intervals():
    bad = dict(FARMS[0])
    bad["interval_allocation"] = {"Apr-May": 0.5, "May-Jun": 0.5}
    assert any("share a month" in msg for msg in r8.validate_farm(bad))
