"""Unit tests for the extraction layer. No network: API clients are replaced by fakes.

Each provider module looks up its client at call time (`yf`, `TiingoClient`,
`Fred`), so monkeypatching that name in the provider module is enough.
"""

from datetime import date, datetime, timedelta

import pandas as pd
import pytest
from tiingo.restclient import RestClientError
from yfinance.exceptions import YFRateLimitError

from miax_toolkit.extraction import (
    FredProvider,
    MacroProvider,
    PriceProvider,
    TiingoProvider,
    YFinanceProvider,
    fred_provider,
    tiingo_provider,
    yfinance_provider,
)
from miax_toolkit.extraction.base import to_naive_dates, validate_dates
from miax_toolkit.models import MacroSeries, PriceSeries

START, END = date(2024, 1, 2), date(2024, 1, 10)
PRICES = [100.0, 101.0, 99.0, 102.0, 103.0]


def trading_days(n: int = len(PRICES), tz: str | None = None, time: str = "00:00"):
    """n business days from START, optionally with a time of day and a timezone."""
    return pd.date_range(f"{START} {time}", periods=n, freq="B", tz=tz)


def expected_dates(n: int = len(PRICES)) -> pd.DatetimeIndex:
    """What every provider must return: tz-naive midnight dates in ns."""
    return pd.date_range(START, periods=n, freq="B").as_unit("ns")


def make_price_series(ticker: str) -> PriceSeries:
    return PriceSeries(
        ticker=ticker,
        name=ticker,
        asset_type="equity",
        currency="USD",
        source="stub",
        prices=pd.Series(PRICES, index=expected_dates()),
        price_type="close",
    )


def make_macro_series(series_id: str, currency: str | None) -> MacroSeries:
    return MacroSeries(
        series_id=series_id,
        name=series_id,
        units="percent",
        source="stub",
        as_of=END,
        values=pd.Series([5.0, 5.1, 5.2], index=expected_dates(3)),
        currency=currency,
    )


# --- Stub providers: test the shared logic of the abstract base classes -------


class StubPriceProvider(PriceProvider):
    """Records every fetch. Tickers in `failures` raise the given exception."""

    source = "stub"

    def __init__(self, failures: dict[str, Exception] | None = None) -> None:
        self.failures = failures or {}
        self.calls: list[tuple[str, date, date]] = []

    def _fetch_prices(self, ticker, start, end):
        self.calls.append((ticker, start, end))
        if ticker in self.failures:
            raise self.failures[ticker]
        return make_price_series(ticker)


class StubMacroProvider(MacroProvider):
    source = "stub"

    def __init__(self, failures: dict[str, Exception] | None = None) -> None:
        self.failures = failures or {}
        self.calls: list[tuple[str, date, date, str | None]] = []

    def _fetch_series(self, series_id, start, end, *, currency):
        self.calls.append((series_id, start, end, currency))
        if series_id in self.failures:
            raise self.failures[series_id]
        return make_macro_series(series_id, currency)


# --- validate_dates and to_naive_dates -----------------------------------------


@pytest.mark.parametrize(
    "start, end",
    [
        ("2024-01-02", END),
        (START, "2024-01-10"),
        (datetime(2024, 1, 2), END),  # datetime is a date subclass, still rejected
        (pd.Timestamp("2024-01-02"), END),
    ],
)
def test_validate_dates_rejects_non_date_types(start, end):
    with pytest.raises(TypeError, match="datetime.date"):
        validate_dates(start, end)


def test_validate_dates_rejects_start_after_end():
    with pytest.raises(ValueError, match="is after end"):
        validate_dates(END, START)


def test_validate_dates_rejects_future_start():
    tomorrow = date.today() + timedelta(days=1)
    with pytest.raises(ValueError, match="in the future"):
        validate_dates(tomorrow, tomorrow + timedelta(days=5))


def test_validate_dates_accepts_same_day():
    validate_dates(START, START)


