import math
from datetime import date

import numpy as np
import pandas as pd
import pytest

from miax_toolkit import metrics
from miax_toolkit.models.macro import MacroSeries
from miax_toolkit.models.portfolio import Portfolio
from miax_toolkit.models.results import SimulationConfig
from miax_toolkit.models.series import PriceSeries

DATES = pd.date_range("2026-01-05", periods=5, freq="B")


def make_series(
    ticker: str, currency: str, prices: list[float], fx_to_usd=None, dates=DATES
):
    return PriceSeries(
        ticker=ticker,
        name=ticker,
        asset_type="index",
        currency=currency,
        source="test",
        prices=pd.Series(prices, index=dates),
        price_type="close",
        fx_to_usd=fx_to_usd,
    )


def make_rate(values: list[float], dates, currency="USD", units="percent"):
    return MacroSeries(
        series_id="DTB3",
        name="3-month Treasury bill",
        units=units,
        source="test",
        as_of=date(2026, 1, 31),
        values=pd.Series(values, index=dates),
        currency=currency,
    )


SPX = make_series("SPX", "USD", [100, 101, 102, 103, 104])
RATE_DATES = pd.to_datetime(["2026-01-01", "2026-01-07"])


def test_portfolio_mixes_currencies_in_usd():
    spx = make_series("SPX", "USD", [100, 101, 102, 103, 104])
    fx = pd.Series([1.10, 1.10, 1.20, 1.20, 1.20], index=DATES)
    ibex = make_series("IBEX", "EUR", [100, 100, 100, 100, 100], fx)

    portfolio = Portfolio("Test", [spx, ibex], [0.5, 0.5])

    assert portfolio.prices["SPX"].iloc[0] == pytest.approx(100)
    assert portfolio.prices["IBEX"].iloc[0] == pytest.approx(110)
    assert portfolio.prices["IBEX"].iloc[2] == pytest.approx(120)


def test_fx_move_shows_in_returns():
    fx = pd.Series([1.00, 1.00, 1.10, 1.10, 1.10], index=DATES)
    ibex = make_series("IBEX", "EUR", [100, 100, 100, 100, 100], fx)

    portfolio = Portfolio("Test", [ibex], [1.0])

    assert portfolio.asset_returns()["IBEX"].iloc[1] == pytest.approx(0.10)


def test_nan_weight_fails_as_invalid_weight():
    other = make_series("NDX", "USD", [100, 102, 101, 104, 105])
    with pytest.raises(ValueError, match="weights must be finite numbers"):
        Portfolio("Test", [SPX, other], [float("nan"), 0.5])


def test_few_common_dates_error_shows_each_asset_range():
    late = make_series(
        "LATE",
        "USD",
        [50, 51, 52, 53, 54],
        dates=pd.date_range("2026-01-08", periods=5, freq="B"),
    )
    with pytest.raises(ValueError) as error:
        Portfolio("Test", [SPX, late], [0.5, 0.5])
    message = str(error.value)
    assert "SPX: 2026-01-05 to 2026-01-09" in message
    assert "LATE: 2026-01-08 to 2026-01-14" in message


def test_risk_free_in_eur_fails():
    rate = make_rate([3.0, 3.1], RATE_DATES, currency="EUR")
    with pytest.raises(ValueError, match="risk_free must be in USD"):
        Portfolio("Test", [SPX], [1.0], rate)


def test_risk_free_with_wrong_units_fails():
    rate = make_rate([118.0, 119.0], RATE_DATES, units="index")
    with pytest.raises(ValueError, match="risk_free units must be"):
        Portfolio("Test", [SPX], [1.0], rate)


def test_risk_free_starting_after_prices_fails():
    rate = make_rate([3.0, 3.1], pd.to_datetime(["2026-01-07", "2026-01-08"]))
    with pytest.raises(ValueError, match="after the first date"):
        Portfolio("Test", [SPX], [1.0], rate)


def test_risk_free_daily_has_same_dates_as_asset_returns():
    rate = make_rate([3.0, 3.6], RATE_DATES)
    portfolio = Portfolio("Test", [SPX], [1.0], rate)
    daily = portfolio.risk_free_daily()
    assert daily.index.equals(portfolio.asset_returns().index)
    assert daily.iloc[0] == pytest.approx(0.030 / 252)
    assert daily.iloc[-1] == pytest.approx(0.036 / 252)


