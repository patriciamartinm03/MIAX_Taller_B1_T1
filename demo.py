"""Interactive demo of miax_toolkit: build a portfolio step by step and analyse it.

Run from the project root:
    uv run --env-file .env python demo.py

The demo walks through the five layers of the toolkit, one step each:
    1. extraction     providers download prices and macro data
    2. preprocessing  conversion to USD and alignment of dates
    3. models         PriceSeries and Portfolio, with their statistics
    4. simulation     Monte Carlo of the portfolio and of a single asset
    5. reporting      Markdown report and charts

Every question has a default value in [brackets]: press Enter to accept it.
Pressing Enter on every question runs the example portfolio.
FRED_API_KEY in .env is optional: without it the risk-free rate is 0.
TIINGO_API_KEY is only needed if you choose Tiingo as the price source.
Output goes to output/ next to this file (report.md and PNG charts).
"""

import sys
import warnings
from collections.abc import Callable
from datetime import date
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pandas.errors import Pandas4Warning

from miax_toolkit.extraction import (
    FredProvider,
    PriceProvider,
    TiingoProvider,
    YFinanceProvider,
)
from miax_toolkit.models import MacroSeries, PriceSeries
from miax_toolkit.models.portfolio import Portfolio
from miax_toolkit.models.results import SimulationConfig, SimulationResult
from miax_toolkit.preprocessing.alignment import align_prices
from miax_toolkit.simulation.montecarlo import returns_to_paths, simulate_returns

OUTPUT = Path(__file__).resolve().parent / "output"

# The data libraries (yfinance, tiingo, fredapi) still call pandas APIs that
# pandas 4 will remove. Hide only those: a Pandas4Warning raised from our own
# code would still be shown, because it means miax_toolkit needs fixing.
warnings.filterwarnings(
    "ignore", category=Pandas4Warning, module=r"(yfinance|tiingo|fredapi)(\.|$)"
)

# Defaults: 60 % US / 40 % Europe, benchmark with the same weights by region
EXAMPLE_ASSETS = [("AAPL", 30.0), ("MSFT", 30.0), ("SAN.MC", 40.0)]
EXAMPLE_BENCHMARK = [("SPY", 60.0), ("FEZ", 40.0)]

PROVIDERS: dict[str, Callable[[], PriceProvider]] = {
    "yfinance": YFinanceProvider,  # equities, ETFs and indices; no API key
    "tiingo": TiingoProvider,  # US equities only; needs TIINGO_API_KEY
}
REBALANCING = {"diario": 1, "mensual": 21, "trimestral": 63, "ninguno": None}


# Generic input helpers


def ask[T](question: str, default: str, parse: Callable[[str], T]) -> T:
    """Ask until parse accepts the answer. Enter returns the default."""
    while True:
        answer = input(f"{question} [{default}]: ").strip() or default
        try:
            return parse(answer)
        except ValueError as error:
            print(f"  Valor no valido: {error}")


def parse_name(text: str) -> str:
    name = text.strip().strip("\"'").strip()  # typed quotes are not part of it
    if not name:
        raise ValueError("el nombre no puede estar vacio")
    return name


def parse_int(low: int, high: int) -> Callable[[str], int]:
    def parse(text: str) -> int:
        value = int(text)
        if not low <= value <= high:
            raise ValueError(f"debe estar entre {low} y {high}")
        return value

    return parse


def parse_float_positive(text: str) -> float:
    value = float(text.replace(",", "."))
    if value <= 0:
        raise ValueError("debe ser mayor que 0")
    return value


def parse_date(after: date | None = None) -> Callable[[str], date]:
    def parse(text: str) -> date:
        value = date.fromisoformat(text)  # raises ValueError if not YYYY-MM-DD
        if value > date.today():
            raise ValueError("la fecha no puede ser futura")
        if after is not None and value <= after:
            raise ValueError(f"debe ser posterior a {after}")
        return value

    return parse