def test_to_naive_dates_drops_timezone_and_time():
    index = trading_days(tz="America/New_York", time="09:30")
    result = to_naive_dates(index)
    assert result.tz is None
    assert result.equals(expected_dates())


def test_to_naive_dates_pins_ns_resolution():
    index = pd.date_range(START, periods=3, freq="B").as_unit("s")
    assert to_naive_dates(index).unit == "ns"


def test_to_naive_dates_keeps_local_calendar_date():
    # 23:00 in New York is already the next day in UTC; the local date must win.
    index = pd.DatetimeIndex(["2024-01-02 23:00"], tz="America/New_York")
    assert to_naive_dates(index)[0] == pd.Timestamp("2024-01-02")


# --- PriceProvider.get_prices ---------------------------------------------------


def test_get_prices_delegates_to_fetch_with_same_arguments():
    provider = StubPriceProvider()
    series = provider.get_prices("AAPL", START, END)
    assert provider.calls == [("AAPL", START, END)]
    assert series.ticker == "AAPL"


@pytest.mark.parametrize(
    "ticker, error, message",
    [
        (123, TypeError, "must be a str"),
        (None, TypeError, "must be a str"),
        ("", ValueError, "must not be empty"),
        ("   ", ValueError, "must not be empty"),
        (" AAPL", ValueError, "whitespace"),
        ("AAPL\n", ValueError, "whitespace"),
    ],
)
def test_get_prices_rejects_bad_ticker_before_fetching(ticker, error, message):
    provider = StubPriceProvider()
    with pytest.raises(error, match=message):
        provider.get_prices(ticker, START, END)
    assert provider.calls == []


def test_get_prices_validates_dates_before_fetching():
    provider = StubPriceProvider()
    with pytest.raises(ValueError, match="is after end"):
        provider.get_prices("AAPL", END, START)
    assert provider.calls == []


# --- PriceProvider.get_many -----------------------------------------------------


def test_get_many_returns_one_series_per_ticker_in_order():
    series, errors = StubPriceProvider().get_many(["MSFT", "AAPL", "SPY"], START, END)
    assert list(series) == ["MSFT", "AAPL", "SPY"]
    assert all(isinstance(s, PriceSeries) for s in series.values())
    assert errors == {}


def test_get_many_downloads_repeated_tickers_once():
    provider = StubPriceProvider()
    series, _ = provider.get_many(["AAPL", "MSFT", "AAPL"], START, END)
    assert list(series) == ["AAPL", "MSFT"]
    assert [call[0] for call in provider.calls] == ["AAPL", "MSFT"]


def test_get_many_accepts_any_iterable():
    series, _ = StubPriceProvider().get_many((t for t in ["AAPL", "MSFT"]), START, END)
    assert list(series) == ["AAPL", "MSFT"]


@pytest.mark.parametrize("failure", [ValueError("no data"), OSError("timeout")])
def test_get_many_records_download_errors_and_continues(failure):
    provider = StubPriceProvider(failures={"BAD": failure})
    series, errors = provider.get_many(["AAPL", "BAD", "MSFT"], START, END)
    assert list(series) == ["AAPL", "MSFT"]
    assert errors == {"BAD": str(failure)}


def test_get_many_does_not_hide_programming_errors():
    provider = StubPriceProvider(failures={"BAD": TypeError("bug")})
    with pytest.raises(TypeError, match="bug"):
        provider.get_many(["AAPL", "BAD"], START, END)


def test_get_many_rejects_a_bare_string():
    # A string is iterable: without this check "AAPL" would become A, A, P, L.
    with pytest.raises(TypeError, match="not a string"):
        StubPriceProvider().get_many("AAPL", START, END)


def test_get_many_rejects_empty_list():
    with pytest.raises(ValueError, match="must not be empty"):
        StubPriceProvider().get_many([], START, END)


