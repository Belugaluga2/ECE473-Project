"""Illustrative one-game injury hedge; probabilities are assumptions, not NBA data.

Run: .venv/bin/python scripts/experiments/sports_injury_feasibility.py
The standard-contract DNP settlement is assumed equal to the entry price,
giving zero net payoff. Kalshi actually determines a fair settlement price.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Scenario:
    dnp: float = 0.05
    injured_under: float = 0.03
    healthy_under: float = 0.30
    healthy_over: float = 0.62
    injury_loss: float = 100.0

    def __post_init__(self) -> None:
        probabilities = (self.dnp, self.injured_under, self.healthy_under,
                         self.healthy_over)
        if any(p < 0 for p in probabilities) or abs(sum(probabilities) - 1) > 1e-10:
            raise ValueError("State probabilities must be nonnegative and sum to one")
        if self.injury_loss <= 0 or self.dnp == 1:
            raise ValueError("Need a positive loss and a positive chance of playing")


@dataclass(frozen=True)
class Result:
    no_price: float
    loss_variance: float
    hedge_variance: float
    covariance: float
    optimal_contracts: float
    variance_reduction: float
    full_claim_contracts: float
    full_claim_entry_cost: float
    state_net_payoffs: tuple[float, float, float, float]


def evaluate(s: Scenario, *, dnp_pays_under: bool = False) -> Result:
    """Evaluate a fair-priced NO position, excluding fees, spread and depth.

    Four mutually exclusive states: DNP, enters then is injured below target,
    healthy below target, and healthy at/above target. All modeled in-game
    injuries end below target, which is favorable to the proposed hedge.
    """
    probs = (s.dnp, s.injured_under, s.healthy_under, s.healthy_over)
    if dnp_pays_under:
        # Counterfactual contract: a DNP is an ordinary UNDER settlement.
        q = s.dnp + s.injured_under + s.healthy_under
        net = (1 - q, 1 - q, 1 - q, -q)
    else:
        # Standard contract: assume its DNP fair settlement equals entry q.
        q = (s.injured_under + s.healthy_under) / (1 - s.dnp)
        net = (0.0, 1 - q, 1 - q, -q)
    if not 0 < q < 1:
        raise ValueError("Both NO outcomes must have positive probability")

    loss = (s.injury_loss, s.injury_loss, 0.0, 0.0)
    mean_loss = sum(p * x for p, x in zip(probs, loss))
    mean_hedge = sum(p * x for p, x in zip(probs, net))
    var_loss = sum(p * (x - mean_loss) ** 2 for p, x in zip(probs, loss))
    var_hedge = sum(p * (x - mean_hedge) ** 2 for p, x in zip(probs, net))
    cov = sum(p * (l - mean_loss) * (h - mean_hedge)
              for p, l, h in zip(probs, loss, net))
    if var_loss == 0 or var_hedge == 0:
        raise ValueError("Need nonzero injury-loss and hedge variance")

    optimal = cov / var_hedge
    full_claim = s.injury_loss / (1 - q)
    return Result(
        no_price=q,
        loss_variance=var_loss,
        hedge_variance=var_hedge,
        covariance=cov,
        optimal_contracts=optimal,
        variance_reduction=cov ** 2 / (var_loss * var_hedge),
        full_claim_contracts=full_claim,
        full_claim_entry_cost=full_claim * q,
        state_net_payoffs=net,
    )


def main() -> None:
    s = Scenario()
    for label, dnp_pays_under in (("Standard DNP fair-price settlement", False),
                                  ("Counterfactual DNP pays UNDER", True)):
        result = evaluate(s, dnp_pays_under=dnp_pays_under)
        print(label)
        print(f"  Fair NO price: {result.no_price:.4f}")
        print(f"  Variance-minimizing contracts: {result.optimal_contracts:.2f}")
        print(f"  Modeled variance reduction: {result.variance_reduction:.2%}")
        print(f"  Contracts to net a $100 in-game injury claim: "
              f"{result.full_claim_contracts:.2f}")
        print(f"  Entry cost of that claim-sized position: "
              f"USD {result.full_claim_entry_cost:.2f}")


if __name__ == "__main__":
    main()
