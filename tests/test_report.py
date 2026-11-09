from datetime import date

import numpy as np
import pandas as pd
import pytest

from miax_toolkit.models.macro import MacroSeries
from miax_toolkit.models.portfolio import Portfolio
from miax_toolkit.models.results import SimulationConfig
from miax_toolkit.models.series import PriceSeries
from miax_toolkit.reporting.report import (
    ReportSettings,
    portfolio_report,
    risk_warnings,
)

DATES = pd.bdate_range("2024-01-01", periods=300)


def make_series(ticker, seed, currency="USD", vol=0.01, base=None):
    rng = np.random.default_rng(seed)
    returns = rng.normal(0.0004, vol, len(DATES))
    if base is not None:  # correlated with another series
        returns = 0.9 * base + 0.1 * returns
    prices = pd.Series(100 * np.cumprod(1 + returns), index=DATES)
    fx = pd.Series(1.08, index=DATES) if currency != "USD" else None
    series = PriceSeries(
        ticker, ticker, "equity", currency, "test", prices, "adj_close", fx
    )
    return series, returns


AAA, AAA_RETURNS = make_series("AAA", 1)
BBB, _ = make_series("BBB", 2, base=AAA_RETURNS)  # very correlated with AAA
CCC, _ = make_series("CCC", 3)
EUR, _ = make_series("EUR1", 4, currency="EUR")
SPY, _ = make_series("SPY", 5)
RATE = MacroSeries(
    "DTB3",
    "3-month T-bill",
    "percent",
    "test",
    date(2025, 1, 1),
    pd.Series([5.0], index=[DATES[0]]),
    "USD",
)


def test_report_has_all_sections_with_benchmark_and_simulation():
    portfolio = Portfolio("Demo", [AAA, CCC, EUR], [0.4, 0.3, 0.3], RATE)
    benchmark = Portfolio("Index", [SPY], [1.0])
    simulation = portfolio.monte_carlo(SimulationConfig(n_sims=200, seed=1))
    text = portfolio.report(benchmark=benchmark, simulation=simulation)
    for title in (
        "# Portfolio report: Demo",
        "## 1. Summary",
        "## 2. Composition",
        "## 3. Performance and risk (in USD)",
        "## 4. Diversification",
        "## 5. Monte Carlo simulation",
        "## 6. Warnings",
        "## 7. Methodology",
    ):
        assert title in text
    assert "Benchmark: Index (SPY 100%)" in text
    assert "Comparison with Index" in text
    assert "Currency effect" in text
    assert "CVaR 95 %" in text


def test_report_method_matches_function():
    portfolio = Portfolio("Demo", [AAA, CCC], [0.5, 0.5])
    assert portfolio.report() == portfolio_report(portfolio)


def test_optional_sections_are_left_out():
    text = Portfolio("Solo", [AAA], [1.0]).report()
    assert "## 4. Diversification" not in text
    assert "## 5. Monte Carlo simulation" not in text
    assert "Benchmark:" not in text


def test_warnings_flag_correlation_weight_currency_and_risk_free():
    portfolio = Portfolio("Demo", [AAA, BBB, EUR], [0.5, 0.3, 0.2])
    warnings = " ".join(risk_warnings(portfolio))
    assert "AAA and BBB have a correlation" in warnings
    assert "AAA weighs 50.00%" in warnings
    assert "exposed to EUR" in warnings
    assert "No risk-free rate" in warnings
    assert "years of history" in warnings


def test_thresholds_are_parameters():
    portfolio = Portfolio("Demo", [AAA, CCC], [0.5, 0.5], RATE)
    strict = risk_warnings(portfolio, settings=ReportSettings(max_weight=0.4))
    relaxed = risk_warnings(
        portfolio, settings=ReportSettings(max_weight=0.6, min_years=0)
    )
    assert any("weighs" in w for w in strict)
    assert not any("weighs" in w for w in relaxed)


def test_decimals_are_a_parameter():
    portfolio = Portfolio("Demo", [AAA, CCC], [0.5, 0.5])
    assert "| AAA | AAA | equity | USD | 50% |" in portfolio.report(
        settings=ReportSettings(decimals=0)
    )


def test_simulation_section_describes_rebalancing():
    portfolio = Portfolio("Demo", [AAA, CCC], [0.5, 0.5])
    simulation = portfolio.monte_carlo(SimulationConfig(n_sims=100, seed=1))
    text = portfolio.report(simulation=simulation)
    assert "Rebalancing: daily" in text
    assert "Assumptions (annualized)" in text


@pytest.mark.parametrize(
    "bad",
    [
        {"max_correlation": 1.5},
        {"max_weight": 0},
        {"max_drawdown_limit": 0.2},
        {"var_level": 95},
        {"decimals": 10},
    ],
)
def test_invalid_settings_are_rejected(bad):
    with pytest.raises(ValueError):
        ReportSettings(**bad)
