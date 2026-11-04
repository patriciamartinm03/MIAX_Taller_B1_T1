import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import date

import pandas as pd

from miax_toolkit.extraction.base import MacroProvider
from miax_toolkit.models import MacroSeries

_BASE_URL = "https://api.stlouisfed.org/fred"
_API_KEY_ENV = "FRED_API_KEY"


class FredProvider(MacroProvider):
    """Macro series from FRED (St. Louis Fed). Needs a free API key in FRED_API_KEY."""

    source = "fred"

    def __init__(self, api_key: str | None = None, timeout: float = 10) -> None:
        self._api_key = api_key or os.environ.get(_API_KEY_ENV)
        if not self._api_key:
            raise ValueError(
                f"FRED API key missing: set {_API_KEY_ENV} in .env or pass api_key"
            )
        self.timeout = timeout

    def get_series(
        self, series_id: str, start: date, end: date, *, currency: str | None
    ) -> MacroSeries:
        info = self._get("series", series_id=series_id)["seriess"][0]
        data = self._get(
            "series/observations",
            series_id=series_id,
            observation_start=start.isoformat(),
            observation_end=end.isoformat(),
        )

        observations = data["observations"]
        if not observations:
            raise ValueError(f"FRED returned no data for '{series_id}'")

        values = pd.Series(
            pd.to_numeric([obs["value"] for obs in observations], errors="coerce"),
            index=pd.to_datetime([obs["date"] for obs in observations]),
            name=series_id,
        ).dropna()

        return MacroSeries(
            series_id=series_id,
            name=info["title"],
            units=_to_units(info["units"]),
            source=self.source,
            as_of=date.fromisoformat(data["realtime_end"]),
            values=values,
            currency=currency,
        )

    def _get(self, endpoint: str, **params: str) -> dict:
        query = urllib.parse.urlencode(
            {**params, "api_key": self._api_key, "file_type": "json"}
        )
        try:
            with urllib.request.urlopen(
                f"{_BASE_URL}/{endpoint}?{query}", timeout=self.timeout
            ) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            try:
                detail = json.load(error).get("error_message", "")
            except ValueError:
                detail = ""
            raise ValueError(
                f"FRED request '{endpoint}' failed ({error.code}): {detail}"
            ) from None


def _to_units(fred_units: str) -> str:
    """Translate FRED's units text ("Percent", "Index 2015=100"...) to MacroSeries units."""
    text = fred_units.lower()
    if text.startswith("percent"):
        return "percent"
    if text.startswith("index"):
        return "index"
    return "level"
