import pandas as pd

from miax_toolkit.constants import TRADING_DAYS


def annual_return(returns: pd.Series) -> float:
    return float(returns.mean()) * TRADING_DAYS


def annual_volatility(returns: pd.Series) -> float:
    return float(returns.std()) * TRADING_DAYS**0.5


def max_drawdown(values: pd.Series) -> float:
    running_max = values.cummax()
    return float((values / running_max - 1).min())
