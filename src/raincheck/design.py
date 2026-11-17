"""Contract design beyond the fixed shapes (doc 24).

Doc 23 priced a menu of payoff shapes per $1 of maximum payout. Three questions were left open:

1. **Equal premium.** Convex shapes are cheaper per $1 of maximum payout, so comparing them at the
   same maximum payout flatters their fillability. `equal_premium_scale` rescales any shape so its
   fair premium matches a reference shape's; the study (scripts/run_exotic_design.py) redoes the
   depth-capped fits at that size.
2. **Holdout term sheet.** The exchange-settled term sheet of doc 23 averages the shape within each
   rain bin over all years. `split_years` + `exotic.binned_values` on the training years give a term
   sheet that is scored on years it never saw.
3. **The utility-optimal payout.** Which step function on the station's ladder should a risk-averse
   farmer buy, given the joint history of station bins and farm losses? This is the index-insurance
   design problem of Raviv (1979) and Zhang, Tan and Weng (2019, ASTIN Bulletin 49): maximize the
   insured's expected utility over indemnity schedules priced with a proportional load. With CRRA
   utility the problem is concave in the bin payouts, so `optimal_step_payout` solves it directly.
   `scale_for_utility` gives the best size of a *fixed* shape for the same farmer, and the ratio of
   certainty-equivalent gains says how much of the optimum each off-the-shelf shape captures.

Conventions: losses and payouts are per $1 of the insured value (the month's protection); wealth is
`wealth` dollars per $1 of insured value (default 2: half the farmer's wealth rides on the month);
the premium is (1 + load) x fair premium, with the fair premium the historical bin frequencies times
the bin payouts (the climatological price of the replicating NO/YES portfolio).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize, minimize_scalar

DEFAULT_GAMMA = 2.0        # relative risk aversion; 1 = log, 4 = very risk averse
DEFAULT_LOAD = 0.2         # Kalshi all-in cost per $1 of expected payout is 1.1-1.3 (docs 09, 23)
DEFAULT_WEALTH = 2.0       # wealth per $1 of insured value
MAX_PAYOUT_PER_DOLLAR = 1.5   # a bin may pay at most 150% of the insured value (keeps wealth positive)
_W_FLOOR = 1e-6


# ---------------------------------------------------------------------------------------------
# utility
# ---------------------------------------------------------------------------------------------

def crra_utility(w, gamma: float) -> np.ndarray:
    w = np.maximum(np.asarray(w, dtype=float), _W_FLOOR)
    if abs(gamma - 1.0) < 1e-12:
        return np.log(w)
    return (w ** (1.0 - gamma) - 1.0) / (1.0 - gamma)


def crra_marginal(w, gamma: float) -> np.ndarray:
    w = np.maximum(np.asarray(w, dtype=float), _W_FLOOR)
    return w ** (-gamma)


def certainty_equivalent(w, gamma: float) -> float:
    """The sure wealth that gives the same expected CRRA utility as the wealth draws `w`."""
    eu = float(np.mean(crra_utility(w, gamma)))
    if abs(gamma - 1.0) < 1e-12:
        return float(np.exp(eu))
    return float((1.0 + (1.0 - gamma) * eu) ** (1.0 / (1.0 - gamma)))


# ---------------------------------------------------------------------------------------------
# bins and premiums
# ---------------------------------------------------------------------------------------------

def bin_frequencies(bins, n_bins: int) -> np.ndarray:
    """Share of years in each bin (the climatological price of $1 paid in that bin)."""
    b = np.asarray(bins, dtype=int)
    return np.bincount(b, minlength=n_bins)[:n_bins] / max(len(b), 1)


def fair_premium(values, freq) -> float:
    return float(np.asarray(freq, float) @ np.asarray(values, float))


def equal_premium_scale(values, freq, target_premium: float) -> float:
    """Multiplier that gives the step payout `values` the fair premium `target_premium`."""
    fp = fair_premium(values, freq)
    return float(target_premium / fp) if fp > 0 else float("nan")


def split_years(years, cut: int = 2000) -> tuple[np.ndarray, np.ndarray]:
    """Boolean masks (train: year <= cut, test: year > cut) for the holdout term sheet."""
    y = np.asarray(years, dtype=int)
    return y <= cut, y > cut


# ---------------------------------------------------------------------------------------------
# the utility-optimal step payout
# ---------------------------------------------------------------------------------------------

@dataclass
class OptimalPayout:
    values: np.ndarray        # payout per $1 of insured value, one entry per rain bin
    freq: np.ndarray          # bin frequencies used to price it
    gamma: float
    load: float
    wealth: float
    ce_without: float         # certainty equivalent per $1 of insured value with no insurance
    ce_with: float            # with the contract, net of premium
    converged: bool

    @property
    def fair_premium(self) -> float:
        return fair_premium(self.values, self.freq)

    @property
    def premium(self) -> float:
        return (1.0 + self.load) * self.fair_premium

    @property
    def ce_gain(self) -> float:
        """Certainty-equivalent gain per $1 of insured value (what the farmer would pay for the cover)."""
        return self.ce_with - self.ce_without

    @property
    def max_payout(self) -> float:
        return float(self.values.max()) if len(self.values) else 0.0

    @property
    def shape(self) -> np.ndarray:
        """The step function per $1 of maximum payout (what `exotic.span_step` wants)."""
        m = self.max_payout
        return self.values / m if m > 0 else self.values.copy()


def _wealth(loss, bins, values, load, freq, wealth):
    prem = (1.0 + load) * fair_premium(values, freq)
    return wealth - loss + values[bins] - prem


def optimal_step_payout(loss, bins, n_bins: int, gamma: float = DEFAULT_GAMMA, load: float = DEFAULT_LOAD,
                        wealth: float = DEFAULT_WEALTH, premium: float | None = None,
                        freq=None) -> OptimalPayout:
    """Expected-utility-maximizing payout per rain bin for a CRRA farmer.

    loss: the farmer's loss per $1 of insured value by year (0 = normal year); bins: the station's
    rain bin for the same years (0 = at or below the lowest strike). Payouts are non-negative and at
    most MAX_PAYOUT_PER_DOLLAR per bin. With `premium` the loaded premium is fixed at that amount
    (a budget); otherwise the farmer also chooses how much to spend. `freq` overrides the bin
    frequencies used for pricing (e.g. a training sample's).
    """
    loss = np.asarray(loss, dtype=float)
    bins = np.asarray(bins, dtype=int)
    ok = ~np.isnan(loss) & (bins >= 0) & (bins < n_bins)
    loss, bins = loss[ok], bins[ok]
    fr = bin_frequencies(bins, n_bins) if freq is None else np.asarray(freq, float)
    n = len(loss)
    base = wealth - loss
    ce0 = certainty_equivalent(base, gamma)
    if n == 0 or np.all(loss <= 0):
        vals = np.zeros(n_bins)
        return OptimalPayout(vals, fr, gamma, load, wealth, ce0, ce0, True)
    onehot = np.zeros((n, n_bins))
    onehot[np.arange(n), bins] = 1.0
    price = (1.0 + load) * fr                       # premium per $1 paid in each bin

    def neg_eu(p):
        w = base + onehot @ p - price @ p
        pen = np.sum(np.minimum(w - _W_FLOOR, 0.0) ** 2)      # keeps wealth positive
        return -float(np.mean(crra_utility(w, gamma))) + 1e3 * pen

    def grad(p):
        w = base + onehot @ p - price @ p
        mu = crra_marginal(w, gamma) / n
        g = -(onehot.T @ mu) + price * mu.sum()
        viol = np.minimum(w - _W_FLOOR, 0.0)
        g = g + 1e3 * 2.0 * ((onehot.T @ viol) - price * viol.sum())
        return g

    start = np.array([float(np.mean(loss[bins == j])) if (bins == j).any() else 0.0 for j in range(n_bins)])
    start = np.clip(start, 0.0, MAX_PAYOUT_PER_DOLLAR)
    bounds = [(0.0, MAX_PAYOUT_PER_DOLLAR)] * n_bins
    if premium is None:
        res = minimize(neg_eu, start, jac=grad, method="L-BFGS-B", bounds=bounds,
                       options={"maxiter": 2000, "ftol": 1e-14, "gtol": 1e-10})
    else:
        cons = [{"type": "eq", "fun": lambda p: price @ p - premium, "jac": lambda p: price}]
        s0 = start * (premium / (price @ start)) if price @ start > 0 else start
        res = minimize(neg_eu, np.clip(s0, 0, MAX_PAYOUT_PER_DOLLAR), jac=grad, method="SLSQP", bounds=bounds,
                       constraints=cons, options={"maxiter": 500, "ftol": 1e-12})
    vals = np.where(res.x < 1e-9, 0.0, res.x)
    w = base + onehot @ vals - price @ vals
    return OptimalPayout(vals, fr, gamma, load, wealth, ce0, certainty_equivalent(w, gamma), bool(res.success))


def scale_for_utility(shape_values, loss, bins, gamma: float = DEFAULT_GAMMA, load: float = DEFAULT_LOAD,
                      wealth: float = DEFAULT_WEALTH, freq=None) -> OptimalPayout:
    """Best size of a fixed step shape (per $1 of maximum payout) for the same CRRA farmer.

    Returns an OptimalPayout whose `values` are the shape times the chosen maximum payout per $1
    of insured value; `max_payout` is that size.
    """
    shape = np.asarray(shape_values, dtype=float)
    n_bins = len(shape)
    loss = np.asarray(loss, dtype=float)
    bins = np.asarray(bins, dtype=int)
    ok = ~np.isnan(loss) & (bins >= 0) & (bins < n_bins)
    loss, bins = loss[ok], bins[ok]
    fr = bin_frequencies(bins, n_bins) if freq is None else np.asarray(freq, float)
    base = wealth - loss
    ce0 = certainty_equivalent(base, gamma)
    top = float(shape.max()) if len(shape) else 0.0
    if len(loss) == 0 or top <= 0:
        return OptimalPayout(np.zeros(n_bins), fr, gamma, load, wealth, ce0, ce0, True)
    unit = shape / top
    price = (1.0 + load) * fair_premium(unit, fr)

    def neg_eu(a):
        w = base + a * unit[bins] - a * price
        pen = np.sum(np.minimum(w - _W_FLOOR, 0.0) ** 2)
        return -float(np.mean(crra_utility(w, gamma))) + 1e3 * pen

    res = minimize_scalar(neg_eu, bounds=(0.0, MAX_PAYOUT_PER_DOLLAR), method="bounded",
                          options={"xatol": 1e-7})
    a = float(res.x) if res.x > 1e-7 else 0.0
    vals = a * unit
    w = base + vals[bins] - a * price
    return OptimalPayout(vals, fr, gamma, load, wealth, ce0, certainty_equivalent(w, gamma), bool(res.success))


def ce_shares(loss, bins, n_bins: int, shapes: dict, gamma: float = DEFAULT_GAMMA, load: float = DEFAULT_LOAD,
              wealth: float = DEFAULT_WEALTH) -> dict:
    """CE gain of the optimum and of each fixed shape at its best size, plus each shape's share of the optimum.

    shapes: {name: step values per $1 of maximum payout (n_bins entries)}.
    """
    opt = optimal_step_payout(loss, bins, n_bins, gamma, load, wealth)
    out = {"optimal": {"ce_gain": opt.ce_gain, "max_payout": opt.max_payout, "premium": opt.premium,
                       "fair_premium": opt.fair_premium, "share": 1.0 if opt.ce_gain > 0 else np.nan,
                       "values": opt.values}}
    for name, sv in shapes.items():
        r = scale_for_utility(sv, loss, bins, gamma, load, wealth, freq=opt.freq)
        out[name] = {"ce_gain": r.ce_gain, "max_payout": r.max_payout, "premium": r.premium,
                     "fair_premium": r.fair_premium,
                     "share": r.ce_gain / opt.ce_gain if opt.ce_gain > 1e-12 else np.nan, "values": r.values}
    return out


def evaluate_payout(values, loss, bins, gamma: float = DEFAULT_GAMMA, load: float = DEFAULT_LOAD,
                    wealth: float = DEFAULT_WEALTH, freq=None) -> dict:
    """CE gain of a given step payout (per $1 of insured value) on a sample, priced at `freq`."""
    values = np.asarray(values, dtype=float)
    loss = np.asarray(loss, dtype=float)
    bins = np.asarray(bins, dtype=int)
    ok = ~np.isnan(loss) & (bins >= 0) & (bins < len(values))
    loss, bins = loss[ok], bins[ok]
    fr = bin_frequencies(bins, len(values)) if freq is None else np.asarray(freq, float)
    base = wealth - loss
    w = base + values[bins] - (1.0 + load) * fair_premium(values, fr)
    ce0, ce1 = certainty_equivalent(base, gamma), certainty_equivalent(w, gamma)
    return {"ce_without": ce0, "ce_with": ce1, "ce_gain": ce1 - ce0, "premium": (1.0 + load) * fair_premium(values, fr),
            "n": int(len(loss))}
