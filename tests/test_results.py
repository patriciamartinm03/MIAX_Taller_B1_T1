import numpy as np
import pytest

from miax_toolkit import metrics
from miax_toolkit.models.results import SimulationConfig, SimulationResult
from miax_toolkit.simulation.montecarlo import returns_to_paths, simulate_returns

MU = np.array([0.0005, 0.0003])
COV = np.array([[0.0004, 0.00018], [0.00018, 0.000225]])


def make_result(rebalance_every=1, n_sims=500, horizon_days=60):
    config = SimulationConfig(n_sims=n_sims, horizon_days=horizon_days, seed=42)
    returns = simulate_returns(MU, COV, n_sims, horizon_days, seed=42)
    paths = returns_to_paths(
        returns, [0.6, 0.4], config.initial_value, rebalance_every=rebalance_every
    )
    return SimulationResult(paths, config, rebalance_every=rebalance_every)


def test_risk_measures_use_metrics():
    result = make_result()
    final, initial = result.final_values, result.config.initial_value
    assert result.prob_loss() == metrics.prob_loss(final, initial)
    for level in (1, 5, 10):
        assert result.value_at_risk(level) == metrics.value_at_risk(
            final, initial, level
        )
        assert result.expected_shortfall(level) == metrics.expected_shortfall(
            final, initial, level
        )


def test_expected_shortfall_is_at_least_value_at_risk():
    result = make_result()
    assert result.expected_shortfall() >= result.value_at_risk()


def test_value_at_risk_rejects_a_confidence_level_passed_as_percentile():
    with pytest.raises(ValueError, match="level must be a percentile"):
        make_result().value_at_risk(95)


def test_rebalance_every_is_required():
    result = make_result()
    with pytest.raises(TypeError):
        SimulationResult(result.paths, result.config)


@pytest.mark.parametrize("bad", [True, 0, 21.0])
def test_rebalance_every_rejects_invalid_values(bad):
    result = make_result()
    with pytest.raises((TypeError, ValueError)):
        SimulationResult(result.paths, result.config, rebalance_every=bad)


def test_periodic_rebalancing_matches_a_day_by_day_loop():
    weights = np.array([0.6, 0.4])
    returns = simulate_returns(MU, COV, 20, 50, seed=1)
    for every in (1, 7, 21, None):
        paths = returns_to_paths(returns, weights, 100.0, rebalance_every=every)
        for sim in range(20):
            holdings = 100.0 * weights
            for day in range(50):
                if every is not None and day % every == 0:
                    holdings = holdings.sum() * weights
                holdings = holdings * (1 + returns[sim, day])
                assert paths[sim, day + 1] == pytest.approx(holdings.sum())


def test_plot_distribution_marks_var_in_the_legend():
    result = make_result()
    ax = result.plot_distribution()
    labels = [text.get_text() for text in ax.get_legend().get_texts()]
    assert labels[0] == "Initial value"
    assert labels[1].startswith("VaR 95 %")
    ax = result.plot_distribution(var_level=None)
    assert len(ax.get_legend().get_texts()) == 1
