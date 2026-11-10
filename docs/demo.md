# Interactive demo (`demo.py`)

`demo.py` is a console program that builds a portfolio step by step from the
user's answers and analyses it end to end. It walks through the five layers of
`miax_toolkit`, one per step, calling the public API of each module:

| Step | Module | What it does | Assignment requirement |
|---|---|---|---|
| 1 | `extraction` | Downloads prices (`get_many`) and the FRED risk-free rate (`get_series`) | 4.2 |
| 2 | `preprocessing` | Converts to USD (`usd_prices`) and aligns dates (`align_prices`) | 4.5 cleaning |
| 3 | `models` | Builds `PriceSeries` and `Portfolio`; exposure and metrics | 4.3 |
| 4 | `simulation` | Monte Carlo of the portfolio and of a single asset | 4.4 |
| 5 | `reporting` | Markdown `report()` and `plots_report()` | 4.5 reports |

It is not part of the package: `demo.py` only **uses** `miax_toolkit`, the same
way any user would. All the calculations live in `src/`.

The program itself talks to the user in Spanish; the prompts and answers quoted
below (`s`/`n`, `mensual`, "Valor no valido"...) are shown exactly as typed or
printed.

---

## 1. Requirements

- The project set up as described in the [README](../README.md): `uv sync` already run.
- API keys in `.env` (optional):

| Variable | Used for | Without it |
|---|---|---|
| `FRED_API_KEY` | Risk-free rate (3-month Treasury bill, `DTB3`) | 0 is used for Sharpe and Sortino, and the report says so |
| `TIINGO_API_KEY` | Only if you choose Tiingo as the price source | The demo stops when creating the provider |

```bash
cp .env.example .env        # macOS / Linux
Copy-Item .env.example .env # Windows (PowerShell)
```

---

## 2. Running it

From the repository root:

```bash
uv run --env-file .env python demo.py   # with API keys
uv run python demo.py                   # without .env
```

Every question shows a default value in brackets; **Enter accepts it**.
Pressing Enter on every question runs the example portfolio:
AAPL 30 %, MSFT 30 %, SAN.MC 40 % against SPY 60 % + FEZ 40 %.

To repeat a run without typing, pipe the answers through standard input (one
per line; `""` means Enter):

```bash
printf '%s\n' \
  "US Tech" "yfinance" "2019-01-01" "" \
  "6" AAPL 20 MSFT 20 NVDA 20 GOOGL 15 AMZN 15 META 10 \
  s 1 QQQ 100 \
  2000 252 10000 mensual 42 \
  n \
| uv run --env-file .env python demo.py
```

> If a ticker fails to download, the demo asks for a replacement and the
> answers piped with `printf` no longer line up: it ends with "Demo cancelada.".
> Run it again interactively.

Ctrl+C cancels at any time.

---

## 3. Questions

All of them are asked up front, in this order:

| # | Question | Default | Validation (asks again if it fails) |
|---|---|---|---|
| 1 | Portfolio name | `Cartera demo` | Not empty; surrounding quotes are removed |
| 2 | Price source | `yfinance` | `yfinance` or `tiingo` |
| 3 | Start date | `2019-01-01` | Format `YYYY-MM-DD`, not in the future |
| 4 | End date | today | After the start date, not in the future |
| 5 | Number of assets in the portfolio | `3` | Integer between 1 and 50 |
| 6 | Ticker of each asset | example | No spaces, no repeats; converted to upper case |
| 7 | Weight of each asset, in % | see below | Between 0 and what is left up to 100 %; accepts `30,5` and `30%` |
| 8 | Compare with a benchmark? | `s` | `s` (yes) or `n` (no) |
| 9 | Benchmark assets and weights | `SPY`, `FEZ` | Same as 5–7 |
| 10 | Number of simulations | `1000` | Between 1 and 100,000 |
| 11 | Horizon in trading days | `252` (1 year) | Between 1 and 7,560 (30 years) |
| 12 | Initial value | `10000` | Greater than 0 |
| 13 | Rebalancing | `mensual` | `diario`, `mensual`, `trimestral` or `ninguno` |
| 14 | Seed | `42` | Integer ≥ 0 (same seed, same results) |
| 15 | Show the charts on screen? | `n` | `s` or `n` (asked at the end) |

**Default weights:** if the number of assets matches the example, it proposes
the example weights; otherwise it splits what is left equally. The last asset
always proposes whatever is missing to reach 100 %. If the weights do not add up
to 100 % at the end, it asks for all the assets again.

**Rebalancing:** `diario` = every day, `mensual` (monthly) = every 21 trading
days, `trimestral` (quarterly) = every 63, `ninguno` (none) = buy and hold.

---

## 4. What each step shows

### Step 1 — Extraction (`miax_toolkit.extraction`)

- **Risk-free rate:** `FredProvider().get_series("DTB3", ...)` returns a
  `MacroSeries`; its name, number of values and mean are shown.
- **Prices:** `provider.get_many(tickers, start, end)` returns one `PriceSeries`
  per ticker and the errors separately. Tickers that fail can be replaced
  without starting over.
- Table per asset: ticker, name, type (`equity`, `etf`, `index`), currency,
  weight, dates, number of prices, and **daily mean and standard deviation**.
  These two are computed automatically when each `PriceSeries` is created
  (`__post_init__`).

