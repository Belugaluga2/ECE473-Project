"""USDA PRF (Pasture, Rangeland, Forage) Rainfall Index premium and indemnity calculator.

This module implements the policy arithmetic of the PRF Rainfall Index plan so that every other
part of the project (scenario runner, payout comparison, Kalshi replication) prices PRF the same
way. All core functions are vectorized: they accept scalars, numpy arrays, or pandas Series (for
example one final grid index per year) and return the same shape.

Index scale: this module works on the RMA "100 = normal" scale (an index of 75.6 means the grid
received 75.6% of its long-run average rainfall for the interval). RMA's Actuarial Data Master
and Decision Support Tool publish the same numbers as fractions (0.756); use
`to_index_scale_100` to convert.

Primary sources (all read on 2026-10-29; copies cached under data/raw/prf_actuarial/handbook/):
  [HB]  FCIC-18150 Rainfall Index Insurance Standards Handbook, 2026 and succeeding crop years,
        issued 2025-08-29.
        https://www.rma.usda.gov/sites/default/files/2025-08/2026-18150-Rainfall-Index-Handbook.pdf
  [BP]  Rainfall Index Plan Common Policy (Basic Provisions) 26-RI.
        https://rma.usda.gov/sites/default/files/2025-08/Rainfall-Index-Plan-Common-Policy-26-RI.pdf
  [CP]  Rainfall Index Pasture, Rangeland, Forage Crop Provisions 26-RI-PRF.
        https://www.rma.usda.gov/sites/default/files/2025-08/Rainfall-Index-Pasture-Rangeland-Forage-Crop-Provisions-26-RI-PRF.pdf
  [ADM] RMA Actuarial Data Master, crop years 2025 and 2026, tables A00030, A00070, A00810,
        A01130, A01135, A00470/A00480/A00490/A00500.
        https://pubfs-rma.fpac.usda.gov/pub/References/actuarial_data_master/
  [DST] PRF Decision Support Tool web API (https://public-rma.fpac.usda.gov/apps/PRF), which
        uses RMA's own implementation of the arithmetic below.

Rounding. The policy text gives formulas but no rounding rules. Three conventions are supported
through the `rounding` argument:
  "official"  Reproduces the HB Exhibit 5 worked example to the dollar, and matches the
              "Payment Factor" RMA publishes in ADM table A01130: the payment calculation
              factor is rounded half-up to 3 decimals; unit premium and unit indemnity are
              rounded to whole dollars from the unrounded policy protection; premium subsidy is
              rounded once on the policy's total premium.
  "dst"       Reproduces the Decision Support Tool: dollar amount of protection per acre rounded
              to cents, policy protection per unit rounded to whole dollars, unit premium and unit
              subsidy rounded to whole dollars, unrounded payment calculation factor.
  "none"      No rounding anywhere (smooth, best for statistics over many years).
Differences between conventions are at most a few dollars per unit.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping

import numpy as np
import pandas as pd

from agri_hedge.prf_intervals import (
    CODE_TO_INTERVAL,
    INTERVAL_CODES,
    INTERVAL_MONTHS,
    INTERVAL_NAMES,
    overlaps,
)

# ---------------------------------------------------------------------------------------------
# Policy constants
# ---------------------------------------------------------------------------------------------

#: Coverage levels offered for additional coverage. [CP] 5(a)(1) and [BP] 7(a)(2)(i) allow 70
#: through 90 percent; the actuarial documents ([ADM] A01130, crop years 2025-2026, and the
#: [DST] coverage list) offer exactly these five levels.
COVERAGE_LEVELS = (0.70, 0.75, 0.80, 0.85, 0.90)

#: Productivity factor range and step. [HB] para 13: 60-150 percent for PRF in 1 percent
#: increments; [CP] 5(a)(2).
PRODUCTIVITY_FACTOR_MIN = 0.60
PRODUCTIVITY_FACTOR_MAX = 1.50
PRODUCTIVITY_FACTOR_STEP = 0.01

#: Minimum number of index intervals. [HB] para 32 C ("A minimum of two index intervals must be
#: selected"); [CP] 2(a) ("more than one index interval").
MIN_INTERVALS = 2

#: Minimum percent of value in any one selected interval. [CP] 2(a): 10 percent.
MIN_PERCENT_OF_VALUE = 0.10

#: Maximum percent of value per interval is set in the Special Provisions ([CP] 2(a)). In the
#: [ADM] A00810 "Maximum Acre Percent" field for crop years 2025-2026 it is 0.50 in TX, NM, FL
#: and 0.60 in OK, MO, CO. This module-level default is only a fallback when no actuarial value
#: is supplied; pass the ADM value for real policies.
DEFAULT_MAX_PERCENT_OF_VALUE = 0.60

#: FCIC premium subsidy share by coverage level for additional coverage. [ADM] A00070 Subsidy
#: Percent, insurance plan 13, record category 04, coverage type A, reinsurance years 2025 and
#: 2026 (identical); also [HB] Exhibit 5 A(4) (51 percent at 90 percent) and the [DST]
#: "SubsidyLevel" returned on 2026-10-29. Beginning/veteran farmer increases ([BP] 11(g)) are
#: not included.
PREMIUM_SUBSIDY_BY_COVERAGE = {0.70: 0.59, 0.75: 0.59, 0.80: 0.55, 0.85: 0.55, 0.90: 0.51}

#: Expected grid index. [HB] para 33 D and Exhibit 5 A(2): the expected grid index is 100 by
#: construction (the long-run average precipitation for the grid and interval).
EXPECTED_GRID_INDEX = 100.0

#: RMA code tables ([ADM] A00470 Intended Use, A00490 Irrigation Practice, A00500 Organic Practice).
INTENDED_USE_CODES = {"grazing": "007", "haying": "030"}
IRRIGATION_PRACTICE_CODES = {"irrigated": "002", "non-irrigated": "003", "not specified": "997"}
ORGANIC_PRACTICE_CODES = {"not organic": "997", "certified": "001", "transitional": "002"}

#: Practice combinations offered in the actuarial documents. Grazing is offered only with no
#: irrigation or organic practice specified; haying is offered irrigated or non-irrigated, each as
#: conventional, certified organic, or transitional ([ADM] A00030, 2025-2026; the [DST] disables
#: the practice drop-downs for grazing).
VALID_PRACTICES = {
    "grazing": {("not specified", "not organic")},
    "haying": {(irr, org) for irr in ("irrigated", "non-irrigated")
               for org in ("not organic", "certified", "transitional")},
}

ROUNDING_MODES = ("official", "dst", "none")


class PRFElectionError(ValueError):
    """Raised when a PRF policy election violates the policy rules. `.errors` lists every problem."""

    def __init__(self, errors: list[str]):
        self.errors = list(errors)
        super().__init__("Invalid PRF election:\n  - " + "\n  - ".join(self.errors))


# ---------------------------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------------------------

def _wrap_like(template, values):
    """Return `values` as a pandas Series if `template` is one, a float if scalar, else ndarray."""
    if isinstance(template, pd.Series):
        return pd.Series(values, index=template.index, name=template.name)
    arr = np.asarray(values, dtype=float)
    return float(arr) if arr.ndim == 0 else arr


def round_half_up(x, decimals: int = 0):
    """Round half away from zero (1.5 -> 2, 0.3025 -> 0.303), vectorized.

    Python's built-in round() and numpy.round() use banker's rounding (0.5 -> 0), which does not
    match RMA. A 1e-9 nudge absorbs binary floating-point error (e.g. 3175 * 0.1 = 317.49999...).
    NaN stays NaN.
    """
    arr = np.asarray(x, dtype=float)
    scale = 10.0 ** decimals
    out = np.sign(arr) * np.floor(np.abs(arr) * scale + 0.5 + 1e-9) / scale
    return _wrap_like(x, out)


def normalize_coverage_level(coverage_level) -> float:
    """Accept 0.9, 90, or "90%" and return a fraction rounded to 2 decimals (0.9)."""
    if isinstance(coverage_level, str):
        coverage_level = float(coverage_level.strip().rstrip("%"))
    c = float(coverage_level)
    if c > 1.0:
        c = c / 100.0
    return round(c, 2)


def normalize_fraction(value) -> float:
    """Accept 1.2, 120, or "120%" (productivity factor, share) and return a fraction."""
    if isinstance(value, str):
        value = float(value.strip().rstrip("%"))
    v = float(value)
    return v / 100.0 if v > 2.0 else v


def interval_name(key) -> str:
    """Return the canonical interval NAME ("Apr-May") for a name, RMA code (628), or "628"."""
    if isinstance(key, (int, np.integer)):
        return CODE_TO_INTERVAL[int(key)]
    s = str(key).strip()
    if s.isdigit():
        return CODE_TO_INTERVAL[int(s)]
    for name in INTERVAL_NAMES:
        if s.replace(" ", "").lower() == name.lower():
            return name
    raise KeyError(f"Unknown PRF index interval: {key!r}")


def to_index_scale_100(values):
    """Convert RMA fraction-of-normal values (0.756) to the 100 scale (75.6). Vectorized."""
    return _wrap_like(values, np.asarray(values, dtype=float) * 100.0)


# ---------------------------------------------------------------------------------------------
# Core vectorized formulas
# ---------------------------------------------------------------------------------------------

def dollar_amount_of_protection_per_acre(county_base_value, coverage_level, productivity_factor,
                                         round_cents: bool = False):
    """Dollar amount of protection per acre = county base value x coverage level x productivity factor.

    [BP] 7(a); [HB] para 14 example and Exhibit 5 E ($20.00 x .90 x 1.20 = $21.60).
    `round_cents=True` rounds to the cent as the [DST] does.
    """
    ppa = (np.asarray(county_base_value, dtype=float) * np.asarray(coverage_level, dtype=float)
           * np.asarray(productivity_factor, dtype=float))
    if round_cents:
        ppa = np.asarray(round_half_up(ppa, 2))
    return _wrap_like(county_base_value, ppa)


def policy_protection_per_unit(protection_per_acre, insured_acres, percent_of_value, share=1.0):
    """Policy protection per unit = protection per acre x insured acres x percent of value x share.

    A unit is one grid ID x index interval x intended use x practice x share ([BP] section 1
    "Unit"). [BP] 7(c)(1); [HB] para 14 ($21.60 x 1,000 acres x 60% x 1.00 = $12,960).
    """
    pp = (np.asarray(protection_per_acre, dtype=float) * np.asarray(insured_acres, dtype=float)
          * np.asarray(percent_of_value, dtype=float) * np.asarray(share, dtype=float))
    return _wrap_like(percent_of_value if isinstance(percent_of_value, pd.Series) else protection_per_acre, pp)


def trigger_grid_index(coverage_level, expected_grid_index=EXPECTED_GRID_INDEX):
    """Trigger grid index = expected grid index x coverage level ([BP] section 1 "Trigger grid index").

    [HB] Exhibit 5 F: trigger 90 = expected 100 x 90% coverage.
    """
    return _wrap_like(coverage_level, np.asarray(expected_grid_index, dtype=float)
                      * np.asarray(coverage_level, dtype=float))


def payment_calculation_factor(final_grid_index, trigger, decimals: int | None = 3):
    """Payment calculation factor = (trigger - final) / trigger when final < trigger, else 0.

    [BP] 8(a)-(b); [HB] Exhibit 5 F. An index exactly at the trigger pays nothing ([HB] Exhibit 5
    F, interval 631 scenario 1: "equal to ... trigger ... no indemnity is due"). An index of 0
    gives a factor of 1 (total loss of the unit's protection). `decimals=3` rounds half-up to 3
    decimals as in the handbook (0.111, 0.056, 0.278) and as in RMA's published ADM A01130
    "Payment Factor"; `decimals=None` returns the unrounded factor (the [DST] convention).
    Vectorized over years: pass a Series/array of final indices. NaN (index not yet published)
    stays NaN.
    """
    fi = np.asarray(final_grid_index, dtype=float)
    tr = np.asarray(trigger, dtype=float)
    with np.errstate(invalid="ignore", divide="ignore"):
        pcf = np.where(fi < tr, (tr - fi) / tr, 0.0)
    pcf = np.where(np.isnan(fi), np.nan, pcf)
    if decimals is not None:
        pcf = np.asarray(round_half_up(pcf, decimals))
    return _wrap_like(final_grid_index, pcf)


def indemnity_per_unit(payment_factor, policy_protection, round_dollars: bool = False):
    """Indemnity = payment calculation factor x policy protection per unit ([BP] 8(c)).

    [HB] Exhibit 5 F: 0.111 x $1,296 = $144. `round_dollars=True` rounds half-up to whole dollars.
    """
    ind = np.asarray(payment_factor, dtype=float) * np.asarray(policy_protection, dtype=float)
    if round_dollars:
        ind = np.asarray(round_half_up(ind, 0))
    template = payment_factor if isinstance(payment_factor, pd.Series) else policy_protection
    return _wrap_like(template, ind)


def premium_per_unit(policy_protection, premium_rate, round_dollars: bool = False):
    """Total (unsubsidized) premium per unit = policy protection per unit x premium rate.

    [BP] 11(c); [HB] Exhibit 5 E ($21.60 x 0.1000 x 100.0 acres x 60% x 1.00 = $130 rounded).
    """
    prem = np.asarray(policy_protection, dtype=float) * np.asarray(premium_rate, dtype=float)
    if round_dollars:
        prem = np.asarray(round_half_up(prem, 0))
    return _wrap_like(policy_protection, prem)


def premium_subsidy_rate(coverage_level):
    """FCIC premium subsidy share for a coverage level (see PREMIUM_SUBSIDY_BY_COVERAGE). Vectorized."""
    levels = np.atleast_1d(np.asarray(coverage_level, dtype=float))
    out = np.empty(levels.shape)
    for i, c in enumerate(levels):
        key = normalize_coverage_level(c)
        if key not in PREMIUM_SUBSIDY_BY_COVERAGE:
            raise ValueError(f"No PRF subsidy defined for coverage level {c}")
        out[i] = PREMIUM_SUBSIDY_BY_COVERAGE[key]
    if np.ndim(coverage_level) == 0:
        return float(out[0])
    return _wrap_like(coverage_level, out)


# ---------------------------------------------------------------------------------------------
# Policy election and validation
# ---------------------------------------------------------------------------------------------

@dataclass
class PRFElection:
    """One PRF election for one grid, intended use, practice, and share.

    allocation maps interval name (or RMA code) to percent of value as a fraction, e.g.
    {"Apr-May": 0.6, "Jul-Aug": 0.4}. coverage_level and productivity_factor are fractions
    (0.90, 1.20); percentages such as 90 or 120 are also accepted and normalized.
    """
    grid_id: int | str
    county_base_value: float
    coverage_level: float
    productivity_factor: float
    insured_acres: float
    allocation: Mapping[str, float]
    intended_use: str = "grazing"
    irrigation_practice: str = "not specified"
    organic_practice: str = "not organic"
    share: float = 1.0
    county_fips: str | None = None
    label: str = ""
    _normalized: bool = field(default=False, repr=False)

    def __post_init__(self):
        self.coverage_level = normalize_coverage_level(self.coverage_level)
        self.productivity_factor = normalize_fraction(self.productivity_factor)
        self.share = normalize_fraction(self.share)
        self.intended_use = str(self.intended_use).strip().lower()
        self.irrigation_practice = _normalize_irrigation(self.irrigation_practice)
        self.organic_practice = _normalize_organic(self.organic_practice)
        alloc = {}
        for k, v in dict(self.allocation).items():
            v = float(v)
            if v > 1.0:  # given as percent
                v = v / 100.0
            alloc[interval_name(k)] = alloc.get(interval_name(k), 0.0) + v
        self.allocation = {k: alloc[k] for k in INTERVAL_NAMES if k in alloc}
        self._normalized = True

    @property
    def selected_intervals(self) -> list[str]:
        """Interval names with a positive percent of value, in calendar order."""
        return [k for k, v in self.allocation.items() if v > 0]

    @property
    def trigger(self) -> float:
        return float(trigger_grid_index(self.coverage_level))

    @property
    def subsidy_rate(self) -> float:
        return premium_subsidy_rate(self.coverage_level)


def _normalize_irrigation(value) -> str:
    if value is None:
        return "not specified"
    s = str(value).strip().lower().replace("_", "-")
    aliases = {"002": "irrigated", "irr": "irrigated", "irrigated": "irrigated",
               "003": "non-irrigated", "non-irrigated": "non-irrigated", "nonirrigated": "non-irrigated",
               "non irrigated": "non-irrigated", "ni": "non-irrigated", "nirr": "non-irrigated",
               "997": "not specified", "not specified": "not specified", "none": "not specified",
               "n/a": "not specified", "na": "not specified", "": "not specified"}
    return aliases.get(s, s)


def _normalize_organic(value) -> str:
    if value is None or value is False:
        return "not organic"
    if value is True:
        return "certified"
    s = str(value).strip().lower()
    aliases = {"997": "not organic", "no": "not organic", "false": "not organic", "none": "not organic",
               "not organic": "not organic", "conventional": "not organic", "": "not organic",
               "001": "certified", "certified": "certified", "organic": "certified", "yes": "certified",
               "true": "certified", "002": "transitional", "transitional": "transitional"}
    return aliases.get(s, s)


def validate_election(election: PRFElection,
                      max_percent_of_value: float | Mapping[str, float] | None = None,
                      min_percent_of_value: float | Mapping[str, float] = MIN_PERCENT_OF_VALUE,
                      available_intervals: Iterable | None = None,
                      raise_on_error: bool = True) -> list[str]:
    """Check a PRF election against the policy rules; return (or raise) the list of violations.

    Rules checked:
      * coverage level is one of COVERAGE_LEVELS ([CP] 5(a)(1); [BP] 7(a)(2)(i));
      * productivity factor in 60-150 percent, 1 percent steps ([HB] para 13; [CP] 5(a)(2));
      * intended use is haying or grazing ([HB] para 16; [CP] 3(a)(2)) and the irrigation/organic
        practice combination is one offered for that use (see VALID_PRACTICES);
      * at least MIN_INTERVALS intervals selected ([HB] para 32 C; [CP] 2(a));
      * each selected interval has at least the minimum percent of value, 10 percent ([CP] 2(a)),
        and at most the maximum in the Special Provisions ([CP] 2(a); [ADM] A00810);
      * percents of value sum to 100 percent ([HB] para 14);
      * no month appears in two selected intervals ([CP] 2(b));
      * selected intervals are offered for the grid/county ([HB] para 32 B, "See the AD");
      * insured acres > 0, share in (0, 1], county base value > 0.
    `max_percent_of_value` and `min_percent_of_value` may be a scalar or a dict keyed by interval.
    """
    e = election
    errors: list[str] = []
    if e.coverage_level not in COVERAGE_LEVELS:
        errors.append(f"coverage level {e.coverage_level:.2f} not in {COVERAGE_LEVELS}")
    pf = e.productivity_factor
    if not (PRODUCTIVITY_FACTOR_MIN - 1e-9 <= pf <= PRODUCTIVITY_FACTOR_MAX + 1e-9):
        errors.append(f"productivity factor {pf:.2f} outside {PRODUCTIVITY_FACTOR_MIN:.2f}-{PRODUCTIVITY_FACTOR_MAX:.2f}")
    elif abs(pf * 100 - round(pf * 100)) > 1e-6:
        errors.append(f"productivity factor {pf} is not a whole percent (1 percent increments)")
    if e.intended_use not in VALID_PRACTICES:
        errors.append(f"intended use {e.intended_use!r} must be 'haying' or 'grazing'")
    elif (e.irrigation_practice, e.organic_practice) not in VALID_PRACTICES[e.intended_use]:
        errors.append(f"practice ({e.irrigation_practice}, {e.organic_practice}) not offered for "
                      f"{e.intended_use}; offered: {sorted(VALID_PRACTICES[e.intended_use])}")
    if not e.insured_acres or e.insured_acres <= 0:
        errors.append("insured acres must be positive")
    if not (0 < e.share <= 1.0 + 1e-9):
        errors.append(f"share {e.share} must be in (0, 1]")
    if e.county_base_value is None or not np.isfinite(e.county_base_value) or e.county_base_value <= 0:
        errors.append("county base value must be a positive number")

    negative = [k for k, v in e.allocation.items() if v < 0]
    if negative:
        errors.append(f"negative percent of value for {negative}")
    selected = e.selected_intervals
    if len(selected) < MIN_INTERVALS:
        errors.append(f"at least {MIN_INTERVALS} index intervals must be selected (got {len(selected)})")
    total = sum(e.allocation.values())
    if abs(total - 1.0) > 1e-6:
        errors.append(f"percent of value must sum to 100% (got {total * 100:.2f}%)")
    for k in selected:
        v = e.allocation[k]
        lo = min_percent_of_value.get(k, MIN_PERCENT_OF_VALUE) if isinstance(min_percent_of_value, Mapping) else min_percent_of_value
        if max_percent_of_value is None:
            hi = DEFAULT_MAX_PERCENT_OF_VALUE
        elif isinstance(max_percent_of_value, Mapping):
            hi = max_percent_of_value.get(k, DEFAULT_MAX_PERCENT_OF_VALUE)
        else:
            hi = max_percent_of_value
        if v < lo - 1e-9:
            errors.append(f"{k}: percent of value {v * 100:.1f}% below minimum {lo * 100:.0f}%")
        if v > hi + 1e-9:
            errors.append(f"{k}: percent of value {v * 100:.1f}% above maximum {hi * 100:.0f}%")
    for i, a in enumerate(selected):
        for b in selected[i + 1:]:
            if overlaps(a, b):
                errors.append(f"intervals {a} and {b} overlap (share a month)")
    if available_intervals is not None:
        avail = {interval_name(k) for k in available_intervals}
        missing = [k for k in selected if k not in avail]
        if missing:
            errors.append(f"intervals not offered in the actuarial documents for this grid: {missing}")
    if errors and raise_on_error:
        raise PRFElectionError(errors)
    return errors


# ---------------------------------------------------------------------------------------------
# Policy-level calculations
# ---------------------------------------------------------------------------------------------

def _rates_for(election: PRFElection, premium_rates) -> np.ndarray:
    """Premium rate per selected interval (calendar order) from a dict/Series keyed by name or code."""
    rates = {}
    items = premium_rates.items() if hasattr(premium_rates, "items") else dict(premium_rates).items()
    for k, v in items:
        rates[interval_name(k)] = float(v)
    missing = [k for k in election.selected_intervals if k not in rates]
    if missing:
        raise KeyError(f"premium rate missing for intervals {missing}")
    return np.array([rates[k] for k in election.selected_intervals])


def policy_table(election: PRFElection, premium_rates, final_index=None,
                 rounding: str = "official", validate: bool = True, **validate_kwargs) -> pd.DataFrame:
    """Per-unit (interval) table for one crop year: protection, premium, subsidy, indemnity.

    premium_rates: rate per interval at the election's coverage level (dict or Series keyed by
    interval name or code). final_index: optional final grid index per interval on the 100 scale
    (dict/Series); intervals missing from it get NaN indemnity. The returned frame has one row per
    selected interval plus attributes `df.attrs["totals"]` with the policy totals.
    """
    if rounding not in ROUNDING_MODES:
        raise ValueError(f"rounding must be one of {ROUNDING_MODES}")
    if validate:
        validate_election(election, **validate_kwargs)
    e = election
    names = e.selected_intervals
    pov = np.array([e.allocation[k] for k in names])
    rates = _rates_for(e, premium_rates)
    ppa_raw = float(dollar_amount_of_protection_per_acre(e.county_base_value, e.coverage_level, e.productivity_factor))
    ppa = float(round_half_up(ppa_raw, 2)) if rounding == "dst" else ppa_raw
    prot_raw = np.asarray(policy_protection_per_unit(ppa, e.insured_acres, pov, e.share))
    prot_shown = np.asarray(round_half_up(prot_raw, 0)) if rounding != "none" else prot_raw
    prot_for_calc = prot_shown if rounding == "dst" else prot_raw
    prem = np.asarray(premium_per_unit(prot_for_calc, rates, round_dollars=rounding != "none"))
    sub_rate = e.subsidy_rate
    if rounding == "dst":
        subsidy = np.asarray(round_half_up(prem * sub_rate, 0))
    else:
        subsidy = prem * sub_rate
    if final_index is not None:
        fi_map = {interval_name(k): float(v) for k, v in dict(final_index).items()}
        fi = np.array([fi_map.get(k, np.nan) for k in names])
    else:
        fi = np.full(len(names), np.nan)
    pcf = np.asarray(payment_calculation_factor(fi, e.trigger, decimals=3 if rounding == "official" else None))
    ind = np.asarray(indemnity_per_unit(pcf, prot_for_calc, round_dollars=rounding != "none"))
    df = pd.DataFrame({
        "interval_name": names,
        "interval_code": [INTERVAL_CODES[k] for k in names],
        "percent_of_value": pov,
        "policy_protection": prot_shown,
        "premium_rate": rates,
        "total_premium": prem,
        "premium_subsidy": subsidy,
        "producer_premium": prem - subsidy,
        "final_index": fi,
        "payment_calculation_factor": pcf,
        "indemnity": ind,
    })
    total_prem = float(prem.sum())
    total_sub = float(round_half_up(total_prem * sub_rate, 0)) if rounding == "official" else float(subsidy.sum())
    df.attrs["totals"] = {
        "protection_per_acre": ppa,
        "policy_protection": float(prot_shown.sum()),
        "total_premium": total_prem,
        "premium_subsidy": total_sub,
        "producer_premium": total_prem - total_sub,
        "indemnity": float(np.nansum(ind)),
        "subsidy_rate": sub_rate,
        "trigger": e.trigger,
    }
    return df


def simulate_years(election: PRFElection, premium_rates, index_by_year: pd.DataFrame,
                   rounding: str = "none", validate: bool = True, **validate_kwargs) -> pd.DataFrame:
    """Apply one fixed election (fixed rates) to many years of final grid indices, vectorized.

    index_by_year: DataFrame indexed by year with one column per interval (names or codes), on the
    100 scale. Returns a long DataFrame with one row per (year, selected interval): policy
    protection, total/subsidy/producer premium, final index, payment factor, indemnity. Years in
    which an interval index is missing get NaN indemnity for that interval.
    """
    if validate:
        validate_election(election, **validate_kwargs)
    base = policy_table(election, premium_rates, None, rounding=rounding, validate=False)
    idx = index_by_year.rename(columns=lambda c: interval_name(c))
    names = list(base["interval_name"])
    for k in names:
        if k not in idx.columns:
            idx[k] = np.nan
    fi = idx[names].to_numpy(dtype=float)  # years x intervals
    prot = base["policy_protection"].to_numpy()
    if rounding == "official":
        e = election
        ppa = float(dollar_amount_of_protection_per_acre(e.county_base_value, e.coverage_level, e.productivity_factor))
        prot_calc = np.asarray(policy_protection_per_unit(ppa, e.insured_acres, base["percent_of_value"].to_numpy(), e.share))
    else:
        prot_calc = prot
    pcf = np.asarray(payment_calculation_factor(fi, election.trigger, decimals=3 if rounding == "official" else None))
    ind = pcf * prot_calc[None, :]
    if rounding != "none":
        ind = np.asarray(round_half_up(ind, 0))
    years = idx.index.to_numpy()
    n_y, n_i = fi.shape
    out = pd.DataFrame({
        "year": np.repeat(years, n_i),
        "interval_name": np.tile(names, n_y),
        "interval_code": np.tile(base["interval_code"].to_numpy(), n_y),
        "percent_of_value": np.tile(base["percent_of_value"].to_numpy(), n_y),
        "policy_protection": np.tile(prot, n_y),
        "premium_rate": np.tile(base["premium_rate"].to_numpy(), n_y),
        "total_premium": np.tile(base["total_premium"].to_numpy(), n_y),
        "premium_subsidy": np.tile(base["premium_subsidy"].to_numpy(), n_y),
        "producer_premium": np.tile(base["producer_premium"].to_numpy(), n_y),
        "final_index": fi.ravel(),
        "payment_calculation_factor": pcf.ravel(),
        "indemnity": ind.ravel(),
    })
    out.attrs["totals"] = base.attrs["totals"]
    return out


def policy_totals(tables: Iterable[pd.DataFrame], rounding: str = "official") -> dict:
    """Totals for a policy made of several grid/use units (e.g. HB Exhibit 5's four grids).

    Sums unit protection, premium, and indemnity across the tables returned by policy_table. In
    "official" mode the premium subsidy is rounded once on the policy total, as in [HB] Exhibit 5 E
    ($1,114 x 51% = $568; producer pays $546); in "dst"/"none" mode unit subsidies are summed.
    All tables must share one coverage level (one subsidy rate).
    """
    tables = list(tables)
    rates = {t.attrs["totals"]["subsidy_rate"] for t in tables}
    if len(rates) != 1:
        raise ValueError("policy_totals needs tables with a single subsidy rate")
    sub_rate = rates.pop()
    prot = float(sum(t["policy_protection"].sum() for t in tables))
    prem = float(sum(t["total_premium"].sum() for t in tables))
    if rounding == "official":
        sub = float(round_half_up(prem * sub_rate, 0))
    else:
        sub = float(sum(t["premium_subsidy"].sum() for t in tables))
    ind = float(sum(np.nansum(t["indemnity"].to_numpy()) for t in tables))
    return {"policy_protection": prot, "total_premium": prem, "premium_subsidy": sub,
            "producer_premium": prem - sub, "indemnity": ind, "subsidy_rate": sub_rate}


def summarize_years(long: pd.DataFrame) -> pd.DataFrame:
    """Collapse simulate_years output to one row per year (premiums, indemnity, net, loss ratio)."""
    g = long.groupby("year")
    df = pd.DataFrame({
        "policy_protection": g["policy_protection"].sum(),
        "total_premium": g["total_premium"].sum(),
        "premium_subsidy": g["premium_subsidy"].sum(),
        "producer_premium": g["producer_premium"].sum(),
        "indemnity": g["indemnity"].sum(min_count=1),
        "n_intervals_paid": g["indemnity"].apply(lambda s: int((s > 0).sum())),
        "n_intervals_missing": g["final_index"].apply(lambda s: int(s.isna().sum())),
    })
    df["net_to_producer"] = df["indemnity"] - df["producer_premium"]
    df["loss_ratio"] = df["indemnity"] / df["total_premium"]
    return df
