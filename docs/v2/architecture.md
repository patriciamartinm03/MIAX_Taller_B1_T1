# Architecture

This document covers task 4.6 of the assignment: the class hierarchy, the
dependencies and the flow of the system. All diagrams are Mermaid, so GitHub
renders them directly. Each one describes the code as it is in `src/miax_toolkit/`.

1. [Layers](#1-layers)
2. [Module dependencies](#2-module-dependencies)
3. [Class diagram (UML)](#3-class-diagram-uml)
4. [Data flow](#4-data-flow)
5. [Sequence: from tickers to report](#5-sequence-from-tickers-to-report)
6. [Data contracts](#6-data-contracts)
7. [Extension points](#7-extension-points)

---

## 1. Layers

The toolkit has five layers. Data only moves forward. Each layer hands the next
a validated, standardised object, never a raw vendor format.

| # | Layer | Package | Responsibility | Output |
|---|---|---|---|---|
| 1 | Extraction | `extraction/` | Talk to the APIs, validate request inputs, translate vendor formats | `PriceSeries`, `MacroSeries` |
| 2 | Preprocessing | `preprocessing/`, `PriceSeries.__post_init__` | Clean (NaN, ≤ 0, duplicates), sort, normalise dates, convert to USD, align calendars | Clean USD prices on common dates |
| 3 | Models | `models/` | Domain objects: series, portfolio, simulation results | `Portfolio` |
| 4 | Simulation | `simulation/` | Correlated GBM returns and path building with rebalancing | `SimulationResult` |
| 5 | Reporting | `reporting/` | Format numbers as Markdown and draw charts | `str` (Markdown), `matplotlib.Figure` |

`metrics.py` and `constants.py` are shared kernels. They hold pure functions and
constants that every layer uses, and they depend on nothing inside the package.

```mermaid
flowchart LR
    subgraph EXT["1. Extraction"]
        direction TB
        PP["PriceProvider (ABC)"]
        MP["MacroProvider (ABC)"]
        YF["YFinanceProvider"]
        TI["TiingoProvider"]
        FR["FredProvider"]
        PP --> YF & TI
        MP --> FR
    end

    subgraph DOM["2-3. Preprocessing + Models"]
        direction TB
        PS["PriceSeries"]
        MS["MacroSeries"]
        AL["align_prices()"]
        PF["Portfolio"]
        PS --> AL --> PF
        MS --> PF
    end

    subgraph SIM["4. Simulation"]
        direction TB
        SR["simulate_returns()"]
        RP["returns_to_paths()"]
        RES["SimulationResult"]
        SR --> RP --> RES
    end

    subgraph REP["5. Reporting"]
        direction TB
        RPT["portfolio_report()"]
        PLT["plot_growth / plot_drawdown / plot_correlation"]
    end

    API[("Yahoo Finance<br/>Tiingo<br/>FRED")] --> EXT
    EXT --> DOM
    PF --> SIM
    PF --> REP
    RES --> REP

    KER[["metrics.py · constants.py<br/>(shared, pure)"]]
    KER -.-> DOM
    KER -.-> SIM
    KER -.-> REP
```

---

## 2. Module dependencies

Runtime imports inside `miax_toolkit`. External libraries are in grey. The graph
has no cycles.

```mermaid
flowchart TD
    constants["constants"]
    metrics["metrics"]
    series["models.series"]
    macro["models.macro"]
    results["models.results"]
    portfolio["models.portfolio"]
    base["extraction.base"]
    yfp["extraction.yfinance_provider"]
    tip["extraction.tiingo_provider"]
    frp["extraction.fred_provider"]
    align["preprocessing.alignment"]
    mc["simulation.montecarlo"]
    report["reporting.report"]
    plots["reporting.plots"]

    metrics --> constants
    series --> metrics & constants
    results --> metrics & mc
    portfolio --> metrics & constants & series & macro & results & align & mc & report & plots
    report --> metrics & constants
    base --> series & macro
    yfp & tip --> base & series
    frp --> base & macro

    yf(["yfinance"]):::ext
    tg(["tiingo"]):::ext
    fa(["fredapi"]):::ext
    yfp --> yf
    tip --> tg
    frp --> fa

    classDef ext fill:#eee,stroke:#999,color:#555
```

Properties of this graph that matter for the design:

- **Ingestion is isolated.** Only `extraction/*` imports `yfinance`, `tiingo`
  or `fredapi`. Nothing outside `extraction/` knows which API produced a
  series.
- **Models do not depend on extraction.** A `PriceSeries` can be built from
  any source, including a CSV file or a test fixture.
- **Engines are pure.** `metrics`, `preprocessing.alignment`,
  `simulation.montecarlo` and `reporting.plots` take pandas or numpy objects
  and return new ones. They know nothing about `Portfolio`, so each one can be
  tested on its own.
- **`Portfolio` is the façade.** It wires the engines together and exposes
  `monte_carlo()`, `report()` and `plots_report()` as methods, as the
  assignment requires.
- **Reporting does not import `Portfolio` at run time.** `reporting.report`
  imports it only under `TYPE_CHECKING`, for type hints. This avoids an import
  cycle and keeps the formatting code independent of the model.

---

## 3. Class diagram (UML)

```mermaid
classDiagram
    direction LR

    class PriceProvider {
        <<abstract>>
        +source: str
        +get_prices(ticker, start, end) PriceSeries
        +get_many(tickers, start, end) tuple
        #_fetch_prices(ticker, start, end) PriceSeries*
    }
    class YFinanceProvider {
        +source = "yfinance"
        +price_type: str
    }
    class TiingoProvider {
        +source = "tiingo"
        +price_type: str
        +asset_type: str
    }
    class MacroProvider {
        <<abstract>>
        +source: str
        +get_series(series_id, start, end, currency) MacroSeries
        +get_many(series_ids, start, end, currency) tuple
        #_fetch_series(series_id, start, end, currency) MacroSeries*
    }
    class FredProvider {
        +source = "fred"
    }

    class PriceSeries {
        <<dataclass>>
        +ticker: str
        +name: str
        +asset_type: equity | etf | index
        +currency: str
        +source: str
        +prices: Series
        +price_type: close | adj_close
        +fx_to_usd: Series | None
        +mean_return: float  «auto»
        +std_return: float  «auto»
        +mean_return_usd: float  «auto»
        +std_return_usd: float  «auto»
        +daily_returns() Series
        +daily_usd_returns() Series
        +usd_prices() Series
        +annual_return / annual_volatility
        +annual_return_usd / annual_volatility_usd
        +max_drawdown
    }
    class MacroSeries {
        <<dataclass>>
        +series_id: str
        +name: str
        +units: percent | decimal | index | level
        +source: str
        +as_of: date
        +values: Series
        +currency: str | None
        +mean: float  «auto»
        +as_decimal() Series
    }

    class Portfolio {
        <<dataclass>>
        +name: str
        +assets: list~PriceSeries~
        +weights: list~float~
        +risk_free: MacroSeries | None
        +prices: DataFrame  «auto, USD, aligned»
        +asset_returns() DataFrame
        +returns() Series
        +value(initial_value, rebalance_every) Series
        +metrics_table(benchmark) DataFrame
        +benchmark_comparison(benchmark) Series
        +benchmark_issues(benchmark) list~str~
        +benchmark_overlap(benchmark) DataFrame
        +correlation() DataFrame
        +diversification_benefit() float
        +currency_exposure() Series
        +currency_attribution() DataFrame
        +effective_n_assets() float
        +drawdown_details() DrawdownDetails
        +simulation_assumptions(mu, cov) DataFrame
        +monte_carlo(config, mu, cov, rebalance_every) SimulationResult
        +report(benchmark, simulation, settings) str
        +plots_report(benchmark, simulation, show_assets, path) Figure
    }

    class SimulationConfig {
        <<frozen dataclass>>
        +n_sims: int = 1000
        +horizon_days: int = 252
        +initial_value: float = 100
        +seed: int | None
    }
    class SimulationResult {
        <<dataclass>>
        +paths: ndarray n_sims x horizon+1
        +config: SimulationConfig
        +rebalance_every: int | None
        +mu: ndarray | None
        +cov: ndarray | None
        +final_values: ndarray
        +prob_loss() float
        +value_at_risk(level) float
        +expected_shortfall(level) float
        +percentiles(levels) DataFrame
        +plot_paths() Axes
        +plot_distribution() Axes
        +plot() Figure
    }
    class ReportSettings {
        <<frozen dataclass>>
        +max_correlation = 0.8
        +max_weight = 0.4
        +min_effective_assets = 3
        +max_drawdown_limit = -0.20
        +min_years = 5
        +var_level = 5
        +decimals = 2
    }
    class DrawdownDetails {
        <<frozen dataclass>>
        +max_drawdown: float
        +peak_date / trough_date
        +recovery_date: Timestamp | None
    }

    PriceProvider <|-- YFinanceProvider
    PriceProvider <|-- TiingoProvider
    MacroProvider <|-- FredProvider
    PriceProvider ..> PriceSeries : creates
    MacroProvider ..> MacroSeries : creates

    Portfolio "1" o-- "1..*" PriceSeries : assets
    Portfolio "1" o-- "0..1" MacroSeries : risk_free
    Portfolio ..> Portfolio : benchmark
    Portfolio ..> SimulationResult : monte_carlo()
    Portfolio ..> ReportSettings : report()
    Portfolio ..> DrawdownDetails
    SimulationResult *-- SimulationConfig
```

Notes:

- `get_prices` and `get_many` are concrete **template methods**. They validate
  the inputs and then call the abstract `_fetch_prices`, so every provider gets
  the same validation and batching for free.
- Fields marked «auto» use `field(init=False)` and are computed in
  `__post_init__`. In particular, the mean and standard deviation the
  assignment asks for (task 4.3) exist as soon as the object is created.
- A benchmark is just another `Portfolio`. A single index is a one-asset
  portfolio with weight `[1.0]`.

---

## 4. Data flow

What happens to the data at each step, and which rule is enforced there.

```mermaid
flowchart TD
    IN[/"User input<br/>tickers: list[str] · start, end: date · weights"/]

    subgraph S1["1 · Provider boundary  (extraction/base.py)"]
        V1["validate_dates: real date objects, start ≤ end, start not in future<br/>tickers: list of str, non-empty, no padding; duplicates removed"]
    end

    subgraph S2["2 · Vendor translation  (*_provider.py)"]
        V2["download → pick close / adj_close column → dropna<br/>dates: drop tz and time, ns resolution<br/>GBp/ILA/ZAc ÷ 100 → GBP/ILS/ZAR<br/>non-USD: download {CCY}USD=X rate (start−7d … end+7d)<br/>check instrument type ∈ {EQUITY, ETF, INDEX}"]
        ERR[["errors dict<br/>{ticker: message}"]]
    end

    subgraph S3["3 · PriceSeries.__post_init__  (models/series.py)"]
        V3["Series with DatetimeIndex, numeric, no NaN, > 0, unique dates, ≥ 3 prices<br/>sort by date · upper-case currency<br/>FX must cover first..last price; forward-fill FX at most 7 days onto price dates<br/>compute mean/std of daily returns (local and USD)"]
    end

    subgraph S4["4 · Portfolio.__post_init__  (models/portfolio.py)"]
        V4["≥ 1 asset · all PriceSeries · one weight per asset · unique tickers<br/>same price_type · weights finite, ≥ 0, sum = 1"]
        AL["align_prices({ticker: usd_prices()})<br/>inner join on dates · NO filling · ≥ 3 common dates"]
        RF["risk_free: MacroSeries in USD, percent/decimal<br/>→ decimal → ÷ 252 → forward-fill onto return dates"]
    end

    subgraph S5["5 · Analysis"]
        RET["asset_returns() = pct_change of aligned USD prices<br/>value() = returns_to_paths(real returns, rebalance_every)"]
        MET["metrics_table · benchmark_comparison (common dates only)<br/>correlation · diversification · currency attribution"]
    end

    subgraph S6["6 · Monte Carlo"]
        MU["mu, cov: historical DAILY, or user override<br/>(shape, finite, variance ≥ 0, not annual)"]
        GBM["simulate_returns: (n_sims, horizon, n_assets)<br/>exp(mu − ½σ² + correlated shock) − 1"]
        PATH["returns_to_paths: (n_sims, horizon+1)<br/>weights reset every rebalance_every days"]
    end

    subgraph S7["7 · Outputs"]
        MD[/"report() → Markdown str"/]
        FIG[/"plots_report() → Figure (+ PNG)"/]
        SIMR[/"SimulationResult: VaR, CVaR, P(loss), plot()"/]
    end

    IN --> V1 --> V2
    V2 -- ValueError / OSError --> ERR
    V2 --> V3 --> V4 --> AL --> RET
    V4 --> RF --> MET
    RET --> MET
    RET --> MU --> GBM --> PATH --> SIMR
    MET --> MD & FIG
    SIMR --> MD & FIG
```

Two choices in this flow deserve emphasis. Both are explained in
[design_decisions.md](design_decisions.md).

- **Asset prices are never filled. FX rates are forward-filled for at most 7
  days.** Filling a missing price creates a fake 0 % return, which lowers
  volatility and correlation. An FX rate is a level that stays valid until the
  next quote, and the 7-day limit stops a stale rate from being used for long.
- **The same path engine (`returns_to_paths`) values both history and
  simulation.** The historical value and the Monte Carlo paths therefore apply
  the same rebalancing rule.

---

## 5. Sequence: from tickers to report

```mermaid
sequenceDiagram
    actor U as User / demo.py
    participant P as YFinanceProvider
    participant API as Yahoo Finance
    participant S as PriceSeries
    participant F as FredProvider
    participant PF as Portfolio
    participant MC as simulation.montecarlo
    participant R as reporting

    U->>P: get_many(["AAPL","SAN.MC"], start, end)
    loop each ticker
        P->>P: get_prices → validate inputs
        P->>API: history + metadata (+ EURUSD=X if not USD)
        API-->>P: vendor DataFrame
        P->>S: PriceSeries(...)
        S->>S: __post_init__: validate, align FX, mean/std
        S-->>P: PriceSeries
    end
    P-->>U: (series, errors)

    U->>F: get_series("DTB3", start, end, currency="USD")
    F-->>U: MacroSeries

    U->>PF: Portfolio(name, assets, weights, risk_free)
    PF->>PF: validate weights · usd_prices · align_prices · daily risk-free

    U->>PF: monte_carlo(config, rebalance_every=21)
    PF->>PF: _simulation_inputs (historical daily mu, cov)
    PF->>MC: simulate_returns(mu, cov, n_sims, horizon, seed)
    MC-->>PF: returns (n_sims, horizon, n_assets)
    PF->>MC: returns_to_paths(returns, weights, initial, rebalance_every)
    MC-->>PF: paths (n_sims, horizon+1)
    PF-->>U: SimulationResult

    U->>PF: report(benchmark, simulation, settings)
    PF->>R: portfolio_report(self, ...)
    R->>PF: metrics_table · correlation · currency_attribution ...
    R-->>U: Markdown str

    U->>PF: plots_report(benchmark, simulation, path)
    PF->>R: plot_growth · plot_drawdown · plot_correlation
    PF->>PF: simulation.plot_paths · plot_distribution
    PF-->>U: Figure (saved to path)
```

---

## 6. Data contracts

These invariants hold for every object, whichever provider created it. This is
what "standardised output" (task 4.2) means in practice.

| Object | Field | Contract |
|---|---|---|
| `PriceSeries` | `prices` | `pd.Series`, `DatetimeIndex` tz-naive at midnight in `ns` resolution, sorted ascending, unique dates, numeric, no NaN, all > 0, at least 3 values |
| | `currency` | ISO code, upper case, main unit (never pence or cents) |
| | `fx_to_usd` | `None` if the currency is USD. Otherwise USD per unit of currency, on exactly the dates of `prices` |
| | `asset_type` | `equity`, `etf` or `index` |
| | `price_type` | `close` or `adj_close` |
| `MacroSeries` | `values` | `pd.Series`, `DatetimeIndex`, sorted, unique, numeric, no NaN, at least 1 value |
| | `units` | `percent` (3.75), `decimal` (0.0375, \|x\| ≤ 0.5), `index` or `level` |
| `Portfolio` | `prices` | `DataFrame` with one column per ticker, **in USD**, only the dates shared by all assets, at least 3 rows |
| | `weights` | `float`, finite, ≥ 0, one per asset, sum to 1 |
| `SimulationResult` | `paths` | `ndarray` of shape `(n_sims, horizon_days + 1)`. Column 0 is `initial_value` |
| | `mu`, `cov` | **Daily** simple-return mean and covariance, given together or not at all |

Units used throughout: returns are **daily simple returns** as decimals.
Annualisation uses 252 trading days (`constants.TRADING_DAYS`), except CAGR,
which uses 365.25 calendar days.

---

## 7. Extension points

| To add... | Do this | What else changes |
|---|---|---|
| A new price API (Alpha Vantage, Polygon...) | Subclass `PriceProvider`, set `source`, implement `_fetch_prices` returning a `PriceSeries` | Nothing. Validation and `get_many` are inherited |
| A new macro or fundamentals source | Subclass `MacroProvider` and implement `_fetch_series` | Nothing |
| A new metric | Add a pure function to `metrics.py`, then a column in `Portfolio._metrics_row` | The report picks it up only if added to the table formatting |
| A new chart | Add a function to `reporting/plots.py` that takes a DataFrame and an `ax` | Wire it into `Portfolio.plots_report` |
| A new warning rule | Add a check in `reporting.report.risk_warnings` and, if it needs a threshold, a field in `ReportSettings` | Nothing |
| A different simulation model | Add a function with the same output shape as `simulate_returns` | `Portfolio.monte_carlo` would need a parameter to choose the model |
