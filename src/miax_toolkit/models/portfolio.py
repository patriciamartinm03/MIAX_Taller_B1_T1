from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from miax_toolkit.models.results import SimulationConfig, SimulationResult
from miax_toolkit.models.series import PriceSeries
from miax_toolkit.preprocessing.alignment import align_prices
from miax_toolkit.simulation.montecarlo import returns_to_paths, simulate_returns


@dataclass
class Portfolio:
    """Long-only portfolio of assets with target weights, in one base currency."""

    name: str
    assets: list[PriceSeries] = field(repr=False)
    weights: list[float]

    prices: pd.DataFrame = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not self.assets:
            raise ValueError("A portfolio needs at least one asset")
        if not all(isinstance(asset, PriceSeries) for asset in self.assets):
            raise TypeError("assets must be PriceSeries objects")
        if len(self.weights) != len(self.assets):
            raise ValueError("There must be one weight per asset")

        tickers = [asset.ticker for asset in self.assets]
        if len(set(tickers)) != len(tickers):
            raise ValueError("There are repeated assets")
        if len({asset.price_type for asset in self.assets}) != 1:
            raise ValueError("All assets must use the same price_type")

        self.weights = [float(weight) for weight in self.weights]
        if min(self.weights) < 0:
            raise ValueError("Negative weights are not allowed")
        if not np.isclose(sum(self.weights), 1.0):
            raise ValueError("weights must add up to 1")

        self.prices = align_prices(
            {asset.ticker: asset.usd_prices() for asset in self.assets}
        )
        if len(self.prices) < 3:
            raise ValueError("Need at least three common dates")

    def asset_returns(self) -> pd.DataFrame:
        """Daily simple returns of each asset, on the common dates."""
        return self.prices.pct_change().dropna()

    def returns(self) -> pd.Series:
        """Daily portfolio returns, assuming daily rebalancing."""
        return self.asset_returns() @ np.array(self.weights)

    def monte_carlo(
        self,
        config: SimulationConfig | None = None,
        mu: np.ndarray | None = None,
        cov: np.ndarray | None = None,
        rebalance: bool = True,
    ) -> SimulationResult:
        """Simulate the portfolio. mu and cov are DAILY; by default, historical."""
        config = SimulationConfig() if config is None else config
        asset_returns = self.asset_returns()
        mu = asset_returns.mean().to_numpy() if mu is None else mu
        cov = asset_returns.cov().to_numpy() if cov is None else cov

        simulated = simulate_returns(
            mu, cov, config.n_sims, config.horizon_days, config.seed
        )
        paths = returns_to_paths(
            simulated, self.weights, config.initial_value, rebalance
        )
        return SimulationResult(paths, config)
