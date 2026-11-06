"""Live tests against the real provider APIs.

Skipped by default. Run with:

    uv run --env-file .env pytest -m live -v

Run a single provider with -k, e.g. `-k tiingo`, `-k fred` or `-k yfinance`.

They need network access. Tiingo and FRED tests also need TIINGO_API_KEY and
FRED_API_KEY in the environment and are skipped when the key is missing.
pytest does not read .env by itself: put the keys in .env (copy .env.example)
and pass it with --env-file as above, or export the variables in your shell.
Behind a corporate VPN with TLS inspection the calls fail with
CERTIFICATE_VERIFY_FAILED; run the tests from a network without it.

Assertions check only stable facts (types, units, currency, date bounds,
plausible values) over a fixed past range, so results do not drift over time.
"""

import os
from datetime import date

import pandas as pd
import pytest

from miax_toolkit.extraction import FredProvider, TiingoProvider, YFinanceProvider
from miax_toolkit.models import MacroSeries, PriceSeries

pytestmark = [
    pytest.mark.live,
    # Third-party libraries may emit their own deprecation warnings; those must
    # not fail a live check of our code.
    pytest.mark.filterwarnings("default"),
]

# Q1 2024: a closed past range with about 60 US trading days.
START, END = date(2024, 1, 2), date(2024, 3, 28)
UNKNOWN_TICKER = "ZZZZNOTATICKER"

needs_tiingo = pytest.mark.skipif(
    not os.environ.get("TIINGO_API_KEY"), reason="TIINGO_API_KEY not set"
)
needs_fred = pytest.mark.skipif(
    not os.environ.get("FRED_API_KEY"), reason="FRED_API_KEY not set"
)


def assert_daily_prices(series: PriceSeries, low: float, high: float) -> None:
    """Shared checks for a daily price series over START..END."""
    prices = series.prices
    assert isinstance(prices.index, pd.DatetimeIndex)
    assert prices.index.tz is None
    assert (prices.index == prices.index.normalize()).all()  # dates, no times
    assert prices.index.is_monotonic_increasing
    assert prices.index.min() >= pd.Timestamp(START)
    assert prices.index.max() <= pd.Timestamp(END)  # end is inclusive, not beyond
    assert 50 <= len(prices) <= 65  # ~60 trading days in Q1 2024
    assert prices.between(low, high).all(), (prices.min(), prices.max())


# --- yfinance (no API key) --------------------------------------------------


@pytest.fixture(scope="module")
def yfinance() -> YFinanceProvider:
    return YFinanceProvider(price_type="close")


def test_yfinance_equity(yfinance):
    series = yfinance.get_prices("AAPL", START, END)
    assert (series.asset_type, series.currency, series.source) == (
        "equity",
        "USD",
        "yfinance",
    )
    assert "Apple" in series.name
    assert_daily_prices(series, low=150, high=210)  # AAPL closed ~165-195


def test_yfinance_etf(yfinance):
    series = yfinance.get_prices("SPY", START, END)
    assert (series.asset_type, series.currency) == ("etf", "USD")
    assert_daily_prices(series, low=450, high=550)  # SPY closed ~470-525


def test_yfinance_index(yfinance):
    series = yfinance.get_prices("^GSPC", START, END)
    assert series.asset_type == "index"
    assert_daily_prices(series, low=4500, high=5500)  # S&P 500 ~4690-5250


def test_yfinance_non_usd_listing(yfinance):
    series = yfinance.get_prices("SAN.MC", START, END)  # Banco Santander, Madrid
    assert series.currency == "EUR"


def test_yfinance_adj_close_is_below_close_for_dividend_payer():
    # Dividends paid after Q1 2024 push the adjusted price below the raw close.
    adjusted = YFinanceProvider("adj_close").get_prices("AAPL", START, END)
    raw = YFinanceProvider("close").get_prices("AAPL", START, END)
    assert (adjusted.prices < raw.prices).all()


def test_yfinance_get_many_records_unknown_ticker(yfinance):
    series, errors = yfinance.get_many(["AAPL", UNKNOWN_TICKER], START, END)
    assert list(series) == ["AAPL"], errors
    assert UNKNOWN_TICKER in errors


