"""Tests for the backtesting engine."""

from __future__ import annotations

import os

import pytest

from v2.backtesting.models import TradeSignal
from v2.backtesting.engine import BacktestEngine
from v2.backtesting.strategy import PEADStrategy
from v2.data.models import EarningsData, EarningsRecord, Price


# ---------------------------------------------------------------------------
# Mock FDClient
# ---------------------------------------------------------------------------

class MockFDClient:
    """Returns canned data for testing without API calls."""

    def __init__(self, earnings=None, prices=None):
        self._earnings = earnings or []
        self._prices = prices or []

    def get_earnings_history(self, ticker, limit=12):
        return self._earnings

    def get_prices(self, ticker, start_date, end_date, **kwargs):
        return self._prices


def _make_prices(start_price: float, days: int, daily_change: float = 0.01) -> list[Price]:
    """Generate a series of daily prices with steady drift."""
    prices = []
    price = start_price
    # Start from a Monday
    from datetime import date, timedelta
    d = date(2025, 8, 4)  # a Monday
    for i in range(days):
        # Skip weekends
        while d.weekday() >= 5:
            d += timedelta(days=1)
        prices.append(Price(
            open=price, close=price, high=price + 1, low=price - 1,
            volume=1000000, time=d.isoformat(),
        ))
        price = round(price * (1 + daily_change), 2)
        d += timedelta(days=1)
    return prices


# ---------------------------------------------------------------------------
# Unit tests — TradeSignal model
# ---------------------------------------------------------------------------

class TestTradeSignal:
    def test_required_fields(self):
        signal = TradeSignal(
            ticker="AAPL", direction="long",
            entry_date="2025-08-01", holding_days=5,
        )
        assert signal.ticker == "AAPL"
        assert signal.metadata == {}

    def test_metadata(self):
        signal = TradeSignal(
            ticker="AAPL", direction="short",
            entry_date="2025-08-01", holding_days=5,
            metadata={"eps_surprise": "MISS", "source_type": "8-K"},
        )
        assert signal.metadata["eps_surprise"] == "MISS"


# ---------------------------------------------------------------------------
# Unit tests — PEADStrategy
# ---------------------------------------------------------------------------

class TestPEADStrategy:
    def test_beat_produces_long(self):
        record = EarningsRecord(
            ticker="AAPL", report_period="2025-06-28",
            source_type="8-K", filing_date="2025-08-01",
            quarterly=EarningsData(eps_surprise="BEAT"),
        )
        fd = MockFDClient(earnings=[record])
        strategy = PEADStrategy(holding_days=5)
        signals = strategy.generate_signals(["AAPL"], fd)
        assert len(signals) == 1
        assert signals[0].direction == "long"
        assert signals[0].metadata["eps_surprise"] == "BEAT"

    def test_miss_produces_short(self):
        record = EarningsRecord(
            ticker="TSLA", report_period="2025-09-30",
            source_type="10-Q", filing_date="2025-10-23",
            quarterly=EarningsData(eps_surprise="MISS"),
        )
        fd = MockFDClient(earnings=[record])
        strategy = PEADStrategy()
        signals = strategy.generate_signals(["TSLA"], fd)
        assert len(signals) == 1
        assert signals[0].direction == "short"

    def test_meet_is_skipped(self):
        record = EarningsRecord(
            ticker="AAPL", report_period="2025-06-28",
            source_type="8-K", filing_date="2025-08-01",
            quarterly=EarningsData(eps_surprise="MEET"),
        )
        fd = MockFDClient(earnings=[record])
        signals = PEADStrategy().generate_signals(["AAPL"], fd)
        assert len(signals) == 0

    def test_no_quarterly_skipped(self):
        record = EarningsRecord(
            ticker="AAPL", report_period="2025-09-27",
            source_type="10-K", filing_date="2025-10-31",
        )
        fd = MockFDClient(earnings=[record])
        signals = PEADStrategy().generate_signals(["AAPL"], fd)
        assert len(signals) == 0

    def test_name(self):
        assert PEADStrategy().name == "pead"


# ---------------------------------------------------------------------------
# Unit tests — BacktestEngine
# ---------------------------------------------------------------------------