def parse_choice(options: list[str]) -> Callable[[str], str]:
    def parse(text: str) -> str:
        text = text.lower()
        if text not in options:
            raise ValueError(f"elige una de: {', '.join(options)}")
        return text

    return parse


def parse_yes_no(text: str) -> bool:
    return parse_choice(["s", "n"])(text) == "s"


def parse_ticker(taken: set[str]) -> Callable[[str], str]:
    def parse(text: str) -> str:
        ticker = text.upper()
        if " " in ticker:
            raise ValueError("el ticker no puede tener espacios")
        if ticker in taken:
            raise ValueError(f"{ticker} ya esta en la cartera")
        return ticker

    return parse


def parse_weight(remaining: float) -> Callable[[str], float]:
    def parse(text: str) -> float:
        weight = float(text.rstrip("%").replace(",", "."))
        if not 0 < weight <= remaining + 1e-9:
            raise ValueError(f"el peso debe estar entre 0 y {remaining:g} %")
        return weight

    return parse


def ask_assets(label: str, examples: list[tuple[str, float]]) -> dict[str, float]:
    """Tickers and weights (in %), until the weights add up to 100 %."""
    n_assets = ask(
        f"Cuantos activos tendra {label}?", str(len(examples)), parse_int(1, 50)
    )
    while True:
        assets: dict[str, float] = {}
        remaining = 100.0
        for position in range(1, n_assets + 1):
            left = n_assets - position + 1
            example_ticker = (
                examples[position - 1][0] if position <= len(examples) else ""
            )
            ticker = ask(
                f"  Activo {position} - ticker",
                example_ticker,
                parse_ticker(set(assets)),
            )
            if left == 1:
                default_weight = remaining  # the last asset completes 100 %
            elif n_assets == len(examples):
                default_weight = examples[position - 1][1]
            else:
                default_weight = round(remaining / left, 2)
            weight = ask(
                f"  Activo {position} - peso en %",
                f"{default_weight:g}",
                parse_weight(remaining),
            )
            assets[ticker] = weight
            remaining -= weight
        if abs(remaining) < 1e-6:
            return {ticker: weight / 100 for ticker, weight in assets.items()}
        print(
            f"  Los pesos suman {100 - remaining:g} %, deben sumar 100 %. "
            "Vuelve a introducirlos."
        )


# Console output helpers (ASCII only, so any terminal can print them)

WIDTH = 78


def step(number: int, title: str, module: str) -> None:
    print("\n" + "=" * WIDTH)
    print(f" PASO {number}/5  {title.upper()}")
    print(f" modulo: {module}")
    print("=" * WIDTH)


def section(title: str) -> None:
    print(f"\n-- {title} " + "-" * max(0, WIDTH - len(title) - 4))


def table(
    headers: list[str],
    rows: list[list[str]],
    left: int = 1,
    split_before: int | None = None,
) -> None:
    """Print rows in aligned columns: text to the left, numbers to the right.

    left: how many leading columns hold text (aligned to the left).
    split_before: index of the row before which a separator line is drawn.
    """
    widths = [max(len(str(cell)) for cell in column) for column in zip(headers, *rows)]

    def line(cells: list[str]) -> str:
        return "  " + "  ".join(
            f"{cell:<{width}}" if position < left else f"{cell:>{width}}"
            for position, (cell, width) in enumerate(zip(cells, widths))
        )

    rule = "  " + "  ".join("-" * width for width in widths)
    print(line(headers))
    print(rule)
    for position, row in enumerate(rows):
        if position == split_before:
            print(rule)
        print(line(row))


def pct(value: float, decimals: int = 1) -> str:
    return f"{value:.{decimals}%}"


# Step 1: extraction


