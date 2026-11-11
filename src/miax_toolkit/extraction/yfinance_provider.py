from datetime import date, timedelta

import yfinance as yf
from yfinance.exceptions import YFException

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
        # yfinance errors (rate limit, missing ticker...) do not subclass
        # ValueError or OSError; translate them so get_many records them per
        # ticker instead of stopping the whole batch.
        try:
            return self._download(ticker, start, end)
        except YFException as error:
            raise ValueError(
                f"yfinance request for '{ticker}' failed: {error}"
            ) from None

    def _download(self, ticker: str, start: date, end: date) -> PriceSeries:
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
        column = _PRICE_COLUMNS[self.price_type]
        if column not in history.columns:
            raise ValueError(f"yfinance returned no '{column}' column for '{ticker}'")
        prices = history[column].dropna()
        prices.index = to_naive_dates(prices.index)
        prices.name = ticker

        currency = metadata.get("currency")
        if not currency:
            raise ValueError(f"yfinance reported no currency for '{ticker}'")

        # Some exchanges quote in hundredths (pence, agorot, cents): convert to
        # the main currency so prices and the exchange rate use the same unit.
        subunits = {"GBp": "GBP", "ILA": "ILS", "ZAc": "ZAR"}
        if currency in subunits:
            prices = prices / 100
            currency = subunits[currency]

        # Non-USD assets carry their exchange rate (USD per unit of currency),
        # used by PriceSeries.usd_prices(). It starts a week earlier so it always
        # covers the first price date.
        fx_to_usd = None
        if currency != "USD":
            fx_history = yf.Ticker(f"{currency}USD=X").history(
                start=start - timedelta(days=7),
                end=end + timedelta(days=7),
                interval="1d",
                actions=False,
            )
            if fx_history.empty:
                raise ValueError(
                    f"yfinance returned no {currency}/USD rate for '{ticker}'"
                )
            fx_to_usd = fx_history["Close"].dropna()
            fx_to_usd.index = to_naive_dates(fx_to_usd.index)
            fx_to_usd.name = f"{currency}USD"

        return PriceSeries(
            ticker=ticker,
            name=metadata.get("longName") or metadata.get("shortName") or ticker,
            asset_type=_ASSET_TYPES[instrument_type],
            currency=currency,
            source=self.source,
            prices=prices,
            price_type=self.price_type,
            fx_to_usd=fx_to_usd,
        )
