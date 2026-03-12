"""Tests for autoresearch.risk_controls."""

from unittest.mock import patch

from autoresearch.risk_controls import (
    apply_stop_loss,
    scale_for_drawdown,
    should_halt_for_drawdown,
    volatility_weights,
)


def test_should_halt_for_drawdown_no_data():
    """When performance.csv does not exist (dd is None), we do not halt."""
    with patch("autoresearch.risk_controls.get_current_drawdown", return_value=None):
        halt, dd = should_halt_for_drawdown("/nonexistent", 15)
    assert halt is False
    assert dd is None


def test_scale_for_drawdown_no_data():
    assert scale_for_drawdown(1.0, "/nonexistent", 15) == 1.0


def test_apply_stop_loss():
    positions = {"AAPL": {"quantity": 100, "avg_price": 150.0}}
    prices = {"AAPL": 130.0}
    trim = apply_stop_loss(positions, prices, 10.0)
    assert "AAPL" in trim
    assert trim["AAPL"] == 0


def test_apply_stop_loss_no_trigger():
    positions = {"AAPL": {"quantity": 100, "avg_price": 150.0}}
    prices = {"AAPL": 145.0}
    trim = apply_stop_loss(positions, prices, 10.0)
    assert trim == {}


def test_volatility_weights():
    # Need >= 5 returns per ticker for vol computation. B has lower vol → higher weight.
    rets = {
        "A": [0.01, 0.02, -0.01, 0.01, 0.02],
        "B": [0.001, 0.001, 0.001, 0.001, 0.001],
    }
    w = volatility_weights(rets)
    assert "A" in w and "B" in w
    assert abs(sum(w.values()) - 1.0) < 1e-6
    assert w["B"] > w["A"]
