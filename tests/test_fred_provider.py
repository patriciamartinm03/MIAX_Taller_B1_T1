from datetime import date
from typing import ClassVar

import pandas as pd
import pytest
from conftest import business_days

from miax_toolkit.extraction import fred_provider
from miax_toolkit.extraction.fred_provider import FredProvider, _to_units

START, END = date(2024, 1, 2), date(2024, 1, 8)


class FakeFred:
    """Stands in for fredapi.Fred. Configure the class attributes per test."""

    info: ClassVar[dict] = {}
    values: ClassVar[pd.Series] = pd.Series(dtype=float)
    instances: ClassVar[list["FakeFred"]] = []

    def __init__(self, api_key=None) -> None:
        self.api_key = api_key
        self.calls: list[tuple] = []
        FakeFred.instances.append(self)

    def get_series_info(self, series_id):
        self.calls.append(("info", series_id))
        return pd.Series(self.info)

    def get_series(self, series_id, **kwargs):
        self.calls.append(("series", series_id, kwargs))
        return self.values.copy()


@pytest.fixture(autouse=True)
def fake_fred(monkeypatch):
    FakeFred.info = {
        "title": "3-Month Treasury Bill Secondary Market Rate",
        "units": "Percent",
        "realtime_end": "2024-01-31",
    }
    # FRED's "." placeholders arrive from fredapi as NaN.
    FakeFred.values = pd.Series(
        [5.25, float("nan"), 5.22, 5.24, 5.2], index=business_days(5)
    )
    FakeFred.instances = []
    monkeypatch.setattr(fred_provider, "Fred", FakeFred)


def test_builds_macro_series_from_fred_data():
    macro = FredProvider().get_series("DTB3", START, END, currency="USD")
    assert macro.series_id == "DTB3"
    assert macro.name == "3-Month Treasury Bill Secondary Market Rate"
    assert (macro.units, macro.source, macro.currency) == ("percent", "fred", "USD")
    assert macro.as_of == date(2024, 1, 31)
    assert list(macro.values) == [5.25, 5.22, 5.24, 5.2]  # NaN dropped, not filled
    assert macro.values.name == "DTB3"


def test_requests_the_given_range():
    FredProvider().get_series("DTB3", START, END, currency=None)
    assert FakeFred.instances[-1].calls[1] == (
        "series",
        "DTB3",
        {"observation_start": START, "observation_end": END},
    )


def test_api_key_is_forwarded():
    FredProvider(api_key="dummy-key")
    assert FakeFred.instances[-1].api_key == "dummy-key"


def test_all_missing_values_are_rejected():
    FakeFred.values = pd.Series([float("nan")] * 3, index=business_days(3))
    with pytest.raises(ValueError, match="no data"):
        FredProvider().get_series("DTB3", START, END, currency="USD")


@pytest.mark.parametrize("key", ["title", "units", "realtime_end"])
def test_missing_metadata_is_rejected(key):
    del FakeFred.info[key]
    with pytest.raises(ValueError, match=f"missing \\['{key}'\\]"):
        FredProvider().get_series("DTB3", START, END, currency="USD")


def test_get_many_records_failed_series():
    del FakeFred.info["title"]
    series, errors = FredProvider().get_many(["DTB3"], START, END, currency="USD")
    assert series == {}
    assert "missing" in errors["DTB3"]


@pytest.mark.parametrize(
    ("fred_units", "expected"),
    [
        ("Percent", "percent"),
        ("Percent Change from Year Ago", "percent"),
        ("Index 2015=100", "index"),
        ("Index Jan 2000=100", "index"),
        ("Billions of Dollars", "level"),
        ("Thousands of Persons", "level"),
    ],
)
def test_to_units_maps_fred_units_text(fred_units, expected):
    assert _to_units(fred_units) == expected