def test_get_many_rejects_non_string_tickers():
    with pytest.raises(TypeError, match="every ticker must be a str"):
        StubPriceProvider().get_many(["AAPL", 42], START, END)


@pytest.mark.parametrize("bad", ["", " MSFT", "MSFT "])
def test_get_many_rejects_empty_or_padded_tickers_before_fetching(bad):
    provider = StubPriceProvider()
    with pytest.raises(ValueError, match="empty or space-padded"):
        provider.get_many(["AAPL", bad], START, END)
    assert provider.calls == []


def test_get_many_validates_dates_before_fetching():
    provider = StubPriceProvider()
    with pytest.raises(TypeError, match="datetime.date"):
        provider.get_many(["AAPL"], "2024-01-02", END)
    assert provider.calls == []


# --- MacroProvider --------------------------------------------------------------


def test_get_series_passes_currency_through():
    provider = StubMacroProvider()
    series = provider.get_series("DTB3", START, END, currency="USD")
    assert provider.calls == [("DTB3", START, END, "USD")]
    assert series.currency == "USD"


def test_get_series_accepts_no_currency():
    assert (
        StubMacroProvider().get_series("CPI", START, END, currency=None).currency
        is None
    )


@pytest.mark.parametrize(
    "series_id, error, message",
    [
        (7, TypeError, "must be a str"),
        ("", ValueError, "must not be empty"),
        ("DTB3 ", ValueError, "whitespace"),
    ],
)
def test_get_series_rejects_bad_series_id(series_id, error, message):
    provider = StubMacroProvider()
    with pytest.raises(error, match=message):
        provider.get_series(series_id, START, END, currency="USD")
    assert provider.calls == []


def test_macro_get_many_records_errors_and_drops_repeats():
    provider = StubMacroProvider(failures={"BAD": ValueError("unknown series")})
    series, errors = provider.get_many(
        ["DTB3", "BAD", "DTB3", "DGS10"], START, END, currency="USD"
    )
    assert list(series) == ["DTB3", "DGS10"]
    assert errors == {"BAD": "unknown series"}
    assert [call[0] for call in provider.calls] == ["DTB3", "BAD", "DGS10"]


@pytest.mark.parametrize(
    "series_ids, error, message",
    [
        ("DTB3", TypeError, "not a string"),
        ([], ValueError, "must not be empty"),
        (["DTB3", None], TypeError, "every series_id must be a str"),
        (["DTB3", " DGS10"], ValueError, "empty or space-padded"),
    ],
)
def test_macro_get_many_rejects_bad_input(series_ids, error, message):
    with pytest.raises(error, match=message):
        StubMacroProvider().get_many(series_ids, START, END, currency="USD")


# --- YFinanceProvider -----------------------------------------------------------


class FakeYFTicker:
    def __init__(self, history: pd.DataFrame, metadata: dict | None = None) -> None:
        self._history = history
        self._metadata = metadata or {}
        self.history_calls: list[dict] = []

    def history(self, **kwargs) -> pd.DataFrame:
        self.history_calls.append(kwargs)
        return self._history.copy()

    def get_history_metadata(self) -> dict:
        return self._metadata


class FakeYF:
    """Stands in for the yfinance module: only Ticker() is used."""

    def __init__(self, tickers: dict[str, FakeYFTicker]) -> None:
        self.tickers = tickers

    def Ticker(self, symbol: str) -> FakeYFTicker:  # same name as yfinance.Ticker
        return self.tickers[symbol]


def yf_history(prices=PRICES, tz="America/New_York", time="09:30") -> pd.DataFrame:
    dates = trading_days(len(prices), tz=tz, time=time)
    return pd.DataFrame(
        {"Close": prices, "Adj Close": [p * 0.9 for p in prices]}, index=dates
    )


def yf_fx_history(rate: float, tz="Europe/London") -> pd.DataFrame:
    # Covers START - 7 days to END + 7 days, every calendar day.
    dates = pd.date_range(START - timedelta(days=7), END + timedelta(days=7), tz=tz)
    return pd.DataFrame({"Close": rate}, index=dates)


