from datetime import date, datetime, timedelta

import pandas as pd
import pytest
from conftest import business_days

from miax_toolkit.extraction.base import (
    MacroProvider,
    PriceProvider,
    to_naive_dates,
    validate_dates,
)
from miax_toolkit.models import MacroSeries, PriceSeries

START, END = date(2024, 1, 1), date(2024, 1, 31)


class StubPrices(PriceProvider):
    """Records every fetch; raises the error mapped to a ticker, if any."""

    source = "stub"

    def __init__(self, errors: dict[str, Exception] | None = None) -> None:
        self.errors = errors or {}
        self.fetched: list[str] = []

    def _fetch_prices(self, ticker: str, start: date, end: date) -> PriceSeries:
        self.fetched.append(ticker)
        if ticker in self.errors:
            raise self.errors[ticker]
        prices = pd.Series([100.0, 101.0, 102.0], index=business_days(3))
        return PriceSeries(ticker, ticker, "equity", "USD", "stub", prices, "close")


class StubMacro(MacroProvider):
    source = "stub"

    def __init__(self, errors: dict[str, Exception] | None = None) -> None:
        self.errors = errors or {}
        self.fetched: list[tuple[str, str | None]] = []

    def _fetch_series(
        self, series_id: str, start: date, end: date, *, currency: str | None
    ) -> MacroSeries:
        self.fetched.append((series_id, currency))
        if series_id in self.errors:
            raise self.errors[series_id]
        values = pd.Series([3.5, 3.6], index=business_days(2))
        return MacroSeries(
            series_id, series_id, "percent", "stub", END, values, currency
        )


# --- validate_dates ---------------------------------------------------------


def test_validate_dates_accepts_same_day():
    validate_dates(START, START)


@pytest.mark.parametrize(
    ("start", "end"),
    [
        ("2024-01-01", END),
        (START, "2024-01-31"),
        (datetime(2024, 1, 1), END),  # datetime is a date subclass
        (pd.Timestamp("2024-01-01"), END),
    ],
    ids=["str-start", "str-end", "datetime", "timestamp"],
)
def test_validate_dates_rejects_non_date_types(start, end):
    with pytest.raises(TypeError, match=r"datetime\.date"):
        validate_dates(start, end)


def test_validate_dates_rejects_reversed_range():
    with pytest.raises(ValueError, match="after end"):
        validate_dates(END, START)


def test_validate_dates_rejects_future_start():
    tomorrow = date.today() + timedelta(days=1)
    with pytest.raises(ValueError, match="future"):
        validate_dates(tomorrow, tomorrow)


def test_validate_dates_accepts_future_end():
    validate_dates(START, date.today() + timedelta(days=30))


# --- to_naive_dates ---------------------------------------------------------


def test_to_naive_dates_keeps_local_calendar_date():
    # 23:30 in New York is already the next day in UTC; the local date must win.
    index = pd.DatetimeIndex(["2024-01-02 09:30", "2024-01-03 23:30"]).tz_localize(
        "America/New_York"
    )
    result = to_naive_dates(index)
    assert result.tz is None
    assert list(result) == [pd.Timestamp("2024-01-02"), pd.Timestamp("2024-01-03")]


def test_to_naive_dates_normalizes_naive_index():
    index = pd.DatetimeIndex(["2024-01-02 15:00"])
    assert list(to_naive_dates(index)) == [pd.Timestamp("2024-01-02")]


# --- PriceProvider ----------------------------------------------------------


def test_get_prices_passes_inputs_to_fetch():
    provider = StubPrices()
    series = provider.get_prices("AAPL", START, END)
    assert series.ticker == "AAPL"
    assert provider.fetched == ["AAPL"]


@pytest.mark.parametrize(
    ("ticker", "error", "message"),
    [
        (None, TypeError, "must be a str"),
        (123, TypeError, "must be a str"),
        ("", ValueError, "must not be empty"),
        ("   ", ValueError, "must not be empty"),
        (" AAPL", ValueError, "whitespace"),
        ("AAPL\n", ValueError, "whitespace"),
    ],
)
def test_get_prices_rejects_bad_ticker_before_fetching(ticker, error, message):
    provider = StubPrices()
    with pytest.raises(error, match=message):
        provider.get_prices(ticker, START, END)
    assert provider.fetched == []


