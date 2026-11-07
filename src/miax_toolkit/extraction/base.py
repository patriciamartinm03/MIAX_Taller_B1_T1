from abc import ABC, abstractmethod
from datetime import date

import pandas as pd

from miax_toolkit.models import MacroSeries, PriceSeries

DOWNLOAD_ERRORS = (ValueError, OSError)


class PriceProvider(ABC):
    """Source of historical asset prices. Every provider returns PriceSeries."""

    source: str

    def get_prices(self, ticker: str, start: date, end: date) -> PriceSeries:
        """Daily prices for one ticker between start and end (both inclusive)."""
        validate_dates(start, end)
        if not isinstance(ticker, str):
            raise TypeError(f"ticker must be a str, not {type(ticker).__name__}")
        if not ticker.strip():
            raise ValueError("ticker must not be empty")
        if ticker != ticker.strip():
            raise ValueError(f"ticker {ticker!r} has leading or trailing whitespace")
        return self._fetch_prices(ticker, start, end)

    def get_many(
        self, tickers: list[str], start: date, end: date
    ) -> tuple[dict[str, PriceSeries], dict[str, str]]:
        """Prices for several tickers. Returns (series that worked, errors by ticker)."""
        validate_dates(start, end)
        if isinstance(tickers, str):
            raise TypeError("tickers must be a list, e.g. ['AAPL'], not a string")
        tickers = list(tickers)  # also lets a generator be checked and then iterated
        if not tickers:
            raise ValueError("tickers must not be empty")
        not_str = [ticker for ticker in tickers if not isinstance(ticker, str)]
        if not_str:
            raise TypeError(f"every ticker must be a str; got {not_str!r}")
        bad = [ticker for ticker in tickers if not ticker or ticker != ticker.strip()]
        if bad:
            raise ValueError(f"empty or space-padded tickers: {bad!r}")
        tickers = list(dict.fromkeys(tickers))  # drop repeats, keep order
        series = {}
        errors = {}
        for ticker in tickers:
            try:
                series[ticker] = self.get_prices(ticker, start, end)
            except DOWNLOAD_ERRORS as error:
                errors[ticker] = str(error)
        return series, errors

    @abstractmethod
    def _fetch_prices(self, ticker: str, start: date, end: date) -> PriceSeries:
        """Download one ticker. Inputs are already validated by get_prices."""


class MacroProvider(ABC):
    """Source of macro indicators (rates, indices, levels). Returns MacroSeries."""

    source: str

    def get_series(
        self, series_id: str, start: date, end: date, *, currency: str | None
    ) -> MacroSeries:
        """One indicator between start and end (both inclusive).

        currency is passed explicitly because sources do not report it
        reliably; use None for data without a currency (e.g. inflation index).
        """
        validate_dates(start, end)
        if not isinstance(series_id, str):
            raise TypeError(f"series_id must be a str, not {type(series_id).__name__}")
        if not series_id.strip():
            raise ValueError("series_id must not be empty")
        if series_id != series_id.strip():
            raise ValueError(
                f"series_id {series_id!r} has leading or trailing whitespace"
            )
        return self._fetch_series(series_id, start, end, currency=currency)

    def get_many(
        self, series_ids: list[str], start: date, end: date, *, currency: str | None
    ) -> tuple[dict[str, MacroSeries], dict[str, str]]:
        """Several indicators sharing a currency. Returns (series, errors by id)."""
        validate_dates(start, end)
        if isinstance(series_ids, str):
            raise TypeError("series_ids must be a list, e.g. ['DTB3'], not a string")
        series_ids = list(series_ids)
        if not series_ids:
            raise ValueError("series_ids must not be empty")
        not_str = [
            series_id for series_id in series_ids if not isinstance(series_id, str)
        ]
        if not_str:
            raise TypeError(f"every series_id must be a str; got {not_str!r}")
        bad = [
            series_id
            for series_id in series_ids
            if not series_id or series_id != series_id.strip()
        ]
        if bad:
            raise ValueError(f"empty or space-padded series_ids: {bad!r}")
        series_ids = list(dict.fromkeys(series_ids))  # drop repeats, keep order
        series = {}
        errors = {}
        for series_id in series_ids:
            try:
                series[series_id] = self.get_series(
                    series_id, start, end, currency=currency
                )
            except DOWNLOAD_ERRORS as error:
                errors[series_id] = str(error)
        return series, errors

    @abstractmethod
    def _fetch_series(
        self, series_id: str, start: date, end: date, *, currency: str | None
    ) -> MacroSeries:
        """Download one indicator. Inputs are already validated by get_series."""


def validate_dates(start: date, end: date) -> None:
    """Reject wrong types and impossible ranges before any network request."""
    if type(start) is not date or type(end) is not date:
        raise TypeError("start and end must be datetime.date (not str or datetime)")
    if start > end:
        raise ValueError(f"start ({start}) is after end ({end})")
    if start > date.today():
        raise ValueError(f"start ({start}) is in the future")


def to_naive_dates(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Drop timezone and time of day, so series from different markets align by date."""
    if index.tz is not None:
        index = index.tz_localize(None)
    # pandas 3 keeps the parsed resolution (s/ms/us/ns); pin it so indexes
    # from different providers compare equal.
    return index.normalize().as_unit("ns")
