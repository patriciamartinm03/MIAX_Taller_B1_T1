from datetime import date

from fredapi import Fred

from miax_toolkit.extraction.base import MacroProvider
from miax_toolkit.models import MacroSeries


class FredProvider(MacroProvider):
    """Macro series from FRED (St. Louis Fed). Needs a free API key in FRED_API_KEY."""

    source = "fred"

    def __init__(self, api_key: str | None = None) -> None:
        # fredapi reads FRED_API_KEY from the environment when api_key is None,
        # and raises ValueError if neither is set.
        self._fred = Fred(api_key=api_key)

    def _fetch_series(
        self, series_id: str, start: date, end: date, *, currency: str | None
    ) -> MacroSeries:
        info = self._fred.get_series_info(series_id)
        values = self._fred.get_series(
            series_id, observation_start=start, observation_end=end
        )

        # FRED marks missing values with "." and fredapi turns them into NaN.
        # They are dropped, not filled: forward-filling rates is a
        # preprocessing decision, done when aligning with prices.
        values = values.dropna()
        if values.empty:
            raise ValueError(f"FRED returned no data for '{series_id}'")
        values.name = series_id

        return MacroSeries(
            series_id=series_id,
            name=info["title"],
            units=_to_units(info["units"]),
            source=self.source,
            as_of=date.fromisoformat(info["realtime_end"]),
            values=values,
            currency=currency,
        )


def _to_units(fred_units: str) -> str:
    """Translate FRED's units text ("Percent", "Index 2015=100"...) to MacroSeries units."""
    text = fred_units.lower()
    if text.startswith("percent"):
        return "percent"
    if text.startswith("index"):
        return "index"
    return "level"
