import numpy as np
import pytest

from miax_toolkit.simulation.montecarlo import returns_to_paths, simulate_returns

MU = np.array([0.0005, 0.0003])
COV = np.array([[0.0001, 0.00002], [0.00002, 0.0004]])


def test_simulated_returns_have_expected_shape():
    returns = simulate_returns(MU, COV, n_sims=50, horizon=10, seed=1)
    assert returns.shape == (50, 10, 2)


def test_same_seed_gives_same_returns():
    first = simulate_returns(MU, COV, n_sims=20, horizon=5, seed=42)
    second = simulate_returns(MU, COV, n_sims=20, horizon=5, seed=42)
    np.testing.assert_array_equal(first, second)


def test_zero_covariance_gives_deterministic_drift():
    returns = simulate_returns(MU, np.zeros((2, 2)), n_sims=3, horizon=4, seed=0)
    np.testing.assert_allclose(returns, np.broadcast_to(np.exp(MU) - 1, (3, 4, 2)))


def test_log_returns_match_gbm_moments():
    # GBM: log(1 + R) ~ N(mu - var / 2, cov). Checked on a large sample.
    returns = simulate_returns(MU, COV, n_sims=20_000, horizon=10, seed=7)
    log_returns = np.log1p(returns).reshape(-1, 2)
    np.testing.assert_allclose(
        log_returns.mean(axis=0), MU - 0.5 * np.diag(COV), atol=2e-4
    )
    np.testing.assert_allclose(np.cov(log_returns.T), COV, rtol=0.05)


def test_list_inputs_are_accepted():
    returns = simulate_returns([0.001], [[0.0001]], n_sims=2, horizon=3, seed=0)
    assert returns.shape == (2, 3, 1)


@pytest.mark.parametrize(
    ("mu", "cov", "message"),
    [
        (np.array([[0.1, 0.2]]), COV, "1D"),
        (MU, np.eye(3), "square"),
        (MU, np.array([[1.0, 0.5], [0.1, 1.0]]), "symmetric"),
        (MU, np.array([[1.0, 2.0], [2.0, 1.0]]), "positive semi-definite"),
    ],
    ids=["mu-2d", "cov-wrong-size", "cov-asymmetric", "cov-not-psd"],
)
def test_invalid_mu_or_cov_is_rejected(mu, cov, message):
    with pytest.raises(ValueError, match=message):
        simulate_returns(mu, cov, n_sims=1, horizon=1)


@pytest.mark.parametrize(("n_sims", "horizon"), [(0, 10), (10, 0)])
def test_non_positive_sizes_are_rejected(n_sims, horizon):
    with pytest.raises(ValueError, match="at least 1"):
        simulate_returns(MU, COV, n_sims=n_sims, horizon=horizon)


# Two days, asset A doubles each day, asset B stays flat, 50/50 portfolio.
DOUBLING_VS_FLAT = np.array([[[1.0, 0.0], [1.0, 0.0]]])
HALF_HALF = np.array([0.5, 0.5])


def test_rebalanced_paths_compound_portfolio_return():
    # Each day the portfolio earns 0.5 * 100 % = 50 %: 100 -> 150 -> 225.
    paths = returns_to_paths(DOUBLING_VS_FLAT, HALF_HALF, rebalance=True)
    np.testing.assert_allclose(paths, [[100.0, 150.0, 225.0]])


def test_buy_and_hold_paths_let_weights_drift():
    # A: 50 -> 100 -> 200, B: 50 -> 50 -> 50. Total: 100 -> 150 -> 250.
    paths = returns_to_paths(DOUBLING_VS_FLAT, HALF_HALF, rebalance=False)
    np.testing.assert_allclose(paths, [[100.0, 150.0, 250.0]])


def test_paths_start_at_initial_value_with_horizon_plus_one_columns():
    returns = simulate_returns(MU, COV, n_sims=5, horizon=8, seed=3)
    paths = returns_to_paths(returns, HALF_HALF, initial_value=250.0)
    assert paths.shape == (5, 9)
    np.testing.assert_array_equal(paths[:, 0], 250.0)


def test_single_asset_rebalance_and_hold_agree():
    returns = simulate_returns([0.001], [[0.0001]], n_sims=4, horizon=6, seed=5)
    np.testing.assert_allclose(
        returns_to_paths(returns, [1.0], rebalance=True),
        returns_to_paths(returns, [1.0], rebalance=False),
    )


@pytest.mark.parametrize(
    ("weights", "message"),
    [([1.0], "one value per asset"), ([0.6, 0.6], "add up to 1")],
)
def test_invalid_weights_are_rejected(weights, message):
    with pytest.raises(ValueError, match=message):
        returns_to_paths(DOUBLING_VS_FLAT, weights)
