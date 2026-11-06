from datetime import date

import numpy as np
import pandas as pd
import pytest
from conftest import business_days

from miax_toolkit.models import MacroSeries


def make_macro(values=None, **overrides) -> MacroSeries:
    if values is None:
        values = pd.Series([3.5, 3.75, 4.0], index=business_days(3))
    fields = {
        "series_id": "DTB3",
        "name": "3-Month Treasury Bill",
        "units": "percent",
        "source": "test",
        "as_of": date(2024, 1, 31),
        "values": values,
        "currency": "USD",
    }
    fields.update(overrides)
    return MacroSeries(**fields)


def test_valid_series_computes_mean_and_sorts():
    index = business_days(3)
    values = pd.Series([4.0, 3.5, 3.75], index=index[[2, 0, 1]])
    macro = make_macro(values)
    assert macro.values.index.is_monotonic_increasing
    assert macro.mean == pytest.approx(3.75)


def test_single_value_is_enough():
    make_macro(pd.Series([2.0], index=business_days(1)))


def test_currency_may_be_none():
    assert make_macro(currency=None, units="index").currency is None


def test_units_are_lowercased():
    assert make_macro(units="PERCENT").units == "percent"


@pytest.mark.parametrize(
    ("values", "error"),
    [
        ([1.0, 2.0], TypeError),
        (pd.Series([1.0, 2.0]), TypeError),
        (pd.Series(["a", "b"], index=business_days(2)), TypeError),
        (pd.Series([], index=pd.DatetimeIndex([]), dtype=float), ValueError),
        (pd.Series([1.0, np.nan], index=business_days(2)), ValueError),
    ],
    ids=["list", "no-dates", "non-numeric", "empty", "nan"],
)
def test_invalid_values_are_rejected(values, error):
    with pytest.raises(error):
        make_macro(values)


def test_duplicate_dates_are_rejected():
    index = pd.DatetimeIndex(["2024-01-02", "2024-01-02"])
    with pytest.raises(ValueError, match="repeated dates"):
        make_macro(pd.Series([1.0, 2.0], index=index))


def test_unknown_units_are_rejected():
    with pytest.raises(ValueError, match="units"):
        make_macro(units="basis_points")


def test_decimal_units_reject_values_that_look_like_percentages():
    with pytest.raises(ValueError, match="look like percentages"):
        make_macro(units="decimal")  # default values are 3.5, 3.75, 4.0


def test_as_decimal_converts_percent():
    decimals = make_macro().as_decimal()
    assert list(decimals) == pytest.approx([0.035, 0.0375, 0.04])


def test_as_decimal_keeps_decimal():
    values = pd.Series([0.035, 0.04], index=business_days(2))
    assert list(make_macro(values, units="decimal").as_decimal()) == [0.035, 0.04]


@pytest.mark.parametrize("units", ["index", "level"])
def test_as_decimal_rejects_non_rates(units):
    with pytest.raises(ValueError, match="Cannot convert"):
        make_macro(units=units).as_decimal()
