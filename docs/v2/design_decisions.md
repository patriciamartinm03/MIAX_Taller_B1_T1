# Design decisions

The assignment says its educational value lies in the engineering decisions:
abstractions, dataclass modelling, modularity, decoupling and standardised
formats. This document records each decision, the alternatives considered and
the reason for the choice. Section 1 also answers task 4.5, which asks the
group to analyse and justify an input validation policy.

| # | Decision |
|---|---|
| [D1](#d1-input-validation-strict-at-every-boundary) | Input validation: strict, at every boundary |
| [D2](#d2-provider-abstraction-template-method) | Provider abstraction: template method |
| [D3](#d3-batch-download-collects-errors-instead-of-failing) | Batch download collects errors instead of failing |
| [D4](#d4-one-standard-object-per-data-kind) | One standard object per data kind |
| [D5](#d5-usd-as-base-currency-fx-travels-with-the-series) | USD as base currency; FX travels with the series |
| [D6](#d6-alignment-keep-common-dates-never-fill-prices) | Alignment: keep common dates, never fill prices |
| [D7](#d7-adjusted-close-by-default-one-price-type-per-portfolio) | Adjusted close by default; one price type per portfolio |
| [D8](#d8-statistics-computed-on-creation) | Statistics computed on creation |
| [D9](#d9-annualisation-conventions) | Annualisation conventions |
| [D10](#d10-monte-carlo-correlated-gbm-shared-path-engine) | Monte Carlo: correlated GBM, shared path engine |
| [D11](#d11-guards-against-annual-vs-daily-and-percent-vs-decimal-mistakes) | Guards against unit mistakes |
| [D12](#d12-reporting-formats-it-does-not-compute) | Reporting formats, it does not compute |
| [D13](#d13-mutable-models-frozen-configuration) | Mutable models, frozen configuration |
| [D14](#d14-tooling-locked-environment-warnings-as-errors-offline-unit-tests) | Tooling |

---

## D1. Input validation: strict, at every boundary

**Question (task 4.5):** should the program accept any input as long as it
contains a price time series, or should it impose stricter restrictions?

**Decision:** stricter restrictions. Inputs are validated where they enter each
layer, and the program fails fast with a message that names the offending
value.

**Why.** A financial calculation on bad data still returns a number, so the
error is silent. Each example below would produce a plausible but wrong
result:

| If we accepted... | The silent consequence |
|---|---|
| Prices with NaN or gaps that were later filled | Fake 0 % returns, so volatility and correlation are understated |
| Prices ≤ 0 | Infinite or meaningless returns |
| Duplicate or unsorted dates | Wrong returns between the wrong pairs of days |
| A series with no currency | A EUR asset added as if it were USD, with the FX effect lost |
| Pence (`GBp`) treated as pounds | A 100× price level, so FX conversion and value are wrong |
| A mix of `close` and `adj_close` | The adjusted assets look better because dividends are counted for only some of them |
| Weights that do not sum to 1, or negative weights | Leverage or shorting the model does not support |
| An annual `mu` passed where a daily one is expected | A simulation that compounds 252× the intended drift |
| A rate in percent passed as a decimal | A 375 % risk-free rate |
| A string date `"2024-01-01"` or a `datetime` | Implicit parsing and timezone or time-of-day mismatches |

A loose "anything with a time series" interface is easier to call but pushes
these checks onto every user, and most users will skip them. Requiring metadata
(currency, price type, asset type, units) is what makes outputs from different
APIs interoperable.

**Where each check lives:**

| Boundary | File | What is checked |
|---|---|---|
| Request | `extraction/base.py` | `start`/`end` are `datetime.date`, `start ≤ end`, `start` not in the future. Tickers are a list of non-empty `str` without padding (a bare string is rejected, so `"AAPL"` is never iterated as `A, A, P, L`). Duplicates are removed |
| Vendor response | `*_provider.py` | Data is not empty, the expected column exists, the instrument type is supported, the currency is reported, FX data exists |
| Domain object | `PriceSeries`, `MacroSeries` `__post_init__` | Data integrity (see the data contracts in [architecture.md §6](architecture.md#6-data-contracts)), allowed enum values, FX coverage |
| Aggregate | `Portfolio.__post_init__` | Weights, unique tickers, one price type, at least 3 common dates, risk-free currency and units |
| Simulation inputs | `Portfolio._simulation_inputs`, `simulate_returns` | Shapes, finite values, non-negative variance, symmetric and PSD covariance, not annual |
| Pure functions | `metrics.py`, `reporting/plots.py` | Defensive checks, so the functions are safe to call directly |

**Trade-off accepted:** some valid edge cases are rejected. For example, a rate
above 50 % in decimal units is treated as a percentage by mistake. The error
messages explain how to proceed.

---

## D2. Provider abstraction: template method

**Decision:** `PriceProvider` and `MacroProvider` are abstract base classes.
The public methods (`get_prices`, `get_many`) are concrete: they validate and
then delegate to one abstract hook, `_fetch_prices` or `_fetch_series`.

**Alternatives:** a free function per API, or a single class with
`if source == ...` branches.

**Why:** a new source only implements the hook and gets validation and batching
unchanged. Calling code depends on the abstraction (`PriceProvider`), so
`demo.py` switches between yfinance and Tiingo with a dictionary lookup. This
is the decoupling that section 2 of the assignment asks for.

---

## D3. Batch download collects errors instead of failing

**Decision:** `get_many` returns `(series_by_ticker, errors_by_ticker)`.
Download and data errors (`ValueError`, `OSError`) for one ticker are recorded,
and the batch continues. Programming errors (`TypeError`) still raise.

**Why:** with N tickers, one delisted or misspelled symbol should not discard
the other N−1 downloads. The caller decides what to do. `demo.py`, for example,
asks for a replacement ticker and downloads only that one.

---

## D4. One standard object per data kind

**Decision:** every price source returns a `PriceSeries` and every macro source
returns a `MacroSeries`. These are two classes, not one.

**Why two:** prices and indicators have different invariants. Prices must be
> 0 and carry a currency and FX rate. A rate can be 0 or negative, has *units*
(percent, decimal, index, level) and may have no currency. One merged class
would need optional fields and conditional rules everywhere.

**Normalisation done by the providers so the objects really are identical:**
timezone and time of day removed, `ns` resolution fixed (pandas 3 keeps the
parsed resolution otherwise, and indexes from different providers would not
compare equal), subunit currencies converted, vendor column names mapped to
`close`/`adj_close`, and vendor unit labels mapped (FRED `"Percent"` becomes
`percent`).

---

## D5. USD as base currency; FX travels with the series

**Decision:** portfolios are measured in `BASE_CURRENCY = "USD"`. A non-USD
`PriceSeries` must carry `fx_to_usd` (USD per unit of currency). The provider
fetches it from the start date minus 7 days, so it always covers the first
price.

**Why:** a portfolio mixing SAN.MC (EUR) and AAPL (USD) cannot be added up in
two currencies. Keeping local prices and FX separate lets the report split
total return into **local**, **FX** and **USD** (`currency_attribution`). It
also lets the report warn about unhedged currency exposure.

**Limitation:** the base currency is a constant, not a parameter. Making it
configurable would mean fetching FX against that base. The structure allows
it, but it is not implemented.

---

## D6. Alignment: keep common dates, never fill prices

**Decision:** `align_prices` does an inner join on dates and drops any date on
which at least one asset did not trade. FX rates, in contrast, are
forward-filled onto price dates with a 7-day tolerance.

**Alternatives:** forward-fill prices (common in quick scripts), or interpolate.

**Why:** filling a holiday in Madrid with the previous close creates a 0 %
return for SAN.MC on a day the US market moved. That biases volatility and
correlation **downwards**, which makes the portfolio look safer than it is. An
FX rate is different: it is a level that remains the valid conversion until
the next quote, so carrying it forward is correct, and the 7-day cap prevents
stale rates. `Portfolio.benchmark_issues()` reports how many dates were lost
to calendar differences, and the report lists them as warnings.

---

## D7. Adjusted close by default; one price type per portfolio

**Decision:** providers default to `price_type="adj_close"`. A `Portfolio`
rejects assets with mixed price types. A benchmark with a different price type
is allowed, but the report flags it.

**Why:** adjusted prices include dividends, so they measure total return.
Comparing a total-return portfolio with a price index (`^NDX`) overstates
outperformance by the dividend yield. That is why the demo uses QQQ, not
`^NDX`, as the Nasdaq-100 benchmark.

---

## D8. Statistics computed on creation

**Decision (task 4.3):** `mean_return`, `std_return`, `mean_return_usd` and
`std_return_usd` are dataclass fields with `init=False`, computed at the end of
`PriceSeries.__post_init__`, after validation. Annualised figures
(`annual_return`, `annual_volatility`, `max_drawdown`) are properties computed
when accessed.

**Why:** the assignment requires mean and standard deviation to exist as soon
as the object is instantiated. They are cheap, and they are also the default
inputs of the Monte Carlo simulation. Derived and annualised metrics are left
as properties, so they can never disagree with the underlying prices.

---

## D9. Annualisation conventions

| Measure | Convention | Reason |
|---|---|---|
| Annual return | mean of daily simple returns × 252 | Arithmetic mean, consistent with Sharpe |
| Annual volatility | daily std × √252 | Square-root-of-time rule |
| CAGR | `(V_end / V_start)^(365.25 / calendar_days) − 1` | Geometric growth over real elapsed time, unaffected by holidays |
| Risk-free | annual rate ÷ 252, forward-filled onto return dates | Same frequency as the returns it is subtracted from |
| Sharpe, Sortino | computed on daily *excess* returns, then annualised | Handles a risk-free rate that changes over time |

Annual return and CAGR differ on purpose. The first is the arithmetic mean;
the second is the realised compound growth, which is lower by roughly ½σ² per
year. The report shows both, and the gap grows with volatility.

---

## D10. Monte Carlo: correlated GBM, shared path engine

**Decision:**

- `simulate_returns` draws correlated multivariate normal shocks with the
  historical daily covariance (SVD method, robust to near-singular matrices).
  Daily returns are `exp(mu − ½σ² + shock) − 1`. The `−½σ²` drift correction
  makes the expected daily return `exp(mu) − 1 ≈ mu`, so the simulation does
  not add the variance to the historical mean.
- It simulates **assets**, not the portfolio's return directly. The portfolio
  is then built by `returns_to_paths`, which applies the rebalancing rule
  (`1` = daily, `21` = monthly, `63` = quarterly, `None` = buy and hold).
- `Portfolio.value()` passes the real historical returns through the same
  `returns_to_paths`. History and simulation therefore follow exactly the same
  rebalancing logic.
- All parameters are configurable: `SimulationConfig(n_sims, horizon_days,
  initial_value, seed)`, plus `mu`/`cov` overrides for return and volatility
  assumptions (task 4.4).

**Why asset-level:** simulating each asset keeps the correlation structure, and
it makes rebalancing meaningful. Buy and hold drifts away from the target
weights; that effect cannot be modelled from a single portfolio series.

**Single asset:** a one-asset `Portfolio` with weight `[1.0]`. `demo.py` also
calls the engine directly for one asset. With the same seed, that matches a
one-asset portfolio exactly, which serves as a cross-check.

**Known limits:** normal shocks (no fat tails), independent days (no volatility
clustering), constant correlation. The report states these limits in its
"Limitations" section.

---

## D11. Guards against "annual vs daily" and "percent vs decimal" mistakes

**Decision:** heuristics that reject values that are almost certainly in the
wrong unit:

- `|mu| > 0.01` daily (more than 1 % per day on average) is treated as annual by mistake.
- A daily variance `> 0.01` (a daily volatility above 10 %) is treated as annual.
- `|rate| > 0.5` in `decimal` units (more than 50 %) is treated as a percentage.

**Why:** these are the most common silent errors in quantitative code, and they
produce output that looks reasonable. The thresholds are far beyond realistic
values for listed equities and developed-market rates.

---

## D12. Reporting formats, it does not compute

**Decision:** `reporting/report.py` only formats. Every number comes from
`Portfolio`, `SimulationResult` or `metrics.py`. Chart functions in
`reporting/plots.py` take DataFrames, not a `Portfolio`. `report.py` imports
`Portfolio` only under `TYPE_CHECKING`.

**Why:** the report cannot drift from the API. The table in the report is the
same `metrics_table()` a user gets in code. The module has no import cycle, and
each chart can be unit-tested with a synthetic DataFrame.

**Parametrisable (task 4.5):** `ReportSettings` holds the warning thresholds
(max correlation, max weight, minimum effective assets, drawdown limit, minimum
years of history), the VaR level and the number of decimals. Benchmark and
simulation sections appear only when those objects are passed in.

---

## D13. Mutable models, frozen configuration

**Decision:** `PriceSeries`, `MacroSeries` and `Portfolio` are regular
dataclasses. `SimulationConfig`, `ReportSettings` and `DrawdownDetails` are
`frozen=True`.

**Why:** the models normalise their own fields in `__post_init__` (upper-case
currency, sorted prices, aligned FX), which a frozen dataclass makes awkward.
Configuration and result objects are values that should never change after
creation, so freezing them prevents accidental edits and makes them safe to
share.

---

## D14. Tooling: locked environment, warnings as errors, offline unit tests

- **uv + `uv.lock`:** the whole team, and the evaluators, get identical
  dependency versions with a single `uv sync`. This is the plug-and-play
  requirement in task 4.1.
- **`src/` layout:** the package is imported as installed, never by accident
  from the working directory.
- **`filterwarnings = ["error"]`:** pandas 3 and numpy 2 deprecations fail the
  tests immediately instead of breaking a future upgrade.
- **Offline unit tests only:** the API clients (`yf`, `TiingoClient`, `Fred`)
  are replaced by fakes, so the suite is deterministic, fast and needs no keys.
  The network, rate limits and vendor data are outside our control and would
  make a test fail for reasons unrelated to our code. The fakes reproduce the
  vendor formats our code must normalise: timezone-aware indexes, `s`
  resolution, pence quotes, missing values and client exceptions.
- **pre-commit:** formatting, large files and private-key detection before
  every commit. `.env` is git-ignored, and `.env.example` documents the
  variables.
- **CI (GitHub Actions):** pre-commit only runs where it is installed, can be
  skipped with `--no-verify`, does not run on commits made on GitHub, and does
  not run the tests. CI runs the same hooks on every file, then installs the
  locked environment from a fresh clone and runs `pytest` on Linux, macOS and
  Windows, the three systems the README supports. The lint rules live in a
  single place (`.pre-commit-config.yaml`), so local runs and CI cannot drift
  apart.
