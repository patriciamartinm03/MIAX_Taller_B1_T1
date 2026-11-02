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

        self.values = self.values.sort_index()

        self.mean = float(self.values.mean())
