"""Rain-to-loss model: a farm's dollar loss (or gain) versus a normal year, given rainfall.

Design doc and backtest: docs/analysis/13_rain_to_loss_model.md. Calibration comes only from
existing project research; nothing here is newly estimated:

* forage and hay elasticities: data/processed/crop_rain_sensitivity_other.csv, rows
  ``scen_<farm_id>`` (doc 03b section 8), column ``rain_elasticity``;
* dry-vs-wet asymmetry (curvature): the quadratic "+1/-1/-2 in" results stored in the same CSV's
  ``valid_range_note`` (doc 03b numbers table, "Quadratic" entries);
* timing weights: the farm's PRF interval allocation (the weighting the 03b elasticities were
  fitted against), or NRCS growth curves listed in doc 03b's numbers table;
* corn and soybeans: the state monthly-rain regressions of doc 03a (VERIFIED), coefficients in
  data/processed/crop_yield_aux/r1_reestimate_coefficients.csv, normals and prices from
  data/processed/crop_rain_sensitivity_corn_soy.csv, irrigated shares from
  data/processed/crop_yield_aux/r1_irrigation_share_2022.csv.

Sign convention: ``loss_usd > 0`` is a loss versus normal, ``loss_usd < 0`` a gain.

Forage / hay model (per farm, per year)::

    R  = sum_k w_k * I_k / 100          (I_k = interval rain index, 100 = normal; sum_k w_k = 1)
    x  = R - 1                          (relative rain anomaly of the season)
    dP = e * (x + g * x**2)             (fractional production change; g <= 0 makes dry hurt more)
         held flat beyond the vertex x* = -1/(2g) unless excess_penalty=True (saturation),
         and floored at -1 (cannot lose more than the whole crop)
    loss_usd = -dP * value_per_acre * acres * (1 - irrigated_share)

With g = 0 and gains clipped to zero this is exactly the doc-04b forage-loss proxy used in
scripts/run_scenarios.py (``forage_loss_proxy``), which now imports its helpers from here.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

import numpy as np
import pandas as pd
import yaml

from agri_hedge.config import PROCESSED, SCENARIOS
from agri_hedge.prf_intervals import INTERVAL_MONTHS, INTERVAL_NAMES, overlaps

FARMS_YAML = SCENARIOS / "farms.yaml"
SENS_OTHER_CSV = PROCESSED / "crop_rain_sensitivity_other.csv"
SENS_CORN_SOY_CSV = PROCESSED / "crop_rain_sensitivity_corn_soy.csv"
ROWCROP_COEF_CSV = PROCESSED / "crop_yield_aux" / "r1_reestimate_coefficients.csv"
IRRIGATION_CSV = PROCESSED / "crop_yield_aux" / "r1_irrigation_share_2022.csv"

#: Six non-overlapping two-month intervals that tile the calendar year (used for growth weights).
CALENDAR_PAIRS = ["Jan-Feb", "Mar-Apr", "May-Jun", "Jul-Aug", "Sep-Oct", "Nov-Dec"]

#: NASS Crop Values 2025 Summary (Feb 26 2026) p.33, "all other hay" marketing-year price, $/ton.
#: Quoted in doc 03b, "Prices and values" table (CONFIRMED there).
STATE_HAY_PRICE_2025 = {"TX": 136.0, "OK": 90.0, "MO": 114.0, "FL": 120.0, "CO": 151.0, "NM": 184.0}
#: ESD stocking convention: 25% of production is grazed (doc 03b, R067BY002CO, CONFIRMED).
HARVEST_EFFICIENCY = 0.25
LB_PER_TON = 2000.0

#: Monthly growth curves (% of annual growth, Jan..Dec), copied from doc 03b's NRCS ESD numbers
#: table (CONFIRMED there against EDIT / the FSG PDF). "MO_fescue_constructed" is NOT an NRCS
#: curve: no Dade County curve exists in EDIT, so it spreads MU Extension's "two-thirds spring,
#: one-third fall" for tall fescue evenly over Mar-Jun and Sep-Nov (our construction).
GROWTH_CURVES: dict[str, tuple[float, ...]] = {
    "TX5514": (2, 2, 8, 10, 20, 23, 5, 3, 10, 10, 5, 2),
    "TX6011": (1, 2, 2, 18, 23, 17, 6, 4, 16, 6, 3, 2),
    "TX4525": (2, 2, 5, 10, 18, 15, 5, 9, 15, 9, 5, 5),
    "TX5520": (0, 0, 0, 10, 21, 22, 10, 5, 14, 10, 8, 0),
    "OK0001": (0, 1, 5, 10, 20, 30, 10, 5, 10, 6, 2, 1),
    "OK0003": (0, 2, 6, 9, 21, 24, 14, 6, 11, 4, 2, 1),
    "CO6701": (0, 0, 2, 8, 20, 28, 15, 12, 10, 5, 0, 0),
    "CO6709": (0, 0, 2, 7, 25, 35, 15, 10, 5, 1, 0, 0),
    "NM4208": (0, 0, 5, 7, 10, 15, 25, 25, 8, 5, 0, 0),
    "FL_bahiagrass_FSG": (0, 1, 3, 14, 14, 17, 19, 17, 14, 3, 0, 0),
    "MO_fescue_constructed": (0, 0, 100 / 6, 100 / 6, 100 / 6, 100 / 6, 0, 0, 100 / 9, 100 / 9, 100 / 9, 0),
}

#: Which growth curve(s) represent each representative farm (averaged when several).
#: Assignment follows doc 03b section 5 ("Recommended forage-relevant intervals" table).
FARM_GROWTH_CURVES: dict[str, tuple[str, ...]] = {
    "DFW_hay": ("TX5520",),                 # coastal bermudagrass hay/pasture curve, Parker Co.
    "DFW_graze": ("TX5514", "TX6011"),      # Parker Co. rangeland ESD curves
    "SAT_graze": ("TX4525",),
    "OKC_hay": ("OK0001", "OK0003"),
    "OKC_graze": ("OK0001", "OK0003"),
    "SGF_hay": ("MO_fescue_constructed",),
    "SGF_graze": ("MO_fescue_constructed",),
    "DEN_graze": ("CO6701", "CO6709"),
    "ABQ_graze": ("NM4208",),
    "TPA_graze": ("FL_bahiagrass_FSG",),
    "TPA_hay": ("FL_bahiagrass_FSG",),
}

#: Row of crop_rain_sensitivity_other.csv whose quadratic (+1/-1/-2 in) supplies each farm's
#: curvature. Rule (doc 13): the row behind the farm's elasticity where it has a quadratic; else
#: an observed same-county series; else the pooled median of all forage/hay quadratics (None).
FARM_CURVATURE_ROW: dict[str, str | None] = {
    "DFW_hay": "hay_other_TX_state_AprSep",          # same data and window as scen_DFW_hay
    "DFW_graze": "forage_rangeland_TX_Parker_AprJun",  # Grass-Cast, same county
    "SAT_graze": None,                               # no Atascosa series: pooled median
    "OKC_hay": "hay_other_OK_state_AprJun",          # same data as scen_OKC_hay
    "OKC_graze": "hay_other_OK_Grady_AprJun",        # observed Grady hay (Grass-Cast too smooth in OK, 03b)
    "SGF_hay": "hay_other_MO_state_AprJun",          # same data as scen_SGF_hay
    "SGF_graze": "hay_other_MO_state_AprJun",        # same data as scen_SGF_graze
    "DEN_graze": "forage_rangeland_CO_Elbert_AprJul",  # Grass-Cast, good in CO (03b)
    "ABQ_graze": "forage_rangeland_NM_Torrance_JulSep",  # Grass-Cast SW (model only, weak)
    "TPA_graze": "hay_other_FL_state_MarMay",        # not significant; convex, clamps to 0
    "TPA_hay": "hay_other_FL_state_MarMay",
}

#: Rows pooled for the default curvature (every forage/hay quadratic in the CSV except Florida,
#: whose fit is not significant, t = 1.2).
POOLED_CURVATURE_ROWS = (
    "hay_other_TX_state_AprSep", "hay_other_TX_state_AprJun", "hay_other_OK_state_AprJun",
    "hay_other_MO_state_AprJun", "hay_other_OK_Grady_AprJun", "hay_other_TX_Parker_AprJun",
    "forage_rangeland_CO_Elbert_AprJul", "forage_rangeland_OK_Grady_AprJun",
    "forage_rangeland_TX_Parker_AprJun", "forage_rangeland_NM_Torrance_JulSep",
)


# =============================================================================================
# Loading
# =============================================================================================

def load_farms(path: Path | str = FARMS_YAML) -> list[dict]:
    """Farm dicts from farms.yaml (top-level key ``farms``)."""
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    farms = data["farms"] if isinstance(data, dict) else data
    if not farms:
        raise ValueError(f"no farms in {path}")
    return farms


def load_sensitivity(path: Path | str = SENS_OTHER_CSV) -> pd.DataFrame:
    return pd.read_csv(path)


def elasticity_for(ref, sens: pd.DataFrame | None, source_name: str = SENS_OTHER_CSV.name) -> tuple[float, str]:
    """Elasticity of forage value to seasonal rainfall shortfall for a farm (default 1.0).

    Moved here unchanged from scripts/run_scenarios.py: reads the first column whose name
    contains "elastic" in the row whose ``row_key`` equals ``ref``.
    """
    if sens is None or ref in (None, "", "none"):
        return 1.0, "default 1.0 (no sensitivity row)"
    if "row_key" not in sens.columns:
        return 1.0, "default 1.0 (sensitivity file has no row_key column)"
    row = sens[sens["row_key"].astype(str) == str(ref)]
    if row.empty:
        return 1.0, f"default 1.0 (row_key {ref!r} not found)"
    cols = [c for c in sens.columns if "elastic" in c.lower()]
    for c in cols:
        v = pd.to_numeric(row.iloc[0][c], errors="coerce")
        if pd.notna(v):
            return float(abs(v)), f"{source_name} row_key={ref}, column {c}"
    return 1.0, f"default 1.0 (row_key {ref!r} has no numeric elasticity column)"


# =============================================================================================
# Rain inputs: interval indices, timing weights, weighted season index
# =============================================================================================

def interval_index_from_monthly(monthly: pd.DataFrame, normals: Mapping[int, float] | pd.Series,
                                intervals=INTERVAL_NAMES) -> pd.DataFrame:
    """PRF-style interval index (100 = normal) from monthly rain.

    ``monthly``: year x month (columns 1..12) rain totals. ``normals``: month -> normal total, same
    units. Interval index = 100 x (rain in its two months) / (normal of those two months), the
    same construction as the PRF grid index and doc 08's station index.
    """
    out = {}
    for k in intervals:
        m1, m2 = INTERVAL_MONTHS[k]
        den = float(normals[m1]) + float(normals[m2])
        if den <= 0:
            raise ValueError(f"normal rain for {k} must be positive")
        out[k] = 100.0 * (monthly[m1] + monthly[m2]) / den
    return pd.DataFrame(out, index=monthly.index)


def normalize_weights(weights: Mapping[str, float]) -> dict[str, float]:
    """Drop zero weights, check intervals are valid and non-overlapping, rescale to sum 1."""
    w = {str(k): float(v) for k, v in weights.items() if float(v) > 0}
    if not w:
        raise ValueError("timing weights are all zero")
    bad = [k for k in w if k not in INTERVAL_MONTHS]
    if bad:
        raise ValueError(f"unknown interval names: {bad}")
    names = list(w)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if overlaps(a, b):
                raise ValueError(f"timing weights use overlapping intervals {a} and {b}")
    s = sum(w.values())
    return {k: v / s for k, v in w.items()}


def growth_timing_weights(curve: tuple[float, ...] | list[float], lead: bool = True) -> dict[str, float]:
    """Rain-timing weights on the six calendar pairs from a 12-month growth curve.

    With ``lead=True`` (default) rain in month m is credited half to growth in m and half to
    growth in m+1 (rain precedes growth); weight_m = (g_m + g_{m+1}) / 2, December wrapping to
    January. This one-month lead is our assumption (doc 13); it moves weight toward spring, in
    line with doc 03b's finding that Apr-Jun rain predicts forage best.
    """
    g = np.asarray(curve, dtype=float)
    if g.shape != (12,) or g.min() < 0 or g.sum() <= 0:
        raise ValueError("growth curve must be 12 non-negative monthly values")
    g = g / g.sum()
    r = 0.5 * (g + np.roll(g, -1)) if lead else g
    w = {k: float(r[INTERVAL_MONTHS[k][0] - 1] + r[INTERVAL_MONTHS[k][1] - 1]) for k in CALENDAR_PAIRS}
    return normalize_weights(w)


def farm_growth_weights(farm_id: str, lead: bool = True) -> dict[str, float]:
    names = FARM_GROWTH_CURVES.get(farm_id)
    if not names:
        raise KeyError(f"no growth curve assigned to farm {farm_id!r}")
    curve = np.mean([np.asarray(GROWTH_CURVES[n], dtype=float) / sum(GROWTH_CURVES[n]) for n in names], axis=0)
    return growth_timing_weights(curve, lead=lead)


def weighted_index(index_by_year: pd.DataFrame, allocation: Mapping[str, float], cap: float | None = None) -> pd.Series:
    """W = sum of weight x interval index over the weighted intervals (100 = normal).

    Moved here unchanged from scripts/run_scenarios.py. cap=100 caps each interval's index at 100
    before weighting, so a wet interval cannot offset a dry one (the "no-offset" case).
    """
    names = [k for k, v in allocation.items() if v > 0]
    w = np.array([allocation[k] for k in names])
    vals = index_by_year[names].to_numpy(dtype=float)
    if cap is not None:
        vals = np.minimum(vals, cap)
    return pd.Series(vals @ (w / w.sum()), index=index_by_year.index, name="weighted_index")


def forage_loss_proxy(value_per_acre: float, acres: float, seasonal_index, elasticity: float = 1.0):
    """The doc-04b proxy: value_per_acre x acres x max(0, 1 - index/100) x elasticity.

    Moved here unchanged from scripts/run_scenarios.py. Equals ``FarmLossModel`` with zero
    curvature, no irrigation and ``gains=False``.
    """
    s = np.asarray(seasonal_index, dtype=float)
    loss = value_per_acre * acres * np.clip(1.0 - s / 100.0, 0.0, None) * elasticity
    if isinstance(seasonal_index, pd.Series):
        return pd.Series(loss, index=seasonal_index.index)
    return loss


# =============================================================================================
# Response curve: elasticity, asymmetry, saturation / excess-rain penalty
# =============================================================================================

_QUAD_RE = re.compile(r"\+1/-1/-2 in\s*=\s*([+\-]?[\d.]+)\s*/\s*([+\-]?[\d.]+)\s*/\s*([+\-]?[\d.]+)")


def parse_quadratic_note(note: str) -> tuple[float, float, float]:
    """(+1 in, -1 in, -2 in) exact yield changes from a CSV ``valid_range_note``."""
    m = _QUAD_RE.search(str(note))
    if not m:
        raise ValueError("note has no 'exact +1/-1/-2 in = a/b/c' quadratic")
    return float(m.group(1)), float(m.group(2)), float(m.group(3))


def curvature_from_quadratic(y_plus1: float, y_minus1: float, normal_in: float) -> float:
    """Dimensionless curvature g of dP = e (x + g x^2), x = rain / normal - 1.

    A quadratic y(d) = b d + a d^2 in inches d gives a = (y(+1) + y(-1)) / 2 and
    b = (y(+1) - y(-1)) / 2. Writing d = x N (N = window normal, inches) and dividing by the
    linear term, g = (a / b) N. g < 0: a dry inch costs more than a wet inch gains.
    """
    b = 0.5 * (y_plus1 - y_minus1)
    a = 0.5 * (y_plus1 + y_minus1)
    if b <= 0:
        raise ValueError("quadratic has no positive rain response at normal")
    return a / b * float(normal_in)


def curvature_for_row(sens: pd.DataFrame, row_key: str) -> dict:
    """Curvature from one sensitivity-CSV row, with its fit check on the -2 in value."""
    row = sens[sens["row_key"] == row_key]
    if row.empty:
        raise KeyError(f"row_key {row_key!r} not in sensitivity file")
    r = row.iloc[0]
    p1, m1, m2 = parse_quadratic_note(r["valid_range_note"])
    n = float(r["baseline_precip_in"])
    g = curvature_from_quadratic(p1, m1, n)
    b, a = 0.5 * (p1 - m1), 0.5 * (p1 + m1)
    return {"row_key": row_key, "plus1": p1, "minus1": m1, "minus2": m2, "normal_in": n,
            "curvature_raw": g, "minus2_implied": -2 * b + 4 * a}


def pooled_curvature(sens: pd.DataFrame, rows=POOLED_CURVATURE_ROWS) -> float:
    """Median raw curvature over the pooled forage/hay quadratics (default for farms with no data)."""
    return float(np.median([curvature_for_row(sens, k)["curvature_raw"] for k in rows]))


def curvature_for_farm(farm_id: str, sens: pd.DataFrame) -> tuple[float, str]:
    """Curvature g <= 0 for a representative farm, and a source string.

    Positive fitted curvature (wet helps more than dry hurts) contradicts the documented
    direction (doc 03b section 6, doc 03a section 2) and is set to 0 (linear).
    """
    key = FARM_CURVATURE_ROW.get(farm_id, None)
    if key is None:
        g = pooled_curvature(sens)
        src = f"pooled median of {len(POOLED_CURVATURE_ROWS)} forage/hay quadratics"
    else:
        c = curvature_for_row(sens, key)
        g, src = c["curvature_raw"], f"{key} (+1/-1 in = {c['plus1']}/{c['minus1']}, normal {c['normal_in']} in)"
    if g > 0:
        return 0.0, src + f"; fitted {g:+.2f} > 0 clamped to 0"
    return float(g), src


def production_response(x, elasticity: float, curvature: float = 0.0, excess_penalty: bool = False):
    """Fractional production change for relative rain anomaly x = R - 1 (vectorized).

    dP = e (x + g x^2). For g < 0 the curve peaks at x* = -1/(2g); beyond it the response is held
    at its peak (saturation, the forage default) or keeps falling if ``excess_penalty``. dP is
    floored at -1.
    """
    if curvature > 0:
        raise ValueError("curvature must be <= 0 (dry hurts at least as much as wet helps)")
    xa = np.asarray(x, dtype=float)
    if curvature < 0 and not excess_penalty:
        xa = np.minimum(xa, -1.0 / (2.0 * curvature))
    dp = elasticity * (xa + curvature * xa ** 2)
    dp = np.maximum(dp, -1.0)
    if isinstance(x, pd.Series):
        return pd.Series(dp, index=x.index)
    return dp if np.ndim(dp) else float(dp)


# =============================================================================================
# Farm values and irrigation
# =============================================================================================

def state_of(farm: dict) -> str:
    county = str(farm.get("county", ""))
    m = re.search(r",\s*([A-Z]{2})\s*$", county)
    if not m:
        raise ValueError(f"cannot read a state code from county {county!r}")
    return m.group(1)


def value_per_acre(farm: dict, basis: str = "rent") -> float:
    """Dollar value of a normal year's production per acre.

    * ``rent``: farms.yaml ``expected_value_usd_per_acre`` (hay: yield x price; grazing: county
      pasture cash rent). The basis used in docs 03b and 04b.
    * ``replacement``: grazing valued as the hay needed to replace the grazed 25% of production,
      production_lb x 0.25 x state 2025 hay price / 2000 (doc 03b section 7). Hay farms: = rent.
    * ``protection``: county base value x productivity factor (the PRF protection basis; doc 04b
      "cbvpf" variant).
    """
    use = str(farm.get("intended_use", "grazing")).lower()
    if basis == "rent":
        return float(farm["expected_value_usd_per_acre"])
    if basis == "replacement":
        if use != "grazing":
            return float(farm["expected_value_usd_per_acre"])
        lb = float(farm["expected_production"]["value"])
        return lb * HARVEST_EFFICIENCY * STATE_HAY_PRICE_2025[state_of(farm)] / LB_PER_TON
    if basis == "protection":
        return float(farm["county_base_value_usd_per_acre"]) * float(farm.get("productivity_factor", 1.0))
    raise ValueError(f"unknown value basis {basis!r}")


def irrigated_share_of(farm: dict) -> float:
    """Share of the farm's acres that are irrigated (rain-insensitive).

    An explicit ``irrigated_share`` key wins; else ``irrigation_practice`` "irrigated" -> 1.0 and
    anything else (non-irrigated, not specified) -> 0.0. All 11 farms.yaml farms are 0.
    """
    if farm.get("irrigated_share") is not None:
        s = float(farm["irrigated_share"])
    else:
        s = 1.0 if str(farm.get("irrigation_practice", "")).strip().lower() == "irrigated" else 0.0
    if not 0.0 <= s <= 1.0:
        raise ValueError("irrigated_share must be in [0, 1]")
    return s


def irrigated_share_for(state: str, crop: str, path: Path | str = IRRIGATION_CSV) -> float:
    """2022 Census irrigated share of harvested acres for corn or soybeans (doc 03a section 7)."""
    t = pd.read_csv(path)
    col = {"corn": "corn_irrigated_pct", "soybeans": "soybeans_irrigated_pct"}[crop]
    row = t[t["state"].str.upper() == state.upper()]
    if row.empty:
        raise KeyError(f"state {state!r} not in {Path(path).name}")
    return float(row.iloc[0][col]) / 100.0


# =============================================================================================
# The farm model
# =============================================================================================

@dataclass(frozen=True)
class FarmLossModel:
    """Rain-to-loss model for one forage or hay farm. Build with ``build_farm_model``."""

    farm_id: str
    acres: float
    value_per_acre: float
    timing_weights: dict = field(hash=False)
    elasticity: float
    curvature: float = 0.0
    irrigated_share: float = 0.0
    excess_penalty: bool = False
    value_basis: str = "rent"
    timing: str = "allocation"
    elasticity_source: str = ""
    curvature_source: str = ""

    @property
    def normal_value_usd(self) -> float:
        """Value of a normal year's production on the rain-fed acres."""
        return self.value_per_acre * self.acres * (1.0 - self.irrigated_share)

    def season_index(self, interval_index: pd.DataFrame | Mapping[str, float]):
        """Weighted season rain index R x 100 (100 = normal) from interval indices.

        ``interval_index``: year x interval-name DataFrame, or one year's {interval: index}.
        """
        if isinstance(interval_index, Mapping):
            frame = pd.DataFrame([interval_index])
            return float(weighted_index(frame, self.timing_weights).iloc[0])
        return weighted_index(interval_index, self.timing_weights)

    def production_change(self, interval_index):
        """Fractional production change of the rain-fed acres versus normal."""
        s = self.season_index(interval_index)
        return production_response(s / 100.0 - 1.0, self.elasticity, self.curvature, self.excess_penalty)

    def loss_usd(self, interval_index, gains: bool = True):
        """Dollar loss versus normal (> 0 loss, < 0 gain). ``gains=False`` floors it at 0."""
        dp = self.production_change(interval_index)
        loss = -np.asarray(dp, dtype=float) * self.normal_value_usd
        if not gains:
            loss = np.maximum(loss, 0.0)
        if isinstance(dp, pd.Series):
            return pd.Series(loss, index=dp.index, name="loss_usd")
        return float(loss)

    def loss_from_monthly(self, monthly: pd.DataFrame, normals, gains: bool = True):
        """Same as ``loss_usd`` from monthly rain (year x month 1..12) and monthly normals."""
        idx = interval_index_from_monthly(monthly, normals, intervals=list(self.timing_weights))
        return self.loss_usd(idx, gains=gains)

    def table(self, interval_index: pd.DataFrame, gains: bool = True) -> pd.DataFrame:
        s = self.season_index(interval_index)
        dp = production_response(s / 100.0 - 1.0, self.elasticity, self.curvature, self.excess_penalty)
        loss = -dp * self.normal_value_usd
        if not gains:
            loss = loss.clip(lower=0.0)
        return pd.DataFrame({"season_index": s, "production_change": dp, "loss_usd": loss})


