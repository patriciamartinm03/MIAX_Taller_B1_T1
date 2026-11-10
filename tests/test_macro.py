from datetime import date

import pandas as pd
import pytest

from miax_toolkit.models.macro import MacroSeries

DATES = pd.date_range("2026-01-05", periods=3, freq="B")


def make_macro(values=(3.0, 3.5, 4.0), units="percent", currency="USD", dates=DATES):
    return MacroSeries(
        series_id="DTB3",
        name="3-month Treasury bill",
        units=units,
        source="test",
        as_of=date(2026, 1, 31),
        # An empty list would default to object dtype; keep it numeric
        values=pd.Series(list(values), index=dates, dtype=None if values else float),
        currency=currency,
    )


def test_mean_is_computed_on_creation():
    assert make_macro().mean == pytest.approx(3.5)


def test_values_are_sorted_by_date():
    macro = make_macro(values=(4.0, 3.5, 3.0), dates=DATES[::-1])
    assert macro.values.index.is_monotonic_increasing
    assert macro.values.tolist() == [3.0, 3.5, 4.0]


def test_currency_is_uppercased_and_none_is_kept():
    assert make_macro(currency="usd").currency == "USD"
    assert make_macro(currency=None).currency is None


def test_units_are_case_insensitive():
    assert make_macro(units="Percent").units == "percent"


def test_negative_rates_are_allowed():
    assert make_macro(values=(-0.5, -0.4, -0.3)).mean == pytest.approx(-0.4)


def test_a_single_value_is_enough():
    assert make_macro(values=(5.0,), dates=DATES[:1]).mean == 5.0


@pytest.mark.parametrize(
    "units, values, expected",
    [
        ("percent", (3.0, 3.5, 4.0), [0.03, 0.035, 0.04]),
        ("decimal", (0.03, 0.035, 0.04), [0.03, 0.035, 0.04]),
    ],
)
def test_as_decimal(units, values, expected):
    assert make_macro(
        values=values, units=units
    ).as_decimal().tolist() == pytest.approx(expected)


@pytest.mark.parametrize("units", ["index", "level"])
def test_as_decimal_of_index_or_level_fails(units):
    with pytest.raises(ValueError, match=f"Cannot convert units '{units}'"):
        make_macro(values=(118.0, 119.0, 120.0), units=units).as_decimal()


def test_unknown_units_fail():
    with pytest.raises(ValueError, match="units must be"):
        make_macro(units="basis points")


def test_decimal_units_with_percentage_values_fail():
    # 3.5 as a decimal would be a 350 % rate: almost certainly a percentage
    with pytest.raises(ValueError, match="look like percentages"):
        make_macro(units="decimal")


@pytest.mark.parametrize(
    "values, dates, error, message",
    [
        ((3.0, None, 4.0), DATES, ValueError, "empty values"),
        ((3.0, 3.5, 4.0), DATES[[0, 0, 1]], ValueError, "repeated dates"),
        ((), DATES[:0], ValueError, "at least one value"),
        (("a", "b", "c"), DATES, TypeError, "must be numeric"),
        ((3.0, 3.5, 4.0), range(3), TypeError, "dates as its index"),
    ],
)
def test_invalid_values_fail(values, dates, error, message):
    with pytest.raises(error, match=message):
        make_macro(values=values, dates=dates)


def test_values_must_be_a_series():
    with pytest.raises(TypeError, match="must be a pandas Series"):
        MacroSeries(
            "DTB3", "T-bill", "percent", "test", date(2026, 1, 31), [3.0], "USD"
        )
