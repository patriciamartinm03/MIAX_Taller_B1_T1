# `miax_toolkit` — Market Data Extraction, Analysis and Portfolio Toolkit

[![CI](https://github.com/patriciamartinm03/MIAX_Taller_B1_T1/actions/workflows/ci.yml/badge.svg)](https://github.com/patriciamartinm03/MIAX_Taller_B1_T1/actions/workflows/ci.yml)

MIAX Workshop B1-T1. A Python package that downloads market data from several
APIs, normalises it into one internal format, and builds, analyses, simulates and
reports on investment portfolios.

```
Yahoo Finance ─┐                                 ┌─ report()        → Markdown
Tiingo ────────┼─► PriceSeries ─► Portfolio ─────┼─ plots_report()  → charts
FRED ──────────┘   MacroSeries    (USD, aligned) └─ monte_carlo()   → SimulationResult
```

The ingestion layer is decoupled from the analysis layer. To add a new data
source you write one subclass of `PriceProvider`; the models, metrics,
simulation and reporting stay unchanged.

---

## Contents

1. [Features](#1-features)
2. [Prerequisites](#2-prerequisites)
3. [Installation](#3-installation)
4. [Configuration (API keys)](#4-configuration-api-keys)
5. [Quick start: interactive demo](#5-quick-start-interactive-demo)
6. [Using the library](#6-using-the-library)
7. [Reproducible examples](#7-reproducible-examples)
8. [Project structure](#8-project-structure)
9. [Tests and code quality](#9-tests-and-code-quality)
10. [Documentation](#10-documentation)
11. [Limitations](#11-limitations)
12. [Authors](#12-authors)

---

## 1. Features

| Area | What it does | Where |
|---|---|---|
| Multi-source extraction | Daily prices of equities, ETFs and indices from **Yahoo Finance** (no key) and **Tiingo** (US equities/ETFs) | `extraction/` |
| Additional data type | Macro series from **FRED**, e.g. the 3-month T-bill (`DTB3`) used as the risk-free rate | `extraction/fred_provider.py` |
| Batch download | `get_many([...])` downloads N series and returns the successes and the failures separately, so one bad ticker does not stop the batch | `extraction/base.py` |
| Standardised output | Every price provider returns the same `PriceSeries` dataclass, and every macro provider returns a `MacroSeries` | `models/series.py`, `models/macro.py` |
| Automatic statistics | Mean and standard deviation of daily returns (local currency and USD) are computed in `__post_init__` | `PriceSeries` |
| Multi-currency | Non-USD assets carry their FX rate and are measured in USD. Pence, agorot and cents are converted to the main currency | `PriceSeries.usd_prices()` |
| Cleaning and alignment | Validates NaN, non-positive and duplicate values, normalises dates, and keeps only the dates all assets share (no gap filling) | `preprocessing/alignment.py` |
| Portfolio model | Weights, currency exposure, effective number of assets, historical value with configurable rebalancing | `models/portfolio.py` |
| Metrics | Annual return, CAGR, volatility, Sharpe, Sortino, max drawdown, tracking error, information ratio, diversification benefit | `metrics.py` |
| Monte Carlo | Correlated multivariate GBM. Parameters: simulations, horizon, initial value, seed, return/volatility assumptions (`mu`, `cov`) and rebalancing. Works for one asset or the whole portfolio | `simulation/montecarlo.py`, `Portfolio.monte_carlo()` |
| Risk on simulations | Probability of loss, VaR, CVaR, percentile bands, path and distribution plots | `models/results.py` |
| Markdown report | `Portfolio.report()`: summary, composition, performance, diversification, simulation, automatic risk warnings, limitations, methodology. Thresholds are configurable | `reporting/report.py` |
| Visual report | `Portfolio.plots_report()`: growth in base 100, drawdown, correlation heatmap, simulated paths and distribution | `reporting/plots.py` |

---

## 2. Prerequisites

| Requirement | Notes |
|---|---|
| **git** | To clone the repository |
| **[uv](https://docs.astral.sh/uv/)** | Package and environment manager. It also installs Python: you do **not** need Python installed beforehand |
| Python **3.12+** | The exact version is pinned in `.python-version`; `uv` downloads it automatically |
| Internet access | Needed to download data. Yahoo Finance may rate-limit requests or be blocked behind a corporate VPN with TLS inspection |
| API keys (optional) | Free keys for FRED and Tiingo; see [section 4](#4-configuration-api-keys) |

Install `uv` once:

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

```powershell
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Open a new terminal and check it with `uv --version`.

---

## 3. Installation

```bash
git clone https://github.com/patriciamartinm03/MIAX_Taller_B1_T1.git
cd MIAX_Taller_B1_T1
uv sync
```

`uv sync` creates `.venv/` and installs the exact versions pinned in `uv.lock`,
so every machine gets the same environment. You do not need to create or
activate a virtual environment yourself.

Check the installation:

```bash
uv run python -c "import miax_toolkit; print('OK')"
```

Optional, for contributors: install the pre-commit hooks once per clone. They
check formatting, large files, private keys and unresolved merge conflicts on
every commit.

```bash
uv tool install pre-commit
pre-commit install
```

---

## 4. Configuration (API keys)

Keys are read from environment variables. Copy the template and fill in only
the keys you need:

```bash
cp .env.example .env              # macOS / Linux
Copy-Item .env.example .env       # Windows (PowerShell)
```

| Variable | Used by | Required? | Without it |
|---|---|---|---|
| `FRED_API_KEY` | `FredProvider` (risk-free rate) | Optional | The demo uses a 0 % risk-free rate and the report says so |
| `TIINGO_API_KEY` | `TiingoProvider` | Only if you use Tiingo | `TiingoProvider()` raises an error when it is created |

Yahoo Finance needs no key.

> `.env` is listed in `.gitignore` and must never be committed. If you add a
> new variable, also add it, with an empty value, to `.env.example`.

Pass the file to any command with `uv run --env-file .env ...`.

---

## 5. Quick start: interactive demo

`demo.py` is a console program. It asks for a portfolio (assets, weights,
benchmark, simulation parameters) and runs it through the five layers of the
toolkit, one step at a time. The prompts are in Spanish.

```bash
uv run --env-file .env python demo.py   # press Enter on every question for the example portfolio
```

The example portfolio is AAPL 30 %, MSFT 30 % and SAN.MC 40 % (in EUR, converted
to USD), compared against SPY 60 % + FEZ 40 %. It runs 1,000 simulations over
252 days with monthly rebalancing and seed 42.

Output files (in `output/`, ignored by git):

| File | Contents |
|---|---|
| `output/report.md` | Full Markdown report |
| `output/plots_report.png` | Growth, drawdown, correlation, simulated paths and distribution |
| `output/montecarlo_asset.png` | Monte Carlo of the heaviest single asset |

For all questions, more scenarios, and a non-interactive run with `printf`, see
[docs/v2/demo.md](docs/v2/demo.md).

---

## 6. Using the library

```python
from datetime import date
from pathlib import Path

import matplotlib.pyplot as plt

from miax_toolkit import (
    FredProvider,
    Portfolio,
    ReportSettings,
    SimulationConfig,
    YFinanceProvider,
)

start, end = date(2019, 1, 1), date(2024, 12, 31)

# 1. Extraction: N series at once; failures come back separately
provider = YFinanceProvider()  # price_type="adj_close" by default
tickers = ["AAPL", "MSFT", "SAN.MC"]
series, errors = provider.get_many(tickers, start, end)
if errors:
    raise SystemExit(errors)

aapl = series["AAPL"]
print(aapl.currency, aapl.mean_return, aapl.std_return)  # computed on creation

# Additional data type: risk-free rate from FRED (needs FRED_API_KEY)
risk_free = FredProvider().get_series("DTB3", start, end, currency="USD")

# 2-3. Model: the portfolio converts to USD and aligns dates by itself
portfolio = Portfolio(
    name="Global 60/40",
    assets=[series[t] for t in tickers],
    weights=[0.3, 0.3, 0.4],
    risk_free=risk_free,
)
benchmark_series, _ = provider.get_many(["SPY"], start, end)
benchmark = Portfolio("S&P 500 (SPY)", [benchmark_series["SPY"]], [1.0])

print(portfolio.metrics_table(benchmark))
print(portfolio.correlation())

# 4. Monte Carlo (historical daily mu and cov by default)
config = SimulationConfig(n_sims=5_000, horizon_days=252, initial_value=10_000, seed=42)
simulation = portfolio.monte_carlo(
    config, rebalance_every=21
)  # 21 = monthly; None = buy and hold
print(f"P(loss) {simulation.prob_loss():.1%}  VaR95 {simulation.value_at_risk():.1%}")
simulation.plot()  # paths + final value distribution

# 5. Reports
settings = ReportSettings(max_weight=0.35, min_years=3, decimals=1)
Path("report.md").write_text(
    portfolio.report(benchmark=benchmark, simulation=simulation, settings=settings),
    encoding="utf-8",
)
portfolio.plots_report(
    benchmark=benchmark, simulation=simulation, path="plots_report.png"
)
plt.show()
```

Run it with `uv run --env-file .env python your_script.py`.

Main entry points. All of them can be imported from the package root
(`from miax_toolkit import ...`); the full module paths, such as
`miax_toolkit.models.portfolio.Portfolio`, also work.

| Object | Key members |
|---|---|
| `YFinanceProvider(price_type)`, `TiingoProvider(api_key, price_type, asset_type)` | `get_prices(ticker, start, end)`, `get_many(tickers, start, end)` |
| `FredProvider(api_key)` | `get_series(series_id, start, end, currency=...)`, `get_many(...)` |
| `PriceSeries` | `prices`, `mean_return`, `std_return`, `mean_return_usd`, `std_return_usd`, `usd_prices()`, `annual_return`, `annual_volatility`, `max_drawdown` |
| `Portfolio` | `value()`, `returns()`, `metrics_table()`, `benchmark_comparison()`, `correlation()`, `currency_exposure()`, `currency_attribution()`, `monte_carlo()`, `report()`, `plots_report()` |
| `SimulationResult` | `final_values`, `prob_loss()`, `value_at_risk()`, `expected_shortfall()`, `percentiles()`, `plot()` |

Custom simulation assumptions: `monte_carlo(mu=..., cov=...)` accepts the
**daily** mean returns and the covariance matrix, in the column order of
`portfolio.prices`. Values that look annual are rejected with a clear message.
To simulate a single asset, build a one-asset `Portfolio(..., [1.0])`.

---

## 7. Reproducible examples

Results are reproducible when you fix all of these:

- **The date range.** Use a closed range in the past, for example `2019-01-01` to `2024-12-31`.
- **The seed.** For example `SimulationConfig(seed=42)`.
- **The locked environment.** `uv sync` installs the versions in `uv.lock`.

Adjusted close prices (`adj_close`) are revised retroactively by the provider
when a new dividend or split is paid. To get bit-for-bit repeatable history,
use `YFinanceProvider(price_type="close")`.

| Scenario | How |
|---|---|
| Default example | `uv run --env-file .env python demo.py`, Enter on everything |
| US tech vs Nasdaq-100 (scripted) | The `printf ... \| uv run ... demo.py` command in [docs/v2/demo.md §2](docs/v2/demo.md#2-running-it) |
| Stocks + index, multi-currency, risk warnings, invalid input | The table in [docs/v2/demo.md §5](docs/v2/demo.md#5-examples-to-try) |

---

## 8. Project structure

```
MIAX_Taller_B1_T1/
├── src/miax_toolkit/
│   ├── constants.py            TRADING_DAYS = 252, BASE_CURRENCY = "USD"
│   ├── metrics.py              Pure metric functions (returns, Sharpe, drawdown, VaR...)
│   ├── extraction/             Ingestion layer: one class per data source
│   │   ├── base.py             PriceProvider / MacroProvider (abstract), input validation
│   │   ├── yfinance_provider.py
│   │   ├── tiingo_provider.py
│   │   └── fred_provider.py
│   ├── models/                 Domain dataclasses
│   │   ├── series.py           PriceSeries
│   │   ├── macro.py            MacroSeries
│   │   ├── portfolio.py        Portfolio (analysis, Monte Carlo, report entry points)
│   │   └── results.py          SimulationConfig, SimulationResult
│   ├── preprocessing/
│   │   └── alignment.py        align_prices: common dates, no filling
│   ├── simulation/
│   │   └── montecarlo.py       simulate_returns (GBM), returns_to_paths (rebalancing)
│   └── reporting/
│       ├── report.py           Markdown report, ReportSettings, risk warnings
│       └── plots.py            Growth, drawdown and correlation charts
├── tests/                      pytest unit tests (offline; API clients replaced by fakes)
├── docs/                       Architecture, design decisions, traceability, demo guide
├── demo.py                     Interactive console demo (uses the public API only)
├── pyproject.toml / uv.lock    Dependencies (locked)
├── .env.example                API key template
└── .pre-commit-config.yaml     Commit hooks
```

The architecture, class diagram and data flow are in
[docs/v2/architecture.md](docs/v2/architecture.md).

---

## 9. Tests and code quality

```bash
uv run pytest                         # full suite: offline, no network or API keys needed
uv run pytest tests/test_extraction.py -v   # one module
uv run ruff check .                   # lint
uv run ruff format --check .          # formatting
```

- Every test is a unit test and runs offline in a few seconds.
- Models, metrics, simulation and reporting are tested on synthetic data with
  known answers. For example, prices that move +10 %, −10 %, +10 %, −10 % have
  a mean return of 0.
- The extraction layer (`tests/test_extraction.py`) replaces the yfinance,
  Tiingo and FRED clients with fakes. It checks input validation, batch
  downloads with partial failures, vendor-format normalisation (timezones,
  `ns` dates, pence/cents, FX), error translation, and that yfinance and Tiingo
  return interchangeable `PriceSeries` for the same data.
- `filterwarnings = ["error"]` makes any unexpected warning fail the suite, so
  pandas and numpy deprecations show up early.

**Continuous integration** (`.github/workflows/ci.yml`) runs on every pull
request and every push to `main`:

| Job | What it does |
|---|---|
| Lint | `pre-commit run --all-files`: the same hooks as locally, on every file |
| Tests | Fresh clone → `uv sync --locked` → import check → `pytest`, on Ubuntu, macOS and Windows |

Pre-commit gives fast feedback before a commit exists. CI is the shared check
that nobody can skip, and it covers what the hooks don't: the test suite, a
clean install from the lockfile, all three operating systems, and commits made
on GitHub itself (pull-request merges, web edits).

---

## 10. Documentation

| Document | Contents |
|---|---|
| [docs/v2/architecture.md](docs/v2/architecture.md) | Layers, module dependencies, UML class diagram, data flow, sequence diagram |
| [docs/v2/design_decisions.md](docs/v2/design_decisions.md) | Why each design choice was made, including the input validation policy (task 4.5) |
| [docs/v2/requirements_traceability.md](docs/v2/requirements_traceability.md) | Each requirement of the assignment mapped to code, tests and docs |
| [docs/v2/demo.md](docs/v2/demo.md) | Full guide to `demo.py` |
| [docs/v2/presentation.md](docs/v2/presentation.md) | Five-minute presentation outline |
| [docs/taller_b1_t1.pdf](docs/taller_b1_t1.pdf) | Original assignment |

---

## 11. Limitations

- Monte Carlo uses normal, independent daily shocks. VaR and CVaR therefore
  understate fat tails and volatility clustering. The report lists these
  limitations explicitly.
- Expected returns and covariances are estimated from history by default.
  Means in particular are estimated with a large error.
- Rebalancing ignores transaction costs and taxes.
- Tiingo covers US-listed equities and ETFs only, priced in USD.
- Only long-only, fully invested portfolios are supported (weights ≥ 0 that sum to 1).
- The base currency is fixed to USD (`constants.BASE_CURRENCY`), and FX exposure is unhedged.

---

## 12. Authors

Patricia Martín · Álvaro Hernández · Lautaro Huljich. MIAX, Workshop B1-T1.
