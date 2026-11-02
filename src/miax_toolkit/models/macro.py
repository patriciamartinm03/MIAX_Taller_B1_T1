from dataclasses import dataclass, field
from datetime import date

import pandas as pd


@dataclass
class MacroSeries:
    series_id: str
    name: str
    units: str
    source: str
    as_of: date
    values: pd.Series = field(repr=False)
    currency: str | None

    mean: float = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.values, pd.Series):
            raise TypeError("values must be a pandas Series")
        if not isinstance(self.values.index, pd.DatetimeIndex):
            raise TypeError("values must have dates as its index")
        if not pd.api.types.is_numeric_dtype(self.values):
            raise TypeError("values must be numeric")
        if len(self.values) < 1:
            raise ValueError("Need at least one value")
        if self.values.isna().any():
            raise ValueError("There are empty values (NaN)")
        if self.values.index.has_duplicates:
            raise ValueError("There are repeated dates")

        # Allowed units:
        #   "percent" -> rate as a percentage: 3.75 means 3.75 %
        #   "decimal" -> rate as a decimal:    0.0375 means 3.75 %
        #   "index"   -> index with a base:    CPI (2015 = 100) -> 118.2
        #   "level"   -> absolute amount:      GDP in billions -> 1500
        self.units = self.units.lower()
        if self.units not in ("percent", "decimal", "index", "level"):
            raise ValueError(
                f"units must be 'percent', 'decimal', 'index' or 'level', not '{self.units}'"
            )
        if self.units == "decimal" and (self.values.abs() > 0.5).any():
            raise ValueError(
                "units='decimal' but there are values above 0.5; "
                "a rate above 50 % is unrealistic, so these look like percentages (use units='percent')"
            )

        self.values = self.values.sort_index()

        self.mean = float(self.values.mean())

    def as_decimal(self) -> pd.Series:
        """Values as decimals (3.75 % -> 0.0375). Only for percent or decimal units."""
        if self.units == "percent":
            return self.values / 100
        if self.units == "decimal":
            return self.values
        raise ValueError(f"Cannot convert units '{self.units}' to decimal")