def test_risk_free_daily_without_risk_free_is_zero():
    assert Portfolio("Test", [SPX], [1.0]).risk_free_daily() == 0.0


def test_weights_follow_tickers_not_alphabetical_order():
    zzz = make_series("ZZZ", "USD", [100, 110, 121, 133.1, 146.41])
    aaa = make_series("AAA", "USD", [100, 100, 100, 100, 100])
    portfolio = Portfolio("Test", [zzz, aaa], [0.8, 0.2])

    assert portfolio.returns().tolist() == pytest.approx([0.08] * 4)
    final = portfolio.value(rebalance=False).iloc[-1]
    assert final == pytest.approx(100 * (0.8 * 1.4641 + 0.2 * 1.0))


def test_risk_free_mean_weights_each_rate_by_its_days():
    rate = make_rate([3.0, 3.6], RATE_DATES)
    portfolio = Portfolio("Test", [SPX], [1.0], rate)
    # Return dates: Jan 6 at 3 %, Jan 7, 8 and 9 at 3.6 %
    assert portfolio.risk_free_mean() == pytest.approx((0.030 + 3 * 0.036) / 4)


def test_risk_free_mean_without_risk_free_is_zero():
    assert Portfolio("Test", [SPX], [1.0]).risk_free_mean() == 0.0


def test_currency_exposure_adds_weights_by_currency():
    fx = pd.Series([1.10] * 5, index=DATES)
    ibex = make_series("IBEX", "EUR", [100, 101, 99, 102, 103], fx)
    portfolio = Portfolio("Test", [SPX, ibex], [0.6, 0.4])
    exposure = portfolio.currency_exposure()
    assert exposure.index.tolist() == ["USD", "EUR"]
    assert exposure.tolist() == pytest.approx([0.6, 0.4])


def test_value_starts_at_initial_value_with_and_without_rebalancing():
    other = make_series("NDX", "USD", [100, 98, 103, 101, 106])
    portfolio = Portfolio("My portfolio", [SPX, other], [0.5, 0.5])
    for rebalance in (True, False):
        values = portfolio.value(initial_value=250.0, rebalance=rebalance)
        assert values.index[0] == DATES[0]
        assert values.iloc[0] == pytest.approx(250.0)
        assert values.name == "My portfolio"


def test_value_of_one_asset_is_its_normalized_price():
    portfolio = Portfolio("Test", [SPX], [1.0])
    expected = (SPX.prices / SPX.prices.iloc[0] * 100).tolist()
    assert portfolio.value(rebalance=True).tolist() == pytest.approx(expected)
    assert portfolio.value(rebalance=False).tolist() == pytest.approx(expected)


def test_diversification_benefit_is_zero_with_one_asset():
    portfolio = Portfolio("Test", [SPX], [1.0])
    assert portfolio.diversification_benefit() == pytest.approx(0, abs=1e-12)


def test_diversification_benefit_is_positive_with_uncorrelated_assets():
    up_down = make_series("A", "USD", [100, 110, 99, 108.9, 98.01])
    two_up_two_down = make_series("B", "USD", [100, 105, 110.25, 104.7375, 99.500625])
    portfolio = Portfolio("Test", [up_down, two_up_two_down], [0.5, 0.5])
    assert portfolio.correlation().loc["A", "B"] == pytest.approx(0, abs=1e-9)
    assert portfolio.diversification_benefit() > 0


def test_correlation_has_ones_on_the_diagonal():
    other = make_series("NDX", "USD", [100, 98, 103, 101, 106])
    correlation = Portfolio("Test", [SPX, other], [0.5, 0.5]).correlation()
    assert correlation.to_numpy().diagonal().tolist() == pytest.approx([1.0, 1.0])


METRIC_COLUMNS = [
    "annual_return",
    "cagr",
    "annual_volatility",
    "sharpe",
    "sortino",
    "max_drawdown",
]


def test_metrics_table_has_one_row_per_asset_plus_portfolio():
    other = make_series("NDX", "USD", [100, 98, 103, 101, 106])
    portfolio = Portfolio("Test", [SPX, other], [0.5, 0.5])
    table = portfolio.metrics_table()
    assert table.index.name == "asset"
    assert table.index.tolist() == ["SPX", "NDX", "Portfolio"]
    assert table.columns.tolist() == METRIC_COLUMNS

    benchmark = Portfolio("Benchmark", [SPX], [1.0])
    with_benchmark = portfolio.metrics_table(benchmark)
    assert with_benchmark.index.tolist() == ["SPX", "NDX", "Portfolio", "Benchmark"]


