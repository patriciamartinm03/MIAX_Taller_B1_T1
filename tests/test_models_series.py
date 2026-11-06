import numpy as np
import pandas as pd
import pytest
from conftest import business_days

from miax_toolkit import metrics
from miax_toolkit.models import PriceSeries


def make_series(prices=None, **overrides) -> PriceSeries:
    if prices is None:
        prices = pd.Series([100.0, 102.0, 101.0, 105.0], index=business_days(4))
    fields = {
        "ticker": "AAPL",
        "name": "Apple Inc.",
        "asset_type": "equity",
        "currency": "USD",
        "source": "test",
        "prices": prices,
        "price_type": "adj_close",
    }
    fields.update(overrides)
    return PriceSeries(**fields)


def test_valid_series_computes_return_stats():
    series = make_series()
    returns = series.prices.pct_change().dropna()
    assert series.mean_return == pytest.approx(returns.mean())
    assert series.std_return == pytest.approx(returns.std())


def test_daily_returns_has_one_fewer_value_than_prices():
    series = make_series()
    assert len(series.daily_returns()) == len(series.prices) - 1


def test_prices_are_sorted_by_date():
    index = business_days(4)
    shuffled = pd.Series([4.0, 1.0, 3.0, 2.0], index=index[[3, 0, 2, 1]])
    series = make_series(shuffled)
    assert series.prices.index.is_monotonic_increasing
    assert list(series.prices) == [1.0, 2.0, 3.0, 4.0]


def test_asset_type_and_price_type_are_lowercased():
    series = make_series(asset_type="ETF", price_type="CLOSE")
    assert series.asset_type == "etf"
    assert series.price_type == "close"


def test_annual_properties_delegate_to_metrics():
    series = make_series()
    returns = series.daily_returns()
    assert series.annual_return == pytest.approx(metrics.annual_return(returns))
    assert series.annual_volatility == pytest.approx(metrics.annual_volatility(returns))
    assert series.max_drawdown == pytest.approx(metrics.max_drawdown(series.prices))


@pytest.mark.parametrize(
    ("prices", "error"),
    [
        ([100.0, 101.0, 102.0], TypeError),  # a list, not a Series
        (pd.Series([100.0, 101.0, 102.0]), TypeError),  # index is not dates
        (pd.Series(["a", "b", "c"], index=business_days(3)), TypeError),
        (pd.Series([100.0, 101.0], index=business_days(2)), ValueError),  # < 3
        (pd.Series([100.0, np.nan, 102.0], index=business_days(3)), ValueError),
        (pd.Series([100.0, 0.0, 102.0], index=business_days(3)), ValueError),
        (pd.Series([100.0, -1.0, 102.0], index=business_days(3)), ValueError),
    ],
    ids=["list", "no-dates", "non-numeric", "too-short", "nan", "zero", "negative"],
)
def test_invalid_prices_are_rejected(prices, error):
    with pytest.raises(error):
        make_series(prices)


def test_duplicate_dates_are_rejected():
    index = pd.DatetimeIndex(["2024-01-02", "2024-01-02", "2024-01-03"])
    with pytest.raises(ValueError, match="repeated dates"):
        make_series(pd.Series([100.0, 101.0, 102.0], index=index))


@pytest.mark.parametrize("field", ["asset_type", "price_type"])
def test_unknown_categories_are_rejected(field):
    with pytest.raises(ValueError, match=field):
        make_series(**{field: "crypto"})
