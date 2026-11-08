"""Exploratory compound corn cover, with temporal tuning frozen before final evaluation.

Doc 26 specifies the experiment. Payoffs/premiums are hypothetical, not executable quotes.
County yield shortfalls include all causes and do not identify farm-level weather damage.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from itertools import product

import numpy as np
import pandas as pd
from scipy.optimize import minimize, nnls

from .dairy_validation import protection_metrics

WINDOWS = {"jul": (7,), "jun_jul": (6, 7), "jun_aug": (6, 7, 8)}
FAMILIES = ("rain", "heat", "additive", "product", "weakest_link", "mixed", "worst_peril")
PAIRS = {"station": ("ord", "mdw"), "area": ("div", "kane")}
FOLDS = ((1994, 1995, 1999), (1999, 2000, 2004), (2004, 2005, 2009))
TRAIN_END = 2009
LIMIT = .30


def sinusoidal_excess(tmin_c, tmax_c, threshold=29.):
    """Daily mean degrees above threshold under a sinusoidal within-day temperature.

    Analytic integral over one day, not simply positive Tmax minus the threshold.
    """
    low, high = np.broadcast_arrays(np.asarray(tmin_c, float), np.asarray(tmax_c, float))
    if not np.isfinite(low).all() or not np.isfinite(high).all() or (low > high).any():
        raise ValueError("Need finite minimum <= maximum temperatures")
    mean, amplitude = (low + high) / 2, (high - low) / 2
    z = np.divide(threshold - mean, amplitude, out=np.zeros_like(mean), where=amplitude > 0)
    z = np.clip(z, -1, 1)
    mixed = ((mean - threshold) * np.arccos(z) + amplitude * np.sqrt(1 - z*z)) / np.pi
    return np.where(threshold >= high, 0., np.where(threshold <= low, mean - threshold, mixed))


def preseason_yields(yields: pd.Series, window=20, minimum=15) -> pd.Series:
    """Rolling linear production forecasts: current and later yields never enter a forecast."""
    if not yields.index.is_unique:
        raise ValueError("Duplicate yield years")
    available = yields.dropna().sort_index().astype(float)
    if not np.isfinite(available).all() or (available <= 0).any():
        raise ValueError("Need finite positive observed yields")
    result = pd.Series(np.nan, index=yields.index, dtype=float)
    for year in result.index:
        past = available[available.index < year].tail(window)
        if len(past) >= minimum:
            x = past.index.to_numpy(float) - year
            _, expected = np.linalg.lstsq(np.column_stack([x, np.ones(len(x))]), past, rcond=None)[0]
            if expected > 0:
                result.loc[year] = float(expected)
    return result


def build_panel(yields: pd.DataFrame, rain: pd.DataFrame, daily: pd.DataFrame):
    """One complete common cohort for all families, windows and signal pairs; no imputation."""
    daily = daily.copy()
    daily["date"] = pd.to_datetime(daily.date)
    if daily.date.duplicated().any() or rain.year.duplicated().any():
        raise ValueError("Duplicate weather date/year")
    yields = yields.set_index("year").corn_yield
    expected = preseason_yields(yields)
    rain = rain.set_index("year")
    temperatures = [f"{site}_t{extreme}_f" for site in ("mdw", "kane") for extreme in ("min", "max")]
    rain_cols = [f"{site}_{month}_in" for site in ("ord", "div") for month in ("jun", "jul", "aug")]
    rows, audit = [], []
    for year in range(1980, 2026):
        weather = daily[(daily.date.dt.year == year) & daily.date.dt.month.isin((6, 7, 8))].copy()
        reasons = []
        if len(weather) != 92 or not np.isfinite(weather[temperatures].to_numpy()).all():
            reasons.append("incomplete June-August temperature")
        if year not in rain.index or not np.isfinite(rain.loc[year, rain_cols].to_numpy(float)).all():
            reasons.append("incomplete June-August rain")
        actual, baseline = yields.get(year, np.nan), expected.get(year, np.nan)
        if not np.isfinite(actual):
            reasons.append("missing observed corn yield")
        if not np.isfinite(baseline):
            reasons.append("insufficient earlier yield baseline")
        audit.append({"year": year, "included": not reasons, "reason": "; ".join(reasons)})
        if reasons:
            continue
        row = {"year": year, "corn_yield_bu_ac": actual, "baseline_bu_ac": baseline,
               "loss_fraction": max(1 - actual / baseline, 0.)}
        for site in ("mdw", "kane"):
            low = (weather[f"{site}_tmin_f"].to_numpy() - 32) * 5/9
            high = (weather[f"{site}_tmax_f"].to_numpy() - 32) * 5/9
            weather[f"{site}_dd29"] = sinusoidal_excess(low, high)
        for pair, (rain_site, heat_site) in PAIRS.items():
            for window, months in WINDOWS.items():
                month_names = {6: "jun", 7: "jul", 8: "aug"}
                row[f"{pair}_{window}_rain"] = sum(rain.loc[year, f"{rain_site}_{month_names[m]}_in"] for m in months)
                row[f"{pair}_{window}_heat"] = weather.loc[weather.date.dt.month.isin(months), f"{heat_site}_dd29"].sum()
        rows.append(row)
    return pd.DataFrame(rows), pd.DataFrame(audit)


@dataclass(frozen=True)
class Config:
    family: str
    window: str
    rain_q: float
    heat_q: float
    ridge: float


def candidates(family):
    if family not in FAMILIES:
        raise ValueError(f"Unknown family: {family}")
    # Omit unused trigger searches rather than inflate a single-peril family's trial count.
    rain_q = (.5,) if family == "heat" else (.25, .5, .75)
    heat_q = (.5,) if family == "rain" else (.25, .5, .75)
    return [Config(family, w, r, h, a) for w, r, h, a in product(WINDOWS, rain_q, heat_q, (0., .01, .10))]


def features(drought, heat, family):
    d, h = np.broadcast_arrays(np.asarray(drought, float), np.asarray(heat, float))
    columns = {"rain": [d], "heat": [h], "additive": [d, h], "product": [d*h],
               "weakest_link": [np.minimum(d, h)], "mixed": [d, h, d*h],
               "worst_peril": [np.maximum(d, h)]}
    return np.column_stack(columns[family])


@dataclass(frozen=True)
class Model:
    config: Config
    pair: str
    rain_trigger: float
    heat_trigger: float
    rain_scale: float
    heat_scale: float
    weights: tuple[float, ...]

    def severities(self, panel):
        rain = panel[f"{self.pair}_{self.config.window}_rain"].to_numpy(float)
        heat = panel[f"{self.pair}_{self.config.window}_heat"].to_numpy(float)
        return (np.clip((self.rain_trigger - rain) / self.rain_scale, 0, 1),
                np.clip((heat - self.heat_trigger) / self.heat_scale, 0, 1))

    def payout(self, panel):
        return features(*self.severities(panel), self.config.family) @ np.asarray(self.weights)

    def record(self):
        return asdict(self)


def fit_model(panel, pair, config):
    if len(panel) < 10:
        raise ValueError("Need at least ten earlier observations")
    r = panel[f"{pair}_{config.window}_rain"].to_numpy(float)
    h = panel[f"{pair}_{config.window}_heat"].to_numpy(float)
    rscale = max(float(np.quantile(r, .9) - np.quantile(r, .1)), 1e-9)
    hscale = max(float(np.quantile(h, .9) - np.quantile(h, .1)), 1e-9)
    model = Model(config, pair, float(np.quantile(r, config.rain_q)),
                  float(np.quantile(h, config.heat_q)), rscale, hscale, ())
    x = features(*model.severities(panel), config.family)
    y = panel.loss_fraction.to_numpy(float)
    xc, yc = x - x.mean(axis=0), y - y.mean()
    n, p = x.shape
    weights = nnls(np.vstack([xc, np.sqrt(n*config.ridge) * np.eye(p)]),
                   np.r_[yc, np.zeros(p)])[0]
    if weights.sum() > LIMIT:
        def objective(w):
            err = xc @ w - yc
            return float(np.mean(err*err) + config.ridge * (w @ w))
        def gradient(w):
            return 2 * (xc.T @ (xc @ w - yc) / n + config.ridge*w)
        result = minimize(objective, weights * LIMIT / weights.sum(), jac=gradient,
            method="SLSQP", bounds=[(0., LIMIT)]*p,
            constraints=[{"type": "ineq", "fun": lambda w: LIMIT - w.sum(),
                          "jac": lambda w: -np.ones_like(w)}],
            options={"ftol": 1e-12, "maxiter": 300})
        if not result.success:
            raise RuntimeError(result.message)
        weights = np.maximum(result.x, 0.)
        if weights.sum() > LIMIT:
            weights *= LIMIT / weights.sum()
    return Model(config, pair, model.rain_trigger, model.heat_trigger, rscale, hscale, tuple(weights))


def earlier_premiums(panel, model, loading=.10):
    """Expanding earlier weather under frozen parameters, excluding the current year."""
    payout, years = model.payout(panel), panel.year.to_numpy()
    return np.array([payout[years < y].mean() * (1 + loading)
                     if (years < y).any() else np.nan for y in years])


def select_family(panel, pair, family):
    """Select solely on 1980-2009 temporal validation; final-test rows never enter fitting."""
    earlier = panel[panel.year <= TRAIN_END].copy()
    scores = []
    for config in candidates(family):
        losses, payouts, premiums = [], [], []
        for fit_end, start, end in FOLDS:
            train = earlier[earlier.year <= fit_end]
            validation = earlier[earlier.year.between(start, end)]
            model = fit_model(train, pair, config)
            period = earlier[earlier.year <= end]
            select = period.year.between(start, end).to_numpy()
            losses.extend(validation.loss_fraction)
            payouts.extend(model.payout(period)[select])
            premiums.extend(earlier_premiums(period, model)[select])
        metrics = protection_metrics(losses, payouts, premiums)
        scores.append({**asdict(config), "pair": pair, "cv_he_net": metrics["he_net"],
                       "cv_he_gross": metrics["he_gross"], "cv_years": len(losses)})
    # Stable predeclared enumeration resolves exact ties without looking at test performance.
    best = max(range(len(scores)), key=lambda i: scores[i]["cv_he_net"])
    return fit_model(earlier, pair, candidates(family)[best]), pd.DataFrame(scores), scores[best]


def net_he_interval(loss, payout, premium, reference=None, seed=473, repetitions=4000):
    """Paired-year fixed-fit bootstrap; optional difference vs another (payout,premium)."""
    y, p, c = map(lambda a: np.asarray(a, float), (loss, payout, premium))
    rng = np.random.default_rng(seed)
    take = rng.integers(0, len(y), (repetitions, len(y)))
    variance = np.var(y[take], axis=1)
    valid = variance > 1e-15
    values = 1 - np.var((y-p+c)[take], axis=1)[valid] / variance[valid]
    if reference is not None:
        rp, rc = map(lambda a: np.asarray(a, float), reference)
        base = 1 - np.var((y-rp+rc)[take], axis=1)[valid] / variance[valid]
        values -= base
    return np.quantile(values, [.025, .975]).tolist() if len(values) else [np.nan, np.nan]
