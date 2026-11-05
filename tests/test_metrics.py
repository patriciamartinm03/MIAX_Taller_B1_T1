import math

import numpy as np
import pandas as pd
import pytest

from miax_toolkit import metrics
from miax_toolkit.constants import TRADING_DAYS

DATES = pd.date_range("2026-01-05", periods=4, freq="B")
RETURNS = pd.Series(
    [0.01, -0.02, 0.015, 0.003, -0.007, 0.012],
    index=pd.date_range("2026-01-05", periods=6, freq="B"),
)


def test_cagr_from_100_to_121_in_two_years_is_10_percent():
    values = pd.Series(
        [100.0, 121.0], index=pd.to_datetime(["2020-01-01", "2022-01-01"])
    )
    assert metrics.cagr(values) == pytest.approx(0.10, abs=0.001)


def test_max_drawdown_details_with_recovery():
    values = pd.Series([100.0, 150.0, 90.0, 160.0], index=DATES)
    details = metrics.max_drawdown_details(values)
    assert details.max_drawdown == pytest.approx(-0.40)
    assert details.peak_date == DATES[1]
    assert details.trough_date == DATES[2]
    assert details.recovery_date == DATES[3]


def test_max_drawdown_details_without_recovery():
    values = pd.Series([100.0, 150.0, 90.0, 140.0], index=DATES)
    assert metrics.max_drawdown_details(values).recovery_date is None


def test_max_drawdown_details_always_rising():
    values = pd.Series([100.0, 110.0, 120.0, 130.0], index=DATES)
    details = metrics.max_drawdown_details(values)
    assert details.max_drawdown == 0
    assert details.peak_date == details.trough_date == details.recovery_date == DATES[0]


def test_cumulative_value_starts_at_initial_value():
    start = pd.Timestamp("2026-01-02")
    values = metrics.cumulative_value(RETURNS, start, initial_value=250.0)
    assert values.index[0] == start
    assert values.iloc[0] == 250.0
    assert len(values) == len(RETURNS) + 1
    assert values.iloc[1] == pytest.approx(250.0 * 1.01)


def test_sharpe_with_constant_rate_series_equals_fixed_number():
    annual_rates = pd.Series(
        [0.03, 0.03], index=pd.to_datetime(["2025-12-31", "2026-01-07"])
    )
    daily_rates = metrics.daily_risk_free(annual_rates, RETURNS.index)
    with_series = metrics.sharpe_ratio(RETURNS, daily_rates)
    with_number = metrics.sharpe_ratio(RETURNS, 0.03 / TRADING_DAYS)
    assert with_series == pytest.approx(with_number)


def test_sharpe_of_constant_returns_is_nan():
    returns = pd.Series(
        [0.01] * 10, index=pd.date_range("2026-01-05", periods=10, freq="B")
    )
    assert math.isnan(metrics.sharpe_ratio(returns))


def test_daily_returns_of_dataframe_by_column():
    prices = pd.DataFrame(
        {"A": [100.0, 110.0, 99.0], "B": [50.0, 50.0, 55.0]},
        index=DATES[:3],
    )
    returns = metrics.daily_returns(prices)
    assert list(returns.columns) == ["A", "B"]
    assert returns.index.equals(DATES[1:3])
    assert returns["A"].tolist() == pytest.approx([0.10, -0.10])
    assert returns["B"].tolist() == pytest.approx([0.0, 0.10])


def test_daily_returns_of_dataframe_with_bad_column_fails():
    prices = pd.DataFrame(
        {"A": [100.0, 110.0, 99.0], "B": [50.0, 0.0, 55.0]}, index=DATES[:3]
    )
    with pytest.raises(ValueError, match=r"less than or equal to 0 in prices\['B'\]"):
        metrics.daily_returns(prices)


def test_daily_risk_free_starting_late_fails():
    annual_rates = pd.Series([0.03, 0.03], index=RETURNS.index[1:3])
    with pytest.raises(ValueError, match="after the first date"):
        metrics.daily_risk_free(annual_rates, RETURNS.index)


def test_daily_risk_free_with_percentage_fails():
    annual_rates = pd.Series([4.0, 4.0], index=RETURNS.index[:2])
    with pytest.raises(ValueError, match="look like percentages"):
        metrics.daily_risk_free(annual_rates, RETURNS.index)


def test_daily_risk_free_accepts_negative_rate():
    annual_rates = pd.Series([-0.005, -0.004], index=RETURNS.index[:2])
    daily_rates = metrics.daily_risk_free(annual_rates, RETURNS.index)
    assert daily_rates.iloc[0] == pytest.approx(-0.005 / TRADING_DAYS)
    assert daily_rates.iloc[-1] == pytest.approx(-0.004 / TRADING_DAYS)


def test_portfolio_against_itself_has_no_tracking_error():
    assert metrics.tracking_error(RETURNS, RETURNS) == 0
    assert math.isnan(metrics.information_ratio(RETURNS, RETURNS))


def test_two_equal_weights_are_two_effective_assets():
    assert metrics.effective_n_assets([0.5, 0.5]) == pytest.approx(2)


def test_expected_shortfall_is_at_least_value_at_risk():
    final_values = np.random.default_rng(0).lognormal(np.log(100), 0.2, 1000)
    var = metrics.value_at_risk(final_values, 100.0)
    cvar = metrics.expected_shortfall(final_values, 100.0)
    assert cvar >= var


def test_value_at_risk_with_level_95_fails():
    final_values = np.array([90.0, 100.0, 110.0])
    with pytest.raises(ValueError, match="level must be a percentile"):
        metrics.value_at_risk(final_values, 100.0, level=95)


def test_refactored_metrics_give_same_results_as_before():
    prices = pd.Series([100.0, 103.0, 98.0, 105.0, 101.0, 110.0], index=RETURNS.index)
    assert metrics.annual_return(RETURNS) == float(RETURNS.mean()) * TRADING_DAYS
    assert (
        metrics.annual_volatility(RETURNS) == float(RETURNS.std()) * TRADING_DAYS**0.5
    )
    assert metrics.max_drawdown(prices) == float((prices / prices.cummax() - 1).min())