def test_benchmark_with_an_extra_day_gives_same_metrics_as_portfolio():
    portfolio_dates = DATES.delete(2)
    asset = make_series("SPX", "USD", [100, 102, 99, 104], dates=portfolio_dates)
    # Same prices plus a dip on a day the portfolio does not have
    benchmark_asset = make_series("SPY", "USD", [100, 102, 90, 99, 104])
    portfolio = Portfolio("Test", [asset], [1.0])
    benchmark = Portfolio("Benchmark", [benchmark_asset], [1.0])

    table = portfolio.metrics_table(benchmark)
    assert table.loc["Benchmark"].tolist() == pytest.approx(
        table.loc["Portfolio"].tolist()
    )


def test_benchmark_that_is_not_a_portfolio_fails():
    portfolio = Portfolio("Test", [SPX], [1.0])
    with pytest.raises(TypeError, match="benchmark must be a Portfolio"):
        portfolio.metrics_table(SPX)


def test_currency_attribution_combines_local_and_fx_returns():
    fx = pd.Series([1.10, 1.12, 1.08, 1.11, 1.09], index=DATES)
    ibex = make_series("IBEX", "EUR", [100, 103, 99, 104, 106], fx)
    row = Portfolio("Test", [SPX, ibex], [0.5, 0.5]).currency_attribution().loc["IBEX"]
    assert row["currency"] == "EUR"
    combined = (1 + row["local_return"]) * (1 + row["fx_return"]) - 1
    assert combined == pytest.approx(row["usd_return"])


def test_currency_attribution_of_rising_asset_with_falling_euro():
    fx = pd.Series([1.00, 1.00, 1.00, 1.00, 0.95], index=DATES)
    ibex = make_series("IBEX", "EUR", [100, 102, 104, 107, 110], fx)
    row = Portfolio("Test", [ibex], [1.0]).currency_attribution().loc["IBEX"]
    assert row["local_return"] == pytest.approx(0.10)
    assert row["fx_return"] == pytest.approx(-0.05)
    assert row["usd_return"] == pytest.approx(0.045)


def test_currency_attribution_of_usd_portfolio_is_empty():
    table = Portfolio("Test", [SPX], [1.0]).currency_attribution()
    assert table.empty
    assert table.index.name == "asset"
    assert table.columns.tolist() == [
        "currency",
        "local_return",
        "fx_return",
        "usd_return",
    ]


OVERLAP_COLUMNS = ["portfolio_weight", "benchmark_weight", "overlap"]


def make_usd_portfolio(name: str, weights: dict[str, float]) -> Portfolio:
    assets = [
        make_series(ticker, "USD", [100, 101 + i, 99, 103 + i, 104])
        for i, ticker in enumerate(weights)
    ]
    return Portfolio(name, assets, list(weights.values()))


def test_benchmark_named_like_a_ticker_fails():
    portfolio = make_usd_portfolio("My portfolio", {"SPY": 0.5, "FEZ": 0.5})
    benchmark = make_usd_portfolio("SPY", {"EWP": 1.0})
    with pytest.raises(
        ValueError, match="'SPY' is also a ticker in portfolio 'My portfolio'"
    ):
        portfolio.metrics_table(benchmark)


def test_benchmark_named_portfolio_fails():
    portfolio = make_usd_portfolio("My portfolio", {"SPY": 1.0})
    benchmark = make_usd_portfolio("Portfolio", {"EWP": 1.0})
    with pytest.raises(ValueError, match="'Portfolio' is reserved"):
        portfolio.metrics_table(benchmark)


def test_benchmark_with_few_common_dates_shows_both_ranges():
    portfolio = Portfolio("My portfolio", [SPX], [1.0])
    late = make_series(
        "SPY",
        "USD",
        [100, 101, 102, 103, 104],
        dates=pd.date_range("2026-01-08", periods=5, freq="B"),
    )
    benchmark = Portfolio("Benchmark 60/40", [late], [1.0])
    with pytest.raises(ValueError) as error:
        portfolio.metrics_table(benchmark)
    message = str(error.value)
    assert "has only 2 dates in common with portfolio 'My portfolio'" in message
    assert "Portfolio: 2026-01-05 to 2026-01-09" in message
    assert "benchmark: 2026-01-08 to 2026-01-14" in message


