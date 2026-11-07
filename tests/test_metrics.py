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


def test_total_return_only_depends_on_first_and_last_value():
    # 110 / 100 - 1 = 0.10 in both cases, whatever happens in between
    calm = pd.Series([100.0, 120.0, 90.0, 110.0], index=DATES)
    wild = pd.Series([100.0, 50.0, 200.0, 110.0], index=DATES)
    assert metrics.total_return(calm) == pytest.approx(0.10)
    assert metrics.total_return(wild) == pytest.approx(0.10)


def test_drawdown_series_measures_fall_from_running_peak():
    # Running peak [100, 100, 120, 120, 120]
    # Day 4: 90 / 120 - 1 = -0.25 (measured from the latest peak, not from 100)
    dates = RETURNS.index[:5]
    prices = pd.Series([100.0, 80.0, 120.0, 90.0, 60.0], index=dates)
    drawdowns = metrics.drawdown_series(prices)
    assert drawdowns.tolist() == pytest.approx([0.0, -0.20, 0.0, -0.25, -0.50])
    assert drawdowns.index.equals(dates)


def test_excess_returns_subtracts_fixed_rate_every_day():
    returns = pd.Series([0.02, -0.01, 0.03], index=DATES[1:])
    excess = metrics.excess_returns(returns, 0.001)
    assert excess.tolist() == pytest.approx([0.019, -0.011, 0.029])


def test_excess_returns_matches_rate_series_by_date():
    # The rate on DATES[0] has no return and is ignored; matching by position
    # instead of by date would give [0.0195, -0.011, 0.028]
    returns = pd.Series([0.02, -0.01, 0.03], index=DATES[1:])
    rates = pd.Series([0.0005, 0.001, 0.002, 0.003], index=DATES)
    excess = metrics.excess_returns(returns, rates)
    assert excess.tolist() == pytest.approx([0.019, -0.012, 0.027])
    assert excess.index.equals(DATES[1:])


def test_active_returns_uses_only_common_dates():
    # Portfolio has DATES[0:3], benchmark has DATES[1:4] -> common DATES[1:3]
    # 0.01 - 0.015 = -0.005; -0.01 - (-0.02) = 0.01
    returns = pd.Series([0.02, 0.01, -0.01], index=DATES[0:3])
    benchmark = pd.Series([0.015, -0.02, 0.01], index=DATES[1:4])
    active = metrics.active_returns(returns, benchmark)
    assert active.tolist() == pytest.approx([-0.005, 0.01])
    assert active.index.equals(DATES[1:3])


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


def test_sortino_without_risk_free_matches_hand_calculation():
    # mean = 0.005; downside = sqrt((0.01² + 0.02²) / 4) = 0.0111803
    # sortino = 0.005 * 252 / (0.0111803 * sqrt(252)) = 7.0993
    returns = pd.Series([0.02, -0.01, 0.03, -0.02], index=DATES)
    assert metrics.sortino_ratio(returns) == pytest.approx(7.0993, abs=1e-4)


def test_sortino_with_risk_free_counts_returns_below_rf_as_downside():
    # excess = [0.02, -0.005, -0.02, 0.01]: the +0.5 % day is below rf (1 %)
    # mean = 0.00125; downside = sqrt((0.005² + 0.02²) / 4) = 0.0103078
    # sortino = 0.00125 * 252 / (0.0103078 * sqrt(252)) = 1.9251
    returns = pd.Series([0.03, 0.005, -0.01, 0.02], index=DATES)
    assert metrics.sortino_ratio(returns, 0.01) == pytest.approx(1.9251, abs=1e-4)


def test_sortino_downside_ignores_size_of_positive_returns():
    # Same as the hand calculation above, but the +0.03 day becomes +0.05.
    # It is still positive, so it still counts as 0 in the downside and as one
    # of the 4 days: downside = sqrt((0.01² + 0.02²) / 4) = 0.0111803, unchanged.
    # Only the mean changes: 0.005 -> 0.04 / 4 = 0.01, so the ratio doubles:
    # 2 * 7.0993 = 14.1986
    returns = pd.Series([0.02, -0.01, 0.05, -0.02], index=DATES)
    assert metrics.sortino_ratio(returns) == pytest.approx(14.1986, abs=1e-4)


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


FINAL_VALUES = np.array([110.0, 80.0, 120.0, 100.0, 90.0])


def test_prob_loss_counts_only_values_strictly_below_initial():
    # Below 100: 80 and 90 (100 itself is not a loss) -> 2 / 5
    assert metrics.prob_loss(FINAL_VALUES, 100.0) == pytest.approx(0.4)


def test_value_at_risk_and_expected_shortfall_at_exact_percentile():
    # Sorted [80, 90, 100, 110, 120]; position (5 - 1) * 25 / 100 = 1 -> 90
    # VaR = 1 - 90 / 100; tail <= 90 is [80, 90], mean 85 -> ES = 1 - 85 / 100
    var = metrics.value_at_risk(FINAL_VALUES, 100.0, level=25)
    es = metrics.expected_shortfall(FINAL_VALUES, 100.0, level=25)
    assert var == pytest.approx(0.10)
    assert es == pytest.approx(0.15)


def test_value_at_risk_interpolates_between_values():
    # Position 4 * 10 / 100 = 0.4 -> 80 + 0.4 * (90 - 80) = 84 -> VaR = 0.16
    # Tail <= 84 is only [80] -> ES = 1 - 80 / 100 = 0.20
    var = metrics.value_at_risk(FINAL_VALUES, 100.0, level=10)
    es = metrics.expected_shortfall(FINAL_VALUES, 100.0, level=10)
    assert var == pytest.approx(0.16)
    assert es == pytest.approx(0.20)


def test_value_at_risk_with_level_95_fails():
    final_values = np.array([90.0, 100.0, 110.0])
    with pytest.raises(ValueError, match="level must be a percentile"):
        metrics.value_at_risk(final_values, 100.0, level=95)


def test_annual_return_is_daily_mean_times_252():
    # mean = (0.01 - 0.01 + 0.02 + 0) / 4 = 0.005 -> 0.005 * 252 = 1.26
    returns = pd.Series([0.01, -0.01, 0.02, 0.0], index=DATES)
    assert metrics.annual_return(returns) == pytest.approx(1.26)


def test_annual_volatility_uses_sample_std():
    # squared deviations sum 0.0005; sample variance = 0.0005 / 3 (n - 1)
    # sqrt(0.0005 / 3 * 252) = sqrt(0.042) = 0.2049 (dividing by n would give 0.1775)
    returns = pd.Series([0.01, -0.01, 0.02, 0.0], index=DATES)
    assert metrics.annual_volatility(returns) == pytest.approx(0.2049, abs=1e-4)


def test_max_drawdown_is_worst_fall_from_previous_peak():
    # Falls: 98 / 103 - 1 = -0.04854 and 101 / 105 - 1 = -0.03810 -> worst -0.0485
    prices = pd.Series([100.0, 103.0, 98.0, 105.0, 101.0, 110.0], index=RETURNS.index)
    assert metrics.max_drawdown(prices) == pytest.approx(-0.0485, abs=1e-4)