def us_equity_metadata(**overrides) -> dict:
    metadata = {
        "instrumentType": "EQUITY",
        "currency": "USD",
        "longName": "Apple Inc.",
        "shortName": "Apple",
    }
    return metadata | overrides


@pytest.fixture
def install_yf(monkeypatch):
    def install(tickers: dict[str, FakeYFTicker]) -> FakeYF:
        fake = FakeYF(tickers)
        monkeypatch.setattr(yfinance_provider, "yf", fake)
        return fake

    return install


def test_yfinance_returns_standard_usd_series(install_yf):
    install_yf({"AAPL": FakeYFTicker(yf_history(), us_equity_metadata())})
    series = YFinanceProvider().get_prices("AAPL", START, END)

    assert isinstance(series, PriceSeries)
    assert (series.ticker, series.name, series.source) == (
        "AAPL",
        "Apple Inc.",
        "yfinance",
    )
    assert (series.asset_type, series.currency, series.price_type) == (
        "equity",
        "USD",
        "adj_close",
    )
    assert series.fx_to_usd is None
    assert series.prices.index.equals(expected_dates())
    assert series.prices.tolist() == pytest.approx([p * 0.9 for p in PRICES])


def test_yfinance_close_price_type_uses_close_column(install_yf):
    install_yf({"AAPL": FakeYFTicker(yf_history(), us_equity_metadata())})
    series = YFinanceProvider(price_type="CLOSE").get_prices("AAPL", START, END)
    assert series.price_type == "close"
    assert series.prices.tolist() == pytest.approx(PRICES)


def test_yfinance_requests_end_date_inclusive_and_raw_prices(install_yf):
    ticker = FakeYFTicker(yf_history(), us_equity_metadata())
    install_yf({"AAPL": ticker})
    YFinanceProvider().get_prices("AAPL", START, END)
    (call,) = ticker.history_calls
    assert call["start"] == START
    assert call["end"] == END + timedelta(days=1)  # yfinance's end is exclusive
    assert call["interval"] == "1d"
    assert call["auto_adjust"] is False  # both Close and Adj Close are returned


@pytest.mark.parametrize(
    "instrument_type, asset_type",
    [("EQUITY", "equity"), ("ETF", "etf"), ("INDEX", "index")],
)
def test_yfinance_maps_instrument_type(install_yf, instrument_type, asset_type):
    metadata = us_equity_metadata(instrumentType=instrument_type)
    install_yf({"X": FakeYFTicker(yf_history(), metadata)})
    assert YFinanceProvider().get_prices("X", START, END).asset_type == asset_type


def test_yfinance_name_falls_back_to_short_name_then_ticker(install_yf):
    install_yf(
        {
            "A": FakeYFTicker(yf_history(), us_equity_metadata(longName=None)),
            "B": FakeYFTicker(
                yf_history(), us_equity_metadata(longName=None, shortName=None)
            ),
        }
    )
    provider = YFinanceProvider()
    assert provider.get_prices("A", START, END).name == "Apple"
    assert provider.get_prices("B", START, END).name == "B"


def test_yfinance_drops_missing_prices(install_yf):
    history = yf_history([100.0, float("nan"), 102.0, 103.0, 104.0])
    install_yf({"AAPL": FakeYFTicker(history, us_equity_metadata())})
    series = YFinanceProvider(price_type="close").get_prices("AAPL", START, END)
    assert series.prices.tolist() == [100.0, 102.0, 103.0, 104.0]


