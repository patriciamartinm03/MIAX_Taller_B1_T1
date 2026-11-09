"""Historical charts for the portfolio report.

Functions here receive pandas tables, not a Portfolio, so they can be tested
on their own. Each one draws on `ax` if given, or on a new figure, and returns it.
"""

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from matplotlib.ticker import PercentFormatter


def _check_values(values: pd.DataFrame) -> None:
    if not isinstance(values, pd.DataFrame):
        raise TypeError("values must be a pandas DataFrame (one column per series)")
    if values.empty:
        raise ValueError("values is empty")
    if not isinstance(values.index, pd.DatetimeIndex):
        raise TypeError("values must have dates as its index")
    if values.isna().any().any():
        raise ValueError("values has empty values (NaN); align the series first")
    if (values <= 0).any().any():
        raise ValueError("values must be positive")


def _format_dates(ax: plt.Axes) -> None:
    locator = mdates.AutoDateLocator()
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))


def plot_growth(
    values: pd.DataFrame, highlight: str | None = None, ax: plt.Axes | None = None
) -> plt.Axes:
    """Growth of each series, rebased to 100 on the first date."""
    _check_values(values)
    if ax is None:
        _, ax = plt.subplots(figsize=(10, 5))

    rebased = values / values.iloc[0] * 100
    others = rebased.drop(columns=[highlight], errors="ignore")
    if not others.empty:
        ax.plot(
            others.index, others.to_numpy(), lw=1, alpha=0.8, label=list(others.columns)
        )
    if highlight in rebased.columns:
        ax.plot(
            rebased.index, rebased[highlight], color="black", lw=2.5, label=highlight
        )

    ax.axhline(100, color="grey", ls="--", lw=0.8)
    _format_dates(ax)
    ax.set(title="Growth (base 100)", xlabel="Date", ylabel="Value")
    ax.legend()
    return ax


def plot_drawdown(values: pd.DataFrame, ax: plt.Axes | None = None) -> plt.Axes:
    """Fall from the previous peak of each series, over time."""
    _check_values(values)
    if ax is None:
        _, ax = plt.subplots(figsize=(10, 5))

    drawdown = values / values.cummax() - 1
    for column in drawdown.columns:
        (line,) = ax.plot(drawdown.index, drawdown[column], lw=1.2, label=column)
        ax.fill_between(
            drawdown.index, drawdown[column], 0, color=line.get_color(), alpha=0.15
        )

    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    _format_dates(ax)
    ax.set(title="Drawdown", xlabel="Date", ylabel="Fall from peak")
    ax.legend()
    return ax


def plot_correlation(corr: pd.DataFrame, ax: plt.Axes | None = None) -> plt.Axes:
    """Heatmap of a correlation matrix, with each value written in its cell."""
    if not isinstance(corr, pd.DataFrame):
        raise TypeError("corr must be a pandas DataFrame")
    if corr.shape[0] != corr.shape[1] or list(corr.index) != list(corr.columns):
        raise ValueError(
            "corr must be square, with the same labels in rows and columns"
        )
    if ax is None:
        _, ax = plt.subplots(figsize=(6, 5))

    image = ax.imshow(corr.to_numpy(), cmap="RdBu_r", vmin=-1, vmax=1)
    labels = list(corr.columns)
    ax.set_xticks(range(len(labels)), labels, rotation=45, ha="right")
    ax.set_yticks(range(len(labels)), labels)

    values = corr.to_numpy()
    texts = np.where(np.isnan(values), "n/a", np.char.mod("%.2f", values))
    colors = np.where(np.abs(values) > 0.6, "white", "black")
    for (i, j), text in np.ndenumerate(texts):
        ax.text(j, i, text, ha="center", va="center", color=colors[i, j])

    ax.figure.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    ax.set_title("Correlation")
    return ax
