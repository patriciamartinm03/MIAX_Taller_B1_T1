import pandas as pd


def align_prices(prices: dict[str, pd.Series]) -> pd.DataFrame:
    """Join price series, keeping only the dates shared by all of them."""
    aligned = pd.concat(prices, axis=1, join="inner").sort_index()
    if aligned.empty:
        raise ValueError("The series have no dates in common")
    return aligned
