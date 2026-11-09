"""End-to-end demo of miax_toolkit: download, portfolio, Monte Carlo, report and charts.

Run from the project root:
    uv run --env-file .env python demo.py

FRED_API_KEY in .env is optional: without it the risk-free rate is 0.
Output goes to output/ (report.md and PNG charts).
"""

from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # save to files, no window needed
import matplotlib.pyplot as plt
import pandas as pd

from miax_toolkit.extraction import FredProvider, YFinanceProvider
from miax_toolkit.models.portfolio import Portfolio
from miax_toolkit.models.results import SimulationConfig
from miax_toolkit.reporting.plots import plot_correlation, plot_drawdown, plot_growth

START = date(2019, 1, 1)
END = date.today()
OUTPUT = Path("output")

# 60 % US / 40 % Europe; the benchmark uses the same weights by region
PORTFOLIO = {"AAPL": 0.30, "MSFT": 0.30, "SAN.MC": 0.40}
BENCHMARK = {"SPY": 0.60, "FEZ": 0.40}


def build_portfolio(provider, name, weights, risk_free):
    series, errors = provider.get_many(list(weights), START, END)
    if errors:
        raise SystemExit(f"Download failed for {name}: {errors}")
    return Portfolio(
        name=name,
        assets=[series[ticker] for ticker in weights],
        weights=list(weights.values()),
        risk_free=risk_free,
    )


def load_risk_free():
    try:
        return FredProvider().get_series("DTB3", START, END, currency="USD")
    except ValueError as error:
        print(f"No risk-free rate (FRED): {error}. Using 0.")
        return None


def main() -> None:
    OUTPUT.mkdir(exist_ok=True)
    provider = YFinanceProvider()
    risk_free = load_risk_free()

    portfolio = build_portfolio(provider, "Demo portfolio", PORTFOLIO, risk_free)
    benchmark = build_portfolio(provider, "Benchmark", BENCHMARK, risk_free)

    print(portfolio.metrics_table(benchmark).round(4).to_string())

    simulation = portfolio.monte_carlo(
        SimulationConfig(n_sims=2000, horizon_days=252, initial_value=100, seed=42),
        rebalance_every=21,  # monthly
    )
    print(f"\nProbability of loss in 1 year: {simulation.prob_loss():.1%}")
    print(f"VaR 95 %: {simulation.value_at_risk():.1%}")
    print(f"CVaR 95 %: {simulation.expected_shortfall():.1%}")

    report = portfolio.report(benchmark=benchmark, simulation=simulation)
    (OUTPUT / "report.md").write_text(report, encoding="utf-8")

    values = pd.concat([portfolio.value(), benchmark.value()], axis=1).dropna()
    plot_growth(values, highlight=portfolio.name).figure.savefig(OUTPUT / "growth.png")
    plot_drawdown(values).figure.savefig(OUTPUT / "drawdown.png")
    plot_correlation(portfolio.correlation()).figure.savefig(OUTPUT / "correlation.png")

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    simulation.plot_paths(ax=axes[0])
    simulation.plot_distribution(ax=axes[1])
    fig.tight_layout()
    fig.savefig(OUTPUT / "montecarlo.png")

    print(f"\nReport and charts saved in {OUTPUT.resolve()}")


if __name__ == "__main__":
    main()
