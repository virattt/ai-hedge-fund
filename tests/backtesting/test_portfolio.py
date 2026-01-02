import math

import pytest

from src.backtesting.portfolio import Portfolio

def test_apply_long_buy_basic(portfolio: Portfolio) -> None:
    executed = portfolio.apply_long_buy("AAPL", quantity=100, price=50.0)
    assert executed == 100
    snap = portfolio.get_snapshot()
    assert snap["positions"]["AAPL"]["long"] == 100
    assert snap["positions"]["AAPL"]["long_cost_basis"] == pytest.approx(50.0)
    # cash reduced by 5,000
    assert snap["cash"] == pytest.approx(95_000.0)


def test_apply_long_buy_partial_fill_when_insufficient_cash() -> None:
    p = Portfolio(tickers=["AAPL"], initial_cash=120.0, margin_requirement=0.5)
    # Request 10 shares at $20 = $200, but only $120 cash → max 6 shares
    executed = p.apply_long_buy("AAPL", quantity=10, price=20.0)
    assert executed == 6
    snap = p.get_snapshot()
    assert snap["positions"]["AAPL"]["long"] == 6
    assert snap["cash"] == pytest.approx(0.0)


def test_apply_long_sell_realized_gain_and_cost_basis_reset(portfolio: Portfolio) -> None:
    # Buy 100 @ 50, then sell 100 @ 60 → realized gain = 100 * (60-50) = 1000
    portfolio.apply_long_buy("AAPL", 100, 50.0)
    executed = portfolio.apply_long_sell("AAPL", 100, 60.0)
    assert executed == 100
    snap = portfolio.get_snapshot()
    assert snap["positions"]["AAPL"]["long"] == 0
    assert snap["positions"]["AAPL"]["long_cost_basis"] == pytest.approx(0.0)
    assert snap["realized_gains"]["AAPL"]["long"] == pytest.approx(1_000.0)
    # Cash: initial 100k - 5k + 6k = 101k
    assert snap["cash"] == pytest.approx(101_000.0)


def test_apply_long_sell_clamps_to_owned() -> None:
    p = Portfolio(tickers=["AAPL"], initial_cash=10_000.0, margin_requirement=0.5)
    p.apply_long_buy("AAPL", 10, 100.0)
    # Try to sell 20, but only 10 owned
    executed = p.apply_long_sell("AAPL", 20, 100.0)
    assert executed == 10
    assert p.get_snapshot()["positions"]["AAPL"]["long"] == 0


def test_apply_short_open_basic(portfolio: Portfolio) -> None:
    # Short 100 @ $30, margin 50% → proceeds 3,000; margin 1,500
    executed = portfolio.apply_short_open("MSFT", 100, 30.0)
    assert executed == 100
    snap = portfolio.get_snapshot()
    pos = snap["positions"]["MSFT"]
    assert pos["short"] == 100
    assert pos["short_cost_basis"] == pytest.approx(30.0)
    assert pos["short_margin_used"] == pytest.approx(1_500.0)
    assert snap["margin_used"] == pytest.approx(1_500.0)
    # Cash increases net by proceeds - margin = 3,000 - 1,500 = 1,500
    assert snap["cash"] == pytest.approx(101_500.0)


def test_apply_short_open_partial_when_insufficient_margin_cash() -> None:
    # Small cash: only enough margin for 4 shares at 50% of proceeds
    p = Portfolio(tickers=["AAPL"], initial_cash=200.0, margin_requirement=0.5)
    # price=100 → margin per share = 50, cash 200 → max 4 shares
    executed = p.apply_short_open("AAPL", 10, 100.0)
    assert executed == 4
    snap = p.get_snapshot()
    pos = snap["positions"]["AAPL"]
    assert pos["short"] == 4
    assert pos["short_margin_used"] == pytest.approx(200.0)
    # cash: + proceeds (400) - margin (200) = +200 → 400 total
    assert snap["cash"] == pytest.approx(400.0)


def test_apply_short_cover_realized_gain_and_margin_release(portfolio: Portfolio) -> None:
    # Open short 100 @ 50, then cover 40 @ 40 → gain = (50-40)*40 = 400
    portfolio.apply_short_open("AAPL", 100, 50.0)
    pre = portfolio.get_snapshot()
    pre_margin_used = pre["positions"]["AAPL"]["short_margin_used"]
    executed = portfolio.apply_short_cover("AAPL", 40, 40.0)
    assert executed == 40
    snap = portfolio.get_snapshot()
    pos = snap["positions"]["AAPL"]
    assert snap["realized_gains"]["AAPL"]["short"] == pytest.approx(400.0)
    # Proportional margin released: 40/100 of pre short_margin_used
    released = (40 / 100.0) * pre_margin_used
    assert pos["short_margin_used"] == pytest.approx(pre_margin_used - released)
    # Cash delta = +released - cover_cost(40*40=1600)
    expected_cash = pre["cash"] + released - 1_600.0
    assert snap["cash"] == pytest.approx(expected_cash)


def test_apply_short_cover_clamps_to_existing_short() -> None:
    p = Portfolio(tickers=["AAPL"], initial_cash=10_000.0, margin_requirement=0.5)
    p.apply_short_open("AAPL", 5, 100.0)
    executed = p.apply_short_cover("AAPL", 10, 100.0)
    assert executed == 5
    assert p.get_snapshot()["positions"]["AAPL"]["short"] == 0


@pytest.mark.parametrize("action", [
    ("buy"), ("sell"), ("short"), ("cover")
])
def test_zero_or_negative_quantity_is_noop(portfolio: Portfolio, action: str) -> None:
    before = portfolio.get_snapshot()
    if action == "buy":
        executed = portfolio.apply_long_buy("AAPL", 0, 10.0)
        executed2 = portfolio.apply_long_buy("AAPL", -5, 10.0)
    elif action == "sell":
        executed = portfolio.apply_long_sell("AAPL", 0, 10.0)
        executed2 = portfolio.apply_long_sell("AAPL", -5, 10.0)
    elif action == "short":
        executed = portfolio.apply_short_open("AAPL", 0, 10.0)
        executed2 = portfolio.apply_short_open("AAPL", -5, 10.0)
    else:
        executed = portfolio.apply_short_cover("AAPL", 0, 10.0)
        executed2 = portfolio.apply_short_cover("AAPL", -5, 10.0)
    after = portfolio.get_snapshot()
    assert executed == 0 and executed2 == 0
    assert after == before


