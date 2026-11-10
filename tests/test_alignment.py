"""align_prices: keep only the dates every series shares; never fill gaps."""

import pandas as pd
import pytest

from miax_toolkit.preprocessing.alignment import align_prices

DATES = pd.date_range("2026-01-05", periods=5, freq="B")  # Mon 5 .. Fri 9


def series(values, dates=DATES) -> pd.Series:
    return pd.Series(values, index=dates, dtype=float)


def test_identical_calendars_keep_every_date():
    aligned = align_prices({"A": series([1, 2, 3, 4, 5]), "B": series([5, 4, 3, 2, 1])})
    assert aligned.index.equals(DATES)
    assert aligned.columns.tolist() == ["A", "B"]
    assert aligned["A"].tolist() == [1, 2, 3, 4, 5]


def test_holiday_in_one_market_drops_that_date_for_all():
    # B does not trade on Wednesday (e.g. a local holiday)
    b_dates = DATES.delete(2)
    aligned = align_prices(
        {"A": series([1, 2, 3, 4, 5]), "B": series([10, 20, 40, 50], b_dates)}
    )
    assert aligned.index.equals(b_dates)
    assert aligned["A"].tolist() == [1, 2, 4, 5]  # A's Wednesday price is dropped
    assert aligned["B"].tolist() == [10, 20, 40, 50]


def test_gaps_are_never_filled():
    # Filling B's missing day would create a fake 0 % return for B.
    aligned = align_prices(
        {"A": series([1, 2, 3, 4, 5]), "B": series([10, 20, 40, 50], DATES.delete(2))}
    )
    assert not aligned.isna().any().any()
    assert DATES[2] not in aligned.index


def test_different_ranges_keep_only_the_overlap():
    early = series([1, 2, 3], DATES[:3])
    late = series([7, 8, 9], DATES[2:])
    aligned = align_prices({"early": early, "late": late})
    assert aligned.index.tolist() == [DATES[2]]


def test_result_is_sorted_by_date_whatever_the_input_order():
    reversed_a = series([5, 4, 3, 2, 1], DATES[::-1])
    aligned = align_prices({"A": reversed_a, "B": series([1, 2, 3, 4, 5])})
    assert aligned.index.is_monotonic_increasing
    assert aligned["A"].tolist() == [1, 2, 3, 4, 5]


def test_columns_follow_the_order_of_the_input():
    aligned = align_prices({"ZZZ": series([1] * 5), "AAA": series([2] * 5)})
    assert aligned.columns.tolist() == ["ZZZ", "AAA"]


def test_no_common_dates_fails():
    later = pd.date_range("2026-02-02", periods=3, freq="B")
    with pytest.raises(ValueError, match="no dates in common"):
        align_prices({"A": series([1, 2, 3, 4, 5]), "B": series([1, 2, 3], later)})