def test_yfinance_converts_eur_listing_with_fx(install_yf):
    fx = FakeYFTicker(yf_fx_history(1.10))
    install_yf(
        {
            "SAN.MC": FakeYFTicker(
                yf_history(tz="Europe/Madrid"),
                us_equity_metadata(currency="EUR", longName="Banco Santander"),
            ),
            "EURUSD=X": fx,
        }
    )
    series = YFinanceProvider(price_type="close").get_prices("SAN.MC", START, END)

    assert series.currency == "EUR"
    assert series.fx_to_usd.index.equals(series.prices.index)
    assert series.usd_prices().tolist() == pytest.approx([p * 1.10 for p in PRICES])
    (call,) = fx.history_calls
    assert call["start"] == START - timedelta(days=7)  # always covers the 1st price
    assert call["end"] == END + timedelta(days=7)


@pytest.mark.parametrize(
    "subunit, currency, fx_symbol",
    [
        ("GBp", "GBP", "GBPUSD=X"),
        ("ILA", "ILS", "ILSUSD=X"),
        ("ZAc", "ZAR", "ZARUSD=X"),
    ],
)
def test_yfinance_converts_subunit_quotes_to_main_currency(
    install_yf, subunit, currency, fx_symbol
):
    install_yf(
        {
            "X": FakeYFTicker(
                yf_history([2500.0, 2510.0, 2490.0]),
                us_equity_metadata(currency=subunit),
            ),
            fx_symbol: FakeYFTicker(yf_fx_history(1.25)),
        }
    )
    series = YFinanceProvider(price_type="close").get_prices("X", START, END)
    assert series.currency == currency
    assert series.prices.tolist() == pytest.approx([25.0, 25.1, 24.9])
    assert series.usd_prices().iloc[0] == pytest.approx(25.0 * 1.25)


def test_yfinance_empty_history_fails(install_yf):
    install_yf({"ZZZZ": FakeYFTicker(pd.DataFrame(), {})})
    with pytest.raises(ValueError, match="no data for 'ZZZZ'"):
        YFinanceProvider().get_prices("ZZZZ", START, END)


def test_yfinance_unsupported_instrument_type_fails(install_yf):
    metadata = us_equity_metadata(instrumentType="CRYPTOCURRENCY")
    install_yf({"BTC-USD": FakeYFTicker(yf_history(), metadata)})
    with pytest.raises(ValueError, match="is of type 'CRYPTOCURRENCY'"):
        YFinanceProvider().get_prices("BTC-USD", START, END)


def test_yfinance_missing_price_column_fails(install_yf):
    history = yf_history().drop(columns="Adj Close")
    install_yf({"AAPL": FakeYFTicker(history, us_equity_metadata())})
    with pytest.raises(ValueError, match="no 'Adj Close' column"):
        YFinanceProvider().get_prices("AAPL", START, END)


def test_yfinance_missing_currency_fails(install_yf):
    install_yf({"AAPL": FakeYFTicker(yf_history(), us_equity_metadata(currency=None))})
    with pytest.raises(ValueError, match="no currency"):
        YFinanceProvider().get_prices("AAPL", START, END)


def test_yfinance_missing_fx_rate_fails(install_yf):
    install_yf(
        {
            "SAN.MC": FakeYFTicker(yf_history(), us_equity_metadata(currency="EUR")),
            "EURUSD=X": FakeYFTicker(pd.DataFrame()),
        }
    )
    with pytest.raises(ValueError, match="no EUR/USD rate"):
        YFinanceProvider().get_prices("SAN.MC", START, END)


def test_yfinance_get_many_records_unknown_ticker(install_yf):
    install_yf(
        {
            "AAPL": FakeYFTicker(yf_history(), us_equity_metadata()),
            "ZZZZ": FakeYFTicker(pd.DataFrame(), {}),
        }
    )
    series, errors = YFinanceProvider().get_many(["AAPL", "ZZZZ"], START, END)
    assert list(series) == ["AAPL"]
    assert "no data" in errors["ZZZZ"]


class RateLimitedYFTicker(FakeYFTicker):
    def history(self, **kwargs) -> pd.DataFrame:
        raise YFRateLimitError()


