from datetime import date, timedelta

import yfinance as yf

from miax_toolkit.extraction.base import PriceProvider, to_naive_dates
from miax_toolkit.models import PriceSeries

_ASSET_TYPES = {"EQUITY": "equity", "ETF": "etf", "INDEX": "index"}
_PRICE_COLUMNS = {"close": "Close", "adj_close": "Adj Close"}


class YFinanceProvider(PriceProvider):
    """Daily prices from Yahoo Finance (no API key needed)."""

    source = "yfinance"

    def __init__(self, price_type: str = "adj_close") -> None:
        price_type = price_type.lower()
        if price_type not in _PRICE_COLUMNS:
            raise ValueError(
                f"price_type must be 'close' or 'adj_close', not '{price_type}'"
            )
        self.price_type = price_type

    def _fetch_prices(self, ticker: str, start: date, end: date) -> PriceSeries:
        yf_ticker = yf.Ticker(ticker)
        history = yf_ticker.history(
            start=start,
            end=end + timedelta(days=1),
            interval="1d",
            auto_adjust=False,
            actions=False,
        )
        if history.empty:
            raise ValueError(f"yfinance returned no data for '{ticker}'")

        metadata = yf_ticker.get_history_metadata()
        instrument_type = metadata.get("instrumentType")
        if instrument_type not in _ASSET_TYPES:
            raise ValueError(
                f"'{ticker}' is of type '{instrument_type}'; "
                f"supported types are {sorted(_ASSET_TYPES)}"
            )
        prices = history[_PRICE_COLUMNS[self.price_type]].dropna()
        prices.index = to_naive_dates(prices.index)
        prices.name = ticker

        return PriceSeries(
            ticker=ticker,
            name=metadata.get("longName") or metadata.get("shortName") or ticker,
            asset_type=_ASSET_TYPES[instrument_type],
            currency=metadata["currency"],
            source=self.source,
            prices=prices,
            price_type=self.price_type,
        )