def test_get_prices_validates_dates_before_fetching():
    provider = StubPrices()
    with pytest.raises(ValueError):
        provider.get_prices("AAPL", END, START)
    assert provider.fetched == []


def test_get_many_records_download_errors_and_continues():
    provider = StubPrices(
        errors={"BAD": ValueError("no data"), "DOWN": ConnectionError("timeout")}
    )
    series, errors = provider.get_many(["AAPL", "BAD", "DOWN", "MSFT"], START, END)
    assert list(series) == ["AAPL", "MSFT"]
    assert errors == {"BAD": "no data", "DOWN": "timeout"}


def test_get_many_records_bad_tickers_per_item():
    series, errors = StubPrices().get_many(["AAPL", " MSFT", ""], START, END)
    assert list(series) == ["AAPL"]
    assert set(errors) == {" MSFT", ""}


@pytest.mark.parametrize("bug", [KeyError("column"), TypeError("bad arg")])
def test_get_many_stops_on_bugs(bug):
    # Only ValueError and OSError are download errors; anything else is a bug.
    provider = StubPrices(errors={"BAD": bug})
    with pytest.raises(type(bug)):
        provider.get_many(["AAPL", "BAD", "MSFT"], START, END)
    assert provider.fetched == ["AAPL", "BAD"]


def test_get_many_rejects_a_single_string():
    with pytest.raises(TypeError, match="not a string"):
        StubPrices().get_many("AAPL", START, END)


def test_get_many_rejects_non_str_items_before_any_request():
    provider = StubPrices()
    with pytest.raises(TypeError, match=r"\[None, 3\]"):
        provider.get_many(["AAPL", None, 3], START, END)
    assert provider.fetched == []


def test_get_many_validates_dates_before_any_request():
    provider = StubPrices()
    with pytest.raises(TypeError):
        provider.get_many(["AAPL"], "2024-01-01", END)
    assert provider.fetched == []


def test_get_many_accepts_any_iterable():
    series, errors = StubPrices().get_many((t for t in ["AAPL", "MSFT"]), START, END)
    assert list(series) == ["AAPL", "MSFT"]
    assert errors == {}


def test_get_many_with_empty_list_returns_empty_results():
    assert StubPrices().get_many([], START, END) == ({}, {})


# --- MacroProvider ----------------------------------------------------------


def test_get_series_passes_currency_through():
    provider = StubMacro()
    macro = provider.get_series("DTB3", START, END, currency="USD")
    assert macro.currency == "USD"
    assert provider.fetched == [("DTB3", "USD")]


def test_get_series_requires_currency_keyword():
    with pytest.raises(TypeError):
        StubMacro().get_series("DTB3", START, END)


@pytest.mark.parametrize(
    ("series_id", "error"),
    [(None, TypeError), (5, TypeError), ("", ValueError), ("DTB3 ", ValueError)],
)
def test_get_series_rejects_bad_id_before_fetching(series_id, error):
    provider = StubMacro()
    with pytest.raises(error):
        provider.get_series(series_id, START, END, currency=None)
    assert provider.fetched == []


def test_macro_get_many_records_errors_and_shares_currency():
    provider = StubMacro(errors={"BAD": ValueError("no data")})
    series, errors = provider.get_many(["DTB3", "BAD"], START, END, currency="EUR")
    assert list(series) == ["DTB3"]
    assert errors == {"BAD": "no data"}
    assert provider.fetched == [("DTB3", "EUR"), ("BAD", "EUR")]


def test_macro_get_many_stops_on_bugs():
    provider = StubMacro(errors={"BAD": KeyError("title")})
    with pytest.raises(KeyError):
        provider.get_many(["BAD"], START, END, currency=None)


def test_macro_get_many_rejects_string_and_non_str_items():
    provider = StubMacro()
    with pytest.raises(TypeError, match="not a string"):
        provider.get_many("DTB3", START, END, currency=None)
    with pytest.raises(TypeError, match=r"\[1\]"):
        provider.get_many(["DTB3", 1], START, END, currency=None)
    assert provider.fetched == []


def test_providers_cannot_be_instantiated_without_fetch():
    with pytest.raises(TypeError):
        PriceProvider()
    with pytest.raises(TypeError):
        MacroProvider()