def test_yfinance_get_many_records_rate_limit_and_keeps_the_rest(install_yf):
    install_yf(
        {
            "AAPL": FakeYFTicker(yf_history(), us_equity_metadata()),
            "MSFT": RateLimitedYFTicker(yf_history(), us_equity_metadata()),
            "NVDA": FakeYFTicker(yf_history(), us_equity_metadata()),
        }
    )
    series, errors = YFinanceProvider().get_many(["AAPL", "MSFT", "NVDA"], START, END)
    assert list(series) == ["AAPL", "NVDA"]
    assert list(errors) == ["MSFT"]
    assert "yfinance request for 'MSFT' failed" in errors["MSFT"]
    assert "Rate limited" in errors["MSFT"]


def test_yfinance_rejects_invalid_price_type():
    with pytest.raises(ValueError, match="price_type must be"):
        YFinanceProvider(price_type="open")


# --- TiingoProvider -------------------------------------------------------------


class FakeTiingoClient:
    def __init__(
        self,
        history: pd.DataFrame | None = None,
        metadata: dict | None = None,
        error: Exception | None = None,
    ) -> None:
        self.history = history
        self.metadata = metadata if metadata is not None else {"name": "Apple Inc"}
        self.error = error
        self.config: dict | None = None
        self.dataframe_calls: list[tuple[str, dict]] = []

    def get_ticker_metadata(self, ticker: str) -> dict:
        if self.error is not None:
            raise self.error
        return self.metadata

    def get_dataframe(self, ticker: str, **kwargs) -> pd.DataFrame:
        self.dataframe_calls.append((ticker, kwargs))
        return self.history.copy()


def tiingo_history(prices=PRICES) -> pd.DataFrame:
    dates = trading_days(len(prices), tz="UTC")
    return pd.DataFrame(
        {"close": prices, "adjClose": [p * 0.9 for p in prices]}, index=dates
    )


@pytest.fixture
def install_tiingo(monkeypatch):
    def install(client: FakeTiingoClient) -> FakeTiingoClient:
        def factory(config: dict) -> FakeTiingoClient:
            client.config = config
            return client

        monkeypatch.setattr(tiingo_provider, "TiingoClient", factory)
        return client

    return install


def test_tiingo_returns_standard_usd_series(install_tiingo):
    install_tiingo(FakeTiingoClient(tiingo_history()))
    series = TiingoProvider().get_prices("AAPL", START, END)

    assert isinstance(series, PriceSeries)
    assert (series.ticker, series.name, series.source) == (
        "AAPL",
        "Apple Inc",
        "tiingo",
    )
    assert (series.asset_type, series.currency, series.price_type) == (
        "equity",
        "USD",
        "adj_close",
    )
    assert series.fx_to_usd is None
    assert series.prices.index.equals(expected_dates())
    assert series.prices.tolist() == pytest.approx([p * 0.9 for p in PRICES])


def test_tiingo_close_and_etf_settings(install_tiingo):
    install_tiingo(FakeTiingoClient(tiingo_history()))
    provider = TiingoProvider(price_type="close", asset_type="ETF")
    series = provider.get_prices("SPY", START, END)
    assert (series.asset_type, series.price_type) == ("etf", "close")
    assert series.prices.tolist() == pytest.approx(PRICES)


def test_tiingo_sends_iso_dates_and_daily_frequency(install_tiingo):
    client = install_tiingo(FakeTiingoClient(tiingo_history()))
    TiingoProvider().get_prices("AAPL", START, END)
    assert client.dataframe_calls == [
        (
            "AAPL",
            {"startDate": "2024-01-02", "endDate": "2024-01-10", "frequency": "daily"},
        )
    ]


def test_tiingo_passes_api_key_only_when_given(install_tiingo):
    client = install_tiingo(FakeTiingoClient(tiingo_history()))
    TiingoProvider(api_key="test-key")
    assert client.config == {"api_key": "test-key"}
    TiingoProvider()
    assert client.config == {}  # the tiingo client then reads TIINGO_API_KEY