def download(
    provider: PriceProvider, weights: dict[str, float], start: date, end: date
) -> tuple[list[PriceSeries], list[float]]:
    """get_many for every ticker; for the ones that fail, ask for a replacement."""
    print(f"  {provider.source}.get_many: {', '.join(weights)}")
    series, errors = provider.get_many(list(weights), start, end)
    while errors:
        for ticker, error in errors.items():
            print(f"  No se pudo descargar {ticker}: {error}")
        retry = ask(
            "Quieres sustituir los tickers que han fallado? (s/n)", "s", parse_yes_no
        )
        if not retry:
            raise SystemExit("Demo cancelada: faltan datos de algunos activos.")
        for ticker in list(errors):
            weight = weights.pop(ticker)
            new = ask(
                f"  Nuevo ticker en lugar de {ticker}", "", parse_ticker(set(weights))
            )
            weights[new] = weight
        missing = [ticker for ticker in weights if ticker not in series]
        new_series, errors = provider.get_many(missing, start, end)
        series.update(new_series)
    return [series[ticker] for ticker in weights], list(weights.values())


def show_price_series(assets: list[PriceSeries], weights: list[float]) -> None:
    """Same PriceSeries fields whatever the provider; mean and std come from init."""
    rows = [
        [
            asset.ticker,
            asset.name[:24],
            asset.asset_type,
            asset.currency,
            pct(weight, 0),
            str(asset.prices.index[0].date()),
            str(asset.prices.index[-1].date()),
            str(len(asset.prices)),
            f"{asset.mean_return:+.3%}",
            pct(asset.std_return, 3),
        ]
        for asset, weight in zip(assets, weights)
    ]
    headers = ["Ticker", "Nombre", "Tipo", "Divisa", "Peso", "Desde", "Hasta"]
    table([*headers, "Precios", "Media dia", "Desv. dia"], rows, left=4)
    first = assets[0]
    print(f"  Fuente: {first.source}, precio {first.price_type}.", end=" ")
    print("Media y desviacion se calculan al crear cada PriceSeries.")


def load_risk_free(start: date, end: date) -> MacroSeries | None:
    section("Tipo sin riesgo (FRED)")
    try:
        series = FredProvider().get_series("DTB3", start, end, currency="USD")
    except ValueError as error:
        first_line = str(error).splitlines()[0]
        print(f"  No disponible ({first_line})")
        print("  Se usa un tipo sin riesgo de 0 para Sharpe y Sortino.")
        return None
    print(f"  {series.series_id}: {series.name}")
    mean = float(series.as_decimal().mean())
    print(f"  {len(series.values)} datos, media del periodo descargado {pct(mean, 2)}")
    return series


# Step 2: preprocessing


def align(label: str, assets: list[PriceSeries]) -> tuple[pd.DataFrame, list[str]]:
    """Convert each asset to USD and keep only the dates all of them share."""
    for asset in assets:
        if asset.currency != "USD":
            print(f"  {asset.ticker}: precios en {asset.currency}, convertidos a USD")
    usd_prices = {asset.ticker: asset.usd_prices() for asset in assets}
    aligned = align_prices(usd_prices)
    longest = max(len(prices) for prices in usd_prices.values())
    row = [
        label,
        str(longest),
        str(len(aligned)),
        str(longest - len(aligned)),
        str(aligned.index[0].date()),
        str(aligned.index[-1].date()),
    ]
    return aligned, row


# Step 4: simulation of a single asset, with the simulation module directly


def simulate_asset(asset: PriceSeries, config: SimulationConfig) -> SimulationResult:
    mu = np.array([asset.mean_return_usd])  # daily, in USD
    cov = np.array([[asset.std_return_usd**2]])
    returns = simulate_returns(mu, cov, config.n_sims, config.horizon_days, config.seed)
    paths = returns_to_paths(
        returns, np.array([1.0]), config.initial_value, rebalance_every=None
    )
    return SimulationResult(paths, config, rebalance_every=None, mu=mu, cov=cov)


def simulation_row(label: str, simulation: SimulationResult) -> list[str]:
    return [
        label,
        f"{np.median(simulation.final_values):,.0f}",
        pct(simulation.prob_loss()),
        pct(simulation.value_at_risk()),
        pct(simulation.expected_shortfall()),
    ]


