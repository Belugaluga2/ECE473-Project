"""Check the illustrative four-state payoff algebra."""
import math

import pytest

from scripts.experiments.sports_injury_feasibility import Scenario, evaluate


def test_standard_dnp_has_no_guaranteed_payoff_and_optimum_reduces_variance():
    scenario = Scenario()
    result = evaluate(scenario)
    assert math.isclose(result.no_price, 0.33 / 0.95)
    assert result.state_net_payoffs[0] == 0
    assert math.isclose(result.optimal_contracts, 100 * 0.03 / 0.33)

    probabilities = (scenario.dnp, scenario.injured_under,
                     scenario.healthy_under, scenario.healthy_over)
    losses = (100.0, 100.0, 0.0, 0.0)
    def variance_after(n):
        residuals = [loss - n * payoff
                     for loss, payoff in zip(losses, result.state_net_payoffs)]
        mean = sum(p * value for p, value in zip(probabilities, residuals))
        return sum(p * (value - mean) ** 2
                   for p, value in zip(probabilities, residuals))

    assert variance_after(result.optimal_contracts) < variance_after(0)
    assert variance_after(result.optimal_contracts) < variance_after(
        2 * result.optimal_contracts)
    assert math.isclose(
        result.variance_reduction,
        1 - variance_after(result.optimal_contracts) / variance_after(0))


def test_dnp_under_counterfactual_changes_the_payoff():
    standard = evaluate(Scenario())
    counterfactual = evaluate(Scenario(), dnp_pays_under=True)
    assert counterfactual.state_net_payoffs[0] > 0
    assert counterfactual.variance_reduction > standard.variance_reduction


def test_bad_probabilities_are_rejected():
    with pytest.raises(ValueError, match="sum to one"):
        Scenario(dnp=0.50)
