# Requirements traceability

This document maps each requirement of the assignment
([taller_b1_t1.pdf](../taller_b1_t1.pdf)) to the code that implements it, the
tests that check it, and the document that explains it.

Paths are relative to `src/miax_toolkit/` unless they start with `tests/`,
`docs/` or the repository root.

---

## 3. Data sources and technical environment

| Requirement | Implementation | Tests | Docs |
|---|---|---|---|
| Online market-data APIs | `extraction/yfinance_provider.py` (Yahoo Finance), `extraction/tiingo_provider.py` (Tiingo) | `tests/test_extraction.py` | README §1 |
| Historical prices of individual equities | `YFinanceProvider`, `TiingoProvider` → `asset_type="equity"` | `tests/test_extraction.py` | README §6 |
| Historical prices of stock indices | `YFinanceProvider` (`^GSPC`, `^IBEX`, `^STOXX50E`...) → `asset_type="index"` | `tests/test_extraction.py` | demo.md §5 "Stocks + index" |
| Additional data type | `extraction/fred_provider.py` → `MacroSeries` (rates, macro indicators); used as the risk-free rate in Sharpe and Sortino | `tests/test_extraction.py`, `tests/test_macro.py`, `tests/test_portfolio.py` | design_decisions D4 |
| Standardised output | `PriceSeries` / `MacroSeries` with fixed invariants | `tests/test_series.py`, `tests/test_macro.py`, `tests/test_extraction.py` | architecture §6 |

## 4.1 GitHub repository and plug-and-play deployment

| Requirement | Implementation | Docs |
|---|---|---|
| Detailed README: description, prerequisites, step-by-step installation and usage, reproducible examples | `README.md` §1–§7 | — |
| Source code organised in `/src` | `src/miax_toolkit/` (src layout, `uv_build` backend) | README §8 |
| Dependency management | `pyproject.toml` + `uv.lock` (locked versions); `.python-version` | README §3, design_decisions D14 |
| `.gitignore` | `.gitignore` (`.env`, `.venv/`, caches, `output/`) | — |
| Clone and run without friction | `git clone` → `uv sync` → `uv run python demo.py`. uv also installs Python. `.env.example` lists the keys. CI (`.github/workflows/ci.yml`) checks this on every pull request with a fresh clone and `uv sync --locked` on Linux, macOS and Windows | README §2–§5, §9 |

## 4.2 Multi-source ingestion and extraction

| Requirement | Implementation | Tests | Docs |
|---|---|---|---|
| Download historical prices of equities and indices | `PriceProvider.get_prices(ticker, start, end)` | `tests/test_extraction.py` | architecture §5 |
| Identical, compatible output whatever the API | Abstract `PriceProvider` (template method); each provider normalises dates (tz-naive, `ns`), subunit currencies, column names and FX | `tests/test_extraction.py` (`test_yfinance_and_tiingo_return_interchangeable_series`) | design_decisions D2, D4 |
| At least one additional data type | `FredProvider` / `MacroSeries` (`percent`, `decimal`, `index`, `level`) | `tests/test_extraction.py`, `tests/test_macro.py` | design_decisions D4 |
| Download N series at once, from a list | `PriceProvider.get_many(tickers, ...)`, `MacroProvider.get_many(series_ids, ...)`. Returns successes and errors separately | `tests/test_extraction.py` | design_decisions D3 |

## 4.3 Modelling: price series and portfolio

| Requirement | Implementation | Tests | Docs |
|---|---|---|---|
| Dataclasses for price series, with metadata and values | `models/series.py::PriceSeries` (`@dataclass`), `models/macro.py::MacroSeries` | `tests/test_series.py`, `tests/test_macro.py` | architecture §3 |
| Portfolio class aggregating assets and weights | `models/portfolio.py::Portfolio` (`@dataclass`): validated weights, USD conversion, date alignment, currency exposure, effective N | `tests/test_portfolio.py` | architecture §3–§4 |
| Mean and std computed automatically on instantiation | `PriceSeries.__post_init__` fills `mean_return`, `std_return`, `mean_return_usd`, `std_return_usd` (`field(init=False)`) | `tests/test_series.py` | design_decisions D8 |

## 4.4 Monte Carlo simulation engine

| Requirement | Implementation | Tests | Docs |
|---|---|---|---|
| Configurable: iterations, horizon, return and volatility assumptions | `SimulationConfig(n_sims, horizon_days, initial_value, seed)`; `monte_carlo(mu=..., cov=..., rebalance_every=...)` | `tests/test_simulation.py` (simulated returns reproduce `mu` and `cov`), `tests/test_results.py`, `tests/test_portfolio.py` | design_decisions D10, D11 |
| Applicable to a single asset and to the whole portfolio | One-asset `Portfolio(..., [1.0])`, or `simulation/montecarlo.py` called directly (`demo.py::simulate_asset`) | `tests/test_simulation.py`, `tests/test_portfolio.py` | demo.md §4 step 4 |
| Monte Carlo as a direct method of the portfolio dataclass | `Portfolio.monte_carlo()` | `tests/test_portfolio.py` | architecture §5 |
| Display simulated paths and distributions | `SimulationResult.plot()`, `plot_paths()`, `plot_distribution()` (5–95 % band, median, VaR line) | `tests/test_results.py` | README §6 |

## 4.5 Cleaning, preprocessing and reports

| Requirement | Implementation | Tests | Docs |
|---|---|---|---|
| Cleaning: NaN handling | Providers `dropna()` vendor data. `PriceSeries`/`MacroSeries` reject any remaining NaN | `tests/test_extraction.py`, `tests/test_series.py`, `tests/test_macro.py` | design_decisions D1 |
| Temporal alignment across different trading calendars | `preprocessing/alignment.py::align_prices` (inner join, no filling). FX forward-filled ≤ 7 days. `benchmark_issues()` reports calendar gaps | `tests/test_alignment.py`, `tests/test_series.py` (FX), `tests/test_portfolio.py` (benchmark gaps) | design_decisions D6 |
| Input validation: analyse and justify the policy | Strict validation at every boundary: request, vendor response, domain object, portfolio, simulation inputs | All test files (`pytest.raises` cases) | **design_decisions D1** |
| Parametrisable Markdown `.report()` with metrics, diagnostics and risk warnings | `Portfolio.report(benchmark, simulation, settings)` → `reporting/report.py`; thresholds in `ReportSettings` | `tests/test_report.py` | design_decisions D12 |
| `.plots_report()` with value-added charts (performance comparison, correlation matrix, portfolio evolution) | `Portfolio.plots_report()`: growth in base 100 vs benchmark and assets, drawdown, correlation heatmap, simulation paths and distribution | `tests/test_plots_report.py` | README §5 |

## 4.6 Project structure and diagrams

| Requirement | Implementation |
|---|---|
| Formal diagram of the class hierarchy, dependencies and system flow (UML or equivalent) | [architecture.md](architecture.md): layer diagram §1, module dependency graph §2, UML class diagram §3, data flow §4, sequence diagram §5 (Mermaid, rendered by GitHub) |

## 5. Deliverables

| Deliverable | Status |
|---|---|
| GitHub repository with source code and commit history | This repository, with feature branches merged through pull requests |
| Five-minute presentation | Outline in [presentation.md](presentation.md) |
