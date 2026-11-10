"""miax_toolkit: market data extraction, portfolio analysis and Monte Carlo simulation.

The public classes are re-exported here, so user code can write

    from miax_toolkit import Portfolio, SimulationConfig, YFinanceProvider

instead of the full module paths. The full paths keep working.
"""

from miax_toolkit.extraction import (
    FredProvider,
    MacroProvider,
    PriceProvider,
    TiingoProvider,
    YFinanceProvider,
)
from miax_toolkit.models import MacroSeries, PriceSeries
from miax_toolkit.models.portfolio import Portfolio
from miax_toolkit.models.results import SimulationConfig, SimulationResult
from miax_toolkit.reporting.report import ReportSettings

__all__ = [
    "FredProvider",
    "MacroProvider",
    "MacroSeries",
    "Portfolio",
    "PriceProvider",
    "PriceSeries",
    "ReportSettings",
    "SimulationConfig",
    "SimulationResult",
    "TiingoProvider",
    "YFinanceProvider",
]
