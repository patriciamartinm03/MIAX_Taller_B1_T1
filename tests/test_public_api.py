"""The package root re-exports the public classes under their original identity."""

import miax_toolkit
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

PUBLIC = {
    "FredProvider": FredProvider,
    "MacroProvider": MacroProvider,
    "MacroSeries": MacroSeries,
    "Portfolio": Portfolio,
    "PriceProvider": PriceProvider,
    "PriceSeries": PriceSeries,
    "ReportSettings": ReportSettings,
    "SimulationConfig": SimulationConfig,
    "SimulationResult": SimulationResult,
    "TiingoProvider": TiingoProvider,
    "YFinanceProvider": YFinanceProvider,
}


def test_all_lists_exactly_the_public_classes():
    assert sorted(miax_toolkit.__all__) == sorted(PUBLIC)


def test_root_names_are_the_same_objects_as_the_full_paths():
    # Same object, so isinstance checks work whichever import path was used
    for name, cls in PUBLIC.items():
        assert getattr(miax_toolkit, name) is cls
