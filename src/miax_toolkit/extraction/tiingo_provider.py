from datetime import date

from tiingo import TiingoClient
from tiingo.restclient import RestClientError

from miax_toolkit.extraction.base import PriceProvider, to_naive_dates
from miax_toolkit.models import PriceSeries

# PriceSeries.price_type -> Tiingo column
_PRICE_COLUMNS = {"close": "close", "adj_close": "adjClose"}


class TiingoProvider(PriceProvider):
    """Daily prices for US stocks and ETFs from Tiingo. Needs TIINGO_API_KEY.

    Tiingo's ticker metadata does not report currency or asset type, so:
    currency is always USD (US-listed tickers only) and asset_type is set
    per provider ("equity" or "etf"). Indices are not covered: use yfinance.
    """

    source = "tiingo"

    def __init__(
        self,
        api_key: str | None = None,
        price_type: str = "adj_close",
        asset_type: str = "equity",
    ) -> None:
        price_type = price_type.lower()
        if price_type not in _PRICE_COLUMNS:
            raise ValueError(
                f"price_type must be 'close' or 'adj_close', not '{price_type}'"
            )
        asset_type = asset_type.lower()
        if asset_type not in ("equity", "etf"):
            raise ValueError(
                f"Tiingo covers 'equity' and 'etf' only, not '{asset_type}'"
            )
        self.price_type = price_type
        self.asset_type = asset_type
        # The tiingo client reads TIINGO_API_KEY from the environment when no
        # key is given, and raises RuntimeError if neither is set.
        config = {"api_key": api_key} if api_key else {}
        self._client = TiingoClient(config)

    def _fetch_prices(self, ticker: str, start: date, end: date) -> PriceSeries:
        try:
            metadata = self._client.get_ticker_metadata(ticker)
            history = self._client.get_dataframe(
                ticker,
                startDate=start.isoformat(),
                endDate=end.isoformat(),
                frequency="daily",
            )
        except RestClientError as error:
            # An unknown ticker comes back as an HTTP 404 wrapped in
            # RestClientError. Converted to ValueError so get_many records it
            # for this ticker and carries on with the rest.
            raise ValueError(f"Tiingo request for '{ticker}' failed: {error}") from None
        except KeyError:
            # The tiingo client raises KeyError('date') when the range is empty.
            raise ValueError(f"Tiingo returned no data for '{ticker}'") from None

        # Rows without a price are dropped, never filled.
        prices = history[_PRICE_COLUMNS[self.price_type]].dropna()
        prices.index = to_naive_dates(prices.index)
        prices.name = ticker

        return PriceSeries(
            ticker=ticker,
            name=metadata.get("name") or ticker,
            asset_type=self.asset_type,
            currency="USD",
            source=self.source,
            prices=prices,
            price_type=self.price_type,
        )
