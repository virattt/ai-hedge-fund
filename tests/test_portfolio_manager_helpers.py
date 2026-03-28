"""Tests for portfolio manager helper functions.

Tests the deterministic, non-LLM functions in src/agents/portfolio_manager.py:
- compute_allowed_actions
- _compact_signals
"""

import pytest

from src.agents.portfolio_manager import compute_allowed_actions, _compact_signals


class TestComputeAllowedActions:
    """Validate the deterministic constraint calculation for trading actions."""

    def _base_portfolio(self, cash=100_000.0, positions=None, margin_requirement=0.5):
        return {
            "cash": cash,
            "positions": positions or {},
            "margin_requirement": margin_requirement,
            "margin_used": 0.0,
            "equity": cash,
        }

    def test_no_positions_buy_allowed(self):
        portfolio = self._base_portfolio(cash=10_000.0)
        result = compute_allowed_actions(
            tickers=["AAPL"],
            current_prices={"AAPL": 100.0},
            max_shares={"AAPL": 50},
            portfolio=portfolio,
        )
        assert result["AAPL"]["buy"] == 50  # min(50 max_shares, 100 affordable)
        assert "sell" not in result["AAPL"] or result["AAPL"].get("sell", 0) == 0
        assert "hold" in result["AAPL"]

    def test_buy_capped_by_cash(self):
        portfolio = self._base_portfolio(cash=200.0)
        result = compute_allowed_actions(
            tickers=["AAPL"],
            current_prices={"AAPL": 100.0},
            max_shares={"AAPL": 50},
            portfolio=portfolio,
        )
        # Can only afford 2 shares at $100 each
        assert result["AAPL"]["buy"] == 2

    def test_sell_limited_to_long_shares(self):
        portfolio = self._base_portfolio(
            positions={"AAPL": {"long": 25, "short": 0, "long_cost_basis": 100.0, "short_cost_basis": 0.0}},
        )
        result = compute_allowed_actions(
            tickers=["AAPL"],
            current_prices={"AAPL": 100.0},
            max_shares={"AAPL": 50},
            portfolio=portfolio,
        )
        assert result["AAPL"]["sell"] == 25

    def test_cover_limited_to_short_shares(self):
        portfolio = self._base_portfolio(
            positions={"AAPL": {"long": 0, "short": 10, "long_cost_basis": 0.0, "short_cost_basis": 150.0}},
        )
        result = compute_allowed_actions(
            tickers=["AAPL"],
            current_prices={"AAPL": 100.0},
            max_shares={"AAPL": 50},
            portfolio=portfolio,
        )
        assert result["AAPL"]["cover"] == 10

    def test_zero_price_disables_buy_and_short(self):
        portfolio = self._base_portfolio(cash=100_000.0)
        result = compute_allowed_actions(
            tickers=["AAPL"],
            current_prices={"AAPL": 0.0},
            max_shares={"AAPL": 100},
            portfolio=portfolio,
        )
        # With zero price, no buy or short should be possible
        assert result["AAPL"].get("buy", 0) == 0
        assert result["AAPL"].get("short", 0) == 0
        assert "hold" in result["AAPL"]

    def test_zero_max_shares_disables_buy(self):
        portfolio = self._base_portfolio(cash=100_000.0)
        result = compute_allowed_actions(
            tickers=["AAPL"],
            current_prices={"AAPL": 100.0},
            max_shares={"AAPL": 0},
            portfolio=portfolio,
        )
        assert result["AAPL"].get("buy", 0) == 0

    def test_zero_cash_disables_buy(self):
        portfolio = self._base_portfolio(cash=0.0)
        result = compute_allowed_actions(
            tickers=["AAPL"],
            current_prices={"AAPL": 100.0},
            max_shares={"AAPL": 50},
            portfolio=portfolio,
        )
        assert result["AAPL"].get("buy", 0) == 0

    def test_multiple_tickers(self):
        portfolio = self._base_portfolio(cash=10_000.0)
        result = compute_allowed_actions(
            tickers=["AAPL", "MSFT"],
            current_prices={"AAPL": 100.0, "MSFT": 200.0},
            max_shares={"AAPL": 50, "MSFT": 25},
            portfolio=portfolio,
        )
        assert "AAPL" in result
        assert "MSFT" in result
        # Both should have buy and hold
        assert result["AAPL"]["buy"] > 0
        assert result["MSFT"]["buy"] > 0

    def test_short_capped_by_margin(self):
        portfolio = self._base_portfolio(cash=1_000.0, margin_requirement=0.5)
        # equity=1000, margin_req=0.5 → available_margin = 1000/0.5 - 0 = 2000
        # At $100/share → max_short_margin = 20, but max_shares caps at 10
        result = compute_allowed_actions(
            tickers=["AAPL"],
            current_prices={"AAPL": 100.0},
            max_shares={"AAPL": 10},
            portfolio=portfolio,
        )
        assert result["AAPL"]["short"] == 10

    def test_hold_always_present(self):
        portfolio = self._base_portfolio(cash=0.0)
        result = compute_allowed_actions(
            tickers=["AAPL"],
            current_prices={"AAPL": 100.0},
            max_shares={"AAPL": 0},
            portfolio=portfolio,
        )
        assert "hold" in result["AAPL"]

    def test_missing_ticker_in_positions_uses_defaults(self):
        portfolio = self._base_portfolio(cash=10_000.0, positions={})
        result = compute_allowed_actions(
            tickers=["AAPL"],
            current_prices={"AAPL": 50.0},
            max_shares={"AAPL": 100},
            portfolio=portfolio,
        )
        # No existing position, so no sell or cover
        assert result["AAPL"].get("sell", 0) == 0
        assert result["AAPL"].get("cover", 0) == 0


class TestCompactSignals:
    """Test the signal compression for LLM prompt construction."""

    def test_basic_compression(self):
        signals = {
            "AAPL": {
                "warren_buffett": {"sig": "bullish", "conf": 0.85},
                "michael_burry": {"sig": "bearish", "conf": 0.60},
            }
        }
        result = _compact_signals(signals)
        assert result["AAPL"]["warren_buffett"] == {"sig": "bullish", "conf": 0.85}

    def test_alternative_key_names(self):
        """Handles both 'sig'/'conf' and 'signal'/'confidence' key formats."""
        signals = {
            "AAPL": {
                "agent1": {"signal": "bullish", "confidence": 0.9},
            }
        }
        result = _compact_signals(signals)
        assert result["AAPL"]["agent1"]["sig"] == "bullish"
        assert result["AAPL"]["agent1"]["conf"] == 0.9

    def test_empty_agents_preserved(self):
        signals = {"AAPL": {}}
        result = _compact_signals(signals)
        assert result["AAPL"] == {}

    def test_none_signal_dropped(self):
        signals = {
            "AAPL": {
                "agent1": {"sig": None, "conf": 0.5},
                "agent2": {"sig": "bullish", "conf": 0.8},
            }
        }
        result = _compact_signals(signals)
        assert "agent1" not in result["AAPL"]
        assert "agent2" in result["AAPL"]

    def test_none_confidence_dropped(self):
        signals = {
            "AAPL": {
                "agent1": {"sig": "bullish", "conf": None},
            }
        }
        result = _compact_signals(signals)
        assert "agent1" not in result["AAPL"]

    def test_multiple_tickers(self):
        signals = {
            "AAPL": {"a1": {"sig": "bullish", "conf": 0.9}},
            "MSFT": {"a2": {"sig": "bearish", "conf": 0.7}},
        }
        result = _compact_signals(signals)
        assert len(result) == 2
        assert "AAPL" in result and "MSFT" in result
