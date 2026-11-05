from datetime import date

import pandas as pd
import pytest

from miax_toolkit.models.macro import MacroSeries
from miax_toolkit.models.portfolio import Portfolio
from miax_toolkit.models.series import PriceSeries

DATES = pd.date_range("2026-01-05", periods=5, freq="B")


def make_series(
    ticker: str, currency: str, prices: list[float], fx_to_usd=None, dates=DATES
):
    return PriceSeries(
        ticker=ticker,
        name=ticker,
        asset_type="index",
        currency=currency,
        source="test",
        prices=pd.Series(prices, index=dates),
        price_type="close",
        fx_to_usd=fx_to_usd,
    )


def make_rate(values: list[float], dates, currency="USD", units="percent"):
    return MacroSeries(
        series_id="DTB3",
        name="3-month Treasury bill",
        units=units,
        source="test",
        as_of=date(2026, 1, 31),
        values=pd.Series(values, index=dates),
        currency=currency,
    )


SPX = make_series("SPX", "USD", [100, 101, 102, 103, 104])
RATE_DATES = pd.to_datetime(["2026-01-01", "2026-01-07"])


def test_portfolio_mixes_currencies_in_usd():
    spx = make_series("SPX", "USD", [100, 101, 102, 103, 104])
    fx = pd.Series([1.10, 1.10, 1.20, 1.20, 1.20], index=DATES)
    ibex = make_series("IBEX", "EUR", [100, 100, 100, 100, 100], fx)

    portfolio = Portfolio("Test", [spx, ibex], [0.5, 0.5])

    assert portfolio.prices["SPX"].iloc[0] == pytest.approx(100)
    assert portfolio.prices["IBEX"].iloc[0] == pytest.approx(110)
    assert portfolio.prices["IBEX"].iloc[2] == pytest.approx(120)


def test_fx_move_shows_in_returns():
    fx = pd.Series([1.00, 1.00, 1.10, 1.10, 1.10], index=DATES)
    ibex = make_series("IBEX", "EUR", [100, 100, 100, 100, 100], fx)

    portfolio = Portfolio("Test", [ibex], [1.0])

    assert portfolio.asset_returns()["IBEX"].iloc[1] == pytest.approx(0.10)


def test_nan_weight_fails_as_invalid_weight():
    other = make_series("NDX", "USD", [100, 102, 101, 104, 105])
    with pytest.raises(ValueError, match="weights must be finite numbers"):
        Portfolio("Test", [SPX, other], [float("nan"), 0.5])


def test_few_common_dates_error_shows_each_asset_range():
    late = make_series(
        "LATE",
        "USD",
        [50, 51, 52, 53, 54],
        dates=pd.date_range("2026-01-08", periods=5, freq="B"),
    )
    with pytest.raises(ValueError) as error:
        Portfolio("Test", [SPX, late], [0.5, 0.5])
    message = str(error.value)
    assert "SPX: 2026-01-05 to 2026-01-09" in message
    assert "LATE: 2026-01-08 to 2026-01-14" in message


def test_risk_free_in_eur_fails():
    rate = make_rate([3.0, 3.1], RATE_DATES, currency="EUR")
    with pytest.raises(ValueError, match="risk_free must be in USD"):
        Portfolio("Test", [SPX], [1.0], rate)


def test_risk_free_with_wrong_units_fails():
    rate = make_rate([118.0, 119.0], RATE_DATES, units="index")
    with pytest.raises(ValueError, match="risk_free units must be"):
        Portfolio("Test", [SPX], [1.0], rate)


def test_risk_free_starting_after_prices_fails():
    rate = make_rate([3.0, 3.1], pd.to_datetime(["2026-01-07", "2026-01-08"]))
    with pytest.raises(ValueError, match="after the first date"):
        Portfolio("Test", [SPX], [1.0], rate)


def test_risk_free_daily_has_same_dates_as_asset_returns():
    rate = make_rate([3.0, 3.6], RATE_DATES)
    portfolio = Portfolio("Test", [SPX], [1.0], rate)
    daily = portfolio.risk_free_daily()
    assert daily.index.equals(portfolio.asset_returns().index)
    assert daily.iloc[0] == pytest.approx(0.030 / 252)
    assert daily.iloc[-1] == pytest.approx(0.036 / 252)


def test_risk_free_daily_without_risk_free_is_zero():
    assert Portfolio("Test", [SPX], [1.0]).risk_free_daily() == 0.0
