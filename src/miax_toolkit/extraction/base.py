from abc import ABC, abstractmethod
from datetime import date

import pandas as pd

from miax_toolkit.models import MacroSeries, PriceSeries

# Errors that get_many records per ticker; any other error is a bug and stops it.
DOWNLOAD_ERRORS = (ValueError, TypeError, KeyError, OSError)


class PriceProvider(ABC):
    """Source of historical asset prices. Every provider returns PriceSeries."""

    source: str

    def get_prices(self, ticker: str, start: date, end: date) -> PriceSeries:
        """Daily prices for one ticker between start and end (both inclusive)."""
        validate_dates(start, end)
        if not ticker.strip():
            raise ValueError("ticker must not be empty")
        return self._fetch_prices(ticker, start, end)

    def get_many(
        self, tickers: list[str], start: date, end: date
    ) -> tuple[dict[str, PriceSeries], dict[str, str]]:
        """Prices for several tickers. Returns (series that worked, errors by ticker)."""
        validate_dates(start, end)
        if isinstance(tickers, str):
            raise TypeError("tickers must be a list, e.g. ['AAPL'], not a string")
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
        if not series_id.strip():
            raise ValueError("series_id must not be empty")
        return self._fetch_series(series_id, start, end, currency=currency)

    def get_many(
        self, series_ids: list[str], start: date, end: date, *, currency: str | None
    ) -> tuple[dict[str, MacroSeries], dict[str, str]]:
        """Several indicators sharing a currency. Returns (series, errors by id)."""
        validate_dates(start, end)
        if isinstance(series_ids, str):
            raise TypeError("series_ids must be a list, e.g. ['DTB3'], not a string")
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
    return index.normalize()