METRIC_COLUMNS = {
    "annual_return": "Rent. anual",
    "cagr": "CAGR",
    "annual_volatility": "Volatilidad",
    "sharpe": "Sharpe",
    "sortino": "Sortino",
    "max_drawdown": "Max. caida",
}


def show_metrics(portfolio: Portfolio, benchmark: Portfolio | None) -> None:
    metrics = portfolio.metrics_table(benchmark)
    ratios = {"sharpe", "sortino"}
    rows = [
        [
            portfolio.name if label == "Portfolio" else str(label),
            *(
                f"{metrics.at[label, column]:.2f}"
                if column in ratios
                else pct(metrics.at[label, column])
                for column in METRIC_COLUMNS
            ),
        ]
        for label in metrics.index
    ]
    table(
        ["Activo", *METRIC_COLUMNS.values()], rows, split_before=len(portfolio.assets)
    )


# Step 5: reporting


def save_simulation_chart(simulation: SimulationResult, title: str, path: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    simulation.plot_paths(ax=axes[0])
    simulation.plot_distribution(ax=axes[1])
    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(path)


def save_charts(
    portfolio: Portfolio,
    benchmark: Portfolio | None,
    simulation: SimulationResult,
    asset_simulation: SimulationResult,
    asset: PriceSeries,
) -> list[Path]:
    """Portfolio.plots_report() for the portfolio, plus the single-asset simulation."""
    paths = [OUTPUT / "plots_report.png", OUTPUT / "montecarlo_asset.png"]
    portfolio.plots_report(benchmark=benchmark, simulation=simulation, path=paths[0])
    save_simulation_chart(asset_simulation, f"Monte Carlo: {asset.ticker}", paths[1])
    return paths


def main() -> None:
    print("=" * WIDTH)
    print(" MIAX TOOLKIT  demo interactiva")
    print(" Pulsa Enter para aceptar el valor entre corchetes.")
    print("=" * WIDTH)
    section("Cartera")

    name = ask("Nombre de la cartera", "Cartera demo", parse_name)
    source = ask(
        "Fuente de precios (yfinance/tiingo)", "yfinance", parse_choice(list(PROVIDERS))
    )
    try:
        provider = PROVIDERS[source]()
    except (RuntimeError, ValueError) as error:
        raise SystemExit(f"No se pudo crear el proveedor {source}: {error}") from None
    start = ask("Fecha de inicio (AAAA-MM-DD)", "2019-01-01", parse_date())
    end = ask(
        "Fecha de fin (AAAA-MM-DD)", date.today().isoformat(), parse_date(after=start)
    )

    weights = ask_assets("tu cartera", EXAMPLE_ASSETS)
    section("Indice de referencia")
    with_benchmark = ask(
        "Comparar con un indice de referencia? (s/n)", "s", parse_yes_no
    )
    benchmark_weights = (
        ask_assets("el indice de referencia", EXAMPLE_BENCHMARK)
        if with_benchmark
        else None
    )

    section("Simulacion de Monte Carlo")
    n_sims = ask("Numero de simulaciones", "1000", parse_int(1, 100_000))
    horizon = ask(
        "Horizonte en dias de mercado (252 = 1 ano)", "252", parse_int(1, 252 * 30)
    )
    initial_value = ask("Valor inicial", "10000", parse_float_positive)
    rebalancing = ask(
        "Rebalanceo (diario/mensual/trimestral/ninguno)",
        "mensual",
        parse_choice(list(REBALANCING)),
    )
    seed = ask("Semilla (para repetir resultados)", "42", parse_int(0, 2**32 - 1))
    config = SimulationConfig(
        n_sims=n_sims, horizon_days=horizon, initial_value=initial_value, seed=seed
    )

    try:
        step(1, "Extraccion de datos", "miax_toolkit.extraction")
        risk_free = load_risk_free(start, end)
        section(f"Cartera: {name}")
        assets, asset_weights = download(provider, dict(weights), start, end)
        show_price_series(assets, asset_weights)
        benchmark_assets = None
        if benchmark_weights:
            section("Indice de referencia")
            benchmark_assets, benchmark_weight_list = download(
                provider, dict(benchmark_weights), start, end
            )
            show_price_series(benchmark_assets, benchmark_weight_list)

        step(2, "Limpieza y alineacion de fechas", "miax_toolkit.preprocessing")
        aligned, row = align(name, assets)
        rows = [row]
        if benchmark_assets:
            rows.append(align("Indice de referencia", benchmark_assets)[1])
        print("  Solo se conservan las fechas en las que cotizan todos los activos.\n")
        headers = ["Cartera", "Max. fechas", "Comunes", "Descartadas"]
        table([*headers, "Desde", "Hasta"], rows)

        step(3, "Modelado de la cartera", "miax_toolkit.models")
        portfolio = Portfolio(name, assets, asset_weights, risk_free=risk_free)
        benchmark = (
            Portfolio(
                "Indice de referencia",
                benchmark_assets,
                benchmark_weight_list,
                risk_free=risk_free,
            )
            if benchmark_assets
            else None
        )
        # Portfolio aligns its assets itself; it must match step 2
        if not portfolio.prices.equals(aligned):
            raise ValueError("Portfolio.prices does not match align_prices")
        exposure = ", ".join(
            f"{currency} {pct(share, 0)}"
            for currency, share in portfolio.currency_exposure().items()
        )
        print(f"  Exposicion por divisa      {exposure}")
        print(f"  Numero efectivo de activos {portfolio.effective_n_assets():.2f}")
        print(f"  Tipo sin riesgo medio      {pct(portfolio.risk_free_mean(), 2)}")
        section("Metricas historicas en USD (anualizadas)")
        show_metrics(portfolio, benchmark)

        step(4, "Simulacion de Monte Carlo", "miax_toolkit.simulation")
        simulation = portfolio.monte_carlo(
            config, rebalance_every=REBALANCING[rebalancing]
        )
        # The asset with the largest weight, simulated on its own
        asset = max(zip(assets, asset_weights), key=lambda pair: pair[1])[0]
        asset_simulation = simulate_asset(asset, config)
        print(
            f"  {config.n_sims:,} simulaciones a {config.horizon_days} dias, "
            f"valor inicial {config.initial_value:,.0f}, semilla {config.seed}\n"
        )
        table(
            [
                "Simulacion",
                "Valor final (mediana)",
                "Prob. perdida",
                "VaR 95 %",
                "CVaR 95 %",
            ],
            [
                simulation_row(f"Cartera, rebalanceo {rebalancing}", simulation),
                simulation_row(f"Solo {asset.ticker} (mayor peso)", asset_simulation),
            ],
        )
        print("\n  VaR 95 %: perdida minima en el 5 % de peores escenarios.")
        print("  CVaR 95 %: perdida media en ese 5 %. Ambos sobre el valor inicial.")
    except (ValueError, TypeError) as error:
        raise SystemExit(f"\nNo se pudo construir la cartera: {error}") from None

    step(5, "Informe y graficos", "miax_toolkit.reporting")
    OUTPUT.mkdir(exist_ok=True)
    report_path = OUTPUT / "report.md"
    report = portfolio.report(benchmark=benchmark, simulation=simulation)
    report_path.write_text(report, encoding="utf-8")
    paths = [
        report_path,
        *save_charts(portfolio, benchmark, simulation, asset_simulation, asset),
    ]
    print(f"  Guardado en {OUTPUT}:")
    for path in paths:
        print(f"    {path.name}")

    if ask("\nMostrar los graficos en pantalla? (s/n)", "n", parse_yes_no):
        plt.show()


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        sys.exit("\nDemo cancelada.")
