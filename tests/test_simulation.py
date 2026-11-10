"""Monte Carlo engine: simulate_returns and the input checks of returns_to_paths.

The path-building and rebalancing logic is checked against a day-by-day loop in
test_results.py; this file covers the random part and its validation.
"""

import numpy as np
import pytest

from miax_toolkit.simulation.montecarlo import (
    check_rebalance_every,
    returns_to_paths,
    simulate_returns,
)

MU = np.array([0.0005, 0.0003])
# Daily volatilities 2 % and 1.5 %, correlation 0.6
COV = np.array([[0.0004, 0.00018], [0.00018, 0.000225]])


@pytest.fixture(scope="module")
def large_sample() -> np.ndarray:
    """1,000,000 simulated days per asset, flattened to (days, assets)."""
    returns = simulate_returns(MU, COV, n_sims=4000, horizon=250, seed=123)
    return returns.reshape(-1, len(MU))


def test_output_shape_is_sims_by_days_by_assets():
    returns = simulate_returns(MU, COV, n_sims=7, horizon=5, seed=1)
    assert returns.shape == (7, 5, 2)


def test_mean_return_matches_mu(large_sample):
    # The -0.5 * sigma^2 drift correction makes E[return] = exp(mu) - 1 ~ mu.
    # Without it the mean would be exp(mu + sigma^2 / 2) - 1, i.e. 0.0007 for
    # the first asset: 10 standard errors away from the tolerance used here.
    np.testing.assert_allclose(large_sample.mean(axis=0), np.exp(MU) - 1, atol=1e-4)


def test_covariance_matches_cov(large_sample):
    np.testing.assert_allclose(np.cov(large_sample, rowvar=False), COV, rtol=0.03)


def test_correlation_matches_cov(large_sample):
    correlation = np.corrcoef(large_sample, rowvar=False)[0, 1]
    assert correlation == pytest.approx(0.6, abs=0.01)


def test_simple_returns_never_fall_below_minus_100_percent():
    huge = np.array([[0.25]])  # 50 % daily volatility
    returns = simulate_returns(np.array([0.0]), huge, n_sims=1000, horizon=50, seed=2)
    assert (returns > -1).all()


def test_zero_variance_gives_the_drift_every_day():
    mu = np.array([0.001, -0.002])
    returns = simulate_returns(mu, np.zeros((2, 2)), n_sims=3, horizon=4, seed=1)
    np.testing.assert_allclose(returns, np.broadcast_to(np.exp(mu) - 1, (3, 4, 2)))


def test_perfectly_correlated_assets_move_together():
    # Singular but valid covariance: the SVD method handles it.
    cov = np.full((2, 2), 0.0001)
    returns = simulate_returns(np.array([0.0002, 0.0002]), cov, 50, 20, seed=3)
    np.testing.assert_allclose(returns[..., 0], returns[..., 1], atol=1e-8)


def test_same_seed_same_returns_different_seed_different_returns():
    first = simulate_returns(MU, COV, 10, 5, seed=42)
    np.testing.assert_array_equal(first, simulate_returns(MU, COV, 10, 5, seed=42))
    assert not np.allclose(first, simulate_returns(MU, COV, 10, 5, seed=43))


def test_single_asset():
    returns = simulate_returns(np.array([0.0004]), np.array([[0.0001]]), 5, 3, seed=1)
    assert returns.shape == (5, 3, 1)


@pytest.mark.parametrize(
    "mu, cov, message",
    [
        (MU.reshape(1, 2), COV, "mu must be a 1D array"),
        (MU, np.eye(3) * 0.0001, "square matrix with one row per asset"),
        (MU, np.array([[0.0004, 0.0001], [0.0002, 0.0004]]), "must be symmetric"),
        # Symmetric, but correlation above 1: eigenvalues 0.0003 and -0.0001
        (MU, np.array([[0.0001, 0.0002], [0.0002, 0.0001]]), "positive semi-definite"),
    ],
)
def test_invalid_mu_or_cov_fails(mu, cov, message):
    with pytest.raises(ValueError, match=message):
        simulate_returns(mu, cov, n_sims=10, horizon=5)


@pytest.mark.parametrize("n_sims, horizon", [(0, 5), (10, 0)])
def test_sims_and_horizon_must_be_positive(n_sims, horizon):
    with pytest.raises(ValueError, match="at least 1"):
        simulate_returns(MU, COV, n_sims=n_sims, horizon=horizon)


# --- returns_to_paths and check_rebalance_every input checks ----------------


def test_paths_start_at_initial_value_with_one_extra_column():
    returns = simulate_returns(MU, COV, 6, 4, seed=1)
    paths = returns_to_paths(returns, [0.5, 0.5], 250.0, rebalance_every=None)
    assert paths.shape == (6, 5)
    assert (paths[:, 0] == 250.0).all()


@pytest.mark.parametrize(
    "weights, message",
    [
        ([1.0], "one value per asset"),
        ([0.5, 0.3, 0.2], "one value per asset"),
        ([0.5, 0.4], "add up to 1"),
    ],
)
def test_paths_reject_invalid_weights(weights, message):
    returns = simulate_returns(MU, COV, 2, 3, seed=1)
    with pytest.raises(ValueError, match=message):
        returns_to_paths(returns, weights, rebalance_every=1)


@pytest.mark.parametrize("valid", [None, 1, 21, 63, 10_000])
def test_check_rebalance_every_accepts_none_and_positive_days(valid):
    check_rebalance_every(valid)


@pytest.mark.parametrize(
    "invalid, error",
    [
        (0, ValueError),
        (-21, ValueError),
        (21.0, TypeError),
        (True, TypeError),
        ("21", TypeError),
    ],
)
def test_check_rebalance_every_rejects_other_values(invalid, error):
    with pytest.raises(error):
        check_rebalance_every(invalid)
