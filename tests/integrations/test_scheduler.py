"""Tests for the Alpaca trading daemon and scheduler helpers."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from integrations.alpaca.light_portfolio import generate_light_decisions
from integrations.alpaca.market_hours import is_regular_session, next_light_tick, session_open_datetime
from integrations.alpaca.session import SessionStore, TradingSessionState
from integrations.alpaca.strategy import SchedulerConfig
from integrations.alpaca.triggers import TriggerMonitor

ET = ZoneInfo("America/New_York")


def test_light_portfolio_hold_when_no_signal() -> None:
    portfolio = {
        "cash": 100_000.0,
        "positions": {"AAPL": {"long": 0, "short": 0}},
        "margin_requirement": 0.5,
        "margin_used": 0.0,
    }
    decisions = generate_light_decisions(
        ["AAPL"],
        analyst_signals={"risk_management_agent": {"AAPL": {"current_price": 100.0, "remaining_position_limit": 5000.0}}},
        portfolio=portfolio,
    )
    assert decisions["AAPL"]["action"] == "hold"


def test_light_portfolio_buy_on_bullish_consensus() -> None:
    portfolio = {
        "cash": 100_000.0,
        "positions": {"AAPL": {"long": 0, "short": 0}},
        "margin_requirement": 0.5,
        "margin_used": 0.0,
    }
    analyst_signals = {
        "risk_management_agent": {
            "AAPL": {"current_price": 100.0, "remaining_position_limit": 10_000.0},
        },
        "technical_analyst_agent": {
            "AAPL": {"signal": "bullish", "confidence": 80},
        },
        "fundamentals_analyst_agent": {
            "AAPL": {"signal": "bullish", "confidence": 70},
        },
    }
    decisions = generate_light_decisions(["AAPL"], analyst_signals, portfolio)
    assert decisions["AAPL"]["action"] == "buy"
    assert decisions["AAPL"]["quantity"] > 0


def test_session_store_roundtrip(tmp_path) -> None:
    store = SessionStore(tmp_path)
    state = TradingSessionState(trading_day="2026-07-09")
    state.mark_heavy(prices={"AAPL": 200.0}, spy_price=500.0)
    store.save(state)
    loaded = store.load(date(2026, 7, 9))
    assert loaded.heavy_open_completed is True
    assert loaded.open_reference_prices["AAPL"] == 200.0
    assert loaded.spy_open_price == 500.0


def test_trigger_price_swing(monkeypatch) -> None:
    config = SchedulerConfig(
        heavy_model_name="gpt-4.1",
        heavy_model_provider="OpenAI",
        heavy_analysts=("warren_buffett",),
        light_analysts=("technical_analyst",),
        light_interval_minutes=5,
        open_delay_minutes=5,
        price_swing_pct=2.0,
        spy_move_pct=1.0,
        trigger_cooldown_minutes=30,
        news_lookback_hours=24,
        session_dir="data/scheduler",
    )
    session = TradingSessionState(
        trading_day="2026-07-09",
        open_reference_prices={"AAPL": 100.0},
    )

    class FakePrice:
        def __init__(self, close: float):
            self.close = close

    monkeypatch.setattr(
        "integrations.alpaca.triggers.get_prices",
        lambda ticker, start, end: [FakePrice(105.0)],
    )
    monkeypatch.setattr(
        "integrations.alpaca.triggers.get_company_news",
        lambda *a, **k: [],
    )

    result = TriggerMonitor(config).evaluate(["AAPL"], session)
    assert result.fired is True
    assert any("AAPL" in reason for reason in result.reasons)


def test_regular_session_hours() -> None:
    open_dt = datetime(2026, 7, 9, 10, 0, tzinfo=ET)
    closed_dt = datetime(2026, 7, 9, 8, 0, tzinfo=ET)
    assert is_regular_session(open_dt) is True
    assert is_regular_session(closed_dt) is False


def test_next_light_tick_aligns_to_interval() -> None:
    dt = datetime(2026, 7, 9, 10, 2, tzinfo=ET)
    nxt = next_light_tick(dt, 5)
    assert nxt.minute % 5 == 0
    assert nxt > dt


def test_heavy_open_not_before_delay() -> None:
    config = SchedulerConfig(
        heavy_model_name="gpt-4.1",
        heavy_model_provider="OpenAI",
        heavy_analysts=("warren_buffett",),
        light_analysts=("technical_analyst",),
        light_interval_minutes=5,
        open_delay_minutes=5,
        price_swing_pct=2.0,
        spy_move_pct=1.0,
        trigger_cooldown_minutes=30,
        news_lookback_hours=24,
        session_dir="data/scheduler",
    )
    session = TradingSessionState(trading_day="2026-07-09")
    early = datetime(2026, 7, 9, 9, 32, tzinfo=ET)
    ready = session_open_datetime(date(2026, 7, 9), delay_minutes=config.open_delay_minutes)
    from integrations.alpaca.scheduler import _should_run_heavy_open

    assert _should_run_heavy_open(early, session, config) is False
    assert _should_run_heavy_open(ready, session, config) is True