def test_tiingo_name_falls_back_to_ticker(install_tiingo):
    install_tiingo(FakeTiingoClient(tiingo_history(), metadata={}))
    assert TiingoProvider().get_prices("AAPL", START, END).name == "AAPL"


@pytest.mark.parametrize(
    "error, message",
    [
        (RestClientError("404 Not Found"), "request for 'ZZZZ' failed"),
        (KeyError("ticker"), "no data for 'ZZZZ'"),
    ],
)
def test_tiingo_client_errors_become_value_errors(install_tiingo, error, message):
    install_tiingo(FakeTiingoClient(error=error))
    with pytest.raises(ValueError, match=message):
        TiingoProvider().get_prices("ZZZZ", START, END)


def test_tiingo_get_many_records_unknown_ticker(install_tiingo):
    class PartlyFailingClient(FakeTiingoClient):
        def get_ticker_metadata(self, ticker):
            if ticker == "ZZZZ":
                raise RestClientError("404 Not Found")
            return self.metadata

    install_tiingo(PartlyFailingClient(tiingo_history()))
    series, errors = TiingoProvider().get_many(["AAPL", "ZZZZ"], START, END)
    assert list(series) == ["AAPL"]
    assert "failed" in errors["ZZZZ"]


def test_tiingo_missing_price_column_fails(install_tiingo):
    install_tiingo(FakeTiingoClient(tiingo_history().drop(columns="adjClose")))
    with pytest.raises(ValueError, match="no 'adjClose' column"):
        TiingoProvider().get_prices("AAPL", START, END)


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"price_type": "open"}, "price_type must be"),
        ({"asset_type": "index"}, "'equity' and 'etf' only"),
    ],
)
def test_tiingo_rejects_invalid_settings(install_tiingo, kwargs, message):
    install_tiingo(FakeTiingoClient())
    with pytest.raises(ValueError, match=message):
        TiingoProvider(**kwargs)


# --- Standardised output across providers ---------------------------------------


def test_yfinance_and_tiingo_return_interchangeable_series(install_yf, install_tiingo):
    # Same prices, different vendor formats: New York time vs UTC midnight,
    # "Close" vs "close". The resulting PriceSeries must line up exactly.
    install_yf({"AAPL": FakeYFTicker(yf_history(), us_equity_metadata())})
    install_tiingo(FakeTiingoClient(tiingo_history()))
    yahoo = YFinanceProvider(price_type="close").get_prices("AAPL", START, END)
    tiingo = TiingoProvider(price_type="close").get_prices("AAPL", START, END)

    pd.testing.assert_series_equal(yahoo.prices, tiingo.prices, check_freq=False)
    for field in ("ticker", "asset_type", "currency", "price_type"):
        assert getattr(yahoo, field) == getattr(tiingo, field)
    assert yahoo.mean_return == pytest.approx(tiingo.mean_return)


# --- FredProvider ---------------------------------------------------------------


class FakeFred:
    def __init__(
        self, series: dict[str, pd.Series], info: dict[str, pd.Series]
    ) -> None:
        self.series = series
        self.info = info
        self.api_key: str | None = None
        self.series_calls: list[tuple[str, dict]] = []

    def get_series_info(self, series_id: str) -> pd.Series:
        if series_id not in self.info:
            raise ValueError(f"Bad Request. The series does not exist: {series_id}")
        return self.info[series_id]

    def get_series(self, series_id: str, **kwargs) -> pd.Series:
        self.series_calls.append((series_id, kwargs))
        return self.series[series_id].copy()


def fred_info(units: str = "Percent", **overrides) -> pd.Series:
    info = {
        "title": "3-Month Treasury Bill Secondary Market Rate",
        "units": units,
        "realtime_end": "2024-01-31",
    }
    return pd.Series(info | overrides)


def fred_values(values=(5.25, 5.24, 5.26)) -> pd.Series:
    # fredapi returns a plain Series indexed by date, with no name.
    return pd.Series(list(values), index=trading_days(len(values)).as_unit("s"))


