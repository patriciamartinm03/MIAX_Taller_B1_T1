"""Shared test setup. All tests run offline: API clients are replaced by fakes."""

import matplotlib

# Non-interactive backend so plot tests never open windows (also works in CI).
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
import pytest


def business_days(n: int, start: str = "2024-01-02", tz: str | None = None):
    """n consecutive business days, optionally timezone-aware."""
    return pd.date_range(start, periods=n, freq="B", tz=tz)


@pytest.fixture(autouse=True)
def close_figures():
    """Free every figure a test opened."""
    yield
    plt.close("all")
