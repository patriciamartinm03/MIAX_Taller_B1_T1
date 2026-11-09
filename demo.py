"""Interactive demo of miax_toolkit: build a portfolio step by step and analyse it.

Run from the project root:
    uv run --env-file .env python demo.py

Every question has a default value in [brackets]: press Enter to accept it.
Pressing Enter on every question runs the example portfolio.
FRED_API_KEY in .env is optional: without it the risk-free rate is 0.
TIINGO_API_KEY is only needed if you choose Tiingo as the price source.
Output goes to output/ (report.md and PNG charts).
"""

import sys
from collections.abc import Callable
from datetime import date
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from miax_toolkit.extraction import (
    FredProvider,
    PriceProvider,
    TiingoProvider,
    YFinanceProvider,
)
from miax_toolkit.models.portfolio import Portfolio
from miax_toolkit.models.results import SimulationConfig
from miax_toolkit.reporting.plots import plot_correlation, plot_drawdown, plot_growth

OUTPUT = Path("output")

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


def parse_date(text: str) -> date:
    return date.fromisoformat(text)  # raises ValueError if not YYYY-MM-DD


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


# Portfolio questions


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
            f"  Los pesos suman {100 - remaining:g} %, deben sumar 100 %. Vuelve a introducirlos."
        )


def download(
    provider: PriceProvider, weights: dict[str, float], start: date, end: date
):
    """Download every ticker; for the ones that fail, ask for a replacement."""
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


def build_portfolio(name, provider, weights, start, end, risk_free) -> Portfolio:
    print(f"\nDescargando {', '.join(weights)}...")
    assets, weight_list = download(provider, dict(weights), start, end)
    for asset in assets:
        print(
            f"  {asset.ticker:<8} {asset.name[:35]:<35} {asset.asset_type:<7} "
            f"{asset.currency}  media diaria {asset.mean_return:+.4%}  "
            f"desv. tipica {asset.std_return:.4%}"
        )
    return Portfolio(name=name, assets=assets, weights=weight_list, risk_free=risk_free)


def load_risk_free(start: date, end: date):
    try:
        return FredProvider().get_series("DTB3", start, end, currency="USD")
    except ValueError as error:
        first_line = str(error).splitlines()[0]
        print(f"Sin tipo sin riesgo de FRED ({first_line}). Se usa 0.")
        return None


# Output


def save_charts(portfolio: Portfolio, benchmark: Portfolio | None, simulation) -> None:
    series = [portfolio.value()] + ([benchmark.value()] if benchmark else [])
    values = pd.concat(series, axis=1).dropna()
    plot_growth(values, highlight=portfolio.name).figure.savefig(OUTPUT / "growth.png")
    plot_drawdown(values).figure.savefig(OUTPUT / "drawdown.png")
    if len(portfolio.assets) > 1:
        plot_correlation(portfolio.correlation()).figure.savefig(
            OUTPUT / "correlation.png"
        )
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    simulation.plot_paths(ax=axes[0])
    simulation.plot_distribution(ax=axes[1])
    fig.tight_layout()
    fig.savefig(OUTPUT / "montecarlo.png")


def main() -> None:
    print("=== miax_toolkit: demo interactiva ===")
    print("Pulsa Enter para aceptar el valor entre corchetes.\n")

    name = ask("Nombre de la cartera", "Cartera demo", str)
    source = ask(
        "Fuente de precios (yfinance/tiingo)", "yfinance", parse_choice(list(PROVIDERS))
    )
    try:
        provider = PROVIDERS[source]()
    except (RuntimeError, ValueError) as error:
        raise SystemExit(f"No se pudo crear el proveedor {source}: {error}") from None
    start = ask("Fecha de inicio (AAAA-MM-DD)", "2019-01-01", parse_date)
    end = ask("Fecha de fin (AAAA-MM-DD)", date.today().isoformat(), parse_date)

    weights = ask_assets("tu cartera", EXAMPLE_ASSETS)
    with_benchmark = ask(
        "Comparar con un indice de referencia? (s/n)", "s", parse_yes_no
    )
    benchmark_weights = (
        ask_assets("el indice de referencia", EXAMPLE_BENCHMARK)
        if with_benchmark
        else None
    )

    print("\n--- Simulacion de Monte Carlo ---")
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

    try:
        risk_free = load_risk_free(start, end)
        portfolio = build_portfolio(name, provider, weights, start, end, risk_free)
        benchmark = (
            build_portfolio(
                "Indice de referencia",
                provider,
                benchmark_weights,
                start,
                end,
                risk_free,
            )
            if benchmark_weights
            else None
        )
        simulation = portfolio.monte_carlo(
            SimulationConfig(
                n_sims=n_sims,
                horizon_days=horizon,
                initial_value=initial_value,
                seed=seed,
            ),
            rebalance_every=REBALANCING[rebalancing],
        )
    except (ValueError, TypeError) as error:
        raise SystemExit(f"\nNo se pudo construir la cartera: {error}") from None

    print("\n--- Metricas historicas (USD) ---")
    print(portfolio.metrics_table(benchmark).round(4).to_string())
    print("\n--- Monte Carlo ---")
    print(f"Probabilidad de perdida: {simulation.prob_loss():.1%}")
    print(f"VaR 95 %:  {simulation.value_at_risk():.1%}")
    print(f"CVaR 95 %: {simulation.expected_shortfall():.1%}")

    OUTPUT.mkdir(exist_ok=True)
    report = portfolio.report(benchmark=benchmark, simulation=simulation)
    (OUTPUT / "report.md").write_text(report, encoding="utf-8")
    save_charts(portfolio, benchmark, simulation)
    print(f"\nInforme y graficos guardados en {OUTPUT.resolve()}")

    if ask("Mostrar los graficos en pantalla? (s/n)", "n", parse_yes_no):
        plt.show()


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        sys.exit("\nDemo cancelada.")
