import pandas as pd
import pytest

from miax_toolkit import metrics
from miax_toolkit.constants import TRADING_DAYS


def test_annual_return_scales_mean_by_trading_days():
    returns = pd.Series([0.01, -0.01, 0.02, 0.0])
    assert metrics.annual_return(returns) == pytest.approx(0.005 * TRADING_DAYS)


def test_annual_volatility_scales_std_by_sqrt_trading_days():
    returns = pd.Series([0.01, -0.01, 0.02, 0.0])
    expected = returns.std() * TRADING_DAYS**0.5
    assert metrics.annual_volatility(returns) == pytest.approx(expected)


def test_max_drawdown_is_largest_drop_from_running_peak():
    # Peak 120, trough 90 -> -25 %. The later new high does not undo it.
    values = pd.Series([100.0, 120.0, 90.0, 130.0])
    assert metrics.max_drawdown(values) == pytest.approx(-0.25)


def test_max_drawdown_is_zero_for_rising_series():
    assert metrics.max_drawdown(pd.Series([1.0, 2.0, 3.0])) == 0.0