def build_farm_model(farm: dict, sens: pd.DataFrame | None = None, timing: str = "allocation",
                     value_basis: str = "rent", curvature: bool | float = True,
                     excess_penalty: bool = False, growth_lead: bool = True) -> FarmLossModel:
    """Build a ``FarmLossModel`` from a farms.yaml entry.

    timing: ``allocation`` (farm's PRF interval allocation; the weighting the 03b elasticities
    were fitted on) or ``growth`` (NRCS growth curve, ``FARM_GROWTH_CURVES``), or pass a dict of
    {interval: weight}. curvature: True = documented curvature for the farm, False = linear, or a
    number (<= 0) to override.
    """
    sens = load_sensitivity() if sens is None else sens
    fid = str(farm["farm_id"])
    e, e_src = elasticity_for(farm.get("rain_sensitivity_ref"), sens)
    if isinstance(timing, Mapping):
        w, tname = normalize_weights(timing), "custom"
    elif timing == "allocation":
        w, tname = normalize_weights(farm["interval_allocation"]), "allocation"
    elif timing == "growth":
        w, tname = farm_growth_weights(fid, lead=growth_lead), "growth"
    else:
        raise ValueError(f"unknown timing {timing!r}")
    if curvature is True:
        g, g_src = curvature_for_farm(fid, sens)
    elif curvature is False:
        g, g_src = 0.0, "linear (curvature off)"
    else:
        g, g_src = float(curvature), "user value"
    return FarmLossModel(farm_id=fid, acres=float(farm["insured_acres"]),
                         value_per_acre=value_per_acre(farm, value_basis), timing_weights=w,
                         elasticity=e, curvature=g, irrigated_share=irrigated_share_of(farm),
                         excess_penalty=excess_penalty, value_basis=value_basis, timing=tname,
                         elasticity_source=e_src, curvature_source=g_src)


