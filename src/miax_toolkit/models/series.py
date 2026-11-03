from dataclasses import dataclass, field

import pandas as pd


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

    mean_return: float = field(init=False)
    std_return: float = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.prices, pd.Series):
            raise TypeError("prices must be a pandas Series")
        if not isinstance(self.prices.index, pd.DatetimeIndex):
            raise TypeError("prices must have dates as its index")
        if not pd.api.types.is_numeric_dtype(self.prices):
            raise TypeError("prices must be numeric")
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
        if self.prices.isna().any():
            raise ValueError("There are empty prices (NaN)")
        if (self.prices <= 0).any():
            raise ValueError("There are prices less than or equal to 0")
        if self.prices.index.has_duplicates:
            raise ValueError("There are repeated dates")

        self.prices = self.prices.sort_index()

        returns = self.daily_returns()
        self.mean_return = float(returns.mean())
        self.std_return = float(returns.std())

    def daily_returns(self) -> pd.Series:
        """Simple daily returns (pct change between consecutive prices)."""
        return self.prices.pct_change().dropna()
