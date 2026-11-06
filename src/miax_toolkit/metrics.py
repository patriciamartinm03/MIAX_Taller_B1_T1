from dataclasses import dataclass

import numpy as np
import pandas as pd

from miax_toolkit.constants import TRADING_DAYS

FloatOrArray = float | np.ndarray


def _check_series(
    values: pd.Series,
    label: str,
    dated: bool = False,
    positive: bool = False,
    min_values: int = 2,
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
    if len(values) < min_values:
        raise ValueError(f"{label} needs at least {min_values} values")
    if positive and (values <= 0).any():
        raise ValueError(f"There are values less than or equal to 0 in {label}")


def _check_number(value: float, label: str, positive: bool = False) -> None:
    if not np.isfinite(value):
        raise ValueError(f"{label} must be a finite number")
    if positive and value <= 0:
        raise ValueError(f"{label} must be positive")


def _to_float_or_array(value: FloatOrArray, label: str) -> FloatOrArray:
    array = np.asarray(value, dtype=float)
    if np.isnan(array).any():
        raise ValueError(f"There are empty values in {label} (NaN)")
    return float(array) if array.ndim == 0 else array


def _check_final_values(final_values: np.ndarray, initial_value: float) -> np.ndarray:
    _check_number(initial_value, "initial_value", positive=True)
    values = np.asarray(final_values, dtype=float)
    if values.ndim != 1:
        raise ValueError("final_values must be a 1D array")
    _check_series(pd.Series(values), "final_values", positive=True)
    return values


def _tail_threshold(values: np.ndarray, level: float) -> float:
    if not 0 < level <= 50:
        raise ValueError(
            f"level must be a percentile in (0, 50], e.g. 5 for a 95 % VaR; got {level}"
        )
    return float(np.percentile(values, level))


def _loss_fraction(value: float, initial_value: float) -> float:
    return float(1 - value / initial_value)


# Basic pieces


def daily_returns(prices: pd.Series | pd.DataFrame) -> pd.Series | pd.DataFrame:
    if isinstance(prices, pd.DataFrame):
        if prices.shape[1] == 0:
            raise ValueError("prices must have at least one column")
        for column in prices.columns:
            _check_series(prices[column], f"prices['{column}']", positive=True)
    else:
        _check_series(prices, "prices", positive=True)
    return prices.pct_change(fill_method=None).dropna()


def total_return(values: pd.Series) -> float:
    _check_series(values, "values", positive=True)
    return float(values.iloc[-1] / values.iloc[0] - 1)


def cumulative_value(
    returns: pd.Series, start_date: pd.Timestamp | str, initial_value: float = 100.0
) -> pd.Series:
    _check_series(returns, "returns", dated=True)
    _check_number(initial_value, "initial_value", positive=True)
    start = pd.Timestamp(start_date)
    first_return_date = returns.index[0]
    if start >= first_return_date:
        raise ValueError(
            f"start_date ({start.date()}) must be before the first return date "
            f"({first_return_date.date()})"
        )
    start_value = pd.Series(
        [initial_value], index=pd.DatetimeIndex([start]), name=returns.name
    )
    return pd.concat([start_value, initial_value * (1 + returns).cumprod()])


def drawdown_series(values: pd.Series) -> pd.Series:
    _check_series(values, "values", positive=True)
    return values / values.cummax() - 1


def annualize_mean(daily_mean: FloatOrArray) -> FloatOrArray:
    daily_mean = _to_float_or_array(daily_mean, "daily_mean")
    return daily_mean * TRADING_DAYS


def annualize_volatility(daily_std: FloatOrArray) -> FloatOrArray:
    daily_std = _to_float_or_array(daily_std, "daily_std")
    if np.any(daily_std < 0):
        raise ValueError("daily_std cannot be negative")
    return daily_std * TRADING_DAYS**0.5


def excess_returns(returns: pd.Series, risk_free_daily: float | pd.Series) -> pd.Series:
    if not isinstance(risk_free_daily, pd.Series):
        _check_series(returns, "returns")
        _check_number(risk_free_daily, "risk_free_daily")
        return returns - risk_free_daily

    _check_series(returns, "returns", dated=True)
    _check_series(risk_free_daily, "risk_free_daily", dated=True)
    missing = returns.index.difference(risk_free_daily.index)
    if len(missing) > 0:
        raise ValueError(
            f"risk_free_daily is missing {len(missing)} dates of returns "
            f"(first missing: {missing[0].date()})"
        )
    return returns - risk_free_daily.reindex(returns.index)


def active_returns(returns: pd.Series, benchmark_returns: pd.Series) -> pd.Series:
    _check_series(returns, "returns", dated=True)
    _check_series(benchmark_returns, "benchmark_returns", dated=True)
    common = returns.index.intersection(benchmark_returns.index).sort_values()
    if len(common) < 2:
        raise ValueError(
            "returns and benchmark_returns need at least 2 dates in common, "
            f"found {len(common)}"
        )
    return returns.loc[common] - benchmark_returns.loc[common]


# Metrics


def annual_return(returns: pd.Series) -> float:
    _check_series(returns, "returns")
    return float(annualize_mean(float(returns.mean())))


def annual_volatility(returns: pd.Series) -> float:
    _check_series(returns, "returns")
    return float(annualize_volatility(float(returns.std())))


def cagr(values: pd.Series) -> float:
    _check_series(values, "values", dated=True, positive=True)
    calendar_days = (values.index[-1] - values.index[0]).days
    return float((1 + total_return(values)) ** (365.25 / calendar_days) - 1)


def max_drawdown(values: pd.Series) -> float:
    return float(drawdown_series(values).min())


@dataclass(frozen=True)
class DrawdownDetails:
    max_drawdown: float
    peak_date: pd.Timestamp
    trough_date: pd.Timestamp
    recovery_date: pd.Timestamp | None


def max_drawdown_details(values: pd.Series) -> DrawdownDetails:
    _check_series(values, "values", dated=True, positive=True)
    drawdowns = drawdown_series(values)
    deepest = float(drawdowns.min())
    if deepest == 0:
        first_date = values.index[0]
        return DrawdownDetails(0.0, first_date, first_date, first_date)

    trough_date = drawdowns.idxmin()
    before_trough = drawdowns.loc[:trough_date]
    peak_date = before_trough[before_trough == 0].index[-1]
    after_trough = drawdowns.loc[trough_date:].iloc[1:]
    recovered = after_trough[after_trough == 0]
    recovery_date = recovered.index[0] if len(recovered) > 0 else None
    return DrawdownDetails(deepest, peak_date, trough_date, recovery_date)


def daily_risk_free(annual_rates: pd.Series, dates: pd.DatetimeIndex) -> pd.Series:
    _check_series(annual_rates, "annual_rates", dated=True, min_values=1)
    if not isinstance(dates, pd.DatetimeIndex) or len(dates) == 0:
        raise TypeError("dates must be a non-empty pandas DatetimeIndex")
    if (annual_rates.abs() > 0.5).any():
        raise ValueError(
            "annual_rates must be in decimals (0.05 = 5 %); some values are above "
            "0.5 in absolute value and look like percentages"
        )
    first_rate_date, first_date = annual_rates.index[0], dates.min()
    if first_rate_date > first_date:
        raise ValueError(
            f"annual_rates starts on {first_rate_date.date()}, "
            f"after the first date ({first_date.date()})"
        )
    return annual_rates.reindex(dates, method="ffill") / TRADING_DAYS


def sharpe_ratio(returns: pd.Series, risk_free_daily: float | pd.Series = 0.0) -> float:
    excess = excess_returns(returns, risk_free_daily)
    volatility = annual_volatility(excess)
    if np.isclose(volatility, 0):
        return float("nan")
    return annual_return(excess) / volatility


def sortino_ratio(
    returns: pd.Series, risk_free_daily: float | pd.Series = 0.0
) -> float:
    excess = excess_returns(returns, risk_free_daily)
    daily_downside = float(np.sqrt((excess.clip(upper=0) ** 2).mean()))
    downside_risk = float(annualize_volatility(daily_downside))
    if np.isclose(downside_risk, 0):
        return float("nan")
    return annual_return(excess) / downside_risk


def tracking_error(returns: pd.Series, benchmark_returns: pd.Series) -> float:
    return annual_volatility(active_returns(returns, benchmark_returns))


def information_ratio(returns: pd.Series, benchmark_returns: pd.Series) -> float:
    error = tracking_error(returns, benchmark_returns)
    if np.isclose(error, 0):
        return float("nan")
    return annual_return(active_returns(returns, benchmark_returns)) / error


def effective_n_assets(weights: list[float] | np.ndarray | pd.Series) -> float:
    weights = np.asarray(weights, dtype=float)
    if weights.ndim != 1 or weights.size == 0:
        raise ValueError("weights must be a non-empty 1D list of numbers")
    if np.isnan(weights).any():
        raise ValueError("There are empty values in weights (NaN)")
    sum_of_squares = float((weights**2).sum())
    if sum_of_squares == 0:
        raise ValueError("weights cannot all be 0")
    return 1 / sum_of_squares


def prob_loss(final_values: np.ndarray, initial_value: float) -> float:
    values = _check_final_values(final_values, initial_value)
    return float((values < initial_value).mean())


def value_at_risk(
    final_values: np.ndarray, initial_value: float, level: float = 5.0
) -> float:
    values = _check_final_values(final_values, initial_value)
    return _loss_fraction(_tail_threshold(values, level), initial_value)


def expected_shortfall(
    final_values: np.ndarray, initial_value: float, level: float = 5.0
) -> float:
    values = _check_final_values(final_values, initial_value)
    tail = values[values <= _tail_threshold(values, level)]
    return _loss_fraction(float(tail.mean()), initial_value)
