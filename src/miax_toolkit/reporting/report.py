"""Markdown report of a portfolio (task 4.5).

The report only formats: every number comes from Portfolio, SimulationResult or
metrics.py. Portfolio is received as a parameter and never imported at run time,
so reporting does not depend on models.
"""

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from miax_toolkit import metrics
from miax_toolkit.constants import BASE_CURRENCY

if TYPE_CHECKING:
    from miax_toolkit.models.portfolio import Portfolio
    from miax_toolkit.models.results import SimulationResult


@dataclass(frozen=True)
class ReportSettings:
    """Thresholds of the automatic warnings and number format of the report."""

    max_correlation: float = 0.8
    max_weight: float = 0.4
    min_effective_assets: float = 3.0
    max_drawdown_limit: float = -0.20
    min_years: float = 5.0
    var_level: float = 5.0
    decimals: int = 2

    def __post_init__(self) -> None:
        if not 0 < self.max_correlation <= 1:
            raise ValueError("max_correlation must be in (0, 1]")
        if not 0 < self.max_weight <= 1:
            raise ValueError("max_weight must be in (0, 1]")
        if self.min_effective_assets < 1:
            raise ValueError("min_effective_assets must be at least 1")
        if not -1 < self.max_drawdown_limit < 0:
            raise ValueError("max_drawdown_limit must be negative, e.g. -0.20")
        if self.min_years < 0:
            raise ValueError("min_years cannot be negative")
        if not 0 < self.var_level <= 50:
            raise ValueError("var_level must be a percentile in (0, 50], e.g. 5")
        if not 0 <= self.decimals <= 6:
            raise ValueError("decimals must be between 0 and 6")


# Formatting


def _pct(value: float, settings: ReportSettings) -> str:
    return "n/a" if pd.isna(value) else f"{value:.{settings.decimals}%}"


def _num(value: float, settings: ReportSettings) -> str:
    return "n/a" if pd.isna(value) else f"{value:.{settings.decimals}f}"


