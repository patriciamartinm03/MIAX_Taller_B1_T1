from dataclasses import FrozenInstanceError

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


@pytest.mark.parametrize(
    "bad, message",
    [
        ({"n_sims": 0}, "at least 1"),
        ({"horizon_days": 0}, "at least 1"),
        ({"initial_value": 0}, "must be positive"),
        ({"initial_value": -100}, "must be positive"),
    ],
)
def test_config_rejects_invalid_values(bad, message):
    with pytest.raises(ValueError, match=message):
        SimulationConfig(**bad)


def test_config_is_frozen():
    config = SimulationConfig()
    with pytest.raises(FrozenInstanceError):
        config.n_sims = 10


def test_paths_must_match_the_config_shape():
    result = make_result(n_sims=20, horizon_days=10)
    other_config = SimulationConfig(n_sims=20, horizon_days=11)
    with pytest.raises(ValueError, match=r"paths must have shape \(20, 12\)"):
        SimulationResult(result.paths, other_config, rebalance_every=1)


def test_mu_and_cov_must_be_given_together():
    result = make_result()
    with pytest.raises(ValueError, match="given together"):
        SimulationResult(result.paths, result.config, rebalance_every=1, mu=MU)
    with pytest.raises(ValueError, match="given together"):
        SimulationResult(result.paths, result.config, rebalance_every=1, cov=COV)


@pytest.mark.parametrize(
    "mu, cov, message",
    [
        (np.array([MU]), COV, "mu must be a 1D array"),
        (MU, np.eye(3) * 0.0001, "square matrix with one row per asset"),
    ],
)
def test_mu_and_cov_shapes_are_checked(mu, cov, message):
    result = make_result()
    with pytest.raises(ValueError, match=message):
        SimulationResult(result.paths, result.config, rebalance_every=1, mu=mu, cov=cov)


def test_percentiles_have_one_row_per_day_and_start_at_initial_value():
    result = make_result(horizon_days=60)
    table = result.percentiles((5, 50, 95))
    assert table.columns.tolist() == ["p5", "p50", "p95"]
    assert len(table) == 61
    assert table.iloc[0].tolist() == pytest.approx([100.0] * 3)
    final = table.iloc[-1]
    assert final["p5"] <= final["p50"] <= final["p95"]


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
