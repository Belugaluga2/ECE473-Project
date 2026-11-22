"""Boundary checks for a cross-calendar-year index pilot and sparse-event uncertainty."""
import importlib.util
from pathlib import Path
import numpy as np

spec=importlib.util.spec_from_file_location('chipata_pilot',Path(__file__).resolve().parents[1]/'scripts/run_chipata_pilot.py')
pilot=importlib.util.module_from_spec(spec);spec.loader.exec_module(pilot)


def test_harvest_year_uses_previous_november_and_december():
    m={(1981,11):10,(1981,12):20,(1982,1):30,(1982,2):40,(1982,3):50,(1982,11):1000}
    totals=pilot.seasonal_totals(m,(11,12,1,2,3))
    assert totals.loc[1982]==150 and np.isnan(totals.loc[1983])


def test_no_historical_events_does_not_imply_zero_risk():
    low,high=pilot.binomial_interval(0,24)
    assert low==0 and 0.10<high<0.20
