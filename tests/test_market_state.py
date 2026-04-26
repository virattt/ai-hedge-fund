"""Tests for the market state verification agent."""

import json
from unittest.mock import patch, MagicMock
import pytest

from src.agents.market_state_verifier import (
    ticker_to_mic,
    fetch_market_status,
    market_state_verification_agent,
    SUFFIX_TO_MIC,
)


# ─── ticker_to_mic mapping ───────────────────────────────────────────────────


class TestTickerToMic:
    def test_us_equity_defaults_to_xnys(self):
        assert ticker_to_mic("AAPL") == "XNYS"
        assert ticker_to_mic("TSLA") == "XNYS"

    def test_london_suffix(self):
        assert ticker_to_mic("VOD.L") == "XLON"

    def test_tokyo_suffix(self):
        assert ticker_to_mic("7203.T") == "XJPX"

    def test_hong_kong_suffix(self):
        assert ticker_to_mic("0700.HK") == "XHKG"

    def test_sydney_suffix(self):
        assert ticker_to_mic("BHP.AX") == "XASX"

    def test_case_insensitive(self):
        assert ticker_to_mic("vod.l") == "XLON"

    def test_all_suffixes_mapped(self):
        """Every suffix in SUFFIX_TO_MIC resolves to a valid MIC."""
        for suffix, mic in SUFFIX_TO_MIC.items():
            assert len(mic) == 4
            assert mic == mic.upper()


# ─── fetch_market_status ─────────────────────────────────────────────────────


class TestFetchMarketStatus:
    @patch("src.agents.market_state_verifier.urlopen")
    def test_open_market_returns_open(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "receipt": {
                "mic": "XNYS",
                "status": "OPEN",
                "issued_at": "2026-04-07T15:00:00Z",
                "expires_at": "2026-04-07T15:01:00Z",
            }
        }).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = fetch_market_status("XNYS")
        assert result["status"] == "OPEN"
        assert result["mic"] == "XNYS"

    @patch("src.agents.market_state_verifier.urlopen")
    def test_closed_market_returns_closed(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "receipt": {"mic": "XNYS", "status": "CLOSED"}
        }).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = fetch_market_status("XNYS")
        assert result["status"] == "CLOSED"

    @patch("src.agents.market_state_verifier.urlopen")
    def test_network_error_returns_unknown(self, mock_urlopen):
        from urllib.error import URLError
        mock_urlopen.side_effect = URLError("Connection refused")

        result = fetch_market_status("XNYS")
        assert result["status"] == "UNKNOWN"
        assert "error" in result


# ─── market_state_verification_agent ─────────────────────────────────────────


def make_state(tickers):
    """Create a minimal AgentState for testing."""
    return {
        "messages": [],
        "data": {
            "tickers": tickers,
            "portfolio": {"cash": 100000, "positions": {}},
            "start_date": "2026-01-01",
            "end_date": "2026-04-07",
            "analyst_signals": {},
        },
        "metadata": {"show_reasoning": False, "model_name": "test", "model_provider": "test"},
    }


class TestMarketStateVerificationAgent:
    @patch("src.agents.market_state_verifier.fetch_market_status")
    def test_open_exchange_allows_trading(self, mock_fetch):
        mock_fetch.return_value = {
            "mic": "XNYS", "status": "OPEN",
            "issued_at": "2026-04-07T15:00:00Z",
            "expires_at": "2026-04-07T15:01:00Z",
        }
        state = make_state(["AAPL", "MSFT"])
        result = market_state_verification_agent(state)

        market_state = result["data"]["market_state"]
        assert market_state["AAPL"]["is_open"] is True
        assert market_state["MSFT"]["is_open"] is True

        msg = json.loads(result["messages"][0].content)
        assert msg["market_state_verification"]["blocked_count"] == 0

    @patch("src.agents.market_state_verifier.fetch_market_status")
    def test_closed_exchange_blocks_trading(self, mock_fetch):
        mock_fetch.return_value = {"mic": "XNYS", "status": "CLOSED"}
        state = make_state(["AAPL"])
        result = market_state_verification_agent(state)

        market_state = result["data"]["market_state"]
        assert market_state["AAPL"]["is_open"] is False
        assert "warning" in market_state["AAPL"]

        msg = json.loads(result["messages"][0].content)
        assert msg["market_state_verification"]["blocked_count"] == 1
        assert "AAPL" in msg["market_state_verification"]["blocked_tickers"]

    @patch("src.agents.market_state_verifier.fetch_market_status")
    def test_unknown_status_blocks_trading(self, mock_fetch):
        """Fail-closed: UNKNOWN must be treated as blocked."""
        mock_fetch.return_value = {"mic": "XNYS", "status": "UNKNOWN", "error": "timeout"}
        state = make_state(["AAPL"])
        result = market_state_verification_agent(state)

        assert result["data"]["market_state"]["AAPL"]["is_open"] is False

    @patch("src.agents.market_state_verifier.fetch_market_status")
    def test_halted_status_blocks_trading(self, mock_fetch):
        mock_fetch.return_value = {"mic": "XNYS", "status": "HALTED"}
        state = make_state(["AAPL"])
        result = market_state_verification_agent(state)

        assert result["data"]["market_state"]["AAPL"]["is_open"] is False

    @patch("src.agents.market_state_verifier.fetch_market_status")
    def test_deduplicates_mic_calls(self, mock_fetch):
        """Multiple tickers on the same exchange should only call the oracle once."""
        mock_fetch.return_value = {"mic": "XNYS", "status": "OPEN"}
        state = make_state(["AAPL", "MSFT", "GOOGL"])
        market_state_verification_agent(state)

        # All three are US equities → XNYS → single call
        assert mock_fetch.call_count == 1

    @patch("src.agents.market_state_verifier.fetch_market_status")
    def test_mixed_exchanges(self, mock_fetch):
        """Tickers on different exchanges get separate oracle calls."""
        def side_effect(mic, timeout=5):
            if mic == "XNYS":
                return {"mic": "XNYS", "status": "OPEN"}
            return {"mic": mic, "status": "CLOSED"}

        mock_fetch.side_effect = side_effect
        state = make_state(["AAPL", "VOD.L"])
        result = market_state_verification_agent(state)

        assert result["data"]["market_state"]["AAPL"]["is_open"] is True
        assert result["data"]["market_state"]["VOD.L"]["is_open"] is False
        assert mock_fetch.call_count == 2

    @patch("src.agents.market_state_verifier.fetch_market_status")
    def test_results_stored_in_analyst_signals(self, mock_fetch):
        """Market state should be accessible via state['data']['analyst_signals']."""
        mock_fetch.return_value = {"mic": "XNYS", "status": "OPEN"}
        state = make_state(["AAPL"])
        result = market_state_verification_agent(state)

        signals = result["data"]["analyst_signals"]
        assert "market_state_verifier" in signals
        assert signals["market_state_verifier"]["AAPL"]["status"] == "OPEN"
