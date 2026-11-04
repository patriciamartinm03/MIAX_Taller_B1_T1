from abc import ABC, abstractmethod
from datetime import date

import pandas as pd

from miax_toolkit.models import MacroSeries, PriceSeries


class PriceProvider(ABC):
    """Source of historical asset prices. Every provider returns PriceSeries."""

    source: str

    @abstractmethod
    def get_prices(self, ticker: str, start: date, end: date) -> PriceSeries:
        """Daily prices for one ticker between start and end (both inclusive)."""

    def get_many(
        self, tickers: list[str], start: date, end: date
    ) -> dict[str, PriceSeries]:
        """Prices for several tickers, keyed by ticker. Override if the API batches."""
        return {ticker: self.get_prices(ticker, start, end) for ticker in tickers}


class MacroProvider(ABC):
    """Source of macro indicators (rates, indices, levels). Returns MacroSeries."""

    source: str

    @abstractmethod
    def get_series(
        self, series_id: str, start: date, end: date, *, currency: str | None
    ) -> MacroSeries:
        """One indicator (rate, index or level) between start and end (both inclusive)."""

    def get_many(
        self,
        series_ids: list[str],
        start: date,
        end: date,
        *,
        currency: str | None,
    ) -> dict[str, MacroSeries]:
        """Several indicators sharing a currency, keyed by series id."""
        return {
            series_id: self.get_series(series_id, start, end, currency=currency)
            for series_id in series_ids
        }


def to_naive_dates(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Drop timezone and time of day, so series from different markets align by date."""
    if index.tz is not None:
        index = index.tz_localize(None)
    return index.normalize()
