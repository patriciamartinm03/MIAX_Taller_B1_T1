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

    def percentiles(self, levels: tuple[int, ...] = (5, 50, 95)) -> pd.DataFrame:
        values = np.percentile(self.paths, levels, axis=0).T
        return pd.DataFrame(values, columns=[f"p{level}" for level in levels])

    def plot_paths(self, n_paths: int = 100) -> None:
        days = np.arange(self.paths.shape[1])
        table = self.percentiles()

        _, ax = plt.subplots(figsize=(10, 5))
        ax.plot(days, self.paths[:n_paths].T, color="tab:blue", alpha=0.08)
        ax.plot(days, table["p50"], color="black", label="Mediana")
        ax.plot(days, table["p5"], color="tab:red", ls="--", label="Percentil 5")
        ax.plot(days, table["p95"], color="tab:green", ls="--", label="Percentil 95")
        ax.set(title="Trayectorias simuladas", xlabel="Día", ylabel="Valor")
        ax.legend()
        plt.show()

    def plot_distribution(self, bins: int = 50) -> None:
        _, ax = plt.subplots(figsize=(10, 5))
        ax.hist(self.final_values, bins=bins, color="tab:blue", alpha=0.7)
        ax.axvline(self.config.initial_value, color="black", ls="--", label="Inicial")
        ax.set(
            title="Distribución del valor final", xlabel="Valor", ylabel="Simulaciones"
        )
        ax.legend()
        plt.show()
