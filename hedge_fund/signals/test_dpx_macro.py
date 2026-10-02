"""Tests for DPXMacroStabilityModel."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import Mock, patch

import requests

from hedge_fund.models import Signal
from hedge_fund.signals import QuantModel
from hedge_fund.signals.base import AlphaModel
from hedge_fund.signals.dpx_macro import DPXMacroStabilityModel

_TODAY = date.today().strftime("%Y-%m-%d")
_YESTERDAY = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")


def _reliability(score: float, status: str, peg_bps: float = 0.0) -> dict:
    return {
        "stability": {
            "currentScore": score,
            "latestStatus": status,
            "threshold": {"stable": 90, "caution": 75, "unstable": 0},
        },
        "peg": {"deviationBps": peg_bps},
    }


class TestInterface:
    def test_is_quant_model_is_alpha_model(self):
        assert issubclass(QuantModel, AlphaModel)
        assert issubclass(DPXMacroStabilityModel, QuantModel)

    def test_name(self):
        assert DPXMacroStabilityModel().name == "dpx_macro"

    def test_returns_signal_type(self):
        with patch("hedge_fund.signals.dpx_macro.requests.get") as mock_get:
            mock_get.return_value = Mock(
                json=lambda: _reliability(95, "STABLE"),
                raise_for_status=lambda: None,
            )
            sig = DPXMacroStabilityModel().predict("AAPL", _TODAY, None)
        assert isinstance(sig, Signal)


class TestConviction:
    def test_stable_conditions_are_bullish(self):
        with patch("hedge_fund.signals.dpx_macro.requests.get") as mock_get:
            mock_get.return_value = Mock(
                json=lambda: _reliability(100, "STABLE"),
                raise_for_status=lambda: None,
            )
            sig = DPXMacroStabilityModel().predict("AAPL", _TODAY, None)
        assert sig.value > 0

    def test_unstable_conditions_are_bearish(self):
        with patch("hedge_fund.signals.dpx_macro.requests.get") as mock_get:
            mock_get.return_value = Mock(
                json=lambda: _reliability(20, "UNSTABLE"),
                raise_for_status=lambda: None,
            )
            sig = DPXMacroStabilityModel().predict("AAPL", _TODAY, None)
        assert sig.value < 0

    def test_signal_is_ticker_agnostic(self):
        # Same macro conditions -> same conviction regardless of ticker
        with patch("hedge_fund.signals.dpx_macro.requests.get") as mock_get:
            mock_get.return_value = Mock(
                json=lambda: _reliability(80, "CAUTION"),
                raise_for_status=lambda: None,
            )
            model = DPXMacroStabilityModel()
            sig_a = model.predict("AAPL", _TODAY, None)
            sig_b = model.predict("MSFT", _TODAY, None)
        assert sig_a.value == sig_b.value


class TestPointInTime:
    def test_abstains_for_non_today_date(self):
        # No historical query available -- must not fabricate a past view
        sig = DPXMacroStabilityModel().predict("AAPL", _YESTERDAY, None)
        assert sig.value == 0.0
        assert "live-only" in sig.reasoning.lower()

    def test_abstains_on_infrastructure_failure(self):
        with patch("hedge_fund.signals.dpx_macro.requests.get") as mock_get:
            mock_get.side_effect = requests.ConnectionError("boom")
            sig = DPXMacroStabilityModel().predict("AAPL", _TODAY, None)
        assert sig.value == 0.0
        assert "unavailable" in sig.reasoning.lower()

    def test_caches_within_same_predict_call_date(self):
        with patch("hedge_fund.signals.dpx_macro.requests.get") as mock_get:
            mock_get.return_value = Mock(
                json=lambda: _reliability(80, "CAUTION"),
                raise_for_status=lambda: None,
            )
            model = DPXMacroStabilityModel()
            model.predict("AAPL", _TODAY, None)
            model.predict("MSFT", _TODAY, None)
        assert mock_get.call_count == 1