# =============================================================================================
# Row crops (corn, soybeans): doc 03a monthly quadratic regressions
# =============================================================================================

_MONTH_TERMS = {"may": (5, "May"), "jun": (6, "June"), "jul": (7, "July"), "aug": (8, "August")}
_STATE_NAME = {"IL": "ILLINOIS", "IN": "INDIANA", "IA": "IOWA"}
_SPEC_MODEL_TYPE = {
    "update 1980-2025": "Tannura et al. specification, yield level (bu/ac)",
    "rain-only 1980-2025": "Tannura et al. specification without temperature terms, yield level (bu/ac)",
}


@dataclass(frozen=True)
class RowCropModel:
    """State monthly-rain yield model for corn or soybeans (doc 03a; temperature held at normal).

    yield change (bu/ac) = sum over months of b1 (r - n) + b2 (r^2 - n^2), with b2 = 0 for the
    linear May and Sep-Apr ("pre") terms. Quadratic months peak at r* = -b1 / (2 b2): rain above
    r* lowers yield (the documented excess-rain penalty), and negative May slopes penalize wet
    planting seasons. Rain is statewide monthly inches, as in the regressions.
    """

    crop: str
    state: str
    spec: str
    coef: dict = field(hash=False)        # term -> coefficient ("may", "jun", "jun2", ..., "pre")
    normals: dict = field(hash=False)     # term -> normal inches ("may", "jun", "jul", "aug", "pre")
    price_usd: float
    trend_yield: float

    def optimum_in(self, term: str) -> float:
        b1, b2 = self.coef.get(term, 0.0), self.coef.get(term + "2", 0.0)
        return -b1 / (2 * b2) if b2 < 0 else math.inf

    def yield_change_bu(self, rain: Mapping[str, float]) -> float:
        """bu/ac change vs normal; ``rain`` maps "may"/"jun"/"jul"/"aug"/"pre" to inches (missing = normal)."""
        total = 0.0
        for term, n in self.normals.items():
            r = float(rain.get(term, n))
            b1, b2 = self.coef.get(term, 0.0), self.coef.get(term + "2", 0.0)
            total += b1 * (r - n) + b2 * (r * r - n * n)
        return total

    def loss_usd(self, rain: Mapping[str, float], acres: float, irrigated_share: float = 0.0,
                 price_usd: float | None = None, farm_trend_yield: float | None = None) -> float:
        """Dollar loss (> 0) or gain (< 0) for a farm; irrigated acres are taken as rain-insensitive.

        ``farm_trend_yield`` scales the state bu/ac change proportionally (constant-% assumption).
        """
        dy = self.yield_change_bu(rain)
        if farm_trend_yield is not None:
            dy *= farm_trend_yield / self.trend_yield
        p = self.price_usd if price_usd is None else price_usd
        return -dy * p * acres * (1.0 - irrigated_share)


