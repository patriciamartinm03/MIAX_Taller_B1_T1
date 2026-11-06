from datetime import date
from typing import ClassVar

import pandas as pd
import pytest
from conftest import business_days

from miax_toolkit.extraction import yfinance_provider
from miax_toolkit.extraction.yfinance_provider import YFinanceProvider

START, END = date(2024, 1, 2), date(2024, 1, 8)


class FakeTicker:
    """Stands in for yfinance.Ticker. Configure the class attributes per test."""

    history_frame: ClassVar[pd.DataFrame] = pd.DataFrame()
    metadata: ClassVar[dict] = {}
    calls: ClassVar[list[dict]] = []

    def __init__(self, ticker: str) -> None:
        self.ticker = ticker

    def history(self, **kwargs):
        FakeTicker.calls.append(kwargs)
        return self.history_frame

    def get_history_metadata(self):
        return self.metadata


def yahoo_history() -> pd.DataFrame:
    # Yahoo returns timestamps in the exchange's timezone.
    return pd.DataFrame(
        {
            "Close": [180.0, 182.0, 181.0, 185.0, 186.0],
            "Adj Close": [179.0, float("nan"), 180.0, 184.0, 185.0],
        },
        index=business_days(5, tz="America/New_York"),
    )


@pytest.fixture(autouse=True)
def fake_ticker(monkeypatch):
    FakeTicker.history_frame = yahoo_history()
    FakeTicker.metadata = {
        "instrumentType": "EQUITY",
        "currency": "USD",
        "longName": "Apple Inc.",
        "shortName": "Apple",
    }
    FakeTicker.calls = []
    monkeypatch.setattr(yfinance_provider.yf, "Ticker", FakeTicker)


def test_builds_adj_close_series_from_yahoo_data():
    series = YFinanceProvider().get_prices("AAPL", START, END)
    assert (series.ticker, series.name) == ("AAPL", "Apple Inc.")
    assert (series.asset_type, series.currency) == ("equity", "USD")
    assert (series.source, series.price_type) == ("yfinance", "adj_close")
    assert list(series.prices) == [179.0, 180.0, 184.0, 185.0]  # NaN dropped
    assert series.prices.index.tz is None
    assert series.prices.index[0] == pd.Timestamp("2024-01-02")


def test_close_price_type_uses_close_column():
    series = YFinanceProvider(price_type="close").get_prices("AAPL", START, END)
    assert list(series.prices) == [180.0, 182.0, 181.0, 185.0, 186.0]


def test_end_date_is_made_inclusive_and_prices_unadjusted():
    YFinanceProvider().get_prices("AAPL", START, END)
    call = FakeTicker.calls[-1]
    assert call["start"] == START
    assert call["end"] == date(2024, 1, 9)  # Yahoo's end is exclusive
    assert call["auto_adjust"] is False
    assert call["interval"] == "1d"


@pytest.mark.parametrize(
    ("instrument", "expected"),
    [("EQUITY", "equity"), ("ETF", "etf"), ("INDEX", "index")],
)
def test_instrument_type_is_mapped(instrument, expected):
    FakeTicker.metadata["instrumentType"] = instrument
    assert YFinanceProvider().get_prices("X", START, END).asset_type == expected


def test_unsupported_instrument_type_is_rejected():
    FakeTicker.metadata["instrumentType"] = "CRYPTOCURRENCY"
    with pytest.raises(ValueError, match="CRYPTOCURRENCY"):
        YFinanceProvider().get_prices("BTC-USD", START, END)


@pytest.mark.parametrize(
    ("names", "expected"),
    [
        ({"longName": None, "shortName": "Apple"}, "Apple"),
        ({"longName": None, "shortName": None}, "AAPL"),
    ],
)
def test_name_falls_back_to_short_name_then_ticker(names, expected):
    FakeTicker.metadata.update(names)
    assert YFinanceProvider().get_prices("AAPL", START, END).name == expected


def test_empty_history_is_rejected():
    FakeTicker.history_frame = pd.DataFrame()
    with pytest.raises(ValueError, match="no data"):
        YFinanceProvider().get_prices("NOPE", START, END)


def test_missing_currency_is_rejected():
    del FakeTicker.metadata["currency"]
    with pytest.raises(ValueError, match="no currency"):
        YFinanceProvider().get_prices("AAPL", START, END)


def test_missing_price_column_is_rejected():
    FakeTicker.history_frame = yahoo_history().drop(columns="Adj Close")
    with pytest.raises(ValueError, match="no 'Adj Close' column"):
        YFinanceProvider().get_prices("AAPL", START, END)


def test_get_many_records_failed_tickers():
    FakeTicker.history_frame = pd.DataFrame()
    series, errors = YFinanceProvider().get_many(["NOPE"], START, END)
    assert series == {}
    assert "no data" in errors["NOPE"]


def test_invalid_price_type_is_rejected():
    with pytest.raises(ValueError, match="price_type"):
        YFinanceProvider(price_type="open")