def test_benchmark_overlap_keeps_only_shared_assets():
    portfolio = make_usd_portfolio("My portfolio", {"SPY": 0.4, "FEZ": 0.6})
    benchmark = make_usd_portfolio("Benchmark", {"SPY": 0.6, "EWP": 0.4})
    overlap = portfolio.benchmark_overlap(benchmark)
    assert overlap.index.name == "asset"
    assert overlap.index.tolist() == ["SPY"]
    assert overlap.columns.tolist() == OVERLAP_COLUMNS
    assert overlap.loc["SPY"].tolist() == pytest.approx([0.4, 0.6, 0.4])
    assert portfolio.benchmark_overlap_share(benchmark) == pytest.approx(0.4)


def test_benchmark_overlap_without_shared_assets_is_empty():
    portfolio = make_usd_portfolio("My portfolio", {"SPY": 1.0})
    benchmark = make_usd_portfolio("Benchmark", {"EWP": 1.0})
    overlap = portfolio.benchmark_overlap(benchmark)
    assert overlap.empty
    assert overlap.columns.tolist() == OVERLAP_COLUMNS
    assert portfolio.benchmark_overlap_share(benchmark) == 0


def test_benchmark_overlap_with_itself_is_one():
    portfolio = make_usd_portfolio("My portfolio", {"SPY": 0.3, "FEZ": 0.7})
    copy = make_usd_portfolio("Copy", {"SPY": 0.3, "FEZ": 0.7})
    assert portfolio.benchmark_overlap_share(copy) == pytest.approx(1.0)


def test_benchmark_that_is_not_a_portfolio_names_the_type():
    portfolio = Portfolio("Test", [SPX], [1.0])
    with pytest.raises(TypeError, match="got PriceSeries"):
        portfolio.benchmark_overlap(SPX)
    with pytest.raises(TypeError, match="got str"):
        portfolio.metrics_table("SPY")


def test_repeated_ticker_error_names_the_ticker():
    other = make_series("SPX", "USD", [100, 102, 101, 104, 105])
    with pytest.raises(ValueError, match="repeated assets: SPX"):
        Portfolio("Test", [SPX, other], [0.5, 0.5])


def test_mixed_price_types_error_lists_each_asset():
    adjusted = PriceSeries(
        ticker="NDX",
        name="NDX",
        asset_type="index",
        currency="USD",
        source="test",
        prices=pd.Series([100, 101, 102, 103, 104], index=DATES),
        price_type="adj_close",
    )
    with pytest.raises(ValueError, match="SPX: close, NDX: adj_close"):
        Portfolio("Test", [SPX, adjusted], [0.5, 0.5])


def test_weights_sum_error_shows_the_sum():
    other = make_series("NDX", "USD", [100, 102, 101, 104, 105])
    with pytest.raises(ValueError, match="they add up to 0.9"):
        Portfolio("Test", [SPX, other], [0.5, 0.4])


def test_negative_weight_error_names_ticker_and_weight():
    other = make_series("NDX", "USD", [100, 102, 101, 104, 105])
    with pytest.raises(ValueError, match="weight of NDX is -0.2"):
        Portfolio("Test", [SPX, other], [1.2, -0.2])


def test_nan_weight_error_names_the_ticker():
    other = make_series("NDX", "USD", [100, 102, 101, 104, 105])
    with pytest.raises(ValueError, match="weight of NDX is nan"):
        Portfolio("Test", [SPX, other], [0.5, float("nan")])


def test_weight_count_error_shows_both_counts():
    with pytest.raises(ValueError, match="got 1 assets and 2 weights"):
        Portfolio("Test", [SPX], [0.5, 0.5])


def test_non_price_series_asset_error_names_position_and_type():
    with pytest.raises(TypeError, match="asset 2 is a str"):
        Portfolio("Test", [SPX, "NDX"], [0.5, 0.5])


def test_risk_free_that_is_not_macro_series_names_the_type():
    with pytest.raises(TypeError, match="got float"):
        Portfolio("Test", [SPX], [1.0], 0.03)


