import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest

from miax_toolkit.models.portfolio import Portfolio
from miax_toolkit.models.results import SimulationConfig
from miax_toolkit.models.series import PriceSeries

DATES = pd.bdate_range("2024-01-01", periods=120)


def make_series(ticker, seed, dates=DATES):
    rng = np.random.default_rng(seed)
    prices = pd.Series(
        100 * np.cumprod(1 + rng.normal(0.0004, 0.01, len(dates))), dates
    )
    return PriceSeries(ticker, ticker, "equity", "USD", "test", prices, "adj_close")


AAA, BBB, SPY = make_series("AAA", 1), make_series("BBB", 2), make_series("SPY", 3)


def titles(fig):
    return [ax.get_title() for ax in fig.axes if ax.get_title()]


def legend(fig, title):
    ax = next(ax for ax in fig.axes if ax.get_title() == title)
    return [text.get_text() for text in ax.get_legend().get_texts()]


def test_history_charts_without_simulation():
    fig = Portfolio("Demo", [AAA, BBB], [0.5, 0.5]).plots_report()
    assert titles(fig) == ["Growth (base 100)", "Drawdown", "Correlation"]
    assert legend(fig, "Growth (base 100)") == ["AAA", "BBB", "Portfolio"]


def test_all_charts_with_benchmark_and_simulation():
    portfolio = Portfolio("Demo", [AAA, BBB], [0.5, 0.5])
    benchmark = Portfolio("Index", [SPY], [1.0])
    simulation = portfolio.monte_carlo(SimulationConfig(n_sims=50, seed=1))
    fig = portfolio.plots_report(benchmark, simulation)
    assert titles(fig) == [
        "Growth (base 100)",
        "Drawdown",
        "Correlation",
        "Simulated paths",
        "Final value distribution",
    ]
    assert legend(fig, "Drawdown") == ["Portfolio", "Index"]
    assert "Index" in legend(fig, "Growth (base 100)")


def test_benchmark_charts_use_common_dates():
    late = make_series("SPY", 3, dates=DATES[30:])
    portfolio = Portfolio("Demo", [AAA, BBB], [0.5, 0.5])
    fig = portfolio.plots_report(Portfolio("Index", [late], [1.0]))
    growth = next(ax for ax in fig.axes if ax.get_title() == "Growth (base 100)")
    first_date = min(line.get_xdata()[0] for line in growth.get_lines()[:-1])
    assert pd.Timestamp(first_date) == DATES[30]


def test_without_assets_only_portfolio_is_drawn():
    fig = Portfolio("Demo", [AAA, BBB], [0.5, 0.5]).plots_report(show_assets=False)
    assert legend(fig, "Growth (base 100)") == ["Portfolio"]


def test_one_asset_has_no_correlation_chart():
    fig = Portfolio("Solo", [AAA], [1.0]).plots_report()
    assert "Correlation" not in titles(fig)


def test_figure_is_saved_to_path(tmp_path):
    path = tmp_path / "report.png"
    fig = Portfolio("Demo", [AAA, BBB], [0.5, 0.5]).plots_report(path=path)
    assert isinstance(fig, plt.Figure)
    assert path.exists() and path.stat().st_size > 0


def test_benchmark_name_cannot_clash_with_a_ticker():
    portfolio = Portfolio("Demo", [AAA, BBB], [0.5, 0.5])
    with pytest.raises(ValueError, match="already used"):
        portfolio.plots_report(Portfolio("AAA", [SPY], [1.0]))


def test_simulation_must_be_a_simulation_result():
    with pytest.raises(TypeError, match="SimulationResult"):
        Portfolio("Demo", [AAA, BBB], [0.5, 0.5]).plots_report(simulation="paths")