class TestBacktestEngine:
    def test_long_trade_pnl(self):
        # Stock goes from 100 to 105 over 5 days (1% daily)
        prices = _make_prices(100.0, 20, daily_change=0.01)
        fd = MockFDClient(prices=prices)

        signal = TradeSignal(
            ticker="TEST", direction="long",
            entry_date=prices[0].time[:10], holding_days=5,
        )
        engine = BacktestEngine(capital=100_000, per_trade=10_000)
        result = engine.run_signals([signal], fd)

        assert len(result.trades) == 1
        trade = result.trades[0]
        assert trade.direction == "long"
        assert trade.entry_price == 100.0
        assert trade.pnl > 0  # stock went up, long is profitable
        assert trade.return_pct > 0

    def test_short_trade_pnl(self):
        # Stock goes from 100 to 105 — short should lose
        prices = _make_prices(100.0, 20, daily_change=0.01)
        fd = MockFDClient(prices=prices)

        signal = TradeSignal(
            ticker="TEST", direction="short",
            entry_date=prices[0].time[:10], holding_days=5,
        )
        engine = BacktestEngine(capital=100_000, per_trade=10_000)
        result = engine.run_signals([signal], fd)

        assert len(result.trades) == 1
        assert result.trades[0].pnl < 0
        assert result.trades[0].return_pct < 0

    def test_position_sizing(self):
        prices = _make_prices(50.0, 20)
        fd = MockFDClient(prices=prices)

        signal = TradeSignal(
            ticker="TEST", direction="long",
            entry_date=prices[0].time[:10], holding_days=5,
        )
        engine = BacktestEngine(per_trade=10_000)
        result = engine.run_signals([signal], fd)

        # $10,000 / $50 = 200 shares
        assert result.trades[0].shares == 200.0

    def test_equity_curve(self):
        prices = _make_prices(100.0, 20, daily_change=0.01)
        fd = MockFDClient(prices=prices)

        signal = TradeSignal(
            ticker="TEST", direction="long",
            entry_date=prices[0].time[:10], holding_days=5,
        )
        engine = BacktestEngine(capital=50_000, per_trade=10_000)
        result = engine.run_signals([signal], fd)

        # Curve starts at capital, ends at capital + pnl
        assert result.equity_curve[0] == 50_000
        assert result.equity_curve[-1] == 50_000 + result.trades[0].pnl

    def test_empty_signals(self):
        fd = MockFDClient()
        engine = BacktestEngine()
        result = engine.run_signals([], fd)
        assert result.trades == []
        assert result.metrics is None

    def test_no_prices_skips_signal(self):
        fd = MockFDClient(prices=[])
        signal = TradeSignal(
            ticker="FAKE", direction="long",
            entry_date="2025-08-01", holding_days=5,
        )
        engine = BacktestEngine()
        result = engine.run_signals([signal], fd)
        assert result.trades == []

    def test_metadata_passes_through(self):
        prices = _make_prices(100.0, 20)
        fd = MockFDClient(prices=prices)

        signal = TradeSignal(
            ticker="TEST", direction="long",
            entry_date=prices[0].time[:10], holding_days=5,
            metadata={"eps_surprise": "BEAT", "source_type": "8-K", "report_period": "2025-06-28"},
        )
        engine = BacktestEngine()
        result = engine.run_signals([signal], fd)

        assert result.trades[0].metadata["eps_surprise"] == "BEAT"
        assert result.trades[0].metadata["source_type"] == "8-K"


# ---------------------------------------------------------------------------
# Unit tests — Metrics
# ---------------------------------------------------------------------------

class TestMetrics:
    def test_win_rate(self):
        # Two trades: one winner (+1%), one loser (-1%)
        prices_up = _make_prices(100.0, 20, daily_change=0.01)
        prices_down = _make_prices(100.0, 20, daily_change=-0.01)

        signals = [
            TradeSignal(ticker="UP", direction="long",
                        entry_date=prices_up[0].time[:10], holding_days=5),
            TradeSignal(ticker="DOWN", direction="long",
                        entry_date=prices_down[0].time[:10], holding_days=5),
        ]

        # Mock that returns different prices per ticker
        class MultiTickerMock:
            def get_prices(self, ticker, start_date, end_date, **kw):
                return prices_up if ticker == "UP" else prices_down

        engine = BacktestEngine()
        result = engine.run_signals(signals, MultiTickerMock())

        assert result.metrics.n_trades == 2
        assert result.metrics.win_rate == 0.5

    def test_max_drawdown(self):
        prices = _make_prices(100.0, 20, daily_change=-0.05)
        fd = MockFDClient(prices=prices)

        signal = TradeSignal(
            ticker="TEST", direction="long",
            entry_date=prices[0].time[:10], holding_days=5,
        )
        engine = BacktestEngine(capital=100_000, per_trade=10_000)
        result = engine.run_signals([signal], fd)

        # Stock dropped ~25% over 5 days, so we should have a drawdown
        assert result.metrics.max_drawdown_pct > 0


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
def test_pead_live(fd):
    strategy = PEADStrategy(holding_days=5, earnings_limit=4)
    engine = BacktestEngine()
    result = engine.run(strategy, ["AAPL"], fd)

    assert len(result.trades) > 0
    assert result.metrics is not None
    assert result.metrics.n_trades > 0
    import math
    assert math.isfinite(result.metrics.sharpe_ratio)
    assert math.isfinite(result.metrics.total_return_pct)