# --- Tiingo (TIINGO_API_KEY) ------------------------------------------------


@needs_tiingo
def test_tiingo_equity():
    series = TiingoProvider(price_type="close").get_prices("AAPL", START, END)
    assert (series.asset_type, series.currency, series.source) == (
        "equity",
        "USD",
        "tiingo",
    )
    assert "Apple" in series.name
    assert_daily_prices(series, low=150, high=210)


@needs_tiingo
def test_tiingo_etf():
    series = TiingoProvider(price_type="close", asset_type="etf").get_prices(
        "SPY", START, END
    )
    assert series.asset_type == "etf"
    assert_daily_prices(series, low=450, high=550)


@needs_tiingo
def test_tiingo_and_yfinance_agree_on_close(yfinance):
    tiingo = TiingoProvider(price_type="close").get_prices("AAPL", START, END)
    yahoo = yfinance.get_prices("AAPL", START, END)
    tiingo_prices, yahoo_prices = tiingo.prices.align(yahoo.prices, join="inner")
    assert len(tiingo_prices) >= 50  # same trading calendar after date alignment
    pd.testing.assert_series_equal(
        tiingo_prices, yahoo_prices, check_names=False, rtol=0.01
    )


@needs_tiingo
def test_tiingo_get_many_records_unknown_ticker():
    series, errors = TiingoProvider().get_many(["AAPL", UNKNOWN_TICKER], START, END)
    assert list(series) == ["AAPL"], errors
    assert UNKNOWN_TICKER in errors


# --- FRED (FRED_API_KEY) ----------------------------------------------------


@pytest.fixture(scope="module")
def fred() -> FredProvider:
    if not os.environ.get("FRED_API_KEY"):
        pytest.skip("FRED_API_KEY not set")
    return FredProvider()


def assert_macro_dates(macro: MacroSeries, start: date, end: date) -> None:
    assert isinstance(macro.values.index, pd.DatetimeIndex)
    assert macro.values.index.is_monotonic_increasing
    assert macro.values.index.min() >= pd.Timestamp(start)
    assert macro.values.index.max() <= pd.Timestamp(end)
    assert macro.as_of >= end  # queried after the range closed


@needs_fred
def test_fred_daily_rate_in_percent(fred):
    macro = fred.get_series("DTB3", START, END, currency="USD")
    assert (macro.units, macro.source, macro.currency) == ("percent", "fred", "USD")
    assert "Treasury" in macro.name
    assert_macro_dates(macro, START, END)
    assert 50 <= len(macro.values) <= 65
    assert macro.values.between(4.0, 6.0).all()  # 3-month T-bill ~5.2 %
    assert macro.as_decimal().between(0.04, 0.06).all()


@needs_fred
def test_fred_monthly_index(fred):
    # Monthly points are dated the 1st, so the range starts on Jan 1.
    start, end = date(2024, 1, 1), date(2024, 3, 31)
    macro = fred.get_series("CPIAUCSL", start, end, currency=None)
    assert macro.units == "index"
    assert macro.currency is None
    assert_macro_dates(macro, start, end)
    assert len(macro.values) == 3  # Jan, Feb, Mar 2024
    assert macro.values.between(300, 320).all()  # CPI (1982-84=100) ~310


@needs_fred
def test_fred_level_series(fred):
    start, end = date(2023, 1, 1), date(2023, 12, 31)
    macro = fred.get_series("GDP", start, end, currency="USD")
    assert macro.units == "level"  # "Billions of Dollars"
    assert_macro_dates(macro, start, end)
    assert len(macro.values) == 4  # quarterly
    with pytest.raises(ValueError, match="Cannot convert"):
        macro.as_decimal()


@needs_fred
def test_fred_get_many_records_unknown_series(fred):
    series, errors = fred.get_many(["DTB3", UNKNOWN_TICKER], START, END, currency="USD")
    assert list(series) == ["DTB3"], errors
    assert UNKNOWN_TICKER in errors
