import pandas as pd

from miax_toolkit.constants import TRADING_DAYS


def validate_price_series(values: pd.Series, label: str) -> None:
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


def daily_returns(prices: pd.Series) -> pd.Series:
    return prices.pct_change(fill_method=None).dropna()


def annual_return(returns: pd.Series) -> float:
    return float(returns.mean()) * TRADING_DAYS


def annual_volatility(returns: pd.Series) -> float:
    return float(returns.std()) * TRADING_DAYS**0.5


def max_drawdown(values: pd.Series) -> float:
    running_max = values.cummax()
    return float((values / running_max - 1).min())
