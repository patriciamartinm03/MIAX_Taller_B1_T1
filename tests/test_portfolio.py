import pandas as pd
import pytest

from miax_toolkit.models.portfolio import Portfolio
from miax_toolkit.models.series import PriceSeries

DATES = pd.date_range("2026-01-05", periods=5, freq="B")


def make_series(ticker: str, currency: str, prices: list[float], fx_to_usd=None):
    return PriceSeries(
        ticker=ticker,
        name=ticker,
        asset_type="index",
        currency=currency,
        source="test",
        prices=pd.Series(prices, index=DATES),
        price_type="close",
        fx_to_usd=fx_to_usd,
    )


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
