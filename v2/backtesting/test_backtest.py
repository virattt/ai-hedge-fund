"""Tests for the backtesting engine (alpha-model harness)."""

from __future__ import annotations

import os
from datetime import date, timedelta

import pytest

from v2.backtesting import BacktestEngine
from v2.data.models import Price
from v2.models import Signal
from v2.signals.base import AlphaModel


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------

class FixedAlpha(AlphaModel):
    """Alpha model that fires a fixed conviction on chosen dates.

    fire_dates=None  -> fire every day
    fire_dates=set() -> never fire (all neutral)
    """

    def __init__(self, value: float = 1.0, fire_dates=None):
        self._value = value
        self._fire_dates = fire_dates

    @property
    def name(self) -> str:
        return "fixed"

    def predict(self, ticker, date, data_client) -> Signal:
        fires = self._fire_dates is None or date in self._fire_dates
        return Signal(
            model_name="fixed", ticker=ticker, date=date,
            value=self._value if fires else 0.0,
        )


class MockFDClient:
    def __init__(self, prices=None):
        self._prices = prices or []

    def get_prices(self, ticker, start_date, end_date, **kwargs):
        return self._prices


def _make_prices(start_price: float, days: int, daily_change: float = 0.01) -> list[Price]:
    """Generate `days` business-day-spaced prices starting Monday 2025-08-04."""
    prices = []
    price = start_price
    d = date(2025, 8, 4)  # a Monday
    for _ in range(days):
        while d.weekday() >= 5:  # skip weekends
            d += timedelta(days=1)
        prices.append(Price(
            open=price, close=price, high=price + 1, low=price - 1,
            volume=1_000_000, time=d.isoformat(),
        ))
        price = round(price * (1 + daily_change), 2)
        d += timedelta(days=1)
    return prices


# ---------------------------------------------------------------------------
# run_alpha — fills, sizing, P&L
# ---------------------------------------------------------------------------

class TestRunAlpha:
    def test_long_trade_profits_when_price_rises(self):
        prices = _make_prices(100.0, 20, daily_change=0.01)
        fd = MockFDClient(prices)
        fire = prices[0].time[:10]

        result = BacktestEngine(per_trade=10_000).run_alpha(
            FixedAlpha(1.0, {fire}), ["TEST"], fd,
            prices[0].time[:10], prices[10].time[:10], holding_days=5,
        )
        assert len(result.trades) == 1
        t = result.trades[0]
        assert t.direction == "long"
        assert t.entry_price == 100.0
        assert t.pnl > 0
        assert t.holding_days == 5

    def test_short_trade_loses_when_price_rises(self):
        prices = _make_prices(100.0, 20, daily_change=0.01)
        fd = MockFDClient(prices)
        fire = prices[0].time[:10]

        result = BacktestEngine().run_alpha(
            FixedAlpha(-1.0, {fire}), ["TEST"], fd,
            prices[0].time[:10], prices[10].time[:10], holding_days=5,
        )
        assert len(result.trades) == 1
        assert result.trades[0].direction == "short"
        assert result.trades[0].pnl < 0

    def test_position_sizing(self):
        prices = _make_prices(50.0, 20)
        fd = MockFDClient(prices)
        fire = prices[0].time[:10]

        result = BacktestEngine(per_trade=10_000).run_alpha(
            FixedAlpha(1.0, {fire}), ["TEST"], fd,
            prices[0].time[:10], prices[10].time[:10], holding_days=5,
        )
        assert result.trades[0].shares == 200.0  # 10_000 / 50

    def test_equity_curve_starts_at_capital(self):
        prices = _make_prices(100.0, 20, daily_change=0.01)
        fd = MockFDClient(prices)
        fire = prices[0].time[:10]

        result = BacktestEngine(capital=50_000).run_alpha(
            FixedAlpha(1.0, {fire}), ["TEST"], fd,
            prices[0].time[:10], prices[10].time[:10], holding_days=5,
        )
        assert result.equity_curve[0] == 50_000
        assert result.equity_curve[-1] == 50_000 + result.trades[0].pnl

    def test_no_signal_no_trades(self):
        prices = _make_prices(100.0, 20)
        fd = MockFDClient(prices)
        result = BacktestEngine().run_alpha(
            FixedAlpha(0.0), ["TEST"], fd,
            prices[0].time[:10], prices[10].time[:10],
        )
        assert result.trades == []
        assert result.metrics is None

    def test_no_prices_skips_ticker(self):
        fd = MockFDClient([])
        result = BacktestEngine().run_alpha(
            FixedAlpha(1.0), ["FAKE"], fd, "2025-08-04", "2025-08-15",
        )
        assert result.trades == []

    def test_non_overlapping_positions(self):
        # Fire on two well-separated dates → two non-overlapping trades
        prices = _make_prices(100.0, 30, daily_change=0.005)
        fd = MockFDClient(prices)
        fire1, fire2 = prices[0].time[:10], prices[12].time[:10]

        result = BacktestEngine().run_alpha(
            FixedAlpha(1.0, {fire1, fire2}), ["TEST"], fd,
            prices[0].time[:10], prices[20].time[:10], holding_days=5,
        )
        assert len(result.trades) == 2
        # Second entry must be on/after the first exit (no overlap)
        assert result.trades[1].entry_date >= result.trades[0].exit_date

    def test_always_firing_yields_single_trade(self):
        # Edge-triggered: a signal that never returns to flat opens once
        prices = _make_prices(100.0, 20)
        fd = MockFDClient(prices)
        result = BacktestEngine().run_alpha(
            FixedAlpha(1.0, None), ["TEST"], fd,
            prices[0].time[:10], prices[10].time[:10], holding_days=5,
        )
        assert len(result.trades) == 1


class TestMetrics:
    def test_win_rate_and_counts(self):
        up = _make_prices(100.0, 20, daily_change=0.01)
        down = _make_prices(100.0, 20, daily_change=-0.01)
        fire = up[0].time[:10]

        class PerTickerMock:
            def get_prices(self, ticker, start_date, end_date, **kw):
                return up if ticker == "UP" else down

        result = BacktestEngine().run_alpha(
            FixedAlpha(1.0, {fire}), ["UP", "DOWN"], PerTickerMock(),
            up[0].time[:10], up[10].time[:10], holding_days=5,
        )
        assert result.metrics.n_trades == 2
        assert result.metrics.n_long == 2
        assert result.metrics.win_rate == 0.5


# ---------------------------------------------------------------------------
# Integration — requires API key
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
def test_pead_alpha_live(fd):
    from v2.signals import PEADModel
    import math

    result = BacktestEngine().run_alpha(
        PEADModel(), ["AAPL"], fd, "2024-06-01", date.today().isoformat(),
        holding_days=5,
    )
    assert len(result.trades) > 0
    assert result.metrics is not None
    assert math.isfinite(result.metrics.sharpe_ratio)
    assert math.isfinite(result.metrics.total_return_pct)