def load_rowcrop_model(crop: str, state: str, spec: str = "rain-only 1980-2025",
                       coef_path: Path | str = ROWCROP_COEF_CSV,
                       sens_path: Path | str = SENS_CORN_SOY_CSV) -> RowCropModel:
    """Row-crop model for crop in {"corn", "soybeans"}, state in {"IL", "IN", "IA"}.

    Default spec is the rain-only 1980-2025 re-estimate: doc 03a Implication 3 says to size a
    rain-only hedge on rain-only slopes. "update 1980-2025" holds temperature fixed instead.
    """
    if spec not in _SPEC_MODEL_TYPE:
        raise ValueError(f"spec must be one of {list(_SPEC_MODEL_TYPE)}")
    c = pd.read_csv(coef_path)
    c = c[(c["crop"] == crop) & (c["state"] == state) & (c["spec"] == spec)]
    if c.empty:
        raise KeyError(f"no coefficients for {crop} {state} {spec}")
    coef = {t: float(v) for t, v in zip(c["term"], c["coef"])
            if t in ("pre", "may", "jun", "jun2", "jul", "jul2", "aug", "aug2")}
    s = pd.read_csv(sens_path)
    s = s[(s["crop"].str.lower().str.startswith(crop[:4])) & (s["region"] == state)
          & s["model_type"].str.endswith(_SPEC_MODEL_TYPE[spec])]
    normals = {}
    for term, (_, label) in _MONTH_TERMS.items():
        normals[term] = float(s.loc[s["month_or_window"] == label, "baseline_precip_in"].iloc[0])
    normals["pre"] = float(s.loc[s["month_or_window"].str.startswith("Sep-Apr"), "baseline_precip_in"].iloc[0])
    note = str(s["valid_range_note"].iloc[0])
    m = re.search(r"\(([\d.]+) bu/ac\)", note)
    if not m:
        raise ValueError("cannot read the trend-yield denominator from the CSV note")
    return RowCropModel(crop=crop, state=state, spec=spec, coef=coef, normals=normals,
                        price_usd=float(s["price_usd_per_unit"].iloc[0]), trend_yield=float(m.group(1)))
