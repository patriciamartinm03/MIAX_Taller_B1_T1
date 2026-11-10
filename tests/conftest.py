"""Shared test setup. All tests run offline: API clients are replaced by fakes."""

import matplotlib

# Non-interactive backend so plot tests never open windows (also works in CI).
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pytest


@pytest.fixture(autouse=True)
def close_figures():
    """Free every figure a test opened."""
    yield
    plt.close("all")