def test_comparison_with_a_copy_of_itself():
    portfolio = make_usd_portfolio("My portfolio", {"SPY": 0.4, "FEZ": 0.6})
    copy = make_usd_portfolio("Copy", {"SPY": 0.4, "FEZ": 0.6})
    comparison = portfolio.benchmark_comparison(copy)
    assert comparison.name == "Copy"
    assert comparison["cagr_difference"] == pytest.approx(0)
    assert comparison["volatility_difference"] == pytest.approx(0)
    assert comparison["sharpe_difference"] == pytest.approx(0)
    assert comparison["tracking_error"] == pytest.approx(0)
    assert math.isnan(comparison["information_ratio"])


def test_copy_missing_a_middle_day_has_no_tracking_error():
    portfolio = Portfolio("My portfolio", [SPX], [1.0])
    missing_day = make_series("SPY", "USD", [100, 101, 103, 104], dates=DATES.delete(2))
    benchmark = Portfolio("Benchmark", [missing_day], [1.0])
    comparison = portfolio.benchmark_comparison(benchmark)
    assert comparison["tracking_error"] == pytest.approx(0)


def test_benchmark_with_other_price_type_is_an_issue():
    adjusted = PriceSeries(
        ticker="SPY",
        name="SPY",
        asset_type="etf",
        currency="USD",
        source="test",
        prices=pd.Series([100, 101, 102, 103, 104], index=DATES),
        price_type="adj_close",
    )
    portfolio = Portfolio("My portfolio", [SPX], [1.0])
    issues = portfolio.benchmark_issues(Portfolio("Benchmark", [adjusted], [1.0]))
    assert issues == [
        (
            "benchmark 'Benchmark' uses price_type 'adj_close' "
            "but portfolio 'My portfolio' uses 'close'"
        )
    ]


def test_benchmark_starting_later_is_an_issue_but_can_be_compared():
    portfolio = Portfolio("My portfolio", [SPX], [1.0])
    late = make_series(
        "SPY",
        "USD",
        [101, 103, 102, 104],
        dates=pd.date_range("2026-01-06", periods=4, freq="B"),
    )
    benchmark = Portfolio("Benchmark", [late], [1.0])
    assert portfolio.benchmark_issues(benchmark) == [
        (
            "benchmark 'Benchmark' starts on 2026-01-06, "
            "after portfolio 'My portfolio' (2026-01-05)"
        )
    ]
    comparison = portfolio.benchmark_comparison(benchmark)
    assert comparison.notna().all()


def test_benchmark_without_common_dates():
    portfolio = Portfolio("My portfolio", [SPX], [1.0])
    later = make_series(
        "SPY",
        "USD",
        [100, 101, 102],
        dates=pd.date_range("2026-02-02", periods=3, freq="B"),
    )
    benchmark = Portfolio("Benchmark", [later], [1.0])
    assert "starts on 2026-02-02" in portfolio.benchmark_issues(benchmark)[0]
    with pytest.raises(ValueError) as error:
        portfolio.benchmark_comparison(benchmark)
    message = str(error.value)
    assert "has only 0 dates in common" in message
    assert "Portfolio: 2026-01-05 to 2026-01-09" in message
    assert "benchmark: 2026-02-02 to 2026-02-04" in message


def test_benchmark_issues_and_comparison_need_a_portfolio():
    portfolio = Portfolio("My portfolio", [SPX], [1.0])
    with pytest.raises(TypeError, match="got PriceSeries"):
        portfolio.benchmark_issues(SPX)
    with pytest.raises(TypeError, match="got PriceSeries"):
        portfolio.benchmark_comparison(SPX)


THREE_ASSETS = {"SPY": 0.4, "FEZ": 0.3, "EWP": 0.3}
DAILY_MU = [0.0004, 0.0003, 0.0002]
DAILY_COV = np.diag([0.0001, 0.0002, 0.0003])


def test_simulation_assumptions_default_to_historical():
    portfolio = make_usd_portfolio("My portfolio", THREE_ASSETS)
    assumptions = portfolio.simulation_assumptions()
    asset_returns = portfolio.asset_returns()
    assert assumptions.index.name == "asset"
    assert assumptions.index.tolist() == asset_returns.columns.tolist()
    for ticker in asset_returns.columns:
        returns = asset_returns[ticker]
        assert assumptions.loc[ticker, "annual_return"] == pytest.approx(
            metrics.annual_return(returns)
        )
        assert assumptions.loc[ticker, "annual_volatility"] == pytest.approx(
            metrics.annual_volatility(returns)
        )


