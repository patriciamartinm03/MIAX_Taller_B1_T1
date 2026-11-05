import pandas as pd
import pytest

from miax_toolkit.models.series import PriceSeries

DATES = pd.date_range("2026-01-05", periods=5, freq="B")


def make_series(currency: str, prices: list[float], fx_to_usd=None) -> PriceSeries:
    return PriceSeries(
        ticker="TEST",
        name="Test asset",
        asset_type="index",
        currency=currency,
        source="test",
        prices=pd.Series(prices, index=DATES),
        price_type="close",
        fx_to_usd=fx_to_usd,
    )


def test_usd_asset_without_fx_keeps_prices():
    series = make_series("USD", [100, 101, 102, 103, 104])
    pd.testing.assert_series_equal(series.usd_prices(), series.prices)


def test_currency_is_upper_case():
    series = make_series("usd", [100, 101, 102, 103, 104])
    assert series.currency == "USD"


def test_eur_price_is_multiplied_by_fx():
    fx = pd.Series([1.08] * 5, index=DATES)
    series = make_series("EUR", [100, 100, 100, 100, 100], fx)
    assert series.usd_prices().iloc[0] == pytest.approx(108)


def test_fx_with_extra_dates_is_cut_to_price_dates():
    fx_dates = pd.date_range("2026-01-01", periods=10, freq="D")
    fx = pd.Series(1.1, index=fx_dates)
    series = make_series("EUR", [100, 101, 102, 103, 104], fx)
    assert series.fx_to_usd.index.equals(series.prices.index)


def test_eur_asset_without_fx_fails():
    with pytest.raises(ValueError, match="fx_to_usd is required"):
        make_series("EUR", [100, 101, 102, 103, 104])


def test_usd_asset_with_fx_fails():
    fx = pd.Series([1.08] * 5, index=DATES)
    with pytest.raises(ValueError, match="fx_to_usd must be None"):
        make_series("USD", [100, 101, 102, 103, 104], fx)


def test_fx_missing_day_uses_last_known_rate():
    fx = pd.Series([1.10, 1.20, 1.30, 1.40], index=DATES.delete(2))
    series = make_series("EUR", [100, 100, 100, 100, 100], fx)
    assert series.usd_prices().iloc[2] == pytest.approx(120)


def test_fx_starting_after_prices_fails():
    fx = pd.Series([1.08] * 4, index=DATES[1:])
    with pytest.raises(ValueError, match="after the first price"):
        make_series("EUR", [100, 101, 102, 103, 104], fx)


def test_fx_ending_before_prices_fails():
    fx = pd.Series([1.08] * 4, index=DATES[:4])
    with pytest.raises(ValueError, match="before the last price"):
        make_series("EUR", [100, 101, 102, 103, 104], fx)


def test_usd_returns_include_fx_move():
    fx = pd.Series([1.00, 1.10, 1.10, 1.10, 1.10], index=DATES)
    series = make_series("EUR", [100, 100, 100, 100, 100], fx)
    assert series.mean_return == pytest.approx(0)
    assert series.daily_usd_returns().iloc[0] == pytest.approx(0.10)
    assert series.mean_return_usd == pytest.approx(0.10 / 4)


def test_usd_asset_has_same_returns_in_usd():
    series = make_series("USD", [100, 101, 99, 103, 104])
    assert series.mean_return_usd == pytest.approx(series.mean_return)
    assert series.std_return_usd == pytest.approx(series.std_return)


def test_fx_with_nan_fails():
    fx = pd.Series([1.08, None, 1.08, 1.08, 1.08], index=DATES)
    with pytest.raises(ValueError, match="empty values in fx_to_usd"):
        make_series("EUR", [100, 101, 102, 103, 104], fx)


def test_fx_with_zero_fails():
    fx = pd.Series([1.08, 0, 1.08, 1.08, 1.08], index=DATES)
    with pytest.raises(ValueError, match="less than or equal to 0 in fx_to_usd"):
        make_series("EUR", [100, 101, 102, 103, 104], fx)


def test_fx_with_negative_value_fails():
    fx = pd.Series([1.08, -1.08, 1.08, 1.08, 1.08], index=DATES)
    with pytest.raises(ValueError, match="less than or equal to 0 in fx_to_usd"):
        make_series("EUR", [100, 101, 102, 103, 104], fx)


def test_unsorted_fx_is_sorted_by_date():
    fx = pd.Series([1.1, 1.2, 1.3, 1.4, 1.5], index=DATES[::-1])
    series = make_series("EUR", [100, 101, 102, 103, 104], fx)
    assert series.fx_to_usd.index.is_monotonic_increasing
    assert series.fx_to_usd.iloc[0] == pytest.approx(1.5)


def test_prices_with_nan_still_fail():
    with pytest.raises(ValueError, match="empty values in prices"):
        make_series("USD", [100, None, 102, 103, 104])
