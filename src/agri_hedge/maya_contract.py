"""Frozen research contract and offline settlement replay; no exchange, blockchain or oracle."""
from __future__ import annotations

import hashlib
import json
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP

import numpy as np
import pandas as pd

from .compound import sinusoidal_excess


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def make_spec(model_record, county):
    """Freeze saved research parameters. This is a demonstration, not newly validated terms."""
    if model_record["config"]["family"] != "weakest_link":
        raise ValueError("Settlement supports only the fixed weakest-link demonstration")
    a = float(model_record["weights"][0])
    pars = model_record["normalizers"][county["fips"]]
    spec = {"version": "maya-research-v1", "status": "hypothetical offline demonstration",
        "fips": county["fips"], "county": county["county"], "state": county["state"],
        "source": "ACIS NRCC GridData grid=1", "latitude": float(county["lat"]), "longitude": float(county["lon"]),
        "covered_months": [6, 7], "days_required": 61, "fit_end": int(model_record["fit_end"]),
        "rain_trigger_in": float(pars[0]), "heat_trigger_c_days": float(pars[1]),
        "rain_scale_in": float(pars[3]), "heat_scale_c_days": float(pars[4]),
        "heat_threshold_c": 29., "coefficient": a, "maximum_payout_fraction": a,
        "modeled_premium_fraction": float(model_record["premium"]),
        "formula": "E * coefficient * min(clipped drought severity, clipped heat severity)",
        "notional": "declared expected crop value, not verified farm revenue",
        "future_template": {"buy_before": "June 1 observation period starts; historical replay is not a purchase",
            "illustrative_snapshot": "August 15 12:00 UTC of coverage year; not an implemented oracle schedule",
            "missing_data": "pending; do not interpolate or settle as zero",
            "revisions_disputes": "not implemented; no claim of production-ready insurance terms"},
        "limitations": ["No verified counterparty or market quote.", "No chain deployment or oracle truth attestation.",
            "Gridded point weather differs from farm losses and listed airport/TWC settlement sources.",
            "Cents rounding in this Python replay is not a Solidity fixed-point implementation."]}
    return {**spec, "spec_sha256": canonical_hash(spec)}


def verify_spec(spec):
    supplied = dict(spec)
    digest = supplied.pop("spec_sha256", None)
    if digest != canonical_hash(supplied):
        raise ValueError("Contract specification hash mismatch")
    if not (0 < spec["coefficient"] <= .30) or spec["maximum_payout_fraction"] != spec["coefficient"]:
        raise ValueError("Invalid payment coefficient/cap")
    if min(spec["rain_scale_in"], spec["heat_scale_c_days"]) <= 0:
        raise ValueError("Invalid severity scale")


def settle(spec, daily, year, expected_value):
    """Replay a single county's complete season. Hashes document inputs, not their truth."""
    verify_spec(spec)
    notional = Decimal(str(expected_value))
    if not notional.is_finite() or notional <= 0 or notional != notional.quantize(Decimal(".01")):
        raise ValueError("Expected crop value must be positive, finite, with at most two decimal places")
    weather = daily.copy()
    weather["date"] = pd.to_datetime(weather.date)
    expected_dates = pd.date_range(f"{year}-06-01", f"{year}-07-31")
    if "fips" not in weather or not weather.fips.astype(str).eq(spec["fips"]).all():
        raise ValueError("Weather county does not match contract")
    if weather.date.duplicated().any() or len(weather) != len(expected_dates) or set(weather.date) != set(expected_dates):
        raise ValueError("Settlement pending: need every unique June-July date, with no extra dates")
    weather = weather.sort_values("date")
    values = weather[["rain_in", "tmax_f", "tmin_f"]].to_numpy(float)
    if not np.isfinite(values).all() or (values[:, 0] < 0).any() or (values[:, 1] < values[:, 2]).any():
        raise ValueError("Settlement pending: invalid or missing weather")
    rain = float(weather.rain_in.sum())
    heat = float(sinusoidal_excess((weather.tmin_f.to_numpy()-32)*5/9,
                                  (weather.tmax_f.to_numpy()-32)*5/9, spec["heat_threshold_c"]).sum())
    d = float(np.clip((spec["rain_trigger_in"]-rain)/spec["rain_scale_in"], 0, 1))
    h = float(np.clip((heat-spec["heat_trigger_c_days"])/spec["heat_scale_c_days"], 0, 1))
    fraction = spec["coefficient"]*min(d, h)
    input_rows = [{"date": row.date.strftime("%Y-%m-%d"), "rain_in": float(row.rain_in),
                   "tmax_f": float(row.tmax_f), "tmin_f": float(row.tmin_f)} for row in weather.itertuples()]
    cents = int(notional*100)
    collateral = int((Decimal(cents)*Decimal(str(spec["coefficient"]))).to_integral_value(rounding=ROUND_CEILING))
    payout = int((Decimal(cents)*Decimal(str(fraction))).to_integral_value(rounding=ROUND_HALF_UP))
    premium = int((Decimal(cents)*Decimal(str(spec["modeled_premium_fraction"]))).to_integral_value(rounding=ROUND_HALF_UP))
    return {"status": "offline research replay; no money transferred", "year": int(year), "fips": spec["fips"],
        "county": spec["county"], "spec_sha256": spec["spec_sha256"], "weather_sha256": canonical_hash(input_rows),
        "source_truth_verified": False, "expected_value_cents": cents, "observations": len(weather),
        "rain_in": rain, "heat_c_days": heat, "drought_severity": d, "heat_severity": h,
        "payout_fraction": fraction, "modeled_premium_cents": premium,
        "required_mock_collateral_cents": collateral, "payout_cents": min(payout, collateral),
        "unused_mock_collateral_cents": collateral-min(payout, collateral)}
