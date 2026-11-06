from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from miax_toolkit import metrics
from miax_toolkit.constants import BASE_CURRENCY
from miax_toolkit.models.macro import MacroSeries
from miax_toolkit.models.results import SimulationConfig, SimulationResult
from miax_toolkit.models.series import PriceSeries
from miax_toolkit.preprocessing.alignment import align_prices
from miax_toolkit.simulation.montecarlo import returns_to_paths, simulate_returns


@dataclass
class Portfolio:
    name: str
    assets: list[PriceSeries] = field(repr=False)
    weights: list[float]
    risk_free: MacroSeries | None = field(default=None, repr=False)

    prices: pd.DataFrame = field(init=False, repr=False)
    _risk_free_daily: pd.Series | None = field(init=False, repr=False, default=None)

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

        try:
            self.weights = [float(weight) for weight in self.weights]
        except (TypeError, ValueError):
            raise ValueError("weights must be finite numbers") from None
        if not np.isfinite(self.weights).all():
            raise ValueError("weights must be finite numbers (found NaN or infinity)")
        if min(self.weights) < 0:
            raise ValueError("Negative weights are not allowed")
        if not np.isclose(sum(self.weights), 1.0):
            raise ValueError("weights must add up to 1")

        self.prices = align_prices(
            {asset.ticker: asset.usd_prices() for asset in self.assets}
        )
        if len(self.prices) < 3:
            ranges = "; ".join(
                f"{asset.ticker}: {asset.prices.index[0].date()} to "
                f"{asset.prices.index[-1].date()}"
                for asset in self.assets
            )
            raise ValueError(
                f"Need at least three common dates, found {len(self.prices)}. "
                f"Date range of each asset: {ranges}"
            )

        if self.risk_free is not None:
            self._validate_risk_free()
            self._risk_free_daily = metrics.daily_risk_free(
                self.risk_free.as_decimal(), self.asset_returns().index
            )

    def _validate_risk_free(self) -> None:
        if not isinstance(self.risk_free, MacroSeries):
            raise TypeError("risk_free must be a MacroSeries")
        if self.risk_free.currency != BASE_CURRENCY:
            raise ValueError(
                f"risk_free must be in {BASE_CURRENCY}, not {self.risk_free.currency}"
            )
        if self.risk_free.units not in ("percent", "decimal"):
            raise ValueError(
                f"risk_free units must be 'percent' or 'decimal', "
                f"not '{self.risk_free.units}'"
            )

    def _weights_by_ticker(self) -> pd.Series:
        return pd.Series(self.weights, index=[asset.ticker for asset in self.assets])

    def risk_free_daily(self) -> pd.Series | float:
        return 0.0 if self._risk_free_daily is None else self._risk_free_daily

    def risk_free_mean(self) -> float:
        if self._risk_free_daily is None:
            return 0.0
        return float(metrics.annualize_mean(float(self._risk_free_daily.mean())))

    def currency_exposure(self) -> pd.Series:
        currencies = {asset.ticker: asset.currency for asset in self.assets}
        exposure = self._weights_by_ticker().groupby(currencies).sum()
        return exposure.rename_axis("currency").sort_values(ascending=False)

    def effective_n_assets(self) -> float:
        return metrics.effective_n_assets(self.weights)

    def asset_returns(self) -> pd.DataFrame:
        return metrics.daily_returns(self.prices)

    def returns(self) -> pd.Series:
        return self.asset_returns() @ self._weights_by_ticker()

    def value(self, initial_value: float = 100.0, rebalance: bool = True) -> pd.Series:
        if rebalance:
            values = metrics.cumulative_value(
                self.returns(), self.prices.index[0], initial_value
            )
        else:
            normalized = self.prices / self.prices.iloc[0]
            values = (normalized * self._weights_by_ticker()).sum(
                axis=1
            ) * initial_value
        return values.rename(self.name)

    def drawdown_details(self) -> metrics.DrawdownDetails:
        return metrics.max_drawdown_details(self.value())

    def correlation(self) -> pd.DataFrame:
        return self.asset_returns().corr()

    def diversification_benefit(self) -> float:
        asset_returns = self.asset_returns()
        asset_volatilities = asset_returns.apply(metrics.annual_volatility)
        weighted_volatility = float(
            (self._weights_by_ticker() * asset_volatilities).sum()
        )
        return weighted_volatility - metrics.annual_volatility(self.returns())

    def monte_carlo(
        self,
        config: SimulationConfig | None = None,
        mu: np.ndarray | None = None,
        cov: np.ndarray | None = None,
        rebalance: bool = True,
    ) -> SimulationResult:
        config = SimulationConfig() if config is None else config
        asset_returns = self.asset_returns()
        mu = asset_returns.mean().to_numpy() if mu is None else mu
        cov = asset_returns.cov().to_numpy() if cov is None else cov

        simulated = simulate_returns(
            mu, cov, config.n_sims, config.horizon_days, config.seed
        )
        weights = self._weights_by_ticker().reindex(asset_returns.columns).to_numpy()
        paths = returns_to_paths(simulated, weights, config.initial_value, rebalance)
        return SimulationResult(paths, config)
