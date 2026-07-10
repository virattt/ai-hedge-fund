"""Tests for the Alpaca trading daemon and scheduler helpers."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from integrations.alpaca.light_portfolio import generate_light_decisions
from integrations.alpaca.market_hours import is_regular_session, next_light_tick, session_open_datetime
from integrations.alpaca.market_signals import MarketSignalEngine
from integrations.alpaca.price_feed import PriceSnapshot
from integrations.alpaca.rate_limit import RateLimiter
from integrations.alpaca.session import SessionStore, TradingSessionState
from integrations.alpaca.triggers import TriggerMonitor
from tests.integrations.scheduler_fixtures import sample_scheduler_config

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


def test_light_portfolio_holds_at_target_instead_of_stacking() -> None:
    """A position already at its conviction-scaled target must not grow."""
    portfolio = {
        "cash": 100_000.0,
        "positions": {"SBUX": {"long": 0, "short": 100, "short_cost_basis": 100.0}},
        "margin_requirement": 0.5,
        "margin_used": 5_000.0,
    }
    analyst_signals = {
        "risk_management_agent": {
            "SBUX": {
                "current_price": 100.0,
                "remaining_position_limit": 500.0,
                "reasoning": {"position_limit": 10_000.0},
            },
        },
        "technical_analyst_agent": {"SBUX": {"signal": "bearish", "confidence": 90}},
        "fundamentals_analyst_agent": {"SBUX": {"signal": "bearish", "confidence": 80}},
    }
    decisions = generate_light_decisions(["SBUX"], analyst_signals, portfolio)
    assert decisions["SBUX"]["action"] == "hold"
    assert "at target" in decisions["SBUX"]["reasoning"]


def test_light_portfolio_skips_dribble_orders_near_target() -> None:
    """Small residual deltas (< 5% of the limit) are not worth an order."""
    portfolio = {
        "cash": 100_000.0,
        "positions": {"O": {"long": 0, "short": 98, "short_cost_basis": 100.0}},
        "margin_requirement": 0.5,
        "margin_used": 4_900.0,
    }
    analyst_signals = {
        # No reasoning breakdown — falls back to remaining + existing value.
        "risk_management_agent": {
            "O": {"current_price": 100.0, "remaining_position_limit": 500.0},
        },
        "technical_analyst_agent": {"O": {"signal": "bearish", "confidence": 90}},
        "fundamentals_analyst_agent": {"O": {"signal": "bearish", "confidence": 80}},
    }
    decisions = generate_light_decisions(["O"], analyst_signals, portfolio)
    assert decisions["O"]["action"] == "hold"


def test_light_portfolio_ignores_weak_conviction() -> None:
    """Mixed votes below the 0.5 conviction threshold must not trade."""
    portfolio = {
        "cash": 100_000.0,
        "positions": {"TSLA": {"long": 0, "short": 0}},
        "margin_requirement": 0.5,
        "margin_used": 0.0,
    }
    analyst_signals = {
        "risk_management_agent": {
            "TSLA": {"current_price": 100.0, "remaining_position_limit": 10_000.0},
        },
    }
    # 7 bearish vs 3 bullish at equal confidence -> strength 0.4 (old code
    # shorted on this; it produced the 3-minute position ratchet live).
    for i in range(7):
        analyst_signals[f"bear_{i}_agent"] = {"TSLA": {"signal": "bearish", "confidence": 100}}
    for i in range(3):
        analyst_signals[f"bull_{i}_agent"] = {"TSLA": {"signal": "bullish", "confidence": 100}}
    decisions = generate_light_decisions(["TSLA"], analyst_signals, portfolio)
    assert decisions["TSLA"]["action"] == "hold"
    assert "below trade threshold" in decisions["TSLA"]["reasoning"]


def test_allowed_actions_respect_broker_buying_power() -> None:
    """Cash inflated by short proceeds must not enable trades when the
    broker reports zero buying power (Reg-T maxed account)."""
    from src.agents.portfolio_manager import compute_allowed_actions

    portfolio = {
        "cash": 215_000.0,  # includes short-sale proceeds — not spendable
        "equity": 100_000.0,
        "buying_power": 0.0,
        "margin_requirement": 0.5,
        "margin_used": 60_000.0,
        "positions": {"BAM": {"long": 0, "short": 10}},
    }
    allowed = compute_allowed_actions(["BAM"], {"BAM": 46.0}, {"BAM": 200}, portfolio)["BAM"]
    assert "buy" not in allowed
    assert "short" not in allowed
    assert allowed.get("cover") == 10  # closing positions is still fine


def test_light_portfolio_holds_when_buying_power_exhausted() -> None:
    portfolio = {
        "cash": 215_000.0,
        "equity": 100_000.0,
        "buying_power": 0.0,
        "margin_requirement": 0.5,
        "margin_used": 60_000.0,
        "positions": {"JPM": {"long": 0, "short": 0}},
    }
    analyst_signals = {
        "risk_management_agent": {
            "JPM": {"current_price": 337.0, "remaining_position_limit": 20_000.0},
        },
        "technical_analyst_agent": {"JPM": {"signal": "bullish", "confidence": 90}},
        "fundamentals_analyst_agent": {"JPM": {"signal": "bullish", "confidence": 85}},
    }
    decisions = generate_light_decisions(["JPM"], analyst_signals, portfolio)
    assert decisions["JPM"]["action"] == "hold"


def test_execute_orders_survives_broker_rejection() -> None:
    """A broker APIError (e.g. insufficient buying power) must not abort
    the cycle — it becomes a failed OrderResult."""
    from integrations.alpaca.executor import execute_orders
    from integrations.broker.models import OrderResult, TradeOrder

    class RejectingBroker:
        name = "fake"

        def submit_order(self, order):
            if order.ticker == "BAM":
                raise RuntimeError("insufficient buying power")
            return OrderResult(submitted=True, dry_run=False, order=order, message="ok")

    orders = [
        TradeOrder(ticker="BAM", action="short", quantity=243, reason="test"),
        TradeOrder(ticker="ABCB", action="sell", quantity=10, reason="test"),
    ]
    results = execute_orders(RejectingBroker(), orders, config=None)
    assert len(results) == 2
    assert results[0].submitted is False
    assert "insufficient buying power" in results[0].message
    assert results[1].submitted is True  # later orders still ran


def test_light_cycle_survives_analyst_failure(monkeypatch) -> None:
    """A dead data feed for one analyst (e.g. DNS failure to Finnhub) must
    not abort the light cycle — remaining analysts still vote."""
    from integrations.alpaca import light_cycle

    def fake_nodes():
        def broken_agent(state):
            raise ConnectionError("Failed to resolve 'finnhub.io'")

        def working_agent(state):
            return {
                "data": {
                    "analyst_signals": {
                        "technical_analyst_agent": {
                            "AAPL": {"signal": "bullish", "confidence": 80},
                        }
                    }
                }
            }

        return {
            "growth_analyst": ("growth_analyst_agent", broken_agent),
            "technical_analyst": ("technical_analyst_agent", working_agent),
        }

    def fake_risk(state):
        return {
            "data": {
                "analyst_signals": {
                    "risk_management_agent": {
                        "AAPL": {"current_price": 100.0, "remaining_position_limit": 10_000.0},
                    }
                }
            }
        }

    monkeypatch.setattr(light_cycle, "get_analyst_nodes", fake_nodes)
    monkeypatch.setattr(light_cycle, "risk_management_agent", fake_risk)

    portfolio = {"cash": 100_000.0, "positions": {"AAPL": {"long": 0, "short": 0}}, "margin_requirement": 0.5, "margin_used": 0.0}
    result = light_cycle.run_light_analysis(
        tickers=["AAPL"],
        portfolio=portfolio,
        start_date="2026-04-10",
        end_date="2026-07-10",
        light_analysts=["growth_analyst", "technical_analyst"],
    )
    assert result["decisions"]["AAPL"]["action"] == "buy"  # tech signal alone drove it
    assert "technical_analyst_agent" in result["analyst_signals"]


def test_light_cycle_holds_everything_when_risk_manager_fails(monkeypatch) -> None:
    from integrations.alpaca import light_cycle

    def fake_nodes():
        def working_agent(state):
            return {
                "data": {
                    "analyst_signals": {
                        "technical_analyst_agent": {
                            "AAPL": {"signal": "bearish", "confidence": 95},
                        }
                    }
                }
            }

        return {"technical_analyst": ("technical_analyst_agent", working_agent)}

    def broken_risk(state):
        raise ConnectionError("Failed to resolve 'finnhub.io'")

    monkeypatch.setattr(light_cycle, "get_analyst_nodes", fake_nodes)
    monkeypatch.setattr(light_cycle, "risk_management_agent", broken_risk)

    portfolio = {"cash": 100_000.0, "positions": {"AAPL": {"long": 50, "short": 0}}, "margin_requirement": 0.5, "margin_used": 0.0}
    result = light_cycle.run_light_analysis(
        tickers=["AAPL"],
        portfolio=portfolio,
        start_date="2026-04-10",
        end_date="2026-07-10",
        light_analysts=["technical_analyst"],
    )
    decision = result["decisions"]["AAPL"]
    assert decision["action"] == "hold"  # never trade without price/risk data
    assert decision["quantity"] == 0


def test_light_portfolio_unwinds_opposing_position() -> None:
    portfolio = {
        "cash": 100_000.0,
        "positions": {"MS": {"long": 0, "short": 50, "short_cost_basis": 100.0}},
        "margin_requirement": 0.5,
        "margin_used": 2_500.0,
    }
    analyst_signals = {
        "risk_management_agent": {
            "MS": {"current_price": 100.0, "remaining_position_limit": 10_000.0},
        },
        "technical_analyst_agent": {"MS": {"signal": "bullish", "confidence": 90}},
        "fundamentals_analyst_agent": {"MS": {"signal": "bullish", "confidence": 80}},
    }
    decisions = generate_light_decisions(["MS"], analyst_signals, portfolio)
    assert decisions["MS"]["action"] == "cover"
    assert decisions["MS"]["quantity"] == 50


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
    config = sample_scheduler_config()
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
    config = sample_scheduler_config()
    session = TradingSessionState(trading_day="2026-07-09")
    early = datetime(2026, 7, 9, 9, 32, tzinfo=ET)
    ready = session_open_datetime(date(2026, 7, 9), delay_minutes=config.open_delay_minutes)
    from integrations.alpaca.scheduler import _should_run_heavy_open

    assert _should_run_heavy_open(early, session, config) is False
    assert _should_run_heavy_open(ready, session, config) is True


def test_heavy_open_backs_off_after_failed_attempt() -> None:
    """A crashed heavy-open cycle (e.g. provider 429) must not retry in a hot loop."""
    config = sample_scheduler_config(heavy_open_retry_minutes=10)
    session = TradingSessionState(trading_day="2026-07-09")
    from integrations.alpaca.scheduler import _should_run_heavy_open

    session.last_heavy_attempt_at = datetime(2026, 7, 9, 9, 36, tzinfo=ET).isoformat()
    just_after = datetime(2026, 7, 9, 9, 37, tzinfo=ET)
    assert _should_run_heavy_open(just_after, session, config) is False

    past_backoff = datetime(2026, 7, 9, 9, 47, tzinfo=ET)
    assert _should_run_heavy_open(past_backoff, session, config) is True


def test_speculative_batch_rotates_and_wraps() -> None:
    from integrations.alpaca.scheduler import next_speculative_batch

    universe = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN"]
    held = ["MSFT"]

    batch1, cursor = next_speculative_batch(universe, held, 0, 3)
    assert batch1 == ["AAPL", "NVDA", "GOOGL"]

    batch2, cursor = next_speculative_batch(universe, held, cursor, 3)
    assert batch2 == ["AMZN", "AAPL", "NVDA"]  # wraps around, skips held MSFT

    assert next_speculative_batch(universe, universe, 0, 3) == ([], 0)
    assert next_speculative_batch(universe, [], 0, 0) == ([], 0)


def test_session_seed_open_references_only_fills_missing() -> None:
    session = TradingSessionState(trading_day="2026-07-09")
    session.mark_heavy(prices={"AAPL": 200.0})
    session.seed_open_references({"AAPL": 999.0, "NVDA": 150.0})
    assert session.open_reference_prices["AAPL"] == 200.0  # heavy price wins
    assert session.open_reference_prices["NVDA"] == 150.0

    # A later heavy on another batch merges rather than replaces.
    session.mark_heavy(prices={"GOOGL": 180.0})
    assert session.open_reference_prices["NVDA"] == 150.0
    assert session.open_reference_prices["GOOGL"] == 180.0


def test_market_signal_promotes_heavy_on_open_move() -> None:
    config = sample_scheduler_config(price_swing_pct=2.0)
    session = TradingSessionState(
        trading_day="2026-07-09",
        heavy_open_completed=True,
        open_reference_prices={"AAPL": 100.0},
        last_watch_prices={"AAPL": 100.0},
    )
    snapshots = {"AAPL": PriceSnapshot("AAPL", 103.0, "2026-07-09T10:00:00")}
    result = MarketSignalEngine(config).evaluate(["AAPL"], session, snapshots)
    assert result.promote == "heavy"
    assert any("vs open" in a for a in result.alerts)
    assert result.heavy_symbols == ["AAPL"]


def test_market_signal_promotes_light_on_tick_move() -> None:
    config = sample_scheduler_config(watch_tick_move_pct=0.5)
    session = TradingSessionState(
        trading_day="2026-07-09",
        heavy_open_completed=True,
        open_reference_prices={"AAPL": 100.0},
        last_watch_prices={"AAPL": 100.0},
    )
    snapshots = {"AAPL": PriceSnapshot("AAPL", 100.6, "2026-07-09T10:01:00")}
    result = MarketSignalEngine(config).evaluate(["AAPL"], session, snapshots)
    assert result.promote == "light"
    # Light tick moves must never leak into the heavy (LLM) focus list.
    assert result.light_symbols == ["AAPL"]
    assert result.heavy_symbols == []


def test_light_tick_symbols_do_not_join_heavy_focus() -> None:
    """One heavy alert + many light tick alerts: heavy focus stays scoped."""
    config = sample_scheduler_config(price_swing_pct=2.0, watch_tick_move_pct=0.5)
    session = TradingSessionState(
        trading_day="2026-07-09",
        heavy_open_completed=True,
        open_reference_prices={"AAPL": 100.0, "MSFT": 100.0, "NVDA": 100.0},
        last_watch_prices={"AAPL": 100.0, "MSFT": 100.0, "NVDA": 100.0},
    )
    snapshots = {
        "AAPL": PriceSnapshot("AAPL", 103.0, "t"),  # heavy: vs open swing
        "MSFT": PriceSnapshot("MSFT", 100.9, "t"),  # light: tick move
        "NVDA": PriceSnapshot("NVDA", 99.2, "t"),  # light: tick move
    }
    result = MarketSignalEngine(config).evaluate(["AAPL", "MSFT", "NVDA"], session, snapshots)
    assert result.promote == "heavy"
    assert result.heavy_symbols == ["AAPL"]
    assert set(result.light_symbols) >= {"MSFT", "NVDA"}
    assert result.heavy_alerts and all("AAPL" in a for a in result.heavy_alerts)


def test_heavy_cooldown_moves_symbols_to_light() -> None:
    config = sample_scheduler_config(price_swing_pct=2.0, trigger_cooldown_minutes=30)
    session = TradingSessionState(
        trading_day="2026-07-09",
        heavy_open_completed=True,
        open_reference_prices={"AAPL": 100.0},
        last_watch_prices={"AAPL": 100.0},
    )
    from integrations.alpaca.market_hours import now_et

    session.last_heavy_at = now_et().isoformat()  # cooldown active
    snapshots = {"AAPL": PriceSnapshot("AAPL", 103.0, "t")}
    result = MarketSignalEngine(config).evaluate(["AAPL"], session, snapshots)
    assert result.promote == "light"
    assert result.heavy_symbols == []
    assert result.heavy_alerts == []
    assert "AAPL" in result.light_symbols


def test_rate_limiter_caps_burst() -> None:
    limiter = RateLimiter(max_per_minute=3)
    for _ in range(3):
        limiter.wait()
    assert limiter.available == 0
