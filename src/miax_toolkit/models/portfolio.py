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

    # Creation and validation

    def __post_init__(self) -> None:
        if not self.assets:
            raise ValueError(f"Portfolio '{self.name}' needs at least one asset")
        for position, asset in enumerate(self.assets, start=1):
            if not isinstance(asset, PriceSeries):
                raise TypeError(
                    f"assets must be PriceSeries objects; asset {position} "
                    f"is a {type(asset).__name__}"
                )
        if len(self.weights) != len(self.assets):
            raise ValueError(
                f"There must be one weight per asset; got {len(self.assets)} assets "
                f"and {len(self.weights)} weights"
            )

        tickers = [asset.ticker for asset in self.assets]
        repeated = sorted({ticker for ticker in tickers if tickers.count(ticker) > 1})
        if repeated:
            raise ValueError(f"There are repeated assets: {', '.join(repeated)}")
        if len({asset.price_type for asset in self.assets}) != 1:
            price_types = ", ".join(
                f"{asset.ticker}: {asset.price_type}" for asset in self.assets
            )
            raise ValueError(
                f"All assets must use the same price_type; got {price_types}"
            )

        weights = []
        for ticker, weight in zip(tickers, self.weights):
            try:
                weight = float(weight)
            except (TypeError, ValueError):
                raise ValueError(
                    f"weights must be finite numbers; the weight of {ticker} "
                    f"is {weight!r}"
                ) from None
            if not np.isfinite(weight):
                raise ValueError(
                    f"weights must be finite numbers; the weight of {ticker} is {weight}"
                )
            if weight < 0:
                raise ValueError(
                    f"Negative weights are not allowed; the weight of {ticker} "
                    f"is {weight}"
                )
            weights.append(weight)
        self.weights = weights
        if not np.isclose(sum(self.weights), 1.0):
            raise ValueError(
                f"weights must add up to 1; they add up to {sum(self.weights):g}"
            )

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
            raise TypeError(
                f"risk_free must be a MacroSeries, got {type(self.risk_free).__name__}"
            )
        if self.risk_free.currency != BASE_CURRENCY:
            raise ValueError(
                f"risk_free must be in {BASE_CURRENCY}, not {self.risk_free.currency}"
            )
        if self.risk_free.units not in ("percent", "decimal"):
            raise ValueError(
                f"risk_free units must be 'percent' or 'decimal', "
                f"not '{self.risk_free.units}'"
            )

    # Risk-free rate

    def risk_free_daily(self) -> pd.Series | float:
        return 0.0 if self._risk_free_daily is None else self._risk_free_daily

    def risk_free_mean(self) -> float:
        if self._risk_free_daily is None:
            return 0.0
        # Not MacroSeries.mean: it covers the whole series, not the portfolio period
        return float(metrics.annualize_mean(float(self._risk_free_daily.mean())))

    # Returns

    def _weights_by_ticker(self) -> pd.Series:
        # Weights are matched by ticker so nothing depends on the column order
        return pd.Series(self.weights, index=[asset.ticker for asset in self.assets])

    def asset_returns(self) -> pd.DataFrame:
        return metrics.daily_returns(self.prices)

    def returns(self) -> pd.Series:
        return self.asset_returns() @ self._weights_by_ticker()

    # Composition

    def currency_exposure(self) -> pd.Series:
        currencies = {asset.ticker: asset.currency for asset in self.assets}
        exposure = self._weights_by_ticker().groupby(currencies).sum()
        return exposure.rename_axis("currency").sort_values(ascending=False)

    def effective_n_assets(self) -> float:
        return metrics.effective_n_assets(self.weights)

    # Historical value

    def value(self, initial_value: float = 100.0, rebalance: bool = True) -> pd.Series:
        """rebalance=True resets weights daily; False is buy and hold."""
        if rebalance:
            values = metrics.cumulative_value(
                self.returns(), self.prices.index[0], initial_value
            )
        else:
            normalized = self.prices / self.prices.iloc[0]
            values = normalized @ self._weights_by_ticker() * initial_value
        return values.rename(self.name)

    def drawdown_details(self) -> metrics.DrawdownDetails:
        return metrics.max_drawdown_details(self.value())

    # Metrics table

    def _metrics_row(self, values: pd.Series, returns: pd.Series) -> dict[str, float]:
        risk_free = self.risk_free_daily()
        return {
            "annual_return": metrics.annual_return(returns),
            "cagr": metrics.cagr(values),
            "annual_volatility": metrics.annual_volatility(returns),
            "sharpe": metrics.sharpe_ratio(returns, risk_free),
            "sortino": metrics.sortino_ratio(returns, risk_free),
            "max_drawdown": metrics.max_drawdown(values),
        }

    def metrics_table(self, benchmark: "Portfolio | None" = None) -> pd.DataFrame:
        """With a benchmark, every row uses only the dates both portfolios share."""
        if benchmark is None:
            prices, own_value, own_returns = self.prices, self.value(), self.returns()
        else:
            self._check_benchmark(benchmark)
            if benchmark.name == "Portfolio":
                raise ValueError(
                    "benchmark name 'Portfolio' is reserved for the portfolio row; "
                    "give the benchmark a different name"
                )
            if benchmark.name in self.prices.columns:
                raise ValueError(
                    f"benchmark name '{benchmark.name}' is also a ticker in portfolio "
                    f"'{self.name}'; give the benchmark a different name"
                )
            own_value, own_returns, benchmark_value, benchmark_returns = (
                self._common_dates_with_benchmark(benchmark)
            )
            common = own_value.index
            prices = self.prices.loc[common]

        asset_returns = metrics.daily_returns(prices)
        rows = {
            ticker: self._metrics_row(prices[ticker], asset_returns[ticker])
            for ticker in prices.columns
        }
        rows["Portfolio"] = self._metrics_row(own_value, own_returns)
        if benchmark is not None:
            rows[benchmark.name] = self._metrics_row(benchmark_value, benchmark_returns)
        return pd.DataFrame.from_dict(rows, orient="index").rename_axis("asset")

    def metrics_period(
        self, benchmark: "Portfolio | None" = None
    ) -> tuple[pd.Timestamp, pd.Timestamp]:
        """First and last date used by metrics_table with the same benchmark."""
        if benchmark is None:
            dates = self.prices.index
        else:
            dates = self._common_dates_with_benchmark(benchmark)[0].index
        return dates[0], dates[-1]

    # Currency effect

    def currency_attribution(self) -> pd.DataFrame:
        dates = self.prices.index
        rows = {
            asset.ticker: {
                "currency": asset.currency,
                "local_return": metrics.total_return(asset.prices.loc[dates]),
                "fx_return": metrics.total_return(asset.fx_to_usd.loc[dates]),
                "usd_return": metrics.total_return(self.prices[asset.ticker]),
            }
            for asset in self.assets
            if asset.currency != BASE_CURRENCY
        }
        columns = ["currency", "local_return", "fx_return", "usd_return"]
        table = pd.DataFrame.from_dict(rows, orient="index", columns=columns)
        return table.rename_axis("asset")

    # Benchmark comparison and overlap

    def _check_benchmark(self, benchmark: "Portfolio") -> None:
        if not isinstance(benchmark, Portfolio):
            raise TypeError(
                f"benchmark must be a Portfolio, got {type(benchmark).__name__}"
            )

    def _common_dates_with_benchmark(
        self, benchmark: "Portfolio"
    ) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
        self._check_benchmark(benchmark)
        own_value, benchmark_value = self.value(), benchmark.value()
        common = own_value.index.intersection(benchmark_value.index).sort_values()
        if len(common) < 3:
            own_dates, benchmark_dates = self.prices.index, benchmark.prices.index
            raise ValueError(
                f"benchmark '{benchmark.name}' has only {len(common)} dates in common "
                f"with portfolio '{self.name}' (at least 3 are needed). "
                f"Portfolio: {own_dates[0].date()} to {own_dates[-1].date()}; "
                f"benchmark: {benchmark_dates[0].date()} to "
                f"{benchmark_dates[-1].date()}"
            )
        # Cut values and recompute returns so both cover exactly the same periods
        own_value, benchmark_value = own_value.loc[common], benchmark_value.loc[common]
        return (
            own_value,
            metrics.daily_returns(own_value),
            benchmark_value,
            metrics.daily_returns(benchmark_value),
        )

    def benchmark_issues(self, benchmark: "Portfolio") -> list[str]:
        self._check_benchmark(benchmark)
        issues = []
        own_type, benchmark_type = (
            self.assets[0].price_type,
            benchmark.assets[0].price_type,
        )
        if benchmark_type != own_type:
            issues.append(
                f"benchmark '{benchmark.name}' uses price_type '{benchmark_type}' "
                f"but portfolio '{self.name}' uses '{own_type}'"
            )
        own_dates, benchmark_dates = self.prices.index, benchmark.prices.index
        if benchmark_dates[0] > own_dates[0]:
            issues.append(
                f"benchmark '{benchmark.name}' starts on {benchmark_dates[0].date()}, "
                f"after portfolio '{self.name}' ({own_dates[0].date()})"
            )
        if benchmark_dates[-1] < own_dates[-1]:
            issues.append(
                f"benchmark '{benchmark.name}' ends on {benchmark_dates[-1].date()}, "
                f"before portfolio '{self.name}' ({own_dates[-1].date()})"
            )
        # Gaps inside the shared period, e.g. holidays of another market
        start = max(own_dates[0], benchmark_dates[0])
        end = min(own_dates[-1], benchmark_dates[-1])
        own_dates_inside = own_dates[(own_dates >= start) & (own_dates <= end)]
        missing = own_dates_inside.difference(benchmark_dates)
        if len(missing) > 0:
            issues.append(
                f"benchmark '{benchmark.name}' is missing {len(missing)} dates of "
                f"portfolio '{self.name}' between {start.date()} and {end.date()} "
                f"(first missing: {missing[0].date()})"
            )
        return issues

    def benchmark_comparison(self, benchmark: "Portfolio") -> pd.Series:
        own_value, own_returns, benchmark_value, benchmark_returns = (
            self._common_dates_with_benchmark(benchmark)
        )
        risk_free = self.risk_free_daily()
        comparison = {
            "cagr_difference": metrics.cagr(own_value) - metrics.cagr(benchmark_value),
            "volatility_difference": metrics.annual_volatility(own_returns)
            - metrics.annual_volatility(benchmark_returns),
            "sharpe_difference": metrics.sharpe_ratio(own_returns, risk_free)
            - metrics.sharpe_ratio(benchmark_returns, risk_free),
            "tracking_error": metrics.tracking_error(own_returns, benchmark_returns),
            "information_ratio": metrics.information_ratio(
                own_returns, benchmark_returns
            ),
        }
        return pd.Series(comparison, name=benchmark.name)

    def benchmark_overlap(self, benchmark: "Portfolio") -> pd.DataFrame:
        self._check_benchmark(benchmark)
        weights = {
            "portfolio_weight": self._weights_by_ticker(),
            "benchmark_weight": benchmark._weights_by_ticker(),
        }
        table = pd.concat(weights, axis=1, join="inner")
        table["overlap"] = table.min(axis=1)
        return table.rename_axis("asset")

    def benchmark_overlap_share(self, benchmark: "Portfolio") -> float:
        return float(self.benchmark_overlap(benchmark)["overlap"].sum())

    # Diversification

    def correlation(self) -> pd.DataFrame:
        return self.asset_returns().corr()

    def diversification_benefit(self) -> float:
        asset_returns = self.asset_returns()
        asset_volatilities = asset_returns.apply(metrics.annual_volatility)
        weighted_volatility = float(
            (self._weights_by_ticker() * asset_volatilities).sum()
        )
        return weighted_volatility - metrics.annual_volatility(self.returns())

    # Simulation

    def _simulation_inputs(
        self, mu: np.ndarray | None = None, cov: np.ndarray | None = None
    ) -> tuple[np.ndarray, np.ndarray]:
        asset_returns = self.asset_returns()
        tickers = list(asset_returns.columns)
        n_assets = len(tickers)
        assets = f"{n_assets}: {', '.join(tickers)}"
        # The 0.01 limits below catch annual values passed by mistake

        if mu is None:
            mu = asset_returns.mean().to_numpy()
        else:
            mu = np.asarray(mu, dtype=float)
            if mu.shape != (n_assets,):
                received = mu.shape[0] if mu.ndim == 1 else f"shape {mu.shape}"
                raise ValueError(
                    f"mu must have one value per asset ({assets}), got {received}"
                )
            not_finite = ~np.isfinite(mu)
            if not_finite.any():
                i = int(np.argmax(not_finite))  # first True
                raise ValueError(
                    f"mu for {tickers[i]} is {mu[i]}; all values of mu must be finite"
                )
            looks_annual = np.abs(mu) > 0.01
            if looks_annual.any():
                i = int(np.argmax(looks_annual))
                raise ValueError(
                    f"mu for {tickers[i]} is {mu[i]:g}, which looks annual; "
                    "mu must be a daily mean return"
                )

        if cov is None:
            cov = asset_returns.cov().to_numpy()
        else:
            cov = np.asarray(cov, dtype=float)
            if cov.shape != (n_assets, n_assets):
                raise ValueError(
                    f"cov must be a {n_assets} x {n_assets} matrix, one row and column "
                    f"per asset ({assets}), got shape {cov.shape}"
                )
            invalid = np.argwhere(~np.isfinite(cov))
            if len(invalid) > 0:
                row, column = invalid[0]
                raise ValueError(
                    f"cov for row {tickers[row]} and column {tickers[column]} is "
                    f"{cov[row, column]}; all values of cov must be finite"
                )
            variances = np.diag(cov)
            negative = variances < 0
            if negative.any():
                i = int(np.argmax(negative))  # first True
                raise ValueError(
                    f"cov diagonal for {tickers[i]} is {variances[i]:g}; "
                    "a variance cannot be negative"
                )
            looks_annual = variances > 0.01
            if looks_annual.any():
                i = int(np.argmax(looks_annual))
                raise ValueError(
                    f"cov diagonal for {tickers[i]} is {variances[i]:g} (a daily "
                    f"volatility of {variances[i] ** 0.5:.0%}), which looks annual; "
                    "cov must be the covariance of daily returns"
                )

        return mu, cov

    def simulation_assumptions(
        self, mu: np.ndarray | None = None, cov: np.ndarray | None = None
    ) -> pd.DataFrame:
        """Annual return and volatility from DAILY mu and cov, given in asset order."""
        mu, cov = self._simulation_inputs(mu, cov)
        return pd.DataFrame(
            {
                "annual_return": metrics.annualize_mean(mu),
                "annual_volatility": metrics.annualize_volatility(
                    np.sqrt(np.diag(cov))
                ),
            },
            index=pd.Index(self.prices.columns, name="asset"),
        )

    def monte_carlo(
        self,
        config: SimulationConfig | None = None,
        mu: np.ndarray | None = None,
        cov: np.ndarray | None = None,
        rebalance: bool = True,
    ) -> SimulationResult:
        config = SimulationConfig() if config is None else config
        mu, cov = self._simulation_inputs(mu, cov)

        simulated = simulate_returns(
            mu, cov, config.n_sims, config.horizon_days, config.seed
        )
        # Same columns, in the same order, as the returns behind mu and cov
        weights = self._weights_by_ticker().reindex(self.prices.columns).to_numpy()
        rebalance_every = 1 if rebalance else None
        paths = returns_to_paths(
            simulated, weights, config.initial_value, rebalance_every=rebalance_every
        )
        return SimulationResult(
            paths, config, rebalance_every=rebalance_every, mu=mu, cov=cov
        )
