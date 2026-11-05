import numpy as np


def simulate_returns(
    mu: np.ndarray,
    cov: np.ndarray,
    n_sims: int,
    horizon: int,
    seed: int | None = None,
) -> np.ndarray:
    """Simulate daily returns with a multivariate geometric Brownian motion.

    Parameters
    ----------
    mu : mean DAILY simple return of each asset (e.g. PriceSeries.mean_return),
        not annual and not log returns. Shape (n_assets,).
    cov : covariance matrix of DAILY simple returns. Shape (n_assets, n_assets).
    n_sims : number of simulated paths.
    horizon : number of days to simulate.
    seed : random seed, for reproducible results.

    Returns
    -------
    Simulated daily simple returns, shape (n_sims, horizon, n_assets).
    """
    mu = np.asarray(mu, dtype=float)
    cov = np.asarray(cov, dtype=float)

    if mu.ndim != 1:
        raise ValueError("mu must be a 1D array")
    if cov.shape != (mu.size, mu.size):
        raise ValueError("cov must be a square matrix with one row per asset")
    if not np.allclose(cov, cov.T):
        raise ValueError("cov must be symmetric")
    if np.linalg.eigvalsh(cov).min() < -1e-12:
        raise ValueError(
            "cov must be positive semi-definite (check how it was estimated)"
        )
    if n_sims < 1 or horizon < 1:
        raise ValueError("n_sims and horizon must be at least 1")

    rng = np.random.default_rng(seed)
    shocks = rng.multivariate_normal(
        np.zeros(mu.size), cov, size=(n_sims, horizon), method="svd"
    )
    drift = mu - 0.5 * np.diag(cov)

    return np.exp(drift + shocks) - 1


def returns_to_paths(
    returns: np.ndarray,
    weights: np.ndarray,
    initial_value: float = 100.0,
    rebalance: bool = True,
) -> np.ndarray:
    """Portfolio value paths. Shape: (n_sims, horizon + 1).

    rebalance=True: weights are reset to their initial value every day.
    rebalance=False: buy and hold; weights drift with prices.
    """
    weights = np.asarray(weights, dtype=float)
    if weights.shape != (returns.shape[2],):
        raise ValueError("weights must have one value per asset")
    if not np.isclose(weights.sum(), 1.0):
        raise ValueError("weights must add up to 1")

    if rebalance:
        growth = np.cumprod(1 + returns @ weights, axis=1)
    else:
        growth = (np.cumprod(1 + returns, axis=1) * weights).sum(axis=2)

    start = np.ones((returns.shape[0], 1))

    return initial_value * np.concatenate([start, growth], axis=1)
