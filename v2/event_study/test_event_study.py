"""Tests for the event study engine."""

from __future__ import annotations

import os

import numpy as np
import pytest

from v2.event_study.models import EventCAR, EventStudyResult, MarketModelFit
from v2.event_study.stats import (
    bootstrap_ci,
    compute_abnormal_returns,
    fit_market_model,
    sum_car,
    ttest_cars,
)


# ---------------------------------------------------------------------------
# Unit tests — stats.py
# ---------------------------------------------------------------------------


class TestFitMarketModel:
    def test_known_alpha_beta(self):
        rng = np.random.default_rng(42)
        n = 240
        market = rng.normal(0.0005, 0.01, n)
        noise = rng.normal(0, 0.005, n)
        stock = 0.001 + 1.2 * market + noise

        fit = fit_market_model(stock, market)
        assert abs(fit.alpha - 0.001) < 0.002
        assert abs(fit.beta - 1.2) < 0.15
        assert fit.r_squared > 0.3
        assert fit.n_obs == n

    def test_identical_returns(self):
        returns = np.array([0.01, -0.005, 0.003, 0.002, -0.001] * 50)
        fit = fit_market_model(returns, returns)
        assert abs(fit.beta - 1.0) < 0.01
        assert abs(fit.alpha) < 0.001

    def test_zero_variance_market(self):
        market = np.zeros(100)
        stock = np.random.default_rng(0).normal(0, 0.01, 100)
        fit = fit_market_model(stock, market)
        assert fit.n_obs == 100


class TestComputeAbnormalReturns:
    def test_exact(self):
        stock = np.array([0.03, -0.01, 0.02])
        market = np.array([0.02, 0.00, 0.01])
        alpha, beta = 0.001, 1.2
        ar = compute_abnormal_returns(stock, market, alpha, beta)
        expected = stock - (alpha + beta * market)
        np.testing.assert_allclose(ar, expected)


class TestSumCar:
    def test_window(self):
        daily_ar = np.array([0.01, 0.005, -0.002, 0.003, 0.001, 0.002])
        assert abs(sum_car(daily_ar, 0, 1) - 0.015) < 1e-10
        assert abs(sum_car(daily_ar, 0, 5) - 0.019) < 1e-10

    def test_single_day(self):
        daily_ar = np.array([0.05, -0.01])
        assert abs(sum_car(daily_ar, 0, 0) - 0.05) < 1e-10


class TestTtestCars:
    def test_positive_mean(self):
        cars = np.array([0.02, 0.03, 0.01, 0.04, 0.02, 0.01, 0.03, 0.02])
        t, p = ttest_cars(cars)
        assert t > 0
        assert p < 0.05

    def test_too_few(self):
        t, p = ttest_cars(np.array([0.01]))
        assert t == 0.0
        assert p == 1.0


class TestBootstrapCI:
    def test_brackets_mean(self):
        rng = np.random.default_rng(99)
        cars = rng.normal(0.02, 0.01, 50)
        ci = bootstrap_ci(cars, n_bootstrap=5000, rng_seed=42)
        assert ci.lower < cars.mean() < ci.upper
        assert ci.confidence == 0.95

    def test_deterministic_with_seed(self):
        cars = np.array([0.01, 0.02, 0.03, 0.04])
        ci1 = bootstrap_ci(cars, rng_seed=123)
        ci2 = bootstrap_ci(cars, rng_seed=123)
        assert ci1.lower == ci2.lower
        assert ci1.upper == ci2.upper


# ---------------------------------------------------------------------------
# Unit tests — engine helpers
# ---------------------------------------------------------------------------


class TestRetrospectiveFilter:
    def test_filters_stale_records(self):
        from v2.data.models import EarningsRecord
        from v2.event_study.engine import _filter_retrospective

        good = EarningsRecord(
            ticker="GS", report_period="2026-03-31", source_type="8-K",
            filing_date="2026-04-13",
        )
        stale = EarningsRecord(
            ticker="GS", report_period="2025-12-31", source_type="8-K",
            filing_date="2026-04-13",
        )
        result = _filter_retrospective([good, stale])
        assert len(result) == 1
        assert result[0].report_period == "2026-03-31"


# ---------------------------------------------------------------------------
# Unit tests — plot (smoke test, no visual assertion)
# ---------------------------------------------------------------------------


class TestPlots:
    @pytest.fixture()
    def synthetic_result(self):
        events = []
        for i in range(10):
            events.append(EventCAR(
                ticker="TEST",
                event_date=f"2025-01-{10 + i:02d}",
                source_type="8-K" if i < 6 else "10-Q",
                report_period=f"2024-12-{10 + i:02d}",
                market_model=MarketModelFit(alpha=0.001, beta=1.1, r_squared=0.5, n_obs=240),
                daily_ar=[0.005 * ((-1) ** j) for j in range(21)],
                car_0_1=0.01 + i * 0.001,
                car_0_5=0.02 + i * 0.002,
                car_0_20=0.03 + i * 0.003,
            ))
        return EventStudyResult(events=events, aggregates=[], skipped_tickers=[])

    def test_plot_car_by_source(self, synthetic_result):
        from v2.event_study.plot import plot_car_by_source
        from v2.event_study.engine import _aggregate

        synthetic_result.aggregates = _aggregate(synthetic_result.events, 1000, 42)
        fig = plot_car_by_source(synthetic_result)
        assert fig is not None
        plt_mod = __import__("matplotlib.pyplot", fromlist=["close"])
        plt_mod.close(fig)

    def test_plot_car_distribution(self, synthetic_result):
        from v2.event_study.plot import plot_car_distribution

        fig = plot_car_distribution(synthetic_result, "[0,+1]")
        assert fig is not None
        plt_mod = __import__("matplotlib.pyplot", fromlist=["close"])
        plt_mod.close(fig)

    def test_plot_cumulative_ar(self, synthetic_result):
        from v2.event_study.plot import plot_cumulative_ar

        fig = plot_cumulative_ar(synthetic_result)
        assert fig is not None
        plt_mod = __import__("matplotlib.pyplot", fromlist=["close"])
        plt_mod.close(fig)


# ---------------------------------------------------------------------------
# Integration tests — require API key
# ---------------------------------------------------------------------------

pytestmark_live = pytest.mark.skipif(
    not os.environ.get("FINANCIAL_DATASETS_API_KEY"),
    reason="live tests require FINANCIAL_DATASETS_API_KEY",
)


@pytest.fixture(scope="module")
def fd():
    from v2.data import FDClient
    with FDClient() as client:
        yield client


@pytestmark_live
def test_compute_car_live(fd):
    from v2.event_study import compute_car

    result = compute_car(["AAPL"], fd, earnings_limit=4, rng_seed=42)
    assert len(result.events) > 0, "Expected at least one event for AAPL"
    for e in result.events:
        assert e.ticker == "AAPL"
        assert e.source_type in {"8-K", "10-Q", "10-K", "20-F"}
        if e.car_0_1 is not None:
            assert np.isfinite(e.car_0_1)


@pytestmark_live
def test_compute_car_multi_ticker(fd):
    from v2.event_study import compute_car

    result = compute_car(["AAPL", "MSFT", "NVDA"], fd, earnings_limit=4, rng_seed=42)
    tickers_seen = {e.ticker for e in result.events}
    assert len(tickers_seen) >= 2, f"Expected multiple tickers, got {tickers_seen}"
    source_types_seen = {e.source_type for e in result.events}
    assert len(source_types_seen) >= 1
