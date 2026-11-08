"""Doc 28: diagnostics of frozen policies, not new crop-model fitting or causal inference."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import minimize, nnls

from .compound import FOLDS

BASELINES = ("original_20_linear", "diagnostic_10_linear", "diagnostic_20_loglinear", "diagnostic_5_mean")
REPLICA_BASES = ("local_continuous", "local_ladders", "chicago_rain", "chicago_rain_hypothetical_heat")
REPLICA_RIDGES = (.01, .10, 1.)
HEAT_STRIKES_F = (80, 85, 90, 95, 100)


def earlier_baselines(yields, target_years):
    """Fixed sensitivity forecasts. None is selected using the diagnosed loss/payout score."""
    series = yields.dropna().sort_index().astype(float)
    if not series.index.is_unique or not np.isfinite(series).all() or (series <= 0).any():
        raise ValueError("Need unique positive yield observations")
    rows = []
    for year in target_years:
        previous = series[series.index < year]
        for name, window, minimum, logarithm in ((BASELINES[0], 20, 15, False),
            (BASELINES[1], 10, 8, False), (BASELINES[2], 20, 15, True), (BASELINES[3], 5, 5, False)):
            past = previous.tail(window)
            value = np.nan
            if len(past) >= minimum:
                if name.endswith("mean"):
                    value = float(past.mean())
                else:
                    x = past.index.to_numpy(float)-year
                    target = np.log(past.to_numpy()) if logarithm else past.to_numpy()
                    _, intercept = np.linalg.lstsq(np.column_stack([x, np.ones(len(x))]), target, rcond=None)[0]
                    value = float(np.exp(intercept) if logarithm else intercept)
                    if value <= 0:
                        value = np.nan
            actual = series.get(year, np.nan)
            rows.append({"year": year, "method": name, "expected_bu_ac": value,
                         "loss_fraction": max(1-actual/value, 0.) if np.isfinite(actual) and np.isfinite(value) else np.nan})
    return pd.DataFrame(rows)


def payment_reason(drought, heat, loss, payout):
    """Mechanical explanation only: it says nothing about what caused the crop shortfall."""
    if drought <= 0 and heat <= 0:
        return "neither drought nor heat trigger met"
    if drought <= 0:
        return "drought trigger not met; joint payment is zero"
    if heat <= 0:
        return "heat trigger not met; joint payment is zero"
    if min(drought, heat) < .10:
        return "both met, but smaller severity is weak"
    if payout < loss:
        return "both met; budget-sized payment is below shortfall"
    return "payment meets or exceeds forecast shortfall"


def replica_basis(frame, name, rain_strikes=range(1, 8)):
    d, h = frame.drought.to_numpy(), frame.heat.to_numpy()
    arrays, labels = [], []
    if name == "local_continuous":
        return np.column_stack([d, h]), ["hypothetical_local_D", "hypothetical_local_H"]
    if name == "local_ladders":
        for variable, values in (("D", d), ("H", h)):
            for strike in (.10, .25, .50, .75):
                yes = (values > strike).astype(float)
                arrays.extend([yes, 1-yes])
                labels.extend([f"synthetic_{variable}_gt_{strike}_YES", f"synthetic_{variable}_gt_{strike}_NO"])
    elif name in ("chicago_rain", "chicago_rain_hypothetical_heat"):
        for month in ("jun", "jul"):
            for strike in rain_strikes:
                yes = (frame[f"ord_{month}_in"].to_numpy() > strike).astype(float)
                arrays.extend([yes, 1-yes])
                labels.extend([f"unlisted_{month}_ORD_gt_{strike}_YES", f"unlisted_{month}_ORD_gt_{strike}_NO"])
        if name.endswith("hypothetical_heat"):
            for strike in HEAT_STRIKES_F:
                yes = frame[f"mdw_days_gt_{strike}"].to_numpy()/61
                arrays.extend([yes, 1-yes])
                labels.extend([f"invented_MDW_daily_gt_{strike}_YES_mean", f"invented_MDW_daily_gt_{strike}_NO_mean"])
    else:
        raise ValueError("Unknown primitive basis")
    return np.column_stack(arrays), labels


@dataclass(frozen=True)
class Replica:
    basis: str
    ridge: float
    weights: tuple
    labels: tuple
    modeled_premium_fraction: float
    maximum_fraction_bound: float

    def payout(self, frame):
        return replica_basis(frame, self.basis)[0] @ np.asarray(self.weights)


def fit_replica(frame, basis, ridge, maximum):
    """Long-only funded approximation to a target payment; never reads crop loss labels."""
    x, labels = replica_basis(frame, basis)
    y = frame.payout_fraction.to_numpy(float)
    n, p = x.shape
    initial = nnls(np.vstack([x, np.sqrt(n*ridge)*np.eye(p)]), np.r_[y, np.zeros(p)])[0]
    if initial.sum() > maximum:
        initial *= maximum/initial.sum()
    def objective(w):
        return float(np.mean((x @ w-y)**2)+ridge*(w @ w))
    def gradient(w):
        return 2*(x.T @ (x @ w-y)/n+ridge*w)
    result = minimize(objective, initial, jac=gradient, method="SLSQP", bounds=[(0., maximum)]*p,
        constraints=[{"type": "ineq", "fun": lambda w: maximum-w.sum(), "jac": lambda w: -np.ones_like(w)}],
        options={"ftol": 1e-12, "maxiter": 400})
    if not result.success or result.x.sum() > maximum+1e-8:
        raise RuntimeError(f"Replica constraint/solver failure: {result.message}")
    weights = tuple(float(v) for v in np.maximum(result.x, 0.))
    price = float(1.10*np.mean(x @ np.asarray(weights)))
    return Replica(basis, ridge, weights, tuple(labels), price, maximum)


def select_replica(frame, basis, maximum):
    earlier = frame[frame.year <= 2009]
    scores = []
    for ridge in REPLICA_RIDGES:
        squared = []
        for cutoff, start, end in FOLDS:
            train, validation = earlier[earlier.year <= cutoff], earlier[earlier.year.between(start, end)]
            model = fit_replica(train, basis, ridge, maximum)
            squared.extend((model.payout(validation)-validation.payout_fraction.to_numpy())**2)
        scores.append({"basis": basis, "ridge": ridge, "cv_target_mse": float(np.mean(squared)),
                       "validation_years": len(squared)})
    best = min(scores, key=lambda x: x["cv_target_mse"])
    return fit_replica(earlier, basis, best["ridge"], maximum), pd.DataFrame(scores)


def payoff_metrics(target, replica):
    target, replica = np.asarray(target, float), np.asarray(replica, float)
    variance = np.var(target)
    return {"target_rmse_fraction": float(np.sqrt(np.mean((target-replica)**2))),
            "target_bias_fraction": float(np.mean(replica-target)),
            "payoff_replication_he": 1-float(np.var(target-replica))/variance if variance else np.nan,
            "maximum_observed_error_fraction": float(np.max(np.abs(target-replica)))}
