import matplotlib.pyplot as plt
import numpy as np
import pytest

from miax_toolkit.models.results import SimulationConfig, SimulationResult

# Four one-day simulations from 100: two losses, two gains.
PATHS = np.array(
    [[100.0, 80.0], [100.0, 90.0], [100.0, 110.0], [100.0, 120.0]],
)
CONFIG = SimulationConfig(n_sims=4, horizon_days=1, initial_value=100.0)


@pytest.fixture
def result() -> SimulationResult:
    return SimulationResult(paths=PATHS, config=CONFIG)


def test_config_defaults():
    config = SimulationConfig()
    assert (config.n_sims, config.horizon_days, config.initial_value) == (
        1000,
        252,
        100.0,
    )
    assert config.seed is None


@pytest.mark.parametrize(
    "kwargs",
    [{"n_sims": 0}, {"horizon_days": 0}, {"initial_value": 0}, {"initial_value": -1}],
)
def test_config_rejects_invalid_values(kwargs):
    with pytest.raises(ValueError):
        SimulationConfig(**kwargs)


def test_config_is_immutable():
    with pytest.raises(AttributeError):
        CONFIG.n_sims = 10


def test_result_rejects_paths_with_wrong_shape():
    with pytest.raises(ValueError, match="shape"):
        SimulationResult(paths=PATHS[:, :1], config=CONFIG)


def test_final_values_are_last_column(result):
    np.testing.assert_array_equal(result.final_values, [80.0, 90.0, 110.0, 120.0])


def test_prob_loss_is_share_ending_below_initial_value(result):
    assert result.prob_loss() == 0.5


@pytest.mark.parametrize(("level", "expected"), [(0, 0.2), (50, 0.0), (100, -0.2)])
def test_value_at_risk_is_loss_at_percentile(result, level, expected):
    assert result.value_at_risk(level) == pytest.approx(expected)


def test_percentiles_table_has_one_row_per_day(result):
    table = result.percentiles()
    assert list(table.columns) == ["p5", "p50", "p95"]
    assert len(table) == 2
    assert list(table.iloc[0]) == [100.0, 100.0, 100.0]
    assert table.loc[1, "p50"] == pytest.approx(100.0)


def test_percentiles_accepts_custom_levels(result):
    assert list(result.percentiles((10, 90)).columns) == ["p10", "p90"]


def test_plot_paths_draws_paths_and_three_reference_lines(result):
    ax = result.plot_paths(n_paths=2)
    assert len(ax.lines) == 2 + 3
    assert ax.get_title() == "Simulated paths"


def test_plot_distribution_marks_initial_value(result):
    ax = result.plot_distribution(bins=4)
    assert ax.lines[0].get_xdata()[0] == 100.0


def test_plot_draws_into_given_axes(result):
    _, ax = plt.subplots()
    assert result.plot_paths(ax=ax) is ax
    assert result.plot_distribution(ax=ax) is ax


def test_plot_returns_figure_with_two_axes(result, monkeypatch):
    monkeypatch.setattr(plt, "show", lambda: None)
    fig = result.plot()
    assert len(fig.axes) == 2
