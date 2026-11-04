from dataclasses import dataclass

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class SimulationConfig:
    n_sims: int = 1000
    horizon_days: int = 252
    initial_value: float = 100.0
    seed: int | None = None

    def __post_init__(self) -> None:
        if self.n_sims < 1 or self.horizon_days < 1:
            raise ValueError("n_sims and horizon_days must be at least 1")
        if self.initial_value <= 0:
            raise ValueError("initial_value must be positive")


@dataclass
class SimulationResult:
    paths: np.ndarray
    config: SimulationConfig

    def __post_init__(self) -> None:
        expected = (self.config.n_sims, self.config.horizon_days + 1)
        if self.paths.shape != expected:
            raise ValueError(f"paths must have shape {expected}")

    @property
    def final_values(self) -> np.ndarray:
        return self.paths[:, -1]

    def prob_loss(self) -> float:
        """Share of simulations that end below the initial value."""
        return float((self.final_values < self.config.initial_value).mean())

    def value_at_risk(self, level: float = 5) -> float:
        """Loss at the given percentile of final values, as a fraction of the initial value.

        E.g. 0.18 means: in the worst `level` % of simulations you lose at least 18 %.
        """
        return float(
            1 - np.percentile(self.final_values, level) / self.config.initial_value
        )

    def percentiles(self, levels: tuple[int, ...] = (5, 50, 95)) -> pd.DataFrame:
        values = np.percentile(self.paths, levels, axis=0).T
        return pd.DataFrame(values, columns=[f"p{level}" for level in levels])

    def plot_paths(self, n_paths: int = 100, ax: plt.Axes | None = None) -> plt.Axes:
        """Simulated paths with the median and the 5-95 percentile band."""
        if ax is None:
            _, ax = plt.subplots(figsize=(10, 5))
        days = np.arange(self.paths.shape[1])
        table = self.percentiles()

        ax.plot(days, self.paths[:n_paths].T, color="tab:blue", alpha=0.08)
        ax.plot(days, table["p50"], color="black", label="Median")
        ax.plot(days, table["p5"], color="tab:red", ls="--", label="5th percentile")
        ax.plot(days, table["p95"], color="tab:green", ls="--", label="95th percentile")
        ax.set(title="Simulated paths", xlabel="Day", ylabel="Value")
        ax.legend()
        return ax

    def plot_distribution(self, bins: int = 50, ax: plt.Axes | None = None) -> plt.Axes:
        """Histogram of final values, with the initial value as reference."""
        if ax is None:
            _, ax = plt.subplots(figsize=(10, 5))
        ax.hist(self.final_values, bins=bins, color="tab:blue", alpha=0.7)
        ax.axvline(
            self.config.initial_value, color="black", ls="--", label="Initial value"
        )
        ax.set(title="Final value distribution", xlabel="Value", ylabel="Simulations")
        ax.legend()
        return ax

    def plot(self) -> plt.Figure:
        """Show simulated paths and final values side by side."""
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))
        self.plot_paths(ax=axes[0])
        self.plot_distribution(ax=axes[1])
        fig.tight_layout()
        plt.show()
        return fig
