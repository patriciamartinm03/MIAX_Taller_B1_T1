import numpy as np


def simulate_returns(
    mu: np.ndarray,
    cov: np.ndarray,
    n_sims: int,
    horizon: int,
    seed: int | None = None,
) -> np.ndarray:
    """Simula retornos diarios. Forma: (n_sims, horizon, n_activos)."""
    mu = np.asarray(mu, dtype=float)
    cov = np.asarray(cov, dtype=float)

    if mu.ndim != 1:
        raise ValueError("mu must be a 1D array")
    if cov.shape != (mu.size, mu.size):
        raise ValueError("cov must be a square matrix with one row per asset")
    if n_sims < 1 or horizon < 1:
        raise ValueError("n_sims and horizon must be at least 1")

    rng = np.random.default_rng(seed)
    shocks = rng.multivariate_normal(
        np.zeros(mu.size), cov, size=(n_sims, horizon), method="svd"
    )
    drift = mu - 0.5 * np.diag(cov)

    return np.exp(drift + shocks) - 1
