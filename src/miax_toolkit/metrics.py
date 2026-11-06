import pandas as pd

from miax_toolkit.constants import TRADING_DAYS


def annual_return(returns: pd.Series) -> float:
    return float(returns.mean()) * TRADING_DAYS


def annual_volatility(returns: pd.Series) -> float:
    return float(returns.std()) * TRADING_DAYS**0.5


def max_drawdown(values: pd.Series) -> float:
    running_max = values.cummax()
    return float((values / running_max - 1).min())


def _check_series(
    values: pd.Series, label: str, dated: bool = False, positive: bool = False
) -> None:
    if not isinstance(values, pd.Series):
        raise TypeError(f"{label} must be a pandas Series")
    if dated:
        if not isinstance(values.index, pd.DatetimeIndex):
            raise TypeError(f"{label} must have dates as its index")
        if values.index.has_duplicates or not values.index.is_monotonic_increasing:
            raise ValueError(f"{label} must be sorted by date with no repeated dates")
    if not pd.api.types.is_numeric_dtype(values):
        raise TypeError(f"{label} must be numeric")
    if values.isna().any():
        raise ValueError(f"There are empty values in {label} (NaN)")
    if len(values) < 2:
        raise ValueError(f"{label} needs at least 2 values")
    if positive and (values <= 0).any():
        raise ValueError(f"There are values less than or equal to 0 in {label}")


def daily_returns(prices: pd.Series | pd.DataFrame) -> pd.Series | pd.DataFrame:
    if isinstance(prices, pd.DataFrame):
        if prices.shape[1] == 0:
            raise ValueError("prices must have at least one column")
        for column in prices.columns:
            _check_series(prices[column], f"prices['{column}']", positive=True)
    else:
        _check_series(prices, "prices", positive=True)
    return prices.pct_change(fill_method=None).dropna()
