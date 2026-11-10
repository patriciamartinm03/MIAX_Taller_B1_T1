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


UP_DOWN_PRICES = [100, 110, 99, 108.9, 98.01]  # returns +10 %, -10 %, +10 %, -10 %


def test_annual_return_of_up_down_10_percent_is_zero():
    # Mean of [0.1, -0.1, 0.1, -0.1] is 0, even though the price ends at 98.01
    series = make_series("USD", UP_DOWN_PRICES)
    assert series.annual_return == pytest.approx(0, abs=1e-12)


def test_annual_volatility_of_up_down_10_percent():
    # Sum of squared deviations 0.04; sqrt(0.04 / 3 * 252) = sqrt(3.36) = 1.8330
    series = make_series("USD", UP_DOWN_PRICES)
    assert series.annual_volatility == pytest.approx(1.8330, abs=1e-4)


def test_max_drawdown_measures_from_highest_price():
    # Highest price 110; worst fall 98.01 / 110 - 1 = -0.109
    series = make_series("USD", UP_DOWN_PRICES)
    assert series.max_drawdown == pytest.approx(-0.109)


def test_usd_asset_has_same_annual_metrics_in_usd():
    series = make_series("USD", UP_DOWN_PRICES)
    assert series.annual_return_usd == pytest.approx(series.annual_return)
    assert series.annual_volatility_usd == pytest.approx(series.annual_volatility)


def test_annual_volatility_usd_of_flat_eur_asset_comes_from_fx():
    # Constant price in EUR: no local volatility, all USD volatility is FX
    fx = pd.Series([1.00, 1.10, 1.05, 1.12, 1.08], index=DATES)
    series = make_series("EUR", [100] * 5, fx)
    assert series.annual_volatility == pytest.approx(0, abs=1e-12)
    assert series.annual_volatility_usd > 0


def test_prices_with_nan_still_fail():
    with pytest.raises(ValueError, match="empty values in prices"):
        make_series("USD", [100, None, 102, 103, 104])


# --- Statistics on creation and validation of the other fields ---------------


def build(**overrides) -> PriceSeries:
    """A valid USD series; any field can be overridden."""
    fields = {
        "ticker": "TEST",
        "name": "Test asset",
        "asset_type": "equity",
        "currency": "USD",
        "source": "test",
        "prices": pd.Series([100.0, 110.0, 99.0, 108.9, 98.01], index=DATES),
        "price_type": "close",
    }
    return PriceSeries(**(fields | overrides))


def test_mean_and_std_are_computed_on_creation():
    # Task 4.3: available as plain attributes right after instantiation
    series = build()
    returns = series.prices.pct_change(fill_method=None).dropna()
    assert series.mean_return == pytest.approx(returns.mean())
    assert series.std_return == pytest.approx(returns.std(ddof=1))  # sample std
    assert series.mean_return == pytest.approx(0, abs=1e-12)  # +10 %, -10 % twice


def test_statistics_are_not_constructor_arguments():
    with pytest.raises(TypeError):
        build(mean_return=0.5)


def test_unsorted_prices_are_sorted_by_date():
    prices = pd.Series([104.0, 103.0, 102.0, 101.0, 100.0], index=DATES[::-1])
    series = build(prices=prices)
    assert series.prices.index.is_monotonic_increasing
    assert series.prices.iloc[0] == 100.0
    assert series.mean_return > 0  # rising once sorted


@pytest.mark.parametrize(
    "field, given, stored",
    [("asset_type", "ETF", "etf"), ("price_type", "ADJ_CLOSE", "adj_close")],
)
def test_text_fields_are_lowercased(field, given, stored):
    assert getattr(build(**{field: given}), field) == stored


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"asset_type": "bond"}, "asset_type must be"),
        ({"price_type": "open"}, "price_type must be"),
        (
            {"prices": pd.Series([100.0, 101.0], index=DATES[:2])},
            "at least three prices",
        ),
        (
            {"prices": pd.Series([100.0, 101.0, 102.0], index=DATES[[0, 0, 1]])},
            "repeated dates in prices",
        ),
    ],
)
def test_invalid_fields_fail(overrides, message):
    with pytest.raises(ValueError, match=message):
        build(**overrides)


@pytest.mark.parametrize(
    "prices, message",
    [
        ([100.0, 101.0, 102.0], "must be a pandas Series"),
        (pd.Series([100.0, 101.0, 102.0]), "dates as its index"),
        (pd.Series(["a", "b", "c"], index=DATES[:3]), "must be numeric"),
    ],
)
def test_prices_must_be_a_numeric_dated_series(prices, message):
    with pytest.raises(TypeError, match=message):
        build(prices=prices)
