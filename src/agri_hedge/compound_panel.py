"""Doc 27: pooled parametric corn cover, with temporal and county holdouts.

Hypothetical experimental prices/indices, not a weather forecast or an executable trade.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd
from scipy.optimize import minimize, nnls

from .compound import FOLDS, LIMIT, TRAIN_END, preseason_yields, sinusoidal_excess
from .dairy_validation import protection_metrics

FAMILIES = ("drought", "heat", "rain_two_sided", "additive", "product", "weakest_link", "mixed", "worst_peril")
RIDGES = (0., .01, .10)
REGIMES = ("equal_premium", "cap_only")
PREMIUM = .01
LOAD = .10
WEATHER = ["rain_jun_jul", "heat_dd29", "rain_apr_may"]


def build_panel(counties, yields, daily):
    """Fixed April-July cohort; no weather/yield filling, earlier-only production forecasts."""
    if yields.duplicated(["fips", "year"]).any() or daily.duplicated(["fips", "date"]).any():
        raise ValueError("Duplicate yield year or weather date")
    daily = daily.copy()
    daily["date"] = pd.to_datetime(daily.date)
    rows, audit = [], []
    for county in counties.itertuples(index=False):
        yy = yields[yields.fips == county.fips].set_index("year").yield_bu_ac
        # A missing current outcome must not falsely imply that its earlier-only forecast
        # is unavailable. Keep the missing outcome, while forecasting every study year.
        yy = yy.reindex(range(min(int(yy.index.min()), 1980), 2025))
        baseline = preseason_yields(yy)
        local = daily[daily.fips == county.fips]
        for year in range(1980, 2025):
            weather = local[(local.date.dt.year == year) & local.date.dt.month.isin((4, 5, 6, 7))]
            bad_weather = len(weather) != 122 or not np.isfinite(weather[["rain_in", "tmax_f", "tmin_f"]].to_numpy()).all()
            actual, expected = yy.get(year, np.nan), baseline.get(year, np.nan)
            reasons = []
            if bad_weather:
                reasons.append("incomplete April-July weather")
            if not np.isfinite(actual):
                reasons.append("missing yield")
            if not np.isfinite(expected):
                reasons.append("insufficient earlier baseline")
            audit.append({"fips": county.fips, "county": county.county, "year": year,
                          "complete": not reasons, "reason": "; ".join(reasons)})
            row = {"fips": county.fips, "state": county.state, "county": county.county, "role": county.role,
                   "year": year, "yield_bu_ac": actual, "baseline_bu_ac": expected,
                   "loss_fraction": max(1-actual/expected, 0.) if np.isfinite(actual) and np.isfinite(expected) else np.nan}
            if bad_weather:
                row.update(dict.fromkeys(WEATHER, np.nan))
            else:
                summer = weather[weather.date.dt.month.isin((6, 7))]
                spring = weather[weather.date.dt.month.isin((4, 5))]
                if (weather.rain_in < 0).any():
                    raise ValueError("Negative precipitation")
                row.update(rain_jun_jul=float(summer.rain_in.sum()), rain_apr_may=float(spring.rain_in.sum()),
                    heat_dd29=float(sinusoidal_excess((summer.tmin_f.to_numpy()-32)*5/9,
                                                     (summer.tmax_f.to_numpy()-32)*5/9).sum()))
            rows.append(row)
    return pd.DataFrame(rows), pd.DataFrame(audit)


def common_years(panel, fips, start, end):
    """Identical county-year cohort for all competing policies, never outcome-value screening."""
    valid = panel[panel.year.between(start, end)].dropna(subset=WEATHER+["loss_fraction"])
    groups = [set(valid.loc[valid.fips == county, "year"]) for county in fips]
    return sorted(set.intersection(*groups)) if groups else []


def feature_matrix(d, h, w, family):
    columns = {"drought": [d], "heat": [h], "rain_two_sided": [d, w],
               "additive": [d, h, w], "product": [d*h], "weakest_link": [np.minimum(d, h)],
               "mixed": [d, h, w, d*h], "worst_peril": [np.maximum(d, h)]}
    return np.column_stack(columns[family])


@dataclass(frozen=True)
class Config:
    family: str
    ridge: float
    regime: str = "equal_premium"


@dataclass(frozen=True)
class Model:
    config: Config
    fit_end: int
    normalizers: dict
    weights: tuple
    premium: float
    training_rows: int
    training_years: tuple

    def severities(self, panel):
        pars = np.array([self.normalizers[fips] for fips in panel.fips])
        # Parameter order: drought/heat/wet triggers, then their severity scales.
        r, h, w = [panel[col].to_numpy(float) for col in WEATHER]
        return (np.clip((pars[:, 0]-r)/pars[:, 3], 0, 1),
                np.clip((h-pars[:, 1])/pars[:, 4], 0, 1),
                np.clip((w-pars[:, 2])/pars[:, 5], 0, 1))

    def payout(self, panel):
        return feature_matrix(*self.severities(panel), self.config.family) @ np.asarray(self.weights)

    def record(self):
        return asdict(self)


def fit_model(panel, cutoff, config):
    if config.regime not in REGIMES or config.family not in FAMILIES:
        raise ValueError("Unknown budget regime or payoff family")
    earlier = panel[panel.year <= cutoff]
    normalizers = {}
    for fips, group in earlier.groupby("fips", sort=True):
        group = group.dropna(subset=WEATHER)
        if len(group) < 10:
            raise ValueError(f"Insufficient earlier weather for {fips}")
        values = group[WEATHER].to_numpy(float)
        triggers = [np.quantile(values[:, 0], .5), np.quantile(values[:, 1], .5), np.quantile(values[:, 2], .75)]
        scales = np.maximum(np.quantile(values, .9, axis=0)-np.quantile(values, .1, axis=0), 1e-9)
        normalizers[fips] = tuple(float(v) for v in np.r_[triggers, scales])
    development = sorted(earlier.loc[earlier.role == "development", "fips"].unique())
    years = common_years(earlier, development, 1980, cutoff)
    if len(years) < 10:
        raise ValueError("Insufficient common training years")
    train = earlier[earlier.fips.isin(development) & earlier.year.isin(years)].copy()
    stub = Model(config, cutoff, normalizers, (), 0., len(train), tuple(years))
    x = feature_matrix(*stub.severities(train), config.family)
    y = train.loss_fraction.to_numpy(float)
    xc, yc = x-x.mean(axis=0), y-y.mean()
    n, p = x.shape
    mean = x.mean(axis=0)
    constraints = [{"type": "ineq", "fun": lambda v: LIMIT-v.sum(), "jac": lambda v: -np.ones_like(v)}]
    if config.regime == "equal_premium":
        budget = PREMIUM/(1+LOAD)
        if LIMIT*max(mean) < budget-1e-12:
            raise ValueError(f"Infeasible equal premium for {config.family}")
        initial = np.zeros(p)
        initial[np.argmax(mean)] = budget/max(mean)
        constraints.append({"type": "eq", "fun": lambda v: mean @ v-budget, "jac": lambda v: mean})
    else:
        initial = nnls(np.vstack([xc, np.sqrt(n*config.ridge)*np.eye(p)]), np.r_[yc, np.zeros(p)])[0]
        if initial.sum() > LIMIT:
            initial *= LIMIT/initial.sum()
    def objective(v):
        error = xc @ v-yc
        return float(np.mean(error*error)+config.ridge*(v @ v))
    def gradient(v):
        return 2*(xc.T @ (xc @ v-yc)/n+config.ridge*v)
    result = minimize(objective, initial, jac=gradient, bounds=[(0., LIMIT)]*p,
        constraints=constraints, method="SLSQP", options={"ftol": 1e-12, "maxiter": 400})
    if not result.success:
        raise RuntimeError(f"{config}: {result.message}")
    weights = np.maximum(result.x, 0.)
    if weights.sum() > LIMIT+1e-8:
        raise RuntimeError("Payout cap violated")
    if config.regime == "equal_premium" and abs(mean @ weights-budget) > 1e-8:
        raise RuntimeError("Equal-premium constraint violated")
    return Model(config, cutoff, normalizers, tuple(float(v) for v in weights),
                 float((1+LOAD)*(mean @ weights)), len(train), tuple(years))


def metrics(loss, payout, premium):
    y, p = np.asarray(loss, float), np.asarray(payout, float)
    cost = np.broadcast_to(np.asarray(premium, float), y.shape)
    out = protection_metrics(y, p, cost)
    base = float(np.mean(y*y))
    out["net_error_skill"] = 1-float(np.mean((y-p+cost)**2))/base if base > 0 else np.nan
    out["net_rmse_fraction"] = float(np.sqrt(np.mean((y-p+cost)**2)))
    out["mean_overpayment_fraction"] = float(np.maximum(p-y, 0).mean())
    return out


def select_family(panel, family, regime):
    """Only development-county losses through 2009 are used to fit/select a policy."""
    earlier = panel[panel.year <= TRAIN_END]
    development = sorted(earlier.loc[earlier.role == "development", "fips"].unique())
    scores = []
    for ridge in RIDGES:
        losses, payouts, costs, validation_years = [], [], [], []
        config = Config(family, ridge, regime)
        feasible = True
        for cutoff, start, end in FOLDS:
            try:
                model = fit_model(earlier, cutoff, config)
            except ValueError as exc:
                if "Infeasible equal premium" not in str(exc):
                    raise
                feasible = False
                break
            years = common_years(earlier, development, start, end)
            validation = earlier[earlier.fips.isin(development) & earlier.year.isin(years)]
            losses.extend(validation.loss_fraction)
            payouts.extend(model.payout(validation))
            costs.extend([model.premium]*len(validation))
            validation_years.extend(years)
        score = metrics(losses, payouts, costs)["net_error_skill"] if feasible else -np.inf
        scores.append({**asdict(config), "cv_net_error_skill": score, "feasible": feasible,
                       "validation_rows": len(losses), "validation_years": len(set(validation_years))})
    best = max(scores, key=lambda row: row["cv_net_error_skill"])
    model = fit_model(earlier, TRAIN_END, Config(family, best["ridge"], regime)) if best["feasible"] else None
    return model, pd.DataFrame(scores), best


def paired_year_interval(frame, other=None, repetitions=4000, seed=473):
    """Conditional net-error-skill interval, resampling whole matched years across counties."""
    frame = frame.sort_values(["year", "fips"])
    years = sorted(frame.year.unique())
    counties = sorted(frame.fips.unique())
    expected = pd.MultiIndex.from_product([years, counties], names=["year", "fips"])
    def array(data, col):
        return data.set_index(["year", "fips"])[col].reindex(expected).to_numpy(float).reshape(len(years), len(counties))
    y, p, cost = [array(frame, col) for col in ("loss_fraction", "payout_fraction", "premium_fraction")]
    if not np.isfinite(np.array([y, p, cost])).all():
        raise ValueError("Need a complete matched county-year rectangle")
    rng = np.random.default_rng(seed)
    take = rng.integers(0, len(years), size=(repetitions, len(years)))
    denominator = np.mean(y[take]**2, axis=(1, 2))
    valid = denominator > 1e-15
    values = 1-np.mean((y-p+cost)[take]**2, axis=(1, 2))[valid]/denominator[valid]
    if other is not None:
        other = other.sort_values(["year", "fips"])
        if not other[["year", "fips"]].reset_index(drop=True).equals(frame[["year", "fips"]].reset_index(drop=True)):
            raise ValueError("Reference must have exactly the same county-years")
        if not np.allclose(array(other, "loss_fraction"), y):
            raise ValueError("Reference must have the same losses")
        op, oc = array(other, "payout_fraction"), array(other, "premium_fraction")
        base = 1-np.mean((y-op+oc)[take]**2, axis=(1, 2))[valid]/denominator[valid]
        values -= base
    return np.quantile(values, [.025, .975]).tolist() if len(values) else [np.nan, np.nan]


def primitive_basis(d, h, w):
    """Synthetic, signed-position static spanning diagnostic; includes a cash/intercept term."""
    return np.column_stack([np.ones(len(d))] + [z > strike for z in (d, h, w) for strike in (.10, .25, .50, .75)])


def fit_primitive_approximation(model, training):
    x = primitive_basis(*model.severities(training))
    return np.linalg.lstsq(x, model.payout(training), rcond=None)[0]