def test_simulation_assumptions_annualize_given_inputs():
    portfolio = make_usd_portfolio("My portfolio", THREE_ASSETS)
    assumptions = portfolio.simulation_assumptions(DAILY_MU, DAILY_COV)
    assert assumptions.index.tolist() == ["SPY", "FEZ", "EWP"]
    assert assumptions["annual_return"].tolist() == pytest.approx(
        [mean * 252 for mean in DAILY_MU]
    )
    assert assumptions["annual_volatility"].tolist() == pytest.approx(
        [(variance * 252) ** 0.5 for variance in np.diag(DAILY_COV)]
    )


def test_monte_carlo_default_equals_historical_inputs_by_hand():
    # Small daily moves, so the historical inputs pass the "looks annual" checks
    assets = [
        make_series("SPY", "USD", [100, 100.5, 100.2, 100.6, 100.9]),
        make_series("FEZ", "USD", [50, 49.8, 50.1, 50.3, 50.2]),
        make_series("EWP", "USD", [30, 30.1, 30.0, 30.2, 30.3]),
    ]
    portfolio = Portfolio("My portfolio", assets, [0.4, 0.3, 0.3])
    asset_returns = portfolio.asset_returns()
    config = SimulationConfig(n_sims=50, horizon_days=10, seed=7)
    default = portfolio.monte_carlo(config)
    by_hand = portfolio.monte_carlo(
        config, asset_returns.mean().to_numpy(), asset_returns.cov().to_numpy()
    )
    np.testing.assert_array_equal(default.paths, by_hand.paths)


def test_mu_with_wrong_length_shows_both_counts():
    portfolio = make_usd_portfolio("My portfolio", THREE_ASSETS)
    with pytest.raises(
        ValueError, match=r"one value per asset \(3: SPY, FEZ, EWP\), got 2"
    ):
        portfolio.simulation_assumptions(mu=[0.0004, 0.0003])


def test_cov_with_wrong_shape_shows_both_shapes():
    portfolio = make_usd_portfolio("My portfolio", THREE_ASSETS)
    with pytest.raises(ValueError, match=r"3 x 3 matrix.*got shape \(2, 2\)"):
        portfolio.simulation_assumptions(cov=np.eye(2) * 0.0001)


def test_annual_mu_looks_annual():
    portfolio = make_usd_portfolio("My portfolio", THREE_ASSETS)
    annual_mu = [0.08, 0.0003, 0.0002]
    with pytest.raises(ValueError, match="mu for SPY is 0.08, which looks annual"):
        portfolio.monte_carlo(mu=annual_mu)
    with pytest.raises(ValueError, match="mu for SPY is 0.08, which looks annual"):
        portfolio.simulation_assumptions(mu=annual_mu)


def test_annual_cov_looks_annual():
    portfolio = make_usd_portfolio("My portfolio", THREE_ASSETS)
    annual_cov = np.diag([0.04, 0.04, 0.04])
    with pytest.raises(ValueError, match="cov diagonal for SPY is 0.04.*looks annual"):
        portfolio.simulation_assumptions(cov=annual_cov)


def test_negative_variance_fails():
    portfolio = make_usd_portfolio("My portfolio", THREE_ASSETS)
    cov = np.diag([0.0001, -0.0002, 0.0003])
    with pytest.raises(ValueError, match="cov diagonal for FEZ is -0.0002"):
        portfolio.simulation_assumptions(cov=cov)


def test_mu_with_nan_names_the_ticker():
    portfolio = make_usd_portfolio("My portfolio", THREE_ASSETS)
    with pytest.raises(
        ValueError, match="mu for FEZ is nan; all values of mu must be finite"
    ):
        portfolio.simulation_assumptions(mu=[0.0004, float("nan"), 0.0002])


def test_cov_with_infinity_names_row_and_column():
    portfolio = make_usd_portfolio("My portfolio", THREE_ASSETS)
    cov = DAILY_COV.copy()
    cov[0, 2] = np.inf
    with pytest.raises(
        ValueError, match="cov for row SPY and column EWP is inf; all values of cov"
    ):
        portfolio.simulation_assumptions(cov=cov)