def _table(headers: list[str], rows: list[list[str]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("|" + "|".join("---" for _ in headers) + "|")
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    return lines


def _rebalancing_text(rebalance_every: int | None) -> str:
    names = {1: "daily", 21: "monthly (every 21 days)", 63: "quarterly (every 63 days)"}
    if rebalance_every is None:
        return "never (buy and hold)"
    return names.get(rebalance_every, f"every {rebalance_every} trading days")


def _composition(portfolio: "Portfolio") -> str:
    return ", ".join(
        f"{asset.ticker} {weight:.0%}"
        for asset, weight in zip(portfolio.assets, portfolio.weights)
    )


# Sections


def _header(portfolio, benchmark, start, end, n_returns) -> list[str]:
    sources = sorted({asset.source for asset in portfolio.assets})
    lines = [
        f"# Portfolio report: {portfolio.name}",
        "",
        f"- Generated: {date.today()}",
        f"- Period: {start.date()} to {end.date()} ({n_returns} daily returns)",
        f"- Base currency: {BASE_CURRENCY}",
        f"- Data sources: {', '.join(sources)}",
    ]
    if benchmark is not None:
        lines.append(f"- Benchmark: {benchmark.name} ({_composition(benchmark)})")
    return lines


def _summary(portfolio, benchmark, table, values, n_warnings, settings) -> list[str]:
    columns = ["Portfolio"] + ([benchmark.name] if benchmark is not None else [])
    measures = [
        ("Total return", lambda c: _pct(metrics.total_return(values[c]), settings)),
        ("CAGR", lambda c: _pct(table.loc[c, "cagr"], settings)),
        (
            "Annual volatility",
            lambda c: _pct(table.loc[c, "annual_volatility"], settings),
        ),
        ("Sharpe ratio", lambda c: _num(table.loc[c, "sharpe"], settings)),
        ("Max drawdown", lambda c: _pct(table.loc[c, "max_drawdown"], settings)),
    ]
    rows = [[name] + [fmt(c) for c in columns] for name, fmt in measures]
    lines = ["## 1. Summary", ""] + _table([""] + columns, rows)
    if benchmark is not None:
        comparison = portfolio.benchmark_comparison(benchmark)
        lines += [
            "",
            (
                f"- CAGR difference (portfolio − benchmark): "
                f"{_pct(comparison['cagr_difference'], settings)}"
            ),
            f"- Information ratio: {_num(comparison['information_ratio'], settings)}",
        ]
    lines += ["", f"Active warnings: **{n_warnings}** (see section 6)."]
    return lines


def _composition_section(portfolio, settings) -> list[str]:
    rows = [
        [asset.ticker, asset.name, asset.asset_type, asset.currency, _pct(w, settings)]
        for asset, w in zip(portfolio.assets, portfolio.weights)
    ]
    exposure = portfolio.currency_exposure()
    heaviest = int(np.argmax(portfolio.weights))
    lines = ["## 2. Composition", ""]
    lines += _table(["Ticker", "Name", "Type", "Currency", "Weight"], rows)
    lines += [
        "",
        "- Currency exposure: "
        + ", ".join(f"{cur} {_pct(w, settings)}" for cur, w in exposure.items()),
        (
            f"- Largest weight: {portfolio.assets[heaviest].ticker} "
            f"({_pct(portfolio.weights[heaviest], settings)})"
        ),
        (
            f"- Effective number of assets: {_num(portfolio.effective_n_assets(), settings)}"
            f" out of {len(portfolio.assets)}"
        ),
    ]
    return lines


def _performance_section(portfolio, benchmark, table, values, settings) -> list[str]:
    headers = ["", "Annual return", "CAGR", "Volatility", "Sharpe", "Sortino", "Max DD"]
    rows = [
        [
            name,
            _pct(row["annual_return"], settings),
            _pct(row["cagr"], settings),
            _pct(row["annual_volatility"], settings),
            _num(row["sharpe"], settings),
            _num(row["sortino"], settings),
            _pct(row["max_drawdown"], settings),
        ]
        for name, row in table.iterrows()
    ]
    lines = ["## 3. Performance and risk (in USD)", ""] + _table(headers, rows)

    details = metrics.max_drawdown_details(values["Portfolio"])
    recovery = details.recovery_date.date() if details.recovery_date else "not yet"
    lines += [
        "",
        (
            f"- Worst drawdown of the portfolio: {_pct(details.max_drawdown, settings)} "
            f"(peak {details.peak_date.date()}, trough {details.trough_date.date()}, "
            f"recovered {recovery})"
        ),
    ]
    if portfolio.risk_free is None:
        lines.append("- Risk-free rate: none given, Sharpe and Sortino use 0 %.")
    else:
        rate = portfolio.risk_free
        lines.append(
            f"- Risk-free rate: {rate.name} ({rate.series_id}, {rate.source}), "
            f"mean {_pct(portfolio.risk_free_mean(), settings)} over the period"
        )

    attribution = portfolio.currency_attribution()
    if not attribution.empty:
        rows = [
            [
                ticker,
                row["currency"],
                _pct(row["local_return"], settings),
                _pct(row["fx_return"], settings),
                _pct(row["usd_return"], settings),
            ]
            for ticker, row in attribution.iterrows()
        ]
        lines += ["", "Currency effect (total return over the portfolio history):", ""]
        lines += _table(["Asset", "Currency", "Local", "FX", "USD"], rows)

    if benchmark is not None:
        comparison = portfolio.benchmark_comparison(benchmark)
        labels = {
            "cagr_difference": ("CAGR difference", _pct),
            "volatility_difference": ("Volatility difference", _pct),
            "sharpe_difference": ("Sharpe difference", _num),
            "tracking_error": ("Tracking error", _pct),
            "information_ratio": ("Information ratio", _num),
        }
        rows = [
            [label, fmt(comparison[key], settings)]
            for key, (label, fmt) in labels.items()
        ]
        lines += ["", f"Comparison with {benchmark.name}:", ""]
        lines += _table(["", "Value"], rows)
    return lines


def _diversification_section(portfolio, settings) -> list[str]:
    corr = portfolio.correlation()
    rows = [[t] + [_num(v, settings) for v in corr.loc[t]] for t in corr.index]
    lines = ["## 4. Diversification", ""] + _table([""] + list(corr.columns), rows)
    lines += [
        "",
        (
            f"- Diversification benefit: {_pct(portfolio.diversification_benefit(), settings)}"
            " of annual volatility (weighted volatility of the assets minus the "
            "volatility of the portfolio)"
        ),
    ]
    return lines


def _simulation_section(portfolio, simulation, settings) -> list[str]:
    config = simulation.config
    level = settings.var_level
    horizon = f"{config.horizon_days} days"
    lines = ["## 5. Monte Carlo simulation", "", "Settings:", ""]
    lines += [
        (
            f"- {config.n_sims} simulations over {horizon}, starting at "
            f"{config.initial_value:,.2f} {BASE_CURRENCY}, seed {config.seed}"
        ),
        f"- Rebalancing: {_rebalancing_text(simulation.rebalance_every)}",
        "- Model: multivariate geometric Brownian motion (normal daily shocks)",
    ]
    if simulation.mu is not None:
        assumptions = portfolio.simulation_assumptions(simulation.mu, simulation.cov)
        rows = [
            [
                t,
                _pct(r["annual_return"], settings),
                _pct(r["annual_volatility"], settings),
            ]
            for t, r in assumptions.iterrows()
        ]
        lines += ["", "Assumptions (annualized):", ""]
        lines += _table(["Asset", "Annual return", "Annual volatility"], rows)

    levels = (5, 25, 50, 75, 95)
    final = simulation.percentiles(levels).iloc[-1]
    rows = [
        [
            f"{p}th",
            f"{final[f'p{p}']:,.2f}",
            _pct(final[f"p{p}"] / config.initial_value - 1, settings),
        ]
        for p in levels
    ]
    values, initial = simulation.final_values, config.initial_value
    confidence = f"{100 - level:g} %"
    lines += ["", f"Final value after {horizon}:", ""]
    lines += _table(["Percentile", "Value", "Return"], rows)
    lines += [
        "",
        f"- Probability of loss: {_pct(metrics.prob_loss(values, initial), settings)}",
        (
            f"- VaR {confidence} at {horizon}: "
            f"{_pct(metrics.value_at_risk(values, initial, level), settings)}"
        ),
        (
            f"- CVaR {confidence} at {horizon}: "
            f"{_pct(metrics.expected_shortfall(values, initial, level), settings)}"
        ),
        "",
        (
            f"VaR and CVaR are losses over the whole {config.horizon_days}-day horizon and "
            "include the expected return. They are not the 1-day VaR used in market risk."
        ),
    ]
    return lines


def risk_warnings(
    portfolio: "Portfolio",
    benchmark: "Portfolio | None" = None,
    settings: ReportSettings | None = None,
) -> list[str]:
    """Automatic warnings, each one a sentence. Empty list if nothing is flagged."""
    settings = ReportSettings() if settings is None else settings
    warnings = []
    table = portfolio.metrics_table(benchmark)
    start, end = portfolio.metrics_period(benchmark)

    corr = portfolio.correlation()
    tickers = list(corr.columns)
    for i, first in enumerate(tickers):
        for second in tickers[i + 1 :]:
            value = corr.loc[first, second]
            if value > settings.max_correlation:
                warnings.append(
                    f"{first} and {second} have a correlation of "
                    f"{_num(value, settings)} (above {settings.max_correlation:g}): "
                    "they diversify little."
                )

    for asset, weight in zip(portfolio.assets, portfolio.weights):
        if weight > settings.max_weight:
            warnings.append(
                f"{asset.ticker} weighs {_pct(weight, settings)} "
                f"(above {settings.max_weight:.0%})."
            )
    effective = portfolio.effective_n_assets()
    if effective < settings.min_effective_assets:
        warnings.append(
            f"Effective number of assets is {_num(effective, settings)} "
            f"(below {settings.min_effective_assets:g}): the portfolio is concentrated."
        )

    exposure = portfolio.currency_exposure().drop(BASE_CURRENCY, errors="ignore")
    for currency, weight in exposure.items():
        warnings.append(
            f"{_pct(weight, settings)} of the portfolio is exposed to {currency} "
            "without currency hedging."
        )

    drawdown = table.loc["Portfolio", "max_drawdown"]
    if drawdown < settings.max_drawdown_limit:
        warnings.append(
            f"Max drawdown of {_pct(drawdown, settings)} "
            f"(worse than {settings.max_drawdown_limit:.0%})."
        )
    years = (end - start).days / 365.25
    if years < settings.min_years:
        warnings.append(
            f"Only {years:.1f} years of history (less than {settings.min_years:g}): "
            "statistics are less reliable."
        )
    if table.loc["Portfolio", "sharpe"] < 0:
        warnings.append("Negative Sharpe ratio: the portfolio did worse than cash.")
    if portfolio.risk_free is None:
        warnings.append("No risk-free rate: Sharpe and Sortino are computed with 0 %.")
    if benchmark is not None:
        warnings += portfolio.benchmark_issues(benchmark)
    return warnings


_LIMITATIONS = [
    (
        "The simulation uses normal daily shocks, so VaR and CVaR are optimistic: "
        "real markets have more extreme days (fat tails)."
    ),
    "Bad days come in clusters during crises; the model treats days as independent.",
    (
        "Correlations tend to rise in crises, so diversification helps less when it is "
        "most needed."
    ),
    (
        "Expected returns and volatilities are estimated from past data, and the mean "
        "return is estimated with a large error."
    ),
    "Rebalancing ignores transaction costs and taxes.",
    "Past returns do not guarantee future returns.",
]

_METHODOLOGY = [
    (
        "Daily simple returns, computed after keeping only the dates shared by all "
        "assets (missing days are dropped, not filled)."
    ),
    (
        "Prices of non-USD assets are converted to USD with the daily exchange rate, "
        "without hedging."
    ),
    "Annualization with 252 trading days; CAGR with calendar days (365.25).",
    "Sharpe and Sortino on the daily excess return over the risk-free rate.",
    "Information ratio: annualized mean active return / tracking error.",
    (
        "Monte Carlo: multivariate geometric Brownian motion with the daily mean "
        "returns and covariance matrix of the assets."
    ),
]


def portfolio_report(
    portfolio: "Portfolio",
    benchmark: "Portfolio | None" = None,
    simulation: "SimulationResult | None" = None,
    settings: ReportSettings | None = None,
) -> str:
    """Markdown report: summary, composition, performance and risk,
    diversification, simulation (if given), warnings and methodology."""
    settings = ReportSettings() if settings is None else settings
    table = portfolio.metrics_table(benchmark)
    start, end = portfolio.metrics_period(benchmark)
    values = {"Portfolio": portfolio.value().loc[start:end]}
    if benchmark is not None:
        values[benchmark.name] = benchmark.value().loc[start:end]
    n_returns = len(portfolio.prices.loc[start:end]) - 1
    warnings = risk_warnings(portfolio, benchmark, settings)

    sections = [
        _header(portfolio, benchmark, start, end, n_returns),
        _summary(portfolio, benchmark, table, values, len(warnings), settings),
        _composition_section(portfolio, settings),
        _performance_section(portfolio, benchmark, table, values, settings),
    ]
    if len(portfolio.assets) > 1:
        sections.append(_diversification_section(portfolio, settings))
    if simulation is not None:
        sections.append(_simulation_section(portfolio, simulation, settings))

    warning_lines = ["## 6. Warnings", ""]
    warning_lines += [f"- ⚠️ {w}" for w in warnings] or ["- No automatic warnings."]
    warning_lines += ["", "Limitations of the analysis:", ""]
    warning_lines += [f"- {text}" for text in _LIMITATIONS]
    sections.append(warning_lines)
    sections.append(["## 7. Methodology", ""] + [f"- {t}" for t in _METHODOLOGY])

    return "\n\n".join("\n".join(section) for section in sections) + "\n"