@pytest.fixture
def install_fred(monkeypatch):
    def install(series: dict, info: dict) -> FakeFred:
        fake = FakeFred(series, info)

        def factory(api_key: str | None = None) -> FakeFred:
            fake.api_key = api_key
            return fake

        monkeypatch.setattr(fred_provider, "Fred", factory)
        return fake

    return install


def test_fred_returns_standard_macro_series(install_fred):
    install_fred({"DTB3": fred_values()}, {"DTB3": fred_info()})
    macro = FredProvider().get_series("DTB3", START, END, currency="usd")

    assert isinstance(macro, MacroSeries)
    assert (macro.series_id, macro.source, macro.units) == ("DTB3", "fred", "percent")
    assert macro.name == "3-Month Treasury Bill Secondary Market Rate"
    assert macro.currency == "USD"
    assert macro.as_of == date(2024, 1, 31)
    assert macro.values.name == "DTB3"
    assert macro.values.index.equals(expected_dates(3))  # ns, same as prices
    assert macro.as_decimal().tolist() == pytest.approx([0.0525, 0.0524, 0.0526])


def test_fred_requests_the_date_range(install_fred):
    fake = install_fred({"DTB3": fred_values()}, {"DTB3": fred_info()})
    FredProvider().get_series("DTB3", START, END, currency="USD")
    assert fake.series_calls == [
        ("DTB3", {"observation_start": START, "observation_end": END})
    ]


def test_fred_passes_api_key(install_fred):
    fake = install_fred({}, {})
    FredProvider(api_key="test-key")
    assert fake.api_key == "test-key"


def test_fred_series_without_currency(install_fred):
    install_fred(
        {"CPIAUCSL": fred_values((308.4, 310.3, 312.2))},
        {"CPIAUCSL": fred_info(units="Index 1982-1984=100")},
    )
    macro = FredProvider().get_series("CPIAUCSL", START, END, currency=None)
    assert (macro.units, macro.currency) == ("index", None)


def test_fred_drops_missing_values(install_fred):
    # FRED marks holidays as missing ("."), which fredapi turns into NaN.
    install_fred(
        {"DTB3": fred_values((5.25, float("nan"), 5.26))}, {"DTB3": fred_info()}
    )
    macro = FredProvider().get_series("DTB3", START, END, currency="USD")
    assert macro.values.tolist() == [5.25, 5.26]


def test_fred_all_missing_values_fail(install_fred):
    install_fred({"DTB3": fred_values((float("nan"),) * 3)}, {"DTB3": fred_info()})
    with pytest.raises(ValueError, match="no data for 'DTB3'"):
        FredProvider().get_series("DTB3", START, END, currency="USD")


def test_fred_incomplete_metadata_fails(install_fred):
    info = fred_info().drop("realtime_end")
    install_fred({"DTB3": fred_values()}, {"DTB3": info})
    with pytest.raises(ValueError, match="missing \\['realtime_end'\\]"):
        FredProvider().get_series("DTB3", START, END, currency="USD")


def test_fred_get_many_records_unknown_series(install_fred):
    install_fred({"DTB3": fred_values()}, {"DTB3": fred_info()})
    series, errors = FredProvider().get_many(
        ["DTB3", "ZZZZ"], START, END, currency="USD"
    )
    assert list(series) == ["DTB3"]
    assert "does not exist" in errors["ZZZZ"]


@pytest.mark.parametrize(
    "fred_units, units",
    [
        ("Percent", "percent"),
        ("Percent Change from Year Ago", "percent"),
        ("Index 2015=100", "index"),
        ("Index 1982-1984=100", "index"),
        ("Billions of Dollars", "level"),
        ("Thousands of Persons", "level"),
    ],
)
def test_fred_units_mapping(fred_units, units):
    assert fred_provider._to_units(fred_units) == units
