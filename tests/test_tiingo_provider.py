from datetime import date
from typing import ClassVar

import pandas as pd
import pytest
from conftest import business_days
from tiingo.restclient import RestClientError

from miax_toolkit.extraction import tiingo_provider
from miax_toolkit.extraction.tiingo_provider import TiingoProvider

START, END = date(2024, 1, 2), date(2024, 1, 8)


class FakeTiingoClient:
    """Stands in for tiingo.TiingoClient. Configure the class attributes per test."""

    metadata: ClassVar[dict] = {"name": "Apple Inc"}
    history: ClassVar[pd.DataFrame | None] = None
    error: ClassVar[Exception | None] = None
    instances: ClassVar[list["FakeTiingoClient"]] = []

    def __init__(self, config: dict) -> None:
        self.config = config
        self.calls: list[tuple] = []
        FakeTiingoClient.instances.append(self)

    def get_ticker_metadata(self, ticker):
        self.calls.append(("metadata", ticker))
        if self.error is not None:
            raise self.error
        return self.metadata

    def get_dataframe(self, ticker, **kwargs):
        self.calls.append(("dataframe", ticker, kwargs))
        return self.history


def tiingo_history() -> pd.DataFrame:
    # Tiingo returns UTC-midnight timestamps and both close columns.
    return pd.DataFrame(
        {
            "close": [180.0, 182.0, 181.0, 185.0, 186.0],
            "adjClose": [179.0, 181.0, 180.0, 184.0, float("nan")],
        },
        index=business_days(5, tz="UTC"),
    )


@pytest.fixture(autouse=True)
def fake_client(monkeypatch):
    FakeTiingoClient.metadata = {"name": "Apple Inc"}
    FakeTiingoClient.history = tiingo_history()
    FakeTiingoClient.error = None
    FakeTiingoClient.instances = []
    monkeypatch.setattr(tiingo_provider, "TiingoClient", FakeTiingoClient)
    return FakeTiingoClient


def test_builds_adj_close_series_from_tiingo_data():
    series = TiingoProvider().get_prices("AAPL", START, END)
    assert series.ticker == "AAPL"
    assert series.name == "Apple Inc"
    assert (series.currency, series.asset_type) == ("USD", "equity")
    assert (series.source, series.price_type) == ("tiingo", "adj_close")
    # The NaN in the last row is dropped, not filled.
    assert list(series.prices) == [179.0, 181.0, 180.0, 184.0]
    assert series.prices.index.tz is None
    assert series.prices.index[0] == pd.Timestamp("2024-01-02")


def test_close_price_type_uses_close_column():
    series = TiingoProvider(price_type="CLOSE").get_prices("AAPL", START, END)
    assert series.price_type == "close"
    assert len(series.prices) == 5


def test_etf_asset_type_is_applied():
    series = TiingoProvider(asset_type="ETF").get_prices("SPY", START, END)
    assert series.asset_type == "etf"


def test_requests_daily_data_for_the_given_range():
    TiingoProvider().get_prices("AAPL", START, END)
    client = FakeTiingoClient.instances[-1]
    assert client.calls[1] == (
        "dataframe",
        "AAPL",
        {"startDate": "2024-01-02", "endDate": "2024-01-08", "frequency": "daily"},
    )


def test_name_falls_back_to_ticker():
    FakeTiingoClient.metadata = {"name": None}
    assert TiingoProvider().get_prices("AAPL", START, END).name == "AAPL"


def test_api_key_is_passed_only_when_given():
    TiingoProvider(api_key="dummy-key")
    TiingoProvider()
    assert FakeTiingoClient.instances[0].config == {"api_key": "dummy-key"}
    assert FakeTiingoClient.instances[1].config == {}


def test_http_error_becomes_value_error():
    FakeTiingoClient.error = RestClientError("404 Not Found")
    with pytest.raises(ValueError, match="request for 'NOPE' failed"):
        TiingoProvider().get_prices("NOPE", START, END)


def test_empty_range_becomes_value_error():
    # The tiingo client raises KeyError('date') when there are no rows.
    FakeTiingoClient.error = KeyError("date")
    with pytest.raises(ValueError, match="no data"):
        TiingoProvider().get_prices("AAPL", START, END)


def test_missing_price_column_becomes_value_error():
    FakeTiingoClient.history = tiingo_history().drop(columns="adjClose")
    with pytest.raises(ValueError, match="no 'adjClose' column"):
        TiingoProvider().get_prices("AAPL", START, END)


def test_get_many_records_failed_tickers():
    provider = TiingoProvider()
    FakeTiingoClient.error = RestClientError("404")
    series, errors = provider.get_many(["NOPE"], START, END)
    assert series == {}
    assert "NOPE" in errors


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [({"price_type": "open"}, "price_type"), ({"asset_type": "index"}, "equity")],
)
def test_invalid_constructor_arguments_are_rejected(kwargs, message):
    with pytest.raises(ValueError, match=message):
        TiingoProvider(**kwargs)