The fields are the same with yfinance or Tiingo: the output is standardised.

### Step 2 — Cleaning and alignment (`miax_toolkit.preprocessing`)

- Every asset not quoted in USD is converted with `usd_prices()` (daily exchange
  rate, unhedged).
- `align_prices()` keeps only the dates on which **all** the assets trade. It
  does not fill gaps: that would create fake 0 % returns.
- Table: maximum dates, common dates, dropped dates and resulting period, for
  the portfolio and for the benchmark.

### Step 3 — Modelling (`miax_toolkit.models`)

- Creates `Portfolio(name, assets, weights, risk_free=...)`. The portfolio
  aligns its assets on its own; the demo checks that the result is identical to
  step 2.
- Currency exposure, effective number of assets (1 / Σ weights²) and average
  risk-free rate over the period.
- Metrics table (`metrics_table`), annualised and in USD: annual return, CAGR,
  volatility, Sharpe, Sortino and maximum drawdown, for each asset, the
  portfolio and the benchmark.

### Step 4 — Monte Carlo (`miax_toolkit.simulation`)

- **Portfolio:** `portfolio.monte_carlo(config, rebalance_every=...)`, the
  portfolio method the assignment asks for.
- **Single asset:** the one with the largest weight (on a tie, the first one
  entered), simulated by calling `simulate_returns` and `returns_to_paths`
  directly.
- Table: median final value, probability of loss, VaR 95 % and CVaR 95 %.
  - **VaR 95 %:** minimum loss in the worst 5 % of scenarios.
  - **CVaR 95 %:** average loss in that 5 %.

Both simulations use the same configuration and seed. With a single-asset
portfolio they give exactly the same result, which works as a cross-check.

### Step 5 — Report and charts (`miax_toolkit.reporting`)

Saved in `output/`, next to `demo.py` (ignored by git):

| File | Contents |
|---|---|
| `report.md` | `portfolio.report(benchmark, simulation)`: summary, composition, performance, diversification, simulation, warnings and methodology notes |
| `plots_report.png` | `portfolio.plots_report(...)`: growth in base 100 (portfolio, benchmark and assets), drawdown, correlations, simulated paths and final value distribution |
| `montecarlo_asset.png` | Paths and distribution of the single-asset simulation |

---

## 5. Examples to try

For each case, the answers in order. "Enter" = default value.

| Case | Answers | What to check |
|---|---|---|
| Default example | Enter on everything | EUR → USD conversion of SAN.MC; unhedged currency warning in the report |
| US tech against the Nasdaq-100 | see the `printf` command in section 2 | Everything in USD; comparison with QQQ |
| Stocks + index | `Acciones + indice` · Enter · `2018-01-01` · Enter · `3` · `AAPL` · `40` · `JPM` · `30` · `^GSPC` · Enter · `n` · Enter ×5 · `s` | `^GSPC` shows up with type `index` |
| Single asset | `Solo Apple` · Enter ×3 · `1` · `AAPL` · Enter · `n` · `5000` · `504` · `1000` · `ninguno` · `1` | No correlation or diversification section; both simulations match |
| Several currencies | `Multidivisa` · Enter ×3 · `4` · `SAN.MC` · `25` · `BP.L` · `25` · `7203.T` · `25` · `MSFT` · Enter · `n` · Enter ×5 | EUR, GBP (BP.L is quoted in pence), JPY and USD |
| Risk warnings | `Concentrada` · Enter · `2024-01-01` · Enter · `2` · `SPY` · `80` · `VOO` · Enter · `n` · Enter ×5 | Correlation > 0.8, weight > 40 %, history < 5 years |
| Unknown ticker | Like the default, with `XXXX123` as the 2nd ticker; then Enter and `GOOG` | It is replaced without losing the rest |
| Validation | `bloomberg` as source, `01/01/2020` as date, `0` assets, repeated ticker, weight `120` | Message "Valor no valido" and the question is asked again |

Why QQQ and not `^NDX`? QQQ is an ETF with a dividend-adjusted price, like the
portfolio prices. `^NDX` is a price index without dividends and would make the
portfolio look better than it is.

---

## 6. Limitations

- The simulation uses **historical** returns and volatilities with a normal
  distribution: it is optimistic in the tails and does not predict the future.
  The report includes these warnings.
- Tiingo only covers US stocks and ETFs (no indices or other currencies).
- Yahoo Finance may rate-limit requests or be blocked behind a VPN.

---

## 7. How `demo.py` is organised

It only holds what belongs to the console interface. No financial calculation
lives here.

| Group | Functions | Purpose |
|---|---|---|
| Questions | `ask`, `parse_*`, `ask_assets` | Ask, validate and ask again |
| Output | `step`, `section`, `table`, `pct`, `num` | Step headers and aligned tables |
| Step 1 | `download`, `show_price_series`, `load_risk_free` | Download with replacement of failed tickers |
| Step 2 | `align` | Conversion to USD and alignment, with a summary |
| Step 3 | `show_metrics` | Formatted metrics table |
| Step 4 | `simulate_asset`, `simulation_row` | Single-asset Monte Carlo and results row |
| Step 5 | `save_charts`, `save_simulation_chart` | Save the charts |
| Program | `main` | Order of questions and steps |
