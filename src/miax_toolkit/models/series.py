from dataclasses import dataclass, field

import pandas as pd

from miax_toolkit import metrics
from miax_toolkit.constants import BASE_CURRENCY


def _validate_series(values: pd.Series, label: str) -> None:
    if not isinstance(values, pd.Series):
        raise TypeError(f"{label} must be a pandas Series")
    if not isinstance(values.index, pd.DatetimeIndex):
        raise TypeError(f"{label} must have dates as its index")
    if not pd.api.types.is_numeric_dtype(values):
        raise TypeError(f"{label} must be numeric")
    if values.isna().any():
        raise ValueError(f"There are empty values in {label} (NaN)")
    if (values <= 0).any():
        raise ValueError(f"There are values less than or equal to 0 in {label}")
    if values.index.has_duplicates:
        raise ValueError(f"There are repeated dates in {label}")


@dataclass
class PriceSeries:
    """Price series of an asset, with validation and basic return statistics."""

    ticker: str
    name: str
    asset_type: str
    currency: str
    source: str
    prices: pd.Series = field(repr=False)
    price_type: str
    fx_to_usd: pd.Series | None = field(default=None, repr=False)

    mean_return: float = field(init=False)
    std_return: float = field(init=False)
    mean_return_usd: float = field(init=False)
    std_return_usd: float = field(init=False)

    def __post_init__(self) -> None:
        _validate_series(self.prices, "prices")
        self.asset_type = self.asset_type.lower()
        if self.asset_type not in ("equity", "etf", "index"):
            raise ValueError(
                f"asset_type must be 'equity', 'etf' or 'index', not '{self.asset_type}'"
            )
        self.price_type = self.price_type.lower()
        if self.price_type not in ("close", "adj_close"):
            raise ValueError(
                f"price_type must be 'close' or 'adj_close', not '{self.price_type}'"
            )
        if len(self.prices) < 3:
            raise ValueError(
                "Need at least three prices to calculate mean and std of returns"
            )

        self.prices = self.prices.sort_index()

        self.currency = self.currency.upper()
        if self.currency == BASE_CURRENCY:
            if self.fx_to_usd is not None:
                raise ValueError(
                    f"fx_to_usd must be None for assets in {BASE_CURRENCY}"
                )
        else:
            if self.fx_to_usd is None:
                raise ValueError(f"fx_to_usd is required for assets in {self.currency}")
            _validate_series(self.fx_to_usd, "fx_to_usd")
            self.fx_to_usd = self.fx_to_usd.sort_index()
            first_fx, last_fx = self.fx_to_usd.index[0], self.fx_to_usd.index[-1]
            first_price, last_price = self.prices.index[0], self.prices.index[-1]
            if first_fx > first_price:
                raise ValueError(
                    f"fx_to_usd starts on {first_fx.date()}, "
                    f"after the first price ({first_price.date()})"
                )
            if last_fx < last_price:
                raise ValueError(
                    f"fx_to_usd ends on {last_fx.date()}, "
                    f"before the last price ({last_price.date()})"
                )
            self.fx_to_usd = self.fx_to_usd.reindex(self.prices.index, method="ffill")

        returns = self.daily_returns()
        self.mean_return = float(returns.mean())
        self.std_return = float(returns.std())

        usd_returns = self.daily_usd_returns()
        self.mean_return_usd = float(usd_returns.mean())
        self.std_return_usd = float(usd_returns.std())

    def daily_returns(self) -> pd.Series:
        return metrics.daily_returns(self.prices)

    def daily_usd_returns(self) -> pd.Series:
        return metrics.daily_returns(self.usd_prices())

    def usd_prices(self) -> pd.Series:
        if self.currency == BASE_CURRENCY:
            return self.prices
        return self.prices * self.fx_to_usd

    @property
    def annual_return(self) -> float:
        """Annualized mean return in the asset's local currency."""
        return metrics.annual_return(self.daily_returns())

    @property
    def annual_volatility(self) -> float:
        """Annualized volatility in the asset's local currency."""
        return metrics.annual_volatility(self.daily_returns())

    @property
    def annual_return_usd(self) -> float:
        """Annualized mean return in USD (BASE_CURRENCY), including the FX effect."""
        return metrics.annual_return(self.daily_usd_returns())

    @property
    def annual_volatility_usd(self) -> float:
        """Annualized volatility in USD (BASE_CURRENCY), including the FX effect."""
        return metrics.annual_volatility(self.daily_usd_returns())

    @property
    def max_drawdown(self) -> float:
        return metrics.max_drawdown(self.prices)
